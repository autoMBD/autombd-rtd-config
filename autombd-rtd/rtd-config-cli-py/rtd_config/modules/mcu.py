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
# File:        mcu.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Mcu module provider (peripheral clock reference dependency).
# =================================================================================

from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class McuProvider:
    """Owns Mcu clock/reference configuration.

    Uart and FlexIO depend on valid Mcu clock references. The Mcu provider
    owns only the Mcu config region; it never edits Port (oscillator pins) or
    Platform (clock-monitor/voltage/reset interrupts).
    """

    name = "mcu"

    def plan(self, intent: Intent) -> Plan:
        """Return planned changes for the Mcu clock-tree recipe.

        For a `set` action with core_clk/aips_plat_clk/aips_slow_clk, two
        changes are described:
        1. PLL and CGM clock-tree configuration (clock_settings + Mcu config_set
           PLL/divider/mux settings).
        2. McuClockReferencePoint array replacement with all selectable S32K344
           clocks (when add_all_clock_reference_points=True).
        """
        payload = intent.payload
        core_clk = payload.get("core_clk")
        aips_plat_clk = payload.get("aips_plat_clk")
        aips_slow_clk = payload.get("aips_slow_clk")
        add_all_ref = payload.get("add_all_clock_reference_points", False)

        changes: list[PlannedChange] = []

        if core_clk is not None or aips_plat_clk is not None or aips_slow_clk is not None:
            changes.append(PlannedChange(
                module="mcu",
                owner="mcu",
                path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0",
                description=(
                    f"Configure PLL clock tree: CORE_CLK={core_clk} MHz, "
                    f"AIPS_PLAT_CLK={aips_plat_clk} MHz, "
                    f"AIPS_SLOW_CLK={aips_slow_clk} MHz. "
                    "Edits clock_settings (DIV1/DIV2 scale, PLL power-up, CGM MUX0 sel=PHI0) "
                    "and Mcu config_set (McuPll_0, McuPll_Configuration, "
                    "McuPll_Parameter PLL params, McuCgm0ClockMux0 divisors)."
                ),
            ))

        if add_all_ref:
            changes.append(PlannedChange(
                module="mcu",
                owner="mcu",
                path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/McuClockReferencePoint",
                description=(
                    "Replace McuClockReferencePoint array with 13 structs "
                    "(one per selectable S32K344 clock: CORE_CLK, AIPS_PLAT_CLK, "
                    "AIPS_SLOW_CLK, FLEXCAN_PE_CLK0_2, FLEXCAN_PE_CLK3_5, "
                    "EMAC_CLK_RX/TX/TS, QuadSPI_SFCK, QSPI_MEM_CLK, "
                    "FIRC_CLK, SIRC_CLK, STM0_CLK)."
                ),
            ))

        if not changes:
            # Fallback: general clock reference ensure (used by Uart dependency)
            changes.append(PlannedChange(
                module="mcu",
                owner="mcu",
                path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0",
                description="Ensure Mcu clock reference is present",
            ))

        return Plan(changes)

    def clock_dependency(self, hw: str) -> PlannedChange:
        """Return the Mcu-owned clock dependency a consumer (Uart) requires."""
        return PlannedChange(
            module="mcu",
            owner="mcu",
            path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0",
            description=f"Ensure clock reference for {hw}",
        )
