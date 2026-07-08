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
# File:        test_cli_spec_input.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-03
# Version:     0.1.0
# Description: Unit tests for structured --spec input normalization.
# =================================================================================

from __future__ import annotations

import json

import pytest

from rtd_config import cli


def _write_spec(tmp_path, module: str, payload: dict) -> str:
    path = tmp_path / f"{module}.json"
    path.write_text(
        json.dumps({"module": module, "action": "set", "payload": payload}),
        encoding="utf-8",
    )
    return str(path)


def _normalize_from_args(argv: list[str]):
    parser = cli.build_parser()
    args = parser.parse_args(argv)
    normalizer = getattr(cli, f"normalize_{args.command}_intent")
    return normalizer(args)


@pytest.mark.parametrize(
    ("module", "flag_args", "payload"),
    [
        (
            "uart",
            [
                "--hw", "LPUART_3",
                "--mode", "interrupt",
                "--baud", "115200",
                "--tx", "PTB10",
                "--rx", "PTB11",
                "--using", "LPUART_IP",
                "--channel-id", "0",
                "--callback", "Autombd_UartCallback",
                "--parity", "none",
                "--stop-bits", "1",
                "--word-length", "8",
                "--priority", "2",
            ],
            {
                "hw": "LPUART_3",
                "mode": "interrupt",
                "baud": 115200,
                "pins": {"tx": "PTB10", "rx": "PTB11"},
                "using": "LPUART_IP",
                "channel_id": 0,
                "callback": "Autombd_UartCallback",
                "parity": "LPUART_UART_IP_PARITY_DISABLED",
                "stop_bits": "LPUART_UART_IP_ONE_STOP_BIT",
                "word_length": "LPUART_UART_IP_8_BITS_PER_CHAR",
                "priority": 2,
            },
        ),
        (
            "platform",
            ["--peripheral", "LPUART_3", "--priority", "2"],
            {"peripheral": "LPUART_3", "priority": 2},
        ),
        (
            "basenxp",
            [
                "--enable-system-timer",
                "--user-mode-support", "true",
                "--dev-error-detect", "false",
                "--custom-timer", "false",
                "--get-user-id", "core",
                "--instance-id", "7",
                "--get-physical-core-id", "true",
                "--software-semaphore", "false",
            ],
            {
                "enable_system_timer": True,
                "user_mode_support": True,
                "dev_error_detect": False,
                "custom_timer": False,
                "get_user_id": "GET_CORE_ID",
                "instance_id": 7,
                "get_physical_core_id": True,
                "software_semaphore": False,
            },
        ),
        (
            "mcl",
            ["--add-flexio-logic-channel", "UART2_TX"],
            {"add_flexio_logic_channel": "UART2_TX"},
        ),
        (
            "port",
            ["--peripheral", "LPUART_3", "--tx", "PTB10", "--rx", "PTB11"],
            {"peripheral": "LPUART_3", "pins": {"tx": "PTB10", "rx": "PTB11"}},
        ),
        (
            "dio",
            ["--add-channel", "LED_CTRL", "--pin", "PTA5", "--direction", "output"],
            {"add_channel": "LED_CTRL", "pin": "PTA5", "direction": "output"},
        ),
        (
            "mcu",
            [
                "--core-clk", "160",
                "--aips-plat-clk", "80",
                "--aips-slow-clk", "40",
                "--add-all-clock-reference-points",
            ],
            {
                "core_clk": 160,
                "aips_plat_clk": 80,
                "aips_slow_clk": 40,
                "add_all_clock_reference_points": True,
            },
        ),
    ],
)
def test_module_set_spec_envelope_matches_flag_intent(tmp_path, module, flag_args, payload):
    project = tmp_path / "project"
    project.mkdir()
    spec = _write_spec(tmp_path, module, payload)

    flag_intent = _normalize_from_args(
        [module, "set", "--project", str(project), *flag_args]
    )
    spec_intent = _normalize_from_args(
        [
            module,
            "set",
            "--project",
            str(project),
            "--spec",
            spec,
            "--configure",
            "--json",
        ]
    )

    assert spec_intent == flag_intent


def test_adc_set_accepts_legacy_raw_payload_spec(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "unit": "ADC_0",
        "transfer": "interrupt",
        "groups": [
            {
                "name": "AdcGroup_0",
                "channels": ["S8_ChanNum32"],
            }
        ],
    }
    spec = tmp_path / "adc.json"
    spec.write_text(json.dumps(payload), encoding="utf-8")

    intent = _normalize_from_args(
        [
            "adc",
            "set",
            "--project",
            str(project),
            "--spec",
            str(spec),
            "--configure",
            "--json",
        ]
    )

    assert intent.module == "adc"
    assert intent.action == "set"
    assert intent.payload == payload


def test_spec_envelope_rejects_wrong_module(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    spec = _write_spec(tmp_path, "dio", {"add_channel": "LED_CTRL"})

    parser = cli.build_parser()
    args = parser.parse_args(["port", "set", "--project", str(project), "--spec", spec])

    with pytest.raises(SystemExit):
        cli.normalize_port_intent(args)
