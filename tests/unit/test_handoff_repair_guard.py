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
# File:        test_handoff_repair_guard.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Real Git and Guard-to-reducer non-case repair histories.
# =================================================================================


import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))
from structured_handoff_fixture import Lifecycle
from structured_handoff_schema import canonical_bytes, load_schema, load_registry
from repair_protocol import changed_fields
from workflow_transition_generality_support import legacy_workflow


class RepairLifecycle(Lifecycle):
    def write(self, name, raw):
        if name == "agent-discipline/workflow-contract.json":
            raw = canonical_bytes(legacy_workflow())
        return super().write(name, raw)

    def manifest(self, sha):
        return self.evidence("manifest", {"contract_version": 3,
            "contract_blob_sha": self.gov["workflow_contract_blob"], "base_sha": self.g,
            "lane_sha": sha, "requirement_ids": ["R"]})

    def checked(self, ref):
        private, seen = [], set()
        def ancestors(source):
            if source["artifact_id"] in seen:
                return
            seen.add(source["artifact_id"])
            body = self.objects[source["artifact_id"]]
            if source["kind"] == "worker-correction-envelope":
                private.append(self.store(self.objects[body["payload"]["disclosure_review"]["source_report_id"]]))
            for predecessor in body.get("predecessors", []):
                if predecessor["artifact_id"] in self.objects:
                    ancestors(predecessor)
        ancestors(ref)
        code, result = self.validate(ref, private)
        assert code == 0, result
        checked_ref = self.store(result)
        return checked_ref

    def source(self, commit, path):
        return {"commit": commit, "path": path, "blob": self.git("rev-parse", commit + ":" + path)}

    def snapshot(self, ref):
        return {"ref": ref, "raw": (self.root / ref["path"]).read_text("utf-8")}

    def mapping(self, field, before, after, facts, edges=()):
        old, new = self.snapshot(before), self.snapshot(after)
        return {"field": field, "before": old, "after": new,
            "changed_fields": changed_fields(json.loads(old["raw"]), json.loads(new["raw"])),
            "reason": "Describe the exact original selection and real supporting source.",
            "source_facts": facts, "dependency_audit": list(edges)}

    def audit(self, facts, affected=()):
        dimensions = ("scenarios", "conditions", "assertions", "expected_results",
                      "pass_fail_criteria", "selected_checks", "exclusions", "coverage")
        return {"requirement_ids": ["R"], "source_bindings": facts,
            "dimensions": [{"dimension": name, "before": "Original approved public behavior",
                "after": "Same approved public behavior", "explanation":
                "The exact file diff changes delivery or adapter mechanics; the approved checks remain."}
                for name in dimensions], "affected_check_ids": list(affected),
            "reviewer_role": "orchestrator", "reviewer_id": "orchestrator-review-fern"}

    def candidate(self, index):
        # Keep the accepted fixture untouched; this owned bridge uses an actual
        # disjoint-lane direct-union tree as well as real ordered Git parents.
        ref = super().candidate(index)
        paths = {tip: self.git("diff", "--name-only", self.g, tip).splitlines()
                 for tip in (self.t, self.i)}
        assert not (set(paths[self.t]) & set(paths[self.i]))
        self.git("read-tree", "-i", "-m", self.g, self.t, self.i)
        tree = self.git("write-tree")
        commit = self.git("commit-tree", tree, "-p", self.t, "-p", self.i,
                          "-m", "direct-union candidate " + str(index))
        for tip, changed in paths.items():
            for path in changed:
                assert self.git("ls-tree", commit, "--", path) == self.git("ls-tree", tip, "--", path)
        body = self.objects[ref["artifact_id"]]
        body["payload"]["candidate"] = self.tip(commit)
        assert body["payload"]["candidate"]["parents"] == [self.t, self.i]
        self.c = self.store(body)
        return self.c

    def metadata(self, rejected=False):
        tag = str(self.serial)
        if rejected:
            bad = json.loads((self.root / self.impact["path"]).read_text("utf-8"))
            del bad["excluded_checks"][0]["reason"]
            self.impact = self.evidence("impact-set", bad)
            body = copy.deepcopy(self.objects[self.tr["artifact_id"]])
            body["artifact_id"] = "rejected-metadata-" + tag
            body["payload"]["impact_set"] = self.impact
            self.tr = self.store(body)
        old = self.objects[self.tr["artifact_id"]]
        if rejected:
            code, receipt = self.validate(self.tr)
            assert code == 1
            checked = self.store(receipt)
            trigger = {"kind": "GUARD_REJECTED", "receipt": checked}
        else:
            checked = self.checked(self.tr)
            trigger = {"kind": "ORCHESTRATOR_OBSERVED", "checked": checked,
                       "observation": "The exclusion explanation is inaccurate after delivery."}
        impact = json.loads((self.root / self.impact["path"]).read_text("utf-8"))
        impact["excluded_checks"][0]["reason"] = "No selected requirement changes vendor configuration."
        updated = self.evidence("impact-set", impact)
        facts = [self.source(self.t, "tests/gate.py")]
        payload = {"repair_version": "1.0", "mode": "METADATA", "dispatch_id": "metadata-review-" + tag,
            "original": self.tr, "trigger": trigger,
            "lane": self.test_lane, "replacement_output": ".agent-state/metadata-replacement-" + tag + ".json",
            "reason": "Clarify the exclusion without changing its membership or requirements.",
            "attachment_changes": [self.mapping("impact_set", self.impact, updated, facts)],
            "semantic_audit": self.audit(facts), "preserve_tip": self.t, "preserve_candidate_index": None,
            "preserve_correction_count": 0, "preserve_review_id": None}
        repair = self.artifact("delivery-repair", payload, [self.tr, checked],
                               consumer_role="tester", visibility="tester-confidential")
        replacement = copy.deepcopy(old)
        replacement.update(artifact_id="metadata-replacement-" + tag,
                           replaces={"original": self.tr, "repair": repair})
        replacement["predecessors"].extend([self.tr, repair])
        replacement["payload"].update(dispatch_id=payload["dispatch_id"], impact_set=updated)
        return repair, self.store(replacement)

    def support(self, previous=None, original=None, commit_count=1):
        prior = self.objects[previous["artifact_id"]]["payload"] if previous else None
        start = prior["to_test_tip"]["commit"] if prior else self.t
        old_manifest = prior["test_manifest"] if prior else self.tm
        old_impact = prior["impact_set"] if prior else self.impact
        path = "tests/transport-" + str(self.serial) + ".py"
        target = self.commit(start, path, "adapter = 'unchanged case semantics'\n")
        for number in range(1, commit_count):
            target = self.commit(target, path, "adapter = 'incremental transport " + str(number) + "'\n")
        manifest = self.manifest(target)
        impact = json.loads((self.root / old_impact["path"]).read_text("utf-8"))
        impact["selected_checks"][0]["covered_paths"].append(path)
        impact["public_dependency_edges"].append({"from": "src/component.py", "to": path,
            "reason": "Selected public check uses the new transport support."})
        new_impact = self.evidence("impact-set", impact)
        source_changes = [{"path": path, "before_blob": None,
            "after_blob": self.git("rev-parse", target + ":" + path),
            "reason": "Added Tester adapter with no new assertion or input."}]
        facts = [self.source(start, "tests/gate.py"), self.source(target, "tests/gate.py"),
                 self.source(target, path), self.source(self.i, "src/component.py")]
        edge = {"before": None, "after": {"from": "src/component.py", "to": path},
                "source_bindings": [self.source(self.i, "src/component.py"), self.source(target, path)],
                "explanation": "Existing selected check gains only the exact added support path."}
        source_original = original or self.tr
        checked = self.checked(source_original)
        index = self.objects[self.c["artifact_id"]]["payload"]["candidate_index"] if self.c else None
        payload = {"repair_version": "1.0", "mode": "TEST_SUPPORT",
            "dispatch_id": "support-review-" + str(self.serial), "original": source_original,
            "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": checked,
                        "observation": "An adapter repair is required with unchanged approved checks."},
            "lane": self.test_lane, "replacement_output": ".agent-state/repaired-source-" + str(self.serial) + ".json",
            "reason": "Bind real incremental Tester support and preserve original Human approval.",
            "attachment_changes": [self.mapping("test_manifest", old_manifest, manifest, facts),
                self.mapping("impact_set", old_impact, new_impact, facts, [edge])],
            "semantic_audit": self.audit(facts, ["CHK"]), "approval": self.human,
            "approved_test_report": self.tr, "previous_support_repair": previous,
            "previous_candidate": self.c, "from_test_tip": self.tip(start), "to_test_tip": self.tip(target),
            "implementation_report": self.ir, "candidate_index": index, "correction_count": index or 0,
            "test_manifest": manifest, "impact_set": new_impact, "source_changes": source_changes,
            "retest_check_ids": ["CHK"]}
        refs = [source_original, checked, self.human, self.tr, self.ir]
        refs += ([previous] if previous else []) + ([self.c] if self.c else [])
        refs = list({x["artifact_id"]: x for x in refs}.values())
        return self.artifact("delivery-repair", payload, refs,
                             consumer_role="tester", visibility="tester-confidential")

    def repaired_candidate(self, repair, index=0, invalid=None):
        p = self.objects[repair["artifact_id"]]["payload"]
        before_t, before_tm, before_impact = self.t, self.tm, self.impact
        self.t, self.tm, self.impact = p["to_test_tip"]["commit"], p["test_manifest"], p["impact_set"]
        old_candidate = self.c
        current = self.candidate(index)
        body = self.objects[current["artifact_id"]]
        body["payload"].update(support_repair=repair, dispatch_id="support-exec-" + str(self.serial),
            execution_id="support-execution-" + str(self.serial), rerun_of=invalid,
            previous_candidate=old_candidate)
        body["predecessors"].append(repair)
        if invalid:
            body["predecessors"].append(invalid)
        join_ref = body["payload"]["coverage_join"]
        join = json.loads((self.root / join_ref["path"]).read_text("utf-8"))
        changed = self.git("diff", "--name-only", self.g, self.t).splitlines()
        join["changed_paths"] = [{"path": path, "owner": "TEST", "requirement_ids": ["R"],
            "selected_check_ids": ["CHK"]} for path in changed] + [
            {"path": "src/component.py", "owner": "IMPLEMENTATION", "requirement_ids": ["R"], "selected_check_ids": ["CHK"]}]
        body["payload"]["coverage_join"] = self.evidence("coverage-join", join)
        self.c = self.store(body)
        self.t, self.tm, self.impact = before_t, before_tm, before_impact
        return self.c


class GuardBridge:
    """Every consumed receipt is produced by the actual filesystem Guard."""

    def __init__(self, life):
        import workflow_transition
        self.life, self.module = life, workflow_transition
        self.state = workflow_transition.initial_state(life.task, life.gov)
        self.receipts = []

    def consume(self, ref):
        checked = self.life.checked(ref)
        context = {"schema_version": "1.0", "workflow_profile": "functional-development-v1",
            "task": self.life.task, "governor": self.life.gov,
            "protocol": {"handoff_schema": load_schema(), "registry": load_registry(),
                "workflow_contract": json.loads(self.life.git("cat-file", "blob", self.life.gov["workflow_contract_blob"]))},
            "artifacts": [], "checks": []}
        for body in self.life.objects.values():
            path = ".agent-state/" + body["artifact_id"] + ".json"
            import hashlib
            item_ref = {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"],
                "path": path, "sha256": hashlib.sha256((self.life.root / path).read_bytes()).hexdigest()}
            item = {"ref": item_ref, "body": body}
            context["checks" if body["artifact_kind"] == "guard-result" else "artifacts"].append(item)
        event = {"schema_version": "1.0", "type": "CONSUME", "event_id": "consume-" + ref["artifact_id"],
                 "artifact": ref, "checked": checked}
        self.state = self.module.transition(self.state, event, context=context)
        self.receipts.append(checked)
        return ref

    def ready(self):
        for ref in (self.life.k, self.life.tlaunch, self.life.wlaunch,
                    self.life.tr, self.life.human, self.life.ir):
            self.consume(ref)

    def success(self):
        report = self.life.report("PASS")
        self.consume(report)
        terminal = self.life.terminal(report, True, self.state["candidate"] is not None and
                                      self.life.objects[self.life.c["artifact_id"]]["payload"]["candidate_index"])
        terminal_body = self.life.objects[terminal["artifact_id"]]
        reviewer = terminal_body["payload"]["review"]
        launch = self.life.objects[reviewer["artifact_id"]]["predecessors"][0]
        for ref in (launch, reviewer, terminal):
            self.consume(ref)
        assert self.state["terminal"] == terminal


@pytest.fixture
def life(tmp_path):
    return RepairLifecycle(tmp_path / "repo")


def test_observed_checked_metadata_and_fresh_replacement_guard(life):
    repair, replacement = life.metadata()
    assert life.validate(repair)[0] == 0
    code, result = life.validate(replacement)
    assert code == 0, result
    assert result["input"]["sha256"] == replacement["sha256"]


def test_incremental_support_guard_uses_actual_new_test_source(life):
    repair = life.support()
    code, result = life.validate(repair)
    assert code == 0, result
    candidate = life.repaired_candidate(repair)
    code, result = life.validate(candidate)
    assert code == 0, result


@pytest.mark.parametrize("mutation", ["blob", "worker-path", "missing-diff", "approval", "argv", "schema-version", "unbound-source"])
def test_support_guard_rejects_forged_or_semantic_mutations(life, mutation):
    repair = life.support()
    body = copy.deepcopy(life.objects[repair["artifact_id"]])
    body["artifact_id"] += "-bad"
    p = body["payload"]
    if mutation == "blob":
        p["source_changes"][0]["after_blob"] = "b" * 40
    elif mutation == "worker-path":
        p["source_changes"][0]["path"] = "src/component.py"
    elif mutation == "missing-diff":
        p["source_changes"] = []
    elif mutation == "approval":
        p["approval"] = life.ir
    elif mutation == "argv":
        change = p["attachment_changes"][1]
        after = json.loads(change["after"]["raw"])
        after["selected_checks"][0]["argv"] = ["python", "other.py"]
        ref = life.evidence("impact-set", after)
        change["after"] = life.snapshot(ref)
        change["changed_fields"] = changed_fields(json.loads(change["before"]["raw"]), after)
        p["impact_set"] = ref
    elif mutation == "schema-version":
        p["repair_version"] = "2.0"
    else:
        foreign = life.commit(life.g, "src/component.py", "Unrelated source branch")
        fact = life.source(foreign, "src/component.py")
        p["semantic_audit"]["source_bindings"] = [*p["semantic_audit"]["source_bindings"], fact]
        for mapping in p["attachment_changes"]:
            mapping["source_facts"] = [*mapping["source_facts"], fact]
    code, _ = life.validate(life.store(body))
    assert code == 1


def test_real_guard_to_reducer_metadata_does_not_repeat_approval(life):
    bridge = GuardBridge(life)
    bridge.ready()
    anchor = copy.deepcopy(bridge.state["test"])
    repair, replacement = life.metadata()
    bridge.consume(repair)
    bridge.consume(replacement)
    assert bridge.state["test"]["approval"] == anchor["approval"]
    assert bridge.state["test"]["ready"] == replacement
    assert bridge.state["worker"]["pending_correction"] is None
    life.tr = replacement
    life.impact = life.objects[replacement["artifact_id"]]["payload"]["impact_set"]
    bridge.consume(life.candidate(0))
    bridge.success()


def test_real_guard_to_reducer_metadata_then_support(life):
    bridge = GuardBridge(life)
    bridge.ready()
    repair, replacement = life.metadata()
    bridge.consume(repair)
    bridge.consume(replacement)
    life.tr = replacement
    life.impact = life.objects[replacement["artifact_id"]]["payload"]["impact_set"]
    support = life.support()
    bridge.consume(support)
    bridge.consume(life.repaired_candidate(support))
    bridge.success()


@pytest.mark.parametrize("after_invalid", [False, True])
def test_real_guard_to_reducer_support_full_chain(life, after_invalid):
    bridge = GuardBridge(life)
    bridge.ready()
    original = copy.deepcopy(bridge.state["test"])
    invalid = None
    if after_invalid:
        bridge.consume(life.candidate(0))
        invalid = life.report("INVALID_RUN")
        bridge.consume(invalid)
    repair = life.support(original=invalid, commit_count=2 if after_invalid else 1)
    if after_invalid:
        p = life.objects[repair["artifact_id"]]["payload"]
        assert p["from_test_tip"]["commit"] not in p["to_test_tip"]["parents"]
    bridge.consume(repair)
    if invalid:
        assert bridge.state["candidate"]["result"] == invalid
    assert bridge.state["test"] == original
    bridge.consume(life.repaired_candidate(repair, invalid=invalid))
    bridge.success()
    assert bridge.state["test"] == original
    assert len(bridge.receipts) == len(bridge.state["consumed"])


def test_real_guard_to_reducer_repeated_support_and_counted_worker_fix(life):
    bridge = GuardBridge(life)
    bridge.ready()
    first = life.support()
    bridge.consume(first)
    second = life.support(previous=first)
    bridge.consume(second)
    bridge.consume(life.repaired_candidate(second))
    failure = life.report("IMPLEMENTATION_FAIL")
    bridge.consume(failure)
    third = life.support(previous=second, original=failure)
    bridge.consume(third)
    assert bridge.state["candidate"]["result"] == failure
    correction = life.correction(1, failure)
    bridge.consume(correction)
    previous = life.i
    life.i = life.commit(previous, "src/component.py", "Correct public implementation branch")
    life.ir = life.implementation(1, life.i, previous, correction)
    bridge.consume(life.ir)
    bridge.consume(life.repaired_candidate(third, index=1))
    bridge.success()
    assert bridge.state["test"]["approval"] == life.human
    assert life.objects[bridge.state["terminal"]["artifact_id"]]["payload"]["correction_count"] == 1


def test_support_retest_requires_fresh_result_ref_even_for_identical_pass(life):
    life.candidate(0)
    old = life.report("INVALID_RUN")
    support = life.support(original=old)
    life.repaired_candidate(support, invalid=old)
    fresh = life.report("PASS")
    old_result = life.objects[old["artifact_id"]]["payload"]["execution"][0]["result"]
    fresh_body = life.objects[fresh["artifact_id"]]
    new_result = fresh_body["payload"]["execution"][0]["result"]
    assert old_result["sha256"] == new_result["sha256"]
    assert old_result["path"] != new_result["path"]
    assert life.validate(fresh)[0] == 0
    stale = copy.deepcopy(fresh_body)
    stale["artifact_id"] += "-reused-evidence"
    stale["payload"]["execution"][0]["result"] = old_result
    assert life.validate(life.store(stale))[0] == 1


def test_real_rejected_descriptive_metadata_is_repaired_before_readiness(life):
    bridge = GuardBridge(life)
    for ref in (life.k, life.tlaunch, life.wlaunch, life.ir):
        bridge.consume(ref)
    repair, replacement = life.metadata(rejected=True)
    bridge.consume(repair)
    bridge.consume(replacement)
    life.tr = replacement
    life.impact = life.objects[replacement["artifact_id"]]["payload"]["impact_set"]
    decision = copy.deepcopy(life.objects[life.human["artifact_id"]]["payload"])
    life.human = life.artifact("human-decision", decision, [replacement])
    bridge.consume(life.human)
    bridge.consume(life.candidate(0))
    bridge.success()


def test_repeated_metadata_replacement_keeps_one_original_approval(life):
    bridge = GuardBridge(life)
    bridge.ready()
    approval = life.human
    for _ in range(2):
        repair, replacement = life.metadata()
        bridge.consume(repair)
        bridge.consume(replacement)
        life.tr = replacement
        life.impact = life.objects[replacement["artifact_id"]]["payload"]["impact_set"]
    bridge.consume(life.candidate(0))
    bridge.success()
    assert bridge.state["test"]["approval"] == approval


def test_supported_execution_metadata_reissue_preserves_exact_results(life):
    bridge = GuardBridge(life)
    bridge.ready()
    support = life.support()
    bridge.consume(support)
    candidate = life.repaired_candidate(support)
    bridge.consume(candidate)
    original = life.report("PASS")
    bridge.consume(original)
    receipt = life.checked(original)
    old = life.objects[original["artifact_id"]]
    facts = [life.source(life.i, "src/component.py")]
    payload = {"repair_version": "1.0", "mode": "METADATA", "dispatch_id": "report-metadata-review",
        "original": original, "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": receipt,
            "observation": "The summary needs a descriptive clarification, not a new execution."},
        "lane": life.test_lane, "replacement_output": ".agent-state/report-metadata-reissue.json",
        "reason": "Clarify only the summary while preserving exact execution evidence.",
        "attachment_changes": [], "semantic_audit": life.audit(facts),
        "preserve_tip": old["payload"]["candidate_sha"], "preserve_candidate_index": 0,
        "preserve_correction_count": 0, "preserve_review_id": None}
    repair = life.artifact("delivery-repair", payload, [original, receipt, candidate],
                          consumer_role="tester", visibility="tester-confidential")
    body = copy.deepcopy(old)
    body.update(artifact_id="report-metadata-reissue", replaces={"original": original, "repair": repair})
    body["predecessors"].extend([original, repair])
    body["payload"].update(dispatch_id=payload["dispatch_id"], summary="Same PASS; clarified execution summary.")
    replacement = life.store(body)
    bridge.consume(repair)
    bridge.consume(replacement)
    assert bridge.state["candidate"]["result"] == replacement
    assert body["payload"]["execution"] == old["payload"]["execution"]
    assert body["payload"]["execution_id"] == old["payload"]["execution_id"]
