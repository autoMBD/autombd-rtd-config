# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-06-11 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Current pass/fail evidence for the E2E acceptance cases defined in `rtd-config-test-cases.md`. This document is the living status record the catalog points to; the catalog defines the target, this records where the tool actually stands. |

> **Governed by [`rtd-config-test-cases.md`](rtd-config-test-cases.md)** (the case
> catalog and isolation protocol) and
> [`rtd-config-test-strategy.md`](rtd-config-test-strategy.md) (layers, the vendor
> pass gate, roles). Per-module truth comes from each `<Module>.xdm`; the
> cross-cutting S32DS flow/gate lives in
> [`../specs/rtd-config-domain-truth.md`](../specs/rtd-config-domain-truth.md).

## 1. Acceptance gate status

The vendor pass gate is the **sole acceptance signal** for an E2E case (exit `0`
AND code generated AND no SEVERE `[TOOL] … has the following error`).

| Item | Status | Evidence |
| --- | --- | --- |
| S32DS headless validation operational | **OPERATIONAL (fixed 2026-06-11)** | Flow B verified on S32DS 3.6.7; pristine `Uart_Example_S32K344` → exit `0`, 120 generated files, `severe_problems: []` via `python -m rtd_config validate`. |
| Pass gate detects real errors | **VERIFIED** | Known-bad probe (`OsIfUseSystemTimer=true`, empty `OsIfCounterConfig`) → SEVERE `[TOOL] The resource "BaseNXP" … has the following error: The number of OsIf Counters must be exactly one …`; gate returns `passed=false`. |
| Caller project safety | **VERIFIED** | After validation the caller's `.mex` is byte-identical (validation runs on a throwaway copy). |

> **Why this matters:** before the fix, the gate failed on *every* input — the
> registration step timed out, so a pristine fixture returned exit `2`. The
> deterministic suite gates the vendor path behind
> `RTD_CONFIG_RUN_S32DS_VALIDATION` (off by default), so "44 passed" never proved
> any `.mex` was vendor-valid. With the gate now trustworthy, the remaining work
> is per-module capability, each provable against it.

## 2. Per-case status

All cases use the fixture `Uart_Example_S32K344`. Status legend: **PASS** (vendor
gate green under isolation), **FAIL** (capability missing), **BLOCKED** (depends
on an unbuilt asset).

| ID | Module | Status | Gap to PASS |
| --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | FAIL | No MCU apply path. Needs clock-tree edits (CORE_CLK/AIPS_PLAT/AIPS_SLOW from 16 MHz FXOSC) **and** creating every Clock Reference Point (element insertion). |
| RTD-MEX-BASENXP-001 | BaseNXP | FAIL | Provider is plan-only. Enabling `OsIfUseSystemTimer` requires **creating one `OsIfCounterConfig`** with `OsIfSystemTimerClockRef`/`…Freq` (baremetal) — element insertion (`BaseNXP.xdm` INVALID rule, confirmed by the known-bad probe). |
| RTD-MEX-PLATFORM-001 | Platform | FAIL | No Platform apply path. Needs to enable the LPUART_3 interrupt, set priority 2, and register the ISR. (LPUART_3 channel already present in the fixture.) |
| RTD-MEX-PORT-001 | Port | BLOCKED | `pins.json` is a 4-signal stub; must be rebuilt complete from the IOMUX workbook before `pin-options`/pin application are trustworthy. Then needs a Port apply path. |
| RTD-MEX-DIO-001 | Dio | BLOCKED | Needs Dio channel **creation** + Port direction config; depends on `pins.json` and the element-insertion writer. |
| RTD-MEX-MCL-001 | Mcl | FAIL | Needs FlexIO-common enable (already true in fixture) + **creating** a FlexIO logic channel (element insertion) with a consistent name/reference. |
| RTD-MEX-UART-001 | UART | FAIL | `uart set` edits an existing channel's hw/method/baud only. Needs parity/stop/word-length/callback, instance switch to LPUART_8, **and cross-module execution** (Platform ISR + MCU ref clock + priority) — currently only *declared*, never written. |
| RTD-MEX-UART-002 | UART | FAIL | Needs FlexIO Uart channel **creation** + MCL logic-channel reference + Platform ISR (LPUART & FlexIO) — creation + orchestration both missing. |
| RTD-MEX-UART-003 | UART | FAIL | DMA is rejected (`unsupported_uart_mode`); needs Uart DMA method + MCL DMA channel/instance + Platform ISR. |

**Summary: 0 / 9 cases PASS.** The acceptance gate is now operational; no
per-module write capability yet produces a vendor-valid result for its case.

## 3. Cross-cutting blockers (critical path)

These unblock multiple cases and should land before/with per-module work:

1. **Byte-faithful element insertion.** The `.mex` writer
   (`backends/s32_mex/document.py`) only edits/removes attributes on existing
   elements; adding an element forces full reserialization (whole-file churn —
   the legacy-skills hazard). Required by every "add/create" case
   (BASENXP counter, MCU clock reference points, DIO/MCL/UART channels).
2. **Cross-module orchestration execution.** Providers declare `PlannedChange`
   dependencies (Mcu clock, Platform IRQ/ISR, Mcl FlexIO/DMA, Port pins) but the
   apply path never writes them. UART-001/002/003 cannot pass until declared
   dependencies are actually applied across modules.
3. **`pins.json` rebuild** from `Copy of S32K344_S32K324_S32K314_IOMUX.xlsx`
   (development input only) into the complete family-scoped Port asset. Gates
   PORT-001 and DIO-001.
4. **DMA capability** (UART-003).
5. **CLI surface** for `mcu`/`basenxp`/`platform`/`port`/`dio`/`mcl` — today only
   `uart set` (plus `inspect`/`check`/`validate`/`pin-options`) is wired.

## 4. Execution plan

Each module runs the per-module delivery checklist in
`docs/plans/rtd-cfgfile-cli-implementation-plan.md` (Explorer → Worker → Tester →
Reviewer), proven against the now-operational gate.

| Step | Work | Unblocks |
| --- | --- | --- |
| 0 | ✅ Repair the vendor acceptance gate (Flow B) | every case |
| 1 | Byte-faithful element insertion in the writer | all creation cases |
| 2 | BASENXP-001: OsIf counter creation + asset + CLI | BASENXP-001 |
| 3 | PLATFORM-001: interrupt enable/priority/ISR apply | PLATFORM-001, UART-* |
| 4 | MCU-001: clock-tree edit + reference-point creation | MCU-001, UART-* |
| 5 | Rebuild `pins.json`; Port apply | PORT-001, DIO-001 |
| 6 | DIO-001: channel creation + Port direction | DIO-001 |
| 7 | MCL-001: FlexIO logic-channel creation | MCL-001, UART-002 |
| 8 | UART cross-module orchestration (apply declared deps) | UART-001/002 |
| 9 | UART-002: FlexIO channel creation + MCL ref | UART-002 |
| 10 | DMA capability (Uart + Mcl + Platform) | UART-003 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-11 | 0.1.0 | Created the acceptance report (the catalog's pass/fail record). Recorded the repaired vendor gate (Flow B, operational + error-detecting + project-safe), the honest 0/9 per-case baseline with each gap, the cross-cutting critical-path blockers, and the sequenced execution plan. |
