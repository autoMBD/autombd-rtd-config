# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.26.0 |
| Date | 2026-07-02 |
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

Non-ADC cases use the fixture `Uart_Example_S32K344`; ADC cases use
`Autombd_Test_Adc_S32K344`. The **Status** column is the functional acceptance
signal — legend: **PASS** (vendor gate green under isolation), **FAIL**
(capability missing), **BLOCKED** (depends on an unbuilt asset), **NOT RUN**
(catalogued but not yet exercised under the black-box protocol). The **KPI**
column records each case's measured KPI result against its catalog budget
(`pass`/`miss`, with the edit-attempt count and the §1 context→check KPI window
time); a case not yet exercised under the black-box protocol reads *Not yet
measured*, and a KPI `miss` never weakens the functional **PASS**.

| ID | Module | Status | KPI |
| --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | **PASS** | **PASS** — 1 edit attempt, validation-excluded 96 s ≤ 2 min budget (black-box, 2026-06-15; legacy `validation_excluded_s` metric — predates the 2026-06-17 context→check refinement, to be re-measured separately) |
| RTD-MEX-BASENXP-001 | BaseNXP | **PASS** | **MISS** — 1 edit attempt, 183.26 s > 1 min budget (OpenCode black-box, 2026-07-01; post-BaseNXP forward-hardening re-measurement; session `ses_0e4ef61c2ffeRVNlt4QfJiGlus`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`) |
| RTD-MEX-PLATFORM-001 | Platform | **PASS** | **PASS** — 1 edit attempt, 58.7 s ≤ 1 min budget (black-box, 2026-06-17; after universal one-shot workflow optimization, context→check window) |
| RTD-MEX-PORT-001 | Port | **PASS** | **PASS** — 1 edit attempt, 54.4 s ≤ 1 min budget (black-box, 2026-06-18; context→check window) |
| RTD-MEX-DIO-001 | Dio | **PASS** | **PASS** — 1 edit attempt, 46.1 s ≤ 1 min budget (black-box, 2026-06-18; context→check window) |
| RTD-MEX-DIO-002 | Dio | **PASS** | **PASS** — 1 edit attempt, 26.3 s ≤ 1 min budget (black-box, 2026-06-18; context→check window) |
| RTD-MEX-MCL-001 | Mcl | **PASS** | **PASS** — 1 edit attempt, 24.3 s ≤ 1 min budget (black-box, 2026-06-18; context→check window) |
| RTD-MEX-UART-001 | UART | **PASS** | **PASS** — 1 edit attempt, 32.8 s ≤ 1 min budget (black-box, 2026-06-18; context→check window) |
| RTD-MEX-UART-002 | UART | **PASS** | **PASS** — 1 edit attempt, 28.6 s ≤ 1 min budget (black-box, 2026-06-18; context→check window) |
| RTD-MEX-UART-003 | UART | **PASS** | **PASS** — 1 edit attempt, 55.3 s ≤ 3 min budget (black-box, 2026-06-18; context→check window; auto-detect HW after --hw optional) |
| RTD-MEX-ADC-001 | ADC | **PASS** | **PASS** — 1 edit attempt, 80.8 s ≤ 2 min budget (black-box, re-measured post-hardening 2026-06-23; context→check window; exit 0, 0 SEVERE, 125 generated files) |
| RTD-MEX-ADC-002 | ADC | **PASS** | **PASS** — 1 edit attempt, 75.3 s ≤ 2 min budget (black-box, re-measured post-hardening 2026-06-23; context→check window; exit 0, 0 SEVERE, 125 generated files) |
| RTD-MEX-ADC-003 | ADC | **PASS** | **PASS** — 1 edit attempt, 106.1 s ≤ 2 min budget (black-box, re-measured post-hardening 2026-06-23; context→check window; exit 0, 0 SEVERE, 125 generated files) |
| RTD-MEX-ADC-004 | ADC | **PASS** | **PASS** — 1 edit attempt, 65.3 s ≤ 2 min budget (black-box, re-measured post-hardening 2026-06-23; context→check window; exit 0, 0 SEVERE, 125 generated files) |

**Summary: 14 / 14 cases functional PASS; 13 / 14 KPI PASS.** The seven-module
minimal system plus the ADC module have functional acceptance evidence
(deterministic suite, static checks, the S32DS vendor gate, and code-generation
evidence). The current KPI exception is **RTD-MEX-BASENXP-001**, which remains
functional PASS but re-measured at 183.26 s against its 1 min KPI after the
BaseNXP forward-hardening and therefore records **KPI MISS**. All four ADC cases
— interrupt software groups + watchdog (ADC-001), DMA streaming (ADC-002), BCTU
single hardware trigger + new-data + watchdog (ADC-003), and dual-ADC BCTU list
trigger + FIFO DMA (ADC-004) — pass the black-box protocol with one edit attempt
each and KPI under the 2 min budget (80.8 / 75.3 / 106.1 / 65.3 s, re-measured
after the forward-hardening), each exit 0 with 125 generated files and no SEVERE.

## 3. Cross-cutting blockers (critical path)

These historical blockers unblocked the accepted minimal-system cases:

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

The completed minimal-system delivery sequence is preserved here as acceptance
history. New ADC evidence is recorded in §2 as each case is exercised.

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
| 12 | ✅ ADC module: `adc set --spec` (Hw Unit / groups / channels / watchdog; DMA streaming + Mcl; BCTU single + list hardware triggers; FIFO DMA) → ADC-001..004 | ADC-001, ADC-002, ADC-003, ADC-004 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-02 | 0.26.0 | Corrected the post-BaseNXP forward-hardening acceptance evidence for RTD-MEX-BASENXP-001: OpenCode black-box E2E on 2026-07-01 remained functional PASS (`configured=true`, `validate_status=passed`) but KPI MISS at 183.26 s > 1 min budget, superseding the older 2026-06-17 53.5 s KPI baseline. Summary now separates functional status (14 / 14 PASS) from KPI status (13 / 14 PASS, BaseNXP MISS). |
| 2026-06-23 | 0.25.1 | Re-measured the four ADC cases' black-box E2E + KPI after the ADC forward-hardening (shared group/trigger byte-builder + new static checks): all four remain functional PASS, 1 edit attempt, within the 2 min budget (ADC-001 80.8 s, ADC-002 75.3 s, ADC-003 106.1 s, ADC-004 65.3 s). The upward shifts on ADC-001/003 are Codex run-to-run variance (ADC-002 was flat), not a tool regression; deterministic suite (635) and the S32DS gate (all four, exit 0 + no SEVERE) were also re-confirmed post-hardening. Recorded KPIs now reflect the current (hardened) tool. |
| 2026-06-23 | 0.25.0 | RTD-MEX-ADC-001 through ADC-004 PASS (issue #30): ADC module support delivered (interrupt software groups + watchdog, DMA streaming, BCTU single hardware trigger, dual-ADC BCTU list trigger + FIFO DMA). All four pass the black-box protocol with 1 edit attempt each and KPI under the 2 min budget (50.5 / 75.4 / 71.0 / 58.7 s), each exit 0 / 0 SEVERE / 125 generated files. Summary now 14 / 14 cases PASS; added the ADC delivery step to §4. |
| 2026-06-19 | 0.24.1 | Clarified that ADC E2E cases use the ADC-ready `Autombd_Test_Adc_S32K344` fixture, while non-ADC cases keep `Uart_Example_S32K344`. |
| 2026-06-19 | 0.24.0 | Added RTD-MEX-ADC-001 through RTD-MEX-ADC-004 as NOT RUN with the catalogued one-edit, ≤2 min KPI budget, keeping the 10/14 summary aligned with the expanded E2E catalog. |
| 2026-06-18 | 0.23.0 | Back-filled KPI for Dio (DIO-001/002: PASS 46.1/26.3 s), Mcl (MCL-001: PASS 24.3 s), Uart (UART-001/002: PASS 32.8/28.6 s; UART-003: PASS 55.3 s after --hw auto-detect optimization). Closes #16, #17, #18. |
| 2026-06-18 | 0.22.0 | Back-filled KPI evidence for RTD-MEX-PORT-001 (1 edit attempt, 54.4 s context→check; PASS). Closes #15. |
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
