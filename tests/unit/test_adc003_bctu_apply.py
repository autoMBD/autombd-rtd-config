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
# File:        test_adc003_bctu_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-22
# Version:     0.1.0
# Description: Unit tests for the ADC1 BCTU single-hardware-trigger configuration
#              (RTD-MEX-ADC-003) on the Autombd_Test_Adc_S32K344 fixture.
# =================================================================================

"""ADC1 BCTU single hardware-trigger configuration (RTD-MEX-ADC-003).

The prompt: configure the Adc Hardware Unit for ADC1, sampling time 2 us, add a
BCTU hardware trigger sourced from eMIOS2 channel 15 (BCTU_EMIOS_2_15), conversion
mode SINGLE, triggering ADC1 channel S10, conversion result stored in the BCTU
data register, register a new-data callback (Autombd_BctuNewDataNotifi), and add a
high/low watchdog (3000/20) on S10 with callback Autombd_AdcNotifiWdg.

ADC1 does NOT exist in the fixture -> apply must ADD an AdcHwUnit for ADC1 (the
add-new-unit path, like ADC-001), then wire the BCTU subtree.

VERIFIED GROUND TRUTH (Adc.xdm + Adc_s32k344_mapbga257.epd, cached):
  - Gating: AdcGeneral/AdcHwTriggerApi=true (any HW-trigger group);
    AutosarExt/AdcEnableCtuControlModeApi=true (gates BctuHwUnit editability,
    Adc.xdm L4182/L4186/L4203); AutosarExt/AdcEnableWatchdogApi=true (watchdog).
  - AdcHwTrigger_0 already exists in the fixture -> repoint AdcHwTrigSrc to
    BCTU_EMIOS_2_15 (valid .epd token; BCTU_EMIOS_2_0..22 exist).
  - BctuHwUnit field order (Adc.xdm L4207..): Name, BctuHwUnitId, BctuLogicalUnitId,
    BctuLowPowerMode=false, BctuGlobalHwTriggers=true, BctuNewDataDMAEnableMask=0,
    BctuFifoDmaRawData=false, BctuTriggerNotification=NULL_PTR, BctuInternalTrigger[],
    BctuAdcNotifications[], BctuListItems(empty), BctuResultFifos(empty).
  - BctuInternalTrigger field order (Adc.xdm L4399..): BctuTriggerSource (ASPath ref
    -> AdcHwTrigger_0), BctuTriggerLoop=false, BctuDataDestination=BCTU_ADC_DATA_REG
    (.epd enum), BctuHwTriggerEnable=true, BctuTriggerConversionMode=SINGLE (xdm L4504),
    BctuAdcTargetMask=2 (bit1 = ADC1 only, 1<<1; default 1), BctuAdcChannelSingle
    (ASPath ref -> ADC1's AdcChannel_<N> whose AdcChannelName=S10_ChanNum34),
    BctuConversionListStartIndex=0.
  - BctuAdcNotifications field order (Adc.xdm L4657..): BctuAdcNotificationsAdcIndex
    (ASPath ref -> ADC1 unit), BctuAdcNewDataNotification=Autombd_BctuNewDataNotifi,
    BctuDataOverrunNotification=NULL_PTR, BctuListLastConversionNotification=NULL_PTR.
  - HW group: AdcGroupTriggSrc=ADC_TRIGG_SRC_HW,
    AdcGroupHwTriggerSource=/Adc/Adc/AdcConfigSet/AdcHwTrigger_0.
  - 2 us @160 MHz: prescale1->320 (out of [8,255]), prescale2->160 (in range);
    AdcPrescale encoded as 2.
"""
import difflib

import pytest

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_adc_set, _derive_adc_sampling_duration
from rtd_config.intent import Intent
from rtd_config.modules.adc import AdcProvider
from tests.fixtures import copy_adc_fixture


MEX_NAME = "Autombd_Test_Adc_S32K344.mex"
TRIG_REF = "/Adc/Adc/AdcConfigSet/AdcHwTrigger_0"


# ---------------------------------------------------------------------------
# Intent helper (the ADC-003 --spec a cold agent authors)
# ---------------------------------------------------------------------------

def _adc003_payload() -> dict:
    return {
        "unit": "ADC1",
        "transfer": "interrupt",
        "sampling_time_us": 2,
        "groups": [
            {
                "trigger": "hw",
                "access": "single",
                "conv": "oneshot",
                "num_samples": 1,
                "channels": ["S10"],
            }
        ],
        "watchdog": [
            {"channel": "S10", "high": 3000, "low": 20,
             "notification": "Autombd_AdcNotifiWdg"},
        ],
        "bctu": {
            "trigger_source": "BCTU_EMIOS_2_15",
            "mode": "single",
            "target": "ADC1",
            "channel": "S10",
            "destination": "data_reg",
            "new_data_notification": "Autombd_BctuNewDataNotifi",
        },
    }


def _intent(payload: dict) -> Intent:
    return Intent.from_dict({"module": "adc", "action": "set", "payload": payload})


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _adc_cfg(doc):
    return doc.find_config_set("Adc")


def _adc_config_set_struct(doc):
    """Return the inner AdcConfigSet struct (holds AdcHwTrigger + BctuHwUnit)."""
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


def _hw_config_by_id(doc, configured_id):
    cfg = _adc_cfg(doc)
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwConfiguration":
            for child in el:
                if child.tag.endswith("struct"):
                    s = doc.find_child_setting(child, "AdcHwConfiguredId")
                    if s is not None and s.attrib.get("value") == configured_id:
                        return child
    return None


def _val(doc, el, name):
    s = doc.find_child_setting(el, name)
    return s.attrib.get("value") if s is not None else None


def _child_arrays(struct, name):
    return [el for el in struct if el.tag.endswith("array") and el.attrib.get("name") == name]


def _groups(doc, unit):
    arrs = _child_arrays(unit, "AdcGroup")
    return [c for c in arrs[0] if c.tag.endswith("struct")] if arrs else []


def _channels(doc, unit):
    arrs = _child_arrays(unit, "AdcChannel")
    return [c for c in arrs[0] if c.tag.endswith("struct")] if arrs else []


def _bctu_units(doc):
    cfgset = _adc_config_set_struct(doc)
    out = []
    for el in cfgset:
        if el.tag.endswith("array") and el.attrib.get("name") == "BctuHwUnit":
            out = [c for c in el if c.tag.endswith("struct")]
    return out


def _first_struct(parent, array_name):
    for el in parent:
        if el.tag.endswith("array") and el.attrib.get("name") == array_name:
            for c in el:
                if c.tag.endswith("struct"):
                    return c
    return None


def _adc_hw_trigger_0(doc):
    cfgset = _adc_config_set_struct(doc)
    for el in cfgset:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwTrigger":
            for c in el:
                if c.tag.endswith("struct"):
                    name = doc.find_child_setting(c, "Name")
                    if name is not None and name.attrib.get("value") == "AdcHwTrigger_0":
                        return c
    return None


# ---------------------------------------------------------------------------
# Sampling derivation: 2 us -> 160 @ prescale 2
# ---------------------------------------------------------------------------

def test_sampling_2us_is_160_at_prescale_2():
    """2 us @160 MHz: prescale1->320 (out), prescale2->160 (in [8,255])."""
    dur, pre = _derive_adc_sampling_duration(2e-6)
    assert (dur, pre) == (160, 2)


def test_unit_prescale_encoded_as_2(tmp_path):
    """The created ADC1 unit must encode AdcPrescale=2 so 2 us is realized."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    unit = _hw_unit_by_id(doc, "ADC1")
    pre = []
    for el in unit:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcPrescale":
            pre = [i.attrib.get("value") for i in el if i.tag.endswith("setting")]
    assert pre == ["2"], f"AdcPrescale must be [2] for 2 us, got {pre}"


# ---------------------------------------------------------------------------
# Gating flags
# ---------------------------------------------------------------------------

def test_hw_trigger_api_flipped(tmp_path):
    """AdcGeneral/AdcHwTriggerApi must flip false->true for a HW-trigger group."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    cfg = _adc_cfg(doc)
    s = doc.find_child_setting(cfg, "AdcHwTriggerApi")
    assert s is not None and s.attrib.get("value") == "true"


def test_ctu_control_mode_api_flipped(tmp_path):
    """AutosarExt/AdcEnableCtuControlModeApi must flip false->true (gates BctuHwUnit)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    cfg = _adc_cfg(doc)
    s = doc.find_child_setting(cfg, "AdcEnableCtuControlModeApi")
    assert s is not None and s.attrib.get("value") == "true"


def test_ctu_dma_transfer_mode_left_false(tmp_path):
    """ADC-003 has no FIFO DMA -> CtuEnableDmaTransferMode stays false."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    cfg = _adc_cfg(doc)
    s = doc.find_child_setting(cfg, "CtuEnableDmaTransferMode")
    assert s is not None and s.attrib.get("value") == "false"


def test_global_watchdog_api_flipped(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    cfg = _adc_cfg(doc)
    s = doc.find_child_setting(cfg, "AdcEnableWatchdogApi")
    assert s is not None and s.attrib.get("value") == "true"


# ---------------------------------------------------------------------------
# AdcHwTrigger_0 repoint
# ---------------------------------------------------------------------------

def test_adc_hw_trigger_source_repointed(tmp_path):
    """The existing AdcHwTrigger_0 must have its AdcHwTrigSrc set to BCTU_EMIOS_2_15."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    trig = _adc_hw_trigger_0(doc)
    assert trig is not None, "AdcHwTrigger_0 must still exist"
    assert _val(doc, trig, "AdcHwTrigSrc") == "BCTU_EMIOS_2_15"
    # The trigger struct keeps exactly its two settings (Name + AdcHwTrigSrc).
    assert _val(doc, trig, "Name") == "AdcHwTrigger_0"


def test_unknown_bctu_trigger_source_rejected(tmp_path):
    """A trigger source token not in the device BCTU enum is rejected."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    payload = _adc003_payload()
    payload["bctu"]["trigger_source"] = "BCTU_EMIOS_9_99"  # not a device token
    result = apply_adc_set(doc, _intent(payload))
    assert result.blocked, "Unknown BCTU trigger source must block"
    codes = [d.code for d in result.diagnostics]
    assert any("bctu_trigger_source" in c for c in codes), codes


# ---------------------------------------------------------------------------
# BctuHwUnit construction
# ---------------------------------------------------------------------------

def test_bctu_hw_unit_created(tmp_path):
    """The empty BctuHwUnit array becomes one populated BctuHwUnit_0 struct."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    units = _bctu_units(doc)
    assert len(units) == 1, f"Expected exactly 1 BctuHwUnit, got {len(units)}"
    bu = units[0]
    assert _val(doc, bu, "Name") == "BctuHwUnit_0"
    assert _val(doc, bu, "BctuHwUnitId") == "0"
    assert _val(doc, bu, "BctuLogicalUnitId") == "0"
    assert _val(doc, bu, "BctuLowPowerMode") == "false"
    assert _val(doc, bu, "BctuGlobalHwTriggers") == "true"
    assert _val(doc, bu, "BctuNewDataDMAEnableMask") == "0"
    assert _val(doc, bu, "BctuFifoDmaRawData") == "false"
    assert _val(doc, bu, "BctuTriggerNotification") == "NULL_PTR"


def test_bctu_internal_trigger_wired(tmp_path):
    """BctuInternalTrigger_0: source ref, SINGLE mode, target mask 2, channel ref."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    bu = _bctu_units(doc)[0]
    it = _first_struct(bu, "BctuInternalTrigger")
    assert it is not None, "BctuInternalTrigger_0 must exist"
    assert _val(doc, it, "Name") == "BctuInternalTrigger_0"
    # Trigger source is the AdcHwTrigger_0 instance ASPath ref (not a raw token).
    assert _val(doc, it, "BctuTriggerSource") == TRIG_REF
    assert _val(doc, it, "BctuTriggerLoop") == "false"
    assert _val(doc, it, "BctuDataDestination") == "BCTU_ADC_DATA_REG"
    assert _val(doc, it, "BctuHwTriggerEnable") == "true"
    assert _val(doc, it, "BctuTriggerConversionMode") == "SINGLE"
    # ADC1 only -> bit1 -> mask 2 (1<<1).
    assert _val(doc, it, "BctuAdcTargetMask") == "2"
    assert _val(doc, it, "BctuConversionListStartIndex") == "0"


def test_bctu_channel_single_refs_adc1_s10(tmp_path):
    """BctuAdcChannelSingle must reference ADC1's actual S10 AdcChannel struct."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))

    unit = _hw_unit_by_id(doc, "ADC1")
    unit_name = _val(doc, unit, "Name")
    # Find the AdcChannel struct on ADC1 whose AdcChannelName is S10.
    s10 = next(
        c for c in _channels(doc, unit)
        if _val(doc, c, "AdcChannelName") == "S10_ChanNum34"
    )
    s10_struct_name = _val(doc, s10, "Name")  # e.g. AdcChannel_<N>
    expected_ref = f"/Adc/Adc/AdcConfigSet/{unit_name}/{s10_struct_name}"

    bu = _bctu_units(doc)[0]
    it = _first_struct(bu, "BctuInternalTrigger")
    ref = _val(doc, it, "BctuAdcChannelSingle")
    assert ref == expected_ref, (
        f"BctuAdcChannelSingle must reference ADC1's real S10 channel struct "
        f"{expected_ref}, got {ref}"
    )
    # It must NOT contain a literal placeholder.
    assert "<N>" not in ref


def test_bctu_adc_notifications_wired(tmp_path):
    """BctuAdcNotifications_0: AdcIndex ref -> ADC1 unit, new-data notification set."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))

    unit = _hw_unit_by_id(doc, "ADC1")
    unit_name = _val(doc, unit, "Name")
    expected_index_ref = f"/Adc/Adc/AdcConfigSet/{unit_name}"

    bu = _bctu_units(doc)[0]
    nt = _first_struct(bu, "BctuAdcNotifications")
    assert nt is not None, "BctuAdcNotifications_0 must exist"
    assert _val(doc, nt, "Name") == "BctuAdcNotifications_0"
    assert _val(doc, nt, "BctuAdcNotificationsAdcIndex") == expected_index_ref
    assert _val(doc, nt, "BctuAdcNewDataNotification") == "Autombd_BctuNewDataNotifi"
    assert _val(doc, nt, "BctuDataOverrunNotification") == "NULL_PTR"
    assert _val(doc, nt, "BctuListLastConversionNotification") == "NULL_PTR"


def test_bctu_list_and_fifo_arrays_empty(tmp_path):
    """BctuListItems / BctuResultFifos stay empty for a single (non-list/FIFO) trigger."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    bu = _bctu_units(doc)[0]
    for arr_name in ("BctuListItems", "BctuResultFifos"):
        arrs = _child_arrays(bu, arr_name)
        assert arrs, f"{arr_name} array must be present"
        structs = [c for c in arrs[0] if c.tag.endswith("struct")]
        assert structs == [], f"{arr_name} must be empty for ADC-003"


# ---------------------------------------------------------------------------
# HW-triggered group on ADC1
# ---------------------------------------------------------------------------

def test_group_is_hw_triggered(tmp_path):
    """The ADC1 group is a HW-triggered single one-shot group referencing AdcHwTrigger_0."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    unit = _hw_unit_by_id(doc, "ADC1")
    g = _groups(doc, unit)[0]
    assert _val(doc, g, "AdcGroupTriggSrc") == "ADC_TRIGG_SRC_HW"
    assert _val(doc, g, "AdcGroupHwTriggerSource") == TRIG_REF
    assert _val(doc, g, "AdcGroupAccessMode") == "ADC_ACCESS_MODE_SINGLE"
    assert _val(doc, g, "AdcGroupConversionMode") == "ADC_CONV_MODE_ONESHOT"


def test_bctu_hw_group_conversion_type_is_injected(tmp_path):
    """A BCTU/CTU-sourced HW-triggered group MUST be ADC_CONV_TYPE_INJECTED.

    Adc.xdm AdcGroupConversionType INVALID rule (L2942-2943): when
    AdcGroupTriggSrc=ADC_TRIGG_SRC_HW and the AdcHwTrigger source's AdcHwTrigSrc
    is a BCTU token (not *EXT_TRIG*), NORMAL is rejected with SEVERE
    "If Hardware Trigger Source comes from BCTU, the conversion type must be
    ADC_CONV_TYPE_INJECTED." The corollary L2952-2953 demands
    AdcUseHardwareNormalGroups for the NORMAL case. Emitting INJECTED clears
    BOTH; the group is oneshot with no priority, so the injected-only-ONESHOT /
    priority-255 rule (L2946-2947) is satisfied, and the add-path
    AdcHwConfiguration already sets AdcInjectedInterruptEnable=true (L2959-2961).
    """
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    unit = _hw_unit_by_id(doc, "ADC1")
    g = _groups(doc, unit)[0]
    # The distinct AdcGroupConversionType setting (not AdcGroupConversionMode).
    assert _val(doc, g, "AdcGroupConversionType") == "ADC_CONV_TYPE_INJECTED"
    # The conversion MODE stays one-shot (a separate setting).
    assert _val(doc, g, "AdcGroupConversionMode") == "ADC_CONV_MODE_ONESHOT"
    # No priority is emitted (empty array), so node:exists(AdcGroupPriority) is
    # false and the injected priority-255 rule does not fire.
    prio = _child_arrays(g, "AdcGroupPriority")
    assert prio, "AdcGroupPriority array must be present"
    assert [c for c in prio[0]] == [], "AdcGroupPriority must stay empty for ADC-003"


def test_hw_group_empty_trig_signal_timer_arrays(tmp_path):
    """A single HW trigger leaves AdcHwTrigSignal / AdcHwTrigTimer empty."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    unit = _hw_unit_by_id(doc, "ADC1")
    g = _groups(doc, unit)[0]
    for arr_name in ("AdcHwTrigSignal", "AdcHwTrigTimer"):
        arrs = _child_arrays(g, arr_name)
        assert arrs, f"{arr_name} must be present"
        items = [c for c in arrs[0]]
        assert items == [], f"{arr_name} must be empty for a single HW trigger"


# ---------------------------------------------------------------------------
# S10 watchdog wiring + coherence
# ---------------------------------------------------------------------------

def test_s10_watchdog_wired(tmp_path):
    """The S10 channel carries the watchdog (thresholds + ref + notification)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))

    unit = _hw_unit_by_id(doc, "ADC1")
    s10 = next(
        c for c in _channels(doc, unit)
        if _val(doc, c, "AdcChannelName") == "S10_ChanNum34"
    )
    assert _val(doc, s10, "AdcEnableThresholds") == "true"
    assert _val(doc, s10, "AdcWdogNotification") == "Autombd_AdcNotifiWdg"
    ref_arrays = _child_arrays(s10, "AdcThresholdRegister")
    assert ref_arrays, "S10 must have an AdcThresholdRegister array"
    refs = [i.attrib.get("value") for i in ref_arrays[0] if i.tag.endswith("setting")]
    assert refs and refs[0], "AdcThresholdRegister ref must be non-empty"
    unit_name = _val(doc, unit, "Name")
    assert unit_name in refs[0]


def test_threshold_control_added(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    unit = _hw_unit_by_id(doc, "ADC1")
    arrs = _child_arrays(unit, "AdcThresholdControl")
    controls = [c for c in arrs[0] if c.tag.endswith("struct")] if arrs else []
    assert len(controls) == 1
    tc = controls[0]
    assert _val(doc, tc, "AdcHighThreshold") == "3000"
    assert _val(doc, tc, "AdcLowThreshold") == "20"


def test_adc1_hw_configuration_added(tmp_path):
    """ADC1 needs its AdcHwConfiguration: NormalInterrupt + WdgThreshold enabled."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    hw = _hw_config_by_id(doc, "ADC1")
    assert hw is not None, "An AdcHwConfiguration entry for ADC1 must be added"
    assert _val(doc, hw, "AdcNormalInterruptEnable") == "true"
    assert _val(doc, hw, "WdgThresholdEnable") == "true"


# ---------------------------------------------------------------------------
# ADC0 + the existing tree stay intact
# ---------------------------------------------------------------------------

def test_adc0_untouched(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc003_payload()))
    adc0 = _hw_unit_by_id(doc, "ADC0")
    assert adc0 is not None
    assert _val(doc, adc0, "Name") == "AdcHwUnit_0"
    assert len(_channels(doc, adc0)) == 1


def test_sw_triggered_group_stays_normal(tmp_path):
    """A SW-triggered group MUST keep AdcGroupConversionType=ADC_CONV_TYPE_NORMAL.

    Scope guard for the INJECTED change: only BCTU/CTU-HW-triggered groups become
    INJECTED. The ADC-001/002 software-triggered path must remain NORMAL (and so
    byte-identical / S32DS-green). Here a SW streaming-continuous group is applied
    to ADC0 (the update path); it must not be promoted to INJECTED.
    """
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    sw_payload = {
        "unit": "ADC0",
        "transfer": "dma",
        "sampling_time_us": 4,
        "groups": [
            {"trigger": "sw", "access": "streaming", "conv": "continuous",
             "num_samples": 10, "notification": "Autombd_AdcNotifiDma",
             "channels": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"]},
        ],
    }
    apply_adc_set(doc, _intent(sw_payload))
    adc0 = _hw_unit_by_id(doc, "ADC0")
    g = _groups(doc, adc0)[0]
    assert _val(doc, g, "AdcGroupTriggSrc") == "ADC_TRIGG_SRC_SW"
    assert _val(doc, g, "AdcGroupConversionType") == "ADC_CONV_TYPE_NORMAL"


# ---------------------------------------------------------------------------
# Narrow byte-faithful write + reload
# ---------------------------------------------------------------------------

def test_noop_spec_reproduces_bytes(tmp_path):
    """An empty ADC spec is a no-op and reproduces the file byte-for-byte."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    original = mex.read_bytes()
    doc = MexDocument.load(mex)
    result = apply_adc_set(doc, _intent({}))
    assert not result.blocked
    assert result.changed_modules == []
    doc.write(mex)
    assert mex.read_bytes() == original


def test_written_file_reloads_well_formed(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc003_payload()))
    doc.write(mex)
    reloaded = MexDocument.load(mex)
    unit = _hw_unit_by_id(reloaded, "ADC1")
    assert unit is not None
    assert len(_groups(reloaded, unit)) == 1
    assert len(_channels(reloaded, unit)) == 1  # S10
    bu = _bctu_units(reloaded)
    assert len(bu) == 1


def test_reapply_is_idempotent(tmp_path):
    """Applying ADC-003 twice yields a byte-stable file."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc003_payload()))
    doc.write(mex)
    after_first = mex.read_bytes()

    doc2 = MexDocument.load(mex)
    apply_adc_set(doc2, _intent(_adc003_payload()))
    doc2.write(mex)
    after_second = mex.read_bytes()

    if after_first != after_second:
        diff = "\n".join(
            difflib.unified_diff(
                after_first.decode("utf-8").splitlines(),
                after_second.decode("utf-8").splitlines(),
                lineterm="", n=1,
            )
        )
        raise AssertionError("Re-apply changed bytes:\n" + diff[:2000])


def test_adc_config_set_quick_selection_removed(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc003_payload()))
    doc.write(mex)
    import re
    content = mex.read_text(encoding="utf-8")
    m = re.search(r'config_set\s+name="Adc"[^>]*>', content)
    assert m is not None
    assert "quick_selection" not in m.group(0), m.group(0)


# ---------------------------------------------------------------------------
# Plan: BCTU stays Adc-owned (no cross-module dependency for ADC-003)
# ---------------------------------------------------------------------------

def test_plan_bctu_is_adc_owned():
    """ADC-003 (BCTU HW trigger, no DMA) declares only an Adc-owned change."""
    plan = AdcProvider().plan(_intent(_adc003_payload()))
    owners = [c.owner for c in plan.changes]
    assert "adc" in owners, plan.to_dict()
    # No Mcl DMA dependency: ADC-003 has no FIFO DMA.
    assert [c for c in plan.changes if c.owner == "mcl"] == [], plan.to_dict()
