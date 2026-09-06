---
name: agent-workflow
description: Validate structured role handoffs and exact identities for the functional development profile, with explicit legacy compatibility and separate passive monitoring.
---

# Agent Workflow

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-09-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Structured role handoff guidance, declarative lifecycle boundaries, legacy compatibility and passive monitoring. |

Use this Skill for work governed by
`agent-discipline/workflow-contract.json`. Pin W from Governor G; do not infer
it from the current HEAD. W v2 is a small closed declaration referencing the
single artifact schema and registry. The registry owns roles, visibility,
named checkpoints and local predecessors; do not copy those domains into
another route list. No validator is a transition executor.

Before creating or consuming a role artifact, read
[Structured Handoffs](references/structured-handoffs.md), then the applicable
schema variant and registry entry. The schema is the member/type authority;
the reference explains the shared protocol and limitations. Role prompts
locate the checked Envelope/K, expected digests, trusted context, declared output
and applicable rules. They must not hide extra task requirements or owner Test
hints in prose.

Human-commanded manual bootstrap remains bounded by its explicit authorization.
A passing checker does not authorize dispatch, Candidate assembly, acceptance,
remote writes, deployment or progression.

## Functional lifecycle

- Test and Implementation lanes start independently from G with the same
  complete public K. Tester owns owner-Test authoring, requirement-driven Impact
  Set selection and applicable RED/full-chain/known-good/known-bad prevalidation;
  Worker owns TDD and generality tests, without access to owner Test.
- Human Gate 1 reviews exact Test T as soon as Test is READY, without waiting
  for Worker READY. Worker does not wait for Gate 1 to implement. Approval
  freezes T, its manifest and Impact Set; do not expand the scoped functional
  gate in response to a Candidate.
- C0 binds approved T and I0, their manifests and checked coverage join. Valid
  Implementation failures permit three incremental corrections (C1..C3), using
  the same Worker lane/session/worktree/branch and strict Implementation
  ancestry. Invalid runs rerun the same Candidate with a new execution identity.
  Delivery repair changes format/evidence references only, not source or counts.
- The Tester sends its full report only to the Orchestrator. Worker receives
  disclosure-reviewed public diagnoses with actionable production locations and
  public requirement/rule references. Consumer-local validation must not open
  confidential predecessor paths; bind the supplied safe central CHECKED result.
- Reach one terminal Reviewer on success or failure; do not use review as
  another correction cycle. Success requires Tester PASS plus Reviewer APPROVED.
  The success PR head is the exact accepted Candidate including Test and
  Implementation; lessons and review artifacts stay outside that head.
  Failure preserves the latest Implementation and does not become a success PR.
- Unknowns first become observations with one bounded diagnostic. Preserve work,
  block only the affected operation and refer ambiguous responsibility to Human.
  KPI is separate later issue-driven post-merge work; it never enters this
  functional gate or automatically triggers Worker optimization.

These are operating rules, not proof of global exactly-once behavior. Remote
approvals, full direct-union verification, isolation and progression retain the
explicit compensating responsibilities listed in the protocol reference.

## Structured artifact validation

Use the existing guard entrypoint for the applicable registry checkpoint:

```console
python agent-discipline/skills/agent-workflow/scripts/handoff_guard.py validate-artifact --artifact <artifact.json> --expected-sha256 <digest> --context <trusted-context.json> --view <orchestrator-full|consumer-local> --result <safe-result.json>
```

CHECKED authorizes consumption of the same bytes; it is not functional PASS,
remote authorization or semantic certification. Preserve rejected originals and
guard results. A replacement uses a new artifact identity and path, retaining
the dispatch and business identities required by the protocol.

## Deterministic command guard

Use the guard for deterministic commands only, not a whole Agent session.
`command_timeout_seconds` is the canonical semantic name for a child-command
deadline. Prefer `--command-timeout-seconds`; `--timeout-seconds` remains the v1
CLI alias. Supply exactly one. The v1 manifest/receipt/event wire member stays
`timeout_seconds`, with the same positive-integer value and digest behavior.
Do not rename frozen v1 fields. Both spellings retain `TIMED_OUT` / exit 124.

Invoke all three operations in order with the same manifest, receipt and log:

```console
python agent-discipline/skills/agent-workflow/scripts/handoff_guard.py prepare --role <role> --expected-top-level <canonical-worktree> --base-sha <sha> --lane-sha <sha> --contract-path <relative-path> --contract-blob-sha <sha> --manifest <manifest.json> --receipt <receipt.json> --event-log <events.jsonl> --command-timeout-seconds <seconds> -- <explicit-argv>
python agent-discipline/skills/agent-workflow/scripts/handoff_guard.py check-handoff --manifest <manifest.json> --receipt <receipt.json> --event-log <events.jsonl>
python agent-discipline/skills/agent-workflow/scripts/handoff_guard.py run --manifest <manifest.json> --receipt <receipt.json> --event-log <events.jsonl>
```

`prepare` pins canonical worktree, HEAD, contract blob, role and argv; the
base SHA names an ancestor commit of HEAD. Both later operations require the
prior receipt's manifest digest to match the raw manifest bytes. `run` also
requires that receipt to be the immediately preceding successful CHECKED event
and equal the event-log tail, then rechecks identity and executes the pinned
argv. PREPARED, REJECTED, EXITED and TIMED_OUT cannot authorize a run; check again
before rerunning. Each invocation replaces the receipt and adds one event to
the append-only event log. Preserve both as evidence.

The guard checks identity; it does not inspect dirty status. Execution uses
exact argv without a shell, so `.cmd` and `.bat` require an explicit interpreter
such as `cmd.exe /d /c`. Operational observations do not imply semantic classification.
This sequence does not implement cross-process locking or global exactly-once
command consumption.

## Explicit compatibility

The #90 interface packet remains available through its original adapter:

```console
python agent-discipline/skills/agent-workflow/scripts/interface_handoff_check.py validate --packet <packet.json> --expected-sha256 <digest>
python agent-discipline/skills/agent-workflow/scripts/handoff_guard.py validate-interface --packet <packet.json> --expected-sha256 <digest>
```

Both use one internal implementation and preserve v1 packet/digest semantics.
They check interface completeness and identity, not hidden owner Test or
natural-language semantic completeness. New role artifacts use
`validate-artifact`, not a fabricated legacy packet.

Validate the active declaration without any workflow record:

```console
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py validate-contract --contract agent-discipline/workflow-contract.json
```

For explicitly legacy records, use the exact v1 snapshot:

```console
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py validate --contract agent-discipline/contracts/workflow-v1.json --record <legacy-record.json>
```

`validate-record` is an alias of `validate`. The importable `load_contract`
and `validate_contract` accept explicit v1 or v2 paths. Legacy record and
lane-manifest functions retain their v1 fields and digest interpretation; they
explicitly reject v2 with guidance to use `validate-artifact`. Unsupported
versions never silently fall back. Contract-only validation checks the closed
declaration, not asset file existence, workflow progression or acceptance.
Exit 0 means the requested validation passed, 1 means invalid evidence/contract,
and 2 means unreadable or undecodable command input.

## Agent monitoring (separate runtime observations)

For live Agent supervision, read [the monitoring contract](references/agent-monitoring.md).
The Orchestrator owns dynamic estimates, passive observation, communication, and
explicit termination. Monitor records never assign workflow findings/verdicts,
consume correction budget, change `G/K/T/I/C`, or authorize the next stage.
Validate their closed shape with:

```console
python agent-discipline/skills/agent-workflow/scripts/agent_monitor.py validate --plan <monitor-plan.json> --events <monitor-events.jsonl>
```

This read-only command checks records; it does not schedule, wait, contact, or
interrupt an Agent. In a Human-commanded manual bootstrap, retain that execution
boundary even when a record says `CONTINUE`. Role dispatch IDs join the existing
task_run/dispatch monitoring identity. Estimates and observations remain outside
K and accepted source; an explicitly authorized resumed dispatch can retain its
lane/session/Implementation identity.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.2.0 | Migrated active guidance to W v2 structured handoffs, parallel readiness, frozen scoped functional checks and terminal review; documented explicit v1 compatibility and retained #95 monitoring. |
