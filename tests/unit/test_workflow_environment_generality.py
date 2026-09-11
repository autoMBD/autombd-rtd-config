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
# File:        test_workflow_environment_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Public capability, checkout and evidence generality tests.
# =================================================================================

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))


def env():
    assert (SCRIPTS / "workflow_environment.py").is_file(), "public environment capability entrypoint is absent"
    return importlib.import_module("workflow_environment")


def digest(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()).hexdigest()


def git(root, *args):
    clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    clean["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["git", "-C", str(root), *args], env=clean, capture_output=True, check=True)
    return result.stdout.decode().strip()


def repo(base):
    root = base / "project"
    root.mkdir()
    git(root, "init", "-b", "seed")
    git(root, "config", "user.name", "Generality")
    git(root, "config", "user.email", "generality@example.invalid")
    (root / ".gitignore").write_bytes(b".agent-state/\ntests/.tmp/\n")
    (root / "source.txt").write_bytes(b"source-v1\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "seed")
    return root, git(root, "rev-parse", "HEAD")


def binding(root, head):
    return dict(task_run="portable-generality", governor=head, workflow_blob="b" * 40,
                contract_sha256="8" * 64, checkout_root=str(root.resolve()), head=head,
                candidate_sha256=None)


def request(root, head, role="worker", capabilities=(), isolation="checkout"):
    return dict(version=1, role=role, platform="codex", bindings=binding(root, head),
                required_capabilities=list(capabilities), isolation=isolation)


def observation(root, head, role="worker", extra=()):
    m = env()
    return dict(version=1, bindings=binding(root, head), checkout=m.inspect_checkout(root, expected_head=head),
                capabilities=[dict(id=name, context="host", status="available", approved=True,
                                   mode="host-cli", evidence_sha256="7" * 64)
                              for name in (*m.required_capabilities(role), *extra)])


@pytest.mark.parametrize("role,expected", [
    ("explorer", {"filesystem-read"}), ("reviewer", {"filesystem-read"}),
    ("orchestrator", {"filesystem-read", "filesystem-write", "git"}),
    ("worker", {"filesystem-read", "filesystem-write", "git"}),
    ("tester", {"filesystem-read", "filesystem-write", "git"}),
])
def test_operation_profiles_do_not_require_unused_vendors(role, expected):
    m = env()
    assert set(m.required_capabilities(role)) == expected
    assert set(m.required_capabilities(role, requires_blackbox=True, requires_s32ds=True)) == expected | {"agent-cli", "blackbox", "s32ds"}


def test_preflight_requires_exact_current_bindings_and_capability_union(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head, capabilities=("github",))
    obs = observation(root, head, extra=("github",))
    ready = m.evaluate_preflight(req, obs)
    assert ready["status"] == "READY"
    m.require_preflight(ready, expected_request_sha256=digest(req), current_bindings=req["bindings"])
    for field, value in [("head", "e" * 40), ("contract_sha256", "3" * 64), ("task_run", "other")]:
        changed = {**req["bindings"], field: value}
        with pytest.raises(m.EnvironmentError):
            m.require_preflight(ready, expected_request_sha256=digest(req), current_bindings=changed)
    (root / "source.txt").write_bytes(b"new source")
    git(root, "add", ".")
    git(root, "commit", "-m", "advance")
    with pytest.raises(m.EnvironmentError):
        m.require_preflight(ready, expected_request_sha256=digest(req), current_bindings=req["bindings"])


@pytest.mark.parametrize("status,approved", [("unknown", True), ("unavailable", True), ("available", False)])
def test_mandatory_facts_fail_closed(tmp_path, status, approved):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head)
    obs = observation(root, head)
    obs["capabilities"][0].update(status=status, approved=approved)
    report = m.evaluate_preflight(req, obs)
    assert report["status"] == "BLOCKED"
    with pytest.raises(m.EnvironmentError):
        m.require_preflight(report, expected_request_sha256=digest(req), current_bindings=req["bindings"])


def test_github_contexts_are_not_conflated(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head, capabilities=("github",))
    obs = observation(root, head)
    records = [
        dict(id="github", context="sandbox", status="unavailable", approved=True, mode="sandbox-cli", evidence_sha256="1"*64),
        dict(id="github", context="host", status="available", approved=True, mode="host-cli", evidence_sha256="2"*64),
        dict(id="github", context="connector", status="available", approved=True, mode="connector", evidence_sha256="3"*64),
    ]
    obs["capabilities"].extend(records)
    selected = m.evaluate_preflight(req, obs)["selected_capabilities"]
    assert next(x for x in selected if x["id"] == "github")["mode"] == "connector"
    obs["capabilities"].pop()
    selected = m.evaluate_preflight(req, obs)["selected_capabilities"]
    assert next(x for x in selected if x["id"] == "github")["mode"] == "host-cli"


def test_input_boundary_requires_separate_proven_fact(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head, isolation="input")
    obs = observation(root, head)
    assert obs["checkout"]["os_read_isolated"] is False
    assert m.evaluate_preflight(req, obs)["status"] == "BLOCKED"
    obs["capabilities"].append(dict(id="input-isolation", context="sandbox", status="available",
        approved=True, mode="non-secret-canary-allow-deny", evidence_sha256="2"*64))
    assert m.evaluate_preflight(req, obs)["status"] == "READY"


@pytest.mark.parametrize("bad", [lambda r: r.update(version=True), lambda r: r.update(platform="mystery"),
    lambda r: r.update(required_capabilities=["git", "git"]), lambda r: r["bindings"].update(head="HEAD"),
    lambda r: r.update(unexpected=True)])
def test_wire_rejects_malformed_requests(tmp_path, bad):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head)
    bad(req)
    with pytest.raises(m.EnvironmentError) as exc:
        m.evaluate_preflight(req, observation(root, head))
    assert exc.value.code == "INVALID_INPUT"


def test_checkout_creation_does_not_copy_other_refs_objects_or_remote(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    git(root, "checkout", "-b", "unrelated")
    (root / "private.txt").write_bytes(b"not in selected source")
    git(root, "add", ".")
    git(root, "commit", "-m", "other history")
    other = git(root, "rev-parse", "HEAD")
    git(root, "checkout", "seed")
    base = tmp_path / "derived"
    result = m.create_isolated_checkout(root, base / "lane", allowed_target_base=base,
        branch="codex/generated", expected_source_head=head)
    target = Path(result["root"])
    assert result["ref_isolated"] and not result["shared_objects"] and not result["os_read_isolated"]
    assert result["head"] == head
    assert git(target, "for-each-ref", "--format=%(refname)") == "refs/heads/codex/generated"
    assert git(target, "remote") == ""
    assert subprocess.run(["git", "-C", str(target), "cat-file", "-e", other], capture_output=True).returncode != 0
    assert git(root, "rev-parse", "HEAD") == head
    with pytest.raises(m.EnvironmentError):
        m.create_isolated_checkout(root, target, allowed_target_base=base, branch="again", expected_source_head=head)


def test_worktree_is_reported_as_shared_not_read_isolated(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    target = tmp_path / "linked"
    git(root, "worktree", "add", "-b", "linked", str(target), head)
    info = m.inspect_checkout(target, expected_head=head)
    assert info["checkout_kind"] == "worktree" and info["shared_objects"]
    assert not info["ref_isolated"] and not info["os_read_isolated"]


@pytest.mark.parametrize("target_name,branch,expected", [("../escape", "valid", None), ("lane", "HEAD", None), ("lane", "bad..ref", None), ("lane", "valid", "f"*40)])
def test_checkout_invalid_request_never_creates_target(tmp_path, target_name, branch, expected):
    m = env()
    root, head = repo(tmp_path)
    base = tmp_path / "derived"
    target = base / target_name
    with pytest.raises(m.EnvironmentError):
        m.create_isolated_checkout(root, target, allowed_target_base=base, branch=branch, expected_source_head=expected or head)
    assert not base.exists()


def test_probe_is_noninteractive_bounded_and_does_not_expose_output(tmp_path):
    m = env()
    secret = "canary-output-not-a-credential"
    result = m.probe_command([sys.executable, "-c", f"print({secret!r})"], tmp_path,
                              approved=True, context="host")
    assert result["status"] == "available" and result["exit_code"] == 0
    assert secret not in json.dumps(result)
    assert result["stdout_sha256"] == hashlib.sha256((secret + os.linesep).encode()).hexdigest()
    blocked = tmp_path / "must-not-exist"
    with pytest.raises(m.EnvironmentError):
        m.probe_command([sys.executable, "-c", f"open({str(blocked)!r},'w').close()"], tmp_path,
                        approved=False, context="host")
    assert not blocked.exists()
    result = m.probe_command([sys.executable, "-c", "import time; time.sleep(4)"], tmp_path,
                            approved=True, context="sandbox", timeout_seconds=1)
    assert result["timed_out"] and result["status"] == "unavailable"


@pytest.mark.parametrize("selected", ["codex", "claude", "opencode"])
def test_actor_uses_contributor_or_explicit_choice(selected):
    m = env()
    assert m.select_agent(selected, [selected]) == selected
    assert m.select_agent("unknown", [selected], explicit_agent=selected) == selected
    with pytest.raises(m.EnvironmentError):
        m.select_agent(None, [selected])
    with pytest.raises(m.EnvironmentError):
        m.select_agent(selected, [])


def test_evidence_checks_source_bytes_new_scope_files_and_allowlist(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    evidence = root / ".agent-state/run"
    evidence.mkdir(parents=True)
    (evidence / "bound.json").write_bytes(b"frozen")
    bindings = binding(root, head)
    snap = m.snapshot_evidence(root, [".agent-state/run/bound.json"], bindings=bindings)
    m.verify_evidence(root, snap, bindings=bindings)
    (evidence / "new.json").write_bytes(b"new")
    with pytest.raises(m.EnvironmentError):
        m.verify_evidence(root, snap, bindings=bindings)
    m.verify_evidence(root, snap, bindings=bindings, allowed_new_paths=[".agent-state/run/new.json"])
    (evidence / "bound.json").write_bytes(b"changed")
    with pytest.raises(m.EnvironmentError):
        m.verify_evidence(root, snap, bindings=bindings, allowed_new_paths=[".agent-state/run/"])
    (evidence / "bound.json").write_bytes(b"frozen")
    (root / "source.txt").write_bytes(b"changed-source")
    with pytest.raises(m.EnvironmentError):
        m.verify_evidence(root, snap, bindings=bindings, allowed_new_paths=[".agent-state/run/new.json"])


def test_cleanup_validates_entire_set_before_deleting_anything(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    base = root / "tests/.tmp/current"
    base.mkdir(parents=True)
    for name in ("keep", "discard"):
        (base / name).write_bytes(name.encode())
    with pytest.raises(m.EnvironmentError):
        m.cleanup_paths(root, ["tests/.tmp/current/discard", "tests/.tmp/current/keep"],
                        allowed_base=base, protected_paths=["tests/.tmp/current/keep"], dry_run=False)
    assert (base / "discard").is_file()
    planned = m.cleanup_paths(root, ["tests/.tmp/current/discard"], allowed_base=base)
    assert planned["status"] == "PLANNED" and (base / "discard").is_file()
    cleaned = m.cleanup_paths(root, ["tests/.tmp/current/discard"], allowed_base=base, dry_run=False)
    assert cleaned["status"] == "CLEANED" and not (base / "discard").exists()
    assert (base / "keep").is_file()
    with pytest.raises(m.EnvironmentError):
        m.cleanup_paths(root, ["source.txt"], allowed_base=root, dry_run=False)


def test_checkout_links_and_alternates_never_claim_reference_isolation(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    alternate = root / ".git/objects/info/alternates"
    alternate.write_bytes(b"/not-a-valid-object-store\n")
    info = m.inspect_checkout(root, expected_head=head)
    assert info["shared_objects"] and not info["ref_isolated"]
    alternate.unlink()
    real_git = tmp_path / "separate-git-store"
    (root / ".git").rename(real_git)
    (root / ".git").symlink_to(real_git, target_is_directory=True)
    info = m.inspect_checkout(root, expected_head=head)
    assert info["shared_objects"] and not info["ref_isolated"]


def test_cleanup_unlinks_leaf_link_without_touching_destination(tmp_path):
    m = env()
    root, _ = repo(tmp_path)
    base = root / "tests/.tmp/job"
    base.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"keep")
    (base / "link").symlink_to(outside, target_is_directory=True)
    m.cleanup_paths(root, ["tests/.tmp/job/link"], allowed_base=base, dry_run=False)
    assert not (base / "link").exists()
    assert (outside / "keep").read_bytes() == b"keep"


def test_cleanup_rejects_linked_ancestor_before_any_delete(tmp_path):
    m = env()
    root, _ = repo(tmp_path)
    base = root / "tests/.tmp/job"
    base.mkdir(parents=True)
    other = tmp_path / "other"
    other.mkdir()
    (other / "secret").write_bytes(b"keep")
    (base / "link").symlink_to(other, target_is_directory=True)
    (base / "ordinary").write_bytes(b"keep")
    with pytest.raises(m.EnvironmentError):
        m.cleanup_paths(root, ["tests/.tmp/job/ordinary", "tests/.tmp/job/link/secret"], allowed_base=base, dry_run=False)
    assert (base / "ordinary").exists() and (other / "secret").exists()


def test_json_cli_reports_ready_blocked_and_malformed_without_touching_inputs(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head)
    obs = observation(root, head)
    paths = [tmp_path / "request.json", tmp_path / "observation.json", tmp_path / "report.json", tmp_path / "bindings.json"]
    for path, data in zip(paths, [req, obs, m.evaluate_preflight(req, obs), req["bindings"]]):
        path.write_bytes((json.dumps(data) + "\n").encode())
    before = [p.read_bytes() for p in paths]
    def run(*args):
        result = subprocess.run([sys.executable, str(SCRIPTS / "workflow_environment.py"), *args],
                                capture_output=True)
        return result.returncode, json.loads(result.stdout)
    assert run("inspect-checkout", "--root", str(root), "--expected-head", head)[0] == 0
    assert run("preflight", "--request", str(paths[0]), "--observations", str(paths[1]))[1]["status"] == "READY"
    assert run("verify-preflight", "--report", str(paths[2]), "--bindings", str(paths[3]),
               "--expected-request-sha256", digest(req))[0] == 0
    assert [p.read_bytes() for p in paths] == before
    assert run("preflight", "--request", str(paths[0]))[0] == 2
    paths[0].write_bytes(b'{"version":1,"version":1}')
    assert run("preflight", "--request", str(paths[0]), "--observations", str(paths[1]))[0] == 2


def test_preflight_report_mutation_cannot_authorize_dispatch(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    req = request(root, head, capabilities=("blackbox",))
    report = m.evaluate_preflight(req, observation(root, head))
    assert report["status"] == "BLOCKED"
    report["status"] = "READY"
    report["diagnostics"] = []
    with pytest.raises(m.EnvironmentError):
        m.require_preflight(report, expected_request_sha256=digest(req), current_bindings=req["bindings"])


@pytest.mark.parametrize("argv,deadline,context", [("arbitrary shell string", 1, "host"),
    (["program"], 0, "host"), (["program"], True, "host"), (["program"], 1, "unknown")])
def test_probe_rejects_malformed_before_spawning(tmp_path, monkeypatch, argv, deadline, context):
    m = env()
    def forbidden(*args, **kwargs):
        raise AssertionError("validation must precede subprocess execution")
    monkeypatch.setattr(m.subprocess, "run", forbidden)
    with pytest.raises(m.EnvironmentError):
        m.probe_command(argv, tmp_path, approved=True, context=context, timeout_seconds=deadline)


def test_single_ref_with_disconnected_objects_is_not_reported_as_isolated(tmp_path):
    m = env()
    root, head = repo(tmp_path)
    git(root, "checkout", "-b", "temporary")
    (root / "canary-private.txt").write_bytes(b"disconnected branch canary")
    git(root, "add", ".")
    git(root, "commit", "-m", "disconnected")
    git(root, "checkout", "seed")
    git(root, "branch", "-D", "temporary")
    assert git(root, "for-each-ref", "--format=%(refname)") == "refs/heads/seed"
    assert m.inspect_checkout(root, expected_head=head)["ref_isolated"] is False
