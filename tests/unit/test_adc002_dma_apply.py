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
# File:        test_adc002_dma_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-19
# Version:     0.1.0
# Description: Unit tests for the ADC0 DMA streaming update path (RTD-MEX-ADC-002)
#              on the Autombd_Test_Adc_S32K344 fixture.
# =================================================================================

"""ADC0 DMA streaming-group configuration via the update-existing-unit path
(RTD-MEX-ADC-002).

Unlike ADC-001 (target unit ADC1 absent -> ADD a unit), ADC-002 targets ADC0
which ALREADY EXISTS in the fixture (AdcHwUnit_0, AdcHwUnitId=ADC0,
AdcTransferType=ADC_INTERRUPT, one channel P0, one SW group AdcGroup_0). The tool
must UPDATE that unit in place: switch to DMA transfer, wire the DMA channel ref,
add channels P1..P7 (reusing the existing P0), and convert AdcGroup_0 into a
DMA-coherent SW streaming group with 10 samples + notification.

VERIFIED DMA coherence (Adc.xdm + S32DS empirical gate -- minimal coherent chain):
  - Unit AdcTransferType=ADC_DMA; AdcDmaChannelId[0] -> a Mcl dmaLogicChannel_Type
    (Adc.xdm L313/L331/L334: required when transfer=DMA).
  - AutosarExt/AdcEnableDmaTransferMode=true (Adc.xdm L305: required for ADC_DMA).
  - AdcHwConfiguration[ADC0]/DmaTransferEnable=true (Adc.xdm L200).
  - AdcHwConfiguration[ADC0]/AdcNormalInterruptEnable=false AND
    AdcInjectedInterruptEnable=false (Adc.xdm L185-198: a DMA unit must disable the
    associated End-of-Conversion / Injected interrupts).
  - Mcl MclEnableDma=true + dmaLogicChannel_Type_0 activated (EnableGlobalConfig,
    dmaGlobalRequest_enDmaRequest, dmaLogicChannelConfig_enDmaMajorInterrupt true).
  - Group: ADC_ACCESS_MODE_STREAMING + ADC_CONV_MODE_CONTINUOUS (Adc.xdm L2877:
    SW + STREAMING cannot be ONESHOT) + ADC_TRIGG_SRC_SW; AdcStreamingNumSamples=10;
    AdcNotification[0]=Autombd_AdcNotifiDma; AdcGroupDefinition = 8 channel refs.

NOTE on the counting DMA channel: Adc.xdm L364/L366 make AdcCountingDmaChannelId
required ONLY when a group has AdcEnableOptimizeDmaStreamingGroups=true (with >1
channel) or a Without-Interrupts streaming combination. ADC-002's plain
SW-streaming-with-interrupts group meets NONE of those, so the counting channel is
NOT required and a SECOND Mcl logic channel is NOT provisioned. This was confirmed
empirically: the minimal single-channel chain passes the S32DS gate (exit 0, no
SEVERE), while leaving optimize off avoids the extra coupled flags.
"""
import difflib
from functools import partial

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_adc_set
from rtd_config.intent import Intent
from rtd_config.modules.adc import AdcProvider
from rtd_config.modules.mcl import MclProvider
from tests.fixtures import copy_adc_fixture, resolved_adc_bundle

_BUNDLE = resolved_adc_bundle()
apply_adc_set = partial(apply_adc_set, bundle=_BUNDLE)
AdcProvider = partial(AdcProvider, _BUNDLE)
MclProvider = partial(MclProvider, _BUNDLE)


MEX_NAME = "Autombd_Test_Adc_S32K344.mex"
DMA_REF0 = "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_0"


# ---------------------------------------------------------------------------
# Intent helpers (the ADC-002 --spec the cold agent authors)
# ---------------------------------------------------------------------------

def _adc002_payload() -> dict:
    return {
        "unit": "ADC0",
        "transfer": "dma",
        "sampling_time_us": 4,
        "groups": [
            {
                "trigger": "sw",
                "access": "streaming",
                "conv": "continuous",
                "num_samples": 10,
                "notification": "Autombd_AdcNotifiDma",
                "channels": ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"],
            }
        ],
    }


def _intent(payload: dict) -> Intent:
    return Intent.from_dict({"module": "adc", "action": "set", "payload": payload})


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

def _adc_cfg(doc):
    return doc.find_config_set("Adc")


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


def _child_arrays(struct, name):
    return [el for el in struct if el.tag.endswith("array") and el.attrib.get("name") == name]


def _groups(doc, unit):
    arrs = _child_arrays(unit, "AdcGroup")
    return [c for c in arrs[0] if c.tag.endswith("struct")] if arrs else []


def _channels(doc, unit):
    arrs = _child_arrays(unit, "AdcChannel")
    return [c for c in arrs[0] if c.tag.endswith("struct")] if arrs else []


def _val(doc, el, name):
    s = doc.find_child_setting(el, name)
    return s.attrib.get("value") if s is not None else None


def _array_items(struct, name):
    """Return the list of <setting>.value under the named array of ``struct``."""
    out = []
    for el in struct:
        if el.tag.endswith("array") and el.attrib.get("name") == name:
            for item in el:
                if item.tag.endswith("setting"):
                    out.append(item.attrib.get("value"))
    return out


def _group_sampling_durations(doc, group):
    for el in group.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "AdcGroupConversionConfiguration":
            return (
                _val(doc, el, "AdcSamplingDuration0"),
                _val(doc, el, "AdcSamplingDuration1"),
                _val(doc, el, "AdcSamplingDuration2"),
            )
    return (None, None, None)


def _mcl_dma_channel_names(doc):
    mcl = doc.find_config_set("Mcl")
    names = []
    for el in mcl.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "dmaLogicChannel_Type":
            for s in el:
                if s.tag.endswith("struct"):
                    n = doc.find_child_setting(s, "Name")
                    if n is not None:
                        names.append(n.attrib.get("value"))
    return names


def _mcl_enable_dma(doc):
    mcl = doc.find_config_set("Mcl")
    for el in mcl.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "MclDma":
            s = doc.find_child_setting(el, "MclEnableDma")
            return s.attrib.get("value") if s is not None else None
    return None


# ---------------------------------------------------------------------------
# Update-existing-unit path
# ---------------------------------------------------------------------------

def test_existing_adc0_updated_not_duplicated(tmp_path):
    """ADC0 exists -> apply must UPDATE it in place, not add a second ADC0 unit."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    result = apply_adc_set(doc, _intent(_adc002_payload()))
    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "adc" in result.changed_modules
    # DMA transfer wires the Mcl DMA logic channel, so changed_modules must
    # report "mcl" too (Tester-flagged under-reporting on ADC-002).
    assert "mcl" in result.changed_modules, result.changed_modules

    cfg = _adc_cfg(doc)
    adc0_units = []
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwUnit":
            for u in el:
                if u.tag.endswith("struct") and _val(doc, u, "AdcHwUnitId") == "ADC0":
                    adc0_units.append(u)
    assert len(adc0_units) == 1, "ADC0 must be updated in place (no duplicate unit)"
    # The updated unit keeps its original Name/struct identity.
    assert _val(doc, adc0_units[0], "Name") == "AdcHwUnit_0"


def test_transfer_switched_to_dma(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    assert _val(doc, unit, "AdcTransferType") == "ADC_DMA"


def test_dma_channel_ref_wired(tmp_path):
    """AdcDmaChannelId[0] must reference a Mcl dmaLogicChannel_Type (Adc.xdm L334)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    refs = _array_items(unit, "AdcDmaChannelId")
    assert refs == [DMA_REF0], f"AdcDmaChannelId must be [{DMA_REF0}], got {refs}"


def test_counting_dma_channel_left_empty(tmp_path):
    """Adc.xdm L364: counting DMA channel is NOT required for a plain SW-streaming
    (interrupts-enabled, optimize-off) group, so it stays empty."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    refs = _array_items(unit, "AdcCountingDmaChannelId")
    assert refs == [], f"AdcCountingDmaChannelId must remain empty, got {refs}"


def test_global_dma_transfer_mode_flipped(tmp_path):
    """AutosarExt/AdcEnableDmaTransferMode false->true (Adc.xdm L305)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    cfg = _adc_cfg(doc)
    s = doc.find_child_setting(cfg, "AdcEnableDmaTransferMode")
    assert s is not None and s.attrib.get("value") == "true"


def test_hw_configuration_dma_enabled_interrupts_disabled(tmp_path):
    """ADC0 HwConfiguration: DmaTransferEnable=true AND Normal/Injected EoC
    interrupts disabled (Adc.xdm L185-198)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    hw = _hw_config_by_id(doc, "ADC0")
    assert hw is not None
    assert _val(doc, hw, "DmaTransferEnable") == "true"
    assert _val(doc, hw, "AdcNormalInterruptEnable") == "false"
    assert _val(doc, hw, "AdcInjectedInterruptEnable") == "false"


def test_mcl_dma_enabled_single_channel(tmp_path):
    """Mcl MclEnableDma=true and the existing dmaLogicChannel_Type_0 is reused
    (no second channel provisioned for this group shape)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    assert _mcl_enable_dma(doc) == "true"
    names = _mcl_dma_channel_names(doc)
    assert names == ["dmaLogicChannel_Type_0"], (
        f"Only the existing dmaLogicChannel_Type_0 is needed, got {names}"
    )


def test_mcl_dma_channel0_activated(tmp_path):
    """dmaLogicChannel_Type_0 activation flags flip true (reusing the Uart DMA
    Mcl plumbing)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    mcl = doc.find_config_set("Mcl")
    ch0 = None
    for el in mcl.iter():
        if el.tag.endswith("struct"):
            n = doc.find_child_setting(el, "Name")
            if n is not None and n.attrib.get("value") == "dmaLogicChannel_Type_0":
                ch0 = el
                break
    assert ch0 is not None
    assert _val(doc, ch0, "dmaLogicChannel_EnableGlobalConfig") == "true"
    found_req = found_irq = False
    for el in ch0.iter():
        if el.tag.endswith("setting"):
            if el.attrib.get("name") == "dmaGlobalRequest_enDmaRequest":
                found_req = el.attrib.get("value") == "true"
            if el.attrib.get("name") == "dmaLogicChannelConfig_enDmaMajorInterrupt":
                found_irq = el.attrib.get("value") == "true"
    assert found_req and found_irq, "ch0 DMA request + major-interrupt flags must be true"


# ---------------------------------------------------------------------------
# 4 us sampling derivation -> 160 @ prescale 4
# ---------------------------------------------------------------------------

def test_sampling_4us_is_160_at_prescale_4(tmp_path):
    """4 us @160 MHz: prescale1->640 (out), prescale2->320 (out), prescale4->160."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    g = _groups(doc, unit)[0]
    sd0, sd1, sd2 = _group_sampling_durations(doc, g)
    assert (sd0, sd1, sd2) == ("160", "160", "160"), (sd0, sd1, sd2)


# ---------------------------------------------------------------------------
# Group: streaming + continuous coercion, num_samples, notification, refs
# ---------------------------------------------------------------------------

def test_group_is_sw_streaming_continuous(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    g = _groups(doc, unit)[0]
    assert _val(doc, g, "AdcGroupAccessMode") == "ADC_ACCESS_MODE_STREAMING"
    assert _val(doc, g, "AdcGroupConversionMode") == "ADC_CONV_MODE_CONTINUOUS"
    assert _val(doc, g, "AdcGroupTriggSrc") == "ADC_TRIGG_SRC_SW"
    assert _val(doc, g, "AdcStreamingNumSamples") == "10"


def test_streaming_oneshot_coerced_to_continuous(tmp_path):
    """Even if the caller writes conv=oneshot, SW+STREAMING must coerce to
    CONTINUOUS (Adc.xdm L2877)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    payload = _adc002_payload()
    payload["groups"][0]["conv"] = "oneshot"
    apply_adc_set(doc, _intent(payload))
    unit = _hw_unit_by_id(doc, "ADC0")
    g = _groups(doc, unit)[0]
    assert _val(doc, g, "AdcGroupConversionMode") == "ADC_CONV_MODE_CONTINUOUS"


def test_group_notification_wired(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    g = _groups(doc, unit)[0]
    notif = _array_items(g, "AdcNotification")
    assert notif == ["Autombd_AdcNotifiDma"], notif


def test_group_definition_lists_eight_channels(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    g = _groups(doc, unit)[0]
    refs = _array_items(g, "AdcGroupDefinition")
    assert len(refs) == 8, f"expected 8 channel refs, got {len(refs)}"
    for i, r in enumerate(refs):
        assert r == f"/Adc/Adc/AdcConfigSet/AdcHwUnit_0/AdcChannel_{i}", r


# ---------------------------------------------------------------------------
# 8-channel reconciliation (reuse existing P0, add P1..P7)
# ---------------------------------------------------------------------------

def test_eight_channels_p0_reused(tmp_path):
    """The existing AdcChannel_0=P0 is REUSED; P1..P7 are added (no duplicate P0)."""
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    channels = _channels(doc, unit)
    names = [_val(doc, c, "AdcChannelName") for c in channels]
    assert names == [f"P{i}_ChanNum{i}" for i in range(8)], names
    # P0 keeps its original struct @name="0"/Name="AdcChannel_0".
    p0 = channels[0]
    assert p0.attrib.get("name") == "0"
    assert _val(doc, p0, "Name") == "AdcChannel_0"


def test_channel_ids_and_logical_ids_unique_sequential(tmp_path):
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / MEX_NAME)
    apply_adc_set(doc, _intent(_adc002_payload()))
    unit = _hw_unit_by_id(doc, "ADC0")
    channels = _channels(doc, unit)
    chan_ids = [_val(doc, c, "AdcChannelId") for c in channels]
    logical = [_val(doc, c, "AdcLogicalChannelId") for c in channels]
    assert chan_ids == [str(i) for i in range(8)], chan_ids
    assert logical == [str(i) for i in range(8)], logical
    # Struct @name attributes globally unique.
    attr_names = [c.attrib.get("name") for c in channels]
    assert len(attr_names) == len(set(attr_names)), attr_names


# ---------------------------------------------------------------------------
# Idempotency: re-apply the same ADC-002 spec is a stable no-op on the result
# ---------------------------------------------------------------------------

def test_reapply_is_idempotent(tmp_path):
    """Applying ADC-002 twice yields a byte-stable file (idempotent update)."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME

    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc002_payload()))
    doc.write(mex)
    after_first = mex.read_bytes()

    doc2 = MexDocument.load(mex)
    apply_adc_set(doc2, _intent(_adc002_payload()))
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


# ---------------------------------------------------------------------------
# Narrow byte-faithful write
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
    apply_adc_set(doc, _intent(_adc002_payload()))
    doc.write(mex)
    reloaded = MexDocument.load(mex)
    unit = _hw_unit_by_id(reloaded, "ADC0")
    assert unit is not None
    assert len(_channels(reloaded, unit)) == 8
    assert len(_groups(reloaded, unit)) == 1


def test_adc_and_mcl_quick_selection_removed(tmp_path):
    """Both edited config_sets (Adc, Mcl) must shed their quick_selection."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc002_payload()))
    doc.write(mex)
    import re
    content = mex.read_text(encoding="utf-8")
    adc = re.search(r'config_set\s+name="Adc"[^>]*>', content)
    mcl = re.search(r'config_set\s+name="Mcl"[^>]*>', content)
    assert adc is not None and "quick_selection" not in adc.group(0), adc.group(0)
    assert mcl is not None and "quick_selection" not in mcl.group(0), mcl.group(0)


# ---------------------------------------------------------------------------
# Plan: ADC provider declares the Mcl DMA cross-module dependency
# ---------------------------------------------------------------------------

def test_plan_declares_mcl_dma_dependency():
    """For transfer=dma, AdcProvider.plan must declare a Mcl-owned DMA dependency
    (mirroring how UartProvider declares MclProvider().dma_dependency)."""
    plan = AdcProvider().plan(_intent(_adc002_payload()))
    owners = [c.owner for c in plan.changes]
    assert "adc" in owners, plan.to_dict()
    mcl_changes = [c for c in plan.changes if c.owner == "mcl"]
    assert len(mcl_changes) == 1, f"Expected one Mcl DMA dependency, got {plan.to_dict()}"
    assert "dmaLogicChannel_Type" in mcl_changes[0].path


def test_plan_interrupt_has_no_mcl_dependency():
    """ADC-001 (interrupt) declares NO Mcl dependency -- it stays Adc-only."""
    plan = AdcProvider().plan(_intent({"unit": "ADC1", "transfer": "interrupt", "groups": []}))
    mcl_changes = [c for c in plan.changes if c.owner == "mcl"]
    assert mcl_changes == [], plan.to_dict()
