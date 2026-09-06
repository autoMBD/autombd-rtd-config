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
# File:        workflow_transition.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Pure transition API and explicit read-only JSON CLI adapter.
# =================================================================================

import copy

from workflow_transition_rules import (Decision, Memory, business_plan, commit, equivalent_ref, history_bodies,
                                       payload, slot_refs)
from workflow_transition_wire import (PROFILE, WorkflowTransitionError, canonical, digest,
    initial_state, json_value, protocol, require, strict_json, validate, wire)


def _artifact_refs(value):
    if type(value) is dict:
        if set(value) == {"kind", "artifact_id", "path", "sha256"}:
            yield value
        else:
            for child in value.values():
                yield from _artifact_refs(child)
    elif type(value) is list:
        for child in value:
            yield from _artifact_refs(child)


def _catalog_shape(context):
    for name in ("artifacts", "checks"):
        identifiers = [x["ref"]["artifact_id"] for x in context[name]]
        require(len(identifiers) == len(set(identifiers)), "MALFORMED_EVENT",
                "/context/" + name)
    artifacts = {x["ref"]["artifact_id"]: x for x in context["artifacts"]}
    for check in context["checks"]:
        other = artifacts.get(check["ref"]["artifact_id"])
        require(other is None or other == check, "MALFORMED_EVENT", "/context/checks")


def _state_invariants(state, context, memory, defs):
    wire(state, "State", "INVALID_STATE")
    require(state["task"] == context["task"] and state["governor"] == context["governor"],
            "INVALID_STATE", "/state/task")
    ids = [x["event_id"] for x in state["consumed"]]
    artifact_ids = [x["artifact"]["artifact_id"] for x in state["consumed"]]
    require(len(ids) == len(set(ids)) and len(artifact_ids) == len(set(artifact_ids)),
            "INVALID_STATE", "/state/consumed")
    consumed = [x["artifact"] for x in state["consumed"]]
    slot_kinds = {
        "/contract": "task-contract", "/stop": "human-decision",
        "/final_decision": "human-decision", "/terminal": "terminal-record",
        "/test/launch": "test-launch", "/test/ack": "test-gate-report",
        "/test/ready": "test-gate-report", "/test/approval": "human-decision",
        "/worker/launch": "worker-launch", "/worker/ack": "implementation-report",
        "/worker/ready": "implementation-report", "/worker/pending_correction": "worker-correction-envelope",
        "/candidate/envelope": "candidate-test-envelope", "/candidate/result": "tester-confidential-report",
        "/review/launch": "reviewer-launch", "/review/report": "reviewer-report"}
    for pointer, ref in slot_refs(state):
        require(ref in consumed, "INVALID_STATE", "/state" + pointer)
        expected = "delivery-repair" if pointer.startswith("/repairs/") else slot_kinds[pointer]
        require(ref["kind"] == expected, "INVALID_STATE", "/state" + pointer)
    for section, key in (("candidate", "envelope"), ("review", "launch")):
        require(state[section] is None or state[section][key] is not None,
                "INVALID_STATE", "/state/" + section)
    for lane in ("test", "worker"):
        require(not (state[lane]["ready"] or state[lane]["ack"]) or state[lane]["launch"],
                "INVALID_STATE", "/state/" + lane + "/launch")
        for slot, status in (("ready", "READY"), ("ack", "K_ACK")):
            body = memory.get(state[lane][slot])
            if body:
                require(payload(body).get("status") == status, "INVALID_STATE",
                        "/state/" + lane + "/" + slot)
    require(not state["test"]["approval"] or state["test"]["ready"], "INVALID_STATE",
            "/state/test/ready")
    require(not state["candidate"] or
            (state["test"]["approval"] and state["test"]["ready"] and state["worker"]["ready"]),
            "INVALID_STATE", "/state/candidate")
    require(not state["worker"]["pending_correction"] or
            (state["candidate"] and state["candidate"]["result"] and state["worker"]["ready"]),
            "INVALID_STATE", "/state/worker/pending_correction")
    require(not state["terminal"] or (state["review"] and state["review"]["report"]),
            "INVALID_STATE", "/state/terminal")
    test = memory.p(state["test"]["ready"])
    impl = memory.p(state["worker"]["ready"])
    approval = memory.p(state["test"]["approval"])
    candidate = memory.p(state["candidate"]["envelope"]) if state["candidate"] else {}
    reviewed = memory.p(state["review"]["launch"]) if state["review"] else {}
    terminal = memory.p(state["terminal"])
    if approval and test:
        require(approval.get("gate") == "TEST" and approval.get("decision") == "APPROVE" and
                approval.get("subject_sha") == commit(test.get("test_tip")), "INVALID_STATE",
                "/state/test/approval")
    if candidate and test:
        require(candidate.get("test_tip") == test.get("test_tip") and
                candidate.get("test_manifest") == test.get("manifest") and
                candidate.get("impact_set") == test.get("impact_set"), "INVALID_STATE",
                "/state/candidate")
    if candidate and impl:
        ci, ii = candidate.get("candidate_index"), impl.get("implementation_index")
        require(type(ci) is int and type(ii) is int and ii in (ci, ci + 1),
                "INVALID_STATE", "/state/worker/ready")
        if ii == ci:
            require(candidate.get("implementation_tip") == impl.get("implementation_tip") and
                    candidate.get("implementation_manifest") == impl.get("manifest"),
                    "INVALID_STATE", "/state/candidate")
        else:
            require(impl.get("previous_implementation") == commit(candidate.get("implementation_tip")),
                    "INVALID_STATE", "/state/worker/ready")
    if reviewed:
        if candidate:
            require(reviewed.get("candidate") == candidate.get("candidate"), "INVALID_STATE",
                    "/state/review/launch")
        if impl:
            require(reviewed.get("last_implementation") == commit(impl.get("implementation_tip")),
                    "INVALID_STATE", "/state/review/launch")
    if terminal:
        require(equivalent_ref(terminal.get("review"), state["review"]["report"], memory), "INVALID_STATE",
                "/state/terminal")
        if impl:
            require(terminal.get("preserved_implementation") == commit(impl.get("implementation_tip")) and
                    terminal.get("correction_count") == impl.get("implementation_index"),
                    "INVALID_STATE", "/state/terminal")

    # Replay available accepted history without I/O or receipts. Missing catalog
    # evidence deliberately defers this proof rather than inventing bad state.
    all_bodies = [memory.get(ref) for ref in consumed]
    if not all(all_bodies):
        return
    rejected_originals = set()
    for body in all_bodies:
        if body.get("replaces"):
            rejected_originals.add(body["replaces"]["original"]["artifact_id"])
        if body.get("artifact_kind") == "delivery-repair":
            rejected_originals.add(body["payload"]["original"]["artifact_id"])
    for body in all_bodies:
        if body["artifact_id"] not in rejected_originals:
            validate(body, defs[body["artifact_kind"]], defs, "INVALID_STATE", "/state/consumed")
        require(body.get("task") == state["task"] and body.get("governor") == state["governor"],
                "INVALID_STATE", "/state/consumed")
    # Dependencies used by lifecycle checks may also be absent. Defer replay in
    # that case, while retaining all shape, slot and uniqueness checks above.
    if any(memory.get(ref) is None for body in all_bodies for ref in _artifact_refs(body)):
        return
    replay = initial_state(state["task"], state["governor"])
    try:
        for item, body in zip(state["consumed"], all_bodies):
            decision = Decision()
            replay = business_plan(replay, body, item["artifact"], memory, decision)
            decision.finish()
            replay["consumed"].append(copy.deepcopy(item))
        require(replay == state, "INVALID_STATE", "/state")
    except WorkflowTransitionError:
        raise WorkflowTransitionError("INVALID_STATE", "/state") from None


def _incoming_identity(state, event, artifact, memory, decision):
    ref = event["artifact"]
    for item in state["consumed"]:
        if item["artifact"]["artifact_id"] == ref["artifact_id"]:
            decision.check(item["artifact"] == ref, "STALE_EVENT", "/event/artifact")
    if artifact:
        decision.check(artifact.get("artifact_id") == ref["artifact_id"] and
                       artifact.get("artifact_kind") == ref["kind"], "STALE_EVENT", "/event/artifact")
    decision.check(not any(x["event_id"] == event["event_id"] or x["artifact"] == ref
                           for x in state["consumed"]), "DUPLICATE_EVENT", "/event/event_id")
    check = memory.get(event["checked"])
    if check:
        trusted = check.get("trusted_context")
        if type(trusted) is dict:
            for key in ("task", "governor"):
                if key in trusted:
                    decision.check(trusted[key] == state[key], "STALE_EVENT",
                                   "/event/checked/trusted_context/" + key)
            if artifact and "task_contract" in trusted:
                decision.check(trusted.get("task_contract") == artifact.get("task_contract"),
                               "STALE_EVENT", "/event/checked/trusted_context/task_contract")


def _evidence(state, event, artifact, memory, defs, decision):
    required_refs = [x["artifact"] for x in state["consumed"]]
    required_refs += [ref for _, ref in slot_refs(state)]
    required_refs += [event["artifact"], event["checked"]]
    if artifact:
        required_refs += list(_artifact_refs(artifact))
    originals = set()
    active_bodies = history_bodies(state, memory) + ([artifact] if artifact else [])
    for body in active_bodies:
        if body.get("replaces"):
            originals.add(body["replaces"]["original"]["artifact_id"])
        if body.get("artifact_kind") == "delivery-repair":
            originals.add(body["payload"]["original"]["artifact_id"])
    for entry in memory.context["artifacts"]:
        decision.check("raw" not in entry or entry["ref"]["artifact_id"] in originals,
                       "INVALID_EVIDENCE", "/context/artifacts/raw")
    checked_ids = set()
    for ref in required_refs:
        token = (ref["artifact_id"], ref["sha256"], ref["path"])
        if token in checked_ids:
            continue
        checked_ids.add(token)
        entry = memory.entry(ref)
        decision.check(entry is not None, "MISSING_EVIDENCE", "/context/catalog")
        if entry is None:
            continue
        decision.check(entry["ref"] == ref, "INVALID_EVIDENCE", "/context/catalog/ref")
        body = entry["body"]
        is_original = ref["artifact_id"] in originals
        if "raw" in entry:
            try:
                import hashlib
                raw = entry["raw"].encode("utf-8")
                parsed = strict_json(raw, "INVALID_EVIDENCE")
                valid = parsed == body and hashlib.sha256(raw).hexdigest() == ref["sha256"]
            except (WorkflowTransitionError, UnicodeError):
                valid = False
            decision.check(is_original and valid, "INVALID_EVIDENCE", "/context/artifacts/raw")
        else:
            decision.check(digest(body) == ref["sha256"], "INVALID_EVIDENCE", "/context/catalog/sha256")
        decision.check(body.get("artifact_id") == ref["artifact_id"] and
                       body.get("artifact_kind") == ref["kind"], "INVALID_EVIDENCE", "/context/catalog/ref")
        if not is_original:
            try:
                validate(body, defs[ref["kind"]], defs, "INVALID_EVIDENCE", "/context/catalog/body")
            except WorkflowTransitionError as error:
                decision.check(False, error.code, error.pointer)
    receipt = memory.get(event["checked"])
    if receipt and artifact:
        expected_input = {k: event["artifact"][k] for k in ("artifact_id", "path", "sha256")}
        expected_trust = {"task": state["task"], "governor": state["governor"],
                          "task_contract": artifact["task_contract"]}
        decision.check(receipt.get("status") == "CHECKED" and
            type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0 and
            receipt.get("evidence_available") is True and receipt.get("violations") == [] and
            receipt.get("input") == expected_input and receipt.get("consumer_role") == artifact["consumer_role"] and
            receipt.get("visibility") == artifact["visibility"] and receipt.get("trusted_context") == expected_trust,
            "INVALID_EVIDENCE", "/event/checked")


def transition(state, event, *, context):
    """Consume one checked artifact, returning a detached complete new state.

    The caller owns loading, durable persistence and real authority. This
    reducer validates only the supplied in-memory identities and evidence.
    """
    try:
        wire(event, "Event", "MALFORMED_EVENT")
        wire(context, "Context", "MALFORMED_EVENT")
        require(event["type"] == "CONSUME" and event["artifact"]["kind"] != "guard-result" and
                event["checked"]["kind"] == "guard-result", "MALFORMED_EVENT", "/event")
        defs = protocol(context)
        _catalog_shape(context)
        memory = Memory(context)
        incoming = memory.get(event["artifact"])
        if incoming:
            validate(incoming, defs[event["artifact"]["kind"]], defs,
                     "MALFORMED_EVENT", "/artifact")
        _state_invariants(state, context, memory, defs)
        decision = Decision()
        _incoming_identity(state, event, incoming, memory, decision)
        output = business_plan(state, incoming, event["artifact"], memory, decision)
        _evidence(state, event, incoming, memory, defs, decision)
        decision.finish()
        output["consumed"].append(copy.deepcopy({"event_id": event["event_id"],
                                                 "artifact": event["artifact"]}))
        try:
            _state_invariants(output, context, memory, defs)
        except WorkflowTransitionError:
            raise WorkflowTransitionError("INVALID_OUTPUT", "/state") from None
        return copy.deepcopy(output)
    except WorkflowTransitionError:
        raise
    except (TypeError, KeyError, IndexError, AttributeError, ValueError, RecursionError):
        raise WorkflowTransitionError("MALFORMED_EVENT", "/") from None


def main(argv=None):
    """Only the explicit CLI adapter reads files; no implicit schema discovery."""
    import argparse
    import sys

    class Parser(argparse.ArgumentParser):
        def error(self, message):
            raise WorkflowTransitionError("USAGE_ERROR", "/arguments", "Invalid command arguments.")

    try:
        parser = Parser(description="Reduce checked workflow artifacts in memory.")
        commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        init = commands.add_parser("init")
        init.add_argument("--task", required=True)
        init.add_argument("--governor", required=True)
        apply = commands.add_parser("apply")
        apply.add_argument("--state", required=True)
        apply.add_argument("--event", required=True)
        apply.add_argument("--context", required=True)
        arguments = parser.parse_args(argv)

        def read(path):
            try:
                with open(path, "rb") as source:
                    return strict_json(source.read())
            except OSError:
                raise WorkflowTransitionError("INPUT_ERROR", "/", "Input file is unavailable.") from None

        if arguments.command == "init":
            result = initial_state(read(arguments.task), read(arguments.governor))
        else:
            state, event, context = read(arguments.state), read(arguments.event), read(arguments.context)
            result = transition(state, event, context=context)
        sys.stdout.buffer.write(canonical(result))
        return 0
    except WorkflowTransitionError as error:
        sys.stderr.buffer.write(canonical(error.as_dict()))
        return 2 if error.code in ("INVALID_OUTPUT", "INPUT_ERROR", "USAGE_ERROR", "EXECUTION_ERROR") else 1
    except Exception:
        sys.stderr.buffer.write(canonical(WorkflowTransitionError("EXECUTION_ERROR").as_dict()))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
