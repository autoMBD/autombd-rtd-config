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
# File:        structured_handoff_fixture.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Synthetic independent Git histories and protocol lifecycles.
# =================================================================================

import hashlib
import json
import subprocess
from pathlib import Path

from structured_handoff_schema import canonical_bytes, load_registry


class Lifecycle:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.write("agent-discipline/workflow-contract.json", b'{"contract_version":1}\n')
        self.write("src/component.py", b"baseline\n")
        self.git("add", ".")
        self.git("commit", "-qm", "governor")
        self.g = self.git("rev-parse", "HEAD")
        self.gov = {"commit": self.g, "workflow_contract_path": "agent-discipline/workflow-contract.json",
                    "workflow_contract_blob": self.git("rev-parse", self.g + ":agent-discipline/workflow-contract.json")}
        self.task = {"repository": "synthetic/repository", "issue_number": 417, "task_run": "run-arbitrary"}
        self.objects = {}
        self.kref = None
        self.serial = 0
        self.test_lane = self.lane("test")
        self.worker_lane = self.lane("worker")
        authority = self.evidence("authority", b"Public synthetic obligation.")
        kp = {"revision": {"number": 0, "predecessor": None, "authority": None, "reason": "Initial public task", "changed_authority_ids": [], "affected_requirement_ids": []},
              "priority": "P1", "dependencies": [], "authorities": [{"id": "A", "source_kind": "human-decision", "locator": "public-command", "snapshot": authority}],
              "objective": "Validate arbitrary public behavior", "requirements": [{"id": "R", "authority_ids": ["A"], "obligation": "Preserve public behavior"}],
              "scope": {"included": ["Public component"], "excluded": []}, "boundaries": [],
              "interfaces": [], "decision_rules": [],
              "acceptance": [{"id": "AC", "kind": "unit", "requirement_ids": ["R"], "selection_rule": "Direct dependency"}],
              "unknown_policy": {"record_first": True, "bounded_diagnostic": True, "block_affected_operation_only": True, "ambiguous_classification": "human", "preserve_implementation": True}}
        self.k = self.artifact("task-contract", kp, [])
        self.kref = {"revision": 0, "path": self.k["path"], "sha256": self.k["sha256"]}
        common = {"mode": "INITIAL", "requirement_ids": ["R"], "interface_ids": [], "forbidden_sources": [], "forbidden_actions": [], "previous_launch": None, "revision_ack_required": False}
        self.tlaunch = self.artifact("test-launch", {**common, "dispatch_id": "test-author", "lane": self.test_lane, "output_path": ".agent-state/test-out.json",
                       "duties": {"author_functional_gate": True, "prevalidate_full_chain": True, "freeze_impact_set": True, "implementation_read_allowed": False, "production_write_allowed": False}}, [self.k])
        self.wlaunch = self.artifact("worker-launch", {**common, "dispatch_id": "worker-build", "lane": self.worker_lane, "output_path": ".agent-state/worker-out.json",
                       "duties": {"tdd": True, "generality": True, "owner_test_read_allowed": False}, "salvage": []}, [self.k])
        self.t = self.commit(self.g, "tests/gate.py", "owner gate")
        self.i = self.commit(self.g, "src/component.py", "implementation zero")
        self.tm = self.manifest(self.t)
        impact = {"schema_version": "1.0", "task": self.task, "task_contract": self.kref,
                  "selected_checks": [{"id": "CHK", "family": "unit", "argv": ["python", "tests/gate.py"], "requirement_ids": ["R"], "covered_paths": ["src/component.py", "tests/gate.py"]}],
                  "excluded_checks": [{"id": "VENDOR", "family": "vendor", "reason": "No vendor surface"}],
                  "public_dependency_edges": [{"from": "src/component.py", "to": "tests/gate.py", "reason": "Direct public interface consumer"}],
                  "prevalidation_obligations": [{"id": mode, "mode": mode, "reason": None} for mode in ["RED", "FULL_CHAIN", "KNOWN_GOOD", "KNOWN_BAD"]]}
        self.impact = self.evidence("impact-set", impact)
        self.tr = self.artifact("test-gate-report", {"dispatch_id": "test-author", "status": "READY", "lane": self.test_lane, "test_tip": self.tip(self.t), "manifest": self.tm,
                   "requirement_coverage": [{"requirement_id": "R", "test_obligation": "Public behavior"}], "impact_set": self.impact,
                   "impact_selection": [{"family": "unit", "disposition": "SELECTED", "dependency_reason": "Direct public consumer"}, {"family": "vendor", "disposition": "EXCLUDED", "dependency_reason": "No vendor surface"}],
                   "prevalidation": [self.run(mode, "FAIL" if mode in {"RED", "KNOWN_BAD"} else "PASS") for mode in ["RED", "FULL_CHAIN", "KNOWN_GOOD", "KNOWN_BAD"]],
                   "revision_ack": None}, [self.tlaunch])
        self.human = self.artifact("human-decision", {"gate": "TEST", "decision": "APPROVE", "subject_sha": self.t, "authority_actor": "Human",
                      "source": {"kind": "human-command", "locator": "public-command", "raw": authority, "created_at": "2026-09-06T01:00:00Z", "updated_at": "2026-09-06T01:00:00Z", "deleted": False}, "reason": None}, [self.tr])
        self.ir = self.implementation(0, self.i, None, self.wlaunch)
        self.c = None

    def git(self, *args, data=None):
        result = subprocess.run(["git", "-C", str(self.root), *args], input=data, capture_output=True, check=True)
        return result.stdout.decode().strip()

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def lane(self, role):
        return {"lane_id": role + "-lane", "agent_session_id": role + "-session", "worktree_id": role + "-tree", "branch": role + "-branch"}

    def commit(self, parent, path, content):
        self.git("read-tree", parent)
        blob = self.git("hash-object", "-w", "--stdin", data=content.encode())
        self.git("update-index", "--add", "--cacheinfo", "100644," + blob + "," + path)
        tree = self.git("write-tree")
        return self.git("commit-tree", tree, "-p", parent, "-m", content)

    def tip(self, commit):
        return {"commit": commit, "parents": self.git("show", "-s", "--format=%P", commit).split(), "tree": self.git("show", "-s", "--format=%T", commit)}

    def evidence(self, kind, value):
        self.serial += 1
        name = ".agent-state/evidence-" + str(self.serial) + ".json"
        raw = value if isinstance(value, bytes) else canonical_bytes(value)
        self.write(name, raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "evidence_type": kind}

    def manifest(self, sha):
        return self.evidence("manifest", {"contract_version": 1, "contract_blob_sha": self.gov["workflow_contract_blob"],
                             "base_sha": self.g, "lane_sha": sha, "requirement_ids": ["R"]})

    def run(self, purpose, outcome="PASS", argv=None):
        body = {"schema_version": "1.0", "argv": argv if argv is not None else ["python", "checks.py"], "cwd": ".", "exit_code": 0 if outcome == "PASS" else 1,
                "outcome": outcome, "environment_id": "synthetic-env"}
        return {"purpose": purpose, **{k: v for k, v in body.items() if k != "schema_version"}, "result": self.evidence("command-result", body)}

    def artifact(self, kind, payload, predecessors, **overrides):
        self.serial += 1
        aid = kind + "-" + str(self.serial)
        spec = load_registry()["artifacts"][kind]
        value = {"schema_version": "1.0", "artifact_kind": kind, "artifact_id": aid, "task": self.task, "workflow_profile": "functional-development-v1",
                 "producer_role": spec["producer"], "consumer_role": spec["consumers"][0], "visibility": spec["visibility"][0], "governor": self.gov,
                 "task_contract": self.kref, "predecessors": predecessors, "replaces": None, "payload": payload, "unresolved": [], **overrides}
        return self.store(value)

    def store(self, value):
        name = ".agent-state/" + value["artifact_id"] + ".json"
        raw = canonical_bytes(value)
        self.write(name, raw)
        ref = {"kind": value["artifact_kind"], "artifact_id": value["artifact_id"], "path": name, "sha256": hashlib.sha256(raw).hexdigest()}
        self.objects[ref["artifact_id"]] = value
        return ref

    def implementation(self, index, sha, previous, predecessor):
        return self.artifact("implementation-report", {"dispatch_id": self.objects[predecessor["artifact_id"]]["payload"]["dispatch_id"],
               "status": "READY", "lane": self.worker_lane, "implementation_index": index, "implementation_tip": self.tip(sha), "previous_implementation": previous,
               "manifest": self.manifest(sha), "changed_paths": [{"path": "src/component.py", "requirement_ids": ["R"], "rationale": "Public implementation"}],
               "requirement_coverage": [{"requirement_id": "R", "implementation_location": "src/component.py"}], "generality": [self.run("TDD")], "revision_ack": None}, [predecessor])

    def candidate(self, index):
        candidate_sha = self.git("commit-tree", self.tip(self.i)["tree"], "-p", self.t, "-p", self.i, "-m", "candidate " + str(index))
        im = self.objects[self.ir["artifact_id"]]["payload"]["manifest"]
        join = self.evidence("coverage-join", {"schema_version": "1.0", "test_commit": self.t, "implementation_commit": self.i, "impact_set_sha256": self.impact["sha256"],
               "changed_paths": [{"path": path, "owner": owner, "requirement_ids": ["R"], "selected_check_ids": ["CHK"]} for path, owner in [("tests/gate.py", "TEST"), ("src/component.py", "IMPLEMENTATION")]]})
        previous = self.c
        self.c = self.artifact("candidate-test-envelope", {"dispatch_id": "candidate-dispatch-" + str(index), "candidate_index": index, "correction_count": index,
                 "candidate": self.tip(candidate_sha), "test_tip": self.tip(self.t), "implementation_tip": self.tip(self.i), "test_manifest": self.tm, "implementation_manifest": im,
                 "impact_set": self.impact, "coverage_join": join, "output_path": ".agent-state/execution.json", "execution_id": "execution-" + str(index),
                 "rerun_of": None, "readonly_candidate": True, "previous_candidate": previous}, [self.human, self.tr, self.ir] + ([previous] if previous else []))
        return self.c

    def report(self, outcome):
        c = self.objects[self.c["artifact_id"]]["payload"]
        impact = json.loads((self.root / c["impact_set"]["path"]).read_text("utf-8"))
        finding = {"id": "finding", "requirement_id": "R", "decision_rule_id": None, "owner_node": "private-node", "assertion": "private-assertion", "case_context": "private-case",
                   "expected": "Public requirement", "observed": "Wrong behavior", "first_divergence": "Public call", "production_location": {"path": "src/component.py", "symbol": "operate", "line": 1},
                   "control_flow": "Incorrect branch", "root_cause": "Public branch selected incorrectly", "confidence_percent": 90, "alternatives": [], "exclusion_evidence": [self.run("diagnostic")["result"]],
                   "responsibility": "IMPLEMENTATION", "affected_surface": ["Public operation"], "unaffected_boundary": ["Other operations"]}
        return self.artifact("tester-confidential-report", {"dispatch_id": c["dispatch_id"], "candidate_index": c["candidate_index"], "candidate_sha": c["candidate"]["commit"],
                 "execution_id": c["execution_id"], "outcome": outcome,
                 "execution": [self.run(check["id"], "FAIL" if outcome == "IMPLEMENTATION_FAIL" else "PASS", check["argv"]) for check in impact["selected_checks"]],
                 "findings": [finding] if outcome == "IMPLEMENTATION_FAIL" else [], "summary": "Execution result"}, [self.c])

    def correction(self, index, report):
        diagnosis = {"id": "diagnosis", "requirement_id": "R", "decision_rule_id": None, "affected_capability": "Public operation", "expected_requirement_ids": ["R"],
                     "observed": "Wrong branch", "first_public_divergence": "Public call", "production_location": {"path": "src/component.py", "symbol": "operate", "line": 1},
                     "control_flow": "Incorrect branch", "root_cause": "Public branch selected incorrectly", "confidence_percent": 90, "alternatives": [],
                     "public_reproduction_authority_id": "A", "required_outcome_requirement_ids": ["R"]}
        disclosure = {"review_id": "disclosure-" + str(index), "source_report_id": report["artifact_id"], "source_report_sha256": report["sha256"], "reviewed_by": "orchestrator",
                      "authority_complete": True, "diagnostic_complete": True, "non_disclosing": True, "anti_fitting": True,
                      "mapping": [{"public_diagnosis_id": "diagnosis", "confidential_finding_id": "finding"}]}
        return self.artifact("worker-correction-envelope", {"dispatch_id": "correction-dispatch-" + str(index), "correction_index": index, "lane": self.worker_lane,
                 "previous_implementation": self.i, "diagnoses": [diagnosis], "disclosure_review": disclosure, "output_path": ".agent-state/correction-out.json"}, [self.ir])

    def terminal(self, report, success, index):
        launch = self.artifact("reviewer-launch", {"dispatch_id": "review-dispatch", "review_id": "review-once", "terminal_reason": "TESTER_PASS" if success else "CORRECTIONS_EXHAUSTED",
                 "candidate": self.objects[self.c["artifact_id"]]["payload"]["candidate"], "last_implementation": self.i, "source_reports": [report], "output_path": ".agent-state/review.json",
                 "review_once": True, "implementation_write_allowed": False, "test_write_allowed": False, "reopen_correction_allowed": False}, [report])
        review = self.artifact("reviewer-report", {"dispatch_id": "review-dispatch", "review_id": "review-once", "verdict": "APPROVED", "findings": [], "lessons": self.evidence("lesson", b"Opaque lesson."),
                  "salvage": []}, [launch])
        return self.artifact("terminal-record", {"result": "SUCCESS" if success else "FAILURE", "review": review, "candidate_index": index, "correction_count": index,
               "accepted_candidate": self.objects[self.c["artifact_id"]]["payload"]["candidate"]["commit"] if success else None, "preserved_implementation": self.i,
               "disposition": "OPEN_SUCCESS_PR" if success else "RECORD_FAILURE", "pr": None, "final_decision": None, "remaining_defects": [] if success else ["Public branch remains incorrect"], "salvage": []}, [review, report])

    def context(self, ref, predecessors=(), central=None):
        value = self.objects[ref["artifact_id"]]
        return {"schema_version": "1.0", "operation_id": "check-" + ref["artifact_id"], "task": self.task, "governor": self.gov,
                "task_contract": value["task_contract"], "consumer_role": value["consumer_role"], "checkpoint": ref["kind"],
                "worktree_root": str(self.root.resolve()), "expected_head": self.g, "predecessor_refs": list(predecessors), "central_check": central}

    def validate(self, ref, predecessors=(), view="orchestrator-full", central=None, result_name=None):
        import structured_handoff
        self.serial += 1
        context = self.write(".agent-state/context-" + str(self.serial) + ".json", canonical_bytes(self.context(ref, predecessors, central)))
        result = self.root / (result_name or ".agent-state/result-" + str(self.serial) + ".json")
        code = structured_handoff.run_validation(str(self.root / ref["path"]), ref["sha256"], str(context), view, str(result))
        return code, json.loads(result.read_text("utf-8")) if code != 2 and result.exists() else None
