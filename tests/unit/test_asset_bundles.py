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
# File:        test_asset_bundles.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Exact asset-bundle resolution and validation tests.
# =================================================================================

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from rtd_config.backends.s32_mex.metadata import ModuleMetadata, ToolMetadata
from rtd_config import cli
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.project import Project
from rtd_config.resources.bundles import AssetBundleResolver


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "autombd-rtd" / "assets"
UART = ROOT / "tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344"
ADC = ROOT / "tests/fixtures/nxp/ds/s32k3/Autombd_Test_Adc_S32K344"


def metadata(project: Path):
    with Project.verified(project) as value:
        return value.metadata


@pytest.mark.parametrize(("project", "profile"), [(UART, "uart"), (ADC, "adc")])
def test_real_fixture_resolves_exact_profile(project, profile):
    bundle = AssetBundleResolver(ASSETS).resolve(metadata(project))
    assert bundle.id == "nxp-s32-mex-s32k344-mapbga257-rtd-7.0.1"
    assert bundle.profile_id == profile
    assert bundle.pin_field == "pin_mapbga257"
    assert bundle.load_json("pins")["_identity"]["package"] == "mapbga257"
    assert bundle.load_json("pins") is bundle.load_json("pins")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vendor", "OTHER"), ("backend", "other"), ("processor", "S32K342"),
        ("family", "S32K1"), ("device", "S32K342"),
        ("raw_package", "S32K344_172HDQFP"), ("package", "hdqfp172"),
        ("rtd_release", "7.0.0"), ("schema_version", "18"),
        ("tools", (ToolMetadata("Pins", "16.0", True),)),
    ],
)
def test_identity_or_tool_mismatch_is_unsupported(field, value):
    base = metadata(UART)
    if field == "schema_version":
        namespace = "http://mcuxpresso.nxp.com/XSD/mex_configuration_18"
        base = replace(base, xml_namespace=namespace, schema_location=f"{namespace} {namespace}.xsd")
    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(ASSETS).resolve(replace(base, **{field: value}))
    assert caught.value.code == "asset_bundle_unsupported"


def test_unknown_and_cross_profile_module_sets_are_unsupported():
    base = metadata(UART)
    for modules in (None, metadata(ADC).modules + (base.modules[1],)):
        with pytest.raises(CliFailure) as caught:
            AssetBundleResolver(ASSETS).resolve(replace(base, modules=modules))
        assert caught.value.code in {"project_metadata_unknown", "asset_bundle_unsupported"}


def test_published_values_for_mcu_and_mcl_must_remain_unknown():
    base = metadata(UART)
    modules = tuple(
        replace(item, software_version="7.0.1") if item.name == "Mcu" else item
        for item in base.modules
    )
    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(ASSETS).resolve(replace(base, modules=modules))
    assert caught.value.code == "asset_bundle_unsupported"


def copied_assets(tmp_path: Path) -> Path:
    target = tmp_path / "assets"
    shutil.copytree(ASSETS, target)
    return target


@pytest.mark.parametrize("path", ["/absolute.json", "nxp\\bad.json", "../bad.json", "x.txt"])
def test_manifest_rejects_unsafe_or_non_json_asset_paths(tmp_path, path):
    root = copied_assets(tmp_path)
    manifest = json.loads((root / "bundles.json").read_text())
    manifest["bundles"][0]["assets"]["pins"] = path
    (root / "bundles.json").write_text(json.dumps(manifest))
    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(root)
    assert caught.value.code == "asset_manifest_invalid"


@pytest.mark.parametrize(("mutation", "code"), [
    ("missing", "asset_not_found"), ("corrupt", "asset_invalid"),
    ("nonobject", "asset_invalid"), ("identity", "asset_identity_mismatch"),
])
def test_asset_load_failures_are_typed(tmp_path, mutation, code):
    root = copied_assets(tmp_path)
    path = root / "nxp/s32k3/port/pins.json"
    if mutation == "missing": path.unlink()
    elif mutation == "corrupt": path.write_text("{")
    elif mutation == "nonobject": path.write_text("[]")
    else:
        value = json.loads(path.read_text())
        value["_identity"]["device"] = "S32K342"
        path.write_text(json.dumps(value))
    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(root).resolve(metadata(UART))
    assert caught.value.code == code


def test_duplicate_matches_are_ambiguous(tmp_path):
    root = copied_assets(tmp_path)
    path = root / "bundles.json"
    manifest = json.loads(path.read_text())
    duplicate = dict(manifest["bundles"][0])
    duplicate["id"] = "duplicate"
    manifest["bundles"].append(duplicate)
    path.write_text(json.dumps(manifest))
    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(root).resolve(metadata(UART))
    assert caught.value.code == "asset_bundle_ambiguous"


@pytest.mark.parametrize("content", [None, "{", "[]", '{"format_version":2,"bundles":[]}'])
def test_missing_or_malformed_manifest_is_typed(tmp_path, content):
    if content is not None:
        (tmp_path / "bundles.json").write_text(content)
    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(tmp_path)
    assert caught.value.code in {"asset_manifest_not_found", "asset_manifest_invalid"}


def test_manifest_symbolic_link_is_rejected_fail_closed(tmp_path):
    root = copied_assets(tmp_path)
    manifest = root / "bundles.json"
    outside = tmp_path / "outside-bundles.json"
    manifest.replace(outside)
    try:
        manifest.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symbolic-link creation unavailable: {exc}")

    with pytest.raises(CliFailure) as caught:
        AssetBundleResolver(root)
    assert caught.value.code == "asset_manifest_invalid"


def test_resolution_failure_precedes_provider_apply_and_vendor(monkeypatch):
    calls = {"plan": 0, "apply": 0, "vendor": 0}

    class RejectingResolver:
        def __init__(self, _root): pass
        def resolve(self, _metadata):
            raise CliFailure("asset_bundle_unsupported", "unsupported")

    class Provider:
        def plan(self, _intent):
            calls["plan"] += 1

    monkeypatch.setattr(cli, "AssetBundleResolver", RejectingResolver)
    monkeypatch.setattr(cli, "UartProvider", Provider)
    monkeypatch.setattr(cli, "normalize_uart_intent", lambda _args: Intent.from_dict({"module":"uart", "action":"set", "payload":{}}))
    monkeypatch.setattr(cli, "apply_uart_set", lambda *_args, **_kwargs: calls.__setitem__("apply", calls["apply"] + 1))
    monkeypatch.setattr(cli, "run_validation", lambda *_args, **_kwargs: calls.__setitem__("vendor", calls["vendor"] + 1))
    with pytest.raises(CliFailure) as caught:
        cli.cmd_uart_set(SimpleNamespace(project=UART, configure=True))
    assert caught.value.code == "asset_bundle_unsupported"
    assert calls == {"plan": 0, "apply": 0, "vendor": 0}
