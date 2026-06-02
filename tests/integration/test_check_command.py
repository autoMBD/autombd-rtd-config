# tests/integration/test_check_command.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_check_reports_well_formed_fixture(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "check", "--project", str(project), "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["checks"]["xml_well_formed"] is True
