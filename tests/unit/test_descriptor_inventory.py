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
# File:        test_descriptor_inventory.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Descriptor coverage extraction and offline-gate contract tests.
# =================================================================================

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "extract_xdm_coverage.py"
COVERAGE_ROOT = ROOT / "docs" / "specs" / "rtd-config-module-coverage"
RUNTIME_ROOT = ROOT / "autombd-rtd"


def _tool_module():
    assert TOOL.is_file(), "descriptor inventory extractor is required"
    spec = importlib.util.spec_from_file_location("extract_xdm_coverage", TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _synthetic_xdm(path: Path) -> Path:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<a:datamodel xmlns:a="urn:test" version="3.0">
  <a:ctr name="Root">
    <a:var name="Mode" type="ENUMERATION">
      <a:da name="DEFAULT" value="A"/>
      <a:da name="RANGE"><a:v>A</a:v><a:v>B</a:v></a:da>
      <a:a name="EDITABLE" type="XPath"><a:tst expr="../Enabled='true'"/></a:a>
      <a:da name="INVALID" type="XPath"><a:tst expr=".='B'" true="blocked"/></a:da>
    </a:var>
    <a:var name="Count" type="INTEGER">
      <a:da name="MIN" value="1"/><a:da name="MAX" value="8"/>
      <a:da name="READONLY" value="false"/>
    </a:var>
    <a:lst name="Entries"><a:da name="ENABLE" value="true"/></a:lst>
    <a:ref name="Target" type="REFERENCE">
      <a:da name="REF" value="ASPathDataOfSchema:/Other/Module/Target"/>
    </a:ref>
  </a:ctr>
</a:datamodel>
""",
        encoding="utf-8",
    )
    return path


def test_synthetic_extractor_is_deterministic_and_preserves_descriptor_facts(tmp_path):
    tool = _tool_module()
    source = _synthetic_xdm(tmp_path / "Synthetic.xdm")

    first = tool.extract_descriptor(source, module="Synthetic")
    second = tool.extract_descriptor(source, module="Synthetic")

    assert first == second
    assert first["source"]["descriptor"] == "Synthetic.xdm"
    assert first["source"]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest().upper()
    assert all(item["key"] == f'{item["kind"]}:{item["path"]}' for item in first["items"])
    mode = next(item for item in first["items"] if item["name"] == "Mode")
    assert mode["type"] == "ENUMERATION"
    assert mode["default"] == {"kind": "literal", "value": "A"}
    assert mode["range"] == {"kind": "literal", "values": ["A", "B"]}
    assert mode["editable"]["kind"] == "xpath"
    assert mode["invalid"]["tests"][0]["true"] == "blocked"
    target = next(item for item in first["items"] if item["name"] == "Target")
    assert target["reference"].endswith("/Other/Module/Target")
    assert target["cross_references"] == ["Other"]


@pytest.mark.parametrize(
    ("module", "count", "sha256"),
    [
        ("mcu", 489, "956DDD8BAB138AD6D9C8454F0F3CC6A1233CF200FE7E9864C4AF7FADF97D282D"),
        ("adc", 279, "D9601D143375F7D0BC2582F1B4BF9C1B93DC50CE975E736140A64F72FDA12BE8"),
    ],
)
def test_committed_descriptor_inventory_has_golden_count_and_identity(module, count, sha256):
    sidecar = json.loads((COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8"))
    assert sidecar["source"]["sha256"] == sha256
    assert sidecar["summary"]["total"] == count == len(sidecar["items"])
    assert sidecar["source"]["descriptor"] == f"{module.title()}.xdm"
    assert not any(":" in str(value) and "\\" in str(value) for value in sidecar["source"].values())


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_key", "double_classification", "missing_trace", "empty_reason", "bad_cross_ref"],
)
def test_offline_gate_rejects_inventory_mutations(mutation):
    tool = _tool_module()
    sidecar = json.loads((COVERAGE_ROOT / "adc.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(sidecar)
    if mutation == "duplicate_key":
        broken["items"].append(copy.deepcopy(broken["items"][0]))
    elif mutation == "double_classification":
        broken["items"][0]["classification"] = ["derived", "deferred"]
    elif mutation == "missing_trace":
        item = next(item for item in broken["items"] if item["classification"] == "configurable")
        item.pop("trace")
    elif mutation == "empty_reason":
        item = next(item for item in broken["items"] if item["classification"] == "deferred")
        item["reason"] = ""
    else:
        broken["items"][0]["cross_references"] = ["NotARealModule"]

    with pytest.raises(tool.InventoryError):
        tool.validate_sidecar(broken, repo_root=ROOT)


def test_verify_source_rejects_hash_or_extraction_drift(tmp_path):
    tool = _tool_module()
    source = _synthetic_xdm(tmp_path / "Synthetic.xdm")
    extracted = tool.extract_descriptor(source, module="Synthetic")
    sidecar = tool.classify_inventory(extracted, {"default": {
        "classification": "deferred", "reason": "Synthetic test item.",
        "dependency": "Synthetic implementation scope.",
    }})
    tool.verify_source(sidecar, source)
    sidecar["source"]["sha256"] = "0" * 64
    with pytest.raises(tool.InventoryError):
        tool.verify_source(sidecar, source)


def test_runtime_assets_and_release_manifest_exclude_coverage_sidecars():
    tool = _tool_module()
    tool.validate_repository(ROOT)
    for path in (RUNTIME_ROOT / "assets").rglob("*.json"):
        assert "_coverage" not in json.loads(path.read_text(encoding="utf-8"))
    manifest = RUNTIME_ROOT / "release-manifest.json"
    if manifest.exists():
        assert "rtd-config-module-coverage" not in manifest.read_text(encoding="utf-8")
