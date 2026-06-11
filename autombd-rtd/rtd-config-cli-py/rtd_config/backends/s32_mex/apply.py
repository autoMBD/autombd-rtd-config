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

import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.diagnostics import Diagnostic
from rtd_config.intent import Intent


# BaseNXP OsIf asset path (committed, versioned; never read .xdm at runtime).
_BASENXP_ASSET = (
    Path(__file__).resolve().parents[4]
    / "assets" / "nxp" / "s32k3" / "basenxp" / "osif.json"
)


# Uart "asynchronous method" enum. RTD 7.0.1 ConfigTools models this field with
# exactly two values per IP -- INTERRUPTS or DMA -- and has NO polling value
# (verified against Uart.xdm and the s32k344 .epd: a "USING_POLLING" enum does
# not exist; ConfigTools rejects it as "value not available"). Milestone 1
# supports interrupt (IRQ); DMA is out of M1 scope. "Polling/blocking" is an
# application-level driver-call pattern, not a .mex async-method value.
_LPUART_METHOD = {
    "interrupt": "LPUART_UART_IP_USING_INTERRUPTS",
}
_FLEXIO_METHOD = {
    "interrupt": "FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS",
}


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
    """Apply an owned Uart channel edit to the loaded document.

    Returns an ApplyResult. On any unsafe/unfound condition it returns a blocker
    Diagnostic instead of raising, so the caller can emit a structured Result.
    """
    payload = intent.payload
    hw = payload.get("hw", "")
    mode = payload.get("mode", "interrupt")
    baud = payload.get("baud")
    want_flexio = _is_flexio_request(hw)

    result = ApplyResult()

    # RTD 7.0.1 has no polling async-method value; M1 supports interrupt only
    # (DMA is out of scope). Reject any other mode with an actionable blocker
    # rather than writing an enum ConfigTools marks "value not available".
    method_map = _FLEXIO_METHOD if want_flexio else _LPUART_METHOD
    if mode not in method_map:
        result.diagnostics.append(Diagnostic(
            severity="blocker",
            code="unsupported_uart_mode",
            module="uart",
            message=(
                f"Uart mode '{mode}' is not supported in Milestone 1. RTD 7.0.1 "
                "models the Uart asynchronous method as interrupt (IRQ) or DMA "
                "only -- there is no polling value -- and DMA is out of M1 scope. "
                "Use mode 'interrupt'."
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

    if method_setting is not None and method_value is not None:
        method_setting.set("value", method_value)
    if baud_value is not None:
        baud_setting = doc.find_child_setting(container, "DesireBaudrate")
        if baud_setting is not None:
            baud_setting.set("value", baud_value)

    # Mark the modified channel so any stale quick_selection on the nearest
    # carrying ancestor is removed before the document is written.
    doc.mark_modified(channel)
    carrier = doc.find_nearest_quick_selection_ancestor(channel)
    if carrier is not None:
        doc.mark_modified(carrier)

    result.changed_modules.append("uart")
    result.modified_elements.append(channel)
    return result


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


def _build_counter_array_bytes(indent: int, line_ending: bytes) -> bytes:
    """Build the populated OsIfCounterConfig array block as raw bytes.

    The returned bytes replace the self-closed ``<array name="OsIfCounterConfig"/>``
    tag verbatim in the raw file. Because ``replace_element_region`` splices
    starting exactly at the ``<`` character, the leading ``indent`` spaces are
    already present in the raw before the splice point and must NOT be repeated
    in the first line. Inner lines do carry their full indentation.

    Values are grounded in the BaseNXP osif.json asset:
    - counter Name: OsIfCounterConfig_0
    - OsIfSystemTimerClockFreq default: 48000000
    - OsIfSystemTimerClockRef: empty array (no core-clock ref in this project)
    - Children order: Name, OsIfCounterEcucPartitionRef, OsIfSystemTimerClockRef,
      OsIfSystemTimerClockFreq, OsIfOsCounterRef
    """
    le = line_ending.decode("latin-1")
    sp1 = " " * (indent + 3)  # 30 spaces for <struct>
    sp2 = " " * (indent + 6)  # 33 spaces for children
    sp = " " * indent          # 27 spaces for closing </array>

    # First line: no leading spaces (they come from raw before src.start)
    lines = [
        '<array name="OsIfCounterConfig">',
        f'{sp1}<struct name="0">',
        f'{sp2}<setting name="Name" value="OsIfCounterConfig_0"/>',
        f'{sp2}<array name="OsIfCounterEcucPartitionRef"/>',
        f'{sp2}<array name="OsIfSystemTimerClockRef"/>',
        f'{sp2}<setting name="OsIfSystemTimerClockFreq" value="48000000"/>',
        f'{sp2}<array name="OsIfOsCounterRef"/>',
        f'{sp1}</struct>',
        f'{sp}</array>',
    ]
    return le.join(lines).encode("utf-8")


def apply_basenxp_set(doc: MexDocument, intent: Intent) -> ApplyResult:
    """Apply owned BaseNXP/OsIf edits: enable system timer and insert one counter.

    Edits are grounded in the BaseNXP osif.json asset (derived from BaseNXP.xdm).
    Two changes are made:
    1. Set OsIfUseSystemTimer from false -> true (attribute edit on existing element).
    2. If OsIfCounterConfig is an empty self-closed array, replace it with a
       populated array containing exactly one counter struct (element insertion via
       replace_element_region).

    Idempotent: if a counter already exists, a second counter is NOT added.
    Returns a blocker Diagnostic if the BaseNXP config set is not found.
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
            # Self-closed empty array -> replace with populated version.
            line_ending = _detect_line_ending(doc._raw)
            new_bytes = _build_counter_array_bytes(indent=27, line_ending=line_ending)
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
