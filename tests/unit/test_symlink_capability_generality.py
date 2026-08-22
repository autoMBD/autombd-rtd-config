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
# File:        test_symlink_capability_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-22
# Version:     0.1.0
# Description: Generality tests for the deterministic symlink prerequisite.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import shutil

import pytest

from tests import symlink_capability as capability


@dataclass(frozen=True)
class _CreateCall:
    target: Path
    link: Path
    kind: capability.LinkKind


@dataclass(frozen=True)
class _ObserveCall:
    link: Path
    payload_via_link: Path
    expected_kind: capability.LinkKind


@dataclass
class _RecordingOperations:
    create_errors: dict[capability.LinkKind, BaseException] = field(default_factory=dict)
    observation_errors: dict[capability.LinkKind, BaseException] = field(
        default_factory=dict
    )
    observation_changes: dict[capability.LinkKind, dict[str, object]] = field(
        default_factory=dict
    )
    observation_overrides: dict[
        capability.LinkKind, capability.LinkObservation
    ] = field(default_factory=dict)
    cleanup_error: BaseException | None = None
    create_calls: list[_CreateCall] = field(default_factory=list)
    observe_calls: list[_ObserveCall] = field(default_factory=list)
    cleanup_calls: list[Path] = field(default_factory=list)
    observed_payloads: dict[capability.LinkKind, bytes] = field(default_factory=dict)
    _links: dict[Path, tuple[Path, capability.LinkKind]] = field(default_factory=dict)

    def create_link(
        self,
        *,
        target: Path,
        link: Path,
        kind: capability.LinkKind,
    ) -> None:
        self.create_calls.append(_CreateCall(target, link, kind))
        error = self.create_errors.get(kind)
        if error is not None:
            raise error
        self._links[link] = (target, kind)

    def observe_link(
        self,
        *,
        link: Path,
        payload_via_link: Path,
        expected_kind: capability.LinkKind,
    ) -> capability.LinkObservation:
        self.observe_calls.append(_ObserveCall(link, payload_via_link, expected_kind))
        error = self.observation_errors.get(expected_kind)
        if error is not None:
            raise error
        override = self.observation_overrides.get(expected_kind)
        if override is not None:
            return override
        target, recorded_kind = self._links[link]
        if recorded_kind is capability.LinkKind.FILE:
            translated_payload = target
        else:
            translated_payload = target / payload_via_link.relative_to(link)
        payload = translated_payload.read_bytes()
        self.observed_payloads[expected_kind] = payload
        observation = capability.LinkObservation(
            is_link=True,
            target_exists=target.exists(),
            target_is_directory=target.is_dir(),
            payload=payload,
        )
        return replace(
            observation,
            **self.observation_changes.get(expected_kind, {}),
        )

    def cleanup_owned_tree(self, *, root: Path) -> None:
        self.cleanup_calls.append(root)
        if self.cleanup_error is not None:
            raise self.cleanup_error
        if root.exists() or root.is_symlink():
            shutil.rmtree(root)


def _winerror_1314() -> OSError:
    error = OSError("privilege unavailable")
    error.winerror = 1314  # type: ignore[attr-defined]
    return error


def _probe_parent(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "arbitrary-capability-parent"
    parent.mkdir()
    sentinel = parent / "adjacent-sentinel.keep"
    sentinel.write_bytes(b"outside-owned-tree")
    return parent, sentinel


def test_probe_checks_distinct_file_and_relative_directory_traversal_once(
    tmp_path: Path,
) -> None:
    parent, sentinel = _probe_parent(tmp_path)
    operations = _RecordingOperations()

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.AVAILABLE
    assert "disposition=available" in result.detail
    assert "file=ok" in result.detail
    assert "directory=ok" in result.detail
    assert "cleanup=ok" in result.detail
    assert "winerror=none" in result.detail
    assert [call.kind for call in operations.create_calls] == [
        capability.LinkKind.FILE,
        capability.LinkKind.DIRECTORY,
    ]
    assert [call.expected_kind for call in operations.observe_calls] == [
        capability.LinkKind.FILE,
        capability.LinkKind.DIRECTORY,
    ]
    assert operations.create_calls[0].target != operations.create_calls[1].target
    assert operations.create_calls[0].link != operations.create_calls[1].link
    assert operations.observe_calls[0].payload_via_link == operations.create_calls[0].link
    directory_relative = operations.observe_calls[1].payload_via_link.relative_to(
        operations.create_calls[1].link
    )
    assert directory_relative.parts
    assert operations.observed_payloads[capability.LinkKind.FILE] != (
        operations.observed_payloads[capability.LinkKind.DIRECTORY]
    )
    assert len(operations.cleanup_calls) == 1
    assert operations.cleanup_calls[0].parent == parent
    assert sentinel.read_bytes() == b"outside-owned-tree"
    assert list(parent.iterdir()) == [sentinel]


def test_probe_owns_and_removes_only_a_missing_probe_parent(tmp_path: Path) -> None:
    parent = tmp_path / "new-capability-parent"
    adjacent = tmp_path / "ancestor-sentinel.keep"
    adjacent.write_bytes(b"preserve-adjacent")
    operations = _RecordingOperations()

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.AVAILABLE
    assert len(operations.cleanup_calls) == 1
    assert not parent.exists()
    assert adjacent.read_bytes() == b"preserve-adjacent"


def test_missing_parent_remains_safe_when_owned_tree_cleanup_fails(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "new-partial-failure-parent"
    adjacent = tmp_path / "partial-failure-sentinel.keep"
    adjacent.write_bytes(b"preserve-on-failure")
    operations = _RecordingOperations(cleanup_error=OSError("owned cleanup blocked"))

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.ERROR
    assert "cleanup=error:OSError:owned cleanup blocked" in result.detail
    assert len(operations.cleanup_calls) == 1
    assert operations.cleanup_calls[0].parent == parent
    assert operations.cleanup_calls[0].exists()
    assert adjacent.read_bytes() == b"preserve-on-failure"


@pytest.mark.parametrize(
    ("error_factory", "expected_disposition", "expected_text"),
    [
        (NotImplementedError, capability.ProbeDisposition.UNSUPPORTED, "unsupported"),
        (_winerror_1314, capability.ProbeDisposition.UNAVAILABLE, "WinError 1314"),
    ],
)
def test_capability_absence_checks_both_link_kinds_and_cleans_owned_tree(
    tmp_path: Path,
    error_factory: type[BaseException] | object,
    expected_disposition: capability.ProbeDisposition,
    expected_text: str,
) -> None:
    parent, sentinel = _probe_parent(tmp_path)
    operations = _RecordingOperations(
        create_errors={
            capability.LinkKind.FILE: error_factory(),  # type: ignore[operator]
            capability.LinkKind.DIRECTORY: error_factory(),  # type: ignore[operator]
        }
    )

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is expected_disposition
    assert expected_text in f"{result.reason} {result.detail}"
    assert [call.kind for call in operations.create_calls] == [
        capability.LinkKind.FILE,
        capability.LinkKind.DIRECTORY,
    ]
    assert operations.observe_calls == []
    assert len(operations.cleanup_calls) == 1
    assert sentinel.exists()
    assert list(parent.iterdir()) == [sentinel]


def test_unrelated_error_is_functional_while_other_link_kind_is_still_probed(
    tmp_path: Path,
) -> None:
    parent, sentinel = _probe_parent(tmp_path)
    operations = _RecordingOperations(
        create_errors={capability.LinkKind.FILE: PermissionError("policy denied")}
    )

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.ERROR
    assert "PermissionError" in result.detail
    assert [call.kind for call in operations.create_calls] == [
        capability.LinkKind.FILE,
        capability.LinkKind.DIRECTORY,
    ]
    assert [call.expected_kind for call in operations.observe_calls] == [
        capability.LinkKind.DIRECTORY
    ]
    assert len(operations.cleanup_calls) == 1
    assert sentinel.exists()


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_evidence"),
    [
        ("is_link", False, "not-a-link"),
        ("target_exists", False, "target-missing"),
        ("target_is_directory", True, "wrong-target-kind"),
        ("payload", b"mutated-observation-payload", "payload-mismatch"),
    ],
)
def test_each_observation_dimension_is_independently_required(
    tmp_path: Path,
    field_name: str,
    field_value: object,
    expected_evidence: str,
) -> None:
    parent, sentinel = _probe_parent(tmp_path)
    operations = _RecordingOperations(
        observation_changes={
            capability.LinkKind.FILE: {field_name: field_value},
        }
    )

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.ERROR
    assert f"file=error:mismatch:{expected_evidence}" in result.detail
    assert "directory=ok" in result.detail
    assert "cleanup=ok" in result.detail
    assert len(operations.observe_calls) == 2
    assert sentinel.exists()


@pytest.mark.parametrize(
    ("error_factory", "expected_evidence"),
    [
        (NotImplementedError, "file=error:NotImplementedError"),
        (_winerror_1314, "file=error:OSError"),
    ],
)
def test_observation_stage_capability_shaped_errors_are_functional(
    tmp_path: Path,
    error_factory: type[BaseException] | object,
    expected_evidence: str,
) -> None:
    parent, sentinel = _probe_parent(tmp_path)
    operations = _RecordingOperations(
        observation_errors={
            capability.LinkKind.FILE: error_factory(),  # type: ignore[operator]
        }
    )

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.ERROR
    assert expected_evidence in result.detail
    assert "directory=ok" in result.detail
    assert "cleanup=ok" in result.detail
    assert len(operations.create_calls) == 2
    assert len(operations.observe_calls) == 2
    assert sentinel.exists()


def test_semantic_mismatch_is_functional_and_cleanup_failure_cannot_hide_it(
    tmp_path: Path,
) -> None:
    parent, sentinel = _probe_parent(tmp_path)
    operations = _RecordingOperations(
        observation_overrides={
            capability.LinkKind.FILE: capability.LinkObservation(
                is_link=False,
                target_exists=True,
                target_is_directory=False,
                payload=b"wrong",
            )
        },
        cleanup_error=OSError("cleanup blocked"),
    )

    result = capability.probe_symlink_capability(parent, operations=operations)

    assert result.disposition is capability.ProbeDisposition.ERROR
    assert "file=" in result.detail
    assert "cleanup=error:OSError:cleanup blocked" in result.detail
    assert len(operations.create_calls) == 2
    assert len(operations.observe_calls) == 2
    assert len(operations.cleanup_calls) == 1
    assert sentinel.exists()
    assert operations.cleanup_calls[0].exists()


class _Reporter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_line(self, line: str) -> None:
        self.lines.append(line)


class _PluginManager:
    def __init__(self, reporter: _Reporter) -> None:
        self._reporter = reporter

    def get_plugin(self, name: str) -> _Reporter | None:
        return self._reporter if name == "terminalreporter" else None


class _Config:
    def __init__(self, rootpath: Path, *, require: bool = False) -> None:
        self.rootpath = rootpath
        self.require = require
        self.reporter = _Reporter()
        self.pluginmanager = _PluginManager(self.reporter)

    def getoption(self, name: str) -> bool:
        assert name == "--require-symlink-capability"
        return self.require


class _Item:
    def __init__(self, config: _Config, marker: str | None) -> None:
        self.config = config
        self.marker = marker

    def get_closest_marker(self, name: str) -> object | None:
        return object() if self.marker == name else None


def _result(disposition: capability.ProbeDisposition, detail: str) -> capability.SymlinkCapability:
    return capability.SymlinkCapability(
        disposition=disposition,
        reason="arbitrary probe outcome",
        detail=(
            f"disposition={disposition.value}; reason=arbitrary probe outcome; "
            f"file={detail}; directory={detail}; cleanup=ok; winerror=none"
        ),
    )


def test_pytest_gate_is_lazy_marker_only_and_cached_once_per_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _Config(tmp_path)
    calls: list[Path] = []

    def probe(parent: Path) -> capability.SymlinkCapability:
        calls.append(parent)
        return _result(capability.ProbeDisposition.AVAILABLE, "ok")

    monkeypatch.setattr(capability, "probe_symlink_capability", probe)

    capability.pytest_runtest_setup(_Item(config, None))
    capability.pytest_runtest_setup(_Item(config, "unrelated_marker"))
    assert calls == []

    capability.pytest_runtest_setup(
        _Item(config, "requires_symlink_capability")
    )
    capability.pytest_runtest_setup(
        _Item(config, "requires_symlink_capability")
    )

    assert calls == [tmp_path / "tests" / ".tmp"]
    assert len(config.reporter.lines) == 1
    assert "disposition=available" in config.reporter.lines[0]


@pytest.mark.parametrize(
    "disposition",
    [capability.ProbeDisposition.UNSUPPORTED, capability.ProbeDisposition.UNAVAILABLE],
)
def test_optional_mode_skips_only_marked_unavailable_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    disposition: capability.ProbeDisposition,
) -> None:
    config = _Config(tmp_path)
    monkeypatch.setattr(
        capability,
        "probe_symlink_capability",
        lambda _parent: _result(disposition, "missing"),
    )

    capability.pytest_runtest_setup(_Item(config, None))
    with pytest.raises(pytest.skip.Exception, match=disposition.value):
        capability.pytest_runtest_setup(
            _Item(config, "requires_symlink_capability")
        )


@pytest.mark.parametrize(
    "disposition",
    [capability.ProbeDisposition.UNSUPPORTED, capability.ProbeDisposition.UNAVAILABLE],
)
def test_required_mode_fails_closed_for_missing_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    disposition: capability.ProbeDisposition,
) -> None:
    config = _Config(tmp_path, require=True)
    monkeypatch.setattr(
        capability,
        "probe_symlink_capability",
        lambda _parent: _result(disposition, "missing"),
    )

    with pytest.raises(pytest.fail.Exception, match=disposition.value):
        capability.pytest_runtest_setup(
            _Item(config, "requires_symlink_capability")
        )


def test_functional_probe_error_fails_in_optional_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _Config(tmp_path)
    monkeypatch.setattr(
        capability,
        "probe_symlink_capability",
        lambda _parent: _result(capability.ProbeDisposition.ERROR, "broken-link"),
    )

    with pytest.raises(pytest.fail.Exception, match="broken-link"):
        capability.pytest_runtest_setup(
            _Item(config, "requires_symlink_capability")
        )
