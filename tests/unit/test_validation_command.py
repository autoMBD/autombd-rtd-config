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
# File:        test_validation_command.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Unit tests for the S32DS validation command builder.
# =================================================================================

from pathlib import Path

from rtd_config.backends.s32_mex.validation import (
    ValidationOutcome,
    _DEFAULT_S32DS_PARENTS,
    build_validation_command,
    default_sdk_path,
    find_severe_tool_problems,
    find_s32ds_root,
    is_valid_s32ds_root,
    probe_which_root,
)


def _validate_cmd():
    return build_validation_command(
        s32ds_root=Path("C:/NXP/S32DS.3.6.7"),
        mex_file=Path("C:/tmp/Uart_Example_S32K344/Uart_Example.mex"),
        workspace=Path("C:/tmp/_ws"),
        export_dir=Path("C:/tmp/_export"),
    )


def test_build_validation_command_is_standalone_flow_b():
    """Flow B: -Load + -ExportSrc, headless, no workspace registration.

    The earlier project flow (-ProjectLink + -UpdateCode) required a registered
    workspace project; its CDT -import step routinely timed out and produced a
    spurious exit 2 with "Cannot get container for IPath". Flow B exports
    generated code to a throwaway folder and needs no registration.
    """
    command = _validate_cmd()
    joined = " ".join(command)
    assert "eclipse" in joined.lower()
    assert "-nosplash" in command
    # The framework app only runs headless when -HeadlessTool is supplied.
    assert "-HeadlessTool" in command
    assert any("framework.application" in item for item in command)
    assert "-Load" in command
    assert "-ExportSrc" in command
    assert "-sdkPath" in command
    assert "-ShowProblems" in command
    # Flow B must NOT use the registration-bound project flow.
    assert "-ProjectLink" not in command
    assert "-UpdateCode" not in command
    assert "-import" not in command


def test_default_sdk_path_points_at_bundled_platform_sdk():
    sdk = default_sdk_path(Path("C:/NXP/S32DS.3.6.7"))
    assert sdk.parts[-3:] == ("S32DS", "software", "PlatformSDK_S32K3")


def test_find_severe_tool_problems_filters_out_environment_noise():
    """Only [TOOL] '... has the following error' resource problems gate.

    Everything else ConfigTools logs at SEVERE/严重 on a headless, unregistered
    run -- "Cannot get container", SerDes "No script file", localized framework
    NLS errors -- is environment noise, not .mex validity, and must be excluded.
    """
    text = "\n".join([
        ' SEVERE: [TOOL] The resource "BaseNXP" ... has the following error: The number of OsIf Counters ... [x]',
        ' SEVERE: From Problems view: ... target: Toolchain/IDE project [y]',
        ' SEVERE: [TOOL] No script file found while trying to recompile ... SerDes Config Tool [z]',
        '严重: Cannot get container for IPath C:/tmp/Uart_Example.mex',
    ])
    problems = find_severe_tool_problems(text)
    assert len(problems) == 1
    assert "has the following error" in problems[0]
    assert "BaseNXP" in problems[0]


def test_validation_outcome_pass_gate():
    base = dict(command=[], log_path="x")
    # Pass = exit 0 AND code generated AND no SEVERE [TOOL] config error.
    assert ValidationOutcome(
        exit_code=0, severe_problems=[], generated_files=122, **base
    ).passed is True
    # exit 0 but a SEVERE [TOOL] problem present -> not a pass.
    assert ValidationOutcome(
        exit_code=0, severe_problems=["boom"], generated_files=122, **base
    ).passed is False
    # exit 0, no severe, but no code generated -> not a pass.
    assert ValidationOutcome(
        exit_code=0, severe_problems=[], generated_files=0, **base
    ).passed is False
    # non-zero exit -> not a pass.
    assert ValidationOutcome(
        exit_code=2, severe_problems=[], generated_files=122, **base
    ).passed is False


# ---------------------------------------------------------------------------
# Helpers — fabricate a minimal valid S32DS root tree in tmp_path.
# ---------------------------------------------------------------------------

def _make_valid_root(base: Path, name: str = "S32DS.3.6.7") -> Path:
    """Create marker files that satisfy is_valid_s32ds_root under base/name."""
    root = base / name
    (root / "eclipse").mkdir(parents=True)
    (root / "eclipse" / "s32dsc.exe").write_bytes(b"")
    (root / "S32DS" / "software" / "PlatformSDK_S32K3").mkdir(parents=True)
    return root


def _make_invalid_root(base: Path, name: str = "S32DS.3.6.0-bad") -> Path:
    """Create a root that is missing the SDK dir (is_valid_s32ds_root -> False)."""
    root = base / name
    (root / "eclipse").mkdir(parents=True)
    (root / "eclipse" / "s32dsc.exe").write_bytes(b"")
    # SDK dir intentionally absent
    return root


# ---------------------------------------------------------------------------
# is_valid_s32ds_root
# ---------------------------------------------------------------------------

def test_is_valid_s32ds_root_true_on_complete_tree(tmp_path):
    root = _make_valid_root(tmp_path)
    assert is_valid_s32ds_root(root) is True


def test_is_valid_s32ds_root_false_missing_exe(tmp_path):
    root = tmp_path / "S32DS.3.6.7"
    # Only SDK dir, no exe
    (root / "S32DS" / "software" / "PlatformSDK_S32K3").mkdir(parents=True)
    assert is_valid_s32ds_root(root) is False


def test_is_valid_s32ds_root_false_missing_sdk(tmp_path):
    root = _make_invalid_root(tmp_path)
    assert is_valid_s32ds_root(root) is False


def test_is_valid_s32ds_root_false_nonexistent(tmp_path):
    assert is_valid_s32ds_root(tmp_path / "does_not_exist") is False


# ---------------------------------------------------------------------------
# find_s32ds_root — explicit wins
# ---------------------------------------------------------------------------

def test_find_s32ds_root_explicit_wins_over_env_and_glob(tmp_path):
    """Explicit path is returned as-is even when env and parent-glob have valid roots."""
    valid_explicit = _make_valid_root(tmp_path, "explicit_root")
    valid_env = _make_valid_root(tmp_path, "env_root")
    valid_parent = _make_valid_root(tmp_path / "parents", "S32DS.3.6.7")

    result = find_s32ds_root(
        explicit=str(valid_explicit),
        env={"RTD_CONFIG_S32DS_ROOT": str(valid_env)},
        search_parents=[tmp_path / "parents"],
        which=lambda _: None,
    )
    assert result == valid_explicit


def test_find_s32ds_root_explicit_returned_even_if_invalid(tmp_path):
    """Explicit is trusted unconditionally — invalid path still returned."""
    bogus = tmp_path / "no_such_install"
    result = find_s32ds_root(
        explicit=str(bogus),
        env={},
        search_parents=[],
        which=lambda _: None,
    )
    assert result == bogus


# ---------------------------------------------------------------------------
# find_s32ds_root — env fallback
# ---------------------------------------------------------------------------

def test_find_s32ds_root_env_used_when_no_explicit(tmp_path):
    valid_env = _make_valid_root(tmp_path)
    result = find_s32ds_root(
        explicit=None,
        env={"RTD_CONFIG_S32DS_ROOT": str(valid_env)},
        search_parents=[],
        which=lambda _: None,
    )
    assert result == valid_env


def test_find_s32ds_root_env_returned_even_if_invalid(tmp_path):
    bogus = tmp_path / "not_a_real_s32ds"
    result = find_s32ds_root(
        explicit=None,
        env={"RTD_CONFIG_S32DS_ROOT": str(bogus)},
        search_parents=[],
        which=lambda _: None,
    )
    assert result == bogus


# ---------------------------------------------------------------------------
# find_s32ds_root — which fallback
# ---------------------------------------------------------------------------

def test_find_s32ds_root_which_valid_root_returned(tmp_path):
    """which returns exe path whose parent.parent is a valid root -> returned."""
    root = _make_valid_root(tmp_path)
    exe = root / "eclipse" / "s32dsc.exe"

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _name: str(exe),
    )
    assert result == root


def test_find_s32ds_root_which_invalid_root_falls_through_to_none(tmp_path):
    """which returns exe but the derived root is invalid -> falls through to None."""
    bad_root = _make_invalid_root(tmp_path)
    exe = bad_root / "eclipse" / "s32dsc.exe"

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _name: str(exe),
    )
    assert result is None


def test_find_s32ds_root_which_none_falls_through(tmp_path):
    """which returns None -> falls through to parent-glob or None."""
    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _: None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# find_s32ds_root — parent-glob, version-sort
# ---------------------------------------------------------------------------

def test_find_s32ds_root_glob_picks_highest_version(tmp_path):
    """Among multiple valid roots, the one with the highest parsed version wins."""
    parent = tmp_path / "NXP"
    _make_valid_root(parent, "S32DS.3.5.0")
    _make_valid_root(parent, "S32DS.3.6.7")
    _make_valid_root(parent, "S32DS.3.6.2")

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result is not None
    assert result.name == "S32DS.3.6.7"


def test_find_s32ds_root_glob_ignores_invalid_roots(tmp_path):
    """Invalid roots (missing exe or SDK) are skipped; valid one is returned."""
    parent = tmp_path / "NXP"
    _make_invalid_root(parent, "S32DS.3.6.7")   # invalid (no SDK)
    valid = _make_valid_root(parent, "S32DS.3.5.0")

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result == valid


def test_find_s32ds_root_glob_empty_parent_returns_none(tmp_path):
    """Parent dir exists but has no S32DS* children -> None."""
    parent = tmp_path / "NXP"
    parent.mkdir()

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# find_s32ds_root — nothing valid -> None
# ---------------------------------------------------------------------------

def test_find_s32ds_root_returns_none_when_nothing_configured(tmp_path):
    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _: None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Fix 2 — unparseable-named valid root must not beat a real versioned install
# ---------------------------------------------------------------------------

def test_find_s32ds_root_glob_versioned_beats_unparseable_name(tmp_path):
    """An ARM-named (unparseable) install must never win over a real versioned one.

    Creates two valid roots under one parent:
    - S32DS.3.6.7  -- parseable version (3, 6, 7)
    - S32DS_ARM_v2.2 -- unparseable (no 'S32DS.' prefix with all-int tail)

    The sort key is (version_tuple, name) descending.  S32DS.3.6.7 has key
    ((3,6,7), 'S32DS.3.6.7') while S32DS_ARM_v2.2 has key ((), 'S32DS_ARM_v2.2').
    Any non-empty tuple compares greater than the empty tuple, so the versioned
    install wins regardless of lexicographic directory name order.
    """
    parent = tmp_path / "NXP"
    versioned = _make_valid_root(parent, "S32DS.3.6.7")
    _make_valid_root(parent, "S32DS_ARM_v2.2")  # structurally valid but unparseable name

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result == versioned, (
        f"Expected {versioned!r}, got {result!r}: "
        "versioned install must win over an unparseable-named install"
    )


# ---------------------------------------------------------------------------
# Fix 3 — production default _DEFAULT_S32DS_PARENTS path is exercised
# ---------------------------------------------------------------------------

def test_default_s32ds_parents_exact_contents():
    """_DEFAULT_S32DS_PARENTS must be [C:\\NXP, C:\\nxp] in that order.

    This pins the constant so that any typo or reorder immediately breaks the
    test.  The test does not depend on those directories existing on disk.
    """
    assert _DEFAULT_S32DS_PARENTS == [Path(r"C:\NXP"), Path(r"C:\nxp")], (
        "_DEFAULT_S32DS_PARENTS order or content changed — update the constant "
        "and this test together"
    )


def test_find_s32ds_root_uses_default_parents_when_none_given(tmp_path, monkeypatch):
    """Calling find_s32ds_root with search_parents=None uses _DEFAULT_S32DS_PARENTS.

    Monkeypatching the module-level list to point at a temp parent containing a
    valid root proves the default branch is reached and that _DEFAULT_S32DS_PARENTS
    is the actual list consulted — not a local copy or hard-coded fallback.
    """
    import rtd_config.backends.s32_mex.validation as _val_mod

    # Build a valid root inside the temp directory.
    valid = _make_valid_root(tmp_path, "S32DS.3.6.7")

    # Redirect the module-level default so our temp dir is searched.
    monkeypatch.setattr(_val_mod, "_DEFAULT_S32DS_PARENTS", [tmp_path])

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=None,   # <-- exercises the default branch
        which=lambda _: None,
    )
    assert result == valid, (
        f"Expected {valid!r}, got {result!r}: "
        "default _DEFAULT_S32DS_PARENTS branch was not taken"
    )


# ---------------------------------------------------------------------------
# Fix 4 — probe_which_root returns the derived path regardless of validity
# ---------------------------------------------------------------------------

def test_probe_which_root_returns_derived_path_even_when_invalid(tmp_path):
    """probe_which_root returns the derived root path even when the install is incomplete.

    This is the breadcrumb contract: the caller (cmd_validate) can surface
    'found s32dsc.exe at X but the installation is incomplete' instead of
    the generic 'not configured' message.
    """
    bad_root = _make_invalid_root(tmp_path)  # exe present, SDK absent
    exe = bad_root / "eclipse" / "s32dsc.exe"

    result = probe_which_root(which_fn=lambda _: str(exe))
    assert result == bad_root


def test_probe_which_root_returns_none_when_which_returns_none():
    """probe_which_root returns None when s32dsc.exe is not on PATH."""
    result = probe_which_root(which_fn=lambda _: None)
    assert result is None
