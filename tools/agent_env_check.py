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
# File:        agent_env_check.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-15
# Version:     0.1.0
# Description: Verify and cache agent-session development dependencies.
# =================================================================================

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

SCHEMA_VERSION = 1
STATE_DIR = ".agent-state"
STATE_FILE = "environment-verification.json"
STATUS_PASSED = "passed"
STATUS_BLOCKED = "blocked"
STATUS_WARNING = "warning"
AGENT_CODEX = "codex"
AGENT_CLAUDE = "claude"
AGENT_OTHER = "other"


@dataclass(frozen=True)
class CheckResult:
    key: str
    status: str
    summary: str
    detail: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Dependency:
    key: str
    label: str
    required: bool
    interactive_auth: bool
    prepare: str
    probe: Callable[[], CheckResult]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_state_file(repo_root: Path) -> Path:
    return repo_root / STATE_DIR / STATE_FILE


def load_state(state_file: Path) -> dict:
    if not state_file.is_file():
        return {"schema_version": SCHEMA_VERSION, "dependencies": {}}
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "dependencies": {}}
    if data.get("schema_version") != SCHEMA_VERSION:
        return {"schema_version": SCHEMA_VERSION, "dependencies": {}}
    if not isinstance(data.get("dependencies"), dict):
        data["dependencies"] = {}
    return data


def save_state(state_file: Path, state: Mapping[str, object]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def cached_dependency(state_file: Path, key: str) -> dict | None:
    entry = load_state(state_file).get("dependencies", {}).get(key)
    return entry if isinstance(entry, dict) and entry.get("status") == STATUS_PASSED else None


def cached_executable_path(state_file: Path, key: str) -> str | None:
    entry = cached_dependency(state_file, key)
    if entry is None:
        return None
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        return None
    path = metadata.get("path")
    if not isinstance(path, str) or not path:
        return None
    return path if Path(path).exists() else None


def _entry_from_result(
    dependency: Dependency,
    result: CheckResult,
    checked_at: str,
    source: str,
) -> dict:
    return {
        "label": dependency.label,
        "required": dependency.required,
        "interactive_auth": dependency.interactive_auth,
        "status": result.status,
        "summary": result.summary,
        "detail": result.detail,
        "prepare": dependency.prepare,
        "checked_at": checked_at,
        "source": source,
        "metadata": dict(result.metadata),
    }


def verify_dependencies(
    repo_root: Path,
    dependencies: tuple[Dependency, ...],
    state_file: Path,
    refresh: bool,
    confirmations: Mapping[str, str] | None = None,
    now: Callable[[], str] = utc_now,
) -> dict:
    state = load_state(state_file)
    stored = state.setdefault("dependencies", {})
    report_dependencies: dict[str, dict] = {}
    confirmations = confirmations or {}

    for dependency in dependencies:
        confirmation = confirmations.get(dependency.key)
        if confirmation:
            checked_at = now()
            result = CheckResult(
                key=dependency.key,
                status=STATUS_PASSED,
                summary=f"{dependency.label} verified by user confirmation",
                detail=confirmation,
                metadata={"confirmation": confirmation},
            )
            entry = _entry_from_result(dependency, result, checked_at, "user_confirmation")
            stored[dependency.key] = entry
            report_dependencies[dependency.key] = entry
            continue

        cached = stored.get(dependency.key)
        if (
            not refresh
            and isinstance(cached, dict)
            and cached.get("status") == STATUS_PASSED
        ):
            entry = dict(cached)
            entry["source"] = "cache"
            report_dependencies[dependency.key] = entry
            continue

        checked_at = now()
        result = dependency.probe()
        entry = _entry_from_result(dependency, result, checked_at, "probe")
        stored[dependency.key] = entry
        report_dependencies[dependency.key] = entry

    save_state(state_file, state)
    blocked_required = [
        key
        for key, entry in report_dependencies.items()
        if entry.get("required") and entry.get("status") != STATUS_PASSED
    ]
    summary = {
        "total": len(report_dependencies),
        "passed": sum(1 for entry in report_dependencies.values() if entry["status"] == STATUS_PASSED),
        "blocked": len(blocked_required),
        "warnings": sum(1 for entry in report_dependencies.values() if entry["status"] == STATUS_WARNING),
    }
    return {
        "status": STATUS_PASSED if not blocked_required else STATUS_BLOCKED,
        "schema_version": SCHEMA_VERSION,
        "repo_root": str(repo_root),
        "state_file": str(state_file),
        "summary": summary,
        "blocked_required": blocked_required,
        "dependencies": report_dependencies,
    }


def _run(argv: list[str], timeout_s: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout_s,
    )


def _which_any(names: tuple[str, ...]) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path is not None:
            return path
    return None


def probe_python() -> CheckResult:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 11):
        return CheckResult(
            "python",
            STATUS_PASSED,
            f"Python {version}",
            metadata={"version": version, "executable": sys.executable},
        )
    return CheckResult("python", STATUS_BLOCKED, f"Python {version} is older than 3.11")


def probe_git() -> CheckResult:
    path = _which_any(("git", "git.exe"))
    if path is None:
        return CheckResult("git", STATUS_BLOCKED, "git executable not found on PATH")
    result = _run([path, "--version"])
    summary = (result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr).strip() else path
    status = STATUS_PASSED if result.returncode == 0 else STATUS_BLOCKED
    return CheckResult("git", status, summary, metadata={"path": path})


def probe_github_cli() -> CheckResult:
    path = _which_any(("gh", "gh.exe"))
    if path is None:
        return CheckResult("github_cli", STATUS_BLOCKED, "GitHub CLI not found on PATH")
    version = _run([path, "--version"])
    auth = _run([path, "auth", "status", "-h", "github.com"])
    version_line = (version.stdout or version.stderr).strip().splitlines()[0] if (version.stdout or version.stderr).strip() else path
    if auth.returncode != 0:
        detail = (auth.stderr or auth.stdout).strip()
        return CheckResult(
            "github_cli",
            STATUS_BLOCKED,
            "GitHub CLI is installed but not authenticated",
            detail,
            {"path": path, "version": version_line},
        )
    return CheckResult(
        "github_cli",
        STATUS_PASSED,
        f"{version_line}; authenticated",
        metadata={"path": path, "version": version_line},
    )


def probe_github_app_connector() -> CheckResult:
    return CheckResult(
        "github_app_connector",
        STATUS_PASSED,
        "Codex uses the GitHub App connector; GitHub CLI authentication is not required",
        metadata={"connector": "GitHub App", "agent": AGENT_CODEX},
    )


def probe_codex_cli() -> CheckResult:
    path = _which_any(("codex", "codex.cmd", "codex.exe"))
    if path is None:
        return CheckResult("codex_cli", STATUS_BLOCKED, "Codex CLI not found on PATH")
    result = _run([path, "--version"])
    summary = (result.stdout or result.stderr).strip().splitlines()[0] if (result.stdout or result.stderr).strip() else path
    status = STATUS_PASSED if result.returncode == 0 else STATUS_WARNING
    return CheckResult("codex_cli", status, summary, metadata={"path": path})


def probe_s32ds() -> CheckResult:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "autombd-rtd" / "rtd-config-cli-py"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    try:
        from rtd_config.backends.s32_mex.validation import find_s32ds_root
    except Exception as exc:  # pragma: no cover - defensive import guard
        return CheckResult("s32ds", STATUS_BLOCKED, "S32DS locator could not be imported", str(exc))

    root = find_s32ds_root(None)
    if root is None:
        return CheckResult(
            "s32ds",
            STATUS_BLOCKED,
            "S32DS root not found",
            "Auto-discovery checks PATH, RTD_CONFIG_S32DS_ROOT, and standard C:\\NXP\\S32DS* installs.",
        )
    return CheckResult("s32ds", STATUS_PASSED, f"S32DS root found: {root}", metadata={"root": str(root)})


def make_reference_materials_probe(repo_root: Path) -> Callable[[], CheckResult]:
    required_paths = (
        "AGENTS.md",
        "agent-discipline/documentation-governance.md",
        "docs/specs/rtd-config-domain-truth.md",
        "docs/tests/rtd-config-test-cases.md",
        "docs/references/rtd-config-source-materials.md",
        "tools/blackbox_e2e.py",
        "tools/deploy_rtd_skill.py",
        "autombd-rtd/SKILL.md",
        "autombd-rtd/assets",
    )

    def probe() -> CheckResult:
        missing = [path for path in required_paths if not (repo_root / path).exists()]
        if missing:
            return CheckResult(
                "reference_materials",
                STATUS_BLOCKED,
                "Required project reference materials are missing",
                ", ".join(missing),
                {"missing": missing},
            )
        return CheckResult(
            "reference_materials",
            STATUS_PASSED,
            "Agent discipline, docs, tools, released skill, and assets are present",
            metadata={"paths": list(required_paths)},
        )

    return probe


def make_github_dependency(agent: str) -> Dependency:
    if agent == AGENT_CODEX:
        return Dependency(
            key="github_app_connector",
            label="GitHub App connector",
            required=True,
            interactive_auth=False,
            prepare="Use the installed Codex GitHub App connector for issue, PR, and repository operations.",
            probe=probe_github_app_connector,
        )
    return Dependency(
        key="github_cli",
        label="GitHub CLI",
        required=True,
        interactive_auth=True,
        prepare=(
            "Run gh auth status -h github.com in the target agent environment. "
            "If it cannot return a usable result, ask the user to complete "
            "gh auth login -h github.com and provide an OK confirmation, then "
            "rerun this check with --confirm-github-cli-auth <confirmation>."
        ),
        probe=probe_github_cli,
    )


def normalize_agent(agent: str) -> str:
    normalized = agent.lower()
    if normalized not in (AGENT_CODEX, AGENT_CLAUDE, AGENT_OTHER):
        raise ValueError(f"unsupported agent {agent!r}; expected codex, claude, or other")
    return normalized


def build_dependencies(repo_root: Path, agent: str = AGENT_CODEX) -> tuple[Dependency, ...]:
    agent = normalize_agent(agent)
    return (
        Dependency(
            key="python",
            label="Python runtime",
            required=True,
            interactive_auth=False,
            prepare="Install Python 3.11 or newer and ensure it is on PATH.",
            probe=probe_python,
        ),
        Dependency(
            key="git",
            label="Git",
            required=True,
            interactive_auth=False,
            prepare="Install Git and ensure git is on PATH.",
            probe=probe_git,
        ),
        make_github_dependency(agent),
        Dependency(
            key="codex_cli",
            label="Third-party agent CLI: Codex",
            required=True,
            interactive_auth=True,
            prepare="Install Codex CLI, then complete its first-run login/authorization before black-box E2E.",
            probe=probe_codex_cli,
        ),
        Dependency(
            key="s32ds",
            label="S32 Design Studio + RTD 7.0.1",
            required=True,
            interactive_auth=False,
            prepare="Install S32DS with S32K3 RTD 7.0.1, or set RTD_CONFIG_S32DS_ROOT.",
            probe=probe_s32ds,
        ),
        Dependency(
            key="reference_materials",
            label="Repository reference materials and tools",
            required=True,
            interactive_auth=False,
            prepare="Restore the repository checkout; do not delete docs, tools, autombd-rtd, or agent-discipline.",
            probe=make_reference_materials_probe(repo_root),
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify and cache project agent-session dependencies."
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--refresh", action="store_true", help="ignore cached passes and probe again")
    parser.add_argument(
        "--agent",
        choices=(AGENT_CODEX, AGENT_CLAUDE, AGENT_OTHER),
        default=AGENT_CODEX,
        help="agent environment to verify; Codex uses the GitHub App connector instead of GitHub CLI",
    )
    parser.add_argument(
        "--confirm-github-cli-auth",
        help=(
            "non-Codex fallback: user confirmation that gh auth status -h "
            "github.com passed in the target agent environment"
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit the full JSON report")
    return parser


def _print_human(report: Mapping[str, object]) -> None:
    print(f"Agent environment: {report['status']}")
    print(f"State file: {report['state_file']}")
    dependencies = report.get("dependencies", {})
    if not isinstance(dependencies, dict):
        return
    for key, entry in dependencies.items():
        if not isinstance(entry, dict):
            continue
        print(f"- {key}: {entry.get('status')} ({entry.get('source')}) - {entry.get('summary')}")
        if entry.get("status") != STATUS_PASSED:
            print(f"  prepare: {entry.get('prepare')}")
            if entry.get("detail"):
                print(f"  detail: {entry.get('detail')}")


def main(
    argv: list[str] | None = None,
    *,
    dependencies: tuple[Dependency, ...] | None = None,
    now: Callable[[], str] = utc_now,
) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    state_file = args.state_file or default_state_file(repo_root)
    deps = dependencies if dependencies is not None else build_dependencies(repo_root, agent=args.agent)
    confirmations = {}
    if args.confirm_github_cli_auth:
        confirmations["github_cli"] = args.confirm_github_cli_auth
    report = verify_dependencies(
        repo_root=repo_root,
        dependencies=deps,
        state_file=state_file,
        refresh=args.refresh,
        confirmations=confirmations,
        now=now,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0 if report["status"] == STATUS_PASSED else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
