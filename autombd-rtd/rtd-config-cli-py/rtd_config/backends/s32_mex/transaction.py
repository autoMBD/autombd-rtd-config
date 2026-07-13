# =================================================================================
# The MIT License
# MIT许可证
#
# <https://opensource.org/license/mit>
#
# SPDX short identifier / SPDX 短标识符：MIT
#
# Copyright (c) 2026 autoMBD
# 版权所有 (c) 2026 autoMBD
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 特此向获得本软件及相关文档（合称"本软件"）副本的任何人免费授予不受限制地利用本软
# 件的许可，包括而不限于：使用、复制、修改、合并、发布、分发、分许可和/或销售本软
# 件副本，并允许本软件的接收者也获得前述许可，但须遵守以下条件：
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 以上版权声明及本许可声明应包含在本软件的所有副本或主要部分中。
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALLTHE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 本软件系"按原样"提供，不包含任何形式的明示或默示保证，包括但不限于适销性、特定
# 目的适用性及不侵权的保证。在任何情况下，无论是在合同、侵权或其他案件中，作者或版
# 权持有人均不对因本软件、或因本软件的使用或其他利用而引起的、引发的或与之相关的任
# 何权利主张、损害赔偿或其他责任承担责任。
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        transaction.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Execute fail-closed, atomic S32 .mex configure transactions.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import stat
from typing import TYPE_CHECKING, Callable

from ...errors import CliFailure
from .apply import ApplyResult
from .document import MexDocument
from .metadata import (
    revalidate_project_metadata,
    revalidate_project_metadata_after_release,
)
from .target import (
    AtomicPublishResult,
    FileSnapshot,
    PublishExpectation,
    atomic_publish_candidate,
    release_for_publish,
    revalidate_publish_expectation,
    revalidate_snapshot,
    rollback_atomic_publish,
)

if TYPE_CHECKING:
    from ...intent import Intent
    from ...project import Project


@dataclass(frozen=True)
class ConfigureTransactionResult:
    status: str
    apply_result: ApplyResult
    static_result: object | None
    vendor_result: object | None
    published_bytes: bytes
    changed_modules: list[str]
    no_op: bool = False


class ConfigureTransaction:
    """Own one verified project snapshot from apply through atomic publish."""

    def __init__(
        self,
        project: "Project",
        *,
        plan: object | None = None,
        backup: bool = False,
        static_runner: Callable[..., object],
        vendor_runner: Callable[..., object] | None = None,
        atomic_publish_fn: Callable[..., AtomicPublishResult] = atomic_publish_candidate,
        backup_replace_fn: Callable[[Path, Path], None] = os.replace,
        release_for_publish_fn: Callable[..., PublishExpectation] = release_for_publish,
    ) -> None:
        self.project = project
        self.plan = plan
        self.target = project.verified_target
        self.original = self.target.mex
        self.metadata = project.metadata
        self.bundle = project.asset_bundle
        self.backup = backup
        self.static_runner = static_runner
        self.vendor_runner = vendor_runner
        self.atomic_publish_fn = atomic_publish_fn
        self.backup_replace_fn = backup_replace_fn
        self.release_for_publish_fn = release_for_publish_fn
        self.platform = self.target.lease._resources.get("platform")
        if self.platform is None:
            raise CliFailure(
                "project_identity_unavailable",
                "The verified project target lacks a publish-capable platform adapter.",
                module="backend",
            )

    def execute(self, intent: "Intent", apply_fn: Callable[..., ApplyResult]) -> ConfigureTransactionResult:
        staging: Path | None = None
        backup_staging: Path | None = None
        restore_staging: Path | None = None
        cleanup: list[Path] = []
        try:
            self.metadata.require_identity()
            revalidate_snapshot(self.target, platform=self.platform)
            revalidate_project_metadata(self.target, self.metadata)

            apply_result = apply_fn(
                self.project.document, intent, bundle=self.bundle
            )
            if apply_result.blocked:
                return self._result("blocked", apply_result, None, None, self.original.content)

            candidate = self.project.document.render()
            no_op = candidate == self.original.content

            staging = self._stage_bytes(candidate, "candidate")
            cleanup.append(staging)
            candidate_snapshot = self._snapshot_staging(staging, candidate)
            candidate_doc = MexDocument.from_snapshot(candidate_snapshot)
            static_result = self.static_runner(
                staging,
                doc=candidate_doc,
                verified_target=self.target,
                modified_elements=apply_result.modified_elements,
                requested_callback=intent.payload.get("callback"),
                bundle=self.bundle,
            )
            if getattr(static_result, "status", None) != "passed":
                return self._result(
                    "blocked", apply_result, static_result, None, self.original.content
                )

            vendor_result = None
            if self.vendor_runner is not None:
                vendor_result = self.vendor_runner(
                    staging=staging,
                    document=candidate_doc,
                    project=self.project,
                    bundle=self.bundle,
                )
                if getattr(vendor_result, "status", None) != "passed":
                    return self._result(
                        "blocked", apply_result, static_result, vendor_result,
                        self.original.content,
                    )

            revalidate_snapshot(self.target, platform=self.platform)
            revalidate_project_metadata(self.target, self.metadata)
            if no_op:
                return self._result(
                    "passed", apply_result, static_result, vendor_result,
                    self.original.content, changed_modules=[], no_op=True,
                )

            backup_path = self.original.path.with_name(self.original.path.name + ".bak")
            backup_before = self._backup_before(backup_path) if self.backup else None
            if self.backup:
                backup_staging = self._stage_bytes(self.original.content, "backup")
                cleanup.append(backup_staging)
                if backup_before is not None:
                    restore_staging = self._stage_bytes(backup_before.content, "restore")
                    cleanup.append(restore_staging)

            expectation = self.release_for_publish_fn(self.target)
            revalidate_publish_expectation(expectation, platform=self.platform)
            revalidate_project_metadata_after_release(self.project.root, self.metadata)
            if self.backup:
                self._revalidate_backup(backup_path, backup_before)
                assert backup_staging is not None
                self._replace_backup(backup_staging, backup_path)
                cleanup.remove(backup_staging)
                backup_staging = None

            try:
                publication = self.atomic_publish_fn(
                    expectation,
                    staging,
                    hashlib.sha256(candidate).hexdigest(),
                    platform=self.platform,
                )
            except CliFailure:
                if self.backup:
                    self._rollback_backup(backup_path, backup_before, restore_staging)
                    if restore_staging is not None and not restore_staging.exists():
                        cleanup.remove(restore_staging)
                        restore_staging = None
                raise
            except Exception as exc:
                if self.backup:
                    self._rollback_backup(backup_path, backup_before, restore_staging)
                raise CliFailure(
                    "configure_publish_failed",
                    "The atomic publication adapter failed unexpectedly.",
                    module="backend",
                ) from exc
            if publication.displaced_path not in cleanup:
                cleanup.append(publication.displaced_path)
            try:
                self._flush_directory(self.original.path.parent)
            except CliFailure:
                rollback_atomic_publish(
                    publication, self.original.path, platform=self.platform
                )
                raise
            return self._result(
                "passed", apply_result, static_result, vendor_result,
                publication.published.content,
            )
        finally:
            if not self.target.lease.closed:
                self.target.close()
            self._cleanup(cleanup)

    def _result(
        self,
        status: str,
        apply_result: ApplyResult,
        static_result: object | None,
        vendor_result: object | None,
        published_bytes: bytes,
        *,
        changed_modules: list[str] | None = None,
        no_op: bool = False,
    ) -> ConfigureTransactionResult:
        return ConfigureTransactionResult(
            status=status,
            apply_result=apply_result,
            static_result=static_result,
            vendor_result=vendor_result,
            published_bytes=published_bytes,
            changed_modules=(
                list(apply_result.changed_modules)
                if changed_modules is None and status == "passed"
                else list(changed_modules or [])
            ),
            no_op=no_op,
        )

    def _stage_bytes(self, content: bytes, purpose: str) -> Path:
        prefix = f".{self.original.path.name}.{purpose}."
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        for _ in range(32):
            path = self.original.path.parent / f"{prefix}{secrets.token_hex(12)}.tmp"
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError:
                continue
            try:
                view = memoryview(content)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise OSError("short staging write")
                    view = view[written:]
                os.fsync(descriptor)
                os.close(descriptor)
                descriptor = -1
                return path
            except BaseException as exc:
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                raise CliFailure(
                    "configure_staging_failed",
                    "A transaction staging file could not be written durably.",
                    module="backend",
                    details={"purpose": purpose},
                ) from exc
        raise CliFailure(
            "configure_staging_failed",
            "A unique transaction staging file could not be allocated.",
            module="backend",
            details={"purpose": purpose},
        )

    def _snapshot_staging(self, path: Path, expected: bytes) -> FileSnapshot:
        try:
            snapshot = self.platform.snapshot_file(path)
        except (OSError, ValueError, RuntimeError) as exc:
            raise CliFailure(
                "configure_staging_changed",
                "The transaction staging file could not be verified safely.",
                module="backend",
            ) from exc
        expected_sha = hashlib.sha256(expected).hexdigest()
        if snapshot.sha256 != expected_sha or snapshot.content != expected:
            raise CliFailure(
                "configure_staging_changed",
                "The transaction staging file changed before validation.",
                module="backend",
            )
        return snapshot

    def _backup_before(self, path: Path) -> FileSnapshot | None:
        try:
            status = os.lstat(path)
        except FileNotFoundError:
            return None
        attributes = getattr(status, "st_file_attributes", 0)
        reparse = bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        if stat.S_ISLNK(status.st_mode) or reparse or not stat.S_ISREG(status.st_mode):
            raise CliFailure(
                "unsafe_backup_target",
                "The configured backup target is not a safe regular file.",
                module="backend",
            )
        try:
            return self.platform.snapshot_file(path)
        except (OSError, ValueError, RuntimeError) as exc:
            raise CliFailure(
                "configure_backup_failed",
                "The existing backup could not be snapshotted safely.",
                module="backend",
            ) from exc

    def _revalidate_backup(self, path: Path, expected: FileSnapshot | None) -> None:
        current = self._backup_before(path)
        if expected is None:
            if current is not None:
                raise CliFailure(
                    "configure_backup_changed",
                    "The backup target changed before publication.",
                    module="backend",
                )
        elif current is None or (
            current.identity != expected.identity or current.sha256 != expected.sha256
        ):
            raise CliFailure(
                "configure_backup_changed",
                "The backup target changed before publication.",
                module="backend",
            )

    def _replace_backup(self, source: Path, target: Path) -> None:
        try:
            self.backup_replace_fn(source, target)
        except OSError as exc:
            raise CliFailure(
                "configure_backup_failed",
                "The original snapshot could not be published as a backup.",
                module="backend",
            ) from exc

    def _rollback_backup(
        self,
        path: Path,
        before: FileSnapshot | None,
        restore: Path | None,
    ) -> None:
        try:
            if before is None:
                path.unlink(missing_ok=True)
            else:
                assert restore is not None
                os.replace(restore, path)
        except OSError as exc:
            raise CliFailure(
                "configure_backup_rollback_failed",
                "Publication failed and the prior backup could not be restored.",
                module="backend",
            ) from exc

    @staticmethod
    def _flush_directory(path: Path) -> None:
        if os.name == "nt":
            return
        descriptor = -1
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
        except OSError as exc:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            raise CliFailure(
                "configure_publish_flush_failed",
                "The published directory entry could not be flushed durably.",
                module="backend",
            ) from exc

    @staticmethod
    def _cleanup(paths: list[Path]) -> None:
        failed = False
        for path in reversed(paths):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                failed = True
        if failed:
            raise CliFailure(
                "configure_cleanup_failed",
                "Transaction staging cleanup failed.",
                module="backend",
            )
