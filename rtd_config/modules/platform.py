# rtd_config/modules/platform.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class PlatformProvider:
    """Owns Platform interrupt-controller configuration.

    Uart interrupt mode must create/update Platform IRQ entries only through
    this provider. The plan never guesses interrupt priority, handler, enable
    state, or partition/core target when missing from the request.
    """

    name = "platform"

    def plan(self, intent: Intent) -> Plan:
        return Plan([self.irq_dependency(intent.payload.get("hw", ""))])

    def irq_dependency(self, hw: str) -> PlannedChange:
        """Return the Platform-owned IRQ dependency a consumer requires."""
        return PlannedChange(
            module="platform",
            owner="platform",
            path="/Platform/Platform/IntCtrlConfig",
            description=f"Configure interrupt entry for {hw}",
        )
