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
# Version:     0.2.0
# Description: Validate canonical nested Agent workflow records without mutation.
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


def validate_record(record: Any) -> list[str]:
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a JSON record against the Agent workflow contract."
    )
    parser.add_argument(
        "record",
        nargs="?",
        default="-",
        help="JSON record path, or '-' to read standard input (default).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.record == "-":
            record = json.load(sys.stdin)
        else:
            record = json.loads(Path(args.record).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2

    errors = validate_record(record)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
