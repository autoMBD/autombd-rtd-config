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
# File:        support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Independent real-Git coverage contract fixtures.
# =================================================================================

"""Independent real-Git artifacts for the declared coverage contract.

Synthetic Human records test local binding only and never assert remote authority.
Every source tip/tree/blob comes from Git; command records are actual executions.
"""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = Path(os.environ.get("RTD_COVERAGE_SCRIPTS", ROOT / "agent-discipline/skills/agent-workflow/scripts")).resolve()
sys.path.insert(0, str(SCRIPTS))
from structured_handoff import run_validation
from structured_handoff_refs import ReferenceGraph
from structured_handoff_rules import LocalRules
from structured_handoff_schema import canonical_bytes, load_registry, validate_definition


def canonical(value):
    return canonical_bytes(value)


class Repository:
    def __init__(self, root, version=4, style="split", namespace="amber", overlap=False):
        self.root = root.resolve()
        self.root.mkdir(parents=True)
        self.serial = 0
        self.objects = {}
        self.kref = None
        self.version = version
        self.style = style
        self.git("init", "-q")
        self.git("config", "user.name", "Coverage Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        workflow = json.loads((ROOT / "agent-discipline/workflow-contract.json").read_bytes())
        workflow["contract_version"] = version
        if version < 4:
            workflow.pop("reviewer_lessons")
            workflow["lifecycle"]["pr_head"] = "accepted_candidate"
        if version < 3:
            workflow.pop("non_case_repairs")
        self.write("agent-discipline/workflow-contract.json", canonical(workflow))
        for key in ("artifact_schema", "registry"):
            self.write(workflow[key], (ROOT / workflow[key]).read_bytes())
        self.paths = {"impl": f"{namespace}/component.py", "middle": f"{namespace}/middle.py",
                      "leaf": f"{namespace}/leaf.py", "test": f"checks/{namespace}_gate.py",
                      "review": f"review/{namespace}.md"}
        self.write(self.paths["leaf"], b"VALUE = 11\n")
        self.write(self.paths["middle"], b"from .leaf import VALUE\n")
        self.write(self.paths["impl"], b"from .middle import VALUE\nVALUE += 1\n")
        self.write("checks/oracle.py", b"import sys\nassert int(sys.argv[1]) == 11\n")
        self.git("add", ".")
        self.git("commit", "-qm", "real source governor")
        self.g = self.git("rev-parse", "HEAD")
        self.gov = {"commit": self.g, "workflow_contract_path": "agent-discipline/workflow-contract.json",
                    "workflow_contract_blob": self.git("rev-parse", self.g + ":agent-discipline/workflow-contract.json")}
        self.task = {"repository": "example/coverage", "issue_number": 116, "task_run": "coverage-" + namespace}
        authority = self.evidence("authority", b"Synthetic public source requirement; no actual Human approval.\n")
        kp = {"revision": {"number": 0, "predecessor": None, "authority": None, "reason": "Independent synthetic public contract",
              "changed_authority_ids": [], "affected_requirement_ids": []}, "priority": "P1", "dependencies": [],
              "authorities": [{"id": "A", "source_kind": "repository-file", "locator": "synthetic source fixture", "snapshot": authority}],
              "objective": "Verify declared graph coverage with real source identities",
              "requirements": [{"id": r, "authority_ids": ["A"], "obligation": "Preserve " + r} for r in ("R", "S")],
              "scope": {"included": ["Source graph"], "excluded": []}, "boundaries": [], "interfaces": [], "decision_rules": [],
              "acceptance": [{"id": "AC", "kind": "functional", "requirement_ids": ["R", "S"], "selection_rule": "Declared source and path coverage"}],
              "unknown_policy": {"record_first": True, "bounded_diagnostic": True, "block_affected_operation_only": True,
              "ambiguous_classification": "human", "preserve_implementation": True}}
        self.k = self.artifact("task-contract", kp, [])
        self.kref = {"revision": 0, "path": self.k["path"], "sha256": self.k["sha256"]}
        common = {"mode": "INITIAL", "requirement_ids": ["R", "S"], "interface_ids": [], "forbidden_sources": [],
                  "forbidden_actions": [], "previous_launch": None, "revision_ack_required": False}
        self.tlaunch = self.artifact("test-launch", {**common, "dispatch_id": "author-test", "lane": self.lane("test"),
            "output_path": ".agent-state/test-out.json", "duties": {"author_functional_gate": True, "prevalidate_full_chain": True,
            "freeze_impact_set": True, "implementation_read_allowed": False, "production_write_allowed": False}}, [self.k])
        self.wlaunch = self.artifact("worker-launch", {**common, "dispatch_id": "build-worker", "lane": self.lane("worker"),
            "output_path": ".agent-state/worker-out.json", "duties": {"tdd": True, "generality": True, "owner_test_read_allowed": False},
            "salvage": []}, [self.k])
        self.t = self.commit(self.g, {self.paths["test"]: f"from {namespace}.leaf import VALUE\nassert VALUE == 11\n".encode(),
            self.paths["review"]: b"Review complete source correspondence.\n"})
        impl_changes = {self.paths["impl"]: b"from .middle import VALUE\nVALUE += 2\n"}
        if overlap:
            impl_changes[self.paths["test"]] = b"assert True\n"
        self.i = self.commit(self.g, impl_changes)
        self.git("read-tree", self.i)
        for path in self.changed(self.t):
            row = self.git("ls-tree", self.t, "--", path).split("\t")[0].split()
            self.git("update-index", "--add", "--cacheinfo", row[0] + "," + row[2] + "," + path)
        self.c = self.git("commit-tree", self.git("write-tree"), "-p", self.t, "-p", self.i, "-m", "actual union")
        self.git("reset", "--hard", self.g)
        self.impact_body = self.make_impact(style)
        self.rebind()

    def git(self, *args, data=None):
        result = subprocess.run(["git", "-C", str(self.root), *args], input=data,
                                capture_output=True, timeout=30, check=True)
        return result.stdout.decode("utf-8").strip()

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def commit(self, parent, changes):
        self.git("read-tree", parent)
        for path, raw in changes.items():
            blob = self.git("hash-object", "-w", "--stdin", data=raw)
            self.git("update-index", "--add", "--cacheinfo", "100644," + blob + "," + path)
        return self.git("commit-tree", self.git("write-tree"), "-p", parent, "-m", "source delta")

    def tip(self, sha):
        return {"commit": sha, "tree": self.git("show", "-s", "--format=%T", sha),
                "parents": self.git("show", "-s", "--format=%P", sha).split()}

    def changed(self, sha):
        return self.git("diff", "--name-only", self.g, sha, "--").splitlines()

    def lane(self, role):
        return {"lane_id": role, "agent_session_id": role + "-session", "worktree_id": role + "-tree", "branch": role}

    def evidence(self, kind, value):
        self.serial += 1
        raw = value if isinstance(value, bytes) else canonical(value)
        path = ".agent-state/evidence-" + str(self.serial) + ".json"
        self.write(path, raw)
        return {"path": path, "sha256": hashlib.sha256(raw).hexdigest(), "evidence_type": kind}

    def manifest(self, sha):
        return self.evidence("manifest", {"contract_version": self.version, "contract_blob_sha": self.gov["workflow_contract_blob"],
            "base_sha": self.g, "lane_sha": sha, "requirement_ids": ["R", "S"]})

    def run(self, purpose, bad=False):
        argv = [sys.executable, "checks/oracle.py", "12" if bad else "11"]
        result = subprocess.run(argv, cwd=self.root, capture_output=True, timeout=15)
        body = {"schema_version": "1.0", "argv": argv, "cwd": ".", "exit_code": result.returncode,
                "outcome": "FAIL" if result.returncode else "PASS", "environment_id": "real-local-python"}
        self.evidence("authority", result.stdout + result.stderr)
        return {"purpose": purpose, **{k: v for k, v in body.items() if k != "schema_version"},
                "result": self.evidence("command-result", body)}

    def artifact(self, kind, payload, predecessors):
        spec = load_registry()["artifacts"][kind]
        self.serial += 1
        body = {"schema_version": "1.0", "artifact_kind": kind, "artifact_id": kind + "-" + str(self.serial),
                "task": self.task, "workflow_profile": "functional-development-v1", "producer_role": spec["producer"],
                "consumer_role": spec["consumers"][0], "visibility": spec["visibility"][0], "governor": self.gov,
                "task_contract": self.kref, "predecessors": predecessors, "replaces": None, "payload": payload, "unresolved": []}
        return self.store(body)

    def store(self, body):
        body = copy.deepcopy(body)
        path = ".agent-state/" + body["artifact_id"] + ".json"
        raw = canonical(body)
        self.write(path, raw)
        ref = {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"], "path": path, "sha256": hashlib.sha256(raw).hexdigest()}
        self.objects[ref["artifact_id"]] = body
        return ref

    def make_impact(self, style):
        paths = self.paths
        groups = {"IMPL": [paths["impl"]], "TEST": [paths["test"], paths["review"]],
                  "SUPPORT": [paths["middle"], paths["leaf"]]}
        if style == "shared":
            groups = {"ALL": list(paths.values())}
        elif style == "chain":
            groups = {"FRONT": [paths["impl"], paths["middle"]], "BACK": [paths["leaf"], paths["test"], paths["review"]]}
        return {"schema_version": "1.0", "task": self.task, "task_contract": self.kref,
            "selected_checks": [{"id": key, "family": "functional", "argv": [sys.executable, "checks/oracle.py", "11"],
                "requirement_ids": ["R", "S"], "covered_paths": values} for key, values in groups.items()],
            "excluded_checks": [{"id": "VENDOR", "family": "vendor", "reason": "No vendor behavior"}],
            "public_dependency_edges": [{"from": paths[a], "to": paths[b], "reason": reason} for a, b, reason in (
                ("impl", "middle", "component imports .middle"), ("middle", "leaf", "middle imports .leaf"),
                ("test", "leaf", "gate imports the leaf") )],
            "prevalidation_obligations": [{"id": m, "mode": m, "reason": None} for m in ("RED", "FULL_CHAIN", "KNOWN_GOOD", "KNOWN_BAD")]}

    def rebind(self):
        """Bind fresh unpublished synthetic predecessors after a case input change."""
        self.impact = self.evidence("impact-set", self.impact_body)
        tm, im = self.manifest(self.t), self.manifest(self.i)
        coverage = [{"requirement_id": r, "test_obligation": "Synthetic " + r} for r in ("R", "S")]
        self.tr = self.artifact("test-gate-report", {"dispatch_id": "author-test", "status": "READY", "lane": self.lane("test"),
            "test_tip": self.tip(self.t), "manifest": tm, "requirement_coverage": coverage, "impact_set": self.impact,
            "impact_selection": [{"family": "functional", "disposition": "SELECTED", "dependency_reason": "Declared source checks"},
                {"family": "vendor", "disposition": "EXCLUDED", "dependency_reason": "No vendor behavior"}],
            "prevalidation": [self.run(m, m in {"RED", "KNOWN_BAD"}) for m in ("RED", "FULL_CHAIN", "KNOWN_GOOD", "KNOWN_BAD")],
            "revision_ack": None}, [self.tlaunch])
        self.approval = self.artifact("human-decision", {"gate": "TEST", "decision": "APPROVE", "subject_sha": self.t,
            "authority_actor": "Synthetic owner", "source": {"kind": "human-command", "locator": "synthetic local binding only",
            "raw": self.evidence("authority", b"Synthetic Test approval fixture, not real authority.\n"), "created_at": "2026-09-11T01:00:00Z",
            "updated_at": "2026-09-11T01:00:00Z", "deleted": False}, "reason": None}, [self.tr])
        self.ir = self.artifact("implementation-report", {"dispatch_id": "build-worker", "status": "READY", "lane": self.lane("worker"),
            "implementation_index": 0, "implementation_tip": self.tip(self.i), "previous_implementation": None, "manifest": im,
            "changed_paths": [{"path": p, "requirement_ids": ["R"], "rationale": "Real source delta"} for p in self.changed(self.i)],
            "requirement_coverage": [{"requirement_id": r, "implementation_location": self.paths["impl"]} for r in ("R", "S")],
            "generality": [self.run("REAL_REFERENCE")], "revision_ack": None}, [self.wlaunch])
        self.join_body = {"schema_version": "1.0", "test_commit": self.t, "implementation_commit": self.i,
            "impact_set_sha256": self.impact["sha256"], "changed_paths": [{"path": path, "owner": owner, "requirement_ids": ["R"],
            "selected_check_ids": [c["id"] for c in self.impact_body["selected_checks"] if path in c["covered_paths"]]}
            for owner, tip in (("TEST", self.t), ("IMPLEMENTATION", self.i)) for path in self.changed(tip)]}
        self.envelope = self.artifact("candidate-test-envelope", {"dispatch_id": "execute-c0", "candidate_index": 0, "correction_count": 0,
            "candidate": self.tip(self.c), "test_tip": self.tip(self.t), "implementation_tip": self.tip(self.i), "test_manifest": tm,
            "implementation_manifest": im, "impact_set": self.impact, "coverage_join": self.evidence("coverage-join", self.join_body),
            "output_path": ".agent-state/execution.json", "execution_id": "exec-c0", "rerun_of": None,
            "readonly_candidate": True, "previous_candidate": None}, [self.approval, self.tr, self.ir])

    def replace_join(self, body):
        envelope = copy.deepcopy(self.objects[self.envelope["artifact_id"]])
        envelope["payload"]["coverage_join"] = self.evidence("coverage-join", body)
        self.envelope = self.store(envelope)

    def context(self, ref):
        body = self.objects[ref["artifact_id"]]
        return {"schema_version": "1.0", "operation_id": "check-" + ref["artifact_id"], "task": self.task, "governor": self.gov,
                "task_contract": body["task_contract"], "consumer_role": body["consumer_role"], "checkpoint": ref["kind"],
                "worktree_root": str(self.root), "expected_head": self.g, "predecessor_refs": [], "central_check": None}

    def validate(self, ref=None, *, cli=False, context_change=None, expected_digest=None):
        ref = ref or self.envelope
        self.serial += 1
        context = self.context(ref)
        if context_change:
            context_change(context)
        context_path = self.write(f".agent-state/context-{self.serial}.json", canonical(context))
        result = self.root / f".agent-state/result-{self.serial}.json"
        args = [str(self.root / ref["path"]), expected_digest or ref["sha256"], str(context_path), "orchestrator-full", str(result)]
        if cli:
            argv = [sys.executable, str(SCRIPTS / "handoff_guard.py"), "validate-artifact", "--artifact", args[0],
                    "--expected-sha256", args[1], "--context", args[2], "--view", args[3], "--result", args[4]]
            child = subprocess.run(argv, cwd=self.root, capture_output=True, timeout=60)
            code = child.returncode
        else:
            code = run_validation(*args)
        assert result.is_file(), "The guard did not produce evidence"
        return code, json.loads(result.read_bytes())

    def graph(self):
        graph = ReferenceGraph(self.context(self.envelope), "orchestrator-full")
        graph.verify_environment()
        graph.artifact(self.envelope, allow_private=True)
        return graph

    def source(self, commit, path):
        return {"commit": commit, "path": path, "blob": self.git("rev-parse", commit + ":" + path)}

    def fingerprints(self):
        return {tip: self.git("ls-tree", "-r", tip) for tip in (self.g, self.t, self.i, self.c)}
