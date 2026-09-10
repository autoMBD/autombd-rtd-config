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
# File:        test_reviewer_lessons.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Focused W4 Reviewer lesson lineage and compatibility regressions.
# =================================================================================

import copy
import json
import tempfile
from pathlib import Path

import pytest

from workflow_transition_generality_support import History, ROOT, digest
from workflow_evidence_generality_support import EvidenceHistory
from structured_handoff_fixture import Lifecycle
import workflow_transition as transition
import workflow_gate
import repair_protocol
from workflow_transition_wire import protocol

LESSONS = "agent-discipline/agent-lessons-learned.md"
CAPABILITY = {"version": "1.0", "path": LESSONS, "append_only": True}


def contract(version=4):
    value = json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text("utf-8"))
    value["contract_version"] = version
    value.pop("reviewer_lessons", None)
    value["lifecycle"]["pr_head"] = "accepted_candidate"
    if version == 4:
        value["reviewer_lessons"] = copy.deepcopy(CAPABILITY)
        value["lifecycle"]["pr_head"] = "reviewer_lesson_commit"
    if version == 2:
        value.pop("non_case_repairs", None)
    return value


def pure_history(outcome="PASS", version=4, candidate=True):
    h = History(transition, "oak-lessons")
    h.context["protocol"]["workflow_contract"] = contract(version)
    if candidate:
        h.assembled()
        h.result(outcome)
        h.review("TESTER_PASS" if outcome == "PASS" else outcome)
    else:
        h.start()
        h.stop()
        h.review("HUMAN_STOP")
    return h


def report(h, with_field=True):
    p = h.body(h.state["review"]["launch"])["payload"]
    body = {"dispatch_id": p["dispatch_id"], "review_id": p["review_id"], "verdict": "APPROVED"}
    if with_field:
        body["lesson_commit"] = h.tip("lesson", [p["candidate"]["commit"]]) if p["candidate"] else None
    return h.make("reviewer-report", body, [h.state["review"]["launch"]])


@pytest.mark.parametrize("version", [2, 3, 4])
def test_supported_contracts_keep_explicit_version_semantics(version):
    h = History(transition, "contract")
    h.context["protocol"]["workflow_contract"] = contract(version)
    protocol(h.context)
    workflow_gate._validate_v2_contract(contract(version))


def test_active_contract_opts_in_to_lesson_children():
    assert json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text("utf-8")) == contract(4)


@pytest.mark.parametrize("schema_version", [1, True, "2"])
def test_standalone_lesson_capability_requires_exact_schema_version(schema_version):
    value = contract()
    value["schema_version"] = schema_version
    with pytest.raises(repair_protocol.RepairError):
        repair_protocol.require_capability(value, {"artifact_kind": "reviewer-report", "payload": {"lesson_commit": None}})


@pytest.mark.parametrize("outcome", ["PASS", "CONTRACT_INVALID"])
def test_pure_terminal_preserves_c_and_l_without_extra_execution(outcome):
    h = pure_history(outcome)
    previous = copy.deepcopy(h.state["candidate"])
    rr = h.consume(report(h))
    terminal = h.terminal("OPEN_SUCCESS_PR" if outcome == "PASS" else "RECORD_FAILURE")
    assert h.state["candidate"] == previous
    p = h.body(terminal)["payload"]
    assert p["accepted_candidate"] == (h.body(previous["envelope"])["payload"]["candidate"]["commit"] if outcome == "PASS" else None)
    assert h.body(rr)["payload"]["lesson_commit"]["parents"] == [h.body(previous["envelope"])["payload"]["candidate"]["commit"]]


@pytest.mark.parametrize("fault", ["missing", "null", "parent", "extra_parent"])
def test_pure_report_rejects_missing_or_wrong_lineage(fault):
    h = pure_history()
    ref = report(h, fault != "missing")
    p = h.body(ref)["payload"]
    if fault == "null":
        p["lesson_commit"] = None
    elif fault == "parent":
        p["lesson_commit"]["parents"] = [h.governor["commit"]]
    elif fault == "extra_parent":
        p["lesson_commit"]["parents"].append(h.governor["commit"])
    ref["sha256"] = digest(h.body(ref))
    with pytest.raises(transition.WorkflowTransitionError):
        h.consume(ref)


@pytest.mark.parametrize("version", [2, 3])
def test_legacy_report_accepts_old_shape_and_rejects_extension(version):
    h = pure_history(version=version)
    ref = report(h)
    with pytest.raises(transition.WorkflowTransitionError):
        h.consume(ref)
    h.consume(report(h, False))


def test_early_stop_requires_explicit_null_lesson_commit():
    h = pure_history(candidate=False)
    h.consume(report(h))
    h.terminal("RECORD_FAILURE")


def test_metadata_repair_cannot_swap_lesson_commit():
    h = pure_history()
    original = h.body(report(h))
    replacement = copy.deepcopy(original)
    replacement["payload"]["lesson_commit"] = h.tip("swapped")
    with pytest.raises(repair_protocol.RepairError):
        repair_protocol.validate_metadata_replacement(original, replacement)


@pytest.mark.parametrize("version", [3, 4])
def test_repair_manifest_requires_exact_pinned_version(version):
    artifact = {"governor": {"commit": "a" * 40, "workflow_contract_blob": "b" * 40}}
    manifest = {"contract_version": version, "base_sha": "a" * 40,
                "contract_blob_sha": "b" * 40, "lane_sha": "c" * 40, "requirement_ids": ["R"]}
    repair_protocol._manifest(manifest, "c" * 40, artifact, ["R"], version)
    manifest["contract_version"] = 7 - version
    with pytest.raises(repair_protocol.RepairError):
        repair_protocol._manifest(manifest, "c" * 40, artifact, ["R"], version)


@pytest.mark.parametrize("version", [3, 4])
@pytest.mark.parametrize("drift", [False, True])
def test_support_repair_reducer_uses_pinned_manifest_version(version, drift):
    from test_handoff_repair_reducer import RepairHistory, support_artifact, snapshot
    h = RepairHistory(transition, "versioned-support")
    h.context["protocol"]["workflow_contract"] = contract(version)
    h.start()
    for lane in ("test", "worker"):
        h.launch(lane)
        h.ready(lane)
    h.approve()
    ref = support_artifact(h)
    if drift:
        p = h.body(ref)["payload"]
        mapping = next(c for c in p["attachment_changes"] if c["field"] == "test_manifest")
        manifest = json.loads(mapping["after"]["raw"])
        manifest["contract_version"] = 7 - version
        mapping["after"] = snapshot(h, "cross-version", manifest, "manifest")
        mapping["changed_fields"] = repair_protocol.changed_fields(json.loads(mapping["before"]["raw"]), manifest)
        p["test_manifest"] = mapping["after"]["ref"]
        ref["sha256"] = digest(h.body(ref))
        with pytest.raises(transition.WorkflowTransitionError):
            h.consume(ref)
    else:
        h.consume(ref)
        assert h.state["repairs"] == [ref]


@pytest.mark.parametrize("kind", ["reviewer-report", "human-decision"])
@pytest.mark.parametrize("drift", [False, True])
def test_consumed_metadata_replacement_retains_lesson_and_final_identity(kind, drift):
    from test_workflow_transition_generality import human_replacement
    h = pure_history()
    reviewed = h.consume(report(h))
    proposal = h.terminal("OPEN_SUCCESS_PR")
    lesson = h.body(reviewed)["payload"]["lesson_commit"]
    if kind == "human-decision":
        original = h.consume(h.make(kind, {"gate": "FINAL", "decision": "APPROVE",
            "subject_sha": lesson["commit"]}, [proposal]))
        changes = {"subject_sha": h.body(h.state["candidate"]["envelope"])["payload"]["candidate"]["commit"]} if drift else {}
    else:
        original = reviewed
        changes = {"lesson_commit": h.tip("swapped-lesson", lesson["parents"])} if drift else {}
    replacement = human_replacement(h, original, **changes)
    if drift:
        with pytest.raises(transition.WorkflowTransitionError):
            h.consume(replacement)
    else:
        h.consume(replacement)
        assert h.state["terminal"] == proposal


class LessonHistory(EvidenceHistory):
    def __init__(self, root):
        super().__init__(root)
        self.context_data["protocol"]["workflow_contract"] = contract()

    def write(self, name, raw):
        if name == "agent-discipline/workflow-contract.json":
            self.git("config", "core.autocrlf", "false")
            Lifecycle.write(self, LESSONS, b"Existing lesson\r\n")
            for filename in ("handoff-v1.schema.json", "functional-development-v1.json"):
                path = "agent-discipline/skills/agent-workflow/schemas/" + filename
                Lifecycle.write(self, path, (ROOT / path).read_bytes())
            return Lifecycle.write(self, name, json.dumps(contract()).encode())
        return Lifecycle.write(self, name, raw)

    def manifest(self, sha):
        return self.evidence("manifest", {"contract_version": 4,
            "contract_blob_sha": self.gov["workflow_contract_blob"], "base_sha": self.g,
            "lane_sha": sha, "requirement_ids": ["R"]})

    def lesson_report(self, fault=None, outcome="PASS"):
        self.assembled()
        tested = self.consume(self.report(outcome))
        terminal = Lifecycle.terminal(self, tested, outcome == "PASS", 0)
        review = self.objects[terminal["artifact_id"]]["payload"]["review"]
        launch = self.objects[review["artifact_id"]]["predecessors"][0]
        if outcome != "PASS":
            self.objects[launch["artifact_id"]]["payload"]["terminal_reason"] = outcome
            launch = self.store(self.objects[launch["artifact_id"]])
            self.objects[review["artifact_id"]]["predecessors"] = [launch]
        self.consume(launch)
        content = "Existing lesson\r\nNew lesson\n"
        if fault == "rewrite":
            content = "Existing lesson\nNew lesson\n"
        self.csha = self.objects[self.c["artifact_id"]]["payload"]["candidate"]["commit"]
        parent = self.g if fault == "parent" else self.csha
        self.l = self.commit(parent, LESSONS, content)
        if fault in ("mixed", "mixed_test"):
            self.git("read-tree", self.l)
            blob = self.git("hash-object", "-w", "--stdin", data=b"mixed production edit")
            path = "tests/gate.py" if fault == "mixed_test" else "src/component.py"
            self.git("update-index", "--cacheinfo", "100644," + blob + "," + path)
            self.l = self.git("commit-tree", self.git("write-tree"), "-p", self.csha, "-m", "mixed")
        if fault == "mode":
            self.git("read-tree", self.l)
            self.git("update-index", "--chmod=+x", LESSONS)
            self.l = self.git("commit-tree", self.git("write-tree"), "-p", self.csha, "-m", "mode")
        if fault == "symlink":
            self.git("read-tree", self.l)
            blob = self.git("hash-object", "-w", "--stdin", data=content.encode())
            self.git("update-index", "--cacheinfo", "120000," + blob + "," + LESSONS)
            self.l = self.git("commit-tree", self.git("write-tree"), "-p", self.csha, "-m", "symlink")
        if fault == "path":
            self.l = self.commit(self.csha, "agent-discipline/other-lessons.md", content)
        if fault == "empty":
            self.l = self.git("commit-tree", self.tip(self.csha)["tree"], "-p", self.csha, "-m", "empty")
        if fault == "gitlink":
            self.git("config", "diff.ignoreSubmodules", "all")
            self.git("read-tree", self.l)
            self.git("update-index", "--add", "--cacheinfo", "160000," + self.g + ",external/dependency")
            self.l = self.git("commit-tree", self.git("write-tree"), "-p", self.csha, "-m", "hidden gitlink")
        body = self.objects[review["artifact_id"]]
        body["payload"]["lesson_commit"] = self.tip(self.l)
        body["payload"]["lessons"] = self.evidence("lesson", b"unrelated" if fault == "binding" else content.encode())
        return self.store(body)


@pytest.fixture
def real_history():
    base = ROOT / "tests/.tmp"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reviewer-lessons-", dir=base) as directory:
        yield LessonHistory(Path(directory) / "repo")


@pytest.mark.parametrize("outcome", ["PASS", "CONTRACT_INVALID"])
def test_real_guard_and_source_verifier_accept_append_only_child(real_history, outcome):
    import workflow_evidence
    h = real_history
    ref = h.lesson_report(outcome=outcome)
    code, result = h.validate(ref)
    assert code == 0, result
    h.consume(ref)
    if outcome != "PASS":
        terminal = next(copy.deepcopy(a["payload"]) for a in h.objects.values()
                        if a["artifact_kind"] == "terminal-record")
        terminal["review"] = ref
        terminal = h.artifact("terminal-record", terminal, [ref])
        assert h.validate(terminal)[0] == 0
        h.consume(terminal)
    result = workflow_evidence.verify_evidence(h.state, context=h.context_data,
        repository_root=str(h.root.resolve()), authority=h.authority, github_get=h.get)
    assert result["checks"]["git"] == "PASS"
    assert result["candidate_sha"] == h.csha


@pytest.mark.parametrize("fault", ["parent", "mixed", "mixed_test", "rewrite", "binding", "mode", "symlink", "path", "empty", "gitlink"])
def test_real_guard_rejects_non_append_git_or_wrong_evidence(real_history, fault):
    ref = real_history.lesson_report(fault)
    code, result = real_history.validate(ref)
    assert code != 0, result


@pytest.mark.parametrize("fault", ["mixed", "mixed_test", "rewrite", "binding", "mode", "symlink", "path", "empty", "gitlink"])
def test_source_verifier_independently_rejects_fake_checked_receipt(real_history, fault):
    import workflow_evidence
    h = real_history
    h.consume(h.lesson_report(fault))
    with pytest.raises(workflow_evidence.WorkflowEvidenceError):
        workflow_evidence.verify_evidence(h.state, context=h.context_data,
            repository_root=str(h.root.resolve()), authority=h.authority, github_get=h.get)


def test_missing_lesson_bytes_fail_before_any_git_proof(real_history, monkeypatch):
    import workflow_evidence
    from workflow_evidence_io import EvidenceGraph
    h = real_history
    review = h.lesson_report()
    h.consume(review)
    lesson = h.objects[review["artifact_id"]]["payload"]["lessons"]
    (h.root / lesson["path"]).unlink()
    calls = []
    def forbidden_git(self, *args):
        calls.append(args)
        raise AssertionError("Git proof must follow complete local closure")
    monkeypatch.setattr(EvidenceGraph, "git_bytes", forbidden_git)
    with pytest.raises(workflow_evidence.WorkflowEvidenceError) as caught:
        workflow_evidence.verify_evidence(h.state, context=h.context_data,
            repository_root=str(h.root.resolve()), authority=h.authority, github_get=h.get)
    assert caught.value.code == "MISSING_EVIDENCE"
    assert calls == []


def test_w4_real_metadata_and_support_keep_approved_test(real_history):
    import workflow_evidence
    h = real_history
    h.start(ready=True)
    approved = copy.deepcopy(h.state["test"]["approval"])
    repair, replacement = h.metadata()
    for ref in (repair, replacement):
        code, result = h.validate(ref)
        assert code == 0, result
        h.consume(ref)
    h.tr = replacement
    h.impact = h.objects[replacement["artifact_id"]]["payload"]["impact_set"]
    support = h.support()
    assert h.validate(support)[0] == 0
    h.consume(support)
    candidate = h.repaired_candidate(support)
    assert h.validate(candidate)[0] == 0
    h.consume(candidate)
    result = workflow_evidence.verify_evidence(h.state, context=h.context_data,
        repository_root=str(h.root.resolve()), authority=h.authority, github_get=h.get)
    target = h.objects[support["artifact_id"]]["payload"]["to_test_tip"]["commit"]
    assert result["approved_test_sha"] == h.t
    assert result["effective_test_sha"] == result["executed_test_sha"] == target
    assert result["functional_correction_count"] == 0
    assert h.state["test"]["approval"] == approved


@pytest.mark.parametrize("fault", [None, "stale_pr", "stale_approval"])
def test_real_git_terminal_pr_final_and_merge_bind_l(real_history, fault):
    import workflow_evidence
    h = real_history
    review = h.lesson_report()
    h.consume(review)
    p = {"result": "SUCCESS", "review": review, "candidate_index": 0, "correction_count": 0,
         "accepted_candidate": h.csha, "preserved_implementation": h.i,
         "disposition": "OPEN_SUCCESS_PR", "final_decision": None, "remaining_defects": [], "salvage": [],
         "pr": {"url": "https://github.com/synthetic/repository/pull/219",
                "head_sha": h.csha if fault == "stale_pr" else h.l, "merge_sha": None}}
    proposal = h.artifact("terminal-record", p, [review])
    if fault == "stale_pr":
        assert h.validate(proposal)[0] != 0
        with pytest.raises(transition.WorkflowTransitionError):
            h.consume(proposal)
        return
    assert h.validate(proposal)[0] == 0
    h.consume(proposal)
    approval = h.decision("FINAL", h.csha if fault == "stale_approval" else h.l, [proposal])
    if fault == "stale_approval":
        assert h.validate(approval)[0] != 0
        with pytest.raises(transition.WorkflowTransitionError):
            h.consume(approval)
        return
    assert h.validate(approval)[0] == 0
    h.consume(approval)
    merged = h.git("commit-tree", h.tip(h.l)["tree"], "-p", h.g, "-p", h.l, "-m", "approved merge")
    p = copy.deepcopy(p)
    p.update(disposition="MERGED", final_decision=approval)
    p["pr"]["merge_sha"] = merged
    terminal = h.artifact("terminal-record", p, [review, approval, proposal])
    assert h.validate(terminal)[0] == 0
    h.consume(terminal)
    h.remote["/repos/synthetic/repository/pulls/219"] = {"status": 200, "body": {
        "number": 219, "html_url": p["pr"]["url"], "state": "closed", "merged": True,
        "merge_commit_sha": merged, "base": {"ref": "integration", "sha": h.g,
            "repo": {"full_name": "synthetic/repository"}}, "head": {"sha": h.l}}}
    result = workflow_evidence.verify_evidence(h.state, context=h.context_data,
        repository_root=str(h.root.resolve()), authority=h.authority, github_get=h.get)
    assert result["accepted_candidate_sha"] == h.csha
    assert result["checks"]["finalization"] == "PASS"
