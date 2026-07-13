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
# File:        validation.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: S32DS / S32 ConfigTools headless validation command and runner.
# =================================================================================

"""S32DS / S32 ConfigTools headless validation command + runner.

This encodes the *verified* S32DS 3.6.x ConfigTools **standalone** headless flow
(domain-truth Flow B), confirmed by live runs on S32DS 3.6.7 against the
``Uart_Example_S32K344`` fixture (known-good -> exit 0 with code generated;
a deliberately invalid OsIf edit -> the SEVERE ``[TOOL]`` resource error below):

- launch ``s32dsc.exe`` with ``--launcher.ini <eclipse>/s32ds.ini`` (the console
  launcher shares the GUI launcher ini; do not use ``s32ds.bat``);
- drive the ConfigTools framework app ``com.nxp.swtools.framework.application``
  with ``-nosplash -consoleLog`` and a ``-HeadlessTool`` (``Peripherals``).
  WITHOUT ``-HeadlessTool`` the app starts a workbench and never terminates;
- point ``-sdkPath`` at the S32DS PlatformSDK that ships ``sdk_manifest.xml``
  (``<root>/S32DS/software/PlatformSDK_S32K3``), not a standalone RTD package;
- load + generate WITHOUT workspace registration using
  ``-Load <mex> -sdkPath <sdk> -ExportSrc <tmp> -ShowProblems SEVERE``.
  ``-ExportSrc`` writes generated code to a throwaway folder, so -- unlike the
  superseded ``-ProjectLink/-UpdateCode`` project flow -- it needs no registered
  workspace project and never hits ``Cannot get container for IPath``. That old
  flow required a CDT ``-import`` registration step which routinely exceeded the
  timeout and produced a spurious exit 2.

Pass condition: ConfigTools exits ``0``, generates at least one source file, AND
reports no SEVERE tool or resource-constraint problem.  Exit ``0`` alone is NOT
sufficient -- ConfigTools returns ``0`` even when it logs a SEVERE configuration
error (verified: an invalid OsIf edit returned exit 0 while logging
``[TOOL] The resource "BaseNXP" ... has the following error: The number of OsIf
Counters must be exactly one ...``; an HSE_CLK>120 MHz configuration returned
exit 0 while emitting ``From Problems view: Tool problem issue: ...``).

The detector flags two classes of real validity errors (see LL-014):

(a) ``[TOOL] ... has the following error`` -- resource-configuration errors
    emitted by the RTD tool engine (English, even on a localized install).
(b) ``From Problems view: Tool problem issue: ...`` -- Clocks/Peripherals/Pins
    resource-constraint violations that ConfigTools exits 0 on and still
    generates code for; these appear on stdout as ``!MESSAGE From Problems
    view: ...`` and on stderr as `` SEVERE: From Problems view: ...``; both
    forms are matched by the substring pair.

Benign framework noise that is deliberately excluded: ``Dependency ... not
found`` (platform driver wiring), ``Cannot get container for IPath`` (CDT
project lookup), SerDes ``No script file``, ``Null toolchain project``,
SLF4J/NLS messages.  None of these contain the ``From Problems view`` +
``Tool problem issue`` pair, so the new sentinel does not produce false
positives on known-good runs.

Commands are built as data so they are unit-testable without launching a vendor
tool. Execution is gated by the caller and the ``RTD_CONFIG_RUN_S32DS_VALIDATION``
environment flag.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from rtd_config.backends.s32_mex.locate import find_single_mex


# S32 ConfigTools standalone application id (registered in S32DS 3.6.x). The
# older ".HeadlessApplication" suffix is NOT registered, and ConfigTools only
# runs headless when a -HeadlessTool is supplied as well.
CONFIGTOOLS_APPLICATION = "com.nxp.swtools.framework.application"

# ConfigTools headless tool that drives RTD peripheral (.mex) configuration.
DEFAULT_HEADLESS_TOOL = "Peripherals"

# Sentinel for class (a): ConfigTools logs real module-configuration errors as
# SEVERE "[TOOL] The resource ... has the following error" (emitted in English
# even on a localized install).
_SEVERE_TOOL_MARKER = "has the following error"

# Sentinels for class (b): Clocks/Peripherals/Pins resource-constraint violations
# are emitted ONLY as "From Problems view: Tool problem issue: ..." (stdout form:
# "!MESSAGE From Problems view: ..."; stderr/tail form: " SEVERE: From Problems
# view: ...").  ConfigTools exits 0 and still generates code for these, so the
# class-(a) sentinel misses them entirely (LL-014).  The PAIR of substrings is
# the discriminating, false-positive-safe sentinel: known-good runs produce zero
# lines that contain both markers, while the benign framework noise ("Dependency
# ... not found", "Cannot get container", SerDes "No script file", "Null toolchain
# project", SLF4J/NLS) contains neither.
_PROBLEMS_VIEW_MARKER = "From Problems view"
_TOOL_PROBLEM_ISSUE_MARKER = "Tool problem issue"


# Default parent directories to scan when neither --s32ds-root nor
# RTD_CONFIG_S32DS_ROOT is set and s32dsc.exe is not on PATH.  The list is
# tried in order; within each parent, valid children are sorted by parsed
# version descending so the newest install wins.
_DEFAULT_S32DS_PARENTS: list[Path] = [
    Path(r"C:\NXP"),
    Path(r"C:\nxp"),
]


def _executable(s32ds_root: Path) -> Path:
    """Return the s32dsc.exe launcher path under an S32DS installation."""
    return s32ds_root / "eclipse" / "s32dsc.exe"


def _launcher_ini(s32ds_root: Path) -> Path | None:
    """Return the Eclipse launcher ``.ini``, or None if the install ships none.

    The console launcher (``s32dsc.exe``) has no ``s32dsc.ini`` of its own; it
    shares the GUI launcher configuration in ``s32ds.ini``. Passing a
    non-existent ``--launcher.ini`` makes the launcher abort.
    """
    eclipse = s32ds_root / "eclipse"
    shared = eclipse / "s32ds.ini"
    if shared.exists():
        return shared
    console = eclipse / "s32dsc.ini"
    return console if console.exists() else None


def default_sdk_path(s32ds_root: Path) -> Path:
    """Return the bundled S32DS PlatformSDK root that ships ``sdk_manifest.xml``."""
    return s32ds_root / "S32DS" / "software" / "PlatformSDK_S32K3"


def is_valid_s32ds_root(root: Path) -> bool:
    """Return True iff *root* looks like a complete S32DS installation.

    Both the headless launcher (``eclipse/s32dsc.exe``) and the bundled
    PlatformSDK directory (``S32DS/software/PlatformSDK_S32K3``) must be
    present.  The SDK directory is required because ``run_validation`` passes
    it to ``-sdkPath``; an install that lacks it cannot validate .mex files.
    """
    return (
        _executable(root).exists()
        and default_sdk_path(root).is_dir()
    )


def _parse_s32ds_version(name: str) -> tuple[int, ...]:
    """Parse ``S32DS.X.Y.Z`` into a version tuple for comparison.

    Returns an empty tuple when the name does not follow the expected pattern
    so that unparseable names sort below any parseable one.
    """
    # Expected format: S32DS.<major>.<minor>.<patch>
    prefix = "S32DS."
    if not name.upper().startswith(prefix.upper()):
        return ()
    tail = name[len(prefix):]
    parts = tail.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return ()


def find_s32ds_root(
    explicit: str | None = None,
    *,
    env: dict[str, str] | None = None,
    search_parents: list[Path] | None = None,
    which: object = shutil.which,
) -> Path | None:
    """Locate the S32DS installation root using a priority-ordered search.

    Resolution order (first hit wins):

    1. *explicit* — path from ``--s32ds-root``; returned as-is as a ``Path``
       even when it does not satisfy ``is_valid_s32ds_root``.  The user stated
       where S32DS is; a clearer downstream error is better than silently
       ignoring the request.
    2. ``env["RTD_CONFIG_S32DS_ROOT"]`` (defaults to ``os.environ``) — same
       trust-and-return rule as explicit.
    3. ``which("s32dsc.exe")`` — if the exe is on PATH, derive the root as
       ``Path(exe).parent.parent`` and return it **only** when
       ``is_valid_s32ds_root`` passes (a stray exe without a matching SDK is
       not a usable root).
    4. Parent-directory glob — for each directory in *search_parents*
       (defaults to ``_DEFAULT_S32DS_PARENTS``, i.e. ``C:\\NXP`` and
       ``C:\\nxp``): collect child directories whose names start with
       ``S32DS`` (case-insensitive), keep only valid roots, sort descending
       by ``(parsed_version_tuple, directory_name)`` so a higher parseable
       version always wins; among roots whose names do not parse to a version
       (empty tuple tie), the directory name provides a deterministic
       descending lexicographic tiebreak.
    5. ``None`` — no usable root found; the caller emits a diagnostic.

    This function never raises.
    """
    # 1. Explicit path from --s32ds-root
    if explicit is not None:
        return Path(explicit)

    # 2. Environment variable
    if env is None:
        env = os.environ
    env_val = env.get("RTD_CONFIG_S32DS_ROOT")
    if env_val:
        return Path(env_val)

    # 3. which("s32dsc.exe") — exe on PATH
    try:
        exe_str = which("s32dsc.exe")  # type: ignore[operator]
    except Exception:
        exe_str = None
    if exe_str:
        derived = Path(exe_str).parent.parent
        if is_valid_s32ds_root(derived):
            return derived

    # 4. Parent-directory glob
    parents = _DEFAULT_S32DS_PARENTS if search_parents is None else search_parents
    for parent in parents:
        if not parent.is_dir():
            continue
        candidates: list[tuple[tuple[int, ...], Path]] = []
        for child in parent.iterdir():
            if not child.is_dir():
                continue
            if not child.name.upper().startswith("S32DS"):
                continue
            if not is_valid_s32ds_root(child):
                continue
            candidates.append((_parse_s32ds_version(child.name), child))
        if candidates:
            # Sort descending by (version_tuple, name): a higher parseable
            # version always wins; equal/empty-tuple roots fall back to
            # descending directory-name order for a deterministic tiebreak.
            candidates.sort(key=lambda t: (t[0], t[1].name), reverse=True)
            return candidates[0][1]

    # 5. Not found
    return None


def probe_which_root(which_fn: object = shutil.which) -> Path | None:
    """Return the S32DS root derived from ``which("s32dsc.exe")``, or None.

    Unlike the ``which`` branch inside :func:`find_s32ds_root` — which silently
    drops an invalid root — this helper returns the derived path even when
    ``is_valid_s32ds_root`` fails, so callers can surface a breadcrumb such as
    "found s32dsc.exe at <path> but the installation is incomplete" rather than
    the generic "not configured" message.
    """
    try:
        exe_str = which_fn("s32dsc.exe")  # type: ignore[operator]
    except Exception:
        exe_str = None
    if exe_str:
        return Path(exe_str).parent.parent
    return None


def _launcher_prefix(s32ds_root: Path) -> list[str]:
    command = [str(_executable(s32ds_root))]
    launcher_ini = _launcher_ini(s32ds_root)
    if launcher_ini is not None:
        command += ["--launcher.ini", str(launcher_ini)]
    return command


def build_validation_command(
    s32ds_root: Path,
    mex_file: Path,
    *,
    workspace: Path,
    export_dir: Path,
    sdk_path: Path | None = None,
    headless_tool: str = DEFAULT_HEADLESS_TOOL,
) -> list[str]:
    """Build the standalone (Flow B) headless ConfigTools validate command.

    Loads ``mex_file`` and exports generated code to ``export_dir`` with no
    workspace registration. ``workspace`` is only the Eclipse ``-data`` directory
    (a throwaway); the project is never registered into it, so there is no
    ``Cannot get container for IPath`` and no slow CDT ``-import`` step.
    """
    sdk_path = sdk_path or default_sdk_path(s32ds_root)
    return _launcher_prefix(s32ds_root) + [
        "-consoleLog",
        "-nosplash",
        "-application", CONFIGTOOLS_APPLICATION,
        "-data", str(workspace),
        "-HeadlessTool", headless_tool,
        "-Load", str(mex_file),
        "-sdkPath", str(sdk_path),
        "-ExportSrc", str(export_dir),
        "-ShowProblems", "SEVERE",
    ]


def find_severe_tool_problems(text: str) -> list[str]:
    """Return SEVERE ConfigTools resource-configuration and resource-constraint problem lines.

    Flags a line if it matches EITHER of two sentinel patterns:

    (a) ``[TOOL]`` AND ``has the following error`` -- the RTD tool-engine
        resource-configuration errors (``[TOOL] The resource "X" ...
        has the following error: ...``), emitted in English on any locale.

    (b) ``From Problems view`` AND ``Tool problem issue`` -- the
        Clocks/Peripherals/Pins resource-constraint violations that
        ConfigTools exits 0 on and still generates code for (LL-014 bypass).
        These appear on stdout as ``!MESSAGE From Problems view: Tool problem
        issue: ...`` and on stderr as `` SEVERE: From Problems view: Tool
        problem issue: ...``; the substring pair matches both forms and both
        English and localized (e.g. Chinese) message bodies.

    Still EXCLUDED (benign framework noise that lacks both sentinel pairs):
    ``Dependency ... not found`` (platform driver wiring), ``Cannot get
    container for IPath`` (CDT project lookup), SerDes ``No script file``,
    ``Null toolchain project``, SLF4J/NLS messages.  ``From Problems view:
    ... target: Toolchain/IDE project`` lines are also excluded because they
    do not carry ``Tool problem issue``.

    Duplicate stripped lines are deduplicated; order is preserved.
    """
    problems: list[str] = []
    for line in text.splitlines():
        is_tool_error = "[TOOL]" in line and _SEVERE_TOOL_MARKER in line
        is_problems_view = (
            _PROBLEMS_VIEW_MARKER in line and _TOOL_PROBLEM_ISSUE_MARKER in line
        )
        if is_tool_error or is_problems_view:
            stripped = line.strip()
            if stripped not in problems:
                problems.append(stripped)
    return problems


@dataclass
class ValidationOutcome:
    exit_code: int
    command: list[str]
    log_path: str
    stdout: str = ""
    stderr: str = ""
    severe_problems: list[str] = field(default_factory=list)
    generated_files: int = 0

    @property
    def passed(self) -> bool:
        """Pass = exit 0 AND code generated AND no SEVERE resource problem.

        Exit 0 alone is insufficient: ConfigTools returns 0 even when it logs a
        SEVERE resource problem — either ``[TOOL] ... has the following error``
        OR a ``From Problems view: Tool problem issue: ...`` Clocks/Peripherals/
        Pins constraint violation (see ``find_severe_tool_problems``) — so the
        severe list must be empty. A pass must also have produced at least one
        generated source file (the ``-ExportSrc`` evidence that codegen ran).
        """
        return (
            self.exit_code == 0
            and self.generated_files > 0
            and not self.severe_problems
        )


def validation_log_path(project: Path) -> Path:
    """Return the path where validation logs are kept (under build/)."""
    return project / "build" / "configtools_validation.log"


def _run(command: list[str], timeout_s: int) -> tuple[int, str, str]:
    """Run a headless launcher command, never raising for expected failures."""
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_s,
            creationflags=creationflags,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", (
            f"S32DS headless step exceeded the {timeout_s}s timeout; "
            "treat as not validated (not a pass)."
        )
    except (FileNotFoundError, OSError) as exc:
        return 127, "", f"Could not launch the S32DS executable: {exc}"


def run_validation(
    project: Path,
    s32ds_root: Path,
    *,
    workspace: Path | None = None,
    sdk_path: Path | None = None,
    headless_tool: str = DEFAULT_HEADLESS_TOOL,
    mex_file: Path | None = None,
    timeout_s: int = 180,
) -> ValidationOutcome:
    """Headlessly validate a project's .mex with the standalone Flow B.

    A throwaway copy of the project is validated so the caller's files are never
    touched, and generated code is exported to a temporary folder. No workspace
    registration is performed; the Eclipse ``-data`` workspace and the
    ``-ExportSrc`` target are temporary directories removed afterwards. The pass
    decision is the returned outcome's ``passed`` property (exit 0 AND code
    generated AND no SEVERE ``[TOOL]`` resource problem).
    """
    project = Path(project)
    s32ds_root = Path(s32ds_root)
    sdk_path = sdk_path or default_sdk_path(s32ds_root)

    # Log under the caller's real project even though validation runs on a copy.
    log_path = validation_log_path(project)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stage = Path(tempfile.mkdtemp(prefix="rtd-validate-"))
    try:
        target = stage / project.name
        shutil.copytree(project, target)
        located_target = find_single_mex(target) if mex_file is None else None
        target_mex = located_target.mex.path if located_target is not None else target / Path(mex_file).name
        if located_target is not None:
            located_target.close()
        export_dir = stage / "_export"
        export_dir.mkdir()
        data_ws = Path(workspace) if workspace is not None else stage / "_ws"
        data_ws.mkdir(parents=True, exist_ok=True)

        val_cmd = build_validation_command(
            s32ds_root, target_mex,
            workspace=data_ws, export_dir=export_dir,
            sdk_path=sdk_path, headless_tool=headless_tool,
        )
        exit_code, stdout, stderr = _run(val_cmd, timeout_s)
        severe = find_severe_tool_problems(stdout + "\n" + stderr)
        generated_files = sum(1 for p in export_dir.rglob("*") if p.is_file())

        log_path.write_text(
            f"$ {' '.join(val_cmd)}\n[validate exit {exit_code}]\n"
            f"[generated_files {generated_files}]\n"
            f"[stdout]\n{stdout}\n[stderr]\n{stderr}\n"
            "[severe_tool_problems]\n" + "\n".join(severe) + "\n",
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    return ValidationOutcome(
        exit_code=exit_code,
        command=val_cmd,
        log_path=str(log_path),
        stdout=stdout,
        stderr=stderr,
        severe_problems=severe,
        generated_files=generated_files,
    )
