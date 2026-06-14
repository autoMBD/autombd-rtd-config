# RTD CfgFile CLI Legacy Skills Experience

| Field | Value |
| --- | --- |
| Version | 0.1.5 |
| Date | 2026-06-14 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Development-time reference: captures `.mex` editing experience from the deprecated S32K3 RTD configuration skills that must guide the tool's `.mex` implementation. |

## Purpose

This document distills practical `.mex` editing experience from the deprecated
rtd-config skills under:

`D:\WorkSpace\ExploreSpace\autombd-skills\skills\rtd-config`

The external skills are development references only. They are not runtime
dependencies of RTD CfgFile CLI. The development team must use this document,
the current active specs, the committed fixture projects, and runtime
validation results as the authority for `.mex` implementation.

The source skills captured real attempts to configure S32K3 RTD 7.0.1 modules
through S32DS ConfigTools `.mex` files. Their most important value is not the
old skill workflow itself, but the failure patterns and editing rules learned
from those attempts.

## Source Coverage

The extraction covers these deprecated skills and references:

| Current module | Deprecated source directory |
| --- | --- |
| `Mcu` | `autombd-s32k3-rtd-mcu-config-hld` |
| `BaseNXP` | `autombd-s32k3-rtd-basenxp-config-hld` |
| `Platform` | `autombd-s32k3-rtd-platform-config-hld` |
| `Port` | `autombd-s32k3-rtd-port-config-hld` |
| `Dio` | `autombd-s32k3-rtd-dio-config-hld` |
| `Mcl` | `autombd-s32k3-rtd-mcl-config-hld` |
| `Uart` | `autombd-s32k3-rtd-uart-config-hld` |
| Shared validation | `autombd-s32k3-config-validation` |
| Minimal `.mex` references | `autombd-s32k3-mex-config-mininal-reference` |
| `.mex` tooling attempts | `autombd-s32k3-rtd-mex-tool`, `autombd-s32k3-rtd-mex-create` |

The extracted rules are version-sensitive to S32K3 RTD 7.0.1 and must be
rechecked before being generalized to other RTD versions or device families.

## Mandatory Development Rules

These rules must be reflected in implementation, tests, diagnostics, and
validation.

| Rule | Requirement |
| --- | --- |
| Narrow edits | Inspect and edit only the `.mex` regions required by the command. Avoid broad inventory scans and broad whole-file rewrites. |
| Ownership | Each module provider may write only its owned module area. Cross-module needs become explicit dependency requests. |
| `quick_selection` | If an element carrying `quick_selection` has its content or children modified, remove `quick_selection` from that element. Unmodified default/template elements may keep it. |
| Metadata preservation | Preserve unrelated UUIDs, dependency entries, component order, localized labels, generated-file metadata, and project links unless the requested change or validation requires a narrow update. |
| Generated files | Do not hand-minimize `generated_project_files`. Let S32 ConfigTools refresh generated-file lists after coherent module/dependency edits. |
| Missing modules | The tool works on existing complete fixture projects. Creation from seeds is reserved for later work, but the implementation must not make seed handling impossible. |
| Runtime data | Do not load deprecated skills, Excel files, raw RTD descriptors, or local install scans at runtime. Convert needed facts into committed runtime assets. |
| Validation | After `.mex` edits, static check runs first, then S32DS/S32 ConfigTools headless validation when configured. Compilation is not proof of `.mex` validity. |
| Diff review | After vendor validation, review the `.mex` diff. Tool-introduced unrelated metadata churn should not become accepted project change. |

## `quick_selection` Handling

The strongest shared lesson is that `quick_selection` is not harmless metadata.
S32 ConfigTools may treat it as a default-template selection. If an element was
edited but still carries its previous quick-selection marker, ConfigTools can
restore default content, discard generated-file entries, or report misleading
errors in another module.

RTD CfgFile CLI must implement `.mex` editing helpers with these semantics:

- when a setting value changes, remove `quick_selection` from the changed
  element if present;
- when a child element is inserted, deleted, or modified, remove
  `quick_selection` from the nearest modified ancestor that carries it;
- keep `quick_selection` only on elements whose content and descendants remain
  identical to the pre-existing project state;
- record a structured diagnostic if a planned edit would leave
  `quick_selection` on a modified element;
- cover this behavior with unit tests and fixture integration tests.

The Mcl/FlexIO Uart case is the highest-risk example. Leaving
`quick_selection="mcl_default"` on `<config_set name="Mcl">` while enabling
FlexIO common or adding FlexIO logic channels can make ConfigTools revert the
Mcl tree and then report the error as a Uart problem. The validation symptom
observed in the deprecated skill material is a Uart out-of-range error after
adding FlexIO-backed Uart channels. The first diagnosis step must be checking
Mcl `quick_selection`, not blindly changing Uart channel fields.

## Backend Document Core Implications

The `.mex` backend document core must provide reusable helpers rather than
letting every provider manipulate XML ad hoc:

- targeted module and config-set lookup;
- setting/container lookup and upsert;
- "mark modified" behavior that removes conflicting `quick_selection`;
- narrow write support that avoids unrelated subtree churn where feasible;
- generated UUID support for later seed insertion;
- diagnostics for missing instance, duplicate names/IDs, invalid references,
  stale references, and quick-selection conflicts;
- enough XML context to preserve ordering and local project style.

This is a core/backend responsibility. Individual providers should describe
what needs to change; the backend should apply consistent XML safety behavior.

## Validation Experience

Shared validation experience from the deprecated skills must be preserved:

- Use `s32dsc.exe` with the S32DS launcher `.ini`; do not use `s32ds.bat` as the
  primary validation command because it can return before the headless action
  completes.
- Prefer a real existing S32DS Eclipse workspace. The documented default is
  `D:\WorkSpace\DSpace\3.6` on the current development computer.
- Prefer the ConfigTools framework application with project import and
  `-sdkPath` so SDK driver components are resolved correctly.
- The expected validation pass condition is ConfigTools process exit code `0`.
- Keep validation logs under the target project's `build/` directory.
- Import is needed when the project is not already present in the workspace or
  ConfigTools reports workspace/container errors.
- CDT headless build commands are not the authoritative `.mex` validation flow.
- Build/compile should run only after ConfigTools validation succeeds.

### Empirically verified on S32DS 3.6.7 (2026-06-03)

Verified end-to-end against the installed `C:\NXP\S32DS.3.6.7` ConfigTools during
minimal-system acceptance. The headless `.mex` validation flow that returns exit `0`:

- **Launcher:** the console launcher `s32dsc.exe` ships **no** `s32dsc.ini`; pass
  `--launcher.ini <eclipse>\s32ds.ini` (the shared GUI launcher config) or it
  aborts.
- **Application id:** `com.nxp.swtools.framework.application.HeadlessApplication`
  is **not registered**; use `com.nxp.swtools.framework.application`.
- **`-HeadlessTool <tool>` is required** (e.g. `Peripherals`). Without it the
  framework app starts a workbench (`...CPerspective`) and never terminates --
  this was the earlier "hang".
- **`-sdkPath`** must point at the bundled PlatformSDK that ships
  `sdk_manifest.xml`: `<root>\S32DS\software\PlatformSDK_S32K3` (not a standalone
  RTD package).
- **Registered project:** the project must be a workspace member, else
  ConfigTools logs `Cannot get container for IPath`. Register with the CDT
  headless `-import` application first; if the project is outside the `-data`
  workspace, stage a copy inside it (the RTD CfgFile CLI stages and cleans up
  automatically).
- **Load/generate** with `-Load <mex> -ProjectLink <project> -UpdateCode` and
  surface problems via `-ShowProblems SEVERE`.
- **Pass gate:** ConfigTools exit `0` **and** no SEVERE `[TOOL] ... has the
  following error` resource problem. Exit `0` alone is NOT sufficient -- it
  returns `0` even with SEVERE config errors. "Toolchain/IDE project"
  driver-not-found SEVEREs are project-build-setup noise, not `.mex` validity.

Confirmed exit `0` with zero SEVERE `[TOOL]` problems on the unmodified fixture
and on the tool-edited LPUART and FlexIO **interrupt** configs. The flow also
caught a real defect: a `polling` config wrote an invalid `UartInteruptDmaMethod`
enum (RTD 7.0.1 has only INTERRUPTS / DMA), which ConfigTools rejected as
an unavailable-value error -- the reason polling is unsupported (INTERRUPTS and
DMA are the only valid async methods).

## Module Experience Summary

| Module | Owned configuration | Key experience |
| --- | --- | --- |
| `Mcu` | Mcu general, clock settings, clock reference points, mode/RAM/reset/power subtrees | Uart and FlexIO depend on valid Mcu clock references. Clock edits are derivative-specific and can invalidate downstream modules. External oscillator pins are Port-owned; clock-monitor/reset/voltage interrupts are Platform-owned. |
| `BaseNXP` | BaseNXP/OsIf general configuration and common support generation | OsIf timer choices affect Uart timeout behavior. Bare-metal system timer must use either an Mcu clock reference or explicit frequency, not both. Custom timers require application functions; do not invent behavior. |
| `Platform` | Platform general, IntCtrl, ISR config, MPU/MCM/INTM feature families | Interrupt configuration is Platform-owned. Do not enable IRQs by default; require exact interrupt source, priority, handler or `NULL_PTR`, enable flag, and partition/core target when relevant. |
| `Port` | Generic SIUL2 pin mux, electrical configuration, untouched pins and IMCRs | Port must stay generic, not Uart-bound. Consumer modules may request pins, but Port owns mux/electrical edits. Do not remove untouched pin/IMCR protection casually. Pin data is derivative/package-specific. |
| `Dio` | Dio ports, channels, channel groups, API switches, partition refs | Dio owns symbolic digital-I/O IDs; Port owns mux/direction/pad settings. Dio channel/group IDs must be unique and package-valid. Channel group masks must match bit count, offset, and reverse-bit mode. |
| `Mcl` | Mcl common resources: FlexIO, DMA, eMIOS, TRGMUX, LCU, cache gates | Mcl is a dependency owner. FlexIO common resources are owned by Mcl and consumed by Uart. Feature switches and arrays must match; enabling FlexIO common without coherent logic channels is incomplete. DMA logic channels are likewise Mcl-owned and consumed by Uart's DMA path. |
| `Uart` | Uart channels, Uart general settings, LPUART/FlexIO channel containers and Uart-side refs | LPUART and FlexIO paths are different. Uart owns channel settings and references; Mcu owns clock references, Mcl owns FlexIO and DMA logic channels, Port owns TX/RX pin routing, Platform owns IRQ entries. |

## Mcu Notes

Mcu is the clock and mode foundation for the Uart minimum stack.

- The tool covers the minimum clock/reference and peripheral-clock behavior
  required by the Uart fixture and mandatory tests.
- Clock reference names, peripheral gates, oscillator availability, PLL limits,
  mux inputs, and divider formulas are device- and RTD-version-sensitive.
- Changing FXOSC/SXOSC use can imply Port-owned oscillator pin routing.
- Clock monitor, PMC voltage, or reset demotion interrupt paths imply
  Platform-owned interrupt configuration.
- IDs and calculated count fields for clock settings, modes, and RAM sections
  must remain coherent.

## BaseNXP Notes

BaseNXP is shared infrastructure, especially for OsIf.

- The tool should detect and preserve existing BaseNXP/OsIf configuration needed
  by the complete fixture.
- Uart timeout features depend on coherent OsIf timer configuration.
- Bare-metal system timer counter configuration must not specify both an Mcu
  clock reference and explicit clock frequency.
- Multicore, AUTOSAR OS mode, partition references, software semaphores, custom
  timers, and DET/Devassert details are advanced or future work unless required
  by the fixture.

## Platform Notes

Platform owns interrupt controller configuration.

- Uart interrupt mode must create or update Platform IRQ entries only through
  Platform provider logic.
- The plan must not guess interrupt priority, handler, enable state, or
  partition/core target when missing from the user request or runtime defaults.
- `IsrName` must be unique in the relevant list.
- `IsrPriority` must be within the device/schema range.
- `IsrHandler` must be a valid C function name or `NULL_PTR`.
- MPU, MCM, and INTM remain advanced or future work unless needed by the
  existing fixture.

## Port Notes

Port must be implemented as a generic pin configuration service.

- The Port provider must not be hardwired to Uart. Uart, Dio, and future
  modules use the same pin-options and set-pin model.
- Pin mapping must come from prepared runtime assets by family, device,
  package, peripheral, signal, and pin.
- Uart TX/RX pin selection is a consumer request; Port owns the actual mux and
  electrical configuration.
- Preserve `UnTouchedPortPin` and `UntouchedIMCR` unless the requested change
  explicitly conflicts and validation proves the replacement is required.
- Input-buffer/readback, pull, drive, open-drain, inversion, filter, and mode
  changeability are electrical choices, not Uart defaults.

## Dio Notes

Dio is simple but still needs clear ownership.

- Dio does not configure pin mux, direction, pull, or default output level.
- Dio channel IDs are logical AUTOSAR symbols tied to SIUL2 port halves and
  bits; they must be package-valid.
- If a requested Dio channel targets a board pin, the plan must include a
  Port-owned GPIO dependency.
- Multi-partition and virtual-wrapper behavior requires existing Rm/EcuC
  references and is not part of the minimum configuration.

## Mcl Notes

Mcl is the key dependency module for FlexIO-backed Uart.

- Mcl owns `MclFlexioCommon` and `FlexioMclLogicChannels`.
- FlexIO-backed Uart must be planned as a coherent Mcl + Uart change.
- `MclEnableFlexioCommon=true` must match actual FlexIO common/channel entries.
- FlexIO logic-channel names should be stable and meaningful; avoid leaving new
  channels with default names when they represent assigned Uart resources.
- `FlexioMclChannelId` and `FlexioMclPinId` must be unique within the selected
  FlexIO common configuration unless the schema and fixture pattern prove a
  paired-channel exception.
- DMA must be configured coherently across Mcl and Uart, never partially (a DMA
  method requires the matching Mcl DMA logic channels and Uart Tx/Rx refs).

## Uart Notes

Uart is the user-facing driver path.

- The tool supports LPUART and FlexIO-backed Uart in interrupt (IRQ) and DMA
  modes; polling is not an RTD 7.0.1 async-method value.
- `UartChannelId` must match the channel array index.
- LPUART hardware instances must be unique across active LPUART Uart channels
  and must not conflict with LIN use.
- FlexIO `UartHwChannelRef` must point to an existing Mcl FlexIO logic channel.
- FlexIO Uart word length is constrained to 8 bits in the captured RTD 7.0.1
  schema experience.
- Uart callback names must be valid C identifiers; `NULL_PTR` is rejected as a
  Uart callback name in the captured schema material.
- Existing `.mex` files may keep both inactive LPUART detail and FlexIO module
  containers. Do not delete inactive containers just because the current channel
  uses one path.

## Implementation Impact

The implementation must use these experience-derived checks:

- unit tests for quick-selection removal on modified elements;
- fixture tests that configure FlexIO Uart and verify Mcl quick-selection
  conflict is not left behind;
- plan diagnostics that show Uart dependencies as Mcu, Port, Platform, and Mcl
  provider-owned work;
- static checks for stale FlexIO `UartHwChannelRef`, duplicate LPUART hardware
  channels, duplicate IDs/names, missing Mcl FlexIO logic channels, and DMA
  coherence (a DMA method requires matching Mcl DMA logic channels and Uart
  Tx/Rx refs);
- validation command construction aligned with the S32DS ConfigTools headless
  flow described above;
- companion Agent Skill guidance that routes user requests through public CLI
  commands and teaches agents to diagnose the FlexIO/Mcl quick-selection issue.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.1.0 | Created Milestone 1 development experience baseline from deprecated rtd-config skills. |
| 2026-06-03 | 0.1.1 | Added empirically verified S32DS 3.6.7 validation findings: launcher `.ini`, ConfigTools application id, headless-exit limitation, and benign-edit parity check. |
| 2026-06-03 | 0.1.2 | Corrected the S32DS findings: the headless flow IS reproducible with `-HeadlessTool` + workspace registration (PlatformSDK `-sdkPath`); recorded the polling-enum defect and the interrupt-only M1 decision, and the exit-0-plus-no-SEVERE-`[TOOL]` pass gate. |
| 2026-06-10 | 0.1.3 | Fourth-round review resolution: moved from `docs/specs/` to `docs/references/` (development-time reference, not a spec); dropped M1 from the title. |
| 2026-06-13 | 0.1.4 | Reworded the localized unavailable-value vendor message in English and aligned metadata with the append-only changelog. |
| 2026-06-14 | 0.1.5 | Removed milestone (M1) framing from the body so the reference is milestone-agnostic (staging vocabulary lives only in the roadmap); de-staled the Uart/Mcl DMA notes to reflect that DMA mode is now supported (was "deferred"/"rejected"); reworded the polling-enum note to "polling unsupported; INTERRUPTS and DMA are the valid async methods". |
