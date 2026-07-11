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
# Date:        2026-07-11
# Version:     0.3.0
# Description: Unit tests for deploying the RTD CfgFile CLI companion skill.
# =================================================================================

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_SKILL_ROOT = REPO_ROOT / "autombd-rtd"


def load_deploy_module():
    module_path = REPO_ROOT / "tools" / "deploy_rtd_skill.py"
    spec = importlib.util.spec_from_file_location("deploy_rtd_skill", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_retry_fs_recovers_from_transient_windows_lock(monkeypatch):
    """A transient WinError-5 on a deploy FS op is retried, then succeeds.

    Reproduces the deploy/black-box failure: AV/indexer briefly locks the freshly
    staged skill tree so ``staging.rename(destination)`` raises WinError 5; the
    bounded retry must absorb it instead of aborting the deploy.
    """
    deploy = load_deploy_module()
    monkeypatch.setattr(deploy.sys, "platform", "win32")
    monkeypatch.setattr(deploy.time, "sleep", lambda _s: None)  # no real backoff

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            err = PermissionError("access denied")
            err.winerror = 5
            raise err

    deploy._retry_fs(flaky)
    assert calls["n"] == 3


def test_retry_fs_reraises_non_transient_error_immediately(monkeypatch):
    """A non-transient OSError is not retried and surfaces on the first attempt."""
    deploy = load_deploy_module()
    monkeypatch.setattr(deploy.sys, "platform", "win32")
    monkeypatch.setattr(deploy.time, "sleep", lambda _s: None)

    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        err = OSError("no such file")
        err.winerror = 2  # ERROR_FILE_NOT_FOUND — not a transient lock code
        raise err

    with pytest.raises(OSError):
        deploy._retry_fs(boom)
    assert calls["n"] == 1  # not retried


def test_project_cli_and_skill_versions_match():
    deploy = load_deploy_module()

    versions = deploy.read_project_versions(Path(__file__).resolve().parents[2])

    # The three project versions must MATCH each other; don't pin a literal —
    # it bumps over time (e.g. the SKILL.md one-shot optimization -> 0.1.1).
    assert versions.launcher_header == versions.skill
    assert versions.package == versions.skill
    deploy.parse_version_tuple(versions.skill)  # must be a valid semver (raises otherwise)


def required_module_reference_paths() -> tuple[Path, ...]:
    """Return the complete module-reference inventory required by the Skill."""
    skill = (SOURCE_SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    required = {
        Path(relative)
        for relative in re.findall(
            r"`(reference/[a-z0-9_-]+-spec\.md)`",
            skill,
        )
    }
    source_inventory = {
        path.relative_to(SOURCE_SKILL_ROOT)
        for path in (SOURCE_SKILL_ROOT / "reference").glob("*-spec.md")
    }

    assert required == source_inventory, (
        "SKILL.md module-reference links and source reference inventory differ: "
        f"required={sorted(path.as_posix() for path in required)}, "
        f"source={sorted(path.as_posix() for path in source_inventory)}"
    )
    return tuple(sorted(required, key=lambda path: path.as_posix()))


def assert_released_payload(installed: Path):
    assert (installed / "SKILL.md").is_file()
    assert (installed / "__main__.py").is_file()
    assert (installed / "rtd-config-cli-py" / "rtd_config" / "cli.py").is_file()
    assert (installed / "assets" / "nxp" / "s32k3" / "uart" / "uart.json").is_file()
    assert (installed / "reference").is_dir(), (
        "deployed Skill is missing reference/ required by SKILL.md"
    )
    for relative in required_module_reference_paths():
        deployed = installed / relative
        source = SOURCE_SKILL_ROOT / relative
        assert deployed.is_file(), f"deployed Skill is missing {relative.as_posix()}"
        assert deployed.read_bytes() == source.read_bytes(), (
            f"deployed Skill reference differs from source: {relative.as_posix()}"
        )
    assert not (installed / "docs").exists()
    assert not (installed / "tests").exists()
    assert not (installed / "tools").exists()


def assert_link_points_to(link: Path, target: Path):
    assert link.exists()
    assert link.resolve() == target.resolve()


def create_complete_installed_payload(installed: Path, deploy, *, version: str) -> None:
    """Create the smallest installed tree satisfying the released-file contract."""
    for relative in deploy.SKILL_PAYLOAD_REQUIRED_FILES:
        target = installed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    (installed / "SKILL.md").write_text(
        f"---\nname: autombd-rtd\nversion: {version}\n---\n# installed\n",
        encoding="utf-8",
    )


def create_source_payload(source: Path, deploy) -> None:
    for item in deploy.SKILL_PAYLOAD_ITEMS:
        target = source / item
        if Path(item).suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item, encoding="utf-8")
        else:
            target.mkdir(parents=True, exist_ok=True)
    for relative in deploy.SKILL_PAYLOAD_REQUIRED_FILES:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(relative.as_posix(), encoding="utf-8")


def test_ensure_link_windows_symlink_failure_with_metachar_path_never_invokes_cmd(
    tmp_path,
    monkeypatch,
):
    deploy = load_deploy_module()
    source = tmp_path / "canonical"
    source.mkdir()
    destination = tmp_path / "safe&whoami"
    assert not hasattr(deploy, "subprocess")

    def deny_symlink(_self, _target, *, target_is_directory=False):
        raise OSError("symbolic-link privilege unavailable")

    monkeypatch.setattr(deploy.sys, "platform", "win32")
    monkeypatch.setattr(Path, "symlink_to", deny_symlink)

    with pytest.raises(RuntimeError, match="Developer Mode|elevated|symlink"):
        deploy.ensure_link(source, destination)


def test_ensure_link_symlink_failure_preserves_existing_destination(
    tmp_path,
    monkeypatch,
):
    deploy = load_deploy_module()
    source = tmp_path / "canonical"
    source.mkdir()
    destination = tmp_path / "installed"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("old install", encoding="utf-8")

    def deny_symlink(_self, _target, *, target_is_directory=False):
        raise OSError("symbolic-link privilege unavailable")

    monkeypatch.setattr(deploy.sys, "platform", "win32")
    monkeypatch.setattr(Path, "symlink_to", deny_symlink)

    with pytest.raises(RuntimeError, match="Developer Mode|elevated|symlink"):
        deploy.ensure_link(source, destination)

    assert sentinel.read_text(encoding="utf-8") == "old install"


def test_copy_released_payload_preserves_existing_install_when_publish_rename_fails(
    tmp_path,
    monkeypatch,
):
    deploy = load_deploy_module()
    source = tmp_path / "source"
    destination = tmp_path / "installed"
    create_source_payload(source, deploy)
    destination.mkdir()
    old_skill = destination / "SKILL.md"
    old_skill.write_text("old payload", encoding="utf-8")

    real_rename = deploy.Path.rename

    def fail_publish_rename(self, target):
        if (
            self.name.startswith(f".{destination.name}.deploying.")
            and Path(target) == destination
        ):
            raise PermissionError("destination locked")
        return real_rename(self, target)

    monkeypatch.setattr(deploy.Path, "rename", fail_publish_rename)

    with pytest.raises(PermissionError):
        deploy.copy_released_payload(source, destination)

    assert old_skill.read_text(encoding="utf-8") == "old payload"
    assert not list(destination.parent.glob(f".{destination.name}.deploying.*"))


def test_copy_released_payload_recovers_legacy_previous_before_copy_failure(
    tmp_path,
):
    deploy = load_deploy_module()
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "installed"
    previous = tmp_path / f".{destination.name}.previous"
    previous.mkdir()
    old_skill = previous / "SKILL.md"
    old_skill.write_text("old payload", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        deploy.copy_released_payload(source, destination)

    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "old payload"


def test_copy_released_payload_rejects_incomplete_staging_without_replacing_existing(
    tmp_path,
):
    deploy = load_deploy_module()
    source = tmp_path / "source"
    destination = tmp_path / "installed"
    create_source_payload(source, deploy)
    (source / "reference" / "adc-spec.md").unlink()
    destination.mkdir()
    old_skill = destination / "SKILL.md"
    old_skill.write_text("old payload", encoding="utf-8")

    with pytest.raises(RuntimeError, match="staged Skill payload is incomplete"):
        deploy.copy_released_payload(source, destination)

    assert old_skill.read_text(encoding="utf-8") == "old payload"
    assert not list(destination.parent.glob(f".{destination.name}.deploying.*"))


def test_deploy_defaults_to_codex_and_claude_project_skill_indexes(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]

    results = deploy.deploy(repo_root, tmp_path)

    assert {result.agent for result in results} == {"codex", "claude"}
    by_agent = {result.agent: result for result in results}
    assert by_agent["codex"].action == "deployed"
    assert by_agent["claude"].action == "linked"
    canonical = tmp_path / ".agents" / "skills" / "autombd-rtd"
    linked = tmp_path / ".claude" / "skills" / "autombd-rtd"
    assert_released_payload(canonical)
    assert_link_points_to(linked, canonical)
    assert_released_payload(linked)


def test_deploy_can_target_only_claude_project_skill_index(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]

    results = deploy.deploy(repo_root, tmp_path, agents=("claude",))

    assert len(results) == 1
    assert results[0].agent == "claude"
    assert results[0].action == "linked"
    assert results[0].destination == tmp_path / ".claude" / "skills" / "autombd-rtd"
    canonical = tmp_path / ".agents" / "skills" / "autombd-rtd"
    assert_released_payload(canonical)
    assert_link_points_to(results[0].destination, canonical)
    assert_released_payload(results[0].destination)


def test_deploy_updates_when_installed_version_is_older(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]
    installed = tmp_path / ".agents" / "skills" / "autombd-rtd"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text(
        "---\nname: autombd-rtd\nversion: 0.0.9\n---\n# stale\n",
        encoding="utf-8",
    )
    (installed / "old-development-note.txt").write_text("remove me", encoding="utf-8")

    result = deploy.deploy_one(repo_root, tmp_path, "codex")

    assert result.action == "deployed"
    assert "old-development-note.txt" not in {p.name for p in installed.iterdir()}
    src_version = deploy.read_project_versions(repo_root).skill
    assert f"version: {src_version}" in (installed / "SKILL.md").read_text(encoding="utf-8")


def test_deploy_replaces_existing_claude_copy_with_link(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]
    installed = tmp_path / ".claude" / "skills" / "autombd-rtd"
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text(
        "---\nname: autombd-rtd\nversion: 0.0.9\n---\n# stale\n",
        encoding="utf-8",
    )

    result = deploy.deploy_one(repo_root, tmp_path, "claude")

    canonical = tmp_path / ".agents" / "skills" / "autombd-rtd"
    assert result.action == "linked"
    assert_link_points_to(installed, canonical)


def test_main_reports_linked_agent_destinations(tmp_path, capsys):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]

    exit_code = deploy.main(
        [str(tmp_path), "--agent", "claude", "--repo-root", str(repo_root)]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    src_version = deploy.read_project_versions(repo_root).skill
    assert f"linked autombd-rtd {src_version} for claude" in output
    assert f"skipped autombd-rtd {src_version} for claude" not in output


def test_deploy_skips_when_installed_version_is_current_or_newer(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]
    installed = tmp_path / ".agents" / "skills" / "autombd-rtd"
    create_complete_installed_payload(installed, deploy, version="9.9.9")
    sentinel = installed / "keep.txt"
    sentinel.write_text("must stay", encoding="utf-8")

    assert deploy.installed_payload_complete(installed)
    result = deploy.deploy_one(repo_root, tmp_path, "codex")

    assert result.action == "skipped"
    assert result.agent == "codex"
    assert result.reason == "installed_version_is_current_or_newer"
    assert sentinel.read_text(encoding="utf-8") == "must stay"


def test_deploy_replaces_newer_install_when_required_reference_is_missing(tmp_path):
    deploy = load_deploy_module()
    repo_root = Path(__file__).resolve().parents[2]
    installed = tmp_path / ".agents" / "skills" / "autombd-rtd"
    create_complete_installed_payload(installed, deploy, version="9.9.9")
    missing_reference = installed / "reference" / "mcu-spec.md"
    missing_reference.unlink()

    assert not deploy.installed_payload_complete(installed)
    result = deploy.deploy_one(repo_root, tmp_path, "codex")

    assert result.action == "deployed"
    assert result.reason == "installed_payload_incomplete"
    assert_released_payload(installed)
