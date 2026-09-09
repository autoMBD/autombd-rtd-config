# Workflow Evidence Verification Requirements

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-09 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Complete public #86 K1 requirements, interfaces and ordered errors for Human Test Gate review. |

This is a readable rendering, not a replacement task authority. Source: issue #86, K revision 1, SHA-256 `2542ea0ebcec840179edcd949ebaba995dba3eaec17906cbc7d0758e69b33c38`.

## Public sources

- **A01:** https://github.com/autoMBD/autombd-rtd-config/issues/86
- **A02:** https://github.com/autoMBD/autombd-rtd-config/issues/86#issuecomment-5541712995
- **A03:** current-thread authorized autonomous issue86 execution; merged AGENTS and structured-handoffs at G
- **A04:** https://github.com/autoMBD/autombd-rtd-config/blob/e6022241ff9a097aae462abd382ba5b12aef9e54/agent-discipline/skills/agent-workflow/references/structured-handoffs.md
- **A05:** https://github.com/autoMBD/autombd-rtd-config/blob/e6022241ff9a097aae462abd382ba5b12aef9e54/agent-discipline/agent-loop-bootstrap-trust-trace.md

A03 preserves the Human authorization in the current task; the durable operating rules are [AGENTS.md at G](https://github.com/autoMBD/autombd-rtd-config/blob/e6022241ff9a097aae462abd382ba5b12aef9e54/AGENTS.md). K1 clarifies receipt selection, exact G-relative excluded content and the existing pre-PR proposal state under those sources.

## Interfaces

| ID | Kind | Location | Signature |
| --- | --- | --- | --- |
| API01 | python | `agent-discipline/skills/agent-workflow/scripts/workflow_evidence.py` | `verify_evidence(state, *, context, repository_root, authority, github_get=None, command_timeout_seconds=15) -> dict; WorkflowEvidenceError.as_dict()` |
| API02 | cli | `agent-discipline/skills/agent-workflow/scripts/workflow_evidence.py` | `verify --state FILE --context FILE --authority FILE --repository-root ABS [--github-cli EXE] [--command-timeout-seconds SECONDS]` |
| API03 | json | `agent-discipline/skills/agent-workflow/schemas/workflow-evidence-v1.schema.json` | `Closed Authority and Result transport definitions per R02/R14; reuse existing State/Context.` |

## Ordered decisions

| Rule | Priority | Condition | Error | Result |
| --- | --- | --- | --- | --- |
| D01 | 1 | Malformed API/CLI input or illegal authority shape | MALFORMED_INPUT | Reject before proof |
| D02 | 2 | Existing accepted State invariant failure | INVALID_STATE | Preserve existing reducer error code/pointer; no mutation |
| D03 | 3 | Missing required local evidence or source; versus present contradictory evidence | MISSING_EVIDENCE or INVALID_EVIDENCE | Reject the current verification only |
| D04 | 4 | Owned remote Human source cannot be authenticated or contradicts exact current vote | MISSING_EVIDENCE (owned remote 404), AUTHORITY_UNVERIFIABLE, REMOTE_UNAVAILABLE or INVALID_EVIDENCE | Never emit VERIFIED for manual/unavailable/contradictory remote evidence |
| D05 | 5 | Final PR is not exact accepted Candidate/approved merge lineage | MISSING_EVIDENCE (owned remote 404 or unavailable local object), REMOTE_UNAVAILABLE or INVALID_EVIDENCE | Reject finalization proof, preserve source and workflow result |
| D06 | 6 | All owned checks passed | None | Return deterministic bound result; unowned stages NOT_APPLICABLE |

## R01

Extend the existing W3 functional-development workflow with a read-only evidence/finalization verifier. Reuse existing State, Context, artifact schema, registry, LocalRules and transition semantics; do not add a second workflow state/ledger, scheduler, writer or execution route. Preserve existing Python/CLI compatibility. The verifier validates supplied accepted state and complete referenced evidence; it never consumes an event or modifies counters.

Sources: A01, A02, A03, A04, A05.

## R02

Public Python API: workflow_evidence.verify_evidence(state, *, context, repository_root, authority, github_get=None, command_timeout_seconds=15) -> detached closed JSON result. Existing State/Context are the only workflow state inputs. repository_root is an explicit absolute local repository path. authority has exactly schema_version='1.0', authorized_actors (nonempty unique nonblank GitHub logins), base_ref (nonblank branch name), packets (array of {decision_artifact_id,packet_comment_id}, unique decision IDs, positive integer comment IDs). Task.repository is owner/name. Inputs are not mutated. github_get(endpoint) is a trusted injected read-only transport returning exactly {status: integer HTTP code, body: JSON object}; endpoints are repository-relative GitHub REST paths built by the verifier, never arbitrary payload URLs. The provider is an explicit trust boundary; supplied snapshots alone are not authenticated transport.

Sources: A01, A02, A03, A04, A05.

## R03

Reuse existing ordered reducer state invariants, exact full references and canonical digests, then require the complete accepted-history artifact/receipt/attachment closure needed for proof. Missing proof is rejected, never silently deferred into VERIFIED. Existing null-before-owner State slots and READY closure remain unchanged; NOT_READY/K_ACK reports may preserve progress/source as currently allowed and do not establish READY. Expose a minimal read-only state validation entry only if needed, without changing transition/state/event wire or introducing hypothetical next events. For each consumed artifact, require at least one supplied CHECKED receipt matching exact input path/artifact_id/digest, task/G/K, consumer and visibility, with valid canonical receipt digest, exit 0, no violations and evidence_available true. Consider matching receipts in canonical full-reference byte order; use the first fully valid one. No matching receipt is MISSING_EVIDENCE; matching candidates but none valid is INVALID_EVIDENCE. Unrelated receipts do not supply that proof. State.consumed does not retain event.checked: do not claim this selected receipt was the original execution receipt or that a guard actually ran. Original execution authentication and global exactly-once remain outside this verifier; do not add State fields.

Sources: A01, A02, A03, A04, A05.

## R04

Verify all referenced source Tips against real Git commit/tree/ordered-parent objects, full 40-character SHA identities, exact G workflow-contract blob and actual lane manifest bindings. New acceptance proof must be anchored to the current state's exact task/G/W/K and current active refs, including equivalent metadata deliveries and W3 support lineage, never stale or foreign Candidate/report references.

Sources: A01, A02, A03, A04, A05.

## R05

For each executed Candidate in the accepted history, require exactly two actual ordered parents [effective executable Test T, Implementation Ik], with git merge-base --all T Ik equal to the singleton exact G. Both lanes descend from G. Compute actual G..T and G..Ik leaf-tree changes using path, mode, object type and object ID, including deletions and mode/type changes. Ownership sets must be disjoint and agree with the existing coverage join. Candidate tree must equal the direct union of those lane changes over G, with no third-lane content, merge-only edit, omitted change, or mode/blob substitution. Do not execute merge/checkout/commit/read-tree or write Git objects during verification. Inherited contents before G are legitimate, including accepted historical tests.

Sources: A01, A02, A03, A04, A05.

## R06

Reuse exact two current LaneManifestV1 references and CoverageJoin; verify their raw-byte hashes, full identity/requirement coverage and changed-path ownership. Do not invent a path inventory inside the closed manifest or demand that manifests be tracked. Ordinary task deliverables (Test automation, requirement/case documents and Worker unit tests) remain in Candidate; temporary reference overlays, .agent-state receipts and appended Reviewer lesson changes do not. Reject task-introduced ignored-state/reference/evidence material as acceptance content; do not rewrite or reject inherited G history. The mechanical exclusion rule is exact and G-relative: prohibit changed paths equal to or beneath .agent-state/ or tests/.tmp/, equal to agent-discipline/agent-lessons-learned.md, or equal to referenced attachment paths whose evidence_type is command-result, lesson or disclosure-review. Compare normalized existing schema paths; do not reject arbitrary names containing reference, fixture, test or evidence. Ordinary committed workflow references and functional fixtures are legal. Prevalidation overlays must use the already-required tests/.tmp/ location. Unmarked semantic contamination cannot be proved by filenames and remains the Orchestrator's inspection duty.

Sources: A01, A02, A03, A04, A05.

## R07

Project candidate_index separately from functional_correction_count: before C0 candidate_index is null and correction count is 0; after valid corrected READY but before its Candidate, correction count may be one ahead of the current Candidate index. Count derives from accepted same-lane READY Implementation, not event totals, elapsed time, observation counts, invalid runs, delivery repairs or KPI. C0 uses 0; at most C1..C3. Verify real strict ancestry I(k-1)->Ik and identical lane/session/worktree/branch across counted corrections using existing authorization/result references. No clean-room reset or KPI counter.

Sources: A01, A02, A03, A04, A05.

## R08

Duplicate transition/event replay retains existing DUPLICATE_EVENT rejection and cannot mutate source/state/count twice. Repeated verification of unchanged inputs/evidence returns identical canonical result without writes. Existing exhausted/terminal behavior remains stable; unrelated evidence/metadata/support repairs cannot reset counters or reopen a terminal route. W3 support-only source snapshots and invalid-run reruns preserve original case approval and truthful effective/executed Test identities.

Sources: A01, A02, A03, A04, A05.

## R09

Complete the structural correction-diagnosis bridge in this verifier: for every accepted worker-correction-envelope, its trusted confidential IMPLEMENTATION_FAIL source digest and Candidate/Implementation bindings must resolve. All source findings whose responsibility is IMPLEMENTATION must appear in disclosure.mapping; every public diagnosis maps to an existing IMPLEMENTATION finding with matching requirement and production location. Do not send private report/case/node/assertion/fixture values to Worker or public errors. Natural-language root-cause sufficiency and disclosure safety remain Orchestrator semantic review, not something a field checker claims to prove. This does not redesign the existing protocol or reclassify other responsibilities.

Sources: A01, A02, A03, A04, A05.

## R10

For each consumed GitHub human decision that contributes to the accepted history (follow metadata replacements to original source rather than creating a second vote), re-read its exact issue comment and nominated packet via github_get. Require canonical github.com URL for this repository/issue and exact comment ID, matching returned id/html_url/issue_url, User author login in authority.authorized_actors and equal payload.authority_actor, current body/time/deletion fields equal captured raw authority facts, unedited created_at==updated_at, not deleted/reply/PR-comment, and decision created strictly after the packet. The packet must belong to this same issue and match the nominated ID. GitHub responses may have extra official fields; validate required identity fields explicitly. Top-level presence is established by /repos/{owner}/{repo}/issues/comments/{id} and exact issue_url; absent in_reply_to_id is valid, present non-null is not. Never infer Human approval from labels, reactions, agent text or source URLs alone. The source.raw authority attachment is the captured original GitHub REST issue-comment JSON object (not a narration); compare its required id/html_url/issue_url/user.login/user.type/body/created_at/updated_at fields to the new response. A remote 404 proves current absence, not authorization. Authorization policy is supplied by the trusted caller, not inferred from a vote.

Sources: A01, A02, A03, A04, A05.

## R11

Supported GitHub decision commands are exact entire '/approve-test <full T>' and '/approve-candidate <full C>' for APPROVE. REQUEST_CHANGES starts exactly '/request-test-changes <T> ' or '/request-candidate-changes <C> ' followed by a nonempty reason matching payload.reason; no abbreviated/stale SHA, prefix-only approval or whitespace-normalized approval. For STOP and source.kind=human-command the v1 verifier returns AUTHORITY_UNVERIFIABLE rather than inventing remote authentication; the existing manual authority route remains available to the Orchestrator but is not an automatic VERIFIED claim. This adapter limitation does not invalidate preserved source or change workflow verdicts.

Sources: A01, A02, A03, A04, A05.

## R12

An existing SUCCESS OPEN_SUCCESS_PR proposal with pr=null owns only local terminal proof: validate its local bindings, do not request a remote PR and set checks.finalization=NOT_APPLICABLE. Once pr is present, the following remote finalization rules apply. For SUCCESS OPEN_SUCCESS_PR or MERGED terminal records, re-read exact PR /repos/{owner}/{repo}/pulls/{number}; require URL/repository/number bindings, base.ref==authority.base_ref, head.sha==the exact accepted Candidate (not Implementation-only, equivalent rebuild or Reviewer lesson child). Premerge requires state open, merged false and base.sha==G. It verifies proposal availability, not Human final approval. MERGED requires merged true, state closed, exact non-null merge_commit_sha matching the terminal record, accepted final decision on that exact Candidate, and locally available merge commit. Allow either merge_sha==Candidate (fast-forward) or an exact two-parent merge [G,Candidate] with Candidate-identical tree; reject squash/rebase or additional edits. After merge use actual merge ancestry for historical base G, not the mutable current PR base.sha. No PR creation, approval, merge or branch mutation occurs.

Sources: A01, A02, A03, A04, A05.

## R13

A successful finalization proof requires the same current Candidate's Tester PASS, terminal Reviewer APPROVED, exact terminal record and (when MERGED) exact final Human approval. A terminal failure remains failure: accepted_candidate/pr are null, latest Implementation remains preserved, one terminal Reviewer retained. Reviewer lessons are separate evidence, not a product head. The verifier validates record truthfulness, does not transform failures into successes or create follow-up issues.

Sources: A01, A02, A03, A04, A05.

## R14

Return exactly schema_version='1.0', status='VERIFIED', task, governor, task_contract (current KRef or null), input_sha256 {state,context,authority}, approved_test_sha, effective_test_sha, executed_test_sha, implementation_sha, candidate_sha, candidate_index, functional_correction_count, accepted_candidate_sha, terminal_disposition, checks {state,git,human_authority,finalization}, remote_evidence. Nullable sources remain null until owned. checks values are PASS or NOT_APPLICABLE; NOT_APPLICABLE only when that stage is not owned (not missing/unavailable evidence). remote_evidence is a deterministically endpoint-sorted array of {endpoint,sha256}, hashing canonical returned body; it contains no raw Human/case content. All input/body digests use existing sorted compact UTF-8 JSON plus LF. Add a closed versioned JSON schema for authority/result only, not duplicated State/Context. executed_test_sha is the current Candidate's actual first-parent Test; it may lag a registered, not-yet-executed support source. A valid pre-PR OPEN_SUCCESS_PR proposal with pr=null has finalization NOT_APPLICABLE under R12 while its local terminal bindings are still checked. This does not mean merged or remotely approved.

Sources: A01, A02, A03, A04, A05.

## R15

Reject malformed inputs, unresolved or contradictory evidence, unavailable source objects, wrong base/parent/tree/ownership, and failed remote bindings with stable safe {error:{code,pointer,message}} JSON and no traceback or private source text. New API raises WorkflowEvidenceError with code/pointer/message and as_dict(); existing reducer rejection codes may be propagated unchanged. New error codes: MALFORMED_INPUT, MISSING_EVIDENCE, INVALID_EVIDENCE, AUTHORITY_UNVERIFIABLE, REMOTE_UNAVAILABLE, COMMAND_TIMEOUT, EXECUTION_ERROR. Ordered evaluation is input shape/canonical legality, existing state invariants, complete local evidence/receipts, Git facts, Human evidence, final PR evidence, result validation; preserve existing state error semantics within that stage. Stable iteration order, not a new global taxonomy of all hypothetical combined failures. Explicitly present wrong evidence is INVALID_EVIDENCE; missing required local evidence/object is MISSING_EVIDENCE; unavailable transport is REMOTE_UNAVAILABLE.

Sources: A01, A02, A03, A04, A05.

## R16

CLI: python agent-discipline/skills/agent-workflow/scripts/workflow_evidence.py verify --state <json> --context <json> --authority <json> --repository-root <absolute> [--github-cli <executable default gh>] [--command-timeout-seconds <positive finite seconds default 15>]. It reads explicit inputs only and emits canonical result plus LF on stdout/exit0, empty stderr. Semantic/binding rejection is exit1 with error on stderr/empty stdout; input/file/usage/internal/remote unavailability is exit2; command timeout exit124/COMMAND_TIMEOUT. Help exit0. CLI GitHub transport uses only authenticated gh api GET --hostname github.com with built endpoint argv, no shell interpolation, token extraction, user login, retries or background work. It never calls remote APIs when no owned stage requires them. 404 for an owned comment/PR is missing evidence rejection; 401/403/rate-limit/network/provider errors are REMOTE_UNAVAILABLE. Each deterministic Git/gh operation obeys configurable deadline; it is not an Agent lifetime.

Sources: A01, A02, A03, A04, A05.

## R17

Worker owns stdlib-first implementation, narrow necessary integration changes, matching workflow Skill guidance/reference and Worker TDD/generality tests. File choices within those responsibilities are Worker design decisions except the public workflow_evidence.py entrypoint and schema locator; no forced production implementation plan. Independently exercise arbitrary valid histories and real temporary Git graphs, not owner literals. Preserve uniform source headers and documentation boundaries. No new package dependency, W/profile rewrite, agent/initializer/deployer change, product/docs changes, #59/#79/#87/#80 implementation or unrelated tests.

Sources: A01, A02, A03, A04, A05.

## R18

Tester independently authors requirement-driven functional cases and full-chain reference prevalidation without current Implementation. Exercise real synthetic Git objects and injected remote responses for deterministic no-network tests; stubs belong only to prevalidation/transport fixtures, never accepted production behavior. Freeze a scoped Impact Set selecting new verifier checks and only directly affected current transition/guard/repair regression checks; do not run the entire unit inventory. Maintain tests/doc/README.md plus separate workflow-evidence-requirements.md and concise case-table file in tests/doc/reference/agent/. Complete public requirements/interfaces/error rules must be readable for Human review; command details/mappings/raw evidence remain outside case prose.

Sources: A01, A02, A03, A04, A05.

## R19

The functional lifecycle follows current W3: same G/K independent parallel Test and Implementation, Test READY opens Gate 1 without waiting for Worker, first assembly needs approval+I0. Only valid Implementation failures drive up to three same-lane incremental corrections. Non-case repairs follow existing versioned metadata/support protocol. One terminal Reviewer; exact accepted Candidate PR with both lanes and final Human review. No extra Human gates, no autonomous merge, no full-suite/S32DS/E2E/KPI for this issue. Unknown problems get one bounded diagnosis, faithful record and only affected-operation hold; genuine classification ambiguity goes to Human.

Sources: A01, A02, A03, A04, A05.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-09 | 0.1.0 | Rendered complete #86 K1 requirements and public interface/error definitions. |

