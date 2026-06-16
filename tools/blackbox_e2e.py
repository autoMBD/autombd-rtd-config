# =================================================================================
# The MIT License
# MIT许可证
#
# <https://opensource.org/license/mit>
#
# SPDX short identifier / SPDX 短标识符：MIT
#
# Copyright (c) 2026 autoMBD
# 版权所有 (c) 2026 autoMBD
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 特此向获得本软件及相关文档（合称"本软件"）副本的任何人免费授予不受限制地利用本软
# 件的许可，包括而不限于：使用、复制、修改、合并、发布、分发、分许可和/或销售本软
# 件副本，并允许本软件的接收者也获得前述许可，但须遵守以下条件：
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 以上版权声明及本许可声明应包含在本软件的所有副本或主要部分中。
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALLTHE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# 本软件系"按原样"提供，不包含任何形式的明示或默示保证，包括但不限于适销性、特定
# 目的适用性及不侵权的保证。在任何情况下，无论是在合同、侵权或其他案件中，作者或版
# 权持有人均不对因本软件、或因本软件的使用或其他利用而引起的、引发的或与之相关的任
# 何权利主张、损害赔偿或其他责任承担责任。
# =================================================================================
# Project:     RTD CfgFile CLI <https://github.com/autoMBD/autombd-rtd-config>
# File:        blackbox_e2e.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-15
# Version:     0.2.0
# Description: True black-box isolated E2E harness that drives a third-party
#              agent CLI (Codex; others via registry) to exercise the released
#              autombd-rtd skill. A Tester uses this to run an E2E case as a
#              genuine black box: fresh temp dir, deployed skill, copied fixture,
#              and the agent sees only skill + fixture + the case's Subagent
#              Prompt — never this repo or any prior context. The summary also
#              carries first-class KPI evidence (edit-attempt count and
#              validation-excluded time), derived from the codex session log
#              that the run's `session id:` banner pins deterministically.
# =================================================================================

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "autombd-rtd"


@dataclass(frozen=True)
class Case:
    """A parsed E2E test case from the test-cases markdown table."""

    id: str
    scenario: str
    prompt: str
    fixture: str
    kpi_minutes: int


@dataclass
class RunResult:
    """Outcome of one agent-runner invocation."""

    exit_code: int
    timed_out: bool
    stdout: str
    stderr: str
    elapsed_s: float
    # The agent session id (e.g. codex's `session id:` banner), used to locate
    # the session log for KPI extraction. None when the runner exposes none.
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Case parsing
# ---------------------------------------------------------------------------

# Column indices in the markdown table (0-based, ignoring leading empty cell
# produced by splitting "| A | B |" on "|").
_COL_ID = 0
_COL_MODULE = 1
_COL_SCENARIO = 2
_COL_PROMPT = 3
_COL_FIXTURE = 4
_COL_KPI = 5
_COL_PASS_CRITERIA = 6


def _strip_cell(cell: str) -> str:
    """Strip whitespace and surrounding backticks from a markdown table cell."""
    cell = cell.strip()
    if cell.startswith("`") and cell.endswith("`"):
        cell = cell[1:-1]
    return cell


def parse_case(test_cases_md_path: Path, case_id: str) -> Case:
    """Parse the E2E test-cases markdown table and return the requested case.

    The table is the first GFM pipe table whose header row contains an "ID"
    column.  The ``Subagent Prompt`` cell is kept verbatim (may be Chinese).
    ``kpi_minutes`` is extracted from the KPI cell via ``within N min``.

    Raises ``ValueError`` if *case_id* is not found in the table.
    """
    text = test_cases_md_path.read_text(encoding="utf-8")

    # Locate the table header line: contains "| ID |"
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and re.search(r"\|\s*ID\s*\|", stripped, re.IGNORECASE):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"no markdown table with an 'ID' column found in {test_cases_md_path}")

    # Walk table data rows (skip header and separator)
    for line in lines[header_idx + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break  # end of table
        cells = stripped.split("|")
        # Split "| A | B | C |" -> ["", "A", "B", "C", ""]
        # Data cells start at index 1.
        data = [c for c in cells[1:] if not (len(cells) == 2 and c == "")]
        # Remove the trailing empty element from "... | last |"
        if data and data[-1].strip() == "":
            data = data[:-1]

        if len(data) < _COL_KPI + 1:
            continue

        row_id = _strip_cell(data[_COL_ID])
        if row_id != case_id:
            continue

        scenario = _strip_cell(data[_COL_SCENARIO])
        prompt = data[_COL_PROMPT].strip()  # verbatim — no backtick stripping
        fixture = _strip_cell(data[_COL_FIXTURE])  # strip backticks from path
        kpi_cell = data[_COL_KPI].strip()

        kpi_match = re.search(r"within\s+(\d+)\s*min", kpi_cell, re.IGNORECASE)
        if not kpi_match:
            raise ValueError(
                f"cannot extract 'within N min' from KPI cell for case {case_id!r}: {kpi_cell!r}"
            )
        kpi_minutes = int(kpi_match.group(1))

        return Case(
            id=case_id,
            scenario=scenario,
            prompt=prompt,
            fixture=fixture,
            kpi_minutes=kpi_minutes,
        )

    raise ValueError(
        f"case id {case_id!r} not found in {test_cases_md_path}; "
        "check that the ID matches exactly (case-sensitive)."
    )


def max_kpi_minutes(test_cases_md_path: Path) -> int:
    """Scan the E2E test-cases catalog and return the maximum KPI in minutes.

    Searches all occurrences of ``within N min`` (same pattern as
    ``parse_case``) across the entire file and returns the largest N.

    Raises ``ValueError`` if no such pattern is found (e.g. empty or
    malformed catalog).
    """
    text = test_cases_md_path.read_text(encoding="utf-8")
    matches = re.findall(r"within\s+(\d+)\s*min", text, re.IGNORECASE)
    if not matches:
        raise ValueError(
            f"no 'within N min' KPI pattern found in {test_cases_md_path}; "
            "cannot determine the maximum catalog KPI."
        )
    return max(int(m) for m in matches)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

_RETURN_SUFFIX = """\

---
When you have finished all configuration steps, run the skill's `check` and
`validate` commands on the project, then print as your FINAL line exactly:

BLACKBOX_RESULT {"configured": <true|false>, "validate_status": "<string>", "notes": "<string>"}

where:
- `configured` is true if configuration edits were applied without errors
- `validate_status` is the one-word outcome of `validate` (e.g. "passed", "failed", "skipped")
- `notes` is a brief one-line comment or empty string
"""


def build_prompt(case: Case, skill_md_path: Path, project_dir: Path) -> str:
    """Build the full agent prompt for *case*.

    Structure:
      1. Preamble: tells the agent where the skill lives and how to invoke the CLI.
      2. The case's Subagent Prompt verbatim.
      3. Return-suffix: instructs the agent to emit a ``BLACKBOX_RESULT`` JSON line.
    """
    skill_dir = skill_md_path.parent
    preamble = (
        f"You are running as an isolated agent.  Your job is to configure the "
        f"NXP S32K3 RTD project at:\n\n"
        f"  {project_dir}\n\n"
        f"You have access to the autombd-rtd skill.  Read the skill description "
        f"at:\n\n"
        f"  {skill_md_path}\n\n"
        f"The skill's CLI launcher is at:\n\n"
        f"  {skill_dir / '__main__.py'}\n\n"
        f"Invoke the CLI with:\n\n"
        f"  python {skill_dir} <command> [args...]\n\n"
        f"You must NOT access any other repository or context.  Use only the "
        f"skill and the project directory above.\n\n"
        f"--- Task ---\n\n"
    )
    return preamble + case.prompt + _RETURN_SUFFIX


# ---------------------------------------------------------------------------
# Agent runners
# ---------------------------------------------------------------------------

def _find_codex() -> str:
    """Return the path to the codex executable, or raise RuntimeError."""
    path = shutil.which("codex")
    if path is None:
        path = shutil.which("codex.cmd")
    if path is None:
        raise RuntimeError(
            "codex executable not found on PATH.  "
            "Install it with: npm install -g @openai/codex"
        )
    return path


# `codex exec` prints a startup banner line `session id: <uuid>` to stderr.
# Capturing it lets the KPI extractor pin the exact rollout log deterministically
# instead of guessing "the newest session", which is fragile when several runs
# land in the same day/minute.
_SESSION_ID_RE = re.compile(
    r"session id:\s*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def _extract_session_id(stderr: str) -> str | None:
    """Return the codex session UUID from the stderr banner, or None if absent."""
    if not stderr:
        return None
    match = _SESSION_ID_RE.search(stderr)
    return match.group(1) if match else None


def run_codex(
    prompt: str,
    workdir: Path,
    timeout_s: int,
    sandbox: str,
) -> RunResult:
    """Run the codex agent CLI with *prompt* on stdin in *workdir*.

    Proven invocation shape (do not alter):
      <prompt> | codex exec -s <sandbox> -c approval_policy=never \\
                    --skip-git-repo-check --cd <workdir>

    Returns a ``RunResult``; never raises for agent-level failures.
    """
    codex_path = _find_codex()
    # Proven primary invocation: prompt on STDIN | codex exec -s <sandbox>
    # -c approval_policy=never --skip-git-repo-check --cd <workdir>
    # Do NOT alter this argv shape — a live run depends on it.
    argv = [
        codex_path,
        "exec",
        "-s", sandbox,
        "-c", "approval_policy=never",
        "--skip-git-repo-check",
        "--cd", str(workdir),
    ]
    t_start = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
        elapsed = time.monotonic() - t_start
        return RunResult(
            exit_code=completed.returncode,
            timed_out=False,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            elapsed_s=elapsed,
            session_id=_extract_session_id(completed.stderr or ""),
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - t_start
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")
        return RunResult(
            exit_code=-1,
            timed_out=True,
            stdout=stdout_text,
            stderr=stderr_text,
            elapsed_s=elapsed,
            session_id=_extract_session_id(stderr_text),
        )
    except (FileNotFoundError, OSError):
        # The primary path above is proven on the target machine.  On some
        # Windows environments a .cmd/.bat script cannot be launched directly
        # by subprocess without shell=True; retry once via 'cmd /c' as a
        # portability fallback — but only for those extensions on Windows.
        if sys.platform == "win32" and Path(codex_path).suffix.lower() in (".cmd", ".bat"):
            fallback_argv = ["cmd", "/c", codex_path] + argv[1:]
            completed = subprocess.run(
                fallback_argv,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout_s,
            )
            elapsed = time.monotonic() - t_start
            return RunResult(
                exit_code=completed.returncode,
                timed_out=False,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                elapsed_s=elapsed,
                session_id=_extract_session_id(completed.stderr or ""),
            )
        raise


# ---------------------------------------------------------------------------
# Runner registry
# ---------------------------------------------------------------------------

#: Registry mapping agent name -> runner callable.
#: Adding a new backend: add one ``run_<x>`` function and one registry entry.
AGENT_RUNNERS: dict[str, Callable[..., RunResult]] = {
    "codex": run_codex,
}


def get_runner(agent: str) -> Callable[..., RunResult]:
    """Return the runner callable for *agent*, or raise ``ValueError``."""
    runner = AGENT_RUNNERS.get(agent)
    if runner is None:
        supported = ", ".join(sorted(AGENT_RUNNERS))
        raise ValueError(
            f"unsupported agent {agent!r}; supported agents are: {supported}"
        )
    return runner


# ---------------------------------------------------------------------------
# Session KPI extraction
# ---------------------------------------------------------------------------
#
# The per-case KPI has two measurable parts: (a) the edit-attempt count and
# (b) the time EXCLUDING validation runtime.  The harness's own ``elapsed_s`` is
# wall-clock that INCLUDES the agent's own ``validate`` (S32DS) calls, so it
# cannot serve as the KPI.  These helpers reconstruct both metrics from the
# codex session rollout JSONL (per-event ms timestamps + the exact commands the
# agent ran).  Detection is module-agnostic and ``--json``-independent:
#   - an *edit attempt* is any skill command carrying the universal
#     ``--configure`` apply flag (the dry-run ``plan`` variant lacks it);
#   - a *validation run* is any ``validate`` subcommand invocation.

#: Word-boundary match for the ``validate`` subcommand verb.
_VALIDATE_RE = re.compile(r"\bvalidate\b")


def _default_codex_home() -> Path:
    """Return the codex home dir (``$CODEX_HOME`` or ``~/.codex``)."""
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else Path.home() / ".codex"


def find_codex_session_file(session_id: str, codex_home: Path | None = None) -> Path | None:
    """Locate the rollout JSONL for *session_id* under the codex sessions tree.

    Codex writes ``<codex_home>/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl``;
    the UUID is embedded in the filename, so we glob by it for a deterministic
    lookup.  If several match (should not happen — UUIDs are unique) the newest
    by mtime wins.  Returns None when nothing matches or *session_id* is falsy.
    """
    if not session_id:
        return None
    home = codex_home if codex_home is not None else _default_codex_home()
    matches = sorted(
        home.glob(f"sessions/**/rollout-*{session_id}*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def _parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (``...Z`` or offset) into a datetime, or None."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _command_of(payload: dict[str, Any]) -> str:
    """Best-effort shell-command string from a ``function_call`` payload.

    Codex stores the command in ``arguments`` as a JSON string ``{"command":
    "..."}``; fall back to the raw ``arguments`` / ``command`` field if it is not
    JSON (so detection never depends on a particular serialisation).
    """
    args = payload.get("arguments")
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            return args
        if isinstance(parsed, dict) and "command" in parsed:
            return str(parsed["command"])
        return args
    cmd = payload.get("command")
    return str(cmd) if cmd is not None else ""


def compute_session_kpi(session_path: Path) -> dict[str, Any]:
    """Derive per-case KPI evidence from a codex rollout JSONL.

    Returns a dict with:
      - ``edit_attempts`` — number of mutating skill invocations (commands
        carrying ``--configure``; the dry-run ``plan`` is correctly excluded);
      - ``validate_runs_s`` — per-call durations of ``validate`` (S32DS) commands;
      - ``total_span_s`` — ``task_started``→``task_complete`` span, falling back
        to first ``function_call`` → last ``function_call_output`` when the task
        markers are absent (e.g. a truncated/timed-out session);
      - ``validation_excluded_s`` — ``total_span_s`` minus the sum of
        ``validate_runs_s`` (the KPI metric: intent/planning/impl/edit time with
        validation runtime removed);
      - ``commands`` — a compact per-call timeline for auditability.
    """
    calls: dict[Any, dict[str, Any]] = {}
    ts_start: str | None = None
    ts_end: str | None = None

    with session_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue
            ptype = payload.get("type", "")
            ts = obj.get("timestamp")
            if ptype == "task_started":
                ts_start = ts
            elif ptype == "task_complete":
                ts_end = ts
            elif ptype == "function_call":
                entry = calls.setdefault(payload.get("call_id"), {})
                entry["call_ts"] = ts
                entry["command"] = _command_of(payload)
            elif ptype == "function_call_output":
                calls.setdefault(payload.get("call_id"), {})["out_ts"] = ts

    commands: list[dict[str, Any]] = []
    edit_attempts = 0
    validate_runs: list[float] = []
    call_times: list[datetime] = []
    out_times: list[datetime] = []

    for entry in calls.values():
        command = entry.get("command", "")
        call_dt = _parse_iso(entry.get("call_ts") or "")
        out_dt = _parse_iso(entry.get("out_ts") or "")
        duration = (out_dt - call_dt).total_seconds() if (call_dt and out_dt) else None
        is_edit = "--configure" in command
        is_validate = bool(_VALIDATE_RE.search(command))
        if is_edit:
            edit_attempts += 1
        if is_validate and duration is not None:
            validate_runs.append(round(duration, 2))
        if call_dt:
            call_times.append(call_dt)
        if out_dt:
            out_times.append(out_dt)
        commands.append({
            "command": command[:200],
            "duration_s": round(duration, 2) if duration is not None else None,
            "is_edit": is_edit,
            "is_validate": is_validate,
        })

    start_dt = _parse_iso(ts_start or "") or (min(call_times) if call_times else None)
    end_dt = _parse_iso(ts_end or "") or (max(out_times) if out_times else None)
    total_span_s = (
        round((end_dt - start_dt).total_seconds(), 2) if (start_dt and end_dt) else None
    )
    validation_excluded_s = (
        round(total_span_s - sum(validate_runs), 2) if total_span_s is not None else None
    )

    return {
        "edit_attempts": edit_attempts,
        "validate_runs_s": validate_runs,
        "total_span_s": total_span_s,
        "validation_excluded_s": validation_excluded_s,
        "commands": commands,
    }


# ---------------------------------------------------------------------------
# Deploy helper (loaded from sibling tools/deploy_rtd_skill.py at runtime)
# ---------------------------------------------------------------------------

def _load_deploy_module():
    """Load ``deploy_rtd_skill`` from tools/ via importlib (no package install needed)."""
    module_path = Path(__file__).resolve().parent / "deploy_rtd_skill.py"
    spec = importlib.util.spec_from_file_location("deploy_rtd_skill", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load deploy_rtd_skill from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("deploy_rtd_skill", mod)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _default_deploy(repo_root: Path, workdir: Path, agents: tuple[str, ...]) -> Any:
    deploy_mod = _load_deploy_module()
    return deploy_mod.deploy(repo_root, workdir, agents=agents)  # returns tuple[DeployResult, ...]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _extract_blackbox_result(text: str) -> dict[str, Any] | None:
    """Find and parse the ``BLACKBOX_RESULT {...}`` line from agent output."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("BLACKBOX_RESULT "):
            json_part = line[len("BLACKBOX_RESULT "):]
            try:
                return json.loads(json_part)
            except json.JSONDecodeError:
                return None
    return None


def _find_mex(project_dir: Path) -> str | None:
    """Return the first .mex file found under *project_dir*, or None."""
    for path in project_dir.rglob("*.mex"):
        return str(path)
    return None


def run_pipeline(
    case: Case,
    agent: str,
    sandbox: str,
    timeout_s: int,
    repo_root: Path,
    temp_base: Path | None = None,
    deploy_fn: Callable[..., Any] | None = None,
    runner_fn: Callable[..., RunResult] | None = None,
    keep: bool = False,
) -> dict[str, Any]:
    """Full black-box pipeline for one E2E case.

    Steps:
      1. Create an isolated temp workdir.
      2. Deploy the released skill into it.
      3. Copy the case fixture into the workdir.
      4. Build the agent prompt.
      5. Run the selected agent runner.
      6. Write the log, extract the BLACKBOX_RESULT, locate the .mex.
      7. Return a JSON-serialisable summary dict.

    *deploy_fn* and *runner_fn* are injectable for testing.
    """
    if deploy_fn is None:
        deploy_fn = _default_deploy
    if runner_fn is None:
        runner_fn = get_runner(agent)

    # 1. Temp workdir
    prefix = f"rtd-bb-{case.id}-"
    workdir = Path(tempfile.mkdtemp(prefix=prefix, dir=temp_base))

    # 2. Deploy skill for the selected agent.
    # deploy_fn returns a tuple of DeployResult-like objects, each with .agent
    # and .destination (the deployed skill dir).  We look up the result for the
    # requested agent to get the exact destination — never hardcode the path.
    results = deploy_fn(repo_root, workdir, (agent,))
    skill_dir = Path(next(r.destination for r in results if r.agent == agent))
    skill_md_path = skill_dir / "SKILL.md"

    # 3. Copy fixture
    fixture_src = repo_root / case.fixture
    fixture_dst = workdir / fixture_src.name
    if fixture_src.is_dir():
        shutil.copytree(str(fixture_src), str(fixture_dst))
    else:
        shutil.copy2(str(fixture_src), str(fixture_dst))
    project_dir = fixture_dst

    # 4. Build prompt
    prompt = build_prompt(case, skill_md_path, project_dir)

    # 5. Run
    run_result = runner_fn(
        prompt=prompt,
        workdir=workdir,
        timeout_s=timeout_s,
        sandbox=sandbox,
    )

    # 6. Log + parse
    combined = run_result.stdout + ("\n--- STDERR ---\n" + run_result.stderr if run_result.stderr else "")
    log_path = workdir / "_blackbox_run.log"
    log_path.write_text(combined, encoding="utf-8")

    blackbox_result = _extract_blackbox_result(run_result.stdout)
    mex_path = _find_mex(project_dir)

    # 6b. KPI evidence — locate the codex session log (deterministically, via the
    # session id the runner captured) and derive the per-case KPI.  Best-effort:
    # the run already succeeded, so a missing/garbled session must not fail it —
    # but the reason is recorded (never silently swallowed).
    session_id = run_result.session_id
    session_path: str | None = None
    kpi: dict[str, Any] | None = None
    if session_id:
        try:
            located = find_codex_session_file(session_id)
            if located is not None:
                session_path = str(located)
                kpi = compute_session_kpi(located)
            else:
                kpi = {"error": f"no session log found for session id {session_id}"}
        except OSError as exc:
            kpi = {"error": f"session KPI extraction failed: {exc}"}

    # 7. Summary
    summary: dict[str, Any] = {
        "case": case.id,
        "scenario": case.scenario,
        "agent": agent,
        "sandbox": sandbox,
        "workdir": str(workdir),
        "project_dir": str(project_dir),
        "mex_path": mex_path,
        "elapsed_s": run_result.elapsed_s,
        "timed_out": run_result.timed_out,
        "exit_code": run_result.exit_code,
        "blackbox_result": blackbox_result,
        "session_id": session_id,
        "session_path": session_path,
        "kpi": kpi,
        "log_path": str(log_path),
    }

    # Cleanup: remove on clean success unless --keep
    if not keep and not run_result.timed_out and run_result.exit_code == 0:
        shutil.rmtree(workdir, ignore_errors=True)

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Black-box isolated E2E harness for the RTD CfgFile CLI autombd-rtd skill.\n"
            "Deploys the released skill into a fresh temp dir, copies the case fixture,\n"
            "and drives a third-party agent CLI with the case's Subagent Prompt."
        )
    )
    parser.add_argument(
        "--case",
        required=True,
        metavar="ID",
        help="E2E case ID (e.g. RTD-MEX-MCU-001) from docs/tests/rtd-config-test-cases.md",
    )
    parser.add_argument(
        "--agent",
        default="codex",
        metavar="NAME",
        help="agent backend to use (default: codex; supported: " + ", ".join(sorted(AGENT_RUNNERS)) + ")",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        metavar="SANDBOX",
        help="codex sandbox policy (default: workspace-write)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=None,
        metavar="N",
        help=(
            "runner timeout in seconds "
            "(default: 3 x the MAX catalog KPI minutes x 60, "
            "so S32DS validation — which the per-case KPI excludes — fits)"
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        metavar="PATH",
        help="repository root (default: this script's repo)",
    )
    parser.add_argument(
        "--temp-base",
        type=Path,
        default=None,
        metavar="DIR",
        help="base directory for the temp workdir (default: OS temp)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the workdir even on clean success",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Validate agent early
    try:
        get_runner(args.agent)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    repo_root: Path = args.repo_root.resolve()
    test_cases_md = repo_root / "docs" / "tests" / "rtd-config-test-cases.md"

    try:
        case = parse_case(test_cases_md, args.case)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        max_kpi = max_kpi_minutes(test_cases_md)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    timeout_s: int = (
        args.timeout_seconds
        if args.timeout_seconds is not None
        else 3 * max_kpi * 60
    )

    runner_fn = get_runner(args.agent)

    summary = run_pipeline(
        case=case,
        agent=args.agent,
        sandbox=args.sandbox,
        timeout_s=timeout_s,
        repo_root=repo_root,
        temp_base=args.temp_base,
        runner_fn=runner_fn,
        keep=args.keep,
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
