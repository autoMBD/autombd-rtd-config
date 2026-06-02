# tests/e2e/test_s32ds_validation.py
import json
import os
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_validate_uart_fixture_headless(tmp_path):
    if not os.environ.get("RTD_CONFIG_RUN_S32DS_VALIDATION"):
        return
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "validate", "--project", str(project), "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["validation"]["exit_code"] == 0
