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
reports no SEVERE ``[TOOL] ... has the following error`` resource problem. Exit
``0`` alone is NOT sufficient -- ConfigTools returns ``0`` even when it logs a
SEVERE configuration error (verified: an invalid OsIf edit returned exit 0 while
logging ``[TOOL] The resource "BaseNXP" ... has the following error: The number
of OsIf Counters must be exactly one ...``). Conversely, framework noise logged
at ``严重:``/SEVERE (``Cannot get container``, SerDes ``No script file``, Port
expression errors, SLF4J/NLS) is not a .mex validity problem and is excluded by
the ``has the following error`` marker.

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

# ConfigTools logs real module-configuration errors as SEVERE
# "[TOOL] The resource ... has the following error" (emitted in English even on a
# localized install). Everything else logged at SEVERE/严重 on a headless,
# unregistered run -- "Cannot get container for IPath", SerDes "No script file",
# Port expression errors, Toolchain/IDE driver-not-found, SLF4J/NLS noise -- is
# environment noise, not .mex validity, and is deliberately excluded.
_SEVERE_TOOL_MARKER = "has the following error"


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
    """Return SEVERE ConfigTools resource-configuration problem lines.

    These are the real ``.mex`` validity errors (``[TOOL] The resource "X" ...
    has the following error: ...``). Project-build "Toolchain/IDE project"
    problems are excluded on purpose.
    """
    problems: list[str] = []
    for line in text.splitlines():
        if "[TOOL]" in line and _SEVERE_TOOL_MARKER in line:
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
        """Pass = exit 0 AND code generated AND no SEVERE [TOOL] config error.

        Exit 0 alone is insufficient: ConfigTools returns 0 even when it logs a
        SEVERE ``[TOOL] ... has the following error`` resource problem, so the
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
        target_mex = find_single_mex(target) if mex_file is None else target / Path(mex_file).name
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
