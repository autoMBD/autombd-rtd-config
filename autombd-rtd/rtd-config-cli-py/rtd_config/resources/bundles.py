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
# File:        bundles.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Exact manifest-driven runtime asset-bundle resolution.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping

from ..backends.s32_mex.metadata import ProjectMetadata
from ..backends.s32_mex.target import (
    _capture_snapshot,
    _inspect,
    _protected_root,
    default_target_platform,
)
from ..errors import CliFailure
from .runtime import load_json


_IDENTITY_FIELDS = (
    "vendor", "backend", "processor", "family", "device", "raw_package",
    "package", "rtd_release", "schema_version",
)
_ASSET_IDENTITY_FIELDS = ("vendor", "family", "device", "package", "rtd_release")
_MODULE_FIELDS = (
    "name", "type", "type_id", "mode", "module_id", "autosar_version",
    "software_version", "vendor_id",
)


def _failure(code: str, message: str, **details: Any) -> CliFailure:
    return CliFailure(code, message, module="backend", details=details)


@dataclass(frozen=True)
class ResolvedAssetBundle:
    id: str
    profile_id: str | None
    root: Path
    assets: Mapping[str, str]
    pin_field: str
    identity: Mapping[str, str]
    asset_identities: Mapping[str, Mapping[str, str]]
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False, compare=False)

    def load_json(self, name: str) -> dict[str, Any]:
        cached = self._cache.get(name)
        if cached is not None:
            return cached
        relative = self.assets.get(name)
        if relative is None:
            raise _failure("asset_not_found", "The requested bundle asset is not declared.", asset=name)
        path = self.root.joinpath(*PurePosixPath(relative).parts)
        try:
            if not path.is_file():
                raise FileNotFoundError
            cursor = self.root
            for part in PurePosixPath(relative).parts:
                cursor /= part
                if cursor.is_symlink():
                    raise _failure("asset_invalid", "Bundle asset paths must not contain symbolic links.", asset=name)
            value = load_json(path)
        except FileNotFoundError as exc:
            raise _failure("asset_not_found", "A required bundle asset was not found.", asset=name) from exc
        except (OSError, UnicodeError) as exc:
            raise _failure("asset_invalid", "A required bundle asset could not be read.", asset=name) from exc
        except (json.JSONDecodeError, TypeError) as exc:
            raise _failure("asset_invalid", "A required bundle asset is not valid JSON.", asset=name) from exc
        expected = {key: self.identity[key] for key in _ASSET_IDENTITY_FIELDS}
        expected.update(self.asset_identities[name])
        actual = value.get("_identity")
        if not isinstance(actual, dict) or actual != expected:
            raise _failure("asset_identity_mismatch", "Bundle asset identity does not match its manifest.", asset=name)
        aliases = {"rtd_version": "rtd_release"}
        for asset_field, identity_field in aliases.items():
            if asset_field in value and value[asset_field] != expected[identity_field]:
                raise _failure("asset_identity_mismatch", "Bundle asset legacy identity conflicts with its manifest.", asset=name, field=asset_field)
        for key in ("family", "device", "package", "module"):
            if key in value and value[key] != expected.get(key):
                raise _failure("asset_identity_mismatch", "Bundle asset legacy identity conflicts with its manifest.", asset=name, field=key)
        self._cache[name] = value
        return value


class AssetBundleResolver:
    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        path = self.root / "bundles.json"
        try:
            platform = default_target_platform()
            with _protected_root(platform, self.root):
                evidence = _inspect(path, platform)
                if not evidence.exists:
                    raise FileNotFoundError
                if (
                    not evidence.is_regular
                    or evidence.is_symlink
                    or evidence.is_reparse_point
                    or evidence.is_mount_point
                ):
                    raise _failure(
                        "asset_manifest_invalid",
                        "The asset bundle manifest must be a safe regular file.",
                    )
                content = _capture_snapshot(path, platform).content
            manifest = json.loads(content.decode("utf-8"))
        except FileNotFoundError as exc:
            raise _failure("asset_manifest_not_found", "The asset bundle manifest was not found.") from exc
        except CliFailure as exc:
            if exc.code == "asset_manifest_invalid":
                raise
            raise _failure("asset_manifest_invalid", "The asset bundle manifest is invalid.") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _failure("asset_manifest_invalid", "The asset bundle manifest is invalid.") from exc
        if not isinstance(manifest, dict) or manifest.get("format_version") != 1 or not isinstance(manifest.get("bundles"), list):
            raise _failure("asset_manifest_invalid", "Unsupported or malformed asset bundle manifest.")
        self._bundles = tuple(self._validate_bundle(item) for item in manifest["bundles"])

    def _validate_bundle(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise _failure("asset_manifest_invalid", "Every bundle declaration must be an object.")
        assets = item.get("assets")
        identities = item.get("asset_identities")
        if not isinstance(item.get("id"), str) or not isinstance(assets, dict) or not isinstance(identities, dict):
            raise _failure("asset_manifest_invalid", "A bundle declaration is incomplete.")
        if set(assets) != set(identities):
            raise _failure("asset_manifest_invalid", "Asset paths and identities must have identical names.")
        for relative in assets.values():
            if not isinstance(relative, str) or "\\" in relative:
                raise _failure("asset_manifest_invalid", "Asset paths must be relative POSIX paths.")
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".json":
                raise _failure("asset_manifest_invalid", "Asset paths must be safe relative JSON paths.")
        if any(not isinstance(value, dict) or set(value) != {"module", "role"} or not all(isinstance(part, str) for part in value.values()) for value in identities.values()):
            raise _failure("asset_manifest_invalid", "Every asset identity requires string module and role fields.")
        if not isinstance(item.get("identity"), dict) or set(_IDENTITY_FIELDS) - set(item["identity"]) or not all(isinstance(item["identity"].get(key), str) for key in _IDENTITY_FIELDS):
            raise _failure("asset_manifest_invalid", "A bundle identity is incomplete.")
        if not isinstance(item.get("module_profiles"), list) or not isinstance(item.get("tools"), list):
            raise _failure("asset_manifest_invalid", "Bundle compatibility profiles are malformed.")
        for tool in item["tools"]:
            if not isinstance(tool, dict) or set(tool) != {"name", "version", "enabled"} or not isinstance(tool["name"], str) or not isinstance(tool["version"], str) or not isinstance(tool["enabled"], bool):
                raise _failure("asset_manifest_invalid", "Bundle tool compatibility is malformed.")
        for profile in item["module_profiles"]:
            if not isinstance(profile, dict) or not isinstance(profile.get("id"), str) or not isinstance(profile.get("modules"), list):
                raise _failure("asset_manifest_invalid", "Bundle module profile is malformed.")
            names: list[str] = []
            for module in profile["modules"]:
                if not isinstance(module, dict) or not all(isinstance(module.get(key), str) for key in ("name", "type", "type_id", "mode")):
                    raise _failure("asset_manifest_invalid", "Bundle module compatibility is malformed.")
                if module.get("published") not in (None, "must_be_unknown"):
                    raise _failure("asset_manifest_invalid", "Unknown module publication policy.")
                names.append(module["name"])
            if len(names) != len(set(names)):
                raise _failure("asset_manifest_invalid", "A module profile contains duplicate modules.")
        if not isinstance(item.get("pin_field"), str):
            raise _failure("asset_manifest_invalid", "Bundle pin field is missing.")
        return item

    @staticmethod
    def _tools_match(metadata: ProjectMetadata, bundle: dict[str, Any]) -> bool:
        if metadata.tools is None:
            return False
        actual = sorted((x.name, x.version, x.enabled) for x in metadata.tools)
        expected = sorted((x["name"], x["version"], x["enabled"]) for x in bundle["tools"])
        return actual == expected

    @staticmethod
    def _profile_matches(metadata: ProjectMetadata, profile: dict[str, Any]) -> bool:
        if metadata.modules is None or len(metadata.modules) != len(profile.get("modules", ())):
            return False
        actual = {item.name: item for item in metadata.modules}
        if set(actual) != {item.get("name") for item in profile["modules"]}:
            return False
        for expected in profile["modules"]:
            item = actual[expected["name"]]
            if expected.get("published") == "must_be_unknown":
                for key in ("module_id", "autosar_version", "software_version", "vendor_id"):
                    if getattr(item, key) is not None:
                        return False
            for key in _MODULE_FIELDS:
                if key in expected and getattr(item, key) != expected[key]:
                    return False
        return True

    def _resolved(self, bundle: dict[str, Any], profile_id: str | None) -> ResolvedAssetBundle:
        resolved = ResolvedAssetBundle(
            bundle["id"], profile_id, self.root,
            MappingProxyType(dict(bundle["assets"])), bundle["pin_field"],
            MappingProxyType(dict(bundle["identity"])),
            MappingProxyType({key: MappingProxyType(dict(value)) for key, value in bundle["asset_identities"].items()}),
        )
        for name in resolved.assets:
            resolved.load_json(name)
        return resolved

    def resolve(self, metadata: ProjectMetadata) -> ResolvedAssetBundle:
        metadata.require_identity()
        matches: list[tuple[dict[str, Any], str]] = []
        for bundle in self._bundles:
            if any(getattr(metadata, key) != value for key, value in bundle["identity"].items()):
                continue
            if not self._tools_match(metadata, bundle):
                continue
            for profile in bundle["module_profiles"]:
                if self._profile_matches(metadata, profile):
                    matches.append((bundle, profile["id"]))
        if not matches:
            raise _failure("asset_bundle_unsupported", "No exact asset bundle supports the observed project identity.")
        if len(matches) != 1:
            raise _failure("asset_bundle_ambiguous", "More than one exact asset bundle matches the project identity.")
        return self._resolved(*matches[0])

    def resolve_selector(self, *, bundle_id: str | None = None, **selector: str) -> ResolvedAssetBundle:
        fields = ("vendor", "backend", "family", "device", "package", "rtd_release", "schema_version")
        matches = [item for item in self._bundles if (
            item["id"] == bundle_id if bundle_id else all(item["identity"].get(key) == selector.get(key) for key in fields)
        )]
        if not matches:
            raise _failure("asset_bundle_unsupported", "No exact asset bundle supports the requested selector.")
        if len(matches) != 1:
            raise _failure("asset_bundle_ambiguous", "More than one asset bundle matches the requested selector.")
        return self._resolved(matches[0], None)
