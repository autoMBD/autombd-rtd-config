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
# File:        static.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Static checks for S32 ConfigTools .mex projects.
# =================================================================================

"""Fast, vendor-free static checks for S32 ConfigTools .mex projects.

These checks run during development testing and as the first stage of runtime
verification after a .mex edit. They never launch a vendor tool. The rules
encode failure patterns established during the legacy-skills experience:

- XML well-formedness;
- single .mex detection;
- enabled module list;
- duplicate enabled-instance-name warning;
- quick_selection conflict on planned/applied edits;
- stale FlexIO Uart UartHwChannelRef detection;
- missing Mcl FlexIO logic-channel detection;
- duplicate LPUART hardware channel detection;
- invalid Uart callback (NULL_PTR / non-C-identifier) detection;
- DMA coherence: a DMA Uart requires Mcl DMA enabled and complete Tx/Rx DMA
  channel refs (codes dma_mcl_not_enabled / dma_refs_incomplete).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.locate import find_single_mex
from rtd_config.backends.s32_mex.static_check import is_xml_well_formed
from rtd_config.diagnostics import Diagnostic, Result


_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _settings_named(root: ET.Element, name: str) -> list[ET.Element]:
    return [
        s for s in root.iter()
        if s.tag.endswith("setting") and s.attrib.get("name") == name
    ]


def flexio_logic_channel_refs(doc: MexDocument) -> set[str]:
    """Return the set of valid FlexIO logic-channel reference paths.

    A reference is the full path under a FlexioCommon entry. Both the explicit
    channel Name (e.g. ``UART_TX``) and the array-index default form
    (``FlexioMclLogicChannels_<index>``) are accepted, matching the leaf forms
    observed in real fixtures.
    """
    refs: set[str] = set()
    for common_array in doc.root.iter():
        if not (common_array.tag.endswith("array") and common_array.attrib.get("name") == "FlexioCommon"):
            continue
        for common in common_array:
            common_name_el = doc.find_child_setting(common, "Name")
            common_name = common_name_el.attrib.get("value") if common_name_el is not None else None
            if not common_name:
                continue
            base = f"/Mcl/Mcl/MclConfig/{common_name}"
            for lc_array in common.iter():
                if not (lc_array.tag.endswith("array") and lc_array.attrib.get("name") == "FlexioMclLogicChannels"):
                    continue
                for index, channel in enumerate(
                    [c for c in lc_array if c.tag.endswith("struct")]
                ):
                    name_el = doc.find_child_setting(channel, "Name")
                    if name_el is not None and name_el.attrib.get("value"):
                        refs.add(f"{base}/{name_el.attrib['value']}")
                    # Array-index default form is also a valid reference target.
                    refs.add(f"{base}/FlexioMclLogicChannels_{index}")
    return refs


def _check_xml_and_single_mex(mex_path: Path, checks: dict, diagnostics: list[Diagnostic]) -> None:
    well_formed = is_xml_well_formed(mex_path)
    checks["xml_well_formed"] = well_formed
    if not well_formed:
        diagnostics.append(Diagnostic(
            severity="blocker",
            code="xml_not_well_formed",
            module="backend",
            message=f"{mex_path.name} is not well-formed XML.",
            details={"path": str(mex_path)},
        ))
    try:
        located = find_single_mex(mex_path.parent)
        checks["single_mex"] = located == mex_path
    except ValueError as exc:
        checks["single_mex"] = False
        diagnostics.append(Diagnostic(
            severity="blocker",
            code="not_single_mex",
            module="backend",
            message=str(exc),
            details={"project": str(mex_path.parent)},
        ))


def _check_enabled_modules(doc: MexDocument, checks: dict, diagnostics: list[Diagnostic]) -> None:
    enabled = sorted(doc.enabled_instance_names())
    checks["enabled_modules"] = enabled
    seen: set[str] = set()
    duplicates: set[str] = set()
    for instance in doc.iter_instances():
        if instance.attrib.get("enabled", "true") == "false":
            continue
        name = instance.attrib.get("name")
        if not name:
            continue
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    for name in sorted(duplicates):
        diagnostics.append(Diagnostic(
            severity="warning",
            code="duplicate_enabled_instance_name",
            module="backend",
            message=f"Enabled instance name '{name}' appears more than once.",
            details={"instance": name},
        ))


def _check_dma(doc: MexDocument, diagnostics: list[Diagnostic]) -> None:
    """DMA configuration validation.

    DMA mode (RTD-MEX-UART-003) is supported. When a Uart channel has
    UartInteruptDmaMethod == LPUART_UART_IP_USING_DMA (or GeneralConfiguration
    UartDmaEnable == true), the Uart.xdm INVALID rule requires:
      - UartDmaTxChannelRef[0] must be non-empty.
      - UartDmaRxChannelRef[0] must be non-empty.
      - Mcl MclEnableDma must be true.

    Missing or incomplete DMA configuration is a blocker: ConfigTools marks these
    fields INVALID and rejects the configuration.

    Channels with UartInteruptDmaMethod != LPUART_UART_IP_USING_DMA are skipped
    (interrupt mode has no DMA refs and MclEnableDma may remain false).

    Grounded in: Uart.xdm INVALID rules (domain-truth §1); fixture
    Uart_Example_S32K344; uart.json UartInteruptDmaMethod enum domain.
    """
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return

    # Collect all LPUART channels that use DMA method
    dma_channels: list[ET.Element] = []
    for array in uart_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "UartChannel"):
            continue
        for channel in array:
            if not channel.tag.endswith("struct"):
                continue
            using_el = doc.find_child_setting(channel, "UartHwUsing")
            if using_el is None or using_el.attrib.get("value") != "LPUART_IP":
                continue
            # Look for UartInteruptDmaMethod in DetailModuleConfiguration
            for el in channel.iter():
                if el.tag.endswith("struct") and el.attrib.get("name") == "DetailModuleConfiguration":
                    method_el = doc.find_child_setting(el, "UartInteruptDmaMethod")
                    if (
                        method_el is not None
                        and method_el.attrib.get("value") == "LPUART_UART_IP_USING_DMA"
                    ):
                        dma_channels.append(channel)
                    break

    if not dma_channels:
        return

    # At least one DMA channel present: check MclEnableDma
    mcl_dma_enabled = False
    for setting in doc.root.iter():
        if setting.tag.endswith("setting") and setting.attrib.get("name") == "MclEnableDma":
            if setting.attrib.get("value", "false").lower() == "true":
                mcl_dma_enabled = True
                break

    if not mcl_dma_enabled:
        diagnostics.append(Diagnostic(
            severity="blocker",
            code="dma_mcl_not_enabled",
            module="mcl",
            message=(
                "Uart DMA mode requires MclEnableDma=true in Mcl configuration. "
                "Set MclEnableDma=true or use interrupt mode."
            ),
            details={},
        ))

    # For each DMA channel, check that Tx/Rx refs are populated
    for channel in dma_channels:
        ch_name = _channel_name(doc, channel)
        tx_populated = False
        rx_populated = False
        for el in channel.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "DetailModuleConfiguration":
                for child in el:
                    if child.tag.endswith("array") and child.attrib.get("name") == "UartDmaTxChannelRef":
                        for item in child:
                            if item.attrib.get("name") == "0" and item.attrib.get("value", "").strip():
                                tx_populated = True
                    if child.tag.endswith("array") and child.attrib.get("name") == "UartDmaRxChannelRef":
                        for item in child:
                            if item.attrib.get("name") == "0" and item.attrib.get("value", "").strip():
                                rx_populated = True
                break

        if not tx_populated or not rx_populated:
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="dma_refs_incomplete",
                module="uart",
                message=(
                    "Uart DMA channel requires non-empty UartDmaTxChannelRef[0] and "
                    "UartDmaRxChannelRef[0] (Uart.xdm INVALID rule)."
                ),
                details={"channel": ch_name, "tx_populated": tx_populated, "rx_populated": rx_populated},
            ))


def _check_flexio_refs(doc: MexDocument, diagnostics: list[Diagnostic]) -> None:
    valid_refs = flexio_logic_channel_refs(doc)
    flexio_common_enabled = any(
        s.attrib.get("value", "false").lower() == "true"
        for s in _settings_named(doc.root, "MclEnableFlexioCommon")
    )

    # Find every FlexIO-using Uart channel and verify its UartHwChannelRef.
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return
    for array in uart_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "UartChannel"):
            continue
        for channel in array:
            if not channel.tag.endswith("struct"):
                continue
            using_el = doc.find_child_setting(channel, "UartHwUsing")
            if using_el is None or using_el.attrib.get("value") != "FLEXIO_IP":
                continue
            # An active FlexIO Uart channel needs Mcl FlexIO common + a channel.
            if not flexio_common_enabled or not valid_refs:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="missing_mcl_flexio_logic_channel",
                    module="mcl",
                    message="FlexIO-backed Uart channel requires an existing Mcl FlexIO logic channel.",
                    details={"channel": _channel_name(doc, channel)},
                ))
                continue
            ref_el = None
            for setting in channel.iter():
                if setting.tag.endswith("setting") and setting.attrib.get("name") == "UartHwChannelRef":
                    ref_el = setting
                    break
            ref_value = ref_el.attrib.get("value") if ref_el is not None else None
            if ref_value not in valid_refs:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="stale_flexio_uart_hw_channel_ref",
                    module="uart",
                    message="FlexIO Uart UartHwChannelRef does not point to an existing Mcl FlexIO logic channel.",
                    details={"ref": ref_value, "channel": _channel_name(doc, channel)},
                ))


def _channel_name(doc: MexDocument, channel: ET.Element) -> str | None:
    name_el = doc.find_child_setting(channel, "Name")
    return name_el.attrib.get("value") if name_el is not None else None


def _check_duplicate_lpuart_hw(doc: MexDocument, diagnostics: list[Diagnostic]) -> None:
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return
    used: dict[str, int] = {}
    for array in uart_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "UartChannel"):
            continue
        for channel in array:
            if not channel.tag.endswith("struct"):
                continue
            using_el = doc.find_child_setting(channel, "UartHwUsing")
            if using_el is None or using_el.attrib.get("value") != "LPUART_IP":
                continue
            hw_el = doc.find_child_setting(channel, "UartHwChannel")
            if hw_el is None:
                continue
            hw = hw_el.attrib.get("value", "")
            used[hw] = used.get(hw, 0) + 1
    for hw, count in sorted(used.items()):
        if count > 1:
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="duplicate_lpuart_hw_channel",
                module="uart",
                message=f"LPUART hardware instance '{hw}' is used by {count} active Uart channels.",
                details={"hw": hw, "count": count},
            ))


def _check_uart_channel_ids(doc: MexDocument, diagnostics: list[Diagnostic]) -> None:
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return
    for array in uart_cfg.iter():
        if not (array.tag.endswith("array") and array.attrib.get("name") == "UartChannel"):
            continue
        index = 0
        for channel in array:
            if not channel.tag.endswith("struct"):
                continue
            id_el = doc.find_child_setting(channel, "UartChannelId")
            if id_el is not None and id_el.attrib.get("value") != str(index):
                diagnostics.append(Diagnostic(
                    severity="error",
                    code="uart_channel_id_mismatch",
                    module="uart",
                    message="UartChannelId must match the channel array index.",
                    details={"index": index, "id": id_el.attrib.get("value")},
                ))
            index += 1


def _check_quick_selection_conflict(
    doc: MexDocument,
    modified_elements: Iterable[ET.Element],
    diagnostics: list[Diagnostic],
) -> None:
    for element in modified_elements:
        carrier = doc.find_nearest_quick_selection_ancestor(element)
        if carrier is not None:
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="quick_selection_conflict",
                module="backend",
                message="A modified element still carries quick_selection; ConfigTools may revert it.",
                details={
                    "quick_selection": carrier.attrib.get("quick_selection"),
                    "element": carrier.attrib.get("name"),
                },
            ))


def _check_callback(requested_callback: str | None, diagnostics: list[Diagnostic]) -> None:
    if requested_callback is None:
        return
    if requested_callback == "NULL_PTR" or not _C_IDENTIFIER.match(requested_callback):
        diagnostics.append(Diagnostic(
            severity="blocker",
            code="invalid_uart_callback",
            module="uart",
            message="Uart callback must be a valid C identifier; NULL_PTR is not accepted.",
            details={"callback": requested_callback},
        ))


def _mcl_dma_enabled(doc: MexDocument) -> bool:
    """Return True when the Mcl MclEnableDma global switch is true.

    Shared by the Uart DMA, ADC unit-DMA, and BCTU FIFO-DMA coherence checks: all
    three consume an Mcl DMA logic channel and require the global Mcl DMA enable.
    """
    for setting in doc.root.iter():
        if setting.tag.endswith("setting") and setting.attrib.get("name") == "MclEnableDma":
            if setting.attrib.get("value", "false").lower() == "true":
                return True
    return False


def _adc_channel_enum() -> set[str]:
    """Return the device ADC channel-name enum from the committed adc.json asset.

    Runtime reads only the committed asset, never the raw .epd. Returns an empty
    set if the asset is unavailable so the check degrades to a no-op rather than
    raising.
    """
    try:
        from rtd_config.backends.s32_mex.apply import _load_adc_asset
        return set(_load_adc_asset().get("channel_name_to_id", {}).keys())
    except Exception:  # pragma: no cover - asset always present in this repo
        return set()


def _adc_unit_structs(doc: MexDocument, adc_cfg: ET.Element) -> list[ET.Element]:
    units: list[ET.Element] = []
    for el in adc_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwUnit":
            units.extend(c for c in el if c.tag.endswith("struct"))
    return units


def _adc_hw_config_by_id(doc: MexDocument, adc_cfg: ET.Element) -> dict[str, ET.Element]:
    out: dict[str, ET.Element] = {}
    for el in adc_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwConfiguration":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                s = doc.find_child_setting(child, "AdcHwConfiguredId")
                if s is not None and s.attrib.get("value"):
                    out[s.attrib["value"]] = child
    return out


def _check_adc(doc: MexDocument, diagnostics: list[Diagnostic]) -> None:
    """ADC coherence validation (RTD-MEX-ADC-001).

    Encodes the Adc.xdm INVALID rules that ConfigTools would otherwise report as
    SEVERE on an incoherent edit:
      - interrupt transfer (AdcTransferType=ADC_INTERRUPT) requires the unit's
        AdcHwConfiguration[AdcHwConfiguredId=<unit>]/AdcNormalInterruptEnable=true
        (adc_interrupt_not_enabled);
      - a channel with AdcEnableThresholds=true requires AdcEnableWatchdogApi=true
        (adc_watchdog_api_disabled), the unit's WdgThresholdEnable=true
        (adc_unit_wdg_threshold_disabled), a non-empty AdcThresholdRegister ref +
        a matching AdcThresholdControl entry (adc_threshold_ref_incomplete), and a
        valid AdcWdogNotification (adc_watchdog_notification_invalid);
      - a channel name must exist in the device channel enum
        (adc_channel_not_in_device);
      - an ADC_DMA unit requires the global Mcl DMA enable (adc_dma_mcl_not_enabled)
        and a non-empty AdcDmaChannelId ref (adc_dma_refs_incomplete; Adc.xdm L334);
      - a BCTU result FIFO with BctuFifoDmaEnable=true requires the global Mcl DMA
        enable (adc_dma_mcl_not_enabled) and a non-empty BctuFifoDmaChannelId ref
        (adc_dma_refs_incomplete; Adc.xdm L5041). These DMA rules mirror the Uart
        _check_dma model (the cross-module Mcl wiring the apply tail performs);
      - a SINGLE-access group must have AdcStreamingNumSamples==1 and a
        STREAMING-access group must have it >1 (adc_group_single_num_samples_invalid
        / adc_group_streaming_num_samples_invalid; Adc.xdm AdcStreamingNumSamples
        L3405-3411);
      - a SINGLE-conversion BctuInternalTrigger must select a single ADC bit in
        BctuAdcTargetMask (adc_bctu_target_mask_invalid; Adc.xdm L4539-4540) and a
        LIST trigger's BctuConversionListStartIndex must be < the BctuListItems
        count (adc_bctu_list_start_index_invalid; Adc.xdm L4621).

    Grounded in Adc.xdm INVALID/RANGE rules (L334/L2758/L2759/L2760/L2761/L3410/
    L4539/L4621/L5041) + the committed adc.json channel enum. Units with no
    threshold-enabled channels are skipped by the watchdog rules so the baseline
    ADC0 fixture stays clean. These checks guard ARBITRARY valid inputs against the
    same Adc.xdm rules the vendor enforces, not just the four ADC E2E cases.
    """
    adc_cfg = doc.find_config_set("Adc")
    if adc_cfg is None:
        return

    channel_enum = _adc_channel_enum()
    hw_configs = _adc_hw_config_by_id(doc, adc_cfg)

    # Adc-global watchdog API switch.
    wdg_api_setting = doc.find_child_setting(adc_cfg, "AdcEnableWatchdogApi")
    wdg_api_enabled = (
        wdg_api_setting is not None
        and wdg_api_setting.attrib.get("value", "false").lower() == "true"
    )

    # Mcl DMA global enable, shared by the ADC unit-DMA and BCTU FIFO-DMA rules.
    mcl_dma_enabled = _mcl_dma_enabled(doc)

    for unit in _adc_unit_structs(doc, adc_cfg):
        unit_id_el = doc.find_child_setting(unit, "AdcHwUnitId")
        unit_id = unit_id_el.attrib.get("value") if unit_id_el is not None else None
        unit_name_el = doc.find_child_setting(unit, "Name")
        unit_name = unit_name_el.attrib.get("value") if unit_name_el is not None else None
        transfer_el = doc.find_child_setting(unit, "AdcTransferType")
        transfer = transfer_el.attrib.get("value") if transfer_el is not None else None

        # Collect this unit's direct AdcChannel / AdcGroup / AdcThresholdControl.
        channels: list[ET.Element] = []
        groups: list[ET.Element] = []
        threshold_controls: list[ET.Element] = []
        for child in unit:
            if not (child.tag.endswith("array")):
                continue
            if child.attrib.get("name") == "AdcChannel":
                channels = [c for c in child if c.tag.endswith("struct")]
            elif child.attrib.get("name") == "AdcGroup":
                groups = [c for c in child if c.tag.endswith("struct")]
            elif child.attrib.get("name") == "AdcThresholdControl":
                threshold_controls = [c for c in child if c.tag.endswith("struct")]

        threshold_channels = [
            c for c in channels
            if (doc.find_child_setting(c, "AdcEnableThresholds") is not None
                and doc.find_child_setting(c, "AdcEnableThresholds").attrib.get("value") == "true")
        ]

        # Group access-mode vs sample-count coherence (Adc.xdm AdcStreamingNumSamples
        # L3405-3411 + DESC L3389-3391): a SINGLE-access group must have
        # AdcStreamingNumSamples == 1 (vendor RANGE rule, L3410); a STREAMING-access
        # group acquires several samples per channel (DESC), so a value <= 1 is a
        # degenerate streaming group ConfigTools would not produce -- guard it so an
        # arbitrary input is held to the same shape the vendor enforces.
        for grp in groups:
            access_el = doc.find_child_setting(grp, "AdcGroupAccessMode")
            access = access_el.attrib.get("value") if access_el is not None else None
            ns_el = doc.find_child_setting(grp, "AdcStreamingNumSamples")
            if ns_el is None or access is None:
                continue
            try:
                num_samples = int(ns_el.attrib.get("value", "1"))
            except ValueError:
                continue
            gname_el = doc.find_child_setting(grp, "Name")
            gname = gname_el.attrib.get("value") if gname_el is not None else None
            if access == "ADC_ACCESS_MODE_SINGLE" and num_samples != 1:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_group_single_num_samples_invalid",
                    module="adc",
                    message=(
                        f"ADC group '{gname}' (unit {unit_id}) is SINGLE access mode "
                        f"but AdcStreamingNumSamples={num_samples}; it must be 1 for "
                        f"ADC_ACCESS_MODE_SINGLE (Adc.xdm AdcStreamingNumSamples RANGE)."
                    ),
                    details={"unit": unit_id, "group": gname, "num_samples": num_samples},
                ))
            elif access == "ADC_ACCESS_MODE_STREAMING" and num_samples <= 1:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_group_streaming_num_samples_invalid",
                    module="adc",
                    message=(
                        f"ADC group '{gname}' (unit {unit_id}) is STREAMING access mode "
                        f"but AdcStreamingNumSamples={num_samples}; a streaming group "
                        f"acquires more than one sample per channel (Adc.xdm "
                        f"AdcStreamingNumSamples)."
                    ),
                    details={"unit": unit_id, "group": gname, "num_samples": num_samples},
                ))

        # Interrupt transfer needs the unit's AdcNormalInterruptEnable=true.
        if transfer == "ADC_INTERRUPT" and unit_id is not None:
            hw_cfg = hw_configs.get(unit_id)
            ni = doc.find_child_setting(hw_cfg, "AdcNormalInterruptEnable") if hw_cfg is not None else None
            if hw_cfg is None or ni is None or ni.attrib.get("value", "false").lower() != "true":
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_interrupt_not_enabled",
                    module="adc",
                    message=(
                        f"ADC unit {unit_id} uses ADC_INTERRUPT transfer but its "
                        f"AdcHwConfiguration[AdcHwConfiguredId={unit_id}]/"
                        f"AdcNormalInterruptEnable is not true. Add/flip that "
                        f"AdcHwConfiguration entry."
                    ),
                    details={"unit": unit_id},
                ))

        # DMA transfer coherence (modelled on the Uart _check_dma rules). An
        # AdcTransferType=ADC_DMA unit consumes an Mcl DMA logic channel:
        #   - MclEnableDma must be true (the global Mcl DMA switch; adc.xdm wires
        #     AdcDmaChannelId -> /Mcl/.../dmaLogicChannel_Type, which is inert when
        #     Mcl DMA is off) -> adc_dma_mcl_not_enabled;
        #   - AdcDmaChannelId must hold a non-empty logic-channel ref (Adc.xdm L334
        #     INVALID: not(node:refvalid(.)) and AdcTransferType='ADC_DMA') ->
        #     adc_dma_refs_incomplete.
        if transfer == "ADC_DMA":
            if not mcl_dma_enabled:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_dma_mcl_not_enabled",
                    module="mcl",
                    message=(
                        f"ADC unit {unit_id} uses ADC_DMA transfer but "
                        f"MclEnableDma is not true in the Mcl configuration. Set "
                        f"MclEnableDma=true or use interrupt mode."
                    ),
                    details={"unit": unit_id},
                ))
            dma_ref_populated = False
            for child in unit:
                if child.tag.endswith("array") and child.attrib.get("name") == "AdcDmaChannelId":
                    for item in child:
                        if (
                            item.tag.endswith("setting")
                            and item.attrib.get("value", "").strip()
                        ):
                            dma_ref_populated = True
                    break
            if not dma_ref_populated:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_dma_refs_incomplete",
                    module="adc",
                    message=(
                        f"ADC unit {unit_id} uses ADC_DMA transfer but its "
                        f"AdcDmaChannelId reference is empty. Populate it with an "
                        f"Mcl dmaLogicChannel_Type ref (Adc.xdm INVALID rule)."
                    ),
                    details={"unit": unit_id},
                ))

        # Channel-name validity (every channel, every unit).
        if channel_enum:
            for c in channels:
                name_el = doc.find_child_setting(c, "AdcChannelName")
                cname = name_el.attrib.get("value") if name_el is not None else None
                if cname is not None and cname not in channel_enum:
                    diagnostics.append(Diagnostic(
                        severity="blocker",
                        code="adc_channel_not_in_device",
                        module="adc",
                        message=(
                            f"ADC channel '{cname}' (unit {unit_id}) is not in the "
                            f"device channel enum. Use a valid AdcChannelName "
                            f"(S-channels start at S8; there is no S0..S7)."
                        ),
                        details={"unit": unit_id, "channel": cname},
                    ))

        if not threshold_channels:
            continue  # no watchdog usage on this unit -> watchdog rules N/A

        # Watchdog: global API must be enabled.
        if not wdg_api_enabled:
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="adc_watchdog_api_disabled",
                module="adc",
                message=(
                    "An ADC channel enables thresholds but "
                    "AutosarExt/AdcEnableWatchdogApi is false. Set it true "
                    "(Adc.xdm: watchdog must be globally enabled)."
                ),
                details={"unit": unit_id},
            ))

        # Watchdog: the unit's WdgThresholdEnable must be true.
        hw_cfg = hw_configs.get(unit_id) if unit_id is not None else None
        wt = doc.find_child_setting(hw_cfg, "WdgThresholdEnable") if hw_cfg is not None else None
        if hw_cfg is None or wt is None or wt.attrib.get("value", "false").lower() != "true":
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="adc_unit_wdg_threshold_disabled",
                module="adc",
                message=(
                    f"ADC unit {unit_id} has threshold-enabled channels but its "
                    f"AdcHwConfiguration/WdgThresholdEnable is not true (Adc.xdm "
                    f"requires the watchdog ISR be activated for the Hw Unit)."
                ),
                details={"unit": unit_id},
            ))

        control_names = {
            doc.find_child_setting(tc, "Name").attrib.get("value")
            for tc in threshold_controls
            if doc.find_child_setting(tc, "Name") is not None
        }

        for c in threshold_channels:
            cname_el = doc.find_child_setting(c, "AdcChannelName")
            cname = cname_el.attrib.get("value") if cname_el is not None else None
            # AdcThresholdRegister ref must exist, be non-empty, and reference a
            # threshold control on this unit.
            ref_value = None
            for child in c:
                if child.tag.endswith("array") and child.attrib.get("name") == "AdcThresholdRegister":
                    for item in child:
                        if item.tag.endswith("setting") and item.attrib.get("name") == "0":
                            ref_value = item.attrib.get("value")
                    break
            ref_ok = bool(ref_value) and any(
                ref_value.endswith(cn) or (cn and cn in ref_value) for cn in control_names
            )
            if not ref_ok:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_threshold_ref_incomplete",
                    module="adc",
                    message=(
                        f"ADC channel '{cname}' (unit {unit_id}) enables thresholds "
                        f"but its AdcThresholdRegister ref does not point to an "
                        f"AdcThresholdControl entry on the same unit. Add a matching "
                        f"AdcThresholdControl and reference it."
                    ),
                    details={"unit": unit_id, "channel": cname, "ref": ref_value},
                ))

            wdog_el = doc.find_child_setting(c, "AdcWdogNotification")
            wdog = wdog_el.attrib.get("value") if wdog_el is not None else None
            if wdog is None or wdog == "NULL_PTR" or not _C_IDENTIFIER.match(wdog):
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_watchdog_notification_invalid",
                    module="adc",
                    message=(
                        f"ADC channel '{cname}' (unit {unit_id}) enables thresholds "
                        f"but AdcWdogNotification is not a valid C identifier "
                        f"(got {wdog!r}); a watchdog notification is required."
                    ),
                    details={"unit": unit_id, "channel": cname, "notification": wdog},
                ))

    # BCTU FIFO-DMA coherence (RTD-MEX-ADC-004). A BctuResultFifos entry whose
    # BctuFifoDmaEnable=true raises a DMA request that is serviced by an Mcl DMA
    # logic channel (BctuFifoDmaChannelId -> /Mcl/.../dmaLogicChannel_Type), so:
    #   - MclEnableDma must be true (the global Mcl DMA switch) ->
    #     adc_dma_mcl_not_enabled;
    #   - BctuFifoDmaChannelId must hold a non-empty ref (Adc.xdm L5041 INVALID:
    #     not(node:refvalid(.)) and BctuFifoDmaEnable='true') -> adc_dma_refs_incomplete.
    # The companion CtuEnableDmaTransferMode gate (Adc.xdm L4986-4987) is applied
    # by the BCTU FIFO-DMA apply path; this check covers the cross-module Mcl wiring
    # the apply tail performs, mirroring the Uart _check_dma model.
    for fifo in _bctu_result_fifos(doc, adc_cfg):
        dma_el = doc.find_child_setting(fifo, "BctuFifoDmaEnable")
        if dma_el is None or dma_el.attrib.get("value", "false").lower() != "true":
            continue
        name_el = doc.find_child_setting(fifo, "Name")
        fifo_name = name_el.attrib.get("value") if name_el is not None else None
        if not mcl_dma_enabled:
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="adc_dma_mcl_not_enabled",
                module="mcl",
                message=(
                    f"BCTU result FIFO '{fifo_name}' enables FIFO DMA "
                    f"(BctuFifoDmaEnable=true) but MclEnableDma is not true in the "
                    f"Mcl configuration. Set MclEnableDma=true."
                ),
                details={"fifo": fifo_name},
            ))
        dma_ref_populated = False
        for child in fifo:
            if child.tag.endswith("array") and child.attrib.get("name") == "BctuFifoDmaChannelId":
                for item in child:
                    if (
                        item.tag.endswith("setting")
                        and item.attrib.get("value", "").strip()
                    ):
                        dma_ref_populated = True
                break
        if not dma_ref_populated:
            diagnostics.append(Diagnostic(
                severity="blocker",
                code="adc_dma_refs_incomplete",
                module="adc",
                message=(
                    f"BCTU result FIFO '{fifo_name}' enables FIFO DMA but its "
                    f"BctuFifoDmaChannelId reference is empty. Populate it with an "
                    f"Mcl dmaLogicChannel_Type ref (Adc.xdm L5041 INVALID rule)."
                ),
                details={"fifo": fifo_name},
            ))

    # BCTU internal-trigger coherence (Adc.xdm BctuInternalTrigger L4399..). For
    # each BctuInternalTrigger under any BctuHwUnit:
    #   - BctuAdcTargetMask must select a SINGLE bit when BctuTriggerConversionMode
    #     is SINGLE (Adc.xdm L4539-4540: a multi-ADC mask is valid only for LIST;
    #     for a single-conversion trigger BCTU ignores a multi-bit mask) ->
    #     adc_bctu_target_mask_invalid;
    #   - BctuConversionListStartIndex must be < the number of BctuListItems in the
    #     same BctuHwUnit when the mode is LIST (Adc.xdm L4621) ->
    #     adc_bctu_list_start_index_invalid.
    for trig, list_item_count in _bctu_internal_triggers(doc, adc_cfg):
        mode_el = doc.find_child_setting(trig, "BctuTriggerConversionMode")
        mode = mode_el.attrib.get("value") if mode_el is not None else "SINGLE"
        name_el = doc.find_child_setting(trig, "Name")
        trig_name = name_el.attrib.get("value") if name_el is not None else None

        mask_el = doc.find_child_setting(trig, "BctuAdcTargetMask")
        if mask_el is not None and mode == "SINGLE":
            try:
                mask = int(mask_el.attrib.get("value", "1"))
            except ValueError:
                mask = 1
            # A single set bit means mask & (mask - 1) == 0 (and mask != 0).
            if mask == 0 or (mask & (mask - 1)) != 0:
                diagnostics.append(Diagnostic(
                    severity="blocker",
                    code="adc_bctu_target_mask_invalid",
                    module="adc",
                    message=(
                        f"BCTU internal trigger '{trig_name}' is SINGLE conversion "
                        f"mode but BctuAdcTargetMask={mask} selects more than one ADC. "
                        f"A multi-ADC mask is valid only for LIST conversion (Adc.xdm "
                        f"BctuAdcTargetMask INVALID rule); use a single-bit mask."
                    ),
                    details={"trigger": trig_name, "mask": mask, "mode": mode},
                ))

        if mode == "LIST":
            start_el = doc.find_child_setting(trig, "BctuConversionListStartIndex")
            if start_el is not None:
                try:
                    start = int(start_el.attrib.get("value", "0"))
                except ValueError:
                    start = 0
                if list_item_count > 0 and start >= list_item_count:
                    diagnostics.append(Diagnostic(
                        severity="blocker",
                        code="adc_bctu_list_start_index_invalid",
                        module="adc",
                        message=(
                            f"BCTU internal trigger '{trig_name}' uses LIST mode but "
                            f"BctuConversionListStartIndex={start} is not less than the "
                            f"number of BctuListItems ({list_item_count}); the start "
                            f"index must be < the list length (Adc.xdm L4621)."
                        ),
                        details={
                            "trigger": trig_name,
                            "start_index": start,
                            "list_length": list_item_count,
                        },
                    ))


def _bctu_internal_triggers(
    doc: MexDocument, adc_cfg: ET.Element
) -> "list[tuple[ET.Element, int]]":
    """Return every BctuInternalTrigger struct paired with its BctuHwUnit's
    BctuListItems count.

    BctuInternalTrigger and BctuListItems arrays both nest inside the same
    BctuHwUnit struct (a direct child of the AdcConfigSet struct). The list-item
    count is needed to validate BctuConversionListStartIndex (must be < list
    length, Adc.xdm L4621). Returns ``[]`` when there is no BCTU subtree.
    """
    out: "list[tuple[ET.Element, int]]" = []
    for cfgset in adc_cfg.iter():
        if not (cfgset.tag.endswith("struct") and cfgset.attrib.get("name") == "AdcConfigSet"):
            continue
        for bctu_array in cfgset:
            if not (
                bctu_array.tag.endswith("array")
                and bctu_array.attrib.get("name") == "BctuHwUnit"
            ):
                continue
            for hw_unit in bctu_array:
                if not hw_unit.tag.endswith("struct"):
                    continue
                triggers: list[ET.Element] = []
                list_item_count = 0
                for child in hw_unit:
                    if not child.tag.endswith("array"):
                        continue
                    if child.attrib.get("name") == "BctuInternalTrigger":
                        triggers = [c for c in child if c.tag.endswith("struct")]
                    elif child.attrib.get("name") == "BctuListItems":
                        list_item_count = sum(
                            1 for c in child if c.tag.endswith("struct")
                        )
                for trig in triggers:
                    out.append((trig, list_item_count))
    return out


def _bctu_result_fifos(doc: MexDocument, adc_cfg: ET.Element) -> list[ET.Element]:
    """Return every BctuResultFifos struct under the AdcConfigSet's BctuHwUnit.

    BctuResultFifos arrays nest inside each BctuHwUnit struct, which is a direct
    child of the AdcConfigSet struct (a sibling of the AdcHwUnit array).
    """
    out: list[ET.Element] = []
    for fifos_array in adc_cfg.iter():
        if not (
            fifos_array.tag.endswith("array")
            and fifos_array.attrib.get("name") == "BctuResultFifos"
        ):
            continue
        out.extend(c for c in fifos_array if c.tag.endswith("struct"))
    return out


def run_static_checks(
    mex_path: Path,
    doc: MexDocument | None = None,
    *,
    modified_elements: Iterable[ET.Element] | None = None,
    requested_callback: str | None = None,
) -> Result:
    """Run all static checks against a .mex document.

    Returns a Result with status "blocked" when any blocker diagnostic is
    present, otherwise "passed". Never raises for expected validation failures;
    structured diagnostics are returned instead of tracebacks.
    """
    diagnostics: list[Diagnostic] = []
    checks: dict = {}

    _check_xml_and_single_mex(mex_path, checks, diagnostics)

    if doc is None and checks.get("xml_well_formed"):
        doc = MexDocument.load(mex_path)

    if doc is not None and checks.get("xml_well_formed", True):
        _check_enabled_modules(doc, checks, diagnostics)
        _check_dma(doc, diagnostics)
        _check_flexio_refs(doc, diagnostics)
        _check_duplicate_lpuart_hw(doc, diagnostics)
        _check_uart_channel_ids(doc, diagnostics)
        _check_adc(doc, diagnostics)
        _check_quick_selection_conflict(doc, modified_elements or [], diagnostics)
        _check_callback(requested_callback, diagnostics)

    has_blocker = any(d.severity == "blocker" for d in diagnostics)
    status = "blocked" if has_blocker else "passed"
    return Result(
        status=status,
        command="check",
        diagnostics=diagnostics,
        data={"checks": checks},
    )
