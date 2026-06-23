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
# File:        test_adc_static_checks.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-19
# Version:     0.1.0
# Description: Unit tests for the ADC coherence static checks (_check_adc).
# =================================================================================

"""ADC static-check coverage.

Verifies that the baseline ADC fixture and a clean ADC-001 apply pass, and that
each ADC coherence rule fires when its precondition is violated. The detectors
encode the Adc.xdm INVALID rules so an incoherent edit is caught before the
S32DS gate.
"""
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_adc_set
from rtd_config.checks.static import run_static_checks
from rtd_config.intent import Intent
from tests.fixtures import copy_adc_fixture


MEX_NAME = "Autombd_Test_Adc_S32K344.mex"


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


def _intent(payload: dict) -> Intent:
    return Intent.from_dict({"module": "adc", "action": "set", "payload": payload})


def _codes(result):
    return {item.code for item in result.diagnostics}


def _adc_unit_by_id(doc, unit_id):
    cfg = doc.find_config_set("Adc")
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwUnit":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                s = doc.find_child_setting(child, "AdcHwUnitId")
                if s is not None and s.attrib.get("value") == unit_id:
                    return child
    return None


def _hw_config_by_id(doc, configured_id):
    cfg = doc.find_config_set("Adc")
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwConfiguration":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                s = doc.find_child_setting(child, "AdcHwConfiguredId")
                if s is not None and s.attrib.get("value") == configured_id:
                    return child
    return None


# ---------------------------------------------------------------------------
# No false positives on the clean baseline / clean apply
# ---------------------------------------------------------------------------

def test_baseline_adc_fixture_passes(tmp_path):
    """The pristine ADC fixture (ADC0 baseline) passes all static checks."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    result = run_static_checks(mex)
    assert result.status == "passed", _codes(result)


def test_clean_adc001_apply_passes(tmp_path):
    """A clean ADC-001 apply passes the static checks (no ADC blockers)."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc001_payload()))
    doc.write(mex)

    result = run_static_checks(mex)
    assert result.status == "passed", _codes(result)


# ---------------------------------------------------------------------------
# Coherence detectors
# ---------------------------------------------------------------------------

def test_interrupt_without_normal_interrupt_enable_blocks(tmp_path):
    """Flip ADC1's AdcNormalInterruptEnable to false -> adc_interrupt_not_enabled."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc001_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    hw = _hw_config_by_id(doc2, "ADC1")
    doc2.find_child_setting(hw, "AdcNormalInterruptEnable").set("value", "false")
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_interrupt_not_enabled" in _codes(result)


def test_threshold_without_watchdog_api_blocks(tmp_path):
    """Flip AdcEnableWatchdogApi to false -> adc_watchdog_api_disabled."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc001_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    adc_cfg = doc2.find_config_set("Adc")
    doc2.find_child_setting(adc_cfg, "AdcEnableWatchdogApi").set("value", "false")
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_watchdog_api_disabled" in _codes(result)


def test_threshold_without_unit_wdg_enable_blocks(tmp_path):
    """Flip ADC1's WdgThresholdEnable to false -> adc_unit_wdg_threshold_disabled."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc001_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    hw = _hw_config_by_id(doc2, "ADC1")
    doc2.find_child_setting(hw, "WdgThresholdEnable").set("value", "false")
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_unit_wdg_threshold_disabled" in _codes(result)


def test_unknown_channel_name_blocks(tmp_path):
    """Corrupt a channel name to a non-device value -> adc_channel_not_in_device."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc001_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    unit = _adc_unit_by_id(doc2, "ADC1")
    # Corrupt the first channel name to something not in the device enum.
    for el in unit:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcChannel":
            first = next(c for c in el if c.tag.endswith("struct"))
            doc2.find_child_setting(first, "AdcChannelName").set("value", "S0_ChanNum999")
            break
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_channel_not_in_device" in _codes(result)


def test_threshold_notification_null_blocks(tmp_path):
    """Set the P5 watchdog notification to NULL_PTR -> adc_watchdog_notification_invalid."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc001_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    unit = _adc_unit_by_id(doc2, "ADC1")
    for el in unit:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcChannel":
            for c in el:
                if not c.tag.endswith("struct"):
                    continue
                name = doc2.find_child_setting(c, "AdcChannelName")
                if name is not None and name.attrib.get("value") == "P5_ChanNum5":
                    doc2.find_child_setting(c, "AdcWdogNotification").set("value", "NULL_PTR")
            break
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_watchdog_notification_invalid" in _codes(result)


# ---------------------------------------------------------------------------
# ADC DMA coherence (modelled on the Uart _check_dma rules)
# ---------------------------------------------------------------------------

def _adc002_dma_payload() -> dict:
    """An ADC0 DMA streaming update (RTD-MEX-ADC-002)."""
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


def test_clean_adc002_dma_apply_passes(tmp_path):
    """A clean ADC-002 DMA apply (full Mcl chain) passes the static checks."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc002_dma_payload()))
    doc.write(mex)

    result = run_static_checks(mex)
    assert result.status == "passed", _codes(result)


def _set_mcl_enable_dma(doc, value: str) -> None:
    mcl = doc.find_config_set("Mcl")
    for el in mcl.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "MclDma":
            doc.find_child_setting(el, "MclEnableDma").set("value", value)
            return


def test_adc_dma_without_mcl_enabled_blocks(tmp_path):
    """An ADC_DMA unit with MclEnableDma=false -> adc_dma_mcl_not_enabled."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc002_dma_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    _set_mcl_enable_dma(doc2, "false")
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_dma_mcl_not_enabled" in _codes(result)


def test_adc_dma_without_channel_ref_blocks(tmp_path):
    """An ADC_DMA unit with an empty AdcDmaChannelId -> adc_dma_refs_incomplete."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc002_dma_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    unit = _adc_unit_by_id(doc2, "ADC0")
    # Empty the AdcDmaChannelId ref so DMA has no logic-channel target.
    for el in unit:
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcDmaChannelId":
            for item in list(el):
                el.remove(item)
            break
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_dma_refs_incomplete" in _codes(result)


def test_bctu_fifo_dma_without_mcl_enabled_blocks(tmp_path):
    """A FIFO-DMA BCTU with MclEnableDma=false -> adc_dma_mcl_not_enabled."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc004_dma_payload()))
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    _set_mcl_enable_dma(doc2, "false")
    result = run_static_checks(mex, doc2)
    assert result.status == "blocked"
    assert "adc_dma_mcl_not_enabled" in _codes(result)


def _adc004_dma_payload() -> dict:
    """The dual-ADC BCTU LIST + FIFO DMA spec (RTD-MEX-ADC-004)."""
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
            "list": ["VREFH", "VREFL", "S20", "S20", "P1", "P2", "P3", "P4"],
            "trigger_order": [2, 2, 4],
            "destination": "fifo1",
            "fifo_dma": True,
            "fifo_notification": "Autombd_BctuFifoNotifi",
        },
    }


def test_clean_adc004_fifo_dma_apply_passes(tmp_path):
    """A clean ADC-004 FIFO-DMA apply passes the static checks (no ADC blockers)."""
    project = copy_adc_fixture(tmp_path)
    mex = project / MEX_NAME
    doc = MexDocument.load(mex)
    apply_adc_set(doc, _intent(_adc004_dma_payload()))
    doc.write(mex)

    result = run_static_checks(mex)
    assert result.status == "passed", _codes(result)
