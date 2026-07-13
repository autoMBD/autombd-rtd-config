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
# File:        test_configure_transaction.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Verify atomic, fail-closed configure transaction behavior.
# =================================================================================

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.transaction import ConfigureTransaction
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.project import Project
from tests.fixtures import copy_uart_fixture


def _prepared_project(tmp_path: Path) -> Project:
    project = Project.verified(copy_uart_fixture(tmp_path))
    cli._preflight_project(project)
    return project


def _intent() -> Intent:
    return Intent.from_dict({"module": "test", "action": "set", "payload": {}})


def _edit(doc, _intent, *, bundle) -> ApplyResult:
    assert bundle is not None
    doc.root.attrib["transaction-test"] = "changed"
    return ApplyResult(changed_modules=["uart"])


def _passed_static(*_args, **_kwargs):
    return SimpleNamespace(status="passed", diagnostics=[], to_dict=lambda: {"status": "passed"})


def test_static_checks_actual_same_directory_candidate_before_publish(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    observed = {}

    def inspect_candidate(path, *, doc, verified_target, bundle, **_kwargs):
        observed["path"] = path
        assert path.parent == mex.parent
        assert path != mex
        assert doc._raw == path.read_bytes()
        assert b'transaction-test="changed"' in doc._raw
        assert mex.read_bytes() == original
        assert verified_target is project.verified_target
        assert bundle is project.asset_bundle
        return _passed_static()

    try:
        result = ConfigureTransaction(project, static_runner=inspect_candidate).execute(
            _intent(), _edit
        )
        assert result.status == "passed"
        assert mex.read_bytes() == result.published_bytes
        assert not observed["path"].exists()
    finally:
        project.close()


def test_target_swap_during_static_is_not_overwritten(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    attacker = b"<attacker/>\n"

    def swap_target(*_args, **_kwargs):
        replacement = mex.with_name("attacker.mex")
        replacement.write_bytes(attacker)
        project.close()
        os.replace(replacement, mex)
        return _passed_static()

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=swap_target).execute(_intent(), _edit)
    assert caught.value.code == "project_target_changed"
    assert mex.read_bytes() == attacker
    assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))


def test_release_window_swap_is_detected_and_attacker_survives(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    attacker = b"<attacker/>\n"

    def release_then_swap(target):
        expectation = cli.release_for_publish(target)
        replacement = mex.with_name("attacker.mex")
        replacement.write_bytes(attacker)
        os.replace(replacement, mex)
        return expectation

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=_passed_static, release_for_publish_fn=release_then_swap
        ).execute(_intent(), _edit)
    assert caught.value.code == "project_target_changed"
    assert mex.read_bytes() == attacker


def test_backup_uses_original_snapshot_bytes(tmp_path):
    project = _prepared_project(tmp_path)
    original = project.verified_target.mex.content
    mex = project.mex_file
    result = ConfigureTransaction(
        project, backup=True, static_runner=_passed_static
    ).execute(_intent(), _edit)
    assert result.status == "passed"
    assert mex.with_name(mex.name + ".bak").read_bytes() == original


def test_noop_does_not_stage_backup_or_replace(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()

    def no_change(_doc, _intent, *, bundle):
        return ApplyResult(changed_modules=["uart"])

    def forbidden(*_args, **_kwargs):
        pytest.fail("no-op attempted validation or publication")

    try:
        result = ConfigureTransaction(
            project,
            backup=True,
            static_runner=forbidden,
            replace_fn=forbidden,
            release_for_publish_fn=forbidden,
        ).execute(_intent(), no_change)
        assert result.status == "passed"
        assert result.changed_modules == []
        assert result.published_bytes == original
        assert not mex.with_name(mex.name + ".bak").exists()
        assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))
    finally:
        project.close()


def test_replace_failure_is_typed_and_staging_is_cleaned(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()

    def fail_replace(_source, _target):
        raise OSError("injected replace failure")

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=_passed_static, replace_fn=fail_replace
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_publish_failed"
    assert mex.read_bytes() == original
    assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))
