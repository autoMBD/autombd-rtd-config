# =================================================================================
# The MIT License
# MIT许可证
#
# <https://opensource.org/license/mit>
#
# SPDX short identifier / SPDX 短标识符: MIT
#
# Copyright (c) 2026 TkungL
# 版权所有 (c) 2026 TkungL
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 特此免费授予任何获得本软件及相关文档文件（以下简称“软件”）副本的人不受限制地
# 处理本软件的权利，包括但不限于使用、复制、修改、合并、发布、分发、再许可
# 和/或销售本软件副本，并允许接受本软件的人这样做，但须符合以下条件：
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 上述版权声明和本许可声明应包含在本软件的所有副本或主要部分中。
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALLTHE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 本软件按“原样”提供，不提供任何形式的明示或暗示担保，包括但不限于适销性、
# 特定用途适用性和非侵权担保。在任何情况下，无论是在合同、侵权或其他诉讼中，
# 作者或版权持有人均不对因本软件或本软件的使用或其他交易而产生、引起或相关的
# 任何索赔、损害或其他责任负责。
# =================================================================================
# Project:     autombd-mc-gd-sdk
# File:        test_sync_agent_skills.py
# Author:      TkungL <tkung.lqk@foxmail.com>
# Date:        2026-05-30
# Version:     0.1.0
# Description: Unit tests for repository-local agent skill symlink syncing
# =================================================================================

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("sync_agent_skills.py")


def can_create_symlink() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="agent-skills-symlink-"))
    try:
        target = tmp / "target"
        link = tmp / "link"
        target.mkdir()
        os.symlink(target, link, target_is_directory=True)
        return link.is_symlink()
    except OSError:
        return False
    finally:
        shutil.rmtree(tmp)


def load_module():
    spec = importlib.util.spec_from_file_location("sync_agent_skills", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SyncAgentSkillsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-skills-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self._skill("common-skills", "cli-module-development")
        self._skill("matlab-skills", "matlab-testing")
        (self.repo / "AGENTS.md").write_text("agent instructions\n", encoding="utf-8")
        (self.repo / "CLAUDE.md").write_text("claude instructions\n", encoding="utf-8")
        (self.repo / ".claude" / "skills").mkdir(parents=True)
        (self.repo / ".agents" / "skills").mkdir(parents=True)
        (self.repo / ".codex").mkdir()
        (self.repo / ".codex" / "config.toml").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def _skill(self, category: str, name: str) -> None:
        path = self.repo / ".skills" / category / name
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: test\n---\n",
            encoding="utf-8",
        )

    def test_dry_run_plans_existing_skill_roots_without_creating_codex_root(self):
        sync_agent_skills = load_module()

        result = sync_agent_skills.sync_repo(self.repo, dry_run=True)

        created = [op for op in result.operations if op.action == "link"]
        self.assertEqual(4, len(created))
        self.assertEqual(4, result.planned_links)
        self.assertFalse((self.repo / ".codex" / "skills").exists())
        self.assertIn("Claude Code", {op.agent for op in created})
        self.assertIn("Codex", {op.agent for op in created})
        self.assertEqual(
            {
                "common-skills-cli-module-development",
                "matlab-skills-matlab-testing",
            },
            {op.link_path.name for op in created},
        )

    def test_source_headers_have_readable_chinese_license_text(self):
        mojibake_markers = tuple(
            chr(code) for code in (0x9420, 0x95BB, 0x5A34, 0x9207, 0x951B)
        )

        for source in (MODULE_PATH, Path(__file__)):
            text = source.read_text(encoding="utf-8")
            self.assertIn("MIT许可证", text)
            self.assertIn("版权所有", text)
            for marker in mojibake_markers:
                self.assertNotIn(marker, text, f"{source.name} contains {marker}")

    def test_symlink_error_hint_covers_windows_linux_and_macos(self):
        sync_agent_skills = load_module()

        cases = {
            "win32": "Developer Mode",
            "linux": "ln -s",
            "darwin": "ln -s",
        }
        for platform_name, expected in cases.items():
            with self.subTest(platform=platform_name):
                self.assertIn(expected, sync_agent_skills.symlink_error_hint(platform_name))

    def test_sync_uses_relative_targets_and_preserves_real_directories(self):
        sync_agent_skills = load_module()
        preserved = self.repo / ".claude" / "skills" / "matlab-skills-matlab-testing"
        preserved.mkdir()
        calls = []

        def fake_link(target: Path, link_path: Path, target_is_directory: bool) -> None:
            calls.append((target, link_path, target_is_directory))
            link_path.write_text(str(target), encoding="utf-8")

        result = sync_agent_skills.sync_repo(
            self.repo,
            create_link=fake_link,
        )

        skipped = [op for op in result.operations if op.action == "skip"]
        self.assertEqual(1, len(skipped))
        self.assertEqual("matlab-skills-matlab-testing", skipped[0].skill)
        self.assertTrue(all(not target.is_absolute() for target, _, _ in calls))
        self.assertTrue(all(target_is_directory for _, _, target_is_directory in calls))
        self.assertEqual(3, result.linked)

    def test_remove_stale_prunes_obsolete_links_even_when_targets_exist(self):
        sync_agent_skills = load_module()
        root = self.repo / ".agents" / "skills"
        obsolete = root / "cli-module-development"
        current = root / "common-skills-cli-module-development"
        real_dir = root / "real-skill"
        external = root / "external"
        for path in (obsolete, current, external):
            path.write_text("", encoding="utf-8")
        real_dir.mkdir()

        target_map = {
            obsolete: self.repo / ".skills" / "common-skills" / "cli-module-development",
            current: self.repo / ".skills" / "common-skills" / "cli-module-development",
            external: Path("..") / ".." / "elsewhere" / "external",
        }
        symlink_names = {path.name for path in target_map}
        unlinked = []

        def fake_is_symlink(path: Path) -> bool:
            return path.name in symlink_names

        def fake_readlink(path: Path) -> str:
            return str(
                next(
                    target
                    for link, target in target_map.items()
                    if link.name == Path(path).name
                )
            )

        def fake_unlink(path: Path) -> None:
            unlinked.append(path)

        with (
            patch.object(Path, "is_symlink", fake_is_symlink),
            patch.object(Path, "unlink", fake_unlink),
            patch("os.readlink", fake_readlink),
        ):
            result = sync_agent_skills.sync_repo(self.repo, remove_stale=True)

        removed = [op for op in result.operations if op.action == "remove-stale"]
        self.assertEqual(["cli-module-development"], [op.link_path.name for op in removed])
        self.assertEqual(["cli-module-development"], [path.name for path in unlinked])
        self.assertTrue(real_dir.is_dir())

    @unittest.skipUnless(can_create_symlink(), "symlink privilege is not available")
    def test_remove_stale_deletes_obsolete_links_but_not_real_directories(self):
        sync_agent_skills = load_module()
        skills_root = self.repo / ".skills"
        stale = self.repo / ".agents" / "skills" / "old-skill"
        obsolete = self.repo / ".agents" / "skills" / "cli-module-development"
        current = self.repo / ".agents" / "skills" / "common-skills-cli-module-development"
        real_dir = self.repo / ".agents" / "skills" / "real-skill"
        external = self.repo / ".agents" / "skills" / "external"
        stale.symlink_to(Path("..") / ".." / ".skills" / "common-skills" / "old-skill")
        obsolete.symlink_to(Path("..") / ".." / ".skills" / "common-skills" / "cli-module-development")
        current.symlink_to(Path("..") / ".." / ".skills" / "common-skills" / "cli-module-development")
        real_dir.mkdir()
        external.symlink_to(Path("..") / ".." / "elsewhere" / "external")

        result = sync_agent_skills.sync_repo(self.repo, remove_stale=True)

        removed = [op for op in result.operations if op.action == "remove-stale"]
        self.assertEqual({stale, obsolete}, {op.link_path for op in removed})
        self.assertFalse(stale.exists())
        self.assertFalse(obsolete.exists())
        self.assertTrue(current.is_symlink())
        self.assertTrue(real_dir.is_dir())
        self.assertTrue(external.is_symlink())
        self.assertTrue(skills_root.exists())


if __name__ == "__main__":
    unittest.main()
