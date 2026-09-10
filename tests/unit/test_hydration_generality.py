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
# File:        test_hydration_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Derived hydration generality tests with real Git and discipline.
# =================================================================================

from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

from test_workflow_environment_generality import ROOT, digest, env, git

INIT = ROOT / "agent-discipline/skills/initialize-agent-discipline/scripts"
sys.path.insert(0, str(INIT))


def hydration():
    assert (INIT / "init_agent_env_hydrate.py").is_file(), "derived hydration entrypoint is absent"
    return importlib.import_module("init_agent_env_hydrate")


@pytest.fixture
def initialized(tmp_path):
    source = tmp_path / "s"
    source.mkdir()
    # Minimal real discipline fixture exercises existing deterministic rendering,
    # not a mock of hydration or a copy of the owner acceptance suite.
    role = source / "agent-discipline/subagents"
    role.mkdir(parents=True)
    (role / "scout.md").write_bytes(b"---\nname: scout\ndescription: Read sources\ntools: Read, Bash\nmodel: inherit\n---\n\nInspect sources.\n")
    skill = source / "agent-discipline/skills/public-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_bytes(b"---\nname: public-skill\n---\nUse public sources.\n")
    external = tmp_path / "external/extra-skill"
    external.mkdir(parents=True)
    (external / "SKILL.md").write_bytes(b"---\nname: extra-skill\n---\nExtra public skill.\n")
    s32 = tmp_path / "vendor/S32"
    (s32 / "eclipse").mkdir(parents=True)
    rtd = tmp_path / "vendor/RTD"
    (rtd / "Family_TS_T_variant").mkdir(parents=True)
    (source / ".gitignore").write_bytes(b".agent-state/\n.agents/\n.claude/\n.codex/\n.opencode/\n")
    git(source, "init", "-b", "foundation")
    git(source, "config", "user.name", "Generality")
    git(source, "config", "user.email", "generality@example.invalid")
    git(source, "config", "core.autocrlf", "true")
    git(source, "add", ".")
    git(source, "commit", "-m", "canonical discipline")
    head = git(source, "rev-parse", "HEAD")
    config = dict(version=2, platforms=["claude", "codex", "opencode"], mode="reset",
                  reset_confirmed=True, s32ds_path=str(s32), rtd_path=str(rtd),
                  additional_skill_workflows=["local"],
                  local_skill_import=dict(roots=[str(external.parent)], selected=[
                      dict(name="extra-skill", source=str(external))]))
    deploy = importlib.import_module("init_agent_env_deploy")
    deploy.deploy(source, config)
    input_path = source / ".agent-state/init-input.json"
    input_path.write_bytes((json.dumps(config) + "\n").encode())
    return source, input_path, head, external


def capture(state):
    source, input_path, head, external = state
    return hydration().capture_initialization(source, input_path,
        expected_input_sha256=hashlib.sha256(input_path.read_bytes()).hexdigest())


def target_for(tmp_path, state):
    source, _, head, _ = state
    target = tmp_path / "derived/t"
    target.parent.mkdir()
    git(source, "worktree", "add", "-b", "derived", str(target), head)
    return target


def tree(path):
    # Inspect only this target's actual paths; links are recorded, never followed.
    result = {}
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in (*dirs, *files):
            item = Path(directory) / name
            if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
                result[item.relative_to(path).as_posix()] = ("link", str(item.resolve()))
            elif item.is_file():
                result[item.relative_to(path).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return result


def run_hydrate(tmp_path, state, snap, target, platforms=("codex",)):
    return hydration().hydrate_checkout(state[0], target, initialization=snap,
        expected_initialization_sha256=digest(snap), allowed_target_base=tmp_path / "derived",
        platforms=platforms, expected_target_head=state[2])


def test_hydration_reuses_only_selected_platform_and_target_local_skill(tmp_path, initialized):
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    result = run_hydrate(tmp_path, initialized, snapshot, target)
    assert result["status"] == "HYDRATED"
    assert result["platforms"] == ["codex"] and result["changed_paths"]
    source_skill = initialized[0] / "agent-discipline/skills/public-skill/SKILL.md"
    target_skill = target / "agent-discipline/skills/public-skill/SKILL.md"
    assert source_skill.read_bytes() != target_skill.read_bytes()
    assert target_skill.read_bytes().replace(b"\r\n", b"\n") == source_skill.read_bytes()
    generated, _ = importlib.import_module("init_agent_env_deploy")._render_outputs(target, ("codex",))
    assert all(path.read_bytes() == content.encode() for path, content in generated.items())
    assert (target / ".codex/agents/scout.toml").is_file()
    assert not (target / ".claude").exists() and not (target / ".opencode").exists()
    assert (target / ".agents/skills/public-skill").resolve() == target / "agent-discipline/skills/public-skill"
    assert (target / ".agents/skills/extra-skill").resolve() == initialized[3]
    first = tree(target)
    repeated = run_hydrate(tmp_path, initialized, snapshot, target)
    assert repeated["changed_paths"] == [] and tree(target) == first


@pytest.mark.parametrize("damage", ["source-role", "source-input", "source-skill", "source-eol", "external-skill", "external-eol", "source-cache", "target-skill"])
def test_hydration_rejects_drift_without_partial_target_writes(tmp_path, initialized, damage):
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    source, input_path, _, external = initialized
    locations = {
        "source-role": source / ".codex/agents/scout.toml",
        "source-input": input_path,
        "source-skill": source / "agent-discipline/skills/public-skill/SKILL.md",
        "source-eol": source / "agent-discipline/skills/public-skill/SKILL.md",
        "external-skill": external / "SKILL.md",
        "external-eol": external / "SKILL.md",
        "source-cache": source / ".agent-state/external-dependencies.json",
        "target-skill": target / "agent-discipline/skills/public-skill/SKILL.md",
    }
    raw = locations[damage].read_bytes()
    locations[damage].write_bytes(raw.replace(b"\n", b"\r\n") if damage.endswith("-eol") else raw + b"\nchanged")
    before = tree(target)
    with pytest.raises(env().EnvironmentError):
        run_hydrate(tmp_path, initialized, snapshot, target)
    assert tree(target) == before


def test_hydration_rejects_unapproved_platform_and_wrong_digest(tmp_path, initialized):
    source, input_path, head, external = initialized
    config = json.loads(input_path.read_bytes())
    config["platforms"] = ["codex"]
    input_path.write_bytes((json.dumps(config) + "\n").encode())
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    before = tree(target)
    with pytest.raises(env().EnvironmentError) as error:
        run_hydrate(tmp_path, initialized, snapshot, target, ("claude",))
    assert error.value.code == "PLATFORM_NOT_APPROVED"
    with pytest.raises(env().EnvironmentError):
        hydration().hydrate_checkout(source, target, initialization=snapshot,
            expected_initialization_sha256="1"*64, allowed_target_base=target.parent,
            platforms=["codex"], expected_target_head=head)
    assert tree(target) == before


def test_hydration_rejects_ordinary_clone_without_source_lineage(tmp_path, initialized):
    snapshot = capture(initialized)
    target = tmp_path / "derived/ordinary"
    target.mkdir(parents=True)
    git(target, "init", "-b", "new")
    git(target, "config", "user.name", "Generality")
    git(target, "config", "user.email", "generality@example.invalid")
    (target / "ordinary.txt").write_bytes(b"ordinary clone")
    git(target, "add", ".")
    git(target, "commit", "-m", "not derived")
    before = tree(target)
    with pytest.raises(env().EnvironmentError):
        hydration().hydrate_checkout(initialized[0], target, initialization=snapshot,
            expected_initialization_sha256=digest(snapshot), allowed_target_base=target.parent,
            platforms=["codex"], expected_target_head=git(target, "rev-parse", "HEAD"))
    assert tree(target) == before


def test_hydration_escaping_managed_parent_is_rejected_before_mutation(tmp_path, initialized):
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    outside = tmp_path / "outside"
    outside.mkdir()
    (target / ".codex").symlink_to(outside, target_is_directory=True)
    before = tree(target)
    with pytest.raises(env().EnvironmentError):
        run_hydrate(tmp_path, initialized, snapshot, target)
    assert tree(target) == before and list(outside.iterdir()) == []


def test_capture_requires_real_deployed_bytes_and_exact_input(tmp_path, initialized):
    source, input_path, _, _ = initialized
    with pytest.raises(env().EnvironmentError):
        hydration().capture_initialization(source, input_path, expected_input_sha256="0"*64)
    (source / ".codex/agents/scout.toml").unlink()
    with pytest.raises(env().EnvironmentError) as error:
        capture(initialized)
    assert error.value.code == "INITIALIZATION_UNAVAILABLE"


def test_capture_never_refreshes_or_writes_source_index(tmp_path, initialized):
    source = initialized[0]
    tracked = source / ".gitignore"
    stat = tracked.stat()
    os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    before = tree(source)
    first = capture(initialized)
    assert tree(source) == before
    assert capture(initialized) == first


def test_conflicting_target_agent_file_blocks_before_skill_or_cache_write(tmp_path, initialized):
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    conflict = target / ".codex/agents/scout.toml"
    conflict.parent.mkdir(parents=True)
    conflict.write_bytes(b"existing local output")
    before = tree(target)
    with pytest.raises(env().EnvironmentError):
        run_hydrate(tmp_path, initialized, snapshot, target)
    assert tree(target) == before


def test_hydration_cli_returns_json_and_leaves_input_untouched(tmp_path, initialized):
    import subprocess
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    snapfile = tmp_path / "initialization.json"
    snapfile.write_bytes((json.dumps(snapshot) + "\n").encode())
    before = snapfile.read_bytes()
    result = subprocess.run([sys.executable, str(INIT / "init_agent_env_hydrate.py"), "hydrate",
        "--source-root", str(initialized[0]), "--target-root", str(target),
        "--initialization", str(snapfile), "--expected-initialization-sha256", digest(snapshot),
        "--allowed-target-base", str(target.parent), "--platform", "codex",
        "--expected-target-head", initialized[2]], capture_output=True)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["status"] == "HYDRATED"
    assert snapfile.read_bytes() == before


def test_hydration_cli_distinguishes_digest_rejection_from_malformed_input(tmp_path, initialized):
    import subprocess
    snapshot = capture(initialized)
    target = target_for(tmp_path, initialized)
    snapfile = tmp_path / "initialization.json"
    snapfile.write_bytes((json.dumps(snapshot) + "\n").encode())
    before = tree(target)
    argv = [sys.executable, str(INIT / "init_agent_env_hydrate.py"), "hydrate",
        "--source-root", str(initialized[0]), "--target-root", str(target),
        "--initialization", str(snapfile), "--expected-initialization-sha256", "9"*64,
        "--allowed-target-base", str(target.parent), "--platform", "codex",
        "--expected-target-head", initialized[2]]
    rejection = subprocess.run(argv, capture_output=True)
    assert rejection.returncode == 1
    assert json.loads(rejection.stdout)["code"] == "INVALID_INPUT"
    assert tree(target) == before


def test_capture_cli_unreadable_input_is_exit_two(tmp_path, initialized):
    import subprocess
    result = subprocess.run([sys.executable, str(INIT / "init_agent_env_hydrate.py"), "capture",
        "--source-root", str(initialized[0]), "--input", str(tmp_path / "missing.json"),
        "--expected-input-sha256", "4"*64], capture_output=True)
    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "INVALID_INPUT"
