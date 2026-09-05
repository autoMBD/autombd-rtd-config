# Agent Monitoring Contract

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-05 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Passive Agent monitoring records, explicit supervision decisions, and deterministic command timeout compatibility. |

## Responsibility and storage

The Orchestrator estimates duration and the next observation point using task
scope, expected commands, dependencies, comparable work, recent progress, and
remaining work. Estimates may increase or decrease; no global duration or KPI
multiplier limits an Agent task. Prefer the harness's existing item/tool/status
events. At an observation point, assess the evidence and contact the same Agent
when more context is needed.

Store each dispatch's mutable plan and append-only observations in ignored
runtime state:

```text
.agent-state/agent-monitoring/<task-run>/<dispatch-id>/monitor-plan.json
.agent-state/agent-monitoring/<task-run>/<dispatch-id>/monitor-events.jsonl
```

The committed validator defines the closed v1 field sets. Each JSONL line is one
complete event; an empty log is valid before the first observation. Unknown
fields and duplicate JSON members are rejected. No record contains workflow
verdicts, correction counts, or contract epochs. Plan estimate revisions leave
the dispatch identity and previous events intact and do not change G/K/T/I/C.

The validator reads records only. It does not wait, launch processes, contact
Agents, terminate tasks, mutate source/evidence, or advance the workflow. A
validated record does not authenticate its author or prove a rationale true;
the Orchestrator remains responsible for those judgments.

## Plan v1

All fields below are required. Text must be nonblank; numeric seconds must be
finite, positive JSON numbers (booleans are not numbers). Identity fields are
stable for the dispatch. Only estimates, their basis, the observation interval,
and newly available Agent/session identifiers are revised.

| Member | Value |
| --- | --- |
| schema_version | Integer 1 |
| task_run, dispatch_id | Nonblank identities, matching every event |
| role, lane_ref | Nonblank role and branch/ref identity |
| worktree | Absolute path to the dispatch worktree |
| harness_adapter | Nonblank harness name; no universal adapter API is implied |
| agent_id, session_id | Nonblank string when known; otherwise null |
| estimated_duration_seconds | Revisable estimate; no expiry action |
| estimate_basis | Nonblank explanation for this task's estimate |
| first_observation_after_seconds | Initial observation interval, not a deadline |
| automatic_timeout | Literal false |
| created_at_utc | ISO timestamp ending Z; retained across revisions |
| owner | Literal orchestrator |

## Event v1

All fields are required. Observations carry the same task/dispatch identities as
the plan; sequences are consecutive integers starting at 1. UTC timestamps
ending Z must not precede plan creation or the previous event. No comparison
against the current clock or estimated duration is performed.

| Member | Value |
| --- | --- |
| task_run, dispatch_id | Exact plan identities |
| sequence, observed_at_utc | Sequence and UTC observation timestamp |
| signal_source | harness_event, wait_snapshot, agent_status, human, platform |
| signal_kind | progress, observation_end, agent_status, completed, human_stop, transport_interruption, tool_interruption, platform_interruption |
| progress_since_previous | Nonblank account; explicitly say no observed progress if none |
| current_operation | Nonblank operation/status description |
| blocker | Nonblank description or null |
| last_evidence_locator | Nonblank raw evidence locator or null when unavailable |
| revised_remaining_seconds | Nonnegative finite number; revisable estimate |
| actor | orchestrator or human |
| decision | CONTINUE, CONTACT, INTERVENE, TERMINATE |
| next_observation_after_seconds | Positive finite number for ongoing work; null after termination or natural completion |
| rationale | Nonblank justification for the explicit decision |
| termination_reason | null except for TERMINATE |

### Decisions and harness boundary

- CONTINUE: meaningful progress supports further waiting; revise remaining time
  and the next observation interval. An estimate overrun alone cannot fail,
  stop, rebase, or restart the task.
- CONTACT: ask the same Agent for current operation, completed work, blockers,
  evidence, and an updated estimate. A wait/yield result is the end of an
  observation window, not task termination.
- INTERVENE: resolve a scoped permission/environment/context problem or pause
  the affected operation. Preserve other completed work.
- TERMINATE: record one of `human_stop`, `unrecoverable_agent`,
  `integrity_safety`, or `unrecoverable_mandatory_operation`, supported by the
  rationale and available raw evidence. Then explicitly invoke the harness
  interruption mechanism and record its result outside this read-only checker.
  A human_stop reason requires source=human and kind=human_stop. The event
  closes this monitor history and sets the next observation to null. Never
  classify mere elapsed time as an unrecoverable condition.

Natural completion uses kind=completed, decision=CONTINUE, remaining=0, and
next observation=null. Here CONTINUE acknowledges natural completion; it neither
interrupts the Agent nor dispatches another step. No further observations are
appended after completion/termination of this dispatch. A later explicitly
authorized resumption uses a new dispatch ID bound to the preserved Agent,
session, worktree, and source where reusable; this does not reset correction
accounting or imply a new contract epoch.

Transport/provider interruption, tool timeout, or platform usage/rate/context
limits are observations, not implementation verdicts. Preserve source and raw
evidence, assess side effects before any retry, and use the same lane/session
when continuation is possible. Only explicit Human/Orchestrator decisions
actively stop a task; the platform can still interrupt it independently.
Monitoring does not override task authorization or manual-bootstrap boundaries.

## Validation

```console
python agent-discipline/skills/agent-workflow/scripts/agent_monitor.py validate --plan <monitor-plan.json> --events <monitor-events.jsonl>
```

Exit 0 returns `{"valid": true, "events": N}`. Exit 1 reports
`MONITOR_RECORD_INVALID` for shape/binding/policy violations. Exit 2 reports
`MONITOR_INPUT_ERROR` for unreadable or malformed JSON, duplicate members, or
non-finite JSON constants. These are monitor-local errors, not workflow findings.

The focused tests construct independent records for prolonged progress, revised
estimates, natural completion, explicit termination, interruption handling,
identity/order errors, and rejected automatic decisions. They do not wait out
real Agent durations or simulate acceptance verdicts.

## Command timeout compatibility

`command_timeout_seconds` names the deterministic child-command deadline.
The #88 guard accepts exactly one of `--command-timeout-seconds` (preferred)
or `--timeout-seconds` (v1 alias). Both write the unchanged v1
`timeout_seconds` manifest/receipt/event member. Existing frozen bytes remain
readable and their digest meaning is unchanged; no automatic wire migration
occurs. Values remain positive integers supplied explicitly, with
`TIMED_OUT` / exit 124 retained. Conflicting aliases are a CLI error.

Use the guard to bound deterministic setup/check commands. Do not use its
blocking child-command runner for an entire Agent session. The current
black-box E2E harness still applies a fixed Agent timeout; #98 owns its adapter
replacement. #95 does not alter that harness or claim its lifecycle is dynamic.
Product/runtime defaults and script/CI deadlines remain #96/#97 work.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-05 | 0.1.0 | Defined closed passive monitor records, explicit decisions, input validation, and unchanged v1 command timeout compatibility. |

