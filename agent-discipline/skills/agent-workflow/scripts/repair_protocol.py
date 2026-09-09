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
# File:        repair_protocol.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Shared pure preservation and inline repair evidence rules.
# =================================================================================

import hashlib
import json


CAPABILITY = {"version": "1.0", "metadata": True, "test_support": True}
ATTACHMENTS = {"manifest": "LaneManifestV1", "test_manifest": "LaneManifestV1",
    "implementation_manifest": "LaneManifestV1", "impact_set": "ImpactSet", "coverage_join": "CoverageJoin"}
PRESERVED = ("status", "outcome", "verdict", "implementation_index", "implementation_tip",
    "previous_implementation", "test_tip", "candidate", "candidate_index", "candidate_sha",
    "correction_count", "review_id", "lane", "result", "accepted_candidate",
    "preserved_implementation", "impact_set", "manifest", "test_manifest",
    "implementation_manifest", "execution_id", "coverage_join", "rerun_of",
    "previous_candidate", "terminal_reason", "last_implementation", "source_reports",
    "disposition", "pr", "final_decision", "revision_ack", "gate", "decision", "subject_sha",
    "support_repair")
DIMENSIONS = {"scenarios", "conditions", "assertions", "expected_results", "pass_fail_criteria",
              "selected_checks", "exclusions", "coverage"}


class RepairError(ValueError):
    """Safe shared failure, translated at each public validation boundary."""

    def __init__(self, rule):
        self.rule = rule
        super().__init__(rule)


def _require(condition, rule):
    if not condition:
        raise RepairError(rule)


def is_v1(artifact, mode=None):
    p = artifact.get("payload", {}) if artifact else {}
    return bool(artifact and artifact.get("artifact_kind") == "delivery-repair" and
                p.get("repair_version") == "1.0" and (mode is None or p.get("mode") == mode))


def require_capability(workflow, artifact):
    p = artifact.get("payload", {})
    extension = "repair_version" in p or "support_repair" in p or "repair" in (artifact.get("replaces") or {})
    if extension:
        _require(type(workflow.get("schema_version")) is int and workflow["schema_version"] == 2 and
                 type(workflow.get("contract_version")) is int and workflow["contract_version"] == 3 and
                 workflow.get("non_case_repairs") == CAPABILITY and
                 all(type(workflow["non_case_repairs"].get(k)) is type(v) for k, v in CAPABILITY.items()),
                 "REPAIR_CAPABILITY")


def validate_snapshot(snapshot):
    _require(type(snapshot) is dict and set(snapshot) == {"ref", "raw"}, "REPAIR_SNAPSHOT")

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "REPAIR_JSON")
            result[key] = value
        return result

    def forbidden(_):
        raise RepairError("REPAIR_JSON")

    try:
        raw = snapshot["raw"].encode("utf-8")
        _require(not raw.startswith(b"\xef\xbb\xbf") and hashlib.sha256(raw).hexdigest() ==
                 snapshot["ref"]["sha256"], "REPAIR_SNAPSHOT_DIGEST")
        body = json.loads(raw, object_pairs_hook=pairs, parse_float=forbidden, parse_constant=forbidden)
        _require(type(body) is dict, "REPAIR_JSON")
        # Re-encoding also rejects isolated surrogate code points in parsed strings.
        json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return body
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError, AttributeError):
        raise RepairError("REPAIR_JSON") from None


def changed_fields(before, after, pointer=""):
    if type(before) is dict and type(after) is dict:
        changed = []
        for key in sorted(set(before) | set(after)):
            location = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
            changed += ([location] if key not in before or key not in after else
                        changed_fields(before[key], after[key], location))
        return changed
    if type(before) is list and type(after) is list and len(before) == len(after):
        return [field for i, (old, new) in enumerate(zip(before, after))
                for field in changed_fields(old, new, pointer + "/" + str(i))]
    return [] if type(before) is type(after) and before == after else [pointer or "/"]


def _indexed(items, key="id"):
    _require(type(items) is list and all(type(x) is dict and key in x for x in items), "REPAIR_PROJECTION")
    result = {x[key]: x for x in items}
    _require(len(items) == len(result), "REPAIR_PROJECTION")
    return result


def validate_impact_projection(before, after, *, source_changes=None):
    """Freeze check semantics; support coverage may change only with exact source diff."""
    try:
        for key in ("schema_version", "task", "task_contract"):
            _require(before[key] == after[key], "REPAIR_IMPACT_IDENTITY")
        old_checks, new_checks = _indexed(before["selected_checks"]), _indexed(after["selected_checks"])
        _require(old_checks.keys() == new_checks.keys(), "REPAIR_SELECTION_CHANGE")
        changes = _indexed(source_changes, "path") if source_changes is not None else {}
        for check_id, old in old_checks.items():
            new = new_checks[check_id]
            for key in ("family", "argv"):
                _require(old[key] == new[key], "REPAIR_SELECTION_CHANGE")
            _require(set(old["requirement_ids"]) == set(new["requirement_ids"]), "REPAIR_SELECTION_CHANGE")
            old_paths, new_paths = set(old["covered_paths"]), set(new["covered_paths"])
            for path in old_paths ^ new_paths:
                change = changes.get(path)
                _require(change is not None, "REPAIR_COVERAGE_CHANGE")
                if path in new_paths:
                    _require(change["before_blob"] is None and change["after_blob"] is not None, "REPAIR_COVERAGE_CHANGE")
                else:
                    _require(change["before_blob"] is not None and change["after_blob"] is None, "REPAIR_COVERAGE_CHANGE")
        for section, fields in (("excluded_checks", ("family",)), ("prevalidation_obligations", ("mode",))):
            old, new = _indexed(before[section]), _indexed(after[section])
            _require(old.keys() == new.keys(), "REPAIR_SELECTION_CHANGE")
            _require(all(all(a[field] == new[key][field] for field in fields) for key, a in old.items()),
                     "REPAIR_SELECTION_CHANGE")
    except (KeyError, TypeError):
        raise RepairError("REPAIR_PROJECTION") from None


def validate_metadata_replacement(original, replacement, repair=None):
    old, new = original.get("payload", {}), replacement.get("payload", {})
    kind = original.get("artifact_kind")
    _require(kind == replacement.get("artifact_kind") and
             original.get("producer_role") == replacement.get("producer_role"), "REPAIR_PRODUCER")
    required = {"test-gate-report": ("status",), "implementation-report": ("status",),
        "tester-confidential-report": ("outcome",), "reviewer-report": ("verdict",),
        "terminal-record": ("result",), "human-decision": ("gate", "decision", "subject_sha")}.get(kind, ())
    _require(all(key in old for key in required), "REPAIR_BUSINESS_MISSING")
    mappings = {x["field"]: x for x in repair["payload"]["attachment_changes"]} if repair else {}
    for key in PRESERVED:
        if key in mappings:
            change = mappings[key]
            _require(key in old and key in new and old[key] == change["before"]["ref"] and
                     new[key] == change["after"]["ref"], "REPAIR_ATTACHMENT_MAPPING")
        else:
            _require(old.get(key) == new.get(key), "REPAIR_BUSINESS_CHANGE")
    if repair:
        _require(is_v1(repair, "METADATA"), "REPAIR_METADATA_REQUIRED")
        # A report's descriptive summary/reason may be repaired; all other
        # non-attachment payload fields remain byte-value equivalent.
        mutable = {"dispatch_id", "summary", "reason"} | mappings.keys()
        _require({k: v for k, v in old.items() if k not in mutable} ==
                 {k: v for k, v in new.items() if k not in mutable}, "REPAIR_BUSINESS_CHANGE")
        _require(all(field in old and field in new for field in mappings), "REPAIR_ATTACHMENT_MAPPING")


def effective_test(test_payload, support_payload=None):
    if support_payload:
        return {"test_tip": support_payload["to_test_tip"], "test_manifest": support_payload["test_manifest"],
                "impact_set": support_payload["impact_set"]}
    return {"test_tip": test_payload.get("test_tip"), "test_manifest": test_payload.get("manifest"),
            "impact_set": test_payload.get("impact_set")}


def equivalent_evidence(original_ref, current_ref, repair_bodies):
    reachable = [original_ref]
    for repair in repair_bodies:
        if is_v1(repair, "METADATA"):
            for change in repair["payload"]["attachment_changes"]:
                if change["before"]["ref"] in reachable:
                    reachable.append(change["after"]["ref"])
    return current_ref in reachable


def equivalent_artifact_ref(original_ref, current_ref, resolve):
    """Resolve a directed metadata replacement chain; callers validate receipts/order."""
    visited = set()
    while current_ref and current_ref["artifact_id"] not in visited:
        if current_ref == original_ref:
            return True
        visited.add(current_ref["artifact_id"])
        body = resolve(current_ref)
        replacement = body.get("replaces") if body else None
        if not replacement:
            return False
        old = resolve(replacement["original"])
        repair = resolve(replacement["repair"]) if "repair" in replacement else None
        if not old:
            return False
        try:
            _same_context(old, body)
            validate_metadata_replacement(old, body, repair)
        except RepairError:
            return False
        current_ref = replacement["original"]
    return False


def validate_retest_evidence(report, candidate, previous_reports, resolve):
    """Reject known exact evidence identity reuse, not identical fresh outcomes."""
    p = candidate.get("payload", {})
    support_ref = p.get("support_repair")
    if not support_ref or report.get("replaces"):
        return
    previous_reports = list(previous_reports)
    previous_ref = p.get("previous_candidate")
    if p.get("rerun_of"):
        rerun = _resolved(p["rerun_of"], resolve, "tester-confidential-report")
        launches = [ref for ref in rerun["predecessors"] if ref["kind"] == "candidate-test-envelope"]
        _require(len(launches) == 1, "REPAIR_SUPPORT_LINEAGE")
        previous_ref = launches[0]
    boundary = None
    if previous_ref:
        previous = _resolved(previous_ref, resolve, "candidate-test-envelope")["payload"]
        executed = any(old.get("payload", {}).get("candidate_sha") == previous["candidate"]["commit"] and
                       old.get("payload", {}).get("execution_id") == previous["execution_id"]
                       for old in previous_reports)
        if executed:
            boundary = previous.get("support_repair")
    affected, visited = set(), set()
    while support_ref and support_ref != boundary:
        _require(support_ref["artifact_id"] not in visited, "REPAIR_SUPPORT_LINEAGE")
        visited.add(support_ref["artifact_id"])
        support = _resolved(support_ref, resolve, "delivery-repair")
        _require(is_v1(support, "TEST_SUPPORT"), "REPAIR_SUPPORT_BINDING")
        affected.update(support["payload"]["retest_check_ids"])
        support_ref = support["payload"]["previous_support_repair"]
    _require(boundary is None or support_ref == boundary, "REPAIR_SUPPORT_LINEAGE")
    current = report.get("payload", {})
    def same_execution(old):
        # A Guard graph is an unordered catalog: it can already contain a later
        # metadata delivery for the execution being rechecked. Delivery identity
        # is not execution identity; replacement equivalence is checked separately.
        other = old.get("payload", {})
        return (current.get("execution_id") is not None and
                other.get("execution_id") == current["execution_id"] and
                other.get("candidate_sha") == current.get("candidate_sha"))
    old_refs = [run["result"] for old in previous_reports
                if old["artifact_id"] != report["artifact_id"] and not same_execution(old)
                for run in old.get("payload", {}).get("execution", []) if run["purpose"] in affected]
    for run in report.get("payload", {}).get("execution", []):
        if run["purpose"] in affected:
            _require(run["result"] not in old_refs, "REPAIR_STALE_EXECUTION_EVIDENCE")


def _resolved(ref, resolve, kind=None):
    body = resolve(ref)
    _require(body is not None and body.get("artifact_id") == ref["artifact_id"] and
             body.get("artifact_kind") == ref["kind"] and
             (kind is None or body["artifact_kind"] == kind), "REPAIR_REFERENCE")
    return body


def _same_context(first, second):
    _require(all(first.get(key) == second.get(key) for key in
                 ("task", "governor", "task_contract")), "REPAIR_CONTEXT")


def _source_tuples(bindings):
    return {(x["commit"], x["path"], x["blob"]) for x in bindings}


def _bound_source_commits(artifact, original, resolve):
    sources = {artifact["governor"]["commit"]}
    def include(body):
        p = body.get("payload", {})
        for key in ("test_tip", "implementation_tip", "candidate", "from_test_tip", "to_test_tip"):
            if p.get(key):
                sources.add(p[key]["commit"])
        for key in ("candidate_sha", "subject_sha", "last_implementation", "preserved_implementation"):
            if p.get(key):
                sources.add(p[key])
    include(original)
    refs = list(original.get("predecessors", []))
    if is_v1(artifact, "TEST_SUPPORT"):
        include(artifact)
        refs += [artifact["payload"][key] for key in ("approved_test_report", "implementation_report")
                 if artifact["payload"][key]]
    for ref in refs:
        if ref["kind"] in ("test-gate-report", "implementation-report", "candidate-test-envelope", "reviewer-launch"):
            body = resolve(ref)
            if body:
                _same_context(artifact, body)
                include(body)
    return sources


def _audit(payload):
    audit = payload["semantic_audit"]
    dimensions = _indexed(audit["dimensions"], "dimension")
    _require(set(dimensions) == DIMENSIONS and audit["reviewer_role"] == "orchestrator" and
             bool(audit["reviewer_id"].strip()) and audit["requirement_ids"] and audit["source_bindings"],
             "REPAIR_SEMANTIC_AUDIT")
    _require(all(all(type(d[key]) is str and d[key].strip() for key in ("before", "after", "explanation"))
                 for d in dimensions.values()), "REPAIR_SEMANTIC_AUDIT")
    # Narrative before/after bases may differ. Only the structured source and
    # acceptance projections are mechanically comparable; the named reviewer
    # remains responsible for actual semantic equivalence of the exact diff.
    return audit


def _dependency_audit(change, before, after):
    old = {(x["from"], x["to"]) for x in before["public_dependency_edges"]}
    new = {(x["from"], x["to"]) for x in after["public_dependency_edges"]}
    removed, added = old - new, new - old
    audited_old, audited_new = [], []
    facts = _source_tuples(change["source_facts"])
    covered = {path for check in after["selected_checks"] for path in check["covered_paths"]}
    for edge in change["dependency_audit"]:
        _require(edge["before"] is not None or edge["after"] is not None, "REPAIR_DEPENDENCY_AUDIT")
        bindings = _source_tuples(edge["source_bindings"])
        _require(bindings and bindings <= facts and edge["explanation"].strip(), "REPAIR_DEPENDENCY_AUDIT")
        for name, target, domain in (("before", audited_old, removed), ("after", audited_new, added)):
            value = edge[name]
            if value is not None:
                pair = (value["from"], value["to"])
                _require(pair in domain, "REPAIR_DEPENDENCY_AUDIT")
                # The old edge may contain the actual typo under repair, so
                # nonexistent old endpoints cannot supply truthful source blobs.
                # The corrected edge must bind both real current endpoints.
                _require(name != "after" or set(pair) <= {x[1] for x in bindings}, "REPAIR_DEPENDENCY_AUDIT")
                _require(name != "after" or set(pair) <= covered, "REPAIR_DEPENDENCY_COVERAGE")
                target.append(pair)
    _require(set(audited_old) == removed and set(audited_new) == added and
             len(audited_old) == len(removed) and len(audited_new) == len(added), "REPAIR_DEPENDENCY_AUDIT")


def _manifest(body, source, artifact, requirements):
    gov = artifact["governor"]
    _require(body["contract_version"] == 3 and body["contract_blob_sha"] == gov["workflow_contract_blob"] and
             body["base_sha"] == gov["commit"] and body["lane_sha"] == source and
             set(body["requirement_ids"]) == set(requirements), "REPAIR_MANIFEST_IDENTITY")


def _attachment_changes(artifact, original, validate_after, expected_before, expected_after=None):
    p, op = artifact["payload"], original["payload"]
    support = p["mode"] == "TEST_SUPPORT"
    changes = _indexed(p["attachment_changes"], "field")
    audit = p["semantic_audit"]
    audit_facts = _source_tuples(audit["source_bindings"])
    for field, change in changes.items():
        _require(field in ATTACHMENTS and field in expected_before, "REPAIR_ATTACHMENT_FIELD")
        _require(change["before"]["ref"] == expected_before[field] and
                 change["before"]["ref"] != change["after"]["ref"], "REPAIR_ATTACHMENT_MAPPING")
        if expected_after is not None:
            _require(field in expected_after and change["after"]["ref"] == expected_after[field],
                     "REPAIR_ATTACHMENT_MAPPING")
        before, after = validate_snapshot(change["before"]), validate_snapshot(change["after"])
        _require(set(change["changed_fields"]) == set(changed_fields(before, after)) and
                 len(change["changed_fields"]) == len(set(change["changed_fields"])), "REPAIR_DIFF_INVENTORY")
        facts = _source_tuples(change["source_facts"])
        _require(facts and facts <= audit_facts, "REPAIR_SOURCE_BINDINGS")
        validate_after(after, ATTACHMENTS[field])
        expected_type = {"LaneManifestV1": "manifest", "ImpactSet": "impact-set", "CoverageJoin": "coverage-join"}[ATTACHMENTS[field]]
        _require(all(change[name]["ref"]["evidence_type"] == expected_type for name in ("before", "after")),
                 "REPAIR_ATTACHMENT_TYPE")
        if field == "impact_set":
            validate_impact_projection(before, after, source_changes=p["source_changes"] if support else None)
            _require(after["task"] == artifact["task"] and after["task_contract"] == artifact["task_contract"],
                     "REPAIR_IMPACT_IDENTITY")
            _dependency_audit(change, before, after)
        else:
            _require(not change["dependency_audit"], "REPAIR_DEPENDENCY_AUDIT")
            if ATTACHMENTS[field] == "LaneManifestV1":
                tip = p["to_test_tip"] if support else (op.get("implementation_tip") if field == "implementation_manifest"
                    else op.get("test_tip") if field == "test_manifest" else op.get("implementation_tip") or op.get("test_tip"))
                _require(tip is not None, "REPAIR_SOURCE_BINDINGS")
                requirements = [x["requirement_id"] for x in op.get("requirement_coverage", [])]
                if not requirements:
                    _require("requirement_ids" in before, "REPAIR_BUSINESS_MISSING")
                    requirements = before["requirement_ids"]
                _manifest(after, tip["commit"], artifact, requirements)
                if support:
                    _manifest(before, p["from_test_tip"]["commit"], artifact, requirements)
                _require(any(x[0] == tip["commit"] for x in facts), "REPAIR_SOURCE_BINDINGS")
            else:
                for key in ("schema_version", "test_commit", "implementation_commit"):
                    _require(key in before and before[key] == after[key], "REPAIR_COVERAGE_CHANGE")
                def projection(body):
                    return sorted((x["path"], x["owner"], tuple(sorted(x["requirement_ids"])),
                                   tuple(sorted(x["selected_check_ids"]))) for x in body["changed_paths"])
                _require(projection(before) == projection(after), "REPAIR_COVERAGE_CHANGE")
                if before["impact_set_sha256"] != after["impact_set_sha256"]:
                    mapping = changes.get("impact_set")
                    _require(mapping and mapping["before"]["ref"]["sha256"] == before["impact_set_sha256"] and
                             mapping["after"]["ref"]["sha256"] == after["impact_set_sha256"], "REPAIR_ATTACHMENT_MAPPING")
    return changes


def validate_repair(artifact, resolve, validate_after):
    """Validate supplied repair evidence only; caller adds live order or Git truth."""
    try:
        _require(is_v1(artifact), "REPAIR_VERSION")
        p = artifact["payload"]
        original = _resolved(p["original"], resolve)
        _same_context(artifact, original)
        _require(artifact["producer_role"] == "orchestrator" and
                 artifact["consumer_role"] == original["producer_role"] and
                 artifact["visibility"] == original["visibility"], "REPAIR_PRODUCER")
        _require(artifact["artifact_id"] != original["artifact_id"] and
                 p["replacement_output"] != p["original"]["path"], "REPAIR_IDENTITY")
        trigger = p["trigger"]
        trigger_ref = trigger["receipt"] if trigger["kind"] == "GUARD_REJECTED" else trigger["checked"]
        receipt = _resolved(trigger_ref, resolve, "guard-result")
        status = "REJECTED" if trigger["kind"] == "GUARD_REJECTED" else "CHECKED"
        _require(receipt["status"] == status and receipt["exit_code"] == (1 if status == "REJECTED" else 0) and
                 receipt["input"] == {key: p["original"][key] for key in ("artifact_id", "path", "sha256")} and
                 receipt["trusted_context"] == {key: artifact[key] for key in ("task", "governor", "task_contract")} and
                 receipt["visibility"] == original["visibility"] and
                 receipt["consumer_role"] == original["consumer_role"], "REPAIR_TRIGGER")
        _require(p["original"] in artifact["predecessors"] and trigger_ref in artifact["predecessors"],
                 "REPAIR_PREDECESSOR")
        op = original["payload"]
        _require("lane" not in op or p["lane"] == op["lane"], "REPAIR_LANE")
        audit = _audit(p)
        _require({x["commit"] for x in audit["source_bindings"]} <=
                 _bound_source_commits(artifact, original, resolve), "REPAIR_SOURCE_BINDINGS")
        if p["mode"] == "METADATA":
            # Missing business fields remain an error even before replacement.
            validate_metadata_replacement(original, original)
            _attachment_changes(artifact, original, validate_after,
                                {key: op[key] for key in ATTACHMENTS if key in op})
            return
        _require(p["mode"] == "TEST_SUPPORT", "REPAIR_MODE")
        approved = _resolved(p["approved_test_report"], resolve, "test-gate-report")
        approval = _resolved(p["approval"], resolve, "human-decision")
        for body in (approved, approval):
            _same_context(artifact, body)
        ap = approved["payload"]
        _require(ap["status"] == "READY" and p["lane"] == ap["lane"] and
                 approval["payload"]["gate"] == "TEST" and approval["payload"]["decision"] == "APPROVE" and
                 approval["payload"]["subject_sha"] == ap["test_tip"]["commit"] and
                 any(equivalent_artifact_ref(ref, p["approved_test_report"], resolve)
                     for ref in approval["predecessors"] if ref["kind"] == "test-gate-report"), "REPAIR_APPROVAL")
        previous = _resolved(p["previous_support_repair"], resolve, "delivery-repair") if p["previous_support_repair"] else None
        if previous:
            _require(is_v1(previous, "TEST_SUPPORT"), "REPAIR_SUPPORT_LINEAGE")
            _same_context(artifact, previous)
            _require(equivalent_artifact_ref(previous["payload"]["approval"], p["approval"], resolve) and
                     equivalent_artifact_ref(previous["payload"]["approved_test_report"], p["approved_test_report"], resolve) and
                     previous["payload"]["lane"] == p["lane"], "REPAIR_SUPPORT_LINEAGE")
        old = effective_test(ap, previous["payload"] if previous else None)
        _require(p["from_test_tip"] == old["test_tip"] and
                 p["to_test_tip"]["commit"] != p["from_test_tip"]["commit"], "REPAIR_SUPPORT_LINEAGE")
        _require(set(p["retest_check_ids"]) == set(audit["affected_check_ids"]) and p["retest_check_ids"],
                 "REPAIR_RETEST_SCOPE")
        mappings = _attachment_changes(artifact, approved, validate_after,
            {"test_manifest": old["test_manifest"], "impact_set": old["impact_set"]},
            {"test_manifest": p["test_manifest"], "impact_set": p["impact_set"]})
        _require(set(mappings) == {"test_manifest", "impact_set"}, "REPAIR_SUPPORT_ATTACHMENTS")
        impact = validate_snapshot(mappings["impact_set"]["after"])
        checks = _indexed(impact["selected_checks"])
        _require(set(p["retest_check_ids"]) <= checks.keys(), "REPAIR_RETEST_SCOPE")
        source_changes = _indexed(p["source_changes"], "path")
        _require(source_changes, "REPAIR_SOURCE_DIFF")
        if p["implementation_report"]:
            implementation = _resolved(p["implementation_report"], resolve, "implementation-report")
            _same_context(artifact, implementation)
            _require(implementation["payload"]["status"] == "READY" and
                     not (source_changes.keys() & {x["path"] for x in implementation["payload"]["changed_paths"]}),
                     "REPAIR_SOURCE_OWNERSHIP")
        facts = _source_tuples(audit["source_bindings"])
        for path, change in source_changes.items():
            before, after = change["before_blob"], change["after_blob"]
            _require(before != after and (before is not None or after is not None), "REPAIR_SOURCE_DIFF")
            for tip, blob in ((p["from_test_tip"], before), (p["to_test_tip"], after)):
                _require(blob is None or (tip["commit"], path, blob) in facts, "REPAIR_SOURCE_BINDINGS")
            affected = {key for key, check in checks.items() if path in check["covered_paths"]}
            if after is None:
                old_impact = validate_snapshot(mappings["impact_set"]["before"])
                affected |= {x["id"] for x in old_impact["selected_checks"] if path in x["covered_paths"]}
            _require(affected and affected <= set(p["retest_check_ids"]), "REPAIR_RETEST_SCOPE")
        for key in ("approved_test_report", "approval", "previous_support_repair", "previous_candidate", "implementation_report"):
            _require(p[key] is None or p[key] in artifact["predecessors"], "REPAIR_PREDECESSOR")
    except RepairError:
        raise
    except (KeyError, TypeError, AttributeError, ValueError):
        raise RepairError("REPAIR_EVIDENCE") from None
