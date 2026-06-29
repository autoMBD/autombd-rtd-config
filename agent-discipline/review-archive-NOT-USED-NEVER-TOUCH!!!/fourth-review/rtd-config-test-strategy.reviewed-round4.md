> **OBSOLETE - review archive only (round 4).** This is the reviewed draft of
> `docs/tests/rtd-config-test-strategy.md` with the user's inline REVIEW comments preserved for traceability.
> It is NOT a requirements source and must not be read to infer current
> behavior, scope, terminology, or acceptance criteria. Use only active
> documents outside `docs/OBSOLETE_NEVER_TOUCH!!!/`. Comment resolutions are
> tracked in `docs/common/rtd-config-core-comments-tracking.md`.

# RTD CfgFile CLI Test Strategy

| Field | Value |
| --- | --- |
| Version | 0.6.0 |
| Date | 2026-06-03 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | The convergence contract for the RTD CfgFile CLI agent development workflow. Tests — deterministic, static, and S32DS vendor validation — are the SOLE criterion for "done". Defines the test layers, the S32DS gate, the acceptance rule, and the subagent roles; the concrete per-milestone cases live in separate test-case documents (Milestone 1: `rtd-config-m1-test-cases.md`). |

## 1. Principle: tests are the only convergence signal

This project is built by an autonomous agent workflow. The workflow stops only
when the gate is green on **real evidence**. Therefore tests must be complete
(every mandatory requirement has a test), rigorous (they exercise real behavior
and real assets — never a stub or a fabricated value), and authoritative (a
passing gate is sufficient to accept; a failing gate blocks).

Per-module facts a test asserts against (valid values, constraints, dependencies)
come from that module's `<Module>.xdm` and live in its provider; cross-cutting
facts (fixture facts, the S32DS command/gate) live in `rtd-config-domain-truth.md`.
This document references both rather than restating them. General engineering
practice (TDD, stdlib, commit-per-task, "diagnostics not tracebacks") is assumed
of every agent and is not respecified here.

## 2. Test layers

1. **Deterministic development tests** — `python -m pytest -q`. Fast, hermetic,
   run on every change. Cover CLI/JSON contract, providers, document core,
   static checks, and `.mex` write fidelity.
2. **Static runtime checks** — the tool's own vendor-free checks, run after every
   `.mex` edit (well-formedness, single `.mex`, enabled modules, quick_selection
   conflict, FlexIO refs, duplicate hardware, callback, DMA rejection,
   unsupported-mode rejection).
3. **S32DS vendor validation** — mandatory. ConfigTools headless per
   domain-truth §3. **Pass gate = exit code `0` AND no SEVERE `[TOOL]` resource
   problem.** Exit 0 alone is not a pass.

## 3. Acceptance rule

A module or feature is **accepted** only when ALL hold:
- its mandatory deterministic tests pass;
- its static checks pass (or correctly block an invalid request with an
  actionable diagnostic);
- **its S32DS vendor validation passes the §2.3 gate.**

Milestone 1 is accepted only when **every one of the seven modules** (Mcu,
BaseNXP, Platform, Port, Dio, Mcl, Uart) reaches this bar. The seven modules are
**equal priority**; Uart is the reference level, not a privileged one.
Advanced/reserved tests (see `rtd-config-m1-test-cases.md` §3 and the roadmap)
do not block M1.

## 4. Subagent roles in the convergence loop

`main agent → Explorer → Worker → Tester → main agent` is one iteration (roles
defined in `.claude/agents/`):

1. **Explorer** sources the per-module truth a case needs from the module's
   `<Module>.xdm` (valid values, constraints, dependencies) into its committed
   provider asset, and confirms fixture state and the exact S32DS command.
2. **Worker** implements the capability TDD-first against that grounded truth,
   never inventing values.
3. **Tester** runs the gate: the deterministic suite + S32DS validation, and
   reports per-module PASS/FAIL with exit code + SEVERE count.

The main agent routes on the Tester's result: **fail → next iteration (back to
Explorer); pass → the Reviewer** for non-test acceptance — domain values vs the
`<Module>.xdm`, uniform header / missed skill triggers, ownership/boundaries,
test adequacy, diff hygiene — after which the Reviewer appends a lessons-learned
entry (`rtd-config-lessons-learned.md`). The Reviewer runs context-isolated
(`fork_context:false`) and does not re-run the gate.

KPIs: a focused case converges within 3 min; an end-to-end case within 5 min; any
run exceeding 10 min triggers orchestrator intervention and issue capture.
Independent black-box validation prompts live in
`rtd-config-m1-subagent-validation.md` (currently the proven Uart-reference
prompts; per-module prompts are added as each module reaches parity).

## 5. Milestone test cases (staged, in separate documents)

The concrete, per-milestone test cases this strategy gates are maintained in
their own documents, so they can grow and iterate without churning the strategy:

- **Milestone 1** — [`rtd-config-m1-test-cases.md`](rtd-config-m1-test-cases.md):
  the seven-module parity matrix (`inspect`, `pin-options`, the seven module
  configures, the two Uart channel cases, the two end-to-end stacks), the M1
  scope guards, and the out-of-scope list.

Every case is governed by the test layers (§2), the S32DS gate (§2.3), and the
acceptance rule (§3) above, and is owned and driven by the roles in §4.

## 6. Test hygiene (enforced by the Reviewer)

- Every mandatory "must" in the specs maps to at least one deterministic test.
- No test asserts against a stub or fabricated value; if the underlying asset is
  unverified (e.g. current `pins.json`), the capability is gated until the asset
  is rebuilt from source (domain-truth §1).
- A test failure blocks; a green gate accepts. Do not relax a test to pass — fix
  the production gap.
- S32DS results are recorded with the exact exit code and SEVERE `[TOOL]` count,
  never summarized as "passed" without that evidence.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.4.x | Mandatory/advanced/reserved split; Uart-centric MIN-001..008 matrix; subagent prompts and KPIs. |
| 2026-06-03 | 0.5.0 | Restructured to seven-module parity with a mandatory S32DS gate (exit 0 + no SEVERE [TOOL]); made tests the sole convergence criterion; assigned Explorer/Worker/Tester/Reviewer roles; moved domain facts to domain-truth and advanced/reserved to the roadmap; withdrew the polling cases. |
| 2026-06-06 | 0.6.0 | Split the concrete M1 case matrix, scope guards, and out-of-scope list into `rtd-config-m1-test-cases.md`; this document now defines only the test method/strategy (layers, gate, acceptance rule, roles, hygiene). |

<!-- REVIEW: 为啥要把Changelog合并？不要这样做！ -->
