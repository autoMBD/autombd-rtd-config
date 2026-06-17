# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.21.0 |
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
| KPI evidence policy | **DEFINED (2026-06-13; metric refined 2026-06-17)** | Each isolated case records its edit-attempt count, the measured KPI, the KPI status (`pass`/`miss`), and the disposition. The canonical KPI is the **`[context-injected → static-check-passed]` window** — intent analysis + planning + implementation + file editing, as the user perceives it — emitted first-class by `tools/blackbox_e2e.py` (`kpi.kpi_seconds`). It **excludes** the agent-runner startup before the prompt lands AND everything after the static `check` (the vendor `validate` runtime and the trailing report). The older `validation_excluded_s` (`total_span` − `validate`) is retained only as a diagnostic; it over-counts and is not the KPI. |

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
catalog budget (`pass`/`miss`, with the edit-attempt count and the §1
context→check KPI window time); a case not yet exercised under the black-box protocol
reads *Not yet measured*, and a KPI `miss` never weakens the functional **PASS**.

| ID | Module | Status | KPI |
| --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | **PASS** | **PASS** — 1 edit attempt, validation-excluded 96 s ≤ 2 min budget (black-box, 2026-06-15; legacy `validation_excluded_s` metric — predates the 2026-06-17 context→check refinement, to be re-measured separately) |
| RTD-MEX-BASENXP-001 | BaseNXP | **PASS** | **PASS** — 1 edit attempt, 53.5 s ≤ 1 min budget (black-box, 2026-06-17; after one-shot SKILL.md optimization, context→check window) |
| RTD-MEX-PLATFORM-001 | Platform | **PASS** | **PASS** — 1 edit attempt, 58.7 s ≤ 1 min budget (black-box, 2026-06-17; after universal one-shot workflow optimization, context→check window) |
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
| 2026-06-17 | 0.21.0 | Compressed changelog: retained all versions, condensed descriptions to 1–2 lines. |
| 2026-06-17 | 0.20.0 | Universal one-shot workflow in SKILL.md replaces per-module recipes. PLATFORM-001 KPI PASS (58.7 s). |
| 2026-06-17 | 0.19.0 | PLATFORM-001 KPI baseline: MISS at 73.3 s (11 commands). Functional PASS reconfirmed. |
| 2026-06-17 | 0.18.0 | KPI metric refined to `[context-injected → static-check-passed]` window. BASENXP-001 KPI PASS (53.5 s). |
| 2026-06-17 | 0.17.0 | BASENXP-001 KPI first measured: MISS at 134 s validation-excluded. Functional PASS reconfirmed. |
| 2026-06-15 | 0.16.0 | Replaced Gap-to-PASS column with KPI column in per-case table. |
| 2026-06-15 | 0.15.0 | First KPI measured: MCU-001 96 s ≤ 2 min (PASS) under black-box protocol. |
| 2026-06-15 | 0.14.1 | De-agented KPI policy: removed `miss-after-3`; KPI status is `pass`/`miss`. |
| 2026-06-15 | 0.14.0 | Issue #7 doc reorganization: removed stale KPI-cap clause and implementation-plan pointer. |
| 2026-06-14 | 0.13.0 | Vendor gate strengthened: catches Clocks/Peripherals/Pins SEVERE that previously exit-0'd. |
| 2026-06-14 | 0.12.0 | RTD-MEX-DIO-002 PASS: DioPort auto-creation on PTA30 (DioPort_1 → DioChannelId 14). |
| 2026-06-13 | 0.11.0 | Added KPI evidence policy: miss triggers up to 3 optimization iterations, then recorded. |
| 2026-06-13 | 0.10.0 | RTD-MEX-UART-003 PASS. DMA capability complete — all 9 cases PASS, minimal system COMPLETE. |
| 2026-06-13 | 0.9.0 | RTD-MEX-UART-002 PASS: `uart add-flexio-channel` creates FlexIO Tx+Rx with MCL refs. |
| 2026-06-12 | 0.8.0 | RTD-MEX-UART-001 PASS: `uart set` 3-module orchestration (Uart + Platform + Mcu). |
| 2026-06-12 | 0.7.0 | RTD-MEX-MCU-001 PASS: 160/80/40 clock tree over 3 vendor refine iterations. |
| 2026-06-12 | 0.6.0 | RTD-MEX-DIO-001 PASS: DioChannel + Port GPIO (cross-module). Codegen verification gate (LL-013). |
| 2026-06-12 | 0.5.0 | RTD-MEX-PORT-001 PASS: pin validation + PortPin insert. Fixed `<pin>` vs `<pin_features>` tag bug. |
| 2026-06-11 | 0.4.0 | RTD-MEX-MCL-001 PASS: FlexIO logic channel with computed ChannelId/PinId. |
| 2026-06-11 | 0.3.0 | RTD-MEX-BASENXP-001 PASS: OsIf counter insertion. Byte-faithful element insertion + pins.json. |
| 2026-06-11 | 0.2.0 | RTD-MEX-PLATFORM-001 PASS (1/9): `platform set` edits PlatformIsrConfig priority/enable. |
| 2026-06-11 | 0.1.0 | Created the acceptance report with per-case table, blockers, execution plan. |
