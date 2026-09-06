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
# File:        test_workflow_transition_contract.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.1
# Description: Scoped schema and immutable protocol compatibility checks.
# =================================================================================

"""Static checks for tests/doc/agent-functional-test-cases.md, cases 029-034.

These declaration checks do not establish runtime or documentation semantics.
"""

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from workflow_transition_cases import ROOT, SCHEMAS, load_protocol, validate_schema

SCHEMA_TARGET = Path(os.environ.get("RTD_TRANSITION_TEST_SCHEMA",
                                    SCHEMAS / "workflow-transition-v1.schema.json"))
DELIVERY_ROOT = Path(os.environ.get("RTD_TRANSITION_TEST_DELIVERY_ROOT", ROOT))
DECLARED_SOURCES = [
    "agent-discipline/skills/agent-workflow/scripts/workflow_transition.py",
    "agent-discipline/skills/agent-workflow/scripts/workflow_transition_wire.py",
    "agent-discipline/skills/agent-workflow/scripts/workflow_transition_rules.py",
    "tests/unit/test_workflow_transition_generality.py",
    "tests/unit/workflow_transition_generality_support.py",
]

# Exact Governor inputs explicitly excluded from this issue's production ownership.
UNCHANGED = {
    "AGENTS.md": "c89c7fce38b5932e3e83e7333351f3fa37bb906c440f7f542d985d26dd1e7e9e",
    "agent-discipline/workflow-contract.json": "8c111f9f88fa83b2d9684fee40667e7d7627a50ca7373f89f5b28a21c8810b80",
    "agent-discipline/subagents/tester.md": "acdce3e96f9be9244380fc79c8b07a34a2b8afa2138d7372375cd091f1edbffd",
    "agent-discipline/subagents/worker.md": "286ffe445c1bb898a7a507a845b9092fd30d31d71e7a6eebeed9dfab85097781",
    "agent-discipline/subagents/reviewer.md": "0cc8cbfbf16a51f67e3104e5da820ca5bc7a6200c07701d4c16f29decf982fb9",
    "agent-discipline/skills/agent-workflow/scripts/workflow_gate.py": "98f4c681319c754a176ff69e9c330a71572b1608b07c0b7a0d294ad310906f70",
    "agent-discipline/skills/agent-workflow/scripts/handoff_guard.py": "414bcda13344400985c1fc34fb93e404141866a4c932d85a4f994041136fb105",
    "agent-discipline/skills/agent-workflow/scripts/interface_handoff_check.py": "f06219020614e5afdd74455245c56dc3612bd988d7f35736288a3a0665e40892",
    "agent-discipline/skills/agent-workflow/scripts/structured_handoff_schema.py": "2586f9b32095f9b735c87d532ab0677e08e326c6c070e68a60d9c483ab46e86c",
    "agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json": "23682ee7cd4ec34b701baeb5910fe736a08a6760c8f0cb866a6fc8f7e2acae79",
    "agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json": "227babd8b0956c72600062ee86851ac3e264bbecbb3492f5fe536756742be448",
}


@pytest.mark.parametrize("path,expected", UNCHANGED.items())
def test_current_protocol_and_legacy_entrypoints_are_unchanged(path, expected):
    """R01,R22: new reducer cannot weaken the authoritative previous protocol."""
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected


def schema():
    assert SCHEMA_TARGET.is_file(), "R04: committed standalone transition schema is absent"
    value = json.loads(SCHEMA_TARGET.read_text(encoding="utf-8"))
    assert {"State", "Event", "Context"} <= value["$defs"].keys()
    return value["$defs"]


def expand_public_references(node, definitions):
    """Resolve only in-memory local or the fixed public handoff schema domains."""
    if isinstance(node, list):
        return [expand_public_references(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        reference = node["$ref"]
        name = reference.split("#/$defs/")[-1]
        if reference.startswith("#/$defs/"):
            target_definitions = definitions
        else:
            assert reference == "handoff-v1.schema.json#/$defs/" + name
            target_definitions = load_protocol()["handoff_schema"]["$defs"]
        resolved = expand_public_references(target_definitions[name], target_definitions)
        resolved.update({k: expand_public_references(v, definitions)
                         for k, v in node.items() if k != "$ref"})
        return resolved
    return {key: expand_public_references(value, definitions) for key, value in node.items()}


@pytest.mark.parametrize("name,keys", [
    ("State", {"schema_version", "workflow_profile", "task", "governor", "contract", "test",
               "worker", "candidate", "review", "stop", "final_decision", "terminal", "repairs", "consumed"}),
    ("Event", {"schema_version", "type", "event_id", "artifact", "checked"}),
    ("Context", {"schema_version", "workflow_profile", "task", "governor", "protocol", "artifacts", "checks"}),
])
def test_public_wire_definitions_are_closed_and_complete(name, keys):
    definitions = schema()
    definition = definitions[name]
    assert definition["additionalProperties"] is False
    assert set(definition["properties"]) == keys
    assert set(definition["required"]) == keys


@pytest.mark.parametrize("name,wire,field", [("Task", "State", "task"),
    ("Governor", "State", "governor"), ("ArtifactRef", "Event", "artifact")])
def test_shared_protocol_domains_retain_their_exact_definition(name, wire, field):
    definitions = schema()
    # Reuse may be either local or fixed-public external references.
    protocol_defs = load_protocol()["handoff_schema"]["$defs"]
    current = definitions[wire]["properties"][field]
    resolved = expand_public_references(current, definitions)
    expected = expand_public_references(protocol_defs[name], protocol_defs)
    if name == "ArtifactRef":
        # A field may reuse the base domain and let the reducer enforce event-kind
        # restrictions, or express that subset directly in the JSON schema.
        actual_kinds = set(resolved["properties"]["kind"]["enum"])
        kinds = set(expected["properties"]["kind"]["enum"])
        assert actual_kinds in (kinds, kinds - {"guard-result"})
        resolved["properties"]["kind"] = expected["properties"]["kind"]
    assert resolved == expected


def test_schema_validates_memory_examples_and_rejects_nested_extras():
    from workflow_transition_cases import empty_state
    definitions = schema()
    definitions = {name: expand_public_references(value, definitions)
                   for name, value in definitions.items()}
    task = {"repository": "example/schema", "issue_number": 417, "task_run": "schema-run"}
    governor = {"commit": "a" * 40, "workflow_contract_path": "agent-discipline/workflow-contract.json",
                "workflow_contract_blob": "b" * 40}
    state = empty_state(task, governor)
    ref = {"kind": "task-contract", "artifact_id": "contract-id",
           "path": ".agent-state/contract.json", "sha256": "c" * 64}
    checked = dict(ref, kind="guard-result", artifact_id="receipt-id")
    event = {"schema_version": "1.0", "type": "CONSUME", "event_id": "event-id",
             "artifact": ref, "checked": checked}
    context = {"schema_version": "1.0", "workflow_profile": "functional-development-v1",
               "task": task, "governor": governor, "protocol": load_protocol(),
               "artifacts": [], "checks": []}
    from structured_handoff_schema import ProtocolError
    for name, value in [("State", state), ("Event", event), ("Context", context)]:
        validate_schema(value, definitions[name], definitions)
        extra = copy.deepcopy(value)
        extra["unknown"] = True
        with pytest.raises(ProtocolError):
            validate_schema(extra, definitions[name], definitions)
    for path in [("test",), ("worker",), ("task",), ("governor",)]:
        extra = copy.deepcopy(state)
        extra[path[0]]["unknown"] = True
        with pytest.raises(ProtocolError):
            validate_schema(extra, definitions["State"], definitions)


@pytest.mark.parametrize("relative", DECLARED_SOURCES)
def test_declared_owned_sources_have_header_and_valid_python_syntax(relative):
    """R22-R25 static only: does not claim Worker TDD execution or adequacy."""
    path = DELIVERY_ROOT / relative
    assert path.is_file(), "Declared owned delivery is absent: " + relative
    source = path.read_text(encoding="utf-8")
    assert source.startswith("# =================================================================================")
    for text in ("# Project:     RTD CfgFile CLI", "# File:        " + path.name,
                 "# Author:      autoMBD <tkung.lqk@foxmail.com>", "# Date:",
                 "# Version:", "# Description:", "SPDX", "MIT"):
        assert text in source[:4000], "Required uniform file metadata absent: " + text
    compile(source, str(path), "exec")


def test_declared_public_reference_exposes_the_actual_interface_names():
    """Presence only; semantic documentation review remains the terminal Reviewer."""
    path = DELIVERY_ROOT / "agent-discipline/skills/agent-workflow/references/workflow-transitions.md"
    assert path.is_file()
    content = path.read_text(encoding="utf-8")
    for name in ("initial_state", "transition", "WorkflowTransitionError", "State", "Event", "Context",
                 "MALFORMED_EVENT", "INVALID_STATE", "STALE_EVENT", "DUPLICATE_EVENT",
                 "ILLEGAL_TRANSITION", "OUT_OF_ORDER_EVENT", "MISSING_EVIDENCE", "INVALID_EVIDENCE",
                 "INVALID_OUTPUT", "INPUT_ERROR", "USAGE_ERROR", "EXECUTION_ERROR"):
        assert name in content, "Public interface reference omits " + name
