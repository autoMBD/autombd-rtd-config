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
# File:        structured_handoff.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Internal structured handoff validation entry point.
# =================================================================================

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from structured_handoff_schema import (
    ProtocolError, canonical_bytes, load_registry, load_schema, parse_json,
    require, validate_artifact, validate_definition, validate_schema,
)
from structured_handoff_refs import ReferenceGraph, safe_path
from structured_handoff_rules import LocalRules


def _central(graph, artifact, input_ref):
    context = graph.context
    ref = context["central_check"]
    require(ref is not None, "CENTRAL_CHECK_REQUIRED")
    result = graph.read(ref, state=True)
    validate_definition(result, "guard-result")
    LocalRules(graph).guard_result(result)
    require(result["status"] == "CHECKED" and result["consumer_role"] == context["consumer_role"], "CENTRAL_CHECK_STATUS")
    require(result["input"] == {"path": input_ref["path"], "artifact_id": artifact["artifact_id"], "sha256": input_ref["sha256"]}, "CENTRAL_CHECK_INPUT")
    expected = {key: context[key] for key in ("task", "governor", "task_contract")}
    require(result["trusted_context"] == expected and result["visibility"] == artifact["visibility"], "CENTRAL_CHECK_CONTEXT")
    if context["consumer_role"] == "worker":
        require(all(graph.worker_allowed(r) for r in result["predecessors"]), "PRIVATE_REFERENCE")
    graph.central_verified = True


def _result(context, input_ref, artifact, phase, code, violation):
    role = context["consumer_role"] if context else "orchestrator"
    visibility = "public-task" if role == "worker" else "orchestrator-confidential"
    if artifact is None and context:
        checkpoint = load_registry()["checkpoints"].get(context["checkpoint"])
        if checkpoint and load_registry()["artifacts"][checkpoint["artifact_kind"]]["visibility"] == ["public-task"]:
            visibility = "public-task"
    if artifact and role != "worker":
        visibility = artifact["visibility"]
    predecessors = artifact.get("predecessors", []) if artifact else []
    if role == "worker":
        registry = load_registry()
        predecessors = [r for r in predecessors if registry["artifacts"][r["kind"]]["worker_readable"]]
    operation = context["operation_id"] if context else "untrusted-input"
    result = {"schema_version": "1.0", "artifact_kind": "guard-result", "artifact_id": operation + "-result",
              "producer_role": "guard", "consumer_role": role, "visibility": visibility,
              "operation_id": operation, "phase": phase,
              "status": {0: "CHECKED", 1: "REJECTED", 2: "EXEC_ERROR", 124: "TIMED_OUT"}[code],
              "input": input_ref, "trusted_context": {key: context[key] for key in ("task", "governor", "task_contract")} if context else None,
              "predecessors": predecessors, "command_started": "NOT_STARTED", "violations": [],
              "exit_code": code, "evidence_available": True}
    if violation:
        # No untrusted strings, private locators or exception text enter public diagnostics.
        result["violations"] = [{"rule_id": violation.rule_id, "field_pointer": "/",
                                  "safe_diagnostic": "The supplied handoff does not satisfy the named protocol rule."}]
    validate_definition(result, "guard-result")
    return result


def _write_result(root, result_path, result):
    path = Path(result_path)
    require(path.is_absolute() and path.is_relative_to(root), "RESULT_PATH")
    relative = path.relative_to(root).as_posix()
    target = safe_path(root, relative, state=True, must_exist=False)
    require(not target.exists() and target.parent.is_dir(), "RESULT_EXISTS")
    # Exclusive creation rejects input/source/hardlink aliases without replacing bytes.
    created = False
    try:
        with target.open("xb") as stream:
            created = True
            stream.write(canonical_bytes(result))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        if created:
            target.unlink(missing_ok=True)
        raise


def run_validation(artifact_path: str, expected_sha256: str,
                   context_path: str, view: str, result_path: str) -> int:
    """Validate one local handoff; never dispatch a role or execute its argv."""
    artifact_path = str(Path(artifact_path).absolute())
    context_path = str(Path(context_path).absolute())
    result_path = str(Path(result_path).absolute())
    context = None
    artifact = None
    identity = {"path": None, "artifact_id": None, "sha256": None}
    phase, code, failure = "PARSE", 0, None
    try:
        context = parse_json(Path(context_path).read_bytes())
        validate_definition(context, "TrustedContext")
        require(view in {"orchestrator-full", "consumer-local"}, "VIEW")
        root = Path(context["worktree_root"])
        context_file = Path(context_path)
        require(context_file.is_absolute() and context_file.is_relative_to(root), "CONTEXT_PATH")
        safe_path(root, context_file.relative_to(root).as_posix(), state=True)
        path = Path(artifact_path)
        require(path.is_absolute() and path.is_relative_to(root), "ARTIFACT_PATH")
        relative = path.relative_to(root).as_posix()
        safe_path(root, relative, state=True)
        identity["path"] = relative
        raw = path.read_bytes()
        identity["sha256"] = hashlib.sha256(raw).hexdigest()
        value = parse_json(raw, expected_sha256)
        phase = "SHAPE"
        validate_artifact(value)
        artifact = value
        identity["artifact_id"] = artifact["artifact_id"]
        graph = ReferenceGraph(context, view)
        phase = "CONTEXT"
        require(artifact["artifact_kind"] != "guard-result", "RESULT_NOT_TASK_INPUT")
        require(artifact["task"] == context["task"] and artifact["governor"] == context["governor"] and artifact["task_contract"] == context["task_contract"], "CONTEXT_IDENTITY")
        require(artifact["consumer_role"] == context["consumer_role"], "CONSUMER_IDENTITY")
        checkpoint = graph.registry["checkpoints"].get(context["checkpoint"])
        require(checkpoint is not None and checkpoint["artifact_kind"] == artifact["artifact_kind"], "CHECKPOINT")
        graph.verify_environment()
        phase = "REFERENCES"
        for ref in context["predecessor_refs"]:
            graph.artifact(ref, allow_private=view == "orchestrator-full")
        input_ref = {"kind": artifact["artifact_kind"], "artifact_id": artifact["artifact_id"], "path": relative, "sha256": expected_sha256}
        if artifact["visibility"] == "public-task" and artifact["consumer_role"] == "worker":
            graph.public_inputs.append(input_ref)
        graph.artifact(input_ref, allow_private=view == "orchestrator-full")
        phase = "CHECK"
        if view == "consumer-local":
            _central(graph, artifact, input_ref)
        rules = LocalRules(graph)
        rules.check(artifact)
    except ProtocolError as exc:
        code, failure = 1, exc
    except subprocess.TimeoutExpired:
        code, failure = 124, ProtocolError("COMMAND_TIMEOUT")
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        code, failure = 2, ProtocolError("EXECUTION_ERROR")
    try:
        require(context is not None, "RESULT_CONTEXT_UNAVAILABLE")
        validate_definition(context, "TrustedContext")
        result = _result(context, identity, artifact, phase, code, failure)
        _write_result(Path(context["worktree_root"]), result_path, result)
    except (ProtocolError, OSError, ValueError, KeyError, TypeError):
        print("Structured handoff result evidence is unavailable; do not consume a receipt from this invocation.", file=sys.stderr)
        return 2
    return code
