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
# Version:     0.1.0
# Description: Validate records against the canonical Agent workflow contract.
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
TASK_TYPES = frozenset(CONTRACT["task_types"])
IMPACT_FLAGS = frozenset(CONTRACT["impact_flags"])
STATES = tuple(CONTRACT["state_machine"]["sequence"])
STATE_INDEX = {name: index for index, name in enumerate(STATES)}


def _is_nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_sha(record: Mapping[str, Any], field: str, errors: list[str]) -> None:
    value = record.get(field)
    if not isinstance(value, str) or FULL_SHA_RE.fullmatch(value) is None:
        errors.append(f"{field} must be a full 40-hex SHA")


def _validate_comment(
    evidence: Any,
    *,
    field: str,
    bound_sha: Any,
    command_name: str,
    errors: list[str],
) -> None:
    if not isinstance(evidence, Mapping):
        errors.append(f"{field} must contain GitHub top-level comment evidence")
        return

    if evidence.get("sha") != bound_sha:
        bound_field = "test_sha" if field == "test_approval" else "candidate_sha"
        errors.append(f"{field}.sha must equal {bound_field}")
    expected_command = f"/{command_name} {bound_sha}"
    if evidence.get("command") != expected_command:
        errors.append(f"{field}.command must be exactly {expected_command}")
    if evidence.get("location") != CONTRACT["human_review"]["evidence_location"]:
        errors.append(f"{field}.location must be github_issue_top_level_comment")
    if evidence.get("author_type") != CONTRACT["human_review"]["authorized_author_type"]:
        errors.append(f"{field}.author_type must be human")

    comment_id = evidence.get("comment_id")
    if isinstance(comment_id, bool) or not (
        isinstance(comment_id, int) and comment_id > 0
        or _is_nonempty_text(comment_id)
    ):
        errors.append(f"{field}.comment_id must identify the GitHub issue comment")
    if not _is_nonempty_text(evidence.get("comment_url")):
        errors.append(f"{field}.comment_url is required")
    if not _is_nonempty_text(evidence.get("author_login")):
        errors.append(f"{field}.author_login is required")
    if not _is_nonempty_text(evidence.get("created_at")):
        errors.append(f"{field}.created_at is required")
    if evidence.get("edited") is not False:
        errors.append(f"{field}.edited must be false")
    if evidence.get("deleted") is not False:
        errors.append(f"{field}.deleted must be false")


def _validate_monitor(
    monitor: Any,
    *,
    field: str,
    require_stopped: bool,
    errors: list[str],
) -> None:
    if not isinstance(monitor, Mapping):
        errors.append(f"{field} must record the Human Review monitor")
        return

    expected_window = CONTRACT["human_review"]["monitor"]["window_minutes"]
    if monitor.get("window_minutes") != expected_window:
        errors.append(f"{field}.window_minutes must be {expected_window}")
    if monitor.get("same_session") is not True:
        errors.append(f"{field}.same_session must be true")
    if monitor.get("new_session") is not False:
        errors.append(f"{field}.new_session must be false")

    status = monitor.get("status")
    if status not in {"polling", "no_update", "stopped"}:
        errors.append(f"{field}.status must be polling, no_update, or stopped")
    valid_update = monitor.get("valid_update_received")
    if not isinstance(valid_update, bool):
        errors.append(f"{field}.valid_update_received must be boolean")
    if valid_update is True and status != "stopped":
        errors.append(f"{field}.status must be stopped before continuing")
    if require_stopped:
        if valid_update is not True:
            errors.append(f"{field}.valid_update_received must be true before continuing")
        if status != "stopped":
            errors.append(f"{field}.status must be stopped before continuing")


def _validate_count(
    record: Mapping[str, Any], field: str, maximum: int, errors: list[str]
) -> None:
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{field} must be a non-negative integer")
    elif value > maximum:
        errors.append(f"{field} exceeds maximum {maximum}; stop and escalate to a human")


def _validate_candidate_evidence(
    evidence: Any,
    *,
    field: str,
    candidate_sha: Any,
    require_pass: bool,
    errors: list[str],
) -> None:
    if not isinstance(evidence, Mapping):
        errors.append(f"{field} is required")
        return
    verdict = evidence.get("verdict")
    if not _is_nonempty_text(verdict):
        errors.append(f"{field}.verdict is required")
    elif require_pass and verdict != "PASS":
        errors.append(f"{field}.verdict must be PASS")
    if evidence.get("candidate_sha") != candidate_sha:
        errors.append(f"{field}.candidate_sha must equal candidate_sha")


def validate_record(record: Any) -> list[str]:
    """Return stable validation errors without modifying *record*.

    Ordinary malformed input is represented by readable errors. The function
    never normalizes, annotates, or otherwise writes into the supplied value.
    """

    if not isinstance(record, Mapping):
        return ["record must be a mapping"]

    errors: list[str] = []
    if record.get("contract_version") != CONTRACT["version"]:
        errors.append(
            f"contract_version must equal canonical version {CONTRACT['version']}"
        )

    task_type = record.get("task_type")
    if not isinstance(task_type, str) or task_type not in TASK_TYPES:
        errors.append(
            f"task_type {task_type!r} is invalid; expected one of {sorted(TASK_TYPES)}"
        )

    raw_flags = record.get("impact_flags")
    flags: list[str] = []
    if not isinstance(raw_flags, list):
        errors.append("impact_flags must be a non-empty list")
    else:
        flags = [flag for flag in raw_flags if isinstance(flag, str)]
        if not raw_flags:
            errors.append("impact_flags must be a non-empty list")
        if len(flags) != len(raw_flags):
            errors.append("impact_flags entries must be strings")
        unknown = sorted(set(flags) - IMPACT_FLAGS)
        if unknown:
            errors.append(f"impact_flags contains invalid values: {unknown}")
        if len(flags) != len(set(flags)):
            errors.append("impact_flags contains duplicate values")

    state = record.get("state")
    if not isinstance(state, str) or state not in STATE_INDEX:
        errors.append(f"state {state!r} is invalid; expected one of {list(STATES)}")
        state_index = -1
    else:
        state_index = STATE_INDEX[state]

    def at_least(name: str) -> bool:
        return state_index >= STATE_INDEX[name]

    test_path = record.get("test_path")
    if not isinstance(test_path, str) or test_path not in CONTRACT["test_paths"]:
        errors.append("test_path must be standard or lightweight")
    lightweight = test_path == "lightweight"

    exception = record.get("exception")
    if lightweight:
        profile = CONTRACT["test_paths"]["lightweight"]
        eligible = (
            task_type in profile["eligible_task_types"]
            and bool(flags)
            and set(flags) <= set(profile["allowed_impact_flags"])
        )
        if not eligible:
            errors.append(
                "lightweight test_path is not eligible for this task_type and impact_flags"
            )
    if lightweight or exception is not None:
        if not isinstance(exception, Mapping):
            errors.append("exception must record the lightweight-path justification")
        else:
            required_fields = CONTRACT["test_paths"]["lightweight"][
                "required_exception_fields"
            ]
            for field in required_fields:
                if not _is_nonempty_text(exception.get(field)):
                    errors.append(f"exception.{field} must be non-empty")

    if at_least("test_authoring"):
        _validate_sha(record, "base_sha", errors)
    if not lightweight and at_least("test_authoring"):
        _validate_sha(record, "test_base_sha", errors)
        if record.get("test_base_sha") != record.get("base_sha"):
            errors.append("test_base_sha must equal base_sha")
    if not lightweight and at_least("human_review_gate_1"):
        _validate_sha(record, "test_sha", errors)
    if at_least("implementing"):
        _validate_sha(record, "implementation_base_sha", errors)
        if record.get("implementation_base_sha") != record.get("base_sha"):
            errors.append("implementation_base_sha must equal base_sha")
    if at_least("candidate"):
        _validate_sha(record, "implementation_sha", errors)
        _validate_sha(record, "candidate_sha", errors)

    monitors = record.get("monitors")
    if monitors is not None and not isinstance(monitors, Mapping):
        errors.append("monitors must be a mapping")
        monitors = {}
    elif monitors is None:
        monitors = {}

    if not lightweight and at_least("implementing"):
        _validate_comment(
            record.get("test_approval"),
            field="test_approval",
            bound_sha=record.get("test_sha"),
            command_name="approve-test",
            errors=errors,
        )
        _validate_monitor(
            monitors.get("test_review"),
            field="monitors.test_review",
            require_stopped=True,
            errors=errors,
        )
    elif not lightweight and at_least("human_review_gate_1"):
        _validate_monitor(
            monitors.get("test_review"),
            field="monitors.test_review",
            require_stopped=False,
            errors=errors,
        )

    _validate_count(
        record,
        "production_rework_count",
        CONTRACT["iteration_limits"]["production_rework"],
        errors,
    )
    _validate_count(
        record,
        "kpi_optimization_count",
        CONTRACT["iteration_limits"]["kpi_optimization"],
        errors,
    )

    candidate_sha = record.get("candidate_sha")
    tester_evidence = record.get("tester_evidence")
    reviewer_evidence = record.get("reviewer_evidence")
    if tester_evidence is not None:
        _validate_candidate_evidence(
            tester_evidence,
            field="tester_evidence",
            candidate_sha=candidate_sha,
            require_pass=at_least("reviewer"),
            errors=errors,
        )
    elif at_least("reviewer"):
        errors.append("tester_evidence is required before Reviewer")

    if at_least("reviewer") and isinstance(tester_evidence, Mapping):
        if tester_evidence.get("verdict") != "PASS":
            errors.append("Reviewer requires tester_evidence.verdict PASS")

    if reviewer_evidence is not None:
        _validate_candidate_evidence(
            reviewer_evidence,
            field="reviewer_evidence",
            candidate_sha=candidate_sha,
            require_pass=at_least("final_human_review"),
            errors=errors,
        )
    elif at_least("final_human_review"):
        errors.append("reviewer_evidence is required before final Human Review")

    if at_least("complete"):
        _validate_comment(
            record.get("final_approval"),
            field="final_approval",
            bound_sha=candidate_sha,
            command_name="approve-candidate",
            errors=errors,
        )
        _validate_monitor(
            monitors.get("final_review"),
            field="monitors.final_review",
            require_stopped=True,
            errors=errors,
        )
    elif at_least("final_human_review"):
        _validate_monitor(
            monitors.get("final_review"),
            field="monitors.final_review",
            require_stopped=False,
            errors=errors,
        )

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
