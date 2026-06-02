# rtd_config/backends/s32_mex/locate.py
from __future__ import annotations

from pathlib import Path


def find_single_mex(project: Path) -> Path:
    matches = sorted(project.glob("*.mex"))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one .mex in {project}, found {len(matches)}")
    return matches[0]
