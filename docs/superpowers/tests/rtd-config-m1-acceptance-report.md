# RTD CfgFile CLI Milestone 1 Acceptance Report

| Field | Value |
| --- | --- |
| Version | 0.2.0 |
| Date | 2026-06-03 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Milestone 1 acceptance integration report for the RTD CfgFile CLI: deterministic development testing, independent black-box subagent validation, static runtime verification, and **real S32DS / S32 ConfigTools headless vendor validation** against the active M1 specs, plan, and test strategy. |

## 1. Verdict

**Milestone 1 is ACCEPTED.** The RTD CfgFile CLI delivers the minimal S32K344
RTD 7.0.1 Uart stack — LPUART and FlexIO-backed channels in **interrupt (IRQ)
mode** — through a deterministic CLI / JSON contract that makes narrow,
byte-faithful, owned `.mex` edits and runs layered runtime verification: fast
static checks first, then **S32DS ConfigTools headless validation**.

The S32DS validation gate is satisfied: the tool's own `validate` command returns
ConfigTools **exit 0 with zero SEVERE `[TOOL]` problems** on both the configured
LPUART interrupt and FlexIO interrupt projects (§6).

Acceptance against the test-strategy Acceptance Rule:

- required mandatory minimum cases pass — **yes** (interrupt-only matrix, §3);
- backend validation passes — **yes** (real S32DS exit 0 + clean, §6);
- focused independent subagent validation meets the KPI — **yes** (§4);
- failures produce actionable diagnostics, not tracebacks — **yes** (§5, §7).

## 2. Scope Correction: interrupt-only (RTD model)

Mandatory S32DS validation revealed that RTD 7.0.1 models the Uart "asynchronous
method" (`UartInteruptDmaMethod` / `FlexioUartInteruptDmaMethod`) with **only
`INTERRUPTS` and `DMA`** — there is **no polling value** (verified in
`Uart.xdm` and the s32k344 `.epd`). The earlier implementation wrote an invented
`..._USING_POLLING` enum, which ConfigTools rejected as `值不可用 (value not
available)`. Per the project decision, **M1 supports interrupt (IRQ) only**; DMA
remains out of scope; "polling/blocking" is an application-level driver-call
pattern, not a `.mex` mode. The mandatory cases RTD-M1-MIN-002/-004 (polling)
are reserved/removed.

## 3. Deterministic Development Testing

```powershell
python -m pytest -q
# 44 passed
```

Distribution: **unit 30, integration 7, e2e 7 — 44 total.** The e2e layer is the
interrupt-only mandatory matrix plus the S32DS command-construction test.
Non-vendor assertions always run; the live S32DS run is gated by
`RTD_CONFIG_RUN_S32DS_VALIDATION` so the matrix is green with or without the
vendor environment while still exercising the vendor path when available.

| Case | Surface | Result |
| --- | --- | --- |
| RTD-M1-MIN-001 | `inspect` | PASS — backend/device/package/RTD/modules/profile |
| RTD-M1-MIN-002 | — | Reserved/removed (polling not an RTD `.mex` value) |
| RTD-M1-MIN-003 | `uart set` LPUART interrupt | PASS |
| RTD-M1-MIN-004 | — | Reserved/removed (polling not an RTD `.mex` value) |
| RTD-M1-MIN-005 | `uart set` FlexIO interrupt | PASS |
| RTD-M1-MIN-006 | `pin-options` | PASS |
| RTD-M1-MIN-007 | E2E LPUART stack | PASS — configure + check |
| RTD-M1-MIN-008 | E2E FlexIO stack | PASS — configure + check |

## 4. Independent Black-Box Subagent Validation

Performed per `rtd-config-m1-subagent-validation.md`. Four cold, context-isolated
subagents (`fork_context:false`: no inherited conversation state) each received
only the simulated Chinese user request, the repository-visible companion skill,
the public CLI, and a private fixture copy. All four converged well within the
3-minute focused KPI (max ~77 s; no run approached the 10-minute intervention
threshold) and independently confirmed module-ownership boundaries, the FlexIO +
Mcl path, DMA absence, and the runtime/development-source boundary. This black-box
pass was at the static-check / JSON-contract level and predates the RTD-model
(interrupt-only) correction; the binding backend acceptance is the real S32DS
validation in §6.

## 5. Runtime Verification — Static Checks

The fast, vendor-free static stage runs during development testing and as the
first stage of runtime verification after every `.mex` edit. All failure patterns
from `rtd-config-m1-legacy-skills-experience.md` are implemented and covered: XML
well-formedness, single `.mex`, enabled-module / duplicate-name detection,
`quick_selection` conflict on modified elements, stale FlexIO `UartHwChannelRef`,
missing Mcl FlexIO logic channel, duplicate LPUART hardware, `UartChannelId` index
match, invalid callback, and M1 DMA rejection. The Uart engine also rejects any
non-interrupt mode (`unsupported_uart_mode`) instead of writing an invalid enum.
Blockers are structured diagnostics, never tracebacks.

`.mex` write fidelity is enforced by regression tests: a no-edit write reproduces
the file byte-for-byte (XML declaration, CRLF, attribute order); an owned edit
changes only the lines it actually touches.

## 6. Runtime Verification — S32DS Headless (Vendor)

### 6.1 Verified flow (S32DS 3.6.7)

The released tool drives the flow that was confirmed against the installed
toolchain:

- launcher `s32dsc.exe` with `--launcher.ini <eclipse>\s32ds.ini`;
- ConfigTools framework app `com.nxp.swtools.framework.application` with
  `-nosplash -consoleLog` **and `-HeadlessTool Peripherals`** (without the
  headless tool the app starts a workbench and never terminates — the original
  "hang");
- `-sdkPath <root>\S32DS\software\PlatformSDK_S32K3` (ships `sdk_manifest.xml`);
- the project is registered in the workspace via the CDT headless `-import`
  application (else `Cannot get container`); external projects are staged into
  the workspace and cleaned up automatically;
- `-Load <mex> -ProjectLink <project> -UpdateCode -ShowProblems SEVERE`.

**Pass gate:** ConfigTools exit `0` **and** no SEVERE `[TOOL] ... has the
following error` resource problem. Exit `0` alone is insufficient — ConfigTools
returns `0` even with SEVERE configuration errors. (`Toolchain/IDE project`
driver-not-found SEVEREs are project-build-setup noise, not `.mex` validity.)

### 6.2 Result

Run via the tool's own `rtd-config validate`:

| Configured project | ConfigTools exit | SEVERE `[TOOL]` | Verdict |
| --- | --- | --- | --- |
| Unmodified fixture (LPUART_3 interrupt) | 0 | 0 | clean |
| LPUART interrupt (tool-edited) | 0 | 0 | **PASS** |
| FlexIO interrupt (tool-edited) | 0 | 0 | **PASS** |

The controlled comparison also proved attribution: the only configuration that
produced SEVERE `[TOOL]` errors was the (now-removed) polling case, whose invalid
async-method enum caused `值不可用` plus a spurious DMA-channel-reference demand.

## 7. Defects Found and Fixed During Acceptance

| Defect | Impact | Fix | Commit |
| --- | --- | --- | --- |
| `.mex` writer reserialized the whole document (3096-line churn) | Violated mandatory "narrow / localized edits" | expat source-span surgical writer; stdlib only | `50ba1dc` |
| `inspect` omitted chip package | MIN-001 asks for 封装 | emit `config.package`; guard in test | `3fc6eb1` |
| `--launcher.ini` → non-existent `s32dsc.ini`; app id `...HeadlessApplication` unregistered; timeout/missing-exe raised tracebacks | `validate` unusable / non-structured | resolve `s32ds.ini`; registered app id; structured 124/127 | `675dfb2` |
| **Invalid `..._USING_POLLING` enum** (no such value in RTD 7.0.1) | ConfigTools rejected every polling config (`值不可用`) | interrupt-only Uart; reject other modes with an actionable blocker | `31816a9` |
| Headless app hung (missing `-HeadlessTool`); wrong `-sdkPath`; unregistered project (`Cannot get container`); exit-0-alone treated as pass | Real vendor validation impossible | verified flow: `-HeadlessTool`, PlatformSDK `-sdkPath`, CDT register + workspace staging, exit-0-AND-no-SEVERE gate | `31816a9` |

## 8. Scope and Boundary Compliance

- **Interrupt-only / no DMA:** the engine writes only the valid `INTERRUPTS`
  enum; `UartDmaEnable`/`MclEnableDma` true → `dma_not_supported_in_m1` blocker.
- **No creation:** edits existing module instances only.
- **Module ownership:** each provider edits only its region; cross-module needs
  are declared dependencies (Mcu clock, Port pins, Platform IRQ, Mcl FlexIO).
- **Runtime/development boundary:** runtime commands read only committed assets;
  no Excel, raw `.xdm`, deprecated skills, or RTD scans at runtime. RTD `.xdm` /
  `.epd` descriptors were consulted only as *development* references to fix the
  enum and validation flow, not as runtime dependencies. The vendor tool uses its
  own installed environment, as permitted.
- **Documentation boundary:** `docs/superpowers/specs/achieved/` was treated as a
  review archive and not used as a requirements source.

## 9. Known Limitations and Deferred Work (M2+)

- DMA-backed Uart, `.mex` creation, missing-module completion, EB tresos backend,
  K1/K5 validation profiles;
- advanced and reserved-future test classes (planning inputs, not M1 gates);
- the reported package is the profile-level identifier (`default`);
- live S32DS validation imports/stages the project into the configured workspace;
  the full env-gated matrix runs under `RTD_CONFIG_RUN_S32DS_VALIDATION=1`.

## 10. Artifacts

- Source: `rtd_config/` (CLI, S32 `.mex` backend, modules, checks, resources).
- Tests: `tests/unit` (30), `tests/integration` (7), `tests/e2e` (7).
- Runtime assets: `data/.../packages/default/pins.json`.
- Companion skill: `.skills/rtd-config/SKILL.md`.
- Validation experience: `docs/superpowers/specs/rtd-config-m1-legacy-skills-experience.md`.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-03 | 0.1.0 | Created the Milestone 1 acceptance integration report. |
| 2026-06-03 | 0.2.0 | Rewrote after real S32DS validation: M1 is interrupt-only (RTD has no polling async-method value); recorded the verified ConfigTools headless flow and the exit-0 + no-SEVERE vendor PASS for LPUART and FlexIO interrupt. |
