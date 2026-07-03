---
name: autombd-rtd
version: 0.1.2
description: >-
  Configure NXP S32K3 RTD 7.0.1 .mex automotive projects through the bundled RTD
  CfgFile CLI. Use when a user asks to inspect a project, query pin options, or
  plan/configure any supported module — Mcu (clock tree), BaseNXP (OsIf system
  timer), Platform (interrupts/ISR), Port (pin mux), Dio (channels), Mcl
  (FlexIO/DMA logic channels), Uart (LPUART or FlexIO channels, interrupt or DMA
  mode), or Adc (Hardware Unit groups, channels, sampling-time derivation, and
  watchdog thresholds) — run static checks, or run S32DS headless validation on
  an S32 ConfigTools .mex project.
license: MIT
---

# RTD CfgFile CLI Companion Skill

The official tool is the **RTD CfgFile CLI**. It edits **existing** NXP S32
ConfigTools `.mex` projects for S32K3 RTD 7.0.1. Always drive it through the
public CLI; never edit `.mex` XML by hand, and never read Excel workbooks, raw
RTD `.xdm` descriptors, or local RTD installation scans to answer a request —
the committed assets bundled with the skill already carry every value the tool
needs.

## Running the bundled CLI

This skill bundles its own implementation; no network access and no install are
required (Python 3.11+, standard library only). A **zero-config launcher** sits
at the skill root, so the simplest invocation works from any directory:

- **Recommended:** `python <skill-dir> <command>` — e.g.
  `python autombd-rtd inspect --project <dir> --json`. No environment setup.
- Equivalent: put `<skill-dir>/rtd-config-cli-py` on `PYTHONPATH` (or `cd` into
  it), then `python -m rtd_config <command>`.

The launcher resolves the committed assets (pin maps, per-module caches) from
the `assets/` directory beside `rtd-config-cli-py/`, so it works from any
working directory and install location. The command reference below is written
as `rtd-config <command>`; run each as `python <skill-dir> <command>`.

`--project` always takes the **project directory** (the folder that contains the
single `.mex`), never the `.mex` file path. Add `--json` to any command for
machine-readable output.

## The plan → configure → validate workflow

Every module command is **`<module> set`**. `--configure` does three things in
one call: it normalizes the request, makes the narrow byte-faithful edit, and
immediately runs the static checks.

### Universal one-shot (default — for simple single-edit cases)

A **simple case** is a straightforward modification to one module: change a
value, set a priority, enable a feature. **Do not explore.** Follow this pattern:

1. Read the module's entry in the [command reference](#module-configuration-set-add---configure-to-write)
   below for the exact flag names.
2. Construct the command from the user's request and the flag reference:
   ```
   <module> set --project <dir> [flags from the user's request] --configure
   ```
3. Run `validate --project <dir> --json` to confirm with the vendor gate.

**Done.** That is the whole workflow — one `set --configure` call + one `validate`.

**Never** do any of these for a simple case (they waste time, `--configure`
already handles everything):
- ❌ `inspect` — `--configure` validates its own input.
- ❌ `<module> set --help` — the flag reference below is sufficient.
- ❌ `<module> set …` without `--configure` as a "dry-run preview" — wasted
  round-trip; add `--json` to `--configure` if you want machine-readable output.
- ❌ A second `validate` — one pass confirms the vendor gate.
- ❌ A separate `check` — `--configure` already runs it; re-running is harmless
  but redundant.

### Plan-first (for cross-module orchestration or when you want to review first)

When multiple modules are involved or you are unsure about the side effects, run
`<module> set …` *without* `--configure` — it writes nothing and prints the plan,
including the cross-module dependencies it will satisfy. Review, then add
**`--configure`** to apply. Compose several `--configure` calls in sequence on the
same project, then `validate` once at the end. Add **`--backup`** to first copy
the original to `<file>.mex.bak`.

## Public commands

### Inspection & checks (never launch a vendor tool)
- `rtd-config inspect --project <dir> --json` — report backend, family, device,
  package, RTD version, the resolved `.mex`, and the enabled module list.
- `rtd-config pin-options --device s32k344 --package default --peripheral
  LPUART_0 --json` — list verified TX/RX pin options for a peripheral. Query
  this **before** choosing `--tx`/`--rx` for `port set`.
- `rtd-config check --project <dir> --json` — run the static checks
  (well-formedness, single `.mex`, enabled modules, duplicate names,
  `quick_selection` conflicts, FlexIO reference coherence, DMA coherence,
  duplicate LPUART hardware, callback validity).

### Module configuration (`set`; add `--configure` to write)
- **`rtd-config mcu set`** — clock tree. `--core-clk <MHz> --aips-plat-clk <MHz>
  --aips-slow-clk <MHz>` set the PLL + MC_CGM dividers; `--add-all-clock-
  reference-points` preserves existing reference points and adds every
  selectable S32K344 clock by name. e.g.
  `mcu set --project <dir> --core-clk 160 --aips-plat-clk 80 --aips-slow-clk 40 --add-all-clock-reference-points --configure`
- **`rtd-config basenxp set`** — configure BaseNXP / OsIf shared
  infrastructure. `--enable-system-timer` enables the OsIf system timer and
  inserts one `OsIfCounterConfig` (the time base for driver timeouts). The
  command also supports BaseNXP-owned OsIfGeneral scalars:
  `--user-mode-support true|false`, `--dev-error-detect true|false`,
  `--custom-timer true|false`, `--get-user-id core|custom`,
  `--instance-id <0..255>`, `--get-physical-core-id true|false`, and
  `--software-semaphore true|false`.
- **`rtd-config platform set --peripheral <e.g. LPUART_3> --priority <n>`** —
  set an existing interrupt's priority, keep it enabled, and confirm its ISR is
  registered. Target by `--peripheral` or exact `--isr-name`.
- **`rtd-config port set --peripheral <e.g. LPUART_0> --tx <PIN> --rx <PIN>`** —
  route a peripheral's TX/RX pins (mux + electrical + direction). Pins are
  validated against the pin database (illegal pins are rejected) — query
  `pin-options` first.
- **`rtd-config dio set --add-channel <NAME> --pin <PIN>`** — add a DIO channel
  (e.g. `LED_CTRL`) on a free GPIO pad; the GPIO direction is configured on the
  Port side automatically (`--direction output`). The pin's `DioPort` container
  is created automatically if it does not yet exist.
- **`rtd-config mcl set --add-flexio-logic-channel <NAME>`** — append a FlexIO
  logic channel; the next free `CHANNEL_N`/`PIN_N` ids are computed and
  uniqueness is enforced.
- **`rtd-config uart set --hw <LPUART_n|FLEXIO_n>`** — configure an existing Uart
  channel and orchestrate its dependencies. Flags: `--mode interrupt|dma`,
  `--baud`, `--parity none|even|odd`, `--stop-bits 1|2`,
  `--word-length 7|8|9|10`, `--callback <CIdent>`, `--priority <n>`,
  `--tx`/`--rx` (pins), `--using LPUART_IP|FLEXIO_IP`, `--channel-id <n>`.
  Setting the channel pulls in the Mcu peripheral-clock reference, the Platform
  ISR (the interrupt ISR, or the DMA-completion ISR in DMA mode), and the Mcl
  channels.
- **`rtd-config uart add-flexio-channel`** — create a **new** FlexIO-backed Uart
  Tx+Rx channel pair plus their two Mcl FlexIO logic channels, with consistent
  references and a callback. `--baud` (default 921600), `--word-length 8`,
  `--callback`, `--tx-name`/`--rx-name`. The shared FlexIO ISR + clock reference
  are ensured idempotently.
- **`rtd-config adc set --spec <path.json>`** — configure an ADC Hardware Unit
  from a single JSON spec: the target unit, transfer mode, per-group sampling
  time (**derived** into `AdcSamplingDuration` from the ADC source clock +
  prescale — never written as a literal), one or more conversion groups, and
  per-channel watchdog thresholds. One `adc set --spec X --configure` expresses
  a full case. The spec object:
  ```json
  {
    "unit": "ADC1",
    "transfer": "interrupt",
    "sampling_time_us": 1,
    "groups": [
      {"name": "AdcGroup_0", "trigger": "sw", "access": "single",
       "conv": "oneshot", "num_samples": 1,
       "notification": "Autombd_AdcNotifi0", "channels": ["VREFL", "S10"]},
      {"trigger": "sw", "access": "streaming", "conv": "continuous",
       "num_samples": 10, "notification": "Autombd_AdcNotifi1",
       "channels": ["VREFH", "P5"]}
    ],
    "watchdog": [
      {"channel": "P5", "high": 3000, "low": 20,
       "notification": "Autombd_AdcNotifiWdg"}
    ]
  }
  ```
  Token domains: `transfer` ∈ `interrupt|dma`; `trigger` ∈ `sw|hw`; `access` ∈
  `single|streaming`; `conv` ∈ `oneshot|continuous`. **Channels** accept the
  short name (`VREFL`, `S10`, `P5`) or the full literal (`S10_ChanNum34`);
  S-channels start at **S8** (there is no S0–S7). The tool resolves channel
  name→id, derives the sampling duration, picks the smallest valid prescaler,
  adds the unit's `AdcHwConfiguration` (interrupt/watchdog coherence), and flips
  `AdcEnableWatchdogApi` when a watchdog is requested. It also enforces the
  vendor rule that a software-triggered **streaming** group must be
  `continuous` (a SW streaming one-shot group is coerced to continuous).
  Run, e.g.:
  `adc set --project <dir> --spec adc001.json --configure --json`

  **BCTU hardware trigger (optional `bctu` block).** Add a `bctu` object to the
  spec to wire a Body Cross-Triggering Unit trigger. The tool repoints
  `AdcHwTrigger_0` to the chosen trigger source, populates the `BctuHwUnit`
  subtree, and flips the gating APIs (`AdcHwTriggerApi`,
  `AdcEnableCtuControlModeApi`, and — for FIFO DMA — `CtuEnableDmaTransferMode`).
  Two modes:
  - **`single`** — one BCTU-triggered conversion of one channel into a data
    register or FIFO. Use the single-`unit` spec above plus:
    ```json
    "bctu": {
      "trigger_source": "BCTU_EMIOS_2_15",
      "mode": "single",
      "target": "ADC1",
      "channel": "S10",
      "destination": "data_reg",
      "new_data_notification": "Autombd_BctuNewDataNotifi"
    }
    ```
    (A full ADC-003 spec is the single-`unit` form above with this `bctu` block;
    the unit needs the BCTU `channel` in one of its groups so the trigger can
    reference it.)
  - **`list`** — a conversion *list* dispatched to one or more ADC units, with
    results in a FIFO and an optional DMA request. Use the **multi-unit** spec
    form (`units: [{unit, sampling_time_us}, …]` instead of a single `unit`) plus
    a `list` `bctu`. The tool creates each unit (each gets its list channels as
    `AdcChannel` structs via one SW group so the list can enumerate them) and
    wires one shared BCTU. Worked ADC-004 (dual-ADC LIST + FIFO DMA):
    ```json
    {
      "units": [
        {"unit": "ADC1", "sampling_time_us": 5},
        {"unit": "ADC2", "sampling_time_us": 6}
      ],
      "transfer": "interrupt",
      "bctu": {
        "trigger_source": "BCTU_EMIOS_1_20",
        "mode": "list",
        "targets": ["ADC1", "ADC2"],
        "list": ["VREFH", "VREFL", "S20", "S20", "P1", "P2", "P3", "P4"],
        "trigger_order": [2, 2, 4],
        "destination": "fifo1",
        "fifo_dma": true,
        "fifo_notification": "Autombd_BctuFifoNotifi"
      }
    }
    ```
  `bctu` token domains: `trigger_source` ∈ the device BCTU tokens
  `BCTU_EMIOS_{0,1,2}_{0..22}` (plus `EXT_TRIG` / `AUX_EXT_TRIG`); `mode` ∈
  `single|list`; `destination` ∈ `data_reg|fifo1|fifo2`. Single keys: `target`
  (one ADC), `channel` (one device channel), `new_data_notification`. List keys:
  `targets` (the ADC units the list drives, e.g. `["ADC1","ADC2"]`), `list` (the
  ordered device channels — repeats allowed, e.g. `S20, S20`), `trigger_order`
  (a partition of the list whose parts sum to the list length; the list halts
  for a re-trigger after each part except the last — `[2,2,4]` over 8 items
  triggers 2 then 2 then 4 channels), `fifo_dma` (`true` raises a FIFO DMA
  request and consumes an Mcl DMA logic channel — `changed_modules` then includes
  `mcl`), and `fifo_notification` (the FIFO watermark callback). When `fifo_dma`
  is on, the tool disables FIFO interrupt notifications (mutually exclusive with
  DMA) and sets the watermark so the final sample of the batch raises the
  request.
- `rtd-config validate --project <dir> --json` — run S32DS / S32 ConfigTools
  **headless** validation. The tool **auto-discovers** a standard S32DS install
  (e.g. `C:\NXP\S32DS.<version>`, or `s32dsc.exe` on `PATH`); override with
  `--s32ds-root <path>` or the `RTD_CONFIG_S32DS_ROOT` environment variable. It
  loads the `.mex`, exports generated code to a throwaway folder, and reports
  problems. **Pass = exit code `0` AND code generated AND no SEVERE
  `[TOOL] … has the following error` resource problem** (exit `0` alone is not
  sufficient). Validation always runs on a **throwaway copy**, so your `.mex` is
  never modified. If no install is found, the result is
  `s32ds_root_not_configured` — set the flag or env var.

## Module ownership

Each provider edits only its own module region; cross-module needs are explicit
declared dependencies, never silent edits:

- **Mcu** owns the clock tree and the peripheral clock reference points.
- **Port** owns TX/RX pin mux/electrical/direction (consumers request pins).
- **Platform** owns the interrupt entries and ISR registration.
- **Mcl** owns the FlexIO common resources, the FlexIO logic channels, and the
  DMA logic channels/instance.
- **BaseNXP** owns the OsIf system-timer counter.
- **Uart** owns channel settings and the Uart-side references, and declares the
  Mcu / Port / Platform / Mcl dependencies above.
- **Adc** owns the `AdcHwUnit` configuration tree (channels, groups,
  `AdcThresholdControl` entries), the unit's `AdcHwConfiguration` entry, and the
  Adc-global `AdcEnableWatchdogApi` switch — all inside `<config_set name="Adc">`.
  Interrupt mode is internal to the ADC peripheral (no Platform IRQ dependency
  for the interrupt-software-group case).

## Interrupt and DMA modes

RTD 7.0.1 models the Uart asynchronous method as **interrupt or DMA only** —
there is no "polling" value (blocking/polling is an application-level
driver-call pattern, not a `.mex` setting). Both modes are fully supported:

- **Interrupt** (`--mode interrupt`, the default): the Platform LPUART/FlexIO
  ISR is enabled and registered with the chosen priority.
- **DMA** (`--mode dma`): the tool sets the Uart DMA method, enables
  `UartDmaEnable`, points the Tx/Rx references at Mcl DMA logic channels,
  enables `MclEnableDma` with the DMA channels/instance, and registers the
  Platform DMATCD completion ISRs. Coherence is enforced by the static checks
  (`dma_mcl_not_enabled`, `dma_refs_incomplete`).

## Clock outputs are ConfigTools-derived

`mcu set` writes the authoritative clock **inputs** — the PLL configuration, the
MC_CGM dividers, and the clock reference points. The Clocks-view `clock_output`
numbers are a **derived display cache that ConfigTools owns and recomputes**;
the tool deliberately does not recompute them (re-deriving the full clock tree
outside ConfigTools would risk diverging from it). The cache refreshes when the
project is opened in S32DS or when `validate` generates code. A Clocks-view
figure that still shows an old value right after `mcu set` is expected — do not
hand-edit it, and do not patch the tool to write it.

## Scope

The tool configures **existing** module instances and writes configuration
values, including the callback **name**. Implementing the C callback function
(e.g. `Autombd_UartCallback`) and building the project are the user's
responsibility — the tool does not generate or edit `.c`/`.h` sources. Creating
a `.mex` from scratch, adding an absent top-level module, EB tresos, and
non-S32K3 devices are out of scope.

## JSON intent contract

Shortcut commands and JSON intents converge on one shape:

```json
{
  "module": "uart",
  "action": "set",
  "payload": {"hw": "LPUART_3", "mode": "dma", "baud": 921600,
              "callback": "Autombd_UartCallback"}
}
```

## Diagnostics

Results are JSON with a `status` (`passed` / `blocked`) and a `diagnostics`
list. Read diagnostics instead of guessing. Key codes:

- `quick_selection_conflict` — a modified element still carries a
  `quick_selection`; ConfigTools may revert it. **Highest-risk case:** a Uart
  out-of-range error after adding a FlexIO Uart usually traces to a stale
  `quick_selection` on `<config_set name="Mcl">`, not to the Uart fields —
  check Mcl first.
- `dma_mcl_not_enabled` / `dma_refs_incomplete` — a DMA Uart needs
  `MclEnableDma=true` and complete Tx/Rx DMA channel references.
- `missing_mcl_flexio_logic_channel` / `stale_flexio_uart_hw_channel_ref` — a
  FlexIO Uart's `UartHwChannelRef` must point at an existing Mcl FlexIO logic
  channel; plan Mcl and Uart together.
- `duplicate_lpuart_hw_channel` — two active LPUART channels share one instance.
- `port_illegal_pin` — the requested pin is not valid for that peripheral
  signal; query `pin-options`.
- `invalid_uart_callback` — the callback is not a valid C identifier
  (`NULL_PTR` is rejected).
- `adc_channel_not_in_device` — an ADC channel name is not in the device enum
  (remember S-channels start at S8; use a name from `adc.json`/`pin-options`).
- `adc_sampling_out_of_range` — the requested sampling time cannot be encoded as
  a valid `AdcSamplingDuration` (8–255) at any prescaler; lower the ADC source
  clock (Mcu) or change the sampling time.
- `adc_interrupt_not_enabled` — an interrupt-transfer unit lacks
  `AdcHwConfiguration/AdcNormalInterruptEnable=true`.
- `adc_watchdog_api_disabled` / `adc_unit_wdg_threshold_disabled` /
  `adc_threshold_ref_incomplete` / `adc_watchdog_notification_invalid` — a
  channel with watchdog thresholds needs `AdcEnableWatchdogApi=true`, the unit's
  `WdgThresholdEnable=true`, a valid `AdcThresholdRegister` ref to a matching
  `AdcThresholdControl` on the same unit, and a valid `AdcWdogNotification`.
- `adc_dma_mcl_not_enabled` / `adc_dma_refs_incomplete` — an `ADC_DMA` unit, or a
  BCTU result FIFO with `BctuFifoDmaEnable=true`, needs `MclEnableDma=true` and a
  non-empty DMA channel ref (`AdcDmaChannelId` / `BctuFifoDmaChannelId`).
- `adc_bctu_trigger_source_not_in_device` / `adc_bctu_channel_not_in_device` /
  `adc_bctu_list_channel_not_in_device` — a `bctu` `trigger_source`, single
  `channel`, or `list` channel is not a valid device token; use a
  `BCTU_EMIOS_{0,1,2}_{0..22}` source and device channel names.
- `adc_bctu_trigger_order_mismatch` — the `list` `trigger_order` parts do not sum
  to the `list` length.
- `*_config_set_not_found` / `*_not_found` (e.g. `uart_channel_not_found`,
  `platform_isr_not_found`, `mcu_config_set_not_found`) — the targeted existing
  instance was not found; the tool edits existing instances, it does not create
  them.
- `s32ds_root_not_configured` — `validate` found no S32DS install; pass
  `--s32ds-root` or set `RTD_CONFIG_S32DS_ROOT`.
