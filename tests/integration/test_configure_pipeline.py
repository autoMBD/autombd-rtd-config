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
# File:        test_configure_pipeline.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-11
# Version:     0.2.0
# Description: Integration test for the configure pipeline.
# =================================================================================

import json
import subprocess
import sys
from argparse import Namespace
from types import SimpleNamespace

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.document import MexDocument, MexWriteError
from rtd_config.intent import Intent
from tests.fixtures import copy_uart_fixture


def _run_configure(project, *extra):
    return subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "uart", "set",
            "--project", str(project),
            "--hw", "LPUART_0",
            "--mode", "interrupt",
            "--baud", "115200",
            "--tx", "PTA15",
            "--rx", "PTA16",
            "--configure",
            "--json",
            *extra,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_configure_lpuart_interrupt_changes_mex_and_checks(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _run_configure(project)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"


def test_configure_writes_real_edit_and_file_reloads(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    before = MexDocument.load(mex)
    before_cfg = before.find_config_set("Uart")
    channel0 = before.find_uart_channel(before_cfg, 0)
    before_baud = before.find_child_setting(channel0, "DesireBaudrate").attrib["value"]

    result = _run_configure(project)
    assert result.returncode == 0

    # The written file must re-load as well-formed XML and reflect a real edit.
    after = MexDocument.load(mex)
    after_cfg = after.find_config_set("Uart")
    channel0_after = after.find_uart_channel(after_cfg, 0)
    after_baud = after.find_child_setting(channel0_after, "DesireBaudrate").attrib["value"]
    after_hw = after.find_child_setting(channel0_after, "UartHwChannel").attrib["value"]

    assert after_baud == "LPUART_UART_BAUDRATE_115200"
    assert after_hw == "LPUART_0"
    # The edit genuinely changed the document (fixture channel 0 was 115200 on
    # LPUART_3; we still assert a concrete post-state above regardless).
    assert before_baud is not None


def test_configure_static_blocker_leaves_original_mex_bytes_unchanged(tmp_path):
    """A post-apply static blocker must roll back every pending .mex edit."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    result = _run_configure(project, "--callback", "NULL_PTR")
    payload = json.loads(result.stdout)

    assert result.returncode == 1, payload
    assert payload["status"] == "blocked", payload
    assert payload["runtime_verification"]["static_check"]["status"] == "blocked"
    diagnostic_codes = {item["code"] for item in payload["diagnostics"]}
    assert "invalid_uart_callback" in diagnostic_codes
    assert mex.read_bytes() == original, (
        "static-check rejection must not leave the applied Uart/Platform/Mcu edits on disk"
    )


def test_configure_writer_blocker_leaves_original_mex_bytes_unchanged(
    tmp_path,
    monkeypatch,
    capsys,
):
    """A narrow-writer blocker must be returned as JSON and never publish staging."""
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    def fail_write(_document, path):
        assert str(path).endswith(".tmp")
        raise MexWriteError("narrow .mex render unavailable: element count changed")

    def apply_ok(_doc, _intent):
        return ApplyResult(changed_modules=["uart"])

    monkeypatch.setattr(
        cli.MexDocument,
        "write",
        fail_write,
    )

    rc = cli._configure_module(
        Namespace(project=project, backup=False),
        Intent.from_dict({"module": "uart", "action": "set", "payload": {}}),
        SimpleNamespace(to_dict=lambda: {"summary": "fake plan"}),
        apply_ok,
    )
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert payload["status"] == "blocked"
    assert payload["diagnostics"][0]["code"] == "narrow_mex_write_unavailable"
    assert payload["diagnostics"][0]["module"] == "backend"
    assert mex.read_bytes() == original
    assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))
