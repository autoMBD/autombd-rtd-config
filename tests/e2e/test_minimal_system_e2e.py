# =================================================================================
# The MIT License 
# MIT许可证
# 
# <https://opensource.org/license/mit>
# 
# SPDX short identifier / SPDX 短标识符：MIT 
# 
# Copyright (c) 2026 autoMBD
# 版权所有 (c) 2026 autoMBD
#
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 特此向获得本软件及相关文档（合称"本软件"）副本的任何人免费授予不受限制地利用本软
# 件的许可，包括而不限于：使用、复制、修改、合并、发布、分发、分许可和/或销售本软
# 件副本，并允许本软件的接收者也获得前述许可，但须遵守以下条件：
# 
# The above copyright notice and this permission notice shall be included 
# in all copies or substantial portions of the Software.
# 以上版权声明及本许可声明应包含在本软件的所有副本或主要部分中。
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF 
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
# NONINFRINGEMENT. IN NO EVENT SHALLTHE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN 
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.
# 本软件系"按原样"提供，不包含任何形式的明示或默示保证，包括但不限于适销性、特定
# 目的适用性及不侵权的保证。在任何情况下，无论是在合同、侵权或其他案件中，作者或版
# 权持有人均不对因本软件、或因本软件的使用或其他利用而引起的、引发的或与之相关的任
# 何权利主张、损害赔偿或其他责任承担责任。
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        test_minimal_system_e2e.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: E2E tests for the minimal-system mandatory minimum matrix.
# =================================================================================

"""Minimal-system mandatory minimum E2E matrix.

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
    # ConfigTools exit 0 alone is not sufficient; the pass gate also requires no
    # SEVERE [TOOL] resource-configuration problems.
    assert payload["validation"]["exit_code"] == 0, payload
    assert payload["validation"]["passed"] is True, payload
    assert payload["validation"]["severe_problems"] == [], payload


def test_inspect_uart_fixture(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _cli("inspect", "--project", str(project), "--json")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["backend"] == "s32-mex"
    # The inspect user prompt explicitly asks for chip package (封装); inspect
    # must surface the package dimension alongside device/RTD version.
    assert payload["package"] == "mapbga257"
    assert payload["device"] == "S32K344"
    assert "Uart" in payload["modules"]


# LPUART polling was removed: RTD 7.0.1 has no polling async-method value,
# so only interrupt mode is supported (see test-strategy doc).


def test_lpuart_interrupt(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "LPUART_0", "interrupt", 115200, "PTA15", "PTA16")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    _maybe_validate(project)


# FlexIO polling was removed for the same reason as LPUART polling:
# polling is not an RTD 7.0.1 .mex async-method value.


def test_flexio_interrupt(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "FLEXIO_0", "interrupt", 115200, "PTB0", "PTB1")
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["changed_modules"] == []
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    _maybe_validate(project)


def test_pin_options(tmp_path):
    result = _cli(
        "pin-options",
        "--vendor", "NXP", "--backend", "s32-mex", "--family", "S32K3",
        "--device", "S32K344", "--package", "mapbga257",
        "--rtd-release", "7.0.1", "--schema", "19",
        "--peripheral", "LPUART_0",
        "--json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert any(item["peripheral"] == "LPUART_0" for item in payload["options"])


def test_e2e_lpuart_stack(tmp_path):
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


def test_e2e_flexio_stack(tmp_path):
    project = copy_uart_fixture(tmp_path)
    configure = _configure(project, "FLEXIO_0", "interrupt", 115200, "PTB0", "PTB1")
    configure_payload = json.loads(configure.stdout)
    assert configure.returncode == 0
    assert configure_payload["status"] == "passed"
    assert configure_payload["changed_modules"] == []

    check = _cli("check", "--project", str(project), "--json")
    check_payload = json.loads(check.stdout)
    assert check.returncode == 0
    assert check_payload["status"] == "passed"
    assert check_payload["checks"]["xml_well_formed"] is True

    _maybe_validate(project)
