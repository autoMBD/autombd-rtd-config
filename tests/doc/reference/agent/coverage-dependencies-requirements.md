# 覆盖与公开依赖：完整公开需求

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-09-11 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Issue #116 K1 的完整需求及来源，供独立功能审阅。 |

本文件完整呈现公开 K1 的 `payload.requirements`，不替代完整任务契约。K revision 为 **1**，原始字节 SHA-256 为 `76a7b3020d021c754ab68457a2b2639607297efe242744b74218c237ec5f30f3`。K1 新增 R09 并修订 R06/R08；其余要求保留。

公开能力边界：`LocalRules.coverage_join(self, artifact)` 沿用现有字段及 ProtocolError；`run_validation(artifact_path, expected_sha256, context_path, view, result_path) -> int` 及 CLI 不变。`validate_impact_projection` 的既有调用仍兼容；无完整补录证明的直接比较保持严格。完整 METADATA repair 可按 R09 补录已有实际覆盖；`validate_repair`、TEST_SUPPORT 和 `verify_evidence` 保留现有接口。

## R01

合并覆盖必须区分所选检查的覆盖归属与真实公开依赖。Implementation 路径与同一 check 中的其他路径共同出现在 covered_paths，不足以要求它们之间存在直接依赖，也不能据此生成、补齐、反向或压缩依赖边。一个检查可以覆盖互不直接依赖的多个源、测试、辅助或审阅文件。

来源：[A_ISSUE116](#a_issue116), [A_HANDOFF](#a_handoff), [A_SCHEMA](#a_schema)。

## R02

保留完整实际 G..T 与 G..I 变更清单及 Test/Implementation 不重叠所有权，覆盖 join 的实际路径清单不得缺失、增加或重复；每个变更的 requirement_ids 与 selected_check_ids 必须引用合法项，且每个选中映射仍要求该路径属于该 check 的 covered_paths、该变更的需求属于该 check 的需求。改动路径覆盖不能靠加入无关依赖或删去映射绕过。

来源：[A_ISSUE116](#a_issue116), [A_RULES](#a_rules), [A_SCHEMA](#a_schema)。

## R03

对已声明的 public_dependency_edges 保留独立的结构与覆盖检查：有向 from/to 路径对不得重复，声明边的两端均须出现在所选检查 covered_paths 的联集中；仅存在于 excluded checks 或未选覆盖外的依赖端点不足以满足覆盖。边的方向和 reason 描述现有真实直接关系；多级关系保留各条真实边，不强制端点之间新增直接捷径，也不强制所有边落在同一个检查中。不得用检查内路径的笛卡尔积、任意连通性或路径命名规则猜测未声明的真实依赖。

来源：[A_ISSUE116](#a_issue116), [A_SCHEMA](#a_schema), [A_REPAIR](#a_repair), [A_CHARTER](#a_charter), [A_HANDOFF](#a_handoff)。

## R04

维持现有机器校验与源码监督的责任边界：校验器检查所提供字节、身份、实际变更及已声明依赖的覆盖，不能宣称自动发现完整真实依赖、证明 reason 文字为真或证明命令确实执行了覆盖。Orchestrator 必须依据精确源核对实际依赖的真实性、完整性和 check 归属；遗漏真实依赖、虚构边、把固定版本来源关联冒充当前执行依赖，均不得因结构 CHECKED 而被接收。新公开说明必须明确此边界；不引入通用源码依赖抽取器或新的自动信任保证。

来源：[A_ISSUE116](#a_issue116), [A_CHARTER](#a_charter), [A_HANDOFF](#a_handoff), [A_EVIDENCE](#a_evidence)。

## R05

保留现有 schema、artifact/checkpoint、task/G/W/K、真实 Test/Implementation tip、manifest、Impact Set digest 和 Candidate 绑定验证，错误源身份、错误摘要、所有权或缺失覆盖仍通过现有校验接口拒绝；结构 CHECKED 不得冒充功能 PASS、Human 审批或完整自然语言正确性。公开 Python/CLI 入口与现有结果格式保持兼容，未受本 Issue 影响的拒绝语义不改变。

来源：[A_ISSUE116](#a_issue116), [A_RULES](#a_rules), [A_EVIDENCE](#a_evidence)。

## R06

冻结用例、断言、预期、通过标准、所选检查 ID/命令/需求、全部旧覆盖路径、排除范围和预验证模式的保护不变。仅 R09 所规定、Human 明确授权的覆盖归属补录可增加 covered_paths 元数据，不得扩大真实验收范围。描述性依赖修复仍由原生产者处理，逐边审计绑定真实源 blob 并保留原 T/批准与替换链；不能借 metadata repair 删除旧覆盖、换命令、改变源或复用过期结果。真实 Test support 源变化仍走已有真实源身份、语义审计和重验边界。

来源：[A_ISSUE116](#a_issue116), [A_REPAIR](#a_repair), [A_HANDOFF](#a_handoff), [A_HUMAN_COVERAGE_ADDITION](#a_human_coverage_addition)。

## R07

修正后的校验器应在保持现有 v2/W2-W4 关闭 schema 和实际版本能力约束的前提下核验既有 Governor/Workflow 绑定的合法材料。升级校验器本身不能改写某运行的 G/W/K、Test 批准、Candidate 或原证据；显式 legacy W1 路径保持原样。本 Issue 完成后恢复 #112 前，Orchestrator 记录经过独立审阅的校验器精确源版本，并在旧运行上下文重新核验，不把新源码伪装成旧校验器或把新 G 套到旧运行。

来源：[A_ISSUE116](#a_issue116), [A_HANDOFF](#a_handoff), [A_EVIDENCE](#a_evidence)。

## R08

实现只修改 coverage_join/其直接本地规则和 R09 必需的 repair_protocol.py 逻辑、精确公开规范及 Worker 自有通用性测试；Test 独立从完整 K 验证合法共享覆盖、真实多级关系、遗漏声明依赖端点覆盖、R09 的安全补录与拒绝边界及既有身份/冻结保护，适用 RED、已知好/坏及全链证据必须真实。禁止在本 Issue 修改 #112 cleanup 实现、schema/registry/W、旧审批证据、修正次数、终审次数、KPI、RTD 或其他运行机制；不读取历史 Codex 对话或旧任务本地执行资料。

来源：[A_ISSUE116](#a_issue116), [A_HUMAN](#a_human), [A_CHARTER](#a_charter), [A_HUMAN_COVERAGE_ADDITION](#a_human_coverage_addition)。

## R09

允许通过现有 METADATA repair 对遗漏的 covered_paths 做有审计的仅增补纠错，限于精确原 Test 源和未变所选命令已经实际覆盖的路径。保留每个 check 的全部旧路径，不得移除/转移旧覆盖、变更 check ID/family/argv/requirement_ids、排除、预验证模式或任何冻结用例语义；实际扩大验收仍需新的 Human 决定，不能由结构通过替代。补录必须绑定现有原报告和原/新 Impact Set 附件、精确 changed_fields、原 T 的 preserve_tip、每个新增路径在该精确源中的真实 blob、全部受影响 check IDs，并由现有 Orchestrator semantic_audit 明确核对 coverage 及所有冻结维度；只给许可 flag、空审计、错误/缺失源绑定或随意理由不足以放行。使用现有关闭修复字段与逐边 source_facts/审计，不引入新 schema；新摘要依原生产者替换链重新校验，保留原 T/批准、源码和计数。既有 API 调用保持兼容；缺少补录证明的直接投影比较仍不能把增加路径当作普通元数据无条件通过。

来源：[A_HUMAN_COVERAGE_ADDITION](#a_human_coverage_addition), [A_REPAIR](#a_repair), [A_HANDOFF](#a_handoff), [A_ISSUE116](#a_issue116)。

## 来源

### A_ISSUE116

[A_ISSUE116 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/issues/116)。

### A_HUMAN

2026-09-11 本轮 Human 决定：“单独修正规则，再恢复自动流程”。该决定授权独立修正 #116，适用校验器经过核验后恢复 #112；不批准 #116 Test、不授权合并，也不更改 #112 的 G/W/K/T。独立 worktree 与 Human/Orchestrator 源码监督沿用当前授权，不能表示为 OS 读隔离。公开上下文见 [Issue #116](https://github.com/autoMBD/autombd-rtd-config/issues/116)。

### A_CHARTER

[A_CHARTER 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/AGENTS.md)。

### A_RULES

[A_RULES 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/scripts/structured_handoff_rules.py)。

### A_HANDOFF

[A_HANDOFF 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/structured-handoffs.md)。

### A_REPAIR

[A_REPAIR 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/scripts/repair_protocol.py)。

### A_SCHEMA

[A_SCHEMA 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json)。

### A_EVIDENCE

[A_EVIDENCE 的精确公开来源](https://github.com/autoMBD/autombd-rtd-config/blob/cf78144a3786d1dc3f1e92d27157674a7ebea85c/agent-discipline/skills/agent-workflow/references/workflow-evidence.md)。

### A_HUMAN_COVERAGE_ADDITION

2026-09-11 本轮 Human 明确答复：“纳入 #116，按上述边界修正规则（建议）”。授权只补录精确原 Test 和未变命令已实际覆盖的路径；全部旧路径、用例、命令及实际验收范围保留，源绑定和语义审计必需，保留原 T/批准与生产者替换链。此为范围授权，不是 Test Gate 或合并批准，不授权新 schema 或任意验收扩大。公开相关功能背景见 [Issue #116](https://github.com/autoMBD/autombd-rtd-config/issues/116)。

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-11 | 0.1.0 | 完整呈现 #116 K0 的 R01–R08 及公开来源。 |
| 2026-09-11 | 0.2.0 | 按 K1 修订 R06/R08，完整增加 Human 授权的 R09 及来源。 |
