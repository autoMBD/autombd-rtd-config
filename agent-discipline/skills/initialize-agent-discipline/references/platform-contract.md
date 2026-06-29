# Agent Platform Deployment Contract

| Field | Value |
| --- | --- |
| Version | 0.2.1 |
| Date | 2026-06-29 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Authoritative project-level Skill and subagent deployment contract for Claude Code, OpenCode, and Codex. |

## Source authority

The four files under `agent-discipline/subagents/` are canonical Claude Code
subagent definitions. Preserve their YAML frontmatter and Markdown bodies.
Generate OpenCode and Codex definitions from these sources; never rewrite the
canonical files into a cross-platform or platform-neutral schema.

Agent-discipline Skills are canonical directories under
`agent-discipline/skills/<name>/`. Deploy them only through directory symbolic
links or Windows junctions. Never copy a Skill directory.

The copy prohibition applies only to Skill directory trees. Subagents are
single-file generated artifacts: parse the canonical Claude definition,
render the selected platform format in memory, validate it, and atomically
replace the target file only when its bytes differ. Never use an AI rewrite or
manual free-form conversion during deployment.

## Target paths

| Platform | Project Skills | Project subagents |
| --- | --- | --- |
| Claude Code | `.claude/skills/<name>/SKILL.md` | `.claude/agents/<name>.md` |
| OpenCode | Reuse `.agents/skills/<name>/SKILL.md` or `.claude/skills/<name>/SKILL.md`; do not create `.opencode/skills/` | `.opencode/agents/<name>.md` |
| Codex | `.agents/skills/<name>/SKILL.md` | `.codex/agents/<name>.toml` |

### OpenCode Skill target selection

OpenCode natively discovers both `.agents/skills/` and `.claude/skills/`.
Select its Skill source deterministically:

1. If Codex is selected, reuse `.agents/skills/`.
2. Otherwise, if Claude Code is selected, reuse `.claude/skills/`.
3. If OpenCode is the only selected platform, deploy the Skill links to
   `.agents/skills/`.
4. Never create `.opencode/skills/`.

When Claude Code and Codex are both selected, each platform still requires its
own native Skill directory. OpenCode may observe the same canonical Skill
through both compatible locations; do not create a third copy or link.

## Selected local Skill contract

Version 2 initialization input records the explicit GUI choice in
`additional_skill_workflows`. Its value is `skip` or one or both of `local` and
`online`; `skip` is mutually exclusive and the field must never be omitted.

When the local workflow is selected, `local_skill_import` describes local Skill
deployment. It contains:

- `roots`: one or more canonical absolute source roots selected in the GUI;
- `selected`: one or more objects containing the exact manifest `name` and
  canonical `source` directory selected by the user.

Prevalidate selected local Skills only. Every selected source must exist below
one of the submitted roots, contain `SKILL.md`, retain the submitted name, and
be unique by name and canonical source. A different source using the same name
as another selected or canonical Skill is fatal before mutation.

The deployer never rescans the roots to add unselected Skills. It deploys
selected local Skills only, using a directory symbolic link or Windows junction
at every applicable project target. It never copies a Skill directory or any
file within one. Verification resolves each target and compares its
`SKILL.md` with the exact submitted source.

A selected local source must not live inside a managed project Skill target
root. Reject that self-referential layout before mutation, especially in Reset
mode where the managed root will be removed. An existing ordinary directory is
never accepted as an already-deployed Skill even when it is also the submitted
source; every deployed target must remain a symbolic link or junction.

Legacy version 1 `import_skills.type = local` input may remain readable during
migration, but every new GUI transaction emits version 2 selection data.

## Online and supplemental orchestration boundary

`online_skill_request` and `supplemental_task` are orchestration fields, not
deployment inputs; online Skill installation is outside this contract. The
orchestrating Agent uses `find-skills` to install requested Skills in the
user-level Agent environment after project verification. The deterministic
deployer does not use the network, write user-level paths, or create project
links for online Skills.

The orchestrating Agent evaluates `supplemental_task` only after deployment,
verification, and requested online installation succeed. Out-of-scope work is
reported and requires explicit user confirmation before it is executed as a
separate task.

## Required Python tool evidence

Python is a required external tool for repository initialization scripts. The
orchestrating Agent checks Python automatically before launching the GUI and
must not request a Python path from the user. If Python is unavailable, the
workflow stops before filesystem mutation and instructs the user to install
Python.

When deployment succeeds, the deterministic deployer records the active
interpreter in `.agent-state/external-dependencies.json` as `tool.python` with
`status: available`, the resolved interpreter path, version evidence,
timestamp, and verifier. Preserve unrelated cache entries.

## Subagent transformations

Use the repository's deterministic deployment script with separate renderers
for Claude Code, OpenCode, and Codex. Parse each canonical file once into
`name`, `description`, `tools`, `model`, and Markdown body. Reject malformed
frontmatter, duplicate fields, unsupported fields, and unknown tools before
writing any target.

Generate all selected-platform outputs in memory first. Validate the complete
output set, then write each changed file through a temporary file in the target
directory followed by an atomic replace. Leave byte-identical targets untouched
and preserve unrelated files.

### Claude Code

Write each canonical template byte-for-byte to
`.claude/agents/<name>.md`. The source YAML frontmatter contains the native
Claude Code fields `name`, `description`, `tools`, and `model`; the Markdown
body is the subagent system prompt.

### OpenCode

Write `.opencode/agents/<name>.md` as YAML frontmatter plus the unchanged
Markdown body.

- Infer the agent name from the filename; omit `name` from frontmatter.
- Copy `description` unchanged.
- Set `mode: subagent`.
- Omit the Claude model alias. OpenCode inherits the invoking primary agent's
  model unless an explicit provider-qualified model is supplied by a future
  project requirement.
- Do not add `$schema`; it belongs in `opencode.json`, not agent Markdown.
- Translate Claude tools to OpenCode permissions:

| Claude tool | OpenCode permission |
| --- | --- |
| `Read` | `read: allow` |
| `Edit` or `Write` | `edit: allow` |
| `Bash` | `bash: allow` |
| `Grep` | `grep: allow` |
| `Glob` | `glob: allow` |
| `WebFetch` | `webfetch: allow` |

Start the permission map with `"*": deny`, then add the translated allow
entries. Reject an unknown Claude tool instead of silently broadening access.

### Codex

Write `.codex/agents/<name>.toml`. Each file contains:

- `name`: copied from Claude frontmatter;
- `description`: copied unchanged;
- `developer_instructions`: the unchanged Markdown body;
- `sandbox_mode = "read-only"` when neither `Edit` nor `Write` is present;
- `sandbox_mode = "workspace-write"` when `Edit` or `Write` is present.

Do not copy Claude's `model` alias into Codex TOML. Omitted model and reasoning
settings inherit from the parent Codex session. Serialize strings using valid
TOML escaping and validate every generated file with Python `tomllib`.

## Update, reset, and migration

Update mode preserves unrelated project-local Agent files and cache entries,
but replaces a selected platform's generated subagent file only when generated
content differs.

Reset mode removes only selected project-level targets:

- Claude Code: `.claude/skills/`, `.claude/agents/`;
- OpenCode: `.opencode/agents/`; compatible Skill links are shared and are
  verified/reused instead of deleted;
- Codex: `.agents/skills/`, `.codex/agents/`;
- shared state: `.agent-state/` after confirmed reset.

During update or reset, remove obsolete entries generated by the old
initializer when their corresponding platform is selected:

- the four known `.agents/agents/<name>.md` files for Codex;
- Skill links under `.opencode/skills/<name>/` that resolve to the canonical
  `agent-discipline/skills/<name>/` directories for OpenCode.

Do not delete an obsolete parent directory unless it is empty. Preserve
unknown files, unrelated links, and user-created project configuration.

Never remove user-level paths such as `~/.claude/`,
`~/.config/opencode/`, `~/.agents/`, or `~/.codex/`.

## Verification requirements

Initialization passes only when all selected-platform checks succeed:

1. Every Skill target is a symbolic link or junction whose target contains
   `SKILL.md`.
2. No canonical agent-discipline Skill link remains under
   `.opencode/skills/` after OpenCode deployment; unrelated content is
   preserved.
3. Claude files are byte-identical to their canonical templates.
4. OpenCode files contain only the documented generated fields, retain the
   exact Markdown body, contain no `$schema`, and enforce the translated tool
   permissions.
5. Codex files exist under `.codex/agents/`, parse as TOML, contain all three
   required identity/instruction fields, preserve the exact body, and use the
   expected sandbox mode.
6. The four obsolete Codex Markdown files and obsolete OpenCode
   agent-discipline Skill links are absent for selected platforms.
7. `.agent-state/external-dependencies.json` is valid JSON and contains only
   non-secret evidence supplied or verified during initialization, including
   `tool.python`, `env.s32ds`, and `env.rtd`.
8. Generated paths are ignored by Git and do not appear in `git status`.

## Changelog

| Version | Date | Changes |
| --- | --- | --- |
| 0.2.1 | 2026-06-29 | Added required Python check and `tool.python` cache evidence. |
| 0.2.0 | 2026-06-25 | Added V2 additional Skill workflows: selected local links, user-level online install, and supplemental task boundary. |
| 0.1.0 | 2026-06-24 | Initial platform deployment contract. |
