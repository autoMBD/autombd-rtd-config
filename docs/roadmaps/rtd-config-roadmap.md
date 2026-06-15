# RTD CfgFile CLI Roadmap

| Field | Value |
| --- | --- |
| Version | 0.4.1 |
| Date | 2026-06-15 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | The basic delivery route for the RTD CfgFile CLI. This is the only document that describes stages; specs stay milestone-free. No technical detail here — capabilities are defined by the core design, cases by the test-cases catalog. |

## Purpose

This roadmap records the delivery order. It intentionally lives outside the
spec so the spec can remain a stable description of the project goal and
architecture. Modules are added one by one under the same development framework;
this document only says **what comes when**.

## Route

| Milestone | Goal |
| --- | --- |
| 1 | **Minimal system**: modules `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`, and `Uart` on NXP S32K3, for `.mex` files. Delivered together, equal priority. |
| 2 | Complete the remaining RTD modules, for `.mex`. |
| 3 | Add missing configuration modules to existing projects, or create a `.mex` configuration file from scratch. |
| 4 | Support EB tresos and `.xdm`. |
| 5 | Long term: support RTD FreeRTOS, RTD Stacks, and RTD CDDs; support more chip families. |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-10 | 0.4.0 | Fourth-round review resolution: simplified to the basic five-stage route (minimal system → remaining modules → completion/creation → EB tresos/.xdm → long-term FreeRTOS/Stacks/CDDs/more chips); removed all technical detail and per-milestone scope bullets. |
| 2026-06-02 | 0.3.0 | Renamed roadmap for RTD CfgFile CLI and clarified mandatory, advanced, and reserved test scope by milestone. |
| 2026-06-02 | 0.2.0 | Added roadmap overview table before detailed milestone sections. |
| 2026-05-30 | 0.1.2 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.1.1 | Standardized document metadata and added changelog. |
| 2026-05-30 | 0.1.0 | Created staged RTD CfgFile CLI roadmap. |
| 2026-06-15 | 0.4.1 | Issue #7 reorganization: removed parenthetical pointer to the deleted implementation-plan from the Purpose paragraph. |
