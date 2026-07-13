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
# File:        adc.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-19
# Version:     0.1.0
# Description: Adc module provider (Hardware Unit, groups, channels, watchdog).
# =================================================================================

from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange
from rtd_config.resources.bundles import ResolvedAssetBundle


class AdcProvider:
    """Owns the Adc Hardware-Unit configuration tree.

    The Adc provider configures one AdcHwUnit (its channels, groups, and
    threshold-control entries) plus the sibling AdcHwConfiguration entry for that
    unit and the Adc-global watchdog API switch. All of these live inside the
    ``<config_set name="Adc">`` region, so they are Adc-owned; no cross-module
    dependency is required for RTD-MEX-ADC-001 (interrupt mode is internal to the
    ADC peripheral and does not consume a Platform IRQ entry the way LPUART does).

    The declarative plan is intentionally one Adc-owned change. The byte-faithful
    editing lives in ``backends/s32_mex/apply.apply_adc_set``.

    Extension points (ADC-002/003/004, not implemented here): DMA transfer adds a
    cross-module Mcl DMA-channel dependency; BCTU triggers add AdcHwTrigger /
    BctuHwUnit edits. Those declare their own PlannedChange records.
    """

    name = "adc"

    def __init__(self, bundle: ResolvedAssetBundle):
        self.bundle = bundle

    def plan(self, intent: Intent) -> Plan:
        payload = intent.payload
        # Multi-unit form (RTD-MEX-ADC-004): payload carries "units":[{unit,
        # sampling_time_us}, ...] plus one shared "bctu" block instead of a single
        # top-level "unit". A LIST BCTU whose FIFO destination raises a DMA request
        # (bctu.fifo_dma) consumes the same Mcl DMA logic channel a unit-DMA does,
        # so the plan declares the Mcl dependency for that path too.
        units = payload.get("units") or []
        unit = payload.get("unit")
        if not unit and not units:
            # Nothing requested -> empty plan (no-op).
            return Plan([])

        groups = payload.get("groups", [])
        watchdog = payload.get("watchdog", [])
        transfer = payload.get("transfer", "interrupt")
        bctu = payload.get("bctu") or {}
        fifo_dma = bool(bctu.get("fifo_dma", False))

        if units:
            unit_ids = ", ".join(str(u.get("unit", "")) for u in units) or "(none)"
            description = (
                f"Configure {len(units)} Adc Hardware Unit(s) [{unit_ids}] and one "
                f"shared BCTU hardware trigger (mode {bctu.get('mode', 'single')!r}); "
                "derive AdcSamplingDuration + AdcPrescale per unit; wire the "
                "AdcHwTrigger / BctuHwUnit subtree (list items, result FIFO, "
                "notifications) and the gating API flags. All Adc edits are inside "
                '<config_set name="Adc">.'
            )
        else:
            description = (
                f"Configure Adc Hardware Unit {unit} ({transfer} transfer) with "
                f"{len(groups)} group(s) and {len(watchdog)} watchdog threshold(s); "
                "derive AdcSamplingDuration + AdcPrescale from the ADC source clock; add "
                "the unit's AdcHwConfiguration entry (NormalInterrupt/Dma/WdgThreshold "
                "coherence) and flip AutosarExt/AdcEnableWatchdogApi when a watchdog "
                "is requested. All edits are inside <config_set name=\"Adc\">."
            )
        changes = [
            PlannedChange(
                module="adc",
                owner="adc",
                path="/Adc/Adc/AdcConfigSet/AdcHwUnit",
                description=description,
            )
        ]

        # DMA transfer is a cross-module dependency: Mcl owns the DMA logic
        # channel the ADC unit references (AdcDmaChannelId / BctuFifoDmaChannelId)
        # and the MclEnableDma global switch. The Adc provider declares it; the
        # Mcl-owned edits are applied through the shared Mcl DMA activation, never
        # silently. Both a unit-DMA (transfer=="dma") and a BCTU FIFO-DMA
        # (bctu.fifo_dma) reuse dmaLogicChannel_Type_0, so either path declares the
        # same single Mcl dependency.
        if transfer == "dma" or fifo_dma:
            changes.append(PlannedChange(
                module="mcl",
                owner="mcl",
                path="/Mcl/Mcl/MclConfig/dmaLogicChannel_Type",
                description=(
                    "Enable Mcl DMA (MclEnableDma=true) and activate the "
                    "dmaLogicChannel_Type_0 logic channel referenced by the ADC "
                    "unit's AdcDmaChannelId or the BCTU result FIFO's "
                    "BctuFifoDmaChannelId for DMA transfer."
                ),
            ))

        return Plan(changes)
