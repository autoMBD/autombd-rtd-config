# rtd_config/modules/base.py
from __future__ import annotations

from typing import Protocol
from rtd_config.intent import Intent
from rtd_config.plan import Plan


class ModuleProvider(Protocol):
    name: str

    def plan(self, intent: Intent) -> Plan:
        ...
