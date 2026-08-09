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
# File:        workflow_gate.py
# Author:      TkungL <tkung.lqk@foxmail.com>
# Date:        2026-08-03
# Version:     0.1.0
# Description: Validate the closed P0 agent workflow contract and evidence.
# =================================================================================

"""Small, fail-closed validators for the P0 agent workflow evidence model."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any
from urllib.parse import unquote, urlparse


class WorkflowValidationError(Exception):
    """Raised when workflow evidence violates the committed contract."""


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_CONTRACT_KEYS = {
    "contract_version", "issue_classes", "impact_flags", "strict_route",
    "checkpoints", "execution_statuses", "verdicts", "finding_classes",
    "dispositions", "requirement_ids", "candidate_attempt", "record_fields",
    "object_fields", "preflight_item_statuses", "finding_sources",
    "role_permissions",
}
_OBJECT_FIELD_KEYS = {
    "contract", "issue", "classification", "preflight", "preflight_item",
    "authority", "human_review_1", "candidate", "tester", "reviewer",
    "finding", "freeze_viability", "draft_pr", "final_human_review",
    "attempt", "blocker", "lane_manifest",
}
_ROLE_KEYS = {"orchestrator", "explorer", "worker", "tester", "reviewer", "human"}
_CLEARANCE_KEYS = (
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
)
_CHECKPOINT_EVIDENCE = (
    ("test_approved", "human_review_1"),
    ("candidate_built", "candidate"),
    ("tester_passed", "tester"),
    ("reviewer_accepted", "reviewer"),
    ("draft_pr_ready", "draft_pr"),
    ("complete", "final_human_review"),
)


def _error(message: str) -> None:
    raise WorkflowValidationError(message)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _error(message)


def _closed_object(value: Any, fields: list[str], label: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{label} must be an object")
    expected = set(fields)
    actual = set(value)
    _require(actual == expected, f"{label} fields must be exactly {fields}")
    return value


def _checkpoint_object(
    record: dict[str, Any],
    contract: dict[str, Any],
    evidence_name: str,
) -> dict[str, Any] | None:
    checkpoint_by_evidence = {
        evidence: checkpoint for checkpoint, evidence in _CHECKPOINT_EVIDENCE
    }
    evidence_checkpoint = checkpoint_by_evidence[evidence_name]
    checkpoints = contract["checkpoints"]
    generated = checkpoints.index(record["checkpoint"]) >= checkpoints.index(evidence_checkpoint)
    evidence = record[evidence_name]
    if not generated:
        _require(evidence is None, f"record.{evidence_name} must be null before {evidence_checkpoint}")
        return None
    return _closed_object(
        evidence,
        contract["object_fields"][evidence_name],
        f"record.{evidence_name}",
    )


def _string(value: Any, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{label} must be a non-empty string")
    return value


def _sha(value: Any, label: str) -> str:
    _require(isinstance(value, str) and _SHA_RE.fullmatch(value) is not None, f"{label} must be a full lowercase commit SHA")
    return value


def _unique_strings(value: Any, label: str, *, length: int | None = None) -> list[str]:
    _require(isinstance(value, list), f"{label} must be a list")
    _require(all(isinstance(item, str) and item for item in value), f"{label} must contain non-empty strings")
    _require(len(value) == len(set(value)), f"{label} must not contain duplicates")
    if length is not None:
        _require(len(value) == length, f"{label} must contain exactly {length} values")
    return value


def _blob_sha(data: bytes) -> str:
    data = data.replace(b"\r\n", b"\n")
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _read_contract(contract_path: Any) -> tuple[dict[str, Any], bytes]:
    data = Path(contract_path).read_bytes()
    value = json.loads(data.decode("utf-8"))
    _require(isinstance(value, dict), "contract JSON must contain an object")
    return value, data


def validate_contract(contract, *, contract_path):
    """Validate a contract object against the authoritative committed JSON path."""
    authoritative, _ = _read_contract(contract_path)
    _require(contract == authoritative, "contract object differs from contract_path")
    _require(set(contract) == _CONTRACT_KEYS, "contract top-level fields are not closed")
    _require(_is_int(contract["contract_version"]) and contract["contract_version"] == 1, "contract_version must be 1")
    _unique_strings(contract["issue_classes"], "issue_classes", length=7)
    _unique_strings(contract["impact_flags"], "impact_flags", length=9)
    for name in (
        "strict_route", "checkpoints", "execution_statuses", "verdicts",
        "finding_classes", "dispositions", "requirement_ids",
        "record_fields", "preflight_item_statuses", "finding_sources",
    ):
        _unique_strings(contract[name], name)
    _require(len(contract["strict_route"]) == 12, "strict_route must record all twelve stages")
    _require(contract["requirement_ids"] == [f"P0-{number:02d}" for number in range(1, 19)], "requirement_ids must be the ordered P0 set")
    attempt = _closed_object(contract["candidate_attempt"], ["minimum", "maximum"], "candidate_attempt")
    _require(attempt == {"minimum": 1, "maximum": 3}, "candidate_attempt bounds must be 1..3")
    object_fields = contract["object_fields"]
    _require(isinstance(object_fields, dict) and set(object_fields) == _OBJECT_FIELD_KEYS, "object_fields is not closed")
    for name, fields in object_fields.items():
        _unique_strings(fields, f"object_fields.{name}")
    for checkpoint, evidence_name in _CHECKPOINT_EVIDENCE:
        _require(checkpoint in contract["checkpoints"], f"checkpoint {checkpoint} is missing")
        _require(evidence_name in object_fields, f"object_fields.{evidence_name} is missing")
    permissions = contract["role_permissions"]
    _require(isinstance(permissions, dict) and set(permissions) == _ROLE_KEYS, "role_permissions is not closed")
    for name, values in permissions.items():
        _unique_strings(values, f"role_permissions.{name}")


def _contract_context(contract_path: Any) -> tuple[dict[str, Any], str]:
    contract, data = _read_contract(contract_path)
    validate_contract(contract, contract_path=contract_path)
    return contract, _blob_sha(data)


def _repo_identity(repository: str) -> tuple[str, str, str]:
    value = repository.strip().rstrip("/")
    parsed = urlparse(value if "://" in value else "https://github.com/" + value)
    parts = [part for part in parsed.path.split("/") if part]
    _require(bool(parsed.hostname) and len(parts) >= 2, "issue.repository must identify a repository host and owner/name")
    return parsed.hostname.lower(), parts[0], parts[1].removesuffix(".git")


def _top_level_comment(url: Any, repository: str, issue_number: int, label: str) -> str:
    value = _string(url, label)
    parsed = urlparse(value)
    host, owner, name = _repo_identity(repository)
    _require(parsed.scheme == "https" and (parsed.hostname or "").lower() == host, f"{label} must use the repository host")
    issue_path = f"/{owner}/{name}/issues/{issue_number}"
    _require(parsed.path.rstrip("/") == issue_path, f"{label} must identify the top-level issue discussion")
    _require(re.fullmatch(r"issuecomment-[1-9][0-9]*", parsed.fragment) is not None, f"{label} must identify a top-level comment")
    return value


def _valid_hostname(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass
    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    labels = ascii_hostname.split(".")
    legacy_ipv4 = 1 <= len(labels) <= 4 and all(
        re.fullmatch(r"(?:[0-9]+|0[xX][0-9A-Fa-f]+)", item) is not None
        for item in labels
    )
    if len(ascii_hostname) > 253 or legacy_ipv4:
        return False
    return all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", item)
        is not None
        for item in labels
    )


def _https_url(url: Any, label: str) -> str:
    value = _string(url, label)
    message = f"{label} must be an unambiguous absolute HTTPS URL"
    _require(re.search(r"%(?![0-9A-Fa-f]{2})", value) is None, message)
    try:
        decoded_value = unquote(value, errors="strict")
    except UnicodeDecodeError:
        _error(message)
    _require(
        "#" not in value
        and not any(
            ord(character) < 32
            or 127 <= ord(character) <= 159
            or character == "\\"
            or character.isspace()
            for character in decoded_value
        ),
        message,
    )
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        parsed.port
    except ValueError:
        _error(message)
    _require(
        parsed.scheme == "https"
        and hostname is not None
        and _valid_hostname(hostname)
        and parsed.username is None
        and parsed.password is None,
        message,
    )
    return value


def _preflight_item(item: Any, contract: dict[str, Any], label: str) -> str:
    fields = contract["object_fields"]
    value = _closed_object(item, fields["preflight_item"], label)
    _string(value["name"], f"{label}.name")
    _string(value["evidence"], f"{label}.evidence")
    _require(value["status"] in contract["preflight_item_statuses"], f"{label}.status is not allowed")
    return value["status"]


def _validate_finding(finding: Any, contract: dict[str, Any], index: int) -> None:
    fields = contract["object_fields"]
    label = f"findings[{index}]"
    value = _closed_object(finding, fields["finding"], label)
    _string(value["id"], f"{label}.id")
    _require(value["source"] in contract["finding_sources"], f"{label}.source must be Tester or Reviewer semantics")
    _require(value["class"] in contract["finding_classes"], f"{label}.class is not allowed")
    _require(value["requirement_id"] in contract["requirement_ids"], f"{label}.requirement_id is not allowed")
    for name in ("evidence", "observed", "expected"):
        _string(value[name], f"{label}.{name}")
    finding_class = value["class"]
    if finding_class == "F2":
        viability = _closed_object(value["freeze_viability"], fields["freeze_viability"], f"{label}.freeze_viability")
        _require(all(type(item) is bool for item in viability.values()), f"{label}.freeze_viability values must be booleans")
    else:
        _require(value["freeze_viability"] is None, f"{label}.freeze_viability must be null outside F2")
        viability = None
    disposition = value["disposition"]
    _require(disposition in contract["dispositions"], f"{label}.disposition is not allowed")
    if finding_class == "F0":
        _require(disposition in {"BLOCK", "STOP"}, "F0 must BLOCK or STOP and cannot freeze")
    elif finding_class == "F1":
        _require(disposition == "REWORK_CURRENT_STAGE", "F1 must rework the current stage")
    elif finding_class == "F2":
        expected = "FREEZE_FOR_NEXT_STAGE" if all(viability.values()) else None
        if expected is None:
            _require(disposition in {"BLOCK", "STOP"}, "non-viable F2 must BLOCK or STOP")
        else:
            _require(disposition == expected, "fully viable F2 must freeze for the next stage")
    else:
        _require(disposition == "DEFER_NON_BLOCKING", "F3/F4 may only defer non-blocking")


def validate_record(record, *, contract_path):
    """Validate one closed P0 workflow record against the authoritative contract."""
    contract, contract_blob_sha = _contract_context(contract_path)
    fields = contract["object_fields"]
    value = _closed_object(record, contract["record_fields"], "record")

    contract_ref = _closed_object(value["contract"], fields["contract"], "record.contract")
    _require(contract_ref["version"] == contract["contract_version"], "record contract version does not match")
    _require(contract_ref["blob_sha"] == contract_blob_sha, "record contract blob SHA does not match")

    issue = _closed_object(value["issue"], fields["issue"], "record.issue")
    repository = _string(issue["repository"], "record.issue.repository")
    _require(_is_int(issue["number"]) and issue["number"] > 0, "record.issue.number must be positive")
    _string(issue["title"], "record.issue.title")

    classification = _closed_object(value["classification"], fields["classification"], "record.classification")
    _require(classification["issue_class"] in contract["issue_classes"], "issue_class is not allowed")
    flags = _unique_strings(classification["impact_flags"], "impact_flags")
    _require(all(flag in contract["impact_flags"] for flag in flags), "impact_flags contains an unknown flag")
    canonical_flags = [flag for flag in contract["impact_flags"] if flag in flags]
    _require(flags == canonical_flags, "impact_flags must follow the canonical contract order")
    _require(classification["route"] == contract["strict_route"], "route must record the strict route exactly; it is not inferred")
    _require(value["checkpoint"] in contract["checkpoints"], "checkpoint is not allowed")
    _require(value["execution_status"] in contract["execution_statuses"], "execution_status is not allowed")

    preflight = _closed_object(value["preflight"], fields["preflight"], "record.preflight")
    statuses = []
    for group in ("permissions", "dependencies", "tools"):
        _require(isinstance(preflight[group], list), f"record.preflight.{group} must be a list")
        statuses.extend(_preflight_item(item, contract, f"record.preflight.{group}[{index}]") for index, item in enumerate(preflight[group]))
    expected_preflight = "blocked" if "blocked" in statuses else "available"
    _require(preflight["result"] == expected_preflight, "preflight result does not match its items")

    blocker = value["blocker"]
    if blocker is not None:
        blocker = _closed_object(blocker, fields["blocker"], "record.blocker")
        for name in fields["blocker"]:
            _string(blocker[name], f"record.blocker.{name}")
    status = value["execution_status"]
    if status == "active":
        _require(expected_preflight == "available" and blocker is None, "active requires available preflight and no blocker")
    elif status == "blocked":
        _require(expected_preflight == "blocked" and blocker is not None, "blocked requires blocked preflight and blocker evidence")
    else:
        _require(blocker is not None, "stopped requires blocker evidence")

    authority = _closed_object(value["authority"], fields["authority"], "record.authority")
    for name in ("base_sha", "test_sha", "implementation_sha"):
        _sha(authority[name], f"record.authority.{name}")
    _require(len({authority["base_sha"], authority["test_sha"], authority["implementation_sha"]}) == 3, "authority commit identities must be distinct")
    reviewer_actor = _string(authority["authorized_reviewer"], "record.authority.authorized_reviewer")

    review_1 = _checkpoint_object(value, contract, "human_review_1")
    if review_1 is not None:
        _require(review_1["actor"] == reviewer_actor, "Human Review 1 actor is not authorized")
        _top_level_comment(review_1["comment_url"], repository, issue["number"], "record.human_review_1.comment_url")
        _sha(review_1["test_sha"], "record.human_review_1.test_sha")
        _require(review_1["test_sha"] == authority["test_sha"], "Human Review 1 is not bound to the full Test SHA")
        _require(review_1["command"] == f"/approve-test {authority['test_sha']}", "Human Review 1 command is not the exact approval command")
        _require(review_1["edited"] is False and review_1["deleted"] is False, "Human Review 1 evidence must be unedited and undeleted")

    candidate = _checkpoint_object(value, contract, "candidate")
    candidate_sha = None
    if candidate is not None:
        candidate_sha = _sha(candidate["sha"], "record.candidate.sha")
        _require(candidate["parent_test_sha"] == authority["test_sha"], "Candidate Test parent identity does not match")
        _require(candidate["parent_implementation_sha"] == authority["implementation_sha"], "Candidate Implementation parent identity does not match")
        _sha(candidate["parent_test_sha"], "record.candidate.parent_test_sha")
        _sha(candidate["parent_implementation_sha"], "record.candidate.parent_implementation_sha")

    tester = _checkpoint_object(value, contract, "tester")
    if tester is not None:
        _require(tester["candidate_sha"] == candidate_sha, "Tester verdict is stale")
        _require(tester["verdict"] == "PASS", "tester_passed checkpoint requires Tester PASS")
        _string(tester["evidence"], "record.tester.evidence")
    reviewer = _checkpoint_object(value, contract, "reviewer")
    if reviewer is not None:
        _require(reviewer["candidate_sha"] == candidate_sha, "Reviewer verdict is stale")
        _require(reviewer["verdict"] == "PASS", "reviewer_accepted checkpoint requires Reviewer PASS")
        _string(reviewer["evidence"], "record.reviewer.evidence")
        _require(tester["verdict"] == "PASS", "Reviewer may run only after Tester PASS on the current Candidate")

    findings = value["findings"]
    _require(isinstance(findings, list), "record.findings must be a list")
    for index, finding in enumerate(findings):
        _validate_finding(finding, contract, index)

    draft_pr = _checkpoint_object(value, contract, "draft_pr")
    if draft_pr is not None:
        _https_url(draft_pr["url"], "record.draft_pr.url")
        _require(draft_pr["candidate_sha"] == candidate_sha, "Draft PR is not bound to the current Candidate")
        _require(draft_pr["is_draft"] is True, "workflow PR must remain a draft")
        _require(reviewer["verdict"] == "PASS", "Draft PR requires Reviewer PASS on the current Candidate")

    final_review = _checkpoint_object(value, contract, "final_human_review")
    if final_review is not None:
        _string(final_review["actor"], "record.final_human_review.actor")
        _https_url(final_review["comment_url"], "record.final_human_review.comment_url")
        _string(final_review["decision"], "record.final_human_review.decision")
        _require(final_review["candidate_sha"] == candidate_sha, "Final Human Review is not bound to the current Candidate")

    attempt = _closed_object(value["attempt"], fields["attempt"], "record.attempt")
    candidate_attempt = attempt["candidate_attempt"]
    bounds = contract["candidate_attempt"]
    _require(_is_int(candidate_attempt) and bounds["minimum"] <= candidate_attempt <= bounds["maximum"], "candidate_attempt must be an integer in the contracted range")
    _require(value["bootstrap_stage"] == "P0", "bootstrap_stage must be P0")


def _validate_manifest(manifest: Any, contract: dict[str, Any], contract_blob_sha: str, label: str) -> dict[str, Any]:
    value = _closed_object(manifest, contract["object_fields"]["lane_manifest"], label)
    _require(value["contract_version"] == contract["contract_version"], f"{label}.contract_version does not match")
    _require(value["contract_blob_sha"] == contract_blob_sha, f"{label}.contract_blob_sha does not match")
    _sha(value["base_sha"], f"{label}.base_sha")
    _sha(value["lane_sha"], f"{label}.lane_sha")
    _require(value["lane_sha"] != value["base_sha"], f"{label}.lane_sha must differ from base_sha")
    _require(value["requirement_ids"] == contract["requirement_ids"], f"{label}.requirement_ids must match exactly")
    return value


def validate_lane_manifests(test_manifest, implementation_manifest, *, contract_path):
    """Validate the two closed lane manifests and their shared identities."""
    contract, blob_sha = _contract_context(contract_path)
    test = _validate_manifest(test_manifest, contract, blob_sha, "test_manifest")
    implementation = _validate_manifest(implementation_manifest, contract, blob_sha, "implementation_manifest")
    _require(test["base_sha"] == implementation["base_sha"], "lane manifests must share the exact base SHA")
    _require(test["lane_sha"] != implementation["lane_sha"], "Test and Implementation lane SHAs must differ")


def _git(repository: Path, *arguments: str, text: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=repository, check=True,
            capture_output=True, text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None)
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        _error(f"git evidence check failed: {(detail or str(exc)).strip()}")


def _deployment_sources(repository: Path, deployment_paths: Any) -> tuple[tuple[str, ...], tuple[Path, ...]]:
    _require(not isinstance(deployment_paths, (str, bytes)) and hasattr(deployment_paths, "__iter__"), "deployment_paths must be an iterable of paths")
    prefixes = []
    external = []
    root = repository.resolve()
    for supplied in deployment_paths:
        path = Path(supplied)
        if path.is_absolute():
            resolved = path.resolve()
            try:
                path = resolved.relative_to(root)
            except ValueError:
                _require(resolved.is_file() or resolved.is_dir(), "external deployment path must exist")
                external.append(resolved)
                continue
        pure = PurePosixPath(path.as_posix())
        _require(not pure.is_absolute() and ".." not in pure.parts, "deployment path must stay within the repository")
        normalized = pure.as_posix().rstrip("/")
        prefixes.append("" if normalized in ("", ".") else normalized)
    return tuple(prefixes), tuple(external)


def _is_deployment_file(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(not prefix or path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _bootstrap_patterns() -> dict[str, re.Pattern[str]]:
    boot = "boot" + "strap"
    p0 = "p" + "0"
    agent = "ag" + "ent"
    workflow = "work" + "flow"
    design_word = "de" + "sign"
    test_word = "te" + "st"
    strategy = "stra" + "tegy"
    temporary = "tempo" + "rary"
    remove = "remo" + "ve"
    delete = "dele" + "te"
    drop = "dr" + "op"
    before = "be" + "fore"
    final = "fi" + "nal"
    after = "af" + "ter"
    debt_word = "de" + "bt"
    evidence = "evi" + "dence"
    pointer = "poin" + "ter"
    open_word = "op" + "en"
    gap = r"[-_/ ]+"
    reference = re.compile(
        rf"(?i)\b(?:"
        rf"{agent}{gap}{workflow}{gap}(?:{boot}{gap})?{design_word}|"
        rf"{agent}{gap}{workflow}{gap}{test_word}{gap}{strategy}|"
        rf"{p0}{gap}{boot}{gap}(?:{workflow}{gap})?{design_word}|"
        rf"{boot}{gap}{test_word}{gap}{strategy}"
        rf")\b"
    )
    heading = re.compile(
        rf"(?i)^\s*#{{1,6}}\s+.*(?:"
        rf"\b{temporary}\b.*(?:\b{boot}\b|\b{p0}\b.*\b{agent}\b.*\b{workflow}\b)|"
        rf"\b{p0}\b.*\b{boot}\b"
        rf")"
    )
    removal = re.compile(
        rf"(?i)\b(?:{remove}|{delete}|{drop})\b.*(?:"
        rf"\b{before}\b.*\b{final}\b.*\b{p0}\b|"
        rf"\b{after}\b.*\b(?:{p0}{gap})?{boot}\b"
        rf")"
    )
    debt_id = re.compile(
        rf"(?i)\b(?:{p0}{gap}bs{gap}[0-9]+|"
        rf"{p0}{gap}{boot}{gap}{debt_word}{gap}[0-9]+)\b"
    )
    debt_pointer = re.compile(
        rf"(?i)^(?=.*\b{boot}\b)(?=.*\b(?:{evidence}|{pointer})\b).*$"
    )
    open_debt = re.compile(
        rf"(?i)^(?=.*\b{boot}\b)(?=.*\b{debt_word}\b)(?=.*\b{open_word}\b).*$"
    )
    return {
        "reference": reference,
        "heading": heading,
        "removal": removal,
        "debt_id": debt_id,
        "debt_pointer": debt_pointer,
        "open_debt": open_debt,
    }


def _bootstrap_design_path(path: str) -> bool:
    words = [word for word in re.split(r"[^a-z0-9]+", path.lower()) if word]
    has_bootstrap = "bootstrap" in words or ("boot" in words and "strap" in words)
    category = "design" in words or ("test" in words and "strategy" in words)
    governed_workflow = (
        "agent-discipline" in path.lower().replace("_", "-")
        and "agent" in words
        and "workflow" in words
    )
    return category and (has_bootstrap or governed_workflow)


def _governance_path(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    words = set(word for word in re.split(r"[^a-z0-9]+", name) if word)
    return name == "agents.md" or bool(words.intersection({"governance", "contract", "mapping"}))


def _payload_path(path: str) -> bool:
    words = set(word for word in re.split(r"[^a-z0-9]+", path.lower()) if word)
    return bool(words.intersection({"generated", "payload", "release"}))


def _scan_content(path: str, content: str, counts: dict[str, int], *, payload: bool) -> None:
    patterns = _bootstrap_patterns()
    references = len(patterns["reference"].findall(content))
    counts[_CLEARANCE_KEYS[1]] += references
    if _governance_path(path):
        counts[_CLEARANCE_KEYS[2]] += references
    residue = references > 0
    for line in content.splitlines():
        if patterns["heading"].search(line):
            counts[_CLEARANCE_KEYS[5]] += 1
            residue = True
        if patterns["removal"].search(line):
            counts[_CLEARANCE_KEYS[6]] += 1
            residue = True
        identifiers = patterns["debt_id"].findall(line)
        counts[_CLEARANCE_KEYS[7]] += len(identifiers)
        residue = residue or bool(identifiers)
        if patterns["debt_pointer"].search(line):
            counts[_CLEARANCE_KEYS[8]] += 1
            residue = True
        if patterns["open_debt"].search(line):
            counts[_CLEARANCE_KEYS[9]] += 1
            residue = True
    if payload and residue:
        counts[_CLEARANCE_KEYS[3]] += 1


def _external_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*") if item.is_file())


def _candidate_blobs(repository: Path, candidate: str) -> list[tuple[str, bytes]]:
    tree_output = _git(repository, "ls-tree", "-r", "--full-tree", "-z", candidate, text=False).stdout
    entries = []
    for raw_entry in tree_output.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        parts = metadata.split(b" ")
        _require(separator == b"\t" and len(parts) == 3, "git tree entry is malformed")
        _, object_type, object_id = parts
        if object_type == b"blob":
            entries.append((raw_path.decode("utf-8", errors="surrogateescape"), object_id))

    if not entries:
        return []
    try:
        result = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=repository,
            check=True,
            input=b"".join(object_id + b"\n" for _, object_id in entries),
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None)
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", errors="replace")
        _error(f"git evidence check failed: {(detail or str(exc)).strip()}")

    offset = 0
    blobs = []
    output = result.stdout
    for (path, expected_id) in entries:
        header_end = output.find(b"\n", offset)
        _require(header_end >= 0, "git cat-file batch header is missing")
        header = output[offset:header_end].split(b" ")
        _require(len(header) == 3, "git cat-file batch header is malformed")
        object_id, object_type, raw_size = header
        _require(object_id == expected_id and object_type == b"blob", "git cat-file returned the wrong object")
        _require(raw_size.isascii() and raw_size.isdigit(), "git cat-file returned an invalid blob size")
        try:
            size = int(raw_size)
        except ValueError:
            _error("git cat-file returned an invalid blob size")
        content_start = header_end + 1
        content_end = content_start + size
        _require(content_end < len(output) and output[content_end:content_end + 1] == b"\n", "git cat-file blob is truncated")
        blobs.append((path, output[content_start:content_end]))
        offset = content_end + 1
    _require(offset == len(output), "git cat-file returned unexpected trailing output")
    return blobs


def audit_bootstrap_clearance(repository_path, candidate_sha, deployment_paths, bootstrap_document_commits):
    """Audit only a Candidate commit tree and fail when bootstrap residue remains."""
    repository = Path(repository_path)
    _require(repository.is_dir(), "repository_path must be a directory")
    candidate = _sha(candidate_sha, "candidate_sha")
    _git(repository, "cat-file", "-e", f"{candidate}^{{commit}}")
    prefixes, external_paths = _deployment_sources(repository, deployment_paths)
    blobs = _candidate_blobs(repository, candidate)
    paths = [path for path, _ in blobs]

    counts = {key: 0 for key in _CLEARANCE_KEYS}
    counts[_CLEARANCE_KEYS[0]] = sum(_bootstrap_design_path(path) for path in paths)
    for path, blob in blobs:
        content = blob.decode("utf-8", errors="ignore")
        _scan_content(
            path,
            content,
            counts,
            payload=_is_deployment_file(path, prefixes) or _payload_path(path),
        )
    for external_path in external_paths:
        for file_path in _external_files(external_path):
            relative = file_path.name if external_path.is_file() else file_path.relative_to(external_path).as_posix()
            if _bootstrap_design_path(relative):
                counts[_CLEARANCE_KEYS[0]] += 1
            try:
                content = file_path.read_bytes().decode("utf-8", errors="ignore")
            except OSError as exc:
                _error(f"cannot read external deployment content: {exc}")
            _scan_content(relative, content, counts, payload=True)

    _require(not isinstance(bootstrap_document_commits, (str, bytes)) and hasattr(bootstrap_document_commits, "__iter__"), "bootstrap_document_commits must be an iterable of SHAs")
    for commit in bootstrap_document_commits:
        document_commit = _sha(commit, "bootstrap_document_commit")
        _git(repository, "cat-file", "-e", f"{document_commit}^{{commit}}")
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", document_commit, candidate],
            cwd=repository, capture_output=True, text=True,
        )
        _require(result.returncode in (0, 1), "git ancestry check failed")
        if result.returncode == 0:
            counts[_CLEARANCE_KEYS[4]] += 1
    if any(counts.values()):
        _error("bootstrap clearance failed: " + json.dumps(counts, separators=(",", ":")))
    return counts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate P0 agent workflow evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a workflow record")
    validate.add_argument("--contract", required=True)
    validate.add_argument("--record", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        contract_path = Path(args.contract)
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        record = json.loads(Path(args.record).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    try:
        validate_contract(contract, contract_path=contract_path)
        validate_record(record, contract_path=contract_path)
    except WorkflowValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 1
    print("workflow validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
