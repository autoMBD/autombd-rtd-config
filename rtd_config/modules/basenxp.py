# rtd_config/modules/basenxp.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class BaseNxpProvider:
    """Owns BaseNXP/OsIf shared infrastructure.

    OsIf timer choices affect Uart timeout behaviour. For Milestone 1 the
    provider only preserves/asserts the existing BaseNXP/OsIf region needed by
    the complete fixture; it does not invent timer or DET behaviour.
    """

    name = "basenxp"

    def plan(self, intent: Intent) -> Plan:
        return Plan([
            PlannedChange(
                module="basenxp",
                owner="basenxp",
                path="/BaseNXP/BaseNXP/OsIfGeneral",
                description="Preserve OsIf configuration used by Uart timeout",
            )
        ])
