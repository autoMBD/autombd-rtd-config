# rtd_config/modules/uart.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange
from rtd_config.modules.mcu import McuProvider
from rtd_config.modules.port import PortProvider
from rtd_config.modules.platform import PlatformProvider
from rtd_config.modules.mcl import MclProvider


def is_flexio(hw: str) -> bool:
    """Return True when the requested hardware uses the FlexIO Uart path."""
    return hw.upper().startswith("FLEXIO")


class UartProvider:
    """User-facing Uart driver path (LPUART and FlexIO, polling/interrupt).

    Uart owns channel settings and Uart-side references. It does not edit other
    modules directly; instead it declares explicit dependency PlannedChange
    records owned by their respective providers:

    - Mcu owns the clock reference (always required);
    - Port owns TX/RX pin routing (when pins are requested);
    - Platform owns the IRQ entry (interrupt mode only);
    - Mcl owns the FlexIO logic channel (FlexIO path only).

    DMA is outside Milestone 1 and is rejected/deferred by the static checks.
    """

    name = "uart"

    def plan(self, intent: Intent) -> Plan:
        payload = intent.payload
        hw = payload.get("hw", "")
        mode = payload.get("mode", "polling")

        # Uart-owned change: the channel settings themselves.
        changes = [
            PlannedChange(
                module="uart",
                owner="uart",
                path="/Uart/Uart/UartGlobalConfig/UartChannel",
                description=f"Configure {hw} channel in {mode} mode",
            )
        ]

        # Mcu clock reference is always required for a working Uart channel.
        changes.append(McuProvider().clock_dependency(hw))

        # Port pin routing dependency, when the consumer requested pins.
        if payload.get("pins"):
            changes.append(PortProvider().pin_dependency(payload["pins"]))

        # Platform IRQ dependency in interrupt mode only.
        if mode == "interrupt":
            changes.append(PlatformProvider().irq_dependency(hw))

        # Mcl FlexIO logic-channel dependency on the FlexIO path only.
        if is_flexio(hw):
            changes.append(MclProvider().flexio_dependency(hw))

        return Plan(changes)
