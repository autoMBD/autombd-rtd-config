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
# File:        test_workflow_gate_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-22
# Version:     0.3.0
# Description: Generality tests for stateful Agent workflow records and gates.
# =================================================================================

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)

BASE_SHA = "19a7c4e36d12f5480ab9dc753da236f109e8bc47"
TEST_SHA = "b583f0a1c7d26e4905ab3c81f46d9e27a130bc65"
IMPLEMENTATION_SHA = "6e2a094cb8f713d5a6c9420be1387fd450ac8e31"
CANDIDATE_SHA = "da39b7452c1806b94f56139e827ca1d034e6af72"
TREE_SHA = "88f9a24e056d2520e186f8e26c9e64af47eb5671"
EVIDENCE_SHA = "902ba3cda1883801594b6e1b452790cc53948fda"
ISSUE_NUMBER = 314


def _load_gate():
    spec = importlib.util.spec_from_file_location("workflow_gate_generality", GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _stopped_monitor() -> dict[str, object]:
    return {
        "status": "stopped",
        "interval_minutes": 10,
        "scope": "current_session",
    }


def _complete_record() -> dict[str, object]:
    return {
        "version": 1,
        "issue": {
            "number": ISSUE_NUMBER,
            "primary_type": "I",
            "impact_flags": ["AR", "TC", "RP"],
        },
        "state": "complete",
        "gate": {"test_required": True, "light_path": None},
        "lanes": {
            "base_sha": BASE_SHA,
            "test_sha": TEST_SHA,
            "implementation_base_sha": BASE_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
            "candidate_sha": CANDIDATE_SHA,
        },
        "human_reviews": {
            "test": {
                "approved": True,
                "sha": TEST_SHA,
                "reviewer": "maintainer-a",
                "evidence": {
                    "provider": "github",
                    "repository": "org/example-repository",
                    "issue_number": ISSUE_NUMBER,
                    "comment_id": 4821,
                    "command": f"/approve-test {TEST_SHA}",
                },
                "monitor": _stopped_monitor(),
            },
            "final": {
                "approved": True,
                "sha": CANDIDATE_SHA,
                "reviewer": "maintainer-b",
                "monitor": _stopped_monitor(),
            },
        },
        "counters": {"production_rework": 1, "kpi_optimization": 2},
        "tester": {"status": "pass", "candidate_sha": CANDIDATE_SHA},
        "reviewer": {"status": "pass", "candidate_sha": CANDIDATE_SHA},
        "exception": None,
    }


def _canonical_record(state: str = "complete") -> dict[str, object]:
    record = {
        "version": 1,
        "issue": {
            "number": ISSUE_NUMBER,
            "repository": "org/example-repository",
            "primary_type": "B",
            "impact_flags": ["PB"],
        },
        "state": "complete",
        "transition": {
            "from": "final_human_review",
            "to": "complete",
            "event": "final_approved",
        },
        "gate": {
            "test_required": True,
            "light_path": None,
            "required_gates": ["deterministic_tests", "isolated_e2e"],
            "profiles": ["behavioral"],
        },
        "revisions": {
            "base_sha": BASE_SHA,
            "test": {"id": "T4", "sha": TEST_SHA, "base_sha": BASE_SHA},
            "implementation": {
                "id": "W6",
                "sha": IMPLEMENTATION_SHA,
                "base_sha": BASE_SHA,
            },
            "candidate": {
                "id": "C7",
                "sha": CANDIDATE_SHA,
                "test_revision": "T4",
                "implementation_revision": "W6",
                "parents": [IMPLEMENTATION_SHA, TEST_SHA],
                "tree_sha": TREE_SHA,
            },
            "evidence": None,
        },
        "human_reviews": {
            "test": {
                "decision": "approved",
                "approved": True,
                "sha": TEST_SHA,
                "reviewer": "maintainer-a",
                "evidence": {
                    "provider": "github",
                    "repository": "org/example-repository",
                    "artifact": "issue_comment",
                    "issue_number": ISSUE_NUMBER,
                    "comment_id": 4821,
                    "top_level": True,
                    "actor": "maintainer-a",
                    "authorized_actor": True,
                    "revision_sha": TEST_SHA,
                    "command": f"/approve-test {TEST_SHA}",
                    "edited": False,
                    "deleted": False,
                    "request_changes": False,
                },
                "monitor": _stopped_monitor(),
            },
            "final": {
                "decision": "approved",
                "approved": True,
                "sha": CANDIDATE_SHA,
                "reviewer": "maintainer-b",
                "evidence": {
                    "provider": "github",
                    "repository": "org/example-repository",
                    "artifact": "pull_request_review",
                    "pull_request_number": 73,
                    "review_id": 9842,
                    "actor": "maintainer-b",
                    "authorized_actor": True,
                    "revision_sha": CANDIDATE_SHA,
                    "state": "APPROVED",
                    "dismissed": False,
                    "stale": False,
                },
                "monitor": _stopped_monitor(),
            },
        },
        "corrections": {
            "production_rework": {"count": 1, "disposition": "continue"},
            "dependency_permission": {
                "count": 2,
                "audit": [
                    "DP1: dependency path confirmed.",
                    "DP2: execution permission confirmed.",
                ],
            },
            "test_contract": {
                "count": 1,
                "audit": ["TC1: owner corrected the Test contract."],
            },
            "kpi_optimization": {"count": 2, "disposition": "continue"},
        },
        "tester": {"status": "pass", "candidate_sha": CANDIDATE_SHA},
        "reviewer": {"status": "pass", "candidate_sha": CANDIDATE_SHA},
        "stop": None,
        "exception": None,
    }
    if state == "testing":
        record["state"] = "testing"
        record["transition"] = {
            "from": "candidate",
            "to": "testing",
            "event": "candidate_ready",
        }
        record["tester"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
        record["reviewer"] = None
        record["human_reviews"]["final"] = None
    elif state == "reviewing":
        record["state"] = "reviewing"
        record["transition"] = {
            "from": "testing",
            "to": "reviewing",
            "event": "functional_pass",
        }
        record["reviewer"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
        record["human_reviews"]["final"] = None
    return record


def test_contract_uses_the_approved_ordered_platform_neutral_schema():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    machine_name = contract["state_machine"]["name"]
    assert contract["version"] == 1
    assert [item["code"] for item in contract["task_classes"]] == [
        "M", "B", "W", "T", "D", "N", "I"
    ]
    assert {item["state_machine"] for item in contract["task_classes"]} == {
        machine_name
    }
    assert [item["code"] for item in contract["impact_flags"]] == [
        "PB", "MS", "MW", "RA", "TC", "VS", "EV", "AR", "RP", "ED", "SS", "DO"
    ]

    assert "human_review_1" not in contract
    assert "final_human_review" not in contract
    review_1 = contract["state_machine"]["human_review_1"]
    assert review_1["before"] == "implementing"
    assert review_1["binds"] == "test_sha"
    assert review_1["monitor"] == "human_review_monitor"
    assert review_1["evidence"]["provider"] == "github"
    assert review_1["evidence"]["artifact"] == "issue_comment"
    assert review_1["evidence"]["full_sha_required"] is True
    assert review_1["evidence"]["top_level_comment_required"] is True
    assert review_1["evidence"]["authorized_actor"] == "human"
    assert {
        "test_sha_change", "comment_edit", "comment_delete", "request_changes"
    } <= set(review_1["evidence"]["invalidated_by"])
    assert review_1["evidence"]["approval_command"] == "/approve-test {test_sha}"
    assert "request_changes_command" not in review_1["evidence"]
    assert review_1["evidence"]["change_request_command"] == (
        "/request-test-changes {test_sha}\n{reason}"
    )

    final_review = contract["state_machine"]["final_human_review"]
    assert final_review["before"] == "complete"
    assert final_review["binds"] == "candidate_sha"
    assert final_review["monitor"] == "human_review_monitor"
    assert final_review["evidence"]["provider"] == "github"
    assert final_review["evidence"]["artifact"] == "pull_request_review"
    assert final_review["evidence"]["binds"] == "candidate_sha"
    assert final_review["evidence"]["authorized_actor"] == "human"
    assert "candidate_sha" in final_review["evidence"]["required_fields"]
    assert contract["limits"] == {
        "production_rework": 3,
        "kpi_optimization": 3,
    }
    assert contract["human_review_monitor"] == {
        "interval_minutes": 10,
        "scope": "current_session",
        "on_no_change": "no_op",
        "on_update": "stop_then_resume",
        "new_session": False,
    }

    github = contract["repository_host"]["github"]
    assert github["selection_order"] == ["builtin_connector", "gh_cli"]
    assert github["gh_cli_when"] == "builtin_connector_unavailable"
    assert set(github["auth_preflight_distinguishes"]) >= {
        "host_access", "sandbox_access"
    }

    timing = contract["subagent_timing"]
    assert timing["focused_validation_target_minutes"] == 3
    assert timing["e2e_validation_target_minutes"] == 5
    assert timing["evidence_intervention_minutes"] == 10
    assert timing["hard_timeout"] is False
    assert timing["applies_only_to"] == "validation_execution"
    assert set(timing["excluded_work"]) >= {
        "test_authoring", "implementation", "exploration", "review"
    }

    assert contract["lanes"]["names"] == ["test", "implementation", "candidate"]
    assert contract["lanes"]["child_ticket_policy"] == "independent-deliverable-only"
    assert set(contract["lanes"]["required_shas"]) >= {
        "base_sha", "test_sha", "implementation_sha", "candidate_sha"
    }
    assert contract["roles"]["explorer"]["writes"] == []
    assert "owner_acceptance_test_implementation" in contract["roles"]["worker"]["forbidden_inputs"]
    assert contract["roles"]["tester"]["production_writes"] == []
    assert contract["roles"]["reviewer"] == {
        "requires": "tester_pass",
        "writes": ["agent-discipline/agent-lessons-learned.md"],
    }
    serialized = json.dumps(contract).lower()
    assert "default_platform" not in serialized
    assert "opencode by default" not in serialized
    assert "codex by default" not in serialized
    assert "claude code by default" not in serialized


def test_complete_canonical_record_is_valid_and_input_is_not_modified():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    before = deepcopy(record)

    assert validate_record(record) == []
    assert record == before


def test_issue_vocabulary_and_malformed_fields_report_paths_without_raising():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["issue"]["number"] = True
    record["issue"]["primary_type"] = "Q"
    record["issue"]["impact_flags"] = ["AR", "XX", "AR"]

    errors = validate_record(record)

    assert errors == sorted(errors)
    assert any("issue.number" in error for error in errors)
    assert any("issue.primary_type" in error and "Q" in error for error in errors)
    assert any("issue.impact_flags" in error and "XX" in error for error in errors)
    assert any("issue.impact_flags" in error and "duplicate" in error for error in errors)

    malformed = _complete_record()
    malformed.update({"issue": [], "gate": "gate", "lanes": None})
    malformed["human_reviews"] = 42
    assert validate_record(malformed)


def test_lane_shas_are_full_and_implementation_starts_from_exact_base():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["lanes"]["test_sha"] = "abc1234"
    record["lanes"]["candidate_sha"] = None
    record["lanes"]["implementation_base_sha"] = "f" * 40

    errors = validate_record(record)

    assert any("lanes.test_sha" in error and "40" in error for error in errors)
    assert any("lanes.candidate_sha" in error and "40" in error for error in errors)
    assert any("lanes.implementation_base_sha must equal lanes.base_sha" in error for error in errors)


def test_test_human_review_requires_exact_github_issue_comment_evidence():
    validate_record = _load_gate().validate_record
    mutations = {
        "bound SHA": ("sha", "f" * 40),
        "human reviewer": ("reviewer", ""),
        "GitHub provider": ("evidence.provider", "gitlab"),
        "repository": ("evidence.repository", ""),
        "matching issue": ("evidence.issue_number", ISSUE_NUMBER + 1),
        "comment ID": ("evidence.comment_id", None),
        "exact command": ("evidence.command", "/approve-test b583f0a"),
        "stopped monitor": ("monitor.status", "polling"),
        "10 minute monitor": ("monitor.interval_minutes", 5),
        "current session": ("monitor.scope", "new_session"),
    }

    for label, (path, value) in mutations.items():
        record = _complete_record()
        target = record["human_reviews"]["test"]
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
        assert any(
            "human_reviews.test" in error for error in validate_record(record)
        ), label


def test_implementing_requires_approved_test_when_gate_requires_tests():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["state"] = "implementing"
    record["human_reviews"]["test"]["approved"] = False

    assert any(
        "human_reviews.test.approved" in error for error in validate_record(record)
    )

    record["gate"]["test_required"] = "yes"
    assert any("gate.test_required" in error for error in validate_record(record))


def test_light_path_is_limited_to_n_do_and_records_remaining_verification():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["issue"] = {
        "number": ISSUE_NUMBER,
        "repository": "org/example-repository",
        "primary_type": "N",
        "impact_flags": ["DO"],
    }
    record["gate"] = {
        "test_required": False,
        "light_path": {
            "reason": "Normalize whitespace only.",
            "residual_risk": "Rendered text may wrap differently.",
            "remaining_verification": ["Render the changed Markdown."],
        },
    }
    record["human_reviews"]["test"] = {
        "approved": False,
        "sha": None,
        "reviewer": None,
        "evidence": None,
        "monitor": None,
    }
    assert validate_record(record) == []

    record["issue"]["impact_flags"] = ["DO", "PB"]
    record["gate"]["light_path"]["remaining_verification"] = ["", 7]
    errors = validate_record(record)
    assert any("gate.light_path" in error and "eligible" in error for error in errors)
    assert any("gate.light_path.remaining_verification[0]" in error for error in errors)
    assert any("gate.light_path.remaining_verification[1]" in error for error in errors)


def test_light_path_ignores_the_entire_stale_human_review_1_block():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["issue"] = {
        "number": ISSUE_NUMBER,
        "repository": "org/example-repository",
        "primary_type": "N",
        "impact_flags": ["DO"],
    }
    record["gate"] = {
        "test_required": False,
        "light_path": {
            "reason": "Normalize one mechanical representation.",
            "residual_risk": "A textual marker could move.",
            "remaining_verification": ["Review the normalized file."],
        },
    }
    record["human_reviews"]["test"] = {
        "approved": "stale-template",
        "sha": "not-a-sha",
        "reviewer": "",
        "evidence": {
            "provider": "stale-provider",
            "repository": "",
            "issue_number": ISSUE_NUMBER + 9,
            "comment_id": None,
            "command": "/approve-test stale",
            "edited": True,
            "deleted": True,
            "request_changes": True,
        },
        "monitor": {
            "status": "polling",
            "interval_minutes": 1,
            "scope": "another_session",
        },
    }

    assert validate_record(record) == []


def test_each_counter_has_its_own_zero_to_three_error():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["counters"] = {"production_rework": 4, "kpi_optimization": -1}

    errors = validate_record(record)

    assert any("counters.production_rework" in error and "0..3" in error for error in errors)
    assert any("counters.kpi_optimization" in error and "0..3" in error for error in errors)


def test_candidate_bound_tester_and_reviewer_evidence_controls_reviewing():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["state"] = "reviewing"
    record["tester"] = {"status": "fail", "candidate_sha": "e" * 40}
    record["reviewer"] = {"status": "pass", "candidate_sha": "d" * 40}

    errors = validate_record(record)

    assert any("state reviewing requires tester.status pass" in error for error in errors)
    assert any("reviewer.status pass requires tester.status pass" in error for error in errors)
    assert any("tester.candidate_sha must equal lanes.candidate_sha" in error for error in errors)
    assert any("reviewer.candidate_sha must equal lanes.candidate_sha" in error for error in errors)


def test_complete_requires_final_review_bound_to_current_candidate():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["human_reviews"]["final"].update(
        {"approved": False, "sha": "f" * 40, "reviewer": ""}
    )
    record["human_reviews"]["final"]["monitor"] = {
        "status": "polling",
        "interval_minutes": 9,
        "scope": "another_session",
    }
    record["reviewer"]["status"] = "fail"

    errors = validate_record(record)

    assert any("complete requires reviewer.status pass" in error for error in errors)
    assert any("human_reviews.final.approved" in error for error in errors)
    assert any("human_reviews.final.sha must equal lanes.candidate_sha" in error for error in errors)
    assert any("human_reviews.final.reviewer" in error for error in errors)
    assert any("human_reviews.final.monitor.status" in error for error in errors)
    assert any("human_reviews.final.monitor.interval_minutes" in error for error in errors)
    assert any("human_reviews.final.monitor.scope" in error for error in errors)


def test_non_null_exception_reports_every_missing_or_invalid_item():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["exception"] = {
        "reason": "",
        "residual_risk": None,
        "remaining_verification": ["Check generated evidence.", "", 3],
    }

    errors = validate_record(record)

    assert any("exception.reason" in error for error in errors)
    assert any("exception.residual_risk" in error for error in errors)
    assert any("exception.remaining_verification[1]" in error for error in errors)
    assert any("exception.remaining_verification[2]" in error for error in errors)


def test_diagnostics_include_stable_human_readable_engineering_concepts():
    validate_record = _load_gate().validate_record
    cases = []

    record = _complete_record()
    record["issue"]["primary_type"] = "?"
    cases.append(("primary type", record))

    record = _complete_record()
    record["issue"]["impact_flags"] = ["?"]
    cases.append(("impact flag", record))

    record = _complete_record()
    record["human_reviews"]["test"]["approved"] = False
    cases.append(("Human Review 1", record))

    record = _complete_record()
    record["human_reviews"]["test"]["evidence"]["command"] = "invalid"
    cases.append(("approval command", record))

    record = _complete_record()
    record["human_reviews"]["test"]["evidence"]["comment_id"] = None
    cases.append(("comment ID", record))

    record = _complete_record()
    record["human_reviews"]["test"]["monitor"]["scope"] = "new_session"
    cases.append(("current session", record))

    record = _complete_record()
    record["counters"]["production_rework"] = 4
    cases.append(("production rework", record))

    record = _complete_record()
    record["counters"]["kpi_optimization"] = 4
    cases.append(("KPI optimization", record))

    record = _complete_record()
    record["exception"] = {
        "reason": "Exceptional processing is required.",
        "residual_risk": "",
        "remaining_verification": ["Inspect evidence."],
    }
    cases.append(("residual risk", record))

    record = _complete_record()
    record["exception"] = {
        "reason": "Exceptional processing is required.",
        "residual_risk": "An approval may become stale.",
        "remaining_verification": [],
    }
    cases.append(("remaining verification", record))

    record = _complete_record()
    record["state"] = "reviewing"
    record["tester"]["status"] = "fail"
    record["reviewer"]["status"] = "pending"
    cases.append(("Tester pass", record))

    record = _complete_record()
    record["human_reviews"]["final"]["approved"] = False
    cases.append(("Final Human Review", record))

    for concept, invalid_record in cases:
        errors = validate_record(invalid_record)
        joined = "\n".join(errors).lower()
        assert concept.lower() in joined, (concept, errors)


def test_ordinary_bad_top_level_inputs_return_errors_instead_of_raising():
    validate_record = _load_gate().validate_record

    for value in (None, [], "record", 42):
        errors = validate_record(value)
        assert isinstance(errors, list)
        assert errors
        assert "mapping" in errors[0]


def test_ordinary_bad_nested_scalar_types_return_errors_instead_of_raising():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["tester"]["status"] = []
    record["reviewer"]["status"] = {}

    errors = validate_record(record)

    assert any("tester.status" in error for error in errors)
    assert any("reviewer.status" in error for error in errors)


def test_canonical_bad_container_members_report_errors_without_raising():
    gate = _load_gate()
    previous = _canonical_record("testing")
    current = _canonical_record("reviewing")
    current["transition"]["to"] = []
    current["transition"]["event"] = []
    current["revisions"]["test"]["sha"] = {}
    current["revisions"]["candidate"]["parents"] = [{}]
    current["revisions"]["evidence"] = {
        "id": "E3",
        "sha": EVIDENCE_SHA,
        "parent_sha": CANDIDATE_SHA,
        "base_candidate_sha": CANDIDATE_SHA,
        "kind": "evidence_only",
        "changed_paths": [{}],
    }

    assert gate.validate_record(current)
    assert gate.validate_transition(previous, current)


def test_contract_exposes_executable_transitions_routing_corrections_and_handoffs():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    transitions = {
        (item["from"], item["to"], item["event"])
        for item in contract["state_machine"]["transitions"]
    }
    assert ("implementing", "candidate", "candidate_created") in transitions
    assert ("candidate", "testing", "testing_started") in transitions
    assert ("testing", "reviewing", "tester_passed") in transitions
    assert ("testing", "rework", "tester_failed") in transitions
    assert ("rework", "implementing", "production_rework") in transitions
    assert ("rework", "stopped", "production_rework") in transitions
    assert ("human_review_1", "test_authoring", "changes_requested") in transitions
    assert "stopped" in contract["state_machine"]["terminal_states"]

    assert set(contract["impact_routing"]) == {
        item["code"] for item in contract["impact_flags"]
    }
    assert contract["correction_classes"]["production_rework"]["consumes"] == (
        "limits.production_rework"
    )
    assert contract["correction_classes"]["dependency_permission"]["consumes"] is None
    assert contract["correction_classes"]["test_contract"]["consumes"] is None

    templates = contract["handoff_templates"]
    assert set(templates) == {"orchestrator", "explorer", "worker", "tester", "reviewer"}
    for template in templates.values():
        assert set(template) == {
            "inputs", "forbidden", "outputs", "stop_conditions", "acceptance"
        }
        assert all(template.values())
        assert any("#/" in item for values in template.values() for item in values)


def test_impact_flags_derive_gates_and_reject_a_self_declared_bypass():
    gate = _load_gate()

    derived = gate.derive_gate_profile("M", ["MW", "VS", "SS"])
    assert derived == {
        "test_required": True,
        "required_gates": [
            "deterministic_tests",
            "safety_security_review",
            "static_runtime_checks",
            "vendor_validation",
        ],
        "profiles": ["mex_write", "safety_critical", "vendor"],
    }

    record = _canonical_record()
    record["gate"]["test_required"] = False
    record["gate"]["light_path"] = {
        "reason": "Claimed bypass.",
        "residual_risk": "Behavior may be untested.",
        "remaining_verification": ["Run the required tests."],
    }
    assert any("derived" in error for error in gate.validate_record(record))


def test_state_dependent_records_do_not_require_future_evidence_and_reject_it():
    validate_record = _load_gate().validate_record
    record = _canonical_record("testing")

    assert validate_record(record) == []

    record["human_reviews"]["final"] = _canonical_record()["human_reviews"]["final"]
    errors = validate_record(record)
    assert any("human_reviews.final" in error and "future" in error for error in errors)


def test_canonical_light_path_ignores_the_entire_stale_gate_1_block():
    record = _canonical_record()
    record["issue"] = {
        "number": ISSUE_NUMBER,
        "repository": "org/example-repository",
        "primary_type": "N",
        "impact_flags": ["DO"],
    }
    record["gate"] = {
        "test_required": False,
        "light_path": {
            "reason": "Normalize one documentation marker.",
            "residual_risk": "The rendered marker may move.",
            "remaining_verification": ["Render the changed document."],
        },
        "required_gates": ["documentation_review"],
        "profiles": ["documentation"],
    }
    record["revisions"]["test"] = None
    record["revisions"]["candidate"].pop("test_revision")
    record["revisions"]["candidate"]["parents"] = [IMPLEMENTATION_SHA]
    record["human_reviews"]["test"] = {
        "decision": "stale",
        "approved": "not-a-boolean",
        "sha": "not-a-sha",
        "reviewer": "",
        "evidence": {"repository": "stale/repository"},
    }

    assert _load_gate().validate_record(record) == []


def test_classify_state_requires_no_future_lanes_reviews_or_results():
    record = {
        "version": 1,
        "issue": {
            "number": ISSUE_NUMBER,
            "repository": "org/example-repository",
            "primary_type": "B",
            "impact_flags": ["PB"],
        },
        "state": "classify",
        "transition": None,
    }

    assert _load_gate().validate_record(record) == []


def test_pass_sequence_accepts_each_snapshot_without_later_evidence():
    validate_record = _load_gate().validate_record
    records = []

    test_authoring = _canonical_record()
    test_authoring["state"] = "test_authoring"
    test_authoring["transition"] = {
        "from": "classify", "to": "test_authoring", "event": "classified"
    }
    test_authoring["revisions"]["test"] = {
        "id": "T4", "sha": None, "base_sha": BASE_SHA
    }
    test_authoring["revisions"]["implementation"] = None
    test_authoring["revisions"]["candidate"] = None
    test_authoring["human_reviews"] = {"test": None, "final": None}
    test_authoring["tester"] = None
    test_authoring["reviewer"] = None
    records.append(("test_authoring", test_authoring))

    human_review = deepcopy(test_authoring)
    human_review["state"] = "human_review_1"
    human_review["transition"] = {
        "from": "test_authoring", "to": "human_review_1", "event": "test_ready"
    }
    human_review["revisions"]["test"]["sha"] = TEST_SHA
    human_review["human_reviews"]["test"] = {
        "decision": "pending", "approved": False, "sha": TEST_SHA
    }
    records.append(("human_review_1", human_review))

    implementing = _canonical_record()
    implementing["state"] = "implementing"
    implementing["transition"] = {
        "from": "human_review_1",
        "to": "implementing",
        "event": "test_approved",
    }
    implementing["revisions"]["implementation"]["sha"] = None
    implementing["revisions"]["candidate"] = None
    implementing["human_reviews"]["final"] = None
    implementing["tester"] = None
    implementing["reviewer"] = None
    records.append(("implementing", implementing))

    candidate = _canonical_record()
    candidate["state"] = "candidate"
    candidate["transition"] = {
        "from": "implementing",
        "to": "candidate",
        "event": "implementation_ready",
    }
    candidate["human_reviews"]["final"] = None
    candidate["tester"] = None
    candidate["reviewer"] = None
    records.append(("candidate", candidate))

    final_review = _canonical_record()
    final_review["state"] = "final_human_review"
    final_review["transition"] = {
        "from": "reviewing",
        "to": "final_human_review",
        "event": "review_pass",
    }
    final_review["human_reviews"]["final"] = {
        "decision": "pending",
        "approved": False,
        "sha": CANDIDATE_SHA,
    }
    records.append(("final_human_review", final_review))

    for label, record in records:
        assert validate_record(record) == [], label


def test_revision_provenance_binds_exact_lane_bases_candidate_parents_and_ids():
    validate_record = _load_gate().validate_record
    mutations = {
        "test base": ("test", "base_sha", "f" * 40),
        "implementation base": ("implementation", "base_sha", "e" * 40),
        "test identity": ("test", "id", "W4"),
        "implementation identity": ("implementation", "id", "T6"),
        "candidate identity": ("candidate", "id", "C0"),
        "candidate test reference": ("candidate", "test_revision", "T9"),
        "candidate implementation reference": (
            "candidate", "implementation_revision", "W2"
        ),
        "candidate parents": ("candidate", "parents", [TEST_SHA, "d" * 40]),
        "candidate tree": ("candidate", "tree_sha", "short"),
    }

    for label, (section, field, value) in mutations.items():
        record = _canonical_record()
        record["revisions"][section][field] = value
        assert any(
            f"revisions.{section}.{field}" in error
            for error in validate_record(record)
        ), label


def test_evidence_only_revision_is_narrowly_allowlisted_and_final_review_binds_it():
    validate_record = _load_gate().validate_record
    record = _canonical_record()
    record["revisions"]["evidence"] = {
        "id": "E2",
        "sha": EVIDENCE_SHA,
        "parent_sha": CANDIDATE_SHA,
        "base_candidate_sha": CANDIDATE_SHA,
        "kind": "evidence_only",
        "changed_paths": ["agent-discipline/agent-lessons-learned.md"],
    }
    record["human_reviews"]["final"]["sha"] = EVIDENCE_SHA
    record["human_reviews"]["final"]["evidence"]["revision_sha"] = EVIDENCE_SHA
    assert validate_record(record) == []

    record["revisions"]["evidence"]["changed_paths"] = [
        "agent-discipline/workflow-contract.json",
        "src/production.py",
    ]
    errors = validate_record(record)
    assert any("evidence-only allowlist" in error for error in errors)


def test_human_review_provenance_requires_current_authorized_github_artifacts():
    validate_record = _load_gate().validate_record
    mutations = {
        "top-level Gate 1": ("test", "evidence", "top_level", False),
        "Gate 1 actor": ("test", "evidence", "actor", "someone-else"),
        "Gate 1 repository": (
            "test", "evidence", "repository", "another/repository"
        ),
        "Gate 1 authorization": ("test", "evidence", "authorized_actor", False),
        "Gate 1 revision": ("test", "evidence", "revision_sha", "f" * 40),
        "Final artifact": ("final", "evidence", "artifact", "issue_comment"),
        "Final PR": ("final", "evidence", "pull_request_number", None),
        "Final review": ("final", "evidence", "review_id", None),
        "Final actor": ("final", "evidence", "actor", "someone-else"),
        "Final repository": (
            "final", "evidence", "repository", "another/repository"
        ),
        "Final state": ("final", "evidence", "state", "CHANGES_REQUESTED"),
        "Final stale": ("final", "evidence", "stale", True),
    }

    for label, (review, group, field, value) in mutations.items():
        record = _canonical_record()
        record["human_reviews"][review][group][field] = value
        assert any(
            f"human_reviews.{review}.evidence.{field}" in error
            for error in validate_record(record)
        ), label


def test_legal_transitions_separate_rework_and_test_contract_corrections():
    gate = _load_gate()
    previous = _canonical_record("testing")
    previous["tester"]["status"] = "fail"
    current = deepcopy(previous)
    current["state"] = "rework"
    current["transition"] = {
        "from": "testing",
        "to": "rework",
        "event": "functional_failure",
    }
    assert gate.validate_transition(previous, current) == []

    implementation = deepcopy(current)
    implementation["state"] = "implementing"
    implementation["transition"] = {
        "from": "rework",
        "to": "implementing",
        "event": "production_rework",
    }
    implementation["corrections"]["production_rework"]["count"] = 2
    implementation["revisions"]["implementation"] = {
        "id": "W7", "sha": None, "base_sha": BASE_SHA
    }
    implementation["revisions"]["candidate"] = None
    implementation["tester"] = None
    assert gate.validate_transition(current, implementation) == []

    implementation["corrections"]["production_rework"]["count"] = 1
    assert any(
        "production_rework.count must increment" in error
        for error in gate.validate_transition(current, implementation)
    )


def test_transition_events_require_the_outcome_recorded_in_the_source_state():
    gate = _load_gate()
    previous = _canonical_record("testing")
    current = _canonical_record("reviewing")

    errors = gate.validate_transition(previous, current)
    assert any("functional_pass requires previous tester.status pass" in error for error in errors)

    previous["tester"]["status"] = "pass"
    assert gate.validate_transition(previous, current) == []


def test_candidate_cannot_change_outside_candidate_creation_transition():
    gate = _load_gate()
    previous = _canonical_record("testing")
    previous["tester"]["status"] = "pass"
    current = _canonical_record("reviewing")
    replacement = "3" * 40
    current["revisions"]["candidate"]["sha"] = replacement
    current["tester"]["candidate_sha"] = replacement
    current["reviewer"]["candidate_sha"] = replacement

    errors = gate.validate_transition(previous, current)
    assert any("Candidate may change only" in error for error in errors)


def test_gate_1_change_request_creates_next_test_revision_without_rework_count():
    gate = _load_gate()
    previous = _canonical_record()
    previous["state"] = "human_review_1"
    previous["transition"] = {
        "from": "test_authoring", "to": "human_review_1", "event": "test_ready"
    }
    review = previous["human_reviews"]["test"]
    review["decision"] = "changes_requested"
    review["approved"] = False
    review["evidence"]["command"] = (
        f"/request-test-changes {TEST_SHA}\nCover arbitrary partition counts."
    )
    review["evidence"]["request_changes"] = True
    review["evidence"]["reason"] = "Cover arbitrary partition counts."
    previous["revisions"]["implementation"] = None
    previous["revisions"]["candidate"] = None
    previous["tester"] = None
    previous["reviewer"] = None
    previous["human_reviews"]["final"] = None

    current = deepcopy(previous)
    current["state"] = "test_authoring"
    current["transition"] = {
        "from": "human_review_1",
        "to": "test_authoring",
        "event": "changes_requested",
    }
    current["revisions"]["test"] = {
        "id": "T5", "sha": None, "base_sha": BASE_SHA
    }
    current["human_reviews"]["test"] = None
    current["corrections"]["test_contract"]["count"] = 2
    current["corrections"]["test_contract"]["audit"].append(
        "TC2: maintainer requested broader Test coverage."
    )

    assert gate.validate_transition(previous, current) == []
    assert current["corrections"]["production_rework"]["count"] == 1


def test_production_rework_cap_requires_stopped_escalation_disposition():
    validate_record = _load_gate().validate_record
    third_attempt = _canonical_record("testing")
    third_attempt["corrections"]["production_rework"] = {
        "count": 3, "disposition": "at_limit"
    }
    assert validate_record(third_attempt) == []

    record = _canonical_record("testing")
    record["state"] = "rework"
    record["transition"] = {
        "from": "testing", "to": "rework", "event": "functional_failure"
    }
    record["tester"]["status"] = "fail"
    record["corrections"]["production_rework"] = {
        "count": 3, "disposition": "continue"
    }
    assert any("stop_escalate" in error for error in validate_record(record))

    record["state"] = "stopped"
    record["transition"] = {
        "from": "rework", "to": "stopped", "event": "rework_cap_reached"
    }
    record["corrections"]["production_rework"]["disposition"] = "stop_escalate"
    record["stop"] = {
        "disposition": "stop_escalate",
        "reason": "Three automatic production reworks were consumed.",
    }
    assert validate_record(record) == []


def test_correction_audit_cardinality_must_match_nonproduction_counts():
    record = _canonical_record()
    record["corrections"]["dependency_permission"]["audit"] = [
        "Only one of two corrections is auditable."
    ]

    errors = _load_gate().validate_record(record)
    assert any("dependency_permission.audit" in error for error in errors)


def test_category_a_active_text_is_functional_and_not_agent_governance():
    paths = [
        Path("docs/tests/rtd-config-test-strategy.md"),
        Path("docs/tests/rtd-config-test-cases.md"),
        Path("docs/tests/rtd-config-acceptance-report.md"),
    ]
    active = "\n".join(
        path.read_text(encoding="utf-8").split("## Changelog", 1)[0]
        for path in paths
    ).lower()

    assert "autonomous agent workflow" not in active
    assert "assumed of every agent" not in active
    assert "agent-runner" not in active
    assert "agent-discipline" not in active
    assert "agents.md" not in active
    assert "sufficient to accept" not in active
    assert "sufficient to be accepted" not in active
    assert "green gate demonstrates" not in active
    assert "a green gate accepts" not in active


def test_cli_emits_json_and_exit_2_for_input_or_invocation_errors():
    commands = [
        ([sys.executable, str(GATE_PATH), "--json", "-"], b"{not-json"),
        ([sys.executable, str(GATE_PATH), "--json", "-"], b"\xff"),
        (
            [sys.executable, str(GATE_PATH), "--json", "tests/.tmp/does-not-exist.json"],
            None,
        ),
        ([sys.executable, str(GATE_PATH)], None),
    ]

    for command, payload in commands:
        result = subprocess.run(command, input=payload, capture_output=True, check=False)
        assert result.returncode == 2
        body = json.loads(result.stdout.decode("utf-8"))
        assert body["ok"] is False
        assert body["error_type"] == "input"
        assert body["errors"]
        assert b"Traceback" not in result.stderr


PUBLIC_STATES = [
    "classify",
    "test_authoring",
    "human_review_1",
    "implementing",
    "candidate",
    "testing",
    "rework",
    "reviewing",
    "final_human_review",
    "complete",
    "stopped",
]


def _public_test_revision(iteration: int = 2, sha: str | None = TEST_SHA):
    return {
        "identity": f"T{iteration}",
        "iteration": iteration,
        "base_sha": BASE_SHA,
        "sha": sha,
    }


def _public_implementation_revision(
    iteration: int = 3, sha: str | None = IMPLEMENTATION_SHA
):
    return {
        "identity": f"W{iteration}",
        "iteration": iteration,
        "base_sha": BASE_SHA,
        "sha": sha,
    }


def _public_candidate_revision(
    iteration: int = 4, sha: str = CANDIDATE_SHA
):
    return {
        "identity": f"C{iteration}",
        "iteration": iteration,
        "sha": sha,
        "parents": {
            "test_sha": TEST_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
        },
    }


def _public_test_review(decision: str = "approved"):
    reason = "Exercise arbitrary channel and partition counts."
    requested = decision == "changes_requested"
    command = (
        f"/request-test-changes {TEST_SHA}\n{reason}"
        if requested
        else f"/approve-test {TEST_SHA}"
    )
    evidence = {
        "provider": "github",
        "artifact": "issue_comment",
        "repository": "org/example-repository",
        "issue_number": ISSUE_NUMBER,
        "comment_id": 9876,
        "command": command,
        "test_sha": TEST_SHA,
        "top_level": True,
        "actor_type": "human",
        "current": True,
        "edited": False,
        "deleted": False,
        "requested_changes": False,
    }
    if requested:
        evidence["decision"] = "changes_requested"
        evidence["reason"] = reason
    return {
        "approved": not requested,
        "sha": TEST_SHA,
        "reviewer": "human-reviewer",
        "evidence": evidence,
        "monitor": {
            "status": "stopped",
            "interval_minutes": 10,
            "scope": "current_session",
        },
    }


def _public_final_review(candidate_sha: str = CANDIDATE_SHA):
    return {
        "approved": True,
        "sha": candidate_sha,
        "reviewer": "human-reviewer",
        "evidence": {
            "provider": "github",
            "artifact": "pull_request_review",
            "repository": "org/example-repository",
            "pull_request_number": 456,
            "review_id": 6543,
            "actor_type": "human",
            "state": "approved",
            "current": True,
            "candidate_sha": candidate_sha,
        },
        "monitor": {
            "status": "stopped",
            "interval_minutes": 10,
            "scope": "current_session",
        },
    }


def _public_record(state: str) -> dict[str, object]:
    record = {
        "version": 1,
        "issue": {
            "number": ISSUE_NUMBER,
            "primary_type": "B",
            "impact_flags": ["PB"],
        },
        "state": state,
        "gate": {"test_required": True},
        "revisions": {"base_sha": BASE_SHA},
        "counters": {"production_rework": 1, "kpi_optimization": 0},
        "exception": None,
    }
    revisions = record["revisions"]
    if state in PUBLIC_STATES[1:]:
        revisions["test"] = _public_test_revision(
            sha=None if state == "test_authoring" else TEST_SHA
        )
    if state in PUBLIC_STATES[3:]:
        revisions["implementation"] = _public_implementation_revision(
            sha=None if state == "implementing" else IMPLEMENTATION_SHA
        )
        record["human_reviews"] = {"test": _public_test_review()}
    if state in PUBLIC_STATES[4:]:
        revisions["candidate"] = _public_candidate_revision()
    if state == "testing":
        record["tester"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    elif state == "rework":
        record["tester"] = {"status": "fail", "candidate_sha": CANDIDATE_SHA}
    elif state in {"reviewing", "final_human_review", "complete"}:
        record["tester"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}
    if state == "reviewing":
        record["reviewer"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    elif state in {"final_human_review", "complete"}:
        record["reviewer"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}
    if state == "final_human_review":
        record.setdefault("human_reviews", {})["final"] = {
            "monitor": {
                "status": "active",
                "interval_minutes": 10,
                "scope": "current_session",
            }
        }
    elif state == "complete":
        record.setdefault("human_reviews", {})["final"] = _public_final_review()
    if state == "stopped":
        record["disposition"] = {
            "status": "stop_escalate",
            "reason": "The automatic production-rework cap was reached.",
        }
    return record


def _delete_path(record: dict[str, object], path: str) -> None:
    parts = path.split(".")
    target = record
    for part in parts[:-1]:
        target = target[part]
    target.pop(parts[-1], None)


def _set_path(record: dict[str, object], path: str, value: object) -> None:
    parts = path.split(".")
    target = record
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def test_public_contract_states_drive_required_and_forbidden_record_paths():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    states = contract["state_machine"]["states"]
    assert [item["name"] for item in states] == PUBLIC_STATES
    probes = {
        "classify": "issue.primary_type",
        "test_authoring": "revisions.test.identity",
        "human_review_1": "revisions.test.sha",
        "implementing": "human_reviews.test.evidence",
        "candidate": "revisions.candidate.parents",
        "testing": "tester.candidate_sha",
        "rework": "tester.status",
        "reviewing": "tester.candidate_sha",
        "final_human_review": "reviewer.candidate_sha",
        "complete": "human_reviews.final.evidence",
        "stopped": "disposition.status",
    }
    for state in states:
        assert state["required_fields"]
        assert isinstance(state["forbidden_fields"], list)
        assert set(state["required_fields"]).isdisjoint(state["forbidden_fields"])
        assert probes[state["name"]] in state["required_fields"]


def test_minimal_record_for_every_public_state_is_valid_and_rules_are_executable():
    gate = _load_gate()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    state_rules = {item["name"]: item for item in contract["state_machine"]["states"]}
    forbidden_value = "f" * 40

    for state in PUBLIC_STATES:
        record = _public_record(state)
        before = deepcopy(record)
        assert gate.validate_record(record) == [], state
        assert record == before

        for required in state_rules[state]["required_fields"]:
            missing = deepcopy(record)
            _delete_path(missing, required)
            assert any(required in error for error in gate.validate_record(missing))

        for forbidden in state_rules[state]["forbidden_fields"]:
            illegal = deepcopy(record)
            _set_path(illegal, forbidden, forbidden_value)
            assert any(forbidden in error for error in gate.validate_record(illegal))


def test_public_revision_graph_and_routing_have_exact_shape_and_derivation():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["revision_graph"] == {
        "identities": {
            "test": "T{iteration}",
            "implementation": "W{iteration}",
            "candidate": "C{iteration}",
        },
        "shared_base": [
            "test.base_sha",
            "implementation.base_sha",
        ],
        "candidate_parents": [
            "test.sha",
            "implementation.sha",
        ],
        "final_evidence_revision": {
            "reviewed_object": "candidate.sha",
            "evidence_only": True,
            "allowed_paths": ["agent-discipline/agent-lessons-learned.md"],
            "production_paths_allowed": False,
        },
    }
    routing = contract["routing"]["impact_flags"]
    assert list(routing) == ["PB", "MS", "MW", "RA", "TC", "VS", "EV", "AR", "RP", "ED", "SS", "DO"]
    assert all(item["required_gates"] and item["profiles"] for item in routing.values())
    flags = ["SS", "PB", "MW"]
    assert _load_gate().derive_routing(flags) == {
        "required_gates": sorted(
            {gate for flag in flags for gate in routing[flag]["required_gates"]}
        ),
        "profiles": sorted(
            {profile for flag in flags for profile in routing[flag]["profiles"]}
        ),
    }


def test_public_forward_transitions_use_approved_events():
    gate = _load_gate()
    sequence = [
        ("classify", "test_authoring", "classification_complete"),
        ("test_authoring", "human_review_1", "test_frozen"),
        ("human_review_1", "implementing", "test_approved"),
        ("implementing", "candidate", "candidate_created"),
        ("candidate", "testing", "testing_started"),
        ("testing", "reviewing", "tester_passed"),
        ("reviewing", "final_human_review", "reviewer_passed"),
        ("final_human_review", "complete", "final_approved"),
    ]
    for source, target, event in sequence:
        previous = _public_record(source)
        current = _public_record(target)
        if source == "testing":
            previous["tester"]["status"] = "pass"
        assert gate.validate_transition(previous, current, event) == [], event


def test_public_special_transitions_preserve_counters_and_revision_iterations():
    gate = _load_gate()

    previous = _public_record("human_review_1")
    previous["human_reviews"] = {"test": _public_test_review("changes_requested")}
    current = _public_record("test_authoring")
    current["revisions"]["test"] = _public_test_revision(3, None)
    assert gate.validate_transition(previous, current, "changes_requested") == []

    previous = _public_record("testing")
    previous["tester"]["status"] = "fail"
    current = _public_record("rework")
    assert gate.validate_transition(previous, current, "tester_failed") == []

    for event in ("dependency_blocked", "permission_blocked"):
        previous = _public_record("implementing")
        current = deepcopy(previous)
        assert gate.validate_transition(previous, current, event) == []

        previous = _public_record("rework")
        current = deepcopy(previous)
        assert gate.validate_transition(previous, current, event) == []

    previous = _public_record("rework")
    current = _public_record("implementing")
    current["counters"]["production_rework"] = 2
    current["revisions"]["implementation"] = _public_implementation_revision(4, None)
    assert gate.validate_transition(previous, current, "production_rework") == []

    previous = _public_record("rework")
    previous["counters"]["production_rework"] = 3
    current = _public_record("stopped")
    current["counters"]["production_rework"] = 3
    assert gate.validate_transition(previous, current, "production_rework") == []

    current["revisions"]["implementation"] = _public_implementation_revision(4)
    assert any(
        "fourth" in error or "revisions" in error
        for error in gate.validate_transition(previous, current, "production_rework")
    )


def test_candidate_revised_requires_new_candidate_and_reset_results():
    gate = _load_gate()
    previous = _public_record("reviewing")
    current = _public_record("testing")
    new_sha = "7" * 40
    current["revisions"]["candidate"] = _public_candidate_revision(5, new_sha)
    current["tester"] = {"status": "pending", "candidate_sha": new_sha}
    current["reviewer"] = {"status": "not_run", "candidate_sha": new_sha}
    assert gate.validate_transition(previous, current, "candidate_revised") == []

    current["reviewer"]["status"] = "pass"
    assert any("reviewer.status" in error for error in gate.validate_transition(previous, current, "candidate_revised"))


def test_public_human_review_contract_and_evidence_are_exact():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    gate_1 = contract["state_machine"]["human_review_1"]["evidence"]
    assert gate_1["change_request_command"] == "/request-test-changes {test_sha}\n{reason}"
    final = contract["state_machine"]["final_human_review"]["evidence"]
    assert final["provider"] == "github"
    assert final["artifact"] == "pull_request_review"
    assert final["binds"] == "candidate_sha"
    assert final["authorized_actor"] == "human"
    assert {"repository", "pull_request_number", "review_id", "state", "candidate_sha"} <= set(final["required_fields"])
    assert {"candidate_sha_change", "review_edit", "review_dismissal", "request_changes"} <= set(final["invalidated_by"])

    validate_record = _load_gate().validate_record
    for review_name, field, value in (
        ("test", "top_level", False),
        ("test", "actor_type", "agent"),
        ("test", "current", False),
        ("final", "actor_type", "agent"),
        ("final", "state", "changes_requested"),
        ("final", "current", False),
        ("final", "candidate_sha", "8" * 40),
    ):
        record = _public_record("complete")
        record["human_reviews"][review_name]["evidence"][field] = value
        assert any(field in error for error in validate_record(record))


def test_public_minimal_issue_and_outer_review_shape_are_authoritative():
    validate_record = _load_gate().validate_record
    classify = _public_record("classify")
    assert set(classify["issue"]) == {"number", "primary_type", "impact_flags"}
    assert validate_record(classify) == []

    complete = _public_record("complete")
    test_review = complete["human_reviews"]["test"]
    final_review = complete["human_reviews"]["final"]
    assert "decision" not in test_review
    assert "decision" not in final_review
    assert test_review["approved"] is True
    assert test_review["sha"] == TEST_SHA
    assert final_review["approved"] is True
    assert final_review["sha"] == CANDIDATE_SHA
    assert validate_record(complete) == []

    complete["issue"]["repository"] = "org/example-repository"
    complete["issue"]["pull_request_number"] = 456
    assert validate_record(complete) == []


def test_public_change_request_uses_only_its_approved_extra_fields():
    record = _public_record("human_review_1")
    record["human_reviews"] = {"test": _public_test_review("changes_requested")}
    assert record["human_reviews"]["test"]["approved"] is False
    evidence = record["human_reviews"]["test"]["evidence"]
    assert evidence["decision"] == "changes_requested"
    assert evidence["requested_changes"] is False
    assert evidence["command"] == f"/request-test-changes {TEST_SHA}\n{evidence['reason']}"
    assert _load_gate().validate_record(record) == []


def test_pending_gate_1_and_stopped_provenance_are_valid_minimal_states():
    validate_record = _load_gate().validate_record
    pending = _public_record("human_review_1")
    pending["human_reviews"] = {
        "test": {
            "approved": False,
            "sha": TEST_SHA,
            "reviewer": None,
            "evidence": None,
            "monitor": {
                "status": "active",
                "interval_minutes": 10,
                "scope": "current_session",
            },
        }
    }
    assert validate_record(pending) == []

    stopped = _public_record("stopped")
    stopped["counters"]["production_rework"] = 3
    stopped["tester"] = {"status": "fail", "candidate_sha": CANDIDATE_SHA}
    stopped["reviewer"] = {"status": "not_run", "candidate_sha": CANDIDATE_SHA}
    assert validate_record(stopped) == []


def test_public_review_diagnostics_name_the_invalid_concept():
    validate_record = _load_gate().validate_record
    probes = [
        ("test", "issue_number", 999, "issue number"),
        ("test", "comment_id", None, "comment id"),
        ("test", "top_level", False, "top-level"),
        ("test", "actor_type", "automation", "human"),
        ("test", "current", False, "current"),
        ("test", "edited", True, "edited"),
        ("test", "deleted", True, "deleted"),
        ("test", "requested_changes", True, "request"),
        ("final", "pull_request_number", None, "pull request"),
        ("final", "review_id", None, "review id"),
        ("final", "actor_type", "automation", "human"),
        ("final", "state", "pending", "approved"),
        ("final", "candidate_sha", "8" * 40, "candidate"),
    ]
    for review_name, field, value, concept in probes:
        record = _public_record("complete")
        record["human_reviews"][review_name]["evidence"][field] = value
        errors = validate_record(record)
        assert any(concept in error.lower() for error in errors), (field, errors)


def test_final_evidence_revision_is_candidate_bound_and_path_allowlisted():
    validate_record = _load_gate().validate_record
    record = _public_record("complete")
    record["revisions"]["final_evidence"] = {
        "identity": "E9",
        "sha": EVIDENCE_SHA,
        "reviewed_candidate_sha": CANDIDATE_SHA,
        "changed_paths": ["agent-discipline/agent-lessons-learned.md"],
    }
    assert validate_record(record) == []

    record["revisions"]["final_evidence"]["changed_paths"] = [
        "agent-discipline/workflow-contract.json"
    ]
    assert any("changed_paths" in error for error in validate_record(record))


def test_skill_has_bounded_structured_handoff_sections_for_all_roles():
    text = Path("agent-discipline/skills/agent-workflow/SKILL.md").read_text(encoding="utf-8")
    assert "## Handoff templates" in text
    role_markers = {
        "Orchestrator": ["classification", "exact SHA", "human review"],
        "Explorer": ["ground truth", "read-only", "decision-ready"],
        "Worker": ["capability", "acceptance-test implementation", "implementation SHA"],
        "Tester": ["candidate SHA", "production repair", "pass/fail"],
        "Reviewer": ["tester pass", "production write", "lessons"],
    }
    for role, markers in role_markers.items():
        match = re.search(rf"(?ms)^### {role}(?: Handoff)?\s*$\n(.*?)(?=^### |^## |\Z)", text)
        assert match, role
        section = match.group(1)
        assert len(section.split()) <= 220
        for label in ("Inputs", "Forbidden sources", "Forbidden actions", "Outputs", "Stop conditions", "Acceptance criteria"):
            assert label in section
        for marker in markers:
            assert marker.lower() in section.lower()

    assert "/request-test-changes {test_sha}" in text
    assert "{reason}" in text
    assert "two-line" in text.lower() or "exactly two lines" in text.lower()


def test_cli_exact_json_option_and_stable_result_envelope():
    script = str(GATE_PATH)
    valid = _public_record("classify")
    invalid = deepcopy(valid)
    invalid["issue"].pop("primary_type")
    cases = [
        ([sys.executable, script, "--json", "-"], json.dumps(valid).encode(), 0, None),
        ([sys.executable, script, "--json", "-"], json.dumps(invalid).encode(), 1, "validation"),
        ([sys.executable, script, "--json", "-"], b"{bad", 2, "input"),
        ([sys.executable, script, "--json", "-"], b"\xff", 2, "input"),
        ([sys.executable, script, "--json", "tests/.tmp/missing-workflow.json"], None, 2, "input"),
        ([sys.executable, script], None, 2, "input"),
    ]
    for command, payload, returncode, error_type in cases:
        result = subprocess.run(command, input=payload, capture_output=True, check=False)
        assert result.returncode == returncode
        body = json.loads(result.stdout.decode("utf-8"))
        assert body["ok"] is (returncode == 0)
        assert isinstance(body["errors"], list)
        assert body["error_type"] == error_type
        assert b"Traceback" not in result.stdout + result.stderr
