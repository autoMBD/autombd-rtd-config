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
# File:        test_workflow_transition_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Independent Worker tests of public transition histories.
# =================================================================================

import copy
import importlib.util
import json
import subprocess
import sys

import pytest

from workflow_transition_generality_support import History, SCRIPTS, canonical, digest


def test_public_module_is_delivered():
    assert (SCRIPTS / "workflow_transition.py").is_file()


@pytest.fixture
def api():
    path = SCRIPTS / "workflow_transition.py"
    assert path.is_file(), "The public transition module must exist"
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("workflow_transition", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["cedar", "marigold"])
def history(api, request):
    return History(api, request.param)


def rejected(h, ref, code, *, event=None, state=None, context=None):
    event = event or h.event(ref)
    state = h.state if state is None else state
    context = h.context if context is None else context
    before = copy.deepcopy((state, event, context))
    with pytest.raises(h.module.WorkflowTransitionError) as caught:
        h.module.transition(state, event, context=context)
    assert caught.value.code == code
    assert caught.value.pointer.startswith("/")
    assert caught.value.as_dict() == {"error": {"code": code, "pointer": caught.value.pointer,
                                                "message": caught.value.message}}
    assert (state, event, context) == before


def test_initial_state_is_closed_and_detached(history):
    h = history
    assert h.state == {"schema_version": "1.0", "workflow_profile": "functional-development-v1",
        "task": h.task, "governor": h.governor, "contract": None,
        "test": {"launch": None, "ack": None, "ready": None, "approval": None},
        "worker": {"launch": None, "ack": None, "ready": None, "pending_correction": None},
        "candidate": None, "review": None, "stop": None, "final_decision": None,
        "terminal": None, "repairs": [], "consumed": []}
    h.state["task"]["task_run"] = "changed"
    assert h.task["task_run"] != "changed"


@pytest.mark.parametrize("order", [("test", "worker"), ("worker", "test")])
def test_independent_lanes_success_proposal(history, order):
    h = history
    h.assembled(order)
    h.result("PASS")
    h.review("TESTER_PASS")
    h.reviewed()
    h.terminal("OPEN_SUCCESS_PR")
    assert h.body(h.state["terminal"])["payload"]["result"] == "SUCCESS"


def test_committed_wire_schema_matches_pure_definitions(api):
    from workflow_transition_wire import definitions
    path = SCRIPTS.parent / "schemas/workflow-transition-v1.schema.json"
    assert path.is_file(), "Portable public wire schema must be committed"
    value = json.loads(path.read_text())
    assert value["$defs"] == definitions()


def test_delivery_repair_is_orthogonal_and_authorizes_new_dispatch(history):
    h = history
    h.start()
    h.launch("worker")
    original = h.ready("worker")
    op = h.body(original)["payload"]
    rejection = rejected_receipt(h, original)
    repair = h.make("delivery-repair", {"dispatch_id": f"{h.seed}-repair-dispatch",
        "original": original, "rejection": rejection, "lane": op["lane"],
        "preserve_tip": op["implementation_tip"]["commit"], "preserve_candidate_index": None,
        "preserve_correction_count": 0, "preserve_review_id": None},
        [original, rejection], consumer_role="worker", visibility="public-task")
    before = copy.deepcopy(h.state)
    h.consume(repair)
    assert h.state["worker"] == before["worker"]
    assert h.state["candidate"] == before["candidate"]
    assert h.state["repairs"] == [repair]
    replacement = report_copy(h, original, dispatch_id=h.body(repair)["payload"]["dispatch_id"])
    body = h.body(replacement)
    body["replaces"] = {"original": original, "guard_result": rejection}
    body["predecessors"] += [original, rejection, repair]
    replacement["sha256"] = digest(body)
    h.consume(replacement)
    assert h.state["worker"]["ready"] == replacement


def test_ready_report_wrong_correction_identity_cannot_hide_in_not_ready(history):
    h = history
    h.assembled()
    h.result("IMPLEMENTATION_FAIL")
    correction = h.correction()
    p = h.body(correction)["payload"]
    ref = h.make("implementation-report", {"status": "NOT_READY", "lane": p["lane"],
        "dispatch_id": p["dispatch_id"], "implementation_index": 2,
        "previous_implementation": p["previous_implementation"], "revision_ack": None}, [correction])
    rejected(h, ref, "STALE_EVENT")


@pytest.mark.parametrize("seed,exhaust", [("cobalt", False), ("jasmine", True)])
def test_cli_selected_full_lifecycle(api, seed, exhaust):
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace

    base = SCRIPTS.parents[3] / "tests/.tmp"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as directory:
        root = Path(directory)

        def cli_transition(state, event, *, context):
            paths = {name: root / f"{name}.json" for name in ("state", "event", "context")}
            for name, value in (("state", state), ("event", event), ("context", context)):
                paths[name].write_bytes(canonical(value))
            argv = [sys.executable, str(SCRIPTS / "workflow_transition.py"), "apply"]
            for name, path in paths.items():
                argv += ["--" + name, str(path)]
            result = subprocess.run(argv, capture_output=True)
            assert result.returncode == 0, result.stderr.decode()
            assert not result.stderr
            value = json.loads(result.stdout)
            assert result.stdout == canonical(value)
            return value

        cli = SimpleNamespace(initial_state=api.initial_state, transition=cli_transition)
        h = History(cli, seed)
        h.assembled(("test", "worker"))
        if exhaust:
            for index in range(1, 4):
                h.result("IMPLEMENTATION_FAIL")
                previous = h.body(h.state["worker"]["ready"])["payload"]["implementation_tip"]["commit"]
                h.correction()
                h.ready("worker", index, previous)
                h.candidate()
            h.result("IMPLEMENTATION_FAIL")
            h.review("CORRECTIONS_EXHAUSTED")
            h.reviewed()
            h.terminal("RECORD_FAILURE")
        else:
            h.result("PASS")
            h.review("TESTER_PASS")
            h.reviewed()
            h.terminal("OPEN_SUCCESS_PR")

    assert h.body(h.state["terminal"])["payload"]["result"] == ("FAILURE" if exhaust else "SUCCESS")


def test_gate_does_not_wait_for_worker(history):
    h = history
    h.start()
    h.launch("test")
    h.ready("test")
    h.approve()
    assert h.state["worker"]["launch"] is None
    h.launch("worker")
    h.ready("worker")
    h.candidate()


def test_three_incremental_corrections_and_stop_preserve_latest_i(history):
    h = history
    h.assembled()
    for index in range(1, 4):
        h.result("IMPLEMENTATION_FAIL")
        prior = h.body(h.state["worker"]["ready"])["payload"]["implementation_tip"]["commit"]
        correction = h.correction()
        assert h.state["worker"]["pending_correction"] == correction
        h.ready("worker", index, prior)
        assert h.state["candidate"] is not None
        assert h.state["worker"]["pending_correction"] is None
        h.candidate()
    h.result("IMPLEMENTATION_FAIL")
    h.review("CORRECTIONS_EXHAUSTED")
    h.reviewed()
    h.terminal("RECORD_FAILURE")
    assert h.body(h.state["terminal"])["payload"]["correction_count"] == 3


def test_stop_between_ready_and_candidate_retains_distinct_tips(history):
    h = history
    h.assembled()
    h.result("IMPLEMENTATION_FAIL")
    old = copy.deepcopy(h.state["candidate"])
    prior = h.body(h.state["worker"]["ready"])["payload"]["implementation_tip"]["commit"]
    h.correction()
    h.ready("worker", 1, prior)
    h.stop()
    assert h.state["candidate"] == old
    h.review("HUMAN_STOP")
    h.reviewed()
    h.terminal("RECORD_FAILURE")
    assert h.body(h.state["terminal"])["payload"]["candidate_index"] == 0
    assert h.body(h.state["terminal"])["payload"]["correction_count"] == 1


def test_invalid_run_rerun_changes_only_execution(history):
    h = history
    h.assembled()
    before = h.state["candidate"]["envelope"]
    invalid_result = h.result("INVALID_RUN")
    h.candidate(rerun=True)
    assert h.body(h.state["candidate"]["envelope"])["payload"]["rerun_of"] == invalid_result
    h.result("PASS")
    h.review("TESTER_PASS")


@pytest.mark.parametrize("outcome,reason", [("TEST_GATE_INVALID", "TEST_GATE_INVALID"),
    ("CONTRACT_INVALID", "CONTRACT_INVALID"), ("INTEGRITY_INVALID", "INTEGRITY_INVALID")])
def test_invalid_gate_routes_to_failure_review(history, outcome, reason):
    h = history
    h.assembled()
    h.result(outcome)
    h.review(reason)
    h.reviewed()
    h.terminal("RECORD_FAILURE")


def test_error_precedence_and_no_mutation(history):
    h = history
    ref = h.start()
    event = h.event(ref)
    # Exact duplicate wins over missing receipt.
    context = copy.deepcopy(h.context)
    context["checks"] = []
    rejected(h, ref, "DUPLICATE_EVENT", event=event, context=context)
    state = copy.deepcopy(h.state)
    state["unexpected"] = True
    rejected(h, ref, "INVALID_STATE", event=event, state=state, context=context)
    event["type"] = "RUN"
    rejected(h, ref, "MALFORMED_EVENT", event=event, state=state, context=context)


def test_missing_and_false_receipts_are_distinct(history):
    h = history
    h.start()
    ref = h.make("worker-launch", {"mode": "INITIAL", "previous_launch": None,
                 "revision_ack_required": False}, [h.contract])
    event = h.event(ref)
    context = copy.deepcopy(h.context)
    context["checks"] = []
    rejected(h, ref, "MISSING_EVIDENCE", event=event, context=context)
    context = copy.deepcopy(h.context)
    context["checks"][-1]["body"]["status"] = "REJECTED"
    rejected(h, ref, "INVALID_EVIDENCE", event=event, context=context)


def test_stale_identity_precedes_missing_evidence(history):
    h = history
    h.start()
    ref = h.make("worker-launch", {"mode": "INITIAL", "previous_launch": None,
        "revision_ack_required": False}, [h.contract])
    event = h.event(ref)
    h.body(ref)["task"] = dict(h.task, task_run="unrelated")
    h.context["checks"] = []
    rejected(h, ref, "STALE_EVENT", event=event)


def test_stop_after_review_does_not_relaunch(history):
    h = history
    h.assembled()
    h.result("PASS")
    launch = h.review("TESTER_PASS")
    h.stop()
    h.reviewed()
    h.terminal("RECORD_FAILURE")
    assert h.state["review"]["launch"] == launch


@pytest.mark.parametrize("bad", [True, 1.25, float("nan"), {"x": object()}])
def test_api_shape_errors_are_structured(api, bad):
    with pytest.raises(api.WorkflowTransitionError):
        api.initial_state(bad, {})


def test_cli_init_and_input_failures(api, history):
    h = history
    import tempfile
    from pathlib import Path
    base = SCRIPTS.parents[3] / "tests/.tmp"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as temp:
        task = Path(temp) / "task.json"
        governor = Path(temp) / "governor.json"
        task.write_bytes(canonical(h.task))
        governor.write_bytes(canonical(h.governor))
        command = [sys.executable, str(SCRIPTS / "workflow_transition.py"), "init",
                   "--task", str(task), "--governor", str(governor)]
        result = subprocess.run(command, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout == canonical(h.state)
        assert result.stderr == b""
        task.write_text('{"x":1,"x":2}')
        result = subprocess.run(command, capture_output=True)
        assert result.returncode == 2 and result.stdout == b""
        assert json.loads(result.stderr)["error"]["code"] == "INPUT_ERROR"
        result = subprocess.run([sys.executable, str(SCRIPTS / "workflow_transition.py"), "absent"],
                                capture_output=True)
        assert result.returncode == 2 and result.stdout == b""
        assert json.loads(result.stderr)["error"]["code"] == "USAGE_ERROR"


def revise(h, lane_order=("worker", "test")):
    old = h.contract
    number = h.body(old)["payload"]["revision"]["number"] + 1
    new = h.make("task-contract", {"revision": {"number": number, "predecessor": old,
        "authority": h.evidence(f"authority-{number}", "authority"),
        "reason": "Changed public interface", "changed_authority_ids": ["interface"],
        "affected_requirement_ids": ["behavior"]}}, [old])
    h.contract = h.consume(new)
    for lane in lane_order:
        prior = h.refs[f"{lane}-launch"]
        p = copy.deepcopy(h.body(prior)["payload"])
        p.update(mode="K_REVISION", dispatch_id=f"{h.seed}-{lane}-revision-{number}",
                 previous_launch=prior, revision_ack_required=True)
        ref = h.make(f"{lane}-launch", p, [new, prior])
        h.refs[f"{lane}-launch"] = h.consume(ref)
    return old, new


def acknowledge(h, lane):
    launch = h.refs[f"{lane}-launch"]
    p = h.body(launch)["payload"]
    old = h.body(p["previous_launch"])["task_contract"]
    ack = {"old_contract": old, "new_contract": h.kref(), "verified_sha256": h.kref()["sha256"],
           "current_tip": h.governor["commit"], "invalidated_receipt_ids": [],
           "retained_work": "Same sources retained", "resume_requirement_ids": []}
    payload = {"status": "K_ACK", "dispatch_id": p["dispatch_id"], "lane": p["lane"],
               "revision_ack": ack}
    if lane == "worker":
        payload.update(implementation_tip=None, manifest=None, previous_implementation=None)
    else:
        payload.update(test_tip=None, manifest=None, impact_set=None)
    return h.consume(h.make("implementation-report" if lane == "worker" else "test-gate-report",
                            payload, [launch]))


def report_copy(h, ref, **changes):
    body = copy.deepcopy(h.body(ref))
    h.serial += 1
    body["artifact_id"] = f"{h.seed}-copy-{h.serial}"
    body["payload"].update(changes)
    return h.register(body)


def test_revised_contract_requires_both_explicit_acknowledgements(history):
    h = history
    h.start()
    for lane in ("worker", "test"):
        h.launch(lane)
        h.ready(lane)
    original_i = h.state["worker"]["ready"]
    revise(h, ("test", "worker"))
    assert h.state["worker"]["ready"] == original_i
    acknowledge(h, "worker")
    launch = h.refs["worker-launch"]
    p = h.body(launch)["payload"]
    premature = h.make("implementation-report", {"status": "READY", "lane": p["lane"],
        "dispatch_id": p["dispatch_id"], "previous_implementation": None, "revision_ack": None},
        [launch])
    rejected(h, premature, "OUT_OF_ORDER_EVENT")
    acknowledge(h, "test")
    h.ready("test")
    h.approve()
    h.ready("worker")
    h.candidate()


def test_not_ready_withdraws_only_own_pre_freeze_readiness(history):
    h = history
    h.start()
    for lane in ("test", "worker"):
        h.launch(lane)
        h.ready(lane)
    worker = h.state["worker"]["ready"]
    ref = report_copy(h, h.state["test"]["ready"], status="NOT_READY",
                      test_tip=None, manifest=None, impact_set=None)
    h.consume(ref)
    assert h.state["test"]["ready"] is None
    assert h.state["worker"]["ready"] == worker
    h.ready("test")
    h.approve()


def test_not_ready_correction_preserves_pending_and_prior_implementation(history):
    h = history
    h.assembled()
    h.result("IMPLEMENTATION_FAIL")
    prior = h.state["worker"]["ready"]
    correction = h.correction()
    p = h.body(correction)["payload"]
    ref = h.make("implementation-report", {"status": "NOT_READY", "lane": p["lane"],
        "dispatch_id": p["dispatch_id"], "implementation_index": 1,
        "previous_implementation": p["previous_implementation"],
        "implementation_tip": None, "manifest": None, "revision_ack": None}, [correction])
    h.consume(ref)
    assert h.state["worker"]["pending_correction"] == correction
    assert h.state["worker"]["ready"] == prior


@pytest.mark.parametrize("decision", ["APPROVE", "REQUEST_CHANGES"])
def test_final_human_decision_closes_exact_proposal(history, decision):
    h = history
    h.assembled()
    h.result("PASS")
    h.review("TESTER_PASS")
    h.reviewed()
    proposal = h.terminal("OPEN_SUCCESS_PR")
    subject = h.body(proposal)["payload"]["accepted_candidate"]
    final = h.consume(h.make("human-decision", {"gate": "FINAL", "decision": decision,
        "subject_sha": subject}, [proposal]))
    if decision == "REQUEST_CHANGES":
        h.terminal("RECORD_FAILURE")
    else:
        merged = report_copy(h, proposal, disposition="MERGED", final_decision=final,
            pr={"url": f"https://example.invalid/{h.seed}/pull/7",
                "head_sha": subject, "merge_sha": h.sha("merge")})
        h.body(merged)["predecessors"].append(final)
        merged["sha256"] = digest(h.body(merged))
        h.consume(merged)
    fresh = h.make("human-decision", {"gate": "FINAL", "decision": "STOP", "subject_sha": subject})
    rejected(h, fresh, "ILLEGAL_TRANSITION")


def test_stop_before_lanes_has_truthful_failure_terminal(history):
    h = history
    h.start()
    h.stop()
    h.review("HUMAN_STOP")
    h.reviewed()
    h.terminal("RECORD_FAILURE")
    assert h.body(h.state["terminal"])["payload"]["preserved_implementation"] is None


@pytest.mark.parametrize("stage", ["launch", "candidate"])
def test_exact_current_artifact_replay_is_duplicate_not_self_stale(history, stage):
    h = history
    h.start()
    ref = h.launch("worker")
    if stage == "candidate":
        h.ready("worker")
        h.launch("test")
        h.ready("test")
        h.approve()
        ref = h.candidate()
    rejected(h, ref, "DUPLICATE_EVENT")


def rejected_receipt(h, original):
    event = h.event(original)
    body = copy.deepcopy(next(e["body"] for e in h.context["checks"] if e["ref"] == event["checked"]))
    body["artifact_id"] += "-rejected"
    body["status"] = "REJECTED"
    body["exit_code"] = 1
    body["violations"] = [{"rule_id": "DELIVERY_FORMAT", "field_pointer": "/",
                           "safe_diagnostic": "Delivery needs format repair."}]
    return h.register(body)


@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("raw", [False, True])
def test_format_replacement_preserves_business_state(history, accepted, raw):
    h = history
    h.start()
    h.launch("worker")
    if accepted:
        original = h.ready("worker")
    else:
        launch = h.refs["worker-launch"]
        p = h.body(launch)["payload"]
        original = h.make("implementation-report", {"status": "READY", "lane": p["lane"],
            "dispatch_id": p["dispatch_id"], "revision_ack": None, "previous_implementation": None,
            "implementation_tip": h.tip("pending-implementation")}, [launch])
    if raw:
        import hashlib
        entry = next(e for e in h.context["artifacts"] if e["ref"] == original)
        entry["raw"] = (canonical(entry["body"]).decode() if accepted else
                        json.dumps(entry["body"], ensure_ascii=False, indent=2))
        original["sha256"] = hashlib.sha256(entry["raw"].encode()).hexdigest()
    rejection = rejected_receipt(h, original)
    replacement = report_copy(h, original)
    body = h.body(replacement)
    body["replaces"] = {"original": original, "guard_result": rejection}
    body["predecessors"] += [original, rejection]
    replacement["sha256"] = digest(body)
    previous_count = len(h.state["consumed"])
    h.consume(replacement)
    assert h.state["worker"]["ready"] == replacement
    assert len(h.state["consumed"]) == previous_count + 1
    assert h.body(replacement)["payload"]["implementation_index"] == 0


def test_raw_duplicate_keys_cannot_authorize_guessed_repair(history):
    h = history
    h.start()
    h.launch("worker")
    original = h.ready("worker")
    rejection = rejected_receipt(h, original)
    replacement = report_copy(h, original)
    body = h.body(replacement)
    body["replaces"] = {"original": original, "guard_result": rejection}
    body["predecessors"] += [original, rejection]
    replacement["sha256"] = digest(body)
    entry = next(e for e in h.context["artifacts"] if e["ref"] == original)
    entry["raw"] = '{"payload":{},"payload":{}}'
    rejected(h, replacement, "INVALID_EVIDENCE")


def test_stale_old_execution_result_precedes_absent_checks(history):
    h = history
    h.assembled()
    stale_result = h.result("INVALID_RUN")
    h.candidate(rerun=True)
    event = h.event(stale_result)
    h.context["checks"] = []
    rejected(h, stale_result, "STALE_EVENT", event=event)


@pytest.mark.parametrize("change", ["float", "unknown", "missing", "boolean_counter"])
def test_closed_incoming_shape_precedes_state(history, change):
    h = history
    h.start()
    h.launch("worker")
    original = h.ready("worker")
    ref = report_copy(h, original)
    body = h.body(ref)
    if change == "float":
        body["payload"]["implementation_index"] = 0.0
    elif change == "unknown":
        body["payload"]["unknown"] = False
    elif change == "missing":
        del body["payload"]["status"]
    else:
        body["payload"]["implementation_index"] = True
    event = h.event(ref)
    state = dict(h.state, extra=True)
    rejected(h, ref, "MALFORMED_EVENT", event=event, state=state)


def test_missing_historical_body_is_evidence_not_invalid_state(history):
    h = history
    h.start()
    launch = h.launch("worker")
    ref = h.make("implementation-report", {"status": "NOT_READY",
        "lane": h.body(launch)["payload"]["lane"], "dispatch_id": h.body(launch)["payload"]["dispatch_id"],
        "previous_implementation": None, "revision_ack": None}, [launch])
    event = h.event(ref)
    h.context["artifacts"] = [e for e in h.context["artifacts"] if e["ref"] != h.contract]
    rejected(h, ref, "MISSING_EVIDENCE", event=event)


def test_protocol_unknown_schema_keyword_fails_closed(history):
    h = history
    ref = h.start()
    event = h.event(ref)
    context = copy.deepcopy(h.context)
    context["protocol"]["handoff_schema"]["$defs"]["implementation-report"]["not"] = {}
    rejected(h, ref, "MALFORMED_EVENT", event=event, context=context)


@pytest.mark.parametrize("which", ["worker", "test"])
def test_withdrawn_ready_cannot_assemble_or_approve(history, which):
    h = history
    h.start()
    for lane in ("worker", "test"):
        h.launch(lane)
        h.ready(lane)
    key = "implementation_tip" if which == "worker" else "test_tip"
    ref = report_copy(h, h.refs[f"{which}-ready"], status="CONTRACT_AMBIGUITY",
                      **{key: None, "manifest": None})
    h.consume(ref)
    if which == "test":
        decision = h.make("human-decision", {"gate": "TEST", "decision": "APPROVE",
                         "subject_sha": h.sha("unavailable")}, [ref])
        rejected(h, decision, "OUT_OF_ORDER_EVENT")


def test_second_pending_correction_is_illegal_not_a_new_grant(history):
    h = history
    h.assembled()
    h.result("IMPLEMENTATION_FAIL")
    original = h.correction()
    second = report_copy(h, original)
    rejected(h, second, "ILLEGAL_TRANSITION")


def test_second_candidate_from_unchanged_implementation_is_illegal(history):
    h = history
    h.assembled()
    h.result("IMPLEMENTATION_FAIL")
    old = h.state["candidate"]["envelope"]
    fresh = report_copy(h, old, previous_candidate=old,
        dispatch_id=f"{h.seed}-new-dispatch", execution_id=f"{h.seed}-new-execution")
    h.body(fresh)["predecessors"].append(old)
    fresh["sha256"] = digest(h.body(fresh))
    rejected(h, fresh, "ILLEGAL_TRANSITION")


def test_rerun_dispatch_cannot_reuse_any_accepted_dispatch(history):
    h = history
    h.assembled()
    old = h.state["candidate"]["envelope"]
    invalid = h.result("INVALID_RUN")
    launch_dispatch = h.body(h.refs["worker-launch"])["payload"]["dispatch_id"]
    fresh = report_copy(h, old, rerun_of=invalid, dispatch_id=launch_dispatch,
                        execution_id=f"{h.seed}-new-execution")
    h.body(fresh)["predecessors"] += [old, invalid]
    fresh["sha256"] = digest(h.body(fresh))
    rejected(h, fresh, "STALE_EVENT")


def test_missing_receipt_identity_is_invalid_evidence_not_stale(history):
    h = history
    h.start()
    ref = h.make("worker-launch", {"mode": "INITIAL", "previous_launch": None,
        "revision_ack_required": False}, [h.contract])
    event = h.event(ref)
    receipt = next(x for x in h.context["checks"] if x["ref"] == event["checked"])
    del receipt["body"]["trusted_context"]["task"]
    rejected(h, ref, "INVALID_EVIDENCE", event=event)


def test_available_state_relationship_is_checked_despite_other_missing_body(history):
    h = history
    h.assembled()
    state = copy.deepcopy(h.state)
    state["test"]["ready"] = None
    event = h.event(h.state["candidate"]["envelope"])
    h.context["artifacts"] = [e for e in h.context["artifacts"] if e["ref"] != h.contract]
    rejected(h, event["artifact"], "INVALID_STATE", event=event, state=state)


def test_boolean_workflow_index_is_not_integer_configuration(history):
    h = history
    ref = h.start()
    event = h.event(ref)
    context = copy.deepcopy(h.context)
    context["protocol"]["workflow_contract"]["lifecycle"]["initial_candidate"] = False
    rejected(h, ref, "MALFORMED_EVENT", event=event, context=context)


def test_business_artifacts_cannot_resolve_from_receipt_catalog(history):
    h = history
    ref = h.start()
    # Supply a new legal launch only in the wrong memory catalog.
    launch = h.make("worker-launch", {"mode": "INITIAL", "previous_launch": None,
        "revision_ack_required": False}, [ref])
    event = h.event(launch)
    entry = next(e for e in h.context["artifacts"] if e["ref"] == launch)
    h.context["artifacts"].remove(entry)
    h.context["checks"].append(entry)
    rejected(h, launch, "MISSING_EVIDENCE", event=event)


def test_api_core_performs_no_file_process_time_or_platform_operations(history, monkeypatch):
    h = history
    import builtins
    import pathlib
    import subprocess
    import time

    def prohibited(*args, **kwargs):
        pytest.fail("Pure transition core attempted an external operation")

    for owner, name in ((builtins, "open"), (pathlib.Path, "read_bytes"),
                        (pathlib.Path, "read_text"), (pathlib.Path, "resolve"),
                        (subprocess, "run"), (subprocess, "Popen"),
                        (time, "time"), (time, "sleep")):
        monkeypatch.setattr(owner, name, prohibited)
    h.assembled()
    h.result("PASS")
    h.review("TESTER_PASS")
    h.reviewed()
    h.terminal("OPEN_SUCCESS_PR")


def test_next_state_references_are_detached_from_event_and_catalog(history):
    h = history
    ref = h.make("task-contract", {"revision": {"number": 0, "predecessor": None,
        "authority": None, "reason": "Initial public contract", "changed_authority_ids": [],
        "affected_requirement_ids": []}})
    event = h.event(ref)
    before = copy.deepcopy((event, h.context))
    output = h.module.transition(h.state, event, context=h.context)
    output["contract"]["artifact_id"] = "caller-mutated"
    assert (event, h.context) == before


def test_reviewer_delivery_replacement_after_proposal_retains_logical_review(history):
    h = history
    h.assembled()
    h.result("PASS")
    h.review("TESTER_PASS")
    original = h.reviewed()
    proposal = h.terminal("OPEN_SUCCESS_PR")
    rejection = rejected_receipt(h, original)
    replacement = report_copy(h, original)
    body = h.body(replacement)
    body["replaces"] = {"original": original, "guard_result": rejection}
    body["predecessors"] += [original, rejection]
    replacement["sha256"] = digest(body)
    h.consume(replacement)
    assert h.state["review"]["report"] == replacement
    assert h.state["terminal"] == proposal


def test_internal_output_invariant_has_distinct_error(history, monkeypatch):
    h = history
    ref = h.make("task-contract", {"revision": {"number": 0, "predecessor": None,
        "authority": None, "reason": "Initial public contract", "changed_authority_ids": [],
        "affected_requirement_ids": []}})
    real = h.module.business_plan

    def corrupted(*args, **kwargs):
        output = real(*args, **kwargs)
        output["unregistered"] = True
        return output

    monkeypatch.setattr(h.module, "business_plan", corrupted)
    rejected(h, ref, "INVALID_OUTPUT")


def test_public_event_schema_excludes_business_receipts(history):
    h = history
    from workflow_transition_wire import validate
    schema = json.loads((SCRIPTS.parent / "schemas/workflow-transition-v1.schema.json").read_text())
    ref = h.start()
    event = h.event(ref)
    event["artifact"] = event["checked"]
    with pytest.raises(h.module.WorkflowTransitionError):
        validate(event, schema["$defs"]["Event"], schema["$defs"], "MALFORMED_EVENT")


def test_deep_initial_input_is_a_structured_programmer_error(api):
    task = {"repository": "sample/deep", "issue_number": 91, "task_run": "deep"}
    value = task
    for _ in range(1200):
        value["nested"] = {}
        value = value["nested"]
    with pytest.raises(api.WorkflowTransitionError):
        api.initial_state(task, {})


@pytest.mark.parametrize("lane", ["worker", "test"])
def test_invalid_execution_allows_only_reference_repair_of_accepted_ready(history, lane):
    h = history
    h.assembled()
    h.result("INVALID_RUN")
    original = h.state[lane]["ready"]
    before = copy.deepcopy(h.state)
    rejection = rejected_receipt(h, original)
    replacement = report_copy(h, original)
    body = h.body(replacement)
    body["replaces"] = {"original": original, "guard_result": rejection}
    body["predecessors"] += [original, rejection]
    replacement["sha256"] = digest(body)
    h.consume(replacement)
    assert h.state[lane]["ready"] == replacement
    assert h.state["candidate"] == before["candidate"]
    assert h.state["worker"]["pending_correction"] is None
    changed = report_copy(h, original, status="NOT_READY")
    rejected(h, changed, "ILLEGAL_TRANSITION")
