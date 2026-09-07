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
# File:        workflow_transition_wire.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Pure JSON, schema and wire checks for workflow transitions.
# =================================================================================

import copy
import hashlib
import json
import re
from datetime import datetime

PROFILE = "functional-development-v1"
WORKFLOW_PATH = "agent-discipline/workflow-contract.json"
KINDS = ("task-contract", "test-launch", "worker-launch", "test-gate-report",
         "implementation-report", "human-decision", "candidate-test-envelope",
         "tester-confidential-report", "worker-correction-envelope", "reviewer-launch",
         "reviewer-report", "terminal-record", "delivery-repair", "guard-result")


class WorkflowTransitionError(ValueError):
    """A deterministic public rejection, never a copy of private diagnostics."""

    def __init__(self, code, pointer="/", message="Workflow requirement not met."):
        super().__init__(message)
        self.code, self.pointer, self.message = code, pointer, message

    def as_dict(self):
        return {"error": {"code": self.code, "pointer": self.pointer, "message": self.message}}


def require(condition, code, pointer="/", message="Workflow requirement not met."):
    if not condition:
        raise WorkflowTransitionError(code, pointer, message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def json_value(value, code, pointer="/", ancestors=None):
    """Only JSON-native types; reject cycles, non-string keys and all floats."""
    ancestors = set() if ancestors is None else ancestors
    if type(value) in (str, int, bool) or value is None:
        if type(value) is str:
            try:
                value.encode("utf-8")
            except UnicodeError:
                require(False, code, pointer)
        return
    require(type(value) in (dict, list), code, pointer)
    require(id(value) not in ancestors, code, pointer)
    ancestors.add(id(value))
    iterator = value.items() if type(value) is dict else enumerate(value)
    for key, child in iterator:
        require(type(value) is list or type(key) is str, code, pointer)
        json_value(child, code, pointer.rstrip("/") + "/" + str(key), ancestors)
    ancestors.remove(id(value))


def strict_json(raw, code="INPUT_ERROR"):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, code, "/")
            result[key] = value
        return result

    def forbidden(_):
        require(False, code, "/")
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_float=forbidden, parse_constant=forbidden)
        require(type(value) is dict, code, "/")
        json_value(value, code)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, WorkflowTransitionError):
            raise
        raise WorkflowTransitionError(code) from None


def closed(value, names, code, pointer):
    require(type(value) is dict, code, pointer)
    require(set(value) == set(names), code, pointer)


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def ref(name):
    return {"$ref": "#/$defs/" + name}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def definitions():
    """Portable wire domains: identical public scalar definitions to #93."""
    defs = {
        "ID": {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$"},
        "Text": {"type": "string", "pattern": r"\S"},
        "SHA": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "Digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "Positive": {"type": "integer", "minimum": 1},
        "Path": {"type": "string", "format": "relative-path"},
        "StatePath": {"type": "string", "format": "state-path"},
        "Kind": {"enum": list(KINDS)},
    }
    defs["Task"] = obj({"repository": ref("Text"), "issue_number": ref("Positive"),
                        "task_run": ref("ID")})
    defs["Governor"] = obj({"commit": ref("SHA"), "workflow_contract_path": ref("Path"),
                            "workflow_contract_blob": ref("SHA")})
    defs["ArtifactRef"] = obj({"kind": ref("Kind"), "artifact_id": ref("ID"),
                              "path": ref("StatePath"), "sha256": ref("Digest")})
    slot = nullable(ref("ArtifactRef"))
    defs["State"] = obj({
        "schema_version": {"const": "1.0"}, "workflow_profile": {"const": PROFILE},
        "task": ref("Task"), "governor": ref("Governor"), "contract": slot,
        "test": obj(dict.fromkeys(("launch", "ack", "ready", "approval"), slot)),
        "worker": obj(dict.fromkeys(("launch", "ack", "ready", "pending_correction"), slot)),
        "candidate": nullable(obj({"envelope": slot, "result": slot})),
        "review": nullable(obj({"launch": slot, "report": slot})),
        "stop": slot, "final_decision": slot, "terminal": slot,
        "repairs": {"type": "array", "items": ref("ArtifactRef")},
        "consumed": {"type": "array", "items": obj({"event_id": ref("ID"),
                                                    "artifact": ref("ArtifactRef")})}})
    business_ref = copy.deepcopy(defs["ArtifactRef"])
    business_ref["properties"]["kind"] = {"enum": [kind for kind in KINDS if kind != "guard-result"]}
    checked_ref = copy.deepcopy(defs["ArtifactRef"])
    checked_ref["properties"]["kind"] = {"const": "guard-result"}
    defs["Event"] = obj({"schema_version": {"const": "1.0"}, "type": {"const": "CONSUME"},
                         "event_id": ref("ID"), "artifact": business_ref,
                         "checked": checked_ref})
    entry = obj({"ref": ref("ArtifactRef"), "body": {"type": "object"}})
    raw_entry = copy.deepcopy(entry)
    raw_entry["properties"]["raw"] = {"type": "string"}
    defs["Context"] = obj({"schema_version": {"const": "1.0"},
        "workflow_profile": {"const": PROFILE}, "task": ref("Task"), "governor": ref("Governor"),
        "protocol": obj(dict.fromkeys(("handoff_schema", "registry", "workflow_contract"),
                                      {"type": "object"})),
        "artifacts": {"type": "array", "items": raw_entry},
        "checks": {"type": "array", "items": entry}})
    return defs


def _format(value, name, code, pointer):
    if name in ("relative-path", "state-path"):
        require(value and not value.startswith("/") and
                not any(c in value for c in '\\\x00:*?"<>|'), code, pointer)
        for part in value.split("/"):
            require(part not in ("", ".", "..") and part[-1] not in " ." and
                    not any(ord(c) < 32 for c in part), code, pointer)
            stem = part.split(".")[0].upper()
            require(stem not in ("CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$") and
                    not re.fullmatch(r"(COM|LPT)[1-9¹²³]", stem), code, pointer)
        require(name != "state-path" or value.startswith(".agent-state/"), code, pointer)
    elif name == "utc-time":
        require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", value), code, pointer)
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            require(False, code, pointer)
    elif name == "canonical-root":
        # This format never occurs in business artifacts. No filesystem probing.
        require(bool(re.match(r"^(?:[A-Za-z]:[/\\]|/)", value)), code, pointer)
    else:
        require(False, code, pointer)


def validate(value, schema, defs, code, pointer="/"):
    """Evaluate the protocol's restricted schema vocabulary wholly in memory."""
    require(type(schema) is dict, code, pointer)
    if "$ref" in schema:
        name = schema["$ref"]
        require(type(name) is str and name.startswith("#/$defs/") and name[8:] in defs,
                code, pointer)
        validate(value, defs[name[8:]], defs, code, pointer)
    for variant in ("anyOf", "oneOf"):
        if variant in schema:
            passes = 0
            for option in schema[variant]:
                try:
                    validate(value, option, defs, code, pointer)
                    passes += 1
                except WorkflowTransitionError:
                    pass
            require(passes > 0 if variant == "anyOf" else passes == 1, code, pointer)
    if "type" in schema:
        types = {"object": dict, "array": list, "string": str, "integer": int,
                 "boolean": bool, "null": type(None)}
        require(schema["type"] in types and type(value) is types[schema["type"]], code, pointer)
    if "const" in schema:
        require(type(value) is type(schema["const"]) and value == schema["const"], code, pointer)
    if "enum" in schema:
        require(any(type(value) is type(item) and value == item for item in schema["enum"]), code, pointer)
    if type(value) is dict:
        props = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), code, pointer)
        require(schema.get("additionalProperties") is not False or set(value) <= set(props), code, pointer)
        for key, child in value.items():
            if key in props:
                validate(child, props[key], defs, code, pointer.rstrip("/") + "/" + key)
    elif type(value) is list:
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)), code, pointer)
        if schema.get("uniqueItems"):
            require(len({canonical(item) for item in value}) == len(value), code, pointer)
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], defs, code, pointer.rstrip("/") + "/" + str(index))
    elif type(value) is str:
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, code, pointer)
        if "format" in schema:
            _format(value, schema["format"], code, pointer)
    elif type(value) is int:
        require(schema.get("minimum", value) <= value <= schema.get("maximum", value), code, pointer)


def wire(value, name, code):
    try:
        json_value(value, code)
        defs = definitions()
        validate(value, defs[name], defs, code, "/" + name.lower())
    except RecursionError:
        raise WorkflowTransitionError(code, "/" + name.lower()) from None


def protocol(context):
    p = context["protocol"]
    schema, registry, workflow = (p["handoff_schema"], p["registry"], p["workflow_contract"])
    code = "MALFORMED_EVENT"
    pointer = "/context/protocol"
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", code, pointer)
    defs = schema.get("$defs")
    require(type(defs) is dict and all(name in defs for name in KINDS), code, pointer)
    keywords = {"$schema", "$id", "title", "$defs", "$ref", "type", "properties",
                "required", "additionalProperties", "items", "minItems", "maxItems",
                "enum", "const", "anyOf", "oneOf", "pattern", "format", "minimum",
                "maximum", "uniqueItems", "description"}

    def supported(node):
        require(type(node) is dict and set(node) <= keywords, code, pointer)
        if "$ref" in node:
            require(type(node["$ref"]) is str and node["$ref"].startswith("#/$defs/") and
                    node["$ref"][8:] in defs, code, pointer)
        if "type" in node:
            require(node["type"] in ("object", "array", "string", "integer", "boolean", "null"),
                    code, pointer)
        for container in ("$defs", "properties"):
            if container in node:
                require(type(node[container]) is dict, code, pointer)
                for child in node[container].values():
                    supported(child)
        for variants in ("anyOf", "oneOf"):
            if variants in node:
                require(type(node[variants]) is list and node[variants], code, pointer)
                for child in node[variants]:
                    supported(child)
        if "items" in node:
            supported(node["items"])
    supported(schema)
    for name, expected in definitions().items():
        if name in ("State", "Event", "Context"):
            continue
        require(defs.get(name) == expected, code, pointer + "/handoff_schema/$defs/" + name)
    require(registry.get("schema_version") == "1.0" and registry.get("workflow_profile") == PROFILE
            and set(registry.get("artifacts", {})) == set(KINDS)
            and set(registry.get("checkpoints", {})) == set(KINDS), code, pointer)
    for kind in KINDS:
        declaration = registry["artifacts"][kind]
        checkpoint = registry["checkpoints"][kind]
        require(type(declaration) is dict and type(declaration.get("producer")) is str and
                type(declaration.get("consumers")) is list and declaration["consumers"] and
                type(declaration.get("visibility")) is list and declaration["visibility"] and
                checkpoint.get("artifact_kind") == kind and
                type(checkpoint.get("required_predecessors")) is list and
                all(x in KINDS for x in checkpoint["required_predecessors"]) and
                checkpoint.get("local_rule") == kind, code, pointer)
        require(defs[kind].get("type") == "object" and
                defs[kind].get("additionalProperties") is False and
                defs[kind].get("properties", {}).get("artifact_kind") == {"const": kind},
                code, pointer)
    lifecycle = {"parallel_lanes": True, "gate1_requires_worker_ready": False,
        "frozen_test": True, "initial_candidate": 0, "max_corrections": 3, "max_candidates": 4,
        "incremental_same_lane": True, "terminal_review_once": True,
        "review_on_success_and_failure": True, "pr_head": "accepted_candidate",
        "pr_includes_test_and_implementation": True, "kpi_in_functional_gate": False}
    require(type(workflow.get("lifecycle")) is dict and
            all(type(workflow["lifecycle"].get(key)) is type(value)
                for key, value in lifecycle.items()), code, pointer)
    require(type(workflow.get("schema_version")) is int and workflow["schema_version"] == 2 and
            type(workflow.get("contract_version")) is int and workflow["contract_version"] == 2 and
            workflow.get("workflow_profile") == PROFILE and workflow.get("lifecycle") == lifecycle and
            workflow.get("artifact_schema") == "agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json" and
            workflow.get("registry") == "agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json",
            code, pointer)
    return defs


def initial_state(task, governor):
    wire(task, "Task", "MALFORMED_EVENT")
    wire(governor, "Governor", "MALFORMED_EVENT")
    require(governor["workflow_contract_path"] == WORKFLOW_PATH, "MALFORMED_EVENT", "/governor/workflow_contract_path")
    return copy.deepcopy({"schema_version": "1.0", "workflow_profile": PROFILE,
        "task": task, "governor": governor, "contract": None,
        "test": {"launch": None, "ack": None, "ready": None, "approval": None},
        "worker": {"launch": None, "ack": None, "ready": None, "pending_correction": None},
        "candidate": None, "review": None, "stop": None, "final_decision": None,
        "terminal": None, "repairs": [], "consumed": []})
