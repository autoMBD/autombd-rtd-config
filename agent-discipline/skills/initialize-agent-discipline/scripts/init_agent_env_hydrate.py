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
# File:        init_agent_env_hydrate.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Read-only initialization capture and derived checkout hydration.
# =================================================================================

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sys
from typing import Sequence

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE.parents[1] / "agent-workflow/scripts"
for directory in (WORKFLOW, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from workflow_environment import JsonParser
from workflow_environment_io import (EnvironmentError, PLATFORMS, canonical, digest, sha256, fields,
    version, check_hash, strings, fail, root_path, no_links, linked, derived_target,
    inspect_checkout, git, source_state, read_json, relative_path)
import init_agent_env_deploy as deployer


def _assets(directory: Path, *, checkout_text=False) -> dict:
    no_links(directory)
    if not directory.is_dir():
        fail("INITIALIZATION_UNAVAILABLE", "Canonical discipline or selected Skill source is missing.")
    inventory = {}
    for parent, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in (*dirs, *files):
            if linked(Path(parent) / name):
                fail("PATH_BOUNDARY", "Discipline source contains an unsupported linked descendant.")
        for name in sorted(files):
            if name.endswith((".pyc", ".pyo")):
                continue
            path = Path(parent) / name
            raw = path.read_bytes()
            if checkout_text and b"\x00" not in raw:
                try:
                    raw.decode("utf-8")
                except UnicodeError:
                    pass
                else:
                    raw = raw.replace(b"\r\n", b"\n")
            inventory[path.relative_to(directory).as_posix()] = sha256(raw)
    if not inventory:
        fail("INITIALIZATION_UNAVAILABLE", "Discipline or Skill source has no reusable assets.")
    return inventory


def _input(path: Path, expected: str) -> dict:
    check_hash(expected)
    path = Path(path)
    no_links(path)
    if not path.is_file():
        fail("INITIALIZATION_UNAVAILABLE", "Supplied initialization input is missing.")
    if sha256(path.read_bytes()) != expected:
        fail("INVALID_INPUT", "Initialization input digest differs from the trusted expectation.", exit_code=1)
    data = read_json(path)
    if not isinstance(data, dict):
        fail("INVALID_INPUT", "Initialization input must be an object.")
    # Reuse existing collector/deployer validation without invoking the GUI.
    validated = deployer._load_and_validate_collector_input(str(path))
    if validated != data:
        fail("INVALID_INPUT", "Initialization parser interpretations disagree.")
    deployer._validate_config(data)
    return data


def _cache(root: Path, config: dict) -> tuple[dict, bytes]:
    path = root / ".agent-state/external-dependencies.json"
    no_links(path)
    if not path.is_file():
        fail("INITIALIZATION_UNAVAILABLE", "An initialized reusable dependency cache is required.")
    raw = path.read_bytes()
    cache = read_json(path)
    fields(cache, {"version", "updated_at", "items"})
    version(cache["version"])
    if not isinstance(cache["items"], dict) or not isinstance(cache["updated_at"], str):
        fail("INITIALIZATION_UNAVAILABLE", "Dependency cache metadata is invalid.")
    try:
        if datetime.fromisoformat(cache["updated_at"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError
    except ValueError:
        fail("INITIALIZATION_UNAVAILABLE", "Dependency cache has no dated availability evidence.")
    for key, record in cache["items"].items():
        if not isinstance(key, str) or not key.startswith(("env.", "tool.", "source.", "connector.")):
            fail("INITIALIZATION_UNAVAILABLE", "Dependency cache entry identity is invalid.")
        fields(record, {"kind", "status", "location", "evidence", "verified_at", "verified_by"}, {"prepare"})
        if record["status"] not in ("available", "blocked", "unknown", "stale"):
            fail("INITIALIZATION_UNAVAILABLE", "Dependency cache status is unsupported.")
        if any(not isinstance(value, str) or not value.strip() for value in record.values()):
            fail("INITIALIZATION_UNAVAILABLE", "Dependency cache stores only nonempty non-secret metadata strings.")
        try:
            if datetime.fromisoformat(record["verified_at"].replace("Z", "+00:00")).tzinfo is None:
                raise ValueError
        except ValueError:
            fail("INITIALIZATION_UNAVAILABLE", "Dependency cache entry has no dated evidence.")
    for item, key in (("env.s32ds", "s32ds_path"), ("env.rtd", "rtd_path")):
        record = cache["items"].get(item, {})
        if (record.get("status") != "available" or not record.get("location")
                or Path(record["location"]).resolve() != Path(config[key]).resolve()):
            fail("INITIALIZATION_UNAVAILABLE", "Required initialization dependency cache does not match the validated input.")
    python = cache["items"].get("tool.python", {})
    if python.get("status") != "available" or not Path(python.get("location", "")).is_file():
        fail("INITIALIZATION_UNAVAILABLE", "The cached initialization Python interpreter is unavailable.")
    return cache, raw


def capture_initialization(source_root: Path, input_path: Path, *, expected_input_sha256: str) -> dict:
    check_hash(expected_input_sha256)
    try:
        source = root_path(source_root)
        config = _input(input_path, expected_input_sha256)
        platforms = deployer._validate_config(config)
        head = git(source, "rev-parse", "HEAD")
        checkout = inspect_checkout(source, expected_head=head)
        assets = _assets(source / "agent-discipline")
        outputs, _ = deployer._render_outputs(source, platforms)
        canonical_sources, sources = deployer._collect_skill_sources(source, config)
        for output in outputs:
            no_links(output)
        links = {}
        for relative in deployer.skill_target_roots(platforms):
            for name, skill in sources.items():
                target = source / relative / name
                no_links(target, include_leaf=False)
                if not linked(target) or target.resolve(strict=True) != skill.resolve(strict=True):
                    fail("INITIALIZATION_UNAVAILABLE", "Selected platform Skill links do not match their approved sources.")
                links[target.relative_to(source).as_posix()] = str(skill)
        deployer._verify_outputs(source, platforms, outputs, sources)
        cache, raw_cache = _cache(source, config)
        skills = {name: {"root": str(path), "canonical": name in canonical_sources,
                         "assets": _assets(path)} for name, path in sorted(sources.items())}
        return {"version": 1, "source_root": str(source), "source_head": checkout["head"],
                "source_state": source_state(source), "source_assets": assets,
                "input": {"path": str(Path(input_path).resolve(strict=True)), "sha256": expected_input_sha256},
                "platforms": list(platforms), "skills": skills,
                "deployed": {"files": {p.relative_to(source).as_posix(): sha256(p.read_bytes()) for p in outputs},
                             "links": links},
                "cache_sha256": sha256(raw_cache),
                "evidence_origin": "validated-input-and-actual-initialized-source"}
    except (deployer.AgentDeploymentError, deployer.AgentTemplateError, OSError, KeyError) as exc:
        raise EnvironmentError("INITIALIZATION_UNAVAILABLE",
            "Source initialization is missing, stale or invalid; use the existing first-initialization process.") from exc


def hydrate_checkout(source_root: Path, target_root: Path, *, initialization: dict,
                     expected_initialization_sha256: str, allowed_target_base: Path,
                     platforms: Sequence[str], expected_target_head: str) -> dict:
    check_hash(expected_initialization_sha256)
    check_hash(expected_target_head, 40)
    fields(initialization, {"version", "source_root", "source_head", "source_state", "source_assets",
                            "input", "platforms", "skills", "deployed", "cache_sha256", "evidence_origin"})
    version(initialization["version"])
    fields(initialization["input"], {"path", "sha256"})
    if digest(initialization) != expected_initialization_sha256:
        fail("INVALID_INPUT", "Initialization snapshot digest does not match the trusted expectation.", exit_code=1)
    selected = strings(platforms, choices=PLATFORMS, empty=False)
    original = strings(initialization["platforms"], choices=PLATFORMS, empty=False)
    check_hash(initialization["source_head"], 40)
    check_hash(initialization["input"]["sha256"])
    if not isinstance(initialization["input"]["path"], str):
        fail("INVALID_INPUT", "Initialization input locator must be an absolute path.")
    source = root_path(source_root)
    target, base = derived_target(source, target_root, allowed_target_base)
    if str(source) != initialization["source_root"]:
        fail("STALE_IDENTITY", "Hydration source differs from its captured canonical root.")
    # Replay read-only capture only. Even if the original request was reset,
    # neither deploy(reset) nor the original collector/GUI is ever called here.
    try:
        current = capture_initialization(source, Path(initialization["input"]["path"]),
                                         expected_input_sha256=initialization["input"]["sha256"])
    except EnvironmentError as exc:
        if exc.code == "PATH_BOUNDARY":
            raise
        raise EnvironmentError("INITIALIZATION_UNAVAILABLE", "Captured source initialization is no longer valid.") from exc
    if current != initialization:
        fail("INITIALIZATION_UNAVAILABLE", "Captured initialization source, assets or deployed evidence changed.")
    if not set(selected).issubset(original):
        fail("PLATFORM_NOT_APPROVED", "Requested platforms were not selected in the supplied source initialization.")
    inspect_checkout(target, expected_head=expected_target_head)
    # The explicit allowed derived base plus actual source ancestry qualifies
    # an existing checkout. Missing ignored files alone do not trigger first init.
    git(target, "merge-base", "--is-ancestor", initialization["source_head"], expected_target_head)
    target_assets = _assets(target / "agent-discipline")
    if target_assets != initialization["source_assets"]:
        # Git may materialize LF text as CRLF. Permit only that difference on
        # clean, identical Git asset trees; source capture remains raw-byte bound.
        if (_assets(target / "agent-discipline", checkout_text=True) !=
                _assets(source / "agent-discipline", checkout_text=True)):
            fail("STALE_IDENTITY", "Derived checkout discipline content differs from the captured source.")
        if git(target, "ls-tree", "-r", "HEAD", "--", "agent-discipline") != git(source, "ls-tree", "-r", "HEAD", "--", "agent-discipline"):
            fail("STALE_IDENTITY", "Derived checkout has a different canonical asset tree.")
        for checkout in (source, target):
            git(checkout, "diff", "--quiet", "--no-ext-diff", "--no-textconv", "HEAD", "--", "agent-discipline")
    try:
        config = _input(Path(initialization["input"]["path"]), initialization["input"]["sha256"])
        outputs, _ = deployer._render_outputs(target, tuple(selected))
        source_canonical, source_skills = deployer._collect_skill_sources(source, config)
        skills = {name: (target / path.relative_to(source) if name in source_canonical else path)
                  for name, path in source_skills.items()}
        source_cache, cache_bytes = _cache(source, config)
        cache_path = target / ".agent-state/external-dependencies.json"
        links = {target / relative / name: path for relative in deployer.skill_target_roots(selected)
                 for name, path in skills.items()}
        changes = []
        # Validate every file, cache and link destination before any mkdir/write.
        for path in (*outputs, cache_path):
            no_links(path)
            if path.exists() and not path.is_file():
                fail("PATH_BOUNDARY", "Hydration file destination is not a regular file.")
        for path, content in outputs.items():
            expected = content.encode("utf-8")
            if path.exists() and path.read_bytes() != expected:
                fail("INITIALIZATION_UNAVAILABLE", "Existing target Agent bytes differ; hydration never resets them.")
            if not path.exists():
                changes.append(path.relative_to(target).as_posix())
        if cache_path.exists():
            target_cache, _ = _cache(target, config)
            if any(target_cache["items"].get(key) != value for key, value in source_cache["items"].items()):
                fail("INITIALIZATION_UNAVAILABLE", "Existing target cache conflicts with captured source evidence.")
        else:
            changes.append(cache_path.relative_to(target).as_posix())
        for destination, skill in links.items():
            no_links(destination, include_leaf=False)
            expected_assets = initialization["skills"][skill.name]["assets"]
            if skill.name in source_canonical:
                actual_assets = _assets(skill, checkout_text=True)
                expected_assets = _assets(source_skills[skill.name], checkout_text=True)
            else:
                actual_assets = _assets(skill)
            if not skill.is_dir() or actual_assets != expected_assets:
                fail("INITIALIZATION_UNAVAILABLE", "Target-local or approved external Skill source changed.")
            if destination.exists() or linked(destination):
                if not linked(destination) or destination.resolve(strict=True) != skill.resolve(strict=True):
                    fail("PATH_BOUNDARY", "Existing Skill destination does not match the selected source.")
            else:
                changes.append(destination.relative_to(target).as_posix())
        if "opencode" in selected:
            for name, skill in skills.items():
                legacy = target / ".opencode/skills" / name
                no_links(legacy, include_leaf=False)
                if linked(legacy) and legacy.resolve(strict=True) == skill.resolve(strict=True):
                    fail("INITIALIZATION_UNAVAILABLE", "Obsolete target Skill layout requires explicit initialization repair.")
        # No target path was touched before this point.
        for destination, skill in links.items():
            deployer.ensure_directory_link(skill, destination)
        for path, content in outputs.items():
            deployer.atomic_write_if_changed(path, content)
        if not cache_path.exists():
            deployer.atomic_write_if_changed(cache_path, cache_bytes.decode("utf-8"))
        deployer._verify_outputs(target, tuple(selected), outputs, skills)
        _cache(target, config)
        return {"version": 1, "status": "HYDRATED", "platforms": selected, "changed_paths": sorted(changes),
                "source_root": str(source), "target_root": str(target), "head": expected_target_head,
                "initialization_sha256": expected_initialization_sha256,
                "target_assets": target_assets,
                "generated_files": {p.relative_to(target).as_posix(): sha256(p.read_bytes()) for p in outputs}}
    except (deployer.AgentDeploymentError, deployer.AgentTemplateError, OSError, KeyError) as exc:
        raise EnvironmentError("INITIALIZATION_UNAVAILABLE", "Derived discipline preparation or verification failed.") from exc


def main(argv=None) -> int:
    parser = JsonParser(description="Capture initialized discipline or explicitly hydrate a qualified derived checkout.")
    sub = parser.add_subparsers(dest="operation", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--source-root", type=Path, required=True)
    capture.add_argument("--input", type=Path, required=True)
    capture.add_argument("--expected-input-sha256", required=True)
    hydrate = sub.add_parser("hydrate")
    hydrate.add_argument("--source-root", type=Path, required=True)
    hydrate.add_argument("--target-root", type=Path, required=True)
    hydrate.add_argument("--initialization", type=Path, required=True)
    hydrate.add_argument("--expected-initialization-sha256", required=True)
    hydrate.add_argument("--allowed-target-base", type=Path, required=True)
    hydrate.add_argument("--platform", action="append", required=True)
    hydrate.add_argument("--expected-target-head", required=True)
    try:
        args = parser.parse_args(argv)
        if args.operation == "capture":
            read_json(args.input)  # Distinguish CLI input-read failures from operation rejection.
            result = capture_initialization(args.source_root, args.input, expected_input_sha256=args.expected_input_sha256)
        else:
            result = hydrate_checkout(args.source_root, args.target_root, initialization=read_json(args.initialization),
                expected_initialization_sha256=args.expected_initialization_sha256,
                allowed_target_base=args.allowed_target_base, platforms=args.platform,
                expected_target_head=args.expected_target_head)
        sys.stdout.buffer.write(canonical(result))
        return 0
    except EnvironmentError as exc:
        sys.stdout.buffer.write(canonical(exc.as_dict()))
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
