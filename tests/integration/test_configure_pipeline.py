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
import re
import subprocess
import sys
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.document import MexDocument, MexWriteError
import rtd_config.backends.s32_mex.transaction as transaction_module
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.modules.registry import ProviderRegistry
from rtd_config.plan import Plan
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


def _install_binding(
    monkeypatch, command_name, *, provider_type=None, normalizer=None, apply_fn=None
):
    registry = cli.get_provider_registry()
    stem = command_name.removeprefix("cmd_")
    if stem == "uart_add_flexio_channel":
        module, cli_action = "uart", "add-flexio-channel"
    else:
        module, cli_action = stem.removesuffix("_set"), "set"
    current = registry.lookup_shortcut(module, cli_action)
    if provider_type is not None:
        provider_type.name = module
    updated = replace(
        current,
        provider_type=provider_type or current.provider_type,
        normalizer=normalizer or current.normalizer,
        apply_fn=apply_fn or current.apply_fn,
    )
    bindings = tuple(
        updated if item.key == current.key else item
        for item in registry._bindings.values()
    )
    monkeypatch.setattr(cli, "_PROVIDER_REGISTRY", ProviderRegistry(bindings))
    return updated


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


def _assert_expected_success_cleanup(
    warnings, *, expected_preserved=(), expect_generated=True
):
    preserved = []
    for warning in warnings:
        assert set(warning) == {"code", "message", "details"}
        assert warning["code"] == "configure_cleanup_residual"
        assert warning["message"] == (
            "Verified rollback evidence was retained for audit cleanup."
        )
        assert set(warning["details"]) == {"preserved"}
        assert len(warning["details"]["preserved"]) == 1
        item = warning["details"]["preserved"][0]
        assert Path(item).name == item
        assert not Path(item).is_absolute()
        preserved.append(item)

    for item in expected_preserved:
        assert preserved.count(item) == 1
    generated = [item for item in preserved if item not in expected_preserved]
    if os.name == "nt":
        assert generated == []
        return
    if not expect_generated:
        assert generated == []
        return
    assert len(generated) == 1
    assert re.fullmatch(
        r"\.\.Uart_Example\.mex\.candidate\.[0-9a-f]{24}\.tmp"
        r"\.cleanup\.[0-9a-f]{24}\.tmp",
        generated[0],
    )


def test_configure_lpuart_interrupt_changes_mex_and_checks(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _run_configure(project)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["published"] is True
    _assert_expected_success_cleanup(payload["cleanup_warnings"])
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
    assert "Traceback" not in result.stderr


def test_cli_json_published_cleanup_warning_is_stable_and_path_safe(
    monkeypatch, tmp_path, capsys
):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()
    residual = project / ".absolute-residual-evidence.tmp"
    real_finalize = transaction_module.finalize_atomic_publish

    def return_residual(publication, *, platform):
        real_finalize(publication, platform=platform)
        return residual

    def apply_ok(doc, _intent, *, bundle):
        assert bundle is not None
        doc.root.attrib["uuid"] = "00000000-0000-0000-0000-000000000067"
        return ApplyResult(changed_modules=["uart"])

    monkeypatch.setattr(
        transaction_module, "finalize_atomic_publish", return_residual
    )
    rc = cli._configure_module(
        Namespace(project=project, backup=False),
        Intent.from_dict({"module": "uart", "action": "set", "payload": {}}),
        SimpleNamespace(to_dict=lambda: {"summary": "atomic cleanup warning"}),
        apply_ok,
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert rc == 0
    assert payload["status"] == "passed"
    assert payload["published"] is True
    _assert_expected_success_cleanup(
        payload["cleanup_warnings"],
        expected_preserved=(residual.name,),
        expect_generated=False,
    )
    assert captured.err == ""
    assert "Traceback" not in captured.out
    assert str(project) not in json.dumps(payload)
    assert mex.read_bytes() != original


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

    def fail_render(_document):
        raise MexWriteError("narrow .mex render unavailable: element count changed")

    def apply_ok(_doc, _intent, *, bundle):
        assert bundle.id == "nxp-s32-mex-s32k344-mapbga257-rtd-7.0.1"
        return ApplyResult(changed_modules=["uart"])

    monkeypatch.setattr(
        cli.MexDocument,
        "render",
        fail_render,
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
        def __init__(self, _bundle):
            pass

        def plan(self, _intent):
            prefs.write_text(
                "com.freescale.s32ds.cross.sdk.support.attachedSDKs="
                "PlatformSDK_S32K3_S32K344_M7_6.0.0_PATH|Debug_FLASH\n",
                encoding="utf-8",
            )
            return Plan()

    def unexpected_apply(*_args, **_kwargs):
        nonlocal apply_called
        apply_called = True

    _install_binding(
        monkeypatch, "cmd_uart_set", provider_type=Provider,
        apply_fn=unexpected_apply,
        normalizer=lambda _args, _bundle: Intent.from_dict(
            {"module": "uart", "action": "set", "payload": {}}
        ),
    )
    with pytest.raises(Exception) as caught:
        cli.cmd_uart_set(Namespace(project=project_root, configure=True, backup=False))
    assert getattr(caught.value, "code", None) == "project_metadata_source_changed"
    assert not apply_called


@pytest.mark.parametrize(
    "changed_relative",
    [
        ".project",
        ".cproject",
        ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
        ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
    ],
)
def test_configure_revalidates_metadata_changed_by_apply_before_publish(
    monkeypatch, tmp_path, changed_relative
):
    project_root = copy_uart_fixture(tmp_path)
    mex = project_root / "Uart_Example.mex"
    original = mex.read_bytes()
    metadata_source = project_root / changed_relative
    projects = []
    original_verified = cli.Project.verified

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    def mutate_aux(_doc, _intent, *, bundle):
        metadata_source.write_bytes(metadata_source.read_bytes() + b"\n")
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


@pytest.mark.parametrize(
    "changed_relative",
    [
        ".project",
        ".cproject",
        ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
        ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
    ],
)
def test_configure_revalidates_metadata_changed_by_static_check_before_publish(
    monkeypatch, tmp_path, changed_relative
):
    project_root = copy_uart_fixture(tmp_path)
    mex = project_root / "Uart_Example.mex"
    original = mex.read_bytes()
    metadata_source = project_root / changed_relative
    original_checks = cli.run_static_checks
    projects = []
    original_verified = cli.Project.verified

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    def mutate_after_checks(*args, **kwargs):
        result = original_checks(*args, **kwargs)
        metadata_source.write_bytes(metadata_source.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    monkeypatch.setattr(cli, "run_static_checks", mutate_after_checks)
    with pytest.raises(CliFailure) as caught:
        cli._configure_module(
            Namespace(project=project_root, backup=False),
            Intent.from_dict({"module": "uart", "action": "set", "payload": {}}),
            SimpleNamespace(to_dict=lambda: {}),
            lambda *_args, **_kwargs: ApplyResult(changed_modules=["uart"]),
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
    injected = {}
    original_verified = cli.Project.verified

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    class Provider:
        def __init__(self, bundle):
            injected["provider"] = bundle

        def plan(self, _intent):
            return Plan()

    def expected_apply(*_args, **_kwargs):
        return ApplyResult()

    def configure_same_project(
        _args, _intent, _plan, apply_fn, project, *, binding=None,
        runtime_config=None,
    ):
        assert project is projects[0]
        assert injected["provider"] is project.asset_bundle
        assert injected["normalizer"] is project.asset_bundle
        assert apply_fn is expected_apply
        assert binding is not None and binding.apply_fn is expected_apply
        assert runtime_config is not None
        assert runtime_config.project == project_root
        assert not project.verified_target.lease.closed
        return 0

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    stem = command_name.removeprefix("cmd_")
    module = "uart" if stem == "uart_add_flexio_channel" else stem.removesuffix("_set")
    action = "add_flexio_channel" if stem == "uart_add_flexio_channel" else "set"
    def normalize(_args, bundle):
        injected["normalizer"] = bundle
        return Intent.from_dict(
            {"module": module, "action": action, "payload": {}}
        )

    _install_binding(
        monkeypatch, command_name, provider_type=Provider,
        normalizer=normalize, apply_fn=expected_apply,
    )
    monkeypatch.setattr(cli, "_configure_verified_project", configure_same_project)

    assert getattr(cli, command_name)(
        Namespace(project=project_root, configure=True, backup=False)
    ) == 0
    assert len(projects) == 1
    assert projects[0].verified_target.lease.closed


def test_real_configure_pipeline_propagates_one_bundle_identity(
    monkeypatch, tmp_path, capsys
):
    project_root = copy_uart_fixture(tmp_path)
    seen = {}
    resolver_type = cli.AssetBundleResolver
    provider_type = cli.UartProvider
    normalize = cli.normalize_uart_intent
    apply_uart = cli.apply_uart_set
    static_checks = cli.run_static_checks

    class TrackingResolver:
        def __init__(self, root):
            self.inner = resolver_type(root)

        def resolve(self, metadata):
            value = self.inner.resolve(metadata)
            seen["resolved"] = value
            return value

    class TrackingProvider:
        def __init__(self, bundle):
            seen["provider_ctor"] = bundle
            self.inner = provider_type(bundle)

        def plan(self, intent):
            seen["provider_plan"] = seen["provider_ctor"]
            return self.inner.plan(intent)

    def tracking_normalizer(args, bundle):
        seen["normalizer"] = bundle
        return normalize(args, bundle)

    def tracking_apply(doc, intent, *, bundle):
        seen["apply"] = bundle
        return apply_uart(doc, intent, bundle=bundle)

    def tracking_static(*args, bundle, **kwargs):
        seen["static"] = bundle
        return static_checks(*args, bundle=bundle, **kwargs)

    monkeypatch.setattr(cli, "AssetBundleResolver", TrackingResolver)
    _install_binding(
        monkeypatch, "cmd_uart_set", provider_type=TrackingProvider,
        normalizer=tracking_normalizer, apply_fn=tracking_apply,
    )
    monkeypatch.setattr(cli, "run_static_checks", tracking_static)

    args = cli.build_parser().parse_args([
        "uart", "set", "--project", str(project_root), "--configure",
        "--hw", "LPUART_3", "--mode", "interrupt", "--baud", "115200",
        "--json",
    ])
    assert cli.cmd_uart_set(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
    resolved = seen["resolved"]
    assert all(seen[name] is resolved for name in (
        "normalizer", "provider_ctor", "provider_plan", "apply", "static",
    ))


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
        def __init__(self, _bundle):
            pass

        def plan(self, _intent):
            return Plan()

    def unexpected_apply(*_args, **_kwargs):
        pytest.fail("apply ran after the verified .mex target was swapped")

    monkeypatch.setattr(cli.Project, "verified", verified_then_swap)
    stem = command_name.removeprefix("cmd_")
    module = "uart" if stem == "uart_add_flexio_channel" else stem.removesuffix("_set")
    action = "add_flexio_channel" if stem == "uart_add_flexio_channel" else "set"
    _install_binding(
        monkeypatch, command_name, provider_type=Provider,
        normalizer=lambda _args, _bundle: Intent.from_dict(
            {"module": module, "action": action, "payload": {}}
        ),
        apply_fn=unexpected_apply,
    )

    with pytest.raises(CliFailure) as caught:
        getattr(cli, command_name)(
            Namespace(project=project_root, configure=True, backup=False)
        )

    assert caught.value.code == "project_target_changed"
    assert len(projects) == 1
    assert projects[0].verified_target.lease.closed
