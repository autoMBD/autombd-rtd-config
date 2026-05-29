---
name: agent-config-sync
description: Audit and synchronize configuration across AI agents (Claude Code and Codex) in this project. Use when switching agents, after updating agent config, or when checking for configuration drift.
---

# Agent Configuration Sync

Keep Claude Code and Codex configurations aligned within this repository. The two agents use different config formats and file locations, but several files form sync pairs that must stay consistent.

## Sync Architecture

```
                    ┌─────────────────┐
                    │   .skills/       │  canonical skills (categorized)
                    │   (N skills)     │  ← agents discover via symlinks
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │   sync_agent_skills.py      │
              │   creates relative symlinks │
              └──────────────┬─────────────┘
                             │
   ┌─────────────────────────┼─────────────────────────┐
   │                         │                         │
┌──┴──────────────┐  ┌──────┴──────────┐  ┌───────────┴───────────┐
│ .claude/skills/  │  │ .agents/skills/ │  │ .codex/skills/        │
│ symlinked        │  │ symlinked       │  │ symlinked             │
└─────────────────┘  └────────────────┘  └───────────────────────┘

   ┌─────────────────┐       ┌─────────────────┐
   │ CLAUDE.md        │       │ AGENTS.md        │
   │ (Claude-specific)│◄──────┼─ (generic, all agents)│
   └─────────────────┘       └─────────────────┘
          NO CONTRADICTIONS — shared facts must agree

   ┌─────────────────┐       ┌─────────────────┐
   │ .claude/.mcp.json│       │ .codex/config.toml│
   │ (gitignored)     │◄──────┼─ (gitignored)    │
   └─────────────────┘       └─────────────────┘
          SEMANTIC EQUIVALENCE — same MCP servers, different formats
```

Skills are stored under `.skills/` in categorized paths (`common-skills/`, `matlab-skills/`, `rtd-config-skills/`). The `tools/sync_agent_skills.py` script discovers all `.skills/**/SKILL.md` files and creates relative symlinks into each detected agent's skill root (`.claude/skills/`, `.agents/skills/`, `.codex/skills/`, etc.). Each symlink name is derived from the category path and skill frontmatter name.

Run `python tools/sync_agent_skills.py --dry-run` to preview, or `python tools/sync_agent_skills.py --remove-stale` to apply and clean up stale links.

## Sync Pairs

### Pair 1 — Agent Docs (semantic consistency)

| Agent | File | Format | Git |
|-------|------|--------|-----|
| Claude | `CLAUDE.md` | Markdown | Tracked |
| All    | `AGENTS.md` | Markdown | Tracked |

`CLAUDE.md` contains Claude-specific detail (build command examples, architecture walkthrough). `AGENTS.md` is a generic reference for any agent. They are NOT identical and should NOT be — but they must not contradict.

Shared facts that must agree across both:
- Build commands and target names
- Default paths (S32DS, SEGGER)
- HAL backend descriptions
- File header convention
- Commit style guidance
- `.skills/` is the canonical skill directory

### Pair 2 — MCP Configs (semantic equivalence, gitignored)

| Agent | File | Format | Git |
|-------|------|--------|-----|
| Claude | `.claude/.mcp.json` | JSON | Ignored |
| Codex  | `.codex/config.toml` | TOML | Ignored |

Both define the `matlab` MCP server. They must point to the same executable and use the same server parameters. Agent-specific extra fields are allowed (e.g., `tool_timeout_sec` in Codex).

## Workflow

### Audit Mode (default)

1. **Check skills symlinks**: `python tools/sync_agent_skills.py --dry-run`
   - If differences: report planned changes, flag as P1
2. **Check Pair 1**: Read both CLAUDE.md and AGENTS.md, compare:
   - Build commands and target names
   - Path defaults
   - Architecture claims (HAL backends, CLI layers)
   - Flag any contradiction as P2
3. **Check Pair 2**: Read both MCP config files (if they exist), verify:
   - Same MCP server name (`matlab`)
   - Same executable path
   - Flag mismatches as P2

### Sync Mode (after making a change)

**After adding or modifying a skill:**
```bash
# Re-run the sync script to update symlinks
python tools/sync_agent_skills.py --remove-stale
```

**After adding a fact to CLAUDE.md:**
Check if `AGENTS.md` needs the same fact. Key things that belong in both:
- New build commands or targets
- Changed path defaults
- New architectural components
- Changed commit conventions

**After changing MCP server setup:**
Update both `.claude/.mcp.json` and `.codex/config.toml` in their respective formats.

### When Adding a New Skill

Skills go under categorized paths such as `.skills/common-skills/<skill-name>/SKILL.md` or `.skills/matlab-skills/<skill-name>/SKILL.md`. After creating the skill, run `python tools/sync_agent_skills.py --remove-stale` to create symlinks into detected agent skill roots. Adding a new skill does NOT require any config file changes — only re-running the sync script.

### When Adding a New Agent

1. Add the new agent to `AGENT_TARGETS` in `tools/sync_agent_skills.py` with its markers and skill roots
2. Create the new agent's config directory and MCP server config in its format
3. Update `.gitignore` to ignore the new agent's runtime files
4. Add relevant sections to `AGENTS.md`

## What NOT to Sync

- `.claude/settings.local.json` — machine-specific permissions, never shared
- `.codex/config.toml` agent-specific fields — e.g., `tool_timeout_sec` is Codex-only
- `.claude/.mcp.json` vs `.codex/config.toml` — different formats by necessity; sync only semantic content (server name, executable path, args)
- `CLAUDE.md` detail sections that are genuinely agent-specific — the two HAL backends table is useful for Claude but not required in AGENTS.md
- Symlinks under agent skill roots — each developer runs `sync_agent_skills.py` locally

## Output

After an audit, report:

```
Agent Config Sync Audit — YYYY-MM-DD

Skills Symlinks:  N OK / N stale / N new
Pair 1 (Docs):    N contradictions found / CONTRADICTION: <details>
Pair 2 (MCP):     EQUIVALENT / MISMATCH: <details>
```

If differences found, offer to sync. Follow `auto-commit` for any tracked file changes.
