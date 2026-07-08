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
# File:        platform.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Platform module provider (interrupt entries).
# =================================================================================

from __future__ import annotations

import json
import re
from pathlib import Path

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange

# Asset root: this file lives at
#   autombd-rtd/rtd-config-cli-py/rtd_config/modules/platform.py
# parents[3] is autombd-rtd/
_MODULE_FILE = Path(__file__).resolve()
_UART_ASSET_PATH = _MODULE_FILE.parents[3] / "assets" / "nxp" / "s32k3" / "uart" / "uart.json"
_PLATFORM_ASSET_PATH = _MODULE_FILE.parents[3] / "assets" / "nxp" / "s32k3" / "platform" / "interrupts.json"


def _load_lpuart_irq_entry(hw: str) -> "dict | None":
    """Load uart.json and return the irq/handler/clock entry for ``hw``.

    Normalises LPUART3 -> LPUART_3 for keys without underscore. Returns None
    for unknown instances or non-LPUART peripherals (e.g. FLEXIO).
    """
    key = hw.strip().upper()
    m = re.match(r"^LPUART(\d+)$", key)
    if m:
        key = f"LPUART_{m.group(1)}"
    try:
        data = json.loads(_UART_ASSET_PATH.read_text(encoding="utf-8"))
        return data.get("instance_irq_clock_map", {}).get(key)
    except (OSError, ValueError):
        return None


def _lpuart_key_from_isr_name(isr_name: str) -> str | None:
    match = re.fullmatch(r"LPUART(\d+)_IRQn", isr_name.strip())
    if match is None:
        return None
    return f"LPUART_{match.group(1)}"


def _load_platform_asset() -> dict:
    try:
        return json.loads(_PLATFORM_ASSET_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _derive_platform_isr_name(peripheral: str) -> str | None:
    patterns = _load_platform_asset().get("isr_name_patterns", {})
    text = peripheral.strip().upper()
    match = re.fullmatch(r"LPUART_?(\d+)", text)
    if match is not None:
        pattern = patterns.get("LPUART_<n>")
        return pattern.replace("<n>", match.group(1)) if pattern else None
    if text.startswith("FLEXIO"):
        return patterns.get("FLEXIO_<x>")
    return None


class PlatformProvider:
    """Owns Platform interrupt-controller configuration.

    Uart interrupt mode must create/update Platform IRQ entries only through
    this provider. The plan never guesses interrupt priority, handler, enable
    state, or partition/core target when missing from the request.
    """

    name = "platform"

    def plan(self, intent: Intent) -> Plan:
        return Plan([self.platform_request_change(intent.payload)])

    def platform_request_change(self, payload: dict) -> PlannedChange:
        """Return the single Platform-owned change requested by ``platform set``."""
        target = payload.get("peripheral") or payload.get("hw") or ""
        priority = payload.get("priority")
        isr_name = payload.get("isr_name")
        if isr_name is None and target:
            isr_name = _derive_platform_isr_name(target)
        elif isr_name and not target:
            target = _lpuart_key_from_isr_name(isr_name) or isr_name

        priority_text = f", priority={priority}" if priority is not None else ""
        handler_text = ", preserve existing IsrHandler registration"
        if target and isr_name:
            description = (
                f"Update existing PlatformIsrConfig for {target}: "
                f"IsrName={isr_name}, IsrEnabled=true{priority_text}{handler_text}"
            )
        elif isr_name:
            description = (
                f"Update existing PlatformIsrConfig: "
                f"IsrName={isr_name}, IsrEnabled=true{priority_text}{handler_text}"
            )
        else:
            description = (
                f"Update existing PlatformIsrConfig for "
                f"{target or 'requested interrupt'}{priority_text}{handler_text}"
            )

        return PlannedChange(
            module="platform",
            owner="platform",
            path="/Platform/Platform/IntCtrlConfig",
            description=description,
        )

    def irq_dependency(
        self,
        hw: str,
        *,
        priority: int | None = None,
        isr_name: str | None = None,
    ) -> PlannedChange:
        """Return the Platform-owned IRQ dependency a consumer requires.

        The description names the concrete IsrName and ISR handler derived from
        the uart.json instance_irq_clock_map (same source as apply_uart_set),
        so the plan accurately describes what will be written.  Falls back to a
        generic description when the hw is not an LPUART instance with a known
        entry (e.g. FLEXIO path or unknown instance).
        """
        entry = _load_lpuart_irq_entry(hw)
        if entry is not None:
            irq_name = entry["irq_name"]
            isr_handler = entry["isr_handler"]
            priority_text = (
                f", priority={priority}"
                if priority is not None
                else ""
            )
            description = (
                f"Insert PlatformIsrConfig for {hw}: "
                f"IsrName={irq_name}, IsrHandler={isr_handler}, "
                f"IsrEnabled=true{priority_text}"
            )
        elif isr_name:
            priority_text = (
                f", priority={priority}"
                if priority is not None
                else ""
            )
            description = (
                f"Update existing PlatformIsrConfig: "
                f"IsrName={isr_name}, IsrEnabled=true{priority_text}"
            )
        else:
            description = f"Configure interrupt entry for {hw}"
        return PlannedChange(
            module="platform",
            owner="platform",
            path="/Platform/Platform/IntCtrlConfig",
            description=description,
        )

    def dma_isr_dependency(self, hw: str) -> PlannedChange:
        """Return the Platform-owned DMA ISR dependency for DMA mode (RTD-MEX-UART-003).

        In DMA mode, the interrupt is generated by DMA (DMATCD), not the peripheral.
        Declares the two DMATCD ISRs: DMATCD0_IRQn/Dma0_Ch0_IRQHandler (TX) and
        DMATCD1_IRQn/Dma0_Ch1_IRQHandler (RX).

        ISR names and handlers loaded from uart.json dma_hw_channel_irq_map (not hardcoded).
        Grounded in: Platform.epd DMATCD IRQ table, Dma_Ip_Irq.c, Spi_Transfer example.
        """
        try:
            data = json.loads(_UART_ASSET_PATH.read_text(encoding="utf-8"))
            dma_map = data.get("dma_hw_channel_irq_map", {})
            ch0 = dma_map.get("0") or dma_map.get(0)
            ch1 = dma_map.get("1") or dma_map.get(1)
            if ch0 and ch1:
                description = (
                    f"Insert two DMATCD PlatformIsrConfig entries for {hw} DMA mode "
                    f"(interrupt generated by DMA, not peripheral): "
                    f"IsrName={ch0['irq_name']}, IsrHandler={ch0['isr_handler']} (TX DMA ch 0); "
                    f"IsrName={ch1['irq_name']}, IsrHandler={ch1['isr_handler']} (RX DMA ch 1). "
                    "Both IsrEnabled=true."
                )
            else:
                description = f"Insert DMATCD PlatformIsrConfig entries for {hw} DMA mode"
        except (OSError, ValueError, KeyError):
            description = f"Insert DMATCD PlatformIsrConfig entries for {hw} DMA mode"
        return PlannedChange(
            module="platform",
            owner="platform",
            path="/Platform/Platform/IntCtrlConfig",
            description=description,
        )
