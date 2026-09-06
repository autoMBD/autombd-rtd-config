# =================================================================================
# The MIT License
# MIT许可证
#
# <https://opensource.org/license/mit>
#
# SPDX short identifier / SPDX 短标识符：MIT
#
# Copyright (c) 2026 TkungL
# 版权所有 (c) 2026 TkungL
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
# Project:     autoMBD RTD Config <https://github.com/autoMBD/autombd-rtd-config>
# File:        test_workflow_contract_migration.py
# Author:      TkungL <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Generality checks for explicit v1 and v2 workflow compatibility.
# =================================================================================

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
ACTIVE = ROOT / "agent-discipline/workflow-contract.json"
LEGACY = ROOT / "agent-discipline/contracts/workflow-v1.json"
SCRIPT = ROOT / "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
LEGACY_BLOB = "b747065ac2fafa03d35d7a94b39d52d70f1de416"


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location("workflow_migration_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declaration():
    return {
        "schema_version": 2,
        "contract_version": 2,
        "workflow_profile": "functional-development-v1",
        "artifact_schema": "agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json",
        "registry": "agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json",
        "legacy_contract": "agent-discipline/contracts/workflow-v1.json",
        "lifecycle": {
            "parallel_lanes": True,
            "gate1_requires_worker_ready": False,
            "frozen_test": True,
            "initial_candidate": 0,
            "max_corrections": 3,
            "max_candidates": 4,
            "incremental_same_lane": True,
            "terminal_review_once": True,
            "review_on_success_and_failure": True,
            "pr_head": "accepted_candidate",
            "pr_includes_test_and_implementation": True,
            "kpi_in_functional_gate": False,
        },
        "deferred_runtime_capabilities": [
            "transition-executor", "remote-authority-verification",
            "candidate-direct-union", "capability-sandbox",
            "global-exactly-once", "kpi-profile",
        ],
    }


def write_contract(tmp_path, value):
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_legacy_snapshot_preserves_exact_original_blob_bytes():
    assert LEGACY.is_file(), "explicit legacy snapshot is missing"
    expected = subprocess.run(
        ["git", "cat-file", "blob", LEGACY_BLOB], cwd=ROOT,
        check=True, capture_output=True,
    ).stdout
    assert LEGACY.read_bytes() == expected
    header = f"blob {len(expected)}\0".encode("ascii")
    assert hashlib.sha1(header + LEGACY.read_bytes()).hexdigest() == LEGACY_BLOB


def test_legacy_snapshot_checkout_retains_exact_bytes_with_autocrlf(tmp_path):
    repository = tmp_path / "snapshot-checkout"
    repository.mkdir()

    def git(*arguments):
        return subprocess.run(
            ["git", *arguments], cwd=repository, check=True, capture_output=True,
        ).stdout

    git("init")
    git("config", "core.autocrlf", "true")
    (repository / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    relative = LEGACY.relative_to(ROOT)
    source = repository / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(LEGACY.read_bytes())
    git("add", ".gitattributes", relative.as_posix())
    checkout = repository / "checkout"
    git("checkout-index", "--all", f"--prefix={checkout.as_posix()}/")
    assert (checkout / relative).read_bytes() == LEGACY.read_bytes()
    attributes = git("check-attr", "eol", "--", relative.as_posix())
    assert attributes.decode("utf-8").strip().endswith(": eol: lf")


def test_active_contract_is_the_approved_small_v2_declaration(gate):
    assert json.loads(ACTIVE.read_text(encoding="utf-8")) == declaration()
    gate.validate_contract(declaration(), contract_path=ACTIVE)


def test_v2_contract_validates_without_any_workflow_record(gate, tmp_path):
    value = declaration()
    path = write_contract(tmp_path, value)
    gate.validate_contract(value, contract_path=path)
    assert callable(getattr(gate, "load_contract", None)), "public contract loader is missing"
    assert gate.load_contract(path) == value


@pytest.mark.parametrize("field", list(declaration()))
def test_v2_contract_rejects_missing_members(gate, tmp_path, field):
    value = declaration()
    del value[field]
    with pytest.raises(gate.WorkflowValidationError):
        gate.validate_contract(value, contract_path=write_contract(tmp_path, value))


@pytest.mark.parametrize("scope", ["top", "lifecycle"])
def test_v2_contract_rejects_unapproved_fields(gate, tmp_path, scope):
    value = declaration()
    target = value if scope == "top" else value[scope]
    target["strict_route"] = ["scope", "implement", "review"]
    with pytest.raises(gate.WorkflowValidationError):
        gate.validate_contract(value, contract_path=write_contract(tmp_path, value))


@pytest.mark.parametrize("field", list(declaration()["lifecycle"]))
def test_v2_lifecycle_constants_are_exact_and_type_strict(gate, tmp_path, field):
    for replacement in (None, "changed", 13, True, False, 0, 1):
        value = declaration()
        expected = value["lifecycle"][field]
        if type(replacement) is type(expected) and replacement == expected:
            continue
        value["lifecycle"][field] = replacement
        with pytest.raises(gate.WorkflowValidationError):
            gate.validate_contract(value, contract_path=write_contract(tmp_path, value))


@pytest.mark.parametrize("field", ["artifact_schema", "registry", "legacy_contract"])
@pytest.mark.parametrize("replacement", ["/outside.json", "../outside.json", "C:/outside.json", "wrong.json", None])
def test_v2_references_pin_the_approved_authorities(gate, tmp_path, field, replacement):
    value = declaration()
    value[field] = replacement
    with pytest.raises(gate.WorkflowValidationError):
        gate.validate_contract(value, contract_path=write_contract(tmp_path, value))


@pytest.mark.parametrize("replacement", [True, "2", 0, 3, 2.0, None])
def test_unknown_or_wrong_type_versions_never_fall_back(gate, tmp_path, replacement):
    value = declaration()
    value["schema_version"] = replacement
    with pytest.raises(gate.WorkflowValidationError):
        gate.validate_contract(value, contract_path=write_contract(tmp_path, value))


@pytest.mark.parametrize("field", ["contract_version", "workflow_profile", "deferred_runtime_capabilities"])
@pytest.mark.parametrize("replacement", [None, True, "unknown", 2.0, [], ["unknown"], ["kpi-profile", "kpi-profile"]])
def test_v2_declared_metadata_is_closed_and_type_strict(gate, tmp_path, field, replacement):
    value = declaration()
    value[field] = replacement
    with pytest.raises(gate.WorkflowValidationError):
        gate.validate_contract(value, contract_path=write_contract(tmp_path, value))


@pytest.mark.parametrize("scope", ["top", "lifecycle"])
def test_v2_loader_rejects_duplicate_members(gate, tmp_path, scope):
    assert callable(getattr(gate, "load_contract", None)), "public contract loader is missing"
    raw = json.dumps(declaration())
    key = "schema_version" if scope == "top" else "max_corrections"
    raw = raw.replace(f'"{key}":', f'"{key}": 9, "{key}":', 1)
    path = tmp_path / "duplicate.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(gate.WorkflowValidationError, match="duplicate"):
        gate.load_contract(path)


@pytest.mark.parametrize("operation", ["record", "manifests"])
def test_v2_rejects_legacy_evidence_with_explicit_migration_diagnostic(gate, tmp_path, operation):
    path = write_contract(tmp_path, declaration())
    with pytest.raises(gate.WorkflowValidationError, match="v2.*validate-artifact"):
        if operation == "record":
            gate.validate_record({}, contract_path=path)
        else:
            gate.validate_lane_manifests({}, {}, contract_path=path)


def test_explicit_v1_loader_preserves_legacy_contract(gate):
    assert callable(getattr(gate, "load_contract", None)), "public contract loader is missing"
    loaded = gate.load_contract(LEGACY)
    assert loaded["contract_version"] == 1
    assert loaded["candidate_attempt"] == {"minimum": 1, "maximum": 3}
    gate.validate_contract(loaded, contract_path=LEGACY)


def test_v2_object_must_match_supplied_path(gate, tmp_path):
    path = write_contract(tmp_path, declaration())
    altered = copy.deepcopy(declaration())
    altered["lifecycle"]["max_corrections"] = 12
    with pytest.raises(gate.WorkflowValidationError, match="differs from contract_path"):
        gate.validate_contract(altered, contract_path=path)


def test_contract_only_cli_has_honest_exit_classes_and_no_record(tmp_path):
    path = write_contract(tmp_path, declaration())
    command = [sys.executable, str(SCRIPT), "validate-contract", "--contract", str(path)]
    passed = subprocess.run(command, capture_output=True, text=True)
    assert passed.returncode == 0, passed.stderr
    assert "contract validation passed" in passed.stdout
    value = declaration()
    value["unexpected"] = True
    write_contract(tmp_path, value)
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode == 1, rejected.stderr
    path.write_text("{broken-json", encoding="utf-8")
    malformed = subprocess.run(command, capture_output=True, text=True)
    assert malformed.returncode == 2, malformed.stderr


@pytest.mark.parametrize("command", ["validate", "validate-record"])
def test_record_cli_rejects_v2_instead_of_claiming_legacy_pass(tmp_path, command):
    path = write_contract(tmp_path, declaration())
    record = tmp_path / "record.json"
    record.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), command, "--contract", str(path), "--record", str(record)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "v2" in result.stderr and "validate-artifact" in result.stderr
    assert "passed" not in result.stdout
