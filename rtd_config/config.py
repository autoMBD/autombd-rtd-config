# rtd_config/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeConfig:
    project: Path
    backend: str = "mex"
    family: str = "s32k3"
    device: str = "s32k344"
    package: str = "default"
    rtd_version: str = "7_0_1"
    data_root: Path = Path("data")
    validation_timeout_s: int = 180

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuntimeConfig":
        values = dict(raw)
        values["project"] = Path(values["project"])
        if "data_root" in values:
            values["data_root"] = Path(values["data_root"])
        return cls(**values)
