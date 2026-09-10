# Pure Workflow Transitions

| Field | Value |
| --- | --- |
| Version | 0.1.6 |
| Date | 2026-09-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Public memory-only transition API, wire, lifecycle, error order and evidence boundary. |

## Purpose and ownership

The transition core consumes current structured functional-development
artifacts. It adds global consumption order, active identity, replay rejection,
parallel readiness, frozen approval, bounded incremental corrections and one
terminal review. It does not execute the workflow.

The [structured handoff protocol](structured-handoffs.md) defines the role
artifacts. W3 explicitly enables non-case repair; W4 retains it and opts into
Reviewer lessons delivery. W2 remains supported without those extensions;
W3 keeps its original exact-C finalization. Profile, fourteen artifact kinds
and State/Event/Context wire shapes remain stable. The legacy
record/path/validate commands and file guard
retain their ownership.
This core is not a wrapper for the obsolete seven-checkpoint or F0/F1 lifecycle.

| File relative to this skill | Responsibility |
| --- | --- |
| `scripts/workflow_transition.py` | Public API, ordered checks, state invariants and read-only CLI |
| `scripts/workflow_transition_wire.py` | Pure JSON/schema/wire and canonical-byte helpers |
| `scripts/workflow_transition_rules.py` | Memory lookup, active identity and lifecycle rules |
| `schemas/workflow-transition-v1.schema.json` | Portable closed State, Event and Context definitions |

Imports do not discover or load schemas. Core functions do not access files,
Git, processes, network, current time, randomness or an Agent platform.

## Python API

Put the skill's scripts directory on the caller's Python module search path:

~~~python
from workflow_transition import (
    WorkflowTransitionError,
    initial_state,
    transition,
)

state = initial_state(task, governor)
try:
    next_state = transition(state, event, context=context)
except WorkflowTransitionError as error:
    public_error = error.as_dict()
~~~

`initial_state(task, governor)` creates the complete empty state. The fixed
workflow contract path is `agent-discipline/workflow-contract.json`.
`transition(state, event, *, context)` returns a detached complete next state.
`validate_state(state, *, context)` exposes the same current-state invariants
without a hypothetical incoming event or any I/O. The separate
[evidence verifier](workflow-evidence.md) adds complete real-source and remote
proof; this entrypoint alone retains the pure reducer's partial-catalog boundary.
No input is mutated on success or rejection; editing the returned state does
not modify the input event or catalog.

Values must be JSON-native dictionaries with string keys, lists, strings,
integers, booleans or null. Integers are distinct from booleans. Floats,
non-finite numbers, cycles and non-JSON objects are rejected. Errors expose
`code`, `pointer` and `message`; `as_dict()` returns:

~~~json
{"error":{"code":"MISSING_EVIDENCE","pointer":"/context/catalog","message":"Workflow requirement not met."}}
~~~

Pointers identify public input areas. Messages do not echo confidential report
bodies, source diagnostics or traceback content.

## Closed wire and caller-loaded context

The portable schema supplies `$defs.State`, `$defs.Event` and `$defs.Context`.
Task, Governor and ArtifactRef scalar/field domains match the existing handoff
schema. Unknown nested members are not silently ignored.

An event has exactly `schema_version`, `type`, `event_id`, `artifact`, and
`checked`. Version is `1.0`, type is `CONSUME`, and checked names a
`guard-result`. Guard receipts are evidence, never business events.

| State area | Stored slots |
| --- | --- |
| Authority | task, governor, nullable contract |
| Independent Test | launch, ack, ready, approval |
| Independent Worker | launch, ack, ready, pending_correction |
| Current Candidate | Nullable object with envelope, result |
| Single review | Nullable object with launch, report |
| Finalization | Nullable stop, final_decision, terminal |
| History | repairs; consumed entries containing event_id plus ArtifactRef |

Version/profile fields are also required. Nullable slots begin as null, both
lane objects exist immediately, and arrays begin empty. State does not duplicate
private report payloads, source text or business counters. Completed corrections
derive from the latest READY Implementation index; Candidate index remains
independent.

Context has exactly `schema_version`, `workflow_profile`, `task`, `governor`,
`protocol`, `artifacts` and `checks`. Protocol contains the explicitly loaded
`handoff_schema`, `registry` and `workflow_contract`. Unsupported versions,
profiles, schema vocabulary and required public domain structure fail before
lifecycle evaluation.

Business artifact entries contain `ref` and `body`. Receipt entries use the
same pair. IDs are unique within each catalog. Business artifacts resolve only
from artifacts; guard receipts can resolve from checks or explicitly supplied
guard-result entries in artifacts. Comparisons use the full reference.

Supply current slot references, consumed artifact references, the incoming
artifact, direct predecessors and relevant repair/replacement originals. No
missing object is fetched. Canonical digests use sorted compact UTF-8 JSON,
preserved Unicode and one final LF.

An explicitly named rejected format-repair original may additionally carry a
`raw` UTF-8 string. Its digest must match those exact bytes and strict JSON
parsing must reproduce body. Original whitespace need not be canonical.
Duplicate keys, invalid JSON, floats and missing trustworthy business fields
are not repaired by inference. Without raw, the canonical body digest applies.
Other artifact and receipt entries cannot use this exception.

## Transition rules

| Accepted input | Global effect and prerequisites |
| --- | --- |
| Initial K | First business artifact, revision zero, initializes contract |
| INITIAL lane launch | Either lane starts independently; Worker never waits for Test or approval |
| READY report | Establishes its own readiness; a pre-freeze withdrawal clears only that lane |
| Test decision | REQUEST_CHANGES clears Test READY; APPROVE preserves the original case/source approval anchor and K without waiting for Worker |
| New Candidate | Joins approved Test (or explicitly repaired executable support source) with latest READY I; ordinary later C requires next completed I |
| Tester result | PASS enables review; Implementation failure enables correction; explicit invalid gate/contract/integrity enables failure review |
| INVALID_RUN rerun | New execution/dispatch for identical Candidate; rerun_of is active INVALID_RUN report, with it and prior envelope as direct predecessors |
| Correction | One pending authorization, same lane/session/worktree/branch and previous I |
| Corrected READY | Advances I once and clears pending; NOT_READY preserves pending and previous I |
| Pre-approval K revision | Increments K, preserves source/history and clears ACKs; revised launches preserve lane, both K_ACKs precede new-K READY |
| FINAL/STOP | Preserves latest I, Candidate and pending work, enables truthful failure finalization |
| Reviewer launch/report | One logical terminal review on success or failure; STOP after launch retains it |
| Success proposal | Requires Tester PASS and Reviewer APPROVED; does not mean merged |
| FINAL decision | Binds exact proposal delivery head (W4 L, W2/W3 C); REQUEST_CHANGES cancels success without reopening corrections |
| MERGED / RECORD_FAILURE | Requires corresponding exact final route and closes business progression |
| Delivery repair | Orthogonal bookkeeping; replacements preserve business values and update only active delivery references |
| W3/W4 support repair | Registers strict descendant Test support and its audit while retaining original READY/approval, Worker and current Candidate/result |

There is no correction four, clean-room restart, automatic invalid-Test
reclassification, second review cycle or KPI retry. Candidate indices are 0–3.
New READY I may temporarily be one increment ahead of current C; STOP preserves
both actual facts.

Unchanged-source reruns retain Candidate, Test/Implementation tips, manifests, Impact Set,
coverage join and indices. Execution and dispatch identities cannot be reused.
A proposed new rerun reusing either identity from accepted history is
`STALE_EVENT` at identity priority 3, even with otherwise current bindings.
Available reuse facts take precedence over absent receipts; the pointer names
the reused `execution_id` or `dispatch_id` field. This differs from replaying
the exact current artifact, which is `DUPLICATE_EVENT` when no higher-priority
identity drift exists. Stale former-execution results cannot become the current
result.

For an already consumed repaired report, replacement does not reapply the
business transition. Historical bytes remain unchanged. A repaired Reviewer
delivery can update the current report while a prior accepted proposal retains
its reference to the equivalent original delivery.

### W4 Reviewer lessons and finalization identity

Under the pinned W4 `reviewer_lessons` capability, the single reviewer-report
includes `payload.lesson_commit`: non-null Tip L whenever review has Candidate
C, explicit null before any Candidate. L declares C as its sole direct parent
and remains separate from state.candidate and accepted_candidate. Consuming the
report does not assemble a Candidate, advance corrections, replace Tester
results or create another review. Failure retains the report/lessons without
becoming success. W2/W3 reject the member and retain their original bindings;
W1 remains explicit legacy validation, not this State interface.

Success still needs Tester PASS and Reviewer APPROVED for C. A W4 proposal's
accepted_candidate stays C, but PR head and FINAL subject bind L. Old C approval
cannot approve L. Equivalent report-format repairs preserve the original C/L,
review identity, verdict and lessons evidence. The pure core checks supplied
Tip/parent and active identity only; actual sole-parent history, lessons-only
changed paths and byte-preserving append are proven by the guard and read-only
evidence verifier. The protocol's
[terminal rule](structured-handoffs.md#terminal-review-pr-and-legacy-boundaries)
owns Reviewer commit and Orchestrator delivery responsibilities. No retest is
required solely for that verified append, and no claim is made that L ran.

### Non-case repair and executable source

Read the [machine repair representation](structured-handoffs.md#versioned-machine-repair-representation)
for the closed forms and trust boundary. W3 or W4 is required for versioned METADATA,
TEST_SUPPORT and Candidate `support_repair`; an upgraded local schema does not
enable them under an old W2 authority. Existing legacy repair inputs still take
their rejected-only path.

Metadata replacements can reconcile a previously CHECKED delivery through a
real Orchestrator observation and repair record. Inline before/after attachment
bytes and bodies make preservation checks visible to this memory-only core.
Original Human `gate`, `decision` and `subject_sha`, source and historical
outcomes remain unchanged. A changed attachment digest alone neither proves
semantic drift nor authorizes changing the checked meaning.

TEST_SUPPORT adds a record to `repairs`; it does not overwrite original
`test.ready`/`test.approval`, clear `candidate.result`, advance Worker index or
replay READY. Three source identities stay distinct: the original approved
Test, latest registered support source, and the active Candidate's executable
Test. An old Candidate remains honest history while newer support awaits
execution. A new Candidate must use the latest registered source and exact
support reference; repeated repairs continue that source even before execution.

With no Candidate, repaired support enters C0 when I0 is ready. After an
INVALID_RUN, an explicitly support-bound execution uses real new Test/Candidate
source, a fresh execution/dispatch and the same correction index. It retains
the old envelope and invalid result as predecessors, rather than pretending to
be an unchanged-source rerun. A valid Implementation failure still requires the
original Worker's next counted correction; registering support cannot erase
that failure or pending correction. PASS, exhaustion, STOP and terminal review
cannot reopen automatically. Later ordinary Worker corrections retain the
latest support source and original case approval.

The current correction index identifies Worker progress, not the number of
delivery metadata revisions or support-only executable snapshots. All old
source/execution artifacts remain immutable and visible in history. Fresh
affected evidence belongs to the newly executed snapshot, never its predecessor.
For intervening unexecuted support repairs, affected check IDs accumulate up to
the previous executed support source. Their new execution must not reuse exact
old command-result references. Fresh evidence with identical deterministic
bytes is allowed; same-execution metadata replacement preserves its existing
results. This is reference freshness, not external-execution authentication.

## Ordered rejection

| Priority | Code | Meaning |
| --- | --- | --- |
| 1 | MALFORMED_EVENT | Illegal event/context/incoming wire or unsupported protocol |
| 2 | INVALID_STATE | Illegal state shape or contradictory available accepted-state facts |
| 3 | STALE_EVENT | Present task/G/W/K, source, lane, dispatch, execution or review identity drift |
| 4 | DUPLICATE_EVENT | Already accepted event or exact artifact identity |
| 5a | ILLEGAL_TRANSITION | Frozen, terminal, exhausted or prohibited outcome route |
| 5b | OUT_OF_ORDER_EVENT | Legal action lacks an accepted lifecycle predecessor |
| 6a | MISSING_EVIDENCE | Required in-memory artifact or receipt absent |
| 6b | INVALID_EVIDENCE | Available schema, digest, receipt or preservation binding contradicts evidence |
| 7 | INVALID_OUTPUT | Proposed output fails independent invariant validation |

Available state relationships are checked even when another body is absent.
Full accepted-history reconstruction is deferred if its catalog evidence is
missing; absence does not fabricate an invalid-state diagnosis. Independent
lifecycle checks collect failures so missing receipts cannot mask observable
stale identity or illegal routes.

Priorities apply only to predicates established for the current operation.
An unauthorized next action does not establish a hypothetical next identity.
Repeating Candidate assembly from unchanged Implementation, submitting business
READY after C0 without an eligible correction, and launching Reviewer from a
non-terminal outcome are illegal routes. Next-Candidate predecessor/index and
INITIAL READY defaults must not manufacture stale errors for those routes.
A real pending correction still binds its exact index, previous tip and dispatch.

Retained older-K READY remains valid historical state but cannot satisfy a
current-K prerequisite. A correctly bound action awaiting eligible READY or
required ACKs is out of order when otherwise legal. Actual incoming K or
established subject drift remains stale.

Contradicted format-replacement business values are preservation evidence,
not a new progression authorization. They fail as `INVALID_EVIDENCE` unless
an independent earlier-priority predicate applies; no INITIAL or correction
identity is inferred from the altered values. Established task/G/W/K,
lane/dispatch/execution/review identities and explicit historical identity
reuse retain their published priority. Valid replacements still apply an
unconsumed original once or update only consumed delivery references.

Human-decision replacements preserve `gate`, `decision` and `subject_sha`,
including explicit null subjects; an absent original field cannot be guessed.
Changed gate/decision values are preservation evidence, not a new Human action.
For an already consumed decision still held in the active approval, stop or
final-decision slot, its original gate determines the actual Test/Candidate
subject binding. A changed subject then remains `STALE_EVENT`, ahead of missing
receipts or contradictory business fields. The replacement's altered gate must
not manufacture another subject. A historical Test REQUEST_CHANGES whose READY
was cleared has no active subject binding; its changed subject is instead
`INVALID_EVIDENCE` when the required evidence is available. Equivalent historical
repairs neither clear a newer READY nor reapply the old decision.

## CLI

~~~console
python agent-discipline/skills/agent-workflow/scripts/workflow_transition.py init --task task.json --governor governor.json
python agent-discipline/skills/agent-workflow/scripts/workflow_transition.py apply --state state.json --event event.json --context context.json
~~~

Every input is explicit. The adapter reads files only, loads no implicit schema,
starts no background work and offers no output file option.

| Outcome | Exit | stdout | stderr |
| --- | --- | --- | --- |
| Success | 0 | One canonical state JSON plus LF | Empty |
| Transition rejection | 1 | Empty | One canonical error JSON plus LF |
| Adapter/internal failure | 2 | Empty | One canonical error JSON plus LF |
| --help | 0 | Normal argparse help | Empty |

Exit 2 codes are INVALID_OUTPUT, INPUT_ERROR, USAGE_ERROR and EXECUTION_ERROR.
File failures, invalid JSON syntax, duplicate keys, floats/non-finite numbers
and non-object roots are INPUT_ERROR. JSON parsing precedes reducer validation.

## Trust and limits

A CHECKED receipt must itself have valid shape and digest, exit zero, available
evidence, no violations, exact input reference, matching recipient/visibility
and trusted task/G/W/K. A boolean assertion is not a receipt.

Offline comparison cannot authenticate Human or remote approval, prove a guard
actually ran, validate Git ancestry/direct union, establish capability isolation,
persist state, guarantee durable globally exactly-once processing or dispatch
an Agent. The caller owns these boundaries and atomic durable acceptance.
Manifest, authority, command-result and other raw attachments are checked by the
existing handoff guard; this reducer neither reads their files nor executes
LocalRules. Versioned repair records carry the exact limited attachment
before/after bytes and source-audit facts inline, so both layers can check the
same semantic-preservation projection. The guard adds actual filesystem/Git
checks; supplied facts do not make the pure reducer a Git or semantic oracle.

## Source salvage and verification scope

The only historical source input was the disclosure-reviewed clean-source
attachment. It supplied mechanisms, not acceptance evidence or requirements.

| Supplied mechanism | Disposition |
| --- | --- |
| WorkflowTransitionError / _reject | Adapted into pointer-bearing error, as_dict and safe require |
| _canonical_json / _compact | Consolidated into canonical UTF-8 bytes plus LF, preceded by strict JSON-native checks |
| _strict_object | Adapted to reject duplicate keys without echoing key/payload content |
| _Parser.error | Adapted to stable USAGE_ERROR output |
| _InputError, _UsageError, _emit_error | Replaced by common error envelope and explicit exit mapping; obsolete top-level ok removed |
| Historical handlers, F0/F1 tables and old validator dependency | Not imported; obsolete for the approved protocol |

Worker generality lives in `tests/unit/test_workflow_transition_generality.py`
and its owned support module. Multiple independent synthetic identities,
lane orders and SHAs exercise Python and complete CLI paths, bounded precedence,
source preservation, strict JSON/schema behavior and prohibited external
operations. This scope excludes owner functional tests, unrelated existing unit
inventory, S32DS/E2E and KPI. Worker tests are not Tester acceptance or Reviewer
approval.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.1.0 | Documented memory-only API, wire, lifecycle, evidence, errors, CLI, trust limits and salvage. |
| 2026-09-06 | 0.1.1 | Clarified historical rerun identity reuse as priority-3 STALE_EVENT with its offending field pointer. |
| 2026-09-07 | 0.1.2 | Explained applicable progression predicates, current-K prerequisite eligibility and replacement preservation without changing error priority. |
| 2026-09-07 | 0.1.3 | Documented Human decision field preservation, explicit nullable subjects and independently active subject identity precedence. |
| 2026-09-09 | 0.1.4 | Documented explicit W3 repair compatibility, immutable approval anchors, orthogonal support registration, same-index invalid-execution recovery and retained counted Implementation failures. |
| 2026-09-09 | 0.1.5 | Exposed pure current-state validation for the separate read-only evidence verifier. |
| 2026-09-10 | 0.1.6 | Documented W4 lessons Tip and L-bound PR/FINAL identity without changing C, correction/review accounting or the pure reducer's no-I/O boundary. |
