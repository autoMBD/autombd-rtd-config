# rtd_config/resources/pins.py
from __future__ import annotations

from pathlib import Path
from .runtime import load_json


def pin_options(data_root: Path, device: str, package: str, peripheral: str) -> list[dict]:
    path = data_root / "s32k" / "families" / "s32k3" / "devices" / device / "packages" / package / "pins.json"
    data = load_json(path)
    return [item for item in data["signals"] if item["peripheral"] == peripheral]
