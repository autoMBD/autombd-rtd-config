# RTD CfgFile CLI Runtime Safety and Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved runtime-safety and public-contract architecture so project/asset mismatches, CLI failures, unsafe writes, validation side effects, provider ownership violations, descriptor gaps, and release drift fail closed.

**Architecture:** Build shared typed-failure, verified-project, bundle-resolution, transaction, ownership, and dispatch boundaries before adapting commands. Keep raw descriptors development-only, move coverage to non-runtime sidecars, and finish with a manifest-driven release plus CI.

**Tech Stack:** Python 3.11+ standard library, pytest, JSON, XML, Windows `ctypes`, GitHub Actions, S32DS ConfigTools.

**Specification:** `docs/specs/rtd-config-runtime-safety-and-contract-design.md`

---

## File map

- `rtd_config/errors.py`: typed failures and stable public mappings.
- `backends/s32_mex/target.py`: containment, reparse checks, identity, immutable bytes/hash.
- `backends/s32_mex/metadata.py`: processor/package/schema/tool/module/RTD parsing.
- `resources/bundles.py` and `assets/bundles.json`: exact supported compatibility bundles.
- `backends/s32_mex/transaction.py`: staging, checks, CAS, backup, atomic publish.
- `backends/s32_mex/process_tree.py`: contained vendor process lifecycle.
- `modules/registry.py`: unique `(backend,module,action)` planner/apply/owner binding.
- `backends/s32_mex/ownership.py`: actual byte delta and region audit.
- `tools/build_descriptor_inventory.py`: deterministic development-time XDM inventory.
- `tools/build_release_manifest.py`: version/path/hash manifest generation and checking.

---

### Task 1: Stable public failure boundary (#66)

**Files:** Create `autombd-rtd/rtd-config-cli-py/rtd_config/errors.py`, modify `diagnostics.py`, `cli.py`, and `backends/s32_mex/locate.py`; test `tests/unit/test_cli_failures.py`.

- [ ] **Write RED tests.** Parameterize missing project, zero/two `.mex`, malformed XML, missing/corrupt spec, permission seams, invalid arguments, and unknown internal errors. For every `--json` call assert one parseable stdout object, stable diagnostic code, nonzero exit, and no default traceback.

```python
def assert_json_failure(result, code):
    payload = json.loads(result.stdout)
    assert payload["status"] in {"failed", "blocked"}
    assert payload["diagnostics"][0]["code"] == code
    assert "Traceback" not in result.stderr
```

- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_cli_failures.py -q`; expected failures are traceback/plain argparse output and missing generic commands.
- [ ] **Implement.** Add immutable `CliFailure(code,message,status,module,details,exit_code)`, `render_failure()`, a raising `ArgumentParser`, raw-argv JSON/debug detection, and one parse+dispatch exception boundary. Map expected path/XML/spec/asset/permission failures; do not swallow `KeyboardInterrupt`.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_cli_failures.py tests/unit/test_cli_smoke.py tests/unit/test_diagnostics.py tests/unit/test_project_locator.py -q`.
- [ ] **Commit.** `git commit -m "fix: return stable diagnostics for CLI failures"` with only Task 1 files.

---

### Task 2: Verified target and metadata parser (#65, #67)

**Files:** Create `backends/s32_mex/target.py` and `metadata.py`; modify `document.py` and `project.py`; test `test_secure_project_target.py` and `test_project_metadata.py`.

- [ ] **Write target RED tests.** Cover missing/non-directory root, multiple files, root/file symlink, injected Windows junction/reparse, resolved escape, and replacement between reads. Assert parsing uses captured bytes without reopening.
- [ ] **Verify target RED.** Run `python -m pytest tests/unit/test_secure_project_target.py -q`; expected missing `VerifiedProjectTarget`/`FileSnapshot` failures.
- [ ] **Implement target types.** Use immutable `FileIdentity(device,inode,windows_file_id)`, `FileSnapshot(path,identity,sha256,content)`, and `VerifiedProjectTarget(root,mex)`. Reject uncertainty; parse XML with `ET.fromstring(snapshot.content)`.
- [ ] **Write metadata RED tests.** The real fixture must yield S32K344, `S32K344_257BGA`/`mapbga257`, RTD 7.0.1, schema 19, Pins/Clocks/Peripherals versions, enabled modules, explicit unknowns, and conflict diagnostics.
- [ ] **Verify metadata RED.** Run `python -m pytest tests/unit/test_project_metadata.py -q`; current default echo must fail.
- [ ] **Implement metadata.** Add immutable `ProjectMetadata` with vendor/backend/family/processor/device/raw+canonical package/RTD/schema/tools/modules/conflicts. Use bounded `.mex` plus known project metadata sources; never infer RTD from one module SW version.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_secure_project_target.py tests/unit/test_project_metadata.py tests/unit/test_mex_document.py tests/unit/test_project_locator.py -q`.
- [ ] **Commit.** `git commit -m "fix: verify project targets and parse project identity"`.

---

### Task 3: Exact asset bundle resolution (#65)

**Files:** Create `resources/bundles.py` and `autombd-rtd/assets/bundles.json`; modify `resources/pins.py`, `resources/runtime.py`, `cli.py`, provider loaders, and `apply.py`; test `test_asset_bundles.py` and `test_pin_options.py`.

- [ ] **Write RED tests.** Cover exact S32K344/MAPBGA257/7.0.1/schema-19 match; wrong processor/package/RTD/schema/tool; missing/ambiguous bundle; asset identity mismatch; package-specific pin filtering.

```python
with pytest.raises(CliFailure) as caught:
    resolver.resolve(replace(metadata, package="unknown"))
assert caught.value.code == "asset_bundle_unsupported"
```

- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_asset_bundles.py tests/unit/test_pin_options.py -q`; unknown tuples currently pass/fallback.
- [ ] **Implement.** Commit only fixture/vendor-proven bundles. Require exactly one match; providers receive `ResolvedAssetBundle`; remove fixed paths and MAPBGA257 fallback. Projectless `pin-options` requires a complete tuple and filters absent package values.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_asset_bundles.py tests/unit/test_pin_options.py tests/unit/test_module_providers.py tests/unit/test_*_apply.py -q`.
- [ ] **Commit.** `git commit -m "fix: resolve exact project-compatible asset bundles"`.

---

### Task 4: Verified configure transaction (#67)

**Files:** Create `backends/s32_mex/transaction.py`; modify `target.py` and `cli.py`; test `test_configure_transaction.py`, `test_configure_pipeline.py`, and `test_backup_option.py`.

- [ ] **Write RED tests.** Inject load/staging/backup/static/CAS/replace/cleanup failures, linked backup targets, same-content new identity, same-identity new content, and check-then-swap. Assert no transaction overwrites the replacement or leaks staging.
- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_configure_transaction.py -q`; expected missing final identity/hash gate.
- [ ] **Implement.** `ConfigureTransaction` owns snapshot through publish. Before `os.replace`, resnapshot and require identity and SHA-256 equality; use a Windows handle-capable adapter where available and block uncertainty. Backup is staged, link-safe, and required before publish.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_configure_transaction.py tests/unit/test_mex_write_narrow.py tests/integration/test_configure_pipeline.py tests/integration/test_backup_option.py -q`.
- [ ] **Commit.** `git commit -m "fix: make mex configuration a verified transaction"`.

---

### Task 5: Read-only validation lifecycle (#68)

**Files:** Create `backends/s32_mex/process_tree.py`; modify `validation.py`, `cli.py`, and `config.py`; test `test_validation_lifecycle.py` and `test_validation_command.py`.

- [ ] **Write RED tests.** Hash/type-manifest the project before/after default validation; assert static blockers never launch vendor, no project log appears, no-follow copy rejects reparse entries, cleanup failure reports a retained safe path, and timeout calls tree terminate+wait.
- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_validation_lifecycle.py -q`; current project log/system-temp/ignored-cleanup behavior must fail.
- [ ] **Implement.** Extend `ValidationOutcome` with bounded logs/cleanup/retained path. Stage under explicit safe temp base, reject recursive reparse entries, and use injectable `ProcessTreeRunner.run(argv,timeout_s,cwd)`. Implement Windows Job Object control through stdlib `ctypes`.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_validation_lifecycle.py tests/unit/test_validation_command.py tests/e2e/test_s32ds_validation.py -q`.
- [ ] **Commit.** `git commit -m "fix: isolate vendor validation lifecycle"`.

---

### Task 6: Provider registry and actual ownership audit (#69)

**Files:** Create `modules/registry.py` and `backends/s32_mex/ownership.py`; modify `modules/base.py`, `modules/__init__.py`, `document.py`, `apply.py`, `transaction.py`, and `cli.py`; test `test_provider_registry.py` and `test_ownership_audit.py`.

- [ ] **Write RED tests.** Assert one binding per supported action, no duplicates, no-op empty changes, declared dependency success, fake changed-module lies ignored, and a malicious apply editing an undeclared module blocked before publish.

```python
binding = ProviderBinding("s32_mex", "uart", "set", planner, malicious_apply, frozenset({"module:uart"}), deps)
result = transaction.run(binding)
assert result.diagnostics[0].code == "provider_ownership_violation"
```

- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_provider_registry.py tests/unit/test_ownership_audit.py -q`.
- [ ] **Implement.** Registry binds planner/apply/allowed physical regions/dependency resolver. Document core keeps before bytes and splice journal. Rendered byte spans map to logical module/tool regions. Require `actual ⊆ declared ⊆ allowed`; derive `changed_modules` from audit.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_provider_registry.py tests/unit/test_ownership_audit.py tests/unit/test_module_providers.py tests/unit/test_*_apply.py tests/unit/test_mex_write_narrow.py -q`.
- [ ] **Commit.** `git commit -m "feat: enforce provider ownership with actual deltas"`.

---

### Task 7: Canonical intent and runtime configuration (#70)

**Files:** Modify `config.py`, `intent.py`, `cli.py`, `autombd-rtd/SKILL.md`, `README.md`, and `docs/specs/rtd-config-core-design.md`; test `test_runtime_config.py`, `test_cli_contract.py`, and `test_generic_intent.py`.

- [ ] **Write RED tests.** Cover help, strict `{module,action,payload}`, bad/unknown intent, plan read-only, generic configure, shortcut/raw-spec compatibility, and generic/shortcut equality for arbitrary legal non-case inputs.
- [ ] **Write config RED tests.** Assert built-in < JSON file < explicit flags and deployed asset root remains correct from another cwd.
- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_runtime_config.py tests/unit/test_cli_contract.py tests/integration/test_generic_intent.py -q`.
- [ ] **Implement.** Add top-level `plan/configure --intent`; normalize shortcuts to the same registry dispatcher. Load JSON config and overlay only explicitly provided flags. Resolve default assets from the deployed Skill, not cwd.
- [ ] **Align docs.** Update Skill/help/README/core-design append-only changelog: generic is stable core, shortcuts equivalent adapters.
- [ ] **Verify GREEN.** Run `python -m pytest tests/unit/test_runtime_config.py tests/unit/test_cli_contract.py tests/integration/test_generic_intent.py tests/unit/test_cli_spec_input.py tests/integration/test_plan_command.py -q`.
- [ ] **Commit.** `git commit -m "feat: expose canonical generic intent commands"`.

---

### Task 8: Descriptor inventories outside runtime assets (#72, #58 dependency)

**Files:** Create `tools/build_descriptor_inventory.py` and `docs/specs/rtd-config-module-coverage/*.json`; remove `_coverage` from runtime assets; modify core design, `AGENTS.md`, governance, and affected tests; create `test_descriptor_inventory.py`.

- [ ] **Write RED tests.** Synthetic XDM covers stable item keys, enum/range/default/INVALID/EDITABLE/ENABLE/reference extraction, duplicates, missing/double classification, invalid traces, descriptor hash mismatch, runtime `_coverage`, and release inclusion.

```python
items = set(sidecar["items"])
groups = [set(sidecar[name]) for name in ("configurable", "derived", "deferred")]
assert set.union(*groups) == items
assert all(not (left & right) for left, right in combinations(groups, 2))
```

- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_descriptor_inventory.py -q`.
- [ ] **Implement extractor.** Accept an explicit descriptor path only; emit stable structural keys, kinds, domains/ranges/defaults, constraints, references, package/version/full SHA-256. `--check` is side-effect free.
- [ ] **Generate complete Mcu/Adc inventories.** Use the exact cached descriptors and account every item as configurable, derived, or deferred. Confirm known reset and ADC DSPSS/self-test/timing/general/power/published/AUTOSAR groups without treating that list as scope.
- [ ] **Migrate coverage.** Move all existing module `_coverage` data to non-runtime sidecars and assert no released asset recursively contains `_coverage`.
- [ ] **Verify GREEN/source.** Run descriptor unit/generality/apply tests, then `build_descriptor_inventory.py --check` for exact Mcu and Adc paths.
- [ ] **Commit.** `git commit -m "feat: gate descriptor inventory outside runtime assets"`.

---

### Task 9: Version, release manifest, CI, and status (#71)

**Files:** Create `tools/build_release_manifest.py`, `autombd-rtd/release-manifest.json`, `.github/workflows/ci.yml`, and `test_release_manifest.py`; modify deployer, version sites, README, test strategy, and deploy tests.

- [ ] **Write RED tests.** Assert pyproject authority/equality, complete sorted path+SHA inventory, missing/corrupt/same-version drift/extra-file detection, clean deploy, and external-cwd launcher.
- [ ] **Verify RED.** Run `python -m pytest tests/unit/test_release_manifest.py tests/unit/test_deploy_rtd_skill.py -q`; current 0.1.0/0.1.7 drift and absent manifest fail.
- [ ] **Implement.** Read `pyproject.toml` with `tomllib`, compare all version sites, generate/check approved release roots, and deploy only verified manifest entries through rollback-safe staging.
- [ ] **Finalize version/manifest.** Select the next release version per repository policy after payload settles; update all sites and generate byte-stable manifest.
- [ ] **Add CI.** Python 3.11–3.14 deterministic matrix plus Windows/Linux clean-deploy smoke using current official action majors. Vendor and independent black-box gates remain outside hosted CI.
- [ ] **Align README.** Use workflow badge and dated acceptance link; distinguish minimal seven and additional ADC without permanent unsupported status claims.
- [ ] **Verify GREEN.** Run manifest check, release/deploy tests, deploy to `tests/.tmp`, and launcher/help/resource smoke from another cwd.
- [ ] **Commit.** `git commit -m "ci: enforce version and release manifest integrity"`.

---

### Task 10: Full acceptance, review, push, and PR

**Files:** Update `docs/tests/rtd-config-acceptance-report.md`; append reviewer lesson only after green; change test cases only if verified behavior requires owner-level correction.

- [ ] **Deterministic gate.** Run `python -m pytest -q`; fix production gaps, never weaken tests.
- [ ] **Hygiene/release gate.** Run `git diff --check`, manifest `--check`, and Agent skill contract tests.
- [ ] **Vendor gate.** Run cached S32DS validation; record exact exit 0, generated-file count, and zero qualifying SEVERE `[TOOL]` resource problems.
- [ ] **Black-box gate.** Run every one of the 14 `RTD-MEX-*` cases through `tools/blackbox_e2e.py --agent opencode --temp-base tests/.tmp`; independently revalidate produced `.mex` files.
- [ ] **KPI loop.** For functional PASS/KPI MISS, perform at most three measured Worker optimizations with a fresh run after each; record the true final result.
- [ ] **Evidence.** Append functional/KPI seconds, edit attempts, date, and session evidence to the acceptance report without machine-specific paths.
- [ ] **Non-test review.** Verify exact descriptor values, full sidecar accounting, runtime/release boundaries, headers, standards, tests, and diff hygiene. Resolve every blocking finding and append one lesson.
- [ ] **Final gate.** Rerun full pytest, diff check, manifest check, relevant S32DS and invalidated black-box cases after any review fix.
- [ ] **Publish.** Push `codex/p1-issues-65-72`; open a draft PR referencing #65–#72, closed #64 as regression baseline, and #58 as the coverage-storage dependency; mark ready only after all checks are green.

---

## Self-review

- Every approved design requirement maps to Tasks 1–10.
- Every production task begins with an observed failing test.
- Dependency order is diagnostics → target/metadata → assets → transaction/validation → ownership → API → inventory → release.
- The release manifest is generated only after runtime payload changes settle.
- Descriptor scope is the full XDM surface, never the E2E literal subset.
- Final acceptance includes deterministic, static, S32DS, independent black-box, KPI, and non-test evidence.
