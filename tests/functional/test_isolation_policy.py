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
# File:        test_isolation_policy.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-13
# Version:     0.1.0
# Description: Owner source-bound scope, readable requirements and policy checks.
# =================================================================================


"""Static checks prove structure and source bounds; semantic review remains separate."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/fixtures/isolation-compliance"))
from isolation_support import G, PHASES, digest, load_schema, load_registry

REQ = "tests/doc/reference/agent/isolation-compliance-requirements.md"
CASES = "tests/doc/reference/agent/isolation-compliance-cases.md"
EXPECTED_REQUIREMENTS = "cf149b7c829fba67793c65f0577d4858ab4c6c0cdaf3e3ad27857b1b6f9abe1b"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def changed():
    committed = git("diff", "--name-only", G, "HEAD").decode().splitlines()
    pending = git("diff", "--name-only", "HEAD").decode().splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").decode().splitlines()
    return set(committed + pending + untracked)


def active(path):
    return (ROOT / path).read_text("utf-8").split("## Changelog")[0]


def test_ic26_requirements_render_complete_k_and_cases_have_no_execution_payload():
    text = (ROOT / REQ).read_text("utf-8")
    parsed = []
    for match in re.finditer(r"^## (R\d\d)\n\n(.*?)\n\nSources: ([^\n]+)", text, re.M | re.S):
        parsed.append({"id": match[1], "obligation": match[2],
                       "authority_ids": match[3].split(", ")})
    assert digest(parsed) == EXPECTED_REQUIREMENTS
    assert [r["id"] for r in parsed] == [f"R{i:02d}" for i in range(1, 26)]
    index = (ROOT / "tests/doc/README.md").read_text("utf-8")
    assert Path(REQ).name in index and Path(CASES).name in index
    cases = (ROOT / CASES).read_text("utf-8")
    rows = [line for line in cases.splitlines() if line.startswith("| IC")]
    assert len(rows) == 29
    assert len({line.split("|")[1].strip() for line in rows}) == 29
    assert all(len(line.split("|")) == 6 for line in rows)
    assert not any(term in cases for term in ("pytest", "tests/.tmp", "execution_id", "outbox/", "def test_"))


def test_ic27_changes_stay_in_agent_scope_and_preserve_historical_bytes():
    paths = changed()
    allowed = ("agent-discipline/skills/agent-workflow/", "agent-discipline/subagents/",
               "tests/unit/", "tests/functional/test_isolation_", "tests/fixtures/isolation-compliance/",
               "tests/doc/reference/agent/isolation-compliance-")
    explicit = {"AGENTS.md", "agent-discipline/local-execution-state.md",
                "agent-discipline/workflow-contract.json", "tests/doc/README.md",
                "tools/blackbox_e2e.py"}
    assert all(p in explicit or p.startswith(allowed) for p in paths), sorted(paths)
    assert not any("review-archive" in p or p.startswith("docs/") for p in paths)
    for path in paths:
        if path.endswith(".py") and not git("ls-tree", G, "--", path).strip():
            text = (ROOT / path).read_text("utf-8")
            assert text.startswith("# ===") and "SPDX" in text[:500], path
            assert all(("# " + field + ":") in text for field in
                       ("Project", "File", "Author", "Date", "Version", "Description")), path
    if "tools/blackbox_e2e.py" in paths:
        # K permits wording correction only; #98 runtime behavior stays separate.
        class WithoutDocstrings(ast.NodeTransformer):
            def generic_visit(self, node):
                super().generic_visit(node)
                if isinstance(getattr(node, "body", None), list) and node.body:
                    first = node.body[0]
                    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                        node.body = node.body[1:]
                return node
        parse = lambda text: ast.dump(WithoutDocstrings().visit(ast.parse(text)), include_attributes=False)
        assert parse(git("show", G + ":tools/blackbox_e2e.py").decode()) == parse((ROOT / "tools/blackbox_e2e.py").read_text("utf-8"))
    for path in paths:
        if not path.endswith(".md"):
            continue
        old = subprocess.run(["git", "-C", str(ROOT), "show", G + ":" + path], capture_output=True)
        if old.returncode:
            continue
        original = old.stdout.decode("utf-8")
        if "## Changelog" in original:
            rows = [row for row in original.split("## Changelog", 1)[1].splitlines()
                    if row.startswith("| 20")]
            current = (ROOT / path).read_text("utf-8")
            assert all(row in current for row in rows), path
    for path in paths:
        if not path.startswith("agent-discipline/skills/agent-workflow/scripts/") or not path.endswith(".py"):
            continue
        tree = ast.parse((ROOT / path).read_text("utf-8"))
        local = {p.stem for p in (ROOT / path).parent.glob("*.py")}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [x.name.split(".")[0] for x in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
                assert all(n in sys.stdlib_module_names or n in local or not n for n in names), (path, names)


def test_ic28_role_guidance_addresses_scope_and_honest_evidence_limits():
    guides = {
        "AGENTS.md": ("isolation", "orchestrator", "reviewer", "violation"),
        "agent-discipline/subagents/worker.md": ("isolation", "scope", "test", "correction"),
        "agent-discipline/subagents/tester.md": ("isolation", "author", "candidate", "production"),
        "agent-discipline/subagents/reviewer.md": ("isolation", "evidence", "violation", "lesson"),
        "agent-discipline/subagents/explorer.md": ("isolation", "source"),
        "agent-discipline/skills/agent-workflow/SKILL.md": ("isolation", "w5"),
        "agent-discipline/local-execution-state.md": ("isolation", "evidence"),
    }
    for path, terms in guides.items():
        text = active(path).lower()
        assert all(term in text for term in terms), (path, terms)
    references = ROOT / "agent-discipline/skills/agent-workflow/references"
    combined = "\n".join(active(p.relative_to(ROOT)) for p in references.glob("*.md")).lower()
    for name in ("i0", "i1", "i2", "scope_id", "cutoff", "indeterminate",
                 "confirmed", "operation", "os", "blackbox", "w1", "w4"):
        assert name in combined, name
    assert not re.search(r"i3\s+(?:isolation\s+)?(?:is\s+)?(?:required|mandatory|default)", combined)
    for path in guides:
        assert "sandboxed to the temp dir" not in active(path).lower()
    tester = active("agent-discipline/subagents/tester.md").lower()
    assert "timeout" in tester and "#98" in tester


def test_ic29_schema_and_registry_keep_one_domain_and_no_new_lifecycle():
    definitions = load_schema()["$defs"]
    assert set(definitions["IsolationLevel"]["enum"]) == {"I0", "I1", "I2"}
    assert set(definitions["IsolationPhase"]["enum"]) == set(PHASES)
    level_domains = [key for key, value in definitions.items()
                    if value.get("enum") == ["I0", "I1", "I2"]]
    assert level_domains == ["IsolationLevel"]
    old = json.loads(git("show", G + ":agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json"))
    current = load_registry()
    assert current["artifacts"].keys() == old["artifacts"].keys()
    assert current["checkpoints"].keys() == old["checkpoints"].keys()
    for name, entry in current["artifacts"].items():
        assert entry["producer"] == old["artifacts"][name]["producer"]
        assert entry["worker_readable"] == old["artifacts"][name]["worker_readable"]
