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
# File:        test_project_metadata.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Unit tests for observed S32 .mex project metadata and conflicts.
# =================================================================================

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.metadata import (
    MetadataConflict,
    MetadataObservation,
    ModuleMetadata,
    ProjectMetadata,
    ToolMetadata,
    parse_project_metadata,
)
from rtd_config.backends.s32_mex.target import verify_project_target
from rtd_config.errors import CliFailure
from rtd_config.project import Project


FIXTURES = Path(__file__).parents[1] / "fixtures" / "nxp" / "ds" / "s32k3"
UART = FIXTURES / "Uart_Example_S32K344"
ADC = FIXTURES / "Autombd_Test_Adc_S32K344"


def _parse(root: Path, **kwargs) -> ProjectMetadata:
    with verify_project_target(root) as target:
        document = MexDocument.from_snapshot(target.mex)
        return parse_project_metadata(target, document, **kwargs)


def _reader(overrides: dict[str, bytes | Exception | None]):
    def read(relative: str):
        value = overrides.get(relative)
        if isinstance(value, Exception):
            raise value
        return value
    return read


def _minimal_mex(**values: str) -> bytes:
    processor = values.get("processor", "S32K344")
    package = values.get("package", "S32K344_257BGA")
    mcu_data = values.get("mcu_data", "PlatformSDK_S32K3")
    name = values.get("name", "S32K344")
    version = values.get("version", "19")
    namespace = values.get("namespace", "http://mcuxpresso.nxp.com/XSD/mex_configuration_19")
    schema = values.get("schema", f"{namespace} {namespace}.xsd")
    return f'''<?xml version="1.0"?>
<configuration xmlns="{namespace}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 name="{name}" version="{version}" xsi:schemaLocation="{schema}">
 <common><processor>{processor}</processor><package>{package}</package><mcu_data>{mcu_data}</mcu_data></common>
 <tools><pins name="Pins" version="17.0" enabled="true"/><clocks name="Clocks" version="19.0" enabled="false"/>
 <periphs name="Peripherals" version="15.0" enabled="true"><functional_groups><functional_group><instances>
 <instance name="Dio" type="Dio" type_id="Dio" mode="autosar" enabled="false"/>
 </instances></functional_group></functional_groups></periphs></tools></configuration>'''.encode()


def _temporary_project(tmp_path: Path, raw: bytes | None = None) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "sample.mex").write_bytes(raw or _minimal_mex())
    return root


def test_uart_fixture_metadata_is_observed_exactly():
    metadata = _parse(UART)

    assert (metadata.vendor, metadata.backend) == ("NXP", "s32-mex")
    assert (metadata.processor, metadata.family, metadata.device) == ("S32K344", "S32K3", "S32K344")
    assert (metadata.raw_package, metadata.package, metadata.mcu_data) == (
        "S32K344_257BGA", "mapbga257", "PlatformSDK_S32K3"
    )
    assert metadata.xml_namespace == "http://mcuxpresso.nxp.com/XSD/mex_configuration_19"
    assert metadata.schema_version == "19"
    assert metadata.schema_location.endswith("mex_configuration_19.xsd")
    assert metadata.rtd_release == "7.0.1"
    assert metadata.tools == (
        ToolMetadata("Pins", "17.0", True),
        ToolMetadata("Clocks", "19.0", True),
        ToolMetadata("Peripherals", "15.0", True),
    )
    assert [module.name for module in metadata.modules] == [
        "Mcl", "Uart", "Port", "BaseNXP", "Platform", "Mcu", "Dio"
    ]
    assert metadata.conflicts == ()


def test_uart_module_identity_and_published_profiles_are_exact():
    modules = {item.name: item for item in _parse(UART).modules}
    assert modules["BaseNXP"] == ModuleMetadata("BaseNXP", "BaseNXP", "Base", "general", "0", "4.7.0", "3.0.0", "43")
    assert modules["Uart"] == ModuleMetadata("Uart", "Uart", "Uart", "autosar", "255", "4.4.0", "2.0.0", "43")
    assert modules["Dio"].software_version == "7.0.1"
    assert modules["Mcl"].module_id is None and modules["Mcl"].software_version is None
    assert modules["Mcu"].autosar_version is None and modules["Mcu"].vendor_id is None


def test_adc_fixture_identity_and_profile_are_observed():
    metadata = _parse(ADC)
    modules = {item.name: item for item in metadata.modules}
    assert metadata.processor == metadata.device == "S32K344"
    assert metadata.package == "mapbga257"
    assert [item.name for item in metadata.modules] == ["BaseNXP", "Dio", "Port", "Mcu", "Adc", "Mcl", "Platform"]
    assert modules["Adc"] == ModuleMetadata("Adc", "Adc", "Adc", "autosar", "123", "4.9.0", "7.0.1", "43")
    assert metadata.rtd_release == "7.0.1"


def test_dio_software_version_is_not_used_as_rtd_release(tmp_path):
    root = _temporary_project(tmp_path)
    raw = (root / "sample.mex").read_bytes().replace(
        b'<instance name="Dio" type="Dio" type_id="Dio" mode="autosar" enabled="false"/>',
        b'<instance name="Dio" type="Dio" type_id="Dio" mode="autosar" enabled="true"><config_set><struct name="CommonPublishedInformation"><setting name="SwMajorVersion" value="7"/><setting name="SwMinorVersion" value="0"/><setting name="SwPatchVersion" value="1"/></struct></config_set></instance>'
    )
    (root / "sample.mex").write_bytes(raw)
    assert _parse(root).rtd_release is None


def test_missing_prefs_stay_unknown_and_do_not_use_runtime_defaults(tmp_path):
    metadata = _parse(_temporary_project(tmp_path))
    assert metadata.family == "S32K3"  # observed from mcu_data, not RuntimeConfig
    assert metadata.rtd_release is None
    assert metadata.processor == "S32K344"


@pytest.mark.parametrize(
    "field,raw,files",
    [
        ("processor", _minimal_mex(processor="S32K345"), {".cproject": b'<listOptionValue value="CPU_S32K344"/>'}),
        ("device", _minimal_mex(name="S32K345"), {".settings/com.nxp.s32ds.cle.runtime.component.prefs": b"com.nxp.s32ds.cle.runtime.hardware.registry.device.id=S32K344\n"}),
        ("family", _minimal_mex(mcu_data="PlatformSDK_S32K4"), {".settings/com.nxp.s32ds.cle.runtime.component.prefs": b"com.nxp.s32ds.cle.runtime.hardware.registry.family.id=S32K3\n"}),
        ("rtd_release", _minimal_mex(), {".settings/com.freescale.s32ds.cross.sdk.support.prefs": b"com.freescale.s32ds.cross.sdk.support.attachedSDKs=PlatformSDK_S32K3_S32K344_M7_7.0.1_PATH|X,PlatformSDK_S32K3_S32K344_M7_6.0.0_PATH|Y\n"}),
        ("schema_version", _minimal_mex(version="18"), {}),
    ],
)
def test_conflicting_observations_are_typed_blockers(tmp_path, field, raw, files):
    root = _temporary_project(tmp_path, raw)
    metadata = _parse(root, source_reader=_reader(files))
    assert field in {item.field for item in metadata.conflicts}
    with pytest.raises(CliFailure) as caught:
        metadata.require_consistent()
    assert caught.value.code == "project_metadata_conflict"
    assert caught.value.details["conflicts"]


def test_identical_duplicate_observations_are_deduplicated(tmp_path):
    root = _temporary_project(tmp_path)
    metadata = _parse(root, source_reader=_reader({
        ".cproject": b'<root><listOptionValue value="CPU_S32K344"/><listOptionValue value="CPU_S32K344"/></root>',
        ".settings/com.nxp.s32ds.cle.runtime.component.prefs": b"com.nxp.s32ds.cle.runtime.hardware.registry.device.id=S32K344\ncom.nxp.s32ds.cle.runtime.hardware.registry.family.id=S32K3\n",
    }))
    assert metadata.processor == metadata.device == "S32K344"
    assert metadata.conflicts == ()


def test_unknown_package_is_not_guessed(tmp_path):
    metadata = _parse(_temporary_project(tmp_path, _minimal_mex(package="S32K344_CUSTOM")))
    assert metadata.raw_package == "S32K344_CUSTOM"
    assert metadata.package is None


def test_disabled_tools_and_modules_are_excluded(tmp_path):
    metadata = _parse(_temporary_project(tmp_path))
    assert [tool.name for tool in metadata.tools] == ["Pins", "Peripherals"]
    assert metadata.modules == ()


@pytest.mark.parametrize(
    "payload,error,code",
    [
        (b"<broken", None, "project_metadata_source_invalid"),
        (b"x" * (1024 * 1024 + 1), None, "project_metadata_source_too_large"),
        (None, PermissionError(), "project_permission_denied"),
        (b"\xff", None, "project_metadata_source_encoding_invalid"),
        (None, RuntimeError("replaced"), "project_metadata_source_changed"),
    ],
    ids=["malformed", "oversize", "permission", "encoding", "replacement"],
)
def test_auxiliary_source_failures_are_typed(tmp_path, payload, error, code):
    root = _temporary_project(tmp_path)
    reader = _reader({".cproject": error or payload})
    with pytest.raises(CliFailure) as caught:
        _parse(root, source_reader=reader)
    assert caught.value.code == code


def test_default_reader_rejects_auxiliary_path_escape_and_reparse(monkeypatch, tmp_path):
    root = _temporary_project(tmp_path)
    settings = root / ".settings"
    settings.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(CliFailure) as caught:
        _parse(root)
    assert caught.value.code == "unsafe_project_path"


def test_metadata_value_objects_are_frozen():
    observation = MetadataObservation("device", "S32K344", ".mex", "/configuration/@name")
    conflict = MetadataConflict("device", (observation,))
    values = [ToolMetadata("Pins", "17.0", True), ModuleMetadata("Dio", "Dio", "Dio", "autosar", None, None, None, None), observation, conflict]
    for value in values:
        with pytest.raises(FrozenInstanceError):
            value.name = "changed" if hasattr(value, "name") else "changed"  # type: ignore[attr-defined]

    metadata = ProjectMetadata(None, None, None, None, None, None, None, None, None, None, None, (), (), None, ())
    with pytest.raises(FrozenInstanceError):
        metadata.device = "S32K344"  # type: ignore[misc]


def test_project_caches_document_and_metadata():
    with Project.verified(UART) as project:
        assert project.document is project.document
        assert project.metadata is project.metadata
        assert project.metadata.processor == "S32K344"


def test_inspect_reports_observed_metadata_not_runtime_defaults(capsys):
    assert cli.cmd_inspect(SimpleNamespace(project=UART)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["processor"] == "S32K344"
    assert payload["family"] == "S32K3"
    assert payload["raw_package"] == "S32K344_257BGA"
    assert payload["package"] == "mapbga257"
    assert payload["rtd_release"] == "7.0.1"
    assert payload["schema_version"] == "19"
    assert len(payload["modules"]) == 7
    assert "validation_profile" not in payload
