# rtd_config/plan.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlannedChange:
    module: str
    owner: str
    path: str
    description: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass(frozen=True)
class Plan:
    changes: list[PlannedChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"changes": [change.to_dict() for change in self.changes]}
