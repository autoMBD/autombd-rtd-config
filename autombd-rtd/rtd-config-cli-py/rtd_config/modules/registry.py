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
# File:        registry.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Typed immutable provider bindings and fail-closed registry.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
import inspect
from types import MappingProxyType
from typing import Callable, Mapping

from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange, TargetSelector


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
        provider_is_type = isinstance(self.provider_type, type)
        provider_name = getattr(self.provider_type, "name", None) if provider_is_type else None
        provider_plan = getattr(self.provider_type, "plan", None) if provider_is_type else None
        if (
            not provider_is_type
            or not isinstance(provider_name, str) or provider_name != self.module
            or not callable(provider_plan)
            or not _signature_accepts(self.provider_type, object())
            or not _signature_accepts(provider_plan, object(), object())
            or not _signature_accepts(self.normalizer, object(), object())
            or not _signature_accepts(self.apply_fn, object(), object(), bundle=object())
        ):
            self._raise_invalid()
        self.validate_ownership()

    def validate_ownership(self) -> None:
        """Validate the callable and ownership fields consumed by a transaction."""
        invalid = (
            not all(isinstance(item, str) and item for item in self.key)
            or not isinstance(self.cli_action, str) or not self.cli_action
            or not callable(self.normalizer) or not callable(self.apply_fn)
            or type(self.write_owners) is not frozenset
            or type(self.read_dependencies) is not frozenset
            or type(self.allowed_regions) is not frozenset
            or not all(isinstance(item, str) and item for item in self.write_owners)
            or not all(isinstance(item, str) and item for item in self.read_dependencies)
            or not all(isinstance(item, PhysicalRegion) for item in self.allowed_regions)
            or self.module not in self.write_owners
            or bool(self.write_owners & self.read_dependencies)
            or not self.write_owners
            or not self.allowed_regions
            or any(region.owner not in self.write_owners for region in self.allowed_regions)
            or any(
                not isinstance(region.owner, str) or not region.owner
                or not isinstance(region.name, str) or not region.name
                for region in self.allowed_regions
            )
            or not self.write_owners <= {region.owner for region in self.allowed_regions}
        )
        if invalid:
            self._raise_invalid()

    def create_plan(self, bundle, intent: Intent) -> Plan:
        """Construct and validate a provider plan behind a typed failure boundary."""
        try:
            provider = self.provider_type(bundle)
        except Exception as exc:
            raise CliFailure(
                "provider_registry_invalid", "The registered provider could not be constructed.",
                module="backend", details={"module": self.module},
            ) from exc
        try:
            plan = provider.plan(intent)
        except Exception as exc:
            raise CliFailure(
                "provider_plan_invalid", "The registered provider could not produce a plan.",
                module="backend", details={"module": self.module},
            ) from exc
        validate_provider_plan(plan)
        return plan

    def _raise_invalid(self) -> None:
        raise CliFailure(
            "provider_registry_invalid",
            "A provider binding has an invalid typed ownership contract.",
            module="backend",
            details={"backend": self.backend, "module": self.module, "action": self.action},
        )


def _signature_accepts(callable_value, *args, **kwargs) -> bool:
    """Check a callable contract without constructing providers or invoking code."""
    try:
        inspect.signature(callable_value).bind(*args, **kwargs)
    except (TypeError, ValueError):
        return False
    return True


def validate_provider_plan(plan) -> None:
    if not isinstance(plan, Plan) or not isinstance(plan.changes, list):
        raise CliFailure(
            "provider_plan_invalid", "The provider must return a typed Plan.", module="backend",
        )
    for change in plan.changes:
        valid_targets = isinstance(change, PlannedChange) and type(change.targets) is tuple and all(
            isinstance(target, TargetSelector)
            and isinstance(target.region, str)
            and type(target.path) is tuple
            and all(isinstance(item, str) and item for item in target.path)
            and type(target.identity) is tuple
            and all(
                type(item) is tuple and len(item) == 2
                and all(isinstance(value, str) and value for value in item)
                for item in target.identity
            )
            for target in change.targets
        )
        if (
            not isinstance(change, PlannedChange)
            or not all(isinstance(value, str) and value for value in (
                change.module, change.owner, change.path, change.description
            ))
            or not valid_targets
        ):
            raise CliFailure(
                "provider_plan_invalid", "The provider returned an invalid planned change.",
                module="backend",
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
