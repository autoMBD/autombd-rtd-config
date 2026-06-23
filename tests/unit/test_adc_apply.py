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
# File:        test_adc_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-19
# Version:     0.1.0
# Description: Unit/integration tests for ADC1 interrupt SW groups + watchdog
#              (RTD-MEX-ADC-001) on the Autombd_Test_Adc_S32K344 fixture.
# =================================================================================

"""ADC1 interrupt software-group + watchdog configuration (RTD-MEX-ADC-001).

The Autombd_Test_Adc_S32K344 fixture has a single AdcHwUnit_0 (AdcHwUnitId=ADC0,
ADC_INTERRUPT, one channel P0, one SW group) and one AdcHwConfiguration_0
(AdcHwConfiguredId=ADC0). ADC1 does NOT exist as a unit -> apply_adc_set must add
an AdcHwUnit for ADC1 and an AdcHwConfiguration entry for ADC1.

ADC-001 intent (the --spec payload):
  unit=ADC1, transfer=interrupt, sampling_time_us=1
  group0: trigger=sw, access=single, conv=oneshot, num_samples=1,
          notification=Autombd_AdcNotifi0, channels=[VREFL, S10]
  group1: trigger=sw, access=streaming, conv=continuous, num_samples=10,
          notification=Autombd_AdcNotifi1, channels=[VREFH, P5]
  watchdog: [{channel=P5, high=3000, low=20, notification=Autombd_AdcNotifiWdg}]

Ground truth (Adc.xdm + Adc_s32k344_mapbga257.epd, cached):
  - ADC source clock = 160 MHz; AdcPrescale in {1,2,4} default 1; SD in [8,255].
    1 us -> round(1e-6 * 160e6 / 1) = 160 at prescale 1.
  - VREFL=VREFL_ChanNum54 id54, S10=S10_ChanNum34 id34,
    VREFH=VREFH_ChanNum55 id55, P5=P5_ChanNum5 id5.
  - Adc.xdm L2877 INVALID: STREAMING + SW-trigger + ONESHOT is rejected, so the
    streaming group is CONTINUOUS.
  - Watchdog coherence: AutosarExt/AdcEnableWatchdogApi=true AND the unit's
    AdcHwConfiguration/WdgThresholdEnable=true; channel AdcEnableThresholds=true
    + AdcThresholdRegister ref + AdcWdogNotification.
"""
import difflib
import json
import pathlib

import pytest

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_adc_set
from rtd_config.intent import Intent
from rtd_config.modules.adc import AdcProvider
from tests.fixtures import copy_adc_fixture


MEX_NAME = "Autombd_Test_Adc_S32K344.mex"


# ---------------------------------------------------------------------------
# Intent helpers
# ---------------------------------------------------------------------------

def _adc001_payload() -> dict:
    return {
        "unit": "ADC1",
        "transfer": "interrupt",
        "sampling_time_us": 1,
        "groups": [
            {
                "name": "AdcGroup_0",
                "trigger": "sw",
                "access": "single",
                "conv": "oneshot",
                "num_samples": 1,
                "notification": "Autombd_AdcNotifi0",
                "channels": ["VREFL", "S10"],
            },
            {
                "trigger": "sw",
                "access": "streaming",
                "conv": "continuous",
                "num_samples": 10,
                "notification": "Autombd_AdcNotifi1",
                "channels": ["VREFH", "P5"],
            },
        ],
        "watchdog": [
            {"channel": "P5", "high": 3000, "low": 20, "notification": "Autombd_AdcNotifiWdg"},
        ],
    }


_SENTINEL = object()


def _intent(payload=_SENTINEL) -> Intent:
    if payload is _SENTINEL:
        payload = _adc001_payload()
    return Intent.from_dict({"module": "adc", "action": "set", "payload": payload})


# ---------------------------------------------------------------------------
# Document navigation helpers
# ---------------------------------------------------------------------------

def _adc_cfg(doc: MexDocument):
    return doc.find_config_set("Adc")


def _hw_unit_by_id(doc: MexDocument, unit_id: str):
    cfg = _adc_cfg(doc)
    if cfg is None:
        return None
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwUnit":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                s = doc.find_child_setting(child, "AdcHwUnitId")
                if s is not None and s.attrib.get("value") == unit_id:
                    return child
    return None


def _hw_config_by_id(doc: MexDocument, configured_id: str):
    cfg = _adc_cfg(doc)
    if cfg is None:
        return None
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwConfiguration":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                s = doc.find_child_setting(child, "AdcHwConfiguredId")
                if s is not None and s.attrib.get("value") == configured_id:
                    return child
    return None


def _child_arrays(struct, name: str):
    return [el for el in struct if el.tag.endswith("array") and el.attrib.get("name") == name]


def _groups(doc: MexDocument, unit):
    arrs = _child_arrays(unit, "AdcGroup")
    if not arrs:
        return []
    return [c for c in arrs[0] if c.tag.endswith("struct")]


def _channels(doc: MexDocument, unit):
    arrs = _child_arrays(unit, "AdcChannel")
    if not arrs:
        return []
    return [c for c in arrs[0] if c.tag.endswith("struct")]


def _threshold_controls(doc: MexDocument, unit):
    arrs = _child_arrays(unit, "AdcThresholdControl")
    if not arrs:
        return []
    return [c for c in arrs[0] if c.tag.endswith("struct")]


def _val(doc: MexDocument, el, name: str):
    s = doc.find_child_setting(el, name)
    return s.attrib.get("value") if s is not None else None


def _group_notification(doc: MexDocument, group):
    for el in group:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcNotification":
            for item in el:
                if item.tag.endswith("setting") and item.attrib.get("name") == "0":
                    return item.attrib.get("value")
    return None


def _group_channel_refs(doc: MexDocument, group):
    refs = []
    for el in group:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcGroupDefinition":
            for item in el:
                if item.tag.endswith("setting"):
                    refs.append(item.attrib.get("value"))
    return refs


def _group_sampling_durations(doc: MexDocument, group):
    for el in group.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "AdcGroupConversionConfiguration":
            return (
                _val(doc, el, "AdcSamplingDuration0"),
                _val(doc, el, "AdcSamplingDuration1"),
                _val(doc, el, "AdcSamplingDuration2"),
            )
    return (None, None, None)


def _changed_lines(before: bytes, after: bytes):
    b = before.decode("utf-8").splitlines(keepends=True)
    a = after.decode("utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(b, a, n=0, lineterm="")
    return [
        line for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


# ---------------------------------------------------------------------------
# Test: ADC1 unit selection / creation
# ---------------------------------------------------------------------------

def test_adc1_unit_created(tmp_path):
    """ADC1 does not exist in the fixture -> apply must add an AdcHwUnit for ADC1."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)

    result = apply_adc_set(doc, _intent())
    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "adc" in result.changed_modules

    unit = _hw_unit_by_id(doc, "ADC1")
    assert unit is not None, "AdcHwUnit with AdcHwUnitId=ADC1 must be created"
    assert _val(doc, unit, "AdcTransferType") == "ADC_INTERRUPT"


def test_adc0_unit_untouched(tmp_path):
    """The existing ADC0 unit must be left intact (narrow edit)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    adc0 = _hw_unit_by_id(doc, "ADC0")
    assert adc0 is not None, "ADC0 unit must still exist"
    assert _val(doc, adc0, "Name") == "AdcHwUnit_0"
    # ADC0 still has its single original channel
    assert len(_channels(doc, adc0)) == 1


# ---------------------------------------------------------------------------
# Test: sampling-time derivation 1us -> 160 @ prescale 1 (not a literal)
# ---------------------------------------------------------------------------

def test_sampling_duration_1us_is_160_at_prescale_1(tmp_path):
    """1 us at 160 MHz / prescale 1 => AdcSamplingDuration0/1/2 = 160."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    groups = _groups(doc, unit)
    assert len(groups) == 2
    for g in groups:
        sd0, sd1, sd2 = _group_sampling_durations(doc, g)
        assert sd0 == "160", f"AdcSamplingDuration0 must be 160, got {sd0}"
        assert sd1 == "160", f"AdcSamplingDuration1 must be 160, got {sd1}"
        assert sd2 == "160", f"AdcSamplingDuration2 must be 160, got {sd2}"


def test_sampling_derivation_helper_picks_smallest_prescaler():
    """Derivation is computed from clock+prescale, not a per-case literal.

    Verifies the production derive helper directly:
      - 1 us @160MHz: prescale 1 -> 160 (in [8,255]).
      - 4 us @160MHz: prescale 1 -> 640 (out), prescale 4 -> 160 (in range).
    """
    from rtd_config.backends.s32_mex.apply import _derive_adc_sampling_duration

    dur1, pre1 = _derive_adc_sampling_duration(1e-6)
    assert (dur1, pre1) == (160, 1)

    dur4, pre4 = _derive_adc_sampling_duration(4e-6)
    assert dur4 == 160 and pre4 == 4, (
        f"4 us should pick prescale 4 -> 160, got duration={dur4} prescale={pre4}"
    )


def test_sampling_out_of_range_rejected():
    """A sampling time that cannot land in [8,255] at any prescaler raises."""
    from rtd_config.backends.s32_mex.apply import _derive_adc_sampling_duration

    with pytest.raises(ValueError):
        # 100 us @160MHz: even prescale 4 -> 4000, far above 255.
        _derive_adc_sampling_duration(100e-6)


# ---------------------------------------------------------------------------
# Test: group construction + the streaming-not-oneshot rule
# ---------------------------------------------------------------------------

def test_group0_single_oneshot_sw(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    g0 = _groups(doc, unit)[0]
    assert _val(doc, g0, "AdcGroupAccessMode") == "ADC_ACCESS_MODE_SINGLE"
    assert _val(doc, g0, "AdcGroupConversionMode") == "ADC_CONV_MODE_ONESHOT"
    assert _val(doc, g0, "AdcGroupTriggSrc") == "ADC_TRIGG_SRC_SW"
    assert _val(doc, g0, "AdcStreamingNumSamples") == "1"
    assert _group_notification(doc, g0) == "Autombd_AdcNotifi0"


def test_group1_streaming_is_continuous_not_oneshot(tmp_path):
    """Adc.xdm L2877: STREAMING + SW + ONESHOT is INVALID.

    The streaming SW group must be CONTINUOUS even if the user wrote oneshot.
    """
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)

    # Even if the caller (mistakenly) asks for oneshot on the streaming group,
    # apply must coerce to CONTINUOUS to satisfy the vendor INVALID rule.
    payload = _adc001_payload()
    payload["groups"][1]["conv"] = "oneshot"
    apply_adc_set(doc, _intent(payload))

    unit = _hw_unit_by_id(doc, "ADC1")
    g1 = _groups(doc, unit)[1]
    assert _val(doc, g1, "AdcGroupAccessMode") == "ADC_ACCESS_MODE_STREAMING"
    assert _val(doc, g1, "AdcGroupConversionMode") == "ADC_CONV_MODE_CONTINUOUS", (
        "Streaming + SW group must be CONTINUOUS (Adc.xdm L2877)"
    )
    assert _val(doc, g1, "AdcStreamingNumSamples") == "10"
    assert _group_notification(doc, g1) == "Autombd_AdcNotifi1"


def test_group_ids_globally_unique(tmp_path):
    """AdcGroupId must be unique across ALL Hw Units (Adc.xdm L2996).

    The baseline ADC0 already uses AdcGroupId=0, so the new ADC1 groups must NOT
    reuse 0; they continue from the global max (1, 2).
    """
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    # Collect every AdcGroupId across all units.
    all_ids: list[str] = []
    adc_cfg = _adc_cfg(doc)
    for el in adc_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcGroup":
            for g in el:
                if g.tag.endswith("struct"):
                    all_ids.append(_val(doc, g, "AdcGroupId"))
    assert len(all_ids) == len(set(all_ids)), f"AdcGroupId not globally unique: {all_ids}"

    unit = _hw_unit_by_id(doc, "ADC1")
    new_ids = [_val(doc, g, "AdcGroupId") for g in _groups(doc, unit)]
    assert new_ids == ["1", "2"], (
        f"ADC1 group ids must continue from the global max (ADC0 uses 0); got {new_ids}"
    )


def test_struct_names_globally_unique(tmp_path):
    """AdcChannel/AdcGroup struct @name + Name must be unique across all units.

    Adc.xdm L2334/L2846 check the struct @name attribute globally. The baseline
    ADC0 uses AdcChannel_0 / AdcGroup_0 (@name="0"), so ADC1 must use higher
    indices (AdcChannel_1.. / AdcGroup_1..).
    """
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    adc_cfg = _adc_cfg(doc)
    for member in ("AdcChannel", "AdcGroup", "AdcThresholdControl"):
        struct_attr_names: list[str] = []
        name_settings: list[str] = []
        for el in adc_cfg.iter():
            if el.tag.endswith("array") and el.attrib.get("name") == member:
                for s in el:
                    if s.tag.endswith("struct"):
                        struct_attr_names.append(s.attrib.get("name"))
                        name_settings.append(_val(doc, s, "Name"))
        assert len(struct_attr_names) == len(set(struct_attr_names)), (
            f"{member} struct @name not globally unique: {struct_attr_names}"
        )
        assert len(name_settings) == len(set(name_settings)), (
            f"{member} Name setting not globally unique: {name_settings}"
        )


# ---------------------------------------------------------------------------
# Test: channel name->id resolution from the asset
# ---------------------------------------------------------------------------

def test_channels_resolved_from_asset(tmp_path):
    """VREFL/S10/VREFH/P5 short names resolve to full literals + correct ids."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    channels = _channels(doc, unit)
    by_name = {_val(doc, c, "AdcChannelName"): c for c in channels}

    assert "VREFL_ChanNum54" in by_name
    assert _val(doc, by_name["VREFL_ChanNum54"], "AdcChannelId") == "54"
    assert "S10_ChanNum34" in by_name
    assert _val(doc, by_name["S10_ChanNum34"], "AdcChannelId") == "34"
    assert "VREFH_ChanNum55" in by_name
    assert _val(doc, by_name["VREFH_ChanNum55"], "AdcChannelId") == "55"
    assert "P5_ChanNum5" in by_name
    assert _val(doc, by_name["P5_ChanNum5"], "AdcChannelId") == "5"


def test_channels_logical_ids_sequential(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    channels = _channels(doc, unit)
    logical = [_val(doc, c, "AdcLogicalChannelId") for c in channels]
    assert logical == [str(i) for i in range(len(channels))], (
        f"AdcLogicalChannelId must be sequential 0..N-1; got {logical}"
    )


def test_group_definition_refs_point_at_unit_channels(tmp_path):
    """Each group's AdcGroupDefinition refs point at this unit's channels."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    unit_name = _val(doc, unit, "Name")
    groups = _groups(doc, unit)

    g0_refs = _group_channel_refs(doc, groups[0])
    assert any(r.endswith("VREFL") or "VREFL" in r for r in g0_refs) or len(g0_refs) == 2
    for r in g0_refs:
        assert f"/AdcConfigSet/{unit_name}/" in r, (
            f"group0 channel ref {r} must reference unit {unit_name}"
        )

    g1_refs = _group_channel_refs(doc, groups[1])
    assert len(g1_refs) == 2
    for r in g1_refs:
        assert f"/AdcConfigSet/{unit_name}/" in r


def test_unknown_channel_rejected(tmp_path):
    """A channel name not in the device enum is rejected with an actionable code."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)

    payload = _adc001_payload()
    payload["groups"][0]["channels"] = ["S0", "S10"]  # S0 does NOT exist
    result = apply_adc_set(doc, _intent(payload))

    assert result.blocked, "Unknown channel S0 must block"
    codes = [d.code for d in result.diagnostics]
    assert any("adc_channel_not_in_device" in c for c in codes), (
        f"Expected adc_channel_not_in_device, got {codes}"
    )


# ---------------------------------------------------------------------------
# Test: watchdog threshold wiring + coherence flips
# ---------------------------------------------------------------------------

def test_threshold_control_entry_added(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    controls = _threshold_controls(doc, unit)
    assert len(controls) == 1, f"Expected 1 AdcThresholdControl, got {len(controls)}"
    tc = controls[0]
    assert _val(doc, tc, "AdcThresholdControlRegister") == "ADC_THRESHOLD_REG_0"
    assert _val(doc, tc, "AdcHighThreshold") == "3000"
    assert _val(doc, tc, "AdcLowThreshold") == "20"


def test_p5_channel_threshold_wiring(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    channels = _channels(doc, unit)
    p5 = next(c for c in channels if _val(doc, c, "AdcChannelName") == "P5_ChanNum5")

    assert _val(doc, p5, "AdcEnableThresholds") == "true"
    assert _val(doc, p5, "AdcWdogNotification") == "Autombd_AdcNotifiWdg"
    # AdcThresholdRegister ref must be present, non-empty, and reference this unit.
    ref_arrays = _child_arrays(p5, "AdcThresholdRegister")
    assert ref_arrays, "P5 must have an AdcThresholdRegister array"
    ref_items = [
        item.attrib.get("value")
        for item in ref_arrays[0]
        if item.tag.endswith("setting")
    ]
    assert ref_items and ref_items[0], "AdcThresholdRegister ref must be non-empty"
    unit_name = _val(doc, unit, "Name")
    assert unit_name in ref_items[0], (
        f"AdcThresholdRegister ref must contain the unit name {unit_name} "
        f"(Adc.xdm L2792), got {ref_items[0]}"
    )


def test_non_watchdog_channels_keep_thresholds_false(tmp_path):
    """Channels without a watchdog request keep AdcEnableThresholds=false."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    unit = _hw_unit_by_id(doc, "ADC1")
    channels = _channels(doc, unit)
    for c in channels:
        if _val(doc, c, "AdcChannelName") == "P5_ChanNum5":
            continue
        assert _val(doc, c, "AdcEnableThresholds") == "false", (
            f"Channel {_val(doc, c, 'AdcChannelName')} must keep thresholds disabled"
        )


def test_global_watchdog_api_flipped(tmp_path):
    """AutosarExt/AdcEnableWatchdogApi must flip false->true (Adc.xdm L2758)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    adc_cfg = _adc_cfg(doc)
    wdg = doc.find_child_setting(adc_cfg, "AdcEnableWatchdogApi")
    assert wdg is not None and wdg.attrib.get("value") == "true", (
        "AdcEnableWatchdogApi must be true when a watchdog is requested"
    )


def test_adc1_hw_configuration_added_with_interrupt_and_wdg(tmp_path):
    """ADC1 needs its own AdcHwConfiguration with NormalInterrupt + WdgThreshold enabled."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    hw = _hw_config_by_id(doc, "ADC1")
    assert hw is not None, "An AdcHwConfiguration entry for ADC1 must be added"
    assert _val(doc, hw, "AdcNormalInterruptEnable") == "true", (
        "Interrupt transfer requires AdcNormalInterruptEnable=true"
    )
    assert _val(doc, hw, "WdgThresholdEnable") == "true", (
        "Channel thresholds require the unit's WdgThresholdEnable=true (Adc.xdm L2761)"
    )


def test_adc0_hw_configuration_untouched(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent())

    hw0 = _hw_config_by_id(doc, "ADC0")
    assert hw0 is not None
    # The ADC0 entry stays at its baseline WdgThresholdEnable=false.
    assert _val(doc, hw0, "WdgThresholdEnable") == "false"


# ---------------------------------------------------------------------------
# Test: narrow byte-faithful write (no-op spec reproduces bytes)
# ---------------------------------------------------------------------------

def test_noop_spec_reproduces_bytes(tmp_path):
    """An empty ADC spec is a no-op and reproduces the file byte-for-byte."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent({}))  # empty payload -> nothing requested
    assert not result.blocked
    assert result.changed_modules == [], "No-op spec must not change any module"
    doc.write(mex)

    assert mex.read_bytes() == original, "No-op spec must reproduce bytes exactly"


def test_xml_declaration_preserved(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent())
    doc.write(mex)

    first_line = mex.read_bytes().decode("utf-8").splitlines()[0]
    assert first_line == '<?xml version="1.0" encoding= "UTF-8" ?>', (
        f"XML declaration must be byte-preserved, got: {first_line!r}"
    )


def test_written_file_reloads_well_formed(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent())
    doc.write(mex)

    reloaded = MexDocument.load(mex)
    unit = _hw_unit_by_id(reloaded, "ADC1")
    assert unit is not None
    assert len(_groups(reloaded, unit)) == 2
    assert len(_channels(reloaded, unit)) == 4  # VREFL, S10, VREFH, P5


def test_adc_config_set_quick_selection_removed(tmp_path):
    """The Adc config_set carries quick_selection=defaultConfig; it must be cleared.

    Otherwise ConfigTools treats the tree as 'use default' and reverts the edits.
    """
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent())
    doc.write(mex)

    import re
    content = mex.read_text(encoding="utf-8")
    m = re.search(r'config_set\s+name="Adc"[^>]*>', content)
    assert m is not None
    assert "quick_selection" not in m.group(0), (
        f"Adc config_set still carries quick_selection: {m.group(0)}"
    )


# ---------------------------------------------------------------------------
# Test: plan() declares the ADC-owned change
# ---------------------------------------------------------------------------

def test_plan_declares_adc_change():
    plan = AdcProvider().plan(_intent())
    adc_changes = [c for c in plan.changes if c.owner == "adc"]
    assert len(adc_changes) >= 1, f"No adc-owned change in plan: {plan.to_dict()}"
    assert AdcProvider().name == "adc"


def test_plan_empty_payload_no_changes():
    plan = AdcProvider().plan(_intent({}))
    assert plan.changes == []


# ---------------------------------------------------------------------------
# Test: adc.json asset schema + code==asset pin (LL-012)
# ---------------------------------------------------------------------------

def _asset_path():
    return (
        pathlib.Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "adc" / "adc.json"
    )


def test_adc_json_asset_schema():
    asset = json.loads(_asset_path().read_text(encoding="utf-8"))

    # Channel map and the specific ids ADC-001 needs.
    cmap = asset["channel_name_to_id"]
    assert cmap["VREFL_ChanNum54"] == 54
    assert cmap["VREFH_ChanNum55"] == 55
    assert cmap["S10_ChanNum34"] == 34
    assert cmap["P5_ChanNum5"] == 5
    # No S0..S7.
    assert not any(k.startswith("S0_") or k.startswith("S1_ChanNum") and k == "S1_ChanNum1" for k in cmap)

    # Short-name aliases.
    aliases = asset["channel_short_name_aliases"]
    assert aliases["VREFL"] == "VREFL_ChanNum54"
    assert aliases["S10"] == "S10_ChanNum34"
    assert aliases["P5"] == "P5_ChanNum5"

    # Sampling derivation params.
    sd = asset["sampling_derivation"]
    assert sd["adc_source_clock_hz"] == 160000000
    assert sd["allowed_prescalers"] == [1, 2, 4]
    assert sd["sampling_duration_min"] == 8
    assert sd["sampling_duration_max"] == 255

    # Enum domains.
    enums = asset["enum_domains"]
    assert "ADC_CONV_MODE_CONTINUOUS" in enums["AdcGroupConversionMode"]
    assert "ADC_ACCESS_MODE_STREAMING" in enums["AdcGroupAccessMode"]

    # Watchdog gating field names.
    wd = asset["watchdog"]
    assert wd["global_watchdog_api_setting"] == "AdcEnableWatchdogApi"
    assert wd["unit_wdg_threshold_enable_setting"] == "WdgThresholdEnable"
    assert wd["default_threshold_register"] == "ADC_THRESHOLD_REG_0"


def test_adc_json_matches_apply_code_literals():
    """Pin the apply.py constants against adc.json (LL-012).

    Any drift between the committed asset and the runtime-loaded values fails
    the gate. apply_adc_set loads the asset at runtime, so this also proves the
    loader path (not a doc-only asset).
    """
    from rtd_config.backends.s32_mex.apply import (
        _load_adc_asset,
        _ADC_SAMPLING_CLOCK_HZ,
        _ADC_ALLOWED_PRESCALERS,
        _ADC_SD_MIN,
        _ADC_SD_MAX,
    )

    asset = _load_adc_asset()
    sd = asset["sampling_derivation"]
    assert _ADC_SAMPLING_CLOCK_HZ == sd["adc_source_clock_hz"]
    assert list(_ADC_ALLOWED_PRESCALERS) == sd["allowed_prescalers"]
    assert _ADC_SD_MIN == sd["sampling_duration_min"]
    assert _ADC_SD_MAX == sd["sampling_duration_max"]
