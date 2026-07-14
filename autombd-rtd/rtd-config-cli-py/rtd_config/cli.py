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
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from . import __version__
from .config import (
    DEFAULT_ASSET_ROOT,
    RuntimeConfig,
    validate_runtime_config_fields,
)
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
from .modules.registry import PhysicalRegion, ProviderBinding, ProviderRegistry
from .checks.static import run_static_checks
from .backends.s32_mex.apply import apply_uart_set, apply_uart_add_flexio_channel, apply_platform_set, apply_basenxp_set, apply_mcl_set, apply_port_set, apply_dio_set, apply_mcu_set, apply_adc_set
from .backends.s32_mex.validation import find_s32ds_root, probe_which_root, run_validation
from .diagnostics import Diagnostic, render_failure
from .errors import CliFailure


ROOT_COMMANDS = frozenset(
    {
        "plan",
        "configure",
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


_RUNTIME_OPTIONS = (
    ("--project", "project"),
    ("--backend", "backend"),
    ("--vendor", "vendor"),
    ("--family", "family"),
    ("--device", "device"),
    ("--package", "package"),
    ("--rtd-version", "rtd_version"),
    ("--schema-version", "schema_version"),
    ("--s32ds-root", "s32ds_root"),
    ("--sdk-path", "sdk_path"),
    ("--workspace", "workspace"),
    ("--temp-root", "temp_root"),
    ("--log-root", "log_root"),
    ("--asset-root", "asset_root"),
)


def _add_runtime_arguments(
    parser: argparse.ArgumentParser, *, include_project: bool
) -> None:
    parser.add_argument("--config", default=argparse.SUPPRESS, metavar="PATH")
    for option, dest in _RUNTIME_OPTIONS:
        if dest == "project" and not include_project:
            continue
        parser.add_argument(option, dest=dest, default=argparse.SUPPRESS)
    parser.add_argument(
        "--timeout", "--validation-timeout-s", dest="validation_timeout_s",
        type=int, default=argparse.SUPPRESS,
    )


def _add_canonical_arguments(parser: argparse.ArgumentParser, *, configure: bool) -> None:
    """Add generic request fields without defaults that could mask JSON config."""
    parser.add_argument("--intent", required=True, metavar="PATH")
    _add_runtime_arguments(parser, include_project=True)
    if configure:
        parser.add_argument("--backup", action="store_true")
    parser.add_argument("--json", action="store_true")


def _load_spec_payload(args: argparse.Namespace, module: str, action: str = "set") -> dict | None:
    spec_path = getattr(args, "spec", None)
    if not spec_path:
        return None

    try:
        raw = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliFailure(
            code="spec_not_found",
            message="The module spec file does not exist.",
            module=module,
        ) from exc
    except PermissionError as exc:
        raise CliFailure(
            code="permission_denied",
            message="Permission was denied while reading the module spec.",
            module=module,
        ) from exc
    except UnicodeError as exc:
        raise CliFailure(
            code="spec_invalid",
            message="The module spec is not valid UTF-8.",
            module=module,
        ) from exc
    except OSError as exc:
        raise CliFailure(
            code="spec_read_failed",
            message="The module spec could not be read.",
            module=module,
        ) from exc
    except json.JSONDecodeError as exc:
        raise CliFailure(
            code="spec_invalid",
            message="The module spec is not valid JSON.",
            module=module,
            details={"line": exc.lineno, "column": exc.colno},
        ) from exc

    if not isinstance(raw, dict):
        raise CliFailure("spec_invalid", "Spec must contain a JSON object.", module=module)

    if "payload" not in raw:
        return raw

    spec_module = raw.get("module")
    if spec_module is not None and spec_module != module:
        raise CliFailure(
            "spec_invalid",
            "The module spec does not match the selected shortcut module.",
            module=module,
        )

    spec_action = raw.get("action")
    if spec_action is not None and spec_action != action:
        raise CliFailure(
            "spec_invalid",
            "The module spec does not match the selected shortcut action.",
            module=module,
        )

    payload = raw["payload"]
    if not isinstance(payload, dict):
        raise CliFailure("spec_invalid", "Spec payload must be a JSON object.", module=module)
    return payload


_RUNTIME_FIELDS = (
    "project", "backend", "vendor", "family", "device", "package",
    "rtd_version", "schema_version", "s32ds_root", "sdk_path", "workspace",
    "validation_timeout_s", "temp_root", "log_root", "asset_root",
)
_RUNTIME_PATH_FIELDS = frozenset({
    "project", "s32ds_root", "sdk_path", "workspace", "temp_root", "log_root",
    "asset_root",
})
_EXPECTED_IDENTITY_FIELDS = frozenset({
    "vendor", "family", "device", "package", "rtd_version", "schema_version",
})
_RTD_VERSION_GRAMMAR = re.compile(
    r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*", re.ASCII
)


def _normalized_rtd_version(value: object) -> tuple[str, ...] | None:
    token = str(value).casefold()
    if _RTD_VERSION_GRAMMAR.fullmatch(token) is None:
        return None
    return tuple(
        str(int(segment)) if segment.isdigit() else segment
        for segment in re.split(r"[._-]", token)
    )


def _read_json_object(raw_path: str, *, code: str, label: str, exit_code: int = 1) -> dict:
    """Read one bounded regular JSON file without echoing its path in failures."""
    path = Path(raw_path)
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise OSError("unsafe JSON input")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CliFailure(
            code, f"{label} must be a readable bounded UTF-8 JSON object.",
            module="cli", exit_code=exit_code,
        ) from exc
    if not isinstance(raw, dict):
        raise CliFailure(
            code, f"{label} must contain a JSON object.",
            module="cli", exit_code=exit_code,
        )
    return raw


def _load_runtime_config(args: argparse.Namespace) -> tuple[RuntimeConfig, frozenset[str]]:
    values: dict = {}
    explicit: set[str] = set()
    config_path = getattr(args, "config", None)
    if config_path is not None:
        values = _read_json_object(
            config_path, code="invalid_arguments", label="Runtime configuration",
            exit_code=2,
        )
        validate_runtime_config_fields(values)
        explicit.update(values)
        base = Path(config_path).resolve().parent
        for key in _RUNTIME_PATH_FIELDS & values.keys():
            value = values[key]
            if isinstance(value, str) and value and not Path(value).is_absolute():
                values[key] = base / value
    for key in _RUNTIME_FIELDS:
        if hasattr(args, key):
            values[key] = getattr(args, key)
            explicit.add(key)
    values.setdefault("asset_root", DEFAULT_ASSET_ROOT)
    config = RuntimeConfig.from_dict(values)
    return config, frozenset(explicit & _EXPECTED_IDENTITY_FIELDS)


def _load_canonical_intent(raw_path: str, *, backend: str) -> Intent:
    raw = _read_json_object(raw_path, code="intent_invalid", label="Intent")
    if set(raw) != {"module", "action", "payload"}:
        raise CliFailure(
            "intent_invalid", "Intent must contain exactly module, action, and payload.",
            module="cli",
        )
    if (
        not isinstance(raw["module"], str) or not raw["module"]
        or not isinstance(raw["action"], str) or not raw["action"]
        or not isinstance(raw["payload"], dict)
    ):
        raise CliFailure(
            "intent_invalid", "Intent fields have invalid types.", module="cli",
        )
    intent = Intent.from_dict(raw)
    try:
        get_provider_registry().require_intent(intent, backend=backend)
    except CliFailure as exc:
        raise CliFailure(
            "intent_invalid", "Intent does not select a registered provider action.",
            module="cli",
        ) from exc
    return intent


def build_parser() -> argparse.ArgumentParser:
    parser = RaisingArgumentParser(prog="rtd-config")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    plan_parser = subparsers.add_parser("plan")
    _add_canonical_arguments(plan_parser, configure=False)

    configure_parser = subparsers.add_parser("configure")
    _add_canonical_arguments(configure_parser, configure=True)

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
    _add_runtime_arguments(uart_set, include_project=True)
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
    _add_runtime_arguments(uart_add_flexio, include_project=True)
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
    _add_runtime_arguments(platform_set, include_project=True)
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
    _add_runtime_arguments(basenxp_set, include_project=True)
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
    _add_runtime_arguments(mcl_set, include_project=True)
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
    _add_runtime_arguments(port_set, include_project=True)
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
    _add_runtime_arguments(dio_set, include_project=True)
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
    _add_runtime_arguments(mcu_set, include_project=True)
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
    _add_runtime_arguments(adc_set, include_project=True)
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


def _preflight_project(
    project: Project, *, asset_root: Path | None = None
) -> Project:
    """Resolve and cache exact project assets before provider or vendor work."""
    metadata = project.metadata.require_identity()
    project._cache["asset_bundle"] = AssetBundleResolver(
        asset_root or DEFAULT_ASSET_ROOT
    ).resolve(metadata)
    return project


def _assert_expected_identity(
    project: Project, config: RuntimeConfig, expected_fields: frozenset[str]
) -> None:
    metadata = project.metadata.require_identity()
    metadata_names = {"rtd_version": "rtd_release"}
    mismatches = []
    for field in sorted(expected_fields):
        observed = getattr(metadata, metadata_names.get(field, field))
        expected = getattr(config, field)
        if field == "rtd_version":
            observed_value = _normalized_rtd_version(observed)
            expected_value = _normalized_rtd_version(expected)
            matches = (
                observed_value is not None
                and expected_value is not None
                and observed_value == expected_value
            )
        else:
            matches = str(observed).casefold() == str(expected).casefold()
        if not matches:
            mismatches.append(field)
    if mismatches:
        raise CliFailure(
            "project_identity_mismatch",
            "Observed project identity does not match runtime constraints.",
            module="backend", details={"fields": mismatches},
        )


def _execute_canonical_request(
    config: RuntimeConfig,
    *,
    configure: bool,
    backup: bool,
    expected_fields: frozenset[str] = frozenset(),
    intent: Intent | None = None,
    binding: ProviderBinding | None = None,
    shortcut_args: argparse.Namespace | None = None,
) -> int:
    """Execute generic and shortcut requests through one registry-owned flow."""
    project = Project.verified(config.project, config.backend)
    try:
        _preflight_project(project, asset_root=config.asset_root)
        _assert_expected_identity(project, config, expected_fields)
        bundle = project.asset_bundle
        if shortcut_args is not None:
            if binding is None:
                binding = _shortcut_binding(shortcut_args)
            intent = binding.normalizer(shortcut_args, bundle)
        if intent is None:
            raise CliFailure("intent_invalid", "Canonical intent is unavailable.", module="cli")
        registered = get_provider_registry().require_intent(intent, backend=config.backend)
        if binding is not None and registered is not binding:
            raise CliFailure(
                "provider_binding_changed",
                "The provider registry changed during command preflight.",
                module="backend",
            )
        binding = registered
        plan = binding.create_plan(bundle, intent)
        if not configure:
            return emit({
                "status": "passed",
                "command": "plan",
                "normalized_intent": _intent_dict(intent),
                "plan": plan.to_dict(),
            })
        execution_args = argparse.Namespace(backup=backup)
        return _configure_verified_project(
            execution_args, intent, plan, binding.apply_fn, project,
            binding=binding, runtime_config=config,
        )
    finally:
        project.close()


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
        project,
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
            "output_faults": outcome.output_faults,
            "cleanup_warnings": outcome.cleanup_warnings,
        },
    })


def cmd_uart_set(args: argparse.Namespace) -> int:
    return _run_registered_shortcut(args, "uart", "set")


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
    return _run_registered_shortcut(args, "uart", "add-flexio-channel")


def _configure_module(
    args: argparse.Namespace, intent: Intent, plan, apply_fn,
    project: Project | None = None,
    binding: ProviderBinding | None = None,
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
        return _configure_verified_project(
            args, intent, plan, apply_fn, project, binding=binding
        )
    finally:
        project.close()


def _configured_vendor_runner(config: RuntimeConfig | None):
    if config is None or config.s32ds_root is None:
        return None

    def validate_candidate(*, staging, document, project, bundle):
        del document, bundle
        outcome = run_validation(
            project,
            config.s32ds_root,
            sdk_path=config.sdk_path,
            workspace=config.workspace,
            timeout_s=config.validation_timeout_s,
            temp_root=config.temp_root,
            log_root=config.log_root,
            mex_file=staging,
        )
        # ConfigureTransaction consumes the shared validator protocol.  Keep
        # compatible validator test doubles on that protocol as well.
        if not hasattr(outcome, "status"):
            outcome.status = "passed" if bool(outcome.passed) else "blocked"
        return outcome

    return validate_candidate


def _configure_verified_project(
    args, intent, plan, apply_fn, project: Project,
    *, binding: ProviderBinding | None = None,
    runtime_config: RuntimeConfig | None = None,
) -> int:
    try:
        transaction_result = ConfigureTransaction(
            project,
            plan=plan,
            binding=binding,
            backup=args.backup,
            static_runner=run_static_checks,
            vendor_runner=_configured_vendor_runner(runtime_config),
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
        vendor_result = transaction_result.vendor_result
        if vendor_result is not None:
            payload.setdefault("runtime_verification", {})["vendor_validation"] = {
                "status": getattr(vendor_result, "status", "blocked"),
                "passed": bool(getattr(vendor_result, "passed", False)),
                "exit_code": getattr(vendor_result, "exit_code", None),
                "severe_problems": list(
                    getattr(vendor_result, "severe_problems", ())
                ),
                "cleanup_warnings": list(
                    getattr(vendor_result, "cleanup_warnings", ())
                ),
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
            details={"reason_code": "narrow_writer_rejected", "failure_count": 1},
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
    return _run_registered_shortcut(args, "platform", "set")


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
    return _run_registered_shortcut(args, "basenxp", "set")


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
    return _run_registered_shortcut(args, "mcl", "set")


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
    return _run_registered_shortcut(args, "port", "set")


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
    return _run_registered_shortcut(args, "dio", "set")


def cmd_mcu_set(args: argparse.Namespace) -> int:
    return _run_registered_shortcut(args, "mcu", "set")


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


_PROVIDER_REGISTRY: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Return the validated single source of provider dispatch and ownership."""
    global _PROVIDER_REGISTRY
    if _PROVIDER_REGISTRY is None:
        config_region = lambda owner, name: PhysicalRegion(owner, f"config_set:{name}")
        bindings = (
            ProviderBinding(
                "mex", "uart", "set", "set", normalize_uart_intent,
                UartProvider, apply_uart_set,
                frozenset({"uart", "mcu", "port", "platform", "mcl"}), frozenset(),
                frozenset({
                    config_region("uart", "Uart"), config_region("mcu", "Mcu"),
                    config_region("port", "Port"), PhysicalRegion("port", "Pins/Port"),
                    config_region("platform", "Platform"), config_region("mcl", "Mcl"),
                    PhysicalRegion("mcu", "Clocks/clock_settings"),
                }),
            ),
            ProviderBinding(
                "mex", "uart", "add_flexio_channel", "add-flexio-channel",
                normalize_uart_add_flexio_intent, UartProvider,
                apply_uart_add_flexio_channel,
                frozenset({"uart", "mcu", "platform", "mcl"}), frozenset(),
                frozenset({
                    config_region("uart", "Uart"), config_region("mcu", "Mcu"),
                    config_region("platform", "Platform"), config_region("mcl", "Mcl"),
                    PhysicalRegion("mcu", "Clocks/clock_settings"),
                }),
            ),
            ProviderBinding(
                "mex", "platform", "set", "set", normalize_platform_intent,
                PlatformProvider, apply_platform_set, frozenset({"platform"}), frozenset(),
                frozenset({config_region("platform", "Platform")}),
            ),
            ProviderBinding(
                "mex", "basenxp", "set", "set", normalize_basenxp_intent,
                BaseNxpProvider, apply_basenxp_set, frozenset({"basenxp"}), frozenset({"mcu"}),
                frozenset({config_region("basenxp", "BaseNXP")}),
            ),
            ProviderBinding(
                "mex", "mcl", "set", "set", normalize_mcl_intent,
                MclProvider, apply_mcl_set, frozenset({"mcl"}), frozenset(),
                frozenset({config_region("mcl", "Mcl")}),
            ),
            ProviderBinding(
                "mex", "port", "set", "set", normalize_port_intent,
                PortProvider, apply_port_set, frozenset({"port"}), frozenset(),
                frozenset({config_region("port", "Port"), PhysicalRegion("port", "Pins/Port")}),
            ),
            ProviderBinding(
                "mex", "dio", "set", "set", normalize_dio_intent,
                DioProvider, apply_dio_set, frozenset({"dio", "port"}), frozenset(),
                frozenset({config_region("dio", "Dio"), config_region("port", "Port"), PhysicalRegion("port", "Pins/Port")}),
            ),
            ProviderBinding(
                "mex", "mcu", "set", "set", normalize_mcu_intent,
                McuProvider, apply_mcu_set, frozenset({"mcu"}), frozenset(),
                frozenset({config_region("mcu", "Mcu"), PhysicalRegion("mcu", "Clocks/clock_settings")}),
            ),
            ProviderBinding(
                "mex", "adc", "set", "set", normalize_adc_intent,
                AdcProvider, apply_adc_set, frozenset({"adc", "mcl"}), frozenset(),
                frozenset({config_region("adc", "Adc"), config_region("mcl", "Mcl")}),
            ),
        )
        _PROVIDER_REGISTRY = ProviderRegistry(bindings)
    return _PROVIDER_REGISTRY


def _shortcut_binding(
    args: argparse.Namespace, module: str | None = None, cli_action: str | None = None
) -> ProviderBinding:
    return get_provider_registry().lookup_shortcut(
        module or args.command, cli_action or args.action
    )


def _run_registered_shortcut(
    args: argparse.Namespace, module: str | None = None, cli_action: str | None = None
) -> int:
    config, expected_fields = _load_runtime_config(args)
    return _execute_canonical_request(
        config,
        configure=bool(getattr(args, "configure", False)),
        backup=bool(getattr(args, "backup", False)),
        expected_fields=expected_fields,
        binding=None,
        shortcut_args=args,
    )


def cmd_adc_set(args: argparse.Namespace) -> int:
    return _run_registered_shortcut(args, "adc", "set")


def _run_generic(args: argparse.Namespace) -> int:
    config, expected_fields = _load_runtime_config(args)
    intent = _load_canonical_intent(args.intent, backend=config.backend)
    return _execute_canonical_request(
        config,
        configure=args.command == "configure",
        backup=bool(getattr(args, "backup", False)),
        expected_fields=expected_fields,
        intent=intent,
    )


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:

    if args.command in {"plan", "configure"}:
        return _run_generic(args)

    if args.command == "pin-options":
        return cmd_pin_options(args)

    if args.command == "inspect":
        return cmd_inspect(args)

    if args.command == "check":
        return cmd_check(args)

    if args.command == "validate":
        return cmd_validate(args)

    action = getattr(args, "action", None)
    if (
        args.command in {"uart", "platform", "basenxp", "mcl", "port", "dio", "mcu", "adc"}
        and isinstance(action, str)
        and action
    ):
        return _run_registered_shortcut(args)

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
