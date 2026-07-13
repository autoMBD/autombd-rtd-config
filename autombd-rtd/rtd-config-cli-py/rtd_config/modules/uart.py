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
from rtd_config.resources.bundles import ResolvedAssetBundle


def is_flexio(hw: str) -> bool:
    """Return True when the requested hardware uses the FlexIO Uart path."""
    return hw.upper().startswith("FLEXIO")


class UartProvider:
    """User-facing Uart driver path (LPUART and FlexIO, interrupt and DMA modes).

    Uart owns channel settings and Uart-side references. It does not edit other
    modules directly; instead it declares explicit dependency PlannedChange
    records owned by their respective providers:

    - Mcu owns the clock reference (always required);
    - Port owns TX/RX pin routing (when pins are requested);
    - Platform owns the IRQ entry (interrupt mode: LPUART IRQ; DMA mode: DMATCD IRQs);
    - Mcl owns the FlexIO logic channel (FlexIO path) or DMA logic channels (DMA mode).
    """

    name = "uart"

    def __init__(self, bundle: ResolvedAssetBundle):
        self.bundle = bundle

    def plan(self, intent: Intent) -> Plan:
        action = intent.action
        if action == "add_flexio_channel":
            return self._plan_add_flexio_channel(intent)
        return self._plan_set(intent)

    def _plan_set(self, intent: Intent) -> Plan:
        """Plan for `uart set` (LPUART / FlexIO channel configure, RTD-MEX-UART-001/003)."""
        payload = intent.payload
        hw = payload.get("hw", "")
        mode = payload.get("mode", "interrupt")

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
        changes.append(McuProvider(self.bundle).clock_dependency(hw))

        # Port pin routing dependency, when the consumer requested pins.
        if payload.get("pins"):
            changes.append(PortProvider(self.bundle).pin_dependency(payload["pins"]))

        if mode == "interrupt":
            # Platform IRQ dependency in interrupt mode: LPUART peripheral IRQ.
            changes.append(PlatformProvider(self.bundle).irq_dependency(hw))
        elif mode == "dma":
            # DMA mode: Platform owns DMATCD ISRs, Mcl owns DMA logic channels.
            changes.append(PlatformProvider(self.bundle).dma_isr_dependency(hw))
            changes.append(MclProvider(self.bundle).dma_dependency(hw))

        # Mcl FlexIO logic-channel dependency on the FlexIO path only.
        if is_flexio(hw):
            changes.append(MclProvider(self.bundle).flexio_dependency(hw))

        return Plan(changes)

    def _plan_add_flexio_channel(self, intent: Intent) -> Plan:
        """Plan for `uart add-flexio-channel` (FlexIO Tx+Rx pair, RTD-MEX-UART-002).

        Declares explicit dependencies for all four modules edited:
        - uart: owns the 2 new UartChannel structs
        - mcl: owns the 2 new FlexioMclLogicChannels structs
        - platform: ensure FLEXIO_IRQn / MCL_FLEXIO_ISR is present+enabled
          (concrete values grounded in uart.json instance_irq_clock_map FLEXIO entry)
        - mcu: ensure FLEXIO_CLK / CORE_CLK is present
          (concrete values grounded in uart.json instance_irq_clock_map FLEXIO entry)
        """
        payload = intent.payload
        tx_name = payload.get("tx_name", "UART2_TX")
        rx_name = payload.get("rx_name", "UART2_RX")
        baud = payload.get("baud", 921600)

        changes = [
            PlannedChange(
                module="uart",
                owner="uart",
                path="/Uart/Uart/UartGlobalConfig/UartChannel",
                description=(
                    f"Append two FlexIO UART channels ({tx_name}, {rx_name}) to "
                    f"UartGlobalConfig/UartChannel at {baud} baud, interrupt mode. "
                    "Each carries both DetailModuleConfiguration (dummy LPUART fields) "
                    "and FlexioModuleConfiguration with UartHwChannelRef to the "
                    f"corresponding MCL logic channel."
                ),
            ),
            PlannedChange(
                module="mcl",
                owner="mcl",
                path="/Mcl/Mcl/MclConfig/FlexioCommon_0/FlexioMclLogicChannels",
                description=(
                    f"Append two FlexIO MCL logic channels ({tx_name}, {rx_name}) to "
                    "FlexioMclLogicChannels with next-available CHANNEL_N/PIN_N ids "
                    "(computed dynamically, uniqueness enforced per Mcl.xdm)."
                ),
            ),
            PlannedChange(
                module="platform",
                owner="platform",
                path="/Platform/Platform/IntCtrlConfig/PlatformIsrConfig",
                description=(
                    "Ensure PlatformIsrConfig for FlexIO shared ISR is present+enabled: "
                    "IsrName=FLEXIO_IRQn, IsrHandler=MCL_FLEXIO_ISR, IsrEnabled=true. "
                    "Idempotent no-op if already present (fixture has it). "
                    "Grounded in uart.json instance_irq_clock_map[FLEXIO]."
                ),
            ),
            PlannedChange(
                module="mcu",
                owner="mcu",
                path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/McuClockReferencePoint",
                description=(
                    "Ensure McuClockReferencePoint for FlexIO clock is present: "
                    "Name=FLEXIO_CLK, McuClockFrequencySelect=CORE_CLK. "
                    "Idempotent no-op if already present (fixture has it). "
                    "Grounded in uart.json instance_irq_clock_map[FLEXIO]."
                ),
            ),
        ]
        return Plan(changes)
