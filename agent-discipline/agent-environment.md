# Agent Environment Dependencies

| Field | Value |
| --- | --- |
| Version | 0.1.1 |
| Date | 2026-06-16 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Agent-session dependency inventory and verification-cache policy for RTD CfgFile CLI development. |

## Purpose

This document defines the agent-session environment contract. It belongs to
Category B because it governs how agents prepare and reuse development tools; it
is not a runtime requirement for the released `autombd-rtd` skill payload.

## Dependency Inventory

| Dependency | Required for | Verification | Preparation |
| --- | --- | --- | --- |
| Python 3.11+ | Deterministic tests, repository tools, and the bundled CLI implementation | `python --version` equivalent via the active interpreter | Install Python 3.11 or newer and ensure the selected interpreter can run `python -m pytest`. |
| Git | Branching, committing, diff review, and pushing PR branches | `git --version` | Install Git and ensure `git` is on `PATH`. |
| GitHub App connector (Codex) | Issue, PR, and repository operations from Codex | Codex records this connector as the GitHub authority; it does not verify GitHub CLI auth | Use the installed Codex GitHub App connector for GitHub operations. |
| GitHub CLI (`gh`) for non-Codex agents | Push/PR fallback, Actions inspection, and authenticated repository operations when no GitHub App connector is available | `gh --version` and `gh auth status -h github.com` in the target agent environment | Install GitHub CLI and run `gh auth login -h github.com` once when the cache is absent or stale. If the agent cannot obtain the status result, ask the user to complete login/authorization in their terminal and provide an OK confirmation; record that confirmation with `--confirm-github-cli-auth`. |
| Third-party agent CLI: Codex | True black-box E2E through `tools/blackbox_e2e.py` | `codex --version` through `codex`, `codex.cmd`, or `codex.exe` | Install Codex CLI and complete its first-run login/authorization before E2E execution. |
| S32 Design Studio with S32K3 RTD 7.0.1 | Vendor ConfigTools validation gate | `rtd_config.backends.s32_mex.validation.find_s32ds_root()` | Install S32DS with S32K3 RTD 7.0.1, or set `RTD_CONFIG_S32DS_ROOT` to the install root. |
| Project reference materials and tools | Agent discipline, domain grounding, test cases, deployment, and black-box validation | Presence check for `AGENTS.md`, `agent-discipline/`, `docs/specs/rtd-config-domain-truth.md`, `docs/tests/rtd-config-test-cases.md`, `docs/references/rtd-config-source-materials.md`, `tools/blackbox_e2e.py`, `tools/deploy_rtd_skill.py`, `autombd-rtd/SKILL.md`, and `autombd-rtd/assets/` | Restore a complete repository checkout; do not delete development docs, tools, the released skill, or committed assets. |

## Verification Cache

Run the bootstrap check at the start of a new Codex session:

```bash
python tools/agent_env_check.py --json
```

Codex is the default agent profile. It uses the GitHub App connector and does
not verify GitHub CLI authentication. For another agent profile, pass the agent
explicitly:

```bash
python tools/agent_env_check.py --agent claude --json
python tools/agent_env_check.py --agent other --json
```

The tool records verification results in:

```text
.agent-state/environment-verification.json
```

The state file is intentionally ignored by Git. It is a local credential cache:
it may contain paths, versions, pass/block status, timestamps, and preparation
instructions, but it must not contain tokens, passwords, or copied secret
material.

If a dependency has a cached `passed` result, later sessions and tools may reuse
that result directly. Interactive or authorization-sensitive probes such as
`gh auth status -h github.com` should run only for non-Codex agents when the
cache is absent or when an agent uses `--refresh`.

For non-Codex agents, if `gh auth status -h github.com` cannot provide a usable
result from the agent environment, the agent asks the user to complete
`gh auth login -h github.com` in their terminal and return a short OK
confirmation. That confirmation is the local verification credential:

```bash
python tools/agent_env_check.py --agent claude \
  --confirm-github-cli-auth "user confirmed gh auth status passed" --json
```

Use `--refresh` after installing/upgrading tools, changing S32DS/RTD locations,
switching GitHub/Codex accounts, or when a cached tool path no longer exists:

```bash
python tools/agent_env_check.py --refresh --json
```

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-16 | 0.1.1 | Updated GitHub verification policy: Codex uses the GitHub App connector without GitHub CLI validation; non-Codex agents use `gh auth status -h github.com` or a user confirmation credential. |
| 2026-06-15 | 0.1.0 | Created the agent-session dependency inventory and verification-cache policy for issue #11. |
