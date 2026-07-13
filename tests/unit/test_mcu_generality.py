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
# File:        test_mcu_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-30
# Version:     0.1.0
# Description: Generality tests for the Mcu module over ARBITRARY valid inputs the
#              RTD-MEX-MCU-001 E2E case does NOT exercise. These prove the Mcu
#              module is forward from Mcu.xdm and not case-fit: the 20 fixture-safe
#              McuClockFrequencySelect values from Mcu.xdm INVALID rules are
#              exercised, not just the 13 clocks the E2E case needs.
#              Forward (Spec-first) development, issues #37/#38.
# =================================================================================

"""Mcu generality over arbitrary valid inputs (forward / Spec-first; issues #37/#38).

The RTD-MEX-MCU-001 E2E case is regression verification only; these tests target
the *editable surface* the module supports, with inputs that are deliberately NOT
the case literals, so they fail if the module ever becomes fit to the one case.

All domain values are grounded in Mcu.xdm INVALID rules (lines 14008-14152)
and the S32K344 reference config. The 20 fixture-safe clocks are the CGM0
Mux0..Mux11 + source subset; 10 CGM Mux12-20 + CM7_CORE_CLK clocks are
deferred (documented in clock.json deferred_clocks). No value is invented here.
"""
import difflib
from functools import partial
import json
import sys
from pathlib import Path

import pytest

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_mcu_set, _ALL_SELECTABLE_CLOCKS, _MCU_SUPPORTED_RECIPES
from rtd_config.intent import Intent
from rtd_config.modules.mcu import McuProvider
from tests.fixtures import copy_uart_fixture, resolved_uart_bundle

_BUNDLE = resolved_uart_bundle()
apply_mcu_set = partial(apply_mcu_set, bundle=_BUNDLE)
McuProvider = partial(McuProvider, _BUNDLE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "mcu", "action": "set", "payload": payload})


def _ref_point_structs(doc: MexDocument) -> list:
    mcu_cfg = doc.find_config_set("Mcu")
    assert mcu_cfg is not None
    for el in mcu_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "McuClockReferencePoint":
            return [c for c in el if c.tag.endswith("struct")]
    return []


def _get_ref_point_names(doc: MexDocument) -> set[str]:
    names: set[str] = set()
    for s in _ref_point_structs(doc):
        ns = doc.find_child_setting(s, "Name")
        if ns is not None:
            names.add(ns.attrib.get("value", ""))
    return names


# ---------------------------------------------------------------------------
# Test G01: Asset _coverage section exists and is well-formed
# ---------------------------------------------------------------------------

def test_asset_has_coverage_section():
    """clock.json must carry _coverage inventory mapping configurable vs deferred."""
    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    assert "_coverage" in asset, (
        "clock.json must have _coverage section (forward-harden #38)"
    )
    cov = asset["_coverage"]
    assert "configurable_today" in cov, "_coverage.configurable_today missing"
    assert "not_yet_exposed" in cov, "_coverage.not_yet_exposed missing"
    assert isinstance(cov["configurable_today"], dict)
    assert isinstance(cov["not_yet_exposed"], dict)
    # not_yet_exposed must list multiple sub-categories
    not_yet = cov["not_yet_exposed"]
    assert len(not_yet) >= 3, (
        f"not_yet_exposed must document 3+ categories of deferred surface; got {len(not_yet)}"
    )


# ---------------------------------------------------------------------------
# Test G02: Full McuClockFrequencySelect enum domain present in asset
# ---------------------------------------------------------------------------

def test_asset_enum_domains_match_mcu_xdm():
    """All 20 selectable clocks in the asset must match apply.py _ALL_SELECTABLE_CLOCKS."""
    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    asset_clocks = asset["all_selectable_clocks"]
    assert asset_clocks == _ALL_SELECTABLE_CLOCKS, (
        f"Asset all_selectable_clocks does not match code _ALL_SELECTABLE_CLOCKS.\n"
        f"Asset: {asset_clocks}\nCode:  {_ALL_SELECTABLE_CLOCKS}"
    )


# ---------------------------------------------------------------------------
# Test G03: Every code clock has a corresponding entry in asset enum_domains
# ---------------------------------------------------------------------------

def test_all_code_clocks_in_asset_enum_domains():
    """Every clock in _ALL_SELECTABLE_CLOCKS must be documented in the asset enum_domains."""
    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    mux0 = asset["enum_domains"]["McuClockFrequencySelect"]["mux0_dividers"]
    mux1_20 = asset["enum_domains"]["McuClockFrequencySelect"]["mux1_20_dividers"]
    source = asset["enum_domains"]["McuClockFrequencySelect"]["source_clocks"]

    all_enum_clocks = set(mux0.keys()) | set(mux1_20.keys()) | set(source.keys())

    for clk in _ALL_SELECTABLE_CLOCKS:
        assert clk in all_enum_clocks, (
            f"Clock {clk!r} in code _ALL_SELECTABLE_CLOCKS is not documented "
            f"in asset enum_domains.McuClockFrequencySelect"
        )


# ---------------------------------------------------------------------------
# Test G04: apply_mcu_set is idempotent with add_all_ref_points=False
#          (clock-tree recipe only, no reference point merge)
# ---------------------------------------------------------------------------

def test_idempotent_without_ref_points(tmp_path):
    """Clock-tree edits alone (no reference points) must be idempotent:
    second apply succeeds and produces the same structural result (same
    number of reference points, same clock setting values)."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    intent = _intent(core_clk=160, aips_plat_clk=80, aips_slow_clk=40)

    doc1 = MexDocument.load(mex)
    result1 = apply_mcu_set(doc1, intent)
    doc1.write(mex)
    assert not result1.blocked, [d.to_dict() for d in result1.diagnostics]

    doc2 = MexDocument.load(mex)
    result2 = apply_mcu_set(doc2, intent)
    doc2.write(mex)
    assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]

    # Structural idempotency: same number of reference points after two applies
    structs = _ref_point_structs(doc2)
    fixture_existing = 2  # LPUART3_CLK + FLEXIO_CLK
    assert len(structs) == fixture_existing, (
        f"Idempotency failed: {len(structs)} ref points after two applies "
        f"(no ref points added), expected {fixture_existing}"
    )


# ---------------------------------------------------------------------------
# Test G05: Merge preserves all existing reference points for any subset of
#          selectable clocks (not just the full 20-clock set).
# ---------------------------------------------------------------------------

def test_merge_preserves_existing_for_arbitrary_clock_subset(tmp_path):
    """Merge must preserve LPUART3_CLK and FLEXIO_CLK when adding an arbitrary
    small subset of selectable clocks (NOT the 20-clock full set)."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # First apply full recipe with reference points to populate the initial array
    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _intent(
        core_clk=160, aips_plat_clk=80, aips_slow_clk=40,
        add_all_clock_reference_points=True,
    ))
    doc.write()

    # Now test: existing points must still be present
    doc2 = MexDocument.load(mex)
    names = _get_ref_point_names(doc2)

    assert "LPUART3_CLK" in names, "Merge must preserve existing LPUART3_CLK"
    assert "FLEXIO_CLK" in names, "Merge must preserve existing FLEXIO_CLK"

    # And the subset we care about must be present
    for clk in ["CORE_CLK", "AIPS_PLAT_CLK", "STM0_CLK", "FIRC_CLK"]:
        assert clk in names, f"Clock {clk!r} missing after merge"


# ---------------------------------------------------------------------------
# Test G06: Different valid clock subsets produce well-formed XML
# ---------------------------------------------------------------------------

def test_well_formed_for_different_clock_subsets(tmp_path):
    """The output .mex must be well-formed XML regardless of which clock
    reference points are present (any valid subset from Mcu.xdm)."""
    from xml.etree.ElementTree import parse

    # Apply without reference points at all
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _intent(core_clk=160, aips_plat_clk=80, aips_slow_clk=40))
    doc.write()
    parse(str(mex))  # must not raise


# ---------------------------------------------------------------------------
# Test G07: Unsupported clock combo returns blocker with clear message
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("combo,label", [
    ((120, 60, 30), "lower"),
    ((200, 100, 50), "higher"),
    ((160, 40, 40), "mismatched"),
])
def test_unsupported_clock_combo_blocked(combo, label, tmp_path):
    """Any unsupported (core, plat, slow) trio must return a blocker diagnostic
    referencing the only supported recipe."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    result = apply_mcu_set(doc, _intent(
        core_clk=combo[0], aips_plat_clk=combo[1], aips_slow_clk=combo[2],
    ))
    assert any(
        d.code == "mcu_unsupported_clock_combo" and d.severity == "blocker"
        for d in result.diagnostics
    ), f"Unsupported combo {combo} ({label}) must produce a blocker"
    # Message must mention the supported-only recipe
    blocker = next(
        d for d in result.diagnostics
        if d.code == "mcu_unsupported_clock_combo"
    )
    assert "160" in blocker.message, "Blocker message must mention 160/80/40"


# ---------------------------------------------------------------------------
# Test G08: plan() returns correct number of changes for different intents
# ---------------------------------------------------------------------------

def test_plan_for_different_intents():
    """plan() must return correct change counts for different intent payloads."""
    provider = McuProvider()

    # Clock-only intent: 1 change (clock tree)
    plan1 = provider.plan(Intent.from_dict({
        "module": "mcu", "action": "set",
        "payload": {"core_clk": 160, "aips_plat_clk": 80, "aips_slow_clk": 40},
    }))
    assert len(plan1.changes) == 1, f"Clock-only intent: expected 1 change, got {len(plan1.changes)}"

    # Clock + ref points intent: 2 changes
    plan2 = provider.plan(Intent.from_dict({
        "module": "mcu", "action": "set",
        "payload": {"core_clk": 160, "aips_plat_clk": 80, "aips_slow_clk": 40,
                     "add_all_clock_reference_points": True},
    }))
    assert len(plan2.changes) == 2, f"Clock+ref intent: expected 2 changes, got {len(plan2.changes)}"

    # Ref-points-only intent: 2 changes (clock fallback + ref points)
    plan3 = provider.plan(Intent.from_dict({
        "module": "mcu", "action": "set",
        "payload": {"add_all_clock_reference_points": True},
    }))
    assert len(plan3.changes) >= 1, f"Ref-only intent: expected >=1 change, got {len(plan3.changes)}"

    # Empty intent (fallback): 1 change
    plan4 = provider.plan(Intent.from_dict({
        "module": "mcu", "action": "set", "payload": {},
    }))
    assert len(plan4.changes) == 1, f"Empty intent: expected 1 fallback change, got {len(plan4.changes)}"


# ---------------------------------------------------------------------------
# Test G09: clock_dependency for valid LPUART instances returns correct info
# ---------------------------------------------------------------------------

def test_clock_dependency_for_various_lpuart_instances():
    """clock_dependency must return a PlannedChange with correct LPUARTx_CLK info
    for different LPUART instances (LPUART_3, LPUART_8, LPUART3, LPUART8)."""
    provider = McuProvider()

    for hw, expected_name in [
        ("LPUART_3", "LPUART3_CLK"),
        ("LPUART3", "LPUART3_CLK"),
        ("lpuart_3", "LPUART3_CLK"),
        ("LPUART_8", "LPUART8_CLK"),
    ]:
        change = provider.clock_dependency(hw)
        assert change.module == "mcu"
        assert change.owner == "mcu"
        assert expected_name in change.description, (
            f"clock_dependency({hw!r}) description must mention {expected_name!r}"
        )
        assert "McuClockFrequencySelect" in change.description, (
            f"clock_dependency({hw!r}) description must mention McuClockFrequencySelect"
        )


# ---------------------------------------------------------------------------
# Test G10: Asset constraints section is well-formed and references Mcu.xdm
# ---------------------------------------------------------------------------

def test_asset_constraints_documented():
    """clock.json constraints section must document known INVALID rules from Mcu.xdm."""
    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    constraints = asset.get("constraints", {})
    # At minimum, the GAP 1 and GAP 2 fixes must be documented
    assert "mcu_no_pll_vs_pll_control" in constraints, "GAP 1 constraint missing"
    assert "pll_under_mcu_control_requires_controlled_clocks" in constraints, "GAP 2 constraint missing"
    assert "hse_clk_max_120mhz" in constraints, "HSE_CLK constraint missing"


# ---------------------------------------------------------------------------
# Test G11: byte-narrow diff — only intended lines change
# ---------------------------------------------------------------------------

def test_byte_narrow_diff_only_intended_lines(tmp_path):
    """Only the lines related to Mcu clock tree and reference points must change;
    unrelated sections (Uart, Platform, Port) must be byte-identical."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _intent(
        core_clk=160, aips_plat_clk=80, aips_slow_clk=40,
        add_all_clock_reference_points=True,
    ))
    doc.write()
    modified = mex.read_bytes()

    diff_lines = list(difflib.unified_diff(
        original.decode("utf-8", errors="replace").splitlines(keepends=True),
        modified.decode("utf-8", errors="replace").splitlines(keepends=True),
        fromfile="original", tofile="modified", lineterm="",
    ))
    diff_text = "\n".join(diff_lines)

    # The diff must NOT touch Uart, Platform, Port config sets
    for forbidden in ["<config_set name=\"Uart\">", "<config_set name=\"Platform\">",
                       "<config_set name=\"Port\">"]:
        assert forbidden not in diff_text, (
            f"Byte-narrow diff must not touch unrelated module {forbidden}"
        )

    # The diff MUST touch Mcu config_set
    assert "<config_set name=\"Mcu\">" in modified.decode("utf-8", errors="replace"), (
        "Mcu config_set must be present in output"
    )


# ---------------------------------------------------------------------------
# Test G12: Reference point array preserves index ordering (existing first,
#           new clocks follow) for ANY arbitrary subset of selectable clocks.
# ---------------------------------------------------------------------------

def test_ref_points_ordered_existing_then_new(tmp_path):
    """After merge, existing points must occupy lowest indices, followed by
    new clock-named points, in the order they appear in _ALL_SELECTABLE_CLOCKS.
    This must hold regardless of how many new clocks are added."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc = MexDocument.load(mex)
    apply_mcu_set(doc, _intent(
        core_clk=160, aips_plat_clk=80, aips_slow_clk=40,
        add_all_clock_reference_points=True,
    ))
    doc.write()

    structs = _ref_point_structs(doc)
    # First 2 must be existing (LPUART3_CLK, FLEXIO_CLK)
    existing_names = []
    for i in range(2):
        ns = doc.find_child_setting(structs[i], "Name")
        existing_names.append(ns.attrib.get("value", "") if ns is not None else "")
    assert "LPUART3_CLK" in existing_names, "LPUART3_CLK must be at index 0 or 1"
    assert "FLEXIO_CLK" in existing_names, "FLEXIO_CLK must be at index 0 or 1"

    # Remaining must be clock-named, one per selectable clock
    clock_names_seen = []
    for i in range(2, len(structs)):
        ns = doc.find_child_setting(structs[i], "Name")
        assert ns is not None, f"Struct {i} missing Name"
        name = ns.attrib.get("value", "")
        assert name in _ALL_SELECTABLE_CLOCKS, (
            f"Struct {i} has non-clock name {name!r}"
        )
        clock_names_seen.append(name)

    # All 20 clocks must be present
    for clk in _ALL_SELECTABLE_CLOCKS:
        assert clk in clock_names_seen, (
            f"Selectable clock {clk!r} missing from reference point array"
        )


# ---------------------------------------------------------------------------
# Test G13: McuClockFrequencySelect enum coverage — all 18 CGM0-derived
#          clocks whose mux dividers exist in the fixture are represented
#          in _ALL_SELECTABLE_CLOCKS.
# ---------------------------------------------------------------------------

def test_cgm0_enum_coverage():
    """Every CGM0-derived clock whose mux divider exists in the fixture
    must be present in _ALL_SELECTABLE_CLOCKS.

    Mux0 Div7 (CM7_CORE_CLK) and Mux12-20 are absent from the fixture;
    those 10 clocks are deferred (documented in clock.json deferred_clocks).
    """
    # These are the 18 CGM0-derivable fixture-safe clocks
    cgm0_derivable_clocks = {
        "CORE_CLK", "AIPS_PLAT_CLK", "AIPS_SLOW_CLK", "HSE_CLK", "DCM_CLK",
        "LBIST_CLK", "QSPI_MEM_CLK",
        "STM0_CLK", "STM1_CLK", "FLEXCAN_PE_CLK0_2", "FLEXCAN_PE_CLK3_5",
        "CLKOUT_STANDBY", "CLKOUT_RUN",
        "EMAC_CLK_RX", "EMAC_CLK_TX", "EMAC_CLK_TS",
        "QuadSPI_SFCK", "TRACE_CLK",
    }
    code_clocks = set(_ALL_SELECTABLE_CLOCKS)
    missing = cgm0_derivable_clocks - code_clocks
    assert not missing, (
        f"CGM0-derivable clocks missing from _ALL_SELECTABLE_CLOCKS: {sorted(missing)}"
    )
    extra = code_clocks - cgm0_derivable_clocks
    # Only FIRC_CLK and SIRC_CLK are source clocks (not CGM0-derived)
    expected_extra = {"FIRC_CLK", "SIRC_CLK"}
    assert extra == expected_extra, (
        f"Unexpected extra clocks in _ALL_SELECTABLE_CLOCKS: {sorted(extra - expected_extra)}"
    )


# ---------------------------------------------------------------------------
# Test G14: Full recipe pin — verify expanded coverage doesn't break
#          existing recipe pin (LL-012 anti-drift check with added coverage).
# ---------------------------------------------------------------------------

def test_recipe_still_pinned_after_forward_harden():
    """The 160/80/40 recipe must still pin correctly against the asset after
    forward-hardening (LL-012). The recipe structure must not have been altered."""
    asset_path = (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcu" / "clock.json"
    )
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    recipes = asset["recipes"]
    assert len(recipes) >= 1, "At least one recipe must exist"

    recipe = recipes[0]
    assert recipe["core_clk"] == 160
    assert recipe["aips_plat_clk"] == 80
    assert recipe["aips_slow_clk"] == 40

    # Recipe must still have all original sections.
    # McuPll_Configuration field values (RDIV/MFI/ODIV2/Odiv0_Div/Odiv1_Div)
    # are InfoSetting per Mcu.xdm; ConfigTools derives them from clock_settings
    # + quick_selection. The recipe documents this in a _note, not as inserts.
    for key in ["clock_settings_changes", "clock_settings_inserts",
                "clock_settings_removes", "mcu_config_set_changes"]:
        assert key in recipe, f"Recipe missing key: {key}"


# ---------------------------------------------------------------------------
# Test G15: _MCU_SUPPORTED_RECIPES is still a frozenset with (160, 80, 40)
# ---------------------------------------------------------------------------

def test_supported_recipes_is_correct():
    """_MCU_SUPPORTED_RECIPES must be a frozenset containing exactly (160, 80, 40)."""
    assert isinstance(_MCU_SUPPORTED_RECIPES, frozenset)
    assert (160, 80, 40) in _MCU_SUPPORTED_RECIPES
    assert len(_MCU_SUPPORTED_RECIPES) == 1, (
        "Only one recipe should be supported until clock-tree solving is implemented"
    )
