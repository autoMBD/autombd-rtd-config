# tests/integration/test_plan_command.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_uart_shortcut_normalizes_to_plan(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "uart", "set",
            "--project", str(project),
            "--hw", "LPUART_0",
            "--mode", "polling",
            "--baud", "115200",
            "--tx", "PTA15",
            "--rx", "PTA16",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["normalized_intent"]["module"] == "uart"
    assert any(change["owner"] == "uart" for change in payload["plan"]["changes"])
