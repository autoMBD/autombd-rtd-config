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
# File:        test_cleanup_tracked_descendants.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Independent cleanup tracked-descendant functional gate.
# =================================================================================

"""Independent functional gate for K0; all operations use real Git/filesystem assets."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT / "tests/fixtures/cleanup-tracked-descendants/cleanup_support.py"
spec = importlib.util.spec_from_file_location("issue112_cleanup_support", SUPPORT)
assert spec and spec.loader
s = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = s
spec.loader.exec_module(s)
G = "cf78144a3786d1dc3f1e92d27157674a7ebea85c"


@pytest.fixture
def cleanup_api():
    return s.load_api()


@pytest.fixture
def lab(tmp_path):
    value = s.Lab(tmp_path)
    try:
        yield value
    finally:
        s.remove_tree(value.directory)


def rejected_without_mutation(api, lab, paths, *, codes=("PATH_BOUNDARY",), **kwargs):
    before = s.inventory(lab.directory)
    try:
        with pytest.raises(api.EnvironmentError) as caught:
            api.cleanup_paths(lab.root, paths, allowed_base=kwargs.pop("allowed_base", lab.base),
                              **kwargs)
        error = caught.value
        assert error.code in codes, error.as_dict()
        body = error.as_dict()
        assert body["version"] == 1 and body["status"] == "REJECTED"
        assert body["code"] == error.code and isinstance(body["message"], str)
    finally:
        assert s.inventory(lab.directory) == before, "Rejection changed source, index or evidence bytes."


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("storage", ["tests/.tmp/current", ".agent-state/agent-loop/current"])
@pytest.mark.parametrize("state", ["committed", "staged", "preignore", "assume-unchanged"])
def test_c01_indexed_descendants_reject_all_source_states(cleanup_api, lab, state, storage, dry_run):
    """CTD-01: source identity follows the index, including dirty worktree bytes."""
    base = lab.root / storage
    source = lab.tracked(state=state, base=base)
    rejected_without_mutation(cleanup_api, lab, [lab.rel(source.parents[1])],
                              allowed_base=base, dry_run=dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("source_position", [0, 1, 2])
def test_c02_source_rejection_is_atomic_over_complete_plan(cleanup_api, lab, dry_run, source_position):
    """CTD-02: a source target anywhere in a batch forbids every mutation."""
    source = lab.tracked()
    targets = [s.write(lab.base / f"scratch-{i}/data.bin").parent for i in range(2)]
    targets.insert(source_position, source.parents[1])
    rejected_without_mutation(cleanup_api, lab, [lab.rel(p) for p in targets], dry_run=dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("tracked_name", [
    "box [ab]/deep [5]/file with spaces.txt",
    "控制 盒/层 β/源文件.bin",
    "box+/--odd/quote' & ! %= #.bin",
    "box(9)/a,b;d/line_end_é.bin",
])
def test_c03_real_names_do_not_evade_index_membership(cleanup_api, lab, tracked_name, dry_run):
    """CTD-03: real supported special/Unicode filenames and literal path boundaries."""
    source = lab.tracked(tracked_name, "staged")
    target = lab.base / Path(tracked_name).parts[0]
    assert source.is_file()
    rejected_without_mutation(cleanup_api, lab, [lab.rel(target)], dry_run=dry_run)


@pytest.mark.parametrize("seed", [7, 23, 61])
def test_c04_varied_tree_sizes_and_prefix_siblings(cleanup_api, lab, seed):
    """CTD-04: index-wide protection does not falsely authorize or block prefix siblings."""
    import random
    rng = random.Random(seed)
    ordinary = []
    for number in range(rng.randrange(2, 6)):
        stem = f"pool-{rng.randrange(1000, 9999)}"
        clean = s.write(lab.base / stem / f"discard-{number}.tmp").parent
        lab.tracked(f"{stem}-archive/layer-{number}/owned.bin", "staged")
        ordinary.append(lab.rel(clean))
    before = s.inventory(lab.directory)
    assert cleanup_api.cleanup_paths(lab.root, ordinary, allowed_base=lab.base) == {
        "version": 1, "status": "PLANNED", "paths": ordinary}
    assert s.inventory(lab.directory) == before
    expected_sources = {name: item for name, item in before.items() if "-archive/" in name}
    result = cleanup_api.cleanup_paths(lab.root, ordinary, allowed_base=lab.base, dry_run=False)
    assert result == {"version": 1, "status": "CLEANED", "paths": ordinary}
    assert all(not (lab.root / name).exists() for name in ordinary)
    after = s.inventory(lab.directory)
    assert {name: item for name, item in after.items() if "-archive/" in name} == expected_sources
    assert {name: item for name, item in after.items() if "/.git/" in name} == {
        name: item for name, item in before.items() if "/.git/" in name}


@pytest.mark.parametrize("storage", ["tests/.tmp/current", ".agent-state/agent-loop/current"])
def test_c05_default_plan_and_explicit_legitimate_cleanup(cleanup_api, lab, storage):
    """CTD-05: the exact signature/default/result and legitimate file/directory cleanup."""
    fn = cleanup_api.cleanup_paths
    signature = inspect.signature(fn)
    assert list(signature.parameters) == ["root", "paths", "allowed_base", "protected_paths", "dry_run"]
    assert signature.parameters["allowed_base"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["protected_paths"].default == ()
    assert signature.parameters["dry_run"].default is True
    base = lab.root / storage
    file = s.write(base / "remove-file.bin")
    directory = s.write(base / "remove-directory/subtree/file.bin").parents[1]
    keep = s.write(base / "bound/approval.json", b"original evidence\n")
    names = [lab.rel(file), lab.rel(directory)]
    before = s.inventory(lab.directory)
    assert fn(lab.root, names, allowed_base=base) == {
        "version": 1, "status": "PLANNED", "paths": names}
    assert s.inventory(lab.directory) == before
    assert fn(lab.root, names, allowed_base=base, dry_run=False) == {
        "version": 1, "status": "CLEANED", "paths": names}
    after = s.inventory(lab.directory)
    removed = [p.relative_to(lab.directory).as_posix() for p in (file, directory)]
    assert after == {name: item for name, item in before.items()
                     if not any(name == p or name.startswith(p + "/") for p in removed)}
    assert keep.read_bytes() == b"original evidence\n"


@pytest.mark.requires_symlink_capability
@pytest.mark.parametrize("kind", ["file", "directory", "junction"])
@pytest.mark.parametrize("placement", ["leaf", "descendant"])
def test_c06_links_only_remove_the_link(cleanup_api, lab, kind, placement):
    """CTD-06: symlink/junction targets can be source or explicitly protected evidence."""
    outside = s.write(lab.directory / "destination/keep.bin", b"destination\x00source\n")
    target = outside if kind == "file" else outside.parent
    link = lab.link("link" if placement == "leaf" else "box/nested/link", kind, target)
    if placement == "descendant":
        s.write(lab.base / "box/plain.tmp")
    name = lab.rel(link if placement == "leaf" else lab.base / "box")
    before = s.inventory(lab.directory)
    assert cleanup_api.cleanup_paths(lab.root, [name], allowed_base=lab.base)["status"] == "PLANNED"
    assert s.inventory(lab.directory) == before
    assert cleanup_api.cleanup_paths(lab.root, [name], allowed_base=lab.base,
                                     dry_run=False)["status"] == "CLEANED"
    assert not s.is_link(link)
    assert outside.read_bytes() == b"destination\x00source\n"
    removed = (lab.root / name).relative_to(lab.directory).as_posix()
    assert s.inventory(lab.directory) == {
        path: item for path, item in before.items()
        if path != removed and not path.startswith(removed + "/")}


@pytest.mark.requires_symlink_capability
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("tracked", [False, True])
def test_c07_link_cleanup_keeps_source_and_explicit_protection(cleanup_api, lab, tracked, dry_run):
    """CTD-07: link identity can be tracked/protected; destinations confer no deletion authority."""
    link = lab.link("owned/link", "file", lab.root / "source.bin")
    if tracked:
        s.git(lab.root, "add", "-f", "--", lab.rel(link))
        kwargs = {}
    else:
        kwargs = {"protected_paths": [lab.rel(link)]}
    early = s.write(lab.base / "ordinary.bin")
    rejected_without_mutation(cleanup_api, lab, [lab.rel(early), lab.rel(link.parent)],
                              dry_run=dry_run, **kwargs)


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("boundary", [
    "source-root", "git-store", "base-itself", "outside-base", "escape",
    "nested-repo-dir", "nested-repo-file", "overlap", "protected-target",
    "protected-descendant", "protected-ancestor", "disallowed-base",
])
def test_c08_existing_boundaries_reject_whole_plan(cleanup_api, lab, boundary, dry_run):
    """CTD-08: existing lexical/source/nested-repo/evidence boundaries remain atomic."""
    early = s.write(lab.base / "ordinary/file.bin").parent
    victim = s.write(lab.base / "victim/child/keep.bin").parents[1]
    base, protected = lab.base, ()
    targets = [lab.rel(early), lab.rel(victim)]
    if boundary == "source-root":
        targets[1] = "."
    elif boundary == "git-store":
        s.write(victim / ".git/objects/data")
    elif boundary == "base-itself":
        targets = [lab.rel(lab.base)]
    elif boundary == "outside-base":
        targets[1] = lab.rel(s.write(lab.root / "tests/.tmp/another/data").parent)
    elif boundary == "escape":
        targets[1] = "tests/.tmp/current/../../../source.bin"
    elif boundary == "nested-repo-dir":
        s.git(victim, "init", "-b", "nested")
    elif boundary == "nested-repo-file":
        s.write(victim / ".git", b"gitdir: unused\n")
    elif boundary == "overlap":
        targets.append(lab.rel(victim / "child"))
    elif boundary == "protected-target":
        protected = [lab.rel(victim)]
    elif boundary == "protected-descendant":
        protected = [lab.rel(victim / "child/keep.bin")]
    elif boundary == "protected-ancestor":
        protected = [lab.rel(lab.base)]
    elif boundary == "disallowed-base":
        base = lab.root
    rejected_without_mutation(cleanup_api, lab, targets, allowed_base=base,
                              protected_paths=protected, dry_run=dry_run)


@pytest.mark.requires_symlink_capability
@pytest.mark.parametrize("kind", ["directory", "junction"])
@pytest.mark.parametrize("dry_run", [True, False])
def test_c09_linked_ancestor_rejects_before_any_delete(cleanup_api, lab, kind, dry_run):
    """CTD-09: an ancestor link never authorizes traversal."""
    destination = s.write(lab.directory / "destination/keep.bin").parent
    link = lab.link("linked", kind, destination)
    early = s.write(lab.base / "ordinary.bin")
    rejected_without_mutation(cleanup_api, lab, [lab.rel(early), lab.rel(link / "keep.bin")],
                              dry_run=dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
def test_c10_real_index_failure_is_not_an_empty_inventory(cleanup_api, lab, dry_run):
    """CTD-10: a real corrupt index cannot become permission to mutate the plan."""
    targets = [s.write(lab.base / name / "keep.bin").parent for name in ("first", "second")]
    index = lab.root / ".git/index"
    index.write_bytes(b"deliberately invalid real Git index\x00")
    failure = s.git(lab.root, "ls-files", "--cached", "-z", check=False)
    assert failure.returncode != 0, "Fixture must make the real index query fail."
    rejected_without_mutation(cleanup_api, lab, [lab.rel(p) for p in targets],
                              codes=("PATH_BOUNDARY", "STALE_IDENTITY", "CAPABILITY_UNAVAILABLE"),
                              dry_run=dry_run)


@pytest.mark.parametrize("dry_run", [True, False])
def test_c11_tracked_leaf_is_protected_even_with_ignored_parent(cleanup_api, lab, dry_run):
    """CTD-11: source can itself be the named cleanup target."""
    source = lab.tracked("leaf.bin", "staged")
    early = s.write(lab.base / "ordinary.bin")
    rejected_without_mutation(cleanup_api, lab, [lab.rel(early), lab.rel(source)], dry_run=dry_run)


@pytest.mark.parametrize("invalid", [None, 0, 1, "false", []])
def test_c12_malformed_dry_run_preserves_existing_error(cleanup_api, lab, invalid):
    """CTD-12: exact boolean validation remains first and side-effect-free."""
    target = s.write(lab.base / "ordinary.bin")
    rejected_without_mutation(cleanup_api, lab, [lab.rel(target)],
                              codes=("INVALID_INPUT",), dry_run=invalid)


@pytest.mark.requires_symlink_capability
@pytest.mark.parametrize("kind", ["file", "directory", "junction"])
def test_c13_legal_link_to_protected_tracked_destination(cleanup_api, lab, kind):
    """CTD-13: deleting an untracked link never grants authority over its destination."""
    source = s.write(lab.root / "public-source/keep.bin", b"protected tracked destination\x00")
    s.git(lab.root, "add", "--", lab.rel(source))
    lab.commit("protected destination")
    destination = source if kind == "file" else source.parent
    link = lab.link("legal-link", kind, destination)
    before = s.inventory(lab.directory)
    kwargs = {"allowed_base": lab.base, "protected_paths": [lab.rel(destination)]}
    assert cleanup_api.cleanup_paths(lab.root, [lab.rel(link)], **kwargs)["status"] == "PLANNED"
    assert s.inventory(lab.directory) == before
    assert cleanup_api.cleanup_paths(lab.root, [lab.rel(link)], dry_run=False, **kwargs)["status"] == "CLEANED"
    removed = link.relative_to(lab.directory).as_posix()
    assert s.inventory(lab.directory) == {name: item for name, item in before.items() if name != removed}
