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
# File:        test_structured_handoff_lifecycle.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: General local-edge and safe-evidence lifecycle tests.
# =================================================================================

import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent-discipline/skills/agent-workflow/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from structured_handoff_fixture import Lifecycle


@pytest.fixture
def life(tmp_path):
    return Lifecycle(tmp_path / "repo")


def require_validator():
    import structured_handoff
    assert hasattr(structured_handoff, "run_validation"), "local-edge validation is not implemented"


def test_initial_success_lifecycle_and_independent_readiness(life):
    require_validator()
    for ref in (life.k, life.tlaunch, life.wlaunch, life.tr, life.ir, life.human):
        code, result = life.validate(ref)
        assert code == 0, result
    life.candidate(0)
    report = life.report("PASS")
    terminal = life.terminal(report, True, 0)
    code, result = life.validate(terminal)
    assert code == 0, result
    assert result["command_started"] == "NOT_STARTED"


def test_three_incremental_corrections_end_in_failure_not_success(life):
    require_validator()
    private = []
    for index in range(4):
        life.candidate(index)
        report = life.report("IMPLEMENTATION_FAIL")
        if index == 3:
            break
        private.append(report)
        correction = life.correction(index + 1, report)
        code, result = life.validate(correction, private)
        assert code == 0, result
        prior = life.i
        life.i = life.commit(prior, "src/component.py", "increment " + str(index))
        life.ir = life.implementation(index + 1, life.i, prior, correction)
    terminal = life.terminal(report, False, 3)
    code, result = life.validate(terminal, private)
    assert code == 0, result
    forged = copy.deepcopy(life.objects[terminal["artifact_id"]])
    forged["payload"].update(result="SUCCESS", disposition="OPEN_SUCCESS_PR", accepted_candidate=life.objects[life.c["artifact_id"]]["payload"]["candidate"]["commit"])
    assert life.validate(life.store(forged), private)[0] == 1


@pytest.mark.parametrize("mutation", ["extra", "missing", "bool-index", "wrong-g", "wrong-k", "wrong-parent", "wrong-digest", "wrong-kind"])
def test_invalid_artifact_identity_shape_and_references_are_rejected(life, mutation):
    require_validator()
    ref = life.candidate(0)
    value = copy.deepcopy(life.objects[ref["artifact_id"]])
    if mutation == "extra":
        value["payload"]["notes"] = "hidden task prose"
    elif mutation == "missing":
        del value["payload"]["execution_id"]
    elif mutation == "bool-index":
        value["payload"]["candidate_index"] = True
    elif mutation == "wrong-g":
        value["governor"]["commit"] = life.i
    elif mutation == "wrong-k":
        value["task_contract"]["sha256"] = "e" * 64
    elif mutation == "wrong-parent":
        value["payload"]["candidate"]["parents"].reverse()
    elif mutation == "wrong-digest":
        value["predecessors"][0]["sha256"] = "e" * 64
    else:
        value["predecessors"][0]["kind"] = "implementation-report"
    changed = life.store(value)
    assert life.validate(changed)[0] == 1


def test_sibling_implementation_is_not_incremental(life):
    require_validator()
    life.candidate(0)
    report = life.report("IMPLEMENTATION_FAIL")
    correction = life.correction(1, report)
    sibling = life.commit(life.g, "src/component.py", "sibling")
    ir = life.implementation(1, sibling, life.i, correction)
    assert life.validate(ir, [report])[0] == 1


def test_worker_local_uses_exact_safe_central_result_without_private_read(life):
    require_validator()
    life.candidate(0)
    report = life.report("IMPLEMENTATION_FAIL")
    correction = life.correction(1, report)
    code, result = life.validate(correction, [report], result_name=".agent-state/central.json")
    assert code == 0, result
    raw = (life.root / ".agent-state/central.json").read_bytes()
    assert report["path"].encode() not in raw
    assert b"private-node" not in raw
    (life.root / report["path"]).unlink()
    central = {"path": ".agent-state/central.json", "sha256": hashlib.sha256(raw).hexdigest()}
    code, result = life.validate(correction, view="consumer-local", central=central)
    assert code == 0, result
    central["sha256"] = "a" * 64
    assert life.validate(correction, view="consumer-local", central=central)[0] == 1


def test_worker_private_predecessor_is_rejected_before_file_open(life):
    require_validator()
    value = copy.deepcopy(life.objects[life.wlaunch["artifact_id"]])
    value["predecessors"].append({"kind": "tester-confidential-report", "artifact_id": "private", "path": ".agent-state/does-not-exist.json", "sha256": "b" * 64})
    ref = life.store(value)
    code, result = life.validate(ref, view="consumer-local")
    assert code == 1
    assert result["violations"][0]["rule_id"] == "PRIVATE_REFERENCE"


@pytest.mark.parametrize("destination", ["src/component.py", ".agent-state/task-contract-2.json"])
def test_results_never_overwrite_existing_inputs_or_sources(life, destination):
    require_validator()
    target = life.root / destination
    before = target.read_bytes()
    code, _ = life.validate(life.k, result_name=destination)
    assert code == 2
    assert target.read_bytes() == before


def test_same_candidate_invalid_rerun_keeps_count_and_changes_execution(life):
    require_validator()
    first = life.candidate(0)
    invalid = life.report("INVALID_RUN")
    value = copy.deepcopy(life.objects[first["artifact_id"]])
    value["artifact_id"] = "rerun-envelope"
    value["payload"].update(execution_id="execution-rerun", dispatch_id="rerun-dispatch", rerun_of=invalid)
    value["predecessors"].extend([first, invalid])
    rerun = life.store(value)
    code, result = life.validate(rerun)
    assert code == 0, result
    value["artifact_id"] = "bad-rerun"
    value["payload"]["execution_id"] = "execution-0"
    assert life.validate(life.store(value))[0] == 1
