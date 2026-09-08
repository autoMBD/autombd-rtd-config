# Workflow Transition — 公开需求参考

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-07 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Issue #85 K5 的完整公开需求、权威关联与接口/决策定义；供 Human 独立审阅。 |

## 文档身份与使用边界

本文件忠实呈现 Task Contract `issue85-v2-k5` 的全部 `payload.requirements`，不是新增权威。K revision 为 **5**，其精确 SHA-256 为 `31b2d0228c22535eeb921cf25d78bee838fbf3e3b22cfc10f56e31d104f69eea`。需求原文与 authority_ids 保留原样；接口和决策定义也取自同一 K。本文不含当前 owner 用例、自动化节点、运行结果或私有报告。

这是本轮 #85 公开需求的独立可读副本；不需要访问忽略目录中的运行 K 即可理解义务。批准后的 Test 仍由精确提交、manifest 和 Impact Set 共同绑定，本文本身不表示 Human 已批准。文档仅规定本轮纯内存转换器，不回填历史已接受功能，不扩展 S32DS、E2E 或 KPI。

## 权威关联

下表将需求中的 authority_ids 映射回原来源和保全摘要。对当前对话或设计快照，相关约束已完整呈现在下文需求及公开定义中；摘要用于来源辨认，不以不可访问的快照代替正文。

| authority_id | 来源与决定 | 保全快照 SHA-256 |
| --- | --- | --- |
| A-ISSUE | [Issue #85](https://github.com/autoMBD/autombd-rtd-config/issues/85)：纯内存工作流转换器任务。 | `6ebd69a1c0d68b7595c518096b7274a166f42b9c13b05aaf1036fb0d35515587` |
| A-DESIGN | 已批准的 issue85-transition-design：当前 Wv2 上的纯状态转换设计；完整义务见 R01–R25。 | `6536eabe61153db996ae51ede1c2672da115c3b812eabdbeda24cd63f1bb766a` |
| A-APPROVAL | Human 对上述设计明确答复“按照这个草案执行”。 | `c3e040f711b7b5daa60e72a97f02f77f7f3dbbef65899ca758c2864561cf9dbe` |
| A-RAW-REPAIR | K1 公开澄清：raw 仅用于被明确拒绝的格式修复原件，严格字节摘要与解析正文一致；见 R05/R19。 | `c300485ab83cf31fe12e47bd65af4f61e5b894d3c4687ce56fe2a02903fcde4f` |
| A-RERUN | 当前 #93 LocalRules 的 RERUN_INVALID：rerun_of 指向 INVALID_RUN 报告，报告及旧 Candidate envelope 均为直接前驱；见 R13。 | `0486dd93cf29121739724f544f343fc1b1cd2cf528a7f7bbbc23e26d74684f04` |
| A-ID-CLASSIFICATION | Human 批准：历史 execution_id/dispatch_id 复用在 identity phase 判为 STALE_EVENT；见 R13/R20。 | `f6616e9db261e9f574be70e7876da005a6a7c75e7852bd926fb37da65e0be753` |
| A-TEST-DOCS | Human 要求本轮 Test 文档为短共享索引、独立完整需求参考和精简用例参考；不改变行为范围，见 R23/R24。 | `1131a62a9fbc94ad7e0f160a80be7a60a2aede0e4e569b207aeaa951cbf5ff70` |

协议基线为 Governor `131b22fa0ce1f662fd3289d131138e58404e19f8`，W blob 为 `923df7ce6c314e15754bb4c81d11d14807f627f8`。稳定来源：[Wv2 declaration](https://github.com/autoMBD/autombd-rtd-config/blob/131b22fa0ce1f662fd3289d131138e58404e19f8/agent-discipline/workflow-contract.json)、[handoff-v1 schema](https://github.com/autoMBD/autombd-rtd-config/blob/131b22fa0ce1f662fd3289d131138e58404e19f8/agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json)、[functional-development-v1 registry](https://github.com/autoMBD/autombd-rtd-config/blob/131b22fa0ce1f662fd3289d131138e58404e19f8/agent-discipline/skills/agent-workflow/schemas/functional-development-v1.json)、[LocalRules](https://github.com/autoMBD/autombd-rtd-config/blob/131b22fa0ce1f662fd3289d131138e58404e19f8/agent-discipline/skills/agent-workflow/scripts/structured_handoff_rules.py)。#93 已通过 PR103 合入该 G，为已满足的硬前置。

## 完整需求

### R01

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Implement the approved pure, deterministic functional-development-v1 transition core over #93 structured handoffs. Current Wv2 and its schema/registry remain authoritative and unchanged. The old v1 record/F0/F1/checkpoint handlers are not the specification. No remote authority verification, file guard rewrite, actual dispatch, Git mutation, persistence, GUI, product, S32DS/E2E, KPI or subsequent issue work.

### R02

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Public Python API: initial_state(task, governor) -> state; transition(state, event, *, context) -> new state; WorkflowTransitionError exposes code, pointer, message and as_dict() returning {error:{code,pointer,message}}. Inputs and outputs use JSON values with string keys, finite integers (bool is not int), strings, bool, null, lists and objects; floats are unsupported. No input mutation on success or rejection. Core and initial_state perform no file/process/Git/network/time/random/Agent-platform operations, including indirect helper calls. Imports must not read schemas. CLI is the sole file-loading adapter.

### R03

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Closed state wire (all keys required): schema_version='1.0'; workflow_profile='functional-development-v1'; task and governor reuse #93 definitions; contract=ArtifactRef|null; test={launch,ack,ready,approval}; worker={launch,ack,ready,pending_correction}; candidate={envelope,result}|null; review={launch,report}|null; stop=ArtifactRef|null; final_decision=ArtifactRef|null; terminal=ArtifactRef|null; repairs=[ArtifactRef]; consumed=[{event_id:ID,artifact:ArtifactRef}]. Every slot not otherwise typed is ArtifactRef|null. initial_state initializes nullable slots to null, arrays empty, nested test/worker objects present. State stores exact references, not private reports or duplicated business payloads. Counts are derived from latest READY Implementation implementation_index and latest Candidate candidate_index, not from commit/event counts.

### R04

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Closed event wire, all required: {schema_version:'1.0',type:'CONSUME',event_id:ID,artifact:ArtifactRef,checked:ArtifactRef}. checked.kind is guard-result. artifact.kind is any current registered task artifact except guard-result, which is evidence rather than a business event. No manually translated F0/F1 events, arbitrary action strings, or unknown nested members. State/event schemas must be committed under the agent-workflow schemas directory, reuse the current protocol domains, and be portable without ignored task files.

### R05

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`, `A-RAW-REPAIR`

Closed in-memory context wire, all required: {schema_version:'1.0',workflow_profile:'functional-development-v1',task:Task,governor:Governor,protocol:{handoff_schema:object,registry:object,workflow_contract:object},artifacts:[{ref:ArtifactRef,body:object,raw?:string}],checks:[{ref:ArtifactRef,body:object}]}. Schema/registry/workflow objects are explicitly caller-loaded current v1 artifact schema, functional-development-v1 registry and Wv2 declaration. The protocol bundle is trusted caller configuration, not selected from input locators; reject unsupported versions/profile/required domain structure. Each catalog has unique artifact IDs. All current state slot refs, consumed artifact refs, incoming artifact, its direct predecessors and relevant replacement/repair originals must resolve in artifacts; receipts resolve in checks or as explicitly supplied guard-result evidence in artifacts. References are matched in full. Canonical SHA256 is over sorted compact UTF-8 object bytes with final LF. Check loaded bodies against their refs and schema in memory using the supplied definitions. A rejected format-repair original may be structurally invalid and is inspected only for the preserved identities/values required by #93; do not require that rejected original itself pass artifact schema. Raw authority/manifest/command attachments are already checked by #93; the reducer does not read or revalidate their files. The optional raw member is permitted only on an explicitly rejected format-repair original named by delivery-repair/replaces. Its UTF-8 bytes must hash to ref.sha256 and strict JSON parsing must equal body; original whitespace need not be canonical. If raw is absent, use canonical body bytes. All other artifact/receipt entries forbid raw and retain canonical digest verification. Duplicate-key or unparseable originals cannot supply trustworthy preserved business fields and are INVALID_EVIDENCE, not guessed repairs.

### R06

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Trust boundary: CHECKED must be a real-shaped guard-result with status CHECKED, exit_code 0, evidence_available true, violations empty, exact input artifact_id/path/sha256, matching recipient, visibility and trusted task/governor/task_contract. Verify its own referenced digest and guard-result shape. Never accept boolean checked or self-selected remote authority. This offline core compares supplied evidence; it does not authenticate a Human, prove Git ancestry/direct union/OS isolation/global durable exactly-once, or execute LocalRules I/O. A missing referenced item is MISSING_EVIDENCE; available wrong digest/non-CHECKED/contradictory receipt is INVALID_EVIDENCE. Present wrong task/G/W/K/active identity is STALE_EVENT before evidence errors.

### R07

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Input state invariants: closed shape, correct slot kinds, unique consumed event IDs and artifact IDs, each non-null slot/repair ref appears in consumed, expected task/governor identities, contract chain revision order, readiness tied to its active launch or pending/completed correction, approval tied to exact frozen Test READY, Candidate tied to approved T and an accepted READY I, indices in 0..3 with no skipped accepted correction/Implementation/Candidate progression, review report tied to single review launch, and terminal/final decisions consistent with accepted review/Candidate. State may retain an older-K READY tip while a pre-Gate K revision is pending, but that readiness cannot authorize the new K. After I(n+1) READY before C(n+1), candidate still references I(n), while worker.ready references I(n+1). STOP never destroys those facts. No inference of readiness from ACK, no negative/boolean counters, and no source invalidation hidden in validation. Missing catalog evidence is phase-6 MISSING_EVIDENCE rather than a fabricated state-invariant diagnosis.

### R08

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Initial K revision0 is the first consumed business artifact and sets state.contract. Each INITIAL Test/Worker launch then binds current K and G, each independently and once; either order is legal and Worker never waits for Test READY or approval. A lane's active dispatch/session/worktree/branch are the launch payload identity. NOT_READY and CONTRACT_AMBIGUITY reports record consumption and observations, do not establish READY or spend a correction; if a newer pre-freeze report withdraws READY, clear only that lane readiness (retain its historical source in consumed). Reports must bind active launch/correction. Repeated same artifact is not a new status.

### R09

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Before Test approval, Test READY sets test.ready without requiring Worker. Test REQUEST_CHANGES consumes exact current Test decision and clears current test.ready, allowing the same Test lane to revise and return another READY; it never affects Implementation. TEST APPROVE requires consumed current-K Test READY and exact subject, sets test.approval, freezes Test tip, manifest, Impact Set and K. It does not require Worker READY. After approval, new Test source/status changes or K revisions are ILLEGAL_TRANSITION (format-only repair with preserved frozen values excepted). STOP is globally represented only by gate FINAL, decision STOP; TEST STOP is not a global stop event in this profile.

### R10

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Worker INITIAL READY sets worker.ready at implementation_index0 under current launch/K, with no previous_implementation. Before C0, same-lane refinements may deliver a new index0 READY without resetting the lane; source cannot be replaced by unrelated history (actual ancestry remains guard responsibility). After C0, a new Implementation requires a consumed pending correction, exact correction dispatch/lane, matching previous latest I, and exactly next implementation_index. NOT_READY during an authorized correction preserves prior READY I and pending correction; successful new READY advances worker.ready and clears pending_correction. Completion count advances only at READY, never when correction was merely authorized.

### R11

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

C0 requires consumed approved current Test and current-K READY I0. Candidate payload must match their exact tips/manifests/Impact Set, index0, correction_count0, parents [T,I0], previous_candidate null and rerun_of null. Subsequent new Cn requires latest READY In with index exactly previous Candidate+1, the same frozen T/manifest/Impact Set/K, exact previous Candidate envelope reference, and no pending correction. Candidate consumes an execution identity/dispatch and sets candidate={envelope:currentRef,result:null}. Never assemble twice from the same unchanged I; never exceed C3. Byte/Git union is still a guard/orchestrator/#86 responsibility; reducer compares supplied identities.

### R12

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

A Tester result requires current Candidate execution, Candidate SHA/index and active dispatch. It sets candidate.result exactly once for that execution. PASS prohibits further development and enables terminal Reviewer; IMPLEMENTATION_FAIL enables correction only while candidate index<3; at C3 it enables terminal Reviewer with CORRECTIONS_EXHAUSTED. TEST_GATE_INVALID, CONTRACT_INVALID, INTEGRITY_INVALID enable their corresponding terminal review and never edit frozen Test or self-exempt via a renamed event. INVALID_RUN permits only a rerun of the same Candidate or Human STOP; no correction, READY I change, new C or business verdict is inferred. Observations do not override the explicit report outcome.

### R13

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`, `A-RERUN`, `A-ID-CLASSIFICATION`

Rerun Candidate envelope requires latest consumed outcome INVALID_RUN, rerun_of equal the exact active tester-confidential-report with INVALID_RUN (state.candidate.result), with that report and the prior active Candidate envelope both present as direct predecessors, identical Candidate/T/I/manifests/Impact Set/coverage join/index/correction_count/previous_candidate, and a previously unused execution_id and dispatch_id. It replaces active envelope and clears result; it does not change I/C indices. A stale result from the old execution is STALE_EVENT even if its checks/evidence are absent. Duplicate IDs across accepted execution/dispatch history cannot start another execution. Human-approved classification: a proposed new rerun reusing an execution_id or dispatch_id from accepted execution history is STALE_EVENT in identity phase (3), even when its other current bindings are correct; it is not DUPLICATE_EVENT, ILLEGAL_TRANSITION or INVALID_EVIDENCE for that reuse fact.

### R14

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Correction authorization requires active consumed IMPLEMENTATION_FAIL from Cn with n<3, no already pending correction, correction_index=n+1, same Worker lane/session/worktree/branch, previous_implementation equal latest READY I, and disclosure_review bound to the active confidential report ID/digest. It sets pending_correction only. Another authorization while pending is ILLEGAL_TRANSITION, not a free replacement grant. A new READY from the same correction clears pending and advances I once; subsequent C uses that exact I. Same Worker retains existing code; no clean-room restart. No correction4 or reinterpretation of invalid Test/contract/integrity as Implementation correction.

### R15

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Before Gate1 only, a genuinely authorized K revision increments revision exactly one and references current K plus change authority; it preserves accepted history/source tips but clears ACKs and makes prior READY ineligible for new-K approval/Candidate. New K_REVISION launches reference each lane's old launch and preserve its lane identity. Each lane then returns explicit K_ACK with exact old/new K and digest. Both ACKs must be consumed before either lane's new-K READY is eligible; ACK itself never means READY. During this synchronization no Candidate or approval may consume older-K READY. Revised-K launch may be missing for one lane while the other ACKs; block only the premature operation, not all unrelated progress.

### R16

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Human global STOP (FINAL/STOP) may be consumed at any non-final-closed point after initial K. subject is exact current Candidate SHA when present, otherwise null. It sets stop and prohibits new development/approval/success publication while preserving latest actual READY I, pending correction, Candidate and evidence. Before review it enables one HUMAN_STOP reviewer-launch; after reviewer-launch it preserves that same review ID/reason and permits its existing report plus truthful FAILURE terminal-record. Do not create a second reviewer-launch or fake Tester/Reviewer FAIL. After MERGED or RECORD_FAILURE no new business action is legal; a repeated event still follows the stated duplicate priority.

### R17

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

At most one logical terminal review: reviewer-launch is permitted only after PASS, exhausted C3 Implementation failure, explicit Test/contract/integrity invalid result, or STOP. It binds current Candidate when present, latest READY I and exact reason/source reports. Missing a result is OUT_OF_ORDER_EVENT; an outcome that admits only rerun/correction is ILLEGAL_TRANSITION. Starting another review ID after one launch, or starting any Worker correction after review, is ILLEGAL_TRANSITION. reviewer-report binds that launch review_id/dispatch, accepted once. Format-repair may replace delivery refs but retains logical review and verdict. A favorable review of failure cannot become success.

### R18

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

terminal-record requires the consumed Reviewer report and exact latest I/C/count/review. SUCCESS requires Tester PASS, Reviewer APPROVED, no STOP, and accepted_candidate exact current C including T+I; OPEN_SUCCESS_PR records the proposal (PR may be null before creation) and does not itself mean MERGED. Its consumption leaves only final Human decision, final disposition, authorized format repair or STOP legal. FINAL APPROVE requires that consumed success proposal and exact Candidate subject, stores final_decision; FINAL REQUEST_CHANGES records rejection, cancels success progression and permits truthful RECORD_FAILURE with same Reviewer (does not autonomously reopen corrections). MERGED requires exact consumed FINAL APPROVE and matching #93 PR/merge evidence and closes state. RECORD_FAILURE requires a non-success route, Reviewer rejection, STOP or FINAL REQUEST_CHANGES; accepted_candidate/pr null, preserves source, closes state. A second unchanged success proposal without real changed PR evidence is ILLEGAL_TRANSITION; a proposal may be updated from pr=null to an exact-head PR before final approval, never to another Candidate.

### R19

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Delivery repair is orthogonal bookkeeping: accepted delivery-repair is appended to repairs; no readiness, verdict, tip, count or review identity changes. It must name real rejected original/check and match the active owned context. A later checked replacement must cite original+rejection and any authorized new repair dispatch; preserve #93 replacement business fields plus execution identity and frozen evidence. If original business artifact was never consumed, apply that business event exactly once. If it was consumed, replace active refs only, retaining business state and counts, and append the replacement identity. Do not relaunch a completed logical review or reapply READY/correction. Rejected original bytes may be malformed; schema repair does not authorize guessing a missing business verdict.

### R20

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`, `A-ID-CLASSIFICATION`

Reject in exact public order: (1) event/context wire and incoming artifact closed shape or unsupported profile/schema/event -> MALFORMED_EVENT; (2) state shape/invariants -> INVALID_STATE; (3) present task/G/W/K, active subject/lane/dispatch/execution/review drift -> STALE_EVENT; (4) event_id or exact artifact already consumed -> DUPLICATE_EVENT; reused artifact ID with different ref/digest is STALE_EVENT; (5a) completed terminal, frozen changes, exceeded budget, disallowed outcome route/review repetition -> ILLEGAL_TRANSITION; (5b) otherwise legal action with unconsumed lifecycle prerequisite -> OUT_OF_ORDER_EVENT; (6a) absent catalog artifact/receipt/required evidence -> MISSING_EVIDENCE; (6b) available false/contradictory digest/check/evidence -> INVALID_EVIDENCE; (7) apply a deep copy and validate output, internal invariant failure -> INVALID_OUTPUT. Check only available identity facts before evidence phase; never fetch. Pointer identifies the offending public field; error text is deterministic and contains no traceback or raw confidential payload. Human-approved classification: a proposed new rerun reusing an execution_id or dispatch_id from accepted execution history is STALE_EVENT in identity phase (3), even when its other current bindings are correct; it is not DUPLICATE_EVENT, ILLEGAL_TRANSITION or INVALID_EVIDENCE for that reuse fact.

### R21

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

CLI at workflow_transition.py: subcommands init --task PATH --governor PATH; apply --state PATH --event PATH --context PATH. stdout is exactly one canonical next-state JSON document plus LF on success and empty on failure. stderr empty on success; exactly one error JSON document plus LF on failure. Exit0 success; exit1 structured transition rejection codes from R20 except INVALID_OUTPUT; exit2 INVALID_OUTPUT, INPUT_ERROR (unreadable file, JSON syntax, duplicates, floats/nonfinite or non-object root), USAGE_ERROR (invalid args) or EXECUTION_ERROR (unexpected adapter exception). --help is normal argparse help exit0, explicitly exempt from JSON output. Files are read only; no output-path overwrite, automatic schema discovery, Git calls or background execution. CLI loads the already supplied context JSON; schema/registry values are within it. Invalid JSON parsing precedes reducer errors. API programmer/shape errors are structured, not raw exceptions.

### R22

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Preserve compatibility: do not change workflow_gate.py legacy record/path/validate CLI behavior, handoff_guard.py, #90 compatibility commands, AGENTS/subagent definitions, workflow-contract.json or existing protocol fields to make new histories pass. Reuse pure helper functions only if they stay in memory; do not call load_schema/load_registry/validate_artifact functions that secretly read disk from transition. A focused new Category B reference documents the actual public API, schemas, errors, transition table, context trust and limitations. No Category A changes.

### R23

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`, `A-TEST-DOCS`

Worker owns TDD unit/generality tests over arbitrary synthetic task histories (at least two independent identities, lane orderings and SHAs), requirements and public interfaces, not owner Test. Tester independently authors requirement-driven functional tests and prevalidates full selected Python/CLI lifecycle on a separate reference/stub, with actual RED, known-good, known-bad and full-chain evidence, including successful terminal and three-correction exhaustion. Reference is prevalidation support only, never Candidate production or Worker input. Both execute only new/changed/affected tests; unrelated unit inventory, S32DS/E2E/KPI and historical acceptance are excluded. Classify unused existing tests with reasons in Impact Set. Commit functional tests in Tester lane and generality tests in Worker lane, distinct paths. Human requires prospective functional documentation in tests/doc/ by type, including #85 without historical accepted-code backfill. Tester replaces the current in-progress monolith with a short tests/doc/README.md shared guide/index linking tests/doc/reference/agent/workflow-transition-requirements.md and workflow-transition-cases.md. The feature cases are a concise table of stable case ID, requirement IDs, scenario and observable expected result, with only conditions needed to distinguish each case. Do not include execution steps, setup procedures, commands, automation-node inventory or run results in the case reference; retain those details in scripts and structured report/Impact Set. Preserve existing behavioral scope and assertions, do not invent cases for a catalogue. KPI docs remain docs/tests/ under separate KPI issues.

### R24

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`, `A-TEST-DOCS`

Output reports must satisfy #93 exact artifact schema and current launch/context identities. Include real manifests, requirement coverage, scoped command outcomes/evidence and progress. Commit only owned deliverables, never .agent-state, reference overlays or lessons in either lane. Tester may use tests/functional/test_workflow_transition.py and owned support; Worker may use tests/unit/test_workflow_transition_generality.py and module-owned support. Paths are ownership anchors, not a restriction against justified in-scope helper decomposition. No overwriting another role's source. Return READY only when complete; otherwise report actual NOT_READY/CONTRACT_AMBIGUITY. Keep operating estimates revisable and communicate before expanding scope. The Test lane owns the shared index and two feature references, committed with corresponding automation in the same Test tip/manifest. Human Gate1 primarily reviews the requirements and concise cases; frozen Test still binds all. The requirements reference must faithfully preserve every payload.requirements ID, full obligation and authority association, identify K revision/digest, and supply durable source associations or needed public interface/decision definitions so it is readable without ignored runtime K. Orchestrator checks fidelity; Tester packages the public rendering. It is not new authority. No runtime envelope/private report dump. Current/unaccepted case references and case-bearing index remain confidential from Worker; only standalone public requirements may be provided separately through the reviewed inbox. Update scoped document alignment evidence and report mappings without expanding functional gate. This pre-Gate documentation-only K5 revision changes no implementation behavior; preserve retained I0. Worker only ACKs K5 and rebinds same-source READY with truthful compatible existing evidence, without code edits or unnecessary test reruns.

### R25

Authority IDs: `A-ISSUE`, `A-DESIGN`, `A-APPROVAL`

Reusable historical Implementation is preserved, not acceptance evidence. Worker may adapt only the disclosure-reviewed clean-source attachment; no historical refs/worktree/source browsing. Old lifecycle handlers are obsolete for Wv2. Record which supplied helper mechanisms were reused/adapted or rejected with technical reasons in owned documentation/coverage. Source preservation never licenses copying an invalid algorithm or skipping new TDD.

## 公开接口定义

### IF-PY

- Kind: `python`
- Locator: `agent-discipline/skills/agent-workflow/scripts/workflow_transition.py`
- Requirement IDs: `R02`, `R03`, `R04`, `R05`, `R06`, `R07`, `R08`, `R09`, `R10`, `R11`, `R12`, `R13`, `R14`, `R15`, `R16`, `R17`, `R18`, `R19`, `R20`, `R21`
- Signature: initial_state(task, governor); transition(state, event, *, context); WorkflowTransitionError(code,pointer,message).as_dict(). Exact wire and behavior: R02-R21.

### IF-JSON

- Kind: `json`
- Locator: `agent-discipline/skills/agent-workflow/schemas/workflow-transition-v1.schema.json`
- Requirement IDs: `R03`, `R04`, `R05`, `R06`, `R07`
- Signature: Closed $defs State, Event, Context; R03-R05. Shared ArtifactRef/Task/Governor domains match #93; no ignored runtime dependency.

### IF-CLI

- Kind: `cli`
- Locator: `agent-discipline/skills/agent-workflow/scripts/workflow_transition.py`
- Requirement IDs: `R02`, `R20`, `R21`, `R22`
- Signature: init --task PATH --governor PATH | apply --state PATH --event PATH --context PATH; R21 canonical stdout/stderr and exits0/1/2.

## 公开决策顺序

数值越小越先检查；各项 side_effects 均为空。错误分类与正文 R20 一致。

| ID | Priority | Requirement IDs | When | Error | Result |
| --- | --- | --- | --- | --- | --- |
| D-SHAPE | 10 | R20 | Incoming event/context/available incoming artifact has illegal shape or unsupported version/profile/type. | MALFORMED_EVENT | Reject before state. |
| D-STATE | 20 | R20 | State has illegal shape or contradictory available state facts. | INVALID_STATE | Reject before stale/event duplicate. |
| D-STALE | 30 | R20 | Present public identity/binding drifts, including reused artifact ID with different reference. Includes a proposed new rerun reusing any previously consumed execution_id or dispatch_id; check available historical identity facts at this priority. | STALE_EVENT | Reject before duplicate/route/evidence. |
| D-DUPLICATE | 40 | R20 | Accepted event_id or exact artifact identity repeats. | DUPLICATE_EVENT | Do not advance twice. |
| D-ILLEGAL | 50 | R20 | Frozen/terminal/budget or explicit current outcome route forbids the action. | ILLEGAL_TRANSITION | Reject without reopening work. |
| D-ORDER | 60 | R20 | Action is otherwise legal but its lifecycle predecessor has not been consumed. | OUT_OF_ORDER_EVENT | Await only real missing step. |
| D-MISSING | 70 | R20 | Required memory catalog or receipt entry is absent. | MISSING_EVIDENCE | Request exact evidence, no I/O. |
| D-EVIDENCE | 80 | R20 | Available digest/receipt/evidence contradicts exact binding. | INVALID_EVIDENCE | Fail closed, preserve sources. |
| D-APPLY | 90 | R20 | All prior checks pass. | null | Apply to deep copy and independently validate output; return complete state; INVALID_OUTPUT on internal invariant failure. |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-07 | 0.1.0 | 按 K5 单独呈现全部 25 项完整义务、authority_ids 和公开接口/决策定义；不引入新需求或私有测试内容。 |
