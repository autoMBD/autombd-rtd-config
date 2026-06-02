---
name: rtd-config
description: >-
  Configure NXP S32K3 RTD 7.0.1 .mex automotive projects through the RTD
  CfgFile CLI. Use when a user asks to inspect, plan, or configure Uart
  (LPUART or FlexIO) channels, query pin options, run static checks, or run
  S32DS headless validation on an S32 ConfigTools .mex project. Milestone 1
  scope only.
---

# RTD CfgFile CLI Companion Skill

The official tool is the **RTD CfgFile CLI**. It edits existing NXP S32
ConfigTools `.mex` projects for S32K3 RTD 7.0.1. Always drive it through the
public CLI; never edit `.mex` XML by hand and never read Excel workbooks, raw
RTD `.xdm` descriptors, or local RTD installation scans to answer a request.

## Operating Rules

- Use only the public CLI commands below. Convert every user request into a JSON
  intent or an equivalent shortcut command, then run the same
  plan / configure / check / validate pipeline.
- `inspect`, `pin-options`, `plan` (the default `uart set` output), and `check`
  never launch a vendor tool. Only `validate` may launch S32DS, and only
  headlessly when its environment is configured.
- Configure edits **existing** module instances only. Creating missing modules
  or a `.mex` from scratch is **not in Milestone 1**.
- Always run `check` (static checks) after a configure. Treat S32DS `validate`
  as confirmation, never as a substitute for the static check.
- By default run only the mandatory minimum tests. Run advanced tests only when
  the user explicitly asks for them.

## Public Commands

- `rtd-config inspect --project <path> --json` — report backend, family,
  device, RTD version, and the enabled module list.
- `rtd-config pin-options --device s32k344 --package default --peripheral
  LPUART_0 --json` — list prepared TX/RX pin options before assigning Uart
  pins. Query this before choosing `--tx` / `--rx`.
- `rtd-config uart set --project <path> --hw <LPUART_0|FLEXIO_0> --mode
  <polling|interrupt> --baud <rate> --tx <pin> --rx <pin> --json` — normalize a
  Uart request into an intent and emit the plan (Mcu/Port/Platform/Mcl
  dependencies). Plan-only; writes nothing.
- Add `--configure` to apply the plan: it makes a real localized Uart edit,
  strips stale `quick_selection`, writes the `.mex`, and runs static-check
  runtime verification. Add `--backup` to keep a `<file>.mex.bak` first.
- `rtd-config check --project <path> --json` — run the static checks
  (well-formedness, single `.mex`, enabled modules, duplicate names,
  quick_selection conflicts, stale FlexIO refs, missing Mcl FlexIO channels,
  duplicate LPUART hardware, invalid callback, DMA rejection).
- `rtd-config validate --project <path> --json` — run S32DS / S32 ConfigTools
  headless validation when `--s32ds-root` or `RTD_CONFIG_S32DS_ROOT` is set.
  The pass condition is ConfigTools exit code `0`.

## JSON Intent Contract

Shortcut commands and JSON intents converge on one shape:

```json
{
  "module": "uart",
  "action": "set",
  "payload": {"hw": "LPUART_0", "mode": "interrupt", "baud": 115200,
              "pins": {"tx": "PTA15", "rx": "PTA16"}}
}
```

## Module Ownership

Each provider edits only its own module region. Uart owns channel settings and
Uart-side references and declares dependencies owned elsewhere:

- **Mcu** owns the peripheral clock reference (always required).
- **Port** owns TX/RX pin mux/electrical configuration (consumer requests pins).
- **Platform** owns the interrupt entry (interrupt mode only).
- **Mcl** owns the FlexIO common resources and logic channels (FlexIO path).

## Milestone 1 Scope and DMA

Milestone 1 supports LPUART and FlexIO-backed Uart in polling and interrupt
modes on the S32K344 Uart fixture.

- **DMA is not in Milestone 1.** Reject or defer any DMA request; never
  partially configure DMA. If a project already has `UartDmaEnable=true` or
  `MclEnableDma=true`, `check` returns a `dma_not_supported_in_m1` blocker.
- FlexIO Uart word length is constrained to 8 bits in RTD 7.0.1.
- A Uart callback must be a valid C identifier; `NULL_PTR` is rejected as a
  callback name (`invalid_uart_callback`).
- `.mex` creation, missing-module completion, EB tresos, K1/K5 validation, and
  runtime Excel/RTD-scan parsing are out of scope for Milestone 1.

## Diagnostics Interpretation

Results are JSON with a `status` (`passed` / `failed` / `blocked`) and a
`diagnostics` list. Read diagnostics instead of guessing. Key codes:

- `quick_selection_conflict` — a modified element still carries
  `quick_selection`. ConfigTools may revert it. **Highest-risk case:** a Uart
  out-of-range error after adding FlexIO-backed Uart usually traces to a stale
  `quick_selection` on `<config_set name="Mcl">`, not to the Uart channel
  fields. Check Mcl `quick_selection` first.
- `stale_flexio_uart_hw_channel_ref` — a FlexIO Uart `UartHwChannelRef` does not
  point to an existing Mcl FlexIO logic channel.
- `missing_mcl_flexio_logic_channel` — FlexIO-backed Uart needs a coherent Mcl
  FlexIO common + logic channel; plan Mcl and Uart together.
- `duplicate_lpuart_hw_channel` — two active LPUART channels share one hardware
  instance.
- `dma_not_supported_in_m1` — DMA was requested or present; reject/defer it.
- `uart_channel_not_found` / `uart_config_set_not_found` — the requested
  existing instance was not found; M1 does not create it.
