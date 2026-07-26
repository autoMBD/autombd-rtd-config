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
# File:        test_workflow_gate_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-26
# Version:     0.6.0
# Description: Generality tests for canonical Agent workflow v2 records and gates.
# =================================================================================

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)

BASE_SHA = "19a7c4e36d12f5480ab9dc753da236f109e8bc47"
TEST_SHA = "b583f0a1c7d26e4905ab3c81f46d9e27a130bc65"
IMPLEMENTATION_SHA = "6e2a094cb8f713d5a6c9420be1387fd450ac8e31"
CANDIDATE_SHA = "da39b7452c1806b94f56139e827ca1d034e6af72"
TREE_SHA = "88f9a24e056d2520e186f8e26c9e64af47eb5671"
EVIDENCE_SHA = "902ba3cda1883801594b6e1b452790cc53948fda"
ISSUE_NUMBER = 314


def _load_gate():
    spec = importlib.util.spec_from_file_location("workflow_gate_generality", GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PUBLIC_STATES = [
    "classify",
    "test_authoring",
    "human_review_1",
    "implementing",
    "candidate",
    "testing",
    "rework",
    "reviewing",
    "final_human_review",
    "complete",
    "stopped",
]


def _public_test_revision(iteration: int = 2, sha: str | None = TEST_SHA):
    return {
        "identity": f"T{iteration}",
        "iteration": iteration,
        "base_sha": BASE_SHA,
        "sha": sha,
    }


def _public_implementation_revision(
    iteration: int = 3, sha: str | None = IMPLEMENTATION_SHA
):
    return {
        "identity": f"W{iteration}",
        "iteration": iteration,
        "base_sha": BASE_SHA,
        "sha": sha,
    }


def _public_candidate_revision(
    iteration: int = 4, sha: str = CANDIDATE_SHA
):
    return {
        "identity": f"C{iteration}",
        "iteration": iteration,
        "sha": sha,
        "parents": {
            "test_sha": TEST_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
        },
    }


def _public_test_review(decision: str = "approved"):
    reason = "Exercise arbitrary channel and partition counts."
    requested = decision == "changes_requested"
    command = (
        f"/request-test-changes {TEST_SHA}\n{reason}"
        if requested
        else f"/approve-test {TEST_SHA}"
    )
    evidence = {
        "provider": "github",
        "artifact": "issue_comment",
        "repository": "org/example-repository",
        "issue_number": ISSUE_NUMBER,
        "comment_id": 9876,
        "command": command,
        "test_sha": TEST_SHA,
        "top_level": True,
        "actor_type": "human",
        "actor_login": "human-reviewer",
        "current": True,
        "edited": False,
        "deleted": False,
        "requested_changes": False,
    }
    if requested:
        evidence["decision"] = "changes_requested"
        evidence["reason"] = reason
    return {
        "approved": not requested,
        "sha": TEST_SHA,
        "reviewer": "human-reviewer",
        "evidence": evidence,
        "monitor": {
            "status": "stopped",
            "interval_minutes": 10,
            "scope": "current_session",
            "automation": {
                "id": "test-review-monitor",
                "tier": "10m",
                "count": 0,
                "session": "current_session",
            },
        },
    }


def _public_final_review(candidate_sha: str = CANDIDATE_SHA):
    return {
        "approved": True,
        "sha": candidate_sha,
        "reviewer": "human-reviewer",
        "evidence": {
            "provider": "github",
            "artifact": "pull_request_review",
            "repository": "org/example-repository",
            "pull_request_number": 456,
            "review_id": 6543,
            "actor_type": "human",
            "actor_login": "human-reviewer",
            "state": "approved",
            "current": True,
            "candidate_sha": candidate_sha,
        },
        "monitor": {
            "status": "stopped",
            "interval_minutes": 10,
            "scope": "current_session",
            "automation": {
                "id": "final-review-monitor",
                "tier": "10m",
                "count": 0,
                "session": "current_session",
            },
        },
    }


def _public_record(state: str) -> dict[str, object]:
    record = {
        "version": 2,
        "schema": "agent_workflow_v2",
        "issue": {
            "number": ISSUE_NUMBER,
            "repository": "org/example-repository",
            "primary_type": "B",
            "impact_flags": ["PB"],
        },
        "authorization": {
            "github": {
                "authorized_human_logins": [
                    "human-reviewer",
                    "release-approver",
                ]
            }
        },
        "state": state,
        "gate": {"test_required": True},
        "revisions": {"base_sha": BASE_SHA},
        "counters": {"production_rework": 1, "kpi_optimization": 0},
        "exception": None,
    }
    revisions = record["revisions"]
    if state in PUBLIC_STATES[1:]:
        revisions["test"] = _public_test_revision(
            sha=None if state == "test_authoring" else TEST_SHA
        )
    if state in PUBLIC_STATES[3:]:
        revisions["implementation"] = _public_implementation_revision(
            sha=None if state == "implementing" else IMPLEMENTATION_SHA
        )
        record["human_reviews"] = {"test": _public_test_review()}
    if state in PUBLIC_STATES[4:]:
        revisions["candidate"] = _public_candidate_revision()
    if state == "testing":
        record["tester"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    elif state == "rework":
        record["tester"] = {"status": "fail", "candidate_sha": CANDIDATE_SHA}
    elif state in {"reviewing", "final_human_review", "complete"}:
        record["tester"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}
    if state == "reviewing":
        record["reviewer"] = {"status": "pending", "candidate_sha": CANDIDATE_SHA}
    elif state in {"final_human_review", "complete"}:
        record["reviewer"] = {"status": "pass", "candidate_sha": CANDIDATE_SHA}
    if state == "final_human_review":
        record.setdefault("human_reviews", {})["final"] = {
            "monitor": {
                "status": "active",
                "interval_minutes": 10,
                "scope": "current_session",
                "automation": {
                    "id": "final-review-monitor",
                    "tier": "10m",
                    "count": 0,
                    "session": "current_session",
                },
            }
        }
    elif state == "complete":
        record.setdefault("human_reviews", {})["final"] = _public_final_review()
    if state == "stopped":
        record["disposition"] = {
            "status": "stop_escalate",
            "reason": "The automatic production-rework cap was reached.",
        }
    return record


def _secured_record(state: str) -> dict[str, object]:
    record = _public_record(state)
    record["permission_preflight"] = {
        "host": {"available": True, "fact": "github_authenticated"},
        "sandbox": {
            "available": True,
            "fact": "network_permitted",
        },
        "required_capabilities": ["read_issue", "read_review"],
        "granted_capabilities": ["read_issue", "read_review"],
        "hydration": {
            "mode": "noninteractive",
            "source": "verified_non_secret_inputs",
        },
    }
    reviews = record.get("human_reviews", {})
    for name in ("test", "final"):
        review = reviews.get(name)
        if not isinstance(review, dict):
            continue
        evidence = review.get("evidence")
        if isinstance(evidence, dict):
            evidence["actor_login"] = review["reviewer"]
        monitor = review.get("monitor")
        if isinstance(monitor, dict):
            monitor["automation"] = {
                "id": f"{name}-review-monitor",
                "tier": f"{monitor['interval_minutes']}m",
                "count": 0,
                "session": "current_session",
            }
    return record


def _delete_path(record: dict[str, object], path: str) -> None:
    parts = path.split(".")
    target = record
    for part in parts[:-1]:
        target = target[part]
    target.pop(parts[-1], None)


def _set_path(record: dict[str, object], path: str, value: object) -> None:
    parts = path.split(".")
    target = record
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def test_public_contract_states_drive_required_and_forbidden_record_paths():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    states = contract["state_machine"]["states"]
    assert [item["name"] for item in states] == PUBLIC_STATES
    probes = {
        "classify": "issue.primary_type",
        "test_authoring": "revisions.test.identity",
        "human_review_1": "revisions.test.sha",
        "implementing": "revisions.implementation.identity",
        "candidate": "revisions.candidate.parents",
        "testing": "tester.candidate_sha",
        "rework": "tester.status",
        "reviewing": "reviewer.candidate_sha",
        "final_human_review": "reviewer.candidate_sha",
        "complete": "human_reviews.final.evidence",
        "stopped": "disposition.status",
    }
    for state in states:
        assert state["required_fields"]
        assert isinstance(state["forbidden_fields"], list)
        assert set(state["required_fields"]).isdisjoint(state["forbidden_fields"])
        assert probes[state["name"]] in state["required_fields"]


def test_minimal_record_for_every_public_state_is_valid_and_rules_are_executable():
    gate = _load_gate()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    state_rules = {item["name"]: item for item in contract["state_machine"]["states"]}
    forbidden_value = "f" * 40

    for state in PUBLIC_STATES:
        record = _public_record(state)
        before = deepcopy(record)
        assert gate.validate_record(record) == [], state
        assert record == before

        for required in state_rules[state]["required_fields"]:
            missing = deepcopy(record)
            _delete_path(missing, required)
            assert any(required in error for error in gate.validate_record(missing))

        for forbidden in state_rules[state]["forbidden_fields"]:
            illegal = deepcopy(record)
            _set_path(illegal, forbidden, forbidden_value)
            assert any(forbidden in error for error in gate.validate_record(illegal))


def test_public_revision_graph_and_routing_have_exact_shape_and_derivation():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert "revision_graph" not in contract
    assert contract["revision_provenance"]["candidate_parents"] == {
        "normal": ["test_sha", "implementation_sha"],
        "mechanical_light": ["base_sha", "implementation_sha"],
    }
    routing = contract["impact_routing"]
    assert list(routing) == ["PB", "MS", "MW", "RA", "TC", "VS", "EV", "AR", "RP", "ED", "SS", "DO"]
    assert all(item["required_gates"] and item["profiles"] for item in routing.values())
    flags = ["SS", "PB", "MW"]
    assert _load_gate().derive_routing(flags) == {
        "required_gates": sorted(
            {gate for flag in flags for gate in routing[flag]["required_gates"]}
        ),
        "profiles": sorted(
            {profile for flag in flags for profile in routing[flag]["profiles"]}
        ),
    }


def test_public_forward_transitions_use_approved_events():
    gate = _load_gate()
    sequence = [
        ("classify", "test_authoring", "classification_complete"),
        ("test_authoring", "human_review_1", "test_frozen"),
        ("human_review_1", "implementing", "test_approved"),
        ("implementing", "candidate", "candidate_created"),
        ("candidate", "testing", "testing_started"),
        ("testing", "reviewing", "tester_passed"),
        ("reviewing", "final_human_review", "reviewer_passed"),
        ("final_human_review", "complete", "final_approved"),
    ]
    for source, target, event in sequence:
        previous = _public_record(source)
        if event == "test_frozen":
            current = _pending_gate_record(10, 0)
            current.pop("permission_preflight")
        else:
            current = _public_record(target)
        assert gate.validate_transition(previous, current, event) == [], event

    previous = _public_record("testing")
    current = _public_record("reviewing")
    current["tester"]["candidate_sha"] = "8" * 40
    assert any(
        "candidate" in error.lower()
        for error in gate.validate_transition(previous, current, "tester_passed")
    )


def test_public_special_transitions_preserve_counters_and_revision_iterations():
    gate = _load_gate()

    previous = _public_record("human_review_1")
    previous["human_reviews"] = {"test": _public_test_review("changes_requested")}
    current = _public_record("test_authoring")
    current["revisions"]["test"] = _public_test_revision(3, None)
    assert gate.validate_transition(previous, current, "changes_requested") == []

    previous = _public_record("testing")
    previous["tester"]["status"] = "fail"
    current = _public_record("rework")
    assert gate.validate_transition(previous, current, "tester_failed") == []

    for event in ("dependency_blocked", "permission_blocked"):
        previous = _public_record("implementing")
        current = deepcopy(previous)
        assert gate.validate_transition(previous, current, event) == []

        previous = _public_record("rework")
        current = deepcopy(previous)
        assert gate.validate_transition(previous, current, event) == []

    previous = _public_record("rework")
    current = _public_record("implementing")
    current["counters"]["production_rework"] = 2
    current["revisions"]["implementation"] = _public_implementation_revision(4, None)
    current["revisions"]["candidate"] = {
        "identity": "C5",
        "iteration": 5,
        "sha": None,
    }
    assert gate.validate_transition(previous, current, "production_rework") == []

    previous = _public_record("rework")
    previous["counters"]["production_rework"] = 3
    current = _public_record("stopped")
    current["counters"]["production_rework"] = 3
    assert gate.validate_transition(previous, current, "production_rework") == []

    current["revisions"]["implementation"] = _public_implementation_revision(4)
    assert any(
        "fourth" in error or "revisions" in error
        for error in gate.validate_transition(previous, current, "production_rework")
    )


def test_direct_candidate_revised_is_not_a_legal_bypass():
    gate = _load_gate()
    previous = _public_record("reviewing")
    current = _public_record("testing")
    new_sha = "7" * 40
    current["revisions"]["candidate"] = _public_candidate_revision(5, new_sha)
    current["tester"] = {"status": "pending", "candidate_sha": new_sha}
    assert any(
        "not legal" in error
        for error in gate.validate_transition(
            previous, current, "candidate_revised"
        )
    )


def test_public_human_review_contract_and_evidence_are_exact():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    gate_1 = contract["state_machine"]["human_review_1"]["evidence"]
    assert gate_1["change_request_command"] == "/request-test-changes {test_sha}\n{reason}"
    final = contract["state_machine"]["final_human_review"]["evidence"]
    assert final["provider"] == "github"
    assert final["artifact"] == "pull_request_review"
    assert final["binds"] == "candidate_sha"
    assert final["authorized_actor"] == "human"
    assert {"repository", "pull_request_number", "review_id", "state", "candidate_sha"} <= set(final["required_fields"])
    assert {"candidate_sha_change", "review_edit", "review_dismissal", "request_changes"} <= set(final["invalidated_by"])

    validate_record = _load_gate().validate_record
    for review_name, field, value in (
        ("test", "top_level", False),
        ("test", "actor_type", "agent"),
        ("test", "current", False),
        ("final", "actor_type", "agent"),
        ("final", "state", "changes_requested"),
        ("final", "current", False),
        ("final", "candidate_sha", "8" * 40),
    ):
        record = _public_record("complete")
        record["human_reviews"][review_name]["evidence"][field] = value
        assert any(field in error for error in validate_record(record))


def test_public_minimal_issue_and_outer_review_shape_are_authoritative():
    validate_record = _load_gate().validate_record
    classify = _public_record("classify")
    assert set(classify["issue"]) == {
        "number",
        "repository",
        "primary_type",
        "impact_flags",
    }
    assert set(classify["authorization"]["github"]) == {
        "authorized_human_logins"
    }
    assert validate_record(classify) == []

    complete = _public_record("complete")
    test_review = complete["human_reviews"]["test"]
    final_review = complete["human_reviews"]["final"]
    assert "decision" not in test_review
    assert "decision" not in final_review
    assert test_review["approved"] is True
    assert test_review["sha"] == TEST_SHA
    assert final_review["approved"] is True
    assert final_review["sha"] == CANDIDATE_SHA
    assert validate_record(complete) == []

    complete["issue"]["repository"] = "org/example-repository"
    complete["issue"]["pull_request_number"] = 456
    assert validate_record(complete) == []


def test_public_change_request_uses_only_its_approved_extra_fields():
    record = _public_record("human_review_1")
    record["human_reviews"] = {"test": _public_test_review("changes_requested")}
    assert record["human_reviews"]["test"]["approved"] is False
    evidence = record["human_reviews"]["test"]["evidence"]
    assert evidence["decision"] == "changes_requested"
    assert evidence["requested_changes"] is False
    assert evidence["command"] == f"/request-test-changes {TEST_SHA}\n{evidence['reason']}"
    assert _load_gate().validate_record(record) == []


def test_public_change_request_accepts_requested_flag_or_decision_reason():
    gate = _load_gate()
    previous = _public_record("human_review_1")
    review = _public_test_review("changes_requested")
    evidence = review["evidence"]
    evidence["requested_changes"] = True
    evidence.pop("decision")
    evidence.pop("reason")
    previous["human_reviews"] = {"test": review}
    assert gate.validate_record(previous) == []

    current = _public_record("test_authoring")
    current["revisions"]["test"] = _public_test_revision(3, None)
    assert gate.validate_transition(previous, current, "changes_requested") == []


def test_active_change_request_monitor_is_atomic_but_active_approval_is_invalid():
    gate = _load_gate()
    for encoding in ("requested_flag", "decision_reason"):
        previous = _public_record("human_review_1")
        review = _public_test_review("changes_requested")
        if encoding == "requested_flag":
            review["evidence"]["requested_changes"] = True
            review["evidence"].pop("decision")
            review["evidence"].pop("reason")
        review["monitor"]["status"] = "active"
        previous["human_reviews"] = {"test": review}
        assert gate.validate_record(previous) == [], encoding

        current = _public_record("test_authoring")
        current["revisions"]["test"] = _public_test_revision(3, None)
        assert gate.validate_transition(
            previous, current, "changes_requested"
        ) == [], encoding

    approval = _public_record("implementing")
    approval["human_reviews"]["test"]["monitor"]["status"] = "active"
    assert any(
        "stopped" in error
        for error in gate.validate_record(approval)
    )

    approval = _public_record("implementing")
    approval["human_reviews"]["test"]["reviewer"] = None
    assert any(
        "reviewer" in error
        for error in gate.validate_record(approval)
    )


def test_pending_gate_1_and_stopped_provenance_are_valid_minimal_states():
    validate_record = _load_gate().validate_record
    pending = _public_record("human_review_1")
    pending["human_reviews"] = {
        "test": {
            "approved": False,
            "sha": TEST_SHA,
            "reviewer": None,
            "evidence": None,
            "monitor": {
                "status": "active",
                "interval_minutes": 10,
                "scope": "current_session",
                "automation": {
                    "id": "test-review-monitor",
                    "tier": "10m",
                    "count": 0,
                    "session": "current_session",
                },
            },
        }
    }
    assert validate_record(pending) == []

    stopped = _public_record("stopped")
    stopped["counters"]["production_rework"] = 3
    stopped["tester"] = {"status": "fail", "candidate_sha": CANDIDATE_SHA}
    assert validate_record(stopped) == []

    stopped["reviewer"] = {"status": "not_run", "candidate_sha": CANDIDATE_SHA}
    assert any("reviewer" in error for error in validate_record(stopped))


def test_public_review_diagnostics_name_the_invalid_concept():
    validate_record = _load_gate().validate_record
    probes = [
        ("test", "issue_number", 999, "issue number"),
        ("test", "comment_id", None, "comment id"),
        ("test", "top_level", False, "top-level"),
        ("test", "actor_type", "automation", "human"),
        ("test", "current", False, "current"),
        ("test", "edited", True, "edited"),
        ("test", "deleted", True, "deleted"),
        ("test", "requested_changes", True, "request"),
        ("test", "requested_changes", None, "request"),
        ("final", "pull_request_number", None, "pull request"),
        ("final", "review_id", None, "review id"),
        ("final", "actor_type", "automation", "human"),
        ("final", "state", "pending", "approved"),
        ("final", "candidate_sha", "8" * 40, "candidate"),
    ]
    for review_name, field, value, concept in probes:
        record = _public_record("complete")
        record["human_reviews"][review_name]["evidence"][field] = value
        errors = validate_record(record)
        assert any(concept in error.lower() for error in errors), (field, errors)


def test_final_evidence_revision_is_candidate_bound_and_path_allowlisted():
    validate_record = _load_gate().validate_record
    for path in (
        "agent-discipline/agent-lessons-learned.md",
        "docs/tests/rtd-config-acceptance-report.md",
    ):
        record = _public_record("complete")
        record["revisions"]["final_evidence"] = {
            "identity": "E9",
            "sha": EVIDENCE_SHA,
            "reviewed_candidate_sha": CANDIDATE_SHA,
            "changed_paths": [path],
        }
        assert validate_record(record) == [], path

    record["revisions"]["final_evidence"]["changed_paths"] = [
        "agent-discipline/workflow-contract.json"
    ]
    assert any("changed_paths" in error for error in validate_record(record))


def test_skill_has_bounded_structured_handoff_sections_for_all_roles():
    text = Path("agent-discipline/skills/agent-workflow/SKILL.md").read_text(encoding="utf-8")
    assert "## Handoff templates" in text
    role_markers = {
        "Orchestrator": ["classification", "exact SHA", "human review"],
        "Explorer": ["ground truth", "read-only", "decision-ready"],
        "Worker": ["capability", "acceptance-test implementation", "implementation SHA"],
        "Tester": ["candidate SHA", "production repair", "pass/fail"],
        "Reviewer": ["tester pass", "production write", "lessons"],
    }
    for role, markers in role_markers.items():
        match = re.search(rf"(?ms)^### {role}(?: Handoff)?\s*$\n(.*?)(?=^### |^## |\Z)", text)
        assert match, role
        section = match.group(1)
        assert len(section.split()) <= 220
        for label in ("Inputs", "Forbidden sources", "Forbidden actions", "Outputs", "Stop conditions", "Acceptance criteria"):
            assert label in section
        for marker in markers:
            assert marker.lower() in section.lower()

    assert "/request-test-changes {test_sha}" in text
    assert "{reason}" in text
    assert "two-line" in text.lower() or "exactly two lines" in text.lower()


def test_cli_exact_json_option_and_stable_result_envelope():
    script = str(GATE_PATH)
    valid = _public_record("classify")
    invalid = deepcopy(valid)
    invalid["issue"].pop("primary_type")
    cases = [
        ([sys.executable, script, "--json", "-"], json.dumps(valid).encode(), 0, None),
        ([sys.executable, script, "--json", "-"], json.dumps(invalid).encode(), 1, "validation"),
        ([sys.executable, script, "--json", "-"], b"{bad", 2, "input"),
        ([sys.executable, script, "--json", "-"], b"\xff", 2, "input"),
        ([sys.executable, script, "--json", "tests/.tmp/missing-workflow.json"], None, 2, "input"),
        ([sys.executable, script], None, 2, "input"),
    ]
    for command, payload, returncode, error_type in cases:
        result = subprocess.run(command, input=payload, capture_output=True, check=False)
        assert result.returncode == returncode
        body = json.loads(result.stdout.decode("utf-8"))
        assert body["ok"] is (returncode == 0)
        assert isinstance(body["errors"], list)
        assert body["error_type"] == error_type
        assert b"Traceback" not in result.stdout + result.stderr


def _light_record(state: str) -> dict[str, object]:
    record = _public_record(state)
    record["issue"] = {
        "number": ISSUE_NUMBER,
        "repository": "org/example-repository",
        "primary_type": "N",
        "impact_flags": ["DO"],
    }
    record["gate"] = {
        "test_required": False,
        "light_path": {
            "reason": "Mechanical documentation normalization only.",
            "residual_risk": "No runtime or workflow behavior changes.",
            "remaining_verification": ["Review the rendered documentation."],
        },
    }
    revisions = record["revisions"]
    revisions.pop("test", None)
    candidate = revisions.get("candidate")
    if candidate is not None:
        candidate["parents"] = {
            "base_sha": BASE_SHA,
            "implementation_sha": IMPLEMENTATION_SHA,
        }
    reviews = record.get("human_reviews")
    if reviews is not None:
        reviews.pop("test", None)
        if not reviews:
            record.pop("human_reviews")
    if record.get("tester") is not None:
        record["tester"]["mode"] = "mechanical_verification"
    return record


def test_contract_and_records_use_only_canonical_v2():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["version"] == 2
    assert contract["schema"] == "agent_workflow_v2"
    assert contract["state_machine"]["name"] == "agent_workflow_v2"
    assert "routing" not in contract
    assert "revision_graph" not in contract
    assert contract["revision_provenance"]["evidence_only"]["allowed_paths"] == [
        "agent-discipline/agent-lessons-learned.md",
        "docs/tests/rtd-config-acceptance-report.md",
    ]


def test_all_v1_shapes_have_one_stable_rejection():
    gate = _load_gate()
    for markers in (
        {},
        {"lanes": {}},
        {"transition": {}},
        {"corrections": {}},
        {"lanes": {}, "transition": {}, "corrections": {}},
    ):
        assert gate.validate_record({"version": 1, **markers}) == [
            "workflow record version 1 is unsupported; expected canonical version 2"
        ]


def test_v2_legacy_markers_never_select_another_validator():
    gate = _load_gate()
    for marker in ("lanes", "transition", "corrections"):
        record = _light_record("classify")
        record[marker] = {}
        errors = gate.validate_record(record)
        assert any(
            marker in error and "canonical version 2" in error
            for error in errors
        )


def test_n_do_runs_the_canonical_mechanical_verification_path():
    gate = _load_gate()
    sequence = [
        ("classify", "implementing", "classification_complete"),
        ("implementing", "candidate", "candidate_created"),
        ("candidate", "testing", "mechanical_verification_started"),
        ("testing", "reviewing", "tester_passed"),
        ("reviewing", "final_human_review", "reviewer_passed"),
        ("final_human_review", "complete", "final_approved"),
    ]
    for source, target, event in sequence:
        previous = _light_record(source)
        current = _light_record(target)
        assert gate.validate_record(previous) == [], source
        assert gate.validate_record(current) == [], target
        assert gate.validate_transition(previous, current, event) == [], event

    candidate = _light_record("candidate")
    assert set(candidate["revisions"]["candidate"]["parents"]) == {
        "base_sha",
        "implementation_sha",
    }
    candidate["revisions"]["test"] = _public_test_revision()
    candidate["human_reviews"] = {"test": _public_test_review()}
    errors = gate.validate_record(candidate)
    assert any("revisions.test" in error and "forbidden" in error for error in errors)
    assert any("human_reviews.test" in error and "forbidden" in error for error in errors)


def test_stopped_terminal_rejects_future_reviewer_final_and_evidence_revision():
    gate = _load_gate()
    base = _light_record("stopped")
    assert gate.validate_record(base) == []
    probes = (
        ("reviewer", {"status": "pass", "candidate_sha": CANDIDATE_SHA}),
        ("human_reviews", {"final": _public_final_review()}),
    )
    for field, value in probes:
        record = deepcopy(base)
        record[field] = value
        assert any(field in error for error in gate.validate_record(record))
    evidence = deepcopy(base)
    evidence["revisions"]["final_evidence"] = {
        "identity": "E8",
        "sha": EVIDENCE_SHA,
        "reviewed_candidate_sha": CANDIDATE_SHA,
        "changed_paths": ["agent-discipline/agent-lessons-learned.md"],
    }
    assert any(
        "revisions.final_evidence" in error
        for error in gate.validate_record(evidence)
    )


def test_testing_and_final_human_review_reject_future_evidence():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    state_rules = {
        item["name"]: item for item in contract["state_machine"]["states"]
    }
    assert "reviewer" in state_rules["testing"]["forbidden_fields"]
    assert (
        "revisions.final_evidence"
        in state_rules["final_human_review"]["forbidden_fields"]
    )

    testing = _public_record("testing")
    testing["reviewer"] = {
        "status": "not_run",
        "candidate_sha": CANDIDATE_SHA,
    }
    assert any(
        "reviewer" in error and "forbidden" in error
        for error in _load_gate().validate_record(testing)
    )

    final_review = _public_record("final_human_review")
    final_review["revisions"]["final_evidence"] = {
        "identity": "E11",
        "sha": EVIDENCE_SHA,
        "reviewed_candidate_sha": CANDIDATE_SHA,
        "changed_paths": ["agent-discipline/agent-lessons-learned.md"],
    }
    assert any(
        "revisions.final_evidence" in error
        and ("future" in error or "forbidden" in error)
        for error in _load_gate().validate_record(final_review)
    )


def test_cli_previous_event_pair_is_checked_before_file_reads():
    missing = "tests/.tmp/does-not-exist-workflow.json"
    for options in (
        ["--json", missing, "--previous", missing],
        ["--json", missing, "--event", "tester_passed"],
    ):
        result = subprocess.run(
            [sys.executable, str(GATE_PATH), *options],
            capture_output=True,
            check=False,
        )
        assert result.returncode == 2
        assert json.loads(result.stdout.decode("utf-8")) == {
            "ok": False,
            "errors": [
                "invocation input error: --previous and --event must be provided together"
            ],
            "error_type": "input",
        }


def test_contract_exposes_per_event_mutation_matrix_and_no_direct_candidate_bypass():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    events = {
        (item["from"], item["to"], item["event"])
        for item in contract["state_machine"]["transitions"]
    }
    assert ("reviewing", "testing", "candidate_revised") not in events
    assert ("final_human_review", "testing", "candidate_revised") not in events
    assert ("reviewing", "rework", "review_correction") in events
    assert (
        "final_human_review",
        "reviewing",
        "changes_requested",
    ) in events
    assert ("final_human_review", "rework", "review_correction") not in events
    assert ("testing", "implementing", "kpi_optimization") in events
    matrix = contract["transition_mutation_matrix"]
    assert set(matrix) == {item[2] for item in events}
    assert all(
        isinstance(rule["mutable_roots"], list)
        and "issue" not in rule["mutable_roots"]
        for rule in matrix.values()
    )


def test_review_corrections_enter_counted_rework_and_direct_candidate_revision_fails():
    gate = _load_gate()
    final = _secured_record("final_human_review")
    reviewing = _secured_record("reviewing")
    reviewing["reviewer"]["status"] = "fail"
    assert gate.validate_transition(
        final, reviewing, "changes_requested"
    ) == []

    rework = _secured_record("rework")
    rework["tester"]["status"] = "pass"
    assert gate.validate_transition(
        reviewing, rework, "review_correction"
    ) == []

    for source in (reviewing, final):
        bypass = _secured_record("testing")
        bypass["revisions"]["candidate"] = _public_candidate_revision(
            5, "7" * 40
        )
        bypass["tester"] = {"status": "pending", "candidate_sha": "7" * 40}
        assert gate.validate_transition(source, bypass, "candidate_revised")

    implementation = _secured_record("implementing")
    implementation["counters"]["production_rework"] = 2
    implementation["revisions"]["implementation"] = (
        _public_implementation_revision(4, None)
    )
    implementation["revisions"]["candidate"] = {
        "identity": "C5",
        "iteration": 5,
        "sha": None,
    }
    assert gate.validate_transition(
        rework, implementation, "production_rework"
    ) == []

    committed_implementation_sha = "e" * 40
    committed_candidate_sha = "f" * 40
    candidate = _secured_record("candidate")
    candidate["counters"]["production_rework"] = 2
    candidate["revisions"]["implementation"] = (
        _public_implementation_revision(4, committed_implementation_sha)
    )
    candidate["revisions"]["candidate"] = {
        "identity": "C5",
        "iteration": 5,
        "sha": committed_candidate_sha,
        "parents": {
            "test_sha": TEST_SHA,
            "implementation_sha": committed_implementation_sha,
        },
    }
    assert gate.validate_transition(
        implementation, candidate, "candidate_created"
    ) == []

    substituted_candidate = deepcopy(candidate)
    substituted_candidate["revisions"]["candidate"]["identity"] = "C6"
    substituted_candidate["revisions"]["candidate"]["iteration"] = 6
    assert any(
        "exact staged C iteration" in error
        for error in gate.validate_transition(
            implementation, substituted_candidate, "candidate_created"
        )
    )


def test_mutation_matrix_freezes_issue_base_test_and_final_candidate_binding():
    gate = _load_gate()
    previous = _secured_record("candidate")
    current = _secured_record("testing")
    for mutation in ("issue", "base", "test"):
        illegal = deepcopy(current)
        if mutation == "issue":
            illegal["issue"]["number"] += 1
        elif mutation == "base":
            illegal["revisions"]["base_sha"] = "a" * 40
            illegal["revisions"]["implementation"]["base_sha"] = "a" * 40
            illegal["revisions"]["test"]["base_sha"] = "a" * 40
        else:
            illegal["revisions"]["test"] = _public_test_revision(7, "b" * 40)
        assert any(
            "mutation matrix" in error or "frozen" in error
            for error in gate.validate_transition(
                previous, illegal, "testing_started"
            )
        ), mutation

    final_previous = _secured_record("final_human_review")
    final_current = _secured_record("complete")
    new_candidate = "c" * 40
    final_current["revisions"]["candidate"]["sha"] = new_candidate
    final_current["human_reviews"]["final"] = _public_final_review(new_candidate)
    final_current["human_reviews"]["final"]["evidence"]["actor_login"] = (
        "human-reviewer"
    )
    final_current["human_reviews"]["final"]["monitor"]["automation"] = {
        "id": "final-review-monitor",
        "tier": "10m",
        "count": 0,
        "session": "current_session",
    }
    final_current["tester"]["candidate_sha"] = new_candidate
    final_current["reviewer"]["candidate_sha"] = new_candidate
    assert any(
        "Candidate" in error or "mutation matrix" in error
        for error in gate.validate_transition(
            final_previous, final_current, "final_approved"
        )
    )


def test_human_review_actor_login_matches_reviewer_and_repository_policy():
    gate = _load_gate()
    assert gate.validate_record(_secured_record("complete")) == []
    for review_name, value in (
        ("test", "spoofed-login"),
        ("final", "release-approver"),
    ):
        record = _secured_record("complete")
        record["human_reviews"][review_name]["evidence"]["actor_login"] = value
        errors = gate.validate_record(record)
        assert any(
            "actor_login" in error and "reviewer" in error for error in errors
        )

    unauthorized = _secured_record("complete")
    unauthorized["authorization"]["github"][
        "authorized_human_logins"
    ] = ["release-approver"]
    assert any(
        "authorized" in error
        for error in gate.validate_record(unauthorized)
    )


def test_kpi_optimization_is_executable_for_iterations_one_and_three_but_not_four():
    gate = _load_gate()
    for previous_count in (0, 2):
        previous = _secured_record("testing")
        previous["tester"]["status"] = "pass"
        previous["counters"]["kpi_optimization"] = previous_count
        current = _secured_record("implementing")
        current["counters"]["kpi_optimization"] = previous_count + 1
        current["revisions"]["implementation"] = (
            _public_implementation_revision(4, None)
        )
        current["revisions"]["candidate"] = {
            "identity": "C5",
            "iteration": 5,
            "sha": None,
        }
        assert current["revisions"]["candidate"]["sha"] is None
        assert "tester" not in current
        assert "reviewer" not in current
        assert gate.validate_transition(
            previous, current, "kpi_optimization"
        ) == [], previous_count

    previous = _secured_record("testing")
    previous["tester"]["status"] = "pass"
    previous["counters"]["kpi_optimization"] = 3
    fourth = _secured_record("implementing")
    fourth["counters"]["kpi_optimization"] = 4
    fourth["revisions"]["implementation"] = (
        _public_implementation_revision(4, None)
    )
    fourth["revisions"]["candidate"] = {
        "identity": "C5",
        "iteration": 5,
        "sha": None,
    }
    assert any(
        "KPI" in error or "0..3" in error or "fourth" in error
        for error in gate.validate_transition(
            previous, fourth, "kpi_optimization"
        )
    )


def test_canonical_record_is_closed_at_every_nested_mapping():
    gate = _load_gate()
    probes = [
        ("record", lambda record: record.__setitem__("mystery", True)),
        ("issue", lambda record: record["issue"].__setitem__("mystery", True)),
        ("gate", lambda record: record["gate"].__setitem__("mystery", True)),
        (
            "revision",
            lambda record: record["revisions"]["test"].__setitem__(
                "mystery", True
            ),
        ),
        (
            "parents",
            lambda record: record["revisions"]["candidate"]["parents"].__setitem__(
                "mystery", "d" * 40
            ),
        ),
        (
            "review evidence",
            lambda record: record["human_reviews"]["final"]["evidence"].__setitem__(
                "mystery", True
            ),
        ),
        (
            "monitor automation",
            lambda record: record["human_reviews"]["final"]["monitor"][
                "automation"
            ].__setitem__("mystery", True),
        ),
        (
            "permission host",
            lambda record: record["permission_preflight"]["host"].__setitem__(
                "mystery", True
            ),
        ),
    ]
    for label, mutate in probes:
        record = _secured_record("complete")
        mutate(record)
        assert any(
            "unknown field" in error for error in gate.validate_record(record)
        ), label


def test_revision_identity_and_parent_shape_come_from_one_canonical_authority():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert "revision_graph" not in contract
    provenance = contract["revision_provenance"]
    assert provenance["candidate_parents"] == {
        "normal": ["test_sha", "implementation_sha"],
        "mechanical_light": ["base_sha", "implementation_sha"],
    }
    assert contract["light_path"].get("candidate_parents") is None


def test_permission_preflight_and_monitor_backoff_are_fail_closed():
    gate = _load_gate()
    assert gate.validate_record(_secured_record("complete")) == []
    for field in ("host", "sandbox", "required_capabilities", "hydration"):
        record = _secured_record("complete")
        record["permission_preflight"].pop(field)
        assert any(
            f"permission_preflight.{field}" in error
            for error in gate.validate_record(record)
        )

    denied = _secured_record("complete")
    denied["permission_preflight"]["granted_capabilities"] = ["read_review"]
    assert any("read_issue" in error for error in gate.validate_record(denied))

    for tier, count in ((10, 0), (10, 2), (30, 0), (30, 2), (60, 0)):
        record = _secured_record("complete")
        monitor = record["human_reviews"]["final"]["monitor"]
        monitor["interval_minutes"] = tier
        monitor["automation"]["tier"] = f"{tier}m"
        monitor["automation"]["count"] = count
        assert gate.validate_record(record) == [], (tier, count)

    for tier, count in ((20, 0), (10, 3), (30, 3), (60, 2)):
        record = _secured_record("complete")
        monitor = record["human_reviews"]["final"]["monitor"]
        monitor["interval_minutes"] = tier
        monitor["automation"]["tier"] = f"{tier}m"
        monitor["automation"]["count"] = count
        assert gate.validate_record(record), (tier, count)

    for forbidden_time_field in ("timestamp", "deadline"):
        record = _secured_record("complete")
        record["human_reviews"]["final"]["monitor"][forbidden_time_field] = (
            "2026-07-26T12:00:00Z"
        )
        assert any(
            "unknown field" in error
            for error in gate.validate_record(record)
        ), forbidden_time_field


def test_acceptance_report_changelog_is_semver_newest_first_without_content_loss():
    text = Path("docs/tests/rtd-config-acceptance-report.md").read_text(
        encoding="utf-8"
    )
    row_351 = (
        "| 2026-07-22 | 0.35.1 | Removed active runner-governance terminology "
        "from the KPI metric description without changing the measured window "
        "or any functional/KPI evidence. Historical entries remain unchanged. |"
    )
    assert text.count(row_351) == 1
    positions = [text.index(f"| 2026-07-{date} | {version} |") for date, version in (
        ("22", "0.35.2"),
        ("22", "0.35.1"),
        ("17", "0.35.0"),
    )]
    assert positions == sorted(positions)


def _use_canonical_authorization(record: dict[str, object]) -> None:
    record["authorization"] = {
        "github": {
            "authorized_human_logins": [
                "human-reviewer",
                "release-approver",
            ]
        }
    }


def _canonical_permission_preflight() -> dict[str, object]:
    return {
        "host": {
            "available": True,
            "fact": "github_authenticated",
        },
        "sandbox": {
            "available": True,
            "fact": "network_permitted",
        },
        "required_capabilities": ["read_issue", "read_review"],
        "granted_capabilities": ["read_issue", "read_review"],
        "hydration": {
            "mode": "noninteractive",
            "source": "verified_non_secret_inputs",
        },
    }


def test_authorization_policy_has_one_canonical_top_level_location():
    gate = _load_gate()
    record = _public_record("complete")
    _use_canonical_authorization(record)
    record.pop("permission_preflight", None)
    assert gate.validate_record(record) == []

    duplicate = deepcopy(record)
    duplicate["issue"]["authorized_humans"] = ["human-reviewer"]
    assert any(
        "unknown field" in error
        for error in gate.validate_record(duplicate)
    )


def test_permission_preflight_is_optional_but_fail_closed_when_present():
    gate = _load_gate()
    absent = _public_record("complete")
    _use_canonical_authorization(absent)
    absent.pop("permission_preflight", None)
    assert gate.validate_record(absent) == []

    present = deepcopy(absent)
    present["permission_preflight"] = _canonical_permission_preflight()
    assert gate.validate_record(present) == []

    empty_capabilities = deepcopy(present)
    empty_capabilities["permission_preflight"]["required_capabilities"] = []
    empty_capabilities["permission_preflight"]["granted_capabilities"] = []
    assert gate.validate_record(empty_capabilities) == []

    for path, field in (
        ("host", "fact"),
        ("sandbox", "fact"),
        ("hydration", "source"),
    ):
        invalid = deepcopy(present)
        invalid["permission_preflight"][path][field] = ""
        assert any(
            f"permission_preflight.{path}.{field}" in error
            for error in gate.validate_record(invalid)
        )


def test_candidate_parent_modes_use_canonical_normal_and_mechanical_light_names():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["revision_provenance"]["candidate_parents"] == {
        "normal": ["test_sha", "implementation_sha"],
        "mechanical_light": ["base_sha", "implementation_sha"],
    }


def _canonical_monitor(
    interval_minutes: int = 10,
    count: int = 0,
    *,
    status: str = "stopped",
    monitor_id: str = "review-monitor-arbitrary",
    session: str = "current_session",
) -> dict[str, object]:
    return {
        "status": status,
        "interval_minutes": interval_minutes,
        "scope": "current_session",
        "automation": {
            "id": monitor_id,
            "tier": f"{interval_minutes}m",
            "count": count,
            "session": session,
        },
    }


def _use_canonical_monitors(record: dict[str, object]) -> None:
    reviews = record.get("human_reviews")
    if not isinstance(reviews, dict):
        return
    for review in reviews.values():
        if not isinstance(review, dict) or "monitor" not in review:
            continue
        status = review["monitor"]["status"]
        review["monitor"] = _canonical_monitor(status=status)


def test_monitor_record_shape_and_tier_state_space_are_canonical():
    gate = _load_gate()
    for interval, counts in ((10, range(3)), (30, range(3)), (60, (0,))):
        for count in counts:
            record = _secured_record("complete")
            _use_canonical_monitors(record)
            record["human_reviews"]["final"]["monitor"] = _canonical_monitor(
                interval, count
            )
            assert gate.validate_record(record) == [], (interval, count)

    invalid_states = (
        (15, "15m", 0),
        (10, "30m", 0),
        (10, "10m", 3),
        (30, "30m", 3),
        (60, "60m", 1),
    )
    for interval, tier, count in invalid_states:
        record = _secured_record("complete")
        _use_canonical_monitors(record)
        monitor = record["human_reviews"]["final"]["monitor"]
        monitor["interval_minutes"] = interval
        monitor["automation"]["tier"] = tier
        monitor["automation"]["count"] = count
        assert gate.validate_record(record), (interval, tier, count)


def test_monitor_automation_has_only_canonical_fields_and_session():
    gate = _load_gate()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["record_schema"]["allowed_fields"]["monitor.automation"] == [
        "id",
        "tier",
        "count",
        "session",
    ]

    for legacy_field in ("tier_minutes", "backoff_seconds", "foreground"):
        record = _secured_record("complete")
        _use_canonical_monitors(record)
        record["human_reviews"]["final"]["monitor"]["automation"][
            legacy_field
        ] = 30
        assert any(
            "unknown field" in error
            for error in gate.validate_record(record)
        ), legacy_field

    wrong_session = _secured_record("complete")
    _use_canonical_monitors(wrong_session)
    wrong_session["human_reviews"]["final"]["monitor"]["automation"][
        "session"
    ] = "replacement_session"
    assert any(
        "session" in error
        for error in gate.validate_record(wrong_session)
    )


def _pending_gate_record(
    interval_minutes: int,
    count: int,
    *,
    monitor_id: str = "review-monitor-arbitrary",
    session: str = "current_session",
) -> dict[str, object]:
    record = _secured_record("human_review_1")
    record["human_reviews"] = {
        "test": {
            "approved": False,
            "sha": TEST_SHA,
            "reviewer": None,
            "evidence": None,
            "monitor": _canonical_monitor(
                interval_minutes,
                count,
                status="active",
                monitor_id=monitor_id,
                session=session,
            ),
        }
    }
    return record


def test_review_poll_no_change_progression_is_exact_and_same_session():
    gate = _load_gate()
    legal = (
        ((10, 0), (10, 1)),
        ((10, 1), (10, 2)),
        ((10, 2), (30, 0)),
        ((30, 0), (30, 1)),
        ((30, 1), (30, 2)),
        ((30, 2), (60, 0)),
        ((60, 0), (60, 0)),
    )
    for (before_interval, before_count), (
        after_interval,
        after_count,
    ) in legal:
        previous = _pending_gate_record(before_interval, before_count)
        current = _pending_gate_record(after_interval, after_count)
        assert gate.validate_transition(
            previous, current, "review_poll_no_change"
        ) == [], (
            before_interval,
            before_count,
            after_interval,
            after_count,
        )

    invalid = (
        ((10, 0), (30, 0)),
        ((10, 1), (10, 0)),
        ((10, 2), (10, 2)),
        ((30, 2), (30, 0)),
        ((60, 0), (10, 0)),
    )
    for (before_interval, before_count), (
        after_interval,
        after_count,
    ) in invalid:
        previous = _pending_gate_record(before_interval, before_count)
        current = _pending_gate_record(after_interval, after_count)
        assert gate.validate_transition(
            previous, current, "review_poll_no_change"
        ), (
            before_interval,
            before_count,
            after_interval,
            after_count,
        )

    previous = _pending_gate_record(10, 0)
    for field, value in (
        ("id", "replacement-monitor"),
        ("session", "replacement_session"),
    ):
        current = _pending_gate_record(10, 1)
        current["human_reviews"]["test"]["monitor"]["automation"][field] = (
            value
        )
        assert gate.validate_transition(
            previous, current, "review_poll_no_change"
        ), field


def test_review_gate_creation_and_replacement_reset_to_10m_count_zero():
    gate = _load_gate()
    test_authoring = _secured_record("test_authoring")
    pending_test_review = _pending_gate_record(10, 0)
    assert gate.validate_transition(
        test_authoring, pending_test_review, "test_frozen"
    ) == []

    wrong_test_reset = _pending_gate_record(30, 0)
    assert gate.validate_transition(
        test_authoring, wrong_test_reset, "test_frozen"
    )

    reviewing = _secured_record("reviewing")
    final_review = _secured_record("final_human_review")
    _use_canonical_monitors(final_review)
    assert gate.validate_transition(
        reviewing, final_review, "reviewer_passed"
    ) == []

    wrong_final_reset = deepcopy(final_review)
    wrong_final_reset["human_reviews"]["final"]["monitor"] = (
        _canonical_monitor(30, 0, status="active")
    )
    assert gate.validate_transition(
        reviewing, wrong_final_reset, "reviewer_passed"
    )
