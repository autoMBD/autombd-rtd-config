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
# File:        test_uart_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-12
# Version:     0.1.0
# Description: Deterministic tests for apply_uart_set orchestration (RTD-MEX-UART-001).
#              Covers: channel fields, callback, Platform ISR insert, Mcu clock-ref
#              insert, UartClockRef, changed_modules, idempotency, anti-hardcode,
#              CLI integration, plan() cross-module deps, uart.json asset.
# =================================================================================

"""Deterministic tests for apply_uart_set full orchestration (RTD-MEX-UART-001).

Fixture: tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/Uart_Example.mex
Channel 0 (Name=LPUART3, UartHwUsing=LPUART_IP) is the target.

Ground truth for enum values and IRQ/handler/clock mapping: uart.json asset.
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


def _channel_setting(doc: MexDocument, channel: ET.Element, name: str) -> str | None:
    """Return a top-level setting value from a UartChannel struct."""
    s = doc.find_child_setting(channel, name)
    return s.attrib.get("value") if s is not None else None


def _gen_cfg_setting(doc: MexDocument, name: str) -> str | None:
    """Return a setting value from GeneralConfiguration."""
    uart_cfg = doc.find_config_set("Uart")
    if uart_cfg is None:
        return None
    for el in uart_cfg.iter():
        if el.tag.endswith("struct") and el.attrib.get("name") == "GeneralConfiguration":
            s = doc.find_child_setting(el, name)
            return s.attrib.get("value") if s is not None else None
    return None


def _gen_cfg_callback_array_value(doc: MexDocument, index: int) -> str | None:
    """Return the value of UartCallback[index] from GeneralConfiguration."""
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


def _mcu_clock_ref(doc: MexDocument, ref_name: str) -> ET.Element | None:
    """Return a McuClockReferencePoint struct with Name==ref_name, or None."""
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


def _mcu_clock_ref_freq(doc: MexDocument, ref_name: str) -> str | None:
    s = _mcu_clock_ref(doc, ref_name)
    if s is None:
        return None
    f = doc.find_child_setting(s, "McuClockFrequencySelect")
    return f.attrib.get("value") if f is not None else None


# ---------------------------------------------------------------------------
# uart.json asset existence + schema tests (LL-012 code==asset pin)
# ---------------------------------------------------------------------------

class TestUartAsset:
    """uart.json must exist, be valid JSON, and contain required fields."""

    def test_asset_file_exists(self):
        assert _UART_ASSET.exists(), f"uart.json not found at {_UART_ASSET}"

    def test_asset_is_valid_json(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_asset_has_enum_domains(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        # All required enum fields must be present
        assert "UartWordLength" in enums
        assert "UartParityType" in enums
        assert "UartStopBitNumber" in enums
        assert "UartInteruptDmaMethod" in enums
        assert "DesireBaudrate" in enums

    def test_baud_921600_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert "LPUART_UART_BAUDRATE_921600" in bauds, (
            "921600 baud enum must be present in uart.json DesireBaudrate"
        )

    def test_asset_has_instance_mapping(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        mapping = data.get("instance_irq_clock_map", {})
        assert "LPUART_8" in mapping
        entry = mapping["LPUART_8"]
        assert entry["irq_name"] == "LPUART8_IRQn"
        assert entry["isr_handler"] == "LPUART_UART_IP_8_IRQHandler"
        assert entry["clock_select"] == "AIPS_PLAT_CLK"

    def test_asset_lpuart_5_is_slow_clk(self):
        """Anti-hardcode: LPUART_5 must map to AIPS_SLOW_CLK (not AIPS_PLAT_CLK)."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        mapping = data.get("instance_irq_clock_map", {})
        assert "LPUART_5" in mapping
        assert mapping["LPUART_5"]["clock_select"] == "AIPS_SLOW_CLK"
        assert mapping["LPUART_5"]["irq_name"] == "LPUART5_IRQn"
        assert mapping["LPUART_5"]["isr_handler"] == "LPUART_UART_IP_5_IRQHandler"

    def test_asset_lpuart_0_is_plat_clk(self):
        """LPUART_0 maps to AIPS_PLAT_CLK per ground truth."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        mapping = data.get("instance_irq_clock_map", {})
        assert "LPUART_0" in mapping
        assert mapping["LPUART_0"]["clock_select"] == "AIPS_PLAT_CLK"

    def test_asset_callback_fields(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        cb = data.get("callback_fields", {})
        assert cb.get("capability_setting") == "UartCallbackCapability"
        assert cb.get("callback_array") == "UartCallback"


# ---------------------------------------------------------------------------
# Channel field edits (LPUART_8, baud 921600, word/parity/stop/method)
# ---------------------------------------------------------------------------

class TestChannelFieldEdits:
    """apply_uart_set must set all channel detail fields for LPUART_8 921600."""

    def test_hw_channel_set_to_lpuart_8(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            word_length="LPUART_UART_IP_8_BITS_PER_CHAR",
            parity="LPUART_UART_IP_PARITY_DISABLED",
            stop_bits="LPUART_UART_IP_ONE_STOP_BIT",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartHwChannel") == "LPUART_8"

    def test_baud_921600_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "DesireBaudrate") == "LPUART_UART_BAUDRATE_921600"

    def test_word_length_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            word_length="LPUART_UART_IP_8_BITS_PER_CHAR",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartWordLength") == "LPUART_UART_IP_8_BITS_PER_CHAR"

    def test_parity_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            parity="LPUART_UART_IP_PARITY_DISABLED",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartParityType") == "LPUART_UART_IP_PARITY_DISABLED"

    def test_stop_bits_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            stop_bits="LPUART_UART_IP_ONE_STOP_BIT",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartStopBitNumber") == "LPUART_UART_IP_ONE_STOP_BIT"

    def test_interrupt_method_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartInteruptDmaMethod") == "LPUART_UART_IP_USING_INTERRUPTS"


# ---------------------------------------------------------------------------
# Callback fields
# ---------------------------------------------------------------------------

class TestCallbackFields:
    """UartCallbackCapability -> true; UartCallback[0] -> Autombd_UartCallback."""

    def test_capability_enabled(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            callback="Autombd_UartCallback",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _gen_cfg_setting(doc, "UartCallbackCapability") == "true"

    def test_callback_name_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            callback="Autombd_UartCallback",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _gen_cfg_callback_array_value(doc, 0) == "Autombd_UartCallback"

    def test_no_callback_leaves_capability_unchanged(self, tmp_path):
        """When callback not requested, UartCallbackCapability stays false."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _gen_cfg_setting(doc, "UartCallbackCapability") == "false"


# ---------------------------------------------------------------------------
# UartClockRef update
# ---------------------------------------------------------------------------

class TestUartClockRef:
    """UartClockRef for channel 0 must point to the LPUART8_CLK path."""

    def test_clock_ref_updated_to_lpuart8(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        ref = _channel_setting(doc, ch, "UartClockRef")
        assert ref is not None
        assert "LPUART8_CLK" in ref, f"Expected LPUART8_CLK in UartClockRef, got: {ref!r}"
        assert ref.startswith("/Mcu/"), f"UartClockRef path must start with /Mcu/, got: {ref!r}"


# ---------------------------------------------------------------------------
# Platform ISR insertion
# ---------------------------------------------------------------------------

class TestPlatformIsrInsert:
    """apply_uart_set must INSERT a new PlatformIsrConfig for LPUART8_IRQn."""

    def test_isr_inserted_for_lpuart8(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt", priority=2,
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        entry = _platform_isr_entry(doc, "LPUART8_IRQn")
        assert entry is not None, "LPUART8_IRQn ISR entry must be inserted"

    def test_isr_enabled(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        assert _platform_isr_setting(doc, "LPUART8_IRQn", "IsrEnabled") == "true"

    def test_isr_priority_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        assert _platform_isr_setting(doc, "LPUART8_IRQn", "IsrPriority") == "2"

    def test_isr_handler_set(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        assert _platform_isr_setting(doc, "LPUART8_IRQn", "IsrHandler") == "LPUART_UART_IP_8_IRQHandler"

    def test_existing_isrs_preserved(self, tmp_path):
        """The existing LPUART3_IRQn and FLEXIO_IRQn entries must be undisturbed."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        assert _platform_isr_setting(doc, "LPUART3_IRQn", "IsrEnabled") == "true"
        assert _platform_isr_setting(doc, "FLEXIO_IRQn", "IsrEnabled") == "true"

    def test_isr_insert_idempotent(self, tmp_path):
        """Second apply must NOT add a duplicate ISR entry."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        # Second call -- same doc
        result2 = apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
        # Count ISR entries with LPUART8_IRQn
        plat_cfg = doc.find_config_set("Platform")
        count = 0
        for arr in plat_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "PlatformIsrConfig":
                for s in arr:
                    if not s.tag.endswith("struct"):
                        continue
                    n = doc.find_child_setting(s, "IsrName")
                    if n is not None and n.attrib.get("value") == "LPUART8_IRQn":
                        count += 1
        assert count == 1, f"Duplicate ISR entry detected: count={count}"


# ---------------------------------------------------------------------------
# Mcu clock reference insertion
# ---------------------------------------------------------------------------

class TestMcuClockRefInsert:
    """apply_uart_set must INSERT a new McuClockReferencePoint for LPUART8_CLK."""

    def test_clock_ref_inserted(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert _mcu_clock_ref(doc, "LPUART8_CLK") is not None, "LPUART8_CLK clock ref must be inserted"

    def test_clock_ref_freq_select(self, tmp_path):
        """LPUART_8 uses AIPS_PLAT_CLK per ground truth."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt"))
        assert _mcu_clock_ref_freq(doc, "LPUART8_CLK") == "AIPS_PLAT_CLK"

    def test_existing_clock_refs_preserved(self, tmp_path):
        """LPUART3_CLK and FLEXIO_CLK from fixture must remain."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt"))
        assert _mcu_clock_ref(doc, "LPUART3_CLK") is not None
        assert _mcu_clock_ref(doc, "FLEXIO_CLK") is not None

    def test_no_frequency_field_written(self, tmp_path):
        """McuClockReferencePointFrequency must NOT be written (ConfigTools computes it)."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt"))
        ref = _mcu_clock_ref(doc, "LPUART8_CLK")
        assert ref is not None
        freq_setting = doc.find_child_setting(ref, "McuClockReferencePointFrequency")
        assert freq_setting is None, "McuClockReferencePointFrequency must NOT be written"

    def test_clock_ref_insert_idempotent(self, tmp_path):
        """Second apply must NOT add a duplicate clock ref."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt"))
        result2 = apply_uart_set(doc, _intent(hw="LPUART_8", baud=921600, mode="interrupt"))
        assert not result2.blocked
        mcu_cfg = doc.find_config_set("Mcu")
        count = 0
        for arr in mcu_cfg.iter():
            if arr.tag.endswith("array") and arr.attrib.get("name") == "McuClockReferencePoint":
                for s in arr:
                    if not s.tag.endswith("struct"):
                        continue
                    n = doc.find_child_setting(s, "Name")
                    if n is not None and n.attrib.get("value") == "LPUART8_CLK":
                        count += 1
        assert count == 1, f"Duplicate clock ref entry detected: count={count}"


# ---------------------------------------------------------------------------
# changed_modules
# ---------------------------------------------------------------------------

class TestChangedModules:
    """changed_modules must include uart, platform, and mcu for the full case."""

    def test_full_orchestration_changed_modules(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            priority=2, callback="Autombd_UartCallback",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        assert "uart" in result.changed_modules
        assert "platform" in result.changed_modules
        assert "mcu" in result.changed_modules


# ---------------------------------------------------------------------------
# Anti-hardcode: different instance -> different IRQ/handler/clock
# ---------------------------------------------------------------------------

class TestAntiHardcode:
    """LL-011/LL-013: instance->IRQ/handler/clock is computed, not hardcoded to 8."""

    def test_lpuart_5_yields_correct_irq(self, tmp_path):
        """LPUART_5 -> LPUART5_IRQn / LPUART_UART_IP_5_IRQHandler / AIPS_SLOW_CLK."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_5", baud=115200, mode="interrupt", priority=3,
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        # Platform ISR
        assert _platform_isr_setting(doc, "LPUART5_IRQn", "IsrName") == "LPUART5_IRQn"
        assert _platform_isr_setting(doc, "LPUART5_IRQn", "IsrHandler") == "LPUART_UART_IP_5_IRQHandler"
        # Mcu clock ref
        assert _mcu_clock_ref_freq(doc, "LPUART5_CLK") == "AIPS_SLOW_CLK"

    def test_lpuart_5_clock_ref_path_in_channel(self, tmp_path):
        """UartClockRef for the channel must reference LPUART5_CLK."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        apply_uart_set(doc, _intent(hw="LPUART_5", baud=115200, mode="interrupt"))
        ch = _uart_channel_0(doc)
        ref = _channel_setting(doc, ch, "UartClockRef")
        assert ref is not None and "LPUART5_CLK" in ref


# ---------------------------------------------------------------------------
# Byte-faithful / well-formed after write
# ---------------------------------------------------------------------------

class TestByteNarrow:
    """Edits are narrow and the written file remains well-formed XML."""

    def test_file_well_formed_after_write(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"
        doc = MexDocument.load(mex)
        apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=921600, mode="interrupt",
            priority=2, callback="Autombd_UartCallback",
        ))
        doc.write(mex)
        # Must still parse as valid XML
        MexDocument.load(mex)

    def test_idempotent_write(self, tmp_path):
        """Two writes of the same intent produce the same file bytes."""
        project = copy_uart_fixture(tmp_path)
        mex = project / "Uart_Example.mex"

        doc1 = MexDocument.load(mex)
        apply_uart_set(doc1, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        doc1.write(mex)
        first_bytes = mex.read_bytes()

        doc2 = MexDocument.load(mex)
        apply_uart_set(doc2, _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2))
        doc2.write(mex)
        second_bytes = mex.read_bytes()

        assert first_bytes == second_bytes, "Second apply should produce identical output"


# ---------------------------------------------------------------------------
# plan() cross-module deps (LL-010)
# ---------------------------------------------------------------------------

class TestPlanDependencies:
    """UartProvider.plan() must declare Platform ISR and Mcu clock deps."""

    def test_plan_declares_platform_dep(self):
        intent = _intent(hw="LPUART_8", baud=921600, mode="interrupt", priority=2)
        plan = UartProvider().plan(intent)
        owners = {c["owner"] for c in plan.to_dict()["changes"]}
        assert "platform" in owners, "plan() must declare a platform-owned change"

    def test_plan_declares_mcu_dep(self):
        intent = _intent(hw="LPUART_8", baud=921600, mode="interrupt")
        plan = UartProvider().plan(intent)
        owners = {c["owner"] for c in plan.to_dict()["changes"]}
        assert "mcu" in owners, "plan() must declare a mcu-owned change"

    def test_plan_has_uart_owner(self):
        intent = _intent(hw="LPUART_8", baud=921600, mode="interrupt")
        plan = UartProvider().plan(intent)
        owners = {c["owner"] for c in plan.to_dict()["changes"]}
        assert "uart" in owners


# ---------------------------------------------------------------------------
# plan() description fidelity (LL-010 / Fix 3)
# Platform dep description must name IsrName + handler; Mcu dep must name clock.
# Values are computed from uart.json instance_irq_clock_map, not hardcoded.
# ---------------------------------------------------------------------------

class TestPlanDescriptionFidelity:
    """plan() dependency descriptions must name concrete IRQ/handler/clock substrings.

    These tests pin LL-010 fidelity: the plan descriptions must contain the
    concrete IsrName, ISR handler, and clock-select values that apply writes,
    derived from the SAME uart.json source used by apply_uart_set.  The exact
    string format is not pinned -- only that the key substrings appear.
    """

    def _platform_desc(self, hw: str) -> str:
        """Return the platform-owned PlannedChange description for ``hw``."""
        intent = _intent(hw=hw, baud=921600, mode="interrupt")
        plan = UartProvider().plan(intent)
        for c in plan.to_dict()["changes"]:
            if c["owner"] == "platform":
                return c["description"]
        raise AssertionError("No platform-owned change in plan")

    def _mcu_desc(self, hw: str) -> str:
        """Return the mcu-owned PlannedChange description for ``hw``."""
        intent = _intent(hw=hw, baud=921600, mode="interrupt")
        plan = UartProvider().plan(intent)
        for c in plan.to_dict()["changes"]:
            if c["owner"] == "mcu":
                return c["description"]
        raise AssertionError("No mcu-owned change in plan")

    def test_platform_description_names_irq_lpuart8(self):
        """LPUART_8 platform dep must name LPUART8_IRQn in its description."""
        desc = self._platform_desc("LPUART_8")
        assert "LPUART8_IRQn" in desc, (
            f"Platform dep description for LPUART_8 must contain 'LPUART8_IRQn', got: {desc!r}"
        )

    def test_platform_description_names_handler_lpuart8(self):
        """LPUART_8 platform dep must name LPUART_UART_IP_8_IRQHandler."""
        desc = self._platform_desc("LPUART_8")
        assert "LPUART_UART_IP_8_IRQHandler" in desc, (
            f"Platform dep description for LPUART_8 must contain handler name, got: {desc!r}"
        )

    def test_platform_description_names_irq_lpuart5(self):
        """Anti-hardcode: LPUART_5 platform dep must name LPUART5_IRQn (not LPUART8_IRQn)."""
        desc = self._platform_desc("LPUART_5")
        assert "LPUART5_IRQn" in desc, (
            f"Platform dep description for LPUART_5 must contain 'LPUART5_IRQn', got: {desc!r}"
        )
        assert "LPUART5_IRQHandler" in desc or "LPUART_UART_IP_5_IRQHandler" in desc, (
            f"Platform dep description for LPUART_5 must contain handler name, got: {desc!r}"
        )

    def test_mcu_description_names_clock_ref_lpuart8(self):
        """LPUART_8 mcu dep description must name the clock-ref name (LPUART8_CLK)."""
        desc = self._mcu_desc("LPUART_8")
        assert "LPUART8_CLK" in desc, (
            f"Mcu dep description for LPUART_8 must contain 'LPUART8_CLK', got: {desc!r}"
        )

    def test_mcu_description_names_clock_select_lpuart8(self):
        """LPUART_8 mcu dep description must name AIPS_PLAT_CLK."""
        desc = self._mcu_desc("LPUART_8")
        assert "AIPS_PLAT_CLK" in desc, (
            f"Mcu dep description for LPUART_8 must contain 'AIPS_PLAT_CLK', got: {desc!r}"
        )

    def test_mcu_description_names_clock_ref_lpuart5(self):
        """Anti-hardcode: LPUART_5 mcu dep must name LPUART5_CLK and AIPS_SLOW_CLK."""
        desc = self._mcu_desc("LPUART_5")
        assert "LPUART5_CLK" in desc, (
            f"Mcu dep description for LPUART_5 must contain 'LPUART5_CLK', got: {desc!r}"
        )
        assert "AIPS_SLOW_CLK" in desc, (
            f"Mcu dep description for LPUART_5 must contain 'AIPS_SLOW_CLK', got: {desc!r}"
        )

    def test_flexio_platform_dep_description_unchanged(self):
        """FlexIO path has no uart.json IRQ entry; description must still be non-empty."""
        intent = _intent(hw="FLEXIO_0", baud=9600, mode="interrupt")
        plan = UartProvider().plan(intent)
        for c in plan.to_dict()["changes"]:
            if c["owner"] == "platform":
                assert len(c["description"]) > 0
                return
        # FlexIO in interrupt mode must still declare a platform dep
        raise AssertionError("No platform dep found for FlexIO interrupt mode")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

class TestCliIntegration:
    """uart set --hw LPUART_8 --baud 921600 ... --configure --json passes."""

    def test_cli_uart_set_lpuart8(self, tmp_path):
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
                "--hw", "LPUART_8",
                "--baud", "921600",
                "--parity", "none",
                "--stop-bits", "1",
                "--word-length", "8",
                "--mode", "interrupt",
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
        assert "platform" in payload["changed_modules"]
        assert "mcu" in payload["changed_modules"]
        assert payload["runtime_verification"]["static_check"]["status"] == "passed"

    def test_cli_backward_compat_lpuart_0(self, tmp_path):
        """Existing CLI call (LPUART_0 without new flags) still works."""
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
                "--hw", "LPUART_0",
                "--mode", "interrupt",
                "--baud", "115200",
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
        assert payload["status"] == "passed", payload
        assert "uart" in payload["changed_modules"]
