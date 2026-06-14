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
# File:        test_uart_flexio_add_channel.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-13
# Version:     0.1.0
# Description: Deterministic tests for RTD-MEX-UART-002:
#              uart add-flexio-channel command -- FlexIO Tx+Rx channel pair creation.
#              Covers: 2 MCL logic channels, 2 Uart FlexIO channels, callback, Platform
#              ISR idempotency, Mcu clock idempotency, changed_modules, byte-narrow,
#              idempotency, anti-hardcode, CLI integration, plan() deps.
# =================================================================================

"""Deterministic tests for apply_uart_add_flexio_channel (RTD-MEX-UART-002).

Fixture: tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/Uart_Example.mex

Ground truth (from brief, Uart.xdm, Mcl.xdm, fixture):
  - MCL: existing UART_TX (CHANNEL_0/PIN_0), UART_RX (CHANNEL_1/PIN_1)
  - Uart: existing channel ids 0,1,2; next = 3 (TX), 4 (RX)
  - New MCL channels: UART2_TX (CHANNEL_2/PIN_2), UART2_RX (CHANNEL_3/PIN_3)
  - FlexIO Uart fields: UartHwUsing=FLEXIO_IP, UartClockRef=.../FLEXIO_CLK,
    FlexioUartInteruptDmaMethod=FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS,
    FlexioDmaChannelRef=<empty array>, DesireBaudrate=FLEXIO_UART_BAUDRATE_921600,
    CustomTimerDecrement=FLEXIO_TIMER_DECREMENT_FXIO_CLK_SHIFT_TMR,
    CustomBaudrateDivider=0, bitCount=FLEXIO_UART_IP_8_BITS_PER_CHAR,
    driverDirection=TX/RX
  - Platform: FLEXIO_IRQn already present; idempotent (no duplicate)
  - Mcu: FLEXIO_CLK already present; idempotent (no duplicate)
"""
from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from rtd_config.backends.s32_mex.apply import apply_uart_add_flexio_channel
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.intent import Intent
from rtd_config.modules.uart import UartProvider
from tests.fixtures import copy_uart_fixture

# ---------------------------------------------------------------------------
# Asset path
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_UART_ASSET = (
    _REPO_ROOT / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "uart" / "uart.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "uart", "action": "add_flexio_channel", "payload": payload})


def _default_intent(**extra) -> Intent:
    """Standard UART-002 intent: 921600 baud, 8-bit, interrupt, callback."""
    payload = {
        "baud": 921600,
        "word_length": 8,
        "mode": "interrupt",
        "callback": "Autombd_UartCallback",
    }
    payload.update(extra)
    return _intent(**payload)


def _mcl_channel_by_name(doc: MexDocument, name: str) -> ET.Element | None:
    """Return the FlexioMclLogicChannels struct with Name==name."""
    mcl_cfg = doc.find_config_set("Mcl")
    if mcl_cfg is None:
        return None
    for arr in mcl_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "FlexioMclLogicChannels":
            for s in arr:
                if not s.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(s, "Name")
                if n is not None and n.attrib.get("value") == name:
                    return s
    return None


def _mcl_channel_setting(doc: MexDocument, channel_name: str, field: str) -> str | None:
    s = _mcl_channel_by_name(doc, channel_name)
    if s is None:
        return None
    f = doc.find_child_setting(s, field)
    return f.attrib.get("value") if f is not None else None


def _uart_channel_by_name(doc: MexDocument, name: str) -> ET.Element | None:
    """Return UartChannel struct with Name==name."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return None
    for arr in uart_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "UartChannel":
            for ch in arr:
                if not ch.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(ch, "Name")
                if n is not None and n.attrib.get("value") == name:
                    return ch
    return None


def _uart_channel_setting(doc: MexDocument, ch_name: str, field: str) -> str | None:
    ch = _uart_channel_by_name(doc, ch_name)
    if ch is None:
        return None
    s = doc.find_child_setting(ch, field)
    return s.attrib.get("value") if s is not None else None


def _flexio_cfg_setting(doc: MexDocument, ch_name: str, field: str) -> str | None:
    """Return a field value from a UartChannel's FlexioModuleConfiguration sub-struct."""
    ch = _uart_channel_by_name(doc, ch_name)
    if ch is None:
        return None
    for el in ch.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "FlexioModuleConfiguration":
            s = doc.find_child_setting(el, field)
            return s.attrib.get("value") if s is not None else None
    return None


def _count_uart_channels_with_hw(doc: MexDocument, hw_using: str) -> int:
    """Count UartChannel structs with UartHwUsing==hw_using."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return 0
    count = 0
    for arr in uart_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "UartChannel":
            for ch in arr:
                if not ch.tag.endswith("struct"):
                    continue
                u = doc.find_child_setting(ch, "UartHwUsing")
                if u is not None and u.attrib.get("value") == hw_using:
                    count += 1
    return count


def _all_uart_channel_ids(doc: MexDocument) -> list[int]:
    """Return all UartChannelId values as integers."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return []
    ids = []
    for arr in uart_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "UartChannel":
            for ch in arr:
                if not ch.tag.endswith("struct"):
                    continue
                s = doc.find_child_setting(ch, "UartChannelId")
                if s is not None and s.attrib.get("value"):
                    try:
                        ids.append(int(s.attrib["value"]))
                    except ValueError:
                        pass
    return ids


def _platform_isr_setting(doc: MexDocument, isr_name: str, field: str) -> str | None:
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
                    f = doc.find_child_setting(s, field)
                    return f.attrib.get("value") if f is not None else None
    return None


def _count_platform_isr_entries(doc: MexDocument, isr_name: str) -> int:
    plat_cfg = doc.find_config_set("Platform")
    if plat_cfg is None:
        return 0
    count = 0
    for arr in plat_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "PlatformIsrConfig":
            for s in arr:
                if not s.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(s, "IsrName")
                if n is not None and n.attrib.get("value") == isr_name:
                    count += 1
    return count


def _mcu_clock_ref(doc: MexDocument, ref_name: str) -> ET.Element | None:
    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        return None
    for arr in mcu_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "McuClockReferencePoint":
            for s in arr:
                if not s.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(s, "Name")
                if n is not None and n.attrib.get("value") == ref_name:
                    return s
    return None


def _count_mcu_clock_refs(doc: MexDocument, ref_name: str) -> int:
    mcu_cfg = doc.find_config_set("Mcu")
    if mcu_cfg is None:
        return 0
    count = 0
    for arr in mcu_cfg.iter():
        if arr.tag.endswith("array") and arr.attrib.get("name") == "McuClockReferencePoint":
            for s in arr:
                if not s.tag.endswith("struct"):
                    continue
                n = doc.find_child_setting(s, "Name")
                if n is not None and n.attrib.get("value") == ref_name:
                    count += 1
    return count


def _gen_cfg_setting(doc: MexDocument, name: str) -> str | None:
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return None
    for el in uart_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "GeneralConfiguration":
            s = doc.find_child_setting(el, name)
            return s.attrib.get("value") if s is not None else None
    return None


def _gen_cfg_callback_value(doc: MexDocument, index: int) -> str | None:
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


# ---------------------------------------------------------------------------
# uart.json asset -- FlexIO-specific enum domains (LL-012 pin)
# ---------------------------------------------------------------------------

class TestUartAssetFlexioEnums:
    """uart.json must contain the FlexIO-specific enum domains for UART-002."""

    def test_flexio_method_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "FlexioUartInteruptDmaMethod" in enums

    def test_flexio_method_has_interrupts(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        methods = data["enum_domains"]["FlexioUartInteruptDmaMethod"]
        assert "FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS" in methods

    def test_flexio_baud_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "FlexioDesireBaudrate" in enums

    def test_flexio_baud_921600_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["FlexioDesireBaudrate"]
        assert "FLEXIO_UART_BAUDRATE_921600" in bauds

    def test_flexio_bit_count_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "FlexioBitCount" in enums

    def test_flexio_bit_count_8_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        values = data["enum_domains"]["FlexioBitCount"]
        assert "FLEXIO_UART_IP_8_BITS_PER_CHAR" in values

    def test_flexio_driver_direction_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "FlexioDriverDirection" in enums

    def test_flexio_driver_direction_tx_rx_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        directions = data["enum_domains"]["FlexioDriverDirection"]
        assert "FLEXIO_UART_IP_DIRECTION_TX" in directions
        assert "FLEXIO_UART_IP_DIRECTION_RX" in directions

    def test_flexio_instance_entry_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        mapping = data.get("instance_irq_clock_map", {})
        assert "FLEXIO" in mapping

    def test_flexio_instance_entry_fields(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        entry = data["instance_irq_clock_map"]["FLEXIO"]
        assert entry["irq_name"] == "FLEXIO_IRQn"
        assert entry["isr_handler"] == "MCL_FLEXIO_ISR"
        assert entry["clock_ref_name"] == "FLEXIO_CLK"
        assert entry["clock_select"] == "CORE_CLK"

    def test_flexio_channel_template_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        assert "flexio_channel_template" in data

    def test_flexio_channel_template_field_order(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        tmpl = data["flexio_channel_template"]
        fields = tmpl["field_order"]
        assert "UartHwChannelRef" in fields
        assert "FlexioUartInteruptDmaMethod" in fields
        assert "FlexioDmaChannelRef" in fields
        assert "DesireBaudrate" in fields
        assert "CustomTimerDecrement" in fields
        assert "CustomBaudrateDivider" in fields
        assert "bitCount" in fields
        assert "driverDirection" in fields

    def test_mcl_ref_path_pattern_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        assert "mcl_ref_path_pattern" in data


# ---------------------------------------------------------------------------
# MCL channel creation
# ---------------------------------------------------------------------------

class TestMclChannelCreation:
    """Two new MCL FlexIO logic channels must be created with correct ids."""

    def test_tx_mcl_channel_created(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _mcl_channel_by_name(doc, "UART2_TX") is not None, "UART2_TX MCL channel must be created"

    def test_rx_mcl_channel_created(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _mcl_channel_by_name(doc, "UART2_RX") is not None, "UART2_RX MCL channel must be created"

    def test_tx_mcl_channel_id_is_channel_2(self, tmp_path):
        """TX MCL channel gets next-available CHANNEL_2 (existing: 0, 1)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART2_TX", "FlexioMclChannelId") == "CHANNEL_2"

    def test_tx_mcl_pin_id_is_pin_2(self, tmp_path):
        """TX MCL channel gets next-available PIN_2 (existing: 0, 1)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART2_TX", "FlexioMclPinId") == "PIN_2"

    def test_rx_mcl_channel_id_is_channel_3(self, tmp_path):
        """RX MCL channel gets next-available CHANNEL_3 (after TX was added)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART2_RX", "FlexioMclChannelId") == "CHANNEL_3"

    def test_rx_mcl_pin_id_is_pin_3(self, tmp_path):
        """RX MCL channel gets next-available PIN_3 (after TX was added)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART2_RX", "FlexioMclPinId") == "PIN_3"

    def test_mcl_add_pin_enable_false_tx(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART2_TX", "FlexioMclAddPinEnable") == "false"

    def test_mcl_add_channel_enable_false_rx(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART2_RX", "FlexioMclAddChannelEnable") == "false"

    def test_existing_mcl_channels_preserved(self, tmp_path):
        """Existing UART_TX (CHANNEL_0/PIN_0) and UART_RX (CHANNEL_1/PIN_1) must remain."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcl_channel_setting(doc, "UART_TX", "FlexioMclChannelId") == "CHANNEL_0"
        assert _mcl_channel_setting(doc, "UART_RX", "FlexioMclChannelId") == "CHANNEL_1"
        assert _mcl_channel_setting(doc, "UART_TX", "FlexioMclPinId") == "PIN_0"
        assert _mcl_channel_setting(doc, "UART_RX", "FlexioMclPinId") == "PIN_1"


# ---------------------------------------------------------------------------
# Uart channel creation
# ---------------------------------------------------------------------------

class TestUartChannelCreation:
    """Two new FLEXIO_IP Uart channels must be created with correct fields."""

    def test_tx_uart_channel_created(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _uart_channel_by_name(doc, "UART2_TX") is not None

    def test_rx_uart_channel_created(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _uart_channel_by_name(doc, "UART2_RX") is not None

    def test_tx_hw_using_flexio(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _uart_channel_setting(doc, "UART2_TX", "UartHwUsing") == "FLEXIO_IP"

    def test_rx_hw_using_flexio(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _uart_channel_setting(doc, "UART2_RX", "UartHwUsing") == "FLEXIO_IP"

    def test_tx_channel_id_is_3(self, tmp_path):
        """TX channel gets UartChannelId=3 (next after existing 0,1,2)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _uart_channel_setting(doc, "UART2_TX", "UartChannelId") == "3"

    def test_rx_channel_id_is_4(self, tmp_path):
        """RX channel gets UartChannelId=4 (next after TX=3)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _uart_channel_setting(doc, "UART2_RX", "UartChannelId") == "4"

    def test_tx_clock_ref_is_flexio_clk(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ref = _uart_channel_setting(doc, "UART2_TX", "UartClockRef")
        assert ref is not None
        assert "FLEXIO_CLK" in ref
        assert ref.startswith("/Mcu/")

    def test_rx_clock_ref_is_flexio_clk(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ref = _uart_channel_setting(doc, "UART2_RX", "UartClockRef")
        assert ref is not None
        assert "FLEXIO_CLK" in ref


# ---------------------------------------------------------------------------
# FlexioModuleConfiguration fields
# ---------------------------------------------------------------------------

class TestFlexioChannelFields:
    """FlexioModuleConfiguration fields must match Uart.xdm ground truth."""

    def test_tx_method_is_interrupts(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_TX", "FlexioUartInteruptDmaMethod") == \
            "FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS"

    def test_rx_method_is_interrupts(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_RX", "FlexioUartInteruptDmaMethod") == \
            "FLEXIO_UART_IP_DRIVER_TYPE_INTERRUPTS"

    def test_tx_baud_is_921600(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_TX", "DesireBaudrate") == \
            "FLEXIO_UART_BAUDRATE_921600"

    def test_rx_baud_is_921600(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_RX", "DesireBaudrate") == \
            "FLEXIO_UART_BAUDRATE_921600"

    def test_tx_bit_count_8(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_TX", "bitCount") == \
            "FLEXIO_UART_IP_8_BITS_PER_CHAR"

    def test_rx_bit_count_8(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_RX", "bitCount") == \
            "FLEXIO_UART_IP_8_BITS_PER_CHAR"

    def test_tx_direction_is_tx(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_TX", "driverDirection") == \
            "FLEXIO_UART_IP_DIRECTION_TX"

    def test_rx_direction_is_rx(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_RX", "driverDirection") == \
            "FLEXIO_UART_IP_DIRECTION_RX"

    def test_tx_timer_decrement(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_TX", "CustomTimerDecrement") == \
            "FLEXIO_TIMER_DECREMENT_FXIO_CLK_SHIFT_TMR"

    def test_tx_custom_baud_divider_zero(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _flexio_cfg_setting(doc, "UART2_TX", "CustomBaudrateDivider") == "0"

    def test_tx_hw_channel_ref_points_to_uart2_tx_mcl(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ref = _flexio_cfg_setting(doc, "UART2_TX", "UartHwChannelRef")
        assert ref is not None
        assert "UART2_TX" in ref
        assert ref.startswith("/Mcl/")

    def test_rx_hw_channel_ref_points_to_uart2_rx_mcl(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ref = _flexio_cfg_setting(doc, "UART2_RX", "UartHwChannelRef")
        assert ref is not None
        assert "UART2_RX" in ref
        assert ref.startswith("/Mcl/")


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------

class TestFlexioCallback:
    """Callback must be set in GeneralConfiguration."""

    def test_callback_capability_enabled(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _gen_cfg_setting(doc, "UartCallbackCapability") == "true"

    def test_callback_name_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _gen_cfg_callback_value(doc, 0) == "Autombd_UartCallback"

    def test_no_callback_leaves_capability_unchanged(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _intent(baud=921600, mode="interrupt"))
        # UartCallbackCapability should remain false when no callback provided
        assert _gen_cfg_setting(doc, "UartCallbackCapability") == "false"


# ---------------------------------------------------------------------------
# Platform FLEXIO_IRQn idempotency
# ---------------------------------------------------------------------------

class TestPlatformFlexioIsr:
    """FLEXIO_IRQn is already present in fixture; must remain present+enabled, no duplicate."""

    def test_flexio_irq_still_present(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _platform_isr_setting(doc, "FLEXIO_IRQn", "IsrEnabled") == "true"

    def test_flexio_irq_handler_unchanged(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _platform_isr_setting(doc, "FLEXIO_IRQn", "IsrHandler") == "MCL_FLEXIO_ISR"

    def test_no_duplicate_flexio_irq(self, tmp_path):
        """Must not add a second FLEXIO_IRQn entry."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _count_platform_isr_entries(doc, "FLEXIO_IRQn") == 1

    def test_lpuart3_irq_preserved(self, tmp_path):
        """The LPUART3_IRQn entry from fixture must remain undisturbed."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _platform_isr_setting(doc, "LPUART3_IRQn", "IsrEnabled") == "true"


# ---------------------------------------------------------------------------
# Mcu FLEXIO_CLK idempotency
# ---------------------------------------------------------------------------

class TestMcuFlexioClock:
    """FLEXIO_CLK is already present in fixture; must remain, no duplicate."""

    def test_flexio_clk_still_present(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcu_clock_ref(doc, "FLEXIO_CLK") is not None

    def test_no_duplicate_flexio_clk(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _count_mcu_clock_refs(doc, "FLEXIO_CLK") == 1

    def test_lpuart3_clk_preserved(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        assert _mcu_clock_ref(doc, "LPUART3_CLK") is not None


# ---------------------------------------------------------------------------
# changed_modules
# ---------------------------------------------------------------------------

class TestChangedModules:
    """changed_modules must include uart and mcl."""

    def test_changed_modules_includes_uart(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert "uart" in result.changed_modules

    def test_changed_modules_includes_mcl(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert "mcl" in result.changed_modules


# ---------------------------------------------------------------------------
# Existing channels untouched
# ---------------------------------------------------------------------------

class TestExistingChannelsUntouched:
    """Existing Uart channels (LPUART3, Flexio0_Tx, Flexio1_Rx) must not be modified."""

    def test_lpuart3_channel_name_unchanged(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ch = _uart_channel_by_name(doc, "LPUART3")
        assert ch is not None

    def test_flexio0_tx_channel_unchanged(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ch = _uart_channel_by_name(doc, "Flexio0_Tx")
        assert ch is not None
        s = doc.find_child_setting(ch, "UartChannelId")
        assert s is not None and s.attrib.get("value") == "1"

    def test_flexio1_rx_channel_unchanged(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ch = _uart_channel_by_name(doc, "Flexio1_Rx")
        assert ch is not None
        s = doc.find_child_setting(ch, "UartChannelId")
        assert s is not None and s.attrib.get("value") == "2"

    def test_total_uart_channels_is_5(self, tmp_path):
        """After UART-002, there must be exactly 5 Uart channels."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        ids = _all_uart_channel_ids(doc)
        assert len(ids) == 5, f"Expected 5 channels, got {len(ids)}: {sorted(ids)}"
        assert sorted(ids) == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Byte-narrow + well-formed
# ---------------------------------------------------------------------------

class TestByteNarrowFlexio:
    """The written .mex must remain well-formed and edits must be narrow."""

    def test_file_well_formed_after_write(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"
        doc = MexDocument.load(mex)
        apply_uart_add_flexio_channel(doc, _default_intent())
        doc.write(mex)
        MexDocument.load(mex)

    def test_byte_footprint_bounded(self, tmp_path):
        """Net byte growth must be bounded: 2 MCL structs + 2 Uart channel structs.

        Measured: 2 MCL structs (~300 bytes each) + 2 Uart channel structs (each
        contains DetailModuleConfiguration + FlexioModuleConfiguration ~1700 bytes)
        = ~4000 bytes content + line endings + indentation. Measured actual delta
        on the fixture: ~7343 bytes. Bound = measured * 1.4 = ~10300, rounded to
        11000 for safe headroom per LL-015 (measure + headroom).
        """
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"
        original_size = mex.stat().st_size
        doc = MexDocument.load(mex)
        apply_uart_add_flexio_channel(doc, _default_intent())
        doc.write(mex)
        new_size = mex.stat().st_size
        delta = new_size - original_size
        assert delta > 0, "File must grow after adding channels"
        assert delta < 11000, f"Byte growth {delta} exceeds 11000 bound (LL-015)"

    def test_idempotent_write(self, tmp_path):
        """Two writes of the same intent produce identical file bytes."""
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"

        doc1 = MexDocument.load(mex)
        apply_uart_add_flexio_channel(doc1, _default_intent())
        doc1.write(mex)
        first_bytes = mex.read_bytes()

        doc2 = MexDocument.load(mex)
        apply_uart_add_flexio_channel(doc2, _default_intent())
        doc2.write(mex)
        second_bytes = mex.read_bytes()

        assert first_bytes == second_bytes, "Second apply must produce identical output"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Re-running add-flexio-channel on the same doc must be a no-op."""

    def test_no_duplicate_mcl_channels(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        result2 = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
        # Count UART2_TX MCL entries
        mcl_cfg = doc.find_config_set("Mcl")
        count = 0
        for arr in mcl_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "FlexioMclLogicChannels":
                for s in arr:
                    if not s.tag.endswith("struct"):
                        continue
                    n = doc.find_child_setting(s, "Name")
                    if n is not None and n.attrib.get("value") == "UART2_TX":
                        count += 1
        assert count == 1, f"Duplicate UART2_TX MCL channel: count={count}"

    def test_no_duplicate_uart_channels(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())
        result2 = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result2.blocked
        # Total channels must still be 5
        ids = _all_uart_channel_ids(doc)
        assert len(ids) == 5, f"After idempotent reapply, expected 5 channels, got {len(ids)}"


# ---------------------------------------------------------------------------
# Anti-hardcode: dynamic index computation
# ---------------------------------------------------------------------------

class TestAntiHardcode:
    """When fixture already has more MCL/Uart entries, ids are computed (not fixed)."""

    def test_new_mcl_ids_dynamic(self, tmp_path):
        """After adding one MCL channel first, UART-002 gets ids 3+4, not 2+3."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        # Pre-add a channel to bump up the max existing index
        from rtd_config.backends.s32_mex.apply import apply_mcl_set
        from rtd_config.intent import Intent as _Intent
        pre_intent = _Intent.from_dict({
            "module": "mcl", "action": "set",
            "payload": {"add_flexio_logic_channel": "PRE_EXISTING"},
        })
        pre_result = apply_mcl_set(doc, pre_intent)
        assert not pre_result.blocked, [d.to_dict() for d in pre_result.diagnostics]
        # Now apply UART-002 -- it should compute ids starting from 3 (TX) and 4 (RX)
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        # TX gets CHANNEL_3 (max was 2 after PRE_EXISTING), RX gets CHANNEL_4
        assert _mcl_channel_setting(doc, "UART2_TX", "FlexioMclChannelId") == "CHANNEL_3"
        assert _mcl_channel_setting(doc, "UART2_RX", "FlexioMclChannelId") == "CHANNEL_4"

    def test_new_uart_channel_ids_dynamic(self, tmp_path):
        """When fixture has more Uart channels, new ids are max+1, max+2."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        # Check that ids 3 and 4 are computed (fixture has 0,1,2)
        apply_uart_add_flexio_channel(doc, _default_intent())
        ids = _all_uart_channel_ids(doc)
        # New channels must have the two highest ids
        assert max(ids) == 4
        assert 3 in ids and 4 in ids


# ---------------------------------------------------------------------------
# plan() cross-module deps (LL-010)
# ---------------------------------------------------------------------------

class TestPlanDependenciesFlexio:
    """UartProvider.plan() for FlexIO create path must declare correct deps."""

    def _plan_changes(self, hw: str = "FLEXIO") -> list[dict]:
        intent = _intent(hw=hw, baud=921600, mode="interrupt")
        plan = UartProvider().plan(intent)
        return plan.to_dict()["changes"]

    def test_plan_has_uart_owner(self):
        owners = {c["owner"] for c in self._plan_changes()}
        assert "uart" in owners

    def test_plan_declares_mcl_dep(self):
        owners = {c["owner"] for c in self._plan_changes()}
        assert "mcl" in owners, "FlexIO path must declare mcl dependency"

    def test_plan_declares_platform_dep(self):
        owners = {c["owner"] for c in self._plan_changes()}
        assert "platform" in owners, "FlexIO interrupt path must declare platform dependency"

    def test_plan_declares_mcu_dep(self):
        owners = {c["owner"] for c in self._plan_changes()}
        assert "mcu" in owners, "FlexIO path must declare mcu clock dependency"

    def test_plan_flexio_platform_dep_names_flexio_irqn(self):
        """FlexIO platform dep description must name FLEXIO_IRQn (concrete value per LL-010)."""
        changes = self._plan_changes("FLEXIO")
        for c in changes:
            if c["owner"] == "platform":
                assert "FLEXIO_IRQn" in c["description"], (
                    f"Platform dep for FlexIO must name FLEXIO_IRQn, got: {c['description']!r}"
                )
                return
        pytest.fail("No platform dep found")

    def test_plan_flexio_platform_dep_names_mcl_flexio_isr(self):
        """FlexIO platform dep must name MCL_FLEXIO_ISR."""
        changes = self._plan_changes("FLEXIO")
        for c in changes:
            if c["owner"] == "platform":
                assert "MCL_FLEXIO_ISR" in c["description"], (
                    f"Platform dep for FlexIO must name MCL_FLEXIO_ISR, got: {c['description']!r}"
                )
                return
        pytest.fail("No platform dep found")

    def test_plan_flexio_mcu_dep_names_flexio_clk(self):
        """FlexIO mcu dep description must name FLEXIO_CLK."""
        changes = self._plan_changes("FLEXIO")
        for c in changes:
            if c["owner"] == "mcu":
                assert "FLEXIO_CLK" in c["description"], (
                    f"Mcu dep for FlexIO must name FLEXIO_CLK, got: {c['description']!r}"
                )
                return
        pytest.fail("No mcu dep found")

    def test_plan_flexio_mcl_dep_description_present(self):
        """FlexIO mcl dep must have non-empty description naming both channels."""
        changes = self._plan_changes("FLEXIO")
        for c in changes:
            if c["owner"] == "mcl":
                assert len(c["description"]) > 0
                return
        pytest.fail("No mcl dep found")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliAddFlexioChannel:
    """uart add-flexio-channel --project ... --baud 921600 ... --configure --json."""

    def test_cli_add_flexio_channel_passes(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "add-flexio-channel",
                "--project", str(project),
                "--baud", "921600",
                "--word-length", "8",
                "--mode", "interrupt",
                "--callback", "Autombd_UartCallback",
                "--configure",
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        payload = json.loads(result.stdout)
        assert payload["status"] == "passed", payload
        assert "uart" in payload["changed_modules"]
        assert "mcl" in payload["changed_modules"]
        assert payload["runtime_verification"]["static_check"]["status"] == "passed"

    def test_cli_creates_two_mcl_channels(self, tmp_path):
        """After CLI run, both UART2_TX and UART2_RX MCL channels exist in the .mex."""
        project = copy_uart_fixture(tmp_path)
        subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "add-flexio-channel",
                "--project", str(project),
                "--baud", "921600",
                "--word-length", "8",
                "--mode", "interrupt",
                "--callback", "Autombd_UartCallback",
                "--configure",
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        from rtd_config.backends.s32_mex.locate import find_single_mex
        mex = find_single_mex(project)
        doc = MexDocument.load(mex)
        assert _mcl_channel_by_name(doc, "UART2_TX") is not None
        assert _mcl_channel_by_name(doc, "UART2_RX") is not None

    def test_cli_creates_two_uart_channels(self, tmp_path):
        """After CLI run, both UART2_TX and UART2_RX Uart channels exist."""
        project = copy_uart_fixture(tmp_path)
        subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "add-flexio-channel",
                "--project", str(project),
                "--baud", "921600",
                "--word-length", "8",
                "--mode", "interrupt",
                "--callback", "Autombd_UartCallback",
                "--configure",
                "--json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        from rtd_config.backends.s32_mex.locate import find_single_mex
        mex = find_single_mex(project)
        doc = MexDocument.load(mex)
        assert _uart_channel_by_name(doc, "UART2_TX") is not None
        assert _uart_channel_by_name(doc, "UART2_RX") is not None

    def test_cli_help_shows_add_flexio_channel(self, tmp_path):
        """--help must list add-flexio-channel as an available subcommand."""
        result = subprocess.run(
            [sys.executable, "-m", "rtd_config", "uart", "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        combined = result.stdout + result.stderr
        assert "add-flexio-channel" in combined, (
            f"'add-flexio-channel' not found in uart --help output: {combined!r}"
        )

    def test_existing_uart_set_command_unaffected(self, tmp_path):
        """uart set (UART-001 path) must still work after UART-002 changes."""
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
                "--hw", "LPUART_8",
                "--baud", "921600",
                "--mode", "interrupt",
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


# ---------------------------------------------------------------------------
# Fix 1: asset loading/pinning for FlexioDesireBaudrate, mcl_ref_path_pattern,
#         FlexioBitCount, FlexioDriverDirection, flexio_channel_template
# ---------------------------------------------------------------------------

class TestFix1AssetLoadingAndPinning:
    """Every uart.json FlexIO key must be either LOADED at runtime or PINNED
    by a code==asset assertion.  No decorative keys (LL-012 / LL-016).
    """

    # -- FlexioDesireBaudrate: LOAD + validate; unsupported baud => blocker --

    def test_unsupported_flexio_baud_returns_blocker(self, tmp_path):
        """baud=99999 is not in FlexioDesireBaudrate => 'unsupported_flexio_baud' blocker."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _intent(baud=99999, mode="interrupt"))
        assert result.blocked, "Expected a blocker for unsupported FlexIO baud"
        codes = [d.code for d in result.diagnostics]
        assert "unsupported_flexio_baud" in codes, f"Expected 'unsupported_flexio_baud', got {codes}"

    def test_unsupported_flexio_baud_lists_valid_bauds(self, tmp_path):
        """Blocker diagnostic 'details' must list valid bauds from the asset."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _intent(baud=99999, mode="interrupt"))
        diag = next(d for d in result.diagnostics if d.code == "unsupported_flexio_baud")
        assert "valid_bauds" in diag.details, f"Missing 'valid_bauds' in details: {diag.details}"
        assert "FLEXIO_UART_BAUDRATE_921600" in diag.details["valid_bauds"]

    def test_supported_baud_921600_not_blocked(self, tmp_path):
        """baud=921600 is in FlexioDesireBaudrate => no blocker."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]

    # -- mcl_ref_path_pattern: LOAD, format with channel_name --

    def test_mcl_ref_path_built_from_asset_pattern(self, tmp_path):
        """UartHwChannelRef must be built from mcl_ref_path_pattern in uart.json.

        The asset says: /Mcl/Mcl/MclConfig/FlexioCommon_0/{channel_name}
        So for UART2_TX the ref must be exactly that.
        """
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        pattern = data["mcl_ref_path_pattern"]
        expected_tx = pattern.format(channel_name="UART2_TX")
        expected_rx = pattern.format(channel_name="UART2_RX")

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())

        ref_tx = _flexio_cfg_setting(doc, "UART2_TX", "UartHwChannelRef")
        ref_rx = _flexio_cfg_setting(doc, "UART2_RX", "UartHwChannelRef")
        assert ref_tx == expected_tx, f"TX ref mismatch: {ref_tx!r} != {expected_tx!r}"
        assert ref_rx == expected_rx, f"RX ref mismatch: {ref_rx!r} != {expected_rx!r}"

    # -- FlexioBitCount: code==asset pin (8-bit inline value is a member) --

    def test_emitted_bit_count_is_member_of_asset_enum(self, tmp_path):
        """bitCount written to .mex must be a member of FlexioBitCount in the asset."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        valid_bit_counts = data["enum_domains"]["FlexioBitCount"]

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())

        emitted = _flexio_cfg_setting(doc, "UART2_TX", "bitCount")
        assert emitted in valid_bit_counts, (
            f"Emitted bitCount {emitted!r} is not in asset FlexioBitCount: {valid_bit_counts}"
        )

    # -- FlexioDriverDirection: code==asset pin --

    def test_emitted_tx_direction_is_member_of_asset_enum(self, tmp_path):
        """driverDirection TX value must be a member of FlexioDriverDirection in the asset."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        valid_dirs = data["enum_domains"]["FlexioDriverDirection"]

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())

        emitted = _flexio_cfg_setting(doc, "UART2_TX", "driverDirection")
        assert emitted in valid_dirs, (
            f"Emitted TX driverDirection {emitted!r} is not in asset FlexioDriverDirection: {valid_dirs}"
        )

    def test_emitted_rx_direction_is_member_of_asset_enum(self, tmp_path):
        """driverDirection RX value must be a member of FlexioDriverDirection in the asset."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        valid_dirs = data["enum_domains"]["FlexioDriverDirection"]

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())

        emitted = _flexio_cfg_setting(doc, "UART2_RX", "driverDirection")
        assert emitted in valid_dirs, (
            f"Emitted RX driverDirection {emitted!r} is not in asset FlexioDriverDirection: {valid_dirs}"
        )

    # -- flexio_channel_template: code==asset pin (field_order + defaults) --

    def test_emitted_flexio_channel_fields_match_template_field_order(self, tmp_path):
        """FlexioModuleConfiguration fields emitted must match asset field_order, in order.

        The asset field_order includes 'Name' (the sub-struct Name setting); the
        emitted struct also has a Name child.  We compare without 'Name' since it
        is always first by construction and is not a user-configurable field.
        """
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        # asset field_order includes "Name"; strip it for comparison since both
        # emitted and expected must exclude the Name sentinel
        expected_order = [f for f in data["flexio_channel_template"]["field_order"] if f != "Name"]

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())

        ch = _uart_channel_by_name(doc, "UART2_TX")
        assert ch is not None
        flexio_struct = None
        for el in ch.iter():
            if el.tag.endswith("struct") and el.attrib.get("name") == "FlexioModuleConfiguration":
                flexio_struct = el
                break
        assert flexio_struct is not None

        # Collect emitted field names in document order (settings and arrays, skip Name)
        emitted_fields = []
        for child in flexio_struct:
            n = child.attrib.get("name", "")
            if n and n != "Name":
                emitted_fields.append(n)

        assert emitted_fields == expected_order, (
            f"FlexioModuleConfiguration field order mismatch:\n"
            f"  emitted:  {emitted_fields}\n"
            f"  expected: {expected_order}"
        )

    def test_emitted_flexio_channel_defaults_match_template(self, tmp_path):
        """Default field values in FlexioModuleConfiguration must match asset template defaults."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        expected_defaults = data["flexio_channel_template"]["defaults"]

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(doc, _default_intent())

        for field_name, expected_value in expected_defaults.items():
            # FlexioDmaChannelRef is an array (empty), skip value check for arrays
            if field_name == "FlexioDmaChannelRef":
                # Just assert the array element is present
                ch = _uart_channel_by_name(doc, "UART2_TX")
                assert ch is not None
                found = False
                for el in ch.iter():
                    if el.tag.endswith("struct") and el.attrib.get("name") == "FlexioModuleConfiguration":
                        for child in el:
                            if child.attrib.get("name") == "FlexioDmaChannelRef":
                                found = True
                assert found, "FlexioDmaChannelRef array not present in FlexioModuleConfiguration"
                continue
            emitted = _flexio_cfg_setting(doc, "UART2_TX", field_name)
            assert emitted == expected_value, (
                f"Default for {field_name!r}: emitted {emitted!r} != asset {expected_value!r}"
            )

    # -- Byte-identity: canonical output (baud 921600, default names) unchanged --

    def test_canonical_output_byte_identity(self, tmp_path):
        """Canonical FlexIO output bytes (baud=921600, default names) must be
        unchanged from the pre-fix accepted output (LL-016 byte-identity contract).

        Strategy: apply once, write, apply again on the result, write again.
        The second write must produce byte-identical output (idempotency = no drift).
        Also asserts deterministic field content for both TX and RX channels.
        """
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"

        doc1 = MexDocument.load(mex)
        apply_uart_add_flexio_channel(doc1, _default_intent())
        doc1.write(mex)
        first_bytes = mex.read_bytes()

        doc2 = MexDocument.load(mex)
        apply_uart_add_flexio_channel(doc2, _default_intent())
        doc2.write(mex)
        second_bytes = mex.read_bytes()

        assert first_bytes == second_bytes, (
            "Canonical FlexIO output bytes changed after round-trip: "
            "implementation introduced output drift"
        )


# ---------------------------------------------------------------------------
# Fix 3: UartChannelId anti-hardcode -- perturbed fixture test
# ---------------------------------------------------------------------------

class TestFix3AntiHardcodeUartChannelId:
    """New UartChannelId values must be computed as max+1 / max+2, never hardcoded.

    This test pre-inserts a Uart channel with a higher UartChannelId so that
    new FlexIO channels must land at IDs beyond 4, exposing any hardcoded 3/4.
    """

    def _insert_extra_uart_channel(self, doc: MexDocument, channel_id: int) -> None:
        """Directly inject a minimal UartChannel struct with a high channel ID
        into the UartChannel array to perturb the fixture state."""
        uart_cfg = doc.find_config_set("Uart")
        assert uart_cfg is not None

        channel_array = None
        for arr in uart_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "UartChannel":
                channel_array = arr
                break
        assert channel_array is not None

        existing_structs = [c for c in channel_array if c.tag.endswith("struct")]
        struct_index = len(existing_structs)
        line_ending = b"\r\n" if b"\r\n" in doc._raw[:4096] else b"\n"
        le = line_ending.decode("latin-1")
        sp = " " * 30
        sp1 = " " * 33
        sp2 = " " * 36
        extra_bytes = (
            f'{sp}<struct name="{struct_index}">{le}'
            f'{sp1}<setting name="Name" value="EXTRA_CH"/>{le}'
            f'{sp1}<setting name="UartHwUsing" value="LPUART_IP"/>{le}'
            f'{sp1}<setting name="UartChannelId" value="{channel_id}"/>{le}'
            f'{sp1}<setting name="UartClockRef" value="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/LPUART3_CLK"/>{le}'
            f'{sp1}<array name="UartChannelEcucPartitionRef"/>{le}'
            f'{sp1}<struct name="DetailModuleConfiguration">{le}'
            f'{sp2}<setting name="Name" value="DetailModuleConfiguration"/>{le}'
            f'{sp2}<setting name="UartHwChannel" value="LPUART_3"/>{le}'
            f'{sp2}<setting name="DesireBaudrate" value="LPUART_UART_BAUDRATE_9600"/>{le}'
            f'{sp2}<setting name="CustomBaudrateMantissa" value="1"/>{le}'
            f'{sp2}<setting name="CustomBaudrateDivisor" value="4"/>{le}'
            f'{sp2}<setting name="UartInteruptDmaMethod" value="LPUART_UART_IP_USING_INTERRUPTS"/>{le}'
            f'{sp2}<array name="UartDmaTxChannelRef"/>{le}'
            f'{sp2}<array name="UartDmaRxChannelRef"/>{le}'
            f'{sp2}<setting name="UartParityType" value="LPUART_UART_IP_PARITY_DISABLED"/>{le}'
            f'{sp2}<setting name="UartStopBitNumber" value="LPUART_UART_IP_ONE_STOP_BIT"/>{le}'
            f'{sp2}<setting name="UartWordLength" value="LPUART_UART_IP_8_BITS_PER_CHAR"/>{le}'
            f'{sp2}<setting name="UartInternalLoopbackEnable" value="false"/>{le}'
            f'{sp2}<setting name="UartTimeoutEnable" value="false"/>{le}'
            f'{sp1}</struct>{le}'
            f'{sp1}<struct name="FlexioModuleConfiguration">{le}'
            f'{sp2}<setting name="Name" value="FlexioModuleConfiguration"/>{le}'
            f'{sp1}</struct>{le}'
            f'{sp}</struct>'
        ).encode("utf-8")

        from rtd_config.backends.s32_mex.apply import _append_after_last_element
        from rtd_config.backends.s32_mex.apply import _append_struct_before_array_close
        ok = _append_after_last_element(doc, existing_structs[-1], extra_bytes, line_ending)
        if not ok:
            _append_struct_before_array_close(doc, channel_array, extra_bytes, line_ending)

    def test_new_uart_ids_beyond_perturbed_max(self, tmp_path):
        """Pre-insert a Uart channel with id=7; new FlexIO channels must get 8 and 9."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")

        # Pre-insert a channel with a high id (7), simulating a perturbed fixture
        self._insert_extra_uart_channel(doc, channel_id=7)

        # Now apply UART-002; TX must get 8, RX must get 9
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]

        ids = _all_uart_channel_ids(doc)
        assert 8 in ids, f"TX channel must get id=8, got ids={sorted(ids)}"
        assert 9 in ids, f"RX channel must get id=9, got ids={sorted(ids)}"

    def test_new_uart_ids_not_hardcoded_3_4(self, tmp_path):
        """When existing max is 7, new channels must NOT be 3 and 4."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")

        self._insert_extra_uart_channel(doc, channel_id=7)

        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]

        tx_id = _uart_channel_setting(doc, "UART2_TX", "UartChannelId")
        rx_id = _uart_channel_setting(doc, "UART2_RX", "UartChannelId")
        assert tx_id not in ("3", "4"), f"TX id must not be hardcoded 3, got {tx_id!r}"
        assert rx_id not in ("3", "4"), f"RX id must not be hardcoded 4, got {rx_id!r}"


# ---------------------------------------------------------------------------
# Fix 4: changed_modules accuracy + dead code
# ---------------------------------------------------------------------------

class TestFix4ChangedModulesAccuracy:
    """changed_modules must be exactly ['uart','mcl'] on the fixture (where
    Platform/Mcu FLEXIO entries already exist and are no-ops).
    """

    def test_changed_modules_exact_on_fixture(self, tmp_path):
        """On the standard fixture, FLEXIO_IRQn and FLEXIO_CLK already exist.
        So changed_modules must be exactly ['uart','mcl'] -- not include 'platform' or 'mcu'.
        """
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert sorted(result.changed_modules) == ["mcl", "uart"], (
            f"changed_modules must be ['uart','mcl'] on fixture, got {result.changed_modules!r}"
        )

    def test_changed_modules_no_platform_when_flexio_irq_already_present(self, tmp_path):
        """'platform' must not appear in changed_modules when FLEXIO_IRQn is a no-op."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert "platform" not in result.changed_modules, (
            f"'platform' should not be in changed_modules for fixture (FLEXIO_IRQn already present): "
            f"{result.changed_modules!r}"
        )

    def test_changed_modules_no_mcu_when_flexio_clk_already_present(self, tmp_path):
        """'mcu' must not appear in changed_modules when FLEXIO_CLK is a no-op."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(doc, _default_intent())
        assert "mcu" not in result.changed_modules, (
            f"'mcu' should not be in changed_modules for fixture (FLEXIO_CLK already present): "
            f"{result.changed_modules!r}"
        )


# ---------------------------------------------------------------------------
# Fix 5: cross-reference derivation -- custom tx_name/rx_name
# ---------------------------------------------------------------------------

class TestFix5CustomNameCrossReference:
    """When --tx-name / --rx-name are custom, both the MCL channel Name and
    the Uart UartHwChannelRef must reflect those custom names, proving the
    ref tracks the MCL channel and is not hardcoded to UART2_TX/UART2_RX.
    """

    def test_custom_names_mcl_channel_created(self, tmp_path):
        """MCL channels MY_TX and MY_RX must be created with custom names."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_add_flexio_channel(
            doc, _default_intent(tx_name="MY_TX", rx_name="MY_RX")
        )
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _mcl_channel_by_name(doc, "MY_TX") is not None, "MY_TX MCL channel must be created"
        assert _mcl_channel_by_name(doc, "MY_RX") is not None, "MY_RX MCL channel must be created"

    def test_custom_tx_name_uart_hw_channel_ref_tracks_mcl(self, tmp_path):
        """UartHwChannelRef for MY_TX uart channel must contain 'MY_TX', not 'UART2_TX'."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(
            doc, _default_intent(tx_name="MY_TX", rx_name="MY_RX")
        )
        ref = _flexio_cfg_setting(doc, "MY_TX", "UartHwChannelRef")
        assert ref is not None, "UartHwChannelRef must be set for MY_TX"
        assert "MY_TX" in ref, (
            f"UartHwChannelRef must contain 'MY_TX' for custom tx_name, got: {ref!r}"
        )
        assert "UART2_TX" not in ref, (
            f"UartHwChannelRef must NOT hardcode 'UART2_TX', got: {ref!r}"
        )

    def test_custom_rx_name_uart_hw_channel_ref_tracks_mcl(self, tmp_path):
        """UartHwChannelRef for MY_RX uart channel must contain 'MY_RX', not 'UART2_RX'."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(
            doc, _default_intent(tx_name="MY_TX", rx_name="MY_RX")
        )
        ref = _flexio_cfg_setting(doc, "MY_RX", "UartHwChannelRef")
        assert ref is not None, "UartHwChannelRef must be set for MY_RX"
        assert "MY_RX" in ref, (
            f"UartHwChannelRef must contain 'MY_RX' for custom rx_name, got: {ref!r}"
        )
        assert "UART2_RX" not in ref, (
            f"UartHwChannelRef must NOT hardcode 'UART2_RX', got: {ref!r}"
        )

    def test_custom_names_ref_built_from_asset_pattern(self, tmp_path):
        """UartHwChannelRef must equal the asset pattern formatted with the custom name."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        pattern = data["mcl_ref_path_pattern"]
        expected_tx = pattern.format(channel_name="MY_TX")
        expected_rx = pattern.format(channel_name="MY_RX")

        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_add_flexio_channel(
            doc, _default_intent(tx_name="MY_TX", rx_name="MY_RX")
        )

        ref_tx = _flexio_cfg_setting(doc, "MY_TX", "UartHwChannelRef")
        ref_rx = _flexio_cfg_setting(doc, "MY_RX", "UartHwChannelRef")
        assert ref_tx == expected_tx, f"TX ref: {ref_tx!r} != {expected_tx!r}"
        assert ref_rx == expected_rx, f"RX ref: {ref_rx!r} != {expected_rx!r}"
