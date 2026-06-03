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


def _lpuart_polling_intent() -> Intent:
    return Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {"hw": "LPUART_0", "mode": "polling", "baud": 115200},
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
    result = apply_uart_set(doc, _lpuart_polling_intent())
    assert not result.blocked
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # A whole-file reserialization churns ~3000 lines; an owned edit must touch
    # only the few it changed. Guard far below the churn threshold.
    assert len(changed) <= 8, f"unexpectedly broad diff: {len(changed)} lines"

    added = [line for line in changed if line.startswith("+")]
    assert any('value="LPUART_0"' in line for line in added)
    assert any("LPUART_UART_IP_USING_POLLING" in line for line in added)

    # The written file re-loads as well-formed XML.
    MexDocument.load(mex)


def test_xml_declaration_and_unrelated_lines_are_byte_preserved(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original_lines = mex.read_bytes().decode("utf-8").splitlines()

    doc = MexDocument.load(mex)
    apply_uart_set(doc, _lpuart_polling_intent())
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
