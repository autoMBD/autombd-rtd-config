> **OBSOLETE - review archive only (round 4).** This is the reviewed draft of
> `docs/specs/rtd-config-module-capabilities.md` with the user's inline REVIEW comments preserved for traceability.
> It is NOT a requirements source and must not be read to infer current
> behavior, scope, terminology, or acceptance criteria. Use only active
> documents outside `docs/OBSOLETE_NEVER_TOUCH!!!/`. Comment resolutions are
> tracked in `docs/common/rtd-config-core-comments-tracking.md`.

# RTD CfgFile CLI Module Capabilities

| Field | Value |
| --- | --- |
| Version | 0.3.0 |
| Date | 2026-06-03 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Maintains module ownership, dependencies, runtime data, and shortcut groups for RTD CfgFile CLI. All seven M1 modules are equal priority; the authoritative test matrix lives in the M1 test-cases document (governed by the test strategy). |

## Purpose

<!-- REVIEW: 这个文件rtd-config-module-capabilities.md没有意义，项目的目标是做一个编辑.mex/.xdm文件的工具，那么就意味着所有合法的编辑、所有可配置项都应该支持。每个provider可编辑的内容/元素，参考 C:\NXP\S32DS.3.6.7\S32DS\software\PlatformSDK_S32K3\RTD\<ModulePackage>\config\<Module>.xdm 即可，这个文件直接移除，在Spec中写明开发目标，然后调整对该文件有依赖的其他文件。 -->

This document is the maintainable module capability table for RTD CfgFile CLI.
It records module ownership, dependencies, supported action direction, runtime
data, shortcut command groups, and aligned test coverage.

All seven modules are **equal priority** in Milestone 1: each must reach the same
configure + S32DS-validated bar as Uart (exit 0 + no SEVERE `[TOOL]`). The
authoritative mandatory matrix and case IDs are in
`tests/rtd-config-m1-test-cases.md` (parity scheme `RTD-M1-<MODULE>-001`,
`RTD-M1-E2E-00x`, plus `RTD-M1-INSPECT-001` / `RTD-M1-PINOPT-001`), governed by
`tests/rtd-config-test-strategy.md`. The per-row "M1 mandatory cases" column
below still uses the implemented `RTD-M1-MIN-*` Uart-slice IDs and is being
migrated to the parity scheme; on any conflict the test-cases document wins. Advanced cases run only on
explicit request; reserved-future cases are later-milestone planning input.

## Capability Table

| Module | Ownership | Key dependencies | Capability direction | Runtime data | Shortcut group | M1 mandatory cases | M1 advanced cases | Reserved future cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mcu | Clock and MCU configuration owned by Mcu | Resource requests from Uart, Mcl FlexIO, Platform, stacks, RTOS, and future drivers | Minimum clock/reference and peripheral-clock support for Uart stack; broader clock/mode/RAM/reset features later | Module schema and constraint cache | `mcu` | `RTD-M1-MIN-003`, `RTD-M1-MIN-005`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-MCU-001`, `RTD-M1-ADV-MCU-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M3-MCU-LOWPOWER-001`, `RTD-FUT-M3-MCU-RAM-001`, `RTD-FUT-M3-MCU-RESET-001` |
| BaseNXP | BaseNXP/OsIf global configuration | Uart timeout/callback needs, Platform/user-mode policy, future OS integration | Existing/minimum BaseNXP support for Uart stack; advanced OsIf timer/diagnostics optional | Module schema and enum cache | `basenxp` | `RTD-M1-MIN-001`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-BASENXP-001`, `RTD-M1-ADV-BASENXP-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M3-BASENXP-OS-001` |
| Platform | Platform and interrupt configuration | Interrupt-driven Uart, Mcu notifications, future DMA/OS/MPU users | Minimum IRQ support for Uart interrupt mode; broader MPU/MCM/INTM later | IRQ/resource constraint cache | `platform` | `RTD-M1-MIN-003`, `RTD-M1-MIN-005`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-PLATFORM-001` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M2-UART-DMA-001`, `RTD-FUT-M3-PLATFORM-MPU-001`, `RTD-FUT-M3-PLATFORM-MCM-001`, `RTD-FUT-M3-PLATFORM-INTM-001` |
| Port | Generic pin mux and pad configuration | Any module needing pins, especially Uart and Dio | Complete generic pin mapping/query and generic Uart pin configuration for S32K344 validation package | Family/device/package pin mapping and Port schema cache | `port` | `RTD-M1-MIN-003`, `RTD-M1-MIN-005`, `RTD-M1-MIN-006`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-PORT-001`, `RTD-M1-ADV-PORT-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002` |
| Dio | Dio ports and channels | GPIO users and external peripheral control | Present in first module set; mandatory only through existing fixture detection and LPUART E2E fixture when needed | Dio schema and resource cache | `dio` | `RTD-M1-MIN-001`, `RTD-M1-MIN-007` | `RTD-M1-ADV-DIO-001`, `RTD-M1-ADV-DIO-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M3-DIO-PARTITION-001` |
| Mcl | Mcl and shared low-level resources | FlexIO Uart users and future DMA/resource users | Minimum FlexIO common resource support for FlexIO Uart; DMA/eMIOS/TRGMUX/LCU later | Mcl schema and FlexIO resource cache | `mcl` | `RTD-M1-MIN-005`, `RTD-M1-MIN-008` | `RTD-M1-ADV-MCL-001` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M2-UART-DMA-001`, `RTD-FUT-M3-MCL-RES-001` |
| Uart | Uart channels and Uart parameters | Mcu, Port, Platform, Mcl as needed | LPUART and FlexIO Uart in interrupt (IRQ) mode; polling is not an RTD 7.0.1 .mex async-method value; DMA deferred | Uart schema and dependency constraints | `uart` | `RTD-M1-MIN-003`, `RTD-M1-MIN-005`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-UART-001`, `RTD-M1-ADV-UART-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M2-UART-DMA-001` |

## Required Fields For New Modules

Every new module entry must define:

- owned backend configuration regions;
- supported actions and shortcut command mapping;
- dependencies and dependency direction;
- constraints and resource limits;
- runtime data/cache files;
- mandatory, advanced, and reserved test-case IDs;
- validation fixture scenarios;
- fast deterministic tests;
- independent subagent validation cases where applicable.

## Ownership Rule

A module may only write configuration regions it owns. Cross-module needs must
be expressed as dependency requests and applied by the owning provider.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.2.0 | Renamed document for RTD CfgFile CLI and aligned module capabilities with mandatory, advanced, and reserved test-case IDs. |
| 2026-05-30 | 0.1.2 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.1.1 | Standardized document metadata and added changelog. |
| 2026-05-30 | 0.1.0 | Created maintainable module capability table. |
