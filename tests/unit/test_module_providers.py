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
# File:        test_module_providers.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Unit tests for the module providers.
# =================================================================================

from functools import partial

from rtd_config.intent import Intent
from rtd_config.modules import platform as platform_module
from rtd_config.modules.platform import PlatformProvider
from rtd_config.modules.uart import UartProvider
from tests.fixtures import resolved_uart_bundle

_BUNDLE = resolved_uart_bundle()
UartProvider = partial(UartProvider, _BUNDLE)
PlatformProvider = partial(PlatformProvider, _BUNDLE)


def test_uart_plan_declares_dependencies_without_owning_other_modules():
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {
            "hw": "LPUART_0",
            "mode": "interrupt",
            "baud": 115200,
            "pins": {"tx": "PTA15", "rx": "PTA16"},
        },
    })
    plan = UartProvider().plan(intent)
    payload = plan.to_dict()
    owners = {item["owner"] for item in payload["changes"]}
    assert "uart" in owners
    assert "platform" in owners
    assert "port" in owners
    assert "mcu" in owners


def test_platform_plan_uses_platform_payload_without_cross_module_asset_probe(monkeypatch):
    def fail_if_uart_asset_is_loaded(_hw: str):
        raise AssertionError("platform-only plan must not probe Uart assets")

    monkeypatch.setattr(platform_module, "_load_lpuart_irq_entry", fail_if_uart_asset_is_loaded)
    intent = Intent.from_dict({
        "module": "platform",
        "action": "set",
        "payload": {
            "peripheral": "LPUART_5",
            "priority": 4,
        },
    })

    plan = PlatformProvider().plan(intent)
    payload = plan.to_dict()

    assert [item["owner"] for item in payload["changes"]] == ["platform"]
    assert payload["changes"][0]["module"] == "platform"
    assert "LPUART_5" in payload["changes"][0]["description"]
    assert "LPUART5_IRQn" in payload["changes"][0]["description"]
    assert "preserve existing IsrHandler" in payload["changes"][0]["description"]
    assert "priority=4" in payload["changes"][0]["description"]
