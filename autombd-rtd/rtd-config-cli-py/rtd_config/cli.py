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
from .modules.basenxp import BaseNxpProvider
from .modules.mcl import MclProvider
from .modules.mcu import McuProvider
from .modules.port import PortProvider
from .modules.dio import DioProvider
from .checks.static import run_static_checks
from .backends.s32_mex.apply import apply_uart_set, apply_uart_add_flexio_channel, apply_platform_set, apply_basenxp_set, apply_mcl_set, apply_port_set, apply_dio_set, apply_mcu_set
from .backends.s32_mex.validation import find_s32ds_root, probe_which_root, run_validation


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
    uart_set.add_argument("--hw", required=False)
    # RTD 7.0.1 has no polling async-method value; interrupt and DMA are supported.
    uart_set.add_argument("--mode", default="interrupt", choices=["interrupt", "dma"])
    uart_set.add_argument("--baud", type=int, default=115200)
    uart_set.add_argument("--tx")
    uart_set.add_argument("--rx")
    uart_set.add_argument("--using", choices=["LPUART_IP", "FLEXIO_IP"])
    uart_set.add_argument("--channel-id", type=int)
    uart_set.add_argument("--callback")
    # LPUART frame parameters (mapped to Uart.xdm enums via uart.json)
    uart_set.add_argument(
        "--parity", choices=["none", "even", "odd"],
        help="Parity: none (disabled), even, or odd. Maps to UartParityType enum.",
    )
    uart_set.add_argument(
        "--stop-bits", dest="stop_bits", choices=["1", "2"],
        help="Stop bits: 1 or 2. Maps to UartStopBitNumber enum.",
    )
    uart_set.add_argument(
        "--word-length", dest="word_length", choices=["7", "8", "9", "10"], type=str,
        help="Word length in bits: 7, 8, 9, or 10. Maps to UartWordLength enum.",
    )
    uart_set.add_argument(
        "--priority", type=int,
        help="ISR priority for the Platform interrupt entry (default 2).",
    )
    uart_set.add_argument("--configure", action="store_true")
    uart_set.add_argument("--backup", action="store_true")
    uart_set.add_argument("--json", action="store_true")

    uart_add_flexio = uart_actions.add_parser(
        "add-flexio-channel",
        help=(
            "Create a FlexIO UART Tx+Rx channel pair (RTD-MEX-UART-002). "
            "Inserts 2 MCL FlexIO logic channels and 2 Uart FlexIO channels "
            "with the given communication parameters and callback. "
            "The shared FLEXIO_IRQn/MCL_FLEXIO_ISR Platform ISR and "
            "FLEXIO_CLK Mcu clock reference are ensured (idempotent)."
        ),
    )
    uart_add_flexio.add_argument("--project", required=True)
    uart_add_flexio.add_argument(
        "--baud", type=int, default=921600,
        help="Desired baud rate (default: 921600). Maps to FLEXIO_UART_BAUDRATE_<baud>.",
    )
    uart_add_flexio.add_argument(
        "--word-length", dest="word_length", type=int, default=8, choices=[8],
        help="Word length in bits (default: 8). Only 8-bit is supported by FlexIO UART.",
    )
    uart_add_flexio.add_argument(
        "--mode", default="interrupt", choices=["interrupt"],
        help="Driver mode (default: interrupt). Only interrupt mode is supported.",
    )
    uart_add_flexio.add_argument(
        "--callback",
        help="Callback function name for UartCallback[0], e.g. Autombd_UartCallback.",
    )
    uart_add_flexio.add_argument(
        "--tx-name", dest="tx_name", default="UART2_TX",
        help="Name for the TX MCL/Uart channel (default: UART2_TX).",
    )
    uart_add_flexio.add_argument(
        "--rx-name", dest="rx_name", default="UART2_RX",
        help="Name for the RX MCL/Uart channel (default: UART2_RX).",
    )
    uart_add_flexio.add_argument("--configure", action="store_true")
    uart_add_flexio.add_argument("--backup", action="store_true")
    uart_add_flexio.add_argument("--json", action="store_true")

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

    basenxp_parser = subparsers.add_parser("basenxp")
    basenxp_actions = basenxp_parser.add_subparsers(dest="action")
    basenxp_set = basenxp_actions.add_parser("set")
    basenxp_set.add_argument("--project", required=True)
    basenxp_set.add_argument(
        "--enable-system-timer",
        action="store_true",
        help="Enable OsIf system timer and insert one OsIfCounterConfig_0 counter.",
    )
    basenxp_set.add_argument("--configure", action="store_true")
    basenxp_set.add_argument("--backup", action="store_true")
    basenxp_set.add_argument("--json", action="store_true")

    mcl_parser = subparsers.add_parser("mcl")
    mcl_actions = mcl_parser.add_subparsers(dest="action")
    mcl_set = mcl_actions.add_parser("set")
    mcl_set.add_argument("--project", required=True)
    mcl_set.add_argument(
        "--add-flexio-logic-channel",
        metavar="NAME",
        help=(
            "Append a new FlexIO logic channel with the given name to "
            "FlexioMclLogicChannels. Next-available CHANNEL_N and PIN_N ids "
            "are computed dynamically (uniqueness enforced per Mcl.xdm)."
        ),
    )
    mcl_set.add_argument("--configure", action="store_true")
    mcl_set.add_argument("--backup", action="store_true")
    mcl_set.add_argument("--json", action="store_true")

    port_parser = subparsers.add_parser("port")
    port_actions = port_parser.add_subparsers(dest="action")
    port_set = port_actions.add_parser("set")
    port_set.add_argument("--project", required=True)
    port_set.add_argument(
        "--peripheral",
        required=True,
        help="Peripheral whose TX/RX pins to configure, e.g. LPUART_0.",
    )
    port_set.add_argument("--tx", metavar="PIN", help="TX pin signal name, e.g. PTA27.")
    port_set.add_argument("--rx", metavar="PIN", help="RX pin signal name, e.g. PTA28.")
    port_set.add_argument("--configure", action="store_true")
    port_set.add_argument("--backup", action="store_true")
    port_set.add_argument("--json", action="store_true")

    dio_parser = subparsers.add_parser("dio")
    dio_actions = dio_parser.add_subparsers(dest="action")
    dio_set = dio_actions.add_parser("set")
    dio_set.add_argument("--project", required=True)
    dio_set.add_argument(
        "--add-channel",
        metavar="NAME",
        help=(
            "Add a DioChannel with the given symbolic name, e.g. LED_CTRL. "
            "Requires --pin to specify the GPIO pad."
        ),
    )
    dio_set.add_argument(
        "--pin",
        metavar="PIN",
        help="GPIO pad to assign, e.g. PTA5. Must be a free GPIO pin.",
    )
    dio_set.add_argument(
        "--direction",
        default="output",
        choices=["output"],
        help="Pin direction (default: output). Only 'output' is currently supported.",
    )
    dio_set.add_argument("--configure", action="store_true")
    dio_set.add_argument("--backup", action="store_true")
    dio_set.add_argument("--json", action="store_true")

    mcu_parser = subparsers.add_parser("mcu")
    mcu_actions = mcu_parser.add_subparsers(dest="action")
    mcu_set = mcu_actions.add_parser("set")
    mcu_set.add_argument("--project", required=True)
    mcu_set.add_argument(
        "--core-clk",
        type=int,
        metavar="MHZ",
        help="Target CORE_CLK frequency in MHz (e.g. 160).",
    )
    mcu_set.add_argument(
        "--aips-plat-clk",
        type=int,
        metavar="MHZ",
        help="Target AIPS_PLAT_CLK frequency in MHz (e.g. 80).",
    )
    mcu_set.add_argument(
        "--aips-slow-clk",
        type=int,
        metavar="MHZ",
        help="Target AIPS_SLOW_CLK frequency in MHz (e.g. 40).",
    )
    mcu_set.add_argument(
        "--add-all-clock-reference-points",
        action="store_true",
        help=(
            "Preserve existing reference points and add entries for all "
            "selectable S32K344 clocks not already present by name."
        ),
    )
    mcu_set.add_argument("--configure", action="store_true")
    mcu_set.add_argument("--backup", action="store_true")
    mcu_set.add_argument("--json", action="store_true")

    return parser


def normalize_uart_intent(args: argparse.Namespace) -> Intent:
    """Normalize `uart set` CLI arguments into the stable JSON intent contract.

    Shortcut commands and JSON intents converge on this same Intent so the
    plan/apply/check pipeline has a single request shape.

    CLI -> payload mapping for frame parameters (grounded in uart.json enum domains):
      --parity none/even/odd  -> word_length via parity_cli_to_enum
      --stop-bits 1/2         -> stop_bits via stop_bits_cli_to_enum
      --word-length 7/8/9/10  -> word_length via word_length_cli_to_enum
      --priority N            -> priority (ISR priority, default 2)
    """
    from rtd_config.backends.s32_mex.apply import _load_uart_asset

    payload: dict = {
        "hw": args.hw or "",
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

    # Map frame parameters to their .mex enum values via the uart.json asset.
    asset = _load_uart_asset()
    enums = asset.get("enum_domains", {})

    parity = getattr(args, "parity", None)
    if parity is not None:
        parity_map = enums.get("parity_cli_to_enum", {})
        payload["parity"] = parity_map.get(parity, parity)

    stop_bits = getattr(args, "stop_bits", None)
    if stop_bits is not None:
        sb_map = enums.get("stop_bits_cli_to_enum", {})
        payload["stop_bits"] = sb_map.get(stop_bits, stop_bits)

    word_length = getattr(args, "word_length", None)
    if word_length is not None:
        wl_map = enums.get("word_length_cli_to_enum", {})
        payload["word_length"] = wl_map.get(str(word_length), word_length)

    priority = getattr(args, "priority", None)
    if priority is not None:
        payload["priority"] = priority

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

    root = find_s32ds_root(args.s32ds_root)
    if root is None:
        # Check whether s32dsc.exe was found on PATH but its root was invalid
        # (e.g. the K3 PlatformSDK directory is missing). Surface the probed
        # path as a breadcrumb so the user knows where to look.
        _which_root = probe_which_root()
        _which_breadcrumb = (
            f"s32dsc.exe was found at {_which_root / 'eclipse' / 's32dsc.exe'} "
            f"but the derived root ({_which_root}) is incomplete (missing "
            f"S32DS/software/PlatformSDK_S32K3). Check that the full S32DS "
            f"package is installed, or provide the correct path explicitly."
            if _which_root is not None
            else ""
        )
        return emit({
            "status": "blocked",
            "command": "validate",
            "diagnostics": [
                {
                    "severity": "blocker",
                    "code": "s32ds_root_not_configured",
                    "module": "backend",
                    "message": (
                        "S32DS root could not be found. Auto-discovery was attempted "
                        "(PATH search via s32dsc.exe, and standard C:\\NXP\\S32DS* "
                        "installs). Provide the location via --s32ds-root <path> or "
                        "set the RTD_CONFIG_S32DS_ROOT environment variable."
                    ),
                    "details": {
                        "probed_which_root": (
                            str(_which_root) if _which_root is not None else None
                        ),
                        "breadcrumb": _which_breadcrumb or None,
                    },
                }
            ],
            "runtime_verification": {"static_check": static_result.to_dict()},
        })

    # Flow B uses a throwaway -data workspace; only honour an explicit override.
    workspace = Path(args.workspace) if args.workspace else None
    sdk_path = Path(args.sdk_path) if args.sdk_path else None
    outcome = run_validation(
        config.project,
        root,
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


def normalize_uart_add_flexio_intent(args: argparse.Namespace) -> Intent:
    """Normalize `uart add-flexio-channel` CLI arguments into the JSON intent contract."""
    payload: dict = {
        "baud": args.baud,
        "word_length": args.word_length,
        "mode": args.mode,
    }
    if args.callback is not None:
        payload["callback"] = args.callback
    if getattr(args, "tx_name", None):
        payload["tx_name"] = args.tx_name
    if getattr(args, "rx_name", None):
        payload["rx_name"] = args.rx_name
    return Intent.from_dict({"module": "uart", "action": "add_flexio_channel", "payload": payload})


def cmd_uart_add_flexio_channel(args: argparse.Namespace) -> int:
    intent = normalize_uart_add_flexio_intent(args)
    plan = UartProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_uart_add_flexio_channel)


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


def normalize_basenxp_intent(args: argparse.Namespace) -> Intent:
    """Normalize `basenxp set` CLI arguments into the JSON intent contract."""
    payload: dict = {}
    if args.enable_system_timer:
        payload["enable_system_timer"] = True
    return Intent.from_dict({"module": "basenxp", "action": "set", "payload": payload})


def cmd_basenxp_set(args: argparse.Namespace) -> int:
    intent = normalize_basenxp_intent(args)
    plan = BaseNxpProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_basenxp_set)


def normalize_mcl_intent(args: argparse.Namespace) -> Intent:
    """Normalize `mcl set` CLI arguments into the JSON intent contract."""
    payload: dict = {}
    channel = getattr(args, "add_flexio_logic_channel", None)
    if channel:
        payload["add_flexio_logic_channel"] = channel
    return Intent.from_dict({"module": "mcl", "action": "set", "payload": payload})


def cmd_mcl_set(args: argparse.Namespace) -> int:
    intent = normalize_mcl_intent(args)
    plan = MclProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_mcl_set)


def normalize_port_intent(args: argparse.Namespace) -> Intent:
    """Normalize `port set` CLI arguments into the JSON intent contract."""
    payload: dict = {}
    if args.peripheral:
        payload["peripheral"] = args.peripheral
    pins: dict = {}
    if args.tx:
        pins["tx"] = args.tx
    if args.rx:
        pins["rx"] = args.rx
    if pins:
        payload["pins"] = pins
    return Intent.from_dict({"module": "port", "action": "set", "payload": payload})


def cmd_port_set(args: argparse.Namespace) -> int:
    intent = normalize_port_intent(args)
    plan = PortProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_port_set)


def normalize_dio_intent(args: argparse.Namespace) -> Intent:
    """Normalize `dio set` CLI arguments into the JSON intent contract."""
    payload: dict = {}
    add_channel = getattr(args, "add_channel", None)
    if add_channel:
        payload["add_channel"] = add_channel
    pin = getattr(args, "pin", None)
    if pin:
        payload["pin"] = pin
    direction = getattr(args, "direction", "output")
    if direction:
        payload["direction"] = direction
    return Intent.from_dict({"module": "dio", "action": "set", "payload": payload})


def normalize_mcu_intent(args: argparse.Namespace) -> Intent:
    """Normalize `mcu set` CLI arguments into the JSON intent contract."""
    payload: dict = {}
    core_clk = getattr(args, "core_clk", None)
    if core_clk is not None:
        payload["core_clk"] = core_clk
    aips_plat_clk = getattr(args, "aips_plat_clk", None)
    if aips_plat_clk is not None:
        payload["aips_plat_clk"] = aips_plat_clk
    aips_slow_clk = getattr(args, "aips_slow_clk", None)
    if aips_slow_clk is not None:
        payload["aips_slow_clk"] = aips_slow_clk
    add_all = getattr(args, "add_all_clock_reference_points", False)
    if add_all:
        payload["add_all_clock_reference_points"] = True
    return Intent.from_dict({"module": "mcu", "action": "set", "payload": payload})


def cmd_dio_set(args: argparse.Namespace) -> int:
    intent = normalize_dio_intent(args)
    plan = DioProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_dio_set)


def cmd_mcu_set(args: argparse.Namespace) -> int:
    intent = normalize_mcu_intent(args)
    plan = McuProvider().plan(intent)

    if not args.configure:
        return emit({
            "status": "passed",
            "command": "plan",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
        })

    return _configure_module(args, intent, plan, apply_mcu_set)


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

    if args.command == "uart" and getattr(args, "action", None) == "add-flexio-channel":
        return cmd_uart_add_flexio_channel(args)

    if args.command == "platform" and getattr(args, "action", None) == "set":
        return cmd_platform_set(args)

    if args.command == "basenxp" and getattr(args, "action", None) == "set":
        return cmd_basenxp_set(args)

    if args.command == "mcl" and getattr(args, "action", None) == "set":
        return cmd_mcl_set(args)

    if args.command == "port" and getattr(args, "action", None) == "set":
        return cmd_port_set(args)

    if args.command == "dio" and getattr(args, "action", None) == "set":
        return cmd_dio_set(args)

    if args.command == "mcu" and getattr(args, "action", None) == "set":
        return cmd_mcu_set(args)

    if args.version:
        return emit({
            "status": "passed",
            "command": "version",
            "tool": "RTD CfgFile CLI",
            "version": __version__,
        })

    parser.print_help()
    return 0
