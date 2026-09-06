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
# File:        test_structured_handoff_protocol.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Generality tests for structured handoff validation.
# =================================================================================

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "agent-discipline/skills/agent-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))


def protocol():
    assert (SCRIPTS / "structured_handoff.py").is_file(), "structured protocol core is not implemented"
    return importlib.import_module("structured_handoff")


def test_schema_is_closed_and_declares_every_artifact_and_attachment():
    core = protocol()
    schema = core.load_schema()
    kinds = {"task-contract", "test-launch", "worker-launch", "test-gate-report",
             "implementation-report", "human-decision", "candidate-test-envelope",
             "tester-confidential-report", "worker-correction-envelope",
             "reviewer-launch", "reviewer-report", "terminal-record", "delivery-repair",
             "guard-result"}
    assert kinds == set(core.load_registry()["artifacts"])
    assert {"ImpactSet", "CoverageJoin", "LaneManifestV1", "CommandResult",
            "DisclosureReview", "TrustedContext"}.issubset(schema["$defs"])
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(schema)


@pytest.mark.parametrize("value", [
    "../escape", "/absolute", "C:/drive", "a//b", "a/./b", "a/../b",
    "a\\b", "a/NUL.txt", "a/COM1", "a/name.", "a/name ", "a:stream",
    "a/aux.log", "", "a/\x00b",
])
def test_paths_reject_cross_platform_aliases(value):
    with pytest.raises(protocol().ProtocolError):
        protocol().validate_definition(value, "Path")


@pytest.mark.parametrize("raw", [
    b'{"a":1,"a":2}\n', b'{"a":NaN}\n', b'{"a":Infinity}\n',
    b'\xef\xbb\xbf{}\n', b'{ "a":1}\n', b'{}', b'{"a":1.5}\n',
])
def test_protocol_bytes_are_strict_and_canonical(raw):
    with pytest.raises(protocol().ProtocolError):
        protocol().parse_json(raw)


def test_schema_rejects_unsupported_keywords():
    core = protocol()
    with pytest.raises(core.ProtocolError):
        core.validate_schema("hello", {"type": "string", "not": {}}, {})


def test_true_is_not_an_integer():
    core = protocol()
    with pytest.raises(core.ProtocolError):
        core.validate_definition(True, "Index")
    core.validate_definition(3, "Index")
    with pytest.raises(core.ProtocolError):
        core.validate_definition(4, "Index")


def test_digest_is_exact_bytes_not_semantic_json():
    core = protocol()
    raw = core.canonical_bytes({"label": "原样"})
    assert raw.endswith(b"\n")
    assert core.parse_json(raw) == {"label": "原样"}
    with pytest.raises(core.ProtocolError):
        core.parse_json(raw, "f" * 64)


def test_every_variant_rejects_each_missing_member_and_nested_extra_member():
    core = protocol()
    schema = core.load_schema()
    definitions = schema["$defs"]
    def example(node):
        if "$ref" in node:
            return example(definitions[node["$ref"][8:]])
        if "const" in node:
            return node["const"]
        if "enum" in node:
            return node["enum"][0]
        if "anyOf" in node:
            return example(node["anyOf"][-1])
        kind = node["type"]
        if kind == "object":
            return {k: example(v) for k, v in node["properties"].items()}
        if kind == "array":
            return [example(node["items"]) for _ in range(node.get("minItems", 0))]
        if kind == "integer":
            return node.get("minimum", 0)
        if kind == "boolean":
            return False
        if kind == "null":
            return None
        if node.get("format") == "state-path":
            return ".agent-state/example.json"
        if node.get("format") == "utc-time":
            return "2026-09-06T00:00:00Z"
        if node.get("format") == "canonical-root":
            return str(Path.cwd().resolve())
        if "40" in node.get("pattern", ""):
            return "a" * 40
        if "64" in node.get("pattern", ""):
            return "a" * 64
        return "sample"
    def objects(value, path=()):
        if isinstance(value, dict):
            yield path, value
            for k, v in value.items():
                yield from objects(v, path + (k,))
        elif isinstance(value, list):
            for k, v in enumerate(value):
                yield from objects(v, path + (k,))
    for name in list(core.load_registry()["artifacts"]) + ["ImpactSet", "CoverageJoin", "TrustedContext", "LaneManifestV1", "CommandResult", "DisclosureReview"]:
        value = example(definitions[name])
        core.validate_definition(value, name)
        for path, obj in objects(value):
            for missing in [None, *obj]:
                changed = copy.deepcopy(value)
                node = changed
                for part in path:
                    node = node[part]
                if missing is None:
                    node["unexpected_member"] = "forbidden"
                else:
                    del node[missing]
                with pytest.raises(core.ProtocolError):
                    core.validate_definition(changed, name)
