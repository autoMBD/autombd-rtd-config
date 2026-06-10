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
    build_validation_command,
    default_sdk_path,
    find_severe_tool_problems,
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
