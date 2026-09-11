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
# File:        test_coverage_dependencies_scope.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Coverage requirement fidelity and narrow source scope.
# =================================================================================

"""Static fidelity and scope checks; prose tokens do not prove semantics."""
import ast
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("RTD_COVERAGE_SOURCE_ROOT", ROOT)).resolve()
G = "cf78144a3786d1dc3f1e92d27157674a7ebea85c"
RULES = "agent-discipline/skills/agent-workflow/scripts/structured_handoff_rules.py"
REFERENCE = "agent-discipline/skills/agent-workflow/references/structured-handoffs.md"
REQUIREMENTS = "tests/doc/reference/agent/coverage-dependencies-requirements.md"
CASES = "tests/doc/reference/agent/coverage-dependencies-cases.md"
FIXTURE = ROOT / "tests/fixtures/coverage-dependencies/public_requirements.json"
OWNED = {RULES, REFERENCE, "tests/unit/test_coverage_dependencies_generality.py", REQUIREMENTS, CASES,
         "tests/doc/README.md", "tests/functional/test_coverage_dependencies.py", "tests/functional/test_coverage_dependencies_scope.py",
         "agent-discipline/skills/agent-workflow/scripts/repair_protocol.py"}


def git(*argv):
    return subprocess.run(["git", "-C", str(ROOT), *argv], capture_output=True, check=True, timeout=30).stdout


def test_complete_readable_requirements_and_source_associations():
    contract = json.loads(FIXTURE.read_bytes())
    text = (ROOT / REQUIREMENTS).read_text("utf-8")
    assert contract["task_contract_sha256"] in text
    assert {r["id"] for r in contract["requirements"]} == {f"R{i:02d}" for i in range(1, 10)}
    for requirement in contract["requirements"]:
        assert "## " + requirement["id"] + "\n" in text
        assert requirement["obligation"] in text
        for authority in requirement["authority_ids"]:
            assert f"[{authority}]" in text


def test_case_table_and_index_are_paired_and_traceable():
    cases = (ROOT / CASES).read_text("utf-8")
    rows = [line for line in cases.splitlines() if line.startswith("| CD-")]
    assert len(rows) == 20 and len(set(re.findall(r"CD-\d{3}", "\n".join(rows)))) == 20
    assert {f"R{i:02d}" for i in range(1, 10)} <= set(re.findall(r"R\d{2}", "\n".join(rows)))
    assert all(len(line.split("|")) == 6 for line in rows)
    assert not any(token in cases for token in ("pytest", "--basetemp", ".agent-state/", "test_coverage_dependencies.py::"))
    index = (ROOT / "tests/doc/README.md").read_text("utf-8")
    assert "reference/agent/coverage-dependencies-requirements.md" in index
    assert "reference/agent/coverage-dependencies-cases.md" in index


def test_public_reference_names_declared_graph_and_version_boundaries():
    # This checks accessible contract vocabulary only. Source-semantic truth and
    # completeness of prose remain the Orchestrator/Reviewer responsibility.
    text = (SOURCE / REFERENCE).read_text("utf-8")
    for term in ("covered_paths", "public_dependency_edges", "Orchestrator", "Governor", "W1", "W2", "W3", "W4", "METADATA", "preserve_tip", "affected_check_ids"):
        assert term in text, f"Missing public contract vocabulary: {term}"


def test_only_authorized_source_paths_change():
    paths = set(git("diff", "--name-only", G, "HEAD", "--").decode().splitlines())
    paths |= set(git("diff", "--name-only", "HEAD", "--").decode().splitlines())
    assert all(p in OWNED or p.startswith("tests/fixtures/coverage-dependencies/") for p in paths), sorted(paths)


def test_schema_registry_workflow_and_other_rules_remain_byte_identical():
    # Compare actual working bytes to the independently pinned public Governor.
    paths = ["agent-discipline/workflow-contract.json", "agent-discipline/contracts/workflow-v1.json",
             "agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json",
             "agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json",
             "agent-discipline/skills/agent-workflow/scripts/structured_handoff.py",
             "agent-discipline/skills/agent-workflow/scripts/structured_handoff_refs.py",
             "agent-discipline/skills/agent-workflow/scripts/workflow_evidence.py"]
    for path in paths:
        original = git("show", G + ":" + path)
        assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == original, path


def test_rule_changes_are_local_to_join_and_direct_helpers():
    before = ast.parse(git("show", G + ":" + RULES).decode())
    after = ast.parse((SOURCE / RULES).read_text("utf-8"))
    dump = lambda n: ast.dump(n, include_attributes=False)
    old_classes = {n.name: n for n in before.body if isinstance(n, ast.ClassDef)}
    new_classes = {n.name: n for n in after.body if isinstance(n, ast.ClassDef)}
    assert old_classes.keys() == new_classes.keys()
    old = {n.name: n for n in old_classes["LocalRules"].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    new = {n.name: n for n in new_classes["LocalRules"].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert old.keys() <= new.keys()
    direct = {n.func.attr for n in ast.walk(new["coverage_join"]) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"}
    for name in old:
        if name not in {"coverage_join"} | direct:
            assert dump(old[name]) == dump(new[name]), name
    assert set(new) - set(old) <= direct
    assert [dump(n) for n in before.body if not isinstance(n, ast.ClassDef)] == [dump(n) for n in after.body if not isinstance(n, ast.ClassDef)]


def test_repair_change_stays_local_and_existing_projection_call_shape_survives():
    path = "agent-discipline/skills/agent-workflow/scripts/repair_protocol.py"
    before = ast.parse(git("show", G + ":" + path).decode())
    after = ast.parse((SOURCE / path).read_text("utf-8"))
    old = {n.name: n for n in before.body if isinstance(n, ast.FunctionDef)}
    new = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
    assert old.keys() <= new.keys()
    allowed = {"validate_impact_projection", "validate_repair", "_attachment_changes", "_audit"}
    while True:
        direct = {node.func.id for key in allowed for node in ast.walk(new[key]) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id in new}
        updated = allowed | direct
        if updated == allowed:
            break
        allowed = updated
    assert set(new) - set(old) <= allowed
    for name in old.keys() - allowed:
        assert ast.dump(old[name], include_attributes=False) == ast.dump(new[name], include_attributes=False), name
    args = new["validate_impact_projection"].args
    assert [a.arg for a in args.args][:2] == ["before", "after"]
    assert "source_changes" in [a.arg for a in args.kwonlyargs]
