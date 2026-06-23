---
name: initialize-agent-discipline
description: Initialize the project-level Agent environment for the RTD CfgFile CLI project. Use when starting development from a clean clone, when the project-level Agent environment has not been initialized, when the user requests an update or reset of the Agent discipline, or when the user requests importing additional skills.
---

# Initialize Agent Discipline

## Overview

This skill sets up the project-level Agent environment by deploying
agent-discipline skills, subagent templates, and external-dependency memory to
the selected Agent platforms. Every agent working in this checkout then operates
from the same project discipline.

The skill orchestrates four phases:

1. **Pre-check** — verify what already exists (`.agent-state/` cache, platform
   directories) to avoid redundant work.
2. **Collect structured input** — run `python tools/init_agent_env.py` to open
   a GUI dialog that gathers platforms, mode, paths, and optional imports. The
   script outputs deployment-ready JSON. S32DS/RTD paths are **optional** — the
   GUI provides a "Skip" checkbox for environments without those tools.
3. **Deploy** — create symlinks for skills, convert and write subagent files,
   and initialize the external-dependency cache.
4. **Verify** — confirm symlink integrity, subagent file presence, cache
   validity, and Git hygiene.

## Trigger Conditions

Load and execute this skill when:

- Development starts from a **clean clone** and no platform-specific project
  directories (`.claude/`, `.opencode/`, `.agents/`) exist.
- The project-level Agent environment has **not been initialized** (missing
  skills, subagents, or external-dependency cache).
- The user explicitly requests an **update** or **reset** of the Agent
  discipline.
- The user requests **importing additional skills** from local or online
  sources.

## Boundaries

This skill manages the project-level Agent environment ONLY:

| In scope | Out of scope |
| --- | --- |
| `.claude/skills/`, `.claude/agents/` (Claude) | `~/.claude/` (user-level/global) |
| `.opencode/skills/`, `.opencode/agents/` (OpenCode) | `~/.config/opencode/` (user-level/global) |
| `.agents/skills/`, `.agents/agents/` (Codex) | `~/.codex/` (user-level/global) |
| `.agent-state/external-dependencies.json` | `autombd-rtd/` skill payload |

The `autombd-rtd/` skill payload is deployed separately by
`tools/deploy_rtd_skill.py` and is outside this skill's scope.

## Files and Paths Reference

### Source paths (committed in repository)

| Content | Path |
| --- | --- |
| Agent-discipline skills | `agent-discipline/skills/<name>/SKILL.md` |
| Subagent templates | `agent-discipline/subagents/<name>.md` |
| Input collector script | `tools/init_agent_env.py` |

### Target paths per platform (generated, NOT committed)

| Platform | Skills directory | Subagents directory |
| --- | --- | --- |
| Claude | `.claude/skills/<name>/` | `.claude/agents/<name>.md` |
| OpenCode | `.opencode/skills/<name>/` | `.opencode/agents/<name>.md` |
| Codex | `.agents/skills/<name>/` | `.agents/agents/<name>.md` |

> **Important:** Codex resolves project-level skills and agents from `.agents/`,
> not `.codex/`. This is confirmed by the existing `tools/deploy_rtd_skill.py`
> which deploys the Codex skill to `.agents/skills/`.

All generated files under `.claude/`, `.opencode/`, `.agents/`, and
`.agent-state/` are covered by `.gitignore` and must never be committed.

## Workflow

### Phase 0: Pre-check Existing State

Before running the input collector, check what already exists:

1. **Read `.agent-state/external-dependencies.json`** if it exists. If the cache
   already has valid `env.s32ds` and `env.rtd` entries, note them — the user can
   skip re-entering these paths in the GUI.
2. **Check for existing platform directories:**
   - `.claude/skills/`, `.claude/agents/`
   - `.opencode/skills/`, `.opencode/agents/`
   - `.agents/skills/`, `.agents/agents/`
3. **Determine the default platforms** — if the agent itself is running on a
   specific platform (e.g. Codex), pre-select that platform. The user can adjust
   in the GUI.
4. **Determine the default mode** — if platform directories already exist with
   symlinks and subagent files, default to `update`. Otherwise default to
   `update` (reset is explicit only).

This pre-check prevents redundant work and lets the agent contextualize the
GUI defaults.

### Phase 1: Collect Structured Input

Run the unified input collector GUI:

```bash
python tools/init_agent_env.py --output .agent-state/init-input.json
```

This opens a tkinter dialog with:

- **Target platforms** — checkboxes for Codex, Claude, OpenCode
- **Operation mode** — Update (preserve existing) or Reset (clear + reinitialize)
- **Reset confirmation** — checkbox, visible only when Reset is selected
- **S32DS installation root** — text entry + **Browse...** button; optional
  (check "Skip S32DS/RTD paths" to deploy skills/subagents only)
- **RTD installation path** — text entry + **Browse...** button; optional
- **Additional skills import** — Skip / Local directory / Online URL

On OK the script validates inputs and writes JSON to the `--output` file. On
Cancel the script exits with code 130.

If the input has already been collected, reload it:

```bash
python tools/init_agent_env.py --input .agent-state/init-input.json
```

If tkinter is unavailable (headless environment), supply pre-collected input
via `--input`.

#### Collected Input Schema

```json
{
  "version": 1,
  "collected_at": "2026-06-23T12:00:00Z",
  "platforms": ["claude", "opencode"],
  "mode": "update",
  "reset_confirmed": false,
  "s32ds_path": "C:/NXP/S32DS.3.6.7",
  "rtd_path": "C:/NXP/S32DS.3.6.7/S32DS/software/PlatformSDK_S32K3/RTD",
  "import_skills": {
    "type": "local",
    "path": "D:/my-skills",
    "description": "Import skills from local directory: D:/my-skills"
  }
}
```

Preserve this file in `.agent-state/` for update-mode reuse. In reset mode,
the `.agent-state/` directory is cleared, so the file is removed.

#### Update Mode Rules

- **Preserve** all existing project-level Agent files and `.agent-state/` cache
  entries that are not explicitly touched in this operation.
- **Deploy or update** only the platforms, skills, subagents, and cache entries
  that the user explicitly selected or entered.
- If a symlink destination already exists and points to the correct source,
  skip it (no change).
- If a subagent file already exists, overwrite it with the converted content
  only if the source template has changed.

#### Reset Mode Rules

- **Clear only** the project-level Agent environment for the selected platforms
  — delete their skill symlinks and generated subagent files.
- **Clear** the current project's `.agent-state/` directory entirely.
- **Do NOT affect** any user-level or global Agent environment
  (`~/.claude/`, `~/.config/opencode/`, `~/.codex/`).
- The `tools/init_agent_env.py` script handles the confirmation prompt. Do not
  proceed with reset unless the collected input has `"reset_confirmed": true`.

After collecting input with reset mode confirmed, delete the listed directories:

```
Remove-Item -Recurse -Force -LiteralPath ".claude\skills"
Remove-Item -Recurse -Force -LiteralPath ".claude\agents"
Remove-Item -Recurse -Force -LiteralPath ".agent-state"
```

Then proceed with reinitialization from the collected input.

### Phase 2: Execute Deployment

Use the collected input to deploy.

> **Critical principle: Project conventions are authoritative.**
> The directory paths, file extensions (`.md`), and YAML-frontmatter format
> are established by this project's own toolchain — specifically
> `tools/deploy_rtd_skill.py` and the templates under
> `agent-discipline/subagents/`. These project facts are **not negotiable**
> through external research. External documentation describes each platform's
> general configuration capabilities; it does **not** override this project's
> established directory structure or file format. Do not replace `.md` with
> `.toml`, `.yaml`, or any other extension. Do not change `.agents/` to
> `.codex/` or any other directory.

#### 2.1 Deploy Agent-Discipline Skills (Symlinks)

For each skill directory under `agent-discipline/skills/` and each selected
platform:

1. Create the platform's skill directory if it does not exist.
   Use the paths from the table in [Files and Paths Reference](#files-and-paths-reference).
2. Create a directory symlink (or junction on Windows) from the platform's
   skill directory to the source directory.
3. **Copying is prohibited.** If a symlink cannot be created, report the error
   and stop. On Windows, enable Developer Mode or run as administrator.
4. Skip skills that are already correctly linked.

Windows symlink commands:

```powershell
New-Item -ItemType SymbolicLink -Path ".claude\skills\external-dependency-memory" -Target "agent-discipline\skills\external-dependency-memory"

cmd /c mklink /J ".claude\skills\external-dependency-memory" "agent-discipline\skills\external-dependency-memory"
```

On non-Windows systems:

```bash
ln -s "$(pwd)/agent-discipline/skills/external-dependency-memory" ".claude/skills/external-dependency-memory"
```

Use absolute source paths.

#### 2.2 Deploy Subagents

The templates under `agent-discipline/subagents/` are **YAML frontmatter +
Markdown body** (`.md` files). This is the project's subagent format. The
directory paths and file extensions are project convention and are not subject
to external research.

For each template and each selected platform:

1. Read the source template. Extract the `name` from its frontmatter.
2. Apply the platform-specific frontmatter adaptation (below).
3. Write the result to the platform's agents directory.

##### Claude Deployment

Write the template content as-is to `.claude/agents/<name>.md`. The templates
are already in Claude-compatible format. In update mode, overwrite only if
the source has changed.

##### OpenCode Deployment

Adapt the frontmatter for OpenCode. To confirm the exact current field set,
load the `customize-opencode` skill or fetch the JSON Schema at
`https://opencode.ai/config.json`. The adaptation is typically:

- **Remove** `name` (OpenCode infers it from the filename).
- **Remove** `model` or translate to provider-prefixed form (e.g.
  `anthropic/claude-sonnet-4-6`). If uncertain, omit — let OpenCode use its
  default.
- **Keep** `description`, `mode` (`subagent`), `permission`.
- Add `"$schema": "https://opencode.ai/config.json"`.
- The Markdown body remains unchanged.

Write to `.opencode/agents/<name>.md`.

##### Codex Deployment

Write the template content as-is to `.agents/agents/<name>.md`. The templates
are compatible with this project's Codex flow — same YAML frontmatter +
Markdown format used by `tools/deploy_rtd_skill.py`. In update mode, overwrite
only if the source has changed.

> **Do not change the file extension or directory.** Codex in THIS project
> resolves agents from `.agents/agents/<name>.md`. The `.agents/` directory and
> `.md` extension are project conventions established by the existing deploy
> toolchain. External Codex documentation may describe other configurations
> but those do not apply to this project's agent discipline layout.

#### 2.3 Initialize External-Dependency Cache

Create or update `.agent-state/external-dependencies.json` using the paths
from the collected input. If `s32ds_path` or `rtd_path` is empty (user chose
"Skip" in the GUI), **skip that entry** — do not record a blank location.

If the file does not exist, create it:

```json
{
  "version": 1,
  "updated_at": "<ISO 8601 timestamp now>",
  "items": {}
}
```

Add or update entries only when the path is non-empty (preserving other
entries in update mode):

```json
{
  "env.s32ds": {
    "kind": "env",
    "status": "available",
    "location": "<s32ds_path from input>",
    "evidence": "User provided and verified during agent discipline initialization via tools/init_agent_env.py.",
    "verified_at": "<ISO 8601 timestamp now>",
    "verified_by": "<current platform name>"
  },
  "env.rtd": {
    "kind": "env",
    "status": "available",
    "location": "<rtd_path from input>",
    "evidence": "User provided and verified during agent discipline initialization via tools/init_agent_env.py.",
    "verified_at": "<ISO 8601 timestamp now>",
    "verified_by": "<current platform name>"
  }
}
```

Follow the `external-dependency-memory` skill rules:
- Use stable item keys (`env.s32ds`, `env.rtd`).
- Write conservative evidence.
- Never record tokens, passwords, or credentials.

#### 2.4 Deploy Additional Skills (If Selected)

If the collected input includes `import_skills`:

**Local directory (`type: "local"`):**
1. Scan the provided `path` for `**/SKILL.md` files.
2. For each skill found, create a directory symlink from each selected
   platform's `skills/` directory to the skill's source directory.
3. Use the same symlink approach as in 2.1.
4. Report each skill deployed and its source path.

**Online source (`type: "online"`):**
1. Fetch the skill listing from the `url`.
2. Report what is available and instruct the user on platform-specific
   installation commands.
3. Do not attempt to automate online installation; the mechanism varies by
   platform.

### Phase 3: Verify

After deployment, run these checks:

1. **Symlink integrity:** For each deployed skill symlink, verify the
   destination exists and points to a directory containing `SKILL.md`.
2. **Subagent file presence:** For each platform, verify every template from
   `agent-discipline/subagents/` has a corresponding file in the platform's
   agents directory with platform-appropriate frontmatter.
3. **Cache validity:** Verify `.agent-state/external-dependencies.json` is
   valid JSON with `env.s32ds` and `env.rtd` at `status: "available"`.
4. **Git hygiene:** Verify no generated files appear in `git status` as
   untracked (`.gitignore` covers `.claude/`, `.opencode/`, `.agents/`,
   `.agent-state/`).

## Error Handling

| Scenario | Action |
| --- | --- |
| `tools/init_agent_env.py` not found | Report the missing file path. The script is committed in `tools/`. Verify the repository is not corrupted. |
| GUI fails to start (tkinter unavailable) | Report the error. Use `--input` to supply pre-collected JSON. |
| Script exits with error (user cancelled or path invalid) | Stop. Report the exit reason. Do not proceed with partial input. |
| Collected input validation fails | Report which field failed and why. Ask the user to re-run the script. |
| Symlink creation fails on Windows | Instruct the user to enable Developer Mode or run as administrator. Do not fall back to copying. |
| Template frontmatter is malformed | Report which template file and the specific parsing error. Skip that template; proceed with the rest. |
| `.gitignore` does not cover generated files | Add the missing pattern to `.gitignore`. Do not stage generated files. |

## Reference: Subagent Templates

The four templates under `agent-discipline/subagents/`:

| Template file | Agent name | Mode | Key permission restriction |
| --- | --- | --- | --- |
| `explorer.md` | explorer | subagent | `edit: deny`, `task: deny` |
| `worker.md` | worker | subagent | full read/write/bash within scope |
| `tester.md` | tester | subagent | full access; runs tests and validation |
| `reviewer.md` | reviewer | subagent | `edit: deny`, `task: deny` |

## Closeout Checklist

- [ ] `tools/init_agent_env.py` ran successfully; input is valid and saved.
- [ ] All selected platforms have valid skill symlinks to `agent-discipline/skills/`.
- [ ] All selected platforms have subagent files in project-convention directories (`.md` format).
- [ ] `.agent-state/external-dependencies.json` exists with S32DS/RTD entries (if paths were provided).
- [ ] Additional skills (if requested) deployed as symlinks.
- [ ] Reset mode: only project-level content cleared; user-level/global intact.
- [ ] No generated files staged in Git.
