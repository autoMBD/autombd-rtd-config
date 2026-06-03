# rtd_config/cli.py
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
from .checks.static import run_static_checks
from .backends.s32_mex.apply import apply_uart_set
from .backends.s32_mex.validation import run_validation, DEFAULT_WORKSPACE


# Repo root, used to resolve committed runtime assets independently of cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = REPO_ROOT / "data"


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
    uart_set.add_argument("--mode", default="polling", choices=["polling", "interrupt"])
    uart_set.add_argument("--baud", type=int, default=115200)
    uart_set.add_argument("--tx")
    uart_set.add_argument("--rx")
    uart_set.add_argument("--using", choices=["LPUART_IP", "FLEXIO_IP"])
    uart_set.add_argument("--channel-id", type=int)
    uart_set.add_argument("--callback")
    uart_set.add_argument("--configure", action="store_true")
    uart_set.add_argument("--backup", action="store_true")
    uart_set.add_argument("--json", action="store_true")

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
        data_root=DEFAULT_DATA_ROOT,
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

    workspace = Path(args.workspace) if args.workspace else DEFAULT_WORKSPACE
    sdk_path = Path(args.sdk_path) if args.sdk_path else None
    outcome = run_validation(
        config.project,
        Path(s32ds_root),
        workspace=workspace,
        sdk_path=sdk_path,
        timeout_s=config.validation_timeout_s,
    )
    status = "passed" if outcome.exit_code == 0 and static_result.status == "passed" else "blocked"
    return emit({
        "status": status,
        "command": "validate",
        "runtime_verification": {"static_check": static_result.to_dict()},
        "validation": {
            "exit_code": outcome.exit_code,
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

    return _configure_uart(args, intent, plan)


def _configure_uart(args: argparse.Namespace, intent: Intent, plan) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    mex = find_single_mex(config.project)
    doc = MexDocument.load(mex)

    apply_result = apply_uart_set(doc, intent)
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

    if args.version:
        return emit({
            "status": "passed",
            "command": "version",
            "tool": "RTD CfgFile CLI",
            "version": __version__,
        })

    parser.print_help()
    return 0
