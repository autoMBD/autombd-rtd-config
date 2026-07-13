---
name: interrupted-task-recovery
description: Checkpoint, heartbeat, resume, and stale-evidence protocol for long-running or unattended Agent tasks in this repository.
---

# Interrupted Task Recovery

## Purpose

Use this Skill to make long-running, unattended, quota-risk, or
compaction-risk Agent work resumable without losing scope, evidence, or
ownership boundaries. It is Category B Agent discipline. It does not change the
RTD CfgFile CLI runtime, the released `autombd-rtd/` Skill, black-box E2E
behavior, or any Category A project document under `docs/`.

## Entry Gate

The mandatory entry gate applies before starting or continuing any task that
meets at least one of these criteria:

- expected execution or investigation time is longer than 30 minutes;
- work may run unattended, including overnight or while the user is absent;
- a model quota, context window, session timeout, network retry, GUI wait, or
  long command may interrupt the session;
- the task depends on subagent handoffs, black-box E2E, S32DS validation, or a
  Reviewer gate whose evidence could become stale before completion;
- the task is explicitly marked long-running, unattended, quota-risk, or
  compaction-risk by the user, the orchestrator, or a role brief.

The skip criteria are intentionally narrow. The Skill may be skipped only when
all of the following are true:

- the task is a short read-only answer or a small direct edit expected to finish
  in the current turn;
- no unattended command, subagent, GUI, external tool, or network operation is
  needed;
- there is no realistic compaction, quota, or interruption risk;
- no evidence produced earlier in the task will be used as an acceptance gate.

If in doubt, use the Skill. The marginal cost is one small local state file and
periodic updates.

## Task-State File

The canonical task-state location is `.agent-state/tasks/<task-id>.md`.
The orchestrator chooses a stable `<task-id>` such as `issue-59-recovery` or
`rtd-mex-uart-002-kpi`. Use lowercase words, digits, and hyphens. Keep these
files local, ignored, small, and free of secrets, credentials, copied logs,
private machine data, broad command output, and disposable test artifacts.

Create or update the file at the entry gate, before unattended execution, and
before any planned handoff. The state file is not project documentation; it is
local working memory for Agents resuming the same checkout.

### Task-state template

```markdown
# <task-id>

| Field | Value |
| --- | --- |
| Task | <issue, PR, or user objective> |
| Owner | <orchestrator or role currently driving> |
| Started | <ISO-8601 local time> |
| Updated | <ISO-8601 local time> |
| Branch | <branch name> |
| Checkpoint | <latest commit, WIP commit, or none> |

## Scope and acceptance criteria

- <self-contained scope>
- <required verification gates and KPI evidence>
- <explicit out-of-scope items>

## Current status

- State: <not-started | active | waiting | paused | blocked | complete>
- Last action: <concise action summary>
- Next action: <single safest next step>

## Last verified evidence

- <command, exit code, timestamp, and result summary>
- <known stale evidence and why>

## Subagent handoffs

- <role, brief summary, started/finished time, result, evidence path/session>
- Evidence decision: <accepted | rejected | deferred> - <rationale>

## Git checkpoints

- <git status summary>
- <checkpoint commit hash or WIP commit hash>
- <push state and remote branch if applicable>

## Open risks and blockers

- <risk, owner, required decision or dependency>

## Resume notes

- <facts a fresh Agent must reconstruct before editing>
```

## Update Cadence

Update the task-state file:

- at task start, role handoff start, role handoff finish, and task finish;
- every 30 minutes while actively working;
- before compaction and after resuming from compaction;
- before unattended execution, long commands, GUI waits, black-box E2E,
  S32DS validation, or any command expected to outlive the current attention
  window;
- after any verification command whose result may be cited later;
- when scope, blockers, branch, checkpoint, KPI status, or acceptance evidence
  changes.

Prefer concise evidence summaries over large logs. Store only enough to
reconstruct status and decide the next safe action.

## Safe Git Checkpoints

Before any checkpoint, inspect `git status --short` and inspect the relevant
diff. Confirm the diff contains only intended files or explicitly recorded
pre-existing user edits.

Checkpoint rules:

- do not stage or commit unrelated user edits;
- record unrelated user edits in the task-state file when they affect routing
  or verification;
- never include secrets, credentials, local dependency cache secrets, broad
  command logs, or generated temp artifacts;
- checkpoint content must not include secrets and must not include temp artifacts;
- never include test scratch output outside the repository temp policy;
- WIP commit is allowed only when the task is long-running or unattended and the
  working tree needs a durable local recovery point;
- the WIP commit message must clearly say it is a recovery checkpoint and name
  the task id;
- prefer normal cohesive commits when the change is ready for review;
- push only when the user, issue workflow, PR workflow, or orchestrator brief
  explicitly requires a remote checkpoint;
- before pushing, repeat status and diff inspection and confirm the remote
  branch is the intended task branch.

If the working tree is dirty because of user changes, work with those changes.
Do not revert them. Stop and ask only when they make the scoped task unsafe or
impossible.

## Resume Handshake

The Resume handshake is mandatory after interruption.

On any resumed, compacted, interrupted, or reassigned task, the Agent must not
edit files, run mutating commands, stage changes, commit, push, or start a new
subagent until the resume handshake is complete. In short: the Agent must not edit files before reconstruction.

The handshake is:

1. read `AGENTS.md`;
2. read this Skill;
3. read the task-state file at `.agent-state/tasks/<task-id>.md`;
4. inspect `git status --short`;
5. inspect the relevant diff and any checkpoint commits named in the state
   file;
6. reconstruct the latest scope, owner, branch, intended files, verification
   gates, KPI status, stale evidence, and next safe action;
7. write or report a concise recovery summary;
8. continue only if safe, in scope, and no approval is needed.

If state is missing, contradictory, or points outside the current repository,
stop before mutation and ask the user or orchestrator for the missing context.
If approval is needed for a remote push, destructive cleanup, external GUI, or
network operation, request approval through the normal tool path.

## Goal Mode

Goal mode is optional. Use it when the task objective is broad enough that an
Agent may need multiple resumptions or automatic continuations, and when a
clear done criteria statement can be written. Do not use Goal mode for a short
single-turn edit, a read-only answer, or work that needs the user to make an
immediate unresolved decision.

Goal mode never replaces task-state and Git checkpoints. Pair Goal mode with
the task-state file and Git checkpoints so a resumed Agent can recover even if
the Goal summary is compacted or the app session is unavailable. Mark the Goal
complete only when the recorded done criteria and verification gates are met.

## Heartbeat Automation

Heartbeat automation is a best-effort recurring wakeup mechanism for unattended
work. It is useful when the Agent platform supports scheduled prompts, local
automation, or an external supervisor. It is not a substitute for the resume
handshake, checkpoint cadence, or user approvals.

The heartbeat prompt must include:

- repository path;
- task id and `.agent-state/tasks/<task-id>.md` path;
- the instruction to read `AGENTS.md`, read this Skill, read task state, inspect
  status and diff, then resume only if safe;
- expected next action or stop condition;
- reminder not to store secrets or broad logs.

Use a safe retry interval of 15 to 30 minutes for ordinary long commands and
30 to 60 minutes for external waits. Increase the interval after rate-limit or
quota pressure. Never create rapid retry loops.

stop conditions:

- task-state says `complete`, `blocked`, or `archived`;
- required approval is missing;
- the branch or repository path is not the expected one;
- git status shows unexpected edits that are not recorded in task state;
- verification failed in a way that needs human or orchestrator routing.

pause conditions:

- model, API, app, or vendor rate limits are active;
- external dependency is unavailable;
- a GUI or local app must be operated by the user;
- subagent or black-box E2E work exceeded the configured time budget and needs
  orchestrator intervention.

archive conditions:

- the task is complete and accepted;
- the branch was merged and no local recovery state is needed;
- the orchestrator intentionally abandons the task and records why.

Known limitations:

- local app limitation: the wakeup may depend on a desktop app, shell session,
  or platform feature that is not available after logout, reboot, or app
  shutdown;
- rate-limit limitation: recurring wakeups cannot bypass model, API, vendor, or
  network limits;
- path limitation: a heartbeat must target this repository path and must stop
  if the path, branch, or task-state file does not match.

## Trusted Hooks/Events

Optional Trusted hooks/events may update the task-state file or create a safe
checkpoint when the platform supports them. Review before use, keep hook scope
narrow, and do not store secrets, credentials, full logs, or unrelated local
state.

Allowed event points are listed below. Each event requires review before use.

- session start/resume;
- stop/pause;
- pre/post compact;
- long command start/finish;
- subagent handoff start/finish.

Hooks must be idempotent, local to the repository, and easy to disable. They
must never perform destructive cleanup, push to a remote, read the review
archive, scan broad machine paths, or modify Category A documents.

## Role Boundaries and Gates

The Orchestrator owns the task-state file for multi-role work. A Worker may
update it for its scoped handoff evidence, but must not broaden scope or change
acceptance gates. Explorer remains read-only. Tester owns convergence evidence.
Reviewer runs after the functional gate and KPI evidence are recorded, and then
reviews non-test acceptance requirements.

Record every subagent handoff start/finish in the task state with role, scope,
evidence, outcome, and an evidence decision of `accepted | rejected | deferred`
with rationale. If relevant source files changed after Tester evidence was
captured, Tester evidence is stale and the orchestrator must route fresh
verification according to `AGENTS.md`. The black-box E2E protocol is unchanged:
use `tools/blackbox_e2e.py` through an independent third-party Agent CLI when
E2E evidence is required.

## Category Boundary

This Skill is Category B only. docs/ stays agent-agnostic. `docs/` must not link
to or describe this Skill. Category B files may reference Category A specs,
test cases, and source-material rules when needed for Agent routing.

## Deferred Workflow Integration

Issue #57 workflow integration is deferred until the #57 workflow-routing Skill exists.
Once that exact file exists, wire this recovery protocol into its task
routing and long-running workflow entry points. Do not invent a #57 workflow
Skill or routing file while implementing this Skill.
