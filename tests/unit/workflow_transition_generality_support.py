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
# File:        workflow_transition_generality_support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Synthetic public-protocol histories for Worker generality.
# =================================================================================

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
SCHEMAS = SCRIPTS.parent / "schemas"


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class History:
    """Generate arbitrary protocol artifacts from public definitions, not cases."""

    def __init__(self, module, seed="cedar"):
        self.module = module
        self.seed = seed
        self.serial = 0
        self.schema = json.loads((SCHEMAS / "handoff-v1.schema.json").read_text())
        self.registry = json.loads((SCHEMAS / "functional-development-v1.json").read_text())
        self.task = {"repository": f"sample/{seed}", "issue_number": len(seed) + 41,
                     "task_run": seed}
        self.governor = {"commit": self.sha("governor"),
                         "workflow_contract_blob": self.sha("workflow"),
                         "workflow_contract_path": "agent-discipline/workflow-contract.json"}
        self.context = {"schema_version": "1.0", "workflow_profile": "functional-development-v1",
                        "task": self.task, "governor": self.governor,
                        "protocol": {"handoff_schema": self.schema, "registry": self.registry,
                                     "workflow_contract": json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text())},
                        "artifacts": [], "checks": []}
        self.state = module.initial_state(self.task, self.governor)
        self.contract = None
        self.refs = {}

    def sha(self, text):
        return hashlib.sha1(f"{self.seed}:{text}".encode()).hexdigest()

    def defaults(self, schema):
        if "$ref" in schema:
            return self.defaults(self.schema["$defs"][schema["$ref"].split("/")[-1]])
        if "const" in schema:
            return copy.deepcopy(schema["const"])
        if "enum" in schema:
            return schema["enum"][0]
        if "anyOf" in schema or "oneOf" in schema:
            return self.defaults(schema.get("anyOf", schema.get("oneOf"))[0])
        kind = schema.get("type")
        if kind == "object":
            return {key: self.defaults(schema["properties"][key]) for key in schema.get("required", [])}
        if kind == "array":
            return [self.defaults(schema["items"]) for _ in range(schema.get("minItems", 0))]
        if kind == "integer":
            return schema.get("minimum", 0)
        if kind == "boolean":
            return False
        if kind == "null":
            return None
        if schema.get("pattern") == "^[0-9a-f]{40}$":
            return self.sha("default")
        if schema.get("pattern") == "^[0-9a-f]{64}$":
            return digest(self.seed)
        if schema.get("format") == "utc-time":
            return "2026-09-06T12:00:00Z"
        if schema.get("format") in {"relative-path", "state-path"}:
            return ".agent-state/example.json"
        return self.seed

    def evidence(self, label, kind="manifest"):
        return {"path": f".agent-state/{self.seed}/{label}.json",
                "sha256": digest(label), "evidence_type": kind}

    def tip(self, label, parents=None):
        return {"commit": self.sha(label), "tree": self.sha(f"tree-{label}"),
                "parents": [self.governor["commit"]] if parents is None else parents}

    def kref(self):
        if self.contract is None:
            return None
        return {"revision": self.body(self.contract)["payload"]["revision"]["number"],
                "path": self.contract["path"], "sha256": self.contract["sha256"]}

    def body(self, ref):
        if ref is None:
            return None
        return next(e["body"] for e in self.context["artifacts"] if e["ref"] == ref)

    def make(self, kind, payload=None, predecessors=None, **overrides):
        self.serial += 1
        value = self.defaults(self.schema["$defs"][kind])
        value.update({"artifact_id": f"{self.seed}-{self.serial}", "task": self.task,
                      "governor": self.governor, "task_contract": self.kref(),
                      "predecessors": predecessors or [], "replaces": None, "unresolved": []})
        value["payload"].update(payload or {})
        value.update(overrides)
        if kind == "task-contract":
            value["task_contract"] = None
        return self.register(value)

    def register(self, body):
        ref = {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"],
               "path": f".agent-state/{self.seed}/{body['artifact_id']}.json", "sha256": digest(body)}
        self.context["artifacts"].append({"ref": ref, "body": body})
        return ref

    def event(self, ref):
        value = self.body(ref)
        receipt = {"schema_version": "1.0", "artifact_kind": "guard-result",
                   "artifact_id": ref["artifact_id"] + "-checked", "producer_role": "guard",
                   "consumer_role": value["consumer_role"], "visibility": value["visibility"],
                   "operation_id": ref["artifact_id"] + "-operation", "phase": "CHECK",
                   "status": "CHECKED", "input": {k: ref[k] for k in ("path", "artifact_id", "sha256")},
                   "trusted_context": {"task": self.task, "governor": self.governor,
                                       "task_contract": value["task_contract"]},
                   "predecessors": value["predecessors"], "command_started": "NOT_STARTED",
                   "violations": [], "exit_code": 0, "evidence_available": True}
        check = {"kind": "guard-result", "artifact_id": receipt["artifact_id"],
                 "path": f".agent-state/{self.seed}/{receipt['artifact_id']}.json",
                 "sha256": digest(receipt)}
        if not any(item["ref"] == check for item in self.context["checks"]):
            self.context["checks"].append({"ref": check, "body": receipt})
        return {"schema_version": "1.0", "type": "CONSUME",
                "event_id": ref["artifact_id"] + "-event", "artifact": ref, "checked": check}

    def consume(self, ref):
        event = self.event(ref)
        before = copy.deepcopy((self.state, event, self.context))
        result = self.module.transition(self.state, event, context=self.context)
        assert (self.state, event, self.context) == before
        self.state = result
        return ref

    def start(self):
        self.contract = self.consume(self.make("task-contract",
            {"revision": {"number": 0, "predecessor": None, "authority": None,
                          "reason": "Synthetic public capability", "changed_authority_ids": [],
                          "affected_requirement_ids": []}}))
        return self.contract

    def launch(self, lane):
        ref = self.make(f"{lane}-launch", {"dispatch_id": f"{self.seed}-{lane}-dispatch",
            "mode": "INITIAL", "lane": {"lane_id": f"{self.seed}-{lane}",
            "agent_session_id": f"{self.seed}-{lane}-session",
            "worktree_id": f"{self.seed}-{lane}-tree", "branch": f"topic/{self.seed}-{lane}"},
            "previous_launch": None, "revision_ack_required": False}, [self.contract])
        self.refs[f"{lane}-launch"] = self.consume(ref)
        return ref

    def ready(self, lane, index=0, previous=None):
        launch = self.state["worker"]["pending_correction"] if lane == "worker" else None
        launch = launch or self.refs[f"{lane}-launch"]
        launch_body = self.body(launch)
        tipkey = "implementation_tip" if lane == "worker" else "test_tip"
        payload = {"dispatch_id": launch_body["payload"]["dispatch_id"], "status": "READY",
                   "lane": launch_body["payload"]["lane"], "revision_ack": None,
                   tipkey: self.tip(f"{lane}-{index}-{self.serial}", [previous] if previous else None),
                   "manifest": self.evidence(f"{lane}-manifest-{self.serial}")}
        if lane == "worker":
            payload.update(implementation_index=index, previous_implementation=previous)
        else:
            payload["impact_set"] = self.evidence(f"impact-{self.serial}", "impact-set")
        ref = self.make("implementation-report" if lane == "worker" else "test-gate-report",
                        payload, [launch])
        self.refs[f"{lane}-ready"] = self.consume(ref)
        return ref

    def approve(self):
        ready = self.refs["test-ready"]
        ref = self.make("human-decision", {"gate": "TEST", "decision": "APPROVE",
            "subject_sha": self.body(ready)["payload"]["test_tip"]["commit"]}, [ready])
        self.refs["approval"] = self.consume(ref)
        return ref

    def candidate(self, rerun=False):
        test = self.body(self.refs["test-ready"])["payload"]
        impl = self.body(self.refs["worker-ready"])["payload"]
        old = self.state["candidate"]["envelope"] if self.state["candidate"] else None
        index = impl["implementation_index"]
        payload = {"dispatch_id": f"{self.seed}-candidate-{self.serial}",
                   "execution_id": f"{self.seed}-execution-{self.serial}", "candidate_index": index,
                   "correction_count": index, "test_tip": test["test_tip"],
                   "implementation_tip": impl["implementation_tip"],
                   "candidate": self.tip(f"candidate-{index}", [test["test_tip"]["commit"],
                                                              impl["implementation_tip"]["commit"]]),
                   "test_manifest": test["manifest"], "implementation_manifest": impl["manifest"],
                   "impact_set": test["impact_set"], "coverage_join": self.evidence(f"join-{index}", "coverage-join"),
                   "previous_candidate": old, "rerun_of": None}
        if rerun:
            payload.update({key: value for key, value in self.body(old)["payload"].items()
                            if key not in {"dispatch_id", "execution_id", "rerun_of"}})
            payload["rerun_of"] = self.state["candidate"]["result"]
        refs = [self.refs["approval"], self.refs["test-ready"], self.refs["worker-ready"]]
        if old:
            refs.append(old)
        if rerun:
            refs.append(self.state["candidate"]["result"])
        ref = self.make("candidate-test-envelope", payload, refs)
        self.refs["candidate"] = self.consume(ref)
        return ref

    def result(self, outcome):
        candidate = self.state["candidate"]["envelope"]
        cp = self.body(candidate)["payload"]
        return self.consume(self.make("tester-confidential-report",
            {"dispatch_id": cp["dispatch_id"], "candidate_index": cp["candidate_index"],
             "candidate_sha": cp["candidate"]["commit"], "execution_id": cp["execution_id"],
             "outcome": outcome}, [candidate]))

    def correction(self):
        report = self.state["candidate"]["result"]
        prior = self.state["worker"]["ready"]
        ip = self.body(prior)["payload"]
        payload = {"dispatch_id": f"{self.seed}-correction-{self.serial}",
                   "correction_index": ip["implementation_index"] + 1, "lane": ip["lane"],
                   "previous_implementation": ip["implementation_tip"]["commit"]}
        ref = self.make("worker-correction-envelope", payload, [prior])
        body = self.body(ref)
        body["payload"]["disclosure_review"]["source_report_id"] = report["artifact_id"]
        body["payload"]["disclosure_review"]["source_report_sha256"] = report["sha256"]
        ref["sha256"] = digest(body)
        return self.consume(ref)

    def stop(self):
        candidate = self.state["candidate"]
        subject = self.body(candidate["envelope"])["payload"]["candidate"]["commit"] if candidate else None
        return self.consume(self.make("human-decision", {"gate": "FINAL", "decision": "STOP",
                                                        "subject_sha": subject}))

    def review(self, reason):
        candidate = self.state["candidate"]
        ready = self.state["worker"]["ready"]
        cp = self.body(candidate["envelope"])["payload"] if candidate else None
        source = self.state["stop"] or (candidate["result"] if candidate else None)
        return self.consume(self.make("reviewer-launch", {
            "dispatch_id": f"{self.seed}-review-dispatch", "review_id": f"{self.seed}-review",
            "terminal_reason": reason, "candidate": cp["candidate"] if cp else None,
            "last_implementation": self.body(ready)["payload"]["implementation_tip"]["commit"] if ready else None,
            "source_reports": [source] if source else []}, [source] if source else []))

    def reviewed(self, verdict="APPROVED"):
        launch = self.state["review"]["launch"]
        p = self.body(launch)["payload"]
        return self.consume(self.make("reviewer-report", {"dispatch_id": p["dispatch_id"],
                           "review_id": p["review_id"], "verdict": verdict}, [launch]))

    def terminal(self, disposition):
        candidate = self.state["candidate"]
        cp = self.body(candidate["envelope"])["payload"] if candidate else None
        ip = self.body(self.state["worker"]["ready"])
        ip = ip["payload"] if ip else None
        success = disposition != "RECORD_FAILURE"
        ref = self.make("terminal-record", {"result": "SUCCESS" if success else "FAILURE",
            "review": self.state["review"]["report"], "candidate_index": cp["candidate_index"] if cp else None,
            "correction_count": ip["implementation_index"] if ip else 0,
            "accepted_candidate": cp["candidate"]["commit"] if success else None,
            "preserved_implementation": ip["implementation_tip"]["commit"] if ip else None,
            "disposition": disposition, "pr": None, "final_decision": self.state["final_decision"]},
            [self.state["review"]["report"]])
        return self.consume(ref)

    def assembled(self, order=("worker", "test")):
        self.start()
        for lane in order:
            self.launch(lane)
            self.ready(lane)
        self.approve()
        return self.candidate()
