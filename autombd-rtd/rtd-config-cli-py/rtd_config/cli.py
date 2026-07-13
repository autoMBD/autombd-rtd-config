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
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from . import __version__
from .config import RuntimeConfig
from .backends.s32_mex.document import MexDocument, MexWriteError
from .backends.s32_mex.metadata import revalidate_project_metadata
from .backends.s32_mex.target import release_for_publish, revalidate_snapshot
from .backends.s32_mex.transaction import ConfigureTransaction
from .project import Project
from .resources.pins import pin_options
from .resources.bundles import AssetBundleResolver
from .intent import Intent
from .modules.uart import UartProvider
from .modules.platform import PlatformProvider
from .modules.basenxp import BaseNxpProvider
from .modules.mcl import MclProvider
from .modules.mcu import McuProvider
from .modules.port import PortProvider
from .modules.dio import DioProvider
from .modules.adc import AdcProvider
from .checks.static import run_static_checks
from .backends.s32_mex.apply import apply_uart_set, apply_uart_add_flexio_channel, apply_platform_set, apply_basenxp_set, apply_mcl_set, apply_port_set, apply_dio_set, apply_mcu_set, apply_adc_set
from .backends.s32_mex.validation import find_s32ds_root, probe_which_root, run_validation
from .diagnostics import Diagnostic, render_failure
from .errors import CliFailure


# Skill root, used to resolve committed runtime assets independently of cwd.
# This file lives at autombd-rtd/rtd-config-cli-py/rtd_config/cli.py, so
# parents[2] is the skill root (autombd-rtd/) that owns assets/.
SKILL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_ROOT = SKILL_ROOT / "assets"
ROOT_COMMANDS = frozenset(
    {
        "pin-options",
        "inspect",
        "check",
        "validate",
        "uart",
        "platform",
        "basenxp",
        "mcl",
        "port",
        "dio",
        "mcu",
        "adc",
    }
)


def emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "passed" else 1


class RaisingArgumentParser(argparse.ArgumentParser):
    """Argument parser whose errors participate in the CLI failure boundary."""

    def error(self, message: str) -> None:
        raise CliFailure(
            code="invalid_arguments",
            message=message,
            module="cli",
            details={"usage": self.format_usage().strip()},
            exit_code=2,
        )


def _parse_bool_token(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on", "enable", "enabled"}:
        return True
    if normalized in {"false", "0", "no", "off", "disable", "disabled"}:
        return False
    raise argparse.ArgumentTypeError(
        "expected a boolean token: true/false, yes/no, on/off, enable/disable"
    )


def _add_spec_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--spec",
        metavar="PATH",
        help=(
            "Path to a module JSON spec. Canonical shape: "
            '{"module":"<module>","action":"set","payload":{...}}. '
            "For compatibility, a raw payload object is also accepted."
        ),
    )


def _load_spec_payload(args: argparse.Namespace, module: str, action: str = "set") -> dict | None:
    spec_path = getattr(args, "spec", None)
    if not spec_path:
        return None

    try:
        raw = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliFailure(
            code="spec_not_found",
            message=f"Spec file does not exist: {spec_path}",
            module=module,
            details={"spec": str(spec_path)},
        ) from exc
    except PermissionError as exc:
        raise CliFailure(
            code="permission_denied",
            message=f"Permission denied while reading spec: {spec_path}",
            module=module,
            details={"spec": str(spec_path)},
        ) from exc
    except UnicodeError as exc:
        raise CliFailure(
            code="spec_invalid",
            message=f"Spec is not valid UTF-8: {spec_path}",
            module=module,
            details={"spec": str(spec_path), "reason": str(exc)},
        ) from exc
    except OSError as exc:
        raise CliFailure(
            code="spec_read_failed",
            message=f"Failed to read spec: {spec_path}",
            module=module,
            details={"spec": str(spec_path), "reason": str(exc)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise CliFailure(
            code="spec_invalid",
            message=f"Spec is not valid JSON: {spec_path}",
            module=module,
            details={"spec": str(spec_path), "line": exc.lineno, "column": exc.colno},
        ) from exc

    if not isinstance(raw, dict):
        raise CliFailure("spec_invalid", "Spec must contain a JSON object.", module=module)

    if "payload" not in raw:
        return raw

    spec_module = raw.get("module")
    if spec_module is not None and spec_module != module:
        raise CliFailure(
            "spec_invalid",
            f"Spec module mismatch: expected {module!r}, got {spec_module!r}.",
            module=module,
        )

    spec_action = raw.get("action")
    if spec_action is not None and spec_action != action:
        raise CliFailure(
            "spec_invalid",
            f"Spec action mismatch: expected {action!r}, got {spec_action!r}.",
            module=module,
        )

    payload = raw["payload"]
    if not isinstance(payload, dict):
        raise CliFailure("spec_invalid", "Spec payload must be a JSON object.", module=module)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = RaisingArgumentParser(prog="rtd-config")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    pin_options_parser = subparsers.add_parser("pin-options")
    pin_options_parser.add_argument("--bundle-id")
    pin_options_parser.add_argument("--vendor")
    pin_options_parser.add_argument("--backend")
    pin_options_parser.add_argument("--family")
    pin_options_parser.add_argument("--device")
    pin_options_parser.add_argument("--package")
    pin_options_parser.add_argument("--rtd-release")
    pin_options_parser.add_argument("--schema")
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
    _add_spec_argument(uart_set)
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
    _add_spec_argument(platform_set)
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
    basenxp_set.add_argument("--user-mode-support", type=_parse_bool_token)
    basenxp_set.add_argument("--dev-error-detect", type=_parse_bool_token)
    basenxp_set.add_argument("--custom-timer", type=_parse_bool_token)
    basenxp_set.add_argument("--get-user-id", choices=("core", "custom", "GET_CORE_ID", "GET_CUSTOM_ID"))
    basenxp_set.add_argument("--instance-id", type=int)
    basenxp_set.add_argument("--get-physical-core-id", type=_parse_bool_token)
    basenxp_set.add_argument("--software-semaphore", type=_parse_bool_token)
    _add_spec_argument(basenxp_set)
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
    _add_spec_argument(mcl_set)
    mcl_set.add_argument("--configure", action="store_true")
    mcl_set.add_argument("--backup", action="store_true")
    mcl_set.add_argument("--json", action="store_true")

    port_parser = subparsers.add_parser("port")
    port_actions = port_parser.add_subparsers(dest="action")
    port_set = port_actions.add_parser("set")
    port_set.add_argument("--project", required=True)
    port_set.add_argument(
        "--peripheral",
        help="Peripheral whose TX/RX pins to configure, e.g. LPUART_0.",
    )
    port_set.add_argument("--tx", metavar="PIN", help="TX pin signal name, e.g. PTA27.")
    port_set.add_argument("--rx", metavar="PIN", help="RX pin signal name, e.g. PTA28.")
    _add_spec_argument(port_set)
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
    _add_spec_argument(dio_set)
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
    _add_spec_argument(mcu_set)
    mcu_set.add_argument("--configure", action="store_true")
    mcu_set.add_argument("--backup", action="store_true")
    mcu_set.add_argument("--json", action="store_true")

    adc_parser = subparsers.add_parser("adc")
    adc_actions = adc_parser.add_subparsers(dest="action")
    adc_set = adc_actions.add_parser(
        "set",
        help=(
            "Configure an ADC Hardware Unit from a JSON --spec: target unit, "
            "transfer mode, per-group sampling time (derived into "
            "AdcSamplingDuration), groups (trigger/access/conv/samples/"
            "notification/channels), and per-channel watchdog thresholds. "
            "One `adc set --spec X --configure` expresses a full case."
        ),
    )
    adc_set.add_argument("--project", required=True)
    _add_spec_argument(adc_set)
    adc_set.add_argument("--configure", action="store_true")
    adc_set.add_argument("--backup", action="store_true")
    adc_set.add_argument("--json", action="store_true")

    return parser


def normalize_uart_intent(args: argparse.Namespace, bundle) -> Intent:
    """Normalize `uart set` CLI arguments into the stable JSON intent contract.

    Shortcut commands and JSON intents converge on this same Intent so the
    plan/apply/check pipeline has a single request shape.

    CLI -> payload mapping for frame parameters (grounded in uart.json enum domains):
      --parity none/even/odd  -> word_length via parity_cli_to_enum
      --stop-bits 1/2         -> stop_bits via stop_bits_cli_to_enum
      --word-length 7/8/9/10  -> word_length via word_length_cli_to_enum
      --priority N            -> priority (ISR priority, default 2)
    """
    spec_payload = _load_spec_payload(args, "uart")
    if spec_payload is not None:
        return Intent.from_dict({"module": "uart", "action": "set", "payload": spec_payload})

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
    asset = bundle.load_json("uart")
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
    selector = {
        "vendor": args.vendor, "backend": args.backend, "family": args.family,
        "device": args.device, "package": args.package,
        "rtd_release": args.rtd_release, "schema_version": args.schema,
    }
    if args.bundle_id is None and any(value is None for value in selector.values()):
        raise CliFailure(
            "invalid_arguments", "Projectless pin-options requires a complete asset selector or --bundle-id.",
            module="cli", exit_code=2,
        )
    bundle = AssetBundleResolver(DEFAULT_ASSET_ROOT).resolve_selector(
        bundle_id=args.bundle_id, **selector
    )
    options = pin_options(bundle=bundle, peripheral=args.peripheral)
    return emit({
        "status": "passed",
        "command": "pin-options",
        "options": options,
    })


def cmd_inspect(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    with Project.verified(config.project, config.backend) as project:
        target = project.verified_target
        _preflight_project(project)
        metadata = project.metadata
        observed = metadata.to_dict()
        observed["module_metadata"] = observed["modules"]
        observed["modules"] = None if metadata.modules is None else [item.name for item in metadata.modules]
        return emit({
            "status": "passed", "command": "inspect", "mex_file": str(target.mex.path),
            "validation_profile": project.asset_bundle.profile_id,
            "compatibility": {
                "status": "passed",
                "diagnostics": [{
                    "severity": "info",
                    "code": "asset_bundle_resolved",
                    "module": "backend",
                    "message": "Exact project asset compatibility is verified.",
                }],
            },
            **observed,
        })


def cmd_check(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    with Project.verified(config.project, config.backend) as project:
        _preflight_project(project)
        revalidate_project_metadata(project.verified_target, project.metadata)
        target = project.verified_target
        result = run_static_checks(
            target.mex.path, doc=project.document,
            verified_target=target, bundle=project.asset_bundle,
        )
        return emit(result.to_dict())


def _intent_dict(intent: Intent) -> dict:
    return {
        "module": intent.module,
        "action": intent.action,
        "payload": intent.payload,
    }


def _preflight_project(project: Project) -> Project:
    """Resolve and cache exact project assets before provider or vendor work."""
    metadata = project.metadata.require_identity()
    project._cache["asset_bundle"] = AssetBundleResolver(DEFAULT_ASSET_ROOT).resolve(metadata)
    return project


def _preflight_plan(args, normalizer, provider_type):
    """Verify observed project identity before module-specific planning."""
    config = RuntimeConfig.from_dict({"project": args.project})
    project = Project.verified(config.project, config.backend)
    try:
        _preflight_project(project)
        bundle = project.asset_bundle
        intent = normalizer(args, bundle)
        return intent, provider_type(bundle).plan(intent), project
    except BaseException:
        project.close()
        raise


def _complete_planned_command(args, intent, plan, apply_fn, project: Project) -> int:
    if not args.configure:
        try:
            return emit({
                "status": "passed",
                "command": "plan",
                "normalized_intent": _intent_dict(intent),
                "plan": plan.to_dict(),
            })
        finally:
            project.close()
    return _configure_module(args, intent, plan, apply_fn, project=project)


def cmd_validate(args: argparse.Namespace) -> int:
    config = RuntimeConfig.from_dict({"project": args.project})
    project = Project.verified(config.project, config.backend)
    try:
        _preflight_project(project)
        return _cmd_validate_verified(args, config, project)
    finally:
        project.close()


def _cmd_validate_verified(args, config: RuntimeConfig, project: Project) -> int:
    project.metadata.require_consistent()
    revalidate_project_metadata(project.verified_target, project.metadata)
    target = project.verified_target
    mex = target.mex.path

    # Static check always runs first; vendor validation never substitutes for it.
    static_result = run_static_checks(
        mex, doc=project.document, verified_target=target, bundle=project.asset_bundle
    )
    if static_result.status != "passed":
        return emit({
            "status": "blocked",
            "command": "validate",
            "runtime_verification": {"static_check": static_result.to_dict()},
        })

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
                            _which_root.name if _which_root is not None else None
                        ),
                        "breadcrumb": (
                            "An incomplete S32DS installation was detected."
                            if _which_breadcrumb else None
                        ),
                    },
                }
            ],
            "runtime_verification": {"static_check": static_result.to_dict()},
        })

    # Flow B uses a throwaway -data workspace; only honour an explicit override.
    workspace = Path(args.workspace) if args.workspace else None
    sdk_path = Path(args.sdk_path) if args.sdk_path else None
    revalidate_snapshot(target)
    revalidate_project_metadata(target, project.metadata)
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
            "process_code": outcome.process_code,
            "timed_out": outcome.timed_out,
            "stdout_truncated": outcome.stdout_truncated,
            "stderr_truncated": outcome.stderr_truncated,
            "cleanup_warnings": outcome.cleanup_warnings,
        },
    })


def cmd_uart_set(args: argparse.Namespace) -> int:
    intent, plan, project = _preflight_plan(args, normalize_uart_intent, UartProvider)
    return _complete_planned_command(args, intent, plan, apply_uart_set, project)


def normalize_uart_add_flexio_intent(args: argparse.Namespace, _bundle) -> Intent:
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
    intent, plan, project = _preflight_plan(args, normalize_uart_add_flexio_intent, UartProvider)
    return _complete_planned_command(
        args, intent, plan, apply_uart_add_flexio_channel, project
    )


def _configure_module(
    args: argparse.Namespace, intent: Intent, plan, apply_fn,
    project: Project | None = None,
) -> int:
    """Shared configure pipeline: apply an owned edit, preflight, then commit.

    ``apply_fn(doc, intent) -> ApplyResult`` is the module's localized backend
    edit. The pipeline is module-agnostic; per-module specifics live in the
    intent payload and the apply function.
    """
    if project is None:
        config = RuntimeConfig.from_dict({"project": args.project})
        project = Project.verified(config.project, config.backend)
        _preflight_project(project)
    try:
        return _configure_verified_project(args, intent, plan, apply_fn, project)
    finally:
        project.close()


def _configure_verified_project(args, intent, plan, apply_fn, project: Project) -> int:
    try:
        transaction_result = ConfigureTransaction(
            project,
            plan=plan,
            backup=args.backup,
            static_runner=run_static_checks,
        ).execute(intent, apply_fn)
        apply_result = transaction_result.apply_result
        static_result = transaction_result.static_result
        diagnostics = list(apply_result.diagnostics)
        if static_result is not None:
            diagnostics.extend(static_result.diagnostics)
        payload = {
            "status": transaction_result.status,
            "command": "configure",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
            "changed_modules": transaction_result.changed_modules,
            "published": transaction_result.published,
            "cleanup_warnings": transaction_result.cleanup_warnings,
            "diagnostics": [d.to_dict() for d in diagnostics],
        }
        if static_result is not None:
            payload["runtime_verification"] = {
                "static_check": static_result.to_dict(),
            }
        return emit(payload)
    except MexWriteError as exc:
        diagnostic = Diagnostic(
            severity="blocker",
            code="narrow_mex_write_unavailable",
            module="backend",
            message=(
                "The pending .mex edit could not be written with the "
                "byte-faithful narrow writer. The original file was left "
                "unchanged."
            ),
            details={"reason": str(exc)},
        )
        return emit({
            "status": "blocked",
            "command": "configure",
            "normalized_intent": _intent_dict(intent),
            "plan": plan.to_dict(),
            "changed_modules": [],
            "diagnostics": [diagnostic.to_dict()],
        })


def normalize_platform_intent(args: argparse.Namespace, _bundle) -> Intent:
    """Normalize `platform set` CLI arguments into the JSON intent contract."""
    spec_payload = _load_spec_payload(args, "platform")
    if spec_payload is not None:
        return Intent.from_dict({"module": "platform", "action": "set", "payload": spec_payload})

    payload: dict = {}
    if args.peripheral:
        payload["peripheral"] = args.peripheral
    if args.isr_name:
        payload["isr_name"] = args.isr_name
    if args.priority is not None:
        payload["priority"] = args.priority
    return Intent.from_dict({"module": "platform", "action": "set", "payload": payload})


def cmd_platform_set(args: argparse.Namespace) -> int:
    intent, plan, project = _preflight_plan(args, normalize_platform_intent, PlatformProvider)
    return _complete_planned_command(args, intent, plan, apply_platform_set, project)


def normalize_basenxp_intent(args: argparse.Namespace, bundle) -> Intent:
    """Normalize `basenxp set` CLI arguments into the JSON intent contract."""
    spec_payload = _load_spec_payload(args, "basenxp")
    if spec_payload is not None:
        return Intent.from_dict({"module": "basenxp", "action": "set", "payload": spec_payload})

    payload: dict = {}
    if args.enable_system_timer:
        payload["enable_system_timer"] = True
    for attr in (
        "user_mode_support",
        "dev_error_detect",
        "custom_timer",
        "instance_id",
        "get_physical_core_id",
        "software_semaphore",
    ):
        value = getattr(args, attr, None)
        if value is not None:
            payload[attr] = value
    get_user_id = getattr(args, "get_user_id", None)
    if get_user_id is not None:
        enum_map = bundle.load_json("basenxp")["cli_enum_map"]["get_user_id"]
        payload["get_user_id"] = enum_map[get_user_id]
    return Intent.from_dict({"module": "basenxp", "action": "set", "payload": payload})


def cmd_basenxp_set(args: argparse.Namespace) -> int:
    intent, plan, project = _preflight_plan(args, normalize_basenxp_intent, BaseNxpProvider)
    return _complete_planned_command(args, intent, plan, apply_basenxp_set, project)


def normalize_mcl_intent(args: argparse.Namespace, _bundle) -> Intent:
    """Normalize `mcl set` CLI arguments into the JSON intent contract."""
    spec_payload = _load_spec_payload(args, "mcl")
    if spec_payload is not None:
        return Intent.from_dict({"module": "mcl", "action": "set", "payload": spec_payload})

    payload: dict = {}
    channel = getattr(args, "add_flexio_logic_channel", None)
    if channel:
        payload["add_flexio_logic_channel"] = channel
    return Intent.from_dict({"module": "mcl", "action": "set", "payload": payload})


def cmd_mcl_set(args: argparse.Namespace) -> int:
    intent, plan, project = _preflight_plan(args, normalize_mcl_intent, MclProvider)
    return _complete_planned_command(args, intent, plan, apply_mcl_set, project)


def normalize_port_intent(args: argparse.Namespace, _bundle) -> Intent:
    """Normalize `port set` CLI arguments into the JSON intent contract."""
    spec_payload = _load_spec_payload(args, "port")
    if spec_payload is not None:
        return Intent.from_dict({"module": "port", "action": "set", "payload": spec_payload})

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
    intent, plan, project = _preflight_plan(args, normalize_port_intent, PortProvider)
    return _complete_planned_command(args, intent, plan, apply_port_set, project)


def normalize_dio_intent(args: argparse.Namespace, _bundle) -> Intent:
    """Normalize `dio set` CLI arguments into the JSON intent contract."""
    spec_payload = _load_spec_payload(args, "dio")
    if spec_payload is not None:
        return Intent.from_dict({"module": "dio", "action": "set", "payload": spec_payload})

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


def normalize_mcu_intent(args: argparse.Namespace, _bundle) -> Intent:
    """Normalize `mcu set` CLI arguments into the JSON intent contract."""
    spec_payload = _load_spec_payload(args, "mcu")
    if spec_payload is not None:
        return Intent.from_dict({"module": "mcu", "action": "set", "payload": spec_payload})

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
    intent, plan, project = _preflight_plan(args, normalize_dio_intent, DioProvider)
    return _complete_planned_command(args, intent, plan, apply_dio_set, project)


def cmd_mcu_set(args: argparse.Namespace) -> int:
    intent, plan, project = _preflight_plan(args, normalize_mcu_intent, McuProvider)
    return _complete_planned_command(args, intent, plan, apply_mcu_set, project)


def normalize_adc_intent(args: argparse.Namespace, _bundle) -> Intent:
    """Normalize `adc set` CLI arguments into the JSON intent contract.

    The ADC config delta is expressed as a single JSON object via ``--spec``;
    its keys become the intent payload verbatim so a cold agent can author one
    self-contained spec file. Domain values (channel names, enum tokens, sampling
    derivation) are resolved/validated downstream in apply_adc_set against the
    committed adc.json asset -- the CLI does not invent or transform them here.
    """
    payload: dict = _load_spec_payload(args, "adc") or {}
    return Intent.from_dict({"module": "adc", "action": "set", "payload": payload})


def cmd_adc_set(args: argparse.Namespace) -> int:
    intent, plan, project = _preflight_plan(args, normalize_adc_intent, AdcProvider)
    return _complete_planned_command(args, intent, plan, apply_adc_set, project)


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:

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

    if args.command == "adc" and getattr(args, "action", None) == "set":
        return cmd_adc_set(args)

    if args.version:
        return emit({
            "status": "passed",
            "command": "version",
            "tool": "RTD CfgFile CLI",
            "version": __version__,
        })

    raise CliFailure(
        code="invalid_arguments",
        message="A complete command and action are required.",
        module="cli",
        details={
            "command": getattr(args, "command", None),
            "action": getattr(args, "action", None),
            "usage": parser.format_usage().strip(),
        },
        exit_code=2,
    )


def _command_from_argv(argv: list[str]) -> str:
    if argv == ["--version"]:
        return "version"
    if argv and argv[0] in ROOT_COMMANDS:
        return argv[0]
    return "unknown"


def _map_exception(exc: Exception) -> CliFailure:
    if isinstance(exc, CliFailure):
        return exc
    if isinstance(exc, PermissionError):
        return CliFailure(
            "permission_denied",
            "The operation was denied by the operating system.",
            module="cli",
            details={"errno": exc.errno} if exc.errno is not None else {},
        )
    if isinstance(exc, FileNotFoundError):
        filename = str(exc.filename) if exc.filename else None
        return CliFailure(
            "asset_not_found" if filename and "assets" in Path(filename).parts else "resource_not_found",
            "A required runtime asset was not found."
            if filename and "assets" in Path(filename).parts
            else "A required file or directory was not found.",
            module="cli",
            details={"errno": exc.errno} if exc.errno is not None else {},
        )
    if isinstance(exc, json.JSONDecodeError):
        return CliFailure(
            "asset_invalid",
            "A required runtime asset is not valid JSON.",
            module="cli",
            details={"line": exc.lineno, "column": exc.colno},
        )
    if isinstance(exc, UnicodeError):
        return CliFailure(
            "asset_invalid",
            "A required runtime asset is not valid UTF-8.",
            module="cli",
        )
    if isinstance(exc, ET.ParseError):
        return CliFailure(
            "project_xml_invalid",
            "The project .mex file is malformed XML.",
            module="backend",
            details={"reason": str(exc)},
        )
    if isinstance(exc, OSError):
        return CliFailure(
            "io_error",
            "The operation failed because of an operating-system I/O error.",
            module="cli",
            details={"errno": exc.errno} if exc.errno is not None else {},
        )
    return CliFailure(
        "internal_error",
        "An unexpected internal error occurred.",
        module="cli",
    )


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in raw_argv
    debug_mode = "--debug" in raw_argv
    parse_argv = [item for item in raw_argv if item not in {"--json", "--debug"}]
    command = _command_from_argv(parse_argv)

    try:
        parser = build_parser()
        args = parser.parse_args(parse_argv)
        args.json = json_mode
        args.debug = debug_mode
        return _dispatch(args, parser)
    except Exception as exc:
        failure = _map_exception(exc)
        payload = render_failure(failure, command)
        if json_mode:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"{failure.code}: {failure.message}", file=sys.stderr)
        if debug_mode:
            traceback.print_exc(file=sys.stderr)
        return failure.exit_code
