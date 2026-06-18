---
name: rtd-e2e-case-designer
description: Design or revise RTD CfgFile CLI module E2E test cases from project specs, module .xdm source facts, real S32DS fixtures, validation evidence, and KPI requirements. Use when adding a new module's E2E case catalog, reviewing user-proposed module prompts for feasibility, choosing or validating a fixture, or updating docs/tests/rtd-config-test-cases.md and docs/tests/rtd-config-acceptance-report.md for module E2E coverage.
---

# RTD E2E Case Designer

Use this skill to turn one RTD module into a durable E2E acceptance case set.
The output is not a loose idea list: it must be grounded in the module `.xdm`,
the project specs, a vendor-valid fixture, and measurable KPI rules.

## Inputs

Collect or derive these before writing test documentation:

- Target module name, for example `Adc`, `Spi`, `Can_43_FLEXCAN`, `Gpt`.
- Current project specs and test docs:
  - `docs/specs/rtd-config-core-design.md`
  - `docs/specs/rtd-config-domain-truth.md`
  - `docs/tests/rtd-config-test-strategy.md`
  - `docs/tests/rtd-config-test-cases.md`
  - `docs/tests/rtd-config-acceptance-report.md`
- Module source material:
  - installed RTD package path;
  - exact `config/<Module>.xdm`;
  - relevant module HLD skill, if already present under the skills inventory.
- At least one candidate S32DS fixture under
  `tests/fixtures/<vendor>/<backend>/<family>/<project>/`.
- User-facing prompts and KPI, if supplied. Preserve user prompts in the
  catalog's `Subagent Prompt` column unless a correction is explicitly agreed.

If a required `.xdm`, RTD package, or fixture path is unknown and cannot be
derived from cached environment evidence, ask for that path instead of
inventing values.

## Ground Truth Workflow

1. Read the module `.xdm` before designing cases.
2. Extract configurable surfaces:
   - general switches and feature gates;
   - top-level containers and arrays;
   - hardware-unit or channel containers;
   - trigger, group, DMA, interrupt, watchdog, callback, timing, routing, and
     dependency fields;
   - enum domains, defaults, editability, conditional fields, references, and
     quick-selection templates.
3. Record constraints in working notes or domain assets as appropriate:
   - valid enum values and legal combinations;
   - ownership boundaries between modules;
   - constraints that must be inferred from MCU clock, pins, DMA channels, or
     platform interrupts;
   - values that must not be literalized in prompts, such as sampling duration
     when the CLI should compute prescaler/duration from the active clock.
4. Inspect existing module skills and minimal-instance references when present,
   but treat the `.xdm` as the source of truth for fields and constraints.

## Fixture Workflow

Do not design final E2E cases against an assumed fixture. Inspect and validate a
real S32DS project first.

1. Locate candidate fixture files:
   - `.project`
   - `.cproject`
   - `.default_mex`
   - exactly one active `.mex`
   - required startup/project files for S32DS validation.
2. Run static inspection:
   - `.default_mex` points to the intended `.mex`;
   - XML parses;
   - `python -m rtd_config inspect --project <fixture> --json`;
   - `python -m rtd_config check --project <fixture> --json`.
3. Inspect fixture readiness:
   - enabled modules include the target module or can support adding it;
   - dependency modules exist where the case needs them;
   - MCU peripherals and clocks cover target hardware instances;
   - DMA/eMIOS/BCTU/Port/Platform resources exist when cases need them.
4. Run vendor validation before calling the fixture usable:
   - set `TEMP` and `TMP` to `tests/.tmp`;
   - run `python -m rtd_config validate --project <fixture> --json`;
   - require exit code `0`, `passed=true`, generated files present, and
     `severe_problems=[]`.
5. Keep validation outputs out of commits:
   - do not stage `build/configtools_validation.log`;
   - do not stage `tests/.tmp`;
   - stage fixture source files only.

If the fixture baseline differs from user wording, clarify the semantics in the
case pass criteria. Example: "modify existing hardware unit to ADC1" may mean
changing an existing module's hardware unit selection to ADC1, not requiring a
pre-existing ADC1 hardware-unit container.

## Case Design Method

Design cases as a coverage ladder from simple to complex. Each case should
exercise a real workflow a developer would ask an agent to perform.

Use this progression when the module supports it:

1. Existing simple configuration edit.
2. Add one new logical unit, channel, group, or container.
3. Enable notification, callback, interrupt, or API switch.
4. Add timing conversion from user intent to valid RTD fields.
5. Add streaming, buffering, queueing, or repeated conversion behavior.
6. Add watchdog, threshold, diagnostic, or error-notification behavior.
7. Add DMA or other cross-module resource dependency.
8. Add hardware trigger, routing, FIFO, trigger-list, or multi-instance flow.
9. Add the broadest realistic case that combines multiple dependencies without
   becoming a vague stress test.

For every case, explicitly decide:

- what the user prompt says;
- what the agent must infer;
- which module owns each edit;
- which dependencies must be routed to other module capabilities;
- which fields are validated directly;
- which behavior is proven only by S32DS validation/code generation;
- what KPI window and edit-attempt budget applies.

Prefer 3-6 E2E cases for a new module. Add more only when the module has
distinct feature families that cannot be covered coherently in fewer cases.

## Feasibility Review Before Documentation

Before writing docs, review the proposed cases against source facts and the
fixture. Report feasibility in plain engineering terms:

- `Feasible`: supported by `.xdm`, fixture resources, and validation flow.
- `Feasible with inference`: user prompt is normal developer language, but the
  agent/CLI must derive concrete fields from clock, dependency, enum, or
  existing project state.
- `Needs fixture adjustment`: source facts are valid, but the current fixture is
  missing a required module/resource/baseline.
- `Blocked`: `.xdm` or installed RTD evidence does not support the requested
  behavior, or a required dependency path is unknown.

Do not reject normal developer prompts merely because they omit derived values.
If the project expects the CLI/agent to compute values such as ADC duration
cycles from the active MCU clock, make that inference part of the pass criteria.

## Catalog Writing Rules

Update `docs/tests/rtd-config-test-cases.md` only after feasibility is clear.

For each case row:

- Use ID scheme `RTD-MEX-<MODULE>-NNN`.
- Keep `Module` as the AUTOSAR/RTD module name used by the project.
- Make `Scenario` short and implementation-oriented.
- Keep `Subagent Prompt` as the user-facing Chinese or English prompt.
- Set `Test fixture` to the validated fixture path for that module.
- State KPI as:
  `One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within <N> min.`
- Write pass criteria as observable requirements:
  - configured instances, channels, groups, triggers, callbacks, thresholds;
  - inferred timing or dependency calculations;
  - cross-module coherence;
  - S32DS validation and code generation success.

If only one module family uses a different fixture, update the section text
instead of falsely saying all cases use one fixture.

## Acceptance Report Rules

Update `docs/tests/rtd-config-acceptance-report.md` with the same fixture truth.

- New cases enter as `NOT RUN`.
- KPI is `Not yet measured` until black-box execution produces evidence.
- Do not mark a case `PASS` from catalog design, static inspection, or fixture
  validation alone.
- Keep the summary count accurate.
- Add a changelog row for fixture or case-status changes.

## Documentation Discipline

Respect the project documentation boundary:

- Put E2E case definitions and KPI in `docs/tests/`.
- Keep `docs/` agent-agnostic: do not refer to subagent discipline, this skill,
  or internal cache mechanics.
- Put agent process refinements in `agent-discipline/`.
- Use `.xdm` and project specs for facts; do not copy machine-specific paths
  into `docs/`.
- Bump document versions and add changelog rows for every changed document.
- Run `git diff --check` on changed docs.

## Closeout Checklist

Before reporting completion:

- Verify ADC-style fixture checks for the target module:
  - `inspect`;
  - `check`;
  - `validate`.
- Verify the catalog points every new case at the intended fixture.
- Verify the acceptance report does not claim unrun cases passed.
- Verify no validation logs, temp directories, generated code folders, or broad
  IDE/build artifacts are staged.
- If committing, stage explicit files only and keep the commit scope coherent:
  one module's fixture + its test-doc updates is one logical commit.
