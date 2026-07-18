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
# File:        test_blackbox_e2e.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-14
# Version:     0.2.0
# Description: Unit tests for the black-box isolated E2E harness that drives a
#              third-party agent CLI (Codex, OpenCode, others) over the released
#              autombd-rtd skill. Tests cover the runner registry, case parsing,
#              prompt building, subprocess wiring, pipeline integration, OpenCode
#              backend, agent adapter registry, agent-selection cache, and CLI
#              defaults — no real codex/opencode/S32DS invocation in any test.
# =================================================================================

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module loader helper
# ---------------------------------------------------------------------------

def load_module():
    """Load tools/blackbox_e2e.py via importlib so tests are path-independent."""
    module_path = Path(__file__).resolve().parents[2] / "tools" / "blackbox_e2e.py"
    spec = importlib.util.spec_from_file_location("blackbox_e2e", module_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["blackbox_e2e"] = mod
    spec.loader.exec_module(mod)
    return mod


# Inline markdown table used by parse_case tests — mirrors the real table shape.
SAMPLE_MD = """
## 2. Test cases

| ID | Module | Scenario | Subagent Prompt | Test fixture | KPI | Pass criteria |
| --- | --- | --- | --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | Modify MCU clock configuration | 修改MCU的时钟配置，外部晶振16MHz，CORE_CLK=160MHz | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 2 min. | Clock configuration is correct, S32DS validation passes. |
| RTD-MEX-BASENXP-001 | BaseNXP | Modify OsIf configuration | 使能OsIf的系统定时器作为计数时基 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | OsIf configuration is correct, S32DS validation passes. |
| RTD-MEX-UART-003 | UART | Configure Uart channel DMA mode | 修改已有的Uart通道，使能DMA模式 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 3 min. | Platform enables and registers the correct ISR, S32DS validation passes. |
"""


# ---------------------------------------------------------------------------
# 1. Runner registry: get_runner
# ---------------------------------------------------------------------------

class TestGetRunner:
    def test_known_agent_returns_codex_runner(self):
        mod = load_module()
        runner = mod.get_runner("codex")
        assert runner is mod.run_codex

    def test_unknown_agent_raises_with_supported_list(self):
        mod = load_module()
        with pytest.raises(ValueError, match="codex") as exc_info:
            mod.get_runner("openai-o3")
        # message must list the supported agents
        assert "openai-o3" in str(exc_info.value) or "supported" in str(exc_info.value).lower()

    def test_unknown_agent_error_mentions_all_registered_backends(self):
        mod = load_module()
        with pytest.raises(ValueError) as exc_info:
            mod.get_runner("nonexistent")
        msg = str(exc_info.value)
        # At minimum "codex" must appear in the error as a supported backend
        assert "codex" in msg


# ---------------------------------------------------------------------------
# 2. Case parsing: parse_case
# ---------------------------------------------------------------------------

class TestParseCase:
    def test_parses_mcu_case_from_inline_table(self, tmp_path):
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        case = mod.parse_case(md_file, "RTD-MEX-MCU-001")

        assert case.id == "RTD-MEX-MCU-001"
        assert "修改MCU的时钟配置" in case.prompt
        # fixture: the backtick-quoted path from the cell, stripped
        assert "Uart_Example_S32K344" in case.fixture
        assert case.kpi_minutes == 2

    def test_parses_basenxp_case_kpi_1_min(self, tmp_path):
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        case = mod.parse_case(md_file, "RTD-MEX-BASENXP-001")

        assert case.id == "RTD-MEX-BASENXP-001"
        assert case.kpi_minutes == 1
        assert "使能OsIf" in case.prompt

    def test_parses_uart003_case_kpi_3_min(self, tmp_path):
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        case = mod.parse_case(md_file, "RTD-MEX-UART-003")

        assert case.kpi_minutes == 3

    def test_raises_on_missing_case_id(self, tmp_path):
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        with pytest.raises((ValueError, KeyError, LookupError)) as exc_info:
            mod.parse_case(md_file, "RTD-MEX-DOES-NOT-EXIST")
        # Error must mention the missing id
        assert "RTD-MEX-DOES-NOT-EXIST" in str(exc_info.value)

    def test_fixture_path_strips_backticks(self, tmp_path):
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        case = mod.parse_case(md_file, "RTD-MEX-MCU-001")

        # Must not contain backtick characters
        assert "`" not in case.fixture

    def test_prompt_is_verbatim_chinese(self, tmp_path):
        """Chinese characters must survive intact (not escaped or dropped)."""
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        case = mod.parse_case(md_file, "RTD-MEX-MCU-001")

        assert "修改MCU的时钟配置" in case.prompt
        assert "外部晶振16MHz" in case.prompt

    def test_parse_against_real_test_cases_file(self):
        """Smoke-test parse_case against the live docs/tests/rtd-config-test-cases.md."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]
        real_md = repo_root / "docs" / "tests" / "rtd-config-test-cases.md"

        case = mod.parse_case(real_md, "RTD-MEX-UART-003")

        assert case.kpi_minutes == 3
        assert "DMA" in case.prompt or "dma" in case.prompt.lower()


# ---------------------------------------------------------------------------
# 2b. max_kpi_minutes
# ---------------------------------------------------------------------------

# Small inline catalog fixture with mixed KPIs: 1, 2, 3 min (max = 3).
SAMPLE_MD_MIXED_KPI = """
## 2. Test cases

| ID | Module | Scenario | Subagent Prompt | Test fixture | KPI | Pass criteria |
| --- | --- | --- | --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | Modify MCU clock | 修改MCU | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | finish within 2 min. | ok |
| RTD-MEX-BASENXP-001 | BaseNXP | Modify OsIf | 使能OsIf | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | finish within 1 min. | ok |
| RTD-MEX-UART-003 | UART | DMA mode | 修改DMA | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | finish within 3 min. | ok |
"""

# Catalog with no "within N min" KPI entries at all.
SAMPLE_MD_NO_KPI = """
## 2. Test cases

| ID | Module | Scenario | Subagent Prompt | Test fixture | KPI | Pass criteria |
| --- | --- | --- | --- | --- | --- | --- |
| RTD-MEX-FOO-001 | Foo | Some scenario | Some prompt | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | N/A | Some criteria |
"""


class TestMaxKpiMinutes:
    def test_returns_maximum_kpi_from_mixed_catalog(self, tmp_path):
        """max_kpi_minutes returns 3 when catalog has KPIs of 1, 2, and 3 min."""
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD_MIXED_KPI, encoding="utf-8")

        result = mod.max_kpi_minutes(md_file)

        assert result == 3

    def test_returns_max_from_real_catalog(self):
        """Smoke-test against the live catalog: max KPI must be >= 3 (UART-003)."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]
        real_md = repo_root / "docs" / "tests" / "rtd-config-test-cases.md"

        result = mod.max_kpi_minutes(real_md)

        # UART-003 has within 3 min; no case should exceed that in the current catalog
        assert result >= 3

    def test_raises_value_error_when_no_kpi_found(self, tmp_path):
        """max_kpi_minutes raises ValueError if no 'within N min' pattern is found."""
        mod = load_module()
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD_NO_KPI, encoding="utf-8")

        with pytest.raises(ValueError):
            mod.max_kpi_minutes(md_file)


# ---------------------------------------------------------------------------
# 3. Prompt building: build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def _make_case(self, mod):
        """Return a minimal Case object for prompt tests."""
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU的时钟配置，外部晶振16MHz，CORE_CLK=160MHz",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def test_contains_skill_md_path(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        assert str(skill_md) in prompt

    def test_contains_project_dir(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        assert str(project_dir) in prompt

    def test_contains_verbatim_case_prompt(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        assert "修改MCU的时钟配置" in prompt
        assert "外部晶振16MHz" in prompt
        assert "CORE_CLK=160MHz" in prompt

    def test_contains_blackbox_result_suffix(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        assert "BLACKBOX_RESULT" in prompt

    def test_contains_json_keys_in_suffix(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        # The return-suffix must instruct the agent to emit configured/validate_status/notes
        assert "configured" in prompt
        assert "validate_status" in prompt
        assert "notes" in prompt

    def test_suffix_requires_check_before_validate_for_kpi(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        assert "run `check` before `validate`" in prompt
        assert "Do not run `validate` before `check`" in prompt

    def test_instructs_how_to_invoke_skill_cli(self, tmp_path):
        mod = load_module()
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# skill\n", encoding="utf-8")
        project_dir = tmp_path / "MyProject"

        prompt = mod.build_prompt(self._make_case(mod), skill_md, project_dir)

        # Must tell the agent how to run the CLI
        assert "python" in prompt.lower()


# ---------------------------------------------------------------------------
# 4. Codex runner: run_codex
# ---------------------------------------------------------------------------

class TestRunCodex:
    def _fake_completed(self, returncode=0, stdout="done", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_argv_shape_and_stdin_wiring(self, tmp_path):
        mod = load_module()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return self._fake_completed()

        fake_codex = str(tmp_path / "codex")

        with patch("shutil.which", return_value=fake_codex), \
             patch("subprocess.run", side_effect=fake_run):
            result = mod.run_codex(
                prompt="hello agent",
                workdir=tmp_path,
                timeout_s=300,
                sandbox="workspace-write",
            )

        argv = captured["args"][0]
        kwargs = captured["kwargs"]

        # Exact argv shape
        assert argv[0] == fake_codex
        assert argv[1] == "exec"
        assert "-s" in argv
        ws_idx = argv.index("-s")
        assert argv[ws_idx + 1] == "workspace-write"
        assert "-c" in argv
        c_idx = argv.index("-c")
        assert argv[c_idx + 1] == "approval_policy=never"
        assert "--skip-git-repo-check" in argv
        assert "--cd" in argv
        cd_idx = argv.index("--cd")
        assert argv[cd_idx + 1] == str(tmp_path)

        # stdin wiring
        assert kwargs.get("input") == "hello agent"
        assert kwargs.get("text") is True

        # timeout passed
        assert kwargs.get("timeout") == 300

        # Normal exit -> not timed_out
        assert result.timed_out is False
        assert result.exit_code == 0

    def test_sandbox_propagated_to_argv(self, tmp_path):
        mod = load_module()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["args"] = args[0]
            return self._fake_completed()

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", side_effect=fake_run):
            mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="read-only",
            )

        argv = captured["args"]
        ws_idx = argv.index("-s")
        assert argv[ws_idx + 1] == "read-only"

    def test_timeout_expired_returns_timed_out_true(self, tmp_path):
        mod = load_module()

        exc = subprocess.TimeoutExpired(cmd=["codex"], timeout=10)
        exc.stdout = "partial output"
        exc.stderr = "partial err"

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", side_effect=exc):
            result = mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=10,
                sandbox="workspace-write",
            )

        assert result.timed_out is True
        assert result.stdout == "partial output"
        assert result.stderr == "partial err"

    def test_timeout_expired_partial_output_none_handled(self, tmp_path):
        """TimeoutExpired with stdout/stderr=None must not crash."""
        mod = load_module()

        exc = subprocess.TimeoutExpired(cmd=["codex"], timeout=5)
        exc.stdout = None
        exc.stderr = None

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", side_effect=exc):
            result = mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=5,
                sandbox="workspace-write",
            )

        assert result.timed_out is True
        # stdout/stderr must be str (empty) not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)

    def test_codex_not_found_raises_clear_error(self, tmp_path):
        mod = load_module()

        with patch("shutil.which", return_value=None):
            with pytest.raises((RuntimeError, SystemExit, FileNotFoundError)) as exc_info:
                mod.run_codex(
                    prompt="test",
                    workdir=tmp_path,
                    timeout_s=60,
                    sandbox="workspace-write",
                )
        assert "codex" in str(exc_info.value).lower()

    def test_run_result_has_elapsed_s(self, tmp_path):
        mod = load_module()

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", return_value=self._fake_completed(stdout="ok")):
            result = mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )

        assert hasattr(result, "elapsed_s")
        assert isinstance(result.elapsed_s, float)
        assert result.elapsed_s >= 0.0

    def test_nonzero_exit_code_propagated(self, tmp_path):
        mod = load_module()

        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", return_value=self._fake_completed(returncode=1)):
            result = mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )

        assert result.exit_code == 1
        assert result.timed_out is False

    def test_codex_cmd_fallback_on_windows(self, tmp_path):
        """When 'codex' is not found by which, fall back to 'codex.cmd'."""
        mod = load_module()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["argv"] = args[0]
            return self._fake_completed()

        def fake_which(name):
            if name == "codex":
                return None
            if name == "codex.cmd":
                return r"C:\npm\codex.cmd"
            return None

        with patch("shutil.which", side_effect=fake_which), \
             patch("subprocess.run", side_effect=fake_run):
            result = mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )

        assert captured["argv"][0] == r"C:\npm\codex.cmd"
        assert result.exit_code == 0

# ---------------------------------------------------------------------------
# 5. Pipeline integration: wiring test (no real codex or S32DS)
# ---------------------------------------------------------------------------

class TestPipelineWiring:
    """Verify that the prepare → build → run → summary wiring is correct
    without invoking real codex, deploy, or S32DS."""

    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def test_run_pipeline_returns_json_summary(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]
        fixture_src = (
            repo_root / "tests" / "fixtures" / "nxp" / "ds" / "s32k3" / "Uart_Example_S32K344"
        )

        fake_run_result = mod.RunResult(
            exit_code=0,
            timed_out=False,
            stdout="some output\nBLACKBOX_RESULT {\"configured\": true, \"validate_status\": \"ok\", \"notes\": \"\"}\n",
            stderr="",
            elapsed_s=1.23,
        )

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            # Create the expected skill path so the pipeline can find it
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return fake_run_result

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=360,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
        )

        # Must be a dict with the required keys
        assert isinstance(summary, dict)
        assert summary["case"] == "RTD-MEX-MCU-001"
        assert summary["agent"] == "codex"
        assert summary["exit_code"] == 0
        assert summary["timed_out"] is False
        assert summary["elapsed_s"] == pytest.approx(1.23)
        # blackbox_result must be parsed JSON (not raw string)
        assert summary["blackbox_result"] is not None
        assert summary["blackbox_result"]["configured"] is True

    def test_run_pipeline_workdir_contains_fixture(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        seen_workdir = {}

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            seen_workdir["path"] = workdir
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.5
            )

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,  # keep workdir so we can inspect it
        )

        workdir = seen_workdir["path"]
        # The fixture dir must have been copied into workdir
        assert (workdir / "Uart_Example_S32K344").is_dir()

    def test_run_pipeline_prompt_contains_case_prompt(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        seen_prompt = {}

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            seen_prompt["value"] = prompt
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.5
            )

        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
        )

        assert "修改MCU配置" in seen_prompt["value"]
        assert "BLACKBOX_RESULT" in seen_prompt["value"]

    def test_run_pipeline_log_written(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0,
                timed_out=False,
                stdout="runner stdout",
                stderr="runner stderr",
                elapsed_s=0.5,
            )

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,  # keep workdir so we can read the log
        )

        log_path = Path(summary["log_path"])
        assert log_path.is_file()
        log_content = log_path.read_text(encoding="utf-8")
        assert "runner stdout" in log_content

    def test_run_pipeline_timeout_multiplier(self, tmp_path):
        """timeout_s default is 3 * kpi_minutes * 60; override is respected."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        seen_timeout = {}

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            seen_timeout["value"] = timeout_s
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.0
            )

        # Override timeout explicitly
        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=999,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
        )

        assert seen_timeout["value"] == 999

    def test_main_default_timeout_uses_max_kpi(self, tmp_path):
        """When --timeout-seconds is omitted, main() passes 3 * max_kpi_minutes * 60 to the runner."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        # Build a small inline catalog where max KPI is 3 min (UART-003)
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")

        seen_timeout = {}

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            seen_timeout["value"] = timeout_s
            return mod.RunResult(
                exit_code=0, timed_out=False,
                stdout='BLACKBOX_RESULT {"configured": true, "validate_status": "ok", "notes": ""}',
                stderr="", elapsed_s=1.0,
            )

        # Monkey-patch _default_deploy and the runner so main() doesn't need
        # real codex or S32DS, and redirect the test-cases md to our inline file.
        import io
        import contextlib

        with patch.object(mod, "_default_deploy", fake_deploy), \
             patch.object(mod, "get_runner", return_value=fake_runner), \
             patch.object(mod, "resolve_agent", return_value=("codex", "flag")), \
             patch.object(mod, "REPO_ROOT", repo_root):
            # Override the test_cases_md lookup inside main by patching parse_case
            # and max_kpi_minutes to use our inline md_file.
            real_parse = mod.parse_case
            real_max_kpi = mod.max_kpi_minutes

            def patched_parse(path, case_id):
                return real_parse(md_file, case_id)

            def patched_max_kpi(path):
                return real_max_kpi(md_file)

            with patch.object(mod, "parse_case", side_effect=patched_parse), \
                 patch.object(mod, "max_kpi_minutes", side_effect=patched_max_kpi):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    exit_code = mod.main([
                        "--case", "RTD-MEX-UART-003",
                        "--temp-base", str(tmp_path),
                        # No --agent: resolve_agent is patched to return codex
                    ])

        # max KPI from SAMPLE_MD is 3 min -> expected timeout = 3 * 3 * 60 = 540
        assert seen_timeout["value"] == 3 * 3 * 60
        assert exit_code == 0

    def test_summary_json_serialisable(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.0
            )

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
        )

        # Must be fully JSON-serialisable (all Path objects converted to str)
        serialised = json.dumps(summary)
        assert isinstance(serialised, str)


# ---------------------------------------------------------------------------
# 5b. Deploy-module loader: _load_deploy_module (issue #13 regression guard)
# ---------------------------------------------------------------------------
#
# Every pipeline test above injects ``deploy_fn``, so the REAL default deploy
# path — ``_default_deploy`` -> ``_load_deploy_module``, which resolves
# ``tools/deploy_rtd_skill.py`` via ``importlib.util`` — is never exercised by
# them.  When the ``import importlib.util`` line was dropped (the issue #12
# import reshuffle), every test still passed while ``python tools/blackbox_e2e.py``
# died at runtime with ``NameError: name 'importlib' is not defined`` on the
# first real deploy.  This test drives the real loader so the import can never
# regress unnoticed again.

class TestLoadDeployModule:
    def test_load_deploy_module_imports_real_deploy(self):
        """_load_deploy_module must load tools/deploy_rtd_skill.py through
        importlib.util (no NameError) and expose a callable ``deploy``."""
        mod = load_module()
        deploy_mod = mod._load_deploy_module()
        assert hasattr(deploy_mod, "deploy"), "deploy_rtd_skill must expose deploy()"
        assert callable(deploy_mod.deploy)


# ---------------------------------------------------------------------------
# 6. New targeted tests for the four cleanup items
# ---------------------------------------------------------------------------

class TestIssue1DeployResultDestination:
    """MAJOR: run_pipeline must derive skill_dir from DeployResult.destination,
    not from a hardcoded '.agents/skills/<name>' path.

    Uses a DeployResult-like namedtuple for a non-codex agent with a CUSTOM
    destination and asserts that build_prompt receives THAT skill_dir, not
    the codex-specific one.
    """

    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def test_pipeline_uses_deploy_result_destination_not_hardcoded(self, tmp_path):
        """run_pipeline must point the agent at DeployResult.destination, not
        a hardcoded path.  Uses opencode as the agent (deploy_agent='codex'), and
        a custom deploy destination under .custom-skills/ to prove the pipeline
        reads the destination from the DeployResult, not from any hardcoded path."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        # Custom destination — non-standard layout to verify the pipeline uses
        # DeployResult.destination, not a hardcoded '.agents/skills/<name>' path.
        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            # Deploy under a custom path — not the standard .agents/skills/
            target = workdir_arg / ".custom-skills" / "autombd-rtd"
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(
                "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
            )
            (target / "__main__.py").write_text("# stub\n", encoding="utf-8")
            # Return a DeployResult with the non-standard destination
            return (SimpleNamespace(agent="codex", destination=target),)

        seen_skill_md = {}

        def fake_runner(prompt, workdir, timeout_s, sandbox, model=None):
            # The prompt contains the skill_md_path — capture it.
            seen_skill_md["prompt"] = prompt
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.1
            )

        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="opencode",  # opencode uses deploy_agent="codex"
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,
        )

        prompt = seen_skill_md["prompt"]
        # The prompt must reference the custom-skills destination, not the
        # hardcoded .agents/skills/ path — proving pipeline uses DeployResult.destination.
        assert ".custom-skills" in prompt, (
            f"Expected '.custom-skills' path in prompt (from DeployResult.destination), "
            f"got:\n{prompt[:400]}"
        )

    def test_pipeline_codex_still_uses_agents_skills_path(self, tmp_path):
        """Codex agent must still point at .agents/skills/<SKILL_NAME> when
        DeployResult.destination resolves to that path — the codex primary
        invocation path is unchanged."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            # codex layout
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
            )
            (skill_dir / "__main__.py").write_text("# stub\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        seen_prompt = {}

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            seen_prompt["value"] = prompt
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.1
            )

        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,
        )

        prompt = seen_prompt["value"]
        assert ".agents" in prompt


class TestIssue2CmdFallback:
    """minor: When primary subprocess.run raises FileNotFoundError/OSError
    and codex_path ends with .cmd/.bat on Windows, retry via 'cmd /c'."""

    def _fake_completed(self, returncode=0, stdout="done", stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_cmd_fallback_invoked_on_file_not_found_with_cmd_extension(self, tmp_path):
        """On Windows, if direct invocation of a .cmd path fails with
        FileNotFoundError, the fallback should retry via ['cmd', '/c', path, ...]."""
        mod = load_module()
        import sys as _sys

        # The fallback only fires on Windows (sys.platform == 'win32').
        # We force the platform check by patching sys.platform.
        call_log = []

        codex_cmd_path = r"C:\npm\codex.cmd"

        def fake_run(*args, **kwargs):
            argv = args[0]
            call_log.append(list(argv))
            if argv[0] == codex_cmd_path:
                # Simulate direct .cmd invocation failing.
                raise FileNotFoundError(f"No such file: {codex_cmd_path}")
            # cmd /c fallback succeeds.
            return self._fake_completed(stdout="fallback ok")

        with patch("shutil.which", return_value=codex_cmd_path), \
             patch("subprocess.run", side_effect=fake_run), \
             patch.object(_sys, "platform", "win32"):
            result = mod.run_codex(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )

        # At least two calls: direct, then fallback.
        assert len(call_log) >= 2, f"Expected at least 2 subprocess.run calls, got: {call_log}"
        fallback_argv = call_log[-1]
        assert fallback_argv[0] == "cmd", f"fallback[0] must be 'cmd', got {fallback_argv}"
        assert fallback_argv[1] == "/c", f"fallback[1] must be '/c', got {fallback_argv}"
        assert fallback_argv[2] == codex_cmd_path, f"fallback[2] must be codex path, got {fallback_argv}"
        assert result.exit_code == 0

    def test_no_fallback_when_primary_path_is_not_cmd_bat(self, tmp_path):
        """If the path does not end in .cmd/.bat, FileNotFoundError must propagate
        (or be surfaced as RuntimeError), not silently retried."""
        mod = load_module()
        import sys as _sys

        regular_path = "/usr/local/bin/codex"

        def fake_run(*args, **kwargs):
            raise FileNotFoundError("No such file: codex")

        with patch("shutil.which", return_value=regular_path), \
             patch("subprocess.run", side_effect=fake_run), \
             patch.object(_sys, "platform", "win32"):
            with pytest.raises((FileNotFoundError, OSError, RuntimeError)):
                mod.run_codex(
                    prompt="test",
                    workdir=tmp_path,
                    timeout_s=60,
                    sandbox="workspace-write",
                )


class TestIssue3NoDeadTryCatch:
    """minor: The dead 'try/except Exception: raise' wrapper must be gone.

    We verify that an exception raised INSIDE run_pipeline (by deploy_fn)
    propagates cleanly — this was already true, but the test documents
    the expected behavior and ensures no regression from removing the wrapper.
    """

    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def test_exception_in_deploy_propagates_without_wrapping(self, tmp_path):
        """An exception in deploy_fn must propagate as-is (not re-raised by a
        dead wrapper or swallowed)."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        class _SentinelError(RuntimeError):
            pass

        def bad_deploy(repo_root_arg, workdir_arg, agents):
            raise _SentinelError("deploy exploded")

        with pytest.raises(_SentinelError, match="deploy exploded"):
            mod.run_pipeline(
                case=self._make_fake_case(mod),
                agent="codex",
                sandbox="workspace-write",
                timeout_s=60,
                repo_root=repo_root,
                temp_base=tmp_path,
                deploy_fn=bad_deploy,
            )


class TestIssue4ScenarioInSummary:
    """minor: run_pipeline summary must include 'scenario' from Case.scenario."""

    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock configuration",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def test_summary_contains_scenario_field(self, tmp_path):
        """The summary dict returned by run_pipeline must have key 'scenario'
        equal to case.scenario."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
            )
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.0
            )

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
        )

        assert "scenario" in summary, "summary must have 'scenario' key"
        assert summary["scenario"] == "Modify MCU clock configuration"

    def test_summary_scenario_is_json_serialisable(self, tmp_path):
        """'scenario' in summary must survive json.dumps (it is a plain string)."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
            )
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.0
            )

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="codex",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
        )

        serialised = json.loads(json.dumps(summary))
        assert serialised["scenario"] == "Modify MCU clock configuration"


# ---------------------------------------------------------------------------
# 7. Session id capture + KPI extraction (v0.2.0)
# ---------------------------------------------------------------------------

class TestExtractSessionId:
    def test_extracts_uuid_from_banner(self):
        mod = load_module()
        stderr = (
            "OpenAI Codex v0.139.0\n"
            "--------\n"
            "session id: 019ecb9d-deeb-7bd3-a779-e10d4066d570\n"
            "--------\n"
        )
        assert mod._extract_session_id(stderr) == "019ecb9d-deeb-7bd3-a779-e10d4066d570"

    def test_returns_none_when_absent(self):
        mod = load_module()
        assert mod._extract_session_id("no banner here\nmodel: gpt-5.5\n") is None

    def test_returns_none_on_empty(self):
        mod = load_module()
        assert mod._extract_session_id("") is None


class TestRunCodexCapturesSessionId:
    def _fake_completed(self, stdout="done", stderr=""):
        result = MagicMock()
        result.returncode = 0
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_session_id_captured_from_stderr_banner(self, tmp_path):
        mod = load_module()
        completed = self._fake_completed(
            stderr="OpenAI Codex\nsession id: 019ecb9d-deeb-7bd3-a779-e10d4066d570\n"
        )
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", return_value=completed):
            result = mod.run_codex(
                prompt="x", workdir=tmp_path, timeout_s=60, sandbox="workspace-write"
            )
        assert result.session_id == "019ecb9d-deeb-7bd3-a779-e10d4066d570"

    def test_session_id_none_when_no_banner(self, tmp_path):
        mod = load_module()
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", return_value=self._fake_completed(stderr="")):
            result = mod.run_codex(
                prompt="x", workdir=tmp_path, timeout_s=60, sandbox="workspace-write"
            )
        assert result.session_id is None

    def test_session_id_captured_on_timeout(self, tmp_path):
        """A timed-out run still yields the session id from partial stderr."""
        mod = load_module()
        exc = subprocess.TimeoutExpired(cmd=["codex"], timeout=10)
        exc.stdout = "partial"
        exc.stderr = "session id: 019ecb9d-deeb-7bd3-a779-e10d4066d570\n"
        with patch("shutil.which", return_value="/usr/bin/codex"), \
             patch("subprocess.run", side_effect=exc):
            result = mod.run_codex(
                prompt="x", workdir=tmp_path, timeout_s=10, sandbox="workspace-write"
            )
        assert result.timed_out is True
        assert result.session_id == "019ecb9d-deeb-7bd3-a779-e10d4066d570"


class TestFindCodexSessionFile:
    def _seed_session(self, codex_home, session_id, ts="2026-06-15T22-09-41"):
        sub = codex_home / "sessions" / "2026" / "06" / "15"
        sub.mkdir(parents=True, exist_ok=True)
        f = sub / f"rollout-{ts}-{session_id}.jsonl"
        f.write_text("{}", encoding="utf-8")
        return f

    def test_finds_session_by_embedded_uuid(self, tmp_path):
        mod = load_module()
        sid = "019ecb9d-deeb-7bd3-a779-e10d4066d570"
        expected = self._seed_session(tmp_path, sid)
        # decoy with a different uuid must not be returned
        self._seed_session(tmp_path, "00000000-0000-0000-0000-000000000000")
        assert mod.find_codex_session_file(sid, codex_home=tmp_path) == expected

    def test_returns_none_when_missing(self, tmp_path):
        mod = load_module()
        assert mod.find_codex_session_file("absent-id", codex_home=tmp_path) is None

    def test_returns_none_on_empty_id(self, tmp_path):
        mod = load_module()
        assert mod.find_codex_session_file("", codex_home=tmp_path) is None


# A synthetic rollout that mirrors the real codex schema: task markers, a read,
# a dry-run plan (mcu set WITHOUT --configure), one mutating edit (--configure),
# and a 120 s validate.  Span 14:00:00 -> 14:02:30 = 150 s; validate 120 s;
# validation-excluded 30 s; edit attempts 1.
_KPI_EVENTS = [
    {"timestamp": "2026-06-15T14:00:00.000Z", "payload": {"type": "task_started"}},
    {"timestamp": "2026-06-15T14:00:02.000Z", "payload": {"type": "function_call", "call_id": "c0", "arguments": json.dumps({"command": "Get-Content .\\SKILL.md"})}},
    {"timestamp": "2026-06-15T14:00:03.000Z", "payload": {"type": "function_call_output", "call_id": "c0"}},
    {"timestamp": "2026-06-15T14:00:08.000Z", "payload": {"type": "function_call", "call_id": "c1", "arguments": json.dumps({"command": "python skill mcu set --core-clk 160 --json"})}},
    {"timestamp": "2026-06-15T14:00:09.000Z", "payload": {"type": "function_call_output", "call_id": "c1"}},
    {"timestamp": "2026-06-15T14:00:10.000Z", "payload": {"type": "function_call", "call_id": "c2", "arguments": json.dumps({"command": "python skill mcu set --core-clk 160 --configure --json"})}},
    {"timestamp": "2026-06-15T14:00:11.000Z", "payload": {"type": "function_call_output", "call_id": "c2"}},
    {"timestamp": "2026-06-15T14:00:20.000Z", "payload": {"type": "function_call", "call_id": "c3", "arguments": json.dumps({"command": "python skill validate --json"})}},
    {"timestamp": "2026-06-15T14:02:20.000Z", "payload": {"type": "function_call_output", "call_id": "c3"}},
    {"timestamp": "2026-06-15T14:02:30.000Z", "payload": {"type": "task_complete"}},
]


def _write_session(path, events):
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return path


class TestComputeSessionKpi:
    def test_edit_attempts_counts_only_configure(self, tmp_path):
        mod = load_module()
        sp = _write_session(tmp_path / "s.jsonl", _KPI_EVENTS)
        kpi = mod.compute_session_kpi(sp)
        # the plan (no --configure) must NOT count; only the --configure edit does
        assert kpi["edit_attempts"] == 1

    def test_validate_runs_and_excluded_time(self, tmp_path):
        mod = load_module()
        sp = _write_session(tmp_path / "s.jsonl", _KPI_EVENTS)
        kpi = mod.compute_session_kpi(sp)
        assert kpi["validate_runs_s"] == [120.0]
        assert kpi["total_span_s"] == 150.0
        assert kpi["validation_excluded_s"] == 30.0

    def test_commands_timeline_flags(self, tmp_path):
        mod = load_module()
        sp = _write_session(tmp_path / "s.jsonl", _KPI_EVENTS)
        kpi = mod.compute_session_kpi(sp)
        by_edit = [c for c in kpi["commands"] if c["is_edit"]]
        by_validate = [c for c in kpi["commands"] if c["is_validate"]]
        assert len(by_edit) == 1 and "--configure" in by_edit[0]["command"]
        assert len(by_validate) == 1 and "validate" in by_validate[0]["command"]

    def test_falls_back_to_call_span_without_task_markers(self, tmp_path):
        """No task_started/complete -> span = first call ts -> last output ts."""
        mod = load_module()
        events = [e for e in _KPI_EVENTS if e["payload"]["type"] not in ("task_started", "task_complete")]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)
        # first call 14:00:02 -> last output 14:02:20 = 138 s; validate 120 s -> 18 s
        assert kpi["total_span_s"] == 138.0
        assert kpi["validation_excluded_s"] == 18.0
        assert kpi["edit_attempts"] == 1

    def test_skips_malformed_lines(self, tmp_path):
        mod = load_module()
        sp = tmp_path / "s.jsonl"
        sp.write_text(
            "not json\n" + "\n".join(json.dumps(e) for e in _KPI_EVENTS) + "\n{bad}\n",
            encoding="utf-8",
        )
        kpi = mod.compute_session_kpi(sp)
        assert kpi["edit_attempts"] == 1
        assert kpi["validate_runs_s"] == [120.0]


# ---------------------------------------------------------------------------
# 7b. Canonical kpi_seconds window: [context_injected -> check_passed]
# ---------------------------------------------------------------------------
#
# The owner-locked KPI window excludes (a) the task_started->first-context-event
# startup gap and (b) everything after the standalone `check` (the `validate`
# vendor-gate runtime + the trailing report).  These tests are independent of
# total_span_s/validate timing on purpose -- the window is anchored only to the
# context-injection event and the standalone `check`'s function_call_output.

# context injected at task_started+10s; standalone `check` dispatched, its
# output lands at +70s (kpi_seconds == 60.0); `validate` follows afterwards and
# must NOT affect kpi_seconds even though it dominates total_span_s.
_KPI_WINDOW_EVENTS = [
    {"timestamp": "2026-06-17T09:00:00.000Z", "payload": {"type": "task_started"}},
    {"timestamp": "2026-06-17T09:00:10.000Z", "payload": {"type": "user_message", "message": "修改MCU的时钟配置"}},
    {"timestamp": "2026-06-17T09:00:12.000Z", "payload": {"type": "function_call", "call_id": "e0", "arguments": json.dumps({"command": "Get-Content .\\SKILL.md"})}},
    {"timestamp": "2026-06-17T09:00:13.000Z", "payload": {"type": "function_call_output", "call_id": "e0"}},
    {"timestamp": "2026-06-17T09:00:20.000Z", "payload": {"type": "function_call", "call_id": "e1", "arguments": json.dumps({"command": "python skill mcu set --core-clk 160 --configure --json"})}},
    {"timestamp": "2026-06-17T09:00:21.000Z", "payload": {"type": "function_call_output", "call_id": "e1"}},
    {"timestamp": "2026-06-17T09:01:00.000Z", "payload": {"type": "function_call", "call_id": "e2", "arguments": json.dumps({"command": "python skill check --json"})}},
    {"timestamp": "2026-06-17T09:01:10.000Z", "payload": {"type": "function_call_output", "call_id": "e2"}},
    {"timestamp": "2026-06-17T09:01:15.000Z", "payload": {"type": "function_call", "call_id": "e3", "arguments": json.dumps({"command": "python skill validate --json"})}},
    {"timestamp": "2026-06-17T09:03:35.000Z", "payload": {"type": "function_call_output", "call_id": "e3"}},
    {"timestamp": "2026-06-17T09:03:40.000Z", "payload": {"type": "task_complete"}},
]


class TestComputeSessionKpiWindow:
    def test_kpi_seconds_equals_context_to_check_output_window(self, tmp_path):
        """kpi_seconds == check_output_ts - context_ts == 60.0, regardless of
        the much larger total_span_s/validate duration that follows `check`."""
        mod = load_module()
        sp = _write_session(tmp_path / "s.jsonl", _KPI_WINDOW_EVENTS)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["kpi_seconds"] == 60.0
        assert kpi["context_injected_ts"] == "2026-06-17T09:00:10.000Z"
        assert kpi["check_passed_ts"] == "2026-06-17T09:01:10.000Z"
        # Sanity: the diagnostic total_span_s is much larger (it includes the
        # 140 s validate + the trailing report window) -- kpi_seconds must NOT
        # equal it, proving the two metrics are independent.
        assert kpi["total_span_s"] is not None
        assert kpi["total_span_s"] != kpi["kpi_seconds"]

    def test_kpi_seconds_excludes_standalone_check_from_validate_detection(self, tmp_path):
        """The standalone `check` call must not be miscounted as a validate run,
        and `validate` must not be miscounted as the standalone check."""
        mod = load_module()
        sp = _write_session(tmp_path / "s.jsonl", _KPI_WINDOW_EVENTS)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["validate_runs_s"] == [140.0]
        assert kpi["edit_attempts"] == 1

    def test_kpi_seconds_back_to_back_dispatch_ends_at_check_output_not_validate(self, tmp_path):
        """check and validate function_calls dispatched back-to-back (both
        issued before either output returns) must still pair by call_id, and
        kpi_seconds must end at the CHECK output -- not the validate output,
        even though the validate function_call is issued (and may complete)
        first in the raw event order."""
        mod = load_module()
        events = [
            {"timestamp": "2026-06-17T10:00:00.000Z", "payload": {"type": "task_started"}},
            {"timestamp": "2026-06-17T10:00:05.000Z", "payload": {"type": "message", "message": "context"}},
            # validate dispatched FIRST...
            {"timestamp": "2026-06-17T10:00:06.000Z", "payload": {"type": "function_call", "call_id": "v0", "arguments": json.dumps({"command": "python skill validate --json"})}},
            # ...then check dispatched SECOND, before either output arrives.
            {"timestamp": "2026-06-17T10:00:07.000Z", "payload": {"type": "function_call", "call_id": "k0", "arguments": json.dumps({"command": "python skill check --json"})}},
            # validate's output completes FIRST (it could even race ahead)...
            {"timestamp": "2026-06-17T10:00:50.000Z", "payload": {"type": "function_call_output", "call_id": "v0"}},
            # ...but the check output is what must bound kpi_seconds.
            {"timestamp": "2026-06-17T10:01:05.000Z", "payload": {"type": "function_call_output", "call_id": "k0"}},
            {"timestamp": "2026-06-17T10:01:10.000Z", "payload": {"type": "task_complete"}},
        ]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        # context 10:00:05 -> check output 10:01:05 = 60.0 s, NOT the validate
        # output at 10:00:50 (which would give 45.0 s if pairing were wrong).
        assert kpi["kpi_seconds"] == 60.0
        assert kpi["check_passed_ts"] == "2026-06-17T10:01:05.000Z"

    def test_kpi_seconds_none_when_no_standalone_check(self, tmp_path):
        """No standalone `check` call anywhere in the session -> kpi_seconds is
        None, and the function still returns every other field without raising."""
        mod = load_module()
        # Drop the standalone `check` call_id pair ("e2") entirely -- only the
        # earlier --configure edit and the later validate remain.
        events = [
            e for e in _KPI_WINDOW_EVENTS
            if not (
                e["payload"].get("type") in ("function_call", "function_call_output")
                and e["payload"].get("call_id") == "e2"
            )
        ]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["kpi_seconds"] is None
        assert kpi["check_passed_ts"] is None
        # other diagnostics must still be populated -- no exception, no silent
        # half-filled dict.
        assert kpi["context_injected_ts"] == "2026-06-17T09:00:10.000Z"
        assert kpi["edit_attempts"] == 1
        assert kpi["validate_runs_s"] == [140.0]
        assert kpi["total_span_s"] is not None

    def test_kpi_seconds_none_when_no_context_event(self, tmp_path):
        """No message/user_message event at/after task_started -> kpi_seconds
        is None even though a standalone `check` exists."""
        mod = load_module()
        events = [e for e in _KPI_WINDOW_EVENTS if e["payload"].get("type") not in ("user_message", "message")]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["kpi_seconds"] is None
        assert kpi["context_injected_ts"] is None
        # check_passed_ts is still derivable (the check call/output pair exists)
        assert kpi["check_passed_ts"] == "2026-06-17T09:01:10.000Z"

    def test_kpi_seconds_ignores_context_event_before_task_started(self, tmp_path):
        """A message/user_message timestamped BEFORE task_started (e.g. stray
        system priming) must not be selected as the context-injection anchor;
        only the first one at/after task_started counts."""
        mod = load_module()
        events = [
            {"timestamp": "2026-06-17T08:59:00.000Z", "payload": {"type": "message", "message": "pre-task priming, must be ignored"}},
        ] + _KPI_WINDOW_EVENTS
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["context_injected_ts"] == "2026-06-17T09:00:10.000Z"
        assert kpi["kpi_seconds"] == 60.0

    def test_existing_fields_unchanged_shape_with_new_kpi_fields_present(self, tmp_path):
        """The pre-existing diagnostic fields keep their exact shape; the new
        canonical fields are simply additive keys on the same dict."""
        mod = load_module()
        sp = _write_session(tmp_path / "s.jsonl", _KPI_WINDOW_EVENTS)
        kpi = mod.compute_session_kpi(sp)

        for key in ("edit_attempts", "validate_runs_s", "total_span_s", "validation_excluded_s", "commands"):
            assert key in kpi
        for key in ("kpi_seconds", "context_injected_ts", "check_passed_ts"):
            assert key in kpi

    def test_kpi_window_ignores_check_validate_configure_inside_update_plan(self, tmp_path):
        """REGRESSION (BASENXP baseline): a codex ``update_plan`` call carries its
        plan as ``{"plan": [...]}`` (no "command" key), and its step prose
        routinely contains "check"/"validate"/"--configure". Those plan-tool
        calls must be excluded from ALL classification: never matched as the
        standalone ``check`` (which ended the KPI window ~48 s early on the real
        baseline -> 33 s instead of the true ~81 s), and never inflating
        ``edit_attempts`` / ``validate_runs_s``."""
        mod = load_module()
        events = [
            {"timestamp": "2026-06-17T11:00:00.000Z", "payload": {"type": "task_started"}},
            {"timestamp": "2026-06-17T11:00:10.000Z", "payload": {"type": "user_message", "message": "使能OsIf的系统定时器"}},
            # EARLY update_plan whose prose mentions --configure, check, validate.
            {"timestamp": "2026-06-17T11:00:12.000Z", "payload": {"type": "function_call", "call_id": "p0", "arguments": json.dumps({"plan": [{"step": "run basenxp set --configure", "status": "in_progress"}, {"step": "then run check and validate", "status": "pending"}]})}},
            {"timestamp": "2026-06-17T11:00:13.000Z", "payload": {"type": "function_call_output", "call_id": "p0"}},
            # the one real mutating edit
            {"timestamp": "2026-06-17T11:00:20.000Z", "payload": {"type": "function_call", "call_id": "e1", "arguments": json.dumps({"command": "python skill basenxp set --enable-system-timer --configure --json"})}},
            {"timestamp": "2026-06-17T11:00:21.000Z", "payload": {"type": "function_call_output", "call_id": "e1"}},
            # a second update_plan, again mentioning check
            {"timestamp": "2026-06-17T11:00:25.000Z", "payload": {"type": "function_call", "call_id": "p1", "arguments": json.dumps({"plan": [{"step": "run check then validate", "status": "in_progress"}]})}},
            {"timestamp": "2026-06-17T11:00:26.000Z", "payload": {"type": "function_call_output", "call_id": "p1"}},
            # the REAL standalone check -- this must anchor check_passed
            {"timestamp": "2026-06-17T11:01:10.000Z", "payload": {"type": "function_call", "call_id": "k0", "arguments": json.dumps({"command": "python skill check --project . --json"})}},
            {"timestamp": "2026-06-17T11:01:11.000Z", "payload": {"type": "function_call_output", "call_id": "k0"}},
            # vendor validate afterwards (excluded from the window)
            {"timestamp": "2026-06-17T11:01:12.000Z", "payload": {"type": "function_call", "call_id": "v0", "arguments": json.dumps({"command": "python skill validate --json"})}},
            {"timestamp": "2026-06-17T11:03:30.000Z", "payload": {"type": "function_call_output", "call_id": "v0"}},
            {"timestamp": "2026-06-17T11:03:35.000Z", "payload": {"type": "task_complete"}},
        ]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        # window ends at the REAL check output (11:01:11), NOT the early
        # plan-tool output (11:00:13): 61.0 s, not 3.0 s.
        assert kpi["check_passed_ts"] == "2026-06-17T11:01:11.000Z"
        assert kpi["kpi_seconds"] == 61.0
        # plan-step prose must not inflate edit / validate detection
        assert kpi["edit_attempts"] == 1
        assert kpi["validate_runs_s"] == [138.0]

    def test_check_regex_not_fooled_by_hyphenated_flag(self, tmp_path):
        """A hyphenated flag containing "check" (e.g. ``--skip-git-repo-check``)
        must not be matched as the standalone ``check`` subcommand."""
        mod = load_module()
        events = [
            {"timestamp": "2026-06-17T12:00:00.000Z", "payload": {"type": "task_started"}},
            {"timestamp": "2026-06-17T12:00:05.000Z", "payload": {"type": "message", "message": "ctx"}},
            {"timestamp": "2026-06-17T12:00:06.000Z", "payload": {"type": "function_call", "call_id": "g0", "arguments": json.dumps({"command": "git status --skip-git-repo-check"})}},
            {"timestamp": "2026-06-17T12:00:07.000Z", "payload": {"type": "function_call_output", "call_id": "g0"}},
            {"timestamp": "2026-06-17T12:00:10.000Z", "payload": {"type": "task_complete"}},
        ]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["check_passed_ts"] is None
        assert kpi["kpi_seconds"] is None

    def test_check_regex_requires_subcommand_flag_not_bare_word(self, tmp_path):
        """The bare word "check" in a quoted path/argument (not the skill
        subcommand, which is always ``check --<flag>``) must not be matched as
        the standalone check or anchor the KPI window."""
        mod = load_module()
        events = [
            {"timestamp": "2026-06-17T13:00:00.000Z", "payload": {"type": "task_started"}},
            {"timestamp": "2026-06-17T13:00:05.000Z", "payload": {"type": "message", "message": "ctx"}},
            {"timestamp": "2026-06-17T13:00:06.000Z", "payload": {"type": "function_call", "call_id": "c0", "arguments": json.dumps({"command": "Get-Content -LiteralPath '.\\my check notes.txt'"})}},
            {"timestamp": "2026-06-17T13:00:07.000Z", "payload": {"type": "function_call_output", "call_id": "c0"}},
            {"timestamp": "2026-06-17T13:00:10.000Z", "payload": {"type": "task_complete"}},
        ]
        sp = _write_session(tmp_path / "s.jsonl", events)
        kpi = mod.compute_session_kpi(sp)

        assert kpi["check_passed_ts"] is None
        assert kpi["kpi_seconds"] is None


class TestPipelineKpiWiring:
    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def _fake_deploy(self):
        from types import SimpleNamespace

        def deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
            )
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        return deploy

    def test_summary_includes_session_and_kpi(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="",
                elapsed_s=277.0, session_id="019ecb9d-deeb-7bd3-a779-e10d4066d570",
            )

        fake_kpi = {
            "edit_attempts": 1, "validate_runs_s": [120.0, 55.8],
            "total_span_s": 272.0, "validation_excluded_s": 96.2, "commands": [],
        }
        fake_session = tmp_path / "rollout.jsonl"
        fake_session.write_text("{}", encoding="utf-8")

        with patch.object(mod, "find_codex_session_file", return_value=fake_session), \
             patch.object(mod, "compute_session_kpi", return_value=fake_kpi):
            summary = mod.run_pipeline(
                case=self._make_fake_case(mod), agent="codex",
                sandbox="workspace-write", timeout_s=540, repo_root=repo_root,
                temp_base=tmp_path, deploy_fn=self._fake_deploy(),
                runner_fn=fake_runner, keep=True,
            )

        assert summary["session_id"] == "019ecb9d-deeb-7bd3-a779-e10d4066d570"
        assert summary["session_path"] == str(fake_session)
        assert summary["kpi"] == fake_kpi
        # still fully JSON-serialisable
        json.dumps(summary)

    def test_summary_kpi_none_when_no_session_id(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=1.0
            )

        # find_codex_session_file must NOT be called when there is no session id
        with patch.object(mod, "find_codex_session_file", side_effect=AssertionError("should not be called")):
            summary = mod.run_pipeline(
                case=self._make_fake_case(mod), agent="codex",
                sandbox="workspace-write", timeout_s=60, repo_root=repo_root,
                temp_base=tmp_path, deploy_fn=self._fake_deploy(),
                runner_fn=fake_runner, keep=True,
            )

        assert summary["session_id"] is None
        assert summary["session_path"] is None
        assert summary["kpi"] is None

    def test_summary_records_error_when_session_not_found(self, tmp_path):
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="",
                elapsed_s=1.0, session_id="missing-session",
            )

        with patch.object(mod, "find_codex_session_file", return_value=None):
            summary = mod.run_pipeline(
                case=self._make_fake_case(mod), agent="codex",
                sandbox="workspace-write", timeout_s=60, repo_root=repo_root,
                temp_base=tmp_path, deploy_fn=self._fake_deploy(),
                runner_fn=fake_runner, keep=True,
            )

        assert summary["session_path"] is None
        assert "missing-session" in summary["kpi"]["error"]


class TestCodexComputeKpiCarriesSessionPath:
    """``_codex_compute_kpi`` is the codex adapter's ``compute_kpi`` field.

    The pipeline now dispatches KPI computation uniformly through
    ``adapter.compute_kpi`` for both agents (no more inline ``if agent ==
    "codex":`` special case). For codex that means ``_codex_compute_kpi``
    must itself carry the located ``session_path`` so the pipeline can lift
    it back out to the summary's top-level field.
    """

    def test_returns_kpi_dict_with_session_path_for_located_session(self, tmp_path):
        mod = load_module()
        fake_kpi = {
            "kpi_seconds": 42.0, "edit_attempts": 1, "validate_runs_s": [1.0],
            "total_span_s": 50.0, "validation_excluded_s": 49.0, "commands": [],
        }
        fake_session = tmp_path / "rollout.jsonl"
        fake_session.write_text("{}", encoding="utf-8")
        rr = mod.RunResult(
            exit_code=0, timed_out=False, stdout="", stderr="",
            elapsed_s=50.0, session_id="any-session-id",
        )

        with patch.object(mod, "find_codex_session_file", return_value=fake_session), \
             patch.object(mod, "compute_session_kpi", return_value=fake_kpi):
            kpi = mod._codex_compute_kpi(rr)

        assert kpi["session_path"] == str(fake_session)
        # the rest of compute_session_kpi's fields must be carried through verbatim
        for key, value in fake_kpi.items():
            assert kpi[key] == value

    def test_returns_none_when_no_session_id(self):
        mod = load_module()
        rr = mod.RunResult(exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=1.0)
        assert mod._codex_compute_kpi(rr) is None

    def test_returns_error_dict_without_session_path_when_session_not_found(self, tmp_path):
        mod = load_module()
        rr = mod.RunResult(
            exit_code=0, timed_out=False, stdout="", stderr="",
            elapsed_s=1.0, session_id="missing-session",
        )
        with patch.object(mod, "find_codex_session_file", return_value=None):
            kpi = mod._codex_compute_kpi(rr)

        assert "missing-session" in kpi["error"]
        assert "session_path" not in kpi

    def test_returns_error_dict_on_oserror(self, tmp_path):
        mod = load_module()
        rr = mod.RunResult(
            exit_code=0, timed_out=False, stdout="", stderr="",
            elapsed_s=1.0, session_id="some-session",
        )
        with patch.object(mod, "find_codex_session_file", side_effect=OSError("disk error")):
            kpi = mod._codex_compute_kpi(rr)

        assert "disk error" in kpi["error"]
        assert "session_path" not in kpi


class TestPipelineRoutesKpiThroughAdapter:
    """Prove ``run_pipeline`` dispatches KPI computation uniformly via
    ``adapter.compute_kpi`` for both agents — no inline ``if agent ==
    "codex":`` special case left in the pipeline.
    """

    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def _fake_deploy(self):
        from types import SimpleNamespace

        def deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
            )
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        return deploy

    def test_codex_kpi_flows_through_adapter_compute_kpi(self, tmp_path):
        """Patch the codex adapter's compute_kpi field directly (not the
        internal find/compute free functions) — this only succeeds if
        run_pipeline actually calls ``adapter.compute_kpi(run_result)``
        rather than running its own inline session-lookup logic.
        """
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="",
                elapsed_s=277.0, session_id="019ecb9d-deeb-7bd3-a779-e10d4066d570",
            )

        fake_session_path = str(tmp_path / "rollout.jsonl")
        adapter_kpi = {
            "kpi_seconds": 99.0, "edit_attempts": 2, "validate_runs_s": [3.0],
            "total_span_s": 100.0, "validation_excluded_s": 97.0, "commands": [],
            "session_path": fake_session_path,
        }

        codex_adapter = mod.AGENT_ADAPTERS["codex"]
        patched_adapter = mod.AgentAdapter(
            name=codex_adapter.name,
            deploy_agent=codex_adapter.deploy_agent,
            prepare_workdir=codex_adapter.prepare_workdir,
            run=codex_adapter.run,
            extract_result=codex_adapter.extract_result,
            compute_kpi=lambda rr: dict(adapter_kpi),
        )

        with patch.dict(mod.AGENT_ADAPTERS, {"codex": patched_adapter}), \
             patch.object(mod, "find_codex_session_file", side_effect=AssertionError(
                 "run_pipeline must not call find_codex_session_file directly; "
                 "it must delegate to adapter.compute_kpi"
             )), \
             patch.object(mod, "compute_session_kpi", side_effect=AssertionError(
                 "run_pipeline must not call compute_session_kpi directly; "
                 "it must delegate to adapter.compute_kpi"
             )):
            summary = mod.run_pipeline(
                case=self._make_fake_case(mod), agent="codex",
                sandbox="workspace-write", timeout_s=540, repo_root=repo_root,
                temp_base=tmp_path, deploy_fn=self._fake_deploy(),
                runner_fn=fake_runner, keep=True,
            )

        # session_path is lifted out of the kpi dict to the summary top level
        assert summary["session_path"] == fake_session_path
        assert "session_path" not in summary["kpi"]
        # the rest of the adapter's kpi dict is preserved verbatim
        assert summary["kpi"]["kpi_seconds"] == 99.0
        assert summary["kpi"]["edit_attempts"] == 2
        json.dumps(summary)

    def test_opencode_kpi_session_path_defaults_to_none(self, tmp_path):
        """The opencode adapter's compute_kpi carries no session_path; the
        pipeline summary must still expose session_path (None) at the top
        level without crashing on a missing key.
        """
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=5.0,
            )

        summary = mod.run_pipeline(
            case=self._make_fake_case(mod), agent="opencode",
            sandbox="workspace-write", timeout_s=60, repo_root=repo_root,
            temp_base=tmp_path, deploy_fn=self._fake_deploy(),
            runner_fn=fake_runner, keep=True,
        )

        assert summary["session_path"] is None
        json.dumps(summary)


# ===========================================================================
# 8. OpenCode backend (issue #50)
# ===========================================================================

# ---------------------------------------------------------------------------
# 8a. _find_opencode
# ---------------------------------------------------------------------------

class TestFindOpencode:
    def test_finds_opencode_via_which(self, tmp_path):
        """_find_opencode returns the path when shutil.which('opencode') hits."""
        mod = load_module()
        fake_path = str(tmp_path / "opencode")

        def fake_which(name):
            return fake_path if name == "opencode" else None

        with patch("shutil.which", side_effect=fake_which):
            result = mod._find_opencode()

        assert result == fake_path

    def test_finds_opencode_cmd_fallback(self, tmp_path):
        """_find_opencode falls back to opencode.cmd when opencode is absent."""
        mod = load_module()
        fake_cmd = str(tmp_path / "opencode.cmd")

        def fake_which(name):
            if name == "opencode":
                return None
            if name == "opencode.cmd":
                return fake_cmd
            return None

        with patch("shutil.which", side_effect=fake_which):
            result = mod._find_opencode()

        assert result == fake_cmd

    def test_raises_when_not_found(self):
        """_find_opencode raises RuntimeError with npm install hint when absent."""
        mod = load_module()
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                mod._find_opencode()
        assert "opencode" in str(exc_info.value).lower()
        assert "npm" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 8b. run_opencode — argv shape, STDIN, session_id extraction
# ---------------------------------------------------------------------------

# Minimal NDJSON fixture for a successful opencode run.
# session_id from first step_start; text event carries assistant response.
_OC_NDJSON_BASIC = "\n".join([
    json.dumps({"type": "step_start", "timestamp": 1_000_000, "sessionID": "ses_abcdefghijklmnopqrstuvwxyz", "part": {"type": "step-start"}}),
    json.dumps({"type": "text",       "timestamp": 1_002_000, "sessionID": "ses_abcdefghijklmnopqrstuvwxyz", "part": {"type": "text", "text": "Configuring...\nBLACKBOX_RESULT {\"configured\": true, \"validate_status\": \"passed\", \"notes\": \"\"}", "time": {"start": 1_001_000, "end": 1_002_000}}}),
    json.dumps({"type": "step_finish","timestamp": 1_003_000, "sessionID": "ses_abcdefghijklmnopqrstuvwxyz", "part": {"type": "step-finish", "reason": "stop"}}),
]) + "\n"


class TestRunOpencode:
    def _fake_completed(self, returncode=0, stdout=_OC_NDJSON_BASIC, stderr=""):
        result = MagicMock()
        result.returncode = returncode
        result.stdout = stdout
        result.stderr = stderr
        return result

    def test_argv_shape_no_model(self, tmp_path):
        """run_opencode builds: opencode.cmd run --format json --dangerously-skip-permissions --dir <workdir>"""
        mod = load_module()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["args"] = args[0]
            captured["kwargs"] = kwargs
            return self._fake_completed()

        fake_oc = str(tmp_path / "opencode.cmd")

        with patch("shutil.which", return_value=fake_oc), \
             patch("subprocess.run", side_effect=fake_run):
            result = mod.run_opencode(
                prompt="hello opencode",
                workdir=tmp_path,
                timeout_s=300,
                sandbox="workspace-write",
            )

        argv = captured["args"]
        assert argv[0] == fake_oc
        assert argv[1] == "run"
        assert "--format" in argv
        assert argv[argv.index("--format") + 1] == "json"
        assert "--dangerously-skip-permissions" in argv
        assert "--dir" in argv
        assert argv[argv.index("--dir") + 1] == str(tmp_path)
        # no --model when model not provided
        assert "--model" not in argv

        # stdin wiring
        assert captured["kwargs"].get("input") == "hello opencode"
        assert captured["kwargs"].get("text") is True
        assert captured["kwargs"].get("timeout") == 300

        assert result.timed_out is False
        assert result.exit_code == 0

    def test_argv_shape_with_model(self, tmp_path):
        """When model is provided, --model <value> is appended to argv."""
        mod = load_module()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["args"] = args[0]
            return self._fake_completed()

        with patch("shutil.which", return_value=str(tmp_path / "opencode.cmd")), \
             patch("subprocess.run", side_effect=fake_run):
            mod.run_opencode(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="anything",
                model="deepseek/deepseek-chat",
            )

        argv = captured["args"]
        assert "--model" in argv
        assert argv[argv.index("--model") + 1] == "deepseek/deepseek-chat"

    def test_session_id_parsed_from_first_step_start(self, tmp_path):
        """session_id is extracted from the first step_start event's sessionID field."""
        mod = load_module()
        with patch("shutil.which", return_value=str(tmp_path / "opencode.cmd")), \
             patch("subprocess.run", return_value=self._fake_completed()):
            result = mod.run_opencode(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )
        assert result.session_id == "ses_abcdefghijklmnopqrstuvwxyz"

    def test_session_id_none_when_stdout_empty(self, tmp_path):
        """Empty stdout -> session_id is None, no crash."""
        mod = load_module()
        with patch("shutil.which", return_value=str(tmp_path / "opencode.cmd")), \
             patch("subprocess.run", return_value=self._fake_completed(stdout="")):
            result = mod.run_opencode(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )
        assert result.session_id is None

    def test_session_id_none_when_no_step_start_event(self, tmp_path):
        """NDJSON with no step_start event -> session_id is None."""
        mod = load_module()
        ndjson = json.dumps({"type": "text", "timestamp": 1000, "sessionID": "ses_xyz123", "part": {"type": "text", "text": "hi", "time": {"start": 999, "end": 1000}}}) + "\n"
        with patch("shutil.which", return_value=str(tmp_path / "opencode.cmd")), \
             patch("subprocess.run", return_value=self._fake_completed(stdout=ndjson)):
            result = mod.run_opencode(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )
        # session_id comes from the first step_start; if absent it's None
        # (the first nonempty line is a text event, not step_start)
        assert result.session_id is None

    def test_timeout_returns_timed_out_true(self, tmp_path):
        """TimeoutExpired -> timed_out=True, stdout/stderr are strings."""
        mod = load_module()
        exc = subprocess.TimeoutExpired(cmd=["opencode.cmd"], timeout=5)
        exc.stdout = "partial"
        exc.stderr = ""
        with patch("shutil.which", return_value=str(tmp_path / "opencode.cmd")), \
             patch("subprocess.run", side_effect=exc):
            result = mod.run_opencode(
                prompt="test",
                workdir=tmp_path,
                timeout_s=5,
                sandbox="workspace-write",
            )
        assert result.timed_out is True
        assert isinstance(result.stdout, str)

    def test_not_found_raises_runtime_error(self):
        """opencode not on PATH -> RuntimeError mentioning npm install."""
        mod = load_module()
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="npm"):
                mod.run_opencode(
                    prompt="test",
                    workdir=Path("."),
                    timeout_s=60,
                    sandbox="workspace-write",
                )

    def test_sandbox_ignored_not_in_argv(self, tmp_path):
        """The sandbox argument is accepted but must NOT appear in opencode argv."""
        mod = load_module()
        captured = {}

        def fake_run(*args, **kwargs):
            captured["args"] = args[0]
            return self._fake_completed()

        with patch("shutil.which", return_value=str(tmp_path / "opencode.cmd")), \
             patch("subprocess.run", side_effect=fake_run):
            mod.run_opencode(
                prompt="test",
                workdir=tmp_path,
                timeout_s=60,
                sandbox="workspace-write",
            )

        argv = captured["args"]
        assert "-s" not in argv
        assert "workspace-write" not in argv
        assert "approval_policy=never" not in argv


# ---------------------------------------------------------------------------
# 8c. BLACKBOX_RESULT extraction from NDJSON text events
# ---------------------------------------------------------------------------

# NDJSON fixture with multiple text events; result marker is in the last one.
_OC_NDJSON_MULTI_TEXT = "\n".join([
    json.dumps({"type": "step_start", "timestamp": 2_000_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "step-start"}}),
    json.dumps({"type": "text", "timestamp": 2_001_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "text", "text": "Reading skill...", "time": {"start": 2_000_500, "end": 2_001_000}}}),
    json.dumps({"type": "tool_use", "timestamp": 2_002_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill mcu set --configure --json"}, "output": "ok", "time": {"start": 2_001_500, "end": 2_002_000}}}}),
    json.dumps({"type": "text", "timestamp": 2_003_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "text", "text": "Running check...", "time": {"start": 2_002_500, "end": 2_003_000}}}),
    json.dumps({"type": "tool_use", "timestamp": 2_004_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill check --project . --json"}, "output": "ok", "time": {"start": 2_003_500, "end": 2_004_000}}}}),
    json.dumps({"type": "text", "timestamp": 2_005_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "text", "text": 'Done!\nBLACKBOX_RESULT {"configured": true, "validate_status": "passed", "notes": "all good"}', "time": {"start": 2_004_500, "end": 2_005_000}}}),
    json.dumps({"type": "step_finish", "timestamp": 2_006_000, "sessionID": "ses_11111111111111111111111111", "part": {"type": "step-finish", "reason": "stop"}}),
]) + "\n"


class TestOpencodeExtractBlackboxResult:
    def test_extracts_result_from_last_text_event(self):
        """BLACKBOX_RESULT is found in the concatenated text events."""
        mod = load_module()
        rr = mod.RunResult(
            exit_code=0, timed_out=False, stdout=_OC_NDJSON_MULTI_TEXT,
            stderr="", elapsed_s=5.0, session_id="ses_11111111111111111111111111",
        )
        adapter = mod.AGENT_ADAPTERS["opencode"]
        result = adapter.extract_result(rr)
        assert result is not None
        assert result["configured"] is True
        assert result["validate_status"] == "passed"
        assert result["notes"] == "all good"

    def test_extracts_terminal_result_after_separate_progress_text_events(self):
        """OpenCode 1.18 emits complete assistant text parts for progress
        updates as well as the final answer.  Those independent parts need not
        end with a newline, so they must not be glued to the terminal marker.
        """
        mod = load_module()
        session_id = "ses_platform001terminalresult"
        ndjson = "\n".join([
            json.dumps({"type": "step_start", "timestamp": 4_000_000, "sessionID": session_id, "part": {"type": "step-start"}}),
            json.dumps({"type": "text", "timestamp": 4_001_000, "sessionID": session_id, "part": {"type": "text", "text": "`set` passed. Now running `check`."}}),
            json.dumps({"type": "tool_use", "timestamp": 4_002_000, "sessionID": session_id, "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill check --project . --json"}}}}),
            json.dumps({"type": "text", "timestamp": 4_003_000, "sessionID": session_id, "part": {"type": "text", "text": "`check` passed. Now running `validate`."}}),
            json.dumps({"type": "tool_use", "timestamp": 4_004_000, "sessionID": session_id, "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill validate --project . --json"}}}}),
            json.dumps({"type": "text", "timestamp": 4_005_000, "sessionID": session_id, "part": {"type": "text", "text": 'BLACKBOX_RESULT {"configured": true, "validate_status": "passed", "notes": "platform configured"}'}}),
            json.dumps({"type": "step_finish", "timestamp": 4_006_000, "sessionID": session_id, "part": {"type": "step-finish", "reason": "stop"}}),
        ]) + "\n"
        rr = mod.RunResult(
            exit_code=0, timed_out=False, stdout=ndjson,
            stderr="", elapsed_s=6.0, session_id=session_id,
        )

        result = mod.AGENT_ADAPTERS["opencode"].extract_result(rr)

        assert result == {
            "configured": True,
            "validate_status": "passed",
            "notes": "platform configured",
        }

    def test_returns_none_when_no_marker(self):
        """No BLACKBOX_RESULT marker in text events -> None."""
        mod = load_module()
        ndjson = "\n".join([
            json.dumps({"type": "step_start", "timestamp": 1000, "sessionID": "ses_x", "part": {"type": "step-start"}}),
            json.dumps({"type": "text", "timestamp": 2000, "sessionID": "ses_x", "part": {"type": "text", "text": "No result here.", "time": {"start": 1500, "end": 2000}}}),
        ]) + "\n"
        rr = mod.RunResult(exit_code=0, timed_out=False, stdout=ndjson, stderr="", elapsed_s=1.0)
        adapter = mod.AGENT_ADAPTERS["opencode"]
        assert adapter.extract_result(rr) is None

    def test_rejects_stale_result_when_terminal_text_has_no_marker(self):
        """A marker from an earlier assistant turn is stale; the protocol
        requires BLACKBOX_RESULT to be the terminal emitted line.
        """
        mod = load_module()
        ndjson = "\n".join([
            json.dumps({"type": "text", "timestamp": 1000, "sessionID": "ses_stale", "part": {"type": "text", "text": 'BLACKBOX_RESULT {"configured": false, "validate_status": "skipped", "notes": "stale"}\n'}}),
            json.dumps({"type": "text", "timestamp": 2000, "sessionID": "ses_stale", "part": {"type": "text", "text": "Continuing work without a terminal result."}}),
        ]) + "\n"
        rr = mod.RunResult(exit_code=0, timed_out=False, stdout=ndjson, stderr="", elapsed_s=1.0)

        assert mod.AGENT_ADAPTERS["opencode"].extract_result(rr) is None

    def test_rejects_ambiguous_terminal_text_with_multiple_markers(self):
        """Two terminal markers are ambiguous even when both JSON objects
        are individually well formed.
        """
        mod = load_module()
        text = "\n".join([
            'BLACKBOX_RESULT {"configured": false, "validate_status": "skipped", "notes": "first"}',
            'BLACKBOX_RESULT {"configured": true, "validate_status": "passed", "notes": "second"}',
        ])
        ndjson = json.dumps({
            "type": "text", "timestamp": 1000, "sessionID": "ses_ambiguous",
            "part": {"type": "text", "text": text},
        }) + "\n"
        rr = mod.RunResult(exit_code=0, timed_out=False, stdout=ndjson, stderr="", elapsed_s=1.0)

        assert mod.AGENT_ADAPTERS["opencode"].extract_result(rr) is None

    def test_handles_empty_stdout(self):
        """Empty stdout (no NDJSON) -> None, no exception."""
        mod = load_module()
        rr = mod.RunResult(exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.1)
        adapter = mod.AGENT_ADAPTERS["opencode"]
        assert adapter.extract_result(rr) is None

    def test_extracts_result_split_mid_json_across_two_text_events(self):
        """The BLACKBOX_RESULT marker can be split mid-JSON across two
        consecutive streamed ``text`` events with NO newline between the two
        ``part.text`` fragments (real token-by-token streaming). Verbatim
        concatenation (no inserted separator) must still recover the full,
        parseable marker.
        """
        mod = load_module()
        ndjson = "\n".join([
            json.dumps({"type": "step_start", "timestamp": 3_000_000, "sessionID": "ses_22222222222222222222222222", "part": {"type": "step-start"}}),
            json.dumps({"type": "text", "timestamp": 3_001_000, "sessionID": "ses_22222222222222222222222222", "part": {"type": "text", "text": 'BLACKBOX_RESULT {"configured": tr', "time": {"start": 3_000_500, "end": 3_001_000}}}),
            json.dumps({"type": "text", "timestamp": 3_002_000, "sessionID": "ses_22222222222222222222222222", "part": {"type": "text", "text": 'ue, "validate_status": "passed", "notes": ""}', "time": {"start": 3_001_500, "end": 3_002_000}}}),
            json.dumps({"type": "step_finish", "timestamp": 3_003_000, "sessionID": "ses_22222222222222222222222222", "part": {"type": "step-finish", "reason": "stop"}}),
        ]) + "\n"
        rr = mod.RunResult(
            exit_code=0, timed_out=False, stdout=ndjson,
            stderr="", elapsed_s=3.0, session_id="ses_22222222222222222222222222",
        )
        adapter = mod.AGENT_ADAPTERS["opencode"]
        result = adapter.extract_result(rr)
        assert result is not None
        assert result["configured"] is True
        assert result["validate_status"] == "passed"
        assert result["notes"] == ""

    def test_concatenation_join_is_empty_string_not_newline(self):
        """Regression guard: the text-event join must be verbatim ("") so a
        marker split mid-token is not corrupted by an inserted newline.
        """
        mod = load_module()
        ndjson = "\n".join([
            json.dumps({"type": "text", "timestamp": 1000, "sessionID": "ses_y", "part": {"type": "text", "text": "BLACKBOX_RESULT {\"a\": 1", "time": {"start": 500, "end": 1000}}}),
            json.dumps({"type": "text", "timestamp": 2000, "sessionID": "ses_y", "part": {"type": "text", "text": "}", "time": {"start": 1500, "end": 2000}}}),
        ]) + "\n"
        rr = mod.RunResult(exit_code=0, timed_out=False, stdout=ndjson, stderr="", elapsed_s=1.0)
        adapter = mod.AGENT_ADAPTERS["opencode"]
        result = adapter.extract_result(rr)
        assert result == {"a": 1}


# ---------------------------------------------------------------------------
# 8d. compute_opencode_kpi — from static NDJSON fixture
# ---------------------------------------------------------------------------

# Canonical fixture: 1 configure edit, 1 standalone check, 1 validate.
# context_injected_ms: first step_start timestamp = 3_000_000 ms (epoch)
# check_passed_ms: tool_use check's time.end = 3_060_000 ms
# kpi_seconds = (3_060_000 - 3_000_000) / 1000 = 60.0
# validate tool_use time: start=3_062_000, end=3_202_000 -> 140.0 s
# edit_attempts = 1 (the --configure command)
_OC_KPI_EVENTS = [
    # step_start -> context_injected
    {"type": "step_start",  "timestamp": 3_000_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "step-start"}},
    # assistant text (preamble)
    {"type": "text",        "timestamp": 3_001_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "text", "text": "Reading skill", "time": {"start": 3_000_500, "end": 3_001_000}}},
    # tool: configure edit
    {"type": "tool_use",    "timestamp": 3_010_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill mcu set --configure --json"}, "output": "ok", "time": {"start": 3_009_000, "end": 3_010_000}}}},
    # tool: standalone check (NOT --configure, NOT validate)
    {"type": "tool_use",    "timestamp": 3_060_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill check --project . --json"}, "output": "passed", "time": {"start": 3_050_000, "end": 3_060_000}}}},
    # tool: validate
    {"type": "tool_use",    "timestamp": 3_202_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "tool", "tool": "bash", "state": {"status": "completed", "input": {"command": "python skill validate --project . --json"}, "output": "SEVERE [TOOL] nope", "time": {"start": 3_062_000, "end": 3_202_000}}}},
    # text: result
    {"type": "text",        "timestamp": 3_203_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "text", "text": 'Done!\nBLACKBOX_RESULT {"configured": true, "validate_status": "passed", "notes": ""}', "time": {"start": 3_202_500, "end": 3_203_000}}},
    # step_finish
    {"type": "step_finish", "timestamp": 3_204_000, "sessionID": "ses_kpi0000000000000000000000000", "part": {"type": "step-finish", "reason": "stop"}},
]
_OC_KPI_NDJSON = "\n".join(json.dumps(e) for e in _OC_KPI_EVENTS) + "\n"


class TestComputeOpencodeKpi:
    def test_kpi_seconds_correct(self):
        """kpi_seconds = (check_passed_ms - first_step_start_ms) / 1000 = 60.0"""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        assert kpi["kpi_seconds"] == 60.0

    def test_edit_attempts(self):
        """edit_attempts = 1 (only the --configure command)."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        assert kpi["edit_attempts"] == 1

    def test_validate_runs_s(self):
        """validate_runs_s = [140.0] (one validate call lasting 140 s)."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        assert kpi["validate_runs_s"] == [140.0]

    def test_boundary_timestamps_as_iso_utc(self):
        """context_injected_ts and check_passed_ts are ISO-8601 UTC strings."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        # 3_000_000 ms from epoch -> 1970-01-01T00:50:00+00:00
        assert kpi["context_injected_ts"] is not None
        assert "T" in kpi["context_injected_ts"]
        assert kpi["check_passed_ts"] is not None
        assert "T" in kpi["check_passed_ts"]

    def test_validate_excluded_from_kpi_window(self):
        """The validate tool_use duration (140 s) must NOT affect kpi_seconds."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        # kpi_seconds ends at the check output; validate happens after
        assert kpi["kpi_seconds"] == 60.0
        assert kpi["total_span_s"] is not None
        assert kpi["total_span_s"] > 60.0  # total includes validate + trailing

    def test_commands_timeline_present(self):
        """commands list is populated with at least the configure/check/validate entries."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        assert isinstance(kpi["commands"], list)
        assert len(kpi["commands"]) >= 3
        edits = [c for c in kpi["commands"] if c.get("is_edit")]
        validates = [c for c in kpi["commands"] if c.get("is_validate")]
        assert len(edits) == 1
        assert len(validates) == 1

    def test_kpi_none_when_no_step_start(self):
        """No step_start event -> context_injected_ms missing -> kpi_seconds=None."""
        mod = load_module()
        events = [e for e in _OC_KPI_EVENTS if e["type"] != "step_start"]
        ndjson = "\n".join(json.dumps(e) for e in events) + "\n"
        kpi = mod.compute_opencode_kpi(ndjson)
        assert kpi["kpi_seconds"] is None

    def test_kpi_none_when_no_standalone_check(self):
        """No standalone check tool_use -> check_passed_ms missing -> kpi_seconds=None."""
        mod = load_module()
        events = [
            e for e in _OC_KPI_EVENTS
            if not (
                e["type"] == "tool_use"
                and "check" in e["part"]["state"]["input"]["command"]
                and "--configure" not in e["part"]["state"]["input"]["command"]
                and "validate" not in e["part"]["state"]["input"]["command"]
            )
        ]
        ndjson = "\n".join(json.dumps(e) for e in events) + "\n"
        kpi = mod.compute_opencode_kpi(ndjson)
        assert kpi["kpi_seconds"] is None

    def test_skips_malformed_lines(self):
        """Malformed JSON lines are silently skipped; valid events still processed."""
        mod = load_module()
        bad_ndjson = "not json\n" + _OC_KPI_NDJSON + "\n{bad}\n"
        kpi = mod.compute_opencode_kpi(bad_ndjson)
        assert kpi["edit_attempts"] == 1
        assert kpi["kpi_seconds"] == 60.0

    def test_standalone_check_not_confused_with_configure(self):
        """A command with both 'check' and '--configure' must count as an edit,
        NOT as the standalone check anchor."""
        mod = load_module()
        events = list(_OC_KPI_EVENTS)
        # Replace the standalone check with a check+configure command
        events = [
            e if not (
                e["type"] == "tool_use"
                and "check --project" in e["part"]["state"]["input"]["command"]
            )
            else {
                **e,
                "part": {
                    **e["part"],
                    "state": {
                        **e["part"]["state"],
                        "input": {"command": "python skill check --project . --configure --json"},
                    }
                }
            }
            for e in events
        ]
        ndjson = "\n".join(json.dumps(e) for e in events) + "\n"
        kpi = mod.compute_opencode_kpi(ndjson)
        # check+configure is an edit, not the standalone check -> no kpi anchor
        assert kpi["kpi_seconds"] is None
        assert kpi["edit_attempts"] == 2  # the original --configure + this one

    def test_standalone_check_not_confused_with_validate(self):
        """A 'validate' command must not be matched as the standalone check."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        # validate_runs_s must have exactly one entry (the validate tool_use)
        assert kpi["validate_runs_s"] == [140.0]
        # kpi_seconds ends at check (60.0), NOT at validate end (202 s from start)
        assert kpi["kpi_seconds"] == 60.0

    def test_empty_stdout_returns_none_kpi(self):
        """Empty NDJSON -> kpi_seconds=None, no exception."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi("")
        assert kpi["kpi_seconds"] is None

    def test_validation_excluded_s_present(self):
        """validation_excluded_s = total_span_s - sum(validate_runs_s)."""
        mod = load_module()
        kpi = mod.compute_opencode_kpi(_OC_KPI_NDJSON)
        assert kpi["total_span_s"] is not None
        assert kpi["validation_excluded_s"] is not None
        expected = round(kpi["total_span_s"] - sum(kpi["validate_runs_s"]), 2)
        assert kpi["validation_excluded_s"] == expected


# ---------------------------------------------------------------------------
# 8e. AgentAdapter registry: AGENT_ADAPTERS + get_adapter
# ---------------------------------------------------------------------------

class TestAgentAdapterRegistry:
    def test_adapters_registry_has_codex_and_opencode(self):
        """AGENT_ADAPTERS must have both 'codex' and 'opencode' entries."""
        mod = load_module()
        assert "codex" in mod.AGENT_ADAPTERS
        assert "opencode" in mod.AGENT_ADAPTERS

    def test_get_adapter_returns_opencode_adapter(self):
        mod = load_module()
        adapter = mod.get_adapter("opencode")
        assert adapter.name == "opencode"

    def test_get_adapter_returns_codex_adapter(self):
        mod = load_module()
        adapter = mod.get_adapter("codex")
        assert adapter.name == "codex"

    def test_get_adapter_unknown_raises_value_error(self):
        mod = load_module()
        with pytest.raises(ValueError, match="supported") as exc_info:
            mod.get_adapter("unknown-agent")
        assert "codex" in str(exc_info.value)
        assert "opencode" in str(exc_info.value)

    def test_codex_adapter_deploy_agent_is_codex(self):
        """Codex adapter's deploy_agent must be 'codex'."""
        mod = load_module()
        adapter = mod.get_adapter("codex")
        assert adapter.deploy_agent == "codex"

    def test_opencode_adapter_deploy_agent_is_codex(self):
        """OpenCode adapter's deploy_agent must also be 'codex' (reuses .agents/skills/)."""
        mod = load_module()
        adapter = mod.get_adapter("opencode")
        assert adapter.deploy_agent == "codex"

    def test_codex_adapter_run_is_run_codex(self):
        """Codex adapter's run function must be run_codex."""
        mod = load_module()
        adapter = mod.get_adapter("codex")
        assert adapter.run is mod.run_codex

    def test_opencode_adapter_run_is_run_opencode(self):
        """OpenCode adapter's run function must be run_opencode."""
        mod = load_module()
        adapter = mod.get_adapter("opencode")
        assert adapter.run is mod.run_opencode

    def test_default_agent_constant_is_opencode(self):
        """DEFAULT_AGENT must be 'opencode'."""
        mod = load_module()
        assert mod.DEFAULT_AGENT == "opencode"

    def test_get_runner_still_works_for_codex(self):
        """get_runner shim must still return run_codex for back-compat."""
        mod = load_module()
        assert mod.get_runner("codex") is mod.run_codex

    def test_get_runner_now_works_for_opencode(self):
        """get_runner shim must now also return run_opencode for opencode."""
        mod = load_module()
        assert mod.get_runner("opencode") is mod.run_opencode


# ---------------------------------------------------------------------------
# 8f. OpenCode adapter prepare_workdir (git init)
# ---------------------------------------------------------------------------

class TestOpencodeAdapterPrepareWorkdir:
    def test_opencode_prepare_workdir_calls_git_init(self, tmp_path):
        """opencode adapter.prepare_workdir must run 'git init' in workdir."""
        mod = load_module()
        adapter = mod.get_adapter("opencode")
        called = {}

        def fake_run(argv, **kwargs):
            called["argv"] = argv
            result = MagicMock()
            result.returncode = 0
            return result

        with patch("subprocess.run", side_effect=fake_run):
            adapter.prepare_workdir(tmp_path)

        assert called["argv"][0] == "git"
        assert called["argv"][1] == "init"
        assert str(tmp_path) in called["argv"]

    def test_codex_prepare_workdir_is_noop(self, tmp_path):
        """codex adapter.prepare_workdir must be a no-op (no subprocess.run)."""
        mod = load_module()
        adapter = mod.get_adapter("codex")

        with patch("subprocess.run", side_effect=AssertionError("should not call subprocess")) as mock_run:
            adapter.prepare_workdir(tmp_path)

        # If we get here without AssertionError, the codex adapter is a no-op
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# 8g. Deploy-agent mapping through pipeline (opencode -> codex deploy target)
# ---------------------------------------------------------------------------

class TestOpencodeDeployMapping:
    def _make_fake_case(self, mod):
        return mod.Case(
            id="RTD-MEX-MCU-001",
            scenario="Modify MCU clock",
            prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344",
            kpi_minutes=2,
        )

    def test_opencode_pipeline_deploys_with_codex_agent(self, tmp_path):
        """run_pipeline with agent='opencode' must call deploy_fn with ('codex',) tuple."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]
        captured_agents = {}

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            captured_agents["agents"] = agents
            # Return a codex deploy result (opencode reuses codex layout)
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox, model=None):
            return mod.RunResult(exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.1)

        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="opencode",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,
        )

        assert "codex" in captured_agents["agents"], (
            f"expected ('codex',) in deploy agents, got: {captured_agents['agents']}"
        )

    def test_skill_lives_at_agents_skills_not_opencode_skills(self, tmp_path):
        """Skill must be deployed to .agents/skills/, never .opencode/skills/."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]
        seen_prompt = {}

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox, model=None):
            seen_prompt["value"] = prompt
            return mod.RunResult(exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.1)

        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="opencode",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,
        )

        # Prompt must reference .agents path, never .opencode
        prompt = seen_prompt["value"]
        assert ".agents" in prompt
        assert ".opencode" not in prompt


# ---------------------------------------------------------------------------
# 8h. Agent-selection cache: read/write/resolve
# ---------------------------------------------------------------------------

class TestAgentCache:
    def test_write_and_read_round_trip(self, tmp_path):
        """write_agent_cache then read_agent_cache returns the same agent name."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        mod.write_agent_cache(cache_path, "opencode")
        result = mod.read_agent_cache(cache_path)
        assert result == "opencode"

    def test_write_creates_parent_directory(self, tmp_path):
        """write_agent_cache must create the parent directory if it doesn't exist."""
        mod = load_module()
        cache_path = tmp_path / "new_dir" / "prefs.json"
        mod.write_agent_cache(cache_path, "codex")
        assert cache_path.is_file()

    def test_write_has_version_field(self, tmp_path):
        """Written cache file must include 'version': 1."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        mod.write_agent_cache(cache_path, "opencode")
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data.get("version") == 1

    def test_write_has_updated_at(self, tmp_path):
        """Written cache must include 'updated_at' ISO-8601 UTC string."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        mod.write_agent_cache(cache_path, "opencode")
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "updated_at" in data
        assert "T" in data["updated_at"]  # ISO-8601

    def test_read_returns_none_when_file_missing(self, tmp_path):
        """read_agent_cache returns None when the file doesn't exist."""
        mod = load_module()
        result = mod.read_agent_cache(tmp_path / "nonexistent.json")
        assert result is None

    def test_read_returns_none_on_corrupt_json(self, tmp_path):
        """read_agent_cache returns None on unparseable JSON (never raises)."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        cache_path.write_text("not valid json", encoding="utf-8")
        assert mod.read_agent_cache(cache_path) is None

    def test_read_returns_none_when_key_missing(self, tmp_path):
        """read_agent_cache returns None when 'default_agent' key is absent."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        cache_path.write_text(json.dumps({"version": 1}), encoding="utf-8")
        assert mod.read_agent_cache(cache_path) is None

    def test_read_returns_none_on_empty_file(self, tmp_path):
        """read_agent_cache returns None on empty file (not valid JSON)."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        cache_path.write_text("", encoding="utf-8")
        assert mod.read_agent_cache(cache_path) is None


class TestResolveAgent:
    def test_cli_flag_returns_flag_source_and_writes_cache(self, tmp_path):
        """Explicit --agent writes cache, returns (agent, 'flag')."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        agent, source = mod.resolve_agent("opencode", cache_path)
        assert agent == "opencode"
        assert source == "flag"
        # Cache must be written
        assert mod.read_agent_cache(cache_path) == "opencode"

    def test_cli_flag_codex_returns_flag_source(self, tmp_path):
        """Explicit --agent codex returns (codex, 'flag') and writes cache."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        agent, source = mod.resolve_agent("codex", cache_path)
        assert agent == "codex"
        assert source == "flag"

    def test_invalid_explicit_agent_raises_value_error(self, tmp_path):
        """An explicit --agent with an unregistered name raises ValueError (hard error)."""
        mod = load_module()
        with pytest.raises(ValueError):
            mod.resolve_agent("nonexistent-agent", tmp_path / "prefs.json")

    def test_invalid_agent_does_not_write_cache(self, tmp_path):
        """On invalid explicit agent, the cache must not be written."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        try:
            mod.resolve_agent("nonexistent-agent", cache_path)
        except ValueError:
            pass
        assert not cache_path.exists()

    def test_no_flag_valid_cache_returns_cache_source(self, tmp_path):
        """No --agent + valid cached agent -> (cached_agent, 'cache')."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        mod.write_agent_cache(cache_path, "codex")
        agent, source = mod.resolve_agent(None, cache_path)
        assert agent == "codex"
        assert source == "cache"

    def test_no_flag_missing_cache_returns_default(self, tmp_path):
        """No --agent + no cache file -> (DEFAULT_AGENT, 'default')."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        agent, source = mod.resolve_agent(None, cache_path)
        assert agent == mod.DEFAULT_AGENT
        assert source == "default"

    def test_no_flag_corrupt_cache_returns_default_without_writing(self, tmp_path):
        """Corrupt cache -> fall back to DEFAULT_AGENT, do NOT rewrite the cache."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        cache_path.write_text("corrupted!", encoding="utf-8")
        mtime_before = cache_path.stat().st_mtime
        agent, source = mod.resolve_agent(None, cache_path)
        assert agent == mod.DEFAULT_AGENT
        assert source == "default"
        # Cache must NOT have been rewritten on fallback
        mtime_after = cache_path.stat().st_mtime
        assert mtime_after == mtime_before

    def test_no_flag_unknown_cached_agent_returns_default(self, tmp_path):
        """If cache holds an agent name not in AGENT_ADAPTERS -> DEFAULT_AGENT."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        cache_path.write_text(
            json.dumps({"version": 1, "default_agent": "unknown-backend", "updated_at": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )
        agent, source = mod.resolve_agent(None, cache_path)
        assert agent == mod.DEFAULT_AGENT
        assert source == "default"

    def test_flag_overwrites_existing_cache(self, tmp_path):
        """An explicit --agent must overwrite whatever is in the cache."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        mod.write_agent_cache(cache_path, "codex")
        agent, source = mod.resolve_agent("opencode", cache_path)
        assert agent == "opencode"
        assert source == "flag"
        assert mod.read_agent_cache(cache_path) == "opencode"


# ---------------------------------------------------------------------------
# 8h2. write_agent_cache: transient Windows FS-lock retry (issue #50 FIX-3)
# ---------------------------------------------------------------------------

class TestWriteAgentCacheTransientLockRetry:
    """write_agent_cache's atomic publish must absorb transient Windows
    AV/Defender/indexer lock errors (WinError 5/32/145) on the final
    ``Path.replace`` the same way ``tools/deploy_rtd_skill.py``'s
    ``_retry_fs``/``_is_transient_windows_lock`` idiom does — a small LOCAL
    helper in this module (no cross-module import), non-Windows behavior
    unchanged.
    """

    def test_is_transient_windows_lock_true_for_5_32_145_on_windows(self, monkeypatch):
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        for code in (5, 32, 145):
            err = OSError("locked")
            err.winerror = code
            assert mod._is_transient_windows_lock(err) is True

    def test_is_transient_windows_lock_false_for_other_codes_on_windows(self, monkeypatch):
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        err = OSError("not found")
        err.winerror = 2  # ERROR_FILE_NOT_FOUND
        assert mod._is_transient_windows_lock(err) is False

    def test_is_transient_windows_lock_false_off_windows_even_with_matching_code(self, monkeypatch):
        """Scoped to Windows: an identical winerror=5 off-Windows must not be retried."""
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "linux")
        err = OSError("locked")
        err.winerror = 5
        assert mod._is_transient_windows_lock(err) is False

    def test_retry_fs_recovers_from_transient_windows_lock(self, monkeypatch):
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                err = PermissionError("access denied")
                err.winerror = 5
                raise err

        mod._retry_fs(flaky)
        assert calls["n"] == 3

    def test_retry_fs_reraises_non_transient_error_immediately(self, monkeypatch):
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        calls = {"n": 0}

        def boom():
            calls["n"] += 1
            err = OSError("no such file")
            err.winerror = 2
            raise err

        with pytest.raises(OSError):
            mod._retry_fs(boom)
        assert calls["n"] == 1

    def test_retry_fs_reraises_last_error_after_exhausting_budget(self, monkeypatch):
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        calls = {"n": 0}

        def always_locked():
            calls["n"] += 1
            err = PermissionError("access denied")
            err.winerror = 5
            raise err

        with pytest.raises(PermissionError):
            mod._retry_fs(always_locked)
        assert calls["n"] == mod._FS_RETRY_ATTEMPTS

    def test_write_agent_cache_retries_replace_on_transient_lock_then_succeeds(self, tmp_path, monkeypatch):
        """write_agent_cache must retry a transient WinError-5/32 on the
        final atomic ``Path.replace`` and end up with the cache correctly
        written, instead of letting the first transient failure propagate.
        """
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        cache_path = tmp_path / "prefs.json"
        real_replace = Path.replace
        calls = {"n": 0}

        def flaky_replace(self, target):
            calls["n"] += 1
            if calls["n"] < 3:
                err = PermissionError("access denied")
                err.winerror = 5
                raise err
            return real_replace(self, target)

        monkeypatch.setattr(Path, "replace", flaky_replace)

        mod.write_agent_cache(cache_path, "opencode")

        assert calls["n"] == 3  # retried twice, succeeded on the 3rd
        assert mod.read_agent_cache(cache_path) == "opencode"

    def test_write_agent_cache_raises_after_retry_budget_exhausted(self, tmp_path, monkeypatch):
        """When the lock never clears, write_agent_cache still raises (the
        retry only absorbs *transient* failures; resolve_agent is the layer
        that makes persistence best-effort).
        """
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        cache_path = tmp_path / "prefs.json"

        def always_locked_replace(self, target):
            err = PermissionError("access denied")
            err.winerror = 5
            raise err

        monkeypatch.setattr(Path, "replace", always_locked_replace)

        with pytest.raises(PermissionError):
            mod.write_agent_cache(cache_path, "opencode")


# ---------------------------------------------------------------------------
# 8h3. resolve_agent: best-effort persistence (issue #50 FIX-3)
# ---------------------------------------------------------------------------

class TestResolveAgentBestEffortPersistence:
    """A persistent cache-write failure must not crash agent resolution —
    the run's actual work matters more than saving a preference file.
    """

    def test_resolve_agent_survives_persistent_write_failure(self, tmp_path, monkeypatch, capsys):
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        cache_path = tmp_path / "prefs.json"

        def always_locked_replace(self, target):
            err = PermissionError("access denied")
            err.winerror = 5
            raise err

        monkeypatch.setattr(Path, "replace", always_locked_replace)

        agent, source = mod.resolve_agent("opencode", cache_path)

        assert agent == "opencode"
        assert source == "flag"
        # a brief warning must be surfaced, but resolve_agent must not raise
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()

    def test_resolve_agent_normal_write_still_persists(self, tmp_path):
        """Non-flaky path: the cache write still actually happens (no
        regression from the best-effort wrapping)."""
        mod = load_module()
        cache_path = tmp_path / "prefs.json"
        agent, source = mod.resolve_agent("codex", cache_path)
        assert agent == "codex"
        assert source == "flag"
        assert mod.read_agent_cache(cache_path) == "codex"

    def test_resolve_agent_does_not_crash_pipeline_caller_on_write_failure(self, tmp_path, monkeypatch):
        """Simulates the real CLI call site: even when persistence is
        impossible, resolve_agent's return value is still usable to drive
        run_pipeline (the actual E2E work must proceed)."""
        mod = load_module()
        monkeypatch.setattr(mod.sys, "platform", "win32")
        monkeypatch.setattr(mod.time, "sleep", lambda _s: None)

        cache_path = tmp_path / "prefs.json"

        def always_locked_replace(self, target):
            err = OSError("sharing violation")
            err.winerror = 32
            raise err

        monkeypatch.setattr(Path, "replace", always_locked_replace)

        agent, source = mod.resolve_agent("opencode", cache_path)
        adapter = mod.get_adapter(agent)  # must not raise — agent is still usable
        assert adapter.name == "opencode"
        assert source == "flag"


# ---------------------------------------------------------------------------
# 8i. CLI: --agent default + --model + --agent caching behavior
# ---------------------------------------------------------------------------

class TestCliDefaults:
    def _make_md(self, tmp_path):
        md_file = tmp_path / "cases.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")
        return md_file

    def _fake_deploy(self):
        from types import SimpleNamespace

        def deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        return deploy

    def _fake_runner(self, mod, seen=None):
        def runner(prompt, workdir, timeout_s, sandbox, model=None):
            if seen is not None:
                seen["model"] = model
            return mod.RunResult(
                exit_code=0, timed_out=False,
                stdout='BLACKBOX_RESULT {"configured": true, "validate_status": "ok", "notes": ""}',
                stderr="", elapsed_s=1.0,
            )
        return runner

    def test_no_agent_flag_empty_cache_resolves_to_opencode(self, tmp_path):
        """With no --agent and no cache, main() runs opencode (the default)."""
        import io, contextlib
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]
        md_file = self._make_md(tmp_path)
        seen_agent = {}

        def fake_run_pipeline(**kwargs):
            seen_agent["agent"] = kwargs.get("agent") or kwargs.get("case") and "unknown"
            return {
                "case": "RTD-MEX-MCU-001", "scenario": "x", "agent": kwargs.get("agent", "?"),
                "sandbox": "workspace-write", "workdir": str(tmp_path),
                "project_dir": str(tmp_path), "mex_path": None,
                "elapsed_s": 1.0, "timed_out": False, "exit_code": 0,
                "blackbox_result": None, "session_id": None, "session_path": None,
                "kpi": None, "log_path": str(tmp_path / "log.txt"),
                "agent_source": "default", "model": None,
            }

        # Use an empty cache path (doesn't exist yet)
        cache_path = tmp_path / ".agent-state" / "e2e-preferences.json"

        # Use tmp_path as repo_root so the cache (.agent-state/) is isolated
        # from the real repo's cache (which may have a different default_agent).
        isolated_repo_root = tmp_path / "isolated_repo"
        isolated_repo_root.mkdir()

        # Capture the real parse_case before patching to avoid recursive mock calls
        real_parse_case = mod.parse_case

        with patch.object(mod, "_default_deploy", self._fake_deploy()), \
             patch.object(mod, "run_pipeline", side_effect=lambda **kw: fake_run_pipeline(**kw)), \
             patch.object(mod, "parse_case", side_effect=lambda p, cid: real_parse_case(md_file, cid)), \
             patch.object(mod, "max_kpi_minutes", side_effect=lambda p: 3):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                mod.main([
                    "--case", "RTD-MEX-MCU-001",
                    "--temp-base", str(tmp_path),
                    "--repo-root", str(isolated_repo_root),  # isolated cache
                ])

        # Default is opencode; the summary printed must say agent=opencode
        output = buf.getvalue()
        data = json.loads(output)
        assert data.get("agent") == "opencode"

    def test_summary_includes_agent_source(self, tmp_path):
        """run_pipeline summary must include 'agent_source' key."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox, model=None):
            return mod.RunResult(exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.0)

        case = mod.Case(
            id="RTD-MEX-MCU-001", scenario="Modify MCU clock", prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344", kpi_minutes=2,
        )
        summary = mod.run_pipeline(
            case=case, agent="opencode", sandbox="workspace-write", timeout_s=60,
            repo_root=repo_root, temp_base=tmp_path,
            deploy_fn=fake_deploy, runner_fn=fake_runner,
            agent_source="default",
        )
        assert "agent_source" in summary
        assert summary["agent_source"] == "default"

    def test_summary_includes_model(self, tmp_path):
        """run_pipeline summary must include 'model' key."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        from types import SimpleNamespace

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            skill_dir = workdir_arg / ".agents" / "skills" / "autombd-rtd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text("---\nname: autombd-rtd\n---\n", encoding="utf-8")
            return (SimpleNamespace(agent="codex", destination=skill_dir),)

        def fake_runner(prompt, workdir, timeout_s, sandbox, model=None):
            return mod.RunResult(exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.0)

        case = mod.Case(
            id="RTD-MEX-MCU-001", scenario="Modify MCU clock", prompt="修改MCU配置",
            fixture="tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344", kpi_minutes=2,
        )
        summary = mod.run_pipeline(
            case=case, agent="opencode", sandbox="workspace-write", timeout_s=60,
            repo_root=repo_root, temp_base=tmp_path,
            deploy_fn=fake_deploy, runner_fn=fake_runner,
            model="deepseek/deepseek-chat",
        )
        assert "model" in summary
        assert summary["model"] == "deepseek/deepseek-chat"
