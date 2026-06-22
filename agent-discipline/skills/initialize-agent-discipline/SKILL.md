---
name: initialize-agent-discipline
description: Initialize the project-level Agent environment for the RTD CfgFile CLI project. Use when starting development from a clean clone, when the project-level Agent environment has not been initialized, when the user requests an update or reset of the Agent discipline, or when the user requests importing additional skills.
---

# Initialize Agent Discipline

## Overview

Use this skill to set up or maintain the project-level Agent environment for
this project. It deploys agent-discipline skills, subagent templates, and
external-dependency memory to the target Agent platforms so that every agent
working in this checkout operates from the same project discipline.

This skill is a set of agent instructions, not a standalone program or script.
The agent executes each step using its own native tools — structured GUI input,
filesystem operations, and file writes — without any dedicated initialization
scripts or separate GUI applications.

## Trigger Conditions

This skill should be loaded and executed when:

- Development starts from a clean clone and no platform-specific project
  directories (`.claude/`, `.opencode/`, `.codex/`) exist.
- The project-level Agent environment has not been initialized (missing skills,
  subagents, or external-dependency cache).
- The user explicitly requests an update or reset of the Agent discipline.
- The user requests importing additional skills from local or online sources.

## Boundaries

This skill manages the project-level Agent environment ONLY:

- **Project-level directories:** `.claude/`, `.opencode/`, `.codex/` for skills
  and subagents, plus `.agent-state/` for the external-dependency cache.
- **NOT user-level or global Agent environments** (e.g. `~/.claude/`,
  `~/.config/opencode/`, `~/.codex/`). Those belong to the user and must not
  be modified.
- **NOT the `autombd-rtd/` skill payload** — that is deployed separately by
  `tools/deploy_rtd_skill.py` and is outside this skill's scope.

## Files and Paths Reference

### Source paths (committed in repository)
| Content | Path |
| --- | --- |
| Agent-discipline skills | `agent-discipline/skills/<name>/SKILL.md` |
| Subagent templates (Claude format) | `agent-discipline/subagents/<name>.md` |
| External-dependency cache (if exists) | `.agent-state/external-dependencies.json` |

### Target paths per platform (generated, NOT committed)
| Platform | Skills directory | Subagents directory |
| --- | --- | --- |
| Claude | `.claude/skills/<name>/` | `.claude/agents/<name>.md` |
| OpenCode | `.opencode/skills/<name>/` | `.opencode/agents/<name>.md` |
| Codex | `.codex/skills/<name>/` | `.codex/agents/<name>.md` |

All generated files under `.claude/`, `.opencode/`, `.codex/`, and
`.agent-state/` are covered by `.gitignore` and must never be committed.

## Workflow

### Step 1: Collect Target Platforms

Use the agent platform's native structured GUI input capability
(e.g. the `question` tool) to let the user select which Agent platforms to
initialize. Support multiple selection:

- **Claude** — Claude Code (VS Code extension); skills + subagents go under
  `.claude/`.
- **OpenCode** — opencode CLI; skills + subagents go under `.opencode/`.
- **Codex** — OpenAI Codex CLI; skills + subagents go under `.codex/`.

Question example:

```
question: "Select the target Agent platforms to initialize."
header: "Target Platforms"
options:
  - label: "Claude"
  - label: "OpenCode"
  - label: "Codex"
multiple: true
```

If no platform is selected, stop and report that at least one platform must
be chosen.

### Step 2: Select Operation Mode

Use native structured GUI input to let the user choose between **Update** and
**Reset** mode:

```
question: "Select the operation mode."
header: "Operation Mode"
options:
  - label: "Update"
    description: "Preserve existing environment; change only what is explicitly selected or entered in this operation."
  - label: "Reset"
    description: "Clear project-level Agent environment and .agent-state/ cache for the selected platforms, then reinitialize from current input."
```

#### Update Mode Rules

- **Preserve** all existing project-level Agent files and `.agent-state/`
  cache entries that are not explicitly touched in this operation.
- **Deploy or update** only the platforms, skills, subagents, and cache entries
  that the user explicitly selects or enters.
- If a symlink destination already exists and points to the correct source,
  skip it (no change).
- If a subagent file already exists, overwrite it with the converted content
  only if the source template has changed.

#### Reset Mode Rules

- **Clear only** the project-level Agent environment for the selected
  platforms — delete their skill symlinks and generated subagent files.
- **Clear** the current project's `.agent-state/` directory entirely.
- **Do NOT affect** any user-level or global Agent environment
  (`~/.claude/`, `~/.config/opencode/`, `~/.codex/`).
- **Before deleting anything**, show the exact scope of what will be cleared
  and obtain explicit user confirmation via native GUI.

Reset scope confirmation example:

```
question: "Reset will delete the following. Confirm?"
header: "Reset Confirmation"
options:
  - label: "Confirm Reset"
    description: "Selected platforms: Claude, OpenCode. Will delete .claude/skills/, .claude/agents/, .opencode/skills/, .opencode/agents/, .agent-state/ entirely."
  - label: "Cancel"
    description: "Abort the reset and return to mode selection."
```

After confirmation, delete the listed directories and files, then proceed
with reinitialization from the user's current input.

### Step 3: Collect S32DS and RTD Paths

Use native structured GUI input to collect the S32 Design Studio installation
root and the RTD installation path. These are required for the
external-dependency cache.

Use free-text input fields:

```
question: "Enter the S32 Design Studio installation root path."
header: "S32DS Path"
options:
  - label: "Enter path manually"
    description: "Provide the absolute path to the S32DS installation root (e.g. C:\\NXP\\S32DS.3.6.7)"
```

```
question: "Enter the RTD installation path."
header: "RTD Path"
options:
  - label: "Enter path manually"
    description: "Provide the absolute path to the RTD package root (e.g. C:\\NXP\\S32DS.3.6.7\\S32DS\\software\\PlatformSDK_S32K3\\RTD)"
```

For each path provided, verify:
1. The path exists on the filesystem.
2. For S32DS: the directory contains expected subdirectories
   (e.g. `eclipse/`, `S32DS/`).
3. For RTD: the directory contains RTD module packages
   (directories matching `*_TS_T*`).

If verification fails, report the specific problem and ask for a corrected
path. Do not cache unverified paths.

### Step 4: Import Additional Skills (Optional)

Ask whether the user wants to import additional skills:

```
question: "Import additional skills?"
header: "Additional Skills"
options:
  - label: "Skip"
    description: "Do not import additional skills."
  - label: "Import from local directory"
    description: "Import skills from a specified local directory."
  - label: "Install from online source"
    description: "Install skills from a specified online source URL."
```

#### Import from Local Directory

1. Ask for the local directory path.
2. Verify the directory exists and contains `**/SKILL.md` files.
3. For each skill found, create a symlink from the platform's skill directory
   to the source skill directory.
4. If the source directory contains symlinks, resolve them before linking
   (prefer the canonical path).

#### Install from Online Source

1. Ask for the online source URL.
2. Fetch the skill listing or manifest from the URL.
3. For each skill, instruct the user on the installation command appropriate
   for their platform. Online skill installation is platform-specific and
   outside the scope of filesystem symlink operations; report what was
   registered and any manual steps the user must complete.

### Step 5: Execute Deployment

After collecting all inputs, execute the deployment for each selected platform.

#### 5.1 Reset Cleanup (Reset Mode Only)

If in Reset mode and after user confirmation, delete:
- For each selected platform: `{platform_dir}/skills/` and
  `{platform_dir}/agents/` (where `platform_dir` is `.claude`, `.opencode`,
  or `.codex`).
- `.agent-state/` directory entirely.

#### 5.2 Deploy Agent-Discipline Skills (Symlinks)

For each skill directory under `agent-discipline/skills/`:

1. Create the target platform's skill directory if it does not exist:
   `{platform_dir}/skills/`
2. Create a directory symlink (or junction on Windows) from
   `{platform_dir}/skills/<skill-name>/` to the source directory
   `agent-discipline/skills/<skill-name>/`.
3. **Copying is prohibited.** If a symlink cannot be created, report the error
   and stop. On Windows, symlink creation requires Developer Mode enabled or
   administrator privileges. On failure, instruct the user to enable Developer
   Mode or run the shell as administrator.
4. Skip skills that are already correctly linked (destination exists and
   resolves to the same source).

Windows symlink commands:

```powershell
# Directory symlink (preferred, requires Developer Mode or admin)
New-Item -ItemType SymbolicLink -Path ".claude\skills\external-dependency-memory" -Target "agent-discipline\skills\external-dependency-memory"

# Fallback: directory junction (does not require Developer Mode)
cmd /c mklink /J ".claude\skills\external-dependency-memory" "agent-discipline\skills\external-dependency-memory"
```

On non-Windows systems (macOS, Linux):
```bash
ln -s "$(pwd)/agent-discipline/skills/external-dependency-memory" ".claude/skills/external-dependency-memory"
```

Use absolute source paths when creating symlinks to ensure the link remains
valid regardless of the working directory.

#### 5.3 Deploy Subagents

The subagent templates under `agent-discipline/subagents/` are in **Claude
format** — YAML frontmatter with `name`, `description`, `model`, `mode`,
and `permission` fields followed by a Markdown body.

##### Claude Deployment

Claude Code can consume the templates directly. For each template:

1. Create `.claude/agents/` if it does not exist.
2. Write the template content as-is to `.claude/agents/<name>.md` (extract
   `name` from the frontmatter).
3. If the destination file already exists and is identical to the source,
   skip it.

##### OpenCode Deployment

Convert each Claude-format template to OpenCode format:

1. Create `.opencode/agents/` if it does not exist.
2. Parse the frontmatter from the source template.
3. Generate an OpenCode agent file with this frontmatter transformation:
   - **Remove** the `name` field (OpenCode infers the name from the filename).
   - **Remove** the `model` field, or set it to the project's default model.
     If the surrounding agent context provides a default model, use that;
     otherwise omit the field to let OpenCode use its configured default.
   - **Keep** `description`, `mode`, and `permission` fields as-is.
   - **Add** `"$schema": "https://opencode.ai/config.json"` for editor
     validation support.
   - Map `permission` values: Codex uses `allow`/`deny`; OpenCode supports
     `allow`/`ask`/`deny`. The `allow` and `deny` values are directly
     compatible.
   - Write the frontmatter in YAML, followed by `---`, followed by the Markdown
     body unchanged.
4. Write to `.opencode/agents/<name>.md`.

Example OpenCode conversion for the `explorer` template:

```markdown
---
description: Read-only investigator that establishes ground-truth facts...
mode: subagent
permission:
  read: allow
  grep: allow
  glob: allow
  bash: allow
  webfetch: allow
  edit: deny
  task: deny
---
(original markdown body from template)
```

##### Codex Deployment

Convert each Claude-format template to Codex CLI format:

1. Create `.codex/agents/` if it does not exist.
2. Parse the frontmatter from the source template.
3. Generate a Codex agent file:
   - **Keep** `name` and `description` fields.
   - **Remove** the `model` field or set it to the default provided by the
     agent context.
   - **Keep** `mode` (typically `subagent`).
   - **Keep** `permission` fields (Codex uses `allow`/`deny`).
4. If the exact Codex agent file format available in the agent's current
   context differs from the above, apply the current format definition.
5. Write to `.codex/agents/<name>.md`.

#### 5.4 Initialize External-Dependency Cache

Create or update `.agent-state/external-dependencies.json` with the S32DS
and RTD paths collected in Step 3.

If the file does not exist, create it with this structure:

```json
{
  "version": 1,
  "updated_at": "<ISO 8601 timestamp now>",
  "items": {}
}
```

Then add or update entries (preserving other existing entries in Update mode):

**S32DS entry:**
```json
"env.s32ds": {
  "kind": "env",
  "status": "available",
  "location": "<user-provided S32DS root path, normalized with forward slashes>",
  "evidence": "User provided installation path and verified directory exists during agent discipline initialization.",
  "verified_at": "<ISO 8601 timestamp now>",
  "verified_by": "<current platform name: codex|claude|opencode>"
}
```

**RTD entry:**
```json
"env.rtd": {
  "kind": "env",
  "status": "available",
  "location": "<user-provided RTD path, normalized with forward slashes>",
  "evidence": "User provided RTD path and verified directory exists during agent discipline initialization.",
  "verified_at": "<ISO 8601 timestamp now>",
  "verified_by": "<current platform name: codex|claude|opencode>"
}
```

Follow the recording rules from the `external-dependency-memory` skill:
- Use stable item keys (`env.s32ds`, `env.rtd`).
- Write conservative evidence (path exists, directory structure verified).
- Never record tokens, passwords, or credentials.
- In Update mode, keep all other cache entries unchanged.

#### 5.5 Deploy Additional Skills (If Selected)

For each additional skill from Step 4:

**Local directory import:**
1. Scan the user-provided directory for `**/SKILL.md` files.
2. For each skill found, create a directory symlink from each selected
   platform's `skills/` directory to the skill's source directory.
3. Use the same symlink approach as in Step 5.2.
4. Report each skill deployed and its source path.

**Online source install:**
1. Fetch the skill listing from the URL.
2. Report what is available and instruct the user on platform-specific
   installation commands.
3. Do not attempt to automate online skill installation; the mechanism varies
   by platform.

### Step 6: Verify

After deployment, run these verifications:

1. **Symlink integrity:** For each deployed skill symlink, verify the
   destination exists and points to the intended source directory containing
   a `SKILL.md` file.

2. **Subagent file presence:** For each deployed platform, verify that every
   template from `agent-discipline/subagents/` has a corresponding file in
   the platform's agents directory.

3. **Cache file validity:** Verify `.agent-state/external-dependencies.json`
   is valid JSON and contains the expected `env.s32ds` and `env.rtd` entries
   with `status: "available"`.

4. **Git exclusion:** Verify no generated files under `.claude/`, `.opencode/`,
   `.codex/`, or `.agent-state/` appear in `git status` as untracked files
   (they should be covered by `.gitignore`).

If any verification fails, report the specific failure and offer to retry
the affected step.

## Error Handling

- **Symlink creation fails on Windows:** Instruct the user to enable Developer
  Mode (Settings → Update & Security → For developers → Developer Mode) or
  run the shell as administrator. Do not fall back to copying.
- **Path verification fails:** Report which path check failed and why. Ask
  the user for a corrected path rather than proceeding with unverified data.
- **Template frontmatter is malformed:** Report which template file is
  malformed and the specific parsing error. Skip that template; proceed with
  the remaining templates.
- **Git exclusion fails:** If generated files appear in `git status`, check
  `.gitignore` coverage and add the missing pattern. Do not commit the
  generated files.

## Closeout Checklist

Before reporting completion:

- [ ] All selected platforms have their `skills/` directory populated with
  valid symlinks to `agent-discipline/skills/`.
- [ ] All selected platforms have their `agents/` directory populated with
  platform-appropriate subagent files derived from
  `agent-discipline/subagents/`.
- [ ] `.agent-state/external-dependencies.json` exists and contains valid
  `env.s32ds` and `env.rtd` entries.
- [ ] Additional skills (if requested) are deployed as symlinks.
- [ ] In Reset mode, only project-level content was cleared; user-level and
  global Agent environments are intact.
- [ ] No generated files are staged in Git.
- [ ] `git status` shows only expected changes (the skill itself and
  `AGENTS.md` update, if applicable).
