# tests/unit/test_validation_command.py
from pathlib import Path

from rtd_config.backends.s32_mex.validation import build_validation_command


def test_build_validation_command_is_headless():
    command = build_validation_command(
        s32ds_root=Path("C:/NXP/S32DS.3.6.7"),
        project=Path("C:/tmp/Uart_Example_S32K344"),
    )
    joined = " ".join(command)
    assert "S32DS" in joined or "eclipse" in joined.lower()
    assert "-nosplash" in command
    assert any("application" in item.lower() for item in command)
