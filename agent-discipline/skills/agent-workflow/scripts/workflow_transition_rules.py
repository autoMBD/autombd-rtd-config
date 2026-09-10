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
# Date:        2026-09-09
# Version:     0.2.0
# Description: Pure global lifecycle and identity rules for transitions.
# =================================================================================

import copy

import repair_protocol
from workflow_transition_wire import WorkflowTransitionError, require, validate

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


def repair_bodies(state, memory):
    """Only already consumed repairs establish attachment equivalence."""
    return [body for ref in state["repairs"] if (body := memory.get(ref))]


def latest_support(state, memory):
    return next((ref for ref in reversed(state["repairs"])
                 if repair_protocol.is_v1(memory.get(ref), "TEST_SUPPORT")), None)


def evidence_equivalent(old, new, state, memory):
    return repair_protocol.equivalent_evidence(old, new, repair_bodies(state, memory))


def test_source(test, support, memory):
    body = memory.get(support)
    return repair_protocol.effective_test(test, payload(body) if repair_protocol.is_v1(body, "TEST_SUPPORT") else None)


def validate_repair_evidence(artifact, memory, decision):
    """Share byte/projection rules with Guard, never substitute filesystem facts."""
    if not artifact:
        return
    try:
        repair_protocol.require_capability(memory.context["protocol"]["workflow_contract"], artifact)
        if repair_protocol.is_v1(artifact):
            defs = memory.context["protocol"]["handoff_schema"]["$defs"]

            def validate_after(body, name):
                validate(body, defs[name], defs, "INVALID_EVIDENCE", "/artifact/payload/attachment_changes")

            repair_protocol.validate_repair(artifact, memory.get, validate_after,
                workflow_version=memory.context["protocol"]["workflow_contract"]["contract_version"])
    except (repair_protocol.RepairError, WorkflowTransitionError):
        decision.check(False, "INVALID_EVIDENCE", "/artifact/payload/repair")


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
    lesson_mode = memory.context["protocol"]["workflow_contract"]["contract_version"] == 4
    publication_head = commit(reviewed.get("lesson_commit")) if lesson_mode else commit(candidate.get("candidate"))
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
    preserves_business = not replacement

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
        validate_repair_evidence(artifact, memory, decision)
        if repair_protocol.is_v1(artifact):
            contract = memory.p(state["contract"])
            if contract:
                evidence(set(p["semantic_audit"]["requirement_ids"]) <=
                         {item["id"] for item in contract["requirements"]}, "payload/semantic_audit/requirement_ids")
        if replacement:
            metadata_ref = replacement.get("repair")
            metadata = memory.get(metadata_ref)
            if metadata_ref:
                evidence(metadata_ref in state["repairs"], "replaces/repair")
                evidence(repair_protocol.is_v1(metadata, "METADATA"), "replaces/repair")
                if metadata:
                    validate_repair_evidence(metadata, memory, decision)
                    rp = payload(metadata)
                    stale(rp.get("original") == replacement["original"], "replaces/original")
                    if "dispatch_id" in p:
                        stale(rp.get("dispatch_id") == p.get("dispatch_id"), "payload/dispatch_id")
                    evidence(rp.get("replacement_output") == ref["path"] and
                             ref["path"] != replacement["original"]["path"], "replaces/repair")
                    evidence(metadata.get("consumer_role") == artifact["producer_role"], "producer_role")
                    repaired_dispatch = rp.get("dispatch_id") == p.get("dispatch_id")
                direct(metadata_ref)
                direct(replacement["original"])
            if original:
                stale(original.get("task") == artifact["task"] and
                      original.get("governor") == artifact["governor"] and
                      original.get("task_contract") == artifact["task_contract"],
                      "replaces/original")
                evidence(original.get("artifact_kind") == kind and
                         original.get("artifact_id") != artifact["artifact_id"], "replaces/original")
                try:
                    repair_protocol.validate_metadata_replacement(original, artifact, metadata)
                    preserves_business = True
                except repair_protocol.RepairError as error:
                    # Keep the published legacy diagnostic pointer while the
                    # shared helper remains the sole preservation authority.
                    changed = next((field for field in repair_protocol.PRESERVED
                        if p.get(field) != original_payload.get(field)), None)
                    field = ("payload/" + changed if changed and error.rule == "REPAIR_BUSINESS_CHANGE"
                             else "replaces/original")
                    evidence(False, field)
                    preserves_business = False
                if p.get("dispatch_id") != original_payload.get("dispatch_id"):
                    repairs = [memory.p(x) for x in state["repairs"]
                               if memory.p(x).get("original") == replacement["original"]]
                    match = next((r for r in repairs if r.get("dispatch_id") == p.get("dispatch_id")), None)
                    evidence(match is not None, "payload/dispatch_id")
                    repaired_dispatch = match is not None
            rejection = memory.get(replacement.get("guard_result"))
            if rejection:
                evidence(rejection.get("status") == "REJECTED" and
                    rejection.get("input") == {k: replacement["original"][k]
                                              for k in ("artifact_id", "path", "sha256")}, "replaces/guard_result")
            direct(replacement["original"]) if not accepted_replacement else None
            direct(replacement.get("guard_result"))

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
    if repair_protocol.is_v1(artifact, "TEST_SUPPORT"):
        illegal(not (state["stop"] or state["review"] or state["terminal"]))
        illegal(outcome not in ("PASS", "TEST_GATE_INVALID", "CONTRACT_INVALID", "INTEGRITY_INVALID")
                and not (outcome == "IMPLEMENTATION_FAIL" and candidate.get("candidate_index") == 3))

    # Logical repair does not replay READY, correction, execution or review.
    if accepted_replacement:
        # The accepted original established these identities independently of
        # whether the replacement preserves its other business values.
        for field in ("lane", "execution_id", "review_id"):
            if field in original_payload:
                stale(p.get(field) == original_payload[field], "payload/" + field)
        if "dispatch_id" in original_payload:
            stale(p.get("dispatch_id") == original_payload["dispatch_id"] or repaired_dispatch,
                  "payload/dispatch_id")
        if kind == "human-decision":
            # Bind the original active decision, not a gate supplied by its
            # replacement. Historical REQUEST_CHANGES has no active subject.
            if (original_payload.get("gate") == "TEST" and
                    replacement["original"] == state["test"]["approval"] and test):
                stale(p.get("subject_sha") == commit(test["test_tip"]), "payload/subject_sha")
            elif (original_payload.get("gate") == "FINAL" and
                    replacement["original"] in (state["stop"], state["final_decision"]) and
                    (candidate or state["candidate"] is None)):
                expected = (commit(candidate.get("candidate")) if replacement["original"] == state["stop"]
                            else publication_head)
                stale(p.get("subject_sha") == expected, "payload/subject_sha")
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
            if lane == "worker" and pending and launch and preserves_business:
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
                    elif pending and preserves_business:
                        if launch:
                            stale(p["implementation_index"] == launch["correction_index"], "payload/implementation_index")
                            stale(p["previous_implementation"] == launch["previous_implementation"], "payload/previous_implementation")
                        if impl:
                            stale(p["implementation_index"] == impl["implementation_index"] + 1 and
                                  p["previous_implementation"] == commit(impl["implementation_tip"]),
                                  "payload/previous_implementation")
                        result["worker"]["pending_correction"] = None
                    elif preserves_business and not state["candidate"] and not (
                            state["stop"] or state["review"] or state["terminal"]):
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
                    order(ready_body["task_contract"] == current_k)
                direct(state["test"]["ready"])
                if p["decision"] == "APPROVE":
                    result["test"]["approval"] = ref
                elif p["decision"] == "REQUEST_CHANGES":
                    result["test"]["ready"] = None
            else:
                expected = commit(candidate.get("candidate")) if stop else publication_head
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
        next_implementation = bool(candidate and impl and
            impl["implementation_index"] == candidate["candidate_index"] + 1 and
            not state["worker"]["pending_correction"])
        if present:
            support_ref = p.get("support_repair")
            support = memory.get(support_ref)
            known_support = repair_protocol.is_v1(support, "TEST_SUPPORT")
            if support_ref:
                evidence(known_support and support_ref in state["repairs"], "payload/support_repair")
                if known_support:
                    stale(support_ref == latest_support(state, memory), "payload/support_repair")
                    direct(support_ref)
            else:
                stale(latest_support(state, memory) is None, "payload/support_repair")
            executable_test = test_source(test, support_ref, memory)
            for needed in (state["test"]["approval"], state["test"]["ready"], state["worker"]["ready"]):
                if needed:
                    order(any(equivalent_ref(predecessor, needed, memory)
                              for predecessor in artifact["predecessors"]), "predecessors")
            for report_ref in (state["test"]["ready"], state["worker"]["ready"]):
                report = memory.get(report_ref)
                if report:
                    order(report["task_contract"] == current_k)
            if test:
                stale(p["test_tip"] == executable_test["test_tip"], "payload/test_tip")
                for key in ("test_manifest", "impact_set"):
                    stale(evidence_equivalent(p[key], executable_test[key], state, memory), "payload/" + key)
            if impl:
                stale(p["implementation_tip"] == impl["implementation_tip"], "payload/implementation_tip")
                stale(evidence_equivalent(p["implementation_manifest"], impl["manifest"], state, memory),
                      "payload/implementation_manifest")
                if preserves_business and (not state["candidate"] or p["rerun_of"] or next_implementation):
                    stale(p["candidate_index"] == impl["implementation_index"], "payload/candidate_index")
            if preserves_business:
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
                    source_repair = bool(known_support and support_ref != candidate.get("support_repair"))
                    if source_repair:
                        stale(p["previous_candidate"] == state["candidate"]["envelope"], "payload/previous_candidate")
                        stale(p["test_tip"] != candidate["test_tip"] and
                              commit(p["candidate"]) != commit(candidate["candidate"]), "payload/candidate")
                        unchanged = ("implementation_tip", "implementation_manifest", "candidate_index", "correction_count")
                    else:
                        unchanged = ("candidate", "test_tip", "implementation_tip", "test_manifest",
                                     "implementation_manifest", "impact_set", "coverage_join",
                                     "candidate_index", "correction_count", "previous_candidate")
                    for key in unchanged:
                        stale(p[key] == candidate[key], "payload/" + key)
            elif state["candidate"]:
                order(state["candidate"]["result"] is not None)
                if tester:
                    illegal(outcome == "IMPLEMENTATION_FAIL", "payload/candidate_index")
                if candidate and impl:
                    illegal(next_implementation, "payload/candidate_index")
                if next_implementation and preserves_business:
                    stale(p["candidate_index"] == candidate["candidate_index"] + 1, "payload/candidate_index")
                    stale(p["previous_candidate"] == state["candidate"]["envelope"], "payload/previous_candidate")
                    direct(state["candidate"]["envelope"])
            else:
                if preserves_business:
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
            try:
                repair_protocol.validate_retest_evidence(artifact,
                    memory.get(state["candidate"]["envelope"]),
                    history_bodies(state, memory, "tester-confidential-report"), memory.get)
            except repair_protocol.RepairError:
                evidence(False, "payload/execution")
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
                  "CORRECTIONS_EXHAUSTED" if outcome == "IMPLEMENTATION_FAIL" and
                  candidate.get("candidate_index") == 3 else outcome if outcome in
                  ("TEST_GATE_INVALID", "CONTRACT_INVALID", "INTEGRITY_INVALID") else None)
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
            if lesson_mode:
                tip = p.get("lesson_commit")
                reviewed_candidate = review.get("candidate")
                if reviewed_candidate is None:
                    evidence(tip is None, "payload/lesson_commit")
                else:
                    evidence(tip is not None, "payload/lesson_commit")
                    if tip:
                        stale(tip["parents"] == [commit(reviewed_candidate)] and
                              tip["commit"] != commit(reviewed_candidate), "payload/lesson_commit")
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
                    stale(p["pr"]["head_sha"] == publication_head, "payload/pr/head_sha")
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
            if repair_protocol.is_v1(artifact, "TEST_SUPPORT"):
                previous = latest_support(state, memory)
                prior = test_source(test, previous, memory)
                order(state["test"]["ready"] is not None and state["test"]["approval"] is not None)
                stale(equivalent_ref(p["approved_test_report"], state["test"]["ready"], memory),
                      "payload/approved_test_report")
                stale(equivalent_ref(p["approval"], state["test"]["approval"], memory), "payload/approval")
                stale(p["previous_support_repair"] == previous, "payload/previous_support_repair")
                if test:
                    stale(p["lane"] == test["lane"], "payload/lane")
                    stale(p["from_test_tip"] == prior["test_tip"], "payload/from_test_tip")
                # The real Guard proves strict Git ancestry; a source repair
                # may contain multiple commits. Memory cannot invent that proof.
                evidence(commit(p["to_test_tip"]) != commit(p["from_test_tip"]), "payload/to_test_tip")
                stale(p["implementation_report"] == state["worker"]["ready"], "payload/implementation_report")
                stale(p["previous_candidate"] == (state["candidate"]["envelope"] if state["candidate"] else None),
                      "payload/previous_candidate")
                stale(p["candidate_index"] == candidate.get("candidate_index"), "payload/candidate_index")
                stale(p["correction_count"] == impl.get("implementation_index", 0), "payload/correction_count")
                for needed in (p["approved_test_report"], p["approval"], previous,
                               p["previous_candidate"], p["implementation_report"]):
                    direct(needed)
                for old in history_bodies(state, memory, "delivery-repair"):
                    stale(p["dispatch_id"] != payload(old).get("dispatch_id"), "payload/dispatch_id")
                result["repairs"].append(ref)
                return result
            op = memory.get(p["original"])
            rejection_ref = p.get("rejection")
            rejection = memory.get(rejection_ref)
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
            if not repair_protocol.is_v1(artifact):
                evidence(p["original"] in artifact["predecessors"] and rejection_ref in artifact["predecessors"],
                         "predecessors")
            result["repairs"].append(ref)
    return result
