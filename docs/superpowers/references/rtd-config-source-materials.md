# RTD Configuration Source Materials

| Field | Value |
| --- | --- |
| Version | 0.2.1 |
| Date | 2026-05-30 |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | Records development source materials and runtime data boundaries. |

This document records the types of source material used to build runtime data
assets for the RTD configuration tool. Source material is for development and
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

Known local development inputs are listed here for traceability. These paths are
development references, not runtime dependencies. If a local path changes,
update this document or add a project-specific reference note; do not hard-code
the path into runtime code.

| Source | Reference location | Use | Notes |
| --- | --- | --- | --- |
| S32K344/S32K324/S32K314 IOMUX workbook | `D:\WorkSpace\ExploreSpace\Copy of S32K344_S32K324_S32K314_IOMUX.xlsx` | Build S32K3 pin mapping data | Development input only |
| S32K3 RTD module `.xdm` files | `C:\NXP\S32DS.3.6.7\S32DS\software\PlatformSDK_S32K3\RTD\<ModulePackage>\config\<Module>.xdm` | Build module schema and constraints | Development input only |
| Uart RTD descriptor example | `C:\NXP\S32DS.3.6.7\S32DS\software\PlatformSDK_S32K3\RTD\Uart_TS_T40D34M70I1R0\config\Uart.xdm` | Build Uart schema and constraints | Development input only |
| S32DS ConfigTools projects | `fixtures/projects/<backend>/<family>/<device>/<scenario>/` | Build and validate fixtures | Keep generated/build artifacts out |

## Data Preparation Rule

When source material is used, convert the needed information into committed,
versioned runtime JSON/cache data. The tool should be able to configure a
project in a clean runtime environment using only repository assets, the target
project, and configured vendor validation tools.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-05-30 | 0.2.1 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.0 | Added concrete development source material locations. |
| 2026-05-30 | 0.1.0 | Created runtime/source-material boundary reference. |
