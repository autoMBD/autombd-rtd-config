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
# File:        test_deploy_rtd_skill.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-13
# Version:     0.1.0
# Description: Unit tests for deploying the RTD CfgFile CLI companion skill.
# =================================================================================

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_deploy_module():
    module_path = Path(__file__).resolve().parents[2] / "tools" / "deploy_rtd_skill.py"
    spec = importlib.util.spec_from_file_location("deploy_rtd_skill", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_project_cli_and_skill_versions_match():
    deploy = load_deploy_module()

    versions = deploy.read_project_versions(Path(__file__).resolve().parents[2])

    assert versions.skill == "0.1.0"
    assert versions.launcher_header == versions.skill
    assert versions.package == versions.skill


def test_deploy_copies_only_released_skill_payload(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]

    result = deploy.deploy(repo_root, tmp_path)

    installed = tmp_path / "skills" / "autombd-rtd"
    assert result.action == "deployed"
    assert result.version == "0.1.0"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "__main__.py").is_file()
    assert (installed / "rtd-config-cli-py" / "rtd_config" / "cli.py").is_file()
    assert (installed / "assets" / "nxp" / "s32k3" / "uart" / "uart.json").is_file()
    assert not (installed / "docs").exists()
    assert not (installed / "tests").exists()
    assert not (installed / "tools").exists()


def test_deploy_updates_when_installed_version_is_older(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]
    installed = tmp_path / "skills" / "autombd-rtd"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text(
        "---\nname: autombd-rtd\nversion: 0.0.9\n---\n# stale\n",
        encoding="utf-8",
    )
    (installed / "old-development-note.txt").write_text("remove me", encoding="utf-8")

    result = deploy.deploy(repo_root, tmp_path)

    assert result.action == "deployed"
    assert "old-development-note.txt" not in {p.name for p in installed.iterdir()}
    assert "version: 0.1.0" in (installed / "SKILL.md").read_text(encoding="utf-8")


def test_deploy_skips_when_installed_version_is_current_or_newer(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]
    installed = tmp_path / "skills" / "autombd-rtd"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text(
        "---\nname: autombd-rtd\nversion: 9.9.9\n---\n# newer\n",
        encoding="utf-8",
    )
    (installed / "__main__.py").write_text("# launcher\n", encoding="utf-8")
    (installed / "rtd-config-cli-py").mkdir()
    (installed / "assets").mkdir()
    sentinel = installed / "keep.txt"
    sentinel.write_text("must stay", encoding="utf-8")

    result = deploy.deploy(repo_root, tmp_path)

    assert result.action == "skipped"
    assert result.reason == "installed_version_is_current_or_newer"
    assert sentinel.read_text(encoding="utf-8") == "must stay"
