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
# File:        deploy_rtd_skill.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-13
# Version:     0.1.0
# Description: Deploy the released RTD CfgFile CLI companion skill into Codex
#              and Claude Code skill indexes without copying development data.
# =================================================================================

from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
import tomllib
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from pathlib import PurePosixPath

SKILL_NAME = "autombd-rtd"
RELEASE_MANIFEST_NAME = "release-manifest.json"
RELEASE_MANIFEST_FORMAT_VERSION = 1
SKILL_PAYLOAD_ITEMS = (
    "SKILL.md",
    "__main__.py",
    "rtd-config-cli-py",
    "assets",
    "reference",
)
MODULE_REFERENCE_FILES = tuple(
    Path("reference") / f"{module}-spec.md"
    for module in (
        "mcu",
        "basenxp",
        "platform",
        "port",
        "dio",
        "mcl",
        "uart",
        "adc",
    )
)
SKILL_PAYLOAD_REQUIRED_FILES = (
    Path("SKILL.md"),
    Path("__main__.py"),
    Path("rtd-config-cli-py") / "rtd_config" / "cli.py",
    Path("assets") / "nxp" / "s32k3" / "uart" / "uart.json",
    *MODULE_REFERENCE_FILES,
)
SUPPORTED_AGENTS = ("codex", "claude")
CANONICAL_AGENT = "codex"
AGENT_SKILL_DIRS = {
    "codex": Path(".agents") / "skills",
    "claude": Path(".claude") / "skills",
}


@dataclass(frozen=True)
class ProjectVersions:
    project: str
    skill: str
    launcher_header: str
    package_header: str
    package: str
    manifest: str


@dataclass(frozen=True)
class ReleaseFile:
    path: str
    sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
    format_version: int
    release_version: str
    files: tuple[ReleaseFile, ...]


@dataclass(frozen=True)
class DeployResult:
    agent: str
    action: str
    version: str
    destination: Path
    reason: str = ""


def parse_version_tuple(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise ValueError(f"unsupported semantic version: {version!r}")
    return tuple(int(part) for part in version.split("."))


def extract_front_matter_value(markdown: str, key: str) -> str | None:
    if not markdown.startswith("---\n"):
        return None
    end = markdown.find("\n---", 4)
    if end == -1:
        return None
    front_matter = markdown[4:end]
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(front_matter)
    return match.group(1).strip("\"'")


def read_skill_version(skill_file: Path) -> str | None:
    if not skill_file.is_file():
        return None
    return extract_front_matter_value(skill_file.read_text(encoding="utf-8"), "version")


def read_launcher_header_version(launcher_file: Path) -> str:
    text = launcher_file.read_text(encoding="utf-8")
    match = re.search(r"^# Version:\s+(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing Version header in {launcher_file}")
    return match.group(1)


def read_package_version(package_init: Path) -> str:
    text = package_init.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing __version__ in {package_init}")
    return match.group(1)


def read_project_version(pyproject_file: Path) -> str:
    with pyproject_file.open("rb") as stream:
        document = tomllib.load(stream)
    try:
        version = document["project"]["version"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"missing [project].version in {pyproject_file}") from exc
    if not isinstance(version, str):
        raise RuntimeError(f"invalid [project].version in {pyproject_file}")
    parse_version_tuple(version)
    return version


def _canonical_manifest_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("manifest path must be a non-empty relative POSIX path")
    if (
        "\\" in value
        or "//" in value
        or value.startswith("/")
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise RuntimeError(f"manifest path is not canonical: {value!r}")
    path = PurePosixPath(value)
    if any(part in ("", ".", "..") for part in path.parts):
        raise RuntimeError(f"manifest path is not a safe relative path: {value!r}")
    if path.as_posix() != value or value == RELEASE_MANIFEST_NAME:
        raise RuntimeError(f"manifest path is not canonical: {value!r}")
    return value


def read_release_manifest(skill_root: Path) -> ReleaseManifest:
    manifest_file = skill_root / RELEASE_MANIFEST_NAME
    try:
        document = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read release manifest: {manifest_file}") from exc
    if not isinstance(document, dict) or set(document) != {
        "format_version",
        "release_version",
        "files",
    }:
        raise RuntimeError("release manifest schema has unexpected fields")
    if document["format_version"] != RELEASE_MANIFEST_FORMAT_VERSION:
        raise RuntimeError("unsupported release manifest format version")
    release_version = document["release_version"]
    if not isinstance(release_version, str):
        raise RuntimeError("release manifest version must be a string")
    try:
        parse_version_tuple(release_version)
    except ValueError as exc:
        raise RuntimeError("invalid release manifest version") from exc
    raw_files = document["files"]
    if not isinstance(raw_files, list):
        raise RuntimeError("release manifest files must be a list")
    files: list[ReleaseFile] = []
    paths: list[str] = []
    folded_paths: set[str] = set()
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {"path", "sha256"}:
            raise RuntimeError("release manifest file schema has unexpected fields")
        path = _canonical_manifest_path(raw_entry["path"])
        digest = raw_entry["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"invalid SHA-256 hash for manifest path {path!r}")
        folded = path.casefold()
        if path in paths or folded in folded_paths:
            raise RuntimeError(f"duplicate or case-colliding manifest path: {path!r}")
        paths.append(path)
        folded_paths.add(folded)
        files.append(ReleaseFile(path=path, sha256=digest))
    if paths != sorted(paths):
        raise RuntimeError("release manifest paths are not in sorted order")
    return ReleaseManifest(
        format_version=RELEASE_MANIFEST_FORMAT_VERSION,
        release_version=release_version,
        files=tuple(files),
    )


def read_project_versions(repo_root: Path) -> ProjectVersions:
    skill_root = repo_root / SKILL_NAME
    skill_version = read_skill_version(skill_root / "SKILL.md")
    if skill_version is None:
        raise RuntimeError(f"missing version in {skill_root / 'SKILL.md'}")
    package_init = skill_root / "rtd-config-cli-py" / "rtd_config" / "__init__.py"
    return ProjectVersions(
        project=read_project_version(repo_root / "pyproject.toml"),
        skill=skill_version,
        launcher_header=read_launcher_header_version(skill_root / "__main__.py"),
        package_header=read_launcher_header_version(package_init),
        package=read_package_version(package_init),
        manifest=read_release_manifest(skill_root).release_version,
    )


def require_consistent_project_versions(versions: ProjectVersions) -> str:
    unique_versions = {
        versions.project,
        versions.skill,
        versions.launcher_header,
        versions.package_header,
        versions.package,
        versions.manifest,
    }
    if len(unique_versions) != 1:
        raise RuntimeError(
            "project version mismatch: "
            f"pyproject.toml={versions.project}, "
            f"SKILL.md={versions.skill}, "
            f"launcher={versions.launcher_header}, "
            f"package_header={versions.package_header}, "
            f"package={versions.package}, "
            f"manifest={versions.manifest}"
        )
    parse_version_tuple(versions.project)
    return versions.project


def normalize_agents(agents: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for agent in agents:
        agent = agent.lower()
        if agent == "both":
            for supported_agent in SUPPORTED_AGENTS:
                if supported_agent not in normalized:
                    normalized.append(supported_agent)
            continue
        if agent not in SUPPORTED_AGENTS:
            raise ValueError(
                f"unsupported agent {agent!r}; expected one of: "
                f"{', '.join((*SUPPORTED_AGENTS, 'both'))}"
            )
        if agent not in normalized:
            normalized.append(agent)
    if not normalized:
        raise ValueError("at least one agent must be selected")
    return tuple(normalized)


def resolve_agent_skills_dir(
    target_project: Path,
    agent: str,
    *,
    platform=None,
) -> Path:
    agent = normalize_agents((agent,))[0]
    target = Path(os.path.abspath(target_project.expanduser()))
    return _ensure_safe_directory_chain(target, AGENT_SKILL_DIRS[agent], platform)


def _is_ignored_runtime_artifact(relative: PurePosixPath) -> bool:
    return (
        "__pycache__" in relative.parts
        or relative.suffix in {".pyc", ".pyo"}
    )


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return path.is_symlink()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag)


def _platform_is_link_or_reparse(platform, path: Path) -> bool:
    checker = _is_link_or_reparse if platform is None else platform.is_link_or_reparse
    return bool(checker(Path(path)))


@dataclass(frozen=True)
class _DirectoryIdentity:
    path: Path
    device: int
    inode: int
    handle: int | None = field(default=None, compare=False, repr=False)
    rename_access: bool = field(default=False, compare=False, repr=False)


def _open_windows_directory(
    path: Path,
    *,
    rename_access: bool = False,
    share_delete: bool = False,
) -> tuple[int, int, int]:
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0x80000000 | (0x00010000 if rename_access else 0),
        0x1 | 0x2 | (0x4 if share_delete else 0),
        None,
        3,  # OPEN_EXISTING
        0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        error = ctypes.get_last_error()
        raise RuntimeError(
            f"cannot open protected destination ancestor {path}: WinError {error}"
        )
    information = _ByHandleFileInformation()
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ByHandleFileInformation))
    get_information.restype = wintypes.BOOL
    if not get_information(handle, ctypes.byref(information)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise RuntimeError(
            f"cannot identify protected destination ancestor {path}: WinError {error}"
        )
    if not information.attributes & 0x10 or information.attributes & 0x400:
        kernel32.CloseHandle(handle)
        raise RuntimeError(
            f"unsafe destination ancestor is not a real directory: {path}"
        )
    file_id = (information.file_index_high << 32) | information.file_index_low
    return int(handle), int(information.volume_serial), int(file_id)


def _close_directory_handle(handle: int) -> None:
    if os.name == "nt":
        from ctypes import wintypes

        close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        close_handle(handle)
    else:
        os.close(handle)


def _open_windows_regular_file(
    path: Path,
    *,
    desired_access: int,
    creation_disposition: int,
) -> int:
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = (
            ("attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("volume_serial", wintypes.DWORD),
            ("file_size_high", wintypes.DWORD),
            ("file_size_low", wintypes.DWORD),
            ("number_of_links", wintypes.DWORD),
            ("file_index_high", wintypes.DWORD),
            ("file_index_low", wintypes.DWORD),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        desired_access,
        0x1 | 0x2,  # FILE_SHARE_READ | FILE_SHARE_WRITE; intentionally no delete.
        None,
        creation_disposition,
        0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        error = ctypes.get_last_error()
        raise OSError(error, f"cannot open protected staging file {path}: WinError {error}")
    information = _ByHandleFileInformation()
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ByHandleFileInformation))
    get_information.restype = wintypes.BOOL
    if not get_information(handle, ctypes.byref(information)):
        error = ctypes.get_last_error()
        kernel32.CloseHandle(handle)
        raise OSError(error, f"cannot inspect protected staging file {path}: WinError {error}")
    if information.attributes & 0x10 or information.attributes & 0x400:
        kernel32.CloseHandle(handle)
        raise RuntimeError(f"unsafe staging entry is not a regular file: {path}")
    return int(handle)


def _write_windows_handle(handle: int, content: bytes) -> None:
    from ctypes import wintypes

    write_file = ctypes.WinDLL("kernel32", use_last_error=True).WriteFile
    write_file.argtypes = (
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    write_file.restype = wintypes.BOOL
    offset = 0
    while offset < len(content):
        chunk = content[offset : offset + 1024 * 1024]
        buffer = ctypes.create_string_buffer(chunk)
        written = wintypes.DWORD()
        if not write_file(handle, buffer, len(chunk), ctypes.byref(written), None):
            error = ctypes.get_last_error()
            raise OSError(error, f"protected staging write failed: WinError {error}")
        if not written.value:
            raise OSError("protected staging write made no progress")
        offset += written.value


def _read_windows_handle(handle: int) -> bytes:
    from ctypes import wintypes

    read_file = ctypes.WinDLL("kernel32", use_last_error=True).ReadFile
    read_file.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    read_file.restype = wintypes.BOOL
    chunks = []
    while True:
        buffer = ctypes.create_string_buffer(1024 * 1024)
        read = wintypes.DWORD()
        if not read_file(handle, buffer, len(buffer), ctypes.byref(read), None):
            error = ctypes.get_last_error()
            raise OSError(error, f"protected staging read failed: WinError {error}")
        if not read.value:
            return b"".join(chunks)
        chunks.append(buffer.raw[: read.value])


def _rename_windows_directory_handle(
    handle: int,
    destination: Path,
) -> None:
    from ctypes import wintypes

    destination_text = str(Path(destination).absolute())

    class _FileRenameInformation(ctypes.Structure):
        _fields_ = (
            ("flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * (len(destination_text) + 1)),
        )

    information = _FileRenameInformation()
    information.flags = 0
    information.root_directory = None
    information.file_name_length = len(destination_text.encode("utf-16-le"))
    information.file_name = destination_text
    set_information = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    ).SetFileInformationByHandle
    set_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    set_information.restype = wintypes.BOOL
    if not set_information(
        handle,
        3,  # FileRenameInfo
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        error = ctypes.get_last_error()
        raise OSError(error, f"handle-bound directory rename failed: WinError {error}")


def _open_directory_identity(path: Path, platform=None) -> _DirectoryIdentity:
    observed = _directory_identity(path, platform)
    if os.name == "nt":
        handle, volume, file_id = _open_windows_directory(path)
        return _DirectoryIdentity(path, volume, file_id, handle)
    flags = _posix_directory_open_flags()
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(
            f"cannot open protected destination ancestor {path}: {exc}"
        ) from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise RuntimeError(f"unsafe destination ancestor is not a directory: {path}")
    if (metadata.st_dev, metadata.st_ino) != (observed.device, observed.inode):
        os.close(descriptor)
        raise RuntimeError(f"destination ancestor changed while opening: {path}")
    return _DirectoryIdentity(path, metadata.st_dev, metadata.st_ino, descriptor)


def _open_child_directory_identity(
    parent: _DirectoryIdentity,
    path: Path,
    platform=None,
    *,
    rename_access: bool = False,
) -> _DirectoryIdentity:
    if path.parent != parent.path or parent.handle is None:
        raise RuntimeError("child capability is not relative to its pinned parent")
    if _platform_is_link_or_reparse(platform, path):
        raise RuntimeError(f"unsafe destination ancestor is linked: {path}")
    if os.name == "nt":
        if rename_access:
            handle, volume, file_id = _open_windows_directory(
                path,
                rename_access=True,
            )
            return _DirectoryIdentity(
                path,
                volume,
                file_id,
                handle,
                rename_access=True,
            )
        return _open_directory_identity(path, platform)
    try:
        descriptor = os.open(
            path.name,
            _posix_directory_open_flags(),
            dir_fd=parent.handle,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot open protected child directory {path}: {exc}") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise RuntimeError(f"unsafe destination ancestor is not a directory: {path}")
    return _DirectoryIdentity(path, metadata.st_dev, metadata.st_ino, descriptor)


def _posix_directory_open_flags() -> int:
    directory = getattr(os, "O_DIRECTORY", None)
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if directory is None or no_follow is None:
        raise RuntimeError("platform lacks required POSIX no-follow directory opens")
    return os.O_RDONLY | directory | no_follow


def _directory_identity(path: Path, platform=None) -> _DirectoryIdentity:
    path = Path(path)
    if _platform_is_link_or_reparse(platform, path):
        raise RuntimeError(
            f"unsafe destination ancestor is a symlink or reparse point: {path}"
        )
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError(f"destination ancestor is missing: {path}") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeError(f"unsafe destination ancestor is not a directory: {path}")
    return _DirectoryIdentity(path, metadata.st_dev, metadata.st_ino)


@dataclass
class _DestinationAncestorGuard:
    identities: tuple[_DirectoryIdentity, ...]
    platform: object | None = None
    closed: bool = field(default=False, init=False)

    def close(self) -> None:
        if self.closed:
            return
        for identity in reversed(self.identities):
            if identity.handle is None:
                continue
            _close_directory_handle(identity.handle)
        self.closed = True

    def __enter__(self):
        try:
            self.verify()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    def verify(self) -> None:
        for expected in self.identities:
            if os.name == "nt" and expected.handle is not None:
                if _platform_is_link_or_reparse(self.platform, expected.path):
                    raise RuntimeError(
                        f"unsafe destination ancestor is linked: {expected.path}"
                    )
                handle, device, inode = _open_windows_directory(
                    expected.path,
                    share_delete=expected.rename_access,
                )
                _close_directory_handle(handle)
                observed = _DirectoryIdentity(expected.path, device, inode)
            elif expected.handle is not None:
                metadata = os.fstat(expected.handle)
                observed = _DirectoryIdentity(
                    expected.path,
                    metadata.st_dev,
                    metadata.st_ino,
                )
            else:
                observed = _directory_identity(expected.path, self.platform)
            if (observed.device, observed.inode) != (expected.device, expected.inode):
                raise RuntimeError(
                    f"unsafe destination ancestor identity changed: {expected.path}"
                )

    def mutate(self, operation):
        self.verify()
        try:
            return operation()
        except OSError as exc:
            if self.platform is None:
                raise
            raise RuntimeError(f"protected destination mutation failed: {exc}") from exc
        finally:
            self.verify()

    def _atomic_mutation(self, mutation_kind: str | None, operation):
        cleanup = lambda: None
        hook = getattr(self.platform, "before_mutation", None)
        if mutation_kind is not None and hook is not None:
            cleanup = hook(mutation_kind, self.parent)
        try:
            return self.mutate(operation)
        finally:
            cleanup()
            self.verify()

    @property
    def parent(self) -> Path:
        return self.identities[-1].path

    @property
    def parent_handle(self) -> int:
        handle = self.identities[-1].handle
        if handle is None:
            raise RuntimeError("destination capability is closed")
        return handle

    def mkdir(self, path: Path, *, mutation_kind: str | None = None) -> None:
        path = Path(path)
        if path.parent != self.parent:
            raise RuntimeError("mkdir escapes protected destination namespace")
        if os.name == "nt":
            self._atomic_mutation(mutation_kind, path.mkdir)
        else:
            self._atomic_mutation(
                mutation_kind,
                lambda: os.mkdir(path.name, dir_fd=self.parent_handle),
            )

    def rename(
        self,
        source: Path,
        destination: Path,
        *,
        mutation_kind: str | None = None,
    ) -> None:
        source = Path(source)
        destination = Path(destination)
        if source.parent != self.parent or destination.parent != self.parent:
            raise RuntimeError("rename escapes protected destination namespace")
        if os.name == "nt":
            self._atomic_mutation(
                mutation_kind,
                lambda: source.rename(destination),
            )
        else:
            self._atomic_mutation(
                mutation_kind,
                lambda: os.rename(
                    source.name,
                    destination.name,
                    src_dir_fd=self.parent_handle,
                    dst_dir_fd=self.parent_handle,
                )
            )

    def entry_present(self, path: Path) -> bool:
        path = Path(path)
        if path.parent != self.parent:
            raise RuntimeError("entry lookup escapes protected destination namespace")
        try:
            if os.name == "nt":
                path.lstat()
            else:
                os.stat(path.name, dir_fd=self.parent_handle, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def entry_metadata(self, path: Path):
        path = Path(path)
        if path.parent != self.parent:
            raise RuntimeError("entry stat escapes protected destination namespace")
        if os.name == "nt":
            return path.lstat()
        return os.stat(path.name, dir_fd=self.parent_handle, follow_symlinks=False)

    def entry_identity(self, path: Path) -> _DirectoryIdentity:
        path = Path(path)
        if os.name == "nt":
            return _directory_identity(path, self.platform)
        if _platform_is_link_or_reparse(self.platform, path):
            raise RuntimeError(f"unsafe transaction entry is linked: {path}")
        metadata = self.entry_metadata(path)
        if not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError(f"unsafe transaction entry is not a directory: {path}")
        return _DirectoryIdentity(path, metadata.st_dev, metadata.st_ino)

    def entry_names(self) -> tuple[str, ...]:
        if os.name == "nt":
            return tuple(os.listdir(self.parent))
        return tuple(os.listdir(self.parent_handle))

    def write_child_file(self, directory: Path, name: str, content: str) -> None:
        directory = Path(directory)
        if directory.parent != self.parent or Path(name).name != name:
            raise RuntimeError("file write escapes protected destination namespace")
        if os.name == "nt":
            self.mutate(
                lambda: (directory / name).write_text(content, encoding="utf-8")
            )
            return
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

        def write_relative() -> None:
            child = os.open(
                directory.name,
                _posix_directory_open_flags(),
                dir_fd=self.parent_handle,
            )
            try:
                descriptor = os.open(name, flags, 0o600, dir_fd=child)
                try:
                    os.write(descriptor, content.encode("utf-8"))
                finally:
                    os.close(descriptor)
            finally:
                os.close(child)

        self.mutate(write_relative)

    def symlink(self, source: Path, destination: Path) -> None:
        destination = Path(destination)
        if destination.parent != self.parent:
            raise RuntimeError("symlink escapes protected destination namespace")
        if os.name == "nt":
            self.mutate(
                lambda: destination.symlink_to(source, target_is_directory=True)
            )
        else:
            self.mutate(
                lambda: os.symlink(
                    source,
                    destination.name,
                    target_is_directory=True,
                    dir_fd=self.parent_handle,
                )
            )

    def open_child(
        self,
        path: Path,
        *,
        rename_access: bool = False,
    ) -> _DestinationAncestorGuard:
        identity = _open_child_directory_identity(
            self.identities[-1],
            Path(path),
            self.platform,
            rename_access=rename_access,
        )
        return _DestinationAncestorGuard((identity,), self.platform)

    @staticmethod
    def _validate_relative(relative: PurePosixPath) -> None:
        if relative.is_absolute() or any(
            part in ("", ".", "..") for part in relative.parts
        ):
            raise RuntimeError("relative capability path is unsafe")

    @contextmanager
    def _windows_relative_parent(
        self,
        relative: PurePosixPath,
        *,
        create: bool,
    ):
        handles = []
        current = self.parent
        try:
            for component in relative.parts[:-1]:
                current /= component
                if create:
                    try:
                        current.mkdir()
                    except FileExistsError:
                        pass
                if _platform_is_link_or_reparse(self.platform, current):
                    raise RuntimeError(f"unsafe staging directory is linked: {current}")
                handle, _device, _inode = _open_windows_directory(current)
                handles.append(handle)
                if _platform_is_link_or_reparse(self.platform, current):
                    raise RuntimeError(f"unsafe staging directory is linked: {current}")
            yield current / relative.name
        finally:
            for handle in reversed(handles):
                _close_directory_handle(handle)

    def write_relative_bytes(self, relative: PurePosixPath, content: bytes) -> None:
        self._validate_relative(relative)
        if os.name == "nt":
            with self._windows_relative_parent(relative, create=True) as destination:
                handle = _open_windows_regular_file(
                    destination,
                    desired_access=0x40000000,  # GENERIC_WRITE
                    creation_disposition=1,  # CREATE_NEW
                )
                try:
                    _write_windows_handle(handle, content)
                finally:
                    _close_directory_handle(handle)
            return
        current_fd = os.dup(self.parent_handle)
        try:
            for component in relative.parts[:-1]:
                try:
                    os.mkdir(component, dir_fd=current_fd)
                except FileExistsError:
                    pass
                child_fd = os.open(
                    component,
                    _posix_directory_open_flags(),
                    dir_fd=current_fd,
                )
                os.close(current_fd)
                current_fd = child_fd
            descriptor = os.open(
                relative.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
                dir_fd=current_fd,
            )
            try:
                view = memoryview(content)
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
            finally:
                os.close(descriptor)
        finally:
            os.close(current_fd)

    def read_relative_bytes(self, relative: PurePosixPath) -> bytes:
        self._validate_relative(relative)
        if os.name == "nt":
            with self._windows_relative_parent(relative, create=False) as source:
                handle = _open_windows_regular_file(
                    source,
                    desired_access=0x80000000,  # GENERIC_READ
                    creation_disposition=3,  # OPEN_EXISTING
                )
                try:
                    return _read_windows_handle(handle)
                finally:
                    _close_directory_handle(handle)
        current_fd = os.dup(self.parent_handle)
        try:
            for component in relative.parts[:-1]:
                child_fd = os.open(
                    component,
                    _posix_directory_open_flags(),
                    dir_fd=current_fd,
                )
                os.close(current_fd)
                current_fd = child_fd
            descriptor = os.open(relative.name, os.O_RDONLY, dir_fd=current_fd)
            try:
                chunks = []
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        return b"".join(chunks)
                    chunks.append(chunk)
            finally:
                os.close(descriptor)
        finally:
            os.close(current_fd)

    def relative_files(self) -> set[str]:
        if os.name == "nt":
            def collect(directory: Path, prefix: PurePosixPath) -> set[str]:
                result = set()
                for name in os.listdir(directory):
                    path = directory / name
                    if _platform_is_link_or_reparse(self.platform, path):
                        raise RuntimeError(f"unsafe staged entry is linked: {path}")
                    metadata = path.lstat()
                    relative = prefix / name
                    if stat.S_ISDIR(metadata.st_mode):
                        handle, _device, _inode = _open_windows_directory(path)
                        try:
                            result.update(collect(path, relative))
                        finally:
                            _close_directory_handle(handle)
                        continue
                    handle = _open_windows_regular_file(
                        path,
                        desired_access=0x80000000,  # GENERIC_READ
                        creation_disposition=3,  # OPEN_EXISTING
                    )
                    _close_directory_handle(handle)
                    result.add(relative.as_posix())
                return result

            return collect(self.parent, PurePosixPath())

        def collect(directory_fd: int, prefix: PurePosixPath) -> set[str]:
            result: set[str] = set()
            for name in os.listdir(directory_fd):
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                relative = prefix / name
                if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                    child_fd = os.open(
                        name,
                        _posix_directory_open_flags(),
                        dir_fd=directory_fd,
                    )
                    try:
                        result.update(collect(child_fd, relative))
                    finally:
                        os.close(child_fd)
                else:
                    result.add(relative.as_posix())
            return result

        return collect(self.parent_handle, PurePosixPath())

    def remove(self, path: Path) -> None:
        path = Path(path)
        if path.parent != self.parent:
            raise RuntimeError("remove escapes protected destination namespace")
        if os.name == "nt":
            if _platform_is_link_or_reparse(self.platform, path):
                raise RuntimeError(f"refusing to remove linked transaction entry: {path}")
            self.mutate(lambda: remove_path(path))
        else:
            self.mutate(lambda: _remove_at(self.parent_handle, path.name))


def _remove_at(parent_fd: int, name: str) -> None:
    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
        flags = _posix_directory_open_flags()
        child_fd = os.open(name, flags, dir_fd=parent_fd)
        try:
            for child_name in os.listdir(child_fd):
                _remove_at(child_fd, child_name)
        finally:
            os.close(child_fd)
        os.rmdir(name, dir_fd=parent_fd)
    else:
        os.unlink(name, dir_fd=parent_fd)


def _guard_for_paths(paths: list[Path], platform=None) -> _DestinationAncestorGuard:
    identities: list[_DirectoryIdentity] = []
    try:
        for index, path in enumerate(paths):
            if index == 0:
                identities.append(_open_directory_identity(path, platform))
            else:
                identities.append(
                    _open_child_directory_identity(identities[-1], path, platform)
                )
    except BaseException:
        _DestinationAncestorGuard(tuple(identities), platform).close()
        raise
    return _DestinationAncestorGuard(tuple(identities), platform)


def _ensure_safe_directory_chain(
    target: Path,
    relative: Path,
    platform=None,
) -> Path:
    target = Path(os.path.abspath(target))
    missing: list[Path] = []
    existing = target
    while not path_present(existing):
        if existing == existing.parent:
            raise RuntimeError(f"cannot find a trusted parent for target: {target}")
        missing.append(existing)
        existing = existing.parent
    guard = _capture_destination_guard(existing, platform)
    try:
        # Keep one capability chain alive from the trusted existing anchor to
        # the final skills directory.  Closing and reopening by full path here
        # would reintroduce a window in which an ancestor could be replaced by
        # a link between two component opens.
        for directory in reversed(missing):
            guard.mkdir(directory)
            identity = _open_child_directory_identity(
                guard.identities[-1],
                directory,
                platform,
            )
            guard.identities += (identity,)

        if guard.parent != target:
            raise RuntimeError("destination capability did not reach target root")

        current = target
        for component in relative.parts:
            current = current / component
            if not guard.entry_present(current):
                guard.mkdir(current)
            identity = _open_child_directory_identity(
                guard.identities[-1],
                current,
                platform,
            )
            guard.identities += (identity,)
        return current
    finally:
        guard.close()


def _capture_destination_guard(
    destination_parent: Path,
    platform=None,
    *,
    trusted_root: Path | None = None,
) -> _DestinationAncestorGuard:
    parent = Path(os.path.abspath(destination_parent))
    if trusted_root is None:
        paths = list(reversed((parent, *parent.parents)))
    else:
        root = Path(os.path.abspath(trusted_root))
        try:
            relative = parent.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("destination escapes its trusted target root") from exc
        paths = [root]
        current = root
        for component in relative.parts:
            current = current / component
            paths.append(current)
    return _guard_for_paths(paths, platform)


def _payload_files(root: Path) -> set[str]:
    if _is_link_or_reparse(root):
        raise RuntimeError(f"release payload root is a symlink or reparse point: {root}")
    files: set[str] = set()
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*directory_names, *file_names):
            candidate = current_path / name
            if _is_link_or_reparse(candidate):
                raise RuntimeError(
                    f"release payload contains a symlink or reparse point: {candidate}"
                )
        for name in file_names:
            relative = (current_path / name).relative_to(root)
            posix = PurePosixPath(*relative.parts)
            if posix.as_posix() == RELEASE_MANIFEST_NAME:
                continue
            if _is_ignored_runtime_artifact(posix):
                continue
            files.add(posix.as_posix())
    return files


def verify_release_payload(root: Path, manifest: ReleaseManifest) -> None:
    manifest_file = root / RELEASE_MANIFEST_NAME
    if not manifest_file.is_file() or _is_link_or_reparse(manifest_file):
        raise RuntimeError(f"release manifest is missing or linked: {manifest_file}")
    declared = {entry.path for entry in manifest.files}
    actual = _payload_files(root)
    missing = sorted(declared - actual)
    extra = sorted(actual - declared)
    if missing or extra:
        raise RuntimeError(
            "release payload file-set drift: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )
    for entry in manifest.files:
        candidate = root.joinpath(*PurePosixPath(entry.path).parts)
        if not candidate.is_file() or _is_link_or_reparse(candidate):
            raise RuntimeError(f"manifest file is missing or linked: {entry.path}")
        actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_digest != entry.sha256:
            raise RuntimeError(
                f"release payload hash mismatch for {entry.path}: "
                f"expected {entry.sha256}, got {actual_digest}"
            )


def build_release_manifest(
    skill_root: Path,
    release_version: str,
    paths: tuple[str, ...] | list[str] | None = None,
) -> ReleaseManifest:
    parse_version_tuple(release_version)
    actual = _payload_files(skill_root)
    selected = sorted(actual if paths is None else paths)
    if set(selected) != actual or len(selected) != len(set(selected)):
        raise RuntimeError(
            "release boundary differs from the eligible source payload: "
            f"missing={sorted(actual - set(selected)) or 'none'}, "
            f"extra={sorted(set(selected) - actual) or 'none'}"
        )
    files = tuple(
        ReleaseFile(
            path=_canonical_manifest_path(relative),
            sha256=hashlib.sha256(
                skill_root.joinpath(*PurePosixPath(relative).parts).read_bytes()
            ).hexdigest(),
        )
        for relative in selected
    )
    return ReleaseManifest(
        format_version=RELEASE_MANIFEST_FORMAT_VERSION,
        release_version=release_version,
        files=files,
    )


def release_manifest_bytes(manifest: ReleaseManifest) -> bytes:
    document = {
        "format_version": manifest.format_version,
        "release_version": manifest.release_version,
        "files": [
            {"path": entry.path, "sha256": entry.sha256}
            for entry in manifest.files
        ],
    }
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_release_manifest(skill_root: Path, manifest: ReleaseManifest) -> Path:
    destination = skill_root / RELEASE_MANIFEST_NAME
    destination.write_bytes(release_manifest_bytes(manifest))
    return destination


def installed_payload_complete(destination: Path) -> bool:
    return all((destination / item).exists() for item in SKILL_PAYLOAD_ITEMS) and all(
        (destination / required_file).is_file()
        for required_file in SKILL_PAYLOAD_REQUIRED_FILES
    )


def should_deploy(
    source_version: str,
    destination: Path,
    source_manifest: ReleaseManifest | None = None,
) -> tuple[bool, str]:
    installed_version = read_skill_version(destination / "SKILL.md")
    if installed_version is None:
        return True, "installed_skill_or_version_missing"
    if not installed_payload_complete(destination):
        return True, "installed_payload_incomplete"
    if parse_version_tuple(installed_version) < parse_version_tuple(source_version):
        return True, "installed_version_is_older"
    if parse_version_tuple(installed_version) == parse_version_tuple(source_version):
        if source_manifest is not None:
            try:
                installed_manifest = read_release_manifest(destination)
                if installed_manifest != source_manifest:
                    return True, "installed_payload_drift"
                verify_release_payload(destination, installed_manifest)
            except RuntimeError:
                return True, "installed_payload_drift"
    return False, "installed_version_is_current_or_newer"


# Windows transiently locks freshly-created/copied directory trees — antivirus,
# Defender, and the Search indexer open handles for a few hundred milliseconds —
# and rmtree/rename then fail with WinError 5 (access denied) or 32 (sharing
# violation); a just-deleted directory name can also linger in a pending-delete
# state, so renaming onto it fails until the FS settles. Retrying with a short
# backoff clears these races without masking a genuine, persistent failure.
_FS_RETRY_ATTEMPTS = 10
_FS_RETRY_DELAY_S = 0.1
_DEPLOYMENT_LOCK_TIMEOUT_S = 10.0
_DEPLOYMENT_LOCK_STALE_S = 300.0


def _is_transient_windows_lock(exc: OSError) -> bool:
    """True for the transient Windows FS-lock errors worth retrying.

    Scoped to Windows winerror codes so non-Windows behavior is unchanged and a
    real, persistent error on any platform still surfaces promptly.
    WinError 5 = ERROR_ACCESS_DENIED, 32 = ERROR_SHARING_VIOLATION,
    145 = ERROR_DIR_NOT_EMPTY (rmtree mid-race).
    """
    return sys.platform == "win32" and getattr(exc, "winerror", None) in (5, 32, 145)


def _retry_fs(operation) -> None:
    """Run a filesystem mutation, retrying transient Windows lock errors.

    Re-raises immediately for any non-transient error and re-raises the last
    error once the attempt budget is exhausted, so a genuine failure is never
    swallowed.
    """
    for attempt in range(_FS_RETRY_ATTEMPTS):
        try:
            operation()
            return
        except OSError as exc:
            if not _is_transient_windows_lock(exc) or attempt == _FS_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_FS_RETRY_DELAY_S * (attempt + 1))


def path_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def transaction_path(destination: Path, role: str) -> Path:
    return destination.parent / f".{destination.name}.{role}.{uuid.uuid4().hex}"


@contextmanager
def deployment_lock(
    destination: Path,
    *,
    platform=None,
    guard: _DestinationAncestorGuard | None = None,
):
    parent = destination.parent
    guard = guard or _capture_destination_guard(parent, platform)
    guard.verify()
    lock = parent / f".{destination.name}.deploy.lock"
    deadline = time.monotonic() + _DEPLOYMENT_LOCK_TIMEOUT_S
    owned_lock: _DirectoryIdentity | None = None
    owned_lock_guard: _DestinationAncestorGuard | None = None

    while True:
        try:
            guard.mkdir(lock, mutation_kind="lock")
            owned_lock = guard.entry_identity(lock)
            owned_lock_guard = guard.open_child(lock)
            owned_lock_guard.__enter__()
            try:
                owned_lock_guard._atomic_mutation(
                    "lock-owner",
                    lambda: owned_lock_guard.write_relative_bytes(
                        PurePosixPath("owner.txt"),
                        f"pid={os.getpid()}\nstarted={time.time():.6f}\n".encode(
                            "utf-8"
                        ),
                    ),
                )
            except BaseException:
                owned_lock_guard.close()
                if guard.entry_present(lock):
                    guard.remove(lock)
                raise
            guard.verify()
            if guard.entry_identity(lock) != owned_lock:
                raise RuntimeError("deployment lock identity changed during acquisition")
            break
        except FileExistsError:
            guard.verify()
            lock_identity = guard.entry_identity(lock)
            try:
                stale = (
                    time.time() - guard.entry_metadata(lock).st_mtime
                    > _DEPLOYMENT_LOCK_STALE_S
                )
            except OSError:
                stale = False
            if stale:
                guard.verify()
                if guard.entry_identity(lock) != lock_identity:
                    raise RuntimeError("stale deployment lock identity changed")
                guard.remove(lock)
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"another deployment is already updating {destination}"
                )
            time.sleep(_FS_RETRY_DELAY_S)

    try:
        yield
    finally:
        if owned_lock_guard is not None:
            owned_lock_guard.close()
        guard.verify()
        if guard.entry_present(lock):
            if owned_lock is None or guard.entry_identity(lock) != owned_lock:
                raise RuntimeError("refusing to remove a replaced deployment lock")
            guard.remove(lock)


def recover_interrupted_publish(
    destination: Path,
    guard: _DestinationAncestorGuard,
) -> None:
    if guard.entry_present(destination):
        return

    parent = destination.parent
    legacy_previous = parent / f".{destination.name}.previous"
    names = guard.entry_names()
    candidates = []
    if legacy_previous.name in names:
        candidates.append(legacy_previous)
    candidates.extend(
        parent / name
        for name in names
        if name.startswith(f".{destination.name}.previous.")
    )
    if not candidates:
        return
    if len(candidates) != 1:
        raise RuntimeError(
            f"cannot recover interrupted deployment for {destination}; "
            f"multiple rollback candidates exist"
        )
    _retry_fs(lambda: guard.rename(candidates[0], destination))


def _populate_staging_payload(
    source_skill_root: Path,
    staging_guard: _DestinationAncestorGuard,
    manifest: ReleaseManifest | None,
) -> None:
    def populate() -> None:
        if manifest is None:
            for item in SKILL_PAYLOAD_ITEMS:
                source = source_skill_root / item
                if not source.exists():
                    raise FileNotFoundError(source)
                if source.is_file():
                    staging_guard.write_relative_bytes(
                        PurePosixPath(item),
                        source.read_bytes(),
                    )
                    continue
                for source_file in source.rglob("*"):
                    if source_file.is_file():
                        relative = PurePosixPath(
                            *source_file.relative_to(source_skill_root).parts
                        )
                        staging_guard.write_relative_bytes(
                            relative,
                            source_file.read_bytes(),
                        )
            return

        for entry in manifest.files:
            relative = PurePosixPath(entry.path)
            staging_guard.write_relative_bytes(
                relative,
                source_skill_root.joinpath(*relative.parts).read_bytes(),
            )
        staging_guard.write_relative_bytes(
            PurePosixPath(RELEASE_MANIFEST_NAME),
            (source_skill_root / RELEASE_MANIFEST_NAME).read_bytes(),
        )

    staging_guard._atomic_mutation("stage-copy", populate)

    if manifest is None:
        return
    expected_files = {entry.path for entry in manifest.files} | {
        RELEASE_MANIFEST_NAME
    }
    actual_files = staging_guard.relative_files()
    if actual_files != expected_files:
        raise RuntimeError(
            "staged Skill payload file-set drift: "
            f"missing={sorted(expected_files - actual_files) or 'none'}, "
            f"extra={sorted(actual_files - expected_files) or 'none'}"
        )
    for entry in manifest.files:
        digest = hashlib.sha256(
            staging_guard.read_relative_bytes(PurePosixPath(entry.path))
        ).hexdigest()
        if digest != entry.sha256:
            raise RuntimeError(f"staged Skill payload hash mismatch: {entry.path}")
    if staging_guard.read_relative_bytes(
        PurePosixPath(RELEASE_MANIFEST_NAME)
    ) != (source_skill_root / RELEASE_MANIFEST_NAME).read_bytes():
        raise RuntimeError("staged Skill release manifest drifted during copy")


def _staged_legacy_payload_complete(
    staging_guard: _DestinationAncestorGuard,
) -> bool:
    files = staging_guard.relative_files()
    required = {path.as_posix() for path in SKILL_PAYLOAD_REQUIRED_FILES}
    if not required.issubset(files):
        return False
    return all(
        item in files or any(path.startswith(f"{item}/") for path in files)
        for item in SKILL_PAYLOAD_ITEMS
    )


def copy_released_payload(
    source_skill_root: Path,
    destination: Path,
    manifest: ReleaseManifest | None = None,
    *,
    platform=None,
    trusted_root: Path | None = None,
) -> None:
    if manifest is not None:
        verify_release_payload(source_skill_root, manifest)
    destination = Path(os.path.abspath(destination))
    guard = _capture_destination_guard(
        destination.parent,
        platform,
        trusted_root=trusted_root,
    )
    with guard, deployment_lock(destination, platform=platform, guard=guard):
        guard.verify()
        recover_interrupted_publish(destination, guard)
        staging = transaction_path(destination, "deploying")
        previous = transaction_path(destination, "previous")
        guard.mkdir(staging, mutation_kind="staging")
        staging_guard = guard.open_child(staging, rename_access=True)
        staging_guard.__enter__()

        moved_previous = False
        try:
            _populate_staging_payload(source_skill_root, staging_guard, manifest)
            if manifest is None and not _staged_legacy_payload_complete(staging_guard):
                raise RuntimeError(
                    f"staged Skill payload is incomplete: {source_skill_root}"
                )

            if guard.entry_present(destination):
                _retry_fs(lambda: guard.rename(destination, previous))
                moved_previous = True
            if os.name == "nt" and manifest is not None:
                guard._atomic_mutation(
                    "publish",
                    lambda: _rename_windows_directory_handle(
                        staging_guard.parent_handle,
                        destination,
                    ),
                )
            else:
                _retry_fs(
                    lambda: guard.rename(
                        staging,
                        destination,
                        mutation_kind="publish",
                    )
                )
        except BaseException:
            staging_guard.close()
            if (
                moved_previous
                and guard.entry_present(previous)
                and not guard.entry_present(destination)
            ):
                _retry_fs(lambda: guard.rename(previous, destination))
            if guard.entry_present(staging):
                guard.remove(staging)
            raise
        staging_guard.close()
        if guard.entry_present(previous):
            guard.remove(previous)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        _retry_fs(path.unlink)
    elif path.exists():
        _retry_fs(lambda: shutil.rmtree(path))


def ensure_link(source: Path, destination: Path, *, platform=None) -> str:
    destination = Path(os.path.abspath(destination))
    guard = _capture_destination_guard(destination.parent, platform)
    source = source.resolve()
    if destination.exists() and destination.resolve() == source:
        return "installed_link_is_current"
    with guard, deployment_lock(destination, platform=platform, guard=guard):
        if destination.exists() and destination.resolve() == source:
            return "installed_link_is_current"
        candidate = transaction_path(destination, "linking")
        previous = transaction_path(destination, "previous")
        moved_previous = False
        try:
            guard.symlink(source, candidate)
            if guard.entry_present(destination):
                _retry_fs(lambda: guard.rename(destination, previous))
                moved_previous = True
            _retry_fs(lambda: guard.rename(candidate, destination))
        except OSError as exc:
            if (
                moved_previous
                and guard.entry_present(previous)
                and not guard.entry_present(destination)
            ):
                _retry_fs(lambda: guard.rename(previous, destination))
            if guard.entry_present(candidate):
                guard.remove(candidate)
            message = "failed to create directory symlink"
            if sys.platform == "win32":
                message += "; enable Developer Mode or run from an elevated shell"
            raise RuntimeError(message) from exc
        if guard.entry_present(previous):
            guard.remove(previous)
        return "symlink_to_canonical_skill"


def deploy_canonical(repo_root: Path, target_project: Path, *, platform=None) -> DeployResult:
    repo_root = repo_root.resolve()
    source_skill_root = repo_root / SKILL_NAME
    if not source_skill_root.is_dir():
        raise RuntimeError(f"source skill not found: {source_skill_root}")

    source_version = require_consistent_project_versions(read_project_versions(repo_root))
    source_manifest = read_release_manifest(source_skill_root)
    verify_release_payload(source_skill_root, source_manifest)
    skills_dir = resolve_agent_skills_dir(
        target_project,
        CANONICAL_AGENT,
        platform=platform,
    )
    destination = skills_dir / SKILL_NAME
    trusted_root = Path(os.path.abspath(target_project.expanduser()))
    transaction_guard = _capture_destination_guard(
        skills_dir,
        platform,
        trusted_root=trusted_root,
    )
    with transaction_guard:
        should_copy, reason = should_deploy(
            source_version,
            destination,
            source_manifest,
        )
        if not should_copy:
            return DeployResult(
                agent=CANONICAL_AGENT,
                action="skipped",
                version=source_version,
                destination=destination,
                reason=reason,
            )

        copy_released_payload(
            source_skill_root,
            destination,
            source_manifest,
            platform=platform,
            trusted_root=trusted_root,
        )
    return DeployResult(
        agent=CANONICAL_AGENT,
        action="deployed",
        version=source_version,
        destination=destination,
        reason=reason,
    )


def deploy_one(
    repo_root: Path,
    target_project: Path,
    agent: str,
    *,
    platform=None,
) -> DeployResult:
    agent = normalize_agents((agent,))[0]
    canonical_result = deploy_canonical(repo_root, target_project, platform=platform)
    if agent == CANONICAL_AGENT:
        return canonical_result

    destination = (
        resolve_agent_skills_dir(target_project, agent, platform=platform) / SKILL_NAME
    )
    reason = ensure_link(canonical_result.destination, destination, platform=platform)
    return DeployResult(
        agent=agent,
        action="skipped" if reason == "installed_link_is_current" else "linked",
        version=canonical_result.version,
        destination=destination,
        reason=reason,
    )


def deploy(
    repo_root: Path,
    target_project: Path,
    agents: tuple[str, ...] | list[str] = ("both",),
    *,
    platform=None,
) -> tuple[DeployResult, ...]:
    return tuple(
        deploy_one(repo_root, target_project, agent, platform=platform)
        for agent in normalize_agents(agents)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy the RTD CfgFile CLI companion skill into project-local "
            "Codex and Claude Code skill indexes."
        )
    )
    parser.add_argument("target", type=Path, help="target project directory")
    parser.add_argument(
        "--agent",
        choices=(*SUPPORTED_AGENTS, "both"),
        default="both",
        help=(
            "agent skill index to deploy: codex -> <target>/.agents/skills, "
            "claude -> <target>/.claude/skills, both -> both indexes"
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="source repository root; defaults to this script's repository",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = deploy(args.repo_root, args.target, agents=(args.agent,))
    for result in results:
        if result.action == "deployed":
            print(
                f"deployed {SKILL_NAME} {result.version} for {result.agent} "
                f"to {result.destination} ({result.reason})"
            )
        elif result.action == "linked":
            print(
                f"linked {SKILL_NAME} {result.version} for {result.agent} "
                f"to {result.destination} ({result.reason})"
            )
        else:
            print(
                f"skipped {SKILL_NAME} {result.version} for {result.agent} "
                f"at {result.destination} ({result.reason})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
