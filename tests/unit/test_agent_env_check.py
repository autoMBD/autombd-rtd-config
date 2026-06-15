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
# File:        test_agent_env_check.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-15
# Version:     0.1.0
# Description: Unit tests for the agent environment verification cache.
# =================================================================================

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[2] / "tools" / "agent_env_check.py"
    spec = importlib.util.spec_from_file_location("agent_env_check", module_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agent_env_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_default_state_file_is_agent_local_and_ignored():
    mod = load_module()

    state_file = mod.default_state_file(Path("repo"))

    assert state_file == Path("repo") / ".agent-state" / "environment-verification.json"


def test_cached_passed_dependency_is_reused_without_probe(tmp_path):
    mod = load_module()
    state_file = tmp_path / ".agent-state" / "environment-verification.json"
    state_file.parent.mkdir()
    state_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dependencies": {
                    "github_cli": {
                        "status": "passed",
                        "checked_at": "2026-06-15T00:00:00Z",
                        "summary": "gh authenticated",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def probe_should_not_run():
        calls.append("called")
        return mod.CheckResult("github_cli", "blocked", "unexpected", "")

    dep = mod.Dependency(
        key="github_cli",
        label="GitHub CLI",
        required=True,
        interactive_auth=True,
        prepare="Run gh auth login -h github.com.",
        probe=probe_should_not_run,
    )

    report = mod.verify_dependencies(
        repo_root=tmp_path,
        dependencies=(dep,),
        state_file=state_file,
        refresh=False,
        now=lambda: "2026-06-15T01:00:00Z",
    )

    assert calls == []
    assert report["dependencies"]["github_cli"]["source"] == "cache"
    assert report["summary"]["passed"] == 1


def test_refresh_reprobes_and_updates_state_file(tmp_path):
    mod = load_module()
    state_file = tmp_path / ".agent-state" / "environment-verification.json"
    calls = []

    def probe():
        calls.append("called")
        return mod.CheckResult("python", "passed", "Python 3.11", "")

    dep = mod.Dependency(
        key="python",
        label="Python",
        required=True,
        interactive_auth=False,
        prepare="Install Python 3.11 or newer.",
        probe=probe,
    )

    report = mod.verify_dependencies(
        repo_root=tmp_path,
        dependencies=(dep,),
        state_file=state_file,
        refresh=True,
        now=lambda: "2026-06-15T01:00:00Z",
    )

    stored = json.loads(state_file.read_text(encoding="utf-8"))
    assert calls == ["called"]
    assert report["dependencies"]["python"]["source"] == "probe"
    assert stored["dependencies"]["python"]["status"] == "passed"
    assert stored["dependencies"]["python"]["checked_at"] == "2026-06-15T01:00:00Z"


def test_blocked_dependency_records_prepare_instruction(tmp_path):
    mod = load_module()

    def probe():
        return mod.CheckResult("s32ds", "blocked", "S32DS root not found", "")

    dep = mod.Dependency(
        key="s32ds",
        label="S32 Design Studio",
        required=True,
        interactive_auth=False,
        prepare="Install S32DS with RTD 7.0.1, or set RTD_CONFIG_S32DS_ROOT.",
        probe=probe,
    )

    report = mod.verify_dependencies(
        repo_root=tmp_path,
        dependencies=(dep,),
        state_file=tmp_path / ".agent-state" / "environment-verification.json",
        refresh=False,
        now=lambda: "2026-06-15T01:00:00Z",
    )

    s32ds = report["dependencies"]["s32ds"]
    assert report["summary"]["blocked"] == 1
    assert s32ds["status"] == "blocked"
    assert "RTD_CONFIG_S32DS_ROOT" in s32ds["prepare"]


def test_main_emits_json_report_and_nonzero_when_required_blocked(tmp_path, capsys):
    mod = load_module()

    def probe():
        return mod.CheckResult("codex_cli", "blocked", "codex not found", "")

    dep = mod.Dependency(
        key="codex_cli",
        label="Codex CLI",
        required=True,
        interactive_auth=True,
        prepare="Install and authenticate Codex CLI.",
        probe=probe,
    )

    exit_code = mod.main(
        [
            "--repo-root",
            str(tmp_path),
            "--state-file",
            str(tmp_path / ".agent-state" / "environment-verification.json"),
            "--json",
        ],
        dependencies=(dep,),
        now=lambda: "2026-06-15T01:00:00Z",
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "blocked"
    assert payload["dependencies"]["codex_cli"]["prepare"] == "Install and authenticate Codex CLI."


def test_main_uses_cache_on_second_run(tmp_path, capsys):
    mod = load_module()
    state_file = tmp_path / ".agent-state" / "environment-verification.json"
    calls = []

    def probe():
        calls.append("called")
        return mod.CheckResult("git", "passed", "git available", "")

    dep = mod.Dependency(
        key="git",
        label="Git",
        required=True,
        interactive_auth=False,
        prepare="Install Git.",
        probe=probe,
    )

    first = mod.main(
        ["--repo-root", str(tmp_path), "--state-file", str(state_file), "--json"],
        dependencies=(dep,),
        now=lambda: "2026-06-15T01:00:00Z",
    )
    capsys.readouterr()
    second = mod.main(
        ["--repo-root", str(tmp_path), "--state-file", str(state_file), "--json"],
        dependencies=(dep,),
        now=lambda: "2026-06-15T01:01:00Z",
    )
    payload = json.loads(capsys.readouterr().out)

    assert first == 0
    assert second == 0
    assert calls == ["called"]
    assert payload["dependencies"]["git"]["source"] == "cache"


def test_codex_agent_uses_github_app_connector_not_github_cli(tmp_path):
    mod = load_module()

    deps = mod.build_dependencies(tmp_path, agent="codex")

    keys = {dep.key for dep in deps}
    assert "github_app_connector" in keys
    assert "github_cli" not in keys


def test_non_codex_agent_uses_github_cli_status_check(tmp_path):
    mod = load_module()

    deps = mod.build_dependencies(tmp_path, agent="claude")

    keys = {dep.key for dep in deps}
    assert "github_cli" in keys
    assert "github_app_connector" not in keys


def test_user_confirmation_satisfies_non_codex_github_cli_auth(tmp_path, capsys):
    mod = load_module()
    state_file = tmp_path / ".agent-state" / "environment-verification.json"
    calls = []

    def probe_should_not_run():
        calls.append("called")
        return mod.CheckResult("github_cli", "blocked", "unexpected", "")

    dep = mod.Dependency(
        key="github_cli",
        label="GitHub CLI",
        required=True,
        interactive_auth=True,
        prepare="Run gh auth status -h github.com.",
        probe=probe_should_not_run,
    )

    exit_code = mod.main(
        [
            "--repo-root",
            str(tmp_path),
            "--state-file",
            str(state_file),
            "--agent",
            "claude",
            "--confirm-github-cli-auth",
            "T哥 confirmed gh auth status passed in desktop PowerShell",
            "--json",
        ],
        dependencies=(dep,),
        now=lambda: "2026-06-16T01:00:00Z",
    )

    payload = json.loads(capsys.readouterr().out)
    stored = json.loads(state_file.read_text(encoding="utf-8"))
    github_cli = payload["dependencies"]["github_cli"]
    assert exit_code == 0
    assert calls == []
    assert github_cli["status"] == "passed"
    assert github_cli["source"] == "user_confirmation"
    assert "desktop PowerShell" in github_cli["detail"]
    assert stored["dependencies"]["github_cli"]["source"] == "user_confirmation"
