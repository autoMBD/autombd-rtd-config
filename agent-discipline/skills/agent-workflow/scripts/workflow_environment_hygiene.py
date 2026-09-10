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
# File:        workflow_environment_hygiene.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Exact source/evidence snapshots and scoped cleanup operations.
# =================================================================================

from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Sequence

from workflow_environment_io import (EnvironmentError, fields, version, strings, root_path, relative_path,
    no_links, linked, inside, fail, sha256, digest, git, source_state, validate_bindings, inspect_checkout)


def _ignored(root: Path, name: str) -> bool:
    try:
        return bool(git(root, "check-ignore", "--", name))
    except EnvironmentError:
        return False


def _inventory(root: Path, scopes: list[str]) -> dict:
    inventory = {}
    for name in scopes:
        path = root / relative_path(name)
        no_links(path)
        if path.is_file():
            inventory[name] = sha256(path.read_bytes())
        elif path.is_dir():
            for directory, dirs, files in os.walk(path, followlinks=False):
                for child in (*dirs, *files):
                    if linked(Path(directory) / child):
                        fail("PATH_BOUNDARY", "Evidence scope contains a linked path.")
                for child in files:
                    item = Path(directory) / child
                    inventory[item.relative_to(root).as_posix()] = sha256(item.read_bytes())
        else:
            fail("STALE_IDENTITY", "Referenced evidence or scope is missing.")
    return dict(sorted(inventory.items()))


def _bound_root(root: Path, bindings: dict) -> Path:
    validate_bindings(bindings)
    root = root_path(root)
    if str(root) != bindings["checkout_root"]:
        fail("STALE_IDENTITY", "Evidence checkout differs from its bound root.")
    inspect_checkout(root, expected_head=bindings["head"])
    return root


def snapshot_evidence(root: Path, paths: Sequence[str], *, bindings: dict) -> dict:
    root = _bound_root(root, bindings)
    names = strings(paths, empty=False)
    scopes = set()
    for name in names:
        rel = relative_path(name)
        path = root / rel
        no_links(path)
        if not path.exists():
            fail("STALE_IDENTITY", "Referenced evidence is missing.")
        # Sibling discovery is confined to ignored task evidence directories.
        # A bound source file never expands the scope to the whole checkout.
        scope = rel.parent if path.is_file() and _ignored(root, name) else rel
        if scope == Path("."):
            fail("PATH_BOUNDARY", "Evidence scope must be narrower than the checkout.")
        scopes.add(scope.as_posix())
    result = {"version": 1, "bindings": dict(bindings), "source": source_state(root),
              "scopes": sorted(scopes), "files": _inventory(root, sorted(scopes))}
    result["snapshot_sha256"] = digest(result)
    return result


def verify_evidence(root: Path, snapshot: dict, *, bindings: dict, allowed_new_paths: Sequence[str] = ()) -> None:
    fields(snapshot, {"version", "bindings", "source", "scopes", "files", "snapshot_sha256"})
    version(snapshot["version"])
    raw = {k: v for k, v in snapshot.items() if k != "snapshot_sha256"}
    if digest(raw) != snapshot["snapshot_sha256"]:
        fail("STALE_IDENTITY", "Evidence snapshot identity was changed.")
    root = _bound_root(root, bindings)
    if bindings != snapshot["bindings"] or source_state(root) != snapshot["source"]:
        fail("STALE_IDENTITY", "Bound identity or Candidate source changed.")
    allowed = []
    for name in strings(allowed_new_paths):
        rel = relative_path(name, directory=True)
        no_links(root / rel)
        if not _ignored(root, rel.as_posix()):
            fail("PATH_BOUNDARY", "New evidence allowlist must contain only ignored paths.")
        allowed.append((rel.as_posix(), name.endswith("/") or (root / rel).is_dir()))
    scopes = strings(snapshot["scopes"], empty=False)
    current = _inventory(root, scopes)
    if not isinstance(snapshot["files"], dict):
        fail("INVALID_INPUT", "Malformed evidence inventory.")
    for name, expected in snapshot["files"].items():
        if current.get(name) != expected:
            fail("STALE_IDENTITY", "Referenced evidence bytes changed or disappeared.")
    for name in set(current) - set(snapshot["files"]):
        if not _ignored(root, name) or not any(name == base or directory and name.startswith(base + "/")
                                                for base, directory in allowed):
            fail("STALE_IDENTITY", "New task evidence is outside the explicit ignored allowlist.")


def cleanup_paths(root: Path, paths: Sequence[str], *, allowed_base: Path, protected_paths: Sequence[str] = (), dry_run: bool = True) -> dict:
    if type(dry_run) is not bool:
        fail("INVALID_INPUT", "dry_run must be boolean.")
    root = root_path(root)
    base = Path(allowed_base)
    no_links(base)
    base = base.resolve(strict=False)
    if not inside(base, root):
        fail("PATH_BOUNDARY", "Cleanup base must be strictly below the checkout.")
    relbase = base.relative_to(root).as_posix()
    if not (relbase.startswith("tests/.tmp/") or relbase == "tests/.tmp"
            or relbase.startswith(".agent-state/agent-loop/")):
        fail("PATH_BOUNDARY", "Cleanup is restricted to current-run temporary/evidence storage.")
    protected = []
    for name in strings(protected_paths):
        item = root / relative_path(name)
        no_links(item, include_leaf=False)
        protected.append(item)
    targets = []
    names = strings(paths)
    for name in names:
        target = root / relative_path(name)
        no_links(target, include_leaf=False)
        if not inside(target, base) or any(p == target or p.is_relative_to(target)
                                          or target.is_relative_to(p) for p in protected):
            fail("PATH_BOUNDARY", "Cleanup target is outside scope or protects bound evidence.")
        if ".git" in target.relative_to(root).parts:
            fail("PATH_BOUNDARY", "Git storage cannot be a cleanup target.")
        if not linked(target):
            no_links(target)
            if target.is_dir():
                # Do not enter nested repositories or follow descendant links.
                for directory, dirs, files in os.walk(target, followlinks=False):
                    if ".git" in dirs or ".git" in files:
                        fail("PATH_BOUNDARY", "Cleanup cannot remove a source checkout.")
                    dirs[:] = [d for d in dirs if not linked(Path(directory) / d)]
        if not _ignored(root, name):
            fail("PATH_BOUNDARY", "Cleanup target must be ignored current-run storage.")
        targets.append(target)
    if any(a != b and a.is_relative_to(b) for a in targets for b in targets):
        fail("PATH_BOUNDARY", "Cleanup targets must not overlap.")
    if not dry_run:
        for target in targets:
            if bool(getattr(target, "is_junction", lambda: False)()):
                target.rmdir()
            elif target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
    return {"version": 1, "status": "PLANNED" if dry_run else "CLEANED",
            "paths": [p.relative_to(root).as_posix() for p in targets]}
