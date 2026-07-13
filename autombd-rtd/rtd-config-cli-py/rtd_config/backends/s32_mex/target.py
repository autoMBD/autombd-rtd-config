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
# File:        target.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Verify link-safe .mex targets and capture immutable file snapshots.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from typing import Protocol

from ...errors import CliFailure


@dataclass(frozen=True)
class WindowsFileId:
    volume_serial: int
    file_id: bytes


@dataclass(frozen=True)
class FileIdentity:
    device: int | None
    inode: int | None
    windows_file_id: WindowsFileId | None


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    identity: FileIdentity
    size: int
    mtime_ns: int
    ctime_ns: int
    sha256: str
    content: bytes


@dataclass(frozen=True)
class VerifiedProjectTarget:
    root: Path
    mex: FileSnapshot


@dataclass(frozen=True)
class PathInspection:
    exists: bool
    is_directory: bool
    is_regular: bool
    is_symlink: bool
    is_reparse_point: bool
    is_mount_point: bool


class TargetPlatform(Protocol):
    def list_directory(self, path: Path) -> tuple[Path, ...]: ...
    def inspect(self, path: Path) -> PathInspection: ...
    def canonicalize(self, path: Path) -> Path: ...
    def snapshot_file(self, path: Path) -> FileSnapshot: ...


class _PosixTargetPlatform:
    def list_directory(self, path: Path) -> tuple[Path, ...]:
        return tuple(path.iterdir())

    def inspect(self, path: Path) -> PathInspection:
        try:
            status = os.lstat(path)
        except FileNotFoundError:
            return PathInspection(False, False, False, False, False, False)
        return PathInspection(
            True,
            stat.S_ISDIR(status.st_mode),
            stat.S_ISREG(status.st_mode),
            stat.S_ISLNK(status.st_mode),
            False,
            os.path.ismount(path),
        )

    def canonicalize(self, path: Path) -> Path:
        return path.resolve(strict=True)

    def snapshot_file(self, path: Path) -> FileSnapshot:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("target is not a regular file")
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            after = os.fstat(descriptor)
            evidence_before = (
                before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns,
            )
            evidence_after = (
                after.st_dev, after.st_ino, after.st_size,
                after.st_mtime_ns, after.st_ctime_ns,
            )
            content = b"".join(chunks)
            if evidence_before != evidence_after or len(content) != before.st_size:
                raise RuntimeError("file changed while being read")
            return FileSnapshot(
                path,
                FileIdentity(before.st_dev, before.st_ino, None),
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
                hashlib.sha256(content).hexdigest(),
                content,
            )
        finally:
            os.close(descriptor)


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _GENERIC_READ = 0x80000000
    _FILE_SHARE_READ = 1
    _FILE_SHARE_WRITE = 2
    _FILE_SHARE_DELETE = 4
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_ATTRIBUTE_DIRECTORY = 0x10
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _FILE_BASIC_INFO(ctypes.Structure):
        _fields_ = [
            ("CreationTime", ctypes.c_longlong), ("LastAccessTime", ctypes.c_longlong),
            ("LastWriteTime", ctypes.c_longlong), ("ChangeTime", ctypes.c_longlong),
            ("FileAttributes", wintypes.DWORD),
        ]

    class _FILE_STANDARD_INFO(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_longlong), ("EndOfFile", ctypes.c_longlong),
            ("NumberOfLinks", wintypes.DWORD), ("DeletePending", wintypes.BOOLEAN),
            ("Directory", wintypes.BOOLEAN),
        ]

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]

    class _FILE_ID_128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class _FILE_ID_INFO(ctypes.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong), ("FileId", _FILE_ID_128)]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    _CreateFileW.restype = wintypes.HANDLE
    _GetFileInformationByHandleEx = _kernel32.GetFileInformationByHandleEx
    _GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    _GetFileInformationByHandleEx.restype = wintypes.BOOL
    _ReadFile = _kernel32.ReadFile
    _ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    _ReadFile.restype = wintypes.BOOL
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL


class _WindowsTargetPlatform:
    def list_directory(self, path: Path) -> tuple[Path, ...]:
        return tuple(path.iterdir())

    def _open(self, path: Path, *, read: bool, directory: bool):
        flags = _FILE_FLAG_OPEN_REPARSE_POINT
        if directory:
            flags |= _FILE_FLAG_BACKUP_SEMANTICS
        handle = _CreateFileW(
            str(path), _GENERIC_READ if read else 0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None, _OPEN_EXISTING, flags, None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            if error in (2, 3):
                raise FileNotFoundError(error, os.strerror(error), str(path))
            raise ctypes.WinError(error)
        return handle

    @staticmethod
    def _query(handle, info_class: int, structure_type):
        value = structure_type()
        if not _GetFileInformationByHandleEx(
            handle, info_class, ctypes.byref(value), ctypes.sizeof(value)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    def inspect(self, path: Path) -> PathInspection:
        try:
            status = os.lstat(path)
        except FileNotFoundError:
            return PathInspection(False, False, False, False, False, False)
        # BACKUP_SEMANTICS is required to open a directory symlink itself with
        # OPEN_REPARSE_POINT. It is harmless for ordinary files.
        handle = self._open(path, read=False, directory=True)
        try:
            tag = self._query(handle, 9, _FILE_ATTRIBUTE_TAG_INFO)
        finally:
            _CloseHandle(handle)
        attrs = tag.FileAttributes
        return PathInspection(
            True,
            bool(attrs & _FILE_ATTRIBUTE_DIRECTORY),
            not bool(attrs & _FILE_ATTRIBUTE_DIRECTORY),
            stat.S_ISLNK(status.st_mode),
            bool(attrs & _FILE_ATTRIBUTE_REPARSE_POINT),
            False,
        )

    def canonicalize(self, path: Path) -> Path:
        return path.resolve(strict=True)

    def snapshot_file(self, path: Path) -> FileSnapshot:
        handle = self._open(path, read=True, directory=False)
        try:
            tag = self._query(handle, 9, _FILE_ATTRIBUTE_TAG_INFO)
            if tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("target is a reparse point")
            basic_before = self._query(handle, 0, _FILE_BASIC_INFO)
            standard_before = self._query(handle, 1, _FILE_STANDARD_INFO)
            id_before = self._query(handle, 18, _FILE_ID_INFO)
            if standard_before.Directory:
                raise ValueError("target is not a regular file")
            chunks: list[bytes] = []
            while True:
                buffer = ctypes.create_string_buffer(1024 * 1024)
                count = wintypes.DWORD()
                if not _ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if count.value == 0:
                    break
                chunks.append(buffer.raw[:count.value])
            basic_after = self._query(handle, 0, _FILE_BASIC_INFO)
            standard_after = self._query(handle, 1, _FILE_STANDARD_INFO)
            id_after = self._query(handle, 18, _FILE_ID_INFO)
            file_id = bytes(id_before.FileId.Identifier)
            before = (
                id_before.VolumeSerialNumber, file_id, standard_before.EndOfFile,
                basic_before.LastWriteTime, basic_before.ChangeTime,
            )
            after = (
                id_after.VolumeSerialNumber, bytes(id_after.FileId.Identifier),
                standard_after.EndOfFile, basic_after.LastWriteTime, basic_after.ChangeTime,
            )
            content = b"".join(chunks)
            if before != after or len(content) != standard_before.EndOfFile:
                raise RuntimeError("file changed while being read")
            return FileSnapshot(
                path,
                FileIdentity(None, None, WindowsFileId(id_before.VolumeSerialNumber, file_id)),
                standard_before.EndOfFile,
                basic_before.LastWriteTime * 100,
                basic_before.ChangeTime * 100,
                hashlib.sha256(content).hexdigest(),
                content,
            )
        finally:
            _CloseHandle(handle)


def default_target_platform() -> TargetPlatform:
    return _WindowsTargetPlatform() if os.name == "nt" else _PosixTargetPlatform()


def _path_components(path: Path) -> tuple[Path, ...]:
    current = path.absolute()
    components: list[Path] = []
    while current != current.parent:
        components.append(current)
        current = current.parent
    components.reverse()
    return tuple(components)


def _inspect(path: Path, platform: TargetPlatform) -> PathInspection:
    try:
        return platform.inspect(path)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while inspecting the project path.",
            module="backend", details={"path": str(path)},
        ) from exc
    except OSError as exc:
        raise CliFailure(
            "unsafe_project_path",
            "The project path could not be inspected safely.",
            module="backend", details={"path": str(path)},
        ) from exc


def _canonicalize(path: Path, platform: TargetPlatform) -> Path:
    try:
        return platform.canonicalize(path)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while resolving the project path.",
            module="backend", details={"path": str(path)},
        ) from exc
    except OSError as exc:
        raise CliFailure(
            "unsafe_project_path",
            "The project path could not be resolved safely.",
            module="backend", details={"path": str(path)},
        ) from exc


def _inspect_safe_chain(path: Path, platform: TargetPlatform) -> None:
    for component in _path_components(path):
        evidence = _inspect(component, platform)
        if not evidence.exists:
            raise FileNotFoundError(str(component))
        if evidence.is_symlink or evidence.is_reparse_point or evidence.is_mount_point:
            raise CliFailure(
                "unsafe_project_path",
                "Project paths must not contain links, junctions, mount points, or reparse points.",
                module="backend",
                details={"path": str(component)},
            )


def _identity_available(identity: FileIdentity) -> bool:
    if identity.windows_file_id is not None:
        item = identity.windows_file_id
        return bool(item.volume_serial and len(item.file_id) == 16 and any(item.file_id))
    return identity.device is not None and identity.inode is not None


def _capture_snapshot(path: Path, platform: TargetPlatform) -> FileSnapshot:
    try:
        snapshot = platform.snapshot_file(path)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while reading the project .mex file.",
            module="backend", details={"path": str(path)},
        ) from exc
    except RuntimeError as exc:
        raise CliFailure(
            "project_target_changed",
            "The project .mex file changed while it was being read; reload and retry.",
            module="backend", details={"path": str(path)},
        ) from exc
    except (OSError, ValueError) as exc:
        raise CliFailure(
            "unsafe_project_path",
            "The project .mex file could not be opened as a safe regular file.",
            module="backend", details={"path": str(path)},
        ) from exc
    if not _identity_available(snapshot.identity):
        raise CliFailure(
            "project_identity_unavailable",
            "A reliable platform file identity is unavailable for the project .mex file.",
            module="backend", details={"path": str(path)},
        )
    return snapshot


def verify_project_target(
    project: Path | str,
    platform: TargetPlatform | None = None,
) -> VerifiedProjectTarget:
    adapter = platform or default_target_platform()
    supplied_root = Path(project).absolute()
    root_evidence = _inspect(supplied_root, adapter)
    if not root_evidence.exists:
        raise CliFailure(
            "project_not_found", f"Project directory does not exist: {project}",
            module="backend", details={"project": str(project)},
        )
    if not root_evidence.is_directory:
        raise CliFailure(
            "project_not_directory", f"Project path is not a directory: {project}",
            module="backend", details={"project": str(project)},
        )
    _inspect_safe_chain(supplied_root, adapter)
    canonical_root = _canonicalize(supplied_root, adapter)
    _inspect_safe_chain(canonical_root, adapter)
    try:
        entries = adapter.list_directory(canonical_root)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while enumerating the project directory.",
            module="backend", details={"project": str(canonical_root)},
        ) from exc
    matches = tuple(sorted(
        (entry for entry in entries if entry.suffix.lower() == ".mex"), key=str
    ))
    if not matches:
        raise CliFailure(
            "project_mex_not_found",
            f"No .mex file was found in project directory: {canonical_root}",
            module="backend", details={"project": str(canonical_root), "mex_count": 0},
        )
    if len(matches) != 1:
        raise CliFailure(
            "project_mex_ambiguous",
            f"Expected one .mex file in {canonical_root}, found {len(matches)}.",
            module="backend",
            details={"project": str(canonical_root), "mex_count": len(matches),
                     "matches": [str(path) for path in matches]},
        )
    supplied_mex = matches[0]
    mex_evidence = _inspect(supplied_mex, adapter)
    if mex_evidence.is_symlink or mex_evidence.is_reparse_point or mex_evidence.is_mount_point:
        raise CliFailure(
            "unsafe_project_path",
            "The project .mex file must not be a link, mount point, or reparse point.",
            module="backend", details={"path": str(supplied_mex)},
        )
    if not mex_evidence.is_regular:
        raise CliFailure(
            "project_mex_not_regular", "The project .mex path is not a regular file.",
            module="backend", details={"path": str(supplied_mex)},
        )
    canonical_mex = _canonicalize(supplied_mex, adapter)
    try:
        canonical_mex.relative_to(canonical_root)
    except ValueError as exc:
        raise CliFailure(
            "unsafe_project_path", "The project .mex file resolves outside the project root.",
            module="backend", details={"path": str(canonical_mex), "root": str(canonical_root)},
        ) from exc
    _inspect_safe_chain(canonical_mex, adapter)
    return VerifiedProjectTarget(canonical_root, _capture_snapshot(canonical_mex, adapter))


def revalidate_snapshot(
    snapshot: FileSnapshot,
    platform: TargetPlatform | None = None,
) -> FileSnapshot:
    adapter = platform or default_target_platform()
    _inspect_safe_chain(snapshot.path, adapter)
    current = _capture_snapshot(snapshot.path, adapter)
    if current.identity != snapshot.identity or current.sha256 != snapshot.sha256:
        raise CliFailure(
            "project_target_changed",
            "The project .mex file changed after it was loaded; reload and retry.",
            module="backend", details={"path": str(snapshot.path)},
        )
    return current
