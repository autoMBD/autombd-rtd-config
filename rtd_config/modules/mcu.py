# rtd_config/modules/mcu.py
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
        return Plan([
            PlannedChange(
                module="mcu",
                owner="mcu",
                path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0",
                description="Ensure Uart peripheral clock reference is present",
            )
        ])

    def clock_dependency(self, hw: str) -> PlannedChange:
        """Return the Mcu-owned clock dependency a consumer (Uart) requires."""
        return PlannedChange(
            module="mcu",
            owner="mcu",
            path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0",
            description=f"Ensure clock reference for {hw}",
        )
