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
# File:        test_adc_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-23
# Version:     0.1.0
# Description: Generality tests for the ADC module over ARBITRARY valid inputs the
#              four ADC E2E cases (ADC-001..004) do NOT exercise. These prove the
#              ADC module is asset/formula/Adc.xdm-driven and not case-fit: a
#              different unit+channel, a streaming group with a different sample
#              count, a BCTU SINGLE on a non-S10 channel, a LIST BCTU with a
#              non-2/2/4 partition + fifo2, and a multi-trigger BCTU (several
#              AdcHwTrigger + BctuInternalTrigger on one BCTU). Forward (Spec-first)
#              development, issues #30/#37.
# =================================================================================

"""ADC generality over arbitrary valid inputs (forward / Spec-first; issues #30/#37).

The four ADC E2E cases are regression verification only; these tests target the
*editable surface* the module supports, with inputs that are deliberately NOT the
case literals, so they fail if the module ever becomes fit to the four cases.

All domain values are grounded: channel literals come from the committed
adc.json device enum, the sampling values from the general
``round(t*clk/prescale)`` formula, the BCTU trigger-source tokens from the device
BCTU enum (BCTU_EMIOS_<0..2>_<0..22>), and the structure rules from Adc.xdm. No
value is invented here.
"""
import difflib
from functools import partial

import pytest

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_adc_set, _derive_adc_sampling_duration
from rtd_config.checks.static import run_static_checks
from rtd_config.intent import Intent
from rtd_config.modules.adc import AdcProvider
from rtd_config.modules.mcl import MclProvider
from tests.fixtures import copy_adc_fixture, resolved_adc_bundle

_BUNDLE = resolved_adc_bundle()
apply_adc_set = partial(apply_adc_set, bundle=_BUNDLE)
run_static_checks = partial(run_static_checks, bundle=_BUNDLE)
AdcProvider = partial(AdcProvider, _BUNDLE)
MclProvider = partial(MclProvider, _BUNDLE)


MEX_NAME = "Autombd_Test_Adc_S32K344.mex"


# ---------------------------------------------------------------------------
# Navigation helpers (independent of the E2E-case test helpers)
# ---------------------------------------------------------------------------

def _intent(payload: dict) -> Intent:
    return Intent.from_dict({"module": "adc", "action": "set", "payload": payload})


def _adc_cfg(doc):
    return doc.find_config_set("Adc")


def _config_set_struct(doc):
    cfg = _adc_cfg(doc)
    for el in cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "AdcConfigSet":
            return el
    return None


def _hw_unit_by_id(doc, unit_id):
    cfg = _adc_cfg(doc)
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwUnit":
            for child in el:
                if child.tag.endswith("struct"):
                    s = doc.find_child_setting(child, "AdcHwUnitId")
                    if s is not None and s.attrib.get("value") == unit_id:
                        return child
    return None


def _val(doc, el, name):
    s = doc.find_child_setting(el, name)
    return s.attrib.get("value") if s is not None else None


def _arrays(struct, name):
    return [el for el in struct if el.tag.endswith("array") and el.attrib.get("name") == name]


def _structs_in(struct, name):
    arrs = _arrays(struct, name)
    return [c for c in arrs[0] if c.tag.endswith("struct")] if arrs else []


def _groups(doc, unit):
    return _structs_in(unit, "AdcGroup")


def _channels(doc, unit):
    return _structs_in(unit, "AdcChannel")


def _group_setting(doc, group, name):
    return _val(doc, group, name)


def _hw_triggers(doc):
    cfgset = _config_set_struct(doc)
    out = []
    for el in cfgset:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwTrigger":
            out = [c for c in el if c.tag.endswith("struct")]
    return out


def _bctu_units(doc):
    cfgset = _config_set_struct(doc)
    out = []
    for el in cfgset:
        if el.tag.endswith("array") and el.attrib.get("name") == "BctuHwUnit":
            out = [c for c in el if c.tag.endswith("struct")]
    return out


def _internal_triggers(doc):
    out = []
    for bu in _bctu_units(doc):
        out += _structs_in(bu, "BctuInternalTrigger")
    return out


def _bctu_notifications(doc):
    out = []
    for bu in _bctu_units(doc):
        out += _structs_in(bu, "BctuAdcNotifications")
    return out


def _list_items(doc):
    out = []
    for bu in _bctu_units(doc):
        out += _structs_in(bu, "BctuListItems")
    return out


def _result_fifos(doc):
    out = []
    for bu in _bctu_units(doc):
        out += _structs_in(bu, "BctuResultFifos")
    return out


def _apply_and_validate(tmp_path, payload):
    """Apply a payload, write, reload, and statically validate. Returns the doc."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent(payload))
    assert not result.blocked, [d.code for d in result.diagnostics]
    doc.write(mex)
    reloaded = MexDocument.load(mex)
    static = run_static_checks(mex)
    assert static.status != "blocked", [d.code for d in static.diagnostics]
    return reloaded


# ===========================================================================
# Case A: a DIFFERENT unit + channel (ADC0 SINGLE interrupt on S15)
# ADC-001 uses ADC1 + VREFL/VREFH/P5; this drives the fixture's existing ADC0
# (update path) with S15, a channel none of the four cases touches.
# ===========================================================================

def test_adc0_single_interrupt_on_s15(tmp_path):
    payload = {
        "unit": "ADC0",
        "transfer": "interrupt",
        "sampling_time_us": 3,
        "groups": [
            {"trigger": "sw", "access": "single", "conv": "oneshot",
             "num_samples": 1, "channels": ["S15"]},
        ],
    }
    doc = _apply_and_validate(tmp_path, payload)
    unit = _hw_unit_by_id(doc, "ADC0")
    assert unit is not None
    assert _val(doc, unit, "AdcTransferType") == "ADC_INTERRUPT"
    channels = _channels(doc, unit)
    names = [_val(doc, c, "AdcChannelName") for c in channels]
    assert "S15_ChanNum39" in names, names
    groups = _groups(doc, unit)
    assert len(groups) == 1
    assert _group_setting(doc, groups[0], "AdcGroupAccessMode") == "ADC_ACCESS_MODE_SINGLE"
    # SINGLE access -> AdcStreamingNumSamples is exactly 1 (Adc.xdm L3410).
    assert _group_setting(doc, groups[0], "AdcStreamingNumSamples") == "1"


def test_adc0_sampling_3us_derives_general_formula(tmp_path):
    """3 us @160 MHz -> 480 @ prescale 1 (out), 240 @ prescale 2 (in [8,255])."""
    dur, pre = _derive_adc_sampling_duration(3e-6)
    assert (dur, pre) == (240, 2)
    doc = _apply_and_validate(tmp_path, {
        "unit": "ADC0", "transfer": "interrupt", "sampling_time_us": 3,
        "groups": [{"trigger": "sw", "access": "single", "conv": "oneshot",
                    "num_samples": 1, "channels": ["S15"]}],
    })
    unit = _hw_unit_by_id(doc, "ADC0")
    # AdcPrescale array carries the non-default prescaler 2.
    pre_arr = []
    for el in unit:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcPrescale":
            pre_arr = [i.attrib.get("value") for i in el if i.tag.endswith("setting")]
    assert pre_arr == ["2"], pre_arr
    # The derived duration is written to all three sampling bands.
    groups = _groups(doc, unit)
    cc = None
    for el in groups[0]:
        if el.tag.endswith("struct") and el.attrib.get("name") == "AdcGroupConversionConfiguration":
            cc = el
    assert cc is not None
    for band in ("AdcSamplingDuration0", "AdcSamplingDuration1", "AdcSamplingDuration2"):
        assert _val(doc, cc, band) == "240"


# ===========================================================================
# Case B: a STREAMING group with a DIFFERENT sample count (8)
# No ADC E2E case configures a streaming group; this proves AdcStreamingNumSamples
# is general (the value flows through, not a fixed literal) and the conv mode is
# coerced to CONTINUOUS for a SW streaming group (Adc.xdm streaming requires it).
# ===========================================================================

@pytest.mark.parametrize("num_samples", [2, 8, 16])
def test_streaming_group_arbitrary_sample_count(tmp_path, num_samples):
    payload = {
        "unit": "ADC0",
        "transfer": "interrupt",
        "sampling_time_us": 1,
        "groups": [
            {"trigger": "sw", "access": "streaming", "conv": "oneshot",
             "num_samples": num_samples, "channels": ["S15", "S16"]},
        ],
    }
    doc = _apply_and_validate(tmp_path, payload)
    unit = _hw_unit_by_id(doc, "ADC0")
    groups = _groups(doc, unit)
    assert len(groups) == 1
    g = groups[0]
    assert _group_setting(doc, g, "AdcGroupAccessMode") == "ADC_ACCESS_MODE_STREAMING"
    # A SW streaming oneshot group is coerced to CONTINUOUS conversion mode.
    assert _group_setting(doc, g, "AdcGroupConversionMode") == "ADC_CONV_MODE_CONTINUOUS"
    # The requested sample count flows through verbatim (general, not a literal).
    assert _group_setting(doc, g, "AdcStreamingNumSamples") == str(num_samples)


# ===========================================================================
# Case C: a BCTU SINGLE on a NON-S10 channel (ADC1, S15, eMIOS1 ch3)
# ADC-003 uses ADC1 + S10 + BCTU_EMIOS_2_15. This drives a different channel and a
# different trigger source to prove the BCTU SINGLE path is general.
# ===========================================================================

def test_bctu_single_non_s10_channel(tmp_path):
    payload = {
        "unit": "ADC1",
        "transfer": "interrupt",
        "sampling_time_us": 2,
        "groups": [
            {"trigger": "hw", "access": "single", "conv": "oneshot",
             "num_samples": 1, "channels": ["S15"]},
        ],
        "bctu": {
            "trigger_source": "BCTU_EMIOS_1_3",
            "mode": "single",
            "target": "ADC1",
            "channel": "S15",
            "destination": "data_reg",
            "new_data_notification": "Autombd_BctuNewDataGen",
        },
    }
    doc = _apply_and_validate(tmp_path, payload)
    # The single AdcHwTrigger_0 is repointed to the requested source.
    trigs = _hw_triggers(doc)
    assert len(trigs) == 1
    assert _val(doc, trigs[0], "AdcHwTrigSrc") == "BCTU_EMIOS_1_3"
    its = _internal_triggers(doc)
    assert len(its) == 1
    it = its[0]
    assert _val(doc, it, "BctuTriggerConversionMode") == "SINGLE"
    # SINGLE -> single-bit mask (ADC1 -> bit1 -> 2).
    assert _val(doc, it, "BctuAdcTargetMask") == "2"
    # The single-channel ref points at the unit's S15 AdcChannel struct.
    single_ref = _val(doc, it, "BctuAdcChannelSingle")
    assert single_ref is not None and single_ref.startswith("/Adc/Adc/AdcConfigSet/AdcHwUnit_")
    unit = _hw_unit_by_id(doc, "ADC1")
    names = [_val(doc, c, "AdcChannelName") for c in _channels(doc, unit)]
    assert "S15_ChanNum39" in names, names


# ===========================================================================
# Case D: a LIST BCTU with a NON-2/2/4 partition ([4,4]) + fifo2
# ADC-004 uses 8 channels, trigger_order [2,2,4], fifo1. This uses an 8-channel
# list partitioned [4,4] into fifo2 to prove the trigger-order partition and FIFO
# destination are general.
# ===========================================================================

def test_bctu_list_partition_4_4_fifo2(tmp_path):
    payload = {
        "units": [
            {"unit": "ADC1", "sampling_time_us": 5},
            {"unit": "ADC2", "sampling_time_us": 5},
        ],
        "transfer": "interrupt",
        "bctu": {
            "mode": "list",
            "targets": ["ADC1", "ADC2"],
            "list": ["S20", "S21", "S22", "S23", "VREFH", "VREFL", "P1", "P2"],
            "trigger_order": [4, 4],
            "destination": "fifo2",
            "trigger_source": "BCTU_EMIOS_2_15",
            "new_data_notification": "Autombd_BctuNewDataGen",
        },
    }
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent(payload))
    assert not result.blocked, [d.code for d in result.diagnostics]
    doc.write(mex)
    static = run_static_checks(mex)
    assert static.status != "blocked", [d.code for d in static.diagnostics]
    reloaded = MexDocument.load(mex)

    its = _internal_triggers(reloaded)
    assert len(its) == 1
    assert _val(reloaded, its[0], "BctuTriggerConversionMode") == "LIST"
    # 8-item list -> start index 0 < 8 (valid).
    assert _val(reloaded, its[0], "BctuConversionListStartIndex") == "0"

    items = _list_items(reloaded)
    assert len(items) == 8
    # trigger_order [4,4] -> the list halts (wait-on-trig) after item index 3 only
    # (the boundary of the first sub-list); the final item is BctuLastChannel.
    waits = [
        i for i, it in enumerate(items)
        if _val(reloaded, it, "BctuNextChannelWaitOnTrig") == "true"
    ]
    assert waits == [3], waits
    assert _val(reloaded, items[-1], "BctuLastChannel") == "true"
    assert all(_val(reloaded, it, "BctuLastChannel") == "false" for it in items[:-1])

    fifos = _result_fifos(reloaded)
    assert len(fifos) == 1
    assert _val(reloaded, fifos[0], "BctuResultFifoIndex") == "BCTU_FIFO2"


def test_plan_reuses_mcl_dma_ownership_for_mixed_unit_override():
    payload = {
        "units": [
            {"unit": "ADC1", "sampling_time_us": 3, "transfer": "interrupt"},
            {"unit": "ADC2", "sampling_time_us": 4, "transfer": "dma"},
        ],
        "transfer": "interrupt",
    }
    plan = AdcProvider().plan(_intent(payload))
    mcl_changes = [change for change in plan.changes if change.owner == "mcl"]

    assert mcl_changes == [MclProvider().dma_dependency("Adc")]


def test_plan_reuses_mcl_dma_ownership_for_arbitrary_fifo_dma():
    payload = {
        "unit": "ADC0",
        "transfer": "interrupt",
        "groups": [],
        "bctu": {
            "mode": "list",
            "targets": ["ADC0"],
            "list": ["S18", "S19"],
            "trigger_order": [2],
            "destination": "fifo2",
            "fifo_dma": True,
            "trigger_source": "BCTU_EMIOS_0_7",
        },
    }
    plan = AdcProvider().plan(_intent(payload))
    mcl_changes = [change for change in plan.changes if change.owner == "mcl"]

    assert mcl_changes == [MclProvider().dma_dependency("Adc")]


def test_plan_interrupt_without_fifo_dma_declares_no_mcl_write():
    payload = {
        "units": [
            {"unit": "ADC1", "sampling_time_us": 3},
            {"unit": "ADC2", "sampling_time_us": 4, "transfer": "interrupt"},
        ],
        "transfer": "interrupt",
        "bctu": {"fifo_dma": False},
    }
    plan = AdcProvider().plan(_intent(payload))

    assert [change for change in plan.changes if change.owner == "mcl"] == []


def test_single_unit_fifo_dma_plan_and_apply_share_mcl_ownership(tmp_path):
    payload = {
        "unit": "ADC0",
        "transfer": "interrupt",
        "sampling_time_us": 2,
        "groups": [
            {"trigger": "sw", "access": "single", "conv": "oneshot",
             "num_samples": 1, "channels": ["S18", "S19"]},
        ],
        "bctu": {
            "mode": "list",
            "targets": ["ADC0"],
            "list": ["S18", "S19"],
            "trigger_order": [2],
            "destination": "fifo2",
            "fifo_dma": True,
            "trigger_source": "BCTU_EMIOS_0_7",
        },
    }
    plan = AdcProvider().plan(_intent(payload))
    assert [change for change in plan.changes if change.owner == "mcl"] == [
        MclProvider().dma_dependency("Adc")
    ]

    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent(payload))
    assert not result.blocked, [d.code for d in result.diagnostics]
    assert result.changed_modules == ["adc", "mcl"]
    doc.write(mex)

    reloaded = MexDocument.load(mex)
    adc_cfg = reloaded.find_config_set("Adc")
    mcl_cfg = reloaded.find_config_set("Mcl")
    assert _val(reloaded, adc_cfg, "CtuEnableDmaTransferMode") == "true"
    assert _val(reloaded, mcl_cfg, "MclEnableDma") == "true"
    assert "quick_selection" not in mcl_cfg.attrib


# ===========================================================================
# Case E: a MULTI-TRIGGER BCTU (several AdcHwTrigger + BctuInternalTrigger)
# No ADC E2E case configures more than one hardware trigger. The S32K3 has a single
# BCTU peripheral (Adc.xdm L4180 caps the BctuHwUnit count), so several triggers are
# expressed as ONE BctuHwUnit holding several AdcHwTrigger + one BctuInternalTrigger
# each (Adc.xdm L4126 AdcHwTrigger MAP MIN=0/no max; L4374 BctuInternalTrigger MAP;
# L4418 trigger index unique; L4674 AdcIndex unique).
# ===========================================================================

def test_bctu_multi_trigger_two_triggers_one_unit(tmp_path):
    payload = {
        "unit": "ADC0",
        "transfer": "interrupt",
        "sampling_time_us": 1,
        "groups": [
            {"trigger": "sw", "access": "single", "conv": "oneshot",
             "num_samples": 1, "channels": ["S15", "S16"]},
        ],
        "bctu": {
            "triggers": [
                {"trigger_source": "BCTU_EMIOS_1_3", "target": "ADC0",
                 "channel": "S15", "new_data_notification": "Autombd_CbA"},
                {"trigger_source": "BCTU_EMIOS_1_4", "target": "ADC0",
                 "channel": "S16", "new_data_notification": "Autombd_CbB"},
            ],
        },
    }
    doc = _apply_and_validate(tmp_path, payload)

    # Two AdcHwTrigger structs, each with its own (distinct) source.
    trigs = _hw_triggers(doc)
    assert len(trigs) == 2
    sources = {_val(doc, t, "AdcHwTrigSrc") for t in trigs}
    assert sources == {"BCTU_EMIOS_1_3", "BCTU_EMIOS_1_4"}
    names = sorted(_val(doc, t, "Name") for t in trigs)
    assert names == ["AdcHwTrigger_0", "AdcHwTrigger_1"]

    # One BctuHwUnit holding two BctuInternalTrigger structs, each referencing a
    # DISTINCT AdcHwTrigger (Adc.xdm L4418 uniqueness).
    assert len(_bctu_units(doc)) == 1
    its = _internal_triggers(doc)
    assert len(its) == 2
    refs = sorted(_val(doc, it, "BctuTriggerSource") for it in its)
    assert refs == [
        "/Adc/Adc/AdcConfigSet/AdcHwTrigger_0",
        "/Adc/Adc/AdcConfigSet/AdcHwTrigger_1",
    ]
    # Each SINGLE trigger has a single-bit mask (ADC0 -> bit0 -> 1).
    assert all(_val(doc, it, "BctuTriggerConversionMode") == "SINGLE" for it in its)
    assert all(_val(doc, it, "BctuAdcTargetMask") == "1" for it in its)
    # Distinct single-channel refs (S15 then S16).
    single_refs = [_val(doc, it, "BctuAdcChannelSingle") for it in its]
    assert len(set(single_refs)) == 2

    # Both triggers target ADC0 -> exactly ONE BctuAdcNotifications (AdcIndex unique).
    notifs = _bctu_notifications(doc)
    assert len(notifs) == 1


def test_bctu_multi_trigger_duplicate_source_blocked(tmp_path):
    """Two triggers with the SAME source is rejected (Adc.xdm L4170 uniqueness)."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent({
        "unit": "ADC0", "transfer": "interrupt", "sampling_time_us": 1,
        "groups": [{"trigger": "sw", "access": "single", "conv": "oneshot",
                    "num_samples": 1, "channels": ["S15", "S16"]}],
        "bctu": {"triggers": [
            {"trigger_source": "BCTU_EMIOS_1_3", "target": "ADC0", "channel": "S15"},
            {"trigger_source": "BCTU_EMIOS_1_3", "target": "ADC0", "channel": "S16"},
        ]},
    }))
    assert result.blocked
    codes = [d.code for d in result.diagnostics]
    assert "adc_bctu_trigger_source_duplicate" in codes, codes


# ===========================================================================
# Negative generality: the broadened static checks guard arbitrary bad inputs
# ===========================================================================

def test_single_group_with_multi_sample_is_blocked(tmp_path):
    """A SINGLE-access group with AdcStreamingNumSamples != 1 is a static blocker."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent({
        "unit": "ADC1", "transfer": "interrupt", "sampling_time_us": 1,
        "groups": [{"trigger": "sw", "access": "single", "conv": "oneshot",
                    "num_samples": 1, "channels": ["S10"]}],
    }))
    doc.write(mex)
    raw = mex.read_text(encoding="utf-8").replace(
        '<setting name="AdcStreamingNumSamples" value="1"/>',
        '<setting name="AdcStreamingNumSamples" value="4"/>', 1,
    )
    mex.write_text(raw, encoding="utf-8")
    static = run_static_checks(mex)
    assert static.status == "blocked"
    assert "adc_group_single_num_samples_invalid" in [d.code for d in static.diagnostics]


def test_streaming_group_with_one_sample_is_blocked(tmp_path):
    """A STREAMING-access group with AdcStreamingNumSamples <= 1 is a static blocker."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent({
        "unit": "ADC1", "transfer": "interrupt", "sampling_time_us": 1,
        "groups": [{"trigger": "sw", "access": "single", "conv": "oneshot",
                    "num_samples": 1, "channels": ["S10"]}],
    }))
    doc.write(mex)
    raw = mex.read_text(encoding="utf-8").replace(
        '<setting name="AdcGroupAccessMode" value="ADC_ACCESS_MODE_SINGLE"/>',
        '<setting name="AdcGroupAccessMode" value="ADC_ACCESS_MODE_STREAMING"/>', 1,
    )
    mex.write_text(raw, encoding="utf-8")
    static = run_static_checks(mex)
    assert static.status == "blocked"
    assert "adc_group_streaming_num_samples_invalid" in [d.code for d in static.diagnostics]


# ===========================================================================
# Byte-faithfulness: a no-op spec reproduces the fixture bytes exactly, and
# every generality config re-applies byte-stably.
# ===========================================================================

def test_noop_spec_reproduces_bytes(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    original = mex.read_bytes()
    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent({}))
    assert not result.blocked
    assert result.changed_modules == []
    doc.write(mex)
    assert mex.read_bytes() == original


@pytest.mark.parametrize("payload", [
    {"unit": "ADC0", "transfer": "interrupt", "sampling_time_us": 3,
     "groups": [{"trigger": "sw", "access": "single", "conv": "oneshot",
                 "num_samples": 1, "channels": ["S15"]}]},
    {"unit": "ADC0", "transfer": "interrupt", "sampling_time_us": 1,
     "groups": [{"trigger": "sw", "access": "streaming", "conv": "oneshot",
                 "num_samples": 8, "channels": ["S15", "S16"]}]},
    {"unit": "ADC0", "transfer": "interrupt", "sampling_time_us": 1,
     "groups": [{"trigger": "sw", "access": "single", "conv": "oneshot",
                 "num_samples": 1, "channels": ["S15", "S16"]}],
     "bctu": {"triggers": [
         {"trigger_source": "BCTU_EMIOS_1_3", "target": "ADC0", "channel": "S15",
          "new_data_notification": "Autombd_CbA"},
         {"trigger_source": "BCTU_EMIOS_1_4", "target": "ADC0", "channel": "S16",
          "new_data_notification": "Autombd_CbB"},
     ]}},
])
def test_generality_configs_reapply_byte_stable(tmp_path, payload):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(payload))
    doc.write(mex)
    after_first = mex.read_bytes()

    doc2 = MexDocument.load(mex)
    apply_adc_set(doc2, _intent(payload))
    doc2.write(mex)
    after_second = mex.read_bytes()

    if after_first != after_second:
        diff = "\n".join(difflib.unified_diff(
            after_first.decode("utf-8").splitlines(),
            after_second.decode("utf-8").splitlines(),
            lineterm="", n=1,
        ))
        raise AssertionError("Re-apply changed bytes:\n" + diff[:2000])
