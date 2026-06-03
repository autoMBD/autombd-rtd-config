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

"""S32DS / S32 ConfigTools headless validation command construction.

This follows the validation experience captured in the M1 legacy-skills doc:

- use ``s32dsc.exe`` with the S32DS launcher ``.ini`` (do not use ``s32ds.bat``
  as the primary command, since it can return before the headless action
  completes);
- run with no visible GUI window (``-nosplash``);
- drive the ConfigTools framework application with project import and a
  ``-sdkPath`` so SDK driver components resolve correctly;
- the expected pass condition is ConfigTools process exit code ``0``;
- keep validation logs under the target project's ``build/`` directory.

The command is built as data so it is unit-testable without launching a vendor
tool. Actual execution is gated by the caller and by the
``RTD_CONFIG_RUN_S32DS_VALIDATION`` environment flag.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# S32 ConfigTools standalone application id used for headless .mex validation.
# NOTE: the ".HeadlessApplication" suffix from older notes is NOT registered in
# S32DS 3.6.x; the registry exposes "com.nxp.swtools.framework.application" as
# the ConfigTools entry point, which runs without a GUI under -nosplash.
CONFIGTOOLS_APPLICATION = "com.nxp.swtools.framework.application"

# Documented default S32DS Eclipse workspace on the development computer.
DEFAULT_WORKSPACE = Path(r"D:\WorkSpace\DSpace\3.6")


def _executable(s32ds_root: Path) -> Path:
    """Return the s32dsc.exe launcher path under an S32DS installation."""
    return s32ds_root / "eclipse" / "s32dsc.exe"


def _launcher_ini(s32ds_root: Path) -> Path | None:
    """Return the Eclipse launcher ``.ini``, or None if the install ships none.

    The console launcher (``s32dsc.exe``) has no ``s32dsc.ini`` of its own; it
    shares the GUI launcher configuration in ``s32ds.ini`` (which carries the
    ``-vm`` / ``-vmargs`` the headless JVM needs). Prefer ``s32ds.ini`` and fall
    back to a co-named ``s32dsc.ini`` only when an install actually ships one;
    passing a non-existent ``--launcher.ini`` makes the launcher abort.
    """
    eclipse = s32ds_root / "eclipse"
    shared = eclipse / "s32ds.ini"
    if shared.exists():
        return shared
    console = eclipse / "s32dsc.ini"
    return console if console.exists() else None


def build_validation_command(
    s32ds_root: Path,
    project: Path,
    *,
    workspace: Path | None = None,
    sdk_path: Path | None = None,
) -> list[str]:
    """Build the headless S32 ConfigTools validation command for a project.

    The returned argv list runs ConfigTools without a visible GUI window and
    imports the target project so its `.mex` is validated.
    """
    workspace = workspace or DEFAULT_WORKSPACE
    command = [str(_executable(s32ds_root))]
    launcher_ini = _launcher_ini(s32ds_root)
    if launcher_ini is not None:
        command += ["--launcher.ini", str(launcher_ini)]
    command += [
        "-nosplash",
        "-application", CONFIGTOOLS_APPLICATION,
        "-data", str(workspace),
        "-import", str(project),
        "-project", project.name,
    ]
    if sdk_path is not None:
        command += ["-sdkPath", str(sdk_path)]
    return command


@dataclass
class ValidationOutcome:
    exit_code: int
    command: list[str]
    log_path: str
    stdout: str = ""
    stderr: str = ""


def validation_log_path(project: Path) -> Path:
    """Return the path where validation logs are kept (under build/)."""
    return project / "build" / "configtools_validation.log"


def run_validation(
    project: Path,
    s32ds_root: Path,
    *,
    workspace: Path | None = None,
    sdk_path: Path | None = None,
    timeout_s: int = 180,
) -> ValidationOutcome:
    """Run the headless ConfigTools validation and capture logs.

    Execution is intended to be reached only when the caller has confirmed the
    vendor environment is available. The process runs without a visible window;
    stdout/stderr are captured and written under the project's build/ directory.
    """
    import subprocess

    command = build_validation_command(
        s32ds_root, project, workspace=workspace, sdk_path=sdk_path
    )
    log_path = validation_log_path(project)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    creationflags = 0
    if os.name == "nt":
        # CREATE_NO_WINDOW keeps the headless run from flashing a console window.
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # A vendor-tool timeout or a missing executable must surface as a structured
    # non-zero outcome, never as a traceback (acceptance rule: actionable
    # diagnostics, not tracebacks). The caller maps a non-zero exit to "blocked".
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
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        exit_code = 124  # conventional timeout exit code
        stdout = ""
        stderr = (
            f"S32DS headless validation exceeded the {timeout_s}s timeout; "
            "treat as not validated (not a pass)."
        )
    except (FileNotFoundError, OSError) as exc:
        exit_code = 127  # conventional command-not-found exit code
        stdout = ""
        stderr = f"Could not launch the S32DS validation executable: {exc}"

    log_path.write_text(
        f"$ {' '.join(command)}\n\n[stdout]\n{stdout}\n[stderr]\n{stderr}\n",
        encoding="utf-8",
    )
    return ValidationOutcome(
        exit_code=exit_code,
        command=command,
        log_path=str(log_path),
        stdout=stdout,
        stderr=stderr,
    )
