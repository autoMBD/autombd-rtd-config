# tests/integration/test_inspect_uart_fixture.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_inspect_uart_fixture_reports_modules_and_backend(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "inspect", "--project", str(project), "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["backend"] == "mex"
    assert payload["family"] == "s32k3"
    assert payload["device"] == "s32k344"
    assert "Uart" in payload["modules"]
