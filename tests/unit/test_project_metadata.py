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

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex import metadata as metadata_module
from rtd_config.backends.s32_mex import target as target_module
from rtd_config.backends.s32_mex.metadata import (
    MetadataConflict,
    MetadataObservation,
    ModuleMetadata,
    ProjectMetadata,
    ToolMetadata,
    parse_project_metadata,
)
from rtd_config.modules.registry import ProviderRegistry
from rtd_config.backends.s32_mex.target import verify_project_target
from rtd_config.errors import CliFailure
from rtd_config.project import Project
from tests.fixtures import copy_uart_fixture


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
    assert _parse(UART).modules == (
        ModuleMetadata("Mcl", "Mcl", "Mcl", "autosar", None, None, None, None),
        ModuleMetadata("Uart", "Uart", "Uart", "autosar", "255", "4.4.0", "2.0.0", "43"),
        ModuleMetadata("Port", "Port", "Port", "autosar", "124", "4.4.0", "2.0.0", "43"),
        ModuleMetadata("BaseNXP", "BaseNXP", "Base", "general", "0", "4.7.0", "3.0.0", "43"),
        ModuleMetadata("Platform", "Platform", "Platform", "autosar", "255", "4.7.0", "3.0.0", "43"),
        ModuleMetadata("Mcu", "Mcu", "Mcu", "autosar", None, None, None, None),
        ModuleMetadata("Dio", "Dio", "Dio", "autosar", "120", "4.9.0", "7.0.1", "43"),
    )


def test_adc_fixture_identity_and_profile_are_observed():
    metadata = _parse(ADC)
    assert (metadata.vendor, metadata.backend) == ("NXP", "s32-mex")
    assert (metadata.processor, metadata.family, metadata.device) == (
        "S32K344", "S32K3", "S32K344",
    )
    assert (metadata.raw_package, metadata.package, metadata.mcu_data) == (
        "S32K344_257BGA", "mapbga257", "PlatformSDK_S32K3",
    )
    assert metadata.xml_namespace == "http://mcuxpresso.nxp.com/XSD/mex_configuration_19"
    assert metadata.schema_version == "19"
    assert metadata.schema_location == (
        "http://mcuxpresso.nxp.com/XSD/mex_configuration_19 "
        "http://mcuxpresso.nxp.com/XSD/mex_configuration_19.xsd"
    )
    assert metadata.tools == (
        ToolMetadata("Pins", "17.0", True),
        ToolMetadata("Clocks", "19.0", True),
        ToolMetadata("Peripherals", "15.0", True),
    )
    assert metadata.modules == (
        ModuleMetadata("BaseNXP", "BaseNXP", "Base", "general", "0", "4.4.0", "2.0.0", "43"),
        ModuleMetadata("Dio", "Dio", "Dio", "autosar", "120", "4.7.0", "3.0.0", "43"),
        ModuleMetadata("Port", "Port", "Port", "autosar", "124", "4.7.0", "3.0.0", "43"),
        ModuleMetadata("Mcu", "Mcu", "Mcu", "autosar", None, None, None, None),
        ModuleMetadata("Adc", "Adc", "Adc", "autosar", "123", "4.9.0", "7.0.1", "43"),
        ModuleMetadata("Mcl", "Mcl", "Mcl", "autosar", None, None, None, None),
        ModuleMetadata("Platform", "Platform", "Platform", "autosar", "255", "4.9.0", "7.0.1", "43"),
    )
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


def test_missing_observations_remain_unknown(tmp_path):
    raw = b'''<?xml version="1.0"?>
<configuration xmlns="urn:unrecognized" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
 <common/><tools/>
</configuration>'''
    metadata = _parse(_temporary_project(tmp_path, raw))
    assert (
        metadata.vendor, metadata.backend, metadata.processor, metadata.family,
        metadata.device, metadata.raw_package, metadata.package, metadata.mcu_data,
        metadata.xml_namespace, metadata.schema_version, metadata.schema_location,
        metadata.tools, metadata.modules, metadata.rtd_release, metadata.conflicts,
    ) == (
        None, None, None, None, None, None, None, None,
        "urn:unrecognized", None, None, (), None, None, (),
    )
    assert all(not item.observed for item in metadata.auxiliary_sources)


@pytest.mark.parametrize(
    "field,raw,files",
    [
        ("processor", _minimal_mex(processor="S32K345"), {".cproject": b'<listOptionValue value="CPU_S32K344"/>'}),
        ("device", _minimal_mex(name="S32K345"), {".settings/com.nxp.s32ds.cle.runtime.component.prefs": b"com.nxp.s32ds.cle.runtime.hardware.registry.device.id=S32K344\n"}),
        ("family", _minimal_mex(mcu_data="PlatformSDK_S32K4"), {".settings/com.nxp.s32ds.cle.runtime.component.prefs": b"com.nxp.s32ds.cle.runtime.hardware.registry.family.id=S32K3\n"}),
        ("rtd_release", _minimal_mex(), {".settings/com.freescale.s32ds.cross.sdk.support.prefs": b"com.freescale.s32ds.cross.sdk.support.attachedSDKs=PlatformSDK_S32K3_S32K344_M7_7.0.1_PATH|X,PlatformSDK_S32K3_S32K344_M7_6.0.0_PATH|Y\n"}),
        ("schema_version", _minimal_mex(version="18"), {}),
        ("schema_version", _minimal_mex(schema="urn:x mex_configuration_18.xsd"), {}),
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


def test_default_reader_does_not_follow_fixed_source_symlink(tmp_path):
    root = _temporary_project(tmp_path)
    outside = tmp_path / "outside.cproject"
    outside.write_text("<cproject/>", encoding="utf-8")
    (root / ".cproject").symlink_to(outside)
    with pytest.raises(CliFailure) as caught:
        _parse(root)
    assert caught.value.code == "unsafe_project_path"


@pytest.mark.parametrize(
    "content,code",
    [
        (b"x" * (1024 * 1024 + 1), "project_metadata_source_too_large"),
        (b"\xff", "project_metadata_source_encoding_invalid"),
    ],
    ids=["oversize", "encoding"],
)
def test_default_reader_rejects_invalid_fixed_source_content(tmp_path, content, code):
    root = _temporary_project(tmp_path)
    (root / ".cproject").write_bytes(content)
    with pytest.raises(CliFailure) as caught:
        _parse(root)
    assert caught.value.code == code


def test_default_reader_detects_fixed_source_replacement(monkeypatch, tmp_path):
    root = _temporary_project(tmp_path)
    (root / ".cproject").write_text("<cproject/>", encoding="utf-8")
    reader_name = "_read_windows_relative" if os.name == "nt" else "_read_posix_relative"
    monkeypatch.setattr(
        target_module, reader_name,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("replaced")),
    )
    with pytest.raises(CliFailure) as caught:
        _parse(root)
    assert caught.value.code == "project_metadata_source_changed"


def test_fixed_source_reader_rejects_unlisted_paths(tmp_path):
    root = _temporary_project(tmp_path)
    with verify_project_target(root) as target:
        reader = metadata_module._safe_source_reader(target)
        with pytest.raises(ValueError, match="unsupported metadata source"):
            reader("arbitrary.txt")


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


def test_metadata_to_dict_returns_detached_nested_values():
    observation = MetadataObservation("device", "S32K344", ".mex", "/configuration/@name")
    metadata = ProjectMetadata(
        "NXP", "s32-mex", "S32K344", "S32K3", "S32K344",
        "S32K344_257BGA", "mapbga257", "PlatformSDK_S32K3",
        "http://mcuxpresso.nxp.com/XSD/mex_configuration_19", "19",
        (
            "http://mcuxpresso.nxp.com/XSD/mex_configuration_19 "
            "http://mcuxpresso.nxp.com/XSD/mex_configuration_19.xsd"
        ),
        (ToolMetadata("Pins", "17.0", True),),
        (ModuleMetadata("Mcl", "Mcl", "Mcl", "autosar", "101", "4.7.0", "7.0.1", "43"),),
        "7.0.1",
        (MetadataConflict("device", (observation,)),),
    )
    first = metadata.to_dict()
    first["tools"][0]["name"] = "mutated"
    first["modules"][0]["name"] = "mutated"
    first["conflicts"][0]["field"] = "mutated"
    first["conflicts"][0]["observations"][0]["value"] = "mutated"
    first["conflicts"].append({"field": "appended"})

    second = metadata.to_dict()
    assert metadata.tools[0].name == second["tools"][0]["name"] == "Pins"
    assert metadata.modules[0].name == second["modules"][0]["name"] == "Mcl"
    assert second["conflicts"] == [{
        "field": "device",
        "observations": [{
            "field": "device",
            "value": "S32K344",
            "source": ".mex",
            "xpath": "/configuration/@name",
        }],
    }]


def test_metadata_records_complete_evidence_for_all_fixed_auxiliary_sources():
    metadata = _parse(UART)
    expected_relatives = [
        ".project", ".cproject",
        ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
        ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
    ]
    assert [item.relative for item in metadata.auxiliary_sources] == expected_relatives
    for evidence, relative in zip(metadata.auxiliary_sources, expected_relatives):
        expected_path = UART / relative
        expected_content = expected_path.read_bytes()
        snapshot = evidence.snapshot
        assert evidence.observed is True
        assert snapshot is not None
        assert snapshot.path == expected_path
        assert snapshot.size == len(expected_content)
        assert snapshot.mtime_ns > 0
        assert snapshot.ctime_ns > 0
        assert snapshot.sha256 == hashlib.sha256(expected_content).hexdigest()
        assert snapshot.content == expected_content
        assert (
            snapshot.identity.device is not None
            and snapshot.identity.inode is not None
        ) or snapshot.identity.windows_file_id is not None
    payload = metadata.to_dict()
    assert "auxiliary_sources" not in payload
    assert "sha256" not in json.dumps(payload)


@pytest.mark.parametrize("changed_relative", [
    ".project", ".cproject",
    ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
    ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
])
def test_parse_revalidates_all_auxiliary_sources_as_one_generation(
    monkeypatch, tmp_path, changed_relative
):
    root = _temporary_project(tmp_path)
    changed_source = root / changed_relative
    changed_source.parent.mkdir(parents=True, exist_ok=True)
    is_xml = changed_source.suffix == ".project" or changed_source.name in {
        ".project", ".cproject"
    }
    changed_source.write_text("<initial/>" if is_xml else "initial", encoding="utf-8")
    real_read = metadata_module.snapshot_project_relative
    calls = 0

    def mutate_after_initial_reads(target, relative, *, max_bytes):
        nonlocal calls
        result = real_read(target, relative, max_bytes=max_bytes)
        calls += 1
        if calls == 4:
            changed_source.write_text(
                "<changed/>" if is_xml else "changed", encoding="utf-8"
            )
        return result

    monkeypatch.setattr(metadata_module, "snapshot_project_relative", mutate_after_initial_reads)
    with pytest.raises(CliFailure) as caught:
        _parse(root)
    assert caught.value.code == "project_metadata_source_changed"


@pytest.mark.parametrize("changed_relative", [
    ".project", ".cproject",
    ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
    ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
])
def test_metadata_revalidation_rejects_same_bytes_new_identity(
    tmp_path, changed_relative
):
    root = copy_uart_fixture(tmp_path)
    with Project.verified(root) as project:
        metadata = project.metadata
        source = project.root / changed_relative
        replacement = source.with_name(f"{source.name}.replacement")
        replacement.write_bytes(source.read_bytes())
        os.replace(replacement, source)
        with pytest.raises(CliFailure) as caught:
            metadata_module.revalidate_project_metadata(project.verified_target, metadata)
    assert caught.value.code == "project_metadata_source_changed"


@pytest.mark.parametrize(
    "field,expected_missing",
    [
        ("vendor", {"vendor"}),
        ("backend", {"backend"}),
        ("processor", {"processor"}),
        ("family", {"family"}),
        ("device", {"device"}),
        ("raw_package", {"raw_package"}),
        ("package", {"package"}),
        ("mcu_data", {"mcu_data"}),
        ("xml_namespace", {"xml_namespace", "schema_identity"}),
        ("schema_version", {"schema_version", "schema_identity"}),
        ("schema_location", {"schema_location", "schema_identity"}),
        ("tools", {"tools"}),
        ("modules", {"modules"}),
        ("rtd_release", {"rtd_release"}),
    ],
)
def test_require_identity_reports_every_missing_metadata_boundary(
    field, expected_missing
):
    metadata = _parse(UART)

    with pytest.raises(CliFailure) as caught:
        replace(metadata, **{field: None}).require_identity()

    assert caught.value.code == "project_metadata_unknown"
    assert set(caught.value.details["missing_fields"]) == expected_missing


def test_require_identity_reports_invalid_schema_identity_without_missing_sources():
    metadata = _parse(UART)

    with pytest.raises(CliFailure) as caught:
        replace(metadata, schema_location="https://example.invalid/schema.xsd").require_identity()

    assert caught.value.code == "project_metadata_unknown"
    assert tuple(caught.value.details["missing_fields"]) == ("schema_identity",)


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
    assert payload["validation_profile"] == "uart"


@pytest.mark.parametrize("flow", ["inspect", "check", "validate", "configure"])
def test_public_project_flows_reject_metadata_conflicts_before_work(
    monkeypatch, tmp_path, flow
):
    root = _temporary_project(tmp_path)
    (root / ".cproject").write_text(
        '<root><listOptionValue value="CPU_S32K345"/></root>',
        encoding="utf-8",
    )
    args = SimpleNamespace(project=root)

    if flow == "inspect":
        invoke = lambda: cli.cmd_inspect(args)
    elif flow == "check":
        monkeypatch.setattr(
            cli, "run_static_checks",
            lambda *_args, **_kwargs: pytest.fail("static checks ran after conflict"),
        )
        invoke = lambda: cli.cmd_check(args)
    elif flow == "validate":
        monkeypatch.setattr(
            cli, "run_static_checks",
            lambda *_args, **_kwargs: pytest.fail("static checks ran after conflict"),
        )
        args = SimpleNamespace(
            project=root, s32ds_root=None, workspace=None, sdk_path=None,
        )
        invoke = lambda: cli.cmd_validate(args)
    else:
        apply_fn = lambda *_args: pytest.fail("apply ran after conflict")
        args = SimpleNamespace(project=root, backup=False)
        intent = SimpleNamespace(module="uart", action="set", payload={})
        plan = SimpleNamespace(to_dict=lambda: {})
        invoke = lambda: cli._configure_module(args, intent, plan, apply_fn)

    with pytest.raises(CliFailure) as caught:
        invoke()
    assert caught.value.code == "project_metadata_conflict"


def test_schema_location_evil_domain_is_a_blocking_identity_conflict(tmp_path):
    raw = _minimal_mex(schema="https://evil.example/mex_configuration_19 https://evil.example/mex_configuration_19.xsd")
    metadata = _parse(_temporary_project(tmp_path, raw))
    assert any(item.field == "schema_identity" for item in metadata.conflicts)
    with pytest.raises(CliFailure, match="disagree"):
        metadata.require_consistent()


def test_common_identity_ignores_same_named_descendant_before_direct_common(tmp_path):
    raw = _minimal_mex().replace(
        b"<common>", b"<other><processor>S32K999</processor></other><common>",
    )
    metadata = _parse(_temporary_project(tmp_path, raw))
    assert metadata.processor == "S32K344"
    assert not any(item.field == "processor" for item in metadata.conflicts)


def test_sdk_attachment_parser_ignores_comments_and_unrelated_properties(tmp_path):
    root = _temporary_project(tmp_path)
    metadata = _parse(root, source_reader=_reader({
        ".settings/com.freescale.s32ds.cross.sdk.support.prefs": (
            b"# PlatformSDK_S32K9_S32K999_M7_9.9.9_PATH\n"
            b"unrelated=PlatformSDK_S32K8_S32K888_M7_8.8.8_PATH\n"
        ),
    }))
    assert metadata.rtd_release is None
    assert metadata.family == "S32K3"


def test_missing_and_empty_tool_module_carriers_are_distinct(tmp_path):
    missing = _parse(_temporary_project(tmp_path, _minimal_mex().replace(b"<tools>", b"<not_tools>").replace(b"</tools>", b"</not_tools>")))
    assert missing.tools is None and missing.modules is None
    assert missing.tools_observed is False and missing.modules_observed is False

    empty_raw = _minimal_mex().replace(
        b'<pins name="Pins" version="17.0" enabled="true"/>', b"",
    ).replace(
        b'<clocks name="Clocks" version="19.0" enabled="false"/>', b"",
    ).replace(
        b'<periphs name="Peripherals" version="15.0" enabled="true"><functional_groups><functional_group><instances>\n <instance name="Dio" type="Dio" type_id="Dio" mode="autosar" enabled="false"/>\n </instances></functional_group></functional_groups></periphs>',
        b'<periphs name="Peripherals" version="15.0" enabled="false"><functional_groups><functional_group><instances/></functional_group></functional_groups></periphs>',
    )
    empty_parent = tmp_path / "empty"
    empty_parent.mkdir()
    empty = _parse(_temporary_project(empty_parent, empty_raw))
    assert empty.tools == () and empty.tools_observed is True
    assert empty.modules == () and empty.modules_observed is True


def test_module_plan_preflights_metadata_before_provider(monkeypatch, tmp_path):
    root = _temporary_project(tmp_path)
    (root / ".cproject").write_text('<root><listOptionValue value="CPU_S32K345"/></root>', encoding="utf-8")
    provider_called = False

    class Provider:
        name = "uart"

        def __init__(self, _bundle):
            pass

        def plan(self, _intent):
            nonlocal provider_called
            provider_called = True
            pytest.fail("provider planned before metadata preflight")

    registry = cli.get_provider_registry()
    current = registry.lookup_shortcut("uart", "set")
    replacement = replace(current, provider_type=Provider)
    monkeypatch.setattr(
        cli,
        "_PROVIDER_REGISTRY",
        ProviderRegistry(
            replacement if binding.key == current.key else binding
            for binding in registry._bindings.values()
        ),
    )
    with pytest.raises(CliFailure) as caught:
        cli.cmd_uart_set(SimpleNamespace(project=root, configure=False))
    assert caught.value.code == "project_metadata_conflict"
    assert not provider_called


def test_inspect_reports_resolved_compatibility_profile(capsys):
    assert cli.cmd_inspect(SimpleNamespace(project=UART)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["validation_profile"] == "uart"
    assert payload["compatibility"]["status"] == "passed"
    assert payload["compatibility"]["diagnostics"]


def test_project_relative_reader_uses_live_target_lease(tmp_path):
    root = _temporary_project(tmp_path)
    (root / ".settings").mkdir()
    source = ".settings/com.example.prefs"
    (root / source).write_bytes(b"key=value\n")
    with verify_project_target(root) as target:
        assert target_module.read_project_relative(target, source, max_bytes=64) == b"key=value\n"
    with pytest.raises(CliFailure) as caught:
        target_module.read_project_relative(target, source, max_bytes=64)
    assert caught.value.code == "project_target_closed"


@pytest.mark.parametrize("root", [UART, ADC], ids=["uart", "adc"])
def test_real_fixture_identity_is_complete_and_self_consistent(root):
    """Both committed vendor fixtures satisfy the strict planning preflight."""
    metadata = _parse(root)
    assert metadata.require_identity() is metadata
    assert metadata.conflicts == ()
    assert metadata.tools_observed is True
    assert metadata.modules_observed is True


@pytest.mark.parametrize(
    "schema",
    [
        "http://mcuxpresso.nxp.com/XSD/mex_configuration_19",
        (
            "http://mcuxpresso.nxp.com/XSD/mex_configuration_19 "
            "http://mcuxpresso.nxp.com/XSD/mex_configuration_19.xsd extra"
        ),
        (
            "http://mcuxpresso.nxp.com/XSD/mex_configuration_19 "
            "http://mcuxpresso.nxp.com/XSD/mex_configuration_19.xsd "
            "https://evil.example/mex_configuration_19 "
            "https://evil.example/mex_configuration_19.xsd"
        ),
    ],
    ids=["odd-token-count", "trailing-token", "additional-pair"],
)
def test_schema_location_requires_one_exact_official_pair(tmp_path, schema):
    metadata = _parse(_temporary_project(tmp_path, _minimal_mex(schema=schema)))
    assert {item.field for item in metadata.conflicts} >= {"schema_identity"}
    with pytest.raises(CliFailure) as caught:
        metadata.require_consistent()
    assert caught.value.code == "project_metadata_conflict"


def test_namespace_prefix_spoof_is_not_an_observed_nxp_identity(tmp_path):
    namespace = "http://mcuxpresso.nxp.com/XSD/mex_configuration_19.evil"
    root = _temporary_project(
        tmp_path,
        _minimal_mex(namespace=namespace, schema=f"{namespace} {namespace}.xsd"),
    )
    metadata = _parse(root, source_reader=_reader({
        ".settings/com.freescale.s32ds.cross.sdk.support.prefs": (
            b"com.freescale.s32ds.cross.sdk.support.attachedSDKs="
            b"PlatformSDK_S32K3_S32K344_M7_7.0.1_PATH|X\n"
        ),
    }))
    assert metadata.vendor is None
    assert metadata.backend is None
    with pytest.raises(CliFailure) as caught:
        metadata.require_identity()
    assert caught.value.code in {"project_metadata_conflict", "project_metadata_unknown"}


def test_official_namespace_on_foreign_root_is_not_an_observed_nxp_identity(tmp_path):
    raw = _minimal_mex().replace(
        b"<configuration xmlns=",
        b"<not_configuration xmlns=",
        1,
    ).replace(b"</configuration>", b"</not_configuration>", 1)
    metadata = _parse(_temporary_project(tmp_path, raw))
    assert metadata.vendor is None
    assert metadata.backend is None
    with pytest.raises(CliFailure) as caught:
        metadata.require_identity()
    assert caught.value.code in {"project_metadata_conflict", "project_metadata_unknown"}


def test_identity_fields_require_direct_children_of_direct_common(tmp_path):
    raw = _minimal_mex().replace(
        b"<common><processor>S32K344</processor><package>S32K344_257BGA</package><mcu_data>PlatformSDK_S32K3</mcu_data></common>",
        (
            b'<common><wrapper><processor>S32K345</processor>'
            b'<package>S32K345_CUSTOM</package><mcu_data>PlatformSDK_S32K4</mcu_data>'
            b'</wrapper><processor>S32K344</processor><package>S32K344_257BGA</package>'
            b'<mcu_data>PlatformSDK_S32K3</mcu_data></common>'
        ),
    )
    metadata = _parse(_temporary_project(tmp_path, raw))
    assert (metadata.processor, metadata.raw_package, metadata.mcu_data) == (
        "S32K344", "S32K344_257BGA", "PlatformSDK_S32K3",
    )
    assert metadata.conflicts == ()


def test_foreign_namespace_carriers_do_not_publish_tools_or_modules(tmp_path):
    raw = _minimal_mex().replace(
        b'<tools>',
        b'<tools xmlns:evil="https://evil.example/schema">',
    ).replace(
        b'<periphs name="Peripherals"',
        b'<evil:periphs name="Peripherals"',
    ).replace(b'</periphs>', b'</evil:periphs>')
    metadata = _parse(_temporary_project(tmp_path, raw))
    assert metadata.modules is None
    assert all(item.name != "Peripherals" for item in metadata.tools or ())


def test_sdk_attachment_accepts_only_trimmed_exact_property_key(tmp_path):
    root = _temporary_project(tmp_path)
    metadata = _parse(root, source_reader=_reader({
        ".settings/com.freescale.s32ds.cross.sdk.support.prefs": (
            b"  com.freescale.s32ds.cross.sdk.support.attachedSDKs  =  "
            b"PlatformSDK_S32K3_S32K344_M7_7.0.1_PATH|X  \n"
            b"com.example.com.freescale.s32ds.cross.sdk.support.attachedSDKs="
            b"PlatformSDK_S32K9_S32K999_M7_9.9.9_PATH|Y\n"
        ),
    }))
    assert (metadata.family, metadata.device, metadata.rtd_release) == (
        "S32K3", "S32K344", "7.0.1",
    )
    assert metadata.conflicts == ()


@pytest.mark.parametrize(
    "tools_fragment,expected_tools,expected_modules",
    [
        (b"", None, None),
        (b"<tools/>", (), None),
        (b'<tools><pins name="Pins" enabled="false"/></tools>', (), None),
        (
            b'<tools><periphs name="Peripherals" enabled="false"/></tools>',
            (), (),
        ),
    ],
    ids=["missing-tools", "empty-tools", "disabled-tool", "disabled-peripherals"],
)
def test_tool_and_module_observation_boundaries(
    tmp_path, tools_fragment, expected_tools, expected_modules
):
    raw = _minimal_mex()
    start = raw.index(b"<tools>")
    end = raw.index(b"</tools>") + len(b"</tools>")
    metadata = _parse(_temporary_project(tmp_path, raw[:start] + tools_fragment + raw[end:]))
    assert metadata.tools == expected_tools
    assert metadata.modules == expected_modules
    payload = metadata.to_dict()
    assert payload["tools_observed"] is (expected_tools is not None)
    assert payload["modules_observed"] is (expected_modules is not None)


@pytest.mark.parametrize(
    "command_name,normalizer_name,provider_name",
    [
        ("cmd_uart_set", "normalize_uart_intent", "UartProvider"),
        ("cmd_uart_add_flexio_channel", "normalize_uart_add_flexio_intent", "UartProvider"),
        ("cmd_platform_set", "normalize_platform_intent", "PlatformProvider"),
        ("cmd_basenxp_set", "normalize_basenxp_intent", "BaseNxpProvider"),
        ("cmd_mcl_set", "normalize_mcl_intent", "MclProvider"),
        ("cmd_port_set", "normalize_port_intent", "PortProvider"),
        ("cmd_dio_set", "normalize_dio_intent", "DioProvider"),
        ("cmd_mcu_set", "normalize_mcu_intent", "McuProvider"),
        ("cmd_adc_set", "normalize_adc_intent", "AdcProvider"),
    ],
)
def test_every_module_plan_requires_complete_observed_identity(
    monkeypatch, tmp_path, command_name, normalizer_name, provider_name
):
    root = _temporary_project(tmp_path)
    provider_called = False

    class Provider:
        def __init__(self, _bundle):
            pass

        def plan(self, _intent):
            nonlocal provider_called
            provider_called = True
            pytest.fail("provider planned before complete metadata identity")

    del normalizer_name, provider_name
    stem = command_name.removeprefix("cmd_")
    if stem == "uart_add_flexio_channel":
        module, cli_action = "uart", "add-flexio-channel"
    else:
        module, cli_action = stem.removesuffix("_set"), "set"
    Provider.name = module
    registry = cli.get_provider_registry()
    current = registry.lookup_shortcut(module, cli_action)
    replacement = replace(current, provider_type=Provider)
    monkeypatch.setattr(
        cli,
        "_PROVIDER_REGISTRY",
        ProviderRegistry(
            replacement if binding.key == current.key else binding
            for binding in registry._bindings.values()
        ),
    )
    with pytest.raises(CliFailure) as caught:
        getattr(cli, command_name)(SimpleNamespace(project=root, configure=False))
    assert caught.value.code == "project_metadata_unknown"
    assert "rtd_release" in caught.value.details["missing_fields"]
    assert provider_called is False


@pytest.mark.parametrize("root", [UART, ADC], ids=["uart", "adc"])
def test_inspect_resolved_compatibility_contract_on_real_fixtures(capsys, root):
    assert cli.cmd_inspect(SimpleNamespace(project=root)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["validation_profile"] in {"uart", "adc"}
    assert payload["compatibility"] == {
        "status": "passed",
        "diagnostics": [{
            "severity": "info",
            "code": "asset_bundle_resolved",
            "module": "backend",
            "message": "Exact project asset compatibility is verified.",
        }],
    }


def test_project_relative_reader_boundary_contract(tmp_path):
    root = _temporary_project(tmp_path)
    (root / "empty.txt").write_bytes(b"")
    (root / "one.txt").write_bytes(b"x")
    with verify_project_target(root) as target:
        assert target_module.read_project_relative(target, "missing.txt", max_bytes=1) is None
        assert target_module.read_project_relative(target, "empty.txt", max_bytes=0) == b""
        with pytest.raises(CliFailure) as caught:
            target_module.read_project_relative(target, "one.txt", max_bytes=0)
        assert caught.value.code == "project_metadata_source_too_large"
        for relative in ("", ".", "..", "a//b", "a/../b", r"a\b"):
            with pytest.raises(ValueError):
                target_module.read_project_relative(target, relative, max_bytes=1)
