# RTD CfgFile CLI Independent Subagent Validation Handoff

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-06-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Black-box subagent validation handoff record. Documents the executed Uart-reference black-box round and its invocation contract; the authoritative E2E acceptance cases and isolation protocol now live in `rtd-config-test-cases.md`. |

## Purpose

This document drives independent, context-isolated subagent validation of the
RTD CfgFile CLI, executed by the **Tester** role (`.claude/agents/tester.md`) or
its delegate. Each subagent receives only a simulated user configuration
request and must satisfy it through the public CLI and the companion
`autombd-rtd` skill.

> The authoritative E2E acceptance cases are
> [`rtd-config-test-cases.md`](rtd-config-test-cases.md) (scheme `RTD-MEX-*`),
> including the full isolation protocol. The cases below are the historical,
> executed Uart-reference black-box prompts (legacy `RTD-M1-MIN-*` IDs kept for
> the record). The vendor pass gate is exit 0 AND no SEVERE `[TOOL]`.

## Invocation Contract

Every validation subagent invocation must satisfy all of the following:

```text
Validation subagents must be context-isolated (no inherited conversation state).
The subagent receives only the simulated user configuration request, the released companion skill, and the public CLI.
Focused KPI is 3 minutes.
E2E KPI is 5 minutes.
The orchestrator intervenes after 10 minutes.
```

- **Context isolation is the requirement**; the mechanism is whatever the agent
  platform provides (e.g. a fresh, non-inherited context — on some platforms a
  fork/inheritance flag). The subagent must not inherit prior conversation
  state.
- The subagent is given only the simulated user configuration request below,
  the repository-visible instructions, the committed companion skill, and the
  public CLI. It must not be told how the tool is built internally.
- A focused case should converge within 3 minutes. An end-to-end case should
  converge within 5 minutes. A run may continue up to 10 minutes to expose
  useful evidence; after 10 minutes the orchestrator steps in and captures the
  issue information.

## Vendor Validation Gate

S32DS / S32 ConfigTools headless validation runs only when
`RTD_CONFIG_RUN_S32DS_VALIDATION=1` and a S32DS root is configured
(`RTD_CONFIG_S32DS_ROOT` or `--s32ds-root`). Without that environment the
subagent must still pass every non-vendor assertion: JSON status, owned changed
modules, and the static-check result. The vendor pass condition is ConfigTools
process exit code `0` **and** no SEVERE `[TOOL]` resource-configuration problem
(exit `0` alone is not sufficient). The tool registers the project in the S32DS
workspace and drives the `Peripherals` headless tool with `-sdkPath` at the
bundled PlatformSDK.

## Mandatory Minimum Cases

Each row gives the case ID, the request surface the subagent should use, the
exact simulated user prompt to hand to the subagent, the expected evidence, and
the KPI.

### RTD-M1-MIN-001 — Inspect existing complete S32K344 Uart fixture

- Request surface: `inspect`
- Simulated user prompt: 我需要确认这个 S32K344 RTD 7.0.1 工程当前启用了哪些 RTD 模块、芯片型号、封装、RTD 版本和可用验证配置。
- Expected evidence: the tool detects backend, device, RTD version, enabled
  modules, and validation profile without project writes or a vendor-tool
  launch.
- KPI: 3 minutes.

### RTD-M1-MIN-002 — Reserved / removed (polling)

Removed from the M1 mandatory set: RTD 7.0.1 models the Uart asynchronous method
as interrupt or DMA only, so "polling mode" is not a configurable `.mex`
scenario. Interrupt coverage is RTD-M1-MIN-003.

### RTD-M1-MIN-003 — Configure one LPUART channel in interrupt mode

- Request surface: JSON intent and `uart set`
- Simulated user prompt: 我需要在 S32K344 RTD 7.0.1 工程中配置一个 LPUART Uart 通道，使用中断模式、115200 baud、8N1、指定 TX/RX 引脚，并启用对应中断。
- Expected evidence: the plan includes an explicit Platform IRQ dependency, no
  DMA edits, and no cross-module ownership violation. Static check passes, and
  S32DS headless validation passes when enabled.
- KPI: 3 minutes.

### RTD-M1-MIN-004 — Reserved / removed (polling)

Removed from the M1 mandatory set for the same reason as MIN-002: polling is not
an RTD 7.0.1 `.mex` async-method value. FlexIO interrupt coverage is
RTD-M1-MIN-005.

### RTD-M1-MIN-005 — Configure one FlexIO-backed Uart channel in interrupt mode

- Request surface: JSON intent and `uart set`
- Simulated user prompt: 我需要在 S32K344 RTD 7.0.1 工程中配置一个 FlexIO Uart 通道，使用中断模式、115200 baud、8N1、指定 TX/RX 引脚，并启用对应中断。
- Expected evidence: the plan includes Mcl FlexIO resources, Port pins, the Uart
  FlexIO channel, and a Platform IRQ dependency. Static check passes, and S32DS
  headless validation passes when enabled.
- KPI: 3 minutes.

### RTD-M1-MIN-006 — Query generic pin options before Uart pin assignment

- Request surface: `pin-options`
- Simulated user prompt: 我需要查询 S32K344 指定封装下某个 LPUART 或 FlexIO Uart 信号可以使用哪些引脚和复用模式，用于后续配置 TX/RX。
- Expected evidence: the query reads prepared runtime pin mapping only, returns
  valid options, and does not read Excel or launch a vendor tool.
- KPI: 3 minutes.

### RTD-M1-MIN-007 — End-to-end minimal LPUART stack

- Request surface: JSON intent
- Simulated user prompt: 我需要在一个真实 S32K344 RTD 7.0.1 工程中完成最小 LPUART Uart 配置，让工程通过配置校验并能生成正确配置代码。
- Expected evidence: one focused real fixture completes the minimum LPUART stack
  and passes the static check, plus S32DS headless validation when enabled.
- KPI: 5 minutes.

### RTD-M1-MIN-008 — End-to-end minimal FlexIO Uart stack

- Request surface: JSON intent
- Simulated user prompt: 我需要在一个真实 S32K344 RTD 7.0.1 工程中完成最小 FlexIO Uart 配置，让工程通过配置校验并能生成正确配置代码。
- Expected evidence: one focused real fixture completes the minimum FlexIO Uart
  stack and passes the static check, plus S32DS headless validation when
  enabled.
- KPI: 5 minutes.

## Acceptance

A case is accepted when the subagent, using only the public CLI and the
companion skill, satisfies the simulated user prompt and produces the expected
evidence within its KPI. Vendor validation assertions apply only when the
vendor environment is configured; otherwise the non-vendor assertions are
authoritative.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-03 | 0.1.0 | Created M1 black-box subagent validation handoff with mandatory minimum prompts and KPIs. |
| 2026-06-10 | 0.2.0 | Fourth-round review alignment: renamed from `rtd-config-m1-subagent-validation.md`; execution role corrected to the Tester (context isolation generic, no platform-specific parameter); repositioned as the historical executed record — the authoritative E2E cases/protocol live in `rtd-config-test-cases.md`. |
