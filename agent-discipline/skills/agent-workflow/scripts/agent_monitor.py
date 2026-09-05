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
# File:        agent_monitor.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-05
# Version:     0.1.0
# Description: Validate passive Agent monitoring records without scheduling.
# =================================================================================

"""Closed v1 monitoring records. No clock, process, workflow verdict, or writes."""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


PLAN_FIELDS = {
    "schema_version", "task_run", "dispatch_id", "role", "worktree", "lane_ref",
    "harness_adapter", "agent_id", "session_id", "estimated_duration_seconds",
    "estimate_basis", "first_observation_after_seconds", "automatic_timeout",
    "created_at_utc", "owner",
}
EVENT_FIELDS = {
    "task_run", "dispatch_id", "sequence", "observed_at_utc", "signal_source",
    "signal_kind", "progress_since_previous", "current_operation", "blocker",
    "last_evidence_locator", "revised_remaining_seconds", "actor", "decision",
    "next_observation_after_seconds", "rationale", "termination_reason",
}
SOURCES = {"harness_event", "wait_snapshot", "agent_status", "human", "platform"}
SIGNALS = {
    "progress", "observation_end", "agent_status", "completed", "human_stop",
    "transport_interruption", "tool_interruption", "platform_interruption",
}
DECISIONS = {"CONTINUE", "CONTACT", "INTERVENE", "TERMINATE"}
STOP_REASONS = {
    "human_stop", "unrecoverable_agent", "integrity_safety",
    "unrecoverable_mandatory_operation",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def closed(value, fields, label):
    require(isinstance(value, dict) and set(value) == fields,
            f"{label} fields must be exactly: {', '.join(sorted(fields))}")


def nonempty(value, name, nullable=False):
    require((nullable and value is None) or
            (isinstance(value, str) and bool(value.strip())), f"{name} must be nonempty text")


def seconds(value, name, zero=False):
    finite = type(value) is int or (type(value) is float and math.isfinite(value))
    bound = "nonnegative" if zero else "positive"
    require(finite and (value >= 0 if zero else value > 0),
            f"{name} must be finite {bound} seconds")


def utc(value, name):
    nonempty(value, name)
    require(value.endswith("Z") and "T" in value, f"{name} must be an explicit UTC timestamp ending Z")
    result = datetime.fromisoformat(value)
    require(result.utcoffset() == timezone.utc.utcoffset(result), f"{name} must be UTC")
    return result


def member(value, domain, name):
    require(isinstance(value, str) and value in domain, f"invalid {name}")


def validate(plan, events):
    """Raise ValueError for invalid records; accept any finite task-specific estimate.

    Identity/shape checks cannot authenticate the actor or judge the truth of
    a rationale. The Orchestrator owns those judgments and any harness action.
    """
    closed(plan, PLAN_FIELDS, "plan")
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1,
            "schema_version must be integer 1")
    require(plan["automatic_timeout"] is False, "automatic_timeout must be false")
    require(plan["owner"] == "orchestrator", "owner must be orchestrator")
    for name in ("task_run", "dispatch_id", "role", "worktree", "lane_ref",
                 "harness_adapter", "estimate_basis"):
        nonempty(plan[name], name)
    require(Path(plan["worktree"]).is_absolute(), "worktree must be absolute")
    for name in ("agent_id", "session_id"):
        nonempty(plan[name], name, nullable=True)
    seconds(plan["estimated_duration_seconds"], "estimated_duration_seconds")
    seconds(plan["first_observation_after_seconds"], "first_observation_after_seconds")
    previous_time = utc(plan["created_at_utc"], "created_at_utc")
    require(isinstance(events, list), "events must be a list")
    terminal = False
    for index, event in enumerate(events, 1):
        require(not terminal, "no observations after this dispatch completed or was terminated")
        closed(event, EVENT_FIELDS, "event")
        require(type(event["sequence"]) is int and event["sequence"] == index,
                "sequence must be consecutive integers starting at 1")
        for name in ("task_run", "dispatch_id"):
            require(event[name] == plan[name], f"{name} does not match plan")
        observed = utc(event["observed_at_utc"], "observed_at_utc")
        require(observed >= previous_time, "observation timestamps must not go backwards")
        previous_time = observed
        member(event["signal_source"], SOURCES, "signal_source")
        member(event["signal_kind"], SIGNALS, "signal_kind")
        member(event["actor"], {"human", "orchestrator"}, "actor")
        member(event["decision"], DECISIONS, "decision")
        for name in ("progress_since_previous", "current_operation", "rationale"):
            nonempty(event[name], name)
        for name in ("blocker", "last_evidence_locator"):
            nonempty(event[name], name, nullable=True)
        seconds(event["revised_remaining_seconds"], "revised_remaining_seconds", zero=True)
        if event["decision"] == "TERMINATE":
            require(event["signal_kind"] != "completed", "completed requires CONTINUE, not TERMINATE")
            member(event["termination_reason"], STOP_REASONS, "termination_reason")
            require(event["next_observation_after_seconds"] is None,
                    "TERMINATE must not schedule an observation")
            if event["termination_reason"] == "human_stop":
                require(event["signal_source"] == "human" and event["signal_kind"] == "human_stop",
                        "human_stop must reference a human stop signal")
            terminal = True
        else:
            require(event["termination_reason"] is None, "nonterminal decision has no termination_reason")
            if event["signal_kind"] == "completed":
                require(event["decision"] == "CONTINUE" and
                        event["revised_remaining_seconds"] == 0 and
                        event["next_observation_after_seconds"] is None,
                        "completed records require CONTINUE, zero remaining, and no next observation")
                terminal = True
            else:
                require(event["signal_kind"] != "human_stop", "human_stop must be honored by TERMINATE")
                seconds(event["next_observation_after_seconds"], "next_observation_after_seconds")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON member: {key}")
        result[key] = value
    return result


def read_json(text):
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="operation", required=True).add_parser("validate")
    command.add_argument("--plan", required=True, type=Path)
    command.add_argument("--events", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        plan = read_json(args.plan.read_text(encoding="utf-8"))
        events = [read_json(line) for line in args.events.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"valid": False, "code": "MONITOR_INPUT_ERROR", "error": str(error)}))
        return 2
    try:
        validate(plan, events)
    except ValueError as error:
        print(json.dumps({"valid": False, "code": "MONITOR_RECORD_INVALID", "error": str(error)}))
        return 1
    print(json.dumps({"valid": True, "events": len(events)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
