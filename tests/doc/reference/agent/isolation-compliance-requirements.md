# 隔离合规：完整公开需求

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-13 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Issue #120 K0 的完整公开需求与必要接口定义，供功能 Test Gate 审阅。 |

来源：Issue #120，K revision 0；K SHA-256：76046f306841e309d54ba5a7044d2a852727778939c7a97587095f603d8d41a0。此文完整呈现 K.payload.requirements，接口定义用于解释义务，不替代共享的完整 K。当前开发任务继续遵循其固定 W4；W5 是本次实现的显式未来接口。

## 来源关联

- A_CURRENT: Human 在 2026-09-13 对本任务的原始授权（完整原文）：

  > 解决#120：基于最新 origin/master，按照仓库现行 Agent Loop 规则解决 autoMBD/autombd-rtd-config#120。任务依据限于该 Issue 的正文、有效公开评论、公开引用及仓库内容；不读取历史 Codex 对话或旧任务的本地执行资料，不继承历史临时特批。允许复用已验证的环境缓存。先核实依赖并固定 Governor，再按现行流程推进；如有缺失或冲突，指出具体问题，不自行扩展规则。

- A_ISSUE120: [A_ISSUE120](https://github.com/autoMBD/autombd-rtd-config/issues/120)
- A_CHARTER: [A_CHARTER](https://github.com/autoMBD/autombd-rtd-config/blob/b2b8223fbcec45649d25f132d0e9882dfb6e2c24/AGENTS.md)
- A_HANDOFF: [A_HANDOFF](https://github.com/autoMBD/autombd-rtd-config/blob/b2b8223fbcec45649d25f132d0e9882dfb6e2c24/agent-discipline/skills/agent-workflow/references/structured-handoffs.md)
- A_ENV: [A_ENV](https://github.com/autoMBD/autombd-rtd-config/blob/b2b8223fbcec45649d25f132d0e9882dfb6e2c24/agent-discipline/skills/agent-workflow/references/workflow-environment.md)

## R01

Define one authoritative isolation vocabulary: independence means separation of design/implementation/verification responsibilities; isolation means context/workspace/Git data controls. Define isolation_level I0 discipline-only, I1 clean role context + separate workspace + reviewed selective delivery, I2 I1 + independent Git store and only authorized source state. Do not conflate these level labels with Implementation tip indices I0/I1/I2/I3.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R02

Document limits for every level: I0 makes no technical-isolation claim; I1 can share Git/host paths; I2 removes hidden-current-Test refs/objects, shared stores and default recovery/fetch paths but does not deny OS cross-directory reads. Remove I3 isolation as a current profile/default/prerequisite/planned mandatory platform; do not remove the valid third Implementation correction identity.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R03

Separate level selection from explicit role and phase permissions. Defaults: Worker initial/correction I2; Tester author/prevalidate I2; Tester execute/diagnose I2; Reviewer terminal I2; ordinary read-only investigation or Human-supervised documentation usually I1; selected black-box E2E fresh independent CLI and corresponding I2 input separation. Lower levels never grant forbidden access or replace an explicitly higher task requirement.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R04

Worker receives complete public K, its Envelope, own Implementation and generality tests. It must not read current/unaccepted Test, cases/case-bearing indexes, confidential reports or indirect disclosures. Keep same lane/session/worktree/branch and strict incremental Implementation ancestry for corrections.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R05

Tester author/prevalidation starts independently from G/K without reading current Worker Implementation and never writes production. Tester execute/diagnosis may read approved Test and exact Candidate Implementation for frozen-scope execution and honest diagnosis, while Candidate implementation stays read-only. Complete reports go only to Orchestrator.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R06

Reviewer may read all this task's authorized terminal Test/Implementation/handoffs/execution evidence; it performs one terminal non-execution review, never reruns the functional gate or changes Test/Implementation. W4-style sole-parent lessons-only child L remains the only permitted source write at review.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R07

Orchestrator holds global material only within its authorized responsibilities, reviews/selectively transfers/redacts deliveries, records its own related operations, and cannot grant access it does not possess. Reviewer examines isolation-related operations of every task role and phase, including Orchestrator deliveries, not merely final diff or agent self-attestation.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R08

Apply the same permission boundary to direct files, other directories, Git history/refs/objects, Connectors, tool substitution, inherited context and forwarded material. Authorization is not a physical path restriction: explicitly authorized tools, public references and cached dependencies may be outside the workspace. Accepted normal regression tests already in G are not current hidden Test.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R09

Agent must obey predeclared task/role/phase read/write/operation boundaries. Completion, diagnosis, test passing or speed never authorize bypass. Any confirmed boundary violation makes that task execution result unconditionally unacceptable even with all functional tests passing; report truthfully and retain raw evidence without deletion, concealment or laundering through reruns.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R10

Judge violation using beforehand authorized scope and actual evidence, never retroactively invented restrictions. Review unauthorized attempts even if access failed; failed access is not automatic exoneration. Distinguish confirmed violation, unauthorized attempt awaiting review, incomplete evidence, compliant observed operations and legitimate external input; missing records neither prove violation nor compliance.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R11

When a violation is confirmed during execution, Orchestrator stops the affected execution, preserves source/reports/raw traces and prevents it from continuing as a successful delivery. Enter the existing one terminal failure review; if discovered during that terminal review, Reviewer returns REJECTED in that same review. Never start a second Reviewer for this event.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R12

Preserve genuine Tester PASS/FAIL independently from isolation rejection. Confirmed violation is not an ordinary Implementation defect, an INVALID_RUN/F0 free retry, a counter reset or a historical fact removable by correction/retest. Retain Implementation and lessons without automatically packaging them as a new compliant success.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R13

Evidence gaps require completion or Human judgment; do not invent charges or automatically accept. General unknowns retain observation-first, one bounded diagnostic and only affected-operation blocking. Do not turn every unknown into whole-task termination or add a new routine Human Gate.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R14

Bind isolation level plus explicit allowed/forbidden role/phase scope through existing versioned task/launch/handoff and preflight interfaces with exact task/G/W/K identities and safe visibility. A level alone is insufficient. Keep old #79 public interfaces and declared compatibility honest rather than renaming a field to fabricate prior capability evidence.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF, A_ENV

## R15

Orchestrator delivers actual launch/context inputs, structured handoffs and raw/addressable file/Git/command/tool/Connector operation evidence with necessary sequence, actor and target associations, all authorized scope changes/anomalies/attempts/violations, and a completeness statement with explicit evidence gaps. Reuse existing harness traces and evidence references; add only necessary navigation/structured fields, not an OS monitor or new agent platform.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R16

Reviewer report explicitly records isolation conclusion, reviewed role/phase/operation coverage and limits, findings, implicated actor/operation, violated authorization clause and evidence locations. Evidence review covers all supplied isolation operation records, not selective favorable summaries. Final PR/failure issue exposes these key conclusions while preserving hidden Test/confidential-report disclosure boundaries.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R17

Align the existing closed schema/registry/guard/reducer/final evidence checks wherever behavior is affected. New policy must have a machine-enforced fail-closed success path for a confirmed violation with truthful Tester PASS and consistent REJECTED review; it cannot rely on prose while automatic success still accepts known violation. Validate shapes, identities, members, ordering, references and report consistency, leaving operation semantic judgment to Reviewer/Orchestrator.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R18

Use explicit version opt-in/compatibility for new wire members or behavior. Preserve real historical G/W/K, approvals, records, original verdicts, public #79 capability claims and accepted tasks; do not retrospectively rewrite/revalidate them. An upgraded checker does not migrate an old run's authority or reinterpret old evidence as stronger isolation.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R19

Preserve independent parallel Test/Implementation lanes, exact Human Test Gate approval, frozen case semantics/scope, authorized metadata/non-case Test support repair with real lineage, at most three original-Worker incremental corrections and exactly one terminal Reviewer. Preserve exact tested/reviewed C and W4 lessons child L, final Human review and no direct feature/policy push to master.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R20

Selected independent black-box E2E receives only deployed artifact, fixture and approved task inputs through a fresh independent third-party CLI, never development repository or embedded agent context. For such execution do not copy the development repository just to satisfy the I2 label and do not claim OS isolation. This issue does not require running a product E2E or vendor gate.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R21

Keep changes narrowly in Agent discipline and directly affected generic workflow interfaces/checks, with readable prospective requirements/case references under tests/doc. Product docs remain agent-agnostic; no machine-specific paths in docs. Use stdlib-first Python, uniform MIT headers for new source and required Skills. Preserve append-only changelogs and read-only review archive.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R22

Independently author and prevalidate requirement-driven Test selection with applicable real RED, known-good/known-bad and selected full-chain evidence, declaring explicit nonapplicability reasons. Run only new/updated/directly affected checks from the declared selection; exclude unrelated full suites, RTD/S32DS/KPI work and real private-data access probes. Synthetic evidence is not real private access or live OS isolation proof.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R23

Respect dependency/scope decisions: reuse merged #79 and completed #112; #87 and #80 consume this issue later without making unrelated tasks globally blocked; #98 lifecycle/timeout/platform adapters remain separate. No servers/VMs/Docker/AppContainer/OS permission platform, OS syscall audit, new acceptance flow, product/module changes, KPI platform or historical task re-execution.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## R24

For this task use only Issue 120 body/valid public comments/public references and repository source, plus verified reusable environment inputs/cache. Do not read historical Codex conversations or old task local execution materials and do not inherit historical temporary exceptions. Pin G/W before functional dispatch, record actual dependency/capability evidence and report specific missing authority/conflicts without extending rules.

Sources: A_CURRENT, A_ISSUE120, A_HANDOFF

## R25

The completed delivery must state exactly which claims machines check and which depend on semantic Reviewer/Orchestrator examination. A summary digest, Boolean/self-authored trace or passing guard never proves all OS reads were monitored, actual remote Human authority, functional correctness beyond selected checks or unavailable platform isolation.

Sources: A_ISSUE120, A_CHARTER, A_HANDOFF

## 公开接口定义

### IF_W5

Location: agent-discipline/workflow-contract.json

Prospective W5 declaration: keep schema_version integer 2, workflow_profile functional-development-v1, existing artifact_schema/registry/legacy_contract paths and lifecycle values; set contract_version integer 5; add exactly isolation_compliance={"version":"1.0","enabled":true}. Retain W4 reviewer_lessons and W3 non_case_repairs unchanged. W5 deferred_runtime_capabilities removes capability-sandbox, without reclassifying other deferred packages. Explicitly retain W1–W4 validation paths, old accepted/rejected artifact member shapes, original repair/lessons semantics and capability declarations; reject W5 extension members under older pinned W. Update all version-gated layers together. This Issue's live task remains G/W4 and must not acquire W5 fields or newly manufactured receipts. New levels/phase domains are defined once by shared handoff schema; W is an opt-in, not another duplicated registry.

### IF_SCOPES

Location: agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json

W5 extends each K.payload.boundaries item in place, retaining role,ownership,forbidden_sources,forbidden_actions and requiring scope_id:ID, phase:IsolationPhase, isolation_level:IsolationLevel, allowed_sources:Text[], allowed_actions:Text[], capability_limits:nonempty Text[]. scope_id is unique within K. Empty allowed arrays grant no additional authority. Define IsolationLevel exactly I0|I1|I2. Define IsolationPhase exactly orchestration|implementation|implementation-correction|test-authoring|test-execution|terminal-review|investigation|supervised-documentation|blackbox-execution. Boundary-specific role domain adds explorer without changing functional artifact producer roles. Legal role/phase pairs: orchestrator→orchestration/supervised-documentation; worker→implementation/implementation-correction; tester→test-authoring/test-execution/blackbox-execution; reviewer→terminal-review; explorer→investigation. Default grade matrix is normative K-authoring policy under R03, not new #87 task classification; machines bind the explicitly authorized grade in K and never grant missing permissions. Extend worker-launch,test-launch,worker-correction-envelope,candidate-test-envelope,reviewer-launch payload with isolation={scope_id:ID,preflight:IsolationSnapshot}. Match the exact K boundary role and the corresponding artifact phase (implementation,test-authoring,implementation-correction,test-execution,terminal-review respectively). Bind the preflight scope/grade/role/G/W/K/source root/HEAD to the actual dispatch context; no private task-wide trace may enter a Worker-visible delivery. Keep existing lane/source/ancestry/frozen-case checks.

### IF_SNAPSHOTS

Location: agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json

Add EvidenceRef evidence_type values isolation-evidence and operation-log only under W5. Define IsolationSnapshot as a closed {ref:EvidenceRef,raw:string}, reusing the existing ref/raw inline snapshot pattern. In its typed positions raw is exact canonical UTF-8 JSON with final LF, no BOM, duplicate members, nonfinite values or floats; SHA-256(raw.encode('utf-8')) equals ref.sha256. The guard/final verifier also require exact on-disk referenced bytes and recursively check authorized local reference closure. The pure reducer reads only inline raw, parses and validates the typed record and bindings without any I/O; it does not pretend to verify unavailable raw operation files. Keep State/Event/Context wire shape and public reducer APIs unchanged. In preflight positions ref.evidence_type=operation-log and parsed raw is the closed v2 preflight report. In task-wide evidence positions ref.evidence_type=isolation-evidence and parsed raw is IsolationEvidence. Raw operation-log attachments elsewhere remain byte-bound opaque original evidence; they are not fabricated LaneManifestV1 or authority approvals. Internal helper design remains Worker-owned; no new generic workflow executor is required.

### IF_PREFLIGHT

Location: agent-discipline/skills/agent-workflow/scripts/workflow_environment.py

Preserve required_capabilities, inspect_checkout/create_isolated_checkout, evaluate_preflight(request,observations), require_preflight(report,*,expected_request_sha256,current_bindings), and existing CLI entrypoints. Preserve the entire v1 request/report path including isolation=checkout|input and its historical input-isolation/canary meaning. Add closed request v2 with exactly version=2,role,platform,bindings,required_capabilities,isolation_scope. Bindings retain the existing task_run/governor/workflow_blob/contract_sha256/checkout_root/head/candidate_sha256 fields. isolation_scope={scope_id:ID,phase:IsolationPhase,isolation_level:IsolationLevel,input_kind:repository|deployed-inputs}. Closed observations v2 contains version=2,bindings,checkout,capabilities,isolation_evidence. isolation_evidence={clean_context:bool,separate_workspace:bool,selective_delivery:bool,development_repository_absent:bool,approved_source_inventory:EvidenceRef,context_evidence:EvidenceRef,delivery_evidence:EvidenceRef}; its three refs have evidence_type=operation-log and bind actual trusted-adapter records, never self-attestation of OS denial. checkout is the existing inspection object in repository mode; it is null only for deployed-inputs. Report v2 retains all v1 report members and additionally includes exact observations, using version=2 and deterministic hashes; reconstructing evaluate_preflight(report.request,report.observations) must reproduce it. All modes require declared authorized evidence and capability selections. I1 additionally requires clean_context,separate_workspace,selective_delivery true with applicable refs; repository I2 additionally requires checkout.ref_isolated=true, checkout.shared_objects=false, checkout.checkout_kind=clone and approved source-inventory evidence. os_read_isolated=false is compatible with every new grade; I2 never implicitly requests historical input-isolation. deployed-inputs is only for tester/blackbox-execution, requires clean context/separate workspace/selective delivery/development_repository_absent true and approved deployed artifact/fixture/input inventory, never a development Git checkout; its selected baseline omits Git unless explicitly required and includes filesystem-read,filesystem-write,agent-cli,blackbox. Existing required_capabilities API semantics stay unchanged; this is scoped v2 request behavior. In deployed mode bindings.head is the logical authorized deployed source commit, not a claim of Git in the staging directory. require_preflight rechecks report consistency, exact current bindings, local evidence digests and current repository HEAD/topology for repository mode; deployed mode checks canonical staging-root existence and supplied local evidence bytes instead of requiring a Git repository. Evidence approval/content completeness remain trusted-adapter/semantic responsibilities and must be declared. Use existing INVALID_INPUT,STALE_IDENTITY,CAPABILITY_UNAVAILABLE categories and CLI exit conventions; absent/unavailable/inapplicable evidence produces BLOCKED, not a misconduct verdict.

### IF_ISOLATION_EVIDENCE

Location: agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json

Define closed IsolationEvidence={version:"1.0",task:Task,governor:Governor,task_contract:KRef,cutoff:{at:Time,last_record:Text},coverage:IsolationCoverage[],authority_changes:EvidenceRef[],findings:IsolationFinding[],gaps:Text[],limits:nonempty Text[]}. authority_changes refs have evidence_type=authority and retain actual prior permission authority; the bundle itself grants nothing. IsolationCoverage={scope_id:ID,actor_id:ID,dispatch_id:ID|null,execution_id:ID|null,stage_status:not-started|active|finished,launch:ArtifactRef|null,traces:[{evidence:EvidenceRef,from_locator:Text,through_locator:Text}],gaps:Text[]}. Trace refs use operation-log and address raw ordered actor/target operations; scope IDs resolve to the bound K, launch/task/dispatch/execution identities must agree where applicable. Coverage includes every declared scope with honest not-started entries for future activity; actually performed stages require evidence spans or explicit gaps. Do not require a future Reviewer action to have already occurred or introduce circular self-references. A supplied artifact catalog known to contain an executed stage cannot omit it from coverage. IsolationFinding={id:ID,status:confirmed-violation|unauthorized-attempt|unresolved|not-violation,scope_id:ID,actor_id:ID,dispatch_id:ID|null,execution_id:ID|null,clause_pointer:Text,evidence:EvidenceRef,operation_locator:Text,conclusion:Text}. IDs are unique; clause_pointer is a syntactically valid JSON pointer resolving within the relevant bound K boundary. The actual effective prior authority, including any referenced authority_changes that narrow or extend that clause, and the operation location must be available for semantic review. The pointer binds the underlying K clause; it does not pretend raw Human scope-change prose is automatically authenticated or machine interpreted. confirmed-violation requires real cited operations and a predeclared violated clause; unauthorized-attempt/unresolved remain pending review regardless of read success. not-violation records a supported resolution/legitimate input, never automatic exoneration because access failed. Preserve all earlier confirmed finding identities/status/evidence and all raw trace refs in subsequent evidence snapshots. Non-confirmed findings may be resolved with the same ID plus the evidence-backed conclusion while originals remain preserved. A later snapshot may fill earlier gaps with actual supplemental evidence; it cannot hide executed missing coverage or rewrite the old snapshot. Cutoff specifies only completed recorded operations; explicitly retain source, role, sequence/target associations and limits rather than asserting all OS activity was monitored.

### IF_REVIEW

Location: agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json

W5 reviewer-launch.payload requires isolation_evidence:IsolationSnapshot and admits new terminal_reason=BOUNDARY_VIOLATION. This reason requires at least one confirmed-violation in its exact evidence snapshot and may reach the existing one terminal Reviewer before any Candidate or Tester result; retain exact available Candidate/latest completed Implementation or honest nulls and existing real source_reports. Do not manufacture a Tester INTEGRITY_INVALID or Human STOP. Orchestrator stops related real execution and preserves source/reports/raw trajectories; the reducer remains pure bookkeeping. W5 reviewer-report.payload requires isolation_review={assessment:COMPLIANT|VIOLATION|INDETERMINATE,evidence:IsolationSnapshot,reviewed_scope_ids:ID[],finding_ids:ID[],gaps:Text[],limits:nonempty Text[]}. evidence may be the launch snapshot or a monotonic supplement including Reviewer's completed review/lessons operations through an explicit cutoff. reviewed_scope_ids covers supplied scopes, finding_ids covers supplied findings; do not omit unfavorable operations/findings. Any confirmed violation anywhere in the available launch/report evidence closure requires assessment=VIOLATION and verdict=REJECTED. Unresolved attempts/findings or unfilled evidence gaps require INDETERMINATE and cannot authorize APPROVED/automatic success; preserve lack of proof rather than fabricating violation. COMPLIANT means observed/supplied evidence at that cutoff has no confirmed or pending violation and no uncovered executed-stage gap, not OS isolation. A Reviewer-discovered violation uses this same review, no second Reviewer. All existing W4 lessons C→L checks apply under W5.

### IF_TERMINAL

Location: agent-discipline/skills/agent-workflow/schemas/handoff-v1.schema.json

W5 terminal-record.payload requires isolation_closeout={review_evidence:EvidenceRef,supplement:IsolationSnapshot|null,assessment:COMPLIANT|VIOLATION|INDETERMINATE}. review_evidence exactly equals reviewer-report.isolation_review.evidence.ref; supplement, if present, adds actual post-review operation evidence and preserves prior confirmed findings/source/traces. Automatic SUCCESS requires existing real Tester PASS + Reviewer APPROVED + COMPLIANT review and closeout with no confirmed violation or unresolved evidence gap in supplied closure. For BOUNDARY_VIOLATION or a later confirmed violation, only terminal FAILURE/RECORD_FAILURE is allowed, with accepted_candidate=null and pr=null; preserve real Tester verdict, Implementation, lessons and existing correction counts. Reviewer's original APPROVED must remain unchanged if a new violation is discovered only after that report; the Orchestrator closeout blocks success and retains failure without a second Reviewer or forged REJECTED report. INDETERMINATE similarly cannot authorize automatic success; preserve any separate explicit Human disposition instead of inventing one. Once the violation terminal route starts, ordinary rerun/Worker correction/TEST_SUPPORT cannot reopen it. METADATA repairs must preserve original violation findings, evidence, assessment, terminal reason and business/source/count identities. Enforce equivalent rejection in the local guard, pure transition/state replay, and final evidence verification while keeping existing State/Event/Context and verifier result interfaces. No new lifecycle, Agent process controller, routine Human gate or replacement acceptance pipeline. Post-review supplements do not label future publication as already reviewed.

### IF_DOCUMENTATION

Location: agent-discipline/skills/agent-workflow/references/structured-handoffs.md

Align the active charter, four role guides, agent-workflow Skill, local execution state and workflow environment/handoff/transition/evidence references to the single level definitions and phase permissions. Correct unsupported "sandboxed to temp dir" wording without changing #98 runner lifecycle. Provide directly navigable scope/trace/cutoff/gap/isolation-conclusion instructions and final publication responsibility. Preserve append-only history and explain explicit legacy preflight/W1-W4 limits; do not rewrite historical requirements/cases or original capability evidence. New feature Test owns tests/doc/reference/agent/isolation-compliance-requirements.md and isolation-compliance-cases.md plus the shared index; Worker writes no current owner Test. Both docs render public requirements and concise cases respectively under current documentation governance; requirements must fully render all K.payload.requirements. Existing APIs not behaviorally affected remain stable; module/S32DS/KPI code and full-suite execution are excluded.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-13 | 0.1.0 | 首次完整呈现 Issue #120 K0 的 R01–R25 与公开接口。 |
