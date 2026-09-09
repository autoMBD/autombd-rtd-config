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
# File:        test_handoff_repair_reducer.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Owned synthetic reducer repair histories; no real Guard claims.
# =================================================================================

import copy
import importlib
import sys
import json
import hashlib

import pytest

from workflow_transition_generality_support import History, SCRIPTS, digest

sys.path.insert(0, str(SCRIPTS))
api = importlib.import_module("workflow_transition")


def snapshot(h, label, body, kind):
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
    ref = {"path": f".agent-state/{h.seed}/{label}.json", "evidence_type": kind,
           "sha256": hashlib.sha256(raw.encode()).hexdigest()}
    h.attachments[ref["path"]] = body
    return {"ref": ref, "raw": raw}


def manifest(h, tip):
    return {"contract_version": 3, "contract_blob_sha": h.governor["workflow_contract_blob"],
            "base_sha": h.governor["commit"], "lane_sha": tip["commit"], "requirement_ids": [h.seed]}


class RepairHistory(History):
    def __init__(self, module, seed):
        super().__init__(module, seed)
        self.attachments = {}

    def ready(self, lane, index=0, previous=None):
        if lane != "test":
            launch = self.state["worker"]["pending_correction"] or self.refs["worker-launch"]
            lp = self.body(launch)["payload"]
            ref = self.make("implementation-report", {"status": "READY", "revision_ack": None,
                "lane": lp["lane"], "dispatch_id": lp["dispatch_id"], "implementation_index": index,
                "previous_implementation": previous,
                "implementation_tip": self.tip(f"worker-{index}-{self.serial}", [previous] if previous else None),
                "manifest": self.evidence(f"worker-manifest-{self.serial}"),
                "changed_paths": [{"path": "src/worker.py", "requirement_ids": [self.seed],
                                   "rationale": "Worker-owned public implementation"}]}, [launch])
            self.refs["worker-ready"] = self.consume(ref)
            return ref
        launch = self.refs["test-launch"]
        tip = self.tip("original-test")
        m = snapshot(self, "manifest-original", manifest(self, tip), "manifest")
        impact = {"schema_version": "1.0", "task": self.task, "task_contract": self.kref(),
            "selected_checks": [{"id": "CHECK", "family": "unit", "argv": ["python", "tests/check.py"],
                "requirement_ids": [self.seed], "covered_paths": ["tests/check.py", "tests/adapter.py", "src/worker.py"]}],
            "excluded_checks": [], "public_dependency_edges": [],
            "prevalidation_obligations": [{"id": "PRE", "mode": "FULL_CHAIN", "reason": None}]}
        i = snapshot(self, "impact-original", impact, "impact-set")
        ref = self.make("test-gate-report", {"status": "READY", "revision_ack": None,
            "lane": self.body(launch)["payload"]["lane"], "test_tip": tip,
            "manifest": m["ref"], "impact_set": i["ref"],
            "dispatch_id": self.body(launch)["payload"]["dispatch_id"]}, [launch])
        self.refs["test-ready"] = self.consume(ref)
        return ref


def ready_history(seed="willow"):
    h = RepairHistory(api, seed)
    h.start()
    for lane in ("test", "worker"):
        h.launch(lane)
        h.ready(lane)
    h.approve()
    return h


def audit(h, facts, affected=()):
    return {"requirement_ids": [h.seed], "source_bindings": facts,
        "dimensions": [{"dimension": field, "before": "The same check source and assertions",
            "after": "The same check source and assertions", "explanation": "Only adapter transport changed"}
            for field in ("scenarios", "conditions", "assertions", "expected_results", "pass_fail_criteria",
                          "selected_checks", "exclusions", "coverage")],
        "affected_check_ids": list(affected), "reviewer_role": "orchestrator", "reviewer_id": "reviewer"}


def support_artifact(h, previous=None):
    import repair_protocol
    test = h.body(h.state["test"]["ready"])["payload"]
    old = h.body(previous)["payload"] if previous else None
    start = old["to_test_tip"] if old else test["test_tip"]
    target = h.tip(f"supported-{h.serial}", [start["commit"]])
    old_manifest = old["test_manifest"] if old else test["manifest"]
    old_impact = old["impact_set"] if old else test["impact_set"]
    old_blob = old["source_changes"][0]["after_blob"] if old else h.sha("adapter-before")
    new_blob = h.sha(f"adapter-after-{h.serial}")
    facts = [{"commit": tip["commit"], "path": path, "blob": blob}
        for tip, path, blob in ((start, "tests/adapter.py", old_blob), (target, "tests/adapter.py", new_blob),
            (start, "tests/check.py", h.sha("case")), (target, "tests/check.py", h.sha("case")))]
    mappings = []
    for field, before_ref, after_body, kind in (
            ("test_manifest", old_manifest, manifest(h, target), "manifest"),
            ("impact_set", old_impact, h.attachments[old_impact["path"]], "impact-set")):
        before_body = h.attachments[before_ref["path"]]
        before_raw = json.dumps(before_body, sort_keys=True, separators=(",", ":")) + "\n"
        after = snapshot(h, f"{field}-{h.serial}", after_body, kind)
        mappings.append({"field": field, "before": {"ref": before_ref, "raw": before_raw}, "after": after,
            "changed_fields": repair_protocol.changed_fields(before_body, after_body), "source_facts": facts,
            "reason": "Bind incremental transport source with unchanged cases", "dependency_audit": []})
    original = h.state["test"]["ready"]
    checked = h.event(original)["checked"]
    current = h.state["candidate"]
    impl = (h.body(h.state["worker"]["ready"]) or {}).get("payload", {})
    p = {"repair_version": "1.0", "mode": "TEST_SUPPORT", "dispatch_id": f"support-{h.serial}",
         "original": original, "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": checked,
             "observation": "The supporting adapter needs a mechanical correction"},
         "lane": test["lane"], "replacement_output": f".agent-state/{h.seed}/support-{h.serial}.json",
         "reason": "Preserve approved assertions while correcting adapter source", "attachment_changes": mappings,
         "semantic_audit": audit(h, facts, ["CHECK"]), "approval": h.state["test"]["approval"],
         "approved_test_report": original, "previous_support_repair": previous,
         "previous_candidate": current["envelope"] if current else None,
         "from_test_tip": start, "to_test_tip": target, "implementation_report": h.state["worker"]["ready"],
         "candidate_index": h.body(current["envelope"])["payload"]["candidate_index"] if current else None,
         "correction_count": impl.get("implementation_index", 0),
         "test_manifest": mappings[0]["after"]["ref"], "impact_set": mappings[1]["after"]["ref"],
         "source_changes": [{"path": "tests/adapter.py", "before_blob": old_blob, "after_blob": new_blob,
                             "reason": "Mechanical loader change; frozen assertions unchanged"}],
         "retest_check_ids": ["CHECK"]}
    predecessors = [original, checked, h.state["test"]["approval"]]
    predecessors += [h.state["worker"]["ready"]] if h.state["worker"]["ready"] else []
    predecessors += [previous] if previous else []
    predecessors += [current["envelope"]] if current else []
    ref = h.make("delivery-repair", predecessors=predecessors,
                 consumer_role="tester", visibility="tester-confidential")
    h.body(ref)["payload"] = p
    ref["sha256"] = digest(h.body(ref))
    return ref


def metadata_artifact(h, original, attachment=None):
    import repair_protocol
    op = h.body(original)["payload"]
    tp = h.body(h.state["test"]["ready"])["payload"]
    facts = [{"commit": tp["test_tip"]["commit"], "path": "tests/check.py", "blob": h.sha("case")}]
    mappings = []
    if attachment:
        before_ref = op[attachment]
        body = copy.deepcopy(h.attachments[before_ref["path"]])
        body["prevalidation_obligations"][0]["reason"] = "This is the actual full-chain obligation"
        after = snapshot(h, f"metadata-{h.serial}", body, "impact-set")
        before_body = h.attachments[before_ref["path"]]
        mappings.append({"field": attachment, "before": {"ref": before_ref,
            "raw": json.dumps(before_body, sort_keys=True, separators=(",", ":")) + "\n"}, "after": after,
            "changed_fields": repair_protocol.changed_fields(before_body, body), "source_facts": facts,
            "reason": "Correct description only", "dependency_audit": []})
    trigger = h.event(original)["checked"]
    p = {"repair_version": "1.0", "mode": "METADATA", "dispatch_id": f"metadata-{h.serial}",
        "original": original, "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": trigger,
            "observation": "Observed inaccurate delivery metadata"}, "lane": op.get("lane", tp["lane"]),
        "replacement_output": f".agent-state/{h.seed}/replacement-{h.serial}.json",
        "reason": "Repair original delivery metadata without a new business event",
        "attachment_changes": mappings, "semantic_audit": audit(h, facts),
        "preserve_tip": (op.get("test_tip") or op.get("implementation_tip") or {}).get("commit"),
        "preserve_candidate_index": op.get("candidate_index"), "preserve_correction_count": 0,
        "preserve_review_id": op.get("review_id")}
    ref = h.make("delivery-repair", predecessors=[original, trigger],
        consumer_role=h.body(original)["producer_role"], visibility=h.body(original)["visibility"])
    h.body(ref)["payload"] = p
    ref["sha256"] = digest(h.body(ref))
    return ref


def metadata_replacement(h, repair):
    rp = h.body(repair)["payload"]
    body = copy.deepcopy(h.body(rp["original"]))
    body["artifact_id"] = f"replacement-{h.serial}"
    body["replaces"] = {"original": rp["original"], "repair": repair}
    body["predecessors"] += [rp["original"], repair]
    if "dispatch_id" in body["payload"]:
        body["payload"]["dispatch_id"] = rp["dispatch_id"]
    for mapping in rp["attachment_changes"]:
        body["payload"][mapping["field"]] = mapping["after"]["ref"]
    ref = h.register(body)
    ref["path"] = rp["replacement_output"]
    return ref


def candidate_artifact(h, support=None, rerun=False):
    test = h.body(h.state["test"]["ready"])["payload"]
    impl = h.body(h.state["worker"]["ready"])["payload"]
    source = h.body(support)["payload"] if support else None
    tip = source["to_test_tip"] if source else test["test_tip"]
    manifest = source["test_manifest"] if source else test["manifest"]
    impact = source["impact_set"] if source else test["impact_set"]
    old = h.state["candidate"]
    predecessors = [h.state["test"]["ready"], h.state["test"]["approval"], h.state["worker"]["ready"]]
    p = {"dispatch_id": f"dispatch-{h.serial}", "execution_id": f"execution-{h.serial}",
         "candidate_index": impl["implementation_index"], "correction_count": impl["implementation_index"],
         "test_tip": tip, "test_manifest": manifest, "impact_set": impact,
         "implementation_tip": impl["implementation_tip"], "implementation_manifest": impl["manifest"],
         "candidate": h.tip(f"candidate-{h.serial}", [tip["commit"], impl["implementation_tip"]["commit"]]),
         "coverage_join": h.evidence(f"join-{h.serial}", "coverage-join"),
         "previous_candidate": old["envelope"] if old else None,
         "rerun_of": old["result"] if rerun else None}
    if support:
        p["support_repair"] = support
        predecessors.append(support)
    if old:
        predecessors.append(old["envelope"])
        if rerun:
            predecessors.append(old["result"])
    return h.make("candidate-test-envelope", p, predecessors)


def reject(h, ref, code):
    before = copy.deepcopy(h.state)
    with pytest.raises(api.WorkflowTransitionError) as caught:
        h.consume(ref)
    assert caught.value.code == code
    assert h.state == before


def test_w2_rejects_explicit_support_even_with_upgraded_schema():
    h = ready_history()
    w = h.context["protocol"]["workflow_contract"]
    w["contract_version"] = 2
    w.pop("non_case_repairs")
    ref = candidate_artifact(h)
    h.body(ref)["payload"]["support_repair"] = h.contract
    ref["sha256"] = digest(h.body(ref))
    reject(h, ref, "INVALID_EVIDENCE")


def test_w3_rejects_non_support_artifact_as_explicit_support():
    h = ready_history("birch")
    ref = candidate_artifact(h)
    h.body(ref)["payload"]["support_repair"] = h.contract
    ref["sha256"] = digest(h.body(ref))
    reject(h, ref, "INVALID_EVIDENCE")


def test_support_before_c0_keeps_original_ready_and_approval():
    h = ready_history()
    before = copy.deepcopy(h.state)
    repair = h.consume(support_artifact(h))
    assert h.state["test"] == before["test"]
    assert h.state["worker"] == before["worker"]
    assert h.state["candidate"] is None
    assert h.state["repairs"] == [repair]
    candidate = h.consume(candidate_artifact(h, repair))
    assert h.state["candidate"]["envelope"] == candidate
    assert h.state["test"]["approval"] == before["test"]["approval"]


def test_repeated_repairs_after_invalid_run_keep_old_candidate_until_fresh_execution():
    h = ready_history()
    first = h.consume(support_artifact(h))
    old = h.consume(candidate_artifact(h, first))
    result = h.result("INVALID_RUN")
    second = h.consume(support_artifact(h, first))
    assert h.state["candidate"] == {"envelope": old, "result": result}
    third = h.consume(support_artifact(h, second))
    fresh = h.consume(candidate_artifact(h, third, rerun=True))
    assert h.body(fresh)["payload"]["candidate_index"] == 0
    assert h.body(fresh)["payload"]["candidate"] != h.body(old)["payload"]["candidate"]


def test_support_never_erases_valid_failure_or_pending_worker_correction():
    h = ready_history()
    h.consume(candidate_artifact(h))
    failure = h.result("IMPLEMENTATION_FAIL")
    pending = h.correction()
    repair = h.consume(support_artifact(h))
    assert h.state["candidate"]["result"] == failure
    assert h.state["worker"]["pending_correction"] == pending
    reject(h, candidate_artifact(h, repair), "ILLEGAL_TRANSITION")
    previous = h.body(h.state["worker"]["ready"])["payload"]["implementation_tip"]["commit"]
    h.ready("worker", 1, previous)
    candidate = h.consume(candidate_artifact(h, repair))
    assert h.body(candidate)["payload"]["candidate_index"] == 1


@pytest.mark.parametrize("outcome", ["PASS", "TEST_GATE_INVALID", "CONTRACT_INVALID", "INTEGRITY_INVALID"])
def test_support_refuses_terminal_result(outcome):
    h = ready_history()
    h.consume(candidate_artifact(h))
    h.result(outcome)
    reject(h, support_artifact(h), "ILLEGAL_TRANSITION")


def test_support_rejects_stale_lineage():
    h = ready_history()
    h.consume(support_artifact(h))
    reject(h, support_artifact(h), "STALE_EVENT")


def test_reducer_does_not_invent_direct_parent_ancestry_requirement():
    h = ready_history()
    repair = support_artifact(h)
    h.body(repair)["payload"]["to_test_tip"]["parents"] = [h.sha("intermediate-support-commit")]
    repair["sha256"] = digest(h.body(repair))
    h.consume(repair)


def test_metadata_replacement_updates_attachment_not_candidate_or_approval():
    h = ready_history()
    h.consume(candidate_artifact(h))
    before = copy.deepcopy(h.state)
    repair = h.consume(metadata_artifact(h, h.state["test"]["ready"], "impact_set"))
    replacement = h.consume(metadata_replacement(h, repair))
    assert h.state["test"]["ready"] == replacement
    assert h.state["test"]["approval"] == before["test"]["approval"]
    assert h.state["candidate"] == before["candidate"]
    h.result("INVALID_RUN")
    # New executable Candidate still anchors its historical source and metadata.
    h.candidate(rerun=True)


def test_metadata_human_approval_reissue_preserves_vote():
    h = ready_history()
    repair = h.consume(metadata_artifact(h, h.state["test"]["approval"]))
    replacement = metadata_replacement(h, repair)
    h.consume(replacement)
    assert h.state["test"]["approval"] == replacement
    assert h.body(replacement)["payload"]["decision"] == "APPROVE"


@pytest.mark.parametrize("field,value,code", [
    ("decision", "REQUEST_CHANGES", "INVALID_EVIDENCE"),
    ("gate", "FINAL", "INVALID_EVIDENCE"),
    ("subject_sha", "f" * 40, "STALE_EVENT")])
def test_metadata_cannot_change_human_business_fields(field, value, code):
    h = ready_history()
    repair = h.consume(metadata_artifact(h, h.state["test"]["approval"]))
    replacement = metadata_replacement(h, repair)
    h.body(replacement)["payload"][field] = value
    replacement["sha256"] = digest(h.body(replacement))
    reject(h, replacement, code)


def test_support_semantic_audit_cannot_invent_requirement():
    h = ready_history()
    repair = support_artifact(h)
    h.body(repair)["payload"]["semantic_audit"]["requirement_ids"] = ["UNKNOWN"]
    repair["sha256"] = digest(h.body(repair))
    reject(h, repair, "INVALID_EVIDENCE")


@pytest.mark.parametrize("mutation", ["blob", "raw", "argv", "unknown-check", "audit", "approval", "lane"])
def test_support_rejects_forged_or_changed_evidence(mutation):
    h = ready_history()
    repair = support_artifact(h)
    p = h.body(repair)["payload"]
    code = "INVALID_EVIDENCE"
    if mutation == "blob":
        p["source_changes"][0]["after_blob"] = "f" * 40
    elif mutation == "raw":
        p["attachment_changes"][0]["after"]["raw"] += " "
    elif mutation == "argv":
        import repair_protocol
        change = p["attachment_changes"][1]
        after = json.loads(change["after"]["raw"])
        after["selected_checks"][0]["argv"] = ["python", "wrong.py"]
        change["after"] = snapshot(h, "forged-selection", after, "impact-set")
        change["changed_fields"] = repair_protocol.changed_fields(json.loads(change["before"]["raw"]), after)
        p["impact_set"] = change["after"]["ref"]
    elif mutation == "unknown-check":
        p["retest_check_ids"] = p["semantic_audit"]["affected_check_ids"] = ["UNKNOWN"]
    elif mutation == "audit":
        p["semantic_audit"]["dimensions"].pop()
    elif mutation == "approval":
        p["approval"] = h.state["worker"]["ready"]
        code = "STALE_EVENT"
    else:
        p["lane"] = h.body(h.state["worker"]["ready"])["payload"]["lane"]
        code = "STALE_EVENT"
    repair["sha256"] = digest(h.body(repair))
    reject(h, repair, code)


def test_support_registration_can_precede_worker_ready():
    h = RepairHistory(api, "before-worker")
    h.start()
    h.launch("test")
    h.ready("test")
    h.approve()
    repair = h.consume(support_artifact(h))
    assert h.state["worker"]["ready"] is None
    h.launch("worker")
    h.ready("worker")
    h.consume(candidate_artifact(h, repair))


@pytest.mark.parametrize("binding", ["stale", "absent"])
def test_candidate_requires_latest_consumed_support(binding):
    h = ready_history()
    first = h.consume(support_artifact(h))
    h.consume(support_artifact(h, first))
    reject(h, candidate_artifact(h, first if binding == "stale" else None), "STALE_EVENT")


def test_candidate_rejects_unconsumed_support():
    h = ready_history()
    pending = support_artifact(h)
    reject(h, candidate_artifact(h, pending), "STALE_EVENT")


def test_same_source_invalid_run_keeps_supported_candidate_exactly():
    h = ready_history()
    repair = h.consume(support_artifact(h))
    old = h.consume(candidate_artifact(h, repair))
    h.result("INVALID_RUN")
    rerun = candidate_artifact(h, repair, rerun=True)
    h.body(rerun)["payload"].update({key: value for key, value in h.body(old)["payload"].items()
        if key not in ("dispatch_id", "execution_id", "rerun_of")})
    rerun["sha256"] = digest(h.body(rerun))
    h.consume(rerun)
    assert h.body(rerun)["payload"]["candidate"] == h.body(old)["payload"]["candidate"]
    assert h.body(rerun)["payload"]["support_repair"] == repair


def test_same_index_source_repair_cannot_hide_valid_failure_without_pending_envelope():
    h = ready_history()
    h.consume(candidate_artifact(h))
    h.result("IMPLEMENTATION_FAIL")
    repair = h.consume(support_artifact(h))
    reject(h, candidate_artifact(h, repair), "ILLEGAL_TRANSITION")


def test_source_repair_requires_fresh_execution_identity():
    h = ready_history()
    old = h.consume(candidate_artifact(h))
    h.result("INVALID_RUN")
    repair = h.consume(support_artifact(h))
    candidate = candidate_artifact(h, repair, rerun=True)
    h.body(candidate)["payload"]["execution_id"] = h.body(old)["payload"]["execution_id"]
    candidate["sha256"] = digest(h.body(candidate))
    reject(h, candidate, "STALE_EVENT")


def test_w2_rejects_support_repair_registration():
    h = ready_history()
    repair = support_artifact(h)
    w = h.context["protocol"]["workflow_contract"]
    w["contract_version"] = 2
    w.pop("non_case_repairs")
    reject(h, repair, "INVALID_EVIDENCE")


def test_w2_rejects_new_repair_in_replayed_history():
    h = ready_history()
    h.consume(support_artifact(h))
    w = h.context["protocol"]["workflow_contract"]
    w["contract_version"] = 2
    w.pop("non_case_repairs")
    reject(h, candidate_artifact(h), "INVALID_STATE")


def test_metadata_replacement_requires_consumed_repair():
    h = ready_history()
    repair = metadata_artifact(h, h.state["test"]["approval"])
    reject(h, metadata_replacement(h, repair), "INVALID_EVIDENCE")


def test_historical_support_trigger_digest_is_not_trusted_by_id_alone():
    h = ready_history()
    repair = h.consume(support_artifact(h))
    trigger = h.body(repair)["payload"]["trigger"]["checked"]
    entry = next(item for item in h.context["checks"] if item["ref"] == trigger)
    entry["body"]["operation_id"] = "forged-different-raw-receipt"
    reject(h, candidate_artifact(h, repair), "INVALID_EVIDENCE")


def test_support_source_changes_cannot_touch_declared_worker_paths():
    h = ready_history()
    repair = support_artifact(h)
    p = h.body(repair)["payload"]
    p["source_changes"][0]["path"] = "src/worker.py"
    for fact in p["semantic_audit"]["source_bindings"]:
        if fact["path"] == "tests/adapter.py":
            fact["path"] = "src/worker.py"
    repair["sha256"] = digest(h.body(repair))
    reject(h, repair, "INVALID_EVIDENCE")


def test_observed_checked_original_does_not_gain_rejected_raw_exception():
    h = ready_history()
    repair = support_artifact(h)
    original = h.body(repair)["payload"]["original"]
    entry = next(item for item in h.context["artifacts"] if item["ref"] == original)
    from workflow_transition_generality_support import canonical
    entry["raw"] = canonical(entry["body"]).decode()
    reject(h, repair, "INVALID_EVIDENCE")


def executed_report(h, outcome, result_ref):
    envelope = h.state["candidate"]["envelope"]
    cp = h.body(envelope)["payload"]
    run = h.defaults(h.schema["$defs"]["RunEvidence"])
    run.update(purpose="CHECK", argv=["python", "tests/check.py"], exit_code=0,
               outcome="PASS", result=result_ref)
    return h.make("tester-confidential-report", {"dispatch_id": cp["dispatch_id"],
        "candidate_index": cp["candidate_index"], "candidate_sha": cp["candidate"]["commit"],
        "execution_id": cp["execution_id"], "outcome": outcome, "execution": [run]}, [envelope])


@pytest.mark.parametrize("reuse", [True, False])
def test_support_retest_requires_fresh_result_identity_not_different_result_bytes(reuse):
    h = ready_history()
    h.consume(candidate_artifact(h))
    old_result = h.evidence("old-check-result", "command-result")
    h.consume(executed_report(h, "INVALID_RUN", old_result))
    repair = h.consume(support_artifact(h))
    h.consume(candidate_artifact(h, repair, rerun=True))
    fresh_result = copy.deepcopy(old_result)
    if not reuse:
        fresh_result["path"] = f".agent-state/{h.seed}/fresh-same-result.json"
    report = executed_report(h, "PASS", fresh_result)
    if reuse:
        reject(h, report, "INVALID_EVIDENCE")
    else:
        h.consume(report)
