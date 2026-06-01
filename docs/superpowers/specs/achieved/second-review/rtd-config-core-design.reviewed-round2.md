# RTD Configuration Tool Core Design

> Archive status: unavailable for requirements. This reviewed draft is kept
> only for comment traceability. Do not read or use it to infer current
> behavior, terminology, scope, architecture, test requirements, or acceptance
> criteria. Use only active documents outside `docs/superpowers/specs/achieved/`.

| Field | Value |
| --- | --- |
| Version | 0.1.3 |
| Date | 2026-05-30 |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | Archives the second reviewed design draft with inline comments preserved. |

<!-- REVIEW: 添加版本、时间、作者（作者是autoMBD<tkung.lqk@foxmali.com>，可以添加说明有AI辅助）overview description -->
<!-- REVIEW: 添加目录 -->

## Purpose

This project builds a deterministic RTD configuration tool that AI agents can
use directly to configure low-level driver software quickly, efficiently,
accurately, and reliably.

<!-- REVIEW: 还有一个很重要的需求没有提，既然是面向AI Agent的工具，一定要配有相关skills文件，让AI Agent可以使用该工具，这也非常重要，必须设计到架构中 -->
<!-- REVIEW: 添加说明配套的Skills帮助AI agents使用该工具 -->

The tool's long-term target is to support the full RTD configuration surface:
driver modules, official RTD RTOS integration, stacks, and supported external
peripheral driver configuration. It must support S32 ConfigTools `.mex`
projects and be extensible to EB tresos configuration projects. It must also be
extensible across S32K families such as K3, K1, and K5, across RTD releases,
and across new modules added over time.

The stable external contract is a CLI that accepts structured requests and
emits stable JSON. Internal Python modules should be clear and testable, but
the CLI/JSON contract is the first compatibility boundary.

This document describes the project and architecture. Milestone order, staged
feature limits, and delivery sequencing belong in the roadmap and
implementation plan. Development workflow and agent validation discipline belong
in the testing and development-process documents.

## Goals

- Enable AI agents to configure RTD projects without hand-editing vendor XML.
- Keep configuration deterministic and repeatable for a given project, data
  cache, tool version, and request.
- Make routine commands fast enough for repeated autonomous use.
- Keep runtime dependencies minimal and predictable.
- Separate development-time source material from runtime assets.
- Preserve module ownership boundaries so new modules and set features can be
  added without entangling existing providers.
- Treat vendor validation as the authority after tool edits.
- Keep specs, module capability tables, references, test cases, and roadmaps
  maintainable and updateable.

<!-- REVIEW: 配置空缺补充和从零创建配置文件也是目标 -->
<!-- REVIEW: 补充Agent Skills -->

## Supported Configuration Backends

The architecture supports multiple configuration backends through backend
providers. Each backend provider owns its file model, validation integration,
and backend-specific write strategy.

| Backend | Configuration format | Primary use |
| --- | --- | --- |
| S32 ConfigTools | `.mex` | S32DS ConfigTools projects |
| EB tresos | `.xdm` and related EB project files | EB tresos projects |

S32 ConfigTools `.mex` is the first backend to implement. EB tresos support
must reuse the same intent, planning, diagnostics, resource cache, module
capability, and testing concepts where practical, while using its own document
model and writer.

## Architecture

Use a modular configuration core with a CLI shell.

The architecture has these layers:

1. CLI layer
   Provides core commands and module shortcut commands. Shortcut commands only
   build normalized intent and then use the same plan/apply/check/validate
   pipeline.

2. Intent and plan layer
   Loads JSON intent or shortcut command arguments, normalizes requests, checks
   constraints, resolves dependencies, and produces deterministic plans before
   writes.

3. Backend document core
   Parses backend project files, builds efficient indexes, provides structured
   editing helpers, performs localized writes, and keeps diffs reviewable.

4. Module providers
   Each module owns its own planning and apply logic. Providers publish their
   supported actions, dependencies, constraints, resources, and tests through a
   maintainable module capability table.

5. Shared resource services
   Provide pin mapping, schema/cache access, references, constraints,
   diagnostics, validation command construction, runtime configuration loading,
   and performance instrumentation.

<!-- REVIEW: 在架构中写明配套的Agent Skills -->

Two architecture rules are mandatory:

- A module provider may only write the configuration area it owns.
- Shared concerns such as document editing, pin mapping, diagnostics,
  schema/cache, constraints, references, and validation must live in core/shared
  layers, not inside individual module implementations.

Cross-module dependencies are explicit plan relationships. For example, a Uart
request may require Port pins, Mcu clocks, Mcl FlexIO resources, and Platform
interrupts. Uart may declare those requirements, but the owning providers must
plan and apply their own edits.

## Backend Document Core

The document core must be efficient and backend-specific.

For `.mex` projects, the document core should:

- parse project XML and build only the indexes needed by the current command;
- avoid scanning unrelated large subtrees where a targeted index is sufficient;
- allow the indexing strategy to evolve after measuring real project sizes;
- provide setting/container lookup and upsert helpers;
- keep localized edits small enough for review;
- avoid broad whole-file rewrites;
- expose diagnostics instead of raw parser or Python tracebacks.

For EB tresos projects, the `.xdm` writer should follow the same concepts:
structured parsing, targeted indexes, localized edits, explicit constraints,
and stable diagnostics. EB-specific details belong in the EB backend design when
that backend is planned.

## Module Capability Model

Module responsibilities are maintained in a capability table rather than
embedded only in prose. The table must be easy to extend when a new RTD module
or set feature is added.

| Module | Ownership | Key dependencies | Capability direction |
| --- | --- | --- | --- |
| Mcu | Clock and MCU configuration owned by Mcu | Resource requests from drivers and stacks | Clock references, peripheral clocks, mode/clock settings |
| BaseNXP | BaseNXP global configuration | Platform and driver timing needs | Available BaseNXP parameters, OsIf, timer basis |
| Platform | Platform and interrupt configuration | Interrupt-driven drivers | Interrupt controller, IRQ enablement, priority, handler/vector basics |
| Port | Pin mux and pad configuration | Any module needing pins | Generic pin configuration from versioned pin mapping |
| Dio | Dio ports and channels | GPIO users and external peripheral control | Generic port/channel configuration and uniqueness checks |
| Mcl | Mcl and FlexIO resources | FlexIO users and future DMA/resource users | FlexIO common, channels, timers, shifters, shared resources |
| Uart | Uart channels and Uart parameters | Mcu, Port, Platform, Mcl as needed | LPUART, FlexIO Uart, polling/interrupt, communication parameters |

<!-- REVIEW: 这个表放到一个单独的文件里才好维护，Spec简明它的作用，并指向该表的位置和。 -->

The capability table must support:

- supported actions;
- owned paths or owned configuration regions per backend;
- dependencies and dependency direction;
- constraints and resource limits;
- data/cache files used at runtime;
- shortcut command mappings;
- tests and validation cases.

Different devices and RTD releases can impose different limits, such as
available pins, peripheral counts, interrupt names, and valid enum values. Those
constraints must come from prepared runtime cache data, not from ad hoc code or
runtime vendor-directory scans.

## Resource And Constraint Data

Runtime data is committed as versioned JSON/cache files. Runtime commands must
not require development source material such as Excel workbooks or installed
RTD package files.

Data assets include:

- module manifests and capability metadata;
- schema/constraint cache extracted from vendor configuration descriptions;
- pin mapping by family, device, package, peripheral, signal, and pin;
- validation profiles;
- known generated-file and reference patterns when needed.

Suggested structure:

```text
data/
  s32k/
    families/
      s32k3/
        devices/
          s32k344/
            packages/
              <package>/
                pins.json
            rtd/
              7_0_1/
                schemas/
                modules/
```

Development-time source documents are described in a separate references
document. The spec only defines what kinds of source material are needed:

- pin mux references;
- RTD module `.xdm` or equivalent constraint descriptions;
- ConfigTools project examples;
- vendor validation command references;
- RTD release/package metadata.

The build process may use these materials to create runtime JSON/cache assets.
The runtime tool must only load the prepared assets.

## Intent And Commands

JSON intent is the core request format. Shortcut commands are convenience
wrappers that normalize into the same intent model.

Core commands:

```powershell
rtd-config inspect --project <project> --json
rtd-config plan --project <project> --intent intent.json --json
rtd-config configure --project <project> --intent intent.json --json
rtd-config check --project <project> --json
rtd-config validate --project <project> --json
rtd-config pin-options --device <device> --package <package> --peripheral <peripheral> --json
```

Shortcut commands follow module groupings:

```powershell
rtd-config uart set ...
rtd-config port set-pin ...
rtd-config dio set-channel ...
rtd-config mcu set-clock ...
rtd-config platform set-irq ...
rtd-config basenxp set ...
rtd-config mcl set-flexio ...
```

The CLI must remain non-interactive for automation. Users who need review
should run `plan` before `configure`.

## Runtime Configuration

Use repository or workspace JSON configuration files for default paths and
settings. CLI parameters may override JSON values.

Configuration should cover:

- backend selection;
- S32DS or EB tresos tool roots;
- workspace path;
- default project path when useful;
- default family, device, package, and RTD version;
- runtime data/cache locations;
- validation timeout;
- validation log directory.

The format is JSON to avoid runtime dependencies beyond the Python standard
library.

## Diagnostics

All commands return stable JSON diagnostics:

```json
{
  "status": "passed|failed|blocked",
  "command": "configure",
  "diagnostics": [
    {
      "severity": "blocker|error|warning|info",
      "code": "missing_pin_mapping",
      "module": "port",
      "message": "Pin PTA15 is not available for the requested package/function.",
      "details": {}
    }
  ]
}
```

Diagnostics must be actionable. They should identify the module, invalid or
missing resource, constraint that failed, and useful details for correction.

## Validation Pipeline

`configure` runs the same high-level pipeline for every backend:

1. load runtime configuration;
2. load and index the project through the backend document core;
3. normalize intent;
4. resolve dependencies and constraints;
5. plan;
6. apply owned edits;
7. run static checks;
8. run backend vendor validation when configured;
9. return changed modules, diagnostics, validation logs, and status.

S32 ConfigTools validation requirements:

- headless execution without a visible GUI window;
- configurable timeout;
- stdout/stderr/log capture;
- JSON result with command, resolved paths, exit code, and log paths;
- clear failure diagnostics.

EB tresos validation should follow equivalent principles once that backend is
introduced.

## Performance Requirements

Commands must be efficient enough for autonomous agent use.

- Runtime commands must not scan RTD installation directories.
- Runtime commands must not read Excel or other development-only source files.
- Inspect, plan, check, and resource-query commands must not launch vendor
  tools.
- A single command should parse/index each project file only as needed and
  reuse indexes across providers.
- Runtime module and resource knowledge must come from committed JSON/cache
  assets.
- The tool must expose enough timing information to identify slow indexing,
  planning, writing, or validation steps.
- If runtime `.mex` parsing or indexing becomes too slow on real projects, the
  document core must support replacing broad indexing with measured targeted
  indexes or prepared project summaries.

## Fixtures

Fixtures use a generic structure. Each fixture is a real vendor project for a
specific backend, device, RTD version, and module scenario.

```text
fixtures/
  projects/
    <backend>/
      <family>/
        <device>/
          <scenario>/
```

Fixtures must include the files required for vendor validation and exclude
build/debug/generated artifacts that do not belong in source control.

Specific fixture scenarios are documented in the test strategy, not in this
spec.

## Tests And Acceptance

The spec requires maintainable test documentation. Test cases, module-specific
test steps, staged coverage, and subagent validation process belong in the test
strategy document.

<!-- REVIEW: 这里要简要说明Subagent是独立测试，不获取任何main agent上下文信息，不输入任何开发文本，仅根据工具deliverables（skills和工具本身），根据测试输入，完成测试目标 -->

Acceptance is based on two criteria:

- the required test cases pass;
- the KPI for focused module configuration validation is met.

The KPI applies to all module configuration flows: an independent validator
should be able to understand a focused test case, use the public tool
interface, and complete validation within 3 minutes. Repeated KPI failures mean
the interface, diagnostics, performance, or test design must be improved.

## Suggested Project Structure

```text
rtd_config/
  __main__.py
  cli.py
  config.py
  diagnostics.py
  intent.py
  plan.py
  backends/
    base.py
    s32_mex/
      document.py
      index.py
      edit.py
      writer.py
      validation.py
    eb_tresos/
      document.py
      index.py
      edit.py
      writer.py
      validation.py
  modules/
    base.py
    mcu.py
    basenxp.py
    platform.py
    port.py
    dio.py
    mcl.py
    uart.py
  resources/
    pins.py
    schema.py
    constraints.py
  checks/
    static.py
data/
fixtures/
tests/
docs/
  superpowers/
    specs/
    references/
    tests/
    roadmaps/
```

## Success Criteria

The project is successful when:

- core CLI commands return stable JSON;
- shortcut commands normalize to the same intent pipeline;
- backend document cores can configure vendor projects through structured,
  localized edits;
- module providers preserve ownership boundaries;
- dependencies between modules are explicit in plans;
- constraints come from prepared runtime data assets;
- runtime commands avoid development-only source files and vendor-directory
  scans;
- static and vendor validation diagnostics are actionable;
- module capability tables, references, tests, and roadmaps remain maintainable;
- required test cases pass;
- focused validation meets the 3-minute KPI.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-05-30 | 0.1.3 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.1.2 | Renamed second-round reviewed design draft to remove date from filename. |
| 2026-05-30 | 0.1.1 | Standardized archive metadata and added changelog. |
| 2026-05-30 | 0.1.0 | Archived second-round reviewed design draft with inline comments. |
