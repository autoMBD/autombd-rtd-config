# rtd_config/intent.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Intent:
    module: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Intent":
        return cls(module=raw["module"], action=raw["action"], payload=dict(raw.get("payload", {})))
