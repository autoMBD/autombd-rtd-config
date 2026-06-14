# RTD CfgFile CLI Test Strategy

| Field | Value |
| --- | --- |
| Version | 0.9.0 |
| Date | 2026-06-13 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | The convergence contract for the RTD CfgFile CLI agent development workflow. Tests — deterministic, static, vendor validation, and isolated E2E acceptance — are the SOLE criterion for functional "done"; KPI misses trigger the capped Worker optimization loop and must be recorded honestly. Defines the test layers, the vendor gate, the acceptance rule, KPI handling, and the subagent roles; the concrete E2E cases live in `rtd-config-test-cases.md`. |

## 1. Principle: tests are the only convergence signal

This project is built by an autonomous agent workflow. The workflow stops only
when the gate is green on **real evidence**. Therefore tests must be complete
(every mandatory requirement has a test), rigorous (they exercise real behavior
and real assets — never a stub or a fabricated value), and authoritative (a
passing gate is sufficient to accept; a failing gate blocks).

Per-module facts a test asserts against (valid values, constraints, dependencies)
come from that module's `<Module>.xdm` and live in its provider; cross-cutting
facts (fixture usage, the vendor command/gate) live in
`rtd-config-domain-truth.md`. This document references both rather than
restating them. General engineering practice (TDD, stdlib, commit-per-task,
"diagnostics not tracebacks") is assumed of every agent and is not respecified
here.

## 2. Test layers

1. **Deterministic development tests** — `python -m pytest -q`. Fast, hermetic,
   run on every change. Cover the CLI/JSON contract, providers, document core,
   static checks, and `.mex` write fidelity (unit + integration).
2. **Static runtime checks** — the tool's own vendor-free checks, run after
   every config-file edit (well-formedness, ownership, reference coherence,
   conflicting carriers, invalid requests rejected with actionable blockers).
3. **Vendor validation** — mandatory. For `.mex`: S32DS ConfigTools headless per
   domain-truth §3. **Pass gate = exit code `0` AND no SEVERE `[TOOL]` resource
   problem.** Exit 0 alone is not a pass.
4. **Isolated E2E acceptance cases** — the cases in `rtd-config-test-cases.md`,
   executed as a **true black box** by the `tools/blackbox_e2e.py` harness: it
   deploys the released `autombd-rtd` skill into a fresh temp dir, copies the
   case fixture, and drives an **independent third-party agent CLI** (Codex now;
   extensible registry), sandboxed to the temp dir, that sees only the deployed
   skill + fixture + the case's prompt — never this repository. The embedded
   subagent is **not** a valid black box (it inherits repo context + filesystem).
   Pass requires the case's criteria, the vendor gate, and successful code
   generation; the Tester **independently re-runs `validate`** on the
   agent-produced `.mex` (it does not trust the agent's self-report) and records
   the case's KPI result.

## 3. Acceptance rule

A module or feature is **accepted** only when ALL hold:
- its mandatory deterministic tests pass;
- its static checks pass (or correctly block an invalid request with an
  actionable diagnostic);
- its vendor validation passes the §2.3 gate;
- **its E2E case(s) pass under the §2.4 black-box protocol.**

KPI is monitored alongside the functional gate. If a case is functionally green
but misses its KPI, the main agent routes it back to the Worker for KPI
optimization. The Worker may improve command ergonomics, diagnostics,
asset-driven defaults, planning clarity, or performance, but must not weaken any
functional check. The same case gets at most **three KPI-optimization
iterations**. If the KPI still misses after the third optimization iteration,
the Tester records the true KPI result in the acceptance evidence and the case
may proceed as functionally accepted.

All supported modules are **equal priority** and reach the same validated bar.
The minimal system (the first seven modules) is accepted only when every one of
them reaches this bar; delivery staging is recorded in the roadmap, not here.

## 4. Subagent roles in the convergence loop

`main agent → Explorer → Worker → Tester → main agent` is one iteration (roles
defined in `.claude/agents/`):

1. **Explorer** sources the per-module truth a case needs from the module's
   `<Module>.xdm` (valid values, constraints, dependencies) into its committed
   provider asset, and confirms fixture state and the exact vendor command.
2. **Worker** implements the capability TDD-first against that grounded truth,
   never inventing values.
3. **Tester** runs the gate: the deterministic suite, vendor validation, and the
   E2E acceptance cases — reporting per-module PASS/FAIL with exit code +
   SEVERE count and KPI evidence. **E2E is a true black box** (§2.4): the
   `tools/blackbox_e2e.py` harness drives an independent third-party agent CLI
   (Codex now; extensible) against the deployed skill + fixture only — never this
   repository, and never the embedded subagent (which inherits repo context). The
   Tester independently re-verifies the agent-produced `.mex` with the vendor
   gate.

The main agent routes on the Tester's result: **functional fail → next iteration
(back to Explorer); functional pass with KPI miss → Worker KPI optimization
(maximum three optimization iterations for the same case); functional pass with
KPI pass, or still-missed KPI after the third optimization iteration → record
the true KPI result and dispatch the Reviewer** for non-test acceptance — domain
values vs the `<Module>.xdm`, uniform header / missed skill triggers,
ownership/boundaries, test adequacy, diff hygiene — after which the Reviewer
appends a lessons-learned entry (`rtd-config-lessons-learned.md`). The Reviewer
reads the repository (it reviews the diff); it runs only after the functional
gate is green and does not re-run the gate.

KPIs: per-case budgets live in the case table (`rtd-config-test-cases.md`, 1–3
min, **excluding** validation runtime); the black-box harness sets the
third-party agent's timeout to **3× the max catalog KPI** so S32DS validation
fits. KPI evidence must include the measured elapsed time, whether the case used
one edit attempt or required rework, the optimization-iteration count, and the
final KPI status (`pass`, `miss`, or `miss-after-3`). The executed black-box
rounds are driven by `tools/blackbox_e2e.py`.

## 5. Test cases (separate document)

The concrete E2E acceptance cases this strategy gates are maintained in
[`rtd-config-test-cases.md`](rtd-config-test-cases.md) — format
`ID | Module | Scenario | Subagent Prompt | Test fixture | KPI | Pass criteria`,
scheme `RTD-MEX-<MODULE>-<NNN>` — so cases can grow and iterate without
churning the strategy. Only the `Subagent Prompt` cell may be written in Chinese;
all surrounding catalog text, scenario names, KPI descriptions, and pass
criteria are English. New modules add their cases there; staging lives in the
roadmap.

## 6. Test hygiene (enforced by the Reviewer)

- Every mandatory "must" in the specs maps to at least one deterministic test.
- No test asserts against a stub or fabricated value; if the underlying asset is
  unverified (e.g. current `pins.json`), the capability is gated until the asset
  is rebuilt from source (domain-truth §1).
- A test failure blocks; a green gate accepts. Do not relax a test to pass — fix
  the production gap.
- Vendor results are recorded with the exact exit code and SEVERE `[TOOL]`
  count, never summarized as "passed" without that evidence.
- KPI results are recorded honestly. A KPI miss does not become a functional
  failure after the third optimization attempt, and it must not be hidden by
  rewording the case KPI.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-14 | 0.9.0 | Codified the TRUE black-box E2E protocol (§2.4, §4): cases run via the `tools/blackbox_e2e.py` harness driving an independent third-party agent CLI (Codex now; extensible registry) against the deployed skill + fixture only — the embedded subagent is not a valid black box (it inherits repo context/filesystem); the harness timeout is 3× the max catalog KPI (so S32DS validation fits), and the Tester independently re-runs the vendor gate on the agent-produced `.mex`. |
| 2026-06-13 | 0.8.0 | Added KPI monitoring to the Tester gate: functionally passing cases that miss KPI return to the Worker for up to three KPI-optimization iterations; after the third miss, the true KPI result is recorded and functional acceptance may proceed. Clarified KPI evidence fields and the English-only rule outside `Subagent Prompt`. |
| 2026-06-10 | 0.7.0 | Fourth-round review resolution: added the isolated-E2E layer (§2.4) and made it part of the acceptance rule; the Tester owns context-isolated E2E execution (isolation generic, no platform-specific parameter); the Reviewer is repo-reading and not isolation-bound; case pointer renamed to `rtd-config-test-cases.md` (`RTD-MEX-*`); removed milestone-specific acceptance wording (staging lives in the roadmap); restored the itemized changelog. |
| 2026-06-06 | 0.6.0 | Split the concrete M1 case matrix, scope guards, and out-of-scope list into the test-cases document; this document now defines only the test method/strategy (layers, gate, acceptance rule, roles, hygiene). |
| 2026-06-03 | 0.5.0 | Restructured to seven-module parity with a mandatory S32DS gate (exit 0 + no SEVERE [TOOL]); made tests the sole convergence criterion; assigned Explorer/Worker/Tester/Reviewer roles; moved domain facts to domain-truth and advanced/reserved to the roadmap; withdrew the polling cases. |
| 2026-06-02 | 0.4.1 | Aligned fixture structure with backend/family/device/module/projects/project layout and recorded the Uart fixture path. |
| 2026-06-02 | 0.4.0 | Split Milestone 1 tests into mandatory minimum, advanced, and reserved future sets; added subagent user prompts and KPI clarification. |
| 2026-06-02 | 0.3.0 | Added first-milestone test case catalog from retired module use-case skills and documented the failure iteration loop. |
| 2026-05-30 | 0.2.1 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.0 | Clarified independent subagent validation scope. |
| 2026-05-30 | 0.1.0 | Created RTD CfgFile CLI test strategy. |
