# RTD CfgFile CLI E2E Test Cases

| Field | Value |
| --- | --- |
| Version | 0.3.2 |
| Date | 2026-06-13 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | The E2E acceptance test cases for the RTD CfgFile CLI (`.mex` backend, scheme `RTD-MEX-*`). Each case is executed by a fully isolated subagent that sees nothing of this repository — only the released `autombd-rtd` skill/CLI, the case's prompt, and the test fixture. Unit/integration coverage lives in the deterministic pytest suite and is governed by the test strategy, not listed here. |

> **Governed by [`rtd-config-test-strategy.md`](rtd-config-test-strategy.md)**
> (test layers, the vendor pass gate — exit `0` AND no SEVERE `[TOOL]` —, the
> acceptance rule, roles, KPI monitoring and KPI-optimization loop). Per-module facts a case exercises (valid
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
5. Evidence required for functional PASS: the case's **Pass criteria**, the vendor gate
   (ConfigTools exit `0` **and** no SEVERE `[TOOL] … has the following error`
   problem), and successful code generation (the validation flow's `-ExportSrc`
   step emits generated source — verified Flow B, domain-truth §3).
6. KPI evidence is mandatory for every case. If functional validation passes but
   the KPI is missed, the main agent returns the case to the Worker for KPI
   optimization. The same case gets at most three KPI-optimization iterations.
   After the third KPI miss, the Tester records the true KPI result and the case
   may proceed with its functional PASS evidence.
7. KPIs (strategy §4): focused ≤ 3 min; E2E ≤ 5 min; the orchestrator
   intervenes at 10 min. The case table's `Subagent Prompt` cells may stay in
   Chinese because they are the exact user-facing prompts; all other catalog
   text is English.

## 2. Test cases

All cases use the fixture `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/`
(staged into the temporary directory per §1).

| ID | Module | Scenario | Subagent Prompt | Test fixture | KPI | Pass criteria |
| --- | --- | --- | --- | --- | --- | --- |
| RTD-MEX-MCU-001 | MCU | Modify MCU clock configuration | 修改MCU的时钟配置，外部晶振16MHz，CORE_CLK=160MHz，AIPS_PLAT_CLK=80MHz，AIPS_SLOW_CLK=40MHz，修改后其他时钟源不报错。在Clock Reference Point中添加所有可选的时钟并将名称修改为对应的时钟 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 2 min. | Clock configuration is correct, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-BASENXP-001 | BaseNXP | Modify OsIf configuration | 使能OsIf的系统定时器作为计数时基（供UART等驱动的超时机制使用），修改后配置不报错 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | OsIf configuration is correct (counter enabled, parameters valid), S32DS validation passes, and code generation succeeds. |
| RTD-MEX-PLATFORM-001 | Platform | Modify interrupt configuration | 将LPUART_3中断的优先级修改为2，确认该中断已使能且ISR正确注册，其他中断配置不受影响 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | Platform interrupt configuration is correct (enabled, priority applied, ISR registered), S32DS validation passes, and code generation succeeds. |
| RTD-MEX-PORT-001 | Port | Modify pin-mux configuration | 先用pin-options查询LPUART_0可用的TX/RX引脚，再将查询到的合法引脚配置为LPUART_0的TX/RX（含复用与方向），其他引脚配置不受影响 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | Pin mux and electrical configuration are correct and come from a legal `pin-options` result, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-DIO-001 | Dio | Add Dio channel configuration | 新增一个DIO输出通道用于LED控制：符号名LED_CTRL，选择一个未被占用的GPIO引脚并配置为输出方向 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | Dio channel and symbolic name are configured correctly, pin direction is configured correctly by Port, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-DIO-002 | Dio | Add Dio channel on a pin whose DioPort container does not yet exist | 新增一个DIO输出通道用于LED控制：符号名LED_CTRL，引脚选择PTA30（其DioPort容器在工程中尚不存在），配置为输出方向 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | The missing DioPort container is auto-created with a correct DioPortId and the channel/symbolic name are configured correctly (DioConf_DioChannel_LED_CTRL, DioConf_DioPort_DioPort_1), pin direction is configured by Port, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-MCL-001 | Mcl | Add FlexIO logic-channel configuration | 使能Mcl的FlexIO公共资源并新建一个FlexIO逻辑通道（命名为FLEXIO_UART_CH0，供后续FlexIO UART使用） | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | FlexIO common resources and the logic channel are configured correctly, naming takes effect, references are coherent, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-UART-001 | UART | Modify Uart channel configuration | 修改UART通讯参数为8bit、921600波特率、无校验位、停止位1bit，改外设实例为LPUART_8，使能中断模式，回调函数Autombd_UartCallback。 | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | Platform enables and registers the correct ISR, the MCU reference clock is correct, priority is set, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-UART-002 | UART | Add new Uart channel configuration | 新增一个基于FlexIO的UART通道，包含Tx和Rx，通讯参数为8bit、921600波特率、无校验位、停止位1bit，使能中断模式，回调函数Autombd_UartCallback | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 1 min. | Platform enables and registers the correct ISR (interrupt mode is global, so both LPUART and FlexIO require enabled/configured ISRs), priority is set, Mcl creates and references the correct FlexIO logic channel, the MCU reference clock is correct, S32DS validation passes, and code generation succeeds. |
| RTD-MEX-UART-003 | UART | Configure Uart channel DMA mode | 修改已有的Uart通道，使能DMA模式，使能中断，回调函数Autombd_UartCallback | `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344` | One edit attempt is sufficient for functional validation; excluding validation runtime, intent analysis, planning, implementation, and file editing finish within 3 min. | Platform enables and registers the correct ISR (in DMA mode, the interrupt is produced by DMA), priority is set, Mcl configures the correct DMA channel and instance, the MCU reference clock is correct, S32DS validation passes, and code generation succeeds. |

## 3. Case status and dependencies

The catalog defines the **acceptance target**; current pass/fail evidence is
recorded in [`rtd-config-acceptance-report.md`](rtd-config-acceptance-report.md),
where every case passes the vendor gate with its generated code verified. The
capability dependencies that once gated these cases are now resolved:

- `RTD-MEX-UART-003` is delivered — the Uart/Mcl **DMA capability** is
  implemented (`uart set --mode dma`; the static checks enforce DMA coherence via
  `dma_mcl_not_enabled` / `dma_refs_incomplete`).
- `RTD-MEX-PORT-001` (and every pin-applying case) uses the complete `pins.json`
  asset rebuilt from the pin-mux source workbook (domain-truth §1); `pin-options`
  output is verified.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-14 | 0.3.2 | Added RTD-MEX-DIO-002 (add a Dio channel on a pin whose DioPort container does not yet exist, e.g. PTA30 → DioPort_1) to codify the DioPort auto-creation capability at the E2E altitude — DIO-001 only ever used a pin in the pre-existing DioPort_0, so the container-creation path lacked E2E coverage (LL-019). Made the section-3 wording count-agnostic. |
| 2026-06-13 | 0.3.1 | Recorded the section-3 case-status update that the previous commit applied without a changelog row: the capability dependencies that once gated the cases are now marked resolved (DMA delivered — `uart set --mode dma`, coherence via `dma_mcl_not_enabled`/`dma_refs_incomplete`; `pins.json` rebuilt), matching the 9/9 acceptance report. |
| 2026-06-13 | 0.3.0 | Added mandatory KPI evidence handling to the isolated execution protocol: functional PASS with KPI miss returns to Worker optimization for at most three iterations, then records the true KPI result. Added the `KPI` column contract and converted all non-`Subagent Prompt` case text to English. |
| 2026-06-10 | 0.2.0 | Fourth-round review resolution: restructured to E2E-only cases in the format ID/Module/Scenario/Subagent Prompt/Test fixture/Pass criteria (scheme `RTD-MEX-*`); seeded with the reviewer's MCU clock and three UART cases (incl. DMA) and extended to all seven minimal-system modules; added the fully-isolated subagent execution protocol; renamed the document from `rtd-config-m1-test-cases.md` (m1 dropped from all doc names). |
| 2026-06-11 | 0.2.1 | Corrected the PASS evidence step to the verified Flow B `-ExportSrc` code generation (was `-UpdateCode`, which belonged to the superseded registration flow); aligned the SEVERE marker wording with domain-truth §3. Added the companion [`rtd-config-acceptance-report.md`](rtd-config-acceptance-report.md) as the living pass/fail record. |
| 2026-06-06 | 0.1.0 | Extracted the M1 mandatory matrix, scope guards, and out-of-scope list from `rtd-config-test-strategy.md` v0.5.0 into this standalone, per-milestone test-cases document. |
