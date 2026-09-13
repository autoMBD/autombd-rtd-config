# 功能测试文档索引

| Field | Value |
| --- | --- |
| Version | 0.1.5 |
| Date | 2026-09-13 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | 新功能测试文档的简短公共布局说明与 Human 审阅索引。 |

本目录按类型、功能增量维护需求与用例，既有已接受功能不追溯补写。Human 优先审阅各功能的完整需求参考和简洁用例表；执行过程、自动化对应及运行证据留在脚本与结构化报告/Impact Set。文档和自动化由同一个精确 Test 提交绑定，批准后共同冻结。

| 类型 | 功能 | 需求参考 | 用例参考 |
| --- | --- | --- | --- |
| Agent | #85 Workflow Transition | [完整公开需求](reference/agent/workflow-transition-requirements.md) | [简洁用例表](reference/agent/workflow-transition-cases.md) |
| Agent | #86 Workflow Evidence Verification | [完整公开需求](reference/agent/workflow-evidence-requirements.md) | [简洁用例表](reference/agent/workflow-evidence-cases.md) |
| Agent | #79 Workflow Environment | [完整公开需求](reference/agent/workflow-environment-requirements.md) | [简洁用例表](reference/agent/workflow-environment-cases.md) |
| Agent | #112 Cleanup 受跟踪后代保护 | [完整公开需求](reference/agent/cleanup-tracked-descendants-requirements.md) | [简洁用例表](reference/agent/cleanup-tracked-descendants-cases.md) |
| Agent | #116 Coverage Dependencies | [完整公开需求](reference/agent/coverage-dependencies-requirements.md) | [简洁用例表](reference/agent/coverage-dependencies-cases.md) |
| Agent | #120 Isolation Compliance | [完整公开需求](reference/agent/isolation-compliance-requirements.md) | [简洁用例表](reference/agent/isolation-compliance-cases.md) |

当前未接受的用例和本索引仍属于 owner Test 私有材料，不向 Worker 披露；仅独立的公开需求参考可经审查后另行提供。KPI 文档仍在 docs/tests/，由独立 KPI issue 管理；本次不迁移、不新增 RTD 产品或历史用例。

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-07 | 0.1.0 | 按 K5 建立短共享索引；#85 需求与用例拆分为两份独立参考。 |
| 2026-09-09 | 0.1.1 | 增加 #86 K1 只读 evidence verifier 的独立需求与用例审阅入口。 |
| 2026-09-10 | 0.1.2 | 增加 #79 能力、隔离和派生初始化的独立需求与用例入口。 |
| 2026-09-11 | 0.1.3 | 增加 #112 cleanup 源保护的独立需求与用例入口。 |
| 2026-09-11 | 0.1.3 | 增加 #116 覆盖与公开依赖的独立需求和用例入口。 |
| 2026-09-11 | 0.1.4 | #116 文档按 K1 扩充源绑定的仅补录修复要求。 |
| 2026-09-13 | 0.1.5 | 增加 #120 隔离合规的完整需求与简洁用例入口。 |
