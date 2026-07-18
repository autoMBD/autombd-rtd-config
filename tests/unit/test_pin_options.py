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
# File:        test_pin_options.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Unit tests for the pin-options query.
# =================================================================================

import json
import subprocess
import sys


def _run_pin_options(peripheral, package="mapbga257", *extra):
    return subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "pin-options",
            "--vendor", "NXP",
            "--backend", "s32-mex",
            "--family", "S32K3",
            "--device", "S32K344",
            "--package", package,
            "--rtd-release", "7.0.1",
            "--schema", "19",
            "--peripheral", peripheral,
            *extra,
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_pin_options_returns_runtime_data_without_vendor_launch():
    result = _run_pin_options("LPUART_0")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["command"] == "pin-options"
    # Peripheral must be presented in user-facing underscore form ("LPUART_0"),
    # even though the asset stores "LPUART0" internally.
    assert any(item["peripheral"] == "LPUART_0" for item in payload["options"])


def test_pin_options_lpuart0_returns_real_pins_not_stub():
    """LPUART_0 pin options must list real IOMUX-verified pins, not the old stub.

    The stub incorrectly listed PTA15/PTA16.  The correct LPUART0 TX/RX are on
    PTA27/PTA28 (verified from S32K344_IO Signal Table rows 329, 345).
    """
    result = _run_pin_options("LPUART_0")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    options = payload["options"]

    # Collect all pins returned
    pins = {item["pin"] for item in options}

    # The wrong stub pins must NOT appear as LPUART_0 options
    assert "PTA15" not in pins, (
        "PTA15 returned for LPUART_0 — this was the stub value; "
        "PTA15 has no LPUART0 function on S32K344."
    )
    assert "PTA16" not in pins, (
        "PTA16 returned for LPUART_0 — this was the stub value; "
        "PTA16 has no LPUART0 function on S32K344."
    )

    # The verified correct TX/RX pins must appear
    assert "PTA27" in pins, (
        "PTA27 not in LPUART_0 options — expected LPUART0_TX on PTA27 "
        "(verified from S32K344 IOMUX workbook row 329)."
    )
    assert "PTA28" in pins, (
        "PTA28 not in LPUART_0 options — expected LPUART0_RX on PTA28 "
        "(verified from S32K344 IOMUX workbook row 345)."
    )


def test_pin_options_lpuart0_has_tx_and_rx():
    """LPUART_0 options must include at least one TX and one RX signal."""
    result = _run_pin_options("LPUART_0")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    options = payload["options"]

    has_tx = any(item.get("signal") == "TX" for item in options)
    has_rx = any(item.get("signal") == "RX" for item in options)
    assert has_tx, "No TX signal option returned for LPUART_0"
    assert has_rx, "No RX signal option returned for LPUART_0"


def test_pin_options_only_returns_active_package_fields():
    payload = json.loads(_run_pin_options("LPUART_0").stdout)
    assert payload["options"]
    assert all(item.get("package_pin") for item in payload["options"])
    assert all("pin_mapbga257" not in item for item in payload["options"])
    assert all(not any(value in (None, "") for value in item.values()) for item in payload["options"])


def test_wrong_and_unproven_packages_are_unsupported():
    for package in ("hdqfp172", "lqfp100", "unknown"):
        result = _run_pin_options("LPUART_0", package)
        assert result.returncode == 1
        assert json.loads(result.stdout)["diagnostics"][0]["code"] == "asset_bundle_unsupported"


def test_projectless_pin_options_requires_full_selector():
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "pin-options", "--peripheral", "LPUART_0", "--json"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["diagnostics"][0]["code"] == "invalid_arguments"
