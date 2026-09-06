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
# File:        workflow_transition_rules.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.1
# Description: Pure global lifecycle and identity rules for transitions.
# =================================================================================

import copy

from workflow_transition_wire import WorkflowTransitionError, require

PRIORITY = {name: index for index, name in enumerate((
    "STALE_EVENT", "DUPLICATE_EVENT", "ILLEGAL_TRANSITION", "OUT_OF_ORDER_EVENT",
    "MISSING_EVIDENCE", "INVALID_EVIDENCE"))}


class Decision:
    """Collect independently observable failures, then apply public precedence."""

    def __init__(self):
        self.failures = []

    def check(self, condition, code, pointer):
        if not condition:
            self.failures.append((PRIORITY[code], len(self.failures), code, pointer))

    def finish(self):
        if self.failures:
            _, _, code, pointer = min(self.failures)
            raise WorkflowTransitionError(code, pointer)


def payload(body):
    return body.get("payload", {}) if body else {}


def commit(tip):
    return tip.get("commit") if type(tip) is dict else None


def equivalent_ref(original, current, memory):
    """Follow checked replacement identities without changing historical bytes."""
    visited = set()
    while current and current["artifact_id"] not in visited:
        if current == original:
            return True
        visited.add(current["artifact_id"])
        body = memory.get(current)
        current = body["replaces"]["original"] if body and body.get("replaces") else None
    return False


def slot_refs(state):
    for key in ("contract", "stop", "final_decision", "terminal"):
        if state[key]:
            yield "/" + key, state[key]
    for lane in ("test", "worker", "candidate", "review"):
        if state[lane]:
            for key, value in state[lane].items():
                if value:
                    yield "/" + lane + "/" + key, value
    for index, ref in enumerate(state["repairs"]):
        yield "/repairs/" + str(index), ref


class Memory:
    """Reference lookup only; absence is not repaired with filesystem access."""

    def __init__(self, context):
        self.context = context
        self.entries = {item["ref"]["artifact_id"]: item for item in context["artifacts"]}
        self.checks = {item["ref"]["artifact_id"]: item for item in context["checks"]}

    def entry(self, ref):
        if not ref:
            return None
        return self.entries.get(ref["artifact_id"]) or (
            self.checks.get(ref["artifact_id"]) if ref["kind"] == "guard-result" else None)

    def get(self, ref):
        entry = self.entry(ref)
        return entry["body"] if entry else None

    def p(self, ref):
        return payload(self.get(ref))


def contract_ref(ref, memory):
    if not ref:
        return None
    body = memory.get(ref)
    if body:
        return {"revision": body["payload"]["revision"]["number"],
                "path": ref["path"], "sha256": ref["sha256"]}
    return None


def history_bodies(state, memory, kind=None):
    return [body for item in state["consumed"]
            if (body := memory.get(item["artifact"])) and
            (kind is None or body.get("artifact_kind") == kind)]


def _replace_slots(state, original, replacement):
    for key in ("contract", "stop", "final_decision", "terminal"):
        if state[key] == original:
            state[key] = copy.deepcopy(replacement)
    for lane in ("test", "worker", "candidate", "review"):
        if state[lane]:
            for key, value in state[lane].items():
                if value == original:
                    state[lane][key] = copy.deepcopy(replacement)
    state["repairs"] = [copy.deepcopy(replacement) if value == original else value
                        for value in state["repairs"]]


def business_plan(state, artifact, ref, memory, decision):
    """Return a proposed state; no mutation of any supplied value occurs."""
    result = copy.deepcopy(state)
    kind = ref["kind"]
    p = payload(artifact)
    present = artifact is not None
    consumed = [item["artifact"] for item in state["consumed"]]
    current_k = contract_ref(state["contract"], memory)
    test = memory.p(state["test"]["ready"])
    impl = memory.p(state["worker"]["ready"])
    candidate = memory.p(state["candidate"]["envelope"]) if state["candidate"] else {}
    tester = memory.p(state["candidate"]["result"]) if state["candidate"] else {}
    review = memory.p(state["review"]["launch"]) if state["review"] else {}
    reviewed = memory.p(state["review"]["report"]) if state["review"] else {}
    terminal = memory.p(state["terminal"])
    final = memory.p(state["final_decision"])
    outcome = tester.get("outcome")
    stop = kind == "human-decision" and p.get("gate") == "FINAL" and p.get("decision") == "STOP"
    repair = kind == "delivery-repair"
    replacement = artifact.get("replaces") if artifact else None
    accepted_replacement = bool(replacement and replacement["original"] in consumed)
    original = memory.get(replacement["original"]) if replacement else None
    original_payload = payload(original)
    repaired_dispatch = False

    def ck(condition, code, field):
        decision.check(condition, code, "/artifact/" + field)

    def stale(condition, field):
        ck(condition, "STALE_EVENT", field)

    def illegal(condition, field="payload"):
        ck(condition, "ILLEGAL_TRANSITION", field)

    def order(condition, field="predecessors"):
        ck(condition, "OUT_OF_ORDER_EVENT", field)

    def evidence(condition, field):
        ck(condition, "INVALID_EVIDENCE", field)

    def direct(required):
        if required and present:
            order(required in artifact["predecessors"], "predecessors")

    if present:
        stale(artifact["task"] == state["task"], "task")
        stale(artifact["governor"] == state["governor"], "governor")
        if kind != "task-contract" and current_k:
            stale(artifact["task_contract"] == current_k, "task_contract")
        if replacement:
            if original:
                stale(original.get("task") == artifact["task"] and
                      original.get("governor") == artifact["governor"] and
                      original.get("task_contract") == artifact["task_contract"],
                      "replaces/original")
                evidence(original.get("artifact_kind") == kind and
                         original.get("artifact_id") != artifact["artifact_id"], "replaces/original")
                preserved = ("status", "outcome", "verdict", "implementation_index", "implementation_tip",
                    "previous_implementation", "test_tip", "candidate", "candidate_index", "candidate_sha",
                    "correction_count", "review_id", "lane", "result", "accepted_candidate",
                    "preserved_implementation", "impact_set", "manifest", "test_manifest",
                    "implementation_manifest", "execution_id", "coverage_join", "rerun_of",
                    "previous_candidate", "terminal_reason", "last_implementation", "source_reports",
                    "disposition", "pr", "final_decision", "revision_ack")
                for field in preserved:
                    evidence(p.get(field) == original_payload.get(field), "payload/" + field)
                required_business = {"test-gate-report": "status", "implementation-report": "status",
                    "tester-confidential-report": "outcome", "reviewer-report": "verdict",
                    "terminal-record": "result"}.get(kind)
                if required_business:
                    evidence(required_business in original_payload, "replaces/original")
                if p.get("dispatch_id") != original_payload.get("dispatch_id"):
                    repairs = [memory.p(x) for x in state["repairs"]
                               if memory.p(x).get("original") == replacement["original"]]
                    match = next((r for r in repairs if r.get("dispatch_id") == p.get("dispatch_id")), None)
                    evidence(match is not None, "payload/dispatch_id")
                    repaired_dispatch = match is not None
            rejection = memory.get(replacement["guard_result"])
            if rejection:
                evidence(rejection.get("status") == "REJECTED" and
                    rejection.get("input") == {k: replacement["original"][k]
                                              for k in ("artifact_id", "path", "sha256")}, "replaces/guard_result")
            direct(replacement["original"]) if not accepted_replacement else None
            direct(replacement["guard_result"])

    # Frozen/terminal restrictions are evaluated independently of missing evidence.
    closed = terminal.get("disposition") in ("MERGED", "RECORD_FAILURE")
    illegal(not closed)
    if not state["contract"]:
        order(kind == "task-contract")
    if state["stop"]:
        illegal(kind in ("reviewer-launch", "reviewer-report", "terminal-record", "delivery-repair")
                or accepted_replacement, "payload")
        if kind == "terminal-record":
            illegal(p.get("disposition") == "RECORD_FAILURE", "payload/disposition")
    if state["review"]:
        illegal(kind not in ("worker-launch", "test-launch", "task-contract",
                "implementation-report", "test-gate-report", "candidate-test-envelope",
                "tester-confidential-report", "worker-correction-envelope") or accepted_replacement)
    if terminal.get("disposition") == "OPEN_SUCCESS_PR":
        illegal(kind in ("human-decision", "terminal-record", "delivery-repair") or accepted_replacement)
        if kind == "human-decision":
            illegal(p.get("gate") == "FINAL", "payload/gate")
    if state["test"]["approval"]:
        illegal(kind not in ("task-contract", "test-launch", "test-gate-report") or accepted_replacement)
        if kind == "human-decision" and p.get("gate") == "TEST":
            illegal(accepted_replacement, "payload/gate")
    if outcome in ("PASS", "TEST_GATE_INVALID", "CONTRACT_INVALID", "INTEGRITY_INVALID") or (
            outcome == "IMPLEMENTATION_FAIL" and candidate.get("candidate_index") == 3):
        illegal(kind not in ("implementation-report", "worker-correction-envelope",
                "candidate-test-envelope", "worker-launch", "test-launch", "test-gate-report",
                "task-contract") or accepted_replacement)
    if outcome == "INVALID_RUN":
        illegal(kind not in ("implementation-report", "worker-correction-envelope",
                "worker-launch", "test-launch", "test-gate-report", "task-contract") or accepted_replacement)
        if kind == "candidate-test-envelope":
            illegal(bool(p.get("rerun_of")) or accepted_replacement, "payload/rerun_of")

    # Logical repair does not replay READY, correction, execution or review.
    if accepted_replacement:
        _replace_slots(result, replacement["original"], ref)
        return result

    if kind == "task-contract":
        if present:
            if ref == state["contract"]:
                return result
            revision = p["revision"]
            if state["contract"]:
                illegal(not state["test"]["approval"])
                old = memory.p(state["contract"])
                if old:
                    stale(revision["number"] == old["revision"]["number"] + 1, "payload/revision/number")
                stale(revision["predecessor"] == state["contract"], "payload/revision/predecessor")
                direct(state["contract"])
                evidence(revision["authority"] is not None, "payload/revision/authority")
            else:
                stale(revision["number"] == 0 and revision["predecessor"] is None,
                      "payload/revision")
                order(not state["consumed"])
            result["contract"] = ref
            result["test"]["ack"] = result["worker"]["ack"] = None
    elif kind in ("test-launch", "worker-launch"):
        lane = "test" if kind == "test-launch" else "worker"
        old_ref = state[lane]["launch"]
        if ref == old_ref:
            return result
        old = memory.p(old_ref)
        if present:
            direct(state["contract"])
            if p["mode"] == "INITIAL":
                illegal(not old_ref, "payload/mode")
                stale(p["previous_launch"] is None, "payload/previous_launch")
                evidence(not p["revision_ack_required"], "payload/revision_ack_required")
            else:
                order(old_ref is not None)
                if old:
                    stale(p["lane"] == old["lane"], "payload/lane")
                    stale(p["previous_launch"] == old_ref, "payload/previous_launch")
                    old_body = memory.get(old_ref)
                    illegal(old_body["task_contract"] != current_k, "task_contract")
                direct(old_ref)
                evidence(p["revision_ack_required"], "payload/revision_ack_required")
            for old_launch in history_bodies(state, memory, kind):
                stale(p["dispatch_id"] != old_launch["payload"]["dispatch_id"], "payload/dispatch_id")
            result[lane]["launch"] = ref
            result[lane]["ack"] = None
    elif kind in ("test-gate-report", "implementation-report"):
        lane = "test" if kind == "test-gate-report" else "worker"
        pending = state["worker"]["pending_correction"] if lane == "worker" else None
        launch_ref = pending or state[lane]["launch"]
        launch = memory.p(launch_ref)
        order(launch_ref is not None)
        if present and launch:
            stale(p["lane"] == launch["lane"], "payload/lane")
            stale(p["dispatch_id"] == launch["dispatch_id"] or repaired_dispatch, "payload/dispatch_id")
            if memory.get(launch_ref).get("task_contract"):
                stale(artifact["task_contract"] == memory.get(launch_ref)["task_contract"], "task_contract")
            direct(launch_ref)
        if lane == "worker" and state["candidate"]:
            illegal(bool(pending), "payload/implementation_index")
        if present:
            status = p["status"]
            if lane == "worker" and pending and launch:
                stale(p["implementation_index"] == launch["correction_index"], "payload/implementation_index")
                stale(p["previous_implementation"] == launch["previous_implementation"], "payload/previous_implementation")
            if status == "K_ACK":
                ack = p["revision_ack"]
                illegal(not pending, "payload/status")
                evidence(ack is not None, "payload/revision_ack")
                if launch:
                    evidence(launch.get("revision_ack_required") is True, "payload/revision_ack")
                    old_launch = memory.get(launch.get("previous_launch"))
                    if ack and old_launch:
                        stale(ack["old_contract"] == old_launch["task_contract"], "payload/revision_ack/old_contract")
                if ack:
                    stale(ack["new_contract"] == artifact["task_contract"] and
                          ack["verified_sha256"] == artifact["task_contract"]["sha256"],
                          "payload/revision_ack/new_contract")
                illegal(state[lane]["ack"] is None, "payload/status")
                result[lane]["ack"] = ref
            else:
                evidence(p["revision_ack"] is None, "payload/revision_ack")
                if status == "READY":
                    if current_k and current_k["revision"] > 0:
                        for peer in ("test", "worker"):
                            ack_ref = state[peer]["ack"]
                            order(ack_ref is not None)
                            ack_body = memory.get(ack_ref)
                            if ack_body:
                                stale(ack_body["task_contract"] == current_k, "task_contract")
                    tip_key = "test_tip" if lane == "test" else "implementation_tip"
                    evidence(p[tip_key] is not None and p["manifest"] is not None, "payload/" + tip_key)
                    if lane == "test":
                        evidence(p["impact_set"] is not None, "payload/impact_set")
                    elif pending:
                        if launch:
                            stale(p["implementation_index"] == launch["correction_index"], "payload/implementation_index")
                            stale(p["previous_implementation"] == launch["previous_implementation"], "payload/previous_implementation")
                        if impl:
                            stale(p["implementation_index"] == impl["implementation_index"] + 1 and
                                  p["previous_implementation"] == commit(impl["implementation_tip"]),
                                  "payload/previous_implementation")
                        result["worker"]["pending_correction"] = None
                    else:
                        stale(p["implementation_index"] == 0 and p["previous_implementation"] is None,
                              "payload/implementation_index")
                    result[lane]["ready"] = ref
                elif lane == "test" or not pending:
                    result[lane]["ready"] = None
    elif kind == "human-decision":
        if present:
            if p["gate"] == "TEST":
                illegal(p["decision"] != "STOP", "payload/decision")
                order(state["test"]["ready"] is not None)
                if test:
                    stale(p["subject_sha"] == commit(test["test_tip"]), "payload/subject_sha")
                    ready_body = memory.get(state["test"]["ready"])
                    stale(ready_body["task_contract"] == current_k, "task_contract")
                direct(state["test"]["ready"])
                if p["decision"] == "APPROVE":
                    result["test"]["approval"] = ref
                elif p["decision"] == "REQUEST_CHANGES":
                    result["test"]["ready"] = None
            else:
                expected = commit(candidate.get("candidate")) if state["candidate"] else None
                if candidate or state["candidate"] is None:
                    stale(p["subject_sha"] == expected, "payload/subject_sha")
                if stop:
                    result["stop"] = ref
                else:
                    order(bool(state["terminal"]))
                    if terminal:
                        illegal(terminal["disposition"] == "OPEN_SUCCESS_PR")
                    illegal(not state["final_decision"], "payload/decision")
                    direct(state["terminal"])
                    result["final_decision"] = ref
    elif kind == "candidate-test-envelope":
        if state["candidate"] and ref == state["candidate"]["envelope"]:
            return result
        order(state["test"]["approval"] is not None and state["test"]["ready"] is not None
              and state["worker"]["ready"] is not None)
        illegal(not state["worker"]["pending_correction"], "payload/candidate_index")
        if present:
            for needed in (state["test"]["approval"], state["test"]["ready"], state["worker"]["ready"]):
                direct(needed)
            for report_ref in (state["test"]["ready"], state["worker"]["ready"]):
                report = memory.get(report_ref)
                if report:
                    stale(report["task_contract"] == current_k, "task_contract")
            if test:
                for key, target in (("test_tip", "test_tip"), ("test_manifest", "manifest"),
                                    ("impact_set", "impact_set")):
                    stale(p[key] == test[target], "payload/" + key)
            if impl:
                stale(p["implementation_tip"] == impl["implementation_tip"], "payload/implementation_tip")
                stale(p["implementation_manifest"] == impl["manifest"], "payload/implementation_manifest")
                stale(p["candidate_index"] == impl["implementation_index"], "payload/candidate_index")
            stale(p["candidate_index"] == p["correction_count"], "payload/correction_count")
            evidence(p["candidate"]["parents"] == [commit(p["test_tip"]), commit(p["implementation_tip"])],
                     "payload/candidate/parents")
            for old in history_bodies(state, memory):
                for field in ("execution_id", "dispatch_id"):
                    stale(p[field] != old["payload"].get(field), "payload/" + field)
            if p["rerun_of"]:
                order(state["candidate"] is not None and state["candidate"]["result"] is not None)
                if tester:
                    illegal(outcome == "INVALID_RUN", "payload/rerun_of")
                if state["candidate"]:
                    stale(p["rerun_of"] == state["candidate"]["result"], "payload/rerun_of")
                    direct(state["candidate"]["result"])
                    direct(state["candidate"]["envelope"])
                if candidate:
                    for key in ("candidate", "test_tip", "implementation_tip", "test_manifest",
                                "implementation_manifest", "impact_set", "coverage_join",
                                "candidate_index", "correction_count", "previous_candidate"):
                        stale(p[key] == candidate[key], "payload/" + key)
            elif state["candidate"]:
                order(state["candidate"]["result"] is not None)
                if tester:
                    illegal(outcome == "IMPLEMENTATION_FAIL", "payload/candidate_index")
                if candidate:
                    illegal(p["candidate_index"] > candidate["candidate_index"], "payload/candidate_index")
                    if p["candidate_index"] > candidate["candidate_index"]:
                        stale(p["candidate_index"] == candidate["candidate_index"] + 1, "payload/candidate_index")
                stale(p["previous_candidate"] == state["candidate"]["envelope"], "payload/previous_candidate")
                direct(state["candidate"]["envelope"])
            else:
                stale(p["candidate_index"] == 0 and p["previous_candidate"] is None, "payload/candidate_index")
            result["candidate"] = {"envelope": ref, "result": None}
    elif kind == "tester-confidential-report":
        order(state["candidate"] is not None)
        if state["candidate"]:
            illegal(state["candidate"]["result"] is None, "payload/outcome")
            if present:
                direct(state["candidate"]["envelope"])
        if present and candidate:
            for key in ("dispatch_id", "execution_id", "candidate_index"):
                stale(p[key] == candidate[key], "payload/" + key)
            stale(p["candidate_sha"] == commit(candidate["candidate"]), "payload/candidate_sha")
        if result["candidate"]:
            result["candidate"]["result"] = ref
    elif kind == "worker-correction-envelope":
        order(state["candidate"] is not None and bool(state["candidate"]["result"]))
        order(state["worker"]["ready"] is not None)
        illegal(state["worker"]["pending_correction"] is None, "payload/correction_index")
        if tester:
            illegal(outcome == "IMPLEMENTATION_FAIL", "payload/correction_index")
        if candidate:
            illegal(candidate["candidate_index"] < 3, "payload/correction_index")
            if present:
                stale(p["correction_index"] == candidate["candidate_index"] + 1, "payload/correction_index")
        if present:
            launch = memory.p(state["worker"]["launch"])
            if launch:
                stale(p["lane"] == launch["lane"], "payload/lane")
            if impl:
                stale(p["previous_implementation"] == commit(impl["implementation_tip"]), "payload/previous_implementation")
                stale(p["correction_index"] == impl["implementation_index"] + 1, "payload/correction_index")
            if state["candidate"] and state["candidate"]["result"]:
                report_ref = state["candidate"]["result"]
                disclosure = p["disclosure_review"]
                stale(disclosure["source_report_id"] == report_ref["artifact_id"] and
                      disclosure["source_report_sha256"] == report_ref["sha256"], "payload/disclosure_review")
            direct(state["worker"]["ready"])
            result["worker"]["pending_correction"] = ref
    elif kind == "reviewer-launch":
        illegal(state["review"] is None, "payload/review_id")
        if not state["stop"]:
            order(bool(state["candidate"] and state["candidate"]["result"]))
            if tester:
                illegal(outcome not in ("INVALID_RUN",) and not (
                    outcome == "IMPLEMENTATION_FAIL" and candidate.get("candidate_index", 0) < 3),
                    "payload/terminal_reason")
        reason = ("HUMAN_STOP" if state["stop"] else "TESTER_PASS" if outcome == "PASS" else
                  "CORRECTIONS_EXHAUSTED" if outcome == "IMPLEMENTATION_FAIL" else outcome)
        if present:
            if reason:
                stale(p["terminal_reason"] == reason, "payload/terminal_reason")
            if candidate or not state["candidate"]:
                stale(p["candidate"] == candidate.get("candidate"), "payload/candidate")
            if impl or not state["worker"]["ready"]:
                stale(p["last_implementation"] == commit(impl.get("implementation_tip")), "payload/last_implementation")
            source = state["stop"] or (state["candidate"]["result"] if state["candidate"] else None)
            if source:
                stale(source in p["source_reports"], "payload/source_reports")
                direct(source)
            result["review"] = {"launch": ref, "report": None}
    elif kind == "reviewer-report":
        order(state["review"] is not None)
        if state["review"]:
            illegal(state["review"]["report"] is None, "payload/review_id")
            if present:
                direct(state["review"]["launch"])
        if present and review:
            stale(p["review_id"] == review["review_id"], "payload/review_id")
            stale(p["dispatch_id"] == review["dispatch_id"] or repaired_dispatch, "payload/dispatch_id")
        if result["review"]:
            result["review"]["report"] = ref
    elif kind == "terminal-record":
        order(bool(state["review"] and state["review"]["report"]))
        if present:
            report_ref = state["review"]["report"] if state["review"] else None
            if report_ref:
                stale(p["review"] == report_ref, "payload/review")
                direct(report_ref)
            if candidate or not state["candidate"]:
                stale(p["candidate_index"] == candidate.get("candidate_index"), "payload/candidate_index")
            if impl or not state["worker"]["ready"]:
                stale(p["preserved_implementation"] == commit(impl.get("implementation_tip")), "payload/preserved_implementation")
                stale(p["correction_count"] == impl.get("implementation_index", 0), "payload/correction_count")
            successful = outcome == "PASS" and reviewed.get("verdict") == "APPROVED" and not state["stop"]
            cancelled = final.get("decision") == "REQUEST_CHANGES"
            if p["disposition"] == "RECORD_FAILURE":
                illegal(not successful or cancelled, "payload/disposition")
                evidence(p["result"] == "FAILURE" and p["accepted_candidate"] is None and p["pr"] is None,
                         "payload/result")
            else:
                illegal(successful and not cancelled, "payload/disposition")
                evidence(p["result"] == "SUCCESS", "payload/result")
                if candidate:
                    stale(p["accepted_candidate"] == commit(candidate["candidate"]), "payload/accepted_candidate")
                if p["pr"]:
                    stale(p["pr"]["head_sha"] == p["accepted_candidate"], "payload/pr/head_sha")
                if p["disposition"] == "MERGED":
                    order(state["terminal"] is not None and state["final_decision"] is not None)
                    if final:
                        illegal(final["decision"] == "APPROVE", "payload/final_decision")
                    stale(p["final_decision"] == state["final_decision"], "payload/final_decision")
                    direct(state["final_decision"])
                    evidence(p["pr"] is not None and p["pr"]["merge_sha"] is not None, "payload/pr")
                    if terminal and terminal.get("pr") and p["pr"]:
                        stale(p["pr"]["url"] == terminal["pr"]["url"], "payload/pr/url")
                else:
                    illegal(not state["final_decision"], "payload/disposition")
                    if terminal:
                        illegal(terminal["disposition"] == "OPEN_SUCCESS_PR" and terminal["pr"] is None
                                and p["pr"] is not None, "payload/pr")
                    evidence(p["pr"] is None or p["pr"]["merge_sha"] is None, "payload/pr")
                    evidence(p["final_decision"] is None, "payload/final_decision")
            result["terminal"] = ref
    elif repair:
        if present:
            op = memory.get(p["original"])
            rejection = memory.get(p["rejection"])
            if op:
                opayload = payload(op)
                stale(op.get("task") == artifact["task"] and op.get("governor") == artifact["governor"]
                      and op.get("task_contract") == artifact["task_contract"], "payload/original")
                stale(artifact["consumer_role"] == op.get("producer_role"), "consumer_role")
                stale(artifact["visibility"] == op.get("visibility"), "visibility")
                if "lane" in opayload:
                    stale(p["lane"] == opayload["lane"], "payload/lane")
                source = commit(opayload.get("implementation_tip") or opayload.get("test_tip")
                                or opayload.get("candidate"))
                index = opayload.get("candidate_index")
                count = opayload.get("correction_count", opayload.get("implementation_index", 0))
                if op.get("artifact_kind") == "tester-confidential-report":
                    source = opayload.get("candidate_sha")
                    count = candidate.get("correction_count", count)
                    if candidate:
                        stale(source == commit(candidate["candidate"]) and
                              opayload.get("execution_id") == candidate["execution_id"], "payload/original")
                elif op.get("artifact_kind") == "reviewer-report":
                    source = commit(review.get("candidate")) or review.get("last_implementation")
                    index = candidate.get("candidate_index")
                    count = impl.get("implementation_index", 0)
                    if review:
                        stale(opayload.get("review_id") == review["review_id"], "payload/preserve_review_id")
                stale(p["preserve_tip"] == source, "payload/preserve_tip")
                stale(p["preserve_candidate_index"] == index and p["preserve_correction_count"] == count,
                      "payload/preserve_correction_count")
                stale(p["preserve_review_id"] == opayload.get("review_id"), "payload/preserve_review_id")
            if rejection:
                evidence(rejection.get("status") == "REJECTED" and
                    rejection.get("input") == {k: p["original"][k] for k in ("artifact_id", "path", "sha256")},
                    "payload/rejection")
            # Originals/rejections need not be accepted business events.
            evidence(p["original"] in artifact["predecessors"] and p["rejection"] in artifact["predecessors"],
                     "predecessors")
            result["repairs"].append(ref)
    return result
