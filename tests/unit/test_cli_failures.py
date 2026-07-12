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
# File:        test_cli_failures.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-12
# Version:     0.1.0
# Description: Public CLI failure-boundary and stable JSON diagnostic tests.
# =================================================================================

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rtd_config import cli
from rtd_config.errors import CliFailure


def run_cli(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "rtd_config", *(str(arg) for arg in args)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def assert_json_failure(
    result: subprocess.CompletedProcess[str], code: str, exit_code: int = 1
) -> dict:
    payload = json.loads(result.stdout)
    assert payload["status"] in {"failed", "blocked"}
    assert payload["diagnostics"][0]["code"] == code
    assert result.returncode == exit_code
    assert "Traceback" not in result.stderr
    return payload


def test_cli_failure_public_fields_are_immutable():
    failure = CliFailure("stable_code", "message", details={"key": "value"})
    with pytest.raises(AttributeError):
        failure.code = "changed"
    with pytest.raises(TypeError):
        failure.details["key"] = "changed"


def test_cli_failure_allows_python_to_attach_traceback():
    with pytest.raises(CliFailure) as caught:
        raise CliFailure("stable_code", "message")
    assert caught.value.__traceback__ is not None


@pytest.mark.parametrize(
    ("case", "code"),
    [
        ("missing_project", "project_not_found"),
        ("zero_mex", "project_mex_not_found"),
        ("two_mex", "project_mex_ambiguous"),
        ("malformed_xml", "project_xml_invalid"),
        ("missing_spec", "spec_not_found"),
        ("corrupt_spec", "spec_invalid"),
    ],
)
def test_expected_failures_have_stable_json_contract(tmp_path, case, code):
    project = tmp_path / "project"
    project.mkdir()
    argv: list[object] = ["inspect", "--project", project, "--json"]

    if case == "missing_project":
        argv[2] = tmp_path / "absent"
    elif case == "two_mex":
        (project / "a.mex").write_text("<mex/>", encoding="utf-8")
        (project / "b.mex").write_text("<mex/>", encoding="utf-8")
    elif case == "malformed_xml":
        (project / "bad.mex").write_text("<mex>", encoding="utf-8")
    elif case in {"missing_spec", "corrupt_spec"}:
        spec = tmp_path / "intent.json"
        if case == "corrupt_spec":
            spec.write_text("{", encoding="utf-8")
        argv = ["platform", "set", "--project", project, "--spec", spec, "--json"]

    payload = assert_json_failure(run_cli(*argv), code)
    assert payload["command"] in {"inspect", "platform"}
    assert set(payload["diagnostics"][0]) == {
        "severity", "code", "module", "message", "details"
    }


@pytest.mark.parametrize(
    "argv",
    [
        ("--json", "inspect"),
        ("inspect", "--json"),
    ],
)
def test_json_flag_is_honored_before_or_after_subcommand(argv):
    assert_json_failure(run_cli(*argv), "invalid_arguments", exit_code=2)


def test_default_mode_reports_expected_failure_without_traceback(tmp_path):
    result = run_cli("inspect", "--project", tmp_path / "absent")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "project_not_found" in result.stderr
    assert "Traceback" not in result.stderr


def test_permission_failure_uses_public_boundary(monkeypatch, capsys, tmp_path):
    def deny(_project: Path) -> Path:
        raise PermissionError("access denied")

    monkeypatch.setattr(cli, "find_single_mex", deny)
    exit_code = cli.main(["inspect", "--project", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "permission_denied"
    assert "Traceback" not in captured.err


def test_missing_and_corrupt_assets_are_mapped(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(cli, "DEFAULT_ASSET_ROOT", tmp_path)
    exit_code = cli.main(["pin-options", "--peripheral", "LPUART_0", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "asset_not_found"

    asset = tmp_path / "nxp" / "s32k3" / "port" / "pins.json"
    asset.parent.mkdir(parents=True)
    asset.write_text("{", encoding="utf-8")
    exit_code = cli.main(["pin-options", "--peripheral", "LPUART_0", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "asset_invalid"


def test_unknown_internal_error_is_hidden_by_default(monkeypatch, capsys, tmp_path):
    def explode(_args) -> int:
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(cli, "cmd_inspect", explode)
    exit_code = cli.main(["inspect", "--project", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "internal_error"
    assert "private implementation detail" not in captured.out
    assert "Traceback" not in captured.err


def test_debug_traceback_stays_on_stderr(monkeypatch, capsys, tmp_path):
    def explode(_args) -> int:
        raise RuntimeError("debug-only detail")

    monkeypatch.setattr(cli, "cmd_inspect", explode)
    exit_code = cli.main(
        ["inspect", "--project", str(tmp_path), "--debug", "--json"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "internal_error"
    assert "Traceback" in captured.err
    assert "debug-only detail" in captured.err
    assert "Traceback" not in captured.out


def test_keyboard_interrupt_is_not_swallowed(monkeypatch, tmp_path):
    def interrupt(_args) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "cmd_inspect", interrupt)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["inspect", "--project", str(tmp_path), "--json"])
