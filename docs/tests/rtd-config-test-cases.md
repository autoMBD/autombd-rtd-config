# RTD CfgFile CLI E2E Test Cases

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-06-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | The E2E acceptance test cases for the RTD CfgFile CLI (`.mex` backend, scheme `RTD-MEX-*`). Each case is executed by a fully isolated subagent that sees nothing of this repository — only the released `autombd-rtd` skill/CLI, the case's prompt, and the test fixture. Unit/integration coverage lives in the deterministic pytest suite and is governed by the test strategy, not listed here. |

> **Governed by [`rtd-config-test-strategy.md`](rtd-config-test-strategy.md)**
> (test layers, the vendor pass gate — exit `0` AND no SEVERE `[TOOL]` —, the
> acceptance rule, roles, KPIs). Per-module facts a case exercises (valid
> values, constraints, dependencies) come from each `<Module>.xdm` via its
> provider asset; cross-cutting fixture and S32DS-command facts live in
> [`../specs/rtd-config-domain-truth.md`](../specs/rtd-config-domain-truth.md).
> New modules add their cases here in the same format; delivery staging lives in
> the [roadmap](../roadmaps/rtd-config-roadmap.md).

## 1. Execution protocol — fully isolated subagent

E2E cases prove the **released skill** works in a cold environment. The
executing subagent (the Tester role, or its delegate) is **context-isolated**:
it must not see this repository, its specs, sources, or tests. The isolation
mechanism is whatever the agent platform provides (a fresh, non-inherited
context).

1. Create a dedicated temporary directory outside this repository
   (e.g. `%TEMP%\autombd-rtd-e2e-<case-id>\`).
2. Stage into it **only**: (a) a copy of the released `autombd-rtd/` skill
   (`SKILL.md`, the `__main__.py` launcher, `assets/`, and the bundled CLI under
   `rtd-config-cli-py/`), and (b) a copy of the case's test fixture project.
3. Dispatch the isolated subagent whose entire input is the case's **Subagent
   Prompt** plus the two staged paths.
4. The subagent satisfies the prompt using the skill and its CLI only
   (`python <skill-dir> <command>`).
5. Evidence required for PASS: the case's **Pass criteria**, the vendor gate
   (ConfigTools exit `0` **and** no SEVERE `[TOOL]` problem), and successful
   code generation (the validation flow's `-UpdateCode` step completes).
6. KPIs (strategy §4): focused ≤ 3 min; E2E ≤ 5 min; the orchestrator
   intervenes at 10 min.

## 2. Test cases

All cases use the fixture `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/`
(staged into the temporary directory per §1).

| ID | Module | Scenario | Subagent Prompt | Test fixture | Pass criteria |
| --- | --- | --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | Modify MCU Clock configuration | 修改MCU的时钟配置，外部晶振16MHz，CORE_CLK=160MHz，AIPS_PLAT_CLK=80MHz，AIPS_SLOW_CLK=40MHz，修改后其他时钟源不报错。在Clock Reference Point中添加所有可选的时钟并将名称修改为对应的时钟 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | 时钟配置正确，S32DS验证通过，能正确生成代码 |
| RTD-MEX-BASENXP-001 | BaseNXP | Modify OsIf configuration | 使能OsIf的系统定时器作为计数时基（供UART等驱动的超时机制使用），修改后配置不报错 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | OsIf配置正确（计数器使能、参数有效），S32DS验证通过，能正确生成代码 |
| RTD-MEX-PLATFORM-001 | Platform | Modify interrupt configuration | 将LPUART_3中断的优先级修改为2，确认该中断已使能且ISR正确注册，其他中断配置不受影响 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | Platform中断配置正确（使能、优先级生效、ISR注册正确），S32DS验证通过，能正确生成代码 |
| RTD-MEX-PORT-001 | Port | Modify pin mux configuration | 先用pin-options查询LPUART_0可用的TX/RX引脚，再将查询到的合法引脚配置为LPUART_0的TX/RX（含复用与方向），其他引脚配置不受影响 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | 引脚复用与电气配置正确且来自合法的查询结果，S32DS验证通过，能正确生成代码 |
| RTD-MEX-DIO-001 | Dio | Add Dio channel configuration | 新增一个DIO输出通道用于LED控制：符号名LED_CTRL，选择一个未被占用的GPIO引脚并配置为输出方向 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | Dio通道与符号名配置正确，引脚方向由Port正确配置，S32DS验证通过，能正确生成代码 |
| RTD-MEX-MCL-001 | Mcl | Add FlexIO logic channel configuration | 使能Mcl的FlexIO公共资源并新建一个FlexIO逻辑通道（命名为FLEXIO_UART_CH0，供后续FlexIO UART使用） | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | FlexIO公共资源与逻辑通道配置正确、命名生效且引用一致，S32DS验证通过，能正确生成代码 |
| RTD-MEX-UART-001 | UART | Modify Uart Channel Configuration | 修改UART通讯参数为8bit、921600波特率、无校验位、停止位1bit，改外设实例为LPUART_8，使能中断模式，回调函数Autombd_UartCallback。 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | Platform 使能并注册了正确的ISR，MCU参考时钟正确，设置了优先级，S32DS验证通过，能正确生成代码 |
| RTD-MEX-UART-002 | UART | Add new Uart Channel Configuration | 新增一个基于FlexIO的UART通道，包含Tx和Rx，通讯参数为8bit、921600波特率、无校验位、停止位1bit，使能中断模式，回调函数Autombd_UartCallback | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | Platform 使能并注册了正确的ISR（中断模式对全局起作用，所以LPUART和FlexIO都要使能和配置ISR），设置了优先级，MCL创建了正确的FlexIO逻辑通道并且引用正确，MCU参考时钟正确，S32DS验证通过，能正确生成代码 |
| RTD-MEX-UART-003 | UART | Config Uart Channel DMA mode | 修改已有的Uart通道，使能DMA模式，使能中断，回调函数Autombd_UartCallback | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | Platform 使能并注册了正确的ISR（DMA模式下，中断由DMA产生），设置了优先级，MCL配置了正确的DMA通道和instance，MCU参考时钟正确，S32DS验证通过，能正确生成代码 |

## 3. Case status and dependencies

The catalog defines the **acceptance target**; current pass/fail evidence is
recorded in [`rtd-config-acceptance-report.md`](rtd-config-acceptance-report.md).
Known capability dependencies:

- `RTD-MEX-UART-003` requires the Uart/Mcl **DMA capability**, which is not yet
  implemented — the current tool intentionally rejects DMA requests
  (diagnostic `dma_not_supported_in_m1`). The case stands as the target that
  drives that capability; it is not weakened to match the current tool.
- `RTD-MEX-PORT-001` (and every pin-applying case) depends on the complete
  `pins.json` asset rebuilt from the pin-mux source workbook
  (domain-truth §1); until then `pin-options` output is unverified.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-10 | 0.2.0 | Fourth-round review resolution: restructured to E2E-only cases in the format ID/Module/Scenario/Subagent Prompt/Test fixture/Pass criteria (scheme `RTD-MEX-*`); seeded with the reviewer's MCU clock and three UART cases (incl. DMA) and extended to all seven minimal-system modules; added the fully-isolated subagent execution protocol; renamed the document from `rtd-config-m1-test-cases.md` (m1 dropped from all doc names). |
| 2026-06-06 | 0.1.0 | Extracted the M1 mandatory matrix, scope guards, and out-of-scope list from `rtd-config-test-strategy.md` v0.5.0 into this standalone, per-milestone test-cases document. |
