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
# File:        isolation_support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-13
# Version:     0.1.0
# Description: Independent W5 controlled-evidence and real Git fixtures.
# =================================================================================


"""Synthetic authorized records exercise real public APIs; no OS-read claim."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
sys.path[:0] = [str(SCRIPTS), str(ROOT / "tests"),
               str(ROOT / "tests/unit"), str(ROOT / "tests/functional"),
               str(ROOT / "tests/fixtures/workflow-environment")]
from structured_handoff_schema import canonical_bytes, load_schema, load_registry
from structured_handoff_fixture import Lifecycle
from workflow_evidence_cases import History
from test_handoff_repair_guard import GuardBridge
import workflow_environment as environment
import workflow_transition as reducer
import workflow_evidence as verifier

G = "b2b8223fbcec45649d25f132d0e9882dfb6e2c24"
LESSONS = "agent-discipline/agent-lessons-learned.md"
PHASES = {
    "orchestration": "orchestrator",
    "implementation": "worker",
    "implementation-correction": "worker",
    "test-authoring": "tester",
    "test-execution": "tester",
    "terminal-review": "reviewer",
    "investigation": "explorer",
    "supervised-documentation": "orchestrator",
    "blackbox-execution": "tester",
}
DISPATCH_PHASES = {
    "worker-launch": "implementation", "test-launch": "test-authoring",
    "worker-correction-envelope": "implementation-correction",
    "candidate-test-envelope": "test-execution", "reviewer-launch": "terminal-review",
}


def digest(value):
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    return hashlib.sha256(raw).hexdigest()


def workflow(version=5):
    value = json.loads((ROOT / "agent-discipline/workflow-contract.json").read_bytes())
    value["contract_version"] = version
    value.pop("isolation_compliance", None)
    value["deferred_runtime_capabilities"] = [
        "transition-executor", "remote-authority-verification", "candidate-direct-union",
        "capability-sandbox", "global-exactly-once", "kpi-profile"]
    if version == 5:
        value["isolation_compliance"] = {"version": "1.0", "enabled": True}
        value["deferred_runtime_capabilities"].remove("capability-sandbox")
    if version < 4:
        value.pop("reviewer_lessons", None)
        value["lifecycle"]["pr_head"] = "accepted_candidate"
    if version == 2:
        value.pop("non_case_repairs", None)
    return value


def capability(name):
    return {"id": name, "context": "host", "status": "available", "approved": True,
            "mode": "host-cli", "evidence_sha256": digest(("controlled " + name).encode())}


def record(root, name, body):
    path = Path(root) / ".agent-state" / (name + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(body)
    path.write_bytes(raw)
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(raw),
            "evidence_type": "operation-log"}


def preflight_inputs(root, *, role="worker", phase="implementation", level="I2",
                     deployed=False, head=None, bindings=None):
    root = Path(root).resolve()
    if bindings is None:
        import subprocess
        head = head or subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
        bindings = {"task_run": "synthetic-isolation", "governor": head,
                    "workflow_blob": "b" * 40, "contract_sha256": "c" * 64,
                    "checkout_root": str(root), "head": head, "candidate_sha256": None}
    selected = (["filesystem-read", "filesystem-write", "agent-cli", "blackbox"]
                if deployed else list(environment.required_capabilities(role)))
    request = {"version": 2, "role": role, "platform": "codex", "bindings": bindings,
               "required_capabilities": [],
               "isolation_scope": {"scope_id": phase, "phase": phase,
                                   "isolation_level": level,
                                   "input_kind": "deployed-inputs" if deployed else "repository"}}
    refs = {}
    for field in ("approved_source_inventory", "context_evidence", "delivery_evidence"):
        refs[field] = record(root, phase + "-" + field, {
            "fixture": "synthetic authorized adapter observation; not OS isolation",
            "actor": role, "phase": phase, "source_head": bindings["head"],
            "root": str(root), "approval": "controlled public fixture authority",
            "target": "deployed skill + fixture + prompt" if deployed else "authorized public source"})
    observations = {"version": 2, "bindings": copy.deepcopy(bindings),
                    "checkout": None if deployed else environment.inspect_checkout(root, expected_head=bindings["head"]),
                    "capabilities": [capability(name) for name in selected],
                    "isolation_evidence": {"clean_context": True, "separate_workspace": True,
                                          "selective_delivery": True,
                                          "development_repository_absent": deployed, **refs}}
    return request, observations


class IsolationHistory(History):
    """Reuse accepted guard/reducer/Git fixture plumbing with K-defined W5 bytes."""

    def __init__(self, root, version=5):
        self.version = version
        self.finding_status = None
        self.bundle_gaps = []
        self.prior_bundle = None
        super().__init__(root)

    def write(self, name, raw):
        if name == "agent-discipline/workflow-contract.json":
            self.git("config", "core.autocrlf", "false")
            Lifecycle.write(self, ".gitignore", b".agent-state/\n")
            Lifecycle.write(self, LESSONS, b"Existing preserved lesson\r\n")
            for key in ("artifact_schema", "registry"):
                path = workflow(self.version)[key]
                Lifecycle.write(self, path, (ROOT / path).read_bytes())
            return Lifecycle.write(self, name, canonical_bytes(workflow(self.version)))
        return Lifecycle.write(self, name, raw)

    def manifest(self, sha):
        return self.evidence("manifest", {"contract_version": self.version,
            "contract_blob_sha": self.gov["workflow_contract_blob"], "base_sha": self.g,
            "lane_sha": sha, "requirement_ids": ["R"]})

    def source_head(self, body):
        p = body["payload"]
        if body["artifact_kind"] == "candidate-test-envelope":
            return p["candidate"]["commit"]
        if body["artifact_kind"] == "reviewer-launch":
            return p["candidate"]["commit"] if p["candidate"] else p["last_implementation"] or self.g
        if body["artifact_kind"] == "worker-correction-envelope":
            return p["previous_implementation"]
        return self.g

    def preflight(self, body, phase):
        head = self.source_head(body)
        self.git("update-ref", "HEAD", head)
        bindings = {"task_run": self.task["task_run"], "governor": self.g,
            "workflow_blob": self.gov["workflow_contract_blob"], "contract_sha256": self.kref["sha256"],
            "checkout_root": str(self.root.resolve()), "head": head,
            "candidate_sha256": head if body["artifact_kind"] in ("candidate-test-envelope", "reviewer-launch")
                                      and body["payload"].get("candidate") else None}
        request, observations = preflight_inputs(self.root, role=PHASES[phase], phase=phase,
                                                 level="I0", bindings=bindings)
        report = environment.evaluate_preflight(request, observations)
        assert report["status"] == "READY", report
        return self.snapshot(self.evidence("operation-log", report))

    def store(self, value):
        kind, p = value.get("artifact_kind"), value.get("payload", {})
        if self.version == 5:
            if kind == "task-contract" and not p["boundaries"]:
                p["boundaries"] = [
                    {"role": role, "ownership": ["Synthetic authorized public fixture"],
                     "forbidden_sources": ["Undelivered confidential fixture"],
                     "forbidden_actions": ["Read an unauthorized source"],
                     "scope_id": phase, "phase": phase, "isolation_level": "I0",
                     "allowed_sources": ["Synthetic public task and selected exact source",
                                         "Explicitly selected public reference outside workspace"],
                     "allowed_actions": ["Exercise declared workflow API on synthetic input"],
                     "capability_limits": ["Explicit I0 fixture; no OS isolation or actual private access"]}
                    for phase, role in PHASES.items()]
            if kind in DISPATCH_PHASES:
                phase = DISPATCH_PHASES[kind]
                existing = p.get("isolation")
                if existing is None or json.loads(existing["preflight"]["raw"])["bindings"]["head"] != self.source_head(value):
                    p["isolation"] = {"scope_id": phase, "preflight": self.preflight(value, phase)}
            if kind == "reviewer-launch" and "isolation_evidence" not in p:
                p["isolation_evidence"] = self.bundle()
            if kind == "reviewer-report" and "isolation_review" not in p:
                snap = self.bundle()
                data = json.loads(snap["raw"])
                p["isolation_review"] = {
                    "assessment": self.assessment(), "evidence": snap,
                    "reviewed_scope_ids": list(PHASES), "finding_ids": [x["id"] for x in data["findings"]],
                    "gaps": list(data["gaps"]), "limits": ["Only supplied controlled records are reviewed."]}
                if self.assessment() != "COMPLIANT":
                    p["verdict"] = "REJECTED"
            if kind == "terminal-record" and "isolation_closeout" not in p:
                review = self.objects[p["review"]["artifact_id"]]["payload"]
                p["isolation_closeout"] = {
                    "review_evidence": review["isolation_review"]["evidence"]["ref"],
                    "supplement": None, "assessment": review["isolation_review"]["assessment"]}
        if self.version >= 4 and kind == "reviewer-report" and "lesson_commit" not in p:
            launch = self.objects[value["predecessors"][0]["artifact_id"]]["payload"]
            if launch["candidate"] is None:
                p["lesson_commit"] = None
            else:
                candidate = launch["candidate"]["commit"]
                # Preserve exact original bytes; git() strips binary output.
                import subprocess
                old = subprocess.check_output(["git", "-C", str(self.root), "show", candidate + ":" + LESSONS])
                complete = old + b"Current synthetic lesson.\n"
                commit = self.commit(candidate, LESSONS, complete.decode())
                p["lesson_commit"] = self.tip(commit)
                p["lessons"] = self.evidence("lesson", complete)
        return Lifecycle.store(self, value)

    def raw_store(self, value):
        return Lifecycle.store(self, value)

    def context(self, ref, predecessors=(), central=None):
        context = super().context(ref, predecessors, central)
        body = self.objects[ref["artifact_id"]]
        if body["artifact_kind"] in DISPATCH_PHASES:
            context["expected_head"] = self.source_head(body)
        else:
            context["expected_head"] = self.git("rev-parse", "HEAD")
        return context

    def validate(self, ref, *args, **kwargs):
        body = self.objects[ref["artifact_id"]]
        if body["artifact_kind"] in DISPATCH_PHASES:
            self.git("update-ref", "HEAD", self.source_head(body))
        return super().validate(ref, *args, **kwargs)

    def context_data(self):
        value = super().context_data()
        value["protocol"]["workflow_contract"] = workflow(self.version)
        return value

    def assessment(self):
        if self.finding_status == "confirmed-violation":
            return "VIOLATION"
        if self.finding_status in ("unauthorized-attempt", "unresolved") or self.bundle_gaps:
            return "INDETERMINATE"
        return "COMPLIANT"

    def bundle(self):
        previous = json.loads(self.prior_bundle["raw"]) if self.prior_bundle else None
        coverage = []
        for phase, role in PHASES.items():
            candidates = [b for b in self.objects.values()
                          if DISPATCH_PHASES.get(b.get("artifact_kind")) == phase]
            launch_body = candidates[-1] if candidates else None
            launch = None
            traces = []
            dispatch = execution = None
            if launch_body:
                launch = {"kind": launch_body["artifact_kind"], "artifact_id": launch_body["artifact_id"],
                          "path": ".agent-state/" + launch_body["artifact_id"] + ".json",
                          "sha256": digest(launch_body)}
                dispatch = launch_body["payload"]["dispatch_id"]
                execution = launch_body["payload"].get("execution_id")
                is_finding_scope = phase == "implementation" and self.finding_status is not None
                target = ("Undelivered confidential fixture" if self.finding_status == "confirmed-violation"
                          else "Explicitly selected public reference outside workspace")
                trace = self.evidence("operation-log", {
                    "records": [{"sequence": 1, "actor_id": role + "-actor", "dispatch_id": dispatch,
                                 "execution_id": execution,
                                 "operation": "synthetic read attempt" if is_finding_scope else "declared synthetic API operation",
                                 "target": target if is_finding_scope else "authorized public fixture",
                                 "result": "denied" if self.finding_status in ("unauthorized-attempt", "unresolved") else "recorded"}],
                    "limits": "Controlled records, not a complete OS audit."})
                old = next((row for row in previous["coverage"] if row["scope_id"] == phase), None) if previous else None
                traces = copy.deepcopy(old["traces"]) if old else []
                traces.append({"evidence": trace, "from_locator": "/records/0", "through_locator": "/records/0"})
            coverage.append({"scope_id": phase, "actor_id": role + "-actor",
                             "dispatch_id": dispatch, "execution_id": execution,
                             "stage_status": "active" if launch else "not-started", "launch": launch,
                             "traces": traces, "gaps": []})
        findings = []
        if self.finding_status:
            row = next(x for x in coverage if x["scope_id"] == "implementation")
            prior_finding = previous["findings"][0] if previous and previous["findings"] else None
            finding_ref = (prior_finding["evidence"] if prior_finding else row["traces"][-1]["evidence"]
                           if row["traces"] else self.evidence("operation-log", b"synthetic operation\n"))
            if self.finding_status == "confirmed-violation" and (not prior_finding or prior_finding["status"] != "confirmed-violation"):
                finding_ref = row["traces"][-1]["evidence"]
            findings = [{"id": "controlled-finding", "status": self.finding_status,
                         "scope_id": "implementation", "actor_id": "worker-actor",
                         "dispatch_id": row["dispatch_id"], "execution_id": None,
                         "clause_pointer": "/payload/boundaries/1/forbidden_actions/0",
                         "evidence": finding_ref, "operation_locator": "/records/0",
                         "conclusion": ("Controlled operation targets the K-forbidden source; confirmed scenario."
                                        if self.finding_status == "confirmed-violation" else
                                        "The selected public external source is explicitly allowed in K; legitimate input."
                                        if self.finding_status == "not-violation" else
                                        "Failed access remains pending semantic authorization review; denial alone is not exoneration.")}]
            if prior_finding and prior_finding["status"] == "confirmed-violation":
                findings = [copy.deepcopy(prior_finding)]
        at = datetime(2026, 9, 13, tzinfo=timezone.utc) + timedelta(seconds=self.serial)
        data = {"version": "1.0", "task": self.task, "governor": self.gov,
                "task_contract": self.kref, "cutoff": {"at": at.isoformat().replace("+00:00", "Z"),
                                                    "last_record": "Recorded synthetic fixture operation " + str(self.serial)},
                "coverage": coverage, "authority_changes": [], "findings": findings,
                "gaps": list(self.bundle_gaps), "limits": ["Only supplied records; no OS observation claim."]}
        self.prior_bundle = self.snapshot(self.evidence("isolation-evidence", data))
        return copy.deepcopy(self.prior_bundle)

    def review_terminal(self, tested=None, *, reason=None, discovery=None):
        reason = reason or ("BOUNDARY_VIOLATION" if self.assessment() == "VIOLATION" else "TESTER_PASS")
        candidate = self.objects[self.c["artifact_id"]]["payload"]["candidate"] if self.c else None
        sources = [tested] if tested else [self.ir]
        predecessors = sources + ([self.c] if candidate and tested is None else [])
        launch = self.artifact("reviewer-launch", {
            "dispatch_id": "review-dispatch", "review_id": "review-once", "terminal_reason": reason,
            "candidate": candidate, "last_implementation": self.i, "source_reports": sources,
            "output_path": ".agent-state/review.json", "review_once": True,
            "implementation_write_allowed": False, "test_write_allowed": False,
            "reopen_correction_allowed": False}, predecessors)
        self.bridge.consume(launch)
        if discovery is not None:
            self.finding_status = discovery
        review = self.artifact("reviewer-report", {
            "dispatch_id": "review-dispatch", "review_id": "review-once", "verdict": "APPROVED",
            "findings": [], "lessons": self.evidence("lesson", b"raw synthetic lesson\n"), "salvage": []}, [launch])
        self.bridge.consume(review)
        return launch, review

    def closeout(self, review, *, success=True, supplement=None):
        candidate = self.objects[self.c["artifact_id"]]["payload"] if self.c else None
        p = self.objects[review["artifact_id"]]["payload"]
        payload = {"result": "SUCCESS" if success else "FAILURE", "review": review,
                   "candidate_index": candidate["candidate_index"] if candidate else None,
                   "correction_count": candidate["correction_count"] if candidate else 0,
                   "accepted_candidate": candidate["candidate"]["commit"] if success else None,
                   "preserved_implementation": self.i,
                   "disposition": "OPEN_SUCCESS_PR" if success else "RECORD_FAILURE",
                   "pr": None, "final_decision": None,
                   "remaining_defects": [] if success else ["Recorded isolation disposition"],
                   "salvage": []}
        if self.version == 5:
            payload["isolation_closeout"] = {
                "review_evidence": p["isolation_review"]["evidence"]["ref"],
                "supplement": supplement,
                "assessment": self.assessment() if supplement else p["isolation_review"]["assessment"]}
        return self.artifact("terminal-record", payload, [review])
