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
# File:        test_symlink_prerequisite.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-13
# Version:     0.1.0
# Description: Public contract tests for the symlink-capability prerequisite.
# =================================================================================

from __future__ import annotations

import importlib
import inspect
import shutil
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Protocol

import pytest


def _api():
    return importlib.import_module("tests.symlink_capability")

class ReferenceOperations:
    """Complete link adapter that follows recorded links without Path patching."""
    def __init__(self, *, create_error: Exception | None = None,
                 observation_change: str | None = None, observe_error: Exception | None = None,
                 cleanup_error: Exception | None = None) -> None:
        self.create_error = create_error
        self.observation_change = observation_change
        self.observe_error = observe_error
        self.cleanup_error = cleanup_error
        self.links: dict[Path, tuple[Path, object]] = {}
        self.observations: list[tuple[Path, Path, object, object]] = []
        self.cleanup_roots: list[Path] = []
        self.paths: list[Path] = []
    def create_link(self, *, target: Path, link: Path, kind: object) -> None:
        self.paths.extend((target, link))
        self.links[link] = (target, kind)
        if self.create_error is not None:
            raise self.create_error
        assert target.exists()
    def observe_link(
        self, *, link: Path, payload_via_link: Path, expected_kind: object
    ) -> object:
        target, actual_kind = self.links[link]
        self.paths.extend((link, payload_via_link))
        assert expected_kind is actual_kind
        if self.observe_error is not None:
            raise self.observe_error
        assert actual_kind.value != "file" or payload_via_link == link
        payload_path = target if actual_kind.value == "file" else (
            target / payload_via_link.relative_to(link)
        )
        observation = _api().LinkObservation(
            is_link=True,
            target_exists=target.exists(),
            target_is_directory=target.is_dir(),
            payload=payload_path.read_bytes(),
        )
        changes = dict(
            not_link={"is_link": False}, broken={"target_exists": False},
            wrong_kind={"target_is_directory": not observation.target_is_directory},
            wrong_payload={"payload": observation.payload + b"wrong"},
        )
        if self.observation_change is not None:
            change = changes[self.observation_change.replace("-", "_")]
            observation = replace(observation, **change)
        self.observations.append((link, payload_via_link, expected_kind, observation))
        return observation
    def cleanup_owned_tree(self, *, root: Path) -> None:
        self.cleanup_roots.append(root)
        for path in self.paths:
            assert path != root
            path.relative_to(root)
        assert all(target != link for link, (target, _kind) in self.links.items())
        if self.cleanup_error is not None:
            raise self.cleanup_error
        shutil.rmtree(root)

def _winerror(code: int) -> OSError:
    error = OSError(f"Windows error {code}")
    error.winerror = code
    return error

def _sentinel(parent: Path) -> Path:
    sentinel = parent / "adjacent-sentinel"
    sentinel.write_bytes(b"preserve")
    return sentinel

def _assert_owned_cleanup(operations, parent, sentinel, *, removed=True):
    assert len(operations.cleanup_roots) == 1
    root = operations.cleanup_roots[0]
    assert root != parent and root.parent == parent
    assert not removed or not root.exists()
    assert sentinel.read_bytes() == b"preserve"

def test_public_operations_protocol_and_keyword_only_signatures():
    api = _api()
    assert issubclass(api.ProbeOperations, Protocol)
    expected = {
        api.ProbeOperations.create_link: ("target", "link", "kind"),
        api.ProbeOperations.observe_link: ("link", "payload_via_link", "expected_kind"),
        api.ProbeOperations.cleanup_owned_tree: ("root",),
    }
    for method, names in expected.items():
        parameters = tuple(inspect.signature(method).parameters.values())
        assert parameters[0].name == "self"
        assert tuple(item.name for item in parameters[1:]) == names
        assert all(item.kind is inspect.Parameter.KEYWORD_ONLY for item in parameters[1:])
    probe = inspect.signature(api.probe_symlink_capability).parameters
    assert probe["operations"].kind is inspect.Parameter.KEYWORD_ONLY

def test_available_probes_distinct_file_and_directory_links_and_cleans_up(tmp_path):
    api = _api()
    sentinel = _sentinel(tmp_path)
    operations = ReferenceOperations()
    result = api.probe_symlink_capability(tmp_path, operations=operations)
    assert result.disposition is api.ProbeDisposition.AVAILABLE
    assert [item.value for item in api.ProbeDisposition] == [
        "available", "unsupported", "unavailable", "error"
    ]
    assert [item.value for item in api.LinkKind] == ["file", "directory"]
    assert {kind for _target, kind in operations.links.values()} == set(api.LinkKind)
    assert len(operations.links) == len(operations.observations) == 2
    root = operations.cleanup_roots[0]
    targets = {target for target, _kind in operations.links.values()}
    links = set(operations.links)
    assert len(targets) == len(links) == 2 and targets.isdisjoint(links)
    for target, link in zip(targets, links):
        target.relative_to(root)
        link.relative_to(root)
    for link, payload_path, expected_kind, _observation in operations.observations:
        payload_path.relative_to(root)
        assert operations.links[link][1] is expected_kind
    observed = [item[3] for item in operations.observations]
    assert all(item.is_link and item.target_exists for item in observed)
    assert {item.target_is_directory for item in observed} == {False, True}
    assert len({item.payload for item in observed}) == 2
    assert all(item.payload for item in observed)
    _assert_owned_cleanup(operations, tmp_path, sentinel)
    assert set(tmp_path.iterdir()) == {sentinel}
    with pytest.raises(FrozenInstanceError):
        result.reason = "mutated"
    with pytest.raises(FrozenInstanceError):
        observed[0].payload = b"mutated"

def test_not_implemented_is_unsupported_and_still_cleans_up(tmp_path):
    api = _api()
    operations = ReferenceOperations(create_error=NotImplementedError("no API"))
    sentinel = _sentinel(tmp_path)
    result = api.probe_symlink_capability(tmp_path, operations=operations)
    assert result.disposition is api.ProbeDisposition.UNSUPPORTED
    _assert_owned_cleanup(operations, tmp_path, sentinel)

def test_winerror_1314_is_unavailable_with_literal_evidence(tmp_path):
    api = _api()
    operations = ReferenceOperations(create_error=_winerror(1314))
    sentinel = _sentinel(tmp_path)
    result = api.probe_symlink_capability(tmp_path, operations=operations)
    assert result.disposition is api.ProbeDisposition.UNAVAILABLE
    assert "WinError 1314" in result.detail
    _assert_owned_cleanup(operations, tmp_path, sentinel)

@pytest.mark.parametrize(
    ("operations"),
    [
        ReferenceOperations(create_error=PermissionError("denied")),
        ReferenceOperations(create_error=_winerror(5)),
        ReferenceOperations(observation_change="not-link"),
        ReferenceOperations(observation_change="broken"),
        ReferenceOperations(observation_change="wrong-kind"),
        ReferenceOperations(observation_change="wrong-payload"),
        ReferenceOperations(observe_error=OSError("observe failed")),
        ReferenceOperations(cleanup_error=OSError("cleanup failed")),
    ],
    ids=[
        "permission-error", "other-oserror", "not-link", "broken-link",
        "wrong-kind", "wrong-payload", "observe-error", "cleanup-failure",
    ],
)
def test_other_failures_are_errors_and_never_escape(tmp_path, operations):
    api = _api()
    sentinel = _sentinel(tmp_path)
    result = api.probe_symlink_capability(tmp_path, operations=operations)
    assert isinstance(result, api.SymlinkCapability)
    assert result.disposition is api.ProbeDisposition.ERROR
    assert result.detail
    if operations.observe_error is not None:
        assert "observe failed" in result.detail
    _assert_owned_cleanup(operations, tmp_path, sentinel, removed=operations.cleanup_error is None)
