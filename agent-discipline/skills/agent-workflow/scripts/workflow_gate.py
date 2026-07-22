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
# File:        workflow_gate.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-22
# Version:     0.4.1
# Description: Validate stateful Agent workflow records and transitions.
# =================================================================================

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
from pathlib import Path
import re
import sys
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[3] / "workflow-contract.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REVISION_ID_RE = {
    kind: re.compile(f"^{pattern}$")
    for kind, pattern in CONTRACT["revision_provenance"]["identities"].items()
}
TASK_CLASSES = frozenset(item["code"] for item in CONTRACT["task_classes"])
IMPACT_FLAGS = frozenset(item["code"] for item in CONTRACT["impact_flags"])
STATES = tuple(CONTRACT["state_machine"]["sequence"])
STATE_INDEX = {state: index for index, state in enumerate(STATES)}
DIAGNOSTIC_CONCEPTS = {
    "primary_type": "primary type",
    "impact_flag": "impact flag",
    "human_review_1": "Human Review 1",
    "approval_command": "approval command",
    "comment_id": "comment ID",
    "current_session": "current session",
    "production_rework": "production rework",
    "kpi_optimization": "KPI optimization",
    "residual_risk": "residual risk",
    "remaining_verification": "remaining verification",
    "tester_pass": "Tester pass",
    "final_human_review": "Final Human Review",
}
LEGACY_TRANSITIONS = {
    "classify": {"test_authoring": "classified"},
    "test_authoring": {"human_review_1": "test_ready"},
    "human_review_1": {
        "implementing": "test_approved",
        "test_authoring": "changes_requested",
    },
    "implementing": {"candidate": "implementation_ready"},
    "candidate": {"testing": "candidate_ready"},
    "testing": {
        "reviewing": "functional_pass",
        "rework": "functional_failure",
    },
    "rework": {
        "implementing": "production_rework",
        "stopped": "rework_cap_reached",
    },
    "reviewing": {"final_human_review": "review_pass"},
    "final_human_review": {"complete": "final_approved"},
    "complete": {},
    "stopped": {},
}


def derive_gate_profile(primary_type: str, impact_flags: list[str]) -> dict[str, Any]:
    """Derive canonical gates and profiles from classification only."""

    if (
        not isinstance(primary_type, str)
        or primary_type not in TASK_CLASSES
        or not isinstance(impact_flags, list)
        or not impact_flags
        or any(not isinstance(flag, str) for flag in impact_flags)
    ):
        raise ValueError("primary type and impact flags must use canonical values")
    unknown = set(impact_flags) - IMPACT_FLAGS
    if unknown:
        raise ValueError("primary type and impact flags must use canonical values")
    routing = CONTRACT["impact_routing"]
    required_gates = sorted(
        {
            gate
            for flag in impact_flags
            for gate in routing[flag]["required_gates"]
        }
    )
    profiles = sorted(
        {
            profile
            for flag in impact_flags
            for profile in routing[flag]["profiles"]
        }
    )
    light = primary_type == "N" and set(impact_flags) == {"DO"}
    return {
        "test_required": not light,
        "required_gates": required_gates,
        "profiles": profiles,
    }


def derive_routing(impact_flags: list[str]) -> dict[str, list[str]]:
    """Return the deterministic union of routing requirements for impact flags."""

    routing = CONTRACT["routing"]["impact_flags"]
    if (
        not isinstance(impact_flags, list)
        or not impact_flags
        or any(not isinstance(flag, str) or flag not in routing for flag in impact_flags)
        or len(impact_flags) != len(set(impact_flags))
    ):
        raise ValueError("impact flags must be unique canonical values")
    return {
        "required_gates": sorted(
            {gate for flag in impact_flags for gate in routing[flag]["required_gates"]}
        ),
        "profiles": sorted(
            {profile for flag in impact_flags for profile in routing[flag]["profiles"]}
        ),
    }


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _mapping(value: Any, path: str, errors: list[str]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    errors.append(f"{path} must be a mapping")
    return {}


def _validate_sha(
    value: Any, path: str, errors: list[str], concept: str | None = None
) -> None:
    if not isinstance(value, str) or FULL_SHA_RE.fullmatch(value) is None:
        prefix = f"{concept}: " if concept else ""
        errors.append(f"{prefix}{path} must be a full 40-hex SHA")


def _validate_required_text(
    value: Any, path: str, errors: list[str], concept: str | None = None
) -> None:
    if not _is_text(value):
        prefix = f"{concept}: " if concept else ""
        errors.append(f"{prefix}{path} must be non-empty text")


def _validate_reason_block(value: Any, path: str, errors: list[str]) -> None:
    block = _mapping(value, path, errors)
    _validate_required_text(block.get("reason"), f"{path}.reason", errors)
    _validate_required_text(
        block.get("residual_risk"),
        f"{path}.residual_risk",
        errors,
        DIAGNOSTIC_CONCEPTS["residual_risk"],
    )
    remaining = block.get("remaining_verification")
    if not isinstance(remaining, list) or not remaining:
        errors.append(
            f"{DIAGNOSTIC_CONCEPTS['remaining_verification']}: "
            f"{path}.remaining_verification "
            "must be a non-empty list"
        )
        return
    for index, item in enumerate(remaining):
        if not _is_text(item):
            errors.append(
                f"{DIAGNOSTIC_CONCEPTS['remaining_verification']}: "
                f"{path}.remaining_verification[{index}] "
                "must be non-empty text"
            )


def _validate_monitor(
    value: Any, path: str, errors: list[str], concept: str
) -> None:
    monitor = _mapping(value, path, errors)
    expected = CONTRACT["human_review_monitor"]
    if monitor.get("status") != "stopped":
        errors.append(f"{concept}: {path}.status must be stopped")
    if monitor.get("interval_minutes") != expected["interval_minutes"]:
        errors.append(
            f"{concept}: {path}.interval_minutes must be "
            f"{expected['interval_minutes']}"
        )
    if monitor.get("scope") != expected["scope"]:
        errors.append(
            f"{concept}: {path}.scope must be "
            f"{DIAGNOSTIC_CONCEPTS['current_session']} "
            f"({expected['scope']})"
        )


def _validate_counter(
    value: Any, path: str, maximum: int, concept: str, errors: list[str]
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > maximum
    ):
        errors.append(
            f"{concept}: {path} must be an integer in 0..{maximum}"
        )


def _validate_test_evidence(
    value: Any,
    *,
    issue_number: Any,
    test_sha: Any,
    path: str,
    errors: list[str],
) -> None:
    evidence = _mapping(value, path, errors)
    review_concept = DIAGNOSTIC_CONCEPTS["human_review_1"]
    if evidence.get("provider") != "github":
        errors.append(f"{review_concept}: {path}.provider must be github")
    _validate_required_text(
        evidence.get("repository"),
        f"{path}.repository",
        errors,
        review_concept,
    )
    if evidence.get("issue_number") != issue_number:
        errors.append(
            f"{review_concept}: {path}.issue_number must equal issue.number"
        )
    comment_id = evidence.get("comment_id")
    if isinstance(comment_id, bool) or not (
        isinstance(comment_id, int) and comment_id > 0 or _is_text(comment_id)
    ):
        errors.append(
            f"{review_concept} {DIAGNOSTIC_CONCEPTS['comment_id']}: "
            f"{path}.comment_id must identify "
            "the GitHub issue comment"
        )
    expected_command = f"/approve-test {test_sha}"
    if evidence.get("command") != expected_command:
        errors.append(
            f"{review_concept} {DIAGNOSTIC_CONCEPTS['approval_command']}: "
            f"{path}.command must be exactly "
            f"{expected_command}"
        )
    for invalidator in ("edited", "deleted", "request_changes"):
        if evidence.get(invalidator) is True:
            errors.append(
                f"{review_concept}: {path}.{invalidator} invalidates the approval"
            )


def _validate_legacy_record(record: Any) -> list[str]:
    """Return stable errors for a canonical record without modifying input."""

    if not isinstance(record, Mapping):
        return ["record must be a mapping"]

    errors: list[str] = []
    if record.get("version") != CONTRACT["version"]:
        errors.append(f"version must equal {CONTRACT['version']}")

    state = record.get("state")
    if not isinstance(state, str) or state not in STATE_INDEX:
        errors.append(f"state {state!r} is invalid; expected one of {list(STATES)}")
        state_index = -1
    else:
        state_index = STATE_INDEX[state]

    def at_least(required_state: str) -> bool:
        return state_index >= STATE_INDEX[required_state]

    issue = _mapping(record.get("issue"), "issue", errors)
    issue_number = issue.get("number")
    if isinstance(issue_number, bool) or not isinstance(issue_number, int):
        errors.append("issue.number must be an integer")
    primary_type = issue.get("primary_type")
    if not isinstance(primary_type, str) or primary_type not in TASK_CLASSES:
        errors.append(
            f"issue.primary_type ({DIAGNOSTIC_CONCEPTS['primary_type']}) "
            f"{primary_type!r} is invalid; "
            f"expected one of {sorted(TASK_CLASSES)}"
        )

    raw_flags = issue.get("impact_flags")
    flags: list[str] = []
    if not isinstance(raw_flags, list) or not raw_flags:
        errors.append(
            "issue.impact_flags "
            f"({DIAGNOSTIC_CONCEPTS['impact_flag']} list) must be a non-empty list"
        )
    else:
        flags = [flag for flag in raw_flags if isinstance(flag, str)]
        if len(flags) != len(raw_flags):
            errors.append(
                "issue.impact_flags "
                f"({DIAGNOSTIC_CONCEPTS['impact_flag']}) entries must be strings"
            )
        unknown_flags = sorted(set(flags) - IMPACT_FLAGS)
        if unknown_flags:
            errors.append(
                "issue.impact_flags "
                f"({DIAGNOSTIC_CONCEPTS['impact_flag']}) contains invalid values: "
                f"{unknown_flags}"
            )
        if len(flags) != len(set(flags)):
            errors.append(
                "issue.impact_flags "
                f"({DIAGNOSTIC_CONCEPTS['impact_flag']}) contains duplicate values"
            )

    gate = _mapping(record.get("gate"), "gate", errors)
    test_required = gate.get("test_required")
    if not isinstance(test_required, bool):
        errors.append("gate.test_required must be boolean")
    if test_required is False:
        light_profile = CONTRACT["light_path"]
        if primary_type != light_profile["primary_type"] or set(flags) != set(
            light_profile["impact_flags"]
        ):
            errors.append(
                "gate.light_path is not eligible; test_required false requires N + DO"
            )
        _validate_reason_block(gate.get("light_path"), "gate.light_path", errors)
    elif gate.get("light_path") is not None:
        errors.append("gate.light_path must be null when gate.test_required is true")

    lanes = _mapping(record.get("lanes"), "lanes", errors)
    lane_fields = (
        "base_sha",
        "test_sha",
        "implementation_base_sha",
        "implementation_sha",
        "candidate_sha",
    )
    for field in lane_fields:
        _validate_sha(lanes.get(field), f"lanes.{field}", errors)
    if lanes.get("implementation_base_sha") != lanes.get("base_sha"):
        errors.append(
            "lanes.implementation_base_sha must equal lanes.base_sha"
        )
    test_sha = lanes.get("test_sha")
    candidate_sha = lanes.get("candidate_sha")

    reviews = _mapping(record.get("human_reviews"), "human_reviews", errors)
    if test_required is not False:
        test_review = _mapping(
            reviews.get("test"), "human_reviews.test", errors
        )
        test_review_concept = DIAGNOSTIC_CONCEPTS["human_review_1"]
        test_approved = test_review.get("approved")
        if not isinstance(test_approved, bool):
            errors.append(
                f"{test_review_concept}: "
                "human_reviews.test.approved must be boolean"
            )
        _validate_sha(
            test_review.get("sha"),
            "human_reviews.test.sha",
            errors,
            test_review_concept,
        )
        if test_approved is True:
            if test_review.get("sha") != test_sha:
                errors.append(
                    f"{test_review_concept}: human_reviews.test.sha must equal "
                    "lanes.test_sha"
                )
            _validate_required_text(
                test_review.get("reviewer"),
                "human_reviews.test.reviewer",
                errors,
                test_review_concept,
            )
            _validate_test_evidence(
                test_review.get("evidence"),
                issue_number=issue_number,
                test_sha=test_sha,
                path="human_reviews.test.evidence",
                errors=errors,
            )
            _validate_monitor(
                test_review.get("monitor"),
                "human_reviews.test.monitor",
                errors,
                test_review_concept,
            )
        if (
            test_required is True
            and at_least("implementing")
            and test_approved is not True
        ):
            errors.append(
                f"{test_review_concept}: human_reviews.test.approved must be true "
                "before implementing"
            )

    final_review = _mapping(
        reviews.get("final"), "human_reviews.final", errors
    )
    final_review_concept = DIAGNOSTIC_CONCEPTS["final_human_review"]
    final_approved = final_review.get("approved")
    if not isinstance(final_approved, bool):
        errors.append(
            f"{final_review_concept}: human_reviews.final.approved must be boolean"
        )
    _validate_sha(
        final_review.get("sha"),
        "human_reviews.final.sha",
        errors,
        final_review_concept,
    )
    if final_approved is True:
        if final_review.get("sha") != candidate_sha:
            errors.append(
                f"{final_review_concept}: human_reviews.final.sha must equal "
                "lanes.candidate_sha"
            )
        _validate_required_text(
            final_review.get("reviewer"),
            "human_reviews.final.reviewer",
            errors,
            final_review_concept,
        )
        _validate_monitor(
            final_review.get("monitor"),
            "human_reviews.final.monitor",
            errors,
            final_review_concept,
        )
    if state == "complete" and final_approved is not True:
        errors.append(
            f"{final_review_concept}: human_reviews.final.approved must be true "
            "before complete"
        )
        if final_review.get("sha") != candidate_sha:
            errors.append(
                f"{final_review_concept}: human_reviews.final.sha must equal "
                "lanes.candidate_sha"
            )
        _validate_required_text(
            final_review.get("reviewer"),
            "human_reviews.final.reviewer",
            errors,
            final_review_concept,
        )
        _validate_monitor(
            final_review.get("monitor"),
            "human_reviews.final.monitor",
            errors,
            final_review_concept,
        )

    counters = _mapping(record.get("counters"), "counters", errors)
    counter_concepts = {
        "production_rework": DIAGNOSTIC_CONCEPTS["production_rework"],
        "kpi_optimization": DIAGNOSTIC_CONCEPTS["kpi_optimization"],
    }
    for field, concept in counter_concepts.items():
        _validate_counter(
            counters.get(field),
            f"counters.{field}",
            CONTRACT["limits"][field],
            concept,
            errors,
        )

    tester = _mapping(record.get("tester"), "tester", errors)
    tester_status = tester.get("status")
    if not isinstance(tester_status, str) or tester_status not in {"pass", "fail"}:
        errors.append("tester.status must be pass or fail")
    _validate_sha(tester.get("candidate_sha"), "tester.candidate_sha", errors)
    if tester.get("candidate_sha") != candidate_sha:
        errors.append("tester.candidate_sha must equal lanes.candidate_sha")

    reviewer = _mapping(record.get("reviewer"), "reviewer", errors)
    reviewer_status = reviewer.get("status")
    if not isinstance(reviewer_status, str) or reviewer_status not in {
        "pending",
        "pass",
        "fail",
    }:
        errors.append("reviewer.status must be pending, pass, or fail")
    _validate_sha(
        reviewer.get("candidate_sha"), "reviewer.candidate_sha", errors
    )
    if reviewer.get("candidate_sha") != candidate_sha:
        errors.append("reviewer.candidate_sha must equal lanes.candidate_sha")
    if reviewer_status == "pass" and tester_status != "pass":
        errors.append(
            f"{DIAGNOSTIC_CONCEPTS['tester_pass']} required: "
            "reviewer.status pass requires tester.status pass"
        )
    if at_least("reviewing") and tester_status != "pass":
        errors.append(
            f"{DIAGNOSTIC_CONCEPTS['tester_pass']} required: state {state} "
            "requires tester.status pass"
        )
    if at_least("final_human_review") and reviewer_status != "pass":
        errors.append(f"{state} requires reviewer.status pass")

    exception = record.get("exception")
    if exception is not None:
        _validate_reason_block(exception, "exception", errors)

    return sorted(set(errors))


def _validate_revision_id(
    value: Any, kind: str, path: str, errors: list[str]
) -> None:
    if not isinstance(value, str) or REVISION_ID_RE[kind].fullmatch(value) is None:
        errors.append(f"{path} must be a canonical {kind} revision identity")


def _validate_nonnegative_count(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{path} must be a non-negative integer")


def _validate_transition_record(
    value: Any, state: Any, errors: list[str]
) -> Mapping[str, Any]:
    transition = _mapping(value, "transition", errors)
    source = transition.get("from")
    target = transition.get("to")
    event = transition.get("event")
    transitions = LEGACY_TRANSITIONS
    if target != state:
        errors.append("transition.to must equal state")
    if not isinstance(source, str) or source not in transitions:
        errors.append("transition.from must name a canonical state")
        return transition
    if not isinstance(target, str) or target not in transitions:
        errors.append("transition.to must name a canonical state")
        return transition
    expected_event = transitions[source].get(target)
    if expected_event is None:
        errors.append(f"transition {source} -> {target} is not legal")
    elif event != expected_event:
        errors.append(
            f"transition.event must be {expected_event!r} for {source} -> {target}"
        )
    return transition


def _validate_canonical_gate(
    issue: Mapping[str, Any], gate: Mapping[str, Any], errors: list[str]
) -> tuple[Any, list[str]]:
    primary_type = issue.get("primary_type")
    raw_flags = issue.get("impact_flags")
    flags = raw_flags if isinstance(raw_flags, list) else []
    valid_flags = all(isinstance(flag, str) and flag in IMPACT_FLAGS for flag in flags)
    if (
        not isinstance(primary_type, str)
        or primary_type not in TASK_CLASSES
        or not flags
        or not valid_flags
    ):
        return gate.get("test_required"), flags

    derived = derive_gate_profile(primary_type, flags)
    for field in ("test_required", "required_gates", "profiles"):
        if gate.get(field) != derived[field]:
            errors.append(
                f"gate.{field} must equal the impact-derived value {derived[field]!r}"
            )
    test_required = gate.get("test_required")
    if test_required is False:
        _validate_reason_block(gate.get("light_path"), "gate.light_path", errors)
    elif gate.get("light_path") is not None:
        errors.append("gate.light_path must be null when tests are impact-derived")
    return test_required, flags


def _validate_canonical_revisions(
    value: Any, state: str, test_required: Any, errors: list[str]
) -> tuple[Any, Any, Any]:
    revisions = _mapping(value, "revisions", errors)
    base_sha = revisions.get("base_sha")
    _validate_sha(base_sha, "revisions.base_sha", errors)

    test = revisions.get("test")
    test_full_states = {
        "human_review_1", "implementing", "candidate", "testing", "rework",
        "reviewing", "final_human_review", "complete", "stopped",
    }
    if test_required is False:
        if test is not None:
            errors.append("revisions.test is inapplicable on the light path")
        test = None
    elif state in test_full_states:
        test = _mapping(test, "revisions.test", errors)
        _validate_revision_id(test.get("id"), "test", "revisions.test.id", errors)
        _validate_sha(test.get("sha"), "revisions.test.sha", errors)
        _validate_sha(test.get("base_sha"), "revisions.test.base_sha", errors)
        if test.get("base_sha") != base_sha:
            errors.append("revisions.test.base_sha must equal revisions.base_sha")
    elif test is not None:
        test = _mapping(test, "revisions.test", errors)
        _validate_revision_id(test.get("id"), "test", "revisions.test.id", errors)
        if test.get("sha") is not None:
            _validate_sha(test.get("sha"), "revisions.test.sha", errors)
        if test.get("base_sha") != base_sha:
            errors.append("revisions.test.base_sha must equal revisions.base_sha")

    implementation = revisions.get("implementation")
    implementation_full_states = {
        "candidate", "testing", "rework", "reviewing", "final_human_review",
        "complete", "stopped",
    }
    if state in implementation_full_states:
        implementation = _mapping(
            implementation, "revisions.implementation", errors
        )
        _validate_revision_id(
            implementation.get("id"),
            "implementation",
            "revisions.implementation.id",
            errors,
        )
        _validate_sha(
            implementation.get("sha"), "revisions.implementation.sha", errors
        )
        _validate_sha(
            implementation.get("base_sha"),
            "revisions.implementation.base_sha",
            errors,
        )
        if implementation.get("base_sha") != base_sha:
            errors.append(
                "revisions.implementation.base_sha must equal revisions.base_sha"
            )
    elif state == "implementing":
        implementation = _mapping(
            implementation, "revisions.implementation", errors
        )
        _validate_revision_id(
            implementation.get("id"),
            "implementation",
            "revisions.implementation.id",
            errors,
        )
        if implementation.get("sha") is not None:
            _validate_sha(
                implementation.get("sha"), "revisions.implementation.sha", errors
            )
        if implementation.get("base_sha") != base_sha:
            errors.append(
                "revisions.implementation.base_sha must equal revisions.base_sha"
            )
    elif implementation is not None:
        errors.append("revisions.implementation is future evidence for this state")

    candidate = revisions.get("candidate")
    candidate_states = {
        "candidate", "testing", "rework", "reviewing", "final_human_review",
        "complete", "stopped",
    }
    if state in candidate_states:
        candidate = _mapping(candidate, "revisions.candidate", errors)
        _validate_revision_id(
            candidate.get("id"), "candidate", "revisions.candidate.id", errors
        )
        _validate_sha(candidate.get("sha"), "revisions.candidate.sha", errors)
        _validate_sha(
            candidate.get("tree_sha"), "revisions.candidate.tree_sha", errors
        )
        if test_required is not False and isinstance(test, Mapping):
            if candidate.get("test_revision") != test.get("id"):
                errors.append(
                    "revisions.candidate.test_revision must equal revisions.test.id"
                )
        if isinstance(implementation, Mapping):
            if candidate.get("implementation_revision") != implementation.get("id"):
                errors.append(
                    "revisions.candidate.implementation_revision must equal "
                    "revisions.implementation.id"
                )
        parents = candidate.get("parents")
        expected_parents = {
            revision.get("sha")
            for revision in (test, implementation)
            if (
                isinstance(revision, Mapping)
                and isinstance(revision.get("sha"), str)
                and FULL_SHA_RE.fullmatch(revision.get("sha"))
            )
        }
        valid_parents = (
            isinstance(parents, list)
            and all(
                isinstance(parent, str) and FULL_SHA_RE.fullmatch(parent)
                for parent in parents
            )
        )
        if not valid_parents or len(parents) != len(expected_parents) or set(
            parents
        ) != expected_parents:
            errors.append(
                "revisions.candidate.parents must contain the exact Test and "
                "Implementation SHAs"
            )
    elif candidate is not None:
        errors.append("revisions.candidate is future evidence for this state")

    evidence = revisions.get("evidence")
    effective_sha = candidate.get("sha") if isinstance(candidate, Mapping) else None
    if evidence is not None:
        if state not in {"reviewing", "final_human_review", "complete"}:
            errors.append("revisions.evidence is future evidence for this state")
        evidence = _mapping(evidence, "revisions.evidence", errors)
        _validate_revision_id(
            evidence.get("id"), "evidence", "revisions.evidence.id", errors
        )
        _validate_sha(evidence.get("sha"), "revisions.evidence.sha", errors)
        if evidence.get("kind") != "evidence_only":
            errors.append("revisions.evidence.kind must be evidence_only")
        candidate_sha = candidate.get("sha") if isinstance(candidate, Mapping) else None
        for field in ("parent_sha", "base_candidate_sha"):
            if evidence.get(field) != candidate_sha:
                errors.append(
                    f"revisions.evidence.{field} must equal the exact Candidate SHA"
                )
        changed_paths = evidence.get("changed_paths")
        allowlist = set(
            CONTRACT["revision_provenance"]["evidence_only"]["allowed_paths"]
        )
        if (
            not isinstance(changed_paths, list)
            or not changed_paths
            or any(
                not isinstance(path, str) or path not in allowlist
                for path in changed_paths
            )
        ):
            errors.append(
                "revisions.evidence.changed_paths must stay within the "
                "evidence-only allowlist"
            )
        effective_sha = evidence.get("sha")
    return test, candidate, effective_sha


def _validate_strict_gate1(
    value: Any,
    *,
    state: str,
    issue_number: Any,
    repository: Any,
    test_revision: Any,
    errors: list[str],
) -> None:
    before_review = {"classify", "test_authoring"}
    if state in before_review:
        if value is not None:
            errors.append("human_reviews.test is future evidence for this state")
        return
    review = _mapping(value, "human_reviews.test", errors)
    decision = review.get("decision")
    if decision not in {"pending", "approved", "changes_requested"}:
        errors.append("human_reviews.test.decision is invalid")
        return
    if not isinstance(test_revision, Mapping):
        return
    test_sha = test_revision.get("sha")
    if review.get("sha") != test_sha:
        errors.append("human_reviews.test.sha must equal revisions.test.sha")
    if review.get("approved") is not (decision == "approved"):
        errors.append("human_reviews.test.approved must match decision")
    if decision == "pending":
        if state != "human_review_1":
            errors.append("Human Review 1 must be approved before implementing")
        return

    _validate_required_text(
        review.get("reviewer"), "human_reviews.test.reviewer", errors
    )
    evidence = _mapping(
        review.get("evidence"), "human_reviews.test.evidence", errors
    )
    expected = {
        "provider": "github",
        "repository": repository,
        "artifact": "issue_comment",
        "issue_number": issue_number,
        "top_level": True,
        "actor": review.get("reviewer"),
        "authorized_actor": True,
        "revision_sha": test_sha,
    }
    for field, expected_value in expected.items():
        if evidence.get(field) != expected_value:
            errors.append(
                f"human_reviews.test.evidence.{field} must equal {expected_value!r}"
            )
    _validate_required_text(
        evidence.get("repository"), "human_reviews.test.evidence.repository", errors
    )
    comment_id = evidence.get("comment_id")
    if isinstance(comment_id, bool) or not (
        isinstance(comment_id, int) and comment_id > 0 or _is_text(comment_id)
    ):
        errors.append("human_reviews.test.evidence.comment_id must identify a comment")
    if evidence.get("edited") is not False:
        errors.append("human_reviews.test.evidence.edited invalidates the decision")
    if evidence.get("deleted") is not False:
        errors.append("human_reviews.test.evidence.deleted invalidates the decision")
    if decision == "approved":
        expected_command = f"/approve-test {test_sha}"
        if evidence.get("command") != expected_command:
            errors.append(
                "human_reviews.test.evidence.command must be the exact approval command"
            )
        if evidence.get("request_changes") is not False:
            errors.append(
                "human_reviews.test.evidence.request_changes invalidates approval"
            )
    else:
        reason = evidence.get("reason")
        _validate_required_text(
            reason, "human_reviews.test.evidence.reason", errors
        )
        expected_command = f"/request-test-changes {test_sha}\n{reason}"
        if evidence.get("command") != expected_command:
            errors.append(
                "human_reviews.test.evidence.command must be the exact "
                "change-request command"
            )
        if evidence.get("request_changes") is not True:
            errors.append(
                "human_reviews.test.evidence.request_changes must be true"
            )
    _validate_monitor(
        review.get("monitor"),
        "human_reviews.test.monitor",
        errors,
        DIAGNOSTIC_CONCEPTS["human_review_1"],
    )
    if state not in {"human_review_1", "test_authoring"} and decision != "approved":
        errors.append("Human Review 1 must be approved before implementing")


def _validate_strict_final_review(
    value: Any,
    *,
    state: str,
    repository: Any,
    effective_sha: Any,
    errors: list[str],
) -> None:
    applicable = {"final_human_review", "complete"}
    if state not in applicable:
        if value is not None:
            errors.append("human_reviews.final is future evidence for this state")
        return
    review = _mapping(value, "human_reviews.final", errors)
    decision = review.get("decision")
    if decision not in {"pending", "approved", "changes_requested"}:
        errors.append("human_reviews.final.decision is invalid")
        return
    if review.get("sha") != effective_sha:
        errors.append(
            "human_reviews.final.sha must equal the exact Candidate or allowed "
            "evidence revision"
        )
    if review.get("approved") is not (decision == "approved"):
        errors.append("human_reviews.final.approved must match decision")
    if state == "complete" and decision != "approved":
        errors.append("Final Human Review must be approved before complete")
    if decision != "approved":
        return
    _validate_required_text(
        review.get("reviewer"), "human_reviews.final.reviewer", errors
    )
    evidence = _mapping(
        review.get("evidence"), "human_reviews.final.evidence", errors
    )
    expected = {
        "provider": "github",
        "repository": repository,
        "artifact": "pull_request_review",
        "actor": review.get("reviewer"),
        "authorized_actor": True,
        "revision_sha": effective_sha,
        "state": "APPROVED",
        "dismissed": False,
        "stale": False,
    }
    for field, expected_value in expected.items():
        if evidence.get(field) != expected_value:
            errors.append(
                f"human_reviews.final.evidence.{field} must equal {expected_value!r}"
            )
    _validate_required_text(
        evidence.get("repository"), "human_reviews.final.evidence.repository", errors
    )
    for field in ("pull_request_number", "review_id"):
        value = evidence.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append(
                f"human_reviews.final.evidence.{field} must be a positive integer"
            )
    _validate_monitor(
        review.get("monitor"),
        "human_reviews.final.monitor",
        errors,
        DIAGNOSTIC_CONCEPTS["final_human_review"],
    )


def _validate_corrections(
    value: Any, state: str, errors: list[str]
) -> Mapping[str, Any]:
    corrections = _mapping(value, "corrections", errors)
    for name in ("production_rework", "kpi_optimization"):
        entry = _mapping(corrections.get(name), f"corrections.{name}", errors)
        count = entry.get("count")
        maximum = CONTRACT["limits"][name]
        _validate_counter(
            count, f"corrections.{name}.count", maximum, name, errors
        )
        if name == "production_rework" and count == maximum:
            expected = (
                "stop_escalate" if state in {"rework", "stopped"} else "at_limit"
            )
        else:
            expected = "stop_escalate" if count == maximum else "continue"
        if entry.get("disposition") != expected:
            errors.append(
                f"corrections.{name}.disposition must be {expected} at count {count}"
            )
    for name in ("dependency_permission", "test_contract"):
        entry = _mapping(corrections.get(name), f"corrections.{name}", errors)
        count = entry.get("count")
        _validate_nonnegative_count(
            count, f"corrections.{name}.count", errors
        )
        audit = entry.get("audit")
        if (
            not isinstance(audit, list)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or len(audit) != count
            or any(not _is_text(item) for item in audit)
        ):
            errors.append(
                f"corrections.{name}.audit must contain one non-empty entry "
                "per correction"
            )
    production = corrections.get("production_rework")
    if state == "stopped" and isinstance(production, Mapping):
        if production.get("count") == CONTRACT["limits"]["production_rework"]:
            if production.get("disposition") != "stop_escalate":
                errors.append("production rework cap requires stop_escalate")
    return corrections


def _validate_canonical_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("version") != CONTRACT["version"]:
        errors.append(f"version must equal {CONTRACT['version']}")
    state = record.get("state")
    if not isinstance(state, str) or state not in STATE_INDEX:
        return [f"state {state!r} is invalid; expected one of {list(STATES)}"]
    if state != "classify":
        _validate_transition_record(record.get("transition"), state, errors)
    elif record.get("transition") is not None:
        errors.append("transition must be null in classify")

    issue = _mapping(record.get("issue"), "issue", errors)
    issue_number = issue.get("number")
    if isinstance(issue_number, bool) or not isinstance(issue_number, int):
        errors.append("issue.number must be an integer")
    repository = issue.get("repository")
    _validate_required_text(repository, "issue.repository", errors)
    primary_type = issue.get("primary_type")
    if not isinstance(primary_type, str) or primary_type not in TASK_CLASSES:
        errors.append("issue.primary_type must use a canonical primary type")
    raw_flags = issue.get("impact_flags")
    if (
        not isinstance(raw_flags, list)
        or not raw_flags
        or any(not isinstance(flag, str) or flag not in IMPACT_FLAGS for flag in raw_flags)
        or len(raw_flags) != len(set(raw_flags))
    ):
        errors.append("issue.impact_flags must be unique canonical impact flags")

    if state == "classify":
        future_fields = (
            "gate", "revisions", "human_reviews", "corrections", "tester",
            "reviewer", "stop", "exception",
        )
        for field in future_fields:
            if record.get(field) is not None:
                errors.append(f"{field} is future evidence for state classify")
        return sorted(set(errors))

    gate = _mapping(record.get("gate"), "gate", errors)
    test_required, _ = _validate_canonical_gate(issue, gate, errors)
    test_revision, candidate, effective_sha = _validate_canonical_revisions(
        record.get("revisions"), state, test_required, errors
    )

    reviews = _mapping(record.get("human_reviews"), "human_reviews", errors)
    if test_required is False:
        pass
    else:
        _validate_strict_gate1(
            reviews.get("test"),
            state=state,
            issue_number=issue_number,
            repository=repository,
            test_revision=test_revision,
            errors=errors,
        )
    _validate_strict_final_review(
        reviews.get("final"),
        state=state,
        repository=repository,
        effective_sha=effective_sha,
        errors=errors,
    )
    test_review = reviews.get("test")
    final_review = reviews.get("final")
    if (
        test_required is not False
        and isinstance(test_review, Mapping)
        and isinstance(final_review, Mapping)
    ):
        test_evidence = test_review.get("evidence")
        final_evidence = final_review.get("evidence")
        if isinstance(test_evidence, Mapping) and isinstance(final_evidence, Mapping):
            if final_evidence.get("repository") != test_evidence.get("repository"):
                errors.append(
                    "human_reviews.final.evidence.repository must equal "
                    "human_reviews.test.evidence.repository"
                )

    _validate_corrections(record.get("corrections"), state, errors)
    candidate_sha = candidate.get("sha") if isinstance(candidate, Mapping) else None
    tester = record.get("tester")
    if state in {"testing", "rework", "reviewing", "final_human_review", "complete"}:
        tester = _mapping(tester, "tester", errors)
        allowed = {"pending", "pass", "fail"} if state == "testing" else {"pass", "fail"}
        if tester.get("status") not in allowed:
            errors.append(f"tester.status is invalid for state {state}")
        if tester.get("candidate_sha") != candidate_sha:
            errors.append("tester.candidate_sha must equal revisions.candidate.sha")
        if state == "rework" and tester.get("status") != "fail":
            errors.append("rework requires tester.status fail")
        if (
            state in {"reviewing", "final_human_review", "complete"}
            and tester.get("status") != "pass"
        ):
            errors.append(f"{state} requires tester.status pass")
    elif tester is not None and state != "stopped":
        errors.append("tester is future evidence for this state")

    reviewer = record.get("reviewer")
    if state in {"reviewing", "final_human_review", "complete"}:
        reviewer = _mapping(reviewer, "reviewer", errors)
        allowed = {"pending", "pass", "fail"} if state == "reviewing" else {"pass"}
        if reviewer.get("status") not in allowed:
            errors.append(f"reviewer.status is invalid for state {state}")
        if reviewer.get("candidate_sha") != candidate_sha:
            errors.append("reviewer.candidate_sha must equal revisions.candidate.sha")
    elif reviewer is not None and state != "stopped":
        errors.append("reviewer is future evidence for this state")

    stop = record.get("stop")
    if state == "stopped":
        stop = _mapping(stop, "stop", errors)
        if stop.get("disposition") != "stop_escalate":
            errors.append("stop.disposition must be stop_escalate")
        _validate_required_text(stop.get("reason"), "stop.reason", errors)
    elif stop is not None:
        errors.append("stop is only legal in the stopped state")

    exception = record.get("exception")
    if exception is not None:
        _validate_reason_block(exception, "exception", errors)
    return sorted(set(errors))


def _path_value(record: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return False, None
        value = value[part]
    return value is not None, value


def _validate_public_revision(
    value: Any,
    *,
    kind: str,
    prefix: str,
    base_sha: Any,
    allow_null_sha: bool,
    errors: list[str],
) -> Mapping[str, Any]:
    path = f"revisions.{kind}"
    revision = _mapping(value, path, errors)
    iteration = revision.get("iteration")
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
        errors.append(f"{path}.iteration must be a positive integer")
    identity = revision.get("identity")
    if (
        not isinstance(iteration, int)
        or isinstance(iteration, bool)
        or identity != f"{prefix}{iteration}"
    ):
        errors.append(f"{path}.identity must equal {prefix}{{iteration}}")
    if revision.get("base_sha") != base_sha:
        errors.append(f"{path}.base_sha must equal revisions.base_sha")
    sha = revision.get("sha")
    if sha is None and allow_null_sha:
        pass
    else:
        _validate_sha(sha, f"{path}.sha", errors)
    return revision


def _validate_public_monitor(
    value: Any, *, path: str, expected_status: str, errors: list[str]
) -> None:
    monitor = _mapping(value, path, errors)
    if monitor.get("status") != expected_status:
        errors.append(f"{path}.status must be {expected_status}")
    if monitor.get("interval_minutes") != 10:
        errors.append(f"{path}.interval_minutes must be 10")
    if monitor.get("scope") != "current_session":
        errors.append(f"{path}.scope must be current_session (current session)")


def _validate_public_test_review(
    value: Any,
    *,
    required: bool,
    issue: Mapping[str, Any],
    test_sha: Any,
    errors: list[str],
) -> None:
    if value is None:
        if required:
            errors.append("human_reviews.test.evidence is required")
        return
    review = _mapping(value, "human_reviews.test", errors)
    approved = review.get("approved")
    if not isinstance(approved, bool):
        errors.append("human_reviews.test.approved must be boolean")
    if review.get("sha") != test_sha:
        errors.append("human_reviews.test.sha must equal the current Test SHA")
    _validate_required_text(
        review.get("reviewer"), "human_reviews.test.reviewer", errors
    )
    evidence = _mapping(
        review.get("evidence"), "human_reviews.test.evidence", errors
    )
    repository = evidence.get("repository")
    _validate_required_text(
        repository, "human_reviews.test.evidence.repository", errors
    )
    issue_repository = issue.get("repository")
    if issue_repository is not None and repository != issue_repository:
        errors.append(
            "human_reviews.test.evidence.repository must equal issue.repository"
        )
    expected = {
        "provider": "github",
        "artifact": "issue_comment",
        "issue_number": issue.get("number"),
        "top_level": True,
        "actor_type": "human",
        "current": True,
        "edited": False,
        "deleted": False,
        "requested_changes": approved is False,
    }
    concepts = {
        "issue_number": "issue number",
        "top_level": "top-level",
        "actor_type": "human",
        "current": "current",
        "edited": "edited",
        "deleted": "deleted",
        "requested_changes": "request",
    }
    for field, expected_value in expected.items():
        if evidence.get(field) != expected_value:
            errors.append(
                f"{concepts.get(field, field)}: "
                f"human_reviews.test.evidence.{field} must equal {expected_value!r}"
            )
    if evidence.get("test_sha") is not None and evidence.get("test_sha") != test_sha:
        errors.append("human_reviews.test.evidence.test_sha must equal review sha")
    comment_id = evidence.get("comment_id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        errors.append(
            "human_reviews.test.evidence.comment_id must be a usable comment id"
        )
    if approved is True:
        expected_command = f"/approve-test {test_sha}"
    elif approved is False:
        if evidence.get("decision") != "changes_requested":
            errors.append(
                "human_reviews.test.evidence.decision must be changes_requested"
            )
        reason = evidence.get("reason")
        _validate_required_text(reason, "human_reviews.test.evidence.reason", errors)
        expected_command = f"/request-test-changes {test_sha}\n{reason}"
    else:
        expected_command = None
    if evidence.get("command") != expected_command:
        errors.append(
            "human_reviews.test.evidence.command must be the exact approval or "
            "two-line request command"
        )
    _validate_public_monitor(
        review.get("monitor"),
        path="human_reviews.test.monitor",
        expected_status="stopped",
        errors=errors,
    )
    if required and approved is not True:
        errors.append("human_reviews.test.approved must be true before implementation")


def _validate_public_final_review(
    value: Any,
    *,
    state: str,
    issue: Mapping[str, Any],
    candidate_sha: Any,
    test_repository: Any,
    errors: list[str],
) -> None:
    if state == "final_human_review":
        review = _mapping(value, "human_reviews.final", errors)
        if review.get("evidence") is not None:
            errors.append("human_reviews.final.evidence is forbidden before approval")
        _validate_public_monitor(
            review.get("monitor"),
            path="human_reviews.final.monitor",
            expected_status="active",
            errors=errors,
        )
        return
    if state != "complete":
        if value is not None:
            errors.append("human_reviews.final is future evidence")
        return
    review = _mapping(value, "human_reviews.final", errors)
    if review.get("approved") is not True:
        errors.append("human_reviews.final.approved must be true")
    if review.get("sha") != candidate_sha:
        errors.append("human_reviews.final.sha must equal the exact Candidate SHA")
    _validate_required_text(
        review.get("reviewer"), "human_reviews.final.reviewer", errors
    )
    evidence = _mapping(review.get("evidence"), "human_reviews.final.evidence", errors)
    repository = evidence.get("repository")
    _validate_required_text(
        repository, "human_reviews.final.evidence.repository", errors
    )
    issue_repository = issue.get("repository")
    if issue_repository is not None and repository != issue_repository:
        errors.append(
            "human_reviews.final.evidence.repository must equal issue.repository"
        )
    expected = {
        "provider": "github",
        "artifact": "pull_request_review",
        "actor_type": "human",
        "current": True,
        "candidate_sha": candidate_sha,
    }
    concepts = {
        "actor_type": "human",
        "state": "approved",
        "current": "current",
        "candidate_sha": "candidate",
    }
    for field, expected_value in expected.items():
        if evidence.get(field) != expected_value:
            errors.append(
                f"{concepts.get(field, field)}: "
                f"human_reviews.final.evidence.{field} must equal {expected_value!r}"
            )
    state_value = evidence.get("state")
    if not isinstance(state_value, str) or state_value.lower() != "approved":
        errors.append(
            "approved: human_reviews.final.evidence.state must be approved"
        )
    for field in ("pull_request_number", "review_id"):
        value = evidence.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            errors.append(
                f"{'pull request' if field == 'pull_request_number' else 'review id'}: "
                f"human_reviews.final.evidence.{field} must be a positive integer"
            )
    issue_pull_request = issue.get("pull_request_number")
    if (
        issue_pull_request is not None
        and evidence.get("pull_request_number") != issue_pull_request
    ):
        errors.append(
            "human_reviews.final.evidence.pull_request_number must equal "
            "issue.pull_request_number"
        )
    if test_repository is not None and evidence.get("repository") != test_repository:
        errors.append(
            "human_reviews.final.evidence.repository must equal "
            "human_reviews.test.evidence.repository"
        )
    _validate_public_monitor(
        review.get("monitor"),
        path="human_reviews.final.monitor",
        expected_status="stopped",
        errors=errors,
    )


def _validate_public_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("version") != CONTRACT["version"]:
        errors.append(f"version must equal {CONTRACT['version']}")
    state = record.get("state")
    state_rules = {item["name"]: item for item in CONTRACT["state_machine"]["states"]}
    if not isinstance(state, str) or state not in state_rules:
        return [f"state {state!r} is invalid; expected one of {list(state_rules)}"]

    for path in state_rules[state]["required_fields"]:
        present, _ = _path_value(record, path)
        if not present:
            errors.append(f"{path} is required in state {state}")
    for path in state_rules[state]["forbidden_fields"]:
        present, _ = _path_value(record, path)
        if present:
            errors.append(f"{path} is forbidden in state {state}")

    issue = _mapping(record.get("issue"), "issue", errors)
    number = issue.get("number")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        errors.append("issue.number must be a usable positive issue number")
    if issue.get("repository") is not None:
        _validate_required_text(issue.get("repository"), "issue.repository", errors)
    primary_type = issue.get("primary_type")
    if not isinstance(primary_type, str) or primary_type not in TASK_CLASSES:
        errors.append("issue.primary_type must use a canonical primary type")
    flags = issue.get("impact_flags")
    flags_valid = not (
        not isinstance(flags, list)
        or not flags
        or any(not isinstance(flag, str) or flag not in IMPACT_FLAGS for flag in flags)
        or len(flags) != len(set(flags))
    )
    if not flags_valid:
        errors.append("issue.impact_flags must be unique canonical impact flags")

    gate = _mapping(record.get("gate"), "gate", errors)
    test_required = gate.get("test_required")
    if not isinstance(test_required, bool):
        errors.append("gate.test_required must be boolean")
    elif primary_type in TASK_CLASSES and flags_valid:
        expected = not (primary_type == "N" and set(flags) == {"DO"})
        if test_required is not expected:
            errors.append(f"gate.test_required must be {expected} for this classification")

    revisions = _mapping(record.get("revisions"), "revisions", errors)
    base_sha = revisions.get("base_sha")
    _validate_sha(base_sha, "revisions.base_sha", errors)
    test = revisions.get("test")
    if test is not None:
        test = _validate_public_revision(
            test,
            kind="test",
            prefix="T",
            base_sha=base_sha,
            allow_null_sha=state == "test_authoring",
            errors=errors,
        )
    implementation = revisions.get("implementation")
    if implementation is not None:
        implementation = _validate_public_revision(
            implementation,
            kind="implementation",
            prefix="W",
            base_sha=base_sha,
            allow_null_sha=state == "implementing",
            errors=errors,
        )
    candidate = revisions.get("candidate")
    candidate_sha = None
    if candidate is not None:
        candidate = _mapping(candidate, "revisions.candidate", errors)
        iteration = candidate.get("iteration")
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
            errors.append("revisions.candidate.iteration must be a positive integer")
        if candidate.get("identity") != f"C{iteration}":
            errors.append("revisions.candidate.identity must equal C{iteration}")
        candidate_sha = candidate.get("sha")
        _validate_sha(candidate_sha, "revisions.candidate.sha", errors)
        parents = _mapping(candidate.get("parents"), "revisions.candidate.parents", errors)
        expected_parents = {
            "test_sha": test.get("sha") if isinstance(test, Mapping) else None,
            "implementation_sha": (
                implementation.get("sha") if isinstance(implementation, Mapping) else None
            ),
        }
        for field, expected_value in expected_parents.items():
            if parents.get(field) != expected_value:
                errors.append(
                    f"revisions.candidate.parents.{field} must equal {expected_value!r}"
                )

    final_evidence = revisions.get("final_evidence")
    if final_evidence is not None:
        if state != "complete":
            errors.append("revisions.final_evidence is legal only in state complete")
        evidence = _mapping(final_evidence, "revisions.final_evidence", errors)
        _validate_required_text(
            evidence.get("identity"), "revisions.final_evidence.identity", errors
        )
        _validate_sha(evidence.get("sha"), "revisions.final_evidence.sha", errors)
        if evidence.get("reviewed_candidate_sha") != candidate_sha:
            errors.append(
                "revisions.final_evidence.reviewed_candidate_sha must equal "
                "revisions.candidate.sha"
            )
        changed_paths = evidence.get("changed_paths")
        allowed = {"agent-discipline/agent-lessons-learned.md"}
        if (
            not isinstance(changed_paths, list)
            or not changed_paths
            or any(path not in allowed for path in changed_paths)
        ):
            errors.append("revisions.final_evidence.changed_paths exceeds the allowlist")

    counters = _mapping(record.get("counters"), "counters", errors)
    for name in ("production_rework", "kpi_optimization"):
        _validate_counter(
            counters.get(name),
            f"counters.{name}",
            CONTRACT["limits"][name],
            name,
            errors,
        )

    reviews = record.get("human_reviews")
    reviews_map = reviews if isinstance(reviews, Mapping) else {}
    test_sha = test.get("sha") if isinstance(test, Mapping) else None
    test_review_required = state in {
        "implementing", "candidate", "testing", "rework", "reviewing",
        "final_human_review", "complete", "stopped",
    }
    _validate_public_test_review(
        reviews_map.get("test"),
        required=test_review_required,
        issue=issue,
        test_sha=test_sha,
        errors=errors,
    )
    test_repository = None
    if isinstance(reviews_map.get("test"), Mapping):
        test_evidence = reviews_map["test"].get("evidence")
        if isinstance(test_evidence, Mapping):
            test_repository = test_evidence.get("repository")
    _validate_public_final_review(
        reviews_map.get("final"),
        state=state,
        issue=issue,
        candidate_sha=candidate_sha,
        test_repository=test_repository,
        errors=errors,
    )

    tester = record.get("tester")
    if tester is not None:
        tester = _mapping(tester, "tester", errors)
        allowed = {
            "testing": {"pending", "pass", "fail"},
            "rework": {"fail"},
            "reviewing": {"pass"},
            "final_human_review": {"pass"},
            "complete": {"pass"},
        }.get(state, {"pending", "pass", "fail"})
        if tester.get("status") not in allowed:
            errors.append(f"tester.status is invalid for state {state}")
        if tester.get("candidate_sha") != candidate_sha:
            errors.append("tester.candidate_sha must equal revisions.candidate.sha")
    reviewer = record.get("reviewer")
    if reviewer is not None:
        reviewer = _mapping(reviewer, "reviewer", errors)
        allowed = {"pending", "pass", "fail", "not_run"}
        if reviewer.get("status") not in allowed:
            errors.append(f"reviewer.status is invalid for state {state}")
        if state in {"final_human_review", "complete"} and reviewer.get("status") != "pass":
            errors.append(f"reviewer.status must be pass in state {state}")
        if reviewer.get("candidate_sha") != candidate_sha:
            errors.append("reviewer.candidate_sha must equal revisions.candidate.sha")

    if state == "stopped":
        disposition = _mapping(record.get("disposition"), "disposition", errors)
        if disposition.get("status") != "stop_escalate":
            errors.append("disposition.status must be stop_escalate")
        _validate_required_text(disposition.get("reason"), "disposition.reason", errors)
    elif record.get("disposition") is not None:
        errors.append("disposition is legal only in state stopped")

    exception = record.get("exception")
    if exception is not None:
        _validate_reason_block(exception, "exception", errors)
    return sorted(set(errors))


def validate_record(record: Any) -> list[str]:
    """Return stable errors for public, historical canonical, or legacy records."""

    if not isinstance(record, Mapping):
        return ["record must be a mapping"]
    if "lanes" in record:
        return _validate_legacy_record(record)
    if "transition" in record or "corrections" in record:
        return _validate_canonical_record(record)
    return _validate_public_record(record)


def _revision_number(value: Any, prefix: str) -> int | None:
    if not isinstance(value, str) or not value.startswith(prefix):
        return None
    suffix = value[len(prefix):]
    return int(suffix) if suffix.isdigit() else None


def _validate_embedded_transition(previous: Any, current: Any) -> list[str]:
    """Validate two immutable snapshots and their exact lifecycle transition."""

    errors = [f"previous: {error}" for error in validate_record(previous)]
    errors.extend(f"current: {error}" for error in validate_record(current))
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return sorted(set(errors))
    transition = current.get("transition")
    if not isinstance(transition, Mapping):
        errors.append("current.transition must be a mapping")
        return sorted(set(errors))
    if transition.get("from") != previous.get("state"):
        errors.append("transition.from must equal previous.state")
    if transition.get("to") != current.get("state"):
        errors.append("transition.to must equal current.state")
    event = transition.get("event")
    previous_tester = previous.get("tester")
    previous_reviewer = previous.get("reviewer")
    previous_reviews = previous.get("human_reviews")
    previous_test_review = (
        previous_reviews.get("test")
        if isinstance(previous_reviews, Mapping)
        else None
    )
    previous_final_review = (
        previous_reviews.get("final")
        if isinstance(previous_reviews, Mapping)
        else None
    )
    outcome_requirements = {
        "functional_pass": (previous_tester, "pass", "tester.status"),
        "functional_failure": (previous_tester, "fail", "tester.status"),
        "test_approved": (previous_test_review, "approved", "decision"),
        "review_pass": (previous_reviewer, "pass", "reviewer.status"),
        "final_approved": (previous_final_review, "approved", "decision"),
    }
    if isinstance(event, str) and event in outcome_requirements:
        source, expected, field = outcome_requirements[event]
        key = field.rsplit(".", 1)[-1]
        if not isinstance(source, Mapping) or source.get(key) != expected:
            errors.append(f"{event} requires previous {field} {expected}")

    def candidate_sha(snapshot: Mapping[str, Any]) -> Any:
        revisions = snapshot.get("revisions")
        candidate = (
            revisions.get("candidate")
            if isinstance(revisions, Mapping)
            else None
        )
        return candidate.get("sha") if isinstance(candidate, Mapping) else None

    previous_candidate_sha = candidate_sha(previous)
    current_candidate_sha = candidate_sha(current)
    creates_candidate = (
        previous.get("state") == "implementing"
        and current.get("state") == "candidate"
    )
    invalidates_candidate = (
        previous.get("state") == "rework"
        and current.get("state") == "implementing"
        and current_candidate_sha is None
    )
    if (
        not creates_candidate
        and not invalidates_candidate
        and current_candidate_sha != previous_candidate_sha
    ):
        errors.append(
            "Candidate may change only on rework invalidation or implementing "
            "-> candidate creation; prior Candidate evidence is otherwise stale"
        )

    previous_corrections = previous.get("corrections")
    current_corrections = current.get("corrections")
    if isinstance(previous_corrections, Mapping) and isinstance(
        current_corrections, Mapping
    ):
        previous_production = previous_corrections.get("production_rework", {})
        current_production = current_corrections.get("production_rework", {})
        previous_count = (
            previous_production.get("count")
            if isinstance(previous_production, Mapping)
            else None
        )
        current_count = (
            current_production.get("count")
            if isinstance(current_production, Mapping)
            else None
        )
        is_rework = (
            previous.get("state") == "rework"
            and current.get("state") == "implementing"
        )
        if is_rework:
            if not isinstance(previous_count, int) or current_count != previous_count + 1:
                errors.append(
                    "production_rework.count must increment exactly once for "
                    "rework -> implementing"
                )
            if previous_count == CONTRACT["limits"]["production_rework"]:
                errors.append("production rework cap requires stopped/stop_escalate")
            previous_revisions = previous.get("revisions", {})
            current_revisions = current.get("revisions", {})
            old_implementation = (
                previous_revisions.get("implementation")
                if isinstance(previous_revisions, Mapping)
                else None
            )
            new_implementation = (
                current_revisions.get("implementation")
                if isinstance(current_revisions, Mapping)
                else None
            )
            old_id = (
                old_implementation.get("id")
                if isinstance(old_implementation, Mapping)
                else None
            )
            new_id = (
                new_implementation.get("id")
                if isinstance(new_implementation, Mapping)
                else None
            )
            old_number = _revision_number(old_id, "W")
            new_number = _revision_number(new_id, "W")
            if old_number is None or new_number != old_number + 1:
                errors.append("production_rework must create the next Wn revision")
        elif current_count != previous_count:
            errors.append(
                "production_rework.count may change only for rework -> implementing"
            )
        if (
            event == "rework_cap_reached"
            and previous_count != CONTRACT["limits"]["production_rework"]
        ):
            errors.append("rework_cap_reached requires production rework count 3")

    if (
        previous.get("state") == "human_review_1"
        and current.get("state") == "test_authoring"
    ):
        previous_reviews = previous.get("human_reviews", {})
        previous_review = (
            previous_reviews.get("test")
            if isinstance(previous_reviews, Mapping)
            else None
        )
        if not isinstance(previous_review, Mapping) or previous_review.get(
            "decision"
        ) != "changes_requested":
            errors.append("changes_requested transition requires a Gate 1 change request")
        previous_revisions = previous.get("revisions", {})
        current_revisions = current.get("revisions", {})
        old_test = (
            previous_revisions.get("test")
            if isinstance(previous_revisions, Mapping)
            else None
        )
        new_test = (
            current_revisions.get("test")
            if isinstance(current_revisions, Mapping)
            else None
        )
        old_id = old_test.get("id") if isinstance(old_test, Mapping) else None
        new_id = new_test.get("id") if isinstance(new_test, Mapping) else None
        old_number = _revision_number(old_id, "T")
        new_number = _revision_number(new_id, "T")
        if old_number is None or new_number != old_number + 1:
            errors.append("changes_requested must create the next Tn revision")
        previous_test_contract = (
            previous_corrections.get("test_contract", {})
            if isinstance(previous_corrections, Mapping)
            else {}
        )
        current_test_contract = (
            current_corrections.get("test_contract", {})
            if isinstance(current_corrections, Mapping)
            else {}
        )
        old_count = (
            previous_test_contract.get("count")
            if isinstance(previous_test_contract, Mapping)
            else None
        )
        new_count = (
            current_test_contract.get("count")
            if isinstance(current_test_contract, Mapping)
            else None
        )
        if not isinstance(old_count, int) or new_count != old_count + 1:
            errors.append(
                "test_contract.count must increment for changes_requested"
            )
    return sorted(set(errors))


def _public_revision_iteration(snapshot: Mapping[str, Any], kind: str) -> Any:
    revisions = snapshot.get("revisions")
    revision = revisions.get(kind) if isinstance(revisions, Mapping) else None
    return revision.get("iteration") if isinstance(revision, Mapping) else None


def _public_candidate_sha(snapshot: Mapping[str, Any]) -> Any:
    revisions = snapshot.get("revisions")
    candidate = revisions.get("candidate") if isinstance(revisions, Mapping) else None
    return candidate.get("sha") if isinstance(candidate, Mapping) else None


def _validate_public_transition(
    previous: Any, current: Any, event: Any
) -> list[str]:
    errors = [f"previous: {error}" for error in validate_record(previous)]
    errors.extend(f"current: {error}" for error in validate_record(current))
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        return sorted(set(errors))
    source = previous.get("state")
    target = current.get("state")
    legal = {
        (item["from"], item["to"], item["event"])
        for item in CONTRACT["state_machine"]["transitions"]
    }
    if (source, target, event) not in legal:
        errors.append(f"transition {source} -> {target} on {event!r} is not legal")
        return sorted(set(errors))

    previous_counters = previous.get("counters", {})
    current_counters = current.get("counters", {})
    previous_production = (
        previous_counters.get("production_rework")
        if isinstance(previous_counters, Mapping) else None
    )
    current_production = (
        current_counters.get("production_rework")
        if isinstance(current_counters, Mapping) else None
    )
    previous_kpi = (
        previous_counters.get("kpi_optimization")
        if isinstance(previous_counters, Mapping) else None
    )
    current_kpi = (
        current_counters.get("kpi_optimization")
        if isinstance(current_counters, Mapping) else None
    )
    if current_kpi != previous_kpi:
        errors.append("counters.kpi_optimization must be preserved by transitions")
    if event == "production_rework":
        if source != "rework":
            errors.append("production_rework requires state rework")
        elif target == "implementing":
            if previous_production == CONTRACT["limits"]["production_rework"]:
                errors.append("production rework cap requires stopped/stop_escalate")
            if (
                not isinstance(previous_production, int)
                or isinstance(previous_production, bool)
                or current_production != previous_production + 1
            ):
                errors.append("counters.production_rework must increment exactly once")
            previous_w = _public_revision_iteration(previous, "implementation")
            current_w = _public_revision_iteration(current, "implementation")
            if not isinstance(previous_w, int) or current_w != previous_w + 1:
                errors.append("production_rework must create the next W iteration")
            revisions = current.get("revisions")
            implementation = (
                revisions.get("implementation")
                if isinstance(revisions, Mapping) else None
            )
            if not isinstance(implementation, Mapping) or implementation.get("sha") is not None:
                errors.append("production_rework must start the next uncommitted W revision")
        else:
            if previous_production != CONTRACT["limits"]["production_rework"]:
                errors.append("stopped requires production rework count 3")
            if current_production != previous_production:
                errors.append("stopped must preserve production rework count 3")
    elif current_production != previous_production:
        errors.append("counters.production_rework may change only on production_rework")

    if event in {"dependency_blocked", "permission_blocked"}:
        if current.get("revisions") != previous.get("revisions"):
            errors.append(f"{event} must preserve revisions")
        if current.get("counters") != previous.get("counters"):
            errors.append(f"{event} must preserve counters")
    if event == "changes_requested" and source == "human_review_1":
        reviews = previous.get("human_reviews")
        review = reviews.get("test") if isinstance(reviews, Mapping) else None
        evidence = review.get("evidence") if isinstance(review, Mapping) else None
        if (
            not isinstance(review, Mapping)
            or review.get("approved") is not False
            or not isinstance(evidence, Mapping)
            or evidence.get("decision") != "changes_requested"
        ):
            errors.append("changes_requested requires Human Review 1 change evidence")
        previous_t = _public_revision_iteration(previous, "test")
        current_t = _public_revision_iteration(current, "test")
        if not isinstance(previous_t, int) or current_t != previous_t + 1:
            errors.append("changes_requested must create the next T iteration")
        revisions = current.get("revisions")
        test = revisions.get("test") if isinstance(revisions, Mapping) else None
        if not isinstance(test, Mapping) or test.get("sha") is not None:
            errors.append("changes_requested must start the next uncommitted T revision")
    if event == "tester_failed":
        tester = previous.get("tester")
        if not isinstance(tester, Mapping) or tester.get("status") != "fail":
            errors.append("tester_failed requires previous tester.status fail")
    if event == "tester_passed":
        tester = previous.get("tester")
        if not isinstance(tester, Mapping) or tester.get("status") != "pass":
            errors.append("tester_passed requires previous tester.status pass")
    if event == "test_approved":
        reviews = current.get("human_reviews")
        review = reviews.get("test") if isinstance(reviews, Mapping) else None
        if not isinstance(review, Mapping) or review.get("approved") is not True:
            errors.append("test_approved requires approved Human Review 1 evidence")
    if event == "reviewer_passed":
        reviewer = current.get("reviewer")
        if not isinstance(reviewer, Mapping) or reviewer.get("status") != "pass":
            errors.append("reviewer_passed requires reviewer.status pass")
    if event == "final_approved":
        reviews = current.get("human_reviews")
        review = reviews.get("final") if isinstance(reviews, Mapping) else None
        if not isinstance(review, Mapping) or review.get("approved") is not True:
            errors.append("final_approved requires approved final review evidence")
    if event == "candidate_revised":
        old_sha = _public_candidate_sha(previous)
        new_sha = _public_candidate_sha(current)
        if not isinstance(new_sha, str) or new_sha == old_sha:
            errors.append("candidate_revised requires a new Candidate SHA")
        old_iteration = _public_revision_iteration(previous, "candidate")
        new_iteration = _public_revision_iteration(current, "candidate")
        if (
            not isinstance(old_iteration, int)
            or not isinstance(new_iteration, int)
            or isinstance(old_iteration, bool)
            or isinstance(new_iteration, bool)
            or new_iteration <= old_iteration
        ):
            errors.append("candidate_revised requires a later Candidate iteration")
        tester = current.get("tester")
        reviewer = current.get("reviewer")
        if not isinstance(tester, Mapping) or tester.get("status") != "pending":
            errors.append("candidate_revised requires tester.status pending")
        if not isinstance(reviewer, Mapping) or reviewer.get("status") != "not_run":
            errors.append("candidate_revised requires reviewer.status not_run")
        if isinstance(tester, Mapping) and tester.get("candidate_sha") != new_sha:
            errors.append("candidate_revised tester evidence must bind the new SHA")
        if isinstance(reviewer, Mapping) and reviewer.get("candidate_sha") != new_sha:
            errors.append("candidate_revised reviewer evidence must bind the new SHA")
        revisions = current.get("revisions")
        if isinstance(revisions, Mapping) and revisions.get("final_evidence") is not None:
            errors.append("candidate_revised invalidates revisions.final_evidence")
    return sorted(set(errors))


def validate_transition(
    previous: Any, current: Any, event: Any | None = None
) -> list[str]:
    """Validate a public event transition or a historical embedded transition."""

    if event is None:
        return _validate_embedded_transition(previous, current)
    return _validate_public_transition(previous, current, event)


def _emit_result(
    ok: bool, errors: list[str], error_type: str | None
) -> None:
    print(
        json.dumps(
            {
                "ok": ok,
                "errors": errors,
                "error_type": error_type,
            },
            indent=2,
        )
    )


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        _emit_result(False, [f"invocation input error: {message}"], "input")
        raise SystemExit(2)


def _build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(
        description="Validate a JSON record against the Agent workflow contract."
    )
    parser.add_argument(
        "--json",
        required=True,
        dest="record",
        help="JSON record path, or '-' to read standard input.",
    )
    parser.add_argument(
        "--previous",
        help="Previous JSON record path for executable transition validation.",
    )
    return parser


def _read_json_record(source: str) -> tuple[Any, str | None]:
    try:
        if source == "-":
            return json.load(sys.stdin), None
        return json.loads(Path(source).read_text(encoding="utf-8")), None
    except UnicodeError:
        return None, "input encoding error: record must be valid UTF-8"
    except json.JSONDecodeError:
        return None, "input JSON error: record must contain valid JSON"
    except FileNotFoundError:
        return None, f"input path error: record path does not exist: {source}"
    except PermissionError:
        return None, f"input path error: record path is not readable: {source}"
    except OSError:
        return None, f"input path error: record path could not be read: {source}"


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    record, input_error = _read_json_record(args.record)
    if input_error is not None:
        _emit_result(False, [input_error], "input")
        return 2

    if args.previous:
        previous, previous_error = _read_json_record(args.previous)
        if previous_error is not None:
            _emit_result(False, [f"previous {previous_error}"], "input")
            return 2
        errors = validate_transition(previous, record)
    else:
        errors = validate_record(record)
    _emit_result(not errors, errors, "validation" if errors else None)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
