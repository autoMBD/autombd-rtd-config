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
# File:        pins.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Pin-options query over committed runtime pin-mapping assets.
# =================================================================================

from __future__ import annotations

import re
from pathlib import Path
from .runtime import load_json


def _normalize_peripheral(peripheral: str) -> str:
    """Normalize a user-facing peripheral name to the asset-internal form.

    The asset stores peripheral names as they appear in the IOMUX workbook's
    Module/peripheral column (col E), e.g. "LPUART0", "LPSPI3", "LPI2C1".
    The user-facing CLI form (and the existing test contract) uses an underscore
    before the instance digit, e.g. "LPUART_0", "LPSPI_3", "LPI2C_1".

    Normalization rule: remove an underscore that appears immediately before a
    sequence of digits at the end of the name, e.g. LPUART_0 -> LPUART0.
    This is a mechanical transform with no invented values — it mirrors the
    exact difference between the two naming conventions in the workbook.
    """
    return re.sub(r"_(\d+)$", r"\1", peripheral)


def _present_peripheral(asset_peripheral: str, requested_peripheral: str) -> str:
    """Return the peripheral name in the user-facing form.

    If the requested form (e.g. "LPUART_0") differs from the asset form
    (e.g. "LPUART0") only by the underscore-before-digit convention, return
    the requested form so the caller sees a consistent presentation.
    Otherwise return the asset form unchanged.
    """
    if _normalize_peripheral(requested_peripheral) == asset_peripheral:
        return requested_peripheral
    return asset_peripheral


def pin_options(
    data_root: Path,
    device: str,
    package: str,
    peripheral: str,
    family: str = "s32k3",
) -> list[dict]:
    """Return pin-option records for a peripheral from the committed runtime asset.

    Committed asset layout: assets/<vendor>/<family>/<module>/pins.json.
    The asset stores peripheral names in the IOMUX workbook form (e.g. "LPUART0").
    The caller may supply the user-facing underscore form (e.g. "LPUART_0");
    normalization bridges the two naming conventions transparently.
    The returned records present `peripheral` in the caller-supplied form so
    the CLI JSON output is consistent with the user's request.
    """
    path = data_root / "nxp" / family / "port" / "pins.json"
    data = load_json(path)
    asset_peripheral = _normalize_peripheral(peripheral)
    result = []
    for item in data["signals"]:
        if item["peripheral"] == asset_peripheral:
            # Return a copy with peripheral in the user-facing form
            presented = dict(item)
            presented["peripheral"] = _present_peripheral(
                item["peripheral"], peripheral
            )
            result.append(presented)
    return result
