# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.17.0 |
| Date | 2026-06-17 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Current pass/fail evidence for the E2E acceptance cases defined in `rtd-config-test-cases.md`. This document is the living status record the catalog points to; the catalog defines the target, this records where the tool actually stands. |

> **Governed by [`rtd-config-test-cases.md`](rtd-config-test-cases.md)** (the case
> catalog) and
> [`rtd-config-test-strategy.md`](rtd-config-test-strategy.md) (layers, the vendor
> pass gate, acceptance rule, KPI handling). Per-module truth comes from each
> `<Module>.xdm`; the cross-cutting S32DS flow/gate lives in
> [`../specs/rtd-config-domain-truth.md`](../specs/rtd-config-domain-truth.md).

## 1. Acceptance gate status

The functional gate is the **sole acceptance signal** for an E2E case (exit `0`,
code generated, no SEVERE `[TOOL] … has the following error`, and the case pass
criteria met). KPI is monitored separately.

| Item | Status | Evidence |
| --- | --- | --- |
| S32DS headless validation operational | **OPERATIONAL (fixed 2026-06-11)** | Flow B verified on S32DS 3.6.7; pristine `Uart_Example_S32K344` → exit `0`, 120 generated files, `severe_problems: []` via `python -m rtd_config validate`. |
| Pass gate detects real errors | **VERIFIED** | Known-bad probe (`OsIfUseSystemTimer=true`, empty `OsIfCounterConfig`) → SEVERE `[TOOL] The resource "BaseNXP" … has the following error: The number of OsIf Counters must be exactly one …`; gate returns `passed=false`. |
| Caller project safety | **VERIFIED** | After validation the caller's `.mex` is byte-identical (validation runs on a throwaway copy). |
| KPI evidence policy | **DEFINED (2026-06-13)** | Each isolated case records elapsed time, edit-attempt count, KPI status (`pass` or `miss`), and final disposition. |

> **Why this matters:** before the fix, the gate failed on *every* input — the
> registration step timed out, so a pristine fixture returned exit `2`. The
> deterministic suite gates the vendor path behind
> `RTD_CONFIG_RUN_S32DS_VALIDATION` (off by default), so "44 passed" never proved
> any `.mex` was vendor-valid. With the gate now trustworthy, the remaining work
> is per-module capability, each provable against it.

## 2. Per-case status

All cases use the fixture `Uart_Example_S32K344`. The **Status** column is the
functional acceptance signal — legend: **PASS** (vendor gate green under
isolation), **FAIL** (capability missing), **BLOCKED** (depends on an unbuilt
asset). The **KPI** column records each case's measured KPI result against its
catalog budget (`pass`/`miss`, with the edit-attempt count and the
validation-excluded time); a case not yet exercised under the black-box protocol
reads *Not yet measured*, and a KPI `miss` never weakens the functional **PASS**.
The detailed per-case implementation evidence is preserved in the changelog below.

| ID | Module | Status | KPI |
| --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | **PASS** | **PASS** — 1 edit attempt, validation-excluded 96 s ≤ 2 min budget (black-box, 2026-06-15) |
| RTD-MEX-BASENXP-001 | BaseNXP | **PASS** | **MISS** — 1 edit attempt, validation-excluded 134 s > 1 min budget (black-box, 2026-06-17) |
| RTD-MEX-PLATFORM-001 | Platform | **PASS** | Not yet measured |
| RTD-MEX-PORT-001 | Port | **PASS** | Not yet measured |
| RTD-MEX-DIO-001 | Dio | **PASS** | Not yet measured |
| RTD-MEX-DIO-002 | Dio | **PASS** | Not yet measured |
| RTD-MEX-MCL-001 | Mcl | **PASS** | Not yet measured |
| RTD-MEX-UART-001 | UART | **PASS** | Not yet measured |
| RTD-MEX-UART-002 | UART | **PASS** | Not yet measured |
| RTD-MEX-UART-003 | UART | **PASS** | Not yet measured |

**Summary: 10 / 10 cases PASS — the seven-module minimal system is COMPLETE**
(RTD-MEX-DIO-002 added as black-box round-2 hardening). All seven modules
(Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart) reach the full acceptance bar:
deterministic suite (467 tests green), static checks, the S32DS vendor gate
(exit 0 + no SEVERE `[TOOL]` + code generated), AND each E2E case's generated
code verified to reflect the edit (LL-013). Every case also passed independent
non-test acceptance review with all findings closed. The five cross-cutting blockers
(element insertion, cross-module orchestration, `pins.json`, DMA, CLI surface)
are all resolved.

## 3. Cross-cutting blockers (critical path)

These unblock multiple cases and should land before/with per-module work:

1. ✅ **Byte-faithful element insertion** — DONE. `document.py
   replace_element_region` splices a new element region (self-closed → populated)
   and re-captures spans; the attribute-edit path is untouched. Proven by
   BASENXP-001 (OsIf counter insertion) with a direct regression test.
2. ✅ **Cross-module orchestration execution** — DONE. DIO-001 proved the pattern
   (Dio channel + Port pin); UART-001 extended it to 3 modules (Uart + Platform
   ISR + Mcu clock), UART-002 to Uart + Mcl (FlexIO), UART-003 to Uart + Mcl +
   Platform (DMA). Each writes only its owned regions and the plan declares the
   cross-module dependencies.
3. ✅ **`pins.json` rebuild** — DONE. 2091 real signals built from the IOMUX
   workbook via a committed stdlib tool (`tools/build_pins_s32k3.py`);
   `pin-options` returns verified pins. The Port `apply` path (PORT-001) writes a
   queried pin into both `.mex` representations; DIO-001 reuses it for GPIO.
4. ✅ **DMA capability** — DONE (UART-003): Uart DMA method + Tx/Rx refs, MCL DMA
   channels/instance, Platform DMATCD ISRs; `_check_dma` enforces the INVALID rule.
5. ✅ **CLI surface** — DONE. All seven module commands are wired (`mcu`/`basenxp`/
   `platform`/`port`/`dio`/`mcl`/`uart` set, plus `uart add-flexio-channel`) on top
   of `inspect`/`check`/`validate`/`pin-options`.

## 4. Execution plan

Each module runs the per-module delivery checklist, proven against the
now-operational gate.

| Step | Work | Unblocks |
| --- | --- | --- |
| 0 | ✅ Repair the vendor acceptance gate (Flow B) | every case |
| 1 | ✅ Byte-faithful element insertion in the writer | all creation cases |
| 2 | ✅ BASENXP-001: OsIf counter insertion + asset + CLI | BASENXP-001 |
| 3 | ✅ PLATFORM-001: interrupt enable/priority/ISR apply | PLATFORM-001, UART-* |
| 4 | ✅ Rebuild `pins.json` (2091 signals) | PORT-001, DIO-001 |
| 5 | ✅ MCL-001: FlexIO logic-channel creation | MCL-001, UART-002 |
| 6 | ✅ MCU-001: clock-tree edit + reference-point merge | MCU-001, UART-* |
| 7 | ✅ Port apply (write queried pin) → PORT-001 | PORT-001, DIO-001 |
| 8 | ✅ DIO-001: channel creation + Port direction (cross-module) | DIO-001 |
| 9 | ✅ UART cross-module orchestration → UART-001 | UART-001 |
| 10 | ✅ UART-002: FlexIO channel creation + MCL ref + ISR | UART-002 |
| 11 | ✅ DMA capability (Uart + Mcl + Platform) → UART-003 | UART-003 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-14 | 0.13.0 | Strengthened the vendor gate (external-review remediation): `validate` now also flags `From Problems view: Tool problem issue:` Clocks/Peripherals/Pins resource violations, closing the LL-014 bypass where an `HSE_CLK>120 MHz` config exit-0'd and false-passed; re-baselined against the real gate (pristine + a valid 160/80/40 config still pass; the HSE_CLK>120 case is now caught). Refreshed the deterministic count to 467. Companion fixes: M1-wording code sweep, doc path/asset-rule corrections, `.gitignore` + README de-stage. |
| 2026-06-14 | 0.12.0 | RTD-MEX-DIO-002 **PASS**: `dio set --pin PTA30` auto-creates the absent `DioPort_1` container (DioPortId 1, array index 1) then inserts the channel (DioChannelId 14); vendor + codegen verified cold (auto-discovery) on the focused case and the full 5-task combined scenario — `Dio_Cfg.h` has `DioConf_DioChannel_LED_CTRL ((uint16)0x001eU)` and `DioConf_DioPort_DioPort_1 ((uint8)0x01U)`. Added as black-box round-2 hardening (LL-019); deterministic suite 422 green. |
| 2026-06-13 | 0.11.0 | Added the KPI evidence policy: functionally passing cases that miss KPI return to Worker optimization for up to three iterations; after the third miss, the true KPI result is recorded in this report. |
| 2026-06-11 | 0.1.0 | Created the acceptance report (the catalog's pass/fail record). Recorded the repaired vendor gate (Flow B, operational + error-detecting + project-safe), the honest 0/9 per-case baseline with each gap, the cross-cutting critical-path blockers, and the sequenced execution plan. |
| 2026-06-11 | 0.2.0 | RTD-MEX-PLATFORM-001 **PASS** (1/9): `platform set` edits an existing `PlatformIsrConfig` priority/enable on the LPUART3 interrupt; verified end-to-end against the real S32DS gate (exit 0, 120 generated files, no severe). Marked plan step 3 done. |
| 2026-06-11 | 0.3.0 | RTD-MEX-BASENXP-001 **PASS** (2/9): `basenxp set --enable-system-timer` inserts an OsIf counter referencing the Mcu CORE_CLK point (FLEXIO_CLK), vendor-gate green; drove the byte-faithful element-insertion writer (blocker #1 DONE) and landed the complete 2091-signal `pins.json` (blocker #3 DONE). Updated the per-case table, cross-cutting blockers, and execution plan. |
| 2026-06-11 | 0.4.0 | RTD-MEX-MCL-001 **PASS** (3/9): `mcl set --add-flexio-logic-channel` appends a FlexIO logic channel with a dynamically-computed unique ChannelId/PinId, vendor-gate green (9-line narrow insert). Marked plan step 5 done. |
| 2026-06-12 | 0.5.0 | RTD-MEX-PORT-001 **PASS** (4/9): `port set` validates a pin against pins.json then inserts both the `<pin>` header and the Port `PortPin` struct; vendor gate green and the generated SIUL2 source reflects the pins. Review hardening fixed a shared-writer same-prefix tag-matching bug (`<pin>` vs `<pin_features>`) that could have forced whole-file reserialization. Marked plan step 7 done. |
| 2026-06-12 | 0.6.0 | RTD-MEX-DIO-001 **PASS** (5/9): `dio set` (cross-module Dio+Port) inserts the DioChannel + the Port GPIO output pin and clears the Dio `config_set` `quick_selection` so codegen emits the channel; vendor gate green and `Dio_Cfg.h` contains `DioConf_DioChannel_LED_CTRL`. Established the codegen-verification gate step (LL-013) and confirmed MCL-001 codegen. Marked plan step 8 done. |
| 2026-06-12 | 0.7.0 | RTD-MEX-MCU-001 **PASS** (6/9): `mcu set` configures the 160/80/40 clock tree (PLL + MC_CGM dividers incl. HSE_CLK/2), McuNoPll/mirror fixes, and merges the Clock Reference Points; vendor + codegen verified over 3 vendor-driven refine iterations. Established LL-014 (comprehensive Problems-view SEVERE scan for clock cases). All 6 non-UART modules done; remaining UART-001/002/003. |
| 2026-06-12 | 0.8.0 | RTD-MEX-UART-001 **PASS** (7/9): `uart set` (3-module orchestration) edits the LPUART_8 channel + module callback and inserts the Platform ISR + Mcu clock ref; vendor + 3-module codegen verified (converged on the first vendor run). Established LL-015 (narrowness-bound discipline as orchestration grows). All 7 modules now have an accepted capability; remaining UART-002 (FlexIO channel creation) + UART-003 (DMA). |
| 2026-06-13 | 0.9.0 | RTD-MEX-UART-002 **PASS** (8/9): `uart add-flexio-channel` creates a FlexIO Tx+Rx Uart channel pair + their MCL logic channels with consistent references + module callback; vendor + end-to-end codegen verified (converged first vendor run). LL-016 ended the recurring documentation-only-asset pattern (FlexIO asset keys now loaded/pinned). Marked plan step 10 done. Only UART-003 (DMA) remains. |
| 2026-06-13 | 0.10.0 | RTD-MEX-UART-003 **PASS** (9/9 — minimal system COMPLETE): developed the DMA capability (Uart DMA method + Tx/Rx refs + MCL DMA channels/instance + Platform DMATCD ISRs); vendor + 4-module codegen verified; `_check_dma` now enforces the DMA INVALID rule (LL-017). All seven modules accepted: deterministic (389), static, vendor gate, and per-case codegen all green; every case Reviewer-approved. All five cross-cutting blockers resolved. |
| 2026-06-15 | 0.14.0 | Issue #7 reorganization: removed KPI-cap clause from §1 (agent-discipline, already canonical in AGENTS.md); removed pointer to deleted implementation-plan from §4 execution-plan text. |
| 2026-06-15 | 0.14.1 | Issue #7 follow-up: de-agented the §1 KPI-evidence-policy row — dropped the `miss-after-3` status value and the optimization-iteration count (the capped optimization loop is agent-discipline, canonical in AGENTS.md); KPI status is recorded as `pass`/`miss`. |
| 2026-06-15 | 0.15.0 | Recorded the first **measured KPI** result (RTD-MEX-MCU-001): functional PASS with **KPI PASS** — a cold Codex agent driving the released skill applied 1 edit attempt and finished the non-validation work in 96 s ≤ the 2 min budget; independently re-verified on the vendor gate (exit 0, 0 SEVERE, 120 files, codegen 160/80/40). KPI was reconstructed from the black-box agent's session log (edit-attempt count + validation-excluded time). Synced the stale header `Version` (was 0.13.0, behind the 0.14.x rows) to the current 0.15.0. |
| 2026-06-15 | 0.16.0 | Restructured the §2 per-case table: replaced the now-obsolete **Gap to PASS** column (all 10 cases are PASS, so there is no gap) with a **KPI** column for recording each case's measured KPI result. MCU-001 carries its measured result (**PASS** — 1 edit, 96 s ≤ 2 min); the other nine read *Not yet measured*. The per-case implementation evidence the old column held is preserved in this changelog (each case's PASS row). |
| 2026-06-17 | 0.17.0 | Recorded the measured KPI for **RTD-MEX-BASENXP-001** (issue #13 back-fill). Functional **PASS** re-confirmed under the TRUE black-box protocol — an independent vendor-gate re-run on the agent-produced `.mex` returned exit 0, 120 generated files, 0 SEVERE, with `OsIfUseSystemTimer=true` and exactly one `OsIfCounterConfig` referencing the Mcu `FLEXIO_CLK` (CORE_CLK) point (OsIf codegen emitted). **KPI: MISS** — 1 edit attempt (meets the single-attempt expectation), but validation-excluded time 134 s > the 1 min budget (total span ≈ 290 s, of which the S32DS `validate` runtime of 156 s is excluded per policy; the remaining cold-agent intent-analysis/planning/edit overhead dominates). Per the KPI policy the miss is recorded as-is and does not weaken the functional PASS. |
