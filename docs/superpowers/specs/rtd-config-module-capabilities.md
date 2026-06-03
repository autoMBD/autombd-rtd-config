# RTD CfgFile CLI Module Capabilities

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-06-02 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Maintains module ownership, dependencies, runtime data, shortcut groups, and aligned test-case coverage for RTD CfgFile CLI. |

## Purpose

This document is the maintainable module capability table for RTD CfgFile CLI.
It records module ownership, dependencies, supported action direction, runtime
data, shortcut command groups, and aligned test coverage.

Milestone 1 acceptance uses only the mandatory minimum test cases listed here.
Advanced cases are not required unless the user explicitly adds them to the
test scope. Reserved future cases are retained as planning input for later
milestones.

## Capability Table

| Module | Ownership | Key dependencies | Capability direction | Runtime data | Shortcut group | M1 mandatory cases | M1 advanced cases | Reserved future cases |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mcu | Clock and MCU configuration owned by Mcu | Resource requests from Uart, Mcl FlexIO, Platform, stacks, RTOS, and future drivers | Minimum clock/reference and peripheral-clock support for Uart stack; broader clock/mode/RAM/reset features later | Module schema and constraint cache | `mcu` | `RTD-M1-MIN-002`, `RTD-M1-MIN-003`, `RTD-M1-MIN-004`, `RTD-M1-MIN-005`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-MCU-001`, `RTD-M1-ADV-MCU-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M3-MCU-LOWPOWER-001`, `RTD-FUT-M3-MCU-RAM-001`, `RTD-FUT-M3-MCU-RESET-001` |
| BaseNXP | BaseNXP/OsIf global configuration | Uart timeout/callback needs, Platform/user-mode policy, future OS integration | Existing/minimum BaseNXP support for Uart stack; advanced OsIf timer/diagnostics optional | Module schema and enum cache | `basenxp` | `RTD-M1-MIN-001`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-BASENXP-001`, `RTD-M1-ADV-BASENXP-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M3-BASENXP-OS-001` |
| Platform | Platform and interrupt configuration | Interrupt-driven Uart, Mcu notifications, future DMA/OS/MPU users | Minimum IRQ support for Uart interrupt mode; broader MPU/MCM/INTM later | IRQ/resource constraint cache | `platform` | `RTD-M1-MIN-003`, `RTD-M1-MIN-005`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-PLATFORM-001` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M2-UART-DMA-001`, `RTD-FUT-M3-PLATFORM-MPU-001`, `RTD-FUT-M3-PLATFORM-MCM-001`, `RTD-FUT-M3-PLATFORM-INTM-001` |
| Port | Generic pin mux and pad configuration | Any module needing pins, especially Uart and Dio | Complete generic pin mapping/query and generic Uart pin configuration for S32K344 validation package | Family/device/package pin mapping and Port schema cache | `port` | `RTD-M1-MIN-002`, `RTD-M1-MIN-003`, `RTD-M1-MIN-004`, `RTD-M1-MIN-005`, `RTD-M1-MIN-006`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-PORT-001`, `RTD-M1-ADV-PORT-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002` |
| Dio | Dio ports and channels | GPIO users and external peripheral control | Present in first module set; mandatory only through existing fixture detection and LPUART E2E fixture when needed | Dio schema and resource cache | `dio` | `RTD-M1-MIN-001`, `RTD-M1-MIN-007` | `RTD-M1-ADV-DIO-001`, `RTD-M1-ADV-DIO-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M3-DIO-PARTITION-001` |
| Mcl | Mcl and shared low-level resources | FlexIO Uart users and future DMA/resource users | Minimum FlexIO common resource support for FlexIO Uart; DMA/eMIOS/TRGMUX/LCU later | Mcl schema and FlexIO resource cache | `mcl` | `RTD-M1-MIN-004`, `RTD-M1-MIN-005`, `RTD-M1-MIN-008` | `RTD-M1-ADV-MCL-001` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M2-UART-DMA-001`, `RTD-FUT-M3-MCL-RES-001` |
| Uart | Uart channels and Uart parameters | Mcu, Port, Platform, Mcl as needed | LPUART and FlexIO Uart in polling/interrupt modes; DMA deferred | Uart schema and dependency constraints | `uart` | `RTD-M1-MIN-002`, `RTD-M1-MIN-003`, `RTD-M1-MIN-004`, `RTD-M1-MIN-005`, `RTD-M1-MIN-007`, `RTD-M1-MIN-008` | `RTD-M1-ADV-UART-001`, `RTD-M1-ADV-UART-002` | `RTD-FUT-M2-CREATE-001`, `RTD-FUT-M2-CREATE-002`, `RTD-FUT-M2-UART-DMA-001` |

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
