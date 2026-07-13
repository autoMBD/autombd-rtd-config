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
# File:        test_asset_bundle_injection.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Mandatory immutable asset-bundle injection contract tests.
# =================================================================================

from __future__ import annotations

import inspect
from pathlib import Path
import re
import shutil

import pytest

from rtd_config.backends.s32_mex import apply
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.checks.static import run_static_checks
from rtd_config.intent import Intent
from rtd_config.modules.adc import AdcProvider
from rtd_config.modules.basenxp import BaseNxpProvider
from rtd_config.modules.dio import DioProvider
from rtd_config.modules.mcl import MclProvider
from rtd_config.modules.mcu import McuProvider
from rtd_config.modules.platform import PlatformProvider
from rtd_config.modules.port import PortProvider
from rtd_config.modules.uart import UartProvider
from rtd_config.project import Project
from rtd_config.resources.bundles import AssetBundleResolver
from tests.fixtures import ADC_FIXTURE, copy_adc_fixture, copy_uart_fixture


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "autombd-rtd/assets"
UART = ROOT / "tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344"


def bundle():
    with Project.verified(UART) as project:
        return AssetBundleResolver(ASSETS).resolve(project.metadata)


@pytest.mark.parametrize("provider", [
    UartProvider, PlatformProvider, BaseNxpProvider, MclProvider,
    PortProvider, DioProvider, McuProvider, AdcProvider,
])
def test_public_providers_require_bundle(provider):
    with pytest.raises(TypeError):
        provider()


@pytest.mark.parametrize("function", [
    apply.apply_uart_set, apply.apply_uart_add_flexio_channel,
    apply.apply_platform_set, apply.apply_basenxp_set, apply.apply_mcl_set,
    apply.apply_port_set, apply.apply_dio_set, apply.apply_mcu_set,
    apply.apply_adc_set, run_static_checks,
])
def test_public_consumers_have_mandatory_keyword_only_bundle(function):
    parameter = inspect.signature(function).parameters["bundle"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_bundle_json_is_defensive_and_never_reopened(monkeypatch):
    resolved = bundle()
    first = resolved.load_json("uart")
    first["enum_domains"] = {"poison": True}
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: pytest.fail("asset reopened"))
    assert "poison" not in resolved.load_json("uart")["enum_domains"]


def test_resolved_bundle_and_consumers_never_reopen_captured_assets(
    monkeypatch, tmp_path
):
    asset_root = tmp_path / "assets"
    shutil.copytree(ASSETS, asset_root)
    with Project.verified(UART) as project:
        resolved = AssetBundleResolver(asset_root).resolve(project.metadata)
    (asset_root / resolved.assets["uart"]).unlink()

    import rtd_config.resources.bundles as bundles_module
    monkeypatch.setattr(
        bundles_module, "snapshot_safe_relative",
        lambda *_args, **_kwargs: pytest.fail("captured asset was reopened"),
    )
    assert resolved.load_json("uart")["_identity"]["module"] == "Uart"
    intent = Intent.from_dict({
        "module": "uart", "action": "set",
        "payload": {"hw": "LPUART_3", "mode": "interrupt", "baud": 115200},
    })
    assert UartProvider(resolved).plan(intent).changes
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    assert not apply.apply_uart_set(doc, intent, bundle=resolved).blocked
    assert run_static_checks(mex, doc=doc, bundle=resolved).status == "passed"


def test_flexio_nested_mcl_receives_same_bundle(monkeypatch, tmp_path):
    resolved = bundle()
    seen = []
    original = apply.apply_mcl_set

    def capture(doc, intent, *, bundle):
        seen.append(bundle)
        return original(doc, intent, bundle=bundle)

    monkeypatch.setattr(apply, "apply_mcl_set", capture)
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    intent = Intent.from_dict({
        "module": "uart", "action": "add_flexio_channel",
        "payload": {"baud": 921600, "tx_name": "SENTINEL_TX", "rx_name": "SENTINEL_RX"},
    })
    result = apply.apply_uart_add_flexio_channel(doc, intent, bundle=resolved)
    assert not result.blocked
    assert seen and all(item is resolved for item in seen)


def test_adc_recursive_apply_receives_same_bundle(monkeypatch, tmp_path):
    with Project.verified(ADC_FIXTURE) as project:
        resolved = AssetBundleResolver(ASSETS).resolve(project.metadata)
    seen = []
    original = apply.apply_adc_set

    def capture(doc, intent, *, bundle):
        seen.append(bundle)
        return original(doc, intent, bundle=bundle)

    monkeypatch.setattr(apply, "apply_adc_set", capture)
    project = copy_adc_fixture(tmp_path)
    doc = MexDocument.load(project / "Autombd_Test_Adc_S32K344.mex")
    intent = Intent.from_dict({
        "module": "adc", "action": "set",
        "payload": {
            "units": [{"unit": "ADC1"}, {"unit": "ADC2"}],
            "transfer": "interrupt",
        },
    })
    result = original(doc, intent, bundle=resolved)
    assert not result.blocked
    assert len(seen) == 2 and all(item is resolved for item in seen)


def test_production_sources_have_no_fixed_asset_loaders_or_fallbacks():
    source_root = ROOT / "autombd-rtd/rtd-config-cli-py/rtd_config"
    text = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.py"))
    for forbidden in (
        "_ASSET_ROOT", "_UART_ASSET_PATH", "_PLATFORM_ASSET_PATH",
        "_load_uart_asset", "_load_basenxp_asset", "_load_mcl_asset",
        "_load_adc_asset", "_load_pins_data", "_DEFAULT_PIN_FIELD",
    ):
        assert re.search(rf"(?<![A-Za-z0-9_]){re.escape(forbidden)}(?![A-Za-z0-9_])", text) is None
