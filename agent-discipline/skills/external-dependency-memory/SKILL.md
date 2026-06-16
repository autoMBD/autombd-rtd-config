---
name: external-dependency-memory
description: Manage project-local memory for reusable external tools, environments, reference materials, and outside-repository facts. Use when an agent starts work in this project, before rechecking any external dependency, before RTD CfgFile CLI module development that needs S32DS/reference materials, when using any module descriptor xdm file content, or when finishing/reviewing work that relied on external inputs.
---

# External Dependency Memory

## Overview

Use this skill to avoid rediscovering reusable external project facts across
different conversations and agents. It records only local, non-secret evidence
about dependencies and references outside the repository.

## Boundaries

This skill manages reusable outside-repository facts only:

- tools such as GitHub CLI, Codex CLI, S32DS, or vendor validators;
- local installed environments such as RTD/S32DS roots;
- development source materials outside the repository, such as workbooks,
  vendor `.xdm` packages, or prior local skill folders;
- other external information that is likely to be needed again.

Do not use this skill for repository-internal specs, tests, source files,
runtime assets, build artifacts, or task plans.

Never record tokens, passwords, copied credential output, private key material,
or full command output that may contain secrets.

## Files

- Cache file: `.agent-state/external-dependencies.json`
- Source-material authority:
  `docs/references/rtd-config-source-materials.md`

The cache file is local and ignored by Git. Treat it as shared memory for agents
working in this checkout, not as project documentation.

## Workflow

1. At project start, read `.agent-state/external-dependencies.json` if it
   exists. Use cached available/blocked facts before probing external tools or
   paths.
2. Before using an external dependency, check whether the cache already has a
   current entry for it. Recheck only when the entry is missing, stale,
   contradicted by the task, or explicitly refreshed by the user.
3. For RTD CfgFile CLI module development, require valid S32DS and required
   reference-material paths. If either is unavailable, refuse the module
   development request and ask the user for the missing usable path.
4. For source materials, first consult
   `docs/references/rtd-config-source-materials.md`. Do not duplicate its
   dependency list in the cache; cache only local availability evidence.
5. If any `<Module>.xdm` content is used, cache the exact descriptor file path
   with module/package evidence so later agents can find that file directly.
6. When a task actually uses or discovers an external dependency, cache it only
   if it is likely to be reused. If none were used or the item is one-off
   scratch context, do nothing.

## Cache Shape

Keep entries small and append-friendly:

```json
{
  "version": 1,
  "updated_at": "2026-06-16T14:30:00Z",
  "items": {
    "connector.github_app": {
      "kind": "connector",
      "status": "available",
      "location": "GitHub App connector",
      "evidence": "Codex used the connector for issue/PR operations.",
      "verified_at": "2026-06-16T14:30:00Z",
      "verified_by": "codex"
    }
  }
}
```

Use stable item keys:

- `tool.<name>` for command-line tools.
- `env.<name>` for installed environments or roots.
- `source.<name>` for development source materials.
- `source.s32k3_rtd_xdm.<module>` for an exact RTD module descriptor file.
- `connector.<name>` for app/connectors that are not command-line tools.

Allowed statuses are `available`, `blocked`, `unknown`, and `stale`.

## Recording Rules

Each entry should explain enough for another agent to avoid repeating the same
check:

- what was checked or used;
- where it lives, if it is a path or named connector;
- whether it was available or blocked;
- when and by which agent it was verified;
- the shortest safe evidence summary;
- a preparation hint for blocked items.

Prefer conservative evidence such as `path exists`, `version command passed`,
`connector was used successfully`, or `user confirmed auth status passed`.
Do not cache every observed external fact. Cache only entries with a reasonable
chance of reuse in future project work.
