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
# File:        test_agent_workflow_lifecycle.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-22
# Version:     0.1.0
# Description: Acceptance tests for workflow lifecycle and revision evidence.
# =================================================================================

import copy
import importlib.util
import json
from pathlib import Path

import pytest


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)
CANONICAL_STATES = (
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
)
FORWARD_TRANSITIONS = (
    ("classify", "test_authoring", "classification_complete"),
    ("test_authoring", "human_review_1", "test_frozen"),
    ("human_review_1", "implementing", "test_approved"),
    ("implementing", "candidate", "candidate_created"),
    ("candidate", "testing", "testing_started"),
    ("testing", "reviewing", "tester_passed"),
    ("reviewing", "final_human_review", "reviewer_passed"),
    ("final_human_review", "complete", "final_approved"),
)
BASE_SHA = "a" * 40
TEST_SHA = "b" * 40
IMPLEMENTATION_SHA = "c" * 40
CANDIDATE_SHA = "d" * 40
REVISED_CANDIDATE_SHA = "e" * 40
FINAL_EVIDENCE_SHA = "f" * 40
LESSONS_PATH = "agent-discipline/agent-lessons-learned.md"
REQUIRED_PROBES = {
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


def _contract() -> dict:
    assert CONTRACT_PATH.is_file(), "missing canonical workflow contract"
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _gate_module():
    if not GATE_PATH.is_file():
        pytest.fail("missing deterministic workflow gate")
    spec = importlib.util.spec_from_file_location("agent_workflow_gate", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_record(state: str) -> dict:
    return {
        "version": 1,
        "issue": {
            "number": 78,
            "primary_type": "W",
            "impact_flags": ["AR", "TC"],
        },
        "state": state,
        "gate": {"test_required": True},
        "revisions": {"base_sha": BASE_SHA},
        "counters": {"production_rework": 0, "kpi_optimization": 0},
        "exception": None,
    }


def _test_revision(sha: str | None) -> dict:
    return {
        "identity": "T1",
        "iteration": 1,
        "base_sha": BASE_SHA,
        "sha": sha,
    }


def _implementation_revision(sha: str | None) -> dict:
    return {
        "identity": "W1",
        "iteration": 1,
        "base_sha": BASE_SHA,
        "sha": sha,
    }


def _candidate_revision(sha: str) -> dict:
    return {
        "identity": "C1",
        "iteration": 1,
        "sha": sha,
        "parents": {
            "test_sha": TEST_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
        },
    }


def _test_review(approved: bool) -> dict:
    review = {
        "approved": approved,
        "sha": TEST_SHA,
        "reviewer": "owner" if approved else None,
    }
    if not approved:
        review["evidence"] = None
        review["monitor"] = {
            "status": "active",
            "interval_minutes": 10,
            "scope": "current_session",
        }
        return review
    review["evidence"] = {
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
    review["monitor"] = {
        "status": "stopped",
        "interval_minutes": 10,
        "scope": "current_session",
    }
    return review


def _test_change_request() -> dict:
    review = _test_review(False)
    review["evidence"] = {
        "provider": "github",
        "artifact": "issue_comment",
        "repository": "autoMBD/autombd-rtd-config",
        "issue_number": 78,
        "comment_id": 7803,
        "command": f"/request-test-changes {TEST_SHA}\nclarify transition coverage",
        "top_level": True,
        "actor_type": "human",
        "current": True,
        "edited": False,
        "deleted": False,
        "requested_changes": True,
    }
    return review


def _final_review(approved: bool) -> dict:
    review = {
        "approved": approved,
        "sha": CANDIDATE_SHA,
        "reviewer": "owner" if approved else None,
        "evidence": None,
        "monitor": {
            "status": "active",
            "interval_minutes": 10,
            "scope": "current_session",
        },
    }
    if approved:
        review["evidence"] = {
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
        review["monitor"]["status"] = "stopped"
    return review


def _record_for_state(state: str) -> dict:
    record = _base_record(state)
    if state == "classify":
        return record

    record["revisions"]["test"] = _test_revision(None)
    if state == "test_authoring":
        return record

    record["revisions"]["test"]["sha"] = TEST_SHA
    record["human_reviews"] = {"test": _test_review(False)}
    if state == "human_review_1":
        return record

    record["human_reviews"]["test"] = _test_review(True)
    record["revisions"]["implementation"] = _implementation_revision(None)
    if state == "implementing":
        return record

    record["revisions"]["implementation"]["sha"] = IMPLEMENTATION_SHA
    record["revisions"]["candidate"] = _candidate_revision(CANDIDATE_SHA)
    if state == "candidate":
        return record

    record["tester"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    if state == "testing":
        return record

    if state == "rework":
        record["tester"]["status"] = "fail"
        return record

    record["tester"]["status"] = "pass"
    record["reviewer"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    if state == "reviewing":
        return record

    record["reviewer"]["status"] = "pass"
    record["human_reviews"]["final"] = _final_review(False)
    if state == "final_human_review":
        return record

    if state == "stopped":
        record["tester"]["status"] = "fail"
        record["reviewer"]["status"] = "not_run"
        record["counters"]["production_rework"] = 3
        record["disposition"] = {
            "status": "stop_escalate",
            "reason": "automatic production rework cap reached",
        }
        del record["human_reviews"]["final"]
        return record

    record["human_reviews"]["final"] = _final_review(True)
    record["revisions"]["final_evidence"] = {
        "identity": "F1",
        "sha": FINAL_EVIDENCE_SHA,
        "reviewed_candidate_sha": CANDIDATE_SHA,
        "changed_paths": [LESSONS_PATH],
    }
    return record


def _record_errors(record: dict) -> list[str]:
    result = _gate_module().validate_record(record)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
    return result


def _delete_path(record: dict, dotted_path: str) -> None:
    owner = record
    fields = dotted_path.split(".")
    for field in fields[:-1]:
        owner = owner[field]
    del owner[fields[-1]]


def _transition_errors(previous: dict, current: dict, event: str) -> list[str]:
    module = _gate_module()
    validator = getattr(module, "validate_transition", None)
    assert callable(validator), "missing explicit workflow transition validator"
    result = validator(previous, current, event)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
    return result


def test_contract_declares_state_dependent_required_and_forbidden_fields():
    machine = _contract()["state_machine"]
    states = machine["states"]

    assert tuple(item["name"] for item in states) == CANONICAL_STATES
    for item in states:
        required = item["required_fields"]
        forbidden = item["forbidden_fields"]
        assert isinstance(required, list) and required, item["name"]
        assert isinstance(forbidden, list), item["name"]
        assert set(required).isdisjoint(forbidden), item["name"]

    by_name = {item["name"]: item for item in states}
    for early_state in ("classify", "test_authoring", "human_review_1"):
        forbidden = set(by_name[early_state]["forbidden_fields"])
        assert "revisions.candidate.sha" in forbidden
        assert "tester.candidate_sha" in forbidden
        assert "reviewer.candidate_sha" in forbidden
        assert "human_reviews.final.evidence" in forbidden

    assert {
        "tester.candidate_sha",
        "reviewer.candidate_sha",
        "human_reviews.final.evidence",
    }.issubset(by_name["candidate"]["forbidden_fields"])
    assert {
        "reviewer.candidate_sha",
        "human_reviews.final.evidence",
    }.issubset(by_name["rework"]["forbidden_fields"])

    final_change_routes = [
        transition
        for transition in machine["transitions"]
        if transition["from"] == "final_human_review"
        and "change" in transition["event"].casefold()
    ]
    assert len(final_change_routes) == 1
    assert final_change_routes[0]["event"]
    assert final_change_routes[0]["to"] in CANONICAL_STATES


@pytest.mark.parametrize("state", CANONICAL_STATES)
def test_each_state_accepts_its_own_minimal_record(state):
    assert _record_errors(_record_for_state(state)) == []


@pytest.mark.parametrize("state", CANONICAL_STATES)
def test_each_state_rejects_a_missing_state_required_field(state):
    record = _record_for_state(state)
    required_path = REQUIRED_PROBES[state]
    _delete_path(record, required_path)

    errors = _record_errors(record)
    assert errors
    assert any(required_path in item for item in errors)


@pytest.mark.parametrize("state", ("classify", "test_authoring", "human_review_1"))
def test_early_states_reject_future_candidate_evidence(state):
    record = _record_for_state(state)
    record["revisions"]["candidate"] = _candidate_revision(CANDIDATE_SHA)
    record["tester"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}

    errors = _record_errors(record)
    assert errors
    assert any("forbidden" in item.casefold() or state in item for item in errors)


def test_transition_validator_accepts_the_canonical_forward_path():
    for previous_state, current_state, event in FORWARD_TRANSITIONS:
        previous = _record_for_state(previous_state)
        current = _record_for_state(current_state)
        assert _transition_errors(previous, current, event) == [], event


def test_human_review_1_change_request_returns_to_test_revision_without_rework():
    previous = _record_for_state("human_review_1")
    previous["human_reviews"]["test"] = _test_change_request()
    current = _record_for_state("test_authoring")
    current["revisions"]["test"].update(
        {"identity": "T2", "iteration": 2, "sha": None}
    )

    assert _transition_errors(previous, current, "changes_requested") == []
    assert current["counters"]["production_rework"] == 0


@pytest.mark.parametrize(
    ("previous_state", "current_state", "event"),
    (
        ("classify", "complete", "final_approved"),
        ("test_authoring", "implementing", "test_approved"),
        ("testing", "complete", "tester_passed"),
        ("complete", "implementing", "production_rework"),
    ),
)
def test_transition_validator_rejects_illegal_jumps(
    previous_state, current_state, event
):
    errors = _transition_errors(
        _record_for_state(previous_state),
        _record_for_state(current_state),
        event,
    )
    assert errors
    assert any("transition" in error.casefold() for error in errors)


def test_production_rework_is_bounded_and_only_rework_to_implementation_consumes_it():
    testing = _record_for_state("testing")
    testing["tester"]["status"] = "fail"
    rework = _record_for_state("rework")
    assert _transition_errors(testing, rework, "tester_failed") == []
    assert rework["counters"]["production_rework"] == 0

    for event in ("dependency_blocked", "permission_blocked"):
        unchanged = copy.deepcopy(rework)
        assert _transition_errors(rework, unchanged, event) == []
        assert unchanged["counters"]["production_rework"] == 0

    implementing = _record_for_state("implementing")
    implementing["revisions"]["implementation"].update(
        {"identity": "W2", "iteration": 2}
    )
    implementing["counters"]["production_rework"] = 1
    assert _transition_errors(rework, implementing, "production_rework") == []

    exhausted = copy.deepcopy(rework)
    exhausted["counters"]["production_rework"] = 3
    stopped = _record_for_state("stopped")
    assert _transition_errors(exhausted, stopped, "production_rework") == []
    assert stopped["counters"]["production_rework"] == 3
    assert stopped["disposition"]["status"] == "stop_escalate"

    fourth = copy.deepcopy(implementing)
    fourth["counters"]["production_rework"] = 4
    errors = _transition_errors(exhausted, fourth, "production_rework")
    assert errors
    assert any("stop" in error.casefold() or "fourth" in error.casefold() for error in errors)


def test_candidate_revision_requires_exact_test_and_implementation_parents():
    contract = _contract()["revision_graph"]
    assert contract["identities"] == {
        "test": "T{iteration}",
        "implementation": "W{iteration}",
        "candidate": "C{iteration}",
    }
    assert set(contract["shared_base"]) == {
        "test.base_sha",
        "implementation.base_sha",
    }
    assert contract["candidate_parents"] == [
        "test.sha",
        "implementation.sha",
    ]

    record = _record_for_state("complete")
    assert _record_errors(record) == []

    bad_base = copy.deepcopy(record)
    bad_base["revisions"]["implementation"]["base_sha"] = REVISED_CANDIDATE_SHA
    assert any("base" in item.casefold() for item in _record_errors(bad_base))

    bad_parent = copy.deepcopy(record)
    bad_parent["revisions"]["candidate"]["parents"]["test_sha"] = REVISED_CANDIDATE_SHA
    assert any("parent" in item.casefold() for item in _record_errors(bad_parent))


@pytest.mark.parametrize(
    ("revision", "invalid_identity"),
    (("test", "T2"), ("implementation", "W2"), ("candidate", "C2")),
)
def test_revision_identity_must_match_its_iteration(revision, invalid_identity):
    record = _record_for_state("complete")
    record["revisions"][revision]["identity"] = invalid_identity

    errors = _record_errors(record)
    assert errors
    assert any("identity" in item.casefold() for item in errors)


def test_candidate_change_invalidates_tester_and_reviewer_evidence():
    previous = _record_for_state("reviewing")
    current = copy.deepcopy(previous)
    current["state"] = "testing"
    current["revisions"]["candidate"]["identity"] = "C2"
    current["revisions"]["candidate"]["iteration"] = 2
    current["revisions"]["candidate"]["sha"] = REVISED_CANDIDATE_SHA

    stale_errors = _transition_errors(previous, current, "candidate_revised")
    assert stale_errors
    assert any("tester" in item.casefold() for item in stale_errors)
    assert any("reviewer" in item.casefold() for item in stale_errors)

    current["tester"] = {
        "status": "pending",
        "candidate_sha": REVISED_CANDIDATE_SHA,
    }
    current["reviewer"] = {
        "status": "not_run",
        "candidate_sha": REVISED_CANDIDATE_SHA,
    }
    assert _transition_errors(previous, current, "candidate_revised") == []


def test_final_evidence_revision_is_path_allowlisted_without_rebinding_candidate():
    evidence_contract = _contract()["revision_graph"]["final_evidence_revision"]
    assert evidence_contract["reviewed_object"] == "candidate.sha"
    assert evidence_contract["evidence_only"] is True
    assert LESSONS_PATH in evidence_contract["allowed_paths"]
    assert evidence_contract["production_paths_allowed"] is False

    record = _record_for_state("complete")
    assert _record_errors(record) == []
    assert record["human_reviews"]["final"]["sha"] == CANDIDATE_SHA
    assert record["revisions"]["final_evidence"]["reviewed_candidate_sha"] == CANDIDATE_SHA

    polluted = copy.deepcopy(record)
    polluted["revisions"]["final_evidence"]["changed_paths"].append(
        "agent-discipline/skills/agent-workflow/SKILL.md"
    )
    errors = _record_errors(polluted)
    assert errors
    assert any("evidence-only" in item.casefold() or "allowlist" in item.casefold() for item in errors)
