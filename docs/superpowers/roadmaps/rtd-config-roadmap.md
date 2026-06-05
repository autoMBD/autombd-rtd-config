# RTD CfgFile CLI Roadmap

| Field | Value |
| --- | --- |
| Version | 0.3.0 |
| Date | 2026-06-02 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Records staged delivery order and milestone boundaries for RTD CfgFile CLI. |

## Purpose

This roadmap records delivery order and staged limits. It intentionally lives
outside the spec so the spec can remain a stable description of the project
goal and architecture.

## Roadmap Overview

| Milestone | Focus | Primary deliverable | Major exclusions carried forward |
| --- | --- | --- | --- |
| 1 | S32K3 RTD 7.0.1 `.mex` core | Existing-project configuration for `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`, and `Uart` on S32K344, with static checks and no-window S32DS headless validation. | DMA, from-scratch `.mex` creation, partial-project completion, EB tresos, K1/K5 validation. |
| 2 | DMA and creation support | Uart DMA paths, Mcl/Dma dependencies, safe missing-module completion, and prepared-template `.mex` creation. | Broad new module expansion and EB tresos backend. |
| 3 | More modules and full set coverage | Additional RTD modules and richer set features until common and then complete RTD configuration needs are covered. | New chip families and backend families unless explicitly prioritized. |
| 4 | More devices, families, and RTD releases | Runtime data and fixtures for more S32K3 devices/packages, S32K1/S32K5, and newer RTD releases. | EB tresos unless milestone 5 has started. |
| 5 | EB tresos backend | `.xdm` document core, EB validation integration, shared intent/resource/module model reuse, and EB-specific fixtures. | Non-EB backend families. |

## Milestone 1: S32K3 RTD 7.0.1 MEX Core

Implement the first complete `.mex` backend path for existing S32DS projects.

Scope:

- backend: S32 ConfigTools `.mex`;
- RTD: S32K3 RTD 7.0.1;
- validation target: S32K344 first;
- modules: `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`, `Uart`;
- Uart: LPUART and FlexIO Uart;
- modes: interrupt (IRQ) only — RTD 7.0.1 has no polling async-method value; DMA deferred;
- Port: complete generic pin mapping and generic pin configuration for the
  validated device/package;
- Mcl: generic FlexIO foundation needed by FlexIO users;
- command flow: JSON intent and seven module shortcut command groups;
- write flow: existing project in-place modification, optional `--backup`;
- validation: static checks plus no-window S32DS headless validation.
- default testing: mandatory minimum tests only. Advanced tests are executed
  only by explicit user instruction. Reserved future tests are not Milestone 1
  acceptance gates.

Out of scope:

- creating a `.mex` from scratch;
- completing missing modules in a partial `.mex`;
- DMA;
- EB tresos implementation;
- K1/K5 validation;
- runtime Excel parsing;
- runtime RTD installation scans.

## Milestone 2: DMA And Creation Support

Add DMA-related configuration and then add from-scratch `.mex` creation and
missing-module completion.

Expected additions:

- Uart DMA paths;
- Mcl/Dma resource ownership and dependencies;
- safe module completion for in-scope modules;
- base `.mex` creation from prepared runtime templates;
- expanded validation fixtures.

Milestone 2 planning will decide which reserved future test cases become
mandatory and which remain advanced.

## Milestone 3: More Modules And Full Set Coverage

Expand module providers and set features until the tool can cover common and
then complete RTD configuration needs.

Expected additions:

- additional driver modules such as Spi, Pwm, Adc, Can, Lin, Ethernet, and
  others as prioritized;
- official RTD RTOS and stacks;
- external peripheral driver configuration where represented in supported
  project files;
- broader module capability tables and test cases.

## Milestone 4: More Devices, Families, And RTD Releases

Extend prepared runtime data and validation fixtures to additional devices,
families, and releases.

Expected additions:

- more S32K3 devices/packages;
- S32K1 and S32K5 support;
- newer RTD versions;
- compatibility metadata and migration checks.

## Milestone 5: EB Tresos Backend

Add EB tresos support through a dedicated backend provider.

Expected additions:

- `.xdm` and related EB project document core;
- EB validation integration;
- shared intent/resource/module model reuse;
- EB-specific fixtures and test cases.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.3.0 | Renamed roadmap for RTD CfgFile CLI and clarified mandatory, advanced, and reserved test scope by milestone. |
| 2026-06-02 | 0.2.0 | Added roadmap overview table before detailed milestone sections. |
| 2026-05-30 | 0.1.2 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.1.1 | Standardized document metadata and added changelog. |
| 2026-05-30 | 0.1.0 | Created staged RTD CfgFile CLI roadmap. |
