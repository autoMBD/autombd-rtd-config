# rtd_config/backends/base.py
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class BackendDocument(Protocol):
    path: Path

    def mark_modified(self, element: object) -> None:
        ...

    def write(self, path: Path | None = None) -> None:
        ...
