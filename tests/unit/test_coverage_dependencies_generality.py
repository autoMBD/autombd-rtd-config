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
# File:        test_coverage_dependencies_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Worker-owned coverage and declared dependency generality tests.
# =================================================================================

"""Exercise local rules with real Git inventories and byte-bound attachments.

These unit tests construct their own inputs. They do not read task-local K,
owner Test, historical run data or accepted functional fixtures. Calling the
local rule directly is not full lifecycle validation or proof of graph semantics.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
TEMP_BASE = ROOT / "tests/.tmp"
sys.path.insert(0, str(SCRIPTS))

from repair_protocol import (RepairError, changed_fields, validate_impact_projection,
                             validate_metadata_replacement)
from structured_handoff import run_validation
from structured_handoff_refs import ReferenceGraph
from structured_handoff_rules import LocalRules
from structured_handoff_schema import ProtocolError, canonical_bytes, validate_artifact


class CoverageDependenciesGenerality(unittest.TestCase):
    """Vary coverage grouping without deriving source edges from that grouping."""

    impl_paths = ["engine/adapter.py", "engine/format.py", "reference/shape.md"]
    test_paths = ["checks/adapter_probe.py", "checks/schema_probe.py",
                  "review/contract.md", "review/overview.md"]
    helpers = ["support/first.py", "support/middle.py", "support/last.py"]
    requirements = ["EDIT", "REVIEW"]

    @classmethod
    def setUpClass(cls):
        TEMP_BASE.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="coverage-generality-", dir=TEMP_BASE)
        cls.repo = Path(cls.temporary.name).resolve()
        cls.addClassCleanup(cls.cleanup_repository)
        cls.git("init", "-q")
        cls.put(".gitignore", b".agent-state/\n")
        cls.put("agent-discipline/workflow-contract.json",
                (ROOT / "agent-discipline/workflow-contract.json").read_bytes())
        cls.put(cls.helpers[0], b"from support.middle import value\n")
        cls.put(cls.helpers[1], b"from support.last import value\n")
        cls.put(cls.helpers[2], b"value = 73\n")
        cls.base = cls.commit("Generality baseline")
        for path in cls.test_paths:
            cls.put(path, ("# Independent check or review input: " + path + "\n").encode())
        cls.test_tip = cls.commit("Independent check lane")
        cls.git("checkout", "-q", "--detach", cls.base)
        cls.put(cls.impl_paths[0], b"from support.first import value\n")
        cls.put(cls.impl_paths[1], b"def render(value):\n    return str(value)\n")
        cls.put(cls.impl_paths[2], b"A shape has a name and dimensions.\n")
        cls.impl_tip = cls.commit("Independent implementation lane")
        cls.put(cls.test_paths[0], b"# Deliberate ownership overlap\n")
        cls.overlap_tip = cls.commit("Overlapping lane for rejection checks")
        cls.governor = {
            "commit": cls.base,
            "workflow_contract_path": "agent-discipline/workflow-contract.json",
            "workflow_contract_blob": cls.git(
                "rev-parse", cls.base + ":agent-discipline/workflow-contract.json"),
        }
        cls.task = {"repository": "autoMBD/autombd-rtd-config", "issue_number": 116,
                    "task_run": "worker-coverage-generality"}
        cls.state = ".agent-state/agent-loop/generality/inbox/"
        authority = cls.store("authority.json", {"purpose": "Independent unit inputs"},
                              "authority")
        contract = {
            "schema_version": "1.0", "artifact_kind": "task-contract",
            "artifact_id": "generality-contract", "task": cls.task,
            "workflow_profile": "functional-development-v1",
            "producer_role": "orchestrator", "consumer_role": "orchestrator",
            "visibility": "public-task", "governor": cls.governor,
            "task_contract": None, "predecessors": [], "replaces": None,
            "unresolved": [], "payload": {
                "revision": {"number": 0, "predecessor": None, "authority": None,
                    "reason": "Independent unit inputs", "changed_authority_ids": [],
                    "affected_requirement_ids": []},
                "priority": "P1", "dependencies": [],
                "authorities": [{"id": "UNIT", "source_kind": "repository-file",
                    "locator": "Worker-owned unit generator", "snapshot": authority}],
                "objective": "Check declared coverage relationships",
                "requirements": [{"id": key, "authority_ids": ["UNIT"],
                    "obligation": "Account for " + key} for key in cls.requirements],
                "scope": {"included": ["Local rule units"], "excluded": []},
                "boundaries": [], "interfaces": [], "decision_rules": [],
                "acceptance": [{"id": "UNIT_ACCEPTANCE", "kind": "unit",
                    "requirement_ids": cls.requirements,
                    "selection_rule": "Run independent generality tests"}],
                "unknown_policy": {"record_first": True, "bounded_diagnostic": True,
                    "block_affected_operation_only": True,
                    "ambiguous_classification": "human", "preserve_implementation": True},
            },
        }
        ref = cls.store("contract.json", contract, "authority")
        cls.kref = {"revision": 0, "path": ref["path"], "sha256": ref["sha256"]}

    @classmethod
    def cleanup_repository(cls):
        if not cls.repo.is_relative_to(TEMP_BASE.resolve()) or cls.repo == TEMP_BASE.resolve():
            raise RuntimeError("Temporary repository escaped its workspace base")
        cls.temporary.cleanup()

    @classmethod
    def git(cls, *args):
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_")}
        environment["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", "-C", str(cls.repo), "-c", "core.autocrlf=false",
             "-c", "commit.gpgsign=false", "-c", "user.name=autoMBD",
             "-c", "user.email=tkung.lqk@foxmail.com", *args],
            capture_output=True, check=True, timeout=15, env=environment)
        return result.stdout.decode("utf-8").strip()

    @classmethod
    def put(cls, path, raw):
        target = cls.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

    @classmethod
    def commit(cls, message):
        cls.git("add", "--all")
        cls.git("commit", "-q", "-m", message)
        return cls.git("rev-parse", "HEAD")

    @classmethod
    def store(cls, name, value, evidence_type):
        raw = canonical_bytes(value)
        path = cls.state + name
        cls.put(path, raw)
        return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(),
                "evidence_type": evidence_type}

    def setUp(self):
        self.impact = {
            "schema_version": "1.0", "task": self.task, "task_contract": self.kref,
            "selected_checks": [self.check("path-" + str(index), [path])
                for index, path in enumerate(self.impl_paths + self.test_paths)],
            "excluded_checks": [], "public_dependency_edges": [],
            "prevalidation_obligations": [{"id": "LOCAL_ONLY", "mode": "NOT_APPLICABLE",
                "reason": "These units invoke the local join, not lifecycle dispatch."}],
        }
        self.join = {
            "schema_version": "1.0", "test_commit": self.test_tip,
            "implementation_commit": self.impl_tip, "impact_set_sha256": "0" * 64,
            "changed_paths": [{"path": path, "owner": owner,
                "requirement_ids": ["EDIT" if owner == "IMPLEMENTATION" else "REVIEW"],
                "selected_check_ids": ["path-" + str(index)]}
                for index, (owner, path) in enumerate(
                    [("IMPLEMENTATION", path) for path in self.impl_paths] +
                    [("TEST", path) for path in self.test_paths])],
        }

    def check(self, check_id, paths, family="unit"):
        return {"id": check_id, "family": family,
                "argv": ["python", "-c", "pass"],
                "requirement_ids": self.requirements[:], "covered_paths": paths[:]}

    def edge(self, source, target):
        return {"from": source, "to": target,
                "reason": "The first source directly imports the second source."}

    def evaluate(self, *, join_change=None, impact_change=None, artifact_change=None):
        impact = copy.deepcopy(self.impact)
        if impact_change:
            impact_change(impact)
        impact_ref = self.store("impact.json", impact, "impact-set")
        join = copy.deepcopy(self.join)
        join["impact_set_sha256"] = impact_ref["sha256"]
        if join_change:
            join_change(join)
        join_ref = self.store("join.json", join, "coverage-join")
        artifact = {"artifact_kind": "candidate-test-envelope", "task": self.task,
            "task_contract": self.kref, "payload": {
                "test_tip": {"commit": self.test_tip},
                "implementation_tip": {"commit": self.impl_tip},
                "coverage_join": join_ref, "impact_set": impact_ref}}
        if artifact_change:
            artifact_change(artifact)
        context = {"worktree_root": str(self.repo), "expected_head": self.overlap_tip,
                   "governor": self.governor, "task": self.task,
                   "consumer_role": "orchestrator", "predecessor_refs": []}
        graph = ReferenceGraph(context, "orchestrator-full")
        graph.verify_environment()
        LocalRules(graph).coverage_join(artifact)
        return graph

    def reject(self, rule, **changes):
        with self.assertRaises(ProtocolError) as caught:
            self.evaluate(**changes)
        self.assertEqual(caught.exception.rule_id, rule)

    def test_individually_covered_changed_paths_need_no_edges(self):
        self.evaluate()

    def test_shared_coverage_does_not_create_direct_dependencies(self):
        paths = self.impl_paths + self.test_paths
        for group_size in (2, 3, len(paths)):
            with self.subTest(group_size=group_size):
                self.impact["selected_checks"] = []
                for index in range(0, len(paths), group_size):
                    selected = self.check("group-" + str(index), paths[index:index + group_size],
                                          "static" if index % 2 else "functional")
                    self.impact["selected_checks"].append(selected)
                for change in self.join["changed_paths"]:
                    change["selected_check_ids"] = [check["id"]
                        for check in self.impact["selected_checks"]
                        if change["path"] in check["covered_paths"]]
                self.evaluate()

    def test_multilevel_dependencies_may_span_different_checks(self):
        chain = [self.impl_paths[0], *self.helpers]
        self.impact["selected_checks"] += [self.check("helper-" + str(index), [path])
            for index, path in enumerate(self.helpers)]
        for length in (2, 3, 4):
            with self.subTest(length=length):
                self.impact["public_dependency_edges"] = [self.edge(first, second)
                    for first, second in zip(chain[:length], chain[1:length])]
                original = copy.deepcopy(self.impact)
                self.evaluate()
                self.assertEqual(self.impact, original)

    def test_static_review_may_share_a_check_without_direct_edges(self):
        covered = self.impl_paths + self.test_paths
        self.impact["selected_checks"] = [self.check("review", covered, "static")]
        for change in self.join["changed_paths"]:
            change["selected_check_ids"] = ["review"]
        self.evaluate()

    def test_duplicate_directed_pairs_are_rejected_even_with_different_reasons(self):
        first, second = self.helpers[:2]
        self.impact["selected_checks"].append(self.check("helpers", [first, second]))
        for reason in ("same", "different"):
            with self.subTest(reason=reason):
                edge = self.edge(first, second)
                duplicate = dict(edge, reason=edge["reason"] if reason == "same" else "Another claim")
                self.impact["public_dependency_edges"] = [edge, duplicate]
                self.reject("DEPENDENCY_EDGE")

    def test_each_declared_endpoint_requires_selected_coverage(self):
        for missing in ("from", "to"):
            with self.subTest(missing=missing):
                edge = self.edge(self.helpers[0], self.helpers[1])
                covered = edge["to" if missing == "from" else "from"]
                self.impact["selected_checks"] = self.impact["selected_checks"][:7]
                self.impact["selected_checks"].append(self.check("one-end", [covered]))
                self.impact["public_dependency_edges"] = [edge]
                self.reject("DEPENDENCY_COVERAGE")

    def test_excluded_check_cannot_supply_endpoint_coverage(self):
        self.impact["public_dependency_edges"] = [self.edge(self.impl_paths[0], self.helpers[0])]
        self.impact["excluded_checks"] = [{"id": "helper-check", "family": "unit",
            "reason": "This check examines " + self.helpers[0] + " but is not selected."}]
        self.reject("DEPENDENCY_COVERAGE")

    def test_directed_pairs_are_not_normalized_to_undirected_pairs(self):
        # Structural success does not certify the truth of these reason strings.
        first, second = self.helpers[:2]
        self.impact["selected_checks"].append(self.check("helpers", [first, second]))
        self.impact["public_dependency_edges"] = [self.edge(first, second), self.edge(second, first)]
        self.evaluate()

    def test_actual_change_inventory_cannot_be_omitted_added_or_duplicated(self):
        operations = [
            ("COVERAGE_CHANGED_PATHS", lambda join: join["changed_paths"].pop()),
            ("COVERAGE_CHANGED_PATHS", lambda join: join["changed_paths"].append(
                dict(join["changed_paths"][0], path=self.helpers[0]))),
            ("COVERAGE_DUPLICATE_PATH", lambda join: join["changed_paths"].append(
                copy.deepcopy(join["changed_paths"][0]))),
            ("COVERAGE_CHANGED_PATHS", lambda join: join["changed_paths"][0].update(owner="TEST")),
        ]
        for rule, mutate in operations:
            with self.subTest(rule=rule, mutate=mutate):
                self.reject(rule, join_change=mutate)

    def test_actual_lane_overlap_is_rejected(self):
        self.reject("OWNERSHIP_OVERLAP",
            join_change=lambda join: join.update(implementation_commit=self.overlap_tip),
            artifact_change=lambda artifact: artifact["payload"]["implementation_tip"].update(
                commit=self.overlap_tip))

    def test_invalid_requirement_or_check_mapping_is_rejected(self):
        for key in ("requirement_ids", "selected_check_ids"):
            with self.subTest(key=key):
                self.reject("COVERAGE_REFERENCE", join_change=lambda join: join[
                    "changed_paths"][0].update({key: ["UNDECLARED"]}))
        self.reject("COVERAGE_JOIN_MISSING", join_change=lambda join: join[
            "changed_paths"][0].update(selected_check_ids=["path-1"]))
        self.reject("COVERAGE_JOIN_MISSING", impact_change=lambda impact: impact[
            "selected_checks"][0].update(requirement_ids=["REVIEW"]))

    def test_empty_mapping_is_rejected_by_existing_closed_schema(self):
        for key in ("requirement_ids", "selected_check_ids"):
            with self.subTest(key=key), self.assertRaises(ProtocolError):
                self.evaluate(join_change=lambda join: join["changed_paths"][0].update({key: []}))

    def test_extra_dependencies_do_not_repair_missing_path_mapping(self):
        self.impact["public_dependency_edges"] = [self.edge(self.impl_paths[0], self.helpers[0])]
        self.impact["selected_checks"].append(self.check("helper", [self.helpers[0]]))
        self.reject("COVERAGE_CHANGED_PATHS", join_change=lambda join: join["changed_paths"].pop())

    def test_coverage_mapping_failure_precedes_invalid_dependency(self):
        edge = self.edge(self.impl_paths[0], self.helpers[0])
        self.impact["public_dependency_edges"] = [edge, copy.deepcopy(edge)]
        self.reject("COVERAGE_JOIN_MISSING", join_change=lambda join: join[
            "changed_paths"][0].update(selected_check_ids=["path-1"]))

    def test_join_identity_and_attachment_digests_remain_bound(self):
        for key, value in (("test_commit", self.impl_tip),
                           ("implementation_commit", self.test_tip),
                           ("impact_set_sha256", "7" * 64)):
            with self.subTest(key=key):
                self.reject("COVERAGE_JOIN_IDENTITY", join_change=lambda join: join.update({key: value}))
        self.reject("EVIDENCE_DIGEST", artifact_change=lambda artifact: artifact[
            "payload"]["coverage_join"].update(sha256="7" * 64))

    def test_metadata_repair_cannot_change_selected_semantics(self):
        changes = [
            ("REPAIR_COVERAGE_CHANGE", lambda impact: impact["selected_checks"][0]["covered_paths"].append(self.helpers[0])),
            ("REPAIR_SELECTION_CHANGE", lambda impact: impact["selected_checks"][0].update(argv=["different-command"])),
            ("REPAIR_SELECTION_CHANGE", lambda impact: impact["selected_checks"].pop()),
            ("REPAIR_SELECTION_CHANGE", lambda impact: impact["selected_checks"][0].update(requirement_ids=["EDIT"])),
            ("REPAIR_SELECTION_CHANGE", lambda impact: impact["excluded_checks"].append(
                {"id": "extra-exclusion", "family": "unit", "reason": "Excluded"})),
            ("REPAIR_SELECTION_CHANGE", lambda impact: impact["prevalidation_obligations"][0].update(mode="RED")),
        ]
        for rule, mutate in changes:
            with self.subTest(rule=rule, mutate=mutate):
                changed = copy.deepcopy(self.impact)
                mutate(changed)
                with self.assertRaises(RepairError) as caught:
                    validate_impact_projection(self.impact, changed)
                self.assertEqual(caught.exception.rule, rule)

    def metadata_repair(self, additions, *, after_change=None, repair_change=None):
        """Use real source/guard evidence; NOT_READY is not Test approval.

        The unit's original report deliberately makes no functional-readiness
        claim. This checks the complete metadata/replacement machinery without
        manufacturing a Human approval or an independent functional verdict.
        """
        serial = getattr(self, "repair_serial", 0) + 1
        self.repair_serial = serial
        prefix = self._testMethodName + "-" + str(serial)
        before = copy.deepcopy(self.impact)
        invocation = [sys.executable, "-B", "-c",
                      "from support.first import value; print(value)"]
        for check in before["selected_checks"]:
            if check["id"] in additions:
                check["argv"] = invocation
        self.git("checkout", "-q", "--detach", self.test_tip)
        try:
            executed = subprocess.run(invocation, cwd=self.repo, capture_output=True,
                                      check=True, timeout=15)
            self.assertEqual(executed.stdout.strip(), b"73")
        finally:
            self.git("checkout", "-q", "--detach", self.overlap_tip)
        after = copy.deepcopy(before)
        for check in after["selected_checks"]:
            check["covered_paths"] += additions.get(check["id"], [])
        if after_change:
            after_change(after)
        before_ref = self.store(prefix + "-before.json", before, "impact-set")
        after_ref = self.store(prefix + "-after.json", after, "impact-set")
        contract = json.loads((self.repo / self.kref["path"]).read_bytes())
        contract_ref = {"kind": "task-contract", "artifact_id": contract["artifact_id"],
                        "path": self.kref["path"], "sha256": self.kref["sha256"]}
        common = {key: contract[key] for key in ("schema_version", "task",
                  "workflow_profile", "governor")}
        common.update(task_contract=self.kref, visibility="tester-confidential",
                      replaces=None, unresolved=[])
        lane = {"lane_id": "unit-test-lane", "agent_session_id": "unit-session",
                "worktree_id": "unit-checkout", "branch": "unit-test"}
        launch = dict(common, artifact_kind="test-launch", artifact_id=prefix + "-launch",
            producer_role="orchestrator", consumer_role="tester", predecessors=[contract_ref],
            payload={"dispatch_id": prefix + "-author", "mode": "INITIAL", "lane": lane,
                "output_path": self.state + prefix + "-original.json",
                "requirement_ids": self.requirements, "interface_ids": [],
                "forbidden_sources": [], "forbidden_actions": [],
                "previous_launch": None, "revision_ack_required": False,
                "duties": {"author_functional_gate": True, "prevalidate_full_chain": True,
                    "freeze_impact_set": True, "implementation_read_allowed": False,
                    "production_write_allowed": False}})

        def artifact_ref(body, suffix):
            validate_artifact(body)
            ref = self.store(prefix + suffix, body, "authority")
            return {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"],
                    "path": ref["path"], "sha256": ref["sha256"]}

        launch_ref = artifact_ref(launch, "-launch.json")
        tip = {"commit": self.test_tip, "parents": [self.base],
               "tree": self.git("rev-parse", self.test_tip + "^{tree}")}
        original = dict(common, artifact_kind="test-gate-report", artifact_id=prefix + "-original",
            producer_role="tester", consumer_role="orchestrator", predecessors=[launch_ref],
            payload={"dispatch_id": launch["payload"]["dispatch_id"], "status": "NOT_READY",
                "lane": lane, "test_tip": tip, "manifest": None,
                "requirement_coverage": [], "impact_set": before_ref, "impact_selection": [],
                "prevalidation": [], "revision_ack": None})
        original_ref = artifact_ref(original, "-original.json")
        context = {"schema_version": "1.0", "operation_id": prefix + "-check",
            "task": self.task, "governor": self.governor, "task_contract": self.kref,
            "consumer_role": "orchestrator", "checkpoint": "test-gate-report",
            "worktree_root": str(self.repo), "expected_head": self.overlap_tip,
            "predecessor_refs": [launch_ref], "central_check": None}
        context_ref = self.store(prefix + "-context.json", context, "authority")
        receipt_path = self.repo / (self.state + prefix + "-checked.json")
        self.assertEqual(run_validation(self.repo / original_ref["path"], original_ref["sha256"],
            self.repo / context_ref["path"], "orchestrator-full", receipt_path), 0)
        receipt = json.loads(receipt_path.read_bytes())
        receipt_ref = {"kind": "guard-result", "artifact_id": receipt["artifact_id"],
            "path": receipt_path.relative_to(self.repo).as_posix(),
            "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
        facts = [{"commit": self.test_tip, "path": path,
                  "blob": self.git("rev-parse", self.test_tip + ":" + path)}
                 for path in self.helpers]
        dimensions = ["scenarios", "conditions", "assertions", "expected_results",
                      "pass_fail_criteria", "selected_checks", "exclusions", "coverage"]
        repair = dict(common, artifact_kind="delivery-repair", artifact_id=prefix + "-repair",
            producer_role="orchestrator", consumer_role="tester",
            predecessors=[original_ref, receipt_ref], payload={
                "repair_version": "1.0", "mode": "METADATA", "dispatch_id": prefix + "-repair",
                "original": original_ref, "trigger": {"kind": "ORCHESTRATOR_OBSERVED",
                    "checked": receipt_ref, "observation": "Existing command imports omitted helpers."},
                "lane": lane, "replacement_output": self.state + prefix + "-replacement.json",
                "reason": "Record source paths already exercised by the unchanged invocation.",
                "attachment_changes": [{"field": "impact_set",
                    "before": {"ref": before_ref, "raw": canonical_bytes(before).decode()},
                    "after": {"ref": after_ref, "raw": canonical_bytes(after).decode()},
                    "changed_fields": changed_fields(before, after),
                    "reason": "The exact Test command imports the first, middle and last helper.",
                    "source_facts": facts, "dependency_audit": []}],
                "semantic_audit": {"requirement_ids": self.requirements,
                    "source_bindings": copy.deepcopy(facts), "affected_check_ids": sorted(additions),
                    "reviewer_role": "orchestrator", "reviewer_id": "unit-source-review",
                    "dimensions": [{"dimension": dimension,
                        "before": "Original exact Test and unchanged invocation.",
                        "after": "Same Test source and invocation; add omitted helper attribution.",
                        "explanation": "The command imports the bound helper chain; all old paths and "
                                       "the original " + dimension + " remain unchanged."}
                                   for dimension in dimensions]},
                "preserve_tip": self.test_tip, "preserve_candidate_index": None,
                "preserve_correction_count": 0, "preserve_review_id": None})
        if repair_change:
            repair_change(repair)
        repair_ref = artifact_ref(repair, "-repair.json")
        graph = ReferenceGraph(context, "orchestrator-full")
        graph.verify_environment()
        graph.artifact(repair_ref)
        LocalRules(graph).check(repair)
        replacement = copy.deepcopy(original)
        replacement.update(artifact_id=prefix + "-replacement",
            predecessors=[launch_ref, original_ref, repair_ref],
            replaces={"original": original_ref, "repair": repair_ref})
        replacement["payload"].update(dispatch_id=repair["payload"]["dispatch_id"], impact_set=after_ref)
        replacement_ref = artifact_ref(replacement, "-replacement.json")
        graph.artifact(replacement_ref)
        LocalRules(graph).check(replacement)
        validate_metadata_replacement(original, replacement, repair)
        return before, after

    def test_complete_metadata_repair_adds_only_source_bound_attribution(self):
        for additions in ({"path-0": self.helpers[:1]},
                          {"path-0": self.helpers[:2], "path-2": self.helpers[1:]}):
            with self.subTest(additions=additions):
                before, after = self.metadata_repair(additions)
                # A direct projection call still has no complete repair proof.
                with self.assertRaises(RepairError) as caught:
                    validate_impact_projection(before, after)
                self.assertEqual(caught.exception.rule, "REPAIR_COVERAGE_CHANGE")

    def test_attribution_repair_rejects_missing_or_wrong_source_proof(self):
        def omit_path(repair):
            repair["payload"]["attachment_changes"][0]["source_facts"] = [
                fact for fact in repair["payload"]["attachment_changes"][0]["source_facts"]
                if fact["path"] != self.helpers[0]]
        def wrong_commit(repair):
            for fact in repair["payload"]["attachment_changes"][0]["source_facts"]:
                fact["commit"] = self.base
            for fact in repair["payload"]["semantic_audit"]["source_bindings"]:
                fact["commit"] = self.base
        def wrong_blob(repair):
            for facts in (repair["payload"]["attachment_changes"][0]["source_facts"],
                          repair["payload"]["semantic_audit"]["source_bindings"]):
                facts[0]["blob"] = "3" * 40
        for mutate in (omit_path, wrong_commit, wrong_blob,
                       lambda repair: repair["payload"].update(preserve_tip=self.impl_tip)):
            with self.subTest(mutate=mutate), self.assertRaises(ProtocolError):
                self.metadata_repair({"path-0": self.helpers[:1]}, repair_change=mutate)

    def test_attribution_repair_requires_exact_check_and_dimension_audit(self):
        mutations = [lambda repair: repair["payload"]["semantic_audit"].update(affected_check_ids=[]),
            lambda repair: repair["payload"]["semantic_audit"].update(affected_check_ids=["path-1"]),
            lambda repair: repair["payload"]["semantic_audit"]["dimensions"].pop(),
            lambda repair: repair["payload"]["attachment_changes"][0].update(changed_fields=[])]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ProtocolError):
                self.metadata_repair({"path-0": self.helpers[:1]}, repair_change=mutate)

    def test_attribution_repair_preserves_every_old_check_path_and_command(self):
        mutations = [lambda impact: impact["selected_checks"][0]["covered_paths"].pop(0),
            lambda impact: impact["selected_checks"][0].update(argv=["different-command"]),
            lambda impact: impact["selected_checks"][0].update(requirement_ids=["EDIT"]),
            lambda impact: impact["selected_checks"][0].update(family="static"),
            lambda impact: impact["selected_checks"].pop(),
            lambda impact: impact["prevalidation_obligations"][0].update(mode="RED", reason=None),
            lambda impact: impact["excluded_checks"].append(
                {"id": "extra-exclusion", "family": "unit", "reason": "Outside the invocation"})]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(ProtocolError):
                self.metadata_repair({"path-0": self.helpers[:1]}, after_change=mutate)


if __name__ == "__main__":
    unittest.main()
