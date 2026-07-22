# RTD CfgFile CLI Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.35.1 |
| Date | 2026-07-22 |
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
| KPI evidence policy | **DEFINED (2026-06-13; metric refined 2026-06-17)** | Each isolated case records its edit-attempt count, the measured KPI, the KPI status (`pass`/`miss`), and the disposition. The canonical KPI is the **`[context-injected → static-check-passed]` window** — intent analysis + planning + implementation + file editing, as the user perceives it — emitted first-class by `tools/blackbox_e2e.py` (`kpi.kpi_seconds`). It **excludes** runner startup before the request lands AND everything after the static `check` (the vendor `validate` runtime and the trailing report). The older `validation_excluded_s` (`total_span` − `validate`) is retained only as a diagnostic; it over-counts and is not the KPI. |

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
| RTD-MEX-MCU-001 | MCU | **PASS** | **PASS** — 1 edit attempt, 40.59 s ≤ 2 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening; context→check window; harness exit 0; session `ses_0948687ebffepZ0HI158uyNPeC`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-BASENXP-001 | BaseNXP | **PASS** | **PASS** — 1 edit attempt, 27.91 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening; context→check window; harness exit 0; session `ses_09478bda3ffeVvQRfk4oEIyFt5`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-PLATFORM-001 | Platform | **PASS** | **PASS** — 1 edit attempt, 22.78 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening and terminal-result parser fix; context→check window; harness exit 0; session `ses_0946dfbe1ffeGvZfh0pRGPwKxO`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-PORT-001 | Port | **PASS** | **PASS** — 1 edit attempt, 31.05 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening with the one-query pin fast path; context→check window; harness exit 0; session `ses_0945f5af3ffeXKlBX9LYA0uwiO`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-DIO-001 | Dio | **PASS** | **PASS** — 1 edit attempt, 43.43 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening; context→check window; harness exit 0; session `ses_0945d5d17ffe5UO4vLDmsSKP6G`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-DIO-002 | Dio | **PASS** | **PASS** — 1 edit attempt, 24.43 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening; context→check window; harness exit 0; session `ses_0945b4186ffe0i2t9Lj6L6sxV8`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-MCL-001 | Mcl | **PASS** | **PASS** — 1 edit attempt, 42.27 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 after the complete shared Mcl DMA ownership fix; context→check window; harness exit 0; session `ses_0942cdf08ffeYlYQVIRBG9BoUO`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-UART-001 | UART | **PASS** | **PASS** — 1 edit attempt, 38.51 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening; context→check window; harness exit 0; session `ses_09456a096ffeSBL6zPyPJheXiu`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-UART-002 | UART | **PASS** | **PASS** — 1 edit attempt, 26.77 s ≤ 1 min budget (OpenCode black-box, 2026-07-16–17 P1 #65–#72 final hardening; context→check window; harness exit 0; session `ses_09454a15bffeofD1BhzRnqAokJ`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-UART-003 | UART | **PASS** | **PASS** — 1 edit attempt, 37.82 s ≤ 3 min budget (OpenCode black-box, 2026-07-16–17 after the complete shared Mcl DMA ownership fix; context→check window; harness exit 0; session `ses_0942a5304ffeo7lPf8Iug1Gyiq`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 120 files) |
| RTD-MEX-ADC-001 | ADC | **PASS** | **PASS** — 1 edit attempt, 58.92 s ≤ 2 min budget (OpenCode black-box, 2026-07-16–17 after ADC/Mcl ownership and coverage hardening; context→check window; harness exit 0; session `ses_094282e2bffexbQSJvZIOCyb38`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 125 files) |
| RTD-MEX-ADC-002 | ADC | **PASS** | **PASS** — 1 edit attempt, 28.89 s ≤ 2 min budget (OpenCode black-box, 2026-07-16–17 after ADC/Mcl ownership and coverage hardening; context→check window; harness exit 0; session `ses_0942501d7ffe9xd7M0fr4DO9SR`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 125 files) |
| RTD-MEX-ADC-003 | ADC | **PASS** | **PASS** — 1 edit attempt, 35.84 s ≤ 2 min budget (OpenCode black-box, 2026-07-16–17 after ADC/Mcl ownership and coverage hardening; context→check window; harness exit 0; session `ses_0942323d5fferxMjnqQ38GWEqb`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 125 files) |
| RTD-MEX-ADC-004 | ADC | **PASS** | **PASS** — 1 edit attempt, 26.64 s ≤ 2 min budget (OpenCode black-box, 2026-07-16–17 after ADC/Mcl ownership and coverage hardening; context→check window; harness exit 0; session `ses_094212cbbffe47p4N1UDE41wFw`; `BLACKBOX_RESULT configured=true`, `validate_status=passed`; independent S32DS exit 0, 0 SEVERE, 125 files) |

**Summary: 14 / 14 functional PASS and 14 / 14 KPI PASS.** Every case has
current OpenCode black-box evidence after the P1 #65–#72 hardening, and every
resulting project independently passes the S32DS gate (exit 0 and no SEVERE
`[TOOL]`). Port converged after replacing an incomplete pin selector example
with the one-query bundle fast path. ADC-002 exposed a real
cross-module ownership gap on Mcl `quick_selection`; the shared Mcl DMA target
set, per-unit DMA detection, single-unit FIFO-DMA path, and descriptor coverage
were hardened before all affected Mcl/Uart/ADC cases were rerun.

## 3. Cross-cutting blockers (critical path)

These historical blockers unblocked the accepted minimal-system cases:

1. ✅ **Byte-faithful element insertion** — DONE. `document.py
   replace_element_region` splices a new element region (self-closed → populated)
   and re-captures spans; the attribute-edit path is untouched. Proven by
   BASENXP-001 (OsIf counter insertion) with a direct regression test.
2. ✅ **Cross-module dependency execution** — DONE. DIO-001 proved the pattern
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
| 9 | ✅ UART cross-module dependency execution → UART-001 | UART-001 |
| 10 | ✅ UART-002: FlexIO channel creation + MCL ref + ISR | UART-002 |
| 11 | ✅ DMA capability (Uart + Mcl + Platform) → UART-003 | UART-003 |
| 12 | ✅ ADC module: `adc set --spec` (Hw Unit / groups / channels / watchdog; DMA streaming + Mcl; BCTU single + list hardware triggers; FIFO DMA) → ADC-001..004 | ADC-001, ADC-002, ADC-003, ADC-004 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-17 | 0.35.0 | Refreshed all 14 OpenCode black-box E2E/KPI cases after P1 #65–#72. Final status is 14/14 functional PASS and 14/14 KPI PASS, each with one edit and an independent S32DS pass. The evidence includes the terminal result-parser fix, the Port one-query pin fast path, and the complete ADC/Mcl DMA ownership + coverage fix; ADC-002 now passes in one edit at 28.89 s after the ownership gap had previously required a second edit. |
| 2026-07-12 | 0.34.0 | Refreshed all 14 OpenCode black-box E2E/KPI cases after #75's P0 release-safety hardening. All functional gates pass and all KPIs pass. ADC-003 initially produced a functional PASS but a KPI MISS because the first spec omitted the target-channel group required by BCTU single conversion; `adc-spec.md` 0.1.1 now shows the complete ADC1/S10 BCTU + watchdog payload, and ADC-003 re-measured PASS at 23.59 s / 1 edit / session `ses_0ac364610ffeylFcv48cIK5TRv`. |
| 2026-07-07 | 0.33.0 | Refreshed the post-review OpenCode black-box evidence that was stale in 0.32.0. Mcl now passes at 54.78 s / 1 edit / session `ses_0c4bcc13effejDypVDWraYJm6y`. UART-002 initially missed after the Mcl allocator fix (113.74 s), then missed the boundary after fast-path guidance (60.01 s), and passed after promoting the UART-002 reference fast path to the top of `uart-spec.md` (32.21 s / 1 edit / session `ses_0c4afe382ffeT485KxDapiIIPC`). Summary returns to 14 / 14 functional PASS and 14 / 14 KPI PASS. |
| 2026-07-04 | 0.32.0 | Recorded the true post-review validation state after fixing Mcl allocator legality and tightening the OpenCode KPI workflow. Platform re-measured KPI PASS at 49.10 s / 1 edit / session `ses_0d24f1e42ffeInbRFKaREs776x` after removing source/explore/inspect behavior. Mcl and UART-002 evidence is explicitly marked stale pending fresh OpenCode reruns; the rerun is blocked by OpenCode usage-limit/escalation and a workspace-XDG hang. |
| 2026-07-04 | 0.31.0 | Completed real KPI optimization for Platform and Mcl after the 0.30.0 misses. Platform route handling now treats interrupt priority/enablement/ISR registration as `platform` even when the prompt names LPUART; Mcl now has a tested Mcl-only FlexIO logic-channel fast path. Fresh OpenCode black-box E2E: Platform 31.66 s / 1 edit / session `ses_0d277eb15ffeJWEohdcCnm7ktA`; Mcl 40.01 s / 1 edit / session `ses_0d274c51affePwH9ymXYM4TWUQ`. Summary returns to 14 / 14 functional PASS and 14 / 14 KPI PASS. |
| 2026-07-04 | 0.30.0 | Split module payload examples out of `SKILL.md` into per-module `autombd-rtd/reference/` docs and refreshed all 14 OpenCode black-box E2E/KPI cases. Functional status is 14 / 14 PASS; KPI status is 12 / 14 PASS. Platform (87.29 s) and Mcl (94.39 s) remain true KPI MISS after three optimization iterations; UART-001 and ADC-003 converged during KPI optimization. |
| 2026-07-03 | 0.29.0 | Issue #53 unified module configuration around structured `--spec` input. Refreshed all 14 OpenCode black-box E2E/KPI cases post-CLI/skill change: all functional PASS, all KPI PASS. DIO-002 needed KPI optimization iteration 1 after an initial 2-edit-attempt run; final evidence is 31.41 s / 1 edit attempt. |
| 2026-07-03 | 0.28.0 | RTD-MEX-MCU-001 re-measured post-forward-harden (#38): 44.2 s context→check, 1 attempt, exit 0, 0 SEVERE [TOOL], 120 generated files. KPI PASS. Deferred 10 Mux12-20+CM7_CORE_CLK clocks documented in asset. |
| 2026-07-02 | 0.27.0 | Completed the required KPI optimization loop for RTD-MEX-BASENXP-001 after the post-hardening miss: iteration 1 clarified the black-box harness prompt so the standalone `check` runs before vendor `validate`; OpenCode black-box E2E re-measured functional PASS / KPI PASS at 12.72 s ≤ 1 min, 1 edit attempt, session `ses_0dfcfb3b1ffeChWcxr0xtOgaxj`. Summary returns to 14 / 14 functional PASS and 14 / 14 KPI PASS. |
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
| 2026-07-22 | 0.35.1 | Removed active runner-governance terminology from the KPI metric description without changing the measured window or any functional/KPI evidence. Historical entries remain unchanged. |
