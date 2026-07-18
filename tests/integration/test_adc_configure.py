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
# File:        test_adc_configure.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-19
# Version:     0.1.0
# Description: CLI integration test for `adc set --spec ... --configure`
#              (RTD-MEX-ADC-001) on a staged ADC fixture copy.
# =================================================================================

"""CLI integration: `adc set --spec <json> --configure` (RTD-MEX-ADC-001).

Drives the full load->apply->write->static-check pipeline via the public CLI
on a staged fixture copy and asserts status=passed plus the key .mex mutations.
"""
import json
import subprocess
import sys

from rtd_config.backends.s32_mex.document import MexDocument
from tests.fixtures import copy_adc_fixture


MEX_NAME = "Autombd_Test_Adc_S32K344.mex"


def _spec() -> dict:
    return {
        "unit": "ADC1",
        "transfer": "interrupt",
        "sampling_time_us": 1,
        "groups": [
            {
                "name": "AdcGroup_0",
                "trigger": "sw",
                "access": "single",
                "conv": "oneshot",
                "num_samples": 1,
                "notification": "Autombd_AdcNotifi0",
                "channels": ["VREFL", "S10"],
            },
            {
                "trigger": "sw",
                "access": "streaming",
                "conv": "continuous",
                "num_samples": 10,
                "notification": "Autombd_AdcNotifi1",
                "channels": ["VREFH", "P5"],
            },
        ],
        "watchdog": [
            {"channel": "P5", "high": 3000, "low": 20, "notification": "Autombd_AdcNotifiWdg"},
        ],
    }


def _write_spec(tmp_path) -> str:
    spec_path = tmp_path / "adc001.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    return str(spec_path)


def test_cli_adc_set_configure(tmp_path):
    project = copy_adc_fixture(tmp_path)
    spec_path = _write_spec(tmp_path)

    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "adc", "set",
            "--project", str(project),
            "--spec", spec_path,
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert "adc" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"

    # Verify the key mutations landed.
    doc = MexDocument.load(project / MEX_NAME)
    adc_cfg = doc.find_config_set("Adc")
    units = []
    for el in adc_cfg.iter():
        if el.tag.endswith("array") and el.attrib.get("name") == "AdcHwUnit":
            units = [c for c in el if c.tag.endswith("struct")]
            break
    unit_ids = {
        doc.find_child_setting(u, "AdcHwUnitId").attrib.get("value") for u in units
    }
    assert "ADC1" in unit_ids, f"ADC1 unit must exist; got {unit_ids}"


def test_cli_adc_set_plan_only_does_not_modify(tmp_path):
    project = copy_adc_fixture(tmp_path)
    spec_path = _write_spec(tmp_path)
    mex = project / MEX_NAME
    original = mex.read_bytes()

    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "adc", "set",
            "--project", str(project),
            "--spec", spec_path,
            "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["command"] == "plan", payload
    assert mex.read_bytes() == original, "plan-only run must not modify the file"


def test_cli_adc_dma_configure_passes_complete_mcl_ownership_audit(tmp_path):
    project = copy_adc_fixture(tmp_path)
    spec_path = tmp_path / "adc-dma-generality.json"
    spec_path.write_text(json.dumps({
        "unit": "ADC0",
        "transfer": "dma",
        "sampling_time_us": 3,
        "groups": [{
            "trigger": "sw",
            "access": "streaming",
            "conv": "continuous",
            "num_samples": 6,
            "channels": ["S18", "S19"],
        }],
    }), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config", "adc", "set",
            "--project", str(project),
            "--spec", str(spec_path),
            "--configure", "--json",
        ],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed", payload
    assert payload["changed_modules"] == ["adc", "mcl"]
