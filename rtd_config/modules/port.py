# rtd_config/modules/port.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class PortProvider:
    """Generic SIUL2 pin-mux / electrical configuration service.

    Port must stay generic and not be hardwired to Uart. Consumer modules
    request TX/RX pins; Port owns the actual mux and electrical edits and
    preserves UnTouchedPortPin / UntouchedIMCR protection.
    """

    name = "port"

    def plan(self, intent: Intent) -> Plan:
        pins = intent.payload.get("pins") or {}
        return Plan([self.pin_dependency(pins)])

    def pin_dependency(self, pins: dict) -> PlannedChange:
        """Return the Port-owned pin-mux dependency a consumer requires."""
        tx = pins.get("tx")
        rx = pins.get("rx")
        return PlannedChange(
            module="port",
            owner="port",
            path="/Port/Port/PortConfigSet",
            description=f"Configure pin mux TX={tx} RX={rx}",
        )
