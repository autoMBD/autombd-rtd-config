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
# File:        test_isolation_compliance.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-13
# Version:     0.1.0
# Description: Owner W5 dispatch, evidence, reducer and terminal acceptance.
# =================================================================================


"""Controlled records test actual guards; synthetic Human data is never authority."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/fixtures/isolation-compliance"))
from isolation_support import (DISPATCH_PHASES, PHASES, IsolationHistory, digest,
    environment, load_schema, reducer, verifier, workflow)
from structured_handoff_schema import ProtocolError, validate_definition
import workflow_gate


@pytest.fixture
def history(tmp_path):
    assert tmp_path.resolve().is_relative_to((ROOT / "tests/.tmp").resolve())
    return IsolationHistory(tmp_path / "history")


def rewrite(h, ref, mutate):
    body = copy.deepcopy(h.objects[ref["artifact_id"]])
    mutate(body)
    return h.raw_store(body)


def rejected(h, ref):
    code, result = h.validate(ref)
    assert code == 1 and result["status"] == "REJECTED", result
    assert result["command_started"] == "NOT_STARTED"
    return result


def terminal_history(h, *, status=None, result=True, candidate=True, reason=None):
    h.ready()
    if candidate:
        h.candidate_ready()
    tested = h.report("PASS") if result and candidate else None
    if tested:
        h.bridge.consume(tested)
    h.finding_status = status
    launch, review = h.review_terminal(tested, reason=reason)
    return tested, launch, review


def test_ic09_w5_optin_preserves_closed_lifecycle_and_old_versions(tmp_path):
    def validate(value):
        path = tmp_path / "declaration.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        workflow_gate.validate_contract(value, contract_path=path)
    value = json.loads((ROOT / "agent-discipline/workflow-contract.json").read_bytes())
    assert value == workflow(5), "R01/R17/R18: active declaration must explicitly opt in to W5."
    validate(value)
    for version in (2, 3, 4):
        old = workflow(version)
        validate(old)
        invalid = copy.deepcopy(old)
        invalid["isolation_compliance"] = {"version": "1.0", "enabled": True}
        with pytest.raises(workflow_gate.WorkflowValidationError):
            validate(invalid)
    invalid = copy.deepcopy(value)
    invalid["isolation_compliance"]["enabled"] = 1
    with pytest.raises(workflow_gate.WorkflowValidationError):
        validate(invalid)


@pytest.mark.parametrize("fault", ["duplicate", "phase", "level", "missing-permission"])
def test_ic10_single_scope_domains_and_role_phase_permissions(history, fault):
    h = history
    h.checked(h.k)
    schema = load_schema()["$defs"]
    assert schema["IsolationLevel"]["enum"] == ["I0", "I1", "I2"]
    assert set(schema["IsolationPhase"]["enum"]) == set(PHASES)
    mutations = {
        "duplicate": lambda b: b["payload"]["boundaries"].append(copy.deepcopy(b["payload"]["boundaries"][0])),
        "phase": lambda b: b["payload"]["boundaries"][1].update(phase="terminal-review"),
        "level": lambda b: b["payload"]["boundaries"][1].update(isolation_level="I3"),
        "missing-permission": lambda b: b["payload"]["boundaries"][1].pop("allowed_actions"),
    }
    rejected(h, rewrite(h, h.k, mutations[fault]))


@pytest.mark.parametrize("kind", ["worker-launch", "test-launch", "candidate-test-envelope", "reviewer-launch"])
def test_ic11_dispatch_binds_scope_phase_preflight_and_visibility(history, kind):
    h = history
    refs = {"worker-launch": h.wlaunch, "test-launch": h.tlaunch}
    if kind in ("candidate-test-envelope", "reviewer-launch"):
        h.ready().candidate_ready()
        refs["candidate-test-envelope"] = h.c
    if kind == "reviewer-launch":
        tested = h.report("PASS")
        h.bridge.consume(tested)
        launch, _ = h.review_terminal(tested)
        refs[kind] = launch
    ref = refs[kind]
    h.checked(ref)
    rejected(h, rewrite(h, ref, lambda b: b["payload"]["isolation"].update(scope_id="investigation")))


@pytest.mark.parametrize("fault", ["sha", "crlf", "duplicate", "float", "unknown", "disk", "escape", "wrong-kind"])
def test_ic12_inline_snapshot_is_canonical_and_exact_on_disk(history, fault):
    h = history
    h.checked(h.wlaunch)
    def mutate(body):
        snap = body["payload"]["isolation"]["preflight"]
        if fault == "sha":
            snap["ref"]["sha256"] = "0" * 64
            return
        if fault == "disk":
            (h.root / snap["ref"]["path"]).write_bytes(b"altered\n")
            return
        if fault == "escape":
            snap["ref"]["path"] = "../undeclared.json"
            return
        if fault == "wrong-kind":
            snap["ref"]["evidence_type"] = "manifest"
            return
        raw = snap["raw"]
        if fault == "crlf":
            raw = raw.replace("\n", "\r\n")
        elif fault == "duplicate":
            raw = '{"version":2,' + raw[1:]
        elif fault == "float":
            raw = raw.replace('"version":2', '"version":2.0', 1)
        else:
            raw = raw[:-2] + ',"unknown":true}\n'
        snap["raw"] = raw
        snap["ref"]["sha256"] = digest(raw.encode())
        (h.root / snap["ref"]["path"]).write_bytes(raw.encode())
    rejected(h, rewrite(h, h.wlaunch, mutate))


@pytest.mark.parametrize("fault", ["missing-scope", "pointer", "duplicate-finding", "wrong-actor", "missing-trace", "bad-local-trace"])
def test_ic13_evidence_covers_declared_and_executed_scopes(history, fault):
    h = history
    tested, launch, review = terminal_history(h, status="confirmed-violation")
    def mutate(body):
        snap = body["payload"]["isolation_review"]["evidence"]
        bundle = json.loads(snap["raw"])
        if fault == "missing-scope":
            bundle["coverage"] = [x for x in bundle["coverage"] if x["scope_id"] != "implementation"]
        elif fault == "pointer":
            bundle["findings"][0]["clause_pointer"] = "/payload/requirements/0"
        elif fault == "duplicate-finding":
            bundle["findings"].append(copy.deepcopy(bundle["findings"][0]))
        elif fault == "wrong-actor":
            bundle["findings"][0]["actor_id"] = "tester-actor"
        elif fault == "missing-trace":
            next(x for x in bundle["coverage"] if x["scope_id"] == "implementation")["traces"] = []
        else:
            trace = bundle["findings"][0]["evidence"]
            (h.root / trace["path"]).write_bytes(b"later unrelated trace\n")
        if fault != "bad-local-trace":
            body["payload"]["isolation_review"]["evidence"] = h.snapshot(h.evidence("isolation-evidence", bundle))
    rejected(h, rewrite(h, review, mutate))


@pytest.mark.parametrize("status,assessment", [
    (None, "COMPLIANT"), ("not-violation", "COMPLIANT"),
    ("confirmed-violation", "VIOLATION"),
    ("unauthorized-attempt", "INDETERMINATE"), ("unresolved", "INDETERMINATE")])
def test_ic14_real_guard_reducer_verifier_respect_true_tester_pass(history, status, assessment):
    h = history
    tested, _, review = terminal_history(h, status=status)
    p = h.objects[review["artifact_id"]]["payload"]
    assert p["isolation_review"]["assessment"] == assessment
    assert p["verdict"] == ("APPROVED" if assessment == "COMPLIANT" else "REJECTED")
    assert h.objects[tested["artifact_id"]]["payload"]["outcome"] == "PASS"
    before_candidate = copy.deepcopy(h.bridge.state["candidate"])
    terminal = h.closeout(review, success=assessment == "COMPLIANT")
    h.bridge.consume(terminal)
    reducer.validate_state(h.bridge.state, context=h.context_data())
    result = h.verify(verifier)
    assert result["status"] == "VERIFIED"
    assert result["functional_correction_count"] == 0
    assert h.bridge.state["candidate"] == before_candidate
    assert h.objects[terminal["artifact_id"]]["payload"]["accepted_candidate"] == (
        h.objects[h.c["artifact_id"]]["payload"]["candidate"]["commit"] if assessment == "COMPLIANT" else None)
    assert p["lesson_commit"]["parents"] == [h.objects[h.c["artifact_id"]]["payload"]["candidate"]["commit"]]


@pytest.mark.parametrize("candidate", [False, True])
def test_ic15_violation_enters_one_review_before_tester_result(history, candidate):
    h = history
    tested, launch, review = terminal_history(h, status="confirmed-violation", result=False, candidate=candidate)
    assert tested is None
    assert h.objects[launch["artifact_id"]]["payload"]["terminal_reason"] == "BOUNDARY_VIOLATION"
    if not candidate:
        assert h.objects[review["artifact_id"]]["payload"]["lesson_commit"] is None
    terminal = h.closeout(review, success=False)
    h.bridge.consume(terminal)
    assert h.verify(verifier)["status"] == "VERIFIED"
    before = copy.deepcopy(h.bridge.state)
    second = copy.deepcopy(h.objects[launch["artifact_id"]])
    second["artifact_id"] += "-second"
    second["payload"]["review_id"] += "-second"
    ref = h.raw_store(second)
    with pytest.raises((AssertionError, reducer.WorkflowTransitionError)):
        h.bridge.consume(ref)
    assert h.bridge.state == before
    # A normally permitted support repair is not a route back out of violation review.
    with pytest.raises((AssertionError, reducer.WorkflowTransitionError)):
        h.bridge.consume(h.support())
    assert h.bridge.state == before


def test_ic16_reviewer_discovery_uses_same_review_and_blocks_success(history):
    h = history.ready().candidate_ready()
    tested = h.report("PASS")
    h.bridge.consume(tested)
    _, review = h.review_terminal(tested, discovery="confirmed-violation")
    original = copy.deepcopy(h.objects[review["artifact_id"]])
    assert original["payload"]["verdict"] == "REJECTED"
    assert original["payload"]["isolation_review"]["assessment"] == "VIOLATION"
    h.bridge.consume(h.closeout(review, success=False))
    assert h.verify(verifier)["status"] == "VERIFIED"
    invalid = rewrite(h, review, lambda b: b["payload"].update(verdict="APPROVED"))
    rejected(h, invalid)


def test_ic17_post_review_violation_preserves_approved_report_and_rejects_success(history):
    h = history
    tested, _, review = terminal_history(h)
    reviewed = copy.deepcopy(h.objects[review["artifact_id"]])
    before = copy.deepcopy(h.bridge.state)
    good = h.closeout(review)
    control_receipt = h.checked(good)
    h.finding_status = "confirmed-violation"
    supplement = h.bundle()
    attempted = h.closeout(review, success=True, supplement=supplement)
    rejected(h, attempted)
    # Controlled negative input only: mutate a real positive receipt so the
    # pure reducer must reject the business violation independently of Guard.
    # This mutant is never claimed to be an authentic CHECKED handoff.
    receipt = copy.deepcopy(h.objects[control_receipt["artifact_id"]])
    receipt["artifact_id"] += "-negative-control"
    receipt["operation_id"] += "-negative-control"
    receipt["input"] = {k: attempted[k] for k in ("artifact_id", "path", "sha256")}
    mutant_receipt = h.raw_store(receipt)
    event = {"schema_version": "1.0", "type": "CONSUME", "event_id": "controlled-invalid-success",
             "artifact": attempted, "checked": mutant_receipt}
    context = h.context_data()
    with pytest.raises(reducer.WorkflowTransitionError):
        reducer.transition(before, event, context=context)
    bad_state = copy.deepcopy(before)
    bad_state["terminal"] = attempted
    bad_state["consumed"].append({"event_id": event["event_id"], "artifact": attempted})
    with pytest.raises(reducer.WorkflowTransitionError):
        reducer.validate_state(bad_state, context=context)
    with pytest.raises(verifier.WorkflowEvidenceError):
        verifier.verify_evidence(bad_state, context=context,
            repository_root=str(h.root.resolve()), authority=h.authority, github_get=h.get)
    assert h.bridge.state == before
    failed = h.closeout(review, success=False, supplement=supplement)
    h.bridge.consume(failed)
    assert h.objects[review["artifact_id"]] == reviewed
    assert reviewed["payload"]["verdict"] == "APPROVED"
    assert h.objects[tested["artifact_id"]]["payload"]["outcome"] == "PASS"
    assert h.verify(verifier)["terminal_disposition"] == "RECORD_FAILURE"


def test_ic18_earlier_confirmed_findings_and_traces_cannot_disappear(history):
    h = history
    _, launch, review = terminal_history(h, status="confirmed-violation")
    def erase(body):
        data = json.loads(body["payload"]["isolation_review"]["evidence"]["raw"])
        data["findings"] = []
        for row in data["coverage"]:
            if row["traces"]:
                row["traces"] = row["traces"][-1:]
        body["payload"].update(verdict="APPROVED")
        body["payload"]["isolation_review"].update(
            assessment="COMPLIANT", evidence=h.snapshot(h.evidence("isolation-evidence", data)), finding_ids=[])
    rejected(h, rewrite(h, review, erase))


def test_ic19_evidence_gap_remains_indeterminate_without_invented_violation(history):
    h = history
    h.bundle_gaps = ["Controlled missing operation interval"]
    _, _, review = terminal_history(h)
    p = h.objects[review["artifact_id"]]["payload"]
    assert p["isolation_review"]["assessment"] == "INDETERMINATE"
    assert not json.loads(p["isolation_review"]["evidence"]["raw"])["findings"]
    rejected(h, h.closeout(review, success=True))


def test_ic20_pure_state_replay_never_reads_operation_files(history, monkeypatch):
    h = history
    _, _, review = terminal_history(h)
    h.bridge.consume(h.closeout(review))
    state, context, _ = h.inputs()
    before = copy.deepcopy((state, context))
    def forbidden(*args, **kwargs):
        raise AssertionError("Pure reducer attempted external I/O")
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    reducer.validate_state(state, context=context)
    assert (state, context) == before


def test_ic21_final_verifier_rechecks_raw_trace_closure(history):
    h = history
    _, _, review = terminal_history(h)
    h.bridge.consume(h.closeout(review))
    assert h.verify(verifier)["status"] == "VERIFIED"
    bundle = json.loads(h.objects[review["artifact_id"]]["payload"]["isolation_review"]["evidence"]["raw"])
    trace = next(x for x in bundle["coverage"] if x["traces"])["traces"][0]["evidence"]
    (h.root / trace["path"]).write_bytes(b"trace mutated after guards\n")
    with pytest.raises(verifier.WorkflowEvidenceError):
        h.verify(verifier)


def test_ic22_w4_rejects_new_members_without_migrating_history(tmp_path):
    h = IsolationHistory(tmp_path / "legacy", version=4)
    h.ready().candidate_ready()
    tested = h.report("PASS")
    h.bridge.consume(tested)
    _, review = h.review_terminal(tested)
    h.bridge.consume(h.closeout(review))
    assert h.verify(verifier)["status"] == "VERIFIED"
    invalid = rewrite(h, h.wlaunch, lambda b: b["payload"].update(isolation={
        "scope_id": "implementation", "preflight": {"ref": h.evidence("operation-log", b"{}\n"), "raw": "{}\n"}}))
    rejected(h, invalid)


@pytest.mark.parametrize("version", [4, 5])
def test_ic23_frozen_support_and_incremental_corrections_keep_lineage(tmp_path, version):
    h = IsolationHistory(tmp_path / "lineage", version=version)
    h.ready().candidate_ready()
    approval = copy.deepcopy(h.human)
    for index in (1, 2, 3):
        previous = h.i
        h.correction_ready(index)
        assert h.git("merge-base", "--is-ancestor", previous, h.i) == ""
        assert h.human == approval
    tested = h.report("IMPLEMENTATION_FAIL")
    h.bridge.consume(tested)
    _, review = h.review_terminal(tested, reason="CORRECTIONS_EXHAUSTED")
    h.bridge.consume(h.closeout(review, success=False))
    outcome = h.verify(verifier)
    assert outcome["functional_correction_count"] == 3
    assert outcome["terminal_disposition"] == "RECORD_FAILURE"
    before = copy.deepcopy(h.bridge.state)
    with pytest.raises((AssertionError, reducer.WorkflowTransitionError)):
        h.bridge.consume(h.correction(4, tested))
    assert h.bridge.state == before


def test_ic24_w4_prevalidated_support_preserves_case_anchor(tmp_path):
    h = IsolationHistory(tmp_path / "support", version=4)
    h.ready()
    h.support_ready(execute=True)
    result = h.verify(verifier)
    assert result["approved_test_sha"] == h.t
    assert result["effective_test_sha"] != h.t
    assert result["functional_correction_count"] == 0
    # Existing final verification really opens byte-bound command evidence.
    selected = h.objects[h.tr["artifact_id"]]["payload"]["prevalidation"][0]["result"]
    (h.root / selected["path"]).write_bytes(b"corrupt command evidence\n")
    with pytest.raises(verifier.WorkflowEvidenceError):
        h.verify(verifier)


def test_ic25_pending_attempt_can_be_resolved_with_retained_evidence(history):
    h = history.ready().candidate_ready()
    tested = h.report("PASS")
    h.bridge.consume(tested)
    h.finding_status = "unauthorized-attempt"
    launch, review = h.review_terminal(tested, discovery="not-violation")
    before = json.loads(h.objects[launch["artifact_id"]]["payload"]["isolation_evidence"]["raw"])
    after = json.loads(h.objects[review["artifact_id"]]["payload"]["isolation_review"]["evidence"]["raw"])
    assert before["findings"][0]["id"] == after["findings"][0]["id"]
    assert before["findings"][0]["status"] == "unauthorized-attempt"
    assert after["findings"][0]["status"] == "not-violation"
    h.bridge.consume(h.closeout(review))
    assert h.verify(verifier)["status"] == "VERIFIED"
