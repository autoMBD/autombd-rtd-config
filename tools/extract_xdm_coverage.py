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
# File:        extract_xdm_coverage.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Deterministically extract and validate non-runtime XDM coverage.
# =================================================================================

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET


FORMAT_VERSION = 1
ITEM_TAGS = {"ctr": "container", "lst": "list", "var": "variable"}
FACT_NAMES = (
    "DEFAULT", "RANGE", "INVALID", "EDITABLE", "ENABLE", "READONLY",
    "MIN", "MAX",
)
CLASSIFICATIONS = {"configurable", "derived", "deferred"}
KNOWN_MODULES = {
    "Adc", "BaseNXP", "Dem", "Dio", "EcuC", "Mcl", "Mcu", "Os",
    "Platform", "Port", "Uart",
}


class InventoryError(ValueError):
    """Raised when descriptor inventory evidence is incomplete or inconsistent."""


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _segment(element: ET.Element, parent: ET.Element | None) -> str:
    local = _local(element)
    identity = (
        element.get("name") or element.get("value") or element.get("type")
        or local
    )
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", identity).strip("_") or local
    if parent is None:
        return f"{local}[{safe}]"
    peers = [
        child for child in parent
        if _local(child) == local
        and (
            child.get("name") or child.get("value") or child.get("type") or local
        ) == identity
    ]
    if len(peers) > 1:
        safe = f"{safe}[{peers.index(element) + 1}]"
    return f"{local}[{safe}]"


def _structural_path(
    element: ET.Element,
    parents: dict[ET.Element, ET.Element],
) -> str:
    chain = [element]
    current = element
    while current in parents:
        current = parents[current]
        if _local(current) in {"datamodel", "ctr", "lst", "chc"}:
            chain.append(current)
    chain.reverse()
    return "/" + "/".join(
        _segment(item, parents.get(item)) for item in chain
    )


def _tests(element: ET.Element) -> list[dict[str, str]]:
    return [
        dict(sorted(child.attrib.items()))
        for child in element
        if _local(child) == "tst"
    ]


def _fact(element: ET.Element, name: str) -> dict | None:
    source = next((child for child in element if child.get("name") == name), None)
    if source is None:
        return None
    tests = _tests(source)
    values = [
        child.get("value") if child.get("value") is not None else (child.text or "").strip()
        for child in source
        if _local(child) == "v"
    ]
    is_xpath = source.get("type", "").casefold() == "xpath" or bool(tests)
    if is_xpath:
        result: dict = {"kind": "xpath"}
        if source.get("expr") is not None:
            result["expr"] = source.get("expr")
        if tests:
            result["tests"] = tests
        if source.get("value") is not None:
            result["value"] = source.get("value")
        return result
    if values:
        return {"kind": "literal", "values": values}
    return {"kind": "literal", "value": source.get("value", "")}


def _reference_module(reference: str) -> str | None:
    raw = reference.split(":", 1)[-1]
    parts = [part for part in raw.split("/") if part]
    if not parts:
        return None
    if len(parts) >= 3 and parts[:2] == ["AUTOSAR", "EcucDefs"]:
        return parts[2]
    if parts[0].startswith("TS_") and len(parts) >= 2:
        return parts[1]
    return parts[0]


def _include_reference(element: ET.Element, module: str) -> bool:
    if not element.get("name"):
        return False
    reference = _fact(element, "REF")
    target = None if reference is None else reference.get("value")
    if module not in {"Mcu", "Adc"}:
        return True
    if not target or _reference_module(target) != module:
        return False
    # BCTU notification ADC index is a generated notification relationship;
    # the enclosing list is the descriptor item and accounts for this field.
    return element.get("name") != "BctuAdcNotificationsAdcIndex"


def _release_from_items(items: list[dict]) -> str:
    values: dict[str, str] = {}
    aliases = {
        "SwMajorVersion": "major", "SwMinorVersion": "minor",
        "SwPatchVersion": "patch",
    }
    for item in items:
        alias = aliases.get(item.get("name"))
        default = item.get("default")
        if alias and isinstance(default, dict) and default.get("kind") == "literal":
            values.setdefault(alias, str(default.get("value", "")))
    if set(values) == {"major", "minor", "patch"}:
        return f'{values["major"]}.{values["minor"]}.{values["patch"]}'
    return "7.0.1"


def extract_descriptor(path: Path | str, *, module: str) -> dict:
    """Extract descriptor facts only; implementation classification is separate."""
    source = Path(path)
    root = ET.parse(source).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    items: list[dict] = []
    for element in root.iter():
        local = _local(element)
        if local in ITEM_TAGS:
            kind = ITEM_TAGS[local]
        elif local == "ref" and _include_reference(element, module):
            kind = "reference"
        else:
            continue
        structural_path = _structural_path(element, parents)
        item: dict = {
            "key": f"{kind}:{structural_path}",
            "kind": kind,
            "path": structural_path,
            "name": element.get("name", ""),
        }
        if element.get("type"):
            item["type"] = element.get("type")
        for fact_name in FACT_NAMES:
            fact = _fact(element, fact_name)
            if fact is not None:
                item[fact_name.casefold()] = fact
        reference = _fact(element, "REF")
        if reference is not None:
            target = str(reference.get("value", ""))
            item["reference"] = target
            referenced_module = _reference_module(target)
            item["cross_references"] = (
                [referenced_module]
                if referenced_module and referenced_module != module else []
            )
        items.append(item)
    items.sort(key=lambda item: item["key"])
    keys = [item["key"] for item in items]
    if len(keys) != len(set(keys)):
        raise InventoryError("descriptor extraction produced duplicate stable keys")
    package_parent = source.parent.parent.name
    package = package_parent.split("_", 1)[1] if "_" in package_parent else package_parent
    return {
        "format_version": FORMAT_VERSION,
        "source": {
            "module": module,
            "descriptor": source.name,
            "package": package,
            "rtd_release": _release_from_items(items),
            "sha256": _sha256(source),
        },
        "items": items,
    }


def _matches(item: dict, match: dict) -> bool:
    if "name" in match and item.get("name") != match["name"]:
        return False
    if "kind" in match and item.get("kind") != match["kind"]:
        return False
    if "key" in match and item.get("key") != match["key"]:
        return False
    if "key_regex" in match and re.search(match["key_regex"], item["key"]) is None:
        return False
    return True


def classify_inventory(extracted: dict, overrides: dict) -> dict:
    """Apply separately maintained classification rules to extracted facts."""
    result = copy.deepcopy(extracted)
    default = overrides.get("default")
    if not isinstance(default, dict):
        raise InventoryError("classification overrides require a default rule")
    rules = overrides.get("rules", [])
    if not isinstance(rules, list):
        raise InventoryError("classification rules must be a list")
    for item in result["items"]:
        classification = copy.deepcopy(default)
        matched = [rule for rule in rules if _matches(item, rule.get("match", {}))]
        if len(matched) > 1:
            raise InventoryError(f'multiple classification rules match {item["key"]}')
        if matched:
            classification = {
                key: copy.deepcopy(value)
                for key, value in matched[0].items() if key != "match"
            }
        item.update(classification)
    counts = {
        status: sum(item.get("classification") == status for item in result["items"])
        for status in sorted(CLASSIFICATIONS)
    }
    result["summary"] = {"total": len(result["items"]), **counts}
    gap_rules = overrides.get("known_gap_rules", {})
    if gap_rules:
        if not isinstance(gap_rules, dict):
            raise InventoryError("known gap rules must be an object")
        result["known_gaps"] = {}
        for group, selectors in gap_rules.items():
            if not isinstance(selectors, list) or not selectors:
                raise InventoryError("known gap selectors must be a non-empty list")
            result["known_gaps"][group] = [
                item["key"] for item in result["items"]
                if item["classification"] == "deferred"
                and any(_matches(item, selector) for selector in selectors)
            ]
    return result


def _resolve_symbol(repo_root: Path, reference: str) -> None:
    path_text, separator, symbol = reference.partition(":")
    path = repo_root / PurePosixPath(path_text)
    if not separator or not path.is_file() or not symbol:
        raise InventoryError(f"invalid trace reference: {reference}")
    if symbol not in path.read_text(encoding="utf-8"):
        raise InventoryError(f"trace symbol is absent: {reference}")


def _resolve_test(repo_root: Path, reference: str) -> None:
    path_text, separator, node = reference.partition("::")
    path = repo_root / PurePosixPath(path_text)
    if not separator or not path.is_file() or node not in path.read_text(encoding="utf-8"):
        raise InventoryError(f"invalid test trace: {reference}")


def _resolve_asset(repo_root: Path, reference: str) -> None:
    path_text, separator, pointer = reference.partition("#")
    path = repo_root / PurePosixPath(path_text)
    if not separator or not path.is_file() or not pointer.startswith("/"):
        raise InventoryError(f"invalid asset trace: {reference}")
    value = json.loads(path.read_text(encoding="utf-8"))
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(token)]
        else:
            value = value[token]


def validate_sidecar(sidecar: dict, *, repo_root: Path) -> None:
    if sidecar.get("format_version") != FORMAT_VERSION:
        raise InventoryError("unsupported inventory format")
    source = sidecar.get("source")
    if not isinstance(source, dict) or set(source) != {
        "module", "descriptor", "package", "rtd_release", "sha256"
    }:
        raise InventoryError("inventory source identity is incomplete")
    if Path(source["descriptor"]).name != source["descriptor"]:
        raise InventoryError("descriptor identity must not contain a machine path")
    if re.fullmatch(r"[0-9A-F]{64}", source["sha256"]) is None:
        raise InventoryError("descriptor hash is invalid")
    items = sidecar.get("items")
    if not isinstance(items, list) or not items:
        raise InventoryError("inventory items are missing")
    keys = [item.get("key") for item in items]
    if len(keys) != len(set(keys)) or any(not isinstance(key, str) for key in keys):
        raise InventoryError("inventory keys must be unique strings")
    for item in items:
        if item.get("key") != f'{item.get("kind")}:{item.get("path")}':
            raise InventoryError("inventory stable key is malformed")
        classification = item.get("classification")
        if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
            raise InventoryError("every item requires exactly one classification")
        for module in item.get("cross_references", []):
            if module not in KNOWN_MODULES:
                raise InventoryError("inventory cross-module reference is unknown")
        if classification == "configurable":
            trace = item.get("trace")
            if not isinstance(trace, dict) or set(trace) != {
                "provider", "apply", "asset", "tests"
            }:
                raise InventoryError("configurable item trace is incomplete")
            _resolve_symbol(repo_root, trace["provider"])
            _resolve_symbol(repo_root, trace["apply"])
            _resolve_asset(repo_root, trace["asset"])
            if not trace["tests"]:
                raise InventoryError("configurable item needs generality tests")
            for test in trace["tests"]:
                _resolve_test(repo_root, test)
        elif classification == "derived":
            trace = item.get("trace")
            if not isinstance(trace, dict) or set(trace) != {"implementation", "tests"}:
                raise InventoryError("derived item trace is incomplete")
            _resolve_symbol(repo_root, trace["implementation"])
            if not trace["tests"]:
                raise InventoryError("derived item needs rule tests")
            for test in trace["tests"]:
                _resolve_test(repo_root, test)
        else:
            if not str(item.get("reason", "")).strip():
                raise InventoryError("deferred item needs an engineering reason")
            if not str(item.get("dependency", "")).strip():
                raise InventoryError("deferred item needs a dependency")
    expected = {
        status: sum(item["classification"] == status for item in items)
        for status in sorted(CLASSIFICATIONS)
    }
    if sidecar.get("summary") != {"total": len(items), **expected}:
        raise InventoryError("inventory summary does not match classifications")
    item_keys = set(keys)
    for group in sidecar.get("known_gaps", {}).values():
        if not isinstance(group, list) or not group or not set(group) <= item_keys:
            raise InventoryError("known gap evidence must reference inventory keys")
        if any(
            next(item for item in items if item["key"] == key)["classification"]
            != "deferred" for key in group
        ):
            raise InventoryError("known gaps must remain explicitly deferred")


def _extraction_projection(sidecar: dict) -> dict:
    result = {
        "format_version": sidecar["format_version"],
        "source": sidecar["source"],
        "items": [],
    }
    for item in sidecar["items"]:
        result["items"].append({
            key: copy.deepcopy(value)
            for key, value in item.items()
            if key not in {"classification", "trace", "reason", "dependency"}
        })
    return result


def verify_source(sidecar: dict, source: Path | str) -> None:
    module = sidecar.get("source", {}).get("module")
    extracted = extract_descriptor(source, module=module)
    if _extraction_projection(sidecar) != extracted:
        raise InventoryError("descriptor extraction or hash differs from the sidecar")


def _contains_coverage(value) -> bool:
    if isinstance(value, dict):
        return "_coverage" in value or any(_contains_coverage(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_coverage(item) for item in value)
    return False


def validate_repository(repo_root: Path) -> None:
    coverage_root = repo_root / "docs/specs/rtd-config-module-coverage"
    for path in sorted(coverage_root.glob("*.json")):
        validate_sidecar(json.loads(path.read_text(encoding="utf-8")), repo_root=repo_root)
    for path in sorted((repo_root / "autombd-rtd/assets").rglob("*.json")):
        if _contains_coverage(json.loads(path.read_text(encoding="utf-8"))):
            raise InventoryError(f"runtime asset contains _coverage: {path.name}")
    manifest = repo_root / "autombd-rtd/release-manifest.json"
    if manifest.exists() and "rtd-config-module-coverage" in manifest.read_text(encoding="utf-8"):
        raise InventoryError("release manifest includes development coverage sidecars")


def _write_json(path: Path, payload: dict) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--module")
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-source", type=Path, metavar="SIDECAR")
    args = parser.parse_args(argv)
    try:
        if args.verify_source is not None:
            if args.descriptor is None:
                raise InventoryError("--verify-source requires --descriptor")
            sidecar = json.loads(args.verify_source.read_text(encoding="utf-8"))
            verify_source(sidecar, args.descriptor)
            return 0
        if args.descriptor is not None:
            if not args.module or args.overrides is None:
                raise InventoryError("generation requires --module and --overrides")
            extracted = extract_descriptor(args.descriptor, module=args.module)
            overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
            sidecar = classify_inventory(extracted, overrides)
            validate_sidecar(sidecar, repo_root=args.repo_root)
            if args.output is None:
                print(json.dumps(sidecar, ensure_ascii=False, indent=2))
            elif args.check:
                committed = json.loads(args.output.read_text(encoding="utf-8"))
                if committed != sidecar:
                    raise InventoryError("committed sidecar differs from regeneration")
            else:
                _write_json(args.output, sidecar)
            return 0
        validate_repository(args.repo_root)
        return 0
    except (InventoryError, OSError, ET.ParseError, json.JSONDecodeError) as exc:
        print(f"descriptor_inventory_error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
