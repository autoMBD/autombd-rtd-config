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
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

SKILL_NAME = "autombd-rtd"
RELEASE_MANIFEST_NAME = "release-manifest.json"
RELEASE_MANIFEST_FORMAT_VERSION = 1
SKILL_PAYLOAD_ITEMS = (
    "SKILL.md",
    "__main__.py",
    "rtd-config-cli-py",
    "assets",
    "reference",
)
MODULE_REFERENCE_FILES = tuple(
    Path("reference") / f"{module}-spec.md"
    for module in (
        "mcu",
        "basenxp",
        "platform",
        "port",
        "dio",
        "mcl",
        "uart",
        "adc",
    )
)
SKILL_PAYLOAD_REQUIRED_FILES = (
    Path("SKILL.md"),
    Path("__main__.py"),
    Path("rtd-config-cli-py") / "rtd_config" / "cli.py",
    Path("assets") / "nxp" / "s32k3" / "uart" / "uart.json",
    *MODULE_REFERENCE_FILES,
)
SUPPORTED_AGENTS = ("codex", "claude")
CANONICAL_AGENT = "codex"
AGENT_SKILL_DIRS = {
    "codex": Path(".agents") / "skills",
    "claude": Path(".claude") / "skills",
}


@dataclass(frozen=True)
class ProjectVersions:
    project: str
    skill: str
    launcher_header: str
    package_header: str
    package: str
    manifest: str


@dataclass(frozen=True)
class ReleaseFile:
    path: str
    sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
    format_version: int
    release_version: str
    files: tuple[ReleaseFile, ...]


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


def read_project_version(pyproject_file: Path) -> str:
    with pyproject_file.open("rb") as stream:
        document = tomllib.load(stream)
    try:
        version = document["project"]["version"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"missing [project].version in {pyproject_file}") from exc
    if not isinstance(version, str):
        raise RuntimeError(f"invalid [project].version in {pyproject_file}")
    parse_version_tuple(version)
    return version


def _canonical_manifest_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("manifest path must be a non-empty relative POSIX path")
    if (
        "\\" in value
        or "//" in value
        or value.startswith("/")
        or re.match(r"^[A-Za-z]:", value)
    ):
        raise RuntimeError(f"manifest path is not canonical: {value!r}")
    path = PurePosixPath(value)
    if any(part in ("", ".", "..") for part in path.parts):
        raise RuntimeError(f"manifest path is not a safe relative path: {value!r}")
    if path.as_posix() != value or value == RELEASE_MANIFEST_NAME:
        raise RuntimeError(f"manifest path is not canonical: {value!r}")
    return value


def read_release_manifest(skill_root: Path) -> ReleaseManifest:
    manifest_file = skill_root / RELEASE_MANIFEST_NAME
    try:
        document = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read release manifest: {manifest_file}") from exc
    if not isinstance(document, dict) or set(document) != {
        "format_version",
        "release_version",
        "files",
    }:
        raise RuntimeError("release manifest schema has unexpected fields")
    if document["format_version"] != RELEASE_MANIFEST_FORMAT_VERSION:
        raise RuntimeError("unsupported release manifest format version")
    release_version = document["release_version"]
    if not isinstance(release_version, str):
        raise RuntimeError("release manifest version must be a string")
    try:
        parse_version_tuple(release_version)
    except ValueError as exc:
        raise RuntimeError("invalid release manifest version") from exc
    raw_files = document["files"]
    if not isinstance(raw_files, list):
        raise RuntimeError("release manifest files must be a list")
    files: list[ReleaseFile] = []
    paths: list[str] = []
    folded_paths: set[str] = set()
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {"path", "sha256"}:
            raise RuntimeError("release manifest file schema has unexpected fields")
        path = _canonical_manifest_path(raw_entry["path"])
        digest = raw_entry["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"invalid SHA-256 hash for manifest path {path!r}")
        folded = path.casefold()
        if path in paths or folded in folded_paths:
            raise RuntimeError(f"duplicate or case-colliding manifest path: {path!r}")
        paths.append(path)
        folded_paths.add(folded)
        files.append(ReleaseFile(path=path, sha256=digest))
    if paths != sorted(paths):
        raise RuntimeError("release manifest paths are not in sorted order")
    return ReleaseManifest(
        format_version=RELEASE_MANIFEST_FORMAT_VERSION,
        release_version=release_version,
        files=tuple(files),
    )


def read_project_versions(repo_root: Path) -> ProjectVersions:
    skill_root = repo_root / SKILL_NAME
    skill_version = read_skill_version(skill_root / "SKILL.md")
    if skill_version is None:
        raise RuntimeError(f"missing version in {skill_root / 'SKILL.md'}")
    package_init = skill_root / "rtd-config-cli-py" / "rtd_config" / "__init__.py"
    return ProjectVersions(
        project=read_project_version(repo_root / "pyproject.toml"),
        skill=skill_version,
        launcher_header=read_launcher_header_version(skill_root / "__main__.py"),
        package_header=read_launcher_header_version(package_init),
        package=read_package_version(package_init),
        manifest=read_release_manifest(skill_root).release_version,
    )


def require_consistent_project_versions(versions: ProjectVersions) -> str:
    unique_versions = {
        versions.project,
        versions.skill,
        versions.launcher_header,
        versions.package_header,
        versions.package,
        versions.manifest,
    }
    if len(unique_versions) != 1:
        raise RuntimeError(
            "project version mismatch: "
            f"pyproject.toml={versions.project}, "
            f"SKILL.md={versions.skill}, "
            f"launcher={versions.launcher_header}, "
            f"package_header={versions.package_header}, "
            f"package={versions.package}, "
            f"manifest={versions.manifest}"
        )
    parse_version_tuple(versions.project)
    return versions.project


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


def _is_ignored_runtime_artifact(relative: PurePosixPath) -> bool:
    return (
        "__pycache__" in relative.parts
        or relative.suffix in {".pyc", ".pyo"}
    )


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return path.is_symlink()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag)


def _payload_files(root: Path) -> set[str]:
    if _is_link_or_reparse(root):
        raise RuntimeError(f"release payload root is a symlink or reparse point: {root}")
    files: set[str] = set()
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*directory_names, *file_names):
            candidate = current_path / name
            if _is_link_or_reparse(candidate):
                raise RuntimeError(
                    f"release payload contains a symlink or reparse point: {candidate}"
                )
        for name in file_names:
            relative = (current_path / name).relative_to(root)
            posix = PurePosixPath(*relative.parts)
            if posix.as_posix() == RELEASE_MANIFEST_NAME:
                continue
            if _is_ignored_runtime_artifact(posix):
                continue
            files.add(posix.as_posix())
    return files


def verify_release_payload(root: Path, manifest: ReleaseManifest) -> None:
    manifest_file = root / RELEASE_MANIFEST_NAME
    if not manifest_file.is_file() or _is_link_or_reparse(manifest_file):
        raise RuntimeError(f"release manifest is missing or linked: {manifest_file}")
    declared = {entry.path for entry in manifest.files}
    actual = _payload_files(root)
    missing = sorted(declared - actual)
    extra = sorted(actual - declared)
    if missing or extra:
        raise RuntimeError(
            "release payload file-set drift: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )
    for entry in manifest.files:
        candidate = root.joinpath(*PurePosixPath(entry.path).parts)
        if not candidate.is_file() or _is_link_or_reparse(candidate):
            raise RuntimeError(f"manifest file is missing or linked: {entry.path}")
        actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_digest != entry.sha256:
            raise RuntimeError(
                f"release payload hash mismatch for {entry.path}: "
                f"expected {entry.sha256}, got {actual_digest}"
            )


def build_release_manifest(
    skill_root: Path,
    release_version: str,
    paths: tuple[str, ...] | list[str] | None = None,
) -> ReleaseManifest:
    parse_version_tuple(release_version)
    actual = _payload_files(skill_root)
    selected = sorted(actual if paths is None else paths)
    if set(selected) != actual or len(selected) != len(set(selected)):
        raise RuntimeError(
            "release boundary differs from the eligible source payload: "
            f"missing={sorted(actual - set(selected)) or 'none'}, "
            f"extra={sorted(set(selected) - actual) or 'none'}"
        )
    files = tuple(
        ReleaseFile(
            path=_canonical_manifest_path(relative),
            sha256=hashlib.sha256(
                skill_root.joinpath(*PurePosixPath(relative).parts).read_bytes()
            ).hexdigest(),
        )
        for relative in selected
    )
    return ReleaseManifest(
        format_version=RELEASE_MANIFEST_FORMAT_VERSION,
        release_version=release_version,
        files=files,
    )


def release_manifest_bytes(manifest: ReleaseManifest) -> bytes:
    document = {
        "format_version": manifest.format_version,
        "release_version": manifest.release_version,
        "files": [
            {"path": entry.path, "sha256": entry.sha256}
            for entry in manifest.files
        ],
    }
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_release_manifest(skill_root: Path, manifest: ReleaseManifest) -> Path:
    destination = skill_root / RELEASE_MANIFEST_NAME
    destination.write_bytes(release_manifest_bytes(manifest))
    return destination


def installed_payload_complete(destination: Path) -> bool:
    return all((destination / item).exists() for item in SKILL_PAYLOAD_ITEMS) and all(
        (destination / required_file).is_file()
        for required_file in SKILL_PAYLOAD_REQUIRED_FILES
    )


def should_deploy(
    source_version: str,
    destination: Path,
    source_manifest: ReleaseManifest | None = None,
) -> tuple[bool, str]:
    installed_version = read_skill_version(destination / "SKILL.md")
    if installed_version is None:
        return True, "installed_skill_or_version_missing"
    if not installed_payload_complete(destination):
        return True, "installed_payload_incomplete"
    if parse_version_tuple(installed_version) < parse_version_tuple(source_version):
        return True, "installed_version_is_older"
    if parse_version_tuple(installed_version) == parse_version_tuple(source_version):
        if source_manifest is not None:
            try:
                installed_manifest = read_release_manifest(destination)
                if installed_manifest != source_manifest:
                    return True, "installed_payload_drift"
                verify_release_payload(destination, installed_manifest)
            except RuntimeError:
                return True, "installed_payload_drift"
    return False, "installed_version_is_current_or_newer"


# Windows transiently locks freshly-created/copied directory trees — antivirus,
# Defender, and the Search indexer open handles for a few hundred milliseconds —
# and rmtree/rename then fail with WinError 5 (access denied) or 32 (sharing
# violation); a just-deleted directory name can also linger in a pending-delete
# state, so renaming onto it fails until the FS settles. Retrying with a short
# backoff clears these races without masking a genuine, persistent failure.
_FS_RETRY_ATTEMPTS = 10
_FS_RETRY_DELAY_S = 0.1
_DEPLOYMENT_LOCK_TIMEOUT_S = 10.0
_DEPLOYMENT_LOCK_STALE_S = 300.0


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


def path_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def transaction_path(destination: Path, role: str) -> Path:
    return destination.parent / f".{destination.name}.{role}.{uuid.uuid4().hex}"


def remove_path_best_effort(path: Path) -> None:
    try:
        remove_path(path)
    except OSError:
        pass


@contextmanager
def deployment_lock(destination: Path):
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    lock = parent / f".{destination.name}.deploy.lock"
    deadline = time.monotonic() + _DEPLOYMENT_LOCK_TIMEOUT_S

    while True:
        try:
            lock.mkdir()
            (lock / "owner.txt").write_text(
                f"pid={os.getpid()}\nstarted={time.time():.6f}\n",
                encoding="utf-8",
            )
            break
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > _DEPLOYMENT_LOCK_STALE_S
            except OSError:
                stale = False
            if stale:
                remove_path_best_effort(lock)
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"another deployment is already updating {destination}"
                )
            time.sleep(_FS_RETRY_DELAY_S)

    try:
        yield
    finally:
        remove_path_best_effort(lock)


def recover_interrupted_publish(destination: Path) -> None:
    if path_present(destination):
        return

    parent = destination.parent
    legacy_previous = parent / f".{destination.name}.previous"
    candidates = []
    if path_present(legacy_previous):
        candidates.append(legacy_previous)
    candidates.extend(
        candidate
        for candidate in parent.glob(f".{destination.name}.previous.*")
        if path_present(candidate)
    )
    if not candidates:
        return
    if len(candidates) != 1:
        raise RuntimeError(
            f"cannot recover interrupted deployment for {destination}; "
            f"multiple rollback candidates exist"
        )
    _retry_fs(lambda: candidates[0].rename(destination))


def copy_released_payload(
    source_skill_root: Path,
    destination: Path,
    manifest: ReleaseManifest | None = None,
) -> None:
    if manifest is not None:
        verify_release_payload(source_skill_root, manifest)
    with deployment_lock(destination):
        recover_interrupted_publish(destination)
        staging = transaction_path(destination, "deploying")
        previous = transaction_path(destination, "previous")
        staging.mkdir()

        moved_previous = False
        try:
            if manifest is None:
                # Kept for transaction-focused callers that construct a minimal
                # synthetic payload. Production deployment always supplies the
                # committed manifest and therefore uses the strict allowlist.
                for item in SKILL_PAYLOAD_ITEMS:
                    source = source_skill_root / item
                    target = staging / item
                    if source.is_dir():
                        shutil.copytree(source, target)
                    else:
                        shutil.copy2(source, target)
                if not installed_payload_complete(staging):
                    raise RuntimeError(
                        f"staged Skill payload is incomplete: {source_skill_root}"
                    )
            else:
                for entry in manifest.files:
                    relative = PurePosixPath(entry.path)
                    source = source_skill_root.joinpath(*relative.parts)
                    target = staging.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                shutil.copy2(
                    source_skill_root / RELEASE_MANIFEST_NAME,
                    staging / RELEASE_MANIFEST_NAME,
                )
                staged_manifest = read_release_manifest(staging)
                if staged_manifest != manifest:
                    raise RuntimeError("staged Skill release manifest drifted during copy")
                verify_release_payload(staging, staged_manifest)

            if path_present(destination):
                _retry_fs(lambda: destination.rename(previous))
                moved_previous = True
            _retry_fs(lambda: staging.rename(destination))
        except BaseException:
            if moved_previous and path_present(previous) and not path_present(destination):
                _retry_fs(lambda: previous.rename(destination))
            remove_path_best_effort(staging)
            raise
        remove_path(previous)


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
    with deployment_lock(destination):
        if destination.exists() and destination.resolve() == source:
            return "installed_link_is_current"
        candidate = transaction_path(destination, "linking")
        previous = transaction_path(destination, "previous")
        moved_previous = False
        try:
            candidate.symlink_to(source, target_is_directory=True)
            if path_present(destination):
                _retry_fs(lambda: destination.rename(previous))
                moved_previous = True
            _retry_fs(lambda: candidate.rename(destination))
        except OSError as exc:
            if moved_previous and path_present(previous) and not path_present(destination):
                _retry_fs(lambda: previous.rename(destination))
            remove_path_best_effort(candidate)
            message = "failed to create directory symlink"
            if sys.platform == "win32":
                message += "; enable Developer Mode or run from an elevated shell"
            raise RuntimeError(message) from exc
        remove_path(previous)
        return "symlink_to_canonical_skill"


def deploy_canonical(repo_root: Path, target_project: Path) -> DeployResult:
    repo_root = repo_root.resolve()
    source_skill_root = repo_root / SKILL_NAME
    if not source_skill_root.is_dir():
        raise RuntimeError(f"source skill not found: {source_skill_root}")

    source_version = require_consistent_project_versions(read_project_versions(repo_root))
    source_manifest = read_release_manifest(source_skill_root)
    verify_release_payload(source_skill_root, source_manifest)
    skills_dir = resolve_agent_skills_dir(target_project, CANONICAL_AGENT)
    destination = skills_dir / SKILL_NAME
    should_copy, reason = should_deploy(source_version, destination, source_manifest)
    if not should_copy:
        return DeployResult(
            agent=CANONICAL_AGENT,
            action="skipped",
            version=source_version,
            destination=destination,
            reason=reason,
        )

    copy_released_payload(source_skill_root, destination, source_manifest)
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
