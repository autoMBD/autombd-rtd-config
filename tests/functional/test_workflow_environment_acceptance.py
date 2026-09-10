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
# File:        test_workflow_environment_acceptance.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Independent issue 79 capability and isolation acceptance.
# =================================================================================

"""Independent owner acceptance for the public issue #79 contract.

Case IDs live beside assertions. No implementation fallback/reference runtime is
embedded here. Governor runs intentionally fail assertions for missing APIs.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / "tests/fixtures/workflow-environment/env_support.py"
_spec = importlib.util.spec_from_file_location("issue79_owner_support", SUPPORT)
assert _spec is not None and _spec.loader is not None
s = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = s
_spec.loader.exec_module(s)


@pytest.fixture
def lab():
    value = s.Lab()
    try:
        yield value
    finally:
        value.close()


def environment():
    return s.require_api(s.load(s.WORKFLOW), s.PUBLIC_FUNCTIONS)


def initializer():
    return s.require_api(s.load(s.HYDRATE), ("capture_initialization", "hydrate_checkout"))


def rejected(module, operation, codes=("INVALID_INPUT",)):
    with pytest.raises(module.EnvironmentError) as caught:
        operation()
    assert caught.value.code in codes, caught.value.as_dict()
    assert isinstance(caught.value.as_dict(), dict)
    s.canonical(caught.value.as_dict())


def sentry_dispatch(module, report, request, path, *, bindings=None, digest=None):
    module.require_preflight(
        report, expected_request_sha256=digest or s.sha(s.canonical(request)),
        current_bindings=bindings or request["bindings"],
    )
    s.write(path, "dispatched\n")


class TestCheckout:
    def test_c01_public_api_and_error_shape(self):
        module = environment()
        assert isinstance(module.EnvironmentError, type)
        assert issubclass(module.EnvironmentError, Exception)
        initializer()

    def test_c02_real_worktree_clone_and_os_claims(self, lab):
        module = environment()
        linked = lab.linked()
        clone = lab.clone()
        linked_report = module.inspect_checkout(linked, expected_head=lab.head)
        clone_report = module.inspect_checkout(clone, expected_head=lab.head)
        assert linked_report["checkout_kind"] == "worktree"
        assert linked_report["shared_objects"] is True
        assert linked_report["ref_isolated"] is False
        assert Path(linked_report["git_dir"]).resolve() != Path(linked_report["common_dir"]).resolve()
        assert clone_report["checkout_kind"] == "clone"
        assert clone_report["shared_objects"] is False
        assert clone_report["ref_isolated"] is True
        for root, report in ((linked, linked_report), (clone, clone_report)):
            assert Path(report["root"]).resolve() == root.resolve()
            assert report["head"] == lab.head
            assert report["os_read_isolated"] is False
            s.canonical(report)

    def test_c03_clone_does_not_expose_unrelated_objects_or_refs(self, lab):
        module = environment()
        hidden = lab.hidden_commit()
        target = lab.derived / "capability-clone"
        before = s.inventory(lab.source)
        report = module.create_isolated_checkout(
            lab.source, target, allowed_target_base=lab.derived,
            branch="codex/test-isolated", expected_source_head=lab.head,
        )
        assert report["head"] == lab.head
        assert report["ref_isolated"] is True
        assert report["os_read_isolated"] is False
        assert s.inventory(lab.source) == before
        assert s.git(target, "for-each-ref", "--format=%(refname)").splitlines() == ["refs/heads/codex/test-isolated"]
        assert s.git(target, "remote") == ""
        assert s.command(["git", "cat-file", "-e", hidden], target, check=False).returncode != 0
        assert not (target / ".git/objects/info/alternates").exists()
        assert not (target / ".git/objects").is_symlink()
        # A clone must not use source object hardlinks either.
        for file in (target / ".git/objects").rglob("*"):
            source = lab.source / ".git/objects" / file.relative_to(target / ".git/objects")
            if file.is_file() and source.is_file():
                assert not os.path.samefile(file, source)

    @pytest.mark.parametrize("bad", ["exists", "head", "outside", "same", "branch"])
    def test_c04_rejected_creation_is_atomic(self, lab, bad):
        module = environment()
        target = lab.derived / "child"
        head, branch = lab.head, "codex/new"
        if bad == "exists":
            s.write(target / "keep", "untouched")
        elif bad == "head":
            head = "e" * 40
        elif bad == "outside":
            target = lab.directory / "unrelated-child"
        elif bad == "same":
            target = lab.source
        else:
            branch = "../not-a-ref"
        before = s.inventory(lab.directory)
        rejected(module, lambda: module.create_isolated_checkout(
            lab.source, target, allowed_target_base=lab.derived, branch=branch,
            expected_source_head=head,
        ), ("INVALID_INPUT", "PATH_BOUNDARY", "STALE_IDENTITY"))
        assert s.inventory(lab.directory) == before

    def test_c05_rejects_link_escape_and_stale_inspection(self, lab):
        module = environment()
        outside = lab.directory / "outside"
        outside.mkdir()
        link = lab.derived / "escape"
        link.symlink_to(outside, target_is_directory=True)
        before = s.inventory(lab.directory)
        rejected(module, lambda: module.create_isolated_checkout(
            lab.source, link / "child", allowed_target_base=lab.derived,
            branch="codex/escape", expected_source_head=lab.head,
        ), ("PATH_BOUNDARY",))
        assert s.inventory(lab.directory) == before
        rejected(module, lambda: module.inspect_checkout(lab.source, expected_head="e" * 40),
                 ("STALE_IDENTITY",))

    def test_c06_shared_clone_is_not_ref_isolated(self, lab):
        module = environment()
        target = lab.derived / "alternates"
        s.git(lab.source, "clone", "--shared", str(lab.source), str(target))
        report = module.inspect_checkout(target, expected_head=lab.head)
        assert report["shared_objects"] is True
        assert report["ref_isolated"] is False
        assert report["os_read_isolated"] is False


class TestHydration:
    def test_c07_capture_is_read_only_and_snapshot_is_opaque_json(self, lab):
        module = initializer()
        lab.initialized()
        before = s.inventory(lab.source)
        snapshot = s.capture(module, lab)
        assert isinstance(snapshot, dict)
        assert s.canonical(snapshot) == s.canonical(json.loads(s.canonical(snapshot)))
        assert s.capture(module, lab) == snapshot
        assert s.inventory(lab.source) == before

    @pytest.mark.parametrize("bad", ["digest", "missing-input", "input-invalid", "missing-cache", "invalid-cache", "generated-role", "skill-link"])
    def test_c08_capture_rejects_unverified_initialization(self, lab, bad):
        module = initializer()
        lab.initialized(platforms=("codex",))
        expected = s.sha(lab.input.read_bytes())
        if bad == "digest":
            expected = "d" * 64
        elif bad == "missing-input":
            lab.input.unlink()
        elif bad == "input-invalid":
            s.write(lab.input, s.canonical({"version": 2}))
            expected = s.sha(lab.input.read_bytes())
        elif bad == "missing-cache":
            (lab.source / ".agent-state/external-dependencies.json").unlink()
        elif bad == "invalid-cache":
            s.write(lab.source / ".agent-state/external-dependencies.json", '{"version":8}\n')
        elif bad == "generated-role":
            s.write(lab.source / ".codex/agents/worker.toml", 'name = "tampered"\n')
        else:
            (lab.source / ".agents/skills/agent-workflow").unlink()
        before = s.inventory(lab.source)
        rejected(module, lambda: module.capture_initialization(
            lab.source, lab.input, expected_input_sha256=expected,
        ), ("INITIALIZATION_UNAVAILABLE", "INVALID_INPUT"))
        assert s.inventory(lab.source) == before

    @pytest.mark.parametrize("platform", ["codex", "claude", "opencode"])
    def test_c09_valid_subset_uses_target_sources_and_is_idempotent(self, lab, platform):
        module = initializer()
        lab.initialized()
        snapshot = s.capture(module, lab)
        target = lab.clone()
        assert not (target / ".agent-state").exists()
        report = s.hydrate(module, lab, target, snapshot, platforms=[platform])
        assert report["status"] == "HYDRATED"
        assert set(report["platforms"]) == {platform}
        assert report["changed_paths"]
        for path in report["changed_paths"]:
            assert isinstance(path, str) and not Path(path).is_absolute() and ".." not in Path(path).parts
            assert (target / path).exists()
        agent_root = target / {"codex": ".codex/agents", "claude": ".claude/agents", "opencode": ".opencode/agents"}[platform]
        assert len(list(agent_root.iterdir())) >= 4
        if platform == "codex":
            worker = tomllib.loads((agent_root / "worker.toml").read_text(encoding="utf-8"))
            reviewer = tomllib.loads((agent_root / "reviewer.toml").read_text(encoding="utf-8"))
            assert worker["sandbox_mode"] == "workspace-write"
            source_reviewer = tomllib.loads((lab.source / ".codex/agents/reviewer.toml").read_text(encoding="utf-8"))
            assert reviewer["sandbox_mode"] == source_reviewer["sandbox_mode"]
        skill_root = target / (".claude/skills" if platform == "claude" else ".agents/skills")
        assert (skill_root / "agent-workflow").resolve() == (target / "agent-discipline/skills/agent-workflow").resolve()
        assert (skill_root / "owner-extra").resolve() == lab.external.resolve()
        for other in {"codex", "claude", "opencode"} - {platform}:
            assert not (target / {"codex": ".codex/agents", "claude": ".claude/agents", "opencode": ".opencode/agents"}[other]).exists()
        cache = json.loads((target / ".agent-state/external-dependencies.json").read_bytes())
        assert cache["version"] == 1 and cache["items"]["tool.python"]["status"] == "available"
        before = s.inventory(target)
        again = s.hydrate(module, lab, target, snapshot, platforms=[platform])
        assert again["status"] == "HYDRATED"
        assert again["changed_paths"] == []
        assert s.inventory(target) == before

    @pytest.mark.parametrize("bad", ["snapshot-digest", "snapshot-shape", "head", "platform", "same", "outside", "unqualified"])
    def test_c10_hydration_rejections_never_mutate_target(self, lab, bad):
        module = initializer()
        lab.initialized(platforms=("codex",))
        snapshot = s.capture(module, lab)
        target = lab.clone()
        options = {}
        if bad == "snapshot-digest":
            options["expected_initialization_sha256"] = "f" * 64
        elif bad == "snapshot-shape":
            snapshot = {"version": 999}
        elif bad == "head":
            options["expected_target_head"] = "f" * 40
        elif bad == "platform":
            options["platforms"] = ["claude"]
        elif bad == "same":
            target = lab.source
        elif bad == "outside":
            options["allowed_target_base"] = lab.directory / "different-base"
        else:
            target = lab.derived / "first-time-empty"
            target.mkdir()
        before = s.inventory(lab.directory)
        rejected(module, lambda: s.hydrate(module, lab, target, snapshot, **options),
                 ("INVALID_INPUT", "PATH_BOUNDARY", "INITIALIZATION_UNAVAILABLE", "PLATFORM_NOT_APPROVED", "STALE_IDENTITY"))
        assert s.inventory(lab.directory) == before

    @pytest.mark.parametrize("changed", ["input", "cache", "role", "asset", "external", "source-head"])
    def test_c11_source_evidence_drift_invalidates_capture(self, lab, changed):
        module = initializer()
        lab.initialized(platforms=("codex",))
        snapshot = s.capture(module, lab)
        target = lab.clone()
        if changed == "input":
            s.write(lab.input, lab.input.read_bytes() + b" ")
        elif changed == "cache":
            (lab.source / ".agent-state/external-dependencies.json").unlink()
        elif changed == "role":
            s.write(lab.source / ".codex/agents/worker.toml", "changed")
        elif changed == "asset":
            path = lab.source / "agent-discipline/skills/agent-workflow/SKILL.md"
            s.write(path, path.read_bytes() + b"\nChanged\n")
        elif changed == "external":
            s.write(lab.external / "SKILL.md", "---\nname: owner-extra\ndescription: Changed.\n---\n")
        else:
            s.write(lab.source / "tracked.txt", "new revision")
            s.git(lab.source, "add", "tracked.txt")
            s.git(lab.source, "commit", "-m", "Source identity changed")
        s.assert_no_mutation(target, lambda: s.hydrate(module, lab, target, snapshot),
                             module.EnvironmentError, ("INITIALIZATION_UNAVAILABLE", "STALE_IDENTITY"))

    def test_c12_linked_target_parent_is_rejected_before_deployment(self, lab):
        module = initializer()
        lab.initialized(platforms=("codex",))
        snapshot = s.capture(module, lab)
        target = lab.clone()
        outside = lab.directory / "outside"
        outside.mkdir()
        (target / ".codex").symlink_to(outside, target_is_directory=True)
        before = s.inventory(lab.directory)
        rejected(module, lambda: s.hydrate(module, lab, target, snapshot), ("PATH_BOUNDARY",))
        assert s.inventory(lab.directory) == before

    def test_c13_source_reset_is_not_replayed_or_gui_reopened(self, lab, monkeypatch):
        module = initializer()
        lab.initialized(platforms=("codex",), mode="reset")
        snapshot = s.capture(module, lab)
        target = lab.clone()
        preserved = s.write(target / ".agent-state/keep-evidence.json", '{"keep":true}\n')
        s.write(target / ".codex/agents/unrelated.toml", 'name = "unrelated"\n')
        import tkinter
        def no_gui(*args, **kwargs):
            raise AssertionError("Hydration must not open the initialization GUI")
        monkeypatch.setattr(tkinter.Tk, "__init__", no_gui)
        result = s.hydrate(module, lab, target, snapshot)
        assert result["status"] == "HYDRATED"
        assert preserved.read_bytes() == b'{"keep":true}\n'
        assert (target / ".codex/agents/unrelated.toml").read_bytes() == b'name = "unrelated"\n'


class TestCapabilities:
    @pytest.mark.parametrize("role,expected", [
        ("orchestrator", {"filesystem-read", "filesystem-write", "git"}),
        ("worker", {"filesystem-read", "filesystem-write", "git"}),
        ("tester", {"filesystem-read", "filesystem-write", "git"}),
        ("explorer", {"filesystem-read"}), ("reviewer", {"filesystem-read"}),
    ])
    def test_c14_role_baselines_do_not_require_unselected_services(self, role, expected):
        module = environment()
        assert isinstance(module.required_capabilities(role), tuple)
        assert set(module.required_capabilities(role)) == expected
        assert set(module.required_capabilities(role, requires_s32ds=True)) == expected | {"s32ds"}
        assert {"blackbox", "agent-cli"} <= set(module.required_capabilities(role, requires_blackbox=True))
        assert "s32ds" not in module.required_capabilities(role, requires_blackbox=True)

    def test_c15_ready_requires_every_baseline_and_optional_absence_is_harmless(self, lab):
        module = environment()
        req = s.request(lab)
        obs = s.observations(module, req)
        obs["capabilities"].append(s.capability("s32ds", status="unavailable"))
        before = copy.deepcopy((req, obs))
        report = module.evaluate_preflight(req, obs)
        assert (req, obs) == before
        assert report["version"] == 1 and report["status"] == "READY"
        assert report["request_sha256"] == s.sha(s.canonical(req))
        assert report["bindings"] == req["bindings"]
        assert report["diagnostics"] == []
        s.canonical(report)
        marker = lab.directory / "dispatch"
        sentry_dispatch(module, report, req, marker)
        assert marker.read_bytes() == b"dispatched\n"

    @pytest.mark.parametrize("fault", ["missing", "unavailable", "unknown", "unapproved"])
    def test_c16_mandatory_capability_failure_blocks_before_dispatch(self, lab, fault):
        module = environment()
        req = s.request(lab)
        obs = s.observations(module, req)
        if fault == "missing":
            obs["capabilities"] = [item for item in obs["capabilities"] if item["id"] != "git"]
        else:
            item = next(item for item in obs["capabilities"] if item["id"] == "git")
            if fault == "unapproved":
                item["approved"] = False
            else:
                item["status"] = fault
        report = module.evaluate_preflight(req, obs)
        assert report["status"] == "BLOCKED"
        assert any(item["capability"] == "git" and item["code"] for item in report["diagnostics"])
        marker = lab.directory / "must-not-dispatch"
        rejected(module, lambda: sentry_dispatch(module, report, req, marker), ("CAPABILITY_UNAVAILABLE",))
        assert not marker.exists()

    @pytest.mark.parametrize("field,value", [
        ("task_run", "different-task"), ("governor", "d" * 40),
        ("workflow_blob", "d" * 40), ("contract_sha256", "d" * 64),
        ("checkout_root", "different-root"), ("head", "d" * 40),
        ("candidate_sha256", "d" * 40),
    ])
    def test_c17_every_identity_component_is_rechecked(self, lab, field, value):
        module = environment()
        req = s.request(lab)
        report = module.evaluate_preflight(req, s.observations(module, req))
        assert report["status"] == "READY"
        current = {**req["bindings"], field: value}
        marker = lab.directory / "must-not-dispatch"
        rejected(module, lambda: sentry_dispatch(module, report, req, marker, bindings=current),
                 ("STALE_IDENTITY", "INVALID_INPUT"))
        assert not marker.exists()
        rejected(module, lambda: sentry_dispatch(module, report, req, marker, digest="d" * 64),
                 ("STALE_IDENTITY", "INVALID_INPUT"))
        assert not marker.exists()

    def test_c18_observation_identity_drift_is_rejected(self, lab):
        module = environment()
        req = s.request(lab)
        obs = s.observations(module, req)
        obs["bindings"]["task_run"] = "other-task"
        rejected(module, lambda: module.evaluate_preflight(req, obs), ("STALE_IDENTITY",))

    @pytest.mark.parametrize("field,value", [
        ("version", 2), ("role", "unknown"), ("platform", "unknown"),
        ("isolation", "renamed-directory"),
        ("required_capabilities", ["git", "git"]),
        ("required_capabilities", ["unknown-capability"]),
    ])
    def test_c19_malformed_request_is_rejected(self, lab, field, value):
        module = environment()
        req = s.request(lab)
        obs = s.observations(module, req)
        req[field] = value
        rejected(module, lambda: module.evaluate_preflight(req, obs), ("INVALID_INPUT",))

    def test_c20_input_isolation_requires_additional_applicable_evidence(self, lab):
        module = environment()
        clone = lab.clone()
        req = s.request(lab, isolation="input", root=clone)
        obs = s.observations(module, req)
        assert obs["checkout"]["ref_isolated"] is True
        assert obs["checkout"]["os_read_isolated"] is False
        report = module.evaluate_preflight(req, obs)
        assert report["status"] == "BLOCKED"
        assert any(item["capability"] == "input-isolation" for item in report["diagnostics"])
        # These are explicit trusted adapter observations, not a claim that this
        # fixture creates OS isolation. The portable evaluator only consumes them.
        obs["capabilities"].append(s.capability("input-isolation", mode="fixture-allow-deny-evidence"))
        assert module.evaluate_preflight(req, obs)["status"] == "READY"

    @pytest.mark.parametrize("connector,host,expected", [
        ("available", True, "connector"), ("unavailable", True, "host"),
        ("unknown", False, None),
    ])
    def test_c21_github_contexts_remain_separate(self, lab, connector, host, expected):
        module = environment()
        req = s.request(lab, extra=("github",))
        obs = s.observations(module, req)
        obs["capabilities"] = [item for item in obs["capabilities"] if item["id"] != "github"]
        obs["capabilities"].extend([
            s.capability("github", context="sandbox", status="unavailable", mode="sandbox-cli"),
            s.capability("github", context="host", approved=host, mode="host-cli"),
            s.capability("github", context="connector", status=connector, mode="connector"),
        ])
        report = module.evaluate_preflight(req, obs)
        if expected is None:
            assert report["status"] == "BLOCKED"
        else:
            assert report["status"] == "READY"
            selected = s.selected(report, "github")
            assert selected["context"] == expected
            assert selected["mode"] == ("connector" if expected == "connector" else "host-cli")


class TestProbesAndActor:
    def test_c22_probe_uses_closed_stdin_literal_argv_and_output_digests(self, lab):
        module = environment()
        literal = "non-secret canary & echo should-not-execute"
        code = "import sys; assert sys.stdin.read()==''; sys.stdout.write(sys.argv[1]); sys.stderr.write('diagnostic')"
        report = module.probe_command([sys.executable, "-c", code, literal], lab.source,
                                      approved=True, context="host", timeout_seconds=10)
        assert report["status"] == "available" and report["exit_code"] == 0
        assert report["context"] == "host" and report["timed_out"] is False
        assert report["stdout_sha256"] == s.sha(literal.encode())
        assert report["stderr_sha256"] == s.sha(b"diagnostic")
        assert literal not in json.dumps(report)
        assert not {"stdout", "stderr", "output"} & report.keys()

    def test_c23_failed_and_timed_out_probes_are_truthful(self, lab):
        module = environment()
        failed = module.probe_command([sys.executable, "-c", "raise SystemExit(7)"],
                                      lab.source, approved=True, context="sandbox", timeout_seconds=5)
        assert failed["status"] == "unavailable" and failed["exit_code"] == 7
        assert failed["timed_out"] is False
        start = time.monotonic()
        timed = module.probe_command([sys.executable, "-c", "import time; time.sleep(8)"],
                                     lab.source, approved=True, context="host", timeout_seconds=1)
        assert timed["status"] == "unavailable" and timed["timed_out"] is True
        assert time.monotonic() - start < 7

    @pytest.mark.parametrize("fault", ["approval", "argv-string", "argv-empty", "cwd", "context", "deadline"])
    def test_c24_probe_rejects_before_process_side_effect(self, lab, fault):
        module = environment()
        marker = lab.directory / "probe-was-launched"
        argv = [sys.executable, "-c", "import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'bad')", str(marker)]
        cwd, approved, context, deadline = lab.source, True, "host", 5
        if fault == "approval":
            approved = False
        elif fault == "argv-string":
            argv = "echo unsafe"
        elif fault == "argv-empty":
            argv = []
        elif fault == "cwd":
            cwd = lab.directory / "absent"
        elif fault == "context":
            context = "auto-elevated"
        else:
            deadline = 0
        codes = ("INVALID_INPUT", "CAPABILITY_UNAVAILABLE")
        if fault == "cwd":
            codes += ("PATH_BOUNDARY",)
        rejected(module, lambda: module.probe_command(argv, cwd, approved=approved,
                 context=context, timeout_seconds=deadline), codes)
        assert not marker.exists()
        if fault == "cwd":
            assert not cwd.exists()

    @pytest.mark.parametrize("platform", ["codex", "claude", "opencode"])
    def test_c25_current_actor_and_explicit_override(self, platform):
        module = environment()
        assert module.select_agent(platform, [platform]) == platform
        other = next(value for value in ["codex", "claude", "opencode"] if value != platform)
        assert module.select_agent(platform, [platform, other], explicit_agent=other) == other
        assert module.select_agent(None, [platform], explicit_agent=platform) == platform

    @pytest.mark.parametrize("platform,available,explicit", [
        (None, ["codex", "claude"], None), ("unknown", ["codex"], None),
        ("claude", ["codex"], None), ("codex", ["codex"], "claude"),
        ("codex", ["codex"], "unregistered"),
    ])
    def test_c26_missing_or_ambiguous_actor_does_not_silently_fallback(self, platform, available, explicit):
        module = environment()
        rejected(module, lambda: module.select_agent(platform, available, explicit_agent=explicit),
                 ("INVALID_INPUT", "CAPABILITY_UNAVAILABLE"))

    @pytest.mark.parametrize("platform", ["codex", "claude", "opencode"])
    def test_c27_harness_current_actor_beats_other_contributor_cache(self, lab, platform):
        module = s.load(s.BLACKBOX)
        assert "current_platform" in inspect.signature(module.resolve_agent).parameters, "IF_ACTOR current-platform integration missing"
        other = next(value for value in ["codex", "claude", "opencode"] if value != platform)
        cache = s.write(lab.directory / "actor-cache.json", s.canonical(
            {"version": 1, "default_agent": other, "updated_at": "2026-01-01T00:00:00Z"}))
        assert module.resolve_agent(None, cache, current_platform=platform,
                                    available_agents=[platform, other]) == (platform, "current-platform")
        assert module.resolve_agent(other, cache, current_platform=platform,
                                    available_agents=[platform, other]) == (other, "flag")
        assert cache.is_file()

    def test_c28_registry_and_cli_support_all_selectable_platforms(self, lab):
        module = s.load(s.BLACKBOX)
        for platform in ("codex", "claude", "opencode"):
            assert platform in module.AGENT_ADAPTERS, f"No selectable {platform} adapter"
            adapter = module.get_adapter(platform)
            for name in ("run", "extract_result", "prepare_workdir"):
                assert callable(getattr(adapter, name))
        help_result = s.command([sys.executable, ROOT / s.BLACKBOX, "--help"], ROOT)
        assert b"--current-platform" in help_result.stdout


class TestEvidenceHygiene:
    def make_snapshot(self, module, lab):
        root = lab.source
        evidence = ".agent-state/agent-loop/current/evidence/check/result.json"
        s.write(root / evidence, '{"actual":"result"}\n')
        bindings = lab.bindings()
        snapshot = module.snapshot_evidence(root, [evidence], bindings=bindings)
        assert isinstance(snapshot, dict)
        s.canonical(snapshot)
        return root, evidence, bindings, snapshot

    def test_c29_unchanged_opaque_evidence_verifies(self, lab):
        module = environment()
        root, path, bindings, snapshot = self.make_snapshot(module, lab)
        before = s.inventory(root)
        assert module.verify_evidence(root, snapshot, bindings=bindings) is None
        assert s.inventory(root) == before

    @pytest.mark.parametrize("change", ["bytes", "missing", "head", "unstaged", "staged", "untracked", "bindings"])
    def test_c30_source_or_bound_evidence_changes_are_stale(self, lab, change):
        module = environment()
        root, path, bindings, snapshot = self.make_snapshot(module, lab)
        if change == "bytes":
            s.write(root / path, '{"actual":"changed"}\n')
        elif change == "missing":
            (root / path).unlink()
        elif change in ("head", "unstaged", "staged"):
            s.write(root / "tracked.txt", "changed source")
            if change in ("head", "staged"):
                s.git(root, "add", "tracked.txt")
            if change == "head":
                s.git(root, "commit", "-m", "Changed revision")
        elif change == "untracked":
            s.write(root / "new-source.py", "changed source\n")
        else:
            bindings = {**bindings, "contract_sha256": "d" * 64}
        rejected(module, lambda: module.verify_evidence(root, snapshot, bindings=bindings),
                 ("STALE_IDENTITY",))

    def test_c31_dirty_source_bytes_cannot_hide_behind_same_status(self, lab):
        module = environment()
        s.write(lab.source / "tracked.txt", "initial dirty\n")
        root, path, bindings, snapshot = self.make_snapshot(module, lab)
        s.write(root / "tracked.txt", "another dirty\n")
        rejected(module, lambda: module.verify_evidence(root, snapshot, bindings=bindings),
                 ("STALE_IDENTITY",))

    def test_c32_only_explicit_new_ignored_evidence_is_allowed(self, lab):
        module = environment()
        root, path, bindings, snapshot = self.make_snapshot(module, lab)
        added = str(Path(path).with_name("new-report.json")).replace("\\", "/")
        s.write(root / added, '{"new":true}\n')
        rejected(module, lambda: module.verify_evidence(root, snapshot, bindings=bindings),
                 ("STALE_IDENTITY",))
        assert module.verify_evidence(root, snapshot, bindings=bindings, allowed_new_paths=[added]) is None
        s.write(root / path, "changed old evidence")
        rejected(module, lambda: module.verify_evidence(root, snapshot, bindings=bindings,
                 allowed_new_paths=[added, path]), ("STALE_IDENTITY",))

    @pytest.mark.parametrize("target", ["tracked.txt", ".git/config", "../escape", "."])
    def test_c33_new_evidence_allowlist_cannot_authorize_source_or_escape(self, lab, target):
        module = environment()
        root, path, bindings, snapshot = self.make_snapshot(module, lab)
        rejected(module, lambda: module.verify_evidence(root, snapshot, bindings=bindings,
                 allowed_new_paths=[target]), ("INVALID_INPUT", "PATH_BOUNDARY", "STALE_IDENTITY"))

    def test_c34_cleanup_plans_then_removes_only_explicit_target(self, lab):
        module = environment()
        root = lab.source
        base = root / "tests/.tmp"
        target = s.write(base / "current/file.txt", "temporary")
        preserved = s.write(base / "unrelated/evidence.txt", "retain")
        plan = module.cleanup_paths(root, ["tests/.tmp/current"], allowed_base=base)
        assert plan["status"] == "PLANNED" and target.exists()
        result = module.cleanup_paths(root, ["tests/.tmp/current"], allowed_base=base, dry_run=False)
        assert result["status"] == "CLEANED" and not target.exists()
        assert preserved.read_bytes() == b"retain"
        assert (root / "tracked.txt").read_bytes() == b"public source\n"
        assert s.git(root, "rev-parse", "HEAD") == lab.head

    @pytest.mark.parametrize("forbidden", [".", ".git", "tracked.txt", "../outside", "tests/.tmp/../../tracked.txt"])
    def test_c35_cleanup_prevalidates_all_targets_before_first_delete(self, lab, forbidden):
        module = environment()
        root = lab.source
        base = root / "tests/.tmp"
        s.write(base / "valid/file.txt", "must survive rejection")
        before = s.inventory(root)
        rejected(module, lambda: module.cleanup_paths(root, ["tests/.tmp/valid", forbidden],
                 allowed_base=base, dry_run=False), ("INVALID_INPUT", "PATH_BOUNDARY"))
        assert s.inventory(root) == before

    def test_c36_protected_descendant_and_link_boundary_are_preserved(self, lab):
        module = environment()
        root = lab.source
        base = root / "tests/.tmp"
        s.write(base / "bound/approval.json", "preserved")
        rejected(module, lambda: module.cleanup_paths(root, ["tests/.tmp/bound"], allowed_base=base,
                 protected_paths=["tests/.tmp/bound/approval.json"], dry_run=False), ("PATH_BOUNDARY",))
        outside = s.write(lab.directory / "outside-data/keep.txt", "outside").parent
        link = base / "permitted-link"
        link.symlink_to(outside, target_is_directory=True)
        result = module.cleanup_paths(root, ["tests/.tmp/permitted-link"], allowed_base=base, dry_run=False)
        assert result["status"] == "CLEANED" and not link.is_symlink()
        assert (outside / "keep.txt").read_bytes() == b"outside"
        link.symlink_to(outside, target_is_directory=True)
        before = s.inventory(lab.directory)
        rejected(module, lambda: module.cleanup_paths(root, ["tests/.tmp/permitted-link/keep.txt"],
                 allowed_base=base, dry_run=False), ("PATH_BOUNDARY",))
        assert s.inventory(lab.directory) == before


class TestCliAndContract:
    def test_c37_thin_preflight_cli_matches_api_and_does_not_write_inputs(self, lab):
        module = environment()
        req = s.request(lab)
        obs = s.observations(module, req)
        req_file = s.write(lab.directory / "request.json", s.canonical(req))
        obs_file = s.write(lab.directory / "observations.json", s.canonical(obs))
        before = s.inventory(lab.directory)
        run = s.command([sys.executable, ROOT / s.WORKFLOW, "preflight", "--request", req_file,
                         "--observations", obs_file], ROOT)
        report = json.loads(run.stdout)
        assert report == module.evaluate_preflight(req, obs)
        assert s.inventory(lab.directory) == before
        report_file = s.write(lab.directory / "report.json", s.canonical(report))
        bindings_file = s.write(lab.directory / "bindings.json", s.canonical(req["bindings"]))
        verified = s.command([sys.executable, ROOT / s.WORKFLOW, "verify-preflight", "--report", report_file,
                              "--expected-request-sha256", s.sha(s.canonical(req)), "--bindings", bindings_file], ROOT)
        json.loads(verified.stdout)
        checkout = s.command([sys.executable, ROOT / s.WORKFLOW, "inspect-checkout",
                              "--root", lab.source, "--expected-head", lab.head], ROOT)
        assert json.loads(checkout.stdout)["head"] == lab.head

    def test_c38_cli_rejected_blocked_and_malformed_exit_contract(self, lab):
        module = environment()
        req = s.request(lab)
        obs = s.observations(module, req)
        obs["capabilities"] = []
        req_file = s.write(lab.directory / "request.json", s.canonical(req))
        obs_file = s.write(lab.directory / "observations.json", s.canonical(obs))
        argv = [sys.executable, ROOT / s.WORKFLOW, "preflight", "--request", req_file, "--observations", obs_file]
        blocked = s.command(argv, ROOT, check=False)
        assert blocked.returncode == 1 and json.loads(blocked.stdout)["status"] == "BLOCKED"
        s.write(req_file, "{invalid")
        malformed = s.command(argv, ROOT, check=False)
        assert malformed.returncode == 2
        json.loads(malformed.stdout or malformed.stderr)
        assert b"Traceback" not in malformed.stdout + malformed.stderr
        req_file.unlink()
        absent = s.command(argv, ROOT, check=False)
        assert absent.returncode == 2

    def test_c39_capture_hydrate_cli_round_trip(self, lab):
        initializer()
        lab.initialized(platforms=("codex",))
        target = lab.clone()
        before = s.inventory(lab.source)
        captured = s.command([sys.executable, ROOT / s.HYDRATE, "capture", "--source-root", lab.source,
                              "--input", lab.input, "--expected-input-sha256", s.sha(lab.input.read_bytes())], ROOT)
        snapshot = json.loads(captured.stdout)
        assert s.inventory(lab.source) == before
        file = s.write(lab.directory / "initialization.json", s.canonical(snapshot))
        hydrated = s.command([sys.executable, ROOT / s.HYDRATE, "hydrate", "--source-root", lab.source,
                              "--target-root", target, "--initialization", file,
                              "--expected-initialization-sha256", s.sha(file.read_bytes()),
                              "--allowed-target-base", lab.derived, "--platform", "codex",
                              "--expected-target-head", lab.head], ROOT)
        assert json.loads(hydrated.stdout)["status"] == "HYDRATED"
        assert file.read_bytes() == s.canonical(snapshot)
        assert (target / ".codex/agents/worker.toml").exists()

    def test_c40_public_reference_and_portable_boundaries(self):
        environment()
        reference = ROOT / "agent-discipline/skills/agent-workflow/references/workflow-environment.md"
        assert reference.is_file()
        text = reference.read_text(encoding="utf-8")
        for name in (*s.PUBLIC_FUNCTIONS, "capture_initialization", "hydrate_checkout"):
            assert name in text, f"Public reference does not document {name}"
        for concept in ("Codex", "Claude", "OpenCode", "S32DS"):
            assert concept.lower() in text.lower()
        assert "isolation" in text.lower() and "evidence" in text.lower()
        for path in [ROOT / s.WORKFLOW, ROOT / s.HYDRATE]:
            source = path.read_text(encoding="utf-8")
            assert source.startswith("# =================================================================================\n")
            assert "# SPDX short identifier / SPDX 短标识符：MIT" in source
            assert f"# File:        {path.name}" in source
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    names = [item.name.split(".")[0] for item in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                assert not set(names) & {"requests", "numpy", "pandas", "yaml", "pexpect"}

    def test_c41_requirements_cases_and_scripts_correspond(self):
        requirements = (ROOT / "tests/doc/reference/agent/workflow-environment-requirements.md").read_text(encoding="utf-8")
        cases = (ROOT / "tests/doc/reference/agent/workflow-environment-cases.md").read_text(encoding="utf-8")
        for number in range(1, 24):
            assert f"R{number:02d}" in requirements
        for number in range(1, 44):
            assert f"ENV-{number:02d}" in cases
        index = (ROOT / "tests/doc/README.md").read_text(encoding="utf-8")
        assert "workflow-environment-requirements.md" in index
        assert "workflow-environment-cases.md" in index

    def test_c42_full_selected_chain_and_stale_dispatch_sentinel(self, lab):
        module = environment()
        hydration = initializer()
        lab.initialized(platforms=("codex",))
        snapshot = s.capture(hydration, lab)
        target = lab.derived / "full-chain"
        module.create_isolated_checkout(lab.source, target, allowed_target_base=lab.derived,
                                       branch="codex/full-chain", expected_source_head=lab.head)
        assert s.hydrate(hydration, lab, target, snapshot)["status"] == "HYDRATED"
        req = s.request(lab, root=target)
        obs = s.observations(module, req)
        # Real command availability evidence, distinct from OS input isolation.
        probe = module.probe_command([sys.executable, "-c", "print('bounded available')"],
                                      target, approved=True, context="host")
        assert probe["status"] == "available"
        report = module.evaluate_preflight(req, obs)
        marker = target / ".agent-state/agent-loop/current/evidence/dispatch.json"
        sentry_dispatch(module, report, req, marker)
        bound = module.snapshot_evidence(target, [marker.relative_to(target).as_posix()], bindings=req["bindings"])
        assert module.verify_evidence(target, bound, bindings=req["bindings"]) is None
        changed = {**req["bindings"], "contract_sha256": "e" * 64}
        next_marker = marker.with_name("must-not-dispatch.json")
        rejected(module, lambda: sentry_dispatch(module, report, req, next_marker, bindings=changed), ("STALE_IDENTITY",))
        assert not next_marker.exists()
        s.write(marker, "bound evidence changed")
        rejected(module, lambda: module.verify_evidence(target, bound, bindings=req["bindings"]), ("STALE_IDENTITY",))

    def test_c43_existing_workflow_and_vendor_boundaries_remain_authoritative(self):
        pinned = {
            "agent-discipline/workflow-contract.json": "771a6c196e38c211d5bec6ea01f5e6b7013a3296",
            "agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json": "e0ef077af1ae5f7d74e04980d4b1d7531579c214",
            "agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json": "fa70dc621091d82b01d136632e6e75d99a96d157",
            "agent-discipline/skills/agent-workflow/scripts/workflow_transition.py": "cc623a09218fdc6272f59759307e4c3e4353b6c7",
            "agent-discipline/skills/agent-workflow/scripts/workflow_evidence.py": "1b26549af9fa59e1c4eb704b4aef432da50e0289",
        }
        for path, blob in pinned.items():
            assert s.git(ROOT, "rev-parse", "HEAD:" + path) == blob
            committed = s.command(["git", "show", "HEAD:" + path], ROOT).stdout
            # Git checkout may materialize CRLF on Windows. Compare every other
            # byte exactly; neither the script nor this assertion edits source.
            assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n")
        role = (ROOT / "agent-discipline/subagents/tester.md").read_text(encoding="utf-8")
        assert "tools/blackbox_e2e.py" in role and "independent third-party agent CLI" in role
        assert "ConfigTools exit code 0 AND zero SEVERE" in role
        assert "embedded" in role and "NOT a valid black box" in role
