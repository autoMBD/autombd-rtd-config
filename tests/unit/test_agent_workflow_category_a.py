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
# File:        test_agent_workflow_category_a.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-22
# Version:     0.1.0
# Description: Acceptance tests for active Category A documentation purity.
# =================================================================================

from pathlib import Path
import re


CATEGORY_A_ROOT = Path("docs")
HISTORICAL_HEADING = re.compile(
    r"(?im)^##\s+(?:changelog|history|revision history)\s*$"
)
FORBIDDEN_ACTIVE_SEMANTICS = {
    "agent workflow authority": re.compile(
        r"\b(?:autonomous\s+)?agent workflow\b", re.IGNORECASE
    ),
    "agent-specific workflow authority": re.compile(
        r"\b(?:workflow stops|every agent|agent convergence)\b", re.IGNORECASE
    ),
    "tests-only convergence authority": re.compile(
        r"\btests?\b.{0,80}\b(?:only|sole)\b.{0,80}"
        r"\b(?:convergence signal|criterion for functional|acceptance criterion)\b",
        re.IGNORECASE,
    ),
    "green gate sufficient acceptance": re.compile(
        r"\b(?:passing|green)\b.{0,40}\b(?:gate|tests?)\b.{0,60}"
        r"\b(?:sufficient to accept|accepts?)\b"
        r"|\b(?:passing gate is sufficient|green gate accepts)\b",
        re.IGNORECASE,
    ),
    "human workflow gate": re.compile(
        r"\b(?:human review 1|final human review|production rework|"
        r"test contract correction|task handoff)\b",
        re.IGNORECASE,
    ),
    "Category B workflow artifact": re.compile(
        r"\b(?:agent-workflow|workflow-contract\.json)\b", re.IGNORECASE
    ),
}


def _active_text(text: str) -> str:
    historical = HISTORICAL_HEADING.search(text)
    if historical:
        text = text[: historical.start()]
    return " ".join(text.split())


def _semantic_offenders(text: str) -> list[str]:
    active = _active_text(text)
    return [
        name
        for name, pattern in FORBIDDEN_ACTIVE_SEMANTICS.items()
        if pattern.search(active)
    ]


def test_active_category_a_has_no_agent_workflow_acceptance_authority():
    offenders: list[str] = []
    for path in sorted(CATEGORY_A_ROOT.rglob("*.md")):
        for semantic in _semantic_offenders(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.as_posix()}: {semantic}")

    assert offenders == [], "active Category A workflow authority:\n" + "\n".join(
        offenders
    )


def test_category_a_lexicon_allows_engineering_test_and_runtime_terms():
    allowed_engineering_statements = (
        "Development testing verifies every mandatory product requirement.",
        "Runtime validation checks the generated configuration after an edit.",
        "Functional acceptance requires deterministic, static, vendor, and E2E evidence.",
        "A failing development test identifies a production defect.",
        "The validation command returns a stable machine-readable diagnostic.",
    )

    for statement in allowed_engineering_statements:
        assert _semantic_offenders(statement) == [], statement


def test_append_only_history_is_not_treated_as_active_authority():
    document = """# Engineering strategy

Development testing verifies the product contract.

## Changelog

| Date | Description |
| --- | --- |
| 2026-01-01 | An autonomous agent workflow once used green gate accepts. |
"""

    assert _semantic_offenders(document) == []
