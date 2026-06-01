# RTD CfgFile CLI Test Strategy

| Field | Value |
| --- | --- |
| Version | 0.4.0 |
| Date | 2026-06-02 |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | Defines testing layers, case classes, subagent validation prompts, and KPI rules for RTD CfgFile CLI. |

## Purpose

This document defines the maintainable testing process for RTD CfgFile CLI. It
applies to every backend, module, and set feature.

The core design defines project goals. This document defines development test
cases, runtime verification expectations, independent subagent validation, and
KPI rules.

## Terminology

| Term | Meaning |
| --- | --- |
| Development testing | The implementation acceptance process. It proves the tool feature, diagnostics, runtime verification behavior, and agent-facing workflow before a feature is accepted. |
| Runtime verification | Tool behavior after it modifies `.mex`, `.xdm`, or another backend configuration file. It includes static check first and backend validation when configured. |
| Static check | The fast tool-owned runtime verification stage. It does not launch vendor tools. |
| Backend validation | The vendor/tool-backed runtime verification stage, such as S32 ConfigTools headless validation for `.mex` projects. |
| Mandatory minimum test | A test that must pass for the current milestone to be accepted. Milestone 1 uses only the mandatory minimum set unless the user explicitly asks for more. |
| Advanced test | A test that remains within the current milestone's possible module surface but is not required unless the user explicitly requests it. |
| Reserved future test | A test case derived from known use cases but outside the current milestone. It is kept for traceability and will be planned when the corresponding milestone starts. |
| Subagent user prompt | The simulated user configuration request given to an independent subagent. It must contain only the user-facing configuration demand, not implementation notes, hidden assumptions, validation instructions, or main-agent context. |

## Test Layers

1. Fast deterministic tests
   Run without vendor tools. They cover intent validation, command
   normalization, resource lookup, document indexing, localized edits, provider
   ownership boundaries, planning, diagnostics, and validation command building.

2. Fixture integration tests
   Run on real vendor project fixtures. They apply configuration changes to the
   fixture project and verify the modified project structure.

3. Backend validation
   Runs the configured vendor validation tool without a visible GUI window on
   the modified fixture project. This is the authority for backend acceptance.

4. Independent subagent validation
   A separate subagent validates fixture integration and backend validation
   behavior using only the public tool interface, companion skills, test input,
   and repository-visible instructions. Fast deterministic tests are normally
   run by the main development agent during implementation.

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

Each fixture must include files required for backend validation. Build outputs,
debug folders, generated binaries, logs, and temporary artifacts must stay out
of source control unless a test explicitly requires a small static fixture.

## Test Case Template

Each concrete test case should be recorded with this structure:

```text
ID:
Class: mandatory minimum | advanced | reserved future
Backend:
Family:
Device:
RTD version:
Module(s):
Scenario:
Input fixture:
Request type: JSON intent | shortcut command
Subagent user prompt:
Preconditions:
Command(s):
Expected plan:
Expected changed modules:
Expected static check result:
Expected backend validation result:
Expected diagnostics:
KPI target:
Subagent validation required:
```

## Milestone 1 Mandatory Minimum Tests

Milestone 1 validates only the minimum Uart stack needed for S32K3 RTD 7.0.1
`.mex` configuration on the S32K344 fixture. These cases are the default
acceptance gate.

| ID | Module(s) | Scenario | Request surface | Subagent user prompt | Expected evidence | KPI |
| --- | --- | --- | --- | --- | --- | --- |
| RTD-M1-MIN-001 | Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart | Inspect an existing complete S32K344 Uart fixture | `inspect` | 我需要确认这个 S32K344 RTD 7.0.1 工程当前启用了哪些 RTD 模块、芯片型号、封装、RTD 版本和可用验证配置。 | Tool detects backend, device, RTD version, enabled modules, runtime data profile, and validation profile without project writes or vendor-tool launch. | 3 min |
| RTD-M1-MIN-002 | Mcu, Port, Uart | Configure one LPUART channel in polling mode | JSON intent and `uart set` | 我需要在 S32K344 RTD 7.0.1 工程中配置一个 LPUART Uart 通道，使用轮询模式、115200 baud、8N1，并配置对应 TX/RX 引脚。 | Plan owns Uart edits through Uart provider, Port pin edits through Port provider, and Mcu clock/reference dependency through Mcu provider. Static check and S32DS headless validation pass. | 3 min |
| RTD-M1-MIN-003 | Mcu, Platform, Port, Uart | Configure one LPUART channel in interrupt mode | JSON intent and `uart set` | 我需要在 S32K344 RTD 7.0.1 工程中配置一个 LPUART Uart 通道，使用中断模式、115200 baud、8N1、指定 TX/RX 引脚，并启用对应中断。 | Plan includes explicit Platform IRQ dependency, no DMA edits, and no cross-module ownership violation. Static check and S32DS headless validation pass. | 3 min |
| RTD-M1-MIN-004 | Mcu, Mcl, Port, Uart | Configure one FlexIO-backed Uart channel in polling mode | JSON intent and `uart set` | 我需要在 S32K344 RTD 7.0.1 工程中配置一个 FlexIO Uart 通道，使用轮询模式、115200 baud、8N1，并配置 FlexIO 逻辑通道和 TX/RX 引脚。 | Plan creates or updates Mcl-owned FlexIO common resources, Port-owned pins, and Uart-owned FlexIO channel references. Static check and S32DS headless validation pass. | 3 min |
| RTD-M1-MIN-005 | Mcu, Mcl, Platform, Port, Uart | Configure one FlexIO-backed Uart channel in interrupt mode | JSON intent and `uart set` | 我需要在 S32K344 RTD 7.0.1 工程中配置一个 FlexIO Uart 通道，使用中断模式、115200 baud、8N1、指定 TX/RX 引脚，并启用对应中断。 | Plan includes Mcl FlexIO resources, Port pins, Uart FlexIO channel, and Platform IRQ dependency. Static check and S32DS headless validation pass. | 3 min |
| RTD-M1-MIN-006 | Port | Query generic pin options before Uart pin assignment | `pin-options` | 我需要查询 S32K344 指定封装下某个 LPUART 或 FlexIO Uart 信号可以使用哪些引脚和复用模式，用于后续配置 TX/RX。 | Query reads prepared runtime pin mapping only, returns valid options and conflict information, and does not read Excel or launch vendor tools. | 3 min |
| RTD-M1-MIN-007 | Mcu, BaseNXP, Platform, Port, Dio, Uart | End-to-end minimal LPUART stack | JSON intent | 我需要在一个真实 S32K344 RTD 7.0.1 工程中完成最小 LPUART Uart 配置，让工程通过配置校验并能生成正确配置代码。 | One focused real fixture completes the minimum LPUART stack and passes static check plus S32DS headless validation. | 5 min |
| RTD-M1-MIN-008 | Mcu, BaseNXP, Platform, Port, Mcl, Uart | End-to-end minimal FlexIO Uart stack | JSON intent | 我需要在一个真实 S32K344 RTD 7.0.1 工程中完成最小 FlexIO Uart 配置，让工程通过配置校验并能生成正确配置代码。 | One focused real fixture completes the minimum FlexIO Uart stack and passes static check plus S32DS headless validation. | 5 min |

## Milestone 1 Advanced Tests

Advanced tests are not part of the default Milestone 1 acceptance gate. They
must be executed only when the user explicitly requests advanced coverage.

| ID | Module(s) | Scenario | Request surface | Subagent user prompt | Expected evidence |
| --- | --- | --- | --- | --- | --- |
| RTD-M1-ADV-MCU-001 | Mcu | Configure detailed clock tree parameters | JSON intent and `mcu set-clock` | 我需要调整 S32K344 RTD 7.0.1 工程的 Mcu 时钟配置，包括外部晶振、PLL、CGM 分频和 Uart 使用的时钟参考。 | Localized Mcu clock edits pass static check and backend validation; invalid frequencies produce actionable diagnostics. |
| RTD-M1-ADV-MCU-002 | Mcu | Configure peripheral clock gate only | JSON intent and `mcu set-peripheral-clock` | 我需要只打开一个 Uart 相关外设的 Mcu 外设时钟门控，不改变 Uart 通道配置。 | Peripheral clock gate is changed by Mcu provider only; duplicate peripheral entries are rejected. |
| RTD-M1-ADV-BASENXP-001 | BaseNXP | Configure bare-metal OsIf timer basis | JSON intent and `basenxp` shortcut | 我需要为 S32K344 RTD 7.0.1 工程配置 BaseNXP/OsIf 的裸机系统定时基础，供超时相关功能使用。 | Exactly one valid counter is configured with either an Mcu clock reference or frequency, not both. |
| RTD-M1-ADV-BASENXP-002 | BaseNXP | Enable DET/dev error checks | JSON intent | 我需要打开 BaseNXP/OsIf 的开发错误检测，用于调试阶段发现配置错误。 | DET switch changes generated defines; missing Det availability is diagnosed clearly. |
| RTD-M1-ADV-PLATFORM-001 | Platform | Configure one explicit IRQ entry | JSON intent and `platform set-irq` | 我需要为一个指定 Uart 中断配置 Platform 中断项、优先级和处理函数名称。 | IRQ entry is unique, priority is in range, handler name is valid, and duplicates are rejected. |
| RTD-M1-ADV-PORT-001 | Port | Configure generic GPIO output pin | JSON intent and `port set-pin` | 我需要把一个指定 S32K344 引脚配置为 GPIO 输出，并设置初始电平。 | Port owns mux/direction/level edits; Dio dependency remains explicit if application uses Dio APIs. |
| RTD-M1-ADV-PORT-002 | Port | Configure generic GPIO input pin | JSON intent and `port set-pin` | 我需要把一个指定 S32K344 引脚配置为 GPIO 输入，并设置上下拉和输入缓冲相关参数。 | Port applies generic pin fields and reports invalid package/pin/electrical combinations. |
| RTD-M1-ADV-DIO-001 | Dio, Port | Configure one Dio channel for an already configured GPIO pin | JSON intent and `dio set-channel` | 我需要为一个已经配置为 GPIO 的引脚添加 Dio channel，供应用调用 Dio_ReadChannel 或 Dio_WriteChannel。 | Dio port/channel IDs are unique and missing Port GPIO configuration is reported as dependency information. |
| RTD-M1-ADV-DIO-002 | Dio | Configure one Dio channel group | JSON intent | 我需要为同一个 Dio port 上的一组连续引脚添加 Dio channel group。 | Group ID/name uniqueness and mask formula are validated. |
| RTD-M1-ADV-MCL-001 | Mcl | Configure FlexIO common resource without Uart edit | JSON intent and `mcl set-flexio` | 我需要单独配置一个 Mcl FlexIO common 逻辑通道，后续再给 FlexIO Uart 使用。 | FlexIO instance, channel, and pin resources are unique and referenceable by Uart. |
| RTD-M1-ADV-UART-001 | Uart | Configure multiple Uart channels in one request | JSON intent | 我需要一次性配置两个 Uart 通道，一个 LPUART、一个 FlexIO Uart，要求资源不冲突。 | Full channel array is planned before editing; duplicate IDs, names, hardware instances, and stale refs are rejected. |
| RTD-M1-ADV-UART-002 | Uart, BaseNXP | Configure callback, timeout, idle, and API switches | JSON intent | 我需要给一个 Uart 通道配置回调函数、超时能力、空闲检测和版本信息 API。 | Callback symbols, timeout configuration, version API, DET, and OSIF dependencies are valid or actionable blockers. |

## Reserved Future Test Cases

Reserved future cases are retained for traceability. They are not executable
Milestone 1 acceptance tests. Their exact execution plan, fixture shape, and
KPI will be determined when Milestone 2 or later milestones are planned.

| ID | Planned milestone | Module(s) | Scenario | Subagent user prompt |
| --- | --- | --- | --- | --- |
| RTD-FUT-M2-CREATE-001 | Milestone 2 | Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart | Complete missing modules in a partial `.mex` | 我需要在一个缺少部分基础模块的 S32K344 RTD 7.0.1 工程中补齐 Uart 最小配置所需模块。 |
| RTD-FUT-M2-CREATE-002 | Milestone 2 | Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart | Create a base `.mex` from prepared templates | 我需要从零创建一个 S32K344 RTD 7.0.1 `.mex` 配置文件，并包含 Uart 最小配置所需模块。 |
| RTD-FUT-M2-UART-DMA-001 | Milestone 2 | Uart, Mcl, Platform | Enable Uart DMA transfer | 我需要为 S32K344 RTD 7.0.1 工程中的 Uart 通道启用 DMA 收发，并配置相关 Mcl DMA 资源。 |
| RTD-FUT-M3-MCU-LOWPOWER-001 | Milestone 3+ | Mcu, Platform | Configure low-power modes and interrupt-backed notifications | 我需要配置 Mcu 低功耗模式、相关唤醒或错误通知，并让必要中断配置正确。 |
| RTD-FUT-M3-MCU-RAM-001 | Milestone 3+ | Mcu | Configure RAM sections | 我需要给 S32K344 RTD 7.0.1 工程添加 Mcu RAM section 初始化配置。 |
| RTD-FUT-M3-MCU-RESET-001 | Milestone 3+ | Mcu | Configure reset and callouts | 我需要启用 Mcu reset API，并配置复位前后的回调函数。 |
| RTD-FUT-M3-BASENXP-OS-001 | Milestone 3+ | BaseNXP | Configure custom timer, AUTOSAR OS mode, multicore, user mode, or software semaphore | 我需要把 BaseNXP/OsIf 配置为 AUTOSAR OS 或多核用户模式，并配置所需计数器和分区引用。 |
| RTD-FUT-M3-PLATFORM-MPU-001 | Milestone 3+ | Platform | Configure MPU M7 regions | 我需要配置 Cortex-M7 MPU region、访问权限和 cache 策略。 |
| RTD-FUT-M3-PLATFORM-MCM-001 | Milestone 3+ | Platform | Configure MCM/system settings | 我需要配置 Platform MCM/system interrupt 相关参数。 |
| RTD-FUT-M3-PLATFORM-INTM-001 | Milestone 3+ | Platform | Configure interrupt monitor | 我需要启用 Platform interrupt monitor 并配置监控通道和可接受延迟。 |
| RTD-FUT-M3-DIO-PARTITION-001 | Milestone 3+ | Dio | Configure multi-partition or virtual wrapper | 我需要为 Dio 配置多分区或 virtual wrapper 支持，并引用已有分区。 |
| RTD-FUT-M3-MCL-RES-001 | Milestone 3+ | Mcl | Configure eMIOS, TRGMUX, LCU, cache, or non-Uart shared resources | 我需要配置 Mcl 的 eMIOS、TRGMUX、LCU 或 cache 相关共享资源。 |

## Required Coverage Categories

Every implemented module or set feature must eventually have tests for:

- valid configuration;
- invalid or missing resources;
- dependency resolution;
- ownership boundaries;
- static diagnostics;
- backend validation result when the backend supports validation;
- shortcut command normalization when a shortcut exists;
- JSON intent path.

For Milestone 1, only the mandatory minimum tests are required by default.
Advanced tests are executed only by explicit user instruction. Reserved future
tests are planning inputs, not current acceptance gates.

## Independent Subagent Validation

Key test cases must be validated by independent subagents.

Subagent validation requirements:

- each subagent call must set `"fork_context": false`;
- with `"fork_context": false`, the subagent is fully independent from the main
  agent and has isolated context;
- the subagent must not see the main agent's analysis, implementation details,
  hidden assumptions, or debugging process;
- the subagent should rely only on the simulated user configuration request,
  repository files, companion skills, and the public CLI;
- each subagent validation run should focus on one test case;
- the subagent prompt supplied for a case must contain only the simulated user
  configuration demand from the case table.

Independent subagent validation targets fixture integration and backend
validation behavior. The main development agent may run fast deterministic
tests during implementation, but those fast checks do not replace independent
validation of fixture edits and backend validation results.

## Failure Iteration Loop

Any development test, fixture integration test, backend validation, or
independent subagent validation failure must feed back into implementation.
The responsible main agent must analyze the failed case, identify whether the
cause is code, runtime data, fixture setup, test wording, diagnostics, or
performance, fix the root cause, and rerun the relevant tests. A feature is not
accepted until the failed case and its related regression coverage pass.

If a subagent run exceeds 10 minutes, the main agent must intervene, stop
treating the case as converged, and collect the issue evidence needed for
debugging.

## KPI

The KPI applies to all module configuration flows:

- focused independent subagent validation should converge within 3 minutes;
- E2E independent subagent validation should converge within 5 minutes;
- subagent execution may run for up to 10 minutes to expose useful failure
  evidence;
- after 10 minutes, the main agent intervenes and records the problem;
- the ideal path is: understand the simulated user demand, use the companion
  skills and public CLI, and pass runtime verification once;
- repeated KPI misses indicate a problem in the public interface, companion
  skills, diagnostics, runtime performance, fixture design, or test-case prompt.

## Acceptance Rule

A module or feature is accepted when:

- required mandatory minimum test cases pass for the current milestone;
- backend validation passes when applicable;
- focused independent subagent validation meets the KPI;
- failures produce actionable diagnostics rather than tracebacks or ambiguous
  logs.

Advanced tests do not block Milestone 1 acceptance unless the user explicitly
adds them to the required test set.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.4.0 | Split Milestone 1 tests into mandatory minimum, advanced, and reserved future sets; added subagent user prompts and KPI clarification. |
| 2026-06-02 | 0.3.0 | Added first-milestone test case catalog from retired module use-case skills and documented the failure iteration loop. |
| 2026-05-30 | 0.2.1 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.0 | Clarified independent subagent validation scope. |
| 2026-05-30 | 0.1.0 | Created RTD CfgFile CLI test strategy. |
