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
import os
import subprocess
import sys
from argparse import Namespace
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.document import MexDocument, MexWriteError
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from tests.fixtures import copy_uart_fixture


CONFIGURE_ENTRY_POINTS = (
    ("cmd_uart_set", "normalize_uart_intent", "UartProvider", "apply_uart_set"),
    (
        "cmd_uart_add_flexio_channel",
        "normalize_uart_add_flexio_intent",
        "UartProvider",
        "apply_uart_add_flexio_channel",
    ),
    ("cmd_platform_set", "normalize_platform_intent", "PlatformProvider", "apply_platform_set"),
    ("cmd_basenxp_set", "normalize_basenxp_intent", "BaseNxpProvider", "apply_basenxp_set"),
    ("cmd_mcl_set", "normalize_mcl_intent", "MclProvider", "apply_mcl_set"),
    ("cmd_port_set", "normalize_port_intent", "PortProvider", "apply_port_set"),
    ("cmd_dio_set", "normalize_dio_intent", "DioProvider", "apply_dio_set"),
    ("cmd_mcu_set", "normalize_mcu_intent", "McuProvider", "apply_mcu_set"),
    ("cmd_adc_set", "normalize_adc_intent", "AdcProvider", "apply_adc_set"),
)


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


def test_configure_revalidates_plan_metadata_before_apply(monkeypatch, tmp_path):
    project_root = copy_uart_fixture(tmp_path)
    prefs = project_root / ".settings/com.freescale.s32ds.cross.sdk.support.prefs"
    apply_called = False

    class Provider:
        def plan(self, _intent):
            prefs.write_text(
                "com.freescale.s32ds.cross.sdk.support.attachedSDKs="
                "PlatformSDK_S32K3_S32K344_M7_6.0.0_PATH|Debug_FLASH\n",
                encoding="utf-8",
            )
            return SimpleNamespace(to_dict=lambda: {})

    def unexpected_apply(*_args):
        nonlocal apply_called
        apply_called = True

    monkeypatch.setattr(cli, "UartProvider", Provider)
    monkeypatch.setattr(cli, "apply_uart_set", unexpected_apply)
    monkeypatch.setattr(
        cli, "normalize_uart_intent",
        lambda _args: Intent.from_dict({"module": "uart", "action": "set", "payload": {}}),
    )
    with pytest.raises(Exception) as caught:
        cli.cmd_uart_set(Namespace(project=project_root, configure=True, backup=False))
    assert getattr(caught.value, "code", None) == "project_metadata_source_changed"
    assert not apply_called


def test_configure_revalidates_metadata_changed_by_apply_before_publish(
    monkeypatch, tmp_path
):
    project_root = copy_uart_fixture(tmp_path)
    mex = project_root / "Uart_Example.mex"
    original = mex.read_bytes()
    prefs = project_root / ".settings/com.freescale.s32ds.cross.sdk.support.prefs"
    projects = []
    original_verified = cli.Project.verified

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    def mutate_aux(_doc, _intent):
        prefs.write_text(prefs.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        return ApplyResult(changed_modules=["uart"])

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    with pytest.raises(CliFailure) as caught:
        cli._configure_module(
            Namespace(project=project_root, backup=False),
            Intent.from_dict({"module": "uart", "action": "set", "payload": {}}),
            SimpleNamespace(to_dict=lambda: {}), mutate_aux,
        )
    assert caught.value.code == "project_metadata_source_changed"
    assert mex.read_bytes() == original
    assert projects[0].verified_target.lease.closed


def test_configure_revalidates_metadata_changed_by_static_check_before_publish(
    monkeypatch, tmp_path
):
    project_root = copy_uart_fixture(tmp_path)
    mex = project_root / "Uart_Example.mex"
    original = mex.read_bytes()
    prefs = project_root / ".settings/com.freescale.s32ds.cross.sdk.support.prefs"
    original_checks = cli.run_static_checks
    projects = []
    original_verified = cli.Project.verified

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    def mutate_after_checks(*args, **kwargs):
        result = original_checks(*args, **kwargs)
        prefs.write_text(prefs.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        return result

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    monkeypatch.setattr(cli, "run_static_checks", mutate_after_checks)
    with pytest.raises(CliFailure) as caught:
        cli._configure_module(
            Namespace(project=project_root, backup=False),
            Intent.from_dict({"module": "uart", "action": "set", "payload": {}}),
            SimpleNamespace(to_dict=lambda: {}),
            lambda *_args: ApplyResult(changed_modules=["uart"]),
        )
    assert caught.value.code == "project_metadata_source_changed"
    assert mex.read_bytes() == original
    assert projects[0].verified_target.lease.closed


@pytest.mark.parametrize(
    "command_name,normalizer_name,provider_name,apply_name",
    CONFIGURE_ENTRY_POINTS,
    ids=[item[0].removeprefix("cmd_") for item in CONFIGURE_ENTRY_POINTS],
)
def test_every_configure_entry_point_plans_and_applies_one_verified_project(
    monkeypatch,
    tmp_path,
    command_name,
    normalizer_name,
    provider_name,
    apply_name,
):
    project_root = copy_uart_fixture(tmp_path)
    projects = []
    original_verified = cli.Project.verified

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    class Provider:
        def plan(self, _intent):
            return SimpleNamespace(to_dict=lambda: {})

    expected_apply = object()

    def configure_same_project(_args, _intent, _plan, apply_fn, project):
        assert project is projects[0]
        assert apply_fn is expected_apply
        assert not project.verified_target.lease.closed
        return 0

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    monkeypatch.setattr(cli, provider_name, Provider)
    monkeypatch.setattr(
        cli,
        normalizer_name,
        lambda _args: Intent.from_dict(
            {"module": "test", "action": "set", "payload": {}}
        ),
    )
    monkeypatch.setattr(cli, apply_name, expected_apply)
    monkeypatch.setattr(cli, "_configure_verified_project", configure_same_project)

    assert getattr(cli, command_name)(
        Namespace(project=project_root, configure=True, backup=False)
    ) == 0
    assert len(projects) == 1
    assert projects[0].verified_target.lease.closed


@pytest.mark.parametrize(
    "command_name,normalizer_name,provider_name,apply_name",
    CONFIGURE_ENTRY_POINTS,
    ids=[item[0].removeprefix("cmd_") for item in CONFIGURE_ENTRY_POINTS],
)
def test_every_configure_entry_point_rejects_target_swap_before_apply(
    monkeypatch,
    tmp_path,
    command_name,
    normalizer_name,
    provider_name,
    apply_name,
):
    project_root = copy_uart_fixture(tmp_path)
    mex = project_root / "Uart_Example.mex"
    projects = []
    original_verified = cli.Project.verified

    def verified_then_swap(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        _ = project.metadata
        project.close()
        replacement = mex.with_name("replacement.mex")
        replacement.write_bytes(mex.read_bytes() + b"\n")
        os.replace(replacement, mex)
        return project

    class Provider:
        def plan(self, _intent):
            return SimpleNamespace(to_dict=lambda: {})

    def unexpected_apply(*_args, **_kwargs):
        pytest.fail("apply ran after the verified .mex target was swapped")

    monkeypatch.setattr(cli.Project, "verified", verified_then_swap)
    monkeypatch.setattr(cli, provider_name, Provider)
    monkeypatch.setattr(
        cli,
        normalizer_name,
        lambda _args: Intent.from_dict(
            {"module": "test", "action": "set", "payload": {}}
        ),
    )
    monkeypatch.setattr(cli, apply_name, unexpected_apply)

    with pytest.raises(CliFailure) as caught:
        getattr(cli, command_name)(
            Namespace(project=project_root, configure=True, backup=False)
        )

    assert caught.value.code == "project_target_changed"
    assert len(projects) == 1
    assert projects[0].verified_target.lease.closed
