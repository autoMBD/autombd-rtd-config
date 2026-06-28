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
# File:        deploy_agent_env.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-25
# Version:     0.2.0
# Description: Deterministically deploy project-level Agent discipline assets.
# =================================================================================

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Iterable


SUPPORTED_PLATFORMS = ("codex", "claude", "opencode")
ALLOWED_FIELDS = frozenset({"name", "description", "tools", "model"})
KNOWN_TOOLS = frozenset(
    {"Read", "Edit", "Write", "Bash", "Grep", "Glob", "WebFetch"}
)
OPEN_CODE_TOOL_MAP = {
    "Read": "read",
    "Edit": "edit",
    "Write": "edit",
    "Bash": "bash",
    "Grep": "grep",
    "Glob": "glob",
    "WebFetch": "webfetch",
}
LEGACY_AGENT_NAMES = ("explorer", "worker", "tester", "reviewer")


class AgentTemplateError(ValueError):
    """Raised when a canonical Claude agent template violates its contract."""


class AgentDeploymentError(RuntimeError):
    """Raised when deployment cannot safely produce the requested environment."""


@dataclass(frozen=True)
class ClaudeAgentTemplate:
    name: str
    description: str
    tools: tuple[str, ...]
    model: str
    body: str
    source_text: str
    newline: str


@dataclass(frozen=True)
class DeploymentReport:
    skill_links: int
    agent_files_written: int
    agent_files_unchanged: int
    removed_legacy: tuple[str, ...]
    cache_updated: bool


def _split_template(text: str) -> tuple[list[str], str, str]:
    if text.startswith("\ufeff"):
        raise AgentTemplateError("UTF-8 BOM is not allowed in a canonical template")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise AgentTemplateError("template must begin with an exact '---' delimiter")
    closing = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.rstrip("\r\n") == "---"
        ),
        None,
    )
    if closing is None:
        raise AgentTemplateError("template is missing its closing '---' delimiter")
    frontmatter = [line.rstrip("\r\n") for line in lines[1:closing]]
    raw_body = "".join(lines[closing + 1 :])
    if raw_body.startswith(newline):
        raw_body = raw_body[len(newline) :]
    if not raw_body.strip():
        raise AgentTemplateError("template Markdown body must not be empty")
    return frontmatter, raw_body, newline


def parse_claude_agent(text: str) -> ClaudeAgentTemplate:
    frontmatter_lines, body, newline = _split_template(text)
    values: dict[str, str] = {}
    for line in frontmatter_lines:
        if not line.strip():
            continue
        if line[:1].isspace() or ":" not in line:
            raise AgentTemplateError(
                f"unsupported nested or malformed frontmatter line: {line!r}"
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key not in ALLOWED_FIELDS:
            raise AgentTemplateError(f"unsupported frontmatter field: {key}")
        if key in values:
            raise AgentTemplateError(f"duplicate frontmatter field: {key}")
        if not value:
            raise AgentTemplateError(f"frontmatter field must not be empty: {key}")
        values[key] = value

    missing = ALLOWED_FIELDS.difference(values)
    if missing:
        raise AgentTemplateError(
            "missing required frontmatter fields: " + ", ".join(sorted(missing))
        )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", values["name"]):
        raise AgentTemplateError(f"invalid agent name: {values['name']!r}")
    tools = tuple(part.strip() for part in values["tools"].split(","))
    if not all(tools) or len(set(tools)) != len(tools):
        raise AgentTemplateError("tools must be a unique comma-separated list")
    return ClaudeAgentTemplate(
        name=values["name"],
        description=values["description"],
        tools=tools,
        model=values["model"],
        body=body,
        source_text=text,
        newline=newline,
    )


def render_claude_agent(template: ClaudeAgentTemplate) -> str:
    return template.source_text


def _validated_tool_permissions(template: ClaudeAgentTemplate) -> tuple[str, ...]:
    unknown = sorted(set(template.tools).difference(KNOWN_TOOLS))
    if unknown:
        raise AgentTemplateError("unknown Claude tools: " + ", ".join(unknown))
    permissions: list[str] = []
    for tool in template.tools:
        permission = OPEN_CODE_TOOL_MAP[tool]
        if permission not in permissions:
            permissions.append(permission)
    return tuple(permissions)


def render_opencode_agent(template: ClaudeAgentTemplate) -> str:
    permissions = _validated_tool_permissions(template)
    nl = template.newline
    description = json.dumps(template.description, ensure_ascii=False)
    lines = [
        "---",
        f"description: {description}",
        "mode: subagent",
        "permission:",
        '  "*": deny',
        *(f"  {permission}: allow" for permission in permissions),
        "---",
        "",
    ]
    return nl.join(lines) + template.body


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_codex_agent(template: ClaudeAgentTemplate) -> str:
    _validated_tool_permissions(template)
    sandbox_mode = (
        "workspace-write"
        if {"Edit", "Write"}.intersection(template.tools)
        else "read-only"
    )
    content = "\n".join(
        (
            f"name = {_toml_string(template.name)}",
            f"description = {_toml_string(template.description)}",
            f"developer_instructions = {_toml_string(template.body)}",
            f"sandbox_mode = {_toml_string(sandbox_mode)}",
            "",
        )
    )
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise AgentTemplateError(
            f"generated Codex TOML is invalid for {template.name}: {exc}"
        ) from exc
    return content


def skill_target_roots(platforms: Iterable[str]) -> tuple[Path, ...]:
    selected = tuple(platforms)
    roots: list[Path] = []
    if "claude" in selected:
        roots.append(Path(".claude/skills"))
    if "codex" in selected or (
        "opencode" in selected and "claude" not in selected
    ):
        roots.append(Path(".agents/skills"))
    return tuple(dict.fromkeys(roots))


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except (FileNotFoundError, OSError):
        return False


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_junction(path: Path) -> bool:
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def ensure_directory_link(source: Path, destination: Path) -> str:
    source = source.resolve(strict=True)
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise AgentDeploymentError(f"Skill source lacks SKILL.md: {source}")
    if destination.exists() or destination.is_symlink():
        is_link = destination.is_symlink() or _is_junction(destination)
        if is_link and _same_path(destination, source):
            return "unchanged"
        kind = "wrong link" if is_link else "ordinary path"
        raise AgentDeploymentError(
            f"Skill destination is an {kind}, refusing replacement: {destination}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.symlink_to(source, target_is_directory=True)
    except OSError as symlink_error:
        if os.name != "nt":
            raise AgentDeploymentError(
                f"failed to create Skill symlink {destination}: {symlink_error}"
            ) from symlink_error
        command = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/c",
            "mklink",
            "/J",
            str(destination),
            str(source),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise AgentDeploymentError(
                f"failed to create Skill symlink or junction {destination}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            ) from symlink_error
    if not _same_path(destination, source):
        raise AgentDeploymentError(
            f"created Skill link does not resolve to its source: {destination}"
        )
    return "created"


def atomic_write_if_changed(path: Path, content: str) -> bool:
    encoded = content.encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return True


def _assert_within_repo(repo_root: Path, path: Path) -> Path:
    root = repo_root.resolve(strict=True)
    # Use a lexical absolute path here. Resolving the final component would
    # follow a Skill symlink/junction and make cleanup delete its source.
    candidate = Path(os.path.abspath(path))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AgentDeploymentError(
            f"refusing path outside repository: {candidate}"
        ) from exc
    resolved_parent = candidate.parent.resolve(strict=False)
    try:
        resolved_parent.relative_to(root)
    except ValueError as exc:
        raise AgentDeploymentError(
            "refusing managed path whose parent resolves outside repository: "
            f"{candidate} -> {resolved_parent}"
        ) from exc
    if candidate == root:
        raise AgentDeploymentError(f"refusing repository-root mutation: {candidate}")
    return candidate


def _remove_path(repo_root: Path, path: Path) -> bool:
    path = _assert_within_repo(repo_root, path)
    if not (path.exists() or path.is_symlink()):
        return False
    if _is_junction(path):
        path.rmdir()
    elif path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        raise AgentDeploymentError(f"unsupported reset target: {path}")
    return True


def _remove_parent_if_empty(path: Path) -> None:
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def _render_outputs(
    repo_root: Path, platforms: tuple[str, ...]
) -> tuple[dict[Path, str], dict[str, ClaudeAgentTemplate]]:
    source_dir = repo_root / "agent-discipline/subagents"
    if not source_dir.is_dir():
        raise AgentDeploymentError(f"missing canonical subagent directory: {source_dir}")
    templates: dict[str, ClaudeAgentTemplate] = {}
    outputs: dict[Path, str] = {}
    for source in sorted(source_dir.glob("*.md")):
        template = parse_claude_agent(source.read_bytes().decode("utf-8"))
        if template.name in templates:
            raise AgentTemplateError(f"duplicate canonical agent name: {template.name}")
        templates[template.name] = template
        if "claude" in platforms:
            outputs[repo_root / ".claude/agents" / f"{template.name}.md"] = (
                render_claude_agent(template)
            )
        if "opencode" in platforms:
            outputs[repo_root / ".opencode/agents" / f"{template.name}.md"] = (
                render_opencode_agent(template)
            )
        if "codex" in platforms:
            outputs[repo_root / ".codex/agents" / f"{template.name}.toml"] = (
                render_codex_agent(template)
            )
    if not templates:
        raise AgentDeploymentError("no canonical subagent templates found")
    return outputs, templates


def _skill_name_from_manifest(skill_dir: Path) -> str:
    manifest = skill_dir / "SKILL.md"
    if not manifest.is_file():
        raise AgentDeploymentError(f"Skill source lacks SKILL.md: {skill_dir}")
    text = manifest.read_text(encoding="utf-8-sig")
    match = re.search(r"(?m)^name:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$", text)
    if not match:
        raise AgentDeploymentError(f"Skill manifest lacks a valid name: {manifest}")
    name = match.group(1)
    if name != skill_dir.name:
        raise AgentDeploymentError(
            f"Skill name {name!r} does not match directory {skill_dir.name!r}"
        )
    return name


def _collect_skill_sources(
    repo_root: Path, config: dict[str, Any]
) -> tuple[dict[str, Path], dict[str, Path]]:
    canonical_root = repo_root / "agent-discipline/skills"
    if not canonical_root.is_dir():
        raise AgentDeploymentError(f"missing canonical Skill directory: {canonical_root}")
    canonical: dict[str, Path] = {}
    for source in sorted(canonical_root.iterdir()):
        if source.is_dir() and (source / "SKILL.md").is_file():
            name = _skill_name_from_manifest(source)
            canonical[name] = source.resolve(strict=True)
    if not canonical:
        raise AgentDeploymentError("no canonical Agent-discipline Skills found")

    combined = dict(canonical)
    local_spec = config.get("local_skill_import")
    if local_spec is not None:
        if config.get("import_skills") is not None:
            raise AgentDeploymentError(
                "local_skill_import and legacy import_skills cannot be combined"
            )
        if not isinstance(local_spec, dict):
            raise AgentDeploymentError("local_skill_import must be an object")
        raw_roots = local_spec.get("roots")
        selected = local_spec.get("selected")
        if not isinstance(raw_roots, list) or not raw_roots:
            raise AgentDeploymentError(
                "local_skill_import.roots must be a non-empty list"
            )
        if not isinstance(selected, list) or not selected:
            raise AgentDeploymentError(
                "local_skill_import requires at least one selected Skill"
            )
        roots: list[Path] = []
        for raw_root in raw_roots:
            root = Path(str(raw_root)).expanduser().resolve(strict=False)
            if not root.is_dir():
                raise AgentDeploymentError(
                    f"local Skill root is not a directory: {root}"
                )
            if root not in roots:
                roots.append(root)

        selected_names: dict[str, Path] = {}
        for entry in selected:
            if not isinstance(entry, dict):
                raise AgentDeploymentError(
                    "local_skill_import.selected entries must be objects"
                )
            submitted_name = str(entry.get("name", "")).strip()
            raw_source = str(entry.get("source", "")).strip()
            if not submitted_name or not raw_source:
                raise AgentDeploymentError(
                    "selected local Skill requires name and source"
                )
            source = Path(raw_source).expanduser().resolve(strict=False)
            if not source.is_dir():
                raise AgentDeploymentError(
                    f"selected Skill source is not a directory: {source}"
                )
            if not any(
                _path_is_within(source, root)
                for root in roots
            ):
                raise AgentDeploymentError(
                    f"selected Skill source is outside submitted roots: {source}"
                )
            actual_name = _skill_name_from_manifest(source)
            if submitted_name != actual_name:
                raise AgentDeploymentError(
                    f"selected Skill name {submitted_name!r} does not match "
                    f"manifest {actual_name!r}"
                )
            previous = selected_names.get(actual_name)
            if previous is not None and not _same_path(previous, source):
                raise AgentDeploymentError(
                    f"duplicate Skill name {actual_name!r}: {previous} and {source}"
                )
            selected_names[actual_name] = source.resolve(strict=True)
            existing = combined.get(actual_name)
            if existing is not None and not _same_path(existing, source):
                raise AgentDeploymentError(
                    f"duplicate Skill name {actual_name!r}: {existing} and {source}"
                )
            combined[actual_name] = source.resolve(strict=True)
        return canonical, combined

    import_spec = config.get("import_skills")
    if import_spec is None:
        return canonical, combined
    if not isinstance(import_spec, dict):
        raise AgentDeploymentError("import_skills must be an object")
    import_type = import_spec.get("type")
    if import_type == "online":
        url = str(import_spec.get("url", "")).strip()
        raise AgentDeploymentError(
            "online Skill import requires explicit external installation before "
            f"deployment: {url or '<missing URL>'}"
        )
    if import_type != "local":
        raise AgentDeploymentError(f"unsupported Skill import type: {import_type!r}")
    import_root = Path(str(import_spec.get("path", ""))).expanduser().resolve(
        strict=False
    )
    if not import_root.is_dir():
        raise AgentDeploymentError(
            f"local Skill import path is not a directory: {import_root}"
        )
    for manifest in sorted(import_root.rglob("SKILL.md")):
        source = manifest.parent.resolve(strict=True)
        name = _skill_name_from_manifest(source)
        existing = combined.get(name)
        if existing is not None and not _same_path(existing, source):
            raise AgentDeploymentError(
                f"duplicate Skill name {name!r}: {existing} and {source}"
            )
        combined[name] = source
    return canonical, combined


def _reset_selected(repo_root: Path, platforms: tuple[str, ...]) -> None:
    targets: list[Path] = []
    if "claude" in platforms:
        targets.extend((repo_root / ".claude/skills", repo_root / ".claude/agents"))
    if "opencode" in platforms:
        targets.append(repo_root / ".opencode/agents")
    if "codex" in platforms:
        targets.extend((repo_root / ".agents/skills", repo_root / ".codex/agents"))
    targets.append(repo_root / ".agent-state")
    for target in targets:
        _remove_path(repo_root, target)


def _remove_legacy(
    repo_root: Path,
    platforms: tuple[str, ...],
    skill_sources: dict[str, Path],
) -> tuple[str, ...]:
    removed: list[str] = []
    if "codex" in platforms:
        parent = repo_root / ".agents/agents"
        for name in LEGACY_AGENT_NAMES:
            target = parent / f"{name}.md"
            if _remove_path(repo_root, target):
                removed.append(target.relative_to(repo_root).as_posix())
        _remove_parent_if_empty(parent)

    if "opencode" in platforms:
        parent = repo_root / ".opencode/skills"
        for name, source in skill_sources.items():
            target = parent / name
            if (target.exists() or target.is_symlink()) and _same_path(target, source):
                _remove_path(repo_root, target)
                removed.append(target.relative_to(repo_root).as_posix())
        _remove_parent_if_empty(parent)
    return tuple(removed)


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "updated_at": "", "items": {}}
    try:
        cache = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentDeploymentError(f"invalid dependency cache {path}: {exc}") from exc
    if cache.get("version") != 1 or not isinstance(cache.get("items"), dict):
        raise AgentDeploymentError(f"unsupported dependency cache shape: {path}")
    return cache


def _update_cache(
    repo_root: Path, config: dict[str, Any], verified_by: str
) -> bool:
    cache_path = repo_root / ".agent-state/external-dependencies.json"
    cache = _load_cache(cache_path)
    now = datetime.now(timezone.utc).isoformat()
    changed = False
    for input_key, item_key in (("s32ds_path", "env.s32ds"), ("rtd_path", "env.rtd")):
        raw_location = str(config.get(input_key, "")).strip()
        if not raw_location:
            continue
        location = Path(raw_location).expanduser().resolve(strict=False)
        if not location.is_dir():
            raise AgentDeploymentError(
                f"provided dependency path is not a usable directory: {location}"
            )
        entry = {
            "kind": "env",
            "status": "available",
            "location": location.as_posix(),
            "evidence": (
                "User provided during Agent discipline initialization; "
                "the exact directory exists."
            ),
            "verified_at": now,
            "verified_by": verified_by,
        }
        if cache["items"].get(item_key) != entry:
            cache["items"][item_key] = entry
            changed = True
    if changed or not cache_path.is_file():
        cache["updated_at"] = now
        atomic_write_if_changed(
            cache_path, json.dumps(cache, indent=2, ensure_ascii=False) + "\n"
        )
        return True
    return False


def _preflight_dependency_cache(repo_root: Path, config: dict[str, Any]) -> None:
    for input_key in ("s32ds_path", "rtd_path"):
        raw_location = str(config.get(input_key, "")).strip()
        if raw_location and not Path(raw_location).expanduser().resolve(
            strict=False
        ).is_dir():
            raise AgentDeploymentError(
                "provided dependency path is not a usable directory: "
                f"{raw_location}"
            )
    if config.get("mode") == "update":
        _load_cache(repo_root / ".agent-state/external-dependencies.json")


def _verify_outputs(
    repo_root: Path,
    platforms: tuple[str, ...],
    outputs: dict[Path, str],
    skill_sources: dict[str, Path],
) -> None:
    for relative_root in skill_target_roots(platforms):
        for name, source in skill_sources.items():
            target = repo_root / relative_root / name
            is_link = target.is_symlink() or _is_junction(target)
            if (
                not is_link
                or not _same_path(target, source)
                or not (target / "SKILL.md").is_file()
            ):
                raise AgentDeploymentError(f"Skill link verification failed: {target}")
    for path, content in outputs.items():
        if not path.is_file() or path.read_bytes() != content.encode("utf-8"):
            raise AgentDeploymentError(f"generated agent verification failed: {path}")
        if path.suffix == ".toml":
            tomllib.loads(path.read_text(encoding="utf-8"))
    if "opencode" in platforms:
        for name, source in skill_sources.items():
            legacy = repo_root / ".opencode/skills" / name
            if (legacy.exists() or legacy.is_symlink()) and _same_path(legacy, source):
                raise AgentDeploymentError(f"obsolete OpenCode Skill link remains: {legacy}")


def _validate_config(config: dict[str, Any]) -> tuple[str, ...]:
    platforms_raw = config.get("platforms")
    if not isinstance(platforms_raw, list) or not platforms_raw:
        raise AgentDeploymentError("platforms must be a non-empty list")
    platforms = tuple(str(value) for value in platforms_raw)
    unknown = sorted(set(platforms).difference(SUPPORTED_PLATFORMS))
    if unknown:
        raise AgentDeploymentError("unsupported platforms: " + ", ".join(unknown))
    if len(set(platforms)) != len(platforms):
        raise AgentDeploymentError("platforms must not contain duplicates")
    mode = config.get("mode")
    if mode not in ("update", "reset"):
        raise AgentDeploymentError("mode must be 'update' or 'reset'")
    if mode == "reset" and config.get("reset_confirmed") is not True:
        raise AgentDeploymentError("reset requires reset_confirmed=true")
    return platforms


def deploy(
    repo_root: Path,
    config: dict[str, Any],
    *,
    verified_by: str = "agent-initializer",
) -> DeploymentReport:
    repo_root = repo_root.resolve(strict=True)
    platforms = _validate_config(config)
    outputs, _templates = _render_outputs(repo_root, platforms)
    canonical_skill_sources, skill_sources = _collect_skill_sources(repo_root, config)

    managed_skill_roots = tuple(
        (repo_root / relative_root).resolve(strict=False)
        for relative_root in skill_target_roots(platforms)
    )
    for name, source in skill_sources.items():
        canonical_source = canonical_skill_sources.get(name)
        if canonical_source is not None and _same_path(source, canonical_source):
            continue
        if any(_path_is_within(source, root) for root in managed_skill_roots):
            raise AgentDeploymentError(
                f"local Skill source is inside managed Skill root: {source}"
            )

    # Validate every destination boundary before the first mutation. Parent
    # resolution catches a managed directory that is itself linked outside.
    managed_destinations = [
        *outputs,
        repo_root / ".agent-state/external-dependencies.json",
    ]
    for relative_root in skill_target_roots(platforms):
        managed_destinations.extend(
            repo_root / relative_root / name for name in skill_sources
        )
    for destination in managed_destinations:
        _assert_within_repo(repo_root, destination)
        if destination in outputs and (
            destination.is_symlink()
            or _is_junction(destination)
            or (destination.exists() and not destination.is_file())
        ):
            raise AgentDeploymentError(
                f"generated agent target must be a regular file: {destination}"
            )
    _preflight_dependency_cache(repo_root, config)

    if config["mode"] == "reset":
        _reset_selected(repo_root, platforms)

    skill_links = 0
    for relative_root in skill_target_roots(platforms):
        for name, source in skill_sources.items():
            ensure_directory_link(source, repo_root / relative_root / name)
            skill_links += 1

    written = 0
    unchanged = 0
    for path, content in outputs.items():
        if atomic_write_if_changed(path, content):
            written += 1
        else:
            unchanged += 1

    removed_legacy = _remove_legacy(
        repo_root, platforms, canonical_skill_sources
    )
    cache_updated = _update_cache(repo_root, config, verified_by)
    _verify_outputs(repo_root, platforms, outputs, skill_sources)
    return DeploymentReport(
        skill_links=skill_links,
        agent_files_written=written,
        agent_files_unchanged=unchanged,
        removed_legacy=removed_legacy,
        cache_updated=cache_updated,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deploy native project-level Agent discipline assets."
    )
    parser.add_argument("--input", required=True, help="Initialization input JSON")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root (default: current directory)"
    )
    parser.add_argument(
        "--verified-by", default="agent-initializer", help="Cache evidence author"
    )
    return parser


def _load_and_validate_collector_input(path: str) -> dict[str, Any]:
    try:
        from init_agent_env import load_input_file, validate_input
    except ModuleNotFoundError:
        collector_path = Path(__file__).with_name("init_agent_env.py")
        spec = importlib.util.spec_from_file_location("init_agent_env", collector_path)
        if spec is None or spec.loader is None:
            raise AgentDeploymentError(
                f"cannot load initialization collector from {collector_path}"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        load_input_file = module.load_input_file
        validate_input = module.validate_input

    config = load_input_file(path)
    errors = validate_input(config)
    if errors:
        raise AgentDeploymentError("invalid initialization input: " + "; ".join(errors))
    return config


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _load_and_validate_collector_input(args.input)
        report = deploy(
            Path(args.repo_root), config, verified_by=args.verified_by
        )
    except (AgentDeploymentError, AgentTemplateError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
