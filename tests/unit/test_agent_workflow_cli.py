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
# File:        test_agent_workflow_cli.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-22
# Version:     0.1.0
# Description: Subprocess acceptance tests for the workflow gate JSON CLI.
# =================================================================================

import json
from pathlib import Path
import subprocess
import sys

import pytest


GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)
BASE_SHA = "a" * 40


def _classify_record() -> dict:
    return {
        "version": 2,
        "issue": {
            "number": 78,
            "primary_type": "W",
            "impact_flags": ["AR"],
        },
        "state": "classify",
        "gate": {"test_required": True},
        "revisions": {"base_sha": BASE_SHA},
        "counters": {"production_rework": 0, "kpi_optimization": 0},
        "exception": None,
    }


def _run(
    record_path: str | Path,
    data: bytes | None = None,
    *extra_args: str,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            sys.executable,
            str(GATE_PATH),
            "--json",
            str(record_path),
            *extra_args,
        ],
        check=False,
        capture_output=True,
        input=data,
        timeout=10,
    )


def _payload(result: subprocess.CompletedProcess[bytes]) -> dict:
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    assert "traceback" not in stdout.casefold()
    assert "traceback" not in stderr.casefold()
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    assert set(payload) >= {"ok", "errors", "error_type"}
    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["errors"], list)
    assert all(isinstance(item, str) for item in payload["errors"])
    assert payload["error_type"] is None or isinstance(payload["error_type"], str)
    return payload


def test_cli_valid_record_returns_exit_zero_and_stable_json():
    data = json.dumps(_classify_record()).encode("utf-8")
    result = _run("-", data)
    payload = _payload(result)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["errors"] == []
    assert payload["error_type"] is None


def test_cli_invalid_record_returns_exit_one_and_validation_json():
    record = _classify_record()
    record["state"] = "not-a-workflow-state"
    result = _run("-", json.dumps(record).encode("utf-8"))
    payload = _payload(result)

    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["errors"]
    assert payload["error_type"] == "validation"


@pytest.mark.parametrize(
    "extra_args",
    (
        ("--previous", "tests/.tmp/not-read-without-event.json"),
        ("--event", "classification_complete"),
    ),
)
def test_cli_transition_mode_requires_paired_previous_and_event(extra_args):
    result = _run(
        "-",
        json.dumps(_classify_record()).encode("utf-8"),
        *extra_args,
    )
    payload = _payload(result)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["error_type"] == "input"
    diagnostic = " ".join(payload["errors"]).casefold()
    assert "--previous" in diagnostic
    assert "--event" in diagnostic


def test_cli_transition_mode_accepts_the_pair_before_reading_previous():
    result = _run(
        "-",
        json.dumps(_classify_record()).encode("utf-8"),
        "--previous",
        "tests/.tmp/issue-78-definitely-missing-previous.json",
        "--event",
        "classification_complete",
    )
    payload = _payload(result)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["error_type"] == "input"
    diagnostic = " ".join(payload["errors"]).casefold()
    assert "previous" in diagnostic
    assert "does not exist" in diagnostic
    assert "provided together" not in diagnostic


@pytest.mark.parametrize("failure", ("invalid_json", "invalid_utf8", "missing_file"))
def test_cli_input_failures_return_exit_two_stable_json_without_traceback(
    failure,
):
    if failure == "invalid_json":
        result = _run("-", b'{"version":')
    elif failure == "invalid_utf8":
        result = _run("-", b"\xff\xfe\xfa")
    else:
        result = _run("tests/.tmp/issue-78-definitely-missing-workflow.json")
    payload = _payload(result)

    assert result.returncode == 2
    assert payload["ok"] is False
    assert payload["errors"]
    assert payload["error_type"] == "input"
