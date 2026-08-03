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
# File:        test_agent_workflow_bootstrap_generality.py
# Author:      TkungL <tkung.lqk@foxmail.com>
# Date:        2026-08-03
# Version:     0.1.0
# Description: Generality tests for the minimal agent workflow bootstrap gate.
# =================================================================================

import copy
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "agent-discipline" / "workflow-contract.json"
GATE_PATH = (
    ROOT
    / "agent-discipline"
    / "skills"
    / "agent-workflow"
    / "scripts"
    / "workflow_gate.py"
)
SHA = {name: character * 40 for name, character in zip(
    ("base", "test", "implementation", "candidate"), "1234"
)}
_GATE = None


def _gate():
    global _GATE
    if _GATE is not None:
        return _GATE
    assert GATE_PATH.is_file(), "workflow_gate.py production entry point is missing"
    spec = importlib.util.spec_from_file_location("workflow_gate_under_test", GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _GATE = module
    return _GATE


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _record():
    contract = _contract()
    return {
        "contract": {"version": 1, "blob_sha": "b747065ac2fafa03d35d7a94b39d52d70f1de416"},
        "issue": {"repository": "autoMBD/workflow-sandbox", "number": 731, "title": "Validate a bounded workflow"},
        "classification": {
            "issue_class": "W",
            "impact_flags": ["agent-runtime", "test-contract"],
            "route": contract["strict_route"],
        },
        "checkpoint": "complete",
        "execution_status": "active",
        "preflight": {
            "permissions": [{"name": "repository", "status": "available", "evidence": "write lane granted"}],
            "dependencies": [{"name": "contract", "status": "available", "evidence": "blob pinned"}],
            "tools": [{"name": "python", "status": "available", "evidence": "stdlib present"}],
            "result": "available",
        },
        "authority": {
            "base_sha": SHA["base"],
            "test_sha": SHA["test"],
            "implementation_sha": SHA["implementation"],
            "authorized_reviewer": "review-captain",
        },
        "human_review_1": {
            "actor": "review-captain",
            "comment_url": "https://github.com/autoMBD/workflow-sandbox/issues/731#issuecomment-92731",
            "test_sha": SHA["test"],
            "command": f"/approve-test {SHA['test']}",
            "edited": False,
            "deleted": False,
        },
        "candidate": {
            "sha": SHA["candidate"],
            "parent_test_sha": SHA["test"],
            "parent_implementation_sha": SHA["implementation"],
        },
        "tester": {"candidate_sha": SHA["candidate"], "verdict": "PASS", "evidence": "functional gate 19/19"},
        "reviewer": {"candidate_sha": SHA["candidate"], "verdict": "PASS", "evidence": "non-test review accepted"},
        "findings": [{
            "id": "finding-31",
            "source": "reviewer",
            "class": "F2",
            "requirement_id": "P0-12",
            "evidence": "repair isolated to next stage",
            "observed": "non-current artifact issue",
            "expected": "stage-local correction",
            "freeze_viability": {
                "identity_trustworthy": True,
                "continuity_available": True,
                "repair_without_mutation": True,
                "evidence_valid": True,
                "safe_reversible": True,
                "facts_available": True,
            },
            "disposition": "FREEZE_FOR_NEXT_STAGE",
        }],
        "draft_pr": {"url": "https://github.com/autoMBD/workflow-sandbox/pull/74", "candidate_sha": SHA["candidate"], "is_draft": True},
        "final_human_review": {
            "actor": "release-owner",
            "comment_url": "https://github.com/autoMBD/workflow-sandbox/pull/74#issuecomment-991",
            "candidate_sha": SHA["candidate"],
            "decision": "APPROVE",
        },
        "attempt": {"candidate_attempt": 2},
        "blocker": None,
        "bootstrap_stage": "P0",
    }


def _expect_invalid(call):
    with pytest.raises(_gate().WorkflowValidationError) as caught:
        call()
    return caught.value


def _clearance_report(error):
    return json.loads(str(error).split(": ", 1)[1])


def test_public_surface_and_valid_arbitrary_record():
    gate = _gate()
    for name, parameters in {
        "validate_contract": ("contract", "contract_path"),
        "validate_record": ("record", "contract_path"),
        "validate_lane_manifests": ("test_manifest", "implementation_manifest", "contract_path"),
        "audit_bootstrap_clearance": ("repository_path", "candidate_sha", "deployment_paths", "bootstrap_document_commits"),
    }.items():
        assert tuple(inspect.signature(getattr(gate, name)).parameters) == parameters
    gate.validate_contract(_contract(), contract_path=CONTRACT_PATH)
    gate.validate_record(_record(), contract_path=CONTRACT_PATH)


def test_contract_and_record_are_closed_and_domains_are_contract_driven():
    gate = _gate()
    mutations = []
    altered_contract = _contract()
    altered_contract["issue_classes"] = altered_contract["issue_classes"][:-1]
    mutations.append(lambda: gate.validate_contract(altered_contract, contract_path=CONTRACT_PATH))
    for path, value in [
        (("classification", "issue_class"), "X"),
        (("classification", "impact_flags"), ["agent-runtime", "invented-flag"]),
        (("classification", "route"), _contract()["strict_route"][:-1]),
        (("authority", "base_sha"), "ABC123"),
    ]:
        record = _record()
        record[path[0]][path[1]] = value
        mutations.append(lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH))
    extra = _record()
    extra["candidate"]["exception"] = "never allowed"
    mutations.append(lambda: gate.validate_record(extra, contract_path=CONTRACT_PATH))
    for mutation in mutations:
        _expect_invalid(mutation)


def test_preflight_review_and_current_candidate_bindings_fail_closed():
    gate = _gate()
    records = []
    blocked = _record()
    blocked["preflight"]["tools"][0]["status"] = "blocked"
    records.append(blocked)
    wrong_actor = _record()
    wrong_actor["human_review_1"]["actor"] = "somebody-else"
    records.append(wrong_actor)
    edited = _record()
    edited["human_review_1"]["edited"] = True
    records.append(edited)
    stale = _record()
    stale["reviewer"]["candidate_sha"] = "5" * 40
    records.append(stale)
    tester_failed = _record()
    tester_failed["tester"]["verdict"] = "FAIL"
    records.append(tester_failed)
    non_draft = _record()
    non_draft["draft_pr"]["is_draft"] = False
    records.append(non_draft)
    for record in records:
        _expect_invalid(lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH))


def test_finding_dispositions_and_attempt_bounds_are_exact():
    gate = _gate()
    for finding_class, viability, disposition, valid in [
        ("F0", [False] * 6, "BLOCK", True),
        ("F0", [True] * 6, "FREEZE_FOR_NEXT_STAGE", False),
        ("F1", [False] * 6, "REWORK_CURRENT_STAGE", True),
        ("F2", [True] * 6, "FREEZE_FOR_NEXT_STAGE", True),
        ("F2", [True, True, False, True, True, True], "BLOCK", True),
        ("F2", [True, True, False, True, True, True], "FREEZE_FOR_NEXT_STAGE", False),
        ("F3", [False] * 6, "DEFER_NON_BLOCKING", True),
        ("F4", [False] * 6, "FINAL_ACCEPT", False),
    ]:
        record = _record()
        finding = record["findings"][0]
        finding["class"] = finding_class
        finding["freeze_viability"] = dict(zip(_contract()["object_fields"]["freeze_viability"], viability))
        finding["disposition"] = disposition
        if valid:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        else:
            _expect_invalid(lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH))
    for attempt in (0, 4, True):
        record = _record()
        record["attempt"]["candidate_attempt"] = attempt
        _expect_invalid(lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH))


def test_lane_manifests_bind_the_same_contract_base_and_requirements():
    gate = _gate()
    contract = _contract()
    common = {
        "contract_version": contract["contract_version"],
        "contract_blob_sha": _record()["contract"]["blob_sha"],
        "base_sha": SHA["base"],
        "requirement_ids": contract["requirement_ids"],
    }
    test_manifest = {**common, "lane_sha": SHA["test"]}
    implementation_manifest = {**common, "lane_sha": SHA["implementation"]}
    gate.validate_lane_manifests(test_manifest, implementation_manifest, contract_path=CONTRACT_PATH)
    for field, value in [("base_sha", "f" * 40), ("lane_sha", SHA["test"]), ("requirement_ids", contract["requirement_ids"][:-1])]:
        changed = copy.deepcopy(implementation_manifest)
        changed[field] = value
        _expect_invalid(lambda changed=changed: gate.validate_lane_manifests(test_manifest, changed, contract_path=CONTRACT_PATH))


def test_cli_has_stable_zero_one_two_exit_classes(tmp_path):
    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps(_record()), encoding="utf-8")
    command = [sys.executable, str(GATE_PATH), "validate", "--contract", str(CONTRACT_PATH), "--record", str(record_path)]
    assert subprocess.run(command, capture_output=True, text=True).returncode == 0
    invalid = _record()
    invalid["attempt"]["candidate_attempt"] = 9
    record_path.write_text(json.dumps(invalid), encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1 and "Traceback" not in result.stderr
    record_path.write_text("{not-json", encoding="utf-8")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2 and "Traceback" not in result.stderr


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_clearance_uses_candidate_tree_checks_ancestry_and_self_scans(tmp_path):
    gate = _gate()
    repo = tmp_path / "synthetic"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Generality Test")
    _git(repo, "config", "user.email", "generality@example.invalid")
    implementation_paths = [
        "AGENTS.md",
        "agent-discipline/skills/agent-workflow/SKILL.md",
        "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py",
        "agent-discipline/subagents/explorer.md",
        "agent-discipline/subagents/worker.md",
        "agent-discipline/subagents/tester.md",
        "agent-discipline/subagents/reviewer.md",
        "tests/unit/test_agent_workflow_bootstrap_generality.py",
    ]
    for relative in implementation_paths:
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    deploy = repo / "deploy"
    deploy.mkdir()
    (deploy / "payload.txt").write_text("durable workflow payload\n", encoding="utf-8")
    root_sha = _commit(repo, "clean self-scan root")
    (deploy / "second.txt").write_text("durable second payload\n", encoding="utf-8")
    candidate_sha = _commit(repo, "clean candidate")
    keys = [
        "bootstrap_design_file_count", "bootstrap_design_reference_count",
        "bootstrap_governance_reference_count", "bootstrap_generated_or_payload_count",
        "bootstrap_commit_ancestor_count", "temporary_heading_count",
        "temporary_removal_marker_count", "bootstrap_debt_id_count",
        "bootstrap_debt_pointer_count", "open_bootstrap_debt_count",
    ]
    report = gate.audit_bootstrap_clearance(repo, candidate_sha, ["deploy"], [])
    assert list(report) == keys and list(report.values()) == [0] * 10
    assert list(gate.audit_bootstrap_clearance(repo, candidate_sha, [repo], []).values()) == [0] * 10
    candidate_tree = _git(repo, "rev-parse", f"{candidate_sha}^{{tree}}")
    unrelated_sha = _git(repo, "commit-tree", candidate_tree, "-m", "unrelated commit")
    assert list(gate.audit_bootstrap_clearance(repo, candidate_sha, ["deploy"], [unrelated_sha]).values()) == [0] * 10
    _expect_invalid(lambda: gate.audit_bootstrap_clearance(repo, candidate_sha, ["deploy"], [root_sha]))

    design_name = "-".join(("agent", "workflow", "design")) + ".md"
    forbidden = repo / "agent-discipline" / design_name
    forbidden.write_text("# " + " ".join(("Agent", "Workflow", "Design")) + "\n", encoding="utf-8")
    mapping = repo / "agent-discipline" / "governance-mapping.md"
    mapping.write_text("agent-discipline/" + design_name + "\n", encoding="utf-8")
    assert list(gate.audit_bootstrap_clearance(repo, candidate_sha, ["deploy"], []).values()) == [0] * 10
    design_sha = _commit(repo, "candidate containing temporary design material")
    design_report = _clearance_report(
        _expect_invalid(lambda: gate.audit_bootstrap_clearance(repo, design_sha, ["deploy"], []))
    )
    assert design_report["bootstrap_design_file_count"] > 0
    assert design_report["bootstrap_design_reference_count"] > 0
    assert design_report["bootstrap_governance_reference_count"] > 0
    forbidden.unlink()
    mapping.unlink()
    clean_sha = _commit(repo, "remove temporary design material")

    boot = "boot" + "strap"
    removal_words = ("remo" + "ve", "be" + "fore", "fi" + "nal", "P" + "0")
    unscoped = repo / "notes" / "release.md"
    unscoped.parent.mkdir()
    unscoped.write_text(
        "# " + " ".join(("Temporary", "P0", boot, "Workflow")) + "\n"
        + "- " + " ".join(removal_words) + "\n",
        encoding="utf-8",
    )
    unscoped_sha = _commit(repo, "candidate containing unscoped residue")
    unscoped_report = _clearance_report(
        _expect_invalid(lambda: gate.audit_bootstrap_clearance(repo, unscoped_sha, ["deploy"], []))
    )
    assert unscoped_report["temporary_heading_count"] > 0
    assert unscoped_report["temporary_removal_marker_count"] > 0
    unscoped.unlink()
    clean_sha = _commit(repo, "remove unscoped residue")

    debt_note = repo / "notes" / "debt.md"
    debt_note.write_text(
        "- " + "-".join(("P0", "BS", "17")) + "\n"
        + "- " + " ".join((boot, "evidence", "pointer")) + "\n"
        + "- " + " ".join((boot, "debt", "OPEN")) + "\n",
        encoding="utf-8",
    )
    debt_sha = _commit(repo, "candidate containing debt residue")
    debt_report = _clearance_report(
        _expect_invalid(lambda: gate.audit_bootstrap_clearance(repo, debt_sha, ["deploy"], []))
    )
    assert debt_report["bootstrap_debt_id_count"] > 0
    assert debt_report["bootstrap_debt_pointer_count"] > 0
    assert debt_report["open_bootstrap_debt_count"] > 0
    debt_note.unlink()
    clean_sha = _commit(repo, "remove debt residue")

    external = tmp_path / "external-stage"
    external.mkdir()
    external_payload = external / "payload.md"
    external_payload.write_text(" ".join(removal_words) + "\n", encoding="utf-8")
    external_report = _clearance_report(
        _expect_invalid(lambda: gate.audit_bootstrap_clearance(repo, clean_sha, [external], []))
    )
    assert external_report["bootstrap_generated_or_payload_count"] > 0
