# RTD CfgFile CLI Source Materials

| Field | Value |
| --- | --- |
| Version | 0.4.0 |
| Date | 2026-06-16 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Records external reference materials used to prepare RTD CfgFile CLI runtime data assets. |

This document records external reference materials used to build committed
runtime data assets for RTD CfgFile CLI. Reference materials are for development
and data preparation only; runtime commands must not depend on these files being
present.

## Reference Materials

Known reference material types are listed here for traceability. This document
must not contain machine-specific absolute paths. Concrete local locations are
checkout facts, not project specification. When local tooling needs a path,
first check the project-local ignored external-dependency cache. If the entry is
absent or stale, ask the user for the location and cache only the non-secret
availability evidence.

| Reference material | What it is | How to locate | Role | Cache hint |
| --- | --- | --- | --- | --- |
| S32K344/S32K324/S32K314 IOMUX workbook | Vendor spreadsheet describing package pins, pad functions, alternate functions, and peripheral signal routing for the S32K3 devices used by this project. | Ask the user for the vendor workbook location, or reuse cached local evidence if present. | Source for building and reviewing committed S32K3 pin mapping data such as `pins.json`. | Cache the local workbook path as `source.s32k3_iomux_workbook` when used. |
| S32K3 RTD module `.xdm` files | Vendor XML descriptor files shipped with the S32K3 RTD package; each module descriptor defines configuration containers, parameters, references, enums, defaults, and constraints used by S32 ConfigTools. | Locate from the user-provided S32DS/RTD installation root, or reuse cached local evidence if present. Ask the user if the S32DS/RTD root is unknown. | Source for building and reviewing committed module schema, constraint, enum, and reference cache data. | Cache the S32DS/RTD root as `env.s32ds_root` and descriptor evidence as `source.s32k3_rtd_xdm` when used. |

## Data Preparation Rule

When source material is used, convert the needed information into committed,
versioned runtime JSON/cache data. The tool should be able to configure a
project in a clean runtime environment using only repository assets, the target
project, and configured vendor validation tools.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-16 | 0.4.0 | Refactored the document into a concise reference-material catalog, removed runtime-boundary and category sections, and kept only the two external reference material types. |
| 2026-06-16 | 0.3.3 | Removed machine-specific absolute paths from known development inputs and redirected concrete locations to local external-dependency cache evidence. |
| 2026-06-02 | 0.3.2 | Added deprecated rtd-config skills as development-only source material and linked the M1 experience baseline. |
| 2026-06-02 | 0.3.1 | Aligned fixture reference path with backend/family/device/module/projects/project layout and recorded the current Uart fixture. |
| 2026-06-02 | 0.3.0 | Renamed document for RTD CfgFile CLI and clarified allowed vendor validation tool environment dependencies. |
| 2026-05-30 | 0.2.1 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.0 | Added concrete development source material locations. |
| 2026-05-30 | 0.1.0 | Created runtime/source-material boundary reference. |
