# Pure Workflow Transitions

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Public memory-only transition API, wire, lifecycle, error order and evidence boundary. |

## Purpose and ownership

The transition core consumes current structured functional-development
artifacts. It adds global consumption order, active identity, replay rejection,
parallel readiness, frozen approval, bounded incremental corrections and one
terminal review. It does not execute the workflow.

The [structured handoff protocol](structured-handoffs.md), artifact schema,
profile registry and Wv2 declaration remain unchanged. The legacy
record/path/validate commands and file guard retain their ownership.
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
| Test decision | REQUEST_CHANGES clears Test READY; APPROVE freezes exact Test/K without waiting for Worker |
| New Candidate | Joins approved current Test with latest READY I; later C requires next completed I |
| Tester result | PASS enables review; Implementation failure enables correction; explicit invalid gate/contract/integrity enables failure review |
| INVALID_RUN rerun | New execution/dispatch for identical Candidate; rerun_of is active INVALID_RUN report, with it and prior envelope as direct predecessors |
| Correction | One pending authorization, same lane/session/worktree/branch and previous I |
| Corrected READY | Advances I once and clears pending; NOT_READY preserves pending and previous I |
| Pre-approval K revision | Increments K, preserves source/history and clears ACKs; revised launches preserve lane, both K_ACKs precede new-K READY |
| FINAL/STOP | Preserves latest I, Candidate and pending work, enables truthful failure finalization |
| Reviewer launch/report | One logical terminal review on success or failure; STOP after launch retains it |
| Success proposal | Requires Tester PASS and Reviewer APPROVED; does not mean merged |
| FINAL decision | Binds exact proposal/Candidate; REQUEST_CHANGES cancels success without reopening corrections |
| MERGED / RECORD_FAILURE | Requires corresponding exact final route and closes business progression |
| Delivery repair | Orthogonal bookkeeping; replacements preserve business values and update only active delivery references |

There is no correction four, clean-room restart, automatic invalid-Test
reclassification, second review cycle or KPI retry. Candidate indices are 0–3.
New READY I may temporarily be one increment ahead of current C; STOP preserves
both actual facts.

Reruns retain Candidate, Test/Implementation tips, manifests, Impact Set,
coverage join and indices. Execution and dispatch identities cannot be reused.
Stale former-execution results cannot become the current result.

For an already consumed repaired report, replacement does not reapply the
business transition. Historical bytes remain unchanged. A repaired Reviewer
delivery can update the current report while a prior accepted proposal retains
its reference to the equivalent original delivery.

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
LocalRules.

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
