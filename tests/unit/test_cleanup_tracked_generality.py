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
# File:        test_cleanup_tracked_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Real-index cleanup source protection and boundary generality tests.
# =================================================================================

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_environment import EnvironmentError, cleanup_paths


def git(root, *args):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    clean.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    return subprocess.run(
        ["git", "--literal-pathspecs", "-c", "core.hooksPath=" + os.devnull,
         "-C", str(root), *args], env=clean, stdin=subprocess.DEVNULL,
        capture_output=True, check=True,
    ).stdout


def write(path, data=b"temporary bytes\x00\r\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def repo(tmp_path, *, ignored=True):
    assert tmp_path.resolve().is_relative_to(ROOT / "tests/.tmp")
    root = tmp_path / "r"
    root.mkdir()
    git(root, "init", "-b", "fixture")
    git(root, "config", "user.name", "Cleanup Generality")
    git(root, "config", "user.email", "cleanup@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.longpaths", "true")
    git(root, "config", "core.symlinks", "true")
    write(root / ".gitignore", b"tests/.tmp/\n.agent-state/\n" if ignored else b"")
    write(root / "source.txt", b"committed source\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture seed")
    return root


def source_identity(root):
    return (git(root, "rev-parse", "HEAD"), (root / ".git/index").read_bytes(),
            git(root, "ls-files", "--stage", "-z"))


def reject_unchanged(root, names, base, preserved, *, dry_run, code="PATH_BOUNDARY", **kwargs):
    before = [p.read_bytes() for p in preserved]
    identity = source_identity(root)
    with pytest.raises(EnvironmentError) as exc:
        cleanup_paths(root, names, allowed_base=base, dry_run=dry_run, **kwargs)
    assert exc.value.code == code
    assert exc.value.as_dict()["status"] == "REJECTED"
    assert [p.read_bytes() for p in preserved] == before
    assert source_identity(root) == identity


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("mode", ["staged", "committed", "before-ignore"])
@pytest.mark.parametrize("scope,folder,leaf", [
    ("tests/.tmp/r3", "set[6]", "deep/a [9].txt"),
    (".agent-state/agent-loop/r8", "空 格", "x/参数'7.txt"),
])
def test_indexed_descendant_rejects_complete_plan(tmp_path, dry_run, mode, scope, folder, leaf):
    root = repo(tmp_path, ignored=mode != "before-ignore")
    base = root / scope
    first = write(base / "ordinary")
    tracked = write(base / folder / leaf, b"indexed version\n")
    git(root, "add", "-f", "--", tracked.relative_to(root).as_posix())
    if mode != "staged":
        git(root, "commit", "-m", "tracked temporary-looking source")
    if mode == "before-ignore":
        write(root / ".gitignore", b"tests/.tmp/\n.agent-state/\n")
        git(root, "add", ".gitignore")
        git(root, "commit", "-m", "ignore after tracking")
    tracked.write_bytes(b"uncommitted version\x00\xff\r\n")
    reject_unchanged(root, [f"{scope}/ordinary", f"{scope}/{folder}"], base,
                     [first, tracked, root / "source.txt"], dry_run=dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
def test_missing_working_file_is_still_in_index(tmp_path, dry_run):
    root = repo(tmp_path)
    base = root / "tests/.tmp/r4"
    first = write(base / "ordinary")
    tracked = write(base / "gone/source")
    git(root, "add", "-f", "--", tracked.relative_to(root).as_posix())
    tracked.unlink()
    tracked.parent.rmdir()
    reject_unchanged(root, ["tests/.tmp/r4/ordinary", "tests/.tmp/r4/gone"], base,
                     [first], dry_run=dry_run)


@pytest.mark.parametrize("kind", ["file", "symlink"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_indexed_leaf_is_protected(tmp_path, kind, dry_run):
    root = repo(tmp_path)
    base = root / "tests/.tmp/r5"
    first = write(base / "ordinary")
    tracked = base / "leaf"
    if kind == "symlink":
        tracked.symlink_to(root / "source.txt")
    else:
        write(tracked)
    git(root, "add", "-f", "--", tracked.relative_to(root).as_posix())
    reject_unchanged(root, ["tests/.tmp/r5/ordinary", "tests/.tmp/r5/leaf"], base,
                     [first, tracked, root / "source.txt"], dry_run=dry_run)
    if kind == "symlink":
        assert tracked.is_symlink()


@pytest.mark.parametrize("scope", ["tests/.tmp/r6", ".agent-state/agent-loop/r9"])
def test_literal_similar_prefixes_and_untracked_temporary_content_remain_cleanable(tmp_path, scope):
    root = repo(tmp_path)
    base = root / scope
    protected = write(base / "logs[4]-source" / "keep")
    git(root, "add", "-f", "--", protected.relative_to(root).as_posix())
    temporary = write(base / "logs[4]" / "space ü.txt")
    leaf = write(base / "log")
    unrelated = write(base / "logs4" / "keep")
    identity = source_identity(root)
    names = [f"{scope}/logs[4]", f"{scope}/log"]
    assert cleanup_paths(root, names, allowed_base=base) == {
        "version": 1, "status": "PLANNED", "paths": names,
    }
    assert temporary.is_file() and leaf.is_file()
    assert cleanup_paths(root, names, allowed_base=base, dry_run=False) == {
        "version": 1, "status": "CLEANED", "paths": names,
    }
    assert not temporary.parent.exists() and not leaf.exists()
    assert protected.is_file() and unrelated.is_file()
    assert source_identity(root) == identity


@pytest.mark.parametrize("dry_run", [True, False])
def test_corrupt_index_fails_closed(tmp_path, dry_run):
    root = repo(tmp_path)
    base = root / "tests/.tmp/r7"
    first = write(base / "one")
    second = write(base / "two/file")
    index = root / ".git/index"
    index.write_bytes(b"unreadable index\x00")
    before = [p.read_bytes() for p in (first, second, index, root / ".git/HEAD")]
    with pytest.raises(EnvironmentError) as exc:
        cleanup_paths(root, ["tests/.tmp/r7/one", "tests/.tmp/r7/two"],
                      allowed_base=base, dry_run=dry_run)
    assert exc.value.as_dict()["status"] == "REJECTED"
    assert [p.read_bytes() for p in (first, second, index, root / ".git/HEAD")] == before


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("kind", ["file-link", "directory-link", "junction"])
def test_cleanup_removes_links_without_following_source_destination(tmp_path, nested, kind):
    if kind == "junction" and os.name != "nt":
        pytest.skip("junctions are a Windows filesystem capability")
    root = repo(tmp_path)
    base = root / "tests/.tmp/r10"
    base.mkdir(parents=True)
    destination = root if kind != "file-link" else root / "source.txt"
    link = base / "box/link" if nested else base / "link"
    link.parent.mkdir(parents=True, exist_ok=True)
    if kind == "junction":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(destination)],
                       check=True, capture_output=True)
        assert link.is_junction()
    else:
        link.symlink_to(destination, target_is_directory=kind == "directory-link")
    identity = source_identity(root)
    before = (root / "source.txt").read_bytes()
    target = link.parent if nested else link
    names = [target.relative_to(root).as_posix()]
    cleanup_paths(root, names, allowed_base=base)
    assert link.exists()
    cleanup_paths(root, names, allowed_base=base, dry_run=False)
    assert not target.exists() and not target.is_symlink()
    assert (root / "source.txt").read_bytes() == before
    assert source_identity(root) == identity


@pytest.mark.parametrize("boundary", ["escape", "base", "source-root", "git-storage",
    "nested-repo", "link-ancestor", "overlap", "protected-leaf", "protected-parent",
    "protected-link"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_existing_boundaries_reject_before_first_delete(tmp_path, boundary, dry_run):
    root = repo(tmp_path)
    base = root / "tests/.tmp/r11"
    ordinary = write(base / "ordinary")
    target = write(base / "box/item")
    names = ["tests/.tmp/r11/ordinary", "tests/.tmp/r11/box"]
    protected_paths = []
    if boundary == "escape":
        names[-1] = "tests/.tmp/r11/../outside"
    elif boundary == "base":
        names[-1] = "tests/.tmp/r11"
    elif boundary == "source-root":
        base = root
    elif boundary == "git-storage":
        write(base / ".git/state")
        names[-1] = "tests/.tmp/r11/.git/state"
    elif boundary == "nested-repo":
        write(base / "box/.git", b"gitdir: elsewhere\n")
    elif boundary == "link-ancestor":
        (base / "alias").symlink_to(base / "box", target_is_directory=True)
        names[-1] = "tests/.tmp/r11/alias/item"
    elif boundary == "overlap":
        names.append("tests/.tmp/r11/box/item")
    elif boundary == "protected-leaf":
        protected_paths = ["tests/.tmp/r11/box/item"]
    elif boundary == "protected-parent":
        protected_paths = ["tests/.tmp/r11"]
    elif boundary == "protected-link":
        (base / "alias").symlink_to(root / "source.txt")
        names[-1] = "tests/.tmp/r11/alias"
        protected_paths = [names[-1]]
    reject_unchanged(root, names, base, [ordinary, target, root / "source.txt"],
                     dry_run=dry_run, protected_paths=protected_paths)


@pytest.mark.skipif(os.name != "nt", reason="case aliases require a case-insensitive Windows checkout")
@pytest.mark.parametrize("dry_run", [True, False])
def test_windows_case_alias_cannot_hide_indexed_directory(tmp_path, dry_run):
    root = repo(tmp_path)
    git(root, "config", "core.ignorecase", "false")
    base = root / "tests/.tmp/r12"
    ordinary = write(base / "ordinary")
    tracked = write(base / "MiXeD/data")
    git(root, "add", "-f", "--", tracked.relative_to(root).as_posix())
    tracked.write_bytes(b"uncommitted case-sensitive index name")
    reject_unchanged(root, ["tests/.tmp/r12/ordinary", "tests/.tmp/r12/mixed"], base,
                     [ordinary, tracked], dry_run=dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
def test_index_query_unavailability_preserves_all_targets(tmp_path, monkeypatch, dry_run):
    import workflow_environment_io as environment_io

    root = repo(tmp_path)
    base = root / "tests/.tmp/r13"
    first = write(base / "one")
    second = write(base / "two/deep/file")
    real_run = subprocess.run

    def unavailable_index_query(argv, *args, **kwargs):
        if "ls-files" in argv and "--cached" in argv:
            raise OSError("injected unavailable Git inventory process")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(environment_io.subprocess, "run", unavailable_index_query)
    reject_unchanged(root, ["tests/.tmp/r13/one", "tests/.tmp/r13/two"], base,
                     [first, second], dry_run=dry_run, code="CAPABILITY_UNAVAILABLE")
