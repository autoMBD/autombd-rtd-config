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
# Description: Deploy the released RTD CfgFile CLI companion skill into Codex
#              and Claude Code skill indexes without copying development data.
# =================================================================================

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SKILL_NAME = "autombd-rtd"
SKILL_PAYLOAD_ITEMS = ("SKILL.md", "__main__.py", "rtd-config-cli-py", "assets")
SUPPORTED_AGENTS = ("codex", "claude")
CANONICAL_AGENT = "codex"
AGENT_SKILL_DIRS = {
    "codex": Path(".agents") / "skills",
    "claude": Path(".claude") / "skills",
}


@dataclass(frozen=True)
class ProjectVersions:
    skill: str
    launcher_header: str
    package: str


@dataclass(frozen=True)
class DeployResult:
    agent: str
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


def normalize_agents(agents: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for agent in agents:
        agent = agent.lower()
        if agent == "both":
            for supported_agent in SUPPORTED_AGENTS:
                if supported_agent not in normalized:
                    normalized.append(supported_agent)
            continue
        if agent not in SUPPORTED_AGENTS:
            raise ValueError(
                f"unsupported agent {agent!r}; expected one of: "
                f"{', '.join((*SUPPORTED_AGENTS, 'both'))}"
            )
        if agent not in normalized:
            normalized.append(agent)
    if not normalized:
        raise ValueError("at least one agent must be selected")
    return tuple(normalized)


def resolve_agent_skills_dir(target_project: Path, agent: str) -> Path:
    agent = normalize_agents((agent,))[0]
    return target_project.expanduser() / AGENT_SKILL_DIRS[agent]


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


# Windows transiently locks freshly-created/copied directory trees — antivirus,
# Defender, and the Search indexer open handles for a few hundred milliseconds —
# and rmtree/rename then fail with WinError 5 (access denied) or 32 (sharing
# violation); a just-deleted directory name can also linger in a pending-delete
# state, so renaming onto it fails until the FS settles. Retrying with a short
# backoff clears these races without masking a genuine, persistent failure.
_FS_RETRY_ATTEMPTS = 10
_FS_RETRY_DELAY_S = 0.1


def _is_transient_windows_lock(exc: OSError) -> bool:
    """True for the transient Windows FS-lock errors worth retrying.

    Scoped to Windows winerror codes so non-Windows behavior is unchanged and a
    real, persistent error on any platform still surfaces promptly.
    WinError 5 = ERROR_ACCESS_DENIED, 32 = ERROR_SHARING_VIOLATION,
    145 = ERROR_DIR_NOT_EMPTY (rmtree mid-race).
    """
    return sys.platform == "win32" and getattr(exc, "winerror", None) in (5, 32, 145)


def _retry_fs(operation) -> None:
    """Run a filesystem mutation, retrying transient Windows lock errors.

    Re-raises immediately for any non-transient error and re-raises the last
    error once the attempt budget is exhausted, so a genuine failure is never
    swallowed.
    """
    for attempt in range(_FS_RETRY_ATTEMPTS):
        try:
            operation()
            return
        except OSError as exc:
            if not _is_transient_windows_lock(exc) or attempt == _FS_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_FS_RETRY_DELAY_S * (attempt + 1))


def copy_released_payload(source_skill_root: Path, destination: Path) -> None:
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{destination.name}.deploying"
    remove_path(staging)
    staging.mkdir()

    for item in SKILL_PAYLOAD_ITEMS:
        source = source_skill_root / item
        target = staging / item
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

    remove_path(destination)
    # Atomic publish: the staged tree is renamed onto the destination. On Windows
    # this is the step most exposed to the transient post-copy/post-delete lock
    # window, so it is retried.
    _retry_fs(lambda: staging.rename(destination))


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        _retry_fs(path.unlink)
    elif path.exists():
        _retry_fs(lambda: shutil.rmtree(path))


def ensure_link(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = source.resolve()
    if destination.exists() and destination.resolve() == source:
        return "installed_link_is_current"
    remove_path(destination)
    try:
        destination.symlink_to(source, target_is_directory=True)
        return "symlink_to_canonical_skill"
    except OSError as exc:
        if sys.platform != "win32":
            raise RuntimeError("failed to create directory symlink") from exc
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(destination), str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "failed to create directory symlink or Windows junction; "
                "enable Developer Mode or run the deployment from an elevated shell"
            ) from exc
        return "junction_to_canonical_skill"


def deploy_canonical(repo_root: Path, target_project: Path) -> DeployResult:
    repo_root = repo_root.resolve()
    source_skill_root = repo_root / SKILL_NAME
    if not source_skill_root.is_dir():
        raise RuntimeError(f"source skill not found: {source_skill_root}")

    source_version = require_consistent_project_versions(read_project_versions(repo_root))
    skills_dir = resolve_agent_skills_dir(target_project, CANONICAL_AGENT)
    destination = skills_dir / SKILL_NAME
    should_copy, reason = should_deploy(source_version, destination)
    if not should_copy:
        return DeployResult(
            agent=CANONICAL_AGENT,
            action="skipped",
            version=source_version,
            destination=destination,
            reason=reason,
        )

    copy_released_payload(source_skill_root, destination)
    return DeployResult(
        agent=CANONICAL_AGENT,
        action="deployed",
        version=source_version,
        destination=destination,
        reason=reason,
    )


def deploy_one(repo_root: Path, target_project: Path, agent: str) -> DeployResult:
    agent = normalize_agents((agent,))[0]
    canonical_result = deploy_canonical(repo_root, target_project)
    if agent == CANONICAL_AGENT:
        return canonical_result

    destination = resolve_agent_skills_dir(target_project, agent) / SKILL_NAME
    reason = ensure_link(canonical_result.destination, destination)
    return DeployResult(
        agent=agent,
        action="skipped" if reason == "installed_link_is_current" else "linked",
        version=canonical_result.version,
        destination=destination,
        reason=reason,
    )


def deploy(
    repo_root: Path,
    target_project: Path,
    agents: tuple[str, ...] | list[str] = ("both",),
) -> tuple[DeployResult, ...]:
    return tuple(
        deploy_one(repo_root, target_project, agent) for agent in normalize_agents(agents)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy the RTD CfgFile CLI companion skill into project-local "
            "Codex and Claude Code skill indexes."
        )
    )
    parser.add_argument("target", type=Path, help="target project directory")
    parser.add_argument(
        "--agent",
        choices=(*SUPPORTED_AGENTS, "both"),
        default="both",
        help=(
            "agent skill index to deploy: codex -> <target>/.agents/skills, "
            "claude -> <target>/.claude/skills, both -> both indexes"
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="source repository root; defaults to this script's repository",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results = deploy(args.repo_root, args.target, agents=(args.agent,))
    for result in results:
        if result.action == "deployed":
            print(
                f"deployed {SKILL_NAME} {result.version} for {result.agent} "
                f"to {result.destination} ({result.reason})"
            )
        elif result.action == "linked":
            print(
                f"linked {SKILL_NAME} {result.version} for {result.agent} "
                f"to {result.destination} ({result.reason})"
            )
        else:
            print(
                f"skipped {SKILL_NAME} {result.version} for {result.agent} "
                f"at {result.destination} ({result.reason})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
