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
# File:        uart.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Uart module provider: owns channel settings, declares dependencies.
# =================================================================================

from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange
from rtd_config.modules.mcu import McuProvider
from rtd_config.modules.port import PortProvider
from rtd_config.modules.platform import PlatformProvider
from rtd_config.modules.mcl import MclProvider


def is_flexio(hw: str) -> bool:
    """Return True when the requested hardware uses the FlexIO Uart path."""
    return hw.upper().startswith("FLEXIO")


class UartProvider:
    """User-facing Uart driver path (LPUART and FlexIO, polling/interrupt).

    Uart owns channel settings and Uart-side references. It does not edit other
    modules directly; instead it declares explicit dependency PlannedChange
    records owned by their respective providers:

    - Mcu owns the clock reference (always required);
    - Port owns TX/RX pin routing (when pins are requested);
    - Platform owns the IRQ entry (interrupt mode only);
    - Mcl owns the FlexIO logic channel (FlexIO path only).

    DMA is outside Milestone 1 and is rejected/deferred by the static checks.
    """

    name = "uart"

    def plan(self, intent: Intent) -> Plan:
        payload = intent.payload
        hw = payload.get("hw", "")
        mode = payload.get("mode", "polling")

        # Uart-owned change: the channel settings themselves.
        changes = [
            PlannedChange(
                module="uart",
                owner="uart",
                path="/Uart/Uart/UartGlobalConfig/UartChannel",
                description=f"Configure {hw} channel in {mode} mode",
            )
        ]

        # Mcu clock reference is always required for a working Uart channel.
        changes.append(McuProvider().clock_dependency(hw))

        # Port pin routing dependency, when the consumer requested pins.
        if payload.get("pins"):
            changes.append(PortProvider().pin_dependency(payload["pins"]))

        # Platform IRQ dependency in interrupt mode only.
        if mode == "interrupt":
            changes.append(PlatformProvider().irq_dependency(hw))

        # Mcl FlexIO logic-channel dependency on the FlexIO path only.
        if is_flexio(hw):
            changes.append(MclProvider().flexio_dependency(hw))

        return Plan(changes)
