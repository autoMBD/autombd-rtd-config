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
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        ownership.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Derive and authorize actual structural XML ownership deltas.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from ...errors import CliFailure
from ...modules.registry import PhysicalRegion, ProviderBinding


@dataclass(frozen=True)
class DeltaEntry:
    kind: str
    path: str
    owner: str
    region: str
    attributes: tuple[tuple[str, str], ...]
    text: str


@dataclass(frozen=True)
class OwnershipAudit:
    entries: tuple[DeltaEntry, ...]
    changed_modules: tuple[str, ...]


@dataclass(frozen=True)
class _Record:
    path: str
    owner: str
    region: str
    attributes: tuple[tuple[str, str], ...]
    text: str

    @property
    def signature(self) -> tuple:
        return self.attributes, self.text


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _selector(element: ET.Element) -> str:
    tag = _local(element.tag)
    for attribute in ("name", "id", "type", "key"):
        value = element.attrib.get(attribute)
        if value is not None:
            return f"{tag}[@{attribute}={value!r}]"
    return tag


def _records(raw: bytes) -> dict[str, _Record]:
    root = ET.fromstring(raw)
    result: dict[str, _Record] = {}

    def visit(element, parent_path, owner, region):
        tag = _local(element.tag)
        if tag == "config_set" and element.attrib.get("name"):
            name = element.attrib["name"]
            owner = name.lower()
            region = f"config_set:{name}"
        elif tag == "pins":
            owner, region = "port", "Pins/Port"
        elif tag == "clock_settings":
            owner, region = "mcu", "Clocks/clock_settings"
        path = f"{parent_path}/{_selector(element)}"
        own_path = path
        suffix = 1
        while own_path in result:
            suffix += 1
            own_path = f"{path}[{suffix}]"
        text = (element.text or "").strip()
        result[own_path] = _Record(
            own_path, owner, region,
            tuple(sorted((str(key), str(value)) for key, value in element.attrib.items())),
            text,
        )
        # Distinct named children keep stable paths when sibling order changes.
        for child in element:
            visit(child, own_path, owner, region)

    visit(root, "", "unknown", "unknown")
    return result


def collect_actual_deltas(before: bytes, candidate: bytes) -> tuple[DeltaEntry, ...]:
    if before == candidate:
        return ()
    old = _records(before)
    new = _records(candidate)
    entries: list[DeltaEntry] = []
    for path in sorted(set(old) | set(new)):
        prior = old.get(path)
        later = new.get(path)
        if prior is not None and later is not None and prior.signature == later.signature:
            continue
        record = later or prior
        assert record is not None
        entries.append(DeltaEntry(
            "added" if prior is None else "removed" if later is None else "modified",
            path, record.owner, record.region, record.attributes, record.text,
        ))
    return tuple(entries)


def audit_candidate(before: bytes, candidate: bytes, binding: ProviderBinding, plan) -> OwnershipAudit:
    binding.validate()
    try:
        changes = tuple(plan.changes)
        declared = {str(change.owner) for change in changes}
    except (AttributeError, TypeError) as exc:
        raise CliFailure(
            "provider_plan_invalid", "Provider ownership audit requires a typed Plan.",
            module="backend",
        ) from exc
    permitted_declarations = binding.write_owners | binding.read_dependencies
    if not declared <= permitted_declarations:
        raise CliFailure(
            "provider_plan_invalid",
            "The provider plan declares an owner outside its binding contract.",
            module="backend", details={"owners": sorted(declared - permitted_declarations)},
        )
    authorized_writes = declared & binding.write_owners
    allowed_regions = {(item.owner, item.name) for item in binding.allowed_regions}
    entries = collect_actual_deltas(before, candidate)
    owner_violations = sorted({
        entry.owner for entry in entries if entry.owner not in authorized_writes
    })
    if owner_violations:
        raise CliFailure(
            "provider_ownership_violation",
            "The candidate changes a module not authorized by the provider plan.",
            module="backend", details={"owners": owner_violations},
        )
    region_violations = sorted({
        f"{entry.owner}:{entry.region}"
        for entry in entries if (entry.owner, entry.region) not in allowed_regions
    })
    if region_violations:
        raise CliFailure(
            "provider_region_violation",
            "The candidate changes a physical XML region outside its binding contract.",
            module="backend", details={"regions": region_violations},
        )
    actual = {entry.owner for entry in entries}
    ordered = tuple(
        ([binding.module] if binding.module in actual else [])
        + sorted(actual - {binding.module})
    )
    return OwnershipAudit(entries, ordered)
