# RTD CfgFile CLI Implementation Plan

| Field | Value |
| --- | --- |
| Version | 0.2.2 |
| Date | 2026-06-13 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | How the RTD CfgFile CLI is implemented: one fixed development framework, applied module by module. The first seven modules form the minimal system and are delivered together; every later module is added on explicit user instruction under the same framework. Delivery staging lives in the roadmap. |

## Implementation model

The tool grows **module by module**, and **every module — current and future —
is developed and tested in the same framework**:

- the subagent iteration loop `main agent → Explorer → Worker → Tester → main
  agent`, with the Reviewer on a green gate (charter: `AGENTS.md`; roles:
  `.claude/agents/`);
- **tests as the sole convergence signal** (method:
  `docs/tests/rtd-config-test-strategy.md`; E2E cases:
  `docs/tests/rtd-config-test-cases.md`), with KPI misses routed through the
  capped Worker optimization loop defined by the test strategy;
- per-module truth sourced from the module's `<Module>.xdm` into a committed
  asset (`docs/specs/rtd-config-domain-truth.md` §1);
- the architecture, ownership rules, and CLI/JSON contract of
  `docs/specs/rtd-config-core-design.md`.

The first seven modules — `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`,
`Uart` — form the **minimal system** and are completed together with equal
priority. After the minimal system, new modules are added when the user gives
the instruction, each as its own scoped task in this same framework. The
sequence and staging of those additions live in
`docs/roadmaps/rtd-config-roadmap.md`, not here.

## Per-module delivery checklist (the framework)

Every module's delivery runs these steps; a module is **done** only when all of
them hold:

1. **Ground truth (Explorer).** Extract the module's valid values, numeric
   ranges/defaults, constraint rules, and cross-module dependencies from its
   `<Module>.xdm`; confirm fixture state and the exact vendor-validation
   command (domain-truth §1/§3). Never invent a value.
2. **Asset (Worker).** Emit or refresh the committed per-module asset under
   `autombd-rtd/assets/<vendor>/<family>/<module>/`, each item traceable to its
   `.xdm` source path and RTD version.
3. **Provider (Worker, TDD-first).** Implement or extend the module provider
   against that asset: ownership-bounded edits only, narrow byte-faithful
   `.mex` writes, structured diagnostics, supporting the module's **full legal
   editable surface** (core design G10).
4. **Deterministic tests (Tester).** Unit/integration coverage for the new
   capability is green: `python -m pytest -q`.
5. **E2E acceptance (Tester, true black box).** The module's E2E case(s) in
   `docs/tests/rtd-config-test-cases.md` pass under the black-box protocol — the
   `tools/blackbox_e2e.py` harness drives an independent third-party agent CLI
   (Codex now; extensible) against the deployed skill + fixture only — including
   the vendor gate (exit `0`
   AND no SEVERE `[TOOL]`) and successful code generation. Tester records the
   case KPI. If functional validation passes but KPI misses, route back to the
   Worker for optimization; after at most three KPI-optimization iterations,
   record the true KPI result and continue with the functional evidence.
6. **Review (Reviewer).** Non-test acceptance: domain values cross-checked
   against the `.xdm`, uniform MIT header / missed skill triggers, ownership
   and boundary compliance, test adequacy, diff hygiene — plus a
   lessons-learned entry (`docs/common/rtd-config-lessons-learned.md`).

## Always-on engineering constraints

- stdlib-only Python runtime; committed assets are the only runtime data — no
  Excel, raw `.xdm`/`.epd`, deprecated skills, or RTD install scans at runtime;
- narrow, byte-faithful `.mex` writes (a no-edit write is byte-identical); no
  edits outside module ownership;
- never invent vendor values; diagnostics, never tracebacks;
- uniform MIT file header on every new source file
  (`.claude/skills/common-uniform-file-header`);
- the released deliverable is the self-contained `autombd-rtd/` Agent Skill
  (SKILL.md + launcher + `assets/` + bundled CLI).

## References

| Document | Used for |
| --- | --- |
| `docs/specs/rtd-config-core-design.md` | Architecture, contract, goals, doc map |
| `docs/specs/rtd-config-domain-truth.md` | `.xdm` sourcing rule; vendor validation flow + gate; fixture usage |
| `docs/tests/rtd-config-test-strategy.md` | Test layers, acceptance rule, roles, KPI optimization loop |
| `docs/tests/rtd-config-test-cases.md` | E2E acceptance cases (`RTD-MEX-*`) + black-box protocol + per-case KPI |
| `docs/roadmaps/rtd-config-roadmap.md` | Delivery staging (the only place stages live) |
| `docs/references/rtd-config-source-materials.md` | Development-time inputs for asset building |
| `docs/references/rtd-config-legacy-skills-experience.md` | `.mex` editing pitfalls baseline |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-14 | 0.2.2 | Aligned the §5 E2E-acceptance step with the TRUE black-box protocol: cases pass via the `tools/blackbox_e2e.py` harness driving an independent third-party agent CLI (Codex now; extensible) against the deployed skill + fixture only — the embedded subagent is not a valid black box. |
| 2026-06-13 | 0.2.1 | Added the KPI-monitoring and capped Worker optimization loop to the module delivery checklist and references. |
| 2026-06-10 | 0.2.0 | Fourth-round review resolution: rewrote as a milestone-agnostic, module-by-module implementation plan (one fixed framework; the first seven modules form the minimal system and land together; later modules are added on user instruction). Removed the historical Milestone-1 task recipes (archived in `docs/OBSOLETE_NEVER_TOUCH!!!/fourth-review/`); renamed the document from `rtd-cfgfile-cli-milestone1-implementation-plan.md`. |
| 2026-06-02 | 0.1.1 | Added M1 legacy-skills experience baseline and quick-selection requirements to document core, static checks, and acceptance. |
| 2026-06-02 | 0.1.0 | Created Milestone 1 implementation plan from active RTD CfgFile CLI specs, roadmap, fixture layout, and test strategy. |
