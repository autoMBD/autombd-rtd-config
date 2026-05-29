---
name: project-audit
description: Comprehensive project health audit covering structure, code quality, documentation accuracy, and git history. Use for periodic checkups or after significant feature batches. Produces a prioritized TODO with P0-P3 severity classification.
---

# Project Audit

Run a systematic, multi-dimensional audit of the entire repository. The goal is to find errors, inconsistencies, stale documentation, and structural problems before they cause real issues.

## When to Use

- User asks to "check the project", "audit the repo", "review project health"
- After landing a significant batch of features
- Before a release or handoff
- Periodically as routine maintenance

## Audit Dimensions

Run these four audits in parallel using subagents. Each subagent gets a self-contained prompt and reports findings only — it does NOT make changes.

### 1. Structure Audit

Delegate to an Explore agent. Prompt it to check:

- Top-level directory and file listing, flag anything unexpected
- Recursive file listing of `src/`, `examples/`, `tools/`
- **Orphan files**: files tracked by git but not referenced by any CMakeLists.txt
- **.gitignore coverage**: is it complete? Are any tracked files accidentally gitignored?
- **Duplicate filenames** across the project (excluding build/ and .git/)
- **Include dependency graph**: for every `#include "..."` in `src/`, verify the target file exists
- **CMakeLists.txt consistency**: every source file listed in CMake actually exists; every target_include_directories path exists
- `.skills/` directory structure and skill bridge integrity

### 2. Code Quality Audit

Delegate to an Explore agent. Prompt it to check:

- **Include guards**: every `.h` file must have `#ifndef`/`#define`/`#endif`
- **MIT bilingual header**: every `.c` and `.h` file must have it (per `uniform-file-header` skill); list any missing
- **Function declarations vs definitions**: no declared-but-undefined or defined-but-undeclared functions
- **Dead code**: functions with zero callers anywhere in the codebase
- **Naming conventions**: check prefixes (`AUTOMBD_` for enums, `autombd_` for functions), flag inconsistencies
- **HAL backend parity**: verify the 12 shared function signatures are truly identical across `s32k3/` and `s32k3_rtd/`
- **extern "C" guards**: C-compatible headers should have them
- **Potential bugs**: uninitialized variables, buffer size limits, integer overflow risks
- **TODO/FIXME/HACK** comments
- **CLI architecture**: verify the three-layer split matches CLAUDE.md description

### 3. CLAUDE.md Accuracy Audit

Delegate to an Explore agent. Prompt it to verify EVERY factual claim in CLAUDE.md:

- Build commands and their flags
- Default paths (S32DS, SEGGER, Make, GCC)
- Architecture claims (HAL function signatures, ops table, CLI layers)
- Feature gating (`AUTOMBD_CLI_ENABLE` default value and mechanism)
- File paths and line-number references
- Cross-check CHANGELOG.md and README.md for consistency

### 4. Git History Audit

Delegate to an Explore agent. Prompt it to run git commands and check:

- `git log --oneline -30` — commit message style consistency
- Large files in history: `git rev-list --objects --all | git cat-file ... | sort -rn | head -20`
- Binary files tracked at HEAD
- `.gitignore` timing: were any files committed before being gitignored?
- `git branch -a` — stale branches
- Merge topology: linear or branched?
- CHANGELOG.md vs actual commit history
- Sensitive data scan: search tracked files for passwords, tokens, keys
- Git config: `user.name`, `user.email`, signing settings

## Severity Classification

| Level | Criteria |
|-------|----------|
| **P0 Critical** | Linker errors, compile-breaking bugs, security vulnerabilities |
| **P1 High** | Missing include guards, missing license headers, data corruption risks |
| **P2 Medium** | Dead code, naming inconsistencies, stale docs, orphan files, binary bloat |
| **P3 Low** | Style nits, whitespace, commit message typos, missing GPG signing |

## Output

1. Write the full audit report to the TODO file requested by the user. If the
   user does not name a TODO file, use `docs/TODO.md`.
2. If the target TODO file already exists and already has P0/P1/P2/P3 sections,
   preserve its existing content and merge new findings into the matching
   severity sections. Do not create a second "audit supplement", "re-audit", or
   duplicate P0/P1/P2/P3 block unless the user explicitly asks for a separate
   dated section.
3. If an existing TODO item is now resolved, remove it from the TODO during the
   audit update instead of leaving it checked off. TODO files are maintenance
   queues, not historical audit logs; resolved items should disappear so the
   file stays short and actionable. Only keep a resolved item when the user
   explicitly asks for historical traceability.
4. If an existing TODO item is partially resolved, update that same item in
   place so only the remaining work stays listed.
5. Keep the file's existing language and encoding style. Chinese content is not
   corruption; if the terminal displays mojibake, verify with git diff or an
   encoding-aware viewer before rewriting.
6. Include CLAUDE.md verification results and improvement recommendations inside
   the relevant P0-P3 sections, or under an existing summary section if one is
   already present.
7. Present a compact summary to the user in one line per severity tier, and
   highlight the worst finding.
8. If the user asks to fix issues: fix P0 first, then P1, following the
   auto-commit skill for each logical unit of work.

## Post-Audit

- After fixes are made, update the selected TODO file by removing resolved items
  and keeping only remaining work.
- If the ROADMAP.md is stale (items resolved in code but not documented), flag it and offer to update.
- Follow `auto-commit` skill for every fix commit.
