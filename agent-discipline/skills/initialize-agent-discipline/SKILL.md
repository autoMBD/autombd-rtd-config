---
name: initialize-agent-discipline
description: Initialize or reset this project's Claude Code, OpenCode, and Codex Agent discipline. Use after a clean clone, when project-level Skills/subagents or the external-dependency cache are missing or stale, when the user requests an Agent environment update/reset, or when importing additional Skills.
---

# Initialize Agent Discipline

## Purpose

Run a GUI-first, user-directed initialization transaction that deploys the
repository's Agent-discipline Skills and four role definitions to every platform
the user selects, then records the required reusable environment evidence.

This Skill is orchestrated by the Agent, but input collection and deployment are
implemented by the repository's deterministic tools. Always use the repository
GUI collector at `tools/init_agent_env.py`; do not substitute an Agent-native
question window, conversational prompts, or inferred defaults. Apply the saved
input with `tools/deploy_agent_env.py`.

Before deployment, read
[`references/platform-contract.md`](references/platform-contract.md) completely.
It is authoritative for target paths, native schemas, deterministic
transformations, migration boundaries, and verification. This Skill remains
authoritative for the user-input workflow and completion criteria.

## Non-negotiable interaction rules

- Always launch the repository GUI collector with `--gui` and save its validated
  result before changing the filesystem, including on a clean checkout.
- The Agent must not infer target platforms from the platform currently running
  the session. "Current Agent environment" means the project-level environment
  selected by the user, not automatically Codex, Claude Code, or OpenCode.
- The Agent must not infer the operation mode. The user explicitly selects
  Update or Reset in the GUI. A recommended or preselected value is not a
  submitted choice.
- S32DS and RTD paths are required. On a clean checkout, both must be entered
  and verified. On an initialized checkout, valid cached values may prefill the
  GUI, but the user must confirm or replace them.
- Do not turn missing dependency paths into empty values, do not omit the cache
  entries, and do not scan broad local directories to guess installations.
- Do not replace the repository GUI with Agent-native GUI controls, CLI text
  prompts, conversational assumptions, or hand-authored input JSON. If the
  repository GUI cannot open, stop before mutation and report the exact error.
- Do not deploy anything until the GUI input is complete and validated.

## Boundaries

Manage project-local content only:

| Platform | Skills | Subagents |
| --- | --- | --- |
| Claude Code | `.claude/skills/<name>/` | `.claude/agents/<name>.md` |
| OpenCode | Reuse `.agents/skills/<name>/` or `.claude/skills/<name>/`; never create `.opencode/skills/` | `.opencode/agents/<name>.md` |
| Codex | `.agents/skills/<name>/` | `.codex/agents/<name>.toml` |

Also manage `.agent-state/external-dependencies.json`. Never modify user-level
locations such as `~/.claude/`, `~/.config/opencode/`, `~/.agents/`, or
`~/.codex/`.

The released `autombd-rtd/` Skill is outside this workflow and is deployed by
`tools/deploy_rtd_skill.py`.

## Sources

| Purpose | Path |
| --- | --- |
| Canonical Agent-discipline Skills | `agent-discipline/skills/<name>/SKILL.md` |
| Canonical Claude Code subagents | `agent-discipline/subagents/<name>.md` |
| Repository GUI collector | `tools/init_agent_env.py` |
| Deterministic deployer | `tools/deploy_agent_env.py` |
| Platform deployment contract | `agent-discipline/skills/initialize-agent-discipline/references/platform-contract.md` |
| External-dependency rules | `agent-discipline/skills/external-dependency-memory/SKILL.md` |

The four canonical subagent files are Claude Code definitions. Preserve their
frontmatter and bodies. Generate native OpenCode Markdown and Codex TOML from
the same parsed sources according to the platform contract.

Deploy every Skill directory through a directory symbolic link or Windows
junction. Never copy a Skill directory. Generated single-file subagent
artifacts are not subject to the Skill-directory copy prohibition.

## Workflow

### 1. Pre-check without mutation

Read `.agent-state/external-dependencies.json` when present. Reuse only current,
available `env.s32ds` and `env.rtd` evidence as GUI defaults; cached evidence
never replaces user confirmation.

Inspect only these project locations:

- `.claude/skills/`, `.claude/agents/`;
- `.opencode/agents/` and obsolete canonical links under `.opencode/skills/`;
- `.agents/skills/` and obsolete files under `.agents/agents/`;
- `.codex/agents/`;
- `.agent-state/`.

The pre-check establishes current state only. It does not authorize choosing a
platform, choosing Update, or skipping the GUI.

### 2. Collect all choices through the repository GUI

#### Windows/Codex desktop launch

Do not run `python ... --gui` directly inside the Agent sandbox or a background
PTY. That process may not attach to the user's interactive desktop, so the
command can remain alive without displaying a window.

For Codex on Windows, run the following PowerShell block through
`exec_command` with `sandbox_permissions: "require_escalated"` and a
justification that the Tkinter form must attach to the user's interactive
desktop. Start the real Python executable with a normal visible window, retain
the process handle, and wait for the user to submit or cancel:

```powershell
$repoRoot = (Get-Location).Path
$pythonExe = (Get-Command python.exe -ErrorAction Stop).Source
$scriptPath = (Resolve-Path '.\tools\init_agent_env.py').Path
$stateDir = Join-Path $repoRoot '.agent-state'
$pendingInput = Join-Path $stateDir 'init-input.pending.json'
$finalInput = Join-Path $stateDir 'init-input.json'

New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
if (Test-Path -LiteralPath $pendingInput) {
    Remove-Item -LiteralPath $pendingInput -Force
}

$arguments = @(
    ('"{0}"' -f $scriptPath),
    '--gui',
    '--output',
    ('"{0}"' -f $pendingInput)
)
$guiProcess = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList $arguments `
    -WorkingDirectory $repoRoot `
    -WindowStyle Normal `
    -PassThru `
    -Wait

if ($guiProcess.ExitCode -ne 0) {
    throw "Agent environment GUI exited with code $($guiProcess.ExitCode)."
}
if (-not (Test-Path -LiteralPath $pendingInput)) {
    throw 'Agent environment GUI exited without producing input.'
}

& $pythonExe $scriptPath --input $pendingInput --validate-only
if ($LASTEXITCODE -ne 0) {
    throw 'Agent environment GUI produced invalid input.'
}
Move-Item -LiteralPath $pendingInput -Destination $finalInput -Force
```

Never use `-WindowStyle Hidden`, omit `-Wait`, or treat a still-running process
as successful collection. If the tool call yields a running process/session,
wait on that same process until it exits; do not launch a second GUI.

On other desktop platforms, use the platform's approved external-process method
that attaches Tkinter to the interactive display, wait for exit, and apply the
same pending-file checks. Do not use the collector's text mode for Agent
initialization. If the user cancels or the GUI exits without producing valid
input, stop without deployment.

The Windows block already validates and promotes the pending file. Before
deployment, the final input may be revalidated idempotently with:

```powershell
python tools\init_agent_env.py `
  --input .agent-state\init-input.json `
  --validate-only
```

Collect and validate every field below before deployment:

1. **Target platforms** — multi-select one or more of `claude`, `opencode`, and
   `codex`. No selection is an error; do not substitute the current platform.
2. **Operation mode** — explicitly choose Update or Reset.
3. **S32DS installation root** — absolute path to an existing directory that
   contains an expected S32DS marker such as `eclipse/` or `S32DS/`.
4. **RTD installation root** — absolute path to an existing directory that
   contains RTD package directories matching `*_TS_T*`.
5. **Additional Skills** — explicitly choose Skip, import from a local
   directory, or install from an online source. Skip is a valid explicit choice;
   a missing answer is not.
6. **Reset confirmation** — required only for Reset and must show the exact
   selected project-local paths that will be removed.

Normalize confirmed paths only after validation. If either dependency path is
missing or invalid, keep the workflow at input collection and request a
corrected value. Never cache unverified paths.

### 3. Resolve additional Skills

For a local import, recursively find `SKILL.md`, validate that each manifest
`name` matches its directory name, resolve the canonical source, and include the
Skill in the same target roots as canonical Skills. A name collision with a
different source is fatal.

For an online import, show the requested URL and use the appropriate platform
installation workflow only after explicit user approval. After installation,
resolve the installed local source and deploy project links to that source.
Never silently download or execute arbitrary content.

### 4. Prevalidate the complete deployment

Before the first mutation:

1. validate all GUI answers and both dependency paths;
2. parse every canonical subagent template once;
3. render every selected-platform subagent output in memory;
4. validate Claude bytes, OpenCode frontmatter/permissions, and Codex TOML;
5. validate all managed destinations remain inside the repository;
6. reject an ordinary directory, regular file, or wrong link at a managed
   Skill-link destination;
7. prepare the complete external-dependency cache update containing both
   `env.s32ds` and `env.rtd` while preserving unrelated entries in Update mode.

Any prevalidation failure stops the transaction before filesystem mutation.

### 5. Apply the selected transaction

Apply the complete validated input with the deterministic deployer:

```powershell
python tools\deploy_agent_env.py `
  --input .agent-state\init-input.json `
  --repo-root . `
  --verified-by codex
```

Replace `codex` with the actual orchestrating platform name when another Agent
platform runs the workflow. The target platform set still comes exclusively
from the GUI input.

For **Update**:

- preserve unrelated project-local files and cache entries;
- create or verify selected Skill links;
- atomically write only changed native subagent files;
- update both confirmed environment cache entries;
- remove only known obsolete outputs covered by the platform contract.

For **confirmed Reset**:

- remove the selected platforms' project-level Agent targets shown in the GUI;
- clear `.agent-state/`;
- rebuild all selected Skill links and native subagent files;
- rebuild `.agent-state/external-dependencies.json` with the confirmed S32DS and
  RTD evidence;
- never touch user-level or global Agent configuration.

Use stable cache keys and conservative evidence:

- `env.s32ds`: `status: available`, confirmed normalized S32DS root, directory
  structure verification evidence, timestamp, and current verifier;
- `env.rtd`: `status: available`, confirmed normalized RTD root, RTD package
  verification evidence, timestamp, and current verifier.

Other external tools remain outside initialization scope and are cached on
demand under the `external-dependency-memory` rules.

### 6. Verify and close out

Run the focused Agent-environment tests:

```powershell
python -m pytest tests\unit\test_deploy_agent_env.py `
  tests\unit\test_agent_skill_contract.py -q
git diff --check
git status --short
```

Confirm all of the following:

- every selected Skill target is a symlink or junction resolving to a source
  containing `SKILL.md`;
- every canonical role has a valid native subagent file for every selected
  platform;
- Claude files are byte-identical to canonical templates;
- OpenCode files contain `description`, `mode`, translated `permission`, no
  `$schema`, and the unchanged body;
- Codex files parse as TOML and contain `name`, `description`,
  `developer_instructions`, and the expected `sandbox_mode`;
- known obsolete Codex/OpenCode outputs are absent;
- `.agent-state/external-dependencies.json` is valid JSON and contains verified
  `env.s32ds` and `env.rtd` entries;
- generated project-level Agent files and caches remain ignored and unstaged.

Initialization is complete only when the GUI input is complete, deployment
succeeds for every selected platform, both dependency entries are cached, and
all verification checks pass. Partial deployment or a missing cache entry is a
failed initialization, not a successful reduced mode.

Restart or open a new session on platforms that load subagent definitions only
at session start.

## Failure handling

| Failure | Required action |
| --- | --- |
| Repository GUI unavailable or cancelled | Stop before mutation; report the exact collector error. |
| No target platform selected | Return to the GUI; never select the current platform automatically. |
| Operation mode not submitted | Return to the GUI; never assume Update. |
| S32DS or RTD path missing/invalid | Return to the GUI for a corrected path; never scan or cache an empty value. |
| Reset unconfirmed | Stop before filesystem mutation. |
| Canonical template malformed or tool unknown | Stop before filesystem mutation and report the exact source error. |
| Skill destination is an ordinary path or wrong link | Stop; never replace it implicitly or fall back to copying. |
| Symlink and Windows junction creation both fail | Stop and request Developer Mode or suitable permissions. |
| Generated native subagent fails validation | Stop before writing any generated output. |
| Online Skill source selected | Obtain explicit approval and resolve a trusted local installed source before linking. |
| Any selected platform fails deployment or verification | Report initialization as failed; do not claim partial success. |

## Completion checklist

- [ ] Platform contract and external-dependency-memory Skill were read.
- [ ] Repository GUI collected an explicit platform set and operation mode.
- [ ] S32DS and RTD paths were explicitly confirmed and verified.
- [ ] Additional-Skill choice was explicitly collected.
- [ ] Reset, if selected, showed its exact scope and was explicitly confirmed.
- [ ] Complete deployment was prevalidated before mutation.
- [ ] Skill targets are links/junctions, never copied directories.
- [ ] Every selected platform has all four native subagent files.
- [ ] Known obsolete generated entries were removed narrowly.
- [ ] Dependency cache contains verified `env.s32ds` and `env.rtd` entries.
- [ ] Focused tests and Git hygiene checks pass.
