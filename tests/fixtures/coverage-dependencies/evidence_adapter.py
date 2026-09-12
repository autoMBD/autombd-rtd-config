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
# File:        evidence_adapter.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Bind unchanged evidence assertions to actual fixture Governor.
# =================================================================================

"""Preserve accepted evidence assertions while binding fixture protocol to G.

The accepted fixture writes W3 to its Git Governor but context_data reads current
W4. This adapter changes that single non-case input to the actual recorded blob.
It does not edit the accepted fixture, test assertions or production verifier.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests/functional"))
import workflow_evidence_cases
import test_workflow_evidence as original


class BoundHistory(workflow_evidence_cases.History):
    def context_data(self):
        context = super().context_data()
        context["protocol"]["workflow_contract"] = json.loads(self.git("cat-file", "blob", self.gov["workflow_contract_blob"]))
        return context


def run_original_case(root, case):
    h = BoundHistory(root)
    api = workflow_evidence_cases.load_target()
    if case in {"ready", "candidate", "gap", "corrected"}:
        index = None if case == "ready" else 1 if case == "corrected" else 0
        original.test_source_projection_and_count_are_independent(api, h, case, index)
    elif case == "tamper":
        original.test_present_attachment_tamper_is_invalid(api, h)
    elif case == "union":
        original.test_real_candidate_direct_union_not_only_parent_claim(api, h)
    else:
        raise AssertionError(case)
