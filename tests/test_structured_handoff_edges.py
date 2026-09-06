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
# File:        test_structured_handoff_edges.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Protocol boundary cases for repair, deadlines and public CLI.
# =================================================================================

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "agent-discipline/skills/agent-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from structured_handoff_fixture import Lifecycle
import structured_handoff as core


@pytest.fixture
def life(tmp_path):
    return Lifecycle(tmp_path / "repo")


@pytest.mark.parametrize("value", ["0", "-5", "NaN", "Infinity", "not-seconds"])
def test_invalid_git_deadline_is_rejected_before_subprocess(life, monkeypatch, value):
    monkeypatch.setenv("RTD_HANDOFF_GIT_TIMEOUT_SECONDS", value)
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid command deadline must be rejected before any subprocess")
    monkeypatch.setattr(subprocess, "run", forbidden)
    code, result = life.validate(life.k)
    assert code == 1, result
    assert result["violations"][0]["rule_id"] == "COMMAND_TIMEOUT_CONFIGURATION"


def test_command_deadline_is_configurable(life, monkeypatch):
    import structured_handoff_refs as refs
    original = subprocess.run
    seen = []
    def capture(*args, **kwargs):
        seen.append(kwargs["timeout"])
        return original(*args, **kwargs)
    monkeypatch.setenv("RTD_HANDOFF_GIT_TIMEOUT_SECONDS", "27.5")
    monkeypatch.setattr(subprocess, "run", capture)
    assert life.validate(life.k)[0] == 0
    assert seen and set(seen) == {27.5}


def test_root_cwd_is_valid_but_dot_file_paths_are_not():
    core.validate_definition(".", "CwdPath")
    core.validate_definition("checks", "CwdPath")
    for value in ("./checks", "..", "/root"):
        with pytest.raises(core.ProtocolError):
            core.validate_definition(value, "CwdPath")
    with pytest.raises(core.ProtocolError):
        core.validate_definition(".", "Path")


def repair(life, original):
    code, _ = life.validate(original, result_name=".agent-state/rejected.json")
    assert code == 1
    raw = (life.root / ".agent-state/rejected.json").read_bytes()
    guard = json.loads(raw)
    rejection = {"kind": "guard-result", "artifact_id": guard["artifact_id"], "path": ".agent-state/rejected.json", "sha256": hashlib.sha256(raw).hexdigest()}
    life.objects[guard["artifact_id"]] = guard
    original_body = life.objects[original["artifact_id"]]
    p = original_body["payload"]
    return life.artifact("delivery-repair", {"dispatch_id": "repair-followup", "original": original, "rejection": rejection, "lane": life.worker_lane,
          "replacement_output": ".agent-state/replacement.json", "preserve_tip": p["implementation_tip"]["commit"],
          "preserve_candidate_index": None, "preserve_correction_count": p["implementation_index"], "preserve_review_id": None, "business_verdict_change_allowed": False},
          [original, rejection], consumer_role="worker", visibility="public-task"), rejection


def test_worker_shape_only_delivery_repair_and_new_dispatch_response(life):
    bad = copy.deepcopy(life.objects[life.ir["artifact_id"]])
    bad["unexpected_format_member"] = "Remove only this member"
    original = life.store(bad)
    envelope, rejection = repair(life, original)
    code, result = life.validate(envelope, [rejection], result_name=".agent-state/repair-central.json")
    assert code == 0, result
    raw = (life.root / ".agent-state/repair-central.json").read_bytes()
    central = {"path": ".agent-state/repair-central.json", "sha256": hashlib.sha256(raw).hexdigest()}
    code, result = life.validate(envelope, [rejection], view="consumer-local", central=central)
    assert code == 0, result
    fixed = copy.deepcopy(bad)
    del fixed["unexpected_format_member"]
    fixed["artifact_id"] = "replacement-report"
    fixed["payload"]["dispatch_id"] = "repair-followup"
    fixed["predecessors"].append(envelope)
    fixed["replaces"] = {"original": original, "guard_result": rejection}
    code, result = life.validate(life.store(fixed), [rejection])
    assert code == 0, result
    fixed["artifact_id"] = "replacement-business-change"
    fixed["payload"]["implementation_index"] = 1
    assert life.validate(life.store(fixed), [rejection])[0] == 1


@pytest.mark.parametrize("view", ["orchestrator-full", "consumer-local"])
def test_real_public_guard_adapter(life, view):
    ref = life.wlaunch
    assert life.validate(ref, result_name=".agent-state/central.json")[0] == 0
    raw = (life.root / ".agent-state/central.json").read_bytes()
    central = {"path": ".agent-state/central.json", "sha256": hashlib.sha256(raw).hexdigest()} if view == "consumer-local" else None
    context = life.write(".agent-state/cli-context.json", core.canonical_bytes(life.context(ref, central=central)))
    argv = [sys.executable, str(SCRIPTS / "handoff_guard.py"), "validate-artifact", "--artifact", str(life.root / ref["path"]),
            "--expected-sha256", ref["sha256"], "--context", str(context), "--view", view, "--result", str(life.root / ".agent-state/cli-result.json")]
    result = subprocess.run(argv, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    argv[argv.index("--expected-sha256") + 1] = "e" * 64
    argv[-1] = str(life.root / ".agent-state/cli-rejected.json")
    result = subprocess.run(argv, capture_output=True, text=True)
    assert result.returncode == 1, result.stderr


def test_hardlink_output_alias_cannot_replace_source(life):
    source = life.root / "src/component.py"
    alias = life.root / ".agent-state/hardlink.json"
    os.link(source, alias)
    before = source.read_bytes()
    assert life.validate(life.k, result_name=".agent-state/hardlink.json")[0] == 2
    assert source.read_bytes() == before


def test_coverage_join_requires_actual_paths_and_public_edges(life):
    ref = life.candidate(0)
    a = copy.deepcopy(life.objects[ref["artifact_id"]])
    impact = json.loads((life.root / life.impact["path"]).read_text("utf-8"))
    impact["public_dependency_edges"] = []
    updated_impact = life.evidence("impact-set", impact)
    test_report = copy.deepcopy(life.objects[life.tr["artifact_id"]])
    test_report["artifact_id"] = "new-test-report"
    test_report["payload"]["impact_set"] = updated_impact
    tr = life.store(test_report)
    a["artifact_id"] = "missing-edge-candidate"
    a["predecessors"] = [tr if r == life.tr else r for r in a["predecessors"]]
    a["payload"]["impact_set"] = updated_impact
    join = json.loads((life.root / a["payload"]["coverage_join"]["path"]).read_text("utf-8"))
    join["impact_set_sha256"] = updated_impact["sha256"]
    a["payload"]["coverage_join"] = life.evidence("coverage-join", join)
    assert life.validate(life.store(a))[0] == 1


def test_relative_cli_arguments_resolve_from_actual_worktree(life):
    ref = life.k
    life.write(".agent-state/relative-context.json", core.canonical_bytes(life.context(ref)))
    result = subprocess.run([sys.executable, str(SCRIPTS / "handoff_guard.py"), "validate-artifact",
             "--artifact", ref["path"], "--expected-sha256", ref["sha256"], "--context", ".agent-state/relative-context.json",
             "--view", "orchestrator-full", "--result", ".agent-state/relative-result.json"], cwd=life.root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_manifest_version_is_exact_governor_contract_version(life):
    value = copy.deepcopy(life.objects[life.ir["artifact_id"]])
    manifest = json.loads((life.root / value["payload"]["manifest"]["path"]).read_text("utf-8"))
    manifest["contract_version"] = 79
    value["payload"]["manifest"] = life.evidence("manifest", manifest)
    assert life.validate(life.store(value))[0] == 1


def test_two_exact_revision_acknowledgements_allow_new_ready(life):
    old_k = life.kref
    k1 = copy.deepcopy(life.objects[life.k["artifact_id"]])
    k1["artifact_id"] = "contract-revision-one"
    k1["payload"]["revision"] = {"number": 1, "predecessor": life.k, "authority": life.evidence("authority", b"Explicit public clarification"),
             "reason": "Clarify public requirement", "changed_authority_ids": ["A"], "affected_requirement_ids": ["R"]}
    k1["predecessors"] = [life.k]
    new_k = life.store(k1)
    life.kref = {"revision": 1, "path": new_k["path"], "sha256": new_k["sha256"]}
    acknowledgements = []
    launches = []
    for initial, report in [(life.tlaunch, life.tr), (life.wlaunch, life.ir)]:
        launch = copy.deepcopy(life.objects[initial["artifact_id"]])
        launch["artifact_id"] += "-revised"
        launch["task_contract"] = life.kref
        launch["payload"].update(mode="K_REVISION", previous_launch=initial, revision_ack_required=True, dispatch_id=launch["artifact_id"])
        launch["predecessors"] = [new_k, initial]
        launches.append(life.store(launch))
        ack = copy.deepcopy(life.objects[report["artifact_id"]])
        ack["artifact_id"] += "-ack"
        ack["task_contract"] = life.kref
        ack["predecessors"] = [launches[-1]]
        ack["payload"].update(status="K_ACK", dispatch_id=launch["payload"]["dispatch_id"], revision_ack={"old_contract": old_k,
              "new_contract": life.kref, "verified_sha256": life.kref["sha256"], "current_tip": life.i if report == life.ir else life.t,
              "invalidated_receipt_ids": ["old-receipt"], "retained_work": "Keep source", "resume_requirement_ids": ["R"]})
        acknowledgements.append(life.store(ack))
    ready = copy.deepcopy(life.objects[life.ir["artifact_id"]])
    ready["artifact_id"] = "implementation-after-acks"
    ready["task_contract"] = life.kref
    ready["payload"]["dispatch_id"] = life.objects[launches[1]["artifact_id"]]["payload"]["dispatch_id"]
    ready["predecessors"] = [launches[1]]
    ref = life.store(ready)
    code, result = life.validate(ref, acknowledgements)
    assert code == 0, result
    assert life.validate(ref, acknowledgements[:1])[0] == 1


def test_repair_cannot_disclose_private_guard_result(life):
    bad = copy.deepcopy(life.objects[life.ir["artifact_id"]])
    bad["extra"] = True
    original = life.store(bad)
    envelope, rejection = repair(life, original)
    private = copy.deepcopy(life.objects[rejection["artifact_id"]])
    private["visibility"] = "orchestrator-confidential"
    raw = core.canonical_bytes(private)
    life.write(rejection["path"], raw)
    changed = {**rejection, "sha256": hashlib.sha256(raw).hexdigest()}
    value = copy.deepcopy(life.objects[envelope["artifact_id"]])
    value["payload"]["rejection"] = changed
    value["predecessors"] = [original, changed]
    assert life.validate(life.store(value), [changed], view="consumer-local")[0] == 1


def test_evidence_write_failure_leaves_no_checked_receipt(life, monkeypatch):
    def fail(_):
        raise OSError("synthetic flush failure")
    monkeypatch.setattr(os, "fsync", fail)
    code, result = life.validate(life.k, result_name=".agent-state/unwritten.json")
    assert code == 2 and result is None
    assert not (life.root / ".agent-state/unwritten.json").exists()


def test_missing_full_chain_and_forged_command_result_are_rejected(life):
    value = copy.deepcopy(life.objects[life.tr["artifact_id"]])
    value["payload"]["prevalidation"] = [r for r in value["payload"]["prevalidation"] if r["purpose"] != "FULL_CHAIN"]
    assert life.validate(life.store(value))[0] == 1
    value = copy.deepcopy(life.objects[life.tr["artifact_id"]])
    value["payload"]["prevalidation"][0]["exit_code"] = 23
    assert life.validate(life.store(value))[0] == 1


def test_approval_freezes_exact_test_report_not_only_test_commit(life):
    ref = life.candidate(0)
    report = copy.deepcopy(life.objects[life.tr["artifact_id"]])
    report["artifact_id"] = "alternate-test-report"
    alternate = life.store(report)
    candidate = copy.deepcopy(life.objects[ref["artifact_id"]])
    candidate["predecessors"] = [alternate if r == life.tr else r for r in candidate["predecessors"]]
    assert life.validate(life.store(candidate))[0] == 1


@pytest.mark.parametrize("mutation", ["argv", "unselected", "duplicate"])
def test_spec_finding_frozen_execution_is_an_exact_unique_join(life, mutation):
    life.candidate(0)
    report = life.report("PASS")
    value = copy.deepcopy(life.objects[report["artifact_id"]])
    run = value["payload"]["execution"][0]
    if mutation == "argv":
        run["argv"] = ["python", "unselected_program.py"]
        body = {k: v for k, v in run.items() if k not in {"purpose", "result"}}
        run["result"] = life.evidence("command-result", {"schema_version": "1.0", **body})
    elif mutation == "unselected":
        value["payload"]["execution"].append(life.run("unselected-check"))
    else:
        value["payload"]["execution"].append(copy.deepcopy(run))
    code, result = life.validate(life.store(value))
    assert code == 1, result


def revise_lifecycle(life):
    old_k = life.kref
    k1 = copy.deepcopy(life.objects[life.k["artifact_id"]])
    k1["artifact_id"] = "contract-k1"
    k1["predecessors"] = [life.k]
    k1["payload"]["revision"] = {"number": 1, "predecessor": life.k, "authority": life.evidence("authority", b"Explicit K1 clarification"),
            "reason": "Public clarification", "changed_authority_ids": ["A"], "affected_requirement_ids": ["R"]}
    new_k = life.store(k1)
    life.kref = {"revision": 1, "path": new_k["path"], "sha256": new_k["sha256"]}
    acks = []
    for launch_ref, report_ref in [(life.tlaunch, life.tr), (life.wlaunch, life.ir)]:
        launch = copy.deepcopy(life.objects[launch_ref["artifact_id"]])
        launch["artifact_id"] += "-k1"
        launch["task_contract"] = life.kref
        launch["payload"].update(mode="K_REVISION", previous_launch=launch_ref, revision_ack_required=True, dispatch_id=launch["artifact_id"])
        launch["predecessors"] = [new_k, launch_ref]
        current_launch = life.store(launch)
        report = copy.deepcopy(life.objects[report_ref["artifact_id"]])
        report["artifact_id"] += "-k1"
        report["task_contract"] = life.kref
        report["predecessors"] = [current_launch]
        report["payload"]["dispatch_id"] = launch["payload"]["dispatch_id"]
        ack = copy.deepcopy(report)
        ack["artifact_id"] += "-ack"
        ack["payload"].update(status="K_ACK", revision_ack={"old_contract": old_k, "new_contract": life.kref,
              "verified_sha256": life.kref["sha256"], "current_tip": life.t if report_ref == life.tr else life.i,
              "invalidated_receipt_ids": ["old-receipt"], "retained_work": "Keep implementation", "resume_requirement_ids": ["R"]})
        acks.append(life.store(ack))
        if report_ref == life.tr:
            impact = json.loads((life.root / life.impact["path"]).read_text("utf-8"))
            impact["task_contract"] = life.kref
            life.impact = life.evidence("impact-set", impact)
            report["payload"]["impact_set"] = life.impact
            life.tr = life.store(report)
        else:
            life.ir = life.store(report)
    approval = copy.deepcopy(life.objects[life.human["artifact_id"]])
    approval["artifact_id"] = "approval-k1"
    approval["task_contract"] = life.kref
    approval["predecessors"] = [life.tr]
    life.human = life.store(approval)
    return acks


def test_spec_finding_k1_local_correction_uses_central_private_ack_fact(life, monkeypatch):
    acks = revise_lifecycle(life)
    life.candidate(0)
    report = life.report("IMPLEMENTATION_FAIL")
    correction = life.correction(1, report)
    assert life.validate(correction, [report, acks[1]])[0] == 1
    code, result = life.validate(correction, [report, *acks], result_name=".agent-state/k1-central.json")
    assert code == 0, result
    raw = (life.root / ".agent-state/k1-central.json").read_bytes()
    assert acks[0]["path"].encode() not in raw
    forbidden = {life.root / ref["path"] for ref in [report, *acks]}
    for path in forbidden:
        path.unlink()
    original_read = Path.read_bytes
    def public_only(path):
        assert path not in forbidden, "Worker attempted to read confidential ACK/report"
        return original_read(path)
    monkeypatch.setattr(Path, "read_bytes", public_only)
    central = {"path": ".agent-state/k1-central.json", "sha256": hashlib.sha256(raw).hexdigest()}
    code, result = life.validate(correction, view="consumer-local", central=central)
    assert code == 0, result
    central["sha256"] = "f" * 64
    assert life.validate(correction, view="consumer-local", central=central)[0] == 1


def stop_terminal(life, candidate, implementation=None):
    tip = life.objects[candidate["artifact_id"]]["payload"]["candidate"] if candidate else None
    current = life.objects[implementation["artifact_id"]]["payload"] if implementation else None
    preserved = current["implementation_tip"]["commit"] if current else (life.i if candidate else None)
    index = life.objects[candidate["artifact_id"]]["payload"]["candidate_index"] if candidate else None
    count = current["implementation_index"] if current else (index or 0)
    decision = life.artifact("human-decision", {"gate": "FINAL", "decision": "STOP", "subject_sha": tip["commit"] if tip else None,
               "authority_actor": "Human", "source": {"kind": "human-command", "locator": "stop-command", "raw": life.evidence("authority", b"Stop now"),
               "created_at": "2026-09-06T02:00:00Z", "updated_at": "2026-09-06T02:00:00Z", "deleted": False}, "reason": "Human stopped before execution"},
               [candidate] if candidate else [], visibility="terminal-review")
    launch = life.artifact("reviewer-launch", {"dispatch_id": "stop-review-dispatch", "review_id": "stop-review", "terminal_reason": "HUMAN_STOP",
             "candidate": tip, "last_implementation": preserved, "source_reports": [decision], "output_path": ".agent-state/stop-review.json",
             "review_once": True, "implementation_write_allowed": False, "test_write_allowed": False, "reopen_correction_allowed": False},
             ([decision, candidate] if candidate else [decision]) + ([implementation] if implementation else []))
    review = life.artifact("reviewer-report", {"dispatch_id": "stop-review-dispatch", "review_id": "stop-review", "verdict": "APPROVED", "findings": [],
             "lessons": life.evidence("lesson", b"Human stop preserved work"), "salvage": []}, [launch])
    return life.artifact("terminal-record", {"result": "FAILURE", "review": review, "candidate_index": index, "correction_count": count,
             "accepted_candidate": None, "preserved_implementation": preserved, "disposition": "RECORD_FAILURE", "pr": None,
             "final_decision": decision, "remaining_defects": ["Stopped before execution"], "salvage": []}, [review, decision])


@pytest.mark.parametrize("has_candidate", [False, True])
def test_spec_finding_human_stop_needs_no_invented_tester_report(life, has_candidate):
    terminal = stop_terminal(life, life.candidate(0) if has_candidate else None)
    assert not any(a["artifact_kind"] == "tester-confidential-report" for a in life.objects.values())
    code, result = life.validate(terminal)
    assert code == 0, result
    forged = copy.deepcopy(life.objects[terminal["artifact_id"]])
    forged["artifact_id"] += "-wrong-count"
    forged["payload"]["correction_count"] = 2
    assert life.validate(life.store(forged))[0] == 1


@pytest.mark.parametrize("report_kind", ["tester-confidential-report", "reviewer-report"])
def test_spec_finding_report_repair_preserves_nonzero_candidate_identity(life, report_kind):
    life.candidate(0)
    first = life.report("IMPLEMENTATION_FAIL")
    correction = life.correction(1, first)
    prior = life.i
    life.i = life.commit(prior, "src/component.py", "arbitrary correction")
    life.ir = life.implementation(1, life.i, prior, correction)
    candidate = life.candidate(1)
    report = life.report("PASS")
    if report_kind == "reviewer-report":
        terminal = life.terminal(report, True, 1)
        report = life.objects[terminal["artifact_id"]]["payload"]["review"]
    original = copy.deepcopy(life.objects[report["artifact_id"]])
    original["extra_format_member"] = True
    bad = life.store(original)
    code, _ = life.validate(bad, [first], result_name=".agent-state/report-rejection.json")
    assert code == 1
    raw = (life.root / ".agent-state/report-rejection.json").read_bytes()
    guard = json.loads(raw)
    rejection = {"kind": "guard-result", "artifact_id": guard["artifact_id"], "path": ".agent-state/report-rejection.json", "sha256": hashlib.sha256(raw).hexdigest()}
    body = {"dispatch_id": "report-repair-dispatch", "original": bad, "rejection": rejection, "lane": life.test_lane if report_kind == "tester-confidential-report" else life.lane("reviewer"),
            "replacement_output": ".agent-state/repaired-report.json", "preserve_tip": life.objects[candidate["artifact_id"]]["payload"]["candidate"]["commit"],
            "preserve_candidate_index": 1, "preserve_correction_count": 1, "preserve_review_id": original["payload"].get("review_id"), "business_verdict_change_allowed": False}
    envelope = life.artifact("delivery-repair", body, [bad, rejection, *original["predecessors"]], consumer_role=original["producer_role"], visibility=original["visibility"])
    code, result = life.validate(envelope, [first])
    assert code == 0, result
    fixed = copy.deepcopy(original)
    del fixed["extra_format_member"]
    fixed["artifact_id"] += "-replacement"
    fixed["payload"]["dispatch_id"] = body["dispatch_id"]
    fixed["predecessors"].append(envelope)
    fixed["replaces"] = {"original": bad, "guard_result": rejection}
    code, result = life.validate(life.store(fixed), [first])
    assert code == 0, result
    wrong = copy.deepcopy(life.objects[envelope["artifact_id"]])
    wrong["artifact_id"] += "-wrong-source"
    wrong["payload"]["preserve_tip"] = life.i
    assert life.validate(life.store(wrong), [first])[0] == 1


@pytest.mark.parametrize("candidate_index", [0, 2])
def test_stop_between_candidate_stages_preserves_latest_implementation(life, candidate_index):
    failures = []
    for index in range(candidate_index + 1):
        candidate = life.candidate(index)
        failure = life.report("IMPLEMENTATION_FAIL")
        failures.append(failure)
        correction = life.correction(index + 1, failure)
        prior = life.i
        life.i = life.commit(prior, "src/component.py", "completed correction " + str(index + 1))
        life.ir = life.implementation(index + 1, life.i, prior, correction)
    terminal = stop_terminal(life, candidate, life.ir)
    code, result = life.validate(terminal, failures)
    assert code == 0, result
    payload = life.objects[terminal["artifact_id"]]["payload"]
    assert payload["candidate_index"] == candidate_index
    assert payload["correction_count"] == candidate_index + 1
    assert payload["preserved_implementation"] == life.i


@pytest.mark.parametrize("mutation", ["stale-tip", "foreign-tip", "stale-count", "foreign-report"])
def test_stop_between_stages_rejects_stale_or_foreign_identity(life, mutation):
    candidate = life.candidate(0)
    failure = life.report("IMPLEMENTATION_FAIL")
    correction = life.correction(1, failure)
    prior = life.i
    life.i = life.commit(prior, "src/component.py", "latest correction")
    life.ir = life.implementation(1, life.i, prior, correction)
    terminal = stop_terminal(life, candidate, life.ir)
    value = copy.deepcopy(life.objects[terminal["artifact_id"]])
    if mutation == "stale-count":
        value["payload"]["correction_count"] = 0
    else:
        review_ref = value["payload"]["review"]
        review = copy.deepcopy(life.objects[review_ref["artifact_id"]])
        launch_ref = review["predecessors"][0]
        launch = copy.deepcopy(life.objects[launch_ref["artifact_id"]])
        if mutation == "foreign-report":
            foreign = copy.deepcopy(life.objects[life.ir["artifact_id"]])
            foreign["artifact_id"] += "-foreign"
            foreign["payload"]["lane"]["lane_id"] = "another-worker-lane"
            foreign_ref = life.store(foreign)
            launch["predecessors"] = [foreign_ref if ref == life.ir else ref for ref in launch["predecessors"]]
        else:
            wrong = prior if mutation == "stale-tip" else life.commit(life.g, "src/component.py", "foreign sibling")
            launch["payload"]["last_implementation"] = wrong
            value["payload"]["preserved_implementation"] = wrong
        updated_launch = life.store(launch)
        review["predecessors"] = [updated_launch]
        updated_review = life.store(review)
        value["payload"]["review"] = updated_review
        value["predecessors"] = [updated_review if ref == review_ref else ref for ref in value["predecessors"]]
    code, result = life.validate(life.store(value), [failure])
    assert code == 1, result


def test_quality_evidence_cache_cannot_relabel_opaque_authority(life):
    value = copy.deepcopy(life.objects[life.wlaunch["artifact_id"]])
    authority = life.objects[life.k["artifact_id"]]["payload"]["authorities"][0]["snapshot"]
    value["payload"]["salvage"] = [{"patch": authority, "source_commit": life.i,
             "disclosure_review": {**authority, "evidence_type": "disclosure-review"}}]
    code, result = life.validate(life.store(value), [life.k])
    assert code == 1, result


@pytest.mark.parametrize("path", ["中文模块.py", " leading.py", " 子目录/文件.py"])
def test_quality_changed_paths_preserve_raw_unicode_and_leading_spaces(life, path):
    from structured_handoff_refs import ReferenceGraph
    core.validate_definition(path, "Path")
    commit = life.commit(life.g, path, "arbitrary path content")
    graph = ReferenceGraph(life.context(life.k), "orchestrator-full")
    graph.verify_environment()
    assert graph.changed_paths(commit) == {path}


@pytest.mark.parametrize("weakness", ["shape", "reference-walk"])
def test_quality_artifact_cache_upgrades_weak_original_before_normal_read(life, weakness):
    from structured_handoff_refs import ReferenceGraph
    value = copy.deepcopy(life.objects[life.wlaunch["artifact_id"]])
    if weakness == "shape":
        value["extra_member"] = True
    else:
        value["predecessors"].append({"kind": "worker-launch", "artifact_id": "missing-reference", "path": ".agent-state/missing.json", "sha256": "a" * 64})
    ref = life.store(value)
    graph = ReferenceGraph(life.context(ref), "orchestrator-full")
    graph.artifact(ref, repair_original=True)
    with pytest.raises(core.ProtocolError) as error:
        graph.artifact(ref)
    assert error.value.rule_id == ("EXTRA_MEMBER" if weakness == "shape" else "REFERENCE_MISSING")


def test_quality_artifact_cache_rechecks_public_visibility_on_read(life):
    from structured_handoff_refs import ReferenceGraph
    assert life.validate(life.k, result_name=".agent-state/guard-view.json")[0] == 0
    path = life.root / ".agent-state/guard-view.json"
    value = json.loads(path.read_text("utf-8"))
    value["visibility"] = "orchestrator-confidential"
    raw = core.canonical_bytes(value)
    path.write_bytes(raw)
    ref = {"kind": "guard-result", "artifact_id": value["artifact_id"], "path": ".agent-state/guard-view.json", "sha256": hashlib.sha256(raw).hexdigest()}
    context = life.context(life.wlaunch, [ref])
    graph = ReferenceGraph(context, "orchestrator-full")
    graph.artifact(ref, allow_private=True)
    with pytest.raises(core.ProtocolError) as error:
        graph.artifact(ref, allow_private=False)
    assert error.value.rule_id == "PRIVATE_REFERENCE"
