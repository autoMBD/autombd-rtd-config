# Reviewed Draft Backup: S32K3 RTD 7.0.1 MEX Configuration Core Design

> Archive status: unavailable for requirements. This reviewed draft is kept
> only for comment traceability. Do not read or use it to infer current
> behavior, terminology, scope, architecture, test requirements, or acceptance
> criteria. Use only active documents outside `docs/superpowers/specs/achieved/`.

| Field | Value |
| --- | --- |
| Version | 0.1.3 |
| Date | 2026-05-30 |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | Archives the first reviewed design draft with inline comments preserved. |

This archived draft preserves the reviewed spec with the user's inline
`REVIEW` comments in their original content context. It is kept for traceability
only; the active spec is `../rtd-config-core-design.md`.

---

# S32K3 RTD 7.0.1 MEX Configuration Core Design

## Purpose

This project builds a deterministic configuration tool for S32K3 RTD 7.0.1
projects that use S32 ConfigTools `.mex` files. The first formal phase focuses
on modifying existing S32DS projects efficiently and safely enough for
human-agent collaboration.

<!-- REVIEW: 人机合作指的是是这个工具开发过程中我会和你一起，而不是这个工具是用于人机合作的，这个工具的目标是让AI Agent可以直接使用并自主完成RTD配置，具备快速、高效、准确性和稳定性。 -->
<!-- REVIEW: 你在Purpose中提第一阶段的、限制功能的内容，不利于后续扩展新模块、新芯片平台。目标要写清除，第一阶段可以的限制、可以在计划、路线图中说明。 -->
<!-- REVIEW: 目标要说明完整的计划，即要支持RTD的全部模块（不仅仅是driver模块，还应包括官方的RTD RTOS、Stacks、外围芯片的driver），要支持.mex（S32 ConfigTools）和（xmd（EB Tresos），要支持扩展跟多芯片（K1、K5等），要支持扩展新版的RTD。 -->

The external contract is a CLI that emits stable JSON. Internal Python modules
should be clean and testable, but their API is not the compatibility boundary
for the first phase.

<!-- REVIEW: 同样，在Spec中不要提及第一阶段、限制等 -->

This design deliberately does not define an AI Agent workflow platform. The
development and validation loop will be guided during the project. Independent
subagent validation is included only as a verification requirement.

<!-- REVIEW: 不太明白这里提到的AI Agent workflow platform是什么，我希望在这个项目开发过程中你可以实现可以闭环的开发、测试工作流，这很重要。但这套流程可能需要更多的支撑（例如skills），当前不太完善，需要逐步添加更多支撑。所以我说我会以人机合作的方式辅助你，但辅助你的核心方向是让你实现闭环的开发、测试工作流。此外这个部分并不属于项目的spec内容，它应该是一种独立于项目的开发模式，你需要知道清楚，把这部分内容单独放到一个文件里。 -->

## Scope

Phase 1 supports:

- S32K3 RTD 7.0.1.
- S32 ConfigTools `.mex` configuration.
- Existing S32DS projects only.
- Device architecture extensible to S32K3, with validation committed for
  S32K344 first.
- Seven RTD modules: `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`,
  and `Uart`.
- Uart configuration for LPUART and FlexIO Uart.
- Interrupt and polling modes.
- Basic Uart communication parameters: baudrate, word length, stop bits,
  parity, timeout, callback, channel id, hardware channel, and references.
- Generic Port pin configuration through complete versioned pin mapping data.
- Generic Dio port/channel basic configuration.
- Mcl FlexIO basic configuration.
- JSON intent files and module-specific shortcut commands.
- In-place `.mex` modification as the normal workflow.
- Optional `--backup`, disabled by default.
- Fast static checks plus no-window S32DS headless validation.

Phase 1 does not support:

- Creating a `.mex` from scratch.
- Completing missing modules in a partial `.mex`.
- DMA.
- EB tresos.
- K1/K5 validation.
- Runtime Excel parsing.
- Default copy-output workflows.

From-scratch creation and missing-module completion are deferred until after
DMA support.

<!-- REVIEW: 关于第一阶段的计划和限制，放到实施计划和路线图中说明 -->

## Chosen Architecture

Use a modular configuration core with a CLI shell.

The design has five layers:

1. CLI layer
   Provides core commands and shortcut commands. Shortcut commands only build
   normalized intent and then use the same plan/apply/check/validate pipeline.

2. Intent and plan layer
   Loads JSON intent or shortcut command arguments, normalizes requests, and
   produces a deterministic plan before any write.

3. MEX document core
   Parses `.mex` XML, builds an efficient document index, provides structured
   setting/container upsert helpers, performs localized writes, and preserves
   small diffs where practical.

<!-- REVIEW: .mex文件可能会非常庞大，这里解析和构建index要考虑效率问题，我觉得runtime时解析可能不可靠，但我们可以先验证看看效果如何，再分析最优方案。 -->

4. Module providers
   Each module owns its own plan/apply logic and only writes its own `.mex`
   configuration area.

<!-- REVIEW: Module providers需要考虑不太模块之间的依赖和关联，例如FlexIO Uart依赖Mcl，中断模式依赖Platform使能ISR和设置优先级 -->
<!-- REVIEW: Module providers还需要考虑配置项的限制约束条件，比如不同型号芯片的可用引脚数量不同，可用外设数量也不同。RTD安装目录下，每个模块内有相应的文件描述模块配置依赖和约束，例如Uart："C:\NXP\S32DS.3.6.7\S32DS\software\PlatformSDK_S32K3\RTD\Uart_TS_T40D34M70I1R0\config\Uart.xdm" -->

5. Shared resource services
   Provide pin mapping, schema/cache access, references, diagnostics,
   validation command construction, and runtime configuration loading.

Two architecture rules are mandatory:

- A module provider may only write the configuration area it owns.
- Shared concerns such as XML editing, pin mapping, diagnostics, schema/cache,
  and validation must live in core/shared layers, not inside individual module
  implementations.

<!-- REVIEW: 开发过程中引用的材料、文件（例如我给你excel文件、driver模块的约束限制文件等），一定不能出现再代码中，也不能在runtime时引用，这个工具的作用就是提前将所需的一切准备好，以实现高效、快速、准确的自主配置。 -->

These rules specifically prevent the PoC problem where Uart logic wrote Port
configuration directly. Uart may request pins, clocks, interrupts, or FlexIO
resources, but Port, Mcu, Platform, and Mcl providers must perform their own
writes.

<!-- REVIEW: 这是一个Spec，写怎么做就行了，不要提什么PoC的问题。 -->

## Module Responsibilities

### Mcu

Phase 1 only covers the clock and reference functionality needed by Uart:

- confirm or set LPUART and FlexIO related clock references;
- confirm or enable required peripheral clocks;
- expose clock/reference lookup to other providers.

Only `Mcu` may write Mcu configuration.

### BaseNXP

`BaseNXP` is small enough for broad phase-1 coverage. It should support set
operations for its available parameters, including OsIf and timer basis
settings.

Only `BaseNXP` may write BaseNXP configuration.

### Platform

Phase 1 covers Uart-related interrupt configuration:

- interrupt controller enablement;
- IRQ enable/disable;
- priority;
- handler/vector basics.

Polling mode should not require unnecessary interrupt writes.

Only `Platform` may write Platform configuration.

### Port

`Port` must implement generic pin configuration, not Uart-specific pin
configuration.

The input model should support device, package, pin, peripheral, signal,
function, direction, and pad-related fields. Uart is only the first consumer.
Future modules must use the same Port provider path for pins.

Runtime pin data comes from versioned JSON committed in the repository. The
Excel file and RTD installation data are development inputs only.

Only `Port` may write Port configuration.

### Dio

`Dio` supports generic port/channel basics:

- port name/id;
- channel name/id;
- direction and initial value where represented in the target configuration;
- uniqueness checks for ids within the relevant owner.

Dio must not be tied to Uart.

Only `Dio` may write Dio configuration.

### Mcl

`Mcl` supports generic FlexIO foundation configuration:

- FlexIO common resources;
- logic channels;
- timers and shifters;
- references needed by FlexIO Uart.

The first validation path is FlexIO Uart, but Mcl should not be designed as a
Uart-only helper.

Only `Mcl` may write Mcl configuration.

### Uart

`Uart` supports:

- LPUART channels;
- FlexIO Uart channels;
- interrupt and polling modes;
- baudrate, word length, stop bits, parity, timeout, callback, channel id,
  hardware channel, clock reference, and resource references.

DMA is deferred. Uart must not write Port, Mcu, Platform, or Mcl areas.

<!-- REVIEW: 上面这些Module Responsibilities，单独写一张表，并且支持支持维护更新，支持后续添加新模块 -->

## CLI Contract

Core commands:

```powershell
rtd-config inspect --mex app.mex --json
rtd-config plan --mex app.mex --intent intent.json --json
rtd-config configure --mex app.mex --intent intent.json --json
rtd-config check --mex app.mex --json
rtd-config validate --mex app.mex --project app --json
rtd-config pin-options --device S32K344 --package <package> --peripheral LPUART_6 --json
```

Shortcut command groups:

```powershell
rtd-config uart set ...
rtd-config port set-pin ...
rtd-config dio set-channel ...
rtd-config mcu set-clock ...
rtd-config platform set-irq ...
rtd-config basenxp set ...
rtd-config mcl set-flexio ...
```

Shortcut commands are convenience wrappers. They must normalize into the same
intent model used by `plan` and `configure`.

`configure` is non-interactive. Users who need review should run `plan`
explicitly before `configure`.

## Runtime Configuration

Use a repository JSON configuration file for default paths and settings. CLI
parameters may override JSON values.

The configuration should cover:

- S32DS root;
- workspace path;
- default project path when useful;
- default device and package;
- RTD/schema/cache locations;
- validation timeout;
- validation log directory.

The format is JSON to avoid runtime dependencies beyond the Python standard
library.

## Data Assets

Runtime data is committed as JSON/cache files. The structure should be
extensible across S32K3 devices even though phase-1 validation is for S32K344.

<!-- REVIEW: 同样，不要在Spec中提phase1，在实施计划和路线图中说明 -->

Suggested structure:

```text
data/
  s32k3/
    s32k344/
      pins/
        <package>.pins.json
      rtd_7_0_1/
        schemas/
          mcu.json
          basenxp.json
          platform.json
          port.json
          dio.json
          mcl.json
          uart.json
        modules/
          mcu.json
          basenxp.json
          platform.json
          port.json
          dio.json
          mcl.json
          uart.json
```

The pin mapping JSON is a first-class asset. It should be complete enough for
the supported S32K344 package used by the real fixture project. Data may include
multiple packages, but only the fixture package is required for phase-1
acceptance.

<!-- REVIEW: 在实施计划和路线图中说明Port第一阶段就要实现完整、通用的功能 -->

The Excel file
`D:\WorkSpace\ExploreSpace\Copy of S32K344_S32K324_S32K314_IOMUX.xlsx` and RTD
installation resources may be used to build the JSON asset during development.
The runtime tool must not read Excel.

<!-- REVIEW: 不要在Spec中把参考引用资料写死，可用新增一个Reference的文档，spec中只说明需要引用什么，在哪里找即可 -->

## MEX Editing Strategy

Use structured XML/document operations as the primary implementation strategy.

Requirements:

- parse once per command and share one context across providers;
- build a document index for module instances, containers, settings,
  references, pins, and interrupts;
- use upsert helpers for settings and containers;
- avoid broad whole-file rewrites;
- keep diffs small enough for review;
- use controlled localized text handling only where ConfigTools XML requires it;
- never expose Python tracebacks as the command interface.

<!-- REVIEW: 同样，mex文件编写一定要考虑效率问题，后续的.xdm文件的编辑可用放一个简略版 -->

## Diagnostics

All commands return stable JSON diagnostics:

```json
{
  "status": "passed|failed|blocked",
  "command": "configure",
  "diagnostics": [
    {
      "severity": "blocker|error|warning|info",
      "code": "missing_pin_mapping",
      "module": "port",
      "message": "Pin PTA15 is not available for the requested package/function.",
      "details": {}
    }
  ]
}
```

Diagnostics must be actionable. They should identify the module, missing or
invalid resource, and useful details for correction.

## Validation Pipeline

`configure` runs:

1. load configuration;
2. parse/index `.mex`;
3. normalize intent;
4. plan;
5. apply in place;
6. run static checks;
7. run S32DS headless validation without opening a window;
8. return changed modules, diagnostics, validation logs, and status.

`validate --dry-run` should remain available for path and command diagnosis.
`configure` defaults to real validation.

S32DS validation requirements:

- no visible GUI window;
- configurable timeout;
- stdout/stderr/log capture;
- JSON result with command, resolved paths, exit code, and log paths;
- clear failure diagnostics.

## Performance Requirements

Commands must be efficient.

- Runtime commands must not scan RTD installation directories.
- Runtime commands must not read Excel.
- `inspect`, `plan`, `check`, and `pin-options` must not launch S32DS.
- Single command execution should parse `.mex` once and reuse indexes.
- Versioned JSON/cache data must be used for module and pin knowledge.
- `configure` may be slower because S32DS validation is required, but tool
  overhead before validation should remain small.

## Fixtures

The primary real project fixture lives under:

```text
fixtures/
  projects/
    s32k344_uart/
```

The fixture should be a real, complete UART S32DS project. It should include
files needed for S32DS headless validation, while excluding build/debug/generated
artifacts that do not belong in source control.

Future modules should add similar real project fixtures:

```text
fixtures/projects/s32k344_spi/
fixtures/projects/s32k344_pwm/
fixtures/projects/s32k344_adc/
```

<!-- REVIEW: Spec中不要指定特定的工程，描述fixtures通用结构即可 -->

## Tests

Testing has two layers.

Fast deterministic tests do not require S32DS and cover:

- intent validation;
- shortcut command normalization;
- pin mapping lookup;
- MEX indexing;
- localized XML edits;
- provider ownership boundaries;
- provider plan/apply behavior;
- diagnostics;
- static checks;
- validation command construction.

Real project validation modifies the `.mex` inside the fixture project and then
runs no-window S32DS headless validation on that project. This is the highest
phase-1 acceptance standard.

The test matrix must cover all phase-1 functionality:

- seven module shortcut set paths;
- JSON intent path;
- LPUART Uart interrupt mode;
- LPUART Uart polling mode;
- FlexIO Uart interrupt mode;
- FlexIO Uart polling mode;
- generic Port pin mapping and application;
- generic Dio channel configuration;
- Mcu Uart-related clock/ref configuration;
- BaseNXP parameter set coverage;
- Platform Uart-related IRQ configuration;
- Mcl FlexIO base configuration;
- static check failures;
- S32DS validation failures;
- missing or invalid mapping diagnostics;
- optional `--backup`.

<!-- REVIEW: 开发过程中，所有模块的验证都是这样的，今后的验证方式也是这样的，不仅仅是phase1，不要在Spec中提phase1 -->
<!-- REVIEW: 需要单独的测试文档来说明不同模块的测试过程，测试文档中需要详细写测试案例（test case），不要在Spec中描述特定模块的测试要求，Spec要说明完成测试文档要求的测试内容 -->

## Independent Subagent Validation

Key test cases must also be validated by independent subagents.

Subagent validation requirements:

- each subagent call must set `"fork_context": false`;
- with `"fork_context": false`, the subagent is fully independent from the main
  agent and has isolated context;
- the subagent must not see the main agent's analysis, implementation details,
  hidden assumptions, or debugging process;
- the subagent should rely only on the user requirement, test-case instructions,
  repository files, and the public tool interface;
- each subagent validates one focused test case whenever practical.

<!-- REVIEW: 这部分放到测试文档中说明，属于测试流程 -->

KPI:

- each subagent validation of one test case must complete within 3 minutes;
- the ideal path is: understand the user need, infer the intent, call the tool,
  and pass validation once;
- if a focused test case routinely exceeds 3 minutes, the tool interface,
  diagnostics, performance, or test design should be improved.

<!-- REVIEW: 这个KPI是所有模块配置的KPI，需要单列小结中描述 -->

## Suggested Project Structure

```text
rtd_config/
  __main__.py
  cli.py
  config.py
  diagnostics.py
  intent.py
  plan.py
  mex/
    document.py
    index.py
    edit.py
    writer.py
  modules/
    base.py
    mcu.py
    basenxp.py
    platform.py
    port.py
    dio.py
    mcl.py
    uart.py
  resources/
    pins.py
    schema.py
    validation.py
  checks/
    static.py
data/
  s32k3/
fixtures/
  projects/
tests/
  unit/
  integration/
docs/
  superpowers/
    specs/
```

## Implementation Sequence

1. Establish package, CLI, JSON diagnostics, configuration loading, and
   validation command construction.
2. Add MEX document parsing, indexing, and localized edit helpers.
3. Add real `fixtures/projects/s32k344_uart/` project and inspect/check support.
4. Add S32K344 pin mapping JSON and generic Port provider.
5. Implement minimal LPUART Uart path with Mcu, Platform, and Port dependencies.
6. Add no-window S32DS headless validation to `configure`.
7. Add FlexIO foundation in Mcl and FlexIO Uart in Uart.
8. Add BaseNXP broad set support and Dio generic channel support.
9. Add seven module shortcut command groups.
10. Complete the full test matrix and independent subagent validation pass.

## Success Criteria

Phase 1 is successful when:

<!-- REVIEW: 同样的，不要在Spec中提Phase1 -->

- core CLI commands return stable JSON;
- shortcut commands normalize to the same intent pipeline;
- existing S32K344 UART fixture can be modified in place;
- LPUART Uart interrupt and polling configurations pass S32DS validation;
- FlexIO Uart interrupt and polling configurations pass S32DS validation;
- Port pin configuration is generic and uses committed pin mapping JSON;
- Uart does not directly write Port, Mcu, Platform, or Mcl configuration;
- Mcl FlexIO configuration is owned by Mcl provider;
- all seven modules expose basic set functionality;
- static and validation diagnostics are actionable;
- runtime commands avoid Excel, RTD scanning, and avoidable repeated parsing;
- test coverage spans all phase-1 functions;
- independent subagent validation meets the 3-minute KPI for focused test cases.

<!-- REVIEW: 验收应该以测试文档和测试结果为标准，简单来说就两个：1）满足KPI；2）测试案例通过 -->
<!-- REVIEW: 测试文档也需要不同阶段设置，支持可维护、可更新、可扩展 -->

<!-- REVIEW: 下面是总结，很重要！！ -->
<!-- REVIEW: 总的来说，Spec一开始要尽可能的完整、详尽，Spec需要可维护、可更新、可迭代，我们讨论的第一阶段的有限功能开发在制定计划的时候说明清楚，而不是在Spec中。 -->
<!-- REVIEW: 当前Spec需要新增一些文件来增强可维护性，包括参考文件、测试文件等，详见上面的comments -->
<!-- REVIEW: 要区分开发模式和Spec，开发模式可能会因为不可预测的问题改变路线，而Spec是描述项目本身的目标、功能、技术栈等信息，是我们开发的指南针 -->
<!-- REVIEW: 要注意开发过程中的工具资源引用和runtime时的资源调度和依赖，不能把开发过程中调用、依赖的一些文件带到runtime时使用，因为runtime环境是不确定的。例如pin映射表，开发过程中你会引用我给你的excel表，在工具内构建映射、查找关系，runtime时就不再需要这个excel表了。 -->

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-05-30 | 0.1.3 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.1.2 | Renamed archived reviewed draft to remove date from filename. |
| 2026-05-30 | 0.1.1 | Standardized archive metadata and added changelog. |
| 2026-05-30 | 0.1.0 | Archived reviewed draft with inline comments preserved in context. |
