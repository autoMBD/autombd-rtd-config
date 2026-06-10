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
# File:        cli.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Command-line entry point: argument parsing and command dispatch.
# =================================================================================

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import __version__
from .config import RuntimeConfig
from .backends.s32_mex.document import MexDocument
from .backends.s32_mex.locate import find_single_mex
from .resources.pins import pin_options
from .intent import Intent
from .modules.uart import UartProvider
from .modules.platform import PlatformProvider
from .checks.static import run_static_checks
from .backends.s32_mex.apply import apply_uart_set, apply_platform_set
from .backends.s32_mex.validation import run_validation


# Skill root, used to resolve committed runtime assets independently of cwd.
# This file lives at autombd-rtd/rtd-config-cli-py/rtd_config/cli.py, so
# parents[2] is the skill root (autombd-rtd/) that owns assets/.
SKILL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_ROOT = SKILL_ROOT / "assets"


def emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtd-config")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    pin_options_parser = subparsers.add_parser("pin-options")
    pin_options_parser.add_argument("--device", default="s32k344")
    pin_options_parser.add_argument("--package", default="default")
    pin_options_parser.add_argument("--peripheral", required=True)
    pin_options_parser.add_argument("--json", action="store_true")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--project", required=True)
    inspect_parser.add_argument("--json", action="store_true")

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--project", required=True)
    check_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--project", required=True)
    validate_parser.add_argument("--s32ds-root")
    validate_parser.add_argument("--workspace")
    validate_parser.add_argument("--sdk-path")
    validate_parser.add_argument("--json", action="store_true")

    uart_parser = subparsers.add_parser("uart")
    uart_actions = uart_parser.add_subparsers(dest="action")
    uart_set = uart_actions.add_parser("set")
    uart_set.add_argument("--project", required=True)
    uart_set.add_argument("--hw", required=True)
    # RTD 7.0.1 has no polling async-method value; M1 supports interrupt only
    # (DMA is reserved for a later milestone).
    uart_set.add_argument("--mode", default="interrupt", choices=["interrupt"])
    uart_set.add_argument("--baud", type=int, default=115200)
    uart_set.add_argument("--tx")
    uart_set.add_argument("--rx")
    uart_set.add_argument("--using", choices=["LPUART_IP", "FLEXIO_IP"])
    uart_set.add_argument("--channel-id", type=int)
    uart_set.add_argument("--callback")
    uart_set.add_argument("--configure", action="store_true")
    uart_set.add_argument("--backup", action="store_true")
    uart_set.add_argument("--json", action="store_true")

    platform_parser = subparsers.add_parser("platform")
    platform_actions = platform_parser.add_subparsers(dest="action")
    platform_set = platform_actions.add_parser("set")
    platform_set.add_argument("--project", required=True)
    # Target an existing interrupt by peripheral (e.g. LPUART_3) or exact IsrName.
    platform_set.add_argument("--peripheral")
    platform_set.add_argument("--isr-name")
    platform_set.add_argument("--priority", type=int)
    platform_set.add_argument("--configure", action="store_true")
    platform_set.add_argument("--backup", action="store_true")
    platform_set.add_argument("--json", action="store_true")

    return parser


def normalize_uart_intent(args: argparse.Namespace) -> Intent:
    """Normalize `uart set` CLI arguments into the stable JSON intent contract.

    Shortcut commands and JSON intents converge on this same Intent so the
    plan/apply/check pipeline has a single request shape.
    """
    payload: dict = {
        "hw": args.hw,
        "mode": args.mode,
        "baud": args.baud,
    }
    pins: dict = {}
    if args.tx:
        pins["tx"] = args.tx
    if args.rx:
        pins["rx"] = args.rx
    if pins:
        payload["pins"] = pins
    if args.using:
        payload["using"] = args.using
    if args.channel_id is not None:
        payload["channel_id"] = args.channel_id
    if args.callback is not None:
        payload["callback"] = args.callback
    return Intent.from_dict({"module": "uart", "action": "set", "payload": payload})


def cmd_pin_options(args: argparse.Namespace) -> int:
    options = pin_options(
        data_root=DEFAULT_ASSET_ROOT,
        device=args.device,
        package=args.package,
        peripheral=args.peripheral,
    )
    return emit({
        "status": "passed",
        "command": "pin-options",
        "options": options,
    })


def cmd_inspect(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    mex = find_single_mex(config.project)
    doc = MexDocument.load(mex)
    modules = sorted(doc.enabled_instance_names())
    return emit({
        "status": "passed",
        "command": "inspect",
        "backend": config.backend,
        "family": config.family,
        "device": config.device,
        "package": config.package,
        "rtd_version": config.rtd_version,
        "mex_file": str(mex),
        "modules": modules,
        "validation_profile": f"{config.family}/{config.rtd_version}",
    })


def cmd_check(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    mex = find_single_mex(config.project)
    result = run_static_checks(mex)
    return emit(result.to_dict())


def _intent_dict(intent: Intent) -> dict:
    return {
        "module": intent.module,
        "action": intent.action,
        "payload": intent.payload,
    }


def cmd_validate(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    mex = find_single_mex(config.project)

    # Static check always runs first; vendor validation never substitutes for it.
    static_result = run_static_checks(mex)

    s32ds_root = args.s32ds_root or os.environ.get("RTD_CONFIG_S32DS_ROOT")
    if not s32ds_root:
        return emit({
            "status": "blocked",
            "command": "validate",
            "diagnostics": [
                {
                    "severity": "blocker",
                    "code": "s32ds_root_not_configured",
                    "module": "backend",
                    "message": (
                        "S32DS root is not configured; set --s32ds-root or "
                        "RTD_CONFIG_S32DS_ROOT to run headless ConfigTools validation."
                    ),
                    "details": {},
                }
            ],
            "runtime_verification": {"static_check": static_result.to_dict()},
        })

    # Flow B uses a throwaway -data workspace; only honour an explicit override.
    workspace = Path(args.workspace) if args.workspace else None
    sdk_path = Path(args.sdk_path) if args.sdk_path else None
    outcome = run_validation(
        config.project,
        Path(s32ds_root),
        workspace=workspace,
        sdk_path=sdk_path,
        timeout_s=config.validation_timeout_s,
    )
    # Vendor pass requires ConfigTools exit 0 AND no SEVERE [TOOL] config
    # problem; exit 0 alone is not sufficient. Static check must also pass.
    status = "passed" if outcome.passed and static_result.status == "passed" else "blocked"
    return emit({
        "status": status,
        "command": "validate",
        "runtime_verification": {"static_check": static_result.to_dict()},
        "validation": {
            "exit_code": outcome.exit_code,
            "passed": outcome.passed,
            "generated_files": outcome.generated_files,
            "severe_problems": outcome.severe_problems,
            "command": outcome.command,
            "log_path": outcome.log_path,
        },
    })


def cmd_uart_set(args: argparse.Namespace) -> int:
    intent = normalize_uart_intent(args)
    plan = UartProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_uart_set)


def _configure_module(args: argparse.Namespace, intent: Intent, plan, apply_fn) -> int:
    """Shared configure pipeline: apply an owned edit, write, then static-check.

    ``apply_fn(doc, intent) -> ApplyResult`` is the module's localized backend
    edit. The pipeline is module-agnostic; per-module specifics live in the
    intent payload and the apply function.
    """
    config = RuntimeConfig.from_dict({"project": args.project})
    mex = find_single_mex(config.project)
    doc = MexDocument.load(mex)

    apply_result = apply_fn(doc, intent)
    if apply_result.blocked:
        return emit({
            "status": "blocked",
            "command": "configure",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
            "changed_modules": apply_result.changed_modules,
            "diagnostics": [d.to_dict() for d in apply_result.diagnostics],
        })

    # Optional safety backup of the original .mex before writing. Default
    # behaviour creates no backup.
    if args.backup:
        backup = mex.with_name(mex.name + ".bak")
        backup.write_bytes(mex.read_bytes())

    doc.write(mex)

    # Runtime verification: static check runs first on the written file. We pass
    # the in-memory document (now identical to disk) so the quick_selection
    # conflict check can inspect the exact elements we modified, while
    # well-formedness is still re-read from the written path.
    static_result = run_static_checks(
        mex,
        doc=doc,
        modified_elements=apply_result.modified_elements,
        requested_callback=intent.payload.get("callback"),
    )

    diagnostics = apply_result.diagnostics + static_result.diagnostics
    status = "passed" if static_result.status == "passed" else "blocked"
    return emit({
        "status": status,
        "command": "configure",
        "normalized_intent": _intent_dict(intent),
        "plan": plan.to_dict(),
        "changed_modules": apply_result.changed_modules,
        "diagnostics": [d.to_dict() for d in diagnostics],
        "runtime_verification": {
            "static_check": static_result.to_dict(),
        },
    })


def normalize_platform_intent(args: argparse.Namespace) -> Intent:
    """Normalize `platform set` CLI arguments into the JSON intent contract."""
    payload: dict = {}
    if args.peripheral:
        payload["peripheral"] = args.peripheral
    if args.isr_name:
        payload["isr_name"] = args.isr_name
    if args.priority is not None:
        payload["priority"] = args.priority
    return Intent.from_dict({"module": "platform", "action": "set", "payload": payload})


def cmd_platform_set(args: argparse.Namespace) -> int:
    intent = normalize_platform_intent(args)
    plan = PlatformProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_platform_set)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "pin-options":
        return cmd_pin_options(args)

    if args.command == "inspect":
        return cmd_inspect(args)

    if args.command == "check":
        return cmd_check(args)

    if args.command == "validate":
        return cmd_validate(args)

    if args.command == "uart" and getattr(args, "action", None) == "set":
        return cmd_uart_set(args)

    if args.command == "platform" and getattr(args, "action", None) == "set":
        return cmd_platform_set(args)

    if args.version:
        return emit({
            "status": "passed",
            "command": "version",
            "tool": "RTD CfgFile CLI",
            "version": __version__,
        })

    parser.print_help()
    return 0
