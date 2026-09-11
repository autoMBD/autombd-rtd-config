# Structured Agent Handoffs

| Field | Value |
| --- | --- |
| Version | 0.1.11 |
| Date | 2026-09-11 |
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
For new issues including #85, its primary review surfaces are two feature
references under `tests/doc/`: the complete readable `K.payload.requirements`
and a concise case table. Shared explanation/index links both without copying
their bodies. Follow the [documentation rules](../../../documentation-governance.md#functional-case-documents-and-human-review).
Orchestrator checks requirement fidelity; Tester derives and implements cases.
Execution steps, automation mapping and prevalidation evidence stay in scripts/
reports, not the case reference. Exact Test binds both feature documents, index
changes and scripts. The reviewed cases and expected results are frozen;
non-case delivery and execution support follow the repair boundary below.
Use existing report coverage/locations and exact-commit links; this rule adds
no artifact kind, schema member, extra approval stage or executable validator.

## Storage, transport and dispatch

Use [Local Execution State](../../../local-execution-state.md) for the single
directory, ownership, transfer and retention rule. This section defines the
handoff's semantic bindings, not a competing local layout. Git does not sync
ignored state: Orchestrator delivers selective exact-byte lane-local inputs and
checks returned reports/evidence before collecting central copies. Never mirror
the central private directory or silently rewrite bound paths during transfer.

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

### Human review boundaries and bootstrap

The normal complete functional-development workflow has exactly two routine
Human review boundaries:

1. **Test Gate approval:** review the feature requirements and case table as
   the Test Gate as soon as Test is READY, without waiting for Worker READY.
2. **Final review:** review the exact delivery PR and terminal findings on the
   functional-PASS path, or the terminal failure report and retained work on
   the failure path. Under W4, the PR head is lessons-only child L of reviewed C.
   Failure review does not create a success PR.

These are Human reviews, distinct from the single Agent Reviewer. K compilation,
lane launch/readiness, prevalidation, handoff validation, disclosure review,
metadata/support repair and in-budget Worker corrections are Agent-owned work,
not additional routine Human gates. A scoped development authorization lets
Orchestrator coordinate those steps; it does not grant merge or unrelated
authority. Real new requirements or frozen-case changes require the relevant
Human decision; case changes amend the Test Gate approval, not a third standard
gate. Resolve ambiguity from existing public authority before asking Human for
a genuinely missing semantic or operational decision.

Manual bootstrap may deliberately require Human involvement at each step.
Keep that run's explicit authority separate; do not turn its observation points
or one-off exceptions into permanent gates. The authorized post-terminal #85 C2
repair is retained history, not the normal route for later Reviewer findings.
Missing runtime support is recorded honestly; written policy is not a deployed
executor or a CHECKED receipt. Discipline improvements remain a separate
reviewed change, not merge-only edits to the functional Candidate.

### Artifact boundaries

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
| Reviewer to Orchestrator | reviewer-report | Return review findings, lessons and reusable work; W4 separately binds lessons commit L; never reopen corrections |
| Orchestrator to Human | terminal-record | Identify accepted Candidate C and exact delivery PR (L under W4), or truthful failure disposition |
| Guard to authorized recipient | guard-result | Record this exact delivery check, not a functional verdict |
| Orchestrator to original producer | delivery-repair | Repair non-case delivery metadata, or register audited Tester support-source repair under explicit W3/W4; preserve case approval, verdicts and Worker accounting |

Tester is one role with two phases, not a new Test-author role. Gate authoring
and prevalidation happen independently of Worker implementation. After Gate 1,
Tester can read Test and Candidate Implementation to diagnose results. Executed
snapshots remain read-only; Tester may repair its non-case support in its own
lane under the shared boundary below, never production or unapproved case
semantics. Worker never reads the current or unaccepted hidden Test; normal
accepted regression code already in G is not a hidden source.
Current/unaccepted case references and case-bearing indexes are never Worker
inputs. The standalone requirements rendering is public, supplied separately
through the reviewed handoff without Test worktree/case access. Its durable
repository copy supports Human review; it neither replaces complete K nor
requires committing runtime `.agent-state/` artifacts. KPI documents stay under `docs/tests/`,
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

Within the approved series, K and the reviewed cases, scenarios, assertions,
expected results and selected acceptance scope remain controlling. Changing a
frozen case requires prior Human approval. The approved Test tip is preserved as
the original source anchor; non-case support repairs bind their actual new
source identities and unchanged case approval as specified below. Never pretend
changed source still has the old T SHA or reuse stale execution evidence.
An invalid execution with unchanged source can repeat against the same Candidate
using a new execution identity, without a Worker correction. Source-changing
support repair requires a newly bound executable snapshot, not that same-source
retry. Neither path exempts a valid Implementation failure from correction
accounting; refer genuine unresolved responsibility to Human with evidence.

Before Gate 1, a genuine K change produces a complete new revision, its change
authority, updated Test and Worker Envelopes, and explicit acknowledgements from
both lanes. Acknowledgement is not READY. Preserve unaffected source and list
invalidated receipts. After Gate 1, do not mutate K or frozen cases behind the
existing approval: obtain the required Human decision before a semantic change.
An unchanged-case support repair follows the local path below; it is not by
itself an invalid-series or terminal condition.

### Frozen cases and non-case repairs

Human freezes the reviewed cases: scenarios, discriminating inputs/conditions,
assertions, expected results and pass/fail criteria, with their selected checks
and exclusions. A change to those semantics requires Human approval before it
is made, whether it appears in case prose, an assertion, a fixture or a driver.
File location or a "support-only" label does not decide the boundary.

Tester may repair its non-case metadata, execution drivers and support without
another Human approval when those frozen semantics remain unchanged. Tester
never fixes Worker production code. Orchestrator owns corrected execution
handoffs and disclosure; implementation failures remain the original Worker's
normal incremental corrections. Apply the following distinction:

| Observed problem | Required action | Accounting and approval |
| --- | --- | --- |
| Erroneous delivery metadata only | Return it to its original producer; correct and recheck the delivery | Same source and historical verdict; no Worker attempt or repeated case approval |
| Tester-owned non-case driver/support defect | Tester repairs its own lane; Orchestrator checks unchanged cases and binds corrected source/delivery; Tester reruns affected checks | New source/execution identities where bytes changed; no Worker attempt or new Human approval |
| Orchestrator handoff mistake prevents or misdirects test execution | Orchestrator rewrites the affected handoff, removes ambiguity and sends rechecked inputs for Tester to retest | No Implementation failure inferred solely from broken execution; no Worker attempt for the handoff repair/retest |
| A handoff ambiguity affected delivered Implementation and a valid case exposes its defect | Preserve the valid failure; Orchestrator removes public ambiguity before the next attempt; original Worker performs the incremental fix | Normal valid-failure path consumes one Worker attempt within the existing budget; no free restart or metadata exemption |

If both execution support and Implementation are affected, first restore a
trustworthy execution path, then use the real case result to route the
Implementation defect. Do not relabel a valid failure as a delivery problem,
weaken its expected result, or escalate every local mistake to a global terminal.

A metadata-only repair must preserve the reviewed scenarios, discriminating
conditions, assertions, expected results and pass/fail criteria, selected checks
and exclusions, exact source tips and actual source inventory/content, recorded
business verdicts and lifecycle identities/counts. It may describe an already
existing dependency accurately;
it must not invent a dependency or missing predecessor, change actual coverage,
add/remove a check, replace a command, or relabel a failed result as PASS.
Manifest/reference corrections must still describe that same existing source;
their metadata is not immune to repair, and a changed digest needs fresh checks.
For Human decisions this also preserves the original gate, decision and exact
subject identity. A format fix cannot change REQUEST_CHANGES to APPROVE or
redirect approval to another Test/Candidate. Do not infer missing business
fields from the desired next action; actual binding drift is not metadata repair.

The original producer supplies corrected delivery bytes at a new artifact
path/identity, with the original input/rejection, reason and precise diff retained. The
Orchestrator reviews semantic equivalence and disclosure, reconciles affected
references to the new digest, then obtains fresh central and consumer checks
before consumption. A metadata-only reconciled report/approval reference is not
a new READY, Human vote, execution, Candidate or correction. Never rewrite
original approval or run evidence, or reuse a receipt for changed bytes.
Unaffected functional evidence need not rerun merely because descriptive
metadata changed; a corrected execution handoff requires the directed retest.

Repair of test execution code (for example a loader or fault-injection driver)
is source repair, not metadata repair. When it is genuinely non-case support,
Tester may perform it under this rule without a separate Human source-repair
approval. Keep the original Test/source, failure and Human approval; record the
incremental old/new source tips, changed files/digests and why all frozen case
semantics are unchanged. Update source inventories/manifests, affected references
and the exact executable Test/Candidate binding. A source change cannot claim
the old Test or Candidate SHA. Orchestrator reissues the affected execution
handoff; Tester reruns the affected selected checks and records fresh execution
identities/results. This does not consume or reset a Worker attempt. A real
case or requirement change still needs Human approval; ambiguity about that
boundary blocks only the affected repair while the distinction is resolved.

Use the registered repair representation below when pinned W enables it.
Preserve legacy rejected-only deliveries as historical evidence; do not rewrite
them into the new representation. An old W2 run does not acquire new authority
merely because the installed checker has been upgraded. A real requirement or
case change remains outside the unchanged-case repair path. Never fabricate a
rejection, manufacture CHECKED, infer a missing original Human vote, or use an
unsupported representation alone to declare terminal functional failure.

### Versioned machine repair representation

W3 opts in with `non_case_repairs` version `1.0`, with `metadata` and
`test_support` enabled; W4 retains that capability. The functional profile and
fourteen artifact kinds remain the same. Old W2 inputs without repair extensions remain supported;
new repair fields under W2 are rejected. W1 record validation remains explicit
and separate. A task's pinned G/W is never silently changed during repair.

The existing `delivery-repair` kind has a legacy rejected-only form and two
explicit `payload.repair_version = "1.0"` forms. Use the closed schema for all
members, including exact inline evidence; this table explains their meaning.

| Form | Evidence and consumption | Source / accounting effect |
| --- | --- | --- |
| Legacy repair | Exact original and real REJECTED receipt; replacement uses `original` plus `guard_result` | Existing strict same-source/business preservation |
| `METADATA` | Real rejection, or an Orchestrator observation linked to the original CHECKED receipt; exact before/after attachment bytes, references and semantic audit; replacement uses `original` plus `repair` | New delivery identity/digest, same original producer/source/verdict/counts; no new READY, Human vote or execution |
| `TEST_SUPPORT` | Original approved Test/report and approval, prior effective source, strict descendant Test tip, exact source-change inventory, new manifest and Orchestrator semantic review | Registers new executable support source without changing original approval, Worker source, Candidate result or correction count |

For an observed metadata error, preserve the old CHECKED receipt as it really
was. The observation explains what was discovered afterward; it is not a
retroactively fabricated guard rejection. Every changed supported attachment
reference needs one exact before/after mapping. Each mapping binds raw UTF-8
bytes, parsed JSON and SHA-256; the guard also verifies the real files. The pure
state engine verifies the same inline byte/body evidence without file access.
The replacement receives fresh guard checks before its event is consumed.

The new attachment must satisfy its normal schema and source constraints. Old
erroneous descriptive metadata can be retained without pretending it validates;
its authoritative source and protected semantics must nevertheless be
unambiguously recoverable. Metadata-only repair preserves selected check IDs,
families, commands, requirement coverage and all old covered paths, excluded checks and
prevalidation modes. It cannot alter a command result or relabel a failure.
Public-dependency corrections require an exact per-edge audit tied to current
source blobs, not just a new reason string. The Orchestrator still judges
whether the claimed dependency accurately describes the unchanged source.

An omitted `covered_paths` attribution may be added through complete METADATA
repair only when the exact original Test and unchanged selected invocation
already exercised that path. This repairs the recorded attribution without
expanding real acceptance scope. Keep every old path in its original check;
do not remove or transfer coverage, add or change checks, alter their family,
command or requirements, change exclusions or prevalidation modes, or change
any frozen scenario, assertion, expected result or pass/fail criterion. A real
acceptance expansion still requires a Human decision.

Use the existing original report and before/after Impact Set snapshots with
their exact digests and `changed_fields`. `preserve_tip` must equal the original
report's Test commit. Each newly attributed path must have a `source_facts`
binding for its real blob at that exact Test commit, included in the
Orchestrator `semantic_audit.source_bindings`. Its `affected_check_ids` must
identify exactly all checks receiving attribution additions. The semantic audit
must explicitly examine coverage and every existing frozen dimension, confirming
that the same invocation already exercised the added paths. Dependency changes
retain their independent per-edge source audit. The guard checks actual Git
blobs; the pure repair rules check the supplied bindings and projections.
Neither proves execution or the truth of the audit's source interpretation.

A permission flag, reason string, incomplete audit, unrelated source version or
missing blob binding cannot authorize this exception. Direct
`validate_impact_projection` calls remain strict without complete repair evidence;
no new public flag, schema field or workflow capability is added. The original
producer delivers a replacement with a new digest and fresh checks under the
existing replacement chain, preserving T/approval, source, verdicts and counts.
W2 does not acquire W3/W4 repair capabilities from a checker upgrade. Actual
Test support source changes still use their existing source-repair and retest
route; stale evidence cannot become a new execution result.

For support source repair, the semantic audit identifies the exact old/new
source, changed files and why scenarios, discriminating conditions, assertions,
expectations and acceptance scope are unchanged. A flag or filename alone does
not establish this. Real added/removed supporting files may be reflected in
coverage metadata only with their exact source changes and per-path audit;
this cannot add a check, weaken case coverage or introduce a new requirement.
Tester owns the source repair; the Orchestrator reviews it and records the
checked repair. The guard verifies real Git facts and the state engine checks
the supplied evidence and lifecycle. Neither claims to prove arbitrary natural-
language semantic equivalence or remote identity authentication.

`state.test.ready` and `state.test.approval` retain the original approved
case anchor. A Candidate's optional `payload.support_repair` identifies its
actual executable Test/manifest. The latest registered support repair must
continue the immediately preceding effective Test source, including a repair
not yet executed. Later ordinary Worker corrections retain that latest source.
Do not use an old Candidate's Test to restart a support branch.

| Current execution state | Permitted next execution after support repair |
| --- | --- |
| No Candidate yet | C0 uses repaired Test and ready I0, with ordered Test/Implementation parents |
| `INVALID_RUN` | Fresh source-bound Candidate, dispatch and execution, at the same Worker correction index; old invalid result retained |
| Valid `IMPLEMENTATION_FAIL` | Failure remains; original Worker must complete the normal counted incremental correction before the next Candidate |
| PASS, exhausted corrections, STOP or terminal review | No automatic reopening through support repair |

Support registration is bookkeeping, not a test run and not a free Worker
attempt. A newly assembled executable snapshot cannot claim the old Candidate
SHA. Source-changing repair is distinct from an unchanged-source INVALID_RUN
retry, which still uses the exact same Candidate. Rerun affected selected
checks on the new executable source and retain fresh execution evidence; do
not reuse old results to claim that changed support was tested.

For the affected checks of a newly executed support snapshot, both layers reject
reuse of an earlier execution's exact command-result reference. Accumulate the
affected checks across intervening, not-yet-executed support repairs; already
executed historical repairs do not create a perpetual new requirement. A fresh
result identity may contain identical deterministic outcome bytes. A metadata
replacement of the same business execution instead preserves its result
identity and is not another execution. These checks detect known stale refs;
they do not prove that an external command really ran.

## Scoped evidence and the diagnostic bridge

The schema distinguishes attachment structures rather than treating every
digest-bound file as equivalent. Lane manifests retain their established
five-field contract. Impact sets declare selected and excluded checks, public
dependencies, requirement/path coverage and prevalidation obligations. Coverage
joins bind the actual Test/Implementation change inventory to that fixed
selection. Command results bind the operation and environment to the recorded
outcome. Authority snapshots and lessons remain raw-byte-bound documents whose
meaning requires the responsible role's review.

Coverage attribution and public dependencies are independent declarations.
Each join must contain exactly the actual `G..T` and `G..I` changed paths, once
each, with non-overlapping Test/Implementation ownership. Every changed path's
requirement and selected-check references must resolve; each mapped check must
cover that path and all requirements attributed to that change. Neither extra
dependency edges nor removed mappings can substitute for changed-path coverage.

One selected check may cover several source, test, helper or review files that
have no direct dependency on each other. Co-membership in `covered_paths` does
not require, generate, reverse or complete a dependency edge. Validate the
declared `public_dependency_edges` separately: duplicate directed `(from, to)`
pairs fail `DEPENDENCY_EDGE`, even if their reasons differ; both endpoints must
belong to the union of selected checks' `covered_paths`, or the join fails
`DEPENDENCY_COVERAGE`. An excluded check cannot supply endpoint coverage. The
endpoints need not occur in one check, and dependencies may include unchanged
helper paths. Preserve the direction and reason of each real direct relation;
multi-level relations retain their direct edges without requiring shortcuts.
Do not infer undeclared edges from Cartesian pairs, connectivity or filenames.

These checks establish structural consistency of supplied bytes, identities,
actual change inventories and declared endpoint coverage. They do not discover
every actual source dependency, prove a reason string true, or prove that a
command executed the claimed coverage. Orchestrator must inspect the exact
source to verify dependency truth, completeness and check attribution. An
omitted real dependency, fabricated edge or fixed-version source association
misrepresented as a current execution dependency remains unacceptable even
when the structural result is CHECKED. Preserve that observation and use the
existing original-producer repair or ambiguity route; do not fabricate a
machine rejection or Human approval. No general source dependency extractor or
new automatic trust guarantee is provided.

This distinction does not relax the frozen-case or non-case repair boundaries.
Descriptive dependency repair still requires the original producer, an exact
per-edge audit bound to real source blobs, the original T/approval and the
replacement chain. Selected check IDs, commands, requirements and all old covered paths,
exclusions and prevalidation modes retain their existing protections. Metadata
repair may add omitted attribution only under the complete source-bound rule
above; it cannot change source or reuse stale results as a new execution. Actual
Test support changes retain their source, semantic-audit and retest obligations.

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
| Incorrect handoff metadata after Test approval | Original producer repairs under the shared non-case boundary | Same cases/scope and source; corrected bytes/references checked, no repeated case approval or Worker correction |
| Non-case Tester support or execution-handoff defect | Tester repairs its support; Orchestrator corrects and rechecks execution handoff | Preserved cases; actual source lineage, fresh affected execution evidence, no Worker attempt |
| Handoff ambiguity affected Implementation and valid testing exposes a defect | Orchestrator removes public ambiguity before the next attempt; original Worker fixes | Normal incremental valid-failure correction consumes an attempt; no clean-room restart |
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

### W4 Reviewer lessons and exact delivery

W4 explicitly enables `reviewer_lessons` and sets `lifecycle.pr_head` to
`reviewer_lesson_commit`. Its `reviewer-report.payload.lesson_commit` is a
nullable Tip: it is required and non-null whenever the terminal review has a
Candidate C; it is explicitly null when failure occurred before any Candidate.
W2/W3 reject this extension. W1 legacy records keep their own interface.
An upgraded checker does not change a run's pinned G/W or rewrite old authority.

The tested/reviewed Candidate C remains the exact two-lane direct union, with
ordered parents [effective Test, Implementation]. Reviewer writes its terminal
report and appends, stages and commits the current lessons once on that Candidate
branch. Lessons commit L has C as its sole direct parent and changes only
`agent-discipline/agent-lessons-learned.md`, retaining the complete existing
file bytes plus a nonempty append. Do not amend C, rewrite prior lessons, add
another parent, change file mode/type or include Test/Implementation, policy,
raw reports or execution evidence. This is not a new Candidate, correction,
Tester execution or second review.

Bind L's actual commit/tree/parent identity in `lesson_commit`. The referenced
raw lesson evidence must match the complete lessons-document blob at L, not
just its appended fragment. Orchestrator checks actual C→L lineage and changed
source against the allowed append. The guard and read-only evidence verifier
prove those local Git/blob facts; the pure reducer checks declared Tip/parent
and lifecycle identity only, not filesystem content or actual Git history.
Neither that proof nor Tester PASS claims that L was executed. No retest is
required solely for a verified lessons-only append; actual code/test changes
are prohibited by this terminal step, not excused as lessons.

The control/evidence worktree may remain pinned to G while the explicitly
authorized Candidate branch/worktree receives L. Selective raw evidence transfer
still follows the local-state rule; this arrangement does not force a separate
lessons branch. The Reviewer saves current lessons on success and failure rather
than deferring them to #109's later aggregation. Failure before C exists retains
raw lessons with null `lesson_commit`, never a manufactured Candidate/commit.
Failure after C retains C, L, final Implementation and original verdicts without
automatically opening a success PR.

For W4 success, `accepted_candidate` remains C while PR head, FINAL decision and
merge evidence bind L. The final Human review receives both C and L, the single
original review identity/verdict, findings with severity/evidence/impact, scope,
treatment or follow-up issues, lessons and remaining decision. Preserve the
original report; later summaries or Human dispositions are labelled separately.
W2/W3 retain their historical exact-C PR and separate-lessons bindings. W1
remains explicit legacy-record validation, not the structured representation.
Old reports, decisions, tests and changelog entries are not migrated in place.
PR-only repository protection is not bypassed by either version.

### Remote delivery

Before requesting review, push the exact intended branch with an explicit
source:destination refspec, set its matching upstream and verify the remote
head. Never push directly to master, let a feature/policy branch track master
or use an ambiguous push.
Publish or update the issue's current review entry with exact-commit links;
local artifacts alone are not a usable remote review packet. A replacement
packet supersedes the prior entry explicitly without rewriting old approvals.

### Reviewer findings become follow-up issues

A new Implementation defect discovered by the terminal Reviewer goes to an
independent issue, not the old task's remaining attempts. Reviewer owns the
technical description/evidence; Orchestrator publishes and links the issue when
Reviewer has no authorized remote-write interface. Check for an equivalent
issue first. Publication does not authorize another Worker or repair cycle.

Each issue identifies the original task/Candidate and finding, public
requirement, affected production surface, expected versus observed or statically
inferred behavior, evidence/uncertainty, impact/risk, recommended priority with
rationale, and implications for the current Candidate's merge. Keep hidden case
literals, assertions and confidential reports out of public diagnoses. Use
existing finding/evidence fields plus the issue body; do not invent members in
the closed handoff schema.

Human decides immediate/deferred treatment and current Candidate disposition
at final review. A finding is neither automatically global-blocking nor
automatically harmless because Tester passed: PASS establishes tested scope,
not absence of other defects. A new issue cannot erase a mandatory/safety
failure, reset the old budget, relabel a verdict or grant merge permission.
A Human-selected follow-up has its own scoped G/K/Test and lifecycle, preserving
reusable Implementation instead of rewriting it. Frozen-case changes still
require their Test Gate approval.

Keep the single Reviewer report and old Tester verdict immutable. Do not
dispatch a second Reviewer or post-terminal correction by default. Existing
automatic success validation still requires Tester PASS and Reviewer APPROVED;
where explicit Human disposition differs from that encoded route, preserve it
as manual authority, not a fabricated APPROVED or automatic SUCCESS.
Runtime/intake support belongs to follow-on packages; this documentation change
does not implement it.

### Compatibility and runtime limits

Legacy W v1 is preserved at `agent-discipline/contracts/workflow-v1.json` for
explicit validation of old records. W2 declares the structured lifecycle;
W3 enables non-case repairs; active W4 preserves both and explicitly enables
the Reviewer lessons C→L delivery extension.
Do not feed new artifacts to a legacy validator or
silently fall back to old route/counting rules. Existing #88 wire fields and
timeout aliases remain compatible. Its intentional behavior correction requires
run to follow a successful CHECKED receipt matching the latest event; prepare
alone is insufficient. The #90 compatibility command uses the same internal
legacy packet validator exposed by the unified guard.

An upgraded coverage checker keeps the existing Python/CLI entrypoints, result
formats and closed structured v2 schemas under each run's pinned W2, W3 or W4
capabilities. Existing task/G/W/K, real tips, manifests, attachment digests and
Candidate bindings remain checked; the explicit legacy W1 path is unchanged.
The source version executing the checker is separate from the examined run's
Governor and workflow blob. Before resuming a pending run such as #112 after
this separately reviewed correction, Orchestrator records the independently
reviewed checker's exact source commit and revalidates the supplied material in
the original run context. Do not substitute a new G/W/K, rewrite Test approval,
Candidate or historical evidence, or describe the upgraded source as the old
checker. Fresh structural CHECKED evidence is neither functional PASS nor
Human authorization or proof of complete natural-language correctness.

The [pure transition engine](workflow-transitions.md) implements global
consumption and repair ordering without executing the workflow. Complete
remote-evidence/direct-union proof is provided by the read-only
[evidence verifier](workflow-evidence.md). Capability isolation (#79),
route execution (#87), and Human/GitHub intake (#80) remain separate. Their contracts
consume these checked inputs/outputs; read-only proof is not their implementation.
Explorer and other workflow profiles are future schema/registry extensions.
KPI is an independent Human-started, issue-driven, post-merge profile for RTD
CfgFile CLI, not a functional correction/optimization branch. Its dedicated
case review, results and dashboard are separate #100–#102 work.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.1.0 | Documented structured functional handoffs, scoped evidence, safe diagnostics, local guard boundaries and explicit legacy migration. |
| 2026-09-06 | 0.1.1 | Bound document-first Human Test review to existing exact Test artifacts, type-classified prospective catalogues and the unchanged confidentiality/KPI boundaries. |
| 2026-09-06 | 0.1.2 | Split the review surface into durable public requirements and concise private cases with a shared index; kept executable evidence in existing reports and added no schema or Gate. |
| 2026-09-07 | 0.1.3 | Distinguished frozen case semantics from repairable delivery metadata; defined same-producer repair, semantic/digest checks and unchanged accounting, while separating Test-driver source changes and current runtime limitations. |
| 2026-09-07 | 0.1.4 | Applied Human's non-case repair authority to Tester support, preserved case-change approval and real source lineage, and separated execution-handoff retests from counted Implementation corrections without claiming runtime changes. |
| 2026-09-08 | 0.1.5 | Defined two routine Human reviews, issue-based terminal findings and preserved bootstrap exceptions; required Human-decision preservation in format repairs and exact remote review delivery, without claiming runtime changes. |
| 2026-09-09 | 0.1.6 | Linked the single local-state rule and made selective, byte-checked central/lane transport explicit while preserving protocol identities and historical paths. |
| 2026-09-09 | 0.1.7 | Defined W3 opt-in machine metadata/support repair, shared inline evidence, original case approval anchors and source-bound execution without freeing Worker corrections or reopening terminal review. |
| 2026-09-09 | 0.1.8 | Linked read-only real-source, direct-union and remote finalization proof while retaining separate execution/intake boundaries. |
| 2026-09-10 | 0.1.9 | Defined W4 Reviewer-owned lessons-only C→L lineage, complete lessons evidence, separate tested/PR identities, failure preservation and old-version compatibility without a new review or retest. |
| 2026-09-11 | 0.1.10 | Separated selected-check coverage from declared direct dependencies, retained endpoint/source/frozen-repair checks and stated exact checker-upgrade provenance. |
| 2026-09-11 | 0.1.11 | Allowed audited additions of omitted coverage attribution through complete METADATA repair, binding exact Test blobs and affected checks while preserving old paths, frozen semantics and strict direct projection calls. |
