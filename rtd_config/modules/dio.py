# rtd_config/modules/dio.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class DioProvider:
    """Owns symbolic digital-I/O IDs (ports, channels, channel groups).

    Dio does not configure pin mux, direction, pull, or default output level;
    those are Port-owned. If a requested Dio channel targets a board pin, the
    plan must add a Port-owned GPIO dependency. This is a plan-only provider in
    Milestone 1 (the Uart fixture contains no Dio instance).
    """

    name = "dio"

    def plan(self, intent: Intent) -> Plan:
        changes = [
            PlannedChange(
                module="dio",
                owner="dio",
                path="/Dio/Dio/DioConfig",
                description="Configure Dio channel symbol",
            )
        ]
        if intent.payload.get("pin"):
            changes.append(
                PlannedChange(
                    module="port",
                    owner="port",
                    path="/Port/Port/PortConfigSet",
                    description="Configure GPIO pad for Dio channel",
                )
            )
        return Plan(changes)
