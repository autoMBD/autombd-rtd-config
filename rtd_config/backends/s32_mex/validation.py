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

This encodes the *verified* S32DS 3.6.x ConfigTools headless flow (confirmed by
running it against the installed toolchain during M1 acceptance):

- launch ``s32dsc.exe`` with ``--launcher.ini <eclipse>/s32ds.ini`` (the console
  launcher shares the GUI launcher ini; do not use ``s32ds.bat``);
- drive the ConfigTools framework app ``com.nxp.swtools.framework.application``
  with ``-nosplash -consoleLog`` and a ``-HeadlessTool`` (e.g. ``Peripherals``).
  WITHOUT ``-HeadlessTool`` the app starts a workbench and never terminates;
- point ``-sdkPath`` at the S32DS PlatformSDK that ships ``sdk_manifest.xml``
  (``<root>/S32DS/software/PlatformSDK_S32K3``), not a standalone RTD package;
- the target project must be a REGISTERED workspace project, otherwise
  ConfigTools reports ``Cannot get container for IPath``; register it first with
  the CDT headless ``-import`` application;
- load + generate with ``-Load <mex> -ProjectLink <project> -UpdateCode`` and
  surface problems with ``-ShowProblems SEVERE``.

Pass condition: ConfigTools exits ``0`` AND reports no SEVERE ``[TOOL]`` resource
validation problem. Exit ``0`` alone is NOT sufficient -- ConfigTools returns
``0`` even when it logs SEVERE configuration errors.

Commands are built as data so they are unit-testable without launching a vendor
tool. Execution is gated by the caller and the ``RTD_CONFIG_RUN_S32DS_VALIDATION``
environment flag.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rtd_config.backends.s32_mex.locate import find_single_mex


# S32 ConfigTools standalone application id (registered in S32DS 3.6.x). The
# older ".HeadlessApplication" suffix is NOT registered, and ConfigTools only
# runs headless when a -HeadlessTool is supplied as well.
CONFIGTOOLS_APPLICATION = "com.nxp.swtools.framework.application"

# CDT headless application used to register (import) a project into the workspace
# so ConfigTools can resolve its container.
CDT_HEADLESS_APPLICATION = "org.eclipse.cdt.managedbuilder.core.headlessbuild"

# Documented default S32DS Eclipse workspace on the development computer.
DEFAULT_WORKSPACE = Path(r"D:\WorkSpace\DSpace\3.6")

# ConfigTools headless tool that drives RTD peripheral (.mex) configuration.
DEFAULT_HEADLESS_TOOL = "Peripherals"

# ConfigTools logs real module-configuration errors as SEVERE
# "[TOOL] The resource ... has the following error"; "Toolchain/IDE project"
# driver-not-found problems are project-build-setup noise (not .mex validity) and
# are deliberately excluded from the pass gate.
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


def build_register_command(
    s32ds_root: Path,
    project: Path,
    *,
    workspace: Path | None = None,
) -> list[str]:
    """Build the CDT headless command that registers a project in the workspace.

    ConfigTools cannot resolve a project's container ("Cannot get container for
    IPath") unless the project is a workspace member; importing it first fixes
    that. Re-importing an already-present project is harmless.
    """
    workspace = workspace or DEFAULT_WORKSPACE
    return _launcher_prefix(s32ds_root) + [
        "-nosplash",
        "-consoleLog",
        "-application", CDT_HEADLESS_APPLICATION,
        "-data", str(workspace),
        "-import", str(project),
    ]


def build_validation_command(
    s32ds_root: Path,
    project: Path,
    *,
    workspace: Path | None = None,
    sdk_path: Path | None = None,
    headless_tool: str = DEFAULT_HEADLESS_TOOL,
    mex_file: Path | None = None,
) -> list[str]:
    """Build the headless S32 ConfigTools load/validate command for a project."""
    workspace = workspace or DEFAULT_WORKSPACE
    sdk_path = sdk_path or default_sdk_path(s32ds_root)
    if mex_file is None:
        mex_file = find_single_mex(project)
    return _launcher_prefix(s32ds_root) + [
        "-consoleLog",
        "-nosplash",
        "-application", CONFIGTOOLS_APPLICATION,
        "-data", str(workspace),
        "-HeadlessTool", headless_tool,
        "-Load", str(mex_file),
        "-ProjectLink", str(project),
        "-sdkPath", str(sdk_path),
        "-UpdateCode",
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
    registered: bool = False

    @property
    def passed(self) -> bool:
        """Pass = ConfigTools exit 0 AND no SEVERE [TOOL] config problem."""
        return self.exit_code == 0 and not self.severe_problems


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


def _workspace_project_meta(workspace: Path, name: str) -> Path:
    return (
        workspace / ".metadata" / ".plugins"
        / "org.eclipse.core.resources" / ".projects" / name
    )


def _unstage(workspace: Path, name: str, staged: Path | None) -> None:
    """Remove a staged in-workspace copy and its workspace metadata entry."""
    if staged is not None:
        shutil.rmtree(staged, ignore_errors=True)
    meta = _workspace_project_meta(workspace, name)
    if meta.exists():
        shutil.rmtree(meta, ignore_errors=True)


def run_validation(
    project: Path,
    s32ds_root: Path,
    *,
    workspace: Path | None = None,
    sdk_path: Path | None = None,
    headless_tool: str = DEFAULT_HEADLESS_TOOL,
    mex_file: Path | None = None,
    register: bool = True,
    timeout_s: int = 180,
) -> ValidationOutcome:
    """Register (best effort) then headlessly validate a project's .mex.

    ConfigTools can only resolve a project's container when the project is a
    member of the ``-data`` workspace. If the project lives outside the
    workspace, a transient copy is staged inside it, validated, and removed; the
    caller's project is never modified. Execution is intended only when the
    vendor environment is available. The pass decision is the returned outcome's
    ``passed`` property (exit 0 AND no SEVERE [TOOL] problem).
    """
    workspace = workspace or DEFAULT_WORKSPACE
    project = Path(project)
    sdk_path = sdk_path or default_sdk_path(s32ds_root)

    # Log under the caller's real project even when validation runs on a stage.
    log_path = validation_log_path(project)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    staged: Path | None = None
    if workspace.resolve() not in project.resolve().parents:
        staged = workspace / project.name
        _unstage(workspace, project.name, staged)
        shutil.copytree(project, staged)
        target = staged
    else:
        target = project

    sections: list[str] = []
    try:
        target_mex = mex_file if (mex_file is not None and staged is None) else find_single_mex(target)
        if register:
            reg_cmd = build_register_command(s32ds_root, target, workspace=workspace)
            reg_code, reg_out, reg_err = _run(reg_cmd, timeout_s)
            sections.append(
                f"$ {' '.join(reg_cmd)}\n[register exit {reg_code}]\n{reg_out}\n{reg_err}\n"
            )

        val_cmd = build_validation_command(
            s32ds_root, target,
            workspace=workspace, sdk_path=sdk_path,
            headless_tool=headless_tool, mex_file=target_mex,
        )
        exit_code, stdout, stderr = _run(val_cmd, timeout_s)
        severe = find_severe_tool_problems(stdout + "\n" + stderr)

        sections.append(
            f"$ {' '.join(val_cmd)}\n[validate exit {exit_code}]\n"
            f"[stdout]\n{stdout}\n[stderr]\n{stderr}\n"
            "[severe_tool_problems]\n" + "\n".join(severe) + "\n"
        )
    finally:
        if staged is not None:
            _unstage(workspace, project.name, staged)

    log_path.write_text("".join(sections), encoding="utf-8")

    return ValidationOutcome(
        exit_code=exit_code,
        command=val_cmd,
        log_path=str(log_path),
        stdout=stdout,
        stderr=stderr,
        severe_problems=severe,
        registered=register,
    )
