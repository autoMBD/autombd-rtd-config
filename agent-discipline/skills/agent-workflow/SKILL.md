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
`impact_routing` table derives `gate.required_gates`, `gate.profiles`, and
`gate.test_required`; callers may not self-declare a weaker gate. Only exact
`N + DO` derives the lightweight path.

## 2. Complete initialization and preflight before lanes

- A first clone may collect initialization inputs interactively before work
  begins.
- A derived checkout or worktree reuses verified, non-secret initialization
  inputs and the local dependency cache, then runs the deterministic deployer in
  non-interactive hydration mode.
- Missing, expired, or unusable initialization input is a fail-fast condition
  before lane creation. Never prompt for it from inside a lane.
- Preflight every external tool before the loop. Record host authentication and
  Agent sandbox/network reachability as separate facts; one does not prove the
  other.
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

testing --functional_failure--> rework --production_rework--> implementing
rework  --rework_cap_reached---------------------------------> stopped
human_review_1 --changes_requested------------------------> test_authoring
```

The exact legal edges and events are `state_machine.transitions`. A record's
`transition.from`, `transition.to`, and `transition.event` must name one edge;
the target must equal the record's `state`. `rework` returns through the
implementation lane, creates a new candidate, and then re-enters Tester. A
Gate 1 change request instead creates the next `Tn` in `test_authoring` and does
not consume production rework. `complete` and `stopped` are terminal.

Evidence is state-dependent. A state requires only evidence already produced
at that point; future Tester, Reviewer, Final Review, Candidate, or evidence-only
revision data is invalid rather than silently accepted.

### Test path

The standard path is mandatory unless all lightweight conditions in the
contract apply. On the standard path, author the complete test revision before
implementation and obtain Human Review Gate 1 approval.

The lightweight no-test path is limited to `N` work whose only impact is `DO`.
Record non-empty `reason`, `residual_risk`, and a non-empty list of
`remaining_verification` actions. It still produces a candidate, evidence,
Reviewer result, and final Human Review. If behavior, a test contract, Agent
rules, packaging, safety, runtime data, or tooling is affected, use the standard
path.

## 4. Build independent lanes

Model each revision explicitly: `Tn` for Test, `Wn` for Implementation, and
`Cn` for Candidate. Record full 40-hex SHAs. Test and Implementation both start
from `revisions.base_sha` in independent checkouts/worktrees and produce
independent commits. Candidate records the exact `Tn`/`Wn`, their exact parent
SHAs, and its tree SHA. Permissions, checkout, inputs, and evidence are separate
boundaries.

The Worker must not receive or read the owner's acceptance-test implementation.
The candidate is a deterministic integration revision made from the test and
implementation revisions. A lane normally does not need a child ticket; create
one only for an independently deliverable objective.

Tester and Reviewer operate on the same exact candidate SHA. Chat history,
summaries, or Agent claims are not evidence. Production rework updates only the
implementation lane and regenerates Candidate. The former Candidate and all
Tester, Reviewer, or Human Review evidence bound to it immediately become stale.

After an exact Candidate, one `evidence_only` revision may carry only paths in
`revision_provenance.evidence_only.allowed_paths`. Its parent and
`base_candidate_sha` must equal that Candidate. A production, workflow-contract,
or Test-contract path can never masquerade as evidence-only. Final Human Review
binds the evidence revision when present; Tester and Reviewer remain bound to
the exact Candidate they evaluated.

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

Replies, reactions, labels, Agent-authored commands, abbreviated or stale SHAs,
and edited or deleted approvals are invalid. A new Test SHA invalidates every
earlier approval. The record binds the approval to the GitHub repository, issue
number, top-level comment ID, authorized human reviewer, exact command, and
current full Test SHA.

After submitting any Human Review request, poll for 10 minutes in the current
conversation/session. No update is a no-op. On a valid update, stop the monitor
before continuing. Do not create a new session for polling. Apply the same
monitor rule to final Human Review.

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

`corrections.production_rework`, `dependency_permission`, and `test_contract`
are separate audit classes. Only the exact `rework -> implementing` transition
increments production rework. Dependency/permission corrections and Gate 1
Test-contract changes carry their own counts and audit entries and never consume
that cap. Production rework and KPI optimization each permit at most three
automatic iterations. The third attempt may execute; a subsequent functional
failure must enter `stopped` with `stop_escalate`. Never reset a counter by
renaming a lane or creating a fresh session.

## 7. Candidate evidence and final Human Review

Tester evidence includes its verdict and exact candidate SHA. Reviewer entry
requires `PASS` on that SHA. Reviewer evidence also binds that same SHA. Any
candidate change invalidates both.

Before `complete`, obtain an authorized-human GitHub PR review whose current
state is `APPROVED`, bound to the exact Candidate SHA or its allowed
evidence-only child. Record repository, PR number, review ID, actor,
authorization, exact revision, non-dismissed/non-stale state, human reviewer,
and a stopped 10-minute current-session monitor. Only then may the record enter
`complete`.

## 8. Role handoffs

Use `handoff_templates` in the machine-readable contract for Orchestrator,
Explorer, Worker, Tester, and Reviewer. Every handoff supplies the five compact
sections `inputs`, `forbidden`, `outputs`, `stop_conditions`, and `acceptance`.
The entries are JSON-pointer-style references to canonical workflow fields; do
not copy and reinterpret transition, revision, gate, counter, or evidence
authority in a role-specific prompt.

## Minimal execution template

Keep the active record in ignored local task state. Replace every placeholder
with real evidence; do not treat the template itself as evidence.

```json
{
  "version": 1,
  "issue": {
    "number": 123,
    "repository": "<owner/repository>",
    "primary_type": "I",
    "impact_flags": ["AR", "TC"]
  },
  "state": "complete",
  "transition": {
    "from": "final_human_review",
    "to": "complete",
    "event": "final_approved"
  },
  "gate": {
    "test_required": true,
    "light_path": null,
    "required_gates": [
      "deterministic_tests",
      "test_contract_review",
      "workflow_contract"
    ],
    "profiles": ["agent_rules", "test_contract"]
  },
  "revisions": {
    "base_sha": "<40-hex-base>",
    "test": {
      "id": "T1",
      "sha": "<40-hex-test>",
      "base_sha": "<40-hex-base>"
    },
    "implementation": {
      "id": "W1",
      "sha": "<40-hex-implementation>",
      "base_sha": "<40-hex-base>"
    },
    "candidate": {
      "id": "C1",
      "sha": "<40-hex-candidate>",
      "test_revision": "T1",
      "implementation_revision": "W1",
      "parents": ["<40-hex-implementation>", "<40-hex-test>"],
      "tree_sha": "<40-hex-tree>"
    },
    "evidence": null
  },
  "human_reviews": {
    "test": {
      "decision": "approved",
      "approved": true,
      "sha": "<40-hex-test>",
      "reviewer": "<human-login>",
      "evidence": {
        "provider": "github",
        "repository": "<owner/repository>",
        "artifact": "issue_comment",
        "issue_number": 123,
        "comment_id": 456,
        "top_level": true,
        "actor": "<human-login>",
        "authorized_actor": true,
        "revision_sha": "<40-hex-test>",
        "command": "/approve-test <40-hex-test>",
        "edited": false,
        "deleted": false,
        "request_changes": false
      },
      "monitor": {
        "status": "stopped",
        "interval_minutes": 10,
        "scope": "current_session"
      }
    },
    "final": {
      "decision": "approved",
      "approved": true,
      "sha": "<40-hex-candidate>",
      "reviewer": "<human-login>",
      "evidence": {
        "provider": "github",
        "repository": "<owner/repository>",
        "artifact": "pull_request_review",
        "pull_request_number": 789,
        "review_id": 1011,
        "actor": "<human-login>",
        "authorized_actor": true,
        "revision_sha": "<40-hex-candidate>",
        "state": "APPROVED",
        "dismissed": false,
        "stale": false
      },
      "monitor": {
        "status": "stopped",
        "interval_minutes": 10,
        "scope": "current_session"
      }
    }
  },
  "corrections": {
    "production_rework": {"count": 0, "disposition": "continue"},
    "dependency_permission": {"count": 0, "audit": []},
    "test_contract": {"count": 0, "audit": []},
    "kpi_optimization": {"count": 0, "disposition": "continue"}
  },
  "tester": {
    "status": "pass",
    "candidate_sha": "<40-hex-candidate>"
  },
  "reviewer": {
    "status": "pass",
    "candidate_sha": "<40-hex-candidate>"
  },
  "stop": null,
  "exception": null
}
```

Validate after every state or SHA change:

```text
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py <record.json>
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py \
  --previous <previous-record.json> <current-record.json>
```

An empty error list with exit code 0 means the recorded transition satisfies
the common contract. Repository-profile gates and actual test/review results
remain independently mandatory.
