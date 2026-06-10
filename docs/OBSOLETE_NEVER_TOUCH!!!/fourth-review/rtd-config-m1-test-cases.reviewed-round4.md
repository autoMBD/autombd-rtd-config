> **OBSOLETE - review archive only (round 4).** This is the reviewed draft of
> `docs/tests/rtd-config-m1-test-cases.md` with the user's inline REVIEW comments preserved for traceability.
> It is NOT a requirements source and must not be read to infer current
> behavior, scope, terminology, or acceptance criteria. Use only active
> documents outside `docs/OBSOLETE_NEVER_TOUCH!!!/`. Comment resolutions are
> tracked in `docs/common/rtd-config-core-comments-tracking.md`.

# RTD CfgFile CLI — Milestone 1 Test Cases

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-06-06 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | The concrete Milestone 1 test cases (seven-module parity matrix) for the RTD CfgFile CLI. Kept separate from `rtd-config-test-strategy.md` and staged per milestone so cases can grow and iterate without churning the strategy. |

<!-- REVIEW: 这测试文件要重构，测试有单元测试和E2E测试两种，我现在只关心E2E测试，test case只保留E2E测试用例即可，测试用例按照下面的格式写：


| ID | Module | Scenario | Subagent Prompt | test fixture | Pass criteria |
| --- | --- | --- | --- | --- | --- |
| RTD-MEX-MCU-001 | | MCU | Modify MCU Clock configration | 修改MCU的时钟配置，外部晶振16MHz，CORE_CLK=160MHz, AIPS_PLAT_CLK=80MHz，AIPS_SLOW_CLK=40MHz，修改后其他时钟源不报错。在Clock Reference Point中添加所有可选的时钟并将名称修改为对应的时钟 | tests\fixtures\nxp\ds\s32k3\Uart_Example_S32K344 | 时钟配置正确，S32DS验证通过，能正确生成代码 |
| RTD-MEX-UART-001 | UART | Modify Uart Channel Configuration | 修改UART通讯参数为8bit、921600波特率、无校验位、停止位1bit，改外设实例为LPUART_8，使能中断模式，回调函数Autombd_UartCallback。 | tests\fixtures\nxp\ds\s32k3\Uart_Example_S32K344 |  Platform 使能并注册了正确的ISR，MCU参考时钟正确，设置了优先级，S32DS验证通过，能正确生成代码 |
| RTD-MEX-UART-002 | UART | Add new Uart Channel Configuration | 新增一个基于FlexIO的UART通道，包含Tx和Rx，通讯参数为8bit、921600波特率、无校验位、停止位1bit，使能中断模式，回调函数Autombd_UartCallback | tests\fixtures\nxp\ds\s32k3\Uart_Example_S32K344 | Platform 使能并注册了正确的ISR（中断模式对全局起作用，所以LPUART和FlexIO都要使能和配置ISR），设置了优先级，MCL创建了正确的FlexIO逻辑通道并且引用正确，MCU参考时钟正确，S32DS验证通过，能正确生成代码 |
| RTD-MEX-UART-003 | UART | Config Uart Channel DMA mode | 修改已有的Uart通道，使能DMA模式，使能中断，回调函数Autombd_UartCallback | tests\fixtures\nxp\ds\s32k3\Uart_Example_S32K344 | Platform 使能并注册了正确的ISR（DMA模式下，中断由DMA产生），设置了优先级，MCL配置了正确的DMA通道和instance，MCU参考时钟正确，S32DS验证通过，能正确生成代码 |

这里给了三个例子，你可以再补充更多的测试用例，给这七个模块。
你需要同步更新rtd-config-test-strategy.md
这些测试用例，必须在subagent完全独立的情况下测试， 不能看到本项目的任何内容，只能使用autombd-rtd cli工具、autombd-rtd skill、测试prompt和测工程，可以创建一个临时目录专门做这个测试。

 -->

> **Governed by [`rtd-config-test-strategy.md`](rtd-config-test-strategy.md).**
> The test layers, the S32DS pass gate (exit `0` AND no SEVERE `[TOOL]`), the
> acceptance rule, and the subagent loop are defined there and are not restated
> here. Per-module facts a case asserts against (valid values, constraints,
> dependencies) come from each `<Module>.xdm` via its provider; cross-cutting
> fixture and S32DS-command facts live in
> [`../specs/rtd-config-domain-truth.md`](../specs/rtd-config-domain-truth.md).

## 1. Mandatory matrix (seven-module parity)

Input fixture (unless a case overrides):
`tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/`, which enables all seven M1
modules. Every CONFIGURE/VALIDATE case asserts, at minimum: JSON
`status=passed`, the owned module in `changed_modules`, static check passed, and
the **S32DS gate** (exit 0 + no SEVERE `[TOOL]`) for the affected module(s) via
the Peripherals tool (chaining Pins/Clocks when the edit touches them).

| ID | Module(s) | Scenario | Surface | Key evidence beyond the common gate | Owner |
| --- | --- | --- | --- | --- | --- |
| RTD-M1-INSPECT-001 | all | Inspect the fixture: backend, device, package, RTD version, enabled modules, validation profile | `inspect` | read-only; no writes, no vendor launch; reports all seven enabled modules incl. Dio | Tester |
| RTD-M1-PINOPT-001 | Port | Query pins/mux for a peripheral signal before assignment | `pin-options` | reads committed pin data only (no Excel/vendor); options match real package data (domain-truth §1) | Explorer, Tester |
| RTD-M1-MCU-001 | Mcu | Configure the peripheral clock reference an enabled Uart needs | `mcu` / intent | Mcu-owned clock edit; Clocks+Peripherals validation clean | Worker, Tester |
| RTD-M1-BASENXP-001 | BaseNXP | Configure/confirm OsIf support required by the Uart timeout path | `basenxp` / intent | BaseNXP-owned edit; no cross-module violation | Worker, Tester |
| RTD-M1-PLATFORM-001 | Platform | Configure an interrupt entry (IsrName/priority/handler/enable) for an IRQ-mode Uart | `platform` / intent | Platform-owned IRQ entry; valid handler (C identifier or NULL_PTR); no DMA | Worker, Tester |
| RTD-M1-PORT-001 | Port | Configure TX/RX pin mux for a Uart signal | `port set-pin` / intent | Port-owned SIUL2 edit using real pin data; Pins+Peripherals validation clean | Worker, Tester |
| RTD-M1-DIO-001 | Dio | Configure a Dio channel (symbolic id, direction) | `dio set-channel` / intent | Dio-owned edit; unique channel/group ids; Port owns pad, Dio owns logical id | Worker, Tester |
| RTD-M1-MCL-001 | Mcl | Configure FlexIO common resources + a logic channel for FlexIO Uart | `mcl` / intent | Mcl-owned FlexIO common+channel; no stale quick_selection on `<config_set name="Mcl">` | Worker, Tester |
| RTD-M1-UART-001 | Uart (+Mcu/Port/Platform deps) | Configure an LPUART channel, interrupt mode, 115200, 8N1, with TX/RX | `uart set` / intent | LPUART_IP channel + INTERRUPTS method; ownership boundaries respected | Worker, Tester |
| RTD-M1-UART-002 | Uart (+Mcu/Port/Platform/Mcl deps) | Configure a FlexIO-backed Uart channel, interrupt mode, 115200, 8N1, with TX/RX | `uart set` / intent | FLEXIO_IP channel + INTERRUPTS method; coherent Mcl FlexIO ref | Worker, Tester |
| RTD-M1-E2E-001 | full LPUART stack | End-to-end minimal LPUART stack on a real fixture | intent | configure → check → S32DS gate all pass for the whole stack | Tester, Reviewer |
| RTD-M1-E2E-002 | full FlexIO stack | End-to-end minimal FlexIO Uart stack on a real fixture | intent | configure → check → S32DS gate all pass for the whole stack | Tester, Reviewer |

## 2. Scope guards asserted across the matrix

- DMA requests are rejected (`dma_not_supported_in_m1`); never partially
  configured.
- Unsupported Uart modes (including "polling") are rejected
  (`unsupported_uart_mode`) — never written as an invalid enum. RTD 7.0.1 models
  the Uart asynchronous method as interrupt or DMA only; there is no polling
  value (domain-truth §1).
- `.mex` writes are byte-faithful: a no-edit write reproduces the file
  byte-for-byte; an owned edit touches only changed lines.
- No module edits outside its ownership.

## 3. Out of Milestone 1

Advanced module-detail cases (e.g. full Mcu clock-tree tuning, advanced Dio
groups) and reserved-future capabilities (`.mex` creation, missing-module
completion, Uart DMA, EB tresos, K1/K5 profiles) are tracked in the
[roadmap](../roadmaps/rtd-config-roadmap.md), not here. They do not gate M1. The
previous polling cases (old `RTD-M1-MIN-002` / `-004`) are withdrawn: RTD 7.0.1
has no polling async-method value (domain-truth §1).

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-06 | 0.1.0 | Extracted the M1 mandatory matrix, scope guards, and out-of-scope list from `rtd-config-test-strategy.md` v0.5.0 into this standalone, per-milestone test-cases document. |
