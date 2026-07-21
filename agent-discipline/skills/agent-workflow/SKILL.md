---
name: agent-workflow
description: Classify repository work and execute the canonical test-first Agent loop with independent lanes, SHA-bound Human Review gates, bounded rework, and candidate-bound evidence.
---

# Agent Workflow

## Authority and scope

Use this Skill for every repository task that changes tracked content or records
acceptance evidence. The machine-readable authority is
`agent-discipline/workflow-contract.json`; validate records with
`scripts/workflow_gate.py`. This Skill explains execution. A repository profile
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
repository-profile checks; it does not select a different state machine.

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
common-workflow default Agent platform or third-party runner; the repository
profile or task handoff selects available tooling.

## 3. Execute the one state machine

```text
classify -> test_authoring -> human_review_gate_1 -> implementing
         -> candidate -> tester -> bounded rework -> reviewer
         -> final_human_review -> complete
```

`rework` returns through the implementation lane, creates a new candidate, and
then re-enters Tester. It is not a shortcut around either Human Review.

### Test path

The standard path is mandatory unless all lightweight conditions in the
contract apply. On the standard path, author the complete test revision before
implementation and obtain Human Review Gate 1 approval.

The lightweight no-test path is limited to `D` or `N` work whose only impact is
`DO`. Record non-empty `reason`, `residual_risk`, and
`remaining_verification`. It still produces a candidate, evidence, Reviewer
result, and final Human Review. If behavior, a test contract, Agent rules,
packaging, safety, runtime data, or tooling is affected, use the standard path.

## 4. Build independent lanes

Record full 40-hex `base_sha`, `test_sha`, `implementation_sha`, and
`candidate_sha` values. The test and implementation lanes both start from the
same exact base in independent checkouts/worktrees and produce independent
commits. Permissions, checkout, inputs, and evidence are separate boundaries.

The Worker must not receive or read the owner's acceptance-test implementation.
The candidate is a deterministic integration revision made from the test and
implementation revisions. A lane normally does not need a child ticket; create
one only for an independently deliverable objective.

Tester and Reviewer operate on the same exact candidate SHA. Chat history,
summaries, or Agent claims are not evidence. Production rework updates only the
implementation lane and regenerates candidate. The former candidate and all
evidence bound to it immediately become stale.

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
/request-test-changes <full-test-sha> <reason>
```

Replies, reactions, labels, Agent-authored commands, abbreviated or stale SHAs,
and edited or deleted approvals are invalid. A new Test SHA invalidates every
earlier approval. Evidence records the comment ID and URL, author login,
creation time, unedited/undeleted state, exact command, and bound SHA.

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

The focused-validation 3-minute and E2E-validation 5-minute values are
convergence checkpoints, not hard timeouts. A validation run may continue up to
10 minutes to collect useful evidence before Orchestrator intervention. These
times apply only to validation execution; test authoring, implementation,
exploration, and review use task-specific handoff budgets.

Production rework and KPI optimization each permit at most three automatic
iterations. On reaching the applicable limit, stop the automatic loop and
escalate for a human decision. Never reset a counter by renaming a lane or
creating a fresh session.

## 7. Candidate evidence and final Human Review

Tester evidence includes its verdict and exact candidate SHA. Reviewer entry
requires `PASS` on that SHA. Reviewer evidence also binds that same SHA. Any
candidate change invalidates both.

Before `complete`, obtain a final authorized-human top-level issue comment bound
to the exact candidate:

```text
/approve-candidate <full-candidate-sha>
```

Record the comment evidence and stopped same-session monitor exactly as for
Gate 1. Only then may the record enter `complete`.

## Minimal execution template

Keep the active record in ignored local task state. Replace every placeholder
with real evidence; do not treat the template itself as evidence.

```json
{
  "contract_version": "1.0.0",
  "task_type": "I",
  "impact_flags": ["AR", "TC"],
  "state": "candidate",
  "test_path": "standard",
  "base_sha": "<40-hex-base>",
  "test_base_sha": "<same-40-hex-base>",
  "test_sha": "<40-hex-test>",
  "implementation_base_sha": "<same-40-hex-base>",
  "implementation_sha": "<40-hex-implementation>",
  "candidate_sha": "<40-hex-candidate>",
  "test_approval": {
    "sha": "<40-hex-test>",
    "command": "/approve-test <40-hex-test>",
    "location": "github_issue_top_level_comment",
    "author_type": "human",
    "comment_id": "<github-comment-id>",
    "comment_url": "<github-comment-url>",
    "author_login": "<human-login>",
    "created_at": "<timestamp>",
    "edited": false,
    "deleted": false
  },
  "monitors": {
    "test_review": {
      "window_minutes": 10,
      "same_session": true,
      "new_session": false,
      "status": "stopped",
      "valid_update_received": true
    }
  },
  "production_rework_count": 0,
  "kpi_optimization_count": 0
}
```

Validate after every state or SHA change:

```text
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py <record.json>
```

An empty error list with exit code 0 means the recorded transition satisfies
the common contract. Repository-profile gates and actual test/review results
remain independently mandatory.
