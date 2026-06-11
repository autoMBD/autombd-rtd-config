# RTD CfgFile CLI Lessons Learned

| Field | Value |
| --- | --- |
| Version | 0.1.3 |
| Date | 2026-06-11 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Running log of lessons captured during the agent development loop. The **Reviewer** appends one entry per accepted iteration (after the Tester's gate is green) so recurring failure modes become permanent guards. This is distinct from the legacy-skills baseline (which captures pre-project `.mex` experience). |

## How this log is used

- Owner: the **Reviewer** subagent. After an iteration passes the test gate, the
  Reviewer records what the iteration taught — especially anything that *passed
  the green gate but was still wrong or risky* (the gate cannot catch everything).
- Every lesson must end in a **durable guard**: a new test, a provider/asset rule,
  a domain-truth/`.xdm` sourcing requirement, a Reviewer checklist item, or a
  Worker convention. A lesson without a guard is not done.
- Keep entries short and factual: what happened → root cause → the guard that
  prevents recurrence. Newest first.

## Entries

| ID | Lesson | Root cause | Durable guard |
| --- | --- | --- | --- |
| LL-010 | A module provider's `plan()` description and its declared ownership went stale after the apply path was corrected: the green gate stayed green while `basenxp.plan()` still told the user it would write `OsIfSystemTimerClockFreq=48000000` with "no core-clock ref in this project", even though `apply_basenxp_set` now writes a populated `OsIfSystemTimerClockRef` (Mcu `FLEXIO_CLK`/CORE_CLK) + an empty Freq array. The plan also never declared the cross-module Mcu read-dependency it now relies on. Separately, the fix to `apply.py`/`osif.json` was made by the **Tester**, whose charter is "edit tests only; report production gaps". | The convergence gate exercises `apply()` (and the vendor `.mex`) but nothing asserts `plan()`'s emitted `description`/`owner` or the declared dependency set, so plan and apply drifted with no failing test. The role deviation happened because a correct, fast production fix was reachable mid-gate and the boundary was not re-stated in the Tester handoff. | (a) Add a test that pins `BaseNxpProvider.plan()` output: its description must match what `apply` writes (populated ClockRef, empty Freq array, no `48000000`), and the plan must declare the Mcu `McuClockReferencePoint` dependency (owner/needs), so plan-vs-apply drift fails the gate. (b) Architecture rule: a cross-module READ that an edit depends on (here Mcu clock-ref discovery) must be an explicit declared dependency in `plan()`, not implicit in apply. (c) Process guard: when the Tester finds a production gap it reports it for the Worker; if the orchestrator authorizes an exceptional Tester-side production fix, a **fresh independent Tester** re-runs the gate (done here) AND the Reviewer treats any Tester-authored production diff as a required focus area. |
| LL-009 | The vendor gate silently failed on *every* input — even a pristine, vendor-authored fixture returned exit 2 — so "44 passed" never proved any `.mex` was vendor-valid. | Validation used the registration-based Flow A whose CDT `-import` step timed out (exit 124); the project was then unregistered, so `-UpdateCode` failed with `Cannot get container for IPath`. It went unnoticed because vendor validation is gated behind an off-by-default env flag and was never re-run on a known-good baseline. | Adopted the verified standalone **Flow B** (`-Load`/`-ExportSrc`, no registration; domain-truth §3). Pass gate now also requires code generation (`generated_files > 0`). The gate's own acceptance evidence is a known-good baseline (pristine fixture → pass) **and** a known-bad probe (invalid OsIf → SEVERE `[TOOL] … has the following error`), confirming exit 0 alone is insufficient. |
| LL-008 | Milestone/schedule wording repeatedly leaked into specs and diagrams ("M1", "first/later") across four review rounds, and changelog history was once collapsed during a doc slim-down. | Authors optimized docs locally without altitude rules: specs absorbed plan/stage detail; history was treated as compressible content. | `AGENTS.md` Documentation Boundary now mandates: specs/diagrams carry no milestone/stage/time wording (stages live only in the roadmap), and changelogs are append-only (never merged). Reviewer checks both per iteration. |
| LL-007 | Spec internal-consistency is not vendor-truth: three review rounds never caught the wrong polling/validation facts. | Reviews checked self-consistency, not the vendor source. | Reviewer cross-checks every domain value against the module `<Module>.xdm`; vendor S32DS gate is an early, mandatory step, not a late one. |
| LL-006 | `.mex` writer reserialized the whole file (~3000-line churn) yet passed well-formedness tests. | Mandatory "narrow edits" rule had no test guard. | Byte-faithful narrow-writer + regression tests (no-edit write is byte-identical; owned edit touches only changed lines). Every spec "must" maps to a test. |
| LL-005 | A runtime asset (`pins.json`) was a hand-made stub, not derived from source, and a test asserted against it. | Asset fabricated instead of built from the authoritative source. | Assets are built from source (pins from the pin-mux Excel, package-specific; per-module truth from `<Module>.xdm`); a capability is gated until its asset is real; tests never assert against a stub. |
| LL-004 | The uniform-file-header skill was never applied (54 `.py` files); a relevant skill trigger was missed, including by implementation subagents. | Skills do not auto-fire and subagents do not inherit the obligation. | Worker applies header on every new source file; Reviewer checklist includes "missed skill triggers"; cross-cutting conventions are injected into every subagent brief. |
| LL-003 | "ConfigTools exit 0 = pass" accepted configs that still had SEVERE errors. | Exit code alone is not the vendor verdict. | Pass gate = exit 0 **AND** no SEVERE `[TOOL]` resource problem (domain-truth §3); the Tester records the exit code + SEVERE count. |
| LL-002 | S32DS headless validation was non-functional as documented (hung; wrong app id / launcher / sdkPath; unregistered project). | The validation command was assumed, not verified against the installed tool + its docs. | Verified S32DS flow captured in domain-truth §3 from the official CLI docs; the Tester runs it on real hardware before claiming a vendor pass. |
| LL-001 | The tool wrote an invented Uart enum `..._USING_POLLING`; ConfigTools rejected it as "value not available". | An enum value was assumed instead of sourced from the module descriptor. | Per-module valid values come from `<Module>.xdm` and live in the provider; the Worker never invents enum strings; the Reviewer verifies against the `.xdm`. |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-03 | 0.1.0 | Created the lessons-learned log and seeded LL-001..007 from the M1 Uart-reference work. |
| 2026-06-10 | 0.1.1 | Added LL-008 (spec altitude + changelog integrity) from the fourth review round. |
| 2026-06-11 | 0.1.2 | Added LL-009 (the vendor gate silently failed on every input; Flow A registration timeout) while landing the Flow B fix and the first accepted case (PLATFORM-001). |
| 2026-06-11 | 0.1.3 | Added LL-010 (provider `plan()` description/ownership drifted from the corrected apply path and stayed green; undeclared cross-module Mcu dependency; Tester-side production fix) for RTD-MEX-BASENXP-001. |
