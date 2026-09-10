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
# File:        env_support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Owner-Test real Git, filesystem and initialization fixtures.
# =================================================================================

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = Path("agent-discipline/skills/agent-workflow/scripts/workflow_environment.py")
HYDRATE = Path("agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env_hydrate.py")
DEPLOY = Path("agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env_deploy.py")
COLLECT = DEPLOY.with_name("init_agent_env_inputs.py")
BLACKBOX = Path("tools/blackbox_e2e.py")
PUBLIC_FUNCTIONS = (
    "inspect_checkout", "create_isolated_checkout", "required_capabilities",
    "evaluate_preflight", "require_preflight", "probe_command", "select_agent",
    "snapshot_evidence", "verify_evidence", "cleanup_paths",
)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))
    return path


def load(relative):
    path = ROOT / relative
    assert path.is_file(), f"K public entrypoint is not implemented: {relative}"
    name = "issue79_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # New helpers may import sibling modules. No production internals are read.
    previous = list(sys.path)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = previous
    return module


def require_api(module, names):
    for name in names:
        assert callable(getattr(module, name, None)), f"K public API missing: {name}"
    return module


def command(argv, cwd, *, input_bytes=None, timeout=45, check=True):
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull})
    result = subprocess.run(list(map(str, argv)), cwd=cwd, input=input_bytes,
                            capture_output=True, timeout=timeout, env=env)
    if check:
        assert result.returncode == 0, (
            f"Fixture command failed: {argv!r}: {result.stderr.decode(errors='replace')}"
        )
    return result


def git(root, *args, input_bytes=None, check=True):
    return command(["git", *args], root, input_bytes=input_bytes,
                   check=check).stdout.decode("utf-8").strip()


def inventory(root):
    """Exact visible file/link inventory; never follow directory links."""
    if not root.exists():
        return None
    found = {}

    def visit(directory):
        for path in sorted(directory.iterdir()):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                found[relative] = ("link", str(path.resolve(strict=False)))
            elif path.is_dir():
                found[relative] = ("dir",)
                visit(path)
            else:
                found[relative] = ("file", sha(path.read_bytes()))
    visit(root)
    return found


def assert_no_mutation(root, operation, error_class, codes):
    before = inventory(root)
    try:
        operation()
    except error_class as error:
        assert error.code in set(codes), error.as_dict()
        assert isinstance(error.as_dict(), dict)
        canonical(error.as_dict())
    else:
        raise AssertionError(f"Expected a structured rejection ({sorted(codes)})")
    assert inventory(root) == before, "Rejected operation mutated its target"


class Lab:
    """All generated repositories and canaries live under tests/.tmp."""

    def __init__(self):
        base = ROOT / "tests/.tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="issue79-owner-", dir=base)).resolve()
        self.source = self.directory / "source"
        self.derived = self.directory / "derived"
        self.derived.mkdir()
        self.source.mkdir()
        write(self.source / ".gitignore", ".agents/\n.codex/\n.claude/\n.opencode/\n.agent-state/\ntests/.tmp/\n__pycache__/\n")
        write(self.source / "tracked.txt", "public source\n")
        git(self.source, "init", "-b", "public")
        git(self.source, "config", "user.name", "Owner Test Fixture")
        git(self.source, "config", "user.email", "owner-test@example.invalid")
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "Public fixture")
        self.head = git(self.source, "rev-parse", "HEAD")

    def close(self):
        root = self.directory.resolve()
        assert root.is_relative_to((ROOT / "tests/.tmp").resolve())
        # shutil does not follow symlinks; directory junction behavior is native
        # on supported Python. Remove links first to make that boundary explicit.
        def unlink_links(directory):
            for path in directory.iterdir():
                if path.is_symlink():
                    path.unlink()
                elif hasattr(path, "is_junction") and path.is_junction():
                    path.rmdir()
                elif path.is_dir():
                    unlink_links(path)
        unlink_links(root)
        def writable_remove(function, path, error):
            os.chmod(path, 0o700)
            function(path)
        shutil.rmtree(root, onexc=writable_remove)

    def hidden_commit(self):
        blob = git(self.source, "hash-object", "-w", "--stdin", input_bytes=b"non-secret hidden object canary\n")
        tree = git(self.source, "mktree", input_bytes=f"100644 blob {blob}\tcanary.txt\n".encode())
        hidden = git(self.source, "commit-tree", tree, "-m", "Unrelated fixture branch")
        git(self.source, "update-ref", "refs/heads/private-canary", hidden)
        return hidden

    def clone(self, name="child"):
        target = self.derived / name
        git(self.source, "clone", "--no-local", "--single-branch", "--branch", "public", str(self.source), str(target))
        git(target, "remote", "remove", "origin")
        return target

    def linked(self):
        target = self.derived / "linked"
        git(self.source, "worktree", "add", "-b", "linked", str(target), self.head)
        return target

    def initialized(self, platforms=("codex", "claude", "opencode"), mode="update"):
        # A real deployer fixture, not an actual vendor installation or Human vote.
        for group in ("subagents", "skills"):
            shutil.copytree(ROOT / "agent-discipline" / group,
                            self.source / "agent-discipline" / group,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        write(self.source / "AGENTS.md", (ROOT / "AGENTS.md").read_bytes())
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "Canonical discipline fixture")
        self.head = git(self.source, "rev-parse", "HEAD")
        s32ds = self.directory / "S32DS"
        (s32ds / "eclipse").mkdir(parents=True)
        rtd = self.directory / "RTD"
        (rtd / "Platform_TS_T40D34M10I0R0").mkdir(parents=True)
        self.external = self.directory / "external-skills" / "owner-extra"
        write(self.external / "SKILL.md", "---\nname: owner-extra\ndescription: Non-secret fixture skill.\n---\nExternal marker\n")
        self.config = {
            "version": 2, "collected_at": "2026-09-10T00:00:00Z",
            "platforms": list(platforms), "mode": mode,
            "reset_confirmed": mode == "reset", "s32ds_path": str(s32ds),
            "rtd_path": str(rtd), "additional_skill_workflows": ["local"],
            "local_skill_import": {"roots": [str(self.external.parent)],
                                   "selected": [{"name": "owner-extra", "source": str(self.external)}]},
        }
        collector = load(COLLECT)
        assert collector.validate_input(self.config) == []
        deployer = load(DEPLOY)
        deployer.deploy(self.source, self.config, verified_by="owner-test-fixture")
        self.input = write(self.source / ".agent-state/init-input.json", canonical(self.config))
        return self

    def bindings(self, root=None):
        root = root or self.source
        return {"task_run": "owner-capability-example", "governor": self.head,
                "workflow_blob": "b" * 40, "contract_sha256": "c" * 64,
                "checkout_root": str(root.resolve()),
                "head": git(root, "rev-parse", "HEAD"), "candidate_sha256": None}


def request(lab, *, role="worker", platform="codex", extra=(), isolation="checkout", root=None):
    return {"version": 1, "role": role, "platform": platform,
            "bindings": lab.bindings(root), "required_capabilities": list(extra),
            "isolation": isolation}


def capability(name, *, context="host", status="available", approved=True, mode="host-cli"):
    return {"id": name, "context": context, "status": status,
            "approved": approved, "mode": mode,
            "evidence_sha256": sha(f"owner observation {name} {context} {status}".encode())}


def observations(module, req, *, extra=()):
    root = Path(req["bindings"]["checkout_root"])
    baseline = module.required_capabilities(req["role"])
    caps = [capability(name) for name in dict.fromkeys((*baseline, *req["required_capabilities"]))]
    return {"version": 1, "bindings": dict(req["bindings"]), "capabilities": caps + list(extra),
            "checkout": module.inspect_checkout(root, expected_head=req["bindings"]["head"])}


def selected(report, name):
    """Only IF_PREFLIGHT's public selected_capabilities is inspected."""
    choices = report["selected_capabilities"]
    if isinstance(choices, dict):
        return choices[name]
    return next(value for value in choices if value["id"] == name)


def capture(module, lab):
    return module.capture_initialization(lab.source, lab.input,
                                         expected_input_sha256=sha(lab.input.read_bytes()))


def hydrate(module, lab, target, snapshot, **overrides):
    options = {"initialization": snapshot, "expected_initialization_sha256": sha(canonical(snapshot)),
               "allowed_target_base": lab.derived, "platforms": ["codex"],
               "expected_target_head": lab.head}
    options.update(overrides)
    return module.hydrate_checkout(lab.source, target, **options)
