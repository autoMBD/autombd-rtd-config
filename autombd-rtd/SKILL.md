---
name: autombd-rtd
version: 0.1.8
description: >-
  Configure NXP S32K3 RTD 7.0.1 .mex automotive projects through the bundled RTD
  CfgFile CLI. Use when a user asks to inspect a project, query pin options,
  plan/configure supported RTD modules, run static checks, or run S32DS
  headless validation on an S32 ConfigTools .mex project.
license: MIT
---

# RTD CfgFile CLI Companion Skill

The official tool is the **RTD CfgFile CLI**. It edits **existing** NXP S32
ConfigTools `.mex` projects for S32K3 RTD 7.0.1. Always drive it through the
public CLI; never edit `.mex` XML by hand, and never read Excel workbooks, raw
RTD `.xdm` descriptors, or local RTD installation scans to answer a request —
the committed assets bundled with the skill already carry every value the tool
needs.

## Fast path for one-module configuration

For a single-module configuration request, do not explore. The requested module
is the command module. Read only that module's reference if payload fields are
needed, write one spec JSON file near the project/workdir, then run:

```text
rtd-config <module> set --project <dir> --spec <module-config.json> --configure --json
rtd-config check --project <dir> --json
rtd-config validate --project <dir> --json
```

Do not spawn exploration tasks/subagents, run `inspect`, run `<module> set
--help`, list directories, query bundled assets, read `rtd-config-cli-py` source
files, or run another module's `set` command unless the selected module
reference explicitly requires that extra command.

For a single-module request, the only allowed shell commands are the three
command forms above: `<module> set --spec --configure --json`, `check`, and
`validate`, unless a module reference explicitly names a compatibility helper
for that case. `inspect` is not validation; running it is a workflow failure.
When the prompt asks for `BLACKBOX_RESULT`, emit that line immediately after
`validate` using the configure/check/validate outputs.

## Module routing

Choose the module by the configuration surface being requested, not by a
peripheral token inside the request.

- Interrupt priority, enablement, or ISR registration is `platform`. An LPUART token in an interrupt-only request does not make it `uart`; read
  `reference/platform-spec.md` and do not run `uart set`.
- FlexIO common resources or FlexIO logic channels are `mcl`; read
  `reference/mcl-spec.md` and do not run `uart set`.
- Uart channel communication settings, hardware instance changes, callbacks,
  frame format, or DMA/interrupt mode are `uart`.
- Pin routing is `port`; GPIO channel creation is `dio`; clock-tree edits are
  `mcu`; OsIf/BaseNXP infrastructure is `basenxp`; ADC hardware units, groups,
  channels, watchdog, DMA streaming, or BCTU triggers are `adc`.

## Running the bundled CLI

This skill bundles its own implementation; no network access and no install are
required (Python 3.11+, standard library only). A **zero-config launcher** sits
at the skill root, so the simplest invocation works from any directory:

- **Recommended:** `python <skill-dir> <command>` — e.g.
  `python autombd-rtd inspect --project <dir> --json`. No environment setup.
- Equivalent immutable invocation: put `<skill-dir>/rtd-config-cli-py` on
  `PYTHONPATH` (or `cd` into it), then `python -B -m rtd_config <command>`.
  Keep `-B`; it prevents Python from adding bytecode files to the verified
  released payload. The root launcher sets the same protection automatically.

The launcher resolves the committed assets (pin maps, per-module caches) from
the `assets/` directory beside `rtd-config-cli-py/`, so it works from any
working directory and install location. The command reference below is written
as `rtd-config <command>`; run each as `python <skill-dir> <command>`.

`--project` always takes the **project directory** (the folder that contains the
single `.mex`), never the `.mex` file path. Add `--json` to any command for
machine-readable output.

## Reference loading

Keep this file as the general operating contract. Read a module reference only
when the user asks for that module or when you need that module's payload
fields, token domains, side effects, or diagnostics.

| Module | Reference |
| --- | --- |
| `mcu` | `reference/mcu-spec.md` |
| `basenxp` | `reference/basenxp-spec.md` |
| `platform` | `reference/platform-spec.md` |
| `port` | `reference/port-spec.md` |
| `dio` | `reference/dio-spec.md` |
| `mcl` | `reference/mcl-spec.md` |
| `uart` | `reference/uart-spec.md` |
| `adc` | `reference/adc-spec.md` |

Do not read every reference up front. Select the smallest set needed for the
requested module configuration.

## The plan -> configure -> validate workflow

Every module configuration command is **`<module> set`**. Use structured spec
input as the canonical API:

```text
rtd-config <module> set --project <dir> --spec <module-config.json> --configure --json
```

The JSON file may use the common envelope below. The CLI validates the optional
`module` and `action` fields, then passes `payload` to the same intent/provider
pipeline used by legacy flags.

```json
{"module": "<module>", "action": "set", "payload": {}}
```

For compatibility, a raw payload object is still accepted. Existing
module-specific flags remain available as shortcuts, but canonical agent use is
`--spec`.

Write the spec file inside the project directory or your current workdir, next
to the copied fixture or agent run files. Do not write module spec files to system temp directories.

For a single requested module:

1. Use the module named by the user request or E2E case as the command module.
   Read only that module's reference file when payload fields or token domains
   are needed.
2. Write one JSON spec file near the project/workdir.
3. Run exactly one mutating `set --spec ... --configure --json` command, or the
   selected reference's explicitly named compatibility helper.
4. Run `check --project <dir> --json`.
5. Run `validate --project <dir> --json`.

Do not run another module's `set` command to prepare or probe dependencies
unless the user explicitly requested that other module; providers handle their
declared dependencies. Do not run `<module> set --help` to discover payload
fields; the selected reference file is the authoritative payload guide.
Do not run `inspect`, list the skill tree, read bundled assets, or read
`rtd-config-cli-py` source files to discover payload fields for a single-module
request. Only run extra discovery commands when the selected reference
explicitly requires them, such as `pin-options` for pin routing.

For multiple modules, repeat the one mutating `set --spec ... --configure
--json` command per requested module, then run one final `check` and one final
`validate`. Add `--backup` to the first mutating command when a `.mex.bak` copy
is required.

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

### Module configuration
- `rtd-config <module> set --project <dir> --spec <module-config.json>
  --configure --json` — configure one supported module through the common spec
  contract. Read the selected module reference before authoring the payload.
- `rtd-config uart add-flexio-channel` — reference-declared compatibility helper
  retained for RTD-MEX-UART-002; read `reference/uart-spec.md` before using it.
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

Each provider edits only its own module region. Cross-module needs are explicit
declared dependencies, never silent edits. Module-specific ownership and
dependency details live in the selected module reference.

## Scope

The tool configures **existing** module instances and writes configuration
values, including the callback **name**. Implementing the C callback function
(e.g. `Autombd_UartCallback`) and building the project are the user's
responsibility — the tool does not generate or edit `.c`/`.h` sources. Creating
a `.mex` from scratch, adding an absent top-level module, EB tresos, and
non-S32K3 devices are out of scope.

## JSON intent contract

Shortcut commands, structured specs, and JSON intents converge on one abstract
shape:

```json
{"module": "<module>", "action": "set", "payload": {}}
```

## Diagnostics

Results are JSON with a `status` (`passed` / `blocked`) and a `diagnostics`
list. Read diagnostics instead of guessing. Module-specific diagnostic meaning
lives in the selected reference. `s32ds_root_not_configured` means `validate`
found no S32DS install; pass `--s32ds-root` or set `RTD_CONFIG_S32DS_ROOT`.
