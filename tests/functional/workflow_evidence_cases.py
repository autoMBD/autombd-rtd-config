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
# File:        workflow_evidence_cases.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.1
# Description: Owner evidence verifier synthetic Git and transport fixtures.
# =================================================================================

"""Independent real-Git owner fixtures; transport fixtures never authenticate users."""
import copy
import hashlib
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "agent-discipline/skills/agent-workflow/scripts"
sys.path[:0] = [str(SCRIPTS), str(ROOT / "tests"), str(ROOT / "tests/unit")]
from structured_handoff_schema import canonical_bytes, load_schema, load_registry
from structured_handoff_fixture import Lifecycle
from test_handoff_repair_guard import RepairLifecycle, GuardBridge
import workflow_transition

_TARGET_SERIAL = itertools.count()

def canonical(value):
    return canonical_bytes(value)

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def target_path():
    return Path(os.environ.get("RTD_EVIDENCE_TARGET", SCRIPTS / "workflow_evidence.py"))

def load_target():
    path = target_path()
    assert path.is_file(), "R02: the public workflow_evidence.py API does not yet exist"
    name = "owner_workflow_evidence_target_" + str(next(_TARGET_SERIAL))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        assert callable(getattr(module, "verify_evidence", None)), "R02 missing verify_evidence"
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module

def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}

class History(RepairLifecycle):
    """Only synthetic repositories are written; accepted G code is reused."""
    def __init__(self, root):
        self.responses = {}
        self.calls = []
        self.authority = {"schema_version": "1.0", "authorized_actors": ["boundary-owner"],
                          "base_ref": "integration", "packets": []}
        super().__init__(root)
        self.human = self.remote_decision(self.human)
        self.bridge = GuardBridge(self)

    def write(self, name, raw):
        if name == "agent-discipline/workflow-contract.json":
            # Include declared protocol dependencies before the Governor commit.
            workflow = json.loads((ROOT / name).read_bytes())
            for key in ("artifact_schema", "registry"):
                path = workflow[key]
                super().write(path, (ROOT / path).read_bytes())
        if name == "src/component.py" and raw == b"baseline\n":
            super().write("tests/accepted-evidence-fixture.py", b"inherited = True\n")
        return super().write(name, raw)

    def capture_command(self, command=None, *, kind=None, decision=None, reason=None):
        body = copy.deepcopy(self.objects[self.human["artifact_id"]])
        p = body["payload"]
        if decision:
            p.update(decision=decision, reason=reason)
        endpoint = next(e for e, value in self.responses.items()
                        if value["body"]["html_url"] == p["source"]["locator"])
        raw = self.responses[endpoint]["body"]
        raw["body"] = command if command is not None else "/approve-test " + p["subject_sha"]
        p["source"]["raw"] = self.evidence("authority", raw)
        if kind:
            p["source"]["kind"] = kind
        self.human = self.store(body)

    def test_change(self, path, *, operation="add", raw=None):
        self.git("read-tree", self.t)
        if operation == "delete":
            self.git("update-index", "--force-remove", path)
        else:
            blob = self.git("hash-object", "-w", "--stdin", data=raw if raw is not None else b"owner fixture\n")
            mode = {"add": "100644", "execute": "100755", "link": "120000"}[operation]
            self.git("update-index", "--add", "--cacheinfo", mode + "," + blob + "," + path)
        self.t = self.git("commit-tree", self.git("write-tree"), "-p", self.t, "-m", "public Test delta")
        self.tm = self.manifest(self.t)
        impact = json.loads((self.root / self.impact["path"]).read_bytes())
        impact["selected_checks"][0]["covered_paths"].append(path)
        impact["public_dependency_edges"].append({"from": "src/component.py", "to": path,
                                                   "reason": "Exact public Test dependency"})
        self.impact = self.evidence("impact-set", impact)
        report = copy.deepcopy(self.objects[self.tr["artifact_id"]])
        report["payload"].update(test_tip=self.tip(self.t), manifest=self.tm, impact_set=self.impact)
        self.tr = self.store(report)
        human = copy.deepcopy(self.objects[self.human["artifact_id"]])
        human["payload"]["subject_sha"] = self.t
        human["predecessors"] = [self.tr]
        self.human = self.store(human)
        self.capture_command()

    def candidate(self, index):
        ref = Lifecycle.candidate(self, index)
        body = copy.deepcopy(self.objects[ref["artifact_id"]])
        self.git("read-tree", self.i)
        for path in self.git("diff", "--name-only", self.g, self.t).splitlines():
            leaf = self.git("ls-tree", self.t, "--", path)
            if not leaf:
                self.git("update-index", "--force-remove", path)
            else:
                facts, _ = leaf.split("\t", 1)
                mode, _, oid = facts.split()
                self.git("update-index", "--add", "--cacheinfo", mode + "," + oid + "," + path)
        commit = self.git("commit-tree", self.git("write-tree"), "-p", self.t, "-p", self.i,
                          "-m", "direct union candidate " + str(index))
        body["payload"]["candidate"] = self.tip(commit)
        join = json.loads((self.root / body["payload"]["coverage_join"]["path"]).read_bytes())
        join["changed_paths"] = [{"path": path, "owner": owner, "requirement_ids": ["R"],
                                 "selected_check_ids": ["CHK"]}
            for owner, tip in (("TEST", self.t), ("IMPLEMENTATION", self.i))
            for path in self.git("diff", "--name-only", self.g, tip).splitlines()]
        body["payload"]["coverage_join"] = self.evidence("coverage-join", join)
        self.c = self.store(body)
        return self.c

    def context_data(self):
        context = {"schema_version": "1.0", "workflow_profile": "functional-development-v1",
                   "task": self.task, "governor": self.gov,
                   "protocol": {"handoff_schema": load_schema(), "registry": load_registry(),
                                "workflow_contract": json.loads((ROOT / "agent-discipline/workflow-contract.json").read_text())},
                   "artifacts": [], "checks": []}
        for body in self.objects.values():
            path = ".agent-state/" + body["artifact_id"] + ".json"
            ref = {"kind": body["artifact_kind"], "artifact_id": body["artifact_id"],
                   "path": path, "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest()}
            context["checks" if body["artifact_kind"] == "guard-result" else "artifacts"].append(
                {"ref": ref, "body": copy.deepcopy(body)})
        return context

    def remote_decision(self, ref):
        body = copy.deepcopy(self.objects[ref["artifact_id"]])
        p = body["payload"]
        number = 9200 + len(self.authority["packets"]) * 2
        repository, issue = self.task["repository"], self.task["issue_number"]
        packet_id, decision_id = number, number + 1
        minute = 1 + 2 * len(self.authority["packets"])
        packet_time = f"2026-09-09T03:{minute:02d}:00Z"
        decision_time = f"2026-09-09T03:{minute + 1:02d}:00Z"
        gate = "test" if p["gate"] == "TEST" else "candidate"
        command = (f"/approve-{gate} {p['subject_sha']}" if p["decision"] == "APPROVE"
                   else f"/request-{gate}-changes {p['subject_sha']} {p['reason']}")
        raw = {"id": decision_id,
               "html_url": f"https://github.com/{repository}/issues/{issue}#issuecomment-{decision_id}",
               "issue_url": f"https://api.github.com/repos/{repository}/issues/{issue}",
               "url": f"https://api.github.com/repos/{repository}/issues/comments/{decision_id}",
               "user": {"login": "boundary-owner", "type": "User", "id": 3811},
               "body": command, "created_at": decision_time, "updated_at": decision_time,
               "author_association": "OWNER", "reactions": {"total_count": 0}}
        packet = copy.deepcopy(raw)
        packet.update(id=packet_id, body="Review the exact source packet.",
                      html_url=f"https://github.com/{repository}/issues/{issue}#issuecomment-{packet_id}",
                      created_at=packet_time, updated_at=packet_time)
        packet["url"] = f"https://api.github.com/repos/{repository}/issues/comments/{packet_id}"
        for value in (raw, packet):
            self.responses[f"/repos/{repository}/issues/comments/{value['id']}"] = {"status": 200, "body": value}
        p.update(authority_actor="boundary-owner",
                 source={"kind": "github-issue-comment", "locator": raw["html_url"],
                         "raw": self.evidence("authority", raw), "created_at": decision_time,
                         "updated_at": decision_time, "deleted": False})
        self.authority["packets"].append({"decision_artifact_id": body["artifact_id"],
                                          "packet_comment_id": packet_id})
        return self.store(body)

    def get(self, endpoint):
        self.calls.append(endpoint)
        assert endpoint.startswith("/repos/" + self.task["repository"] + "/")
        assert endpoint in self.responses, endpoint
        return copy.deepcopy(self.responses[endpoint])

    def ready(self):
        self.bridge.ready()
        return self

    def candidate_ready(self, *, omitted=False):
        ref = Lifecycle.candidate(self, 0) if omitted else self.candidate(0)
        self.bridge.consume(ref)
        return self

    def correction_ready(self, index, *, assemble=True):
        report = self.report("IMPLEMENTATION_FAIL")
        self.bridge.consume(report)
        correction = self.correction(index, report)
        self.bridge.consume(correction)
        previous = self.i
        self.i = self.commit(self.i, "src/component.py", "incremental public component " + str(index))
        self.ir = self.implementation(index, self.i, previous, correction)
        self.bridge.consume(self.ir)
        if assemble:
            self.bridge.consume(self.candidate(index))
        return self

    def proposal(self, *, success=True):
        report = self.report("PASS" if success else "IMPLEMENTATION_FAIL")
        self.bridge.consume(report)
        index = self.objects[self.c["artifact_id"]]["payload"]["candidate_index"]
        terminal = self.terminal(report, success, index)
        body = copy.deepcopy(self.objects[terminal["artifact_id"]])
        if success:
            body["payload"]["pr"] = {
                "url": f"https://github.com/{self.task['repository']}/pull/73",
                "head_sha": body["payload"]["accepted_candidate"], "merge_sha": None}
            terminal = self.store(body)
            self.responses[f"/repos/{self.task['repository']}/pulls/73"] = {"status": 200, "body": {
                "number": 73, "html_url": body["payload"]["pr"]["url"], "state": "open",
                "merged": False, "merge_commit_sha": None,
                "base": {"ref": "integration", "sha": self.g,
                         "repo": {"full_name": self.task["repository"]}},
                "head": {"sha": body["payload"]["accepted_candidate"],
                         "repo": {"full_name": self.task["repository"]}}}}
        review = body["payload"]["review"]
        launch = self.objects[review["artifact_id"]]["predecessors"][0]
        for ref in (launch, review, terminal):
            self.bridge.consume(ref)
        return self

    def merged(self, *, ff=False, variant="valid"):
        terminal_ref = self.bridge.state["terminal"]
        proposal = self.objects[terminal_ref["artifact_id"]]
        candidate = proposal["payload"]["accepted_candidate"]
        decision = self.artifact("human-decision", {
            "gate": "FINAL", "decision": "APPROVE", "subject_sha": candidate,
            "authority_actor": "boundary-owner",
            "source": {"kind": "human-command", "locator": "captured-command",
                       "raw": self.evidence("authority", b"placeholder"),
                       "created_at": "2026-09-09T03:05:00Z", "updated_at": "2026-09-09T03:05:00Z",
                       "deleted": False}, "reason": None}, [terminal_ref], visibility="terminal-review")
        decision = self.remote_decision(decision)
        self.bridge.consume(decision)
        tree = self.tip(self.i if variant == "extra" else candidate)["tree"]
        parents = ["-p", self.g] if variant == "squash" else [
            "-p", self.i if variant == "wrong-parent" else self.g, "-p", candidate]
        merge = candidate if ff else self.git("commit-tree", tree, *parents, "-m", "merge fixture")
        payload = copy.deepcopy(proposal["payload"])
        payload.update(disposition="MERGED", final_decision=decision)
        payload["pr"]["merge_sha"] = merge
        merged = self.artifact("terminal-record", payload,
                              [payload["review"], terminal_ref, decision], visibility="terminal-review")
        self.bridge.consume(merged)
        remote = self.responses[f"/repos/{self.task['repository']}/pulls/73"]["body"]
        remote.update(state="closed", merged=True, merge_commit_sha=merge)
        remote["base"]["sha"] = self.i  # current base is not the historical premerge base.
        return self

    def support_ready(self, *, execute=False):
        repair = self.support()
        self.bridge.consume(repair)
        if execute:
            self.bridge.consume(self.repaired_candidate(repair))
        return self

    def inputs(self):
        return copy.deepcopy(self.bridge.state), self.context_data(), copy.deepcopy(self.authority)

    def verify(self, api, **kwargs):
        state, context, authority = self.inputs()
        return api.verify_evidence(state, context=context, repository_root=str(self.root.resolve()),
            authority=authority, github_get=self.get, **kwargs)


class ProcessAdapter:
    """Observe the Popen boundary, including cached normal import aliases.

    The injected process is a test transport, not a purported Windows executable.
    Both subprocess.run and direct Popen/communicate use the same adapter.
    """
    def __init__(self, monkeypatch, intercept, *, budget):
        import io
        import math
        import types

        original = subprocess.Popen
        self.records = []

        class InjectedProcess:
            def __init__(self, argv, response, options):
                self.args = argv
                self.returncode = None
                self.response = response
                self.killed = False
                self.text = bool(options.get("text") or options.get("encoding") or options.get("universal_newlines"))
                empty = "" if self.text else b""
                self.output = response.get("stdout", empty)
                self.error = response.get("stderr", empty)
                if self.text:
                    self.output = self.output.decode() if isinstance(self.output, bytes) else self.output
                    self.error = self.error.decode() if isinstance(self.error, bytes) else self.error
                self.stdout = io.StringIO(self.output) if self.text else io.BytesIO(self.output)
                self.stderr = io.StringIO(self.error) if self.text else io.BytesIO(self.error)
                self.stdin = None

            def communicate(self, input=None, timeout=None):
                if self.response.get("timeout") and not self.killed:
                    assert timeout is not None, "The observed blocking operation has no deadline"
                    raise subprocess.TimeoutExpired(self.args, timeout, output=self.output, stderr=self.error)
                if self.returncode is None:
                    self.returncode = self.response.get("returncode", 0)
                return self.output, self.error

            def wait(self, timeout=None):
                if self.response.get("timeout") and not self.killed:
                    assert timeout is not None, "The observed blocking operation has no deadline"
                    raise subprocess.TimeoutExpired(self.args, timeout)
                if self.returncode is None:
                    self.returncode = self.response.get("returncode", 0)
                return self.returncode

            def poll(self):
                if not self.response.get("timeout") and self.returncode is None:
                    self.returncode = self.response.get("returncode", 0)
                return self.returncode

            def kill(self):
                self.killed, self.returncode = True, -9

            def terminate(self):
                self.killed, self.returncode = True, -15

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class ObservedProcess:
            def __init__(self, child, record):
                self.child, self.record = child, record

            def __getattr__(self, name):
                return getattr(self.child, name)

            def deadline(self, timeout):
                if timeout is not None:
                    assert type(timeout) in (int, float) and math.isfinite(timeout)
                    assert 0 < timeout <= budget
                    self.record["timeouts"].append(timeout)

            def communicate(self, *args, **kwargs):
                timeout = kwargs.get("timeout", args[1] if len(args) > 1 else None)
                self.deadline(timeout)
                return self.child.communicate(*args, **kwargs)

            def wait(self, *args, **kwargs):
                timeout = kwargs.get("timeout", args[0] if args else None)
                self.deadline(timeout)
                return self.child.wait(*args, **kwargs)

            def __enter__(self):
                self.child.__enter__()
                return self

            def __exit__(self, *args):
                return self.child.__exit__(*args)

        def launch(*args, **kwargs):
            argv = args[0] if args else kwargs["args"]
            assert isinstance(argv, (list, tuple)), "Process argv must remain explicit"
            response = intercept(argv, kwargs)
            record = {"argv": list(argv), "timeouts": []}
            self.records.append(record)
            child = original(*args, **kwargs) if response is None else InjectedProcess(argv, response, kwargs)
            return ObservedProcess(child, record)

        # Normal "from subprocess import Popen" aliases are part of the same
        # process boundary; no production module names or source are inspected.
        for module in list(sys.modules.values()):
            if not isinstance(module, types.ModuleType):
                continue
            for name, value in list(vars(module).items()):
                if value is original:
                    monkeypatch.setattr(module, name, launch)
