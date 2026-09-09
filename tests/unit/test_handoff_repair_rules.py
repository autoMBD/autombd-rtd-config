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
# File:        test_handoff_repair_rules.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Public repair projection and exact inline evidence regressions.
# =================================================================================

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "agent-discipline/skills/agent-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def rules():
    assert (SCRIPTS / "repair_protocol.py").is_file(), "Shared pure repair protocol is missing"
    return importlib.import_module("repair_protocol")


def snapshot(body, label="impact", raw=None):
    raw = raw or json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
    return {"ref": {"path": f".agent-state/{label}.json", "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "evidence_type": "impact-set"}, "raw": raw}


def impact():
    return {"schema_version": "1.0", "task": {"repository": "example/tree", "issue_number": 9, "task_run": "oak"},
        "task_contract": {"revision": 0, "path": ".agent-state/k.json", "sha256": "a" * 64},
        "selected_checks": [{"id": "CHECK_A", "family": "unit", "argv": ["python", "tests/check.py"],
                             "requirement_ids": ["REQ_A"], "covered_paths": ["src/api.py", "tests/check.py"]}],
        "excluded_checks": [{"id": "OUT", "family": "vendor", "reason": "No vendor boundary"}],
        "public_dependency_edges": [{"from": "src/api.py", "to": "tests/check.py", "reason": "Public dependency"}],
        "prevalidation_obligations": [{"id": "PRE", "mode": "FULL_CHAIN", "reason": None}]}


def test_legacy_guard_human_replacement_cannot_change_vote():
    from structured_handoff_rules import LocalRules
    from structured_handoff_schema import ProtocolError
    original_ref = {"kind": "human-decision", "artifact_id": "vote-old", "path": ".agent-state/old.json", "sha256": "a" * 64}
    receipt_ref = {"kind": "guard-result", "artifact_id": "receipt", "path": ".agent-state/reject.json", "sha256": "b" * 64}
    old = {"artifact_kind": "human-decision", "artifact_id": "vote-old", "producer_role": "human",
           "task_contract": {}, "payload": {"gate": "TEST", "decision": "REQUEST_CHANGES", "subject_sha": "c" * 40}}
    new = copy.deepcopy(old)
    new.update(artifact_id="vote-new", replaces={"original": original_ref, "guard_result": receipt_ref})
    new["payload"]["decision"] = "APPROVE"
    class Graph:
        artifacts = {"vote-old": old, "receipt": {"artifact_kind": "guard-result", "status": "REJECTED",
            "input": {k: original_ref[k] for k in ("artifact_id", "path", "sha256")}}}
    with pytest.raises(ProtocolError):
        LocalRules(Graph()).replacement(new)


@pytest.mark.parametrize("field", ["gate", "decision", "subject_sha"])
def test_missing_original_human_business_value_is_never_inferred(rules, field):
    old = {"artifact_kind": "human-decision", "producer_role": "human", "payload": {
        "gate": "FINAL", "decision": "STOP", "subject_sha": None}}
    new = copy.deepcopy(old)
    del old["payload"][field]
    with pytest.raises(rules.RepairError):
        rules.validate_metadata_replacement(old, new)


def test_snapshot_verifies_raw_digest_and_strict_parsed_body(rules):
    sample = snapshot({"value": "真实源"})
    assert rules.validate_snapshot(sample) == {"value": "真实源"}
    for changed in (dict(sample, body={"value": "different"}), dict(sample, raw=sample["raw"] + " "),
                    snapshot({"value": 2}, raw='{"value":1,"value":2}\n')):
        with pytest.raises(rules.RepairError):
            rules.validate_snapshot(changed)


@pytest.mark.parametrize("field,value", [("argv", ["python", "wrong.py"]), ("id", "OTHER"),
    ("family", "functional"), ("requirement_ids", ["REQ_B"]), ("covered_paths", ["src/api.py"])])
def test_metadata_impact_projection_rejects_acceptance_changes(rules, field, value):
    old = impact()
    new = copy.deepcopy(old)
    new["selected_checks"][0][field] = value
    with pytest.raises(rules.RepairError):
        rules.validate_impact_projection(old, new)


def test_descriptive_impact_projection_preserves_semantics(rules):
    old = impact()
    new = copy.deepcopy(old)
    new["excluded_checks"][0]["reason"] = "No device-specific contract is selected"
    new["selected_checks"][0]["covered_paths"].reverse()
    rules.validate_impact_projection(old, new)


def test_support_coverage_changes_need_exact_real_diff(rules):
    old = impact()
    new = copy.deepcopy(old)
    new["selected_checks"][0]["covered_paths"].append("tests/transport.py")
    changes = [{"path": "tests/transport.py", "before_blob": None, "after_blob": "d" * 40,
                "reason": "New non-case adapter; assertions unchanged"}]
    rules.validate_impact_projection(old, new, source_changes=changes)
    with pytest.raises(rules.RepairError):
        rules.validate_impact_projection(old, new, source_changes=[])
    new["selected_checks"][0]["covered_paths"].remove("tests/check.py")
    with pytest.raises(rules.RepairError):
        rules.validate_impact_projection(old, new, source_changes=changes)


def test_new_feature_never_implicitly_enabled_by_local_schema(rules):
    artifact = {"artifact_kind": "candidate-test-envelope", "payload": {"support_repair": {}}}
    with pytest.raises(rules.RepairError):
        rules.require_capability({"schema_version": 2, "contract_version": 2}, artifact)
    rules.require_capability({"schema_version": 2, "contract_version": 3,
        "non_case_repairs": {"version": "1.0", "metadata": True, "test_support": True}}, artifact)


def test_exact_changed_field_inventory_is_computed_without_io(rules):
    old = {"a": [{"x": 1}], "b": "before"}
    new = {"a": [{"x": 2}], "b": "after", "c": None}
    assert rules.changed_fields(old, new) == ["/a/0/x", "/b", "/c"]


def test_cumulative_unexecuted_support_checks_keep_freshness_obligations(rules):
    first = {"kind": "delivery-repair", "artifact_id": "first"}
    latest = {"kind": "delivery-repair", "artifact_id": "latest"}
    records = {"first": {"artifact_id": "first", "artifact_kind": "delivery-repair",
        "payload": {"repair_version": "1.0", "mode": "TEST_SUPPORT", "previous_support_repair": None,
                    "retest_check_ids": ["A"]}},
        "latest": {"artifact_id": "latest", "artifact_kind": "delivery-repair",
        "payload": {"repair_version": "1.0", "mode": "TEST_SUPPORT", "previous_support_repair": first,
                    "retest_check_ids": ["B"]}}}
    old_ref = {"path": ".agent-state/old-result.json", "sha256": "a" * 64, "evidence_type": "command-result"}
    report = {"artifact_id": "new-report", "payload": {"execution": [{"purpose": "A", "result": old_ref}]}}
    prior = {"artifact_id": "prior-report", "payload": {"execution": [{"purpose": "A", "result": old_ref}]}}
    with pytest.raises(rules.RepairError):
        rules.validate_retest_evidence(report, {"payload": {"support_repair": latest}}, [prior],
                                      lambda ref: records[ref["artifact_id"]])


def test_dependency_typo_can_be_corrected_using_real_current_endpoint_blobs(rules):
    old, new = impact(), impact()
    old["public_dependency_edges"][0]["to"] = "tests/misspelled.py"
    facts = [{"commit": "a" * 40, "path": path, "blob": "b" * 40}
             for path in ("src/api.py", "tests/check.py")]
    audit = {"before": {"from": "src/api.py", "to": "tests/misspelled.py"},
             "after": {"from": "src/api.py", "to": "tests/check.py"}, "source_bindings": facts,
             "explanation": "The old target was a descriptive typo; these exact current files are the real edge."}
    rules._dependency_audit({"source_facts": facts, "dependency_audit": [audit]}, old, new)


def test_retest_accumulation_stops_at_previous_executed_support(rules):
    first = {"kind": "delivery-repair", "artifact_id": "first"}
    latest = {"kind": "delivery-repair", "artifact_id": "latest"}
    previous = {"kind": "candidate-test-envelope", "artifact_id": "previous"}
    records = {"first": {"artifact_id": "first", "artifact_kind": "delivery-repair",
        "payload": {"repair_version": "1.0", "mode": "TEST_SUPPORT", "previous_support_repair": None,
                    "retest_check_ids": ["A"]}},
        "latest": {"artifact_id": "latest", "artifact_kind": "delivery-repair",
        "payload": {"repair_version": "1.0", "mode": "TEST_SUPPORT", "previous_support_repair": first,
                    "retest_check_ids": ["B"]}},
        "previous": {"artifact_id": "previous", "artifact_kind": "candidate-test-envelope",
            "payload": {"support_repair": first, "candidate": {"commit": "old-source"}, "execution_id": "old-exec"}}}
    result = {"path": ".agent-state/old-result.json", "sha256": "a" * 64, "evidence_type": "command-result"}
    prior = {"artifact_id": "prior", "payload": {"candidate_sha": "old-source", "execution_id": "old-exec",
        "execution": [{"purpose": "A", "result": result}]}}
    new = {"artifact_id": "new", "payload": {"candidate_sha": "new-source", "execution_id": "new-exec",
        "execution": [{"purpose": "A", "result": result}]}}
    rules.validate_retest_evidence(new, {"payload": {"support_repair": latest, "previous_candidate": previous}},
                                  [prior], lambda ref: records[ref["artifact_id"]])


def test_same_execution_metadata_delivery_is_not_old_execution(rules):
    support = {"kind": "delivery-repair", "artifact_id": "repair"}
    body = {"artifact_kind": "delivery-repair", "artifact_id": "repair", "payload": {
        "repair_version": "1.0", "mode": "TEST_SUPPORT", "retest_check_ids": ["A"], "previous_support_repair": None}}
    result = {"path": ".agent-state/result.json", "sha256": "a" * 64, "evidence_type": "command-result"}
    report = {"artifact_id": "original", "payload": {"execution_id": "same", "candidate_sha": "same",
        "execution": [{"purpose": "A", "result": result}]}}
    metadata = copy.deepcopy(report)
    metadata["artifact_id"] = "new-delivery"
    rules.validate_retest_evidence(report, {"payload": {"support_repair": support}}, [metadata], lambda ref: body)


@pytest.mark.parametrize("broken", ["missing", "cycle", "unrelated-boundary"])
def test_cumulative_retest_requires_closed_repair_lineage(rules, broken):
    support = {"kind": "delivery-repair", "artifact_id": "support"}
    previous = {"kind": "candidate-test-envelope", "artifact_id": "previous"}
    other = {"kind": "delivery-repair", "artifact_id": "other"}
    body = {"artifact_kind": "delivery-repair", "artifact_id": "support", "payload": {
        "repair_version": "1.0", "mode": "TEST_SUPPORT", "retest_check_ids": ["A"],
        "previous_support_repair": support if broken == "cycle" else other if broken == "missing" else None}}
    records = {"support": body, "previous": {"artifact_kind": "candidate-test-envelope", "artifact_id": "previous",
        "payload": {"candidate": {"commit": "before"}, "execution_id": "before", "support_repair": other}}}
    candidate = {"payload": {"support_repair": support}}
    prior = []
    if broken == "unrelated-boundary":
        candidate["payload"]["previous_candidate"] = previous
        prior = [{"artifact_id": "old", "payload": {"candidate_sha": "before", "execution_id": "before"}}]
    with pytest.raises(rules.RepairError):
        rules.validate_retest_evidence({"artifact_id": "new", "payload": {}}, candidate, prior,
                                      lambda ref: records.get(ref["artifact_id"]))
