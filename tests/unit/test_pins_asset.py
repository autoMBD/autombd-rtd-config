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
# File:        test_pins_asset.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Tests for the complete S32K344 pin-mux asset (pins.json).
#              Asserts completeness and VERIFIED oracle records from the IOMUX
#              source workbook. Never asserts against stub values.
# =================================================================================

import json
from pathlib import Path

import pytest

# Location of the committed runtime asset
_ASSET_PATH = (
    Path(__file__).resolve().parents[2]
    / "autombd-rtd"
    / "assets"
    / "nxp"
    / "s32k3"
    / "port"
    / "pins.json"
)


@pytest.fixture(scope="module")
def pins_data():
    data = json.loads(_ASSET_PATH.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def signals(pins_data):
    return pins_data["signals"]


# ---------------------------------------------------------------------------
# Completeness checks — proves this is NOT a stub
# ---------------------------------------------------------------------------

def test_asset_top_level_metadata(pins_data):
    assert pins_data["family"] == "s32k3"
    assert pins_data["device"] == "s32k344"
    assert pins_data["package"] == "default"


def test_asset_is_complete_not_stub(signals):
    """The complete asset must have more than 2000 signal records (not a stub)."""
    assert len(signals) > 2000, (
        f"pins.json has only {len(signals)} records — looks like a stub. "
        "Expected >2000 records built from the IOMUX workbook."
    )


def test_asset_has_all_three_directions(signals):
    directions = {s["direction"] for s in signals}
    assert "output" in directions
    assert "input" in directions
    assert "gpio" in directions


# ---------------------------------------------------------------------------
# Oracle record: LPUART0_TX on PTA27
# Verified from S32K344_IO Signal Table row 329 + Pinout sheet
# ---------------------------------------------------------------------------

def test_oracle_lpuart0_tx_pta27(signals):
    """LPUART0 TX on PTA27: mscr=27, mux_sss='00000100', direction=output."""
    matches = [
        s for s in signals
        if s["peripheral"] == "LPUART0"
        and s["function"] == "LPUART0_TX"
        and s["pin"] == "PTA27"
    ]
    assert len(matches) >= 1, "Expected LPUART0_TX on PTA27 in signals"
    rec = matches[0]
    assert rec["mscr"] == 27
    assert rec["mux_sss"] == "00000100"
    assert rec["direction"] == "output"
    assert rec["pin_hdqfp172"] == "28"
    assert rec["pin_mapbga257"] == "M2"
    assert rec["imcr"] is None
    assert rec["imcr_sss"] is None


# ---------------------------------------------------------------------------
# Oracle record: LPUART0_RX on PTA28
# Verified from S32K344_IO Signal Table row 345 + Pinout sheet
# ---------------------------------------------------------------------------

def test_oracle_lpuart0_rx_pta28(signals):
    """LPUART0 RX on PTA28: mscr=28, direction=input, imcr=699, imcr_sss='00000100'."""
    matches = [
        s for s in signals
        if s["peripheral"] == "LPUART0"
        and s["function"] == "LPUART0_RX"
        and s["pin"] == "PTA28"
    ]
    assert len(matches) >= 1, "Expected LPUART0_RX on PTA28 in signals"
    rec = matches[0]
    assert rec["mscr"] == 28
    assert rec["direction"] == "input"
    assert rec["imcr"] == 699
    assert rec["imcr_sss"] == "00000100"


# ---------------------------------------------------------------------------
# Oracle record: GPIO[4] on PTA4
# Verified from S32K344_IO Signal Table row 68
# ---------------------------------------------------------------------------

def test_oracle_gpio_pta4(signals):
    """GPIO[4] on PTA4: mscr=4, direction=gpio."""
    matches = [
        s for s in signals
        if s["pin"] == "PTA4"
        and s["direction"] == "gpio"
    ]
    assert len(matches) >= 1, "Expected GPIO gpio record on PTA4"
    rec = matches[0]
    assert rec["mscr"] == 4
    assert rec["direction"] == "gpio"


# ---------------------------------------------------------------------------
# Cross-check: LPUART3 TX on PTD2 and RX on PTD3 (fixture pins)
# Verified from S32K344_IO Signal Table rows 1195, 1220
# ---------------------------------------------------------------------------

def test_oracle_lpuart3_tx_ptd2(signals):
    """LPUART3_TX on PTD2: mscr=98, direction=output."""
    matches = [
        s for s in signals
        if s["peripheral"] == "LPUART3"
        and s["function"] == "LPUART3_TX"
        and s["pin"] == "PTD2"
    ]
    assert len(matches) >= 1, "Expected LPUART3_TX on PTD2"
    assert matches[0]["mscr"] == 98
    assert matches[0]["direction"] == "output"


def test_oracle_lpuart3_rx_ptd3(signals):
    """LPUART3_RX on PTD3: mscr=99, direction=input."""
    matches = [
        s for s in signals
        if s["peripheral"] == "LPUART3"
        and s["function"] == "LPUART3_RX"
        and s["pin"] == "PTD3"
    ]
    assert len(matches) >= 1, "Expected LPUART3_RX on PTD3"
    assert matches[0]["mscr"] == 99
    assert matches[0]["direction"] == "input"


# ---------------------------------------------------------------------------
# Confirm stub pins PTA15/PTA16 do NOT map to LPUART0
# The stub was wrong — this is the regression guard.
# ---------------------------------------------------------------------------

def test_stub_pins_not_lpuart0(signals):
    """PTA15 and PTA16 must NOT appear as LPUART0 TX/RX (stub was wrong)."""
    bad = [
        s for s in signals
        if s["peripheral"] == "LPUART0"
        and s["pin"] in ("PTA15", "PTA16")
        and s["function"] in ("LPUART0_TX", "LPUART0_RX")
    ]
    assert bad == [], (
        f"Found wrong stub pins for LPUART0: {bad}. "
        "PTA15/PTA16 have no LPUART0 TX/RX function on S32K344."
    )


# ---------------------------------------------------------------------------
# Schema check: all required fields present on every record
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {
    "peripheral", "signal", "function", "mux", "pin",
    "mscr", "mux_sss", "direction", "imcr", "imcr_sss",
    "pin_hdqfp172", "pin_mapbga257",
}


def test_all_records_have_required_fields(signals):
    missing = []
    for i, s in enumerate(signals):
        for field in _REQUIRED_FIELDS:
            if field not in s:
                missing.append((i, s.get("pin"), s.get("function"), field))
    assert missing == [], f"Records missing required fields: {missing[:10]}"
