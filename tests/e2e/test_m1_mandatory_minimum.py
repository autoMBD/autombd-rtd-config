# tests/e2e/test_m1_mandatory_minimum.py
"""Milestone 1 mandatory minimum test matrix (RTD-M1-MIN-001 .. 008).

Each test drives the public CLI and asserts the JSON contract. Non-vendor
checks (status, changed modules, static check) always run. Backend S32DS
headless validation is asserted only when RTD_CONFIG_RUN_S32DS_VALIDATION is
set, so the matrix passes without the vendor environment while still exercising
the vendor path when it is available.
"""
import json
import os
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


VENDOR_ENV = "RTD_CONFIG_RUN_S32DS_VALIDATION"


def _cli(*args, timeout=180):
    return subprocess.run(
        [sys.executable, "-m", "rtd_config", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def _configure(project, hw, mode, baud, tx, rx, *extra):
    return _cli(
        "uart", "set",
        "--project", str(project),
        "--hw", hw,
        "--mode", mode,
        "--baud", str(baud),
        "--tx", tx,
        "--rx", rx,
        "--configure",
        "--json",
        *extra,
    )


def _maybe_validate(project):
    """Run vendor validation only when the environment flag is set."""
    if not os.environ.get(VENDOR_ENV):
        return
    result = _cli("validate", "--project", str(project), "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload
    assert payload["status"] == "passed", payload
    assert payload["validation"]["exit_code"] == 0, payload


def test_rtd_m1_min_001_inspect_uart_fixture(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _cli("inspect", "--project", str(project), "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["backend"] == "mex"
    # The MIN-001 user prompt explicitly asks for chip package (封装); inspect
    # must surface the package dimension alongside device/RTD version.
    assert payload["package"] == "default"
    assert payload["device"] == "s32k344"
    assert "Uart" in payload["modules"]


def test_rtd_m1_min_002_lpuart_polling(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "LPUART_0", "polling", 115200, "PTA15", "PTA16")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    _maybe_validate(project)


def test_rtd_m1_min_003_lpuart_interrupt(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "LPUART_0", "interrupt", 115200, "PTA15", "PTA16")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    _maybe_validate(project)


def test_rtd_m1_min_004_flexio_polling(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "FLEXIO_0", "polling", 115200, "PTB0", "PTB1")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    _maybe_validate(project)


def test_rtd_m1_min_005_flexio_interrupt(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "FLEXIO_0", "interrupt", 115200, "PTB0", "PTB1")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    _maybe_validate(project)


def test_rtd_m1_min_006_pin_options(tmp_path):
    result = _cli(
        "pin-options",
        "--device", "s32k344",
        "--package", "default",
        "--peripheral", "LPUART_0",
        "--json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert any(item["peripheral"] == "LPUART_0" for item in payload["options"])


def test_rtd_m1_min_007_e2e_lpuart_stack(tmp_path):
    project = copy_uart_fixture(tmp_path)
    configure = _configure(project, "LPUART_0", "interrupt", 115200, "PTA15", "PTA16")
    configure_payload = json.loads(configure.stdout)
    assert configure.returncode == 0
    assert configure_payload["status"] == "passed"
    assert "uart" in configure_payload["changed_modules"]

    check = _cli("check", "--project", str(project), "--json")
    check_payload = json.loads(check.stdout)
    assert check.returncode == 0
    assert check_payload["status"] == "passed"
    assert check_payload["checks"]["xml_well_formed"] is True

    _maybe_validate(project)


def test_rtd_m1_min_008_e2e_flexio_stack(tmp_path):
    project = copy_uart_fixture(tmp_path)
    configure = _configure(project, "FLEXIO_0", "interrupt", 115200, "PTB0", "PTB1")
    configure_payload = json.loads(configure.stdout)
    assert configure.returncode == 0
    assert configure_payload["status"] == "passed"
    assert "uart" in configure_payload["changed_modules"]

    check = _cli("check", "--project", str(project), "--json")
    check_payload = json.loads(check.stdout)
    assert check.returncode == 0
    assert check_payload["status"] == "passed"
    assert check_payload["checks"]["xml_well_formed"] is True

    _maybe_validate(project)
