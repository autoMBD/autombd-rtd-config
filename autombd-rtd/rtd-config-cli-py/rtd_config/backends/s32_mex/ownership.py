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
# File:        ownership.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Byte-complete XML delta journal and target-level ownership audit.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from ...errors import CliFailure
from ...modules.registry import PhysicalRegion, ProviderBinding, validate_provider_plan
from ...plan import PlannedChange, TargetSelector


_MEX_NS = "http://mcuxpresso.nxp.com/XSD/mex_configuration_19"


def _mex(local: str) -> str:
    return f"{{{_MEX_NS}}}{local}"


@dataclass(frozen=True)
class DeltaEntry:
    kind: str
    path: str
    owner: str
    region: str
    attributes: tuple[tuple[str, str], ...]
    text: str
    logical_path: tuple[str, ...] = ()
    facts: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class OwnershipAudit:
    entries: tuple[DeltaEntry, ...]
    changed_modules: tuple[str, ...]


@dataclass(frozen=True)
class _Record:
    path: str
    owner: str
    region: str
    qname: str
    attributes: tuple[tuple[str, str], ...]
    text: str
    tail: str
    logical_path: tuple[str, ...]
    facts: tuple[tuple[str, str], ...]

    @property
    def signature(self) -> tuple:
        return self.qname, self.attributes, self.text, self.tail


def _parse(raw: bytes) -> ET.Element:
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        return ET.fromstring(raw, parser=parser)
    except (ET.ParseError, ValueError) as exc:
        raise CliFailure(
            "ownership_unknown", "The XML delta could not be safely journaled.",
            module="backend",
        ) from exc


def _qname(element: ET.Element) -> str:
    return "#comment" if element.tag is ET.Comment else str(element.tag)


def _scope_facts(element: ET.Element) -> tuple[tuple[str, str], ...]:
    """Return facts owned by one lexical element scope, excluding sibling scopes."""
    facts = {str(key): str(value) for key, value in element.attrib.items()}
    for child in element:
        if (
            str(child.tag).rsplit("}", 1)[-1] == "setting"
            and child.attrib.get("name")
            and "value" in child.attrib
        ):
            facts[child.attrib["name"]] = child.attrib["value"]
    return tuple(sorted(facts.items()))


def _merge_facts(
    inherited: tuple[tuple[str, str], ...],
    local: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str], ...]:
    merged = dict(inherited)
    merged.update(local)
    return tuple(sorted(merged.items()))


def _classify(element, ancestors, inherited):
    qname = _qname(element)
    if qname == "#comment":
        return inherited
    tags = tuple(_qname(item) for item in ancestors)
    local = qname.rsplit("}", 1)[-1]
    supported = not qname.startswith("{") or qname.startswith(f"{{{_MEX_NS}}}")
    if not supported:
        return "unknown", "unknown"
    if local == "config_set":
        direct = tags == ("mex", "tools", "periphs")
        full = tags[-7:] == tuple(_mex(item) for item in (
            "configuration", "tools", "periphs", "functional_groups",
            "functional_group", "instances", "instance",
        ))
        compact = tags == ("mex",)
        name = element.attrib.get("name")
        if name and (direct or full or compact):
            return name.lower(), f"config_set:{name}"
        return "unknown", "unknown"
    if local == "pins":
        top = tags in {
            ("mex", "tools"),
            (_mex("configuration"), _mex("tools")),
        }
        if top:
            return "port", "Pins/Port"
        if inherited == ("port", "Pins/Port"):
            return inherited
        return "unknown", "unknown"
    if local == "clock_settings":
        synthetic = tags == ("mex", "tools", "clocks")
        full = tags[-5:] == tuple(_mex(item) for item in (
            "configuration", "tools", "clocks", "clock_configurations", "clock_configuration",
        ))
        return ("mcu", "Clocks/clock_settings") if synthetic or full else ("unknown", "unknown")
    return inherited


def _records(raw: bytes) -> dict[str, _Record]:
    root = _parse(raw)
    result: dict[str, _Record] = {}

    def visit(element, ancestors, parent_path, inherited, logical, fact_scope):
        qname = _qname(element)
        owner, region = _classify(element, ancestors, inherited)
        siblings = list(ancestors[-1]) if ancestors else [element]
        same = [item for item in siblings if _qname(item) == qname]
        index = same.index(element) + 1
        path = f"{parent_path}/{qname}[{index}]"
        values = tuple(
            str(element.attrib[key]) for key in ("name", "id", "key", "type")
            if key in element.attrib
        ) if element.tag is not ET.Comment else ()
        own_logical = logical + values
        local = qname.rsplit("}", 1)[-1]
        if local in {"array", "struct", "pin", "setting"}:
            fact_scope = _merge_facts(fact_scope, _scope_facts(element))
        result[path] = _Record(
            path, owner, region, qname,
            tuple((str(key), str(value)) for key, value in element.attrib.items()),
            element.text or "", element.tail or "", own_logical, fact_scope,
        )
        for child in element:
            visit(child, ancestors + (element,), path, (owner, region), own_logical, fact_scope)

    visit(root, (), "", ("unknown", "unknown"), (), ())
    return result


def collect_actual_deltas(before: bytes, candidate: bytes) -> tuple[DeltaEntry, ...]:
    if before == candidate:
        return ()
    old, new = _records(before), _records(candidate)
    entries: list[DeltaEntry] = []
    for path in sorted(set(old) | set(new)):
        prior, later = old.get(path), new.get(path)
        if prior is not None and later is not None and prior.signature == later.signature:
            continue
        record = later or prior
        assert record is not None
        entries.append(DeltaEntry(
            "added" if prior is None else "removed" if later is None else "modified",
            path, record.owner, record.region, record.attributes,
            record.text, record.logical_path, record.facts,
        ))
    if not entries:
        raise CliFailure(
            "ownership_unknown",
            "Byte-distinct XML produced no safely attributable journal entries.",
            module="backend",
        )
    return tuple(entries)


def _in_order(needles: tuple[str, ...], values: tuple[str, ...]) -> bool:
    iterator = iter(values)
    return all(any(value == needle for value in iterator) for needle in needles)


def _inferred_target(change: PlannedChange) -> TargetSelector:
    parts = tuple(item for item in change.path.split("/") if item)
    while parts and parts[0].lower() == change.owner.lower():
        parts = parts[1:]
    return TargetSelector("" if not parts else f"config_set:{change.owner.title()}", parts)


def _matches(entry: DeltaEntry, change: PlannedChange) -> bool:
    targets = change.targets or (_inferred_target(change),)
    return entry.owner == change.owner and any(
        (not target.region or entry.region == target.region)
        and _in_order(target.path, entry.logical_path)
        and set(target.identity) <= set(entry.facts)
        for target in targets
    )


def audit_candidate(before: bytes, candidate: bytes, binding: ProviderBinding, plan) -> OwnershipAudit:
    binding.validate_ownership()
    validate_provider_plan(plan)
    changes = tuple(plan.changes)
    declared = {change.owner for change in changes}
    permitted = binding.write_owners | binding.read_dependencies
    if not declared <= permitted:
        raise CliFailure(
            "provider_plan_invalid", "The plan declares an owner outside its binding.",
            module="backend", details={"owners": sorted(declared - permitted)},
        )
    entries = collect_actual_deltas(before, candidate)
    unknown = sorted(entry.path for entry in entries if entry.owner == "unknown")
    if unknown:
        raise CliFailure(
            "ownership_unknown", "An XML delta has no safe physical ownership mapping.",
            module="backend", details={"paths": unknown},
        )
    invalid_owners = sorted({
        entry.owner for entry in entries if entry.owner not in binding.write_owners
    })
    if invalid_owners:
        raise CliFailure(
            "provider_ownership_violation", "The candidate changes an unauthorized owner.",
            module="backend", details={"owners": invalid_owners},
        )
    allowed_regions = {(item.owner, item.name) for item in binding.allowed_regions}
    invalid_regions = sorted({
        f"{entry.owner}:{entry.region}" for entry in entries
        if (entry.owner, entry.region) not in allowed_regions
    })
    if invalid_regions:
        raise CliFailure(
            "provider_region_violation", "The candidate changes an undeclared XML region.",
            module="backend", details={"regions": invalid_regions},
        )
    unauthorized = [
        entry for entry in entries
        if not any(_matches(entry, change) for change in changes)
    ]
    if unauthorized:
        raise CliFailure(
            "provider_ownership_violation",
            "The candidate delta does not match a planned target selector.",
            module="backend", details={
                "paths": sorted(item.path for item in unauthorized),
                "facts": {
                    item.path: [list(fact) for fact in item.facts]
                    for item in unauthorized
                },
            },
        )
    actual = {entry.owner for entry in entries}
    ordered = tuple(([binding.module] if binding.module in actual else []) + sorted(actual - {binding.module}))
    return OwnershipAudit(entries, ordered)
