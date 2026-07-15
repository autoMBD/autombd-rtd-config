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

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re

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


def _synthetic_repeated_facts_xdm(path: Path) -> Path:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<a:datamodel xmlns:a="urn:test" version="3.0">
  <a:ctr name="Root">
    <a:var name="Bounded" type="INTEGER">
      <a:a name="INVALID" type="XPath">
        <a:tst expr="../Enabled='false'" true="disabled"/>
      </a:a>
      <a:da name="INVALID" type="Range">
        <a:tst expr="&lt;=10"/><a:tst expr="&gt;=1"/>
      </a:da>
    </a:var>
    <a:ref name="External" type="REFERENCE">
      <a:da name="REF" value="ASPathDataOfSchema:/AUTOSAR/EcucDefs/EcuC/Partition"/>
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


def test_extractor_preserves_every_repeated_a_and_da_constraint(tmp_path):
    tool = _tool_module()
    source = _synthetic_repeated_facts_xdm(tmp_path / "Repeated.xdm")

    extracted = tool.extract_descriptor(source, module="Synthetic")
    bounded = next(item for item in extracted["items"] if item["name"] == "Bounded")
    evidence = json.dumps(bounded["invalid"], ensure_ascii=False)

    assert "../Enabled='false'" in evidence
    assert "disabled" in evidence
    assert "<=10" in evidence
    assert ">=1" in evidence


@pytest.mark.parametrize("module", ["Mcu", "Adc"])
def test_exact_module_extraction_retains_named_cross_module_references(tmp_path, module):
    tool = _tool_module()
    source = _synthetic_repeated_facts_xdm(tmp_path / f"{module}.xdm")

    extracted = tool.extract_descriptor(source, module=module)
    external = next(item for item in extracted["items"] if item["name"] == "External")

    assert external["kind"] == "reference"
    assert external["cross_references"] == ["EcuC"]


@pytest.mark.parametrize(
    ("module", "count", "sha256"),
    [
        ("mcu", 489, "956DDD8BAB138AD6D9C8454F0F3CC6A1233CF200FE7E9864C4AF7FADF97D282D"),
        ("adc", 279, "D9601D143375F7D0BC2582F1B4BF9C1B93DC50CE975E736140A64F72FDA12BE8"),
        ("uart", 56, "0B5064AA0DCBE90048C1DBC2D49C540887D941D39B04962785FB7F98789FEED5"),
        ("platform", 73, "D3BA70C932DA05DF1A952CCB5D5737DF083CAC942C9FA204E7D075B8C3C8939B"),
        ("basenxp", 34, "8CD7DE06F69CADC997E8BA240E36C3EF7A67AAC6B520E04789AE0DC9B610C754"),
        ("mcl", 245, "264610E47D335A127E398B753AF6CA320CC176DF68FF288F06B26001BA0B9DE9"),
        ("port", 82, "59C1552C2B083929132115546AA2196BCE7E1A5B73A537AC5A10A825744C2A68"),
        ("dio", 45, "E3F8FDF2BACED5D8014FA9FE1A4B0C5AB527B9C1C665C8FC1E6A15768BC63278"),
    ],
)
def test_committed_descriptor_inventory_has_golden_count_and_identity(module, count, sha256):
    sidecar = json.loads((COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8"))
    assert sidecar["source"]["sha256"] == sha256
    assert sidecar["summary"]["total"] == count == len(sidecar["items"])
    descriptor = "BaseNXP.xdm" if module == "basenxp" else f"{module.title()}.xdm"
    assert sidecar["source"]["descriptor"] == descriptor
    assert not any(":" in str(value) and "\\" in str(value) for value in sidecar["source"].values())


def test_repository_gate_contains_every_shipped_module_sidecar():
    assert {path.stem for path in COVERAGE_ROOT.glob("*.json")} == {
        "uart", "platform", "basenxp", "mcl", "port", "dio", "mcu", "adc",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_key", "double_classification", "missing_trace", "empty_reason",
        "bad_cross_ref", "symbol_substring", "test_node_substring",
    ],
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
    elif mutation == "bad_cross_ref":
        broken["items"][0]["cross_references"] = ["NotARealModule"]
    elif mutation == "symbol_substring":
        item = next(item for item in broken["items"] if item["classification"] == "configurable")
        path = item["trace"]["provider"].split(":", 1)[0]
        item["trace"]["provider"] = f"{path}:from"
    else:
        item = next(item for item in broken["items"] if item["classification"] == "configurable")
        path = item["trace"]["tests"][0].split("::", 1)[0]
        item["trace"]["tests"] = [f"{path}::test_"]

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


def test_known_descriptor_gap_groups_are_complete_and_explicitly_deferred():
    expected = {
        "mcu": {"mcu_reset": 23},
        "adc": {
            "adc_dspss": 25,
            "adc_self_test": 8,
            "adc_timing": 12,
            "adc_general": 1,
            "adc_power": 8,
            "adc_published_information": 14,
            "adc_autosar_extension": 43,
        },
    }
    for module, groups in expected.items():
        sidecar = json.loads(
            (COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8")
        )
        by_key = {item["key"]: item for item in sidecar["items"]}
        assert {name: len(keys) for name, keys in sidecar["known_gaps"].items()} == groups
        assert all(
            by_key[key]["classification"] == "deferred"
            for keys in sidecar["known_gaps"].values()
            for key in keys
        )


def test_recipe_fixed_and_automatic_fields_are_not_claimed_caller_configurable():
    expectations = {
        "mcu": {
            "McuNoPll", "McuPll0UnderMcuControl", "McuPLLUnderMcuControl",
            "McuPllOdiv0_En", "McuPllOdiv1_En",
        },
        "adc": {"AdcEnableWatchdogApi", "WdgThresholdEnable"},
    }
    for module, names in expectations.items():
        sidecar = json.loads(
            (COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8")
        )
        matched = [item for item in sidecar["items"] if item["name"] in names]
        assert {item["name"] for item in matched} == names
        assert all(item["classification"] != "configurable" for item in matched)


def test_runtime_python_never_reads_development_coverage_sidecars():
    forbidden = ("rtd-config-module-coverage", "known_gaps")
    for path in (RUNTIME_ROOT / "rtd-config-cli-py" / "rtd_config").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        call_literals = [
            value.value
            for call in ast.walk(tree) if isinstance(call, ast.Call)
            for value in ast.walk(call)
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        ]
        assert not any(
            token in literal for token in forbidden for literal in call_literals
        ), path


@pytest.mark.parametrize("module", ["mcu", "adc"])
def test_module_overrides_never_classify_by_unqualified_basename(module):
    overrides = json.loads(
        (ROOT / f"tools/xdm-coverage-overrides/{module}.json").read_text(
            encoding="utf-8"
        )
    )
    selectors = [rule["match"] for rule in overrides["rules"]]
    selectors.extend(
        selector
        for group in overrides.get("known_gap_rules", {}).values()
        for selector in group
    )
    assert all("name" not in selector and "key_regex" not in selector for selector in selectors)
    assert all(
        set(selector) & {"key", "keys", "path", "paths", "path_prefixes"}
        for selector in selectors
    )


def test_mcu_coverage_is_pll0_exact_and_traces_every_actual_edit():
    sidecar = json.loads((COVERAGE_ROOT / "mcu.json").read_text(encoding="utf-8"))
    items = sidecar["items"]
    actual = {
        "McuNoPll", "McuPll0UnderMcuControl", "McuPLLUnderMcuControl",
        "McuPLLEnabled", "McuPllOdiv0_En", "McuPllOdiv1_En",
        "McuClkMux0_Source", "McuClockReferencePoint", "McuClockFrequencySelect",
    }
    assert all(
        item["classification"] != "deferred"
        for item in items if item["name"] in actual and "ctr[McuPll_1]" not in item["path"]
    )
    assert all(
        item["classification"] == "deferred"
        for item in items
        if "ctr[McuPll_1]" in item["path"] or "ctr[McuPll_Parameter]" in item["path"]
    )


def test_adc_created_parent_structures_are_coverage_accounted():
    sidecar = json.loads((COVERAGE_ROOT / "adc.json").read_text(encoding="utf-8"))
    required = {
        "AdcHwUnit", "AdcChannel", "AdcGroup", "AdcGroupConversionConfiguration",
        "AdcThresholdControl", "AdcHwTrigger", "AdcHwConfiguration", "BctuHwUnit",
        "BctuInternalTrigger", "BctuListItems", "BctuResultFifos",
        "BctuAdcNotifications",
    }
    observed = {
        item["name"] for item in sidecar["items"]
        if item["name"] in required and item["classification"] != "deferred"
    }
    assert observed == required


@pytest.mark.parametrize(
    "module", ["uart", "platform", "basenxp", "mcl", "port", "dio"]
)
def test_shipped_module_override_names_are_grounded_under_the_exact_ancestor(module):
    """A basename in a broad rule must not silently classify the wrong branch."""
    overrides = json.loads(
        (ROOT / f"tools/xdm-coverage-overrides/{module}.json").read_text(
            encoding="utf-8"
        )
    )
    sidecar = json.loads(
        (COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8")
    )
    for rule in overrides["rules"]:
        match = rule["match"]
        prefixes = match.get("path_prefixes")
        names = match.get("names")
        assert prefixes and names, f"{module} classification is not ancestor-qualified"
        for name in names:
            matched = [
                item for item in sidecar["items"]
                if item["name"] == name
                and any(item["path"].startswith(prefix) for prefix in prefixes)
            ]
            assert matched, f"{module}:{name} is a dead or wrong-ancestor selector"
            assert all(
                item["classification"] == rule["classification"] for item in matched
            )


def _literal_xml_names_written_by(*function_names: str) -> set[str]:
    source_path = RUNTIME_ROOT / "rtd-config-cli-py/rtd_config/backends/s32_mex/apply.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    written: set[str] = set()
    for function_name in function_names:
        segment = ast.get_source_segment(source, functions[function_name])
        assert segment is not None
        written.update(re.findall(r'name=\\?"([A-Za-z][A-Za-z0-9_]*)', segment))
    return written - {"Name"}


@pytest.mark.parametrize(
    ("module", "ancestor", "writers", "additional_names"),
    [
        (
            "platform", "/lst[IntCtrlConfig]",
            ("_build_platform_isr_struct_bytes",), {"PlatformIsrConfig"},
        ),
        (
            "basenxp", "/lst[OsIfCounterConfig]",
            ("_build_counter_array_bytes",), set(),
        ),
        (
            "mcl", "/lst[dmaLogicChannel_Type]",
            ("_build_dma_logic_channel_struct_bytes",), {"dmaLogicChannel_Type"},
        ),
        (
            "port", "/lst[PortPin]",
            ("_build_portpin_struct_bytes", "_build_gpio_portpin_struct_bytes"),
            {"PortPin"},
        ),
        (
            "dio", "/lst[DioPort]",
            ("_build_dio_channel_array_bytes", "_build_dio_port_struct_bytes"),
            {"DioPort"},
        ),
    ],
)
def test_every_literal_xdm_parent_and_leaf_emitted_by_writers_is_accounted(
    module, ancestor, writers, additional_names
):
    """The coverage sidecar must not defer structures the implementation emits."""
    sidecar = json.loads(
        (COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8")
    )
    written_names = _literal_xml_names_written_by(*writers) | additional_names
    for name in sorted(written_names):
        matched = [
            item for item in sidecar["items"]
            if item["name"] == name and ancestor in item["path"]
        ]
        assert matched, f"{module}:{name} writer output is absent from its XDM inventory"
        assert all(item["classification"] != "deferred" for item in matched), (
            f"{module}:{name} is written by {writers} but remains deferred"
        )


@pytest.mark.parametrize(
    ("module", "ancestor", "names"),
    [
        (
            "uart",
            "/ctr[GeneralConfiguration]",
            {
                "GeneralConfiguration": "configurable",
                "UartCallback": "configurable",
                "UartCallbackCapability": "derived",
                "UartDmaEnable": "derived",
            },
        ),
        (
            "mcl",
            "/ctr[MclDma]",
            {"MclDma": "derived", "MclEnableDma": "derived"},
        ),
    ],
)
def test_attribute_mutations_and_their_exact_parents_are_coverage_accounted(
    module, ancestor, names
):
    sidecar = json.loads(
        (COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8")
    )
    for name, classification in names.items():
        matched = [
            item for item in sidecar["items"]
            if item["name"] == name and ancestor in item["path"]
        ]
        assert matched, f"{module}:{name} is absent under {ancestor}"
        assert all(item["classification"] == classification for item in matched)


@pytest.mark.parametrize(
    ("module", "ancestor", "names"),
    [
        (
            "platform",
            "/lst[IntCtrlConfig]",
            {
                "IsrPriority": "configurable",
                "IsrEnabled": "derived",
                "IsrName": "derived",
                "IsrHandler": "derived",
            },
        ),
        (
            "port",
            "/lst[PortPin]",
            {
                "PortPinPue": "derived",
                "PortPinPus": "derived",
                "PortPinDirection": "deferred",
                "PortPinLevelValue": "deferred",
                "PortPinMode": "deferred",
            },
        ),
    ],
)
def test_fixed_or_derived_writer_fields_are_not_claimed_caller_configurable(
    module, ancestor, names
):
    sidecar = json.loads(
        (COVERAGE_ROOT / f"{module}.json").read_text(encoding="utf-8")
    )
    for name, classification in names.items():
        matched = [
            item for item in sidecar["items"]
            if item["name"] == name and ancestor in item["path"]
        ]
        assert matched, f"{module}:{name} is absent under {ancestor}"
        assert all(item["classification"] == classification for item in matched)
