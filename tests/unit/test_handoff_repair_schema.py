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
# File:        test_handoff_repair_schema.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Worker generality tests for closed non-case repair wire domains.
# =================================================================================

import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
SCHEMAS = SCRIPTS.parent / "schemas"
CAPABILITY = {"version": "1.0", "metadata": True, "test_support": True}
DIMENSIONS = ("scenarios", "conditions", "assertions", "expected_results",
              "pass_fail_criteria", "selected_checks", "exclusions", "coverage")


@pytest.fixture
def wire():
    sys.path.insert(0, str(SCRIPTS))
    import workflow_transition_wire
    return workflow_transition_wire


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location("repair_schema_gate", SCRIPTS / "workflow_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protocol_data(version):
    workflow = json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text(encoding="utf-8"))
    workflow["contract_version"] = version
    workflow.pop("non_case_repairs", None)
    if version == 3:
        workflow["non_case_repairs"] = copy.deepcopy(CAPABILITY)
    return {"handoff_schema": json.loads((SCHEMAS / "handoff-v1.schema.json").read_text(encoding="utf-8")),
            "registry": json.loads((SCHEMAS / "functional-development-v1.json").read_text(encoding="utf-8")),
            "workflow_contract": workflow}


def artifact(name="origin", kind="test-gate-report"):
    return {"kind": kind, "artifact_id": name,
            "path": ".agent-state/repair-general/" + name + ".json", "sha256": "c" * 64}


def evidence():
    return {"path": ".agent-state/repair-general/manifest.json", "sha256": "d" * 64,
            "evidence_type": "manifest"}


def source():
    return {"commit": "a" * 40, "path": "tests/drivers/shared.py", "blob": "b" * 40}


def repair(mode):
    value = {"repair_version": "1.0", "mode": mode, "dispatch_id": "repair-maple",
        "original": artifact(),
        "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": artifact("checked", "guard-result"),
                    "observation": "The descriptive ownership label is inaccurate."},
        "lane": {"lane_id": "test-maple", "agent_session_id": "session-maple",
                 "worktree_id": "tree-maple", "branch": "test/maple"},
        "replacement_output": ".agent-state/repair-general/replacement.json",
        "reason": "Restore accurate descriptive metadata without changing acceptance.",
        "attachment_changes": [],
        "semantic_audit": {"requirement_ids": ["REQ-A"], "source_bindings": [source()],
            "dimensions": [{"dimension": name, "before": "Bound original " + name,
                            "after": "Bound unchanged " + name, "explanation": "No semantic delta."}
                           for name in DIMENSIONS],
            "affected_check_ids": [], "reviewer_role": "orchestrator", "reviewer_id": "audit-maple"}}
    if mode == "METADATA":
        value.update(preserve_tip=None, preserve_candidate_index=None,
                     preserve_correction_count=0, preserve_review_id=None)
    else:
        value.update(approval=artifact("approval", "human-decision"),
            approved_test_report=artifact(), previous_support_repair=None, previous_candidate=None,
            from_test_tip={"commit": "a" * 40, "tree": "b" * 40, "parents": ["e" * 40]},
            to_test_tip={"commit": "f" * 40, "tree": "d" * 40, "parents": ["a" * 40]},
            implementation_report=None, candidate_index=None, correction_count=0,
            test_manifest=evidence(), impact_set=dict(evidence(), evidence_type="impact-set"),
            source_changes=[{"path": "tests/drivers/shared.py", "before_blob": "b" * 40,
                             "after_blob": "d" * 40, "reason": "Correct driver path resolution."}],
            retest_check_ids=["CHECK-A"])
    return value


def sample(schema, defs):
    if "$ref" in schema:
        return sample(defs[schema["$ref"].split("/")[-1]], defs)
    if "anyOf" in schema:
        return sample(schema["anyOf"][0], defs)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "object":
        return {key: sample(child, defs) for key, child in schema["properties"].items()}
    if kind == "array":
        return [sample(schema["items"], defs) for _ in range(schema.get("minItems", 0))]
    if kind == "integer":
        return schema.get("minimum", 0)
    if kind == "null":
        return None
    if kind == "string":
        if schema.get("pattern") == "^[0-9a-f]{40}$":
            return "a" * 40
        if schema.get("pattern") == "^[0-9a-f]{64}$":
            return "b" * 64
        return ".agent-state/maple.json" if schema.get("format") == "state-path" else "maple"
    return {}


def test_active_contract_explicitly_declares_non_case_repairs():
    workflow = json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text(encoding="utf-8"))
    assert workflow["contract_version"] == 3
    assert workflow["non_case_repairs"] == CAPABILITY


@pytest.mark.parametrize("version", [2, 3])
def test_pure_protocol_accepts_exact_supported_versions(wire, version):
    data = protocol_data(version)
    assert wire.protocol({"protocol": data}) == data["handoff_schema"]["$defs"]


@pytest.mark.parametrize("version,extension", [(2, CAPABILITY), (3, None),
    (3, {}), (3, dict(CAPABILITY, metadata=1)), (3, dict(CAPABILITY, test_support=False)),
    (3, dict(CAPABILITY, version="2.0")), (3, dict(CAPABILITY, arbitrary=True)), (4, CAPABILITY)])
def test_pure_protocol_rejects_implicit_or_unknown_capabilities(wire, version, extension):
    data = protocol_data(version)
    if extension is None:
        data["workflow_contract"].pop("non_case_repairs", None)
    else:
        data["workflow_contract"]["non_case_repairs"] = copy.deepcopy(extension)
    with pytest.raises(wire.WorkflowTransitionError):
        wire.protocol({"protocol": data})


@pytest.mark.parametrize("mode", ["METADATA", "TEST_SUPPORT"])
def test_repair_payloads_accept_complete_fields_and_reject_missing_or_extra(wire, mode):
    defs = protocol_data(3)["handoff_schema"]["$defs"]
    schema = defs["delivery-repair"]["properties"]["payload"]
    value = repair(mode)
    wire.validate(value, schema, defs, "INVALID_EVIDENCE")
    for field in value:
        missing = copy.deepcopy(value)
        del missing[field]
        with pytest.raises(wire.WorkflowTransitionError):
            wire.validate(missing, schema, defs, "INVALID_EVIDENCE")
    with pytest.raises(wire.WorkflowTransitionError):
        wire.validate(dict(value, implicit=True), schema, defs, "INVALID_EVIDENCE")


@pytest.mark.parametrize("binding", ["guard_result", "repair"])
def test_replacement_variants_remain_disjoint_closed_shapes(wire, binding):
    defs = protocol_data(3)["handoff_schema"]["$defs"]
    value = {"original": artifact(), binding: artifact("receipt", "guard-result")}
    wire.validate(value, defs["Replacement"], defs, "INVALID_EVIDENCE")
    value["repair" if binding == "guard_result" else "guard_result"] = artifact("other")
    with pytest.raises(wire.WorkflowTransitionError):
        wire.validate(value, defs["Replacement"], defs, "INVALID_EVIDENCE")


def test_candidate_support_binding_is_explicit_and_absence_preserves_legacy(wire):
    defs = protocol_data(3)["handoff_schema"]["$defs"]
    schema = defs["candidate-test-envelope"]["properties"]["payload"]
    original = sample(schema, defs)
    assert "support_repair" not in original
    wire.validate(original, schema, defs, "INVALID_EVIDENCE")
    wire.validate(dict(original, support_repair=artifact("support", "delivery-repair")),
                  schema, defs, "INVALID_EVIDENCE")
    with pytest.raises(wire.WorkflowTransitionError):
        wire.validate(dict(original, support_repair=None), schema, defs, "INVALID_EVIDENCE")


@pytest.mark.parametrize("name", ["RepairSourceBinding", "RepairSnapshot", "RepairSourceChange",
    "RepairDependencyAudit", "RepairAttachmentChange", "RepairSemanticAudit", "RepairTrigger"])
def test_reusable_evidence_definitions_are_closed_at_each_known_object(wire, name):
    defs = protocol_data(3)["handoff_schema"]["$defs"]
    assert name in defs
    value = sample(defs[name], defs)
    wire.validate(value, defs[name], defs, "INVALID_EVIDENCE")
    for field in value:
        missing = copy.deepcopy(value)
        del missing[field]
        with pytest.raises(wire.WorkflowTransitionError):
            wire.validate(missing, defs[name], defs, "INVALID_EVIDENCE")
    with pytest.raises(wire.WorkflowTransitionError):
        wire.validate(dict(value, unreviewed=True), defs[name], defs, "INVALID_EVIDENCE")


@pytest.mark.parametrize("version", [2, 3])
def test_gate_loads_supported_declarations_but_never_as_legacy_records(gate, tmp_path, version):
    value = protocol_data(version)["workflow_contract"]
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert gate.load_contract(path) == value
    with pytest.raises(gate.WorkflowValidationError, match="legacy|validate-artifact"):
        gate.validate_record({}, contract_path=path)


def test_gate_retains_explicit_legacy_v1(gate):
    assert gate.load_contract(ROOT / "agent-discipline/contracts/workflow-v1.json")["contract_version"] == 1


def test_snapshots_have_no_redundant_or_open_parsed_body():
    defs = protocol_data(3)["handoff_schema"]["$defs"]
    assert "RepairSnapshot" in defs
    snapshot = defs["RepairSnapshot"]
    assert set(snapshot["properties"]) == set(snapshot["required"]) == {"ref", "raw"}
    assert snapshot["additionalProperties"] is False


@pytest.mark.parametrize("version", [2, 3])
def test_protocol_contract_shape_is_closed(wire, version):
    data = protocol_data(version)
    data["workflow_contract"]["extra_capability"] = True
    with pytest.raises(wire.WorkflowTransitionError):
        wire.protocol({"protocol": data})
