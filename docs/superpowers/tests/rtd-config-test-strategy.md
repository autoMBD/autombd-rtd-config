# RTD Configuration Test Strategy

| Field | Value |
| --- | --- |
| Version | 0.3.0 |
| Date | 2026-06-02 |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | Defines testing layers, fixture validation, subagent validation, and KPI rules. |

## Purpose

This document defines the maintainable testing process for the RTD
configuration tool. It applies to every backend, module, and set feature.

The spec defines project goals. This document defines test cases, validation
workflow, independent subagent validation, and KPI expectations.

## Test Layers

1. Fast deterministic tests
   Run without vendor tools. They cover intent validation, command
   normalization, resource lookup, document indexing, localized edits, provider
   ownership boundaries, planning, diagnostics, and validation command building.

2. Fixture integration tests
   Run on real vendor project fixtures. They apply configuration changes to the
   fixture project and verify the modified project structure.

3. Vendor headless validation
   Runs the configured vendor validation tool without a visible GUI window on
   the modified fixture project. This is the authority for backend acceptance.

4. Independent subagent validation
   A separate subagent validates fixture integration tests and vendor headless
   validation cases using only the public tool interface, companion skills, test
   input, and repository-visible instructions. Fast deterministic tests are
   normally run by the main development agent during implementation.

## Fixture Structure

Fixtures use a backend/family/device/scenario structure:

```text
fixtures/
  projects/
    <backend>/
      <family>/
        <device>/
          <scenario>/
```

Each fixture must include files required for vendor validation. Build outputs,
debug folders, generated binaries, logs, and temporary artifacts must stay out
of source control unless a test explicitly requires a small static fixture.

## Test Case Template

Each test case should be recorded with this structure:

```text
ID:
Backend:
Family:
Device:
RTD version:
Module(s):
Scenario:
Input fixture:
Request type: JSON intent | shortcut command
Preconditions:
Command(s):
Expected plan:
Expected changed modules:
Expected static check result:
Expected vendor validation result:
Expected diagnostics:
KPI target:
Subagent validation required:
```

## Milestone 1 S32K3 MEX Test Case Catalog

These cases are derived from the retired development reference skills under
`D:\WorkSpace\ExploreSpace\autombd-skills\skills\rtd-config` for the first
milestone modules: `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`, and
`Uart`. The catalog defines acceptance targets for S32K3 RTD 7.0.1 `.mex`
configuration on the S32K344 validation fixture.

| ID | Module(s) | Source use case | Request surface | Expected evidence |
| --- | --- | --- | --- | --- |
| RTD-M1-MCU-001 | Mcu | Add missing Mcu instance | JSON intent and `mcu` shortcut | A valid Mcu instance is inserted or updated without creating non-Mcu dependencies. Static check and S32DS headless validation pass. |
| RTD-M1-MCU-002 | Mcu | Configure clocks | JSON intent and `mcu set-clock` | Oscillator, PLL, CGM mux/divider, and clock-reference edits are localized and invalid frequencies produce actionable diagnostics. |
| RTD-M1-MCU-003 | Mcu | Configure peripheral clock gate | JSON intent and `mcu set-peripheral-clock` | Peripheral clock gate is enabled or disabled in the selected mode and duplicate peripheral names are rejected. |
| RTD-M1-MCU-004 | Mcu | Configure modes and low power | JSON intent | Mode IDs, power mode fields, and low-power prerequisites are consistent or reported as blockers. |
| RTD-M1-MCU-005 | Mcu | Configure RAM sections | JSON intent | RAM section base, size, default value, and write-size fields are generated with range diagnostics for invalid memory. |
| RTD-M1-MCU-006 | Mcu | Configure reset and callouts | JSON intent | Reset API/callout fields accept valid C identifiers and reject invalid symbols. |
| RTD-M1-MCU-007 | Mcu, Platform | Configure notifications and interrupt-backed errors | JSON intent | Mcu notification switches are configured while Platform-owned IRQ changes remain explicit dependencies. |
| RTD-M1-BASENXP-001 | BaseNXP | Add minimal bare-metal BaseNXP | JSON intent and `basenxp` shortcut | BaseNXP/OsIf bare-metal defaults are valid and do not introduce timer or OS dependencies. |
| RTD-M1-BASENXP-002 | BaseNXP | Enable DET/dev error checks | JSON intent | DET switch changes generated defines and missing Det availability is diagnosed as a dependency issue. |
| RTD-M1-BASENXP-003 | BaseNXP, Mcu | Enable bare-metal system timer | JSON intent | Exactly one valid counter is configured with either Mcu clock reference or frequency, not both. |
| RTD-M1-BASENXP-004 | BaseNXP | Enable custom timer | JSON intent | Custom timer switch is configured and missing application timer functions are reported clearly. |
| RTD-M1-BASENXP-005 | BaseNXP | Change OS mode and user ID source | JSON intent | OS choice child is replaced consistently and invalid `GET_PARTITION_ID` combinations are rejected. |
| RTD-M1-BASENXP-006 | BaseNXP | Multicore, partitions, user mode, software semaphore | JSON intent | Supported combinations pass; missing EcuC/Os/partition prerequisites are reported as blockers without hidden edits. |
| RTD-M1-PLATFORM-001 | Platform | Add or enable IRQ | JSON intent and `platform set-irq` | `PlatformIsrConfig` entry is unique, priority is in range, handler is valid, and duplicates are rejected. |
| RTD-M1-PLATFORM-002 | Platform | Configure MPU M7 region | JSON intent | Region count, size, alignment, memory type, and access rights pass schema and static checks. |
| RTD-M1-PLATFORM-003 | Platform | Configure MCM/system settings | JSON intent | MCM feature gate and system ISR entries are configured with duplicate-name diagnostics. |
| RTD-M1-PLATFORM-004 | Platform | Configure interrupt monitor | JSON intent | INTM enablement requires at least one channel and validates monitored IRQ and accepted latency. |
| RTD-M1-PLATFORM-005 | Platform | Multicore, partitions, and user mode | JSON intent | Partition references are consistent or reported as missing external dependencies. |
| RTD-M1-PORT-001 | Port | Create default Port | JSON intent and `port` shortcut | Valid Port instance/config set exists and generated file metadata remains vendor-owned. |
| RTD-M1-PORT-002 | Port | Route peripheral signal | JSON intent, `port set-pin`, and `pin-options` | Pin mapping query returns valid options, selected mux is applied generically, and consumer module ownership is preserved. |
| RTD-M1-PORT-003 | Port, Dio | Configure GPIO output | JSON intent and `port set-pin` | GPIO mux, output direction, initial level, and optional direction-change flag are set; Dio channel dependency is explicit. |
| RTD-M1-PORT-004 | Port, Dio, Platform | Configure GPIO input or external interrupt pin | JSON intent and `port set-pin` | GPIO input, pull/readback/filter settings are valid; Platform IRQ routing remains a separate dependency. |
| RTD-M1-PORT-005 | Port | Configure alternate-function input and electrical settings | JSON intent | Input mux, IMCR/MSCR ownership, pull/drive/filter/inversion fields pass device/package constraints. |
| RTD-M1-PORT-006 | Port | Configure untouched pins or runtime APIs | JSON intent | Untouched MSCR/IMCR conflicts and per-pin runtime API flags are detected before vendor validation. |
| RTD-M1-DIO-001 | Dio | Create minimal Dio | JSON intent and `dio` shortcut | Minimal Dio instance is valid and optional APIs remain disabled by default. |
| RTD-M1-DIO-002 | Dio, Port | Add Dio channel | JSON intent and `dio set-channel` | Port ID/channel ID are unique, channel symbol is generated, and missing Port GPIO config is an explicit dependency. |
| RTD-M1-DIO-003 | Dio | Add Dio channel group | JSON intent | Group ID/name uniqueness and mask formula are validated. |
| RTD-M1-DIO-004 | Dio | Enable optional APIs and diagnostics | JSON intent | Flip, masked-write, version, DET, and undefined-pin read switches update generated configuration consistently. |
| RTD-M1-DIO-005 | Dio | Multi-partition and virtual wrapper | JSON intent | Partition references are accepted only when referenced EcuC/Rm resources exist; otherwise blockers are reported. |
| RTD-M1-MCL-001 | Mcl | Create default or empty Mcl | JSON intent and `mcl` shortcut | Valid Mcl base instance exists without enabling unused hardware features. |
| RTD-M1-MCL-002 | Mcl, Uart | Add FlexIO common logic channel | JSON intent and `mcl set-flexio` | FlexIO instance, channel, pin, optional extra channel/pin fields are unique and referenceable by Uart. |
| RTD-M1-MCL-003 | Mcl | Diagnostics and access mode switches | JSON intent | Dev-error, version-info, user-mode, and partition switches are validated against project dependencies. |
| RTD-M1-MCL-004 | Mcl | DMA/eMIOS/TRGMUX/LCU use cases from retired skills | JSON intent | First milestone returns explicit out-of-scope or deferred-feature diagnostics until those features are implemented. |
| RTD-M1-UART-001 | Uart, Mcu, Port, Platform | Add LPUART channel in interrupt mode | JSON intent and `uart set` | Channel ID/order, LPUART hardware instance, clock reference, pins, IRQ dependency, baud, parity, stop bit, and word length are valid. |
| RTD-M1-UART-002 | Uart, Mcu, Port | Add LPUART channel in polling mode | JSON intent and `uart set` | LPUART channel is configured without interrupt/DMA dependency and runtime verification passes. |
| RTD-M1-UART-003 | Uart, Mcu, Mcl, Port, Platform | Add FlexIO-backed Uart channel in interrupt mode | JSON intent and `uart set` | Uart references an Mcl FlexIO logic channel, valid FlexIO clock, Port pins, and explicit IRQ dependency. |
| RTD-M1-UART-004 | Uart, Mcu, Mcl, Port | Add FlexIO-backed Uart channel in polling mode | JSON intent and `uart set` | FlexIO-backed Uart channel validates without interrupt/DMA dependency. |
| RTD-M1-UART-005 | Uart | Configure multiple channels in one request | JSON intent | Full channel array is planned before editing; duplicate IDs, names, hardware instances, FlexIO refs, and stale refs are rejected. |
| RTD-M1-UART-006 | Uart, BaseNXP | Configure callbacks, timeout, idle, and API switches | JSON intent | Callback symbols, timeout method/duration, version API, DET, and OSIF dependencies are valid or actionable blockers. |
| RTD-M1-UART-007 | Uart, Mcl | DMA request before milestone 2 | JSON intent and `uart set` | First milestone returns explicit deferred-feature diagnostics instead of partial DMA edits. |
| RTD-M1-E2E-001 | Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart | Minimal Uart stack configuration | JSON intent | One focused end-to-end fixture configures the minimum module combination for LPUART Uart and passes static check plus S32DS headless validation. |
| RTD-M1-E2E-002 | Mcu, BaseNXP, Platform, Port, Mcl, Uart | Minimal FlexIO Uart stack configuration | JSON intent | One focused end-to-end fixture configures FlexIO Uart with Mcl FlexIO resources and passes static check plus S32DS headless validation. |

## Required Coverage Categories

Every implemented module or set feature must have tests for:

- valid configuration;
- invalid or missing resources;
- dependency resolution;
- ownership boundaries;
- static diagnostics;
- vendor validation result when the backend supports validation;
- shortcut command normalization when a shortcut exists;
- JSON intent path.

Backend test documents should add concrete test cases for specific modules and
milestones.

## Independent Subagent Validation

Key test cases must be validated by independent subagents.

Subagent validation requirements:

- each subagent call must set `"fork_context": false`;
- with `"fork_context": false`, the subagent is fully independent from the main
  agent and has isolated context;
- the subagent must not see the main agent's analysis, implementation details,
  hidden assumptions, or debugging process;
- the subagent should rely only on the user requirement, test-case
  instructions, repository files, companion skills, and the public tool
  interface;
- each subagent should validate one focused test case whenever practical.

Independent subagent validation targets the integration and vendor validation
layers. The main development agent may run fast deterministic tests during
implementation, but those fast checks do not replace independent validation of
fixture edits and vendor headless results.

## Failure Iteration Loop

Any development test, fixture integration test, vendor headless validation, or
independent subagent validation failure must feed back into implementation.
The responsible agent must analyze the failed case, identify whether the cause
is code, runtime data, fixture setup, test wording, diagnostics, or performance,
fix the root cause, and rerun the relevant tests. A feature is not accepted
until the failed case and its related regression coverage pass.

## KPI

The KPI applies to all module configuration flows:

- each independent subagent validation of one focused test case must complete
  within 3 minutes;
- the ideal path is: understand the requirement, infer or use the provided
  intent, call the tool, and pass validation once;
- repeated KPI misses indicate a problem in the public interface, diagnostics,
  runtime performance, fixture design, or test-case wording.

## Acceptance Rule

A module or feature is accepted when:

- required test cases pass;
- vendor validation passes when applicable;
- focused independent subagent validation meets the KPI;
- failures produce actionable diagnostics rather than tracebacks or ambiguous
  logs.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.3.0 | Added first-milestone test case catalog from retired module use-case skills and documented the failure iteration loop. |
| 2026-05-30 | 0.2.1 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.0 | Clarified independent subagent validation scope. |
| 2026-05-30 | 0.1.0 | Created RTD configuration test strategy. |
