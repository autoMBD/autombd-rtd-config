# RTD Configuration Test Strategy

Version: 0.2.0
Date: 2026-05-30
Author: autoMBD <tkung.lqk@foxmali.com>
Authoring note: AI-assisted test strategy prepared through human review.

## Purpose

This document defines the maintainable testing process for the RTD
configuration tool. It applies to every backend, module, and set feature.

The spec defines project goals. This document defines test cases, validation
workflow, independent subagent validation, and KPI expectations.

## Test Layers

1. Fast deterministic tests
   Run without vendor tools. They cover intent validation, command
   normalization, resource lookup, document indexing, localized edits, provider
   ownership boundaries, planning, diagnostics, and validation command building.

2. Fixture integration tests
   Run on real vendor project fixtures. They apply configuration changes to the
   fixture project and verify the modified project structure.

3. Vendor headless validation
   Runs the configured vendor validation tool without a visible GUI window on
   the modified fixture project. This is the authority for backend acceptance.

4. Independent subagent validation
   A separate subagent validates fixture integration tests and vendor headless
   validation cases using only the public tool interface, companion skills, test
   input, and repository-visible instructions. Fast deterministic tests are
   normally run by the main development agent during implementation.

## Fixture Structure

Fixtures use a backend/family/device/scenario structure:

```text
fixtures/
  projects/
    <backend>/
      <family>/
        <device>/
          <scenario>/
```

Each fixture must include files required for vendor validation. Build outputs,
debug folders, generated binaries, logs, and temporary artifacts must stay out
of source control unless a test explicitly requires a small static fixture.

## Test Case Template

Each test case should be recorded with this structure:

```text
ID:
Backend:
Family:
Device:
RTD version:
Module(s):
Scenario:
Input fixture:
Request type: JSON intent | shortcut command
Preconditions:
Command(s):
Expected plan:
Expected changed modules:
Expected static check result:
Expected vendor validation result:
Expected diagnostics:
KPI target:
Subagent validation required:
```

## Required Coverage Categories

Every implemented module or set feature must have tests for:

- valid configuration;
- invalid or missing resources;
- dependency resolution;
- ownership boundaries;
- static diagnostics;
- vendor validation result when the backend supports validation;
- shortcut command normalization when a shortcut exists;
- JSON intent path.

Backend test documents should add concrete test cases for specific modules and
milestones.

## Independent Subagent Validation

Key test cases must be validated by independent subagents.

Subagent validation requirements:

- each subagent call must set `"fork_context": false`;
- with `"fork_context": false`, the subagent is fully independent from the main
  agent and has isolated context;
- the subagent must not see the main agent's analysis, implementation details,
  hidden assumptions, or debugging process;
- the subagent should rely only on the user requirement, test-case
  instructions, repository files, companion skills, and the public tool
  interface;
- each subagent should validate one focused test case whenever practical.

Independent subagent validation targets the integration and vendor validation
layers. The main development agent may run fast deterministic tests during
implementation, but those fast checks do not replace independent validation of
fixture edits and vendor headless results.

## KPI

The KPI applies to all module configuration flows:

- each independent subagent validation of one focused test case must complete
  within 3 minutes;
- the ideal path is: understand the requirement, infer or use the provided
  intent, call the tool, and pass validation once;
- repeated KPI misses indicate a problem in the public interface, diagnostics,
  runtime performance, fixture design, or test-case wording.

## Acceptance Rule

A module or feature is accepted when:

- required test cases pass;
- vendor validation passes when applicable;
- focused independent subagent validation meets the KPI;
- failures produce actionable diagnostics rather than tracebacks or ambiguous
  logs.

## Changelog

- 2026-05-30 v0.2.0: Clarified independent subagent validation scope.
- 2026-05-30 v0.1.0: Created RTD configuration test strategy.
