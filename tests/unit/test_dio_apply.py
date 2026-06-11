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
# File:        test_dio_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-12
# Version:     0.1.0
# Description: Unit/integration tests for Dio output channel insertion
#              (RTD-MEX-DIO-001): add LED_CTRL on PTA5, cross-module Dio+Port.
# =================================================================================

"""Dio LED_CTRL output channel insertion (RTD-MEX-DIO-001).

The Uart_Example_S32K344 fixture has:
  Dio config_set with DioPort_0 (DioPortId=0, empty DioChannel array).
  Port config_set with PortContainer_0 and 4 PortPin structs (PortPinIds 1-4).
  <pins> section with 4 <pin> entries (LPUART3 + FXIO).

Pin PTA5: mscr=5, direction=gpio, pin_mapbga257=A3 (from pins.json).
DioPortId = mscr // 16 = 0, DioChannelId = mscr % 16 = 5.
DioPort_0 (DioPortId=0) already exists in the fixture.

This case inserts:
  (A) Dio channel into DioPort_0.DioChannel array:
        Name=LED_CTRL, DioChannelId=5, PDACSlot=VIRTUAL_WRAPPER_PDAC0
  (B) <pin> header entry for the GPIO pad:
        peripheral=SIUL2, signal="gpio, 5", pin_num=A3, pin_signal=PTA5
        with direction=OUTPUT feature
  (C) PortPin struct appended to PortContainer_0/PortPin array:
        Name=Led_Ctrl, PortPinId=max+1 (=5), PortPinDirectionChangeable=false,
        PortPinModeChangeable=false (GPIO output -- not changeable at runtime)
"""
import difflib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_dio_set
from rtd_config.intent import Intent
from rtd_config.modules.dio import DioProvider
from tests.fixtures import copy_uart_fixture


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "dio", "action": "set", "payload": payload})


def _standard_intent() -> Intent:
    """Intent for LED_CTRL on PTA5, direction=output."""
    return _intent(
        add_channel="LED_CTRL",
        pin="PTA5",
        direction="output",
    )


# ---------------------------------------------------------------------------
# Document navigation helpers
# ---------------------------------------------------------------------------

def _dio_cfg(doc: MexDocument) -> ET.Element | None:
    return doc.find_config_set("Dio")


def _dio_port_0(doc: MexDocument) -> ET.Element | None:
    """Return the DioPort_0 struct (DioPortId=0) from the Dio config set."""
    cfg = _dio_cfg(doc)
    if cfg is None:
        return None
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "DioPort":
            for child in el:
                if not child.tag.endswith("struct"):
                    continue
                id_setting = doc.find_child_setting(child, "DioPortId")
                if id_setting is not None and id_setting.attrib.get("value") == "0":
                    return child
    return None


def _dio_channel_array(doc: MexDocument) -> ET.Element | None:
    """Return the DioChannel array inside DioPort_0."""
    port = _dio_port_0(doc)
    if port is None:
        return None
    for el in port:
        if el.tag.endswith("array") and el.attrib.get("name") == "DioChannel":
            return el
    return None


def _dio_channel_structs(doc: MexDocument) -> list[ET.Element]:
    arr = _dio_channel_array(doc)
    if arr is None:
        return []
    return [c for c in arr if c.tag.endswith("struct")]


def _pins_function(doc: MexDocument) -> ET.Element | None:
    """Return the <pins> child of the PortContainer_0_VS_0 function element."""
    for el in doc.root.iter():
        if el.tag.endswith("function") and el.attrib.get("name") == "PortContainer_0_VS_0":
            for child in el:
                if child.tag.endswith("pins"):
                    return child
    return None


def _pin_entries(doc: MexDocument) -> list[ET.Element]:
    pins_el = _pins_function(doc)
    if pins_el is None:
        return []
    return [c for c in pins_el if c.tag.endswith("pin")]


def _portpin_array(doc: MexDocument) -> ET.Element | None:
    port_cfg = doc.find_config_set("Port")
    if port_cfg is None:
        return None
    for el in port_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
            return el
    return None


def _portpin_structs(doc: MexDocument) -> list[ET.Element]:
    arr = _portpin_array(doc)
    if arr is None:
        return []
    return [c for c in arr if c.tag.endswith("struct")]


def _setting_value(doc: MexDocument, el: ET.Element, name: str) -> str | None:
    s = doc.find_child_setting(el, name)
    return s.attrib.get("value") if s is not None else None


def _changed_lines(before: bytes, after: bytes) -> list[str]:
    b = before.decode("utf-8").splitlines(keepends=True)
    a = after.decode("utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(b, a, n=0, lineterm="")
    return [
        line for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


# ---------------------------------------------------------------------------
# Test 1: Dio channel inserted into DioPort_0 with correct fields
# ---------------------------------------------------------------------------

def test_dio_channel_inserted_into_dioport_0(tmp_path):
    """DioChannel LED_CTRL lands in DioPort_0 (DioPortId=0) with correct Name and DioChannelId=5."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_dio_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "dio" in result.changed_modules

    structs = _dio_channel_structs(doc)
    assert len(structs) == 1, f"Expected 1 DioChannel struct, got {len(structs)}"

    ch = structs[0]
    assert ch.attrib.get("name") == "0", (
        f"First DioChannel struct name must be '0', got '{ch.attrib.get('name')}'"
    )
    assert _setting_value(doc, ch, "Name") == "LED_CTRL", (
        f"Expected Name=LED_CTRL, got {_setting_value(doc, ch, 'Name')}"
    )
    assert _setting_value(doc, ch, "DioChannelId") == "5", (
        f"Expected DioChannelId=5 (mscr=5, port-relative 5%16=5), "
        f"got {_setting_value(doc, ch, 'DioChannelId')}"
    )


def test_dio_channel_has_pdac_slot(tmp_path):
    """DioChannel LED_CTRL has PDACSlot=VIRTUAL_WRAPPER_PDAC0 from dio.json default."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    structs = _dio_channel_structs(doc)
    assert len(structs) == 1
    ch = structs[0]
    assert _setting_value(doc, ch, "PDACSlot") == "VIRTUAL_WRAPPER_PDAC0", (
        f"Expected PDACSlot=VIRTUAL_WRAPPER_PDAC0, got {_setting_value(doc, ch, 'PDACSlot')}"
    )


def test_dio_channel_has_ecuc_partition_ref_array(tmp_path):
    """DioChannel LED_CTRL has an empty DioChannelEcucPartitionRef array."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    structs = _dio_channel_structs(doc)
    assert len(structs) == 1
    ch = structs[0]
    array_names = {
        el.attrib.get("name")
        for el in ch
        if el.tag.endswith("array")
    }
    assert "DioChannelEcucPartitionRef" in array_names, (
        f"DioChannel must have DioChannelEcucPartitionRef array; arrays found: {array_names}"
    )


# ---------------------------------------------------------------------------
# Test 2: Port <pin> header inserted with SIUL2/GPIO signal format
# ---------------------------------------------------------------------------

def test_pin_header_siul2_gpio_inserted(tmp_path):
    """GPIO <pin> header: peripheral=SIUL2, signal='gpio, 5', pin_num=A3, pin_signal=PTA5."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_dio_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "port" in result.changed_modules

    pins = _pin_entries(doc)
    # Original 4 pins + 1 new GPIO = 5
    assert len(pins) == 5, f"Expected 5 pin entries, got {len(pins)}"

    gpio_pin = next(
        (p for p in pins
         if p.attrib.get("peripheral") == "SIUL2" and p.attrib.get("signal") == "gpio, 5"),
        None,
    )
    assert gpio_pin is not None, "SIUL2 gpio,5 pin header not found"
    assert gpio_pin.attrib.get("pin_num") == "A3", (
        f"Expected pin_num=A3 (BGA257 for PTA5), got {gpio_pin.attrib.get('pin_num')}"
    )
    assert gpio_pin.attrib.get("pin_signal") == "PTA5", (
        f"Expected pin_signal=PTA5, got {gpio_pin.attrib.get('pin_signal')}"
    )


def test_pin_header_gpio_has_direction_output(tmp_path):
    """GPIO <pin> has direction=OUTPUT pin_feature (output LED)."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    pins = _pin_entries(doc)
    gpio_pin = next(
        (p for p in pins
         if p.attrib.get("peripheral") == "SIUL2" and p.attrib.get("signal") == "gpio, 5"),
        None,
    )
    assert gpio_pin is not None

    direction_found = False
    for child in gpio_pin.iter():
        if child.tag.endswith("pin_feature") and child.attrib.get("name") == "direction":
            assert child.attrib.get("value") == "OUTPUT", (
                f"GPIO direction must be OUTPUT, got {child.attrib.get('value')}"
            )
            direction_found = True
    assert direction_found, "GPIO pin must have direction=OUTPUT pin_feature"


# ---------------------------------------------------------------------------
# Test 3: Port PortPin struct inserted with correct fields for GPIO output
# ---------------------------------------------------------------------------

def test_portpin_struct_led_ctrl_inserted(tmp_path):
    """Led_Ctrl PortPin struct appended with correct Name and next PortPinId."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_dio_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]

    structs = _portpin_structs(doc)
    # Original 4 structs + 1 new = 5
    assert len(structs) == 5, f"Expected 5 PortPin structs, got {len(structs)}"

    led_struct = structs[4]
    assert led_struct.attrib.get("name") == "4", (
        f"Led_Ctrl struct name must be '4', got '{led_struct.attrib.get('name')}'"
    )
    assert _setting_value(doc, led_struct, "Name") == "Led_Ctrl", (
        f"Expected Name=Led_Ctrl, got {_setting_value(doc, led_struct, 'Name')}"
    )
    # PortPinId = max(existing) + 1 = 4 + 1 = 5
    assert _setting_value(doc, led_struct, "PortPinId") == "5", (
        f"Expected PortPinId=5 (max+1), got {_setting_value(doc, led_struct, 'PortPinId')}"
    )


def test_portpin_struct_gpio_output_fields(tmp_path):
    """Led_Ctrl PortPin struct has the complete GPIO output field set per the task spec.

    Key differences from the LPUART pattern:
      PortPinDirectionChangeable=false (GPIO output -- not changeable at runtime)
      PortPinModeChangeable=false
    All other fields match the portpin.json template defaults.
    """
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    structs = _portpin_structs(doc)
    led_struct = structs[4]

    required_fields = [
        ("PortPinPue", "false"),
        ("PortPinPus", "false"),
        ("PortPinSafeMode", "false"),
        ("PortPinDse", "false"),
        ("PortPinWithReadBack", "false"),
        ("PortPinPke", "false"),
        ("PortPinIfe", "false"),
        ("PortPinDirectionChangeable", "false"),   # GPIO output: not changeable
        ("PortPinModeChangeable", "false"),          # GPIO output: not changeable
        ("PortPinInvertControl", "false"),
        ("PortPinSiul2Instance", "SIUL2_0"),
        ("PortPinInitialMode", "PORT_GPIO_MODE"),
        ("OBEGroupSelect", "NO_OBE_GROUP"),
        ("MscrPdacSlot", "VIRTUAL_WRAPPER_PDAC0"),
        ("ImcrPdacSlot", "VIRTUAL_WRAPPER_PDAC0"),
    ]
    for field_name, expected in required_fields:
        actual = _setting_value(doc, led_struct, field_name)
        assert actual == expected, (
            f"Led_Ctrl: expected {field_name}={expected}, got {actual}"
        )

    # Required arrays
    array_names = {
        el.attrib.get("name")
        for el in led_struct
        if el.tag.endswith("array")
    }
    assert "IGFSettings" in array_names, "Missing IGFSettings array"
    assert "PortPinEcucPartitionRef" in array_names, "Missing PortPinEcucPartitionRef array"


# ---------------------------------------------------------------------------
# Test 4: existing Dio/Port entries untouched
# ---------------------------------------------------------------------------

def test_existing_dioport_0_unchanged(tmp_path):
    """DioPort_0's DioPortId and Name remain untouched; only its DioChannel array is populated."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    port = _dio_port_0(doc)
    assert port is not None, "DioPort_0 must exist after apply"
    assert _setting_value(doc, port, "DioPortId") == "0"
    assert _setting_value(doc, port, "Name") == "DioPort_0"


def test_existing_portpin_structs_untouched(tmp_path):
    """Existing 4 PortPin structs (Flexio0_Tx, Flexio1_Rx, Lpuart3_Tx, Lpuart3_Rx) untouched."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    structs = _portpin_structs(doc)
    assert _setting_value(doc, structs[0], "Name") == "Flexio0_Tx"
    assert _setting_value(doc, structs[0], "PortPinId") == "1"

    assert _setting_value(doc, structs[1], "Name") == "Flexio1_Rx"
    assert _setting_value(doc, structs[1], "PortPinId") == "2"

    assert _setting_value(doc, structs[2], "Name") == "Lpuart3_Tx"
    assert _setting_value(doc, structs[2], "PortPinId") == "3"

    assert _setting_value(doc, structs[3], "Name") == "Lpuart3_Rx"
    assert _setting_value(doc, structs[3], "PortPinId") == "4"


def test_existing_pin_headers_untouched(tmp_path):
    """First 4 <pin> entries (LPUART3 + FXIO) remain at the same positions."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_dio_set(doc, _standard_intent())

    pins = _pin_entries(doc)
    assert pins[0].attrib.get("peripheral") == "LPUART3"
    assert pins[0].attrib.get("signal") == "lpuart3_rx"
    assert pins[0].attrib.get("pin_signal") == "PTD3"

    assert pins[1].attrib.get("peripheral") == "LPUART3"
    assert pins[1].attrib.get("signal") == "lpuart3_tx"
    assert pins[1].attrib.get("pin_signal") == "PTD2"

    assert pins[2].attrib.get("peripheral") == "FXIO"
    assert pins[2].attrib.get("signal") == "fxio_d0"

    assert pins[3].attrib.get("peripheral") == "FXIO"
    assert pins[3].attrib.get("signal") == "fxio_d1"


# ---------------------------------------------------------------------------
# Test 5: pin-legality -- reject non-GPIO pins
# ---------------------------------------------------------------------------

def test_blocker_on_non_gpio_pin(tmp_path):
    """PTA24 has no gpio direction record in pins.json -- apply must return blocker dio_pin_not_gpio.

    pins.json only has eMIOS/FXIO records for PTA24 (all direction=input, no gpio mux),
    so _find_gpio_pin_record returns None for this pin.
    """
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    intent = _intent(add_channel="LED_CTRL", pin="PTA24", direction="output")
    result = apply_dio_set(doc, intent)

    assert result.blocked, "Expected blocker for non-GPIO pin PTA24"
    codes = [d.code for d in result.diagnostics]
    assert any("dio_pin_not_gpio" in code for code in codes), (
        f"Expected dio_pin_not_gpio diagnostic, got: {codes}"
    )


def test_blocker_on_already_used_pin(tmp_path):
    """PTA5 already configured as PortPin -> second apply must be idempotent (no blocker)."""
    # Actually PTA5 is FREE in the fixture; test that an already-configured pin
    # (simulate by first applying, then applying again) is idempotent.
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc1 = MexDocument.load(mex)
    r1 = apply_dio_set(doc1, _standard_intent())
    assert not r1.blocked, [d.to_dict() for d in r1.diagnostics]
    doc1.write(mex)

    doc2 = MexDocument.load(mex)
    r2 = apply_dio_set(doc2, _standard_intent())
    # Second apply must be idempotent (not blocked, not re-inserting)
    assert not r2.blocked, [d.to_dict() for d in r2.diagnostics]

    doc2.write(mex)
    doc3 = MexDocument.load(mex)
    channel_structs = _dio_channel_structs(doc3)
    assert len(channel_structs) == 1, (
        f"Idempotency: expected 1 DioChannel, got {len(channel_structs)}"
    )
    portpin_structs = _portpin_structs(doc3)
    assert len(portpin_structs) == 5, (
        f"Idempotency: expected 5 PortPin structs, got {len(portpin_structs)}"
    )


# ---------------------------------------------------------------------------
# Test 6: LL-011 perturbed-fixture next-id proof
# ---------------------------------------------------------------------------

def test_portpin_id_non_trivial_with_perturbed_fixture(tmp_path):
    """Perturb the fixture max PortPinId to 17 -- Led_Ctrl must land at PortPinId=18.

    The fixture has PortPinIds 1-4 (structs 0-3).  We mutate the last struct's
    PortPinId to 17.  After that max_existing_id=17, existing_count=4.
    Expected: Led_Ctrl: struct name='4', PortPinId=18.
    A hardcoded id of 5 would fail (expected 18).
    """
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # Perturb: set last PortPin struct's PortPinId to 17
    doc_prep = MexDocument.load(mex)
    port_cfg = doc_prep.find_config_set("Port")
    portpin_arr = None
    for el in port_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "PortPin":
            portpin_arr = el
            break
    assert portpin_arr is not None

    existing = [c for c in portpin_arr if c.tag.endswith("struct")]
    assert len(existing) == 4, f"Precondition: must have 4 PortPin structs, got {len(existing)}"

    last_struct = existing[-1]
    pid_setting = doc_prep.find_child_setting(last_struct, "PortPinId")
    assert pid_setting is not None
    pid_setting.set("value", "17")
    doc_prep.write(mex)

    # Apply on perturbed fixture
    doc_apply = MexDocument.load(mex)
    result = apply_dio_set(doc_apply, _standard_intent())
    assert not result.blocked, [d.to_dict() for d in result.diagnostics]

    structs_after = _portpin_structs(doc_apply)
    assert len(structs_after) == 5, f"Expected 5 structs after insertion, got {len(structs_after)}"

    led_struct = structs_after[4]
    assert led_struct.attrib.get("name") == "4", (
        f"Led_Ctrl struct name must be '4', got '{led_struct.attrib.get('name')}'"
    )
    led_id = _setting_value(doc_apply, led_struct, "PortPinId")
    assert led_id == "18", (
        f"Led_Ctrl PortPinId must be 18 (max=17+1), got {led_id}. "
        "If this is 5, the dynamic next-id computation is broken (hardcoded)."
    )


# ---------------------------------------------------------------------------
# Test 7: byte-narrow diff
# ---------------------------------------------------------------------------

def test_edit_is_byte_narrow(tmp_path):
    """Diff adds only: Dio channel struct, GPIO <pin> entry, and PortPin struct lines."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_dio_set(doc, _standard_intent())
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # Inserting 1 DioChannel struct (~4 lines), 1 GPIO pin header (~5 lines),
    # 1 PortPin struct (~20 lines). Allow generous upper bound.
    assert len(changed) <= 50, (
        f"Unexpectedly broad diff: {len(changed)} lines:\n" + "".join(changed)
    )
    added = [line for line in changed if line.startswith("+")]
    assert any("LED_CTRL" in line for line in added), "Missing LED_CTRL in diff"
    assert any("gpio, 5" in line for line in added), "Missing gpio, 5 signal in diff"
    assert any("PTA5" in line for line in added), "Missing PTA5 in diff"
    assert any("Led_Ctrl" in line for line in added), "Missing Led_Ctrl PortPin in diff"
    assert any("DioChannelId" in line for line in added), "Missing DioChannelId in diff"

    # XML declaration preserved
    after_lines = mex.read_bytes().decode("utf-8").splitlines()
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>'


# ---------------------------------------------------------------------------
# Test 8: well-formed reload
# ---------------------------------------------------------------------------

def test_written_file_is_well_formed(tmp_path):
    """Written .mex reloads as well-formed XML with all three insertions accessible."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc = MexDocument.load(mex)
    apply_dio_set(doc, _standard_intent())
    doc.write(mex)

    reloaded = MexDocument.load(mex)

    # Dio channel
    ch_structs = _dio_channel_structs(reloaded)
    assert len(ch_structs) == 1
    assert _setting_value(reloaded, ch_structs[0], "Name") == "LED_CTRL"
    assert _setting_value(reloaded, ch_structs[0], "DioChannelId") == "5"

    # GPIO pin header
    pins = _pin_entries(reloaded)
    assert len(pins) == 5
    gpio_pin = next(
        (p for p in pins if p.attrib.get("peripheral") == "SIUL2"), None
    )
    assert gpio_pin is not None, "SIUL2 GPIO pin header not found in reloaded doc"
    assert gpio_pin.attrib.get("signal") == "gpio, 5"

    # PortPin struct
    pp_structs = _portpin_structs(reloaded)
    assert len(pp_structs) == 5
    assert _setting_value(reloaded, pp_structs[4], "Name") == "Led_Ctrl"
    assert _setting_value(reloaded, pp_structs[4], "PortPinId") == "5"


# ---------------------------------------------------------------------------
# Test 9: CLI integration -- dio set --configure returns passed
# ---------------------------------------------------------------------------

def test_cli_dio_set_configure(tmp_path):
    """CLI: dio set --add-channel LED_CTRL --pin PTA5 --configure --json returns passed."""
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "dio", "set",
            "--project", str(project),
            "--add-channel", "LED_CTRL",
            "--pin", "PTA5",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert "dio" in payload["changed_modules"]
    assert "port" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"


# ---------------------------------------------------------------------------
# Test 10: CLI integration -- plan-only (no --configure) does not modify file
# ---------------------------------------------------------------------------

def test_cli_dio_set_plan_only(tmp_path):
    """Plan-only run returns plan without modifying the .mex file."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "dio", "set",
            "--project", str(project),
            "--add-channel", "LED_CTRL",
            "--pin", "PTA5",
            "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["command"] == "plan", payload
    assert mex.read_bytes() == original, "File was modified by plan-only run"


# ---------------------------------------------------------------------------
# Test 11: plan() declares both Dio-owned channel AND Port cross-module dependency
# ---------------------------------------------------------------------------

def test_plan_declares_dio_and_port_dependency(tmp_path):
    """DioProvider.plan() returns at least one dio-owned change AND a port-owned dependency.

    Per LL-010: cross-module dependencies must be DECLARED in the plan, not
    silently edited. The Port GPIO pin routing is port-owned.
    """
    intent = _standard_intent()
    plan = DioProvider().plan(intent)

    dio_changes = [c for c in plan.changes if c.owner == "dio"]
    port_changes = [c for c in plan.changes if c.owner == "port"]

    assert len(dio_changes) >= 1, (
        f"No dio-owned change in plan: {plan.to_dict()}"
    )
    assert len(port_changes) >= 1, (
        f"No port-owned cross-module dependency in plan (LL-010 violation): {plan.to_dict()}"
    )

    # The port dependency must reference the GPIO pin routing path
    port_dep = port_changes[0]
    assert port_dep.module == "port"
    assert port_dep.owner == "port"


# ---------------------------------------------------------------------------
# Test 12: dio.json asset exists and has the correct channel field schema
# ---------------------------------------------------------------------------

def test_dio_json_asset_has_correct_schema(tmp_path):
    """dio.json asset must exist and contain DioChannelId mapping rule and PDACSlot default.

    This test verifies that runtime reads the committed asset, not raw xdm.
    Grounded in Dio.xdm: DioChannelId range 0-15 (port-relative),
    mapping rule: DioPortId = mscr // 16, DioChannelId = mscr % 16.
    """
    import pathlib
    asset_path = (
        pathlib.Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "dio" / "dio.json"
    )
    assert asset_path.exists(), f"dio.json asset not found at {asset_path}"

    asset = json.loads(asset_path.read_text(encoding="utf-8"))

    # Must have the DioPort ID mapping rule
    assert "dio_port_id_rule" in asset, "dio.json must have 'dio_port_id_rule' key"
    assert "dio_channel_id_rule" in asset, "dio.json must have 'dio_channel_id_rule' key"

    # Must have channel field defaults
    assert "channel_fields" in asset, "dio.json must have 'channel_fields' key"
    fields = asset["channel_fields"]
    assert "PDACSlot" in fields, "channel_fields must include PDACSlot"
    assert fields["PDACSlot"]["default"] == "VIRTUAL_WRAPPER_PDAC0", (
        "PDACSlot default must be VIRTUAL_WRAPPER_PDAC0"
    )

    # Verify the mapping rule is correct for PTA5 (mscr=5)
    # DioPortId = mscr // 16 => should state the // 16 operation
    assert "16" in asset["dio_port_id_rule"], (
        "dio_port_id_rule must reference the mscr // 16 mapping"
    )
    assert "16" in asset["dio_channel_id_rule"], (
        "dio_channel_id_rule must reference the mscr % 16 mapping"
    )


# ---------------------------------------------------------------------------
# Test 13: idempotent -- second CLI apply with same channel/pin no duplicate
# ---------------------------------------------------------------------------

def test_idempotent_cli_apply(tmp_path):
    """Two CLI configure runs with the same LED_CTRL/PTA5 do not duplicate entries."""
    project = copy_uart_fixture(tmp_path)

    # First apply
    r1 = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "dio", "set",
            "--project", str(project),
            "--add-channel", "LED_CTRL",
            "--pin", "PTA5",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert r1.returncode == 0, f"First apply failed: {r1.stdout}\n{r1.stderr}"

    # Second apply
    r2 = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "dio", "set",
            "--project", str(project),
            "--add-channel", "LED_CTRL",
            "--pin", "PTA5",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert r2.returncode == 0, f"Second apply failed: {r2.stdout}\n{r2.stderr}"

    # Verify no duplicates
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    ch_structs = _dio_channel_structs(doc)
    assert len(ch_structs) == 1, (
        f"Idempotency: expected 1 DioChannel after 2 applies, got {len(ch_structs)}"
    )
    pp_structs = _portpin_structs(doc)
    assert len(pp_structs) == 5, (
        f"Idempotency: expected 5 PortPin structs after 2 applies, got {len(pp_structs)}"
    )
    pin_entries = _pin_entries(doc)
    assert len(pin_entries) == 5, (
        f"Idempotency: expected 5 pin entries after 2 applies, got {len(pin_entries)}"
    )
