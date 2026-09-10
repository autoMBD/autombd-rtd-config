# Local Execution State and Handoff Storage

| Field | Value |
| --- | --- |
| Version | 0.1.1 |
| Date | 2026-09-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Local state ownership, directory layout, selective lane transfer, evidence lifecycle and scoped cleanup. |

## Purpose and authority

This Category B document is the single storage rule for `.agent-state/`.
It organizes local execution material; it does not add a workflow, artifact
schema, state machine, Human gate or execution permission. Follow
[Structured Handoffs](skills/agent-workflow/references/structured-handoffs.md)
for task semantics, existing schema/registry identities, repairs and role
visibility, and [Agent Monitoring](skills/agent-workflow/references/agent-monitoring.md)
for supervision. A directory, filename or navigation status is never approval,
CHECKED, a functional verdict or correction accounting.

Use one authoritative source for each fact. Source code, Worker unit tests and
Tester functional tests belong to their Git lanes. Durable requirements/cases
remain in the agreed `tests/doc/` layout; reusable discipline belongs here in
`agent-discipline/`. K, Envelopes, execution reports and local approval evidence
belong in ignored state. KPI's approved durable cases/results have their own
issue-driven storage, not this directory as a permanent results database.
Do not create a task directory for every question, read-only lookup or tool call.

## Top-level layout and navigation

Paths in this table are relative to the central work area's `.agent-state/`.
Create directories only when needed, not as empty scaffolding.

| Path | Purpose / owner |
| --- | --- |
| `README.md` | Human-readable local navigation, maintained by Orchestrator; not the repository-root README |
| `agent-loop/<task_run>/` | Task contracts, structured handoffs and bound evidence |
| `agent-monitoring/<task_run>/<dispatch_id>/` | Existing monitor plan/events; same task/dispatch identities |
| `plans/` | Task-specific execution plans and explicitly distinguished cross-issue plans |
| `wt/` | Sole location for newly created linked Git worktrees |
| `external-dependencies.json` | Existing non-secret dependency cache, under its existing Skill |
| `init-input.json` | Existing initialization input; ordinary work must not rewrite it or trigger initialization GUI |
| `e2e-preferences.json` | Existing local E2E preferences, not task authorization |

Do not create synonymous top-level `policy-review/`, `tasks/`, `handoffs/`,
`issue-<number>/`, `workflow/` or `worktrees/` directories for new work. Fit a
new task into its existing category. A genuinely new category belongs in an
explicit discipline change explaining purpose, ownership and cleanup; it is
not an ad hoc side effect or a new approval gate for each ordinary file.
Legacy paths remain handled by the migration rule below.

Navigation uses one row per task/run, not a duplicate file database. Include
task_run and issue/Human task, execution mode, task/plan/monitor/worktree
locations, latest handoff or terminal-result entry, whether still in use and
last update. Cross-issue plans get a distinct section; historical/unknown
status must be labelled rather than guessed. Update relevant entries when a
handoff, interruption, terminal disposition or cleanup changes their meaning.
Navigation summarizes; original source-bound reports and Human evidence decide
status. It is not a subagent task contract, and the full central index must not
be supplied to Worker when it exposes private Test locations.

## Task layout

Within `agent-loop/<task_run>/`, use these categories as needed:

| Path | Contents |
| --- | --- |
| `authority/` | Relevant Issue/specification/Human source snapshots with origin and capture context; not fabricated remote approvals |
| `inbox/` | Public K, dispatch Envelopes, trusted context and authorized input attachments |
| `outbox/` | Role reports, guard results, terminal records, raw Reviewer lesson evidence and clearly labelled Orchestrator summaries |
| `evidence/<execution_id-or-check-id>/` | Raw command outputs, execution context and report-referenced attachments |

K is the public contract in inbox, with sources under authority. Manifests,
Impact Sets and coverage joins are referenced handoff attachments, not competing
task contracts. An attachment produced as output can be delivered as an exact
input copy; its identity and ownership do not change because of its directory.
Existing tool-defined state snapshots and events are task outputs using that
tool's format, not a new invented state schema. Plans and monitoring remain in
their existing top-level locations and are linked, not duplicated into the run.

Active test throwaways and staged fixtures stay in that worktree's `tests/.tmp/`,
not system TEMP or new scratch folders in `.agent-state/`. Preserve selected
raw evidence needed by a report before cleanup, with accurate paths/digests;
do not retain every rebuildable temporary tree or convert raw output into
rewritten evidence. Reviewer JSON and raw Markdown lesson evidence remain
separate outputs. Under W4 the durable lessons document is also appended and
committed once by Reviewer on the Candidate branch as C's lessons-only child L;
the raw lesson snapshot binds the complete L document. W2/W3 retain their
historical separate-lessons rule; W1 remains explicit legacy validation. See the shared
[terminal protocol](skills/agent-workflow/references/structured-handoffs.md#terminal-review-pr-and-legacy-boundaries).

## Identities and continuity

Use existing legal identities: task_run is the task series, dispatch_id is a
role dispatch, execution_id is an actual execution, and artifact identity/
revision identifies delivered bytes and replacement lineage. Descriptive short
filenames include the type and needed identity/revision; avoid ambiguous
`final-final`, `latest2` or parallel names for the same current authority.
Names locate files; contents, references and hashes establish their identity.

Corrections, delivery repairs and continuation do not become a new task_run
merely to tidy directories. New dispatch/execution IDs do not create a Candidate
or reset the correction budget. Retain the same Worker/lane/session/worktree/
Implementation where required by the lifecycle. A related genuinely new task
records its relationship and authorized reusable work; a new path is not
permission to restart implementation from G.

A Human-commanded policy task can use its own run under `agent-loop/`, without
being forced through the functional-development profile. When its input/output
contract is not registered, define a bounded structured manual contract before
dispatch and label it honestly; do not claim registered guard or runtime support.
Prompts still locate the task files rather than carrying hidden obligations.

## Central and lane-local transfer

Ignored `.agent-state/` directories do **not** synchronize through Git commits,
checkout, fetch or worktree creation. Orchestrator coordinates explicit,
selective file copies; no mirroring or shared-directory link is implied.

| Actor | Write responsibility |
| --- | --- |
| Orchestrator | Canonical authority/K, dispatches, public diagnoses, central checks, navigation and Human-facing delivery |
| Worker | Its Implementation/unit tests, reports and evidence in its own lane |
| Tester | Its Test, prevalidation/results and authorized non-case support repairs; never Worker production |
| Reviewer | Its one terminal report and raw lesson evidence; under W4 also the append-only lessons commit on Candidate branch; Test/Implementation remain read-only |

For a handoff:

1. Orchestrator selects the authorized files and checks their semantics,
   identities, exact references and disclosure.
2. Copy only those files as exact bytes into the receiving worktree's own
   `.agent-state/agent-loop/<task_run>/inbox/` and authorized attachment paths.
   Include the complete public K and the inputs actually needed by its Envelope.
3. The receiving role validates those local bytes and trusted bindings using
   the applicable existing checks. The central directory is not its input path.
4. The role writes its declared lane-local outbox and evidence. It announces
   progress/result location; chat is not an alternate report.
5. Orchestrator checks the actual output, copies the declared results/evidence
   back into central storage without rewriting the producer's bytes, verifies
   matching SHA-256 and retains their source provenance before consumption.

Use the same task_run, dispatch_id, G/W/K and artifact/evidence references to
associate copies. Only their authorized containing worktree differs. Preserve
safe relative paths required by the protocol; absolute worktree locators are
used only where their existing field allows them. Do not edit a report merely
to make a central copy appear native. If a reference cannot resolve safely in
the receiving context, repair/reissue that delivery with real lineage instead
of silent path rewriting or traversal into another lane. Never resolve equal
filenames by last-write-wins: equal identity/digest is a copy; changed bytes
need the appropriate new identity/revision and renewed checks.

Never copy the whole central directory, private Tester report, hidden cases or
case-bearing index into Worker. Do not link its inbox to another lane's state.
Use the existing safe consumer-local evidence view; central CHECKED receipts
with confidential paths cannot be forwarded wholesale. Directory separation is
an operating rule, not proof of OS capability isolation or automatic transport.

A control/evidence worktree pinned to G need not move to L. Under W4,
Orchestrator identifies the authorized Candidate branch/worktree for Reviewer's
lessons-only append/commit and collects its exact complete-document snapshot
and report using the same selective transfer rules. This does not require a
separate lessons branch, broaden source access or synchronize ignored state.

## Formats, publication and mutation

Formal role artifacts use the existing closed schema/registry; monitor files
retain their v1 JSON/JSONL contract. Human plans/summaries/lessons are Markdown;
raw outputs retain their real format. Registered canonical JSON remains UTF-8
without BOM, duplicate keys or non-finite values, with the protocol's sorted
compact keys/final LF and raw-byte SHA-256. Do not apply text normalization to
raw evidence or invent members to describe storage housekeeping.

| Material | Mutation rule |
| --- | --- |
| Undelivered draft | Original producer may edit before publication |
| Delivered/checked contract, Envelope, report or immutable receipt | Preserve original; repair using a new artifact identity/path and explicit reference to the old one |
| Raw execution and Human approval evidence | Preserve bytes and original verdict; no historical rewrite |
| Monitor/operation event history | Append under its existing contract, not rewrite |
| Navigation, plans, allowed cache and mutable tool snapshot | Update within its owning contract; never replace referenced historical truth |

Respect an existing tool's explicit mutable receipt semantics: for example,
the #88 prepare/check-handoff/run chain updates its current receipt and appends
events. Do not break that CLI by imposing a new immutable output path on each
step. A particular snapshot already cited as immutable evidence must remain
available separately with its real identity; the mutable latest pointer cannot
stand in for historical evidence. No concurrent writers to one output path.

Case freeze and authorized non-case repair follow the shared handoff rule.
Storage tidying cannot change scenarios/assertions/expectations, approval
subjects, source SHAs, functional results or correction accounting. Non-case
source repairs retain actual new source/execution identities and affected retests.

## Local failure and interruption handling

| Problem | Route |
| --- | --- |
| Naming, classification or navigation drift | Record and correct locally; not a functional failure or global stop |
| Missing current input, wrong digest/reference or skipped predecessor | Hold that consumption only; original responsible party repairs and rechecks |
| Potential private Test disclosure | Hold that transfer; Orchestrator repeats disclosure review |
| Valid testing finds Implementation failure | Existing incremental Worker correction/attempt path |
| I/O, network, tool or platform interruption | Preserve progress, inspect side effects and resume safely without manufactured results or a new series |
| Genuine unresolved responsibility/semantic ambiguity | One bounded diagnostic, then a precise Human question |

Monitoring records waiting/contact/intervention/termination, not business
verdicts. Do not respond to each unknown by inventing another directory, schema,
global rule or severity escalation. Honor dynamic Agent estimates and separate
configurable command deadlines; a timeout is not automatic source invalidation.

## Completion, retention and cleanup

During execution preserve active inputs, approvals, report dependencies and
resume state. Clean owned test throwaways under the existing test rules; do not
delete a still-referenced unique evidence file as though it were a cache.
At completion, Orchestrator updates the result entry and exposes the Reviewer's
verdict, key findings/evidence/impact, treatment, lessons and pending decision
in the PR body or failure issue. Label central summaries and local-only originals
honestly. Publication does not change the original Reviewer verdict or source.

Retain the smallest complete evidence chain needed for review/traceability;
do not indefinitely keep all reproducible temporary files. Default archive is
logical: mark ended in navigation while referenced files remain at their bound
paths. No default age-based deletion of valid evidence. A proposed relocation
lists old/new locations and reference impact and requires applicable authority;
never alter bound bytes while pretending old hashes still apply.

Worktree removal, branch deletion and stash deletion are distinct operations.
Validate the exact resolved targets, worktree registration and local changes
before cleanup. Use Git worktree management for registrations. Inspect local
changes and state the impact; when Human explicitly directs discard, do not
create unsolicited stashes/backups. Without discard/preservation authority,
hold only the affected destructive operation. Remove links themselves without
following them into other locations. Verify registrations and filesystem
residue afterward and report scope and available recovery, without claiming
permanent secure erasure. Never touch the main work area or unrelated lanes.

## Existing material and implementation boundary

Apply this layout to new work. First index active old runs without moving their
bound files; label historical `policy-review/`, misplaced reports under plans,
or other old paths with their owning task and do not continue new work there.
Do not recreate removed historical worktrees or manufacture missing histories.
Approval of this policy is not blanket authorization to migrate/delete existing
evidence, change schemas, deploy discipline or alter a functional Candidate.

Keep this rule in one place; charter, workflow and monitoring guidance link it.
Existing guards validate supported path/identity/digest/order constraints only.
Navigation upkeep, selective transport, semantic disclosure and retention remain
explicit Orchestrator duties unless separately implemented. No new full-suite
test run, extra Human gate, autonomous Loop or logging platform is required by
this documentation change.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-09 | 0.1.0 | Established the Human-approved local layout, explicit selective lane transfer, evidence lifecycle, navigation and scoped cleanup without new runtime or migration. |
| 2026-09-10 | 0.1.1 | Distinguished raw report/lesson storage from W4 Reviewer lessons commit on Candidate branch while preserving a G-pinned control worktree and historical W1–W3 behavior. |
