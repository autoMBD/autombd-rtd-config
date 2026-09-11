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
# File:        prevalidate_cleanup.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Independent known-good and bad controls for Test prevalidation.
# =================================================================================

"""Authoring-only controls. This runner never evaluates a Candidate as production.

The known-good wrapper adds an independent index preflight to the real baseline
cleanup implementation. Every operation still exercises a real Git repository
and filesystem. Mutants deliberately break one rule to prove discrimination.
The frozen Candidate commands invoke pytest directly, without this runner.
"""

from __future__ import annotations

import argparse
import functools
import os
from pathlib import Path, PurePosixPath
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleanup_support as s


def control_api(base, mode):
    def indexed(root):
        top = s.git(root, "rev-parse", "--show-toplevel", check=False)
        if top.returncode or Path(os.fsdecode(top.stdout.rstrip(b"\r\n"))).resolve() != root.resolve():
            raise base.EnvironmentError("STALE_IDENTITY", "Reference could not bind the checkout.")
        result = s.git(root, "ls-files", "--cached", "-z", check=False)
        if result.returncode:
            raise base.EnvironmentError("STALE_IDENTITY", "Reference real index query failed.")
        raw = result.stdout.decode("ascii", errors="ignore") if mode == "unicode-loss" else os.fsdecode(result.stdout)
        return [name for name in raw.split("\0") if name]

    @functools.wraps(base.cleanup_paths)
    def cleanup(root, paths, *, allowed_base, protected_paths=(), dry_run=True):
        if mode == "omit-index" or type(dry_run) is not bool:
            return base.cleanup_paths(root, paths, allowed_base=allowed_base,
                                      protected_paths=protected_paths, dry_run=dry_run)
        if mode == "reject-all":
            raise base.EnvironmentError("PATH_BOUNDARY", "Controlled invalid blanket rejection.")
        if mode == "early-delete" and not dry_run and len(paths) > 1:
            safe = control_api(base, "known-good")
            for name in paths:
                safe.cleanup_paths(root, [name], allowed_base=allowed_base,
                                   protected_paths=protected_paths, dry_run=False)
            return {"version": 1, "status": "CLEANED", "paths": list(paths)}
        names = indexed(root)
        for target in paths:
            components = PurePosixPath(target).parts
            for tracked in names:
                parts = PurePosixPath(tracked).parts
                matches = parts[:len(components)] == components
                if mode == "prefix-match":
                    matches = tracked.startswith(target)
                if matches:
                    if mode == "rewrite-before-reject":
                        s.write(root / tracked, b"controlled forbidden rewrite")
                    raise base.EnvironmentError("PATH_BOUNDARY", "Reference index owns target content.")
        base.cleanup_paths(root, paths, allowed_base=allowed_base,
                           protected_paths=protected_paths, dry_run=True)
        if mode == "follow-leaf" and not dry_run:
            for name in paths:
                path = root / name
                if s.is_link(path):
                    destination = path.resolve()
                    assert destination.is_relative_to((s.ROOT / "tests/.tmp").resolve())
                    if destination.is_file():
                        destination.unlink()
                    elif destination.is_dir():
                        s.remove_tree(destination)
        return base.cleanup_paths(root, paths, allowed_base=allowed_base,
                                  protected_paths=protected_paths, dry_run=dry_run)
    return SimpleNamespace(cleanup_paths=cleanup, EnvironmentError=base.EnvironmentError)


class Controls:
    def __init__(self, mode):
        self.mode = mode

    @pytest.hookimpl(tryfirst=True)
    def pytest_fixture_setup(self, fixturedef, request):
        if fixturedef.argname == "cleanup_api":
            value = control_api(s.load_api(), self.mode)
            fixturedef.cached_result = (value, fixturedef.cache_key(request), None)
            return value
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", required=True, choices=[
        "known-good", "omit-index", "early-delete", "rewrite-before-reject",
        "prefix-match", "unicode-loss", "follow-leaf", "reject-all"])
    args, nodes = parser.parse_known_args()
    if nodes and nodes[0] == "--":
        nodes = nodes[1:]
    if not nodes:
        parser.error("Explicit owner test selection is required.")
    print("AUTHORING CONTROL: " + args.control + "; not production acceptance.", flush=True)
    return pytest.main(nodes, plugins=[Controls(args.control)])


if __name__ == "__main__":
    raise SystemExit(main())
