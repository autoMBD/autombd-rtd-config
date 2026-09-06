# Structured Agent Handoffs

| Field | Value |
| --- | --- |
| Version | 0.1.1 |
| Date | 2026-09-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Functional-development role interfaces, local delivery validation, confidentiality, and explicit legacy migration boundaries. |

## Authority and responsibility

The handoff protocol expresses the inputs and outputs of the Loop; it is not a
second Loop. The active `agent-discipline/workflow-contract.json` identifies the
profile and its lifecycle rules. The [artifact schema](../schemas/handoff-v1.schema.json)
defines closed members and types. The [profile registry](../schemas/functional-development-v1.json)
defines role, visibility and local predecessor requirements. Do not maintain
another domain inventory in prompts or infer a new field from an example.

G is the exact starting Git commit, not a Governor document. W is the workflow
contract blob at its fixed path in G, not an independently chosen rulebook.
K is the Orchestrator's public task contract, compiled from the Issue, approved
specification and Human decisions. K contains requirements, interfaces, ordered
decision rules, expected errors and side effects, scope and acceptance criteria.
It must not include the current hidden Test or Implementation source.

The Orchestrator owns semantic completeness and the confidentiality review of
diagnostic text. The guard checks shape, bindings and local order; it does not
prove a natural-language requirement true, authenticate a Human, or discover
all affected code automatically. Human Gate 1 reviews the Test Gate; it does not
require Human review of the Worker's Implementation or every protocol field.
For new issues including #85, its primary review surface is the type-classified
functional case document under `tests/doc/`, not a source diff from which Human
must infer cases. Follow the [documentation rules](../../../documentation-governance.md#functional-case-documents-and-human-review).
Tester derives the document from K and implements it; Orchestrator verifies
case-to-script correspondence. The exact Test commit binds both document and
scripts, so the existing Test tip/manifest/Impact Set freeze still applies.
Use existing report coverage/locations and exact-commit links; this rule adds
no artifact kind, schema member, extra approval stage or executable validator.

## Storage, transport and dispatch

Keep task artifacts in ignored `.agent-state/agent-loop/<run>/` storage. The
Orchestrator maintains the canonical authority and confidential artifacts;
copy only the authorized files into each lane's inbox. Worktrees do not share
ignored state automatically. A lane receives a local exact-byte K snapshot and
its own Envelope, not a path into another lane or the Orchestrator's private
directory. Report destinations are explicit lane-local outbox paths.

Every handoff binds the task run, G/W/K revision and digest, artifact identity,
producer, consumer, visibility, and exact predecessor references. Dispatch and
response bind the same `dispatch_id`; that identity joins the separate
[monitoring records](agent-monitoring.md). A replacement report gets a new
artifact identity but remains in its active dispatch. An explicitly authorized
repair after that dispatch completed uses a new dispatch and references the
original delivery separately. Resumed work retains the original Agent, lane,
Implementation and applicable review/accounting identities.

Task semantics travel through K and kind-specific fields. Prompts identify
these files and remind the role of its rules and relevant non-task operating
context; chat responses announce progress or the result location. Neither is
an alternate task-contract channel. There is no generic `notes` or
`description_session` escape hatch. Named natural-language fields still allow
engineering explanations, hypotheses, root causes and scope reasoning.

An example locator prompt is:

```text
Read AGENTS.md and the role rules.
Input: .agent-state/agent-loop/example/inbox/worker-launch.json.
Expected input SHA-256: <exact digest supplied by the Orchestrator>.
Trusted context: .agent-state/agent-loop/example/inbox/worker-context.json.
Before consuming the task, run consumer-local validation with those inputs
and a fresh result path under .agent-state/agent-loop/example/outbox/.
Continue only when the same input bytes receive CHECKED.
Follow the public task contract referenced by that Envelope.
Do not access the forbidden sources it declares.
Write your structured result at its output_path.
Report progress and questions without replacing the structured delivery.
```

This example is not authorization to start a role. An explicit manual-bootstrap
instruction remains controlling even when a file or monitor says READY or
CONTINUE.

## Functional-development handoff map

| Boundary | Artifact | Required meaning |
| --- | --- | --- |
| Authority compilation | task-contract | One public K for both lanes; evidence-backed requirements and precedence, no hidden cases |
| Orchestrator to Tester | test-launch | Author the independent functional Test Gate and perform full-chain prevalidation |
| Orchestrator to Worker | worker-launch | Implement from public K, with Worker-owned TDD and generality tests |
| Tester to Orchestrator | test-gate-report | Deliver Test, coverage, frozen impact selection and prevalidation, or honestly report not-ready/ambiguity |
| Worker to Orchestrator | implementation-report | Deliver the current incremental Implementation, ownership and TDD evidence |
| Human to Orchestrator | human-decision | Record the exact Test/final decision and its original evidence |
| Orchestrator to Tester | candidate-test-envelope | Bind the precise Candidate, approved Test, Implementation, two manifests and fixed test selection |
| Tester to Orchestrator | tester-confidential-report | Return actual execution status and evidence-backed diagnosis; never send directly to Worker |
| Orchestrator to original Worker | worker-correction-envelope | Deliver public, actionable implementation diagnosis without case disclosure |
| Orchestrator to Reviewer | reviewer-launch | Start the single terminal review, on success or failure |
| Reviewer to Orchestrator | reviewer-report | Return review findings, lessons and reusable work; never reopen corrections |
| Orchestrator to Human | terminal-record | Identify the accepted Candidate PR or truthful failure disposition |
| Guard to authorized recipient | guard-result | Record this exact delivery check, not a functional verdict |
| Orchestrator to original producer | delivery-repair | Repair rejected report structure/references without changing source, verdict or accounting |

Tester is one role with two phases, not a new Test-author role. Gate authoring
and prevalidation happen independently of Worker implementation. After Gate 1,
Tester can read Test and Candidate Implementation to diagnose results but cannot
modify either. Worker never reads the current or unaccepted hidden Test; normal
accepted regression code already in G is not a hidden source.
The same visibility boundary applies to case documents: current/unaccepted
catalogues are never Worker inputs. KPI documents stay under `docs/tests/`,
maintained by separate KPI test issues; historical accepted features are not
retroactively required to receive functional case documents.

## Parallel readiness, freeze and correction

Start Test and Implementation independently from the same G/K. Test READY can
be submitted to Human immediately; it does not wait for Worker READY. Worker
can finish before or after Test approval. Only first assembly requires both
the approved Test and completed Implementation.

Candidate C0 contains the approved Test and I0, with ordered parents Test first
and Implementation second. It costs no correction opportunity. A valid
Implementation failure can authorize correction 1, 2 or 3, producing I1, I2 or
I3 and C1, C2 or C3. Each I continues the same Worker lane and is a strict
descendant of the prior I; commits within a lane are not correction counts.
Do not rebuild the same implementation as a fresh sibling from G.

Within the approved series, K, Test, its manifest and the Test Impact Set stay
frozen. An invalid execution can be repeated against the same Candidate using
a new execution identity, without a new Candidate or correction. It is not
permission to self-exempt an ambiguous implementation failure: escalate unclear
responsibility to Human with evidence.

Before Gate 1, a genuine K change produces a complete new revision, its change
authority, updated Test and Worker Envelopes, and explicit acknowledgements from
both lanes. Acknowledgement is not READY. Preserve unaffected source and list
invalidated receipts. After Gate 1, do not mutate K/Test behind the existing
approval; report the invalid series and obtain the required Human disposition.

## Scoped evidence and the diagnostic bridge

The schema distinguishes attachment structures rather than treating every
digest-bound file as equivalent. Lane manifests retain their established
five-field contract. Impact sets declare selected and excluded checks, public
dependencies, requirement/path coverage and prevalidation obligations. Coverage
joins bind the actual Test/Implementation change inventory to that fixed
selection. Command results bind the operation and environment to the recorded
outcome. Authority snapshots and lessons remain raw-byte-bound documents whose
meaning requires the responsible role's review.

Worker unit/generality tests and Tester functional tests are separate layers.
Run only new, changed and actually affected tests from the declared selection.
Full-chain prevalidation means exercising the selected lifecycle end to end;
it does not mean executing every existing unit test. Reference/known-good/bad
cases establish that the selected gate can execute and discriminate, not that
the public contract is semantically complete.

For a failure, Tester records the private case context plus the public
requirement, expected and observed behavior, first divergence, production
location, control flow, root cause, confidence, alternatives and exclusion
evidence. Orchestrator checks those claims against K and source, then prepares
a Correction Envelope containing only the actionable public diagnosis. It
preserves opaque provenance identifiers and records the disclosure review.
No test node, assertion, fixture, mutant, case literal or raw private-report
locator may be sent to Worker. Worker adds a general regression and fixes its
existing implementation rather than reproducing a hidden case.

## Central and consumer-local validation

Use the existing guard as the single entry point:

```console
python agent-discipline/skills/agent-workflow/scripts/handoff_guard.py validate-artifact --artifact <lane-local-file> --expected-sha256 <digest> --context <trusted-context.json> --view <orchestrator-full|consumer-local> --result <safe-result.json>
```

The caller supplies expected task, baseline, contract, recipient and predecessor
context. The input cannot choose its own trusted baseline. Canonical JSON is
UTF-8 without BOM, duplicate members or non-finite numbers, sorted compact keys
and a final LF; SHA-256 covers raw bytes. Unknown nested members are rejected.
Paths must be safe relative paths and actual file resolution must remain within
the authorized worktree. Never overwrite an input/source or an aliased path to
manufacture a result receipt.
Command `cwd` alone may use the literal `.` for the worktree root; this does not
permit dot/traversal components in artifact or evidence file paths.

Central validation may read authorized private predecessors. Consumer-local
validation reads only that recipient's permitted artifacts and an independently
pinned, safe central CHECKED receipt. In particular, Worker must not open the
private Tester report merely to validate its Correction Envelope. A central
result containing confidential paths cannot be copied wholesale to Worker.
For report-format repair, an explicitly pinned public-task rejection receipt may
retain its original `consumer_role=orchestrator`: it describes the rejected
Worker-to-Orchestrator report, so its bytes must not be relabeled. Worker can read
that safe receipt only as an authorized predecessor. This does not relax the
separate central CHECKED receipt's exact Worker recipient binding.

CHECKED authorizes consumption of the checked bytes only. It does not prove
real remote approval, global uniqueness, semantic nondisclosure, or OS-level
capability isolation. Those boundaries remain explicit.

## Rejection and interruption routing

| Condition | Owning action | Resume condition |
| --- | --- | --- |
| Missing/illegal member or wrong reference | Original producer receives delivery-repair | Corrected delivery passes; source, verdict and counters unchanged |
| Wrong cwd/HEAD/G/W/K or stale local copy | Orchestrator checks and restores only the correct owned context | Actual identities agree; do not overwrite user changes or rebase to hide drift |
| Missing predecessor or skipped check | Orchestrator supplies the real missing step | Verified local order; do not invent a success receipt |
| Private data in Worker-visible delivery | Orchestrator rejects before sending and repeats disclosure review | Public actionable delivery; an actual prior leak must still be recorded |
| Real business/contract ambiguity | Orchestrator consults authority, or asks Human | Explicit semantic decision and applicable K/series handling |
| I/O/guard exception or command timeout | One bounded diagnosis; preserve evidence and inspect side effects | Safe retry or scoped Human intervention; no blind command replay |

Unknown problems enter the observation record first and block only the affected
operation. Do not promote a local diagnostic into a universal constraint.
Agent observation windows use #95 dynamic supervision and are not deadlines.
The guard's command timeout bounds a deterministic child operation, never an
entire Agent session. A rejected or unwritable result does not become PASS.
Structured-handoff Git probes default to 15 seconds per command. Agents may set
`RTD_HANDOFF_GIT_TIMEOUT_SECONDS` to a positive finite number of seconds for the
particular invocation; invalid/non-finite values fail before probing. For example,
PowerShell `$env:RTD_HANDOFF_GIT_TIMEOUT_SECONDS = '30'` overrides the default for
that shell's command environment. Retain the chosen setting with execution
context; it is not a new K revision or permission to restart an Agent.

## Terminal review, PR and legacy boundaries

Any successful Candidate or terminal failure enters one Reviewer review. A
Reviewer accepting the analysis of a failed task does not turn it into success.
Report-format repair preserves the same review identity and does not reopen
review or correction. Preserve the final Implementation on failure.

A successful PR uses the exact accepted Candidate head, including Test and
Implementation. Reviewer lessons and execution records stay outside that head;
there is no lesson child commit substituted for the accepted Candidate. Final
approval and merge evidence must bind that same delivery. PR-only repository
protection is not bypassed by this local protocol.

Legacy W v1 is preserved at `agent-discipline/contracts/workflow-v1.json` for
explicit validation of old records. Active W v2 declares the new lifecycle and
references this protocol. Do not feed new artifacts to a legacy validator or
silently fall back to old route/counting rules. Existing #88 wire fields and
timeout aliases remain compatible. Its intentional behavior correction requires
run to follow a successful CHECKED receipt matching the latest event; prepare
alone is insufficient. The #90 compatibility command uses the same internal
legacy packet validator exposed by the unified guard.

This package does not implement the global transition engine (#85), complete
remote-evidence/direct-union finalization (#86), capability isolation (#79),
route executor (#87), or Human/GitHub intake (#80). Their contracts consume
these checked inputs/outputs; a local checker is not their implementation.
Explorer and other workflow profiles are future schema/registry extensions.
KPI is an independent Human-started, issue-driven, post-merge profile for RTD
CfgFile CLI, not a functional correction/optimization branch. Its dedicated
case review, results and dashboard are separate #100–#102 work.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.1.0 | Documented structured functional handoffs, scoped evidence, safe diagnostics, local guard boundaries and explicit legacy migration. |
| 2026-09-06 | 0.1.1 | Bound document-first Human Test review to existing exact Test artifacts, type-classified prospective catalogues and the unchanged confidentiality/KPI boundaries. |
