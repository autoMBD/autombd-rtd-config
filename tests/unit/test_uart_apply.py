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

    def test_baud_7200_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert "LPUART_UART_BAUDRATE_7200" in bauds

    def test_baud_14400_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert "LPUART_UART_BAUDRATE_14400" in bauds

    def test_baud_28800_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert "LPUART_UART_BAUDRATE_28800" in bauds

    def test_baud_1843200_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert "LPUART_UART_BAUDRATE_1843200" in bauds

    def test_baud_custom_in_asset(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert "LPUART_UART_BAUDRATE_CUSTOM" in bauds

    def test_desire_baudrate_count_is_16(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        bauds = data["enum_domains"]["DesireBaudrate"]
        assert len(bauds) == 16, f"Expected 16 baud rates including CUSTOM, got {len(bauds)}"

    def test_flexio_custom_timer_decrement_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "FlexioCustomTimerDecrement" in enums
        values = enums["FlexioCustomTimerDecrement"]
        assert "FLEXIO_TIMER_DECREMENT_FXIO_CLK_SHIFT_TMR" in values
        assert "FLEXIO_TIMER_DECREMENT_FXIO_CLK_DIV_16" in values
        assert "FLEXIO_TIMER_DECREMENT_FXIO_CLK_DIV_256" in values

    def test_uart_timeout_method_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "UartTimeoutMethod" in enums
        values = enums["UartTimeoutMethod"]
        assert "OSIF_COUNTER_DUMMY" in values
        assert "OSIF_COUNTER_SYSTEM" in values
        assert "OSIF_COUNTER_CUSTOM" in values

    def test_uart_hw_using_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "UartHwUsing" in enums
        values = enums["UartHwUsing"]
        assert "LPUART_IP" in values
        assert "FLEXIO_IP" in values

    def test_uart_implementation_config_variant_enum_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enums = data.get("enum_domains", {})
        assert "UartImplementationConfigVariant" in enums
        values = enums["UartImplementationConfigVariant"]
        assert "VariantPostBuild" in values
        assert "VariantPreCompile" in values

    def test_numeric_domains_section_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        nd = data.get("numeric_domains", {})
        assert "CustomBaudrateMantissa" in nd
        assert "CustomBaudrateDivisor" in nd
        assert "CustomBaudrateDividerFlexio" in nd
        assert "UartTimeoutDuration" in nd

    def test_numeric_domains_correct_ranges(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        nd = data["numeric_domains"]
        assert nd["CustomBaudrateMantissa"]["range"] == [1, 8191]
        assert nd["CustomBaudrateMantissa"]["default"] == 1
        assert nd["CustomBaudrateDivisor"]["range"] == [4, 32]
        assert nd["CustomBaudrateDivisor"]["default"] == 4
        assert nd["CustomBaudrateDividerFlexio"]["range"] == [2, 512]
        assert nd["CustomBaudrateDividerFlexio"]["default"] == 32
        assert nd["UartTimeoutDuration"]["range"] == [0, 4294967295]
        assert nd["UartTimeoutDuration"]["default"] == 1000

    def test_constraints_section_present(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        const = data.get("constraints", {})
        assert "enforced_by_cli" in const
        assert "vendor_gate_only" in const

    def test_constraints_enforced_by_cli_has_baud_validation(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        enforced = data["constraints"]["enforced_by_cli"]
        assert "lpuart_baud_validation" in enforced
        assert "flexio_baud_validation" in enforced

    def test_constraints_vendor_gate_has_key_rules(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        vendor = data["constraints"]["vendor_gate_only"]
        assert "custom_baudrate_computation" in vendor
        assert "hw_channel_uniqueness" in vendor
        assert "callback_coherence" in vendor

    def test_coverage_no_hallucinated_fields(self):
        """Ensure UartIctEnable etc. are NOT in not_yet_exposed."""
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        nye = data["_coverage"]["not_yet_exposed"]
        per_ch_str = json.dumps(nye["per_channel"])
        assert "UartIctEnable" not in per_ch_str
        assert "UartRtsPolEnable" not in per_ch_str
        assert "UartCtsPolEnable" not in per_ch_str
        gen_cfg_str = json.dumps(nye["general_configuration"])
        assert "GeneralCallback" not in gen_cfg_str

    def test_coverage_per_channel_has_expected_fields(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        per_ch = data["_coverage"]["not_yet_exposed"]["per_channel"]
        per_ch_str = json.dumps(per_ch)
        assert "UartInternalLoopbackEnable" in per_ch_str
        assert "UartTimeoutEnable" in per_ch_str
        assert "CustomBaudrateMantissa" in per_ch_str
        assert "CustomBaudrateDivisor" in per_ch_str
        assert len(per_ch) == 4, f"Expected 4 per_channel entries, got {len(per_ch)}: {per_ch}"

    def test_coverage_general_configuration_has_expected_fields(self):
        data = json.loads(_UART_ASSET.read_text(encoding="utf-8"))
        gen_cfg = data["_coverage"]["not_yet_exposed"]["general_configuration"]
        gen_cfg_str = json.dumps(gen_cfg)
        assert "UartDevErrorDetect" in gen_cfg_str
        assert "DisableUartRuntimeErrorDetect" in gen_cfg_str
        assert "UartMultipartitionSupport" in gen_cfg_str
        assert "UartEnableUserModeSupport" in gen_cfg_str
        assert "UartTimeoutMethod" in gen_cfg_str
        assert "UartTimeoutDuration" in gen_cfg_str
        assert "UartVersionInfoApi" in gen_cfg_str
        assert len(gen_cfg) == 7, f"Expected 7 general_configuration entries, got {len(gen_cfg)}: {gen_cfg}"


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

    def test_no_hw_auto_detect_from_existing_channel(self, tmp_path):
        """When --hw is omitted, the existing UartHwChannel is auto-detected."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            baud=115200, mode="interrupt",
        ))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartHwChannel") == "LPUART_3"

    def test_no_hw_auto_detect_preserves_hw_channel(self, tmp_path):
        """Auto-detection preserves the existing UartHwChannel without blanking."""
        project = copy_uart_fixture(tmp_path)
        doc = MexDocument.load(project / "Uart_Example.mex")
        ch_before = _uart_channel_0(doc)
        assert _detail_setting(doc, ch_before, "UartHwChannel") == "LPUART_3"
        result = apply_uart_set(doc, _intent(mode="dma"))
        assert not result.blocked, [d.to_dict() for d in result.diagnostics]
        ch_after = _uart_channel_0(doc)
        assert _detail_setting(doc, ch_after, "UartHwChannel") == "LPUART_3"

    def test_cli_no_hw_auto_detect(self, tmp_path):
        """CLI `uart set` without --hw succeeds on a single-channel fixture."""
        project = copy_uart_fixture(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "rtd_config",
                "uart", "set",
                "--project", str(project),
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


# ===========================================================================
# LPUART enum validation (forward-hardening: validate baud/word_length/
# parity/stop_bits against uart.json enum domains — not dependent on
# particular E2E case literals).
# ===========================================================================

def _load_asset() -> dict:
    """Return the uart.json asset as a dict."""
    return json.loads(_UART_ASSET.read_text(encoding="utf-8"))


class TestLpuartBaudValidation:
    """LPUART baud rate must be validated against DesireBaudrate enum domain."""

    def test_unsupported_baud_returns_blocker(self, tmp_path):
        """An unsupported baud rate (e.g. 999) returns a blocker diagnostic."""
        project = copy_uart_fixture(tmp_path / "baud_invalid")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=999, mode="interrupt",
        ))
        assert result.blocked
        codes = {d.code for d in result.diagnostics}
        assert "unsupported_lpuart_baud" in codes
        diag = next(d for d in result.diagnostics if d.code == "unsupported_lpuart_baud")
        assert "baud" in diag.details
        assert "supported" in diag.details
        assert isinstance(diag.details["supported"], list)
        # The supported list must include standard bauds from the asset
        asset = _load_asset()
        std_bauds = asset["enum_domains"]["DesireBaudrate"]
        assert set(diag.details["supported"]) == set(std_bauds)

    def test_all_standard_baud_rates_accepted(self, tmp_path):
        """Every numeric baud rate in DesireBaudrate must be accepted without blocker.
        CUSTOM is skipped because it is not a numeric baud rate and requires
        separate CustomBaudrateMantissa/Divisor support (future work)."""
        asset = _load_asset()
        std_bauds = asset["enum_domains"]["DesireBaudrate"]
        for idx, enum_val in enumerate(std_bauds):
            # Extract numeric baud from e.g. "LPUART_UART_BAUDRATE_921600"
            parts = enum_val.rsplit("_", 1)
            if parts[1] == "CUSTOM":
                continue  # CUSTOM requires separate support (future work)
            baud_int = int(parts[1])
            project = copy_uart_fixture(tmp_path / f"baud_{idx}")
            doc = MexDocument.load(project / "Uart_Example.mex")
            result = apply_uart_set(doc, _intent(
                hw="LPUART_8", baud=baud_int, mode="interrupt",
            ))
            assert not result.blocked, (
                f"Standard baud {baud_int} ({enum_val}) blocked: "
                f"{[d.to_dict() for d in result.diagnostics]}"
            )

    def test_valid_baud_written_to_mex_field(self, tmp_path):
        """An arbitrary valid baud (115200) is written correctly to DesireBaudrate."""
        project = copy_uart_fixture(tmp_path / "baud_write")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
        ))
        assert not result.blocked
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "DesireBaudrate") == "LPUART_UART_BAUDRATE_115200"


class TestLpuartWordLengthValidation:
    """LPUART word length must be validated against UartWordLength enum domain."""

    def test_unsupported_word_length_returns_blocker(self, tmp_path):
        """An unsupported word_length returns a blocker diagnostic."""
        project = copy_uart_fixture(tmp_path / "wl_invalid")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
            word_length="LPUART_UART_IP_12_BITS_PER_CHAR",
        ))
        assert result.blocked
        codes = {d.code for d in result.diagnostics}
        assert "unsupported_lpuart_word_length" in codes
        diag = next(d for d in result.diagnostics if d.code == "unsupported_lpuart_word_length")
        assert "word_length" in diag.details
        assert "supported" in diag.details
        asset = _load_asset()
        assert set(diag.details["supported"]) == set(asset["enum_domains"]["UartWordLength"])

    def test_all_standard_word_lengths_accepted(self, tmp_path):
        """Every word_length in UartWordLength must be accepted without blocker."""
        asset = _load_asset()
        wls = asset["enum_domains"]["UartWordLength"]
        for idx, wl in enumerate(wls):
            project = copy_uart_fixture(tmp_path / f"wl_{idx}")
            doc = MexDocument.load(project / "Uart_Example.mex")
            result = apply_uart_set(doc, _intent(
                hw="LPUART_8", baud=115200, mode="interrupt",
                word_length=wl,
            ))
            assert not result.blocked, (
                f"Standard word_length {wl} blocked: "
                f"{[d.to_dict() for d in result.diagnostics]}"
            )

    def test_nine_bit_written_correctly(self, tmp_path):
        """9-bit word length is written correctly to UartWordLength."""
        project = copy_uart_fixture(tmp_path / "wl_write")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
            word_length="LPUART_UART_IP_9_BITS_PER_CHAR",
        ))
        assert not result.blocked
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartWordLength") == "LPUART_UART_IP_9_BITS_PER_CHAR"


class TestLpuartParityValidation:
    """LPUART parity type must be validated against UartParityType enum domain."""

    def test_unsupported_parity_returns_blocker(self, tmp_path):
        """An unsupported parity returns a blocker diagnostic."""
        project = copy_uart_fixture(tmp_path / "par_invalid")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
            parity="LPUART_UART_IP_PARITY_MARK",
        ))
        assert result.blocked
        codes = {d.code for d in result.diagnostics}
        assert "unsupported_lpuart_parity" in codes
        diag = next(d for d in result.diagnostics if d.code == "unsupported_lpuart_parity")
        assert "parity" in diag.details
        assert "supported" in diag.details
        asset = _load_asset()
        assert set(diag.details["supported"]) == set(asset["enum_domains"]["UartParityType"])

    def test_all_parity_types_accepted(self, tmp_path):
        """Every parity type in UartParityType must be accepted without blocker."""
        asset = _load_asset()
        pars = asset["enum_domains"]["UartParityType"]
        for idx, par in enumerate(pars):
            project = copy_uart_fixture(tmp_path / f"par_{idx}")
            doc = MexDocument.load(project / "Uart_Example.mex")
            result = apply_uart_set(doc, _intent(
                hw="LPUART_8", baud=115200, mode="interrupt",
                parity=par,
            ))
            assert not result.blocked, (
                f"Standard parity {par} blocked: "
                f"{[d.to_dict() for d in result.diagnostics]}"
            )

    def test_even_parity_written_correctly(self, tmp_path):
        """Even parity is written correctly to UartParityType."""
        project = copy_uart_fixture(tmp_path / "par_write")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
            parity="LPUART_UART_IP_PARITY_EVEN",
        ))
        assert not result.blocked
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartParityType") == "LPUART_UART_IP_PARITY_EVEN"


class TestLpuartStopBitsValidation:
    """LPUART stop bits must be validated against UartStopBitNumber enum domain."""

    def test_unsupported_stop_bits_returns_blocker(self, tmp_path):
        """An unsupported stop_bits returns a blocker diagnostic."""
        project = copy_uart_fixture(tmp_path / "sb_invalid")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
            stop_bits="LPUART_UART_IP_THREE_STOP_BIT",
        ))
        assert result.blocked
        codes = {d.code for d in result.diagnostics}
        assert "unsupported_lpuart_stop_bits" in codes
        diag = next(d for d in result.diagnostics if d.code == "unsupported_lpuart_stop_bits")
        assert "stop_bits" in diag.details
        assert "supported" in diag.details
        asset = _load_asset()
        assert set(diag.details["supported"]) == set(asset["enum_domains"]["UartStopBitNumber"])

    def test_both_stop_bit_values_accepted(self, tmp_path):
        """Both stop-bit values in UartStopBitNumber must be accepted."""
        asset = _load_asset()
        sbs = asset["enum_domains"]["UartStopBitNumber"]
        for idx, sb in enumerate(sbs):
            project = copy_uart_fixture(tmp_path / f"sb_{idx}")
            doc = MexDocument.load(project / "Uart_Example.mex")
            result = apply_uart_set(doc, _intent(
                hw="LPUART_8", baud=115200, mode="interrupt",
                stop_bits=sb,
            ))
            assert not result.blocked, (
                f"Standard stop_bits {sb} blocked: "
                f"{[d.to_dict() for d in result.diagnostics]}"
            )

    def test_two_stop_bits_written_correctly(self, tmp_path):
        """2 stop bits is written correctly to UartStopBitNumber."""
        project = copy_uart_fixture(tmp_path / "sb_write")
        doc = MexDocument.load(project / "Uart_Example.mex")
        result = apply_uart_set(doc, _intent(
            hw="LPUART_8", baud=115200, mode="interrupt",
            stop_bits="LPUART_UART_IP_TWO_STOP_BIT",
        ))
        assert not result.blocked
        ch = _uart_channel_0(doc)
        assert _detail_setting(doc, ch, "UartStopBitNumber") == "LPUART_UART_IP_TWO_STOP_BIT"


class TestUartCoverageAsset:
    """uart.json must carry a _coverage section documenting the editable surface."""

    def test_coverage_section_exists(self):
        asset = _load_asset()
        assert "_coverage" in asset, "uart.json must have a _coverage section"

    def test_coverage_has_configurable_and_not_exposed(self):
        asset = _load_asset()
        cov = asset["_coverage"]
        assert "configurable_today" in cov
        assert "not_yet_exposed" in cov

    def test_configurable_mentions_core_channel_fields(self):
        """configurable_today must mention LPUART channel fields."""
        asset = _load_asset()
        today = asset["_coverage"]["configurable_today"]
        today_flat = json.dumps(today)
        assert "baud" in today_flat.lower() or "Baud" in today_flat or "LPUART" in today_flat
        assert "word" in today_flat.lower() or "UartWordLength" in today_flat or "frame" in today_flat.lower()

    def test_not_yet_exposed_has_per_channel_entries(self):
        """not_yet_exposed must document per-channel gaps."""
        asset = _load_asset()
        nye = asset["_coverage"]["not_yet_exposed"]
        # Check either as a dict with sub-keys or as a flat description string
        nye_flat = json.dumps(nye) if isinstance(nye, dict) else str(nye)
        assert "channel" in nye_flat.lower() or "DetailModuleConfiguration" in nye_flat

    def test_not_yet_exposed_has_general_configuration_entries(self):
        """not_yet_exposed must document GeneralConfiguration gaps."""
        asset = _load_asset()
        nye = asset["_coverage"]["not_yet_exposed"]
        nye_flat = json.dumps(nye) if isinstance(nye, dict) else str(nye)
        assert "general" in nye_flat.lower() or "GeneralConfiguration" in nye_flat

    def test_references_cite_issue_44(self):
        asset = _load_asset()
        refs = asset["_coverage"].get("references", [])
        refs_text = json.dumps(refs)
        assert "#44" in refs_text, f"references must cite issue #44, got: {refs_text}"


class TestAllLpuartInstances:
    """All 16 LPUART_0..15 must be configurable via apply_uart_set."""

    def test_all_sixteen_in_instance_map(self):
        """instance_irq_clock_map must contain LPUART_0 through LPUART_15."""
        asset = _load_asset()
        mapping = asset["instance_irq_clock_map"]
        for n in range(16):
            key = f"LPUART_{n}"
            assert key in mapping, f"Missing LPUART instance: {key}"

    def test_lpuart_0_and_8_are_plat_clk(self):
        """LPUART_0 and LPUART_8 use AIPS_PLAT_CLK."""
        asset = _load_asset()
        mapping = asset["instance_irq_clock_map"]
        assert mapping["LPUART_0"]["clock_select"] == "AIPS_PLAT_CLK"
        assert mapping["LPUART_8"]["clock_select"] == "AIPS_PLAT_CLK"

    def test_other_lpuarts_are_slow_clk(self):
        """LPUART_1..7 and LPUART_9..15 use AIPS_SLOW_CLK."""
        asset = _load_asset()
        mapping = asset["instance_irq_clock_map"]
        plat = {0, 8}
        for n in range(16):
            if n in plat:
                continue
            key = f"LPUART_{n}"
            assert mapping[key]["clock_select"] == "AIPS_SLOW_CLK", (
                f"LPUART_{n} clock_select expected AIPS_SLOW_CLK, "
                f"got {mapping[key]['clock_select']}"
            )

    def test_every_lpuart_configurable_without_blockers(self, tmp_path):
        """Every LPUART_0..15 configurable via apply_uart_set with no blockers."""
        for n in range(16):
            hw = f"LPUART_{n}"
            project = copy_uart_fixture(tmp_path / f"inst_{n}")
            doc = MexDocument.load(project / "Uart_Example.mex")
            result = apply_uart_set(doc, _intent(
                hw=hw, baud=115200, mode="interrupt",
            ))
            assert not result.blocked, (
                f"apply_uart_set blocked for {hw}: "
                f"{[d.to_dict() for d in result.diagnostics]}"
            )
