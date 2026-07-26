---
name: agent-workflow
description: Classify repository work and execute the canonical test-first Agent loop with independent lanes, SHA-bound Human Review gates, bounded rework, and candidate-bound evidence.
---

# Agent Workflow

## Authority and scope

Use this Skill for every repository task that changes tracked content or records
acceptance evidence. The machine-readable authority is
`agent-discipline/workflow-contract.json`; validate records with
`scripts/workflow_gate.py`. This Skill is platform-neutral and explains
execution. A repository profile
such as `AGENTS.md` may add domain and ownership constraints, but must not
redefine the common state machine, gates, lanes, limits, or evidence rules.

## 1. Classify once

Choose exactly one task type and every applicable impact flag from the canonical
contract:

| Type | Meaning |
| --- | --- |
| `M` | module capability |
| `B` | bug |
| `W` | workflow or discipline |
| `T` | tests or validation |
| `D` | specifications or documentation |
| `N` | mechanical maintenance |
| `I` | infrastructure or tooling |

| Flag | Impact | Flag | Impact |
| --- | --- | --- | --- |
| `PB` | public behavior | `MS` | module surface |
| `MW` | MEX write path | `RA` | runtime asset |
| `TC` | test contract | `VS` | vendor/S32DS validation |
| `EV` | black-box E2E | `AR` | Agent rules |
| `RP` | release/package | `ED` | external dependency |
| `SS` | security/safety | `DO` | documentation only |

All seven types use the same workflow. Classification selects additional
repository-profile checks; it does not select a different state machine. The
`impact_routing` derives the required gates and profiles, while the
classification determines `gate.test_required`; callers may not self-declare a
weaker gate. Only exact `N + DO` derives the lightweight path.

## 2. Complete initialization and preflight before lanes

- A first clone may collect initialization inputs interactively before work
  begins.
- A derived checkout or worktree reuses verified, non-secret initialization
  inputs and the local dependency cache, then runs the deterministic deployer in
  non-interactive hydration mode.
- Missing, expired, or unusable initialization input is a fail-fast condition
  before lane creation. Never prompt for it from inside a lane.
- Preflight every external tool before the loop. Record host authentication and
  Agent sandbox/network reachability as separate `host` and `sandbox` facts;
  each needs an `available: true` result and non-empty evidence, because one
  does not prove the other.
- Record `required_capabilities` and `granted_capabilities`; every required
  capability must be granted. The preflight object is optional in a workflow
  record, but when present it is fail-closed; both capability lists may be
  empty. Record deterministic derived-worktree hydration as
  `{"mode": "noninteractive", "source": "verified_non_secret_inputs"}`.
- Pre-authorize the smallest stable command prefixes practical. An executing
  lane must not pause waiting for a chat permission approval.

For GitHub, use the current Agent platform's built-in GitHub Connector first.
Use `gh` only when that platform has no built-in Connector. Do not choose a
common-workflow default Agent platform or third-party runner. The current Agent
platform capabilities and the task handoff must explicitly select the
independent runner used for a validation execution.

## 3. Execute the one state machine

```text
classify -> test_authoring -> human_review_1 -> implementing
         -> candidate -> testing -> reviewing
         -> final_human_review -> complete

classify -> implementing -> candidate
         -> testing(mechanical_verification) -> reviewing
         -> final_human_review -> complete                 [N + DO only]

testing --tester_failed--> rework --production_rework--> implementing
rework  --production_rework---------------------------------> stopped
human_review_1 --changes_requested------------------------> test_authoring
human_review_1 --review_poll_no_change--------------------> human_review_1
testing --kpi_optimization-------------------------------> implementing
final_human_review --changes_requested-------------------> reviewing
reviewing --review_correction----------------------------> rework
```

The exact legal edges and events are `state_machine.transitions`. Validate an
edge by passing the previous record, current record, and event to
`validate_transition`. `rework` returns through the implementation lane,
creates `W(n+1)`, clears the old Candidate, creates the next Candidate only on
`candidate_created`, and then re-enters Tester. Reviewer corrections enter
`rework` directly. Final Human Review
corrections first return to `reviewing`, then enter `rework`; neither routing
edge increments the counter. Only the following `production_rework` edge
increments it. There is no direct Candidate-to-Tester revision bypass. A Gate 1 change request
instead creates the next `Tn` in `test_authoring` and does not consume
production rework. A functional PASS with KPI MISS takes the executable
`kpi_optimization` edge, increments that counter exactly once, and similarly
starts `W(n+1)` with no Candidate. Dependency and permission blocks preserve
revisions and counters. `complete` and `stopped` are terminal.

Evidence is state-dependent. A state requires only evidence already produced
at that point; future Tester, Reviewer, Final Review, Candidate, or evidence-only
revision data is invalid rather than silently accepted.
Reviewer evidence begins in `reviewing`, never `testing`. A
review correction invalidates Reviewer and Final Human Review evidence before
the counted rework cycle. KPI optimization invalidates the old Candidate's
Tester, Reviewer, and Final Human Review evidence. Final evidence is produced
only in `complete`.

Every event is governed by `transition_mutation_matrix`: top-level changes
outside that event's allowlist are invalid. Issue and gate authority and the
Base SHA are immutable after classification. `test_approved` freezes the exact
Test identity and SHA. `candidate_created` preserves the Implementation
identity while committing its SHA, creates the Candidate with the same numeric
iteration, and binds its exact parents. From `testing_started` onward, Test,
Implementation, and Candidate authority remain immutable until an explicit
production-rework or KPI-optimization edge invalidates the old Candidate.
Diagnostics name the authority field that changed or was rebound. Version 2 is
a closed schema at every nested record object, so unknown fields are rejected.
Revision identity and Candidate parent keys are defined only by
`revision_provenance`, using parent modes `normal` and `mechanical_light`.

### Test path

The standard path is mandatory unless all lightweight conditions in the
contract apply. On the standard path, author the complete test revision before
implementation and obtain Human Review Gate 1 approval.

The lightweight no-test path is limited to `N` work whose only impact is `DO`.
Record non-empty `reason`, `residual_risk`, and a non-empty list of
`remaining_verification` actions. It skips Test authoring and Human Review
Gate 1, forbids their revision/review evidence, and enters `implementing`
directly. Its Candidate parents are the exact Base and Implementation SHAs, and
Tester records `mode: mechanical_verification`. It still produces a candidate,
Reviewer result, and final Human Review. If behavior, a test contract, Agent
rules, packaging, safety, runtime data, or tooling is affected, use the standard
path.

## 4. Build independent lanes

Model each revision explicitly: `Tn` for Test, `Wn` for Implementation, and
`Cn` for Candidate. Store each identity and numeric iteration separately and
record full 40-hex SHAs. Test and Implementation both start from
`revisions.base_sha` in independent checkouts/worktrees and produce independent
commits. Candidate `parents.test_sha` and `parents.implementation_sha` bind
those exact revisions. The entire `revisions.candidate` key is forbidden while
state is `implementing`; a correction cannot keep an old Candidate or a null
placeholder bound. `candidate_created` introduces the new Candidate only when
moving from `implementing` to `candidate`, and its iteration must match the
Implementation iteration. Permissions, checkout, inputs, and evidence are
separate boundaries.

The Worker must not receive or read the owner's acceptance-test implementation.
The candidate is a deterministic integration revision made from the test and
implementation revisions. A lane normally does not need a child ticket; create
one only for an independently deliverable objective.

Tester and Reviewer operate on the same exact candidate SHA. Chat history,
summaries, or Agent claims are not evidence. Production rework updates only the
implementation lane and regenerates Candidate. The former Candidate and all
Tester, Reviewer, or Human Review evidence bound to it immediately become stale.

Only the `complete` record may carry `revisions.final_evidence`; its
`changed_paths` may contain only paths in
`revision_provenance.evidence_only.allowed_paths`. Its
`reviewed_candidate_sha` must equal that Candidate. A production,
workflow-contract, or Test-contract path can never masquerade as final evidence.
Tester, Reviewer, and Final Human Review remain bound to the exact Candidate
they evaluated.

## 5. Human Review Gate 1

Gate 1 binds the complete test revision, not a diff description or abbreviated
revision. The only approval is a GitHub top-level issue comment authored by an
authorized human with this exact command:

```text
/approve-test <full-test-sha>
```

A change request is a top-level human comment beginning with the following
command and followed by its reason:

```text
/request-test-changes <full-test-sha>
<reason>
```

The literal template is exactly two lines: `/request-test-changes {test_sha}`
followed by `{reason}`.

Before a decision, Gate 1 may record `approved: false`, a null reviewer and
evidence, and an active current-session monitor. Approval evidence requires a
stopped monitor. At the atomic change-request boundary, the previous Gate 1
record may still show an active monitor or may already show it stopped; the
current `test_authoring` record carries neither review nor monitor. A change
request has two equivalent encodings: `requested_changes: true` may stand alone
with the reason inferred from command line 2, or `decision: changes_requested`
and a matching `reason` may be used while `requested_changes` is false or absent.
Both require the exact two-line command. An approval is invalid if
`requested_changes` is true.

The outer Gate 1 `reviewer` identifies the approving human. Approval requires
that non-empty reviewer to exactly equal evidence `actor_login`. A pending
record keeps reviewer and evidence null. A change-request record also keeps
the reviewer explicitly null: its top-level human `actor_login` comes from the
command evidence and is not compared with that null reviewer. Top-level
`authorization` is optional; when supplied, approval and change-request actors
must appear in `authorization.github.authorized_human_logins`.
`issue.repository` is also optional; when supplied, it must exactly match the
evidence repository.

Replies, reactions, labels, Agent-authored commands, abbreviated or stale SHAs,
and edited or deleted approvals are invalid. A new Test SHA invalidates every
earlier approval. The record binds the approval to the GitHub repository, issue
number, top-level comment ID, authorized human reviewer, exact command, and
current full Test SHA.

Every newly created or replacement review gate starts with
`interval_minutes: 10`, automation tier `10m`, and count `0`. The automation
object contains only `id`, `tier`, `count`, and `session`; the ID is non-empty,
the session is `current_session`, and both remain unchanged while polling.

On `review_poll_no_change`, use exactly this progression:

```text
10m/0 -> 10m/1 -> 10m/2 -> 30m/0
30m/0 -> 30m/1 -> 30m/2 -> 60m/0
60m/0 -> 60m/0 indefinitely
```

`interval_minutes` must equal the tier (`10m`, `30m`, or `60m`). A no-update
event advances only the approved count/tier schedule. Do not encode a
timestamp, deadline, legacy timing field, or a new session. On a valid update,
stop the monitor before continuing. Apply the same initial/reset shape to
Final Human Review.

## 6. Roles, validation, and bounded rework

- Explorer is read-only.
- Worker owns production in the implementation lane and never receives owner
  acceptance-test implementation.
- Tester writes only tests and evidence; production failures return to Worker.
- Reviewer starts only after Tester PASS on the candidate, performs review
  without production fixes, and may write only an append to the lessons log.

Each focused-validation 3-minute or E2E-validation 5-minute target is a
convergence checkpoint, not a hard timeout. A validation run may continue up to
10 minutes to collect useful evidence before Orchestrator intervention. These
times apply only to validation execution; test authoring, implementation,
exploration, and review use task-specific handoff budgets.

Only the exact `rework -> implementing` production-rework transition increments
`counters.production_rework`. Dependency/permission blocks and Gate 1
Test-contract changes never consume that counter. Production rework and KPI
optimization each permit at most three automatic iterations. At count three,
the next production-rework disposition enters `stopped` with `stop_escalate`;
the counter never becomes four. KPI optimization supports iterations one
through three and rejects a fourth edge. Each successful KPI edge increments
exactly once and requires Candidate-bound Tester PASS with
`tester.kpi.status: miss`, positive elapsed/limit values where elapsed exceeds
the limit, and a positive edit-attempt count. Counter `n` is bound to Worker
iteration `W(n+1)`; after incrementing, the next Candidate has the same
iteration as that Worker. The edge invalidates the prior Candidate, Tester KPI,
Reviewer, Final Human Review, and final evidence before work resumes. Never
reset a counter by renaming a lane or creating a fresh session.

## 7. Candidate evidence and final Human Review

Tester evidence includes its verdict and exact candidate SHA. Reviewer entry
requires `PASS` on that SHA. Reviewer evidence also binds that same SHA. Any
candidate change invalidates both.

For `tester_passed`, the previous `testing` record remains pending and the
current `reviewing` record carries Tester PASS plus a pending Reviewer, all
bound to the unchanged Candidate SHA.

On entry to `final_human_review`, record the pending shape explicitly:
`approved: false`, the exact Candidate SHA, null reviewer, null evidence, and
an active current-session monitor reset to 10m/count0. Before `complete`,
obtain a current GitHub PR review made by a human whose state is `approved`,
bound to the exact Candidate SHA. Record repository, PR number, review ID,
exact actor login, Candidate SHA, and a stopped current-session monitor at
10 minutes with automation tier `10m`; counts valid for that tier remain
legal. The actor login must equal the outer reviewer. If top-level
authorization is supplied, the actor must be authorized by
`authorization.github.authorized_human_logins`. A Candidate SHA change, review
edit, dismissal, or requested change invalidates it. The `final_approved`
transition must preserve the exact Candidate revision object and add the
required allowlisted `revisions.final_evidence`. Only then may the record enter
`complete`.

## Handoff templates

### Orchestrator

- Inputs: issue classification, exact SHA graph, impact-derived gates, and human review evidence.
- Forbidden sources: unstated requirements, stale Candidate evidence, and owner acceptance-test implementation for Worker.
- Forbidden actions: weakening gates, merging lane ownership, or treating Agent claims as evidence.
- Outputs: self-contained role briefs, exact revision bindings, routing decisions, and final disposition.
- Stop conditions: missing authority, unusable dependencies, invalid human review, or exhausted production-rework count.
- Acceptance criteria: every required gate is routed, evidence binds the exact SHA, and terminal state is justified.

### Explorer

- Inputs: bounded investigation question, descriptor/reference locations, fixture, and dependency evidence.
- Forbidden sources: acceptance cases as specification and invented domain values.
- Forbidden actions: production writes, test edits, or crossing module ownership.
- Outputs: decision-ready ground truth with exact source evidence and unresolved constraints.
- Stop conditions: required reference is unavailable, contradictory, or outside the authorized scope.
- Acceptance criteria: read-only investigation is reproducible and every non-inferable fact is grounded.

### Worker

- Inputs: approved Test SHA when `test_required` is true, capability brief, implementation base SHA, grounded asset/descriptor facts, and ownership boundary.
- Forbidden sources: owner acceptance-test implementation and E2E case literals as specification.
- Forbidden actions: changing the frozen Test, guessing values, or repairing another provider's region.
- Outputs: implementation SHA, Worker-owned generality tests, exact dev-test result, and scoped diff evidence.
- Stop conditions: ambiguity, ungrounded value, cross-module ownership need, or missing dependency authority.
- Acceptance criteria: capability is implemented forward from its source and acceptance-test implementation remains unread.

### Tester

- Inputs: exact candidate SHA, frozen Test revision, fixtures, required profiles, and validation commands.
- Forbidden sources: Worker private reasoning or repository context in a black-box run.
- Forbidden actions: production repair, weakening a test, or changing the Candidate under test.
- Outputs: candidate-bound pass/fail verdict, deterministic/vendor/E2E evidence, and KPI measurement.
- Stop conditions: Candidate drift, environment invalidity, timeout intervention, or missing required gate.
- Acceptance criteria: all required evidence is fresh for the exact candidate SHA and production failures return to Worker.

### Reviewer

- Inputs: tester pass on the exact Candidate, scoped diff, contract, source truth, and coverage evidence.
- Forbidden sources: stale Tester evidence and unapproved Candidate revisions.
- Forbidden actions: production write, Test repair, or changing acceptance evidence; only lessons may be appended.
- Outputs: candidate-bound findings, disposition, and append-only lessons evidence.
- Stop conditions: Tester is not PASS, Candidate SHA changed, or a required source cannot be verified.
- Acceptance criteria: all non-test requirements are reviewed and any lessons path remains evidence-only.

## Minimal execution template

Keep the active record in ignored local task state. Replace every placeholder
with real evidence; do not treat the template itself as evidence.

```json
{
  "version": 2,
  "schema": "agent_workflow_v2",
  "issue": {
    "number": 123,
    "repository": "<owner/repository>",
    "primary_type": "I",
    "impact_flags": ["AR", "TC"]
  },
  "authorization": {
    "github": {"authorized_human_logins": ["<human-login>"]}
  },
  "state": "complete",
  "gate": {"test_required": true},
  "revisions": {
    "base_sha": "<40-hex-base>",
    "test": {
      "identity": "T1", "iteration": 1,
      "base_sha": "<40-hex-base>", "sha": "<40-hex-test>"
    },
    "implementation": {
      "identity": "W1", "iteration": 1,
      "base_sha": "<40-hex-base>", "sha": "<40-hex-implementation>"
    },
    "candidate": {
      "identity": "C1", "iteration": 1,
      "sha": "<40-hex-candidate>",
      "parents": {
        "test_sha": "<40-hex-test>",
        "implementation_sha": "<40-hex-implementation>"
      }
    },
    "final_evidence": {
      "identity": "E1", "sha": "<40-hex-evidence>",
      "reviewed_candidate_sha": "<40-hex-candidate>",
      "changed_paths": [
        "agent-discipline/agent-lessons-learned.md"
      ]
    }
  },
  "human_reviews": {
    "test": {
      "approved": true,
      "sha": "<40-hex-test>",
      "reviewer": "<human-login>",
      "evidence": {
        "provider": "github", "artifact": "issue_comment",
        "repository": "<owner/repository>", "issue_number": 123,
        "comment_id": 456,
        "command": "/approve-test <40-hex-test>",
        "top_level": true, "actor_type": "human",
        "actor_login": "<human-login>", "current": true,
        "edited": false, "deleted": false, "requested_changes": false
      },
      "monitor": {
        "status": "stopped", "interval_minutes": 10,
        "scope": "current_session",
        "automation": {
          "id": "<monitor-id>", "tier": "10m", "count": 0,
          "session": "current_session"
        }
      }
    },
    "final": {
      "approved": true,
      "sha": "<40-hex-candidate>",
      "reviewer": "<human-login>",
      "evidence": {
        "provider": "github", "artifact": "pull_request_review",
        "repository": "<owner/repository>", "pull_request_number": 789,
        "review_id": 1011, "actor_type": "human",
        "actor_login": "<human-login>", "state": "approved",
        "current": true, "candidate_sha": "<40-hex-candidate>"
      },
      "monitor": {
        "status": "stopped", "interval_minutes": 10,
        "scope": "current_session",
        "automation": {
          "id": "<monitor-id>", "tier": "10m", "count": 0,
          "session": "current_session"
        }
      }
    }
  },
  "counters": {"production_rework": 0, "kpi_optimization": 0},
  "permission_preflight": {
    "host": {"available": true, "fact": "github_authenticated"},
    "sandbox": {"available": true, "fact": "network_permitted"},
    "required_capabilities": ["read_issue", "read_review"],
    "granted_capabilities": ["read_issue", "read_review"],
    "hydration": {
      "mode": "noninteractive",
      "source": "verified_non_secret_inputs"
    }
  },
  "tester": {"status": "pass", "candidate_sha": "<40-hex-candidate>"},
  "reviewer": {"status": "pass", "candidate_sha": "<40-hex-candidate>"},
  "exception": null
}
```

Validate after every state or SHA change:

```text
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py --json <record.json>
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py --json <current.json> --previous <previous.json> --event <event>
```

An empty error list with exit code 0 means the recorded transition satisfies
the common contract. Repository-profile gates and actual test/review results
remain independently mandatory.
