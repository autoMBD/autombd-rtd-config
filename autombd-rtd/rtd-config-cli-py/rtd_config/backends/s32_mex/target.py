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
import re
import secrets
import threading
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
    mode: int | None = None


@dataclass(frozen=True)
class TargetLease:
    _release: Callable[[], None] = field(repr=False, compare=False)
    _retained: bool = field(default=False, init=False, repr=False, compare=False)
    _closed: bool = field(default=False, init=False, repr=False, compare=False)
    _closing: bool = field(default=False, init=False, repr=False, compare=False)
    _active_readers: int = field(default=0, init=False, repr=False, compare=False)
    _condition: threading.Condition = field(default_factory=threading.Condition, init=False, repr=False, compare=False)
    _resources: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    def retain(self) -> None:
        object.__setattr__(self, "_retained", True)

    @property
    def retained(self) -> bool:
        return self._retained

    @property
    def closed(self) -> bool:
        return self._closed

    @contextmanager
    def borrow(self):
        with self._condition:
            if self._closing or self._closed:
                raise CliFailure(
                    "project_target_closed",
                    "The verified project lease is closing or closed.",
                    module="backend",
                )
            object.__setattr__(self, "_active_readers", self._active_readers + 1)
        try:
            yield
        finally:
            with self._condition:
                object.__setattr__(self, "_active_readers", self._active_readers - 1)
                self._condition.notify_all()

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            if self._closing:
                while not self._closed:
                    self._condition.wait()
                return
            object.__setattr__(self, "_closing", True)
            while self._active_readers:
                self._condition.wait()
        try:
            self._release()
        finally:
            with self._condition:
                object.__setattr__(self, "_closed", True)
                self._condition.notify_all()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


@dataclass(frozen=True)
class PublishExpectation:
    path: Path
    identity: FileIdentity
    sha256: str


@dataclass(frozen=True)
class AtomicPublishResult:
    published: FileSnapshot
    displaced: FileSnapshot | None
    displaced_path: Path | None
    state: "AtomicPublishState | None" = None


@dataclass
class AtomicPublishState:
    destination: Path
    candidate_path: Path
    phase: str = "prepared"
    published: FileSnapshot | None = None
    displaced_path: Path | None = None
    displaced: FileSnapshot | None = None
    rescue_paths: list[Path] = field(default_factory=list)

    @property
    def preserved_basenames(self) -> list[str]:
        values = [
            self.destination,
            self.candidate_path,
            self.displaced_path,
            *self.rescue_paths,
        ]
        return sorted({path.name for path in values if path is not None})


class AtomicPublishFailure(CliFailure):
    """Typed atomic failure carrying ownership even after a syscall succeeded."""

    __slots__ = ("state",)

    def __init__(self, code: str, message: str, state: AtomicPublishState) -> None:
        super().__init__(
            code, message, module="backend",
            details={"preserved": state.preserved_basenames},
        )
        self.state = state


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
        nonblock_flag: int | None = None,
        mount_detector: Callable[[Path], bool] | None = None,
    ) -> None:
        self._no_follow = getattr(os, "O_NOFOLLOW", 0) if no_follow_flag is None else no_follow_flag
        self._nonblock = getattr(os, "O_NONBLOCK", 0) if nonblock_flag is None else nonblock_flag
        self._mount_detector = mount_detector or self._default_mount_detector()
        self._state = threading.local()

    @property
    def _root_fd(self): return getattr(self._state, "root_fd", None)
    @_root_fd.setter
    def _root_fd(self, value): self._state.root_fd = value
    @property
    def _root_path(self): return getattr(self._state, "root_path", None)
    @_root_path.setter
    def _root_path(self, value): self._state.root_path = value
    @property
    def _protected_fds(self): return getattr(self._state, "protected_fds", None)
    @_protected_fds.setter
    def _protected_fds(self, value): self._state.protected_fds = value

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
                Path(re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4]))
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
            lease._resources["root_fd"] = fd
            lease._resources["platform"] = self
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
        if not self._nonblock:
            raise CliFailure(
                "project_identity_unavailable",
                "This POSIX platform cannot open project files without blocking.",
                module="backend",
            )
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | self._no_follow | self._nonblock
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
                stat.S_IMODE(before.st_mode),
            )
        finally:
            if self._protected_fds is not None:
                self._protected_fds.append(descriptor)
            else:
                os.close(descriptor)

    @staticmethod
    def exchange_capture(replacement: Path, target: Path, _capture: Path) -> Path:
        """Atomically exchange two names, leaving the displaced target at replacement."""
        import ctypes

        library = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(library, "renameat2", None)
        if renameat2 is None:
            raise NotImplementedError("renameat2 is unavailable")
        renameat2.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        if renameat2(
            -100, os.fsencode(replacement), -100, os.fsencode(target), 0x2
        ) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        return replacement

    @classmethod
    def restore_capture(cls, target: Path, capture: Path, _rescue: Path) -> Path:
        return cls.exchange_capture(capture, target, _rescue)

    @staticmethod
    def install_absent(replacement: Path, target: Path) -> None:
        import ctypes

        library = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(library, "renameat2", None)
        if renameat2 is None:
            raise NotImplementedError("renameat2 is unavailable")
        renameat2.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        if renameat2(-100, os.fsencode(replacement), -100, os.fsencode(target), 0x1) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))

    @classmethod
    def capture_remove(cls, source: Path, capture: Path) -> None:
        cls.install_absent(source, capture)


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
    _FILE_ATTRIBUTE_READONLY = 0x1
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

    class _FILE_DISPOSITION_INFO(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

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
    _ReplaceFileW = _kernel32.ReplaceFileW
    _ReplaceFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID,
    ]
    _ReplaceFileW.restype = wintypes.BOOL
    _MoveFileExW = _kernel32.MoveFileExW
    _MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    _MoveFileExW.restype = wintypes.BOOL
    _SetFileInformationByHandle = _kernel32.SetFileInformationByHandle
    _SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    _SetFileInformationByHandle.restype = wintypes.BOOL


class _WindowsTargetPlatform:
    def __init__(self) -> None:
        self._state = threading.local()

    @property
    def _protected_handles(self): return getattr(self._state, "protected_handles", [])
    @_protected_handles.setter
    def _protected_handles(self, value): self._state.protected_handles = value

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
            lease._resources["root_handle"] = handles[-1]
            lease._resources["platform"] = self
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
                0o444 if basic_before.FileAttributes & _FILE_ATTRIBUTE_READONLY else 0o666,
            )
        finally:
            if self._protected_handles:
                self._protected_handles.append(handle)
            else:
                _CloseHandle(handle)

    @staticmethod
    def exchange_capture(replacement: Path, target: Path, capture: Path) -> Path:
        if not _ReplaceFileW(str(target), str(replacement), str(capture), 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        return capture

    @staticmethod
    def restore_capture(target: Path, capture: Path, rescue: Path) -> Path:
        if not _ReplaceFileW(str(target), str(capture), str(rescue), 0, None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        return rescue

    @staticmethod
    def install_absent(replacement: Path, target: Path) -> None:
        if not _MoveFileExW(str(replacement), str(target), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    @classmethod
    def capture_remove(cls, source: Path, capture: Path) -> None:
        cls.install_absent(source, capture)

    def secure_delete_owned(self, path: Path, expected: FileSnapshot) -> None:
        handle = _CreateFileW(
            str(path), _GENERIC_READ | 0x00010000,
            _FILE_SHARE_READ, None, _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT, None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            tag = self._query(handle, 9, _FILE_ATTRIBUTE_TAG_INFO)
            standard = self._query(handle, 1, _FILE_STANDARD_INFO)
            identity = self._query(handle, 18, _FILE_ID_INFO)
            if tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT or standard.Directory:
                raise OSError("cleanup target is not a regular file")
            content = b""
            while True:
                buffer = ctypes.create_string_buffer(1024 * 1024)
                count = wintypes.DWORD()
                if not _ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not count.value:
                    break
                content += buffer.raw[:count.value]
            actual_identity = FileIdentity(
                None, None,
                WindowsFileId(
                    identity.VolumeSerialNumber, bytes(identity.FileId.Identifier)
                ),
            )
            if (
                actual_identity != expected.identity
                or hashlib.sha256(content).hexdigest() != expected.sha256
            ):
                raise OSError("cleanup target identity changed")
            disposition = _FILE_DISPOSITION_INFO(True)
            if not _SetFileInformationByHandle(
                handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
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
            module="backend", details={},
        ) from exc
    except OSError as exc:
        if exc.errno == getattr(os, "ENOTDIR", 20):
            raise CliFailure(
                "project_not_directory", "The project path is not a directory.",
                module="backend", details={},
            ) from exc
        raise CliFailure(
            "unsafe_project_path",
            "The project path could not be inspected safely.",
            module="backend", details={},
        ) from exc


def _canonicalize(path: Path, platform: TargetPlatform) -> Path:
    try:
        return platform.canonicalize(path)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while resolving the project path.",
            module="backend", details={},
        ) from exc
    except OSError as exc:
        raise CliFailure(
            "unsafe_project_path",
            "The project path could not be resolved safely.",
            module="backend", details={},
        ) from exc


def _inspect_safe_chain(path: Path, platform: TargetPlatform) -> PathInspection:
    final: PathInspection | None = None
    for component in _path_components(path):
        evidence = _inspect(component, platform)
        final = evidence
        if not evidence.exists:
            raise FileNotFoundError(str(component))
        if evidence.is_symlink or evidence.is_reparse_point or evidence.is_mount_point:
            raise CliFailure(
                "unsafe_project_path",
                "Project paths must not contain links, junctions, mount points, or reparse points.",
                module="backend",
                details={},
            )
    if final is None:  # pragma: no cover - absolute roots have a component
        raise FileNotFoundError(str(path))
    return final


def _raise_protected_root_enotdir(
    path: Path,
    platform: TargetPlatform,
    cause: OSError,
) -> None:
    """Classify ENOTDIR without confusing a no-follow link rejection with a file."""
    try:
        root_evidence = _inspect_safe_chain(path, platform)
    except CliFailure as failure:
        if failure.code == "unsafe_project_path":
            raise failure from cause
        raise
    except FileNotFoundError as changed:
        raise CliFailure(
            "unsafe_project_path",
            "The project path changed while its protected lease was acquired.",
            module="backend",
            details={},
        ) from changed
    if not root_evidence.is_directory:
        raise CliFailure(
            "project_not_directory",
            "The project path is not a directory.",
            module="backend",
            details={},
        ) from cause
    raise CliFailure(
        "unsafe_project_path",
        "The project path could not be opened without following links.",
        module="backend",
        details={},
    ) from cause


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
            module="backend", details={},
        ) from exc
    except RuntimeError as exc:
        raise CliFailure(
            "project_target_changed",
            "The project .mex file changed while it was being read; reload and retry.",
            module="backend", details={},
        ) from exc
    except (OSError, ValueError) as exc:
        raise CliFailure(
            "unsafe_project_path",
            "The project .mex file could not be opened as a safe regular file.",
            module="backend", details={},
        ) from exc
    if not _identity_available(snapshot.identity):
        raise CliFailure(
            "project_identity_unavailable",
            "A reliable platform file identity is unavailable for the project .mex file.",
            module="backend", details={},
        )
    return snapshot


def _protected_root(platform: TargetPlatform, path: Path):
    protector = getattr(platform, "protect_root", None)
    if not callable(protector):
        raise CliFailure(
            "project_identity_unavailable",
            "The target platform cannot provide a protected project-root lease.",
            module="backend", details={},
        )
    return protector(path)


def _direct_mex_entries(root: Path, platform: TargetPlatform) -> tuple[Path, ...]:
    try:
        entries = platform.list_directory(root)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while enumerating the project directory.",
            module="backend", details={},
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
                    module="backend", details={},
                )
            root_evidence = _inspect(supplied_root, adapter)
            if not root_evidence.exists:
                raise CliFailure(
                    "project_not_found", "The project directory does not exist.",
                    module="backend", details={},
                )
            if not root_evidence.is_directory:
                raise CliFailure(
                    "project_not_directory", "The project path is not a directory.",
                    module="backend", details={},
                )
            _inspect_safe_chain(supplied_root, adapter)
            canonical_root = _canonicalize(supplied_root, adapter)
            matches = _direct_mex_entries(supplied_root, adapter)
            if not matches:
                raise CliFailure(
                    "project_mex_not_found",
                    "No .mex file was found in the project directory.",
                    module="backend", details={"mex_count": 0},
                )
            if len(matches) != 1:
                raise CliFailure(
                    "project_mex_ambiguous",
                    f"Expected one .mex file, found {len(matches)}.",
                    module="backend",
                    details={"mex_count": len(matches)},
                )
            supplied_mex = matches[0]
            mex_evidence = _inspect(supplied_mex, adapter)
            if mex_evidence.is_symlink or mex_evidence.is_reparse_point or mex_evidence.is_mount_point:
                raise CliFailure(
                    "unsafe_project_path",
                    "The project .mex file must not be a link, mount point, or reparse point.",
                    module="backend", details={},
                )
            if not mex_evidence.is_regular:
                raise CliFailure(
                    "project_mex_not_regular", "The project .mex path is not a regular file.",
                    module="backend", details={},
                )
            canonical_mex = _canonicalize(supplied_mex, adapter)
            try:
                canonical_mex.relative_to(canonical_root)
            except ValueError as exc:
                raise CliFailure(
                    "unsafe_project_path",
                    "The project .mex file resolves outside the project root.",
                    module="backend",
                    details={},
                ) from exc
            snapshot = _capture_snapshot(supplied_mex, adapter)
            snapshot = FileSnapshot(canonical_mex, snapshot.identity, snapshot.size,
                                    snapshot.mtime_ns, snapshot.ctime_ns,
                                    snapshot.sha256, snapshot.content, snapshot.mode)
            after_matches = _direct_mex_entries(supplied_root, adapter)
            if tuple(path.name for path in after_matches) != (supplied_mex.name,):
                raise CliFailure(
                    "project_target_changed",
                    "The project .mex set changed while the target was being verified.",
                    module="backend", details={},
                )
            after = _capture_snapshot(after_matches[0], adapter)
            if after.identity != snapshot.identity or after.sha256 != snapshot.sha256:
                raise CliFailure(
                    "project_target_changed",
                    "The project .mex file changed while the target was being verified.",
                    module="backend", details={},
                )
            if _canonicalize(supplied_root, adapter) != canonical_root:
                raise CliFailure(
                    "project_target_changed",
                    "The project path changed while the target was being verified.",
                    module="backend", details={},
                )
            lease.retain()
            return VerifiedProjectTarget(canonical_root, snapshot, lease)
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while acquiring the protected project lease.",
            module="backend", details={},
        ) from exc
    except FileNotFoundError as exc:
        raise CliFailure(
            "project_not_found", "The project directory does not exist.",
            module="backend", details={},
        ) from exc
    except OSError as exc:
        if exc.errno == getattr(os, "ENOTDIR", 20):
            _raise_protected_root_enotdir(supplied_root, adapter, exc)
        raise CliFailure(
            "unsafe_project_path",
            "The protected project lease could not be acquired safely.",
            module="backend", details={"errno": exc.errno} if exc.errno is not None else {},
        ) from exc


def read_project_relative(
    target: VerifiedProjectTarget,
    relative: str,
    *,
    max_bytes: int,
) -> bytes | None:
    """Read one bounded project-relative file through the live root lease."""
    snapshot = snapshot_project_relative(target, relative, max_bytes=max_bytes)
    return None if snapshot is None else snapshot.content


def snapshot_project_relative(
    target: VerifiedProjectTarget,
    relative: str,
    *,
    max_bytes: int,
) -> FileSnapshot | None:
    """Capture one bounded project-relative file through the live root lease."""
    if not isinstance(target, VerifiedProjectTarget):
        raise TypeError("target must be a VerifiedProjectTarget")
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")
    parts = tuple(relative.split("/"))
    if not parts or any(not part or part in {".", ".."} or "\\" in part for part in parts):
        raise ValueError("relative project paths must contain only fixed child names")
    platform = target.lease._resources.get("platform")
    try:
        with target.lease.borrow():
            if isinstance(platform, _PosixTargetPlatform):
                return _read_posix_relative(target, parts, max_bytes)
            if isinstance(platform, _WindowsTargetPlatform):
                return _read_windows_relative(target, parts, max_bytes, platform)
            raise CliFailure(
                "project_identity_unavailable",
                "The verified target does not retain a handle-capable project reader.",
                module="backend",
            )
    except FileNotFoundError:
        return None
    except CliFailure:
        raise
    except PermissionError as exc:
        raise CliFailure(
            "project_permission_denied",
            "Permission was denied while reading project metadata.",
            module="backend", details={"source": relative},
        ) from exc
    except RuntimeError as exc:
        raise CliFailure(
            "project_metadata_source_changed",
            "A project metadata source changed while it was read; reload and retry.",
            module="backend", details={"source": relative},
        ) from exc
    except OSError as exc:
        raise CliFailure(
            "unsafe_project_path",
            "A project metadata source could not be opened without following links.",
            module="backend", details={"source": relative},
        ) from exc


def snapshot_safe_relative(root: Path, relative: str, *, max_bytes: int) -> FileSnapshot | None:
    """Capture a bounded root-relative regular file without following path links."""
    absolute_root = Path(root).absolute()
    platform = default_target_platform()
    with _protected_root(platform, absolute_root) as lease:
        placeholder = FileSnapshot(
            absolute_root, FileIdentity(None, None, None), 0, 0, 0, "", b""
        )
        target = VerifiedProjectTarget(absolute_root, placeholder, lease)
        return snapshot_project_relative(target, relative, max_bytes=max_bytes)


def _read_posix_relative(
    target: VerifiedProjectTarget,
    parts: tuple[str, ...],
    max_bytes: int,
) -> FileSnapshot:
    root_fd = target.lease._resources.get("root_fd")
    platform = target.lease._resources.get("platform")
    if root_fd is None or not platform._no_follow or not platform._nonblock:
        raise CliFailure(
            "project_identity_unavailable",
            "Safe project-relative open flags are unavailable.",
            module="backend",
        )
    opened: list[int] = []
    parent = root_fd
    current = target.root
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | platform._no_follow | platform._nonblock
        for part in parts[:-1]:
            current /= part
            if platform._mount_detector(current):
                raise CliFailure(
                    "unsafe_project_path", "Project metadata paths must not cross mounts.",
                    module="backend", details={"path": str(current)},
                )
            parent = os.open(part, directory_flags, dir_fd=parent)
            opened.append(parent)
            if platform._mount_detector(current):
                raise CliFailure(
                    "unsafe_project_path", "Project metadata mount topology changed during open.",
                    module="backend", details={"path": str(current)},
                )
        current /= parts[-1]
        if platform._mount_detector(current):
            raise CliFailure(
                "unsafe_project_path", "Project metadata paths must not cross mounts.",
                module="backend", details={"path": str(current)},
            )
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | platform._no_follow | platform._nonblock
        descriptor = os.open(parts[-1], flags, dir_fd=parent)
        opened.append(descriptor)
        if platform._mount_detector(current):
            raise CliFailure(
                "unsafe_project_path", "Project metadata mount topology changed during open.",
                module="backend", details={"path": str(current)},
            )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError("metadata source is not a regular file")
        if before.st_size > max_bytes:
            raise CliFailure(
                "project_metadata_source_too_large",
                "A project metadata source exceeds its size limit.",
                module="backend", details={"size": before.st_size, "limit": max_bytes},
            )
        content = b""
        while chunk := os.read(descriptor, min(64 * 1024, max_bytes + 1 - len(content))):
            content += chunk
            if len(content) > max_bytes:
                raise CliFailure(
                    "project_metadata_source_too_large",
                    "A project metadata source exceeds its size limit.",
                    module="backend", details={"limit": max_bytes},
                )
        after = os.fstat(descriptor)
        before_evidence = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        after_evidence = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if before_evidence != after_evidence or len(content) != before.st_size:
            raise RuntimeError("metadata source changed")
        return FileSnapshot(
            current,
            FileIdentity(before.st_dev, before.st_ino, None),
            before.st_size, before.st_mtime_ns, before.st_ctime_ns,
            hashlib.sha256(content).hexdigest(), content,
            stat.S_IMODE(before.st_mode),
        )
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def _read_windows_relative(
    target: VerifiedProjectTarget,
    parts: tuple[str, ...],
    max_bytes: int,
    platform: _WindowsTargetPlatform,
) -> FileSnapshot:
    held = []
    current = target.root
    try:
        for part in parts[:-1]:
            current /= part
            handle = platform._open(current, read=True, directory=True, share_delete=False, share_write=False)
            held.append(handle)
            tag = platform._query(handle, 9, _FILE_ATTRIBUTE_TAG_INFO)
            if tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
                raise OSError("metadata parent is a reparse point")
        current /= parts[-1]
        handle = platform._open(current, read=True, directory=False, share_delete=False, share_write=False)
        held.append(handle)
        tag = platform._query(handle, 9, _FILE_ATTRIBUTE_TAG_INFO)
        if tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise OSError("metadata source is a reparse point")
        basic_before = platform._query(handle, 0, _FILE_BASIC_INFO)
        standard_before = platform._query(handle, 1, _FILE_STANDARD_INFO)
        id_before = platform._query(handle, 18, _FILE_ID_INFO)
        if standard_before.Directory:
            raise OSError("metadata source is not a regular file")
        if standard_before.EndOfFile > max_bytes:
            raise CliFailure(
                "project_metadata_source_too_large",
                "A project metadata source exceeds its size limit.",
                module="backend", details={"size": standard_before.EndOfFile, "limit": max_bytes},
            )
        chunks = []
        while True:
            buffer = ctypes.create_string_buffer(min(64 * 1024, max_bytes + 1))
            count = wintypes.DWORD()
            if not _ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if count.value == 0:
                break
            chunks.append(buffer.raw[:count.value])
            if sum(map(len, chunks)) > max_bytes:
                raise CliFailure(
                    "project_metadata_source_too_large",
                    "A project metadata source exceeds its size limit.",
                    module="backend", details={"limit": max_bytes},
                )
        basic_after = platform._query(handle, 0, _FILE_BASIC_INFO)
        standard_after = platform._query(handle, 1, _FILE_STANDARD_INFO)
        id_after = platform._query(handle, 18, _FILE_ID_INFO)
        before = (id_before.VolumeSerialNumber, bytes(id_before.FileId.Identifier), standard_before.EndOfFile, basic_before.LastWriteTime, basic_before.ChangeTime)
        after = (id_after.VolumeSerialNumber, bytes(id_after.FileId.Identifier), standard_after.EndOfFile, basic_after.LastWriteTime, basic_after.ChangeTime)
        content = b"".join(chunks)
        if before != after or len(content) != standard_before.EndOfFile:
            raise RuntimeError("metadata source changed")
        return FileSnapshot(
            current,
            FileIdentity(
                None, None,
                WindowsFileId(id_before.VolumeSerialNumber, bytes(id_before.FileId.Identifier)),
            ),
            standard_before.EndOfFile,
            basic_before.LastWriteTime * 100,
            basic_before.ChangeTime * 100,
            hashlib.sha256(content).hexdigest(), content,
            0o444 if basic_before.FileAttributes & _FILE_ATTRIBUTE_READONLY else 0o666,
        )
    finally:
        for handle in reversed(held):
            _CloseHandle(handle)


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


def release_for_publish(
    target: VerifiedProjectTarget,
    platform: TargetPlatform | None = None,
) -> PublishExpectation:
    """Revalidate and release a target, returning Task 4 publish evidence."""
    revalidate_snapshot(target, platform=platform)
    expectation = PublishExpectation(target.mex.path, target.mex.identity, target.mex.sha256)
    target.close()
    return expectation


def revalidate_publish_expectation(
    expectation: PublishExpectation,
    platform: TargetPlatform | None = None,
) -> FileSnapshot:
    """Recheck the exact selected target after releasing its live lease."""
    adapter = platform or default_target_platform()
    try:
        current = _capture_snapshot(expectation.path, adapter)
    except CliFailure as exc:
        raise CliFailure(
            "project_target_changed",
            "The verified project target changed before publication; reload and retry.",
            module="backend",
        ) from exc
    if current.identity != expectation.identity or current.sha256 != expectation.sha256:
        raise CliFailure(
            "project_target_changed",
            "The verified project target changed before publication; reload and retry.",
            module="backend",
        )
    return current


def atomic_publish_candidate(
    expectation: PublishExpectation,
    staging: Path,
    candidate_sha256: str,
    platform: TargetPlatform | None = None,
) -> AtomicPublishResult:
    """Publish by atomically capturing and verifying the displaced target.

    The syscall itself captures whichever destination existed at its linearized
    instant.  A check-then-swap attacker is therefore detected from the
    displaced file, restored atomically, and never permanently overwritten.
    Platforms without capture/exchange semantics fail closed.
    """
    adapter = platform or default_target_platform()
    state = AtomicPublishState(expectation.path, staging)
    exchange = getattr(adapter, "exchange_capture", None)
    restore = getattr(adapter, "restore_capture", None)
    if not callable(exchange) or not callable(restore):
        raise CliFailure(
            "configure_atomic_publish_unavailable",
            "This platform cannot atomically capture a displaced .mex target.",
            module="backend",
        )

    revalidate_publish_expectation(expectation, platform=adapter)
    capture = _unused_publish_name(expectation.path, "displaced")
    try:
        displaced_path = exchange(staging, expectation.path, capture)
    except NotImplementedError as exc:
        raise CliFailure(
            "configure_atomic_publish_unavailable",
            "This platform lacks the required atomic exchange primitive.",
            module="backend",
        ) from exc
    except OSError as exc:
        raise CliFailure(
            "configure_publish_failed",
            "The verified .mex candidate could not be published atomically.",
            module="backend",
        ) from exc
    state.phase = "exchanged"
    state.displaced_path = Path(displaced_path)

    try:
        displaced = adapter.snapshot_file(displaced_path)
        published = adapter.snapshot_file(expectation.path)
    except (OSError, ValueError, RuntimeError) as exc:
        raise AtomicPublishFailure(
            "configure_publish_uncertain",
            "Atomic publication artifacts could not be classified and were preserved.",
            state,
        ) from exc
    state.displaced = displaced
    state.published = published
    state.phase = "classified"

    if displaced.identity != expectation.identity or displaced.sha256 != expectation.sha256:
        residual = _restore_displaced_target(
            adapter, restore, expectation.path, displaced_path, displaced, published,
            state,
        )
        if residual is not None:
            raise AtomicPublishFailure(
                "project_target_changed",
                "The target changed at publication; it was restored with audit evidence retained.",
                state,
            )
        raise CliFailure(
            "project_target_changed",
            "The verified project target changed at publication; it was preserved and restored.",
            module="backend",
        )
    if published.sha256 != candidate_sha256:
        residual = _restore_displaced_target(
            adapter, restore, expectation.path, displaced_path, displaced, published,
            state,
        )
        if residual is not None:
            raise AtomicPublishFailure(
                "configure_staging_changed",
                "The staged candidate changed; the original was restored with audit evidence retained.",
                state,
            )
        raise CliFailure(
            "configure_staging_changed",
            "The staged candidate changed at publication; the original was restored.",
            module="backend",
        )
    if expectation.identity is not None and expectation.sha256 and (
        displaced.mode is not None and published.mode is not None
        and expectation.path.suffix.lower() == ".mex"
        and published.mode != displaced.mode
    ):
        residual = _restore_displaced_target(
            adapter, restore, expectation.path, displaced_path, displaced, published,
            state,
        )
        if residual is not None:
            raise AtomicPublishFailure(
                "configure_publish_metadata_changed",
                "Publication metadata changed; the original was restored with audit evidence retained.",
                state,
            )
        raise CliFailure(
            "configure_publish_metadata_changed",
            "The published .mex did not preserve required file metadata.",
            module="backend",
        )
    state.phase = "published"
    return AtomicPublishResult(published, displaced, displaced_path, state)


def atomic_install_absent(
    path: Path,
    staging: Path,
    candidate_sha256: str,
    platform: TargetPlatform | None = None,
    *,
    install_fn: Callable[[Path, Path], None] | None = None,
) -> AtomicPublishResult:
    """Atomically install a candidate only while its destination is absent."""
    adapter = platform if platform is not None else default_target_platform()
    state = AtomicPublishState(path, staging)
    installer = (
        install_fn if install_fn is not None
        else getattr(adapter, "install_absent", None)
    )
    if not callable(installer):
        raise CliFailure(
            "configure_atomic_publish_unavailable",
            "This platform cannot atomically install an absent destination.",
            module="backend",
        )
    if os.path.lexists(path):
        raise CliFailure(
            "configure_backup_changed",
            "The backup destination appeared before atomic installation.",
            module="backend",
        )
    try:
        candidate = adapter.snapshot_file(staging)
    except Exception as exc:
        raise CliFailure(
            "configure_staging_changed",
            "The staged backup candidate could not be classified before publication.",
            module="backend",
        ) from exc
    if (
        candidate.sha256 != candidate_sha256
        or hashlib.sha256(candidate.content).hexdigest() != candidate_sha256
    ):
        raise CliFailure(
            "configure_staging_changed",
            "The staged backup candidate changed before publication.",
            module="backend",
        )

    def failed_install(
        code: str, message: str
    ) -> AtomicPublishFailure:
        try:
            inspection = adapter.inspect(path)
            classifiable = (
                inspection.exists
                and not inspection.is_directory
                and inspection.is_regular
                and not inspection.is_symlink
                and not inspection.is_reparse_point
                and not inspection.is_mount_point
            )
            published = adapter.snapshot_file(path) if classifiable else None
        except Exception:
            published = None
        if published is not None and (
            published.identity == candidate.identity
            and published.sha256 == candidate.sha256
            and published.content == candidate.content
            and hashlib.sha256(published.content).hexdigest() == candidate_sha256
        ):
            state.published = published
        return AtomicPublishFailure(code, message, state)

    try:
        installer(staging, path)
    except NotImplementedError as exc:
        raise failed_install(
            "configure_atomic_publish_unavailable",
            "This platform lacks atomic no-replace installation.",
        ) from exc
    except Exception as exc:
        raise failed_install(
            "configure_backup_changed",
            "The absent backup destination changed at publication.",
        ) from exc
    state.phase = "installed"

    try:
        inspection = adapter.inspect(path)
    except Exception as exc:
        raise AtomicPublishFailure(
            "configure_backup_uncertain",
            "The installed backup could not be classified and was preserved.",
            state,
        ) from exc
    if (
        not inspection.exists
        or inspection.is_directory
        or not inspection.is_regular
        or inspection.is_symlink
        or inspection.is_reparse_point
        or inspection.is_mount_point
    ):
        raise AtomicPublishFailure(
            "configure_backup_uncertain",
            "The installed backup could not be classified and was preserved.",
            state,
        )
    try:
        published = adapter.snapshot_file(path)
    except Exception as exc:
        raise AtomicPublishFailure(
            "configure_backup_uncertain",
            "The installed backup could not be classified and was preserved.",
            state,
        ) from exc
    state.published = published
    if (
        published.identity != candidate.identity
        or published.sha256 != candidate.sha256
        or published.content != candidate.content
        or hashlib.sha256(published.content).hexdigest() != candidate_sha256
    ):
        raise AtomicPublishFailure(
            "configure_staging_changed",
            "The installed backup differs from the validated candidate identity or content.",
            state,
        )
    state.phase = "published"
    return AtomicPublishResult(published, None, None, state)


def rollback_atomic_publish(
    result: AtomicPublishResult,
    target: Path,
    platform: TargetPlatform | None = None,
) -> Path | None:
    """Restore a captured original only while the published candidate is intact."""
    adapter = platform or default_target_platform()
    if result.displaced is None or result.displaced_path is None:
        return discard_owned_path(target, result.published, adapter)
    restore = getattr(adapter, "restore_capture", None)
    if not callable(restore):
        raise CliFailure(
            "configure_publish_restore_failed",
            "The atomic publication cannot be rolled back on this platform.",
            module="backend",
        )
    try:
        current = adapter.snapshot_file(target)
    except (OSError, ValueError, RuntimeError) as exc:
        raise CliFailure(
            "configure_publish_restore_failed",
            "The published target changed before rollback and was not overwritten.",
            module="backend",
        ) from exc
    if (
        current.identity != result.published.identity
        or current.sha256 != result.published.sha256
    ):
        raise CliFailure(
            "configure_publish_restore_failed",
            "The published target changed before rollback and was not overwritten.",
            module="backend",
        )
    return _restore_displaced_target(
        adapter, restore, target, result.displaced_path, result.displaced,
        result.published, result.state or AtomicPublishState(
            target, result.published.path, published=result.published,
            displaced_path=result.displaced_path, displaced=result.displaced,
        ),
    )


def finalize_atomic_publish(
    result: AtomicPublishResult,
    platform: TargetPlatform | None = None,
) -> Path | None:
    """Discard only a proven transaction-owned displaced artifact."""
    if result.displaced is None or result.displaced_path is None:
        return None
    return discard_owned_path(
        result.displaced_path, result.displaced,
        platform or default_target_platform(),
    )


def prepare_atomic_finalize(
    result: AtomicPublishResult,
    platform: TargetPlatform | None = None,
) -> None:
    """Classify rollback evidence without destroying it."""
    if result.displaced is None or result.displaced_path is None:
        # An absent-destination install still needs a final destination CAS.
        adapter = platform or default_target_platform()
        try:
            current = adapter.snapshot_file(result.published.path)
        except (OSError, ValueError, RuntimeError) as exc:
            state = result.state or AtomicPublishState(
                result.published.path, result.published.path,
                published=result.published,
            )
            raise AtomicPublishFailure(
                "configure_finalize_prepare_failed",
                "The published destination could not be classified before commit.",
                state,
            ) from exc
        if not _same_snapshot(current, result.published):
            state = result.state or AtomicPublishState(
                result.published.path, result.published.path,
                published=result.published,
            )
            raise AtomicPublishFailure(
                "configure_finalize_prepare_changed",
                "The published destination changed before the commit decision.",
                state,
            )
        return
    adapter = platform or default_target_platform()
    try:
        published = adapter.snapshot_file(result.published.path)
        current = adapter.snapshot_file(result.displaced_path)
    except (OSError, ValueError, RuntimeError) as exc:
        state = result.state or AtomicPublishState(
            result.published.path, result.published.path,
            published=result.published, displaced_path=result.displaced_path,
            displaced=result.displaced,
        )
        raise AtomicPublishFailure(
            "configure_finalize_prepare_failed",
            "Rollback evidence could not be classified before commit.",
            state,
        ) from exc
    if (
        not _same_snapshot(published, result.published)
        or not _same_snapshot(current, result.displaced)
    ):
        state = result.state or AtomicPublishState(
            result.published.path, result.published.path,
            published=result.published, displaced_path=result.displaced_path,
            displaced=result.displaced,
        )
        raise AtomicPublishFailure(
            "configure_finalize_prepare_changed",
            "Rollback evidence changed before the commit decision.",
            state,
        )


def _restore_displaced_target(
    adapter: TargetPlatform,
    restore: Callable[[Path, Path, Path], Path],
    target: Path,
    displaced_path: Path,
    expected_displaced: FileSnapshot,
    expected_current: FileSnapshot,
    state: AtomicPublishState,
) -> Path | None:
    rescue = _unused_publish_name(target, "rejected")
    state.rescue_paths.append(rescue)
    try:
        rejected_path = restore(target, displaced_path, rescue)
        state.phase = "restore_exchanged"
        restored = adapter.snapshot_file(target)
        rescued = adapter.snapshot_file(rejected_path)
    except (OSError, ValueError, RuntimeError) as exc:
        raise AtomicPublishFailure(
            "configure_publish_restore_failed",
            "An unexpected destination was captured but could not be restored safely.",
            state,
        ) from exc
    if not _same_snapshot(restored, expected_displaced):
        raise AtomicPublishFailure(
            "configure_publish_restore_failed",
            "The displaced file was not restored with its verified identity.",
            state,
        )
    if not _same_snapshot(rescued, expected_current):
        recovery = _unused_publish_name(target, "recovery")
        state.rescue_paths.append(recovery)
        try:
            recovered_path = restore(target, rejected_path, recovery)
            state.phase = "secondary_restore_exchanged"
            external = adapter.snapshot_file(target)
            recovered = adapter.snapshot_file(recovered_path)
        except (OSError, ValueError, RuntimeError) as exc:
            raise AtomicPublishFailure(
                "configure_publish_restore_cas_failed",
                "Restore captured an external destination and secondary recovery failed.",
                state,
            ) from exc
        if not _same_snapshot(external, rescued) or not _same_snapshot(
            recovered, expected_displaced
        ):
            raise AtomicPublishFailure(
                "configure_publish_restore_cas_failed",
                "Secondary recovery could not prove all preserved identities.",
                state,
            )
        raise AtomicPublishFailure(
            "project_target_changed",
            "The target changed during restore; external and displaced files were preserved.",
            state,
        )
    residual = discard_owned_path(Path(rejected_path), expected_current, adapter)
    if residual is not None:
        state.rescue_paths.append(residual)
    return residual


def _same_snapshot(actual: FileSnapshot, expected: FileSnapshot) -> bool:
    return actual.identity == expected.identity and actual.sha256 == expected.sha256


def discard_owned_path(
    path: Path,
    expected: FileSnapshot,
    adapter: TargetPlatform,
) -> Path | None:
    if not os.path.lexists(path) and not hasattr(adapter, "files"):
        return None
    capture_remove = getattr(adapter, "capture_remove", None)
    install_absent = getattr(adapter, "install_absent", None)
    if not callable(capture_remove) or not callable(install_absent):
        raise CliFailure(
            "configure_cleanup_failed",
            "The platform cannot atomically capture a cleanup candidate.",
            module="backend",
        )
    quarantine = _unused_publish_name(path, "cleanup")
    try:
        capture_remove(path, quarantine)
        captured = adapter.snapshot_file(quarantine)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise CliFailure(
            "configure_cleanup_failed",
            "A cleanup candidate could not be captured safely.",
            module="backend",
            details={"preserved": sorted({path.name, quarantine.name})},
        ) from exc
    if not _same_snapshot(captured, expected):
        try:
            install_absent(quarantine, path)
        except (OSError, ValueError, RuntimeError) as exc:
            raise CliFailure(
                "configure_cleanup_restore_failed",
                "An unowned cleanup path was preserved but could not be restored.",
                module="backend",
                details={"preserved": [quarantine.name]},
            ) from exc
        raise CliFailure(
            "configure_cleanup_ownership_changed",
            "An unowned cleanup path was preserved and not deleted.",
            module="backend",
        )
    unlinker = getattr(adapter, "unlink_path", None)
    secure_delete = getattr(adapter, "secure_delete_owned", None)
    try:
        if callable(secure_delete):
            secure_delete(quarantine, captured)
            return None
        if callable(unlinker):
            unlinker(quarantine)
            return None
        return quarantine
    except OSError as exc:
        raise CliFailure(
            "configure_cleanup_failed",
            "A verified transaction-owned artifact could not be removed.",
            module="backend",
            details={"preserved": [quarantine.name]},
        ) from exc


def _unused_publish_name(target: Path, purpose: str) -> Path:
    for _ in range(32):
        candidate = target.parent / (
            f".{target.name}.{purpose}.{secrets.token_hex(12)}.tmp"
        )
        if not os.path.lexists(candidate):
            return candidate
    raise CliFailure(
        "configure_staging_failed",
        "A unique atomic-publication capture name could not be allocated.",
        module="backend",
        details={"purpose": purpose},
    )
