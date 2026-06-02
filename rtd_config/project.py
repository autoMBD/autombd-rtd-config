# rtd_config/project.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    root: Path
    backend: str
    mex_file: Path
