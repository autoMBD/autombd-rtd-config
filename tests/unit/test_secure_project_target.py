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
# File:        test_secure_project_target.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-13
# Version:     0.1.0
# Description: Unit tests for secure project target verification and snapshots.
# =================================================================================

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import FrozenInstanceError, replace
from functools import partial
import gc
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex import target as target_module
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.backends.s32_mex.target import (
    FileIdentity,
    FileSnapshot,
    PathInspection,
    TargetLease,
    VerifiedProjectTarget,
    WindowsFileId,
    _PosixTargetPlatform,
    _WindowsTargetPlatform,
    release_for_publish,
    default_target_platform,
    revalidate_snapshot,
    verify_project_target,
)
from rtd_config.errors import CliFailure
from rtd_config.project import Project
from rtd_config.checks.static import run_static_checks
from tests.fixtures import resolved_uart_bundle

run_static_checks = partial(run_static_checks, bundle=resolved_uart_bundle())


XML_A = b"<mex><instance name='A'/></mex>"
XML_B = b"<mex><instance name='B'/></mex>"
UART_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures/nxp/ds/s32k3/Uart_Example_S32K344"
)
COMPATIBLE_XML = (UART_FIXTURE / "Uart_Example.mex").read_bytes()


def _project(tmp_path: Path, raw: bytes = XML_A) -> tuple[Path, Path]:
    root = tmp_path / "project"
    root.mkdir(parents=True)
    mex = root / "sample.mex"
    mex.write_bytes(raw)
    return root, mex


def _bundle_compatible_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    shutil.copytree(UART_FIXTURE, root)
    return root, root / "Uart_Example.mex"


class InjectedPlatform:
    def __init__(self) -> None:
        self.native = default_target_platform()
        self.inspections: dict[Path, PathInspection] = {}
        self.canonical: dict[Path, Path] = {}
        self.snapshot_error: Exception | None = None
        self.snapshot_override: FileSnapshot | None = None
        self.list_error: Exception | None = None
        self.inspect_error: Exception | None = None
        self.canonical_error: Exception | None = None
        self.canonical_hook = None
        self.snapshot_hook = None

    def protect_root(self, path: Path):
        return self.native.protect_root(path)

    def list_directory(self, path: Path) -> tuple[Path, ...]:
        if self.list_error is not None:
            raise self.list_error
        return self.native.list_directory(path)

    def inspect(self, path: Path) -> PathInspection:
        if self.inspect_error is not None:
            raise self.inspect_error
        return self.inspections.get(path, self.native.inspect(path))

    def canonicalize(self, path: Path) -> Path:
        if self.canonical_error is not None:
            raise self.canonical_error
        if self.canonical_hook is not None:
            replacement = self.canonical_hook(path)
            if replacement is not None:
                return replacement
        return self.canonical.get(path, self.native.canonicalize(path))

    def snapshot_file(self, path: Path) -> FileSnapshot:
        if self.snapshot_hook is not None:
            hook, self.snapshot_hook = self.snapshot_hook, None
            hook()
        if self.snapshot_error is not None:
            raise self.snapshot_error
        if self.snapshot_override is not None:
            return replace(self.snapshot_override, path=path)
        return self.native.snapshot_file(path)


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_rejects_missing_or_non_directory_root(tmp_path, kind):
    root = tmp_path / "project"
    if kind == "file":
        root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root)

    assert caught.value.code in {"project_not_found", "project_not_directory"}


@pytest.mark.parametrize("count", [0, 2])
def test_rejects_zero_or_multiple_direct_mex_files(tmp_path, count):
    root = tmp_path / "project"
    root.mkdir()
    for index in range(count):
        (root / f"{index}.mex").write_bytes(XML_A)

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root)

    assert caught.value.code in {"project_mex_not_found", "project_mex_ambiguous"}


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("linked_part", ["ancestor", "root", "mex"])
def test_rejects_symlink_in_existing_target_chain(tmp_path, linked_part):
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    real_root, real_mex = _project(real_parent)
    if linked_part == "ancestor":
        link = tmp_path / "linked-parent"
        try:
            link.symlink_to(real_parent, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
        root = link / real_root.name
    elif linked_part == "root":
        root = tmp_path / "linked-root"
        try:
            root.symlink_to(real_root, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
    else:
        real_mex.unlink()
        source = tmp_path / "outside.mex"
        source.write_bytes(XML_A)
        try:
            real_mex.symlink_to(source)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")
        root = real_root

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root)

    assert caught.value.code == "unsafe_project_path"


@pytest.mark.parametrize("flag", ["is_reparse_point", "is_mount_point"])
def test_injected_junction_reparse_or_mount_is_rejected(tmp_path, flag):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    current = platform.inspect(root)
    platform.inspections[root] = replace(current, **{flag: True})

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "unsafe_project_path"


def test_resolved_mex_escape_is_rejected(tmp_path):
    root, mex = _project(tmp_path)
    outside = tmp_path / "outside.mex"
    outside.write_bytes(XML_A)
    platform = InjectedPlatform()
    platform.canonical[mex] = outside.resolve()

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "unsafe_project_path"


def test_nonregular_mex_is_rejected(tmp_path):
    root, mex = _project(tmp_path)
    platform = InjectedPlatform()
    platform.inspections[mex] = replace(platform.inspect(mex), is_regular=False)

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_mex_not_regular"


def test_identity_unavailable_fails_closed(tmp_path):
    root, mex = _project(tmp_path)
    platform = InjectedPlatform()
    snapshot = platform.native.snapshot_file(mex)
    platform.snapshot_override = replace(
        snapshot,
        identity=FileIdentity(device=None, inode=None, windows_file_id=None),
    )

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_identity_unavailable"


@pytest.mark.parametrize(
    "error",
    [PermissionError("denied"), RuntimeError("file changed while being read")],
)
def test_permission_or_read_instability_becomes_typed_failure(tmp_path, error):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    platform.snapshot_error = error

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code in {"project_permission_denied", "project_target_changed"}


@pytest.mark.parametrize("stage", ["inspect", "canonicalize"])
def test_path_evidence_permission_failure_is_typed(tmp_path, stage):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    if stage == "inspect":
        platform.inspect_error = PermissionError("denied")
    else:
        platform.canonical_error = PermissionError("denied")

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_permission_denied"


def test_directory_enumeration_permission_failure_is_typed(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    platform.list_error = PermissionError("denied")

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_permission_denied"


def test_snapshot_contains_identity_evidence_hash_and_exact_bytes(tmp_path):
    root, mex = _project(tmp_path)

    target = verify_project_target(root)

    assert target.root == root.resolve()
    assert target.mex.path == mex.resolve()
    assert target.mex.content == XML_A
    assert target.mex.sha256 == hashlib.sha256(XML_A).hexdigest()
    assert target.mex.size == len(XML_A)
    assert target.mex.mtime_ns > 0
    assert target.mex.ctime_ns > 0
    identity = target.mex.identity
    if os.name == "nt":
        assert identity.windows_file_id is not None
        assert len(identity.windows_file_id.file_id) == 16
    else:
        assert identity.device is not None
        assert identity.inode is not None


def test_mex_set_change_during_snapshot_fails_closed(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    platform.snapshot_hook = lambda: (root / "late.mex").write_bytes(XML_B)

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_target_changed"


def test_ancestor_path_swap_during_verification_fails_closed(tmp_path):
    root, _ = _project(tmp_path)
    replacement_root, _ = _project(tmp_path / "replacement")
    platform = InjectedPlatform()
    root_calls = 0

    def swap_canonical_root(path: Path) -> Path | None:
        nonlocal root_calls
        if path != root.absolute():
            return None
        root_calls += 1
        return root.resolve() if root_calls == 1 else replacement_root.resolve()

    platform.canonical_hook = swap_canonical_root

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_target_changed"


def test_root_aware_revalidation_rejects_new_mex(tmp_path):
    root, _ = _project(tmp_path)
    target = verify_project_target(root)
    (root / "late.mex").write_bytes(XML_B)

    with pytest.raises(CliFailure) as caught:
        revalidate_snapshot(target)

    assert caught.value.code == "project_mex_ambiguous"


def test_root_aware_revalidation_rechecks_root_path_safety(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    target = verify_project_target(root, platform=platform)
    platform.inspections[root] = replace(
        platform.inspect(root), is_reparse_point=True
    )

    with pytest.raises(CliFailure) as caught:
        revalidate_snapshot(target, platform=platform)

    assert caught.value.code == "unsafe_project_path"


def test_root_aware_revalidation_rechecks_mex_containment(tmp_path):
    root, mex = _project(tmp_path)
    outside = tmp_path / "outside.mex"
    outside.write_bytes(XML_A)
    platform = InjectedPlatform()
    target = verify_project_target(root, platform=platform)
    platform.canonical[mex] = outside.resolve()

    with pytest.raises(CliFailure) as caught:
        revalidate_snapshot(target, platform=platform)

    assert caught.value.code == "unsafe_project_path"


def test_posix_without_no_follow_support_fails_closed(tmp_path):
    root, _ = _project(tmp_path)

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=_PosixTargetPlatform(no_follow_flag=0))

    assert caught.value.code == "project_identity_unavailable"


def test_posix_without_nonblock_support_fails_closed(tmp_path):
    _, mex = _project(tmp_path)
    platform = _PosixTargetPlatform(
        no_follow_flag=1, nonblock_flag=0, mount_detector=lambda _path: False
    )
    with pytest.raises(CliFailure) as caught:
        platform.snapshot_file(mex)
    assert caught.value.code == "project_identity_unavailable"


def test_posix_snapshot_opens_nonregular_targets_nonblocking(monkeypatch, tmp_path):
    _, mex = _project(tmp_path)
    no_follow = 0x100000
    nonblock = 0x200000
    platform = _PosixTargetPlatform(
        no_follow_flag=no_follow,
        nonblock_flag=nonblock,
        mount_detector=lambda _path: False,
    )
    opened = []
    closed = []
    fifo_status = SimpleNamespace(st_mode=target_module.stat.S_IFIFO)

    def fake_open(path, flags, **kwargs):
        opened.append((path, flags, kwargs))
        return 123

    monkeypatch.setattr(target_module.os, "open", fake_open)
    monkeypatch.setattr(target_module.os, "fstat", lambda _fd: fifo_status)
    monkeypatch.setattr(target_module.os, "close", closed.append)

    with pytest.raises(ValueError, match="regular file"):
        platform.snapshot_file(mex)

    assert opened[0][1] & no_follow
    assert opened[0][1] & nonblock
    assert closed == [123]


def test_static_malformed_snapshot_is_structured_and_releases_lease(tmp_path):
    root, mex = _project(tmp_path, b"<mex>")
    result = run_static_checks(mex)
    assert result.status == "blocked"
    assert any(item.code == "xml_not_well_formed" for item in result.diagnostics)
    root.rename(tmp_path / "released-malformed")


def test_static_malformed_supplied_snapshot_never_reopens_path(monkeypatch, tmp_path):
    root, mex = _project(tmp_path, b"<mex>")
    target = verify_project_target(root)
    monkeypatch.setattr(
        MexDocument,
        "load",
        classmethod(lambda _cls, _path: pytest.fail("path reload is forbidden")),
    )
    try:
        result = run_static_checks(mex, verified_target=target, doc=None)
        assert result.status == "blocked"
        assert any(item.code == "xml_not_well_formed" for item in result.diagnostics)
    finally:
        target.close()
    assert target.lease.closed


def test_injected_bind_mount_detector_fails_closed(tmp_path):
    root, _ = _project(tmp_path)
    platform = _PosixTargetPlatform(
        no_follow_flag=1,
        mount_detector=lambda path: path == root.absolute(),
    )

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "unsafe_project_path"


def test_missing_protect_root_fails_closed(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    platform.protect_root = None

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_identity_unavailable"


@pytest.mark.parametrize("lease_state", ["missing", "closed"])
def test_invalid_protect_root_lease_fails_closed(tmp_path, lease_state):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    lease = None
    if lease_state == "closed":
        lease = TargetLease(lambda: None)
        lease.close()
    platform.protect_root = lambda _path: nullcontext(lease)

    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)

    assert caught.value.code == "project_identity_unavailable"


def test_mount_change_after_fd_chain_open_fails_closed(monkeypatch, tmp_path):
    root, _ = _project(tmp_path)
    calls = 0

    def changing_detector(_path: Path) -> bool:
        nonlocal calls
        calls += 1
        return calls > len(target_module._path_components(root.absolute()))

    platform = _PosixTargetPlatform(no_follow_flag=1, mount_detector=changing_detector)
    monkeypatch.setattr(target_module.os, "O_DIRECTORY", 0x10000, raising=False)
    monkeypatch.setattr(target_module.os, "open", lambda *_args, **_kwargs: calls + 100)
    monkeypatch.setattr(target_module.os, "close", lambda _fd: None)
    with pytest.raises(CliFailure) as caught:
        with platform.protect_root(root):
            pass
    assert caught.value.code == "unsafe_project_path"


def test_verified_target_has_no_implicit_path_conversion(tmp_path):
    root, _ = _project(tmp_path)
    target = verify_project_target(root)
    try:
        with pytest.raises(TypeError):
            os.fspath(target)
    finally:
        target.close()


def test_posix_lease_holds_component_and_snapshot_fds_until_close(
    monkeypatch, tmp_path
):
    root, _ = _project(tmp_path)
    platform = _PosixTargetPlatform(
        no_follow_flag=1,
        mount_detector=lambda _path: False,
    )
    opened: list[int] = []
    closed: list[int] = []

    def fake_open(_path, _flags, *, dir_fd=None):
        descriptor = 100 + len(opened)
        opened.append(descriptor)
        return descriptor

    monkeypatch.setattr(target_module.os, "O_DIRECTORY", 0x10000, raising=False)
    monkeypatch.setattr(target_module.os, "open", fake_open)
    monkeypatch.setattr(target_module.os, "close", closed.append)

    with platform.protect_root(root) as lease:
        lease.retain()
        assert platform._protected_fds is not None
        snapshot_descriptor = 999
        platform._protected_fds.append(snapshot_descriptor)

    assert opened
    assert closed == []
    lease.close()
    assert closed == [snapshot_descriptor, *reversed(opened)]


@pytest.mark.parametrize(
    ("platform", "attribute", "main_value", "worker_value", "worker_default"),
    [
        (
            _PosixTargetPlatform(
                no_follow_flag=1,
                nonblock_flag=1,
                mount_detector=lambda _path: False,
            ),
            "_root_fd",
            101,
            202,
            None,
        ),
        (_WindowsTargetPlatform(), "_protected_handles", [101], [202], []),
    ],
    ids=["posix-fds", "windows-handles"],
)
def test_platform_protection_state_is_thread_local(
    platform, attribute, main_value, worker_value, worker_default
):
    setattr(platform, attribute, main_value)
    observed = []

    def inspect_worker_state():
        observed.append(getattr(platform, attribute))
        setattr(platform, attribute, worker_value)
        observed.append(getattr(platform, attribute))

    thread = threading.Thread(target=inspect_worker_state)
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert observed == [worker_default, worker_value]
    assert getattr(platform, attribute) == main_value


def test_linux_mountinfo_detector_decodes_escaped_mount_paths(monkeypatch):
    mountinfo = (
        "36 25 0:32 / /workspace\\040bind rw,relatime - ext4 /dev/root rw\n"
        "37 25 0:33 / /workspace\\011tab rw,relatime - ext4 /dev/root rw\n"
        "38 25 0:34 / /workspace\\134slash rw,relatime - ext4 /dev/root rw\n"
        "39 25 0:35 / /workspace\\012newline rw,relatime - ext4 /dev/root rw\n"
    )
    monkeypatch.setattr(target_module.sys, "platform", "linux")
    monkeypatch.setattr(
        target_module.Path,
        "read_text",
        lambda _self, *, encoding: mountinfo,
    )

    detector = _PosixTargetPlatform._default_mount_detector()

    assert detector(Path("/workspace bind"))
    assert detector(Path("/workspace\ttab"))
    assert detector(Path("/workspace\\slash"))
    assert detector(Path("/workspace\nnewline"))
    assert not detector(Path("/workspace/ordinary"))


def test_linux_default_mount_detector_resamples_mountinfo(monkeypatch, tmp_path):
    monkeypatch.setattr(target_module.sys, "platform", "linux")
    mount = tmp_path / "bind"
    snapshots = iter(("", f"36 25 0:32 / {mount} rw - ext4 /dev/root rw\n"))
    monkeypatch.setattr(
        target_module.Path,
        "read_text",
        lambda _self, *, encoding: next(snapshots),
    )
    detector = _PosixTargetPlatform._default_mount_detector()

    assert not detector(mount)
    assert detector(mount)


def test_non_linux_posix_mount_detection_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(target_module.sys, "platform", "darwin")
    detector = _PosixTargetPlatform._default_mount_detector()

    with pytest.raises(CliFailure) as caught:
        detector(tmp_path)

    assert caught.value.code == "project_identity_unavailable"


def _swap_project_after_verification(monkeypatch, root: Path, mex: Path) -> None:
    original_verified = cli.Project.verified

    def verified_then_swap(project_root: Path, backend: str = "s32-mex"):
        project = original_verified(project_root, backend)
        _ = project.metadata
        project.verified_target.close()
        replacement = root / "replacement.mex"
        replacement.write_bytes(XML_B)
        os.replace(replacement, mex)
        return project

    monkeypatch.setattr(cli.Project, "verified", verified_then_swap)


def test_inspect_uses_verified_bytes_when_target_is_swapped(monkeypatch, capsys, tmp_path):
    root, mex = _bundle_compatible_project(tmp_path)
    _swap_project_after_verification(monkeypatch, root, mex)

    assert cli.cmd_inspect(SimpleNamespace(project=root)) == 0
    payload = json.loads(capsys.readouterr().out)

    assert "Uart" in payload["modules"]
    assert mex.read_bytes() == XML_B


def test_check_uses_verified_bytes_when_target_is_swapped(monkeypatch, capsys, tmp_path):
    root, mex = _bundle_compatible_project(tmp_path)
    _swap_project_after_verification(monkeypatch, root, mex)
    monkeypatch.setattr(
        cli, "run_static_checks",
        lambda *_args, **_kwargs: pytest.fail("checks ran after target ownership ended"),
    )

    with pytest.raises(CliFailure) as caught:
        cli.cmd_check(SimpleNamespace(project=root))

    assert caught.value.code == "project_target_closed"
    assert mex.read_bytes() == XML_B


def test_validate_uses_snapshot_then_rejects_swapped_target_before_vendor(
    monkeypatch, tmp_path
):
    root, mex = _bundle_compatible_project(tmp_path)
    _swap_project_after_verification(monkeypatch, root, mex)
    original_checks = cli.run_static_checks
    vendor_called = False

    def assert_snapshot_checks(path, doc=None, **kwargs):
        assert doc is not None and doc._raw == COMPATIBLE_XML
        return original_checks(path, doc=doc, **kwargs)

    def unexpected_vendor(*_args, **_kwargs):
        nonlocal vendor_called
        vendor_called = True

    monkeypatch.setattr(cli, "run_static_checks", assert_snapshot_checks)
    monkeypatch.setattr(cli, "find_s32ds_root", lambda _root: tmp_path)
    monkeypatch.setattr(cli, "run_validation", unexpected_vendor)
    args = SimpleNamespace(
        project=root, s32ds_root=tmp_path, workspace=None, sdk_path=None
    )

    with pytest.raises(CliFailure) as caught:
        cli.cmd_validate(args)

    assert caught.value.code == "project_target_closed"
    assert not vendor_called


def test_configure_uses_snapshot_then_rejects_swapped_target_before_publish(
    monkeypatch, tmp_path
):
    root, mex = _project(tmp_path)
    _swap_project_after_verification(monkeypatch, root, mex)

    def apply_snapshot(doc, _intent):
        assert doc._raw == XML_A
        return SimpleNamespace(
            blocked=False,
            modified_elements=[],
            diagnostics=[],
            changed_modules=[],
        )

    args = SimpleNamespace(project=root, backup=False)
    intent = SimpleNamespace(module="test", action="set", payload={})
    plan = SimpleNamespace(to_dict=lambda: {})

    with pytest.raises(CliFailure) as caught:
        cli._configure_module(args, intent, plan, apply_snapshot)

    assert caught.value.code == "project_metadata_unknown"
    assert mex.read_bytes() == XML_B


def test_document_parses_captured_bytes_and_revalidation_detects_replacement(tmp_path):
    root, mex = _project(tmp_path)
    target = verify_project_target(root)
    replacement = root / "replacement.mex"
    replacement.write_bytes(XML_B)
    target.close()
    os.replace(replacement, mex)

    doc = MexDocument.from_snapshot(target.mex)

    assert doc._raw == XML_A
    assert doc._source_snapshot is target.mex
    assert not hasattr(doc, "_verified_target")
    assert doc.root.find("instance").attrib["name"] == "A"
    with pytest.raises(CliFailure) as caught:
        revalidate_snapshot(target)
    assert caught.value.code == "project_target_changed"


def test_revalidation_detects_identity_change_even_when_bytes_are_identical(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    target = verify_project_target(root, platform=platform)
    original = target.mex
    if original.identity.windows_file_id is not None:
        changed_identity = replace(
            original.identity,
            windows_file_id=replace(
                original.identity.windows_file_id,
                file_id=b"1" * 16,
            ),
        )
    else:
        changed_identity = replace(original.identity, inode=original.identity.inode + 1)
    platform.snapshot_override = replace(original, identity=changed_identity)

    with pytest.raises(CliFailure) as caught:
        revalidate_snapshot(target, platform=platform)

    assert caught.value.code == "project_target_changed"


def test_revalidation_detects_byte_change_even_when_identity_is_unchanged(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    target = verify_project_target(root, platform=platform)
    original = target.mex
    platform.snapshot_override = replace(
        original,
        size=len(XML_B),
        sha256=hashlib.sha256(XML_B).hexdigest(),
        content=XML_B,
    )

    with pytest.raises(CliFailure) as caught:
        revalidate_snapshot(target, platform=platform)

    assert caught.value.code == "project_target_changed"


def test_public_revalidation_rejects_bare_snapshot(tmp_path):
    root, _ = _project(tmp_path)
    target = verify_project_target(root)
    try:
        with pytest.raises(TypeError):
            revalidate_snapshot(target.mex)
    finally:
        target.close()


def test_project_verified_preserves_locator_compatibility_and_snapshot(tmp_path):
    root, mex = _project(tmp_path)

    project = Project.verified(root)
    try:
        assert project.root == root.resolve()
        assert project.mex_file == mex.resolve()
        assert isinstance(project.verified_target, VerifiedProjectTarget)
        assert project.verified_target.mex.content == XML_A
    finally:
        project.verified_target.close()


def test_project_requires_a_verified_target(tmp_path):
    with pytest.raises(TypeError):
        Project(root=tmp_path, backend="s32-mex")  # type: ignore[call-arg]


@pytest.mark.parametrize("raise_inside", [False, True])
def test_project_context_closes_lease_on_success_and_exception(tmp_path, raise_inside):
    root, _ = _project(tmp_path)
    project = Project.verified(root)
    try:
        with project:
            assert not project.verified_target.lease.closed
            if raise_inside:
                raise RuntimeError("boom")
    except RuntimeError:
        assert raise_inside
    assert project.verified_target.lease.closed


def test_target_lease_close_is_thread_safe_and_release_failure_is_not_retried():
    barrier = threading.Barrier(2)
    releases = []

    def release():
        releases.append(1)
        raise RuntimeError("release failed")

    lease = TargetLease(release)
    errors = []
    def close():
        barrier.wait()
        try:
            lease.close()
        except RuntimeError:
            errors.append(1)
    threads = [threading.Thread(target=close) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    lease.close()
    assert releases == [1]
    assert errors == [1]


def test_target_lease_close_waits_for_active_reader_and_releases_once():
    borrowed = threading.Event()
    allow_reader_exit = threading.Event()
    released = threading.Event()
    releases = []
    lease = TargetLease(lambda: (releases.append(1), released.set()))

    def reader():
        with lease.borrow():
            borrowed.set()
            assert allow_reader_exit.wait(timeout=5)

    reader_thread = threading.Thread(target=reader)
    reader_thread.start()
    assert borrowed.wait(timeout=5)
    closers = [threading.Thread(target=lease.close) for _ in range(2)]
    for closer in closers:
        closer.start()
    assert not released.wait(timeout=0.1)
    with pytest.raises(CliFailure) as caught:
        with lease.borrow():
            pass
    assert caught.value.code == "project_target_closed"
    allow_reader_exit.set()
    reader_thread.join(timeout=5)
    for closer in closers:
        closer.join(timeout=5)
    assert releases == [1]
    assert lease.closed


def test_target_lease_close_waits_for_every_concurrent_reader():
    entered = [threading.Event(), threading.Event()]
    exits = [threading.Event(), threading.Event()]
    released = threading.Event()
    lease = TargetLease(released.set)

    def reader(index):
        with lease.borrow():
            entered[index].set()
            assert exits[index].wait(timeout=5)

    readers = [threading.Thread(target=reader, args=(index,)) for index in range(2)]
    for reader_thread in readers:
        reader_thread.start()
    assert all(event.wait(timeout=5) for event in entered)

    closer = threading.Thread(target=lease.close)
    closer.start()
    exits[0].set()
    readers[0].join(timeout=5)
    assert not readers[0].is_alive()
    assert not released.wait(timeout=0.1)

    exits[1].set()
    readers[1].join(timeout=5)
    closer.join(timeout=5)
    assert not readers[1].is_alive()
    assert not closer.is_alive()
    assert released.is_set()
    assert lease.closed


def test_project_relative_reader_rejects_internal_mount_before_open(
    monkeypatch, tmp_path
):
    root, mex = _project(tmp_path)
    settings = root / ".settings"
    platform = _PosixTargetPlatform(
        no_follow_flag=1,
        nonblock_flag=1,
        mount_detector=lambda path: path == settings,
    )
    lease = TargetLease(lambda: None)
    lease._resources.update(platform=platform, root_fd=101)
    target = VerifiedProjectTarget(
        root,
        FileSnapshot(
            mex,
            FileIdentity(1, 2, None),
            len(XML_A),
            1,
            1,
            hashlib.sha256(XML_A).hexdigest(),
            XML_A,
        ),
        lease,
    )
    monkeypatch.setattr(
        target_module.os,
        "open",
        lambda *_args, **_kwargs: pytest.fail(
            "an internal mount must be rejected before opening it"
        ),
    )
    monkeypatch.setattr(target_module.os, "O_DIRECTORY", 0x10000, raising=False)

    try:
        with pytest.raises(CliFailure) as caught:
            target_module.read_project_relative(
                target, ".settings/sample.prefs", max_bytes=32
            )
    finally:
        target.close()

    assert caught.value.code == "unsafe_project_path"
    assert caught.value.details["path"] == str(settings)


@pytest.mark.skipif(os.name != "posix", reason="POSIX openat mount guard")
def test_project_relative_reader_resamples_descendant_mounts(tmp_path):
    root, _ = _project(tmp_path)
    settings = root / ".settings"
    settings.mkdir()
    (settings / "sample.prefs").write_bytes(b"x=1\n")
    sampled = []

    def detector(path):
        sampled.append(path)
        return sampled.count(path) > 1 and path == settings

    platform = _PosixTargetPlatform(mount_detector=detector)
    with verify_project_target(root, platform=platform) as target:
        with pytest.raises(CliFailure) as caught:
            target_module.read_project_relative(
                target, ".settings/sample.prefs", max_bytes=32
            )
    assert caught.value.code == "unsafe_project_path"
    assert sampled.count(settings) >= 2


@pytest.mark.skipif(sys.platform != "linux", reason="Linux bind-mount test")
def test_real_linux_internal_bind_mount_is_rejected(tmp_path):
    root, _ = _project(tmp_path)
    source = tmp_path / "source-settings"
    source.mkdir()
    (source / "sample.prefs").write_bytes(b"x=1\n")
    mountpoint = root / ".settings"
    mountpoint.mkdir()
    mounted = subprocess.run(
        ["mount", "--bind", str(source), str(mountpoint)],
        capture_output=True, text=True, check=False,
    )
    if mounted.returncode != 0:
        pytest.skip("bind mount unavailable in this Linux environment")
    try:
        with verify_project_target(root) as target:
            with pytest.raises(CliFailure) as caught:
                target_module.read_project_relative(
                    target, ".settings/sample.prefs", max_bytes=32
                )
        assert caught.value.code == "unsafe_project_path"
    finally:
        subprocess.run(["umount", str(mountpoint)], check=False)


@pytest.mark.parametrize("error,code", [(PermissionError(), "project_permission_denied"), (OSError(), "unsafe_project_path")])
def test_protect_root_enter_errors_are_typed(tmp_path, error, code):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    @contextmanager
    def fail(_path):
        raise error
        yield
    platform.protect_root = fail
    with pytest.raises(CliFailure) as caught:
        verify_project_target(root, platform=platform)
    assert caught.value.code == code


def test_release_for_publish_revalidates_then_closes(tmp_path):
    root, _ = _project(tmp_path)
    target = verify_project_target(root)
    expectation = release_for_publish(target)
    assert expectation.path == target.mex.path
    assert expectation.identity == target.mex.identity
    assert expectation.sha256 == target.mex.sha256
    assert target.lease.closed


def test_release_for_publish_rejects_a_changed_target_before_release(tmp_path):
    root, _ = _project(tmp_path)
    platform = InjectedPlatform()
    target = verify_project_target(root, platform=platform)
    platform.snapshot_override = replace(
        target.mex,
        sha256=hashlib.sha256(XML_B).hexdigest(),
        content=XML_B,
    )

    try:
        with pytest.raises(CliFailure) as caught:
            release_for_publish(target, platform=platform)
        assert caught.value.code == "project_target_changed"
        assert not target.lease.closed
    finally:
        target.close()


@pytest.mark.parametrize("flow", ["inspect", "check", "validate", "configure"])
def test_public_project_flows_close_lease_when_work_raises(
    monkeypatch, tmp_path, flow
):
    root, _ = (
        _bundle_compatible_project(tmp_path)
        if flow in {"check", "validate", "configure"}
        else _project(tmp_path)
    )
    projects = []
    original_verified = cli.Project.verified

    def tracked_verified(project_root: Path, backend: str = "s32-mex"):
        project = original_verified(project_root, backend)
        projects.append(project)
        return project

    monkeypatch.setattr(cli.Project, "verified", tracked_verified)
    failure = RuntimeError(f"{flow} work failed")
    args = SimpleNamespace(project=root)

    if flow == "inspect":
        monkeypatch.setattr(
            cli.MexDocument,
            "from_snapshot",
            staticmethod(lambda _snapshot: (_ for _ in ()).throw(failure)),
        )
        invoke = lambda: cli.cmd_inspect(args)
    elif flow in {"check", "validate"}:
        monkeypatch.setattr(
            cli,
            "run_static_checks",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
        )
        if flow == "check":
            invoke = lambda: cli.cmd_check(args)
        else:
            validate_args = SimpleNamespace(
                project=root, s32ds_root=None, workspace=None, sdk_path=None
            )
            invoke = lambda: cli.cmd_validate(validate_args)
    else:
        intent = SimpleNamespace(module="test", action="set", payload={})
        plan = SimpleNamespace(to_dict=lambda: {})
        configure_args = SimpleNamespace(project=root, backup=False)

        monkeypatch.setattr(
            cli,
            "_configure_verified_project",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
        )

        invoke = lambda: cli._configure_module(
            configure_args, intent, plan, lambda *_args: None
        )

    with pytest.raises(RuntimeError, match=f"{flow} work failed"):
        invoke()

    assert len(projects) == 1
    assert projects[0].verified_target.lease.closed


def test_secure_target_value_objects_are_frozen(tmp_path):
    root, _ = _project(tmp_path)
    target = verify_project_target(root)

    windows_id = WindowsFileId(volume_serial=1, file_id=b"0" * 16)
    values_and_mutations = (
        (windows_id, "volume_serial", 2),
        (target.mex.identity, "device", 999),
        (target.mex, "sha256", "changed"),
        (target, "root", tmp_path),
        (default_target_platform().inspect(root), "exists", False),
    )
    for value, attribute, replacement in values_and_mutations:
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, replacement)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_real_windows_junction_is_rejected_and_safely_cleaned(tmp_path):
    source = tmp_path / "source"
    root, _ = _project(source)
    junction = tmp_path / "junction"
    import subprocess

    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.skip(f"junction creation unavailable: {completed.stderr}")
    try:
        with pytest.raises(CliFailure) as caught:
            verify_project_target(junction)
        assert caught.value.code == "unsafe_project_path"
    finally:
        # rmdir removes the junction itself and never traverses its target.
        os.rmdir(junction)


@pytest.mark.skipif(os.name != "nt", reason="Windows handle protection test")
def test_real_windows_root_handle_blocks_path_swap(tmp_path):
    root, _ = _project(tmp_path)
    replacement = tmp_path / "replacement"

    with default_target_platform().protect_root(root):
        with pytest.raises(PermissionError):
            root.rename(replacement)

    assert root.is_dir()
    assert not replacement.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows lease lifecycle test")
def test_windows_target_close_releases_path_locks(tmp_path):
    root, mex = _project(tmp_path)
    target = verify_project_target(root)
    replacement = root / "replacement.mex"
    replacement.write_bytes(XML_B)

    with pytest.raises(PermissionError):
        os.replace(replacement, mex)

    target.close()
    os.replace(replacement, mex)

    assert mex.read_bytes() == XML_B


@pytest.mark.skipif(os.name != "nt", reason="Windows lease lifecycle test")
def test_windows_target_context_and_finalizer_release_locks(tmp_path):
    root, _ = _project(tmp_path)
    with verify_project_target(root):
        with pytest.raises(PermissionError):
            root.rename(tmp_path / "blocked")
    first = tmp_path / "first"
    root.rename(first)
    first.rename(root)

    target = verify_project_target(root)
    del target
    gc.collect()
    root.rename(tmp_path / "finalized")


@pytest.mark.skipif(os.name != "nt", reason="Windows lease cleanup test")
def test_windows_verification_failure_releases_all_handles(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(CliFailure):
        verify_project_target(root)

    root.rename(tmp_path / "released")
