# RTD CfgFile CLI

> A deterministic, agent-friendly command-line tool that edits NXP **S32 ConfigTools `.mex`** automotive configuration files for **S32K3 RTD 7.0.1**, then verifies the result through real S32DS headless validation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Dependencies](https://img.shields.io/badge/deps-stdlib--only-success.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)
![Backend](https://img.shields.io/badge/backend-S32%20ConfigTools%20.mex-blue.svg)
![NXP RTD](https://img.shields.io/badge/NXP%20RTD-7.0.1-blue.svg)
![Minimal system](https://img.shields.io/badge/minimal%20system-complete-brightgreen.svg)
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

## What it is

RTD CfgFile CLI lets engineers and **AI agents** configure low-level RTD driver
software through a stable CLI / JSON contract instead of driving the S32 ConfigTools
GUI by hand. It accepts a structured request, makes **narrow, byte-faithful** edits
to the project `.mex`, runs fast static checks, then validates the project with the
real **S32DS ConfigTools headless** flow. The whole project ships **as one
installable Agent Skill** (`autombd-rtd/`): a `SKILL.md` that teaches an
agent the workflow, bundling the CLI and its committed data so it runs
self-contained on another machine or in another agent environment.

- **Deterministic:** same project + assets + version + request → same result.
- **Vendor-validated:** acceptance requires ConfigTools exit `0` **and** no SEVERE
  `[TOOL]` problem — exit code alone is not enough.
- **Bounded edits:** providers write only the region they own; cross-module needs are
  explicit dependencies; a no-edit write reproduces the file byte-for-byte.
- **Stdlib-only** Python runtime; JSON runtime assets.

## Status

**Minimal system — complete.** All seven modules — `Mcu,
BaseNXP, Platform, Port, Dio, Mcl, Uart` (equal priority) — are delivered and
vendor-validated end to end: every E2E acceptance case passes the S32DS gate
(exit `0`, code generated, no SEVERE `[TOOL]`) with its generated code verified.
See
[`docs/tests/rtd-config-acceptance-report.md`](docs/tests/rtd-config-acceptance-report.md).

> RTD models the Uart asynchronous method as **interrupt or DMA only** (no
> polling). Both modes are delivered: `uart set --mode interrupt|dma` (DMA wires
> the Mcl DMA channels and the Platform DMATCD completion ISRs).

## Quick start

```bash
# The whole project is an installable Agent Skill; the CLI is bundled inside it
# (Python 3.11+, standard library only — no install, no PYTHONPATH). A zero-config
# launcher at the skill root runs it from any directory:
python autombd-rtd --version

# Inspect a project (read-only)
python autombd-rtd inspect --project <path-to-S32DS-project> --json

# List valid TX/RX pins for a peripheral before assigning them
python autombd-rtd pin-options --device s32k344 --package default --peripheral LPUART_0 --json

# Configure an LPUART Uart channel (interrupt mode) and run static verification
python autombd-rtd uart set --project <path> --hw LPUART_0 --mode interrupt \
    --baud 115200 --tx PTA15 --rx PTA16 --configure --json

# Static checks only / full S32DS headless validation
python autombd-rtd check --project <path> --json
# validate auto-discovers a standard S32DS install (override: --s32ds-root / RTD_CONFIG_S32DS_ROOT)
python autombd-rtd validate --project <path> --json
```

(Equivalent without the launcher: put `autombd-rtd/rtd-config-cli-py` on
`PYTHONPATH`, then use `python -m rtd_config <command>`.)

Every shortcut command normalizes to the same JSON intent and the same
plan → apply → check → validate pipeline.

## Deploy the Skill

Use the deployment helper to publish only the released skill payload into an
agent project skills index:

```bash
python tools/deploy_rtd_skill.py <target-project-dir>
python tools/deploy_rtd_skill.py <target-project-dir> --agent codex
python tools/deploy_rtd_skill.py <target-project-dir> --agent claude
```

By default the helper supports both agent indexes with one physical payload:
`<target>/.agents/skills/autombd-rtd/` is the canonical Codex copy, and
`<target>/.claude/skills/autombd-rtd/` is a filesystem link to that same copy
for Claude Code. Use `--agent codex`, `--agent claude`, or `--agent both` to
select the destination set explicitly. Deploying only Claude Code still ensures
the canonical Codex copy exists first, then links Claude Code to it. On Windows,
the helper creates a directory symlink when permitted and falls back to an NTFS
junction when symlink privileges are unavailable.

The helper checks the source version across `autombd-rtd/SKILL.md`, the
launcher header, and the Python package version before updating the canonical
copy. It deploys only when the canonical skill, bundled tool payload, or version
metadata is missing, or when the installed version is older than the project
version. Current or newer complete installations are left untouched.

The copied payload is intentionally limited to `SKILL.md`, `__main__.py`,
`rtd-config-cli-py/`, and `assets/`; development materials such as `docs/`,
`tests/`, and `tools/` are not included.

## Repository layout

```text
autombd-rtd/                 # ← the deliverable: an installable Agent Skill bundling the CLI + data
  SKILL.md                   #   skill manifest: name, description, agent operating instructions
  __main__.py                #   zero-config launcher — run: python autombd-rtd <command>
  assets/nxp/<family>/<module>/    #   committed assets (e.g. port/pins.json, per-module caches)
  rtd-config-cli-py/rtd_config/    #   bundled stdlib-only Python CLI
tests/                       # deterministic suite — the convergence gate
  fixtures/nxp/<ds|eb>/<family>/<project>/   #   real vendor project fixtures (ds = S32DS, eb = EB tresos)
docs/                        # specs, tests, roadmaps, references — development documentation only
agent-discipline/            # agent charter, lessons learned, review records, governance
.claude/agents/              # Worker / Reviewer / Explorer / Tester subagent roles
.claude/skills/              # common authoring skills (uniform file header, …)
pyproject.toml               # pytest configuration + project metadata
```

## Development workflow

The product is built by an autonomous agent loop; roles and the iteration
protocol live in [`AGENTS.md`](AGENTS.md). The
[lessons-learned log](agent-discipline/agent-lessons-learned.md) records what
each iteration taught.

```bash
python tools/agent_env_check.py --json
python -m pytest -q          # deterministic gate
```

## Documentation

**Development documentation** (`docs/` — engineering content; agent-agnostic):

| Doc | Purpose |
| --- | --- |
| [Core design](docs/specs/rtd-config-core-design.md) | Architecture + CLI/JSON contract + engineering constraints |
| [Domain truth & validation](docs/specs/rtd-config-domain-truth.md) | RTD enum sourcing rule + verified S32DS flow |
| [Test strategy](docs/tests/rtd-config-test-strategy.md) | The convergence contract: layers, vendor gate, acceptance rule |
| [E2E test cases](docs/tests/rtd-config-test-cases.md) | The E2E acceptance case catalog (`RTD-MEX-*`) |
| [Acceptance report](docs/tests/rtd-config-acceptance-report.md) | Current pass/fail evidence for E2E cases |
| [Roadmap](docs/roadmaps/rtd-config-roadmap.md) | The staged delivery route (stages live only here) |
| [Source materials](docs/references/rtd-config-source-materials.md) | Development-time inputs for asset building |

**Agent discipline** (process and governance):

| Doc | Purpose |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent charter: orchestrator duties, roles, iteration loop |
| [`.claude/agents/`](.claude/agents/) | Explorer / Worker / Tester / Reviewer role definitions |
| [Owner review comments](agent-discipline/owner-review-comments.md) | Review-comment resolutions across rounds |
| [Agent lessons learned](agent-discipline/agent-lessons-learned.md) | Reviewer's running lessons log |
| [Documentation governance](agent-discipline/documentation-governance.md) | Governance rules + authoritative documentation map |

## License

Released under the [MIT License](LICENSE).

## About

Built by **autoMBD** — sharing and advancing Model-Based Design (MBD) for automotive
electronics and embedded software. Find more at the autoMBD WeChat Official Account
and [GitHub](https://github.com/autoMBD).
