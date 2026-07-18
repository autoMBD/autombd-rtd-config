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
# File:        generate_release_manifest.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-15
# Version:     0.1.0
# Description: Generate or check the deterministic released-Skill file and hash
#              allowlist from the exact Git-tracked publication boundary.
# =================================================================================

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
from pathlib import Path
import subprocess
import sys

from deploy_rtd_skill import (
    RELEASE_MANIFEST_NAME,
    SKILL_NAME,
    build_release_manifest,
    read_project_version,
    read_release_manifest,
    release_manifest_bytes,
    verify_release_payload,
    write_release_manifest,
)


def tracked_payload_paths(repo_root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", SKILL_NAME],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"cannot read Git release boundary: {result.stderr.strip()}")
    prefix = f"{SKILL_NAME}/"
    paths = []
    for tracked in result.stdout.splitlines():
        if not tracked.startswith(prefix):
            raise RuntimeError(f"unexpected tracked release path: {tracked!r}")
        relative = tracked[len(prefix):]
        if relative != RELEASE_MANIFEST_NAME:
            paths.append(relative)
    return tuple(sorted(paths))


def require_lf_checkout_attributes(
    repo_root: Path,
    paths: tuple[str, ...],
) -> None:
    tracked = tuple(f"{SKILL_NAME}/{path}" for path in paths)
    result = subprocess.run(
        ["git", "-C", str(repo_root), "check-attr", "-z", "--stdin", "eol"],
        input=("\0".join(tracked) + "\0").encode("utf-8"),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"cannot read Git release EOL attributes: {stderr}")
    fields = result.stdout.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) != len(tracked) * 3:
        raise RuntimeError("Git returned malformed release EOL attributes")
    attributes = {
        fields[index].decode("utf-8", errors="surrogateescape"): fields[index + 2]
        .decode("utf-8", errors="replace")
        .lower()
        for index in range(0, len(fields), 3)
    }
    invalid = [path for path in tracked if attributes.get(path) != "lf"]
    if invalid:
        raise RuntimeError(
            "every tracked release payload file must use Git eol=lf; "
            f"invalid={invalid}"
        )


def _lf_checkout_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def expected_manifest(repo_root: Path):
    skill_root = repo_root / SKILL_NAME
    version = read_project_version(repo_root / "pyproject.toml")
    paths = tracked_payload_paths(repo_root)
    require_lf_checkout_attributes(repo_root, paths)
    manifest = build_release_manifest(
        skill_root,
        version,
        paths,
    )
    return replace(
        manifest,
        files=tuple(
            replace(
                entry,
                sha256=hashlib.sha256(
                    _lf_checkout_bytes(
                        skill_root.joinpath(*Path(entry.path).parts)
                    )
                ).hexdigest(),
            )
            for entry in manifest.files
        ),
    )


def check_manifest(repo_root: Path) -> None:
    skill_root = repo_root / SKILL_NAME
    expected = expected_manifest(repo_root)
    manifest_file = skill_root / RELEASE_MANIFEST_NAME
    if manifest_file.read_bytes() != release_manifest_bytes(expected):
        raise RuntimeError(
            "committed release manifest is stale; run "
            "python tools/generate_release_manifest.py"
        )
    committed = read_release_manifest(skill_root)
    if committed != expected:
        raise RuntimeError("committed release manifest differs from tracked payload")
    verify_release_payload(skill_root, committed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or verify the deterministic Skill release manifest."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed manifest is not byte-for-byte current",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.check:
        check_manifest(repo_root)
        print("release manifest is current")
    else:
        manifest = expected_manifest(repo_root)
        destination = write_release_manifest(repo_root / SKILL_NAME, manifest)
        print(f"wrote {destination} ({len(manifest.files)} published files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
