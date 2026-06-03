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
# File:        sync_agent_skills.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Developer tool: sync the committed companion agent skill.
# =================================================================================

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


CreateLink = Callable[[Path, Path, bool], None]


@dataclass(frozen=True)
class AgentTarget:
    name: str
    markers: tuple[str, ...]
    skill_roots: tuple[str, ...]


@dataclass(frozen=True)
class SkillEntry:
    name: str
    link_name: str
    path: Path


@dataclass(frozen=True)
class Operation:
    action: str
    agent: str
    skill: str
    link_path: Path
    target: Path | None = None
    message: str = ""


@dataclass
class SyncResult:
    operations: list[Operation] = field(default_factory=list)
    planned_links: int = 0
    linked: int = 0
    unchanged: int = 0
    skipped: int = 0
    removed_stale: int = 0
    errors: int = 0


AGENT_TARGETS: tuple[AgentTarget, ...] = (
    AgentTarget(
        name="Claude Code",
        markers=("CLAUDE.md", ".claude"),
        skill_roots=(".claude/skills",),
    ),
    AgentTarget(
        name="Codex",
        markers=("AGENTS.md", ".codex", ".agents"),
        skill_roots=(".agents/skills", ".codex/skills"),
    ),
    AgentTarget(
        name="GitHub Copilot",
        markers=(
            ".github/copilot-instructions.md",
            ".github/instructions",
            ".github/copilot",
        ),
        skill_roots=(".github/copilot/skills", ".github/skills"),
    ),
    AgentTarget(
        name="OpenCode",
        markers=("opencode.json", "opencode.yaml", "opencode.toml", ".opencode"),
        skill_roots=(".opencode/skills",),
    ),
)


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def read_frontmatter_name(skill_file: Path) -> str | None:
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        lines = skill_file.read_text(encoding="utf-8-sig").splitlines()

    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:40]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def discover_skills(repo: Path) -> list[SkillEntry]:
    skills_root = repo / ".skills"
    if not skills_root.is_dir():
        return []

    skills: list[SkillEntry] = []
    used_names: set[str] = set()
    for skill_file in sorted(skills_root.rglob("SKILL.md")):
        skill_dir = skill_file.parent
        name = read_frontmatter_name(skill_file) or skill_dir.name
        if name in used_names:
            continue
        used_names.add(name)
        rel_parts = skill_dir.relative_to(skills_root).parts
        link_name = "-".join(rel_parts[:-1] + (name,))
        skills.append(SkillEntry(name=name, link_name=link_name, path=skill_dir))
    return skills


def detected_skill_roots(repo: Path) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    for target in AGENT_TARGETS:
        has_marker = any((repo / marker).exists() for marker in target.markers)
        if not has_marker:
            continue
        for root in target.skill_roots:
            path = repo / root
            if path.is_dir():
                roots.append((target.name, path))
    return roots


def relative_target(source: Path, link_path: Path) -> Path:
    return Path(os.path.relpath(source, start=link_path.parent))


def default_create_link(target: Path, link_path: Path, target_is_directory: bool) -> None:
    os.symlink(target, link_path, target_is_directory=target_is_directory)


def symlink_error_hint(platform_name: str = sys.platform) -> str:
    if platform_name.startswith("win"):
        return (
            "creating relative directory symlinks on Windows may require Developer Mode "
            "or an elevated shell; enable Developer Mode or rerun from an administrator "
            "PowerShell session."
        )
    if platform_name == "darwin":
        return (
            "creating relative directory symlinks on macOS should work with normal user "
            "permissions; verify the destination filesystem supports symlinks, or test "
            "manually with ln -s."
        )
    return (
        "creating relative directory symlinks on Linux should work with normal user "
        "permissions; verify the destination filesystem supports symlinks, or test "
        "manually with ln -s."
    )


def link_points_to(link_path: Path, expected: Path) -> bool:
    if not link_path.is_symlink():
        return False
    raw_target = Path(os.readlink(link_path))
    actual = raw_target if raw_target.is_absolute() else link_path.parent / raw_target
    return actual.resolve(strict=False) == expected.resolve(strict=False)


def remove_stale_links(
    repo: Path,
    skills_root: Path,
    roots: Iterable[tuple[str, Path]],
    expected_links: dict[Path, Path],
    result: SyncResult,
    dry_run: bool,
) -> set[Path]:
    removed_paths: set[Path] = set()
    for agent, root in roots:
        for link_path in sorted(root.iterdir()):
            if not link_path.is_symlink():
                continue
            raw_target = Path(os.readlink(link_path))
            actual = raw_target if raw_target.is_absolute() else link_path.parent / raw_target
            resolved = actual.resolve(strict=False)
            if not is_relative_to(resolved, skills_root.resolve(strict=False)):
                continue
            expected_target = expected_links.get(link_path)
            if expected_target is not None and link_points_to(link_path, expected_target):
                continue
            result.operations.append(
                Operation(
                    action="remove-stale",
                    agent=agent,
                    skill=link_path.name,
                    link_path=link_path,
                    target=actual,
                )
            )
            result.removed_stale += 1
            removed_paths.add(link_path)
            if not dry_run:
                link_path.unlink()
    return removed_paths


def sync_repo(
    repo: Path,
    dry_run: bool = False,
    remove_stale: bool = False,
    create_link: CreateLink = default_create_link,
) -> SyncResult:
    repo = repo.resolve()
    result = SyncResult()
    skills = discover_skills(repo)
    roots = detected_skill_roots(repo)
    skills_root = repo / ".skills"
    expected_links = {
        root / skill.link_name: skill.path
        for _, root in roots
        for skill in skills
    }

    removed_paths: set[Path] = set()
    if remove_stale:
        removed_paths = remove_stale_links(
            repo,
            skills_root,
            roots,
            expected_links,
            result,
            dry_run,
        )

    for agent, root in roots:
        for skill in skills:
            link_path = root / skill.link_name
            rel_target = relative_target(skill.path, link_path)
            path_present = link_path.exists() or link_path.is_symlink()
            if dry_run and link_path in removed_paths:
                path_present = False
            if path_present:
                if link_points_to(link_path, skill.path):
                    result.unchanged += 1
                    result.operations.append(
                        Operation("unchanged", agent, skill.link_name, link_path, rel_target)
                    )
                else:
                    result.skipped += 1
                    result.operations.append(
                        Operation(
                            "skip",
                            agent,
                            skill.link_name,
                            link_path,
                            rel_target,
                            "existing path is not the expected skill symlink",
                        )
                    )
                continue
            result.operations.append(Operation("link", agent, skill.link_name, link_path, rel_target))
            result.planned_links += 1
            if dry_run:
                continue
            try:
                create_link(rel_target, link_path, True)
                result.linked += 1
            except OSError as exc:
                result.errors += 1
                result.operations.append(
                    Operation("error", agent, skill.link_name, link_path, rel_target, str(exc))
                )
    return result


def format_operation(repo: Path, op: Operation) -> str:
    link = op.link_path.relative_to(repo)
    target = f" -> {op.target}" if op.target is not None else ""
    suffix = f" ({op.message})" if op.message else ""
    return f"{op.action:12} {op.agent:14} {op.skill:36} {link}{target}{suffix}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Link this repository's .skills entries into detected agent skill roots.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root; defaults to the parent of tools/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned changes without creating or removing links",
    )
    parser.add_argument(
        "--remove-stale",
        action="store_true",
        help=(
            "remove obsolete or broken symlinks that point back into this "
            "repository's .skills/"
        ),
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="show supported agent markers and skill roots",
    )
    return parser


def print_supported_agents() -> None:
    for target in AGENT_TARGETS:
        print(target.name)
        print(f"  markers: {', '.join(target.markers)}")
        print(f"  skill roots: {', '.join(target.skill_roots)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_agents:
        print_supported_agents()
        return 0

    repo = args.repo.resolve()
    result = sync_repo(repo, dry_run=args.dry_run, remove_stale=args.remove_stale)
    for op in result.operations:
        print(format_operation(repo, op))
    print(
        "summary: "
        f"planned_links={result.planned_links}, linked={result.linked}, unchanged={result.unchanged}, "
        f"skipped={result.skipped}, removed_stale={result.removed_stale}, "
        f"errors={result.errors}"
    )
    if result.errors:
        print(f"error: {symlink_error_hint()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
