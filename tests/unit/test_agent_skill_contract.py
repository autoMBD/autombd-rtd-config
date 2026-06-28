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
# File:        test_agent_skill_contract.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-25
# Version:     0.2.0
# Description: Unit test for the companion agent skill contract.
# =================================================================================

from pathlib import Path


INIT_SCRIPT_PATH = Path(
    "agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env.py"
)
DEPLOY_SCRIPT_PATH = Path(
    "agent-discipline/skills/initialize-agent-discipline/scripts/deploy_agent_env.py"
)


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    opening, frontmatter, _body = text.split("---", 2)
    assert opening == ""
    return frontmatter.strip()


def test_rtd_config_skill_documents_public_cli_and_module_surface():
    skill = Path("autombd-rtd/SKILL.md").read_text(encoding="utf-8")
    # Names the tool and its read-only CLI surface.
    assert "RTD CfgFile CLI" in skill
    assert "rtd-config inspect" in skill
    assert "rtd-config pin-options" in skill
    assert "validate" in skill
    # Documents the full seven-module configure surface, not uart alone.
    for fragment in (
        "mcu set", "basenxp set", "platform set", "port set",
        "dio set", "mcl set", "uart set",
    ):
        assert fragment in skill, f"SKILL.md must document `{fragment}`"
    # DMA is a supported Uart mode now; the milestone-era rejection is gone.
    assert "DMA" in skill
    assert "dma_not_supported_in_m1" not in skill
    # Active docs stay milestone-free; guard against regression to M1 wording.
    assert "Milestone 1" not in skill


def test_external_dependency_memory_skill_is_lightweight_contract():
    skill_path = Path("agent-discipline/skills/external-dependency-memory/SKILL.md")
    skill = skill_path.read_text(encoding="utf-8")

    assert "name: external-dependency-memory" in skill
    assert ".agent-state/external-dependencies.json" in skill
    assert "docs/references/rtd-config-source-materials.md" in skill
    assert "refuse the module" in skill
    assert "development request" in skill
    assert "source.s32k3_rtd_xdm.<module>" in skill
    assert "Never record tokens" in skill
    assert "tools/agent_env_check.py" not in skill
    assert "environment-verification.json" not in skill


def test_subagent_templates_keep_original_claude_code_frontmatter():
    expected = {
        "explorer": "\n".join((
            "name: explorer",
            "description: Read-only investigator that establishes ground-truth facts from the repo, fixtures, the RTD SDK (.xdm/.epd), and the S32DS ConfigTools docs — RTD enum domains, pin-mux matrices, fixture contents, and vendor CLI behavior. Returns decision-ready conclusions with evidence, never file dumps, never edits.",
            "tools: Read, Grep, Glob, Bash, WebFetch",
            "model: sonnet",
        )),
        "worker": "\n".join((
            "name: worker",
            "description: Implements one scoped RTD CfgFile CLI engineering task (code or committed runtime asset) against a self-contained brief, using TDD. Also handles KPI optimization when the Tester reports functional PASS but KPI MISS. Use for feature/bugfix implementation and scoped KPI optimization. Not for cross-cutting design, independent review, or final acceptance.",
            "tools: Read, Edit, Write, Bash, Grep, Glob",
            "model: sonnet",
        )),
        "tester": "\n".join((
            "name: tester",
            "description: Owns the convergence gate. Writes/extends tests and runs the deterministic suite, S32DS headless validation, AND the isolated E2E acceptance cases, then reports an evidence-backed PASS/FAIL plus KPI evidence. E2E runs as a TRUE black box via an independent third-party agent CLI (the tools/blackbox_e2e.py harness; Codex-first, extensible) against the deployed skill + fixture only — never this repository and never the embedded subagent. Tests are the sole functional acceptance criterion for \"done\"; KPI misses trigger capped Worker optimization. Use to prove a change converges.",
            "tools: Read, Edit, Write, Bash, Grep, Glob",
            "model: sonnet",
        )),
        "reviewer": "\n".join((
            "name: reviewer",
            "description: Acceptance reviewer, invoked by the main agent ONLY after the Tester's functional gate is already green and KPI evidence is recorded. Reviews every development requirement EXCEPT test execution (code standards, uniform header, missed skill triggers, ownership/boundaries, domain-value-vs-.xdm, test adequacy, KPI evidence hygiene, diff hygiene) and appends a lessons-learned entry. Read-only — reads the repository to review the diff; produces findings, not fixes.",
            "tools: Read, Grep, Glob, Bash",
            "model: opus",
        )),
    }

    for name, expected_frontmatter in expected.items():
        path = Path("agent-discipline/subagents") / f"{name}.md"
        assert _frontmatter(path) == expected_frontmatter, name


def test_initialize_agent_discipline_uses_native_platform_paths():
    skill = Path(
        "agent-discipline/skills/initialize-agent-discipline/SKILL.md"
    ).read_text(encoding="utf-8")

    for required in (
        ".claude/agents/<name>.md",
        ".opencode/agents/<name>.md",
        ".codex/agents/<name>.toml",
        ".agents/skills/<name>/",
        "references/platform-contract.md",
    ):
        assert required in skill

    assert ".agents/agents/<name>.md" not in skill
    assert 'Add `"$schema"`' not in skill
    assert "Write the template content as-is to `.agents/agents" not in skill

    collector = INIT_SCRIPT_PATH.read_text(encoding="utf-8")
    assert '"opencode": ".opencode/skills"' not in collector
    assert '"codex": ".agents/agents"' not in collector


def test_initialize_agent_discipline_requires_gui_first_complete_input():
    skill = Path(
        "agent-discipline/skills/initialize-agent-discipline/SKILL.md"
    ).read_text(encoding="utf-8")

    for required in (
        "repository GUI collector",
        "agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env.py",
        "--gui",
        "agent-discipline/skills/initialize-agent-discipline/scripts/deploy_agent_env.py",
        "Start-Process",
        "-WindowStyle Normal",
        "-PassThru",
        "-Wait",
        "interactive desktop",
        "require_escalated",
        "must not infer target platforms",
        "must not infer the operation mode",
        "S32DS and RTD paths are required",
        "env.s32ds",
        "env.rtd",
        "Do not deploy anything until the GUI input is complete",
        "Initialization is complete only when",
    ):
        assert required in skill

    for forbidden in (
        "native structured GUI input",
        "Default to update mode",
        "optional S32DS and RTD paths",
        "Empty paths are valid",
        "Use portable text prompts",
    ):
        assert forbidden not in skill

    collector = INIT_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "_skip_paths_var" not in collector
    assert "Skip S32DS/RTD paths" not in collector
    assert "falling back to text mode" not in collector

    platform_contract = Path(
        "agent-discipline/skills/initialize-agent-discipline/"
        "references/platform-contract.md"
    ).read_text(encoding="utf-8")
    assert "deterministic deployment script" in platform_contract
    assert "native project-local file tools" not in platform_contract


def test_initialize_agent_discipline_documents_multi_skill_orchestration():
    skill = Path(
        "agent-discipline/skills/initialize-agent-discipline/SKILL.md"
    ).read_text(encoding="utf-8")
    platform_contract = Path(
        "agent-discipline/skills/initialize-agent-discipline/"
        "references/platform-contract.md"
    ).read_text(encoding="utf-8")

    for required in (
        "multiple local directories",
        "Select all",
        "Clear all",
        "additional_skill_workflows",
        "local_skill_import",
        "online_skill_request",
        "supplemental_task",
        "find-skills",
        "user-level Agent environment",
        "outside the deterministic deployer",
        "out of scope",
        "explicit confirmation",
    ):
        assert required in skill

    for required in (
        "selected local Skills only",
        "directory symbolic link or Windows junction",
        "never rescans the roots to add unselected Skills",
        "online Skill installation is outside this contract",
    ):
        assert required in platform_contract

    deployer = DEPLOY_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "npx skills" not in deployer


def test_initialize_agent_discipline_keeps_scripts_inside_skill_directory():
    skill = Path(
        "agent-discipline/skills/initialize-agent-discipline/SKILL.md"
    ).read_text(encoding="utf-8")
    agents = Path("AGENTS.md").read_text(encoding="utf-8")

    assert INIT_SCRIPT_PATH.exists()
    assert DEPLOY_SCRIPT_PATH.exists()
    assert not Path("tools/init_agent_env.py").exists()
    assert not Path("tools/deploy_agent_env.py").exists()

    for document in (skill, agents):
        assert INIT_SCRIPT_PATH.as_posix() in document
        assert DEPLOY_SCRIPT_PATH.as_posix() in document
        assert "tools/init_agent_env.py" not in document
        assert "tools/deploy_agent_env.py" not in document
