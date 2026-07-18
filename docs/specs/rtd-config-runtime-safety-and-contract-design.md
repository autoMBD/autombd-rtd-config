# RTD CfgFile CLI Runtime Safety and Contract Design

| Field | Value |
| --- | --- |
| Version | 0.1.1 |
| Date | 2026-07-18 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Defines project identity, asset compatibility, stable diagnostics, secure configuration transactions, provider ownership enforcement, descriptor inventory, and release integrity for the RTD CfgFile CLI. |

## 1. Purpose

This document refines the long-term architecture in
`rtd-config-core-design.md` at the runtime trust boundaries where external
project data, committed assets, configuration edits, vendor processes, and the
released Skill meet.

The design has four invariants:

1. project identity is observed from a verified project snapshot, never
   manufactured from runtime defaults;
2. every public command returns one stable diagnostic result for expected
   user, project, asset, and environment failures;
3. an edit is published only when the target is still the file that was loaded
   and every actual byte change belongs to a declared provider owner;
4. runtime payload completeness and descriptor-surface accounting are
   machine-verifiable committed contracts.

## 2. Scope and non-goals

### 2.1 In scope

- S32 ConfigTools `.mex` project identity and compatibility parsing;
- exact asset-bundle selection by vendor, backend, family, device, package,
  RTD release, schema, tool versions, and module compatibility;
- stable JSON diagnostics across every public CLI failure path;
- path containment, reparse-point rejection, file snapshots, and transactional
  `.mex` writes;
- read-only vendor validation and contained process/temp lifecycle;
- registry-bound provider plan/apply ownership and actual-change auditing;
- canonical generic intent commands plus module shortcut adapters;
- JSON runtime configuration and deterministic precedence;
- descriptor inventory and coverage sidecars outside the released runtime
  assets;
- single-source version metadata, release manifest verification, and CI.

### 2.2 Non-goals

- adding support for an unverified device, package, RTD release, or schema;
- treating the presence of an RTD `.epd` file as proof that a configuration
  combination is supported;
- reading raw `.xdm` or `.epd` files at runtime;
- changing legal module values based on test-case literals;
- replacing S32DS as the vendor authority for `.mex` validity.

## 3. Requirements traceability

| Requirement | Architectural response |
| --- | --- |
| Project processor/package/RTD mismatch must fail closed | Verified `ProjectSnapshot`, parsed `ProjectMetadata`, exact `AssetBundleResolver`, and a compatibility gate before plan/apply/validation |
| JSON failures must never leak expected tracebacks | One top-level command boundary, typed failures, stable diagnostic codes, explicit debug mode |
| `.mex` symlink/path escape/TOCTOU must be rejected | Canonical containment, reparse rejection, same-read parsing, file identity plus SHA-256, pre-commit compare-and-swap |
| Validation must be read-only and clean up safely | Static-first short circuit, controlled staging, process-tree runner, explicit cleanup outcome, no default project log |
| Provider ownership must be enforced | Unique `ProviderBinding` registry, allowed physical regions, immutable before snapshot, actual byte-delta audit |
| Public CLI and runtime config must match the core design | Generic intent commands are canonical; shortcuts normalize to the same dispatcher; flags override JSON config |
| Version and release metadata must not drift | `pyproject.toml` authority, generated/checked release manifest, clean-directory deployment smoke tests |
| Descriptor coverage gaps must be impossible to hide | Deterministic descriptor inventory, non-runtime coverage sidecars, complete classification gate |

## 4. End-to-end architecture

```text
argv + JSON config
    -> command boundary / argument normalization
    -> secure project location
    -> ProjectSnapshot(bytes + identity + hash)
    -> ProjectMetadata parser
    -> AssetBundleResolver(exact compatibility match)
    -> Intent normalization
    -> ProviderBinding registry
    -> plan(declared owners and dependencies)
    -> backend apply into an in-memory/staged document
    -> actual byte-delta ownership audit
    -> static checks
    -> optional vendor validation in controlled staging
    -> target compare-and-swap verification
    -> atomic publish
    -> stable result JSON
```

Read-only commands stop at the earliest layer that satisfies their contract.
`inspect` reports observed metadata and compatibility diagnostics. `plan` stops
before apply. `check` never launches S32DS. `validate` never publishes project
changes. `configure` is the only command that may publish a `.mex` edit.

## 5. Verified project identity

### 5.1 `VerifiedProjectTarget`

Secure project location produces an immutable target containing:

- canonical project root and `.mex` path;
- proof that the root is a directory and the `.mex` is a regular file;
- canonical containment of the `.mex` within the root;
- rejection evidence for symbolic links, junctions, mount/reparse points, and
  resolved-path escape;
- platform file identity (`st_dev/st_ino` where reliable; Windows volume/file
  identifier through a handle-capable adapter);
- size and timestamps as diagnostic evidence, never as the sole identity;
- SHA-256 and the exact bytes read.

The XML tree is parsed from the captured bytes. The loader must not read bytes
and then reopen the path for a second parse.

### 5.2 `ProjectMetadata`

The `.mex` backend parses and normalizes:

- vendor and backend;
- processor, family, device, raw package, canonical package, and MCU data;
- XML namespace, schema version, and schema location;
- enabled ConfigTools with names and versions;
- enabled module names, types, identifiers, and modes;
- published AUTOSAR/software version fields when present;
- SDK/RTD release from project attachment evidence;
- conflicts among `.mex`, `.settings`, and project metadata sources.

Missing facts remain `unknown`; they are never filled from `RuntimeConfig`.
An exact asset manifest may define which unknown fields are tolerated for a
specific supported combination. Conflicting facts are blockers.

### 5.3 Initial supported combination

The existing vendor-validatable fixtures establish the initial exact bundle:

- NXP S32 ConfigTools `.mex`;
- S32K3 / S32K344 / `S32K344_257BGA` (`mapbga257`);
- RTD 7.0.1;
- root schema 19;
- the tool and module versions explicitly recorded by the project and bundle
  manifest.

Other packages or releases remain unsupported until they have a complete
asset bundle, a compatible fixture, and vendor-gate evidence. An unknown
combination must never fall back to MAPBGA257 data.

## 6. Asset bundle compatibility

### 6.1 Bundle manifest

A committed manifest identifies one runtime bundle by:

```text
vendor / backend / family / device / package / RTD release /
schema range / tool versions / module compatibility
```

It also lists the module assets and the package-specific pin field. Asset
files contain runtime data only. Each asset's embedded identity, when present,
must agree with the bundle manifest.

### 6.2 Resolution rules

- exactly one compatible bundle is required;
- zero matches produce `asset_bundle_unsupported`;
- multiple matches produce `asset_bundle_ambiguous`;
- missing, malformed, or identity-mismatched files produce stable asset
  diagnostics;
- providers receive an already-resolved bundle and do not construct fixed
  paths from `__file__`;
- `pin-options` requires a complete explicit tuple when no project is supplied
  and filters out records without a value for the selected package.

`RuntimeConfig` can select an asset root but cannot override observed project
identity to force a mismatch to appear compatible.

## 7. Stable command diagnostics

### 7.1 Result contract

Every public command returns:

```json
{
  "status": "passed | failed | blocked",
  "command": "inspect | plan | configure | check | validate | pin-options | ...",
  "diagnostics": [
    {
      "severity": "info | warning | error | blocker",
      "code": "stable_machine_code",
      "module": "optional module",
      "message": "actionable summary",
      "details": {}
    }
  ]
}
```

Expected failures include argument/spec errors, missing or ambiguous projects,
malformed XML, permission failures, unsafe paths, target changes, missing or
invalid assets, unsupported compatibility tuples, staging failures, vendor
timeouts, and cleanup failures.

### 7.2 Exception boundary

- argument parsing participates in the same JSON boundary;
- JSON mode is detected from raw argv before full parsing;
- typed domain failures map to stable diagnostics and exit codes;
- an unknown `Exception` maps to `internal_error` without a traceback by
  default;
- `--debug` may emit a traceback to stderr while stdout remains valid JSON;
- `KeyboardInterrupt` and process termination signals are not swallowed.

## 8. Secure configuration transaction

`ConfigureTransaction` owns load-to-publish state:

1. capture the verified target and immutable before bytes;
2. parse metadata and resolve assets;
3. plan declared owners/dependencies;
4. apply in memory and render a same-filesystem staging file;
5. compute actual byte deltas and physical touched regions;
6. reject undeclared ownership;
7. run static checks on staging;
8. optionally run vendor validation against controlled copies;
9. revalidate target path, reparse status, file identity, and SHA-256;
10. publish with atomic replace;
11. clean staging and report any cleanup failure.

The transaction fails closed if the IDE or another process changes the target
after load. The diagnostic instructs the caller to reload and retry.

Backup creation is part of the transaction. Existing backup links/reparse
points are rejected, and backup failure prevents publication.

## 9. Read-only vendor validation

Validation has a separate lifecycle:

```text
verified snapshot
    -> static checks
    -> blocker: return without vendor launch
    -> controlled staging under configured temp base
    -> no-follow project copy policy
    -> S32DS process-tree execution
    -> bounded stdout/stderr collection
    -> gate evaluation
    -> cleanup or retained-path diagnostic
```

Default validation writes nothing into the real project. Logs are returned in
the result with bounded size. A file is written only when the user supplies an
explicit, safely validated log-output path.

On timeout, the runner terminates and waits for the complete process tree. On
Windows it uses Job Object semantics or an equivalently tested tree-control
adapter. Cleanup failure returns `validation_cleanup_failed` and a retained
path inside the configured safe temp base; it is never silently ignored.

## 10. Provider registry and ownership audit

### 10.1 `ProviderBinding`

The unique registry key is `(backend, module, action)`. Each binding contains:

- provider planner;
- backend apply operation;
- statically allowed physical regions;
- rules that derive conditional cross-module dependencies from the plan;
- supported asset capability identifiers.

Module shortcuts and generic intent commands use the same registry lookup.
There is no second CLI-side plan/apply pairing table.

### 10.2 Actual change evidence

The backend document core retains immutable before bytes and records every raw
splice or attribute update. After render it produces:

- byte offsets and before/after hashes for changed spans;
- logical module/tool regions mapped from those spans;
- actual touched modules;
- empty evidence for a no-op.

Publication requires:

```text
actual touched regions subset of plan-declared owners/dependencies
plan-declared owners/dependencies subset of binding-allowed ownership
```

`changed_modules` is derived from this audit. Apply code cannot self-report a
module change as authoritative evidence.

## 11. Public CLI and runtime configuration

### 11.1 Canonical API

The stable core commands are:

- `plan --project <p> --intent <intent.json> --json`;
- `configure --project <p> --intent <intent.json> --json`.

The canonical intent envelope is:

```json
{
  "module": "uart",
  "action": "set",
  "payload": {}
}
```

Module shortcuts remain supported for compatibility and ergonomics. They
normalize immediately to the same envelope and dispatcher. Equivalent generic
and shortcut requests must produce identical plans, bytes, and diagnostics.

### 11.2 Runtime configuration

Configuration precedence is deterministic:

```text
built-in defaults < JSON config file < explicit CLI flags
```

Runtime configuration covers backend, project, S32DS/SDK roots, workspace,
validation timeout, temp/log output paths, and asset root. The default asset
root is resolved from the deployed Skill, independent of current working
directory.

Family/device/package/RTD fields in configuration are expected constraints for
projectless resource queries or compatibility assertions. They do not replace
observed project metadata.

## 12. Normalized descriptor coverage definitions

### 12.1 Storage boundary

Each runtime asset remains an independent released input. Development coverage
data is not runtime input and must not be published in the released Skill
assets. Each module has a single normalized development coverage definition:

```text
docs/specs/rtd-config-module-coverage/<module>.json
```

These definitions are project engineering specifications. Runtime code does not
read them, and the release manifest excludes them. There is no separate
classification-overrides file or directory.

### 12.2 Inventory format

Each normalized definition records:

- module, RTD release, descriptor package, descriptor SHA-256, and extraction
  format version;
- every editable descriptor item under a stable structural key as exact,
  fact-only extraction data;
- kind (`container`, `variable`, `reference`, `list`, or equivalent descriptor
  construct);
- type/domain/range/default when defined;
- `INVALID`, `EDITABLE`, and `ENABLE` constraints;
- cross-module references;
- a SHA-256-addressed fact pool that interns repeated descriptor domains,
  ranges, defaults, and constraints with collision verification;
- embedded `classification_default`, `classification_rules`, and
  `known_gap_rules`;
- implementation/asset traces in rules for configurable or derived items;
- reason and dependency rules for deferred items.

The tool expands fact references and applies those rules to create a resolved
coverage view in memory, or as explicitly requested temporary output. Resolved
per-item classification, trace, summary, and known-gap lists are never committed.

An asset trace proves semantic domain consistency only when its rule declares
an asset-domain assertion with a named descriptor fact and precise JSON Pointer.
Mode `exact` requires ordered value equality; mode `subset` requires every asset
value to belong to the descriptor fact. The contract therefore selects either
`exact` or `subset` explicitly. Structural and template traces do not imply a
domain assertion.

Mcu and Adc inventories are regenerated from the exact cached descriptors.
The extraction includes the known missing Mcu reset surfaces and Adc DSPSS,
self-test, timing, general, power-state, published-information, and AUTOSAR
extension surfaces; the descriptor, not this list, defines completeness.

### 12.3 Inventory gate

The deterministic gate verifies:

- inventory keys are unique and stable;
- every extracted editable descriptor item appears exactly once;
- materialization gives every inventory item exactly one classification;
- configurable/derived traces resolve to committed implementation/assets;
- deferred items have a non-empty engineering reason;
- descriptor identity and SHA-256 match regeneration evidence when the source
  descriptor is available;
- runtime assets contain no `_coverage` key;
- every declared asset-domain assertion passes its exact/subset comparison;
- the release manifest contains no development coverage definition.

CI validates committed inventory/classification consistency without requiring
an RTD installation. Descriptor regeneration and source-hash comparison are a
development-time verification step.

## 13. Version, release manifest, and CI

### 13.1 Version authority

`pyproject.toml [project].version` is authoritative. A deterministic checker
requires equality with:

- Skill frontmatter version;
- launcher header version;
- package `__version__` and header version;
- release manifest version.

### 13.2 Release manifest

The committed manifest contains format version, release version, and every
published file path plus SHA-256. It excludes itself from the hash list.
Deployment copies only manifest-declared files, verifies staging completely,
then transactionally switches the installed Skill.

Missing files, hash mismatches, unapproved extra files, or same-version content
drift prevent a false completeness result.

### 13.3 CI contract

CI covers:

- the deterministic suite on Python 3.11, 3.12, 3.13, and 3.14;
- version and release-manifest checks;
- clean-directory deployment and installed-payload verification;
- launcher/help/resource smoke tests from a working directory outside the
  repository;
- Windows and Linux deployment smoke coverage.

S32DS validation and isolated black-box acceptance remain separate because
hosted CI does not contain the licensed/local vendor environment.

README status uses the real workflow badge and links dated recorded acceptance
evidence rather than asserting an unqualified permanent green state.

## 14. Compatibility and migration

- existing module shortcuts remain valid;
- a raw shortcut spec remains accepted only at the shortcut boundary and is
  normalized to the canonical envelope;
- unsupported project combinations change from unsafe fallback/pass behavior
  to actionable blockers;
- default validation no longer creates `build/configtools_validation.log`;
- `_coverage` disappears from runtime assets and moves to committed sidecars;
- version synchronization may bump the released Skill version once after all
  payload changes are finalized;
- shared CLI/apply/Skill changes require fresh acceptance evidence for every
  affected module case.

## 15. Verification strategy

### 15.1 Deterministic tests

Mandatory tests cover:

- project metadata parsing and all mismatch/unknown combinations;
- exact asset resolution and package-specific pin filtering;
- every expected JSON failure, parser placement, and debug behavior;
- real and injected Windows link/reparse/path-escape cases;
- same-read XML parsing, identity/hash changes, and transaction failure points;
- validation byte-identical project manifests, static short circuit, cleanup,
  and process-tree timeout;
- registry completeness, no-op results, declared dependencies, and a
  deliberately undeclared edit;
- generic/shortcut equivalence and runtime-config precedence;
- descriptor inventory accounting and absence of runtime `_coverage`;
- version equality, release-manifest drift, and clean deployment.

### 15.2 Runtime and acceptance tests

- static checks must pass or correctly block invalid input;
- S32DS passes only with exit code `0` and no SEVERE `[TOOL]` resource problem;
- all affected `RTD-MEX-*` cases run through `tools/blackbox_e2e.py` with temp
  artifacts under `tests/.tmp/`;
- the vendor gate is independently rerun against every produced `.mex`;
- the acceptance report records fresh functional and timing evidence.

## 16. Key risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Windows check-to-replace race remains after stat/hash | Use a handle-capable platform adapter and tests that exercise replacement attempts; always fail closed on uncertainty |
| Existing fixtures expose schema 19 while stale documentation mentions schema 18 | Treat observed fixture metadata and explicit bundle compatibility as authoritative; do not hard-code one global schema constant |
| HDQFP172/LQFP100 RTD descriptors are present but project support is unproven | Keep them unsupported until complete assets, fixtures, and vendor evidence exist |
| Central apply code makes physical ownership mapping difficult | Introduce the registry and audit journal before generic dispatch; preserve narrow-write tests throughout |
| Descriptor inventories are large and manually error-prone | Generate stable inventories deterministically and review classifications, never transcribe nodes by hand |
| Release manifest churn during implementation | Generate the final manifest only after runtime payload and documentation changes settle; CI checks drift afterward |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-07-18 | 0.1.1 | Replaced expanded coverage sidecars plus separate overrides with one normalized per-module development definition, pooled exact descriptor facts, in-memory resolved views, embedded rules, and explicit exact/subset asset-domain assertions. |
| 2026-07-12 | 0.1.0 | Initial runtime-safety and public-contract design covering project identity, stable diagnostics, secure transactions, validation containment, provider ownership, generic intent, descriptor inventory, and release integrity. |
