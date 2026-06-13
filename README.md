# RTD CfgFile CLI

> A deterministic, agent-friendly command-line tool that edits NXP **S32 ConfigTools `.mex`** automotive configuration files for **S32K3 RTD 7.0.1**, then verifies the result through real S32DS headless validation.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Dependencies](https://img.shields.io/badge/deps-stdlib--only-success.svg)
![Tests](https://img.shields.io/badge/tests-44%20passing-brightgreen.svg)
![Backend](https://img.shields.io/badge/backend-S32%20ConfigTools%20.mex-blue.svg)
![NXP RTD](https://img.shields.io/badge/NXP%20RTD-7.0.1-blue.svg)
![Roadmap](https://img.shields.io/badge/roadmap-stage%201%20·%20minimal%20system-orange.svg)
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

**Minimal system (roadmap stage 1) — in progress.** The **Uart reference path**
(LPUART and FlexIO, interrupt mode) is delivered and vendor-validated end to
end. The acceptance bar is **module parity**: `Mcu, BaseNXP, Platform, Port,
Dio, Mcl, Uart` — all equal priority — each passing its E2E acceptance cases
and the S32DS gate. See
[`docs/tests/rtd-config-acceptance-report.md`](docs/tests/rtd-config-acceptance-report.md).

> RTD models the Uart asynchronous method as **interrupt or DMA only** (no polling).
> The delivered Uart path currently supports interrupt; the DMA capability is a
> tracked target (`RTD-MEX-UART-003` in the test cases).

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
python autombd-rtd validate --project <path> --s32ds-root C:\NXP\S32DS.3.6.7 --json
```

(Equivalent without the launcher: put `autombd-rtd/rtd-config-cli-py` on
`PYTHONPATH`, then use `python -m rtd_config <command>`.)

Every shortcut command normalizes to the same JSON intent and the same
plan → apply → check → validate pipeline.

## Deploy the Skill

Use the deployment helper to publish only the released skill payload into an
agent skills index:

```bash
python tools/deploy_rtd_skill.py <agent-home-or-skills-dir>
```

If the argument is an agent home directory, the helper deploys to
`<target>/skills/autombd-rtd/`. If the argument itself is named `skills`, it
deploys directly to `<target>/autombd-rtd/`. The helper checks the source
version across `autombd-rtd/SKILL.md`, the launcher header, and the Python
package version before copying. It deploys only when the target skill, bundled
tool payload, or version metadata is missing, or when the installed version is
older than the project version. Current or newer complete installations are
left untouched.

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
docs/                        # specs, tests, plans, roadmaps, references, common, OBSOLETE archive
.claude/agents/              # Worker / Reviewer / Explorer / Tester subagent roles
.claude/skills/              # common authoring skills (uniform file header, …)
pyproject.toml               # pytest configuration + project metadata
```

## Development workflow

The product is built by an autonomous agent loop —
`main → Explorer → Worker → Tester → main` — where **tests are the sole functional
convergence signal**. The Tester also records per-case KPI evidence; a functional
PASS with a KPI miss returns to the Worker for up to three optimization
iterations, then records the true KPI result. On a green functional gate the
**Reviewer** performs non-test acceptance review and appends a
[lessons-learned](docs/common/rtd-config-lessons-learned.md) entry. Roles live in
[`.claude/agents/`](.claude/agents/); the charter is [`AGENTS.md`](AGENTS.md).

```bash
python -m pytest -q          # deterministic gate
```

## Documentation

| Doc | Purpose |
| --- | --- |
| [Core design](docs/specs/rtd-config-core-design.md) | Architecture + CLI/JSON contract |
| [Domain truth & validation](docs/specs/rtd-config-domain-truth.md) | RTD enum sourcing rule + verified S32DS flow |
| [Test strategy](docs/tests/rtd-config-test-strategy.md) | The convergence contract: layers, vendor gate, acceptance rule, roles, KPI loop |
| [E2E test cases](docs/tests/rtd-config-test-cases.md) | The E2E acceptance case catalog (`RTD-MEX-*`, isolated protocol, KPI) |
| [Implementation plan](docs/plans/rtd-cfgfile-cli-implementation-plan.md) | The module-by-module delivery framework |
| [Roadmap](docs/roadmaps/rtd-config-roadmap.md) | The staged delivery route (stages live only here) |

## License

Released under the [MIT License](LICENSE).

## About

Built by **autoMBD** — sharing and advancing Model-Based Design (MBD) for automotive
electronics and embedded software. Find more at the autoMBD WeChat Official Account
and [GitHub](https://github.com/autoMBD).
