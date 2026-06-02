# tests/fixtures.py
from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UART_FIXTURE = REPO_ROOT / "fixtures" / "mex" / "s32k3" / "s32k344" / "uart" / "projects" / "Uart_Example_S32K344"


def copy_uart_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "Uart_Example_S32K344"
    shutil.copytree(UART_FIXTURE, target)
    return target
