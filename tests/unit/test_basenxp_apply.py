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
# File:        test_basenxp_apply.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Unit/integration tests for the BaseNXP OsIf system-timer edit
#              (RTD-MEX-BASENXP-001): enable timer and insert counter struct.
# =================================================================================

"""BaseNXP OsIf system-timer enable (RTD-MEX-BASENXP-001).

The Uart_Example_S32K344 fixture has:
  OsIfUseSystemTimer="false" and an empty <array name="OsIfCounterConfig"/>

The fixture Mcu config (McuClockSettingConfig_0) has two McuClockReferencePoints:
  - LPUART3_CLK (McuClockFrequencySelect=AIPS_SLOW_CLK)
  - FLEXIO_CLK  (McuClockFrequencySelect=CORE_CLK)

The case enables the system timer, inserts exactly one counter struct with
OsIfSystemTimerClockRef pointing to the CORE_CLK reference point (FLEXIO_CLK),
OsIfSystemTimerClockFreq as an empty array (ConfigTools ArraySetting type),
and verifies byte-narrowness and idempotency.
"""
import difflib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.apply import apply_basenxp_set
from rtd_config.intent import Intent
from tests.fixtures import copy_uart_fixture


def _intent(**payload) -> Intent:
    return Intent.from_dict({"module": "basenxp", "action": "set", "payload": payload})


def _asset_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "autombd-rtd"
        / "assets"
        / "nxp"
        / "s32k3"
        / "basenxp"
        / "osif.json"
    )


def _osif_cfg(doc: MexDocument) -> ET.Element | None:
    return doc.find_config_set("BaseNXP")


def _use_system_timer_value(doc: MexDocument) -> str | None:
    """Return the OsIfUseSystemTimer setting value from the loaded document."""
    cfg = _osif_cfg(doc)
    if cfg is None:
        return None
    setting = doc.find_child_setting(cfg, "OsIfUseSystemTimer")
    return setting.attrib.get("value") if setting is not None else None


def _counter_array(doc: MexDocument) -> ET.Element | None:
    cfg = _osif_cfg(doc)
    if cfg is None:
        return None
    for el in cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "OsIfCounterConfig":
            return el
    return None


def _counter_structs(doc: MexDocument) -> list[ET.Element]:
    arr = _counter_array(doc)
    if arr is None:
        return []
    return [c for c in arr if c.tag.endswith("struct")]


def _child_setting_value(doc: MexDocument, el: ET.Element, name: str) -> str | None:
    s = doc.find_child_setting(el, name)
    return s.attrib.get("value") if s is not None else None


def _changed_lines(before: bytes, after: bytes) -> list[str]:
    b = before.decode("utf-8").splitlines(keepends=True)
    a = after.decode("utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(b, a, n=0, lineterm="")
    return [
        line for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


# ---------------------------------------------------------------------------
# Forward surface coverage: osif.json must account for the BaseNXP.xdm surface.
# ---------------------------------------------------------------------------
def test_osif_json_asset_has_forward_surface_coverage():
    asset = json.loads(_asset_path().read_text(encoding="utf-8"))

    assert "BaseNXP.xdm" in asset["_source"]
    coverage = asset["_coverage"]

    configurable = coverage["configurable_today"]
    osif_general = configurable["OsIfGeneral"]
    for item in (
        "OsIfEnableUserModeSupport",
        "OsIfDevErrorDetect",
        "OsIfUseCustomTimer",
        "OsIfUseGetUserId",
        "OsIfInstanceId",
        "OsIfGetPhysicalCoreIdEnable",
        "OsIfSoftwareSemaphoredEnable",
        "OsIfUseSystemTimer",
        "OsIfCounterConfig",
    ):
        assert item in osif_general

    not_yet = coverage["not_yet_exposed"]
    assert "OsIfMulticoreSupport" in not_yet["multicore_partition_os"]
    assert "OsIfEcucPartitionRef" in not_yet["multicore_partition_os"]
    assert "OsIfOsCounterRef" in not_yet["autosar_os"]
    assert "CommonPublishedInformation" in not_yet["published_information"]

    assert asset["enum_domains"]["OsIfUseGetUserId"] == [
        "GET_CORE_ID",
        "GET_PARTITION_ID",
        "GET_CUSTOM_ID",
    ]
    assert asset["constraints"]["OsIfInstanceId"] == {
        "min": 0,
        "max": 255,
        "source_ref": "BaseNXP.xdm:OsIfGeneral/OsIfInstanceId INVALID Range",
    }


# ---------------------------------------------------------------------------
# Generality: arbitrary valid BaseNXP-owned OsIfGeneral values, not E2E literals.
# ---------------------------------------------------------------------------
def test_apply_sets_arbitrary_valid_osif_general_values(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    result = apply_basenxp_set(doc, _intent(
        user_mode_support=True,
        dev_error_detect=False,
        custom_timer=True,
        get_user_id="GET_CUSTOM_ID",
        instance_id=42,
        get_physical_core_id=True,
        software_semaphore=True,
    ))
    doc.write(mex)

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "basenxp" in result.changed_modules

    reloaded = MexDocument.load(mex)
    cfg = _osif_cfg(reloaded)
    assert cfg is not None
    assert _child_setting_value(reloaded, cfg, "OsIfEnableUserModeSupport") == "true"
    assert _child_setting_value(reloaded, cfg, "OsIfDevErrorDetect") == "false"
    assert _child_setting_value(reloaded, cfg, "OsIfUseCustomTimer") == "true"
    assert _child_setting_value(reloaded, cfg, "OsIfUseGetUserId") == "GET_CUSTOM_ID"
    assert _child_setting_value(reloaded, cfg, "OsIfInstanceId") == "42"
    assert _child_setting_value(reloaded, cfg, "OsIfGetPhysicalCoreIdEnable") == "true"
    assert _child_setting_value(reloaded, cfg, "OsIfSoftwareSemaphoredEnable") == "true"
    assert _use_system_timer_value(reloaded) == "false"
    assert len(_counter_structs(reloaded)) == 0


def test_apply_rejects_instance_id_outside_xdm_range(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    result = apply_basenxp_set(doc, _intent(instance_id=256))

    assert result.blocked
    assert [d.code for d in result.diagnostics] == ["basenxp_instance_id_out_of_range"]
    assert _child_setting_value(doc, _osif_cfg(doc), "OsIfInstanceId") == "0"


def test_cli_basenxp_set_general_osif_values_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "basenxp", "set",
            "--project", str(project),
            "--user-mode-support", "true",
            "--dev-error-detect", "false",
            "--custom-timer", "true",
            "--get-user-id", "custom",
            "--instance-id", "42",
            "--get-physical-core-id", "true",
            "--software-semaphore", "true",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert payload["status"] == "passed", payload

    reloaded = MexDocument.load(mex)
    cfg = _osif_cfg(reloaded)
    assert cfg is not None
    assert _child_setting_value(reloaded, cfg, "OsIfEnableUserModeSupport") == "true"
    assert _child_setting_value(reloaded, cfg, "OsIfDevErrorDetect") == "false"
    assert _child_setting_value(reloaded, cfg, "OsIfUseCustomTimer") == "true"
    assert _child_setting_value(reloaded, cfg, "OsIfUseGetUserId") == "GET_CUSTOM_ID"
    assert _child_setting_value(reloaded, cfg, "OsIfInstanceId") == "42"
    assert _child_setting_value(reloaded, cfg, "OsIfGetPhysicalCoreIdEnable") == "true"
    assert _child_setting_value(reloaded, cfg, "OsIfSoftwareSemaphoredEnable") == "true"


# ---------------------------------------------------------------------------
# Test 1: apply sets OsIfUseSystemTimer to true
# ---------------------------------------------------------------------------
def test_apply_sets_use_system_timer_true(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    result = apply_basenxp_set(doc, _intent(enable_system_timer=True))

    assert not result.blocked, [d.to_dict() for d in result.diagnostics]
    assert "basenxp" in result.changed_modules
    assert _use_system_timer_value(doc) == "true"


# ---------------------------------------------------------------------------
# Test 2: apply inserts exactly one well-formed counter struct
# ---------------------------------------------------------------------------
def test_apply_inserts_exactly_one_counter(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")

    apply_basenxp_set(doc, _intent(enable_system_timer=True))

    structs = _counter_structs(doc)
    assert len(structs) == 1, f"Expected 1 counter struct, got {len(structs)}"
    counter = structs[0]
    assert counter.attrib.get("name") == "0"


# ---------------------------------------------------------------------------
# Test 3: OsIfSystemTimerClockFreq must be an empty array (not a scalar setting).
#
# ConfigTools types OsIfSystemTimerClockFreq as ArraySetting. When a Mcu
# McuClockReferencePoint exists (as in this fixture), the correct pattern is
# OsIfSystemTimerClockRef populated + OsIfSystemTimerClockFreq as empty array.
# ---------------------------------------------------------------------------
def test_counter_has_correct_clock_freq(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    raw = mex.read_bytes().decode("utf-8")

    # OsIfSystemTimerClockFreq must be an empty array (never a scalar setting)
    assert '<array name="OsIfSystemTimerClockFreq"/>' in raw, (
        "OsIfSystemTimerClockFreq must be an empty array (ConfigTools type: "
        "ArraySetting); scalar <setting> causes vendor gate SEVERE"
    )
    assert '<setting name="OsIfSystemTimerClockFreq"' not in raw, (
        "OsIfSystemTimerClockFreq must NOT be a scalar <setting>"
    )


# ---------------------------------------------------------------------------
# Test 4: counter has Name=OsIfCounterConfig_0 and all required children.
#
# OsIfSystemTimerClockRef must be POPULATED (carries the Mcu ref path) when
# a McuClockReferencePoint exists in the project.  OsIfCounterEcucPartitionRef
# and OsIfOsCounterRef remain empty arrays.  OsIfSystemTimerClockFreq is an
# empty array (not a scalar).
# ---------------------------------------------------------------------------
def test_counter_has_required_children(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    raw = mex.read_bytes().decode("utf-8")
    doc2 = MexDocument.load(mex)
    counter = _counter_structs(doc2)[0]

    name_val = _child_setting_value(doc2, counter, "Name")
    assert name_val == "OsIfCounterConfig_0", f"Got: {name_val}"

    # All required array children must be present
    arr_names = {el.attrib.get("name") for el in counter if el.tag.endswith("array")}
    assert "OsIfCounterEcucPartitionRef" in arr_names, f"Missing OsIfCounterEcucPartitionRef; got {arr_names}"
    assert "OsIfSystemTimerClockRef" in arr_names, f"Missing OsIfSystemTimerClockRef; got {arr_names}"
    assert "OsIfSystemTimerClockFreq" in arr_names, f"Missing OsIfSystemTimerClockFreq array; got {arr_names}"
    assert "OsIfOsCounterRef" in arr_names, f"Missing OsIfOsCounterRef; got {arr_names}"

    # OsIfSystemTimerClockRef must be POPULATED (non-empty: has a child setting)
    assert '<array name="OsIfSystemTimerClockRef">' in raw, (
        "OsIfSystemTimerClockRef must be a populated (open/close) array, "
        "not self-closed, when a McuClockReferencePoint exists"
    )

    # OsIfSystemTimerClockFreq must be empty (self-closed)
    assert '<array name="OsIfSystemTimerClockFreq"/>' in raw, (
        "OsIfSystemTimerClockFreq must be an empty self-closed array"
    )


# ---------------------------------------------------------------------------
# Test 5: written file re-loads as well-formed XML
# ---------------------------------------------------------------------------
def test_written_file_is_well_formed(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    # Must reload without exception
    reloaded = MexDocument.load(mex)
    assert _use_system_timer_value(reloaded) == "true"


# ---------------------------------------------------------------------------
# Test 6: edit is byte-narrow (only OsIf flag line + OsIfCounterConfig region change)
# ---------------------------------------------------------------------------
def test_edit_is_byte_narrow(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    original = mex.read_bytes()

    doc = MexDocument.load(mex)
    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    changed = _changed_lines(original, mex.read_bytes())
    # Two changed regions:
    # 1. OsIfUseSystemTimer line (1 removal + 1 addition = 2 diff lines)
    # 2. OsIfCounterConfig region (1 removal of self-closed + N addition lines)
    # Total diff lines must be << a full-file reserialization (which churns ~3000 lines).
    # We allow up to 30 diff lines to cover the expanded array block.
    assert len(changed) <= 30, f"unexpectedly broad diff: {len(changed)} lines:\n" + "".join(changed)

    # The OsIfUseSystemTimer flip must appear
    added = [line for line in changed if line.startswith("+")]
    assert any('OsIfUseSystemTimer' in line and 'value="true"' in line for line in added), \
        "Missing OsIfUseSystemTimer=true in diff"

    # OsIfSystemTimerClockRef (populated) and OsIfSystemTimerClockFreq (empty array)
    # must both appear in the added diff lines
    assert any('OsIfSystemTimerClockRef' in line for line in added), \
        "Missing OsIfSystemTimerClockRef in diff"
    assert any('OsIfSystemTimerClockFreq' in line for line in added), \
        "Missing OsIfSystemTimerClockFreq in diff"

    # XML declaration and unrelated lines preserved
    after_lines = mex.read_bytes().decode("utf-8").splitlines()
    assert after_lines[0] == '<?xml version="1.0" encoding= "UTF-8" ?>'


# ---------------------------------------------------------------------------
# Test 7: idempotency -- running twice does not add a second counter
# ---------------------------------------------------------------------------
def test_idempotent_apply_does_not_add_second_counter(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"

    doc = MexDocument.load(mex)
    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    # Second apply on the already-modified file
    doc2 = MexDocument.load(mex)
    result2 = apply_basenxp_set(doc2, _intent(enable_system_timer=True))
    doc2.write(mex)

    assert not result2.blocked, [d.to_dict() for d in result2.diagnostics]
    doc3 = MexDocument.load(mex)
    structs = _counter_structs(doc3)
    assert len(structs) == 1, f"Idempotency failed: {len(structs)} counter structs after two applies"


# ---------------------------------------------------------------------------
# Test 9: OsIfSystemTimerClockFreq must NOT appear as a scalar <setting>;
#         OsIfSystemTimerClockRef must carry the dynamically-discovered Mcu path.
#
# ConfigTools defines OsIfSystemTimerClockFreq as an ArraySetting (log line:
#   "[SDK/DATA] ... type from the component definition: ArraySetting").
# All vendor examples store it as an empty <array name="OsIfSystemTimerClockFreq"/>
# when a Mcu clock reference is provided via OsIfSystemTimerClockRef.
# Writing it as <setting name="OsIfSystemTimerClockFreq" value="..."/> causes
# ConfigTools to ignore the value and still fire the SEVERE constraint:
#   "Either OsIfSystemTimerClockRef or OsIfSystemTimerClockFreq must be enabled".
#
# The Uart_Example_S32K344 fixture has two McuClockReferencePoints in
# McuClockSettingConfig_0:
#   - struct 0: LPUART3_CLK, McuClockFrequencySelect=AIPS_SLOW_CLK
#   - struct 1: FLEXIO_CLK,  McuClockFrequencySelect=CORE_CLK
# The dynamic ref discovery must prefer CORE_CLK -> FLEXIO_CLK.
# Expected ref path: /Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/FLEXIO_CLK
#
# Production gap: apply.py _build_counter_array_bytes() emits
#   <setting name="OsIfSystemTimerClockFreq" value="48000000"/>
# which is the wrong XML element type.  This test must fail on the current
# production code and pass only when the fix is in.
# ---------------------------------------------------------------------------
def test_counter_clock_config_uses_clock_ref_not_scalar_freq(tmp_path):
    """After apply, OsIfSystemTimerClockRef must carry the Mcu reference path
    (dynamically discovered, preferring CORE_CLK) and OsIfSystemTimerClockFreq
    must be an empty array — never a scalar setting.

    The Uart_Example_S32K344 fixture has FLEXIO_CLK with CORE_CLK as the
    preferred reference point; the expected ref path is:
    /Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/FLEXIO_CLK
    """
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    apply_basenxp_set(doc, _intent(enable_system_timer=True))
    doc.write(mex)

    # Re-read raw bytes and check serialization
    raw = mex.read_bytes().decode("utf-8")

    # OsIfSystemTimerClockFreq must appear as an empty array, not as a scalar setting
    assert '<array name="OsIfSystemTimerClockFreq"/>' in raw, (
        "OsIfSystemTimerClockFreq must be serialized as an empty array "
        "<array name=\"OsIfSystemTimerClockFreq\"/> (ConfigTools component definition "
        "type is ArraySetting; a scalar <setting> is silently rejected causing "
        "SEVERE: Either OsIfSystemTimerClockRef or OsIfSystemTimerClockFreq must "
        "be enabled in baremetal mode)"
    )

    # OsIfSystemTimerClockFreq must NOT appear as a scalar <setting>
    assert '<setting name="OsIfSystemTimerClockFreq"' not in raw, (
        "OsIfSystemTimerClockFreq must NOT be a scalar <setting>; "
        "ConfigTools rejects it as 'StoragePeriphsScalarSetting' vs expected 'ArraySetting'"
    )

    # OsIfSystemTimerClockRef must be an array carrying the Mcu path
    assert '<array name="OsIfSystemTimerClockRef">' in raw, (
        "OsIfSystemTimerClockRef must be a non-empty array carrying the Mcu "
        "McuClockReferencePoint path (as in every vendor example)"
    )

    # Dynamic ref discovery must prefer CORE_CLK -> FLEXIO_CLK in this fixture
    expected_ref = "/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/FLEXIO_CLK"
    assert expected_ref in raw, (
        f"OsIfSystemTimerClockRef must reference '{expected_ref}' "
        "(CORE_CLK reference point preferred; fixture has FLEXIO_CLK=CORE_CLK). "
        f"Actual file snippet around ClockRef: "
        f"{raw[max(0,raw.find('OsIfSystemTimerClockRef')-20):raw.find('OsIfSystemTimerClockRef')+200]}"
    )


# ---------------------------------------------------------------------------
# Test 10: blocker when no McuClockReferencePoint exists in the loaded document.
#
# The dynamic ref discovery helper is exercised directly by temporarily removing
# the Mcu config set from the tree.  The result must carry a blocker diagnostic
# with code 'basenxp_no_clock_reference_point' and NOT modify the file.
# ---------------------------------------------------------------------------
def test_no_clock_reference_point_returns_blocker(tmp_path):
    """apply_basenxp_set must return a blocker diagnostic when no
    McuClockReferencePoint can be found in the Mcu config set.
    """
    import xml.etree.ElementTree as ET
    from rtd_config.backends.s32_mex.apply import _find_mcu_clock_ref_path

    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)

    # Helper must return a tuple (path, None) or (None, Diagnostic)
    # When there are no McuClockReferencePoint structs, it returns (None, Diagnostic).
    # We can test _find_mcu_clock_ref_path directly with a stub config set that has
    # no McuClockReferencePoint array at all.
    #
    # Build a minimal stub Mcu config set with no clock ref points:
    stub = ET.fromstring(
        '<config_set name="Mcu">'
        '<array name="McuClockSettingConfig">'
        '<struct name="0">'
        '<setting name="Name" value="McuClockSettingConfig_0"/>'
        '<array name="McuClockReferencePoint"/>'  # empty — no children
        '</struct>'
        '</array>'
        '</config_set>'
    )
    path, diag = _find_mcu_clock_ref_path(doc, stub)
    assert path is None, f"Expected None path when no ref points exist; got {path}"
    assert diag is not None, "Expected a Diagnostic when no ref points exist"
    assert diag.code == "basenxp_no_clock_reference_point", f"Got code: {diag.code}"
    assert diag.severity == "blocker"


# ---------------------------------------------------------------------------
# Test 8: CLI integration -- basenxp set --enable-system-timer --configure returns passed
# ---------------------------------------------------------------------------
def test_cli_basenxp_set_configure(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "basenxp", "set",
            "--project", str(project),
            "--enable-system-timer",
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert payload["status"] == "passed", payload
    assert "basenxp" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
