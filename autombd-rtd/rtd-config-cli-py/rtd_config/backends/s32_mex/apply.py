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
