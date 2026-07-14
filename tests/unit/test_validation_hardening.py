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
# File:        test_validation_hardening.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-14
# Version:     0.1.0
# Description: Adversarial tests for fail-closed vendor validation lifecycle.
# =================================================================================

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

import pytest

from rtd_config.backends.s32_mex.process_tree import (
    ProcessOutputLimits,
    ProcessTreeRunner,
)
from rtd_config.backends.s32_mex.validation import ValidationOutcome, run_validation
from rtd_config.backends.s32_mex.validation_workspace import (
    ControlledValidationWorkspace,
)
from rtd_config.errors import CliFailure
from rtd_config.project import Project
from tests.fixtures import copy_uart_fixture
import rtd_config.backends.s32_mex.process_tree as process_tree_module
import rtd_config.backends.s32_mex.validation_workspace as workspace_module


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stdout_truncated": True},
        {"stderr_truncated": True},
        {"output_faults": ["process_output_read_failed"]},
    ],
)
def test_validation_outcome_rejects_untrustworthy_output(kwargs):
    outcome = ValidationOutcome(
        exit_code=0, command=[], log_path="validation.log", **kwargs
    )
    assert outcome.passed is False


@pytest.mark.parametrize("fd,field", [(1, "stdout"), (2, "stderr")])
def test_streamed_severe_survives_invalid_encoding_and_tail_truncation(
    tmp_path, fd, field
):
    severe = b"SEVERE: [TOOL] resource has the following error: bad\xffvalue\n"
    script = (
        "import os,sys,time; fd=int(sys.argv[1]); "
        "os.write(fd,b'SEVERE: [TO'); time.sleep(.03); "
        "os.write(fd,b'OL] resource has the following error: bad\\xffvalue\\n'); "
        "os.write(fd,b'noise\\n'*8192)"
    )
    result = ProcessTreeRunner(
        ProcessOutputLimits(max_bytes=128, max_lines=4)
    ).run(
        [sys.executable, "-c", script, str(fd)],
        cwd=tmp_path,
        env=os.environ,
        timeout_s=10,
    )

    assert getattr(result, f"{field}_truncated") is True
    assert result.code == "process_output_truncated"
    assert any(
        "[TOOL]" in item and "has the following error" in item
        for item in result.severe_problems
    )
    assert severe.decode("utf-8", errors="replace").strip() in result.severe_problems


def test_output_reader_fault_is_structured_and_fails_closed(monkeypatch, tmp_path):
    real_popen = process_tree_module.subprocess.Popen

    class FaultingStream:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def read(self, _size):
            raise OSError("injected reader fault")

        def close(self):
            self.wrapped.close()

    def popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        process.stdout = FaultingStream(process.stdout)
        return process

    monkeypatch.setattr(process_tree_module.subprocess, "Popen", popen)
    result = ProcessTreeRunner().run(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        env=os.environ,
        timeout_s=10,
    )
    assert result.code == "process_output_fault"
    assert result.exit_code != 0
    assert result.output_faults
    assert all("injected reader fault" not in item for item in result.output_faults)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group behavior")
def test_normal_parent_exit_escalates_signal_ignoring_descendant(tmp_path):
    marker = tmp_path / "escaped.txt"
    child = (
        "import pathlib,signal,sys,time; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "time.sleep(1); pathlib.Path(sys.argv[1]).write_text('escaped')"
    )
    parent = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]])"
    )
    started = time.monotonic()
    result = ProcessTreeRunner().run(
        [sys.executable, "-c", parent, child, str(marker)],
        cwd=tmp_path,
        env=os.environ,
        timeout_s=10,
    )
    assert result.code == "process_exit"
    assert time.monotonic() - started < 5
    time.sleep(1.2)
    assert not marker.exists()


def test_interrupt_cleanup_failure_has_stable_code_and_only_bounded_waits(
    monkeypatch, tmp_path
):
    waits = []

    class FakeProcess:
        args = ["validator"]
        pid = 12345
        returncode = None
        stdout = BytesIO(b"")
        stderr = BytesIO(b"")

        def poll(self):
            return self.returncode

        def wait(self, timeout=None):
            waits.append(timeout)
            self.returncode = 125
            return self.returncode

        def kill(self):
            raise OSError("injected kill fault")

    monkeypatch.setattr(
        process_tree_module.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess()
    )
    if os.name == "nt":
        class FakeJob:
            def assign_and_resume(self, _process):
                return None

            def terminate(self):
                raise OSError("injected job termination fault")

            def close(self):
                return None

        monkeypatch.setattr(process_tree_module, "_WindowsJob", FakeJob)
    monkeypatch.setattr(
        ProcessTreeRunner,
        "_interruptible_wait",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    monkeypatch.setattr(
        ProcessTreeRunner, "_terminate_tree", lambda *_args, **_kwargs: False
    )

    with pytest.raises(CliFailure) as caught:
        ProcessTreeRunner().run(
            ["validator"], cwd=tmp_path, env={}, timeout_s=1
        )
    assert caught.value.code == "process_tree_kill_failed"
    assert waits and all(timeout is not None for timeout in waits)


@pytest.mark.parametrize("failure_point", ["inventory", "workspace"])
def test_owned_project_is_closed_exactly_once_on_every_preflight_failure(
    monkeypatch, tmp_path, failure_point
):
    root = copy_uart_fixture(tmp_path)
    calls = []
    original_close = Project.close

    def counted_close(self):
        calls.append(self.root)
        return original_close(self)

    monkeypatch.setattr(Project, "close", counted_close)
    if failure_point == "inventory":
        monkeypatch.setattr(
            Project,
            "capture_validator_inputs",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                CliFailure("inventory_failed", "injected", module="backend")
            ),
        )
        workspace = tmp_path / "validation"
    else:
        workspace = root / "unsafe-workspace"

    with pytest.raises(CliFailure):
        run_validation(
            root, Path("C:/NXP/S32DS.3.6.7"), workspace=workspace
        )
    assert calls == [root]
    renamed = root.with_name(root.name + "-renamed")
    root.rename(renamed)
    renamed.rename(root)


def test_owned_project_close_failure_augments_without_masking_primary(
    monkeypatch, tmp_path
):
    root = copy_uart_fixture(tmp_path)
    close_calls = 0

    def inventory_failure(*_args, **_kwargs):
        raise CliFailure("inventory_failed", "injected primary", module="backend")

    def close_failure(_self):
        nonlocal close_calls
        close_calls += 1
        raise CliFailure("project_close_failed", "injected close", module="backend")

    monkeypatch.setattr(Project, "capture_validator_inputs", inventory_failure)
    monkeypatch.setattr(Project, "close", close_failure)
    with pytest.raises(CliFailure) as caught:
        run_validation(
            root,
            Path("C:/NXP/S32DS.3.6.7"),
            workspace=tmp_path / "validation",
        )
    assert caught.value.code == "inventory_failed"
    assert caught.value.details["project_close_failure"]["code"] == "project_close_failed"
    assert close_calls == 1


def test_workspace_base_identity_cannot_swap_during_run_creation(
    monkeypatch, tmp_path
):
    root = copy_uart_fixture(tmp_path)
    with Project.verified(root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    displaced = tmp_path / "controlled-original"
    attack_succeeded = False
    real_mkdir = os.mkdir

    def attacking_mkdir(path, mode=0o777, *args, **kwargs):
        nonlocal attack_succeeded
        candidate = Path(path)
        if candidate.parent == base and candidate.name.startswith("run-"):
            try:
                base.rename(displaced)
                real_mkdir(base)
                attack_succeeded = True
            except OSError:
                pass
        return real_mkdir(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", attacking_mkdir)
    workspace = ControlledValidationWorkspace(base, inventory)
    try:
        workspace.open()
    except CliFailure:
        pass
    finally:
        workspace.close()
    assert attack_succeeded is False


def test_workspace_identity_cannot_swap_during_materialization(
    monkeypatch, tmp_path
):
    root = copy_uart_fixture(tmp_path)
    with Project.verified(root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    displaced = tmp_path / "controlled-original"
    attack_succeeded = False
    original = ControlledValidationWorkspace._materialize_snapshot

    def attacking_materialize(snapshot, target, **kwargs):
        nonlocal attack_succeeded
        if not attack_succeeded:
            try:
                base.rename(displaced)
                base.mkdir()
                attack_succeeded = True
            except OSError:
                pass
        return original(snapshot, target, **kwargs)

    monkeypatch.setattr(
        ControlledValidationWorkspace, "_materialize_snapshot",
        staticmethod(attacking_materialize),
    )
    workspace = ControlledValidationWorkspace(base, inventory)
    try:
        workspace.open()
    except CliFailure:
        pass
    finally:
        workspace.close()
    assert attack_succeeded is False


def test_workspace_cleanup_keeps_identity_guard_until_recursive_delete(
    monkeypatch, tmp_path
):
    """Cleanup must never delete a replacement installed at the run path."""
    project_root = copy_uart_fixture(tmp_path)
    with Project.verified(project_root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    workspace = ControlledValidationWorkspace(base, inventory).open()
    assert workspace.root is not None
    run_root = workspace.root
    displaced = tmp_path / "displaced-run"
    real_identity = workspace_module._directory_identity
    attack_succeeded = False
    armed = True

    def attack_after_identity_check(path):
        nonlocal attack_succeeded
        identity = real_identity(path)
        if armed and Path(path) == run_root and not attack_succeeded:
            try:
                run_root.rename(displaced)
                run_root.mkdir()
                (run_root / "attacker-owned.txt").write_bytes(b"do not delete")
                attack_succeeded = True
            except OSError:
                pass
        return identity

    monkeypatch.setattr(
        workspace_module, "_directory_identity", attack_after_identity_check
    )
    try:
        workspace.close()
        assert attack_succeeded is False
    finally:
        armed = False
        monkeypatch.setattr(workspace_module, "_directory_identity", real_identity)
        if run_root.exists():
            shutil.rmtree(run_root)
        if displaced.exists():
            shutil.rmtree(displaced)


def test_workspace_cleanup_deletes_nested_bound_tree_before_releasing_guards(
    monkeypatch, tmp_path
):
    project_root = copy_uart_fixture(tmp_path)
    with Project.verified(project_root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    workspace = ControlledValidationWorkspace(base, inventory).open()
    assert workspace.root is not None and workspace.export_dir is not None
    nested = workspace.export_dir / "one" / "two"
    nested.mkdir(parents=True)
    (nested / "generated.c").write_bytes(b"generated")
    root = workspace.root
    original_release = workspace._release_guards
    release_observations = []

    def observed_release():
        release_observations.append(root.exists())
        original_release()

    monkeypatch.setattr(workspace, "_release_guards", observed_release)
    assert workspace.close() == []
    assert release_observations == [False]
    assert not root.exists()


@pytest.mark.parametrize("target_is_directory", [False, True])
def test_workspace_cleanup_rejects_links_without_touching_external_target(
    tmp_path, target_is_directory
):
    project_root = copy_uart_fixture(tmp_path)
    with Project.verified(project_root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    workspace = ControlledValidationWorkspace(base, inventory).open()
    assert workspace.root is not None and workspace.export_dir is not None
    outside = tmp_path / ("outside-dir" if target_is_directory else "outside.txt")
    if target_is_directory:
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"keep")
    else:
        outside.write_bytes(b"keep")
    link = workspace.export_dir / "untrusted-link"
    try:
        link.symlink_to(outside, target_is_directory=target_is_directory)
    except OSError as exc:
        workspace.close()
        pytest.skip(f"symlink unavailable: {exc}")

    warnings = workspace.close()
    assert warnings and warnings[0]["code"] == "validation_cleanup_failed"
    if target_is_directory:
        assert (outside / "keep.txt").read_bytes() == b"keep"
    else:
        assert outside.read_bytes() == b"keep"
    shutil.rmtree(workspace.root)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_windows_cleanup_rejects_junction_without_touching_external_tree(tmp_path):
    project_root = copy_uart_fixture(tmp_path)
    with Project.verified(project_root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    workspace = ControlledValidationWorkspace(base, inventory).open()
    assert workspace.root is not None and workspace.export_dir is not None
    outside = tmp_path / "outside-junction-target"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_bytes(b"keep")
    junction = workspace.export_dir / "untrusted-junction"
    created = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if created.returncode != 0:
        workspace.close()
        pytest.skip("junction creation unavailable")

    warnings = workspace.close()
    assert warnings and warnings[0]["code"] == "validation_cleanup_failed"
    assert marker.read_bytes() == b"keep"
    os.rmdir(junction)
    shutil.rmtree(workspace.root)


@pytest.mark.skipif(os.name != "nt", reason="Windows handle-lock behavior")
@pytest.mark.parametrize("seam", ["enumerate", "delete"])
def test_windows_cleanup_blocks_root_swap_during_enumerate_or_delete(
    monkeypatch, tmp_path, seam
):
    project_root = copy_uart_fixture(tmp_path)
    with Project.verified(project_root) as project:
        inventory = project.capture_validator_inputs()
    base = tmp_path / "controlled"
    base.mkdir()
    workspace = ControlledValidationWorkspace(base, inventory).open()
    assert workspace.root is not None
    root = workspace.root
    displaced = tmp_path / "displaced-run"
    attack_succeeded = False

    def attack():
        nonlocal attack_succeeded
        try:
            root.rename(displaced)
            root.mkdir()
            attack_succeeded = True
        except OSError:
            pass

    if seam == "enumerate":
        real_scandir = os.scandir

        def attacking_scandir(path):
            if Path(path) == root:
                attack()
            return real_scandir(path)

        monkeypatch.setattr(os, "scandir", attacking_scandir)
    else:
        real_delete = workspace_module._windows_mark_delete

        def attacking_delete(handle):
            attack()
            return real_delete(handle)

        monkeypatch.setattr(workspace_module, "_windows_mark_delete", attacking_delete)

    assert workspace.close() == []
    assert attack_succeeded is False
    assert not root.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle-lock behavior")
def test_windows_cleanup_holds_workspace_ancestors_during_recursive_delete(
    monkeypatch, tmp_path
):
    project_root = copy_uart_fixture(tmp_path)
    with Project.verified(project_root) as project:
        inventory = project.capture_validator_inputs()
    ancestor = tmp_path / "workspace-ancestor"
    base = ancestor / "controlled"
    base.mkdir(parents=True)
    workspace = ControlledValidationWorkspace(base, inventory).open()
    assert workspace.root is not None
    root = workspace.root
    displaced = tmp_path / "displaced-ancestor"
    attack_succeeded = False
    real_scandir = os.scandir

    def attacking_scandir(path):
        nonlocal attack_succeeded
        if Path(path) == root and not attack_succeeded:
            try:
                ancestor.rename(displaced)
                ancestor.mkdir()
                attack_succeeded = True
            except OSError:
                pass
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", attacking_scandir)
    assert workspace.close() == []
    assert attack_succeeded is False
    assert not root.exists()
