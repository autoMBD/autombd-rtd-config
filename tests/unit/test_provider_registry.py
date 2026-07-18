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
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange, TargetSelector
from rtd_config.project import Project
from rtd_config.modules.registry import (
    PhysicalRegion,
    ProviderBinding,
    ProviderRegistry,
    validate_provider_plan,
)


ROOT = Path(__file__).resolve().parents[2]
UART = ROOT / "tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344"


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


def test_runtime_plan_rejects_empty_or_non_concrete_write_targets():
    binding = _binding()
    for targets in (
        (),
        (TargetSelector("", ("Uart",)),),
        (TargetSelector("config_set:Uart", ()),),
        (TargetSelector("config_set:Uart", ("*",)),),
        (TargetSelector("config_set:*", ("Uart",)),),
        (TargetSelector("config_set:Uart", ("Uart?",)),),
        (TargetSelector("config_set:Uart", ("Uart[0]",)),),
        (TargetSelector("config_set:Uart", ("Uart{0}",)),),
        (TargetSelector("config_set:Uart", ("Uart.name",)),),
        (TargetSelector("config_set:Uart", ("Uart/name",)),),
        (TargetSelector("config_set:Uart", (r"Uart\name",)),),
        (TargetSelector("config_set:Uart", ("Uart\x00name",)),),
        (TargetSelector("config_set:Uart", ("Uart",), (("name", "*"),)),),
        (TargetSelector("config_set:Uart", ("Uart",), (("na?me", "safe"),)),),
    ):
        with pytest.raises(CliFailure) as caught:
            validate_provider_plan(Plan([
                PlannedChange("uart", "uart", "/Uart", "invalid", targets=targets)
            ]), binding=binding)
        assert caught.value.code == "provider_plan_invalid"


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


def test_direct_namespace_shortcut_keeps_explicit_binding_through_configure(monkeypatch):
    observed = {}

    def configure(_args, _intent, _plan, _apply_fn, _project, **kwargs):
        observed["binding"] = kwargs["binding"]
        return 0

    monkeypatch.setattr(cli, "_configure_verified_project", configure)
    args = SimpleNamespace(project=UART, configure=True, backup=False)

    assert cli.cmd_mcl_set(args) == 0
    assert observed["binding"].module == "mcl"
    assert observed["binding"].action == "set"


def test_shortcut_passes_registry_free_selection_to_canonical_dispatcher(monkeypatch):
    observed = {}

    def execute(_config, **kwargs):
        observed["binding"] = kwargs["binding"]
        return 0

    monkeypatch.setattr(cli, "_execute_canonical_request", execute)

    assert cli.cmd_mcl_set(SimpleNamespace(project=UART, configure=False)) == 0
    assert observed["binding"].key == ("mex", "mcl", "set")


def test_generic_registry_lookup_waits_until_asset_preflight(monkeypatch, tmp_path):
    intent = tmp_path / "intent.json"
    intent.write_text(
        json.dumps({"module": "mcl", "action": "set", "payload": {}}),
        encoding="utf-8",
    )

    class RejectingResolver:
        def __init__(self, _root):
            pass

        def resolve(self, _metadata):
            raise CliFailure("asset_bundle_unsupported", "unsupported")

    monkeypatch.setattr(cli, "AssetBundleResolver", RejectingResolver)
    monkeypatch.setattr(
        cli, "get_provider_registry",
        lambda: pytest.fail("registry constructed before asset preflight"),
    )

    with pytest.raises(CliFailure) as caught:
        cli._run_generic(SimpleNamespace(
            command="plan", project=UART, intent=str(intent),
        ))
    assert caught.value.code == "asset_bundle_unsupported"


def test_asset_preflight_revalidates_observed_metadata(monkeypatch):
    observed = []
    monkeypatch.setattr(
        cli, "revalidate_project_metadata",
        lambda target, metadata: observed.append((target, metadata)),
    )
    with Project.verified(UART) as project:
        cli._preflight_project(project, revalidate_metadata=True)
        assert observed == [(project.verified_target, project.metadata)]


@pytest.mark.parametrize(
    "command_name",
    [
        "cmd_uart_set", "cmd_uart_add_flexio_channel", "cmd_platform_set",
        "cmd_basenxp_set", "cmd_mcl_set", "cmd_port_set", "cmd_dio_set",
        "cmd_mcu_set", "cmd_adc_set",
    ],
)
def test_shortcut_preflight_classifies_lease_swap_as_target_changed(
    monkeypatch, command_name
):
    projects = []
    original_verified = cli.Project.verified
    original_resolver = cli.AssetBundleResolver

    def tracked_verified(root, backend="s32-mex"):
        project = original_verified(root, backend)
        projects.append(project)
        return project

    class SwapAfterResolve:
        def __init__(self, root):
            self._delegate = original_resolver(root)

        def resolve(self, metadata):
            bundle = self._delegate.resolve(metadata)
            projects[-1].close()
            return bundle

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    monkeypatch.setattr(cli, "AssetBundleResolver", SwapAfterResolve)

    with pytest.raises(CliFailure) as caught:
        getattr(cli, command_name)(
            SimpleNamespace(project=UART, configure=False, backup=False)
        )
    assert caught.value.code == "project_target_changed"


def test_caller_reusing_closed_project_keeps_target_closed_classification():
    project = Project.verified(UART)
    project.close()
    with pytest.raises(CliFailure) as caught:
        cli._preflight_project(project, revalidate_metadata=True)
    assert caught.value.code == "project_target_closed"
