---
name: spec-documentation-quality
description: Use when drafting, reviewing, or revising project specs and companion documentation so the result is maintainable, versioned, reviewable, and actionable. Applies to spec docs, roadmap docs, reference docs, test strategy docs, comments tracking, achieved/reviewed drafts, metadata tables, changelogs, and review-comment resolution.
---

# Spec Documentation Quality

Use this skill when creating or updating project specifications and their
supporting documents. The goal is to make specs durable guides for development,
not one-off notes.

## Core Principles

- Keep the spec focused on the project goal, architecture, contracts, and
  success criteria.
- Move staged delivery limits into roadmap or implementation-plan documents.
- Move test cases, validation flow, KPI, and subagent validation process into
  test strategy documents.
- Move source material locations and runtime/development dependency boundaries
  into reference documents.
- Keep review comments connected to their original context by archiving reviewed
  drafts before resolving comments.
- Track every review comment with a clear resolution and target document.
- Do not let development-only source materials become runtime dependencies.

## Required Document Shape

Every Markdown document produced or maintained under this workflow must have:

1. A title.
2. A metadata table immediately after the title:

```markdown
| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | YYYY-MM-DD |
| Author | autoMBD <tkung.lqk@foxmali.com> (AI-assisted) |
| Description | One sentence describing this document. |
```

3. Main content.
4. A Changelog table at the end:

```markdown
## Changelog

| Date | Version | Description |
| --- | --- | --- |
| YYYY-MM-DD | 0.1.0 | Created initial document. |
```

Use semantic filenames, not date-prefixed filenames. Dates belong in metadata
and changelogs.

## Document Set

Prefer a small, maintainable document set:

- `specs/`: stable project goals, architecture, contracts, and success criteria.
- `roadmaps/`: milestones, staged scope, deferrals, and delivery order.
- `references/`: development source material locations and runtime boundaries.
- `tests/`: test strategy, test-case templates, validation process, and KPI.
- `specs/achieved/`: archived reviewed drafts that preserve inline comments.
- `comments-tracking`: how each review comment was resolved.

Add a separate capability table when a spec contains data that will evolve, such
as module ownership, dependencies, supported actions, runtime data, and tests.

## Review Workflow

When the user reviews a document with inline comments:

1. Archive the reviewed draft with comments preserved in context under
   `specs/achieved/`.
2. Update the active documents to resolve the comments.
3. Keep comments out of active docs after resolution.
4. Update comments tracking with:
   - ID;
   - original area;
   - comment intent;
   - resolution;
   - target document.
5. Update metadata versions and changelog rows for every changed document.
6. Verify no active document contains unresolved `<!-- REVIEW` markers.

Do not keep only a standalone comments list; without surrounding document
context, comments lose important meaning.

## Spec Writing Checklist

Before considering a spec ready for review:

- Purpose describes the complete project target, not just the next milestone.
- Architecture includes all deliverable layers, including Agent Skills if the
  tool targets AI agents.
- Runtime assets are separated from development-time references.
- Cross-module ownership and dependency rules are explicit.
- Acceptance criteria point to test cases and KPI, not vague confidence.
- Companion roadmap, reference, and test documents exist when the spec would be
  overloaded by staged details.

## Verification

Before committing documentation changes:

- Check every Markdown file has metadata and changelog tables.
- Check active docs have no unresolved `<!-- REVIEW` markers.
- Check date-prefixed filenames are not introduced.
- Run `git diff --check -- <docs-path>`.
- Review `git status --short` and stage only the intended docs.
