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
# File:        test_basenxp_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Unit/integration tests for the BaseNXP OsIf system-timer edit
#              (RTD-MEX-BASENXP-001): enable timer and insert counter struct.
# =================================================================================

"""BaseNXP OsIf system-timer enable (RTD-MEX-BASENXP-001).

The Uart_Example_S32K344 fixture has:
  OsIfUseSystemTimer="false" and an empty <array name="OsIfCounterConfig"/>

The case enables the system timer, inserts exactly one counter struct with
OsIfSystemTimerClockFreq=48000000 (no ClockRef in baremetal/no-Mcu-ref
scenario), and verifies byte-narrowness and idempotency.
"""
import difflib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_basenxp_set
from rtd_config.intent import Intent
from tests.fixtures import copy_uart_fixture


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "basenxp", "action": "set", "payload": payload})


def _osif_cfg(doc: MexDocument) -> ET.Element | None:
    return doc.find_config_set("BaseNXP")


def _use_system_timer_value(doc: MexDocument) -> str | None:
    """Return the OsIfUseSystemTimer setting value from the loaded document."""
    cfg = _osif_cfg(doc)
    if cfg is None:
        return None
    setting = doc.find_child_setting(cfg, "OsIfUseSystemTimer")
    return setting.attrib.get("value") if setting is not None else None


def _counter_array(doc: MexDocument) -> ET.Element | None:
    cfg = _osif_cfg(doc)
    if cfg is None:
        return None
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "OsIfCounterConfig":
            return el
    return None


def _counter_structs(doc: MexDocument) -> list[ET.Element]:
    arr = _counter_array(doc)
    if arr is None:
        return []
    return [c for c in arr if c.tag.endswith("struct")]


def _child_setting_value(doc: MexDocument, el: ET.Element, name: str) -> str | None:
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
# Test 1: apply sets OsIfUseSystemTimer to true
# ---------------------------------------------------------------------------
def test_apply_sets_use_system_timer_true(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_basenxp_set(doc, _intent(enable_system_timer=True))

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "basenxp" in result.changed_modules
    assert _use_system_timer_value(doc) == "true"


# ---------------------------------------------------------------------------
# Test 2: apply inserts exactly one well-formed counter struct
# ---------------------------------------------------------------------------
def test_apply_inserts_exactly_one_counter(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_basenxp_set(doc, _intent(enable_system_timer=True))

    structs = _counter_structs(doc)
    assert len(structs) == 1, f"Expected 1 counter struct, got {len(structs)}"
    counter = structs[0]
    assert counter.attrib.get("name") == "0"


# ---------------------------------------------------------------------------
# Test 3: counter has OsIfSystemTimerClockFreq=48000000
# ---------------------------------------------------------------------------
def test_counter_has_correct_clock_freq(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_basenxp_set(doc, _intent(enable_system_timer=True))

    counter = _counter_structs(doc)[0]
    freq = _child_setting_value(doc, counter, "OsIfSystemTimerClockFreq")
    assert freq == "48000000", f"Expected 48000000, got {freq}"


# ---------------------------------------------------------------------------
# Test 4: counter has Name=OsIfCounterConfig_0 and empty Ref arrays
# ---------------------------------------------------------------------------
def test_counter_has_required_children(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_basenxp_set(doc, _intent(enable_system_timer=True))

    counter = _counter_structs(doc)[0]
    name_val = _child_setting_value(doc, counter, "Name")
    assert name_val == "OsIfCounterConfig_0", f"Got: {name_val}"

    # Empty reference arrays must be present (self-closed)
    arr_names = {el.attrib.get("name") for el in counter if el.tag.endswith("array")}
    assert "OsIfCounterEcucPartitionRef" in arr_names
    assert "OsIfSystemTimerClockRef" in arr_names
    assert "OsIfOsCounterRef" in arr_names


# ---------------------------------------------------------------------------
# Test 5: written file re-loads as well-formed XML
# ---------------------------------------------------------------------------
def test_written_file_is_well_formed(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    # Must reload without exception
    reloaded = MexDocument.load(mex)
    assert _use_system_timer_value(reloaded) == "true"


# ---------------------------------------------------------------------------
# Test 6: edit is byte-narrow (only OsIf flag line + OsIfCounterConfig region change)
# ---------------------------------------------------------------------------
def test_edit_is_byte_narrow(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # Two changed regions:
    # 1. OsIfUseSystemTimer line (1 removal + 1 addition = 2 diff lines)
    # 2. OsIfCounterConfig region (1 removal of self-closed + N addition lines)
    # Total diff lines must be << a full-file reserialization (which churns ~3000 lines).
    # We allow up to 30 diff lines to cover the expanded array block.
    assert len(changed) <= 30, f"unexpectedly broad diff: {len(changed)} lines:\n" + "".join(changed)

    # The OsIfUseSystemTimer flip must appear
    added = [line for line in changed if line.startswith("+")]
    assert any('OsIfUseSystemTimer' in line and 'value="true"' in line for line in added), \
        "Missing OsIfUseSystemTimer=true in diff"

    # The counter struct's ClockFreq must appear
    assert any('OsIfSystemTimerClockFreq' in line for line in added), \
        "Missing OsIfSystemTimerClockFreq in diff"

    # XML declaration and unrelated lines preserved
    after_lines = mex.read_bytes().decode("utf-8").splitlines()
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>'


# ---------------------------------------------------------------------------
# Test 7: idempotency -- running twice does not add a second counter
# ---------------------------------------------------------------------------
def test_idempotent_apply_does_not_add_second_counter(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc = MexDocument.load(mex)
    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    # Second apply on the already-modified file
    doc2 = MexDocument.load(mex)
    result2 = apply_basenxp_set(doc2, _intent(enable_system_timer=True))
    doc2.write(mex)

    assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
    doc3 = MexDocument.load(mex)
    structs = _counter_structs(doc3)
    assert len(structs) == 1, f"Idempotency failed: {len(structs)} counter structs after two applies"


# ---------------------------------------------------------------------------
# Test 8: CLI integration -- basenxp set --enable-system-timer --configure returns passed
# ---------------------------------------------------------------------------
def test_cli_basenxp_set_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "basenxp", "set",
            "--project", str(project),
            "--enable-system-timer",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert payload["status"] == "passed", payload
    assert "basenxp" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
