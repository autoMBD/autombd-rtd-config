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
# File:        test_port_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Unit/integration tests for Port pin-routing insertion
#              (RTD-MEX-PORT-001): configure LPUART_0 TX/RX on PTA27/PTA28.
# =================================================================================

"""Port LPUART_0 TX/RX pin configuration (RTD-MEX-PORT-001).

The Uart_Example_S32K344 fixture has:
  <pins> section containing LPUART3 + FXIO pin headers (lines ~44-61)
  Port config_set PortContainer[0] PortPin array with 4 structs (indices 0-3,
  PortPinIds 1-4) for Flexio0_Tx, Flexio1_Rx, Lpuart3_Tx, Lpuart3_Rx.

This case inserts:
  (A) Two <pin> header entries after the last existing FXIO pin inside
      <function name="PortContainer_0_VS_0"><pins>:
        LPUART0 TX  peripheral=LPUART0, signal=lpuart0_tx, pin_num=M2, pin_signal=PTA27
        LPUART0 RX  peripheral=LPUART0, signal=lpuart0_rx, pin_num=N2, pin_signal=PTA28
  (B) Two PortPin struct entries appended to the PortContainer[0]/PortPin array:
        struct name=4: Name=Lpuart0_Tx, PortPinId=5 (max+1)
        struct name=5: Name=Lpuart0_Rx, PortPinId=6

Legal-pin validation prevents writing illegal pins; blocker code=port_illegal_pin.
"""
import difflib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_port_set
from rtd_config.intent import Intent
from rtd_config.modules.port import PortProvider
from tests.fixtures import copy_uart_fixture


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "port", "action": "set", "payload": payload})


def _standard_intent() -> Intent:
    """Intent for LPUART_0 TX=PTA27, RX=PTA28 -- the valid case."""
    return _intent(
        peripheral="LPUART_0",
        pins={"tx": "PTA27", "rx": "PTA28"},
    )


# ---------------------------------------------------------------------------
# Helpers to navigate the document
# ---------------------------------------------------------------------------

def _pins_function(doc: MexDocument) -> ET.Element | None:
    """Return the <pins> child of the PortContainer_0_VS_0 function element."""
    for el in doc.root.iter():
        if el.tag.endswith("function") and el.attrib.get("name") == "PortContainer_0_VS_0":
            for child in el:
                if child.tag.endswith("pins"):
                    return child
    return None


def _pin_entries(doc: MexDocument) -> list[ET.Element]:
    """Return all <pin> elements inside PortContainer_0_VS_0 <pins>."""
    pins_el = _pins_function(doc)
    if pins_el is None:
        return []
    return [c for c in pins_el if c.tag.endswith("pin")]


def _portpin_array(doc: MexDocument) -> ET.Element | None:
    """Return the PortPin array inside PortContainer[0]."""
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


def _pin_attr(el: ET.Element, attr: str) -> str | None:
    return el.attrib.get(attr)


def _changed_lines(before: bytes, after: bytes) -> list[str]:
    b = before.decode("utf-8").splitlines(keepends=True)
    a = after.decode("utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(b, a, n=0, lineterm="")
    return [
        line for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


# ---------------------------------------------------------------------------
# Test 1: <pin> header entries are inserted with correct attributes
# ---------------------------------------------------------------------------
def test_pin_header_tx_inserted_correctly(tmp_path):
    """TX pin header: peripheral=LPUART0, signal=lpuart0_tx, pin_num=M2, pin_signal=PTA27."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_port_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "port" in result.changed_modules

    pins = _pin_entries(doc)
    # Original 4 pins + 2 new = 6
    assert len(pins) == 6, f"Expected 6 pin entries, got {len(pins)}"

    # Find the LPUART0 TX pin
    tx_pin = next(
        (p for p in pins
         if p.attrib.get("peripheral") == "LPUART0" and p.attrib.get("signal") == "lpuart0_tx"),
        None,
    )
    assert tx_pin is not None, "LPUART0 lpuart0_tx pin header not found"
    assert _pin_attr(tx_pin, "pin_num") == "M2", f"Expected M2, got {_pin_attr(tx_pin, 'pin_num')}"
    assert _pin_attr(tx_pin, "pin_signal") == "PTA27", f"Expected PTA27, got {_pin_attr(tx_pin, 'pin_signal')}"


def test_pin_header_rx_inserted_correctly(tmp_path):
    """RX pin header: peripheral=LPUART0, signal=lpuart0_rx, pin_num=N2, pin_signal=PTA28."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_port_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]

    pins = _pin_entries(doc)
    rx_pin = next(
        (p for p in pins
         if p.attrib.get("peripheral") == "LPUART0" and p.attrib.get("signal") == "lpuart0_rx"),
        None,
    )
    assert rx_pin is not None, "LPUART0 lpuart0_rx pin header not found"
    assert _pin_attr(rx_pin, "pin_num") == "N2", f"Expected N2, got {_pin_attr(rx_pin, 'pin_num')}"
    assert _pin_attr(rx_pin, "pin_signal") == "PTA28", f"Expected PTA28, got {_pin_attr(rx_pin, 'pin_signal')}"


def test_pin_header_tx_has_direction_output(tmp_path):
    """TX pin has direction=OUTPUT pin_feature; RX is self-closed with no direction feature."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    apply_port_set(doc, _standard_intent())

    pins = _pin_entries(doc)
    tx_pin = next(
        (p for p in pins
         if p.attrib.get("peripheral") == "LPUART0" and p.attrib.get("signal") == "lpuart0_tx"),
        None,
    )
    assert tx_pin is not None

    # TX must have a <pin_features> child containing direction=OUTPUT
    direction_found = False
    for child in tx_pin.iter():
        if child.tag.endswith("pin_feature") and child.attrib.get("name") == "direction":
            assert child.attrib.get("value") == "OUTPUT", (
                f"TX direction must be OUTPUT, got {child.attrib.get('value')}"
            )
            direction_found = True
    assert direction_found, "TX pin must have a direction=OUTPUT pin_feature"


def test_pin_header_rx_has_no_direction_feature(tmp_path):
    """RX pin entry has no pin_features / direction child (input-only, self-closed)."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    apply_port_set(doc, _standard_intent())

    pins = _pin_entries(doc)
    rx_pin = next(
        (p for p in pins
         if p.attrib.get("peripheral") == "LPUART0" and p.attrib.get("signal") == "lpuart0_rx"),
        None,
    )
    assert rx_pin is not None

    # RX must have NO direction pin_feature
    for child in rx_pin.iter():
        if child.tag.endswith("pin_feature") and child.attrib.get("name") == "direction":
            pytest_fail_msg = (
                f"RX pin must have no direction feature, "
                f"but found direction={child.attrib.get('value')}"
            )
            assert False, pytest_fail_msg


# ---------------------------------------------------------------------------
# Test 2: PortPin struct entries are inserted with correct values
# ---------------------------------------------------------------------------
def test_portpin_tx_struct_inserted_correctly(tmp_path):
    """Lpuart0_Tx struct appended with correct Name and next PortPinId."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_port_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]

    structs = _portpin_structs(doc)
    # Original 4 structs + 2 new = 6
    assert len(structs) == 6, f"Expected 6 PortPin structs, got {len(structs)}"

    tx_struct = structs[4]
    assert tx_struct.attrib.get("name") == "4", (
        f"Lpuart0_Tx struct name must be '4', got '{tx_struct.attrib.get('name')}'"
    )
    assert _setting_value(doc, tx_struct, "Name") == "Lpuart0_Tx", (
        f"Expected Name=Lpuart0_Tx, got {_setting_value(doc, tx_struct, 'Name')}"
    )
    # PortPinId = previous max + 1 = 4 + 1 = 5
    assert _setting_value(doc, tx_struct, "PortPinId") == "5", (
        f"Expected PortPinId=5, got {_setting_value(doc, tx_struct, 'PortPinId')}"
    )


def test_portpin_rx_struct_inserted_correctly(tmp_path):
    """Lpuart0_Rx struct appended with correct Name and next PortPinId."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_port_set(doc, _standard_intent())

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]

    structs = _portpin_structs(doc)
    assert len(structs) == 6, f"Expected 6 PortPin structs, got {len(structs)}"

    rx_struct = structs[5]
    assert rx_struct.attrib.get("name") == "5", (
        f"Lpuart0_Rx struct name must be '5', got '{rx_struct.attrib.get('name')}'"
    )
    assert _setting_value(doc, rx_struct, "Name") == "Lpuart0_Rx", (
        f"Expected Name=Lpuart0_Rx, got {_setting_value(doc, rx_struct, 'Name')}"
    )
    assert _setting_value(doc, rx_struct, "PortPinId") == "6", (
        f"Expected PortPinId=6, got {_setting_value(doc, rx_struct, 'PortPinId')}"
    )


def test_portpin_struct_has_all_required_fields(tmp_path):
    """Each new PortPin struct has the full field set from the portpin.json template."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    apply_port_set(doc, _standard_intent())

    structs = _portpin_structs(doc)
    tx_struct = structs[4]

    required_fields = [
        ("PortPinPue", "false"),
        ("PortPinPus", "false"),
        ("PortPinSafeMode", "false"),
        ("PortPinDse", "false"),
        ("PortPinWithReadBack", "false"),
        ("PortPinPke", "false"),
        ("PortPinIfe", "false"),
        ("PortPinDirectionChangeable", "true"),
        ("PortPinModeChangeable", "true"),
        ("PortPinInvertControl", "false"),
        ("PortPinSiul2Instance", "SIUL2_0"),
        ("PortPinInitialMode", "PORT_GPIO_MODE"),
        ("OBEGroupSelect", "NO_OBE_GROUP"),
        ("MscrPdacSlot", "VIRTUAL_WRAPPER_PDAC0"),
        ("ImcrPdacSlot", "VIRTUAL_WRAPPER_PDAC0"),
    ]
    for field_name, expected in required_fields:
        actual = _setting_value(doc, tx_struct, field_name)
        assert actual == expected, (
            f"Lpuart0_Tx: expected {field_name}={expected}, got {actual}"
        )

    # IGFSettings and PortPinEcucPartitionRef arrays must be present
    array_names = {
        el.attrib.get("name")
        for el in tx_struct
        if el.tag.endswith("array")
    }
    assert "IGFSettings" in array_names, "Missing IGFSettings array"
    assert "PortPinEcucPartitionRef" in array_names, "Missing PortPinEcucPartitionRef array"


# ---------------------------------------------------------------------------
# Test 3: existing entries are untouched
# ---------------------------------------------------------------------------
def test_existing_lpuart3_and_fxio_pins_untouched(tmp_path):
    """The existing LPUART3 and FXIO <pin> entries are not modified."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    apply_port_set(doc, _standard_intent())

    pins = _pin_entries(doc)
    # First 4 pins must be the original ones
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


def test_existing_portpin_structs_untouched(tmp_path):
    """The existing Flexio0_Tx, Flexio1_Rx, Lpuart3_Tx, Lpuart3_Rx structs are untouched."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    apply_port_set(doc, _standard_intent())

    structs = _portpin_structs(doc)
    assert _setting_value(doc, structs[0], "Name") == "Flexio0_Tx"
    assert _setting_value(doc, structs[0], "PortPinId") == "1"

    assert _setting_value(doc, structs[1], "Name") == "Flexio1_Rx"
    assert _setting_value(doc, structs[1], "PortPinId") == "2"

    assert _setting_value(doc, structs[2], "Name") == "Lpuart3_Tx"
    assert _setting_value(doc, structs[2], "PortPinId") == "3"

    assert _setting_value(doc, structs[3], "Name") == "Lpuart3_Rx"
    assert _setting_value(doc, structs[3], "PortPinId") == "4"


# ---------------------------------------------------------------------------
# Test 4: legal-pin validation -- blocker on illegal pin
# ---------------------------------------------------------------------------
def test_blocker_on_illegal_tx_pin(tmp_path):
    """PTA15 is not a valid LPUART_0 TX pin; apply must return blocker port_illegal_pin."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    intent = _intent(
        peripheral="LPUART_0",
        pins={"tx": "PTA15", "rx": "PTA28"},
    )
    result = apply_port_set(doc, intent)

    assert result.blocked, "Expected blocker for illegal TX pin PTA15"
    codes = [d.code for d in result.diagnostics]
    assert any("port_illegal_pin" in code for code in codes), (
        f"Expected port_illegal_pin diagnostic, got: {codes}"
    )
    # Blocker details must include legal options
    diag = next(d for d in result.diagnostics if "port_illegal_pin" in d.code)
    assert "legal_pins" in diag.details or "options" in diag.details, (
        f"Blocker details must list legal options: {diag.details}"
    )


def test_blocker_on_illegal_rx_pin(tmp_path):
    """PTA15 is not a valid LPUART_0 RX pin either."""
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    intent = _intent(
        peripheral="LPUART_0",
        pins={"tx": "PTA27", "rx": "PTA15"},
    )
    result = apply_port_set(doc, intent)

    assert result.blocked, "Expected blocker for illegal RX pin PTA15"
    codes = [d.code for d in result.diagnostics]
    assert any("port_illegal_pin" in code for code in codes), (
        f"Expected port_illegal_pin diagnostic, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 5: idempotency -- second apply with same pins makes no duplicate
# ---------------------------------------------------------------------------
def test_idempotent_apply_no_duplicate_pins(tmp_path):
    """Second apply with same LPUART_0 TX/RX does not add duplicate entries."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc = MexDocument.load(mex)
    apply_port_set(doc, _standard_intent())
    doc.write(mex)

    doc2 = MexDocument.load(mex)
    result2 = apply_port_set(doc2, _standard_intent())
    doc2.write(mex)

    assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]

    doc3 = MexDocument.load(mex)
    pins = _pin_entries(doc3)
    assert len(pins) == 6, (
        f"Idempotency failed: {len(pins)} pin entries after two applies (expected 6)"
    )
    structs = _portpin_structs(doc3)
    assert len(structs) == 6, (
        f"Idempotency failed: {len(structs)} PortPin structs after two applies (expected 6)"
    )


# ---------------------------------------------------------------------------
# Test 6: byte-narrow diff
# ---------------------------------------------------------------------------
def test_edit_is_byte_narrow(tmp_path):
    """The diff adds only the new <pin> and PortPin struct lines; no broad churn."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_port_set(doc, _standard_intent())
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # Inserting 2 pin entries (TX: ~4 lines, RX: 1 line) and 2 PortPin structs
    # (~18 lines each). Allow generous upper bound; any full reserialization
    # would produce thousands of diff lines.
    assert len(changed) <= 60, (
        f"Unexpectedly broad diff: {len(changed)} lines:\n" + "".join(changed)
    )
    added = [line for line in changed if line.startswith("+")]
    assert any("lpuart0_tx" in line for line in added), "Missing lpuart0_tx in diff"
    assert any("lpuart0_rx" in line for line in added), "Missing lpuart0_rx in diff"
    assert any("Lpuart0_Tx" in line for line in added), "Missing Lpuart0_Tx in diff"
    assert any("Lpuart0_Rx" in line for line in added), "Missing Lpuart0_Rx in diff"
    assert any("PTA27" in line for line in added), "Missing PTA27 in diff"
    assert any("PTA28" in line for line in added), "Missing PTA28 in diff"

    # XML declaration preserved
    after_lines = mex.read_bytes().decode("utf-8").splitlines()
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>'


# ---------------------------------------------------------------------------
# Test 7: written file reloads as well-formed XML with new entries
# ---------------------------------------------------------------------------
def test_written_file_is_well_formed(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_port_set(doc, _standard_intent())
    doc.write(mex)

    reloaded = MexDocument.load(mex)

    pins = _pin_entries(reloaded)
    assert len(pins) == 6, f"Expected 6 pin entries after reload, got {len(pins)}"

    structs = _portpin_structs(reloaded)
    assert len(structs) == 6, f"Expected 6 PortPin structs after reload, got {len(structs)}"

    # Verify new entries are accessible in the reloaded doc
    tx_pin = next(
        (p for p in pins if p.attrib.get("signal") == "lpuart0_tx"), None
    )
    assert tx_pin is not None, "lpuart0_tx pin not found in reloaded doc"
    assert _setting_value(reloaded, structs[4], "Name") == "Lpuart0_Tx"
    assert _setting_value(reloaded, structs[5], "Name") == "Lpuart0_Rx"


# ---------------------------------------------------------------------------
# Test 8: plan() emits accurate PlannedChange for pin routing
# ---------------------------------------------------------------------------
def test_plan_describes_pin_routing(tmp_path):
    intent = _standard_intent()
    plan = PortProvider().plan(intent)

    assert len(plan.changes) >= 1
    port_changes = [c for c in plan.changes if c.owner == "port"]
    assert len(port_changes) >= 1, "No port-owned change in plan"

    tx_change = next(
        (c for c in port_changes
         if "PTA27" in c.description or "TX" in c.description or "lpuart0" in c.description.lower()),
        None,
    )
    assert tx_change is not None, (
        f"No PlannedChange describing TX pin routing; changes={plan.to_dict()}"
    )
    assert tx_change.module == "port"
    assert tx_change.owner == "port"


# ---------------------------------------------------------------------------
# Test 9: CLI integration -- port set --configure returns passed
# ---------------------------------------------------------------------------
def test_cli_port_set_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "port", "set",
            "--project", str(project),
            "--peripheral", "LPUART_0",
            "--tx", "PTA27",
            "--rx", "PTA28",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert "port" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"


# ---------------------------------------------------------------------------
# Test 10: CLI integration -- illegal pin returns exit code 1 + blocked status
# ---------------------------------------------------------------------------
def test_cli_port_set_illegal_pin_blocked(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "port", "set",
            "--project", str(project),
            "--peripheral", "LPUART_0",
            "--tx", "PTA15",
            "--rx", "PTA28",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 1, (
        f"Expected exit code 1 for illegal pin, got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked", payload
    codes = [d["code"] for d in payload["diagnostics"]]
    assert any("port_illegal_pin" in c for c in codes), (
        f"Expected port_illegal_pin in diagnostics, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 11: plan-only (no --configure) returns plan without modifying file
# ---------------------------------------------------------------------------
def test_cli_port_set_plan_only(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "port", "set",
            "--project", str(project),
            "--peripheral", "LPUART_0",
            "--tx", "PTA27",
            "--rx", "PTA28",
            "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["command"] == "plan", payload
    # File must be unmodified
    assert mex.read_bytes() == original, "File was modified by plan-only run"
