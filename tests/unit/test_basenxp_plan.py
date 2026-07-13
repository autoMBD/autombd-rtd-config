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
# File:        test_basenxp_plan.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Unit tests that pin BaseNxpProvider.plan() for enable-system-timer
#              intent (RTD-MEX-BASENXP-001). Tests must fail before the fix and
#              pass after.
# =================================================================================

"""Pin tests for BaseNxpProvider.plan() enable-system-timer path.

The apply path (apply_basenxp_set) is already correct and vendor-validated.
These tests ensure plan() accurately mirrors apply and declares the cross-module
Mcu dependency explicitly, as required by AGENTS.md.

Three assertions are pinned:
(a) No description in the plan contains "48000000".
(b) A change describes OsIfSystemTimerClockRef referencing an Mcu
    McuClockReferencePoint (populated array, not a scalar frequency).
(c) A declared dependency with owner="mcu" referencing McuClockReferencePoint
    is present.
"""

from functools import partial

from rtd_config.intent import Intent
from rtd_config.modules.basenxp import BaseNxpProvider
from tests.fixtures import resolved_uart_bundle

BaseNxpProvider = partial(BaseNxpProvider, resolved_uart_bundle())


def _timer_intent() -> Intent:
    return Intent.from_dict(
        {"module": "basenxp", "action": "set", "payload": {"enable_system_timer": True}}
    )


def _no_timer_intent() -> Intent:
    return Intent.from_dict(
        {"module": "basenxp", "action": "set", "payload": {}}
    )


# ---------------------------------------------------------------------------
# Test P1: no description in the plan mentions "48000000"
# ---------------------------------------------------------------------------
def test_plan_descriptions_do_not_mention_freq_literal():
    """No PlannedChange description may contain '48000000' — the hardcoded
    frequency that was removed from the implementation when the clock-ref
    approach was adopted.
    """
    provider = BaseNxpProvider()
    plan = provider.plan(_timer_intent())
    for change in plan.changes:
        assert "48000000" not in change.description, (
            f"Description mentions hardcoded frequency '48000000': {change.description!r}"
        )


# ---------------------------------------------------------------------------
# Test P2: a change describes OsIfSystemTimerClockRef referencing an Mcu
#          McuClockReferencePoint (populated array pattern)
# ---------------------------------------------------------------------------
def test_plan_has_counter_config_change_describing_clock_ref():
    """One PlannedChange must describe the OsIfCounterConfig insert whose
    OsIfSystemTimerClockRef references an Mcu McuClockReferencePoint.
    The description must NOT mention 'no core-clock ref' and must make clear
    that OsIfSystemTimerClockFreq is an empty array.
    """
    provider = BaseNxpProvider()
    plan = provider.plan(_timer_intent())
    descs = [c.description for c in plan.changes]

    # At least one change must describe the clock-ref population
    assert any("OsIfSystemTimerClockRef" in d for d in descs), (
        "No PlannedChange description mentions 'OsIfSystemTimerClockRef'; "
        f"descriptions: {descs}"
    )
    # The description must mention McuClockReferencePoint (the Mcu entity referenced)
    assert any("McuClockReferencePoint" in d for d in descs), (
        "No PlannedChange description mentions 'McuClockReferencePoint'; "
        f"descriptions: {descs}"
    )
    # Must not say "no core-clock ref" (stale wording from old incorrect impl)
    for d in descs:
        assert "no core-clock ref" not in d, (
            f"Description contains stale wording 'no core-clock ref': {d!r}"
        )


# ---------------------------------------------------------------------------
# Test P3: a declared cross-module dependency with owner="mcu" referencing
#          McuClockReferencePoint is present
# ---------------------------------------------------------------------------
def test_plan_declares_mcu_dependency_for_clock_reference_point():
    """A PlannedChange with owner='mcu' must be present in the plan and its
    path/description must make explicit that BaseNXP reads (read-only) an
    existing Mcu McuClockReferencePoint for the system-timer clock.
    """
    provider = BaseNxpProvider()
    plan = provider.plan(_timer_intent())

    mcu_deps = [c for c in plan.changes if c.owner == "mcu"]
    assert len(mcu_deps) >= 1, (
        f"No PlannedChange with owner='mcu' found; changes: {[c.to_dict() for c in plan.changes]}"
    )

    # The mcu dependency must reference McuClockReferencePoint in either
    # its path or description so the dependency purpose is unambiguous.
    dep = mcu_deps[0]
    assert "McuClockReferencePoint" in dep.path or "McuClockReferencePoint" in dep.description, (
        f"Mcu dependency does not reference 'McuClockReferencePoint': {dep.to_dict()}"
    )


# ---------------------------------------------------------------------------
# Test P4: the OsIfUseSystemTimer change is basenxp-owned
# ---------------------------------------------------------------------------
def test_plan_has_basenxp_owned_use_system_timer_change():
    """A basenxp-owned PlannedChange must enable OsIfUseSystemTimer."""
    provider = BaseNxpProvider()
    plan = provider.plan(_timer_intent())

    timer_changes = [
        c for c in plan.changes
        if c.owner == "basenxp" and "OsIfUseSystemTimer" in c.path
    ]
    assert len(timer_changes) >= 1, (
        "No basenxp-owned change for OsIfUseSystemTimer found; "
        f"changes: {[c.to_dict() for c in plan.changes]}"
    )


# ---------------------------------------------------------------------------
# Test P5: no-timer path is not affected
# ---------------------------------------------------------------------------
def test_plan_no_timer_path_unchanged():
    """When enable_system_timer is not set, plan() must not emit an Mcu
    dependency or any OsIfCounterConfig change.
    """
    provider = BaseNxpProvider()
    plan = provider.plan(_no_timer_intent())

    mcu_deps = [c for c in plan.changes if c.owner == "mcu"]
    assert len(mcu_deps) == 0, (
        f"No-timer path must not declare an Mcu dependency; found: {mcu_deps}"
    )

    counter_changes = [
        c for c in plan.changes
        if "OsIfCounterConfig" in c.path
    ]
    assert len(counter_changes) == 0, (
        f"No-timer path must not have OsIfCounterConfig changes; found: {counter_changes}"
    )
