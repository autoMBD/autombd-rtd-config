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
# File:        test_workflow_actor_selection_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Contributor-aware black-box actor selection generality tests.
# =================================================================================

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("workflow_actor_generality", ROOT / "tools/blackbox_e2e.py")
BB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BB
SPEC.loader.exec_module(BB)


def actor():
    parameters = inspect.signature(BB.resolve_agent).parameters
    assert "current_platform" in parameters and "available_agents" in parameters, "contributor-aware selection interface is missing"
    return BB


@pytest.mark.parametrize("platform", ["codex", "claude", "opencode"])
def test_current_platform_overrides_previous_contributor_preference(tmp_path, platform):
    m = actor()
    cache = tmp_path / "preference.json"
    cache.write_text(json.dumps({"default_agent": "opencode" if platform != "opencode" else "codex"}))
    before = cache.read_bytes()
    assert m.resolve_agent(None, cache, current_platform=platform, available_agents=[platform]) == (platform, "current-platform")
    assert cache.read_bytes() == before


def test_explicit_available_actor_wins_and_persists(tmp_path):
    m = actor()
    cache = tmp_path / "preference.json"
    assert m.resolve_agent("claude", cache, current_platform="codex", available_agents=["codex", "claude"]) == ("claude", "flag")
    assert json.loads(cache.read_bytes())["default_agent"] == "claude"


def test_unknown_or_unavailable_context_never_uses_static_default(tmp_path, monkeypatch):
    m = actor()
    for name in ("RTD_CURRENT_PLATFORM", "CODEX_THREAD_ID", "CLAUDECODE", "OPENCODE"):
        monkeypatch.delenv(name, raising=False)
    cache = tmp_path / "preference.json"
    cache.write_text('{"default_agent":"opencode"}')
    with pytest.raises(ValueError):
        m.resolve_agent(None, cache, available_agents=["codex", "opencode"])
    with pytest.raises(ValueError):
        m.resolve_agent(None, cache, current_platform="codex", available_agents=["opencode"])
    assert m.resolve_agent(None, cache, available_agents=["claude"]) == ("claude", "available")


def test_cli_exposes_contributor_platform():
    m = actor()
    args = m.build_parser().parse_args(["--case", "arbitrary", "--current-platform", "claude"])
    assert args.current_platform == "claude"
    assert set(m.AGENT_ADAPTERS) >= {"codex", "claude", "opencode"}


def test_claude_adapter_is_noninteractive_and_keeps_existing_protocol(tmp_path, monkeypatch):
    m = actor()
    assert "claude" in m.AGENT_ADAPTERS, "Claude adapter is missing"
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps({
            "type": "result", "is_error": False,
            "result": 'BLACKBOX_RESULT {"status":"ok"}', "session_id": "new-session"}), "")
    monkeypatch.setattr(m.shutil, "which", lambda name: str(tmp_path / "claude.exe") if name == "claude" else None)
    monkeypatch.setattr(m.subprocess, "run", run)
    adapter = m.get_adapter("claude")
    result = adapter.run("public staged prompt", tmp_path, 7, "workspace-write", model="explicit-model")
    assert isinstance(result, m.RunResult)
    assert adapter.extract_result(result) == {"status": "ok"}
    argv, options = calls[0]
    assert "-p" in argv and "--no-session-persistence" in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert "--dangerously-skip-permissions" not in argv
    assert options["cwd"] == tmp_path and options["input"] == "public staged prompt"
    assert options["timeout"] == 7 and options.get("shell", False) is False
    assert adapter.compute_kpi(result) is None
