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
# File:        test_isolation_preflight.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-13
# Version:     0.1.0
# Description: Owner v2 preflight and explicit v1 compatibility acceptance.
# =================================================================================


"""Requirement-derived preflight vectors; all observations are controlled inputs."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/fixtures/isolation-compliance"))
from isolation_support import capability, digest, environment, preflight_inputs
from env_support import Lab, git


@pytest.fixture
def lab():
    value = Lab()
    try:
        yield value
    finally:
        value.close()


def ready(request, observations):
    before = copy.deepcopy((request, observations))
    result = environment.evaluate_preflight(request, observations)
    assert result["status"] == "READY", result
    assert result["version"] == 2
    assert (request, observations) == before
    assert result["request"] == request and result["observations"] == observations
    assert result["request_sha256"] == digest(request)
    assert result["observations_sha256"] == digest(observations)
    assert result["report_sha256"] == digest({k: v for k, v in result.items() if k != "report_sha256"})
    assert environment.evaluate_preflight(request, observations) == result
    return result


def require(result):
    return environment.require_preflight(result,
        expected_request_sha256=result["request_sha256"], current_bindings=result["bindings"])


@pytest.mark.parametrize("level", ["I0", "I1", "I2"])
@pytest.mark.parametrize("role,phase", [
    ("worker", "implementation"), ("worker", "implementation-correction"),
    ("tester", "test-authoring"), ("tester", "test-execution"),
    ("reviewer", "terminal-review"), ("orchestrator", "orchestration")])
def test_ic01_v2_levels_bind_exact_context_without_os_claim(lab, level, role, phase):
    root = lab.clone()
    request, observations = preflight_inputs(root, role=role, phase=phase, level=level)
    assert observations["checkout"]["os_read_isolated"] is False
    report = ready(request, observations)
    assert "input-isolation" not in {x["id"] for x in report["selected_capabilities"]}
    require(report)


@pytest.mark.parametrize("field", ["clean_context", "separate_workspace", "selective_delivery"])
def test_ic02_i1_missing_separation_blocks_only_operation(lab, field):
    request, observations = preflight_inputs(lab.clone(), level="I1")
    ready(request, observations)
    observations["isolation_evidence"][field] = False
    result = environment.evaluate_preflight(request, observations)
    assert result["status"] == "BLOCKED"
    with pytest.raises(environment.EnvironmentError) as caught:
        require(result)
    assert caught.value.code == "CAPABILITY_UNAVAILABLE"


@pytest.mark.parametrize("level,expected", [("I0", "READY"), ("I1", "READY"), ("I2", "BLOCKED")])
def test_ic03_shared_git_is_honest_and_grade_specific(lab, level, expected):
    root = lab.linked()
    request, observations = preflight_inputs(root, level=level)
    assert observations["checkout"]["shared_objects"] is True
    assert observations["checkout"]["ref_isolated"] is False
    result = environment.evaluate_preflight(request, observations)
    assert result["version"] == 2 and result["status"] == expected


@pytest.mark.parametrize("field", [
    "approved_source_inventory", "context_evidence", "delivery_evidence"])
def test_ic04_preflight_rechecks_local_evidence_bytes(lab, field):
    root = lab.clone()
    request, observations = preflight_inputs(root)
    report = ready(request, observations)
    require(report)
    (root / observations["isolation_evidence"][field]["path"]).write_bytes(b"changed evidence\n")
    with pytest.raises(environment.EnvironmentError) as caught:
        require(report)
    assert caught.value.code in {"STALE_IDENTITY", "CAPABILITY_UNAVAILABLE", "INVALID_INPUT"}


@pytest.mark.parametrize("drift", ["binding", "report-selection", "request-grade", "current-head", "current-topology"])
def test_ic05_preflight_rejects_binding_and_rehashed_report_forgery(lab, drift):
    root = lab.clone()
    request, observations = preflight_inputs(root)
    report = ready(request, observations)
    if drift == "binding":
        report["bindings"]["contract_sha256"] = "d" * 64
    elif drift == "report-selection":
        report["selected_capabilities"] = []
    elif drift == "request-grade":
        report["request"]["isolation_scope"]["isolation_level"] = "I0"
    elif drift == "current-head":
        git(root, "config", "user.name", "Owner fixture")
        git(root, "config", "user.email", "fixture@example.invalid")
        (root / "new.txt").write_text("new public state\n")
        git(root, "add", "new.txt")
        git(root, "commit", "-qm", "source changed")
    else:
        (root / ".git/objects/info/alternates").write_text(str(lab.source / ".git/objects") + "\n")
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    with pytest.raises(environment.EnvironmentError) as caught:
        require(report)
    assert caught.value.code in {"STALE_IDENTITY", "INVALID_INPUT", "CAPABILITY_UNAVAILABLE"}


@pytest.mark.parametrize("bad", ["version-bool", "unknown-level", "extra", "phase", "deployed-role", "duplicate-capability"])
def test_ic06_closed_v2_inputs_fail_before_consumption(lab, bad):
    request, observations = preflight_inputs(lab.clone())
    ready(request, observations)
    if bad == "version-bool":
        request["version"] = True
    elif bad == "unknown-level":
        request["isolation_scope"]["isolation_level"] = "I3"
    elif bad == "extra":
        request["isolation"] = "input"
    elif bad == "phase":
        request["isolation_scope"]["phase"] = "terminal-review"
    elif bad == "deployed-role":
        request["isolation_scope"]["input_kind"] = "deployed-inputs"
        observations["checkout"] = None
    else:
        observations["capabilities"].append(copy.deepcopy(observations["capabilities"][0]))
    with pytest.raises(environment.EnvironmentError) as caught:
        environment.evaluate_preflight(request, observations)
    assert caught.value.code == "INVALID_INPUT"


def test_ic07_deployed_blackbox_needs_no_development_git(lab):
    root = lab.directory / "deployed"
    root.mkdir()
    (root / "fixture.txt").write_text("approved deployed fixture\n")
    request, observations = preflight_inputs(
        root, role="tester", phase="blackbox-execution", deployed=True, head=lab.head)
    report = ready(request, observations)
    assert observations["checkout"] is None and not (root / ".git").exists()
    assert {r["id"] for r in report["selected_capabilities"]} == {
        "filesystem-read", "filesystem-write", "agent-cli", "blackbox"}
    require(report)
    observations["isolation_evidence"]["development_repository_absent"] = False
    assert environment.evaluate_preflight(request, observations)["status"] == "BLOCKED"


def test_ic08_v1_input_isolation_claim_remains_explicit(lab):
    from env_support import request as old_request, observations as old_observations
    req = old_request(lab, root=lab.clone(), isolation="input")
    obs = old_observations(environment, req)
    report = environment.evaluate_preflight(req, obs)
    assert report["version"] == 1 and report["status"] == "BLOCKED"
    assert "observations" not in report
    assert any(row.get("capability") == "input-isolation" for row in report["diagnostics"])
    obs["capabilities"].append(capability("input-isolation"))
    report = environment.evaluate_preflight(req, obs)
    assert report["status"] == "READY"
    environment.require_preflight(report, expected_request_sha256=digest(req),
                                  current_bindings=req["bindings"])
