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
# File:        test_cleanup_tracked_scope.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Static fidelity and ownership for the cleanup Test gate.
# =================================================================================

"""CTD-14: complete requirements, case correspondence and declared source ownership."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/fixtures/cleanup-tracked-descendants"))
import cleanup_support as s

G = "9f2357d5b4983b3b2465c442920626cb440b0e9e"
DOCS = ROOT / "tests/doc/reference/agent"
REQUIREMENTS = DOCS / "cleanup-tracked-descendants-requirements.md"
CASES = DOCS / "cleanup-tracked-descendants-cases.md"
EXPECTED = json.loads(r'''{"R01":{"obligation":"cleanup_paths 必须在递归删除目标目录前，依据该 checkout 的真实 Git index 检查完整目标归属；只要目标自身或其任意后代被该仓库跟踪，就拒绝清理。父目录被忽略、文件被强制加入或早于 ignore 规则受跟踪，均不能豁免源保护；不以是否已提交或当前工作树字节是否与 index 一致作为豁免条件。","sources":["A_ISSUE112","A_R16_R17"]},"R02":{"obligation":"整个清理请求必须先完成全部目标的验证，再发生第一次删除。任何一个目标违反源保护或既有边界，都拒绝整批请求；调用顺序靠前的合法临时目标必须保留。dry_run=True 和 dry_run=False 对非法计划执行相同的拒绝语义。","sources":["A_ISSUE112","A_R16_R17","A_INTERFACE"]},"R03":{"obligation":"拒绝清理时保留受影响工作树文件的原始字节，包括未提交修改；不修改 Git index、Git commit、Candidate 源或被引用证据。拒绝不能依赖先删除再恢复，也不能通过移出或取消跟踪文件来使计划合法。","sources":["A_ISSUE112","A_R16_R17"]},"R04":{"obligation":"保留现有 cleanup_paths 公开 Python 签名、默认 dry_run=True 及结果格式：合法 dry-run 返回 version=1、status=PLANNED、目标相对路径且不删除；显式 dry_run=False 对合法 ignored 当前运行临时目标返回 status=CLEANED 并只删除所请求目标。新增源检查不能阻止正常临时文件/目录清理。","sources":["A_INTERFACE","A_HYGIENE"]},"R05":{"obligation":"保留合法 leaf symlink/junction 的清理能力：仅删除链接本身，不跟随或删除目的地；目录中的链接也不能成为越界遍历或删除目的地的通路。判断链接是否可清理时仍保留 Git 源保护和显式保护路径规则，不把链接目的地的源文件当作已被授权删除。","sources":["A_ISSUE112","A_R16_R17","A_INTERFACE"]},"R06":{"obligation":"保留既有 cleanup 路径防护：目标必须严格位于显式 allowed_base 下，base 限当前运行的 tests/.tmp 或 .agent-state/agent-loop 子树；拒绝源根、Git 存储、嵌套仓库、链接祖先、逃逸路径、重叠目标和与 protected_paths 相交的目标。只在所有边界验证完成后删除。","sources":["A_R16_R17","A_INTERFACE","A_HYGIENE"]},"R07":{"obligation":"完整 Git index 归属检查必须按真实路径处理合法文件名和目录边界，不得因特殊字符、空白、非 ASCII 名称或相似前缀遗漏受跟踪后代。若 Git/index 检查无法可信完成，则拒绝整个计划并保留全部目标；不能把查询失败当作无受跟踪内容。","sources":["A_ISSUE112","A_R16_R17","A_HYGIENE"]},"R08":{"obligation":"修复及验证限定于 #112 的 cleanup 源保护和实际直接依赖；公开文档准确说明新保护行为。保留现行 Agent Loop、W4 身份与角色所有权；不重开 #79 的终审尝试，不继承 R23 或其他历史临时特批，不读取旧任务本地执行资料或历史 Codex 对话，不修改无关 initializer、平台隔离、黑盒运行、S32DS 或 KPI 行为。","sources":["A_CHARTER","A_HUMAN","A_ISSUE112"]}}''')
ALLOWED = {
    "agent-discipline/skills/agent-workflow/scripts/workflow_environment_hygiene.py",
    "agent-discipline/skills/agent-workflow/scripts/workflow_environment_io.py",
    "agent-discipline/skills/agent-workflow/references/workflow-environment.md",
    "tests/unit/test_cleanup_tracked_generality.py",
    "tests/functional/test_cleanup_tracked_descendants.py",
    "tests/functional/test_cleanup_tracked_scope.py",
    "tests/fixtures/cleanup-tracked-descendants/cleanup_support.py",
    "tests/fixtures/cleanup-tracked-descendants/prevalidate_cleanup.py",
    "tests/doc/README.md",
    "tests/doc/reference/agent/cleanup-tracked-descendants-requirements.md",
    "tests/doc/reference/agent/cleanup-tracked-descendants-cases.md",
}
REFERENCE = "agent-discipline/skills/agent-workflow/references/workflow-environment.md"


def test_c14_complete_requirements_and_case_correspondence():
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert "87158a8d95d3fc671b2eaa1a4372f32d89bfaa14e0a461e371a7a5aec8774f7c" in text
    actual = dict(re.findall(r"^## (R\d+)\n\n(.*?)(?=\n## |\Z)", text, re.S | re.M))
    assert actual.keys() == EXPECTED.keys()
    for key, value in EXPECTED.items():
        assert actual[key].split("\n\n", 1)[0] == value["obligation"]
        for source in value["sources"]:
            assert source in actual[key]
    case_text = CASES.read_text(encoding="utf-8")
    case_ids = set(re.findall(r"\| (CTD-\d+) \|", case_text))
    functional = (ROOT / "tests/functional/test_cleanup_tracked_descendants.py").read_text(encoding="utf-8")
    assert case_ids == set(re.findall(r"CTD-\d+", functional)) | {"CTD-14"}
    assert len(case_ids) == 14
    index = (ROOT / "tests/doc/README.md").read_text(encoding="utf-8")
    for path in (REQUIREMENTS, CASES):
        assert path.name in index
    assert "执行步骤" not in case_text and "pytest" not in case_text


def test_c14_changes_stay_within_declared_surface():
    changed = s.cleanup_scope_changes(ROOT, G)
    assert changed <= ALLOWED, sorted(changed - ALLOWED)
    production = {p for p in changed if "/scripts/" in p}
    if production:
        assert REFERENCE in changed, "A production cleanup correction requires a public reference update."
    assert s.git(ROOT, "diff", "--check", G, "HEAD", check=False).returncode == 0
