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

The skill orchestrates three phases:

1. **Collect structured input** — run `python tools/init_agent_env.py` to
   interactively gather platforms, mode, paths, and optional imports. The script
   outputs deployment-ready JSON. This unified input collector works identically
   on all Agent platforms — no platform-native GUI tools are required.
2. **Research platform formats** — for each selected platform, search and
   retrieve the authoritative subagent/agent configuration format before
   generating any files.
3. **Execute deployment** — create symlinks for skills, convert and write
   subagent files in each platform's native format, and initialize the
   external-dependency cache.

No standalone GUI application. No dedicated initialization scripts beyond the
input collector.

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

### Phase 1: Collect Structured Input

Run the unified input collector:

```bash
python tools/init_agent_env.py
```

This launches an interactive CLI that prompts the user for:

- **Target platforms** — multi-select from `codex`, `claude`, `opencode`
- **Operation mode** — `update` (preserve existing) or `reset` (clear + reinitialize)
- **Reset confirmation** — explicit yes/no before any deletion (reset mode only)
- **S32DS installation root** — validated for expected subdirectories (`eclipse/`, `S32DS/`)
- **RTD installation path** — validated for RTD package directories (`*_TS_T*`)
- **Additional skills import** — optionally import from local directory or online source

The script writes the collected input as JSON to stdout. Capture it:

```powershell
python tools/init_agent_env.py --output .agent-state/init-input.json
```

Or parse from stdout directly.

If the input has already been collected and saved to a file, use:

```bash
python tools/init_agent_env.py --input .agent-state/init-input.json
```

to validate and reload it non-interactively.

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

### Phase 2: Research Platform Subagent Formats

Before generating any subagent files, **retrieve the authoritative subagent
configuration format for each selected platform**. Never guess or hardcode a
format — formats evolve and differ between platforms.

#### OpenCode Agent Format

The format is documented in the project's `customize-opencode` skill and the
published JSON Schema.

1. Load the `customize-opencode` skill if available. Key facts:
   - Agent files live in `.opencode/agent/<name>.md` or `.opencode/agents/<name>.md`.
   - Required frontmatter fields: `description`, `mode` (`subagent`, `primary`, `all`).
   - Optional: `model` (provider-prefixed, e.g. `anthropic/claude-sonnet-4-6`),
     `permission`, `temperature`, `top_p`, `hidden`, `color`, `disable`.
   - The `name` field is **inferred from the filename**, not declared in frontmatter.
2. Fetch the authoritative JSON Schema: `https://opencode.ai/config.json`
   Locate the agent object schema to confirm the current field set.
3. Apply any current-field changes from the schema before writing.

Typical OpenCode agent file structure:

```markdown
---
description: <from template>
mode: subagent
permission:
  edit: allow
  bash: allow
---
(markdown body from template)
```

#### Claude Agent Format

The subagent templates under `agent-discipline/subagents/` are already in
Claude-compatible format (YAML frontmatter + Markdown body). Claude Code
resolves agents from `.claude/agents/`.

1. Read the existing templates to understand the field set:
   ```yaml
   ---
   name: <agent-name>
   description: <...>
   model: opus
   mode: subagent
   permission:
     read: allow
     edit: allow
     ...
   ---
   ```
2. If Claude Code documentation or release notes are available through the
   agent's web fetch capability, verify that the field set is current.
3. Otherwise, use the template format as-is — it matches the conventions used
   by this project's deploy toolchain and is known to work with Claude Code.

#### Codex Agent Format

Codex resolves agents from `.agents/agents/`. The format is typically similar
to the template format (YAML frontmatter + Markdown body).

1. Check for existing `.agents/` content or documentation:
   - If `.agents/agents/` already has files, inspect their frontmatter.
   - If the Codex CLI has an `--agent-template` or similar command, use it.
2. Search for current Codex agent configuration documentation:
   - Check `https://github.com/openai/codex` docs or the Codex CLI `--help`.
   - Use `webfetch` if available.
3. If no documentation is found, use the template format as-is: the templates
   under `agent-discipline/subagents/` are known to be compatible with this
   project's Codex flow.

#### For Any Future Platform

Apply the same principle: search for and retrieve the authoritative format
definition before generating files. If no format can be confirmed, report the
gap and skip that platform rather than writing potentially invalid files.

### Phase 3: Execute Deployment

Use the collected input (Phase 1) and the researched formats (Phase 2) to
deploy.

#### 3.1 Deploy Agent-Discipline Skills (Symlinks)

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

Use absolute source paths. The source `agent-discipline/skills/<name>/` must
resolve to a real directory containing `SKILL.md`.

#### 3.2 Deploy Subagents

For each template under `agent-discipline/subagents/` and each selected platform:

1. Read the source template. Extract the `name` from its frontmatter.
2. Convert to the target platform's format (researched in Phase 2).
3. Write the converted file to the platform's agents directory:
   - Claude: `.claude/agents/<name>.md`
   - OpenCode: `.opencode/agents/<name>.md`
   - Codex: `.agents/agents/<name>.md`
4. In update mode, overwrite only if the source template has changed.

##### OpenCode Conversion (Typical)

Based on the format retrieved in Phase 2, the conversion typically involves:

- **Remove** `name` (OpenCode infers from filename).
- **Remove** or translate `model` (OpenCode uses provider-prefixed model IDs).
  If the agent's current context provides a default model, use it; otherwise
  omit to let OpenCode use its configured default.
- **Keep** `description`, `mode` (`subagent`), and `permission`.
- Add `"$schema": "https://opencode.ai/config.json"` for editor validation.
- The Markdown body remains unchanged.

> **Always verify against the schema fetched in Phase 2.** The above is the
> typical conversion but may change with OpenCode updates.

##### Claude Deployment (Typical)

The source templates are already in Claude-compatible format. Write them as-is
to `.claude/agents/<name>.md`. Verify against any format documentation found
in Phase 2.

##### Codex Deployment (Typical)

The source templates are typically compatible with Codex. Write them to
`.agents/agents/<name>.md`. Verify against any format documentation found in
Phase 2.

#### 3.3 Initialize External-Dependency Cache

Create or update `.agent-state/external-dependencies.json` using the paths
from the collected input.

If the file does not exist, create it:

```json
{
  "version": 1,
  "updated_at": "<ISO 8601 timestamp now>",
  "items": {}
}
```

Add or update these entries (preserving other entries in update mode):

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

#### 3.4 Deploy Additional Skills (If Selected)

If the collected input includes `import_skills`:

**Local directory (`type: "local"`):**
1. Scan the provided `path` for `**/SKILL.md` files.
2. For each skill found, create a directory symlink from each selected
   platform's `skills/` directory to the skill's source directory.
3. Use the same symlink approach as in 3.1.
4. Report each skill deployed and its source path.

**Online source (`type: "online"`):**
1. Fetch the skill listing from the `url`.
2. Report what is available and instruct the user on platform-specific
   installation commands.
3. Do not attempt to automate online installation; the mechanism varies by
   platform.

### Phase 4: Verify

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
| Script exits with error (user cancelled or path invalid) | Stop. Report the exit reason. Do not proceed with partial input. |
| Collected input validation fails | Report which field failed and why. Ask the user to re-run the script. |
| Platform format cannot be determined (Phase 2) | Report which platform and skip it. Proceed with the remaining platforms. Do not guess. |
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
- [ ] Platform subagent formats were researched and confirmed before generation.
- [ ] All selected platforms have valid skill symlinks pointing to `agent-discipline/skills/`.
- [ ] All selected platforms have platform-native subagent files derived from `agent-discipline/subagents/`.
- [ ] `.agent-state/external-dependencies.json` exists with `env.s32ds` and `env.rtd`.
- [ ] Additional skills (if requested) deployed as symlinks.
- [ ] Reset mode: only project-level content cleared; user-level/global intact.
- [ ] No generated files staged in Git.
