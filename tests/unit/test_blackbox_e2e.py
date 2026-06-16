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
# Version:     0.1.0
# Description: Unit tests for the black-box isolated E2E harness that drives a
#              third-party agent CLI (Codex, others) over the released autombd-rtd
#              skill. Tests cover the runner registry, case parsing, prompt
#              building, subprocess wiring, and pipeline integration — no real
#              codex/S32DS invocation in any test.
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
        the hardcoded '.agents/skills/<SKILL_NAME>' path."""
        mod = load_module()
        repo_root = Path(__file__).resolve().parents[2]

        # Custom destination — matches claude layout, not codex layout.
        custom_skill_dir = tmp_path / "workdir" / ".claude" / "skills" / "autombd-rtd"
        custom_skill_dir.mkdir(parents=True, exist_ok=True)
        (custom_skill_dir / "SKILL.md").write_text(
            "---\nname: autombd-rtd\nversion: 0.1.0\n---\n", encoding="utf-8"
        )
        (custom_skill_dir / "__main__.py").write_text("# stub\n", encoding="utf-8")

        # A simple DeployResult-like with .agent and .destination attributes.
        from types import SimpleNamespace
        fake_result = SimpleNamespace(agent="claude", destination=custom_skill_dir)

        def fake_deploy(repo_root_arg, workdir_arg, agents):
            # Copy the pre-built skill dir into the workdir so the path exists.
            target = workdir_arg / ".claude" / "skills" / "autombd-rtd"
            if not target.exists():
                import shutil
                shutil.copytree(str(custom_skill_dir), str(target))
            return (SimpleNamespace(agent="claude", destination=target),)

        seen_skill_md = {}

        def fake_runner(prompt, workdir, timeout_s, sandbox):
            # The prompt contains the skill_md_path — capture it.
            seen_skill_md["prompt"] = prompt
            return mod.RunResult(
                exit_code=0, timed_out=False, stdout="", stderr="", elapsed_s=0.1
            )

        mod.run_pipeline(
            case=self._make_fake_case(mod),
            agent="claude",
            sandbox="workspace-write",
            timeout_s=60,
            repo_root=repo_root,
            temp_base=tmp_path,
            deploy_fn=fake_deploy,
            runner_fn=fake_runner,
            keep=True,
        )

        prompt = seen_skill_md["prompt"]
        # The prompt must reference the claude-layout skill dir, not the codex one.
        assert ".claude" + "/" in prompt or ".claude\\" in prompt, (
            f"Expected '.claude' skill path in prompt, got:\n{prompt[:400]}"
        )
        assert ".agents" not in prompt or ".claude" in prompt, (
            "run_pipeline should use DeployResult.destination (claude path), "
            f"not the hardcoded codex path; prompt snippet: {prompt[:400]}"
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
