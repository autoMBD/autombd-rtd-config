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
# File:        test_absent_backup_publication_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-22
# Version:     0.1.0
# Description: Generality tests for classified absent-backup publication.
# =================================================================================

from __future__ import annotations

import hashlib
import inspect
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.apply import ApplyResult
from rtd_config.backends.s32_mex.target import (
    AtomicPublishFailure,
    AtomicPublishResult,
    AtomicPublishState,
    FileIdentity,
    FileSnapshot,
    PathInspection,
    atomic_install_absent,
    default_target_platform,
    rollback_atomic_publish,
)
from rtd_config.backends.s32_mex.transaction import ConfigureTransaction
from rtd_config.errors import CliFailure
from rtd_config.intent import Intent
from rtd_config.project import Project
from tests.fixtures import UART_FIXTURE


class _DelegatingInstallAdapter:
    def __init__(self) -> None:
        self.delegate = default_target_platform()
        self.install_calls: list[tuple[Path, Path]] = []

    def install_absent(self, staging: Path, destination: Path) -> None:
        self.install_calls.append((staging, destination))
        os.replace(staging, destination)

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


class _ClassifyingAdapter:
    def __init__(
        self,
        destination: Path,
        inspection: PathInspection,
        *,
        snapshot_error: Exception | None = None,
    ) -> None:
        self.delegate = default_target_platform()
        self.destination = destination
        self.inspection = inspection
        self.snapshot_error = snapshot_error
        self.destination_snapshot_calls = 0

    def inspect(self, path: Path) -> PathInspection:
        if path == self.destination:
            return self.inspection
        return self.delegate.inspect(path)

    def snapshot_file(self, path: Path) -> FileSnapshot:
        if path == self.destination:
            self.destination_snapshot_calls += 1
            if self.snapshot_error is not None:
                raise self.snapshot_error
        return self.delegate.snapshot_file(path)

    def __getattr__(self, name: str):
        return getattr(self.delegate, name)


def _stage(tmp_path: Path, stem: str, payload: bytes) -> tuple[Path, Path, str]:
    staging = tmp_path / f".{stem}.candidate.payload"
    destination = tmp_path / f"{stem}.archive"
    staging.write_bytes(payload)
    return staging, destination, hashlib.sha256(payload).hexdigest()


def _forged_result(tmp_path: Path) -> AtomicPublishResult:
    content = b"forged-publication-receipt"
    path = tmp_path / "forged.receipt"
    snapshot = FileSnapshot(
        path=path,
        identity=FileIdentity(-701, -809, None),
        size=len(content),
        mtime_ns=11,
        ctime_ns=13,
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )
    return AtomicPublishResult(
        snapshot,
        None,
        None,
        AtomicPublishState(path, tmp_path / "forged.candidate", published=snapshot),
    )


def test_public_signatures_add_only_the_purpose_specific_install_dependency():
    install_parameters = inspect.signature(atomic_install_absent).parameters
    assert list(install_parameters) == [
        "path", "staging", "candidate_sha256", "platform", "install_fn"
    ]
    assert install_parameters["install_fn"].kind is inspect.Parameter.KEYWORD_ONLY
    assert install_parameters["install_fn"].default is None

    transaction_parameters = inspect.signature(ConfigureTransaction.__init__).parameters
    assert list(transaction_parameters) == [
        "self",
        "project",
        "plan",
        "binding",
        "backup",
        "static_runner",
        "vendor_runner",
        "atomic_publish_fn",
        "release_for_publish_fn",
        "backup_install_absent_fn",
    ]
    dependency = transaction_parameters["backup_install_absent_fn"]
    assert dependency.kind is inspect.Parameter.KEYWORD_ONLY
    assert dependency.default is None


@pytest.mark.parametrize("use_override", [False, True])
def test_install_override_and_selected_adapter_receive_candidate_then_destination(
    tmp_path: Path, use_override: bool
):
    payload = b"bounded-general-input::quartz::17"
    staging, destination, digest = _stage(
        tmp_path, f"quartz-{int(use_override)}", payload
    )
    adapter = _DelegatingInstallAdapter()
    override_calls: list[tuple[Path, Path]] = []

    def override(candidate: Path, backup: Path) -> None:
        override_calls.append((candidate, backup))
        os.replace(candidate, backup)

    result = atomic_install_absent(
        destination,
        staging,
        digest,
        platform=adapter,
        install_fn=override if use_override else None,
    )

    assert result.published.path == destination
    assert result.published.content == payload
    expected_call = [(staging, destination)]
    assert override_calls == (expected_call if use_override else [])
    assert adapter.install_calls == ([] if use_override else expected_call)


def test_helper_ignores_a_forged_primitive_result_and_owns_cleanup_state(
    tmp_path: Path,
):
    payload = b"bounded-general-input::indigo::29"
    staging, destination, digest = _stage(tmp_path, "indigo-ledger", payload)
    forged = _forged_result(tmp_path)
    adapter = _DelegatingInstallAdapter()

    def install(candidate: Path, backup: Path):
        os.replace(candidate, backup)
        return forged

    result = atomic_install_absent(
        destination, staging, digest, platform=adapter, install_fn=install
    )

    assert result is not forged
    assert result.published.content == payload
    assert result.published.identity != forged.published.identity
    assert result.state is not None
    assert result.state.phase == "published"
    assert result.state.published == result.published
    assert rollback_atomic_publish(result, destination, platform=adapter) is None
    assert not destination.exists()


def test_precheck_conflict_and_primitive_failure_are_backup_changes(
    tmp_path: Path,
):
    payload = b"bounded-general-input::copper::31"
    staging, destination, digest = _stage(tmp_path, "copper-journal", payload)
    destination.write_bytes(b"pre-existing-unowned-evidence")
    calls: list[tuple[Path, Path]] = []

    with pytest.raises(CliFailure) as conflict:
        atomic_install_absent(
            destination,
            staging,
            digest,
            install_fn=lambda source, target: calls.append((source, target)),
        )
    assert conflict.value.code == "configure_backup_changed"
    assert calls == []
    assert destination.read_bytes() == b"pre-existing-unowned-evidence"
    assert staging.read_bytes() == payload

    destination.unlink()

    def fail_before_return(_source: Path, _target: Path) -> None:
        raise OSError("bounded primitive failure")

    with pytest.raises(CliFailure) as primitive:
        atomic_install_absent(
            destination, staging, digest, install_fn=fail_before_return
        )
    assert primitive.value.code == "configure_backup_changed"
    assert not destination.exists()
    assert staging.read_bytes() == payload


@pytest.mark.parametrize(
    ("outcome", "inspection"),
    [
        (
            "reparse",
            PathInspection(True, False, False, False, True, False),
        ),
        (
            "directory",
            PathInspection(True, True, False, False, False, False),
        ),
    ],
)
def test_post_return_unclassifiable_entries_are_uncertain_without_following(
    tmp_path: Path, outcome: str, inspection: PathInspection
):
    payload = f"bounded-general-input::{outcome}::37".encode()
    staging, destination, digest = _stage(tmp_path, f"{outcome}-vault", payload)
    adapter = _ClassifyingAdapter(destination, inspection)

    def install(_candidate: Path, backup: Path) -> None:
        backup.mkdir()

    with pytest.raises(AtomicPublishFailure) as caught:
        atomic_install_absent(
            destination, staging, digest, platform=adapter, install_fn=install
        )

    assert caught.value.code == "configure_backup_uncertain"
    assert caught.value.state.phase == "installed"
    assert adapter.destination_snapshot_calls == 0
    assert destination.is_dir()
    assert staging.read_bytes() == payload
    assert set(caught.value.details["preserved"]) == {
        destination.name,
        staging.name,
    }


@pytest.mark.parametrize("outcome", ["missing", "snapshot-failure"])
def test_post_return_missing_or_snapshot_failure_is_uncertain(
    tmp_path: Path, outcome: str
):
    payload = f"bounded-general-input::{outcome}::41".encode()
    staging, destination, digest = _stage(tmp_path, f"{outcome}-record", payload)
    adapter = _ClassifyingAdapter(
        destination,
        PathInspection(
            outcome != "missing", False, outcome != "missing", False, False, False
        ),
        snapshot_error=(
            OSError("bounded snapshot failure")
            if outcome == "snapshot-failure"
            else None
        ),
    )

    def install(candidate: Path, backup: Path) -> None:
        if outcome == "missing":
            candidate.unlink()
        else:
            os.replace(candidate, backup)

    with pytest.raises(AtomicPublishFailure) as caught:
        atomic_install_absent(
            destination, staging, digest, platform=adapter, install_fn=install
        )

    assert caught.value.code == "configure_backup_uncertain"
    assert caught.value.state.phase == "installed"
    assert set(caught.value.details["preserved"]) == {
        destination.name,
        staging.name,
    }


@pytest.mark.parametrize("foreign_content", [b"different-foreign-bytes", None])
def test_post_return_foreign_identity_or_content_is_staging_changed_and_preserved(
    tmp_path: Path, foreign_content: bytes | None
):
    payload = b"bounded-general-input::saffron::43"
    stem = "different-content" if foreign_content is not None else "same-content"
    staging, destination, digest = _stage(tmp_path, stem, payload)

    def install(candidate: Path, backup: Path) -> None:
        backup.write_bytes(payload if foreign_content is None else foreign_content)
        assert candidate.exists()

    with pytest.raises(AtomicPublishFailure) as caught:
        atomic_install_absent(destination, staging, digest, install_fn=install)

    assert caught.value.code == "configure_staging_changed"
    assert caught.value.state.phase == "installed"
    assert caught.value.state.published is not None
    assert destination.read_bytes() == (
        payload if foreign_content is None else foreign_content
    )
    assert staging.read_bytes() == payload
    assert set(caught.value.details["preserved"]) == {
        destination.name,
        staging.name,
    }


@pytest.mark.parametrize(
    ("backup", "existing_backup", "expected_calls"),
    [(False, False, 0), (True, True, 0), (True, False, 1)],
)
def test_transaction_routes_install_dependency_only_to_an_absent_backup(
    tmp_path: Path,
    backup: bool,
    existing_backup: bool,
    expected_calls: int,
):
    route_name = f"route-{int(backup)}-{int(existing_backup)}"
    root = tmp_path / route_name
    shutil.copytree(UART_FIXTURE, root)
    mex_path = next(root.glob("*.mex"))
    backup_path = mex_path.with_name(mex_path.name + ".bak")
    if existing_backup:
        backup_path.write_bytes(b"bounded-preexisting-backup::47")
    project = Project.verified(root)
    cli._preflight_project(project)
    calls: list[tuple[Path, Path]] = []

    def install(candidate: Path, destination: Path) -> None:
        calls.append((candidate, destination))
        os.replace(candidate, destination)

    def apply(document, _intent, *, bundle) -> ApplyResult:
        del bundle
        config = document.find_config_set("Uart")
        setting = next(item for item in config.iter() if item.tag.endswith("setting"))
        setting.attrib["value"] = f"GENERALITY_ROUTE_{route_name}"
        return ApplyResult(changed_modules=["uart"], modified_elements=[setting])

    result = ConfigureTransaction(
        project,
        backup=backup,
        static_runner=lambda *_args, **_kwargs: SimpleNamespace(status="passed"),
        backup_install_absent_fn=install,
    ).execute(Intent("surface", "mutate", {"route": route_name}), apply)

    assert result.status == "passed"
    assert result.published is True
    assert len(calls) == expected_calls
    if calls:
        candidate, destination = calls[0]
        assert candidate.name.startswith(f".{mex_path.name}.backup.")
        assert destination == backup_path
    assert backup_path.exists() is backup
