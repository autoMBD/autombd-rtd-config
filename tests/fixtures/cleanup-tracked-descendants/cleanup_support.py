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
# File:        cleanup_support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Real Git fixtures for independent cleanup source protection.
# =================================================================================

"""Real isolated Git/filesystem fixtures; no production fallback or canned results."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
(ROOT / "tests/.tmp").mkdir(parents=True, exist_ok=True)


def load_api():
    sys.path.insert(0, str(SCRIPTS))
    return importlib.import_module("workflow_environment")


def command(argv, cwd, *, check=True):
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                            stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=45, check=False)
    if check:
        assert result.returncode == 0, (argv, result.stderr.decode(errors="replace"))
    return result


def git(root, *args, check=True):
    return command(["git", "-c", "core.hooksPath=" + os.devnull,
                    "-C", root, *args], root, check=check)


def cleanup_scope_changes(root, base):
    """Account for the exact retained lessons in the authorized master merge."""
    result = git(root, "diff", "--name-only", "-z", base, "HEAD").stdout
    changed = {part.decode("utf-8") for part in result.split(b"\0") if part}
    lesson = "agent-discipline/agent-lessons-learned.md"
    # Exact tree entry from integration 9732081d7cc5c74091890850a4c4a3b0582f6c0d.
    retained = ("100644 blob 815ed5025b4310eab2a1ac01aa57d66647d437b3\t"
                + lesson + "\0").encode("utf-8")
    if git(root, "ls-tree", "-z", "HEAD", "--", lesson).stdout == retained:
        changed.discard(lesson)
    else:
        changed.add(lesson)
    return changed


def write(path, data=b"temporary\x00bytes\r\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


def is_link(path):
    return path.is_symlink() or path.is_junction()


def inventory(root):
    """Bytes, directories and link identities, including the actual Git store."""
    found = {}

    def walk(directory):
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            if is_link(path):
                found[name] = ("link", os.readlink(path))
            elif path.is_dir():
                found[name] = ("directory",)
                walk(path)
            else:
                found[name] = ("file", path.read_bytes())
    walk(root)
    return found


def remove_tree(path):
    path = path.resolve()
    assert path.is_relative_to((ROOT / "tests/.tmp").resolve())

    def unlink(directory):
        for child in directory.iterdir():
            if child.is_junction():
                child.rmdir()
            elif child.is_symlink():
                child.unlink()
            elif child.is_dir():
                unlink(child)
    unlink(path)

    def writable(function, target, exc):
        os.chmod(target, 0o700)
        function(target)
    shutil.rmtree(path, onexc=writable)


class Lab:
    def __init__(self, directory):
        self.directory = directory.resolve()
        assert self.directory.is_relative_to((ROOT / "tests/.tmp").resolve())
        self.root = self.directory / "checkout"
        self.root.mkdir(parents=True)
        self.base = self.root / "tests/.tmp/current"
        write(self.root / ".gitignore", b"/tests/.tmp/\n/.agent-state/\n")
        write(self.root / "source.bin", b"committed source\x00\r\n")
        git(self.root, "init", "-b", "fixture")
        git(self.root, "config", "user.name", "Cleanup Test")
        git(self.root, "config", "user.email", "cleanup-test@example.invalid")
        git(self.root, "config", "core.autocrlf", "false")
        git(self.root, "config", "core.symlinks", "true")
        git(self.root, "add", "--", ".gitignore", "source.bin")
        self.commit("fixture root")
        self.base.mkdir(parents=True)

    def commit(self, message):
        git(self.root, "-c", "commit.gpgsign=false", "commit", "-m", message)

    def rel(self, path):
        return path.relative_to(self.root).as_posix()

    def tracked(self, name="owned/deep/source.bin", state="committed", *, base=None):
        path = write((base or self.base) / name, b"indexed bytes\x00\r\n")
        if state == "preignore":
            write(self.root / ".gitignore", b"")
            git(self.root, "add", "--", ".gitignore", self.rel(path))
            self.commit("source before ignore")
            write(self.root / ".gitignore", b"/tests/.tmp/\n/.agent-state/\n")
            git(self.root, "add", "--", ".gitignore")
            self.commit("ignore later")
        else:
            git(self.root, "add", "-f", "--", self.rel(path))
            if state != "staged":
                self.commit("force-added source")
        if state == "assume-unchanged":
            git(self.root, "update-index", "--assume-unchanged", "--", self.rel(path))
        write(path, b"uncommitted source bytes\xff\x00\r\n")
        return path

    def link(self, name, kind, destination):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "junction":
            command(["cmd.exe", "/d", "/c", "mklink", "/J", str(path), str(destination)],
                    self.root)
            assert path.is_junction(), "The host must provide a real junction."
        else:
            path.symlink_to(destination, target_is_directory=kind == "directory")
            assert path.is_symlink(), "The host must provide a real symbolic link."
        return path
