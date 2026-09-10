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
# File:        workflow_evidence_generality_support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Worker-owned real-source workflow evidence generality.
# =================================================================================

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
sys.path[:0] = [str(SCRIPTS), str(ROOT / "tests")]
import workflow_transition
from structured_handoff_fixture import Lifecycle
from workflow_transition_wire import canonical, digest
from test_handoff_repair_guard import RepairLifecycle


class EvidenceHistory(Lifecycle):
    """Public synthetic histories use real Git and explicit fake GET transport."""

    def __init__(self, root):
        self.remote = {}
        self.calls = []
        self.authority = {"schema_version": "1.0", "authorized_actors": ["owner-example"],
                          "base_ref": "integration", "packets": []}
        self.bad_union = False
        super().__init__(root)
        self.objects.pop(self.human["artifact_id"])
        self.human = self.decision("TEST", self.t, [self.tr])
        self.context_data = {
            "schema_version": "1.0", "workflow_profile": "functional-development-v1",
            "task": self.task, "governor": self.gov,
            "protocol": {name: json.loads((ROOT / path).read_text("utf-8")) for name, path in {
                "handoff_schema": "agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json",
                "registry": "agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json",
                "workflow_contract": "agent-discipline/workflow-contract.json"}.items()},
            "artifacts": [], "checks": []}
        self.state = workflow_transition.initial_state(self.task, self.gov)

    def git(self, *args, data=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        result = subprocess.run(["git", "-C", str(self.root), *args], input=data,
                                capture_output=True, check=True, env=env, timeout=15)
        return result.stdout.decode().strip()

    source = RepairLifecycle.source
    snapshot = RepairLifecycle.snapshot
    mapping = RepairLifecycle.mapping
    audit = RepairLifecycle.audit
    support = RepairLifecycle.support
    metadata = RepairLifecycle.metadata
    repaired_candidate = RepairLifecycle.repaired_candidate

    def checked(self, ref):
        return next(e["ref"] for e in self.context_data["checks"]
                    if e["body"]["input"]["artifact_id"] == ref["artifact_id"])

    def write(self, name, raw):
        if name == "agent-discipline/workflow-contract.json":
            raw = (ROOT / name).read_bytes()
            for filename in ("handoff-v1.schema.json", "functional-development-v1.json"):
                schema = "agent-discipline/skills/agent-workflow/schemas/" + filename
                super().write(schema, (ROOT / schema).read_bytes())
        return super().write(name, raw)

    def manifest(self, sha):
        return self.evidence("manifest", {"contract_version": 3,
            "contract_blob_sha": self.gov["workflow_contract_blob"], "base_sha": self.g,
            "lane_sha": sha, "requirement_ids": ["R"]})

    def comment(self, number, body, time="2026-09-08T01:00:00Z"):
        repository = self.task["repository"]
        return {"id": number, "html_url": f"https://github.com/{repository}/issues/{self.task['issue_number']}#issuecomment-{number}",
                "issue_url": f"https://api.github.com/repos/{repository}/issues/{self.task['issue_number']}",
                "user": {"login": "owner-example", "type": "User"}, "body": body,
                "created_at": time, "updated_at": time}

    def decision(self, gate, sha, predecessors, decision="APPROVE", reason=None):
        number = 1700 + self.serial
        word = "test" if gate == "TEST" else "candidate"
        command = f"/approve-{word} {sha}" if decision == "APPROVE" else f"/request-{word}-changes {sha} {reason}"
        raw = self.comment(number, command)
        packet = self.comment(number - 1, "Review packet.", "2026-09-08T00:00:00Z")
        prefix = f"/repos/{self.task['repository']}/issues/comments/"
        self.remote[prefix + str(number)] = {"status": 200, "body": raw}
        self.remote[prefix + str(number - 1)] = {"status": 200, "body": packet}
        ref = self.artifact("human-decision", {"gate": gate, "decision": decision,
            "subject_sha": sha, "authority_actor": "owner-example", "reason": reason,
            "source": {"kind": "github-issue-comment", "locator": raw["html_url"],
                       "raw": self.evidence("authority", raw), "created_at": raw["created_at"],
                       "updated_at": raw["updated_at"], "deleted": False}}, predecessors,
            visibility="tester-confidential" if gate == "TEST" else "terminal-review")
        self.authority["packets"].append({"decision_artifact_id": ref["artifact_id"],
                                         "packet_comment_id": number - 1})
        return ref

    def get(self, endpoint):
        self.calls.append(endpoint)
        return copy.deepcopy(self.remote.get(endpoint, {"status": 404, "body": {}}))

    def sync(self):
        self.context_data["artifacts"] = [{"ref": self.ref(body), "body": copy.deepcopy(body)}
                                         for body in self.objects.values()]

    def ref(self, body):
        return {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"],
                "path": ".agent-state/" + body["artifact_id"] + ".json", "sha256": digest(body)}

    def consume(self, ref):
        self.sync()
        body = self.objects[ref["artifact_id"]]
        receipt = {"schema_version": "1.0", "artifact_kind": "guard-result",
            "artifact_id": ref["artifact_id"] + "-checked", "producer_role": "guard",
            "consumer_role": body["consumer_role"], "visibility": body["visibility"],
            "operation_id": ref["artifact_id"] + "-operation", "phase": "CHECK",
            "status": "CHECKED", "input": {k: ref[k] for k in ("path", "artifact_id", "sha256")},
            "trusted_context": {"task": self.task, "governor": self.gov, "task_contract": body["task_contract"]},
            "predecessors": body["predecessors"], "command_started": "NOT_STARTED",
            "violations": [], "exit_code": 0, "evidence_available": True}
        check = self.ref(receipt)
        self.write(check["path"], canonical(receipt))
        self.context_data["checks"].append({"ref": check, "body": receipt})
        self.state = workflow_transition.transition(self.state,
            {"schema_version": "1.0", "type": "CONSUME", "event_id": ref["artifact_id"] + "-event",
             "artifact": ref, "checked": check}, context=self.context_data)
        return ref

    def start(self, ready=False):
        for ref in (self.k, self.wlaunch, self.tlaunch):
            self.consume(ref)
        if ready:
            for ref in (self.ir, self.tr, self.human):
                self.consume(ref)

    def candidate(self, index):
        ref = super().candidate(index)
        if not self.bad_union:
            self.git("read-tree", self.i)
            for path in self.git("diff", "--name-only", "--no-renames", self.g, self.t).splitlines():
                entry = self.git("ls-tree", self.t, "--", path)
                if entry:
                    mode, kind, rest = entry.split(" ", 2)
                    oid = rest.split("\t", 1)[0]
                    self.git("update-index", "--add", "--cacheinfo", mode + "," + oid + "," + path)
                else:
                    self.git("update-index", "--force-remove", path)
            tree = self.git("write-tree")
            sha = self.git("commit-tree", tree, "-p", self.t, "-p", self.i, "-m", f"union {index}")
            body = self.objects[ref["artifact_id"]]
            body["payload"]["candidate"] = self.tip(sha)
            ref = self.store(body)
            self.c = ref
        return ref

    def change_component(self, mode):
        self.git("read-tree", self.i)
        if mode is None:
            self.git("update-index", "--force-remove", "src/component.py")
        else:
            blob = self.git("hash-object", "-w", "--stdin", data=b"arbitrary component")
            self.git("update-index", "--cacheinfo", mode + "," + blob + ",src/component.py")
        self.i = self.git("commit-tree", self.git("write-tree"), "-p", self.i, "-m", "entry change")
        self.ir = self.implementation(0, self.i, None, self.wlaunch)

    def corrected(self, index):
        failure = self.consume(self.report("IMPLEMENTATION_FAIL"))
        envelope = self.consume(self.correction(index, failure))
        previous = self.i
        self.i = self.commit(previous, "src/component.py", f"generality correction {index}")
        self.ir = self.implementation(index, self.i, previous, envelope)
        self.consume(self.ir)
        return envelope

    def assembled(self):
        self.start(ready=True)
        return self.consume(self.candidate(0))

    def proposal(self):
        self.assembled()
        report = self.consume(self.report("PASS"))
        terminal = super().terminal(report, True, 0)
        review = self.objects[terminal["artifact_id"]]["payload"]["review"]
        launch = self.objects[review["artifact_id"]]["predecessors"][0]
        self.consume(launch)
        self.consume(review)
        body = self.objects[terminal["artifact_id"]]
        candidate = body["payload"]["accepted_candidate"]
        body["payload"]["pr"] = {"url": f"https://github.com/{self.task['repository']}/pull/219",
                                "head_sha": candidate, "merge_sha": None}
        terminal = self.store(body)
        self.remote[f"/repos/{self.task['repository']}/pulls/219"] = {"status": 200, "body": {
            "number": 219, "html_url": body["payload"]["pr"]["url"], "state": "open",
            "merged": False, "merge_commit_sha": None,
            "base": {"ref": "integration", "sha": self.g, "repo": {"full_name": self.task["repository"]}},
            "head": {"sha": candidate, "repo": {"full_name": self.task["repository"]}}}}
        return self.consume(terminal)

    def merged(self, fast_forward=False, squash=False):
        proposal = self.proposal()
        old = self.objects[proposal["artifact_id"]]
        candidate = old["payload"]["accepted_candidate"]
        decision = self.consume(self.decision("FINAL", candidate, [proposal]))
        if fast_forward:
            merge = candidate
        else:
            parents = ["-p", self.g] + ([] if squash else ["-p", candidate])
            merge = self.git("commit-tree", self.tip(candidate)["tree"], *parents, "-m", "final merge")
        p = copy.deepcopy(old["payload"])
        p.update(disposition="MERGED", final_decision=decision)
        p["pr"]["merge_sha"] = merge
        terminal = self.artifact("terminal-record", p, [p["review"], decision, proposal])
        remote = self.remote[f"/repos/{self.task['repository']}/pulls/219"]["body"]
        remote.update(state="closed", merged=True, merge_commit_sha=merge)
        return self.consume(terminal)

    def metadata_for(self, original):
        body = self.objects[original["artifact_id"]]
        op = body["payload"]
        tag = str(self.serial)
        receipt = self.checked(original)
        tip = op.get("candidate") or op.get("test_tip") or op.get("implementation_tip")
        payload = {"repair_version": "1.0", "mode": "METADATA",
            "dispatch_id": "metadata-general-" + tag, "original": original,
            "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": receipt,
                        "observation": "Equivalent descriptive delivery."},
            "lane": op.get("lane", self.test_lane),
            "replacement_output": ".agent-state/general-replacement-" + tag + ".json",
            "reason": "Preserve exact business source and result.",
            "attachment_changes": [], "semantic_audit": self.audit([
                self.source(op["candidate"]["commit"] if op.get("candidate") else self.t, "tests/gate.py")]),
            "preserve_tip": tip["commit"] if tip else None,
            "preserve_candidate_index": op.get("candidate_index"),
            "preserve_correction_count": op.get("correction_count", op.get("implementation_index", 0)),
            "preserve_review_id": op.get("review_id")}
        repair = self.artifact("delivery-repair", payload, [original, receipt],
            consumer_role=body["producer_role"], visibility=body["visibility"])
        replacement = copy.deepcopy(body)
        replacement.update(artifact_id="general-replacement-" + tag,
                           replaces={"original": original, "repair": repair})
        replacement["predecessors"].extend([original, repair])
        if "dispatch_id" in replacement["payload"]:
            replacement["payload"]["dispatch_id"] = payload["dispatch_id"]
        return repair, self.store(replacement)
