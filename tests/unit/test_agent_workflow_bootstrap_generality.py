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
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "agent-discipline" / "contracts" / "workflow-v1.json"
CASE_CATALOG_PATH = ROOT / "docs" / "tests" / "rtd-config-test-cases.md"
TEST_STRATEGY_PATH = ROOT / "docs" / "tests" / "rtd-config-test-strategy.md"
GATE_PATH = (
    ROOT
    / "agent-discipline"
    / "skills"
    / "agent-workflow"
    / "scripts"
    / "workflow_gate.py"
)
HANDOFF_GUARD_PATH = (
    ROOT
    / "agent-discipline"
    / "skills"
    / "agent-workflow"
    / "scripts"
    / "handoff_guard.py"
)
WORKFLOW_SKILL_PATH = ROOT / "agent-discipline" / "skills" / "agent-workflow" / "SKILL.md"
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
            "impact_flags": [
                flag
                for flag in contract["impact_flags"]
                if flag in {"agent-runtime", "test-contract"}
            ],
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


_CHECKPOINT_EVIDENCE = (
    ("test_approved", "human_review_1"),
    ("candidate_built", "candidate"),
    ("tester_passed", "tester"),
    ("reviewer_accepted", "reviewer"),
    ("draft_pr_ready", "draft_pr"),
    ("complete", "final_human_review"),
)


def _record_at_checkpoint(checkpoint):
    record = _record()
    checkpoints = _contract()["checkpoints"]
    record["checkpoint"] = checkpoint
    checkpoint_index = checkpoints.index(checkpoint)
    for evidence_checkpoint, evidence_name in _CHECKPOINT_EVIDENCE:
        if checkpoints.index(evidence_checkpoint) > checkpoint_index:
            record[evidence_name] = None
    return record


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


def test_impact_flags_are_a_canonical_ordered_subsequence():
    gate = _gate()
    canonical = _contract()["impact_flags"]
    selected = canonical[1::3]
    record = _record()
    record["classification"]["impact_flags"] = selected
    gate.validate_record(record, contract_path=CONTRACT_PATH)

    reordered = copy.deepcopy(record)
    reordered["classification"]["impact_flags"] = list(reversed(selected))
    _expect_invalid(
        lambda: gate.validate_record(reordered, contract_path=CONTRACT_PATH)
    )


def test_classification_still_rejects_duplicate_flags_and_missing_route():
    gate = _gate()
    canonical = _contract()["impact_flags"]
    duplicate = _record()
    duplicate["classification"]["impact_flags"] = [canonical[2], canonical[2]]
    _expect_invalid(
        lambda: gate.validate_record(duplicate, contract_path=CONTRACT_PATH)
    )

    missing_route = _record()
    del missing_route["classification"]["route"]
    _expect_invalid(
        lambda: gate.validate_record(missing_route, contract_path=CONTRACT_PATH)
    )


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


def test_draft_pr_url_requires_an_absolute_https_url():
    gate = _gate()
    valid = _record()
    valid["draft_pr"]["url"] = "https://review.invalid/pulls/%39%32%33?mode=draft"
    gate.validate_record(valid, contract_path=CONTRACT_PATH)

    for invalid_url in (
        "http://review.invalid/pulls/923",
        "review.invalid/pulls/923",
        "https:///pulls/923",
        "https://review.invalid/pulls/bad path",
        923,
    ):
        record = _record()
        record["draft_pr"]["url"] = invalid_url
        _expect_invalid(
            lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH)
        )


def test_draft_pr_url_rejects_malformed_and_ambiguous_locators():
    gate = _gate()
    malformed = [
        "https://review.invalid/pulls/%",
        "https://review.invalid/pulls/%0G",
        r"https://review.invalid\@mirror.invalid/pulls/923",
        "https://review..invalid/pulls/923",
        "https://:443/pulls/923",
        "https://reader:token@review.invalid/pulls/923",
        "https://review.invalid:invalid/pulls/923",
        "https://review.invalid/pulls/923#https://mirror.invalid/pulls/923",
    ]
    malformed.extend(
        f"https://review.invalid/pulls/a{chr(code)}b"
        for code in (*range(32), 127)
    )
    malformed.extend(
        f"https://review.invalid/pulls/%{code:02X}"
        for code in (*range(32), 92, 127)
    )

    accepted = []
    for invalid_url in malformed:
        record = _record()
        record["draft_pr"]["url"] = invalid_url
        try:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        except gate.WorkflowValidationError:
            continue
        accepted.append(repr(invalid_url))
    assert not accepted, "malformed draft PR locators accepted:\n" + "\n".join(accepted)


def test_draft_pr_url_rejects_c1_controls_and_preserves_utf8_data():
    gate = _gate()
    for suffix in ("✓", "%E2%9C%93", "caf%C3%A9"):
        record = _record()
        record["draft_pr"]["url"] = f"https://review.invalid/pulls/{suffix}"
        gate.validate_record(record, contract_path=CONTRACT_PATH)

    invalid_urls = [
        f"https://review.invalid/pulls/a{chr(code)}b"
        for code in range(0x80, 0xA0)
    ]
    invalid_urls.extend(
        f"https://review.invalid/pulls/%{code:02X}"
        for code in range(0x80, 0xA0)
    )
    invalid_urls.extend(
        f"https://review.invalid/pulls/%C2%{code:02X}"
        for code in range(0x80, 0xA0)
    )
    accepted = []
    for invalid_url in invalid_urls:
        record = _record()
        record["draft_pr"]["url"] = invalid_url
        try:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        except gate.WorkflowValidationError:
            continue
        accepted.append(repr(invalid_url))
    assert not accepted, "C1-control draft PR locators accepted:\n" + "\n".join(accepted)


def test_draft_pr_url_rejects_legacy_ipv4_without_rejecting_unambiguous_hosts():
    gate = _gate()
    for hostname in (
        "192.0.2.17",
        "[2001:db8::17]",
        "xn--bcher-kva.invalid",
        "build-123.invalid",
        "deadbeef.invalid",
    ):
        record = _record()
        record["draft_pr"]["url"] = f"https://{hostname}/pulls/923"
        gate.validate_record(record, contract_path=CONTRACT_PATH)

    accepted = []
    for hostname in (
        "0x7f000001",
        "0X7F000001",
        "2130706433",
        "017700000001",
        "127.1",
        "0177.0.0.1",
        "0x7f.0.0.1",
        "127.0x0.0.1",
        "0x7f.00.0x0.1",
    ):
        record = _record()
        record["draft_pr"]["url"] = f"https://{hostname}/pulls/923"
        try:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        except gate.WorkflowValidationError:
            continue
        accepted.append(hostname)
    assert not accepted, "legacy numeric IPv4 hosts accepted: " + ", ".join(accepted)


def test_final_human_review_requires_same_repository_pr_conversation_comments():
    gate = _gate()
    examples = (
        (
            "stellar-labs/drive_kernel",
            2861,
            "https://github.com/stellar-labs/drive_kernel/issues/2861#issuecomment-77123",
            "https://github.com/stellar-labs/drive_kernel/pull/4729#issuecomment-830041",
            "release authority alpha",
            "ACCEPT_AFTER_SAFETY_REVIEW",
        ),
        (
            "https://code.example.net/Vector-Works/brake.control.git",
            643,
            "https://code.example.net/Vector-Works/brake.control/issues/643#issuecomment-77123",
            "https://code.example.net/Vector-Works/brake.control/pull/906#issuecomment-410007",
            "independent approver beta",
            "ship-with-recorded-rationale",
        ),
    )
    for repository, issue_number, review_1_url, comment_url, actor, decision in examples:
        record = _record()
        record["issue"]["repository"] = repository
        record["issue"]["number"] = issue_number
        record["human_review_1"]["comment_url"] = review_1_url
        record["final_human_review"]["comment_url"] = comment_url
        record["final_human_review"]["actor"] = actor
        record["final_human_review"]["decision"] = decision
        gate.validate_record(record, contract_path=CONTRACT_PATH)


def test_final_human_review_rejects_raw_empty_delimiters_before_url_parsing():
    gate = _gate()
    examples = (
        ("forge.alpha.invalid", "Aurora-Systems", "torque_core", 381, 284, 65091),
        ("code.beta.invalid", "Helix-Labs", "steer.unit", 642, 917, 408203),
    )
    accepted = []
    for host, owner, name, issue_number, pull_number, comment_number in examples:
        record = _record()
        record["issue"]["repository"] = f"https://{host}/{owner}/{name}.git"
        record["issue"]["number"] = issue_number
        record["human_review_1"]["comment_url"] = (
            f"https://{host}/{owner}/{name}/issues/{issue_number}"
            f"#issuecomment-{comment_number + 1}"
        )
        base = f"https://{host}/{owner}/{name}/pull/{pull_number}"
        fragment = f"#issuecomment-{comment_number}"
        record["final_human_review"]["comment_url"] = base + fragment
        record["final_human_review"]["actor"] = f"release authority for {owner}"
        record["final_human_review"]["decision"] = f"accept pull {pull_number}"
        gate.validate_record(record, contract_path=CONTRACT_PATH)

        invalid_urls = (
            base + "?" + fragment,
            base + ";" + fragment,
            f"https://{host}:/{owner}/{name}/pull/{pull_number}{fragment}",
        )
        for invalid_url in invalid_urls:
            malformed = copy.deepcopy(record)
            malformed["final_human_review"]["comment_url"] = invalid_url
            try:
                gate.validate_record(malformed, contract_path=CONTRACT_PATH)
            except gate.WorkflowValidationError:
                continue
            accepted.append(invalid_url)
    assert not accepted, "raw noncanonical delimiters accepted:\n" + "\n".join(accepted)


def test_final_human_review_rejects_noncanonical_pr_comment_locators():
    gate = _gate()
    repository = "https://review.example.net/Delta-Works/power_node.git"
    issue_number = 502
    valid_base = "https://review.example.net/Delta-Works/power_node/pull/418"
    invalid_urls = (
        "http://review.example.net/Delta-Works/power_node/pull/418#issuecomment-62001",
        "review.example.net/Delta-Works/power_node/pull/418#issuecomment-62001",
        "https://mirror.example.net/Delta-Works/power_node/pull/418#issuecomment-62001",
        "https://review.example.net/Other-Works/power_node/pull/418#issuecomment-62001",
        "https://review.example.net/Delta-Works/other_node/pull/418#issuecomment-62001",
        "https://reader:token@review.example.net/Delta-Works/power_node/pull/418#issuecomment-62001",
        "https://review.example.net:443/Delta-Works/power_node/pull/418#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/issues/418#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/pull/418/reviews/62001#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/pull/418/files#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/pull/0#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/pull/0418#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/pull/not-decimal#issuecomment-62001",
        "https://review.example.net/Delta-Works/power_node/pull/418?view=conversation#issuecomment-62001",
        valid_base,
        f"{valid_base}#pullrequestreview-62001",
        f"{valid_base}#issuecomment-0",
        f"{valid_base}#issuecomment-062001",
        f"{valid_base}#issuecomment-not-decimal",
        418,
    )
    accepted = []
    for invalid_url in invalid_urls:
        record = _record()
        record["issue"]["repository"] = repository
        record["issue"]["number"] = issue_number
        record["human_review_1"]["comment_url"] = (
            "https://review.example.net/Delta-Works/power_node/issues/502"
            "#issuecomment-77123"
        )
        record["final_human_review"]["comment_url"] = invalid_url
        try:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        except gate.WorkflowValidationError:
            continue
        accepted.append(repr(invalid_url))
    assert not accepted, "noncanonical final-review locators accepted:\n" + "\n".join(accepted)


def test_final_human_review_rejects_encoded_ambiguity_and_control_characters():
    gate = _gate()
    valid_base = "https://secure.example.org/Control-Team/chassis_fw/pull/719"
    invalid_urls = [
        f"{valid_base}%",
        f"{valid_base}%0G#issuecomment-92017",
        f"{valid_base}%FF#issuecomment-92017",
        f"{valid_base}%C0%AF#issuecomment-92017",
        "https://secure.example.org/Control-Team/chassis_fw/pull/%37%31%39#issuecomment-92017",
        "https://secure.example.org/Control-Team/chassis_fw/pull/719%2Ffiles#issuecomment-92017",
        "https://secure.example.org/Control-Team/chassis_fw/pull/719%3Ftab#issuecomment-92017",
        "https://secure.example.org/Control-Team/chassis_fw/pull/719%23issuecomment-92017",
        "https://secure.example.org/Control-Team/chassis_fw/pull/719#issuecomment-%39%32%30%31%37",
        "https://secure.example.org%2FControl-Team/chassis_fw/pull/719#issuecomment-92017",
        r"https://secure.example.org\@mirror.example.org/Control-Team/chassis_fw/pull/719#issuecomment-92017",
        r"https://secure.example.org/Control-Team\chassis_fw/pull/719#issuecomment-92017",
        "https://secure.example.org/Control-Team%5Cchassis_fw/pull/719#issuecomment-92017",
        "https://secure.example.org/Control-Team/chassis_fw/pull/719%20#issuecomment-92017",
    ]
    invalid_urls.extend(
        f"{valid_base}{chr(code)}#issuecomment-92017"
        for code in (*range(32), *range(0x80, 0xA0), 127)
    )
    invalid_urls.extend(
        f"{valid_base}%{code:02X}#issuecomment-92017"
        for code in (*range(32), *range(0x80, 0xA0), 92, 127)
    )
    invalid_urls.extend(
        f"{valid_base}%C2%{code:02X}#issuecomment-92017"
        for code in range(0x80, 0xA0)
    )

    accepted = []
    for invalid_url in invalid_urls:
        record = _record()
        record["issue"]["repository"] = "secure.example.org/Control-Team/chassis_fw"
        record["issue"]["number"] = 811
        record["human_review_1"]["comment_url"] = (
            "https://secure.example.org/Control-Team/chassis_fw/issues/811"
            "#issuecomment-77123"
        )
        record["final_human_review"]["comment_url"] = invalid_url
        try:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        except gate.WorkflowValidationError:
            continue
        accepted.append(repr(invalid_url))
    assert not accepted, "ambiguous final-review locators accepted:\n" + "\n".join(accepted)


@pytest.mark.parametrize("hostname", ("review..example", "0x7f000001"))
def test_final_human_review_requires_an_unambiguous_repository_host(hostname):
    gate = _gate()
    record = _record()
    record["issue"]["repository"] = f"https://{hostname}/Safety-Team/body_gateway.git"
    record["issue"]["number"] = 347
    record["human_review_1"]["comment_url"] = (
        f"https://{hostname}/Safety-Team/body_gateway/issues/347#issuecomment-58103"
    )
    record["final_human_review"]["comment_url"] = (
        f"https://{hostname}/Safety-Team/body_gateway/pull/126#issuecomment-74009"
    )
    _expect_invalid(
        lambda: gate.validate_record(record, contract_path=CONTRACT_PATH)
    )


def test_final_human_review_retains_closed_stage_and_candidate_bindings():
    gate = _gate()
    valid = _record()
    valid["final_human_review"]["actor"] = "arbitrary-release-authority"
    valid["final_human_review"]["decision"] = "ARBITRARY-NONEMPTY-DECISION"
    gate.validate_record(valid, contract_path=CONTRACT_PATH)

    mutations = []
    for field in ("actor", "decision"):
        record = _record()
        record["final_human_review"][field] = ""
        mutations.append(record)
    stale = _record()
    stale["final_human_review"]["candidate_sha"] = "5" * 40
    mutations.append(stale)
    premature = _record()
    premature["checkpoint"] = "draft_pr_ready"
    mutations.append(premature)
    for record in mutations:
        _expect_invalid(
            lambda record=record: gate.validate_record(
                record, contract_path=CONTRACT_PATH
            )
        )


def test_category_a_case_catalog_has_no_category_b_agents_pointer():
    assert "AGENTS.md" not in CASE_CATALOG_PATH.read_text(encoding="utf-8")


def test_category_a_test_strategy_has_no_category_b_agents_pointer():
    assert "AGENTS.md" not in TEST_STRATEGY_PATH.read_text(encoding="utf-8")


def test_checkpoint_evidence_is_null_before_generation_and_closed_after_generation():
    gate = _gate()
    contract = _contract()
    checkpoints = contract["checkpoints"]
    complete = _record()

    for checkpoint in checkpoints:
        gate.validate_record(_record_at_checkpoint(checkpoint), contract_path=CONTRACT_PATH)

    for evidence_checkpoint, evidence_name in _CHECKPOINT_EVIDENCE:
        generated_at = checkpoints.index(evidence_checkpoint)
        for earlier_checkpoint in checkpoints[:generated_at]:
            forged = _record_at_checkpoint(earlier_checkpoint)
            forged[evidence_name] = copy.deepcopy(complete[evidence_name])
            _expect_invalid(
                lambda forged=forged: gate.validate_record(forged, contract_path=CONTRACT_PATH)
            )

        missing = _record_at_checkpoint(evidence_checkpoint)
        missing[evidence_name] = None
        _expect_invalid(
            lambda missing=missing: gate.validate_record(missing, contract_path=CONTRACT_PATH)
        )

        incomplete = _record_at_checkpoint(evidence_checkpoint)
        del incomplete[evidence_name][contract["object_fields"][evidence_name][-1]]
        _expect_invalid(
            lambda incomplete=incomplete: gate.validate_record(incomplete, contract_path=CONTRACT_PATH)
        )


def test_pass_checkpoints_reject_every_non_pass_terminal_verdict():
    gate = _gate()
    non_pass_verdicts = set(_contract()["verdicts"]) - {"PASS"}
    for checkpoint, evidence_name in (
        ("tester_passed", "tester"),
        ("reviewer_accepted", "reviewer"),
    ):
        for verdict in non_pass_verdicts:
            record = _record_at_checkpoint(checkpoint)
            record[evidence_name]["verdict"] = verdict
            _expect_invalid(
                lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH)
            )


def test_finding_dispositions_and_attempt_bounds_are_exact():
    gate = _gate()
    for finding_class, viability, disposition, valid in [
        ("F0", None, "BLOCK", True),
        ("F0", None, "FREEZE_FOR_NEXT_STAGE", False),
        ("F1", None, "REWORK_CURRENT_STAGE", True),
        ("F2", [True] * 6, "FREEZE_FOR_NEXT_STAGE", True),
        ("F2", [True, True, False, True, True, True], "BLOCK", True),
        ("F2", [True, True, False, True, True, True], "FREEZE_FOR_NEXT_STAGE", False),
        ("F3", None, "DEFER_NON_BLOCKING", True),
        ("F4", None, "FINAL_ACCEPT", False),
    ]:
        record = _record()
        finding = record["findings"][0]
        finding["class"] = finding_class
        finding["freeze_viability"] = (
            None
            if viability is None
            else dict(zip(_contract()["object_fields"]["freeze_viability"], viability))
        )
        finding["disposition"] = disposition
        if valid:
            gate.validate_record(record, contract_path=CONTRACT_PATH)
        else:
            _expect_invalid(lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH))
    for attempt in (0, 4, True):
        record = _record()
        record["attempt"]["candidate_attempt"] = attempt
        _expect_invalid(lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH))


def test_freeze_viability_is_null_outside_f2_and_closed_for_f2():
    gate = _gate()
    non_f2_dispositions = {
        "F0": "BLOCK",
        "F1": "REWORK_CURRENT_STAGE",
        "F3": "DEFER_NON_BLOCKING",
        "F4": "DEFER_NON_BLOCKING",
    }
    stale_viability = copy.deepcopy(_record()["findings"][0]["freeze_viability"])
    for finding_class, disposition in non_f2_dispositions.items():
        record = _record()
        finding = record["findings"][0]
        finding["class"] = finding_class
        finding["freeze_viability"] = None
        finding["disposition"] = disposition
        gate.validate_record(record, contract_path=CONTRACT_PATH)

        finding["freeze_viability"] = copy.deepcopy(stale_viability)
        _expect_invalid(
            lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH)
        )

    missing = _record()
    missing["findings"][0]["freeze_viability"] = None
    _expect_invalid(lambda: gate.validate_record(missing, contract_path=CONTRACT_PATH))

    malformed_values = []
    incomplete = copy.deepcopy(stale_viability)
    incomplete.pop(next(iter(incomplete)))
    malformed_values.append(incomplete)
    extra = copy.deepcopy(stale_viability)
    extra["uncontracted"] = True
    malformed_values.append(extra)
    non_boolean = copy.deepcopy(stale_viability)
    non_boolean[next(iter(non_boolean))] = 1
    malformed_values.append(non_boolean)
    for viability in malformed_values:
        record = _record()
        record["findings"][0]["freeze_viability"] = viability
        _expect_invalid(
            lambda record=record: gate.validate_record(record, contract_path=CONTRACT_PATH)
        )


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


def _git_input(repo, arguments, data):
    return subprocess.run(
        ["git", *arguments], cwd=repo, check=True, input=data,
        capture_output=True,
    ).stdout.strip().decode("ascii")


def _commit_tree_with_long_payload_path(repo, content, *, root_name="payload"):
    blob = _git_input(repo, ["hash-object", "-w", "--stdin"], content)
    tree = _git_input(
        repo,
        ["mktree", "-z"],
        f"100644 blob {blob}\tpayload.txt\0".encode("ascii"),
    )
    components = [f"segment-{index:03d}-" + "x" * 176 for index in range(180)]
    for component in reversed(components):
        tree = _git_input(
            repo,
            ["mktree", "-z"],
            f"040000 tree {tree}\t{component}\0".encode("ascii"),
        )
    tree = _git_input(
        repo,
        ["mktree", "-z"],
        f"040000 tree {tree}\t{root_name}\0".encode("ascii"),
    )
    return _git(repo, "commit-tree", tree, "-m", "long object-only payload")


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


def test_clearance_reads_long_tracked_paths_through_tree_object_ids(tmp_path):
    gate = _gate()
    repo = tmp_path / "long-object-tree"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Generality Test")
    _git(repo, "config", "user.email", "generality@example.invalid")
    removal_words = " ".join(("remo" + "ve", "be" + "fore", "fi" + "nal", "P" + "0"))
    candidate_sha = _commit_tree_with_long_payload_path(
        repo,
        (removal_words + "\n").encode("utf-8"),
    )

    report = _clearance_report(
        _expect_invalid(lambda: gate.audit_bootstrap_clearance(repo, candidate_sha, ["payload"], []))
    )
    assert report["bootstrap_generated_or_payload_count"] == 1
    assert report["temporary_removal_marker_count"] == 1


@pytest.mark.parametrize(
    ("repository_name", "marker_words", "numeric_id"),
    (
        ("clearance-alpha", ("P0", "BS"), 28461),
        ("clearance-beta", ("P0", "bootstrap", "debt"), 90317),
    ),
)
def test_clearance_rejects_bare_and_numeric_markers_across_declared_roots(
    tmp_path, repository_name, marker_words, numeric_id
):
    gate = _gate()
    repo = tmp_path / repository_name
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Synthetic Clearance")
    _git(repo, "config", "user.email", "clearance@example.invalid")
    neutral_root = repo / "handoff-zone"
    neutral_root.mkdir()
    (neutral_root / "state.txt").write_text("durable state\n", encoding="utf-8")
    ancestor_sha = _commit(repo, "clean ancestor evidence")
    (neutral_root / "next.txt").write_text("durable next state\n", encoding="utf-8")
    clean_sha = _commit(repo, "clean candidate")
    clean_report = gate.audit_bootstrap_clearance(
        repo, clean_sha, ["handoff-zone"], []
    )
    assert list(clean_report.values()) == [0] * 10

    marker = "-".join(marker_words)
    (neutral_root / "marker.txt").write_text(marker + "\n", encoding="utf-8")
    notes = repo / "notes"
    notes.mkdir()
    (notes / "identity.txt").write_text(
        f"{marker}-{numeric_id}\n", encoding="utf-8"
    )
    candidate_sha = _commit(repo, "candidate with temporary marker residue")
    candidate_report = _clearance_report(
        _expect_invalid(
            lambda: gate.audit_bootstrap_clearance(
                repo, candidate_sha, ["handoff-zone"], [ancestor_sha]
            )
        )
    )
    expected_candidate = dict.fromkeys(clean_report, 0)
    expected_candidate["bootstrap_generated_or_payload_count"] = 1
    expected_candidate["bootstrap_commit_ancestor_count"] = 1
    expected_candidate["bootstrap_debt_id_count"] = 2
    assert candidate_report == expected_candidate

    outside = tmp_path / f"outside-{repository_name}"
    outside.mkdir()
    (outside / "markers.txt").write_text(
        f"{marker}\n{marker}-{numeric_id + 7}\n", encoding="utf-8"
    )
    external_report = _clearance_report(
        _expect_invalid(
            lambda: gate.audit_bootstrap_clearance(repo, clean_sha, [outside], [])
        )
    )
    expected_external = dict.fromkeys(clean_report, 0)
    expected_external["bootstrap_generated_or_payload_count"] = 1
    expected_external["bootstrap_debt_id_count"] = 2
    assert external_report == expected_external


def test_clearance_reads_bare_and_numeric_markers_from_long_candidate_paths(tmp_path):
    gate = _gate()
    repo = tmp_path / "long-marker-tree"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Synthetic Long Path")
    _git(repo, "config", "user.email", "long-path@example.invalid")
    marker = "-".join(("P0", "BS"))
    candidate_sha = _commit_tree_with_long_payload_path(
        repo,
        f"{marker}\n{marker}-73146\n".encode("utf-8"),
        root_name="archive-zone",
    )

    report = _clearance_report(
        _expect_invalid(
            lambda: gate.audit_bootstrap_clearance(
                repo, candidate_sha, ["archive-zone"], []
            )
        )
    )
    expected = dict.fromkeys(report, 0)
    expected["bootstrap_generated_or_payload_count"] = 1
    expected["bootstrap_debt_id_count"] = 2
    assert report == expected


@pytest.mark.parametrize("raw_size", [b"+1", b"-1", b"1x"])
def test_clearance_rejects_non_decimal_cat_file_blob_sizes(tmp_path, monkeypatch, raw_size):
    gate = _gate()
    repo = tmp_path / "malformed-batch-size"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Generality Test")
    _git(repo, "config", "user.email", "generality@example.invalid")
    payload = repo / "payload.bin"
    payload.write_bytes(b"x")
    candidate_sha = _commit(repo, "arbitrary binary payload")
    object_id = _git(repo, "hash-object", "payload.bin")
    original_run = gate.subprocess.run

    def malformed_batch(arguments, *args, **kwargs):
        if arguments[:3] == ["git", "cat-file", "--batch"]:
            output = object_id.encode("ascii") + b" blob " + raw_size + b"\n" + b"x\n"
            return subprocess.CompletedProcess(arguments, 0, stdout=output, stderr=b"")
        return original_run(arguments, *args, **kwargs)

    monkeypatch.setattr(gate.subprocess, "run", malformed_batch)
    error = _expect_invalid(
        lambda: gate.audit_bootstrap_clearance(repo, candidate_sha, ["payload.bin"], [])
    )
    assert "invalid blob size" in str(error)


def _run_handoff_guard(repo, *arguments):
    return subprocess.run(
        [sys.executable, str(HANDOFF_GUARD_PATH), *arguments],
        cwd=repo,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("repository_name", "role", "contract_relative", "evidence_relative", "command", "result_relative", "timeout"),
    (
        (
            "aurora-handoff",
            "explorer-probe",
            "policy/aurora.json",
            "records/north",
            "from pathlib import Path; Path('aurora.done').write_text('north', encoding='utf-8')",
            "aurora.done",
            11,
        ),
        (
            "zephyr-handoff",
            "review-auditor",
            "rules/zephyr.txt",
            "audit/east",
            "from pathlib import Path; Path('zephyr.result').write_text('east', encoding='utf-8')",
            "zephyr.result",
            19,
        ),
    ),
)
def test_handoff_guard_runs_independent_synthetic_git_handoffs(
    tmp_path, repository_name, role, contract_relative, evidence_relative,
    command, result_relative, timeout
):
    repo = tmp_path / repository_name
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Synthetic Handoff")
    _git(repo, "config", "user.email", "handoff@example.invalid")
    contract = repo / contract_relative
    contract.parent.mkdir(parents=True)
    contract.write_text(f"contract for {role}\n", encoding="utf-8")
    base_sha = _commit(repo, f"establish {role} base")
    (repo / f"lane-{role}.txt").write_text("lane identity\n", encoding="utf-8")
    lane_sha = _commit(repo, f"advance {role} lane")
    contract_blob_sha = _git(repo, "hash-object", contract_relative)
    evidence = repo / evidence_relative
    evidence.mkdir(parents=True)
    manifest, receipt, event_log = (
        evidence / "manifest.json", evidence / "receipt.json", evidence / "events.jsonl"
    )
    child_argv = [sys.executable, "-c", command]
    common = ["--manifest", str(manifest), "--receipt", str(receipt), "--event-log", str(event_log)]
    prepare = _run_handoff_guard(
        repo, "prepare", "--role", role, "--expected-top-level", str(repo.resolve()),
        "--base-sha", base_sha, "--lane-sha", lane_sha,
        "--contract-path", contract_relative, "--contract-blob-sha", contract_blob_sha,
        *common, "--timeout-seconds", str(timeout), "--", *child_argv,
    )
    assert prepare.returncode == 0, prepare.stderr
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_value["role"] == role
    assert manifest_value["argv"] == child_argv
    assert manifest_value["timeout_seconds"] == timeout

    (repo / f"untracked-{role}.txt").write_text("dirty state is outside identity\n", encoding="utf-8")
    checked = _run_handoff_guard(repo, "check-handoff", *common)
    assert checked.returncode == 0, checked.stderr
    executed = _run_handoff_guard(repo, "run", *common)
    assert executed.returncode == 0, executed.stderr
    assert (repo / result_relative).is_file()
    events = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert [event["operation"] for event in events] == ["prepare", "check-handoff", "run"]
    assert [event["outcome"] for event in events] == ["PREPARED", "CHECKED", "EXITED"]
    assert {event["manifest_sha256"] for event in events} == {
        hashlib.sha256(manifest.read_bytes()).hexdigest()
    }
    assert json.loads(receipt.read_text(encoding="utf-8")) == events[-1]


@pytest.mark.parametrize("operation", ("prepare", "check-handoff", "run"))
@pytest.mark.parametrize("base_kind", ("missing", "blob", "tree", "tag", "nonancestor"))
def test_handoff_guard_rejects_invalid_base_for_every_operation(
    tmp_path, operation, base_kind
):
    role = f"{base_kind}-{operation}-probe"
    repo = tmp_path / f"identity-{base_kind}-{operation}"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Synthetic Identity")
    _git(repo, "config", "user.email", "identity@example.invalid")
    contract_relative = f"policy/{base_kind}/{operation}.txt"
    contract = repo / contract_relative
    contract.parent.mkdir(parents=True)
    contract.write_text(f"identity contract for {role}\n", encoding="utf-8")
    valid_base = _commit(repo, f"establish {role} base")
    (repo / "lane.txt").write_text(f"lane for {role}\n", encoding="utf-8")
    lane_sha = _commit(repo, f"advance {role} lane")
    contract_blob_sha = _git(repo, "hash-object", contract_relative)
    if base_kind == "missing":
        invalid_base = "e" * 40
    elif base_kind == "blob":
        invalid_base = contract_blob_sha
    elif base_kind == "tree":
        invalid_base = _git(repo, "rev-parse", "HEAD^{tree}")
    elif base_kind == "tag":
        _git(repo, "tag", "-a", "detached-base", valid_base, "-m", f"tag for {role}")
        invalid_base = _git(repo, "rev-parse", "refs/tags/detached-base")
    else:
        invalid_base = _git(
            repo, "commit-tree", _git(repo, "rev-parse", "HEAD^{tree}"),
            "-m", f"detached {role}",
        )
    evidence = repo / "identity-evidence"
    evidence.mkdir()
    manifest, receipt, event_log = (
        evidence / "manifest.json", evidence / "receipt.json", evidence / "events.jsonl"
    )
    marker = f"spawned-{base_kind}-{operation}.txt"
    child_argv = [
        sys.executable, "-c",
        f"from pathlib import Path; Path('{marker}').write_text('spawned', encoding='utf-8')",
    ]
    common = ["--manifest", str(manifest), "--receipt", str(receipt), "--event-log", str(event_log)]

    if operation != "prepare":
        prepared = _run_handoff_guard(
            repo, "prepare", "--role", role, "--expected-top-level", str(repo.resolve()),
            "--base-sha", valid_base, "--lane-sha", lane_sha,
            "--contract-path", contract_relative, "--contract-blob-sha", contract_blob_sha,
            *common, "--timeout-seconds", "23", "--", *child_argv,
        )
        assert prepared.returncode == 0, prepared.stderr
        manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
        manifest_value["base_sha"] = invalid_base
        raw = json.dumps(
            manifest_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest.write_bytes(raw)
        receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
        receipt_value["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        receipt.write_text(json.dumps(receipt_value), encoding="utf-8")
        result = _run_handoff_guard(repo, operation, *common)
    else:
        result = _run_handoff_guard(
            repo, "prepare", "--role", role, "--expected-top-level", str(repo.resolve()),
            "--base-sha", invalid_base, "--lane-sha", lane_sha,
            "--contract-path", contract_relative, "--contract-blob-sha", contract_blob_sha,
            *common, "--timeout-seconds", "23", "--", *child_argv,
        )

    assert result.returncode == 1, result.stderr
    assert json.loads(receipt.read_text(encoding="utf-8"))["outcome"] == "REJECTED"
    assert not (repo / marker).exists()


@pytest.mark.parametrize("operation", ("check-handoff", "run"))
@pytest.mark.parametrize(
    "receipt_state", ("missing", "malformed", "duplicate", "manifest-rewrite")
)
def test_handoff_guard_requires_prior_receipt_digest_continuity(
    tmp_path, operation, receipt_state
):
    role = f"continuity-{receipt_state}-{operation}"
    repo = tmp_path / f"continuity-{receipt_state}-{operation}"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Synthetic Continuity")
    _git(repo, "config", "user.email", "continuity@example.invalid")
    contract_relative = f"rules/{receipt_state}/{operation}.cfg"
    contract = repo / contract_relative
    contract.parent.mkdir(parents=True)
    contract.write_text(f"continuity contract for {role}\n", encoding="utf-8")
    base_sha = _commit(repo, f"establish {role} base")
    (repo / "lane.txt").write_text(f"lane for {role}\n", encoding="utf-8")
    lane_sha = _commit(repo, f"advance {role} lane")
    contract_blob_sha = _git(repo, "hash-object", contract_relative)
    evidence = repo / "continuity-evidence"
    evidence.mkdir()
    manifest, receipt, event_log = (
        evidence / "manifest.json", evidence / "receipt.json", evidence / "events.jsonl"
    )
    marker = f"spawned-{receipt_state}-{operation}.txt"
    child_argv = [
        sys.executable, "-c",
        f"from pathlib import Path; Path('{marker}').write_text('spawned', encoding='utf-8')",
    ]
    common = ["--manifest", str(manifest), "--receipt", str(receipt), "--event-log", str(event_log)]
    prepared = _run_handoff_guard(
        repo, "prepare", "--role", role, "--expected-top-level", str(repo.resolve()),
        "--base-sha", base_sha, "--lane-sha", lane_sha,
        "--contract-path", contract_relative, "--contract-blob-sha", contract_blob_sha,
        *common, "--timeout-seconds", "31", "--", *child_argv,
    )
    assert prepared.returncode == 0, prepared.stderr

    if receipt_state == "missing":
        receipt.unlink()
    elif receipt_state == "malformed":
        receipt.write_bytes(b"{malformed-receipt")
    elif receipt_state == "duplicate":
        receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
        correct = receipt_value["manifest_sha256"]
        field = f'"manifest_sha256":"{correct}"'
        duplicate = f'"manifest_sha256":"{"0" * 64}",{field}'
        receipt.write_text(
            receipt.read_text(encoding="utf-8").replace(field, duplicate, 1),
            encoding="utf-8",
        )
    else:
        manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
        manifest.write_text(
            json.dumps(manifest_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    result = _run_handoff_guard(repo, operation, *common)

    assert result.returncode == 1, result.stderr
    assert json.loads(receipt.read_text(encoding="utf-8"))["outcome"] == "REJECTED"
    assert not (repo / marker).exists()


def test_workflow_skill_requires_guarded_handoffs_and_states_boundaries():
    skill = WORKFLOW_SKILL_PATH.read_text(encoding="utf-8")
    for operation in ("prepare", "check-handoff", "run"):
        assert f"handoff_guard.py {operation}" in skill
    for boundary in (
        "receipt",
        "append-only event log",
        "does not inspect dirty status",
        "explicit interpreter",
        ".cmd",
        ".bat",
        "observations do not imply semantic classification",
        "base SHA names an ancestor commit",
        "prior receipt's manifest digest",
    ):
        assert boundary in skill
