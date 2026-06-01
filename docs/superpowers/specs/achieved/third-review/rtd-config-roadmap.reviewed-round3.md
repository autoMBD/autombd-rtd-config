# RTD Configuration Tool Roadmap

> Archive status: unavailable for requirements. This reviewed draft is kept
> only for comment traceability. Do not read or use it to infer current
> behavior, terminology, scope, architecture, test requirements, or acceptance
> criteria. Use only active documents outside `docs/superpowers/specs/achieved/`.

| Field | Value |
| --- | --- |
| Version | 0.1.2 |
| Date | 2026-05-30 |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | Records staged delivery order and milestone boundaries for the RTD configuration tool. |

## Purpose

This roadmap records delivery order and staged limits. It intentionally lives
outside the spec so the spec can remain a stable description of the project
goal and architecture.

<!-- REVIEW: 先给一个overview的roadmap表格，再分章节描述。 -->

## Milestone 1: S32K3 RTD 7.0.1 MEX Core

Implement the first complete `.mex` backend path for existing S32DS projects.

Scope:

- backend: S32 ConfigTools `.mex`;
- RTD: S32K3 RTD 7.0.1;
- validation target: S32K344 first;
- modules: `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`, `Uart`;
- Uart: LPUART and FlexIO Uart;
- modes: interrupt and polling;
- Port: complete generic pin mapping and generic pin configuration for the
  validated device/package;
- Mcl: generic FlexIO foundation needed by FlexIO users;
- command flow: JSON intent and seven module shortcut command groups;
- write flow: existing project in-place modification, optional `--backup`;
- validation: static checks plus no-window S32DS headless validation.

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
| 2026-05-30 | 0.1.2 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.1.1 | Standardized document metadata and added changelog. |
| 2026-05-30 | 0.1.0 | Created staged RTD configuration tool roadmap. |
