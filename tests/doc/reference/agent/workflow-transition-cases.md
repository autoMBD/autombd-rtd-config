# Workflow Transition — 功能用例

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-09-07 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Issue #85 的稳定场景编号、关联需求与可观察结果；不承载执行过程或运行证据。 |

依据 [K5 完整需求参考](workflow-transition-requirements.md)。下表保留既有 34 个场景族及判据；参数化变体属于同一场景，不另造编号。标注“静态”的项只检查声明，不代表功能语义执行；本文件本身不表示批准或运行通过。

| 用例编号 | 需求 ID | 场景与必要区分条件 | 可观察预期结果 |
| --- | --- | --- | --- |
| AGENT-FUNC-085-001 | R02、R03 | 初始状态与 API 输入边界：新 task/governor；非法 JSON API 值或 task 字段。 | 合法输入得到完整 14 字段空状态：各引用为 null，test/worker 对象存在，repairs/consumed 为空；原输入不变，返回对象不共享可变状态。非法 API 参数只能产生 WorkflowTransitionError 及 error 对象；初始化的非事件输入允许 MALFORMED_EVENT 或 INVALID_STATE，不能泄露原生异常。 |
| AGENT-FUNC-085-002 | R04、R05、R20 | 入口封闭结构优先于状态错误：入口/event/context/artifact 非法与非法 state 同时存在；包括 guard-result 作为业务事件。 | 全部返回 MALFORMED_EVENT，优先于同时存在的状态或证据错误；guard-result 只能作为证据，不能推进业务状态。 |
| AGENT-FUNC-085-003 | R03、R07、R20 | 状态自洽与已接受历史不可跳跃：状态结构、已消费引用或已接受 I/C 历史自相矛盾；可同时缺回执。 | 返回 INVALID_STATE，而非 DUPLICATE_EVENT、MISSING_EVIDENCE 或对伪造历史继续执行；所有输入保持原状。索引合法性来源于已接受历史，不能以事件/提交数量替代。 |
| AGENT-FUNC-085-004 | R06、R20 | 可见身份漂移与重复消费的优先级：可见 task/G/K 漂移、重复事件/引用、同 artifact ID 不同引用；可同时缺回执。 | 身份漂移及同 ID 不同引用返回 STALE_EVENT；相同已消费事件或 exact artifact 返回 DUPLICATE_EVENT，均先于缺少回执。不能重复推进或把身份冲突当成普通重复。 |
| AGENT-FUNC-085-005 | R05、R07、R20 | 内存目录缺项与目录唯一性：内存目录缺 incoming/receipt/state 引用/前驱，或 artifact ID 重复。 | 缺项返回 MISSING_EVIDENCE，不能伪装为 INVALID_STATE；目录 ID 重复是入口结构错误 MALFORMED_EVENT。 |
| AGENT-FUNC-085-006 | R05、R06、R20 | CHECKED 证据必须真实匹配：回执字段或业务/回执正文摘要不匹配。 | 全部返回 INVALID_EVIDENCE；既核对业务引用 digest，也核对回执自身 digest，不能接受布尔式或仅状态名为 CHECKED 的伪证据。 |
| AGENT-FUNC-085-007 | R08、R09 | 两条 lane 独立就绪及撤回：仅一条 lane 启动；或 Test 批准前 READY 撤回/REQUEST_CHANGES。 | Worker 不等待 Test，Test 批准不等待 Worker；撤回只清除本 lane 的当前 READY，另一 lane 和历史保持；Test 请求修改不丢失 I，允许同 lane 修订后批准。 |
| AGENT-FUNC-085-008 | R09、R20 | Test 批准冻结与 STOP gate 区分：Test 已 APPROVE 后的新 Test/K；以及 TEST/STOP。 | 冻结后的 Test/K 变更返回 ILLEGAL_TRANSITION，优先于缺少证据；TEST/STOP 同样非法且 state.stop 仍为 null，不能当作全局 FINAL/STOP。 |
| AGENT-FUNC-085-009 | R10 | C0 前同 lane 的 I0 细化：尚无 C0，同一 Worker lane 的新 index0 READY。 | 当前 worker.ready 更新到新引用，implementation_index 仍为 0；不是纠正轮次，也不创建新 lane。真实 Git 祖先关系不由本内存用例认证。 |
| AGENT-FUNC-085-010 | R11、R20 | Candidate 的前置条件和精确绑定：未批准 Test 的 C0；T/I/manifest/Impact 绑定漂移；未变化 I 的再次组装。 | 无批准为 OUT_OF_ORDER_EVENT；绑定漂移为 STALE_EVENT；无新 I 的再次组装为 ILLEGAL_TRANSITION。不能把缺少回执抢在这些更高优先级错误之前。 |
| AGENT-FUNC-085-011 | R12、R17 | 当前执行结果只消费一次并决定终态路线：C0 的 PASS/三类 invalid 终态结果；同执行第二个不同结果。 | 四类终态结果都禁止继续开发，返回 ILLEGAL_TRANSITION；Reviewer 原因与 outcome 一致。相同执行的第二份新结果也非法，不能用不同 artifact_id 翻转既有 verdict。 |
| AGENT-FUNC-085-012 | R13、R20 | INVALID_RUN 只重跑同 Candidate，身份不能复用：INVALID_RUN 后同 Candidate 重跑；旧结果、历史 execution/dispatch ID 复用（有/无回执）。 | INVALID_RUN 不授权 correction/review。合法 rerun 仅替换 active envelope 并清空 result，T/I/索引不变；rerun_of 是当前 INVALID_RUN 报告，且该报告和旧 Candidate envelope 都是直接前驱。旧结果与历史 execution/dispatch ID 复用均返回 STALE_EVENT，先于缺少回执；新执行随后仍能消费合法 PASS。 |
| AGENT-FUNC-085-013 | R10、R14、R20 | 修正授权不等于完成修正：IMPLEMENTATION_FAIL 后 pending correction、NOT_READY、新 I READY；授权绑定漂移。 | 只允许一个 pending_correction；重复授权 ILLEGAL_TRANSITION。NOT_READY 保留旧 READY I 和 pending，I1 READY 才清 pending 并推进；漂移为 STALE_EVENT，不创建新 session，不用授权次数冒充完成次数。 |
| AGENT-FUNC-085-014 | R07、R15 | K 修订保留源状态并要求双 ACK：Test 批准前连续 K 修订；仅一个 ACK 与精确双 ACK。 | 修订保留历史 T/I 引用，但 ACK 不是 READY；只有一份 ACK 时 READY/批准返回 OUT_OF_ORDER_EVENT，旧 K READY 不能授权新 K。两份精确 ACK 消费后才能完成新 K 就绪/批准/组装。 |
| AGENT-FUNC-085-015 | R16、R17、R18 | 全局 STOP 保留实际源状态和单次 review：K、I READY、C0、pending correction、review/proposal 等非关闭阶段 STOP；I 超前于 C。 | STOP 不改变保存的 worker/candidate/review；不伪造新的失败测试或第二个 review。I1 超前场景保留 C0 和 I1，terminal candidate_index=0、correction_count=1；失败结果 accepted_candidate=null。 |
| AGENT-FUNC-085-016 | R12、R17、R20 | 终态 review 的入口与唯一性：无结果、INVALID_RUN、PASS 或已启动 review。 | 无结果为 OUT_OF_ORDER_EVENT；INVALID_RUN 仅允许重跑，故 review 为 ILLEGAL_TRANSITION；已有一次 review 后，第二次 review 和 correction 均非法。 |
| AGENT-FUNC-085-017 | R16、R18、R20 | 成功提案、最终决策和失败关闭分开：成功 proposal、未最终批准 MERGED、Reviewer/Human 拒绝、已失败关闭。 | 未变化 proposal 为 ILLEGAL_TRANSITION；缺最终批准的 MERGED 为 OUT_OF_ORDER_EVENT。拒绝只能进入真实失败，不重开 correction；关闭后的完全重复事件仍优先 DUPLICATE_EVENT，新业务为 ILLEGAL_TRANSITION。 |
| AGENT-FUNC-085-018 | R19 | 未消费的格式错误原件经 repair 后只应用一次：未消费 Worker READY 格式错误原件及保持业务字段的合法 replacement。 | repair 只追加 repairs，不建立 READY；替代件才建立一次 index0 READY，repairs 长度保持 1；不要求被拒原件通过完整 artifact schema。 |
| AGENT-FUNC-085-019 | R05、R19、R20 | raw 原件权限与可信业务字段：rejected repair original 的非规范合法 raw、重复键/截断/正文不等；普通 artifact/receipt 的 raw。 | 合法非规范 raw 在 digest 与严格解析 body 一致时允许修复；重复/不可解析/不相等为 INVALID_EVIDENCE。普通 artifact 的 raw 是权限违反 INVALID_EVIDENCE；checks 不允许 raw 成员，返回 MALFORMED_EVENT。 |
| AGENT-FUNC-085-020 | R09、R19 | 已消费 READY 的格式替代不重放业务：已消费 Worker/Test READY 的格式替代；或替代件篡改 status/tip/index。 | 合法替代只更新当前交付引用并保留业务状态，不能再应用 READY、失去批准或改计数；篡改业务字段均为 INVALID_EVIDENCE。 |
| AGENT-FUNC-085-021 | R02、R22 | 纯内存核心和导入不得访问外部服务：完整内存输入；受监测的文件/进程/网络/时间/随机等调用和导入加载。 | 初始化/transition 仍成功且输入不变；导入后公共 transition 可调用，无 tripwire 触发。该检查是所列入口的动态保障，不宣称操作系统能力隔离或远程认证。 |
| AGENT-FUNC-085-022 | R21 | CLI 输入解析先于 reducer 且不覆盖输入：CLI 输入为非法 JSON、重复键、float/nonfinite 或非对象根。 | exit 2；stdout 为空；stderr 是唯一规范 error JSON 加 LF，code=INPUT_ERROR，无 traceback；输入字节原样保留。 |
| AGENT-FUNC-085-023 | R21 | CLI 参数错误为结构化 JSON：CLI 参数为空、未知、不完整或多余。 | exit 2、stdout 空、stderr 唯一规范 JSON/LF，code=USAGE_ERROR；不输出普通 argparse 错误正文替代约定格式。 |
| AGENT-FUNC-085-024 | R21 | CLI help 是明确的普通帮助例外：CLI --help。 | exit 0，stdout 含正常 usage 帮助，stderr 空；不要求 help 输出 JSON。 |
| AGENT-FUNC-085-025 | R20、R21 | CLI 文件错误、业务拒绝和适配层异常路由：CLI 不可读文件、重复业务；调用点 INVALID_OUTPUT/未知异常注入。 | 不可读文件：exit2 INPUT_ERROR；业务重复：exit1 DUPLICATE_EVENT；输出不变量故障：exit2 INVALID_OUTPUT；未知异常：exit2 EXECUTION_ERROR。每次 stdout 空、stderr 唯一规范 JSON/LF，无 traceback 或私有异常 marker。故障注入只验证适配层路由，不证明 reducer 的所有内部输出不变量。 |
| AGENT-FUNC-085-026 | R20 | 诊断不回显私有输入：非法公共入口带可识别私有 marker。 | error 文本不含 marker 或 traceback；不能把原始私有 payload 作为诊断返回。 |
| AGENT-FUNC-085-027 | R01–R12、R17、R18、R21、R23 | 成功链：从初始化到 exact Candidate 的 MERGED：两个独立身份、SHA 和 lane 顺序的成功生命周期。 | 每步完整新状态与独立预期一致、仅一次 consumed 追加、输入不变；父顺序/绑定保持 T 再 I。最终无 pending correction，accepted_candidate 为精确 C0；所有 CLI 成功 exit0、stdout 唯一规范状态 JSON/LF、stderr 空，输入文件不变。 |
| AGENT-FUNC-085-028 | R10–R14、R17、R18、R21、R23 | 失败链：C0 到 C3 三次修正耗尽：两个独立身份、SHA 和 lane 顺序的 C0..C3 修正耗尽生命周期。 | 授权/NOT_READY 不推进完成数；新 I READY 前旧 I 保留，新 I READY 后 Candidate 仍保留旧 C，直到合法组装；最终最新 I index=3、accepted_candidate=null，Test 始终冻结；CLI 每事件状态一致、exit0、stdout 唯一规范 JSON/LF、stderr 空且输入字节不变。 |
| AGENT-FUNC-085-029 | R01、R22 | 既有协议和兼容入口保持原样（静态）：G 中明确不可修改的 11 个协议/兼容入口文件。 | 11 项全部相等；不通过修改旧协议/角色/兼容入口来容纳新 reducer。仅是字节保持检查，不重跑这些已有工具的全部单元测试。 |
| AGENT-FUNC-085-030 | R03、R04、R05 | State/Event/Context 定义封闭且完整（静态）：交付 schema 的 State/Event/Context。 | State 为 K 的 14 个顶层字段，Event 为 schema_version/type/event_id/artifact/checked，Context 为 schema_version/workflow_profile/task/governor/protocol/artifacts/checks；required 与字段全集相同且额外字段禁止。 |
| AGENT-FUNC-085-031 | R03、R04、R05、R22 | 共享 Task/Governor/ArtifactRef 域一致（静态）：新 schema 与当前 handoff schema 的共享定义。 | Task/Governor 与当前协议完全一致；ArtifactRef 只允许复用原 kind 域或去掉 guard-result 的业务子集，其余域保持不变；不能依赖忽略目录/任意外部引用。 |
| AGENT-FUNC-085-032 | R03、R04、R05 | 封闭 wire 的内存示例与额外字段拒绝（静态）：合法 wire 示例与顶层/State 嵌套额外字段。 | 合法示例全部通过；每个额外字段变体均被 schema 拒绝。本项是声明结构检查，不替代 reducer 的生命周期运行。 |
| AGENT-FUNC-085-033 | R22、R23、R24、R25 | 本次声明源码头与语法（静态）：公开变更清单中的 3 个 production 与 2 个 Worker generality 文件。 | 五文件均存在，头部包含项目/文件/作者/日期/版本/描述与 MIT/SPDX，语法可编译。不能据此宣称 Worker TDD 已执行、generality 充分或复用来源正确；这些仍由各自证据和终态审查判定。 |
| AGENT-FUNC-085-034 | R02、R20、R21、R22、R25 | 公开接口说明包含实际接口与错误名（静态）：交付的公共 workflow-transitions.md 接口说明。 | 所列名称全部出现；缺项失败。仅证明声明存在，不证明自然语言语义正确、转换表完整或 salvage 解释充分，终态 Reviewer 仍审查这些非执行要求。 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.1.1 | 按 Human 要求增加用例总览表，将 34 项明细改为表格；保留原编号、五组说明、自动化映射与所有测试判据，不修改脚本或扩大范围。 |
| 2026-09-06 | 0.1.0 | 根据 #85 K4/Human 文档要求建立 Agent 类型增量目录；将既有 133 功能与 24 静态节点对应到 34 个可审阅场景族，保留作用域和预期，不回填历史已接受功能。 |
| 2026-09-07 | 0.2.0 | 迁移至功能独立参考，保留原场景/判据并精简为用例表；执行过程、节点对应与证据由脚本和结构化报告/Impact Set 承载，需求另文完整呈现。 |
