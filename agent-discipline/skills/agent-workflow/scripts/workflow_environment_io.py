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
# File:        workflow_environment_io.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Portable identity, Git topology and safe path operations.
# =================================================================================

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from typing import Any

from structured_handoff_schema import canonical_bytes

PLATFORMS = ("codex", "claude", "opencode")
CAPABILITIES = ("filesystem-read", "filesystem-write", "git", "github", "agent-cli", "blackbox", "s32ds", "input-isolation")
ROLES = ("orchestrator", "explorer", "worker", "tester", "reviewer")
CONTEXTS = ("host", "sandbox", "connector")


class EnvironmentError(ValueError):
    """Safe public rejection; command output and credentials are never included."""

    def __init__(self, code: str, message: str, *, exit_code: int | None = None):
        self.code = code
        self.exit_code = (2 if code == "INVALID_INPUT" else 1) if exit_code is None else exit_code
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"version": 1, "status": "REJECTED", "code": self.code, "message": str(self)}


def fail(code: str, message: str, *, exit_code: int | None = None) -> None:
    raise EnvironmentError(code, message, exit_code=exit_code)


def canonical(value: Any) -> bytes:
    try:
        return canonical_bytes(value)
    except (ValueError, TypeError, UnicodeError):
        fail("INVALID_INPUT", "Expected finite UTF-8 JSON data.")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    return sha256(canonical(value))


def check_hash(value: Any, size: int = 64) -> None:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{" + str(size) + "}", value) is None:
        fail("INVALID_INPUT", f"Expected a lowercase {size}-digit hexadecimal identity.")


def fields(value: Any, required: set[str], optional: set[str] = frozenset()) -> None:
    if not isinstance(value, dict) or set(value) - required - optional or required - set(value):
        fail("INVALID_INPUT", "Object members do not match the versioned interface.")


def version(value: Any) -> None:
    if type(value) is not int or value != 1:
        fail("INVALID_INPUT", "Only record version 1 is supported.")


def strings(value: Any, *, choices=None, empty=True) -> list[str]:
    if not isinstance(value, (list, tuple)) or (not empty and not value):
        fail("INVALID_INPUT", "Expected an explicit sequence.")
    if any(not isinstance(x, str) or not x or "\x00" in x for x in value) or len(set(value)) != len(value):
        fail("INVALID_INPUT", "Expected unique nonempty strings.")
    if choices is not None and not set(value).issubset(choices):
        fail("INVALID_INPUT", "Unsupported selection.")
    return list(value)


def linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def absolute(path: Path) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        fail("PATH_BOUNDARY", "An absolute path without traversal is required.")
    return path


def no_links(path: Path, *, include_leaf=True) -> None:
    path = absolute(path)
    parts = (path, *path.parents) if include_leaf else tuple(path.parents)
    if any(linked(part) for part in parts):
        fail("PATH_BOUNDARY", "A path or ancestor is a symbolic link or junction.")


def root_path(root: Path) -> Path:
    root = absolute(root)
    no_links(root)
    try:
        if not root.is_dir():
            fail("PATH_BOUNDARY", "Checkout root must be an existing directory.")
        return root.resolve(strict=True)
    except OSError:
        fail("PATH_BOUNDARY", "Checkout root is unavailable.")


def relative_path(value: str, *, directory=False) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        fail("PATH_BOUNDARY", "Expected a safe slash-separated relative path.")
    cleaned = value.rstrip("/") if directory else value
    parts = cleaned.split("/")
    if any(p in ("", ".", "..") or ":" in p for p in parts) or PurePosixPath(cleaned).is_absolute():
        fail("PATH_BOUNDARY", "Relative path escapes its declared scope.")
    return Path(*parts)


def inside(path: Path, base: Path, *, same=False) -> bool:
    return (same or path != base) and path.is_relative_to(base)


def derived_target(source: Path, target: Path, allowed_base: Path) -> tuple[Path, Path]:
    source = root_path(source)
    target, base = absolute(target), absolute(allowed_base)
    no_links(base)
    no_links(target)
    target, base = target.resolve(strict=False), base.resolve(strict=False)
    if not inside(target, base) or target == source or source.is_relative_to(target) or base == source:
        fail("PATH_BOUNDARY", "Target is not a distinct checkout below the explicit derived base.")
    return target, base


def git(root: Path, *argv: str) -> str:
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    clean.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        result = subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(root), *argv],
                                env=clean, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        fail("CAPABILITY_UNAVAILABLE", "Noninteractive Git command is unavailable or exceeded its deadline.")
    if result.returncode != 0:
        fail("STALE_IDENTITY", "Git command rejected the requested checkout, ref or identity.")
    return result.stdout.decode("utf-8", errors="surrogateescape").rstrip("\r\n")


def validate_bindings(value: dict) -> None:
    fields(value, {"task_run", "governor", "workflow_blob", "contract_sha256", "checkout_root", "head", "candidate_sha256"})
    if not isinstance(value["task_run"], str) or not value["task_run"].strip() or "\x00" in value["task_run"]:
        fail("INVALID_INPUT", "task_run must be a nonempty identity.")
    for name in ("governor", "workflow_blob", "head"):
        check_hash(value[name], 40)
    check_hash(value["contract_sha256"])
    if value["candidate_sha256"] is not None:
        check_hash(value["candidate_sha256"], 40)
        if value["candidate_sha256"] != value["head"]:
            fail("STALE_IDENTITY", "Candidate and checkout HEAD must identify the same source.")
    if not isinstance(value["checkout_root"], str):
        fail("INVALID_INPUT", "checkout_root must be a canonical absolute locator.")
    path = Path(value["checkout_root"])
    if not path.is_absolute() or ".." in path.parts or path != path.resolve(strict=False):
        fail("INVALID_INPUT", "checkout_root must be a canonical absolute locator.")


def inspect_checkout(root: Path, *, expected_head: str) -> dict:
    check_hash(expected_head, 40)
    root = root_path(root)
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        fail("PATH_BOUNDARY", "Requested root is not the Git checkout top level.")
    head = git(root, "rev-parse", "HEAD")
    if head != expected_head:
        fail("STALE_IDENTITY", "Checkout HEAD differs from the requested identity.")
    git_dir = Path(git(root, "rev-parse", "--absolute-git-dir")).resolve()
    raw_common = Path(git(root, "rev-parse", "--git-common-dir"))
    common = (raw_common if raw_common.is_absolute() else root / raw_common).resolve()
    worktree = git_dir != common or (root / ".git").is_file()
    objects = common / "objects"
    shared = worktree or linked(root / ".git") or not common.is_relative_to(root) or linked(objects) or (objects / "info/alternates").exists() or (objects / "info/http-alternates").exists()
    if objects.is_dir() and not shared:
        for directory, dirs, files in os.walk(objects, followlinks=False):
            if any(linked(Path(directory) / name) for name in (*dirs, *files)):
                shared = True
                break
            if any((Path(directory) / name).stat().st_nlink > 1 for name in files):
                shared = True
                break
    refs = git(root, "for-each-ref", "--format=%(refname)").splitlines()
    independent = (not shared and not worktree and git_dir == root / ".git"
                   and len(refs) == 1 and refs[0].startswith("refs/heads/")
                   and not git(root, "remote"))
    if independent:
        # A deleted private ref can leave readable disconnected objects behind.
        # Exclude reflogs as roots: their presence must not hide that residual data.
        independent = not bool(git(root, "fsck", "--no-reflogs", "--unreachable", "--no-dangling"))
    return {"root": str(root), "head": head, "git_dir": str(git_dir), "common_dir": str(common),
            "checkout_kind": "worktree" if worktree else "clone", "shared_objects": bool(shared),
            "ref_isolated": bool(independent), "os_read_isolated": False}


def create_isolated_checkout(source_root: Path, target_root: Path, *, allowed_target_base: Path,
                             branch: str, expected_source_head: str) -> dict:
    check_hash(expected_source_head, 40)
    if not isinstance(branch, str) or not branch or branch.startswith("-") or "\x00" in branch:
        fail("INVALID_INPUT", "An explicit branch name is required.")
    source = root_path(source_root)
    target, base = derived_target(source, target_root, allowed_target_base)
    if target.exists() or linked(target):
        fail("PATH_BOUNDARY", "An existing target is never overwritten.")
    inspect_checkout(source, expected_head=expected_source_head)
    git(source, "check-ref-format", "refs/heads/" + branch)
    git(source, "check-ref-format", "--branch", branch)
    # All semantic/path validation precedes the first mutation. Fetching only
    # one exact shallow commit avoids copying unrelated source objects or refs.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    try:
        git(target, "init", "--initial-branch=" + branch)
        git(target, "-c", "protocol.file.allow=always", "fetch", "--no-tags", "--depth=1",
            str(source), expected_source_head)
        git(target, "checkout", "-B", branch, expected_source_head)
        fetch_head = target / ".git/FETCH_HEAD"
        if fetch_head.exists():
            fetch_head.unlink()
        inspect_checkout(source, expected_head=expected_source_head)
        return inspect_checkout(target, expected_head=expected_source_head)
    except EnvironmentError:
        # Preserve partial output for inspection; never delete a newly created
        # checkout automatically after an execution failure.
        raise


def source_state(root: Path) -> dict:
    tracked = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\x00")
    hashes = {}
    for name in sorted(set(tracked) - {""}):
        path = root / relative_path(name)
        if linked(path):
            hashes[name] = {"link": os.readlink(path)}
        elif path.is_file():
            hashes[name] = {"sha256": sha256(path.read_bytes())}
        else:
            hashes[name] = {"missing": True}
    return {"head": git(root, "rev-parse", "HEAD"), "tree": git(root, "rev-parse", "HEAD^{tree}"),
            "index": git(root, "ls-files", "--stage", "-z"),
            "status": git(root, "status", "--porcelain=v1", "--untracked-files=all", "-z"),
            "files": hashes}


def read_json(path: Path) -> Any:
    def pairs(entries):
        value = {}
        for key, item in entries:
            if key in value:
                fail("INVALID_INPUT", "Duplicate JSON object member.")
            value[key] = item
        return value
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: fail("INVALID_INPUT", "Non-finite JSON value."))
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, EnvironmentError):
            raise
        fail("INVALID_INPUT", "JSON input is unreadable or malformed.")
