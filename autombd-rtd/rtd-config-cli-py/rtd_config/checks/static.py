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
# Description: Milestone 1 static checks for S32 ConfigTools .mex projects.
# =================================================================================

"""Fast, vendor-free static checks for S32 ConfigTools .mex projects.

These checks run during development testing and as the first stage of runtime
verification after a .mex edit. They never launch a vendor tool. The rules
encode the failure patterns captured in the M1 legacy-skills experience:

- XML well-formedness;
- single .mex detection;
- enabled module list;
- duplicate enabled-instance-name warning;
- quick_selection conflict on planned/applied edits;
- stale FlexIO Uart UartHwChannelRef detection;
- missing Mcl FlexIO logic-channel detection;
- duplicate LPUART hardware channel detection;
- invalid Uart callback (NULL_PTR / non-C-identifier) detection;
- Milestone 1 DMA rejection (never partially configure DMA).
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


def run_static_checks(
    mex_path: Path,
    doc: MexDocument | None = None,
    *,
    modified_elements: Iterable[ET.Element] | None = None,
    requested_callback: str | None = None,
) -> Result:
    """Run all M1 static checks against a .mex document.

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
