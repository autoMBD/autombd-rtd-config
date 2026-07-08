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
# File:        test_mcl_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Unit/integration tests for the Mcl FlexIO logic-channel insertion
#              (RTD-MEX-MCL-001): append FLEXIO_UART_CH0 to FlexioMclLogicChannels.
# =================================================================================

"""Mcl FlexIO logic-channel insertion (RTD-MEX-MCL-001).

The Uart_Example_S32K344 fixture has:
  MclEnableFlexioCommon=true (already true -- must NOT be flipped)
  FlexioCommon[0] (Name=FlexioCommon_0) with FlexioMclLogicChannels containing:
    struct 0: Name=UART_TX, FlexioMclChannelId=CHANNEL_0, FlexioMclPinId=PIN_0
    struct 1: Name=UART_RX, FlexioMclChannelId=CHANNEL_1, FlexioMclPinId=PIN_1

The case appends struct 2: Name=FLEXIO_UART_CH0, CHANNEL_2, PIN_2.
Next-available ids are computed from the first unused legal XDM enum values,
not hardcoded or invented outside the descriptor domain.
"""
import difflib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import (
    apply_mcl_set,
    _extract_channel_index,
    _extract_pin_index,
)
from rtd_config.intent import Intent
from rtd_config.modules.mcl import MclProvider
from tests.fixtures import copy_uart_fixture


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "mcl", "action": "set", "payload": payload})


def _asset_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "mcl" / "mcl.json"
    )


def _mcl_cfg(doc: MexDocument) -> ET.Element | None:
    return doc.find_config_set("Mcl")


def _flexio_channels_array(doc: MexDocument) -> ET.Element | None:
    """Return the FlexioMclLogicChannels array inside the first FlexioCommon struct."""
    mcl_cfg = _mcl_cfg(doc)
    if mcl_cfg is None:
        return None
    for el in mcl_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "FlexioMclLogicChannels":
            return el
    return None


def _channel_structs(doc: MexDocument) -> list[ET.Element]:
    arr = _flexio_channels_array(doc)
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


def _flexio_stub(entries: list[tuple[str, str, str]]) -> bytes:
    structs: list[str] = []
    for index, (name, channel_id, pin_id) in enumerate(entries):
        structs.append(
            f"""                <mex:struct name="{index}">
                  <mex:setting name="Name" value="{name}"/>
                  <mex:setting name="FlexioMclChannelId" value="{channel_id}"/>
                  <mex:setting name="FlexioMclPinId" value="{pin_id}"/>
                  <mex:setting name="FlexioMclAddPinEnable" value="false"/>
                  <mex:setting name="FlexioMclAddPinId" value="PIN_0"/>
                  <mex:setting name="FlexioMclAddChannelEnable" value="false"/>
                  <mex:setting name="FlexioMclAddChannelId" value="CHANNEL_0"/>
                </mex:struct>"""
        )
    joined = "\n".join(structs)
    return f"""<?xml version="1.0" encoding= "UTF-8" ?>
<mex:mex_configuration xmlns:mex="http://mcuxpresso.nxp.com/XSD/mex_configuration_18">
  <mex:instance name="Mcl" enabled="true">
    <mex:config_set name="Mcl">
      <mex:setting name="MclEnableFlexioCommon" value="true"/>
      <mex:array name="MclConfig">
        <mex:struct name="0">
          <mex:setting name="Name" value="MclConfig_0"/>
          <mex:array name="FlexioCommon">
            <mex:struct name="0">
              <mex:setting name="Name" value="FlexioCommon_0"/>
              <mex:array name="FlexioMclLogicChannels">
{joined}
              </mex:array>
            </mex:struct>
          </mex:array>
        </mex:struct>
      </mex:array>
    </mex:config_set>
  </mex:instance>
</mex:mex_configuration>
""".encode("utf-8")


# ---------------------------------------------------------------------------
# Forward surface coverage: mcl.json must account for the Mcl.xdm surface.
# ---------------------------------------------------------------------------
def test_mcl_json_asset_has_forward_surface_coverage():
    asset = json.loads(_asset_path().read_text(encoding="utf-8"))

    assert "Mcl.xdm" in asset["_source"]
    coverage = asset["_coverage"]
    configurable = coverage["configurable_today"]

    assert "MclGeneral/MclFlexioCommon" in configurable
    assert "MclEnableFlexioCommon" in configurable["MclGeneral/MclFlexioCommon"]

    logic_channels = configurable["MclConfig/FlexioCommon/FlexioMclLogicChannels"]
    for item in (
        "Name",
        "FlexioMclChannelId",
        "FlexioMclPinId",
        "FlexioMclAddPinEnable",
        "FlexioMclAddPinId",
        "FlexioMclAddChannelEnable",
        "FlexioMclAddChannelId",
    ):
        assert item in logic_channels

    assert "MclConfig/FlexioCommon/FlexioMclLogicChannels" in coverage["not_yet_exposed"]
    algorithm = asset["FlexioMclLogicChannel"]["next_id_algorithm"]
    assert "first unused legal" in algorithm
    assert "max_existing" not in algorithm


# ---------------------------------------------------------------------------
# Test 1: new struct is inserted with Name=FLEXIO_UART_CH0 and unique CHANNEL_2/PIN_2
# ---------------------------------------------------------------------------
def test_insert_adds_channel_with_correct_name_and_ids(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "mcl" in result.changed_modules

    structs = _channel_structs(doc)
    # Must have 3 channels now (2 existing + 1 new)
    assert len(structs) == 3, f"Expected 3 structs, got {len(structs)}"
    new_struct = structs[2]
    assert new_struct.attrib.get("name") == "2", f"Struct name should be '2', got {new_struct.attrib.get('name')}"
    assert _setting_value(doc, new_struct, "Name") == "FLEXIO_UART_CH0"
    assert _setting_value(doc, new_struct, "FlexioMclChannelId") == "CHANNEL_2"
    assert _setting_value(doc, new_struct, "FlexioMclPinId") == "PIN_2"


# ---------------------------------------------------------------------------
# Test 2: new struct has all required fields with correct defaults
# ---------------------------------------------------------------------------
def test_insert_has_all_required_fields(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))

    structs = _channel_structs(doc)
    new_struct = structs[2]

    # All six required fields per Mcl.xdm
    assert _setting_value(doc, new_struct, "Name") == "FLEXIO_UART_CH0"
    assert _setting_value(doc, new_struct, "FlexioMclChannelId") == "CHANNEL_2"
    assert _setting_value(doc, new_struct, "FlexioMclPinId") == "PIN_2"
    assert _setting_value(doc, new_struct, "FlexioMclAddPinEnable") == "false"
    assert _setting_value(doc, new_struct, "FlexioMclAddPinId") == "PIN_0"
    assert _setting_value(doc, new_struct, "FlexioMclAddChannelEnable") == "false"
    assert _setting_value(doc, new_struct, "FlexioMclAddChannelId") == "CHANNEL_0"


# ---------------------------------------------------------------------------
# Test 3: existing UART_TX and UART_RX entries are untouched
# ---------------------------------------------------------------------------
def test_existing_channels_untouched(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))

    structs = _channel_structs(doc)
    uart_tx = structs[0]
    uart_rx = structs[1]

    assert _setting_value(doc, uart_tx, "Name") == "UART_TX"
    assert _setting_value(doc, uart_tx, "FlexioMclChannelId") == "CHANNEL_0"
    assert _setting_value(doc, uart_tx, "FlexioMclPinId") == "PIN_0"

    assert _setting_value(doc, uart_rx, "Name") == "UART_RX"
    assert _setting_value(doc, uart_rx, "FlexioMclChannelId") == "CHANNEL_1"
    assert _setting_value(doc, uart_rx, "FlexioMclPinId") == "PIN_1"


# ---------------------------------------------------------------------------
# Test 4: written file re-loads as well-formed XML
# ---------------------------------------------------------------------------
def test_written_file_is_well_formed(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))
    doc.write(mex)

    reloaded = MexDocument.load(mex)
    structs = _channel_structs(reloaded)
    assert len(structs) == 3
    assert _setting_value(reloaded, structs[2], "Name") == "FLEXIO_UART_CH0"


# ---------------------------------------------------------------------------
# Test 5: byte-narrow diff -- only the new struct lines are added
# ---------------------------------------------------------------------------
def test_edit_is_byte_narrow(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # Inserting one new struct (9 lines: struct open + 7 settings + struct close) + no removals
    # Allow up to 20 diff lines to cover edge cases; a full reserialization would be thousands.
    assert len(changed) <= 20, (
        f"Unexpectedly broad diff: {len(changed)} lines:\n" + "".join(changed)
    )
    added = [line for line in changed if line.startswith("+")]
    assert any("FLEXIO_UART_CH0" in line for line in added), "Missing FLEXIO_UART_CH0 in diff"
    assert any("CHANNEL_2" in line for line in added), "Missing CHANNEL_2 in diff"
    assert any("PIN_2" in line for line in added), "Missing PIN_2 in diff"

    # XML declaration preserved
    after_lines = mex.read_bytes().decode("utf-8").splitlines()
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>'


# ---------------------------------------------------------------------------
# Test 6: idempotency -- second apply with same name adds no duplicate
# ---------------------------------------------------------------------------
def test_idempotent_apply_no_duplicate(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc = MexDocument.load(mex)
    apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))
    doc.write(mex)

    # Second apply on the modified file
    doc2 = MexDocument.load(mex)
    result2 = apply_mcl_set(doc2, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))
    doc2.write(mex)

    assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
    doc3 = MexDocument.load(mex)
    structs = _channel_structs(doc3)
    assert len(structs) == 3, (
        f"Idempotency failed: {len(structs)} structs after two applies (expected 3)"
    )


# ---------------------------------------------------------------------------
# Test 7: plan() emits accurate PlannedChange with owner=mcl
# ---------------------------------------------------------------------------
def test_plan_describes_channel_creation(tmp_path):
    intent = _intent(add_flexio_logic_channel="FLEXIO_UART_CH0")
    plan = MclProvider().plan(intent)

    assert len(plan.changes) >= 1
    mcl_changes = [c for c in plan.changes if c.owner == "mcl"]
    assert len(mcl_changes) >= 1, "No mcl-owned change in plan"

    ch_change = next(
        (c for c in mcl_changes if "FLEXIO_UART_CH0" in c.description or "FlexioMclLogicChannels" in c.path),
        None,
    )
    assert ch_change is not None, (
        f"No PlannedChange describing FLEXIO_UART_CH0 or FlexioMclLogicChannels; changes={plan.to_dict()}"
    )
    assert ch_change.module == "mcl"
    assert ch_change.owner == "mcl"
    assert "MclEnableFlexioCommon=true" in ch_change.description
    assert "no inspect required" in ch_change.description
    assert "first-unused legal CHANNEL_N/PIN_N" in ch_change.description


def test_plan_for_arbitrary_single_channel_declares_no_probe_no_uart_fast_path():
    """Mcl-only fast-path guidance must not be tied to an E2E channel literal."""
    channel_name = "FLEXIO_DIAG_TX0"
    plan = MclProvider().plan(_intent(add_flexio_logic_channel=channel_name))

    descriptions = "\n".join(c.description for c in plan.changes)
    assert channel_name in descriptions
    assert "Mcl-only" in descriptions
    assert "no inspect" in descriptions
    assert "no existing Mcl tree probe" in descriptions
    assert "no Uart configuration" in descriptions


# ---------------------------------------------------------------------------
# Test 8: blocker when no FlexioCommon container exists
# ---------------------------------------------------------------------------
def test_blocker_when_no_flexio_common(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    # Load doc; remove Mcl config_set from tree to simulate missing container
    doc = MexDocument.load(mex)
    # Patch: use a doc whose Mcl config_set has no FlexioCommon array
    # We do this by passing an intent that the function can try to act on,
    # then checking a patched doc scenario via a minimal stub document.
    import io
    stub_xml = b"""<?xml version="1.0" encoding= "UTF-8" ?>
<mex:mex_configuration xmlns:mex="http://mcuxpresso.nxp.com/XSD/mex_configuration_18">
  <mex:instance name="Mcl" enabled="true">
    <mex:config_set name="Mcl">
      <mex:array name="MclConfig">
        <mex:struct name="0">
          <mex:setting name="Name" value="MclConfig_0"/>
        </mex:struct>
      </mex:array>
    </mex:config_set>
  </mex:instance>
</mex:mex_configuration>
"""
    import tempfile, pathlib
    stub_path = tmp_path / "stub.mex"
    stub_path.write_bytes(stub_xml)
    stub_doc = MexDocument.load(stub_path)

    result = apply_mcl_set(stub_doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))

    assert result.blocked, "Expected blocker when FlexioCommon container is missing"
    codes = [d.code for d in result.diagnostics]
    assert any("flexio_common" in code for code in codes), (
        f"Expected a flexio_common diagnostic code, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 9: MclEnableFlexioCommon is NOT changed (must stay true as-is)
# ---------------------------------------------------------------------------
def test_enable_flexio_common_not_flipped(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original_raw = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))
    doc.write(mex)

    after_raw = mex.read_bytes()
    # Confirm MclEnableFlexioCommon=true is present both before and after
    assert b'MclEnableFlexioCommon' in original_raw
    assert b'MclEnableFlexioCommon' in after_raw
    # The value must remain "true" (not changed)
    mcl_cfg = doc.find_config_set("Mcl")
    assert mcl_cfg is not None
    setting = doc.find_child_setting(mcl_cfg, "MclEnableFlexioCommon")
    # We can verify via the written file too
    reloaded = MexDocument.load(mex)
    mcl_cfg2 = reloaded.find_config_set("Mcl")
    val = reloaded.find_child_setting(mcl_cfg2, "MclEnableFlexioCommon")
    assert val is None or val.attrib.get("value") == "true", (
        f"MclEnableFlexioCommon must not be modified; got {val.attrib if val is not None else 'not found'}"
    )


# ---------------------------------------------------------------------------
# Test 10: CLI integration -- mcl set --add-flexio-logic-channel --configure returns passed
# ---------------------------------------------------------------------------
def test_cli_mcl_set_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "mcl", "set",
            "--project", str(project),
            "--add-flexio-logic-channel", "FLEXIO_UART_CH0",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert "mcl" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"


# ---------------------------------------------------------------------------
# Test 11: "next-id is computed, not hardcoded" -- sequential-application proof
#
# A hardcoded-index implementation would always produce CHANNEL_2/PIN_2.
# This test perturbs the fixture by adding a first channel (lands at index 2),
# then applies a DISTINCT channel name and asserts the second lands at index 3.
# ---------------------------------------------------------------------------
def test_sequential_ids_prove_dynamic_computation(tmp_path):
    """Second add lands at struct name='3', CHANNEL_3, PIN_3 (not a constant)."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    # First add: FLEXIO_UART_CH0 -> struct "2", CHANNEL_2, PIN_2
    doc1 = MexDocument.load(mex)
    r1 = apply_mcl_set(doc1, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))
    assert not r1.blocked, [d.to_dict() for d in r1.diagnostics]
    doc1.write(mex)

    # Second add: FLEXIO_UART_CH1 (different name) -> struct "3", CHANNEL_3, PIN_3
    doc2 = MexDocument.load(mex)
    r2 = apply_mcl_set(doc2, _intent(add_flexio_logic_channel="FLEXIO_UART_CH1"))
    assert not r2.blocked, [d.to_dict() for d in r2.diagnostics]
    assert "mcl" in r2.changed_modules
    doc2.write(mex)

    # Verify final state
    doc3 = MexDocument.load(mex)
    structs = _channel_structs(doc3)
    assert len(structs) == 4, f"Expected 4 structs total, got {len(structs)}"

    # The third (index 2) channel is FLEXIO_UART_CH0 at struct "2"
    ch0 = structs[2]
    assert ch0.attrib.get("name") == "2"
    assert _setting_value(doc3, ch0, "Name") == "FLEXIO_UART_CH0"
    assert _setting_value(doc3, ch0, "FlexioMclChannelId") == "CHANNEL_2"
    assert _setting_value(doc3, ch0, "FlexioMclPinId") == "PIN_2"

    # The fourth (index 3) channel is FLEXIO_UART_CH1 at struct "3"
    ch1 = structs[3]
    assert ch1.attrib.get("name") == "3", (
        f"Second added channel must be struct name='3', got '{ch1.attrib.get('name')}' "
        "(a hardcoded implementation would fail here)"
    )
    assert _setting_value(doc3, ch1, "Name") == "FLEXIO_UART_CH1"
    assert _setting_value(doc3, ch1, "FlexioMclChannelId") == "CHANNEL_3", (
        "Second channel must be the next unused legal enum, not a constant"
    )
    assert _setting_value(doc3, ch1, "FlexioMclPinId") == "PIN_3", (
        "Second pin must be the next unused legal enum, not a constant"
    )

    # All four ChannelIds and PinIds must be unique across the array
    channel_ids = [_setting_value(doc3, s, "FlexioMclChannelId") for s in structs]
    pin_ids = [_setting_value(doc3, s, "FlexioMclPinId") for s in structs]
    assert len(set(channel_ids)) == 4, f"ChannelIds not unique: {channel_ids}"
    assert len(set(pin_ids)) == 4, f"PinIds not unique: {pin_ids}"


def test_gapped_flexio_ids_reuse_first_unused_legal_channel_and_pin(tmp_path):
    """A gapped project must fill CHANNEL_1/PIN_1, not emit max+1."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    raw = mex.read_bytes()
    raw = raw.replace(
        b'<setting name="FlexioMclChannelId" value="CHANNEL_1"/>',
        b'<setting name="FlexioMclChannelId" value="CHANNEL_2"/>',
        1,
    )
    raw = raw.replace(
        b'<setting name="FlexioMclPinId" value="PIN_1"/>',
        b'<setting name="FlexioMclPinId" value="PIN_2"/>',
        1,
    )
    mex.write_bytes(raw)

    doc = MexDocument.load(mex)
    result = apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_GAP_FILL"))

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    structs = _channel_structs(doc)
    new_struct = structs[-1]
    assert _setting_value(doc, new_struct, "FlexioMclChannelId") == "CHANNEL_1"
    assert _setting_value(doc, new_struct, "FlexioMclPinId") == "PIN_1"


def test_exhausted_flexio_channel_domain_blocks_without_inventing_enum(tmp_path):
    """The XDM channel enum is CHANNEL_0..CHANNEL_7; CHANNEL_8 is illegal."""
    entries = [
        (f"USED_{idx}", f"CHANNEL_{idx}", f"PIN_{idx}")
        for idx in range(8)
    ]
    mex = tmp_path / "exhausted.mex"
    mex.write_bytes(_flexio_stub(entries))

    doc = MexDocument.load(mex)
    result = apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_TOO_MANY"))

    assert result.blocked
    diagnostic = next(d for d in result.diagnostics if d.module == "mcl")
    assert diagnostic.code == "mcl_flexio_channel_id_exhausted"
    assert diagnostic.details["legal_values"] == [f"CHANNEL_{idx}" for idx in range(8)]
    assert "CHANNEL_8" not in diagnostic.message


# ---------------------------------------------------------------------------
# Test 12: _extract_channel_index returns None for malformed enum strings
# ---------------------------------------------------------------------------
def test_extract_channel_index_none_on_malformed():
    """Helper must return None -- not raise -- on strings that are not CHANNEL_<int>."""
    assert _extract_channel_index("CHANNEL_X") is None, "Non-integer suffix must yield None"
    assert _extract_channel_index("PIN_") is None, "Wrong prefix must yield None"
    assert _extract_channel_index("FOO") is None, "Unrecognised string must yield None"
    assert _extract_channel_index("CHANNEL_") is None, "Empty integer part must yield None"
    # Sanity: a valid value still works
    assert _extract_channel_index("CHANNEL_0") == 0
    assert _extract_channel_index("CHANNEL_7") == 7


# ---------------------------------------------------------------------------
# Test 13: _extract_pin_index returns None for malformed enum strings
# ---------------------------------------------------------------------------
def test_extract_pin_index_none_on_malformed():
    """Helper must return None -- not raise -- on strings that are not PIN_<int>."""
    assert _extract_pin_index("CHANNEL_X") is None, "Wrong prefix must yield None"
    assert _extract_pin_index("PIN_") is None, "Empty integer part must yield None"
    assert _extract_pin_index("FOO") is None, "Unrecognised string must yield None"
    assert _extract_pin_index("PIN_Z") is None, "Non-integer suffix must yield None"
    # Sanity: valid values still work
    assert _extract_pin_index("PIN_0") == 0
    assert _extract_pin_index("PIN_31") == 31


# ---------------------------------------------------------------------------
# Test 14: empty FlexioMclLogicChannels array -- first channel lands at index 0
#
# Exercises the else-branch in apply_mcl_set that handles an empty (self-closed)
# FlexioMclLogicChannels array. Builds a minimal stub doc rather than relying on
# the standard fixture so this branch is genuinely exercised.
# ---------------------------------------------------------------------------
_EMPTY_CHANNELS_STUB = b"""<?xml version="1.0" encoding= "UTF-8" ?>
<mex:mex_configuration xmlns:mex="http://mcuxpresso.nxp.com/XSD/mex_configuration_18">
  <mex:instance name="Mcl" enabled="true">
    <mex:config_set name="Mcl">
      <mex:setting name="MclEnableFlexioCommon" value="true"/>
      <mex:array name="MclConfig">
        <mex:struct name="0">
          <mex:setting name="Name" value="MclConfig_0"/>
          <mex:array name="FlexioCommon">
            <mex:struct name="0">
              <mex:setting name="Name" value="FlexioCommon_0"/>
              <mex:array name="FlexioMclLogicChannels"/>
            </mex:struct>
          </mex:array>
        </mex:struct>
      </mex:array>
    </mex:config_set>
  </mex:instance>
</mex:mex_configuration>
"""


def test_empty_channels_array_inserts_first_channel_at_index_zero(tmp_path):
    """apply_mcl_set on an empty FlexioMclLogicChannels populates CHANNEL_0/PIN_0."""
    mex = tmp_path / "stub.mex"
    mex.write_bytes(_EMPTY_CHANNELS_STUB)

    doc = MexDocument.load(mex)
    result = apply_mcl_set(doc, _intent(add_flexio_logic_channel="FLEXIO_UART_CH0"))

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "mcl" in result.changed_modules

    # Write and reload to confirm the file is well-formed after the empty-array splice
    doc.write(mex)
    reloaded = MexDocument.load(mex)

    structs = _channel_structs(reloaded)
    assert len(structs) == 1, f"Expected exactly 1 struct after first insert, got {len(structs)}"
    s = structs[0]
    assert s.attrib.get("name") == "0", (
        f"First channel struct name must be '0' (empty list -> index 0), got '{s.attrib.get('name')}'"
    )
    assert _setting_value(reloaded, s, "Name") == "FLEXIO_UART_CH0"
    assert _setting_value(reloaded, s, "FlexioMclChannelId") == "CHANNEL_0", (
        "Empty list -> max channel index is -1 -> new id is CHANNEL_0"
    )
    assert _setting_value(reloaded, s, "FlexioMclPinId") == "PIN_0", (
        "Empty list -> max pin index is -1 -> new id is PIN_0"
    )
