# RTD CfgFile CLI Documentation Governance

| Field | Value |
| --- | --- |
| Version | 0.1.10 |
| Date | 2026-09-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Documentation-governance rules for the RTD CfgFile CLI project. Defines the two-category split, official tool name, changelog integrity, archive policy, and the authoritative cross-category documentation map. |

## Governance rules

### Official tool name

The official tool name in all active documentation is **RTD CfgFile CLI**.

### Two-category documentation split

All project documents fall into exactly one of two physically separated
categories:

- **Category A — Development documentation** (`docs/` and agent-agnostic RTD
  CfgFile CLI feature references under `tests/doc/`): pure project and
  engineering content; self-contained and agent-agnostic. Contains zero
  agent-discipline content and carries no pointers or links to agent-discipline
  documents. Includes specs (architecture, domain truth), test documents
  (strategy, cases, acceptance report), the roadmap, and references.
- **Category B — Agent discipline** (`AGENTS.md` at repo root,
  `agent-discipline/subagents/`, `agent-discipline/`, and Agent feature references,
  Agent-bearing requirement snapshots and shared guidance in `tests/doc/`): agent charter, role definitions, iteration loop,
  KPI policies, review records, lessons learned, and this governance document.

Cross-category pointers are allowed from Category B to Category A (e.g.,
`AGENTS.md` referencing domain-truth or test cases), but never from Category A
to Category B.

### Functional case documents and Human review

Effective for new issue work, explicitly including ongoing #85, keep functional
documentation in `tests/doc/` using one short general guide/index and separate
feature references, grouped by subject (Agent / RTD CfgFile CLI). Do not append
every feature's cases to an ever-growing type-wide document. Use stable feature
names rather than creating a duplicate document for each follow-up issue.

The layout below illustrates #85; these paths are a convention, not a claim
that the feature files have already been delivered by this policy change:

| File | Content |
| --- | --- |
| `tests/doc/README.md` | Shared explanation and an index: type, feature, requirements link, cases link. No copies of feature requirements/cases or per-run evidence. |
| `tests/doc/reference/agent/workflow-transition-requirements.md` | Standalone readable rendering of the feature's complete `K.payload.requirements`. |
| `tests/doc/reference/agent/workflow-transition-cases.md` | That feature's concise case table only, apart from normal title/metadata/changelog. |

Other Agent features reuse `reference/agent/`; product features use
`reference/rtdcfg-cli/`. Add index links when an applicable new issue supplies
the two references; do not create empty feature files or backfill old features.
The previous `agent-functional-test-cases.md` monolith is not the continuing
layout: split its in-progress #85 content when that Test delivery is next revised.

The requirements reference must retain every requirement ID, full obligation
and source association in `payload.requirements`; resolve authority IDs to
durable issue/specification/decision references, not only ignored local files.
Identify the source K revision/digest for reconciliation. If an obligation needs
an interface or decision table to be understandable, provide a durable exact
source link or the necessary public definition in this same requirements file.
A label such as "R01–R25" without accessible requirement text is insufficient.
This is a durable review rendering, not a new authority or replacement for the
complete K used by both Agents. Keep dispatch paths, private reports and the
rest of the runtime envelope out of it; do not commit `.agent-state/` wholesale.
Orchestrator owns fidelity to K and supplies the same public requirements to
both lanes; Tester packages the checked rendering with the Test review files.
Resolve any real requirement disagreement through K, never silently in the doc.

Tester derives cases from the public requirements without reading Worker
Implementation. Use a concise table: case ID, requirement ID, scenario and
expected result. Include only the conditions needed to distinguish the case;
do not add per-case execution steps, setup procedures, command sequences,
automation-node inventories or run results. Those details belong in scripts
and existing structured reports/Impact Set. Orchestrator still checks the
requirement-to-case-to-script mapping; a shorter Human document does not weaken
the executable assertions or reduce the selected functional scope.

At Gate 1, Tester supplies exact-Test-commit links to **two primary review
files: the feature requirements and its cases**, plus their changes. The general
guide links both; Human need not infer requirements from local K or cases from
code, nor review every handoff field. The Test commit contains those documents,
the corresponding index update and automation. The existing approval freezes
their exact bytes with T/manifest/Impact Set; this adds no extra Human gate.
Prevalidation details and results remain supporting evidence, not case prose.

Later issues update only their affected feature references and index entry,
preserving accepted case IDs and history. A changed requirement or expectation
must be identified for review, not silently weakened. Requirement-only content
is public task material and can reach Worker through the reviewed public
handoff; current/unaccepted case references and scripts remain hidden Test.
Do not send Worker the case-bearing index, Test worktree or a mixed document
bundle to obtain public requirements. Accepted cases already in G retain their
normal regression status.

The shared guide and Agent references are Category B. Pure product cases and
requirements are Category A; a full K requirements rendering containing Agent
delivery obligations is Category B even for a product feature. Classify by
content: the shared Category B index may link both, but a Category A case file
must not link to Agent discipline or carry its text. Requirement IDs can map
through the shared index/report without that forbidden reverse link.

KPI case documents stay in `docs/tests/` and are created/updated by their KPI
test issues, with the separate Human case review and local execution lifecycle.
Do not put KPI catalogues in `tests/doc/`, turn them into functional acceptance,
or migrate historical KPI documents as part of this rule. Worker-owned unit/TDD
tests remain distinct and do not require a duplicate functional case catalogue.
Historical code already accepted into the repository needs no retrospective
case-document backfill. A new issue documents only its new/changed functional
scope; touching an old feature is not authority to redocument that whole feature.

### Specs stay at architecture altitude — milestone-free

Documents under `docs/specs/` (including their diagrams and goal tables) must
not reference a specific milestone, stage, schedule, or time-plan wording such
as "first/later/M1". Delivery staging lives only in
`docs/roadmaps/rtd-config-roadmap.md`. This rule exists because milestone
wording repeatedly leaked into specs across review rounds.

### Category A purity sweep

When reorganizing or auditing documentation, the Category A purity check must be
**repo-wide over all of `docs/`** — not scoped to the files a change happened to
touch. Grep for the agent-discipline lexicon
(`orchestrat|explorer|worker|tester|reviewer|subagent|main agent|KPI[- ]optim|convergence gate|iteration loop`),
excluding frozen changelog rows and `agent-discipline/review-archive-NOT-USED-NEVER-TOUCH!!!/`. The only
permitted survivors in `docs/` are the `Subagent Prompt` column name (a data
contract parsed by `tools/blackbox_e2e.py`, its unit tests, and its help text)
and references to `tools/blackbox_e2e.py` itself (committed project tooling).

### Changelogs are append-only

Changelog tables are append-only history records. Never merge, collapse, or
summarize existing changelog rows. New rows are added at the top or bottom
(consistently within each document).

### Task-specific plans are temporary local state

Task-specific execution plans, checklists, command sequences, and commit
sequences live only under the ignored `.agent-state/plans/` directory and are
never committed. Durable human engineering architecture and design decisions
belong in Category A documents in agent-agnostic form. Reusable Agent workflow
rules belong in Category B; neither category is a home for one-off execution
state.

### Review archive is read-only

`agent-discipline/review-archive-NOT-USED-NEVER-TOUCH!!!/` (formerly
`docs/OBSOLETE_NEVER_TOUCH!!!/`) contains frozen review archives only. These
files are unavailable as requirements sources and must not be read to infer
current behavior, scope, terminology, or acceptance criteria. Their contents
must never be edited.

### File header convention

Source and script files (`.py`, `.c`, `.h`, …) carry the uniform MIT file header
per `.claude/skills/common-uniform-file-header`. Project Markdown documents do
**not** use the MIT banner: they start directly with a `# Title` followed by a
metadata table (Version, Date, Author, Description), matching every existing
project doc.

## Documentation map

The authoritative map of all project documents, organized by category. All
paths are relative to the repository root.

### Category A: Development documentation (`docs/`)

| Document | Role | References |
| --- | --- | --- |
| `docs/specs/rtd-config-core-design.md` | Long-term architecture, CLI/JSON contract, goals, engineering constraints, minimal-system definition | domain-truth, test strategy, test cases, source materials |
| `docs/specs/rtd-config-runtime-safety-and-contract-design.md` | Runtime trust-boundary design: project identity, assets, diagnostics, secure transactions, provider ownership, descriptor inventory, and release integrity | core design, domain truth, test strategy |
| `docs/specs/rtd-config-domain-truth.md` | Per-module truth sourcing rule; vendor validation flow + gate; fixture role | source materials |
| `docs/specs/figures/` | Editable architecture figures (drawio + spec) | — |
| `docs/tests/rtd-config-test-strategy.md` | Test method: layers, gate, acceptance rule, hygiene | domain-truth, test cases |
| `docs/tests/rtd-config-test-cases.md` | E2E acceptance case catalog (`RTD-MEX-*`) | test strategy, domain-truth, fixtures |
| `docs/tests/rtd-config-acceptance-report.md` | Recorded acceptance evidence and current status | test cases, test strategy |
| `tests/doc/reference/rtdcfg-cli/*-cases.md` and agent-agnostic `*-requirements.md` (when needed) | Feature-scoped product requirements/cases, not a type-wide monolith | public product requirements |
| `docs/roadmaps/rtd-config-roadmap.md` | **The only place stages live**: the basic delivery route | — |
| `docs/references/rtd-config-source-materials.md` | Catalog of development-time inputs (Excel, `.xdm`, vendor docs) | — |

### Category B: Agent discipline

| Document | Role | References |
| --- | --- | --- |
| `AGENTS.md` | Agent charter: orchestrator duties, four roles, iteration loop, convergence gate, KPI policies, documentation discipline | domain-truth, agent-lessons-learned, test cases |
| `agent-discipline/subagents/explorer.md` | Explorer role definition | AGENTS.md, domain-truth |
| `agent-discipline/subagents/worker.md` | Worker role definition | AGENTS.md, domain-truth |
| `agent-discipline/subagents/tester.md` | Tester role definition | AGENTS.md, test cases |
| `tests/doc/README.md` | Short shared explanation and type/feature index; no copied case/requirement bodies | Each feature's requirements and cases |
| `tests/doc/reference/agent/*-requirements.md` and `*-cases.md` | Separate durable requirements and concise cases for each Agent feature | public Agent requirements and decisions |
| Agent-bearing `tests/doc/reference/rtdcfg-cli/*-requirements.md` (when needed) | Full public requirement rendering that also contains Agent delivery obligations | public task requirements and decisions; no Category A inbound links |
| `agent-discipline/subagents/reviewer.md` | Reviewer role definition | AGENTS.md, agent-lessons-learned |
| `agent-discipline/skills/external-dependency-memory/SKILL.md` | Skill for reusing local external dependency evidence across agents and conversations | AGENTS.md, source materials |
| `agent-discipline/owner-review-comments.md` | Review-comment resolutions across rounds | agent-discipline/review-archive-NOT-USED-NEVER-TOUCH!!!/ |
| `agent-discipline/agent-lessons-learned.md` | Reviewer's running lessons log | — |
| `agent-discipline/agent-loop-bootstrap-trust-trace.md` | Bootstrap trust-tracing lane: frozen framework/history audit, Human-approved lifecycle design, derived current snapshot, append-only bootstrap events, and complete lessons synthesis | AGENTS.md, workflow contract, agent-lessons-learned |
| `agent-discipline/documentation-governance.md` | This document: governance rules + documentation map | — |
| `agent-discipline/review-archive-NOT-USED-NEVER-TOUCH!!!/` | Frozen review archives — never a requirements source | — |

### Standalone deliverable

| Document | Role |
| --- | --- |
| `autombd-rtd/SKILL.md` | Released Agent Skill: how an agent drives the public CLI (self-contained; ships with `assets/` + CLI) |
| `README.md` | Entry point: status, quick start, repository layout |

```mermaid
flowchart TD
  README["README.md"] --> CORE["docs/specs/core-design"]
  AGENTS["AGENTS.md"] --> DT["docs/specs/domain-truth"]
  AGENTS --> TC["docs/tests/test-cases"]
  CORE --> DT
  CORE --> TS["docs/tests/test-strategy"]
  CORE --> SM["docs/references/source-materials"]
  TS --> TC
  TC --> DT
  AR["docs/tests/acceptance-report"] --> TC
  RM["docs/roadmaps/roadmap"]
  ROLES["agent-discipline/subagents/"] --> AGENTS
  LL["agent-discipline/agent-lessons-learned"] --> AGENTS
  TT["agent-discipline/agent-loop-bootstrap-trust-trace"] --> AGENTS
  TT --> LL
  CT["agent-discipline/owner-review-comments"] -.archives.-> OBS["agent-discipline/review-archive-NOT-USED-NEVER-TOUCH!!!/"]
  SKILL["autombd-rtd/SKILL.md + assets/ + CLI"] -. released deliverable .-> TC
```

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-06 | 0.1.10 | Replaced growing type-wide catalogues with one guide/index and feature references; made complete durable requirements plus concise cases the two Gate review files, without procedural case prose or changed isolation/KPI scope. |
| 2026-09-06 | 0.1.9 | Established prospective type-classified functional case catalogues and document-first Human Test review, exact doc/script binding, incremental ownership and distinct KPI issue-maintained documents; no historical backfill. |
| 2026-08-29 | 0.1.8 | Renamed the Agent Loop review as the bootstrap trust-tracing lane and documented its split baseline/design/snapshot/append-only-event responsibilities. |
| 2026-08-29 | 0.1.7 | Added the Agent Loop framework review and limited-bootstrap design to the authoritative Category B documentation map. |
| 2026-07-18 | 0.1.6 | Required task-specific execution plans to remain ignored local state under `.agent-state/plans/`; durable engineering design remains Category A and reusable Agent workflow remains Category B. |
| 2026-07-12 | 0.1.5 | Added the Category B implementation-plan directory to the authoritative documentation map. |
| 2026-07-12 | 0.1.4 | Added the runtime-safety and public-contract design to the authoritative Category A documentation map. |
| 2026-06-29 | 0.1.3 | Issue #35: renamed the read-only review archive to `agent-discipline/review-archive-NOT-USED-NEVER-TOUCH!!!/` to make its frozen status explicit; updated all active references (purity-sweep rule, archive policy, documentation map, mermaid diagram). Frozen changelog rows retain the historical path. |
| 2026-06-16 | 0.1.2 | Replaced the script-centered agent environment document with the lightweight external-dependency-memory skill entry. |
| 2026-06-15 | 0.1.1 | Added `agent-discipline/agent-environment.md` to the Category B documentation map for issue #11. |
| 2026-06-15 | 0.1.0 | Created per issue #7 documentation reorganization: established the two-category split, ported and updated the authoritative documentation map from the deleted core-design `## Documentation map` section (with all paths updated to new locations), and codified the governance rules (tool name, milestone-free specs, Category A purity sweep, append-only changelogs, read-only review archive, file header convention). |
