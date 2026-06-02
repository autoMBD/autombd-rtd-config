# tests/unit/test_pin_options.py
import json
import subprocess
import sys


def test_pin_options_returns_runtime_data_without_vendor_launch():
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "pin-options",
            "--device", "s32k344",
            "--package", "default",
            "--peripheral", "LPUART_0",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["command"] == "pin-options"
    assert any(item["peripheral"] == "LPUART_0" for item in payload["options"])
