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
LIGHT_FORWARD_TRANSITIONS = (
    ("classify", "implementing", "classification_complete"),
    ("implementing", "candidate", "candidate_created"),
    ("candidate", "testing", "mechanical_verification_started"),
    ("testing", "reviewing", "tester_passed"),
    ("reviewing", "final_human_review", "reviewer_passed"),
    ("final_human_review", "complete", "final_approved"),
)
FROZEN_AUTHORITIES = (
    "issue",
    "base",
    "test_identity",
    "test_sha",
    "implementation_identity",
    "implementation_sha",
    "candidate_identity",
    "candidate_sha",
)
BASE_SHA = "a" * 40
TEST_SHA = "b" * 40
IMPLEMENTATION_SHA = "c" * 40
CANDIDATE_SHA = "d" * 40
REVISED_CANDIDATE_SHA = "e" * 40
FINAL_EVIDENCE_SHA = "f" * 40
NEXT_IMPLEMENTATION_SHA = "1" * 40
NEXT_CANDIDATE_SHA = "2" * 40
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
FUTURE_EVIDENCE = {
    "classify": (
        "revisions.test",
        "human_reviews.test",
        "revisions.implementation",
        "revisions.candidate",
        "tester",
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "test_authoring": (
        "human_reviews.test",
        "revisions.implementation",
        "revisions.candidate",
        "tester",
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "human_review_1": (
        "revisions.implementation",
        "revisions.candidate",
        "tester",
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "implementing": (
        "revisions.candidate",
        "tester",
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "candidate": (
        "tester",
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "testing": (
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "rework": (
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "reviewing": (
        "human_reviews.final",
        "revisions.final_evidence",
    ),
    "final_human_review": ("revisions.final_evidence",),
    "stopped": (
        "human_reviews.final",
        "revisions.final_evidence",
    ),
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


def _permission_preflight() -> dict:
    return {
        "host": {"available": True, "fact": "github_authenticated"},
        "sandbox": {"available": True, "fact": "network_permitted"},
        "required_capabilities": ["read_issue", "read_review"],
        "granted_capabilities": ["read_issue", "read_review"],
        "hydration": {
            "mode": "noninteractive",
            "source": "verified_non_secret_inputs",
        },
    }


def _authorization() -> dict:
    return {"github": {"authorized_human_logins": ["owner"]}}


def _automation(*, count: int = 0, backoff_seconds: int = 10) -> dict:
    return {
        "id": "review-monitor-78",
        "tier": "foreground",
        "count": count,
        "session": "current_session",
        "backoff_seconds": backoff_seconds,
    }


def _base_record(state: str) -> dict:
    return {
        "version": 2,
        "schema": "agent_workflow_v2",
        "issue": {
            "number": 78,
            "primary_type": "W",
            "impact_flags": ["AR", "TC"],
        },
        "state": state,
        "gate": {"test_required": True},
        "revisions": {"base_sha": BASE_SHA},
        "counters": {"production_rework": 0, "kpi_optimization": 0},
        "permission_preflight": _permission_preflight(),
        "authorization": _authorization(),
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


def _candidate_revision(sha: str, *, light_path: bool = False) -> dict:
    parents = {
        "implementation_sha": IMPLEMENTATION_SHA,
    }
    if light_path:
        parents["base_sha"] = BASE_SHA
    else:
        parents["test_sha"] = TEST_SHA
    return {
        "identity": "C1",
        "iteration": 1,
        "sha": sha,
        "parents": parents,
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
            "automation": _automation(),
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
        "actor_login": "owner",
        "current": True,
        "edited": False,
        "deleted": False,
        "requested_changes": False,
    }
    review["monitor"] = {
        "status": "stopped",
        "interval_minutes": 10,
        "scope": "current_session",
        "automation": _automation(count=1),
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
        "actor_login": "owner",
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
            "automation": _automation(),
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
            "actor_login": "owner",
            "state": "approved",
            "current": True,
            "candidate_sha": CANDIDATE_SHA,
        }
        review["monitor"]["status"] = "stopped"
        review["monitor"]["automation"]["count"] = 1
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
        del record["reviewer"]
        record["counters"]["production_rework"] = 3
        record["disposition"] = {
            "status": "stop_escalate",
            "reason": "automatic production rework cap reached",
        }
        del record["human_reviews"]["final"]
        return record

    record["human_reviews"]["final"] = _final_review(True)
    record["revisions"]["final_evidence"] = {
        "identity": "E1",
        "sha": FINAL_EVIDENCE_SHA,
        "reviewed_candidate_sha": CANDIDATE_SHA,
        "changed_paths": [LESSONS_PATH],
    }
    return record


def _light_record_for_state(state: str) -> dict:
    assert state in {
        "classify",
        "implementing",
        "candidate",
        "testing",
        "reviewing",
        "final_human_review",
        "complete",
    }
    record = _base_record(state)
    record["issue"] = {
        "number": 78,
        "primary_type": "N",
        "impact_flags": ["DO"],
    }
    record["gate"] = {
        "test_required": False,
        "light_path": {
            "reason": "Only non-normative documentation is renamed.",
            "residual_risk": "A stale link could remain.",
            "remaining_verification": ["link check", "git diff --check"],
        },
    }
    if state == "classify":
        return record

    record["revisions"]["implementation"] = _implementation_revision(None)
    if state == "implementing":
        return record

    record["revisions"]["implementation"]["sha"] = IMPLEMENTATION_SHA
    record["revisions"]["candidate"] = _candidate_revision(
        CANDIDATE_SHA, light_path=True
    )
    if state == "candidate":
        return record

    record["tester"] = {
        "status": "pending",
        "candidate_sha": CANDIDATE_SHA,
        "mode": "mechanical_verification",
    }
    if state == "testing":
        return record

    record["tester"]["status"] = "pass"
    record["reviewer"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    if state == "reviewing":
        return record

    record["reviewer"]["status"] = "pass"
    record["human_reviews"] = {"final": _final_review(False)}
    if state == "final_human_review":
        return record

    record["human_reviews"]["final"] = _final_review(True)
    record["revisions"]["final_evidence"] = {
        "identity": "E1",
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


def _set_path(record: dict, dotted_path: str, value: object) -> None:
    owner = record
    fields = dotted_path.split(".")
    for field in fields[:-1]:
        owner = owner.setdefault(field, {})
    owner[fields[-1]] = value


def _key_paths(
    value: object,
    key: str,
    prefix: tuple[str, ...] = (),
) -> list[tuple[str, ...]]:
    paths = []
    if isinstance(value, dict):
        for field, child in value.items():
            child_path = (*prefix, field)
            if field == key:
                paths.append(child_path)
            paths.extend(_key_paths(child, key, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_key_paths(child, key, (*prefix, str(index))))
    return paths


def _transition_errors(previous: dict, current: dict, event: str) -> list[str]:
    module = _gate_module()
    validator = getattr(module, "validate_transition", None)
    assert callable(validator), "missing explicit workflow transition validator"
    result = validator(previous, current, event)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
    return result


def _next_iteration_records(
    *,
    counter: str,
    counter_value: int,
    revision_iteration: int,
) -> tuple[dict, dict, dict]:
    implementing = _record_for_state("implementing")
    implementing["revisions"]["implementation"] = {
        "identity": f"W{revision_iteration}",
        "iteration": revision_iteration,
        "base_sha": BASE_SHA,
        "sha": None,
    }
    implementing["counters"][counter] = counter_value

    candidate = _record_for_state("candidate")
    candidate["revisions"]["implementation"] = {
        "identity": f"W{revision_iteration}",
        "iteration": revision_iteration,
        "base_sha": BASE_SHA,
        "sha": NEXT_IMPLEMENTATION_SHA,
    }
    candidate["revisions"]["candidate"] = {
        "identity": f"C{revision_iteration}",
        "iteration": revision_iteration,
        "sha": NEXT_CANDIDATE_SHA,
        "parents": {
            "test_sha": TEST_SHA,
            "implementation_sha": NEXT_IMPLEMENTATION_SHA,
        },
    }
    candidate["counters"][counter] = counter_value

    testing = copy.deepcopy(candidate)
    testing["state"] = "testing"
    testing["tester"] = {
        "status": "pending",
        "candidate_sha": NEXT_CANDIDATE_SHA,
    }
    return implementing, candidate, testing


def _coherently_rebind(record: dict, authority: str) -> None:
    replacement_sha = "3" * 40
    if authority == "issue":
        record["issue"]["number"] = 79
        record["human_reviews"]["test"]["evidence"]["issue_number"] = 79
        if "final" in record["human_reviews"]:
            record["human_reviews"]["final"]["evidence"][
                "pull_request_number"
            ] = 79
    elif authority == "base":
        record["revisions"]["base_sha"] = replacement_sha
        record["revisions"]["test"]["base_sha"] = replacement_sha
        record["revisions"]["implementation"]["base_sha"] = replacement_sha
    elif authority == "test_identity":
        record["revisions"]["test"].update(identity="T2", iteration=2)
    elif authority == "test_sha":
        record["revisions"]["test"]["sha"] = replacement_sha
        record["human_reviews"]["test"]["sha"] = replacement_sha
        record["human_reviews"]["test"]["evidence"][
            "command"
        ] = f"/approve-test {replacement_sha}"
        if "candidate" in record["revisions"]:
            record["revisions"]["candidate"]["parents"][
                "test_sha"
            ] = replacement_sha
    elif authority == "implementation_identity":
        record["revisions"]["implementation"].update(identity="W2", iteration=2)
    elif authority == "implementation_sha":
        record["revisions"]["implementation"]["sha"] = replacement_sha
        if "candidate" in record["revisions"]:
            record["revisions"]["candidate"]["parents"][
                "implementation_sha"
            ] = replacement_sha
    elif authority == "candidate_identity":
        record["revisions"]["candidate"].update(identity="C2", iteration=2)
    elif authority == "candidate_sha":
        record["revisions"]["candidate"]["sha"] = replacement_sha
        if "tester" in record:
            record["tester"]["candidate_sha"] = replacement_sha
        if "reviewer" in record:
            record["reviewer"]["candidate_sha"] = replacement_sha
        if "final" in record.get("human_reviews", {}):
            record["human_reviews"]["final"]["sha"] = replacement_sha
            evidence = record["human_reviews"]["final"]["evidence"]
            if evidence is not None:
                evidence["candidate_sha"] = replacement_sha
        if "final_evidence" in record["revisions"]:
            record["revisions"]["final_evidence"][
                "reviewed_candidate_sha"
            ] = replacement_sha
    else:
        raise AssertionError(authority)


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
    for state, future_paths in FUTURE_EVIDENCE.items():
        forbidden = by_name[state]["forbidden_fields"]
        for future_path in future_paths:
            assert any(
                future_path == blocked
                or future_path.startswith(f"{blocked}.")
                for blocked in forbidden
            ), (state, future_path)

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


@pytest.mark.parametrize(
    ("state", "future_path"),
    tuple(
        (state, future_path)
        for state, future_paths in FUTURE_EVIDENCE.items()
        for future_path in future_paths
    ),
)
def test_each_state_rejects_every_future_evidence_field(state, future_path):
    record = _record_for_state(state)
    _set_path(record, future_path, {"unexpected": "future evidence"})

    errors = _record_errors(record)
    assert errors
    assert any(
        "forbidden" in item.casefold()
        and any(
            blocked_path in item
            for blocked_path in (
                ".".join(future_path.split(".")[:depth])
                for depth in range(len(future_path.split(".")), 0, -1)
            )
        )
        for item in errors
    )


def test_transition_validator_accepts_the_canonical_forward_path():
    for previous_state, current_state, event in FORWARD_TRANSITIONS:
        previous = _record_for_state(previous_state)
        current = _record_for_state(current_state)
        assert _transition_errors(previous, current, event) == [], event


def test_mechanical_light_path_executes_the_canonical_skipping_sequence():
    for state in (
        "classify",
        "implementing",
        "candidate",
        "testing",
        "reviewing",
        "final_human_review",
        "complete",
    ):
        record = _light_record_for_state(state)
        assert _record_errors(record) == [], state
        assert "test" not in record["revisions"]
        assert "test" not in record.get("human_reviews", {})

    for previous_state, current_state, event in LIGHT_FORWARD_TRANSITIONS:
        previous = _light_record_for_state(previous_state)
        current = _light_record_for_state(current_state)
        assert _transition_errors(previous, current, event) == [], event

    candidate = _light_record_for_state("candidate")
    assert candidate["revisions"]["candidate"]["parents"] == {
        "base_sha": BASE_SHA,
        "implementation_sha": IMPLEMENTATION_SHA,
    }
    testing = _light_record_for_state("testing")
    assert testing["tester"]["mode"] == "mechanical_verification"


@pytest.mark.parametrize(
    "legacy_gate_1_path",
    ("revisions.test", "human_reviews.test"),
)
def test_mechanical_light_path_forbids_skipped_test_gate_evidence(
    legacy_gate_1_path,
):
    record = _light_record_for_state("complete")
    _set_path(record, legacy_gate_1_path, {"unexpected": "skipped gate evidence"})

    errors = _record_errors(record)
    assert errors
    assert any(
        legacy_gate_1_path in item
        and ("forbidden" in item.casefold() or "light path" in item.casefold())
        for item in errors
    )


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
    contract = _contract()
    assert _key_paths(contract, "identities") == [
        ("revision_provenance", "identities")
    ]
    assert _key_paths(contract, "candidate_parents") == [
        ("revision_provenance", "candidate_parents")
    ]
    provenance = contract["revision_provenance"]
    assert provenance["identities"] == {
        "test": "T[1-9][0-9]*",
        "implementation": "W[1-9][0-9]*",
        "candidate": "C[1-9][0-9]*",
        "evidence": "E[1-9][0-9]*",
    }
    assert provenance["candidate_parents"] == {
        "normal": ["test_sha", "implementation_sha"],
        "mechanical_light": ["base_sha", "implementation_sha"],
    }
    record = _record_for_state("complete")
    assert _record_errors(record) == []
    assert record["revisions"]["candidate"]["parents"] == {
        "test_sha": TEST_SHA,
        "implementation_sha": IMPLEMENTATION_SHA,
    }

    light_record = _light_record_for_state("complete")
    assert _record_errors(light_record) == []
    assert light_record["revisions"]["candidate"]["parents"] == {
        "base_sha": BASE_SHA,
        "implementation_sha": IMPLEMENTATION_SHA,
    }

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


@pytest.mark.parametrize("previous_state", ("reviewing", "final_human_review"))
def test_candidate_revision_cannot_bypass_counted_worker_rework(previous_state):
    previous = _record_for_state(previous_state)
    current = copy.deepcopy(previous)
    current["state"] = "testing"
    current["revisions"]["candidate"]["identity"] = "C2"
    current["revisions"]["candidate"]["iteration"] = 2
    current["revisions"]["candidate"]["sha"] = REVISED_CANDIDATE_SHA
    current["tester"] = {
        "status": "pending",
        "candidate_sha": REVISED_CANDIDATE_SHA,
    }
    current.pop("reviewer", None)
    current.get("human_reviews", {}).pop("final", None)

    errors = _transition_errors(previous, current, "candidate_revised")
    assert errors
    assert any(
        marker in item.casefold()
        for item in errors
        for marker in ("transition", "rework", "worker", "implementing")
    )

    direct_routes = [
        transition
        for transition in _contract()["state_machine"]["transitions"]
        if transition["from"] == previous_state
        and transition["to"] == "testing"
        and transition["event"] == "candidate_revised"
    ]
    assert direct_routes == []


def test_review_corrections_have_a_machine_readable_route_into_counted_rework():
    transitions = _contract()["state_machine"]["transitions"]
    final_correction_routes = [
        transition
        for transition in transitions
        if transition["from"] == "final_human_review"
        and transition["to"] == "reviewing"
        and "change" in transition["event"].casefold()
    ]
    worker_rework_routes = [
        transition
        for transition in transitions
        if transition["from"] == "reviewing"
        and transition["to"] == "rework"
    ]

    assert len(final_correction_routes) == 1
    assert len(worker_rework_routes) == 1
    assert worker_rework_routes[0]["event"]


@pytest.mark.parametrize(
    ("previous_state", "current_state", "event", "authority"),
    tuple(
        (previous_state, current_state, event, authority)
        for previous_state, current_state, event, authorities in (
            (
                "human_review_1",
                "implementing",
                "test_approved",
                FROZEN_AUTHORITIES[:4],
            ),
            (
                "implementing",
                "candidate",
                "candidate_created",
                FROZEN_AUTHORITIES[:5],
            ),
            (
                "candidate",
                "testing",
                "testing_started",
                FROZEN_AUTHORITIES,
            ),
            (
                "testing",
                "reviewing",
                "tester_passed",
                FROZEN_AUTHORITIES,
            ),
            (
                "reviewing",
                "final_human_review",
                "reviewer_passed",
                FROZEN_AUTHORITIES,
            ),
            (
                "final_human_review",
                "complete",
                "final_approved",
                FROZEN_AUTHORITIES,
            ),
        )
        for authority in authorities
    ),
)
def test_forward_transitions_cannot_rebind_frozen_revision_authority(
    previous_state,
    current_state,
    event,
    authority,
):
    previous = _record_for_state(previous_state)
    current = _record_for_state(current_state)
    _coherently_rebind(current, authority)

    assert _record_errors(previous) == []
    assert _record_errors(current) == []
    errors = _transition_errors(previous, current, event)
    assert errors
    assert any(
        marker in item.casefold()
        for item in errors
        for marker in ("immutable", "rebind", "changed", authority.split("_")[0])
    )


@pytest.mark.parametrize("authority", ("issue", "base", "test_sha"))
def test_production_rework_cannot_adversarially_rebind_frozen_authority(
    authority,
):
    previous = _record_for_state("rework")
    current, _, _ = _next_iteration_records(
        counter="production_rework",
        counter_value=1,
        revision_iteration=2,
    )
    _coherently_rebind(current, authority)

    assert _record_errors(previous) == []
    assert _record_errors(current) == []
    errors = _transition_errors(previous, current, "production_rework")
    assert errors
    assert any(
        marker in item.casefold()
        for item in errors
        for marker in ("immutable", "rebind", "changed", authority.split("_")[0])
    )


def test_counted_rework_builds_a_new_worker_and_candidate_before_retesting():
    rework = _record_for_state("rework")
    implementing, candidate, testing = _next_iteration_records(
        counter="production_rework",
        counter_value=1,
        revision_iteration=2,
    )

    assert _transition_errors(rework, implementing, "production_rework") == []
    assert _transition_errors(implementing, candidate, "candidate_created") == []
    assert _transition_errors(candidate, testing, "testing_started") == []
    assert implementing["revisions"]["implementation"]["identity"] == "W2"
    assert candidate["revisions"]["candidate"]["identity"] == "C2"
    assert candidate["revisions"]["candidate"]["parents"] == {
        "test_sha": TEST_SHA,
        "implementation_sha": NEXT_IMPLEMENTATION_SHA,
    }
    assert testing["tester"] == {
        "status": "pending",
        "candidate_sha": NEXT_CANDIDATE_SHA,
    }
    assert testing["counters"]["production_rework"] == 1


def _kpi_miss_testing_record(*, completed_optimizations: int) -> dict:
    record = _record_for_state("testing")
    record["tester"] = {
        "status": "pass",
        "candidate_sha": CANDIDATE_SHA,
        "kpi": {
            "status": "miss",
            "candidate_sha": CANDIDATE_SHA,
            "elapsed_seconds": 90,
            "limit_seconds": 60,
            "edit_attempts": 1,
        },
    }
    record["counters"]["kpi_optimization"] = completed_optimizations
    return record


@pytest.mark.parametrize(
    ("previous_count", "current_count", "revision_iteration"),
    ((0, 1, 2), (2, 3, 4)),
)
def test_kpi_optimization_consumes_exactly_one_iteration_and_retests_candidate(
    previous_count,
    current_count,
    revision_iteration,
):
    previous = _kpi_miss_testing_record(
        completed_optimizations=previous_count
    )
    implementing, candidate, testing = _next_iteration_records(
        counter="kpi_optimization",
        counter_value=current_count,
        revision_iteration=revision_iteration,
    )

    assert _transition_errors(previous, implementing, "kpi_optimization") == []
    assert _transition_errors(implementing, candidate, "candidate_created") == []
    assert _transition_errors(candidate, testing, "testing_started") == []
    assert implementing["counters"]["kpi_optimization"] == previous_count + 1
    assert testing["counters"]["production_rework"] == 0
    assert testing["tester"]["status"] == "pending"
    assert testing["tester"]["candidate_sha"] == NEXT_CANDIDATE_SHA


@pytest.mark.parametrize(
    "stale_path",
    (
        "revisions.candidate.sha",
        "tester.candidate_sha",
        "reviewer",
        "human_reviews.final",
        "revisions.final_evidence",
    ),
)
def test_kpi_optimization_invalidates_all_old_candidate_bound_evidence(
    stale_path,
):
    _, _, testing = _next_iteration_records(
        counter="kpi_optimization",
        counter_value=1,
        revision_iteration=2,
    )
    stale_values = {
        "revisions.candidate.sha": CANDIDATE_SHA,
        "tester.candidate_sha": CANDIDATE_SHA,
        "reviewer": {"status": "pass", "candidate_sha": CANDIDATE_SHA},
        "human_reviews.final": _final_review(True),
        "revisions.final_evidence": {
            "identity": "E1",
            "sha": FINAL_EVIDENCE_SHA,
            "reviewed_candidate_sha": CANDIDATE_SHA,
            "changed_paths": [LESSONS_PATH],
        },
    }
    _set_path(testing, stale_path, stale_values[stale_path])

    errors = _record_errors(testing)
    assert errors
    assert any(
        stale_path in item
        or "candidate" in item.casefold()
        or "forbidden" in item.casefold()
        for item in errors
    )


def test_fourth_kpi_optimization_is_forbidden():
    previous = _kpi_miss_testing_record(completed_optimizations=3)
    implementing, _, _ = _next_iteration_records(
        counter="kpi_optimization",
        counter_value=4,
        revision_iteration=5,
    )

    errors = _transition_errors(previous, implementing, "kpi_optimization")
    assert errors
    assert any(
        marker in item.casefold()
        for item in errors
        for marker in ("limit", "stop", "fourth", "kpi")
    )


def test_one_evidence_only_path_policy_governs_final_revision_without_rebinding():
    contract = _contract()
    assert _key_paths(contract, "allowed_paths") == [
        ("revision_provenance", "evidence_only", "allowed_paths")
    ]
    evidence_contract = contract["revision_provenance"]["evidence_only"]
    assert evidence_contract["kind"] == "evidence_only"
    assert evidence_contract["parent"] == "exact_candidate_sha"
    assert set(evidence_contract["allowed_paths"]) == {
        LESSONS_PATH,
        "docs/tests/rtd-config-acceptance-report.md",
    }

    record = _record_for_state("complete")
    assert _record_errors(record) == []
    assert record["human_reviews"]["final"]["sha"] == CANDIDATE_SHA
    assert (
        record["revisions"]["final_evidence"]["reviewed_candidate_sha"]
        == CANDIDATE_SHA
    )

    for allowed_path in evidence_contract["allowed_paths"]:
        allowed = copy.deepcopy(record)
        allowed["revisions"]["final_evidence"]["changed_paths"] = [allowed_path]
        assert _record_errors(allowed) == [], allowed_path

    polluted = copy.deepcopy(record)
    polluted["revisions"]["final_evidence"]["changed_paths"].append(
        "agent-discipline/skills/agent-workflow/SKILL.md"
    )
    errors = _record_errors(polluted)
    assert errors
    assert any("evidence-only" in item.casefold() or "allowlist" in item.casefold() for item in errors)
