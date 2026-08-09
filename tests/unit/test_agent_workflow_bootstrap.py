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
# File:        test_agent_workflow_bootstrap.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-03
# Version:     0.1.0
# Description: Owner tests for the Agent workflow contract bootstrap at P0.
# =================================================================================

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)
CANONICAL_CONTRACT_BLOB_SHA = "b747065ac2fafa03d35d7a94b39d52d70f1de416"

ISSUE_CLASSES = ["M", "B", "W", "T", "D", "N", "I"]
IMPACT_FLAGS = [
    "public-behavior",
    "module-surface",
    "mex-write",
    "test-contract",
    "agent-runtime",
    "release-payload",
    "external-dependency",
    "safety-security",
    "docs-only",
]
STRICT_ROUTE = [
    "scope",
    "preflight",
    "ground",
    "author_test",
    "human_review_1",
    "implement",
    "candidate",
    "tester",
    "reviewer",
    "draft_pr",
    "human_review_2",
    "complete",
]
REQUIREMENT_IDS = [
    "P0-01",
    "P0-02",
    "P0-03",
    "P0-04",
    "P0-05",
    "P0-06",
    "P0-07",
    "P0-08",
    "P0-09",
    "P0-10",
    "P0-11",
    "P0-12",
    "P0-13",
    "P0-14",
    "P0-15",
    "P0-16",
    "P0-17",
    "P0-18",
]

BASE_SHA = "1" * 40
TEST_SHA = "2" * 40
IMPLEMENTATION_SHA = "3" * 40
CANDIDATE_SHA = "4" * 40
CLEARANCE_REPORT_KEYS = [
    "bootstrap_design_file_count",
    "bootstrap_design_reference_count",
    "bootstrap_governance_reference_count",
    "bootstrap_generated_or_payload_count",
    "bootstrap_commit_ancestor_count",
    "temporary_heading_count",
    "temporary_removal_marker_count",
    "bootstrap_debt_id_count",
    "bootstrap_debt_pointer_count",
    "open_bootstrap_debt_count",
]


def _joined(*fragments: str) -> str:
    return "".join(fragments)


def _git(
    repository_path: Path,
    *arguments: str,
    check: bool = True,
    text=True,
    input=None,
):
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_path,
        check=check,
        capture_output=True,
        text=text,
        input=input,
    )


def _load_gate():
    if not GATE_PATH.is_file():
        pytest.fail("workflow_gate.py is not implemented")

    spec = importlib.util.spec_from_file_location("workflow_gate", GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _contract_blob_sha(repository_path: Path = Path(".")) -> str:
    return _git(
        repository_path,
        "rev-parse",
        f"HEAD:{CONTRACT_PATH.as_posix()}",
    ).stdout.strip()


def _assert_accepted(callback, *, case: str) -> None:
    try:
        callback()
    except Exception as exc:  # pragma: no cover - exercised after gate implementation
        pytest.fail(
            f"{case}: unexpectedly rejected with {type(exc).__name__}: {exc}"
        )


def _rejection_failure(expected_error, callback, *, case: str) -> str | None:
    try:
        callback()
    except expected_error:
        return None
    except Exception as exc:  # pragma: no cover - exercised after gate implementation
        return (
            f"{case}: raised {type(exc).__name__}, expected "
            f"{expected_error.__name__}: {exc}"
        )
    return f"{case}: expected {expected_error.__name__}"


def _assert_rejected(expected_error, callback, *, case: str) -> None:
    failure = _rejection_failure(expected_error, callback, case=case)
    if failure is not None:
        pytest.fail(failure)


def _clearance_report(**nonzero_counts: int) -> dict[str, int]:
    report = {key: 0 for key in CLEARANCE_REPORT_KEYS}
    assert set(nonzero_counts).issubset(report)
    report.update(nonzero_counts)
    return report


def _clearance_rejection_failure(
    expected_error,
    callback,
    *,
    case: str,
    expected_report: dict[str, int],
) -> str | None:
    try:
        callback()
    except expected_error as exc:
        message_prefix = "bootstrap clearance failed: "
        message = str(exc)
        if not message.startswith(message_prefix):
            return f"{case}: rejected for a non-clearance reason: {message}"
        try:
            report = json.loads(message.removeprefix(message_prefix))
        except json.JSONDecodeError as parse_error:
            return f"{case}: clearance report is not JSON: {parse_error}"
        if list(report) != CLEARANCE_REPORT_KEYS:
            return f"{case}: clearance report keys are not canonical: {report}"
        if report != expected_report:
            return (
                f"{case}: clearance report {report} does not equal "
                f"{expected_report}"
            )
        return None
    except Exception as exc:  # pragma: no cover - exercised after gate implementation
        return (
            f"{case}: raised {type(exc).__name__}, expected "
            f"{expected_error.__name__}: {exc}"
        )
    return f"{case}: expected {expected_error.__name__}"


def _valid_candidate_record() -> dict[str, object]:
    return {
        "contract": {"version": 1, "blob_sha": _contract_blob_sha()},
        "issue": {
            "repository": "autoMBD/autombd-rtd-config",
            "number": 78,
            "title": "Bootstrap the P0 Agent workflow gate",
        },
        "classification": {
            "issue_class": "W",
            "impact_flags": [
                "test-contract",
                "agent-runtime",
                "release-payload",
            ],
            "route": STRICT_ROUTE.copy(),
        },
        "checkpoint": "candidate_built",
        "execution_status": "active",
        "preflight": {
            "permissions": [
                {
                    "name": "repository-write",
                    "status": "available",
                    "evidence": "workspace write permission confirmed",
                }
            ],
            "dependencies": [
                {
                    "name": "workflow-contract",
                    "status": "available",
                    "evidence": "contract file is available",
                }
            ],
            "tools": [
                {
                    "name": "pytest",
                    "status": "available",
                    "evidence": "pytest is available",
                }
            ],
            "result": "available",
        },
        "authority": {
            "base_sha": BASE_SHA,
            "test_sha": TEST_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
            "authorized_reviewer": "autoMBD",
        },
        "human_review_1": {
            "actor": "autoMBD",
            "comment_url": (
                "https://github.com/autoMBD/autombd-rtd-config/issues/78"
                "#issuecomment-1001"
            ),
            "test_sha": TEST_SHA,
            "command": f"/approve-test {TEST_SHA}",
            "edited": False,
            "deleted": False,
        },
        "candidate": {
            "sha": CANDIDATE_SHA,
            "parent_test_sha": TEST_SHA,
            "parent_implementation_sha": IMPLEMENTATION_SHA,
        },
        "tester": None,
        "reviewer": None,
        "findings": [],
        "draft_pr": None,
        "final_human_review": None,
        "attempt": {"candidate_attempt": 1},
        "blocker": None,
        "bootstrap_stage": "P0",
    }


def _valid_complete_record() -> dict[str, object]:
    record = _valid_candidate_record()
    record["checkpoint"] = "complete"
    record["tester"] = {
        "candidate_sha": CANDIDATE_SHA,
        "verdict": "PASS",
        "evidence": "all owner tests passed for the current candidate",
    }
    record["reviewer"] = {
        "candidate_sha": CANDIDATE_SHA,
        "verdict": "PASS",
        "evidence": "non-test acceptance review passed",
    }
    record["draft_pr"] = {
        "url": "https://github.com/autoMBD/autombd-rtd-config/pull/123",
        "candidate_sha": CANDIDATE_SHA,
        "is_draft": True,
    }
    record["final_human_review"] = {
        "actor": "autoMBD",
        "comment_url": (
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002"
        ),
        "candidate_sha": CANDIDATE_SHA,
        "decision": "approved",
    }
    return record


def test_contract_blob_identity_survives_checkout_line_ending_conversion(
    tmp_path,
):
    canonical_payload = _git(
        Path("."),
        "show",
        f"HEAD:{CONTRACT_PATH.as_posix()}",
        text=False,
    ).stdout
    assert _contract_blob_sha() == CANONICAL_CONTRACT_BLOB_SHA

    repository_path = tmp_path / "contract-checkout"
    repository_path.mkdir()
    _git(repository_path, "init")
    _git(repository_path, "config", "user.name", "P0 Owner Test")
    _git(
        repository_path,
        "config",
        "user.email",
        "p0-owner-test@example.invalid",
    )
    _git(repository_path, "config", "core.autocrlf", "false")
    checkout_contract = repository_path / CONTRACT_PATH
    checkout_contract.parent.mkdir(parents=True)
    checkout_contract.write_bytes(canonical_payload)
    _git(repository_path, "add", CONTRACT_PATH.as_posix())
    _git(repository_path, "commit", "-m", "canonical contract")
    assert _contract_blob_sha(repository_path) == CANONICAL_CONTRACT_BLOB_SHA

    _git(repository_path, "config", "core.autocrlf", "true")
    checkout_contract.unlink()
    _git(repository_path, "checkout", "--", CONTRACT_PATH.as_posix())
    assert b"\r\n" in checkout_contract.read_bytes()
    assert _contract_blob_sha(repository_path) == CANONICAL_CONTRACT_BLOB_SHA


def test_contract_freezes_exact_p0_vocabulary():
    contract = _load_contract()

    assert contract["issue_classes"] == ISSUE_CLASSES
    assert contract["impact_flags"] == IMPACT_FLAGS
    assert contract["strict_route"] == STRICT_ROUTE
    assert contract["requirement_ids"] == REQUIREMENT_IDS
    assert contract["candidate_attempt"] == {"minimum": 1, "maximum": 3}

    list_values = {
        key: value
        for key, value in contract.items()
        if isinstance(value, list)
    }
    list_values.update(
        {
            f"object_fields.{key}": value
            for key, value in contract["object_fields"].items()
        }
    )
    for name, values in list_values.items():
        assert len(values) == len(set(values)), f"duplicate value in {name}"


def test_contract_rejects_duplicate_vocabulary_values():
    gate = _load_gate()
    base_contract = _load_contract()
    gate.validate_contract(base_contract, contract_path=CONTRACT_PATH)

    for duplicate_path in (
        "issue_classes",
        "impact_flags",
        "requirement_ids",
        "record_fields",
    ):
        contract = deepcopy(base_contract)
        contract[duplicate_path].append(contract[duplicate_path][0])
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda contract=contract: gate.validate_contract(
                contract,
                contract_path=CONTRACT_PATH,
            ),
            case=f"duplicate {duplicate_path}",
        )


def test_classification_accepts_every_canonical_class():
    gate = _load_gate()
    for issue_class in ISSUE_CLASSES:
        record = _valid_candidate_record()
        record["classification"]["issue_class"] = issue_class
        _assert_accepted(
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"canonical issue class {issue_class}",
        )


def test_classification_accepts_each_canonical_flag():
    gate = _load_gate()
    for impact_flag in IMPACT_FLAGS:
        record = _valid_candidate_record()
        record["classification"]["impact_flags"] = [impact_flag]
        _assert_accepted(
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"canonical impact flag {impact_flag}",
        )


def test_classification_rejects_unknown_alias_duplicate_out_of_order_and_short_route():
    gate = _load_gate()
    mutations = [
        (
            "unknown class",
            lambda classification: classification.update(issue_class="X"),
        ),
        (
            "unknown flag alias",
            lambda classification: classification.update(
                impact_flags=["runtime-asset"]
            ),
        ),
        (
            "duplicate flags",
            lambda classification: classification.update(
                impact_flags=["agent-runtime", "agent-runtime"]
            ),
        ),
        (
            "out-of-order flags",
            lambda classification: classification.update(
                impact_flags=[
                    "release-payload",
                    "agent-runtime",
                    "test-contract",
                ]
            ),
        ),
        (
            "short route",
            lambda classification: classification.update(route=STRICT_ROUTE[:-1]),
        ),
    ]
    for case, mutation in mutations:
        record = _valid_candidate_record()
        mutation(record["classification"])
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )


def test_candidate_attempt_accepts_one_through_three_and_rejects_zero_and_four():
    gate = _load_gate()
    for candidate_attempt in (1, 2, 3):
        record = _valid_candidate_record()
        record["attempt"]["candidate_attempt"] = candidate_attempt
        _assert_accepted(
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"valid candidate attempt {candidate_attempt}",
        )

    for candidate_attempt in (0, 4):
        record = _valid_candidate_record()
        record["attempt"]["candidate_attempt"] = candidate_attempt
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"invalid candidate attempt {candidate_attempt}",
        )


def test_bootstrap_stage_requires_exact_p0_string():
    gate = _load_gate()
    valid_record = _valid_complete_record()
    _assert_accepted(
        lambda: gate.validate_record(
            valid_record,
            contract_path=CONTRACT_PATH,
        ),
        case="exact P0 bootstrap stage",
    )

    for invalid_stage in (0, 1, True, None, "p0", "P1"):
        record = _valid_complete_record()
        record["bootstrap_stage"] = invalid_stage
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"invalid bootstrap stage {invalid_stage!r}",
        )


def test_preflight_blocking_and_execution_status_are_consistent():
    gate = _load_gate()

    active_record = _valid_candidate_record()
    _assert_accepted(
        lambda: gate.validate_record(
            active_record,
            contract_path=CONTRACT_PATH,
        ),
        case="active record with available preflight items",
    )

    blocked_record = _valid_candidate_record()
    blocked_record["preflight"]["tools"][0]["status"] = "blocked"
    blocked_record["preflight"]["tools"][0]["evidence"] = (
        "pytest is unavailable"
    )
    blocked_record["preflight"]["result"] = "blocked"
    blocked_record["execution_status"] = "blocked"
    blocked_record["blocker"] = {
        "kind": "tool",
        "reason": "pytest is unavailable",
        "evidence": "preflight tool probe failed",
    }
    _assert_accepted(
        lambda: gate.validate_record(
            blocked_record,
            contract_path=CONTRACT_PATH,
        ),
        case="blocked tool with consistent status and blocker",
    )

    blocked_mutations = [
        (
            "blocked execution without blocker",
            lambda record: record.update(blocker=None),
        ),
        (
            "active execution with blocked preflight item",
            lambda record: record.update(execution_status="active"),
        ),
        (
            "available preflight with blocked preflight item",
            lambda record: record["preflight"].update(result="available"),
        ),
    ]
    for case, mutation in blocked_mutations:
        record = deepcopy(blocked_record)
        mutation(record)
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )

    active_with_blocker = _valid_candidate_record()
    active_with_blocker["blocker"] = {
        "kind": "human-decision",
        "reason": "an active record cannot retain a blocker",
        "evidence": "preflight is otherwise available and passed",
    }
    _assert_rejected(
        gate.WorkflowValidationError,
        lambda: gate.validate_record(
            active_with_blocker,
            contract_path=CONTRACT_PATH,
        ),
        case="active execution with non-null blocker",
    )

    stopped_record = _valid_candidate_record()
    stopped_record["execution_status"] = "stopped"
    stopped_record["blocker"] = {
        "kind": "human-decision",
        "reason": "the owner stopped execution",
        "evidence": "owner disposition is STOP",
    }
    _assert_accepted(
        lambda: gate.validate_record(
            stopped_record,
            contract_path=CONTRACT_PATH,
        ),
        case="stopped execution with blocker",
    )

    stopped_without_blocker = deepcopy(stopped_record)
    stopped_without_blocker["blocker"] = None
    _assert_rejected(
        gate.WorkflowValidationError,
        lambda: gate.validate_record(
            stopped_without_blocker,
            contract_path=CONTRACT_PATH,
        ),
        case="stopped execution without blocker",
    )


def test_role_permissions_preserve_read_write_and_decision_ownership():
    contract = _load_contract()
    expected_permissions = {
        "orchestrator": [
            "classify",
            "assign_disposition",
            "assemble_candidate",
            "escalate_human",
        ],
        "explorer": ["read", "report_facts"],
        "worker": [
            "read_approved_contract",
            "write_implementation",
            "write_generality_tests",
        ],
        "tester": [
            "write_owner_tests",
            "read_candidate",
            "run_gate",
            "report_verdict",
        ],
        "reviewer": [
            "read_candidate",
            "append_lesson",
            "report_findings",
        ],
        "human": [
            "approve_test",
            "supply_blocker_input",
            "review_pr",
            "merge",
        ],
    }
    permissions = contract["role_permissions"]

    assert permissions == expected_permissions
    assert permissions["explorer"] == ["read", "report_facts"]
    assert {
        "write_owner_tests",
        "assign_disposition",
        "assemble_candidate",
        "approve_test",
        "review_pr",
        "merge",
    }.isdisjoint(permissions["worker"])
    for permission in ("assign_disposition", "assemble_candidate"):
        assert [
            role
            for role, role_permissions in permissions.items()
            if permission in role_permissions
        ] == ["orchestrator"]
    for permission in ("approve_test", "review_pr", "merge"):
        assert [
            role
            for role, role_permissions in permissions.items()
            if permission in role_permissions
        ] == ["human"]

    gate = _load_gate()
    _assert_accepted(
        lambda: gate.validate_contract(
            contract,
            contract_path=CONTRACT_PATH,
        ),
        case="unmodified contract role permissions",
    )


def test_human_review_1_binds_exact_actor_sha_command_and_comment():
    gate = _load_gate()
    baseline = _valid_candidate_record()
    _assert_accepted(
        lambda: gate.validate_record(
            baseline,
            contract_path=CONTRACT_PATH,
        ),
        case="exact first human approval",
    )

    mutations = [
        (
            "wrong first-review actor",
            lambda review: review.update(actor="unauthorized-reviewer"),
        ),
        (
            "non-HTTPS first-review comment",
            lambda review: review.update(
                comment_url=(
                    "http://github.com/autoMBD/autombd-rtd-config/issues/78"
                    "#issuecomment-1001"
                )
            ),
        ),
        (
            "non-GitHub-issue first-review comment",
            lambda review: review.update(
                comment_url=(
                    "https://github.com/autoMBD/autombd-rtd-config/pull/78"
                    "#discussion_r1001"
                )
            ),
        ),
        (
            "first-review approval for stale test SHA",
            lambda review: review.update(test_sha="5" * 40),
        ),
        (
            "first-review command with extra text",
            lambda review: review.update(
                command=f"/approve-test {TEST_SHA} extra"
            ),
        ),
        (
            "first-review command for wrong SHA",
            lambda review: review.update(command=f"/approve-test {'5' * 40}"),
        ),
        (
            "edited first-review approval",
            lambda review: review.update(edited=True),
        ),
        (
            "deleted first-review approval",
            lambda review: review.update(deleted=True),
        ),
    ]
    for case, mutation in mutations:
        record = deepcopy(baseline)
        mutation(record["human_review_1"])
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )


def test_tester_precedes_reviewer_and_both_bind_current_candidate():
    gate = _load_gate()

    tester_passed = _valid_candidate_record()
    tester_passed["checkpoint"] = "tester_passed"
    tester_passed["tester"] = {
        "candidate_sha": CANDIDATE_SHA,
        "verdict": "PASS",
        "evidence": "all owner tests passed for the current candidate",
    }
    _assert_accepted(
        lambda: gate.validate_record(
            tester_passed,
            contract_path=CONTRACT_PATH,
        ),
        case="tester PASS for current candidate",
    )

    reviewer_accepted = deepcopy(tester_passed)
    reviewer_accepted["checkpoint"] = "reviewer_accepted"
    reviewer_accepted["reviewer"] = {
        "candidate_sha": CANDIDATE_SHA,
        "verdict": "PASS",
        "evidence": "non-test acceptance review passed",
    }
    _assert_accepted(
        lambda: gate.validate_record(
            reviewer_accepted,
            contract_path=CONTRACT_PATH,
        ),
        case="reviewer PASS after tester PASS for current candidate",
    )

    invalid_records = []

    reviewer_before_tester = _valid_candidate_record()
    reviewer_before_tester["reviewer"] = deepcopy(
        reviewer_accepted["reviewer"]
    )
    invalid_records.append(("reviewer before tester", reviewer_before_tester))

    tester_failed = deepcopy(tester_passed)
    tester_failed["tester"]["verdict"] = "FAIL"
    invalid_records.append(("tester FAIL at tester_passed", tester_failed))

    stale_tester = deepcopy(tester_passed)
    stale_tester["tester"]["candidate_sha"] = "5" * 40
    invalid_records.append(("tester PASS for stale candidate", stale_tester))

    stale_reviewer = deepcopy(reviewer_accepted)
    stale_reviewer["reviewer"]["candidate_sha"] = "5" * 40
    invalid_records.append(
        ("reviewer PASS for stale candidate", stale_reviewer)
    )

    reviewer_without_tester_pass = deepcopy(reviewer_accepted)
    reviewer_without_tester_pass["tester"]["verdict"] = "BLOCKED"
    invalid_records.append(
        (
            "reviewer accepted without tester PASS",
            reviewer_without_tester_pass,
        )
    )

    for reviewer_verdict in ("FAIL", "BLOCKED"):
        invalid_reviewer = deepcopy(reviewer_accepted)
        invalid_reviewer["reviewer"]["verdict"] = reviewer_verdict
        invalid_records.append(
            (
                f"reviewer_accepted with reviewer {reviewer_verdict}",
                invalid_reviewer,
            )
        )

    for case, record in invalid_records:
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )


def test_finding_class_rules_preserve_verdict_and_orchestrator_disposition():
    gate = _load_gate()
    contract = _load_contract()
    assert "verdict" not in contract["object_fields"]["finding"]

    f1_finding = {
        "id": "FINDING-001",
        "source": "tester",
        "class": "F1",
        "requirement_id": "P0-10",
        "evidence": "candidate evidence contradicts the frozen requirement",
        "observed": "the current stage does not satisfy the requirement",
        "expected": "the current stage satisfies the frozen requirement",
        "freeze_viability": None,
        "disposition": "REWORK_CURRENT_STAGE",
    }

    def record_with_finding(finding):
        record = _valid_candidate_record()
        record["findings"] = [deepcopy(finding)]
        return record

    f1_record = record_with_finding(f1_finding)
    role_verdicts = (f1_record["tester"], f1_record["reviewer"])
    _assert_accepted(
        lambda: gate.validate_record(
            f1_record,
            contract_path=CONTRACT_PATH,
        ),
        case="F1 reworks the current stage",
    )
    assert (f1_record["tester"], f1_record["reviewer"]) == role_verdicts

    required_field_mutations = [
        (
            "F1 missing requirement ID",
            lambda finding: finding.pop("requirement_id"),
        ),
        (
            "F1 unknown requirement ID",
            lambda finding: finding.update(requirement_id="P0-99"),
        ),
        ("F1 missing evidence", lambda finding: finding.pop("evidence")),
        ("F1 missing observed", lambda finding: finding.pop("observed")),
        ("F1 missing expected", lambda finding: finding.pop("expected")),
    ]
    for case, mutation in required_field_mutations:
        finding = deepcopy(f1_finding)
        mutation(finding)
        record = record_with_finding(finding)
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )

    f0_freeze = deepcopy(f1_finding)
    f0_freeze["class"] = "F0"
    f0_freeze["freeze_viability"] = {
        field: True for field in contract["object_fields"]["freeze_viability"]
    }
    f0_freeze["disposition"] = "FREEZE_FOR_NEXT_STAGE"
    record = record_with_finding(f0_freeze)
    _assert_rejected(
        gate.WorkflowValidationError,
        lambda: gate.validate_record(record, contract_path=CONTRACT_PATH),
        case="F0 cannot freeze for the next stage",
    )

    for disposition in ("BLOCK", "STOP"):
        f0_finding = deepcopy(f1_finding)
        f0_finding["class"] = "F0"
        f0_finding["disposition"] = disposition
        record = record_with_finding(f0_finding)
        _assert_accepted(
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"F0 with {disposition}",
        )

    f2_freeze = deepcopy(f1_finding)
    f2_freeze["class"] = "F2"
    f2_freeze["freeze_viability"] = {
        field: True for field in contract["object_fields"]["freeze_viability"]
    }
    f2_freeze["disposition"] = "FREEZE_FOR_NEXT_STAGE"
    record = record_with_finding(f2_freeze)
    _assert_accepted(
        lambda: gate.validate_record(record, contract_path=CONTRACT_PATH),
        case="F2 freezes only with all viability fields true",
    )

    for viability_field in contract["object_fields"]["freeze_viability"]:
        non_viable_finding = deepcopy(f2_freeze)
        non_viable_finding["freeze_viability"][viability_field] = False

        record = record_with_finding(non_viable_finding)
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"F2 freeze with false {viability_field}",
        )

        for disposition in ("BLOCK", "STOP"):
            blocked_finding = deepcopy(non_viable_finding)
            blocked_finding["disposition"] = disposition
            record = record_with_finding(blocked_finding)
            _assert_accepted(
                lambda record=record: gate.validate_record(
                    record,
                    contract_path=CONTRACT_PATH,
                ),
                case=(
                    f"F2 false {viability_field} with {disposition}"
                ),
            )

    for finding_class in ("F3", "F4"):
        deferred_finding = deepcopy(f1_finding)
        deferred_finding["class"] = finding_class
        deferred_finding["disposition"] = "DEFER_NON_BLOCKING"
        record = record_with_finding(deferred_finding)
        _assert_accepted(
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"{finding_class} deferred as non-blocking",
        )

        for disposition in (
            "FINAL_ACCEPT",
            "REWORK_CURRENT_STAGE",
            "FREEZE_FOR_NEXT_STAGE",
            "BLOCK",
            "STOP",
        ):
            invalid_finding = deepcopy(deferred_finding)
            invalid_finding["disposition"] = disposition
            record = record_with_finding(invalid_finding)
            _assert_rejected(
                gate.WorkflowValidationError,
                lambda record=record: gate.validate_record(
                    record,
                    contract_path=CONTRACT_PATH,
                ),
                case=f"{finding_class} with {disposition}",
            )

    for source in ("tester", "reviewer"):
        finding = deepcopy(f1_finding)
        finding["source"] = source
        record = record_with_finding(finding)
        _assert_accepted(
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"finding reported by {source}",
        )

    for source in ("orchestrator", "worker", "human"):
        finding = deepcopy(f1_finding)
        finding["source"] = source
        record = record_with_finding(finding)
        _assert_rejected(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=f"finding reported by unauthorized source {source}",
        )

    finding_with_verdict = deepcopy(f1_finding)
    finding_with_verdict["verdict"] = "PASS"
    record = record_with_finding(finding_with_verdict)
    _assert_rejected(
        gate.WorkflowValidationError,
        lambda: gate.validate_record(record, contract_path=CONTRACT_PATH),
        case="finding cannot store a role verdict",
    )


def test_draft_pr_and_final_human_review_bind_current_candidate():
    gate = _load_gate()

    draft_pr_ready = _valid_candidate_record()
    draft_pr_ready["checkpoint"] = "draft_pr_ready"
    draft_pr_ready["tester"] = {
        "candidate_sha": CANDIDATE_SHA,
        "verdict": "PASS",
        "evidence": "all owner tests passed for the current candidate",
    }
    draft_pr_ready["reviewer"] = {
        "candidate_sha": CANDIDATE_SHA,
        "verdict": "PASS",
        "evidence": "non-test acceptance review passed",
    }
    draft_pr_ready["draft_pr"] = {
        "url": "https://github.com/autoMBD/autombd-rtd-config/pull/123",
        "candidate_sha": CANDIDATE_SHA,
        "is_draft": True,
    }
    _assert_accepted(
        lambda: gate.validate_record(
            draft_pr_ready,
            contract_path=CONTRACT_PATH,
        ),
        case="draft PR for current accepted candidate",
    )

    complete = deepcopy(draft_pr_ready)
    complete["checkpoint"] = "complete"
    complete["final_human_review"] = {
        "actor": "autoMBD",
        "comment_url": (
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002"
        ),
        "candidate_sha": CANDIDATE_SHA,
        "decision": "approved",
    }
    synthetic_complete = deepcopy(complete)
    synthetic_complete["issue"]["repository"] = (
        "https://forge.example.test/DeltaTeam/control-plane"
    )
    synthetic_complete["human_review_1"]["comment_url"] = (
        "https://forge.example.test/DeltaTeam/control-plane/issues/78"
        "#issuecomment-3107"
    )
    synthetic_complete["draft_pr"]["url"] = (
        "https://forge.example.test/DeltaTeam/control-plane/pull/907"
    )
    synthetic_complete["final_human_review"]["comment_url"] = (
        "https://forge.example.test/DeltaTeam/control-plane/pull/907"
        "#issuecomment-880031"
    )
    synthetic_complete["final_human_review"]["actor"] = (
        "synthetic-change-council"
    )
    synthetic_complete["final_human_review"]["decision"] = (
        "recorded-after-independent-review"
    )
    _assert_accepted(
        lambda: gate.validate_record(
            synthetic_complete,
            contract_path=CONTRACT_PATH,
        ),
        case=(
            "final human approval dynamically bound to an independent "
            "synthetic repository"
        ),
    )

    _assert_accepted(
        lambda: gate.validate_record(
            complete,
            contract_path=CONTRACT_PATH,
        ),
        case="final human approval for current accepted candidate",
    )

    rejection_failures = []
    dynamic_repository_records = (
        ("canonical repository", complete),
        ("independent synthetic repository", synthetic_complete),
    )
    assert len(
        {
            record["issue"]["repository"]
            for _, record in dynamic_repository_records
        }
    ) == len(dynamic_repository_records)
    assert len(
        {
            record["final_human_review"]["comment_url"]
            for _, record in dynamic_repository_records
        }
    ) == len(dynamic_repository_records)

    dynamic_repository_identities = []
    for repository_case, baseline in dynamic_repository_records:
        canonical_url = baseline["final_human_review"]["comment_url"]
        locator, separator, fragment = canonical_url.rpartition("#")
        assert separator == "#"
        authority_end = locator.find("/", len("https://"))
        assert authority_end > len("https://")
        locator_parts = locator[authority_end + 1 :].split("/")
        assert len(locator_parts) == 4
        assert locator_parts[2] == "pull"
        fragment_kind, fragment_id = fragment.rsplit("-", 1)
        assert fragment_kind == "issuecomment"
        dynamic_repository_identities.append(
            (
                locator[len("https://") : authority_end],
                locator_parts[0],
                locator_parts[1],
                locator_parts[3],
                fragment_id,
            )
        )
        raw_noncanonical_locators = (
            (
                "trailing empty query delimiter",
                locator + "?#" + fragment,
            ),
            (
                "empty path parameter delimiter",
                locator + ";#" + fragment,
            ),
            (
                "empty port delimiter",
                locator[:authority_end]
                + ":"
                + locator[authority_end:]
                + "#"
                + fragment,
            ),
        )
        for locator_case, comment_url in raw_noncanonical_locators:
            record = deepcopy(baseline)
            record["final_human_review"]["comment_url"] = comment_url
            failure = _rejection_failure(
                gate.WorkflowValidationError,
                lambda record=record: gate.validate_record(
                    record,
                    contract_path=CONTRACT_PATH,
                ),
                case=f"{repository_case}: {locator_case}",
            )
            if failure is not None:
                rejection_failures.append(failure)

    for identity_index in range(5):
        assert len(
            {
                identity[identity_index]
                for identity in dynamic_repository_identities
            }
        ) == len(dynamic_repository_records)

    invalid_final_review_comment_urls = [
        (
            "final-review comment on a different repository host",
            "https://example.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment under a different repository owner",
            "https://github.com/not-autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment under a different repository name",
            "https://github.com/autoMBD/not-autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with userinfo",
            "https://reviewer@github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with explicit port",
            "https://github.com:443/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with query",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "?notification_referrer_id=1#issuecomment-2002",
        ),
        (
            "final-review comment URL with extra path",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123/files"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with trailing slash ambiguity",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123/"
            "#issuecomment-2002",
        ),
        (
            "issue comment used as final-review comment",
            "https://github.com/autoMBD/autombd-rtd-config/issues/123"
            "#issuecomment-2002",
        ),
        (
            "pull review path used as final-review comment",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123/reviews/2002"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL without fragment",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123",
        ),
        (
            "final-review comment URL with wrong fragment kind",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#pullrequestreview-2002",
        ),
        (
            "final-review comment URL with zero comment id",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-0",
        ),
        (
            "final-review comment URL with leading-zero comment id",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-02002",
        ),
        (
            "final-review comment URL with non-decimal comment id",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-not-a-number",
        ),
        (
            "final-review comment URL with zero pull request number",
            "https://github.com/autoMBD/autombd-rtd-config/pull/0"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with leading-zero pull request number",
            "https://github.com/autoMBD/autombd-rtd-config/pull/0123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with non-decimal pull request number",
            "https://github.com/autoMBD/autombd-rtd-config/pull/not-a-number"
            "#issuecomment-2002",
        ),
        (
            "non-HTTPS final-review comment URL",
            "http://github.com/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with malformed percent escape",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123%"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with raw control character",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123\x1f"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with raw C1 character",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123\x85"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with raw DEL character",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123\x7f"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with decoded control character",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123%1F"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with decoded C1 character",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123%C2%85"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with decoded DEL character",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123%7F"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with raw backslash",
            "https://github.com/autoMBD/autombd-rtd-config/pull\\123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with decoded backslash",
            "https://github.com/autoMBD/autombd-rtd-config/pull%5C123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with raw whitespace",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123 "
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with decoded whitespace",
            "https://github.com/autoMBD/autombd-rtd-config/pull/123%20"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with encoded host ambiguity",
            "https://github%2Ecom/autoMBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with encoded owner ambiguity",
            "https://github.com/auto%4DBD/autombd-rtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with encoded repository ambiguity",
            "https://github.com/autoMBD/autombd%2Drtd-config/pull/123"
            "#issuecomment-2002",
        ),
        (
            "final-review comment URL with encoded path ambiguity",
            "https://github.com/autoMBD/autombd-rtd-config/pull/%31%32%33"
            "#issuecomment-2002",
        ),
    ]
    for case, comment_url in invalid_final_review_comment_urls:
        record = deepcopy(complete)
        record["final_human_review"]["comment_url"] = comment_url
        failure = _rejection_failure(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )
        if failure is not None:
            rejection_failures.append(failure)

    mutations = [
        (
            "draft PR for stale candidate",
            draft_pr_ready,
            lambda record: record["draft_pr"].update(
                candidate_sha="5" * 40
            ),
        ),
        (
            "non-draft PR at draft checkpoint",
            draft_pr_ready,
            lambda record: record["draft_pr"].update(is_draft=False),
        ),
        (
            "non-HTTPS draft PR URL",
            draft_pr_ready,
            lambda record: record["draft_pr"].update(
                url="http://github.com/autoMBD/autombd-rtd-config/pull/123"
            ),
        ),
        (
            "final review for stale candidate",
            complete,
            lambda record: record["final_human_review"].update(
                candidate_sha="5" * 40
            ),
        ),
        (
            "empty final-review actor",
            complete,
            lambda record: record["final_human_review"].update(
                actor=""
            ),
        ),
        (
            "whitespace-only final-review actor",
            complete,
            lambda record: record["final_human_review"].update(
                actor=" \t\r\n"
            ),
        ),
        (
            "non-string final-review actor",
            complete,
            lambda record: record["final_human_review"].update(
                actor=7
            ),
        ),
        (
            "empty final-review decision",
            complete,
            lambda record: record["final_human_review"].update(
                decision=""
            ),
        ),
        (
            "whitespace-only final-review decision",
            complete,
            lambda record: record["final_human_review"].update(
                decision=" \t\r\n"
            ),
        ),
        (
            "non-string final-review decision",
            complete,
            lambda record: record["final_human_review"].update(
                decision={"value": "recorded"}
            ),
        ),
    ]
    for case, baseline, mutation in mutations:
        record = deepcopy(baseline)
        mutation(record)
        failure = _rejection_failure(
            gate.WorkflowValidationError,
            lambda record=record: gate.validate_record(
                record,
                contract_path=CONTRACT_PATH,
            ),
            case=case,
        )
        if failure is not None:
            rejection_failures.append(failure)

    assert not rejection_failures, (
        "record rejection gaps:\n" + "\n".join(rejection_failures)
    )


def test_lane_manifest_preflight_rejects_every_identity_or_requirement_mismatch():
    gate = _load_gate()
    contract = _load_contract()
    contract_blob_sha = _contract_blob_sha()
    assert contract["contract_version"] == 1

    test_manifest = {
        "contract_version": 1,
        "contract_blob_sha": contract_blob_sha,
        "base_sha": BASE_SHA,
        "lane_sha": TEST_SHA,
        "requirement_ids": REQUIREMENT_IDS.copy(),
    }
    implementation_manifest = {
        "contract_version": 1,
        "contract_blob_sha": contract_blob_sha,
        "base_sha": BASE_SHA,
        "lane_sha": IMPLEMENTATION_SHA,
        "requirement_ids": REQUIREMENT_IDS.copy(),
    }
    assert test_manifest["contract_blob_sha"] == _contract_blob_sha()
    assert implementation_manifest["contract_blob_sha"] == _contract_blob_sha()

    _assert_accepted(
        lambda: gate.validate_lane_manifests(
            test_manifest,
            implementation_manifest,
            contract_path=CONTRACT_PATH,
        ),
        case="matching closed lane manifests",
    )
    _assert_accepted(
        lambda: gate.validate_lane_manifests(
            implementation_manifest,
            test_manifest,
            contract_path=CONTRACT_PATH,
        ),
        case="matching closed lane manifests in symmetric argument order",
    )

    malformed_shared_base_test = deepcopy(test_manifest)
    malformed_shared_base_implementation = deepcopy(implementation_manifest)
    malformed_shared_base_test["base_sha"] = "not-a-sha"
    malformed_shared_base_implementation["base_sha"] = "not-a-sha"
    _assert_rejected(
        gate.WorkflowValidationError,
        lambda: gate.validate_lane_manifests(
            malformed_shared_base_test,
            malformed_shared_base_implementation,
            contract_path=CONTRACT_PATH,
        ),
        case="both lane manifests share the same malformed Base SHA",
    )

    mutations = [
        (
            "lane manifest contract version mismatch",
            lambda manifest, _other: manifest.update(contract_version=2),
        ),
        (
            "lane manifest contract blob mismatch",
            lambda manifest, _other: manifest.update(
                contract_blob_sha="5" * 40
            ),
        ),
        (
            "lane manifest Base SHA mismatch",
            lambda manifest, _other: manifest.update(base_sha="5" * 40),
        ),
        (
            "lane manifest malformed Base SHA",
            lambda manifest, _other: manifest.update(base_sha="not-a-sha"),
        ),
        (
            "lane manifest malformed lane SHA",
            lambda manifest, _other: manifest.update(lane_sha="not-a-sha"),
        ),
        (
            "lane manifests reuse one lane SHA",
            lambda manifest, other: manifest.update(
                lane_sha=other["lane_sha"]
            ),
        ),
        (
            "lane manifest requirement omission",
            lambda manifest, _other: manifest.update(
                requirement_ids=REQUIREMENT_IDS[:-1]
            ),
        ),
        (
            "lane manifest requirement reorder",
            lambda manifest, _other: manifest.update(
                requirement_ids=[
                    REQUIREMENT_IDS[1],
                    REQUIREMENT_IDS[0],
                    *REQUIREMENT_IDS[2:],
                ]
            ),
        ),
        (
            "lane manifest extra requirement",
            lambda manifest, _other: manifest.update(
                requirement_ids=[*REQUIREMENT_IDS, "P0-99"]
            ),
        ),
        (
            "lane manifest extra object field",
            lambda manifest, _other: manifest.update(
                unfrozen_metadata="extra"
            ),
        ),
    ]
    for case, mutation in mutations:
        for lane in ("Test", "Implementation"):
            mutated_test_manifest = deepcopy(test_manifest)
            mutated_implementation_manifest = deepcopy(
                implementation_manifest
            )
            if lane == "Test":
                target_manifest = mutated_test_manifest
                other_manifest = mutated_implementation_manifest
            else:
                target_manifest = mutated_implementation_manifest
                other_manifest = mutated_test_manifest
            mutation(target_manifest, other_manifest)
            _assert_rejected(
                gate.WorkflowValidationError,
                lambda test=mutated_test_manifest, implementation=(
                    mutated_implementation_manifest
                ): gate.validate_lane_manifests(
                    test,
                    implementation,
                    contract_path=CONTRACT_PATH,
                ),
                case=f"{case} on {lane} manifest",
            )


def test_skill_role_and_category_boundaries_use_single_contract_authority():
    runtime_files = [
        Path("AGENTS.md"),
        Path("agent-discipline/skills/agent-workflow/SKILL.md"),
        Path("agent-discipline/subagents/explorer.md"),
        Path("agent-discipline/subagents/worker.md"),
        Path("agent-discipline/subagents/tester.md"),
        Path("agent-discipline/subagents/reviewer.md"),
    ]
    authority_reference = "agent-discipline/workflow-contract.json"
    for runtime_file in runtime_files:
        assert runtime_file.is_file(), f"missing runtime file: {runtime_file}"
        content = runtime_file.read_text(encoding="utf-8")
        assert authority_reference in content, (
            f"{runtime_file} is not wired to the workflow contract authority"
        )
        assert not all(flag in content for flag in IMPACT_FLAGS), (
            f"{runtime_file} duplicates the complete impact-flag vocabulary"
        )
        assert not all(
            requirement_id in content for requirement_id in REQUIREMENT_IDS
        ), (
            f"{runtime_file} duplicates the complete requirement vocabulary"
        )

    forbidden_docs_tokens = (
        b"agent-discipline/",
        b"AGENTS.md",
        b".agents/skills/agent-workflow",
        b".codex/agents/",
        b".claude/skills/agent-workflow",
        b"workflow-contract.json",
        b"agent-workflow",
        b"contract_blob_sha",
        b"FREEZE_FOR_NEXT_STAGE",
    )
    review_archive = "review-archive-NOT-USED-NEVER-TOUCH!!!"
    active_docs = [
        path
        for path in Path("docs").rglob("*")
        if path.is_file() and review_archive not in path.parts
    ]

    def content_outside_subagent_prompt_regions(content):
        visible_lines = []
        prompt_heading_level = None
        prompt_table_column = None

        for line in content.splitlines():
            stripped = line.strip()
            heading_marker, separator, heading_title = stripped.partition(" ")
            heading_level = None
            if (
                separator
                and 1 <= len(heading_marker) <= 6
                and set(heading_marker) == {"#"}
            ):
                heading_level = len(heading_marker)
                heading_title = heading_title.rstrip("#").strip()

            if prompt_heading_level is not None:
                if heading_level is None or heading_level > prompt_heading_level:
                    continue
                prompt_heading_level = None

            if heading_level == 3 and heading_title == "Subagent Prompt":
                prompt_heading_level = heading_level
                continue

            table_cells = None
            if stripped.startswith("|") and stripped.endswith("|"):
                table_cells = [
                    cell.strip() for cell in stripped[1:-1].split("|")
                ]

            if table_cells is not None and "Subagent Prompt" in table_cells:
                prompt_table_column = table_cells.index("Subagent Prompt")
                visible_lines.append(line)
                continue

            if prompt_table_column is not None:
                if (
                    table_cells is not None
                    and len(table_cells) > prompt_table_column
                ):
                    table_cells[prompt_table_column] = ""
                    visible_lines.append("|" + "|".join(table_cells) + "|")
                    continue
                prompt_table_column = None

            visible_lines.append(line)

        return "\n".join(visible_lines).encode("utf-8")

    for docs_file in active_docs:
        content = content_outside_subagent_prompt_regions(
            docs_file.read_text(encoding="utf-8")
        )
        for forbidden_token in forbidden_docs_tokens:
            assert forbidden_token not in content, (
                f"{docs_file} crosses the development/agent-discipline boundary "
                f"with {forbidden_token.decode('ascii')}"
            )


def test_bootstrap_clearance_rejects_each_residual_fact(tmp_path):
    gate = _load_gate()
    temporary_marker_prefix = _joined("P0", "-", "BS", "-")
    residual_cases = (
        {
            "name": _joined("bootstrap-de", "sign-file"),
            "repository_files": {
                _joined("agent-discipline/agent-work", "flow-design.md"): (
                    "Retired synthetic design artifact.\n"
                )
            },
        },
        {
            "name": _joined("bootstrap-test-stra", "tegy-file"),
            "repository_files": {
                _joined(
                    "agent-discipline/agent-workflow-test-",
                    "strategy.md",
                ): (
                    "Retired synthetic test-strategy artifact.\n"
                )
            },
        },
        {
            "name": _joined("bootstrap-de", "sign-heading"),
            "repository_files": {
                "notes.md": _joined(
                    "# Agent Workflow Boot",
                    "strap Design\n",
                )
            },
        },
        {
            "name": _joined("bootstrap-test-stra", "tegy-heading"),
            "repository_files": {
                "notes.md": _joined(
                    "# Agent Workflow Bootstrap Test Stra",
                    "tegy\n",
                )
            },
        },
        {
            "name": "bootstrap-governance-reference",
            "repository_files": {
                "AGENTS.md": (
                    "Workflow governance map: "
                    + _joined(
                        "agent-discipline/agent-workflow-",
                        "design.md\n",
                    )
                )
            },
        },
        {
            "name": "bootstrap-deployment-payload-reference",
            "payload_content": _joined(
                "See agent-discipline/agent-workflow-test-",
                "strategy.md for bootstrap instructions.\n",
            ),
        },
        {
            "name": "candidate-internal-deployment-full-id",
            "repository_files": {
                "zone-a/SKILL.md": (
                    temporary_marker_prefix + "410\n"
                )
            },
            "repository_deployment_roots": ["zone-a"],
            "assert_unclassified_without_repository_root": True,
            "expected_report": _clearance_report(
                bootstrap_generated_or_payload_count=1,
                bootstrap_debt_id_count=1,
            ),
        },
        {
            "name": "external-deployment-full-id",
            "payload_content": temporary_marker_prefix + "420\n",
            "expected_report": _clearance_report(
                bootstrap_generated_or_payload_count=1,
                bootstrap_debt_id_count=1,
            ),
        },
        {
            "name": "two-deployment-roots-bare-marker-prefix",
            "repository_files": {
                "zone-a/SKILL.md": temporary_marker_prefix + "\n"
            },
            "repository_deployment_roots": ["zone-a"],
            "payload_content": temporary_marker_prefix + "\n",
            "expected_report": _clearance_report(
                bootstrap_generated_or_payload_count=2,
                bootstrap_debt_id_count=2,
            ),
        },
        {
            "name": "bootstrap-commit-ancestor",
            "ancestor": True,
        },
        {
            "name": "temporary-bootstrap-heading",
            "repository_files": {
                "notes.md": _joined(
                    "# TEMPO",
                    "RARY — P0 Boot",
                    "strap Issues — REMOVE BE",
                    "FORE FINAL P0\n",
                )
            },
        },
        {
            "name": "temporary-removal-marker",
            "repository_files": {
                "notes.md": _joined("REMOVE BE", "FORE FINAL P0\n")
            },
        },
        {
            "name": "bootstrap-debt-id",
            "repository_files": {
                "notes.md": (
                    "Deferred workflow item "
                    + temporary_marker_prefix
                    + "001.\n"
                )
            },
        },
        {
            "name": "temporary-marker-prefix",
            "repository_files": {
                "notes.md": temporary_marker_prefix + "\n"
            },
        },
        {
            "name": _joined(
                "bootstrap-",
                "evidence-",
                "pointer",
            ),
            "repository_files": {
                "notes.md": _joined(
                    "Boot",
                    "strap evidence: evidence/boot",
                    "strap-clearance.json\n",
                )
            },
        },
        {
            "name": _joined(
                "open-bootstrap-",
                "debt",
            ),
            "repository_files": {
                "notes.md": _joined(
                    "Boot",
                    "strap debt status: O",
                    "PEN\n",
                )
            },
        },
    )

    rejection_failures = []
    for case_index, case in enumerate(residual_cases):
        case_root = tmp_path / f"case-{case_index:02d}"
        repository_path = case_root / "repository"
        repository_path.mkdir(parents=True)
        deployment_root = case_root / "deployment"
        deployment_path = deployment_root / "SKILL.md"
        deployment_root.mkdir(parents=True)
        deployment_path.write_text(
            case.get("payload_content", "Synthetic payload.\n"),
            encoding="utf-8",
        )

        git = lambda *arguments, check=True: _git(
            repository_path,
            *arguments,
            check=check,
        )

        git("init")
        git("config", "user.name", "P0 Owner Test")
        git("config", "user.email", "p0-owner-test@example.invalid")
        (repository_path / "README.md").write_text(
            "Synthetic repository.\n",
            encoding="utf-8",
        )

        bootstrap_document_commits = []
        if case.get("ancestor"):
            git("add", "README.md")
            git("commit", "-m", "synthetic root")
            bootstrap_document_commits.append(
                git("rev-parse", "HEAD").stdout.strip()
            )
            (repository_path / "candidate.txt").write_text(
                "Synthetic candidate.\n",
                encoding="utf-8",
            )

        for relative_path, content in case.get(
            "repository_files", {}
        ).items():
            artifact_path = repository_path / relative_path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(content, encoding="utf-8")

        git("add", ".")
        git("commit", "-m", "synthetic candidate")
        candidate_sha = git("rev-parse", "HEAD").stdout.strip()
        repository_deployment_roots = [
            Path(root)
            for root in case.get("repository_deployment_roots", [])
        ]
        deployment_paths = [deployment_root, *repository_deployment_roots]

        if case.get("assert_unclassified_without_repository_root"):
            heuristic_tokens = {
                "payload",
                "generated",
                "release",
                "output",
                "build",
                "deploy",
            }
            for repository_root in repository_deployment_roots:
                root_tokens = {
                    token
                    for path_part in repository_root.parts
                    for token in path_part.lower().replace("_", "-").split("-")
                }
                assert root_tokens.isdisjoint(heuristic_tokens)
            baseline_failure = _clearance_rejection_failure(
                gate.WorkflowValidationError,
                lambda: gate.audit_bootstrap_clearance(
                    repository_path=repository_path,
                    candidate_sha=candidate_sha,
                    deployment_paths=[deployment_root],
                    bootstrap_document_commits=bootstrap_document_commits,
                ),
                case=(
                    f"{case['name']}: neutral path without caller-supplied "
                    "repository root"
                ),
                expected_report=_clearance_report(
                    bootstrap_debt_id_count=1,
                ),
            )
            if baseline_failure is not None:
                rejection_failures.append(baseline_failure)

        audit = lambda: gate.audit_bootstrap_clearance(
            repository_path=repository_path,
            candidate_sha=candidate_sha,
            deployment_paths=deployment_paths,
            bootstrap_document_commits=bootstrap_document_commits,
        )
        if "expected_report" in case:
            failure = _clearance_rejection_failure(
                gate.WorkflowValidationError,
                audit,
                case=case["name"],
                expected_report=case["expected_report"],
            )
        else:
            failure = _rejection_failure(
                gate.WorkflowValidationError,
                audit,
                case=case["name"],
            )
        if failure is not None:
            rejection_failures.append(failure)

    assert not rejection_failures, (
        "bootstrap clearance gaps:\n" + "\n".join(rejection_failures)
    )


def test_bootstrap_clearance_returns_exact_zero_report_for_clean_candidate(
    tmp_path,
):
    import inspect

    gate = _load_gate()
    signature = inspect.signature(gate.audit_bootstrap_clearance)
    parameters = list(signature.parameters.values())
    assert [parameter.name for parameter in parameters] == [
        "repository_path",
        "candidate_sha",
        "deployment_paths",
        "bootstrap_document_commits",
    ]
    assert all(
        parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        and parameter.default is inspect.Parameter.empty
        for parameter in parameters
    )
    repository_path = tmp_path / "r"
    repository_path.mkdir(parents=True)
    deployment_path = tmp_path / "d" / "SKILL.md"
    deployment_path.parent.mkdir(parents=True)
    deployment_path.write_text(
        "Synthetic clean deployment.\n",
        encoding="utf-8",
    )

    def git(*arguments, check=True, text=True, input=None):
        return _git(
            repository_path,
            *arguments,
            check=check,
            text=text,
            input=input,
        )

    git("init")
    git("config", "user.name", "P0 Owner Test")
    git("config", "user.email", "p0-owner-test@example.invalid")
    long_path_parts = tuple(f"segment-{index:02d}" for index in range(32))
    long_file_name = "payload.txt"
    long_relative_path = "/".join((*long_path_parts, long_file_name))
    assert all(len(part) < 32 for part in (*long_path_parts, long_file_name))
    long_checkout_path = repository_path / Path(*long_path_parts) / long_file_name
    assert len(str(long_checkout_path)) > 260

    def long_path_tree(content: bytes) -> str:
        blob_sha = git(
            "hash-object",
            "-w",
            "--stdin",
            text=False,
            input=content,
        ).stdout.strip().decode("ascii")
        tree_sha = git(
            "mktree",
            text=False,
            input=(
                f"100644 blob {blob_sha}\t{long_file_name}\n"
            ).encode("ascii"),
        ).stdout.strip().decode("ascii")
        for path_part in reversed(long_path_parts):
            tree_sha = git(
                "mktree",
                text=False,
                input=(
                    f"040000 tree {tree_sha}\t{path_part}\n"
                ).encode("ascii"),
            ).stdout.strip().decode("ascii")
        return tree_sha

    owner_test_content = Path(__file__).read_text(encoding="utf-8")
    temporary_marker_prefix = _joined("P0", "-", "BS", "-")
    assert temporary_marker_prefix not in owner_test_content
    owner_repository = Path(".")
    owner_candidate_sha = _git(
        owner_repository,
        "rev-parse",
        "HEAD",
    ).stdout.strip()
    owner_test_path = Path(__file__).relative_to(Path.cwd()).as_posix()
    owner_test_blob_sha = _git(
        owner_repository,
        "rev-parse",
        f"{owner_candidate_sha}:{owner_test_path}",
    ).stdout.strip()
    committed_owner_test = _git(
        owner_repository,
        "cat-file",
        "blob",
        owner_test_blob_sha,
        text=False,
    ).stdout
    assert committed_owner_test == owner_test_content.encode("utf-8")
    candidate_literal_scan = _git(
        owner_repository,
        "grep",
        "--fixed-strings",
        "--quiet",
        temporary_marker_prefix,
        owner_candidate_sha,
        "--",
        check=False,
    )
    assert candidate_literal_scan.returncode == 1

    candidate_tree = long_path_tree(b"Synthetic clean long-path payload.\n")
    candidate_sha = git(
        "commit-tree",
        candidate_tree,
        "-m",
        "synthetic clean candidate",
    ).stdout.strip()
    committed_paths = git(
        "ls-tree",
        "-r",
        "--name-only",
        candidate_sha,
    ).stdout.splitlines()
    assert long_relative_path in committed_paths

    residual_tree = long_path_tree(
        (
            "Deferred long-path workflow item "
            + temporary_marker_prefix
            + "730\n"
        ).encode("utf-8")
    )
    residual_candidate_sha = git(
        "commit-tree",
        residual_tree,
        "-m",
        "synthetic long-path residual candidate",
    ).stdout.strip()
    residual_paths = git(
        "ls-tree",
        "-r",
        "--name-only",
        residual_candidate_sha,
    ).stdout.splitlines()
    assert residual_paths == [long_relative_path]
    long_residual_failure = _clearance_rejection_failure(
        gate.WorkflowValidationError,
        lambda: gate.audit_bootstrap_clearance(
            repository_path=repository_path,
            candidate_sha=residual_candidate_sha,
            deployment_paths=[deployment_path],
            bootstrap_document_commits=[],
        ),
        case="long tracked Candidate blob with bootstrap residual",
        expected_report=_clearance_report(
            bootstrap_generated_or_payload_count=1,
            bootstrap_debt_id_count=1,
        ),
    )
    if long_residual_failure is not None:
        pytest.fail(long_residual_failure)

    non_ancestor_bootstrap_commit = git(
        "commit-tree",
        candidate_tree,
        "-m",
        "synthetic non-ancestor bootstrap commit",
    ).stdout.strip()
    assert git(
        "merge-base",
        "--is-ancestor",
        non_ancestor_bootstrap_commit,
        candidate_sha,
        check=False,
    ).returncode == 1

    report = gate.audit_bootstrap_clearance(
        repository_path=repository_path,
        candidate_sha=candidate_sha,
        deployment_paths=[deployment_path],
        bootstrap_document_commits=[non_ancestor_bootstrap_commit],
    )
    assert isinstance(report, dict)
    assert list(report) == CLEARANCE_REPORT_KEYS
    assert report == _clearance_report()
