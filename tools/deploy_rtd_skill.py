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
# File:        deploy_rtd_skill.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-13
# Version:     0.1.0
# Description: Deploy the released RTD CfgFile CLI companion skill into a Codex
#              skills index without copying development-only project material.
# =================================================================================

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

SKILL_NAME = "autombd-rtd"
SKILL_PAYLOAD_ITEMS = ("SKILL.md", "__main__.py", "rtd-config-cli-py", "assets")


@dataclass(frozen=True)
class ProjectVersions:
    skill: str
    launcher_header: str
    package: str


@dataclass(frozen=True)
class DeployResult:
    action: str
    version: str
    destination: Path
    reason: str = ""


def parse_version_tuple(version: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise ValueError(f"unsupported semantic version: {version!r}")
    return tuple(int(part) for part in version.split("."))


def extract_front_matter_value(markdown: str, key: str) -> str | None:
    if not markdown.startswith("---\n"):
        return None
    end = markdown.find("\n---", 4)
    if end == -1:
        return None
    front_matter = markdown[4:end]
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
    match = pattern.search(front_matter)
    return match.group(1).strip("\"'")


def read_skill_version(skill_file: Path) -> str | None:
    if not skill_file.is_file():
        return None
    return extract_front_matter_value(skill_file.read_text(encoding="utf-8"), "version")


def read_launcher_header_version(launcher_file: Path) -> str:
    text = launcher_file.read_text(encoding="utf-8")
    match = re.search(r"^# Version:\s+(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing Version header in {launcher_file}")
    return match.group(1)


def read_package_version(package_init: Path) -> str:
    text = package_init.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing __version__ in {package_init}")
    return match.group(1)


def read_project_versions(repo_root: Path) -> ProjectVersions:
    skill_root = repo_root / SKILL_NAME
    skill_version = read_skill_version(skill_root / "SKILL.md")
    if skill_version is None:
        raise RuntimeError(f"missing version in {skill_root / 'SKILL.md'}")
    return ProjectVersions(
        skill=skill_version,
        launcher_header=read_launcher_header_version(skill_root / "__main__.py"),
        package=read_package_version(
            skill_root / "rtd-config-cli-py" / "rtd_config" / "__init__.py"
        ),
    )


def require_consistent_project_versions(versions: ProjectVersions) -> str:
    unique_versions = {versions.skill, versions.launcher_header, versions.package}
    if len(unique_versions) != 1:
        raise RuntimeError(
            "project version mismatch: "
            f"SKILL.md={versions.skill}, "
            f"launcher={versions.launcher_header}, "
            f"package={versions.package}"
        )
    parse_version_tuple(versions.skill)
    return versions.skill


def resolve_skills_dir(target_root: Path) -> Path:
    target_root = target_root.expanduser()
    if target_root.name.lower() == "skills":
        return target_root
    return target_root / "skills"


def installed_payload_complete(destination: Path) -> bool:
    return all((destination / item).exists() for item in SKILL_PAYLOAD_ITEMS)


def should_deploy(source_version: str, destination: Path) -> tuple[bool, str]:
    installed_version = read_skill_version(destination / "SKILL.md")
    if installed_version is None:
        return True, "installed_skill_or_version_missing"
    if not installed_payload_complete(destination):
        return True, "installed_payload_incomplete"
    if parse_version_tuple(installed_version) < parse_version_tuple(source_version):
        return True, "installed_version_is_older"
    return False, "installed_version_is_current_or_newer"


def copy_released_payload(source_skill_root: Path, destination: Path) -> None:
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{destination.name}.deploying"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    for item in SKILL_PAYLOAD_ITEMS:
        source = source_skill_root / item
        target = staging / item
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

    if destination.exists():
        shutil.rmtree(destination)
    staging.rename(destination)


def deploy(repo_root: Path, target_root: Path) -> DeployResult:
    repo_root = repo_root.resolve()
    source_skill_root = repo_root / SKILL_NAME
    if not source_skill_root.is_dir():
        raise RuntimeError(f"source skill not found: {source_skill_root}")

    source_version = require_consistent_project_versions(read_project_versions(repo_root))
    skills_dir = resolve_skills_dir(target_root)
    destination = skills_dir / SKILL_NAME
    should_copy, reason = should_deploy(source_version, destination)
    if not should_copy:
        return DeployResult(
            action="skipped",
            version=source_version,
            destination=destination,
            reason=reason,
        )

    copy_released_payload(source_skill_root, destination)
    return DeployResult(
        action="deployed",
        version=source_version,
        destination=destination,
        reason=reason,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy the RTD CfgFile CLI companion skill into a target skills index. "
            "Pass an agent home directory to deploy under <target>/skills, or pass "
            "the skills directory itself."
        )
    )
    parser.add_argument("target", type=Path, help="agent home directory or skills index")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="source repository root; defaults to this script's repository",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = deploy(args.repo_root, args.target)
    if result.action == "deployed":
        print(
            f"deployed {SKILL_NAME} {result.version} to {result.destination} "
            f"({result.reason})"
        )
    else:
        print(
            f"skipped {SKILL_NAME} {result.version} at {result.destination} "
            f"({result.reason})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
