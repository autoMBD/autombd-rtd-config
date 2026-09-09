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
# File:        workflow_evidence_io.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.1
# Description: Read-only exact workflow evidence verification.
# =================================================================================

"""Read-only local proof adapter; neither history storage nor an executor."""

import copy
import hashlib
import os
import re
import subprocess
from pathlib import Path

from structured_handoff_refs import ReferenceGraph, safe_path
from structured_handoff_rules import LocalRules
from structured_handoff_schema import ProtocolError
from workflow_transition_rules import Memory
from workflow_transition_wire import WorkflowTransitionError, canonical, digest, strict_json, validate


class WorkflowEvidenceError(ValueError):
    """Safe public failure without confidential source values."""

    def __init__(self, code, pointer="/", message="Workflow evidence requirement not met."):
        super().__init__(message)
        self.code, self.pointer, self.message = code, pointer, message

    def as_dict(self):
        return {"error": {"code": self.code, "pointer": self.pointer, "message": self.message}}


def require(condition, code="INVALID_EVIDENCE", pointer="/evidence"):
    if not condition:
        raise WorkflowEvidenceError(code, pointer)


def process(argv, *, timeout, environment=None, pointer="/repository"):
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout, env=environment)
    except subprocess.TimeoutExpired:
        raise WorkflowEvidenceError("COMMAND_TIMEOUT", pointer) from None
    except OSError:
        raise WorkflowEvidenceError("EXECUTION_ERROR", pointer) from None


class EvidenceGraph(ReferenceGraph):
    def __init__(self, state, context, root, timeout):
        self.state = state
        self.memory = Memory(context)
        self.protocol = context["protocol"]
        self.timeout = timeout
        # Reuse the graph and LocalRules interface, with explicit caller context.
        self.context = {"worktree_root": str(root), "governor": state["governor"],
                        "task": state["task"], "consumer_role": "orchestrator",
                        "predecessor_refs": [item["artifact"] for item in state["consumed"]]}
        self.root = root
        self.view = "orchestrator-full"
        self.registry = self.protocol["registry"]
        self.artifacts, self.refs, self.attachments = {}, {}, {}
        self.artifact_validations, self.loading = set(), set()
        self.verified_tips = {}
        self.private_context_ids = {entry["ref"]["artifact_id"] for entry in context["artifacts"]}
        self.public_inputs = []
        self.central_verified = False
        self.workflow_contract = self.protocol["workflow_contract"]
        self.workflow_version = self.workflow_contract["contract_version"]
        self.git_phase = False
        self.pending_tips = []
        self.tree_cache = {}
        self.commit_cache = set()

    def raw(self, ref, state=False):
        try:
            path = safe_path(self.root, ref["path"], state=state)
            raw = path.read_bytes()
        except ProtocolError as error:
            code = "MISSING_EVIDENCE" if error.rule_id == "REFERENCE_MISSING" else "INVALID_EVIDENCE"
            raise WorkflowEvidenceError(code, "/evidence/local") from None
        except OSError:
            raise WorkflowEvidenceError("MISSING_EVIDENCE", "/evidence/local") from None
        require(hashlib.sha256(raw).hexdigest() == ref["sha256"],
                pointer="/evidence/local/sha256")
        return raw

    def read(self, ref, state=False, canonical=True):
        raw = self.raw(ref, state)
        body = strict_json(raw, "INVALID_EVIDENCE")
        if canonical:
            require(globals()["canonical"](body) == raw, pointer="/evidence/local/canonical")
        return body

    def artifact(self, ref, allow_private=False, repair_original=False):
        entry = self.memory.entry(ref)
        require(entry is not None, "MISSING_EVIDENCE", "/context/catalog")
        require(entry["ref"] == ref, pointer="/context/catalog/ref")
        value = super().artifact(ref, allow_private=allow_private, repair_original=repair_original)
        require(value == entry["body"], pointer="/context/catalog/body")
        if "raw" in entry:
            require(repair_original and entry["raw"].encode("utf-8") == self.raw(ref, True),
                    pointer="/context/catalog/raw")
        else:
            require(digest(value) == ref["sha256"], pointer="/context/catalog/sha256")
        return value

    def evidence(self, ref):
        # The common graph performs normal attachment schemas and snapshot rules.
        self.raw(ref)
        return super().evidence(ref)

    def git_bytes(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_REPLACE_OBJECTS="1",
                   GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")
        result = process(["git", "--no-optional-locks", "-C", str(self.root), *args],
                         timeout=self.timeout, environment=env)
        if args[0] == "merge-base" and result.returncode == 1:
            return b""
        require(result.returncode == 0, "MISSING_EVIDENCE", "/repository/objects")
        return result.stdout

    def git(self, *args):
        try:
            return self.git_bytes(*args).decode("utf-8").strip()
        except UnicodeError:
            raise WorkflowEvidenceError("INVALID_EVIDENCE", "/repository/objects") from None

    def verify_commit(self, sha):
        require(type(sha) is str and re.fullmatch("[0-9a-f]{40}", sha),
                pointer="/repository/commit")
        if sha not in self.commit_cache:
            require(self.git("cat-file", "-t", sha) == "commit", pointer="/repository/commit")
            self.commit_cache.add(sha)

    def tip(self, sha):
        self.verify_commit(sha)
        if sha not in self.verified_tips:
            raw = self.git_bytes("cat-file", "commit", sha)
            headers = raw.split(b"\n\n", 1)[0].split(b"\n")
            try:
                tree = [line[5:].decode("ascii") for line in headers if line.startswith(b"tree ")]
                parents = [line[7:].decode("ascii") for line in headers if line.startswith(b"parent ")]
            except UnicodeError:
                raise WorkflowEvidenceError("INVALID_EVIDENCE", "/repository/tip") from None
            require(len(tree) == 1, pointer="/repository/tip")
            require(self.git("cat-file", "-t", tree[0]) == "tree", pointer="/repository/tree")
            for parent in parents:
                self.verify_commit(parent)
            self.verified_tips[sha] = {"commit": sha, "tree": tree[0], "parents": parents}
        return self.verified_tips[sha]

    def verify_tip(self, tip):
        if not self.git_phase:
            self.pending_tips.append(tip)
            return
        require(tip == self.tip(tip["commit"]), pointer="/repository/tip")

    def strict_ancestor(self, old, new):
        require(old != new, pointer="/repository/ancestry")
        self.ancestor(old, new)

    def ancestor(self, old, new):
        self.verify_commit(old)
        self.verify_commit(new)
        require(self.git("merge-base", "--all", old, new).splitlines() == [old],
                pointer="/repository/ancestry")

    def inventory(self, sha):
        if sha not in self.tree_cache:
            self.verify_commit(sha)
            entries = self.git_bytes("ls-tree", "-r", "-z", "--full-tree", sha)
            value = {}
            try:
                for entry in entries.split(b"\0"):
                    if not entry:
                        continue
                    meta, path = entry.split(b"\t", 1)
                    mode, kind, oid = meta.decode("ascii").split()
                    value[path.decode("utf-8")] = (mode, kind, oid)
            except (UnicodeError, ValueError):
                raise WorkflowEvidenceError("INVALID_EVIDENCE", "/repository/tree") from None
            self.tree_cache[sha] = value
        return self.tree_cache[sha]

    def changed_paths(self, sha):
        before = self.inventory(self.state["governor"]["commit"])
        after = self.inventory(sha)
        return {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}

    def closure(self):
        for item in self.state["consumed"]:
            self.artifact(item["artifact"], allow_private=True)
        for item in self.state["consumed"]:
            ref = item["artifact"]
            body = self.artifacts[ref["artifact_id"]]
            expected = {k: ref[k] for k in ("artifact_id", "path", "sha256")}
            entries = self.memory.context["checks"] + [
                e for e in self.memory.context["artifacts"] if e["ref"]["kind"] == "guard-result"]
            receipts = sorted([e for e in entries if e["body"].get("input") == expected],
                              key=lambda e: canonical(e["ref"]))
            require(receipts, "MISSING_EVIDENCE", "/context/checks")
            trust = {"task": self.state["task"], "governor": self.state["governor"],
                     "task_contract": body["task_contract"]}
            # Recursive closure changes only these containers; cached values
            # are read-only, and Git proof has not started. Publish their
            # additions only after the entire receipt attempt succeeds.
            proof_fields = ("artifacts", "refs", "attachments", "artifact_validations",
                            "loading", "pending_tips")
            for entry in receipts:
                try:
                    r = self.read(entry["ref"], state=True)
                    defs = self.protocol["handoff_schema"]["$defs"]
                    validate(r, defs["guard-result"], defs, "INVALID_EVIDENCE", "/context/checks")
                    require(r == entry["body"] and r["status"] == "CHECKED" and r["trusted_context"] == trust
                            and r["consumer_role"] == body["consumer_role"] and r["visibility"] == body["visibility"]
                            and r["exit_code"] == 0 and r["evidence_available"] is True and r["violations"] == [],
                            pointer="/context/checks")
                    attempt = copy.copy(self)
                    for name in proof_fields:
                        setattr(attempt, name, getattr(self, name).copy())
                    attempt.artifact(entry["ref"], allow_private=True)
                except (WorkflowEvidenceError, WorkflowTransitionError, ProtocolError):
                    continue
                for name in proof_fields:
                    setattr(self, name, getattr(attempt, name))
                break
            else:
                require(False, pointer="/context/checks")

    def sources(self):
        self.git_phase = True
        gov = self.state["governor"]
        require(Path(self.git("rev-parse", "--show-toplevel")).resolve() == self.root,
                pointer="/repository_root")
        self.verify_commit(gov["commit"])
        for key, path in (("workflow_contract", gov["workflow_contract_path"]),
                          ("handoff_schema", self.workflow_contract["artifact_schema"]),
                          ("registry", self.workflow_contract["registry"])):
            oid = self.git("rev-parse", gov["commit"] + ":" + path)
            if key == "workflow_contract":
                require(oid == gov["workflow_contract_blob"], pointer="/governor/workflow_contract_blob")
            require(self.git("cat-file", "-t", oid) == "blob", pointer="/governor")
            actual = strict_json(self.git_bytes("cat-file", "blob", oid), "INVALID_EVIDENCE")
            require(actual == self.protocol[key], pointer="/context/protocol")
        for tip in self.pending_tips:
            self.verify_tip(tip)
        # LocalRules check one delivery in its historical evidence scope. Future
        # equivalent deliveries must not look like extra reviews/executions when
        # rechecking an earlier accepted artifact.
        scoped = EvidenceGraph(self.state, self.memory.context, self.root, self.timeout)
        scoped.git_phase = True
        scoped.verified_tips = self.verified_tips
        scoped.commit_cache = self.commit_cache
        scoped.tree_cache = self.tree_cache
        scoped.attachments = self.attachments
        rules = LocalRules(scoped)
        for item in self.state["consumed"]:
            rules.check(scoped.artifact(item["artifact"], allow_private=True))
        for item in self.state["consumed"]:
            body = self.artifacts[item["artifact"]["artifact_id"]]
            if body["artifact_kind"] == "candidate-test-envelope":
                self.candidate_union(body)
            elif body["artifact_kind"] == "worker-correction-envelope":
                self.diagnosis_bridge(body)

    def candidate_union(self, body):
        p = body["payload"]
        g, t, i, c = (self.state["governor"]["commit"], p["test_tip"]["commit"],
                       p["implementation_tip"]["commit"], p["candidate"]["commit"])
        require(self.tip(c)["parents"] == [t, i], pointer="/candidate/parents")
        self.ancestor(g, t)
        self.ancestor(g, i)
        require(self.git("merge-base", "--all", t, i).splitlines() == [g],
                pointer="/candidate/merge_base")
        before, test, implementation = self.inventory(g), self.inventory(t), self.inventory(i)
        test_paths, implementation_paths = self.changed_paths(t), self.changed_paths(i)
        require(not test_paths & implementation_paths, pointer="/candidate/ownership")
        expected = dict(before)
        for lane, paths in ((test, test_paths), (implementation, implementation_paths)):
            for path in sorted(paths):
                require(not self.temporary_content(path), pointer="/candidate/content")
                if path in lane:
                    expected[path] = lane[path]
                else:
                    expected.pop(path, None)
        require(expected == self.inventory(c), pointer="/candidate/tree")

    def temporary_content(self, path):
        return (path == ".agent-state" or path.startswith(".agent-state/")
                or path == "tests/.tmp" or path.startswith("tests/.tmp/")
                or path == "agent-discipline/agent-lessons-learned.md"
                or any(path == ref_path and kind in {"command-result", "lesson", "disclosure-review"}
                       for ref_path, sha, kind in self.attachments))

    def diagnosis_bridge(self, body):
        p = body["payload"]
        disclosure = p["disclosure_review"]
        source = self.artifacts.get(disclosure["source_report_id"])
        require(source is not None, "MISSING_EVIDENCE", "/correction/source")
        require(self.refs[source["artifact_id"]]["sha256"] == disclosure["source_report_sha256"],
                pointer="/correction/source")
        findings = {f["id"]: f for f in source["payload"]["findings"]
                    if f["responsibility"] == "IMPLEMENTATION"}
        mappings = disclosure["mapping"]
        require({m["confidential_finding_id"] for m in mappings} == set(findings),
                pointer="/correction/disclosure")
        diagnoses = {d["id"]: d for d in p["diagnoses"]}
        for mapping in mappings:
            finding = findings.get(mapping["confidential_finding_id"])
            diagnosis = diagnoses.get(mapping["public_diagnosis_id"])
            require(finding is not None and diagnosis is not None and
                    diagnosis["requirement_id"] == finding["requirement_id"] and
                    diagnosis["production_location"] == finding["production_location"],
                    pointer="/correction/disclosure")
