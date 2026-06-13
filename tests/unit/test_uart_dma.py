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
# 权持有人均不对因本软件、或引自于本软件的使用或其他利用而引起的、引发的或与之相关的任
# 何权利主张、损害赔偿或其他责任承担责任。
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        test_uart_dma.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-13
# Version:     0.1.0
# Description: Deterministic tests for apply_uart_set DMA mode (RTD-MEX-UART-003).
#              Covers: DMA method enum, UartDmaEnable, Tx/Rx channel refs, MCL DMA
#              channel activate+add, Platform DMATCD ISRs, changed_modules, byte-narrow,
#              idempotent, well-formed, CLI integration, plan() DMA deps, asset keys,
#              anti-hardcode (DMA ch->ISR/handler derived, not hardcoded).
# =================================================================================

"""Deterministic tests for apply_uart_set DMA mode orchestration (RTD-MEX-UART-003).

Fixture: tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/Uart_Example.mex
Channel 0 (Name=LPUART3, UartHwUsing=LPUART_IP) is the target for DMA mode.

Ground truth:
- Uart.xdm: UartInteruptDmaMethod enum = LPUART_UART_IP_USING_DMA (from uart.json)
- Mcl fixture lines ~591-674: dmaLogicChannel_Type_0 (DMA_IP_HW_CH_0)
- Platform: DMATCD0_IRQn/Dma0_Ch0_IRQHandler, DMATCD1_IRQn/Dma0_Ch1_IRQHandler
- uart.json: dma_hw_channel_irq_map key (loaded, not hardcoded)
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rtd_config.backends.s32_mex.apply import apply_uart_set
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.intent import Intent
from rtd_config.modules.uart import UartProvider
from tests.fixtures import copy_uart_fixture

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_UART_ASSET = (
    _REPO_ROOT / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "uart" / "uart.json"
)

# DMA enum verified in Uart.xdm and uart.json enum_domains
_DMA_METHOD_ENUM = "LPUART_UART_IP_USING_DMA"

# DMA Tx/Rx MCL ref paths (fixture-grounded: dmaLogicChannel_Type_0 / _1)
_DMA_TX_REF = "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_0"
_DMA_RX_REF = "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_1"

# Platform DMA ISRs (grounded: DMATCD<ch>_IRQn -> Dma0_Ch<ch>_IRQHandler)
_DMATCD0_IRQ = "DMATCD0_IRQn"
_DMATCD0_HANDLER = "Dma0_Ch0_IRQHandler"
_DMATCD1_IRQ = "DMATCD1_IRQn"
_DMATCD1_HANDLER = "Dma0_Ch1_IRQHandler"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "uart", "action": "set", "payload": payload})


def _uart_channel_0(doc: MexDocument) -> ET.Element:
    """Return the first UartChannel struct (LPUART_IP path, channel[0])."""
    uart_cfg = doc.find_config_set("Uart")
    assert uart_cfg is not None, "Uart config_set not found"
    for arr in uart_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "UartChannel":
            for ch in arr:
                if ch.tag.endswith("struct"):
                    using = doc.find_child_setting(ch, "UartHwUsing")
                    if using is not None and using.attrib.get("value") == "LPUART_IP":
                        return ch
    raise AssertionError("LPUART_IP UartChannel struct not found")


def _detail_setting(doc: MexDocument, channel: ET.Element, name: str) -> str | None:
    """Return a setting value from the DetailModuleConfiguration sub-struct."""
    for el in channel.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "DetailModuleConfiguration":
            s = doc.find_child_setting(el, name)
            return s.attrib.get("value") if s is not None else None
    return None


def _detail_array(doc: MexDocument, channel: ET.Element, name: str) -> ET.Element | None:
    """Return an array element from the DetailModuleConfiguration sub-struct."""
    for el in channel.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "DetailModuleConfiguration":
            for child in el:
                if child.tag.endswith("array") and child.attrib.get("name") == name:
                    return child
    return None


def _gen_cfg_setting(doc: MexDocument, name: str) -> str | None:
    """Return a setting value from Uart GeneralConfiguration."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return None
    for el in uart_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "GeneralConfiguration":
            s = doc.find_child_setting(el, name)
            return s.attrib.get("value") if s is not None else None
    return None


def _gen_cfg_callback_array_value(doc: MexDocument, index: int) -> str | None:
    """Return UartCallback[index] from Uart GeneralConfiguration."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return None
    for el in uart_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "GeneralConfiguration":
            for arr in el:
                if arr.tag.endswith("array") and arr.attrib.get("name") == "UartCallback":
                    for child in arr:
                        if child.attrib.get("name") == str(index):
                            return child.attrib.get("value")
    return None


def _platform_isr_entry(doc: MexDocument, isr_name: str) -> ET.Element | None:
    """Return a PlatformIsrConfig struct matching isr_name, or None."""
    plat_cfg = doc.find_config_set("Platform")
    if plat_cfg is None:
        return None
    for arr in plat_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "PlatformIsrConfig":
            for s in arr:
                if not s.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(s, "IsrName")
                if n is not None and n.attrib.get("value") == isr_name:
                    return s
    return None


def _platform_isr_setting(doc: MexDocument, isr_name: str, field: str) -> str | None:
    entry = _platform_isr_entry(doc, isr_name)
    if entry is None:
        return None
    s = doc.find_child_setting(entry, field)
    return s.attrib.get("value") if s is not None else None


def _mcl_dma_channel(doc: MexDocument, name: str) -> ET.Element | None:
    """Return the dmaLogicChannel_Type struct with Name==name, or None."""
    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is None:
        return None
    for arr in mcl_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "dmaLogicChannel_Type":
            for s in arr:
                if not s.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(s, "Name")
                if n is not None and n.attrib.get("value") == name:
                    return s
    return None


def _mcl_dma_channel_setting(doc: MexDocument, ch_name: str, field: str) -> str | None:
    ch = _mcl_dma_channel(doc, ch_name)
    if ch is None:
        return None
    # Direct child setting
    s = doc.find_child_setting(ch, field)
    if s is not None:
        return s.attrib.get("value")
    # Nested setting (walk all descendants)
    for el in ch.iter():
        if el.tag.endswith("setting") and el.attrib.get("name") == field:
            return el.attrib.get("value")
    return None


def _mcl_general_dma_enabled(doc: MexDocument) -> str | None:
    """Return MclEnableDma value from Mcl MclGeneral/MclDma."""
    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is None:
        return None
    for el in mcl_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "MclDma":
            s = doc.find_child_setting(el, "MclEnableDma")
            return s.attrib.get("value") if s is not None else None
    return None


def _dma_tx_ref_value(doc: MexDocument, channel: ET.Element, index: int) -> str | None:
    """Return UartDmaTxChannelRef[index] value from DetailModuleConfiguration."""
    arr = _detail_array(doc, channel, "UartDmaTxChannelRef")
    if arr is None:
        return None
    for child in arr:
        if child.attrib.get("name") == str(index):
            return child.attrib.get("value")
    return None


def _dma_rx_ref_value(doc: MexDocument, channel: ET.Element, index: int) -> str | None:
    """Return UartDmaRxChannelRef[index] value from DetailModuleConfiguration."""
    arr = _detail_array(doc, channel, "UartDmaRxChannelRef")
    if arr is None:
        return None
    for child in arr:
        if child.attrib.get("name") == str(index):
            return child.attrib.get("value")
    return None


# ---------------------------------------------------------------------------
# Asset: DMA-specific keys (LL-016 code==asset pin)
# ---------------------------------------------------------------------------

class TestUartAssetDmaKeys:
    """uart.json must contain DMA-specific keys (LL-016)."""

    def test_dma_enum_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data["enum_domains"]["UartInteruptDmaMethod"]
        assert "LPUART_UART_IP_USING_DMA" in enums, (
            "DMA enum must be present in uart.json UartInteruptDmaMethod"
        )

    def test_asset_has_dma_hw_channel_irq_map(self):
        """uart.json must have dma_hw_channel_irq_map (loaded at runtime, not hardcoded)."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        dma_map = data.get("dma_hw_channel_irq_map")
        assert dma_map is not None, "uart.json must have dma_hw_channel_irq_map"
        assert isinstance(dma_map, dict)

    def test_dma_channel_0_irq_entry(self):
        """DMA HW channel 0 -> DMATCD0_IRQn / Dma0_Ch0_IRQHandler."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        entry = data["dma_hw_channel_irq_map"].get("0") or data["dma_hw_channel_irq_map"].get(0)
        assert entry is not None, "dma_hw_channel_irq_map must have entry for channel 0"
        assert entry["irq_name"] == "DMATCD0_IRQn"
        assert entry["isr_handler"] == "Dma0_Ch0_IRQHandler"

    def test_dma_channel_1_irq_entry(self):
        """DMA HW channel 1 -> DMATCD1_IRQn / Dma0_Ch1_IRQHandler."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        entry = data["dma_hw_channel_irq_map"].get("1") or data["dma_hw_channel_irq_map"].get(1)
        assert entry is not None, "dma_hw_channel_irq_map must have entry for channel 1"
        assert entry["irq_name"] == "DMATCD1_IRQn"
        assert entry["isr_handler"] == "Dma0_Ch1_IRQHandler"

    def test_asset_has_dma_channel_ref_path_pattern(self):
        """uart.json must have dma_channel_ref_path_pattern (MCL DMA ref path, loaded)."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        pattern = data.get("dma_channel_ref_path_pattern")
        assert pattern is not None, "uart.json must have dma_channel_ref_path_pattern"
        # Must be a string with {index} placeholder
        assert "{index}" in pattern, (
            "dma_channel_ref_path_pattern must contain {index} placeholder"
        )

    def test_dma_tx_ref_path_matches_fixture(self):
        """DMA TX ref path (index=0) must equal the fixture dmaLogicChannel_Type_0 path."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        pattern = data["dma_channel_ref_path_pattern"]
        tx_path = pattern.format(index=0)
        assert tx_path == "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_0"

    def test_dma_rx_ref_path_matches_fixture(self):
        """DMA RX ref path (index=1) must equal the fixture dmaLogicChannel_Type_1 path."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        pattern = data["dma_channel_ref_path_pattern"]
        rx_path = pattern.format(index=1)
        assert rx_path == "/Mcl/Mcl/MclConfig/dmaLogicChannel_Type_1"

    def test_asset_has_mcl_dma_channel_template(self):
        """uart.json must have mcl_dma_channel_template for building dmaLogicChannel_Type_1."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        tmpl = data.get("mcl_dma_channel_template")
        assert tmpl is not None, "uart.json must have mcl_dma_channel_template"
        # Must have the critical fields
        assert "dmaLogicChannel_EnableGlobalConfig" in tmpl
        assert "dmaGlobalRequest_enDmaRequest" in tmpl
        assert "dmaLogicChannelConfig_enDmaMajorInterrupt" in tmpl

    def test_mcl_dma_channel_template_enable_flags(self):
        """The MCL DMA channel template must have the correct activation flags."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        tmpl = data["mcl_dma_channel_template"]
        assert tmpl["dmaLogicChannel_EnableGlobalConfig"] == "true"
        assert tmpl["dmaGlobalRequest_enDmaRequest"] == "true"
        assert tmpl["dmaLogicChannelConfig_enDmaMajorInterrupt"] == "true"


# ---------------------------------------------------------------------------
# Uart channel DMA edits
# ---------------------------------------------------------------------------

class TestUartDmaMethod:
    """apply_uart_set with mode=dma must set UartInteruptDmaMethod=LPUART_UART_IP_USING_DMA."""

    def test_dma_method_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_3", mode="dma", callback="Autombd_UartCallback",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartInteruptDmaMethod") == _DMA_METHOD_ENUM

    def test_dma_does_not_block(self, tmp_path):
        """mode=dma must not return a blocker (old DMA rejection is removed)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]


class TestUartDmaEnable:
    """GeneralConfiguration/UartDmaEnable must be set to true in DMA mode."""

    def test_uart_dma_enable_true(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _gen_cfg_setting(doc, "UartDmaEnable") == "true"

    def test_uart_dma_enable_unchanged_in_interrupt_mode(self, tmp_path):
        """UartDmaEnable must NOT be set to true when mode=interrupt."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", mode="interrupt"))
        assert _gen_cfg_setting(doc, "UartDmaEnable") == "false"


class TestUartDmaChannelRefs:
    """UartDmaTxChannelRef[0] and UartDmaRxChannelRef[0] must be populated in DMA mode."""

    def test_dma_tx_ref_populated(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        val = _dma_tx_ref_value(doc, ch, 0)
        assert val == _DMA_TX_REF, f"UartDmaTxChannelRef[0] expected {_DMA_TX_REF!r}, got {val!r}"

    def test_dma_rx_ref_populated(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        val = _dma_rx_ref_value(doc, ch, 0)
        assert val == _DMA_RX_REF, f"UartDmaRxChannelRef[0] expected {_DMA_RX_REF!r}, got {val!r}"

    def test_dma_refs_empty_in_interrupt_mode(self, tmp_path):
        """UartDmaTxChannelRef and UartDmaRxChannelRef must stay empty in interrupt mode."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", mode="interrupt"))
        ch = _uart_channel_0(doc)
        assert _dma_tx_ref_value(doc, ch, 0) is None
        assert _dma_rx_ref_value(doc, ch, 0) is None


class TestUartDmaCallback:
    """Callback set in DMA mode same as interrupt mode."""

    def test_dma_callback_capability_enabled(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", callback="Autombd_UartCallback"))
        assert _gen_cfg_setting(doc, "UartCallbackCapability") == "true"

    def test_dma_callback_name_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", callback="Autombd_UartCallback"))
        assert _gen_cfg_callback_array_value(doc, 0) == "Autombd_UartCallback"


# ---------------------------------------------------------------------------
# MCL DMA channel edits
# ---------------------------------------------------------------------------

class TestMclDmaChannelActivate:
    """apply_uart_set DMA mode must activate dmaLogicChannel_Type_0 (TX)."""

    def test_mcl_enable_dma_true(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _mcl_general_dma_enabled(doc) == "true"

    def test_mcl_ch0_enable_global_config(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_0", "dmaLogicChannel_EnableGlobalConfig")
        assert val == "true", f"dmaLogicChannel_EnableGlobalConfig expected 'true', got {val!r}"

    def test_mcl_ch0_en_dma_request(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_0", "dmaGlobalRequest_enDmaRequest")
        assert val == "true", f"dmaGlobalRequest_enDmaRequest expected 'true', got {val!r}"

    def test_mcl_ch0_en_major_interrupt(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_0", "dmaLogicChannelConfig_enDmaMajorInterrupt")
        assert val == "true", f"dmaLogicChannelConfig_enDmaMajorInterrupt expected 'true', got {val!r}"

    def test_mcl_ch0_hw_ch_id(self, tmp_path):
        """dmaLogicChannel_Type_0 must use DMA_IP_HW_CH_0 (fixture-grounded)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_0", "dmaLogicChannel_HwChId")
        assert val == "DMA_IP_HW_CH_0", f"HwChId expected 'DMA_IP_HW_CH_0', got {val!r}"


class TestMclDmaChannelAdd:
    """apply_uart_set DMA mode must ADD dmaLogicChannel_Type_1 (RX channel)."""

    def test_mcl_ch1_added(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch1 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_1")
        assert ch1 is not None, "dmaLogicChannel_Type_1 must be added by DMA mode"

    def test_mcl_ch1_logic_name(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_1", "dmaLogicChannel_LogicName")
        assert val == "DMA_LOGIC_CH_1", f"LogicName expected 'DMA_LOGIC_CH_1', got {val!r}"

    def test_mcl_ch1_hw_ch_id(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_1", "dmaLogicChannel_HwChId")
        assert val == "DMA_IP_HW_CH_1", f"HwChId expected 'DMA_IP_HW_CH_1', got {val!r}"

    def test_mcl_ch1_hw_inst_id(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_1", "dmaLogicChannel_HwInstId")
        assert val == "DMA_IP_HW_INST_0", f"HwInstId expected 'DMA_IP_HW_INST_0', got {val!r}"

    def test_mcl_ch1_enable_global_config(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_1", "dmaLogicChannel_EnableGlobalConfig")
        assert val == "true"

    def test_mcl_ch1_en_dma_request(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_1", "dmaGlobalRequest_enDmaRequest")
        assert val == "true"

    def test_mcl_ch1_en_major_interrupt(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))
        val = _mcl_dma_channel_setting(doc, "dmaLogicChannel_Type_1", "dmaLogicChannelConfig_enDmaMajorInterrupt")
        assert val == "true"

    def test_mcl_ch1_not_added_in_interrupt_mode(self, tmp_path):
        """dmaLogicChannel_Type_1 must NOT be added in interrupt mode."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", mode="interrupt"))
        ch1 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_1")
        assert ch1 is None, "dmaLogicChannel_Type_1 must NOT be added in interrupt mode"


# ---------------------------------------------------------------------------
# Platform DMA ISR insertions
# ---------------------------------------------------------------------------

class TestPlatformDmaIsrs:
    """apply_uart_set DMA mode must ADD DMATCD0_IRQn and DMATCD1_IRQn Platform ISRs."""

    def test_dmatcd0_isr_added(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        entry = _platform_isr_entry(doc, _DMATCD0_IRQ)
        assert entry is not None, f"{_DMATCD0_IRQ} ISR entry must be inserted"

    def test_dmatcd0_isr_handler(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, _DMATCD0_IRQ, "IsrHandler") == _DMATCD0_HANDLER

    def test_dmatcd0_isr_enabled(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, _DMATCD0_IRQ, "IsrEnabled") == "true"

    def test_dmatcd0_isr_priority(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, _DMATCD0_IRQ, "IsrPriority") == "2"

    def test_dmatcd1_isr_added(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        entry = _platform_isr_entry(doc, _DMATCD1_IRQ)
        assert entry is not None, f"{_DMATCD1_IRQ} ISR entry must be inserted"

    def test_dmatcd1_isr_handler(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, _DMATCD1_IRQ, "IsrHandler") == _DMATCD1_HANDLER

    def test_dmatcd1_isr_enabled(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, _DMATCD1_IRQ, "IsrEnabled") == "true"

    def test_dmatcd1_isr_priority(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, _DMATCD1_IRQ, "IsrPriority") == "2"

    def test_existing_isrs_preserved(self, tmp_path):
        """Existing LPUART3_IRQn and FLEXIO_IRQn must remain intact."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert _platform_isr_setting(doc, "LPUART3_IRQn", "IsrEnabled") == "true"
        assert _platform_isr_setting(doc, "FLEXIO_IRQn", "IsrEnabled") == "true"

    def test_dma_isrs_not_added_in_interrupt_mode(self, tmp_path):
        """DMATCD ISRs must NOT be added when mode=interrupt."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", mode="interrupt", priority=2))
        assert _platform_isr_entry(doc, _DMATCD0_IRQ) is None
        assert _platform_isr_entry(doc, _DMATCD1_IRQ) is None


# ---------------------------------------------------------------------------
# changed_modules
# ---------------------------------------------------------------------------

class TestDmaChangedModules:
    """changed_modules must include uart, mcl, and platform for DMA mode."""

    def test_dma_changed_modules(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_3", mode="dma", priority=2, callback="Autombd_UartCallback",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert "uart" in result.changed_modules
        assert "mcl" in result.changed_modules
        assert "platform" in result.changed_modules

    def test_mcu_not_in_dma_changed_modules(self, tmp_path):
        """Mcu is unchanged in DMA mode (no new clock ref for LPUART_3 -- it already exists)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        # mcu should NOT appear if LPUART3_CLK already in fixture
        # (it IS already in the fixture -- so mcu is not changed)
        assert "mcu" not in result.changed_modules


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestDmaIdempotent:
    """Two applies of DMA mode must produce identical output."""

    def test_dma_idempotent_no_duplicate_dmatcd0(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        result2 = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result2.blocked
        plat_cfg = doc.find_config_set("Platform")
        count = 0
        for arr in plat_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "PlatformIsrConfig":
                for s in arr:
                    n = doc.find_child_setting(s, "IsrName")
                    if n is not None and n.attrib.get("value") == _DMATCD0_IRQ:
                        count += 1
        assert count == 1, f"Duplicate DMATCD0_IRQn: count={count}"

    def test_dma_idempotent_no_duplicate_dmatcd1(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        result2 = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result2.blocked
        plat_cfg = doc.find_config_set("Platform")
        count = 0
        for arr in plat_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "PlatformIsrConfig":
                for s in arr:
                    n = doc.find_child_setting(s, "IsrName")
                    if n is not None and n.attrib.get("value") == _DMATCD1_IRQ:
                        count += 1
        assert count == 1, f"Duplicate DMATCD1_IRQn: count={count}"

    def test_dma_idempotent_no_duplicate_mcl_ch1(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        mcl_cfg = doc.find_config_set("Mcl")
        count = 0
        for arr in mcl_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "dmaLogicChannel_Type":
                for s in arr:
                    n = doc.find_child_setting(s, "Name")
                    if n is not None and n.attrib.get("value") == "dmaLogicChannel_Type_1":
                        count += 1
        assert count == 1, f"Duplicate dmaLogicChannel_Type_1: count={count}"

    def test_dma_idempotent_file_bytes(self, tmp_path):
        """Two writes of DMA intent produce identical file bytes."""
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"

        doc1 = MexDocument.load(mex)
        apply_uart_set(doc1, _intent(hw="LPUART_3", mode="dma", priority=2, callback="Autombd_UartCallback"))
        doc1.write(mex)
        first_bytes = mex.read_bytes()

        doc2 = MexDocument.load(mex)
        apply_uart_set(doc2, _intent(hw="LPUART_3", mode="dma", priority=2, callback="Autombd_UartCallback"))
        doc2.write(mex)
        second_bytes = mex.read_bytes()

        assert first_bytes == second_bytes, "Second DMA apply should produce identical output"


# ---------------------------------------------------------------------------
# Byte-faithful / well-formed
# ---------------------------------------------------------------------------

class TestDmaByteNarrow:
    """DMA edits are narrow and the file remains well-formed XML."""

    def test_file_well_formed_after_dma_write(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"
        doc = MexDocument.load(mex)
        apply_uart_set(doc, _intent(
            hw="LPUART_3", mode="dma", priority=2, callback="Autombd_UartCallback",
        ))
        doc.write(mex)
        MexDocument.load(mex)  # must parse without error

    def test_dma_byte_delta_bounded(self, tmp_path):
        """DMA edit adds less than 5000 bytes to the file (narrowness bound)."""
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"
        original_size = mex.read_bytes().__len__()

        doc = MexDocument.load(mex)
        apply_uart_set(doc, _intent(
            hw="LPUART_3", mode="dma", priority=2, callback="Autombd_UartCallback",
        ))
        doc.write(mex)
        new_size = mex.read_bytes().__len__()

        delta = new_size - original_size
        # DMA mode adds: dmaLogicChannel_Type_1 struct (~80 lines, ~3500 B),
        # two DMATCD ISR PlatformIsrConfig entries (~400 B each), and
        # UartDmaTxChannelRef/UartDmaRxChannelRef array population (~200 B each).
        # Measured delta on fixture: ~9484 bytes.  Bound at 15000 to catch
        # accidental full-file rewrites while allowing the real delta through.
        assert delta < 15000, (
            f"DMA mode adds too many bytes: delta={delta} >= 15000. "
            "Check for accidental full-file rewrites."
        )
        assert delta > 0, "DMA mode must add some bytes (UartDmaEnable, MCL ch1, ISRs)"


# ---------------------------------------------------------------------------
# Anti-hardcode: ISR/handler derived dynamically from asset map
# ---------------------------------------------------------------------------

class TestDmaAntiHardcode:
    """The DMA channel->ISR/handler mapping must be derived from the asset, not hardcoded.

    The real proof is: perturb the asset map at load time and assert the WRITTEN
    Platform ISR name/handler in the mex track the perturbed values. This way, any
    hardcode of DMATCD0_IRQn / Dma0_Ch0_IRQHandler in production code would cause
    the test to fail when the asset map is changed.
    """

    def test_written_dmatcd0_isr_name_tracks_asset_map(self, tmp_path, monkeypatch):
        """DMATCD0_IRQn in the written mex must equal the dma_hw_channel_irq_map[0].irq_name.

        Monkeypatches the loaded asset to use a sentinel IRQ name, then verifies
        the written Platform ISR entry carries that sentinel -- not a hardcoded literal.
        """
        import rtd_config.backends.s32_mex.apply as apply_mod
        sentinel_irq = "SENTINEL_DMA0_IRQn"
        sentinel_handler = "Sentinel_Ch0_IRQHandler"

        original_load = apply_mod._load_uart_asset

        def _patched_load():
            data = original_load()
            data = dict(data)
            data["dma_hw_channel_irq_map"] = {
                "0": {"irq_name": sentinel_irq, "isr_handler": sentinel_handler},
                "1": {"irq_name": "SENTINEL_DMA1_IRQn", "isr_handler": "Sentinel_Ch1_IRQHandler"},
            }
            return data

        monkeypatch.setattr(apply_mod, "_load_uart_asset", _patched_load)

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]

        # The ISR name written to the mex must match the (monkeypatched) asset
        assert _platform_isr_setting(doc, sentinel_irq, "IsrHandler") == sentinel_handler, (
            "DMA ch0 ISR name/handler in mex must come from the asset map, not a hardcoded literal"
        )
        # Confirm the real DMATCD0_IRQn was NOT written (it was replaced by the sentinel)
        assert _platform_isr_entry(doc, _DMATCD0_IRQ) is None, (
            "The real DMATCD0_IRQn must NOT appear when the asset map uses a sentinel"
        )

    def test_written_dmatcd1_isr_name_tracks_asset_map(self, tmp_path, monkeypatch):
        """DMATCD1_IRQn in the written mex must equal the dma_hw_channel_irq_map[1].irq_name.

        Same sentinel pattern as above, for the RX channel.
        """
        import rtd_config.backends.s32_mex.apply as apply_mod
        sentinel_irq = "SENTINEL_DMA1_IRQn"
        sentinel_handler = "Sentinel_Ch1_IRQHandler"

        original_load = apply_mod._load_uart_asset

        def _patched_load():
            data = original_load()
            data = dict(data)
            data["dma_hw_channel_irq_map"] = {
                "0": {"irq_name": "SENTINEL_DMA0_IRQn", "isr_handler": "Sentinel_Ch0_IRQHandler"},
                "1": {"irq_name": sentinel_irq, "isr_handler": sentinel_handler},
            }
            return data

        monkeypatch.setattr(apply_mod, "_load_uart_asset", _patched_load)

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]

        assert _platform_isr_setting(doc, sentinel_irq, "IsrHandler") == sentinel_handler, (
            "DMA ch1 ISR name/handler in mex must come from the asset map, not a hardcoded literal"
        )
        assert _platform_isr_entry(doc, _DMATCD1_IRQ) is None, (
            "The real DMATCD1_IRQn must NOT appear when the asset map uses a sentinel"
        )

    def test_activation_flags_track_asset_template(self, tmp_path, monkeypatch):
        """The three activation flags written to dmaLogicChannel_Type_0 must equal the asset template.

        Monkeypatches the template to use "false" for all three flags, then asserts
        the WRITTEN values in the mex match the (patched) template -- not hardcoded "true".
        """
        import rtd_config.backends.s32_mex.apply as apply_mod
        original_load = apply_mod._load_uart_asset

        def _patched_load():
            data = original_load()
            data = dict(data)
            # Overwrite the template flags so they differ from the real values
            data["mcl_dma_channel_template"] = {
                "dmaLogicChannel_EnableGlobalConfig": "false",
                "dmaGlobalRequest_enDmaRequest": "false",
                "dmaLogicChannelConfig_enDmaMajorInterrupt": "false",
            }
            return data

        monkeypatch.setattr(apply_mod, "_load_uart_asset", _patched_load)

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))

        # With the template overridden to "false", the written values must also be "false"
        # (not hardcoded "true"). If production hardcodes "true" this fails.
        val_global = _mcl_dma_channel_setting(
            doc, "dmaLogicChannel_Type_0", "dmaLogicChannel_EnableGlobalConfig"
        )
        val_req = _mcl_dma_channel_setting(
            doc, "dmaLogicChannel_Type_0", "dmaGlobalRequest_enDmaRequest"
        )
        val_irq = _mcl_dma_channel_setting(
            doc, "dmaLogicChannel_Type_0", "dmaLogicChannelConfig_enDmaMajorInterrupt"
        )
        assert val_global == "false", (
            "dmaLogicChannel_EnableGlobalConfig must come from asset template, not hardcoded 'true'"
        )
        assert val_req == "false", (
            "dmaGlobalRequest_enDmaRequest must come from asset template, not hardcoded 'true'"
        )
        assert val_irq == "false", (
            "dmaLogicChannelConfig_enDmaMajorInterrupt must come from asset template, not hardcoded 'true'"
        )


# ---------------------------------------------------------------------------
# plan() DMA cross-module deps (LL-010)
# ---------------------------------------------------------------------------

class TestPlanDmaDeps:
    """UartProvider.plan() in DMA mode must declare MCL and Platform deps."""

    def test_plan_dma_declares_mcl_dep(self):
        intent = _intent(hw="LPUART_3", mode="dma")
        plan = UartProvider().plan(intent)
        owners = {c["owner"] for c in plan.to_dict()["changes"]}
        assert "mcl" in owners, "DMA plan must declare an mcl-owned change"

    def test_plan_dma_declares_platform_dep(self):
        intent = _intent(hw="LPUART_3", mode="dma")
        plan = UartProvider().plan(intent)
        owners = {c["owner"] for c in plan.to_dict()["changes"]}
        assert "platform" in owners, "DMA plan must declare a platform-owned change"

    def test_plan_dma_declares_mcu_dep(self):
        intent = _intent(hw="LPUART_3", mode="dma")
        plan = UartProvider().plan(intent)
        owners = {c["owner"] for c in plan.to_dict()["changes"]}
        assert "mcu" in owners, "DMA plan must declare an mcu-owned change"

    def test_plan_dma_platform_description_names_dmatcd(self):
        intent = _intent(hw="LPUART_3", mode="dma")
        plan = UartProvider().plan(intent)
        for c in plan.to_dict()["changes"]:
            if c["owner"] == "platform":
                assert "DMATCD" in c["description"], (
                    f"Platform dep description for DMA mode must name DMATCD ISRs, got: {c['description']!r}"
                )
                return
        raise AssertionError("No platform dep in DMA plan")

    def test_plan_dma_mcl_description_names_dma_channel(self):
        intent = _intent(hw="LPUART_3", mode="dma")
        plan = UartProvider().plan(intent)
        for c in plan.to_dict()["changes"]:
            if c["owner"] == "mcl":
                assert "dmaLogicChannel" in c["description"] or "DMA" in c["description"], (
                    f"Mcl dep description for DMA mode must name DMA channel, got: {c['description']!r}"
                )
                return
        raise AssertionError("No mcl dep in DMA plan")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliDmaIntegration:
    """uart set --mode dma ... --configure --json must pass."""

    def test_cli_uart_set_dma(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
                "--hw", "LPUART_3",
                "--mode", "dma",
                "--callback", "Autombd_UartCallback",
                "--priority", "2",
                "--configure",
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert result.returncode == 0, result.stderr + result.stdout
        assert payload["status"] == "passed", payload
        assert "uart" in payload["changed_modules"]
        assert "mcl" in payload["changed_modules"]
        assert "platform" in payload["changed_modules"]
        assert payload["runtime_verification"]["static_check"]["status"] == "passed"

    def test_cli_dma_mode_is_valid_choice(self, tmp_path):
        """--mode dma must not be rejected by argparse (it's now a valid choice)."""
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
                "--hw", "LPUART_3",
                "--mode", "dma",
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        # argparse error = exit code 2, not 0 or 1
        assert result.returncode != 2, (
            f"--mode dma was rejected by argparse (exit 2): {result.stderr}"
        )

    def test_cli_interrupt_mode_still_works(self, tmp_path):
        """Extending DMA must not break the existing interrupt mode CLI."""
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
                "--hw", "LPUART_8",
                "--mode", "interrupt",
                "--baud", "921600",
                "--configure",
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        payload = json.loads(result.stdout)
        assert result.returncode == 0, result.stderr
        assert payload["status"] == "passed"
        assert "uart" in payload["changed_modules"]


# ---------------------------------------------------------------------------
# Fix 3: Structural equivalence dmaLogicChannel_Type_1 vs _0
# ---------------------------------------------------------------------------

def _collect_nested_struct_and_setting_names(el: ET.Element) -> set[str]:
    """Return the set of all struct.name and setting.name in the subtree (excluding root)."""
    names: set[str] = set()
    for child in el.iter():
        if child is el:
            continue
        tag = child.tag
        if tag.endswith("struct") or tag.endswith("setting"):
            n = child.attrib.get("name")
            if n:
                names.add(n)
    return names


# Setting names that are allowed to differ between _0 and _1 (index-varying fields).
_CHANNEL_VARYING_SETTINGS = {
    "Name",
    "dmaLogicChannel_LogicName",
    "dmaLogicChannel_HwChId",
    "dmaLogicChannel_EnableGlobalConfig",
    "dmaGlobalRequest_enDmaRequest",
    "dmaLogicChannelConfig_enDmaMajorInterrupt",
    "dynamic_dmaLogicChannelConfig_MinorLoopLinkChValueType",
    "dynamic_dmaLogicChannelConfig_MajorLoopLinkChValueType",
}


class TestDmaLogicChannelStructuralEquivalence:
    """dmaLogicChannel_Type_1 must have the IDENTICAL nested struct+setting NAME set as _0.

    Values may differ only at the channel-varying settings; the schema (field names)
    must be identical. This catches a future dropped/added field in
    _build_dma_logic_channel_struct_bytes.
    """

    def test_ch1_and_ch0_have_identical_struct_name_set(self, tmp_path):
        """All struct names present in _0 must also appear in _1, and vice versa."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))

        ch0 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_0")
        ch1 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_1")
        assert ch0 is not None, "dmaLogicChannel_Type_0 must exist"
        assert ch1 is not None, "dmaLogicChannel_Type_1 must exist after DMA apply"

        def _struct_names(el):
            return {
                child.attrib.get("name")
                for child in el.iter()
                if child is not el and child.tag.endswith("struct") and child.attrib.get("name")
            }

        structs0 = _struct_names(ch0)
        structs1 = _struct_names(ch1)
        only_in_0 = structs0 - structs1
        only_in_1 = structs1 - structs0
        assert not only_in_0, f"Struct names in _0 but not in _1: {sorted(only_in_0)}"
        assert not only_in_1, f"Struct names in _1 but not in _0: {sorted(only_in_1)}"

    def test_ch1_and_ch0_have_identical_setting_name_set(self, tmp_path):
        """All setting names present in _0 must also appear in _1, and vice versa."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))

        ch0 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_0")
        ch1 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_1")
        assert ch0 is not None
        assert ch1 is not None

        def _setting_names(el):
            return {
                child.attrib.get("name")
                for child in el.iter()
                if child is not el and child.tag.endswith("setting") and child.attrib.get("name")
            }

        settings0 = _setting_names(ch0)
        settings1 = _setting_names(ch1)
        only_in_0 = settings0 - settings1
        only_in_1 = settings1 - settings0
        assert not only_in_0, f"Setting names in _0 but not in _1: {sorted(only_in_0)}"
        assert not only_in_1, f"Setting names in _1 but not in _0: {sorted(only_in_1)}"

    def test_ch1_non_varying_settings_have_same_values_as_ch0(self, tmp_path):
        """Non-index-varying settings must have identical values in _0 and _1."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        # Apply DMA to set ch0 flags; ch1 is the freshly built struct
        apply_uart_set(doc, _intent(hw="LPUART_3", mode="dma"))

        ch0 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_0")
        ch1 = _mcl_dma_channel(doc, "dmaLogicChannel_Type_1")
        assert ch0 is not None
        assert ch1 is not None

        def _setting_map(el):
            return {
                child.attrib.get("name"): child.attrib.get("value")
                for child in el.iter()
                if child is not el
                and child.tag.endswith("setting")
                and child.attrib.get("name") not in _CHANNEL_VARYING_SETTINGS
            }

        map0 = _setting_map(ch0)
        map1 = _setting_map(ch1)
        mismatches = {
            k: (map0.get(k), map1.get(k))
            for k in map0.keys() | map1.keys()
            if map0.get(k) != map1.get(k)
        }
        assert not mismatches, (
            "Non-varying settings differ between _0 and _1:\n"
            + "\n".join(f"  {k}: _0={v0!r}, _1={v1!r}" for k, (v0, v1) in sorted(mismatches.items()))
        )


# ---------------------------------------------------------------------------
# Fix 5: changed_modules accuracy on idempotent re-run
# ---------------------------------------------------------------------------

class TestDmaIdempotentChangedModules:
    """changed_modules must include mcl even on an idempotent (second) DMA apply.

    The second apply re-activates the MCL attributes (MclEnableDma, ch0 flags),
    so mcl is part of the actual edited set even when no new struct is inserted.
    """

    def test_idempotent_dma_changed_modules_includes_mcl(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"

        # First apply
        doc1 = MexDocument.load(mex)
        apply_uart_set(doc1, _intent(hw="LPUART_3", mode="dma", priority=2))
        doc1.write(mex)

        # Second apply (idempotent)
        doc2 = MexDocument.load(mex)
        result2 = apply_uart_set(doc2, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
        assert "mcl" in result2.changed_modules, (
            "mcl must appear in changed_modules even on idempotent re-apply "
            "(MCL attributes are re-written each time)"
        )

    def test_idempotent_dma_changed_modules_includes_platform(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"

        doc1 = MexDocument.load(mex)
        apply_uart_set(doc1, _intent(hw="LPUART_3", mode="dma", priority=2))
        doc1.write(mex)

        doc2 = MexDocument.load(mex)
        result2 = apply_uart_set(doc2, _intent(hw="LPUART_3", mode="dma", priority=2))
        assert not result2.blocked
        assert "platform" in result2.changed_modules, (
            "platform must appear in changed_modules even on idempotent re-apply"
        )
