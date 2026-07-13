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
import stat
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.target import (
    FileIdentity,
    FileSnapshot,
    PublishExpectation,
    atomic_publish_candidate,
    default_target_platform,
)
from rtd_config.backends.s32_mex.transaction import ConfigureTransaction
import rtd_config.backends.s32_mex.transaction as transaction_module
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
    doc.root.attrib["uuid"] = "00000000-0000-0000-0000-000000000067"
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
        assert b'uuid="00000000-0000-0000-0000-000000000067"' in doc._raw
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
        pytest.fail("no-op attempted publication")

    try:
        result = ConfigureTransaction(
            project,
            backup=True,
            static_runner=_passed_static,
            atomic_publish_fn=forbidden,
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

    def fail_replace(*_args, **_kwargs):
        raise OSError("injected replace failure")

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=_passed_static, atomic_publish_fn=fail_replace
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_publish_failed"
    assert mex.read_bytes() == original
    assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))


def test_precreated_staging_symlink_is_never_followed_or_overwritten(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    outside = tmp_path / "outside-staging"
    outside.write_bytes(b"attacker")
    staging = mex.parent / f".{mex.name}.candidate.sentinel.tmp"
    try:
        staging.symlink_to(outside)
    except OSError as exc:
        project.close()
        pytest.skip(f"staging symlink creation unavailable: {exc}")
    monkeypatch.setattr(transaction_module.secrets, "token_hex", lambda _size: "sentinel")

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )
    assert caught.value.code == "configure_staging_failed"
    assert outside.read_bytes() == b"attacker"


def test_vendor_pass_cannot_publish_after_auxiliary_metadata_drift(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    source = project.root / ".project"

    def mutate_auxiliary(**_kwargs):
        source.write_bytes(source.read_bytes() + b"\n")
        return _passed_static()

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            static_runner=_passed_static,
            vendor_runner=mutate_auxiliary,
        ).execute(_intent(), _edit)
    assert caught.value.code == "project_metadata_source_changed"
    assert mex.read_bytes() == original


@pytest.mark.parametrize("relative", [
    ".project",
    ".cproject",
    ".settings/com.freescale.s32ds.cross.sdk.support.prefs",
    ".settings/com.nxp.s32ds.cle.runtime.component.prefs",
])
@pytest.mark.parametrize("operation", ["modify", "swap", "delete", "recreate"])
def test_auxiliary_change_after_release_is_rejected_before_publish(
    tmp_path, relative, operation
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    source = project.root / relative
    original_source = source.read_bytes()

    def release_then_mutate(target):
        expectation = cli.release_for_publish(target)
        if operation == "modify":
            source.write_bytes(original_source + b"\n")
        elif operation == "swap":
            replacement = source.with_name(source.name + ".replacement")
            replacement.write_bytes(original_source + b"\n")
            os.replace(replacement, source)
        elif operation == "delete":
            source.unlink()
        else:
            source.unlink()
            source.write_bytes(original_source)
        return expectation

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=_passed_static,
            release_for_publish_fn=release_then_mutate,
        ).execute(_intent(), _edit)
    assert caught.value.code == "project_metadata_source_changed"
    assert mex.read_bytes() == original


def test_candidate_changed_after_validation_is_restored_without_publish(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()

    def mutate_validated_candidate(path, **_kwargs):
        path.write_bytes(b"<attacker-candidate/>")
        return _passed_static()

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=mutate_validated_candidate
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_staging_changed"
    assert mex.read_bytes() == original
    assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))


def test_vendor_observes_exact_validated_candidate_bytes(tmp_path):
    project = _prepared_project(tmp_path)
    observed = {}

    def vendor(*, staging, document, project, bundle):
        observed["bytes"] = staging.read_bytes()
        assert document._raw == observed["bytes"]
        assert bundle is project.asset_bundle
        return _passed_static()

    result = ConfigureTransaction(
        project, static_runner=_passed_static, vendor_runner=vendor
    ).execute(_intent(), _edit)
    assert observed["bytes"] == result.published_bytes


def test_transaction_closes_target_lease_exactly_once(monkeypatch, tmp_path):
    project = _prepared_project(tmp_path)
    calls = 0
    target = project.verified_target
    target_type = type(target)
    original_close = target_type.close

    def counted_close(self):
        nonlocal calls
        if self is target:
            calls += 1
        original_close(self)

    monkeypatch.setattr(target_type, "close", counted_close)
    ConfigureTransaction(project, static_runner=_passed_static).execute(
        _intent(), _edit
    )
    assert calls == 1


def test_linked_backup_target_is_rejected_before_target_publish(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    backup.write_bytes(b"attacker")
    real_lstat = os.lstat

    def linked_lstat(path):
        status = real_lstat(path)
        if Path(path) == backup:
            return SimpleNamespace(
                st_mode=stat.S_IFLNK,
                st_file_attributes=getattr(status, "st_file_attributes", 0),
            )
        return status

    monkeypatch.setattr(os, "lstat", linked_lstat)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static
        ).execute(_intent(), _edit)
    assert caught.value.code == "unsafe_backup_target"
    assert mex.read_bytes() == original
    assert backup.read_bytes() == b"attacker"


def test_real_symlink_backup_target_is_rejected_and_target_preserved(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    outside = tmp_path / "outside-backup"
    outside.write_bytes(b"attacker")
    try:
        backup.symlink_to(outside)
    except OSError as exc:
        project.close()
        pytest.skip(f"backup symlink creation unavailable: {exc}")

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static
        ).execute(_intent(), _edit)
    assert caught.value.code == "unsafe_backup_target"
    assert mex.read_bytes() == original
    assert outside.read_bytes() == b"attacker"


def test_keyboard_interrupt_closes_lease_and_cleans_staging(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        ConfigureTransaction(project, static_runner=interrupt).execute(_intent(), _edit)
    assert project.verified_target.lease.closed
    assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))


def test_cleanup_failure_is_typed_without_publishing(monkeypatch, tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    real_unlink = Path.unlink

    def fail_staging_cleanup(path, *args, **kwargs):
        if path.name.startswith(f".{mex.name}.candidate."):
            raise OSError("injected cleanup failure")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_staging_cleanup)
    blocked = SimpleNamespace(status="blocked", diagnostics=[])
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=lambda *_args, **_kwargs: blocked
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_cleanup_failed"
    assert mex.read_bytes() == original
    for staging in mex.parent.glob(f".{mex.name}.*.tmp"):
        real_unlink(staging)


class _CapturePlatform:
    def __init__(self, target: Path, staging: Path) -> None:
        self.target = target
        self.staging = staging
        self.files = {
            target: (FileIdentity(1, 1, None), b"original"),
            staging: (FileIdentity(1, 2, None), b"candidate"),
        }
        self.inject_at_exchange = False
        self.restore_fails = False

    def snapshot_file(self, path: Path) -> FileSnapshot:
        identity, content = self.files[path]
        import hashlib

        return FileSnapshot(
            path, identity, len(content), 1, 1,
            hashlib.sha256(content).hexdigest(), content,
        )

    def exchange_capture(self, replacement: Path, target: Path, capture: Path) -> Path:
        if self.inject_at_exchange:
            self.inject_at_exchange = False
            self.files[target] = (FileIdentity(1, 3, None), b"attacker")
        displaced = self.files.pop(target)
        self.files[target] = self.files.pop(replacement)
        self.files[capture] = displaced
        return capture

    def restore_capture(self, target: Path, capture: Path, rescue: Path) -> Path:
        if self.restore_fails:
            raise OSError("injected restore failure")
        self.files[rescue] = self.files.pop(target)
        self.files[target] = self.files.pop(capture)
        return rescue


def _capture_expectation(platform: _CapturePlatform) -> PublishExpectation:
    original = platform.snapshot_file(platform.target)
    return PublishExpectation(original.path, original.identity, original.sha256)


def test_atomic_adapter_captures_syscall_window_swap_and_restores_attacker(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expectation = _capture_expectation(platform)
    platform.inject_at_exchange = True

    with pytest.raises(CliFailure) as caught:
        atomic_publish_candidate(
            expectation,
            staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=platform,
        )
    assert caught.value.code == "project_target_changed"
    assert platform.files[target][1] == b"attacker"
    assert b"original" not in [content for _, content in platform.files.values()]


def test_atomic_adapter_restore_failure_is_typed_and_preserves_displaced_attacker(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expectation = _capture_expectation(platform)
    platform.inject_at_exchange = True
    platform.restore_fails = True

    with pytest.raises(CliFailure) as caught:
        atomic_publish_candidate(
            expectation,
            staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=platform,
        )
    assert caught.value.code == "configure_publish_restore_failed"
    assert b"attacker" in [content for _, content in platform.files.values()]


def test_atomic_adapter_is_mandatory(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expectation = _capture_expectation(platform)
    unsupported = SimpleNamespace(snapshot_file=platform.snapshot_file)
    with pytest.raises(CliFailure) as caught:
        atomic_publish_candidate(
            expectation,
            staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=unsupported,
        )
    assert caught.value.code == "configure_atomic_publish_unavailable"


@pytest.mark.skipif(os.name != "nt", reason="Windows ReplaceFileW capture test")
def test_real_windows_adapter_restores_destination_swapped_at_syscall(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    attacker = tmp_path / "attacker.mex"
    target.write_bytes(b"original")
    staging.write_bytes(b"candidate")
    attacker.write_bytes(b"attacker")
    inner = default_target_platform()
    original = inner.snapshot_file(target)
    expectation = PublishExpectation(target, original.identity, original.sha256)

    class InjectAtSyscall:
        snapshot_file = staticmethod(inner.snapshot_file)
        restore_capture = staticmethod(inner.restore_capture)

        @staticmethod
        def exchange_capture(replacement, destination, capture):
            os.replace(attacker, destination)
            return inner.exchange_capture(replacement, destination, capture)

    with pytest.raises(CliFailure) as caught:
        atomic_publish_candidate(
            expectation,
            staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=InjectAtSyscall(),
        )
    assert caught.value.code == "project_target_changed"
    assert target.read_bytes() == b"attacker"
    assert not list(tmp_path.glob(".project.mex.*.tmp"))
