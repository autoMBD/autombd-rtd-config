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
# File:        config.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Runtime configuration model for the RTD CfgFile CLI.
# =================================================================================

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import CliFailure


DEFAULT_ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"
_PATH_FIELDS = frozenset({
    "project", "s32ds_root", "sdk_path", "workspace", "temp_root", "log_root",
    "asset_root",
})
_STRING_FIELDS = frozenset({
    "backend", "vendor", "family", "device", "package", "rtd_version",
    "schema_version",
})
_ALLOWED_FIELDS = _PATH_FIELDS | _STRING_FIELDS | frozenset({"validation_timeout_s"})


def _invalid_config(message: str) -> CliFailure:
    return CliFailure(
        "invalid_arguments", message, module="cli", exit_code=2,
    )


def validate_runtime_config_fields(raw: dict[str, Any]) -> None:
    """Validate only the JSON object's shape before precedence is applied."""
    if not isinstance(raw, dict):
        raise _invalid_config("Runtime configuration must be a JSON object.")
    unknown = sorted(set(raw) - _ALLOWED_FIELDS - {"data_root"})
    if unknown:
        raise _invalid_config("Runtime configuration contains unknown fields.")


@dataclass(frozen=True)
class RuntimeConfig:
    project: Path
    backend: str = "mex"
    vendor: str = "nxp"
    family: str = "s32k3"
    device: str = "s32k344"
    package: str = "default"
    rtd_version: str = "7_0_1"
    schema_version: str = "19"
    s32ds_root: Path | None = None
    sdk_path: Path | None = None
    workspace: Path | None = None
    temp_root: Path | None = None
    log_root: Path | None = None
    asset_root: Path = DEFAULT_ASSET_ROOT
    validation_timeout_s: int = 180

    @property
    def data_root(self) -> Path:
        """Compatibility alias for the former runtime asset field."""
        return self.asset_root

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuntimeConfig":
        validate_runtime_config_fields(raw)
        values = dict(raw)
        if "data_root" in values:
            if "asset_root" in values:
                raise _invalid_config("Runtime configuration repeats the asset root.")
            values["asset_root"] = values.pop("data_root")
        if "project" not in values:
            raise _invalid_config("Runtime configuration requires a project path.")
        for key in _STRING_FIELDS & values.keys():
            value = values[key]
            if (
                not isinstance(value, str) or not value.strip()
                or len(value) > 128 or any(ord(char) < 32 for char in value)
            ):
                raise _invalid_config("Runtime configuration contains an invalid string field.")
            values[key] = value.strip()
        if values.get("backend", "mex") != "mex":
            raise _invalid_config("The requested runtime backend is not supported.")
        for key in _PATH_FIELDS & values.keys():
            value = values[key]
            if not isinstance(value, (str, Path)) or not str(value) or "\x00" in str(value):
                raise _invalid_config("Runtime configuration contains an invalid path field.")
            if len(str(value)) > 4096:
                raise _invalid_config("Runtime configuration contains an invalid path field.")
            values[key] = Path(value)
        timeout = values.get("validation_timeout_s", 180)
        if type(timeout) is not int or not 1 <= timeout <= 3600:
            raise _invalid_config("Runtime validation timeout must be an integer from 1 to 3600.")
        return cls(**values)
