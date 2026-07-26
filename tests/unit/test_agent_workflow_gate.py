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
# File:        test_agent_workflow_gate.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-21
# Version:     0.1.0
# Description: Behavioral tests for the deterministic Agent workflow gate.
# =================================================================================

import copy
import importlib.util
from pathlib import Path

import pytest


GATE_PATH = Path(
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py"
)
UNSUPPORTED_V1 = (
    "workflow record version 1 is unsupported; expected canonical version 2"
)


def _gate_module():
    if not GATE_PATH.is_file():
        pytest.fail("missing deterministic workflow gate")
    spec = importlib.util.spec_from_file_location("agent_workflow_gate", GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(character: str) -> str:
    return character * 40


def _valid_record() -> dict:
    return {
        "version": 2,
        "schema": "agent_workflow_v2",
        "issue": {
            "number": 321,
            "primary_type": "W",
            "impact_flags": ["AR"],
        },
        "state": "complete",
        "gate": {"test_required": True},
        "revisions": {
            "base_sha": _sha("a"),
            "test": {
                "identity": "T1",
                "iteration": 1,
                "base_sha": _sha("a"),
                "sha": _sha("b"),
            },
            "implementation": {
                "identity": "W1",
                "iteration": 1,
                "base_sha": _sha("a"),
                "sha": _sha("c"),
            },
            "candidate": {
                "identity": "C1",
                "iteration": 1,
                "sha": _sha("d"),
                "parents": {
                    "test_sha": _sha("b"),
                    "implementation_sha": _sha("c"),
                },
            },
            "final_evidence": {
                "identity": "E1",
                "sha": _sha("e"),
                "reviewed_candidate_sha": _sha("d"),
                "changed_paths": [
                    "agent-discipline/agent-lessons-learned.md"
                ],
            },
        },
        "human_reviews": {
            "test": {
                "approved": True,
                "sha": _sha("b"),
                "reviewer": "owner",
                "evidence": {
                    "provider": "github",
                    "repository": "autoMBD/autombd-rtd-config",
                    "issue_number": 321,
                    "comment_id": 123456,
                    "command": f"/approve-test {_sha('b')}",
                    "artifact": "issue_comment",
                    "top_level": True,
                    "actor_type": "human",
                    "actor_login": "owner",
                    "current": True,
                    "edited": False,
                    "deleted": False,
                    "requested_changes": False,
                },
                "monitor": {
                    "status": "stopped",
                    "interval_minutes": 10,
                    "scope": "current_session",
                    "automation": {
                        "id": "review-monitor-321",
                        "tier": "foreground",
                        "count": 1,
                        "session": "current_session",
                        "backoff_seconds": 10,
                    },
                },
            },
            "final": {
                "approved": True,
                "sha": _sha("d"),
                "reviewer": "owner",
                "evidence": {
                    "provider": "github",
                    "artifact": "pull_request_review",
                    "repository": "autoMBD/autombd-rtd-config",
                    "pull_request_number": 321,
                    "review_id": 654321,
                    "actor_type": "human",
                    "actor_login": "owner",
                    "state": "approved",
                    "current": True,
                    "candidate_sha": _sha("d"),
                },
                "monitor": {
                    "status": "stopped",
                    "interval_minutes": 10,
                    "scope": "current_session",
                    "automation": {
                        "id": "review-monitor-321",
                        "tier": "foreground",
                        "count": 1,
                        "session": "current_session",
                        "backoff_seconds": 10,
                    },
                },
            },
        },
        "counters": {"production_rework": 0, "kpi_optimization": 0},
        "tester": {"status": "pass", "candidate_sha": _sha("d")},
        "reviewer": {"status": "pass", "candidate_sha": _sha("d")},
        "permission_preflight": {
            "host": {"available": True, "fact": "github_authenticated"},
            "sandbox": {"available": True, "fact": "network_permitted"},
            "required_capabilities": ["read_issue", "read_review"],
            "granted_capabilities": ["read_issue", "read_review"],
            "hydration": {
                "mode": "noninteractive",
                "source": "verified_non_secret_inputs",
            },
        },
        "authorization": {
            "github": {"authorized_human_logins": ["owner"]}
        },
        "exception": None,
    }


def _errors(record: dict) -> list[str]:
    module = _gate_module()
    result = module.validate_record(record)
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
    return result


def _assert_error(record: dict, expected: str) -> None:
    errors = _errors(record)
    assert any(expected in error.casefold() for error in errors), errors


def _set_path(record: dict, dotted_path: str, value: object) -> None:
    owner = record
    fields = dotted_path.split(".")
    for field in fields[:-1]:
        owner = owner[field]
    owner[fields[-1]] = value


def test_valid_portable_workflow_record_passes():
    assert _errors(_valid_record()) == []


@pytest.mark.parametrize("legacy_marker", (None, "lanes", "transition", "corrections"))
def test_version_1_and_all_legacy_dialects_have_one_stable_rejection(
    legacy_marker,
):
    record = {"version": 1}
    if legacy_marker is not None:
        record[legacy_marker] = {}

    assert _errors(record) == [UNSUPPORTED_V1]


def test_v2_only_gate_exposes_no_migration_or_normalizer_api():
    module = _gate_module()
    public_migration_api = [
        name
        for name in dir(module)
        if not name.startswith("_")
        and ("migrat" in name.casefold() or "normaliz" in name.casefold())
    ]

    assert public_migration_api == []


@pytest.mark.parametrize("legacy_marker", ("lanes", "transition", "corrections"))
def test_legacy_markers_cannot_bypass_canonical_v2_validation(legacy_marker):
    record = _valid_record()
    record[legacy_marker] = {}
    record["human_reviews"]["final"]["approved"] = False
    record["human_reviews"]["final"]["evidence"] = None

    errors = _errors(record)
    assert errors
    assert any(
        legacy_marker in error and "legacy" in error.casefold()
        for error in errors
    )
    assert any(
        "final human review" in error.casefold()
        or "human_reviews.final" in error
        for error in errors
    )


def test_valid_mechanical_light_path_records_reduced_gate_justification():
    record = {
        "version": 2,
        "schema": "agent_workflow_v2",
        "issue": {
            "number": 654,
            "primary_type": "N",
            "impact_flags": ["DO"],
        },
        "state": "testing",
        "gate": {
            "test_required": False,
            "light_path": {
                "reason": "Only non-normative documentation is renamed.",
                "residual_risk": "A stale link could remain.",
                "remaining_verification": ["link check", "git diff --check"],
            },
        },
        "revisions": {
            "base_sha": _sha("a"),
            "implementation": {
                "identity": "W1",
                "iteration": 1,
                "base_sha": _sha("a"),
                "sha": _sha("c"),
            },
            "candidate": {
                "identity": "C1",
                "iteration": 1,
                "sha": _sha("d"),
                "parents": {
                    "base_sha": _sha("a"),
                    "implementation_sha": _sha("c"),
                },
            },
        },
        "tester": {
            "status": "pending",
            "candidate_sha": _sha("d"),
            "mode": "mechanical_verification",
        },
        "counters": {"production_rework": 0, "kpi_optimization": 0},
        "permission_preflight": {
            "host": {"available": True, "fact": "local_state_available"},
            "sandbox": {"available": True, "fact": "workspace_write"},
            "required_capabilities": [],
            "granted_capabilities": [],
            "hydration": {
                "mode": "noninteractive",
                "source": "verified_non_secret_inputs",
            },
        },
        "authorization": {
            "github": {"authorized_human_logins": ["owner"]}
        },
        "exception": None,
    }

    assert _errors(record) == []


@pytest.mark.parametrize(
    "unknown_path",
    (
        "unknown_top",
        "issue.unknown",
        "gate.unknown",
        "revisions.unknown",
        "revisions.test.unknown",
        "revisions.implementation.unknown",
        "revisions.candidate.unknown",
        "revisions.candidate.parents.unknown",
        "revisions.final_evidence.unknown",
        "human_reviews.unknown",
        "human_reviews.test.unknown",
        "human_reviews.test.evidence.unknown",
        "human_reviews.test.monitor.unknown",
        "human_reviews.test.monitor.automation.unknown",
        "human_reviews.final.unknown",
        "human_reviews.final.evidence.unknown",
        "human_reviews.final.monitor.unknown",
        "counters.unknown",
        "tester.unknown",
        "reviewer.unknown",
        "permission_preflight.unknown",
        "permission_preflight.host.unknown",
        "permission_preflight.sandbox.unknown",
        "permission_preflight.hydration.unknown",
        "authorization.unknown",
        "authorization.github.unknown",
        "permission_preflight.timestamp",
        "human_reviews.test.monitor.deadline",
        "human_reviews.test.monitor.automation.timestamp",
    ),
)
def test_canonical_v2_rejects_unknown_fields_at_every_nesting_level(
    unknown_path,
):
    record = _valid_record()
    _set_path(record, unknown_path, True)

    errors = _errors(record)
    assert errors
    assert any(
        unknown_path in error and "unknown" in error.casefold()
        for error in errors
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("primary_type", "X", "primary type"),
        ("impact_flags", ["AR", "UNKNOWN"], "impact flag"),
    ),
)
def test_unknown_class_or_impact_flag_is_rejected(field, value, expected):
    record = _valid_record()
    record["issue"][field] = value

    _assert_error(record, expected)


def test_implementation_requires_human_review_1_on_frozen_test_sha():
    record = _valid_record()
    record["state"] = "implementing"
    del record["revisions"]["candidate"]
    del record["revisions"]["final_evidence"]
    record["revisions"]["implementation"]["sha"] = None
    del record["tester"]
    del record["reviewer"]
    del record["human_reviews"]["final"]
    record["human_reviews"]["test"] = {
        "approved": False,
        "sha": _sha("b"),
        "reviewer": None,
    }

    _assert_error(record, "human_reviews.test.evidence")


@pytest.mark.parametrize(
    ("mutate", "expected"),
    (
        (
            lambda record: record["human_reviews"]["test"]["evidence"].update(
                command=f"/approve-test {_sha('e')}"
            ),
            "human_reviews.test.evidence.command",
        ),
        (
            lambda record: record["human_reviews"]["test"]["evidence"].pop(
                "comment_id"
            ),
            "human_reviews.test.evidence.comment_id",
        ),
    ),
)
def test_human_review_1_requires_github_comment_bound_to_test_sha(
    mutate, expected
):
    record = _valid_record()
    mutate(record)

    _assert_error(record, expected)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    (
        (
            lambda record: record["human_reviews"]["test"]["monitor"].update(
                status="active"
            ),
            "human_reviews.test.monitor.status",
        ),
        (
            lambda record: record["human_reviews"]["test"]["monitor"].update(
                interval_minutes=5
            ),
            "human_reviews.test.monitor.interval_minutes",
        ),
        (
            lambda record: record["human_reviews"]["test"]["monitor"].update(
                scope="new_session"
            ),
            "human_reviews.test.monitor.scope",
        ),
    ),
)
def test_approved_human_review_requires_stopped_same_session_monitor(
    mutate, expected
):
    record = _valid_record()
    mutate(record)

    _assert_error(record, expected)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    (
        (
            lambda record: record["revisions"]["test"].update(sha="short"),
            "revisions.test.sha",
        ),
        (
            lambda record: record["revisions"]["implementation"].update(
                base_sha=_sha("e")
            ),
            "revisions.implementation.base_sha",
        ),
        (
            lambda record: record["human_reviews"]["test"].update(sha=_sha("e")),
            "human_reviews.test.sha",
        ),
    ),
)
def test_malformed_or_cross_field_mismatched_revision_shas_are_rejected(
    mutate, expected
):
    record = _valid_record()
    mutate(record)

    _assert_error(record, expected)


@pytest.mark.parametrize(
    "counter",
    (
        "production_rework",
        "kpi_optimization",
    ),
)
def test_fourth_bounded_iteration_is_rejected(counter):
    record = _valid_record()
    record["counters"][counter] = 4

    _assert_error(record, f"counters.{counter}")


@pytest.mark.parametrize(
    "missing_field",
    ("reason", "residual_risk", "remaining_verification"),
)
def test_exception_requires_complete_justification(missing_field):
    record = _valid_record()
    record["exception"] = {
        "reason": "The normal gate cannot run.",
        "residual_risk": "A platform-specific behavior remains unchecked.",
        "remaining_verification": ["deterministic contract tests"],
    }
    del record["exception"][missing_field]

    _assert_error(record, f"exception.{missing_field}")


def test_reviewer_cannot_pass_before_tester_is_green():
    record = _valid_record()
    record["state"] = "reviewing"
    record["tester"]["status"] = "fail"

    _assert_error(record, "tester.status")


def test_candidate_evidence_is_invalidated_by_a_different_candidate_sha():
    record = _valid_record()
    record["tester"]["candidate_sha"] = _sha("e")

    _assert_error(record, "candidate_sha")


def test_complete_state_requires_final_human_review_on_candidate():
    record = _valid_record()
    record["state"] = "complete"
    record["human_reviews"]["final"] = {
        "approved": False,
        "sha": _sha("d"),
        "reviewer": None,
    }

    _assert_error(record, "human_reviews.final.approved")


def test_validator_does_not_mutate_the_workflow_record():
    record = _valid_record()
    before = copy.deepcopy(record)

    _errors(record)

    assert record == before
