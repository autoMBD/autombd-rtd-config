# RTD Configuration Tool Core Design

Version: 0.2.1
Date: 2026-05-30
Author: autoMBD <tkung.lqk@foxmali.com>
Authoring note: AI-assisted design document prepared through human review.

## Overview

The RTD Configuration Tool is a CLI-first configuration system for RTD projects.
It prepares deterministic runtime data, accepts structured configuration
requests, edits vendor project files through backend-specific document cores,
and verifies results through static checks and vendor validation. Companion
Agent Skills are part of the deliverable so AI agents can discover the tool,
translate user requests into intents or shortcut commands, run validation, and
interpret diagnostics without reading implementation code.

## Contents

- [Purpose](#purpose)
- [Goals](#goals)
- [Supported Configuration Backends](#supported-configuration-backends)
- [Architecture](#architecture)
- [Backend Document Core](#backend-document-core)
- [Module Capability Model](#module-capability-model)
- [Resource And Constraint Data](#resource-and-constraint-data)
- [Intent And Commands](#intent-and-commands)
- [Runtime Configuration](#runtime-configuration)
- [Diagnostics](#diagnostics)
- [Validation Pipeline](#validation-pipeline)
- [Performance Requirements](#performance-requirements)
- [Fixtures](#fixtures)
- [Tests And Acceptance](#tests-and-acceptance)
- [Suggested Project Structure](#suggested-project-structure)
- [Success Criteria](#success-criteria)

## Purpose

This project builds a deterministic RTD configuration tool that AI agents can
use directly to configure low-level driver software quickly, efficiently,
accurately, and reliably.

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
- Support completion of missing configuration and creation of new configuration
  files through prepared runtime templates when those capabilities are planned
  for the relevant backend.
- Provide companion Agent Skills that explain how agents should use the tool,
  prepare intents, run commands, validate results, and react to diagnostics.
- Treat vendor validation as the authority after tool edits.
- Keep specs, module capability tables, references, test cases, and roadmaps
  maintainable and updateable.

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

2. Agent Skills layer
   Provides repository skills that teach AI agents how to select workflows,
   convert user requests into intents or shortcut commands, call the CLI, run
   validation, and interpret JSON diagnostics. Skills are documentation and
   workflow adapters over the public CLI; they must not bypass the CLI contract
   or depend on private implementation details.

3. Intent and plan layer
   Loads JSON intent or shortcut command arguments, normalizes requests, checks
   constraints, resolves dependencies, and produces deterministic plans before
   writes.

4. Backend document core
   Parses backend project files, builds efficient indexes, provides structured
   editing helpers, performs localized writes, and keeps diffs reviewable.

5. Module providers
   Each module owns its own planning and apply logic. Providers publish their
   supported actions, dependencies, constraints, resources, and tests through a
   maintainable module capability table.

6. Shared resource services
   Provide pin mapping, schema/cache access, references, constraints,
   diagnostics, validation command construction, runtime configuration loading,
   and performance instrumentation.

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

Module responsibilities are maintained in a separate capability table rather
than embedded only in this spec. The active table is:

`docs/superpowers/specs/rtd-config-module-capabilities.md`

The table is the maintainable index for module ownership, dependencies,
supported actions, constraints, runtime data, shortcut mappings, and test
coverage. It must be updated whenever a new RTD module or set feature is added.

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

Independent subagent validation is black-box validation of the delivered tool
and companion skills. The subagent must not receive main-agent context,
implementation notes, hidden assumptions, or development text. It uses only the
public deliverables, test input, repository-visible instructions, and public CLI
to complete the assigned validation target.

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
.skills/
  rtd-config/
    <agent-facing workflow skills>
data/
fixtures/
tests/
docs/
  superpowers/
    specs/
      rtd-config-module-capabilities.md
    references/
    tests/
    roadmaps/
```

## Success Criteria

The project is successful when:

- core CLI commands return stable JSON;
- companion Agent Skills guide AI agents through tool usage without relying on
  private implementation details;
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

- 2026-05-30 v0.2.1: Standardized document metadata and added changelog.
- 2026-05-30 v0.2.0: Integrated second-round review updates and Agent Skills architecture.
- 2026-05-30 v0.1.0: Created initial RTD configuration core design.
