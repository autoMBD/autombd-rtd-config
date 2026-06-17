---
name: autombd-rtd
version: 0.1.1
description: >-
  Configure NXP S32K3 RTD 7.0.1 .mex automotive projects through the bundled RTD
  CfgFile CLI. Use when a user asks to inspect a project, query pin options, or
  plan/configure any of the seven minimal-system modules — Mcu (clock tree),
  BaseNXP (OsIf system timer), Platform (interrupts/ISR), Port (pin mux), Dio
  (channels), Mcl (FlexIO/DMA logic channels), or Uart (LPUART or FlexIO
  channels, interrupt or DMA mode) — run static checks, or run S32DS headless
  validation on an S32 ConfigTools .mex project.
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
- **`rtd-config basenxp set --enable-system-timer`** — enable the OsIf system
  timer and insert one `OsIfCounterConfig` (the time base for driver timeouts).
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

### Vendor validation
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
- `*_config_set_not_found` / `*_not_found` (e.g. `uart_channel_not_found`,
  `platform_isr_not_found`, `mcu_config_set_not_found`) — the targeted existing
  instance was not found; the tool edits existing instances, it does not create
  them.
- `s32ds_root_not_configured` — `validate` found no S32DS install; pass
  `--s32ds-root` or set `RTD_CONFIG_S32DS_ROOT`.
