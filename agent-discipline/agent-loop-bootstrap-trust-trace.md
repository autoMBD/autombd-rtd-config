# Agent Loop Bootstrap Trust Trace

| Field | Value |
| --- | --- |
| Version | 0.12.2 |
| Date | 2026-09-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Status | #93 manual implementation and focused verification completed in the feature worktree; Human inspection pending; no commit, push or merge |
| Description | Agent Loop 的 Category B trust-tracing lane：保留现状审计与历史教训，维护结构化交接、统一守卫、双 lane 与 Candidate 0 加三次修正、人工自举、动态监督和工具超时，并记录三级测试、RTD CfgFile CLI 单向 KPI Issue 与本地结果展示的批准设计及实施边界。 |

## 0. Trust-tracing lane 的权威与维护边界

本文件不是新的 workflow executor，也不取代现有机器合同。它承担四个互相分离的
职责：

1. **Baseline audit**：冻结已经完成的框架盘点、历史失败和成功收敛机制；
2. **Versioned design**：记录经 Human 批准的有限自举规则；
3. **Current bootstrap snapshot**：给出当前可复核状态的派生视图；
4. **Append-only trust trace**：按事件追加 exact identity、证据和下一合法操作。

真正权威仍分别属于：Git commit/blob 的代码身份、GitHub Human comment 的审批、
`workflow-contract.json` 的机器生命周期、以及 raw receipt 的执行结果。本文件只引用
这些权威并解释它们之间的关系，不得用自然语言摘要覆盖不一致的原始证据。

本文件使用 governance/trust lane 维护；当前产品任务新增的 trace/runtime evidence
不作为 merge-only edits 注入 Test、Implementation 或 Candidate。已经通过治理 PR
合入并存在于 `G` 中的本文属于正常基线，不因后续 Candidate 继承它而违规。本文自身
的治理变更按 Human 批准的范围审阅、提 PR，不借 Reviewer lesson child 自动合入。
历史事件只追加；发现旧记录有误时追加 `supersedes` 事件，不改写旧事件。经 Human
要求纠正的设计正文和派生快照可以更新，但必须记录版本与纠正依据。

## 1. 审阅结论

§1–§7 保留审阅基线 `9331d668...` 的盘点与历史结论，不用未合并代码改写历史。
当前执行状态以 §14.1 与 BT-0011 为准：Human 已批准 #93 编码，结构化协议与统一
守卫已在功能分支工作区实现并完成定向验证，但尚未提交、合并或部署到 Agent 平台目录。

### 1.1 本版对前版结论的纠偏

本报告 0.2.0 对现有规则盘点基本成立，但把部分**历史运行方式**误写成了今后的
正确流程。Owner 在本轮复盘中给出了更精确、且优先级高于历史 issue prompt、
heartbeat 和当前活动文档的治理定义。本版据此作出以下核心纠偏：

1. Test lane 与 Implementation lane 从同一 Governor、同一 Task Contract Epoch
   **独立并行推进**；Test lane 一旦形成可交付结果即可发布 Human Review Gate 1，
   不等待 Worker。Gate 1 的唯一审批对象是 exact Test；Governor、Task Contract、
   Test Impact Set 和预验证是该 Test Gate 的绑定身份与支持证据，不是额外审批对象，
   Implementation 更不在 Gate 1 审核范围内。首次 Candidate 组装才同时要求 exact
   Test 已获批准且 `I0` ready。
2. Test owner 在构建 Gate 期间负责完整 reference/full-chain prevalidation；Human
   未批准时可以继续修 Test，一旦批准，exact Test SHA 在本任务结束前永久冻结。
3. 首次组装和测试是 **Candidate 0**，不消耗修正机会；Worker 最多有三次在原
   Implementation 进展上增量修正的机会，依次产生 Candidate 1、2、3。因此一个
   task 最多有四个 Candidate，而不是三个。
4. Candidate 失败不触发“换一个 fresh Worker、从 Governor 重写”。同一个 Worker
   消费经过 Orchestrator 去除 owner-Test 泄漏的失败报告，在同一 Implementation
   lineage 上修正；只有 Human 明确选择新的 Governor 才发生 Git rebaseline，公开
   合同变化只产生新的 Task Contract Epoch。两者都不自动作废可复用 source/patch。
5. Reviewer 在 task **终止时恰好运行一次**：Candidate 通过时审查成功结果；
   Candidate 3 仍失败时审查失败过程、剩余缺陷和治理证据。Reviewer 不是每次
   Candidate 的一部分，也不驱动新的 Attempt。
6. 成功 PR 的 head 是经过 Tester PASS 和 terminal Reviewer APPROVED 的 exact
   **acceptance Candidate `Ck=[T,Ik]`**；`G..Ck` 同时包含 Human-approved frozen Test
   和最终 Implementation，包括 Worker-owned generality tests。开发期间的双 lane
   隔离不等于最终 PR 排除测试。Gate 1 只批准 Test，不授权单独把 Test 推入主线；
   Human final approval 后通过 PR 合入同一个 `Ck`，不得换成 `Ik` 或 lesson child。
   失败则不建成功 PR，只记录 Tester/Reviewer 终态并保留已有实现。

本版撤回前版的 **Implementation-only PR** 及“Test/Candidate 进入主线即构成污染”
推论：这两项是 Orchestrator 的错误解释，不是 Owner 要求。§6.9、§9.11 给出统一
拓扑与合并规则；BT-0008 记录本次纠正。历史提交事实、旧事件和旧 changelog 保留，
其中被纠正的解释不再作为执行依据；不重写 `G` 之前的 Git 历史。

v0.12.0 另按 Owner 的三级测试讨论纠偏：Worker TDD unit、Tester 人审 feature
functional gate、合并后 RTD CfgFile CLI 综合 KPI 是不同目的的交付。KPI 不再进入
功能 Candidate 的放行或自动优化计数；由 Reviewer 形成建单决定、Orchestrator 提
PR 时建立待 merge 的 KPI Issue，Human 在源 Candidate 获批且源 PR 实际合并后
启动该 Issue。用例与结果都经人审，本地不自动触发、不做 CT、不追溯补齐历史测试
架构。完整规则见 §9.14，实施旁路见 §11.12，BT-0009 记录本次授权；这些仍是待
实现设计，不是对当前机器合同或 runner 已具备能力的声明。

当前 `workflow-contract.json`、Agent Workflow Skill、`AGENTS.md` 和角色说明仍
保留“`candidate_attempt=1..3`”“Gate 1 后才实施”“Reviewer 仅在 Tester PASS 后”
以及 Reviewer 写 repo lessons 的旧模型。因此本版不是声称新模型已经落地，而是
把这些冲突登记为下一次受治理开发前必须先修正的 **B0 合同缺陷**。

### 1.2 当前能力定位

当前主线并非“只有规则、完全没有执行能力”，但也不能称为可靠的
Agent Loop 执行框架。准确描述是：

> 当前系统由一个较强的静态验收快照校验器、一个机械身份/命令交接守卫、
> 一个接口包形状检查器，以及大量文档化角色规则组成。它能够拒绝一部分
> 错误证据和错误执行上下文，但不能驱动工作流、证明角色交接语义充分、
> 让角色任务输入/输出成为统一且可守卫的结构化文件、重放状态历史或确定性
> 组装 Candidate。

这次 #85 的三项最终失败不是三个互不相关的偶发编码错误：

- contract 绑定检查顺序错误：期望 `MALFORMED_EVENT`，实际
  `INVALID_RECORD`；
- approval actor/command 身份漂移：期望 `STALE_EVENT`，实际
  `MISSING_EVIDENCE`；
- F1 在当前 checkpoint 的路由分类错误：期望 `ILLEGAL_TRANSITION`，实际
  `OUT_OF_ORDER_EVENT`。

三者共同证明：现有 #90 packet 能证明“接口字段齐全、摘要未漂移”，却不能证明
公开语义交接已经完整覆盖行为、判定顺序和错误分类。这绝不意味着 Worker 应读取
owner Test。正确边界是：Worker 只从公开合同独立实现；Tester 可同时读取 frozen
Test 和 Candidate Implementation，负责形成完整的实现缺陷与根因分析；Orchestrator
再把该报告转换成不含 Test source、case、literal 或 mutant 的 Worker Correction
Envelope。Reference PASS 证明 Test 与 reference overlay 能相互配合，不等于证明
公开语义合同充分，也不等于证明 Tester→Orchestrator→Worker 的安全诊断桥已经存在。
它仍应保留在 Test Gate Ready Report 中，因为它独立证明所选 Test Impact Set 能在
真实 discovery/import/CLI/cwd/temp/fixture 链上运行，并能区分 known-good 与
known-bad；它不进入 Worker 输入，也不再承担 `K` 有效性证明。

本次审阅建议保留并继续使用已经合并的 P0 最小 Loop、#88 和 #90，不推倒重来。
下一步不应先建设一个完整 `loopctl` 或一次铺开全功能执行器，而应复用 #78 已经
证明有效的增量自举原则，并采用一个人类深度监督、单边界、可退出的
`BOOTSTRAP-LIMITED` 流程。当前先由 #94 冻结本 trust trace，再由 #57 Phase 1
完成执行索引；第一项实现 package 是 Timeout Package A
[#95](https://github.com/autoMBD/autombd-rtd-config/issues/95)，其 accepted merge
成为 #93 Governor。随后 #93 才把结构化交接文件、统一守卫、lane 生命周期、
Candidate 0+三次修正、terminal Reviewer 和 accepted-Candidate PR topology 固化到
合同/角色文档及最小回放 gate。未知问题默认进入观察账本，只阻塞受影响操作；除非
它破坏证据完整性、安全性或强制验收项，否则不得自动扩展为全局规则或更高阻塞等级。

## 2. 审阅范围、方法与证据基线

### 2.1 基线

- Repository：`autoMBD/autombd-rtd-config`
- Branch：`master`
- 审阅 HEAD：`9331d6684d4cfb977212ef60e70771e36c065b7c`
- 审阅时远端：`master == origin/master`

### 2.2 审阅对象

本次覆盖：

- `AGENTS.md` 中的 Orchestrator、角色、隔离、验收、测试和文档规则；
- `agent-discipline/workflow-contract.json`；
- `agent-discipline/skills/agent-workflow/` 下的 Skill 和三个主线脚本；
- Explorer、Worker、Tester、Reviewer 四个角色定义；
- Agent 环境初始化 Skill 及其 GUI/deployer 边界；
- Agent Loop 相关 owner/generality tests 和当前 CI 入口；
- #57、#59、#78、#79、#80、#81、#82、#83、#85、#86、#87、#88、#90、#92
  的计划或历史证据；
- `.agent-state/` 中与 #85 R2 交接、reference prevalidation、Candidate 失败和
  handoff events 直接相关的本地证据。

本次不把以下内容当成已落地能力：

- Codex 产品内部 heartbeat/automation 的临时 prompt；
- 未合并分支中的实现；
- issue 评论里声明但没有进入主线代码、合同或可重放证据的规则；
- 仅凭自然语言声称已经运行、但当前证据链无法重新绑定的执行结果。

### 2.3 新鲜验证

审阅期间在上述 HEAD 运行了当前主线的五组 Agent Loop 核心测试：

```text
tests/unit/test_agent_workflow_bootstrap.py
tests/unit/test_agent_workflow_bootstrap_generality.py
tests/unit/test_handoff_guard.py
tests/unit/test_interface_handoff_check.py
tests/unit/test_interface_handoff_check_generality.py
```

结果：

```text
137 passed, 248 subtests passed in 138.06s
```

这证明当前已提交工具在其现有测试合同内是绿色的；它不证明本审阅指出的
设计外能力已经存在，也不证明现有测试合同没有遗漏。

### 2.4 结论标签

为避免把所有观察都升级为阻塞项，本文使用以下标签：

- **已实现**：主线存在代码，且存在 committed tests；
- **文档规则**：当前活动文档要求，但没有运行时强制；
- **显式边界**：实现或 Skill 明确声明不负责；
- **已证实缺陷**：实现与现行规则冲突，或存在可复现的错误路径；
- **集成缺口**：单个工具按设计工作，但没有覆盖真实执行链；
- **计划未落地**：已经有 issue/依赖计划，但主线尚无实现；
- **待验证风险**：证据表明值得验证，但当前不应直接变成阻塞规则。

## 3. 当前框架的分层结构

当前实际结构可以分成五层：

| 层 | 当前资产 | 已经证明的能力 | 没有证明的能力 |
| --- | --- | --- | --- |
| 治理层 | `AGENTS.md`、四个角色文件、documentation governance | 角色职责、所有权、独立测试、旧版 Reviewer 时序、文档边界 | Owner 新确认的双 lane/Candidate 0+3/terminal Reviewer/accepted-Candidate PR topology；运行时身份认证、文件访问隔离、角色输出结构化 |
| 静态合同层 | `workflow-contract.json`、`workflow_gate.py` | 封闭字段/枚举、快照一致性、部分 Human/Test/Candidate 绑定、finding-disposition 形状 | 合法状态历史、真实 Git/GitHub 对象、实际 role permission、Candidate direct union |
| 机械执行守卫 | `handoff_guard.py`（#88） | cwd/HEAD/Base/contract/argv/timeout/digest 连续性 | 统一角色交接文件、业务语义、文件洁净度、角色能力 |
| 接口包守卫 | `interface_handoff_check.py`（#90） | packet 封闭形状、安全路径、接口种类、authority/receipt 摘要形状 | 行为语义、错误 precedence、authority/receipt 真值、Worker 是否只读批准输入 |
| 外部操作层 | GitHub Connector/CLI、Codex heartbeat、subagent tool、人工 Git 命令 | 历史上完成过 Gate polling、评论证据、worktree、Candidate/PR/merge | 仓库内可重放的 executor、幂等状态、恢复、统一事件账本 |

结论：主线拥有“验收面”和两个窄“执行面”组件，但控制面之间尚未闭环。

## 4. 已落地功能与规则清单

### 4.1 静态工作流合同与验收快照

`agent-discipline/workflow-contract.json` 当前为 version 1，定义：

- issue classes：`M/B/W/T/D/N/I`；
- 9 个 impact flags；
- 12 阶段 strict route；
- 7 个 checkpoints；
- `active/blocked/stopped`；
- `PASS/FAIL/BLOCKED`；
- `F0..F4`；
- 6 个 dispositions；
- `P0-01..P0-18`；
- Candidate attempt 范围 `1..3`；
- workflow record、嵌套 evidence object 和 lane manifest 的封闭字段；
- Orchestrator、Explorer、Worker、Tester、Reviewer、Human 的权限词表。

`workflow_gate.py` 已实现：

- 调用者提供的合同解析对象必须等于 `contract_path` 的解析对象；record/lane 的
  contract blob identity 另按规范化 Git-blob SHA 校验；
- record 顶层和嵌套对象必须是封闭字段集合；
- contract version/blob、Base/Test/Implementation/Candidate SHA 的格式和
  声明关系检查；
- classification、route、checkpoint、status 和 preflight 声明的一致性；
- Human Review 1 的 actor、完整 Test SHA、精确 `/approve-test <sha>`、
  未编辑/未删除和 issue-comment URL 形状；
- Candidate 声明的 Test/Implementation parent identity；
- Tester PASS 后才允许 Reviewer PASS；
- draft PR、final review 与同一 Candidate 的声明绑定；
- finding class 与 disposition 的静态矩阵；
- Test/Implementation lane manifest 的同 Base、不同 lane、完整 requirement ID；
- final bootstrap residue clearance 的十个固定计数。

它明确是 **thin evidence gate, not a workflow engine**。它校验一个调用者提供的
快照，不接收 previous state 和 event，不推进 route，也不修改仓库。

还必须区分“代码确实这样实现”与“今后应该继续这样做”。当前合同的 strict
route 把 `human_review_1` 放在 `implement` 之前，`candidate_attempt` 只允许
`1..3`，并把 Reviewer PASS 约束在 Tester PASS 之后。这些是当前机器真值，但已
被 Owner 的新流程定义取代，属于待迁移的 legacy semantics，不能再被当成设计
依据。迁移必须保留旧记录可解释性，同时让新记录明确表达 Candidate 0、三次
Worker correction 和 success/failure 两种 terminal review。

### 4.2 角色治理

当前文档已清晰规定：

- **Orchestrator**：解释目标、选择权威 spec/plan/test/fixture、拆解任务、
  交接、监控、分类、集成证据、保护架构和验收 Loop；
- **Explorer**：只读获取不可推断事实，区分 verified/inferred/unknown；
- **Worker**：只读批准合同，不读 owner Test，TDD 实现和 generality tests；
- **Tester**：拥有 owner functional gate，Candidate 只读，运行确定性、S32DS、
  真黑盒 E2E 和 KPI；
- **Reviewer**：当前文档只允许在 Candidate Tester PASS 后进行非测试审查，且
  唯一写入是 append-only lessons log；Owner 新规则要求在成功或三次修正耗尽后
  恰好审查一次，当前 task 的 lesson 只能留在 review evidence/off-main lane；
- **Human**：批准 Test、提供 blocker 输入、最终审核和 merge。

这些规则在角色 Markdown 和平台生成配置中存在，但大部分仍属于 policy
isolation，不是可证明的 capability isolation；其中 Gate/Reviewer/lesson 时序还
与 Owner 新规则发生实质冲突，必须先修文档和机器合同，不能只改 Orchestrator
prompt。

### 4.3 #88 最小交接执行守卫

`handoff_guard.py` 提供：

```text
prepare
check-handoff
run
```

执行 manifest 固化：

- schema version；
- role 字符串；
- canonical git top-level；
- Base SHA、lane/HEAD SHA；
- contract path 和 contract blob SHA；
- exact argv；
- timeout。

它可以在 child 启动前拒绝：

- wrong cwd / wrong Git top-level；
- wrong HEAD / stale lane；
- Base 不是 commit 或不是 lane ancestor；
- contract bytes 已漂移；
- manifest/receipt/event path alias、hardlink alias、Windows trailing-dot alias；
- duplicate JSON keys、额外字段、malformed field；
- lane 内伪造 Git executable；
- stale/rewritten manifest digest。

`run` 使用 `shell=False`、固定 cwd 和 timeout，保留 child exit code；receipt 原子
替换，event JSONL 追加写。

### 4.4 #90 Test owner → isolated Worker 接口包检查器

`interface_handoff_check.py` 已定义并验证：

- packet identity：issue、Base、contract blob、approved Test、consumer role；
- required interface kinds；
- Python seam：path/symbol/signature；
- CLI seam：path/argv/stdin/stdout/stderr/exit codes；
- JSON seam：path/top-level type/required keys；
- authority kind/id/SHA-256；
- reference prevalidation receipt SHA-256 + `PASS`；
- forbidden sources 精确为 owner Test source/literals；
- `unresolved == []`；
- raw packet SHA-256、strict UTF-8/JSON、duplicate keys、路径安全和封闭字段。

Skill 要求通过 #88 固定 exact checker argv；guard 与 checker 同时 PASS 才允许
dispatch Worker。

### 4.5 Agent 环境初始化子系统

初始化 Skill 已经实现：

- GUI collector：选择 Codex/Claude/OpenCode、update/reset、S32DS/RTD 路径、
  local/online Skill；
- deterministic deployer：生成各平台角色文件、permissions/sandbox、Skills
  symlink/junction、dependency cache、prevalidate-before-mutation、atomic write、
  reset/update 和 post-deploy verification；
- platform contract 和初始化测试。

其当前合同是 GUI-first；fresh/missing/stale 环境需要初始化。自动化 Loop 的
headless verify/hydration 例外尚未进入主线，因此 derived worktree 丢失 ignored/
generated agent directories 时会与“automation 不使用 GUI”的运行原则冲突。
该问题已作为 #92 记录，当前不应阻塞 #85 的功能交付，但应保持为计划缺口。

### 4.6 产品 release 工具与 CI

仓库另有 deterministic release manifest 和安全 deployer，并在 CI 中运行
manifest check、全 pytest、outside-repo deploy smoke 和 Windows symlink lane。
但 release manifest、workflow lane manifest、#88 execution manifest 是三个
不同 schema，当前没有统一生成器或 provenance 链。

### 4.7 未在仓库落地的运行能力

以下能力目前不存在于 `master`：

- `previous record + event -> next record` transition engine；
- closed event schema 和可重放 history；
- event duplicate/stale/order/precedence 的统一真值；
- Candidate assembler/verifier；
- GitHub Gate polling、heartbeat/backoff、评论真值验证和幂等 evidence writer；
- closed structured role-input/role-report artifact family and guarded delivery；
- workflow recovery/resume；
- authoritative attempt epoch ledger；
- route executor；
- Agent 动态估时、被动进度观测、显式 `CONTINUE/CONTACT/INTERVENE/TERMINATE`
  决策和可恢复 interruption 记录；
- 跨 Codex/OpenCode/其他 runner 的统一 harness adapter，以及 Agent 生命周期与
  transport/MCP/command timeout 的正交建模；
- GUI-free derived-checkout hydration。

对应计划主要分布在 #59、#79、#80、#81、#85、#86、#87、#92、#93。

2026-09-06 追加的能力边界：三级测试的独立路由、Reviewer→PR 的 KPI 建单交接、
单向 KPI Issue、根目录 `kpi/` JSON 结果与美观 Dashboard 均尚未实现，分别由
#100/#101/#102 跟踪；不得把下文目标设计误读为现有执行能力。

## 5. 当前角色交付接口审阅

### 5.1 当前逐边界数据流

当前活动合同表达的是以下旧顺序：

```text
Orchestrator → Explorer/Test → Human Gate 1 → fresh Worker
→ Candidate attempt 1..3 → Tester PASS → Reviewer → lesson-child merge
```

其逐边界交付现状如下：

| 边界 | 当前交付物 | 已机器验证 | 仍依赖自然语言或人工 |
| --- | --- | --- | --- |
| Orchestrator → Explorer | prompt、source scope | 几乎无 | 事实边界、unknown、时限、输出格式 |
| Explorer → Test owner | prose facts/sources | 几乎无 | trace 完整性、是否遗漏/误加需求 |
| Test owner → Human Gate 1 | Test SHA、issue packet、reference claim | record/packet 的声明形状 | GitHub 实时真值、Test scope、语义合同充分性 |
| Human Gate 1 → Worker | approval、#90 packet、payload、worktree | #88 机械身份；#90 形状/digest | 行为语义、precedence、side effect、effective agent context |
| Worker → Candidate | Implementation SHA、generality、manifest | manifest 的少量字段 | changed paths、ownership、blob set、真实测试证据 |
| Candidate → Tester | Candidate SHA、prompt | record 中声明的 SHA | Git 对象/parents/tree、freshness、实际命令环境 |
| Tester → Reviewer | PASS/FAIL prose、KPI prose | 非空 evidence、同 Candidate 声明 | 结构化命令/exit/node/environment/raw digest |
| Reviewer → Human Gate 2 | Candidate、PR、packet、lesson | Candidate/URL 的部分声明 | exact decision、author、unedited、真实 PR 状态 |
| Human Gate 2 → merge | approval、Candidate、lesson child | 无 executor | ordered lineage、remote/PR/issue/post-merge 状态 |

Owner 本轮确认的目标交付链应替换为：

```text
                          ┌─ Tester builds Test lane + full-chain prevalidation
Governor G + Contract K ─┤       └─ T ready → Human Gate 1 → exact T + K frozen
                          └─ Worker builds Implementation lane + generality → I0 ready

Human-approved T + matching I0 ready → assemble Candidate 0 → Tester
    FAIL → sanitize → same Worker correction 1 → Candidate 1
    FAIL → sanitize → same Worker correction 2 → Candidate 2
    FAIL → sanitize → same Worker correction 3 → Candidate 3
    PASS at any Candidate ─┐
    FAIL at Candidate 3 ──┴→ terminal Reviewer exactly once
                            ├─ success: PR exact accepted Ck=[T,Ik] → Human final approval
                            └─ failure: issue terminal record, no PR
```

相应的目标接口是：

| 边界 | 必须交付 | 不得交付/不得发生 |
| --- | --- | --- |
| Orchestrator → Tester lane | `K` + Test Launch Envelope：exact Governor、公开 spec/authority、Test ownership、预验证拓扑、scope/non-goals | Implementation branch 内容不能成为 Test 设计依据；prompt 承载任务语义 |
| Orchestrator → Worker lane | 同一 `K` + Worker Launch Envelope：exact Governor、Implementation ownership、generality 要求 | owner Test source、case、literal、reference mutant、Test worktree；prompt 承载任务语义 |
| Tester → Orchestrator（Gate 构建完成） | Test Gate Ready Report：Test tip、manifest、RED/reference/known-bad/full-chain receipts、公开合同缺口 | 尚未完成预验证就发布 Human Gate；另造 “Test author” 角色 |
| Worker → Orchestrator（可早于或晚于 Gate 1） | Implementation Report：tip `I0`、manifest、generality receipts、deviations/unknowns、与 `G/K` 的一致性 | 因为不知道 owner Test 而猜测其 literals；等待 Human Gate 才开始或结束独立实现 |
| Orchestrator → Human Gate 1 | 唯一审批对象 exact Test；Task Contract Epoch、Test Impact Set、prevalidation 和公开接口摘要作为其绑定身份/支持证据 | 等待或审核 Implementation；把 G/K/Impact/receipt 拆成额外审批对象；把 Worker 状态写成 Human Test 审批对象 |
| Human Gate 1 → Orchestrator | 对 exact Test 的批准或 Test change request；同时记录该 Test 所绑定的 G/K/Impact/prevalidation identity | 批准后再修改 Test；复用旧 Test approval 到新 SHA；把支持证据误写成独立 Human approval |
| Orchestrator → Tester | Candidate Test Envelope：`C0=[T,I0]`，以后为 `Ck=[T,Ik]`；exact manifests/lineage | 让 Tester 修改 Implementation 或 frozen Test Gate |
| Tester → Orchestrator（PASS/FAIL） | Confidential Tester Report：完整结果、Implementation 首个偏差、生产代码根因/置信度、责任分类 | 直接把 owner Test source/literal 当修复提示交给 Worker；Tester 修改 Implementation |
| Orchestrator → same Worker | 经完整性与泄漏审查的 Worker Correction Envelope；上一 Implementation tip | fresh restart；暴露 test case；只给症状不给根因；把 correction 当新 Test epoch |
| Worker correction | `Ik` 必须是 `I(k-1)` 的增量后继；最多 `k=1..3` | sibling-from-Governor 重建；无理由丢弃已完成实现 |
| Orchestrator → terminal Reviewer | Reviewer Launch Envelope：成功终态或 Candidate 3 失败终态的完整证据 | 每次 Attempt 都调用 Reviewer；Reviewer 触发新返工 |
| Reviewer → Orchestrator/Human | Reviewer Report：恰好一次终态 review；当前 task 的 lesson/evidence 留在 review lane/comment | 用 lesson child 替换已验收 Candidate 作为 PR head，或将 lesson 作为 merge-only edit 注入 Candidate |
| success finalization | PR head 为 exact accepted `Ck=[T,Ik]`；Human final approval 后，Test 与 Implementation 一起通过该 PR 合入 | 改为 Implementation-only PR、单独推送 Test，或用未验收 Candidate/lesson child 替换获批 head |
| failure finalization | issue 记录 final Tester + Reviewer 结果、剩余缺陷和可复用 Implementation tip | 建立声称成功的产品 PR；删除失败实现历史 |

### 5.2 当前交付合同的核心断点

当前存在两条并行但没有真正相交的通道：

```text
机器通道：#88 manifest + #90 packet + digests
自然语言通道：Orchestrator prompt + issue comments + subagent response
```

问题不在于没有哈希实际 prompt。目标模型不把 prompt 作为任务语义或 acceptance
evidence：prompt 只指向 lane-local 输入/输出文件、要求加载 Agent 规则、提醒角色边界，
并可携带不改变任务语义的运行上下文。任务目标、接口、判定规则、可见性和交付格式
全部位于结构化文件；subagent 的聊天 response 也只是通知，角色返回的结构化报告才是
权威结果。

#85 本地 handoff evidence 进一步证明当前集成方式：大量 manifest 固定的 argv
只是 `git rev-parse HEAD` 或 `interface_handoff_check.py validate ...`。它们证明
执行过身份探针/checker，却没有形成 Test/Worker Launch Envelope、Test Gate Ready
Report、Implementation Report、Candidate Test Envelope、Confidential Tester Report、
Worker Correction Envelope、Reviewer Launch/Report 和 Terminal Record 这一条封闭
交付链。

相应缺口必须按三种不同机制处理，不能再次混成一个 executor：

- **lane continuity**：Orchestrator 固定复用同一个 Worker、worktree 和 branch；每份
  Implementation Report 回显前一 tip 和 correction index，守卫只需用 Git ancestry
  做低成本确认；
- **failure disclosure**：confidential Tester Forensics Report 与发给 Worker 的
  Correction Envelope 之间使用结构化字段和 digest 引用；守卫拒绝错误可见性和
  Test-confidential 成员，Orchestrator 作为受信任 LLM 负责判断自然语言是否仍泄漏
  hidden Test 或丢失可行动根因；
- **artifact disposition**：作为 workflow state/finalization 规则直接写入 Reviewer
  Report 和 Terminal Record；不再为它另建大型子系统。

结构化文件不包含通用 `description_session`。任务相关自然语言若无法映射到合法
结构化字段，就必须补充 `K` schema/authority 或走 `K` revision；不得在自由文本中
暗中增加需求。只有 locator、Agent 规则提醒和非任务运行上下文可留在启动 prompt。
这一边界保留 LLM 的自主推理能力，同时避免 prompt 成为第二份任务合同。

没有上述交付链时，Orchestrator 很容易把“旧 acceptance evidence 不可复用”错误扩大
成“旧 source/Implementation 不可复用”，或者为了保持 Candidate direct-union 外形
而把增量修复重新压成 Governor 的 sibling commit。新规则明确：stale evidence 只要求
重建 evidence；除非 Implementation 被 Test 污染、与新 `G/K` 不兼容或 Human 明确要求
放弃，否则同一 Worker 必须在原 worktree/branch 上继续增量修正。

### 5.3 #90 的正确定位

#90 没有失效；它按设计完成了“形状完整性”职责。Skill 明确声明它：

> validates only completeness, closed shape, immutable identities, and digest
> continuity. It has no semantic authority.

因此不能通过向 #90 不断添加隐藏行为规则来补救 #85。#93 将保留 #88/#90 已证明的
能力，通过兼容适配器把它们收敛为一个参数化交接守卫。该守卫只负责：

1. 结构化交接文件的完整性和直接前驱/局部交接顺序；
2. 成员、类型、枚举、路径、SHA、digest、角色可见性和适用 Git identity/ancestry 的
   合法性。

业务语义正确性、LLM 推理和全局 `previous state + event -> next state` 不属于守卫；
后者继续由 #85 实现。新增文件种类时，只增加封闭 schema、合法边和 known-good/bad
fixture，不再创建一个新的独立 checker。

## 6. 关键 Issue 的纵向复盘

### 6.1 分析口径

本节不按“最后是否合并”简单评判成功或失败，而对每个关键 Issue 使用同一组
问题：

1. 最初要解决什么，Orchestrator 当时默认了什么前提；
2. Test、Implementation、Candidate 或执行环境分别暴露了什么直接失败；
3. 直接失败背后的合同、测试边界、执行面或治理缺陷是什么；
4. 最终是通过什么**改变证明对象或缩小状态空间**才成功，而不是把最后一次
   PASS 错写成“多试几次就好了”；
5. 合并只永久解决了什么，明确没有解决什么；
6. 哪条经验已经进入当前 `master` 的代码、测试或活动 lessons，哪条仍只存在于
   历史评论或未合并分支。

主分析对象是已经合并的 #78、#82、#83、#88、#90。#85 尚未成功合并，本节只把
它作为反证：用于检查前述成功项的残余边界是否被误当成完整执行框架。

#### 6.1.1 Owner 时间线与阶段性决策

单看最终合并 commit 会掩盖真正的决策转折。Owner 对一个多月执行史的重建如下，
本次 Git/issue 取证与其一致：

| 顺序 | 事件 | 当时暴露的问题 | 改变收敛方式的决策 |
| --- | --- | --- | --- |
| 1 | #57 深度 brainstorming，定义 Agent Loop 总方向和后续包 | 目标覆盖治理、验收、执行、Human、恢复等完整系统 | 形成 umbrella，但尚无可依赖的执行基座 |
| 2 | #78 按完整方案开工，累计超过百次历史 commit 仍不收敛 | 测试范围无重点扩张；在基座不存在时仍试图一次证明完整 Loop；未及时采用 bootstrap | Owner 停止执行，要求优先级分层，只交付最小 P0，并用 bootstrap 分阶段自举 |
| 3 | #78 minimal P0 最终成功 | 完整执行器被明确后置 | 获得当前最小验收 Loop；上一阶段 Implementation 连续成为下一阶段 Governor |
| 4 | 首轮 #83 多次失败 | pytest/Windows/路径/交接前提逐层暴露；Human Gate 前没有端到端执行预演 | 第二次反省：先补最小 handover guard，创建 P0 #88 |
| 5 | #88 运行三个历史 Candidate（当时标作 attempt 1–3）后成功 | commit/ancestry/raw bytes/guard 顺序等机械身份错误；旧账本把初始 Candidate 误算成一次修正 | 获得最小机械交接守卫；按新模型相当于 `C0→C1→C2`，使用两次 correction，未触及 `C3` |
| 6 | #82 运行两个历史 Candidate 后成功 | Test seam 与 Windows publication/ownership 语义混杂 | 冻结 purpose-specific public seam，增量修正 Implementation；按新模型不应称为“两次 correction” |
| 7 | 回到 #83，一次 Candidate series 成功 | 前置依赖和全链 prevalidation 已齐 | 证明“先修依赖 + Gate 前真实 vertical slice”能显著缩短收敛 |
| 8 | 首轮 #85 运行三个历史 Candidate 后被冻结为“预算耗尽” | 执行守卫不能证明接口包完整；不同角色交接仍靠 prose；旧计数实际只表达 `C0+C1+C2` | 第三次反省：创建 P0.1 #90；同时确认按新模型仍应有 correction 3 / `C3`，历史冻结提前了一步 |
| 9 | #90 两次历史 Candidate presentation 后成功 | 第一版 owner Test 对诊断词做 lexical overconstraint | 保留同一 Implementation，只替换 Test；这是 Test series replacement，不消耗 Worker correction |
| 10 | 第二轮 #85 再运行三个历史 Candidate 后被错误宣告“修正机会耗尽” | shape/digest 完整不等于 semantic sufficiency；旧账本再次把初始 Candidate 算作 correction | 本次停止：重审整个框架；按新模型 R2 只形成 `C0/C1/C2`，第三次 correction 与 `C3` 从未执行 |

表中的历史 `attempt 1/3..3/3` 实际标记了三个 Candidate presentation，而不是三次
Worker correction。按第 9 节唯一术语，初始 `Candidate 0` 不消耗机会，三次 Worker
correction 分别产生 `Candidate 1..3`；因此历史只有 A1/A2/A3 时，应映射为
`C0/C1/C2`，不能宣告 correction budget exhausted。#85 R1/R2 都因此被提前终止，
真正的第三次 correction / `C3` 没有发生。

### 6.2 #78：从“完整工作流一次建成”退回可证明的最小 P0

#### 6.2.1 初始目标与错误前提

#78 试图一次建立 Agent Loop 的合同、状态、证据、角色权限、计数、CLI、Human
Gate 和文档规则。它隐含了三个后来被证明不成立的前提：

- 可以在同一轮中同时稳定 schema、transition semantics 和 acceptance tests；
- 终态 snapshot 只要字段齐全，就足以证明到达终态的生命周期合法；
- 由同一轮 Test/Implementation 逐步补齐规则，最终自然会收敛到一个 canonical
  invariant，而不需要先冻结语义边界。

#### 6.2.2 失败是怎样逐层发生的

| 阶段 | 可核验结果 | 当时暴露的直接问题 |
| --- | --- | --- |
| 初始 Candidate | 67 PASS / 24 FAIL | contract schema 与 validator 不一致；仍保留过时的 OpenCode 默认假设。 |
| 前两轮 rework | 81 PASS / 14 FAIL，随后 95 PASS / 1 FAIL | `request_changes_command`、轻量路径和 Gate 1 绑定、诊断术语仍不一致。 |
| TC 阶段中段 | Tester 一度全绿，Reviewer 仍拒绝 | owner Test 证明了终态字段，却未证明完整 lifecycle、T/W/C lineage、Human provenance、路由与 correction cap、CLI 异常路径。 |
| TC10–TC15 | 多次测试绿、Review 红；最终 correction/exception 预算耗尽 | 跨状态字段可任意突变、Candidate 可绕过 Worker/rework cap、Human 只有抽象 actor 无授权账号绑定、KPI 无可执行转移、schema 未递归封闭、final review polling 和 change-request evidence 不完整。 |
| Workflow V2 clean bootstrap | 196 PASS / 635 FAIL | 不是单个实现回归，而是新的“大一统”语义设计与既有合同、CLI、provenance 全面不相容。 |
| Minimal P0 stages 2–5 | 每轮只剩 2–4 个 blocker，但持续暴露新边界 | impact flag 顺序、F1 null viability、URL 类型、Category A 反向引用、issue-comment URL、bare prefix、空 URL delimiter、测试读取 review archive 等。 |
| Minimal P0 stage 6 | owner 18/18、generality 32/32、regression 50/50，Tester 与 Reviewer 均通过 | Candidate `31e913d` 被接受，最终集成 `3f24f6b`。 |

关键历史证据包括初始失败
[comment 5040067981](https://github.com/autoMBD/autombd-rtd-config/issues/78#issuecomment-5040067981)、
TC10 审阅失败
[comment 5082268000](https://github.com/autoMBD/autombd-rtd-config/issues/78#issuecomment-5082268000)、
V2 clean-bootstrap 崩溃
[comment 5149855264](https://github.com/autoMBD/autombd-rtd-config/issues/78#issuecomment-5149855264)
和最终批准
[comment 5232159305](https://github.com/autoMBD/autombd-rtd-config/issues/78#issuecomment-5232159305)。

#### 6.2.3 为什么前面的“修一个错、加一个测试”没有收敛

失败节点不断从 schema 移到 lifecycle，再移到 provenance、Human identity、KPI、
polling 和文档边界，说明当时不是在修一个稳定实现，而是在一边运行 Loop、一边
发明 Loop 的语义。Test、Implementation 和 Reviewer 看到的判定域也并未始终来自
同一个可执行 authority。每次局部修复都可能令某一层 green，却把未显式化的规则
推迟到下一层才暴露。

这也是典型的循环自证风险：当 owner Test 只断言当前实现已经提供的终态字段时，
它无法证明历史是可达的；当 Reviewer 后来补充生命周期不变量时，又会推翻已经
green 的 Candidate。增加断言数量不能代替先固定状态模型和判定 precedence。

#### 6.2.4 最后为什么成功

真正的转折不是 TC15 之后再增加一轮，而是承认完整 V2 无法在当前基座上可靠
自举，重新定义交付目标为**静态最小 P0 evidence gate**：

- 放弃在本 Issue 内完成 executor、完整 transition history 和所有 provenance；
- 每个 bootstrap stage 只冻结一个很小的合同增量；
- Test/Candidate acceptance evidence 每阶段重新建立，但**上一阶段的
  Implementation tip 直接成为下一阶段 Governor**，实现能力持续累积而不是重写；
- 用小规模 owner/generality/regression gates 验证明确的字段和错误域；
- Tester 负责功能判定，Reviewer 负责 Test 无法覆盖的边界；
- Human 对 exact Candidate 作最终批准。

从 `6cecde0f44f1ede2347c2c8a9238008bce59602e` 到最终 Candidate 之前的提交拓扑
证明了这一点：

| Bootstrap stage | 该阶段 Governor | Test tip | Implementation tip | Acceptance Candidate |
| --- | --- | --- | --- | --- |
| 1 | `6cecde0f` | `0d60fbb` | `d54ce313` | `8783607` |
| 2 | `d54ce313` | `86e2fbc` | `c1f86e8` | `55b6c9a` |
| 3 | `c1f86e8` | `58efb8c` | `02d5962` | `cb7b99b` |
| 4 | `02d5962` | `a4f671c` | `31cbc94` | `9dced42` |
| 5 | `31cbc94` | `23991d6` | `57373f5` | `1255dc8` |
| 6 | `57373f5` | `fe8cc87` | `c7dc051` | `31e913d` |

最终 ancestry 因而包含连续 Implementation 链：

```text
6cecde0f → d54ce313 → c1f86e8 → 02d5962 → 31cbc94 → 57373f5
          └──────────────── cumulative implementation ───────────────┘

stage 6: 57373f5 ─┬─ fe8cc87 (final Test)
                  └─ c7dc051 (final Implementation)
                       \ ordered merge Candidate 31e913d
```

Stage 1–5 的 Test 和 Candidate 没有进入最终 accepted ancestry；它们是阶段性证明。
Stage 1–5 的 Implementation 进展却全部通过父子链被保留。这正是“测试证据可作废、
已完成实现不应随之丢弃”的最强历史证据。这是当时的 staged-bootstrap 谱系事实，
不是排除最终 Test 的交付规则；最终 `31e913d` 本身仍包含 stage 6 的 Test 与
Implementation。今后的成功 PR 交付 accepted Candidate，不从它再剥离 Test。

因此成功的因果链是：

```text
语义重置
→ 交付目标缩小为静态最小 P0
→ 每阶段只冻结一个可审查增量，Implementation 连续继承
→ Test/Reviewer 各自证明明确边界
→ exact Candidate 获批并合入
```

不是：

```text
同一套完整设计重试足够多次
→ 自然成功
```

#### 6.2.5 永久成果与残余边界

#78 合并了当前 workflow contract、静态 gate 和基本治理，是后续工作的基座，不能
废弃。但它有意没有交付可靠执行器；transition engine、真实 evidence collection、
结构化角色交付、Candidate assembler 和 isolation verification 被留给 P1。

另有一条 bootstrap redesign 历史分支从 `0a70a8e9` 开始：`dfa643a7` 曾加入
`agent-workflow-design.md` 与 `agent-workflow-test-strategy.md`，后续 debt/clearance
记录继续细化 staged bootstrap，最终 `273331db` 又把这些 bootstrap-only design
evidence 清除。该分支本来就不是最终 `d1dc62c2...` 的 ancestor；包含 explicit
per-event mutation matrix、完整可达 pre-state 等精确规则的 `0cab60e4`、
`356921d7`、`b36cd510` 也不在当前 `master` ancestry。

这解释了为什么 #78 成功使用的 bootstrap 方法后来像是“丢失”了：实现成果进入了
主线，但可复用的操作协议被当作临时债务/设计证据清掉，没有提升为持久的
Category B playbook 或机器回放。问题不是 Agent 没有经历过，而是 Orchestrator
没有把已经证明有效的**过程知识**纳入 active trust root，后续又依赖会话记忆。

必须区分可继承与不可照搬的部分：

- **必须继承**：优先级分层、小 stage、保留累积实现、每阶段明确退出，以及阶段
  证据与实现资产分离；新任务由 Human 选择已验收合入后的 exact 基线，不能把历史
  “上一 Implementation tip 直接作为下一 Governor”推广成剥离测试的通用规则；
- **不得照搬**：用故意失败的 full-target owner Test 逐阶段发现需求、允许修改同一
  task 已经 Human-approved 的 Test、绕过 final approval/PR 单独推 Test，或把 lesson
  child 当作已验收 Candidate 合入。新版 governed bootstrap 的窄 work package 遵守
  Candidate 0+三次 correction，成功 PR 包含最终 Test+Implementation；当前人工
  Phase 0–3 则按 §9.2 审阅 exact 变更与所需测试，不自主运行这些步骤。

### 6.3 #82：先修正 Test seam，再定义 Windows 发布线性化与所有权

#### 6.3.1 为什么一个看似独立的 Windows 测试会阻塞后续工作

#82 的直接现象是 clean baseline 上 reparse/backup path-attack 测试失败；同一失败
也会出现在与它无关的 #83 Candidate 上。最初容易把它理解为“Candidate 新引入的
Windows 回归”，但 Base 与 Candidate 的字节和失败节点相同，说明它是前置基线
缺陷，而不是 #83 的实现缺陷。

进一步诊断发现，Windows 上保留 handle 且 `share_delete=False` 时，
`MoveFileExW` 仍可能移动打开的文件，而攻击用的后续 replace 可能因权限失败。
原测试把攻击注入到 wrapper 内部；一旦 setup 在 primitive 返回前抛错，helper
尚未进入已发布 phase，结果被归类为 `configure_backup_changed`。测试因此把
“攻击场景没有建立成功”与“事务在发布后如何分类”混在一起。

#### 6.3.2 失败与修正轨迹

| 阶段 | 发生了什么 | 暴露的缺陷 |
| --- | --- | --- |
| baseline 调查 | full suite 1 FAIL / 1595 PASS / 8 SKIP，Base 与工作分支相同 | 不能把所有 Candidate-scoped full-suite 失败都计入当前 Candidate。 |
| 初始注入 seam | 测试依赖 whole-platform/private adapter state | Test seam 太宽且与 Windows 实际权限、hook 时序耦合，不能稳定表达发布时点。 |
| frozen contract v2 | 明确 pre-publication 与 post-publication 的错误分类 | 首次把 namespace observable publication 作为线性化点，把 readable mismatch、unreadable/reparse/missing 分开。 |
| purpose-specific seam | 引入 `backup_install_absent_fn` / `install_fn` | primitive 只负责建立 namespace 状态并正常返回；helper 负责 phase、snapshot、classification 和 result，避免伪造 receipt/result。 |
| Test v3 | Governor RED 10/67/3，reference 77/3；多组 bypass/routing/forged-result/identity/path mutants | owner Test 开始证明公共 seam 和所有权，不再依赖具体平台攻击偶然成功。 |
| Candidate A1 | 仅一项 owner failure | 实现把 `adapter.inspect` 变成隐含必需 seam，违反“snapshot-only adapter 也可工作”。 |
| Candidate A2 | focused 96 PASS / 3 SKIP；Reviewer 通过；post-merge 99 PASS | Implementation `fa942273`、Candidate `616b7fc`、lesson/master `c896174` 成功合入。 |

关键合同冻结见
[comment 5284388354](https://github.com/autoMBD/autombd-rtd-config/issues/82#issuecomment-5284388354)
和
[comment 5284557238](https://github.com/autoMBD/autombd-rtd-config/issues/82#issuecomment-5284557238)；
最终结果见
[comment 5377572905](https://github.com/autoMBD/autombd-rtd-config/issues/82#issuecomment-5377572905)。

#### 6.3.3 最后为什么成功

#82 最终不是靠找到一种“在所有 Windows 主机都能稳定制造 reparse attack”的技巧
成功，而是把业务不变量从不可靠的攻击装置中抽离：

```text
平台攻击 setup
    ↓ 只用于证明/观察 namespace 状态
明确 publication linearization point
    ↓
helper 根据 phase + snapshot + ownership 做分类和回滚
```

同时，Candidate A1 的失败被正确用于收窄实现依赖：`inspect` 只能是 optional
defense-in-depth，不能成为公共合同暗门。A2 支持 snapshot-only adapter 后，Test
与 Implementation 才围绕同一个公开 seam 收敛。

full suite 当时仍有 51 个失败，但一次有界 Base comparison 证明这些失败在未改动
文件、节点和数量上与 Base 完全相同，因此被记录为 non-blocking，而不是盲目把
当前 Issue 扩展成清理整个基线。这是“完成优先、忠实记录”的正确实例：前提是
比较是精确、可复核且只用于与本变更无关的节点。

#### 6.3.4 永久成果与残余边界

#82 永久建立了 backup publication 的线性化、证据所有权、foreign evidence 保留和
late primitive failure 后的重新分类规则。它也证明 Test seam 必须是
purpose-specific、public、可由 minimal adapter 实现。

它没有解决一般 Windows capability discovery、pytest 生命周期或 Agent handoff；
这些后来由 #83、#88 等 Issue 分别处理。#82 的成功不能被概括成“允许 full suite
失败”，而应理解为“允许经过 exact Base comparison 证明无关的已知失败不阻塞当前
交付”。

### 6.4 #83：从逐层暴露 Windows/pytest 隐形前提，到 Human Gate 前完整链预验证

#### 6.4.1 初始目标为什么被不断放大

#83 原本只是 Windows 文件/目录 symlink capability 的确定性探测与 pytest gate。
但这条路径同时穿过 WinError 1314、目录 parent、pytest discovery/hook order、
creation 与 observation exception、capable/unavailable/unsupported 三类语义、CI
lane、Candidate-local temp 和 Windows path length。早期每一版 Test 只验证了其中
一层，于是 Human approval 后才由下一层暴露隐藏前提。

#### 6.4.2 主要失败轨迹

| 阶段 | 直接现象 | 实际问题归属 |
| --- | --- | --- |
| Test v1–v3 | Test SHA 多次替换，旧批准很快失效 | Test contract 没有一次冻结 callable 方向、目录 parent、WinError1314 和完整 pytest lifecycle。 |
| recovery contract v1–v3 | 逐步补充 preflight read boundary、disposable discovery adapter 和 procedural contract | Orchestrator 的交接文字先于公开 seam 成熟；每次只补上一层新发现。 |
| Test v7 prevalidation | full-chain 才发现命令规范、existing environment dependency 和 loader/hook 问题 | 早期“单元 reference green”不等于真实 pytest discovery + execution green。 |
| Candidate A1/A2 | static rejection：diff/whitespace、marker contract 等 | Candidate 还未进入功能验收，静态规则已与 owner intent 不一致或实现不洁净。 |
| Candidate A3 执行 | 先 wrong cwd，再缺失 Candidate-local `tests/.tmp` parent，再遇到 260-character path | 这是 PROCESS/ENVIRONMENT F0，不是同一个 Implementation defect；但说明执行前提未由 guard 一次准备完整。 |
| A3 后续 | 被 #82 baseline defect 阻塞 | 如果继续在 #83 内修 #82，会破坏 ownership；因此正确建立依赖并暂停。 |
| Test v8 / Candidate A1 | owner 12、Worker generality 19；unavailable optional、require fail-closed、capable Windows 六项均按合同通过；full 1644 PASS / 30 SKIP / 19 subtests | Test、Worker、real loader/lifecycle 和环境前提首次在 Human Gate 前形成同一条可执行链。 |

恢复合同的演进可从
[comment 5256000575](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5256000575)、
[comment 5256193169](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5256193169)
和
[comment 5256304013](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5256304013)
核验；v7 被 #82 阻塞见
[comment 5284311813](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5284311813)；
v8 最终接受见
[comment 5378492042](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5378492042)。

#### 6.4.3 最后为什么成功

最后的成功不是因为 capability probe 代码突然变简单，而是因为 Test Gate 的进入
条件改变了：在 Human review 前，先从 clean absent-parent 状态跑过真实 pytest
discovery vertical slice，覆盖 marker 注册、hook 调用、session cache、file +
directory probe、owned cleanup、optional skip、require fail-closed 和 capable lane。

同时，测试明确区分：

- link creation 自身抛出的 `NotImplementedError`；
- exact WinError 1314 表示 capability unavailable；
- creation 成功后 observation/cleanup 失败属于功能错误；
- capable 环境不得用 skip 掩盖 assertion failure。

依赖关系也终于被诚实处理：#82 是 Base defect，先修 #82；#88 是执行交接前置，
先合 #88；再从新 Governor 重建 #83 v8。这样避免把无关问题塞进 #83，却也没有
把它们无限期“留待以后”。

#### 6.4.4 永久成果与残余边界

#83 合并的 LL-045 固化了 clean absent-parent full-chain prevalidation、creation 与
observation 分离以及 Test marker 的 Candidate-only review 边界。它解决的是
Windows symlink capability 这一具体先决条件。

它没有证明任意 Test/Implementation handoff 都语义充分，也没有建立通用执行器。
它证明：

```text
owner Test + reference + real loader/lifecycle + 真实环境路径可以端到端运行
```

它不自动证明：

```text
一个未读 owner Test 的独立 Worker，只凭公开 handoff 就能唯一推导同一行为
```

这个差异后来在 #85 被直接验证。

### 6.5 #88：用极小、可人工审查的守卫封死机械交接错误

#### 6.5.1 自举策略与边界

#88 没有尝试在尚不可靠的 Loop 内再建一个完整执行框架。它采用两阶段自举：

1. 人深度参与，先在 Loop 外审核一个很小的 v0.1 guard 源文件和摘要；
2. 再把 byte-identical artifact 与 owner tests 合入现有 P0，证明集成后行为不变。

目标只覆盖已反复发生的机械错误：wrong cwd、wrong HEAD、wrong/non-commit Base、
contract drift、stale/rewritten manifest、argv/timeout drift。签名、锁、并发、cleanliness、
完整 receipt architecture、semantic classifier 和 `loopctl` 都被明确排除。

#### 6.5.2 失败轨迹与每次获得的新事实

| 阶段 | 直接结果 | 新增的确定性事实 |
| --- | --- | --- |
| 外部 v0.1 / Test v1 | 20 个 owner nodes；Governor RED、reference green | byte-identical integration 可行，但初始身份模型仍只把 Base 当作 SHA-looking string。 |
| Candidate A1/A2 | stale/替换 | working-tree source hash 与 committed blob 可能因 line-ending/filter 不同；可信源必须是 committed blob。 |
| replacement Test | 23 nodes + 19 subcases | Base 必须是 Git commit 且为 HEAD ancestor；JSON 必须拒绝 duplicate keys；raw manifest SHA 必须绑定 prepare receipt。 |
| Candidate A3 | owner 23、generality 58、adjacent 18、combined 99/19；dogfood 通过 | Implementation `10ee5c0`、Candidate `a6429a6`、lesson/master `091da706` 成功。 |
| post-merge | 99 PASS / 19 subtests | 第一次 sandbox run 因 `tests/.tmp` ACL 无效；host clean rerun 通过，作为 PROCESS/F0 记录。 |

replacement packet 见
[comment 5364333974](https://github.com/autoMBD/autombd-rtd-config/issues/88#issuecomment-5364333974)，
最终 Gate 见
[comment 5364990818](https://github.com/autoMBD/autombd-rtd-config/issues/88#issuecomment-5364990818)，
合并验收见
[comment 5365857953](https://github.com/autoMBD/autombd-rtd-config/issues/88#issuecomment-5365857953)。

#### 6.5.3 最后为什么成功

#88 是本批历史中最接近成功自举样板的 Issue，原因不是零失败，而是每次失败都只
增加一个已被反例证明的机械不变量：

- SHA-like string → typed Git commit + ancestry；
- working-file digest → committed blob/raw manifest digest；
- decoded JSON equivalence → duplicate-free JSON + raw bytes binding；
- 手工假设 cwd/HEAD → prepare/check/run 前的 fail-closed identity check。

每个脚本和测试域仍小到可以人工审阅，且合入 artifact 必须与已批准外部版本
byte-identical。没有借机加入状态机或业务语义，因此状态空间受控。

#### 6.5.4 永久成果与当前已证实残余

#88 已经有效挡住 wrong cwd、wrong HEAD、invalid Base、contract drift 和 stale
manifest，必须保留并作为后续 handoff 的强制机械前置。

本次代码审阅同时确认一个未在 #88 验收范围内的**已证实缺陷**：Skill 要求
`prepare -> check-handoff -> run`，但 `run` 只验证 prior receipt 的相同
`manifest_sha256`，没有要求 prior operation=`check-handoff`、outcome=`CHECKED`
且 exit code=0。现有测试中甚至有 `prepare -> run` 直接启动 child 的路径。因此：

```text
prepare PASS
→ 跳过 check-handoff，或 check-handoff REJECTED 后恢复 identity
→ run 仍可能启动 child
```

这不是推翻 #88；它说明 #88 当时成功交付的是 identity/manifest guard，不是完整
顺序执行器。最小修复应只绑定直接 prior successful CHECKED receipt 并增加 replay
regression，不应借机扩展成整个 workflow engine。

此外，`role` 在 standalone guard 中只是通用小写 token，generality tests 允许
`explorer-probe`、`review-auditor`。如果 governed workflow 要求 canonical role，
应由其 wrapper/manifest producer 做映射；未经批准不能把 #88 的通用合同悄悄
收窄。

### 6.6 #90：成功交付“接口包形状完整性”，但没有交付语义充分性

#### 6.6.1 为什么需要 #90

#85 第一轮暴露出 Test owner 与隔离 Worker 之间没有机器可验的交接包。#90 因此
被定义为 P0.1：冻结 packet raw bytes、identity 字段、seam shape，以及 authority /
reference receipt digest 的连续性。它明确不是 workflow transition engine，也不
解释 authority 的业务语义。

#### 6.6.2 失败与修正轨迹

| 阶段 | 直接结果 | 正确归属与处理 |
| --- | --- | --- |
| Test v1 pre-Gate | Test 从 1081 行压到 598 行；checker launch 从约 525 行压到 283 行；修复 `core.autocrlf` 造成的 bytes 差异 | 这些在 Human Gate 前发现，属于 Test/process F0；按本版术语不消耗 Worker correction。 |
| Gate v1 | reference owner 18 PASS / 149 subtests；#88 chain 与 full suite 通过 | 首次机器冻结 packet 的 closed shape 和 digest continuity。 |
| Candidate A1 | owner 17 PASS / 1 FAIL / 145 subtests | Implementation 的诊断写 `SHA-256`，Test 却只接受 `digest` 或连续 `sha256`；这是 owner Test lexical overconstraint，不是产品合同失败。 |
| replacement Test | 只增加 `sha-256` lexical alternative；Implementation `d0a1274` 原样保留 | 正确只返工 Test owner，不重写已经满足公共语义的 Implementation。 |
| 历史标记的 Candidate A1 | owner 18/149、generality 20/80、#88 regression 81/19、full 1682 PASS / 30 SKIP / 248 subtests；Reviewer 无 finding | Candidate `e72befe`、lesson/master `9331d66` 合并。 |
| acceptance F0 | 前序 test stages 在 hash 验证后删除 ignored frozen fixtures | checker fail-closed；恢复 exact canonical bytes 后重跑通过。删除源忠实记录为 unresolved/non-blocking，未谎报 Implementation correction。 |

Test v1 见
[comment 5394632956](https://github.com/autoMBD/autombd-rtd-config/issues/90#issuecomment-5394632956)，
A1 分类见
[comment 5396542936](https://github.com/autoMBD/autombd-rtd-config/issues/90#issuecomment-5396542936)，
replacement packet 见
[comment 5412555131](https://github.com/autoMBD/autombd-rtd-config/issues/90#issuecomment-5412555131)，
最终验收见
[comment 5413955608](https://github.com/autoMBD/autombd-rtd-config/issues/90#issuecomment-5413955608)。

#### 6.6.3 最后为什么成功

#90 成功的关键是坚持职责窄化和 owner-aware routing：

- Test 约束了公共诊断类别，却一度误约束标点拼写；一旦证明是 Test 错，就只修
  Test，不把 retained Implementation 重做一遍；
- replacement packet 后重新跑完整 reference/full-chain 预验证，不复用旧 acceptance
  evidence；
- exact packet、Implementation 和 Candidate identity 继续冻结；
- ignored canonical evidence 被删除后，checker 正确拒绝；恢复原 bytes 后才继续，
  没有放宽 checker 或把环境异常伪装成 PASS。

#### 6.6.4 永久成果与设计边界

#90 没有失效；它按设计完成了“接口包**形状**完整性”。活动 Skill 也明确声明
checker 无 semantic authority。它能证明：

- packet 是 duplicate-free closed JSON；
- required identity、seam、authority 与 receipt digest 字段存在且格式正确；
- bytes/摘要在 handoff 前后没有漂移。

它不能证明：

- authority 原文包含完整 decision table；
- 多份 authority 之间没有冲突；
- malformed/stale/illegal 的判定 precedence；
- actor、approval、contract binding 的跨事件语义；
- Worker 是否收到并回报同一组结构化 input/output artifacts；
- reference receipt 能由任意 fresh consumer 重现。

因此 #85 后来的失败不意味着 #90 白做了，而是证明 Orchestrator 把“形状完整”
错误提升成了“语义充分”。#93 的正确修复是把公开语义放入 `K` 和 kind-specific
structured fields，并把 #90 v1 作为统一守卫的 compatibility adapter；不能把守卫
无限膨胀为业务 oracle。

### 6.7 #85 R2：作为已合并能力边界的反证

#90 之前的 #85 epoch 在 Candidates `4b5d06b0`、`f300d5db`、`1aa544eb` 后冻结，
其 acceptance evidence 不可复用。本节只分析从 `9331d66` 新 Governor 启动的 R2。

#### 6.7.1 Human Gate 前看似完整的证据

R2 在 Gate 前曾运行 owner gate 6 PASS、selected mutants PASS、full suite PASS、#90
direct checker PASS、#88 prepare/check/run PASS。`full suite` 是历史执行事实，不是
本版认可的 task-level Tester 要求；新模型只运行冻结的 Impact Set。其余 receipts
分别证明了：

- owner Test 能和 reference overlay 配合；
- packet 形状与摘要正确；
- handoff 时 cwd/HEAD/manifest identity 正确。

它们没有共同证明公开 authority 已经充分、无歧义地定义 transition semantics，
也没有证明 Tester 在 FAIL 后能产出完整根因、再由 Orchestrator 安全交给 Worker。
这是 Orchestrator 的合同与诊断桥缺口，绝不是允许 Worker 读取 owner Test 的理由。

#### 6.7.2 三个历史 Candidate 为什么分别失败，以及为何不等于三次 correction

| Candidate | 结果 | 直接 Implementation 缺陷 | 促成缺口 |
| --- | --- | --- | --- |
| A1 | 6 collection errors | Worker-owned tests 修改 `sys.path`，掩盖 direct-path 真实加载；Candidate 中出现 `ModuleNotFoundError`。 | handoff 没冻结 loader topology，Worker generality gate 没用真实消费者加载方式。 |
| A2 | 6 owner failures | schema/order、decision case、malformed/stale precedence 等与合同不符。 | packet 只有签名、required keys、streams/exits 和摘要，没有完整 decision/precedence table。 |
| A3 | 3 owner failures / 3 PASS | contract 绑定顺序应为 `MALFORMED_EVENT` 却返回 `INVALID_RECORD`；approval identity drift 应为 `STALE_EVENT` 却返回 `MISSING_EVIDENCE`；F1 routing 应为 `ILLEGAL_TRANSITION` 却返回 `OUT_OF_ORDER_EVENT`。 | 分散 issue prose、reference mutants 和 owner Test 没有被收敛成唯一、公开、可执行的 semantic annex。 |

按本版计数，A1 是初始 `C0`，A2 是 correction 1 后的 `C1`，A3 是 correction 2 后的
`C2`。当时把 A3 叫作 “attempt 3/3” 并宣告预算耗尽是账本错误：Worker 仍应拥有
correction 3，随后才形成 `C3`。本报告保留 A1/A2/A3 的真实失败证据，但不再把该
冻结解释成合法的 correction-exhausted terminal state。

当前不直接在旧 R2 上补跑 `C3`，理由也不再是“预算耗尽”：Owner 已批准先修正
生命周期合同，#93 会改变 governing `W` 并在合入后选择新 `G`，旧 R2 因 contract
model invalid 而终止。A3 的未污染 Implementation source/diagnosis 必须进入 salvage
inventory；新 series 从新 `G/K` fresh 验证，不允许把这次必要重建解释成丢弃实现。

三次结果当然包含真实 Implementation 缺陷；不能把责任全部推给交接。但三类错误
都发生在“多个条件同时不满足时，先判哪一个、返回哪一类”这一共同边界，而 #90
packet 恰好不承诺该语义。这说明 Orchestrator 在 Worker dispatch 前没有完成自己
负责的接口合同收敛。

真实证明链是：

```text
owner Test + 逐步修正过的 reference overlay = PASS
```

却被错误解释成：

```text
任意隔离 Worker + frozen shape packet = 可唯一复现合同
```

#### 6.7.3 #85 对已合并框架给出的结论

- #78 的静态验收基座仍有效，但 transition/history 尚未落地；
- #83 的 full-chain Test prevalidation 仍有效，但没有证明 handoff sufficiency；
- #88 的 mechanical identity guard 仍有效，但没有守卫完整的结构化角色交付链；
- #90 的 shape/digest checker 仍有效，但没有 semantic authority；
- “所有现有 gate 都 green”只能说明各自局部承诺成立，不能自动推出端到端交付
  合同充分。

#85 因而不是推倒前述成果的理由，而是下一轮自举必须补齐“语义附件 + fresh
consumer rehearsal + real loader topology”三项的证据。

### 6.8 Implementation 为什么被丢弃：事实审计与根因

Owner 指出的浪费属实，但需要区分三种不同现象：真正重写、内容复用但 lineage
被压平，以及正确的增量修正。Git 审计结果如下：

| Issue/epoch | Implementation 拓扑 | 评价 |
| --- | --- | --- |
| #78 minimal P0 | `d54ce313 → c1f86e8 → 02d5962 → 31cbc94 → 57373f5`，再产生 final `c7dc051` | 正确的累积 bootstrap；阶段 Test/Candidate 可替换，实现进展连续保留。 |
| #82 | `e9de3a0 → fa94227` | 正确的同 lane 增量修正；第二版只针对失败 seam 调整。 |
| #83 R2 | 同一 Implementation `10a89f0` 先后与 Tests `9994e4c`、`066d172`、`7bd1c9f` 组装 | 正确：失败归属 Test/Process 时，Implementation 原封不动保留。 |
| #83 v7 | `1718a20`、`3a35b9e`、`95ee1e8` 都直接从同 Governor 分叉 | 内容实际上逐步复用，A2→A3 仅约 `+2/-1`，但 commit lineage 被丢弃，审计上看成三次重建。 |
| #83 v8 | `3b6c364 → 748a547 → 228c9d3` | 正确的 epoch 内增量修正；但相对 v7 仍重新基线化。 |
| #88 | `a84dd66`、`025fe55`、`10ee5c0` 是 Governor siblings | A1/A2 的核心 guard blob 相同，主要变化在 generality；源码被复用，但历史被压平，浪费 provenance。 |
| #90 | Test 替换后继续使用 exact Implementation `d0a1274` | 最佳局部返工案例：owner Test lexical overconstraint 不应牵连 Implementation。 |
| #85 R1 | `675927a → 06eb015 → … → b697c05` | 正确的连续修正。 |
| #85 R2 | `130af4c`、`bb4a2c6`、`80f7e6b` 都直接从 `9331d66` 分叉 | A1→A2 约 `+46/-12`、A2→A3 约 `+203/-31`，内容是累积修正，Git 身份却被伪装成 fresh sibling。 |
| #85 R1→R2 | 五个 scoped files 约 `+646/-2129` | 这是实质性重写。新 Governor/合同要求 fresh acceptance evidence 合理，但禁止读取/复用所有旧 source 把 evidence invalidation 错扩大成 code invalidation。 |

根因不是 Git 技巧，而是 Orchestrator 混淆了三个概念：

1. **stale acceptance evidence**：旧 Test PASS、approval、Candidate、Reviewer 结论不
   能证明新 epoch；这一点必须严格作废。
2. **implementation source/progress**：只要没有被 owner Test 污染、没有违反新
   contract，旧 source、patch、设计和 generality tests 可以作为非权威输入被
   salvage，并在新 epoch 从头重新验证。
3. **direct-union Candidate**：Candidate 不允许 merge-only edits，不等于
   Implementation 必须是 Governor 的单一 sibling commit。`Ik` 完全可以是
   `I(k-1)` 的后继，再与 frozen Test 组装 direct union。

今后的不可变规则是：

- 同一 Candidate series `S=(task_run,G,K,T)` 内，`I1`、`I2`、`I3` 必须是上一
  Implementation tip 的
  后继；同一个 Worker lane 继续拥有修正，不能因一次 FAIL 重新开发。
- Test/Process/Environment 归属的失败不产生新的 Implementation；修 owning lane 后
  重新组装同一 Implementation。
- `G` 或 `K` 改变时，旧 commit identity 不能直接充当新 acceptance，但
  Orchestrator 必须先生成 source-salvage 清单：可复用、需适配、受 owner Test
  污染、与新合同冲突。只有后两类允许丢弃或重写。
- “不得读取历史 Test/Candidate”只保护当前或未接受 series 的隐藏 gate，不排除已
  accepted merge 带入 `G` 的正常回归测试；也不得扩写成“不得读取自己完成的
  Implementation 或公开设计”。若隔离要求 fresh Worker，也必须给它经过审查的
  clean implementation patch，而不是让其从零重复发现相同设计。

### 6.9 合并路径纠偏：交付 accepted Candidate，而不是剥离 Test

Owner 点名的 `091da706e6332ca7ca01064764448144e1011073`、
`6648f94c15aeca296335e6700e5534b036f243a6` 和
`c896174cb94382ab25c5b5d284ff6c8ea14689c9` 引出了两个必须分开审查的问题：
Test 是否绕过最终验收/PR 单独进入主线，以及最终提交是否由 accepted Candidate
变成了 Reviewer lesson child。过去确实反复采用后者的 finalization 路径；精确谱系
如下。该表记录 Git 事实，不凭 ancestry 本身判定某次 Human 审批是否有效：

| Issue | Acceptance Candidate | Candidate parents | 被推入主线的 lesson/final tip |
| --- | --- | --- | --- |
| #78 | `31e913d` | Test `fe8cc87` + Implementation `c7dc051` | lesson/integration `3f24f6b`，随后进入 PR #84 merge `d1dc62c` |
| #88 | `a6429a6` | Test `a8bdda3` + Implementation `10ee5c0` | `091da706` |
| #82 | `616b7fc` | Test `3d38a505` + Implementation `fa94227` | `c896174` |
| #83 | `d510f09` | Test `6648f94` + Implementation `228c9d3` | `69b4e217` |
| #90 | `e72befe` | Test `f94eb2f` + Implementation `d0a1274` | `9331d668`（本次审阅 HEAD） |

前版据此推导“Test/Candidate 进入主线即污染，成功 PR 只能保留 Implementation”，
这是错误的。`6648f94...` 是 Test commit，不意味着它必须永远排除在主线外；它可以
作为已批准 `T`，随通过验收和最终 Human 审批的 `Ck=[T,Ik]` 经 PR 一起合入。
仅凭祖先链，不能区分这条合法路径与绕过审批直接推送 Test 的违规路径。

隔离保护的是**当前任务开发/修正期间**的 owner Test：Worker 不读它，Tester 不改
Implementation。既往 accepted Candidate 带入 `G` 的测试是已合并回归资产；其存在
本身不证明新任务发生泄漏。当前任务未批准、失败或仍保密的 Test/Candidate 仍不能
通过历史 ref 访问绕过隔离。不得以“保护隔离”为由删除最终应交付的测试。

正确的目标拓扑是：

```text
same G → Test lane → approved frozen T
same G → Implementation lane → I0 → I1 → I2 → I3（按需修正）

Ck = direct union of T and Ik; ordered parents = [T, Ik]
Ck → Tester PASS → terminal Reviewer APPROVED
   → PR head exactly Ck → Human final approval → merge Test + Implementation

Reviewer report/lesson: separate evidence; does not replace Ck as PR head
failure: no success PR; preserve Implementation and terminal evidence
```

机器 finalization 至少要证明：

- PR head 就是 terminal PASS 且 Reviewer APPROVED 的 exact `Ck`，不是 `Ik`；
- `Ck` 的 ordered parents 为 `[T,Ik]`，两条 lane 的 merge-base 为 exact `G`；
- `G..Ck` 的 changed paths/blob set 是两个 lane manifest 的 direct union；包含批准
  Test 的交付文件和 Implementation（含 generality tests），无 merge-only edits；
- PR base 与批准的 `G` 一致，Human Gate 2、Tester/Reviewer evidence 和 PR head/tree
  都绑定同一 `Ck`；不得换 head、重建一份“等价”Implementation-only 交付；
- 不将临时 reference/stub、confidential receipts、未接受的 Candidate 或 Reviewer
  lesson 追加到获批 head；不重写 `G` 之前的历史。

Reviewer 的 lesson 若需要长期进入仓库，必须另开一个明确获批的 governance issue/
PR；它不能借产品任务自动进入主线。当前 `AGENTS.md` 要求 Reviewer append repo
lessons，与这条规则冲突；迁移完成前，Reviewer 可在独立 review branch 生成 commit
供精确审计，再由 Orchestrator把内容发布为 issue/PR evidence，但不得合并该 commit。

### 6.10 跨 Issue 对照矩阵

| Issue | 最初误判或缺口 | 最终收敛机制 | 已合并的永久能力 | 成功后仍存在的边界 |
| --- | --- | --- | --- | --- |
| #78 | 把完整状态机、证据、权限、CLI 和治理当成一次可自举的大交付；snapshot 被当成合法 history。 | 语义重置，缩成 staged minimal P0 static gate；小 owner/general/regression gates + Tester + Reviewer + Human。 | workflow contract、静态 gate、角色/证据基本治理。 | 无 executor、history replay、结构化角色交付、assembler、可靠 isolation。 |
| #82 | 把不稳定平台攻击 setup 当作事务语义测试；whole-platform private seam 太宽。 | 定义 publication linearization/ownership；purpose-specific public seam；minimal adapter 与 mutants。 | late-failure classification、owned rollback、foreign evidence 保留。 | 非通用 Windows capability/pytest/Agent 执行方案。 |
| #83 | 单层 reference green 被当成真实 pytest lifecycle 可执行；环境前提逐层暴露。 | clean absent-parent full-chain prevalidation；区分 creation/observation；先修 #82/#88 依赖。 | deterministic symlink capability gate 与 CI 行为。 | 不证明任意角色 handoff 语义充分。 |
| #88 | SHA-looking/string-equivalent identity 被当成 Git/byte identity。 | 小型外部人工自举；typed commit + ancestry；raw manifest/blob digest；synthetic repo。 | cwd/HEAD/Base/contract/manifest/argv/timeout 机械守卫。 | 可跳过 successful check；未覆盖完整结构化角色交付、canonical role 或语义。 |
| #90 | 缺 packet 被当作主要问题，shape completeness 容易被高估为 semantic completeness。 | closed duplicate-free packet、raw bytes/digest、owner-aware Test correction、retained Implementation。 | 机器可验的接口包形状与摘要连续性。 | 不读取/解释 authority；无 precedence、identity matrix、vectors 或通用 artifact family。 |
| #85 R2 | local gates 的 conjunction 被误当成端到端 handoff sufficiency。 | 尚未收敛；A1/A2/A3 被旧账本提前冻结。 | 目前只有失败证据；按新模型仅到 `C2`，correction 3 / `C3` 未执行。 | 需要 semantic annex、Tester forensic bridge、真实 loader topology 和可信 epoch ledger。 |

### 6.11 这些 Issue 最后艰难成功的共同机制

跨 #78、#82、#83、#88、#90，真正有效的收敛动作高度一致：

1. **先停止把新失败自动塞回原 Issue。** 用 Base comparison、ownership 和公开
   scope 判断它是当前实现、Test、Process/Environment 还是独立前置缺陷。
2. **冻结并作废旧证据，但保留实现资产。** Test、Implementation 或 authority
   发生语义变化后，旧 approval、Candidate 和 acceptance receipt 不再复用；这不
   自动作废未受污染的 source、patch、设计和 Worker generality tests。
3. **缩小到一个公开 seam 或一个机械不变量。** #82 缩到 publication seam，#88
   缩到 handoff identity，#90 缩到 packet shape；#78 只有退回 minimal P0 后才成功。
4. **把失败翻译成合同，而不是实现提示。** 例如“Base 必须是 ancestor commit”、
   “publication 后不能再返回 backup_changed”、“诊断要求类别而非固定标点”。
5. **在 Human Gate 前证明正确 reference 和错误 mutants。** 只跑 reference green
   不够；必须有 known-bad 证明 gate 真能拒绝关键绕过。
6. **使用真实拓扑做至少一条 vertical slice。** 包括真实 Git object、真实 pytest
   discovery、真实 absent-parent、真实 manifest bytes，而非只有 monkeypatch helper。
7. **严格绑定 identity 与 lineage。** Governor、Test、Implementation、ordered
   Candidate parents、manifest/raw bytes、Human comment 都必须指向本 epoch。
8. **按 owner 局部返工。** Human 批准前的 Test lexical overconstraint 只修 Test；
   Base defect 建独立依赖；批准后的 Test 永久冻结；Implementation defect 才消耗
   一次 Worker correction，并在同一 lineage 产生下一个 Candidate。
9. **Tester 与 Reviewer 证明不同问题。** Tester 对最多四个 Candidate 提供唯一
   功能收敛信号；Reviewer 只在 task 成功或 correction budget 耗尽时审查一次，
   覆盖 Test 未证明的边界、ownership、generality 和失败经验。
10. **对未知问题做一次有界诊断并忠实记录。** 只有可复核 Base-equivalent 或
    Process/Environment 证据时才能 non-blocking；不能由 Orchestrator 模糊自判来
    规避 attempt。

这些成功不是“规则越多越好”。相反，每次成功都依赖规则与当前失败之间存在明确
因果、规则可以被人审阅和机器反演、且不把未证明的邻接问题升级成全局 blocker。

### 6.12 当前必须避免的错误历史叙事

以下七种叙事都会导致下一轮重复失败：

- “#78 已经合并，所以 Loop 已完整。”——它合并的是 minimal acceptance P0，
  execution P1 明确未完成。
- “#83 最终全链预验证成功，所以任何 Test Gate 都已端到端。”——#83 证明特定
  pytest/capability 链，不证明角色之间的 semantic handoff。
- “#90 checker PASS，所以 Worker 收到的合同一定充分。”——它只证明 shape 和
  digest continuity。
- “#85 三次都是 Worker 写错，因此换一个 Worker 即可。”——实现确实有错，但
  三次均集中在未机器交付的 precedence/identity/routing 语义；不补合同就只是在
  同一信息缺口上重新抽样。
- “旧 acceptance evidence 作废，所以旧 Implementation 也必须丢弃。”——证据与
  source 是不同资产；只有污染或合同不兼容的部分不能 salvage。
- “三次 Attempt 等于最多三个 Candidate。”——三次是初始实现之后的三次修正，
  正确上限是 Candidate 0、1、2、3 共四个。
- “开发时 Test/Implementation 隔离，所以成功 PR 必须排除 Test。”——隔离约束开发
  过程；最终 PR 必须是包含两者的 accepted Candidate。Reviewer lesson 属于单独
  证据，不能据此将 PR head 换成未验收 lesson child。

正确叙事是：现有成果都是有效但有边界的 building blocks。下一轮自举必须组合
它们，同时为“从公开合同到 fresh consumer 行为”增加独立证据，才能把局部 green
提升为端到端可信。

### 6.13 `agent-lessons-learned.md` 全量归纳

截至本次审阅，活动 lessons 包含 Legacy LSK-1～7 和 LL-001～LL-046。它们不是
46 条互不相干的检查项，而是反复指向七类系统性教训：

| 主题 | 覆盖 lessons | 对 bootstrap 的约束 |
| --- | --- | --- |
| source authority、XDM、asset、coverage | LSK-4/7；LL-001/005/007/012/014/016/017/027/029/030/036 | 从真实 descriptor/source 前向实现；asset 必须 runtime-bound 或 code-equal；coverage 必须双向、path-specific |
| gate 真值、known-good/bad、真实链路、黑盒 | LSK-5；LL-002/003/009/013/018/019/020/021/023/028/034/045/046 | exit 0、helper PASS 或 reference PASS 都不够；必须证明真实消费者、真实默认路径和错误样本；full-chain 不等于 full-suite |
| ownership、窄修改、安全发布 | LSK-1/2/3/6；LL-006/010/015/027/032/033/035/037/044 | byte/path/ancestor/rollback ownership 分开证明；角色不得跨边界修改；未知 late failure 只按可证明所有权处理 |
| generality、反 hardcode、反 case-fit | LL-011/012/013/016/017/019/023/030/040/046 | 扰动 fixture、边界和真实 loader；完整规则逐条有正/负断言；public semantics 不得被 Test lexical 偏好收窄 |
| evidence identity、raw canonicality、freshness | LL-029/031/034/038/039/041/042/043/045/046 | exact commit/blob、duplicate-free raw JSON、canonical syntax、tested tree 和输出完整性都属于 verdict 本身 |
| 执行效率、KPI、临时环境、completion-first | LL-024/025/026/044/045 | 简单任务走窄路径；测试临时物受控；一次有界 Base comparison；不把无关环境问题扩成全局 blocker |
| role、文档和治理一致性 | LL-004/008/010/021/022/031/038/039/040 | missed skill、plan/apply、Category A/B、metadata/changelog 和完整 Agent rule 都需要独立守卫 |

Legacy baseline 的七项稳定规则是：

| ID | 归纳后的永久规则 |
| --- | --- |
| LSK-1 | 修改 element 或 carrier 时，`quick_selection` 必须在所有 reload/replace 之后清理并由写出字节证明。 |
| LSK-2 | 每个模块只改自己的窄范围；无关字节保持不变。 |
| LSK-3 | XML safety、byte-faithful serialization 和原子写入由 document core 统一承担。 |
| LSK-4 | runtime 只消费 committed release assets，不能回退到开发源或不可发布路径。 |
| LSK-5 | vendor gate 顺序为 static checks 后 S32DS；PASS 需要 exit 0 且无 qualifying SEVERE。 |
| LSK-6 | module ownership 与 cross-module dependency 必须显式声明并按最窄路径授权。 |
| LSK-7 | enum、pin、ID、range、default 和约束来自真实 `.xdm`/source，禁止推测。 |

LL-001～LL-046 的 coverage index 如下。该索引用于证明本 trust trace 已处理全部
活动 lesson；详细原始叙述仍以 `agent-lessons-learned.md` 为准。

| ID | 失败事实与保留规则 |
| --- | --- |
| LL-001 | invented Uart enum 被 vendor 拒绝；所有 domain value 必须来自 `.xdm`。 |
| LL-002 | 未验证的 S32DS headless 命令会挂起或走错 launcher；外部工具流程先在真实环境确认。 |
| LL-003 | ConfigTools exit 0 仍可能含 SEVERE；vendor verdict 必须组合 exit 与诊断。 |
| LL-004 | Skill 不会自动触发；Worker brief 和 Reviewer 必须显式检查 uniform header 等横切规则。 |
| LL-005 | 手工 stub asset 不能成为测试真值；asset 必须从 authority 构建。 |
| LL-006 | XML well-formed 不证明窄修改；无编辑 byte-identical、owned edit narrow 必须可测试。 |
| LL-007 | spec 自洽不等于 vendor truth；Reviewer 要对照 descriptor，vendor gate 要前置。 |
| LL-008 | milestone 不得泄漏到 spec，changelog 不得压缩改写。 |
| LL-009 | off-by-default vendor gate 可让全部输入实际失败仍“44 PASS”；known-good 与 known-bad 是 gate 自证前提。 |
| LL-010 | plan/apply/dependency 可在绿测下漂移，且 Tester 曾越权改 production；必须同时守住行为与角色边界。 |
| LL-011 | fixture 的平凡 next-id 会掩盖 hardcode；用扰动、连续添加和空分支证明动态算法。 |
| LL-012 | asset provenance 可错误且 runtime 未加载；每个值引用真实来源，asset 必须 runtime-bound 或 code-equal。 |
| LL-013 | exit 0 但 quick selection 让生成代码忽略新增配置；插入必须在 generated output 与派生 ID 上被证明。 |
| LL-014 | Problems-view SEVERE 不被旧 detector 捕获且 clock asset 漂移；完整诊断面与 recipe binding 都是 gate。 |
| LL-015 | 为通过 review 放宽 diff bound 会消灭窄修改保证；边界应从测得的合法 footprint 得出。 |
| LL-016 | FlexIO asset keys 和 loader 无绑定，asset-only tests 循环自证；每个 key 必须到达 runtime 或代码等值。 |
| LL-017 | DMA asset、static checker 和结构 spot-check 均可空转；禁止 no-op guard，结构和每个 runtime key 都要可追踪。 |
| LL-018 | repo 内 green 不能证明发布 Skill 或环境 vendor gate；必须验证 released artifact 的真实路径。 |
| LL-019 | 只有 existing-container fixture 会遗漏 create path；每个创建能力要有 absent-container/perturbed case。 |
| LL-020 | inherited embedded subagent 不是 true black box；E2E 必须由独立第三方 Agent CLI 执行。 |
| LL-021 | cold review 可发现 deferred guard rot 和未经证明的人工控制删除；外部审查与补偿控制映射不能省略。 |
| LL-022 | Category A purity 和 spec altitude 需要 repo-wide 检查，不能只看 diff。 |
| LL-023 | injected seam PASS 可掩盖真实 default loader 断裂；至少一条测试必须走真实默认路径。 |
| LL-024 | 简单任务被计划仪式拖慢并错失 KPI；规模与依赖不足时使用窄 fast path。 |
| LL-025 | regex/proxy 会把计划文字误算成实际命令；KPI measurement 必须绑定真实 invocation。 |
| LL-026 | system temp 和遗留工作目录会产生环境漂移；测试临时物统一放 `tests/.tmp` 并由 owner 清理。 |
| LL-027 | ADC/BCTU 嵌套 ownership、timing representability、asset binding 和 Windows retry 必须作为不同约束验证。 |
| LL-028 | adapter 可以宣称支持却绕过真实 dispatch，stream marker 可跨 chunk；每个 advertised field 都要走 production path。 |
| LL-029 | green 测试可能对应 dirty/uncommitted tree，XDM 提取不完整，文档计数过期；结论必须绑定 exact tested state。 |
| LL-030 | KPI fast path 不能替代 XDM 边界和 surface coverage；gapped/exhausted domain 与 `_coverage` 都要证明。 |
| LL-031 | metadata version/date 可落后 changelog；编辑 reference 时三者必须原子一致。 |
| LL-032 | bundle preflight 旁路 legacy loader 无法建立 trust；所有 asset read 和路径组件必须经过同一 resolved capability。 |
| LL-033 | rollback/restore 是第二次 adversarial publish；恢复也需 CAS、identity、hash 和 cleanup ownership。 |
| LL-034 | 截断输出或 reader failure 可丢掉早期 SEVERE；输出完整性与 process-tree cleanup 是 verdict 条件。 |
| LL-035 | normalization 会漏掉 byte/QName/order 变化，module-level authorization 太宽；journal 必须 byte-complete、path-narrow。 |
| LL-036 | descriptor 再生成只证明 source fidelity，不证明 coverage 分类诚实；实现写集合与 coverage 必须双向精确映射。 |
| LL-037 | payload hash 正确仍可能经 symlink/reparse ancestor 发布到错误位置；content integrity 与 location integrity 分开验证。 |
| LL-038 | Category A acceptance 只能记录产品可观察证据，Agent routing 叙事留在 Category B。 |
| LL-039 | 删除 superseded current rule 不能重写历史 changelog；current projection 与 append-only history 分离。 |
| LL-040 | Agent contract test 必须 pin 完整规则，而不是只 pin 存储路径和少数词语。 |
| LL-041 | parser normalization 与 self-clearance 会接受非 canonical locator 或污染真实 archive；raw grammar 和 synthetic fixture 分离。 |
| LL-042 | raw delimiter、bare prefix 和 exact count 必须在 normalization 前独立守卫。 |
| LL-043 | SHA-looking string 可能是 blob/tree/tag，JSON 可能 duplicate-key；身份要 type-exact、raw-byte continuous。 |
| LL-044 | primitive raise 后仍可能已发布；按 identity/content 收回所有权，并对未知 F0 只做一次 exact Base comparison。 |
| LL-045 | Human Gate 前预验证完整 prerequisite chain、真实 absent-parent 与异常阶段；full-chain 是选定 gate 的端到端拓扑，不是全量 unit suite。 |
| LL-046 | hidden Test 不得把意义合同收窄成固定标点；frozen evidence 必须脱离 runner-owned cleanup 生命周期。 |

## 7. 重要缺陷与风险登记

以下优先级只表示相对于下一轮有限自举的处理顺序，不自动等价于全项目
blocker，也不自动改变现有 issue priority。

### 7.1 B0：进入下一次 #85 实现前必须显式处理

#### B0-0 当前机器合同与 Owner 生命周期定义冲突

- 标签：**已证实设计/合同缺陷**。
- 事实：当前 route 把 Human Gate 1 放在 Implementation 前；
  `candidate_attempt=1..3` 不能表达 Candidate 0+三次 correction；Reviewer 只允许
  Tester PASS 后进入；历史 finalization 又用 lesson child 替代 accepted Candidate
  作为最终 tip。前版的 Implementation-only 纠偏反而错误剥离了应交付 Test。
- 影响：如果直接按当前合同恢复 #85，新流程要么无法表示，要么被迫伪造 attempt、
  跳过 failure review，或让最终交付偏离已验收 Candidate。
- 当前措施：先以一个极窄 bootstrap work package 更新合同、Skill、角色定义和
  known-good/bad lifecycle replay；不在该包中实现 #85 transition engine、完整
  executor、recovery 或 GitHub automation。
- 验收：至少证明 Test/Implementation 同 `G/K` 独立推进、Test ready 可在 `I0`
  之前触发 Gate 1、首次 Candidate 才 join approved Test 与 ready Implementation、
  Test approval freeze、`C0` 不消耗 correction、`C1..C3` 逐一消耗、
  `I0→I1→I2→I3` continuity、PASS/exhausted 两条 terminal Reviewer 路径和
  accepted-Candidate PR topology：head exact `Ck=[T,Ik]`，完整交付测试与实现。

#### B0-1 语义交接合同缺失

- 标签：**集成缺口**。
- 事实：公开 packet 不包含 decision/precedence/identity/routing 行为。
- 影响：packet 单独不足以唯一决定行为；Worker 必须依赖分散的 issue prose，或在
  prose 冲突/遗漏时自行解释，owner Test 因而可能成为隐藏规范。
- 当前措施：为 #85 冻结一个公开语义附件，并用合同消费者预演证明其可解释性。
- 不应采取：把 owner Test source/literals 发给 Worker，或把所有业务语义塞入 #90
  checker。

#### B0-2 Reference prevalidation 与失败诊断桥的证明目标不完整

- 标签：**流程设计缺陷**。
- 事实：目前证明 owner Test、特定 reference overlay 和一组 selected mutants
  一致；未证明公开合同足以让独立 Worker 实现，也未证明 Candidate FAIL 后 Tester
  能把 hidden case 转换成完整 Implementation root-cause report，再由 Orchestrator
  安全交给 Worker。
- 影响：仍可能在 Human Gate 后逐层发现公开合同遗漏，或只给 Worker 症状而迫使其
  猜 hidden Test。
- 当前措施：把 prevalidation 拆成“Test 链可执行”“公开合同消费者可解释”两项
  receipt，并增加 confidential Tester Forensics Report、Worker Correction Envelope
  和字段级 disclosure review。Worker 始终不得读取 owner Test。

#### B0-3 角色任务输入与返回没有统一结构化文件

- 标签：**集成缺口**。
- 事实：#88 固定 checker/identity argv，#90 只检查一种 owner-Test-to-Worker packet；
  角色任务仍由 prompt/prose 承载，返回仍主要是 chat response。
- 影响：同一任务的字段、可见性、前驱关系、返回状态和 evidence shape 会随每次
  dispatch 漂移；新文件类型继续诱发新的独立 checker。
- 当前措施：#93 定义统一 canonical artifact family 和参数化 handoff guard。Prompt
  只定位 lane-local input/output、加载 Agent 规则并提醒非任务运行边界；它不承载任务
  语义，也不需要严格哈希。角色报告文件回显 input Envelope digest，chat response
  只通知报告 path/digest/status，不作为 acceptance evidence。

#### B0-4 classification 与 correction/task epoch 无可信账本

- 标签：**模型缺口**。
- 事实：合同只有当前 `candidate_attempt: 1..3`，没有 Candidate 0、correction
  index、Test/contract epoch、前序 Candidate/Implementation、失败 owner 或 reset
  authority。
- 影响：可能误耗 correction，也可能用重新命名 task/epoch 规避 correction 上限。
- 当前措施：有限自举为每次公开合同 freeze 赋予一个 Task Contract Epoch `K`；
  `C0` 固定为初始
  组装，只有 Tester 证明的 Implementation failure 才产生 correction `1..3` 和新
  `I/C`；有争议由 Human 决定，计数在决定前冻结而非重置。

#### B0-5 固定 Agent 时限与实际 harness 语义冲突

- 标签：**已证实治理/执行缺口**。
- 事实：`AGENTS.md` 仍以固定 3/5/10 分钟描述 Subagent 预期和强制介入；Tester
  guidance 与 `tools/blackbox_e2e.py` 以 `3 × 最大 catalog KPI` 对外部 Agent CLI
  设置硬 timeout。相对地，当前 Codex 公开 Turn/Subagent 接口提供事件流和显式
  interrupt，但没有公开的 per-turn 固定 wall-clock deadline；本机 OpenCode `run`
  也未暴露统一 task timeout 参数。
- 影响：任务复杂度不同却共享截止时间；有进展的 Agent 可能被提前杀死，KPI 被错误
  用作生命周期限制，transport/tool/platform interruption 又可能被误记为 Test 或
  Implementation failure，并错误消耗 correction。
- 当前措施：在 #93 前先落一个极窄动态监督 bootstrap package；删除固定 Agent 自动
  终止规则，复用 harness 原生 progress/status/interrupt，只把估时作为观测触发器。
  `handoff_guard.py --timeout-seconds` 保留为确定性子命令 timeout，但改名/说明为
  `command_timeout_seconds`，不得解释为角色任务期限。
- 不扩展：该 package 不实现 route executor、持久 recovery、通用 scheduler 或所有
  项目脚本 timeout；后者按 §9.13 和 §11 的独立非阻塞链逐步实现。

### 7.2 B1：按依赖 owner 分流，不设统一的“#85 后修复阶段”

B1 是已明确事实和边界的窄缺口，但五项并不共享同一时序：B1-1/B1-2 是 #93
统一 #88/#90 交接守卫的一部分，必须在 #85 重启前完成；B1-3/B1-4/B1-5 由 #86
在 #85 transition vocabulary 稳定后实现。不得再把它们整体推迟到 #85 之后，或
另建一个重复的 handoff-guard repair stage。

#### B1-1 #88 可以跳过成功的 `check-handoff`

- 标签：**已证实缺陷**。
- 最小修复目标：`run` 必须只接受同 manifest digest、operation=`check-handoff`、
  outcome=`CHECKED`、exit code 0 的直接 prior receipt；添加 known-good/bad replay
  tests。
- 路由：并入 #93 的统一交接守卫，先于 #85。
- 不扩展：本修复不顺带实现完整 workflow transition engine。

#### B1-2 Governed workflow 未把 generic guard role 映射到 canonical role

- 标签：**集成缺口/待决设计**。
- 事实：#88 按既定通用合同允许符合正则的 role token；standalone guard 不承诺
  role 必须来自 workflow contract。
- 最小目标：由 governed workflow 的 wrapper/manifest producer 校验 canonical
  role；除非另行批准改变 #88 generic contract，不直接收窄 standalone guard。
- 路由：并入 #93 的统一交接守卫，先于 #85。

#### B1-3 Candidate 和 lane manifest 不验证 Git 实体

- 标签：**能力缺口**。
- 事实：当前只比较声明字符串，不验证 commit 存在、ordered parents、merge-base、
  direct union、path ownership、no merge-only edits。
- 建议：#86 在 route executor 前增加一个只读 Candidate/finalization verifier；
  除了验证 acceptance Candidate，还必须证明 success PR head 就是 exact accepted
  `Ck=[T,Ik]`，`G..Ck` 保留两个 lane 的交付且没有 merge-only edits 或 lesson-child
  替换；不能排除合法 Test paths。assembler 仍后置。
- 路由：#86，位于 #85 之后、#79/#87 之前。

#### B1-4 Human/Tester/Reviewer evidence 是 self-asserted/free-form

- 标签：**能力缺口**。
- 事实：workflow gate 不访问 GitHub；Tester/Reviewer evidence 只是非空字符串；
  Gate 2 actor/decision 比实际运行规则更宽。
- 建议：由 #86 处理 exact remote evidence、structured result envelope 和 epoch
  ledger，不在 #85 transition core 内夹带实现。
- 路由：#86。

#### B1-5 Operational invalid-run 与 contract finding 共用 “F0” 命名

- 标签：**命名/建模缺口**。
- 事实：contract finding 只允许 Tester/Reviewer 产生，且 F0 明确只能
  `BLOCK|STOP`；#83/#90/LL-044 中的 Environment/PROCESS “F0” 是运行叙事，
  不等于一个有效 `record.finding.F0`。
- 建议：在 #86 中将 operational observation、contract finding、affected operation
  state、correction accounting 和 global workflow status 分开建模；在映射获批前，
  不以 completion-first 实践为理由弱化现有 contract F0 blocker 矩阵。
- 路由：#86。

### 7.3 B2：重要但不阻塞当前自举

#### B2-1 Role isolation 主要依赖行为承诺

Worker/Tester 共享宿主文件系统；`forbidden_sources` 是 packet 声明，不是访问
控制。#79 应实现 capability-aware derived worktree hydration 与可审计访问边界。
在此之前，以独立 worktree、最小复制的结构化输入、locator-only prompt 和 post-run
diff 审查作为有限补偿。

#### B2-2 Event log 不是不可改写 workflow history

#88 events 没有 sequence、previous hash、session/run ID、并发锁，也不被后续读取。
它是 operation log，不是状态真值。#85 transition 和 #86 evidence 应明确谁拥有
canonical history，避免再造第四种不相连的 manifest/event schema。

#### B2-3 Preflight 可以由空列表自证 available

现有 validator 对 permissions/dependencies/tools 不要求必需项，evidence 也只是
非空字符串。未来 capability preflight 应有 probe、observed_at、runner identity、
有效期；但不能现在盲目把所有工具都改成 hard blocker。

#### B2-4 失败分支 lessons 不会进入 active trust root

当前 Reviewer 只在 Tester PASS 后追加 lessons，最有价值的 exhausted/frozen
failure 可能永远留在未合并分支或 `.agent-state`。Owner 新规则以“terminal
Reviewer 成功/失败都恰好一次”补齐事实入口，但 lesson 仍不得随 Candidate 合入。
需要一个独立于产品 merge 的 issue/PR evidence 或 process-incident intake；其内容
先是事实记录，不自动成为新规则。

#### B2-5 初始化 GUI 与 automation derived worktree 冲突

这是 [#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)/
[#92](https://github.com/autoMBD/autombd-rtd-config/issues/92) 范围。当前以“已初始化主 checkout 为权威、派生 worktree 只做
deterministic hydration/验证、automation 禁止启动 GUI”的人工规则绕开；待后续
实现 verify-only receipt。它不应抢在 #85、#86 之前扩成新的 P0 工程。

#### B2-6 CI 证明工具存在，不证明每个 PR 使用了工具

CI 运行工具单元测试和全 pytest，但不读取 live workflow record、handoff receipts、
Candidate lineage 或 Human evidence。将来 route executor 稳定后再接 enforcement；
当前不应用一个尚不可靠的 executor 阻塞所有 PR。

#### B2-7 P0 requirement IDs 和 issue classes 缺少活动语义映射

`P0-01..P0-18` 和 `M/B/W/T/D/N/I` 在 machine contract 中只有 ID/字母域；lane
manifest 声称包含全部 ID 并不能证明每项需求被实现或测试。后续合同版本应绑定
requirement text、owner stage、evidence type 和 test trace，但这不是 #85 R3 的
临时新增范围。

#### B2-8 Reviewer lesson child 被错误当成产品 finalization tip

实际合并常将“Reviewer lesson commit”作为 exact Candidate 的 sole child 推到
`master`。问题不是它的父链含 Test/Candidate，而是 lesson child 不再是同一个已
验收 Candidate，不能自动继承对 `Ck` 的批准。当前成功 PR 必须保留 exact `Ck` 为
head，完整包含 Test 与 Implementation；#86 verifier 验证这种身份一致性。lesson
若需进入仓库，走独立 governance approval，不再给产品 Candidate 增加 child。

#### B2-9 规范权威仍然碎片化

当前行为规则分散在 machine contract、Skill、角色文件、issue body/comments、
owner Test/reference 和 heartbeat prompt。宣称 `workflow-contract.json` 是唯一机器
权威，并不等于所有语义已经进入其中。有限自举必须为当前任务生成一个明确的
authority inventory；长期则由 #85/#86 决定哪些内容进入机器合同，避免把所有
issue prose 永久复制到 JSON。

### 7.4 待验证而非立即固化的风险

以下观察应记录并设计小实验，不应直接新增全局规则：

- dirty tree 是否应由所有 handoff 阻塞，还是只由 Candidate/Tester 边界阻塞；
- handoff event log 是否需要防篡改，或 Git-backed immutable receipts 已足够；
- 是否需要绑定 model/toolset/sandbox identity；
- 是否需要通用语义 schema，还是每类任务维护小型 contract annex；
- 简单任务是否可免去 disposable consumer implementation，只运行 contract vectors。

## 8. 自举方案比较

### 8.1 方案 A：继续现有 Loop，只在 prompt 中增加更多规则

优点：没有新工具成本。

缺点：规则继续存在于不可哈希的 prompt/issue prose；#85 已证明会逐层暴露；
Orchestrator 记忆成为唯一集成点。

结论：**不接受**。

### 8.2 方案 B：暂停业务，先一次完成完整执行框架

优点：最终形态更整齐。

缺点：用尚不可靠的 Loop 自举完整 Loop，重演 #78；transition、evidence、executor、
recovery、GitHub、isolation 同时变化，无法定位失败 owner。

结论：**不接受**。

### 8.3 方案 C：在现有 P0/#88/#90 上叠加有限自举监督层

优点：保留既有成果；只补当前交付边界；每次一个 seam；能在执行框架未完成时
继续交付；所有残余风险显式记录。

代价：在结构化交付、classification 和 Candidate assembly 机器化之前，Human/
Orchestrator 仍需进行窄而明确的人工确认；Orchestrator 作为受信任 LLM 承担
Correction Envelope 的语义充分性与 non-disclosure 判断。

结论：**推荐**。

## 9. 修正后的 `BOOTSTRAP-LIMITED` 交付流程

### 9.1 唯一术语与状态模型

本节从本版起取代历史 issue/heartbeat 中所有与它冲突的 Attempt 用法。首先必须
区分代码基线、全局机器合同、task 公开语义快照和一次 Candidate series：

| 符号 | 含义 | 生命周期 |
| --- | --- | --- |
| `G` | exact Governor/Base Git commit | 两条开发 lane 的共同父基线；series 内不可变 |
| `W=blob(G,path)` | `G` 中固定路径的 exact global Workflow Contract blob | 从 `G` 唯一派生，只作通用 route/field/permission/lifecycle 的完整性身份，不是第二个可自由选择的基线 |
| `K` | Task Contract Epoch / Shared Task Brief | 对 `G`、派生 `W`、task 公开 authority、semantic annex、scope 和交接接口的不可变公开快照 |
| `T` | owner Test tip | Human Gate 1 前可修订；批准后到 task 终止永久冻结 |
| `I0` | Worker 初始完整 Implementation tip | Worker lane 首次完成时形成 |
| `Ik` | 第 `k` 次增量修正后的 Implementation，`k=1..3` | 必须是 `I(k-1)` 的后继 |
| `Ck=[T,Ik]` | 当前 task 第 `k` 个 acceptance Candidate | 审批前在独立 ref 验收；direct union、无 merge-only edits；成功的 exact Ck 是最终 PR head |
| Correction Attempt `k` | Tester 证明 Implementation defect 后，Worker 的第 `k` 次修正机会 | 只有 `k=1..3`，没有 Attempt 0 |
| `S=(task_run,G,K,T)` | Human 批准后冻结的 Candidate series | `G/K/T` 任一改变即终止，不得原地重置预算 |
| `R` | terminal Reviewer result/lesson evidence | series 成功或失败终止时恰好产生一次 |

#### 9.1.1 Governor `G`

Governor 是 exact Git commit，不是动态 `master` 指针。其 tree 包含产品、测试基础
设施、Agent Loop 实现、活动机器合同、Skill/角色定义、治理文档和已合并依赖。
它只负责代码/blob 基线、共同 merge-base、变更归属和 lineage，不包含未来 Test、
Implementation、Human comment、运行环境或临时 receipt。

Orchestrator 可以提出 Governor change，但只有 Human 可以批准。只有以下情况允许
选择新 Governor：本任务依赖的前置修复已合入；当前 Base 有
影响 mandatory acceptance 的已确认缺陷；governing contract/code 已由独立任务
合入；Human 明确选择新基线；或者前一 task 已终止而 successor task 需要新 Base。
Candidate FAIL、Worker correction、Gate 前 Test revision、runner/ACL/cwd/temp/network
问题、无关 `master` 更新和重置修正预算都不是换 Governor 的理由。

每次 Governor 变化必须记录：`old_governor`、`new_governor`、change reason、relevant
diff、invalidated evidence、salvaged source/patch 和 Human authority。旧 acceptance
evidence 作废，不自动作废未被 owner Test 污染且与新公开合同兼容的 source、设计或
Worker generality tests。

#### 9.1.2 Workflow Contract `W` 与 Task Contract Epoch `K`

`workflow-contract.json` 是全局机器合同，只定义通用生命周期、封闭字段/枚举、
route、role permission 和 evidence shape；它不是某个 Issue 的完整业务语义。
Orchestrator 只选择 exact `G`，不得再独立选择一个可能与其不匹配的 `W`。`W` 必须
按 `W=git_blob(G,"agent-discipline/workflow-contract.json")` 派生；Launch Envelope
记录 path 和 expected blob 只为验证 checkout、raw bytes 和两条 lane 的规则身份没有
漂移。

Task Contract Epoch `K` 是本 task 的公开语义权威快照，其摘要至少绑定：task/issue、
priority/dependencies、`G`、派生 `W`、公开 requirement/spec authority raw digests、
scope、non-goals、角色 ownership/forbidden boundary/expected seam、public interface/
schema、decision precedence、actor/command/SHA/event identity、transition/routing/error
class、side effect、role visibility、Tester/Worker handoff schema、mandatory acceptance
类型/impact-selection rule 和 unknown-problem policy。它不是角色 prompt；它是
Test/Worker 两份实际 Launch Envelope 共同引用的、字节一致的公开部分。

历史 #85 没有完整、独立、可寻址的 `K` 文件；Issue/comment、heartbeat、#90 interface
packet 和 Orchestrator prompt 只承载了它的不同碎片。因此 `K` v0.1 是本轮反省提出且
经 Human 讨论确认的缺口修复设计，**尚未**成为当前仓库已实现能力。#93 必须先冻结
它的最小 schema、canonical encoding/digest、revision 和 lane binding，后续任务才可
声称自己受到机器可验证的 `K` 约束。

`K` v0.1 只需要一个封闭的 canonical JSON，最小字段为：

```text
schema_version
task(issue, task_run)
governor(commit, workflow_contract_path, derived_workflow_contract_blob)
revision(id, predecessor_digest, change_authority)
public authorities + raw digests
objective + public requirements
scope(included, excluded)
role boundaries + expected seams
public interfaces + decision rules
acceptance-impact obligations
unknown-problem policy
```

它不得演化成新的大型 executor，也不得包含 owner Test source/node/literal/fixture/
mutant、Implementation source、面向 hidden Test 的提示或 transient runner receipt。
精确 owner Test 执行计划属于 Human/Tester 可见的 `T` receipt；Worker 只消费 `K` 中
的公开能力和规则。

Orchestrator 的权威副本存放在其管辖 worktree 的 ignored state：

```text
.agent-state/task-contracts/<issue>/<task-run>/K0.json
.agent-state/task-contracts/<issue>/<task-run>/K1.json
.agent-state/task-contracts/<issue>/<task-run>/revision-log.jsonl
```

独立 Git worktree 不会自动看到主 worktree 的 untracked `.agent-state`。因此 dispatch
前，Orchestrator 必须把 exact K bytes 分别复制到 Test 和 Worker worktree 的同一
相对路径，验证两份 SHA-256 都等于权威副本，再让每个角色只读取自己的 lane 副本。
Subagent 不得通过绝对路径读取或修改 Orchestrator 中央副本；Launch Envelope 携带
lane-local path、revision 和 digest，角色返回时必须回显。`K` 不进入 Test、
Implementation、Candidate 或最终 PR；GitHub issue 可额外记录公开摘要/digest 作为
持久审计，但不取代 raw bytes。

公开 scope/requirement、interface/schema、precedence、identity/routing/error、side
effect/ownership、role visibility、handoff schema、mandatory acceptance 定义或 `W`
发生变化时，必须生成新 `K`。只修 Test 实现而不改变公开行为、修改 Worker code、
新增 receipt、runner 变化或未纳入 authority inventory 的纯文档编辑不改变 `K`。
有限自举 v0.1 不做“语义等价”猜测：任何 contract-bearing authority raw bytes 变化
都产生新 `K` revision。

Gate 1 前，`K` 可在 Human 可见的 change control 下修订；所有受影响 lane receipt
重新证明 ready，但未污染 Implementation source 可以继续使用。Gate 1 批准后，
`K` 与 `T` 一起冻结；如必须改变，当前 `S` 终止并进入 terminal Reviewer，新 `K`
需要新的 Test Gate 和 Human approval，但 source salvage 与 acceptance evidence
复用仍按不同资产处理。改变 `K` 不等于改变 Git baseline；只有 `G` 变化才叫
rebaseline。

每个 `K` revision 必须记录：`old_K/new_K`、changed authority blobs、semantic diff、
change class、affected public obligations、invalidated Test/Worker receipts、Test Impact
Set disposition、source salvage inventory 和 Human decision。Orchestrator 只能提出并
传播 revision，不能自行把 Candidate failure 改名为 contract change 来规避 correction。

维护关系必须按下表处理：

| 变化 | 是否新 `G` | 是否新 `K` | 证据处理 |
| --- | --- | --- | --- |
| 前置 Implementation 合入且成为新代码基线 | 是 | 仅当公开合同同时变化 | 两条 lane 从新 `G` fresh prove；source 可 salvage |
| 公开 precedence/interface/ownership 改变 | 否 | 是 | 受影响 lane receipt 失效；Gate 1 后终止当前 series |
| Gate 1 前只修 Test code，公开行为不变 | 否 | 否 | 产生新 `T` tip并重跑 affected prevalidation；Worker 不重启 |
| Gate 1 后发现 Test bug | 否 | 仅公开合同也错时才是 | 当前 series 终止；新 exact Test 必须重新 Human approval |
| Worker修复 Implementation | 否 | 否 | 消耗一次 correction，保持 `I(k-1)→Ik` lineage |
| Process/Environment invalid run | 否 | 否 | 恢复后重跑同一 Candidate；不消耗 correction |
| Candidate 3 valid FAIL | 否 | 否 | terminal Reviewer；不得借“新 epoch”自动重置预算 |

#### 9.1.3 Candidate 与 correction 计数

因此唯一有效的计数是：

```text
I0 + frozen T → Candidate 0        # 初始组装，不消耗修正机会
Candidate 0 FAIL → correction 1 → I1 → Candidate 1
Candidate 1 FAIL → correction 2 → I2 → Candidate 2
Candidate 2 FAIL → correction 3 → I3 → Candidate 3
Candidate 3 FAIL → correction budget exhausted
```

最多测试四个 Candidate。Environment/Process invalid run、重复执行同一 Candidate、
Human Gate 前的 Test 修订、以及 Orchestrator 对报告做泄漏审查都不消耗 correction。
不得再使用“Candidate attempt 1/3”同时指 Candidate 序号和修正机会。

### 9.2 适用范围与一次性自举例外

正常任务都应使用第 9.1 节模型。只有当任务本身正在修改当前 Loop、而旧合同无法
表达新模型时，才允许 `BOOTSTRAP-LIMITED`：

- Human 明确批准一个窄 bootstrap work package；
- 每个 package 只改变一个主要边界；
- 复用已合并的 P0 gate、#88 和 #90 能证明的部分；
- 不能因为旧 gate 无法表达新状态就声称新状态已经机器验证；
- 由 Human/Orchestrator 对 exact commits、diff、known-good/bad replay 和分支拓扑
  做一次显式 compensating review；
- governed package 成功后，经 final approval/PR 合入 exact accepted Candidate，
  同时交付 Test 与 Implementation；临时验收证据和 terminal lesson 不追加到该 head；
- 下一 stage 从已验收合入的 exact 基线开始，保留测试与实现成果，不回到最初 Governor。

当前 Phase 0、1、2、3 进一步使用 `MANUAL-BOOTSTRAP`：不得自主 dispatch lane、
迭代、重试、组装 Candidate、轮询 Gate、计算 correction 或 merge。每个开发、修正、
验证、PR 和 merge 动作都必须从一条明确 Human 命令开始；Agent 完成该有界动作并
返回 exact diff/evidence 后停止，Human 审阅并明确选择下一动作。准备 future issue/
index 只建立 tracking topology，不完成 phase，也不授权进入下一 phase。

> No autonomous Agent Loop iteration is authorized in Phases 0–3. No automatic
> lane dispatch, retry, Candidate assembly, gate polling, correction accounting,
> or merge. Each development/correction step begins only from an explicit Human
> command; the Agent produces the requested change and evidence; the Human
> reviews and verifies it; the exact final revision merges only after explicit
> Human approval.

Phase 0 [#94](https://github.com/autoMBD/autombd-rtd-config/issues/94) 先冻结本文，
Phase 1 再由 #57 的 canonical execution index 完成依赖绑定。第一项**实现** package
是 Timeout Package A [#95](https://github.com/autoMBD/autombd-rtd-config/issues/95)；
它只纠正 Agent 生命周期与确定性 command timeout 的边界。其 accepted merge 由
Human 选择为 #93 Governor 后，#93 才修复 `functional-development-v1` 当前无法安全
交接的结构边界：B0-0 的双 lane readiness、Test freeze、Candidate 0、三次
correction、terminal Reviewer 和 accepted-Candidate finalization；B0-3 的最小
artifact family 与统一交接守卫；以及 B0-1/B0-2 所需的 `K`、Tester Report、
Correction Envelope 结构容器。#93 不实现 #85 的具体 precedence/identity/routing
语义，也不得顺带实现完整 `loopctl`、recovery、notifications、GitHub executor 或
capability sandbox。

### 9.3 启动权威与 Orchestrator 责任

Orchestrator 不是把同一段 prompt 转发给两个角色。任何角色开工前，它必须先选择
exact `G`、从 `G` 派生并校验 `W`、编译共享 `K`，再生成两份不同的结构化输入文件：
Test Launch Envelope 和 Worker Launch Envelope。关系是：

```text
exact G ──derive──> W identity
   │
   └──compile public authority──> K / Shared Task Brief
                                  ├── Test-specific duties ──> Test Launch Envelope
                                  └── Worker-specific duties -> Worker Launch Envelope
```

`G` 不是交接文件，而是 exact Git commit identity；不得再创建一份可编辑的
“Governor file”与 Git 真值竞争。`W` 是从 `G` 派生的全局规则 blob，`K` 是两条
lane 共享的公开任务内容。Launch Envelope 是角色实际消费的结构化任务文件，prompt
只负责告诉角色从哪里读取它、把报告写到哪里、加载哪些 Agent 规则以及注意哪些
非任务运行边界。

#### 9.3.1 最小结构化交接文件族

#93 v0.1 只为 `functional-development-v1` 定义以下 canonical JSON kinds：

| Artifact kind | Producer → consumer | Purpose |
| --- | --- | --- |
| Task Contract `K` | Orchestrator → Tester/Worker | 绑定 `G/W`、公开 authority、需求、接口、decision rules、scope 和角色可见性 |
| Test Launch Envelope | Orchestrator → Tester | 启动 Tester 的 Test Gate 构建阶段 |
| Worker Launch Envelope | Orchestrator → Worker | 启动 Worker 的初始 Implementation 阶段 |
| Test Gate Ready Report | Tester → Orchestrator | 返回 `T`、Impact Set、full-chain/reference/known-bad 预验证和 unresolved |
| Implementation Report | Worker → Orchestrator | 返回 `I0..I3`、前序 Implementation、generality evidence 和 unresolved |
| Human Decision Record | Human adapter → Orchestrator | 记录 Gate 1 或 final gate 的 exact decision evidence |
| Candidate Test Envelope | Orchestrator → Tester | 绑定 exact `G/K/T/Ik/Ck`、manifest 和 frozen Impact Set |
| Confidential Tester Report | Tester → Orchestrator | 返回 PASS、Implementation FAIL、invalid run 或 Test/contract/integrity terminal diagnosis |
| Worker Correction Envelope | Orchestrator → same Worker | 返回脱敏但可行动的 production root cause 和 correction identity |
| Reviewer Launch Envelope | Orchestrator → Reviewer | 启动唯一一次 terminal review |
| Reviewer Report | Reviewer → Orchestrator/Human | 返回成功或失败终态 review，不触发返工 |
| Terminal Record | Orchestrator → Human/finalization | 记录 exact accepted-Candidate PR（含 Test+Implementation）或失败处置 |
| Handoff Guard Result | 统一守卫 → Orchestrator/获授权的 artifact producer | 机器返回本次检查的 exact 输入、检查状态、拒绝字段与证据；不是业务 verdict |

这些 artifacts 共享极小公共外壳：

```text
schema_version / artifact_kind / artifact_id / task_run / workflow_profile
producer_role / consumer_role / visibility
G commit / derived W path+blob / K revision+digest
predecessor artifact kind+id+digest
kind-specific closed payload
unresolved observations
```

公共外壳由各 kind 按阶段约束：`K` 不自引用自身 digest；Guard Result 在输入无法
解析、identity 尚未可信时，必须允许明确记录 unknown/unavailable 及其原因，不能
为了填全字段伪造 `G/K/predecessor`。只有成功 CHECKED 才要求该操作所需 identity
全部可验证；失败记录不授予继续执行的权限。

v0.1 不包含通用 `description_session` 或其他自由文本逃生口。任务相关信息必须进入
`K` 或该 kind 的合法字段；若现有 schema 无法表达新的规范性语义，就修订 `K/schema`，
不能把它藏进 prompt 或任意 notes。Prompt 只可携带 locator、Agent 规则提醒和不改变
任务含义的运行上下文。

Explorer Launch/Report 和其他 workflow profile 是显式后续扩展；新增 artifact 时只向
统一守卫增加 schema、合法局部边和 known-good/bad fixtures，不再新增独立 checker。

#### 9.3.2 Tester 与 Worker 的既有角色不变

“Test Gate authoring”是既有 **Tester** 的一个 phase，不是新的 `Test author` 角色。
同一个 Tester role：

1. 在 Gate 1 前依据 Test Launch Envelope 编写 Test Case、构建 Test Gate并完成
   full-chain/reference/known-good/bad 预测试；
2. Gate 1 后依据 Candidate Test Envelope 对 frozen Test Gate 进行只读执行，形成
   Confidential Tester Report；
3. 在两个 phase 都不得修改 production；Gate 1 后也不得再修改 frozen Test。

Worker 也保持现有唯一角色：先依据 Worker Launch Envelope 形成 `I0`，Candidate FAIL
后依据 Worker Correction Envelope 在同一 Worker、worktree 和 branch 上形成增量
`I1..I3`。无需创建 “initial Worker” 或 “correction Worker” 新身份。

Test Launch Envelope 至少携带：

```text
role=Tester / task phase=Test Gate authoring
issue/task ID + exact G
derived W path/blob assertion
lane-local K path/revision/digest + exact public authorities
public capability、interface、decision/routing/error obligations
Test ownership boundary（tests/reference/stubs）和 production-write prohibition
Test independence、Test Impact selection 和 full-chain prevalidation duties
Worker branch/worktree/source prohibition
T_READY receipt fields and non-ready/ambiguity return format
```

Worker Launch Envelope 至少携带：

```text
role=Worker / task phase=initial implementation
same issue/task ID + exact G
same derived W path/blob assertion
lane-local byte-identical K path/revision/digest + exact public authorities
public capability、interface、decision/routing/error obligations
Implementation scope、forbidden boundaries、expected existing seams
sanitized source-salvage inventory and Worker-owned generality duties
owner Test/source/node/literal/fixture/mutant/worktree prohibition
I0_READY receipt fields and non-ready/ambiguity return format
```

Orchestrator 规定的是公开能力、架构边界、角色 ownership、禁止领域和已有 expected
seams，不代替专业角色预先决定 changed files。Tester 自己设计 Test 文件/结构并给出
Impact Set 依据；Worker 根据 Governor 架构选择必要生产文件并解释 changed-path
rationale。只有仓库架构、公开 Issue 或 Human 明确冻结唯一路径时，具体路径才是强制
合同；否则“allowlist”只能是 scope/ownership guard，不能变成 Orchestrator 对角色
实现细节的遥控。

两份 Envelope 都不得把未来 owner Test literals 伪装成公开需求。Test Envelope 可以
包含 Human/Tester 可见的 confidential execution plan；Worker Envelope 只能包含 `K`
公开语义、公开 source 和经过污染审查的 source-salvage bundle。

#### 9.3.3 角色定义中的最小 prompt examples

#93 实现 schema/守卫时，必须把以下 locator-only examples 写入活动角色定义；在 #93
合入前它们只是目标设计，不能让当前角色因文件尚不存在而失败。

Tester — Test Gate 构建 phase：

```text
读取 AGENTS.md。
读取 .agent-state/agent-loop/<run>/inbox/test-launch.json。
按照该结构化文件构建 Test Gate 并完成预测试。
不要读取其中声明的 forbidden sources。
把结果写入指定的 test-gate-report.json。
```

Tester — Candidate 验收 phase：

```text
读取 AGENTS.md。
读取 .agent-state/agent-loop/<run>/inbox/candidate-test-envelope-C<k>.json。
把 Candidate 和 frozen Test 当作只读输入，执行其中指定的 Test Impact Set。
把完整结果写入指定的 tester-confidential-report-C<k>.json。
```

Worker — initial/correction phases：

```text
读取 AGENTS.md。
读取 .agent-state/agent-loop/<run>/inbox/worker-launch.json 或当前
worker-correction-envelope-<k>.json。
按照其中的公开任务合同执行。
不要读取其中声明的 forbidden sources。
把结果写入指定的 implementation-report-I<k>.json。
```

Reviewer — terminal phase：

```text
读取 AGENTS.md。
读取 .agent-state/agent-loop/<run>/inbox/reviewer-launch.json。
只执行终态审查，不修改 Test 或 Implementation，不发起返工。
把结果写入指定的 reviewer-report.json。
```

Subagent 的 chat response 只需回报 `report path + raw SHA-256 + status`；结构化报告才是
交付证据。无需哈希或严格验证实际 prompt/response 文本。

Orchestrator 的核心责任不是“把 prompt 转发出去”，而是：

1. 确认公开 spec 足以让 Test 和 Implementation 独立工作；
2. 生成权威 `K`，向两个隔离 worktree 部署相同 bytes，并把两份角色 Envelope 分别
   发给 Tester 和 Worker；
3. 给两条 lane 同一 `G/K` 和同一公开语义接口，不给 Worker owner Test；
4. 审查角色返回，决定是 lane 内继续工作、公开合同 change control，还是 ready；
5. Human Gate 前把所有 Test 隐藏判据映射回公开 authority；
6. Candidate FAIL 后先审计 Tester 的 confidential forensic report，再给同一个
   Worker 发完整但不泄漏 owner Test 的 Correction Envelope；
7. 维护 correction 账本和 `I0→I1→I2→I3` 连续性；
8. 在 terminal review 后按成功/失败选择 PR 或 issue 记录。

Orchestrator 对 Confidential Tester Report 到 Worker Correction Envelope 的语义审查
是 v0.1 明确接受的 LLM trust boundary：统一守卫验证结构、visibility、引用和禁止成员，
Orchestrator 负责判断公开 root cause 是否足够、自然语言是否泄漏 hidden Test。Owner
明确接受这一小部分由 LLM 执行；v0.1 不为此再建设语义 oracle。

实际 dispatch 可以由 Subagent API、Agent CLI 或后续 executor 完成。现有 #88/#90
只能证明一部分 identity/shape；它们尚不能生成 `K`、复制 lane snapshot、守卫整个
artifact family 或原子同步 revision。过渡期 Orchestrator 必须保存 K/Envelope/Report
raw digests、lane tips 和 manifest digests，并明确哪些是机器验证、哪些只是人工补偿，
不能把后者包装成工具能力。

#### 9.3.4 守卫失败路由：拒绝当前交接，保留既有工作

本节将 Owner 要求的失败处理固化为 #93 的交付合同；**尚未实现**于当前 #88/#90。
守卫只产生可复核检查结果，不修改业务文件、不派发角色、不自行改变 workflow
状态或 correction 计数。当前由 Orchestrator 执行以下局部路由，未来由 #85/#87
消费同一结构化结果；不在 #93 另造一个全局执行状态机。

**检查点与禁止前进的边界。** 出站输入在 consumer dispatch/continue 前检查；入站
报告在 Orchestrator 接受 ready/verdict、发布 Human Gate 或组装 Candidate 前检查。

```text
拟交接 artifact + exact predecessor + 已绑定运行上下文
    → guard CHECKED → consumer 可消费该 exact artifact / 接受该报告
    → guard REJECTED → 当前交接不成立 → producer 局部修复 → 新 artifact → 重检
    → EXEC_ERROR / TIMED_OUT / 证据不可写 → 保存现场 → 有界诊断 → 安全恢复后重检
```

`CHECKED` 必须对应本次操作、相同 raw digest、所需直接 predecessor 和合法局部边；
consumer 使用前再次确认 identity 未变。`run` 不能只凭“receipt 的 manifest digest
相同”继续，必须消费适用的成功 check 结果；`PREPARED`、`REJECTED`、超时、缺失
receipt 或旧成功结果都不能替代它。任一拒绝只使该 handoff/operation 未完成，不
自动把另一独立 lane、整个 Issue 或后续所有任务设为 BLOCKED。

**最小结果文件。** Handoff Guard Result 使用闭合 schema，至少记录：

```text
result identity + task_run + handoff/operation identity
guard/schema identity + checked artifact path/id/raw digest
适用 predecessor references + 已观测运行上下文
检查状态、执行阶段、command_started（未启动/已启动/不确定）
violations[{rule_id, artifact_ref, field_pointer, safe diagnostic}]
本次 invocation 的 exit/outcome 和可用证据 locator
```

这些是待 #93 schema 固化的字段语义，不是向旧 `W` 记录偷加新枚举。工具自身输出
按固定 schema 生成并由 consumer 检查引用，不再递归启动“守卫的守卫”。同次安全
可独立检查的字段尽量一次列出，避免一轮只暴露一个格式错误；不能为了聚合错误而
读取未授权文件或越过失败的 identity/security 检查。

拒绝诊断的可见性不能高于输入权限：发给 Worker 的内容只包含其有权读取的文件、
字段约束和安全诊断，不复制 confidential report 的 actual value、Test node/literal
或 raw body。修复 owner 按已记录交接关系和 artifact kind 的 producer 决定，不能
相信无效 payload 自称的 role。Orchestrator 仍负责自然语言脱敏和语义充分性。

**按责任局部路由。**

| 触发 | 修复责任和动作 | 恢复条件 / 不得做的事 |
| --- | --- | --- |
| 缺成员、类型/枚举错误、错误引用或摘要声明 | 原 artifact producer 根据 guard result 生成修复版；Orchestrator-owned Envelope 由 Orchestrator 修，角色 Report 由同一角色修 | exact bytes 和引用重检通过。不得伪造缺失 receipt、仅改 digest 掩盖源内容变化或以补格式名义修改业务结论 |
| `G/W/K`、cwd/HEAD、lane-local snapshot 不匹配 | Orchestrator 核对 authority 和实际 checkout，只恢复自己拥有的正确上下文/副本；同一角色继续 | 可恢复 canonical exact bytes 时不换 `K`；不是为了让记录“看上去匹配”而改 HEAD、覆盖用户改动或重新选择 Governor |
| 真正的 `K` 文件/公开语义需要更改 | 按 §9.4.3 生成完整新 revision、更新两份 Envelope 和双 lane ACK | v0.1 的 `K` raw bytes 一旦改变就有新 revision；不能用“格式修复”原地改冻结 K。Gate 1 后按 series 终止规则处理；未污染 source 保留 |
| 缺 predecessor、跳过 check、错误局部顺序 | Orchestrator 返回最后一个已验证交接点，补真实缺失步骤或纠正错误引用 | 不伪造一个 CHECKED 结果、不跳过前序。未依赖此边的已完成步骤不重做 |
| Report 引错 Implementation tip / 实际 ancestry 不连续 | 先核对是 report 错还是 Git 实体错；前者修 report，后者由同一 Worker 在原 lane 保留实现并修复合法 lineage | 不把 sibling-from-Governor 当增量交付；不通过新 Worker/清空 worktree 处理；实际业务代码缺陷仍走 Tester verdict |
| Worker-visible 输入含 confidential Test 信息 / 不安全路径 | 出站即拒绝且不发送；Orchestrator 重新脱敏或恢复已验证路径 | 若尚未发送，不宣告 Worker 已污染；若已实际泄漏或越界，记录受影响对象，按 §10.2 integrity/security 处置，不能只补一份干净报告掩盖 |
| 守卫本身异常、I/O 错误、执行 timeout | Orchestrator 做一次有界诊断，保留运行状态/日志，先判断命令是否启动及是否留下副作用 | 没有可用成功检查就不交接；已经启动的写操作必须证明幂等或完成 owned cleanup 后才能重试，禁止盲目 replay |
| schema 无法表达合法任务，或角色报告业务歧义 | 不是普通字段修复；Orchestrator 按公开 authority 判断，必要时请求 Human 语义决策和 `K/schema` revision | 不为了让文件过关偷偷添加成员、扩大 scope、重分类 Implementation FAIL 或改变 Test |

如果标准结果输出路径本身 alias/越界或不可写，**不得向该危险路径强写 receipt**。
以 stderr/exit 和外层受控调用记录保留失败；如有预验证的安全 evidence 位置可写，
在那里记录证据不可用。无可信成功结果时仍拒绝该交接。当前 #88 的两条 early
path-alias return 没有标准 receipt；#93 必须覆盖这一失败路径，而不是声称它已闭环。

**修复版如何交接。**

- 被检查的原文件及拒绝结果保持不变；修复版使用新 `artifact_id`/路径，记录
  `replaces` 和 `guard_result_ref`。一般 Envelope/Report 修复保持同一 `G/K`；
  如修改的是 K 本体则使用其 revision 协议，不混为普通报告修复。
- 需要角色补交时，Orchestrator 在既有 Launch/return 协议内使用一个窄的
  **delivery-repair** 模式，引用拒绝结果、原报告及新输出位置；不是新的 Worker
  Correction Envelope，也不是新角色。Prompt 仍只给该修复文件的 locator。
- 同一 Tester/Worker/Reviewer 在原 worktree 返回修复文件；Worker implementation
  tip 不因“报告格式错”而重写。Reviewer 只修补同一次终态审查的报告交付，不再审
  第二次、不修改 Test/Implementation、不借格式修复发起业务返工。
- 已有执行证据完整、identity 一致时可重用以补交报告；若真实证据缺失、截断或
  identity 漂移，必须恢复/重建受影响证据，不能直接填写 PASS。业务结果改变要进入
  正常 verdict 路由，不能伪装成 report-only repair。

**重检停止条件与计数。**

1. 确定性输入错误不对相同 bytes/上下文原样重试；先做可说明的局部修正，再重检。
2. 未知执行问题遵循 §10 的一次有界诊断。相同可复核失败再次出现且没有新修复依据
   时停止自动空转；保留该 operation 为未完成，报告事实/已试动作/所缺条件。
   不能安全自行恢复时请求 Human 决策，但不自动停止整个 series 或新建全局规则。
3. delivery repair 不新增、不回退、不重置 `correction_count` 或 `candidate_index`。
   correction 2 的 Report 未通过时，仍是 correction 2 的交付未完成；若 C2 尚未
   组装就不生成它，若 C2 已存在则只修复/重建相应证据，不冒造 C3。
4. TIMEOUT/REJECTED 本身不证明 PROCESS 豁免或 Implementation 缺陷。如果本任务
   **正在测试守卫/timeout 功能本身**，其错误拒绝、错误放行或未按公开 deadline
   结束，是 Tester 可报告的 Implementation FAIL，照常触发 correction。
   同样，不能用“补交报告”隐藏已经证明的产品缺陷；有争议时保留计数，交 Human
   分类，不自行通过重命名失败来免计。
5. 只有 mandatory evidence 或隔离/安全破坏无法在受影响 operation 内恢复、必须
   更换 frozen G/K/T，或其他 §12.1 条件才进入 terminal Reviewer。普通 handoff
   rejection 不触发 Reviewer。

**#93 必须预验证的局部路径。** 使用 synthetic artifacts/receipts，范围限于新改
交接守卫和受影响兼容接口，不新增全量 suite：

| 路径 | 必须证明 |
| --- | --- |
| CHECKED + exact 输入 | 可推进同一交接，绑定本次 predecessor |
| REJECTED / PREPARED / missing receipt 后尝试 run | 不调用被保护命令；不接受 ready 或 Candidate |
| 缺字段后由原 producer 修复 | 原拒绝记录保留，新文件过检，同一 source tip、K 和计数不变 |
| stale/corrupt lane copy | 恢复 canonical bytes 后继续；真正 K 变更不能绕过 revision/ACK |
| 路径 alias / evidence 输出失败 | 不写危险位置、不报 CHECKED；有安全失败证据或明确 evidence unavailable |
| 子命令 timeout / 部分副作用 | outcome 与是否启动可区分；不能无条件 replay 或转成 PASS |
| 连续同因拒绝 / 另一独立 lane 活跃 | 不无限同输入重试；只暂停受影响交接，不自动全局阻塞 |
| confidential 输入被拒绝 | 不向 Worker 泄漏 raw 诊断；实际未 dispatch 与已泄漏分开处理 |
| 守卫作为被测产品出现缺陷 | 不被 PROCESS/HANDOFF 豁免逻辑吞掉真实 Implementation FAIL |

### 9.4 同一 Governor 上的两条独立开发 lane

Human Gate 1 **不是 Worker 的启动门**。Test lane 和 Implementation lane 在同一
Governor 上独立推进，可并行执行以缩短等待时间。

#### 9.4.1 Test lane

Tester 可以在自己的 Test branch 内提交多次，但只有满足全部完成条件后才向
Orchestrator 返回“Gate ready”：

- owner Test 明确覆盖公开 acceptance，范围与 issue priority 相称；
- 每个强制 expected behavior 都可追溯到公开 spec/interface，不依赖实现现状；
- Test 不读取 Worker branch，也不从 Implementation 反推断言；
- Governor 上有明确 RED/negative discrimination；如某类任务不适用，给出理由；
- known-good reference/stub PASS，known-bad mutants 在预期边界被拒绝；
- 在 clean disposable checkout 中完成 discovery/import/CLI/cwd/temp/lifecycle 等
  与未来 Candidate 相同的完整链路预验证；
- 必要时使用 disposable stubs 构造预测试，但 stub 不进入产品、Candidate 或 Worker
  输入，也不能只复制 owner Test literals；
- 冻结并运行本 task 的 Test Impact Set：新增、修改和由公开依赖关系证明受影响的
  unit/integration/generality gate；不得把全量存量 unit suite 当作默认保险；
- Test manifest、prevalidation commands、exit codes、environment 和 raw digests
  完整；
- 经过 Orchestrator 的 scope/spec/quality 审计，确认没有循环自证和范围膨胀。

“预验证”是 Test owner 的交付责任，不是 Candidate 失败后再逐层补 discovery、
loader、路径、fixture 或平台前提。Test lane 尚未完成这些证据时，Orchestrator
不得发布 Human Gate。

`full-chain` 与 `full-suite` 必须严格分开：`full-chain` 是让**选定的** Test Impact
Set 从 discovery/import/CLI/cwd/temp/fixture 到 result collection 走完整真实拓扑；
`full-suite` 是执行仓库全部存量测试。前者是 Gate ready 条件，后者不属于 task-level
Tester，也不参与 Candidate verdict 或 correction 计数。独立 CI/release gate 即使
另行运行 full suite，其结果也只是独立 repository-health 证据，不能冒充本 task 的
Tester result。

Test Impact Set 在 Gate 1 前依据公开 Implementation scope、expected seams 和依赖关系
冻结，因为 Human review 可以早于 Worker 完成。它只包括：新增 owner tests、修改 tests、直接
覆盖 changed public capability 的现有 tests、由明确 dependency edge 证明受影响的
regression、Worker-owned generality，以及 `K` 明确要求且受影响的 integration/vendor/
E2E gate。无依赖关系的存量 unit tests、仅为“保险”加入的邻接模块和全量 pytest
明确排除。

`K` 保存公开 capability/validation-type 级别的 impact obligations；exact Test
file/node/parameter 清单保存在 Human/Tester 可见的 confidential execution plan，
不得发给 Worker。Worker ready 后，Orchestrator 必须在首次组装前执行 coverage join
check：actual changed paths 及其公开 dependency edges 必须已被 frozen Impact Set
覆盖。Worker 可以选择实现文件，但不能通过意外扩大 production surface 绕过 Gate。
若 uncovered impact 在 Human approval 后才暴露，不得临时追加 owner Test；当前
series 按 Test Gate/contract 边界处理，未污染 Implementation source 保留给后续合法
series。后续 correction 保持同一公开 capability/scope 和 frozen Impact Set；如果
实现证明原 scope 无法完成，应升级为公开 contract decision，而不是临时扩测或硬编码
文件 allowlist。

#### 9.4.2 Implementation lane

Worker 同样可以在自己的 Implementation branch 内提交多次，但只有满足全部完成
条件后才返回 `I0 ready`：

- 只消费 Launch Envelope 中的公开 spec、接口合同和经过授权/污染审查的 source；
- 不读取当前 owner Test source、branch/worktree、reference mutants、case literals，
  也不得借历史未接受 Test/Candidate refs 访问隐藏 gate；已合入 `G` 的回归测试不因
  其历史来源是 Test lane 而被自动禁止；
- 以 TDD 编写 Worker-owned generality tests，输入与 owner gate literals 独立；
- 实现完整公开能力，不以“猜中 hidden Test”为目标；
- 自己决定实现所需 changed paths，但每个路径必须落在公开 capability/scope 与角色
  ownership 内，并提供 architecture/dependency rationale；
- 所有偏差、歧义、unknown 和未满足依赖如实返回，不自行扩大 scope 或阻塞等级；
- Implementation manifest、generality commands/results、tip SHA 和 parent lineage
  完整。

Tester 或 Worker 若发现公开合同歧义，都必须在 lane ready 前返回 Orchestrator，不得
自行选择一种解释。若语义 identity 改变，两条 lane 都必须基于新 identity 重新证明
受影响的 ready evidence，但已有未污染 Test/Implementation source 不必丢弃。

#### 9.4.3 `K0→K1` 歧义处理与双 lane 同步

`K` revision 不是 Agent 在自己 branch 内修改一份共享文件。发现歧义的角色先在安全
点结束当前 turn，返回结构化 `CONTRACT_AMBIGUITY`：observed K revision/digest、公开
authority locators、两种可成立解释、受影响 obligation、已完成且可保留的工作和
是否还能安全进行不相关工作。Tester 可以另附只给 Orchestrator 的 confidential
诊断，但 owner Test source/literal 不得进入公开报告或 Worker 输入。

有限自举期间不假装 Subagent 具备可靠的“暂停函数 A、继续函数 B”内部调度器。默认
行为是：报告歧义的 lane 在安全点整体返回并保留 tip；Orchestrator 只把该 lane/该
交付操作标为未 ready，而不自动阻塞整个项目或依赖计划。另一 lane 只有在歧义与其
剩余工作有明确独立性时才可继续；否则 Orchestrator 通过 message/interrupt 让它也在
安全点返回。澄清后使用同一 lane 的 follow-up 继续，禁止 fresh restart。

Orchestrator 按公开权威判定：若 `K0` 已唯一明确，只发送带 locator 的解释，不产生
新 revision；若 contract-bearing raw bytes、public interface/precedence/identity/
routing/error、role boundary 或 mandatory acceptance 定义变化，则编译完整替代快照
`K1`，不能原地编辑 `K0` 或只发一个 diff。存在两种合理公开解释时必须先取得 Human
语义决策；这是一项需求澄清，不是新的 Human Test Gate。

同步顺序固定为：

```text
K0_ACTIVE
  -> CONTRACT_AMBIGUITY_REPORTED
  -> K1_DRAFT / Human semantic decision（如需要）
  -> K1_PUBLISHED：K0 不再接受新的 ready receipt
  -> exact K1 bytes 复制到 Test/Worker lane-local .agent-state
  -> 生成分别引用 K1 的 replacement Test/Worker Launch Envelopes
  -> locator-only follow-up 通知两个既有角色读取 replacement Envelope
  -> ACK_TEST_K1 + ACK_WORKER_K1
  -> K1_ACTIVE
```

当前没有真正的原子 broadcast API；“publish”实际是 Orchestrator 把 exact K1 与两份
replacement Envelopes 写入各 lane-local inbox，再向两个现有角色发送 locator-only
follow-up。角色用结构化 ACK/report 回显 `task_run`、old/new K、verified digest、current
tip、invalidated receipts、salvaged work 和 resume point。任一 ACK 缺失、digest 不同或
角色继续返回 K0 report 时，Gate-ready、I0-ready 和 Candidate assembly 都不得发生。
#93 以后可机器化这组状态；在此之前它只是明确标注的人工补偿协议，不能声称
#88/#90 已实现。

Gate 1 前允许 `K1`：两条 lane 只重证受影响部分，Worker 在现有未污染 tip 上适配；
已发布但未批准的旧 Test packet 必须撤换。Human 批准 exact Test 后，当前 `G/K/T`
series 冻结；如公开语义仍必须改变，当前 series terminal，不得在原 series 偷换 `K1`
或 Test。只修改隐藏 Test 实现且公开语义不变不产生新 `K`；只修改 Worker code 也不
产生新 `K`。

Candidate failure 与 contract ambiguity 必须分开：若 `K` 已唯一规定“F1 at
`tester_passed` → `ILLEGAL_TRANSITION`”，Implementation 返回 `OUT_OF_ORDER_EVENT`
就是 Implementation defect，进入一次 Worker correction；Orchestrator 不得为了规避
correction 事后改称 `K` 歧义。只有公开 `K` 本身无法唯一推出这两个错误码中的哪一个，
才是 contract ambiguity，并在 Human 澄清后产生新 revision。

### 9.5 两条 lane 的完成交接合同

Tester 的 ready receipt 至少包含：

```text
Governor / derived Workflow Contract / K revision+digest / public-interface digests
Test tip + parent + tree
owned paths and Test manifest digest
requirement-to-Test trace（公开 requirement IDs，不含给 Worker 的 case 细节）
public impact obligations + confidential exact Test Impact Set digest
每个 selected/excluded test family 的 dependency rationale
RED/reference/stub/known-bad/full-chain commands and normalized results
environment/topology identity
unresolved/deviations
```

Worker 的 ready receipt 至少包含：

```text
Governor / derived Workflow Contract / K revision+digest / public-interface digests
Implementation tip I0 + parent + tree
owned paths and Implementation manifest digest
public-requirement coverage
Worker generality commands and normalized results
unresolved/deviations
```

两条 lane 使用两个独立状态：Test receipt 通过审计后产生 `T_READY_FOR_HUMAN_GATE_1`；
Worker receipt 通过审计后产生 `I0_READY_FOR_ASSEMBLY`。前者不等待后者。Orchestrator
在发布 Gate 1 前只需证明 `T` 与 `G/K` 一致、Test scope/impact/prevalidation 完整且
没有 blocking deviation；它不得把 Worker 完成状态加入 Human Test approval。

首次组装时才执行 join：绑定当前 `G/K` 的 `Human-approved(T)` 与
`I0_READY_FOR_ASSEMBLY(G,K)` 必须同时成立，actual Implementation diff 必须通过
coverage join check，且 lane ownership 无冲突。Test ready 不代表 Implementation
正确，Implementation ready 也不代表 owner gate 通过；两者只分别证明自己的交付合同。

对于 #85 一类 precedence/identity/routing 任务，public interface 必须另带一个小型
semantic annex：

- ordered decision/precedence table；
- actor/command/SHA/event identity matrix；
- transition pre-state、result 和 error class；
- side effects/ownership；
- real loader/import/CLI topology；
- small known-good/bad vectors；
- explicit non-goals。

annex 是 Orchestrator 负责的跨角色交接合同，不是 Test source 的摘抄。Tester 用
reference/stubs 预验证它，Worker 独立实现它；Gate packet 展示它只是为了说明 exact
Test 的公开依据，Human 的唯一审批对象仍是 Test。#90 继续只负责 closed shape/
digest，不被膨胀成业务语义 oracle。

### 9.6 Human Review Gate 1 与 Test freeze

Human Gate 1 在 `T_READY_FOR_HUMAN_GATE_1` 后立即发布，不等待 `I0`。Gate packet
必须绑定：

```text
G
K + workflow-contract/public-interface identity
T + Test manifest/prevalidation receipt
public impact obligations + confidential Test Impact Set digest
Test lane ownership and exclusions
known unresolved/nonblocking observations
join condition and future Candidate assembly plan
```

Human 把整个 packet 作为**一个 Test Gate**审核：Test scope、公开需求可追溯性、
Impact Set、预验证充分性、公开接口依据，以及 Test 是否独立于 Implementation 都是
exact Test 的支持证据，不是额外审批对象。Human 不分别审批 `G`、派生 `W`、`K`、
Impact Set 或 prevalidation，也不审核 Worker code、manifest、generality 或 ready
状态。Human approval 的含义是：

- 批准 exact `T` 作为本 task 唯一 owner gate；
- 记录该 Test 当时绑定的 `G/K`、Impact Set 和 prevalidation identity，使后续不能在
  保持同一 Test approval 的同时偷换测试依据；
- 授权 Orchestrator 在匹配该 `G/K` 的 `I0` ready 后构造 `C0`；
- **不是**审核、批准或宣告任何 Implementation 已通过 owner gate。

Human change request 时，Tester 可继续修改 Test branch 并重复全部受影响预验证。
若只修 Test 表达错误且 `K` 不变，Worker lane 不受影响；若公开语义合同改变，生成
新 `K`，Tester 和 Worker 分别重新证明与新 identity 一致，但 Worker 在原有未污染
Implementation 进展上适配而不是从零重写。两种情况都不产生 Candidate，也不消耗
correction。

一旦 Human 批准 exact `T`：

- `T` 到 task 终止不得再改；
- 所有 `C0..C3` 必须使用同一个 Test parent/tree/manifest；
- 新增或删减 owner case、修改 expected、修 Test bug都要求终止当前 Candidate
  series，并建立新的 exact Test approval；只有公开合同改变时才同时建立新 `K`，
  不能用“Test correction”在当前 series 偷换 gate；
- 若批准后才发现 Test 本身错误，当前 task 以 `TEST_GATE_INVALID` 终止，不消耗
  Worker correction，随后执行 terminal Reviewer；是否开启 replacement task 由
  Human 决定。

严格 freeze 会提高 Gate 前预验证成本，但它消除了 Candidate 过程中 Tester 与
Worker互相追逐、以及失败后修改 Test 让实现“通过”的循环自证。

### 9.7 Candidate 0 与 Tester 的只读职责

Orchestrator 用 frozen `T` 和 exact `I0` 组装 `C0`：

- ordered parents 明确；
- merge-base exact `G`；
- Test 与 Implementation manifests 各自完整；
- tree 是两条 lane 相对 `G` 的 direct union；
- 无 merge-only edits；
- 验收和最终 Human approval 前，Candidate/Test 保持在开发与验收 refs，不直接推入
  主线；成功后 exact `Ck` 连同 Test 通过 PR 合入，临时 acceptance receipts 不注入它。

`C0` 是首次真实集成和 owner gate 执行，**不是 correction Attempt**。Tester 可读取
完整 Candidate，包括 Implementation 和 Test，但必须：

- 把 Candidate 当作只读；
- 不修改 Implementation；
- frozen Test 也不得修改；
- 从头运行 frozen Test Impact Set 和该 task 的其他 mandatory acceptance，不运行
  无影响的存量 unit suite；
- 忠实记录每条命令、环境、exit、node/result、raw digest 和 Base comparison；
- 区分 valid Test result 与 Environment/Process invalid run；
- 对每个 valid FAIL 分析 Implementation 的 first divergence、生产代码控制流、
  root cause、置信度和备选原因，形成只交给 Orchestrator 的 confidential forensic
  report；不直接向 Worker发送，也不修改 production。

如果 `C0` PASS，进入 terminal Reviewer；如果 FAIL，先进入第 9.8 节，而不是直接
换 Worker 或重建 Test。

### 9.8 失败审查、去泄漏和责任分类

Tester 的原始报告只交给 Orchestrator。Orchestrator 必须先做两项独立审查。

#### 9.8.1 Validity/ownership classification

一个新的 failure signature 最多做一次 bounded diagnostic：

- wrong cwd/HEAD/digest、runner crash、ACL/temp residue 等机械 invalidity 由现有
  guard/原始证据判定；恢复后重跑**同一个 Candidate**，不产生 correction；
- Base-equivalent 或 out-of-scope observation 记录后仅绕开受影响步骤，不盲目升级；
- frozen Test 与公开合同不一致时，task 终止为 Test Gate invalid，不修 Test；
- 公开合同存在歧义且无法从批准材料唯一裁决时，task 终止为 contract handoff
  failure，不把它伪装成 Implementation defect；
- 只有 valid Candidate result 且 expected 可由批准公开合同唯一推导时，才是
  Implementation failure；
- 模糊分类由 Human 裁决；Orchestrator 不能自判 PROCESS/TEST_CONTRACT 来规避
  correction，也不能把所有未知都升级成 P0 blocker。

#### 9.8.2 Confidential Tester Forensics Report

Tester 能读取 frozen Test 与 Candidate Implementation，因此必须完成根因分析，而
不是只返回 `expected/actual` 或把 pytest 输出原样转发。其 confidential report 只交
给 Orchestrator，至少包含：

- `G/K/T/Ik/Ck`、执行命令、runner/environment 和 raw result digest；
- failing owner nodes、完整断言和 hidden case context；
- 公开 requirement/semantic-annex row；
- observed behavior、expected behavior 和 first divergence；
- production file/symbol/line、调用链或 decision path；
- Implementation root-cause hypothesis、置信度、备选原因和排除证据；
- Test/Contract/Implementation/Process/Environment 责任建议及依据；
- 受影响 public surface 和未受影响边界。

Tester 只能分析和报告；不得修改 Implementation、替 Worker写 patch，或直接向 Worker
发送任何内容。

#### 9.8.3 Worker Correction Envelope

Orchestrator 先审查 confidential report 的 validity、责任分类、根因充分性和 hidden
Test 泄漏，再生成给**同一 Worker**的 Correction Envelope：

```text
task / G / K / previous Implementation / correction index
public requirement or semantic-annex row
affected production capability/API/checkpoint
public expected behavior
observed production behavior
first public-contract divergence
production file/symbol/line/control-flow diagnosis
root-cause hypothesis + confidence + bounded alternatives
public reproduction vector（仅当它已是公开合同内容）
affected scope / non-goals / required correction outcome
raw-report digest / envelope digest / disclosure-review receipt
```

必须删除 owner Test 文件、函数/node、源码/行号、fixture/case/parameter literal、
reference mutant 名称/实现/差异、Test-only helper、assert expression，以及任何只
存在于 hidden Test 的 expected behavior或“怎样让某条用例通过”的提示。production
文件、symbol、行号和控制流属于 Worker 自己的实现，可以且应当保留。

若某个 literal 本身是公开合同值，只能通过对应 authority row 引用。Orchestrator
必须完成四项字段级检查：

1. **authority completeness**：每个 expected 都能追溯到 `K`；
2. **diagnostic completeness**：包含 first divergence 和可行动 root cause，不只给症状；
3. **non-disclosure**：所有非公开值、Test path/node/helper/mutant 均已删除；
4. **anti-fitting**：没有提供具体 assert、hidden parameter 或 case-passing recipe。

检查结果与 raw-report/envelope digest 一起记录。无法形成既不泄漏又足够行动的
Envelope 时，不得把信息缺口转嫁给 Worker；由 Orchestrator补充公开合同，或按
Contract Epoch change control 结束当前 series。

### 9.9 三次增量修正与四个 Candidate 上限

确认 Implementation failure 后：

1. `C0` FAIL 触发 correction 1；同一个 Worker 在 `I0` 上修正，返回后继 `I1`；
2. Orchestrator 验证 `parent/ancestor(I1, I0)`、changed paths、generality 和 Worker
   Correction Envelope identity，再与同一 frozen `T` 组装 `C1`；
3. `C1` FAIL 触发 correction 2，得到 `I2` 和 `C2`；
4. `C2` FAIL 触发 correction 3，得到 `I3` 和 `C3`；
5. `C3` FAIL 后不再修复、不换 Worker、不重置数字，进入 terminal Reviewer。

Worker 每次只得到当前 Worker Correction Envelope、公开合同和自己已有的
Implementation history；不得得到 owner Test。Worker 可增加/修改自己的 generality
tests，但不能删除公开能力或弱化合同来迎合失败类别。

以下行为明确禁止：

- 从 `G` 新建 sibling commit 伪装成 `Ik`；
- 因 Test/Process/Environment 问题丢弃 Implementation；
- 把 Test SHA 换掉后继续沿用同一 correction 账本；
- 用“fresh Worker”重置三次修正机会；
- 将失败分类改名后重试同一实现并声称新 Candidate；
- 超过 `C3` 继续秘密修正。

如果 contract/Governor 必须改变，当前 task 终止并进入 terminal Reviewer。新 task
可 salvage 未污染 Implementation source，但必须建立新的 Test、Human approval 和
Candidate 0；旧 correction 数字不能伪装成新 task 的 acceptance evidence。

### 9.10 Terminal Reviewer：成功或失败都恰好一次

满足任一条件时进入 Reviewer，进入即表示 task 不再返工：

- 任一 `C0..C3` 获得 Tester functional PASS；
- `C3` 获得 valid functional FAIL；
- frozen Test、contract handoff 或 integrity blocker 令当前 task 无法继续；
- Human 明确终止。

Reviewer 读取 exact terminal Candidate（如存在）、frozen Test、Implementation
lineage、Tester forensic evidence、Worker Correction Envelopes、公开合同和 diff，
恰好执行一次：

- Tester PASS 路径：审查 scope、generality、ownership、代码/文档质量、是否 test-fit、
  lane continuity、开发期隔离及最终 PR 与 accepted Candidate 的身份一致性；
- Tester FAIL/invalid 路径：审查失败归属、三次 correction 是否真实增量、是否泄漏
  owner Test、是否错误丢弃实现、剩余缺陷和可 salvage 资产；
- 两条路径都记录 lessons/observations，但不修改 Test 或 Implementation；
- Reviewer 不发起新的 Attempt；finding 不能在同一 task 返工。

§9.14 的新功能交付规则落地后，成功路径 Reviewer Report 还包含结构化 KPI 建单
决定：产品归属、feature/变更类型、需新建或复用的 KPI 用例及来源身份。Reviewer
只做审查和交接，不获取宽泛 GitHub 写权限；实际建单由 Orchestrator 在提 PR 时
完成。非 RTD CfgFile CLI 任务不要求 KPI；缺少 KPI 结果不阻塞功能 Reviewer。

Terminal 状态：

| Tester terminal | Reviewer result | Task result |
| --- | --- | --- |
| PASS | APPROVED | SUCCESS，可进入 Human final review/PR |
| PASS | REJECTED / blocking finding | FAILURE，记录后结束，不在本 task 修复 |
| Candidate 3 FAIL | 任意忠实 review 结果 | FAILURE，记录后结束 |
| Test/contract/integrity invalid | 任意忠实 review 结果 | FAILURE，记录后结束 |

Reviewer 可在独立 review branch 生成精确 lesson commit 便于审计，但该 commit 永远
不是产品 PR tip，也不得作为 Candidate child 合入 `master`。长期 lesson 若要进入
仓库，另开 governance change；当前任务只把 Reviewer result/lesson digest 发布为
issue/PR evidence。

### 9.11 成功 PR、失败记录与主分支拓扑

#### 成功

当且仅当 Tester PASS 且 terminal Reviewer APPROVED：

1. Orchestrator 创建 PR，head 为 exact accepted Candidate `Ck`，不是单独的 `Ik`、
   `T` 或 Reviewer lesson child；
2. `Ck` 保留 ordered parents `[T,Ik]`、exact merge-base `G` 和两个 manifest 的
   direct union。PR 同时交付 frozen Test 与最终 Implementation，包括 generality
   tests；不能删除 Test-only paths 或重新组装一棵不同的交付树；
3. Human final packet 同时绑定 `G/T/Ik/Ck`、PR head/tree、Tester PASS 和 Reviewer
   result。Gate 1 的 Test approval 不替代这次最终审批；
4. Human final approval 后通过该 PR 合入同一个 `Ck`；不单独推 Test、改用
   Implementation-only PR，或把 lesson/其他新编辑追加到获批 head；
5. finalization verifier 或人工补偿检查 `PR head == accepted Ck`、`G..Ck` 的 Test
   与 Implementation 完整性、scope/ownership 和 no merge-only edits。失败 Candidate
   与临时 confidential/reference evidence 不成为交付内容；已有 `G` 历史不重写；
6. merge 后运行 bounded trust-root verification，确认远端包含 exact accepted `Ck`
   及批准的合并结果，并在 issue 记录 exact remote tip。

提 PR 步骤同步消费 Reviewer 的 KPI 建单决定：符合 §9.14 范围时创建或复用一个
关联 source PR/exact Candidate 的待 merge KPI Issue。建单不修改 Candidate tree，
也不自动启动个人端 Agent。只有该 Candidate 的 Human final approval、源 PR
实际 accepted merge 及 Human 启动 KPI Issue 三者满足，才进入独立 KPI 路由。

这里的“包含测试”指两个 lane 中按合同交付的测试源码与必要测试资产，不把 ignored
reference overlay、一次性 stubs、运行日志或 confidential 报告自动升级成 PR 文件。
**开发隔离、验收同树、交付同一 Candidate** 是三个同时成立的要求。

#### 失败

Candidate 3 FAIL、Reviewer 拒绝或 Test/contract/integrity invalid 时：

- 不建立声称成功的产品 PR；
- issue top-level terminal comment 绑定 `G/T/I0..Ik/C0..Ck`、三次 correction、
  Tester 原始结果摘要、Reviewer result、remaining defects 和 salvage inventory；
- 保留 Implementation branch/tip 供后续明确授权的新 task 评估复用；
- 不把失败 Test、Candidate 或 lesson 推入 `master`；
- 不自动创建更多约束或更高优先级 issue；按第 10 节门槛决定后续。

### 9.12 把 #78 bootstrap 经验正确用于当前自举

#78 可复用的不是“让一个大 Test 连续红六个 stage”，而是以下结构：

```text
窄 package 通过其适用的验收与 Human 合并审批
→ 下一 package 从 Human 选定的 exact accepted merge 基线开始
→ 累积已交付的实现与测试，不复用旧任务的 approval/verdict 证明新变更
→ 正常 Loop 使用独立双 lane/Candidate；人工 Phase 0–3 使用显式命令与 exact diff 审阅
```

当前推荐四步：

1. **Timeout Stage 0 — 动态 Agent 监督边界。** 只修改活动规则、role
   guidance、最小 monitor record 与语义回放，删除固定 Agent 任务截止
   规则；不在该 stage 重构完整 black-box harness。
2. **Bootstrap Stage A — 生命周期合同纠偏。** 只修改 workflow contract、Skill、
   role guidance 和最小 replay tests，使第 9.1–9.11 节可表达；Human 深度参与，
   不依赖旧合同自证。当前人工 Phase 合入 Human 审阅的 exact 变更，包含实现、
   配套测试与获准文档；不为人工开发虚构 Test lane/Candidate。
3. **Bootstrap Stage B — #85 语义交接充分性。** 从 Stage A 新 master 启动；由
   Orchestrator冻结 semantic annex，Tester 和 Worker 独立完成，使用 Candidate
   0+三次 correction。优先评估/清洗现有 #85 Implementation 资产，禁止无理由重写。
4. **后续 stages。** #86 evidence ledger、Candidate/finalization verifier、#79
   isolation、#87 executor 分别作为窄 task；每项从已验收合入的基线开始，在 governed
   模式下交付含 Test+Implementation 的 accepted Candidate，不一次建完整医院。

每个 governed stage 都有自己的可独立通过的 Test Gate；当前人工 Phase 0–3 则按
Human 命令完成对应 focused checks 和人工验证，没有创建的 `T/I/C` 如实记录为
`NOT_CREATED`。两种模式都不得用尚未实现的后续 stage 要求故意制造当前失败。
这样既保留 #78 的最小 Loop 和 bootstrap 成果，也不把人工补偿冒充完整自动执行器。

### 9.13 Agent 动态监督与确定性工具超时：两个独立时间平面

本节记录 2026-09-04 经 Human 审阅通过的时间控制设计。它取代当前活动规则中把
Agent 任务固定为 3/5/10 分钟、或用 `3 × 最大 KPI` 自动终止外部 Agent 的做法；
在实际规则/工具完成独立实现和验收前，本节是目标设计与有限自举人工补偿，不冒充
已落地机器能力。

#### 9.13.1 不得混用的时间语义

```text
Agent execution plane
  Orchestrator 按任务估时
  → 复用 harness 事件做被动进度观测
  → 到动态观察点后决定 CONTINUE / CONTACT / INTERVENE / TERMINATE
  → 只有显式 TERMINATE 才中断 Agent

Deterministic tool plane
  工具提供 operation-specific 合理默认 timeout
  → config 可覆盖
  → 显式 CLI/API 参数优先
  → monotonic deadline + bounded cleanup + 稳定 timeout error
```

| 名称 | 含义 | 到时能否自动判 FAIL/终止 Agent |
| --- | --- | --- |
| `estimated_duration` | Orchestrator 对本次角色任务的可修订估计 | 否；只决定何时观察 |
| `observation_window` | 本次等待/轮询多久后重新取得状态 | 否；窗口结束不停止 Subagent/Turn |
| `agent_task_timeout` | 用固定 wall-clock 自动杀死角色任务 | 正常 Loop 禁止；只能由 Human/Orchestrator 明确终止 |
| `transport_idle_timeout` | provider stream 长时间没有 transport activity | 只说明 transport/request 中断，不证明任务或 Implementation 失败 |
| `mcp_tool_timeout` | 一个 MCP server 启动或 tool call 的调用上限 | 只失败受影响调用；可按安全性重试/后备 |
| `command_timeout` | 一个确定性命令/子进程的执行上限 | 可以终止该命令；必须报告阶段、elapsed、cleanup 和稳定错误 |
| Human Gate polling/backoff | 何时再读外部审批状态 | 不是审批或任务 expiry |
| 功能 Candidate/correction | 功能开发的组装索引与修正次数预算 | 不是 wall-clock timeout；不适用于 KPI Issue |
| KPI 指标 | 场景执行后的性能衡量 | 不是 Agent timeout，也没有自动优化 correction cap |

估计超出本身不消耗 correction、不作废 `T/I/C`、不更换 Worker、不生成新 `K`，
也不把 observation 自动升级为 blocker。Agent 长时间没有可见进度只触发一次状态
判断；终止权仍在 Orchestrator/Human。

#### 9.13.2 Codex/OpenCode harness 的现有边界

本次审计以官方 Codex 文档、本机 Codex CLI 0.150.1、OpenCode 1.18.23 和当前工具
schema 为依据，得到以下边界：

| Harness 能力 | 当前可见行为 | 本框架如何使用 |
| --- | --- | --- |
| Codex App Server Turn | `turn/start` 后持续发送 `turn/item/tool` 事件；公开接口没有 per-turn wall-clock timeout；`turn/steer` 可追加信息，`turn/interrupt` 才把 Turn 置为 `interrupted` | 原生事件是主要 heartbeat source；动态决策后才 steer/interrupt，不另造自动 deadline |
| Codex SDK | `thread.run()` 启动/继续 Agent；公开页未提供 task-timeout 参数 | 调用者负责观察、取消和恢复策略，不把缺省等待猜成项目规则 |
| 当前 Subagent tool | spawn 无 timeout；`wait_agent(timeout_ms)` 只结束本次等待并返回状态；`interrupt_agent` 才中止 Agent | observation window 与 termination 分开记录 |
| 当前 command tool | `yield_time_ms` 只决定何时返回 running session；后续可 poll/terminate | 不把 yield 当 command timeout；工具自己的 deadline 另行传入 |
| Codex model-provider transport | 自定义 provider 默认 HTTP request retry 4 次、stream retry 5 次、SSE idle timeout 300000 ms | 归类为 harness/transport interruption；恢复同一 lane，不自动消耗 correction |
| Codex MCP | MCP server 默认 startup timeout 10 s、单次 tool timeout 60 s，均可按 server 覆盖 | 作为外部 tool-call timeout；可能较长的调用显式配置，失败只阻塞该调用 |
| Codex shell/process | App Server `thread/shellCommand` 缺省一小时；`command/exec` 支持 `timeoutMs`；process/command 有显式 terminate/kill | 作为确定性命令层，不作为 Agent Turn 生命周期 |
| OpenCode CLI | 本机 `opencode run` 未暴露统一 task-timeout 参数；provider/version 内部限制不构成项目稳定合同 | adapter 解析其事件/进程状态；项目层不得假设一个跨 runner 固定时限 |
| 平台 usage/rate/context limit | 可能令 Agent/请求中断，但不是任务 wall-clock 策略 | 保存 worktree/Implementation/receipts，标记 platform interruption，条件恢复后续跑同一 lane |

官方参考：

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)；
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)；
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)；
- [Codex Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)。

公开文档没有给出所有服务端内部 hard limit，因此框架不得声称“永远不会被平台
中断”。正确合同是：**不把未公开/不可控平台中断当作项目主动 timeout，也不把它
自动重分类为业务失败；只使用已公开状态和本次实际 evidence 做恢复决策。**

#### 9.13.3 最小动态监督记录

动态监督属于 Orchestrator runtime state，不属于 `K` 的公开业务语义，也不进入 Test、
Implementation、Candidate 或 PR。建议 ignored 存储：

```text
.agent-state/agent-monitoring/<task-run>/<dispatch-id>/monitor-plan.json
.agent-state/agent-monitoring/<task-run>/<dispatch-id>/monitor-events.jsonl
```

初始 `monitor-plan.json` 最小字段：

```text
schema_version
task_run + dispatch_id + role + lane/worktree identity
harness_adapter + agent/session identity（可用时）
estimated_duration_seconds + estimate_basis
first_observation_after_seconds
automatic_timeout: false
created_at_utc + owner: orchestrator
```

`estimated_duration_seconds` 和 `first_observation_after_seconds` 是本次 dispatch 的判断，
不是全局常量。依据至少包括任务范围、预计命令、历史相似任务、外部依赖、Agent
最近报告和剩余工作；它们可以在每次观察后修订。

每次 `monitor-events.jsonl` 追加：

```text
observed_at_utc + sequence
signal_source(harness_event | wait_snapshot | agent_status | human | platform)
progress_since_previous + current_operation + blocker
last_evidence_locator + revised_remaining_seconds
decision(CONTINUE | CONTACT | INTERVENE | TERMINATE)
next_observation_after_seconds + rationale
```

执行规则：

1. 优先使用已有 item/tool/command/message/status 事件，不要求 Agent 按固定周期生成
   自定义心跳，避免为“证明还活着”消耗额外 token。
2. 到动态观察点仍有实质进度：`CONTINUE`，修订估时并设置下一观察点。
3. 状态不清楚但没有失效证据：`CONTACT`，向同一 Agent 请求当前操作、已完成内容、
   blocker 和新估时；不换 Agent/worktree。
4. 可由 Orchestrator解除的局部问题：`INTERVENE`，提供缺失权限/环境/公开合同解释，
   或暂停受影响命令；保留其余完成内容。
5. 仅 Human 明确停止、Agent 明确不可恢复、继续会破坏 integrity/safety，或受影响
   mandatory operation 已无法恢复时使用 `TERMINATE`；记录原因后调用 harness
   interrupt/kill，并保留可复用 source/evidence。

监控记录更新不会产生 `K1`。Launch Envelope 只需绑定 `dispatch_id` 和相应
lane/session；monitor plan 由 Orchestrator持有并可变。未来 route executor 可消费
这些事实，但 #93 handoff guard 不验证时间估计是否“正确”，也不承担 scheduler 或
语义判断。

#### 9.13.4 确定性工具的统一 timeout 合同

项目的非 Agent CLI、脚本和阻塞 API 必须采用：

```text
built-in operation default
  < config/env override
  < explicit CLI/API invocation override
```

公共合同至少满足：

- 默认值按 operation 风险/正常耗时确定，不设置一个全项目万能数字；
- caller 可显式覆盖主要阻塞 operation 的 timeout；内部 polling/cleanup 微常量只有在
  确有公共控制价值时才暴露，避免配置面无边界膨胀；
- 使用 monotonic deadline；嵌套步骤只能消费 remaining budget，不能各自重置完整
  timeout；
- timeout 返回非成功 exit/status 和稳定、工具局部的错误标识，不伪装普通失败；
- 结构化结果至少包含 `operation`、`configured_timeout`、`elapsed`、`phase`、
  `timed_out`、`process/exit code`、`cleanup_status` 和 evidence locator；
- 进程型工具终止完整进程树并执行有界 cleanup grace；cleanup 失败使用独立错误，
  不能覆盖原 timeout；
- 纯计算、有限 collision loop 和非阻塞查询不因统一化而被强行添加 timeout。

嵌套 harness 与项目工具都有限时能力时，外层必须大于内层业务 deadline 加 cleanup/
结果写出余量，或外层只做可轮询 session supervision：

```text
outer harness deadline > inner tool deadline + cleanup grace + report margin
```

不得让外层先杀死进程，导致内层来不及清理子进程、写出 `timed_out`、保存日志或
返回稳定错误。MCP 的长操作同理：设置 server-specific tool timeout，或改为可轮询的
异步 operation，而不是叠加一个更短外层硬杀。

#### 9.13.5 当前项目 timeout/等待机制审计

| 区域 | 当前事实 | 处置 |
| --- | --- | --- |
| Agent role guidance | `AGENTS.md` 固定 focused 3 min、E2E 5 min、10 min 介入；Tester 使用 `3 × 最大 KPI` | P0.1 动态监督 package 删除固定自动判断，保留任务级动态估时 |
| `blackbox_e2e.py` | 默认 `3 × max KPI × 60`，用 `subprocess.run(timeout=...)` 对 Codex/OpenCode 硬终止；Windows Codex fallback 可能重启完整预算；Git init 未限时 | 改为 streaming/pollable runner、harness adapter 和显式终止；KPI 只作结束后度量；setup Git 使用独立 tool timeout |
| Runtime validation | 通用 runtime config 有 180 s 默认、1..3600 范围、配置/CLI/API 覆盖和 process-tree cleanup | 保留；补齐结果结构和 timeout scope |
| standalone `validate` | parser 没有 runtime `--config/--timeout`，实际固定使用默认 180 s | 增加与通用入口一致的 override/precedence，不改变 validation 业务语义 |
| Validation lease/cleanup | `TargetLease.close()` 的 condition wait 和部分 workspace cleanup 无 deadline；cleanup 内部有固定短 grace | 为真正可无限阻塞的 operation 增加 bounded deadline；短 cleanup grace 仍可内部管理 |
| E2E outer helper | 外层常用 180 s 与内层 vendor 180 s 相同，可能先于内层 structured timeout/cleanup 结束 | 外层由内层 deadline + cleanup/report margin 派生 |
| Deploy tooling | filesystem retry 为固定有限退避；lock acquire 10 s、stale 300 s、poll 0.1 s，覆盖/活性证明不足 | 暴露主要 lock/operation timeout；stale lock 增加 PID/liveness/lease refresh，不把每个 poll 常量变成公共参数 |
| Release manifest | Git subprocess 没有 timeout 或 caller override | 增加小型、可覆盖的 Git operation timeout 和稳定错误 |
| #88/#90/workflow probes | guarded business argv 可限时，但若干前置 Git probe 无 timeout；`timeout_seconds` 命名容易被误解为 Agent timeout | 补前置 Git command deadline；兼容期接受旧字段但规范名为 `command_timeout_seconds` |
| Initialization | GUI/text input 的 Human 等待可无限；Windows junction fallback 等确定性命令未限时 | Human wait 保持人为终止；自动化仍禁止 GUI；只给确定性子命令加 timeout |
| CI/tests | workflow 没有 job-level safety cap；pytest 无统一 timeout plugin；多处 test subprocess 无限等待 | CI 可设独立 job safety cap；只修本次触达/可无限阻塞的 subprocess，不批量改所有测试 |
| Human Gate heartbeat | 10 min→30 min→hourly backoff 只决定何时再 poll | 保留为 scheduler cadence；不得叫 Agent timeout 或 approval expiry |

#### 9.13.6 中断和 timeout 的局部路由

| 观测 | 默认路由 | correction/Candidate 影响 |
| --- | --- | --- |
| 仅超出动态估时，仍有进度 | `CONTINUE`，修订估时 | 无 |
| 无状态但 harness/session 仍可访问 | `CONTACT` 同一 Agent；一次有界诊断 | 无 |
| provider stream idle、网络断开、usage/rate limit | 保存现场，优先 resume 同一 Agent/lane；必要时等待外部条件 | 不因中断本身消耗 correction |
| MCP/tool/command timeout，命令未开始或无业务副作用 | 恢复条件后重跑受影响 operation | 不自动消耗 correction |
| command timeout 且可能已有副作用 | 先证明幂等或完成 owned cleanup，再决定重跑 | 未取得 valid Tester verdict 前不计 |
| Orchestrator/Human 显式终止 | 记录 `TERMINATE` authority、原因、salvage/evidence | 按 §12 判断 task 是否 terminal；不得伪装 PASS |
| 正在验收 timeout/guard 功能且实现未按公开合同结束、清理或报告 | Tester 可形成 valid Implementation FAIL | 照常进入下一 correction |

Harness/transport/tool/platform interruption 是 observation source，不新增当前 `W`
finding enum，也不能由 Agent 自己声明 PROCESS 豁免。模糊归因保持计数冻结并交 Human；
只有 Tester 在完整、可信运行上证明 Implementation defect，才消耗 correction。

#### 9.13.7 最小验证范围

时间控制 package 只运行新增、修改和 dependency edge 证明受影响的测试：

- 动态监督：持续进度、重新估时、无响应后 CONTACT、局部 blocker 后 INTERVENE、
  Human/Orchestrator TERMINATE，以及 usage interruption 后 same-lane resume；
- deterministic tool：默认值、config/CLI/API precedence、monotonic remaining budget、
  structured timeout、process-tree cleanup 和 cleanup failure；
- black-box adapter：长时间但有进度的 Agent 不被自动终止、显式终止清理进程树、
  Windows fallback 不重置预算、失败保留 workdir/evidence、shell exit 与 summary 一致；
- nested deadline：inner timeout 有足够时间完成 cleanup/report，outer 不抢先杀死；
- regression 只选择受影响 owner/generality/adapter tests，不运行无 dependency edge 的
  存量 full unit suite；CI/release full suite 与当前 Candidate verdict 分离。

### 9.14 三级测试与 RTD CfgFile CLI 单向 KPI Issue

#### 9.14.1 生效范围：只约束后续交付，不追溯补课

本节记录 2026-09-06 Human 已确认的设计。适用于后续新 feature 开发和新 issue
解决；正在排队、尚未接受的 #85 等后续交付按对应新规则执行。已合并 feature/代码
不因缺少新分层架构而补建 Test lane、补跑全套测试或重新审批历史 PR。已有实现和
测试保留；未来变更确实影响已有测试时，按 Test Impact Set 选择相关回归。

| 测试类别 | 责任与交付 | 目的与时机 |
| --- | --- | --- |
| Unit | Worker 在 Implementation lane 基于 TDD 编写，包括 generality tests | 开发/增量修正期间验证实现细节、边界和泛化；不是独立 owner 功能验收 |
| Functional | Tester 在独立 Test lane 编写并预验证，Human 批准后冻结 | 合并前验证当前 issue/feature 的正常、异常和必要直接依赖行为；PR 交付 accepted Candidate 的 Test+Implementation |
| KPI | Tester/Human 独立设计或选择综合场景；Human 审用例，Tester 执行，Human 审结果 | 功能 merge 后评估 RTD CfgFile CLI 复合/综合场景及其性能，不回写原功能 Gate 或自动优化 |

分类依据职责和目的，不是 pytest API、目录或调用粒度。功能测试以当前 feature
为边界，但不能只测 happy path；也不能默认膨胀为完整系统综合场景。KPI 不是给
功能 Gate 复制一份计时器。当前 KPI 范围**仅 RTD CfgFile CLI**，不包括 Agent Loop
自身、#85 状态机、文档或其他工具。指标阈值不是 Agent 生命周期期限。

#### 9.14.2 Reviewer 决策、PR 时建单、merge 后人工启动

不得假定 GitHub merge 能自动唤醒个人端 Agent。本地阶段没有 merge webhook
触发器、后台领单、定时 CT 或新服务。建单是正在运行的功能交付流程中的显式动作：

1. 功能 Tester PASS 后，terminal Reviewer 审查时根据公开任务合同/issue scope
   判定产品、feature、new-feature/bugfix、KPI 用例覆盖和建单需要，形成结构化结果。
   不凭修改路径猜测业务类型，不读取隐藏功能用例来为 Worker 定制实现。
2. Reviewer APPROVED 后，Orchestrator **在提交功能 PR 时**消费该结果，创建并
   关联待 merge 的 KPI Issue；记录 source issue/PR、exact accepted Candidate 和
   测试范围。Reviewer 不亲自获得通用 GitHub writer 权限。
3. 基于 source PR/Candidate 与测试范围识别已有建单；重复命令或写入响应不明时
   先核对，不重复创建。KPI 资产/结果/Dashboard 的提交不得递归生成 KPI Issue。
4. 提 PR 时尚未 merge，因此 Issue 创建与可执行是两件事。只有 exact Candidate
   获 Human final approval、源 PR 实际合入且身份已验证、**Human 明确启动该 KPI
   Issue**，才进入用例准备和测试流程；不以 Issue 存在或 approval 单独证明已合并。
5. 源 PR 未合并、关闭或换了未批准 Candidate 时不运行该 Issue；保留真实状态供
   Human 处置，不自动换被测版本、重建 Issue 或启动补偿流程。

| 来源变更 | KPI Issue 的用例工作 |
| --- | --- |
| RTD CfgFile CLI 新 feature | 准备独立的复合/综合 KPI 场景，进入 Human 用例 Gate |
| 旧 feature bugfix，已有 KPI 用例覆盖 | 引用既有用例版本与本次范围，不重复开发；执行后提交结果 |
| 旧 feature bugfix，没有现成覆盖 | 记录覆盖缺口并交 Human 决定，不擅自补 case 或跳过并宣称已测 |
| 非 RTD CfgFile CLI | 不建 KPI 测量 Issue，不要求 KPI 证据 |

“没有现成覆盖”是保留的 Human 决策分支，不是自动回补历史的授权。

#### 9.14.3 KPI 是独立类型、单向 Loop，不是功能 correction 的延长

目标路由（具体枚举/JSON schema 由 #100 版本化落地，不偷加到旧 v1 record）：

```text
Human 启动 KPI Issue（源 Candidate 已批、源 PR 已 merge）
→ Tester/Human 编写或选择用例，完成预测试
→ Human 用例 Gate（冻结 exact case revision 与执行范围）
→ Tester 本地执行获批用例
→ 记录完整结果
→ Reviewer 一次终态审查
→ Human 结果审核/处置
→ KPI Issue 结束
```

KPI Issue 没有 Worker、Implementation lane、Candidate 组装或 correction counter。
Tester 不改产品实现；Reviewer 只审过程/证据/报告且不重跑测试或发起返工。所有
结果均交 Human，不自动修复、优化、重新采样直到通过或启动下一 issue。Human
另行命令重测、改用例或修复时，生成明确的新执行/变更记录，不覆盖失败记录。

人工可以直接设计、编写或修改 KPI 用例。Tester 负责将最终内容变为可执行用例并
预验证所选 discovery/fixture/runner/计时/结果采集链；预测试不承担产品优化，也不
作为正式测量结果。Human Gate 审的是完整用例包，指标、方法、范围和版本是其组成
部分，不为每个字段另设审批。既有用例只确认本次引用的获批版本和范围，不重复开发。
获批内容在本次执行期间冻结；语义改变需要新的用例版本和 Human 批准。

#### 9.14.4 真实结果与人工处置

| 结果 | 必须记录的含义与后续 |
| --- | --- |
| 场景完成且指标达标 | 有效样本、目标比较和证据，交 Human 审核 |
| 场景完成但指标未达标 | 性能差距与瓶颈分析，交 Human；不调用 Worker |
| 综合场景失败 | 如实记录失败位置与可确认原因，不包装成单纯环境/测量无效 |
| 环境异常、数据缺失或执行中断 | 单列 operational outcome、不可判定指标及证据，不算作达标或擅自豁免真实场景失败 |

场景需要完成条件，失败后快速退出不能视为性能优秀；这不是重新审核原功能 PR。
一次评估完成不等于 KPI 全部达标，Human 可以接受“已完成评估/存在失败”的结果并
安排后续工作。不得修改原功能 verdict、重置功能 correction 或为此舍弃已有实现。
执行方案中预先获批的重复采样属于测试方法，不是失败后的自主迭代；必须保留所有
样本，不只记录最快一次。Agent 动态监督及确定性命令超时继续按 §9.13 执行。

#### 9.14.5 两类交接沿用一个守卫

最小 KPI 交接包括：功能 Reviewer 的建单决定、KPI Issue/启动输入、KPI 用例包与
预测试报告、Human 用例决定、Tester 执行报告、terminal Reviewer 报告、Human
结果决定及终态记录。用例包表达场景、完成条件、指标/单位/阈值、样本方法、fixture
和版本；执行报告绑定该包、源合并身份、实际环境和结果。Prompt 只定位文件。

上述 kind-specific 文件复用 #93 的统一包装、身份、前驱、合法性和可见性守卫。
#100 实现显式 KPI profile 扩展，不另建 guard，不哈希 prompt，也不用虚假
Implementation/Candidate 字段填充功能 profile。#93 初版仍只实现功能交付必需文件，
不因本节增加完整 KPI 引擎。自然语言场景审查和诊断判断仍由 Human/LLM 承担。

#### 9.14.6 既有用例迁移与第三方 Agent 执行

`docs/tests/rtd-config-test-cases.md` 现有 14 个带 KPI 的 `RTD-MEX-*` 用例直接迁入
新 KPI 架构，保留 ID、场景、fixture、指标和必要完成条件；历史用例不强制重写成
全新复杂场景。迁移清单/口径经 Human 确认。历史报告保持原义，不冒充本次 postmerge
结果；仅因迁移不重跑历史全量验收。未来新 issue 的功能 Gate 由独立 Test lane
生成，旧综合 KPI catalog 不再默认是合并前的 mandatory full E2E suite。

保留现有第三方 Agent/E2E 能力：Tester 组织执行并分析，场景 Agent 只看到部署后
Skill、case prompt、staged fixture，不看到仓库；embedded Tester 不是黑盒执行端。
复用 #98 adapter 与现有 harness，局部修正功能/KPI catalog 耦合及计时有效性：
runner exit 0 不等于场景成功，首次失败 check 的结束时间不能作成功计时终点。
不借此新建通用测试平台。临时环境仍在 `tests/.tmp/`，必要证据持久保存后才能清理。

#### 9.14.7 根目录 `kpi/`、JSON 结果与 Dashboard

| 目标路径 | 职责 |
| --- | --- |
| `kpi/cases/` | 可复用 KPI 场景、指标和版本 |
| `kpi/schemas/` | 用例/结果 JSON 的格式合同 |
| `kpi/results/<run-id>.json` | 一次执行一份结果，简单 JSON 数据库，不覆盖旧运行 |
| `kpi/dashboard/` | 本地网页、图表和只读结果浏览 |
| `kpi/README.md` | 本地准备、执行和查看方法 |

JSON 至少记录 source/KPI issue、源 PR/merge SHA、feature、获批用例及审批引用、
runner/model/tool/环境身份、实际命令、全部样本/单位/目标、场景与指标结论、异常、
原始证据引用和 Human 结果处置关联。不存凭据，不把缺失值写作零或 PASS；结果与
审批/后续处置分别可追溯。Dashboard 的汇总/索引可重建，JSON 是唯一结果源。

Dashboard 的**美观与可视化友好是验收要求**：先给 Human 审阅页面设计，再验证
实际渲染。要求总览→feature/场景→单次详情层次、目标与实测对比、历史趋势、合理的
版本对比、筛选/证据导航；排版、留白、配色、响应式布局一致，状态不只靠颜色区分。
清楚显示未执行、达标、未达标、场景失败、不可判定；比较时保留用例/环境/指标口径，
不能把不可比版本或极少样本画成可信的性能改善。Schema PASS 不替代视觉验收。

`kpi/` 放工程用例、数据和界面，Agent 角色/审批/路由规则仍在 Category B。
用例、工具和 Dashboard 的仓库交付需显式 Human 审阅；KPI 运行结果不自动 commit/
push，是否发布及保留原始日志由对应交付决定。不把这些资产追加进已批准产品
Candidate，不用 Reviewer lesson child 带入主线。

#### 9.14.8 本地阶段不是 CT，框架建设也不是 KPI 测量任务

本地阶段的全部 KPI 工作由 Issue 驱动、Human 启动；交付可复用获批用例和本次
结果，不安装服务器、自动触发器、后台领单服务或定时 CT。未来有服务器时只增加
调度/运行环境，调用同一测试入口、用例和 JSON 输出，不每轮重做用例开发 Loop。

#100/#101/#102 是建设这些能力的普通工程 issue，遵循各自获准的开发/功能验收
流程；它们产出的 KPI 测量 issue 才不含 Worker/Candidate。不能用“开发 KPI 框架”
为理由取消工程实现的 unit/functional gate，也不能把其建设反过来升级为所有新
feature merge 的前置条件。Phase 0–3 人工命令边界保持不变。

## 10. 未知问题处理协议

### 10.1 默认原则

未知问题首先是 observation，不是新规则。处理目标按顺序是：

1. 保护数据、证据和当前操作；
2. 用一次有界诊断确定影响范围；
3. 尽量继续不依赖该问题的交付路径；
4. 忠实记录原始现象、命令、输入 identity 和影响；
5. 在当前任务完成后决定是否值得固化。

在 #86 尚未提供 canonical incident ledger 前，使用以下最小人工记录，不新建工具：

```text
observation_id
observed_at_utc
stage / affected operation
Base/Test/Implementation/Candidate/epoch identity（适用者）
exact command or operation
raw result/evidence digest
deduplicated failure signature
bounded diagnostic performed
current disposition and rationale
owner/follow-up issue and expiry（如有）
```

该记录是事实账本，不自动产生 finding class、correction 豁免或全局 guard。

### 10.2 三类立即阻塞条件的精确定义

#### 10.2.1 Evidence integrity

仅当当前 operation 依赖的 identity、bytes、lineage 或 verdict 不能可信证明时成立，
包括：wrong/unknown cwd、HEAD、`G/K/T/I/C`；raw digest 不一致或 duplicate-key
歧义；approved Test 被修改；tested tree 与记录不同；Candidate 不是 direct union；
输出截断/reader failure 令 verdict 不完整；或者 role isolation breach 令 evidence
provenance 不可信。

它只阻塞依赖该 evidence 的 operation。例如 Candidate identity 不可信时阻塞 Tester
acceptance，不阻塞 Worker 在自己 branch 上继续公开合同范围内的分析。若能清理
residue并重新生成 fresh exact evidence，就恢复同一 Candidate，不消耗 correction。
只有 mandatory evidence 无法重建时，当前 series 才终止。

#### 10.2.2 Security/safety

仅当继续操作可能产生越权、越界、不可逆或秘密泄漏时成立，包括：out-of-scope
filesystem/remote write；凭证或 secret 暴露；symlink/junction/reparse/path escape；
未获授权的 destructive history/data mutation；不可信代码越出批准 capability；或
Tester/Worker 隔离被破坏到 hidden Test 已泄漏或 Tester 可修改 production。

首先停止具体危险 mutation 并保存现场；能够通过换到 verified root、撤销 capability
或重新建立隔离来控制时，其余路径继续。只有危险无法限定在单一 operation，或数据/
隔离无法恢复时，才终止整个 series。人工补偿不得授权秘密泄漏、路径逃逸或不可逆
外部写入。

#### 10.2.3 Mandatory acceptance

Mandatory acceptance 只指 `K` 和 Human-approved Test Gate 所绑定的 Test Impact Set
明确列为本 task 必需、且由公开 Implementation scope/expected seams/dependency edges
证明受影响的验收项：新增/修改 owner tests、directly affected existing tests、Worker
generality、以及 `K` 明确要求且受影响的 integration/vendor/E2E。无依赖关系的存量
unit suite 不在其中。

某项 FAIL、缺失或 evidence 不可信时，只阻塞 Candidate acceptance/final merge；
Tester 诊断、Worker correction 和无关 lane 仍可继续。只有 frozen mandatory gate
本身无效、公开 expected 无法由 `K` 唯一推导，或三次 correction 后仍 valid FAIL，
当前 series 才终止。

Human 明确要求停止始终优先。除此之外，任何触发都先阻塞最小受影响 operation，
不得自动把整个 issue、dependency plan 或未来任务升级为 global blocker。

### 10.3 何时继续

以下情况记录后继续：

- 在相同 runner/environment/input 下，与 Base 的原始 failure signature、node set 和
  count 完全相同，且该失败不属于本次变更触达的 mandatory acceptance；任何受
  影响的 mandatory acceptance 仍必须有独立 fresh PASS，否则阻塞该 acceptance；
- 可恢复的 runner/ACL/temp residue，恢复后能获得 fresh evidence；
- 不影响当前 acceptance 的 observability/ergonomics；
- 计划中已有 owner issue 且当前任务不依赖；
- 失败落在未被 Test Impact Set 选择、且没有 dependency edge 指向本次公开
  Implementation scope/expected seams 的存量测试；该事实只记录，不临时扩大当前
  gate；
- 工具能力缺口可以由可逆、可复核且有 exact input/output digest 的人工步骤补偿；
  人工步骤不能补偿安全边界、凭证处理、不可逆外部写入或 mandatory acceptance
  完整性。

### 10.4 从 observation 升级为 guard 的门槛

新 guard 至少满足一项：

- 已经重复发生并影响交付；
- 单次发生即可造成不可恢复或难以发现的证据/数据损坏；
- 是当前 acceptance 的必需前提。

并且必须同时具备：

- 窄、明确的守卫边界；
- known-good 与 known-bad fixture；
- 不阻塞无关路径的证明；
- owner、版本、移除/扩展条件；
- Human 对语义规则的批准。

机械性守卫可自动生成/执行，Human 可以降低逐行实现审查强度，但在合同另行批准
前仍必须通过 known-good/bad、无关路径不阻塞证明和现有 Human merge gate；不能
先合入再抽查。语义判定、错误 precedence、correction 豁免和 Human authority 必须
逐条批准。

## 11. 推荐执行顺序、优先级与依赖

本计划不放弃 #78 已合并成果，也不立即建设完整执行器。它先用一个极窄 package
去除固定 Agent 时限与 harness 误建模，再修正会直接扭曲下一 task 的生命周期，
然后恢复 #85；每一步都是窄 issue。正常 Loop 成功后合入含 Test+Implementation 的
accepted Candidate；人工 Phase 0–3 合入 Human 审阅的 exact 变更与配套测试。

### 11.1 依赖图

```text
#94 Phase 0 freeze trust-trace baseline
    └──hard──> #57 Phase 1 execution index explicitly completed by Human
                   └──hard──> #95 Timeout Package A dynamic Agent supervision
                                  └──hard──> #93 structured handoff artifacts
                                                 + unified #88/#90 guard
                                                 + lifecycle correction
                                                   └──hard──> #85 transition core
                                                                  └──hard──> #86 evidence/finalization
                                                                                 └──hard──> #79 isolation/hydration
                                                                                                └──hard──> #87 route profiles
                                                                                                               └──hard──> #80 Human intake

#96 Timeout Package C product/runtime public timeout contract
    └──hard──> #97 Timeout Package D project scripts/CI
                   └──hard──> #98 Timeout Package E black-box Agent harness adapter

#98 also depends on #95's Agent-lifecycle semantics.
#96/#97/#98 begin implementation only after #93 so they use the accepted workflow,
but #93 and #85 do not wait for them.

#87 -> #100 KPI issue profile / Reviewer-to-PR ticket intake (schedule after #80)
#100 + #98 -> #101 local KPI cases / manual execution / JSON results
#101 -> #102 local visual KPI Dashboard
#100/#101/#102 are not predecessors of functional feature acceptance.

#92 GUI hygiene executes after #80 unless it becomes an actual blocker.
#59 recovery and #81 notifications consume the stabilized state/evidence model later.
```

“hard” 只表示下游不能在旧语义上继续。Package A 不建设 scheduler/executor，只先
纠正角色时间语义，使 #93 的 Launch/guard 设计不再冻结错误的 timeout 含义。#93
直接吸收 #88 的顺序缺陷和 #90 的 artifact-shape 能力，不再把它们留成 #85 之后
的独立 repair stage。

### 11.2 P0.1-A：动态 Agent 监督与 harness 边界

优先级：**P0.1，阻塞 #93 lane dispatch，但不阻塞与 Agent Loop 无关的产品工作**。
Tracking issue：[#95](https://github.com/autoMBD/autombd-rtd-config/issues/95)。
#95 必须等待 #94 accepted merge 和 #57 Phase 1 明确完成；每个开发、验证、修正、
PR 和 merge 动作仍分别需要 Human 命令。

该 package 只能包括：

- 删除/替换 `AGENTS.md` 中 fixed 3/5/10-minute Agent 判断；
- 删除 Tester guidance 中 `3 × 最大 KPI` 等同外部 Agent 生命周期的规则；KPI 仅作
  完成后的性能 evidence；
- 定义 §9.13.3 的最小 Orchestrator monitor plan/event，明确 passive harness event
  优先、动态 observation window、四种显式决定和 `automatic_timeout=false`；
- 明确 `wait_agent(timeout_ms)`/command yield 只结束观察，不结束 Agent/command；
- 明确 transport/MCP/tool/platform interruption 与 Implementation verdict 正交；
- 把 #88 的 `timeout_seconds` 规范语义限定为 `command_timeout_seconds`，保留旧字段
  compatibility，不在本 package 改造成 Agent scheduler；
- 增加极小 synthetic policy/record known-good/bad 验证，不运行无关 unit suite。

明确排除：

- 修改 `blackbox_e2e.py` 的完整 streaming/process-tree 实现（属于 Package E）；
- route executor、persistent recovery、GitHub heartbeat automation、notification；
- 产品/runtime timeout、deploy/release/CI 变更（属于 Packages C/D）；
- #93 artifact family、#85 transition 业务语义。

Package A 合入后，Human 选择其 exact merge commit 作为 #93 新 Governor；不得把
本节文档审批当成 Implementation 合入审批。

Package A 只纠正规则、角色与监督记录的时间语义，不会令当前
`tools/blackbox_e2e.py` 立即符合动态 Agent 监督。在 Package E 合入前，
任何依赖该 harness 的 E2E 任务都不得宣称其 Agent 生命周期已经是动态
监督；这一局部能力缺口不反向阻塞不调用该 harness 的 #93/#85。

### 11.3 P0.1-B：执行 #93 结构化交付与生命周期合同纠偏

优先级：**P0.1，阻塞新的 #85 Candidate series**。Tracking issue：
[#93](https://github.com/autoMBD/autombd-rtd-config/issues/93)。

范围只能包括：

- 更新 workflow contract 的 route/state，使两条 lane 可从同一 `G/K` 并行推进；
  `T_READY_FOR_HUMAN_GATE_1` 可独立触发 Gate 1，`I0_READY_FOR_ASSEMBLY` 不属于
  Human Test approval，首次 Candidate 才 join 两者；
- 固化 `W=blob(G,"agent-discipline/workflow-contract.json")`，禁止独立选择不匹配的
  `G/W`；
- 固化最小 `K` v0.1 canonical JSON/schema/digest、Orchestrator ignored 权威副本、
  两个 worktree 的 byte-identical lane-local snapshots 和 stale-K receipt rejection；
- 固化完整 v0.1 artifact family：`K`、Test/Worker Launch Envelopes、Test Gate Ready
  Report、Implementation Report、Human Decision、Candidate Test Envelope、Confidential
  Tester Report、Worker Correction Envelope、Reviewer Launch/Report、Terminal Record
  和 Handoff Guard Result；
- 把 #88/#90 收敛为一个参数化 handoff guard，验证文件完整性、成员合法性和直接
  前驱/局部交接顺序；保留现有 v1 compatibility adapters；
- 固化 §9.3.4 的拒绝/执行异常结果、原 producer 的 delivery-repair、immutable
  replacement references、successful-check prerequisite、局部重检和计数不变；
  守卫作为被测产品的真实缺陷不得被 PROCESS 分类豁免；
- 固化 locator-only prompt 与 authoritative report-file 规则，角色定义包含第 9.3.3 节
  examples；不哈希实际 prompt/response，不实现通用 executor 或真正 atomic broadcast；
- 固化 safe-point ambiguity return、full-replacement K revision、双 lane follow-up/ACK；
- 用独立字段表达 `candidate_index=0..3` 与
  `correction_count=0..3`，禁止一个 `candidate_attempt` 字段承担两种含义；
- 固化 exact Test freeze；
- 固化 Task Contract Epoch、Test Impact Set 和 Gate 1 后的 `G/K/T` series freeze；
- 固化 `I0→I1→I2→I3` continuity 和 same-Worker-lane ownership；
- 支持 Tester PASS 与 correction exhausted/Test invalid/contract invalid 两种
  terminal Reviewer 路径；
- Reviewer 恰好一次且 terminal，不触发返工；
- finalization 明确 PR head 为 exact accepted `Ck=[T,Ik]`，完整交付两个 lane；
  禁止提前单独推 Test、剥离测试，以及用 Reviewer lesson child 替换获批 head；
- 更新对应 Skill、角色说明和极小 lifecycle known-good/bad replay。

按 §9.14 明确 Worker unit 与 Tester 功能 Gate 的归属，移除功能 profile 对合并前
KPI 结果/自动优化的依赖。KPI 专属类型、审批文件和路由由 #100 扩展；#93 不实现
完整 KPI 引擎、建单服务、runner 或 Dashboard，也不为未来字段填假 receipt。

明确排除：

- #85 的 transition/event 业务语义；
- 完整 event executor、GitHub polling/recovery、notification；
- #79 capability isolation；
- 通用 Candidate assembler；
- 把历史 owner Test 从 Git history 重写删除。

这是一次显式 `MANUAL-BOOTSTRAP`：旧合同不能证明自己的替代品，故由 Human 深度
审查 exact contract delta、focused replay vectors 和最终 PR。该人工 PR 包含实际
实现、配套测试与获准文档，不需要先运行新 Loop 生成虚构的 `T/I/C`。Human 明确
批准后合入 exact revision，再选择 exact merge commit 为后续任务 Governor。
#93 要实现的未来正常 Loop 则严格采用 accepted Candidate 为 PR head，两者不能混用。

### 11.4 P1-C：从新 master 重启 #85，而不是从零重写

依赖：#93 merged。

启动前先对现有 #85 R1/R2 Implementation 做 source-salvage audit：

| 分类 | 处理 |
| --- | --- |
| 可直接复用的公开实现/设计 | 作为非权威 patch 带入新 Worker lane，从新 Governor 重新验证 |
| 需要适配新 contract 的代码 | 保留设计/测试价值，在同一 `I0` 建设期修改 |
| 被 owner Test/source 污染 | 隔离并重写该局部，不传播 literals |
| 与批准公开合同冲突 | 删除或替换，并记录理由 |

#85 的 Orchestrator semantic annex 至少覆盖完整 event domain 的 ordered precedence、
approval identity、F0/F1 routing 和 real loader topology。三项最终失败是 mandatory
regression vectors，但不能成为全部范围：

| Public vector | 唯一 expected result |
| --- | --- |
| active contract binding malformed/drift 在 record validation 前被识别 | `MALFORMED_EVENT` |
| approval actor/command identity 相对批准事件漂移 | `STALE_EVENT` |
| 当前 checkpoint 不允许 F1 route | `ILLEGAL_TRANSITION` |

Tester 和 Worker 从同一新 Governor/Task Contract Epoch 并行完成；Tester 完成所选
Impact Set 的全链预验证后即可提交 Human Gate 1，不等待 Worker。Human 批准后
Test/K 冻结；`I0` ready 后才 join 并按 Candidate 0+三次增量修正执行。不得 fresh
restart，也不得把旧 #85 Candidate acceptance 结果当新证据。

### 11.5 P1-D：#86 exact evidence、correction ledger 与 finalization verifier

依赖：#85 的 transition/state vocabulary 稳定。

#86 应机器化本报告目前由 Human/Orchestrator补偿的部分：

- Test/contract/task epoch；
- Candidate index 与 correction count 分离；
- `I(k-1)→Ik` continuity、failure owner 和 consumption authority；
- confidential Tester Forensics Report 与 Worker Correction Envelope 的 digests、
  root-cause completeness 和 disclosure receipt；
- exact GitHub Human evidence；
- structured Tester/Worker/Reviewer result envelope；
- canonical history、sequence/run identity 和 duplicate idempotency；
- operational observation 与 contract finding/status 正交；
- Candidate ordered parents/direct union/no merge-only edits；
- final PR head 等于 exact accepted `Ck=[T,Ik]`；`G..Ck` 完整包含两条 lane 的
  交付，不能剥离 Test 或追加 lesson/merge-only edits；不重写 `G` 之前的历史。

持久化 recovery 仍属于 #59；assembler/merge mutation 仍后置。先做只读 verifier，
避免把一个尚不稳定的 writer 放进所有 PR 路径。

旧标题/设计中的独立 KPI optimization counter 已被 §9.14 取代：#86 只维护功能
Candidate/correction 账本，不创建 KPI 自动修正预算；KPI report 不是功能接受的
前置证据，KPI 的 source-merge 关联由 #100 消费已稳定的身份验证能力。

### 11.6 已并入 #93：#88/#90 统一交接守卫迁移

不再保留一个 #85 之后的独立 #88 repair stage。#93 直接吸收：

- `run` 必须消费同 manifest/artifact chain 的直接 prior successful check；
- standalone guard 的 generic role 与 governed canonical role 映射；
- #90 v1 interface packet 和 #88 v1 manifest 的 compatibility adapters；
- 所有 v0.1 artifacts 的 closed schema、field legality、visibility、direct predecessor/
  local-order known-good/bad replay；
- §9.3.4 的 CHECKED/拒绝/证据不可用路径、同 lane 补交、局部阻塞和有副作用时禁止
  无条件重试；v1 mutable receipt 可作兼容视图，但新交接引用的每版结果必须保留；
- 守卫不绑定业务语义，不变成 executor 或 semantic oracle。

### 11.7 P1-E：#79 capability isolation 与 #92 headless 初始化

依赖：稳定 lane/result identity；不得与当前 #93/#85 混成一个 Candidate。

- derived worktree headless hydration 和 initialization attestation；
- Worker/Test 最小可见输入；
- 明确 sibling worktree/Git object/.agent-state 的 trust boundary；
- automation 禁止 GUI；#92 保持较低优先级，只有 hydration 真正阻塞受影响 task 时
  才前移。

### 11.8 Timeout Package C：产品/runtime 公共 timeout 合同

优先级：**P1；不阻塞 #93/#85，只阻塞依赖这些长操作的后续产品验收**。
Tracking issue：[#96](https://github.com/autoMBD/autombd-rtd-config/issues/96)。
实现治理上等待 #93 accepted，以使用新工作流；技术设计基线依赖 #94。

- standalone `validate` 支持与通用 runtime 一致的 config/CLI/API timeout override 和
  precedence；
- configure/validate 结果补齐 `timed_out`、process code、phase、elapsed、cleanup；
- 为 `TargetLease.close()` 和 validation cleanup 的真实无限等待增加 monotonic deadline；
- 明确 timeout 覆盖哪些 preparation/vendor/post-scan/cleanup 阶段；
- 外层 E2E/helper deadline 由内层 deadline 加 cleanup/report margin 派生；
- 只运行新增/修改和受影响 validation/runtime tests。

### 11.9 Timeout Package D：项目 scripts/CI 的确定性 deadline

Tracking issue：[#97](https://github.com/autoMBD/autombd-rtd-config/issues/97)。
依赖：#96 的错误结构和 deadline 传播语义稳定。

- release manifest 的 Git subprocess 增加合理默认、显式覆盖和稳定错误；
- deploy lock/operation timeout 可覆盖，stale lock 增加 PID/liveness/lease refresh；
- #88/workflow/black-box setup 的前置 Git probe 使用 command timeout；
- CI 设置独立 job-level safety cap，但不把它计入 Candidate correction；
- 不批量给纯函数和所有历史测试增加 timeout，不把内部 poll/retry 微常量全部公开。

### 11.10 Timeout Package E：black-box Agent harness adapter

Tracking issue：[#98](https://github.com/autoMBD/autombd-rtd-config/issues/98)。
依赖：#95 的 Agent-lifecycle 语义以及 #96/#97 的内外 deadline/错误结构。它只阻塞
真正调用该 black-box runner 的操作，包括 #101 本地 KPI 执行；不再一概阻塞
#40–#44 的开发或 merge，也不反向阻塞 #93/#85。若新 feature 自身的功能 Gate
确需该 runner，应以实际 dependency edge 单独证明，不能用已迁出的 KPI catalog
把所有产品任务重新绑成全局前置。

- 以 streaming/pollable adapter 驱动 Codex、OpenCode 和后续 runner；
- 删除正常路径的 `subprocess.run(..., fixed Agent timeout)`；长时间但持续有进展的
  Agent 不被自动终止；
- 只有 Orchestrator/Human 显式 `TERMINATE` 或外部平台不可恢复结束才停止 Agent，
  并清理完整进程树；
- Codex/OpenCode adapter 统一 `start/observe/contact/interrupt/classify_end`，但保留
  runner-specific 原始 evidence；
- Windows fallback 不重新获得完整预算；failure/timeout/malformed result 均非零退出，
  并保留 workdir/evidence，只有 validated PASS 自动清理；
- setup Git、vendor validation 等确定性步骤使用独立 tool timeout；KPI 不再控制 Agent
  生命周期。

### 11.11 后续：#87、#80、#59、#81

- #87 route executor 依赖 #85 transition、#86 evidence/finalization 和 #79 isolation；
- #80 contributor/ticket/PR intake 消费稳定 route/evidence fields；
- #59 recovery 依赖可重放 canonical state；
- #81 notifications 依赖稳定 Human Gate/result identity。

不得为了“无人值守”同时开工这四项；executor 能重放、能恢复之后再接通知。

### 11.12 P1 KPI 旁路：用例与本地结果，不建设本期 CT

| Issue | 交付边界 | 硬依赖与排程 |
| --- | --- | --- |
| [#100](https://github.com/autoMBD/autombd-rtd-config/issues/100) | KPI 类型、单向角色/人审交接、Reviewer 建单决定及 PR 时幂等建单、source merge 前置 | #87；排程偏好主链到 #80 后，不反向阻塞主链 |
| [#101](https://github.com/autoMBD/autombd-rtd-config/issues/101) | 14 个已有 KPI 用例迁移、本地人工启动执行、第三方 Agent/E2E 复用、JSON 结果与证据 | #100 和 #98；不运行历史补课或自动优化 |
| [#102](https://github.com/autoMBD/autombd-rtd-config/issues/102) | 美观易用的本地 JSON Dashboard、图表/筛选/详情/证据，Human 视觉验收 | #101 结果 schema；可先做界面设计，集成须以接受的格式为准 |

三个均为 P1 窄工程任务，不因登记就开工。#93 不承担全部 KPI schema/执行器，
#85 保持功能 transition core，#86 不实现 KPI 优化计数，#79 保持隔离边界。
#87/#80 的公共路由/入口被 #100 复用，KPI 专属能力不与它们同时膨胀。
新产品 issue 仍按 #9 triage→#40→#41→#42→#43→#44 的既有排序评估自身功能范围；
#9 不变成历史三级测试重建。已存在的产品功能缺口继续独立处理，不因“不补测试
架构”被宣称解决。未来服务器 CT 只记录扩展方向，不新增当前实施前置或服务任务。

## 12. 自举退出条件

### 12.1 单个 task/package 的强制终止

本小节描述 **Phase 3 被 Human 验收并合入之后**，未来 governed Loop 对单个
task/package 的目标终止语义；它不是 Phase 0、1、2、3 当前人工自举过程的执行
授权。Phase 0–3 继续受 §9.2 的 `MANUAL-BOOTSTRAP` 覆盖：每个 bounded action
完成即停止，Candidate 组装、Tester、terminal Reviewer、PR 和 merge 都只能在
Human 对该 exact 下一动作另行下令后发生，不得因下列条件自动 dispatch 或推进。

进入该未来 governed 模式后，**功能开发 profile** 的一个 package 只覆盖一个 issue
和一个 frozen Candidate series。KPI 测量 profile 没有 Candidate，按 §9.14 的单向
执行、一次终态 Reviewer 和 Human 结果处置结束，不套用以下修正/终止条件。
功能开发发生以下任一条件即结束，随后 terminal Reviewer 恰好运行一次：

- 某个 `C0..C3` Tester PASS；
- `C3` valid FAIL；
- Human-approved Test 被证明无效；
- `G`、`K` 或 Human-approved `T` 必须改变；
- evidence-integrity/security-safety blocker 无法在受影响 operation 内恢复；
- Human 明确停止。

PASS 不等于直接合并：只有 Reviewer APPROVED 和 Human final approval 后，exact
accepted Candidate PR（包含 Test+Implementation）才能进入主线。失败不建产品 PR；
保留 Implementation tip 和 salvage inventory。

package 退出时清理 disposable stubs/temp evidence，保留 raw digests、terminal
Tester/Reviewer results 和 observations。下一个 stage 必须从已验收合入的 exact 基线
或 Human 明确指定的新 Governor 启动，不能隐式继承旧 Test/Candidate approval。

### 12.2 长期取消人工补偿控制的目标

未来正常 Loop 不再需要 `BOOTSTRAP-LIMITED`，至少要具备：

- 机器合同原生表达双 lane readiness、Test freeze、Candidate 0+三次 correction 和
  terminal Reviewer；
- transition engine 可重放合法 history，并拒绝 duplicate/stale/out-of-order event；
- exact evidence ledger 能解释每次 correction 消耗和 task/epoch replacement；
- structured failure-disclosure bridge 绑定 Confidential Tester Report 与 Worker
  Correction Envelope；守卫验证结构/visibility/引用，Orchestrator LLM 负责 root cause
  充分性和 hidden-Test non-disclosure；
- Candidate/finalization verifier 证明最终 PR head 与 accepted Candidate identity
  一致，完整包含批准 Test 和最终 Implementation，无 merge-only edits；
- governed role handoff 以结构化 input/output artifacts、direct predecessor digests 和
  有效运行上下文为权威；prompt/response 只是 locator/notification；
- Worker/Test 隔离具有可验证 capability boundary；
- Agent 调度复用 Codex/OpenCode harness 的 progress/event 与显式 interrupt，
  由 Orchestrator 按任务动态估时、观察和选择 `CONTINUE | CONTACT |
  INTERVENE | TERMINATE`，不再以固定时钟自动判定任务失败；
- 项目确定性工具对可阻塞 operation 实现合理默认、可覆盖、monotonic
  deadline、稳定 timeout error 与 bounded cleanup，且不把工具 timeout
  误记为 Candidate correction；
- route executor 从 canonical state 生成下一步，而不是手抄 heartbeat prompt；
- normal Loop replay suite 在 clean derived checkout 通过。

相应机器能力落地后，重复人工补偿必须删除，不能形成两个权威。#59 recovery 和
#81 notifications 提高无人值守能力，但不是任何单个 bootstrap task 成功的前置。

## 13. Owner 已确认的治理决策与实施前置

本轮复盘已经确认，不再作为待猜测问题：

1. 保留 #78 最小 Loop、#88、#90；它们是有边界的有效成果，不推倒重来。
2. Test 与 Implementation 从同一 `G/K` 独立并行；Test ready 后立即进入 Human
   Gate 1，不等待也不审核 Implementation；首次 Candidate 才 join approved Test
   和 ready Implementation。
3. Test 预验证由 Tester 在 Gate 构建期完成；Human-approved Test 在 Candidate
   series 结束前不可修改。
4. 初始 Candidate 0 不消耗修正；三次 correction 对应 Candidate 1、2、3，最多四个
   Candidate。
5. Candidate FAIL 后由 Tester 提交完整 Implementation root-cause analysis；
   Orchestrator 验证诊断充分性并去除 owner-Test 泄漏，再由同一个 Worker 在既有
   Implementation 上增量修正。
6. Reviewer 在 task 成功或失败终止时恰好一次，进入 Reviewer 后不再返工。
7. 成功 PR 的 head 是 exact accepted `Ck=[T,Ik]`，`G..Ck` 同时交付 Human-approved
   frozen Test 与最终 Implementation。禁止的是提前单独推 Test、剥离 Test 的
   Implementation-only PR，以及 Reviewer lesson child 替换获批 head；不是禁止
   测试随 Candidate 经 PR 合入。失败用 issue terminal record，既有 Git 历史不重写。
8. 未知问题 observation-first、completion-first；一次有界诊断，除 integrity、
   safety 或 mandatory acceptance 外不盲目扩大 scope/blocking。
9. Task-level Tester 只运行 Human-approved Test Gate 所绑定的 Test Impact Set；
   full-chain 是该集合的完整执行拓扑，不是 full-suite。存量无影响 unit tests不运行，
   独立 CI/release full suite 不参与 Candidate verdict 或 correction accounting。
10. 只有 Human 选择新的 exact Git commit 才发生 Governor rebaseline；公开语义
    变化生成新 Task Contract Epoch。两者都只作废 acceptance evidence，不自动
    作废未污染且兼容的 Implementation source。
11. #78 bootstrap 的 Implementation 累积原则必须恢复；stale evidence 不等于 stale
    source。
12. `G` 是 exact Git commit identity，不是交接文件；`W` 只能从 `G` 派生，`K` 和
    每份交接文件绑定并回显 `G/W`。
13. 任务语义只通过结构化 `K`、Launch Envelope、Correction Envelope 和角色报告
    传递；prompt 只定位文件、加载 Agent 规则和携带非任务运行上下文，chat response
    只通知 report path/digest/status。v0.1 不提供通用 `description_session`。
14. Tester 是唯一既有角色，分别承担 Gate 1 前 Test Case/Test Gate 构建与预测试、
    Gate 1 后 frozen Candidate 验收两个 phase；不新增 `Test author`。Worker 同样保持
    单一角色并在同一 worktree/branch 上完成 `I0→I1→I2→I3`。
15. #93 把 #88/#90 的职责收敛为统一交接守卫；守卫只验证交接文件完整性、成员
    合法性和直接前驱/局部顺序。#85 仍是全局 functional-development state machine，
    依赖 #93，不与守卫合并。
16. Confidential Tester Report 到 Worker Correction Envelope 的自由语言语义审查由
    Orchestrator LLM 负责并被 Owner 接受为 v0.1 trust boundary；机器守卫不冒充
    semantic oracle。
17. 守卫失败按 §9.3.4 只拒绝当前交接，由原 producer 补交或 Orchestrator 恢复
    上下文；保留 source、拒绝 evidence 和计数，不用新 Worker/新 series 隐藏失败。
    真正 Implementation 缺陷仍由 Tester 判断，不能因涉及守卫或 timeout 自动豁免。
18. Agent 角色任务不使用固定 wall-clock timeout。Orchestrator 按 task/phase/命令和
    历史 evidence 动态估时，复用 harness progress/status 做心跳观测，并显式决定
    `CONTINUE/CONTACT/INTERVENE/TERMINATE`；超出估时本身不是失败。
19. Codex/OpenCode 的 provider idle、MCP tool、command、usage/rate limit 和显式
    interrupt 必须与 Agent 任务生命周期正交。`wait/yield` 只结束观察窗口；只有
    Orchestrator/Human 明确 `TERMINATE` 才主动结束 Agent。
20. 项目的非 Agent CLI/脚本必须提供 operation-specific 合理 timeout 默认值、
    config 与显式 CLI/API 覆盖、monotonic remaining budget、稳定 timeout error、
    bounded process-tree cleanup 和结构化结果；不得盲目给纯计算/所有测试扩展 timeout。
21. 动态 monitor plan/event 属于 ignored Orchestrator runtime state，不进入 `K` 或
    Candidate identity。估时/下一观察点修订不产生 `K1`；#93 guard 只校验 locator/
    identity/结构，不判断时间估计、调度或业务 verdict。
22. Phase 0、1、2、3 使用 `MANUAL-BOOTSTRAP`，不允许 Agent Loop 自主 dispatch、
    迭代、重试、Candidate 组装、Gate polling、correction accounting 或 merge；每个
    bounded action 和最终合并都由 Human 分别明确下令并审阅 evidence。
23. 当前 completion gate 顺序是 #94 → #57 Phase 1 → #95 → #93；#93 在 #85 前吸收
    B1-1/B1-2，#86 在 #85 后处理 B1-3/B1-4/B1-5。finalization 对当前 task 检查
    `PR head == accepted Ck` 和 `G..Ck` 的完整交付；不得把开发期隔离扩大为测试
    永不进入主线，也不重写历史。
24. 三级测试按责任/目的划分：Worker TDD unit、Tester 人审 feature functional gate、
    合并后 RTD CfgFile CLI 独立综合 KPI。新规则面向后续交付，已合并历史不补课。
25. KPI 用例和结果都经 Human 审核；Human 可直接设计用例。KPI Issue 是无 Worker/
    Implementation/Candidate/correction 的单向 Loop，任何结果只记录后交 Human。
26. Reviewer 形成 KPI 建单决定，Orchestrator 提功能 PR 时建待 merge 的关联 Issue；
    exact Candidate 人批、源 PR 真实 merge、Human 启动后才执行。不依赖 merge
    自动唤醒个人端 Agent，不做本地后台领单或 CT。
27. 已有带 KPI 的 14 个 RTD-MEX 用例直接迁移；有覆盖的 bugfix 复用，无覆盖交
    Human 决定。根目录 kpi/ 保存可复用用例与逐 run JSON，Dashboard 美观/可视化
    友好属于验收；未来服务器仅复用用例和执行入口。#100/#101/#102 跟踪实施。

仍需 Human 对实际变更逐项批准的是：

- #94 corrected trust-trace 的 formal verification、freeze commit、PR 和 final merge；
- #95 每个实现/验证动作、exact PR 和 final merge；
- #93 每个合同/实现/回放验证动作、exact PR 和 final merge；
- 之后以新 master 重启 #85 的 exact semantic annex 和 Gate。

在 Timeout Package A 与 #93 合入前，本文是审阅与目标设计，不修改
`workflow-contract.json`，也不允许用现有 `candidate_attempt=1..3` 记录伪装已经
符合新模型。

## 14. Bootstrap trust trace

### 14.1 当前状态快照

该快照由下方 append-only events 派生，不是独立 authority：

| Field | Current value |
| --- | --- |
| Trace lane | `agent-discipline/agent-loop-bootstrap-trust-trace.md` |
| Audited Governor | `9331d6684d4cfb977212ef60e70771e36c065b7c` |
| Audited Workflow Contract blob | `b747065ac2fafa03d35d7a94b39d52d70f1de416` |
| Execution Governor | `0e4aa7613a39c55a1c6afb1c03cbe9d793b4f674` — Human 关闭 #95 并命令继续后核实的远程 master；保留现有提交，不伪造 #95 PR merge receipt |
| Design state | 已批准架构不变；Human 审阅协议完整性映射后批准执行。工作区现有 Wv2 声明、14 类结构化 artifact、统一守卫与角色指南；旧 Wv1 exact snapshot 保留。均未合并，不冒充主线已部署能力 |
| Active bootstrap package | #93 manual Phase 3 实现及定向验证完成，等待 Human 检查；分支 `codex/issue-93-structured-handoffs`，upstream 为同名远端跟踪分支；#95 不重开 |
| Candidate/correction state | none；不得用历史 `candidate_attempt` 伪造新模型 |
| Next allowed operation | Human 检查实际 diff 与交付报告，再明确授权后续修订/提交/PR；不自动合并、启动 #85、KPI 或新 Loop。协议草案原字节保留，实施补充及证据位于 ignored .agent-state/plans |

### 14.2 Append-only event schema

自 BT-0004 起，每个新增 bootstrap event 必须追加以下字段；未知值写 `UNKNOWN`
并说明原因，禁止推测：

```text
trace_id
observed_at_utc
issue / task_run / stage
event / actor / authority
G / W / K / T / I / C / candidate_index / correction_count
input_digests / output_digests
Test Impact Set digest / mandatory acceptance result
raw Tester report / Worker Correction Envelope digests（适用时）
observations / bounded diagnostic / disposition
next_allowed_operation
supersedes（仅纠正旧事件时）
```

Trace event 只记录已经发生且可引用的事实。设计愿望、未来计划和自然语言判断分别
留在 versioned design/current snapshot；不得伪造成 event。事件修正只能追加新行并
通过 `supersedes` 指向旧 `trace_id`。

BT-0001、BT-0002、BT-0003 在该完整 schema 冻结前已经追加，缺少
`Test Impact Set / mandatory acceptance`、`raw Tester report / Worker Correction
Envelope` 和 `bounded diagnostic` 字段；这些缺项统一解释为
`NOT_RECORDED_LEGACY`，不推导为 PASS、NOT_APPLICABLE 或当前合规证据。append-only
规则禁止为补齐形状而改写它们；如需纠正其事实，只能追加带 `supersedes` 的新事件。

### 14.3 Append-only events

#### BT-0001 — v0.4.0 trust-tracing design approved

```text
trace_id: BT-0001
observed_at_utc: 2026-08-28T23:56:51.4877669Z
issue / task_run / stage: framework-review / current Codex task / design-freeze
event / actor: BOOTSTRAP_DESIGN_APPROVED / Human autoMBD
authority: current task message "按你的分析来，批准了。"
G: 9331d6684d4cfb977212ef60e70771e36c065b7c
W: b747065ac2fafa03d35d7a94b39d52d70f1de416
K / T / I / C: NOT_CREATED
candidate_index / correction_count: NOT_STARTED / 0
input_digests: UNKNOWN — v0.3.0 pre-rename raw digest was not captured; lessons source is identified through LL-046
output_digests: pending exact Git blob when this governance-only change is committed
Test Impact Set: N/A — documentation design only
observations: existing machine contract still expresses legacy lifecycle
disposition: RECORD_AND_PROCEED_WITH_DOCUMENTATION_ONLY
next_allowed_operation: finish and verify v0.4.0; then separately propose P0-A package
supersedes: none
```

#### BT-0002 — v0.5.0 isolated Launch Envelope design approved

```text
trace_id: BT-0002
observed_at_utc: 2026-08-29T14:45:01.8392533Z
issue / task_run / stage: framework-review / current Codex task / design-freeze
event / actor: ISOLATED_LAUNCH_HANDOFF_DESIGN_APPROVED / Human autoMBD
authority: current task message "现在我比较清楚了，把刚刚的讨论（即Orchestrator将任务安全、准确交接给Tester和Worker）更新到agent-loop-bootstrap-trust-trace.md中。"
G: 9331d6684d4cfb977212ef60e70771e36c065b7c
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — derived from G, not independently selected
K / T / I / C: NOT_CREATED
candidate_index / correction_count: NOT_STARTED / 0
input_digests: UNKNOWN — discussion messages have no stable raw artifact digest in this trace
output_digests: pending exact Git blob when this governance-only change is committed
Test Impact Set: N/A — documentation design only
observations: K v0.1 schema/storage/replication/revision ACK and prompt binding are target design, not landed capability
disposition: RECORD_AND_PROCEED_WITH_DOCUMENTATION_ONLY
next_allowed_operation: verify v0.5.0; then separately create/review P0-A narrow work package
supersedes: none
```

#### BT-0003 — v0.6.0 structured artifact and unified guard design approved

```text
trace_id: BT-0003
observed_at_utc: 2026-08-30T01:40:35.6396913Z
issue / task_run / stage: framework-review / current Codex task / design-freeze
event / actor: STRUCTURED_HANDOFF_DESIGN_APPROVED / Human autoMBD
authority: current task annotations plus "基本清楚了，可以更新 agent-loop-bootstrap-trust-trace.md"
G: 9331d6684d4cfb977212ef60e70771e36c065b7c — Git identity, not a handoff file
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — derived from G
K / T / I / C: NOT_CREATED
candidate_index / correction_count: NOT_STARTED / 0
input_digests: UNKNOWN — discussion messages have no stable raw artifact digest in this trace
output_digests: pending exact Git blob when this governance-only change is committed
Test Impact Set: N/A — documentation design only
observations: task semantics move to canonical structured files; prompt is locator-only; chat response is notification-only; v0.1 has no description_session; Tester remains one role across Gate-authoring/prevalidation and Candidate-acceptance phases; Orchestrator LLM is the accepted semantic non-disclosure trust boundary; #93 created and #85 explicitly depends on it
disposition: RECORD_AND_PROCEED_WITH_DOCUMENTATION_REVIEW_ONLY
next_allowed_operation: verify v0.6.0, obtain Human document review, then write #93 implementation plan
supersedes: BT-0002 only where it described Launch Envelopes as actual prompts or required prompt binding; all other BT-0002 decisions remain active
```

#### BT-0004 — guard-failure routing documented

```text
trace_id: BT-0004
observed_at_utc: 2026-09-02T23:52:58Z
issue / task_run / stage: framework-review / current Codex task / guard-failure-routing-documentation
event / actor: GUARD_FAILURE_ROUTING_DOCUMENTED / Orchestrator
authority: current Human instruction "把守卫失败时的路由整理好写进文档"
G: 9331d6684d4cfb977212ef60e70771e36c065b7c
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED
candidate_index / correction_count: NOT_STARTED / 0
input_digests: v0.6.0 raw SHA-256 5c00c4d56945509b5cdaa5b5a2e8c2826d919ba43b7589bd789246ea5a851237
output_digests: pending exact Git blob when this governance-only change is committed
Test Impact Set / mandatory acceptance: N/A — documentation only; no functional or vendor/E2E test execution
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE
observations: rejection routing preserves same-lane source and counters; no broad PROCESS exemption
bounded diagnostic: documentation diff and history-integrity checks; no runtime or GitHub mutation
disposition: DOCUMENTATION_ONLY
next_allowed_operation: verify guard-routing documentation and history integrity; do not automatically resume #85
supersedes: none — completes guard failure handling omitted from BT-0003 without rewriting that event
```

#### BT-0005 — two-plane time control and harness boundary approved

```text
trace_id: BT-0005
observed_at_utc: 2026-09-04T05:19:37.6072478Z
issue / task_run / stage: framework-review / current Codex task / time-control-design-freeze
event / actor: TIME_CONTROL_AND_HARNESS_BOUNDARY_APPROVED / Human autoMBD
authority: Human's two timeout principles, followed by "这个方案看起来不错" and "我认为没问题了，更新一下文档。"
G: 9331d6684d4cfb977212ef60e70771e36c065b7c
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED
candidate_index / correction_count: NOT_STARTED / 0
input_digests: v0.7.0 raw SHA-256 06d08b00e8f81bb96b749256dcd569c1181845be8abcbb0f275d247e5655b8d2
output_digests: pending exact Git blob when this governance-only change is committed
Test Impact Set / mandatory acceptance: N/A — documentation only; no functional or E2E test execution
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE
observations: Agent dynamic supervision is separate from deterministic tool timeout; native harness events/wait/interrupt are reused; fixed 3/5/10 and 3×KPI Agent termination are target removals; monitor state does not mutate K
bounded diagnostic: official Codex App Server/SDK/Subagent/config review; local Codex 0.150.1 and OpenCode 1.18.23 CLI help; repository timeout/path/test inventory; no runtime or GitHub mutation
disposition: DOCUMENTATION_ONLY
next_allowed_operation: verify v0.8.0; await explicit authority for Timeout Package A tracking/implementation before #93 dispatch
supersedes: none — records the newly approved design; active fixed-time rules remain facts until separately implemented and accepted
```

#### BT-0006 — Phase 0 trust-trace correction authorized

```text
trace_id: BT-0006
observed_at_utc: 2026-09-04T23:32:00.1047379Z
issue / task_run / stage: #94 / manual-bootstrap-phase-0 / trust-trace-correction
event / actor: PHASE0_TRUST_TRACE_CORRECTION_AUTHORIZED / Human autoMBD
authority: current Human instruction "是的，修正这些内容" after the frozen-document audit
G: 9331d6684d4cfb977212ef60e70771e36c065b7c
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED
candidate_index / correction_count: NOT_STARTED / 0
input_digests: frozen head cb3f48414434789fba21c2ff0461ba7126bc8c14; trust-trace raw SHA-256 b9ba3244015f08a202ad6cbb61ab305de640ec669df3e4c2c4d180712546a0df; ignored execution-plan SHA-256 1111b12fe1fea16742c96a439147db3504c724ab113b394abca21933483cadd8
output_digests: corrected working-tree document; exact raw SHA-256 is reported externally because a file cannot embed its own digest; no correction commit created
Test Impact Set / mandatory acceptance: N/A — governance documentation only; structural and semantic review required
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE
observations: #94–#98 and the #57 canonical index exist; current projections must route #94 → #57 Phase 1 → #95 → #93; B1-1/B1-2 belong to #93, B1-3/B1-4/B1-5 to #86; topology exclusions apply only to current-task additions in G..accepted-Implementation-PR
bounded diagnostic: author self-check of the exact two-file branch path set plus two independent read-only correction reviews; this is correction evidence, not the separately Human-commanded Phase 0 VERIFY verdict; no runtime, product, Test Gate, Candidate, commit, PR, or merge action
disposition: CORRECT_DOCUMENTATION_AND_STOP_FOR_HUMAN_REVIEW
next_allowed_operation: present the v0.9.0 exact working-tree diff and author self-check evidence, then await an explicit Human VERIFY command; do not commit or create a PR
supersedes: BT-0003 only for its direct-#93 next operation, and BT-0005 only for its now-completed tracking-creation next operation; all approved design content remains active
```

#### BT-0007 — Phase 0 merge and direct #95 implementation

```text
trace_id: BT-0007
observed_at_utc: 2026-09-05T04:53:47Z
issue / task_run / stage: #95 / issue95-direct-development / manual-bootstrap-phase-2
event / actor: DIRECT_IMPLEMENTATION_WITH_FOCUSED_VERIFICATION / Orchestrator under Human command
authority: Human "继续下一个，拉issue 创建分支，然后直接解决，不走agent loop，解决后等待我检查即可。"
G: 2631060b80c1192729be99690f9de2d726d66d44
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED — direct development, no autonomous Loop lanes or Candidates
candidate_index / correction_count: NOT_STARTED / 0
input_digests: accepted PR #99 head 43e8cb28eb69a59b585a4b4c606936393294a6d3; merged trust-trace blob ed14ed830d2fbe3765bc424587925a054bb1b059; #57 execution index 5541711951; issue #95 body
output_digests: working-tree diff and file identities reported in ignored .agent-state/plans/issue95-implementation-report.md; no implementation commit or PR yet
Test Impact Set / mandatory acceptance: final test_agent_monitor.py 47 passed; affected test_handoff_guard.py 26 passed with 19 subtests; three selected role/frontmatter/renderer checks passed; no full suite, S32DS, or E2E run
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE — direct Human-commanded development and verification
observations: removed fixed 3/5/10-minute and Tester KPI-derived lifetime rules; added passive closed monitor records with explicit decisions and a read-only validator; command timeout alias preserves v1 wire fields; generated local platform roles still need deployment after acceptance; #98 retains ownership of the fixed black-box runtime adapter
bounded diagnostic: missing-validator and unsupported-alias RED evidence preceded implementation; a read-only check found completed+TERMINATE incorrectly accepted, reproduced with a failing test then fixed; isolated pytest cache writes were disabled after a cache warning; generic skill validation lacked optional PyYAML, so unchanged frontmatter and reference links were checked directly
disposition: IMPLEMENTED_ON_BRANCH_AWAITING_HUMAN_REVIEW
next_allowed_operation: present the branch diff and evidence, then wait for Human review; no PR, merge, or #93 advancement
supersedes: BT-0006 next operation and Phase 0 pending state only; historical observations and approved design remain intact
```

#### BT-0008 — accepted-Candidate PR rule corrected after Human review

```text
trace_id: BT-0008
observed_at_utc: 2026-09-05T10:46:45Z
issue / task_run / stage: #95 / issue95-direct-development / documentation-correction
event / actor: CANDIDATE_PR_SEMANTICS_CORRECTION / Orchestrator under Human instruction
authority: Human "test lane和implement lane独立走，但pr是 acceptance Candidate，即包含两者" followed by "审查全文，把这部分修正。"
G: 2631060b80c1192729be99690f9de2d726d66d44 — existing manual package base, not reselected
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED — documentation correction within manual development
candidate_index / correction_count: NOT_STARTED / 0
input_digests: reviewed HEAD 8519d9d99d06db37346b23f554dd0586ca243190; v0.10.0 trust-trace blob ae12c93da63542e3491064a3b11b603f3f278089; raw SHA-256 9b2d7160113a49c1ccb012c55b0bda7f0755ecf8a8ade7855621d84abe723179
output_digests: corrected working-tree document and ignored execution plan; final raw digests reported externally, not embedded self-digests
Test Impact Set / mandatory acceptance: N/A — documentation-only correction; no new runtime/unit/E2E verdict claimed
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE
observations: prior design wrongly equated development isolation with excluding Test from final PR; success PR must be exact accepted Ck=[T,Ik], not Ik or lesson child; existing accepted tests in G are not automatically a hidden-Test breach; manual Phases 0–3 do not fabricate Candidates
bounded diagnostic: full-document reading, targeted cross-section audit and independent read-only consistency review; no implementation, Test Gate, Git ref, GitHub issue/PR or merge mutation
disposition: CORRECT_CURRENT_DESIGN_AND_LOCAL_PLAN_PRESERVE_HISTORICAL_RECORDS
next_allowed_operation: present corrected document and consistency checks for Human inspection; do not commit, open PR, merge or advance #93
supersedes: prior design's Implementation-only / permanent Test-or-Candidate off-main interpretations, including BT-0006's G..accepted-Implementation-PR observation and corresponding v0.3.0/v0.9.0 changelog conclusions; all other historical facts, decisions and raw BT-0001…BT-0007 records remain unchanged
```

#### BT-0009 — three-tier tests and issue-driven local KPI plan synchronized

```text
trace_id: BT-0009
observed_at_utc: 2026-09-05T18:54:14Z
issue / task_run / stage: #57 / three-tier-kpi-planning / documentation-and-tracking
event / actor: KPI_DESIGN_AND_EXECUTION_PLAN_SYNC / Orchestrator under Human instruction
authority: Human "把我们的讨论更新到agent-loop-bootstrap-trust-trace.md中，同时调整执行计划，同步远程issues，如果需要创建新issue，也一并创建。"
G: 2631060b80c1192729be99690f9de2d726d66d44 — existing accepted manual baseline, not reselected
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED — documentation and issue synchronization only
candidate_index / correction_count: NOT_STARTED / 0
input_digests: reviewed HEAD e7a2ab5f1a99473e78e27285826fb895a0f8672c; v0.11.0 trust blob d0b94f478baf9282b63bdbc0c1f6c7ae69f41b70; raw SHA-256 d26192692952eac0090450e849fc49fba8bff1e2fb67195fad718ab5b0ec72d2
output_digests: v0.12.0 working document and ignored plan v0.5.0; final raw hashes and exact GitHub write/readback receipts are recorded in the ignored synchronization record and #57 canonical index, not self-embedded
Test Impact Set / mandatory acceptance: documentation consistency/diff checks and exact remote readback; no runtime/unit/E2E acceptance claimed
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE
observations: Worker TDD unit and frozen Human-approved feature functional gates remain premerge; CLI-only comprehensive KPI is a separately Human-started one-way issue with case/result review, no Worker or automatic correction; Reviewer decides ticket intake, Orchestrator creates waiting-for-merge ticket at PR submission; current local delivery is not CT; historical KPI cases migrate without historical test backfill
bounded diagnostic: read active role/contract/harness/plan and existing open issues/comments; create bounded #100/#101/#102 tracking, synchronize affected issue bodies/index without changing old Human approvals or runtime code
disposition: RECORD_APPROVED_DESIGN_AND_SYNC_TRACKING_PRESERVE_IMPLEMENTATION_AND_HISTORY
next_allowed_operation: verify local document/plan and remote receipts, then report; no implementation, PR, merge, automatic Agent wakeup or #93 advancement
supersedes: earlier proposal of no KPI Human Gate, generic-feature KPI, automatic merge-trigger/local CT, and functional premerge KPI optimization counters; BT-0008 remote-sync restriction is superseded only by this explicit synchronization authority; historical test/verdict/event/changelog bytes remain unchanged
```

#### BT-0010 — Human closed #95 and started #93 manual contract preparation

```text
trace_id: BT-0010
observed_at_utc: 2026-09-05T20:11:56Z
issue / task_run / stage: #93 / issue93-manual-contract-draft / manual-phase-3-contract-preparation
event / actor: MANUAL_NEXT_PACKAGE_STARTED / Orchestrator under Human instruction
authority: Human "设置好了，仓库现在只允许走PR。我把#95关闭了，#95就此揭过。继续推进下一步。"
G: 0e4aa7613a39c55a1c6afb1c03cbe9d793b4f674
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — unchanged
K / T / I / C: NOT_CREATED — concrete protocol draft is not a task K or acceptance artifact
candidate_index / correction_count: NOT_STARTED / 0
input_digests: exact G and W above; approved trust-trace v0.12.0; current #93 body and manual-bootstrap comment 5541711518
output_digests: ignored issue93-handoff-protocol-draft.md, issue93-implementation-plan.md and updated execution plan; hashes recorded in the #57 execution index, not self-embedded
Test Impact Set / mandatory acceptance: NOT_RUN — document consistency and branch identity checks only
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE
observations: GitHub readback confirms #95 closed/completed; existing source retained without rewriting history; #93 remote/local branch and same-name upstream verified; Human reports master PR protection configured, not independently claimed as a tested capability
bounded diagnostic: read-only #88/#90 compatibility inspection confirms successful-CHECKED ordering gap and affected legacy test setup; no runtime/test changes
disposition: PREPARE_CONCRETE_PROTOCOL_FOR_HUMAN_REVIEW
next_allowed_operation: present unapproved local contract draft; subsequent coding/verification/PR/merge remains Human-commanded
supersedes: BT-0009 next-operation restriction only for Human-authorized #93 start; no historical evidence or approved normative design rewritten
```

#### BT-0011 — Human-commanded #93 implementation verified, awaiting inspection

```text
trace_id: BT-0011
observed_at_utc: 2026-09-06T04:34:35Z
issue / task_run / stage: #93 / issue93-manual-implementation / manual-phase-3-delivery
event / actor: MANUAL_IMPLEMENTATION_VERIFIED / Orchestrator under Human command
authority: Human "批准执行" after protocol draft and completeness mapping review
G: 0e4aa7613a39c55a1c6afb1c03cbe9d793b4f674 — HEAD unchanged
W: b747065ac2fafa03d35d7a94b39d52d70f1de416 — exact governing baseline blob; local Wv2 is not a new committed Governor
K / T / I / C: NOT_CREATED — manual code/tests and synthetic fixture histories are not real acceptance lanes or Candidates
candidate_index / correction_count: NOT_STARTED / 0
input_digests: reviewed draft SHA256 ea226ba2309f37794dd0a62a88e6b4397491c4be62ceff67e8870be0fd6ee9d5; approved implementation supplement retains scoped authority
output_digests: local Wv2 raw SHA256 854b573f46df069199cff1297ba864e70af148cf6b5818f35856976376eb9438; final A source/test hashes recorded in ignored issue93-final-verification.md; no new commit or remote receipt
Test Impact Set / mandatory acceptance: selected new/changed/affected checks only; final A 83 passed in 132.31s; unchanged B 70 passed / 267 subtests and C 86 passed retained with unchanged source/test hashes; no full suite, S32DS, E2E or KPI
raw Tester report / Worker Correction Envelope: NOT_APPLICABLE — independent manual verification report, not governed Tester acceptance or Worker correction accounting
observations: all 14 artifact kinds, typed attachments, G/W/K/dispatch bindings, dual views, incremental source, STOP/repair identities, CHECKED/run prerequisite and explicit v1/v2 migration implemented; four spec omissions, a STOP regression and cache/path defects were reproduced and fixed in the same retained source before Human inspection; independent scoped spec/quality checks closed the confirmed findings
bounded diagnostic: same-cache-family weak/strong validation bypass confirmed and repaired without new schema or isolation scope; generic Skill helper lacked PyYAML, alternative runtime lookup returned no usable result and was canceled; focused Skill behavior/frontmatter/link checks passed
disposition: WAIT_FOR_HUMAN_DIFF_INSPECTION — uncommitted and unmerged; no GUI, deployment, automatic Loop, remote mutation or source discard
next_allowed_operation: present actual delivery and verification evidence; further correction, submission, PR and merge remain Human-commanded; #85 stays pending
supersedes: BT-0010 next-operation restriction only after Human coding approval; previous audit, failures, receipts and changelog preserved
```

## Appendix A — 证据索引

### A.1 当前主线文件

- Governance charter：[`../AGENTS.md`](../AGENTS.md)
- Machine contract：[`workflow-contract.json`](workflow-contract.json)
- Agent Workflow Skill：[`skills/agent-workflow/SKILL.md`](skills/agent-workflow/SKILL.md)
- Static workflow gate：
  [`skills/agent-workflow/scripts/workflow_gate.py`](skills/agent-workflow/scripts/workflow_gate.py)
- Handoff guard：
  [`skills/agent-workflow/scripts/handoff_guard.py`](skills/agent-workflow/scripts/handoff_guard.py)
- Interface packet checker：
  [`skills/agent-workflow/scripts/interface_handoff_check.py`](skills/agent-workflow/scripts/interface_handoff_check.py)
- Roles：[`subagents/`](subagents/)
- Active lessons：[`agent-lessons-learned.md`](agent-lessons-learned.md)
- Initialization Skill：
  [`skills/initialize-agent-discipline/SKILL.md`](skills/initialize-agent-discipline/SKILL.md)

### A.2 当前主线测试

- [`../tests/unit/test_agent_workflow_bootstrap.py`](../tests/unit/test_agent_workflow_bootstrap.py)
- [`../tests/unit/test_agent_workflow_bootstrap_generality.py`](../tests/unit/test_agent_workflow_bootstrap_generality.py)
- [`../tests/unit/test_handoff_guard.py`](../tests/unit/test_handoff_guard.py)
- [`../tests/unit/test_interface_handoff_check.py`](../tests/unit/test_interface_handoff_check.py)
- [`../tests/unit/test_interface_handoff_check_generality.py`](../tests/unit/test_interface_handoff_check_generality.py)

### A.3 关键历史与当前 tracking receipts

#### A.3.1 当前人工自举 tracking

- Phase 0 trust-trace freeze：
  [issue 94](https://github.com/autoMBD/autombd-rtd-config/issues/94)
- Canonical Phase 0–3 execution index：
  [#57 comment 5541711951](https://github.com/autoMBD/autombd-rtd-config/issues/57#issuecomment-5541711951)
- Timeout Package A：
  [issue 95](https://github.com/autoMBD/autombd-rtd-config/issues/95)
- Timeout Packages C/D/E：
  [issue 96](https://github.com/autoMBD/autombd-rtd-config/issues/96)、
  [issue 97](https://github.com/autoMBD/autombd-rtd-config/issues/97)、
  [issue 98](https://github.com/autoMBD/autombd-rtd-config/issues/98)
- Phase 3 manual-bootstrap dependency：
  [#93 comment 5541711518](https://github.com/autoMBD/autombd-rtd-config/issues/93#issuecomment-5541711518)
- #85 restart anchor：
  [comment 5541712266](https://github.com/autoMBD/autombd-rtd-config/issues/85#issuecomment-5541712266)
- #86 corrected lifecycle：
  [comment 5541712995](https://github.com/autoMBD/autombd-rtd-config/issues/86#issuecomment-5541712995)
- #79/#87/#80 dependency boundaries：
  [#79 comment 5541712568](https://github.com/autoMBD/autombd-rtd-config/issues/79#issuecomment-5541712568)、
  [#87 comment 5541713320](https://github.com/autoMBD/autombd-rtd-config/issues/87#issuecomment-5541713320)、
  [#80 comment 5541714111](https://github.com/autoMBD/autombd-rtd-config/issues/80#issuecomment-5541714111)
- #59/#81/#92 non-hard scheduling boundaries：
  [#59 comment 5541713661](https://github.com/autoMBD/autombd-rtd-config/issues/59#issuecomment-5541713661)、
  [#81 comment 5541714532](https://github.com/autoMBD/autombd-rtd-config/issues/81#issuecomment-5541714532)、
  [#92 comment 5541714868](https://github.com/autoMBD/autombd-rtd-config/issues/92#issuecomment-5541714868)

#### A.3.2 已有历史评论

本轮 KPI 设计 tracking：[#100](https://github.com/autoMBD/autombd-rtd-config/issues/100)、
[#101](https://github.com/autoMBD/autombd-rtd-config/issues/101)、
[#102](https://github.com/autoMBD/autombd-rtd-config/issues/102)。本轮同步的 issue/comment
写入和回读证据存于 ignored 执行计划及 synchronization receipt；#57 仍只有一个
canonical execution index，不另建竞争清单。

- #57 approved baseline / package split：
  [comment 5035390309](https://github.com/autoMBD/autombd-rtd-config/issues/57#issuecomment-5035390309)
- #57 P1 dependency map：
  [comment 5232371194](https://github.com/autoMBD/autombd-rtd-config/issues/57#issuecomment-5232371194)
- #57 post-#83 execution-framework correction：
  [comment 5255578159](https://github.com/autoMBD/autombd-rtd-config/issues/57#issuecomment-5255578159)
- #57 #88 immediate P0 bootstrap decision：
  [comment 5357736646](https://github.com/autoMBD/autombd-rtd-config/issues/57#issuecomment-5357736646)
- #78 initial gate failure：
  [comment 5040067981](https://github.com/autoMBD/autombd-rtd-config/issues/78#issuecomment-5040067981)
- #78 P0 bootstrap final approval：
  [comment 5232159305](https://github.com/autoMBD/autombd-rtd-config/issues/78#issuecomment-5232159305)
- #82 publication contract freeze：
  [comment 5284388354](https://github.com/autoMBD/autombd-rtd-config/issues/82#issuecomment-5284388354)
- #82 final Candidate A2 acceptance：
  [comment 5377572905](https://github.com/autoMBD/autombd-rtd-config/issues/82#issuecomment-5377572905)
- #83 recovery handoff contract v1：
  [comment 5256000575](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5256000575)
- #83 final v8 acceptance：
  [comment 5378492042](https://github.com/autoMBD/autombd-rtd-config/issues/83#issuecomment-5378492042)
- #88 replacement Test packet：
  [comment 5364333974](https://github.com/autoMBD/autombd-rtd-config/issues/88#issuecomment-5364333974)
- #88 final merge acceptance：
  [comment 5365857953](https://github.com/autoMBD/autombd-rtd-config/issues/88#issuecomment-5365857953)
- #90 replacement Test packet：
  [comment 5412555131](https://github.com/autoMBD/autombd-rtd-config/issues/90#issuecomment-5412555131)
- #90 final acceptance：
  [comment 5413955608](https://github.com/autoMBD/autombd-rtd-config/issues/90#issuecomment-5413955608)
- #85 R2 Human Gate 1 packet：
  [comment 5425567948](https://github.com/autoMBD/autombd-rtd-config/issues/85#issuecomment-5425567948)
- #85 R2 Candidate A1：
  [comment 5426287765](https://github.com/autoMBD/autombd-rtd-config/issues/85#issuecomment-5426287765)
- #85 R2 Candidate A2：
  [comment 5432701432](https://github.com/autoMBD/autombd-rtd-config/issues/85#issuecomment-5432701432)
- #85 R2 Candidate A3 freeze：
  [comment 5432817909](https://github.com/autoMBD/autombd-rtd-config/issues/85#issuecomment-5432817909)
- #93 structured handoff and unified guard bootstrap issue：
  [issue 93](https://github.com/autoMBD/autombd-rtd-config/issues/93)
- #85 dependency/lifecycle correction after #93 creation：
  [comment 5465899028](https://github.com/autoMBD/autombd-rtd-config/issues/85#issuecomment-5465899028)

### A.4 关键 Git 拓扑证据

- #78 minimal P0 anchor：`6cecde0f44f1ede2347c2c8a9238008bce59602e`；
  cumulative Implementation tips：`d54ce313`、`c1f86e8`、`02d5962`、`31cbc94`、
  `57373f5`；final Test/Implementation/Candidate：`fe8cc87` / `c7dc051` /
  `31e913d`；lesson/integration：`3f24f6b`；PR #84 merge：`d1dc62c`。
- #82 incremental Implementation：`e9de3a0 → fa94227`；Candidate/lesson：
  `616b7fc → c896174`。
- #88 sibling Implementation evidence：`a84dd66`、`025fe55`、`10ee5c0`；
  Candidate/lesson：`a6429a6 → 091da706`。
- #83 retained Implementation and final v8 lineage：`10a89f0`；
  `3b6c364 → 748a547 → 228c9d3`；Test/Candidate/lesson：
  `6648f94` / `d510f09` / `69b4e217`。
- #90 retained Implementation/Test/Candidate/lesson：`d0a1274` / `f94eb2f` /
  `e72befe` / `9331d668`。
- #85 R2 sibling Implementation evidence：`130af4c`、`bb4a2c6`、`80f7e6b`。

上述关系来自本地 Git object/parent/blob/diff 审计；Owner 提供的提交图截图用于
定位历史阶段，不替代 Git 对象本身。

### A.5 本地 ignored execution evidence

以下文件用于复盘，但不是可移植的 repository trust root：

- `.agent-state/handoffs/issue85-r2-interface-handoff.json`
- `.agent-state/handoffs/issue85-r2-reference-prevalidation.json`
- `.agent-state/handoffs/issue85-r2-candidate-a1-failure.md`
- `.agent-state/handoffs/issue85-r2-candidate-a2-failure.md`
- `.agent-state/handoffs/issue85-r2-candidate-a3-freeze.md`
- `.agent-state/issue-85/handoff-events.jsonl`

### A.6 证据限制

- 本地 ignored evidence 可能被清理，故本文件只把它作为历史诊断，不把它当成
  未来 acceptance evidence；
- GitHub comment 引用证明历史过程，不替代当前 remote-state verification；
- BT-0008 当时只纠正本地文档与 ignored 执行计划，没有改写 #86/#93 等 GitHub
  评论；BT-0009 获得同步授权后修正当前 issue 正文/索引并记录 superseding receipts。
  历史评论中的 Implementation-only 或 KPI 自动优化表述保留作历史，不作为新执行
  依据；远程变更应以本轮逐项回读结果为准，不把本地编辑冒充 remote write；
- 未合并历史 lesson commit 证明“曾发现过问题”，不自动成为当前规范；
- 截至 BT-0005 的原始审阅动作只创建 #93 并在 #85 追加依赖/生命周期纠偏评论；
  BT-0006 另行记录已创建的 #94–#98 和现有 issue 的 dependency comments。两阶段
  都没有修改 workflow contract、现有 Candidate refs 或 product/runtime。

## Changelog

| Version | Date | Changes |
| --- | --- | --- |
| 0.12.2 | 2026-09-06 | Recorded Human-commanded #93 implementation, final scoped verification and independent closure of actual findings in BT-0011; distinguished unmerged worktree capability from the preserved audit baseline, retained source and old evidence, and stopped for Human inspection without commit/PR/merge. |
| 0.12.1 | 2026-09-06 | Recorded Human closure of #95 and manual #93 contract preparation, verified the same-name published branch/upstream, and appended BT-0010; new wire details remain an unapproved ignored draft rather than active rules. |
| 0.12.0 | 2026-09-06 | Recorded Human-approved Worker-unit / Tester-functional / CLI-only comprehensive KPI tiers; defined Reviewer-to-PR ticket intake, merge plus Human-start prerequisites, one-way KPI issue with Human case/result review and no Worker correction, direct legacy case migration without retrospective test backfill, local JSON/Dashboard delivery and deferred server CT; split #100/#101/#102, narrowed #98 dependencies, synchronized current planning authority and added BT-0009 while preserving historical events and changelog rows. |
| 0.11.0 | 2026-09-05 | Corrected the full document to deliver the exact accepted Candidate as PR head, including frozen Test and final Implementation; withdrew the Implementation-only and Test-in-history-as-contamination interpretations, aligned finalization/#93/#86/bootstrap guidance, distinguished manual Phases 0–3, and added BT-0008 without rewriting prior events or changelog rows. |
| 0.10.0 | 2026-09-05 | Recorded PR #99 acceptance and the Human-commanded direct #95 branch implementation, focused monitoring/timeout compatibility evidence, deferred deployment/#98 boundaries, and BT-0007; preserved earlier trace events and audit baselines. |
| 0.9.0 | 2026-09-05 | Corrected the Phase 0 trust trace before PR: made #94 → #57 Phase 1 → #95 → #93 the explicit order and bound Phases 0–3 to Human-commanded `MANUAL-BOOTSTRAP`; split B1-1/B1-2 to #93 and B1-3/B1-4/B1-5 to #86; scoped off-main/finalization ancestry checks to current-task additions in `G..accepted-Implementation-PR`; recorded #94–#98 and dependency-comment receipts; updated the derived snapshot; and appended BT-0006 without rewriting BT-0001…BT-0005. |
| 0.8.0 | 2026-09-04 | Recorded the Human-approved two-plane time-control design: dynamic Orchestrator supervision for Agent tasks, deterministic configurable deadlines for project tools, Codex/OpenCode harness boundaries, interruption routing, current timeout inventory, narrow validation scope, and dependency-ordered Timeout Packages A/C/D/E. Added Owner decisions 18–21 and append-only trace BT-0005 without claiming implementation. |
| 0.7.0 | 2026-09-03 | Recorded local guard-failure routing, structured guard results, immutable replacement/report-only repair, same-lane continuity, safe evidence fallback, side-effect-aware retry and unchanged correction accounting; explicitly excluded real guard/timeout implementation defects from PROCESS exemptions. Appended BT-0004 and preserved earlier trace/changelog history. |
| 0.6.0 | 2026-08-30 | Froze the structured-handoff architecture: `G` remains a Git identity rather than a file; task semantics move to canonical `K`/Envelope/Report artifacts; prompts are locator-only and chat responses notification-only; removed generic `description_session`; retained one Tester role across Test Gate authoring/prevalidation and Candidate acceptance and one Worker across incremental corrections; accepted Orchestrator LLM semantic redaction as the v0.1 trust boundary; defined the complete minimal artifact family, unified #88/#90 guard responsibilities, role prompt examples, #93→#85 dependency, and trace event BT-0003. |
| 0.5.0 | 2026-08-29 | Defined safe and accurate Orchestrator dispatch: `W` is derived from exact `G` rather than independently selected; `K` v0.1 is an explicitly unimplemented Shared Task Brief with canonical ignored Orchestrator storage plus byte-identical lane-local snapshots; Test/Worker Launch Envelopes are the actual role prompts and preserve role design freedom through scope/boundaries/expected seams instead of fixed file allowlists; Gate 1 approves only exact Test while G/K/Impact/prevalidation remain supporting identity/evidence; added safe-point ambiguity return, full-replacement K revision, two-lane follow-up/ACK, stale-K rejection and Candidate-failure-vs-contract-ambiguity rules; added trace event BT-0002. |
| 0.4.0 | 2026-08-29 | Renamed the review into the bootstrap trust-tracing lane; corrected Gate 1 to trigger on Test ready without waiting for or reviewing Implementation; defined Governor, global Workflow Contract, Task Contract Epoch and Candidate series change control; fixed Candidate 0 plus three Worker corrections/four-Candidate accounting and reclassified historical A1/A2/A3 freezes as only `C0/C1/C2`; added confidential Tester root-cause analysis and sanitized-but-actionable Worker Correction Envelope; froze impact-selected testing and prohibited task-level full-suite runs; precisely scoped evidence-integrity, security/safety and mandatory-acceptance blockers; synthesized Legacy LSK-1–7 and LL-001–046; added derived snapshot and append-only trace event BT-0001. |
| 0.3.0 | 2026-08-29 | 按 Owner 时间线重建 #57→#78→#83/#88→#82→#83→#85/#90→#85；用 Git 证明 #78 成功依赖连续 Implementation bootstrap，而操作 playbook 后来未进入 active trust root；审计真实重写、sibling-lineage 丢失和正确增量复用；确认 Test/Candidate/Reviewer lesson 进入主线的系统性拓扑污染；将流程纠正为同 Governor 双 lane、Tester Gate 前全链预验证、Human-approved Test 永久冻结、Candidate 0 加三次增量修正（最多四个 Candidate）、Tester 结果经 Orchestrator 去泄漏后返回同一 Worker、terminal Reviewer 成功/失败恰好一次、accepted Implementation-only PR；重排 P0-A→#85→#86/finalization→后续执行计划。 |
| 0.2.0 | 2026-08-28 | 将历史复盘扩展为 #78、#82、#83、#88、#90 五个已合并关键 Issue 的纵向案例；逐项记录初始误判、失败链、最终收敛机制、永久成果与残余边界；以 #85 R2 作为组合能力不足的反证；增加跨 Issue 对照矩阵、共同成功机制和禁止采用的错误历史叙事。 |
| 0.1.0 | 2026-08-28 | 首次盘点主线 Agent Loop 的治理、静态验收、#88、#90、初始化和外部操作边界；初步复盘重复失效模式；区分显式设计边界、已证实缺陷、集成缺口、计划未落地能力和待验证风险；提出保留现有 P0 成果的 `BOOTSTRAP-LIMITED` 流程、双重预验证、语义交接附件、attempt 分类判据和未知问题升级门槛。 |
