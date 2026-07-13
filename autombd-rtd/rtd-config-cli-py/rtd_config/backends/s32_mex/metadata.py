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
# File:        metadata.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Parse observed S32 .mex project identity and source conflicts.
# =================================================================================

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
from typing import Any
import xml.etree.ElementTree as ET

from ...errors import CliFailure
from .document import MexDocument
from .target import VerifiedProjectTarget


_NXP_NAMESPACE_PREFIX = "http://mcuxpresso.nxp.com/XSD/mex_configuration_"
_XSI_SCHEMA_LOCATION = "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation"
_MAX_SOURCE_BYTES = 1024 * 1024
_AUXILIARY_SOURCES = (
    ".project",
    ".cproject",
    ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
    ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
)
DEFAULT_PACKAGE_ALIASES = {"S32K344_257BGA": "mapbga257"}
SourceReader = Callable[[str], bytes | None]


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    version: str | None
    enabled: bool


@dataclass(frozen=True)
class ModuleMetadata:
    name: str
    type: str | None
    type_id: str | None
    mode: str | None
    module_id: str | None
    autosar_version: str | None
    software_version: str | None
    vendor_id: str | None


@dataclass(frozen=True)
class MetadataObservation:
    field: str
    value: str
    source: str
    xpath: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "value": self.value, "source": self.source, "xpath": self.xpath}


@dataclass(frozen=True)
class MetadataConflict:
    field: str
    observations: tuple[MetadataObservation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "observations": [item.to_dict() for item in self.observations]}


@dataclass(frozen=True)
class ProjectMetadata:
    vendor: str | None
    backend: str | None
    processor: str | None
    family: str | None
    device: str | None
    raw_package: str | None
    package: str | None
    mcu_data: str | None
    xml_namespace: str | None
    schema_version: str | None
    schema_location: str | None
    tools: tuple[ToolMetadata, ...]
    modules: tuple[ModuleMetadata, ...]
    rtd_release: str | None
    conflicts: tuple[MetadataConflict, ...]

    def require_consistent(self) -> "ProjectMetadata":
        if self.conflicts:
            raise CliFailure(
                "project_metadata_conflict",
                "Project metadata sources disagree; resolve the conflicts before continuing.",
                module="backend",
                details={"conflicts": [item.to_dict() for item in self.conflicts]},
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor, "backend": self.backend,
            "processor": self.processor, "family": self.family, "device": self.device,
            "raw_package": self.raw_package, "package": self.package, "mcu_data": self.mcu_data,
            "xml_namespace": self.xml_namespace, "schema_version": self.schema_version,
            "schema_location": self.schema_location,
            "tools": [item.__dict__ for item in self.tools],
            "modules": [item.__dict__ for item in self.modules],
            "rtd_release": self.rtd_release,
            "conflicts": [item.to_dict() for item in self.conflicts],
        }


class _Observations:
    def __init__(self) -> None:
        self._items: dict[str, list[MetadataObservation]] = {}

    def add(self, field: str, value: str | None, source: str, xpath: str) -> None:
        normalized = _normalize(field, value)
        if normalized is None:
            return
        item = MetadataObservation(field, normalized, source, xpath)
        bucket = self._items.setdefault(field, [])
        if item not in bucket:
            bucket.append(item)

    def resolve(self, field: str) -> tuple[str | None, MetadataConflict | None]:
        items = tuple(self._items.get(field, ()))
        distinct = {item.value for item in items}
        if not distinct:
            return None, None
        if len(distinct) == 1:
            return next(iter(distinct)), None
        return None, MetadataConflict(field, items)


def _normalize(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    result = value.strip()
    if not result:
        return None
    if field in {"processor", "device"}:
        result = re.sub(r"^CPU_", "", result, flags=re.IGNORECASE).upper()
    elif field == "family":
        result = result.upper()
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _root_namespace(root: ET.Element) -> str | None:
    match = re.match(r"^\{([^}]+)\}", root.tag)
    return match.group(1) if match else None


def _text_child(root: ET.Element, name: str) -> str | None:
    for item in root.iter():
        if _local_name(item.tag) == name:
            return item.text
    return None


def _version(settings: Mapping[str, str], prefix: str) -> str | None:
    values = tuple(settings.get(prefix + suffix) for suffix in ("MajorVersion", "MinorVersion", "RevisionVersion" if prefix == "ArRelease" else "PatchVersion"))
    return ".".join(values) if all(value is not None for value in values) else None


def _parse_tools(root: ET.Element) -> tuple[ToolMetadata, ...]:
    tools = next((item for item in root.iter() if _local_name(item.tag) == "tools"), None)
    if tools is None:
        return ()
    result = []
    for item in tools:
        if item.attrib.get("enabled", "true").lower() != "true":
            continue
        name = item.attrib.get("name")
        if name:
            result.append(ToolMetadata(name, item.attrib.get("version"), True))
    return tuple(result)


def _parse_modules(root: ET.Element) -> tuple[ModuleMetadata, ...]:
    modules = []
    for item in root.iter():
        if _local_name(item.tag) != "instance" or item.attrib.get("enabled", "true").lower() != "true":
            continue
        name = item.attrib.get("name")
        if not name:
            continue
        published = next((child for child in item.iter() if child.attrib.get("name") == "CommonPublishedInformation"), None)
        settings: dict[str, str] = {}
        if published is not None:
            settings = {
                child.attrib["name"]: child.attrib["value"]
                for child in published.iter()
                if _local_name(child.tag) == "setting" and "name" in child.attrib and "value" in child.attrib
            }
        modules.append(ModuleMetadata(
            name, item.attrib.get("type"), item.attrib.get("type_id"), item.attrib.get("mode"),
            settings.get("ModuleId"), _version(settings, "ArRelease"),
            _version(settings, "Sw"), settings.get("VendorId"),
        ))
    return tuple(modules)


def _safe_source_reader(target: VerifiedProjectTarget) -> SourceReader:
    root = target.root

    def read(relative: str) -> bytes | None:
        if relative not in _AUXILIARY_SOURCES:
            raise ValueError(f"unsupported metadata source: {relative}")
        path = root.joinpath(*relative.split("/"))
        current = root
        try:
            for part in relative.split("/"):
                current = current / part
                if not current.exists() and not current.is_symlink():
                    return None
                status = current.lstat()
                attributes = getattr(status, "st_file_attributes", 0)
                if current.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    raise CliFailure("unsafe_project_path", "Project metadata paths must not contain links or reparse points.", module="backend", details={"path": str(current)})
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
            if not resolved.is_file():
                raise CliFailure("unsafe_project_path", "A project metadata source is not a regular file.", module="backend", details={"path": str(path)})
            size = resolved.stat().st_size
            if size > _MAX_SOURCE_BYTES:
                raise CliFailure("project_metadata_source_too_large", "A project metadata source exceeds the one MiB limit.", module="backend", details={"source": relative, "size": size})
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(resolved, flags)
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise CliFailure("unsafe_project_path", "A project metadata source is not a regular file.", module="backend", details={"path": str(path)})
                content = os.read(descriptor, _MAX_SOURCE_BYTES + 1)
                after = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            evidence_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            evidence_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            if evidence_before != evidence_after or len(content) != before.st_size:
                raise CliFailure("project_metadata_source_changed", "A project metadata source changed while it was being read; reload and retry.", module="backend", details={"source": relative})
            if len(content) > _MAX_SOURCE_BYTES:
                raise CliFailure("project_metadata_source_too_large", "A project metadata source exceeds the one MiB limit.", module="backend", details={"source": relative})
            return content
        except CliFailure:
            raise
        except PermissionError as exc:
            raise CliFailure("project_permission_denied", "Permission was denied while reading project metadata.", module="backend", details={"source": relative}) from exc
        except (OSError, ValueError) as exc:
            raise CliFailure("unsafe_project_path", "A project metadata source could not be read safely.", module="backend", details={"source": relative}) from exc
    return read


def _read_sources(reader: SourceReader) -> dict[str, str]:
    result = {}
    for relative in _AUXILIARY_SOURCES:
        try:
            raw = reader(relative)
        except CliFailure:
            raise
        except PermissionError as exc:
            raise CliFailure("project_permission_denied", "Permission was denied while reading project metadata.", module="backend", details={"source": relative}) from exc
        except OSError as exc:
            raise CliFailure("unsafe_project_path", "A project metadata source could not be read safely.", module="backend", details={"source": relative}) from exc
        except RuntimeError as exc:
            raise CliFailure("project_metadata_source_changed", "A project metadata source changed while it was being read; reload and retry.", module="backend", details={"source": relative}) from exc
        if raw is None:
            continue
        if not isinstance(raw, bytes):
            raise TypeError("source_reader must return bytes or None")
        if len(raw) > _MAX_SOURCE_BYTES:
            raise CliFailure("project_metadata_source_too_large", "A project metadata source exceeds the one MiB limit.", module="backend", details={"source": relative, "size": len(raw)})
        try:
            result[relative] = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CliFailure("project_metadata_source_encoding_invalid", "A project metadata source is not valid UTF-8.", module="backend", details={"source": relative}) from exc
    return result


def _parse_xml_source(text: str, source: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise CliFailure("project_metadata_source_invalid", "A project metadata XML source is malformed.", module="backend", details={"source": source, "reason": str(exc)}) from exc


def _add_attachment_observations(observations: _Observations, text: str, source: str) -> None:
    for match in re.finditer(r"PlatformSDK_(S32K\d+)_([A-Z0-9]+)_M\d+_(\d+\.\d+\.\d+)_PATH", text, re.IGNORECASE):
        observations.add("family", match.group(1), source, "/attachedSDKs")
        observations.add("device", match.group(2), source, "/attachedSDKs")
        observations.add("rtd_release", match.group(3), source, "/attachedSDKs")


def parse_project_metadata(
    target: VerifiedProjectTarget,
    document: MexDocument,
    source_reader: SourceReader | None = None,
    package_aliases: Mapping[str, str] = DEFAULT_PACKAGE_ALIASES,
) -> ProjectMetadata:
    if not isinstance(target, VerifiedProjectTarget):
        raise TypeError("target must be a VerifiedProjectTarget")
    if not isinstance(document, MexDocument) or document._source_snapshot is not target.mex:
        raise TypeError("document must be parsed from the verified target snapshot")
    root = document.root
    namespace = _root_namespace(root)
    recognized = namespace is not None and namespace.startswith(_NXP_NAMESPACE_PREFIX)
    observations = _Observations()
    observations.add("processor", _text_child(root, "processor"), ".mex", "/configuration/common/processor")
    observations.add("device", root.attrib.get("name"), ".mex", "/configuration/@name")
    raw_package = _normalize("raw_package", _text_child(root, "package"))
    mcu_data = _normalize("mcu_data", _text_child(root, "mcu_data"))
    if mcu_data:
        match = re.fullmatch(r"PlatformSDK_(S32K\d+)", mcu_data, re.IGNORECASE)
        if match:
            observations.add("family", match.group(1), ".mex", "/configuration/common/mcu_data")
    schema_location = _normalize("schema_location", root.attrib.get(_XSI_SCHEMA_LOCATION))
    schema_version = root.attrib.get("version")
    observations.add("schema_version", schema_version, ".mex", "/configuration/@version")
    if namespace:
        match = re.search(r"mex_configuration_(\d+)$", namespace)
        observations.add("schema_version", match.group(1) if match else None, ".mex", "/configuration/namespace-uri()")
    if schema_location:
        versions = set(re.findall(r"mex_configuration_(\d+)", schema_location))
        for version in versions:
            observations.add("schema_version", version, ".mex", "/configuration/@xsi:schemaLocation")

    sources = _read_sources(source_reader or _safe_source_reader(target))
    for source in (".project", ".cproject"):
        text = sources.get(source)
        if text is None:
            continue
        xml_root = _parse_xml_source(text, source)
        if source == ".cproject":
            for item in xml_root.iter():
                value = item.attrib.get("value", "")
                if re.fullmatch(r"CPU_S32K\d+", value, re.IGNORECASE):
                    observations.add("processor", value, source, "//listOptionValue/@value")
                    observations.add("device", value, source, "//listOptionValue/@value")

    runtime_source = ".settings/com.nxp.s32ds.cle.runtime.component.prefs"
    runtime = sources.get(runtime_source, "")
    for line_number, line in enumerate(runtime.splitlines(), 1):
        key, separator, value = line.partition("=")
        if not separator:
            continue
        if key.endswith("hardware.registry.device.id"):
            observations.add("device", value, runtime_source, f"/{key}[line={line_number}]")
        elif key.endswith("hardware.registry.family.id"):
            observations.add("family", value, runtime_source, f"/{key}[line={line_number}]")

    sdk_source = ".settings/com.freescale.s32ds.cross.sdk.support.prefs"
    _add_attachment_observations(observations, sources.get(sdk_source, ""), sdk_source)

    resolved: dict[str, str | None] = {}
    conflicts = []
    for field in ("processor", "family", "device", "schema_version", "rtd_release"):
        value, conflict = observations.resolve(field)
        resolved[field] = value
        if conflict:
            conflicts.append(conflict)
    return ProjectMetadata(
        "NXP" if recognized else None, "s32-mex" if recognized else None,
        resolved["processor"], resolved["family"], resolved["device"],
        raw_package, package_aliases.get(raw_package) if raw_package else None, mcu_data,
        namespace, resolved["schema_version"], schema_location,
        _parse_tools(root), _parse_modules(root), resolved["rtd_release"], tuple(conflicts),
    )
