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

from dataclasses import replace
import hashlib
import inspect
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.target import (
    AtomicPublishFailure,
    AtomicPublishState,
    FileIdentity,
    FileSnapshot,
    PublishExpectation,
    atomic_publish_candidate,
    default_target_platform,
    discard_owned_path,
)
from rtd_config.backends.s32_mex.transaction import ConfigureTransaction
from rtd_config.backends.s32_mex.validation import run_validation
import rtd_config.backends.s32_mex.target as target_module
import rtd_config.backends.s32_mex.metadata as metadata_module
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


def _path_record(path: Path):
    status = os.lstat(path)
    identity = (status.st_dev, status.st_ino) if status.st_ino else None
    if stat.S_ISLNK(status.st_mode):
        return ("link", identity, os.readlink(path))
    if stat.S_ISREG(status.st_mode):
        return ("file", identity, path.read_bytes())
    return ("directory", identity, None)


def _directory_inventory(root: Path):
    return {
        path.relative_to(root).as_posix(): _path_record(path)
        for path in sorted(root.rglob("*"))
    }


def _assert_failure_has_no_path_leak(failure: CliFailure, root: Path) -> None:
    def strings(value):
        if isinstance(value, dict) or hasattr(value, "items"):
            for key, item in value.items():
                if key == "preserved":
                    assert all(Path(name).name == name for name in item)
                yield str(key)
                yield from strings(item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                yield from strings(item)
        elif isinstance(value, (str, Path)):
            yield str(value)

    roots = {str(root.resolve()), root.resolve().as_posix()}
    for text in strings({"message": failure.message, "details": failure.details}):
        assert not any(value in text for value in roots)
        assert not Path(text).is_absolute()


def test_static_checks_actual_same_directory_candidate_before_publish(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    observed = {"seam": 0}

    def reject_backup(*_args): observed["seam"] += 1; pytest.fail("backup=False reached absent-backup seam")

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
        result = ConfigureTransaction(project, static_runner=inspect_candidate, backup_install_absent_fn=reject_backup).execute(
            _intent(), _edit
        )
        assert result.status == "passed"
        assert mex.read_bytes() == result.published_bytes
        assert observed["seam"] == 0 and not mex.with_name(mex.name + ".bak").exists()
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


def test_absent_backup_seam_and_real_helper_own_publication_state(
    monkeypatch, tmp_path
):
    constructor = inspect.signature(ConfigureTransaction).parameters
    assert tuple(constructor) == ("project", "plan", "binding", "backup", "static_runner", "vendor_runner", "atomic_publish_fn", "release_for_publish_fn", "backup_install_absent_fn")
    dependency = constructor["backup_install_absent_fn"]
    assert (dependency.kind, dependency.default, dependency.annotation) == (inspect.Parameter.KEYWORD_ONLY, None, "Callable[[Path, Path], None] | None")
    helper = inspect.signature(target_module.atomic_install_absent).parameters
    assert tuple(helper) == ("path", "staging", "candidate_sha256", "platform", "install_fn")
    assert (helper["install_fn"].kind, helper["install_fn"].default, helper["install_fn"].annotation) == (inspect.Parameter.KEYWORD_ONLY, None, "Callable[[Path, Path], None] | None")

    platform = default_target_platform()
    destination, candidate = tmp_path / "backup.mex", tmp_path / "candidate.tmp"
    destination.write_bytes(b"external")
    called = []
    with pytest.raises(CliFailure) as conflict:
        target_module.atomic_install_absent(
            destination, candidate, "unused", platform, install_fn=lambda *args: called.append(args)
        )
    assert conflict.value.code == "configure_backup_changed"
    assert called == []

    destination.unlink()
    candidate.write_bytes(b"candidate")
    expected_sha = hashlib.sha256(b"candidate").hexdigest()
    observed = []
    def snapshot_file(path): observed.append(("snapshot", path)); return platform.snapshot_file(path)
    def install_absent(source, target):
        observed.append(("install", source, target))
        platform.install_absent(source, target)
        return target_module.AtomicPublishResult(FileSnapshot(target, FileIdentity(None, None, None), 0, 0, 0, "forged", b""), None, None, AtomicPublishState(target, source))
    spy = SimpleNamespace(install_absent=install_absent, snapshot_file=snapshot_file)
    result = target_module.atomic_install_absent(destination, candidate, expected_sha, spy)
    assert observed == [("snapshot", candidate), ("install", candidate, destination), ("snapshot", destination)]
    assert result.state is not None and result.state.phase == "published"
    assert result.published == result.state.published
    assert result.published.sha256 == expected_sha

    destination.unlink()
    candidate.write_bytes(b"candidate")
    snapshot = platform.snapshot_file
    monkeypatch.setattr(platform, "snapshot_file", lambda path: (_ for _ in ()).throw(OSError()) if path == destination else snapshot(path))
    with pytest.raises(AtomicPublishFailure) as uncertain:
        target_module.atomic_install_absent(
            destination, candidate, expected_sha, platform,
            install_fn=platform.install_absent,
        )
    assert uncertain.value.code == "configure_backup_uncertain"
    assert uncertain.value.state.phase == "installed"
    assert uncertain.value.state.destination == destination
    monkeypatch.setattr(platform, "snapshot_file", snapshot)


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
            backup=False,
            static_runner=_passed_static,
            atomic_publish_fn=forbidden,
            release_for_publish_fn=forbidden,
            backup_install_absent_fn=forbidden,
        ).execute(_intent(), no_change)
        assert result.status == "passed"
        assert result.changed_modules == []
        assert result.published_bytes == original
        assert result.published is False
        if os.name == "nt":
            assert result.cleanup_warnings == []
        else:
            assert len(result.cleanup_warnings) == 1
            warning = result.cleanup_warnings[0]
            assert warning["code"] == "configure_cleanup_residual"
            preserved = warning["details"]["preserved"]
            assert len(preserved) == 1
            assert Path(preserved[0]).name == preserved[0]
            residual = mex.parent / preserved[0]
            assert residual.read_bytes() == original
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


def test_vendor_validation_uses_controlled_candidate_copy_before_publish(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    control = tmp_path / "controlled-validation"
    observed = {}

    class FakeRunner:
        def run(self, argv, *, cwd, env, timeout_s):
            load = Path(argv[argv.index("-Load") + 1])
            export = Path(argv[argv.index("-ExportSrc") + 1])
            observed["validated"] = load.read_bytes()
            assert load != mex and load.is_relative_to(control)
            load.write_bytes(b"vendor-mutated-copy")
            (export / "generated.c").write_bytes(b"generated")
            return SimpleNamespace(
                exit_code=0, stdout="", stderr="", code="process_exit",
                timed_out=False, stdout_truncated=False, stderr_truncated=False,
            )

    def vendor(*, staging, document, project, bundle):
        outcome = run_validation(
            project.root, Path("C:/NXP/S32DS.3.6.7"),
            workspace=control, mex_file=staging, runner=FakeRunner(),
        )
        return SimpleNamespace(status="passed" if outcome.passed else "blocked")

    result = ConfigureTransaction(
        project, static_runner=_passed_static, vendor_runner=vendor
    ).execute(_intent(), _edit)
    assert result.status == "passed"
    assert observed["validated"] == result.published_bytes
    assert mex.read_bytes() != original
    assert not control.exists()


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
    platform = project.verified_target.lease._resources["platform"]

    def fail_secure_delete(_path, _expected):
        raise OSError("injected secure-delete failure")

    monkeypatch.setattr(
        platform, "secure_delete_owned", fail_secure_delete, raising=False
    )
    blocked = SimpleNamespace(status="blocked", diagnostics=[])
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=lambda *_args, **_kwargs: blocked
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_cleanup_failed"
    assert mex.read_bytes() == original
    for staging in mex.parent.glob(f".{mex.name}.*.tmp"):
        staging.unlink()


def test_finally_preserves_staging_replaced_by_external_bytes(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    external = b"<external-staging/>"
    observed = {}

    def replace_then_block(path, **_kwargs):
        path.write_bytes(external)
        observed["path"] = path
        return SimpleNamespace(status="blocked", diagnostics=[])

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, static_runner=replace_then_block
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_cleanup_ownership_changed"
    assert observed["path"].read_bytes() == external
    assert mex.read_bytes() == project.verified_target.mex.content


class _CapturePlatform:
    def __init__(self, target: Path, staging: Path) -> None:
        self.target = target
        self.staging = staging
        self.files = {
            target: (FileIdentity(1, 1, None), b"original"),
            staging: (FileIdentity(1, 2, None), b"candidate"),
        }
        self.inject_at_exchange = False
        self.inject_before_restore = False
        self.restore_fails = False
        self.restore_calls = 0
        self.fail_restore_call = 0

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
        self.restore_calls += 1
        if self.restore_fails or self.restore_calls == self.fail_restore_call:
            raise OSError("injected restore failure")
        if self.inject_before_restore:
            self.inject_before_restore = False
            held = target.with_name("held-candidate.mex")
            self.files[held] = self.files[target]
            self.files[target] = (FileIdentity(1, 4, None), b"restore-attacker")
        self.files[rescue] = self.files.pop(target)
        self.files[target] = self.files.pop(capture)
        return rescue

    def install_absent(self, replacement: Path, target: Path) -> None:
        if target in self.files:
            raise OSError("destination exists")
        self.files[target] = self.files.pop(replacement)

    def capture_remove(self, source: Path, capture: Path) -> None:
        self.install_absent(source, capture)

    def unlink_path(self, path: Path) -> None:
        self.files.pop(path)


def _capture_expectation(platform: _CapturePlatform) -> PublishExpectation:
    original = platform.snapshot_file(platform.target)
    return PublishExpectation(original.path, original.identity, original.sha256)


def test_exchange_snapshot_failure_carries_structured_publication_state(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expectation = _capture_expectation(platform)
    snapshot = platform.snapshot_file
    exchanged = {"value": False}
    exchange = platform.exchange_capture

    def mark_exchange(*args):
        result = exchange(*args)
        exchanged["value"] = True
        return result

    def fail_after_exchange(path):
        if exchanged["value"]:
            exchanged["value"] = False
            raise OSError("injected post-exchange snapshot failure")
        return snapshot(path)

    platform.exchange_capture = mark_exchange
    platform.snapshot_file = fail_after_exchange
    with pytest.raises(AtomicPublishFailure) as caught:
        atomic_publish_candidate(
            expectation, staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=platform,
        )
    assert isinstance(caught.value.state, AtomicPublishState)
    assert caught.value.state.phase == "exchanged"
    assert caught.value.state.displaced_path is not None
    assert set(caught.value.details["preserved"]) == set(
        caught.value.state.preserved_basenames
    )


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


def test_restore_is_a_second_cas_and_restores_new_attacker(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expectation = _capture_expectation(platform)
    platform.inject_at_exchange = True
    platform.inject_before_restore = True

    with pytest.raises(CliFailure):
        atomic_publish_candidate(
            expectation,
            staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=platform,
        )
    assert platform.files[target][1] == b"restore-attacker"
    assert b"attacker" in [content for _, content in platform.files.values()]
    assert b"candidate" in [content for _, content in platform.files.values()]


def test_secondary_restore_failure_preserves_every_classified_file(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expectation = _capture_expectation(platform)
    platform.inject_at_exchange = True
    platform.inject_before_restore = True
    platform.fail_restore_call = 2

    with pytest.raises(CliFailure) as caught:
        atomic_publish_candidate(
            expectation,
            staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=platform,
        )
    assert caught.value.code == "configure_publish_restore_cas_failed"
    contents = [content for _, content in platform.files.values()]
    assert b"attacker" in contents
    assert b"restore-attacker" in contents
    assert b"candidate" in contents


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


def test_injected_posix_mode_mismatch_restores_original_fail_closed(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"

    class ModePlatform(_CapturePlatform):
        def snapshot_file(self, path):
            snapshot = super().snapshot_file(path)
            mode = 0o640 if snapshot.content == b"original" else 0o600
            return replace(snapshot, mode=mode)

    platform = ModePlatform(target, staging)
    expectation = _capture_expectation(platform)
    with pytest.raises(CliFailure) as caught:
        atomic_publish_candidate(
            expectation, staging,
            __import__("hashlib").sha256(b"candidate").hexdigest(),
            platform=platform,
        )
    assert caught.value.code == "configure_publish_metadata_changed"
    assert platform.files[target][1] == b"original"


def test_injected_cleanup_quarantine_deletes_only_snapshot_proven_candidate(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expected = platform.snapshot_file(staging)
    discard_owned_path(staging, expected, platform)
    assert staging not in platform.files


def test_injected_cleanup_quarantine_restores_unowned_replacement(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"
    platform = _CapturePlatform(target, staging)
    expected = platform.snapshot_file(staging)
    platform.files[staging] = (FileIdentity(1, 9, None), b"external")
    with pytest.raises(CliFailure) as caught:
        discard_owned_path(staging, expected, platform)
    assert caught.value.code == "configure_cleanup_ownership_changed"
    assert platform.files[staging][1] == b"external"


def test_secure_delete_window_swap_never_deletes_external_bytes(tmp_path):
    target = tmp_path / "project.mex"
    staging = tmp_path / ".project.mex.candidate.tmp"

    class SwapBeforeDelete(_CapturePlatform):
        def secure_delete_owned(self, path, expected):
            self.files[path] = (FileIdentity(1, 99, None), b"external")
            actual = self.snapshot_file(path)
            if actual.identity != expected.identity or actual.sha256 != expected.sha256:
                raise OSError("conditional delete identity mismatch")
            self.files.pop(path)

    platform = SwapBeforeDelete(target, staging)
    expected = platform.snapshot_file(staging)
    with pytest.raises(CliFailure) as caught:
        discard_owned_path(staging, expected, platform)
    assert caught.value.code == "configure_cleanup_failed"
    assert b"external" in [content for _, content in platform.files.values()]
    assert caught.value.details["preserved"]


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
        capture_remove = staticmethod(inner.capture_remove)
        install_absent = staticmethod(inner.install_absent)

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


def test_atomic_publish_internal_aux_mutation_cannot_return_pass(tmp_path):
    project = _prepared_project(tmp_path)
    source = project.root / ".project"

    def publish_then_mutate(*args, **kwargs):
        result = atomic_publish_candidate(*args, **kwargs)
        source.write_bytes(source.read_bytes() + b"\n")
        return result

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            static_runner=_passed_static,
            atomic_publish_fn=publish_then_mutate,
        ).execute(_intent(), _edit)
    assert caught.value.code == "project_metadata_source_changed"


def test_flush_auxiliary_mutation_cannot_return_pass(monkeypatch, tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    source = project.root / ".project"

    def mutate_aux(_directory):
        source.write_bytes(source.read_bytes() + b"\n")

    monkeypatch.setattr(ConfigureTransaction, "_flush_directory", staticmethod(mutate_aux))
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )
    assert caught.value.code == "project_metadata_source_changed"
    assert mex.read_bytes() == original


@pytest.mark.parametrize("field", ["mtime_ns", "ctime_ns", "mode"])
def test_auxiliary_metadata_only_drift_after_release_cannot_return_pass(
    monkeypatch, tmp_path, field
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    capture = metadata_module.snapshot_safe_relative

    def drift_metadata(root, relative, *, max_bytes):
        snapshot = capture(root, relative, max_bytes=max_bytes)
        if relative != ".project" or snapshot is None:
            return snapshot
        return replace(snapshot, **{field: getattr(snapshot, field) + 1})

    monkeypatch.setattr(
        metadata_module, "snapshot_safe_relative", drift_metadata
    )
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )

    assert caught.value.code == "project_metadata_source_changed"
    assert mex.read_bytes() == original


def test_flush_target_swap_cannot_return_pass(monkeypatch, tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    attacker = b"<flush-attacker/>\n"

    def mutate_target(_directory):
        replacement = mex.with_name("flush-attacker.mex")
        replacement.write_bytes(attacker)
        os.replace(replacement, mex)

    monkeypatch.setattr(ConfigureTransaction, "_flush_directory", staticmethod(mutate_target))
    with pytest.raises(CliFailure):
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )
    assert mex.read_bytes() == attacker


@pytest.mark.parametrize("preexisting", [False, True])
def test_final_cas_external_target_preserves_attacker_and_restores_backup_pair(
    monkeypatch, tmp_path, preexisting
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    backup = mex.with_name(mex.name + ".bak")
    prior = b"prior-backup"
    attacker = b"<final-cas-attacker/>"
    if preexisting:
        backup.write_bytes(prior)

    def mutate_target(_directory):
        replacement = mex.with_name("final-cas-attacker.mex")
        replacement.write_bytes(attacker)
        os.replace(replacement, mex)

    monkeypatch.setattr(ConfigureTransaction, "_flush_directory", staticmethod(mutate_target))
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static
        ).execute(_intent(), _edit)
    assert caught.value.code == "project_target_changed"
    recovery_codes = {
        item["code"] for item in caught.value.details["recovery_failures"]
    }
    assert "configure_publish_restore_failed" in recovery_codes
    if os.name != "nt":
        assert "configure_cleanup_ownership_changed" in recovery_codes
    assert mex.read_bytes() == attacker
    if preexisting:
        assert backup.read_bytes() == prior
    else:
        assert not backup.exists()


@pytest.mark.parametrize("preexisting", [False, True])
def test_flush_failure_rolls_back_backup_and_target(monkeypatch, tmp_path, preexisting):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    prior_backup = b"prior-backup"
    if preexisting:
        backup.write_bytes(prior_backup)

    def fail_flush(_directory):
        raise CliFailure(
            "configure_publish_flush_failed", "injected flush failure", module="backend"
        )

    monkeypatch.setattr(ConfigureTransaction, "_flush_directory", staticmethod(fail_flush))
    with pytest.raises(CliFailure):
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static
        ).execute(_intent(), _edit)
    assert mex.read_bytes() == original
    if preexisting:
        assert backup.read_bytes() == prior_backup
    else:
        assert not backup.exists()


@pytest.mark.parametrize("preexisting", [False, True])
def test_target_publish_failure_rolls_back_backup_pair(tmp_path, preexisting):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    prior = b"prior-backup"
    if preexisting:
        backup.write_bytes(prior)

    def fail_target_publish(*_args, **_kwargs):
        raise CliFailure(
            "configure_publish_failed", "injected target failure", module="backend"
        )

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static,
            atomic_publish_fn=fail_target_publish,
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_publish_failed"
    assert mex.read_bytes() == original
    if preexisting:
        assert backup.read_bytes() == prior
    else:
        assert not backup.exists()


def test_absent_backup_syscall_race_preserves_external_backup(
    monkeypatch, tmp_path,
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    attacker = b"external-backup"
    platform = project.verified_target.lease._resources["platform"]
    before = _directory_inventory(mex.parent)
    observed = {}

    def lose_absent_race(candidate, destination):
        destination.write_bytes(attacker)
        observed["attacker"] = _path_record(destination)
        platform.install_absent(candidate, destination)

    helper = target_module.atomic_install_absent
    def require_exact_forwarding(path, staging, sha, platform=None, *, install_fn=None):
        observed["forwarded"] = True
        assert platform is project.verified_target.lease._resources["platform"]
        assert install_fn is lose_absent_race
        return helper(path, staging, sha, platform, install_fn=install_fn)
    monkeypatch.setattr(transaction_module, "atomic_install_absent", require_exact_forwarding)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            backup=True,
            static_runner=_passed_static,
            backup_install_absent_fn=lose_absent_race,
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_backup_changed"
    assert observed["forwarded"] is True
    expected = dict(before)
    expected[backup.name] = observed["attacker"]
    assert _directory_inventory(mex.parent) == expected
    assert mex.read_bytes() == original and backup.read_bytes() == attacker
    _assert_failure_has_no_path_leak(caught.value, mex.parent)


def test_preexisting_backup_syscall_race_preserves_external_backup(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    backup.write_bytes(b"prior")
    attacker = b"external-backup"
    publish = transaction_module.atomic_publish_candidate

    def reject_absent_helper(*_args, **_kwargs):
        pytest.fail("absent-backup helper reached the existing-backup branch")

    def race(expectation, staging, candidate_sha256, *, platform):
        replacement = backup.with_name("external-backup.tmp")
        replacement.write_bytes(attacker)
        os.replace(replacement, backup)
        return publish(
            expectation, staging, candidate_sha256, platform=platform
        )

    monkeypatch.setattr(transaction_module, "atomic_publish_candidate", race)
    monkeypatch.setattr(transaction_module, "atomic_install_absent", reject_absent_helper)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static,
            backup_install_absent_fn=reject_absent_helper,
        ).execute(_intent(), _edit)
    assert caught.value.code == "project_target_changed"
    assert mex.read_bytes() == original
    assert backup.read_bytes() == attacker


def test_published_mode_matches_original(tmp_path):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    before_mode = stat.S_IMODE(mex.stat().st_mode)
    ConfigureTransaction(project, static_runner=_passed_static).execute(
        _intent(), _edit
    )
    assert stat.S_IMODE(mex.stat().st_mode) == before_mode


@pytest.mark.skipif(os.name != "nt", reason="Windows readonly metadata test")
def test_real_windows_readonly_target_fails_closed_without_metadata_loss(tmp_path):
    root = copy_uart_fixture(tmp_path)
    mex = root / "Uart_Example.mex"
    original = mex.read_bytes()
    os.chmod(mex, stat.S_IREAD)
    try:
        project = Project.verified(root)
        cli._preflight_project(project)
        with pytest.raises(CliFailure) as caught:
            ConfigureTransaction(project, static_runner=_passed_static).execute(
                _intent(), _edit
            )
        assert caught.value.code == "configure_publish_failed"
        assert mex.read_bytes() == original
        assert not (mex.stat().st_mode & stat.S_IWRITE)
        assert not list(mex.parent.glob(f".{mex.name}.*.tmp"))
    finally:
        os.chmod(mex, stat.S_IREAD | stat.S_IWRITE)


def test_real_static_context_uses_candidate_and_verified_project_facts(tmp_path):
    project = _prepared_project(tmp_path)
    result = ConfigureTransaction(
        project, static_runner=cli.run_static_checks
    ).execute(_intent(), _edit)
    assert result.static_result.status == "passed"
    checks = result.static_result.data["checks"]
    assert checks["single_mex"] is True
    assert checks["schema"] is True
    assert checks["project_target"] is True


@pytest.mark.parametrize("failed_snapshot", [1, 2])
def test_exchange_classification_failure_is_adopted_and_primary_code_survives(
    monkeypatch, tmp_path, failed_snapshot
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    platform = project.verified_target.lease._resources["platform"]
    snapshot = platform.snapshot_file
    exchange = platform.exchange_capture
    state = {"exchanged": False, "count": 0}

    def mark_exchange(*args):
        result = exchange(*args)
        state["exchanged"] = True
        return result

    def fail_first_classification(path):
        if state["exchanged"]:
            state["count"] += 1
            if state["count"] == failed_snapshot:
                raise OSError("injected classification failure")
        return snapshot(path)

    monkeypatch.setattr(platform, "exchange_capture", mark_exchange)
    monkeypatch.setattr(platform, "snapshot_file", fail_first_classification)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )
    assert caught.value.code == "configure_publish_uncertain"
    assert mex.read_bytes() == original
    assert len(caught.value.details["preserved"]) >= 2


@pytest.mark.skipif(os.name != "nt", reason="real Windows transaction path")
def test_real_windows_transaction_adopts_restore_failure_without_masking_primary(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    held = mex.with_name("held-original.mex")
    attacker = mex.with_name("syscall-attacker.mex")
    attacker_bytes = b"<syscall-attacker/>"
    platform = project.verified_target.lease._resources["platform"]
    exchange = platform.exchange_capture
    restore = platform.restore_capture
    calls = {"restore": 0}

    def inject_at_exchange(replacement, destination, capture):
        os.replace(destination, held)
        attacker.write_bytes(attacker_bytes)
        os.replace(attacker, destination)
        return exchange(replacement, destination, capture)

    def fail_first_restore(target, capture, rescue):
        calls["restore"] += 1
        if calls["restore"] == 1:
            raise OSError("injected first restore failure")
        return restore(target, capture, rescue)

    monkeypatch.setattr(platform, "exchange_capture", inject_at_exchange)
    monkeypatch.setattr(platform, "restore_capture", fail_first_restore)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )

    assert caught.value.code == "configure_publish_restore_failed"
    assert mex.read_bytes() == attacker_bytes
    assert held.read_bytes() == original
    preserved = caught.value.details["preserved"]
    assert mex.name in preserved
    assert all(Path(item).name == item for item in preserved)


@pytest.mark.parametrize("missing_destination", [False, True])
def test_absent_backup_post_install_snapshot_failure_is_uncertain_and_cleaned(
    monkeypatch, tmp_path, missing_destination
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    evidence = mex.with_name("missing-backup-evidence.bin")
    platform = project.verified_target.lease._resources["platform"]
    snapshot = platform.snapshot_file
    state = {"installed": False, "failed": False}
    before = _directory_inventory(mex.parent)

    def install_backup(candidate, destination):
        platform.install_absent(candidate, destination)
        state["installed"] = True
        state["record"] = _path_record(destination)
        if missing_destination:
            os.replace(destination, evidence)

    def fail_first_backup_snapshot(path):
        if path == backup and state["installed"] and not state["failed"]:
            state["failed"] = True
            if missing_destination:
                raise FileNotFoundError(path)
            raise OSError("injected backup classification failure")
        return snapshot(path)

    monkeypatch.setattr(platform, "snapshot_file", fail_first_backup_snapshot)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            backup=True,
            static_runner=_passed_static,
            backup_install_absent_fn=install_backup,
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_backup_uncertain"
    expected = before | ({evidence.name: state["record"]} if missing_destination else {})
    assert _directory_inventory(mex.parent) == expected
    assert mex.read_bytes() == original and not backup.exists()
    assert state["record"][2] == original
    assert backup.name in caught.value.details["preserved"]
    _assert_failure_has_no_path_leak(caught.value, mex.parent)


@pytest.mark.parametrize("same_bytes", [False, True])
def test_absent_backup_readable_swap_is_staging_changed_and_preserved(tmp_path, same_bytes):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    platform = project.verified_target.lease._resources["platform"]
    evidence = mex.with_name("installed-backup-evidence.bin")
    attacker = mex.with_name("readable-backup-attacker.bin")
    attacker_bytes = original if same_bytes else b"external-backup-after-noreplace"
    attacker.write_bytes(attacker_bytes)
    before = _directory_inventory(mex.parent)
    observed = {}

    def publish_then_swap(candidate, destination):
        platform.install_absent(candidate, destination)
        os.replace(destination, evidence)
        observed["evidence"] = _path_record(evidence)
        os.replace(attacker, destination)

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            backup=True,
            static_runner=_passed_static,
            backup_install_absent_fn=publish_then_swap,
        ).execute(_intent(), _edit)

    assert caught.value.code == "configure_staging_changed"
    expected = dict(before)
    expected[backup.name] = expected.pop(attacker.name)
    expected[evidence.name] = observed["evidence"]
    assert _directory_inventory(mex.parent) == expected
    assert backup.read_bytes() == attacker_bytes and evidence.read_bytes() == original
    assert backup.name in caught.value.details["preserved"]
    _assert_failure_has_no_path_leak(caught.value, mex.parent)


def test_absent_backup_unclassifiable_destination_is_uncertain_and_preserved(
    tmp_path,
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    evidence = mex.with_name("unclassifiable-backup-evidence.bin")
    platform = project.verified_target.lease._resources["platform"]
    before = _directory_inventory(mex.parent)
    observed = {}

    def publish_then_make_directory(candidate, destination):
        platform.install_absent(candidate, destination)
        os.replace(destination, evidence)
        observed["evidence"] = _path_record(evidence)
        destination.mkdir()
        (destination / "attacker-sentinel.bin").write_bytes(b"attacker-evidence")
        observed["directory"] = _path_record(destination)
        observed["sentinel"] = _path_record(destination / "attacker-sentinel.bin")

    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            backup=True,
            static_runner=_passed_static,
            backup_install_absent_fn=publish_then_make_directory,
        ).execute(_intent(), _edit)

    assert caught.value.code == "configure_backup_uncertain"
    expected = dict(before)
    expected.update({evidence.name: observed["evidence"], backup.name: observed["directory"],
                     f"{backup.name}/attacker-sentinel.bin": observed["sentinel"]})
    assert _directory_inventory(mex.parent) == expected
    assert evidence.read_bytes() == original
    assert backup.name in caught.value.details["preserved"]
    _assert_failure_has_no_path_leak(caught.value, mex.parent)


@pytest.mark.skipif(os.name != "nt", reason="literal Windows reparse-point slice")
def test_real_windows_absent_backup_reparse_is_uncertain_and_not_followed(
    monkeypatch, tmp_path
):
    platform = default_target_platform()
    prerequisite_target = tmp_path / "symlink-prerequisite-target.bin"
    prerequisite_link = tmp_path / "symlink-prerequisite-link.bin"
    prerequisite_candidate = tmp_path / "symlink-prerequisite-candidate.bin"
    prerequisite_installed = tmp_path / "symlink-prerequisite-installed.bin"
    prerequisite_target.write_bytes(b"probe")
    prerequisite_candidate.write_bytes(b"installed")
    try:
        with platform.protect_root(tmp_path.resolve()):
            platform.install_absent(prerequisite_candidate, prerequisite_link)
            os.replace(prerequisite_link, prerequisite_installed)
            os.symlink(prerequisite_target, prerequisite_link)
            try:
                platform.snapshot_file(prerequisite_link)
            except (OSError, ValueError, RuntimeError):
                pass
            else:
                pytest.fail("Windows adapter followed the retained-handle reparse point")
    except OSError as exc:
        pytest.skip(
            "Windows retained-handle no-replace/reparse prerequisite unavailable "
            f"(winerror={getattr(exc, 'winerror', None)})"
        )
    finally:
        for path in (prerequisite_link, prerequisite_installed, prerequisite_target):
            if os.path.lexists(path):
                path.unlink()

    project = _prepared_project(tmp_path)
    mex = project.mex_file
    platform = project.verified_target.lease._resources["platform"]
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    external = mex.with_name("reparse-target-evidence.bin")
    installed = mex.with_name("reparse-installed-evidence.bin")
    external.write_bytes(b"external-reparse-evidence")
    before = _directory_inventory(mex.parent)
    snapshot = platform.snapshot_file
    attack = {"execute_entered": False, "primitive_returned": False, "done": False}

    def install_movable_then_return(candidate, destination):
        attack["execute_entered"] = True
        movable = tmp_path / "movable-backup-candidate.bin"
        movable.write_bytes(candidate.read_bytes())
        platform.install_absent(movable, destination)
        attack["primitive_returned"] = True

    def attack_after_primitive_return(path):
        if path == backup and not attack["done"]:
            assert attack["primitive_returned"] is True
            attack["done"] = True
            try:
                os.replace(path, installed)
                os.symlink(external, path)
            except OSError as exc:
                attack["setup_error"] = exc
                raise
            attack["installed"] = _path_record(installed)
            attack["link"] = _path_record(path)
        return snapshot(path)

    monkeypatch.setattr(platform, "snapshot_file", attack_after_primitive_return)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project,
            backup=True,
            static_runner=_passed_static,
            backup_install_absent_fn=install_movable_then_return,
        ).execute(_intent(), _edit)

    assert attack["execute_entered"] is True
    assert attack["primitive_returned"] is True
    assert "setup_error" not in attack and attack["done"] is True
    assert backup.is_symlink()
    assert caught.value.code == "configure_backup_uncertain"
    expected = dict(before)
    expected.update({backup.name: attack["link"], installed.name: attack["installed"]})
    assert _directory_inventory(mex.parent) == expected
    assert mex.read_bytes() == original
    assert installed.read_bytes() == original and external.read_bytes() == b"external-reparse-evidence"
    assert backup.name in caught.value.details["preserved"]
    _assert_failure_has_no_path_leak(caught.value, mex.parent)


def test_second_finalize_failure_returns_published_with_cleanup_warning(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    finalize = transaction_module.finalize_atomic_publish
    calls = {"count": 0}

    def fail_second(result, *, platform):
        calls["count"] += 1
        if calls["count"] == 2:
            raise CliFailure(
                "configure_cleanup_failed", "injected finalize failure",
                module="backend", details={"preserved": ["backup-evidence.tmp"]},
            )
        return finalize(result, platform=platform)

    monkeypatch.setattr(transaction_module, "finalize_atomic_publish", fail_second)
    result = ConfigureTransaction(
        project, backup=True, static_runner=_passed_static
    ).execute(_intent(), _edit)
    assert result.status == "passed"
    assert result.published is True
    assert mex.read_bytes() == result.published_bytes != original
    assert mex.with_name(mex.name + ".bak").read_bytes() == original
    warning = next(
        item
        for item in result.cleanup_warnings
        if item["code"] == "configure_cleanup_failed"
    )
    assert list(warning["details"]["preserved"]) == ["backup-evidence.tmp"]


def test_target_finalize_failure_is_postcommit_warning_without_fake_rollback(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    finalize = transaction_module.finalize_atomic_publish
    calls = {"count": 0}

    def fail_first(result, *, platform):
        calls["count"] += 1
        if calls["count"] == 1:
            raise CliFailure(
                "configure_cleanup_failed", "injected target finalize failure",
                module="backend", details={"preserved": ["target-evidence.tmp"]},
            )
        return finalize(result, platform=platform)

    monkeypatch.setattr(transaction_module, "finalize_atomic_publish", fail_first)
    result = ConfigureTransaction(
        project, backup=True, static_runner=_passed_static
    ).execute(_intent(), _edit)

    assert result.status == "passed"
    assert result.published is True
    assert mex.read_bytes() == result.published_bytes != original
    assert mex.with_name(mex.name + ".bak").read_bytes() == original
    assert result.cleanup_warnings[0]["code"] == "configure_cleanup_failed"
    assert result.cleanup_warnings[0]["message"] == (
        "injected target finalize failure"
    )
    assert list(result.cleanup_warnings[0]["details"]["preserved"]) == [
        "target-evidence.tmp"
    ]


def test_committed_delete_failure_reports_auditable_warning_and_keeps_bytes(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    platform = project.verified_target.lease._resources["platform"]

    def fail_delete(_path, _expected):
        raise OSError("injected delete-by-handle failure")

    monkeypatch.setattr(platform, "secure_delete_owned", fail_delete, raising=False)
    result = ConfigureTransaction(
        project, backup=True, static_runner=_passed_static
    ).execute(_intent(), _edit)

    assert result.status == "passed"
    assert result.published is True
    assert mex.read_bytes() == result.published_bytes != original
    assert mex.with_name(mex.name + ".bak").read_bytes() == original
    assert len(result.cleanup_warnings) == 1
    assert {item["code"] for item in result.cleanup_warnings} == {
        "configure_cleanup_failed"
    }
    preserved = [
        name
        for warning in result.cleanup_warnings
        for name in warning["details"]["preserved"]
    ]
    assert preserved
    assert all(Path(item).name == item for item in preserved)


def test_posix_shaped_adapter_without_conditional_delete_keeps_quarantine_warning(
    monkeypatch, tmp_path,
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    platform = project.verified_target.lease._resources["platform"]
    monkeypatch.setattr(platform, "secure_delete_owned", None, raising=False)
    monkeypatch.setattr(platform, "unlink_path", None, raising=False)
    result = ConfigureTransaction(project, static_runner=_passed_static).execute(
        _intent(), _edit
    )

    assert result.status == "passed"
    assert result.published is True
    assert mex.read_bytes() == result.published_bytes != original
    assert result.cleanup_warnings
    warning = result.cleanup_warnings[0]
    assert warning["code"] == "configure_cleanup_residual"
    residual = mex.parent / warning["details"]["preserved"][0]
    assert residual.exists()
    assert residual.read_bytes() == original


def test_merge_failures_appends_existing_recovery_evidence_in_order():
    primary = CliFailure(
        "project_target_changed",
        "primary",
        module="backend",
        details={
            "preserved": ["primary.tmp"],
            "recovery_failures": [{
                "code": "existing_recovery",
                "message": "existing",
                "details": {"preserved": ["existing.tmp"]},
            }],
        },
    )
    secondary = [
        CliFailure(
            "secondary_one", "one", module="backend",
            details={"preserved": ["one.tmp", "primary.tmp"]},
        ),
        CliFailure(
            "secondary_two", "two", module="backend",
            details={"preserved": ["two.tmp"]},
        ),
    ]

    merged = ConfigureTransaction._merge_failures(primary, secondary)

    assert merged.code == "project_target_changed"
    assert [item["code"] for item in merged.details["recovery_failures"]] == [
        "existing_recovery", "secondary_one", "secondary_two",
    ]
    assert list(merged.details["preserved"]) == [
        "primary.tmp", "existing.tmp", "one.tmp", "two.tmp",
    ]


@pytest.mark.skipif(os.name != "nt", reason="real Windows delete-by-handle path")
def test_real_windows_delete_by_handle_blocks_unlink_window_swap(
    monkeypatch, tmp_path
):
    path = tmp_path / "cleanup.tmp"
    attacker = tmp_path / "cleanup-attacker.tmp"
    path.write_bytes(b"owned")
    attacker.write_bytes(b"external")
    platform = default_target_platform()
    expected = platform.snapshot_file(path)
    set_disposition = target_module._SetFileInformationByHandle
    blocked = {"value": False}

    def try_swap_while_handle_is_locked(handle, info_class, info, size):
        try:
            os.replace(attacker, path)
        except OSError:
            blocked["value"] = True
        return set_disposition(handle, info_class, info, size)

    monkeypatch.setattr(
        target_module, "_SetFileInformationByHandle", try_swap_while_handle_is_locked
    )
    platform.secure_delete_owned(path, expected)
    assert blocked["value"] is True
    assert not path.exists()
    assert attacker.read_bytes() == b"external"


def test_backup_displaced_drift_fails_before_commit_and_keeps_primary_code(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    original = mex.read_bytes()
    backup = mex.with_name(mex.name + ".bak")
    backup.write_bytes(b"prior-backup")
    prepare = transaction_module.prepare_atomic_finalize
    calls = {"count": 0}

    def drift_second(result, *, platform):
        calls["count"] += 1
        if calls["count"] == 2:
            assert result.displaced_path is not None
            result.displaced_path.write_bytes(b"external-displaced")
        return prepare(result, platform=platform)

    monkeypatch.setattr(transaction_module, "prepare_atomic_finalize", drift_second)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(
            project, backup=True, static_runner=_passed_static
        ).execute(_intent(), _edit)
    assert caught.value.code == "configure_finalize_prepare_changed"
    assert mex.read_bytes() == original
    assert backup.read_bytes() == b"external-displaced"


def test_target_displaced_drift_fails_before_commit_and_preserves_drift(
    monkeypatch, tmp_path
):
    project = _prepared_project(tmp_path)
    mex = project.mex_file
    prepare = transaction_module.prepare_atomic_finalize
    changed = b"external-target-evidence"

    def drift_target(result, *, platform):
        assert result.displaced_path is not None
        result.displaced_path.write_bytes(changed)
        return prepare(result, platform=platform)

    monkeypatch.setattr(transaction_module, "prepare_atomic_finalize", drift_target)
    with pytest.raises(CliFailure) as caught:
        ConfigureTransaction(project, static_runner=_passed_static).execute(
            _intent(), _edit
        )
    assert caught.value.code == "configure_finalize_prepare_changed"
    assert mex.read_bytes() == changed
    assert caught.value.details["preserved"]


def test_production_has_no_bare_replace_or_unlink():
    root = Path(transaction_module.__file__).parent
    production = (root / "transaction.py").read_text(encoding="utf-8")
    production += (root / "target.py").read_text(encoding="utf-8")
    assert "os.replace" not in production
    assert ".unlink(" not in production
