# RTD CfgFile CLI Source Materials

| Field | Value |
| --- | --- |
| Version | 0.3.3 |
| Date | 2026-06-16 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Records RTD CfgFile CLI development source materials, vendor tool environment assumptions, and runtime data boundaries. |

This document records the types of source material used to build runtime data
assets for RTD CfgFile CLI. Source material is for development and
data preparation only. Runtime commands must not depend on these files being
present.

## Runtime Boundary

Runtime commands may load:

- repository JSON configuration;
- committed module manifests and capability data;
- committed schema/constraint cache JSON;
- committed pin mapping JSON;
- target project files;
- configured vendor validation tools.

The current development computer is configured with the required vendor tool
environment for S32DS/S32 ConfigTools validation. The configured vendor
validation tool may use its own installed environment internally, including RTD
packages and metadata. This does not relax the RTD CfgFile CLI runtime boundary:
the CLI itself must not directly read development-only source material during
normal operation.

Runtime commands must not load:

- Excel workbooks used to derive pin mapping;
- installed RTD package `.xdm` files directly;
- broad RTD installation directory scans;
- ad hoc developer notes or local-only paths;
- files outside the repository unless they are explicit target projects or
  configured validation tool paths.

## Source Material Categories

| Category | Purpose | Runtime output |
| --- | --- | --- |
| Pin mux tables | Build device/package pin mapping | `pins.json` |
| RTD module descriptors | Extract containers, enums, refs, constraints | schema/constraint cache JSON |
| Real ConfigTools projects | Validate real project structure and edits | fixtures and test cases |
| Vendor validation references | Build headless validation commands | validation profile JSON or config |
| RTD release metadata | Track package/release compatibility | module/release metadata JSON |

## Known Development Inputs

Known development input types are listed here for traceability. This document
must not contain machine-specific absolute paths. Concrete local locations are
checkout facts, not project specification. When local tooling needs a path,
first check the project-local ignored external-dependency cache. If the entry is
absent or stale, ask the user for the location and cache only the non-secret
availability evidence.

| Source | How to locate | Use | Notes |
| --- | --- | --- | --- |
| S32K344/S32K324/S32K314 IOMUX workbook | Ask the user for the vendor workbook location, or reuse a cached `source.s32k3_iomux_workbook` local path if present. | Build S32K3 pin mapping data | Development input only |
| S32K3 RTD module `.xdm` files | Locate from the user-provided S32DS/RTD installation root, or reuse cached `env.s32ds_root` / `source.s32k3_rtd_xdm` evidence if present. | Build module schema and constraints | Development input only |
| Uart RTD descriptor example | Locate under the same S32K3 RTD descriptor set as the other module `.xdm` files; ask the user if the module package cannot be found. | Build Uart schema and constraints | Development input only |
| S32DS ConfigTools projects | Use committed fixtures under `tests/fixtures/nxp/<backend>/<family>/<project>/`, or ask the user for any additional real project used only for data preparation. | Build and validate fixtures | Current Uart fixture: `tests/fixtures/nxp/ds/s32k3/Uart_Example_S32K344/`; keep generated/build artifacts out |
| Deprecated rtd-config skills | Ask the user for the local legacy skill checkout only when prior `.mex` editing experience must be re-examined; cache as `source.legacy_rtd_config_skill` if used. | Extract prior `.mex` editing experience for the `.mex` implementation | Development input only; `.mex` editing experience extracted to seed the implementation rules; never load at runtime |

## Data Preparation Rule

When source material is used, convert the needed information into committed,
versioned runtime JSON/cache data. The tool should be able to configure a
project in a clean runtime environment using only repository assets, the target
project, and configured vendor validation tools.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-16 | 0.3.3 | Removed machine-specific absolute paths from known development inputs and redirected concrete locations to local external-dependency cache evidence. |
| 2026-06-02 | 0.3.2 | Added deprecated rtd-config skills as development-only source material and linked the M1 experience baseline. |
| 2026-06-02 | 0.3.1 | Aligned fixture reference path with backend/family/device/module/projects/project layout and recorded the current Uart fixture. |
| 2026-06-02 | 0.3.0 | Renamed document for RTD CfgFile CLI and clarified allowed vendor validation tool environment dependencies. |
| 2026-05-30 | 0.2.1 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.0 | Added concrete development source material locations. |
| 2026-05-30 | 0.1.0 | Created runtime/source-material boundary reference. |
