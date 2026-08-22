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
# File:        symlink_capability.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-22
# Version:     0.1.0
# Description: Lazy pytest prerequisite for real file and directory symlinks.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import shutil
from typing import Protocol
from uuid import uuid4

import pytest


class ProbeDisposition(str, Enum):
    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class LinkKind(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True)
class LinkObservation:
    is_link: bool
    target_exists: bool
    target_is_directory: bool
    payload: bytes


class ProbeOperations(Protocol):
    def create_link(
        self,
        *,
        target: Path,
        link: Path,
        kind: LinkKind,
    ) -> None: ...

    def observe_link(
        self,
        *,
        link: Path,
        payload_via_link: Path,
        expected_kind: LinkKind,
    ) -> LinkObservation: ...

    def cleanup_owned_tree(self, *, root: Path) -> None: ...


@dataclass(frozen=True)
class SymlinkCapability:
    disposition: ProbeDisposition
    reason: str
    detail: str


class _PathOperations:
    def create_link(
        self,
        *,
        target: Path,
        link: Path,
        kind: LinkKind,
    ) -> None:
        if not hasattr(os, "symlink"):
            raise NotImplementedError("os.symlink is unavailable")
        link.symlink_to(target, target_is_directory=kind is LinkKind.DIRECTORY)

    def observe_link(
        self,
        *,
        link: Path,
        payload_via_link: Path,
        expected_kind: LinkKind,
    ) -> LinkObservation:
        del expected_kind
        return LinkObservation(
            is_link=link.is_symlink(),
            target_exists=link.exists(),
            target_is_directory=link.is_dir(),
            payload=payload_via_link.read_bytes(),
        )

    def cleanup_owned_tree(self, *, root: Path) -> None:
        if root.is_symlink():
            root.unlink()
        elif root.exists():
            shutil.rmtree(root)


@dataclass(frozen=True)
class _ProbeCase:
    kind: LinkKind
    target: Path
    link: Path
    payload_via_link: Path
    payload: bytes


def _safe_text(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace(";", ",")


def _error_text(error: BaseException) -> str:
    return f"{type(error).__name__}:{_safe_text(error)}"


def _validate_observation(
    observation: LinkObservation,
    *,
    expected_kind: LinkKind,
    expected_payload: bytes,
) -> str:
    mismatches: list[str] = []
    if not observation.is_link:
        mismatches.append("not-a-link")
    if not observation.target_exists:
        mismatches.append("target-missing")
    expected_directory = expected_kind is LinkKind.DIRECTORY
    if observation.target_is_directory is not expected_directory:
        mismatches.append("wrong-target-kind")
    if observation.payload != expected_payload:
        mismatches.append("payload-mismatch")
    return "ok" if not mismatches else "error:mismatch:" + ",".join(mismatches)


def _summarize_disposition(
    statuses: dict[LinkKind, str], *, cleanup_status: str
) -> ProbeDisposition:
    if cleanup_status.startswith("error:"):
        return ProbeDisposition.ERROR
    if any(value.startswith("error:") for value in statuses.values()):
        return ProbeDisposition.ERROR
    if any(value.startswith("unavailable:") for value in statuses.values()):
        return ProbeDisposition.UNAVAILABLE
    if any(value.startswith("unsupported:") for value in statuses.values()):
        return ProbeDisposition.UNSUPPORTED
    return ProbeDisposition.AVAILABLE


def _reason_for(disposition: ProbeDisposition) -> str:
    return {
        ProbeDisposition.AVAILABLE: "file and directory symlink traversal is available",
        ProbeDisposition.UNSUPPORTED: "symbolic links are unsupported",
        ProbeDisposition.UNAVAILABLE: "symbolic-link capability is unavailable",
        ProbeDisposition.ERROR: "symbolic-link capability probe failed",
    }[disposition]


def probe_symlink_capability(
    probe_parent: Path,
    *,
    operations: ProbeOperations | None = None,
) -> SymlinkCapability:
    active_operations = operations if operations is not None else _PathOperations()
    owned_tree = Path(probe_parent) / f"symlink-capability-{uuid4().hex}"
    statuses = {LinkKind.FILE: "not-run", LinkKind.DIRECTORY: "not-run"}
    winerrors: set[int] = set()
    cleanup_status = "not-needed"
    owned_tree_created = False

    try:
        owned_tree.mkdir()
        owned_tree_created = True
        file_payload = b"symlink-capability-file-payload\n"
        directory_payload = b"symlink-capability-directory-payload\n"
        file_target = owned_tree / "file-source.bin"
        file_target.write_bytes(file_payload)
        directory_target = owned_tree / "directory-source"
        directory_relative = Path("relative") / "traversal" / "payload.bin"
        (directory_target / directory_relative.parent).mkdir(parents=True)
        (directory_target / directory_relative).write_bytes(directory_payload)

        cases = (
            _ProbeCase(
                kind=LinkKind.FILE,
                target=file_target,
                link=owned_tree / "file-link",
                payload_via_link=owned_tree / "file-link",
                payload=file_payload,
            ),
            _ProbeCase(
                kind=LinkKind.DIRECTORY,
                target=directory_target,
                link=owned_tree / "directory-link",
                payload_via_link=owned_tree / "directory-link" / directory_relative,
                payload=directory_payload,
            ),
        )
        for case in cases:
            try:
                active_operations.create_link(
                    target=case.target,
                    link=case.link,
                    kind=case.kind,
                )
                observation = active_operations.observe_link(
                    link=case.link,
                    payload_via_link=case.payload_via_link,
                    expected_kind=case.kind,
                )
                statuses[case.kind] = _validate_observation(
                    observation,
                    expected_kind=case.kind,
                    expected_payload=case.payload,
                )
            except NotImplementedError as error:
                statuses[case.kind] = f"unsupported:{_error_text(error)}"
            except OSError as error:
                winerror = getattr(error, "winerror", None)
                if winerror == 1314:
                    winerrors.add(1314)
                    statuses[case.kind] = "unavailable:WinError 1314"
                else:
                    statuses[case.kind] = f"error:{_error_text(error)}"
            except BaseException as error:
                statuses[case.kind] = f"error:{_error_text(error)}"
    except BaseException as error:
        statuses[LinkKind.FILE] = f"error:setup:{_error_text(error)}"
        statuses[LinkKind.DIRECTORY] = "not-run"
    finally:
        if owned_tree_created:
            try:
                active_operations.cleanup_owned_tree(root=owned_tree)
                cleanup_status = "ok"
            except BaseException as error:
                cleanup_status = f"error:{_error_text(error)}"

    disposition = _summarize_disposition(statuses, cleanup_status=cleanup_status)
    reason = _reason_for(disposition)
    winerror_text = ",".join(str(value) for value in sorted(winerrors)) or "none"
    detail = (
        f"disposition={disposition.value}; reason={reason}; "
        f"file={statuses[LinkKind.FILE]}; "
        f"directory={statuses[LinkKind.DIRECTORY]}; "
        f"cleanup={cleanup_status}; winerror={winerror_text}"
    )
    return SymlinkCapability(disposition=disposition, reason=reason, detail=detail)


_CACHE_ATTRIBUTE = "_rtd_symlink_capability_result"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("symlink capability")
    group.addoption(
        "--require-symlink-capability",
        action="store_true",
        default=False,
        help="Fail instead of skip when file/directory symlinks are unavailable.",
    )


def _session_capability(config: pytest.Config) -> SymlinkCapability:
    cached = getattr(config, _CACHE_ATTRIBUTE, None)
    if cached is not None:
        return cached
    result = probe_symlink_capability(config.rootpath / "tests" / ".tmp")
    setattr(config, _CACHE_ATTRIBUTE, result)
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(f"symlink capability: {result.detail}")
    return result


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("requires_symlink_capability") is None:
        return
    result = _session_capability(item.config)
    message = f"symlink capability prerequisite: {result.detail}"
    if result.disposition is ProbeDisposition.AVAILABLE:
        return
    if result.disposition is ProbeDisposition.ERROR:
        pytest.fail(message, pytrace=False)
    if item.config.getoption("--require-symlink-capability"):
        pytest.fail(message, pytrace=False)
    pytest.skip(message)
