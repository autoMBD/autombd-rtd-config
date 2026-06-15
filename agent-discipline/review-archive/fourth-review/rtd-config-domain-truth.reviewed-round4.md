> **OBSOLETE - review archive only (round 4).** This is the reviewed draft of
> `docs/specs/rtd-config-domain-truth.md` with the user's inline REVIEW comments preserved for traceability.
> It is NOT a requirements source and must not be read to infer current
> behavior, scope, terminology, or acceptance criteria. Use only active
> documents outside `docs/OBSOLETE_NEVER_TOUCH!!!/`. Comment resolutions are
> tracked in `docs/common/rtd-config-core-comments-tracking.md`.

# RTD CfgFile CLI Domain Truth & Validation Reference

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-06-03 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Holds only CROSS-CUTTING truth (the S32DS headless validation flow + gate, and fixture facts) and the SOURCING RULE for per-module truth. Per-module valid values, constraints, and dependencies are NOT listed here — they come from each module's `.xdm` and live in that module's provider. |

## Why this document is deliberately thin

The RTD CfgFile CLI's worst defects (an invented Uart "polling" enum; a broken
S32DS command) came from *assuming* vendor facts instead of sourcing them. The
fix is not a giant catalog of every module's values — that would duplicate the
vendor descriptors and rot immediately. Instead:

- **Per-module truth lives in the module's provider, sourced from its `.xdm`**
  (§1).
- **Only genuinely cross-cutting facts live here:** the S32DS validation flow and
  pass gate (§3), and the shared fixture facts (§2).

## 1. Per-module truth — sourcing rule (authoritative: `<Module>.xdm`)

Each RTD driver module ships a ConfigTools descriptor that is the **authoritative
source** for that module's:

- **valid values** (enumeration domains, integer/float ranges, defaults);
- **constraints** (the `INVALID` / `EDITABLE` / `ENABLE` XPath rules that
  ConfigTools enforces);
- **dependencies** (reference vars to other modules' resources).

Path pattern (S32K3 RTD 7.0.1):

```text
C:\NXP\S32DS.3.6.7\S32DS\software\PlatformSDK_S32K3\RTD\<Module>_TS_T40D34M70I1R0\config\<Module>.xdm
```

These descriptors are large and complete — e.g. `Uart.xdm` is ~1657 lines with 14
enumerations, 18 numeric vars, 31 constraint rules, 7 reference vars, 41 defaults,
and cross-module references (Mcl/Mcu/Platform/Dma). Every module has its own
equivalent (`Mcu.xdm`, `Port.xdm`, `Dio.xdm`, `Mcl.xdm`, `Platform.xdm`,
`BaseNXP.xdm`/OsIf, …).

### Build step (CRITICAL): `<Module>.xdm` → committed per-module asset → provider

This development-time step is how each module's truth enters the tool. It is the
**first part of every module's parity work** (run once per module, refreshed when
the RTD release or device changes). It is not optional or implicit — no provider
may carry hand-written enum/constraint/dependency values.

1. **Input** — the module descriptor `<Module>.xdm` (development source; never
   read at runtime).
2. **Extract** (Explorer) — from the `.xdm`: enumeration domains; numeric ranges
   and defaults; constraint rules (the `INVALID` / `EDITABLE` / `ENABLE` XPath
   expressions); and cross-module reference dependencies (`v:ref` targets).
3. **Emit** (Worker) — a committed, versioned per-module asset under
   `autombd-rtd/data/<vendor>/<family>/<module>/` (e.g. `autombd-rtd/data/nxp/s32k3/uart/`)
   holding `{valid_values, defaults, constraints, dependencies}`, each item
   traceable to its `.xdm` (record the source path + RTD version). The provider
   loads this asset (or embeds the constants from it). **The truth lives with the
   provider — not in this document.**
4. **Runtime boundary** — runtime commands read only the committed asset; the
   `.xdm` is never opened at runtime.
5. **Verify** — the Tester proves provider edits built from these values pass the
   S32DS gate (§3); the Reviewer cross-checks the asset against the `.xdm`.

**Do not transcribe per-module values into this document.** When a provider needs
a value/constraint/dependency it comes from that module's asset, traceable to its
`.xdm`.

*Illustrative example (not a registry entry):* `Uart.xdm` defines the Uart
asynchronous method (`UartInteruptDmaMethod` / `FlexioUartInteruptDmaMethod`) as
INTERRUPTS or DMA only — there is **no polling value**, and a DMA selection makes
`UartDmaTxChannelRef`/`UartDmaRxChannelRef` required (an `INVALID` rule). This is
the kind of fact that belongs in the Uart provider (from `Uart.xdm`), not here.

### Pin mapping (Port-owned, family-scoped asset)
Pin-mux truth (SIUL2) is owned by the Port module and committed as a single
family-scoped asset, `autombd-rtd/data/nxp/<family>/port/pins.json`, built
from the pin-mux source (Excel / ConfigTools Pins data). It must cover every
peripheral signal and carry the package as an in-record field, so one file serves
all of a family's packages (`lqfp100`, `hdqfp172`, `mapbga257`, …). The current
`pins.json` is a stub and must be rebuilt complete; until then `pin-options`
output is unverified and Port pin application is gated.

<!-- REVIEW: 把Excel位置写清楚："D:\WorkSpace\ExploreSpace\Copy of S32K344_S32K324_S32K314_IOMUX.xlsx" -->

## 2. Fixture facts — `Uart_Example_S32K344`

Path: `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/`. Full S32DS
project (`.project` name `Uart_Example_S32K344` + `.cproject`). Default XML
namespace `http://mcuxpresso.nxp.com/XSD/mex_configuration_18`; CRLF endings;
non-canonical XML declaration `<?xml version="1.0" encoding= "UTF-8" ?>` — preserve
byte-for-byte. Confirm the enabled module set with `inspect` against the *current*
fixture (it is being extended to all seven M1 modules incl. Dio); do not hardcode
it. Recompute the nearest `quick_selection` carrier at edit time.

<!-- REVIEW: 这里Uart_Example_S32K344只是fixture的一个例子，随着支持的module越来越多，fixture会更新更多（不要写进spec，让你理解的）。这里要说明的是fixture的使用方法和作用，这个uart例子可以保留。 -->

## 3. S32 ConfigTools headless validation (cross-cutting; verified)

Source: the `com.nxp.swtools.doc.uct` plugin jar
(`C:\NXP\S32DS.3.6.7\eclipse\plugins\com.nxp.swtools.doc.uct_1.9.1.*.jar` →
*Getting Started > Command-line execution*), confirmed by live runs on S32DS
3.6.7. This one flow validates every module's `.mex` edits.

- **Launcher:** `…\eclipse\s32dsc.exe` with `--launcher.ini …\eclipse\s32ds.ini`
  (console build blocks until done; not `s32ds.bat`).
- **Application:** `com.nxp.swtools.framework.application` with `-nosplash`
  `-consoleLog`. The `…HeadlessApplication` id is **not** registered.
- **`-HeadlessTool <Tool>` is required** and separates chains. RTD module configs
  are **Peripherals**-tool components; SIUL2 pins are the **Pins** tool; the clock
  tree is the **Clocks** tool. Chain the tools a change touches. Without a
  `-HeadlessTool` the framework app opens a workbench and never exits.
- **`-sdkPath`** = `<root>\S32DS\software\PlatformSDK_S32K3` (ships
  `sdk_manifest.xml`), not a standalone RTD package.
- **`-data <workspace>`** required (use `D:\WorkSpace\DSpace\3.6`).
- **Exit codes (official):** `1` = missing parameter, `2` = tool error, `0` =
  completed.
- **Pass gate (stricter than exit code):** exit `0` **AND** no
  SEVERE `[TOOL] … has the following error` resource problem. Exit `0` alone is
  insufficient. `SEVERE … target: Toolchain/IDE project` (driver-not-found) and
  SLF4J/NLS noise are project-build artifacts, not `.mex` validity.

### Flows
- **(A) Project mode (current tool flow, full):** project must be a workspace
  member, else `Cannot get container for IPath`. Register first
  (`-application org.eclipse.cdt.managedbuilder.core.headlessbuild -import <project>`),
  then `-HeadlessTool Peripherals -importProject <project> -sdkPath <sdk>
  -ShowProblems SEVERE`. The CLI stages an out-of-workspace project in and cleans
  up.
- **(B) Standalone `.mex` mode (candidate to simplify; documented, not yet
  verified here):** `-HeadlessTool Peripherals -Load <mex> -sdkPath <sdk>
  -ExportSrc <tmp> -ShowProblems SEVERE` — exports generated code to a folder, so
  it should not need workspace registration. The Tester must confirm it returns
  clean on a known-good `.mex` and exit 2 / SEVERE on a known-bad one before it
  replaces flow (A).
- Evidence flags: `-ExportHTML` (report), `-ExportMEX` (tool-normalized `.mex` to
  diff against the input).

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-03 | 0.1.0 | Initial anchor (attempted to register per-module enum facts). |
| 2026-06-03 | 0.2.0 | Reframed: per-module values/constraints/dependencies are sourced from each `<Module>.xdm` and owned by the provider (not catalogued here); this doc keeps only the cross-cutting S32DS validation flow/gate, fixture facts, and the sourcing rule. |
