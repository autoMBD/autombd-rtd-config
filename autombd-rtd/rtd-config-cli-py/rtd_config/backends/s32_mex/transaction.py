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

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import secrets
import stat
import sys
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
    AtomicPublishFailure,
    AtomicPublishState,
    FileSnapshot,
    PublishExpectation,
    atomic_install_absent,
    atomic_publish_candidate,
    discard_owned_path,
    finalize_atomic_publish,
    prepare_atomic_finalize,
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
    published: bool = False
    cleanup_warnings: list[dict] = field(default_factory=list)


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
        cleanup: list[FileSnapshot] = []
        target_publication: AtomicPublishResult | None = None
        backup_publication: AtomicPublishResult | None = None
        committed = False
        cleanup_warnings: list[dict] = []
        try:
            self.metadata.require_identity()
            revalidate_snapshot(self.target, platform=self.platform)
            revalidate_project_metadata(self.target, self.metadata)

            apply_result = apply_fn(
                self.project.document, intent, bundle=self.bundle
            )
            if apply_result.blocked:
                return self._result(
                    "blocked", apply_result, None, None, self.original.content,
                    cleanup_warnings=cleanup_warnings,
                )

            candidate = self.project.document.render()
            no_op = candidate == self.original.content

            staging = self._stage_bytes(candidate, "candidate", self.original.mode)
            candidate_snapshot = self._snapshot_staging(staging, candidate)
            cleanup.append(candidate_snapshot)
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
                    "blocked", apply_result, static_result, None, self.original.content,
                    cleanup_warnings=cleanup_warnings,
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
                        cleanup_warnings=cleanup_warnings,
                    )

            revalidate_snapshot(self.target, platform=self.platform)
            revalidate_project_metadata(self.target, self.metadata)
            if no_op:
                return self._result(
                    "passed", apply_result, static_result, vendor_result,
                    self.original.content, changed_modules=[], no_op=True,
                    cleanup_warnings=cleanup_warnings,
                )

            backup_path = self.original.path.with_name(self.original.path.name + ".bak")
            backup_before = self._backup_before(backup_path) if self.backup else None
            if self.backup:
                backup_mode = (
                    backup_before.mode if backup_before is not None else self.original.mode
                )
                backup_staging = self._stage_bytes(
                    self.original.content, "backup", backup_mode
                )
                cleanup.append(
                    self._snapshot_staging(backup_staging, self.original.content)
                )

            expectation = self.release_for_publish_fn(self.target)
            revalidate_publish_expectation(expectation, platform=self.platform)
            revalidate_project_metadata_after_release(self.project.root, self.metadata)
            try:
                if self.backup:
                    self._revalidate_backup(backup_path, backup_before)
                    assert backup_staging is not None
                    backup_sha = hashlib.sha256(self.original.content).hexdigest()
                    if backup_before is None:
                        backup_publication = atomic_install_absent(
                            backup_path, backup_staging, backup_sha,
                            platform=self.platform,
                        )
                    else:
                        backup_publication = atomic_publish_candidate(
                            PublishExpectation(
                                backup_path, backup_before.identity, backup_before.sha256
                            ),
                            backup_staging,
                            backup_sha,
                            platform=self.platform,
                        )
                target_publication = self.atomic_publish_fn(
                    expectation,
                    staging,
                    hashlib.sha256(candidate).hexdigest(),
                    platform=self.platform,
                )
            except CliFailure as primary:
                if isinstance(primary, AtomicPublishFailure):
                    adopted = self._adopt_atomic_failure(primary, cleanup)
                    if adopted is not None:
                        if primary.state.destination == backup_path:
                            backup_publication = adopted
                        else:
                            target_publication = adopted
                failures = self._rollback_publications(
                    target_publication, backup_publication, backup_path
                )
                raise self._merge_failures(primary, failures)
            except Exception as exc:
                failures = self._rollback_publications(
                    target_publication, backup_publication, backup_path
                )
                primary = CliFailure(
                    "configure_publish_failed",
                    "The atomic publication adapter failed unexpectedly.",
                    module="backend",
                )
                raise self._merge_failures(primary, failures) from exc
            try:
                self._flush_directory(self.original.path.parent)
                final = self.platform.snapshot_file(self.original.path)
                if not self._same_snapshot(final, target_publication.published):
                    raise CliFailure(
                        "project_target_changed",
                        "The published target changed before final commit confirmation.",
                        module="backend",
                    )
                revalidate_project_metadata_after_release(
                    self.project.root, self.metadata
                )
                prepare_atomic_finalize(target_publication, platform=self.platform)
                if backup_publication is not None:
                    prepare_atomic_finalize(
                        backup_publication, platform=self.platform
                    )
            except BaseException as primary:
                failures = self._rollback_publications(
                    target_publication, backup_publication, backup_path
                )
                if isinstance(primary, CliFailure):
                    raise self._merge_failures(primary, failures)
                if failures and hasattr(primary, "add_note"):
                    primary.add_note(self._failure_note(failures))
                raise

            # Everything which can invalidate rollback evidence has completed.
            # From here onward the candidate is the committed project state.
            committed = True
            for publication in (target_publication, backup_publication):
                if publication is None:
                    continue
                try:
                    residual = finalize_atomic_publish(
                        publication, platform=self.platform
                    )
                    if residual is not None:
                        cleanup_warnings.append(
                            self._cleanup_residual_warning(residual)
                        )
                except CliFailure as exc:
                    cleanup_warnings.append(self._warning(exc))
            return self._result(
                "passed", apply_result, static_result, vendor_result,
                final.content,
                published=True,
                cleanup_warnings=cleanup_warnings,
            )
        finally:
            primary = sys.exc_info()[1]
            cleanup_failures: list[CliFailure] = []
            if not self.target.lease.closed:
                try:
                    self.target.close()
                except Exception as exc:
                    cleanup_failure = CliFailure(
                        "configure_cleanup_failed",
                        "Transaction resources could not be released cleanly.",
                        module="backend",
                    )
                    cleanup_failure.__cause__ = exc
                    cleanup_failures.append(cleanup_failure)
            try:
                residuals = self._cleanup(cleanup)
                for residual in residuals:
                    cleanup_warnings.append(
                        self._cleanup_residual_warning(residual)
                    )
            except CliFailure as failure:
                cleanup_failures.append(failure)
            if cleanup_failures:
                cleanup_failure = self._merge_failures(
                    cleanup_failures[0], cleanup_failures[1:]
                )
                if committed:
                    cleanup_warnings.append(self._warning(cleanup_failure))
                elif isinstance(primary, CliFailure):
                    raise self._merge_failures(primary, [cleanup_failure]) from primary
                elif primary is not None:
                    if hasattr(primary, "add_note"):
                        primary.add_note(self._failure_note([cleanup_failure]))
                else:
                    raise cleanup_failure

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
        published: bool = False,
        cleanup_warnings: list[dict] | None = None,
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
            published=published,
            cleanup_warnings=(
                cleanup_warnings if cleanup_warnings is not None else []
            ),
        )

    def _stage_bytes(
        self, content: bytes, purpose: str, mode: int | None = None
    ) -> Path:
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
                if os.name != "nt" and mode is not None:
                    os.fchmod(descriptor, mode)
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
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                raise CliFailure(
                    "configure_staging_failed",
                    "A transaction staging file could not be written durably.",
                    module="backend",
                    details={"purpose": purpose, "preserved": [path.name]},
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

    def _rollback_publications(
        self,
        target_publication: AtomicPublishResult | None,
        backup_publication: AtomicPublishResult | None,
        backup_path: Path,
    ) -> list[CliFailure]:
        failures: list[CliFailure] = []
        if target_publication is not None:
            try:
                residual = rollback_atomic_publish(
                    target_publication, self.original.path, platform=self.platform
                )
                if residual is not None:
                    failures.append(self._residual_failure(residual))
            except CliFailure as exc:
                failures.append(exc)
        if backup_publication is not None:
            try:
                residual = rollback_atomic_publish(
                    backup_publication, backup_path, platform=self.platform
                )
                if residual is not None:
                    failures.append(self._residual_failure(residual))
            except CliFailure as exc:
                failures.append(exc)
        return failures

    def _adopt_atomic_failure(
        self,
        failure: AtomicPublishFailure,
        known_snapshots: list[FileSnapshot],
    ) -> AtomicPublishResult | None:
        """Recover publication ownership immediately from a typed syscall failure."""
        state = failure.state
        by_identity = {
            (item.identity, item.sha256): item for item in known_snapshots
        }
        try:
            published = state.published or self.platform.snapshot_file(
                state.destination
            )
        except (OSError, ValueError, RuntimeError, KeyError):
            return None
        owned_candidate = by_identity.get((published.identity, published.sha256))
        if owned_candidate is None:
            return None
        state.published = published
        if state.displaced_path is None:
            state.phase = "adopted_install"
            return AtomicPublishResult(published, None, None, state)
        try:
            displaced = state.displaced or self.platform.snapshot_file(
                state.displaced_path
            )
        except (OSError, ValueError, RuntimeError, KeyError):
            return None
        state.displaced = displaced
        state.phase = "adopted_exchange"
        return AtomicPublishResult(
            published, displaced, state.displaced_path, state
        )

    @classmethod
    def _merge_failures(
        cls, primary: CliFailure, secondary: list[CliFailure]
    ) -> CliFailure:
        if not secondary:
            return primary
        details = dict(primary.details or {})
        preserved = set(details.get("preserved", []))
        cleanup: list[dict] = []
        for failure in secondary:
            item = cls._warning(failure)
            cleanup.append(item)
            preserved.update(item.get("details", {}).get("preserved", []))
        if preserved:
            details["preserved"] = sorted(preserved)
        details["recovery_failures"] = cleanup
        return CliFailure(
            primary.code,
            primary.message,
            module=primary.module,
            status=primary.status,
            exit_code=primary.exit_code,
            details=details,
        )

    @staticmethod
    def _warning(failure: CliFailure) -> dict:
        return {
            "code": failure.code,
            "message": failure.message,
            "details": dict(failure.details or {}),
        }

    @staticmethod
    def _cleanup_residual_warning(path: Path) -> dict:
        return {
            "code": "configure_cleanup_residual",
            "message": "Verified rollback evidence was retained for audit cleanup.",
            "details": {"preserved": [path.name]},
        }

    @staticmethod
    def _residual_failure(path: Path) -> CliFailure:
        return CliFailure(
            "configure_cleanup_residual",
            "Verified recovery evidence was retained for audit cleanup.",
            module="backend",
            details={"preserved": [path.name]},
        )

    @classmethod
    def _failure_note(cls, failures: list[CliFailure]) -> str:
        codes = ", ".join(item.code for item in failures)
        return f"Additional transaction recovery failures: {codes}"

    @staticmethod
    def _same_snapshot(actual: FileSnapshot, expected: FileSnapshot) -> bool:
        return actual.identity == expected.identity and actual.sha256 == expected.sha256

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

    def _cleanup(self, snapshots: list[FileSnapshot]) -> list[Path]:
        failures: list[CliFailure] = []
        residuals: list[Path] = []
        for snapshot in reversed(snapshots):
            try:
                residual = discard_owned_path(snapshot.path, snapshot, self.platform)
                if residual is not None:
                    residuals.append(residual)
            except CliFailure as exc:
                failures.append(exc)
        if failures:
            raise self._merge_failures(failures[0], failures[1:])
        return residuals
