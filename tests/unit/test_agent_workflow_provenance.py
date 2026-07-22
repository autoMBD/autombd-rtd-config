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
# File:        test_agent_workflow_provenance.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-22
# Version:     0.1.0
# Description: Acceptance tests for review provenance, routing, and handoffs.
# =================================================================================

import copy
import importlib.util
import json
from pathlib import Path
import re

import pytest


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
SKILL_PATH = Path("agent-discipline/skills/agent-workflow/SKILL.md")
GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)
FLAGS = (
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
)
BASE_SHA = "a" * 40
TEST_SHA = "b" * 40
IMPLEMENTATION_SHA = "c" * 40
CANDIDATE_SHA = "d" * 40
FINAL_EVIDENCE_SHA = "e" * 40


def _contract() -> dict:
    assert CONTRACT_PATH.is_file(), "missing canonical workflow contract"
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _skill() -> str:
    assert SKILL_PATH.is_file(), "missing authoritative agent-workflow Skill"
    return SKILL_PATH.read_text(encoding="utf-8")


def _gate_module():
    if not GATE_PATH.is_file():
        pytest.fail("missing deterministic workflow gate")
    spec = importlib.util.spec_from_file_location("agent_workflow_gate", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _test_evidence() -> dict:
    return {
        "provider": "github",
        "artifact": "issue_comment",
        "repository": "autoMBD/autombd-rtd-config",
        "issue_number": 78,
        "comment_id": 7801,
        "command": f"/approve-test {TEST_SHA}",
        "top_level": True,
        "actor_type": "human",
        "current": True,
        "edited": False,
        "deleted": False,
        "requested_changes": False,
    }


def _final_evidence() -> dict:
    return {
        "provider": "github",
        "artifact": "pull_request_review",
        "repository": "autoMBD/autombd-rtd-config",
        "pull_request_number": 78,
        "review_id": 7802,
        "actor_type": "human",
        "state": "approved",
        "current": True,
        "candidate_sha": CANDIDATE_SHA,
    }


def _monitor() -> dict:
    return {
        "status": "stopped",
        "interval_minutes": 10,
        "scope": "current_session",
    }


def _review_record(state: str) -> dict:
    record = {
        "version": 1,
        "issue": {
            "number": 78,
            "primary_type": "W",
            "impact_flags": ["AR"],
        },
        "state": state,
        "gate": {"test_required": True},
        "revisions": {
            "base_sha": BASE_SHA,
            "test": {
                "identity": "T1",
                "iteration": 1,
                "base_sha": BASE_SHA,
                "sha": TEST_SHA,
            },
        },
        "human_reviews": {
            "test": {
                "approved": True,
                "sha": TEST_SHA,
                "reviewer": "owner",
                "evidence": _test_evidence(),
                "monitor": _monitor(),
            }
        },
        "counters": {"production_rework": 0, "kpi_optimization": 0},
        "exception": None,
    }
    if state == "human_review_1":
        return record

    record["revisions"]["implementation"] = {
        "identity": "W1",
        "iteration": 1,
        "base_sha": BASE_SHA,
        "sha": IMPLEMENTATION_SHA,
    }
    record["revisions"]["candidate"] = {
        "identity": "C1",
        "iteration": 1,
        "sha": CANDIDATE_SHA,
        "parents": {
            "test_sha": TEST_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
        },
    }
    record["tester"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}
    record["reviewer"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}
    record["human_reviews"]["final"] = {
        "approved": True,
        "sha": CANDIDATE_SHA,
        "reviewer": "owner",
        "evidence": _final_evidence(),
        "monitor": _monitor(),
    }
    record["revisions"]["final_evidence"] = {
        "identity": "F1",
        "sha": FINAL_EVIDENCE_SHA,
        "reviewed_candidate_sha": CANDIDATE_SHA,
        "changed_paths": ["agent-discipline/agent-lessons-learned.md"],
    }
    return record


def _errors(record: dict) -> list[str]:
    result = _gate_module().validate_record(record)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
    return result


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _handoff_section(skill: str, role: str) -> str:
    assert "handoff templates" in skill.casefold()
    heading = re.search(
        rf"(?im)^(?P<marks>###{{1,4}})\s+{re.escape(role)}(?:\s+handoff)?\s*$",
        skill,
    )
    assert heading is not None, f"missing {role} handoff template"
    level = len(heading.group("marks"))
    next_heading = re.search(
        rf"(?m)^#{{1,{level}}}\s+",
        skill[heading.end() :],
    )
    end = heading.end() + next_heading.start() if next_heading else len(skill)
    return _normalized(skill[heading.end() : end])


def test_gate1_change_request_is_strict_two_line_command_in_json_and_skill():
    template = _contract()["state_machine"]["human_review_1"]["evidence"][
        "change_request_command"
    ]
    assert template == "/request-test-changes {test_sha}\n{reason}"
    assert template.count("\n") == 1

    skill = _normalized(_skill())
    assert "/request-test-changes {test_sha}" in skill
    assert "{reason}" in skill
    assert "two-line" in skill or "exactly two lines" in skill


def test_gate1_accepts_current_top_level_authorized_human_comment():
    assert _errors(_review_record("human_review_1")) == []


def test_gate1_change_request_record_requires_exact_two_lines_and_reason():
    record = _review_record("human_review_1")
    review = record["human_reviews"]["test"]
    reason = "The test contract must cover transition evidence."
    review["approved"] = False
    review["evidence"]["decision"] = "changes_requested"
    review["evidence"]["reason"] = reason
    review["evidence"]["command"] = f"/request-test-changes {TEST_SHA}\n{reason}"
    assert _errors(record) == []

    invalid_commands = (
        f"/request-test-changes {TEST_SHA}",
        f"/request-test-changes {TEST_SHA}\n",
        f"/request-test-changes {TEST_SHA}\n{reason}\nextra line",
    )
    for command in invalid_commands:
        invalid = copy.deepcopy(record)
        invalid["human_reviews"]["test"]["evidence"]["command"] = command
        errors = _errors(invalid)
        assert errors
        assert any("two-line" in item.casefold() or "reason" in item.casefold() for item in errors)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("repository", "", "repository"),
        ("issue_number", 79, "issue number"),
        ("comment_id", None, "comment id"),
        ("top_level", False, "top-level"),
        ("actor_type", "automation", "human"),
        ("current", False, "current"),
        ("edited", True, "edited"),
        ("deleted", True, "deleted"),
        ("requested_changes", True, "request"),
    ),
)
def test_gate1_rejects_noncurrent_or_unauthorized_issue_comment(
    field, value, expected
):
    record = _review_record("human_review_1")
    record["human_reviews"]["test"]["evidence"][field] = value

    errors = _errors(record)
    assert errors
    assert any(expected in item.casefold() for item in errors)


def test_final_human_review_contract_is_exact_candidate_github_pr_review():
    evidence = _contract()["state_machine"]["final_human_review"]["evidence"]
    assert evidence["provider"] == "github"
    assert evidence["artifact"] == "pull_request_review"
    assert evidence["binds"] == "candidate_sha"
    assert evidence["authorized_actor"] == "human"
    assert set(evidence["required_fields"]) >= {
        "repository",
        "pull_request_number",
        "review_id",
        "state",
        "candidate_sha",
    }
    assert set(evidence["invalidated_by"]) >= {
        "candidate_sha_change",
        "review_edit",
        "review_dismissal",
        "request_changes",
    }


def test_final_human_review_accepts_current_authorized_exact_candidate_review():
    assert _errors(_review_record("complete")) == []


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("status", "active", "stop"),
        ("interval_minutes", 5, "10"),
        ("scope", "new_session", "current session"),
    ),
)
def test_final_human_review_requires_stopped_current_session_monitor(
    field, value, expected
):
    record = _review_record("complete")
    record["human_reviews"]["final"]["monitor"][field] = value

    errors = _errors(record)
    assert errors
    assert any(expected in item.casefold() for item in errors)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("repository", "", "repository"),
        ("pull_request_number", None, "pull request"),
        ("review_id", None, "review id"),
        ("actor_type", "automation", "human"),
        ("state", "commented", "approved"),
        ("current", False, "current"),
        ("candidate_sha", "f" * 40, "candidate"),
    ),
)
def test_final_human_review_rejects_stale_or_unauthorized_pr_review(
    field, value, expected
):
    record = _review_record("complete")
    record["human_reviews"]["final"]["evidence"][field] = value

    errors = _errors(record)
    assert errors
    assert any(expected in item.casefold() for item in errors)


def test_impact_flag_routing_table_is_complete_and_machine_readable():
    routing = _contract()["routing"]["impact_flags"]
    assert tuple(routing) == FLAGS
    for flag in FLAGS:
        entry = routing[flag]
        assert isinstance(entry["required_gates"], list) and entry["required_gates"]
        assert isinstance(entry["profiles"], list) and entry["profiles"]


@pytest.mark.parametrize("flag", FLAGS)
def test_gate_derives_required_gates_and_profiles_from_each_impact_flag(flag):
    module = _gate_module()
    derive = getattr(module, "derive_routing", None)
    assert callable(derive), "missing machine-readable impact routing API"

    expected = _contract()["routing"]["impact_flags"][flag]
    actual = derive([flag])
    assert set(actual["required_gates"]) == set(expected["required_gates"])
    assert set(actual["profiles"]) == set(expected["profiles"])


@pytest.mark.parametrize(
    ("role", "role_markers"),
    (
        ("Orchestrator", ("classification", "exact sha", "human review")),
        ("Explorer", ("ground truth", "read-only", "decision-ready")),
        ("Worker", ("capability", "acceptance-test implementation", "implementation sha")),
        ("Tester", ("candidate sha", "production repair", "pass/fail")),
        ("Reviewer", ("tester pass", "production write", "lessons")),
    ),
)
def test_skill_has_concise_executable_role_handoff_templates(role, role_markers):
    section = _handoff_section(_skill(), role)
    for field in (
        "inputs",
        "forbidden sources",
        "forbidden actions",
        "outputs",
        "stop conditions",
        "acceptance criteria",
    ):
        assert field in section, (role, field)
    for marker in role_markers:
        assert marker in section, (role, marker)
    assert len(section.split()) <= 220, f"{role} handoff is not concise"
