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
# File:        test_ownership_audit.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Actual XML delta ownership and physical-region audit tests.
# =================================================================================

from __future__ import annotations

from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.ownership import audit_candidate, collect_actual_deltas
from rtd_config.backends.s32_mex.transaction import ConfigureTransaction
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.modules.registry import PhysicalRegion, ProviderBinding
from rtd_config.plan import Plan, PlannedChange
from rtd_config.project import Project
from tests.fixtures import copy_uart_fixture


class _Provider:
    name = "uart"


def _binding(
    *, module="uart", write=("uart",), read=(), regions=None, apply_fn=lambda *_a, **_k: None
):
    provider = type("Provider", (), {"name": module})
    return ProviderBinding(
        backend="mex", module=module, action="set", cli_action="set",
        normalizer=lambda *_a: Intent(module, "set", {}),
        provider_type=provider, apply_fn=apply_fn,
        write_owners=frozenset(write), read_dependencies=frozenset(read),
        allowed_regions=frozenset(
            regions or (PhysicalRegion(module, f"config_set:{module.title()}"),)
        ),
    )


def _plan(*owners):
    return Plan([
        PlannedChange(owner, owner, f"/{owner}", "test") for owner in owners
    ])


_XML = b"""<mex><tools>
<pins><pin name="PTA0" value="A"/></pins>
<clocks><clock_settings><setting name="CORE" value="1"/></clock_settings></clocks>
<periphs><config_set name="Uart"><setting name="Baud" value="9600"/></config_set>
<config_set name="BaseNXP"><setting name="Timer" value="false"/></config_set>
<config_set name="Mcu"><setting name="Clock" value="CORE"/></config_set></periphs>
</tools></mex>"""


def test_actual_delta_ignores_comments_whitespace_attribute_and_element_order():
    equivalent = b"""<mex>\n<!-- ignored --><tools><periphs>
<config_set name="Mcu"><setting value="CORE" name="Clock"/></config_set>
<config_set name="BaseNXP"><setting value="false" name="Timer"/></config_set>
<config_set name="Uart"><setting value="9600" name="Baud"/></config_set></periphs>
<clocks><clock_settings><setting value="1" name="CORE"/></clock_settings></clocks>
<pins><pin value="A" name="PTA0"/></pins></tools></mex>"""
    result = audit_candidate(_XML, equivalent, _binding(), _plan("uart"))
    assert result.entries == ()
    assert result.changed_modules == ()


@pytest.mark.parametrize(
    "candidate,kind",
    [
        (_XML.replace(b'value="9600"', b'value="115200"'), "modified"),
        (_XML.replace(b'/></config_set>', b'>polling</setting></config_set>', 1), "modified"),
        (_XML.replace(
            b'<setting name="Baud" value="9600"/>',
            b'<setting name="Baud" value="9600"/><setting name="Parity" value="NONE"/>',
        ), "added"),
        (_XML.replace(b'<setting name="Baud" value="9600"/>', b''), "removed"),
    ],
)
def test_actual_delta_classifies_attribute_text_element_add_and_remove(candidate, kind):
    entries = collect_actual_deltas(_XML, candidate)
    assert any(item.kind == kind and item.owner == "uart" for item in entries)


def test_actual_delta_preserves_duplicate_siblings_without_collapsing_changes():
    before = b'''<mex><config_set name="Uart">
<setting name="Dup" value="A"/><setting name="Dup" value="B"/>
</config_set></mex>'''
    added = before.replace(
        b'</config_set>', b'<setting name="Dup" value="C"/></config_set>'
    )
    entries = collect_actual_deltas(before, added)
    assert len(entries) == 1
    assert entries[0].kind == "added"
    assert entries[0].owner == "uart"


def test_owner_mapping_is_case_normalized_but_region_identity_is_exact():
    candidate = _XML.replace(b'name="Uart"', b'name="uArT"')
    entries = collect_actual_deltas(_XML, candidate)
    assert entries
    assert {item.owner for item in entries} == {"uart"}
    assert {item.region for item in entries} == {
        "config_set:Uart", "config_set:uArT"
    }


def test_audit_rejects_undeclared_module_and_region():
    changed_mcu = _XML.replace(b'value="CORE"', b'value="FIRC"')
    with pytest.raises(CliFailure) as module_error:
        audit_candidate(_XML, changed_mcu, _binding(), _plan("uart"))
    assert module_error.value.code == "provider_ownership_violation"

    changed_pin = _XML.replace(b'value="A"', b'value="B"')
    broad = _binding(
        write=("uart", "port"),
        regions=(
            PhysicalRegion("uart", "config_set:Uart"),
            PhysicalRegion("port", "config_set:Port"),
        ),
    )
    with pytest.raises(CliFailure) as region_error:
        audit_candidate(_XML, changed_pin, broad, _plan("uart", "port"))
    assert region_error.value.code == "provider_region_violation"


def test_basenxp_mcu_dependency_is_read_only_and_cannot_authorize_write():
    binding = _binding(
        module="basenxp", write=("basenxp",), read=("mcu",),
        regions=(PhysicalRegion("basenxp", "config_set:BaseNXP"),),
    )
    changed = _XML.replace(b'value="CORE"', b'value="FIRC"')
    with pytest.raises(CliFailure) as caught:
        audit_candidate(_XML, changed, binding, _plan("basenxp", "mcu"))
    assert caught.value.code == "provider_ownership_violation"


def test_pins_and_clocks_map_to_explicit_physical_regions():
    binding = _binding(
        write=("uart", "port", "mcu"),
        regions=(
            PhysicalRegion("uart", "config_set:Uart"),
            PhysicalRegion("port", "Pins/Port"),
            PhysicalRegion("mcu", "Clocks/clock_settings"),
        ),
    )
    changed = _XML.replace(b'value="A"', b'value="B"').replace(
        b'name="CORE" value="1"', b'name="CORE" value="2"'
    )
    result = audit_candidate(_XML, changed, binding, _plan("uart", "port", "mcu"))
    assert {(item.owner, item.region) for item in result.entries} == {
        ("port", "Pins/Port"), ("mcu", "Clocks/clock_settings")
    }


@pytest.mark.parametrize(
    "owner,old,new",
    [
        ("mcu", b'value="CORE"', b'value="FIRC"'),
        ("port", b'value="PORT_OLD"', b'value="PORT_NEW"'),
        ("platform", b'value="PLATFORM_OLD"', b'value="PLATFORM_NEW"'),
        ("mcl", b'value="MCL_OLD"', b'value="MCL_NEW"'),
    ],
)
def test_uart_binding_authorizes_each_plan_declared_cross_module_write(owner, old, new):
    before = _XML.replace(
        b'</periphs>',
        b'<config_set name="Port"><setting name="P" value="PORT_OLD"/></config_set>'
        b'<config_set name="Platform"><setting name="P" value="PLATFORM_OLD"/></config_set>'
        b'<config_set name="Mcl"><setting name="P" value="MCL_OLD"/></config_set>'
        b'</periphs>',
    )
    binding = cli.get_provider_registry().lookup("mex", "uart", "set")
    result = audit_candidate(before, before.replace(old, new), binding, _plan("uart", owner))
    assert result.changed_modules == (owner,)


def _prepared_project(tmp_path):
    project = Project.verified(copy_uart_fixture(tmp_path))
    cli._preflight_project(project)
    return project


def _passed_static(*_args, **_kwargs):
    return SimpleNamespace(status="passed", diagnostics=[])


def _change_first_setting(doc, config_name, value):
    config = doc.find_config_set(config_name)
    setting = next(item for item in config.iter() if item.tag.endswith("setting"))
    setting.attrib["value"] = value
    return setting


def test_transaction_uses_actual_delta_not_apply_self_report(tmp_path):
    project = _prepared_project(tmp_path)
    intent = Intent("uart", "set", {})
    plan = _plan("uart")

    def lying_apply(doc, _intent, *, bundle):
        element = _change_first_setting(doc, "Uart", "OWNERSHIP_AUDIT_VALUE")
        return ApplyResult(changed_modules=["mcu"], modified_elements=[element])

    binding = _binding(apply_fn=lying_apply)
    result = ConfigureTransaction(
        project, plan=plan, binding=binding, static_runner=_passed_static
    ).execute(intent, binding.apply_fn)
    assert result.changed_modules == ["uart"]


def test_transaction_recovers_omitted_self_report_from_published_bytes(tmp_path):
    project = _prepared_project(tmp_path)

    def silent_apply(doc, _intent, *, bundle):
        element = _change_first_setting(doc, "Uart", "ACTUAL_ONLY")
        return ApplyResult(changed_modules=[], modified_elements=[element])

    binding = _binding(apply_fn=silent_apply)
    result = ConfigureTransaction(
        project, plan=_plan("uart"), binding=binding, static_runner=_passed_static
    ).execute(Intent("uart", "set", {}), binding.apply_fn)
    assert result.changed_modules == ["uart"]
    assert result.published_bytes == project.mex_file.read_bytes()


def test_transaction_self_reported_change_on_noop_is_empty(tmp_path):
    project = _prepared_project(tmp_path)
    binding = _binding(apply_fn=lambda *_a, **_k: ApplyResult(changed_modules=["uart"]))
    result = ConfigureTransaction(
        project, plan=_plan("uart"), binding=binding, static_runner=_passed_static
    ).execute(Intent("uart", "set", {}), binding.apply_fn)
    assert result.no_op is True
    assert result.changed_modules == []


def test_transaction_blocks_unauthorized_apply_before_static_or_publish(tmp_path):
    project = _prepared_project(tmp_path)
    original = project.mex_file.read_bytes()
    static_called = False
    vendor_called = False

    def malicious(doc, _intent, *, bundle):
        element = _change_first_setting(doc, "Mcu", "UNAUTHORIZED")
        return ApplyResult(changed_modules=["basenxp"], modified_elements=[element])

    def static(*_args, **_kwargs):
        nonlocal static_called
        static_called = True
        return _passed_static()

    def vendor(**_kwargs):
        nonlocal vendor_called
        vendor_called = True
        return SimpleNamespace(status="passed")

    binding = _binding(
        module="basenxp", write=("basenxp",), read=("mcu",),
        regions=(PhysicalRegion("basenxp", "config_set:BaseNXP"),),
        apply_fn=malicious,
    )
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, plan=_plan("basenxp", "mcu"), binding=binding,
            static_runner=static, vendor_runner=vendor,
        ).execute(Intent("basenxp", "set", {}), binding.apply_fn)
    assert caught.value.code == "provider_ownership_violation"
    assert static_called is False
    assert vendor_called is False
    assert project.mex_file.read_bytes() == original


def test_transaction_blocks_undeclared_physical_region_before_validation(tmp_path):
    project = _prepared_project(tmp_path)
    original = project.mex_file.read_bytes()
    calls = {"static": 0, "vendor": 0}

    def edit_pin(doc, _intent, *, bundle):
        pin = next(item for item in doc.root.iter() if item.tag.endswith("pin"))
        pin.attrib["signal"] = "UNDECLARED_REGION"
        return ApplyResult(changed_modules=["port"], modified_elements=[pin])

    binding = _binding(
        module="port", write=("port",),
        regions=(PhysicalRegion("port", "config_set:Port"),),
        apply_fn=edit_pin,
    )
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, plan=_plan("port"), binding=binding,
            static_runner=lambda *_a, **_k: calls.__setitem__("static", 1),
            vendor_runner=lambda **_k: calls.__setitem__("vendor", 1),
        ).execute(Intent("port", "set", {}), binding.apply_fn)
    assert caught.value.code == "provider_region_violation"
    assert calls == {"static": 0, "vendor": 0}
    assert project.mex_file.read_bytes() == original
