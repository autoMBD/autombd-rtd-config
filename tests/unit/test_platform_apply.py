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
# File:        test_platform_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Unit/integration tests for the Platform interrupt edit (RTD-MEX-PLATFORM-001).
# =================================================================================

"""Platform interrupt edit (RTD-MEX-PLATFORM-001).

The Uart_Example_S32K344 fixture ships an enabled LPUART3 interrupt
(IsrName=LPUART3_IRQn, IsrEnabled=true, IsrPriority=0,
IsrHandler=LPUART_UART_IP_3_IRQHandler). The case sets its priority to 2 and
confirms it stays enabled with its ISR registered, without disturbing the other
interrupt (FLEXIO_IRQn). The edit is a narrow attribute change on an existing
element -- no element creation.
"""
import difflib
import json
import subprocess
import sys
from pathlib import Path

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_platform_set
from rtd_config.intent import Intent
from rtd_config.modules.platform import PlatformProvider
from tests.fixtures import copy_uart_fixture


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "platform", "action": "set", "payload": payload})


def _asset_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd" / "assets" / "nxp" / "s32k3" / "platform" / "interrupts.json"
    )


def _isr_entry(doc: MexDocument, isr_name: str):
    platform_cfg = doc.find_config_set("Platform")
    for array in platform_cfg.iter():
        if array.tag.endswith("array") and array.attrib.get("name") == "PlatformIsrConfig":
            for entry in array:
                if not entry.tag.endswith("struct"):
                    continue
                name = doc.find_child_setting(entry, "IsrName")
                if name is not None and name.attrib.get("value") == isr_name:
                    return entry
    return None


def _setting_value(doc: MexDocument, entry, name: str) -> str | None:
    setting = doc.find_child_setting(entry, name)
    return setting.attrib.get("value") if setting is not None else None


def test_platform_json_asset_has_forward_surface_coverage():
    asset = json.loads(_asset_path().read_text(encoding="utf-8"))

    assert "Platform.xdm" in asset["source"]
    coverage = asset["_coverage"]

    isr_surface = coverage["configurable_today"]["IntCtrlConfig/PlatformIsrConfig"]
    for item in ("IsrName", "IsrEnabled", "IsrPriority", "IsrHandler"):
        assert item in isr_surface

    assert "PlatformNvicEcucPartitionRef" in coverage["not_yet_exposed"]["partitioning"]
    assert "SystemIsrConfig" in coverage["not_yet_exposed"]["system_interrupts"]
    assert coverage["references"] == [
        "Platform.xdm:IntCtrlConfig/PlatformIsrConfig",
        "issue #53 Platform KPI route correction",
    ]


def test_set_priority_by_peripheral(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    result = apply_platform_set(doc, _intent(peripheral="LPUART_3", priority=2))

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "platform" in result.changed_modules
    entry = _isr_entry(doc, "LPUART3_IRQn")
    assert _setting_value(doc, entry, "IsrPriority") == "2"
    assert _setting_value(doc, entry, "IsrEnabled") == "true"
    # The ISR handler registration is preserved (already correct in the fixture).
    assert _setting_value(doc, entry, "IsrHandler") == "LPUART_UART_IP_3_IRQHandler"


def test_set_priority_by_exact_isr_name(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_platform_set(doc, _intent(isr_name="LPUART3_IRQn", priority=5))

    assert not result.blocked
    assert _setting_value(doc, _isr_entry(doc, "LPUART3_IRQn"), "IsrPriority") == "5"


def test_other_interrupt_untouched(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_platform_set(doc, _intent(peripheral="LPUART_3", priority=2))

    # The FLEXIO interrupt entry must be left exactly as the fixture had it.
    flexio = _isr_entry(doc, "FLEXIO_IRQn")
    assert _setting_value(doc, flexio, "IsrPriority") == "0"
    assert _setting_value(doc, flexio, "IsrEnabled") == "true"


def test_edit_is_byte_faithful(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_platform_set(doc, _intent(peripheral="LPUART_3", priority=2))
    doc.write(mex)

    after = mex.read_bytes().decode("utf-8").splitlines(keepends=True)
    before = original.decode("utf-8").splitlines(keepends=True)
    changed = [
        line for line in difflib.unified_diff(before, after, n=0, lineterm="")
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    # A pure priority flip on one existing element: a handful of lines at most.
    assert len(changed) <= 6, f"unexpectedly broad diff: {len(changed)} lines"
    assert any('value="2"' in line for line in changed if line.startswith("+"))
    MexDocument.load(mex)  # still well-formed


def test_unknown_interrupt_blocks(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    # LPUART_9 -> LPUART9_IRQn, which the fixture does not configure.
    result = apply_platform_set(doc, _intent(peripheral="LPUART_9", priority=2))

    assert result.blocked
    codes = [d.code for d in result.diagnostics]
    assert "platform_isr_not_found" in codes
    # The diagnostic lists what is actually available, never invents an entry.
    detail = next(d for d in result.diagnostics if d.code == "platform_isr_not_found")
    assert "LPUART3_IRQn" in detail.details["available"]


def test_negative_priority_rejected(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_platform_set(doc, _intent(peripheral="LPUART_3", priority=-1))

    assert result.blocked
    assert "platform_priority_out_of_range" in [d.code for d in result.diagnostics]


def test_plan_for_spec_payload_names_target_irq_and_priority():
    plan = PlatformProvider().plan(_intent(peripheral="LPUART_3", priority=2))

    assert len(plan.changes) == 1
    change = plan.changes[0]
    assert change.owner == "platform"
    assert "LPUART3_IRQn" in change.description
    assert "priority=2" in change.description
    assert "Configure interrupt entry for " not in change.description


def test_cli_platform_set_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "platform", "set",
            "--project", str(project),
            "--peripheral", "LPUART_3",
            "--priority", "2",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, payload
    assert payload["status"] == "passed"
    assert "platform" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
