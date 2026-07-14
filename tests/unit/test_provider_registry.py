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
# File:        test_provider_registry.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Typed provider-registry contract and completeness tests.
# =================================================================================

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.modules.registry import (
    PhysicalRegion,
    ProviderBinding,
    ProviderRegistry,
)


class _Provider:
    name = "uart"

    def __init__(self, _bundle):
        pass

    def plan(self, _intent):
        return SimpleNamespace(changes=[])


def _normalizer(_args, _bundle):
    return Intent("uart", "set", {})


def _apply(_doc, _intent, *, bundle):
    return None


def _binding(**overrides):
    values = dict(
        backend="mex", module="uart", action="set",
        cli_action="set", normalizer=_normalizer,
        provider_type=_Provider, apply_fn=_apply,
        write_owners=frozenset({"uart"}), read_dependencies=frozenset(),
        allowed_regions=frozenset({PhysicalRegion("uart", "config_set:Uart")}),
    )
    values.update(overrides)
    return ProviderBinding(**values)


def test_registry_rejects_duplicate_keys_stably():
    with pytest.raises(CliFailure) as caught:
        ProviderRegistry((_binding(), _binding()))
    assert caught.value.code == "provider_registry_duplicate"
    assert not caught.value.details.get("path")


def test_registry_rejects_duplicate_shortcut_even_when_registry_actions_differ():
    with pytest.raises(CliFailure) as caught:
        ProviderRegistry((_binding(), _binding(action="other")))
    assert caught.value.code == "provider_registry_duplicate"


def test_registry_and_bindings_are_immutable_after_validation():
    binding = _binding()
    registry = ProviderRegistry((binding,))
    with pytest.raises(TypeError):
        registry._bindings[binding.key] = binding
    with pytest.raises(TypeError):
        registry._shortcuts[(binding.module, binding.cli_action)] = binding
    with pytest.raises(FrozenInstanceError):
        binding.module = "mcu"


@pytest.mark.parametrize(
    "binding,code",
    [
        (_binding(provider_type=type("Wrong", (), {"name": "mcu"})), "provider_registry_invalid"),
        (_binding(provider_type=SimpleNamespace(name="uart")), "provider_registry_invalid"),
        (_binding(read_dependencies=frozenset({"uart"})), "provider_registry_invalid"),
        (_binding(allowed_regions=frozenset({PhysicalRegion("mcu", "config_set:Mcu")})), "provider_registry_invalid"),
    ],
)
def test_registry_rejects_provider_ownership_contract_errors(binding, code):
    with pytest.raises(CliFailure) as caught:
        ProviderRegistry((binding,))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "overrides",
    [
        {"normalizer": lambda _args: Intent("uart", "set", {})},
        {"apply_fn": lambda _doc, _intent: None},
        {"write_owners": {"uart"}},
        {"read_dependencies": ("mcu",)},
        {"allowed_regions": {PhysicalRegion("uart", "config_set:Uart")}},
        {"write_owners": frozenset({"uart", 1})},
    ],
)
def test_registry_rejects_invalid_callable_signatures_and_runtime_field_types(overrides):
    with pytest.raises(CliFailure) as caught:
        ProviderRegistry((_binding(**overrides),))
    assert caught.value.code == "provider_registry_invalid"


def test_registry_lookup_rejects_unknown_and_wrong_intent():
    registry = ProviderRegistry((_binding(),))
    with pytest.raises(CliFailure) as unknown:
        registry.lookup("mex", "adc", "set")
    assert unknown.value.code == "provider_binding_unknown"
    with pytest.raises(CliFailure) as wrong:
        registry.require_intent(Intent("uart", "other", {}), backend="mex")
    assert wrong.value.code == "provider_intent_mismatch"
    with pytest.raises(CliFailure) as invalid:
        registry.require_intent(SimpleNamespace(module="uart", action="set"), backend="mex")
    assert invalid.value.code == "provider_intent_invalid"
    with pytest.raises(CliFailure) as shortcut:
        registry.lookup_shortcut("uart", "missing")
    assert shortcut.value.code == "provider_binding_unknown"


def test_default_registry_has_exactly_all_nine_supported_bindings():
    registry = cli.get_provider_registry()
    assert registry.keys() == (
        ("mex", "adc", "set"),
        ("mex", "basenxp", "set"),
        ("mex", "dio", "set"),
        ("mex", "mcl", "set"),
        ("mex", "mcu", "set"),
        ("mex", "platform", "set"),
        ("mex", "port", "set"),
        ("mex", "uart", "add_flexio_channel"),
        ("mex", "uart", "set"),
    )
    basenxp = registry.lookup("mex", "basenxp", "set")
    assert basenxp.write_owners == frozenset({"basenxp"})
    assert basenxp.read_dependencies == frozenset({"mcu"})


def test_every_shortcut_command_resolves_through_registry(monkeypatch):
    observed = []
    registry = cli.get_provider_registry()
    real_lookup = registry.lookup

    def lookup(backend, module, action):
        observed.append((backend, module, action))
        return real_lookup(backend, module, action)

    monkeypatch.setattr(registry, "lookup", lookup)
    for module, cli_action, registry_action in (
        ("uart", "set", "set"),
        ("uart", "add-flexio-channel", "add_flexio_channel"),
        ("platform", "set", "set"), ("basenxp", "set", "set"),
        ("mcl", "set", "set"), ("port", "set", "set"),
        ("dio", "set", "set"), ("mcu", "set", "set"),
        ("adc", "set", "set"),
    ):
        binding = cli._shortcut_binding(
            SimpleNamespace(command=module, action=cli_action)
        )
        assert binding.module == module and binding.action == registry_action
    assert len(observed) == 9
