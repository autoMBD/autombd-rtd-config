# tests/unit/test_cli_smoke.py
import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "rtd_config", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_cli_version_returns_json():
    result = run_cli("--version", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["command"] == "version"
    assert payload["tool"] == "RTD CfgFile CLI"
