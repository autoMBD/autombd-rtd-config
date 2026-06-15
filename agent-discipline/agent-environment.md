# Agent Environment Dependencies

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-06-15 |
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
| GitHub CLI (`gh`) | Push/PR fallback, Actions inspection, and authenticated repository operations not covered by the GitHub connector | `gh --version` and `gh auth status` | Install GitHub CLI and run `gh auth login -h github.com` once when the cache is absent or stale. |
| Third-party agent CLI: Codex | True black-box E2E through `tools/blackbox_e2e.py` | `codex --version` through `codex`, `codex.cmd`, or `codex.exe` | Install Codex CLI and complete its first-run login/authorization before E2E execution. |
| S32 Design Studio with S32K3 RTD 7.0.1 | Vendor ConfigTools validation gate | `rtd_config.backends.s32_mex.validation.find_s32ds_root()` | Install S32DS with S32K3 RTD 7.0.1, or set `RTD_CONFIG_S32DS_ROOT` to the install root. |
| Project reference materials and tools | Agent discipline, domain grounding, test cases, deployment, and black-box validation | Presence check for `AGENTS.md`, `agent-discipline/`, `docs/specs/rtd-config-domain-truth.md`, `docs/tests/rtd-config-test-cases.md`, `docs/references/rtd-config-source-materials.md`, `tools/blackbox_e2e.py`, `tools/deploy_rtd_skill.py`, `autombd-rtd/SKILL.md`, and `autombd-rtd/assets/` | Restore a complete repository checkout; do not delete development docs, tools, the released skill, or committed assets. |

## Verification Cache

Run the bootstrap check at the start of a new agent session:

```bash
python tools/agent_env_check.py --json
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
`gh auth status` should run only when the cache is absent or when an agent uses
`--refresh`.

Use `--refresh` after installing/upgrading tools, changing S32DS/RTD locations,
switching GitHub/Codex accounts, or when a cached tool path no longer exists:

```bash
python tools/agent_env_check.py --refresh --json
```

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-15 | 0.1.0 | Created the agent-session dependency inventory and verification-cache policy for issue #11. |
