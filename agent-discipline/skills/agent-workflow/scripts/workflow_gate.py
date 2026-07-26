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
# Version:     0.5.0
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

    routing = CONTRACT["impact_routing"]
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


def _validate_revision_id(
    value: Any, kind: str, path: str, errors: list[str]
) -> None:
    if not isinstance(value, str) or not REVISION_ID_RE[kind].fullmatch(value):
        errors.append(f"{path} must match the canonical {kind} identity")


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
    value: Any,
    *,
    path: str,
    expected_status: str | tuple[str, ...],
    errors: list[str],
) -> None:
    monitor = _mapping(value, path, errors)
    allowed_statuses = (
        (expected_status,) if isinstance(expected_status, str) else expected_status
    )
    if monitor.get("status") not in allowed_statuses:
        errors.append(f"{path}.status must be {' or '.join(allowed_statuses)}")
    if monitor.get("interval_minutes") != 10:
        errors.append(f"{path}.interval_minutes must be 10")
    if monitor.get("scope") != "current_session":
        errors.append(f"{path}.scope must be current_session (current session)")


def _public_change_request_reason(
    evidence: Mapping[str, Any], test_sha: Any
) -> str | None:
    command = evidence.get("command")
    if not isinstance(command, str):
        return None
    lines = command.split("\n")
    if (
        len(lines) != 2
        or lines[0] != f"/request-test-changes {test_sha}"
        or not lines[1].strip()
    ):
        return None
    command_reason = lines[1]
    decision = evidence.get("decision")
    stated_reason = evidence.get("reason")
    encoding_a = (
        evidence.get("requested_changes") is True
        and decision in (None, "changes_requested")
        and stated_reason in (None, command_reason)
    )
    encoding_b = (
        decision == "changes_requested"
        and stated_reason == command_reason
        and evidence.get("requested_changes") is not True
    )
    return command_reason if encoding_a or encoding_b else None


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
    if review.get("evidence") is None:
        if approved is not False:
            errors.append("pending Human Review 1 must have approved false")
        if review.get("reviewer") is not None:
            errors.append("pending Human Review 1 reviewer must be null")
        _validate_public_monitor(
            review.get("monitor"),
            path="human_reviews.test.monitor",
            expected_status="active",
            errors=errors,
        )
        if required:
            errors.append(
                "human_reviews.test.evidence is required before implementation"
            )
        return
    if approved is True:
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
    }
    concepts = {
        "issue_number": "issue number",
        "top_level": "top-level",
        "actor_type": "human",
        "current": "current",
        "edited": "edited",
        "deleted": "deleted",
    }
    for field, expected_value in expected.items():
        if evidence.get(field) != expected_value:
            errors.append(
                f"{concepts.get(field, field)}: "
                f"human_reviews.test.evidence.{field} must equal {expected_value!r}"
            )
    if evidence.get("test_sha") is not None and evidence.get("test_sha") != test_sha:
        errors.append("human_reviews.test.evidence.test_sha must equal review sha")
    if approved is True and evidence.get("requested_changes") is not False:
        errors.append(
            "request: approved Human Review 1 requires requested_changes false"
        )
    comment_id = evidence.get("comment_id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int) or comment_id <= 0:
        errors.append(
            "human_reviews.test.evidence.comment_id must be a usable comment id"
        )
    if approved is True:
        expected_command = f"/approve-test {test_sha}"
    elif approved is False:
        reason = _public_change_request_reason(evidence, test_sha)
        if reason is None:
            errors.append(
                "human_reviews.test.evidence must use either requested_changes "
                "or matching changes_requested decision/reason evidence"
            )
            expected_command = None
        else:
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
        expected_status=("active", "stopped") if approved is False else "stopped",
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
    if record.get("schema") != CONTRACT["schema"]:
        errors.append(
            f"schema must equal the canonical machine ID {CONTRACT['schema']!r}"
        )
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
    if test_required is False:
        if state in {"test_authoring", "human_review_1"}:
            errors.append(
                f"state {state} is forbidden when gate.test_required is false"
            )
        light_path = _mapping(gate.get("light_path"), "gate.light_path", errors)
        _validate_reason_block(light_path, "gate.light_path", errors)
        remaining = light_path.get("remaining_verification")
        if (
            not isinstance(remaining, list)
            or not remaining
            or any(not _is_text(item) for item in remaining)
        ):
            errors.append(
                "gate.light_path.remaining_verification must be a non-empty "
                "list of non-empty actions"
            )
    elif gate.get("light_path") is not None:
        errors.append("gate.light_path is forbidden when gate.test_required is true")

    revisions = _mapping(record.get("revisions"), "revisions", errors)
    base_sha = revisions.get("base_sha")
    _validate_sha(base_sha, "revisions.base_sha", errors)
    test = revisions.get("test")
    if test_required is False and test is not None:
        errors.append("revisions.test is forbidden when gate.test_required is false")
    standard_test_states = {
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
    }
    if test_required is True and state in standard_test_states and test is None:
        errors.append(f"revisions.test is required in state {state}")
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
        expected_parents = (
            {
                "base_sha": base_sha,
                "implementation_sha": (
                    implementation.get("sha")
                    if isinstance(implementation, Mapping)
                    else None
                ),
            }
            if test_required is False
            else {
                "test_sha": test.get("sha") if isinstance(test, Mapping) else None,
                "implementation_sha": (
                    implementation.get("sha")
                    if isinstance(implementation, Mapping)
                    else None
                ),
            }
        )
        if set(parents) != set(expected_parents):
            errors.append(
                "revisions.candidate.parents must contain exactly "
                + (
                    "base_sha and implementation_sha"
                    if test_required is False
                    else "test_sha and implementation_sha"
                )
            )
        for field, expected_value in expected_parents.items():
            if parents.get(field) != expected_value:
                errors.append(
                    f"revisions.candidate.parents.{field} must equal {expected_value!r}"
                )

    final_evidence = revisions.get("final_evidence")
    if final_evidence is not None:
        if state != "complete":
            errors.append(
                "revisions.final_evidence is future evidence before "
                "state complete"
            )
        evidence = _mapping(final_evidence, "revisions.final_evidence", errors)
        _validate_revision_id(
            evidence.get("identity"),
            "evidence",
            "revisions.final_evidence.identity",
            errors,
        )
        _validate_sha(evidence.get("sha"), "revisions.final_evidence.sha", errors)
        if evidence.get("reviewed_candidate_sha") != candidate_sha:
            errors.append(
                "revisions.final_evidence.reviewed_candidate_sha must equal "
                "revisions.candidate.sha"
            )
        changed_paths = evidence.get("changed_paths")
        allowed = set(
            CONTRACT["revision_provenance"]["evidence_only"]["allowed_paths"]
        )
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
    test_review_required = test_required is True and state in {
        "implementing", "candidate", "testing", "rework", "reviewing",
        "final_human_review", "complete", "stopped",
    }
    if test_required is False and reviews_map.get("test") is not None:
        errors.append(
            "human_reviews.test is forbidden when gate.test_required is false"
        )
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
        if test_required is False:
            if tester.get("mode") != CONTRACT["light_path"]["testing_mode"]:
                errors.append(
                    "tester.mode must be mechanical_verification when "
                    "gate.test_required is false"
                )
        elif tester.get("mode") == CONTRACT["light_path"]["testing_mode"]:
            errors.append(
                "tester.mode mechanical_verification is reserved for the "
                "N + DO no-Test path"
            )
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
    """Return stable errors for the one canonical version 2 record schema."""

    if not isinstance(record, Mapping):
        return ["record must be a mapping"]
    version = record.get("version")
    if version == 1:
        return [
            "workflow record version 1 is unsupported; "
            "expected canonical version 2"
        ]
    if version != CONTRACT["version"]:
        return [
            f"workflow record version {version!r} is unsupported; "
            f"expected canonical version {CONTRACT['version']}"
        ]
    errors = _validate_public_record(record)
    for marker in ("lanes", "transition", "corrections"):
        if marker in record:
            errors.append(
                f"{marker} is a legacy record marker forbidden by canonical version 2"
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
    previous_gate = previous.get("gate")
    test_required = (
        previous_gate.get("test_required")
        if isinstance(previous_gate, Mapping)
        else None
    )
    if source == "classify":
        expected_target = "test_authoring" if test_required is True else "implementing"
        if target != expected_target:
            errors.append(
                f"classification_complete must enter {expected_target} when "
                f"gate.test_required is {str(test_required).lower()}"
            )
    if source == "candidate" and target == "testing":
        expected_event = (
            "mechanical_verification_started"
            if test_required is False
            else "testing_started"
        )
        if event != expected_event:
            errors.append(
                f"candidate -> testing must use {expected_event!r} when "
                f"gate.test_required is {str(test_required).lower()}"
            )

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
            if current.get("revisions") != previous.get("revisions"):
                errors.append(
                    "stopped must preserve revisions and must not create a fourth W"
                )
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
            or _public_change_request_reason(evidence, review.get("sha")) is None
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
        previous_tester = previous.get("tester")
        current_tester = current.get("tester")
        if (
            not isinstance(previous_tester, Mapping)
            or previous_tester.get("status") != "pending"
        ):
            errors.append("tester_passed requires previous tester.status pending")
        if (
            not isinstance(current_tester, Mapping)
            or current_tester.get("status") != "pass"
        ):
            errors.append("tester_passed requires current tester.status pass")
        candidate_sha = _public_candidate_sha(current)
        if (
            _public_candidate_sha(previous) != candidate_sha
            or not isinstance(current_tester, Mapping)
            or current_tester.get("candidate_sha") != candidate_sha
        ):
            errors.append("tester_passed must preserve the exact Candidate binding")
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
        if reviewer is not None:
            errors.append("candidate_revised must remove stale reviewer evidence")
        if isinstance(tester, Mapping) and tester.get("candidate_sha") != new_sha:
            errors.append("candidate_revised tester evidence must bind the new SHA")
        revisions = current.get("revisions")
        if isinstance(revisions, Mapping) and revisions.get("final_evidence") is not None:
            errors.append("candidate_revised invalidates revisions.final_evidence")
    return sorted(set(errors))


def validate_transition(previous: Any, current: Any, event: Any) -> list[str]:
    """Validate one canonical version 2 event transition."""

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
    parser.add_argument(
        "--event",
        help="Canonical event for executable transition validation.",
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
    if bool(args.previous) != bool(args.event):
        _build_parser().error(
            "--previous and --event must be provided together"
        )
    record, input_error = _read_json_record(args.record)
    if input_error is not None:
        _emit_result(False, [input_error], "input")
        return 2

    if args.previous:
        previous, previous_error = _read_json_record(args.previous)
        if previous_error is not None:
            _emit_result(False, [f"previous {previous_error}"], "input")
            return 2
        errors = validate_transition(previous, record, args.event)
    else:
        errors = validate_record(record)
    _emit_result(not errors, errors, "validation" if errors else None)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
