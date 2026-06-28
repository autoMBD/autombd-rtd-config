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
# File:        test_init_agent_env.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-25
# Version:     0.1.0
# Description: Unit tests for Agent environment GUI input and local Skill discovery.
# =================================================================================

import importlib.util
from pathlib import Path
import sys


SCRIPT_PATH = Path(
    "agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env_inputs.py"
)


def _load_init_module():
    spec = importlib.util.spec_from_file_location("init_agent_env_inputs", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


init_agent_env_inputs = _load_init_module()
LocalSkillSelectionModel = init_agent_env_inputs.LocalSkillSelectionModel
discover_local_skills = init_agent_env_inputs.discover_local_skills
run_cli = init_agent_env_inputs.run_cli
validate_input = init_agent_env_inputs.validate_input


def _skill(parent: Path, name: str, *, manifest_name: str | None = None) -> Path:
    source = parent / name
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\n"
        f"name: {manifest_name or name}\n"
        f"description: {name} helper.\n"
        "---\n",
        encoding="utf-8",
    )
    return source


def _valid_config(tmp_path: Path) -> dict[str, object]:
    s32ds = tmp_path / "S32DS.3.6.7"
    (s32ds / "eclipse").mkdir(parents=True)
    rtd = tmp_path / "RTD"
    (rtd / "Platform_TS_T40D34M10I0R0").mkdir(parents=True)
    return {
        "version": 2,
        "platforms": ["codex"],
        "mode": "update",
        "reset_confirmed": False,
        "s32ds_path": s32ds.as_posix(),
        "rtd_path": rtd.as_posix(),
        "additional_skill_workflows": ["skip"],
    }


def test_discovers_skills_across_multiple_roots_in_stable_order(tmp_path):
    root_a = tmp_path / "skills-a"
    root_b = tmp_path / "skills-b"
    skill_b = _skill(root_b / "nested", "skill-b")
    skill_a = _skill(root_a, "skill-a")

    result = discover_local_skills([root_b, root_a])

    assert [(item.name, item.source) for item in result.candidates] == [
        ("skill-a", skill_a.resolve()),
        ("skill-b", skill_b.resolve()),
    ]
    assert result.issues == ()


def test_overlapping_roots_deduplicate_the_same_skill_source(tmp_path):
    root = tmp_path / "skills"
    skill = _skill(root / "nested", "release-helper")

    result = discover_local_skills([root, root / "nested"])

    assert [(item.name, item.source) for item in result.candidates] == [
        ("release-helper", skill.resolve())
    ]
    assert result.issues == ()


def test_discovery_reports_invalid_manifest_and_duplicate_name_conflict(tmp_path):
    root_a = tmp_path / "skills-a"
    root_b = tmp_path / "skills-b"
    _skill(root_a, "bad-directory", manifest_name="different-name")
    _skill(root_a, "shared")
    _skill(root_b, "shared")

    result = discover_local_skills([root_a, root_b])

    assert result.candidates == ()
    messages = [issue.message for issue in result.issues]
    assert any("does not match directory" in message for message in messages)
    assert any("duplicate Skill name 'shared'" in message for message in messages)


def test_selection_model_preserves_remaining_selections_after_rescan(tmp_path):
    root_a = tmp_path / "skills-a"
    root_b = tmp_path / "skills-b"
    skill_a = _skill(root_a, "skill-a")
    _skill(root_b, "skill-b")
    model = LocalSkillSelectionModel()

    model.add_root(root_a)
    model.add_root(root_b)
    model.select_all()
    model.remove_root(root_b)

    assert model.roots == (root_a.resolve(),)
    assert model.selected_entries() == (
        {"name": "skill-a", "source": skill_a.resolve().as_posix()},
    )
    model.clear_all()
    assert model.selected_entries() == ()


def test_version_2_validates_selected_local_skills_and_optional_text(tmp_path):
    root = tmp_path / "skills"
    source = _skill(root, "skill-a")
    config = _valid_config(tmp_path)
    config.update(
        {
            "additional_skill_workflows": ["local", "online"],
            "local_skill_import": {
                "roots": [root.as_posix()],
                "selected": [
                    {"name": "skill-a", "source": source.as_posix()}
                ],
            },
            "online_skill_request": "Find and install a testing skill.",
            "supplemental_task": "Initialize project Agent formatting rules.",
        }
    )

    assert validate_input(config) == []


def test_version_2_rejects_empty_or_untrusted_local_selection(tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    outside = _skill(tmp_path / "outside", "skill-a")
    config = _valid_config(tmp_path)
    config["local_skill_import"] = {"roots": [root.as_posix()], "selected": []}
    assert any("at least one selected Skill" in error for error in validate_input(config))

    config["local_skill_import"] = {
        "roots": [root.as_posix()],
        "selected": [{"name": "skill-a", "source": outside.as_posix()}],
    }
    assert any("outside submitted roots" in error for error in validate_input(config))


def test_version_2_rejects_blank_optional_text_and_duplicate_names(tmp_path):
    root_a = tmp_path / "skills-a"
    root_b = tmp_path / "skills-b"
    source_a = _skill(root_a, "shared")
    source_b = _skill(root_b, "shared")
    config = _valid_config(tmp_path)
    config.update(
        {
            "local_skill_import": {
                "roots": [root_a.as_posix(), root_b.as_posix()],
                "selected": [
                    {"name": "shared", "source": source_a.as_posix()},
                    {"name": "shared", "source": source_b.as_posix()},
                ],
            },
            "online_skill_request": "   ",
            "supplemental_task": 42,
        }
    )

    errors = validate_input(config)
    assert any("duplicate selected Skill name" in error for error in errors)
    assert any("online_skill_request" in error for error in errors)
    assert any("supplemental_task" in error for error in errors)


def test_version_2_requires_an_explicit_additional_skill_choice(tmp_path):
    config = _valid_config(tmp_path)
    del config["additional_skill_workflows"]
    assert any(
        "additional_skill_workflows" in error for error in validate_input(config)
    )

    config["additional_skill_workflows"] = ["skip", "online"]
    config["online_skill_request"] = "Find a testing skill."
    assert any("Skip cannot be combined" in error for error in validate_input(config))


def test_gui_mode_switch_does_not_pack_before_an_unmanaged_widget():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "pack(fill=\"x\", before=" not in source


def test_gui_can_select_local_and_online_skill_workflows_together():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "self._local_import_var" in source
    assert "self._online_import_var" in source
    assert "self._skip_import_var" in source
    assert "self._import_var" not in source


def test_gui_exposes_a_manual_local_skill_path_entry():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "self._root_entry_var" in source
    assert 'text="Add"' in source
    assert 'text="Browse..."' in source


def test_text_collector_emits_version_2_for_local_and_online_workflows(
    tmp_path, monkeypatch
):
    s32ds = tmp_path / "S32DS.3.6.7"
    (s32ds / "eclipse").mkdir(parents=True)
    rtd = tmp_path / "RTD"
    (rtd / "Platform_TS_T40D34M10I0R0").mkdir(parents=True)
    root = tmp_path / "skills"
    source = _skill(root, "skill-a")
    candidate_label = f"skill-a — {source.resolve().as_posix()}"
    multi_answers = iter(
        (
            ["codex"],
            ["Import from local directory", "Install from online source"],
            [candidate_label],
        )
    )
    path_answers = iter((str(s32ds), str(rtd), str(root), ""))
    text_answers = iter(
        (
            "Find and install a testing skill.",
            "Initialize Agent formatting rules.",
        )
    )
    monkeypatch.setattr(
        init_agent_env_inputs,
        "_choose_multi",
        lambda _label, _options: next(multi_answers),
    )
    monkeypatch.setattr(
        init_agent_env_inputs,
        "_choose_one",
        lambda _label, _options: "Update — preserve existing environment",
    )
    monkeypatch.setattr(
        init_agent_env_inputs, "_ask_path_optional", lambda _prompt: next(path_answers)
    )
    monkeypatch.setattr(
        init_agent_env_inputs, "_safe_input", lambda _prompt: next(text_answers)
    )

    result = run_cli()

    assert result is not None
    assert result["version"] == 2
    assert result["additional_skill_workflows"] == ["local", "online"]
    assert result["local_skill_import"] == {
        "roots": [str(root)],
        "selected": [{"name": "skill-a", "source": source.resolve().as_posix()}],
    }
    assert result["online_skill_request"] == "Find and install a testing skill."
    assert result["supplemental_task"] == "Initialize Agent formatting rules."
