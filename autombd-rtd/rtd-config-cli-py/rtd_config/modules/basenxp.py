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
# File:        basenxp.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: BaseNXP / OsIf module provider.
# =================================================================================

from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange, TargetSelector
from rtd_config.resources.bundles import ResolvedAssetBundle


_GENERAL_SETTING_CHANGES = {
    "user_mode_support": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfEnableUserModeSupport",
        "Set OsIfEnableUserModeSupport from the BaseNXP.xdm boolean surface",
    ),
    "dev_error_detect": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfDevErrorDetect",
        "Set OsIfDevErrorDetect from the BaseNXP.xdm boolean surface",
    ),
    "custom_timer": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfUseCustomTimer",
        "Set OsIfUseCustomTimer from the BaseNXP.xdm boolean surface",
    ),
    "get_user_id": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfUseGetUserId",
        "Set OsIfUseGetUserId to a CLI-exposed BaseNXP.xdm enum value",
    ),
    "instance_id": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfInstanceId",
        "Set OsIfInstanceId within the BaseNXP.xdm range [0, 255]",
    ),
    "get_physical_core_id": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfGetPhysicalCoreIdEnable",
        "Set OsIfGetPhysicalCoreIdEnable from the BaseNXP.xdm boolean surface",
    ),
    "software_semaphore": (
        "/BaseNXP/BaseNXP/OsIfGeneral/OsIfSoftwareSemaphoredEnable",
        "Set OsIfSoftwareSemaphoredEnable from the BaseNXP.xdm boolean surface",
    ),
}


class BaseNxpProvider:
    """Owns BaseNXP/OsIf shared infrastructure.

    OsIf timer choices affect Uart timeout behaviour. The provider owns the
    OsIfGeneral region including the system-timer flag and counter configuration.
    Values are grounded in the committed osif.json asset (derived from BaseNXP.xdm).
    """

    name = "basenxp"

    def __init__(self, bundle: ResolvedAssetBundle):
        self.bundle = bundle

    def plan(self, intent: Intent) -> Plan:
        changes = []
        for key, (path, description) in _GENERAL_SETTING_CHANGES.items():
            if key not in intent.payload:
                continue
            changes.append(PlannedChange(
                module="basenxp",
                owner="basenxp",
                path=path,
                description=description,
                targets=(TargetSelector(
                    "config_set:BaseNXP", ("OsIfGeneral", path.rsplit("/", 1)[-1]),
                ),),
            ))
        if intent.payload.get("enable_system_timer", False):
            # Basenxp-owned change 1: enable the OsIf system timer flag.
            changes.append(PlannedChange(
                module="basenxp",
                owner="basenxp",
                path="/BaseNXP/BaseNXP/OsIfGeneral/OsIfUseSystemTimer",
                description="Enable OsIf system timer (OsIfUseSystemTimer=true)",
                targets=(TargetSelector(
                    "config_set:BaseNXP", ("OsIfGeneral", "OsIfUseSystemTimer"),
                ),),
            ))
            # Basenxp-owned change 2: insert one OsIfCounterConfig whose
            # OsIfSystemTimerClockRef is populated with an Mcu McuClockReferencePoint
            # (CORE_CLK preferred, else first available) discovered from the project.
            # OsIfSystemTimerClockFreq is left as an empty array (ConfigTools type:
            # ArraySetting; a scalar <setting> causes vendor gate SEVERE).
            changes.append(PlannedChange(
                module="basenxp",
                owner="basenxp",
                path="/BaseNXP/BaseNXP/OsIfGeneral/OsIfCounterConfig",
                description=(
                    "Insert OsIfCounterConfig_0: OsIfSystemTimerClockRef populated "
                    "with an existing Mcu McuClockReferencePoint (CORE_CLK preferred, "
                    "else first available); OsIfSystemTimerClockFreq as empty array "
                    "(ConfigTools ArraySetting type)"
                ),
                targets=tuple(
                    TargetSelector("config_set:BaseNXP", ("OsIfCounterConfig", leaf))
                    for leaf in (
                        "OsIfCounterConfig_0", "Name", "OsIfSystemTimerClockRef",
                        "OsIfSystemTimerClockFreq", "OsIfOsCounterRef",
                    )
                ) + (TargetSelector(
                    "config_set:BaseNXP", ("OsIfCounterConfig",),
                ),),
            ))
            # Cross-module dependency: BaseNXP reads (read-only) an existing Mcu
            # McuClockReferencePoint to populate OsIfSystemTimerClockRef. This
            # dependency is declared explicitly per AGENTS.md; apply_basenxp_set
            # discovers the path at runtime via _find_mcu_clock_ref_path.
            changes.append(PlannedChange(
                module="mcu",
                owner="mcu",
                path="/Mcu/Mcu/McuModuleConfiguration/McuClockSettingConfig_0/McuClockReferencePoint",
                description=(
                    "Read-only dependency: BaseNXP requires an existing Mcu "
                    "McuClockReferencePoint to populate OsIfSystemTimerClockRef "
                    "(CORE_CLK preferred, else first available)"
                ),
            ))
        if not changes:
            changes.append(PlannedChange(
                module="basenxp",
                owner="basenxp",
                path="/BaseNXP/BaseNXP/OsIfGeneral",
                description="Preserve OsIf configuration used by Uart timeout",
            ))
        return Plan(changes)
