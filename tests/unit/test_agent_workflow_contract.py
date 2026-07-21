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
# File:        test_agent_workflow_contract.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-21
# Version:     0.1.0
# Description: Contract tests for the portable Agent workflow discipline.
# =================================================================================

import json
from pathlib import Path


CONTRACT_PATH = Path("agent-discipline/workflow-contract.json")
SKILL_PATH = Path("agent-discipline/skills/agent-workflow/SKILL.md")
GOVERNANCE_PATH = Path("agent-discipline/documentation-governance.md")
EXPECTED_CLASSES = ("M", "B", "W", "T", "D", "N", "I")
EXPECTED_FLAGS = (
    "PB",
    "MS",
    "MW",
    "RA",
    "TC",
    "VS",
    "EV",
    "AR",
    "RP",
    "ED",
    "SS",
    "DO",
)


def _contract() -> dict:
    assert CONTRACT_PATH.is_file(), "missing canonical workflow contract"
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _skill() -> str:
    assert SKILL_PATH.is_file(), "missing authoritative agent-workflow Skill"
    return SKILL_PATH.read_text(encoding="utf-8")


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def test_workflow_contract_has_exact_portable_task_classes_and_impact_flags():
    contract = _contract()

    assert tuple(item["code"] for item in contract["task_classes"]) == EXPECTED_CLASSES
    assert tuple(item["code"] for item in contract["impact_flags"]) == EXPECTED_FLAGS
    assert len({item["state_machine"] for item in contract["task_classes"]}) == 1


def test_workflow_contract_uses_one_bounded_human_gated_state_machine():
    contract = _contract()
    machine = contract["state_machine"]

    assert machine["name"] == contract["task_classes"][0]["state_machine"]
    assert machine["human_review_1"]["before"] == "implementing"
    assert machine["human_review_1"]["binds"] == "test_sha"
    assert machine["final_human_review"]["before"] == "complete"
    assert contract["limits"] == {
        "production_rework": 3,
        "kpi_optimization": 3,
    }


def test_workflow_contract_defines_ticket_lanes_exact_shas_and_role_boundaries():
    contract = _contract()

    assert contract["lanes"]["names"] == ["test", "implementation", "candidate"]
    assert contract["lanes"]["child_ticket_policy"] == "independent-deliverable-only"
    assert set(contract["lanes"]["required_shas"]) == {
        "base_sha",
        "test_sha",
        "implementation_sha",
        "candidate_sha",
    }
    assert contract["roles"]["explorer"]["writes"] == []
    assert contract["roles"]["worker"]["forbidden_inputs"] == [
        "owner_acceptance_test_implementation"
    ]
    assert contract["roles"]["tester"]["production_writes"] == []
    assert contract["roles"]["reviewer"]["requires"] == "tester_pass"
    assert contract["roles"]["reviewer"]["writes"] == [
        "agent-discipline/agent-lessons-learned.md"
    ]


def test_charter_mandates_skill_without_becoming_a_second_workflow_authority():
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    normalized = _normalized(agents)

    assert "agent-discipline/skills/agent-workflow/skill.md" in normalized
    assert "mandatory" in normalized
    assert "workflow-contract.json" in normalized
    assert normalized.count("m/b/w/t/d/n/i") <= 1


def test_governance_maps_workflow_contract_and_skill_only_in_category_b():
    governance = GOVERNANCE_PATH.read_text(encoding="utf-8")

    assert "`agent-discipline/workflow-contract.json`" in governance
    assert "`agent-discipline/skills/agent-workflow/SKILL.md`" in governance
    for path in Path("docs").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "agent-workflow" not in text, path
        assert "workflow-contract.json" not in text, path


def test_portable_workflow_contract_has_no_vendor_specific_authority():
    contract = _contract()
    skill = _normalized(_skill())

    assert "default_platform" not in contract
    assert "platform-neutral" in skill
    assert "opencode by default" not in skill
    assert "codex by default" not in skill
    assert "claude code by default" not in skill

