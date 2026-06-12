# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.7.0 |
| Date | 2026-06-12 |
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
| RTD-MEX-MCU-001 | MCU | **PASS** | `mcu set --core-clk 160 --aips-plat-clk 80 --aips-slow-clk 40 --add-all-clock-reference-points`: configures the PLL (FXOSC 16MHz → VCO 960 → PHI0 160) + MC_CGM dividers (CORE/1, AIPS_PLAT/2, AIPS_SLOW/4, HSE/2), sets McuNoPll=false + the McuPll0UnderMcuControl mirror, and **merges** the Clock Reference Points (preserves LPUART3_CLK/FLEXIO_CLK + adds 13 selectable clocks → 15). Vendor gate green incl. the comprehensive Problems-view scan (no HSE_CLK>120MHz); generated `Clock_Ip_PBcfg.c` has CORE_CLK=160000000U / AIPS_PLAT=80000000U / AIPS_SLOW=40000000U. Took 3 refine iterations driven by the vendor gate. |
| RTD-MEX-BASENXP-001 | BaseNXP | **PASS** | `basenxp set --enable-system-timer`: sets `OsIfUseSystemTimer=true` and **inserts** one `OsIfCounterConfig` whose `OsIfSystemTimerClockRef` references the Mcu `FLEXIO_CLK` (CORE_CLK) reference point, with `OsIfSystemTimerClockFreq` an empty array (both are ArraySettings — scalar freq is rejected). Vendor gate green (exit 0, 120 files, no severe), 14-line narrow edit. Drove the byte-faithful element-insertion writer. |
| RTD-MEX-PLATFORM-001 | Platform | **PASS** | `platform set --peripheral LPUART_3 --priority 2`: `IsrPriority` 0→2 on the existing `LPUART3_IRQn` entry, kept enabled with its ISR (`LPUART_UART_IP_3_IRQHandler`) registered, FLEXIO entry untouched. Vendor gate green (exit 0, 120 generated files, no severe). |
| RTD-MEX-PORT-001 | Port | **PASS** | `port set --peripheral LPUART_0 --tx PTA27 --rx PTA28`: validates pins against pins.json (rejects illegal pins), then inserts BOTH representations — the `<pin>` header (`lpuart0_tx`@M2 + `direction=OUTPUT`; `lpuart0_rx`@N2) and the Port `PortPin` structs (`Lpuart0_Tx`/`Lpuart0_Rx`, next `PortPinId`). Vendor gate green (exit 0, 120 files, no severe); generated `Siul2_Port_Ip_PBcfg.c` confirms PTA27 ALT4/TX + PTA28 IMCR/RX. |
| RTD-MEX-DIO-001 | Dio | **PASS** | `dio set --add-channel LED_CTRL --pin PTA5` (cross-module Dio+Port): inserts the DioChannel (`DioChannelId`=mscr%16=5 in DioPort_0) AND the Port GPIO pin (`<pin>` SIUL2 gpio,5 OUTPUT + PortPin struct), clearing the Dio `config_set` `quick_selection` so codegen emits the channel. Vendor gate green; generated `Dio_Cfg.h` has `DioConf_DioChannel_LED_CTRL ((uint16)0x0005U)` and SIUL2 configures PTA5 as GPIO output. |
| RTD-MEX-MCL-001 | Mcl | **PASS** | `mcl set --add-flexio-logic-channel FLEXIO_UART_CH0`: appends a third `FlexioMclLogicChannels` struct with a dynamically-computed unique `FlexioMclChannelId=CHANNEL_2`/`FlexioMclPinId=PIN_2` (referenceable as `/Mcl/Mcl/MclConfig/FlexioCommon_0/FLEXIO_UART_CH0`); existing UART_TX/UART_RX untouched. Vendor gate green (exit 0, 120 files, no severe), 9-line narrow edit. |
| RTD-MEX-UART-001 | UART | FAIL | `uart set` edits an existing channel's hw/method/baud only. Needs parity/stop/word-length/callback, instance switch to LPUART_8, **and cross-module execution** (Platform ISR + MCU ref clock + priority) — currently only *declared*, never written. |
| RTD-MEX-UART-002 | UART | FAIL | Needs FlexIO Uart channel **creation** + MCL logic-channel reference + Platform ISR (LPUART & FlexIO) — creation + orchestration both missing. |
| RTD-MEX-UART-003 | UART | FAIL | DMA is rejected (`unsupported_uart_mode`); needs Uart DMA method + MCL DMA channel/instance + Platform ISR. |

**Summary: 6 / 9 cases PASS** (PLATFORM-001, BASENXP-001, MCL-001, PORT-001,
DIO-001, MCU-001). All six non-UART modules now have an accepted, vendor- and
codegen-verified capability. Remaining: the three UART cases (UART-001/002/003),
which exercise the full cross-module orchestration (Uart channel + Platform ISR
+ MCU clock + MCL FlexIO/DMA) and the new DMA capability.

## 3. Cross-cutting blockers (critical path)

These unblock multiple cases and should land before/with per-module work:

1. ✅ **Byte-faithful element insertion** — DONE. `document.py
   replace_element_region` splices a new element region (self-closed → populated)
   and re-captures spans; the attribute-edit path is untouched. Proven by
   BASENXP-001 (OsIf counter insertion) with a direct regression test.
2. **Cross-module orchestration execution.** *Pattern proven by DIO-001* (one
   command writes both the Dio channel and the Port GPIO pin, declaring the Port
   dependency). The UART cases need the larger orchestration — a Uart channel
   edit must also write the Platform ISR, the MCU clock ref, and (FlexIO) the MCL
   channel. Still to do for UART-001/002/003.
3. ✅ **`pins.json` rebuild** — DONE. 2091 real signals built from the IOMUX
   workbook via a committed stdlib tool (`tools/build_pins_s32k3.py`);
   `pin-options` returns verified pins. A Port `apply` path is still needed to
   *write* a queried pin (gates PORT-001, DIO-001).
4. **DMA capability** (UART-003).
5. **CLI surface** for `mcu`/`port`/`dio`/`mcl` — `uart`, `platform`, `basenxp`
   are wired (plus `inspect`/`check`/`validate`/`pin-options`).

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
| 9 | UART cross-module orchestration (apply declared deps) → UART-001 | UART-001 |
| 10 | UART-002: FlexIO channel creation + MCL ref + ISR | UART-002 |
| 11 | DMA capability (Uart + Mcl + Platform) → UART-003 | UART-003 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-11 | 0.1.0 | Created the acceptance report (the catalog's pass/fail record). Recorded the repaired vendor gate (Flow B, operational + error-detecting + project-safe), the honest 0/9 per-case baseline with each gap, the cross-cutting critical-path blockers, and the sequenced execution plan. |
| 2026-06-11 | 0.2.0 | RTD-MEX-PLATFORM-001 **PASS** (1/9): `platform set` edits an existing `PlatformIsrConfig` priority/enable on the LPUART3 interrupt; verified end-to-end against the real S32DS gate (exit 0, 120 generated files, no severe). Marked plan step 3 done. |
| 2026-06-11 | 0.3.0 | RTD-MEX-BASENXP-001 **PASS** (2/9): `basenxp set --enable-system-timer` inserts an OsIf counter referencing the Mcu CORE_CLK point (FLEXIO_CLK), vendor-gate green; drove the byte-faithful element-insertion writer (blocker #1 DONE) and landed the complete 2091-signal `pins.json` (blocker #3 DONE). Updated the per-case table, cross-cutting blockers, and execution plan. |
| 2026-06-11 | 0.4.0 | RTD-MEX-MCL-001 **PASS** (3/9): `mcl set --add-flexio-logic-channel` appends a FlexIO logic channel with a dynamically-computed unique ChannelId/PinId, vendor-gate green (9-line narrow insert). Marked plan step 5 done. |
| 2026-06-12 | 0.5.0 | RTD-MEX-PORT-001 **PASS** (4/9): `port set` validates a pin against pins.json then inserts both the `<pin>` header and the Port `PortPin` struct; vendor gate green and the generated SIUL2 source reflects the pins. Review hardening fixed a shared-writer same-prefix tag-matching bug (`<pin>` vs `<pin_features>`) that could have forced whole-file reserialization. Marked plan step 7 done. |
| 2026-06-12 | 0.6.0 | RTD-MEX-DIO-001 **PASS** (5/9): `dio set` (cross-module Dio+Port) inserts the DioChannel + the Port GPIO output pin and clears the Dio `config_set` `quick_selection` so codegen emits the channel; vendor gate green and `Dio_Cfg.h` contains `DioConf_DioChannel_LED_CTRL`. Established the codegen-verification gate step (LL-013) and confirmed MCL-001 codegen. Marked plan step 8 done. |
| 2026-06-12 | 0.7.0 | RTD-MEX-MCU-001 **PASS** (6/9): `mcu set` configures the 160/80/40 clock tree (PLL + MC_CGM dividers incl. HSE_CLK/2), McuNoPll/mirror fixes, and merges the Clock Reference Points; vendor + codegen verified over 3 vendor-driven refine iterations. Established LL-014 (comprehensive Problems-view SEVERE scan for clock cases). All 6 non-UART modules done; remaining UART-001/002/003. |
