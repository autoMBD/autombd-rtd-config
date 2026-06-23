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
# File:        test_deploy_agent_env.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-24
# Version:     0.1.0
# Description: Unit tests for deterministic Agent environment deployment.
# =================================================================================

import json
from pathlib import Path
import tomllib

import pytest

from tools.deploy_agent_env import (
    AgentDeploymentError,
    AgentTemplateError,
    deploy,
    ensure_directory_link,
    main,
    parse_claude_agent,
    render_claude_agent,
    render_codex_agent,
    render_opencode_agent,
    skill_target_roots,
)
from tools.init_agent_env import validate_input


SOURCE = (
    "---\n"
    "name: reviewer\n"
    "description: Reviews changes without editing.\n"
    "tools: Read, Grep, Glob, Bash\n"
    "model: opus\n"
    "---\n\n"
    "Review correctness and report findings.\n"
)


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    skill = repo / "agent-discipline/skills/example"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: example\ndescription: Example skill.\n---\n",
        encoding="utf-8",
    )
    agents = repo / "agent-discipline/subagents"
    agents.mkdir(parents=True)
    (agents / "reviewer.md").write_text(SOURCE, encoding="utf-8")
    return repo


def _config(*platforms: str, mode: str = "update") -> dict[str, object]:
    return {
        "version": 1,
        "platforms": list(platforms),
        "mode": mode,
        "reset_confirmed": mode == "reset",
        "s32ds_path": "",
        "rtd_path": "",
    }


def test_collector_requires_verified_s32ds_and_rtd_paths(tmp_path):
    config = _config("codex")
    errors = validate_input(config)
    assert "'s32ds_path' must be a verified S32DS installation root" in errors
    assert "'rtd_path' must be a verified RTD package root" in errors

    s32ds = tmp_path / "S32DS.3.6.7"
    (s32ds / "eclipse").mkdir(parents=True)
    rtd = tmp_path / "RTD"
    (rtd / "Platform_TS_T40D34M10I0R0").mkdir(parents=True)
    config["s32ds_path"] = str(s32ds)
    config["rtd_path"] = str(rtd)

    assert validate_input(config) == []


def test_renderers_preserve_body_and_use_native_schema():
    template = parse_claude_agent(SOURCE)
    assert render_claude_agent(template) == SOURCE

    opencode = render_opencode_agent(template)
    frontmatter = opencode.split("---", 2)[1]
    assert "name:" not in frontmatter
    assert "mode: subagent" in frontmatter
    assert '"*": deny' in frontmatter
    assert "read: allow" in frontmatter
    assert "edit: allow" not in frontmatter
    assert "$schema" not in frontmatter
    assert opencode.endswith("Review correctness and report findings.\n")

    codex = render_codex_agent(template)
    parsed = tomllib.loads(codex)
    assert parsed == {
        "name": "reviewer",
        "description": "Reviews changes without editing.",
        "developer_instructions": "Review correctness and report findings.\n",
        "sandbox_mode": "read-only",
    }


def test_writable_claude_tools_map_to_native_platform_permissions():
    source = SOURCE.replace(
        "Read, Grep, Glob, Bash", "Read, Edit, Write, Bash, Grep, Glob"
    )
    template = parse_claude_agent(source)
    assert "edit: allow" in render_opencode_agent(template)
    assert tomllib.loads(render_codex_agent(template))["sandbox_mode"] == (
        "workspace-write"
    )


def test_unknown_claude_tool_is_rejected():
    source = SOURCE.replace("Read, Grep, Glob, Bash", "Read, UnknownTool")
    with pytest.raises(AgentTemplateError, match="UnknownTool"):
        render_opencode_agent(parse_claude_agent(source))


def test_parser_rejects_unsupported_or_duplicate_frontmatter():
    with pytest.raises(AgentTemplateError, match="unsupported"):
        parse_claude_agent(SOURCE.replace("model: opus", "color: red"))
    with pytest.raises(AgentTemplateError, match="duplicate"):
        parse_claude_agent(SOURCE.replace("model: opus", "model: opus\nmodel: sonnet"))


@pytest.mark.parametrize(
    ("platforms", "expected"),
    [
        (("claude",), (Path(".claude/skills"),)),
        (("codex",), (Path(".agents/skills"),)),
        (("opencode",), (Path(".agents/skills"),)),
        (("claude", "opencode"), (Path(".claude/skills"),)),
        (
            ("claude", "opencode", "codex"),
            (Path(".claude/skills"), Path(".agents/skills")),
        ),
    ],
)
def test_skill_target_roots(platforms, expected):
    assert skill_target_roots(platforms) == expected


def test_all_platform_deployment_links_skills_and_generates_native_agents(tmp_path):
    repo = _fixture_repo(tmp_path)
    report = deploy(repo, _config("claude", "opencode", "codex"))

    source_skill = repo / "agent-discipline/skills/example/SKILL.md"
    assert (repo / ".claude/skills/example/SKILL.md").samefile(source_skill)
    assert (repo / ".agents/skills/example/SKILL.md").samefile(source_skill)
    assert not (repo / ".opencode/skills").exists()
    assert (repo / ".claude/agents/reviewer.md").read_text("utf-8") == SOURCE
    assert "mode: subagent" in (
        repo / ".opencode/agents/reviewer.md"
    ).read_text("utf-8")
    assert tomllib.loads(
        (repo / ".codex/agents/reviewer.toml").read_text("utf-8")
    )["name"] == "reviewer"
    assert report.skill_links == 2
    assert report.agent_files_written == 3

    second = deploy(repo, _config("claude", "opencode", "codex"))
    assert second.agent_files_written == 0
    assert second.agent_files_unchanged == 3


def test_skill_destination_must_be_a_link_to_the_canonical_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("skill", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()

    with pytest.raises(AgentDeploymentError, match="ordinary"):
        ensure_directory_link(source, destination)


def test_legacy_cleanup_is_narrow_and_preserves_unrelated_files(tmp_path):
    repo = _fixture_repo(tmp_path)
    obsolete_agents = repo / ".agents/agents"
    obsolete_agents.mkdir(parents=True)
    (obsolete_agents / "reviewer.md").write_text("obsolete", encoding="utf-8")
    (obsolete_agents / "personal.md").write_text("keep", encoding="utf-8")
    obsolete_skill = repo / ".opencode/skills/example"
    ensure_directory_link(repo / "agent-discipline/skills/example", obsolete_skill)
    unrelated_skill = repo / ".opencode/skills/personal"
    unrelated_skill.mkdir(parents=True)
    (unrelated_skill / "SKILL.md").write_text("keep", encoding="utf-8")

    deploy(repo, _config("opencode", "codex"))

    assert not (obsolete_agents / "reviewer.md").exists()
    assert (obsolete_agents / "personal.md").is_file()
    assert not obsolete_skill.exists()
    assert (unrelated_skill / "SKILL.md").is_file()


def test_cache_update_preserves_unrelated_entries(tmp_path):
    repo = _fixture_repo(tmp_path)
    s32ds = tmp_path / "S32DS"
    rtd = tmp_path / "RTD"
    s32ds.mkdir()
    rtd.mkdir()
    state = repo / ".agent-state"
    state.mkdir()
    (state / "external-dependencies.json").write_text(
        json.dumps({
            "version": 1,
            "updated_at": "old",
            "items": {"tool.existing": {"status": "available"}},
        }),
        encoding="utf-8",
    )
    config = _config("claude")
    config["s32ds_path"] = str(s32ds)
    config["rtd_path"] = str(rtd)

    deploy(repo, config)

    cache = json.loads(
        (state / "external-dependencies.json").read_text(encoding="utf-8")
    )
    assert "tool.existing" in cache["items"]
    assert cache["items"]["env.s32ds"]["location"] == s32ds.as_posix()
    assert cache["items"]["env.rtd"]["location"] == rtd.as_posix()


def test_unconfirmed_reset_is_rejected_before_mutation(tmp_path):
    repo = _fixture_repo(tmp_path)
    marker = repo / ".claude/agents/personal.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("keep", encoding="utf-8")
    config = _config("claude", mode="reset")
    config["reset_confirmed"] = False

    with pytest.raises(AgentDeploymentError, match="reset_confirmed"):
        deploy(repo, config)
    assert marker.is_file()


def test_local_additional_skills_are_linked_not_copied(tmp_path):
    repo = _fixture_repo(tmp_path)
    imported = tmp_path / "imported/release"
    imported.mkdir(parents=True)
    (imported / "SKILL.md").write_text(
        "---\nname: release\ndescription: Release helper.\n---\n",
        encoding="utf-8",
    )
    config = _config("claude", "opencode")
    config["import_skills"] = {"type": "local", "path": str(imported.parent)}

    deploy(repo, config)

    assert (repo / ".claude/skills/release/SKILL.md").samefile(
        imported / "SKILL.md"
    )
    assert not (repo / ".opencode/skills").exists()


def test_online_skill_import_requires_explicit_external_installation(tmp_path):
    repo = _fixture_repo(tmp_path)
    config = _config("codex")
    config["import_skills"] = {
        "type": "online",
        "url": "https://example.invalid/skills",
    }

    with pytest.raises(AgentDeploymentError, match="online Skill import"):
        deploy(repo, config)


def test_cli_loads_collector_json_and_deploys_native_outputs(tmp_path):
    repo = _fixture_repo(tmp_path)
    s32ds = tmp_path / "S32DS.3.6.7"
    (s32ds / "eclipse").mkdir(parents=True)
    rtd = tmp_path / "RTD"
    (rtd / "Platform_TS_T40D34M10I0R0").mkdir(parents=True)
    config = _config("claude", "opencode", "codex")
    config["s32ds_path"] = str(s32ds)
    config["rtd_path"] = str(rtd)
    input_path = repo / ".agent-state/init-input.json"
    input_path.parent.mkdir()
    input_path.write_text(
        json.dumps(config),
        encoding="utf-8",
    )

    assert main(["--input", str(input_path), "--repo-root", str(repo)]) == 0
    assert (repo / ".claude/agents/reviewer.md").is_file()
    assert (repo / ".opencode/agents/reviewer.md").is_file()
    assert (repo / ".codex/agents/reviewer.toml").is_file()


def test_deployment_refuses_a_managed_parent_linked_outside_repo(tmp_path):
    repo = _fixture_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("marker", encoding="utf-8")
    link = repo / ".codex"
    ensure_directory_link(outside, link)

    try:
        with pytest.raises(AgentDeploymentError, match="outside repository"):
            deploy(repo, _config("codex"))
        assert not (outside / "agents/reviewer.toml").exists()
    finally:
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            link.rmdir()


def test_invalid_generated_target_fails_before_any_skill_link_is_created(tmp_path):
    repo = _fixture_repo(tmp_path)
    invalid = repo / ".codex/agents/reviewer.toml"
    invalid.mkdir(parents=True)

    with pytest.raises(AgentDeploymentError, match="regular file"):
        deploy(repo, _config("codex"))
    assert not (repo / ".agents/skills").exists()


def test_invalid_dependency_or_cache_fails_before_any_deployment(tmp_path):
    repo = _fixture_repo(tmp_path)
    config = _config("codex")
    config["s32ds_path"] = str(tmp_path / "missing-s32ds")

    with pytest.raises(AgentDeploymentError, match="usable directory"):
        deploy(repo, config)
    assert not (repo / ".agents/skills").exists()

    state = repo / ".agent-state"
    state.mkdir()
    (state / "external-dependencies.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(AgentDeploymentError, match="invalid dependency cache"):
        deploy(repo, _config("codex"))
    assert not (repo / ".agents/skills").exists()
