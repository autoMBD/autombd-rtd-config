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

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import stat
import sys
from collections.abc import Callable
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
class TargetLease:
    _release: Callable[[], None] = field(repr=False, compare=False)
    _retained: bool = field(default=False, init=False, repr=False, compare=False)
    _closed: bool = field(default=False, init=False, repr=False, compare=False)

    def retain(self) -> None:
        object.__setattr__(self, "_retained", True)

    @property
    def retained(self) -> bool:
        return self._retained

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            self._release()
            object.__setattr__(self, "_closed", True)

    def __del__(self) -> None:
        self.close()


@dataclass(frozen=True)
class VerifiedProjectTarget:
    root: Path
    mex: FileSnapshot
    lease: TargetLease = field(repr=False, compare=False)

    def close(self) -> None:
        self.lease.close()

    def __enter__(self) -> "VerifiedProjectTarget":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()


@dataclass(frozen=True)
class PathInspection:
    exists: bool
    is_directory: bool
    is_regular: bool
    is_symlink: bool
    is_reparse_point: bool
    is_mount_point: bool


class TargetPlatform(Protocol):
    def protect_root(self, path: Path): ...
    def list_directory(self, path: Path) -> tuple[Path, ...]: ...
    def inspect(self, path: Path) -> PathInspection: ...
    def canonicalize(self, path: Path) -> Path: ...
    def snapshot_file(self, path: Path) -> FileSnapshot: ...


class _PosixTargetPlatform:
    def __init__(
        self,
        no_follow_flag: int | None = None,
        mount_detector: Callable[[Path], bool] | None = None,
    ) -> None:
        self._no_follow = getattr(os, "O_NOFOLLOW", 0) if no_follow_flag is None else no_follow_flag
        self._mount_detector = mount_detector or self._default_mount_detector()
        self._root_fd: int | None = None
        self._root_path: Path | None = None
        self._protected_fds: list[int] | None = None

    @staticmethod
    def _default_mount_detector() -> Callable[[Path], bool]:
        if not sys.platform.startswith("linux"):
            def unsupported(_path: Path) -> bool:
                raise CliFailure(
                    "project_identity_unavailable",
                    "Mount-point safety cannot be proven on this POSIX platform.",
                    module="backend",
                )
            return unsupported
        def detect(path: Path) -> bool:
            try:
                lines = Path("/proc/self/mountinfo").read_text(
                    encoding="utf-8"
                ).splitlines()
            except OSError as exc:
                raise CliFailure(
                    "project_identity_unavailable",
                    "Linux mount information is unavailable; project safety cannot be proven.",
                    module="backend",
                ) from exc
            mounts = {
                Path(fields[4].replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\"))
                for line in lines
                if len(fields := line.split()) > 5
            }
            return path in mounts
        return detect

    @contextmanager
    def protect_root(self, path: Path):
        if not self._no_follow:
            raise CliFailure(
                "project_identity_unavailable",
                "This POSIX platform cannot open project paths without following links.",
                module="backend",
            )
        absolute = path.absolute()
        for component in _path_components(absolute):
            if self._mount_detector(component):
                raise CliFailure(
                    "unsafe_project_path",
                    "Project paths must not cross mount points or bind mounts.",
                    module="backend", details={"path": str(component)},
                )
        flags = os.O_RDONLY | os.O_DIRECTORY | self._no_follow
        fd = os.open(absolute.anchor, flags)
        fds = [fd]
        lease = TargetLease(lambda: [os.close(item) for item in reversed(fds)])
        try:
            for name in absolute.parts[1:]:
                child = os.open(name, flags, dir_fd=fd)
                fds.append(child)
                fd = child
            for component in _path_components(absolute):
                if self._mount_detector(component):
                    raise CliFailure(
                        "unsafe_project_path",
                        "The project mount topology changed while its fd chain was opened.",
                        module="backend", details={"path": str(component)},
                    )
            self._root_fd = fd
            self._root_path = absolute
            self._protected_fds = fds
            yield lease
        finally:
            self._root_fd = None
            self._root_path = None
            self._protected_fds = None
            if not lease.retained:
                lease.close()

    def list_directory(self, path: Path) -> tuple[Path, ...]:
        if self._root_fd is not None and path == self._root_path:
            return tuple(path / name for name in os.listdir(self._root_fd))
        return tuple(path.iterdir())

    def inspect(self, path: Path) -> PathInspection:
        try:
            if self._root_fd is not None and path.parent == self._root_path:
                status = os.stat(path.name, dir_fd=self._root_fd, follow_symlinks=False)
            elif self._root_fd is not None and path == self._root_path:
                status = os.fstat(self._root_fd)
            else:
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
        if not self._no_follow:
            raise CliFailure(
                "project_identity_unavailable",
                "This POSIX platform cannot open project files without following links.",
                module="backend",
            )
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | self._no_follow
        if self._root_fd is not None and path.parent == self._root_path:
            descriptor = os.open(path.name, flags, dir_fd=self._root_fd)
        else:
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
            if self._protected_fds is not None:
                self._protected_fds.append(descriptor)
            else:
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
    def __init__(self) -> None:
        self._protected_handles: list = []

    @contextmanager
    def protect_root(self, path: Path):
        handles: list = []
        lease = TargetLease(lambda: [_CloseHandle(item) for item in reversed(handles)])
        try:
            for component in _path_components(path):
                handle = self._open(component, read=True, directory=True, share_delete=False)
                handles.append(handle)
                tag = self._query(handle, 9, _FILE_ATTRIBUTE_TAG_INFO)
                if tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                    raise CliFailure(
                        "unsafe_project_path",
                        "Project paths must not contain reparse points.",
                        module="backend", details={"path": str(component)},
                    )
            self._protected_handles = handles
            yield lease
        finally:
            self._protected_handles = []
            if not lease.retained:
                lease.close()

    def list_directory(self, path: Path) -> tuple[Path, ...]:
        return tuple(path.iterdir())

    def _open(
        self,
        path: Path,
        *,
        read: bool,
        directory: bool,
        share_delete: bool = True,
        share_write: bool = True,
    ):
        flags = _FILE_FLAG_OPEN_REPARSE_POINT
        if directory:
            flags |= _FILE_FLAG_BACKUP_SEMANTICS
        handle = _CreateFileW(
            str(path), _GENERIC_READ if read else 0,
            _FILE_SHARE_READ | (_FILE_SHARE_WRITE if share_write else 0)
            | (_FILE_SHARE_DELETE if share_delete else 0),
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
        handle = self._open(
            path, read=True, directory=False, share_delete=False, share_write=False
        )
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
            if self._protected_handles:
                self._protected_handles.append(handle)
            else:
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


def _protected_root(platform: TargetPlatform, path: Path):
    protector = getattr(platform, "protect_root", None)
    if not callable(protector):
        raise CliFailure(
            "project_identity_unavailable",
            "The target platform cannot provide a protected project-root lease.",
            module="backend", details={"path": str(path)},
        )
    return protector(path)


def _direct_mex_entries(root: Path, platform: TargetPlatform) -> tuple[Path, ...]:
    try:
        entries = platform.list_directory(root)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while enumerating the project directory.",
            module="backend", details={"project": str(root)},
        ) from exc
    return tuple(sorted(
        (entry for entry in entries if entry.suffix.lower() == ".mex"), key=str
    ))


def verify_project_target(
    project: Path | str,
    platform: TargetPlatform | None = None,
) -> VerifiedProjectTarget:
    adapter = platform or default_target_platform()
    supplied_root = Path(project).absolute()
    try:
        protection = _protected_root(adapter, supplied_root)
        with protection as lease:
            if not isinstance(lease, TargetLease) or lease.closed:
                raise CliFailure(
                    "project_identity_unavailable",
                    "The target platform returned an invalid project-root lease.",
                    module="backend", details={"path": str(supplied_root)},
                )
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
            matches = _direct_mex_entries(supplied_root, adapter)
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
                    "unsafe_project_path",
                    "The project .mex file resolves outside the project root.",
                    module="backend",
                    details={"path": str(canonical_mex), "root": str(canonical_root)},
                ) from exc
            snapshot = _capture_snapshot(supplied_mex, adapter)
            snapshot = FileSnapshot(canonical_mex, snapshot.identity, snapshot.size,
                                    snapshot.mtime_ns, snapshot.ctime_ns,
                                    snapshot.sha256, snapshot.content)
            after_matches = _direct_mex_entries(supplied_root, adapter)
            if tuple(path.name for path in after_matches) != (supplied_mex.name,):
                raise CliFailure(
                    "project_target_changed",
                    "The project .mex set changed while the target was being verified.",
                    module="backend", details={"project": str(canonical_root)},
                )
            after = _capture_snapshot(after_matches[0], adapter)
            if after.identity != snapshot.identity or after.sha256 != snapshot.sha256:
                raise CliFailure(
                    "project_target_changed",
                    "The project .mex file changed while the target was being verified.",
                    module="backend", details={"path": str(canonical_mex)},
                )
            if _canonicalize(supplied_root, adapter) != canonical_root:
                raise CliFailure(
                    "project_target_changed",
                    "The project path changed while the target was being verified.",
                    module="backend", details={"project": str(canonical_root)},
                )
            lease.retain()
            return VerifiedProjectTarget(canonical_root, snapshot, lease)
    except FileNotFoundError as exc:
        raise CliFailure(
            "project_not_found", f"Project directory does not exist: {project}",
            module="backend", details={"project": str(project)},
        ) from exc


def revalidate_snapshot(
    snapshot: VerifiedProjectTarget,
    platform: TargetPlatform | None = None,
) -> FileSnapshot:
    if not isinstance(snapshot, VerifiedProjectTarget):
        raise TypeError("revalidate_snapshot requires VerifiedProjectTarget")
    current_target = verify_project_target(snapshot.root, platform=platform)
    try:
        if current_target.mex.identity != snapshot.mex.identity or current_target.mex.sha256 != snapshot.mex.sha256:
            raise CliFailure(
                "project_target_changed",
                "The verified project target changed after it was loaded; reload and retry.",
                module="backend", details={"path": str(snapshot.mex.path)},
            )
        return current_target.mex
    finally:
        current_target.close()
