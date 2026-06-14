# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.13.0 |
| Date | 2026-06-13 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Current pass/fail evidence for the E2E acceptance cases defined in `rtd-config-test-cases.md`. This document is the living status record the catalog points to; the catalog defines the target, this records where the tool actually stands. |

> **Governed by [`rtd-config-test-cases.md`](rtd-config-test-cases.md)** (the case
> catalog and isolation protocol) and
> [`rtd-config-test-strategy.md`](rtd-config-test-strategy.md) (layers, the vendor
> pass gate, roles, KPI monitoring). Per-module truth comes from each
> `<Module>.xdm`; the cross-cutting S32DS flow/gate lives in
> [`../specs/rtd-config-domain-truth.md`](../specs/rtd-config-domain-truth.md).

## 1. Acceptance gate status

The functional gate is the **sole acceptance signal** for an E2E case (exit `0`,
code generated, no SEVERE `[TOOL] … has the following error`, and the case pass
criteria met). KPI is monitored separately. If the functional gate passes but
KPI misses, the case returns to the Worker for KPI optimization, capped at three
optimization iterations; after the third KPI miss, this report records the true
KPI result and the case may proceed with its functional PASS evidence.

| Item | Status | Evidence |
| --- | --- | --- |
| S32DS headless validation operational | **OPERATIONAL (fixed 2026-06-11)** | Flow B verified on S32DS 3.6.7; pristine `Uart_Example_S32K344` → exit `0`, 120 generated files, `severe_problems: []` via `python -m rtd_config validate`. |
| Pass gate detects real errors | **VERIFIED** | Known-bad probe (`OsIfUseSystemTimer=true`, empty `OsIfCounterConfig`) → SEVERE `[TOOL] The resource "BaseNXP" … has the following error: The number of OsIf Counters must be exactly one …`; gate returns `passed=false`. |
| Caller project safety | **VERIFIED** | After validation the caller's `.mex` is byte-identical (validation runs on a throwaway copy). |
| KPI evidence policy | **DEFINED (2026-06-13)** | Each isolated case records elapsed time, edit-attempt count, KPI status (`pass`, `miss`, or `miss-after-3`), optimization-iteration count, and final disposition. |

> **Why this matters:** before the fix, the gate failed on *every* input — the
> registration step timed out, so a pristine fixture returned exit `2`. The
> deterministic suite gates the vendor path behind
> `RTD_CONFIG_RUN_S32DS_VALIDATION` (off by default), so "44 passed" never proved
> any `.mex` was vendor-valid. With the gate now trustworthy, the remaining work
> is per-module capability, each provable against it.

## 2. Per-case status

All cases use the fixture `Uart_Example_S32K344`. Status legend: **PASS** (vendor
gate green under isolation), **FAIL** (capability missing), **BLOCKED** (depends
on an unbuilt asset). New evidence entries must also record KPI status. Historic
entries below predate the explicit KPI-evidence policy unless a row states a
measured KPI result.

| ID | Module | Status | Gap to PASS |
| --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | **PASS** | `mcu set --core-clk 160 --aips-plat-clk 80 --aips-slow-clk 40 --add-all-clock-reference-points`: configures the PLL (FXOSC 16MHz → VCO 960 → PHI0 160) + MC_CGM dividers (CORE/1, AIPS_PLAT/2, AIPS_SLOW/4, HSE/2), sets McuNoPll=false + the McuPll0UnderMcuControl mirror, and **merges** the Clock Reference Points (preserves LPUART3_CLK/FLEXIO_CLK + adds 13 selectable clocks → 15). Vendor gate green incl. the comprehensive Problems-view scan (no HSE_CLK>120MHz); generated `Clock_Ip_PBcfg.c` has CORE_CLK=160000000U / AIPS_PLAT=80000000U / AIPS_SLOW=40000000U. Took 3 refine iterations driven by the vendor gate. |
| RTD-MEX-BASENXP-001 | BaseNXP | **PASS** | `basenxp set --enable-system-timer`: sets `OsIfUseSystemTimer=true` and **inserts** one `OsIfCounterConfig` whose `OsIfSystemTimerClockRef` references the Mcu `FLEXIO_CLK` (CORE_CLK) reference point, with `OsIfSystemTimerClockFreq` an empty array (both are ArraySettings — scalar freq is rejected). Vendor gate green (exit 0, 120 files, no severe), 14-line narrow edit. Drove the byte-faithful element-insertion writer. |
| RTD-MEX-PLATFORM-001 | Platform | **PASS** | `platform set --peripheral LPUART_3 --priority 2`: `IsrPriority` 0→2 on the existing `LPUART3_IRQn` entry, kept enabled with its ISR (`LPUART_UART_IP_3_IRQHandler`) registered, FLEXIO entry untouched. Vendor gate green (exit 0, 120 generated files, no severe). |
| RTD-MEX-PORT-001 | Port | **PASS** | `port set --peripheral LPUART_0 --tx PTA27 --rx PTA28`: validates pins against pins.json (rejects illegal pins), then inserts BOTH representations — the `<pin>` header (`lpuart0_tx`@M2 + `direction=OUTPUT`; `lpuart0_rx`@N2) and the Port `PortPin` structs (`Lpuart0_Tx`/`Lpuart0_Rx`, next `PortPinId`). Vendor gate green (exit 0, 120 files, no severe); generated `Siul2_Port_Ip_PBcfg.c` confirms PTA27 ALT4/TX + PTA28 IMCR/RX. |
| RTD-MEX-DIO-001 | Dio | **PASS** | `dio set --add-channel LED_CTRL --pin PTA5` (cross-module Dio+Port): inserts the DioChannel (`DioChannelId`=mscr%16=5 in DioPort_0) AND the Port GPIO pin (`<pin>` SIUL2 gpio,5 OUTPUT + PortPin struct), clearing the Dio `config_set` `quick_selection` so codegen emits the channel. Vendor gate green; generated `Dio_Cfg.h` has `DioConf_DioChannel_LED_CTRL ((uint16)0x0005U)` and SIUL2 configures PTA5 as GPIO output. |
| RTD-MEX-DIO-002 | Dio | **PASS** | `dio set --add-channel LED_CTRL --pin PTA30` on a pin whose DioPort container is ABSENT: **auto-creates `DioPort_1`** (DioPortId=1, array index 1 — the struct name/`Name` use the array index, `DioPortId` is computed `mscr//16`) then inserts the channel (`DioChannelId`=mscr%16=14), clearing the Dio `config_set` `quick_selection`. Vendor gate green under isolation (exit 0, 120 files, no severe); generated `Dio_Cfg.h` has `DioConf_DioChannel_LED_CTRL ((uint16)0x001eU)` and `DioConf_DioPort_DioPort_1 ((uint8)0x01U)`. Proven cold (auto-discovery) on the focused case AND the full 5-task combined scenario (LL-019). |
| RTD-MEX-MCL-001 | Mcl | **PASS** | `mcl set --add-flexio-logic-channel FLEXIO_UART_CH0`: appends a third `FlexioMclLogicChannels` struct with a dynamically-computed unique `FlexioMclChannelId=CHANNEL_2`/`FlexioMclPinId=PIN_2` (referenceable as `/Mcl/Mcl/MclConfig/FlexioCommon_0/FLEXIO_UART_CH0`); existing UART_TX/UART_RX untouched. Vendor gate green (exit 0, 120 files, no severe), 9-line narrow edit. |
| RTD-MEX-UART-001 | UART | **PASS** | `uart set --hw LPUART_8 --baud 921600 --parity none --stop-bits 1 --word-length 8 --callback Autombd_UartCallback --priority 2`: edits the channel (incl. UartClockRef→LPUART8_CLK) + module callback, AND orchestrates the cross-module deps — inserts the Platform ISR (`LPUART8_IRQn`/`LPUART_UART_IP_8_IRQHandler`/prio 2) and the Mcu clock ref (`LPUART8_CLK`→AIPS_PLAT_CLK). `changed_modules=[uart,platform,mcu]`. Vendor + 3-module codegen verified (HW channel 8U/921600/Autombd_UartCallback; LPUART8 ISR; LPUART8_CLK). Instance→IRQ/handler/clock map computed (anti-hardcode tested). |
| RTD-MEX-UART-002 | UART | **PASS** | `uart add-flexio-channel --baud 921600`: creates 2 MCL FlexIO logic channels (UART2_TX/CHANNEL_2, UART2_RX/CHANNEL_3) + 2 FlexIO Uart channels (UartChannelId 3/4, FLEXIO_IP, bitCount 8, interrupt, the `UartHwChannelRef`s matching the new MCL names) + module callback; ensures the shared `FLEXIO_IRQn`/`FLEXIO_CLK` (idempotent). Vendor + end-to-end codegen verified (`MCL_FLEXIOCOMMON_0_UART2_TX=CHANNEL_2`; FlexIO channel configs reference them; callback present). `changed_modules=[uart,mcl]`. |
| RTD-MEX-UART-003 | UART | **PASS** | `uart set --hw LPUART_3 --mode dma --callback Autombd_UartCallback`: the new DMA capability — Uart `UartInteruptDmaMethod=USING_DMA` + `UartDmaEnable` + Tx/Rx refs to MCL DMA channels + callback; MCL `MclEnableDma` + activate `dmaLogicChannel_Type_0` (TX) + add `_1` (RX) with `enDmaRequest`/`enDmaMajorInterrupt`; Platform `DMATCD0/1_IRQn`→`Dma0_Ch0/1_IRQHandler`. Vendor + 4-module codegen verified (built with no end-to-end vendor example; S32DS gate the authority). `changed_modules=[uart,mcl,platform]`. `_check_dma` now enforces the DMA INVALID rule. |

**Summary: 10 / 10 cases PASS — the seven-module minimal system is COMPLETE**
(RTD-MEX-DIO-002 added as black-box round-2 hardening). All seven modules
(Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart) reach the full acceptance bar:
deterministic suite (467 tests green), static checks, the S32DS vendor gate
(exit 0 + no SEVERE `[TOOL]` + code generated), AND each E2E case's generated
code verified to reflect the edit (LL-013). Every case also passed independent
Reviewer acceptance with its findings closed. The five cross-cutting blockers
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

Each module runs the per-module delivery checklist in
`docs/plans/rtd-cfgfile-cli-implementation-plan.md` (Explorer → Worker → Tester →
Reviewer), proven against the now-operational gate.

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
