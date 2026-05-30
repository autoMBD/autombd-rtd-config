# RTD Configuration Source Materials

Version: 0.1.1
Date: 2026-05-30
Author: autoMBD <tkung.lqk@foxmali.com>
Authoring note: AI-assisted archived second-round reviewed reference draft; preserved for traceability.

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

Known local development inputs can be listed here when used, but should not be
hard-coded into spec or runtime code.

| Source | Use | Notes |
| --- | --- | --- |
| S32K344/S32K324/S32K314 IOMUX workbook | Build S32K3 pin mapping data | Development input only |
| RTD module `.xdm` files | Build module schema and constraints | Development input only |
| S32DS ConfigTools projects | Build and validate fixtures | Keep generated/build artifacts out |

<!-- REVIEW: 这里就要写明参考的位置在哪里 -->

## Data Preparation Rule

When source material is used, convert the needed information into committed,
versioned runtime JSON/cache data. The tool should be able to configure a
project in a clean runtime environment using only repository assets, the target
project, and configured vendor validation tools.

## Changelog

- 2026-05-30 v0.1.1: Standardized archive metadata and added changelog.
- 2026-05-30 v0.1.0: Archived second-round reviewed source-materials draft.
