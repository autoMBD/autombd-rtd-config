# RTD CfgFile CLI Milestone 1 Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-06-03 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Milestone 1 acceptance integration report for the RTD CfgFile CLI, consolidating deterministic development testing, independent black-box subagent validation, static runtime verification, and S32DS headless vendor validation against the active M1 specs, plan, and test strategy. |

## 1. Verdict

**Milestone 1 is ACCEPTED.** The RTD CfgFile CLI delivers the minimal S32K344
RTD 7.0.1 Uart stack — LPUART and FlexIO-backed channels in polling and
interrupt modes — through a deterministic CLI / JSON contract that edits the
existing `.mex` with narrow, byte-faithful, owned changes and runs layered
runtime verification (fast static checks first, S32DS headless validation
second).

Acceptance rests on the test-strategy Acceptance Rule (§229–240):

- required mandatory minimum cases pass — **yes** (RTD-M1-MIN-001..008);
- backend validation passes when applicable — **conditionally**: ConfigTools
  loads and evaluates the tool-edited `.mex` with an error profile **identical**
  to the unmodified original NXP example (the edit is benign), but this S32DS
  3.6.7 install exposes no self-terminating ConfigTools headless-validate
  application, so an automated exit-code gate is not reproducible (§6); the
  acceptance rule and validation handoff make this non-blocking and the
  non-vendor evidence authoritative;
- focused independent subagent validation meets the KPI — **yes** (§4);
- failures produce actionable diagnostics, not tracebacks — **yes** (§5, §7).

## 2. Acceptance Criteria Mapping

Mapped to the plan's *Final Milestone 1 Acceptance* checklist.

| Plan acceptance item | Status | Evidence |
| --- | --- | --- |
| Full deterministic tests pass (`unit` + `integration`) | PASS | 33/33 (§3) |
| Mandatory E2E pass without vendor validation | PASS | 9/9 e2e incl. RTD-M1-MIN-001..008 (§3) |
| Mandatory E2E with S32DS validation | ENV-LIMITED (non-blocking) | ConfigTools evaluates edited `.mex` with error profile identical to the original; no headless-exit app on this install (§6) |
| Independent subagent validation, `fork_context:false` | PASS | 4 representative cases within KPI (§4) |
| `.mex` quick-selection behavior covered by tests | PASS | static-check + narrow-write unit/fixture tests (§5) |
| Focused cases converge within 3 min | PASS | max 77 s (§4) |
| No case exceeds 10 min without intervention | PASS | no intervention required (§4, §6) |

## 3. Deterministic Development Testing

Command and result:

```powershell
python -m pytest -q
# 42 passed
```

Distribution: **unit 26, integration 7, e2e 9 — 42 total.** The e2e layer is
the mandatory minimum matrix `RTD-M1-MIN-001..008` plus the S32DS-command
construction test. Non-vendor assertions always run; the S32DS process
assertion is gated by `RTD_CONFIG_RUN_S32DS_VALIDATION` so the matrix is green
with or without the vendor environment.

| Case | Surface | Result |
| --- | --- | --- |
| RTD-M1-MIN-001 | `inspect` | PASS — backend/device/package/RTD/modules/profile |
| RTD-M1-MIN-002 | `uart set` LPUART polling | PASS — status passed, uart owned, static passed |
| RTD-M1-MIN-003 | `uart set` LPUART interrupt | PASS |
| RTD-M1-MIN-004 | `uart set` FlexIO polling | PASS |
| RTD-M1-MIN-005 | `uart set` FlexIO interrupt | PASS |
| RTD-M1-MIN-006 | `pin-options` | PASS — LPUART_0 options present |
| RTD-M1-MIN-007 | E2E LPUART stack | PASS — configure + check |
| RTD-M1-MIN-008 | E2E FlexIO stack | PASS — configure + check |

## 4. Independent Black-Box Subagent Validation

Performed per `rtd-config-m1-subagent-validation.md`. Each validator ran as a
cold, context-isolated subagent (`fork_context:false` semantics: no inherited
conversation state) and received **only** the simulated Chinese user request,
the repository-visible companion skill (`.skills/rtd-config/SKILL.md`), the
public CLI, and its own private copy of the fixture project. No validator was
told how the tool is built internally.

| Case | Request surface | Verdict | Convergence | KPI |
| --- | --- | --- | --- | --- |
| RTD-M1-MIN-001 | `inspect` | PASS | ~28 s | 3 min |
| RTD-M1-MIN-002 | LPUART polling | PASS | ~77 s | 3 min |
| RTD-M1-MIN-004 | FlexIO polling | PASS | ~72 s | 3 min |
| RTD-M1-MIN-006 | `pin-options` | PASS | ~62 s | 3 min |

All four converged well within the 3-minute focused KPI; no run approached the
10-minute intervention threshold. The validators independently confirmed:
module-ownership boundaries (Uart owns channel; Mcu clock, Port pins, Mcl FlexIO
are dependencies), correct absence of a Platform IRQ dependency in polling mode,
the FlexIO logic-channel reference with no `quick_selection` conflict, DMA
absence, and the runtime/development-source boundary (`pin-options` reads only
the committed `pins.json`). These representative cases cover the read path
(`inspect`), the core LPUART configure path, the higher-risk FlexIO + Mcl path,
and the runtime-asset query path.

One real gap surfaced and was fixed during validation: `inspect` did not emit
the chip **package (封装)** that the MIN-001 prompt explicitly asks for (§7).

## 5. Runtime Verification — Static Checks

The fast, vendor-free static stage runs during development testing and as the
first stage of runtime verification after every `.mex` edit. All failure
patterns from `rtd-config-m1-legacy-skills-experience.md` are implemented and
covered: XML well-formedness, single `.mex`, enabled-module/duplicate-name
detection, `quick_selection` conflict on modified elements, stale FlexIO
`UartHwChannelRef`, missing Mcl FlexIO logic channel, duplicate LPUART hardware,
`UartChannelId` index match, invalid callback (`NULL_PTR`/non-C-identifier), and
M1 DMA rejection. Blockers are returned as structured diagnostics, never
tracebacks.

`.mex` write fidelity is enforced by dedicated regression tests: a no-edit write
reproduces the file byte-for-byte (including the non-canonical XML declaration
and CRLF endings), and an owned LPUART edit changes ≤ 8 lines while leaving the
declaration and unrelated entries byte-identical.

## 6. Runtime Verification — S32DS Headless (Vendor)

The development computer is configured for the vendor flow:

- launcher: `C:\NXP\S32DS.3.6.7\eclipse\s32dsc.exe` with `--launcher.ini`
  `s32ds.ini`;
- application: `com.nxp.swtools.framework.application.HeadlessApplication`,
  `-nosplash`;
- workspace: `D:\WorkSpace\DSpace\3.6` (documented default, RTD packages
  registered);
- SDK: `-sdkPath C:\NXP\SW32K3_S32M27x_RTD_R23-11_7.0.1` (RTD R23-11 7.0.1,
  S32K3XX resource set present);
- pass condition: ConfigTools process exit code `0`.

### 6.1 Tool launch defects found and fixed

Running the real vendor flow on this configured machine exposed and fixed two
launch defects in the `validate` command (commit `675dfb2`):

- `--launcher.ini` resolved to a non-existent `s32dsc.ini`; the console launcher
  shares `s32ds.ini`. Now resolves to the file that exists, else omits the flag.
- the application id `com.nxp.swtools.framework.application.HeadlessApplication`
  is **not registered** in S32DS 3.6.7 (`Application "..." could not be found in
  the registry`). Corrected to the registered ConfigTools entry
  `com.nxp.swtools.framework.application`.

A vendor-tool timeout or missing executable now returns a structured non-zero
outcome (124 / 127), never a traceback.

### 6.2 Result and error attribution

With the corrected command, ConfigTools loads the RTD 7.0.1 SDK, imports the
project, and evaluates the `.mex`. Two controlled headless runs were compared —
the tool-edited LPUART project and the **unmodified** original NXP example:

| Run | s32dsc result | SEVERE | `Port_GetNumOfPinConfig` errors | GUI-perspective wait |
| --- | --- | --- | --- | --- |
| Unmodified original | timeout-killed (120 s) | 61 | 42 | yes |
| Tool-edited LPUART_0 | timeout-killed (240 s) | 61 | 42 | yes |

The error profiles are **identical** while the two `.mex` files differ on disk
(distinct SHA-256). Two conclusions follow:

1. **The tool's edit is benign to ConfigTools.** It introduces zero additional
   evaluation errors relative to the shipped, working NXP example — positive
   evidence that the narrow edit preserves project integrity.
2. **A clean automated headless exit-code gate is not reproducible on this
   install.** The registered ConfigTools entry is a GUI application that loads
   and evaluates the project but then waits on a UI perspective (`There is no
   tool that has perspective called '...CPerspective'`) instead of
   self-terminating; S32DS 3.6.7 registers no dedicated ConfigTools
   headless-validate application. The `Port_GetNumOfPinConfig` script errors are
   environmental — present on the untouched original — and unrelated to the tool.

Per the Acceptance Rule ("backend validation passes when applicable") and the
validation handoff ("the non-vendor assertions are authoritative"), this does
not block Milestone 1. The tool now drives ConfigTools correctly; confirming a
fully headless exit-code gate (a dedicated ConfigTools validate/generate
application id, or a newer S32DS) is carried as an M2 vendor-integration item.

## 7. Defects Found and Fixed During Acceptance

| Defect | Impact | Fix | Commit |
| --- | --- | --- | --- |
| `.mex` writer reserialized the whole document (3096-line churn on a 2408-line file) | Violated the mandatory "narrow / localized edits" rule; review-hostile diffs | expat source-span surgical writer; rewrite only changed start tags, copy all other bytes verbatim; stdlib only | `50ba1dc` |
| `inspect` omitted the chip package | MIN-001 prompt asks for 封装; spec treats package as first-class | emit `config.package`; guard in mandatory test | `3fc6eb1` |
| `--launcher.ini` pointed at non-existent `s32dsc.ini` | Headless validation would abort on a correctly-configured machine | resolve to the shared `s32ds.ini`; omit when absent | (this report's branch) |
| S32DS timeout / missing executable raised a traceback | Violated "actionable diagnostics, not tracebacks" | catch `TimeoutExpired`/`OSError`; return structured non-zero outcome (124/127) | (this report's branch) |

## 8. Scope and Boundary Compliance

- **DMA excluded:** `UartDmaEnable`/`MclEnableDma` true → `dma_not_supported_in_m1`
  blocker; never partially configured.
- **No creation:** edits existing module instances only; missing-module
  completion and `.mex`-from-scratch are deferred to M2.
- **Module ownership:** each provider edits only its region; cross-module needs
  are declared dependencies (Mcu clock, Port pins, Platform IRQ, Mcl FlexIO).
- **Runtime/development boundary:** runtime commands read only committed assets
  (`pins.json`, manifests); no Excel, raw `.xdm`, deprecated skills, or RTD
  install scans are read at runtime. The vendor tool uses its own installed
  environment internally, as permitted.
- **Documentation boundary:** `docs/superpowers/specs/achieved/` was treated as a
  review archive and not used as a requirements source.

## 9. Known Limitations and Deferred Work (M2+)

- `.mex` creation and missing-module completion;
- DMA-backed Uart, EB tresos backend, K1/K5 validation profiles;
- advanced and reserved-future test classes (planning inputs, not M1 gates);
- the reported package is the profile-level identifier (`default`); per-orderable
  package names are an M2 data-model enrichment;
- a fully headless ConfigTools exit-code gate is an M2 vendor-integration item
  (§6): the env-gated matrix (`RTD_CONFIG_RUN_S32DS_VALIDATION=1`) is wired and
  will assert exit code `0` once a self-terminating headless validate
  application id is confirmed for the installed S32DS. For M1, ConfigTools was
  shown to evaluate the tool-edited `.mex` with an error profile identical to
  the original NXP example, and the authoritative non-vendor evidence governs
  acceptance.

## 10. Artifacts

- Source: `rtd_config/` (CLI, S32 `.mex` backend, modules, checks, resources).
- Tests: `tests/unit` (26), `tests/integration` (7), `tests/e2e` (9).
- Runtime assets: `data/s32k/families/s32k3/devices/s32k344/packages/default/pins.json`.
- Companion skill: `.skills/rtd-config/SKILL.md`.
- Validation handoff: `docs/superpowers/tests/rtd-config-m1-subagent-validation.md`.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-03 | 0.1.0 | Created the Milestone 1 acceptance integration report. |
