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
# File:        workflow_transition_cases.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Schema-grounded independent functional history builders.
# =================================================================================

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
SCHEMAS = SCRIPTS.parent / "schemas"
sys.path.insert(0, str(SCRIPTS))
from structured_handoff_schema import validate_schema

PROFILE = "functional-development-v1"


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(label):
    return hashlib.sha1(label.encode()).hexdigest()


def load_protocol():
    return {
        "handoff_schema": json.loads((SCHEMAS / "handoff-v1.schema.json").read_text()),
        "registry": json.loads((SCHEMAS / "functional-development-v1.json").read_text()),
        "workflow_contract": json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text()),
    }


def load_target(path):
    spec = importlib.util.spec_from_file_location("owner_transition_target", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def empty_state(task, governor):
    return {
        "schema_version": "1.0", "workflow_profile": PROFILE,
        "task": copy.deepcopy(task), "governor": copy.deepcopy(governor),
        "contract": None,
        "test": {"launch": None, "ack": None, "ready": None, "approval": None},
        "worker": {"launch": None, "ack": None, "ready": None, "pending_correction": None},
        "candidate": None, "review": None, "stop": None,
        "final_decision": None, "terminal": None, "repairs": [], "consumed": [],
    }


class History:
    """Build public artifacts, never derive expected values from DUT output."""

    def __init__(self, target, seed="copper"):
        self.target = target
        self.seed = seed
        self.serial = 0
        self.protocol = load_protocol()
        self.defs = self.protocol["handoff_schema"]["$defs"]
        self.task = {"repository": "example/" + seed, "issue_number": 407,
                     "task_run": seed + "-run"}
        self.governor = {"commit": sha(seed + "-G"),
                         "workflow_contract_path": "agent-discipline/workflow-contract.json",
                         "workflow_contract_blob": sha(seed + "-W")}
        self.context = {"schema_version": "1.0", "workflow_profile": PROFILE,
                        "task": self.task, "governor": self.governor,
                        "protocol": self.protocol, "artifacts": [], "checks": []}
        self.expected = empty_state(self.task, self.governor)
        self.state = target.initial_state(copy.deepcopy(self.task), copy.deepcopy(self.governor))
        assert self.state == self.expected
        self.last_event = None
        self.steps = []

    def uid(self, tag):
        self.serial += 1
        return f"{self.seed}-{tag}-{self.serial}"

    def sample(self, schema):
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            special = {"ID": "sample-id", "SHA": sha("schema"),
                       "Digest": "d" * 64, "Text": "Public example text",
                       "Path": "sample/file.json", "StatePath": ".agent-state/sample.json",
                       "Time": "2026-09-06T00:00:00Z", "CwdPath": "."}
            return special[name] if name in special else self.sample(self.defs[name])
        if "const" in schema:
            return copy.deepcopy(schema["const"])
        if "enum" in schema:
            return copy.deepcopy(schema["enum"][0])
        if "anyOf" in schema or "oneOf" in schema:
            options = schema.get("anyOf", schema.get("oneOf"))
            null = next((x for x in options if x.get("type") == "null"), None)
            return self.sample(null or options[0])
        kind = schema.get("type")
        if kind == "object":
            return {k: self.sample(schema["properties"][k]) for k in schema.get("required", [])}
        if kind == "array":
            return [self.sample(schema["items"]) for _ in range(schema.get("minItems", 0))]
        if kind == "integer":
            return schema.get("minimum", 0)
        if kind == "boolean":
            return False
        if kind == "null":
            return None
        if kind == "string":
            return "value"
        raise AssertionError(schema)

    def evidence(self, name, kind):
        return {"path": f".agent-state/{self.seed}/{name}.json",
                "sha256": digest({"evidence": name, "seed": self.seed}), "evidence_type": kind}

    def run_evidence(self, outcome="PASS"):
        return {"purpose": "selected-functional", "argv": ["python", "check.py"],
                "cwd": ".", "exit_code": 0 if outcome == "PASS" else 1,
                "outcome": outcome, "result": self.evidence("command", "command-result"),
                "environment_id": self.seed + "-environment"}

    def tip(self, name, parents=None):
        return {"commit": sha(self.seed + name), "tree": sha(self.seed + name + "-tree"),
                "parents": parents if parents is not None else [self.governor["commit"]]}

    def lane(self, role):
        return {"lane_id": self.seed + "-" + role,
                "agent_session_id": self.seed + "-" + role + "-session",
                "worktree_id": self.seed + "-" + role + "-wt",
                "branch": "codex/" + self.seed + "-" + role}

    def body(self, ref):
        return next(x["body"] for x in self.context["artifacts"] if x["ref"] == ref)

    def payload(self, ref):
        return self.body(ref)["payload"]

    def kref(self, ref=None):
        ref = ref or self.expected["contract"]
        if ref is None:
            return None
        return {"path": ref["path"], "sha256": ref["sha256"],
                "revision": self.payload(ref)["revision"]["number"]}

    def artifact(self, kind, payload=None, predecessors=None):
        body = self.sample(self.defs[kind])
        body.update(artifact_id=self.uid(kind), task=copy.deepcopy(self.task),
                    governor=copy.deepcopy(self.governor),
                    task_contract=None if kind == "task-contract" else self.kref(),
                    predecessors=copy.deepcopy(predecessors or []), replaces=None, unresolved=[])
        if kind == "human-decision":
            body["visibility"] = "tester-confidential"
        if kind == "task-contract":
            body["payload"]["authorities"][0].update(id="authority-id",
                snapshot=self.evidence("source-authority", "authority"))
            body["payload"]["requirements"][0].update(id="requirement-id", authority_ids=["authority-id"])
            body["payload"]["acceptance"][0].update(id="acceptance-id", requirement_ids=["requirement-id"])
        if payload:
            body["payload"].update(copy.deepcopy(payload))
        return body

    def ref(self, body):
        return {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"],
                "path": f".agent-state/{self.seed}/{body['artifact_id']}.json",
                "sha256": digest(body)}

    def check(self, body, ref):
        receipt = self.sample(self.defs["guard-result"])
        receipt.update(artifact_id=self.uid("receipt"), consumer_role=body["consumer_role"],
                       visibility=body["visibility"], operation_id=self.uid("operation"),
                       phase="CHECK", status="CHECKED",
                       input={k: ref[k] for k in ("path", "artifact_id", "sha256")},
                       trusted_context={"task": copy.deepcopy(self.task),
                                        "governor": copy.deepcopy(self.governor),
                                        "task_contract": copy.deepcopy(body["task_contract"])},
                       predecessors=copy.deepcopy(body["predecessors"]),
                       command_started="NOT_STARTED", violations=[],
                       exit_code=0, evidence_available=True)
        return receipt

    def event(self, body, validate=True):
        if validate:
            validate_schema(body, self.defs[body["artifact_kind"]], self.defs)
        ref = self.ref(body)
        receipt = self.check(body, ref)
        checkref = self.ref(receipt)
        if not any(x["ref"] == ref for x in self.context["artifacts"]):
            self.context["artifacts"].append({"ref": ref, "body": copy.deepcopy(body)})
        self.context["checks"].append({"ref": checkref, "body": receipt})
        return {"schema_version": "1.0", "type": "CONSUME",
                "event_id": self.uid("event"), "artifact": ref, "checked": checkref}

    def take(self, body, updates, validate=True):
        event = self.event(body, validate)
        before = copy.deepcopy((self.state, event, self.context))
        actual = self.target.transition(self.state, event, context=self.context)
        assert (self.state, event, self.context) == before, "success mutated an input"
        expected = copy.deepcopy(self.expected)
        for path, value in updates.items():
            cursor = expected
            keys = path.split(".")
            for key in keys[:-1]:
                cursor = cursor[key]
            cursor[keys[-1]] = event["artifact"] if value == "@incoming" else copy.deepcopy(value)
        expected["consumed"].append({"event_id": event["event_id"], "artifact": event["artifact"]})
        assert actual == expected
        assert actual is not self.state
        self.expected, self.state = expected, actual
        self.last_event = event
        self.steps.append((before[0], copy.deepcopy(event), copy.deepcopy(self.context), copy.deepcopy(expected)))
        return event["artifact"]

    def reject(self, event, code, pointer_prefix=None, state=None, context=None):
        state = self.state if state is None else state
        context = self.context if context is None else context
        before = copy.deepcopy((state, event, context))
        errors = []
        for _ in range(2):
            try:
                self.target.transition(state, event, context=context)
            except self.target.WorkflowTransitionError as error:
                assert error.code == code, error.as_dict()
                assert isinstance(error.pointer, str) and error.pointer.startswith("/")
                assert isinstance(error.message, str) and error.message
                assert error.as_dict() == {"error": {"code": error.code, "pointer": error.pointer,
                                                    "message": error.message}}
                if pointer_prefix:
                    assert error.pointer.startswith(pointer_prefix), error.as_dict()
                errors.append(error.as_dict())
            else:
                raise AssertionError(f"expected {code}")
            assert (state, event, context) == before, "rejection mutated an input"
        assert errors[0] == errors[1]

    def contract(self, revision=0):
        old = self.expected["contract"]
        body = self.artifact("task-contract")
        body["payload"]["revision"].update(number=revision, predecessor=old,
            authority=self.evidence("revision-authority", "authority") if old else None)
        body["predecessors"] = [old] if old else []
        updates = {"contract": "@incoming"}
        if revision:
            updates.update({"test.ack": None, "worker.ack": None})
        return self.take(body, updates)

    def launch(self, role, revision=False):
        state_role = "test" if role == "tester" else "worker"
        old = self.expected[state_role]["launch"]
        body = self.artifact("test-launch" if role == "tester" else "worker-launch",
            {"dispatch_id": self.uid(role + "-dispatch"), "lane": self.lane(role),
             "mode": "K_REVISION" if revision else "INITIAL",
             "previous_launch": old if revision else None, "revision_ack_required": revision},
            [self.expected["contract"]] + ([old] if revision else []))
        return self.take(body, {state_role + ".launch": "@incoming"})

    def report_body(self, role, status="READY", index=0):
        lane = self.expected["test" if role == "tester" else "worker"]
        parent = lane.get("pending_correction") or lane["launch"]
        payload = {"dispatch_id": self.payload(parent)["dispatch_id"],
                   "lane": self.lane(role), "status": status}
        if role == "tester":
            payload.update(test_tip=self.tip(self.uid("T")) if status == "READY" else None,
                           manifest=self.evidence("test-manifest", "manifest"),
                           impact_set=self.evidence("impact", "impact-set"),
                           prevalidation=[self.run_evidence()] if status == "READY" else [],
                           requirement_coverage=[{"requirement_id": "requirement-id",
                               "test_obligation": "Public synthetic requirement."}])
        else:
            prior = self.payload(lane["ready"])["implementation_tip"]["commit"] if lane["ready"] else None
            payload.update(implementation_index=index,
                implementation_tip=self.tip(self.uid("I"), [prior or self.governor["commit"]])
                    if status == "READY" else None,
                previous_implementation=prior if index else None,
                manifest=self.evidence(self.uid("implementation-manifest"), "manifest"),
                generality=[self.run_evidence()] if status == "READY" else [],
                requirement_coverage=[{"requirement_id": "requirement-id",
                    "implementation_location": "public/module.py"}])
        return self.artifact("test-gate-report" if role == "tester" else "implementation-report",
                             payload, [parent])

    def ready(self, role, index=0):
        body = self.report_body(role, index=index)
        updates = {("test" if role == "tester" else "worker") + ".ready": "@incoming"}
        if role == "worker":
            updates["worker.pending_correction"] = None
        return self.take(body, updates)

    def decision_body(self, gate, decision):
        subject = (self.payload(self.expected["test"]["ready"])["test_tip"]["commit"]
                   if gate == "TEST" and self.expected["test"]["ready"] else
                   self.payload(self.expected["candidate"]["envelope"])["candidate"]["commit"]
                   if gate == "FINAL" and self.expected["candidate"] else None)
        predecessor = self.expected["test"]["ready"] if gate == "TEST" else self.expected["terminal"]
        body = self.artifact("human-decision",
            {"gate": gate, "decision": decision, "subject_sha": subject},
            [predecessor] if predecessor else [])
        body["payload"]["source"]["raw"] = self.evidence("human", "authority")
        body["payload"]["source"]["deleted"] = False
        body["visibility"] = "tester-confidential" if gate == "TEST" else "terminal-review"
        if decision == "REQUEST_CHANGES":
            body["payload"]["reason"] = "Human requests a truthful disposition."
        return body

    def approve(self):
        return self.take(self.decision_body("TEST", "APPROVE"), {"test.approval": "@incoming"})

    def candidate_body(self, rerun=False):
        test = self.payload(self.expected["test"]["ready"])
        worker = self.payload(self.expected["worker"]["ready"])
        old = self.expected["candidate"]["envelope"] if self.expected["candidate"] else None
        index = worker["implementation_index"]
        payload = {"dispatch_id": self.uid("execution-dispatch"), "candidate_index": index,
            "correction_count": index, "candidate": self.tip("C" + str(index),
                [test["test_tip"]["commit"], worker["implementation_tip"]["commit"]]),
            "test_tip": test["test_tip"], "implementation_tip": worker["implementation_tip"],
            "test_manifest": test["manifest"], "implementation_manifest": worker["manifest"],
            "impact_set": test["impact_set"], "coverage_join": self.evidence("join" + str(index), "coverage-join"),
            "execution_id": self.uid("execution"), "rerun_of": self.expected["candidate"]["result"] if rerun else None,
            "previous_candidate": old if index and not rerun else None}
        if rerun:
            prior = self.payload(old)
            for key in payload:
                if key not in {"dispatch_id", "execution_id", "rerun_of"}:
                    payload[key] = copy.deepcopy(prior[key])
        return self.artifact("candidate-test-envelope", payload,
            [self.expected["test"]["approval"], self.expected["test"]["ready"],
             self.expected["worker"]["ready"]] + ([old] if old else []) +
            ([self.expected["candidate"]["result"]] if rerun else []))

    def candidate(self, rerun=False):
        body = self.candidate_body(rerun)
        return self.take(body, {"candidate": {"envelope": self.ref(body), "result": None}})

    def result_body(self, outcome):
        current = self.expected["candidate"]["envelope"]
        candidate = self.payload(current)
        body = self.artifact("tester-confidential-report",
            {"dispatch_id": candidate["dispatch_id"], "candidate_index": candidate["candidate_index"],
             "candidate_sha": candidate["candidate"]["commit"], "execution_id": candidate["execution_id"],
             "outcome": outcome, "summary": "Independent synthetic public outcome."}, [current])
        body["payload"]["execution"] = [self.run_evidence("FAIL" if outcome == "IMPLEMENTATION_FAIL" else "PASS")]
        if outcome == "IMPLEMENTATION_FAIL":
            finding = self.sample(self.defs["ConfidentialFinding"])
            finding["production_location"] = self.sample(self.defs["Location"])
            finding["requirement_id"] = "requirement-id"
            finding["exclusion_evidence"] = [self.evidence("exclusion", "command-result")]
            body["payload"]["findings"] = [finding]
        return body

    def result(self, outcome):
        return self.take(self.result_body(outcome), {"candidate.result": "@incoming"})

    def correction_body(self):
        current = self.expected["candidate"]
        index = self.payload(current["envelope"])["candidate_index"] + 1
        result = current["result"]
        body = self.artifact("worker-correction-envelope",
            {"dispatch_id": self.uid("correction-dispatch"), "correction_index": index,
             "lane": self.lane("worker"),
             "previous_implementation": self.payload(self.expected["worker"]["ready"])["implementation_tip"]["commit"]},
            [self.expected["worker"]["ready"]])
        body["payload"]["disclosure_review"].update(source_report_id=result["artifact_id"],
                                                    source_report_sha256=result["sha256"])
        body["payload"]["diagnoses"][0]["requirement_id"] = "requirement-id"
        return body

    def correct(self):
        return self.take(self.correction_body(), {"worker.pending_correction": "@incoming"})

    def review_body(self, reason):
        current = self.expected["candidate"]
        result = current["result"] if current else None
        ready = self.expected["worker"]["ready"]
        sources = ([self.expected["stop"]] if reason == "HUMAN_STOP" and self.expected["stop"]
                   else [result] if result else [])
        return self.artifact("reviewer-launch",
            {"dispatch_id": self.uid("review-dispatch"), "review_id": self.uid("review"),
             "terminal_reason": reason,
             "candidate": self.payload(current["envelope"])["candidate"] if current else None,
             "last_implementation": self.payload(ready)["implementation_tip"]["commit"] if ready else None,
             "source_reports": sources},
             sources + ([current["envelope"]] if current else []) + ([ready] if ready else []))

    def review(self, reason="TESTER_PASS", verdict="APPROVED"):
        body = self.review_body(reason)
        ref = self.take(body, {"review": {"launch": self.ref(body), "report": None}})
        report = self.artifact("reviewer-report",
            {"dispatch_id": body["payload"]["dispatch_id"], "review_id": body["payload"]["review_id"],
             "verdict": verdict, "lessons": self.evidence("lessons", "lesson")}, [ref])
        return self.take(report, {"review.report": "@incoming"})

    def terminal_body(self, disposition, success=True, pr=None):
        current = self.expected["candidate"]
        cp = self.payload(current["envelope"]) if current else None
        ready = self.expected["worker"]["ready"]
        return self.artifact("terminal-record",
            {"result": "SUCCESS" if success else "FAILURE", "review": self.expected["review"]["report"],
             "candidate_index": cp["candidate_index"] if cp else None,
             "correction_count": self.payload(ready)["implementation_index"] if ready else 0,
             "accepted_candidate": cp["candidate"]["commit"] if success else None,
             "preserved_implementation": self.payload(ready)["implementation_tip"]["commit"] if ready else None,
             "disposition": disposition, "pr": pr, "final_decision": self.expected["final_decision"]},
            [self.expected["review"]["report"]] +
            ([self.expected["final_decision"]] if self.expected["final_decision"] else []))

    def terminal(self, disposition="OPEN_SUCCESS_PR", success=True, pr=None):
        return self.take(self.terminal_body(disposition, success, pr), {"terminal": "@incoming"})

    def prepared(self, order=("tester", "worker")):
        self.contract()
        for role in order:
            self.launch(role)
            self.ready(role)
            if role == "tester":
                self.approve()
        return self.candidate()
