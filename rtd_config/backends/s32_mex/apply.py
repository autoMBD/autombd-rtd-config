# rtd_config/backends/s32_mex/apply.py
"""Localized, owned edits to an S32 ConfigTools .mex Uart configuration.

Milestone 1 only edits EXISTING module instances; it never creates missing
modules or a .mex from scratch (reserved for M2). The Uart provider owns the
channel settings; cross-module concerns (Mcu clock, Port pins, Platform IRQ,
Mcl FlexIO) are declared as dependencies in the plan, not edited here.

The edit is narrow: it locates the existing Uart channel that matches the
requested hardware path and updates its owned fields in place, then marks the
modified element so any stale quick_selection on the nearest carrying ancestor
is removed (the highest-risk lesson from the legacy-skills experience).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.diagnostics import Diagnostic
from rtd_config.intent import Intent


# Mode -> driver-method enum, following the RTD 7.0.1 LPUART/FlexIO naming.
_LPUART_METHOD = {
    "polling": "LPUART_UART_IP_USING_POLLING",
    "interrupt": "LPUART_UART_IP_USING_INTERRUPTS",
}
_FLEXIO_METHOD = {
    "polling": "FLEXIO_UART_IP_DRIVER_TYPE_POLLING",
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
    mode = payload.get("mode", "polling")
    baud = payload.get("baud")
    want_flexio = _is_flexio_request(hw)

    result = ApplyResult()

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
