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
# Version:     0.2.0
# Description: Generality tests for the canonical nested Agent workflow record.
# =================================================================================

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)

BASE_SHA = "19a7c4e36d12f5480ab9dc753da236f109e8bc47"
TEST_SHA = "b583f0a1c7d26e4905ab3c81f46d9e27a130bc65"
IMPLEMENTATION_SHA = "6e2a094cb8f713d5a6c9420be1387fd450ac8e31"
CANDIDATE_SHA = "da39b7452c1806b94f56139e827ca1d034e6af72"
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

    assert contract["state_machine"]["final_human_review"] == {
        "before": "complete",
        "binds": "candidate_sha",
        "monitor": "human_review_monitor",
    }
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
