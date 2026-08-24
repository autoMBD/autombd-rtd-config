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
# File:        test_agent_workflow_transition.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-22
# Version:     0.1.0
# Description: Owner acceptance for deterministic P1 workflow transitions.
# =================================================================================

from __future__ import annotations

from copy import deepcopy
import builtins
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "agent-discipline" / "skills" / "agent-workflow"
SCRIPTS = SKILL / "scripts"
TRANSITION_PATH = SCRIPTS / "workflow_transition.py"
GATE_PATH = SCRIPTS / "workflow_gate.py"
EVENT_SCHEMA_PATH = SKILL / "workflow-transition-schema.json"
CONTRACT_PATH = ROOT / "agent-discipline" / "workflow-contract.json"
CONTRACT_BLOB = "b747065ac2fafa03d35d7a94b39d52d70f1de416"
EVENT_TYPES = (
    "TEST_APPROVED",
    "CANDIDATE_BUILT",
    "TESTER_PASSED",
    "REVIEWER_ACCEPTED",
    "DRAFT_PR_READY",
    "FINAL_HUMAN_APPROVED",
    "F0_TEST_CONTRACT_INVALID",
    "F1_PRODUCTION_FAILURE",
)
PAYLOAD_FIELDS = {
    "TEST_APPROVED": [
        "test_sha", "human_review_1", "reference_seam_passed",
        "vertical_slice_passed",
    ],
    "CANDIDATE_BUILT": ["implementation_sha", "candidate"],
    "TESTER_PASSED": ["tester"],
    "REVIEWER_ACCEPTED": ["reviewer"],
    "DRAFT_PR_READY": ["draft_pr"],
    "FINAL_HUMAN_APPROVED": ["final_human_review"],
    "F0_TEST_CONTRACT_INVALID": [
        "test_sha", "root_cause_digest", "finding",
    ],
    "F1_PRODUCTION_FAILURE": [
        "candidate_sha", "failure_digest", "finding",
    ],
}
REJECTION_CODES = [
    "USAGE_ERROR",
    "MALFORMED_INPUT",
    "MALFORMED_EVENT",
    "UNKNOWN_EVENT",
    "INVALID_RECORD",
    "STALE_EVENT",
    "DUPLICATE_EVENT",
    "OUT_OF_ORDER_EVENT",
    "ILLEGAL_TRANSITION",
    "MISSING_EVIDENCE",
    "OUTPUT_INVALID",
    "INTERNAL_ERROR",
]
SHA = {name: str(index) * 40 for index, name in enumerate(
    ("base", "old_test", "old_impl", "test", "impl", "candidate"), start=1
)}


def _load(path: Path, name: str):
    if not path.is_file():
        pytest.fail(f"required production module is missing: {path.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def transition_module():
    return _load(TRANSITION_PATH, "owner_workflow_transition")


@pytest.fixture(scope="module")
def gate_module():
    return _load(GATE_PATH, "owner_workflow_gate")


@pytest.fixture
def contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def event_schema_path():
    assert EVENT_SCHEMA_PATH.is_file(), (
        "the Skill must contain workflow-transition-schema.json as a file"
    )
    matches = sorted(SKILL.glob("workflow-transition*.json"))
    assert matches == [EVENT_SCHEMA_PATH], (
        "the Skill must not contain additional workflow-transition*.json siblings"
    )
    return EVENT_SCHEMA_PATH


@pytest.fixture
def event_schema(event_schema_path):
    return json.loads(event_schema_path.read_text(encoding="utf-8"))


def _record() -> dict[str, object]:
    return {
        "contract": {"version": 1, "blob_sha": CONTRACT_BLOB},
        "issue": {
            "repository": "https://synthetic.example/controls/workflow-fixture",
            "number": 314,
            "title": "Exercise an arbitrary governed task",
        },
        "classification": {
            "issue_class": "W",
            "impact_flags": ["test-contract", "agent-runtime"],
            "route": [
                "scope", "preflight", "ground", "author_test",
                "human_review_1", "implement", "candidate", "tester",
                "reviewer", "draft_pr", "human_review_2", "complete",
            ],
        },
        "checkpoint": "scoped",
        "execution_status": "active",
        "preflight": {
            "permissions": [{
                "name": "synthetic-write", "status": "available",
                "evidence": "isolated fixture is writable",
            }],
            "dependencies": [{
                "name": "synthetic-contract", "status": "available",
                "evidence": "canonical contract is present",
            }],
            "tools": [{
                "name": "synthetic-runner", "status": "available",
                "evidence": "runner probe passed",
            }],
            "result": "available",
        },
        "authority": {
            "base_sha": SHA["base"],
            "test_sha": SHA["old_test"],
            "implementation_sha": SHA["old_impl"],
            "authorized_reviewer": "synthetic-reviewer",
        },
        "human_review_1": None,
        "candidate": None,
        "tester": None,
        "reviewer": None,
        "findings": [],
        "draft_pr": None,
        "final_human_review": None,
        "attempt": {"candidate_attempt": 1},
        "blocker": None,
        "bootstrap_stage": "P0",
    }


def _canonical_id(event_type: str, payload: dict[str, object]) -> str:
    raw = json.dumps(
        {"type": event_type, "payload": payload},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _event(event_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": _canonical_id(event_type, payload),
        "type": event_type,
        "payload": payload,
    }


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _reordered(value):
    if isinstance(value, dict): return {key: _reordered(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list): return [_reordered(item) for item in value]
    return value


def _finding(kind: str, identity: str, digest: str, disposition: str):
    return {
        "id": f"{kind}:{identity}:{digest}",
        "source": "tester",
        "class": kind,
        "requirement_id": "P0-07",
        "evidence": f"stable evidence {digest[:12]}",
        "observed": "synthetic observed result",
        "expected": "synthetic expected result",
        "freeze_viability": None,
        "disposition": disposition,
    }


def _payloads():
    review = {
        "actor": "synthetic-reviewer",
        "comment_url": (
            "https://synthetic.example/controls/workflow-fixture/issues/314"
            "#issuecomment-2718"
        ),
        "test_sha": SHA["test"],
        "command": f"/approve-test {SHA['test']}",
        "edited": False,
        "deleted": False,
    }
    candidate = {
        "sha": SHA["candidate"],
        "parent_test_sha": SHA["test"],
        "parent_implementation_sha": SHA["impl"],
    }
    return [
        ("TEST_APPROVED", {
            "test_sha": SHA["test"], "human_review_1": review,
            "reference_seam_passed": True, "vertical_slice_passed": True,
        }),
        ("CANDIDATE_BUILT", {
            "implementation_sha": SHA["impl"], "candidate": candidate,
        }),
        ("TESTER_PASSED", {"tester": {
            "candidate_sha": SHA["candidate"], "verdict": "PASS",
            "evidence": "owner gate passed on the exact candidate",
        }}),
        ("REVIEWER_ACCEPTED", {"reviewer": {
            "candidate_sha": SHA["candidate"], "verdict": "PASS",
            "evidence": "independent non-test review accepted",
        }}),
        ("DRAFT_PR_READY", {"draft_pr": {
            "url": "https://synthetic.example/controls/workflow-fixture/pull/1618",
            "candidate_sha": SHA["candidate"], "is_draft": True,
        }}),
        ("FINAL_HUMAN_APPROVED", {"final_human_review": {
            "actor": "synthetic-reviewer",
            "comment_url": (
                "https://synthetic.example/controls/workflow-fixture/pull/1618"
                "#issuecomment-5772"
            ),
            "candidate_sha": SHA["candidate"], "decision": "approved",
        }}),
    ]


def _apply(module, record, event, contract, schema, blob=CONTRACT_BLOB):
    return module.transition_workflow(
        record, event, contract=contract, contract_blob_sha=blob,
        event_schema=schema,
    )


def _reject(module, code, record, event, contract, schema, blob=CONTRACT_BLOB):
    with pytest.raises(module.WorkflowTransitionError) as caught:
        _apply(module, record, event, contract, schema, blob)
    assert caught.value.code == code
    return caught.value


def _candidate_record(module, contract, schema, *, attempt=1):
    record = _record()
    for event_type, payload in _payloads()[:2]:
        record = _apply(module, record, _event(event_type, payload), contract, schema)
    record["attempt"]["candidate_attempt"] = attempt
    return record


def _history(module, contract, schema, count):
    record = _record()
    for event_type, payload in _payloads()[:count]:
        record = _apply(module, record, _event(event_type, payload), contract, schema)
    return record


def _set(value, path, replacement):
    target = value
    for name in path[:-1]:
        target = target[name]
    target[path[-1]] = replacement


def test_public_api_is_pure_deterministic_and_schema_bound(
    transition_module, gate_module, contract, event_schema, monkeypatch, tmp_path,
):
    assert str(inspect.signature(transition_module.canonical_event_id)) == "(event_type, payload)"
    assert str(inspect.signature(transition_module.transition_workflow)) == "(record, event, *, contract, contract_blob_sha, event_schema)"
    assert str(inspect.signature(gate_module.validate_record_in_memory)) == "(record, *, contract, contract_blob_sha)"
    assert set(event_schema) == {"schema_version", "contract_blob_sha", "event_envelope_fields", "event_types", "payload_fields", "rejection_codes"}
    assert event_schema["schema_version"] == 1
    assert event_schema["contract_blob_sha"] == CONTRACT_BLOB
    assert event_schema["event_envelope_fields"] == ["schema_version", "event_id", "type", "payload"]
    assert event_schema["event_types"] == list(EVENT_TYPES)
    assert event_schema["payload_fields"] == PAYLOAD_FIELDS
    assert event_schema["rejection_codes"] == REJECTION_CODES
    sample = _payloads()[0]
    assert transition_module.canonical_event_id(*sample) == _canonical_id(*sample)
    record, event = _record(), _event(*sample)
    record_before, event_before, contract_before, schema_before = map(deepcopy, (record, event, contract, event_schema))
    monkeypatch.chdir(tmp_path)
    first = _apply(transition_module, record, event, contract, event_schema)
    other_cwd = tmp_path / "other"; other_cwd.mkdir(); monkeypatch.chdir(other_cwd)
    second = _apply(transition_module, record, event, contract, event_schema)
    assert first == second
    assert (record, event, contract, event_schema) == (record_before, event_before, contract_before, schema_before)
    assert list(tmp_path.iterdir()) == [other_cwd] and list(other_cwd.iterdir()) == []
    reordered = _reordered(event)
    reordered_record = _apply(
        transition_module, record, reordered, contract, event_schema
    )
    assert reordered_record == first
    for next_record in (first, second, reordered_record):
        gate_module.validate_record_in_memory(
            next_record,
            contract=contract,
            contract_blob_sha=CONTRACT_BLOB,
        )
    wrong_schema = deepcopy(event_schema); wrong_schema["contract_blob_sha"] = "f" * 40
    _reject(transition_module, "MALFORMED_EVENT", record, event, contract, wrong_schema)
    _reject(transition_module, "MALFORMED_EVENT", record, event, contract, event_schema, "f" * 40)
    altered_contract = deepcopy(contract); altered_contract["checkpoints"] = contract["checkpoints"][:-1]
    _reject(transition_module, "MALFORMED_EVENT", record, event, altered_contract, event_schema)

    def fail_read(*_args, **_kwargs):
        raise AssertionError("pure transition attempted an external read")
    with monkeypatch.context() as guard:
        for owner, name in ((builtins, "open"), (Path, "read_text"), (Path, "read_bytes"), (Path, "cwd"), (os, "getenv"), (os, "getcwd"), (time, "time"), (subprocess, "run")):
            guard.setattr(owner, name, fail_read)
        assert _apply(transition_module, record, event, contract, event_schema) == first


def test_six_adjacent_checkpoint_events_preserve_lineage_and_add_exact_evidence(
    transition_module, gate_module, contract, event_schema,
):
    record = _record()
    stable = {field: deepcopy(record[field]) for field in ("contract", "issue", "classification", "preflight", "bootstrap_stage")}
    expected_authority = deepcopy(record["authority"])
    edges = zip(_payloads(), (
        ("test_approved", "human_review_1"),
        ("candidate_built", "candidate"), ("tester_passed", "tester"),
        ("reviewer_accepted", "reviewer"), ("draft_pr_ready", "draft_pr"),
        ("complete", "final_human_review"),
    ), strict=True)
    accumulated = {}
    for (event_type, payload), (checkpoint, evidence_field) in edges:
        before = deepcopy(record)
        record = _apply(transition_module, record, _event(event_type, payload), contract, event_schema)
        if event_type == "TEST_APPROVED": expected_authority["test_sha"] = payload["test_sha"]
        if event_type == "CANDIDATE_BUILT": expected_authority["implementation_sha"] = payload["implementation_sha"]
        accumulated[evidence_field] = deepcopy(payload[evidence_field])
        expected_evidence = payload[evidence_field]
        assert record["checkpoint"] == checkpoint
        assert record[evidence_field] == expected_evidence
        assert _bytes({field: record[field] for field in accumulated}) == _bytes(accumulated)
        assert record["findings"] == []
        assert record["attempt"] == {"candidate_attempt": 1}
        assert record["execution_status"] == "active"
        assert record["authority"]["base_sha"] == before["authority"]["base_sha"]
        assert {field: record[field] for field in stable} == stable and record["authority"] == expected_authority
        gate_module.validate_record_in_memory(record, contract=contract, contract_blob_sha=CONTRACT_BLOB)
        snapshot = deepcopy(record)
        _reject(transition_module, "DUPLICATE_EVENT", record, _event(event_type, payload), contract, event_schema)
        assert record == snapshot
    assert record["authority"]["test_sha"] == SHA["test"]
    assert record["authority"]["implementation_sha"] == SHA["impl"]
    assert record["candidate"] == _payloads()[1][1]["candidate"]


def test_bindings_and_rejections_use_frozen_precedence_codes(
    transition_module, contract, event_schema,
):
    test_type, test_payload = _payloads()[0]
    invalid_record = _record()
    invalid_record["attempt"]["candidate_attempt"] = 4

    malformed = _event("NOT_A_REAL_EVENT", {})
    malformed["extra"] = "closed"
    _reject(transition_module, "MALFORMED_EVENT", invalid_record, malformed, contract, event_schema)
    wrong_version = _event(test_type, test_payload); wrong_version["schema_version"] = 2
    _reject(transition_module, "MALFORMED_EVENT", _record(), wrong_version, contract, event_schema)
    for invalid_event_id in ("f" * 12, "F" * 64):
        malformed_id = _event(test_type, test_payload); malformed_id["event_id"] = invalid_event_id
        _reject(transition_module, "MALFORMED_EVENT", _record(), malformed_id, contract, event_schema)
    extra_payload = deepcopy(test_payload)
    extra_payload["uncontracted"] = True
    _reject(transition_module, "MALFORMED_EVENT", _record(), _event(test_type, extra_payload), contract, event_schema)
    unknown = _event("NOT_A_REAL_EVENT", {})
    _reject(transition_module, "UNKNOWN_EVENT", invalid_record, unknown, contract, event_schema)
    _reject(transition_module, "INVALID_RECORD", invalid_record, _event(test_type, test_payload), contract, event_schema)
    for eligibility, replacement in (("reference_seam_passed", False), ("vertical_slice_passed", False), ("reference_seam_passed", 1), ("vertical_slice_passed", "true")):
        ineligible = deepcopy(test_payload)
        ineligible[eligibility] = replacement
        _reject(
            transition_module, "MISSING_EVIDENCE", _record(),
            _event(test_type, ineligible), contract, event_schema,
        )

    binding_cases = [
        (0, ("test_sha",), SHA["old_test"], "STALE_EVENT"),
        (0, ("human_review_1", "actor"), "intruder", "STALE_EVENT"),
        (0, ("human_review_1", "command"), "/approve-test wrong", "STALE_EVENT"),
        (0, ("human_review_1", "test_sha"), SHA["old_test"], "STALE_EVENT"),
        (0, ("human_review_1", "edited"), True, "MISSING_EVIDENCE"),
        (0, ("human_review_1", "deleted"), True, "MISSING_EVIDENCE"),
        (0, ("human_review_1", "comment_url"), "https://synthetic.example/issues/314", "MISSING_EVIDENCE"),
        (1, ("implementation_sha",), SHA["old_impl"], "STALE_EVENT"),
        (1, ("candidate", "sha"), "9" * 12, "MISSING_EVIDENCE"),
        (1, ("candidate", "sha"), "A" * 40, "MISSING_EVIDENCE"),
        (1, ("candidate", "parent_test_sha"), SHA["old_test"], "STALE_EVENT"),
        (1, ("candidate", "parent_implementation_sha"), SHA["old_impl"], "STALE_EVENT"),
        (2, ("tester", "candidate_sha"), SHA["old_impl"], "STALE_EVENT"),
        (2, ("tester", "verdict"), "FAIL", "MISSING_EVIDENCE"),
        (3, ("reviewer", "candidate_sha"), SHA["old_impl"], "STALE_EVENT"),
        (3, ("reviewer", "verdict"), "FAIL", "MISSING_EVIDENCE"),
        (4, ("draft_pr", "candidate_sha"), SHA["old_impl"], "STALE_EVENT"),
        (4, ("draft_pr", "is_draft"), False, "MISSING_EVIDENCE"),
        (5, ("final_human_review", "candidate_sha"), SHA["old_impl"], "STALE_EVENT"),
        (5, ("final_human_review", "actor"), "intruder", "STALE_EVENT"),
        (5, ("final_human_review", "decision"), "rejected", "MISSING_EVIDENCE"),
        (5, ("final_human_review", "comment_url"), "https://synthetic.example/pull/1", "MISSING_EVIDENCE"),
    ]
    for edge, path, replacement, code in binding_cases:
        event_type, payload = deepcopy(_payloads()[edge])
        _set(payload, path, replacement)
        _reject(transition_module, code, _history(transition_module, contract, event_schema, edge), _event(event_type, payload), contract, event_schema)
    for edge, invalid_sha, code in ((0, SHA["old_test"], "STALE_EVENT"), (1, SHA["old_impl"], "STALE_EVENT"), (0, "4" * 12, "MISSING_EVIDENCE"), (1, "A" * 40, "MISSING_EVIDENCE")):
        event_type, payload = deepcopy(_payloads()[edge])
        if edge == 0:
            payload["test_sha"] = payload["human_review_1"]["test_sha"] = invalid_sha; payload["human_review_1"]["command"] = f"/approve-test {invalid_sha}"
        else:
            payload["implementation_sha"] = payload["candidate"]["parent_implementation_sha"] = invalid_sha
        _reject(transition_module, code, _history(transition_module, contract, event_schema, edge), _event(event_type, payload), contract, event_schema)

    approved = _apply(
        transition_module, _record(), _event(test_type, test_payload),
        contract, event_schema,
    )
    stale_payload = deepcopy(_payloads()[1][1])
    stale_payload["candidate"]["parent_test_sha"] = SHA["old_test"]
    _reject(
        transition_module, "STALE_EVENT", approved,
        _event("CANDIDATE_BUILT", stale_payload), contract, event_schema,
    )
    replay_snapshot = deepcopy(approved)
    _reject(
        transition_module, "DUPLICATE_EVENT", approved,
        _event(test_type, test_payload), contract, event_schema,
    )
    assert approved == replay_snapshot
    early_candidate = deepcopy(_payloads()[1][1])
    early_candidate["candidate"].update({"parent_test_sha": SHA["old_test"], "parent_implementation_sha": ""}); early_candidate["implementation_sha"] = ""
    _reject(
        transition_module, "OUT_OF_ORDER_EVENT", _record(),
        _event("CANDIDATE_BUILT", early_candidate), contract, event_schema,
    )
    stopped = deepcopy(approved)
    stopped["execution_status"] = "stopped"
    stopped["blocker"] = {
        "kind": "synthetic-stop", "reason": "explicit stop",
        "evidence": "stable stop evidence",
    }
    _reject(
        transition_module, "ILLEGAL_TRANSITION", stopped,
        _event(*_payloads()[1]), contract, event_schema,
    )
    missing = deepcopy(_payloads()[1][1])
    missing["implementation_sha"] = ""
    missing["candidate"]["parent_implementation_sha"] = ""
    _reject(
        transition_module, "MISSING_EVIDENCE", approved,
        _event("CANDIDATE_BUILT", missing), contract, event_schema,
    )

    bad_id = _event(test_type, test_payload)
    bad_id["event_id"] = "f" * 64
    _reject(transition_module, "INVALID_RECORD", invalid_record, bad_id, contract, event_schema)
    _reject(transition_module, "STALE_EVENT", _record(), bad_id, contract, event_schema)
    _reject(transition_module, "STALE_EVENT", approved, bad_id, contract, event_schema)


def test_f0_first_root_rewinds_without_attempt_and_second_distinct_root_stops(
    transition_module, contract, event_schema,
):
    digest_1 = hashlib.sha256(b"synthetic harness root one").hexdigest()
    for source_count in range(6):
        source = _history(transition_module, contract, event_schema, source_count)
        test_sha = source["authority"]["test_sha"]
        finding = _finding("F0", test_sha, digest_1, "BLOCK")
        first = _apply(transition_module, source, _event("F0_TEST_CONTRACT_INVALID", {"test_sha": test_sha, "root_cause_digest": digest_1, "finding": finding}), contract, event_schema)
        assert (first["checkpoint"], first["execution_status"], first["attempt"]) == ("scoped", "active", source["attempt"])
        assert first["findings"] == [finding]

    candidate = _candidate_record(transition_module, contract, event_schema)
    finding_1 = _finding("F0", SHA["test"], digest_1, "BLOCK")
    event_1 = _event("F0_TEST_CONTRACT_INVALID", {"test_sha": SHA["test"], "root_cause_digest": digest_1, "finding": finding_1})
    first = _apply(transition_module, candidate, event_1, contract, event_schema)
    assert (first["checkpoint"], first["execution_status"], first["attempt"], first["blocker"]) == ("scoped", "active", {"candidate_attempt": 1}, None)
    assert first["authority"] == candidate["authority"] and first["findings"] == [finding_1]
    assert all(first[field] is None for field in ("human_review_1", "candidate", "tester", "reviewer", "draft_pr", "final_human_review"))
    snapshot = deepcopy(first)
    _reject(transition_module, "DUPLICATE_EVENT", first, event_1, contract, event_schema)
    assert first == snapshot

    digest_2 = hashlib.sha256(b"synthetic fixture root two").hexdigest()
    finding_2 = _finding("F0", SHA["test"], digest_2, "STOP")
    second = _apply(transition_module, first, _event("F0_TEST_CONTRACT_INVALID", {"test_sha": SHA["test"], "root_cause_digest": digest_2, "finding": finding_2}), contract, event_schema)
    assert (second["checkpoint"], second["execution_status"], second["attempt"]) == ("scoped", "stopped", {"candidate_attempt": 1})
    assert second["findings"] == [finding_1, finding_2]
    assert second["blocker"]["kind"] == "architecture-review-required"
    wrong_first = deepcopy(event_1["payload"]); wrong_first["finding"]["disposition"] = "STOP"
    _reject(transition_module, "MISSING_EVIDENCE", candidate, _event("F0_TEST_CONTRACT_INVALID", wrong_first), contract, event_schema)
    wrong_second = deepcopy(finding_2); wrong_second["disposition"] = "BLOCK"
    _reject(transition_module, "MISSING_EVIDENCE", first, _event("F0_TEST_CONTRACT_INVALID", {"test_sha": SHA["test"], "root_cause_digest": digest_2, "finding": wrong_second}), contract, event_schema)
    wrong_class = deepcopy(event_1["payload"]); wrong_class["finding"]["class"] = "F1"
    _reject(transition_module, "MISSING_EVIDENCE", candidate, _event("F0_TEST_CONTRACT_INVALID", wrong_class), contract, event_schema)
    _reject(transition_module, "ILLEGAL_TRANSITION", _history(transition_module, contract, event_schema, 6), event_1, contract, event_schema)

    for path, replacement in [
        (("test_sha",), SHA["old_test"]),
        (("root_cause_digest",), digest_2),
        (("finding", "id"), f"F0:{SHA['test']}:{'f' * 64}"),
    ]:
        payload = deepcopy(event_1["payload"]); _set(payload, path, replacement)
        _reject(transition_module, "STALE_EVENT", candidate, _event("F0_TEST_CONTRACT_INVALID", payload), contract, event_schema)

    replacement_sha = "7" * 40
    replacement = deepcopy(_payloads()[0][1])
    replacement["test_sha"] = replacement_sha
    replacement["human_review_1"].update({"test_sha": replacement_sha, "command": f"/approve-test {replacement_sha}"})
    reset = _apply(transition_module, first, _event("TEST_APPROVED", replacement), contract, event_schema)
    digest_3 = hashlib.sha256(b"replacement revision root").hexdigest()
    finding_3 = _finding("F0", replacement_sha, digest_3, "BLOCK")
    reset_first = _apply(transition_module, reset, _event("F0_TEST_CONTRACT_INVALID", {"test_sha": replacement_sha, "root_cause_digest": digest_3, "finding": finding_3}), contract, event_schema)
    assert reset_first["execution_status"] == "active" and reset_first["attempt"] == first["attempt"]
    assert _bytes(reset_first["findings"]) == _bytes([finding_1, finding_3])
    stale_f0 = {"test_sha": SHA["old_test"], "root_cause_digest": digest_1, "finding": _finding("F0", SHA["old_test"], digest_1, "BLOCK")}
    _reject(transition_module, "STALE_EVENT", candidate, _event("F0_TEST_CONTRACT_INVALID", stale_f0), contract, event_schema)
    for malformed_digest in ("f" * 12, "F" * 64):
        malformed_f0 = {"test_sha": SHA["test"], "root_cause_digest": malformed_digest, "finding": _finding("F0", SHA["test"], malformed_digest, "BLOCK")}
        _reject(transition_module, "MISSING_EVIDENCE", candidate, _event("F0_TEST_CONTRACT_INVALID", malformed_f0), contract, event_schema)


def test_f1_increments_once_then_budget_stop_never_creates_attempt_four(
    transition_module, contract, event_schema,
):
    digest = hashlib.sha256(b"synthetic production failure").hexdigest()
    finding = _finding("F1", SHA["candidate"], digest, "REWORK_CURRENT_STAGE")
    event = _event("F1_PRODUCTION_FAILURE", {"candidate_sha": SHA["candidate"], "failure_digest": digest, "finding": finding})
    for attempt, expected_attempt in ((1, 2), (2, 3)):
        candidate = _candidate_record(transition_module, contract, event_schema, attempt=attempt)
        rework = _apply(transition_module, candidate, event, contract, event_schema)
        assert (rework["checkpoint"], rework["attempt"], rework["human_review_1"]) == ("test_approved", {"candidate_attempt": expected_attempt}, candidate["human_review_1"])
    candidate = _candidate_record(transition_module, contract, event_schema)
    rework = _apply(transition_module, candidate, event, contract, event_schema)
    assert rework["human_review_1"] == candidate["human_review_1"]
    assert rework["authority"]["test_sha"] == candidate["authority"]["test_sha"]
    assert rework["authority"]["implementation_sha"] == candidate["authority"]["implementation_sha"]
    assert rework["findings"] == [finding]
    assert all(rework[field] is None for field in ("candidate", "tester", "reviewer", "draft_pr", "final_human_review"))
    _reject(transition_module, "DUPLICATE_EVENT", rework, event, contract, event_schema)
    assert rework["attempt"] == {"candidate_attempt": 2}

    last = _candidate_record(transition_module, contract, event_schema, attempt=3)
    exhausted = _apply(transition_module, last, event, contract, event_schema)
    assert exhausted["checkpoint"] == "candidate_built"
    assert exhausted["execution_status"] == "stopped"
    assert exhausted["attempt"] == {"candidate_attempt": 3}
    assert exhausted["candidate"] == last["candidate"]
    assert exhausted["findings"] == [finding]
    assert exhausted["blocker"]["kind"] == "candidate-attempt-budget-exhausted"

    for path, replacement in [
        (("candidate_sha",), SHA["old_impl"]),
        (("failure_digest",), "f" * 64),
        (("finding", "id"), f"F1:{SHA['candidate']}:{'f' * 64}"),
    ]:
        payload = deepcopy(event["payload"]); _set(payload, path, replacement)
        _reject(transition_module, "STALE_EVENT", candidate, _event("F1_PRODUCTION_FAILURE", payload), contract, event_schema)
    stale = {"candidate_sha": SHA["old_impl"], "failure_digest": digest, "finding": _finding("F1", SHA["old_impl"], digest, "REWORK_CURRENT_STAGE")}
    _reject(transition_module, "STALE_EVENT", candidate, _event("F1_PRODUCTION_FAILURE", stale), contract, event_schema)
    for bad_digest in ("f" * 12, "F" * 64):
        malformed = {"candidate_sha": SHA["candidate"], "failure_digest": bad_digest, "finding": _finding("F1", SHA["candidate"], bad_digest, "REWORK_CURRENT_STAGE")}
        _reject(transition_module, "MISSING_EVIDENCE", candidate, _event("F1_PRODUCTION_FAILURE", malformed), contract, event_schema)
    wrong = deepcopy(event["payload"]); wrong["finding"]["disposition"] = "BLOCK"
    _reject(transition_module, "MISSING_EVIDENCE", candidate, _event("F1_PRODUCTION_FAILURE", wrong), contract, event_schema)
    _reject(transition_module, "ILLEGAL_TRANSITION", _history(transition_module, contract, event_schema, 3), event, contract, event_schema)
    _reject(transition_module, "ILLEGAL_TRANSITION", _history(transition_module, contract, event_schema, 6), event, contract, event_schema)

    rebuilt_payload = deepcopy(_payloads()[1][1])
    rebuilt_payload["implementation_sha"] = "7" * 40
    rebuilt_payload["candidate"] = {"sha": "8" * 40, "parent_test_sha": SHA["test"], "parent_implementation_sha": "7" * 40}
    rebuilt = _apply(transition_module, rework, _event("CANDIDATE_BUILT", rebuilt_payload), contract, event_schema)
    assert rebuilt["authority"]["implementation_sha"] == "7" * 40
    assert rebuilt["candidate"] == rebuilt_payload["candidate"]
    assert _bytes(rebuilt["findings"]) == _bytes([finding])
    digest_2 = hashlib.sha256(b"second production failure").hexdigest()
    finding_2 = _finding("F1", "8" * 40, digest_2, "REWORK_CURRENT_STAGE")
    second = _apply(transition_module, rebuilt, _event("F1_PRODUCTION_FAILURE", {"candidate_sha": "8" * 40, "failure_digest": digest_2, "finding": finding_2}), contract, event_schema)
    assert _bytes(second["findings"]) == _bytes([finding, finding_2])


def _run_cli(schema_path: Path, value=None, *extra, raw=None, contract_path=CONTRACT_PATH):
    command = [
        sys.executable, "-B", str(TRANSITION_PATH), "--contract", str(contract_path),
        "--event-schema", str(schema_path), *extra,
    ]
    stdin = raw if isinstance(raw, bytes) else (raw if raw is not None else json.dumps(value, separators=(",", ":"))).encode()
    try:
        return subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as failure:
        pytest.fail(
            "workflow transition CLI exceeded its 10-second timeout; "
            f"command={command!r}; stdout={failure.stdout!r}; "
            f"stderr={failure.stderr!r}"
        )


def _json_error(result, exit_code, code):
    assert result.returncode == exit_code
    assert result.stdout == b""
    stderr = result.stderr.decode("utf-8")
    assert "Traceback" not in stderr
    value = json.loads(stderr)
    assert set(value) == {"ok", "error"} and value["ok"] is False
    assert set(value["error"]) == {"code", "message"}
    assert value["error"]["code"] == code
    assert value["error"]["message"]


def test_cli_is_a_complete_json_vertical_slice_with_exact_stream_classes(
    transition_module, contract, event_schema, event_schema_path, tmp_path,
):
    event = _event(*_payloads()[0])
    result = _run_cli(event_schema_path, {"record": _record(), "event": event})
    assert result.returncode == 0
    assert result.stderr == b""
    value = json.loads(result.stdout.decode("utf-8"))
    assert set(value) == {"ok", "record"} and value["ok"] is True
    assert value["record"] == _apply(
        transition_module, _record(), event, contract, event_schema
    )
    reordered_result = _run_cli(event_schema_path, {"event": event, "record": _record()})
    assert reordered_result.returncode == 0 and reordered_result.stderr == b""

    invalid = _record()
    invalid["attempt"]["candidate_attempt"] = 4
    approved = _apply(transition_module, _record(), event, contract, event_schema)
    extra_input = {"record": _record(), "event": event, "extra": True}
    extra_event = deepcopy(event); extra_event["extra"] = True
    missing_contract = tmp_path / "guaranteed-absent-contract.json"
    missing_schema = tmp_path / "guaranteed-absent-event-schema.json"
    assert missing_contract.is_absolute() and not missing_contract.exists()
    assert missing_schema.is_absolute() and not missing_schema.exists()
    cases = [
        (_run_cli(event_schema_path, raw=b"\xff"), 2, "MALFORMED_INPUT"),
        (_run_cli(event_schema_path, {"record": _record(), "event": event}, contract_path=missing_contract), 2, "MALFORMED_INPUT"),
        (_run_cli(missing_schema, {"record": _record(), "event": event}), 2, "MALFORMED_INPUT"),
        (_run_cli(event_schema_path, raw="{not-json"), 2, "MALFORMED_INPUT"),
        (_run_cli(event_schema_path, raw='{"record":{},"record":{},"event":{}}'), 2, "MALFORMED_INPUT"),
        (_run_cli(event_schema_path, raw='{"record":{"attempt":{"candidate_attempt":1,"candidate_attempt":1}},"event":{}}'), 2, "MALFORMED_INPUT"),
        (_run_cli(event_schema_path, extra_input), 2, "MALFORMED_INPUT"),
        (_run_cli(event_schema_path, {"record": _record(), "event": extra_event}), 2, "MALFORMED_EVENT"),
        (_run_cli(event_schema_path, {"record": invalid, "event": event}), 1, "INVALID_RECORD"),
        (_run_cli(event_schema_path, {"record": _record(), "event": _event("NOT_A_REAL_EVENT", {})}), 1, "UNKNOWN_EVENT"),
        (_run_cli(event_schema_path, {"record": approved, "event": event}), 1, "DUPLICATE_EVENT"),
        (_run_cli(event_schema_path, None, "--unexpected", raw=""), 2, "USAGE_ERROR"),
    ]
    for cli_result, exit_code, code in cases:
        _json_error(cli_result, exit_code, code)
