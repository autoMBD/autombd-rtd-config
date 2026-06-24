# Agent Initialization Skill Import Implementation Plan

> **For agentic workers:** Execute each task in order with test-first red/green evidence. Do not use repository-aware embedded agents as black-box validators.

**Goal:** Add multi-directory local Skill discovery and selection, link-only selected-Skill deployment, Agent-orchestrated online Skill requests, and scope-gated supplemental initialization tasks.

**Architecture:** Keep local discovery as pure collector logic shared by the Tk GUI and tests. Persist an explicit version 2 selection so deployment revalidates and links only the selected source directories. Keep online installation and supplemental-task execution in the initialization Skill orchestration contract, outside the deterministic deployer.

**Tech Stack:** Python 3, tkinter/ttk, pathlib, pytest, JSON, Markdown contracts.

---

### Task 1: Local Skill discovery contract

**Files:**

- Modify: `tests/unit/test_init_agent_env.py`
- Modify: `tools/init_agent_env.py`

- [ ] **Step 1: Write failing discovery tests**

Add tests that create multiple roots, overlapping roots, valid manifests,
invalid manifests, and same-name/different-source collisions. Assert a pure
`discover_local_skills(roots)` function returns sorted candidates and explicit
issues:

```python
result = discover_local_skills([root_a, root_b])
assert [(item.name, item.source) for item in result.candidates] == [
    ("skill-a", (root_a / "skill-a").resolve()),
    ("skill-b", (root_b / "nested/skill-b").resolve()),
]
assert result.issues == ()
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/unit/test_init_agent_env.py -q`

Expected: import failure because the discovery API does not exist.

- [ ] **Step 3: Implement minimal discovery types and parser**

Add immutable `LocalSkillCandidate`, `LocalSkillIssue`, and
`LocalSkillDiscovery` dataclasses. Implement recursive `SKILL.md` discovery,
frontmatter-name parsing, path normalization, deterministic sorting,
same-source deduplication, and blocking same-name/different-source issues.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/unit/test_init_agent_env.py -q`

Expected: all Task 1 tests pass.

### Task 2: Version 2 structured-input validation

**Files:**

- Modify: `tests/unit/test_init_agent_env.py`
- Modify: `tools/init_agent_env.py`

- [ ] **Step 1: Write failing validation tests**

Cover valid multiple selections and rejection of empty selections, duplicate
names, mismatched manifest names, sources outside submitted roots, malformed
online requests, and malformed supplemental tasks:

```python
config["version"] = 2
config["local_skill_import"] = {
    "roots": [root.as_posix()],
    "selected": [{"name": "skill-a", "source": skill.as_posix()}],
}
assert validate_input(config) == []
```

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/unit/test_init_agent_env.py -q`

Expected: invalid version 2 local selections are currently accepted.

- [ ] **Step 3: Implement validation**

Accept versions 1 and 2, validate optional version 2 fields, and expose a
shared `validate_local_skill_import(spec)` helper. Preserve legacy version 1
validation for old saved input while emitting only version 2 from collectors.

- [ ] **Step 4: Verify GREEN**

Run the focused test file and require zero failures.

### Task 3: GUI multi-root and multi-select behavior

**Files:**

- Modify: `tests/unit/test_init_agent_env.py`
- Modify: `tools/init_agent_env.py`

- [ ] **Step 1: Write failing state-model tests**

Test a display-independent `LocalSkillSelectionModel` for add/remove/rescan,
selection preservation, select-all, clear-all, and JSON serialization. Add a
source assertion or Tk test proving import-mode switching does not use
`pack(before=...)` against an unmanaged widget.

- [ ] **Step 2: Run and verify RED**

Expected: model import fails and current source still contains the broken pack
pattern.

- [ ] **Step 3: Implement the model and GUI controls**

Replace the single directory entry with a roots list, repeated Add/Remove
actions, Rescan, a scrollable checkbutton candidate list, Select all, and Clear
all. Add multiline online-request and supplemental-task text widgets. Use
stable packing without `before=`. Serialize version 2 fields from `_on_ok`.

- [ ] **Step 4: Verify GREEN**

Run the GUI/model unit tests. Importing the module must not require creating a
Tk root.

### Task 4: Selected-only link deployment

**Files:**

- Modify: `tests/unit/test_deploy_agent_env.py`
- Modify: `tools/deploy_agent_env.py`

- [ ] **Step 1: Write failing deployment tests**

Create two discovered Skills but select one. Assert only the selected Skill is
linked. Add tests for multiple roots, overlapping roots, source changes after
collection, source outside roots, duplicate names, canonical collisions, and
ordinary-directory target rejection.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/unit/test_deploy_agent_env.py -q`

Expected: deployer ignores version 2 selection or rescans all roots.

- [ ] **Step 3: Implement selected-source collection**

Replace legacy local-root rescanning for version 2 with exact selected-entry
revalidation. Keep version 1 local import compatibility. Do not alter
`ensure_directory_link`: every target remains a directory symlink or Windows
junction and copying remains prohibited.

- [ ] **Step 4: Verify GREEN**

Run both initializer and deployer unit tests and require zero failures.

### Task 5: Initialization orchestration contracts

**Files:**

- Modify: `tests/unit/test_agent_skill_contract.py`
- Modify: `agent-discipline/skills/initialize-agent-discipline/SKILL.md`
- Modify: `agent-discipline/skills/initialize-agent-discipline/references/platform-contract.md`
- Modify: `agent-discipline/documentation-governance.md` only if its metadata or map requires synchronization

- [ ] **Step 1: Write failing contract tests**

Assert the Skill and platform contract require multiple local roots, explicit
selected Skills, link-only local deployment, user-level `find-skills`
bootstrap/install outside the deployer, post-verification supplemental-task
execution, and confirmation for out-of-scope supplemental work.

- [ ] **Step 2: Run and verify RED**

Run: `python -m pytest tests/unit/test_agent_skill_contract.py -q`

Expected: required version 2 orchestration language is absent.

- [ ] **Step 3: Update the contracts**

Document the precise GUI fields, JSON ownership, execution sequence, failure
behavior, and verification checklist. Retain the GUI-first rule and never
direct the deployer to install online Skills or write user-level directories.

- [ ] **Step 4: Verify GREEN**

Run all three focused test files and require zero failures.

### Task 6: Full verification and review

**Files:**

- Review all changed files.

- [ ] **Step 1: Run fresh focused verification**

```powershell
python -m pytest tests\unit\test_init_agent_env.py `
  tests\unit\test_deploy_agent_env.py `
  tests\unit\test_agent_skill_contract.py -q
```

- [ ] **Step 2: Run the full deterministic unit suite**

Run: `python -m pytest tests/unit -q`

- [ ] **Step 3: Run static and Git hygiene checks**

```powershell
python -m py_compile tools\init_agent_env.py tools\deploy_agent_env.py
git diff --check
git status --short
```

- [ ] **Step 4: Review requirements and diff**

Confirm every acceptance criterion in the approved design is represented by
code, tests, or orchestration documentation; confirm no project Skill directory
is copied and no online-install command entered the deployer.

- [ ] **Step 5: Commit implementation**

Stage only the scoped implementation, tests, and contract documents. Commit
with a message describing multi-Skill initialization support.
