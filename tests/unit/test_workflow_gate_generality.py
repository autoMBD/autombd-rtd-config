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
# Version:     0.1.0
# Description: Generality tests for the canonical Agent workflow record gate.
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


def _load_gate():
    assert GATE_PATH.is_file(), f"missing workflow gate: {GATE_PATH}"
    spec = importlib.util.spec_from_file_location("workflow_gate_generality", GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _comment_evidence(bound_sha: str, command_name: str) -> dict[str, object]:
    return {
        "sha": bound_sha,
        "command": f"/{command_name} {bound_sha}",
        "location": "github_issue_top_level_comment",
        "author_type": "human",
        "comment_id": 1843,
        "comment_url": "https://github.example/org/repository/issues/83#issuecomment-1843",
        "author_login": "maintainer-a",
        "created_at": "2026-04-03T08:12:25Z",
        "edited": False,
        "deleted": False,
    }


def _stopped_monitor() -> dict[str, object]:
    return {
        "window_minutes": 10,
        "same_session": True,
        "new_session": False,
        "status": "stopped",
        "valid_update_received": True,
    }


def _complete_record() -> dict[str, object]:
    return {
        "contract_version": "1.0.0",
        "task_type": "I",
        "impact_flags": ["AR", "TC", "RP"],
        "state": "complete",
        "test_path": "standard",
        "base_sha": BASE_SHA,
        "test_base_sha": BASE_SHA,
        "test_sha": TEST_SHA,
        "implementation_base_sha": BASE_SHA,
        "implementation_sha": IMPLEMENTATION_SHA,
        "candidate_sha": CANDIDATE_SHA,
        "test_approval": _comment_evidence(TEST_SHA, "approve-test"),
        "monitors": {
            "test_review": _stopped_monitor(),
            "final_review": _stopped_monitor(),
        },
        "production_rework_count": 1,
        "kpi_optimization_count": 2,
        "tester_evidence": {
            "verdict": "PASS",
            "candidate_sha": CANDIDATE_SHA,
        },
        "reviewer_evidence": {
            "verdict": "PASS",
            "candidate_sha": CANDIDATE_SHA,
        },
        "final_approval": _comment_evidence(
            CANDIDATE_SHA, "approve-candidate"
        ),
    }


def test_contract_defines_complete_platform_neutral_vocabulary():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["version"] == "1.0.0"
    assert set(contract["task_types"]) == {"M", "B", "W", "T", "D", "N", "I"}
    assert set(contract["impact_flags"]) == {
        "PB",
        "MS",
        "MW",
        "RA",
        "TC",
        "VS",
        "EV",
        "AR",
        "RP",
        "ED",
        "SS",
        "DO",
    }
    assert contract["state_machine"]["sequence"] == [
        "classify",
        "test_authoring",
        "human_review_gate_1",
        "implementing",
        "candidate",
        "tester",
        "rework",
        "reviewer",
        "final_human_review",
        "complete",
    ]
    assert "default_platform" not in json.dumps(contract)


def test_complete_standard_record_is_valid_and_input_is_not_modified():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    before = deepcopy(record)

    assert validate_record(record) == []
    assert record == before


def test_vocabulary_sha_and_lane_failures_are_stable_and_readable():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["task_type"] = "Z"
    record["impact_flags"] = ["AR", "UNKNOWN", "AR"]
    record["test_sha"] = "b583f0a"
    record["implementation_base_sha"] = "f" * 40

    errors = validate_record(record)

    assert errors == sorted(errors)
    assert any("task_type" in error and "Z" in error for error in errors)
    assert any("impact_flags" in error and "UNKNOWN" in error for error in errors)
    assert any("impact_flags" in error and "duplicate" in error for error in errors)
    assert any("test_sha" in error and "40" in error for error in errors)
    assert any("implementation_base_sha must equal base_sha" in error for error in errors)


def test_test_gate_rejects_every_non_authoritative_approval_form():
    validate_record = _load_gate().validate_record
    mutations = {
        "stale SHA": ("sha", "f" * 40),
        "abbreviated command SHA": ("command", "/approve-test b583f0a"),
        "reply": ("location", "github_issue_reply"),
        "agent command": ("author_type", "agent"),
        "edited approval": ("edited", True),
        "deleted approval": ("deleted", True),
    }

    for label, (field, value) in mutations.items():
        record = _complete_record()
        record["test_approval"][field] = value
        errors = validate_record(record)
        assert any("test_approval" in error for error in errors), (label, errors)


def test_monitor_caps_and_lightweight_exception_rules_are_enforced():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["monitors"]["test_review"] = {
        "window_minutes": 9,
        "same_session": False,
        "new_session": True,
        "status": "polling",
        "valid_update_received": True,
    }
    record["production_rework_count"] = 4
    record["kpi_optimization_count"] = 7

    errors = validate_record(record)

    assert any("window_minutes must be 10" in error for error in errors)
    assert any("same_session must be true" in error for error in errors)
    assert any("new_session must be false" in error for error in errors)
    assert any("status must be stopped" in error for error in errors)
    assert any("production_rework_count" in error and "maximum 3" in error for error in errors)
    assert any("kpi_optimization_count" in error and "maximum 3" in error for error in errors)

    lightweight = _complete_record()
    lightweight.update(
        {
            "task_type": "D",
            "impact_flags": ["DO"],
            "test_path": "lightweight",
            "test_base_sha": None,
            "test_sha": None,
            "test_approval": None,
            "monitors": {"final_review": _stopped_monitor()},
            "exception": {
                "reason": "Text-only correction with no executable behavior.",
                "residual_risk": "A stale cross-reference could remain.",
                "remaining_verification": "Review links and render Markdown.",
            },
        }
    )
    assert validate_record(lightweight) == []

    lightweight["exception"]["remaining_verification"] = ""
    assert any(
        "exception.remaining_verification" in error
        for error in validate_record(lightweight)
    )
    lightweight["exception"]["remaining_verification"] = "Review links."
    lightweight["impact_flags"] = ["DO", "PB"]
    assert any("lightweight" in error and "eligible" in error for error in validate_record(lightweight))


def test_human_review_states_require_monitor_configuration():
    validate_record = _load_gate().validate_record
    test_review = _complete_record()
    test_review["state"] = "human_review_gate_1"
    test_review["monitors"] = {}

    assert any(
        "monitors.test_review" in error for error in validate_record(test_review)
    )

    final_review = _complete_record()
    final_review["state"] = "final_human_review"
    final_review["monitors"].pop("final_review")

    assert any(
        "monitors.final_review" in error for error in validate_record(final_review)
    )


def test_reviewer_and_completion_require_candidate_bound_pass_evidence():
    validate_record = _load_gate().validate_record
    record = _complete_record()
    record["tester_evidence"]["verdict"] = "FAIL"
    record["reviewer_evidence"]["candidate_sha"] = "e" * 40
    record["final_approval"]["sha"] = "d" * 40
    record["final_approval"]["command"] = f"/approve-candidate {'d' * 40}"

    errors = validate_record(record)

    assert any("Reviewer requires tester_evidence.verdict PASS" in error for error in errors)
    assert any("reviewer_evidence.candidate_sha must equal candidate_sha" in error for error in errors)
    assert any("final_approval.sha must equal candidate_sha" in error for error in errors)


def test_ordinary_non_mapping_inputs_return_errors_instead_of_raising():
    validate_record = _load_gate().validate_record

    for value in (None, [], "record", 42):
        errors = validate_record(value)
        assert isinstance(errors, list)
        assert errors
        assert "mapping" in errors[0]


def test_malformed_mapping_field_types_return_errors_instead_of_raising():
    validate_record = _load_gate().validate_record
    malformed = {
        "contract_version": [],
        "task_type": [],
        "impact_flags": [{}],
        "state": [],
        "test_path": {},
        "production_rework_count": "many",
        "kpi_optimization_count": None,
    }

    errors = validate_record(malformed)

    assert errors == sorted(errors)
    assert any("task_type" in error for error in errors)
    assert any("state" in error for error in errors)
    assert any("test_path" in error for error in errors)
