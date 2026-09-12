# Cleanup 受跟踪后代保护需求

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-11 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | #112 的完整公开需求与来源关联。 |

本文件逐项保存 #112 公开 K0 的完整 requirements；K 的 SHA-256 为 `87158a8d95d3fc671b2eaa1a4372f32d89bfaa14e0a461e371a7a5aec8774f7c`。它是 Human 审阅参考，完整 K 仍为两条工作线的任务依据。

## R01

cleanup_paths 必须在递归删除目标目录前，依据该 checkout 的真实 Git index 检查完整目标归属；只要目标自身或其任意后代被该仓库跟踪，就拒绝清理。父目录被忽略、文件被强制加入或早于 ignore 规则受跟踪，均不能豁免源保护；不以是否已提交或当前工作树字节是否与 index 一致作为豁免条件。

来源：[A_ISSUE112](https://github.com/autoMBD/autombd-rtd-config/issues/112)；[A_R16_R17](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/tests/doc/reference/agent/workflow-environment-requirements.md#r16)。

## R02

整个清理请求必须先完成全部目标的验证，再发生第一次删除。任何一个目标违反源保护或既有边界，都拒绝整批请求；调用顺序靠前的合法临时目标必须保留。dry_run=True 和 dry_run=False 对非法计划执行相同的拒绝语义。

来源：[A_ISSUE112](https://github.com/autoMBD/autombd-rtd-config/issues/112)；[A_R16_R17](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/tests/doc/reference/agent/workflow-environment-requirements.md#r16)；[A_INTERFACE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/workflow-environment.md)。

## R03

拒绝清理时保留受影响工作树文件的原始字节，包括未提交修改；不修改 Git index、Git commit、Candidate 源或被引用证据。拒绝不能依赖先删除再恢复，也不能通过移出或取消跟踪文件来使计划合法。

来源：[A_ISSUE112](https://github.com/autoMBD/autombd-rtd-config/issues/112)；[A_R16_R17](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/tests/doc/reference/agent/workflow-environment-requirements.md#r16)。

## R04

保留现有 cleanup_paths 公开 Python 签名、默认 dry_run=True 及结果格式：合法 dry-run 返回 version=1、status=PLANNED、目标相对路径且不删除；显式 dry_run=False 对合法 ignored 当前运行临时目标返回 status=CLEANED 并只删除所请求目标。新增源检查不能阻止正常临时文件/目录清理。

来源：[A_INTERFACE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/workflow-environment.md)；[A_HYGIENE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/scripts/workflow_environment_hygiene.py)。

## R05

保留合法 leaf symlink/junction 的清理能力：仅删除链接本身，不跟随或删除目的地；目录中的链接也不能成为越界遍历或删除目的地的通路。判断链接是否可清理时仍保留 Git 源保护和显式保护路径规则，不把链接目的地的源文件当作已被授权删除。

来源：[A_ISSUE112](https://github.com/autoMBD/autombd-rtd-config/issues/112)；[A_R16_R17](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/tests/doc/reference/agent/workflow-environment-requirements.md#r16)；[A_INTERFACE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/workflow-environment.md)。

## R06

保留既有 cleanup 路径防护：目标必须严格位于显式 allowed_base 下，base 限当前运行的 tests/.tmp 或 .agent-state/agent-loop 子树；拒绝源根、Git 存储、嵌套仓库、链接祖先、逃逸路径、重叠目标和与 protected_paths 相交的目标。只在所有边界验证完成后删除。

来源：[A_R16_R17](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/tests/doc/reference/agent/workflow-environment-requirements.md#r16)；[A_INTERFACE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/workflow-environment.md)；[A_HYGIENE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/scripts/workflow_environment_hygiene.py)。

## R07

完整 Git index 归属检查必须按真实路径处理合法文件名和目录边界，不得因特殊字符、空白、非 ASCII 名称或相似前缀遗漏受跟踪后代。若 Git/index 检查无法可信完成，则拒绝整个计划并保留全部目标；不能把查询失败当作无受跟踪内容。

来源：[A_ISSUE112](https://github.com/autoMBD/autombd-rtd-config/issues/112)；[A_R16_R17](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/tests/doc/reference/agent/workflow-environment-requirements.md#r16)；[A_HYGIENE](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/scripts/workflow_environment_hygiene.py)。

## R08

修复及验证限定于 #112 的 cleanup 源保护和实际直接依赖；公开文档准确说明新保护行为。保留现行 Agent Loop、W4 身份与角色所有权；不重开 #79 的终审尝试，不继承 R23 或其他历史临时特批，不读取旧任务本地执行资料或历史 Codex 对话，不修改无关 initializer、平台隔离、黑盒运行、S32DS 或 KPI 行为。

来源：[A_CHARTER](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/AGENTS.md)；A_HUMAN（当前任务 Human 指令，见下方完整文字）；[A_ISSUE112](https://github.com/autoMBD/autombd-rtd-config/issues/112)。

## A_HUMAN — 当前任务指令

2026-09-11 的当前任务指令，属于本次本地授权，未声称为远端投票：

> 基于最新 origin/master，按照仓库现行 Agent Loop 规则解决 autoMBD/autombd-rtd-config#112。任务依据限于该 Issue 的正文、有效公开评论、公开引用及仓库内容；不读取历史 Codex 对话或旧任务的本地执行资料，不继承历史临时特批。允许复用已验证的环境缓存。先核实依赖并固定 Governor，再按现行流程推进；如有缺失或冲突，指出具体问题，不自行扩展规则。

## 公开接口与判定顺序

`cleanup_paths(root: pathlib.Path, paths: Sequence[str], *, allowed_base: pathlib.Path, protected_paths: Sequence[str] = (), dry_run: bool = True) -> dict` 由 `workflow_environment.py` 导出，`workflow_environment_hygiene.py` 实现。拒绝保留既有 `EnvironmentError.code` 和 `as_dict()`；不新增 CLI 或 schema。

| 条件 | 结果与副作用 |
| --- | --- |
| 输入或既有词法、路径、链接、保护路径、源根边界非法 | 沿用既有错误类型和优先级，在删除前拒绝；无副作用。 |
| 目标自身或后代在真实 Git index 中受跟踪 | 整批以 `PATH_BOUNDARY` 拒绝；忽略状态和 dry-run 不构成豁免；无副作用。 |
| Git/index 归属无法可靠确认 | 既有 Git/identity `EnvironmentError`；不能把失败视为空结果；无副作用。 |
| 所有目标合法且 dry_run=True | `version=1`、`status=PLANNED` 和目标相对路径；无副作用。 |
| 所有目标合法且 dry_run=False | `status=CLEANED`；完成整批验证后仅移除指定目标，合法 leaf link 仅移除链接本身。 |

公开接口依据：[G 的 workflow-environment](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/workflow-environment.md#sourceevidence-hygiene-and-cleanup)。本任务不承诺既有 API 未提供的并发文件系统/index 事务隔离。

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-11 | 0.1.0 | 完整保存 #112 K0 的 R01–R08、来源和公开接口判定。 |
