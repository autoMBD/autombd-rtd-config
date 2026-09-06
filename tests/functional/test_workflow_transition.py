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
# File:        test_workflow_transition.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.1
# Description: Independent frozen functional gate for the pure workflow reducer.
# =================================================================================

"""Automation for tests/doc/agent-functional-test-cases.md, cases 001-028.

The case catalogue is the Human review entry; preserve its approved expectations.
"""

import copy
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from workflow_transition_cases import (
    History, ROOT, SCRIPTS, canonical, digest, empty_state, load_target, sha,
)

TARGET = Path(os.environ.get("RTD_TRANSITION_TEST_TARGET", SCRIPTS / "workflow_transition.py"))


@pytest.fixture
def api():
    assert TARGET.is_file(), "R02: new public workflow_transition.py API is absent"
    module = load_target(TARGET)
    for name in ("initial_state", "transition", "WorkflowTransitionError"):
        assert callable(getattr(module, name, None)), "R02: missing public callable " + name
    return module


@pytest.fixture
def h(api):
    return History(api)


def refresh_check(history, event, change):
    entry = next(x for x in history.context["checks"] if x["ref"] == event["checked"])
    change(entry["body"])
    entry["ref"]["sha256"] = digest(entry["body"])
    event["checked"] = copy.deepcopy(entry["ref"])


@pytest.mark.parametrize("seed,order", [
    ("copper", ("tester", "worker")), ("indigo", ("worker", "tester")),
])
def test_success_lifecycle_python_and_cli(api, seed, order):
    """R01-R12,R17-R18,R21,R23: independent lane order to exact merged head."""
    history = History(api, seed)
    history.prepared(order)
    history.result("PASS")
    history.review()
    history.terminal()
    candidate = history.payload(history.state["candidate"]["envelope"])["candidate"]["commit"]
    pr = {"url": "https://example.test/pull/317", "head_sha": candidate, "merge_sha": None}
    history.terminal(pr=pr)
    history.take(history.decision_body("FINAL", "APPROVE"), {"final_decision": "@incoming"})
    pr["merge_sha"] = sha(seed + "-merge")
    history.terminal("MERGED", pr=pr)
    assert history.state["worker"]["pending_correction"] is None
    assert history.payload(history.state["terminal"])["accepted_candidate"] == candidate
    replay_cli(history)


@pytest.mark.parametrize("seed,order", [
    ("ochre", ("worker", "tester")), ("violet", ("tester", "worker")),
])
def test_three_corrections_exhaustion_python_and_cli(api, seed, order):
    """R10-R14,R17-R18,R23: authorization is not completed correction."""
    history = History(api, seed)
    history.prepared(order)
    for index in range(4):
        history.result("IMPLEMENTATION_FAIL")
        if index < 3:
            old_ready = history.state["worker"]["ready"]
            old_candidate = copy.deepcopy(history.state["candidate"])
            history.correct()
            assert history.state["worker"]["ready"] == old_ready
            not_ready = history.report_body("worker", status="NOT_READY", index=index + 1)
            history.take(not_ready, {})
            assert history.state["worker"]["ready"] == old_ready
            history.ready("worker", index + 1)
            assert history.state["candidate"] == old_candidate
            history.candidate()
    history.review("CORRECTIONS_EXHAUSTED")
    history.terminal("RECORD_FAILURE", success=False)
    assert history.payload(history.state["worker"]["ready"])["implementation_index"] == 3
    assert history.payload(history.state["terminal"])["accepted_candidate"] is None
    replay_cli(history)


def test_initial_state_is_complete_closed_and_independent(api):
    task = {"repository": "public/finite", "issue_number": 990, "task_run": "independent"}
    governor = {"commit": "1" * 40, "workflow_contract_path": "agent-discipline/workflow-contract.json",
                "workflow_contract_blob": "2" * 40}
    original = copy.deepcopy((task, governor))
    result = api.initial_state(task, governor)
    assert result == empty_state(task, governor)
    assert (task, governor) == original
    result["task"]["repository"] = "changed"
    result["worker"]["launch"] = {"unrelated": True}
    assert (task, governor) == original
    assert api.initial_state(task, governor) == empty_state(task, governor)


@pytest.mark.parametrize("bad", [None, [], True, 1.1, float("inf"), {"repository": "r"},
                                  {"repository": "r", "issue_number": True, "task_run": "id"}])
def test_initial_programmer_errors_are_structured(api, bad):
    governor = {"commit": "1" * 40, "workflow_contract_path": "agent-discipline/workflow-contract.json",
                "workflow_contract_blob": "2" * 40}
    with pytest.raises(api.WorkflowTransitionError) as caught:
        api.initial_state(bad, governor)
    assert caught.value.code in {"MALFORMED_EVENT", "INVALID_STATE"}
    assert set(caught.value.as_dict()) == {"error"}


@pytest.mark.parametrize("where,mutator", [
    ("event", lambda x: x.update(unknown=True)),
    ("event", lambda x: x.update(type="F0")),
    ("event", lambda x: x.update(schema_version="2.0")),
    ("event", lambda x: x.update(checked=True)),
    ("event", lambda x: x["artifact"].update(unknown=0)),
    ("event", lambda x: x["checked"].update(kind="implementation-report")),
    ("context", lambda x: x.update(unknown=None)),
    ("context", lambda x: x.update(workflow_profile="legacy")),
    ("context", lambda x: x["protocol"].update(unknown={})),
    ("context", lambda x: x["protocol"]["registry"].update(schema_version="8.0")),
    ("context", lambda x: x["protocol"]["workflow_contract"].update(contract_version=1)),
    ("context", lambda x: x["protocol"]["handoff_schema"].update({"$defs": {}})),
    ("context", lambda x: x["task"].update(issue_number=True)),
])
def test_malformed_wire_has_highest_priority(h, where, mutator):
    body = h.artifact("task-contract")
    event = h.event(body)
    state = copy.deepcopy(h.state)
    state["illegal"] = True
    context = copy.deepcopy(h.context)
    mutator(event if where == "event" else context)
    h.reject(event, "MALFORMED_EVENT", state=state, context=context)


def test_malformed_incoming_body_before_invalid_state(h):
    body = h.artifact("task-contract")
    body["payload"]["unknown"] = "confidential-marker-not-for-errors"
    event = h.event(body, validate=False)
    state = copy.deepcopy(h.state)
    state["unknown"] = True
    h.reject(event, "MALFORMED_EVENT", state=state)


@pytest.mark.parametrize("mutator", [
    lambda x: x.update(unknown=True),
    lambda x: x.pop("stop"),
    lambda x: x["worker"].update(count=0),
    lambda x: x["test"].update(launch=x["contract"]),
    lambda x: x["consumed"].append(copy.deepcopy(x["consumed"][0])),
    lambda x: x["consumed"][0].update(event_id=True),
    lambda x: x.update(stop={"kind": "human-decision", "artifact_id": "unconsumed",
        "path": ".agent-state/unconsumed.json", "sha256": "a" * 64}),
])
def test_invalid_state_precedes_duplicate_and_evidence(h, mutator):
    h.contract()
    state = copy.deepcopy(h.state)
    mutator(state)
    context = copy.deepcopy(h.context)
    context["checks"] = []
    h.reject(copy.deepcopy(h.last_event), "INVALID_STATE", state=state, context=context)


@pytest.mark.parametrize("component", ["task", "governor", "task_contract"])
def test_present_identity_drift_precedes_missing_receipt(h, component):
    h.contract()
    body = h.artifact("worker-launch", {"lane": h.lane("worker"),
        "dispatch_id": h.uid("dispatch")}, [h.state["contract"]])
    if component == "task":
        body[component]["task_run"] = "foreign-run"
    elif component == "governor":
        body[component]["commit"] = "f" * 40
    else:
        body[component]["sha256"] = "b" * 64
    event = h.event(body)
    h.context["checks"] = []
    h.reject(event, "STALE_EVENT")


def test_duplicate_event_and_artifact_precede_missing_receipt(h):
    h.contract()
    event = copy.deepcopy(h.last_event)
    h.context["checks"] = []
    h.reject(event, "DUPLICATE_EVENT")
    event["event_id"] = h.uid("same-artifact-new-event")
    h.reject(event, "DUPLICATE_EVENT")


def test_same_artifact_id_with_different_reference_is_stale(h):
    h.contract()
    event = copy.deepcopy(h.last_event)
    event["artifact"]["sha256"] = "e" * 64
    h.context["checks"] = []
    h.reject(event, "STALE_EVENT")


@pytest.mark.parametrize("missing", ["incoming", "receipt", "prior-state", "direct-predecessor"])
def test_missing_catalog_is_evidence_not_invalid_state(h, missing):
    h.contract()
    body = h.artifact("worker-launch", {"lane": h.lane("worker"),
        "dispatch_id": h.uid("dispatch")}, [h.state["contract"]])
    if missing == "direct-predecessor":
        other = h.artifact("human-decision")
        body["predecessors"].append(h.ref(other))
    event = h.event(body)
    if missing == "incoming":
        h.context["artifacts"] = [x for x in h.context["artifacts"] if x["ref"] != event["artifact"]]
    elif missing == "receipt":
        h.context["checks"] = []
    elif missing == "prior-state":
        h.context["artifacts"] = [x for x in h.context["artifacts"] if x["ref"] != h.state["contract"]]
    h.reject(event, "MISSING_EVIDENCE")


@pytest.mark.parametrize("change", [
    lambda x: x.update(status="REJECTED"),
    lambda x: x.update(exit_code=1),
    lambda x: x.update(evidence_available=False),
    lambda x: x.update(violations=[{"rule_id": "FAIL", "field_pointer": "/", "safe_diagnostic": "reject"}]),
    lambda x: x.update(consumer_role="human"),
    lambda x: x.update(visibility="terminal-review"),
    lambda x: x["input"].update(path=".agent-state/wrong.json"),
    lambda x: x["input"].update(sha256="f" * 64),
    lambda x: x["input"].update(artifact_id="different"),
    lambda x: x.update(trusted_context=None),
])
def test_available_false_checked_receipts_fail_closed(h, change):
    event = h.event(h.artifact("task-contract"))
    refresh_check(h, event, change)
    h.reject(event, "INVALID_EVIDENCE")


def test_receipt_digest_and_artifact_digest_are_both_checked(h):
    event = h.event(h.artifact("task-contract"))
    h.context["checks"][0]["body"]["operation_id"] = "altered"
    h.reject(event, "INVALID_EVIDENCE")
    h.context["checks"][0]["body"]["operation_id"] = "altered-again"
    refresh_check(h, event, lambda x: None)
    h.context["artifacts"][0]["body"]["payload"]["objective"] = "altered"
    h.reject(event, "INVALID_EVIDENCE")


@pytest.mark.parametrize("role", ["tester", "worker"])
def test_lane_initial_readiness_is_independent(api, role):
    h = History(api, "parallel-" + role)
    h.contract()
    h.launch(role)
    h.ready(role)
    if role == "tester":
        h.approve()
        assert h.state["worker"]["launch"] is None
    else:
        assert h.state["test"]["launch"] is None


@pytest.mark.parametrize("status", ["NOT_READY", "CONTRACT_AMBIGUITY"])
@pytest.mark.parametrize("role", ["tester", "worker"])
def test_pre_freeze_withdrawal_clears_only_own_ready(h, role, status):
    h.contract()
    h.launch("tester")
    h.launch("worker")
    h.ready("tester")
    h.ready("worker")
    other = copy.deepcopy(h.state["worker" if role == "tester" else "test"])
    own = "test" if role == "tester" else "worker"
    h.take(h.report_body(role, status), {own + ".ready": None})
    assert h.state["worker" if role == "tester" else "test"] == other


def test_test_request_changes_retains_worker_and_allows_same_lane_revision(h):
    h.contract()
    h.launch("tester")
    h.launch("worker")
    h.ready("tester")
    worker = h.ready("worker")
    h.take(h.decision_body("TEST", "REQUEST_CHANGES"), {"test.ready": None})
    assert h.state["worker"]["ready"] == worker
    h.ready("tester")
    h.approve()


@pytest.mark.parametrize("kind", ["test-status", "test-ready", "contract"])
def test_approval_freezes_test_and_contract_before_evidence(h, kind):
    h.contract()
    h.launch("tester")
    h.ready("tester")
    h.approve()
    if kind == "contract":
        body = h.artifact("task-contract")
        body["payload"]["revision"].update(number=1, predecessor=h.state["contract"],
            authority=h.evidence("change", "authority"))
        body["predecessors"] = [h.state["contract"]]
    else:
        body = h.report_body("tester", "READY" if kind == "test-ready" else "NOT_READY")
    event = h.event(body)
    h.context["checks"] = []
    h.reject(event, "ILLEGAL_TRANSITION")


def test_test_stop_is_not_global_stop(h):
    h.contract()
    h.launch("tester")
    h.ready("tester")
    h.reject(h.event(h.decision_body("TEST", "STOP")), "ILLEGAL_TRANSITION")
    assert h.state["stop"] is None


def test_before_c0_worker_same_lane_index0_refinement(h):
    h.contract()
    h.launch("worker")
    first = h.ready("worker")
    h.ready("worker")
    assert h.state["worker"]["ready"] != first
    assert h.payload(h.state["worker"]["ready"])["implementation_index"] == 0


def test_candidate_requires_consumed_approval_before_missing_evidence(h):
    h.contract()
    h.launch("tester")
    h.ready("tester")
    h.launch("worker")
    h.ready("worker")
    body = h.candidate_body()
    body["predecessors"] = [p for p in body["predecessors"] if p is not None]
    event = h.event(body)
    h.context["checks"] = []
    h.reject(event, "OUT_OF_ORDER_EVENT")


@pytest.mark.parametrize("field", ["test_tip", "implementation_tip", "test_manifest", "impact_set"])
def test_candidate_binding_drift_is_stale(h, field):
    h.prepared()
    body = h.candidate_body()
    if field.endswith("tip"):
        body["payload"][field]["commit"] = sha("unbound-tip")
    else:
        body["payload"][field]["sha256"] = "e" * 64
    event = h.event(body)
    h.context["checks"] = []
    h.reject(event, "STALE_EVENT")


def test_duplicate_assembly_without_new_implementation_is_illegal(h):
    h.prepared()
    h.reject(h.event(h.candidate_body()), "ILLEGAL_TRANSITION")


@pytest.mark.parametrize("outcome", ["PASS", "TEST_GATE_INVALID", "CONTRACT_INVALID", "INTEGRITY_INVALID"])
def test_terminal_outcome_prohibits_correction_and_new_worker(h, outcome):
    h.prepared()
    h.result(outcome)
    h.reject(h.event(h.correction_body()), "ILLEGAL_TRANSITION")
    h.reject(h.event(h.report_body("worker", index=1)), "ILLEGAL_TRANSITION")
    h.review("TESTER_PASS" if outcome == "PASS" else outcome)
    h.terminal("OPEN_SUCCESS_PR" if outcome == "PASS" else "RECORD_FAILURE", success=outcome == "PASS")


def test_result_requires_current_execution_and_consumes_once(h):
    h.prepared()
    body = h.result_body("PASS")
    h.result("PASS")
    h.reject(h.event(body), "ILLEGAL_TRANSITION")


def test_invalid_run_rerun_keeps_sources_and_rejects_stale_old_result(h):
    h.prepared()
    old_envelope = h.state["candidate"]["envelope"]
    old_result = h.result_body("PASS")
    frozen_worker = copy.deepcopy(h.state["worker"])
    frozen_test = copy.deepcopy(h.state["test"])
    h.result("INVALID_RUN")
    invalid_report = h.state["candidate"]["result"]
    h.reject(h.event(h.correction_body()), "ILLEGAL_TRANSITION")
    h.reject(h.event(h.review_body("TESTER_PASS")), "ILLEGAL_TRANSITION")
    h.candidate(rerun=True)
    assert h.state["worker"] == frozen_worker
    assert h.state["test"] == frozen_test
    assert h.payload(h.state["candidate"]["envelope"])["rerun_of"] == invalid_report
    assert old_envelope in h.body(h.state["candidate"]["envelope"])["predecessors"]
    event = h.event(old_result)
    h.context["checks"] = []
    h.reject(event, "STALE_EVENT")
    h.result("PASS")


@pytest.mark.parametrize("field", ["execution_id", "dispatch_id"])
def test_rerun_cannot_reuse_execution_or_dispatch_history(h, field):
    h.prepared()
    first = h.payload(h.state["candidate"]["envelope"])
    h.result("INVALID_RUN")
    h.candidate(rerun=True)
    h.result("INVALID_RUN")
    body = h.candidate_body(rerun=True)
    body["payload"][field] = first[field]
    event = h.event(body)
    h.reject(event, "STALE_EVENT")
    h.context["checks"] = []
    h.reject(event, "STALE_EVENT")


def test_pending_correction_is_single_and_not_ready_does_not_spend_it(h):
    h.prepared()
    h.result("IMPLEMENTATION_FAIL")
    h.correct()
    before = copy.deepcopy(h.state["worker"])
    h.reject(h.event(h.correction_body()), "ILLEGAL_TRANSITION")
    h.take(h.report_body("worker", status="NOT_READY", index=1), {})
    assert h.state["worker"] == before
    h.ready("worker", index=1)
    assert h.state["worker"]["pending_correction"] is None
    h.candidate()


@pytest.mark.parametrize("field", ["lane", "previous_implementation", "disclosure_review"])
def test_correction_exact_public_binding(h, field):
    h.prepared()
    h.result("IMPLEMENTATION_FAIL")
    body = h.correction_body()
    if field == "lane":
        body["payload"][field]["agent_session_id"] = "replacement-session"
    elif field == "previous_implementation":
        body["payload"][field] = sha("foreign-source")
    else:
        body["payload"][field]["source_report_sha256"] = "e" * 64
    event = h.event(body)
    h.context["checks"] = []
    h.reject(event, "STALE_EVENT")


def test_k_revision_two_ack_barrier_and_independent_launches(h):
    h.contract()
    h.launch("tester")
    h.launch("worker")
    old_t = h.ready("tester")
    old_i = h.ready("worker")
    old_k = h.kref()
    h.contract(revision=1)
    assert h.state["test"]["ready"] == old_t
    assert h.state["worker"]["ready"] == old_i
    h.launch("tester", revision=True)
    ack = h.report_body("tester", "K_ACK")
    revision_ack = h.sample(h.defs["RevisionAck"])
    revision_ack.update(old_contract=old_k, new_contract=h.kref(),
                        verified_sha256=h.kref()["sha256"], current_tip=h.payload(old_t)["test_tip"]["commit"])
    ack["payload"]["revision_ack"] = revision_ack
    h.take(ack, {"test.ack": "@incoming"})
    assert h.state["test"]["ready"] == old_t
    h.reject(h.event(h.report_body("tester")), "OUT_OF_ORDER_EVENT")
    # The decision has current K and the retained current slot's exact subject;
    # identities agree, but a consumed current-K READY prerequisite is absent.
    h.reject(h.event(h.decision_body("TEST", "APPROVE")), "OUT_OF_ORDER_EVENT")
    h.launch("worker", revision=True)
    ack = h.report_body("worker", "K_ACK")
    revision_ack = copy.deepcopy(revision_ack)
    revision_ack["current_tip"] = h.payload(old_i)["implementation_tip"]["commit"]
    ack["payload"]["revision_ack"] = revision_ack
    h.take(ack, {"worker.ack": "@incoming"})
    h.ready("tester")
    h.ready("worker")
    h.approve()
    h.candidate()


@pytest.mark.parametrize("stage", ["contract", "worker", "candidate", "pending", "review", "proposal"])
def test_global_stop_preserves_actual_sources_and_uses_one_review(api, stage):
    h = History(api, "stop-" + stage)
    if stage in {"contract", "worker"}:
        h.contract()
        if stage == "worker":
            h.launch("worker")
            h.ready("worker")
    else:
        h.prepared()
        if stage == "pending":
            h.result("IMPLEMENTATION_FAIL")
            h.correct()
        elif stage in {"review", "proposal"}:
            h.result("PASS")
            launch = h.review_body("TESTER_PASS")
            h.take(launch, {"review": {"launch": h.ref(launch), "report": None}})
            if stage == "proposal":
                payload = h.payload(h.state["review"]["launch"])
                report = h.artifact("reviewer-report", {"dispatch_id": payload["dispatch_id"],
                    "review_id": payload["review_id"], "verdict": "APPROVED",
                    "lessons": h.evidence("lessons", "lesson")}, [h.state["review"]["launch"]])
                h.take(report, {"review.report": "@incoming"})
                h.terminal()
    saved = copy.deepcopy((h.state["worker"], h.state["candidate"], h.state["review"]))
    h.take(h.decision_body("FINAL", "STOP"), {"stop": "@incoming"})
    assert (h.state["worker"], h.state["candidate"], h.state["review"]) == saved
    if not h.state["review"]:
        h.review("HUMAN_STOP")
    elif not h.state["review"]["report"]:
        payload = h.payload(h.state["review"]["launch"])
        report = h.artifact("reviewer-report", {"dispatch_id": payload["dispatch_id"],
            "review_id": payload["review_id"], "verdict": "APPROVED",
            "lessons": h.evidence("lessons", "lesson")}, [h.state["review"]["launch"]])
        h.take(report, {"review.report": "@incoming"})
    h.terminal("RECORD_FAILURE", success=False)
    assert h.payload(h.state["terminal"])["result"] == "FAILURE"


def test_review_without_result_is_order_error_but_invalid_run_is_illegal(h):
    h.prepared()
    h.reject(h.event(h.review_body("TESTER_PASS")), "OUT_OF_ORDER_EVENT")
    h.result("INVALID_RUN")
    h.reject(h.event(h.review_body("TESTER_PASS")), "ILLEGAL_TRANSITION")


def test_one_terminal_review_and_no_corrections_after_it(h):
    h.prepared()
    h.result("PASS")
    h.review()
    h.reject(h.event(h.review_body("TESTER_PASS")), "ILLEGAL_TRANSITION")
    h.reject(h.event(h.correction_body()), "ILLEGAL_TRANSITION")


@pytest.mark.parametrize("verdict,decision", [("REJECTED", None), ("APPROVED", "REQUEST_CHANGES")])
def test_rejected_success_becomes_truthful_failure_without_corrections(h, verdict, decision):
    h.prepared()
    h.result("PASS")
    h.review(verdict=verdict)
    if decision:
        h.terminal()
        h.take(h.decision_body("FINAL", decision), {"final_decision": "@incoming"})
    else:
        h.reject(h.event(h.terminal_body("OPEN_SUCCESS_PR")), "ILLEGAL_TRANSITION")
    h.terminal("RECORD_FAILURE", success=False)
    assert h.state["worker"]["pending_correction"] is None


def test_success_proposal_is_not_merge_and_cannot_repeat_unchanged(h):
    h.prepared()
    h.result("PASS")
    h.review()
    h.terminal()
    h.reject(h.event(h.terminal_body("OPEN_SUCCESS_PR")), "ILLEGAL_TRANSITION")
    h.reject(h.event(h.terminal_body("MERGED", pr={"url": "https://example.test/pull/1",
        "head_sha": h.payload(h.state["candidate"]["envelope"])["candidate"]["commit"],
        "merge_sha": sha("merge")})), "OUT_OF_ORDER_EVENT")
    assert h.state["final_decision"] is None


def test_closed_failure_rejects_new_business_but_duplicate_priority_wins(h):
    h.contract()
    h.take(h.decision_body("FINAL", "STOP"), {"stop": "@incoming"})
    h.review("HUMAN_STOP")
    h.terminal("RECORD_FAILURE", success=False)
    h.reject(copy.deepcopy(h.last_event), "DUPLICATE_EVENT")
    h.reject(h.event(h.decision_body("FINAL", "STOP")), "ILLEGAL_TRANSITION")


def test_delivery_repair_bookkeeping_and_never_consumed_malformed_original(h):
    h.contract()
    h.launch("worker")
    original = h.report_body("worker")
    malformed = copy.deepcopy(original)
    malformed["unknown_format_field"] = "rejected"
    original_ref = h.ref(malformed)
    h.context["artifacts"].append({"ref": original_ref, "body": malformed})
    reject = h.check(malformed, original_ref)
    reject.update(status="REJECTED", exit_code=1, violations=[
        {"rule_id": "EXTRA_MEMBER", "field_pointer": "/", "safe_diagnostic": "unknown member"}])
    rejection_ref = h.ref(reject)
    h.context["checks"].append({"ref": rejection_ref, "body": reject})
    repair = h.artifact("delivery-repair", {"dispatch_id": h.uid("repair-dispatch"),
        "original": original_ref, "rejection": rejection_ref, "lane": h.lane("worker"),
        "preserve_tip": original["payload"]["implementation_tip"]["commit"],
        "preserve_candidate_index": None, "preserve_correction_count": 0,
        "preserve_review_id": None}, [original_ref, rejection_ref])
    repair["consumer_role"], repair["visibility"] = "worker", "public-task"
    previous = copy.deepcopy(h.state["worker"])
    h.take(repair, {"repairs": [h.ref(repair)]})
    assert h.state["worker"] == previous
    original["artifact_id"] = h.uid("format-fixed")
    original["replaces"] = {"original": original_ref, "guard_result": rejection_ref}
    original["predecessors"].extend([original_ref, rejection_ref, h.ref(repair)])
    original["payload"]["dispatch_id"] = repair["payload"]["dispatch_id"]
    h.take(original, {"worker.ready": "@incoming", "worker.pending_correction": None})
    assert len(h.state["repairs"]) == 1
    assert h.payload(h.state["worker"]["ready"])["implementation_index"] == 0


def test_pure_core_does_not_touch_external_services(h, monkeypatch):
    body = h.artifact("task-contract")
    event = h.event(body)
    import builtins
    import io
    import random
    import socket
    import time
    import uuid
    def forbidden(*args, **kwargs):
        raise AssertionError("R02: external operation from pure core")
    before = copy.deepcopy((h.task, h.governor, h.state, event, h.context))
    with monkeypatch.context() as patch:
        for owner, names in [
            (builtins, ["open"]), (io, ["open"]), (Path, ["open", "read_text", "read_bytes", "resolve"]),
            (subprocess, ["run", "Popen", "call", "check_output", "check_call"]),
            (os, ["system", "popen"]), (time, ["time", "monotonic", "sleep"]),
            (random, ["random", "randint"]), (uuid, ["uuid4"]), (socket, ["socket"]),
        ]:
            for name in names:
                patch.setattr(owner, name, forbidden)
        assert h.target.initial_state(h.task, h.governor) == empty_state(h.task, h.governor)
        result = h.target.transition(h.state, event, context=h.context)
        assert result["contract"] == event["artifact"]
    assert (h.task, h.governor, h.state, event, h.context) == before


def invoke_cli(argv):
    return subprocess.run([sys.executable, str(TARGET), *argv], cwd=ROOT,
                          capture_output=True, timeout=45)


def cli_document(result, success=True, code=None):
    import json
    assert result.returncode == (0 if success else code)
    stream = result.stdout if success else result.stderr
    assert (result.stderr if success else result.stdout) == b""
    parsed = json.loads(stream)
    assert stream == canonical(parsed)
    return parsed


def replay_cli(history):
    temp_base = ROOT / "tests/.tmp"
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="transition-owner-", dir=temp_base) as directory:
        folder = Path(directory)
        for name, value in [("task", history.task), ("governor", history.governor)]:
            (folder / (name + ".json")).write_bytes(canonical(value))
        result = invoke_cli(["init", "--task", str(folder / "task.json"),
                             "--governor", str(folder / "governor.json")])
        assert cli_document(result) == empty_state(history.task, history.governor)
        for state, event, context, expected in history.steps:
            for name, value in [("state", state), ("event", event), ("context", context)]:
                (folder / (name + ".json")).write_bytes(canonical(value))
            snapshot = {p.name: p.read_bytes() for p in folder.iterdir()}
            result = invoke_cli(["apply", "--state", str(folder / "state.json"),
                "--event", str(folder / "event.json"), "--context", str(folder / "context.json")])
            assert cli_document(result) == expected
            assert {p.name: p.read_bytes() for p in folder.iterdir()} == snapshot


@pytest.mark.parametrize("raw", [b"{", b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}',
                                   b'{"x":Infinity}', b"null", b"[]", b"1"])
def test_cli_input_errors_precede_reducer_and_never_overwrite(api, raw):
    temp_base = ROOT / "tests/.tmp"
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="transition-json-", dir=temp_base) as directory:
        path = Path(directory) / "bad.json"
        path.write_bytes(raw)
        result = invoke_cli(["apply", "--state", str(path), "--event", str(path), "--context", str(path)])
        error = cli_document(result, False, 2)
        assert error["error"]["code"] == "INPUT_ERROR"
        assert path.read_bytes() == raw
        assert b"Traceback" not in result.stderr


@pytest.mark.parametrize("argv", [[], ["unknown"], ["apply"], ["init", "--unexpected"]])
def test_cli_usage_errors_are_json(api, argv):
    error = cli_document(invoke_cli(argv), False, 2)
    assert error["error"]["code"] == "USAGE_ERROR"


def test_cli_help_is_explicit_normal_help_exception(api):
    result = invoke_cli(["--help"])
    assert result.returncode == 0
    assert b"usage:" in result.stdout.lower()
    assert result.stderr == b""


def test_cli_unreadable_file_and_transition_rejection(api):
    result = invoke_cli(["init", "--task", str(ROOT / "tests/.tmp/not-existent-task.json"),
                         "--governor", str(ROOT / "tests/.tmp/not-existent-governor.json")])
    assert cli_document(result, False, 2)["error"]["code"] == "INPUT_ERROR"
    h = History(api)
    h.contract()
    temp_base = ROOT / "tests/.tmp"
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="transition-reject-", dir=temp_base) as directory:
        folder = Path(directory)
        for name, value in [("state", h.state), ("event", h.last_event), ("context", h.context)]:
            (folder / (name + ".json")).write_bytes(canonical(value))
        result = invoke_cli(["apply", "--state", str(folder / "state.json"),
            "--event", str(folder / "event.json"), "--context", str(folder / "context.json")])
        assert cli_document(result, False, 1)["error"]["code"] == "DUPLICATE_EVENT"
        # Fault injection at the public reducer call tests only the thin adapter's
        # promised exception routing; it does not alter or inspect production internals.
        driver = """import runpy, sys
target, mode = sys.argv[1:3]
sys.argv = [target] + sys.argv[3:]
def fault(frame, event, arg):
    if event == 'call' and frame.f_code.co_name == 'transition' and 'WorkflowTransitionError' in frame.f_globals:
        sys.settrace(None)
        if mode == 'INVALID_OUTPUT':
            raise frame.f_globals['WorkflowTransitionError']('INVALID_OUTPUT', '/', 'Injected output invariant fault.')
        raise RuntimeError('adapter-private-exception-marker')
    return fault
sys.settrace(fault)
runpy.run_path(target, run_name='__main__')
"""
        for code in ("INVALID_OUTPUT", "EXECUTION_ERROR"):
            result = subprocess.run([sys.executable, "-c", driver, str(TARGET), code,
                "apply", "--state", str(folder / "state.json"), "--event", str(folder / "event.json"),
                "--context", str(folder / "context.json")], cwd=ROOT, capture_output=True, timeout=45)
            assert cli_document(result, False, 2)["error"]["code"] == code
            assert b"Traceback" not in result.stderr
            assert b"adapter-private-exception-marker" not in result.stderr

def repair_setup(h, *, consumed=False, raw_mode=None, role="worker"):
    """A rejected delivery is data, never fabricated as a consumed business event."""
    import hashlib
    import json
    h.contract()
    h.launch(role)
    if consumed:
        original_ref = h.ready(role)
        original = copy.deepcopy(h.body(original_ref))
        if role == "tester":
            h.approve()
    else:
        original = h.report_body(role)
        original_ref = h.ref(original)
    entry = {"ref": original_ref, "body": copy.deepcopy(original)}
    if raw_mode is not None:
        raw = json.dumps(original, ensure_ascii=False, indent=2) + "\n"
        if raw_mode == "duplicate":
            raw = raw.replace('"schema_version": "1.0"', '"schema_version": "1.0", "schema_version": "1.0"')
        elif raw_mode == "unparseable":
            raw = raw[:-4]
        elif raw_mode == "mismatched-body":
            raw = raw.replace('"status": "READY"', '"status": "NOT_READY"')
        original_ref = copy.deepcopy(original_ref)
        original_ref["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        entry = {"ref": original_ref, "body": copy.deepcopy(original), "raw": raw}
    if not consumed:
        h.context["artifacts"].append(entry)
    rejected = h.check(original, original_ref)
    rejected.update(status="REJECTED", exit_code=1, violations=[
        {"rule_id": "NON_CANONICAL", "field_pointer": "/", "safe_diagnostic": "format rejection"}])
    rejected_ref = h.ref(rejected)
    h.context["checks"].append({"ref": rejected_ref, "body": rejected})
    repair = h.artifact("delivery-repair", {"dispatch_id": h.uid("repair-dispatch"),
        "original": original_ref, "rejection": rejected_ref, "lane": h.lane(role),
        "preserve_tip": original["payload"]["test_tip" if role == "tester" else "implementation_tip"]["commit"],
        "preserve_candidate_index": None, "preserve_correction_count": 0,
        "preserve_review_id": None}, [original_ref, rejected_ref])
    repair["consumer_role"] = role
    repair["visibility"] = "tester-confidential" if role == "tester" else "public-task"
    return original, original_ref, rejected_ref, repair


def test_raw_noncanonical_rejected_original_can_be_repaired(h):
    original, original_ref, rejected_ref, repair = repair_setup(h, raw_mode="noncanonical")
    h.take(repair, {"repairs": [h.ref(repair)]})
    fixed = copy.deepcopy(original)
    fixed["artifact_id"] = h.uid("fixed")
    fixed["replaces"] = {"original": original_ref, "guard_result": rejected_ref}
    fixed["predecessors"].extend([original_ref, rejected_ref, h.ref(repair)])
    fixed["payload"]["dispatch_id"] = repair["payload"]["dispatch_id"]
    h.take(fixed, {"worker.ready": "@incoming", "worker.pending_correction": None})


@pytest.mark.parametrize("mode", ["duplicate", "unparseable", "mismatched-body"])
def test_untrustworthy_raw_original_cannot_supply_repair_business_fields(h, mode):
    original, original_ref, rejected_ref, repair = repair_setup(h, raw_mode=mode)
    h.reject(h.event(repair), "INVALID_EVIDENCE")


def test_raw_is_forbidden_on_normal_incoming_and_receipt_catalog(h):
    event = h.event(h.artifact("task-contract"))
    h.context["artifacts"][0]["raw"] = canonical(h.context["artifacts"][0]["body"]).decode()
    # raw is a legal optional artifact-entry member, but its non-repair use
    # violates the evidence permission. Receipt entries never admit that member.
    h.reject(event, "INVALID_EVIDENCE")
    h.context["artifacts"][0].pop("raw")
    h.context["checks"][0]["raw"] = canonical(h.context["checks"][0]["body"]).decode()
    h.reject(event, "MALFORMED_EVENT")


@pytest.mark.parametrize("role", ["worker", "tester"])
def test_consumed_ready_format_replacement_does_not_reapply_business(h, role):
    original, original_ref, rejected_ref, repair = repair_setup(h, consumed=True, role=role)
    h.take(repair, {"repairs": [h.ref(repair)]})
    before = copy.deepcopy(h.state)
    fixed = copy.deepcopy(original)
    fixed["artifact_id"] = h.uid("fixed")
    fixed["replaces"] = {"original": original_ref, "guard_result": rejected_ref}
    fixed["predecessors"].extend([original_ref, rejected_ref, h.ref(repair)])
    fixed["payload"]["dispatch_id"] = repair["payload"]["dispatch_id"]
    slot = "test" if role == "tester" else "worker"
    h.take(fixed, {slot + ".ready": "@incoming"})
    assert h.state["candidate"] == before["candidate"]
    assert h.state["worker"]["pending_correction"] == before["worker"]["pending_correction"]
    tip = "test_tip" if role == "tester" else "implementation_tip"
    assert h.payload(h.state[slot]["ready"])[tip] == original["payload"][tip]
    assert h.state["test"]["approval"] == before["test"]["approval"]


@pytest.mark.parametrize("field", ["status", "implementation_tip", "implementation_index"])
def test_format_repair_cannot_change_preserved_business_values(h, field):
    original, original_ref, rejected_ref, repair = repair_setup(h)
    h.take(repair, {"repairs": [h.ref(repair)]})
    fixed = copy.deepcopy(original)
    fixed["artifact_id"] = h.uid("fixed")
    fixed["replaces"] = {"original": original_ref, "guard_result": rejected_ref}
    fixed["predecessors"].extend([original_ref, rejected_ref, h.ref(repair)])
    fixed["payload"]["dispatch_id"] = repair["payload"]["dispatch_id"]
    if field == "status":
        fixed["payload"][field] = "NOT_READY"
    elif field == "implementation_tip":
        fixed["payload"][field]["commit"] = sha("replacement-unrelated-tip")
    else:
        fixed["payload"][field] = 1
    h.reject(h.event(fixed), "INVALID_EVIDENCE")


def test_stop_after_new_ready_preserves_implementation_ahead_of_candidate(h):
    h.prepared()
    h.result("IMPLEMENTATION_FAIL")
    h.correct()
    h.ready("worker", 1)
    c0 = copy.deepcopy(h.state["candidate"])
    i1 = h.state["worker"]["ready"]
    h.take(h.decision_body("FINAL", "STOP"), {"stop": "@incoming"})
    h.review("HUMAN_STOP")
    h.terminal("RECORD_FAILURE", success=False)
    assert h.state["candidate"] == c0
    assert h.state["worker"]["ready"] == i1
    assert h.payload(h.state["terminal"])["candidate_index"] == 0
    assert h.payload(h.state["terminal"])["correction_count"] == 1


@pytest.mark.parametrize("catalog", ["artifacts", "checks"])
def test_catalog_artifact_ids_are_unique(h, catalog):
    event = h.event(h.artifact("task-contract"))
    h.context[catalog].append(copy.deepcopy(h.context[catalog][0]))
    h.reject(event, "MALFORMED_EVENT")


def test_guard_receipt_is_not_a_business_event(h):
    event = h.event(h.artifact("task-contract"))
    event["artifact"] = copy.deepcopy(event["checked"])
    h.reject(event, "MALFORMED_EVENT")


@pytest.mark.parametrize("slot,key,value", [
    ("worker", "implementation_index", 2),
    ("worker", "implementation_index", True),
    ("worker", "previous_implementation", "f" * 40),
    ("candidate", "candidate_index", 2),
    ("candidate", "correction_count", 1),
])
def test_available_state_facts_cannot_skip_accepted_history(h, slot, key, value):
    h.prepared()
    ref = h.state["worker"]["ready"] if slot == "worker" else h.state["candidate"]["envelope"]
    h.body(ref)["payload"][key] = value
    event = h.event(h.result_body("PASS"))
    h.reject(event, "INVALID_STATE")


def test_error_text_does_not_echo_private_input_payload(h):
    body = h.artifact("task-contract")
    marker = "SECRET_PRIVATE_CASE_CONTEXT_257"
    body["payload"]["private"] = marker
    event = h.event(body, validate=False)
    with pytest.raises(h.target.WorkflowTransitionError) as caught:
        h.target.transition(h.state, event, context=h.context)
    assert marker not in str(caught.value.as_dict())
    assert "Traceback" not in str(caught.value.as_dict())


def test_import_does_not_load_schema_files(api, monkeypatch):
    import builtins
    import io
    import structured_handoff_schema
    source = TARGET.read_text(encoding="utf-8")
    namespace = {"__name__": "owner_purity_import", "__file__": str(TARGET)}
    def forbidden(*args, **kwargs):
        raise AssertionError("R02: importing transition read a schema or performed file I/O")
    with monkeypatch.context() as patch:
        patch.setattr(structured_handoff_schema, "load_schema", forbidden)
        patch.setattr(structured_handoff_schema, "load_registry", forbidden)
        for owner, names in [(builtins, ["open"]), (io, ["open"]),
                             (Path, ["read_text", "read_bytes", "open"])]:
            for name in names:
                patch.setattr(owner, name, forbidden)
        exec(compile(source, str(TARGET), "exec"), namespace)
    assert callable(namespace["transition"])
