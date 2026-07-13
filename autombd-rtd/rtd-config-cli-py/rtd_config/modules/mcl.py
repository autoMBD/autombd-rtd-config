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
# File:        mcl.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Mcl module provider (FlexIO common resources).
# =================================================================================

from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange
from rtd_config.resources.bundles import ResolvedAssetBundle


class MclProvider:
    """Owns Mcl common resources (FlexIO common + FlexIO logic channels).

    FlexIO common resources are owned by Mcl and consumed by Uart.
    MclEnableFlexioCommon must match real FlexIO common/channel entries.
    When Mcl content changes, the highest-risk lesson is to strip a stale
    quick_selection from <config_set name="Mcl"> so ConfigTools does not
    revert the Mcl tree and misreport a Uart out-of-range error.
    """

    name = "mcl"

    def __init__(self, bundle: ResolvedAssetBundle):
        self.bundle = bundle

    def plan(self, intent: Intent) -> Plan:
        changes = []
        channel_name = intent.payload.get("add_flexio_logic_channel")
        if channel_name:
            changes.append(PlannedChange(
                module="mcl",
                owner="mcl",
                path="/Mcl/Mcl/MclConfig/FlexioCommon_0/FlexioMclLogicChannels",
                description=(
                    f"Mcl-only fast path: append FlexIO logic channel '{channel_name}' to "
                    "FlexioMclLogicChannels; MclEnableFlexioCommon=true and "
                    "FlexioCommon_0 are provider-owned preconditions; no inspect required, "
                    "no existing Mcl tree probe, and no Uart configuration. "
                    "Use first-unused legal CHANNEL_N/PIN_N ids from the Mcl.xdm "
                    "domains (uniqueness enforced per Mcl.xdm constraint)."
                ),
            ))
        else:
            # Legacy plan path: used when called without add_flexio_logic_channel
            # (e.g., by the Uart provider's cross-module dependency declaration).
            hw = intent.payload.get("hw", "")
            changes.append(self._flexio_dependency(hw))
        return Plan(changes)

    def _flexio_dependency(self, hw: str) -> PlannedChange:
        """Return the Mcl-owned FlexIO logic-channel dependency Uart requires."""
        return PlannedChange(
            module="mcl",
            owner="mcl",
            path="/Mcl/Mcl/MclConfig/FlexioCommon_0/FlexioMclLogicChannels",
            description=f"Ensure FlexIO logic channel for {hw}",
        )

    # Keep the legacy public name for any existing callers.
    def flexio_dependency(self, hw: str) -> PlannedChange:
        return self._flexio_dependency(hw)

    def dma_dependency(self, hw: str) -> PlannedChange:
        """Return the Mcl-owned DMA logic-channel dependency for DMA mode (RTD-MEX-UART-003).

        In DMA mode, two dmaLogicChannel_Type structs are required:
        - dmaLogicChannel_Type_0 (TX, existing in fixture, activated)
        - dmaLogicChannel_Type_1 (RX, added by DMA path)
        Grounded in uart.json dma_channel_ref_path_pattern and fixture dmaLogicChannel_Type_0.
        """
        return PlannedChange(
            module="mcl",
            owner="mcl",
            path="/Mcl/Mcl/MclConfig/dmaLogicChannel_Type",
            description=(
                f"Activate dmaLogicChannel_Type_0 (TX, DMA_IP_HW_CH_0) for {hw} DMA TX: "
                "set dmaLogicChannel_EnableGlobalConfig=true, "
                "dmaGlobalRequest_enDmaRequest=true (LPUART HW DMA request triggers transfer), "
                "dmaLogicChannelConfig_enDmaMajorInterrupt=true (generates DMATCD0_IRQn). "
                "Add dmaLogicChannel_Type_1 (RX, DMA_IP_HW_CH_1) mirroring _0 field set with "
                "all activation flags=true (generates DMATCD1_IRQn). "
                "Enable MclEnableDma=true. "
                "Grounded in uart.json dma_channel_ref_path_pattern + fixture dmaLogicChannel_Type_0."
            ),
        )
