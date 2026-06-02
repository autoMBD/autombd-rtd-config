# rtd_config/modules/mcl.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class MclProvider:
    """Owns Mcl common resources (FlexIO common + FlexIO logic channels).

    For Milestone 1, FlexIO common resources are owned by Mcl and consumed by
    Uart. MclEnableFlexioCommon must match real FlexIO common/channel entries.
    DMA stays deferred. When Mcl content changes, the highest-risk lesson is to
    strip a stale quick_selection from <config_set name="Mcl"> so ConfigTools
    does not revert the Mcl tree and misreport a Uart out-of-range error.
    """

    name = "mcl"

    def plan(self, intent: Intent) -> Plan:
        return Plan([self.flexio_dependency(intent.payload.get("hw", ""))])

    def flexio_dependency(self, hw: str) -> PlannedChange:
        """Return the Mcl-owned FlexIO logic-channel dependency Uart requires."""
        return PlannedChange(
            module="mcl",
            owner="mcl",
            path="/Mcl/Mcl/MclConfig/FlexioCommon_0/FlexioMclLogicChannels",
            description=f"Ensure FlexIO logic channel for {hw}",
        )
