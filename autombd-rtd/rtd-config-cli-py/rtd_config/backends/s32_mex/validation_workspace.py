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
# File:        validation_workspace.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Stage validator inputs in an isolated, auditable workspace.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat

from ...errors import CliFailure
from .metadata import ValidatorInputInventory
from .target import default_target_platform


@dataclass(frozen=True)
class ProjectFileEvidence:
    identity: tuple[int, int]
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str


def _is_reparse(status: os.stat_result) -> bool:
    return bool(
        getattr(status, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _reject_unsafe(path: Path, status: os.stat_result) -> None:
    if stat.S_ISLNK(status.st_mode) or _is_reparse(status):
        raise CliFailure(
            "validation_source_unsafe",
            "Validation source paths must not contain links or reparse points.",
            module="backend", details={"entry": path.name},
        )


def _snapshot_regular(path: Path) -> ProjectFileEvidence:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("not a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        content = b"".join(chunks)
        evidence_before = (
            before.st_dev, before.st_ino, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
        )
        evidence_after = (
            after.st_dev, after.st_ino, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns,
        )
        if evidence_before != evidence_after or len(content) != before.st_size:
            raise RuntimeError("source changed while read")
        return ProjectFileEvidence(
            (before.st_dev, before.st_ino), before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
            hashlib.sha256(content).hexdigest(),
        )
    except (OSError, ValueError, RuntimeError) as exc:
        raise CliFailure(
            "validation_source_unsafe",
            "A validation source file could not be snapshotted safely.",
            module="backend", details={"entry": path.name},
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def snapshot_project_tree(root: Path) -> dict[str, ProjectFileEvidence]:
    root = Path(root)
    try:
        root_status = os.lstat(root)
    except OSError as exc:
        raise CliFailure(
            "validation_source_unsafe",
            "The validation project root is unavailable.",
            module="backend", details={"entry": root.name},
        ) from exc
    _reject_unsafe(root, root_status)
    if not stat.S_ISDIR(root_status.st_mode):
        raise CliFailure(
            "validation_source_unsafe",
            "The validation project root must be a directory.",
            module="backend", details={"entry": root.name},
        )

    result: dict[str, ProjectFileEvidence] = {}
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = tuple(os.scandir(directory))
        except OSError as exc:
            raise CliFailure(
                "validation_source_unsafe",
                "The validation source tree could not be enumerated safely.",
                module="backend", details={"entry": directory.name},
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            try:
                status = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise CliFailure(
                    "validation_source_unsafe",
                    "A validation source entry changed during enumeration.",
                    module="backend", details={"entry": path.name},
                ) from exc
            _reject_unsafe(path, status)
            if stat.S_ISDIR(status.st_mode):
                if path.is_mount():
                    raise CliFailure(
                        "validation_source_unsafe",
                        "Validation source trees must not cross mount points.",
                        module="backend", details={"entry": path.name},
                    )
                stack.append(path)
            elif stat.S_ISREG(status.st_mode):
                relative = path.relative_to(root).as_posix()
                result[relative] = _snapshot_regular(path)
            else:
                raise CliFailure(
                    "validation_source_unsafe",
                    "Validation source trees may contain only directories and regular files.",
                    module="backend", details={"entry": path.name},
                )
    return result


def verify_project_tree(
    root: Path, expected: dict[str, ProjectFileEvidence]
) -> None:
    current = snapshot_project_tree(root)
    if current != expected:
        changed = sorted(set(current) ^ set(expected))
        if not changed:
            changed = sorted(
                name for name in current if current[name] != expected[name]
            )
        raise CliFailure(
            "validation_source_changed",
            "The original project changed during isolated vendor validation.",
            module="backend",
            details={"entries": [Path(name).name for name in changed[:20]]},
        )


def _validate_components(path: Path) -> None:
    absolute = path.absolute()
    parts: list[Path] = []
    current = absolute
    while current != current.parent:
        parts.append(current)
        current = current.parent
    for component in reversed(parts):
        try:
            status = os.lstat(component)
        except FileNotFoundError:
            continue
        _reject_unsafe(component, status)
        if component != absolute and component.is_mount() and component != Path(component.anchor):
            raise CliFailure(
                "validation_workspace_unsafe",
                "Validation workspace paths must not cross mount points.",
                module="backend", details={"entry": component.name},
            )


def _reject_system_temp(path: Path) -> None:
    candidate = path.absolute()
    for key in ("TEMP", "TMP", "TMPDIR"):
        value = os.environ.get(key)
        if not value:
            continue
        system_temp = Path(value).absolute()
        try:
            candidate.relative_to(system_temp)
        except ValueError:
            continue
        raise CliFailure(
            "validation_workspace_unsafe",
            "System temporary directories cannot host validation workspaces.",
            module="backend", details={"entry": candidate.name},
        )


class ControlledValidationWorkspace:
    def __init__(self, base: Path, inventory: ValidatorInputInventory) -> None:
        self.base = Path(base).absolute()
        self.inventory = inventory
        self.created_base = False
        self.root: Path | None = None
        self.project_dir: Path | None = None
        self.mex_file: Path | None = None
        self.export_dir: Path | None = None
        self.data_dir: Path | None = None
        self.log_file: Path | None = None
        self.temp_dir: Path | None = None
        self.cleanup_warnings: list[dict] = []
        self._guards: list = []
        self._guarded_paths: set[Path] = set()
        self._directory_fds: dict[Path, int] = {}
        self._directory_identities: dict[Path, tuple[int, int]] = {}
        self._root_identity: tuple[int, int] | None = None

    def _guard_directory(self, path: Path) -> None:
        path = path.absolute()
        if path in self._guarded_paths:
            return
        platform = default_target_platform()
        guard = platform.protect_root(path)
        try:
            lease = guard.__enter__()
        except (OSError, ValueError) as exc:
            raise CliFailure(
                "validation_workspace_unsafe",
                "A validation workspace directory could not be identity-bound.",
                module="backend", details={"entry": path.name},
            ) from exc
        self._guards.append(guard)
        self._guarded_paths.add(path)
        self._directory_identities[path] = _directory_identity(path)
        root_fd = lease._resources.get("root_fd")
        if root_fd is not None:
            self._directory_fds[path] = root_fd

    def _release_guards(self) -> None:
        failures = False
        for guard in reversed(self._guards):
            try:
                guard.__exit__(None, None, None)
            except (OSError, CliFailure):
                failures = True
        self._guards.clear()
        self._guarded_paths.clear()
        self._directory_fds.clear()
        self._directory_identities.clear()
        if failures:
            self.cleanup_warnings.append({
                "code": "validation_cleanup_failed",
                "message": "Validation workspace identity handles could not be released.",
                "details": {"preserved": [self.base.name]},
            })

    def _mkdir(self, parent: Path, name: str) -> Path:
        target = parent / name
        parent_fd = self._directory_fds.get(parent.absolute())
        try:
            if parent_fd is not None and os.name == "posix":
                os.mkdir(name, 0o700, dir_fd=parent_fd)
            else:
                os.mkdir(target, 0o700)
            self._guard_directory(target)
        except FileExistsError:
            raise
        except (OSError, CliFailure) as exc:
            raise CliFailure(
                "validation_workspace_unsafe",
                "A controlled workspace directory could not be created safely.",
                module="backend", details={"entry": target.name},
            ) from exc
        return target

    def open(self) -> "ControlledValidationWorkspace":
        _reject_system_temp(self.base)
        _validate_components(self.base)
        if not self.base.exists():
            if not self.base.parent.exists():
                raise CliFailure(
                    "validation_workspace_unsafe",
                    "The configured validation workspace parent must already exist.",
                    module="backend", details={"entry": self.base.parent.name},
                )
            self._guard_directory(self.base.parent)
            self._mkdir(self.base.parent, self.base.name)
            self.created_base = True
        else:
            before_identity = _directory_identity(self.base)
            self._guard_directory(self.base)
            if _directory_identity(self.base) != before_identity:
                raise CliFailure(
                    "validation_workspace_unsafe",
                    "The controlled validation root changed while it was opened.",
                    module="backend", details={"entry": self.base.name},
                )
        status = os.lstat(self.base)
        _reject_unsafe(self.base, status)
        if not stat.S_ISDIR(status.st_mode):
            raise CliFailure(
                "validation_workspace_unsafe",
                "The controlled validation root must be a directory.",
                module="backend", details={"entry": self.base.name},
            )
        for _ in range(32):
            name = f"run-{secrets.token_hex(12)}"
            try:
                self.root = self._mkdir(self.base, name)
                break
            except FileExistsError:
                continue
        if self.root is None:
            raise CliFailure(
                "validation_workspace_create_failed",
                "A unique controlled validation workspace could not be created.",
                module="backend",
            )
        self._root_identity = _directory_identity(self.root)
        self.project_dir = self.root / "project"
        self.export_dir = self.root / "export"
        self.data_dir = self.root / "data"
        self.temp_dir = self.root / "temp"
        logs = self.root / "logs"
        for name in ("project", "export", "data", "temp", "logs"):
            self._mkdir(self.root, name)
        self.log_file = logs / "validation.log"
        created_directories = {PurePosixPath(".")}
        for item in self.inventory.files:
            relative = PurePosixPath(item.relative)
            parent = relative.parent
            pending: list[PurePosixPath] = []
            while parent not in created_directories and parent != PurePosixPath("."):
                pending.append(parent)
                parent = parent.parent
            for directory_relative in reversed(pending):
                directory = self.project_dir.joinpath(*directory_relative.parts)
                self._mkdir(directory.parent, directory.name)
                created_directories.add(directory_relative)
            target = self.project_dir.joinpath(*relative.parts)
            parent_fd = self._directory_fds.get(target.parent.absolute())
            self._materialize_snapshot(
                item.snapshot, target,
                dir_fd=parent_fd if os.name == "posix" else None,
            )
            self.verify_identity()
            if item.relative == self.inventory.mex_relative:
                self.mex_file = target
        if self.mex_file is None:
            raise CliFailure(
                "validation_inventory_incomplete",
                "The validator inventory did not materialize its selected .mex.",
                module="backend",
            )
        return self

    def verify_identity(self) -> None:
        for path, expected in self._directory_identities.items():
            if _directory_identity(path) != expected:
                raise CliFailure(
                    "validation_workspace_unsafe",
                    "A controlled workspace directory changed during staging.",
                    module="backend", details={"entry": path.name},
                )

    @staticmethod
    def _materialize_snapshot(snapshot, target: Path, *, dir_fd: int | None = None) -> None:
        target_fd = -1
        write_flags = (
            os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            target_fd = os.open(
                target.name if dir_fd is not None else target,
                write_flags, 0o600, dir_fd=dir_fd,
            )
            view = memoryview(snapshot.content)
            while view:
                written = os.write(target_fd, view)
                if written <= 0:
                    raise OSError("short validation staging write")
                view = view[written:]
            if os.name != "nt" and snapshot.mode is not None:
                os.fchmod(target_fd, snapshot.mode)
            os.fsync(target_fd)
            materialized = os.fstat(target_fd)
            if materialized.st_size != snapshot.size:
                raise OSError("validation staging size mismatch")
        except OSError as exc:
            raise CliFailure(
                "validation_staging_failed",
                "The validator input could not be copied safely.",
                module="backend", details={"entry": target.name},
            ) from exc
        finally:
            if target_fd >= 0:
                os.close(target_fd)
        if os.name == "nt" and snapshot.mode is not None:
            os.chmod(target, snapshot.mode)

    def environment(self) -> dict[str, str]:
        allowed = (
            "SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT",
            "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOME", "LANG",
        )
        result = {key: os.environ[key] for key in allowed if key in os.environ}
        assert self.temp_dir is not None
        result["TEMP"] = str(self.temp_dir)
        result["TMP"] = str(self.temp_dir)
        return result

    def close(self) -> list[dict]:
        expected_root = self._root_identity
        self._release_guards()
        safe_to_remove = False
        if self.root is not None:
            try:
                safe_to_remove = _directory_identity(self.root) == expected_root
            except (OSError, CliFailure):
                safe_to_remove = False
        if self.root is not None and self.root.exists() and safe_to_remove:
            try:
                shutil.rmtree(self.root)
            except OSError:
                self.cleanup_warnings.append({
                    "code": "validation_cleanup_failed",
                    "message": "The controlled validation workspace was preserved for audit.",
                    "details": {"preserved": [self.root.name]},
                })
        elif self.root is not None and self.root.exists() and not safe_to_remove:
            self.cleanup_warnings.append({
                "code": "validation_cleanup_failed",
                "message": "The controlled workspace identity changed; cleanup was blocked.",
                "details": {"preserved": [self.root.name]},
            })
        if self.created_base and self.base.exists() and not self.cleanup_warnings:
            try:
                self.base.rmdir()
            except OSError:
                self.cleanup_warnings.append({
                    "code": "validation_cleanup_failed",
                    "message": "The empty validation root could not be removed.",
                    "details": {"preserved": [self.base.name]},
                })
        return self.cleanup_warnings


def _directory_identity(path: Path) -> tuple[int, int]:
    try:
        status = os.lstat(path)
    except OSError as exc:
        raise CliFailure(
            "validation_workspace_unsafe",
            "A controlled workspace directory became unavailable.",
            module="backend", details={"entry": path.name},
        ) from exc
    _reject_unsafe(path, status)
    if not stat.S_ISDIR(status.st_mode):
        raise CliFailure(
            "validation_workspace_unsafe",
            "A controlled workspace entry is no longer a directory.",
            module="backend", details={"entry": path.name},
        )
    return status.st_dev, status.st_ino
