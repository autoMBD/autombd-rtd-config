# rtd_config/diagnostics.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["blocker", "error", "warning", "info"]
Status = Literal["passed", "failed", "blocked"]


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    module: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "module": self.module,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class Result:
    status: Status
    command: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "command": self.command,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
        payload.update(self.data)
        return payload
