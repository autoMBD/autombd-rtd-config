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

Pass condition: ConfigTools exits ``0`` AND reports no qualifying SEVERE tool
or resource-constraint problem.  Generated-file count is retained as audit
evidence but is not an additional validity criterion. Exit ``0`` alone is NOT
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
from dataclasses import dataclass, field
from pathlib import Path

from rtd_config.backends.s32_mex.metadata import revalidate_validator_input_inventory
from rtd_config.backends.s32_mex.process_tree import ProcessTreeRunner
from rtd_config.backends.s32_mex.target import snapshot_project_relative
from rtd_config.backends.s32_mex.validation_workspace import (
    ControlledValidationWorkspace,
    snapshot_project_tree,
)
from rtd_config.errors import CliFailure
from rtd_config.project import Project


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
    process_code: str = "process_exit"
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    output_faults: list[str] = field(default_factory=list)
    cleanup_warnings: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Pass = exit 0 AND no qualifying SEVERE resource problem.

        Exit 0 alone is insufficient: ConfigTools returns 0 even when it logs a
        SEVERE resource problem — either ``[TOOL] ... has the following error``
        OR a ``From Problems view: Tool problem issue: ...`` Clocks/Peripherals/
        Pins constraint violation (see ``find_severe_tool_problems``) — so the
        severe list must be empty. Generated-file count remains audit evidence,
        but it is not an additional vendor validity criterion.
        """
        return (
            self.exit_code == 0
            and self.process_code == "process_exit"
            and not self.severe_problems
            and not self.stdout_truncated
            and not self.stderr_truncated
            and not self.output_faults
            and not self.cleanup_warnings
        )

    @property
    def status(self) -> str:
        return "passed" if self.passed else "blocked"


def validation_log_path(_project: Path) -> Path:
    """Return the sanitized logical name of the controlled validation log."""
    return Path("validation.log")


def _sanitized_command(command: list[str]) -> list[str]:
    result = [Path(command[0]).name]
    path_value = False
    for item in command[1:]:
        if path_value:
            result.append(Path(item).name)
            path_value = False
            continue
        result.append(item)
        path_value = item in {"--launcher.ini", "-data", "-Load", "-sdkPath", "-ExportSrc"}
    return result


def _write_controlled_log(path: Path, text: str) -> None:
    flags = (
        os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = -1
    try:
        descriptor = os.open(path, flags, 0o600)
        data = text.encode("utf-8", errors="replace")
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short validation log write")
            view = view[written:]
        os.fsync(descriptor)
    except OSError as exc:
        raise CliFailure(
            "validation_log_failed",
            "The controlled validation log could not be written.",
            module="backend", details={"entry": path.name},
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _redact_validation_text(text: str, replacements: list[tuple[Path, str]]) -> str:
    result = text
    for path, label in replacements:
        raw = str(path)
        result = result.replace(raw, label)
        result = result.replace(raw.replace("\\", "/"), label)
    return result


def run_validation(
    project: Path | Project,
    s32ds_root: Path,
    *,
    workspace: Path | None = None,
    sdk_path: Path | None = None,
    headless_tool: str = DEFAULT_HEADLESS_TOOL,
    mex_file: Path | None = None,
    timeout_s: int = 180,
    runner: ProcessTreeRunner | None = None,
    temp_root: Path | None = None,
    log_root: Path | None = None,
) -> ValidationOutcome:
    """Headlessly validate a project's .mex with the standalone Flow B.

    Only the selected .mex is copied into a controlled sibling workspace; the
    vendor never receives an original-project path. The complete source tree is
    snapshotted before and after execution, and the controlled data, export, log,
    and temp roots are removed or reported as audit residuals. The pass decision
    is exit 0 with no qualifying SEVERE resource problem and no cleanup warning.
    """
    project_argument = project
    s32ds_root = Path(s32ds_root)
    sdk_path = sdk_path or default_sdk_path(s32ds_root)
    owned_project: Project | None = None
    verified_project: Project | None = None
    inventory = None
    controlled: ControlledValidationWorkspace | None = None
    primary: BaseException | None = None
    outcome: ValidationOutcome | None = None
    cleanup_warnings: list[dict] = []
    try:
        if isinstance(project_argument, Project):
            verified_project = project_argument
        else:
            owned_project = Project.verified(Path(project_argument))
            verified_project = owned_project
        project_root = verified_project.root
        selected_snapshot = None
        selected_relative = None
        if mex_file is not None:
            source_mex = Path(mex_file).absolute()
            try:
                selected_relative = source_mex.relative_to(project_root).as_posix()
            except ValueError as exc:
                raise CliFailure(
                    "validation_source_unsafe",
                    "The validator input must remain inside the verified project.",
                    module="backend", details={"entry": source_mex.name},
                ) from exc
            selected_snapshot = snapshot_project_relative(
                verified_project.verified_target,
                selected_relative,
                max_bytes=64 * 1024 * 1024,
            )
            if selected_snapshot is None:
                raise CliFailure(
                    "validation_source_changed",
                    "The selected validator candidate is no longer available.",
                    module="backend", details={"entry": source_mex.name},
                )
        inventory = verified_project.capture_validator_inputs(
            selected_mex=selected_snapshot,
            selected_source_relative=selected_relative,
        )
        controlled_root = (
            Path(workspace).absolute()
            if workspace is not None
            else project_root.parent / ".rtd-config-validation"
        )
        try:
            controlled_root.relative_to(project_root)
        except ValueError:
            pass
        else:
            raise CliFailure(
                "validation_workspace_unsafe",
                "The controlled validation workspace must be outside the project.",
                module="backend", details={"entry": controlled_root.name},
            )
        controlled = ControlledValidationWorkspace(
            controlled_root, inventory, temp_root=temp_root, log_root=log_root
        )
        controlled.open()
        assert controlled.mex_file is not None
        assert controlled.data_dir is not None
        assert controlled.export_dir is not None
        assert controlled.root is not None
        assert controlled.log_file is not None
        val_cmd = build_validation_command(
            s32ds_root, controlled.mex_file,
            workspace=controlled.data_dir, export_dir=controlled.export_dir,
            sdk_path=sdk_path, headless_tool=headless_tool,
        )
        controlled.verify_identity()
        process = (runner or ProcessTreeRunner()).run(
            val_cmd,
            cwd=controlled.root,
            env=controlled.environment(),
            timeout_s=timeout_s,
        )
        replacements = [
            (controlled.root, "<validation-workspace>"),
            (project_root, "<project>"),
            (s32ds_root, "<s32ds>"),
            (sdk_path, "<sdk>"),
        ]
        stdout = _redact_validation_text(process.stdout, replacements)
        stderr = _redact_validation_text(process.stderr, replacements)
        severe = find_severe_tool_problems(stdout + "\n" + stderr)
        for item in getattr(process, "severe_problems", ()):
            if item not in severe:
                severe.append(item)
        generated_files = len(snapshot_project_tree(controlled.export_dir))
        sanitized = _sanitized_command(val_cmd)
        _write_controlled_log(
            controlled.log_file,
            f"$ {' '.join(sanitized)}\n[validate exit {process.exit_code}]\n"
            f"[generated_files {generated_files}]\n"
            f"[stdout]\n{stdout}\n[stderr]\n{stderr}\n"
            "[severe_tool_problems]\n" + "\n".join(severe) + "\n",
        )
        outcome = ValidationOutcome(
            exit_code=process.exit_code,
            command=sanitized,
            log_path=controlled.public_log_path,
            stdout=stdout,
            stderr=stderr,
            severe_problems=severe,
            generated_files=generated_files,
            process_code=process.code,
            timed_out=process.timed_out,
            stdout_truncated=process.stdout_truncated,
            stderr_truncated=process.stderr_truncated,
            output_faults=list(getattr(process, "output_faults", ())),
        )
    except BaseException as exc:
        primary = exc
    finally:
        if verified_project is not None and inventory is not None:
            try:
                revalidate_validator_input_inventory(
                    verified_project.verified_target, inventory
                )
            except CliFailure as exc:
                primary = _merge_validation_failure(
                    primary, "source_verification", exc
                )
        if controlled is not None:
            try:
                cleanup_warnings = controlled.close()
            except BaseException as exc:
                primary = _merge_validation_failure(
                    primary, "workspace_close_failure", exc
                )
        if owned_project is not None:
            try:
                owned_project.close()
            except BaseException as exc:
                primary = _merge_validation_failure(
                    primary, "project_close_failure", exc
                )
    if primary is not None:
        if cleanup_warnings and isinstance(primary, CliFailure):
            details = dict(primary.details)
            details["cleanup_warnings"] = cleanup_warnings
            primary = CliFailure(
                primary.code, primary.message, status=primary.status,
                module=primary.module, details=details,
                exit_code=primary.exit_code,
            )
        raise primary
    assert outcome is not None
    outcome.cleanup_warnings.extend(cleanup_warnings)
    return outcome


def _merge_validation_failure(
    primary: BaseException | None,
    key: str,
    secondary: BaseException,
) -> BaseException:
    if primary is None:
        return secondary
    if not isinstance(primary, CliFailure):
        return primary
    if isinstance(secondary, CliFailure):
        evidence = {"code": secondary.code, "details": dict(secondary.details)}
    else:
        evidence = {"code": type(secondary).__name__}
    details = dict(primary.details)
    details[key] = evidence
    return CliFailure(
        primary.code, primary.message, status=primary.status,
        module=primary.module, details=details,
        exit_code=primary.exit_code,
    )
