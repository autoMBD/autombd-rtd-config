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
# 件的许可，包括而不限于：使用、复制、修改、合并、发布、分许可和/或销售本软
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
# File:        test_generic_cli.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Integration contract tests for canonical generic CLI commands.
# =================================================================================

from __future__ import annotations

from copy import deepcopy
import json
import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.config import RuntimeConfig
from rtd_config.errors import CliFailure
from rtd_config.modules.registry import ProviderRegistry
from tests.fixtures import copy_uart_fixture


CASES = (
    ("uart", "set", {"hw": "LPUART_0", "mode": "interrupt", "baud": 115200}),
    (
        "uart", "add_flexio_channel",
        {
            "baud": 921600, "word_length": 8, "mode": "interrupt",
            "tx_name": "UART2_TX", "rx_name": "UART2_RX",
        },
    ),
    ("platform", "set", {"peripheral": "LPUART_3", "priority": 2}),
    ("basenxp", "set", {"enable_system_timer": True}),
    ("mcl", "set", {"add_flexio_logic_channel": "UART2_TX"}),
    (
        "port", "set",
        {"peripheral": "LPUART_0", "pins": {"tx": "PTA15", "rx": "PTA16"}},
    ),
    ("dio", "set", {"add_channel": "LED_CTRL", "pin": "PTA5", "direction": "output"}),
    (
        "mcu", "set",
        {"core_clk": 160, "aips_plat_clk": 80, "aips_slow_clk": 40},
    ),
    ("adc", "set", {}),
)

SHORTCUTS = (
    ("uart", "set"),
    ("uart", "add-flexio-channel"),
    ("platform", "set"),
    ("basenxp", "set"),
    ("mcl", "set"),
    ("port", "set"),
    ("dio", "set"),
    ("mcu", "set"),
    ("adc", "set"),
)


def _normalize_checked_cleanup_residual(payload):
    normalized = deepcopy(payload)
    warnings = normalized["cleanup_warnings"]
    if os.name == "nt":
        assert warnings == []
        return normalized
    if not normalized["published"] and not warnings:
        return normalized
    assert len(warnings) == 1
    warning = warnings[0]
    assert set(warning) == {"code", "message", "details"}
    assert warning["code"] == "configure_cleanup_residual"
    assert warning["message"] == (
        "Verified rollback evidence was retained for audit cleanup."
    )
    assert set(warning["details"]) == {"preserved"}
    assert len(warning["details"]["preserved"]) == 1
    residual = warning["details"]["preserved"][0]
    assert Path(residual).name == residual
    assert not Path(residual).is_absolute()
    assert re.fullmatch(
        r"\.\.Uart_Example\.mex\.candidate\.[0-9a-f]{24}\.tmp"
        r"\.cleanup\.[0-9a-f]{24}\.tmp",
        residual,
    )
    warning["details"]["preserved"] = ["<transaction-residual>"]
    return normalized


def _write_json(path: Path, payload) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _invoke(capsys, argv):
    rc = cli.main([*argv, "--json"])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "Traceback" not in captured.out
    return rc, json.loads(captured.out)


def _shortcut(module, action, project, spec):
    if (module, action) == ("uart", "add_flexio_channel"):
        return [
            "uart", "add-flexio-channel", "--project", str(project),
            "--baud", "921600", "--word-length", "8", "--mode", "interrupt",
            "--tx-name", "UART2_TX", "--rx-name", "UART2_RX",
        ]
    return [module, "set", "--project", str(project), "--spec", str(spec)]


@pytest.mark.parametrize(("module", "action", "parameters"), CASES)
def test_generic_plan_matches_every_registered_shortcut(
    tmp_path, capsys, module, action, parameters
):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json",
        {"module": module, "action": action, "payload": parameters},
    )
    spec = _write_json(tmp_path / "spec.json", parameters)

    generic_rc, generic = _invoke(
        capsys, ["plan", "--project", str(project), "--intent", str(intent)]
    )
    shortcut_rc, shortcut = _invoke(
        capsys, _shortcut(module, action, project, spec)
    )

    assert generic_rc == shortcut_rc == 0
    assert generic["normalized_intent"] == shortcut["normalized_intent"]
    assert generic["plan"] == shortcut["plan"]


@pytest.mark.parametrize(
    "intent",
    [
        {},
        {"module": "uart", "action": "set"},
        {"module": "uart", "action": "set", "payload": None},
        {"module": "uart", "action": "set", "payload": {}, "extra": True},
        {"module": "unknown", "action": "set", "payload": {}},
        {"module": "uart", "action": "unknown", "payload": {}},
    ],
)
def test_generic_intent_envelope_is_strict_and_path_safe(tmp_path, capsys, intent):
    project = copy_uart_fixture(tmp_path)
    secret = tmp_path / "SECRET_INTENT_PATH.json"
    _write_json(secret, intent)

    rc, payload = _invoke(
        capsys, ["plan", "--project", str(project), "--intent", str(secret)]
    )

    assert rc != 0
    assert payload["diagnostics"][0]["code"] == "intent_invalid"
    assert str(secret) not in json.dumps(payload)


@pytest.mark.parametrize(
    "config",
    [
        {"backend": None},
        {"backend": "mex", "unknown": True},
        {"backend": "unknown"},
        {"validation_timeout_s": "slow"},
        {"asset_root": None},
    ],
)
def test_runtime_config_is_strict_and_path_safe(tmp_path, capsys, config):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "uart", "action": "set", "payload": {}}
    )
    secret = _write_json(tmp_path / "SECRET_CONFIG_PATH.json", config)

    rc, payload = _invoke(
        capsys,
        [
            "plan", "--project", str(project), "--intent", str(intent),
            "--config", str(secret),
        ],
    )

    assert rc == 2
    assert payload["diagnostics"][0]["code"] == "invalid_arguments"
    assert str(secret) not in json.dumps(payload)


def test_runtime_precedence_uses_explicit_flag_over_json_without_parser_defaults(
    tmp_path, capsys
):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    config = _write_json(
        tmp_path / "runtime.json",
        {"backend": "mex", "project": str(tmp_path / "missing-project")},
    )
    parsed = cli.build_parser().parse_args(
        ["plan", "--intent", str(intent), "--config", str(config)]
    )
    assert not hasattr(parsed, "project")
    assert not hasattr(parsed, "backend")

    rc, payload = _invoke(
        capsys,
        [
            "plan", "--intent", str(intent), "--config", str(config),
            "--project", str(project),
        ],
    )
    assert rc == 0
    assert payload["status"] == "passed"


@pytest.mark.parametrize(
    ("invalid_field", "invalid_value", "override"),
    [
        ("project", None, lambda project: ["--project", str(project)]),
        ("backend", None, lambda _project: ["--backend", "mex"]),
        (
            "validation_timeout_s", "not-an-integer",
            lambda _project: ["--validation-timeout-s", "60"],
        ),
        (
            "asset_root", None,
            lambda _project: ["--asset-root", str(cli.DEFAULT_ASSET_ROOT)],
        ),
    ],
)
def test_explicit_flags_override_invalid_lower_precedence_config_values(
    tmp_path, capsys, invalid_field, invalid_value, override
):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    values = {"project": str(project), invalid_field: invalid_value}
    config = _write_json(tmp_path / "runtime.json", values)

    rc, payload = _invoke(
        capsys,
        [
            "plan", "--intent", str(intent), "--config", str(config),
            *override(project),
        ],
    )

    assert rc == 0
    assert payload["status"] == "passed"


def test_every_optional_runtime_flag_is_suppressed_until_explicit():
    args = cli.build_parser().parse_args(["plan", "--intent", "intent.json"])

    assert not {
        field for field in cli._RUNTIME_FIELDS if hasattr(args, field)
    }


def test_runtime_config_resolves_all_json_paths_relative_to_config(tmp_path):
    config_path = _write_json(
        tmp_path / "runtime.json",
        {
            "project": "project", "backend": "mex", "s32ds_root": "s32ds",
            "sdk_path": "sdk", "workspace": "workspace", "temp_root": "temp",
            "log_root": "logs", "asset_root": "assets", "validation_timeout_s": 90,
        },
    )
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    args = cli.build_parser().parse_args(
        ["plan", "--intent", str(intent), "--config", str(config_path)]
    )

    config, _expected = cli._load_runtime_config(args)

    assert config.project == tmp_path / "project"
    assert config.s32ds_root == tmp_path / "s32ds"
    assert config.sdk_path == tmp_path / "sdk"
    assert config.workspace == tmp_path / "workspace"
    assert config.temp_root == tmp_path / "temp"
    assert config.log_root == tmp_path / "logs"
    assert config.asset_root == tmp_path / "assets"
    assert config.validation_timeout_s == 90


def test_expected_identity_is_asserted_against_observed_project(tmp_path, capsys):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )

    rc, payload = _invoke(
        capsys,
        [
            "plan", "--project", str(project), "--intent", str(intent),
            "--family", "not-the-observed-family",
        ],
    )

    assert rc == 1
    assert payload["diagnostics"][0]["code"] == "project_identity_mismatch"


@pytest.mark.parametrize(
    ("expected", "status"),
    [
        ("7_0_1", "passed"), ("7.01", "failed"), ("70.1", "failed"),
        ("7..0.1", "failed"), ("7._0-1", "failed"), ("7.0.1.", "failed"),
        (".7.0.1", "failed"), ("7/0/1", "failed"),
    ],
)
def test_rtd_version_alias_preserves_numeric_segment_boundaries(
    tmp_path, capsys, expected, status
):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    rc, payload = _invoke(
        capsys,
        [
            "plan", "--project", str(project), "--intent", str(intent),
            "--rtd-version", expected,
        ],
    )
    assert payload["status"] == status
    assert (rc == 0) is (status == "passed")


def test_configured_vendor_runner_forwards_every_runtime_control(monkeypatch, tmp_path):
    config = RuntimeConfig.from_dict({
        "project": tmp_path / "project", "s32ds_root": tmp_path / "s32ds",
        "sdk_path": tmp_path / "sdk", "workspace": tmp_path / "workspace",
        "temp_root": tmp_path / "temp", "log_root": tmp_path / "logs",
        "validation_timeout_s": 73,
    })
    calls = []

    def validate(project, root, **kwargs):
        calls.append((project, root, kwargs))
        return SimpleNamespace(passed=True)

    monkeypatch.setattr(cli, "run_validation", validate)
    runner = cli._configured_vendor_runner(config)
    project = object()
    staging = tmp_path / "candidate.mex"
    result = runner(
        staging=staging, document=object(), project=project, bundle=object()
    )

    assert result.status == "passed"
    assert calls == [(project, config.s32ds_root, {
        "sdk_path": config.sdk_path,
        "workspace": config.workspace,
        "timeout_s": 73,
        "temp_root": config.temp_root,
        "log_root": config.log_root,
        "mex_file": staging,
    })]
    assert cli._configured_vendor_runner(RuntimeConfig.from_dict({
        "project": tmp_path / "project",
    })) is None


def test_shortcut_accepts_the_same_explicit_vendor_runtime_controls(tmp_path):
    args = cli.build_parser().parse_args([
        "mcl", "set", "--project", str(tmp_path / "project"),
        "--s32ds-root", str(tmp_path / "s32ds"),
        "--sdk-path", str(tmp_path / "sdk"),
        "--workspace", str(tmp_path / "workspace"),
        "--temp-root", str(tmp_path / "temp"),
        "--log-root", str(tmp_path / "logs"),
        "--timeout", "81",
    ])
    config, _expected = cli._load_runtime_config(args)
    assert config.s32ds_root == tmp_path / "s32ds"
    assert config.validation_timeout_s == 81


@pytest.mark.parametrize("shortcut", SHORTCUTS)
def test_every_shortcut_uses_the_same_config_only_runtime_contract(
    tmp_path, shortcut
):
    configured_project = tmp_path / "configured-project"
    explicit_project = tmp_path / "explicit-project"
    config_path = _write_json(tmp_path / "runtime.json", {
        "project": str(configured_project), "backend": "mex", "vendor": "nxp",
        "family": "s32k3", "device": "s32k344", "package": "default",
        "rtd_version": "7_0_1", "schema_version": "19",
        "s32ds_root": str(tmp_path / "s32ds"), "sdk_path": str(tmp_path / "sdk"),
        "workspace": str(tmp_path / "workspace"), "temp_root": str(tmp_path / "temp"),
        "log_root": str(tmp_path / "logs"), "asset_root": str(tmp_path / "assets"),
        "validation_timeout_s": 91,
    })
    parser = cli.build_parser()

    config_only, expected = cli._load_runtime_config(parser.parse_args([
        *shortcut, "--config", str(config_path),
    ]))
    overridden, overridden_expected = cli._load_runtime_config(parser.parse_args([
        *shortcut, "--config", str(config_path), "--project", str(explicit_project),
    ]))

    assert config_only.project == configured_project
    assert overridden == replace(config_only, project=explicit_project)
    assert expected == overridden_expected == cli._EXPECTED_IDENTITY_FIELDS


@pytest.mark.parametrize("shortcut", SHORTCUTS)
def test_every_shortcut_reports_one_missing_project_contract(shortcut):
    args = cli.build_parser().parse_args([*shortcut])

    with pytest.raises(CliFailure) as caught:
        cli._load_runtime_config(args)

    assert caught.value.code == "invalid_arguments"
    assert caught.value.exit_code == 2


def test_generic_plan_is_read_only_and_has_zero_validation_side_effects(
    tmp_path, monkeypatch, capsys
):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()
    intent = _write_json(
        tmp_path / "intent.json",
        {"module": "uart", "action": "set", "payload": {"hw": "LPUART_0"}},
    )
    monkeypatch.setattr(
        cli, "run_static_checks",
        lambda *_a, **_k: pytest.fail("plan must not run static checks"),
    )
    monkeypatch.setattr(
        cli, "ConfigureTransaction",
        lambda *_a, **_k: pytest.fail("plan must not construct a transaction"),
    )
    monkeypatch.setattr(
        cli, "run_validation",
        lambda *_a, **_k: pytest.fail("plan must not run vendor validation"),
    )
    monkeypatch.setattr(
        cli, "release_for_publish",
        lambda *_a, **_k: pytest.fail("plan must not enter the publish gate"),
    )
    monkeypatch.setattr(
        cli, "_configure_verified_project",
        lambda *_a, **_k: pytest.fail("plan must not enter configure dispatch"),
    )

    def forbidden_apply(_document, _intent, *, bundle):
        pytest.fail("plan must not invoke the registered apply function")

    registry = cli.get_provider_registry()
    bindings = []
    for key in registry.keys():
        binding = registry.lookup(*key)
        if key == ("mex", "uart", "set"):
            binding = replace(binding, apply_fn=forbidden_apply)
        bindings.append(binding)
    isolated_registry = ProviderRegistry(bindings)
    monkeypatch.setattr(cli, "get_provider_registry", lambda: isolated_registry)

    rc, payload = _invoke(
        capsys, ["plan", "--project", str(project), "--intent", str(intent)]
    )

    assert rc == 0
    assert payload["command"] == "plan"
    assert mex.read_bytes() == original


def test_generic_commands_resolve_default_assets_outside_current_directory(tmp_path):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    env = dict(os.environ)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "plan", "--project", str(project),
            "--intent", str(intent), "--json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "passed"
    assert result.stderr == ""


def test_generic_and_shortcut_configure_use_one_canonical_dispatcher(
    tmp_path, monkeypatch
):
    project = tmp_path / "project-need-not-be-opened-by-the-dispatch-spy"
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    spec = _write_json(tmp_path / "spec.json", {})
    calls = []

    def capture(config, **kwargs):
        calls.append((config, kwargs))
        return 17

    monkeypatch.setattr(cli, "_execute_canonical_request", capture)

    assert cli.main([
        "configure", "--project", str(project), "--intent", str(intent), "--json",
    ]) == 17
    assert cli.main([
        "mcl", "set", "--project", str(project), "--spec", str(spec),
        "--configure", "--json",
    ]) == 17

    assert len(calls) == 2
    assert all(kwargs["configure"] is True for _config, kwargs in calls)
    assert calls[0][1]["intent"].module == "mcl"
    assert calls[0][1].get("binding") is None
    assert calls[1][1]["binding"].key == ("mex", "mcl", "set")
    assert calls[1][1]["shortcut_args"].command == "mcl"


def test_generic_configure_matches_shortcut_noop(tmp_path, capsys):
    generic_root = tmp_path / "generic"
    shortcut_root = tmp_path / "shortcut"
    generic_root.mkdir()
    shortcut_root.mkdir()
    generic_project = copy_uart_fixture(generic_root)
    shortcut_project = copy_uart_fixture(shortcut_root)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    spec = _write_json(tmp_path / "spec.json", {})

    generic_rc, generic = _invoke(
        capsys,
        ["configure", "--project", str(generic_project), "--intent", str(intent)],
    )
    shortcut_rc, shortcut = _invoke(
        capsys,
        [
            "mcl", "set", "--project", str(shortcut_project), "--spec", str(spec),
            "--configure",
        ],
    )

    assert generic_rc == shortcut_rc == 0
    for key in ("status", "command", "normalized_intent", "plan", "changed_modules", "published"):
        assert generic[key] == shortcut[key]
    assert generic["published"] is False


def test_generic_configure_matches_shortcut_published_bytes(tmp_path, capsys):
    generic_root = tmp_path / "generic-write"
    shortcut_root = tmp_path / "shortcut-write"
    generic_root.mkdir()
    shortcut_root.mkdir()
    generic_project = copy_uart_fixture(generic_root)
    shortcut_project = copy_uart_fixture(shortcut_root)
    parameters = {
        "hw": "LPUART_0", "mode": "interrupt", "baud": 115200,
        "pins": {"tx": "PTA15", "rx": "PTA16"},
    }
    intent = _write_json(
        tmp_path / "write-intent.json",
        {"module": "uart", "action": "set", "payload": parameters},
    )
    spec = _write_json(tmp_path / "write-spec.json", parameters)

    generic_rc, generic = _invoke(
        capsys,
        ["configure", "--project", str(generic_project), "--intent", str(intent)],
    )
    shortcut_rc, shortcut = _invoke(
        capsys,
        [
            "uart", "set", "--project", str(shortcut_project), "--spec", str(spec),
            "--configure",
        ],
    )

    assert generic_rc == shortcut_rc == 0
    assert generic["changed_modules"] == shortcut["changed_modules"]
    assert (generic_project / "Uart_Example.mex").read_bytes() == (
        shortcut_project / "Uart_Example.mex"
    ).read_bytes()


@pytest.mark.parametrize(("module", "action", "parameters"), CASES)
def test_generic_configure_matches_every_registered_shortcut_and_published_bytes(
    tmp_path, capsys, module, action, parameters
):
    generic_root = tmp_path / "generic"
    shortcut_root = tmp_path / "shortcut"
    generic_root.mkdir()
    shortcut_root.mkdir()
    generic_project = copy_uart_fixture(generic_root)
    shortcut_project = copy_uart_fixture(shortcut_root)
    intent = _write_json(
        tmp_path / "intent.json",
        {"module": module, "action": action, "payload": parameters},
    )
    spec = _write_json(tmp_path / "spec.json", parameters)

    generic_rc, generic = _invoke(
        capsys,
        ["configure", "--project", str(generic_project), "--intent", str(intent)],
    )
    shortcut_rc, shortcut = _invoke(
        capsys,
        [*_shortcut(module, action, shortcut_project, spec), "--configure"],
    )

    assert generic_rc == shortcut_rc
    assert _normalize_checked_cleanup_residual(generic) == (
        _normalize_checked_cleanup_residual(shortcut)
    )
    assert (generic_project / "Uart_Example.mex").read_bytes() == (
        shortcut_project / "Uart_Example.mex"
    ).read_bytes()


@pytest.mark.parametrize(("module", "action", "parameters"), CASES)
def test_generic_and_shortcut_failures_have_equal_path_safe_diagnostics(
    tmp_path, capsys, module, action, parameters
):
    secret_project = tmp_path / "PRIVATE_PROJECT_sk_live_SUPERSECRET"
    intent = _write_json(
        tmp_path / "intent.json",
        {"module": module, "action": action, "payload": parameters},
    )
    spec = _write_json(tmp_path / "spec.json", parameters)

    generic_rc, generic = _invoke(
        capsys,
        ["plan", "--project", str(secret_project), "--intent", str(intent)],
    )
    shortcut_rc, shortcut = _invoke(
        capsys, _shortcut(module, action, secret_project, spec),
    )

    assert generic_rc == shortcut_rc != 0
    assert generic["diagnostics"] == shortcut["diagnostics"]
    public = json.dumps(
        {"generic": generic, "shortcut": shortcut}, ensure_ascii=False
    ).lower()
    assert "private_project" not in public
    assert "sk_live_supersecret" not in public
    assert str(secret_project).lower() not in public


def test_generic_configure_redacts_internal_write_failure_secrets(
    tmp_path, monkeypatch, capsys
):
    project = copy_uart_fixture(tmp_path)
    intent = _write_json(
        tmp_path / "intent.json", {"module": "mcl", "action": "set", "payload": {}}
    )
    secret = str(tmp_path / "PRIVATE_WRITE_sk_live_SUPERSECRET.mex")

    class FailingTransaction:
        def __init__(self, *_args, **_kwargs):
            pass

        def execute(self, *_args, **_kwargs):
            raise cli.MexWriteError(f"write failed for {secret}")

    monkeypatch.setattr(cli, "ConfigureTransaction", FailingTransaction)

    rc, payload = _invoke(
        capsys,
        ["configure", "--project", str(project), "--intent", str(intent)],
    )

    assert rc != 0
    assert payload["diagnostics"][0]["code"] == "narrow_mex_write_unavailable"
    public = json.dumps(payload, ensure_ascii=False).lower()
    assert "private_write" not in public
    assert "sk_live_supersecret" not in public
    assert secret.lower() not in public
