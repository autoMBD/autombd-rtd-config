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
# File:        workflow_evidence.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Read-only exact workflow evidence verification.
# =================================================================================

"""Read-only verification of accepted workflow evidence and finalization."""

import copy
import json
import math
import os
import re
from pathlib import Path

from structured_handoff_schema import ProtocolError
from workflow_evidence_io import EvidenceGraph, WorkflowEvidenceError, require
from workflow_evidence_remote import RemoteProof, github_cli
from workflow_transition import validate_state
from workflow_transition_rules import Memory, latest_support, test_source
from workflow_transition_wire import (WorkflowTransitionError, canonical, digest, json_value,
                                      strict_json, wire, validate)


def _schema():
    path = Path(__file__).resolve().parent.parent / "schemas/workflow-evidence-v1.schema.json"
    return json.loads(path.read_text("utf-8"))["$defs"]


def _inputs(state, context, repository_root, authority, timeout):
    for name, value in (("state", state), ("context", context), ("authority", authority)):
        try:
            json_value(value, "MALFORMED_INPUT", "/" + name)
        except WorkflowTransitionError:
            raise WorkflowEvidenceError("MALFORMED_INPUT", "/" + name) from None
    defs = _schema()
    validate(authority, defs["Authority"], defs, "MALFORMED_INPUT", "/authority")
    require(type(authority) is dict and set(authority) ==
            {"schema_version", "authorized_actors", "base_ref", "packets"}
            and authority["schema_version"] == "1.0", "MALFORMED_INPUT", "/authority")
    actors = authority["authorized_actors"]
    require(type(actors) is list and actors and all(type(a) is str and a.strip() for a in actors)
            and len(actors) == len(set(actors)), "MALFORMED_INPUT", "/authority/authorized_actors")
    require(type(authority["base_ref"]) is str and authority["base_ref"].strip(),
            "MALFORMED_INPUT", "/authority/base_ref")
    packets = authority["packets"]
    require(type(packets) is list, "MALFORMED_INPUT", "/authority/packets")
    ids = []
    for packet in packets:
        require(type(packet) is dict and set(packet) == {"decision_artifact_id", "packet_comment_id"}
                and type(packet["decision_artifact_id"]) is str and re.fullmatch(
                    "[A-Za-z0-9][A-Za-z0-9._-]*", packet["decision_artifact_id"])
                and type(packet["packet_comment_id"]) is int and packet["packet_comment_id"] > 0,
                "MALFORMED_INPUT", "/authority/packets")
        ids.append(packet["decision_artifact_id"])
    require(len(ids) == len(set(ids)), "MALFORMED_INPUT", "/authority/packets")
    require(isinstance(repository_root, (str, os.PathLike)) and
            type(os.fspath(repository_root)) is str and Path(repository_root).is_absolute(),
            "MALFORMED_INPUT", "/repository_root")
    try:
        valid_timeout = type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
    except OverflowError:
        valid_timeout = False
    require(valid_timeout, "MALFORMED_INPUT", "/command_timeout_seconds")
    wire(context, "Context", "MALFORMED_INPUT")
    for value in (state, context):
        require(type(value) is dict and type(value.get("task")) is dict and
                type(value["task"].get("repository")) is str and re.fullmatch(
                    "[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value["task"]["repository"]),
                "MALFORMED_INPUT", "/task/repository")


def verify_evidence(state, *, context, repository_root, authority, github_get=None,
                    command_timeout_seconds=15):
    """Verify explicit evidence without consuming an event or modifying inputs."""
    try:
        _inputs(state, context, repository_root, authority, command_timeout_seconds)
        require(github_get is None or callable(github_get), "MALFORMED_INPUT", "/github_get")
        validate_state(state, context=context)
        root = Path(repository_root).resolve()
        require(root.is_dir(), "MISSING_EVIDENCE", "/repository_root")
        graph = EvidenceGraph(state, context, root, command_timeout_seconds)
        graph.closure()
        graph.sources()
        remote = RemoteProof(graph, authority, github_get)
        human = remote.human()
        finalization = remote.finalization()
        memory = Memory(context)
        ready = memory.p(state["test"]["ready"])
        impl = memory.p(state["worker"]["ready"])
        candidate = memory.p(state["candidate"]["envelope"]) if state["candidate"] else {}
        terminal = memory.p(state["terminal"])
        support = latest_support(state, memory)
        effective = test_source(ready, support, memory) if ready else {}
        contract = state["contract"]
        kref = ({"revision": memory.p(contract)["revision"]["number"],
                 "path": contract["path"], "sha256": contract["sha256"]} if contract else None)
        def sha(payload, key):
            return payload.get(key, {}).get("commit") if payload.get(key) else None
        result = {
            "schema_version": "1.0", "status": "VERIFIED", "task": state["task"],
            "governor": state["governor"], "task_contract": kref,
            "input_sha256": {"state": digest(state), "context": digest(context), "authority": digest(authority)},
            "approved_test_sha": sha(ready, "test_tip") if state["test"]["approval"] else None,
            "effective_test_sha": sha(effective, "test_tip"),
            "executed_test_sha": sha(candidate, "test_tip"),
            "implementation_sha": sha(impl, "implementation_tip"),
            "candidate_sha": sha(candidate, "candidate"),
            "candidate_index": candidate.get("candidate_index"),
            "functional_correction_count": impl.get("implementation_index", 0),
            "accepted_candidate_sha": terminal.get("accepted_candidate"),
            "terminal_disposition": terminal.get("disposition"),
            "checks": {"state": "PASS", "git": "PASS", "human_authority": human,
                       "finalization": finalization}, "remote_evidence": remote.evidence()}
        json_value(result, "EXECUTION_ERROR")
        defs = _schema()
        validate(result, defs["Result"], defs, "EXECUTION_ERROR", "/result")
        return copy.deepcopy(result)
    except WorkflowEvidenceError:
        raise
    except WorkflowTransitionError as error:
        code = "MALFORMED_INPUT" if error.code == "MALFORMED_EVENT" else error.code
        raise WorkflowEvidenceError(code, error.pointer) from None
    except ProtocolError as error:
        code = "MISSING_EVIDENCE" if error.rule_id in {"REFERENCE_MISSING", "DISCLOSURE_SOURCE"} else "INVALID_EVIDENCE"
        raise WorkflowEvidenceError(code, "/evidence") from None
    except Exception:
        raise WorkflowEvidenceError("EXECUTION_ERROR") from None


def main(argv=None):
    import argparse
    import sys

    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise WorkflowEvidenceError("MALFORMED_INPUT", "/arguments")

    try:
        parser = Parser(description="Verify accepted workflow evidence without writes.")
        commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        verify = commands.add_parser("verify")
        for name in ("state", "context", "authority", "repository-root"):
            verify.add_argument("--" + name, required=True)
        verify.add_argument("--github-cli", default="gh")
        verify.add_argument("--command-timeout-seconds", type=float, default=15)
        args = parser.parse_args(argv)
        def read(path):
            try:
                return strict_json(Path(path).read_bytes(), "MALFORMED_INPUT")
            except OSError:
                raise WorkflowEvidenceError("MALFORMED_INPUT", "/inputs") from None
        result = verify_evidence(read(args.state), context=read(args.context),
            repository_root=args.repository_root, authority=read(args.authority),
            github_get=github_cli(args.github_cli, args.command_timeout_seconds),
            command_timeout_seconds=args.command_timeout_seconds)
        sys.stdout.buffer.write(canonical(result))
        return 0
    except WorkflowTransitionError as error:
        failure = WorkflowEvidenceError("MALFORMED_INPUT", error.pointer)
    except WorkflowEvidenceError as error:
        failure = error
    except Exception:
        failure = WorkflowEvidenceError("EXECUTION_ERROR")
    sys.stderr.buffer.write(canonical(failure.as_dict()))
    if failure.code == "COMMAND_TIMEOUT":
        return 124
    return 2 if failure.code in {"MALFORMED_INPUT", "REMOTE_UNAVAILABLE", "EXECUTION_ERROR"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
