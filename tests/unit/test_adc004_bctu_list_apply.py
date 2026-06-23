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
# File:        test_adc004_bctu_list_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-22
# Version:     0.1.0
# Description: Unit tests for the dual-ADC BCTU LIST trigger + FIFO DMA
#              configuration (RTD-MEX-ADC-004) on the Autombd_Test_Adc_S32K344
#              fixture.
# =================================================================================

"""Dual-ADC BCTU LIST trigger + FIFO DMA configuration (RTD-MEX-ADC-004).

The prompt: add TWO Adc Hardware Units (ADC1 @5 us, ADC2 @6 us); add a BCTU
trigger sourced from eMIOS1 channel 20 (BCTU_EMIOS_1_20), conversion mode LIST,
triggering ADC1 AND ADC2; an 8-item list VREFH, VREFL, S20, S20, P1, P2, P3, P4
with a 2/2/4 trigger order; results in FIFO1; on 8 samples raise a FIFO DMA
request; FIFO watermark callback Autombd_BctuFifoNotifi; FIFO DMA enabled.

Neither ADC1 nor ADC2 exists in the fixture -> apply must ADD both units (the
add-new-unit path), then wire a single list BCTU subtree targeting both.

VERIFIED GROUND TRUTH (Adc.xdm + Adc_s32k344_mapbga257.epd, cached):
  - Gating: AdcGeneral/AdcHwTriggerApi=true; AutosarExt/AdcEnableCtuControlModeApi=true;
    AutosarExt/CtuEnableDmaTransferMode=true (required for FIFO DMA, Adc.xdm
    L4986-4987 -- BctuFifoDmaEnable INVALID unless CtuEnableDmaTransferMode is true).
  - AdcHwTrigger_0 repointed to BCTU_EMIOS_1_20 (valid .epd token).
  - BctuInternalTrigger LIST mode: BctuTriggerConversionMode=LIST,
    BctuAdcTargetMask=6 (ADC1|ADC2 = (1<<1)|(1<<2)); LIST allows multi-ADC
    (Adc.xdm L4539-4540); BctuConversionListStartIndex=0; BctuDataDestination=
    BCTU_FIFO1; NO BctuAdcChannelSingle (single-mode only, L4596).
  - BctuListItems field order (Adc.xdm L4762-4818): Name, BctuAdcChannelList
    (ENUM full literal), BctuNextChannelWaitOnTrig (bool, default false),
    BctuLastChannel (bool, default false). 2/2/4 = wait-on-trig true on item
    indices 1 and 3 (last of the first two sub-lists), false elsewhere;
    BctuLastChannel true only on item index 7.
  - BctuResultFifos field order (Adc.xdm L4841-5043): Name, BctuResultFifoIndex=
    BCTU_FIFO1, BctuWatermarkValue=7 (INTEGER 0..15 and < FIFO depth; DMA fires
    when active entries exceed the watermark, so 7 raises the request when the
    8th sample lands), BctuFifoNotificationsEnable=false (MUST be false with DMA,
    L4984-4988), BctuWatermarkNotification=Autombd_BctuFifoNotifi (EDITABLE when
    DMA or int enabled, L4924; used for both, L4910), BctuUnderrunNotification=
    NULL_PTR, BctuOverrunNotification=NULL_PTR, BctuFifoDmaEnable=true,
    BctuFifoDmaBuffer=BctuDmaFifo1 (LINKER-SYMBOL default concat('BctuDmaFifo',N)),
    BctuFifoDmaChannelId=[/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_0] (REF, required
    when DMA enabled, L5038-5041).
  - 5 us @160 MHz: prescale1->800, prescale2->400, prescale4->200 (in [8,255]) -> 200/p4.
    6 us @160 MHz: prescale1->960, prescale2->480, prescale4->240 (in [8,255]) -> 240/p4.
  - Mcl cross-module: FIFO DMA reuses _activate_mcl_dma (MclEnableDma=true +
    dmaLogicChannel_Type_0 activated). AdcProvider.plan declares the Mcl DMA
    dependency for the FIFO-DMA path.
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
DMA_REF0 = "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_0"

# The 8 list channels (full literals) and their short forms, in list order.
LIST_SHORT = ["VREFH", "VREFL", "S20", "S20", "P1", "P2", "P3", "P4"]
LIST_FULL = [
    "VREFH_ChanNum55", "VREFL_ChanNum54", "S20_ChanNum44", "S20_ChanNum44",
    "P1_ChanNum1", "P2_ChanNum2", "P3_ChanNum3", "P4_ChanNum4",
]


# ---------------------------------------------------------------------------
# Intent helper (the ADC-004 --spec a cold agent authors)
# ---------------------------------------------------------------------------

def _adc004_payload() -> dict:
    return {
        "units": [
            {"unit": "ADC1", "sampling_time_us": 5},
            {"unit": "ADC2", "sampling_time_us": 6},
        ],
        "transfer": "interrupt",
        "bctu": {
            "trigger_source": "BCTU_EMIOS_1_20",
            "mode": "list",
            "targets": ["ADC1", "ADC2"],
            "list": LIST_SHORT,
            "trigger_order": [2, 2, 4],
            "destination": "fifo1",
            "fifo_dma": True,
            "fifo_notification": "Autombd_BctuFifoNotifi",
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


def _array_structs(parent, array_name):
    for el in parent:
        if el.tag.endswith("array") and el.attrib.get("name") == array_name:
            return [c for c in el if c.tag.endswith("struct")]
    return []


def _first_struct(parent, array_name):
    structs = _array_structs(parent, array_name)
    return structs[0] if structs else None


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
# Sampling derivation: 5 us -> 200 @ p4, 6 us -> 240 @ p4
# ---------------------------------------------------------------------------

def test_sampling_5us_is_200_at_prescale_4():
    dur, pre = _derive_adc_sampling_duration(5e-6)
    assert (dur, pre) == (200, 4)


def test_sampling_6us_is_240_at_prescale_4():
    dur, pre = _derive_adc_sampling_duration(6e-6)
    assert (dur, pre) == (240, 4)


# ---------------------------------------------------------------------------
# Dual-unit creation
# ---------------------------------------------------------------------------

def test_both_units_created(tmp_path):
    """ADC1 and ADC2 are both added (neither exists in the fixture)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    result = apply_adc_set(doc, _intent(_adc004_payload()))
    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert _hw_unit_by_id(doc, "ADC1") is not None
    assert _hw_unit_by_id(doc, "ADC2") is not None
    # ADC0 baseline untouched.
    assert _hw_unit_by_id(doc, "ADC0") is not None


def test_unit_prescales_encoded(tmp_path):
    """ADC1 encodes AdcPrescale=4 (5 us), ADC2 encodes AdcPrescale=4 (6 us)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    for uid in ("ADC1", "ADC2"):
        unit = _hw_unit_by_id(doc, uid)
        pre = []
        for el in unit:
            if el.tag.endswith("array") and el.attrib.get("name") == "AdcPrescale":
                pre = [i.attrib.get("value") for i in el if i.tag.endswith("setting")]
        assert pre == ["4"], f"{uid} AdcPrescale must be [4], got {pre}"


def test_unit_sampling_durations(tmp_path):
    """ADC1 group SD=200 (5 us), ADC2 group SD=240 (6 us)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    expected = {"ADC1": "200", "ADC2": "240"}
    for uid, sd in expected.items():
        unit = _hw_unit_by_id(doc, uid)
        g = _groups(doc, unit)[0]
        for el in g.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "AdcGroupConversionConfiguration":
                assert _val(doc, el, "AdcSamplingDuration0") == sd, uid
                assert _val(doc, el, "AdcSamplingDuration1") == sd, uid
                assert _val(doc, el, "AdcSamplingDuration2") == sd, uid


def test_units_logical_ids_unique(tmp_path):
    """Each added unit gets a unique AdcLogicalUnitId continuing past ADC0=0."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    ids = []
    for uid in ("ADC0", "ADC1", "ADC2"):
        unit = _hw_unit_by_id(doc, uid)
        ids.append(_val(doc, unit, "AdcLogicalUnitId"))
    assert len(ids) == len(set(ids)), f"AdcLogicalUnitId values must be unique: {ids}"


def test_struct_names_globally_unique(tmp_path):
    """AdcChannel/AdcGroup struct @name + AdcGroupId are unique across all units."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    chan_names, group_names, group_ids = [], [], []
    for uid in ("ADC0", "ADC1", "ADC2"):
        unit = _hw_unit_by_id(doc, uid)
        for c in _channels(doc, unit):
            chan_names.append(c.attrib.get("name"))
        for g in _groups(doc, unit):
            group_names.append(g.attrib.get("name"))
            group_ids.append(_val(doc, g, "AdcGroupId"))
    assert len(chan_names) == len(set(chan_names)), f"channel @name collision: {chan_names}"
    assert len(group_names) == len(set(group_names)), f"group @name collision: {group_names}"
    assert len(group_ids) == len(set(group_ids)), f"AdcGroupId collision: {group_ids}"


# ---------------------------------------------------------------------------
# Gating flags
# ---------------------------------------------------------------------------

def test_hw_trigger_api_flipped(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    cfg = _adc_cfg(doc)
    assert _val(doc, cfg, "AdcHwTriggerApi") == "true"


def test_ctu_control_mode_api_flipped(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    cfg = _adc_cfg(doc)
    assert _val(doc, cfg, "AdcEnableCtuControlModeApi") == "true"


def test_ctu_dma_transfer_mode_flipped(tmp_path):
    """FIFO DMA requires AutosarExt/CtuEnableDmaTransferMode=true (Adc.xdm L4986-4987)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    cfg = _adc_cfg(doc)
    assert _val(doc, cfg, "CtuEnableDmaTransferMode") == "true"


# ---------------------------------------------------------------------------
# AdcHwTrigger_0 repoint
# ---------------------------------------------------------------------------

def test_adc_hw_trigger_source_repointed(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    trig = _adc_hw_trigger_0(doc)
    assert trig is not None
    assert _val(doc, trig, "AdcHwTrigSrc") == "BCTU_EMIOS_1_20"
    assert _val(doc, trig, "Name") == "AdcHwTrigger_0"


# ---------------------------------------------------------------------------
# BctuInternalTrigger (LIST mode)
# ---------------------------------------------------------------------------

def test_bctu_internal_trigger_list_mode(tmp_path):
    """LIST mode: target mask 6 (ADC1|ADC2), FIFO1 destination, start index 0,
    NO single-channel ref."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    it = _first_struct(bu, "BctuInternalTrigger")
    assert it is not None, "BctuInternalTrigger_0 must exist"
    assert _val(doc, it, "BctuTriggerSource") == TRIG_REF
    assert _val(doc, it, "BctuTriggerConversionMode") == "LIST"
    # ADC1 + ADC2 -> bit1|bit2 -> mask 6.
    assert _val(doc, it, "BctuAdcTargetMask") == "6"
    assert _val(doc, it, "BctuDataDestination") == "BCTU_FIFO1"
    assert _val(doc, it, "BctuConversionListStartIndex") == "0"
    assert _val(doc, it, "BctuHwTriggerEnable") == "true"
    # LIST mode must NOT carry a single-channel ref (single-mode only).
    assert doc.find_child_setting(it, "BctuAdcChannelSingle") is None


# ---------------------------------------------------------------------------
# BctuListItems (8 entries + 2/2/4 flags)
# ---------------------------------------------------------------------------

def test_bctu_list_items_count_and_channels(tmp_path):
    """The list has 8 items in order VREFH, VREFL, S20, S20, P1, P2, P3, P4."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    items = _array_structs(bu, "BctuListItems")
    assert len(items) == 8, f"expected 8 list items, got {len(items)}"
    channels = [_val(doc, it, "BctuAdcChannelList") for it in items]
    assert channels == LIST_FULL, channels


def test_bctu_list_items_indices_sequential(tmp_path):
    """Each list item carries a unique sequential @name (0..7) and Name suffix."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    items = _array_structs(bu, "BctuListItems")
    assert [it.attrib.get("name") for it in items] == [str(i) for i in range(8)]


def test_bctu_list_wait_on_trig_flags_224(tmp_path):
    """2/2/4 order: BctuNextChannelWaitOnTrig true on indices 1 and 3 only."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    items = _array_structs(bu, "BctuListItems")
    waits = [_val(doc, it, "BctuNextChannelWaitOnTrig") for it in items]
    expected = ["false", "true", "false", "true", "false", "false", "false", "false"]
    assert waits == expected, waits


def test_bctu_list_last_channel_flag(tmp_path):
    """BctuLastChannel is true only on the final list item (index 7)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    items = _array_structs(bu, "BctuListItems")
    last = [_val(doc, it, "BctuLastChannel") for it in items]
    expected = ["false"] * 7 + ["true"]
    assert last == expected, last


# ---------------------------------------------------------------------------
# BctuResultFifos (FIFO1 + DMA)
# ---------------------------------------------------------------------------

def test_bctu_result_fifo_dma_wired(tmp_path):
    """One FIFO1 result-fifo entry with DMA enabled, watermark callback, Mcl ref."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    fifos = _array_structs(bu, "BctuResultFifos")
    assert len(fifos) == 1, f"expected 1 result fifo, got {len(fifos)}"
    f = fifos[0]
    assert _val(doc, f, "BctuResultFifoIndex") == "BCTU_FIFO1"
    assert _val(doc, f, "BctuFifoDmaEnable") == "true"
    # FIFO interrupt notifications MUST be disabled when DMA is enabled.
    assert _val(doc, f, "BctuFifoNotificationsEnable") == "false"
    # Watermark callback is shared by interrupt + DMA (Adc.xdm L4910).
    assert _val(doc, f, "BctuWatermarkNotification") == "Autombd_BctuFifoNotifi"
    # Watermark < FIFO depth so an 8-sample batch raises the request.
    wm = int(_val(doc, f, "BctuWatermarkValue"))
    assert 0 <= wm <= 15
    assert wm < 8, f"watermark {wm} must be < 8 so the 8th sample raises the DMA request"
    # DMA buffer linker-symbol default for FIFO1.
    assert _val(doc, f, "BctuFifoDmaBuffer") == "BctuDmaFifo1"
    # Underrun/overrun left as NULL_PTR (DMA path; interrupts disabled).
    assert _val(doc, f, "BctuUnderrunNotification") == "NULL_PTR"
    assert _val(doc, f, "BctuOverrunNotification") == "NULL_PTR"


def test_bctu_result_fifo_dma_channel_ref(tmp_path):
    """BctuFifoDmaChannelId references the Mcl dmaLogicChannel_Type_0 (Adc.xdm L5038)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    f = _array_structs(bu, "BctuResultFifos")[0]
    refs = []
    for el in f:
        if el.tag.endswith("array") and el.attrib.get("name") == "BctuFifoDmaChannelId":
            refs = [i.attrib.get("value") for i in el if i.tag.endswith("setting")]
    assert refs == [DMA_REF0], f"BctuFifoDmaChannelId must be [{DMA_REF0}], got {refs}"


def test_bctu_fifo_notification_disabled_when_dma(tmp_path):
    """Explicit guard: FIFO interrupt + DMA are mutually exclusive (Adc.xdm L4984-4985)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    bu = _bctu_units(doc)[0]
    f = _array_structs(bu, "BctuResultFifos")[0]
    dma = _val(doc, f, "BctuFifoDmaEnable") == "true"
    notif = _val(doc, f, "BctuFifoNotificationsEnable") == "true"
    assert not (dma and notif), "FIFO interrupts and DMA cannot both be enabled"


# ---------------------------------------------------------------------------
# Mcl cross-module DMA wiring
# ---------------------------------------------------------------------------

def test_mcl_dma_enabled_for_fifo_dma(tmp_path):
    """FIFO DMA activates Mcl DMA (MclEnableDma=true + dmaLogicChannel_Type_0)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc004_payload()))
    mcl = doc.find_config_set("Mcl")
    enable = None
    for el in mcl.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "MclDma":
            enable = _val(doc, el, "MclEnableDma")
            break
    assert enable == "true"
    # dmaLogicChannel_Type_0 activation flags flipped true.
    ch0 = None
    for el in mcl.iter():
        if el.tag.endswith("struct"):
            n = doc.find_child_setting(el, "Name")
            if n is not None and n.attrib.get("value") == "dmaLogicChannel_Type_0":
                ch0 = el
                break
    assert ch0 is not None
    assert _val(doc, ch0, "dmaLogicChannel_EnableGlobalConfig") == "true"


def test_changed_modules_includes_mcl(tmp_path):
    """ADC FIFO-DMA apply wires Mcl, so changed_modules must include 'mcl'."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    result = apply_adc_set(doc, _intent(_adc004_payload()))
    assert "adc" in result.changed_modules
    assert "mcl" in result.changed_modules, result.changed_modules


def test_plan_declares_mcl_dma_dependency():
    """For FIFO DMA, AdcProvider.plan declares a Mcl-owned DMA dependency."""
    plan = AdcProvider().plan(_intent(_adc004_payload()))
    owners = [c.owner for c in plan.changes]
    assert "adc" in owners, plan.to_dict()
    mcl_changes = [c for c in plan.changes if c.owner == "mcl"]
    assert len(mcl_changes) == 1, f"expected one Mcl DMA dependency, got {plan.to_dict()}"
    assert "dmaLogicChannel_Type" in mcl_changes[0].path


# ---------------------------------------------------------------------------
# Unknown trigger source / bad list rejection
# ---------------------------------------------------------------------------

def test_unknown_bctu_trigger_source_rejected(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    payload = _adc004_payload()
    payload["bctu"]["trigger_source"] = "BCTU_EMIOS_9_99"
    result = apply_adc_set(doc, _intent(payload))
    assert result.blocked
    codes = [d.code for d in result.diagnostics]
    assert any("bctu_trigger_source" in c for c in codes), codes


def test_list_channel_not_in_device_rejected(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    payload = _adc004_payload()
    payload["bctu"]["list"] = ["VREFH", "NOPE", "S20", "S20", "P1", "P2", "P3", "P4"]
    result = apply_adc_set(doc, _intent(payload))
    assert result.blocked
    codes = [d.code for d in result.diagnostics]
    assert any("bctu" in c and "channel" in c for c in codes), codes


def test_trigger_order_mismatch_rejected(tmp_path):
    """trigger_order must sum to the list length, else a blocker."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    payload = _adc004_payload()
    payload["bctu"]["trigger_order"] = [2, 2, 2]  # sums to 6, not 8
    result = apply_adc_set(doc, _intent(payload))
    assert result.blocked
    codes = [d.code for d in result.diagnostics]
    assert any("trigger_order" in c for c in codes), codes


# ---------------------------------------------------------------------------
# Backward-compatibility: ADC-003 single-mode BCTU spec still works
# ---------------------------------------------------------------------------

def test_single_unit_form_still_supported(tmp_path):
    """The ADC-003 single-`unit` + single-mode `bctu` spec is unchanged."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    payload = {
        "unit": "ADC1",
        "transfer": "interrupt",
        "sampling_time_us": 2,
        "groups": [
            {"trigger": "hw", "access": "single", "conv": "oneshot",
             "num_samples": 1, "channels": ["S10"]},
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
    result = apply_adc_set(doc, _intent(payload))
    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    bu = _bctu_units(doc)[0]
    it = _first_struct(bu, "BctuInternalTrigger")
    assert _val(doc, it, "BctuTriggerConversionMode") == "SINGLE"
    assert _val(doc, it, "BctuAdcTargetMask") == "2"
    # Single mode keeps the single-channel ref and empty list/fifo arrays.
    assert _val(doc, it, "BctuAdcChannelSingle") is not None
    assert _array_structs(bu, "BctuListItems") == []
    assert _array_structs(bu, "BctuResultFifos") == []


# ---------------------------------------------------------------------------
# Narrow byte-faithful write + idempotency
# ---------------------------------------------------------------------------

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


def test_written_file_reloads_well_formed(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc004_payload()))
    doc.write(mex)
    reloaded = MexDocument.load(mex)
    assert _hw_unit_by_id(reloaded, "ADC1") is not None
    assert _hw_unit_by_id(reloaded, "ADC2") is not None
    bu = _bctu_units(reloaded)
    assert len(bu) == 1
    assert len(_array_structs(bu[0], "BctuListItems")) == 8
    assert len(_array_structs(bu[0], "BctuResultFifos")) == 1


def test_reapply_is_idempotent(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc004_payload()))
    doc.write(mex)
    after_first = mex.read_bytes()

    doc2 = MexDocument.load(mex)
    apply_adc_set(doc2, _intent(_adc004_payload()))
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


def test_adc_and_mcl_quick_selection_removed(tmp_path):
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc004_payload()))
    doc.write(mex)
    import re
    content = mex.read_text(encoding="utf-8")
    adc = re.search(r'config_set\s+name="Adc"[^>]*>', content)
    mcl = re.search(r'config_set\s+name="Mcl"[^>]*>', content)
    assert adc is not None and "quick_selection" not in adc.group(0), adc.group(0)
    assert mcl is not None and "quick_selection" not in mcl.group(0), mcl.group(0)
