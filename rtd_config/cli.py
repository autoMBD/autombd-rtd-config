# rtd_config/cli.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .config import RuntimeConfig
from .backends.s32_mex.document import MexDocument
from .backends.s32_mex.locate import find_single_mex
from .resources.pins import pin_options


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

    return parser


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
        "rtd_version": config.rtd_version,
        "mex_file": str(mex),
        "modules": modules,
        "validation_profile": f"{config.family}/{config.rtd_version}",
    })


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "pin-options":
        return cmd_pin_options(args)

    if args.command == "inspect":
        return cmd_inspect(args)

    if args.version:
        return emit({
            "status": "passed",
            "command": "version",
            "tool": "RTD CfgFile CLI",
            "version": __version__,
        })

    parser.print_help()
    return 0
