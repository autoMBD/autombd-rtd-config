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
# File:        apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Localized, owned per-module edits to an S32 ConfigTools .mex.
# =================================================================================

"""Localized, owned edits to an S32 ConfigTools .mex configuration.

Milestone 1 only edits EXISTING module instances; it never creates missing
modules or a .mex from scratch (reserved for M2). Each provider owns its
module's settings; cross-module concerns are declared as dependencies in the
plan, not edited here.

Edits are narrow: they locate the existing element and update its owned fields
in place (attribute edit) or replace a self-closed empty array with a populated
one (element-insertion via replace_element_region), then mark the modified
element so any stale quick_selection on the nearest carrying ancestor is
removed (the highest-risk lesson from the legacy-skills experience).
"""
from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.diagnostics import Diagnostic
from rtd_config.intent import Intent

# Skill root: this file lives at
#   autombd-rtd/rtd-config-cli-py/rtd_config/backends/s32_mex/apply.py
# parents[4] is autombd-rtd/
_APPLY_FILE = Path(__file__).resolve()
_SKILL_ROOT = _APPLY_FILE.parents[4]
_ASSET_ROOT = _SKILL_ROOT / "assets"


# Uart "asynchronous method" enum. RTD 7.0.1 ConfigTools models this field with
# exactly two values per IP -- INTERRUPTS or DMA -- and has NO polling value
# (verified against Uart.xdm and the s32k344 .epd: a "USING_POLLING" enum does
# not exist; ConfigTools rejects it as "value not available"). Both interrupt (IRQ)
# and DMA modes are supported. "Polling/blocking" is an application-level driver-call
# pattern, not a .mex async-method value.
_LPUART_METHOD = {
    "interrupt": "LPUART_UART_IP_USING_INTERRUPTS",
    "dma": "LPUART_UART_IP_USING_DMA",
}
_FLEXIO_METHOD = {
    "interrupt": "FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS",
}


def _load_uart_asset() -> dict:
    """Load the committed uart.json asset at runtime. Never reads raw .xdm."""
    asset_path = _ASSET_ROOT / "nxp" / "s32k3" / "uart" / "uart.json"
    return json.loads(asset_path.read_text(encoding="utf-8"))


def _lookup_lpuart_irq_clock(hw: str) -> "dict | None":
    """Return the irq_name/isr_handler/clock_select entry for an LPUART instance.

    Grounded in uart.json instance_irq_clock_map (derived from S32K344_IRQ.h,
    Platform.xdm/.epd, and the fixture clock tool).  Returns None for unknown
    instances or non-LPUART peripherals (e.g. FLEXIO).
    """
    key = hw.strip().upper()
    # Normalise LPUART3 -> LPUART_3 if the caller omitted the underscore
    m = re.match(r"^LPUART(\d+)$", key)
    if m:
        key = f"LPUART_{m.group(1)}"
    asset = _load_uart_asset()
    return asset.get("instance_irq_clock_map", {}).get(key)


@dataclass
class ApplyResult:
    changed_modules: list[str] = field(default_factory=list)
    modified_elements: list[ET.Element] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(d.severity == "blocker" for d in self.diagnostics)


def _is_flexio_request(hw: str) -> bool:
    return hw.upper().startswith("FLEXIO")


def _select_channel(doc: MexDocument, uart_cfg: ET.Element, want_flexio: bool, channel_id):
    """Pick the Uart channel to edit.

    If an explicit channel_id is given, use it. Otherwise pick the first channel
    whose UartHwUsing matches the requested path (LPUART vs FlexIO).
    """
    if channel_id is not None:
        return doc.find_uart_channel(uart_cfg, channel_id)
    want = "FLEXIO_IP" if want_flexio else "LPUART_IP"
    for array in uart_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "UartChannel"):
            continue
        for channel in array:
            if not channel.tag.endswith("struct"):
                continue
            using = doc.find_child_setting(channel, "UartHwUsing")
            if using is not None and using.attrib.get("value") == want:
                return channel
    return None


def apply_uart_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply the full Uart channel orchestration to the loaded document.

    Performs three owned edits in one call (RTD-MEX-UART-001):

    1. **Uart-owned** (config_set "Uart"):
       - UartHwChannel, DesireBaudrate, UartInteruptDmaMethod (LPUART path)
       - UartWordLength, UartParityType, UartStopBitNumber (when supplied)
       - UartCallbackCapability=true + UartCallback[0]=<callback> (when --callback)
       - UartClockRef -> /Mcu/Mcu/McuModuleConfiguration/<ClockSetting>/<LPUART_N_CLK>

    2. **Platform-owned** (config_set "Platform"):
       - INSERT a new PlatformIsrConfig struct for the LPUART instance
         (skip if IsrName already present -- idempotent).
       - IsrName, IsrEnabled=true, IsrPriority=<priority>, IsrHandler
         all grounded in uart.json instance_irq_clock_map.

    3. **Mcu-owned** (config_set "Mcu"):
       - INSERT a new McuClockReferencePoint struct for <LPUART_N_CLK>
         (skip if Name already present -- idempotent).
       - Name=<LPUART_N_CLK>, McuClockFrequencySelect=<AIPS_PLAT_CLK|AIPS_SLOW_CLK>
         grounded in uart.json instance_irq_clock_map.
       - McuClockReferencePointFrequency is NOT written (ConfigTools computes it).

    The FLEXIO path does NOT orchestrate Platform/Mcu (unchanged from the prior
    single-module behaviour -- FlexIO ISR and clock are handled by Mcl/Platform
    via their own providers).

    DMA mode (mode='dma') is also supported: see apply_uart_set_dma_edits for the
    four-module edit set (Uart method/refs, Mcl channels, Platform DMATCD ISRs).

    changed_modules is the set actually edited (e.g. ["uart","platform","mcu"]).
    Idempotent: running twice with the same intent produces identical output.
    """
    payload = intent.payload
    hw = payload.get("hw", "")
    mode = payload.get("mode", "interrupt")
    baud = payload.get("baud")
    callback = payload.get("callback")
    priority = payload.get("priority", 2)
    word_length = payload.get("word_length")
    parity = payload.get("parity")
    stop_bits = payload.get("stop_bits")
    want_flexio = _is_flexio_request(hw)

    result = ApplyResult()

    # RTD 7.0.1 has no polling async-method value; interrupt and DMA are supported.
    # Reject any other mode with an actionable blocker rather than writing an enum
    # ConfigTools marks "value not available".
    method_map = _FLEXIO_METHOD if want_flexio else _LPUART_METHOD
    if mode not in method_map:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="unsupported_uart_mode",
            module="uart",
            message=(
                f"Uart mode '{mode}' is not supported. RTD 7.0.1 models the Uart "
                "asynchronous method as interrupt (IRQ) or DMA only -- there is no "
                "polling value. Use mode 'interrupt' or 'dma'."
            ),
            details={"mode": mode, "supported": sorted(method_map)},
        ))
        return result

    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="uart_config_set_not_found",
            module="uart",
            message="No enabled Uart <config_set> found; M1 edits existing instances only.",
            details={},
        ))
        return result

    channel = _select_channel(doc, uart_cfg, want_flexio, payload.get("channel_id"))
    if channel is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="uart_channel_not_found",
            module="uart",
            message=(
                "No existing Uart channel matches the requested hardware path; "
                "M1 does not create new channels."
            ),
            details={"hw": hw, "want_flexio": want_flexio},
        ))
        return result

    if want_flexio:
        container = _find_struct(channel, "FlexioModuleConfiguration")
        method_setting = doc.find_child_setting(container, "FlexioUartInteruptDmaMethod") if container is not None else None
        method_value = _FLEXIO_METHOD.get(mode)
        baud_value = f"FLEXIO_UART_BAUDRATE_{baud}" if baud is not None else None
    else:
        container = _find_struct(channel, "DetailModuleConfiguration")
        hw_setting = doc.find_child_setting(container, "UartHwChannel") if container is not None else None
        if hw_setting is not None:
            hw_setting.set("value", hw)
        method_setting = doc.find_child_setting(container, "UartInteruptDmaMethod") if container is not None else None
        method_value = _LPUART_METHOD.get(mode)
        baud_value = f"LPUART_UART_BAUDRATE_{baud}" if baud is not None else None

    if container is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="uart_channel_detail_not_found",
            module="uart",
            message="The selected Uart channel has no matching detail container to edit.",
            details={"hw": hw, "want_flexio": want_flexio},
        ))
        return result

    # =====================================================================
    # PHASE 1: All raw-bytes operations (replace_element_region splices).
    # These each reload the tree from _raw, so they MUST all complete before
    # any attribute mutation (.set("value", ...)). Attribute mutations done
    # before a raw-bytes reload are lost because _capture_sources() re-snaps
    # attribs from the freshly parsed tree. (Same ordering rule as apply_mcu_set.)
    # =====================================================================

    # For the LPUART path, look up IRQ/handler/clock from uart.json asset.
    irq_clock = None
    clock_setting_name = ""
    ref_clock_name = ""
    if not want_flexio:
        irq_clock = _lookup_lpuart_irq_clock(hw)
        if irq_clock is not None:
            # Discover the McuClockSettingConfig name BEFORE any raw-bytes splices.
            clock_setting_name = _find_clock_setting_config_name(doc)
            ref_clock_name = _lpuart_clock_ref_name(hw)  # e.g. "LPUART8_CLK"

            # Part A: Mcu clock-ref insertion (raw bytes; reloads tree)
            mcu_inserted = _ensure_mcu_clock_ref(doc, ref_clock_name, irq_clock["clock_select"])

            if mode == "interrupt":
                # Part B (interrupt): Platform LPUART ISR insertion
                _ensure_platform_isr(
                    doc,
                    irq_name=irq_clock["irq_name"],
                    isr_handler=irq_clock["isr_handler"],
                    priority=priority,
                )
                if "platform" not in result.changed_modules:
                    result.changed_modules.append("platform")

            elif mode == "dma":
                # Part B (DMA): MCL ch1 add + Platform DMATCD ISR insertions (raw-bytes).
                _apply_uart_set_dma_phase1(doc, result, priority)
                # Part C (DMA): Populate UartDmaTxChannelRef + UartDmaRxChannelRef (raw-bytes).
                # Must happen in Phase 1 BEFORE attribute mutations -- replace_element_region
                # reloads the tree and wipes any prior .set() mutations.
                _populate_uart_dma_refs(doc)

            if mcu_inserted and "mcu" not in result.changed_modules:
                result.changed_modules.append("mcu")

    # =====================================================================
    # PHASE 2: Attribute mutations (no raw-bytes reload after this point).
    # Re-find all elements now; they are stale after Phase 1 raw splices.
    # =====================================================================

    uart_cfg = doc.find_config_set("Uart")
    channel = (
        _select_channel(doc, uart_cfg, want_flexio, payload.get("channel_id"))
        if uart_cfg is not None else None
    )

    if channel is not None:
        container = _find_struct(
            channel,
            "FlexioModuleConfiguration" if want_flexio else "DetailModuleConfiguration",
        )

    if channel is not None and container is not None:
        if want_flexio:
            method_setting = doc.find_child_setting(container, "FlexioUartInteruptDmaMethod")
        else:
            hw_setting = doc.find_child_setting(container, "UartHwChannel")
            if hw_setting is not None:
                hw_setting.set("value", hw)
            method_setting = doc.find_child_setting(container, "UartInteruptDmaMethod")

        if method_setting is not None and method_value is not None:
            method_setting.set("value", method_value)

        if baud_value is not None:
            baud_setting = doc.find_child_setting(container, "DesireBaudrate")
            if baud_setting is not None:
                baud_setting.set("value", baud_value)

        # Optional LPUART-specific frame parameters
        if not want_flexio:
            if word_length is not None:
                wl_setting = doc.find_child_setting(container, "UartWordLength")
                if wl_setting is not None:
                    wl_setting.set("value", word_length)
            if parity is not None:
                par_setting = doc.find_child_setting(container, "UartParityType")
                if par_setting is not None:
                    par_setting.set("value", parity)
            if stop_bits is not None:
                sb_setting = doc.find_child_setting(container, "UartStopBitNumber")
                if sb_setting is not None:
                    sb_setting.set("value", stop_bits)

            # DMA mode Phase 2: attribute-only mutations (no raw-bytes splice).
            # UartDmaEnable and MCL ch0 flags are attribute mutations.
            # Tx/Rx ref population was done in Phase 1 (_populate_uart_dma_refs).
            if mode == "dma":
                _apply_uart_set_dma_attrs(doc, uart_cfg)

    # UartClockRef update (LPUART path, after all raw splices so ref is stable)
    if not want_flexio and channel is not None and clock_setting_name and ref_clock_name:
        clock_ref_path = (
            f"/Mcu/Mcu/McuModuleConfiguration/{clock_setting_name}/{ref_clock_name}"
        )
        clock_ref_setting = doc.find_child_setting(channel, "UartClockRef")
        if clock_ref_setting is not None:
            clock_ref_setting.set("value", clock_ref_path)

    # Callback fields (GeneralConfiguration: UartCallbackCapability + UartCallback[0])
    if callback is not None and uart_cfg is not None:
        _apply_uart_callback(doc, uart_cfg, callback)

    # =====================================================================
    # PHASE 3: mark_modified + clear quick_selection LAST (LL-013 ordering).
    # Must happen after ALL replace_element_region calls so the final
    # _capture_sources() snapshot sees the cleared attributes.
    # =====================================================================

    if channel is not None:
        doc.mark_modified(channel)
        carrier = doc.find_nearest_quick_selection_ancestor(channel)
        if carrier is not None:
            doc.mark_modified(carrier)
        result.modified_elements.append(channel)

    if not want_flexio:
        platform_cfg = doc.find_config_set("Platform")
        if platform_cfg is not None:
            doc.mark_modified(platform_cfg)
            result.modified_elements.append(platform_cfg)
        mcu_cfg_final = doc.find_config_set("Mcu")
        if mcu_cfg_final is not None:
            doc.mark_modified(mcu_cfg_final)
            result.modified_elements.append(mcu_cfg_final)
        # DMA: also mark Mcl config as modified
        if mode == "dma":
            mcl_cfg_final = doc.find_config_set("Mcl")
            if mcl_cfg_final is not None:
                doc.mark_modified(mcl_cfg_final)
                result.modified_elements.append(mcl_cfg_final)

    result.changed_modules.append("uart")
    # Ensure uart appears first (matches historical contract).
    result.changed_modules = (
        ["uart"] + [m for m in result.changed_modules if m != "uart"]
    )
    return result


def _apply_uart_callback(doc: MexDocument, uart_cfg: ET.Element, callback: str) -> None:
    """Set UartCallbackCapability=true and UartCallback[0]=callback.

    Edits happen in-memory (attribute mutations); no raw-bytes splice needed.
    Grounded in uart.json callback_fields: capability_setting=UartCallbackCapability,
    callback_array=UartCallback. The array already contains a <setting name="0" value=""/>
    in the fixture; we update its value attribute directly.
    """
    for el in uart_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "GeneralConfiguration":
            cap = doc.find_child_setting(el, "UartCallbackCapability")
            if cap is not None:
                cap.set("value", "true")
            for arr in el:
                if arr.tag.endswith("array") and arr.attrib.get("name") == "UartCallback":
                    for child in arr:
                        if child.attrib.get("name") == "0":
                            child.set("value", callback)
                            break
            break


def _build_dma_logic_channel_struct_bytes(
    struct_index: int,
    channel_index: int,
    struct_indent: int,
    line_ending: bytes,
) -> bytes:
    """Build raw bytes for one dmaLogicChannel_Type <struct> (RX channel).

    Replicates the EXACT field set and order of dmaLogicChannel_Type_0 in the
    fixture (lines ~592-674 of Uart_Example.mex), with updated Name/LogicName/
    HwChId for the new channel_index and all activation flags set to true
    (EnableGlobalConfig, dmaGlobalRequest_enDmaRequest,
    dmaLogicChannelConfig_enDmaMajorInterrupt).

    Grounded in: fixture dmaLogicChannel_Type_0 field set, Mcl.xdm DMA channel
    schema, uart.json mcl_dma_channel_template.

    ``struct_index``: index of the new struct in the dmaLogicChannel_Type array.
    ``channel_index``: DMA hardware channel index (e.g. 1 for RX).
    Indentation: struct_indent spaces for <struct>, +3/+6/+9 for nested levels.
    """
    le = line_ending.decode("latin-1")
    sp = " " * struct_indent           # struct open/close (e.g. 33 spaces)
    sp1 = " " * (struct_indent + 3)    # direct children (e.g. 36 spaces)
    sp2 = " " * (struct_indent + 6)    # nested struct open/close (e.g. 39 spaces)
    sp3 = " " * (struct_indent + 9)    # nested children (e.g. 42 spaces)
    sp4 = " " * (struct_indent + 12)   # double-nested (e.g. 45 spaces)
    sp5 = " " * (struct_indent + 15)   # triple-nested (e.g. 48 spaces)

    ch_n = channel_index
    # Self-ref path for MinorLoop/MajorLoop link (mirrors fixture pattern: _0 refs itself)
    self_ref = f"/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_{ch_n}"

    lines = [
        f'{sp}<struct name="{struct_index}">',
        f'{sp1}<setting name="Name" value="dmaLogicChannel_Type_{ch_n}"/>',
        f'{sp1}<setting name="dmaLogicChannel_LogicName" value="DMA_LOGIC_CH_{ch_n}"/>',
        f'{sp1}<setting name="dmaLogicChannel_HwInstId" value="DMA_IP_HW_INST_0"/>',
        f'{sp1}<setting name="dmaLogicChannel_HwChId" value="DMA_IP_HW_CH_{ch_n}"/>',
        f'{sp1}<setting name="dmaLogicChannel_InterruptCallback" value="NULL_PTR"/>',
        f'{sp1}<setting name="dmaLogicChannel_ErrorInterruptCallback" value="NULL_PTR"/>',
        f'{sp1}<setting name="dmaLogicChannel_EcucPartitionRef" value=""/>',
        f'{sp1}<setting name="dmaLogicChannel_EnableGlobalConfig" value="true"/>',
        f'{sp1}<setting name="dmaLogicChannel_EnableTransferConfig" value="false"/>',
        f'{sp1}<setting name="dmaLogicChannel_EnableScatterGather" value="false"/>',
        f'{sp1}<struct name="dmaLogicChannel_ConfigType">',
        f'{sp2}<setting name="Name" value="dmaLogicChannel_ConfigType"/>',
        f'{sp2}<struct name="dmaLogicChannel_GlobalConfigType">',
        f'{sp3}<setting name="Name" value="dmaLogicChannel_GlobalConfigType"/>',
        f'{sp3}<struct name="dmaLogicChannelConfig_GlobalControlType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_GlobalControlType"/>',
        f'{sp4}<setting name="dmaGlobalControl_enMasterIdReplication" value="false"/>',
        f'{sp4}<setting name="dmaGlobalControl_enBufferedWrites" value="false"/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_GlobalRequestType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_GlobalRequestType"/>',
        f'{sp4}<setting name="dmaGlobalRequest_enDmaRequest" value="true"/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_GlobalInterruptType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_GlobalInterruptType"/>',
        f'{sp4}<setting name="dmaGlobalInterrupt_enDmaErrorInterrupt" value="false"/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_GlobalPriorityType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_GlobalPriorityType"/>',
        f'{sp4}<setting name="dmaGlobalPriority_GroupPriority" value="DMA_IP_GROUP_PRIO0"/>',
        f'{sp4}<setting name="dmaGlobalPriority_LevelPriority" value="DMA_IP_LEVEL_PRIO0"/>',
        f'{sp4}<setting name="dmaGlobalPriority_enPreemption" value="false"/>',
        f'{sp4}<setting name="dmaGlobalPriority_disPreempt" value="false"/>',
        f'{sp3}</struct>',
        f'{sp2}</struct>',
        f'{sp2}<struct name="dmaLogicChannel_TransferConfigType">',
        f'{sp3}<setting name="Name" value="dmaLogicChannel_TransferConfigType"/>',
        f'{sp3}<struct name="dmaLogicChannelConfig_TransferControlType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_TransferControlType"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enDmaMajorInterrupt" value="true"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enDmaHalfMajorInterrupt" value="false"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_disDmaAutoHwReq" value="false"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enEndOfPacketSignal" value="false"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_bandwidthControl" value="DMA_IP_BWC_ENGINE_NO_STALL"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_DestinationStoreAddressType" value=""/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_TransferSourceType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_TransferSourceType"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_SourceSignedOffsetType" value="0"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_SourceLastAddressAdjustmentType" value="0"/>',
        f'{sp4}<setting name="dmaTransferConfig_TransferSizeType" value="DMA_IP_TRANSFER_SIZE_1_BYTE"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_SourceModuloType" value="0"/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_TransferDestinationType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_TransferDestinationType"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_DestinationSignedOffsetType" value="0"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_DestinationLastAddressAdjustmentType" value="0"/>',
        f'{sp4}<setting name="dmaTransferConfig_TransferSizeType" value="DMA_IP_TRANSFER_SIZE_1_BYTE"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_DestinationModuloType" value="0"/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_TransferMinorLoopType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_TransferMinorLoopType"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enSourceOffset" value="false"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enDestinationOffset" value="false"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_OffsetValueType" value="0"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enMinorLoopLinkCh" value="false"/>',
        f'{sp4}<setting name="dynamic_dmaLogicChannelConfig_MinorLoopLinkChValueType" value="{self_ref}"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_MinorLoopSizeType" value="0"/>',
        f'{sp3}</struct>',
        f'{sp3}<struct name="dmaLogicChannelConfig_TransferMajorLoopType">',
        f'{sp4}<setting name="Name" value="dmaLogicChannelConfig_TransferMajorLoopType"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_enMajorLoopLinkCh" value="false"/>',
        f'{sp4}<setting name="dynamic_dmaLogicChannelConfig_MajorLoopLinkChValueType" value="{self_ref}"/>',
        f'{sp4}<setting name="dmaLogicChannelConfig_MajorLoopCountType" value="0"/>',
        f'{sp3}</struct>',
        f'{sp2}</struct>',
        f'{sp2}<struct name="dmaLogicChannel_ScatterGatherConfigType">',
        f'{sp3}<setting name="Name" value="dmaLogicChannel_ScatterGatherConfigType"/>',
        f'{sp3}<array name="dmaLogicChannelConfig_ScatterGatherArrayType"/>',
        f'{sp2}</struct>',
        f'{sp1}</struct>',
        f'{sp}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _ensure_dma_logic_channel(doc: MexDocument, channel_index: int) -> bool:
    """Ensure a dmaLogicChannel_Type_<N> struct exists in the Mcl dmaLogicChannel_Type array.

    If a struct with Name==dmaLogicChannel_Type_<N> already exists, returns False (no-op).
    Otherwise appends a new struct after the last existing struct.

    Used by DMA mode to add dmaLogicChannel_Type_1 (RX channel).
    Returns True if inserted, False if already present.
    """
    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is None:
        return False

    ch_array = None
    for el in mcl_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "dmaLogicChannel_Type":
            ch_array = el
            break
    if ch_array is None:
        return False

    target_name = f"dmaLogicChannel_Type_{channel_index}"
    existing_structs = [c for c in ch_array if c.tag.endswith("struct")]

    # Idempotency: skip if already present
    for s in existing_structs:
        ns = doc.find_child_setting(s, "Name")
        if ns is not None and ns.attrib.get("value") == target_name:
            return False

    new_struct_index = len(existing_structs)
    line_ending = _detect_line_ending(doc._raw)

    # Detect struct indent from last existing struct
    if existing_structs:
        struct_indent = _detect_struct_indent(doc, existing_structs[-1])
    else:
        struct_indent = 33  # fixture level (30 sp array + 3 = 33 for struct)

    new_struct_bytes = _build_dma_logic_channel_struct_bytes(
        struct_index=new_struct_index,
        channel_index=channel_index,
        struct_indent=struct_indent,
        line_ending=line_ending,
    )

    if existing_structs:
        ok = _append_after_last_element(doc, existing_structs[-1], new_struct_bytes, line_ending)
        if not ok:
            _append_struct_before_array_close(doc, ch_array, new_struct_bytes, line_ending)
    else:
        le = line_ending.decode("latin-1")
        sp_array = " " * (struct_indent - 3)
        array_bytes = (
            f'<array name="dmaLogicChannel_Type">{le}'
            f'{new_struct_bytes.decode("utf-8")}{le}'
            f'{sp_array}</array>'
        ).encode("utf-8")
        doc.replace_element_region(ch_array, array_bytes)

    return True


def _activate_dma_logic_channel_0(doc: MexDocument) -> None:
    """Activate dmaLogicChannel_Type_0 for DMA TX use.

    Sets the three activation flags on the EXISTING dmaLogicChannel_Type_0 struct.
    Flag values are loaded from uart.json mcl_dma_channel_template (not hardcoded)
    to ensure the asset is the single truth source.

    Grounded in fixture lines ~600, ~614, ~632 and uart.json mcl_dma_channel_template.
    """
    asset = _load_uart_asset()
    tmpl = asset.get("mcl_dma_channel_template", {})
    flag_global = tmpl.get("dmaLogicChannel_EnableGlobalConfig", "true")
    flag_req = tmpl.get("dmaGlobalRequest_enDmaRequest", "true")
    flag_irq = tmpl.get("dmaLogicChannelConfig_enDmaMajorInterrupt", "true")

    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is None:
        return

    for arr in mcl_cfg.iter():
        if not (arr.tag.endswith("array") and arr.attrib.get("name") == "dmaLogicChannel_Type"):
            continue
        for ch in arr:
            if not ch.tag.endswith("struct"):
                continue
            ns = doc.find_child_setting(ch, "Name")
            if ns is None or ns.attrib.get("value") != "dmaLogicChannel_Type_0":
                continue
            # Found ch0: update EnableGlobalConfig (from template)
            en_global = doc.find_child_setting(ch, "dmaLogicChannel_EnableGlobalConfig")
            if en_global is not None:
                en_global.set("value", flag_global)
            # Update nested flags (from template)
            for el in ch.iter():
                if el.tag.endswith("setting") and el.attrib.get("name") == "dmaGlobalRequest_enDmaRequest":
                    el.set("value", flag_req)
                if el.tag.endswith("setting") and el.attrib.get("name") == "dmaLogicChannelConfig_enDmaMajorInterrupt":
                    el.set("value", flag_irq)
            break


def _build_dma_channel_ref_array_bytes(
    array_name: str,
    ref_path: str,
    array_indent: int,
    line_ending: bytes,
) -> bytes:
    """Build raw bytes for a populated DMA channel ref array.

    Replaces the self-closed empty ``<array name="UartDmaTxChannelRef"/>`` or
    ``<array name="UartDmaRxChannelRef"/>`` with a populated version containing
    one <setting name="0" value="{ref_path}"/>.

    ``array_indent``: leading spaces before the <array> tag (splice start has
    no leading whitespace -- it is already in the raw bytes before src.start).
    """
    le = line_ending.decode("latin-1")
    sp_child = " " * (array_indent + 3)
    sp_close = " " * array_indent
    lines = [
        f'<array name="{array_name}">',
        f'{sp_child}<setting name="0" value="{ref_path}"/>',
        f'{sp_close}</array>',
    ]
    return le.join(lines).encode("utf-8")


def _ensure_dma_channel_ref_populated(
    doc: MexDocument,
    ref_array: ET.Element,
    ref_path: str,
) -> bool:
    """Populate a DMA channel ref array (Tx or Rx) with one setting entry.

    Idempotent: if the array already contains a child with name="0", no-op.
    Uses replace_element_region to splice the populated array in place.

    Returns True if insertion was made, False if already populated (no-op).
    """
    existing = [c for c in ref_array]
    for child in existing:
        if child.attrib.get("name") == "0":
            return False  # already populated

    # Detect indent of the <array> tag in raw bytes
    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is ref_array), None)
    if src_index is None or not doc._aligned:
        return False

    arr_src = doc._sources[src_index]
    raw = doc._raw
    i = arr_src.start - 1
    while i >= 0 and raw[i:i + 1] not in (b"\n", b"\r"):
        i -= 1
    line_start = i + 1
    spaces = 0
    while line_start + spaces < arr_src.start and raw[line_start + spaces:line_start + spaces + 1] == b" ":
        spaces += 1
    array_indent = spaces

    line_ending = _detect_line_ending(doc._raw)
    array_name = ref_array.attrib.get("name", "")
    new_bytes = _build_dma_channel_ref_array_bytes(
        array_name=array_name,
        ref_path=ref_path,
        array_indent=array_indent,
        line_ending=line_ending,
    )
    doc.replace_element_region(ref_array, new_bytes)
    return True


def _apply_uart_set_dma_phase1(
    doc: MexDocument,
    result: ApplyResult,
    priority: int,
) -> None:
    """Phase 1 (raw-bytes) DMA edits for apply_uart_set DMA mode (RTD-MEX-UART-003).

    Performs three raw-bytes operations (each reloads the tree):
    1. Add dmaLogicChannel_Type_1 (RX DMA channel) to Mcl dmaLogicChannel_Type array.
    2. Insert DMATCD0_IRQn / Dma0_Ch0_IRQHandler Platform ISR (TX DMA complete IRQ).
    3. Insert DMATCD1_IRQn / Dma0_Ch1_IRQHandler Platform ISR (RX DMA complete IRQ).

    The activation flags on dmaLogicChannel_Type_0 (EnableGlobalConfig,
    dmaGlobalRequest_enDmaRequest, dmaLogicChannelConfig_enDmaMajorInterrupt)
    are attribute mutations and happen in Phase 2.

    DMA channel -> ISR/handler mapping loaded from uart.json dma_hw_channel_irq_map
    (not hardcoded). DMA channel ref path loaded from uart.json dma_channel_ref_path_pattern.

    Propagates changed_modules: adds "mcl" and "platform" to result.
    """
    asset = _load_uart_asset()
    dma_map = asset.get("dma_hw_channel_irq_map", {})

    # 1. Add MCL dmaLogicChannel_Type_1 (RX, ch index=1).
    # "mcl" is always added to changed_modules in DMA mode: even on an idempotent
    # re-apply the MCL attribute mutations (MclEnableDma, ch0 flags) are re-written.
    _ensure_dma_logic_channel(doc, channel_index=1)
    if "mcl" not in result.changed_modules:
        result.changed_modules.append("mcl")

    # 2. Insert Platform DMATCD0_IRQn (TX DMA complete)
    ch0_entry = dma_map.get("0") or dma_map.get(0)
    if ch0_entry:
        _ensure_platform_isr(
            doc,
            irq_name=ch0_entry["irq_name"],
            isr_handler=ch0_entry["isr_handler"],
            priority=priority,
        )

    # 3. Insert Platform DMATCD1_IRQn (RX DMA complete)
    ch1_entry = dma_map.get("1") or dma_map.get(1)
    if ch1_entry:
        _ensure_platform_isr(
            doc,
            irq_name=ch1_entry["irq_name"],
            isr_handler=ch1_entry["isr_handler"],
            priority=priority,
        )

    # "platform" is always added in DMA mode: even on idempotent re-apply the
    # platform config_set is marked modified and ISR entries are confirmed present.
    if (ch0_entry or ch1_entry) and "platform" not in result.changed_modules:
        result.changed_modules.append("platform")


def _find_lpuart_ip_channel_detail(doc: MexDocument) -> "ET.Element | None":
    """Re-find the LPUART_IP UartChannel's DetailModuleConfiguration after a tree reload."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return None
    for arr in uart_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "UartChannel":
            for ch in arr:
                if not ch.tag.endswith("struct"):
                    continue
                using = doc.find_child_setting(ch, "UartHwUsing")
                if using is not None and using.attrib.get("value") == "LPUART_IP":
                    return _find_struct(ch, "DetailModuleConfiguration")
    return None


def _populate_uart_dma_refs(doc: MexDocument) -> None:
    """Phase 1 raw-bytes: populate UartDmaTxChannelRef[0] and UartDmaRxChannelRef[0].

    Replaces the self-closed empty arrays with populated versions containing
    one <setting name="0" value="{ref_path}"/> each.
    Idempotent: no-op if already populated.
    Each replace_element_region reloads the tree; re-find between ops.

    Ref paths loaded from uart.json dma_channel_ref_path_pattern (not hardcoded).
    """
    asset = _load_uart_asset()
    ref_pattern = asset.get(
        "dma_channel_ref_path_pattern",
        "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_{index}",
    )
    tx_ref_path = ref_pattern.format(index=0)
    rx_ref_path = ref_pattern.format(index=1)

    # Populate TX ref
    container = _find_lpuart_ip_channel_detail(doc)
    if container is not None:
        for child in container:
            if child.tag.endswith("array") and child.attrib.get("name") == "UartDmaTxChannelRef":
                _ensure_dma_channel_ref_populated(doc, child, tx_ref_path)
                break

    # Re-find after reload, then populate RX ref
    container = _find_lpuart_ip_channel_detail(doc)
    if container is not None:
        for child in container:
            if child.tag.endswith("array") and child.attrib.get("name") == "UartDmaRxChannelRef":
                _ensure_dma_channel_ref_populated(doc, child, rx_ref_path)
                break


def _activate_mcl_dma(doc: MexDocument) -> None:
    """Set MclEnableDma=true and activate dmaLogicChannel_Type_0 flags.

    Pure attribute mutations (no raw-bytes splice). Called in Phase 2.

    1. Sets MclDma/MclEnableDma=true (fixture line ~542: value="false").
    2. Delegates dmaLogicChannel_Type_0 three-flag activation to
       _activate_dma_logic_channel_0.

    Grounded in fixture Mcl MclGeneral/MclDma and uart.json mcl_dma_channel_template.
    """
    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is not None:
        for el in mcl_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "MclDma":
                dma_en = doc.find_child_setting(el, "MclEnableDma")
                if dma_en is not None:
                    dma_en.set("value", "true")
                break
    _activate_dma_logic_channel_0(doc)


def _apply_uart_set_dma_attrs(doc: MexDocument, uart_cfg: "ET.Element | None") -> None:
    """Phase 2 attribute-only DMA mutations for apply_uart_set DMA mode.

    Two attribute mutations only (no replace_element_region):
    1. Set UartDmaEnable=true in Uart GeneralConfiguration.
    2. Set MclEnableDma=true and activate dmaLogicChannel_Type_0 flags in Mcl config.

    Called in Phase 2 of apply_uart_set after ALL raw-bytes splices are done.
    The Tx/Rx ref population is done in Phase 1 (_populate_uart_dma_refs).
    """
    # 1. UartDmaEnable=true in Uart GeneralConfiguration
    cfg = uart_cfg if uart_cfg is not None else doc.find_config_set("Uart")
    if cfg is not None:
        for el in cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "GeneralConfiguration":
                dma_en = doc.find_child_setting(el, "UartDmaEnable")
                if dma_en is not None:
                    dma_en.set("value", "true")
                break

    # 2. MclEnableDma=true + activate dmaLogicChannel_Type_0 flags
    _activate_mcl_dma(doc)


def _find_clock_setting_config_name(doc: MexDocument) -> str:
    """Return the Name of the first McuClockSettingConfig struct (e.g. 'McuClockSettingConfig_0')."""
    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        return "McuClockSettingConfig_0"
    for el in mcu_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "McuClockSettingConfig":
            for child in el:
                if child.tag.endswith("struct"):
                    ns = doc.find_child_setting(child, "Name")
                    if ns is not None:
                        return ns.attrib.get("value", "McuClockSettingConfig_0")
    return "McuClockSettingConfig_0"


def _lpuart_clock_ref_name(hw: str) -> str:
    """Convert LPUART_8 -> LPUART8_CLK (the McuClockReferencePoint Name convention).

    Grounded in the fixture: LPUART_3 -> LPUART3_CLK, FLEXIO -> FLEXIO_CLK.
    """
    text = hw.strip().upper()
    m = re.fullmatch(r"LPUART_?(\d+)", text)
    if m:
        return f"LPUART{m.group(1)}_CLK"
    return f"{text}_CLK"


def _ensure_mcu_clock_ref(
    doc: MexDocument,
    ref_name: str,
    clock_select: str,
) -> bool:
    """Insert a new McuClockReferencePoint struct (idempotent: skip if Name exists).

    Appends the new struct after the last existing struct in the
    McuClockReferencePoint array. McuClockReferencePointFrequency is NOT written
    (ConfigTools computes it -- writing it causes SEVERE).

    Indentation grounded in the fixture: array=33sp, struct=36sp, setting=39sp.

    Returns True if a new struct was inserted, False if already present (no-op).
    """
    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        return False

    ref_array = None
    for el in mcu_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "McuClockReferencePoint":
            ref_array = el
            break
    if ref_array is None:
        return False

    existing_structs = [c for c in ref_array if c.tag.endswith("struct")]

    # Idempotency: skip if already present
    for s in existing_structs:
        ns = doc.find_child_setting(s, "Name")
        if ns is not None and ns.attrib.get("value") == ref_name:
            return False  # already present -- no-op

    new_struct_index = len(existing_structs)
    line_ending = _detect_line_ending(doc._raw)

    new_struct_bytes = _build_mcu_clock_ref_struct_bytes(
        struct_index=new_struct_index,
        name=ref_name,
        clock_select=clock_select,
        struct_indent=36,
        line_ending=line_ending,
    )

    if existing_structs:
        last_struct = existing_structs[-1]
        ok = _append_after_last_element(doc, last_struct, new_struct_bytes, line_ending)
        if not ok:
            # Fallback: try raw regex append before </array>
            _append_struct_before_array_close(doc, ref_array, new_struct_bytes, line_ending)
    else:
        # Empty array case: replace the self-closed or empty array
        le = line_ending.decode("latin-1")
        sp_array = " " * 33
        array_bytes = (
            f'<array name="McuClockReferencePoint">{le}'
            f'{new_struct_bytes.decode("utf-8")}{le}'
            f'{sp_array}</array>'
        ).encode("utf-8")
        doc.replace_element_region(ref_array, array_bytes)

    return True  # insertion was made


def _build_mcu_clock_ref_struct_bytes(
    struct_index: int,
    name: str,
    clock_select: str,
    struct_indent: int,
    line_ending: bytes,
) -> bytes:
    """Build raw bytes for one McuClockReferencePoint <struct>.

    Field set grounded in uart.json and Mcu.xdm: Name + McuClockFrequencySelect.
    McuClockReferencePointFrequency is NOT written (ConfigTools computes it).
    """
    le = line_ending.decode("latin-1")
    sp_struct = " " * struct_indent
    sp_child = " " * (struct_indent + 3)
    lines = [
        f'{sp_struct}<struct name="{struct_index}">',
        f'{sp_child}<setting name="Name" value="{name}"/>',
        f'{sp_child}<setting name="McuClockFrequencySelect" value="{clock_select}"/>',
        f'{sp_struct}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _ensure_platform_isr(
    doc: MexDocument,
    irq_name: str,
    isr_handler: str,
    priority: int,
) -> bool:
    """Insert a new PlatformIsrConfig struct (idempotent: skip if IsrName exists).

    Appends after the last existing struct in the PlatformIsrConfig array.
    The Name field is PlatformIsrConfig_<next_index>.
    Indentation grounded in the fixture: struct=33sp, setting=36sp.

    Returns True if a new struct was inserted, False if already present (no-op).
    """
    platform_cfg = doc.find_config_set("Platform")
    if platform_cfg is None:
        return False

    isr_array = None
    for el in platform_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "PlatformIsrConfig":
            isr_array = el
            break
    if isr_array is None:
        return False

    existing_structs = [c for c in isr_array if c.tag.endswith("struct")]

    # Idempotency: skip if already present
    for s in existing_structs:
        ns = doc.find_child_setting(s, "IsrName")
        if ns is not None and ns.attrib.get("value") == irq_name:
            return False  # already present -- no-op

    new_struct_index = len(existing_structs)
    line_ending = _detect_line_ending(doc._raw)

    new_struct_bytes = _build_platform_isr_struct_bytes(
        struct_index=new_struct_index,
        irq_name=irq_name,
        isr_handler=isr_handler,
        priority=priority,
        struct_indent=33,
        line_ending=line_ending,
    )

    if existing_structs:
        last_struct = existing_structs[-1]
        ok = _append_after_last_element(doc, last_struct, new_struct_bytes, line_ending)
        if not ok:
            _append_struct_before_array_close(doc, isr_array, new_struct_bytes, line_ending)
    else:
        # Empty array case: replace with populated array
        le = line_ending.decode("latin-1")
        sp_array = " " * 30
        array_bytes = (
            f'<array name="PlatformIsrConfig">{le}'
            f'{new_struct_bytes.decode("utf-8")}{le}'
            f'{sp_array}</array>'
        ).encode("utf-8")
        doc.replace_element_region(isr_array, array_bytes)

    return True  # insertion was made


def _build_platform_isr_struct_bytes(
    struct_index: int,
    irq_name: str,
    isr_handler: str,
    priority: int,
    struct_indent: int,
    line_ending: bytes,
) -> bytes:
    """Build raw bytes for one PlatformIsrConfig <struct>.

    Field set grounded in uart.json / Platform.xdm/.epd fixture:
    Name, IsrName, IsrEnabled, IsrPriority, IsrHandler.
    """
    le = line_ending.decode("latin-1")
    sp_struct = " " * struct_indent
    sp_child = " " * (struct_indent + 3)
    config_name = f"PlatformIsrConfig_{struct_index}"
    lines = [
        f'{sp_struct}<struct name="{struct_index}">',
        f'{sp_child}<setting name="Name" value="{config_name}"/>',
        f'{sp_child}<setting name="IsrName" value="{irq_name}"/>',
        f'{sp_child}<setting name="IsrEnabled" value="true"/>',
        f'{sp_child}<setting name="IsrPriority" value="{priority}"/>',
        f'{sp_child}<setting name="IsrHandler" value="{isr_handler}"/>',
        f'{sp_struct}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _append_struct_before_array_close(
    doc: MexDocument,
    array_el: ET.Element,
    new_bytes: bytes,
    line_ending: bytes,
) -> None:
    """Fallback: insert new_bytes before the </array> close tag using raw bytes.

    Used when _append_after_last_element fails (e.g. alignment mismatch).
    Finds the array element's region in raw bytes, locates the last </array>
    close tag, and inserts new_bytes on the preceding line.
    """
    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is array_el), None)
    if src_index is None or not doc._aligned:
        return
    src = doc._sources[src_index]
    span_end = doc._find_element_region_end(src, array_el)
    if span_end is None:
        return
    parent_raw = doc._raw[src.start: span_end + 1]
    close_tag = b"</array>"
    close_pos = parent_raw.rfind(close_tag)
    if close_pos < 0:
        return
    line_start = close_pos
    while line_start > 0 and parent_raw[line_start - 1:line_start] not in (b"\n", b"\r"):
        line_start -= 1
    new_parent_raw = (
        parent_raw[:line_start]
        + new_bytes
        + line_ending
        + parent_raw[line_start:]
    )
    doc.replace_element_region(array_el, new_parent_raw)


def _find_struct(parent: ET.Element, name: str) -> ET.Element | None:
    for struct in parent.iter():
        if struct.tag.endswith("struct") and struct.attrib.get("name") == name:
            return struct
    return None


def _derive_isr_name(peripheral: str) -> str | None:
    """Map a peripheral to its PlatformIsrConfig IsrName (asset patterns).

    Grounded in the Platform asset / fixture: ``LPUART_<n>`` -> ``LPUART<n>_IRQn``
    and any ``FLEXIO*`` -> the single shared ``FLEXIO_IRQn``. Returns None when
    the peripheral does not match a known pattern; the caller still verifies the
    derived name exists in the project before editing, so this never invents an
    interrupt entry.
    """
    text = peripheral.strip().upper()
    match = re.fullmatch(r"LPUART_?(\d+)", text)
    if match is not None:
        return f"LPUART{match.group(1)}_IRQn"
    if text.startswith("FLEXIO"):
        return "FLEXIO_IRQn"
    return None


def _find_isr_entry(
    doc: MexDocument,
    platform_cfg: ET.Element,
    *,
    isr_name: str | None,
) -> ET.Element | None:
    """Return the PlatformIsrConfig <struct> whose IsrName equals ``isr_name``."""
    if isr_name is None:
        return None
    for array in platform_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "PlatformIsrConfig"):
            continue
        for entry in array:
            if not entry.tag.endswith("struct"):
                continue
            name_setting = doc.find_child_setting(entry, "IsrName")
            if name_setting is not None and name_setting.attrib.get("value") == isr_name:
                return entry
    return None


def _available_isr_names(doc: MexDocument, platform_cfg: ET.Element) -> list[str]:
    names: list[str] = []
    for array in platform_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "PlatformIsrConfig"):
            continue
        for entry in array:
            if not entry.tag.endswith("struct"):
                continue
            name_setting = doc.find_child_setting(entry, "IsrName")
            if name_setting is not None and name_setting.attrib.get("value"):
                names.append(name_setting.attrib["value"])
    return names


def apply_platform_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply an owned Platform interrupt edit (priority / enable) in place.

    Edits an EXISTING ``PlatformIsrConfig`` entry only; it never creates an
    interrupt. The entry is located by explicit ``isr_name`` or by deriving the
    IsrName from ``peripheral`` (then verifying it exists). ``IsrPriority`` is set
    and the entry is ensured enabled; the device-specific upper priority bound is
    enforced by the vendor gate (Platform.xdm ``irqMaxPrio``), so the provider
    only rejects a negative priority here.
    """
    payload = intent.payload
    result = ApplyResult()

    isr_name = payload.get("isr_name")
    peripheral = payload.get("peripheral")
    if isr_name is None and peripheral is not None:
        isr_name = _derive_isr_name(peripheral)

    priority = payload.get("priority")
    if priority is not None and priority < 0:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="platform_priority_out_of_range",
            module="platform",
            message=(
                f"Interrupt priority {priority} is invalid; IsrPriority must be "
                ">= 0 (and <= the device's Platform.irqMaxPrio, enforced by "
                "S32DS validation)."
            ),
            details={"priority": priority},
        ))
        return result

    platform_cfg = doc.find_config_set("Platform")
    if platform_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="platform_config_set_not_found",
            module="platform",
            message="No enabled Platform <config_set> found; M1 edits existing instances only.",
            details={},
        ))
        return result

    entry = _find_isr_entry(doc, platform_cfg, isr_name=isr_name)
    if entry is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="platform_isr_not_found",
            module="platform",
            message=(
                "No existing PlatformIsrConfig entry matches the requested "
                "interrupt; M1 does not create interrupt entries."
            ),
            details={
                "requested_isr_name": isr_name,
                "peripheral": peripheral,
                "available": _available_isr_names(doc, platform_cfg),
            },
        ))
        return result

    if priority is not None:
        prio_setting = doc.find_child_setting(entry, "IsrPriority")
        if prio_setting is not None:
            prio_setting.set("value", str(priority))

    # The interrupt must be enabled and its ISR registered for the case to pass;
    # ensure enabled (the handler is already registered on an existing entry).
    enabled_setting = doc.find_child_setting(entry, "IsrEnabled")
    if enabled_setting is not None:
        enabled_setting.set("value", "true")

    doc.mark_modified(entry)
    carrier = doc.find_nearest_quick_selection_ancestor(entry)
    if carrier is not None:
        doc.mark_modified(carrier)

    result.changed_modules.append("platform")
    result.modified_elements.append(entry)
    return result


def _detect_line_ending(raw: bytes) -> bytes:
    """Return the file's dominant line ending as bytes (b'\\r\\n' or b'\\n')."""
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    return b"\r\n" if crlf >= lf else b"\n"


def _find_mcu_clock_ref_path(
    doc: MexDocument,
    mcu_cfg: ET.Element,
) -> "tuple[str, None] | tuple[None, Diagnostic]":
    """Discover the McuClockReferencePoint path to use for OsIfSystemTimerClockRef.

    Searches the Mcu config_set's ``McuClockSettingConfig*`` container for a
    ``McuClockReferencePoint`` array, then picks the reference point whose
    ``McuClockFrequencySelect`` equals ``CORE_CLK`` (preferred); if none has
    ``CORE_CLK``, picks the first reference point. Returns a tuple of
    ``(ref_path, None)`` on success, or ``(None, Diagnostic)`` when no reference
    points are found at all (caller must propagate the blocker).

    Path format: ``/Mcu/Mcu/McuModuleConfiguration/<ClockSettingName>/<PointName>``
    where ``<ClockSettingName>`` is the ``Name`` setting of the
    ``McuClockSettingConfig`` struct (e.g. ``McuClockSettingConfig_0``) and
    ``<PointName>`` is the ``Name`` setting of the chosen
    ``McuClockReferencePoint`` struct (e.g. ``FLEXIO_CLK``).

    Grounded in the fixture: McuClockSettingConfig_0 has LPUART3_CLK
    (AIPS_SLOW_CLK) and FLEXIO_CLK (CORE_CLK); CORE_CLK preferred -> FLEXIO_CLK.
    """
    for el in mcu_cfg.iter():
        if not (el.tag.endswith("array") and el.attrib.get("name") == "McuClockSettingConfig"):
            continue
        for clock_struct in el:
            if not clock_struct.tag.endswith("struct"):
                continue
            # Resolve the struct's Name setting (e.g. "McuClockSettingConfig_0")
            name_setting = doc.find_child_setting(clock_struct, "Name")
            clock_setting_name = (
                name_setting.attrib.get("value", "") if name_setting is not None else ""
            )
            # Find the McuClockReferencePoint array inside this clock setting struct
            for child in clock_struct.iter():
                if not (
                    child.tag.endswith("array")
                    and child.attrib.get("name") == "McuClockReferencePoint"
                ):
                    continue
                ref_structs = [c for c in child if c.tag.endswith("struct")]
                if not ref_structs:
                    break  # empty array in this clock setting; keep searching

                # Prefer the ref point with McuClockFrequencySelect == CORE_CLK
                chosen = None
                for rs in ref_structs:
                    freq_sel = doc.find_child_setting(rs, "McuClockFrequencySelect")
                    if freq_sel is not None and freq_sel.attrib.get("value") == "CORE_CLK":
                        chosen = rs
                        break
                if chosen is None:
                    chosen = ref_structs[0]

                point_name_setting = doc.find_child_setting(chosen, "Name")
                point_name = (
                    point_name_setting.attrib.get("value", "") if point_name_setting is not None else ""
                )
                ref_path = (
                    f"/Mcu/Mcu/McuModuleConfiguration/{clock_setting_name}/{point_name}"
                )
                return ref_path, None

    # No McuClockReferencePoint found in any clock setting config
    return None, Diagnostic(
        severity="blocker",
        code="basenxp_no_clock_reference_point",
        module="basenxp",
        message=(
            "No McuClockReferencePoint found in the Mcu config set. "
            "OsIfSystemTimerClockRef requires an existing Mcu clock reference point. "
            "Add at least one McuClockReferencePoint to the Mcu McuClockSettingConfig "
            "before enabling the BaseNXP OsIf system timer."
        ),
        details={},
    )


def _build_counter_array_bytes(
    indent: int,
    line_ending: bytes,
    clock_ref_path: str,
) -> bytes:
    """Build the populated OsIfCounterConfig array block as raw bytes.

    The returned bytes replace the self-closed ``<array name="OsIfCounterConfig"/>``
    tag verbatim in the raw file. Because ``replace_element_region`` splices
    starting exactly at the ``<`` character, the leading ``indent`` spaces are
    already present in the raw before the splice point and must NOT be repeated
    in the first line. Inner lines do carry their full indentation.

    Grounded in the BaseNXP osif.json asset (verified against vendor .mex examples):
    - counter Name: OsIfCounterConfig_0
    - OsIfSystemTimerClockRef: populated array referencing an existing Mcu
      McuClockReferencePoint (CORE_CLK preferred, else first available).
    - OsIfSystemTimerClockFreq: empty array (ConfigTools type: ArraySetting; a
      scalar <setting> is silently rejected by ConfigTools, causing SEVERE).
    - Children order: Name, OsIfCounterEcucPartitionRef, OsIfSystemTimerClockRef,
      OsIfSystemTimerClockFreq, OsIfOsCounterRef
    """
    le = line_ending.decode("latin-1")
    sp1 = " " * (indent + 3)  # 30 spaces for <struct>
    sp2 = " " * (indent + 6)  # 33 spaces for children
    sp3 = " " * (indent + 9)  # 36 spaces for array child
    sp = " " * indent          # 27 spaces for closing </array>

    # First line: no leading spaces (they come from raw before src.start)
    lines = [
        '<array name="OsIfCounterConfig">',
        f'{sp1}<struct name="0">',
        f'{sp2}<setting name="Name" value="OsIfCounterConfig_0"/>',
        f'{sp2}<array name="OsIfCounterEcucPartitionRef"/>',
        f'{sp2}<array name="OsIfSystemTimerClockRef">',
        f'{sp3}<setting name="0" value="{clock_ref_path}"/>',
        f'{sp2}</array>',
        f'{sp2}<array name="OsIfSystemTimerClockFreq"/>',
        f'{sp2}<array name="OsIfOsCounterRef"/>',
        f'{sp1}</struct>',
        f'{sp}</array>',
    ]
    return le.join(lines).encode("utf-8")


def apply_basenxp_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply owned BaseNXP/OsIf edits: enable system timer and insert one counter.

    Edits are grounded in the BaseNXP osif.json asset (derived from BaseNXP.xdm)
    and the Mcu config set (for OsIfSystemTimerClockRef path discovery).
    Two changes are made:
    1. Set OsIfUseSystemTimer from false -> true (attribute edit on existing element).
    2. If OsIfCounterConfig is an empty self-closed array, replace it with a
       populated array containing exactly one counter struct (element insertion via
       replace_element_region). The counter's OsIfSystemTimerClockRef is populated
       with a dynamically-discovered McuClockReferencePoint path (CORE_CLK preferred).

    Idempotent: if a counter already exists, a second counter is NOT added.
    Returns a blocker Diagnostic if the BaseNXP config set is not found or if no
    McuClockReferencePoint exists in the Mcu config set.
    """
    result = ApplyResult()

    if not intent.payload.get("enable_system_timer", False):
        # Nothing requested; return empty result (no-op).
        return result

    basenxp_cfg = doc.find_config_set("BaseNXP")
    if basenxp_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="basenxp_config_set_not_found",
            module="basenxp",
            message="No enabled BaseNXP <config_set> found; cannot enable OsIf system timer.",
            details={},
        ))
        return result

    # ---- Step 1: Populate OsIfCounterConfig if currently empty ----
    # Do this BEFORE the timer attribute edit so that replace_element_region
    # (which reloads the tree) does not discard the timer_setting mutation.
    counter_array = _find_osif_counter_array(doc, basenxp_cfg)
    if counter_array is not None:
        existing_structs = [c for c in counter_array if c.tag.endswith("struct")]
        if len(existing_structs) == 0:
            # Discover the Mcu clock reference path before splicing.
            mcu_cfg = doc.find_config_set("Mcu")
            if mcu_cfg is None:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="basenxp_no_clock_reference_point",
                    module="basenxp",
                    message=(
                        "No Mcu <config_set> found; cannot discover a "
                        "McuClockReferencePoint for OsIfSystemTimerClockRef."
                    ),
                    details={},
                ))
                return result

            clock_ref_path, diag = _find_mcu_clock_ref_path(doc, mcu_cfg)
            if diag is not None:
                result.diagnostics.append(diag)
                return result

            # Self-closed empty array -> replace with populated version.
            line_ending = _detect_line_ending(doc._raw)
            new_bytes = _build_counter_array_bytes(
                indent=27,
                line_ending=line_ending,
                clock_ref_path=clock_ref_path,
            )
            doc.replace_element_region(counter_array, new_bytes)

            # After replace_element_region the tree is reloaded; re-find everything.
            basenxp_cfg = doc.find_config_set("BaseNXP")
            if basenxp_cfg is not None:
                counter_array = _find_osif_counter_array(doc, basenxp_cfg)
        # else: already has counters -- idempotent, do not add a second

    # ---- Step 2: Set OsIfUseSystemTimer = true (attribute edit on fresh ref) ----
    timer_setting = doc.find_child_setting(basenxp_cfg, "OsIfUseSystemTimer") \
        if basenxp_cfg is not None else None
    if timer_setting is not None:
        timer_setting.set("value", "true")

    # Mark modified elements and strip stale quick_selection from nearest ancestor.
    modified: list[ET.Element] = []
    if timer_setting is not None:
        doc.mark_modified(timer_setting)
        carrier = doc.find_nearest_quick_selection_ancestor(timer_setting)
        if carrier is not None:
            doc.mark_modified(carrier)
        modified.append(timer_setting)

    if counter_array is not None:
        doc.mark_modified(counter_array)
        carrier = doc.find_nearest_quick_selection_ancestor(counter_array)
        if carrier is not None:
            doc.mark_modified(carrier)
        modified.append(counter_array)

    result.changed_modules.append("basenxp")
    result.modified_elements.extend(modified)
    return result


def _find_osif_counter_array(doc: MexDocument, basenxp_cfg: ET.Element) -> ET.Element | None:
    for el in basenxp_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "OsIfCounterConfig":
            return el
    return None


# ---------------------------------------------------------------------------
# Mcl: FlexIO logic-channel insertion
# ---------------------------------------------------------------------------

def _find_flexio_channels_array(
    doc: MexDocument,
    mcl_cfg: ET.Element,
) -> "ET.Element | None":
    """Return the FlexioMclLogicChannels array inside the first FlexioCommon struct."""
    for el in mcl_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "FlexioMclLogicChannels":
            return el
    return None


def _extract_channel_index(value: str) -> int | None:
    """Parse a CHANNEL_N enum value to its integer index N. Returns None on failure."""
    if value.startswith("CHANNEL_"):
        try:
            return int(value[len("CHANNEL_"):])
        except ValueError:
            pass
    return None


def _extract_pin_index(value: str) -> int | None:
    """Parse a PIN_N enum value to its integer index N. Returns None on failure."""
    if value.startswith("PIN_"):
        try:
            return int(value[len("PIN_"):])
        except ValueError:
            pass
    return None


def _build_flexio_channel_struct_bytes(
    struct_index: int,
    channel_id: str,
    pin_id: str,
    channel_name: str,
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build the raw bytes for one new FlexioMclLogicChannels <struct>.

    The returned bytes represent the complete struct (open tag + settings +
    close tag). They will be appended after the last existing struct's bytes,
    separated by a line ending.

    ``indent`` is the number of leading spaces before the ``<struct>`` tag;
    settings are indented by ``indent + 3`` spaces.

    Children order from Mcl.xdm (verified in mcl.json asset):
      Name, FlexioMclChannelId, FlexioMclPinId,
      FlexioMclAddPinEnable, FlexioMclAddPinId,
      FlexioMclAddChannelEnable, FlexioMclAddChannelId
    """
    le = line_ending.decode("latin-1")
    sp_struct = " " * indent
    sp_child = " " * (indent + 3)
    lines = [
        f'{sp_struct}<struct name="{struct_index}">',
        f'{sp_child}<setting name="Name" value="{channel_name}"/>',
        f'{sp_child}<setting name="FlexioMclChannelId" value="{channel_id}"/>',
        f'{sp_child}<setting name="FlexioMclPinId" value="{pin_id}"/>',
        f'{sp_child}<setting name="FlexioMclAddPinEnable" value="false"/>',
        f'{sp_child}<setting name="FlexioMclAddPinId" value="PIN_0"/>',
        f'{sp_child}<setting name="FlexioMclAddChannelEnable" value="false"/>',
        f'{sp_child}<setting name="FlexioMclAddChannelId" value="CHANNEL_0"/>',
        f'{sp_struct}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _detect_struct_indent(doc: MexDocument, struct: ET.Element) -> int:
    """Detect the number of leading spaces before ``struct``'s start tag in the raw bytes.

    Uses the expat-captured source span: walks backward from src.start to find
    the previous newline, then counts spaces from newline+1 to src.start.
    """
    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is struct), None)
    if src_index is None or not doc._aligned:
        return 36  # sane fallback (matches fixture indent level)
    src = doc._sources[src_index]
    raw = doc._raw
    # Walk backward from src.start to find the start of the line
    i = src.start - 1
    while i >= 0 and raw[i:i + 1] not in (b"\n", b"\r"):
        i -= 1
    line_start = i + 1
    spaces = 0
    while line_start + spaces < src.start and raw[line_start + spaces:line_start + spaces + 1] == b" ":
        spaces += 1
    return spaces


def apply_mcl_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply an owned Mcl edit: append one FlexIO logic channel to FlexioMclLogicChannels.

    Intent payload must carry ``add_flexio_logic_channel`` (string: the new
    channel's Name). The next-available struct index, FlexioMclChannelId, and
    FlexioMclPinId are computed dynamically from the existing entries to satisfy
    the Mcl.xdm uniqueness constraint (no hardcoded indices).

    Idempotent: if a channel with the same Name already exists, returns without
    modifying the document (no-op, no error).

    Returns a blocker Diagnostic if:
    - No Mcl <config_set> is found.
    - No FlexioCommon container (and thus no FlexioMclLogicChannels array) exists.
    """
    result = ApplyResult()
    channel_name = intent.payload.get("add_flexio_logic_channel")
    if not channel_name:
        return result  # nothing requested -- no-op

    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="mcl_config_set_not_found",
            module="mcl",
            message="No enabled Mcl <config_set> found; cannot add FlexIO logic channel.",
            details={},
        ))
        return result

    channels_array = _find_flexio_channels_array(doc, mcl_cfg)
    if channels_array is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="mcl_flexio_common_not_found",
            module="mcl",
            message=(
                "No FlexioMclLogicChannels array found under a FlexioCommon struct in "
                "the Mcl config set; cannot add FlexIO logic channel. Ensure "
                "MclEnableFlexioCommon is true and a FlexioCommon entry exists."
            ),
            details={},
        ))
        return result

    existing_structs = [c for c in channels_array if c.tag.endswith("struct")]

    # Idempotency: do not add a duplicate if the name already exists.
    for struct in existing_structs:
        name_setting = doc.find_child_setting(struct, "Name")
        if name_setting is not None and name_setting.attrib.get("value") == channel_name:
            return result  # already present -- silent no-op

    # Compute next-available indices dynamically.
    # struct name = count of existing structs (sequential 0-based).
    new_struct_index = len(existing_structs)

    # FlexioMclChannelId: max existing channel index + 1
    max_channel = -1
    for struct in existing_structs:
        ch_setting = doc.find_child_setting(struct, "FlexioMclChannelId")
        if ch_setting is not None:
            idx = _extract_channel_index(ch_setting.attrib.get("value", ""))
            if idx is not None and idx > max_channel:
                max_channel = idx
    new_channel_id = f"CHANNEL_{max_channel + 1}"

    # FlexioMclPinId: max existing pin index + 1
    max_pin = -1
    for struct in existing_structs:
        pin_setting = doc.find_child_setting(struct, "FlexioMclPinId")
        if pin_setting is not None:
            idx = _extract_pin_index(pin_setting.attrib.get("value", ""))
            if idx is not None and idx > max_pin:
                max_pin = idx
    new_pin_id = f"PIN_{max_pin + 1}"

    # Detect indentation from the last existing struct to match sibling formatting.
    last_struct = existing_structs[-1] if existing_structs else None
    if last_struct is not None:
        struct_indent = _detect_struct_indent(doc, last_struct)
    else:
        struct_indent = 36  # fallback: fixture level

    line_ending = _detect_line_ending(doc._raw)

    new_struct_bytes = _build_flexio_channel_struct_bytes(
        struct_index=new_struct_index,
        channel_id=new_channel_id,
        pin_id=new_pin_id,
        channel_name=channel_name,
        indent=struct_indent,
        line_ending=line_ending,
    )

    if last_struct is not None:
        # Insertion strategy (a): replace the last existing struct's region with
        # [itself] + line_ending + [new struct bytes].
        # First capture the last struct's raw bytes via its element region.
        elements = list(doc.root.iter())
        last_src_index = next(
            (i for i, e in enumerate(elements) if e is last_struct), None
        )
        if last_src_index is None or not doc._aligned:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="mcl_struct_not_aligned",
                module="mcl",
                message="Could not locate last FlexioMclLogicChannels struct in raw bytes.",
                details={},
            ))
            return result

        last_src = doc._sources[last_src_index]
        # Find the end of the last struct's region in the raw bytes.
        # We need to call the document's internal helper via replace_element_region's
        # own logic -- but we want the original bytes, not to trigger a replace.
        # Use the document's _find_element_region_end to get span_end.
        span_end = doc._find_element_region_end(last_src, last_struct)
        if span_end is None:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="mcl_struct_region_end_not_found",
                module="mcl",
                message="Could not determine byte region of last FlexioMclLogicChannels struct.",
                details={},
            ))
            return result

        # Extract the original last-struct bytes verbatim from raw.
        last_struct_raw = doc._raw[last_src.start: span_end + 1]

        # Build replacement: original last struct + line_ending + new struct bytes
        combined = last_struct_raw + line_ending + new_struct_bytes

        # replace_element_region splices starting at last_src.start and ending at span_end.
        # We need to pass the live element reference (last_struct) -- but after
        # _capture_sources(), the element reference is still valid before the splice.
        doc.replace_element_region(last_struct, combined)
    else:
        # Empty array case: replace the self-closed array with a populated one.
        # (should not occur given the fixture, but handles empty FlexioMclLogicChannels)
        le = line_ending.decode("latin-1")
        array_indent = struct_indent - 3  # array is one level above struct
        sp_array = " " * array_indent
        array_bytes = (
            f'<array name="FlexioMclLogicChannels">{le}'
            f'{new_struct_bytes.decode("utf-8")}{le}'
            f'{sp_array}</array>'
        ).encode("utf-8")
        doc.replace_element_region(channels_array, array_bytes)

    # After replace_element_region the tree is reloaded; re-find the Mcl config.
    mcl_cfg = doc.find_config_set("Mcl")
    channels_array = _find_flexio_channels_array(doc, mcl_cfg) if mcl_cfg is not None else None

    # Mark modified: the channels array and its nearest quick_selection ancestor.
    modified: list[ET.Element] = []
    if channels_array is not None:
        doc.mark_modified(channels_array)
        carrier = doc.find_nearest_quick_selection_ancestor(channels_array)
        if carrier is not None:
            doc.mark_modified(carrier)
        modified.append(channels_array)

    result.changed_modules.append("mcl")
    result.modified_elements.extend(modified)
    return result


# ---------------------------------------------------------------------------
# Port: LPUART TX/RX pin-routing insertion
# ---------------------------------------------------------------------------

# Package element text -> pins.json field mapping (grounded in portpin.json asset)
_PACKAGE_PIN_FIELD: dict[str, str] = {
    "S32K344_257BGA": "pin_mapbga257",
    "S32K344_172HDQFP": "pin_hdqfp172",
}
_DEFAULT_PIN_FIELD = "pin_mapbga257"


def _load_pins_data() -> list[dict]:
    """Load committed pins.json asset. Never reads .xdm at runtime."""
    pins_path = _ASSET_ROOT / "nxp" / "s32k3" / "port" / "pins.json"
    data = json.loads(pins_path.read_text(encoding="utf-8"))
    return data["signals"]


def _normalize_peripheral_id(peripheral: str) -> str:
    """LPUART_0 -> LPUART0 (asset-internal form)."""
    return re.sub(r"_(\d+)$", r"\1", peripheral.strip().upper())


def _detect_package_pin_field(doc: MexDocument) -> str:
    """Read <common><package> from the .mex and return the pins.json field name."""
    for el in doc.root.iter():
        if el.tag.endswith("package") and el.text:
            pkg = el.text.strip()
            return _PACKAGE_PIN_FIELD.get(pkg, _DEFAULT_PIN_FIELD)
    return _DEFAULT_PIN_FIELD


def _legal_pins_for_signal(
    signals: list[dict],
    peripheral_id: str,
    signal_suffix: str,
) -> list[dict]:
    """Return all pins.json records where peripheral==peripheral_id and signal==signal_suffix.

    ``signal_suffix`` is the short signal name from the asset, e.g. 'TX', 'RX'.
    Matching is case-insensitive.
    """
    target_signal = signal_suffix.upper()
    return [
        s for s in signals
        if s.get("peripheral", "").upper() == peripheral_id
        and s.get("signal", "").upper() == target_signal
    ]


def _find_pin_record(
    signals: list[dict],
    peripheral_id: str,
    signal_suffix: str,
    pin_signal: str,
) -> dict | None:
    """Return the pins.json record for a specific peripheral+signal+pin combination."""
    target_signal = signal_suffix.upper()
    target_pin = pin_signal.upper()
    for s in signals:
        if (
            s.get("peripheral", "").upper() == peripheral_id
            and s.get("signal", "").upper() == target_signal
            and s.get("pin", "").upper() == target_pin
        ):
            return s
    return None


def _find_port_function_pins_el(doc: MexDocument) -> ET.Element | None:
    """Return the <pins> element inside the PortContainer_0_VS_0 function."""
    for el in doc.root.iter():
        if (
            el.tag.endswith("function")
            and el.attrib.get("name") == "PortContainer_0_VS_0"
        ):
            for child in el:
                if child.tag.endswith("pins"):
                    return child
    return None


def _is_pin_already_configured(
    pins_el: ET.Element,
    peripheral_id: str,
    signal_attr: str,
) -> bool:
    """Return True if a <pin> with the given peripheral and signal already exists."""
    for child in pins_el:
        if (
            child.tag.endswith("pin")
            and child.attrib.get("peripheral") == peripheral_id
            and child.attrib.get("signal") == signal_attr
        ):
            return True
    return False


def _is_portpin_struct_already_configured(
    portpin_array: ET.Element,
    doc: MexDocument,
    name: str,
) -> bool:
    """Return True if a PortPin struct with the given Name already exists."""
    for child in portpin_array:
        if child.tag.endswith("struct"):
            name_setting = doc.find_child_setting(child, "Name")
            if name_setting is not None and name_setting.attrib.get("value") == name:
                return True
    return False


def _build_pin_header_tx_bytes(
    peripheral_id: str,
    signal_attr: str,
    pin_num: str,
    pin_signal: str,
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build bytes for a TX <pin> entry with direction=OUTPUT feature.

    Grounded in portpin.json and fixture lines 46-50 (LPUART3 TX pattern).
    """
    le = line_ending.decode("latin-1")
    sp = " " * indent
    sp2 = " " * (indent + 3)
    sp3 = " " * (indent + 6)
    lines = [
        f'{sp}<pin peripheral="{peripheral_id}" signal="{signal_attr}" pin_num="{pin_num}" pin_signal="{pin_signal}">',
        f'{sp2}<pin_features>',
        f'{sp3}<pin_feature name="direction" value="OUTPUT"/>',
        f'{sp2}</pin_features>',
        f'{sp}</pin>',
    ]
    return le.join(lines).encode("utf-8")


def _build_pin_header_rx_bytes(
    peripheral_id: str,
    signal_attr: str,
    pin_num: str,
    pin_signal: str,
    indent: int,
) -> bytes:
    """Build bytes for an RX <pin> self-closed entry (input-only, no direction).

    Grounded in portpin.json and fixture line 45 (LPUART3 RX pattern).
    """
    sp = " " * indent
    return (
        f'{sp}<pin peripheral="{peripheral_id}" signal="{signal_attr}"'
        f' pin_num="{pin_num}" pin_signal="{pin_signal}"/>'
    ).encode("utf-8")


def _build_portpin_struct_bytes(
    struct_index: int,
    portpin_name: str,
    portpin_id: int,
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build the raw bytes for one new PortPin <struct>.

    Field set and order grounded in portpin.json (derived from Port.xdm and the
    Uart_Example_S32K344 fixture Lpuart3_Tx/Lpuart3_Rx structs).
    All settings use safe defaults from the asset.
    """
    le = line_ending.decode("latin-1")
    sp_struct = " " * indent
    sp_child = " " * (indent + 3)
    lines = [
        f'{sp_struct}<struct name="{struct_index}">',
        f'{sp_child}<setting name="Name" value="{portpin_name}"/>',
        f'{sp_child}<setting name="PortPinPue" value="false"/>',
        f'{sp_child}<setting name="PortPinPus" value="false"/>',
        f'{sp_child}<setting name="PortPinSafeMode" value="false"/>',
        f'{sp_child}<setting name="PortPinDse" value="false"/>',
        f'{sp_child}<setting name="PortPinWithReadBack" value="false"/>',
        f'{sp_child}<setting name="PortPinPke" value="false"/>',
        f'{sp_child}<setting name="PortPinIfe" value="false"/>',
        f'{sp_child}<setting name="PortPinDirectionChangeable" value="true"/>',
        f'{sp_child}<setting name="PortPinModeChangeable" value="true"/>',
        f'{sp_child}<setting name="PortPinInvertControl" value="false"/>',
        f'{sp_child}<setting name="PortPinSiul2Instance" value="SIUL2_0"/>',
        f'{sp_child}<setting name="PortPinId" value="{portpin_id}"/>',
        f'{sp_child}<setting name="PortPinInitialMode" value="PORT_GPIO_MODE"/>',
        f'{sp_child}<setting name="OBEGroupSelect" value="NO_OBE_GROUP"/>',
        f'{sp_child}<setting name="MscrPdacSlot" value="VIRTUAL_WRAPPER_PDAC0"/>',
        f'{sp_child}<setting name="ImcrPdacSlot" value="VIRTUAL_WRAPPER_PDAC0"/>',
        f'{sp_child}<array name="IGFSettings"/>',
        f'{sp_child}<array name="PortPinEcucPartitionRef"/>',
        f'{sp_struct}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _pin_name_for_signal(peripheral: str, signal: str) -> str:
    """Build the PortPin struct Name following the convention in portpin.json.

    Convention (grounded in fixture and portpin.json):
      LPUART0 TX -> Lpuart0_Tx
      LPUART0 RX -> Lpuart0_Rx
    Rule: PascalCase peripheral_id (Lpuart0) + underscore + TitleCase signal (Tx/Rx).
    peripheral here is the raw CLI peripheral like 'LPUART_0' or 'LPUART0'.
    signal is 'TX' or 'RX'.
    """
    # Build PascalCase from the peripheral ID (LPUART0 -> Lpuart0)
    periph_id = _normalize_peripheral_id(peripheral)  # e.g. LPUART0
    # PascalCase: capitalize first char, then lower except digits
    # Pattern: first letter upper, rest of word lower, digits preserved
    # LPUART0 -> L + puart + 0 -> Lpuart0
    if periph_id:
        pascal = periph_id[0].upper() + periph_id[1:].lower()
    else:
        pascal = periph_id
    # TitleCase signal: TX -> Tx, RX -> Rx
    sig_title = signal.upper()[0] + signal.upper()[1:].lower()
    return f"{pascal}_{sig_title}"


def _append_after_last_element(
    doc: MexDocument,
    last_el: ET.Element,
    new_bytes: bytes,
    line_ending: bytes,
) -> bool:
    """Append ``new_bytes`` after ``last_el``'s byte region.

    Uses the same splice-and-append pattern as apply_mcl_set. Returns True on
    success; False if the element cannot be located (aligned mismatch).
    """
    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is last_el), None)
    if src_index is None or not doc._aligned:
        return False

    last_src = doc._sources[src_index]
    span_end = doc._find_element_region_end(last_src, last_el)
    if span_end is None:
        return False

    last_el_raw = doc._raw[last_src.start: span_end + 1]
    combined = last_el_raw + line_ending + new_bytes
    doc.replace_element_region(last_el, combined)
    return True


def _insert_into_parent_before_close(
    doc: MexDocument,
    parent_el: ET.Element,
    new_bytes: bytes,
    line_ending: bytes,
) -> bool:
    """Insert ``new_bytes`` just before the parent element's close tag LINE.

    Strategy: locate the parent element's byte span via expat source data,
    extract the raw region, find the last ``</tag_name>`` within it, then
    walk backward to the start of that close-tag's line (preserving the
    original indentation of the close tag). New bytes are inserted before
    the close-tag line so the indentation is preserved exactly.

    Returns True on success, False if the parent cannot be located or its
    close tag cannot be found in the raw bytes.

    This approach avoids depth-counting on children whose tag name shares a
    prefix with the parent (e.g. ``<pin>`` with ``<pin_features>`` children),
    which confuses the generic ``_find_element_region_end`` scanner.
    """
    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is parent_el), None)
    if src_index is None or not doc._aligned:
        return False

    parent_src = doc._sources[src_index]
    span_end = doc._find_element_region_end(parent_src, parent_el)
    if span_end is None:
        return False

    parent_raw = doc._raw[parent_src.start: span_end + 1]

    # Extract tag name from the raw start tag to build the close tag bytes.
    start_tag_text = parent_raw[:parent_src.tag_end - parent_src.start + 1].decode("utf-8", errors="replace")
    m = re.match(r"<([A-Za-z0-9_:.\-]+)", start_tag_text)
    if m is None:
        return False
    close_tag = f"</{m.group(1)}>".encode("utf-8")

    # Find the LAST occurrence of close_tag in the parent's raw bytes.
    close_pos = parent_raw.rfind(close_tag)
    if close_pos < 0:
        return False

    # Walk backward from close_pos to find the start of the close-tag's line.
    # The line starts after the last \n before close_pos. This preserves the
    # indentation whitespace as part of the close-tag line.
    line_start = close_pos
    while line_start > 0 and parent_raw[line_start - 1:line_start] not in (b"\n", b"\r"):
        line_start -= 1

    # Build the replacement:
    #   everything before the close-tag line start
    #   + new_bytes + line_ending
    #   + close-tag line (indentation + close tag)
    new_parent_raw = (
        parent_raw[:line_start]
        + new_bytes
        + line_ending
        + parent_raw[line_start:]
    )
    doc.replace_element_region(parent_el, new_parent_raw)
    return True


def apply_port_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply Port pin-routing insertion for a peripheral's TX/RX pins.

    Validates that the requested pins are legal options for the peripheral
    and signal from the committed pins.json asset. Rejects illegal pins with
    a blocker ``port_illegal_pin`` diagnostic listing legal alternatives.

    On success, inserts TWO representations (byte-faithful, pure insertion):
      (A) ``<pin>`` header entries in the Pins tool
          ``<function name="PortContainer_0_VS_0"><pins>`` section.
      (B) ``PortPin`` struct entries appended to
          ``config_set[Port] > PortConfigSet > PortContainer[0] > PortPin``.

    Idempotent: skips a pin already configured (detected by peripheral+signal
    for A and by Name for B). Returns ``changed_modules=["port"]`` only when
    at least one representation was actually inserted.

    Grounded in:
    - pins.json (legality: legal peripheral+signal->pin options)
    - portpin.json (PortPin field template, <pin> header format, package mapping)
    - Port.xdm (field order, enum values)
    - Uart_Example_S32K344 fixture (reference for exact indentation/structure)
    """
    result = ApplyResult()
    payload = intent.payload
    peripheral = payload.get("peripheral", "")
    pins = payload.get("pins") or {}
    tx_pin = pins.get("tx")
    rx_pin = pins.get("rx")

    if not peripheral or (not tx_pin and not rx_pin):
        # Nothing actionable
        return result

    peripheral_id = _normalize_peripheral_id(peripheral)  # e.g. LPUART0

    # Load committed pins.json asset (legality source)
    signals_data = _load_pins_data()

    # Validate TX pin legality
    if tx_pin:
        legal_tx = _legal_pins_for_signal(signals_data, peripheral_id, "TX")
        legal_tx_pin_names = [s["pin"].upper() for s in legal_tx]
        if tx_pin.upper() not in legal_tx_pin_names:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_illegal_pin",
                module="port",
                message=(
                    f"Pin '{tx_pin}' is not a legal TX option for {peripheral} "
                    f"(asset: {peripheral_id} TX). "
                    f"Legal TX pins from pins.json: {sorted(set(legal_tx_pin_names))}."
                ),
                details={
                    "peripheral": peripheral,
                    "signal": "TX",
                    "requested_pin": tx_pin,
                    "legal_pins": sorted(set(legal_tx_pin_names)),
                },
            ))

    # Validate RX pin legality
    if rx_pin:
        legal_rx = _legal_pins_for_signal(signals_data, peripheral_id, "RX")
        legal_rx_pin_names = [s["pin"].upper() for s in legal_rx]
        if rx_pin.upper() not in legal_rx_pin_names:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_illegal_pin",
                module="port",
                message=(
                    f"Pin '{rx_pin}' is not a legal RX option for {peripheral} "
                    f"(asset: {peripheral_id} RX). "
                    f"Legal RX pins from pins.json: {sorted(set(legal_rx_pin_names))}."
                ),
                details={
                    "peripheral": peripheral,
                    "signal": "RX",
                    "requested_pin": rx_pin,
                    "legal_pins": sorted(set(legal_rx_pin_names)),
                },
            ))

    if result.blocked:
        return result

    # Determine package -> pin_num field
    pin_field = _detect_package_pin_field(doc)

    line_ending = _detect_line_ending(doc._raw)

    # ---- Part (A): Insert <pin> header entries ----
    pins_el = _find_port_function_pins_el(doc)
    if pins_el is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="port_pins_function_not_found",
            module="port",
            message=(
                "No <function name='PortContainer_0_VS_0'><pins> section found "
                "in the .mex Pins tool; cannot insert pin header entries."
            ),
            details={},
        ))
        return result

    pin_header_inserted = False

    # Build all new <pin> bytes that need to be inserted (TX then RX, in order).
    # We splice both into the <pins> parent with a single replace_element_region call
    # to avoid repeated tree reloads and to sidestep the <pin>/<pin_features> depth-
    # tracking issue in _find_element_region_end (which confuses <pin_features> with
    # the <pin> open tag when scanning for the matching </pin> close tag).
    new_pin_parts: list[bytes] = []

    if tx_pin:
        tx_signal_attr = f"{peripheral_id.lower()}_tx"
        if not _is_pin_already_configured(pins_el, peripheral_id, tx_signal_attr):
            tx_record = _find_pin_record(signals_data, peripheral_id, "TX", tx_pin)
            tx_pin_num_raw = tx_record.get(pin_field) if tx_record else None
            if not tx_pin_num_raw:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="port_pin_no_package_num",
                    module="port",
                    message=(
                        f"Pin '{tx_pin}' is a legal TX option for {peripheral} but has no "
                        f"pin number for the active package field '{pin_field}'. "
                        "Cannot write an empty pin_num to the .mex file."
                    ),
                    details={"peripheral": peripheral, "signal": "TX", "pin": tx_pin, "package_field": pin_field},
                ))
                return result
            # Use canonical pin name from asset record, not the raw CLI string
            tx_canonical_pin = tx_record["pin"]
            tx_pin_bytes = _build_pin_header_tx_bytes(
                peripheral_id=peripheral_id,
                signal_attr=tx_signal_attr,
                pin_num=tx_pin_num_raw,
                pin_signal=tx_canonical_pin,
                indent=18,
                line_ending=line_ending,
            )
            new_pin_parts.append(tx_pin_bytes)

    if rx_pin:
        rx_signal_attr = f"{peripheral_id.lower()}_rx"
        if not _is_pin_already_configured(pins_el, peripheral_id, rx_signal_attr):
            rx_record = _find_pin_record(signals_data, peripheral_id, "RX", rx_pin)
            rx_pin_num_raw = rx_record.get(pin_field) if rx_record else None
            if not rx_pin_num_raw:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="port_pin_no_package_num",
                    module="port",
                    message=(
                        f"Pin '{rx_pin}' is a legal RX option for {peripheral} but has no "
                        f"pin number for the active package field '{pin_field}'. "
                        "Cannot write an empty pin_num to the .mex file."
                    ),
                    details={"peripheral": peripheral, "signal": "RX", "pin": rx_pin, "package_field": pin_field},
                ))
                return result
            # Use canonical pin name from asset record, not the raw CLI string
            rx_canonical_pin = rx_record["pin"]
            rx_pin_bytes = _build_pin_header_rx_bytes(
                peripheral_id=peripheral_id,
                signal_attr=rx_signal_attr,
                pin_num=rx_pin_num_raw,
                pin_signal=rx_canonical_pin,
                indent=18,
            )
            new_pin_parts.append(rx_pin_bytes)

    if new_pin_parts:
        # Join multiple new pins with line_ending separator
        combined_new_pins = line_ending.join(new_pin_parts)
        ok = _insert_into_parent_before_close(
            doc, pins_el, combined_new_pins, line_ending
        )
        if not ok:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_pin_insertion_failed",
                module="port",
                message="Could not splice new <pin> entries into <pins> section.",
                details={"tx_pin": tx_pin, "rx_pin": rx_pin},
            ))
            return result

        # Re-find pins_el after tree reload
        pins_el = _find_port_function_pins_el(doc)
        if pins_el is None:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_pins_function_not_found",
                module="port",
                message="<pins> section lost after pin insertion.",
                details={},
            ))
            return result
        pin_header_inserted = True

    # ---- Part (B): Insert PortPin struct entries ----
    port_cfg = doc.find_config_set("Port")
    if port_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="port_config_set_not_found",
            module="port",
            message="No enabled Port <config_set> found; cannot insert PortPin structs.",
            details={},
        ))
        return result

    portpin_array = None
    for el in port_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
            portpin_array = el
            break

    if portpin_array is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="port_portpin_array_not_found",
            module="port",
            message="No PortPin array found in Port PortContainer[0]; cannot insert structs.",
            details={},
        ))
        return result

    existing_structs = [c for c in portpin_array if c.tag.endswith("struct")]

    # Compute max existing PortPinId
    max_portpin_id = 0
    for s in existing_structs:
        pid_setting = doc.find_child_setting(s, "PortPinId")
        if pid_setting is not None:
            try:
                pid = int(pid_setting.attrib.get("value", "0"))
                if pid > max_portpin_id:
                    max_portpin_id = pid
            except ValueError:
                pass

    struct_indent = 36  # fixture indentation for PortPin <struct> elements
    portpin_struct_inserted = False

    # TX PortPin struct
    if tx_pin:
        tx_name = _pin_name_for_signal(peripheral, "TX")
        if not _is_portpin_struct_already_configured(portpin_array, doc, tx_name):
            # Re-query existing structs (may have changed from prior insertions)
            existing_structs = [c for c in portpin_array if c.tag.endswith("struct")]
            new_struct_index = len(existing_structs)
            new_portpin_id = max_portpin_id + 1

            tx_struct_bytes = _build_portpin_struct_bytes(
                struct_index=new_struct_index,
                portpin_name=tx_name,
                portpin_id=new_portpin_id,
                indent=struct_indent,
                line_ending=line_ending,
            )

            last_struct = existing_structs[-1] if existing_structs else None
            if last_struct is None:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="port_portpin_array_empty",
                    module="port",
                    message="PortPin array is empty; cannot append TX struct.",
                    details={},
                ))
                return result

            ok = _append_after_last_element(doc, last_struct, tx_struct_bytes, line_ending)
            if not ok:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="port_portpin_struct_insertion_failed",
                    module="port",
                    message="Could not locate last PortPin struct for TX insertion.",
                    details={"tx_name": tx_name},
                ))
                return result

            # Re-find Port config after tree reload
            port_cfg = doc.find_config_set("Port")
            portpin_array = None
            if port_cfg is not None:
                for el in port_cfg.iter():
                    if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
                        portpin_array = el
                        break

            max_portpin_id = new_portpin_id
            portpin_struct_inserted = True

    # RX PortPin struct
    if rx_pin:
        rx_name = _pin_name_for_signal(peripheral, "RX")
        if portpin_array is not None and not _is_portpin_struct_already_configured(portpin_array, doc, rx_name):
            existing_structs = [c for c in portpin_array if c.tag.endswith("struct")]
            new_struct_index = len(existing_structs)
            new_portpin_id = max_portpin_id + 1

            rx_struct_bytes = _build_portpin_struct_bytes(
                struct_index=new_struct_index,
                portpin_name=rx_name,
                portpin_id=new_portpin_id,
                indent=struct_indent,
                line_ending=line_ending,
            )

            last_struct = existing_structs[-1] if existing_structs else None
            if last_struct is None:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="port_portpin_array_empty",
                    module="port",
                    message="PortPin array is empty; cannot append RX struct.",
                    details={},
                ))
                return result

            ok = _append_after_last_element(doc, last_struct, rx_struct_bytes, line_ending)
            if not ok:
                result.diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="port_portpin_struct_insertion_failed",
                    module="port",
                    message="Could not locate last PortPin struct for RX insertion.",
                    details={"rx_name": rx_name},
                ))
                return result

            # Re-find Port config after tree reload
            port_cfg = doc.find_config_set("Port")
            portpin_array = None
            if port_cfg is not None:
                for el in port_cfg.iter():
                    if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
                        portpin_array = el
                        break

            portpin_struct_inserted = True

    if not pin_header_inserted and not portpin_struct_inserted:
        # Everything already configured -- idempotent no-op
        return result

    # Mark modified: portpin_array and its nearest quick_selection ancestor
    modified: list[ET.Element] = []
    if portpin_array is not None:
        doc.mark_modified(portpin_array)
        carrier = doc.find_nearest_quick_selection_ancestor(portpin_array)
        if carrier is not None:
            doc.mark_modified(carrier)
        modified.append(portpin_array)

    result.changed_modules.append("port")
    result.modified_elements.extend(modified)
    return result


# ---------------------------------------------------------------------------
# Dio: DIO output channel insertion (cross-module: Dio owns channel, Port owns pin)
# ---------------------------------------------------------------------------

def _find_gpio_pin_record(signals: list[dict], pin_name: str) -> dict | None:
    """Return the pins.json record where pin==pin_name and direction=='gpio'."""
    target = pin_name.upper()
    for s in signals:
        if s.get("pin", "").upper() == target and s.get("direction", "") == "gpio":
            return s
    return None


def _is_gpio_pin_already_in_port(
    pins_el: ET.Element,
    signal_attr: str,
) -> bool:
    """Return True if a SIUL2 <pin> entry with the given signal already exists."""
    for child in pins_el:
        if (
            child.tag.endswith("pin")
            and child.attrib.get("peripheral") == "SIUL2"
            and child.attrib.get("signal") == signal_attr
        ):
            return True
    return False


def _build_gpio_pin_header_bytes(
    signal_attr: str,
    pin_num: str,
    pin_signal: str,
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build bytes for a GPIO <pin> entry with peripheral=SIUL2 and direction=OUTPUT.

    Signal format: 'gpio, <mscr>' (space after comma).
    Grounded in the task spec (RTD-MEX-DIO-001) and the fixture GPIO pin format.
    """
    le = line_ending.decode("latin-1")
    sp = " " * indent
    sp2 = " " * (indent + 3)
    sp3 = " " * (indent + 6)
    lines = [
        f'{sp}<pin peripheral="SIUL2" signal="{signal_attr}" pin_num="{pin_num}" pin_signal="{pin_signal}">',
        f'{sp2}<pin_features>',
        f'{sp3}<pin_feature name="direction" value="OUTPUT"/>',
        f'{sp2}</pin_features>',
        f'{sp}</pin>',
    ]
    return le.join(lines).encode("utf-8")


def _build_gpio_portpin_struct_bytes(
    struct_index: int,
    portpin_name: str,
    portpin_id: int,
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build the raw bytes for a GPIO output PortPin <struct>.

    Key difference from the LPUART PortPin builder: GPIO output pins use
    PortPinDirectionChangeable=false and PortPinModeChangeable=false
    (per the RTD-MEX-DIO-001 task spec / vendor example_Dio.mex).
    All other field defaults are the same as portpin.json.

    Field order per portpin.json children_order:
      Name, PortPinPue, PortPinPus, PortPinSafeMode, PortPinDse,
      PortPinWithReadBack, PortPinPke, PortPinIfe, PortPinDirectionChangeable,
      PortPinModeChangeable, PortPinInvertControl, PortPinSiul2Instance,
      PortPinId, PortPinInitialMode, OBEGroupSelect, MscrPdacSlot,
      ImcrPdacSlot, IGFSettings, PortPinEcucPartitionRef.
    """
    le = line_ending.decode("latin-1")
    sp_struct = " " * indent
    sp_child = " " * (indent + 3)
    lines = [
        f'{sp_struct}<struct name="{struct_index}">',
        f'{sp_child}<setting name="Name" value="{portpin_name}"/>',
        f'{sp_child}<setting name="PortPinPue" value="false"/>',
        f'{sp_child}<setting name="PortPinPus" value="false"/>',
        f'{sp_child}<setting name="PortPinSafeMode" value="false"/>',
        f'{sp_child}<setting name="PortPinDse" value="false"/>',
        f'{sp_child}<setting name="PortPinWithReadBack" value="false"/>',
        f'{sp_child}<setting name="PortPinPke" value="false"/>',
        f'{sp_child}<setting name="PortPinIfe" value="false"/>',
        f'{sp_child}<setting name="PortPinDirectionChangeable" value="false"/>',
        f'{sp_child}<setting name="PortPinModeChangeable" value="false"/>',
        f'{sp_child}<setting name="PortPinInvertControl" value="false"/>',
        f'{sp_child}<setting name="PortPinSiul2Instance" value="SIUL2_0"/>',
        f'{sp_child}<setting name="PortPinId" value="{portpin_id}"/>',
        f'{sp_child}<setting name="PortPinInitialMode" value="PORT_GPIO_MODE"/>',
        f'{sp_child}<setting name="OBEGroupSelect" value="NO_OBE_GROUP"/>',
        f'{sp_child}<setting name="MscrPdacSlot" value="VIRTUAL_WRAPPER_PDAC0"/>',
        f'{sp_child}<setting name="ImcrPdacSlot" value="VIRTUAL_WRAPPER_PDAC0"/>',
        f'{sp_child}<array name="IGFSettings"/>',
        f'{sp_child}<array name="PortPinEcucPartitionRef"/>',
        f'{sp_struct}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _build_dio_channel_array_bytes(
    channel_name: str,
    channel_id: int,
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build bytes for a populated DioChannel array replacing a self-closed one.

    The returned bytes include the opening <array name="DioChannel"> and the
    single DioChannel struct. Field set and order from dio.json/Dio.xdm:
      Name, DioChannelId, PDACSlot, DioChannelEcucPartitionRef.
    ``indent`` is the leading spaces before the <array> open tag.
    """
    le = line_ending.decode("latin-1")
    sp_array = " " * indent
    sp_struct = " " * (indent + 3)
    sp_child = " " * (indent + 6)
    lines = [
        f'<array name="DioChannel">',
        f'{sp_struct}<struct name="0">',
        f'{sp_child}<setting name="Name" value="{channel_name}"/>',
        f'{sp_child}<setting name="DioChannelId" value="{channel_id}"/>',
        f'{sp_child}<setting name="PDACSlot" value="VIRTUAL_WRAPPER_PDAC0"/>',
        f'{sp_child}<array name="DioChannelEcucPartitionRef"/>',
        f'{sp_struct}</struct>',
        f'{sp_array}</array>',
    ]
    return le.join(lines).encode("utf-8")


def _find_dio_port_by_id(
    doc: MexDocument,
    dio_cfg: ET.Element,
    port_id: int,
) -> ET.Element | None:
    """Return the DioPort struct with DioPortId==port_id from the Dio config set."""
    for el in dio_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "DioPort":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                id_setting = doc.find_child_setting(child, "DioPortId")
                if id_setting is not None and id_setting.attrib.get("value") == str(port_id):
                    return child
    return None


def _find_dio_channel_array(doc: MexDocument, dio_port: ET.Element) -> ET.Element | None:
    """Return the DioChannel array inside a DioPort struct."""
    for el in dio_port:
        if el.tag.endswith("array") and el.attrib.get("name") == "DioChannel":
            return el
    return None


def apply_dio_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply a Dio output channel insertion with cross-module Port GPIO pin routing.

    Owns the Dio channel edit; orchestrates the Port-owned GPIO pin edits.
    The two Port edits (GPIO <pin> header + PortPin struct) reuse the helpers
    from apply_port_set / the GPIO-specific builders added here.

    Intent payload:
      add_channel (str): symbolic DioChannel Name, e.g. 'LED_CTRL'
      pin (str): S32K3 pin signal name, e.g. 'PTA5'
      direction (str): 'output' (default, only value supported in M1)

    Validation:
      - pin must have direction='gpio' in pins.json (no mux-only peripherals)
      - pin must not already be configured as a <pin> header (idempotent guard)

    Returns changed_modules=['dio', 'port'] when edits were made.
    Idempotent: if the DioChannel name already exists, or the Port pin already
    configured, each part is skipped independently.

    Blocker codes:
      dio_config_set_not_found   -- Dio <config_set> is absent
      dio_port_not_found         -- DioPort for the computed DioPortId is absent
      dio_pin_not_gpio           -- pin does not have direction='gpio' in pins.json
      port_config_set_not_found  -- Port <config_set> is absent
      port_pins_function_not_found -- <pins> section is absent
      port_portpin_array_not_found -- PortPin array absent in PortContainer[0]
    """
    result = ApplyResult()
    payload = intent.payload
    channel_name = payload.get("add_channel", "")
    pin_name = payload.get("pin", "")

    if not channel_name or not pin_name:
        return result  # nothing requested -- no-op

    # ---- Load assets ----
    signals_data = _load_pins_data()
    pin_field = _detect_package_pin_field(doc)
    line_ending = _detect_line_ending(doc._raw)

    # ---- Validate pin: must be a GPIO pin in pins.json ----
    gpio_record = _find_gpio_pin_record(signals_data, pin_name)
    if gpio_record is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="dio_pin_not_gpio",
            module="dio",
            message=(
                f"Pin '{pin_name}' is not a free GPIO pin in pins.json "
                f"(direction='gpio' record not found). "
                "DIO channel insertion requires a GPIO-capable pin."
            ),
            details={"pin": pin_name},
        ))
        return result

    mscr = gpio_record["mscr"]
    dio_port_id = mscr // 16
    dio_channel_id = mscr % 16
    pin_num = gpio_record.get(pin_field, "")
    pin_signal = gpio_record["pin"]  # canonical pin name from asset
    gpio_signal_attr = f"gpio, {mscr}"  # e.g. "gpio, 5"

    # ---- Locate Dio config set ----
    dio_cfg = doc.find_config_set("Dio")
    if dio_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="dio_config_set_not_found",
            module="dio",
            message="No enabled Dio <config_set> found; cannot insert DioChannel.",
            details={},
        ))
        return result

    # ---- Locate DioPort for the computed DioPortId ----
    dio_port = _find_dio_port_by_id(doc, dio_cfg, dio_port_id)
    if dio_port is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="dio_port_not_found",
            module="dio",
            message=(
                f"No DioPort with DioPortId={dio_port_id} found in the Dio config set. "
                f"Pin '{pin_name}' (mscr={mscr}) maps to DioPortId={dio_port_id}; "
                "this DioPort must exist before a DioChannel can be inserted."
            ),
            details={"pin": pin_name, "mscr": mscr, "dio_port_id": dio_port_id},
        ))
        return result

    # ---- Part A: Insert DioChannel into DioPort's DioChannel array ----
    dio_channel_array = _find_dio_channel_array(doc, dio_port)
    dio_channel_inserted = False

    if dio_channel_array is not None:
        existing_channels = [c for c in dio_channel_array if c.tag.endswith("struct")]

        # Idempotency: skip if channel name already exists
        channel_already_exists = any(
            doc.find_child_setting(c, "Name") is not None
            and doc.find_child_setting(c, "Name").attrib.get("value") == channel_name
            for c in existing_channels
        )

        if not channel_already_exists:
            # Self-closed or empty DioChannel array -> replace with populated one.
            # The indent of the <array> tag itself is detected from the raw bytes.
            elements = list(doc.root.iter())
            src_index = next(
                (i for i, e in enumerate(elements) if e is dio_channel_array), None
            )
            if src_index is not None and doc._aligned:
                array_src = doc._sources[src_index]
                raw = doc._raw
                i = array_src.start - 1
                while i >= 0 and raw[i:i + 1] not in (b"\n", b"\r"):
                    i -= 1
                line_start = i + 1
                spaces = 0
                while (
                    line_start + spaces < array_src.start
                    and raw[line_start + spaces: line_start + spaces + 1] == b" "
                ):
                    spaces += 1
                array_indent = spaces
            else:
                array_indent = 33  # sane fallback matching the Dio fixture level

            new_array_bytes = _build_dio_channel_array_bytes(
                channel_name=channel_name,
                channel_id=dio_channel_id,
                indent=array_indent,
                line_ending=line_ending,
            )
            doc.replace_element_region(dio_channel_array, new_array_bytes)
            dio_channel_inserted = True

            # After replace_element_region the tree is reloaded; re-find everything.
            dio_cfg = doc.find_config_set("Dio")
            if dio_cfg is not None:
                dio_port = _find_dio_port_by_id(doc, dio_cfg, dio_port_id)
                if dio_port is not None:
                    dio_channel_array = _find_dio_channel_array(doc, dio_port)

    # Mark Dio channel array modified (but do NOT clear the Dio config_set's
    # quick_selection here -- Parts B and C below both call replace_element_region
    # which reloads the tree from raw bytes, discarding any in-memory attrib
    # pop done before those reloads. The quick_selection clear on the Dio
    # config_set MUST happen after the last replace_element_region call).
    if dio_channel_inserted and dio_channel_array is not None:
        doc.mark_modified(dio_channel_array)
        result.changed_modules.append("dio")
        result.modified_elements.append(dio_channel_array)

    # ---- Part B: Port <pin> header for the GPIO pad ----
    pins_el = _find_port_function_pins_el(doc)
    if pins_el is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="port_pins_function_not_found",
            module="port",
            message=(
                "No <function name='PortContainer_0_VS_0'><pins> section found; "
                "cannot insert GPIO pin header."
            ),
            details={"pin": pin_name},
        ))
        return result

    port_pin_header_inserted = False
    if not _is_gpio_pin_already_in_port(pins_el, gpio_signal_attr):
        if not pin_num:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_pin_no_package_num",
                module="port",
                message=(
                    f"Pin '{pin_name}' has no pin number for package field '{pin_field}'. "
                    "Cannot write an empty pin_num to the .mex file."
                ),
                details={"pin": pin_name, "package_field": pin_field},
            ))
            return result

        gpio_pin_bytes = _build_gpio_pin_header_bytes(
            signal_attr=gpio_signal_attr,
            pin_num=pin_num,
            pin_signal=pin_signal,
            indent=18,
            line_ending=line_ending,
        )
        ok = _insert_into_parent_before_close(doc, pins_el, gpio_pin_bytes, line_ending)
        if not ok:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_pin_insertion_failed",
                module="port",
                message="Could not splice GPIO <pin> entry into <pins> section.",
                details={"pin": pin_name},
            ))
            return result

        pins_el = _find_port_function_pins_el(doc)
        port_pin_header_inserted = True

    # ---- Part C: Port PortPin struct for the GPIO pad ----
    port_cfg = doc.find_config_set("Port")
    if port_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="port_config_set_not_found",
            module="port",
            message="No enabled Port <config_set> found; cannot insert PortPin struct.",
            details={},
        ))
        return result

    portpin_array = None
    for el in port_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
            portpin_array = el
            break

    if portpin_array is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="port_portpin_array_not_found",
            module="port",
            message="No PortPin array found in Port PortContainer[0]; cannot insert GPIO struct.",
            details={},
        ))
        return result

    # GPIO PortPin name convention: "Led_Ctrl" (PascalCase-like, from channel name)
    # Rule: capitalize first letter of each word (using channel_name as base with underscores)
    gpio_portpin_name = _portpin_name_for_gpio_channel(channel_name)

    portpin_struct_inserted = False
    existing_structs = [c for c in portpin_array if c.tag.endswith("struct")]

    if not _is_portpin_struct_already_configured(portpin_array, doc, gpio_portpin_name):
        # Compute next PortPinId
        max_portpin_id = 0
        for s in existing_structs:
            pid_setting = doc.find_child_setting(s, "PortPinId")
            if pid_setting is not None:
                try:
                    pid = int(pid_setting.attrib.get("value", "0"))
                    if pid > max_portpin_id:
                        max_portpin_id = pid
                except ValueError:
                    pass

        new_struct_index = len(existing_structs)
        new_portpin_id = max_portpin_id + 1

        gpio_struct_bytes = _build_gpio_portpin_struct_bytes(
            struct_index=new_struct_index,
            portpin_name=gpio_portpin_name,
            portpin_id=new_portpin_id,
            indent=36,  # fixture indentation for PortPin <struct> elements
            line_ending=line_ending,
        )

        last_struct = existing_structs[-1] if existing_structs else None
        if last_struct is None:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_portpin_array_empty",
                module="port",
                message="PortPin array is empty; cannot append GPIO struct.",
                details={},
            ))
            return result

        ok = _append_after_last_element(doc, last_struct, gpio_struct_bytes, line_ending)
        if not ok:
            result.diagnostics.append(Diagnostic(
                severity="blocker",
                code="port_portpin_struct_insertion_failed",
                module="port",
                message="Could not locate last PortPin struct for GPIO insertion.",
                details={"portpin_name": gpio_portpin_name},
            ))
            return result

        # Re-find Port config after tree reload
        port_cfg = doc.find_config_set("Port")
        portpin_array = None
        if port_cfg is not None:
            for el in port_cfg.iter():
                if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
                    portpin_array = el
                    break

        portpin_struct_inserted = True

    if port_pin_header_inserted or portpin_struct_inserted:
        if portpin_array is not None:
            doc.mark_modified(portpin_array)
            carrier = doc.find_nearest_quick_selection_ancestor(portpin_array)
            if carrier is not None:
                doc.mark_modified(carrier)
            result.modified_elements.append(portpin_array)
        if "port" not in result.changed_modules:
            result.changed_modules.append("port")

    # Clear quick_selection on the Dio config_set AFTER all replace_element_region
    # calls. Each replace_element_region reloads the tree from raw bytes, resetting
    # _sources (and therefore the src.attrib snapshot used by _render_minimal).
    # Any mark_modified done before a reload is overwritten by the reload because
    # _capture_sources() re-snaps attribs from the freshly parsed tree (which still
    # carries quick_selection="DioDefault" in the raw bytes). The clear must happen
    # LAST, after every insertion is complete, so the final _render_minimal sees the
    # Dio config_set element's attrib as different from its src.attrib snapshot and
    # calls _remove_attr to strip quick_selection from the written bytes.
    if dio_channel_inserted:
        dio_cfg_final = doc.find_config_set("Dio")
        if dio_cfg_final is not None and "quick_selection" in dio_cfg_final.attrib:
            doc.mark_modified(dio_cfg_final)

    return result


def _portpin_name_for_gpio_channel(channel_name: str) -> str:
    """Build the PortPin struct Name for a GPIO DIO channel.

    Convention from the task spec: LED_CTRL -> Led_Ctrl
    Rule: split on underscores, capitalize each word's first letter, lower the rest,
    rejoin with underscores.
    Examples:
      LED_CTRL    -> Led_Ctrl
      SWITCH_IN   -> Switch_In
    """
    parts = channel_name.split("_")
    return "_".join(p[0].upper() + p[1:].lower() if p else "" for p in parts)


# ---------------------------------------------------------------------------
# Mcu: clock-tree PLL + divider + McuClockReferencePoint configuration
# ---------------------------------------------------------------------------

# Supported clock-frequency recipe table, keyed by (core_clk, aips_plat_clk, aips_slow_clk).
# Only 160/80/40 is supported in Milestone 1. Values grounded in Mcu.xdm and
# the S32K344 160MHz reference config (FXOSC=16MHz).
_MCU_SUPPORTED_RECIPES: frozenset = frozenset({
    (160, 80, 40),
})

# Clocks available as McuClockFrequencySelect on S32K344, grounded in the
# S32K344 reference config and Mcu.xdm. Must stay in sync with clock.json
# (all_selectable_clocks) and the test constant _ALL_SELECTABLE_CLOCKS.
# Drift is caught by test_clock_json_matches_apply_code_literals (LL-012).
# clock.json is a committed reference document for the recipe; it is NOT
# loaded at runtime -- this constant is the runtime source of truth.
_ALL_SELECTABLE_CLOCKS: list[str] = [
    "CORE_CLK",
    "AIPS_PLAT_CLK",
    "AIPS_SLOW_CLK",
    "FLEXCAN_PE_CLK0_2",
    "FLEXCAN_PE_CLK3_5",
    "EMAC_CLK_RX",
    "EMAC_CLK_TX",
    "EMAC_CLK_TS",
    "QuadSPI_SFCK",
    "QSPI_MEM_CLK",
    "FIRC_CLK",
    "SIRC_CLK",
    "STM0_CLK",
]


def _find_clock_settings_parent(doc: MexDocument) -> ET.Element | None:
    """Return the <clock_settings> element in the top-level clocks tool section.

    This is the NOT-a-config_set section; its elements use id="..." attributes.
    """
    for el in doc.root.iter():
        if el.tag.endswith("clock_settings"):
            return el
    return None


def _change_clock_setting_value(doc: MexDocument, setting_id: str, new_value: str) -> bool:
    """Change an existing <setting id="..." value="..."> in clock_settings (raw bytes).

    Uses regex on raw bytes to perform a byte-faithful in-place value change.
    Returns True if the setting was found and updated, False otherwise.
    """
    pattern = (
        rb'(<setting id="' + re.escape(setting_id).encode() + rb'" value=")[^"]*(")'
    )
    match = re.search(pattern, doc._raw)
    if match is None:
        return False
    new_raw = doc._raw[:match.start(1)] + match.group(1) + new_value.encode() + match.group(2) + doc._raw[match.end(2):]
    doc._raw = new_raw
    doc.tree = ET.parse(io.BytesIO(new_raw))
    doc._capture_sources()
    return True


def _insert_clock_setting(doc: MexDocument, setting_id: str, value: str, locked: str = "false") -> None:
    """Insert a new <setting id="setting_id" value="value" locked="locked"/> into clock_settings.

    Insertion strategy: find the last existing <setting id=...> in the
    <clock_settings> block and append after it, preserving indentation.
    """
    # Find the last <setting id= ... /> line position in the raw bytes.
    # We detect indentation from the existing settings and insert after the last one.
    clock_settings = _find_clock_settings_parent(doc)
    if clock_settings is None:
        return

    line_ending = _detect_line_ending(doc._raw)
    le = line_ending

    # Find the last <setting id= in the raw bytes by scanning for all occurrences
    # and picking the one whose end we can locate.
    all_setting_matches = list(re.finditer(
        rb'<setting id="[^"]*" value="[^"]*"[^/]*/>', doc._raw
    ))
    if not all_setting_matches:
        return

    last_match = all_setting_matches[-1]
    match_start = last_match.start()

    # Detect indentation: walk backward from match_start to find the preceding newline,
    # then count spaces from newline+1 to match_start.
    raw = doc._raw
    i = match_start - 1
    while i >= 0 and raw[i:i + 1] not in (b"\n", b"\r"):
        i -= 1
    line_start = i + 1
    spaces = 0
    while line_start + spaces < match_start and raw[line_start + spaces: line_start + spaces + 1] == b" ":
        spaces += 1
    indent = spaces

    new_setting_bytes = (
        le + (b" " * indent)
        + f'<setting id="{setting_id}" value="{value}" locked="{locked}"/>'.encode("utf-8")
    )
    insert_pos = last_match.end()
    new_raw = raw[:insert_pos] + new_setting_bytes + raw[insert_pos:]
    doc._raw = new_raw
    doc.tree = ET.parse(io.BytesIO(new_raw))
    doc._capture_sources()


def _remove_clock_setting(doc: MexDocument, setting_id: str) -> bool:
    """Remove a <setting id="setting_id" ...> from clock_settings (raw bytes).

    Removes the element's entire line (including the newline preceding it).
    Returns True if removed, False if not found.
    """
    # Match the line: optional whitespace + element + optional trailing whitespace
    pattern = (
        rb'[^\S\r\n]*<setting id="' + re.escape(setting_id).encode() + rb'"[^/]*/>[^\S\r\n]*'
    )
    raw = doc._raw
    match = re.search(pattern, raw)
    if match is None:
        return False

    # Include the preceding newline (LF or CRLF) to remove the whole line.
    start = match.start()
    end = match.end()
    if start > 0 and raw[start - 1:start] == b"\n":
        start -= 1
        if start > 0 and raw[start - 1:start] == b"\r":
            start -= 1
    elif start > 0 and raw[start - 1:start] == b"\r":
        start -= 1

    new_raw = raw[:start] + raw[end:]
    doc._raw = new_raw
    doc.tree = ET.parse(io.BytesIO(new_raw))
    doc._capture_sources()
    return True


def _build_merged_ref_point_array_bytes(
    doc: MexDocument,
    existing_structs: list[ET.Element],
    new_clocks: list[str],
    indent: int,
    line_ending: bytes,
) -> bytes:
    """Build a merged McuClockReferencePoint array block as raw bytes.

    Strategy (GAP 3 fix): PRESERVE existing reference-point structs (so any
    UartClockRef / OsIfSystemTimerClockRef paths that reference them remain
    resolvable) AND ADD the 13 selectable-clock structs named after their clock
    (Name == McuClockFrequencySelect), skipping any whose Name already exists.
    Indices are renumbered sequentially 0..N-1 across the merged list.

    Existing structs keep their original Name and McuClockFrequencySelect.
    New structs have Name == McuClockFrequencySelect == clock name.
    McuClockReferencePointFrequency is NOT written (ConfigTools computes it).

    ``indent`` is the number of leading spaces for the <array> open tag.
    Children (struct) are at indent+3; settings at indent+6.
    """
    le = line_ending.decode("latin-1")
    sp_array = " " * indent
    sp_struct = " " * (indent + 3)
    sp_child = " " * (indent + 6)

    # Collect names already present in existing structs (for dedup of new ones)
    existing_names: set[str] = set()
    for s in existing_structs:
        ns = doc.find_child_setting(s, "Name")
        if ns is not None:
            existing_names.add(ns.attrib.get("value", ""))

    # Build the ordered list of (name, freq_select) tuples:
    # first the existing structs (preserved as-is), then the new ones not already present.
    entries: list[tuple[str, str]] = []
    for s in existing_structs:
        ns = doc.find_child_setting(s, "Name")
        fs = doc.find_child_setting(s, "McuClockFrequencySelect")
        name = ns.attrib.get("value", "") if ns is not None else ""
        freq = fs.attrib.get("value", "") if fs is not None else ""
        entries.append((name, freq))

    for clk in new_clocks:
        if clk not in existing_names:
            entries.append((clk, clk))

    lines: list[str] = ['<array name="McuClockReferencePoint">']
    for i, (name, freq) in enumerate(entries):
        lines.append(f'{sp_struct}<struct name="{i}">')
        lines.append(f'{sp_child}<setting name="Name" value="{name}"/>')
        lines.append(f'{sp_child}<setting name="McuClockFrequencySelect" value="{freq}"/>')
        lines.append(f'{sp_struct}</struct>')
    lines.append(f'{sp_array}</array>')
    return le.join(lines).encode("utf-8")


def _insert_settings_into_struct(
    doc: MexDocument,
    struct_el: ET.Element,
    settings: dict[str, str],
) -> None:
    """Insert new <setting name="..." value="..."/> children into a struct element.

    Strategy: locate the struct's byte region, find the closing tag's line, and
    insert the new settings before it. Uses _insert_into_parent_before_close
    pattern adapted for config_set settings (name=... not id=...).
    """
    line_ending = _detect_line_ending(doc._raw)

    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is struct_el), None)
    if src_index is None or not doc._aligned:
        return

    src = doc._sources[src_index]
    span_end = doc._find_element_region_end(src, struct_el)
    if span_end is None:
        return

    parent_raw = doc._raw[src.start: span_end + 1]
    start_tag_text = parent_raw[:src.tag_end - src.start + 1].decode("utf-8", errors="replace")
    m = re.match(r"<([A-Za-z0-9_:.\-]+)", start_tag_text)
    if m is None:
        return
    close_tag = f"</{m.group(1)}>".encode("utf-8")

    close_pos = parent_raw.rfind(close_tag)
    if close_pos < 0:
        return

    # Find the line start of the close tag
    line_start = close_pos
    while line_start > 0 and parent_raw[line_start - 1:line_start] not in (b"\n", b"\r"):
        line_start -= 1

    # Detect indentation for the new settings: use the close-tag's line indentation
    # and add 3 more spaces (settings are one level inside the struct).
    close_indent_raw = parent_raw[line_start:close_pos]
    close_spaces = len(close_indent_raw) - len(close_indent_raw.lstrip(b" "))
    child_indent = close_spaces + 3

    le = line_ending.decode("latin-1")
    sp = " " * child_indent
    new_lines = []
    for name, value in settings.items():
        new_lines.append(f'{sp}<setting name="{name}" value="{value}"/>')
    new_bytes = le.join(new_lines).encode("utf-8")

    new_parent_raw = (
        parent_raw[:line_start]
        + new_bytes
        + line_ending
        + parent_raw[line_start:]
    )
    doc.replace_element_region(struct_el, new_parent_raw)


def apply_mcu_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply the Mcu clock-tree PLL/divider recipe and McuClockReferencePoint array.

    Implements RTD-MEX-MCU-001: 160/80/40 MHz clock tree for S32K344 using the
    16MHz FXOSC -> CORE_PLL -> PHI0 path. Only the 160/80/40 recipe is
    supported; other frequency combinations return a blocker diagnostic.

    Two regions are edited:
    (A) clock_settings section (top-level clocks tool, elements use id="..."):
        - INSERT: CORE_PLL_PD=Power_up, CORE_PLLODIV_0_DE=Enabled,
                  CORE_PLLODIV_1_DE=Enabled, MC_CGM_MUX_0.sel=PHI0
        - CHANGE: MC_CGM_MUX_0_DIV1.scale 1->2, MC_CGM_MUX_0_DIV2.scale 2->4,
                  MC_CGM_MUX_0_DIV3.scale 1->2 (HSE_CLK=CORE/2=80 MHz; fixes SEVERE
                  "输入频率必须小于或等于： 120 MHz" on HSE_CLK with 160MHz core)
        - ENSURE: MC_CGM_MUX_0_DIV4.scale=4 (DCM_CLK=40 MHz), MC_CGM_MUX_0_DIV6.scale=1
                  (QSPI_MEM_CLK=160 MHz) -- idempotent if already correct; grounded in
                  example_Dio.mex verified working 160MHz example
        - REMOVE: PLLunderMcuControl="Disabled"
        - LEAVE UNCHANGED: CORE_MFD.scale=120, PLL_PREDIV.scale=2, PHI0.scale=3,
                           PHI1.scale=3, POSTDIV.scale=2, MC_CGM_MUX_0_DIV0.scale=1
        - NOT WRITTEN: clock_output values (ConfigTools recomputes them)

    (B) Mcu config_set (elements use name="..."):
        - McuPll_0: McuPLLUnderMcuControl false->true, McuPLLEnabled false->true
        - McuPll_Configuration: McuPllOdiv0_En false->true, McuPllOdiv1_En false->true
        - McuPll_Parameter: INSERT PLL fields; CLEAR quick_selection LAST (LL-013)
        - McuCgm0ClockMux0: McuClkMux0_Source FIRC_CLK->PLL_PHI0_CLK; INSERT divisors
        - McuGeneralConfiguration: McuNoPll true->false (GAP 1: Mcu.xdm INVALID rule)
        - McuControlledClocksConfiguration: McuPll0UnderMcuControl false->true (GAP 2)
        - McuClockReferencePoint array: MERGE (preserve existing + add 13 clocks; GAP 3)

    Idempotent: second apply with same intent produces the same output.
    Returns a blocker for unsupported frequency combinations.

    ORDERING: All raw-bytes operations (replace_element_region / direct _raw edits)
    happen FIRST. These reload the tree from _raw, discarding any prior in-memory
    attribute mutations. Attribute mutations (.set("value", ...)) happen LAST, after
    all _raw edits are complete, so they are captured by _render_minimal on write().
    """
    result = ApplyResult()
    payload = intent.payload
    core_clk = payload.get("core_clk")
    aips_plat_clk = payload.get("aips_plat_clk")
    aips_slow_clk = payload.get("aips_slow_clk")
    add_all_ref_points = payload.get("add_all_clock_reference_points", False)

    # Validate: only supported recipe combos may proceed
    combo = (core_clk, aips_plat_clk, aips_slow_clk)
    if combo not in _MCU_SUPPORTED_RECIPES:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="mcu_unsupported_clock_combo",
            module="mcu",
            message=(
                f"Clock combination core={core_clk}/plat={aips_plat_clk}/"
                f"slow={aips_slow_clk} MHz is not supported. "
                "Only 160/80/40 MHz is supported in Milestone 1."
            ),
            details={
                "core_clk": core_clk,
                "aips_plat_clk": aips_plat_clk,
                "aips_slow_clk": aips_slow_clk,
                "supported": [(160, 80, 40)],
            },
        ))
        return result

    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="mcu_config_set_not_found",
            module="mcu",
            message="No enabled Mcu <config_set> found; M1 edits existing instances only.",
            details={},
        ))
        return result

    # ==================================================================
    # PHASE 1: All raw-bytes operations (clock_settings + struct insertions +
    #          array replacement). These each reload the tree from _raw, so
    #          they must all complete before any attribute mutation.
    # ==================================================================

    # --- Part A: clock_settings (top-level clocks tool) ---

    # A1: Change MC_CGM_MUX_0_DIV1.scale from 1 to 2
    _change_clock_setting_value(doc, "MC_CGM_MUX_0_DIV1.scale", "2")

    # A2: Change MC_CGM_MUX_0_DIV2.scale from 2 to 4
    _change_clock_setting_value(doc, "MC_CGM_MUX_0_DIV2.scale", "4")

    # A2b: Change MC_CGM_MUX_0_DIV3.scale to 2 (HSE_CLK = CORE/2 = 80 MHz).
    # Without this fix CORE_CLK=160 -> HSE_CLK=160 MHz which exceeds the 120 MHz limit,
    # producing SEVERE: "输入频率必须小于或等于： 120 MHz" / "HSE_CLK must be half of the CORE_CLK".
    # Grounded in example_Dio.mex verified working 160MHz example: DIV3.scale=2.
    # Fixture has DIV3.scale=1 -> CHANGE to 2.
    _change_clock_setting_value(doc, "MC_CGM_MUX_0_DIV3.scale", "2")

    # A2c: Ensure MC_CGM_MUX_0_DIV4.scale = 4 (DCM_CLK = CORE/4 = 40 MHz).
    # Grounded in example_Dio.mex verified working 160MHz example: DIV4.scale=4.
    # Fixture already has DIV4.scale=4; this is idempotent (same value).
    _change_clock_setting_value(doc, "MC_CGM_MUX_0_DIV4.scale", "4")

    # A2d: Ensure MC_CGM_MUX_0_DIV6.scale = 1 (QSPI_MEM_CLK = CORE/1 = 160 MHz).
    # Grounded in example_Dio.mex verified working 160MHz example: DIV6.scale=1.
    # Fixture already has DIV6.scale=1; this is idempotent (same value).
    _change_clock_setting_value(doc, "MC_CGM_MUX_0_DIV6.scale", "1")

    # A3: Remove PLLunderMcuControl="Disabled"
    _remove_clock_setting(doc, "PLLunderMcuControl")

    # A4-A7: Insert new settings (only if absent -- idempotency)
    for sid, val in [
        ("CORE_PLL_PD", "Power_up"),
        ("CORE_PLLODIV_0_DE", "Enabled"),
        ("CORE_PLLODIV_1_DE", "Enabled"),
        ("MC_CGM_MUX_0.sel", "PHI0"),
    ]:
        if (b'<setting id="' + re.escape(sid).encode() + b'"') not in doc._raw:
            _insert_clock_setting(doc, sid, val, locked="false")

    # Re-find Mcu config_set after clock_settings raw edits.
    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="mcu_config_set_lost",
            module="mcu",
            message="Mcu config_set was lost after clock_settings raw edits.",
            details={},
        ))
        return result

    # --- Part B raw: McuPll_Parameter field insertion ---
    # Find the current McuPll_Parameter struct and insert PLL fields if absent.
    pll_param = None
    for el in mcu_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "McuPll_Parameter":
            pll_param = el
            break

    if pll_param is not None and doc.find_child_setting(pll_param, "McuPllDvRdiv") is None:
        _insert_settings_into_struct(doc, pll_param, {
            "McuPllDvRdiv": "2",
            "McuPllDvMfi": "120",
            "McuPllDvOdiv2": "2",
            "McuPllOdiv0_Div": "2",
            "McuPllOdiv1_Div": "1",
        })
        mcu_cfg = doc.find_config_set("Mcu")

    # --- Part B raw: McuCgm0ClockMux0 divisor insertion ---
    mux0 = None
    if mcu_cfg is not None:
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuCgm0ClockMux0":
                mux0 = el
                break

    if mux0 is not None and doc.find_child_setting(mux0, "McuClkMux0Div0_Divisor") is None:
        # McuClkMux0Div0/1/2_Divisor are display-only InfoSettings in the Mcu
        # component -- ConfigTools generates the divider code from
        # MC_CGM_MUX_0_DIV0/1/2.scale (written above in Phase 1), NOT from
        # these fields.  These mirror the scale values for human readability:
        #   Div0_Divisor=0 mirrors DIV0.scale=1 (CORE_CLK, divisor=scale-1=0)
        #   Div1_Divisor=1 mirrors DIV1.scale=2 (AIPS_PLAT_CLK, /2)
        #   Div2_Divisor=3 mirrors DIV2.scale=4 (AIPS_SLOW_CLK, /4)
        # They produce the benign [SDK/DATA] "type ... differs ... InfoSettings"
        # log line which can be ignored.  A future reader must NOT "fix" the
        # MC_CGM_MUX_0_DIVx.scale values and leave these stale -- they must
        # stay consistent with the scales.
        _insert_settings_into_struct(doc, mux0, {
            "McuClkMux0Div0_Divisor": "0",
            "McuClkMux0Div1_Divisor": "1",
            "McuClkMux0Div2_Divisor": "3",
        })
        mcu_cfg = doc.find_config_set("Mcu")

    # --- Part B raw: McuClockReferencePoint array MERGE ---
    # Strategy (GAP 3 fix): preserve existing reference points so that UartClockRef
    # paths (e.g. LPUART3_CLK, FLEXIO_CLK) remain resolvable, then add the 13
    # selectable-clock structs (Name == McuClockFrequencySelect) for any clock
    # not already present by Name. Dedup: skip clocks already in the array.
    if add_all_ref_points and mcu_cfg is not None:
        ref_array = None
        for el in mcu_cfg.iter():
            if el.tag.endswith("array") and el.attrib.get("name") == "McuClockReferencePoint":
                ref_array = el
                break

        if ref_array is not None:
            existing_structs = [c for c in ref_array if c.tag.endswith("struct")]

            # Collect names already present
            existing_names: set[str] = set()
            for s in existing_structs:
                ns = doc.find_child_setting(s, "Name")
                if ns is not None:
                    existing_names.add(ns.attrib.get("value", ""))

            # Idempotency: skip if all 13 selectable clocks already present
            new_clocks_needed = [c for c in _ALL_SELECTABLE_CLOCKS if c not in existing_names]
            if new_clocks_needed:
                # Detect indentation of the <array> tag from raw bytes
                elements = list(doc.root.iter())
                src_index = next(
                    (i for i, e in enumerate(elements) if e is ref_array), None
                )
                array_indent = 36  # fixture default
                if src_index is not None and doc._aligned:
                    arr_src = doc._sources[src_index]
                    raw = doc._raw
                    ii = arr_src.start - 1
                    while ii >= 0 and raw[ii:ii + 1] not in (b"\n", b"\r"):
                        ii -= 1
                    ls = ii + 1
                    sp = 0
                    while ls + sp < arr_src.start and raw[ls + sp:ls + sp + 1] == b" ":
                        sp += 1
                    array_indent = sp

                line_ending = _detect_line_ending(doc._raw)
                new_array_bytes = _build_merged_ref_point_array_bytes(
                    doc=doc,
                    existing_structs=existing_structs,
                    new_clocks=_ALL_SELECTABLE_CLOCKS,
                    indent=array_indent,
                    line_ending=line_ending,
                )
                doc.replace_element_region(ref_array, new_array_bytes)
                mcu_cfg = doc.find_config_set("Mcu")

    # ==================================================================
    # PHASE 2: Attribute mutations (no raw-bytes reload after this point).
    # These are captured by _render_minimal when doc.write() is called.
    # All raw-bytes operations are complete; re-find all elements now.
    # ==================================================================

    if mcu_cfg is None:
        mcu_cfg = doc.find_config_set("Mcu")

    if mcu_cfg is not None:
        # B1-B2: McuPll_0 -> McuPLLUnderMcuControl=true, McuPLLEnabled=true
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuPll_0":
                s = doc.find_child_setting(el, "McuPLLUnderMcuControl")
                if s is not None:
                    s.set("value", "true")
                s2 = doc.find_child_setting(el, "McuPLLEnabled")
                if s2 is not None:
                    s2.set("value", "true")
                break

        # B3-B4: McuPll_Configuration -> McuPllOdiv0_En=true, McuPllOdiv1_En=true
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuPll_Configuration":
                s = doc.find_child_setting(el, "McuPllOdiv0_En")
                if s is not None:
                    s.set("value", "true")
                s2 = doc.find_child_setting(el, "McuPllOdiv1_En")
                if s2 is not None:
                    s2.set("value", "true")
                break

        # B5: McuCgm0ClockMux0 -> McuClkMux0_Source=PLL_PHI0_CLK
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuCgm0ClockMux0":
                s = doc.find_child_setting(el, "McuClkMux0_Source")
                if s is not None:
                    s.set("value", "PLL_PHI0_CLK")
                break

        # B6 (GAP 1): McuGeneralConfiguration -> McuNoPll=false
        # Mcu.xdm INVALID rule: McuNoPll='true' AND McuPLLUnderMcuControl='true'
        # produces SEVERE "PLL cannot be under MCU control if McuNoPll is enabled."
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuGeneralConfiguration":
                s = doc.find_child_setting(el, "McuNoPll")
                if s is not None:
                    s.set("value", "false")
                break

        # B7 (GAP 2): McuControlledClocksConfiguration -> McuPll0UnderMcuControl=true
        # Mcu.xdm INVALID rule: McuPLLUnderMcuControl='true' but
        # McuGeneralConfiguration/McuControlledClocksConfiguration/McuPll0UnderMcuControl='false'
        # produces SEVERE: "The field McuGeneralConfiguration/McuControlledClocksConfiguration/
        # McuPll0UnderMcuControl must be set to 'true' when PLL is under MCU control."
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuControlledClocksConfiguration":
                s = doc.find_child_setting(el, "McuPll0UnderMcuControl")
                if s is not None:
                    s.set("value", "true")
                break

    # ==================================================================
    # PHASE 3: Mark modified + clear quick_selection LAST (LL-013 ordering).
    # quick_selection clear must happen after all replace_element_region calls
    # so the final _capture_sources() snapshot sees the clear.
    # ==================================================================

    if mcu_cfg is not None:
        # Mark McuPll_Parameter and clear its quick_selection (LL-013: LAST)
        for el in mcu_cfg.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "McuPll_Parameter":
                doc.mark_modified(el)  # removes quick_selection="Default" if present
                break

    result.changed_modules.append("mcu")
    if mcu_cfg is not None:
        result.modified_elements.append(mcu_cfg)
    return result


# ---------------------------------------------------------------------------
# UART-002: FlexIO Tx+Rx channel pair creation
# ---------------------------------------------------------------------------

def _find_uart_channel_array(doc: MexDocument, uart_cfg: ET.Element) -> "ET.Element | None":
    """Return the UartChannel array inside UartGlobalConfig."""
    for el in uart_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "UartChannel":
            return el
    return None


def _compute_next_uart_channel_id(channel_array: ET.Element, doc: MexDocument) -> int:
    """Return the next UartChannelId (max existing + 1)."""
    max_id = -1
    for ch in channel_array:
        if not ch.tag.endswith("struct"):
            continue
        s = doc.find_child_setting(ch, "UartChannelId")
        if s is not None and s.attrib.get("value"):
            try:
                v = int(s.attrib["value"])
                if v > max_id:
                    max_id = v
            except ValueError:
                pass
    return max_id + 1


def _uart_channel_name_exists(channel_array: ET.Element, doc: MexDocument, name: str) -> bool:
    """Return True if a UartChannel struct with Name==name already exists."""
    for ch in channel_array:
        if not ch.tag.endswith("struct"):
            continue
        n = doc.find_child_setting(ch, "Name")
        if n is not None and n.attrib.get("value") == name:
            return True
    return False


def _build_flexio_uart_channel_bytes(
    struct_index: int,
    channel_name: str,
    uart_channel_id: int,
    clock_ref_path: str,
    mcl_channel_ref: str,
    baud_enum: str,
    bit_count_enum: str,
    direction_enum: str,
    struct_indent: int,
    line_ending: bytes,
) -> bytes:
    """Build raw bytes for one FlexIO UartChannel <struct>.

    Mirrors the EXACT field set and order of Flexio0_Tx / Flexio1_Rx structs in
    the fixture (lines 893-925 and 926-958).

    Top-level fields (struct_indent, e.g. 30 spaces):
      Name, UartHwUsing, UartChannelId, UartClockRef, UartChannelEcucPartitionRef,
      DetailModuleConfiguration sub-struct, FlexioModuleConfiguration sub-struct.

    DetailModuleConfiguration fields (struct_indent+6, e.g. 36 spaces) mirror
    Flexio0_Tx verbatim (dummy LPUART fields; ignored for FLEXIO_IP but required
    by ConfigTools schema):
      Name, UartHwChannel, DesireBaudrate, CustomBaudrateMantissa, CustomBaudrateDivisor,
      UartInteruptDmaMethod, UartDmaTxChannelRef, UartDmaRxChannelRef, UartParityType,
      UartStopBitNumber, UartWordLength, UartInternalLoopbackEnable, UartTimeoutEnable.

    FlexioModuleConfiguration fields (struct_indent+6, e.g. 36 spaces):
      Name, UartHwChannelRef, FlexioUartInteruptDmaMethod, FlexioDmaChannelRef,
      DesireBaudrate, CustomTimerDecrement, CustomBaudrateDivider, bitCount,
      driverDirection.
    """
    le = line_ending.decode("latin-1")
    sp = " " * struct_indent          # struct open/close
    sp1 = " " * (struct_indent + 3)   # direct children of channel struct
    sp2 = " " * (struct_indent + 6)   # children of sub-structs

    # Determine the dummy LPUART channel name based on channel_id
    # (mirrors fixture: Flexio0_Tx uses LPUART_1, Flexio1_Rx uses LPUART_2)
    dummy_lpuart = f"LPUART_{uart_channel_id}"

    lines = [
        f'{sp}<struct name="{struct_index}">',
        f'{sp1}<setting name="Name" value="{channel_name}"/>',
        f'{sp1}<setting name="UartHwUsing" value="FLEXIO_IP"/>',
        f'{sp1}<setting name="UartChannelId" value="{uart_channel_id}"/>',
        f'{sp1}<setting name="UartClockRef" value="{clock_ref_path}"/>',
        f'{sp1}<array name="UartChannelEcucPartitionRef"/>',
        f'{sp1}<struct name="DetailModuleConfiguration">',
        f'{sp2}<setting name="Name" value="DetailModuleConfiguration"/>',
        f'{sp2}<setting name="UartHwChannel" value="{dummy_lpuart}"/>',
        f'{sp2}<setting name="DesireBaudrate" value="LPUART_UART_BAUDRATE_9600"/>',
        f'{sp2}<setting name="CustomBaudrateMantissa" value="1"/>',
        f'{sp2}<setting name="CustomBaudrateDivisor" value="4"/>',
        f'{sp2}<setting name="UartInteruptDmaMethod" value="LPUART_UART_IP_USING_INTERRUPTS"/>',
        f'{sp2}<array name="UartDmaTxChannelRef"/>',
        f'{sp2}<array name="UartDmaRxChannelRef"/>',
        f'{sp2}<setting name="UartParityType" value="LPUART_UART_IP_PARITY_DISABLED"/>',
        f'{sp2}<setting name="UartStopBitNumber" value="LPUART_UART_IP_ONE_STOP_BIT"/>',
        f'{sp2}<setting name="UartWordLength" value="{bit_count_enum}"/>',
        f'{sp2}<setting name="UartInternalLoopbackEnable" value="false"/>',
        f'{sp2}<setting name="UartTimeoutEnable" value="false"/>',
        f'{sp1}</struct>',
        f'{sp1}<struct name="FlexioModuleConfiguration">',
        f'{sp2}<setting name="Name" value="FlexioModuleConfiguration"/>',
        f'{sp2}<setting name="UartHwChannelRef" value="{mcl_channel_ref}"/>',
        f'{sp2}<setting name="FlexioUartInteruptDmaMethod" value="FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS"/>',
        f'{sp2}<array name="FlexioDmaChannelRef"/>',
        f'{sp2}<setting name="DesireBaudrate" value="{baud_enum}"/>',
        f'{sp2}<setting name="CustomTimerDecrement" value="FLEXIO_TIMER_DECREMENT_FXIO_CLK_SHIFT_TMR"/>',
        f'{sp2}<setting name="CustomBaudrateDivider" value="0"/>',
        f'{sp2}<setting name="bitCount" value="{bit_count_enum}"/>',
        f'{sp2}<setting name="driverDirection" value="{direction_enum}"/>',
        f'{sp1}</struct>',
        f'{sp}</struct>',
    ]
    return le.join(lines).encode("utf-8")


def _find_flexio_clock_ref_path(doc: MexDocument) -> str:
    """Return the UartClockRef path for the FLEXIO_CLK ref point.

    Grounded in uart.json FLEXIO entry and the fixture:
    /Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/FLEXIO_CLK
    Looks up dynamically from the Mcu config set to find FLEXIO_CLK.
    Falls back to the fixture-grounded literal if not found.
    """
    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        return "/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/FLEXIO_CLK"

    for el in mcu_cfg.iter():
        if not (el.tag.endswith("array") and el.attrib.get("name") == "McuClockSettingConfig"):
            continue
        for cs in el:
            if not cs.tag.endswith("struct"):
                continue
            ns = doc.find_child_setting(cs, "Name")
            cs_name = ns.attrib.get("value", "") if ns is not None else ""
            for child in cs.iter():
                if not (child.tag.endswith("array")
                        and child.attrib.get("name") == "McuClockReferencePoint"):
                    continue
                for rp in child:
                    if not rp.tag.endswith("struct"):
                        continue
                    rn = doc.find_child_setting(rp, "Name")
                    if rn is not None and rn.attrib.get("value") == "FLEXIO_CLK":
                        return f"/Mcu/Mcu/McuModuleConfiguration/{cs_name}/FLEXIO_CLK"

    return "/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/FLEXIO_CLK"


def apply_uart_add_flexio_channel(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Create a FlexIO Tx+Rx UART channel pair (RTD-MEX-UART-002).

    Performs four orchestrated edits in one call:

    1. **Mcl-owned** (config_set "Mcl"):
       Insert TWO new FlexioMclLogicChannels structs:
         - UART2_TX: next-available CHANNEL_N / PIN_N
         - UART2_RX: next-available CHANNEL_N+1 / PIN_N+1
       Idempotent: skip if Name already exists.

    2. **Uart-owned** (config_set "Uart"):
       Append TWO new UartChannel structs to UartGlobalConfig/UartChannel:
         - UART2_TX: UartHwUsing=FLEXIO_IP, UartChannelId=next, driverDirection=TX
         - UART2_RX: UartHwUsing=FLEXIO_IP, UartChannelId=next+1, driverDirection=RX
       Each carries DetailModuleConfiguration (dummy LPUART fields, byte-faithful
       mirror of fixture Flexio0_Tx) and FlexioModuleConfiguration with:
         UartHwChannelRef -> /Mcl/.../UART2_TX or UART2_RX
         FlexioUartInteruptDmaMethod=FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS
         DesireBaudrate=FLEXIO_UART_BAUDRATE_<baud>
         bitCount=FLEXIO_UART_IP_8_BITS_PER_CHAR (or from word_length)
         driverDirection=TX or RX
       Idempotent: skip if Name already exists.

    3. **Callback** (Uart-owned GeneralConfiguration):
       Set UartCallbackCapability=true + UartCallback[0]=<callback> (when --callback).

    4. **Platform/Mcu idempotent ensure**:
       FLEXIO_IRQn with MCL_FLEXIO_ISR: verify present (no-op if already there --
       the fixture has it; never add a duplicate).
       FLEXIO_CLK with CORE_CLK: verify present (no-op if already there).

    Byte-faithful: mirrors the EXACT field set/order of Flexio0_Tx and Flexio1_Rx.
    Narrowness: only appends new structs; never rewrites existing content.
    changed_modules: the set actually edited (["uart", "mcl"] always; platform/mcu
    only if they were absent and had to be inserted).

    Intent payload:
      baud (int): baud rate, e.g. 921600
      word_length (int|str): bit count, e.g. 8 (maps to FLEXIO_UART_IP_8_BITS_PER_CHAR)
      mode (str): 'interrupt' (only supported mode)
      callback (str, optional): callback function name
      tx_name (str, optional): name for TX MCL/Uart channel (default 'UART2_TX')
      rx_name (str, optional): name for RX MCL/Uart channel (default 'UART2_RX')
    """
    result = ApplyResult()
    payload = intent.payload
    mode = payload.get("mode", "interrupt")
    baud = payload.get("baud", 921600)
    word_length = payload.get("word_length", 8)
    callback = payload.get("callback")
    tx_name = payload.get("tx_name", "UART2_TX")
    rx_name = payload.get("rx_name", "UART2_RX")

    if mode not in _FLEXIO_METHOD:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="unsupported_uart_mode",
            module="uart",
            message=(
                f"Uart mode '{mode}' is not supported. RTD 7.0.1 FlexIO UART "
                "supports interrupt mode only (DMA deferred). Use mode 'interrupt'."
            ),
            details={"mode": mode, "supported": sorted(_FLEXIO_METHOD)},
        ))
        return result

    # Load asset to validate baud and build MCL ref path (Fix 1 / LL-012).
    uart_asset = _load_uart_asset()

    # Validate baud against FlexioDesireBaudrate enum domain (LOAD approach).
    valid_baud_enums: list[str] = uart_asset["enum_domains"]["FlexioDesireBaudrate"]
    baud_enum = f"FLEXIO_UART_BAUDRATE_{baud}"
    if baud_enum not in valid_baud_enums:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="unsupported_flexio_baud",
            module="uart",
            message=(
                f"FlexIO UART baud rate {baud!r} is not supported. "
                f"Supported values: {valid_baud_enums}."
            ),
            details={"baud": baud, "baud_enum": baud_enum, "valid_bauds": valid_baud_enums},
        ))
        return result

    # word_length: accept int or str "8" -> FLEXIO_UART_IP_8_BITS_PER_CHAR
    wl_str = str(word_length)
    bit_count_enum = f"FLEXIO_UART_IP_{wl_str}_BITS_PER_CHAR"

    # MCL ref path pattern: LOADED from uart.json mcl_ref_path_pattern (Fix 1 / LL-012).
    mcl_ref_pattern: str = uart_asset["mcl_ref_path_pattern"]
    mcl_ref_tx = mcl_ref_pattern.format(channel_name=tx_name)
    mcl_ref_rx = mcl_ref_pattern.format(channel_name=rx_name)

    line_ending = _detect_line_ending(doc._raw)

    # =====================================================================
    # PHASE 1: Raw-bytes insertions (replace_element_region splices).
    # All raw-bytes ops BEFORE any attribute mutations.
    # Order: MCL channels first (both), then Uart channels (both), then
    # Platform/Mcu ensure (idempotent no-ops if already present).
    # Each replace_element_region reloads the tree, so re-find after each.
    # =====================================================================

    # ---- Part 1a: Mcl UART2_TX logic channel ----
    _apply_mcl_add_channel_inner(doc, tx_name, result)
    if result.blocked:
        return result

    # ---- Part 1b: Mcl UART2_RX logic channel (after tx, so pin/channel indices are correct) ----
    _apply_mcl_add_channel_inner(doc, rx_name, result)
    if result.blocked:
        return result

    # ---- Part 1c: Uart UART2_TX channel ----
    _apply_uart_append_flexio_channel_inner(
        doc, tx_name, mcl_ref_tx, baud_enum, bit_count_enum,
        "FLEXIO_UART_IP_DIRECTION_TX", line_ending, result,
    )
    if result.blocked:
        return result

    # ---- Part 1d: Uart UART2_RX channel ----
    _apply_uart_append_flexio_channel_inner(
        doc, rx_name, mcl_ref_rx, baud_enum, bit_count_enum,
        "FLEXIO_UART_IP_DIRECTION_RX", line_ending, result,
    )
    if result.blocked:
        return result

    # ---- Part 1e: Ensure FLEXIO_CLK in Mcu (idempotent no-op if present).
    # Returns True only when an insertion was made (absent before this call).
    mcu_inserted = _ensure_mcu_clock_ref(doc, "FLEXIO_CLK", "CORE_CLK")

    # ---- Part 1f: Ensure FLEXIO_IRQn in Platform (idempotent no-op if present).
    # Returns True only when an insertion was made (absent before this call).
    platform_inserted = _ensure_platform_isr(
        doc,
        irq_name="FLEXIO_IRQn",
        isr_handler="MCL_FLEXIO_ISR",
        priority=0,
    )

    # =====================================================================
    # PHASE 2: Attribute mutations (no raw-bytes reload after this point).
    # Re-find Uart config set after all Phase 1 reloads.
    # =====================================================================

    uart_cfg = doc.find_config_set("Uart")
    if callback is not None and uart_cfg is not None:
        _apply_uart_callback(doc, uart_cfg, callback)

    # =====================================================================
    # PHASE 3: mark_modified + clear quick_selection LAST (LL-013 ordering).
    # =====================================================================

    # Mark Mcl channels array
    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is not None:
        channels_array = _find_flexio_channels_array(doc, mcl_cfg)
        if channels_array is not None:
            doc.mark_modified(channels_array)
            carrier = doc.find_nearest_quick_selection_ancestor(channels_array)
            if carrier is not None:
                doc.mark_modified(carrier)
            result.modified_elements.append(channels_array)

    # Mark Uart channel array
    uart_cfg_final = doc.find_config_set("Uart")
    if uart_cfg_final is not None:
        uart_channel_array = _find_uart_channel_array(doc, uart_cfg_final)
        if uart_channel_array is not None:
            doc.mark_modified(uart_channel_array)
            carrier = doc.find_nearest_quick_selection_ancestor(uart_channel_array)
            if carrier is not None:
                doc.mark_modified(carrier)
            result.modified_elements.append(uart_channel_array)

    # Mark Platform config only when an insertion was actually made (not a no-op).
    if platform_inserted:
        platform_cfg_final = doc.find_config_set("Platform")
        if platform_cfg_final is not None:
            doc.mark_modified(platform_cfg_final)
            result.modified_elements.append(platform_cfg_final)

    # Mark Mcu config only when an insertion was actually made (not a no-op).
    if mcu_inserted:
        mcu_cfg_final = doc.find_config_set("Mcu")
        if mcu_cfg_final is not None:
            doc.mark_modified(mcu_cfg_final)
            result.modified_elements.append(mcu_cfg_final)

    # changed_modules: uart and mcl always (both get new channel structs);
    # platform/mcu only when an entry was actually inserted (not a no-op).
    result.changed_modules = ["uart", "mcl"]
    if platform_inserted:
        result.changed_modules.append("platform")
    if mcu_inserted:
        result.changed_modules.append("mcu")

    return result


def _apply_mcl_add_channel_inner(
    doc: MexDocument,
    channel_name: str,
    result: ApplyResult,
) -> None:
    """Reuse apply_mcl_set's insertion logic to add one MCL channel.

    This is a delegating helper that constructs a synthetic Intent and calls
    apply_mcl_set, then propagates any blockers into result.
    """
    synthetic_intent = Intent.from_dict({
        "module": "mcl",
        "action": "set",
        "payload": {"add_flexio_logic_channel": channel_name},
    })
    mcl_result = apply_mcl_set(doc, synthetic_intent)
    for d in mcl_result.diagnostics:
        result.diagnostics.append(d)
    for m in mcl_result.changed_modules:
        if m not in result.changed_modules:
            result.changed_modules.append(m)


def _apply_uart_append_flexio_channel_inner(
    doc: MexDocument,
    channel_name: str,
    mcl_ref: str,
    baud_enum: str,
    bit_count_enum: str,
    direction_enum: str,
    line_ending: bytes,
    result: ApplyResult,
) -> bool:
    """Append one FlexIO Uart channel struct to UartGlobalConfig/UartChannel.

    Idempotent: skip if a channel with channel_name already exists.
    Returns True if an insertion was made, False if it was a no-op.
    Propagates blockers into result if the Uart config set is not found.
    """
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="uart_config_set_not_found",
            module="uart",
            message="No enabled Uart <config_set> found; cannot add FlexIO channel.",
            details={},
        ))
        return False

    channel_array = _find_uart_channel_array(doc, uart_cfg)
    if channel_array is None:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="uart_channel_array_not_found",
            module="uart",
            message="No UartChannel array found in UartGlobalConfig.",
            details={},
        ))
        return False

    # Idempotency: skip if name already exists
    if _uart_channel_name_exists(channel_array, doc, channel_name):
        return False  # no-op

    # Compute next UartChannelId dynamically
    next_channel_id = _compute_next_uart_channel_id(channel_array, doc)

    # Count existing structs for the struct index
    existing_structs = [c for c in channel_array if c.tag.endswith("struct")]
    struct_index = len(existing_structs)

    # Discover the FLEXIO_CLK ref path from the live Mcu config
    clock_ref_path = _find_flexio_clock_ref_path(doc)

    # Detect the struct indent from the last existing channel struct
    last_struct = existing_structs[-1] if existing_structs else None
    if last_struct is not None:
        struct_indent = _detect_struct_indent(doc, last_struct)
    else:
        struct_indent = 30  # fixture level for UartChannel structs

    # Determine LPUART word-length enum for DetailModuleConfiguration
    # (dummy field -- not functional for FLEXIO_IP, but schema requires it)
    # We pass bit_count_enum which is FLEXIO_UART_IP_8_BITS_PER_CHAR, but
    # UartWordLength uses LPUART_UART_IP_8_BITS_PER_CHAR. Always use 8-bit LPUART default.
    lpuart_wl = "LPUART_UART_IP_8_BITS_PER_CHAR"

    new_struct_bytes = _build_flexio_uart_channel_bytes(
        struct_index=struct_index,
        channel_name=channel_name,
        uart_channel_id=next_channel_id,
        clock_ref_path=clock_ref_path,
        mcl_channel_ref=mcl_ref,
        baud_enum=baud_enum,
        bit_count_enum=bit_count_enum,
        direction_enum=direction_enum,
        struct_indent=struct_indent,
        line_ending=line_ending,
    )

    if last_struct is not None:
        ok = _append_after_last_element(doc, last_struct, new_struct_bytes, line_ending)
        if not ok:
            # Fallback: insert before array close tag
            _append_struct_before_array_close(doc, channel_array, new_struct_bytes, line_ending)
    else:
        # Empty array -- replace self-closed array
        le = line_ending.decode("latin-1")
        sp_array = " " * (struct_indent - 3)
        array_bytes = (
            f'<array name="UartChannel">{le}'
            f'{new_struct_bytes.decode("utf-8")}{le}'
            f'{sp_array}</array>'
        ).encode("utf-8")
        doc.replace_element_region(channel_array, array_bytes)

    return True
