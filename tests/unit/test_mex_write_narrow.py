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
# File:        test_mex_write_narrow.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Unit tests for byte-faithful narrow .mex writing.
# =================================================================================

"""The .mex writer must produce byte-faithful, narrow diffs.

ElementTree's tree.write() reserializes the whole document (XML declaration,
attribute order, self-closing spacing, empty-element form), which churns ~3000
lines on the 2408-line Uart fixture. The mandatory "narrow / localized edits"
rule requires that an owned edit touch only the lines it actually changes and
leave every unrelated byte intact. These tests pin that contract.
"""
import difflib

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_uart_set
from rtd_config.intent import Intent
from tests.fixtures import copy_uart_fixture


def _lpuart_intent() -> Intent:
    return Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {"hw": "LPUART_0", "mode": "interrupt", "baud": 115200},
    })


def _changed_lines(before: bytes, after: bytes) -> list[str]:
    """Return only the +/- payload lines of a unified diff (CRLF-preserving)."""
    b = before.decode("utf-8").splitlines(keepends=True)
    a = after.decode("utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(b, a, n=0, lineterm="")
    return [
        line for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


def test_write_without_edits_is_byte_identical(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    doc.write(mex)

    # No edits => the file must be reproduced byte-for-byte, including the
    # non-canonical XML declaration, CRLF line endings, and attribute order.
    assert mex.read_bytes() == original


def test_owned_edit_touches_only_changed_lines(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    result = apply_uart_set(doc, _lpuart_intent())
    assert not result.blocked
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # A whole-file reserialization churns ~3000 lines; an owned edit must touch
    # only the few it actually changed. Guard far below the churn threshold.
    # The full orchestration (RTD-MEX-UART-001) inserts a Platform ISR entry
    # (~8 lines) and an Mcu clock-ref entry (~5 lines) plus the channel field
    # change (1-2 lines) + UartClockRef update (2 lines) = ~20 lines total.
    # Still far below 3000; any value under 50 guards against a full reserialization.
    assert len(changed) <= 50, f"unexpectedly broad diff: {len(changed)} lines"

    added = [line for line in changed if line.startswith("+")]
    # interrupt-only M1: the owned change here is the hardware-channel value
    # (the fixture's method is already INTERRUPTS, so it is not re-emitted).
    assert any('value="LPUART_0"' in line for line in added)

    # The written file re-loads as well-formed XML.
    MexDocument.load(mex)


def test_xml_declaration_and_unrelated_lines_are_byte_preserved(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original_lines = mex.read_bytes().decode("utf-8").splitlines()

    doc = MexDocument.load(mex)
    apply_uart_set(doc, _lpuart_intent())
    doc.write(mex)
    after_lines = mex.read_bytes().decode("utf-8").splitlines()

    # The original, deliberately non-canonical XML declaration survives verbatim
    # (tree.write() would rewrite it to <?xml version='1.0' encoding='utf-8'?>).
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>'
    assert original_lines[0] == after_lines[0]

    # An unrelated generated-files entry is untouched (tree.write() would add a
    # space before the self-closing '/>').
    unrelated = next(l for l in original_lines if 'path="board/Siul2_Port_Ip_Cfg.c"' in l)
    assert unrelated in after_lines


def test_quick_selection_removal_is_a_narrow_byte_edit(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()
    before_count = original.decode("utf-8").count("quick_selection=")

    doc = MexDocument.load(mex)
    carrier = doc.find_first_with_attribute("quick_selection")
    assert carrier is not None
    doc.mark_modified(carrier)
    doc.write(mex)

    after = mex.read_bytes()
    # Exactly one quick_selection attribute was removed, nothing else changed.
    assert after.decode("utf-8").count("quick_selection=") == before_count - 1
    changed = _changed_lines(original, after)
    assert len(changed) == 2, f"expected one line edited, got {len(changed)}"
    for line in changed:
        if line.startswith("+"):
            assert "quick_selection" not in line

    MexDocument.load(mex)  # still well-formed


# ---------------------------------------------------------------------------
# Keystone writer test: replace_element_region splices a self-closed empty
# array with a populated open/close array block.
# ---------------------------------------------------------------------------
def test_replace_element_region_self_closed_to_populated_array(tmp_path):
    """MexDocument.replace_element_region must:

    (i)  produce a file that re-loads as well-formed XML;
    (ii) have the inserted children present in the reloaded tree;
    (iii) be byte-narrow — bytes outside the replaced element's region are unchanged.

    Target element: the self-closed <array name="OsIfCounterConfig"/> in the
    Uart_Example_S32K344 fixture (inside the BaseNXP config_set).
    Replacement: a populated open/close array with one child struct whose
    OsIfSystemTimerClockRef points to a stub Mcu path, and OsIfSystemTimerClockFreq
    is an empty array.
    """
    import xml.etree.ElementTree as ET

    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    assert doc._aligned, "Document must load aligned for the narrow-write path"

    # Locate the target: self-closed OsIfCounterConfig array
    target_array = None
    for el in doc.root.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "OsIfCounterConfig":
            target_array = el
            break
    assert target_array is not None, "OsIfCounterConfig array not found in fixture"

    # Verify it is self-closed (no children) before the splice
    child_structs = [c for c in target_array if c.tag.endswith("struct")]
    assert len(child_structs) == 0, "Precondition: OsIfCounterConfig must be empty in fixture"

    # Build replacement bytes: populated open/close array with one counter struct.
    # The indent matches the fixture's 27-space indent for this element.
    stub_ref = "/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/STUB_CLK"
    new_bytes = (
        b'<array name="OsIfCounterConfig">\r\n'
        b'                              <struct name="0">\r\n'
        b'                                 <setting name="Name" value="OsIfCounterConfig_0"/>\r\n'
        b'                                 <array name="OsIfCounterEcucPartitionRef"/>\r\n'
        b'                                 <array name="OsIfSystemTimerClockRef">\r\n'
        b'                                    <setting name="0" value="' + stub_ref.encode() + b'"/>\r\n'
        b'                                 </array>\r\n'
        b'                                 <array name="OsIfSystemTimerClockFreq"/>\r\n'
        b'                                 <array name="OsIfOsCounterRef"/>\r\n'
        b'                              </struct>\r\n'
        b'                           </array>'
    )

    doc.replace_element_region(target_array, new_bytes)
    doc.write(mex)

    written = mex.read_bytes()

    # (i) Re-loads as well-formed XML
    reloaded = MexDocument.load(mex)
    assert reloaded._aligned, "Reloaded document must still be aligned"

    # (ii) Inserted children are present in the reloaded tree
    counter_arr = None
    for el in reloaded.root.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "OsIfCounterConfig":
            counter_arr = el
            break
    assert counter_arr is not None, "OsIfCounterConfig not found after write"

    structs = [c for c in counter_arr if c.tag.endswith("struct")]
    assert len(structs) == 1, f"Expected 1 inserted struct, got {len(structs)}"
    assert structs[0].attrib.get("name") == "0"

    # OsIfSystemTimerClockRef must be a populated array (non-empty)
    raw_written = written.decode("utf-8")
    assert '<array name="OsIfSystemTimerClockRef">' in raw_written, (
        "OsIfSystemTimerClockRef must be a populated open/close array in written file"
    )
    assert stub_ref in raw_written, (
        f"Stub ref path '{stub_ref}' not found in written file"
    )
    # OsIfSystemTimerClockFreq must be a self-closed empty array
    assert '<array name="OsIfSystemTimerClockFreq"/>' in raw_written, (
        "OsIfSystemTimerClockFreq must be an empty self-closed array in written file"
    )

    # (iii) Byte-narrow: unrelated bytes are unchanged.
    # The XML declaration and an unrelated element must survive verbatim.
    orig_lines = original.decode("utf-8").splitlines()
    after_lines = raw_written.splitlines()
    assert after_lines[0] == orig_lines[0], (
        f"XML declaration changed: {after_lines[0]!r}"
    )
    # An unrelated line (e.g. the generated-files board entry) must be untouched.
    unrelated = next((l for l in orig_lines if 'path="board/Siul2_Port_Ip_Cfg.c"' in l), None)
    assert unrelated is not None, "Fixture must contain the board entry line used as unrelated probe"
    assert unrelated in after_lines, "Unrelated 'board/Siul2_Port_Ip_Cfg.c' line was altered"

    # Diff line count must be narrow (far fewer than a full reserialization)
    changed = _changed_lines(original, written)
    assert len(changed) <= 30, (
        f"replace_element_region produced a broad diff ({len(changed)} lines), "
        "expected narrow splice"
    )


# ---------------------------------------------------------------------------
# Fix 1 regression: tag-prefix matching bug
# The old code scanned for open-tag matches using a raw bytes prefix: for tag
# name "pin" the prefix was b"<pin", which also matches "<pin_features>".  The
# depth counter would never return to 0, _find_element_region_end would return
# None, and replace_element_region would fall back to full reserialization.
#
# The fix requires a token-boundary check: the byte after "<tagname" must be
# space (0x20), ">" (0x3E), or "/" (0x2F) -- i.e. a real XML token boundary.
# ---------------------------------------------------------------------------
def test_find_element_region_end_pin_with_pin_features(tmp_path):
    """_find_element_region_end must find the region end for a <pin> element that
    contains a <pin_features> child, WITHOUT being confused by the <pin_features>
    open tag (which shares the 'pin' prefix).

    Regression test for the tag-prefix matching bug: b'<pin' matches
    b'<pin_features>' when there is no token-boundary guard.

    Assertions:
      (i)  _find_element_region_end returns a non-None value.
      (ii) replace_element_region on the <pin> element succeeds (doc stays aligned).
      (iii) the written file reloads as well-formed XML.
      (iv)  the write is byte-narrow (no full reserialization).
    """
    # Build a minimal .mex-like XML that contains a <pin> with a <pin_features>
    # child.  This is the exact structure in the Uart_Example_S32K344 fixture's
    # <pins> section (lines 46-50) and the structure the Port apply path creates.
    xml_bytes = (
        b'<?xml version="1.0" encoding= "UTF-8" ?>\r\n'
        b'<root>\r\n'
        b'   <pins>\r\n'
        b'      <pin peripheral="LPUART0" signal="lpuart0_tx" pin_num="M2" pin_signal="PTA27">\r\n'
        b'         <pin_features>\r\n'
        b'            <pin_feature name="direction" value="OUTPUT"/>\r\n'
        b'         </pin_features>\r\n'
        b'      </pin>\r\n'
        b'      <pin peripheral="LPUART0" signal="lpuart0_rx" pin_num="N2" pin_signal="PTA28"/>\r\n'
        b'   </pins>\r\n'
        b'</root>\r\n'
    )
    mex = tmp_path / "test_pin.mex"
    mex.write_bytes(xml_bytes)

    doc = MexDocument.load(mex)
    assert doc._aligned, "Document should load as aligned"

    # Find the TX <pin> element (the one with <pin_features>)
    tx_pin_el = None
    for el in doc.root.iter():
        if el.tag.endswith("pin") and el.attrib.get("signal") == "lpuart0_tx":
            tx_pin_el = el
            break
    assert tx_pin_el is not None, "TX pin element not found in test XML"

    # Verify it has a child (pin_features) so we're testing the open-element path
    children = list(tx_pin_el)
    assert len(children) > 0, "TX pin must have pin_features child for this test to exercise the bug"

    # (i) _find_element_region_end must return a non-None value.
    elements = list(doc.root.iter())
    src_index = next((i for i, e in enumerate(elements) if e is tx_pin_el), None)
    assert src_index is not None
    src = doc._sources[src_index]
    span_end = doc._find_element_region_end(src, tx_pin_el)
    assert span_end is not None, (
        "_find_element_region_end returned None for a <pin> with <pin_features> child; "
        "this indicates the tag-prefix bug is present (b'<pin' matched b'<pin_features>')"
    )

    # (ii) replace_element_region must succeed and keep the doc aligned.
    # Replace the TX pin with an updated version (changed pin_num value).
    replacement = (
        b'<pin peripheral="LPUART0" signal="lpuart0_tx" pin_num="M2_UPDATED" pin_signal="PTA27">\r\n'
        b'         <pin_features>\r\n'
        b'            <pin_feature name="direction" value="OUTPUT"/>\r\n'
        b'         </pin_features>\r\n'
        b'      </pin>'
    )
    doc.replace_element_region(tx_pin_el, replacement)
    assert doc._aligned, (
        "doc._aligned is False after replace_element_region; "
        "the writer fell back to full reserialization because region-end was not found"
    )

    # (iii) Written file reloads as well-formed XML.
    doc.write(mex)
    reloaded = MexDocument.load(mex)
    assert reloaded._aligned

    # Check the updated pin_num is in the written file.
    written_text = mex.read_bytes().decode("utf-8")
    assert "M2_UPDATED" in written_text, "Updated pin_num not found in written file"

    # (iv) Byte-narrow: diff must be small.
    changed = _changed_lines(xml_bytes, mex.read_bytes())
    assert len(changed) <= 4, (
        f"replace_element_region on <pin>/<pin_features> produced a broad diff "
        f"({len(changed)} lines); full reserialization triggered"
    )
