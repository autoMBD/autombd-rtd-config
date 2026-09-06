# Agent 功能测试用例

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | 按稳定用例编号维护 Agent 功能行为、可观察判据及自动化映射，作为 Human 的用例审阅入口。 |

## 1. 目录边界与审阅方式

本文件是 Agent 类型的增量功能用例目录。本次仅纳入 issue #85 的新纯内存转换器，不为历史已接受代码补写用例，也不扩大到 RTD CfgFile CLI 产品、S32DS、黑盒 E2E 或 KPI。RTD CfgFile CLI 的新功能目录按类型另建；KPI 用例仍由独立 KPI test issue 在 docs/tests/ 维护，本次不迁移或改写。

用例依据是 #85 完整公开 Task Contract 的 R01–R25；当前文档义务由 Human 确认的 R23/R24 补充。文档定义可审阅的场景、输入、操作和结果，自动化实现这些已定义的场景；不从 Worker 实现或历史隐藏测试推导期望。既有本轮自动化按同一 K 保留并与文档逐项对齐，不伪造“文档早于已存在代码”的历史。

Human 先审阅本文件的前提与判据，再按需追踪自动化；不要求通过阅读 Python 才能知道用例在验证什么。批准时同一 Test 提交树绑定本文档和脚本，批准后的系列保持两者及 Impact Set 冻结。当前未接受的本文档与 owner 脚本同属 Tester 私有材料，不向 Worker 披露。

后续新增 Agent 用例沿用本目录，在已接受内容上增量添加；已有编号不重分配。修改已接受判据须有明确的新需求/授权并追加版本记录；不能为迎合实现结果改写预期。AGENT-FUNC-085-001..034 是本次保留场景族，参数化变体是同一场景的输入分支，不按运行次数另造编号。

## 2. 共同前提、判据与执行映射

- 公共入口是 initial_state(task, governor)、transition(state, event, context=...)、WorkflowTransitionError.as_dict() 及相应 init/apply CLI。G 中的 Wv2、handoff-v1 schema 与 functional-development-v1 registry 为协议基线，调用方显式提供已加载内存对象。
- 输入使用独立合成 task/G/W/commit/digest，业务 artifact 及 CHECKED 回执遵守现有协议域；这些是可控离线验证输入，不是远程 Human、Git ancestry/direct union 或操作系统隔离的证明。除明确缺项/篡改分支外，输入都有精确引用、schema、digest 和直接前驱。
- 使用 H 构造器的每次成功消费都比较完整期望状态；期望由用例步骤独立构造，不从被测返回值反推。检查原 state/event/context 不变且 consumed 只增加当前事件一次。使用 H.reject 的拒绝分支重复执行以比较确定性错误对象，检查 code、以 / 起始的公共 pointer、非空 message、{error:{code,pointer,message}} 形状及输入不变；初始化 API、诊断隐私和 CLI 专项按各自下列判据检查，不宣称这些专项逐项重复调用。
- 任何规定的状态/错误/输出/只读条件不满足，即该分支失败；参数族必须全部分支通过。F 组是运行功能检查；S 组明确标为静态/声明检查，不能以“静态通过”声称语义运行或全域实现完备。
- CLI（help 除外）成功 exit0、唯一规范 UTF-8 状态 JSON 加 LF 位于 stdout，stderr 空；失败 stdout 空、唯一规范 error JSON 加 LF 位于 stderr。规范 JSON 是排序键、紧凑格式、无非有限数。用例专门声明的 exit1/exit2 分类必须匹配；所有临时输入只放在 tests/.tmp/。

自动化定位别名：

| 别名 | 自动化文件 | 选择 |
| --- | --- | --- |
| F | [test_workflow_transition.py](../functional/test_workflow_transition.py) | 本文件全部 133 个参数化功能节点 |
| S | [test_workflow_transition_contract.py](../functional/test_workflow_transition_contract.py) | 本文件全部 24 个静态节点 |
| H | [workflow_transition_cases.py](../functional/workflow_transition_cases.py) | F/S 共用的 schema-grounded 输入与独立期望构造支持，不是独立验收用例 |

下方 F::/S:: 后面的名称就是对应 pytest 函数节点；不带参数后缀意味着执行该函数的全部参数变体。对只读 Candidate 的两条行为/声明脚本命令为：

```console
python -m pytest tests/functional/test_workflow_transition.py -q -p no:cacheprovider --basetemp tests/.tmp/issue85-functional
python -m pytest tests/functional/test_workflow_transition_contract.py -q -p no:cacheprovider --basetemp tests/.tmp/issue85-static
```

另有一条仅针对本文档及 F/S 源码的只读静态对应性命令，精确 argv 随 Test Impact Set 冻结：核对 34 个编号唯一、每项五组说明存在、58 个函数定位与两份脚本的全部测试函数相等且无遗漏/未知/重复，以及文档元数据与变更记录存在。它只审计本次新文档交付，不是新增业务场景、通用文档 validator 或文档语义正确性的证明。

owner 的参考预验证可通过显式受控环境绑定独立参考实现/schema/静态正例；该绑定与原始日志必须随证据保存。正式 Candidate 运行不得继承这些参考覆盖。预验证证明用例能执行/区分已知缺陷，不等于 Candidate PASS，也不等于 Human Test Gate 批准。

## 3. Issue #85 用例

### AGENT-FUNC-085-001 — 初始状态与 API 输入边界

- 目的/需求：R02、R03；验证初始状态与 API 输入边界。
- 前置与输入：新的 task/governor；另准备 null、数组、布尔、浮点、非有限数、缺少字段的 task，以及布尔 issue_number。
- 操作步骤：调用 initial_state；修改返回对象中的 task/worker，再以原输入调用；逐一提交非法 task。
- 预期与通过判据：合法输入得到完整 14 字段空状态：各引用为 null，test/worker 对象存在，repairs/consumed 为空；原输入不变，返回对象不共享可变状态。非法 API 参数只能产生 WorkflowTransitionError 及 error 对象；初始化的非事件输入允许 MALFORMED_EVENT 或 INVALID_STATE，不能泄露原生异常。
- 自动化映射：`F::test_initial_state_is_complete_closed_and_independent`；`F::test_initial_programmer_errors_are_structured`。

### AGENT-FUNC-085-002 — 入口封闭结构优先于状态错误

- 目的/需求：R04、R05、R20；验证入口封闭结构优先于状态错误。
- 前置与输入：当前协议构造的合法事件/context，并同时准备非法 state；变体包括额外字段、旧 F0 类型、错误版本、布尔 checked、错误引用 kind、旧 profile/W、缺少协议定义、布尔 issue_number；另准备带额外 payload 字段的业务 artifact 和被当作业务事件的 guard-result。
- 操作步骤：每次只引入一个入口变体，调用 transition；对同一输入重复调用。
- 预期与通过判据：全部返回 MALFORMED_EVENT，优先于同时存在的状态或证据错误；guard-result 只能作为证据，不能推进业务状态。
- 自动化映射：`F::test_malformed_wire_has_highest_priority`；`F::test_malformed_incoming_body_before_invalid_state`；`F::test_guard_receipt_is_not_a_business_event`。

### AGENT-FUNC-085-003 — 状态自洽与已接受历史不可跳跃

- 目的/需求：R03、R07、R20；验证状态自洽与已接受历史不可跳跃。
- 前置与输入：已消费 K 或已建立 C0；分别引入未知/缺少状态字段、错误槽位 kind、重复 consumed、布尔事件 ID、未消费的 stop 引用；或把现有 I/C 索引、previous_implementation、correction_count 改成跳跃/矛盾事实。
- 操作步骤：对被修改的状态提交重复事件或当前结果，部分变体同时删除回执。
- 预期与通过判据：返回 INVALID_STATE，而非 DUPLICATE_EVENT、MISSING_EVIDENCE 或对伪造历史继续执行；所有输入保持原状。索引合法性来源于已接受历史，不能以事件/提交数量替代。
- 自动化映射：`F::test_invalid_state_precedes_duplicate_and_evidence`；`F::test_available_state_facts_cannot_skip_accepted_history`。

### AGENT-FUNC-085-004 — 可见身份漂移与重复消费的优先级

- 目的/需求：R06、R20；验证可见身份漂移与重复消费的优先级。
- 前置与输入：已消费 K；准备 task_run、G commit 或 K digest 不符的 launch，以及完全重复的事件、同 artifact 的新 event_id、同 artifact_id 的不同 digest；移除对应回执。
- 操作步骤：分别调用 transition，重复调用同一拒绝输入。
- 预期与通过判据：身份漂移及同 ID 不同引用返回 STALE_EVENT；相同已消费事件或 exact artifact 返回 DUPLICATE_EVENT，均先于缺少回执。不能重复推进或把身份冲突当成普通重复。
- 自动化映射：`F::test_present_identity_drift_precedes_missing_receipt`；`F::test_duplicate_event_and_artifact_precede_missing_receipt`；`F::test_same_artifact_id_with_different_reference_is_stale`。

### AGENT-FUNC-085-005 — 内存目录缺项与目录唯一性

- 目的/需求：R05、R07、R20；验证内存目录缺项与目录唯一性。
- 前置与输入：K 已消费且 launch 其他绑定合法；分别缺 incoming、receipt、state 引用对应 artifact 或直接前驱；另分别在 artifacts/checks 中重复同 artifact_id。
- 操作步骤：提交各变体，不允许 reducer 访问文件补齐。
- 预期与通过判据：缺项返回 MISSING_EVIDENCE，不能伪装为 INVALID_STATE；目录 ID 重复是入口结构错误 MALFORMED_EVENT。
- 自动化映射：`F::test_missing_catalog_is_evidence_not_invalid_state`；`F::test_catalog_artifact_ids_are_unique`。

### AGENT-FUNC-085-006 — CHECKED 证据必须真实匹配

- 目的/需求：R05、R06、R20；验证CHECKED 证据必须真实匹配。
- 前置与输入：待消费的合法 K 及其精确回执；逐一修改 status、exit_code、evidence_available、violations、consumer_role、visibility、input 的 path/digest/artifact_id、trusted_context。独立准备未同步 digest 的回执/业务正文修改。
- 操作步骤：对字段变体重新计算回执引用 digest，以隔离业务证据矛盾；对正文篡改变体保留旧 digest 后调用。
- 预期与通过判据：全部返回 INVALID_EVIDENCE；既核对业务引用 digest，也核对回执自身 digest，不能接受布尔式或仅状态名为 CHECKED 的伪证据。
- 自动化映射：`F::test_available_false_checked_receipts_fail_closed`；`F::test_receipt_digest_and_artifact_digest_are_both_checked`。

### AGENT-FUNC-085-007 — 两条 lane 独立就绪及撤回

- 目的/需求：R08、R09；验证两条 lane 独立就绪及撤回。
- 前置与输入：分别只启动 Tester 或 Worker；以及两 lane 均 READY 但 Test 未批准的状态。撤回状态分别取 NOT_READY、CONTRACT_AMBIGUITY；另准备 TEST REQUEST_CHANGES。
- 操作步骤：单 lane 独立 READY；Tester 可独立申请批准。然后分别撤回一个 lane；最后执行 Test 请求修改、同 lane 再 READY、批准。
- 预期与通过判据：Worker 不等待 Test，Test 批准不等待 Worker；撤回只清除本 lane 的当前 READY，另一 lane 和历史保持；Test 请求修改不丢失 I，允许同 lane 修订后批准。
- 自动化映射：`F::test_lane_initial_readiness_is_independent`；`F::test_pre_freeze_withdrawal_clears_only_own_ready`；`F::test_test_request_changes_retains_worker_and_allows_same_lane_revision`。

### AGENT-FUNC-085-008 — Test 批准冻结与 STOP gate 区分

- 目的/需求：R09、R20；验证Test 批准冻结与 STOP gate 区分。
- 前置与输入：已消费 Test READY/APPROVE；准备新 Test READY、Test NOT_READY 或 K 修订并删除回执。另有未批准 Test READY 的 TEST/STOP 决策。
- 操作步骤：分别提交冻结后的变更；提交 TEST/STOP。
- 预期与通过判据：冻结后的 Test/K 变更返回 ILLEGAL_TRANSITION，优先于缺少证据；TEST/STOP 同样非法且 state.stop 仍为 null，不能当作全局 FINAL/STOP。
- 自动化映射：`F::test_approval_freezes_test_and_contract_before_evidence`；`F::test_test_stop_is_not_global_stop`。

### AGENT-FUNC-085-009 — C0 前同 lane 的 I0 细化

- 目的/需求：R10；验证C0 前同 lane 的 I0 细化。
- 前置与输入：已消费 K 和 Worker INITIAL launch，尚无 Candidate。
- 操作步骤：依次接收同 lane 的两个 index0 READY。
- 预期与通过判据：当前 worker.ready 更新到新引用，implementation_index 仍为 0；不是纠正轮次，也不创建新 lane。真实 Git 祖先关系不由本内存用例认证。
- 自动化映射：`F::test_before_c0_worker_same_lane_index0_refinement`。

### AGENT-FUNC-085-010 — Candidate 的前置条件和精确绑定

- 目的/需求：R11、R20；验证Candidate 的前置条件和精确绑定。
- 前置与输入：T/I 均 READY 但 Test 尚未批准；以及合法 C0 已存在。变体分别漂移 T commit、I commit、Test manifest digest、Impact Set digest，或从同一未更新 I 再组装。
- 操作步骤：无批准时删除回执后尝试 C0；对绑定漂移同样缺回执后提交；最后重复无新 I 的组装。
- 预期与通过判据：无批准为 OUT_OF_ORDER_EVENT；绑定漂移为 STALE_EVENT；无新 I 的再次组装为 ILLEGAL_TRANSITION。不能把缺少回执抢在这些更高优先级错误之前。
- 自动化映射：`F::test_candidate_requires_consumed_approval_before_missing_evidence`；`F::test_candidate_binding_drift_is_stale`；`F::test_duplicate_assembly_without_new_implementation_is_illegal`。

### AGENT-FUNC-085-011 — 当前执行结果只消费一次并决定终态路线

- 目的/需求：R12、R17；验证当前执行结果只消费一次并决定终态路线。
- 前置与输入：合法 C0；结果分别为 PASS、TEST_GATE_INVALID、CONTRACT_INVALID、INTEGRITY_INVALID。另为同一次执行预先构造两个不同结果 artifact。
- 操作步骤：消费结果后尝试 correction 和新 Worker READY；按该结果启动终态 Reviewer/terminal。对已完成执行提交第二份结果。
- 预期与通过判据：四类终态结果都禁止继续开发，返回 ILLEGAL_TRANSITION；Reviewer 原因与 outcome 一致。相同执行的第二份新结果也非法，不能用不同 artifact_id 翻转既有 verdict。
- 自动化映射：`F::test_terminal_outcome_prohibits_correction_and_new_worker`；`F::test_result_requires_current_execution_and_consumes_once`。

### AGENT-FUNC-085-012 — INVALID_RUN 只重跑同 Candidate，身份不能复用

- 目的/需求：R13、R20；验证INVALID_RUN 只重跑同 Candidate，身份不能复用。
- 前置与输入：合法 C0，保存原 T/I 状态和旧执行结果；随后消费 INVALID_RUN。身份复用变体先完成一次合法重跑并再次 INVALID_RUN，再尝试复用更早的 execution_id 或 dispatch_id。
- 操作步骤：INVALID_RUN 后尝试 correction/成功 review；提交合法 rerun；检查 rerun_of 与直接前驱；提交旧执行结果；分别在有/无回执时提交历史 ID 复用。
- 预期与通过判据：INVALID_RUN 不授权 correction/review。合法 rerun 仅替换 active envelope 并清空 result，T/I/索引不变；rerun_of 是当前 INVALID_RUN 报告，且该报告和旧 Candidate envelope 都是直接前驱。旧结果与历史 execution/dispatch ID 复用均返回 STALE_EVENT，先于缺少回执；新执行随后仍能消费合法 PASS。
- 自动化映射：`F::test_invalid_run_rerun_keeps_sources_and_rejects_stale_old_result`；`F::test_rerun_cannot_reuse_execution_or_dispatch_history`。

### AGENT-FUNC-085-013 — 修正授权不等于完成修正

- 目的/需求：R10、R14、R20；验证修正授权不等于完成修正。
- 前置与输入：C0 的 IMPLEMENTATION_FAIL；准备合法 correction1，以及 lane/session、previous_implementation、disclosure source digest 漂移变体。
- 操作步骤：接受一次 correction；再次授权；返回 NOT_READY；随后 I1 READY 并组装 C1。对绑定漂移删除回执后分别提交。
- 预期与通过判据：只允许一个 pending_correction；重复授权 ILLEGAL_TRANSITION。NOT_READY 保留旧 READY I 和 pending，I1 READY 才清 pending 并推进；漂移为 STALE_EVENT，不创建新 session，不用授权次数冒充完成次数。
- 自动化映射：`F::test_pending_correction_is_single_and_not_ready_does_not_spend_it`；`F::test_correction_exact_public_binding`。

### AGENT-FUNC-085-014 — K 修订保留源状态并要求双 ACK

- 目的/需求：R07、R15；验证K 修订保留源状态并要求双 ACK。
- 前置与输入：两 lane 在 K0 下 READY，Test 尚未批准；合法连续 K1 修订包含 predecessor 与 change authority。
- 操作步骤：消费 K1；先只重发 Tester launch/ACK；尝试 Tester READY 与批准旧 READY；再完成 Worker launch/ACK、两 lane 新 READY、Test APPROVE 和 C0。
- 预期与通过判据：修订保留历史 T/I 引用，但 ACK 不是 READY；只有一份 ACK 时 READY/批准返回 OUT_OF_ORDER_EVENT，旧 K READY 不能授权新 K。两份精确 ACK 消费后才能完成新 K 就绪/批准/组装。
- 自动化映射：`F::test_k_revision_two_ack_barrier_and_independent_launches`。

### AGENT-FUNC-085-015 — 全局 STOP 保留实际源状态和单次 review

- 目的/需求：R16、R17、R18；验证全局 STOP 保留实际源状态和单次 review。
- 前置与输入：分别停在 K、Worker READY、C0、pending correction、Reviewer 已启动、成功 proposal；另停在 I1 已 READY 而 active Candidate 仍为 C0。
- 操作步骤：消费精确 FINAL/STOP；无 review 时启动 HUMAN_STOP review，已有 review 时沿用；生成真实 RECORD_FAILURE。
- 预期与通过判据：STOP 不改变保存的 worker/candidate/review；不伪造新的失败测试或第二个 review。I1 超前场景保留 C0 和 I1，terminal candidate_index=0、correction_count=1；失败结果 accepted_candidate=null。
- 自动化映射：`F::test_global_stop_preserves_actual_sources_and_uses_one_review`；`F::test_stop_after_new_ready_preserves_implementation_ahead_of_candidate`。

### AGENT-FUNC-085-016 — 终态 review 的入口与唯一性

- 目的/需求：R12、R17、R20；验证终态 review 的入口与唯一性。
- 前置与输入：合法 C0 但尚无结果；以及 INVALID_RUN、PASS 后的状态。
- 操作步骤：无结果时尝试成功 review；INVALID_RUN 后再次尝试；PASS 后完成一次 review，再提交第二个 review 和 correction。
- 预期与通过判据：无结果为 OUT_OF_ORDER_EVENT；INVALID_RUN 仅允许重跑，故 review 为 ILLEGAL_TRANSITION；已有一次 review 后，第二次 review 和 correction 均非法。
- 自动化映射：`F::test_review_without_result_is_order_error_but_invalid_run_is_illegal`；`F::test_one_terminal_review_and_no_corrections_after_it`。

### AGENT-FUNC-085-017 — 成功提案、最终决策和失败关闭分开

- 目的/需求：R16、R18、R20；验证成功提案、最终决策和失败关闭分开。
- 前置与输入：PASS/APPROVED review 后的成功 proposal；另有 Reviewer REJECTED 或 Human FINAL REQUEST_CHANGES；以及 STOP 后已 RECORD_FAILURE。
- 操作步骤：重复未变化的 proposal；未最终批准就 MERGED；处理 Reviewer/Human 拒绝并 RECORD_FAILURE；对关闭状态重放相同 terminal 及提交新 STOP。
- 预期与通过判据：未变化 proposal 为 ILLEGAL_TRANSITION；缺最终批准的 MERGED 为 OUT_OF_ORDER_EVENT。拒绝只能进入真实失败，不重开 correction；关闭后的完全重复事件仍优先 DUPLICATE_EVENT，新业务为 ILLEGAL_TRANSITION。
- 自动化映射：`F::test_success_proposal_is_not_merge_and_cannot_repeat_unchanged`；`F::test_rejected_success_becomes_truthful_failure_without_corrections`；`F::test_closed_failure_rejects_new_business_but_duplicate_priority_wins`。

### AGENT-FUNC-085-018 — 未消费的格式错误原件经 repair 后只应用一次

- 目的/需求：R19；验证未消费的格式错误原件经 repair 后只应用一次。
- 前置与输入：Worker launch 后的一份未消费 READY 原件含未知格式字段；提供真实形状 REJECTED 回执和 delivery-repair，保留 tip/index/计数及 lane。
- 操作步骤：先消费 repair，再提交带 replaces、原件/拒绝/repair 前驱、授权 dispatch 的合法替代件。
- 预期与通过判据：repair 只追加 repairs，不建立 READY；替代件才建立一次 index0 READY，repairs 长度保持 1；不要求被拒原件通过完整 artifact schema。
- 自动化映射：`F::test_delivery_repair_bookkeeping_and_never_consumed_malformed_original`。

### AGENT-FUNC-085-019 — raw 原件权限与可信业务字段

- 目的/需求：R05、R19、R20；验证raw 原件权限与可信业务字段。
- 前置与输入：被明确拒绝的修复原件；raw 分别为合法非规范空白、重复键、截断 JSON、与 body 不同的正文。另在普通 artifact 或 receipt 条目上放入 raw。
- 操作步骤：提交 repair/合法替代件；逐一提交无可信原件和非法 raw 位置。
- 预期与通过判据：合法非规范 raw 在 digest 与严格解析 body 一致时允许修复；重复/不可解析/不相等为 INVALID_EVIDENCE。普通 artifact 的 raw 是权限违反 INVALID_EVIDENCE；checks 不允许 raw 成员，返回 MALFORMED_EVENT。
- 自动化映射：`F::test_raw_noncanonical_rejected_original_can_be_repaired`；`F::test_untrustworthy_raw_original_cannot_supply_repair_business_fields`；`F::test_raw_is_forbidden_on_normal_incoming_and_receipt_catalog`。

### AGENT-FUNC-085-020 — 已消费 READY 的格式替代不重放业务

- 目的/需求：R09、R19；验证已消费 READY 的格式替代不重放业务。
- 前置与输入：分别已有 Worker READY 和已批准的 Test READY；有保留业务字段的 repair/replaces。另对未消费 Worker READY 替代件篡改 status、implementation_tip 或 implementation_index。
- 操作步骤：消费 repair 和替代件；比较前后 tip、pending、Candidate、Test approval；逐一提交业务篡改变体。
- 预期与通过判据：合法替代只更新当前交付引用并保留业务状态，不能再应用 READY、失去批准或改计数；篡改业务字段均为 INVALID_EVIDENCE。
- 自动化映射：`F::test_consumed_ready_format_replacement_does_not_reapply_business`；`F::test_format_repair_cannot_change_preserved_business_values`。

### AGENT-FUNC-085-021 — 纯内存核心和导入不得访问外部服务

- 目的/需求：R02、R22；验证纯内存核心和导入不得访问外部服务。
- 前置与输入：已在调用方准备好完整内存 context；安装文件、Path、process、socket、time、random、UUID tripwire；另在导入路径禁止 schema/registry load 和文件读取。
- 操作步骤：在 tripwire 内调用 initial_state 与消费 K；在独立命名空间执行目标模块导入。
- 预期与通过判据：初始化/transition 仍成功且输入不变；导入后公共 transition 可调用，无 tripwire 触发。该检查是所列入口的动态保障，不宣称操作系统能力隔离或远程认证。
- 自动化映射：`F::test_pure_core_does_not_touch_external_services`；`F::test_import_does_not_load_schema_files`。

### AGENT-FUNC-085-022 — CLI 输入解析先于 reducer 且不覆盖输入

- 目的/需求：R21；验证CLI 输入解析先于 reducer 且不覆盖输入。
- 前置与输入：文件内容分别是截断 JSON、重复键、浮点、NaN、Infinity、null、数组、整数根。
- 操作步骤：通过真实进程调用 apply，把该文件作为输入；比较执行前后文件字节。
- 预期与通过判据：exit 2；stdout 为空；stderr 是唯一规范 error JSON 加 LF，code=INPUT_ERROR，无 traceback；输入字节原样保留。
- 自动化映射：`F::test_cli_input_errors_precede_reducer_and_never_overwrite`。

### AGENT-FUNC-085-023 — CLI 参数错误为结构化 JSON

- 目的/需求：R21；验证CLI 参数错误为结构化 JSON。
- 前置与输入：参数分别为空、未知子命令、不完整 apply、init 的未知参数。
- 操作步骤：逐一真实进程调用 CLI。
- 预期与通过判据：exit 2、stdout 空、stderr 唯一规范 JSON/LF，code=USAGE_ERROR；不输出普通 argparse 错误正文替代约定格式。
- 自动化映射：`F::test_cli_usage_errors_are_json`。

### AGENT-FUNC-085-024 — CLI help 是明确的普通帮助例外

- 目的/需求：R21；验证CLI help 是明确的普通帮助例外。
- 前置与输入：可导入的 CLI。
- 操作步骤：真实进程调用 --help。
- 预期与通过判据：exit 0，stdout 含正常 usage 帮助，stderr 空；不要求 help 输出 JSON。
- 自动化映射：`F::test_cli_help_is_explicit_normal_help_exception`。

### AGENT-FUNC-085-025 — CLI 文件错误、业务拒绝和适配层异常路由

- 目的/需求：R20、R21；验证CLI 文件错误、业务拒绝和适配层异常路由。
- 前置与输入：不存在的 task/governor 文件；重复消费 K 的合法 state/event/context 文件；在公共 transition 调用点分别注入 INVALID_OUTPUT 和未预期 RuntimeError。
- 操作步骤：依次真实进程调用 init/apply；使用受控调用点故障注入检查适配层，而非修改生产源码。
- 预期与通过判据：不可读文件：exit2 INPUT_ERROR；业务重复：exit1 DUPLICATE_EVENT；输出不变量故障：exit2 INVALID_OUTPUT；未知异常：exit2 EXECUTION_ERROR。每次 stdout 空、stderr 唯一规范 JSON/LF，无 traceback 或私有异常 marker。故障注入只验证适配层路由，不证明 reducer 的所有内部输出不变量。
- 自动化映射：`F::test_cli_unreadable_file_and_transition_rejection`。

### AGENT-FUNC-085-026 — 诊断不回显私有输入

- 目的/需求：R20；验证诊断不回显私有输入。
- 前置与输入：入口 artifact 的非法额外字段含可识别的私有 marker。
- 操作步骤：调用 transition 并读取结构化异常。
- 预期与通过判据：error 文本不含 marker 或 traceback；不能把原始私有 payload 作为诊断返回。
- 自动化映射：`F::test_error_text_does_not_echo_private_input_payload`。

### AGENT-FUNC-085-027 — 成功链：从初始化到 exact Candidate 的 MERGED

- 目的/需求：R01–R12、R17、R18、R21、R23；验证成功链：从初始化到 exact Candidate 的 MERGED。
- 前置与输入：两组互不相同的 task/G/W/源 SHA；分别 Tester-first、Worker-first。所有业务/回执由当前协议构造，使用 exact T/I/manifests/Impact refs。
- 操作步骤：初始化→K→独立 launches/READY→Test APPROVE→C0→Tester PASS→单次 APPROVED review→pr=null 成功 proposal→exact-head PR 更新→FINAL APPROVE→MERGED；对每一步再用真实 CLI init/apply 重放。
- 预期与通过判据：每步完整新状态与独立预期一致、仅一次 consumed 追加、输入不变；父顺序/绑定保持 T 再 I。最终无 pending correction，accepted_candidate 为精确 C0；所有 CLI 成功 exit0、stdout 唯一规范状态 JSON/LF、stderr 空，输入文件不变。
- 自动化映射：`F::test_success_lifecycle_python_and_cli`。

### AGENT-FUNC-085-028 — 失败链：C0 到 C3 三次修正耗尽

- 目的/需求：R10–R14、R17、R18、R21、R23；验证失败链：C0 到 C3 三次修正耗尽。
- 前置与输入：两组独立 task/G/W/源 SHA，交换 lane 启动顺序；已准备 C0。
- 操作步骤：C0..C3 各产生 IMPLEMENTATION_FAIL；在前三次失败后依次 correction→NOT_READY→I(n+1) READY→C(n+1)；C3 失败后以 CORRECTIONS_EXHAUSTED review→RECORD_FAILURE。用真实 CLI 重放初始化及每次消费。
- 预期与通过判据：授权/NOT_READY 不推进完成数；新 I READY 前旧 I 保留，新 I READY 后 Candidate 仍保留旧 C，直到合法组装；最终最新 I index=3、accepted_candidate=null，Test 始终冻结；CLI 的状态、字节输出和只读输入要求同成功链。
- 自动化映射：`F::test_three_corrections_exhaustion_python_and_cli`。

### AGENT-FUNC-085-029 — 既有协议和兼容入口保持原样（静态）

- 目的/需求：R01、R22；验证既有协议和兼容入口保持原样。
- 前置与输入：G 中明确不属 #85 修改权限的 11 个文件：AGENTS、W、三角色规则、workflow_gate、handoff_guard、interface_handoff_check、structured_handoff_schema、handoff schema、profile registry。
- 操作步骤：将这些交付文件字节 SHA256 与既定基线值逐一比较。
- 预期与通过判据：11 项全部相等；不通过修改旧协议/角色/兼容入口来容纳新 reducer。仅是字节保持检查，不重跑这些已有工具的全部单元测试。
- 自动化映射：`S::test_current_protocol_and_legacy_entrypoints_are_unchanged`。

### AGENT-FUNC-085-030 — State/Event/Context 定义封闭且完整（静态）

- 目的/需求：R03、R04、R05；验证State/Event/Context 定义封闭且完整。
- 前置与输入：交付的 workflow-transition-v1.schema.json。
- 操作步骤：读取三个定义，比较 properties 与 required 集合，并检查 additionalProperties。
- 预期与通过判据：State 为 K 的 14 个顶层字段，Event 为 schema_version/type/event_id/artifact/checked，Context 为 schema_version/workflow_profile/task/governor/protocol/artifacts/checks；required 与字段全集相同且额外字段禁止。
- 自动化映射：`S::test_public_wire_definitions_are_closed_and_complete`。

### AGENT-FUNC-085-031 — 共享 Task/Governor/ArtifactRef 域一致（静态）

- 目的/需求：R03、R04、R05、R22；验证共享 Task/Governor/ArtifactRef 域一致。
- 前置与输入：当前 handoff schema 和新 transition schema；允许本地定义引用或固定公开 handoff schema 引用。
- 操作步骤：展开公共引用，比较 State.task、State.governor、Event.artifact 的定义。
- 预期与通过判据：Task/Governor 与当前协议完全一致；ArtifactRef 只允许复用原 kind 域或去掉 guard-result 的业务子集，其余域保持不变；不能依赖忽略目录/任意外部引用。
- 自动化映射：`S::test_shared_protocol_domains_retain_their_exact_definition`。

### AGENT-FUNC-085-032 — 封闭 wire 的内存示例与额外字段拒绝（静态）

- 目的/需求：R03、R04、R05；验证封闭 wire 的内存示例与额外字段拒绝。
- 前置与输入：合法空 State、CONSUME Event、调用方加载协议的 Context；准备三个顶层和 State 的 test/worker/task/governor 嵌套额外字段。
- 操作步骤：用供给的 schema definitions 验证合法示例，再逐项验证非法示例。
- 预期与通过判据：合法示例全部通过；每个额外字段变体均被 schema 拒绝。本项是声明结构检查，不替代 reducer 的生命周期运行。
- 自动化映射：`S::test_schema_validates_memory_examples_and_rejects_nested_extras`。

### AGENT-FUNC-085-033 — 本次声明源码头与语法（静态）

- 目的/需求：R22、R23、R24、R25；验证本次声明源码头与语法。
- 前置与输入：公开变更路径清单的三个 production 文件及两个 Worker generality 文件；执行时读取 Candidate 中对应只读文件。
- 操作步骤：检查文件存在、项目标准头所需标识/元数据和 Python compile。
- 预期与通过判据：五文件均存在，头部包含项目/文件/作者/日期/版本/描述与 MIT/SPDX，语法可编译。不能据此宣称 Worker TDD 已执行、generality 充分或复用来源正确；这些仍由各自证据和终态审查判定。
- 自动化映射：`S::test_declared_owned_sources_have_header_and_valid_python_syntax`。

### AGENT-FUNC-085-034 — 公开接口说明包含实际接口与错误名（静态）

- 目的/需求：R02、R20、R21、R22、R25；验证公开接口说明包含实际接口与错误名。
- 前置与输入：本次交付的 Category B 公共 workflow-transitions.md。
- 操作步骤：检查 initial_state、transition、WorkflowTransitionError、State/Event/Context 与 K 的全部 reducer/CLI 错误名称。
- 预期与通过判据：所列名称全部出现；缺项失败。仅证明声明存在，不证明自然语言语义正确、转换表完整或 salvage 解释充分，终态 Reviewer 仍审查这些非执行要求。
- 自动化映射：`S::test_declared_public_reference_exposes_the_actual_interface_names`。

## 4. 覆盖与证据边界

本轮 34 个场景族逐项对应两份选定脚本全部 157 个参数化节点；没有把 #93 已拥有的完整本地字段验证、未修改产品单元测试或未受影响依赖加入新门禁。R01–R22 的运行行为在相应场景中断言；R23 的独立性/双身份和正负区分由本节预验证方法及 027/028 支持。R24 的精确交付身份、文档/代码同树和报告绑定由本轮 manifest、Impact Set、结构化交接检查及文档对齐审计记录；它们是交付证据，不冒充 reducer 功能执行。

R25 中 Worker 的历史复用声明与来源正确性、R22 的说明文档语义质量、所有权/标准和测试充分性由终态 Reviewer 结合相应角色证据审查。033/034 仅覆盖真实读取到的头/语法/名称，不声称检查了被禁止读取的 Worker 作者过程或说明语义。测试不能认证真实 Human 权限、持久 exactly-once、Git 直接合并树、外部工具或 OS 隔离；这些公开限制不因本轮通过而消失。

预验证必须有实际正例和可区分负例，而非仅收集测试或让空 stub 通过：

| 义务 | 用例关联 | 可观察判据 |
| --- | --- | --- |
| RED | 001 | 返回空对象的未实现 stub 在完整初态断言失败，不是导入/收集错误 |
| Known good | 001、007、014；全体 F/S | 合法参考在选定初态、独立 lane、双 ACK 及全体选择上通过 |
| Known bad：伪回执 | 006 | 将 INVALID_EVIDENCE 错误吞掉的参考变体在“必须拒绝”断言失败 |
| Known bad：丢修正授权 | 013、028 | 清空 pending_correction 的参考变体在完整状态比较处失败 |
| Known bad：历史 ID 分类 | 012 | 将已批准的历史 ID 复用错误归为 INVALID_EVIDENCE 的参考在精确 code 断言失败 |
| Full chain | 027、028 | 两个不同身份/两种 lane 顺序的成功与三次耗尽链，逐事件在 Python 和真实 CLI 上完整重放通过 |

实际结果、Test SHA、K revision、文件摘要和环境保存在对应本轮证据中；本文档不把一次运行的 PASS 固化为永久结论。后续公开行为改变必须重跑受影响的冻结选择，不能用本文档或过期参考运行替代。

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.1.0 | 根据 #85 K4/Human 文档要求建立 Agent 类型增量目录；将既有 133 功能与 24 静态节点对应到 34 个可审阅场景族，保留作用域和预期，不回填历史已接受功能。 |
