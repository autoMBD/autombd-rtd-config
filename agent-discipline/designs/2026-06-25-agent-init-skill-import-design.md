# Agent Initialization Skill Import Design

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-06-25 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Design for multi-directory local Skill discovery and selection, Agent-orchestrated user-level online Skill installation, and post-initialization supplemental tasks. |

## Objective

Extend the Agent-environment initializer so a user can discover Skills from
multiple local directories, select any subset for project deployment, request
user-level online Skill installation, and provide an optional supplemental
initialization task. Preserve the GUI-first transaction, project-local
deployment boundaries, and link-only local Skill deployment contract.

## Scope

The change covers:

- the repository GUI collector and its structured JSON contract;
- deterministic validation and deployment of selected local Skills;
- the `initialize-agent-discipline` orchestration instructions for online Skill
  installation and supplemental tasks;
- the platform deployment contract and focused unit/contract tests.

It does not make the deterministic deployer search for, download, or install
online Skills. Online Skills are installed in the user's environment by the
orchestrating Agent through `find-skills` and are not linked into the project.

## Architecture

The workflow has three distinct ownership boundaries:

1. The GUI collector gathers explicit user intent and resolves local Skill
   candidates without mutating the Agent environment.
2. The deterministic deployer validates the submitted selection and creates
   project-level directory symbolic links or Windows junctions for selected
   local Skills only.
3. The orchestrating Agent handles online Skill requests and supplemental tasks
   outside the deployer, using the sequencing and confirmation rules in the
   initialization Skill.

Keeping these boundaries separate prevents a user-level online installation
from being mistaken for project deployment and makes the local deployment set
stable between GUI submission and filesystem mutation.

## GUI design

### Local Skills

The Additional Skills section provides:

- an `Add directory...` action that may be used repeatedly;
- a list of added source roots with `Remove directory` and `Rescan` actions;
- a checkbutton list containing every valid Skill found recursively below the
  source roots;
- `Select all` and `Clear all` actions;
- the Skill name and canonical source directory for each candidate.

Adding, removing, or rescanning a root rebuilds the candidate list while
preserving selections for candidates whose canonical source remains present.
Candidates are sorted by Skill name and then source path for deterministic
display and output.

The existing local/online conditional controls must be laid out without using
an unmanaged widget as a Tk `pack(before=...)` reference. Switching import mode
must never raise a Tk callback error, and the local path controls must be
visible immediately after the user selects local import.

### Online Skills

Online installation uses a multiline request field rather than a single URL.
The field accepts one or more Skill names, package references, URLs, or a
natural-language discovery request. The GUI records the request verbatim after
trimming surrounding whitespace. It does not execute a package manager or
resolve an online source.

### Supplemental task

A separate optional multiline field records additional Agent-environment
initialization instructions. Its label states that the task runs only after
the core initialization and online Skill workflow have completed successfully.

## Structured input contract

The collector writes version 2 input. Local and online requests are separate so
the deployer cannot accidentally consume an online request:

```json
{
  "version": 2,
  "platforms": ["codex"],
  "mode": "update",
  "reset_confirmed": false,
  "s32ds_path": "C:/NXP/S32DS.3.6.7",
  "rtd_path": "C:/NXP/S32DS.3.6.7/S32DS/software/PlatformSDK_S32K3/RTD",
  "local_skill_import": {
    "roots": ["D:/skills-a", "D:/skills-b"],
    "selected": [
      {"name": "skill-a", "source": "D:/skills-a/skill-a"},
      {"name": "skill-b", "source": "D:/skills-b/nested/skill-b"}
    ]
  },
  "online_skill_request": "Find and install skill-c and skill-d",
  "supplemental_task": "Initialize the project-local formatter configuration."
}
```

Omit each optional field when its trimmed content is empty. The collector may
read version 1 input for validation compatibility, but newly collected input is
always version 2.

## Local discovery and validation

Local discovery recursively finds files named `SKILL.md`. For each manifest it:

1. resolves the manifest's parent directory to a canonical absolute path;
2. parses a lowercase kebab-case `name` from the YAML frontmatter;
3. requires the manifest name to match the source directory name;
4. deduplicates repeated discovery of the same name and canonical source;
5. reports a blocking conflict when the same name resolves to different source
   directories.

The GUI reports invalid manifests and name conflicts without silently dropping
them. Submission is blocked while a conflict exists or while local import is
selected without at least one selected Skill.

The deployer treats the submitted `selected` entries as authoritative but
revalidates every entry before mutation. Each selected source must still:

- be an existing directory;
- contain `SKILL.md`;
- have the submitted manifest name;
- resolve below one of the submitted source roots;
- remain unique by name and canonical path.

The deployer does not rescan the roots to add unselected Skills. A collision
between a selected local Skill and a canonical Agent-discipline Skill with a
different source is fatal before mutation.

## Link-only deployment

Every selected local Skill is deployed to the selected platforms using the
existing platform target rules. The target is a directory symbolic link or,
on Windows when directory symlink creation is unavailable, a directory
junction. Skill directory contents are never copied.

Prevalidation rejects ordinary files, ordinary directories, stale links, and
links resolving to a different source at managed destinations. Verification
confirms that every resulting target resolves to the selected source's
`SKILL.md`.

## Online Skill workflow

When `online_skill_request` is present, the orchestrating Agent performs the
following after GUI validation and as part of initialization, but outside the
deterministic deployment script:

1. Check whether `find-skills` is available in the current user's Agent
   environment.
2. If unavailable, automatically install `find-skills` through the platform's
   supported user-level Skill installation mechanism, then load it.
3. Use `find-skills` to discover and assess the requested online Skills.
4. Show the resolved Skill identities and user-level installation actions when
   the installation workflow requires approval.
5. Install the selected online Skills into the user-level Agent environment.
6. Record actual success or failure separately from project-level deployment.

The deployer must reject legacy `import_skills.type = online` input with a
message directing the Agent to the orchestration workflow. It never invokes
`npx`, downloads content, writes user-level directories, or creates project
links for online Skills.

## Supplemental task workflow

The orchestrating Agent evaluates `supplemental_task` only after all selected
platform deployments, dependency-cache updates, focused verification, and
requested online Skill installations have completed successfully.

- If the task is within Agent-environment initialization scope, execute it
  under the normal authorization and safety rules.
- If the task is unrelated to Agent-environment initialization, do not execute
  it. Explain the scope mismatch and request explicit confirmation to continue
  as a separate task.
- If initialization fails, preserve the supplemental task in the collected
  input but do not execute it.

Supplemental text is untrusted user input, not a relaxation of repository,
filesystem, network, or external-action permissions.

## Error handling

The GUI keeps the current form state after recoverable validation errors.
Directory scan errors are associated with their source root. Invalid manifests
and duplicate-name conflicts are shown in the candidate area and block
submission. Removing the offending root or rescanning after correction clears
the error.

All deployment validation occurs before the first filesystem mutation. An
online installation failure is reported as an initialization failure and does
not cause the deployer to copy or link the partially installed user-level
Skill. A supplemental-task scope mismatch is not an initialization failure; it
is a confirmation gate after initialization.

## Testing strategy

Focused tests cover:

- deterministic recursive discovery across multiple roots;
- deduplication of overlapping roots;
- rejection of invalid manifests and same-name/different-source conflicts;
- preserving selections across rescans;
- collecting multiple selected local Skills into version 2 JSON;
- rejecting local mode with no selected Skills;
- mode switching without a Tk `pack(before=...)` failure;
- deployer installation of only selected Skills;
- prevalidation of roots, selected sources, manifest names, and collisions;
- proof that local targets resolve through symbolic links or junctions and are
  not copied directories;
- separation and validation of online requests and supplemental tasks;
- contract tests proving the initialization Skill documents `find-skills`
  bootstrap, online user-level installation, scope gating, and execution order;
- the existing focused Agent-environment regression suite and Git hygiene
  checks.

## Acceptance criteria

The change is accepted when a user can add multiple local roots, see all valid
Skills, select any subset, and deploy only that subset as links; when online
requests are handled exclusively by the Agent through `find-skills`; when the
optional supplemental task follows the post-initialization scope gate; and
when all focused tests and repository hygiene checks pass.
