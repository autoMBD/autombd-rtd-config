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
# File:        registry.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Typed immutable provider bindings and fail-closed registry.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping

from rtd_config.errors import CliFailure
from rtd_config.intent import Intent


@dataclass(frozen=True, order=True)
class PhysicalRegion:
    owner: str
    name: str


@dataclass(frozen=True)
class ProviderBinding:
    backend: str
    module: str
    action: str
    cli_action: str
    normalizer: Callable
    provider_type: type
    apply_fn: Callable
    write_owners: frozenset[str]
    read_dependencies: frozenset[str]
    allowed_regions: frozenset[PhysicalRegion]

    @property
    def key(self) -> tuple[str, str, str]:
        return self.backend, self.module, self.action

    def validate(self) -> None:
        invalid = (
            not all(isinstance(item, str) and item for item in self.key)
            or not isinstance(self.cli_action, str) or not self.cli_action
            or not callable(self.normalizer) or not callable(self.apply_fn)
            or getattr(self.provider_type, "name", None) != self.module
            or self.module not in self.write_owners
            or bool(self.write_owners & self.read_dependencies)
            or not self.write_owners
            or not self.allowed_regions
            or any(region.owner not in self.write_owners for region in self.allowed_regions)
            or any(not region.name for region in self.allowed_regions)
            or not self.write_owners <= {region.owner for region in self.allowed_regions}
        )
        if invalid:
            raise CliFailure(
                "provider_registry_invalid",
                "A provider binding has an invalid typed ownership contract.",
                module="backend",
                details={"backend": self.backend, "module": self.module, "action": self.action},
            )


class ProviderRegistry:
    def __init__(self, bindings) -> None:
        values: dict[tuple[str, str, str], ProviderBinding] = {}
        shortcuts: dict[tuple[str, str], ProviderBinding] = {}
        for binding in tuple(bindings):
            if not isinstance(binding, ProviderBinding):
                raise CliFailure(
                    "provider_registry_invalid", "Registry entries must be ProviderBinding values.",
                    module="backend",
                )
            binding.validate()
            if binding.key in values:
                raise CliFailure(
                    "provider_registry_duplicate",
                    "A provider registry key is registered more than once.",
                    module="backend",
                    details={"backend": binding.backend, "module": binding.module, "action": binding.action},
                )
            shortcut = binding.module, binding.cli_action
            if shortcut in shortcuts:
                raise CliFailure(
                    "provider_registry_duplicate",
                    "A provider shortcut key is registered more than once.",
                    module="backend",
                    details={"module": binding.module, "action": binding.cli_action},
                )
            values[binding.key] = binding
            shortcuts[shortcut] = binding
        self._bindings: Mapping[tuple[str, str, str], ProviderBinding] = MappingProxyType(values)
        self._shortcuts: Mapping[tuple[str, str], ProviderBinding] = MappingProxyType(shortcuts)

    def keys(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(sorted(self._bindings))

    def lookup(self, backend: str, module: str, action: str) -> ProviderBinding:
        try:
            return self._bindings[(backend, module, action)]
        except KeyError as exc:
            raise CliFailure(
                "provider_binding_unknown",
                "No provider binding exists for the requested intent.",
                module="backend", details={"backend": backend, "module": module, "action": action},
            ) from exc

    def lookup_shortcut(self, module: str, cli_action: str) -> ProviderBinding:
        try:
            binding = self._shortcuts[(module, cli_action)]
            return self.lookup(*binding.key)
        except KeyError as exc:
            raise CliFailure(
                "provider_binding_unknown",
                "No provider binding exists for the requested shortcut.",
                module="cli", details={"module": module, "action": cli_action},
            ) from exc

    def require_intent(self, intent: Intent, *, backend: str) -> ProviderBinding:
        if not isinstance(intent, Intent):
            raise CliFailure(
                "provider_intent_invalid", "Provider dispatch requires a typed Intent.",
                module="backend",
            )
        try:
            return self.lookup(backend, intent.module, intent.action)
        except CliFailure as exc:
            raise CliFailure(
                "provider_intent_mismatch",
                "The intent does not match a registered provider binding.",
                module="backend",
                details={"backend": backend, "module": intent.module, "action": intent.action},
            ) from exc
