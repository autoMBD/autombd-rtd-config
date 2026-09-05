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
# File:        test_agent_monitor.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-05
# Version:     0.1.0
# Description: Verify monitoring records without Agent lifecycle side effects.
# =================================================================================

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "agent-discipline/skills/agent-workflow/scripts/agent_monitor.py"


@pytest.fixture
def monitor():
    assert SCRIPT.is_file(), "monitor record validator is not implemented"
    spec = importlib.util.spec_from_file_location("agent_monitor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plan(tmp_path):
    return {
        "schema_version": 1, "task_run": "public-task", "dispatch_id": "worker-a",
        "role": "worker", "worktree": str(tmp_path.resolve()), "lane_ref": "work/topic",
        "harness_adapter": "codex", "agent_id": "agent-23", "session_id": None,
        "estimated_duration_seconds": 35, "estimate_basis": "Small public API change",
        "first_observation_after_seconds": 12, "automatic_timeout": False,
        "created_at_utc": "2026-09-05T00:00:00Z", "owner": "orchestrator",
    }


def event(**changes):
    value = {
        "task_run": "public-task", "dispatch_id": "worker-a", "sequence": 1,
        "observed_at_utc": "2026-09-05T02:00:00Z", "signal_source": "wait_snapshot",
        "signal_kind": "observation_end", "progress_since_previous": "Parser implemented",
        "current_operation": "Check compatibility", "blocker": None,
        "last_evidence_locator": "session:worker-a/item/42", "revised_remaining_seconds": 240,
        "actor": "orchestrator", "decision": "CONTINUE",
        "next_observation_after_seconds": 45, "rationale": "Progress justifies waiting",
        "termination_reason": None,
    }
    value.update(changes)
    return value


def test_overdue_progress_and_revised_estimate_remain_valid(monitor, plan):
    before = copy.deepcopy(plan)
    events = [event(), event(sequence=2, observed_at_utc="2026-09-05T03:00:00Z",
                            revised_remaining_seconds=1000, next_observation_after_seconds=180)]
    snapshot = copy.deepcopy(events)
    monitor.validate(plan, events)
    assert plan == before and events == snapshot
    plan["estimated_duration_seconds"] = 8000
    monitor.validate(plan, events)  # no contract epoch or timer reset required


@pytest.mark.parametrize("kind,source", [
    ("observation_end", "wait_snapshot"), ("transport_interruption", "harness_event"),
    ("tool_interruption", "harness_event"), ("platform_interruption", "platform"),
])
def test_interruptions_are_observations_not_verdicts(monitor, plan, kind, source):
    monitor.validate(plan, [event(signal_kind=kind, signal_source=source, decision="CONTACT")])


@pytest.mark.parametrize("decision", ["CONTINUE", "CONTACT", "INTERVENE"])
def test_explicit_nonterminal_decisions(monitor, plan, decision):
    monitor.validate(plan, [event(decision=decision)])


def test_explicit_human_termination_and_natural_completion(monitor, plan):
    monitor.validate(plan, [event(actor="human", signal_source="human", signal_kind="human_stop",
                                 decision="TERMINATE", termination_reason="human_stop",
                                 next_observation_after_seconds=None)])
    monitor.validate(plan, [event(signal_kind="completed", revised_remaining_seconds=0,
                                 next_observation_after_seconds=None)])


@pytest.mark.parametrize("reason", ["unrecoverable_agent", "integrity_safety",
                                  "unrecoverable_mandatory_operation"])
def test_explicit_orchestrator_termination(monitor, plan, reason):
    monitor.validate(plan, [event(decision="TERMINATE", termination_reason=reason,
                                 next_observation_after_seconds=None)])


def test_very_large_estimate_is_not_a_machine_deadline(monitor, plan):
    plan["estimated_duration_seconds"] = 10 ** 400
    monitor.validate(plan, [])


@pytest.mark.parametrize("changes", [
    {"automatic_timeout": True}, {"automatic_timeout": 0}, {"owner": "worker"},
    {"estimated_duration_seconds": True}, {"estimated_duration_seconds": float("inf")},
    {"first_observation_after_seconds": 0}, {"worktree": "relative/lane"},
    {"estimate_basis": " "}, {"schema_version": True}, {"K": "changed"},
    {"created_at_utc": "2026-09-05"}, {"agent_id": ""},
])
def test_reject_invalid_plan(monitor, plan, changes):
    plan.update(changes)
    with pytest.raises(ValueError):
        monitor.validate(plan, [])


@pytest.mark.parametrize("changes", [
    {"dispatch_id": "other"}, {"task_run": "other"}, {"sequence": True},
    {"sequence": 2}, {"decision": "AUTO_FAIL"}, {"actor": "clock"},
    {"decision": "TERMINATE", "termination_reason": "estimate_exceeded"},
    {"decision": "TERMINATE", "termination_reason": None},
    {"decision": "TERMINATE", "termination_reason": "human_stop"},
    {"termination_reason": "human_stop"},
    {"next_observation_after_seconds": 0}, {"next_observation_after_seconds": None},
    {"revised_remaining_seconds": -1}, {"rationale": " "},
    {"observed_at_utc": "2026-09-04T00:00:00Z"}, {"signal_kind": "IMPLEMENTATION_FAIL"},
    {"implementation_verdict": "FAIL"}, {"correction_count": 1},
])
def test_reject_invalid_event(monitor, plan, changes):
    with pytest.raises(ValueError):
        monitor.validate(plan, [event(**changes)])


def test_sequence_and_time_order(monitor, plan):
    with pytest.raises(ValueError):
        monitor.validate(plan, [event(), event()])
    with pytest.raises(ValueError):
        monitor.validate(plan, [event(), event(sequence=2, observed_at_utc="2026-09-05T01:00:00Z")])


def test_termination_closes_only_this_monitor_history(monitor, plan):
    end = event(decision="TERMINATE", termination_reason="unrecoverable_agent",
                next_observation_after_seconds=None)
    monitor.validate(plan, [end])
    with pytest.raises(ValueError):
        monitor.validate(plan, [end, event(sequence=2)])


def test_completed_signal_cannot_be_reclassified_as_termination(monitor, plan):
    with pytest.raises(ValueError):
        monitor.validate(plan, [event(signal_kind="completed", decision="TERMINATE",
                                     termination_reason="unrecoverable_agent",
                                     next_observation_after_seconds=None)])


def test_cli_is_read_only_and_reports_invalid_input(monitor, plan, tmp_path):
    plan_path, events_path = tmp_path / "plan.json", tmp_path / "events.jsonl"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    events_path.write_text(json.dumps(event()) + "\n", encoding="utf-8")
    before = (plan_path.read_bytes(), events_path.read_bytes())
    argv = [sys.executable, str(SCRIPT), "validate", "--plan", str(plan_path),
            "--events", str(events_path)]
    result = subprocess.run(argv, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"valid": True, "events": 1}
    assert before == (plan_path.read_bytes(), events_path.read_bytes())
    events_path.write_text(json.dumps(event(decision="AUTO_FAIL")) + "\n", encoding="utf-8")
    result = subprocess.run(argv, text=True, capture_output=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["code"] == "MONITOR_RECORD_INVALID"
    plan_path.write_text('{"owner":"orchestrator","owner":"clock"}', encoding="utf-8")
    result = subprocess.run(argv, text=True, capture_output=True, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "MONITOR_INPUT_ERROR"
