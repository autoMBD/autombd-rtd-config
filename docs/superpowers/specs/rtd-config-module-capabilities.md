# RTD Configuration Module Capabilities

Version: 0.1.1
Date: 2026-05-30
Author: autoMBD <tkung.lqk@foxmali.com>
Authoring note: AI-assisted capability table prepared through human review.

## Purpose

This document is the maintainable module capability table for the RTD
Configuration Tool. It records module ownership, dependencies, supported action
direction, runtime data, shortcut command groups, and test coverage. Update this
file whenever a module, backend, or set feature is added.

## Capability Table

| Module | Ownership | Key dependencies | Capability direction | Runtime data | Shortcut group | Test coverage |
| --- | --- | --- | --- | --- | --- | --- |
| Mcu | Clock and MCU configuration owned by Mcu | Resource requests from drivers, stacks, RTOS, and peripherals | Clock references, peripheral clocks, mode/clock settings | Module schema and constraint cache | `mcu` | Clock/ref valid and invalid cases |
| BaseNXP | BaseNXP global configuration | Platform and driver timing needs | Available BaseNXP parameters, OsIf, timer basis | Module schema and enum cache | `basenxp` | Parameter set and validation cases |
| Platform | Platform and interrupt configuration | Interrupt-driven drivers and stack modules | Interrupt controller, IRQ enablement, priority, handler/vector basics | IRQ/resource constraint cache | `platform` | Interrupt enable/priority valid and invalid cases |
| Port | Pin mux and pad configuration | Any module needing pins | Generic pin configuration from versioned pin mapping | Family/device/package pin mapping and Port schema cache | `port` | Pin mapping, mux, pad, conflict, invalid pin cases |
| Dio | Dio ports and channels | GPIO users and external peripheral control | Generic port/channel configuration and uniqueness checks | Dio schema and resource cache | `dio` | Channel creation/update, duplicate id, invalid port cases |
| Mcl | Mcl and shared low-level resources | FlexIO users and future DMA/resource users | FlexIO common, channels, timers, shifters, shared resources | Mcl schema, FlexIO resource cache | `mcl` | FlexIO resource valid and conflict cases |
| Uart | Uart channels and Uart parameters | Mcu, Port, Platform, Mcl as needed | LPUART, FlexIO Uart, polling/interrupt, communication parameters | Uart schema, dependency constraints | `uart` | LPUART/FlexIO, polling/interrupt, invalid dependency cases |

## Required Fields For New Modules

Every new module entry must define:

- owned backend configuration regions;
- supported actions and shortcut command mapping;
- dependencies and dependency direction;
- constraints and resource limits;
- runtime data/cache files;
- validation fixture scenarios;
- fast deterministic tests;
- independent subagent validation cases where applicable.

## Ownership Rule

A module may only write configuration regions it owns. Cross-module needs must
be expressed as dependency requests and applied by the owning provider.

## Changelog

- 2026-05-30 v0.1.1: Standardized document metadata and added changelog.
- 2026-05-30 v0.1.0: Created maintainable module capability table.
