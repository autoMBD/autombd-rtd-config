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
# File:        test_mcu_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-12
# Version:     0.1.0
# Description: Deterministic tests for apply_mcu_set (RTD-MEX-MCU-001):
#              160/80/40 PLL/divider recipe + all-clocks McuClockReferencePoint.
#              Structure-only gate (clock-math correctness is the vendor gate job).
# =================================================================================

"""Deterministic unit tests for apply_mcu_set (RTD-MEX-MCU-001).

Fixture: Uart_Example_S32K344/Uart_Example.mex (FXOSC=16MHz, FIRC-based 48MHz).
Intent:  core_clk=160, aips_plat_clk=80, aips_slow_clk=40, add_all_clock_reference_points=True.

The tests verify STRUCTURAL edits only. Clock-math correctness (do these inputs
actually yield 160/80/40 MHz?) is the Tester's S32DS vendor-gate job.

Expected edits grounded in Explorer-verified fixture + Mcu.xdm:

A) clock_settings section:
   - CORE_PLL_PD = Power_up    (inserted, was absent)
   - CORE_PLLODIV_0_DE = Enabled  (inserted, was absent)
   - CORE_PLLODIV_1_DE = Enabled  (inserted, was absent)
   - PLLunderMcuControl changed from "Disabled" to "Enabled"
   - MC_CGM_MUX_0.sel = PHI0   (inserted, was absent)
   - MC_CGM_MUX_0_DIV1.scale = 2  (changed from 1)
   - MC_CGM_MUX_0_DIV2.scale = 4  (changed from 2)
   Already-correct values left alone:
     CORE_MFD.scale=120, PLL_PREDIV.scale=2, PHI0.scale=3, PHI1.scale=3,
     POSTDIV.scale=2, MC_CGM_MUX_0_DIV0.scale=1

B) Mcu config_set:
   - McuPll_0 / McuPLLUnderMcuControl: false -> true
   - McuPll_0 / McuPLLEnabled: false -> true
   - McuPll_Configuration / McuPllOdiv0_En: false -> true
   - McuPll_Configuration / McuPllOdiv1_En: false -> true
    - McuPll_Configuration: quick_selection cleared; PLL fields inserted:
       McuPllDvRdiv=2, McuPllDvMfi=120, McuPllDvOdiv2=2,
       McuPllOdiv0_Div=2, McuPllOdiv1_Div=1
    - McuCgm0ClockMux0 / McuClkMux0_Source: FIRC_CLK -> PLL_PHI0_CLK

C) McuClockReferencePoint array: MERGED -- existing 2 points preserved (LPUART3_CLK,
   FLEXIO_CLK) + 20 new points added (one per selectable clock), each named after its
   clock with McuClockFrequencySelect == Name.  Total = 22 structs, indices 0..21.
   Clocks added: CORE_CLK, AIPS_PLAT_CLK, AIPS_SLOW_CLK, HSE_CLK, DCM_CLK,
                 LBIST_CLK, QSPI_MEM_CLK, STM0_CLK, STM1_CLK,
                 FLEXCAN_PE_CLK0_2, FLEXCAN_PE_CLK3_5, CLKOUT_STANDBY,
                 CLKOUT_RUN, EMAC_CLK_RX, EMAC_CLK_TX, EMAC_CLK_TS,
                 QuadSPI_SFCK, TRACE_CLK, FIRC_CLK, SIRC_CLK
   Existing preserved: LPUART3_CLK (McuClockFrequencySelect=AIPS_SLOW_CLK),
                       FLEXIO_CLK  (McuClockFrequencySelect=CORE_CLK)

NOT written by us:
   - clock_output values (ConfigTools computes these)
   - McuClockReferencePointFrequency
   - McuPllDvRdiv, McuPllDvMfi, McuPllDvOdiv2, McuPllOdiv0_Div, McuPllOdiv1_Div
     (InfoSetting per Mcu.xdm component definition; ConfigTools computes these
     from the clock_settings recipe + quick_selection. Writing them as
     StoragePeriphsScalarSetting causes [SDK/DATA] SEVERE type-mismatch
     and [TOOL] SEVERE "该取值值不可用". Grounded in S32DS 3.6.7 validation
     on 2026-06-30.)
"""

import difflib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_mcu_set
from rtd_config.intent import Intent
from rtd_config.modules.mcu import McuProvider
from tests.fixtures import copy_uart_fixture


# All selectable clocks verified from the Mcu.xdm INVALID rules (lines 14008-14152)
# and the S32K344 reference config. Must match apply.py _ALL_SELECTABLE_CLOCKS
# and clock.json all_selectable_clocks (LL-012 anti-drift).
_ALL_SELECTABLE_CLOCKS = [
    # Mux0 dividers (7 of 8 — Div7 absent from fixture)
    "CORE_CLK",
    "AIPS_PLAT_CLK",
    "AIPS_SLOW_CLK",
    "HSE_CLK",
    "DCM_CLK",
    "LBIST_CLK",
    "QSPI_MEM_CLK",
    # Mux1..Mux11 (all present in fixture)
    "STM0_CLK",
    "STM1_CLK",
    "FLEXCAN_PE_CLK0_2",
    "FLEXCAN_PE_CLK3_5",
    "CLKOUT_STANDBY",
    "CLKOUT_RUN",
    "EMAC_CLK_RX",
    "EMAC_CLK_TX",
    "EMAC_CLK_TS",
    "QuadSPI_SFCK",
    "TRACE_CLK",
    # Source clocks (not through CGM muxes; directly available)
    "FIRC_CLK",
    "SIRC_CLK",
]

# Pre-existing reference points in the fixture (preserved by the MERGE strategy).
# Grounded in Uart_Example.mex lines 1637-1644: LPUART3_CLK (AIPS_SLOW_CLK) and
# FLEXIO_CLK (CORE_CLK).  These have Name != McuClockFrequencySelect intentionally.
_FIXTURE_EXISTING_REF_POINTS = [
    "LPUART3_CLK",
    "FLEXIO_CLK",
]

# Total after merge: existing 2 + 20 new = 22
_EXPECTED_REF_POINT_COUNT = len(_FIXTURE_EXISTING_REF_POINTS) + len(_ALL_SELECTABLE_CLOCKS)


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "mcu", "action": "set", "payload": payload})


def _std_intent() -> Intent:
    """Standard 160/80/40 intent with add_all_clock_reference_points."""
    return _intent(
        core_clk=160,
        aips_plat_clk=80,
        aips_slow_clk=40,
        add_all_clock_reference_points=True,
    )


def _mcu_cfg(doc: MexDocument) -> ET.Element | None:
    return doc.find_config_set("Mcu")


def _find_clock_setting(raw: bytes, setting_id: str) -> str | None:
    """Find a clock_settings <setting id="..." value="..."> in the raw bytes.

    Returns the value attribute string if found, else None.
    This avoids the namespace-prefixed ET parse for the clock_settings section.
    """
    import re
    pattern = rf'<setting id="{re.escape(setting_id)}" value="([^"]*)"'
    m = re.search(pattern.encode(), raw)
    if m:
        return m.group(1).decode()
    return None


def _clock_setting_absent(raw: bytes, setting_id: str) -> bool:
    """Return True if no <setting id="setting_id" ...> exists in raw bytes."""
    import re
    pattern = rf'<setting id="{re.escape(setting_id)}"'.encode()
    return pattern not in raw


def _mcu_struct_setting(doc: MexDocument, struct_name: str, setting_name: str) -> str | None:
    """Find a named struct inside Mcu config_set, return a child setting value."""
    mcu_cfg = _mcu_cfg(doc)
    if mcu_cfg is None:
        return None
    for el in mcu_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == struct_name:
            s = doc.find_child_setting(el, setting_name)
            return s.attrib.get("value") if s is not None else None
    return None


def _find_pll_cfg_struct(doc: MexDocument) -> ET.Element | None:
    """Return the McuPll_Configuration struct inside McuPll_0."""
    mcu_cfg = _mcu_cfg(doc)
    if mcu_cfg is None:
        return None
    for el in mcu_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "McuPll_Configuration":
            return el
    return None


def _find_struct_by_name_setting(doc: MexDocument, name_value: str) -> ET.Element | None:
    """Find any struct whose Name setting equals name_value."""
    mcu_cfg = _mcu_cfg(doc)
    if mcu_cfg is None:
        return None
    for el in mcu_cfg.iter():
        if el.tag.endswith("struct"):
            ns = doc.find_child_setting(el, "Name")
            if ns is not None and ns.attrib.get("value") == name_value:
                return el
    return None


def _ref_point_structs(doc: MexDocument) -> list[ET.Element]:
    """Return the McuClockReferencePoint struct list."""
    mcu_cfg = _mcu_cfg(doc)
    if mcu_cfg is None:
        return []
    for el in mcu_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "McuClockReferencePoint":
            return [c for c in el if c.tag.endswith("struct")]
    return []


def _changed_lines(before: bytes, after: bytes) -> list[str]:
    b = before.decode("utf-8", errors="replace").splitlines(keepends=True)
    a = after.decode("utf-8", errors="replace").splitlines(keepends=True)
    diff = difflib.unified_diff(b, a, n=0, lineterm="")
    return [
        line for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


# ===========================================================================
# Section A: clock_settings input edits
# ===========================================================================

# Test A1: MC_CGM_MUX_0.sel = PHI0 is written (was absent)
def test_clock_setting_mux0_sel_phi0(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    result = apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "mcu" in result.changed_modules
    assert _find_clock_setting(after, "MC_CGM_MUX_0.sel") == "PHI0", (
        "MC_CGM_MUX_0.sel must be set to PHI0"
    )


# Test A2: MC_CGM_MUX_0_DIV1.scale changed from 1 to 2
def test_clock_setting_div1_scale_2(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "MC_CGM_MUX_0_DIV1.scale")
    assert val == "2", f"MC_CGM_MUX_0_DIV1.scale must be '2', got {val!r}"


# Test A3: MC_CGM_MUX_0_DIV2.scale changed from 2 to 4
def test_clock_setting_div2_scale_4(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "MC_CGM_MUX_0_DIV2.scale")
    assert val == "4", f"MC_CGM_MUX_0_DIV2.scale must be '4', got {val!r}"


# Test A3b: MC_CGM_MUX_0_DIV3.scale changed from 1 to 2 (HSE_CLK fix)
# Root cause of SEVERE: "输入频率必须小于或等于： 120 MHz" on HSE_CLK.
# With CORE_CLK=160 MHz and DIV3=1, HSE_CLK=160 MHz which exceeds the 120 MHz limit.
# Grounded in example_Dio.mex clock_settings: DIV3.scale=2 -> HSE_CLK=160/2=80 MHz.
def test_clock_setting_div3_scale_2(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Verify fixture starts with DIV3.scale=1 (pre-condition for the CHANGE path)
    before = mex.read_bytes()
    assert b'MC_CGM_MUX_0_DIV3.scale" value="1"' in before, (
        "Fixture must have MC_CGM_MUX_0_DIV3.scale=1 before apply (pre-condition)"
    )

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "MC_CGM_MUX_0_DIV3.scale")
    assert val == "2", (
        f"MC_CGM_MUX_0_DIV3.scale must be '2' (HSE_CLK=CORE/2=80 MHz; "
        f"grounded in example_Dio.mex verified working example), got {val!r}"
    )


# Test A3c: MC_CGM_MUX_0_DIV4.scale written as 4 (DCM_CLK = CORE/4 = 40 MHz)
# Grounded in example_Dio.mex clock_settings: DIV4.scale=4 -> DCM_CLK=160/4=40 MHz.
# Fixture already has DIV4.scale=4; this test confirms consistency (no regression).
def test_clock_setting_div4_scale_4(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "MC_CGM_MUX_0_DIV4.scale")
    assert val == "4", (
        f"MC_CGM_MUX_0_DIV4.scale must be '4' (DCM_CLK=CORE/4=40 MHz; "
        f"grounded in example_Dio.mex verified working example), got {val!r}"
    )


# Test A3d: MC_CGM_MUX_0_DIV6.scale written as 1 (QSPI_MEM_CLK = CORE/1 = 160 MHz)
# Grounded in example_Dio.mex clock_settings: DIV6.scale=1 -> QSPI_MEM_CLK=160/1=160 MHz.
# Fixture already has DIV6.scale=1; this test confirms consistency (no regression).
def test_clock_setting_div6_scale_1(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "MC_CGM_MUX_0_DIV6.scale")
    assert val == "1", (
        f"MC_CGM_MUX_0_DIV6.scale must be '1' (QSPI_MEM_CLK=CORE/1=160 MHz; "
        f"grounded in example_Dio.mex verified working example), got {val!r}"
    )


# Test A4: CORE_PLL_PD = Power_up is written (was absent)
def test_clock_setting_pll_power_up(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "CORE_PLL_PD")
    assert val == "Power_up", f"CORE_PLL_PD must be 'Power_up', got {val!r}"


# Test A5: CORE_PLLODIV_0_DE = Enabled (was absent)
def test_clock_setting_pllodiv0_enabled(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "CORE_PLLODIV_0_DE")
    assert val == "Enabled", f"CORE_PLLODIV_0_DE must be 'Enabled', got {val!r}"


# Test A6: CORE_PLLODIV_1_DE = Enabled (was absent)
def test_clock_setting_pllodiv1_enabled(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "CORE_PLLODIV_1_DE")
    assert val == "Enabled", f"CORE_PLLODIV_1_DE must be 'Enabled', got {val!r}"


# Test A7: PLLunderMcuControl is changed from "Disabled" to "Enabled" in clock_settings
def test_clock_setting_pll_under_mcu_control_changed_to_enabled(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Verify it exists in the fixture
    before = mex.read_bytes()
    assert b'PLLunderMcuControl' in before, "PLLunderMcuControl must be in fixture"

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    val = _find_clock_setting(after, "PLLunderMcuControl")
    assert val == "Enabled", f"PLLunderMcuControl must be 'Enabled', got {val!r}"


# Test A8: Already-correct values are NOT changed by our edits
# CORE_MFD.scale=120, PLL_PREDIV.scale=2, PHI0.scale=3, POSTDIV.scale=2,
# MC_CGM_MUX_0_DIV0.scale=1
def test_correct_values_untouched(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    assert _find_clock_setting(after, "CORE_MFD.scale") == "120"
    assert _find_clock_setting(after, "PLL_PREDIV.scale") == "2"
    assert _find_clock_setting(after, "PHI0.scale") == "3"
    assert _find_clock_setting(after, "PHI1.scale") == "3"
    assert _find_clock_setting(after, "POSTDIV.scale") == "2"
    assert _find_clock_setting(after, "MC_CGM_MUX_0_DIV0.scale") == "1"


# Test A9: clock_output values are NOT written by us (they would be new entries)
def test_clock_output_values_not_written(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    before = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    # Count clock_output lines -- must be unchanged
    before_outputs = [l for l in before.split(b"\n") if b"clock_output" in l]
    after_outputs = [l for l in after.split(b"\n") if b"clock_output" in l]
    assert len(before_outputs) == len(after_outputs), (
        f"clock_output count changed: {len(before_outputs)} -> {len(after_outputs)}; "
        "we must NOT write clock_output values"
    )


# ===========================================================================
# Section B: Mcu config_set structural edits
# ===========================================================================

# Test B1: McuPLLUnderMcuControl changed to true
def test_mcu_pll_under_mcu_control_true(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    val = _mcu_struct_setting(doc, "McuPll_0", "McuPLLUnderMcuControl")
    assert val == "true", f"McuPLLUnderMcuControl must be 'true', got {val!r}"


# Test B2: McuPLLEnabled changed to true
def test_mcu_pll_enabled_true(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    val = _mcu_struct_setting(doc, "McuPll_0", "McuPLLEnabled")
    assert val == "true", f"McuPLLEnabled must be 'true', got {val!r}"


# Test B3: McuPllOdiv0_En changed to true inside McuPll_Configuration
def test_mcu_pll_odiv0_en_true(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    val = _mcu_struct_setting(doc, "McuPll_Configuration", "McuPllOdiv0_En")
    assert val == "true", f"McuPllOdiv0_En must be 'true', got {val!r}"


# Test B4: McuPllOdiv1_En changed to true inside McuPll_Configuration
def test_mcu_pll_odiv1_en_true(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    val = _mcu_struct_setting(doc, "McuPll_Configuration", "McuPllOdiv1_En")
    assert val == "true", f"McuPllOdiv1_En must be 'true', got {val!r}"


# Test B5: McuPll_Configuration does NOT have PLL divider parameter fields written.
# McuPllDvRdiv, McuPllDvMfi, McuPllDvOdiv2, McuPllOdiv0_Div, McuPllOdiv1_Div
# are InfoSetting per Mcu.xdm (ConfigTools computes them from the clock_settings
# recipe + quick_selection on McuPll_Parameter). Writing them as
# StoragePeriphsScalarSetting causes:
#   [SDK/DATA] SEVERE: type mismatch (InfoSetting in .xdm, StoragePeriphsScalarSetting in .mex)
#   [TOOL] SEVERE: "该取值值不可用" (value not available)
# Grounded in S32DS 3.6.7 validation on 2026-06-30.
def test_mcu_pll_divider_fields_not_written(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    mex2 = project / "Uart_Example.mex"
    doc.write(mex2)
    doc2 = MexDocument.load(mex2)

    pll_cfg = _find_pll_cfg_struct(doc2)
    assert pll_cfg is not None, "McuPll_Configuration struct not found after apply"

    # These five fields are InfoSetting — ConfigTools computes them.
    # Our code must NOT write them (same class of bug as McuClkMux0Div*_Divisor).
    assert doc2.find_child_setting(pll_cfg, "McuPllDvRdiv") is None, \
        "McuPllDvRdiv must NOT be written (InfoSetting per Mcu.xdm; S32DS [TOOL] SEVERE otherwise)"
    assert doc2.find_child_setting(pll_cfg, "McuPllDvMfi") is None, \
        "McuPllDvMfi must NOT be written (InfoSetting per Mcu.xdm)"
    assert doc2.find_child_setting(pll_cfg, "McuPllDvOdiv2") is None, \
        "McuPllDvOdiv2 must NOT be written (InfoSetting per Mcu.xdm)"
    assert doc2.find_child_setting(pll_cfg, "McuPllOdiv0_Div") is None, \
        "McuPllOdiv0_Div must NOT be written (InfoSetting per Mcu.xdm)"
    assert doc2.find_child_setting(pll_cfg, "McuPllOdiv1_Div") is None, \
        "McuPllOdiv1_Div must NOT be written (InfoSetting per Mcu.xdm)"


# Test B6: McuPll_Parameter quick_selection is preserved after apply
def test_mcu_pll_parameter_quick_selection_preserved(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Verify quick_selection exists in fixture
    before = mex.read_bytes()
    assert b'McuPll_Parameter' in before
    # The fixture has quick_selection="Default" on McuPll_Parameter
    assert b'quick_selection="Default"' in before

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    # After apply, McuPll_Parameter must STILL carry quick_selection="Default"
    # (McuPll_Parameter is untouched by apply_mcu_set; PLL fields are now written
    # to McuPll_Configuration instead. The quick_selection on McuPll_Parameter
    # is needed by ConfigTools for calculated output fields like PLL_PHI0_Frequency.)
    import re
    # Find the McuPll_Parameter struct start tag in the output
    m = re.search(rb'<[^>]*name="McuPll_Parameter"[^>]*>', after)
    assert m is not None, "McuPll_Parameter not found in written file"
    tag = m.group(0)
    assert b'quick_selection="Default"' in tag, (
        f"quick_selection must be preserved on McuPll_Parameter after apply; "
        f"tag: {tag!r}"
    )


# Test B7: McuClkMux0_Source changed to PLL_PHI0_CLK
def test_mcu_cgm_mux0_source_pll_phi0(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    val = _mcu_struct_setting(doc, "McuCgm0ClockMux0", "McuClkMux0_Source")
    assert val == "PLL_PHI0_CLK", f"McuClkMux0_Source must be 'PLL_PHI0_CLK', got {val!r}"


# Test B8: McuCgm0ClockMux0 divisor fields are NOT written (removed per descriptor audit)
def test_mcu_cgm_mux0_divisors_absent(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    doc2 = MexDocument.load(mex)

    mux0 = _find_struct_by_name_setting(doc2, "McuCgm0ClockMux0")
    assert mux0 is not None, "McuCgm0ClockMux0 struct not found"

    div0 = doc2.find_child_setting(mux0, "McuClkMux0Div0_Divisor")
    div1 = doc2.find_child_setting(mux0, "McuClkMux0Div1_Divisor")
    div2 = doc2.find_child_setting(mux0, "McuClkMux0Div2_Divisor")

    assert div0 is None, "McuClkMux0Div0_Divisor must NOT be written"
    assert div1 is None, "McuClkMux0Div1_Divisor must NOT be written"
    assert div2 is None, "McuClkMux0Div2_Divisor must NOT be written"


# ===========================================================================
# Section C: McuClockReferencePoint array replacement
# ===========================================================================

# Test C1: Array has exactly the expected merged count (existing 2 + 20 new = 22)
# The MERGE strategy preserves existing points (so UartClockRef paths stay resolvable)
# and adds the 20 selectable-clock points. Vendor gate confirmed replace-all deletes
# LPUART3_CLK/FLEXIO_CLK causing SEVERE "该取值值不可用" on Uart channels.
def test_ref_points_count(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    structs = _ref_point_structs(doc)
    assert len(structs) == _EXPECTED_REF_POINT_COUNT, (
        f"Expected {_EXPECTED_REF_POINT_COUNT} reference points "
        f"(existing {len(_FIXTURE_EXISTING_REF_POINTS)} + new {len(_ALL_SELECTABLE_CLOCKS)}), "
        f"got {len(structs)}"
    )


# Test C2: New clock-named reference points have Name == McuClockFrequencySelect.
# The MERGE strategy preserves existing structs (LPUART3_CLK, FLEXIO_CLK) whose
# Name intentionally differs from McuClockFrequencySelect (cross-references kept
# for Uart channels). Only the NEW structs are required to have Name==FreqSelect.
# All 20 selectable clocks must be present (forward from Mcu.xdm; issue #38).
def test_ref_points_named_after_clock(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    structs = _ref_point_structs(doc)
    all_names = []
    for s in structs:
        name = doc.find_child_setting(s, "Name")
        freq_sel = doc.find_child_setting(s, "McuClockFrequencySelect")
        assert name is not None, "McuClockReferencePoint struct missing Name setting"
        assert freq_sel is not None, "McuClockReferencePoint struct missing McuClockFrequencySelect"
        n = name.attrib.get("value", "")
        f = freq_sel.attrib.get("value", "")
        all_names.append(n)
        # For NEW clock-named structs (Name is one of the selectable clocks):
        # Name must equal McuClockFrequencySelect.
        # Existing preserved structs (LPUART3_CLK, FLEXIO_CLK) intentionally have
        # Name != McuClockFrequencySelect (they are cross-reference aliases).
        if n in _ALL_SELECTABLE_CLOCKS:
            assert n == f, (
                f"New clock-named struct: Name ({n!r}) must equal "
                f"McuClockFrequencySelect ({f!r})"
            )

    # All selectable clocks must be present as reference point Names
    for clk in _ALL_SELECTABLE_CLOCKS:
        assert clk in all_names, f"Clock {clk!r} missing from McuClockReferencePoint array"


# Test C3: Struct indices are sequential from 0 across all merged structs.
# The MERGE reorders indices 0..N-1 where N = existing + new (32 in fixture).
# Existing structs come first (indices 0,1), new clock-named structs follow (2..31).
def test_ref_points_sequential_indices(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    structs = _ref_point_structs(doc)
    assert len(structs) == _EXPECTED_REF_POINT_COUNT, (
        f"Expected {_EXPECTED_REF_POINT_COUNT} structs for sequential-index check, "
        f"got {len(structs)}"
    )
    for i, s in enumerate(structs):
        assert s.attrib.get("name") == str(i), (
            f"Struct at position {i} has name {s.attrib.get('name')!r}, expected '{i}'"
        )


# Test C4: McuClockReferencePointFrequency is NOT written by us
def test_ref_points_no_frequency_written(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())

    structs = _ref_point_structs(doc)
    for s in structs:
        freq = doc.find_child_setting(s, "McuClockReferencePointFrequency")
        assert freq is None, (
            f"McuClockReferencePointFrequency must NOT be written by apply_mcu_set; "
            f"found in struct {s.attrib.get('name')!r}"
        )


# ===========================================================================
# Section D: Cross-cutting structural correctness
# ===========================================================================

# Test D1: Written file reloads as well-formed XML
def test_written_file_well_formed(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcu_set(doc, _std_intent())
    doc.write(mex)

    reloaded = MexDocument.load(mex)
    mcu_cfg = reloaded.find_config_set("Mcu")
    assert mcu_cfg is not None, "Mcu config_set not found in reloaded file"

    structs = _ref_point_structs(reloaded)
    assert len(structs) == _EXPECTED_REF_POINT_COUNT


# Test D2: Idempotency -- second apply produces no duplicate reference points
def test_idempotent_apply(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc1 = MexDocument.load(mex)
    apply_mcu_set(doc1, _std_intent())
    doc1.write(mex)

    doc2 = MexDocument.load(mex)
    result2 = apply_mcu_set(doc2, _std_intent())
    doc2.write(mex)

    assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
    doc3 = MexDocument.load(mex)
    structs = _ref_point_structs(doc3)
    assert len(structs) == _EXPECTED_REF_POINT_COUNT, (
        f"Idempotency failed: {len(structs)} ref points after two applies, "
        f"expected {_EXPECTED_REF_POINT_COUNT}"
    )


# Test D3: Byte-narrow diff -- existing unrelated settings NOT blown away
def test_edit_is_not_full_reserialization(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    before = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    # XML declaration line must be preserved exactly
    after_lines = after.decode("utf-8", errors="replace").splitlines()
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>', (
        "XML declaration must be preserved byte-faithfully"
    )

    # Existing Mcu config elements we do NOT touch must remain
    assert b"McuClockSettingConfig_0" in after
    assert b"McuFIRC" in after
    assert b"McuSIRC" in after
    assert b"McuFXOSC" in after
    assert b"McuCgm0PcfsConfig_0" in after


# Test D4: McuNoPll must be set to false when PLL is enabled under Mcu control
# Grounded in Mcu.xdm INVALID rule: McuNoPll='true' AND McuPLLUnderMcuControl='true'
# produces SEVERE: "PLL cannot be under MCU control if McuNoPll is enabled."
def test_mcu_no_pll_set_false_when_pll_enabled(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Verify the fixture starts with McuNoPll=true (the pre-PLL default)
    before = mex.read_bytes()
    assert b'McuNoPll" value="true"' in before, (
        "Fixture must have McuNoPll=true before apply (pre-condition)"
    )

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    # McuNoPll must be false after enabling PLL (Mcu.xdm INVALID rule)
    assert b'McuNoPll" value="false"' in after, (
        "McuNoPll must be set to 'false' when PLL is enabled under Mcu control "
        "(Mcu.xdm INVALID: PLL cannot be under MCU control if McuNoPll is enabled)"
    )
    assert b'McuNoPll" value="true"' not in after, (
        "McuNoPll must NOT remain 'true' after PLL enable"
    )


# Test D5-b: McuPll0UnderMcuControl in McuControlledClocksConfiguration must be true
# Grounded in Mcu.xdm INVALID rule: McuPLLUnderMcuControl='true' but
# McuControlledClocksConfiguration/McuPll0UnderMcuControl='false' produces
# SEVERE: "The field McuGeneralConfiguration/McuControlledClocksConfiguration/
#          McuPll0UnderMcuControl must be set to 'true' when PLL is under MCU control."
def test_mcu_pll0_under_mcu_control_in_general_config(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Verify the fixture starts with McuPll0UnderMcuControl=false (the pre-PLL default)
    before = mex.read_bytes()
    assert b'McuPll0UnderMcuControl" value="false"' in before, (
        "Fixture must have McuPll0UnderMcuControl=false before apply (pre-condition)"
    )

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    # McuPll0UnderMcuControl under McuControlledClocksConfiguration must be true
    assert b'McuPll0UnderMcuControl" value="true"' in after, (
        "McuGeneralConfiguration/McuControlledClocksConfiguration/McuPll0UnderMcuControl "
        "must be set to 'true' when PLL is under MCU control "
        "(Mcu.xdm INVALID rule; vendor gate SEVERE otherwise)"
    )


# Test D4-uart: UartClockRef paths in Uart config remain valid after reference point replacement
# The --add-all-clock-reference-points flag replaces the McuClockReferencePoint array.
# Pre-existing UartClockRef paths that reference named clock points (e.g. LPUART3_CLK,
# FLEXIO_CLK) must still resolve after the replacement, i.e. the new array must include
# structs with those names (or the implementation must update the Uart references).
# Vendor gate SEVERE: "该取值值不可用" (value unavailable) otherwise.
def test_uart_clock_refs_remain_resolvable(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Identify UartClockRef names in the original fixture
    before = mex.read_bytes()
    import re
    uart_clock_refs = re.findall(
        rb'UartClockRef" value="[^"]+/McuClockSettingConfig_0/([^"]+)"',
        before,
    )
    # Fixture has LPUART3_CLK and FLEXIO_CLK
    assert len(uart_clock_refs) > 0, "Fixture must have UartClockRef entries"
    ref_names = {r.decode() for r in uart_clock_refs}

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _std_intent())
    doc.write(mex)
    after = mex.read_bytes()

    # After apply, every UartClockRef name that existed before must exist
    # as a Name setting in the McuClockReferencePoint array.
    # Locate the McuClockReferencePoint array section in the written bytes.
    rp_section_m = re.search(
        rb'array name="McuClockReferencePoint">(.*?)</array>',
        after,
        re.DOTALL,
    )
    assert rp_section_m is not None, "McuClockReferencePoint array not found after apply"
    rp_section = rp_section_m.group(1)

    rp_names = set(re.findall(rb'Name" value="([^"]+)"', rp_section))
    for ref in ref_names:
        assert ref.encode() in rp_names, (
            f"UartClockRef '{ref}' is no longer a valid McuClockReferencePoint Name after apply; "
            f"existing names: {sorted(n.decode() for n in rp_names)}. "
            f"Vendor gate raises SEVERE '该取值值不可用' when a UartClockRef resolves to nothing."
        )


# Test D5: Unsupported frequency combo returns a blocker (not a silent wrong write)
def test_unsupported_combo_blocked(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    # 200/100/50 is not in our supported recipe table
    result = apply_mcu_set(
        doc,
        _intent(core_clk=200, aips_plat_clk=100, aips_slow_clk=50, add_all_clock_reference_points=True),
    )

    assert result.blocked, (
        "Expected a blocker for unsupported freq combo 200/100/50; got no blocker"
    )
    codes = [d.code for d in result.diagnostics]
    assert any("unsupported" in c for c in codes), (
        f"Expected an 'unsupported' diagnostic code; got: {codes}"
    )


# ===========================================================================
# Section E: plan() and CLI integration
# ===========================================================================

# Test E1: plan() emits accurate PlannedChange(s) with owner=mcu
def test_plan_describes_clock_and_ref_edits(tmp_path):
    intent = _std_intent()
    plan = McuProvider().plan(intent)

    assert len(plan.changes) >= 1
    mcu_changes = [c for c in plan.changes if c.owner == "mcu"]
    assert len(mcu_changes) >= 1, "No mcu-owned change in plan"

    # At least one change references the clock tree or the reference point array
    texts = " ".join(c.description + c.path for c in mcu_changes)
    assert any(kw in texts for kw in ("clock", "PLL", "reference", "McuClockReferencePoint")), (
        f"plan() changes do not reference clock or reference point work: {plan.to_dict()}"
    )


# Test E2: CLI integration -- mcu set --core-clk 160 ... --configure returns passed
def test_cli_mcu_set_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "mcu", "set",
            "--project", str(project),
            "--core-clk", "160",
            "--aips-plat-clk", "80",
            "--aips-slow-clk", "40",
            "--add-all-clock-reference-points",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, (
        f"mcu set returned non-zero\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert "mcu" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"


# Test E3: CLI plan-only (no --configure) returns passed with plan info
def test_cli_mcu_set_plan_only(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "mcu", "set",
            "--project", str(project),
            "--core-clk", "160",
            "--aips-plat-clk", "80",
            "--aips-slow-clk", "40",
            "--add-all-clock-reference-points",
            "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, (
        f"mcu set plan-only returned non-zero\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert payload["command"] == "plan"
    # Mex file must NOT be modified in plan-only mode
    mex = project / "Uart_Example.mex"
    after = mex.read_bytes()
    # The fixture still has the old MC_CGM_MUX_0_DIV1.scale=1 (no configure)
    assert b'MC_CGM_MUX_0_DIV1.scale" value="1"' in after, (
        "File must not be modified in plan-only mode"
    )


# ===========================================================================
# Section F: Asset-code synchronisation (LL-012 anti-drift)
# ===========================================================================

# Test F1: _ALL_SELECTABLE_CLOCKS in apply.py matches clock.json asset
def test_all_selectable_clocks_matches_asset():
    """Code literal _ALL_SELECTABLE_CLOCKS must match clock.json asset list (LL-012).

    Prevents the code constants and the committed asset from drifting silently.
    """
    from pathlib import Path
    from rtd_config.backends.s32_mex.apply import _ALL_SELECTABLE_CLOCKS

    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    asset_clocks = asset["all_selectable_clocks"]

    assert _ALL_SELECTABLE_CLOCKS == asset_clocks, (
        f"Code _ALL_SELECTABLE_CLOCKS does not match clock.json all_selectable_clocks.\n"
        f"Code: {_ALL_SELECTABLE_CLOCKS}\n"
        f"Asset: {asset_clocks}"
    )

    # Verify it also matches the test-level constant (code vs test cross-check)
    from rtd_config.backends.s32_mex.apply import _ALL_SELECTABLE_CLOCKS as code_clocks
    assert code_clocks == _ALL_SELECTABLE_CLOCKS, (
        f"Code _ALL_SELECTABLE_CLOCKS does not match test constant.\n"
        f"Code: {code_clocks}\n"
        f"Test: {_ALL_SELECTABLE_CLOCKS}"
    )
    assert asset_clocks == list(_ALL_SELECTABLE_CLOCKS), (
        "clock.json all_selectable_clocks must match the test constant"
    )


# ===========================================================================
# Section G: Full recipe pin (Fix 1 -- LL-012/LL-014 anti-drift, Fix 3, Fix 4)
# ===========================================================================

# Test G1: Full clock recipe pin -- code literals vs clock.json (Fix 1)
def test_clock_json_matches_apply_code_literals():
    """Pin the FULL 160/80/40 recipe in apply.py against clock.json (LL-012/LL-014).

    Every clock_settings change/insert/remove id+value, the PLL param values,
    the divisors, and the GAP-field writes must all be present in clock.json.
    Any future code/asset drift fails this gate.

    clock.json is a committed reference document for the recipe; it must stay
    current with the code via this test. The asset is NOT loaded at runtime;
    it is pinned here.
    """
    from pathlib import Path

    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))

    # There must be exactly one recipe for 160/80/40
    recipes = asset["recipes"]
    recipe = next(
        (r for r in recipes if r["core_clk"] == 160 and r["aips_plat_clk"] == 80
         and r["aips_slow_clk"] == 40),
        None,
    )
    assert recipe is not None, "No 160/80/40 recipe found in clock.json"

    # --- clock_settings_changes: all 5 scale writes ---
    changes = {e["id"]: e["value"] for e in recipe["clock_settings_changes"]}
    assert changes.get("MC_CGM_MUX_0_DIV1.scale") == "2", (
        "clock.json must document DIV1.scale=2"
    )
    assert changes.get("MC_CGM_MUX_0_DIV2.scale") == "4", (
        "clock.json must document DIV2.scale=4"
    )
    assert changes.get("MC_CGM_MUX_0_DIV3.scale") == "2", (
        "clock.json must document DIV3.scale=2 (HSE_CLK fix -- ffc6ff2)"
    )
    assert changes.get("MC_CGM_MUX_0_DIV4.scale") == "4", (
        "clock.json must document DIV4.scale=4 (DCM_CLK)"
    )
    assert changes.get("MC_CGM_MUX_0_DIV6.scale") == "1", (
        "clock.json must document DIV6.scale=1 (QSPI_MEM_CLK)"
    )

    # --- clock_settings_inserts: 4 entries ---
    inserts = {e["id"]: e["value"] for e in recipe["clock_settings_inserts"]}
    assert inserts.get("CORE_PLL_PD") == "Power_up", (
        "clock.json must document CORE_PLL_PD=Power_up insert"
    )
    assert inserts.get("CORE_PLLODIV_0_DE") == "Enabled", (
        "clock.json must document CORE_PLLODIV_0_DE=Enabled insert"
    )
    assert inserts.get("CORE_PLLODIV_1_DE") == "Enabled", (
        "clock.json must document CORE_PLLODIV_1_DE=Enabled insert"
    )
    assert inserts.get("MC_CGM_MUX_0.sel") == "PHI0", (
        "clock.json must document MC_CGM_MUX_0.sel=PHI0 insert"
    )

    # --- clock_settings_changes: PLLunderMcuControl Disabled->Enabled ---
    changes = [e["id"] for e in recipe["clock_settings_changes"]]
    assert "PLLunderMcuControl" in changes, (
        "clock.json must document PLLunderMcuControl change to Enabled"
    )
    pll_change = next(e for e in recipe["clock_settings_changes"] if e["id"] == "PLLunderMcuControl")
    assert pll_change.get("value") == "Enabled", (
        "clock.json must document PLLunderMcuControl value=Enabled"
    )

    # --- mcu_config_set_changes: GAP fixes + PLL + Cgm source ---
    cfg_changes = recipe["mcu_config_set_changes"]

    # GAP 1: McuNoPll=false (prevents SEVERE "PLL cannot be under MCU control if McuNoPll is enabled")
    gen_cfg = cfg_changes.get("McuGeneralConfiguration", {})
    assert gen_cfg.get("McuNoPll") == "false", (
        "clock.json must document McuGeneralConfiguration/McuNoPll=false (GAP 1)"
    )

    # GAP 2: McuPll0UnderMcuControl=true
    ctrl_cfg = cfg_changes.get("McuControlledClocksConfiguration", {})
    assert ctrl_cfg.get("McuPll0UnderMcuControl") == "true", (
        "clock.json must document McuControlledClocksConfiguration/McuPll0UnderMcuControl=true (GAP 2)"
    )

    # McuPll_0
    pll0 = cfg_changes.get("McuPll_0", {})
    assert pll0.get("McuPLLUnderMcuControl") == "true"
    assert pll0.get("McuPLLEnabled") == "true"

    # McuPll_Configuration
    pll_cfg = cfg_changes.get("McuPll_Configuration", {})
    assert pll_cfg.get("McuPllOdiv0_En") == "true"
    assert pll_cfg.get("McuPllOdiv1_En") == "true"

    # McuCgm0ClockMux0 source
    mux0 = cfg_changes.get("McuCgm0ClockMux0", {})
    assert mux0.get("McuClkMux0_Source") == "PLL_PHI0_CLK", (
        "clock.json must document McuCgm0ClockMux0/McuClkMux0_Source=PLL_PHI0_CLK"
    )

    # --- McuPll_Configuration_inserts: must NOT exist ---
    # McuPllDvRdiv/McuPllDvMfi/McuPllDvOdiv2/McuPllOdiv0_Div/McuPllOdiv1_Div
    # are InfoSetting per Mcu.xdm (ConfigTools computes them from clock_settings
    # recipe + quick_selection). The asset must not document writing them.
    # S32DS 3.6.7 validation on 2026-06-30: writing them as
    # StoragePeriphsScalarSetting causes [SDK/DATA] SEVERE type-mismatch
    # and [TOOL] SEVERE "该取值值不可用".
    assert "McuPll_Configuration_inserts" not in recipe, (
        "clock.json must NOT contain McuPll_Configuration_inserts -- "
        "McuPllDvRdiv/McuPllDvMfi/etc. are InfoSetting per Mcu.xdm; "
        "writing them triggers [TOOL] SEVERE '该取值值不可用' (S32DS 2026-06-30)"
    )

    # --- _source key exists (Fix 5) ---
    assert "_source" in asset, (
        "clock.json must use '_source' key for provenance (not '_comment')"
    )


# Test G2: plan() description does NOT say "replace" -- it describes merge (Fix 4)
def test_plan_add_all_ref_describes_merge_not_replace():
    """plan() with add_all_clock_reference_points must describe a merge, not a replacement.

    The apply code merges (preserves existing ref points + adds new selectable
    clocks). The plan description must not say 'replace' and must convey the
    merge semantics.
    """
    intent = _std_intent()
    plan = McuProvider().plan(intent)

    ref_changes = [
        c for c in plan.changes
        if "McuClockReferencePoint" in c.path or "reference" in c.description.lower()
    ]
    assert ref_changes, "plan() must emit a change for McuClockReferencePoint when add_all_ref=True"

    for c in ref_changes:
        desc_lower = c.description.lower()
        assert "replace" not in desc_lower, (
            f"plan() description must not say 'replace' (apply merges, not replaces).\n"
            f"Got: {c.description!r}"
        )
        assert any(kw in desc_lower for kw in ("merge", "preserve", "add")), (
            f"plan() description must describe merge semantics (merge/preserve/add).\n"
            f"Got: {c.description!r}"
        )


# Test G3: _load_mcu_clock_asset is NOT importable (dead function removed -- Fix 1)
def test_load_mcu_clock_asset_removed():
    """_load_mcu_clock_asset must not exist in apply.py (dead function removed)."""
    import rtd_config.backends.s32_mex.apply as apply_mod
    assert not hasattr(apply_mod, "_load_mcu_clock_asset"), (
        "_load_mcu_clock_asset is dead code (zero call sites) and must be removed. "
        "The asset is pinned by test_clock_json_matches_apply_code_literals instead."
    )
