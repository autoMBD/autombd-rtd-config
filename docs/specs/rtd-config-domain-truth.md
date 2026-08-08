# RTD CfgFile CLI Domain Truth & Validation Reference

| Field | Value |
| --- | --- |
| Version | 0.5.0 |
| Date | 2026-06-15 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Holds only CROSS-CUTTING truth (the S32DS headless validation flow + gate, and fixture role/usage) and the SOURCING RULE for per-module truth. Per-module valid values, constraints, and dependencies are NOT listed here — they come from each module's `.xdm` and live in that module's provider. |

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
2. **Extract** — from the `.xdm`: enumeration domains; numeric ranges
   and defaults; constraint rules (the `INVALID` / `EDITABLE` / `ENABLE` XPath
   expressions); and cross-module reference dependencies (`v:ref` targets).
3. **Emit** — a committed, versioned per-module asset under
   `autombd-rtd/assets/<vendor>/<family>/<module>/` (e.g. `autombd-rtd/assets/nxp/s32k3/uart/`)
   holding `{valid_values, defaults, constraints, dependencies}`, each item
   traceable to its `.xdm` (record the source path + RTD version). The provider
   loads this asset at runtime, or — if it embeds the constants — pins them with a
   code==asset test that fails on drift (a documentation-only asset with no loader
   and no pin is prohibited; see lessons-learned LL-012). **The truth lives with the
   provider — not in this document.**
4. **Runtime boundary** — runtime commands read only the committed asset; the
   `.xdm` is never opened at runtime.
5. **Verify** — provider edits built from these values are proven to pass the
   S32DS gate (§3), and the asset is cross-checked against the `.xdm`.

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
family-scoped asset, `autombd-rtd/assets/nxp/<family>/port/pins.json`, built
from the pin-mux source workbook
`D:\WorkSpace\ExploreSpace\Copy of S32K344_S32K324_S32K314_IOMUX.xlsx`
(development input only — also catalogued in the source-materials reference;
never read at runtime). It must cover every peripheral signal and carry the
package as an in-record field, so one file serves all of a family's packages
(`lqfp100`, `hdqfp172`, `mapbga257`, …). The `pins.json` asset is built from that
workbook by the committed development tool `tools/build_pins_s32k3.py` (2091
S32K344 signals; byte-verified), and `pin-options` is verified against it.
Writing a queried pin into a `.mex` (Port apply) is the remaining Port capability.

## 2. Fixtures — role and usage

Fixtures are **real vendor projects** under
`tests/fixtures/<vendor>/<backend: ds|eb>/<family>/<project>/`. Their role: give
every test layer a genuine, vendor-validatable input — deterministic tests and
E2E cases edit a **copy** (fixtures are staged into a temporary workspace and
never edited in place), and the vendor gate then judges the edited copy. A
fixture must contain everything vendor validation needs (project files + config
file) and exclude build/generated artifacts. The fixture set grows as module
support grows; confirm what a fixture actually enables with `inspect` against
its *current* content — never hardcode an enabled-module list in code, tests, or
docs.

Worked example — `Uart_Example_S32K344`
(`tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/`): full S32DS project
(`.project` name `Uart_Example_S32K344` + `.cproject`). Default XML namespace
`http://mcuxpresso.nxp.com/XSD/mex_configuration_18`; LF (Unix) endings (CRLF
count 0, LF 2467 — byte-verified); the byte-faithful writer auto-detects the
file's line ending so insertions derive it from the file and never hardcode a
line-ending style; non-canonical XML declaration
`<?xml version="1.0" encoding= "UTF-8" ?>` — preserve byte-for-byte.
Recompute the nearest `quick_selection` carrier at edit time.

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
- **(B) Standalone `.mex` mode — VERIFIED, the adopted tool flow:**
  `-HeadlessTool Peripherals -Load <mex> -sdkPath <sdk> -ExportSrc <tmp>
  -ShowProblems SEVERE` (with a throwaway `-data <tmp-ws>`; **no** `-ProjectLink`,
  **no** `-UpdateCode`, **no** registration). `-ExportSrc` writes generated code
  to a throwaway folder, so the project need not be a workspace member and the
  run never hits `Cannot get container for IPath`. Confirmed on S32DS 3.6.7
  against `Uart_Example_S32K344`: known-good → exit `0`, 120 generated files, no
  `[TOOL] … has the following error`; a known-bad probe (`OsIfUseSystemTimer=true`
  with an empty `OsIfCounterConfig`) → exit `0` **but** the gate-tripping
  `SEVERE: [TOOL] The resource "BaseNXP" … has the following error: The number of
  OsIf Counters must be exactly one …`. This empirically confirms exit `0` alone
  is insufficient. The CLI validates a throwaway copy so the caller's project is
  never modified.
- **(A) Project mode (SUPERSEDED):** registered the project via the CDT headless
  `-import` application, then `-Load <mex> -ProjectLink <project> -UpdateCode`.
  The `-import` step routinely exceeded the timeout (exit `124`); the project was
  then not a workspace member, so `-UpdateCode` failed with repeated
  `Cannot get container for IPath` and a spurious exit `2` on a pristine fixture.
  Replaced by (B). Kept here only as the rejected approach.
- Evidence flags: `-ExportHTML` (report), `-ExportMEX` (tool-normalized `.mex` to
  diff against the input).

## 4. DMA ISR/IRQ names — S32K344 cross-cutting fact

**Source:** Installed-RTD-derived (S32K3 RTD 7.0.1):
- `Platform.epd` DMATCD IRQ table (IRQn enum values for each DMA Transfer Control
  Descriptor channel).
- `Dma_Ip_Irq.c` — the `Dma0_Ch<N>_IRQHandler` ISR function names generated by
  RTD for each DMA HW channel.

These names are also pinned in `autombd-rtd/assets/nxp/s32k3/uart/uart.json`
`dma_hw_channel_irq_map` (runtime asset; loaded by the Uart provider, not hardcoded).

**Why here:** DMA ISR names are a cross-cutting concern shared between the Uart
provider (Platform ISR insertion) and any future DMA-using provider. Recording them
here allows future maintainers to re-verify the mapping without reopening the RTD
install.

**S32K344 mapping (DMA HW channel N → DMATCD IRQn / ISR handler):**

| DMA HW Channel | IRQn enum (`Platform.epd`) | ISR handler (`Dma_Ip_Irq.c`) |
| --- | --- | --- |
| 0 | `DMATCD0_IRQn` | `Dma0_Ch0_IRQHandler` |
| 1 | `DMATCD1_IRQn` | `Dma0_Ch1_IRQHandler` |

Pattern: `DMATCD<N>_IRQn` / `Dma0_Ch<N>_IRQHandler` for channel index N.

**Uart DMA usage (RTD-MEX-UART-003):** TX uses DMA HW channel 0 (existing fixture
`dmaLogicChannel_Type_0`, `HwChId=DMA_IP_HW_CH_0`); RX uses DMA HW channel 1
(inserted `dmaLogicChannel_Type_1`, `HwChId=DMA_IP_HW_CH_1`).

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-03 | 0.1.0 | Initial anchor (attempted to register per-module enum facts). |
| 2026-06-03 | 0.2.0 | Reframed: per-module values/constraints/dependencies are sourced from each `<Module>.xdm` and owned by the provider (not catalogued here); this doc keeps only the cross-cutting S32DS validation flow/gate, fixture facts, and the sourcing rule. |
| 2026-06-10 | 0.3.0 | Fourth-round review resolution: recorded the exact pin-mux workbook path as the pins.json source (development input only); reframed §2 as fixture role/usage (fixtures grow with module support; Uart_Example_S32K344 kept as the worked example); asset paths updated to `autombd-rtd/assets/`. |
| 2026-06-11 | 0.4.0 | Verified S32DS **Flow B** (standalone `-Load`/`-ExportSrc`, no registration) on S32DS 3.6.7 and adopted it as the validation flow; marked the registration-based **Flow A** superseded. Flow A's CDT `-import` step timed out (exit 124), so every run failed with `Cannot get container for IPath` and a spurious exit 2 even on a pristine fixture. Recorded the known-good/known-bad evidence and the empirical confirmation that exit 0 alone is insufficient (an invalid OsIf edit returns exit 0 while logging a SEVERE `[TOOL] … has the following error`). |
| 2026-06-11 | 0.4.1 | Corrected the `Uart_Example_S32K344` fixture line-ending fact: the file has LF (Unix) endings (CRLF count 0, LF 2467 — byte-verified), not CRLF. Added the auto-detect rule: the byte-faithful writer derives line endings from the file and never hardcodes a style. |
| 2026-06-11 | 0.4.2 | §1 pin-mapping: replaced the stale "pins.json is a stub / must be rebuilt / pin-options unverified" note — the asset is now built from the IOMUX workbook by `tools/build_pins_s32k3.py` (2091 S32K344 signals, verified); Port `.mex` pin application remains the open Port capability. |
| 2026-06-14 | 0.4.4 | Tightened the asset sourcing rule (step 3) to match the enforced LL-012 discipline: a provider loads the committed asset at runtime, or — if it embeds the constants — pins them with a code==asset test that fails on drift; a documentation-only asset with no loader and no pin is prohibited. |
| 2026-06-13 | 0.4.3 | §4 added: S32K344 DMA ISR/IRQ cross-cutting fact (`DMATCD<N>_IRQn` / `Dma0_Ch<N>_IRQHandler`) sourced from installed-RTD Platform.epd and Dma_Ip_Irq.c; pinned in uart.json dma_hw_channel_irq_map. LL-017 provenance fix: updated uart.json dma_hw_channel_irq_map._note to credit Platform.epd/Dma_Ip_Irq.c (not the committed fixture). |
| 2026-06-15 | 0.5.0 | Issue #7 reorganization: de-agented the §1 sourcing-rule steps — removed the Explorer/Worker/Tester/Reviewer role names from steps 2/3/5 so the spec reads as an agent-agnostic engineering process. |
