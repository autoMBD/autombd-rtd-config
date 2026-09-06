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
# File:        structured_handoff_refs.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Safe byte-bound references and real Git identity checks.
# =================================================================================

import hashlib
import math
import os
import subprocess
from pathlib import Path

from structured_handoff_schema import (
    ProtocolError, load_registry, parse_json, require, validate_artifact,
    validate_definition,
)

ATTACHMENTS = {"manifest": "LaneManifestV1", "impact-set": "ImpactSet",
               "coverage-join": "CoverageJoin", "command-result": "CommandResult",
               "disclosure-review": "DisclosureReview"}
ARTIFACT_KEYS = {"kind", "artifact_id", "path", "sha256"}
EVIDENCE_KEYS = {"path", "sha256", "evidence_type"}
KREF_KEYS = {"revision", "path", "sha256"}


def safe_path(root, relative, state=False, must_exist=True):
    validate_definition(relative, "StatePath" if state else "Path")
    target = root / relative
    resolved = target.resolve()
    require(resolved.is_relative_to(root), "PATH_ESCAPE")
    current = root
    for part in Path(relative).parts:
        current = current / part
        require(not current.is_symlink() and not (hasattr(current, "is_junction") and current.is_junction()), "PATH_ALIAS")
    require(target == resolved, "PATH_ALIAS")
    if must_exist:
        require(target.is_file(), "REFERENCE_MISSING")
    return target


def command_timeout():
    try:
        seconds = float(os.environ.get("RTD_HANDOFF_GIT_TIMEOUT_SECONDS", "15"))
    except ValueError as exc:
        raise ProtocolError("COMMAND_TIMEOUT_CONFIGURATION") from exc
    require(math.isfinite(seconds) and seconds > 0, "COMMAND_TIMEOUT_CONFIGURATION")
    return seconds


def git_bytes(root, *args):
    timeout = command_timeout()
    environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            timeout=timeout, env=environment)
    require(result.returncode == 0, "GIT_IDENTITY")
    return result.stdout


def git(root, *args):
    return git_bytes(root, *args).decode("utf-8").strip()


class ReferenceGraph:
    def __init__(self, context, view):
        self.context = context
        self.root = Path(context["worktree_root"])
        self.view = view
        self.registry = load_registry()
        self.artifacts = {}
        self.artifact_validations = set()
        self.refs = {}
        self.attachments = {}
        self.loading = set()
        self.verified_tips = {}
        self.private_context_ids = {r["artifact_id"] for r in context["predecessor_refs"]}
        self.public_inputs = []
        self.central_verified = False

    def worker_allowed(self, ref):
        policy = self.registry["artifacts"][ref["kind"]]
        if policy["worker_readable"]:
            return True
        if "worker_conditional_visibility" not in policy:
            return False
        return self.view == "orchestrator-full" or ref in self.context["predecessor_refs"] or ref in self.public_inputs

    def verify_environment(self):
        require(Path(git(self.root, "rev-parse", "--show-toplevel")).resolve() == self.root, "WORKTREE_ROOT")
        require(git(self.root, "rev-parse", "HEAD") == self.context["expected_head"], "HEAD_MISMATCH")
        gov = self.context["governor"]
        require(gov["workflow_contract_path"] == "agent-discipline/workflow-contract.json", "GOVERNOR_PATH")
        self.verify_commit(gov["commit"])
        require(git(self.root, "rev-parse", gov["commit"] + ":" + gov["workflow_contract_path"]) ==
                gov["workflow_contract_blob"], "GOVERNOR_BLOB")
        require(git(self.root, "cat-file", "-t", gov["workflow_contract_blob"]) == "blob", "GOVERNOR_BLOB")
        contract = parse_json(git(self.root, "cat-file", "blob", gov["workflow_contract_blob"]).encode("utf-8"), canonical=False)
        self.workflow_version = contract.get("contract_version")
        require(type(self.workflow_version) is int and self.workflow_version > 0, "GOVERNOR_CONTRACT_VERSION")

    def verify_commit(self, sha):
        validate_definition(sha, "SHA")
        require(git(self.root, "rev-parse", "--verify", sha + "^{commit}") == sha, "GIT_COMMIT")

    def verify_tip(self, tip):
        if tip["commit"] not in self.verified_tips:
            self.verify_commit(tip["commit"])
            actual = git(self.root, "show", "-s", "--format=%T%n%P", tip["commit"]).split("\n")
            self.verified_tips[tip["commit"]] = {"commit": tip["commit"], "tree": actual[0], "parents": actual[1].split() if len(actual) > 1 else []}
        require(tip == self.verified_tips[tip["commit"]], "GIT_TIP")

    def strict_ancestor(self, old, new):
        require(old != new, "STRICT_ANCESTRY")
        self.verify_commit(old)
        self.verify_commit(new)
        require(git(self.root, "merge-base", old, new) == old, "STRICT_ANCESTRY")

    def changed_paths(self, sha):
        raw = git_bytes(self.root, "diff", "--name-only", "-z", self.context["governor"]["commit"], sha, "--")
        return {path.decode("utf-8") for path in raw.split(b"\0") if path}

    def read(self, ref, state=False, canonical=True):
        path = safe_path(self.root, ref["path"], state)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "REFERENCE_DIGEST")
        return parse_json(raw, canonical=canonical)

    def artifact(self, ref, allow_private=False, repair_original=False):
        validate_definition(ref, "ArtifactRef")
        if self.context["consumer_role"] == "worker" and not allow_private:
            require(self.worker_allowed(ref), "PRIVATE_REFERENCE")
        aid = ref["artifact_id"]
        validation = (aid, allow_private, repair_original)
        require(aid not in self.loading, "REFERENCE_CYCLE")
        if aid in self.artifacts:
            require(self.refs[aid] == ref, "ARTIFACT_ID_REUSED")
            if validation in self.artifact_validations:
                return self.artifacts[aid]
        self.loading.add(aid)
        value = self.read(ref, state=True, canonical=not repair_original)
        if not repair_original:
            validate_artifact(value)
        require(value["artifact_kind"] == ref["kind"] and value["artifact_id"] == aid, "REFERENCE_IDENTITY")
        if ref["kind"] != "guard-result":
            require(value["task"] == self.context["task"], "TASK_MISMATCH")
            require(value["governor"] == self.context["governor"], "GOVERNOR_MISMATCH")
        if not allow_private:
            policy = self.registry["artifacts"][ref["kind"]]
            if "worker_conditional_visibility" in policy:
                require(value["visibility"] in policy["worker_conditional_visibility"], "PRIVATE_REFERENCE")
                if ref["kind"] != "guard-result":
                    require(value["consumer_role"] == "worker", "PRIVATE_REFERENCE")
        self.artifacts[aid] = value
        self.refs[aid] = ref
        if not repair_original:
            self.walk(value, public=value.get("visibility") == "public-task",
                      allow_private=allow_private)
        self.artifact_validations.add(validation)
        self.loading.remove(aid)
        return value

    def evidence(self, ref):
        validate_definition(ref, "EvidenceRef")
        key = (ref["path"], ref["sha256"], ref["evidence_type"])
        if key in self.attachments:
            return self.attachments[key]
        path = safe_path(self.root, ref["path"])
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "EVIDENCE_DIGEST")
        if ref["evidence_type"] in ATTACHMENTS:
            value = parse_json(raw, canonical=ref["evidence_type"] != "manifest")
            validate_definition(value, ATTACHMENTS[ref["evidence_type"]])
            self.attachments[key] = value
            self.walk(value, public=False, allow_private=self.view == "orchestrator-full")
            return value
        self.attachments[key] = raw
        return raw

    def walk(self, value, public=False, allow_private=False, repair_original_ref=None):
        if isinstance(value, list):
            for item in value:
                self.walk(item, public, allow_private, repair_original_ref)
        elif isinstance(value, dict):
            keys = set(value)
            if keys == ARTIFACT_KEYS:
                if public:
                    require(self.worker_allowed(value), "PRIVATE_REFERENCE")
                self.artifact(value, allow_private=allow_private and not public,
                              repair_original=value == repair_original_ref)
            elif keys == EVIDENCE_KEYS:
                self.evidence(value)
            elif keys == KREF_KEYS:
                body = self.read(value, state=True)
                require(body.get("artifact_kind") == "task-contract", "KIND_CONTRACT")
                ref = {"kind": "task-contract", "artifact_id": body["artifact_id"], "path": value["path"], "sha256": value["sha256"]}
                contract = self.artifact(ref, allow_private=True)
                require(contract["payload"]["revision"]["number"] == value["revision"], "CONTRACT_REVISION")
            elif keys == {"commit", "parents", "tree"}:
                self.verify_tip(value)
            else:
                is_repair = value.get("artifact_kind") == "delivery-repair"
                original = value["payload"]["original"] if is_repair else (value["replaces"]["original"] if value.get("replaces") else None)
                for name, child in value.items():
                    scoped_original = repair_original_ref
                    if original:
                        scoped_original = original if name in {"predecessors", "replaces"} or (is_repair and name == "payload") else None
                    self.walk(child, public, allow_private, scoped_original)

    def contract(self, artifact):
        if artifact["artifact_kind"] == "task-contract":
            return artifact
        kr = artifact["task_contract"]
        return next(v for aid, v in self.artifacts.items() if self.refs[aid]["path"] == kr["path"] and self.refs[aid]["sha256"] == kr["sha256"])

    def direct(self, artifact, kind):
        return [self.artifacts[r["artifact_id"]] for r in artifact["predecessors"] if r["kind"] == kind]

    def one(self, artifact, kind, predicate=lambda value: True):
        matches = [v for v in self.direct(artifact, kind) if predicate(v)]
        require(len(matches) == 1, "PREDECESSOR_REQUIRED")
        return matches[0]

    def same_k(self, first, second):
        require(first["task_contract"] == second["task_contract"], "CONTRACT_FROZEN")
