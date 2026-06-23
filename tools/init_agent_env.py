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
# File:        init_agent_env.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-23
# Version:     0.1.0
# Description: Unified structured input collector for Agent environment
#              initialization. Runs as an interactive CLI to collect target
#              platforms, operation mode, external dependency paths, and
#              additional skill imports. Outputs deployment-ready JSON to
#              stdout (or a file with --output). Also accepts pre-collected
#              input via --input for non-interactive agent-driven use.
# =================================================================================

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUPPORTED_PLATFORMS = ("codex", "claude", "opencode")

PLATFORM_LABELS: dict[str, str] = {
    "codex": "Codex",
    "claude": "Claude",
    "opencode": "OpenCode",
}

PLATFORM_SKILL_DIRS: dict[str, str] = {
    "codex": ".agents/skills",
    "claude": ".claude/skills",
    "opencode": ".opencode/skills",
}

PLATFORM_AGENT_DIRS: dict[str, str] = {
    "codex": ".agents/agents",
    "claude": ".claude/agents",
    "opencode": ".opencode/agents",
}


def _safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        print("\nInput interrupted.", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)


def _choose_multi(label: str, options: list[str]) -> list[str]:
    print(f"\n{label}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    print(f"  [0] Done / none")

    selected: list[str] = []
    while True:
        raw = _safe_input("Enter number (0 when done): ").strip()
        if raw == "":
            continue
        try:
            n = int(raw)
        except ValueError:
            print(f"  Invalid number: {raw!r}")
            continue
        if n == 0:
            break
        if 1 <= n <= len(options):
            name = options[n - 1]
            if name not in selected:
                selected.append(name)
                print(f"  Added: {name}")
            else:
                print(f"  Already selected: {name}")
        else:
            print(f"  Out of range [1..{len(options)}]")
    return selected


def _choose_one(label: str, options: list[str]) -> str:
    print(f"\n{label}")
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")

    while True:
        raw = _safe_input("Enter number: ").strip()
        try:
            n = int(raw)
        except ValueError:
            print(f"  Invalid number: {raw!r}")
            continue
        if 1 <= n <= len(options):
            return options[n - 1]
        print(f"  Out of range [1..{len(options)}]")


def _choose_yes_no(question: str) -> bool:
    while True:
        raw = _safe_input(f"{question} [y/N]: ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no", ""):
            return False
        print(f"  Please answer y or n.")


def _ask_path(prompt: str) -> str:
    while True:
        raw = _safe_input(f"{prompt}: ").strip().strip("\"'")
        if not raw:
            print("  Path cannot be empty.")
            continue
        p = Path(raw).expanduser()
        if not p.exists():
            if _choose_yes_no(f"  Path does not exist: {p}. Use anyway?"):
                return str(p.resolve())
            continue
        return str(p.resolve())


def _verify_s32ds_root(path: str) -> bool:
    p = Path(path)
    if not p.is_dir():
        return False
    markers = [
        p / "eclipse",
        p / "S32DS",
    ]
    return any(m.is_dir() for m in markers)


def _verify_rtd_root(path: str) -> bool:
    p = Path(path)
    if not p.is_dir():
        return False
    entries = list(p.iterdir())
    rtd_packages = [e for e in entries if e.is_dir() and "_TS_T" in e.name]
    return len(rtd_packages) > 0


def _ask_import_skills() -> dict[str, Any] | None:
    print("\n--- Additional Skills Import ---")
    choice = _choose_one(
        "Import additional skills?",
        [
            "Skip — do not import additional skills",
            "Import from local directory",
            "Install from online source",
        ],
    )
    if "Skip" in choice:
        return None

    result: dict[str, Any] = {}

    if "local" in choice:
        local = _ask_path("Local skill directory path")
        result["type"] = "local"
        result["path"] = local
        result["description"] = f"Import skills from local directory: {local}"
    elif "online" in choice:
        url = _safe_input("Online skill source URL: ").strip()
        result["type"] = "online"
        result["url"] = url
        result["description"] = f"Install skills from online source: {url}"

    return result


def run_interactive() -> dict[str, Any]:
    print("=" * 60)
    print("  RTD CfgFile CLI — Agent Environment Initialization")
    print("=" * 60)

    platforms = _choose_multi(
        "Select target Agent platforms (multiple allowed):",
        list(SUPPORTED_PLATFORMS),
    )
    if not platforms:
        print("No platforms selected. Exiting.", file=sys.stderr)
        raise SystemExit(1)

    mode = _choose_one(
        "Select operation mode:",
        [
            "Update — preserve existing environment; change only what is explicitly entered",
            "Reset — clear project-level Agent environment and .agent-state/ for selected platforms, then reinitialize",
        ],
    )

    reset_confirmed = False
    if "Reset" in mode:
        print(f"\n  RESET will clear the following for platforms: {', '.join(platforms)}")
        print(f"    - Skill symlinks and subagent files under project-level directories")
        print(f"    - The entire .agent-state/ cache")
        print(f"  User-level and global Agent environments will NOT be affected.")
        reset_confirmed = _choose_yes_no("  Confirm reset?")
        if not reset_confirmed:
            print("Reset cancelled. Switching to Update mode.")
            mode = "update"

    print("\n--- External Dependencies ---")
    print("S32 Design Studio (S32DS) is a hard prerequisite for RTD CfgFile CLI")
    print("module development. Provide the installation root path.")

    s32ds_path = _ask_path("S32DS installation root")
    if not _verify_s32ds_root(s32ds_path):
        print(f"  WARNING: {s32ds_path} does not appear to be a valid S32DS root.")
        print("  Expected subdirectories: eclipse/, S32DS/")
        if not _choose_yes_no("  Proceed anyway?"):
            print("Aborted by user.", file=sys.stderr)
            raise SystemExit(1)

    print("\nRTD packages are located under the PlatformSDK S32K3 RTD directory.")
    print('Example: C:\\NXP\\S32DS.3.6.7\\S32DS\\software\\PlatformSDK_S32K3\\RTD')

    rtd_path = _ask_path("RTD installation path")
    if not _verify_rtd_root(rtd_path):
        print(f"  WARNING: {rtd_path} does not contain RTD package directories (*_TS_T*).")
        if not _choose_yes_no("  Proceed anyway?"):
            print("Aborted by user.", file=sys.stderr)
            raise SystemExit(1)

    import_skills = _ask_import_skills()

    result: dict[str, Any] = {
        "version": 1,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "platforms": platforms,
        "mode": "update" if "Update" in mode else "reset",
        "reset_confirmed": reset_confirmed,
        "s32ds_path": s32ds_path.replace("\\", "/"),
        "rtd_path": rtd_path.replace("\\", "/"),
    }
    if import_skills is not None:
        result["import_skills"] = import_skills

    return result


def load_input_file(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        print(f"Input file not found: {p}", file=sys.stderr)
        raise SystemExit(1)
    with open(p, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def validate_input(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    platforms = data.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        errors.append("'platforms' must be a non-empty list")
    else:
        unknown = [p for p in platforms if p not in SUPPORTED_PLATFORMS]
        if unknown:
            errors.append(f"Unknown platforms: {unknown}. Supported: {list(SUPPORTED_PLATFORMS)}")

    mode = data.get("mode")
    if mode not in ("update", "reset"):
        errors.append("'mode' must be 'update' or 'reset'")

    if mode == "reset" and not data.get("reset_confirmed", False):
        errors.append("'reset_confirmed' must be true for reset mode")

    if not data.get("s32ds_path"):
        errors.append("'s32ds_path' is required")
    if not data.get("rtd_path"):
        errors.append("'rtd_path' is required")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect structured input for RTD CfgFile CLI Agent environment initialization."
    )
    parser.add_argument(
        "--input",
        type=str,
        metavar="FILE",
        help="Read pre-collected input from JSON file (non-interactive mode)",
    )
    parser.add_argument(
        "--output",
        type=str,
        metavar="FILE",
        help="Write collected input as JSON to file instead of stdout",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing input file without interactive collection (requires --input)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.validate_only:
        if not args.input:
            print("--validate-only requires --input", file=sys.stderr)
            return 2
        data = load_input_file(args.input)
        errors = validate_input(data)
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print("Input is valid.")
        return 0

    if args.input:
        data = load_input_file(args.input)
        errors = validate_input(data)
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            return 1
    else:
        data = run_interactive()

    json_text = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json_text, encoding="utf-8")
        print(f"Input saved to {out}")
    else:
        print(json_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
