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
# Date:        2026-06-17
# Version:     0.4.0
# Description: True black-box isolated E2E harness that drives a third-party
#              agent CLI (Codex, OpenCode; others via adapter registry) to
#              exercise the released autombd-rtd skill. A Tester uses this to
#              run an E2E case as a genuine black box: fresh temp dir, deployed
#              skill, copied fixture, and the agent sees only skill + fixture +
#              the case's Subagent Prompt — never this repo or any prior context.
#              The summary carries the CANONICAL per-case KPI (`kpi_seconds`,
#              the [context-injected -> static-check-passed] window) plus
#              diagnostic-only evidence (edit-attempt count and
#              validation-excluded time), all derived from the agent's session
#              output. OpenCode is the DEFAULT agent; an explicit --agent flag
#              persists the choice to .agent-state/e2e-preferences.json for
#              subsequent runs.
# =================================================================================

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
When you have finished all configuration steps, run `check` before `validate`
on the project, then print as your FINAL line exactly:

1. Run the skill's standalone `check --project <project-dir> --json`
   immediately after the configuration edit. This standalone check is required
   for KPI audit even if `--configure` already ran static checks.
2. Do not run `validate` before `check`.
3. If `check` passes, run the skill's `validate --project <project-dir> --json`
   exactly once. If `check` fails, skip `validate` and report
   `"validate_status": "skipped"`.

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
    model: str | None = None,  # accepted for uniform runner signature; ignored by codex
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
# OpenCode runner
# ---------------------------------------------------------------------------

def _find_opencode() -> str:
    """Return the path to the opencode executable, or raise RuntimeError."""
    path = shutil.which("opencode")
    if path is None:
        path = shutil.which("opencode.cmd")
    if path is None:
        raise RuntimeError(
            "opencode executable not found on PATH.  "
            "Install it with: npm install -g opencode-ai"
        )
    return path


def run_opencode(
    prompt: str,
    workdir: Path,
    timeout_s: int,
    sandbox: str,  # accepted for uniform runner signature; ignored by opencode
    model: str | None = None,
) -> RunResult:
    """Run the OpenCode agent CLI with *prompt* on stdin in *workdir*.

    Invocation shape:
      <prompt> | opencode run --format json --dangerously-skip-permissions
                    [--model <model>] --dir <workdir>

    STDOUT is an NDJSON event stream; STDERR is empty.  The session id is
    extracted from the ``sessionID`` field of the first ``step_start`` event.
    The ``sandbox`` argument is a no-op for OpenCode (it has no sandbox tiers).
    """
    oc_path = _find_opencode()
    argv = [
        oc_path,
        "run",
        "--format", "json",
        "--dangerously-skip-permissions",
    ]
    if model is not None:
        argv += ["--model", model]
    argv += ["--dir", str(workdir)]

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
        stdout_text = completed.stdout or ""
        session_id = _extract_opencode_session_id(stdout_text)
        return RunResult(
            exit_code=completed.returncode,
            timed_out=False,
            stdout=stdout_text,
            stderr=completed.stderr or "",
            elapsed_s=elapsed,
            session_id=session_id,
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
            session_id=_extract_opencode_session_id(stdout_text),
        )


def _extract_opencode_session_id(stdout: str) -> str | None:
    """Extract the sessionID from the first ``step_start`` event in the NDJSON stream.

    OpenCode emits a ``step_start`` event as the first event of a session; the
    ``sessionID`` field (format ``ses_<26 alnum>``) is present on every event but
    we anchor to ``step_start`` to be deterministic.
    """
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "step_start":
            sid = obj.get("sessionID")
            return str(sid) if sid is not None else None
    return None


# ---------------------------------------------------------------------------
# OpenCode KPI extraction
# ---------------------------------------------------------------------------

def _ms_epoch_to_iso_utc(ms: int | float) -> str:
    """Convert a millisecond-epoch integer to an ISO-8601 UTC string."""
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    return dt.isoformat()


def compute_opencode_kpi(stdout: str) -> dict[str, Any]:
    """Derive per-case KPI evidence from the OpenCode NDJSON STDOUT stream.

    The CANONICAL ``kpi_seconds`` window is identical in meaning to the codex
    extractor's: ``[context_injected -> check_passed]``, where:

    - ``context_injected_ms`` = top-level ``timestamp`` of the FIRST
      ``step_start`` event (milliseconds since epoch);
    - ``check_passed_ms`` = ``part.state.time.end`` of the FIRST ``tool_use``
      event whose ``part.state.input.command`` matches ``_CHECK_RE`` AND does
      NOT contain ``--configure`` AND does NOT match ``_VALIDATE_RE``.

    Returns a dict with the same diagnostic keys as ``compute_session_kpi``
    (``kpi_seconds``, ``context_injected_ts``, ``check_passed_ts``,
    ``edit_attempts``, ``validate_runs_s``, ``total_span_s``,
    ``validation_excluded_s``, ``commands``), adapted for the OpenCode event
    schema.  Malformed lines and unknown event types are silently skipped.
    """
    context_injected_ms: int | float | None = None
    check_passed_ms: int | float | None = None
    check_passed_ts: str | None = None
    edit_attempts = 0
    validate_runs: list[float] = []
    all_timestamps: list[int | float] = []
    commands: list[dict[str, Any]] = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue

        event_type = obj.get("type")
        top_ts = obj.get("timestamp")

        if event_type == "step_start":
            if context_injected_ms is None and top_ts is not None:
                context_injected_ms = top_ts
            if top_ts is not None:
                all_timestamps.append(top_ts)

        elif event_type == "step_finish":
            if top_ts is not None:
                all_timestamps.append(top_ts)

        elif event_type == "text":
            if top_ts is not None:
                all_timestamps.append(top_ts)

        elif event_type == "tool_use":
            if top_ts is not None:
                all_timestamps.append(top_ts)

            # Extract the bash command and timing from the tool state
            part = obj.get("part", {})
            state = part.get("state", {})
            inp = state.get("input", {})
            command = inp.get("command", "") if isinstance(inp, dict) else ""
            timing = state.get("time", {})
            t_start_ms = timing.get("start")
            t_end_ms = timing.get("end")

            duration_s: float | None = None
            if t_start_ms is not None and t_end_ms is not None:
                duration_s = round((t_end_ms - t_start_ms) / 1000.0, 2)

            is_edit = "--configure" in command
            is_validate = bool(_VALIDATE_RE.search(command))
            is_standalone_check = (
                bool(_CHECK_RE.search(command))
                and not is_edit
                and not is_validate
            )

            if is_edit:
                edit_attempts += 1
            if is_validate and duration_s is not None:
                validate_runs.append(duration_s)
            if is_standalone_check and t_end_ms is not None and check_passed_ms is None:
                # Anchor to the FIRST qualifying check's completion time
                check_passed_ms = t_end_ms
                check_passed_ts = _ms_epoch_to_iso_utc(t_end_ms)

            commands.append({
                "command": command[:200],
                "duration_s": duration_s,
                "is_edit": is_edit,
                "is_validate": is_validate,
            })

    # Compute canonical KPI window
    context_injected_ts: str | None = None
    kpi_seconds: float | None = None
    if context_injected_ms is not None:
        context_injected_ts = _ms_epoch_to_iso_utc(context_injected_ms)
    if context_injected_ms is not None and check_passed_ms is not None:
        kpi_seconds = round((check_passed_ms - context_injected_ms) / 1000.0, 2)

    # Total span: first step_start timestamp to last known timestamp
    total_span_s: float | None = None
    if all_timestamps and context_injected_ms is not None:
        total_span_s = round((max(all_timestamps) - context_injected_ms) / 1000.0, 2)

    validation_excluded_s: float | None = None
    if total_span_s is not None:
        validation_excluded_s = round(total_span_s - sum(validate_runs), 2)

    return {
        "kpi_seconds": kpi_seconds,
        "context_injected_ts": context_injected_ts,
        "check_passed_ts": check_passed_ts,
        "edit_attempts": edit_attempts,
        "validate_runs_s": validate_runs,
        "total_span_s": total_span_s,
        "validation_excluded_s": validation_excluded_s,
        "commands": commands,
    }


# ---------------------------------------------------------------------------
# Agent adapter registry
# ---------------------------------------------------------------------------

DEFAULT_AGENT = "opencode"


@dataclass(frozen=True)
class AgentAdapter:
    """Encapsulates per-agent divergences so the pipeline stays uniform.

    Fields:
      - ``name``: the agent's registry key;
      - ``deploy_agent``: which agent name to pass to ``deploy_fn`` (so the
        skill lands in the right platform directory);
      - ``prepare_workdir``: called after deploy+fixture, before run —
        opencode needs ``git init`` for isolation; codex is a no-op;
      - ``run``: the agent runner callable (uniform signature);
      - ``extract_result``: extract the BLACKBOX_RESULT dict from a RunResult;
      - ``compute_kpi``: derive the KPI dict from a RunResult.
    """

    name: str
    deploy_agent: str
    prepare_workdir: Callable[[Path], None]
    run: Callable[..., RunResult]
    extract_result: Callable[[RunResult], "dict[str, Any] | None"]
    compute_kpi: Callable[[RunResult], "dict[str, Any] | None"]


def _codex_prepare_workdir(workdir: Path) -> None:
    """Codex prepare_workdir: no-op (codex handles isolation via --skip-git-repo-check)."""
    pass  # deliberate no-op


def _opencode_prepare_workdir(workdir: Path) -> None:
    """OpenCode prepare_workdir: run ``git init`` so opencode roots at workdir.

    Without this, OpenCode walks up from ``--dir`` to the git worktree root and
    loads that root's AGENTS.md/skills, breaking the black-box isolation.  A
    ``git init`` in the workdir makes it the new root.
    """
    subprocess.run(["git", "init", str(workdir)], check=True, capture_output=True)


def _codex_extract_result(rr: RunResult) -> "dict[str, Any] | None":
    """Extract BLACKBOX_RESULT from codex plain-text stdout."""
    return _extract_blackbox_result(rr.stdout)


def _opencode_extract_result(rr: RunResult) -> "dict[str, Any] | None":
    """Extract BLACKBOX_RESULT from opencode NDJSON stdout.

    OpenCode emits both complete progress messages and streamed fragments as
    ``text`` events.  Parse the terminal text event on its own first so a
    progress message without a trailing newline cannot be glued to the final
    marker.  If the marker itself was streamed across events, expand only the
    terminal suffix, preserving verbatim concatenation between fragments.

    A result is accepted only when exactly one marker is the final non-empty
    line of that suffix.  This prevents an earlier (stale) result, a malformed
    terminal result, or multiple ambiguous results from being promoted.
    """
    parts: list[str] = []
    for line in rr.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "text":
            part = obj.get("part", {})
            text = part.get("text", "")
            if text:
                parts.append(text)
    if not parts:
        return None

    suffix = parts[-1]
    if "BLACKBOX_RESULT " in suffix:
        return _extract_terminal_blackbox_result(suffix)

    for text in reversed(parts[:-1]):
        suffix = text + suffix
        if "BLACKBOX_RESULT " in suffix:
            return _extract_terminal_blackbox_result(suffix)
    return None


def _extract_terminal_blackbox_result(text: str) -> "dict[str, Any] | None":
    """Parse one unambiguous BLACKBOX_RESULT from the final non-empty line."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    marker = "BLACKBOX_RESULT "
    result_lines = [line for line in lines if line.startswith(marker)]
    if len(result_lines) != 1 or result_lines[0] != lines[-1]:
        return None
    try:
        result = json.loads(result_lines[0][len(marker):])
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def _codex_compute_kpi(rr: RunResult) -> "dict[str, Any] | None":
    """Compute KPI for codex: locate the session log, then compute_session_kpi.

    When a session is located, the returned dict also carries
    ``session_path`` (the rollout JSONL path) alongside the usual
    ``compute_session_kpi`` fields. ``run_pipeline`` lifts that key back out
    to the summary's top-level ``session_path`` field so the public summary
    shape is unchanged; ``summary["kpi"]`` itself never carries
    ``session_path``. The "no session log" and OSError cases keep their
    existing error-dict shape (no ``session_path`` key) since there is no
    located file to report.
    """
    session_id = rr.session_id
    if not session_id:
        return None
    try:
        located = find_codex_session_file(session_id)
        if located is not None:
            kpi = dict(compute_session_kpi(located))
            kpi["session_path"] = str(located)
            return kpi
        return {"error": f"no session log found for session id {session_id}"}
    except OSError as exc:
        return {"error": f"session KPI extraction failed: {exc}"}


def _opencode_compute_kpi(rr: RunResult) -> "dict[str, Any] | None":
    """Compute KPI for opencode: derive from the NDJSON STDOUT stream.

    Unlike codex, KPI evidence is derived in-memory from STDOUT, so there is
    no on-disk session log to report. The dict carries no ``session_path``
    key (equivalent to ``session_path=None``); ``run_pipeline`` pops it with
    a default of ``None`` when lifting it to the summary's top level.
    """
    return compute_opencode_kpi(rr.stdout)


#: Registry mapping agent name -> AgentAdapter.
AGENT_ADAPTERS: dict[str, AgentAdapter] = {
    "codex": AgentAdapter(
        name="codex",
        deploy_agent="codex",
        prepare_workdir=_codex_prepare_workdir,
        run=run_codex,
        extract_result=_codex_extract_result,
        compute_kpi=_codex_compute_kpi,
    ),
    "opencode": AgentAdapter(
        name="opencode",
        deploy_agent="codex",  # OpenCode reuses .agents/skills/ — codex layout
        prepare_workdir=_opencode_prepare_workdir,
        run=run_opencode,
        extract_result=_opencode_extract_result,
        compute_kpi=_opencode_compute_kpi,
    ),
}


def get_adapter(agent: str) -> AgentAdapter:
    """Return the AgentAdapter for *agent*, or raise ``ValueError``."""
    adapter = AGENT_ADAPTERS.get(agent)
    if adapter is None:
        supported = ", ".join(sorted(AGENT_ADAPTERS))
        raise ValueError(
            f"unsupported agent {agent!r}; supported agents are: {supported}"
        )
    return adapter


# ---------------------------------------------------------------------------
# Runner registry (back-compat shim — existing tests import get_runner)
# ---------------------------------------------------------------------------

#: Registry mapping agent name -> runner callable.
#: Adding a new backend: add an AgentAdapter in AGENT_ADAPTERS above.
AGENT_RUNNERS: dict[str, Callable[..., RunResult]] = {
    name: adapter.run for name, adapter in AGENT_ADAPTERS.items()
}


def get_runner(agent: str) -> Callable[..., RunResult]:
    """Return the runner callable for *agent*, or raise ``ValueError``.

    This is a thin back-compat shim over ``get_adapter``; prefer
    ``get_adapter`` for new code.
    """
    runner = AGENT_RUNNERS.get(agent)
    if runner is None:
        supported = ", ".join(sorted(AGENT_RUNNERS))
        raise ValueError(
            f"unsupported agent {agent!r}; supported agents are: {supported}"
        )
    return runner


# ---------------------------------------------------------------------------
# Agent-selection cache
# ---------------------------------------------------------------------------

_CACHE_VERSION = 1

# Windows transiently locks a freshly-written temp file — antivirus, Defender,
# and the Search indexer open handles for a few hundred milliseconds — and the
# atomic Path.replace() then fails with WinError 5 (access denied) or 32
# (sharing violation); 145 (dir not empty) is included for parity with the
# rmtree/rename race this same idiom guards in tools/deploy_rtd_skill.py. This
# is a small LOCAL helper (not a cross-module import) so blackbox_e2e.py keeps
# no dependency on deploy_rtd_skill.py; the retry/backoff shape mirrors that
# module's proven ``_retry_fs``/``_is_transient_windows_lock`` idiom exactly.
_FS_RETRY_ATTEMPTS = 10
_FS_RETRY_DELAY_S = 0.1


def _is_transient_windows_lock(exc: OSError) -> bool:
    """True for the transient Windows FS-lock errors worth retrying.

    Scoped to Windows winerror codes so non-Windows behavior is unchanged and
    a real, persistent error on any platform still surfaces promptly.
    WinError 5 = ERROR_ACCESS_DENIED, 32 = ERROR_SHARING_VIOLATION,
    145 = ERROR_DIR_NOT_EMPTY.
    """
    return sys.platform == "win32" and getattr(exc, "winerror", None) in (5, 32, 145)


def _retry_fs(operation: Callable[[], Any]) -> None:
    """Run a filesystem mutation, retrying transient Windows lock errors.

    Re-raises immediately for any non-transient error and re-raises the last
    error once the attempt budget is exhausted, so a genuine failure is never
    swallowed.
    """
    for attempt in range(_FS_RETRY_ATTEMPTS):
        try:
            operation()
            return
        except OSError as exc:
            if not _is_transient_windows_lock(exc) or attempt == _FS_RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_FS_RETRY_DELAY_S * (attempt + 1))


def read_agent_cache(path: Path) -> str | None:
    """Read the cached default agent from *path*.

    Returns the ``default_agent`` string, or ``None`` on missing file,
    unparseable JSON, or missing key.  Never raises.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        agent = data.get("default_agent")
        return str(agent) if agent is not None else None
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError, TypeError):
        return None


def write_agent_cache(path: Path, agent: str) -> None:
    """Atomically write the agent cache at *path*, creating parent dirs as needed.

    The final publish (``tmp_path.replace(path)``) is retried on a transient
    Windows FS lock (see ``_retry_fs``); a persistent failure still raises —
    callers that want best-effort persistence (e.g. ``resolve_agent``) catch
    ``OSError`` themselves rather than this function silently swallowing it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    updated_at = datetime.now(tz=timezone.utc).isoformat()
    data = {
        "version": _CACHE_VERSION,
        "default_agent": agent,
        "updated_at": updated_at,
    }
    # Write atomically via a sibling temp file
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _retry_fs(lambda: tmp_path.replace(path))


def resolve_agent(
    cli_agent: str | None,
    cache_path: Path,
) -> tuple[str, str]:
    """Resolve the active agent from the CLI flag and/or the cache.

    Returns ``(agent, source)`` where source is one of ``"flag"``,
    ``"cache"``, or ``"default"``.

    - ``cli_agent`` not None: validate against ``AGENT_ADAPTERS`` (raise
      ``ValueError`` for unknown agents); best-effort persist to cache
      (a write failure that survives ``write_agent_cache``'s own transient-
      lock retry is logged to stderr and swallowed — losing a preference
      write must never abort the run); return ``(cli_agent, "flag")``.
    - else: read cache; if a valid cached agent is found, return
      ``(cached, "cache")``.
    - else: return ``(DEFAULT_AGENT, "default")`` — do NOT rewrite the cache
      on fallback.
    """
    if cli_agent is not None:
        if cli_agent not in AGENT_ADAPTERS:
            supported = ", ".join(sorted(AGENT_ADAPTERS))
            raise ValueError(
                f"unsupported agent {cli_agent!r}; supported agents are: {supported}"
            )
        try:
            write_agent_cache(cache_path, cli_agent)
        except OSError as exc:
            print(
                f"warning: could not persist agent preference to {cache_path}: {exc}",
                file=sys.stderr,
            )
        return (cli_agent, "flag")

    cached = read_agent_cache(cache_path)
    if cached is not None and cached in AGENT_ADAPTERS:
        return (cached, "cache")

    return (DEFAULT_AGENT, "default")


# ---------------------------------------------------------------------------
# Session KPI extraction
# ---------------------------------------------------------------------------
#
# The CANONICAL per-case KPI is ``kpi_seconds``: the owner-locked window from
# the moment the prompt/context is injected (the user's perceived start) to the
# moment the standalone static ``check`` passes — i.e.
# ``[context_injected -> check_passed]``.  This deliberately EXCLUDES (a) the
# ``task_started``->context startup gap before the prompt lands, and (b)
# everything AFTER ``check``: the vendor ``validate`` (S32DS) runtime and the
# trailing agent report.  ``edit_attempts``, ``validate_runs_s``,
# ``total_span_s`` and ``validation_excluded_s`` remain as DIAGNOSTICS only —
# ``validation_excluded_s`` (``total_span_s`` minus the validate calls) still
# over-counts because it keeps the post-edit deliberation, the standalone
# ``check`` itself, and the trailing report, so it must never be read as the
# KPI; ``kpi_seconds`` is the one number that gates the per-case budget.
#
# These helpers reconstruct every metric from the codex session rollout JSONL
# (per-event ms timestamps + the exact commands the agent ran).  Detection is
# module-agnostic and ``--json``-independent:
#   - an *edit attempt* is any skill command carrying the universal
#     ``--configure`` apply flag (the dry-run ``plan`` variant lacks it);
#   - a *validation run* is any ``validate`` subcommand invocation;
#   - the *context-injection event* is the first ``message``/``user_message``
#     payload at/after ``task_started`` (codex's permissions/AGENTS.md/prompt
#     events injected into the first turn);
#   - the *standalone check* is a ``function_call`` whose command contains the
#     ``check`` verb but is neither the mutating ``--configure`` edit nor the
#     vendor ``validate`` gate, paired to its ``function_call_output`` strictly
#     by ``call_id`` (never by event order), so a ``check``/``validate`` pair
#     dispatched back-to-back is still resolved correctly even if the other
#     call's output arrives first.

#: Word-boundary match for the ``validate`` subcommand verb.
_VALIDATE_RE = re.compile(r"\bvalidate\b")

#: Match the standalone ``check`` SUBCOMMAND: the ``check`` verb (``(?<!-)``
#: rejects a hyphenated flag like ``--skip-git-repo-check``) immediately
#: followed by a CLI flag (``(?=\s+--)``), which every real ``check --project
#: …`` invocation carries.  This rejects the bare word "check" inside a quoted
#: path/arg, and (together with ``_is_plan_tool``) the word inside a plan-tool
#: payload.  A command counts as the standalone check only when it also is NOT
#: the mutating ``--configure`` edit and NOT the ``validate`` vendor gate.
_CHECK_RE = re.compile(r"(?<!-)\bcheck\b(?=\s+--)")

#: Payload types codex emits for the prompt/context content injected into the
#: first turn (permissions/AGENTS.md/the task prompt itself).
_CONTEXT_PAYLOAD_TYPES = ("message", "user_message")


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


def _is_plan_tool(command: str) -> bool:
    """True if *command* is a codex ``update_plan`` payload, not a shell command.

    Codex's plan tool is a ``function_call`` whose ``arguments`` are
    ``{"plan": [{"step": ..., "status": ...}, ...]}`` (no ``command`` key), so
    ``_command_of`` returns that raw JSON.  Its plan-step prose routinely
    contains words like "check", "validate", or "configure", which would
    otherwise be misclassified as skill commands — a real defect: an early plan
    update worded "...check..." was matched as the standalone ``check`` and
    ended the KPI window ~48 s too early.  Plan-tool calls do no project work,
    so they are excluded from every command classification.
    """
    s = command.lstrip()
    if not s.startswith("{"):
        return False
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return False
    return isinstance(obj, dict) and "plan" in obj


def compute_session_kpi(session_path: Path) -> dict[str, Any]:
    """Derive per-case KPI evidence from a codex rollout JSONL.

    Returns a dict with:
      - ``kpi_seconds`` — THE CANONICAL per-case KPI: the
        ``[context_injected -> check_passed]`` window in seconds (float,
        rounded to 2 dp), or ``None`` when either boundary cannot be located
        (no context event, or no standalone ``check``).  This is the number
        the per-case budget gates — never ``validation_excluded_s`` (see
        below);
      - ``context_injected_ts`` / ``check_passed_ts`` — the two boundary
        ISO-8601 timestamps backing ``kpi_seconds`` (or ``None``), kept for
        auditability;
      - ``edit_attempts`` — number of mutating skill invocations (commands
        carrying ``--configure``; the dry-run ``plan`` is correctly excluded);
      - ``validate_runs_s`` — per-call durations of ``validate`` (S32DS) commands;
      - ``total_span_s`` — ``task_started``→``task_complete`` span, falling back
        to first ``function_call`` → last ``function_call_output`` when the task
        markers are absent (e.g. a truncated/timed-out session);
      - ``validation_excluded_s`` — DIAGNOSTIC ONLY (no longer the KPI):
        ``total_span_s`` minus the sum of ``validate_runs_s``.  It still
        over-counts relative to ``kpi_seconds`` because it keeps the
        post-edit deliberation, the standalone ``check`` call itself, and the
        trailing agent report that follow the canonical window's end;
      - ``commands`` — a compact per-call timeline for auditability.
    """
    calls: dict[Any, dict[str, Any]] = {}
    ts_start: str | None = None
    ts_end: str | None = None
    # Candidate context (message/user_message) events, in file order.  The
    # winning anchor cannot be picked until ts_start is FINAL (task_started
    # may itself appear after a stray pre-task event in the raw log), so every
    # candidate is buffered here and resolved once the single pass completes.
    context_candidates: list[tuple[str | None, str]] = []

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
            elif ptype in _CONTEXT_PAYLOAD_TYPES and ts is not None:
                context_candidates.append((ts, ptype))

    # Resolve the context-injection anchor now that ts_start is final: the
    # FIRST message/user_message event at/after task_started.  A candidate
    # strictly earlier than task_started (e.g. stray pre-task priming that
    # happens to appear before the task_started line) is not the user's
    # perceived start and must be ignored.
    start_dt = _parse_iso(ts_start or "")
    context_injected_ts: str | None = None
    for cand_ts, _cand_type in context_candidates:
        cand_dt = _parse_iso(cand_ts or "")
        if cand_dt is None:
            continue
        if start_dt is None or cand_dt >= start_dt:
            context_injected_ts = cand_ts
            break

    commands: list[dict[str, Any]] = []
    edit_attempts = 0
    validate_runs: list[float] = []
    call_times: list[datetime] = []
    out_times: list[datetime] = []
    check_passed_dt: datetime | None = None
    check_passed_ts: str | None = None

    for entry in calls.values():
        command = entry.get("command", "")
        call_dt = _parse_iso(entry.get("call_ts") or "")
        out_dt = _parse_iso(entry.get("out_ts") or "")
        duration = (out_dt - call_dt).total_seconds() if (call_dt and out_dt) else None
        # Codex plan-tool (`update_plan`) calls are NOT shell commands; their
        # plan-step prose can contain "check"/"validate"/"configure" and must
        # never be classified as a skill command (else an early plan update
        # worded "...check..." ends the KPI window prematurely).
        is_plan = _is_plan_tool(command)
        is_edit = (not is_plan) and "--configure" in command
        is_validate = (not is_plan) and bool(_VALIDATE_RE.search(command))
        # The standalone `check` is the `check` verb minus the mutating edit
        # and minus the vendor `validate` gate — those are distinct
        # subcommands even though `validate` does not itself contain "check".
        is_standalone_check = (
            (not is_plan)
            and bool(_CHECK_RE.search(command))
            and not is_edit
            and not is_validate
        )
        if is_edit:
            edit_attempts += 1
        if is_validate and duration is not None:
            validate_runs.append(round(duration, 2))
        if is_standalone_check and out_dt is not None:
            # Resolve ties by EARLIEST output timestamp — pairing is always by
            # call_id (each `entry` already belongs to exactly one call_id), so
            # this only matters when multiple standalone `check` calls exist;
            # the FIRST one to pass anchors the canonical window's end.
            if check_passed_dt is None or out_dt < check_passed_dt:
                check_passed_dt = out_dt
                check_passed_ts = entry.get("out_ts")
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

    # Diagnostic total span: task_started->task_complete, falling back to the
    # first call -> last output when the task markers are absent.  Distinct
    # from `start_dt`/context_dt above — this backs total_span_s/
    # validation_excluded_s (diagnostics), not kpi_seconds (the canonical KPI).
    span_start_dt = start_dt or (min(call_times) if call_times else None)
    span_end_dt = _parse_iso(ts_end or "") or (max(out_times) if out_times else None)
    total_span_s = (
        round((span_end_dt - span_start_dt).total_seconds(), 2)
        if (span_start_dt and span_end_dt) else None
    )
    validation_excluded_s = (
        round(total_span_s - sum(validate_runs), 2) if total_span_s is not None else None
    )

    context_dt = _parse_iso(context_injected_ts or "")
    kpi_seconds = (
        round((check_passed_dt - context_dt).total_seconds(), 2)
        if (context_dt is not None and check_passed_dt is not None)
        else None
    )

    return {
        "kpi_seconds": kpi_seconds,
        "context_injected_ts": context_injected_ts,
        "check_passed_ts": check_passed_ts,
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
    agent_source: str = "default",
    model: str | None = None,
    prepare_workdir_fn: "Callable[[Path], None] | None" = None,
) -> dict[str, Any]:
    """Full black-box pipeline for one E2E case.

    Steps:
      1. Create an isolated temp workdir.
      2. Deploy the released skill using the adapter's deploy_agent target.
      3. Copy the case fixture into the workdir.
      4. Build the agent prompt.
      4b. Call prepare_workdir_fn (defaults to adapter.prepare_workdir; e.g. git
          init for opencode isolation, no-op for codex).
      5. Run the selected agent runner.
      6. Write the log, extract the BLACKBOX_RESULT, locate the .mex.
      6b. Compute KPI evidence via the adapter's compute_kpi.
      7. Return a JSON-serialisable summary dict.

    *deploy_fn*, *runner_fn*, and *prepare_workdir_fn* are injectable for testing.
    """
    if deploy_fn is None:
        deploy_fn = _default_deploy

    # Resolve the adapter for this agent
    adapter = get_adapter(agent)

    # Determine the effective runner: injected > adapter
    effective_runner: Callable[..., RunResult] = runner_fn if runner_fn is not None else adapter.run

    # Determine the effective prepare_workdir callable: injected > adapter
    effective_prepare: Callable[[Path], None] = (
        prepare_workdir_fn if prepare_workdir_fn is not None else adapter.prepare_workdir
    )

    # 1. Temp workdir
    prefix = f"rtd-bb-{case.id}-"
    workdir = Path(tempfile.mkdtemp(prefix=prefix, dir=temp_base))

    # 2. Deploy skill using the adapter's deploy_agent target.
    # For opencode, deploy_agent="codex" so the skill lands in .agents/skills/,
    # which is exactly what opencode discovers once the workdir is git-init'd.
    deploy_agent = adapter.deploy_agent
    results = deploy_fn(repo_root, workdir, (deploy_agent,))
    skill_dir = Path(next(r.destination for r in results if r.agent == deploy_agent))
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

    # 4b. Per-adapter workdir preparation (e.g. git init for opencode isolation).
    effective_prepare(workdir)

    # 5. Run — pass model only when the runner accepts it (preserves back-compat
    # with test stubs that were written with the 4-arg signature before model was
    # added; real runners run_codex and run_opencode both accept model=None).
    try:
        sig = inspect.signature(effective_runner)
        accepts_model = "model" in sig.parameters
    except (ValueError, TypeError):
        accepts_model = True  # unknown signature: assume the full signature

    if accepts_model:
        run_result = effective_runner(
            prompt=prompt,
            workdir=workdir,
            timeout_s=timeout_s,
            sandbox=sandbox,
            model=model,
        )
    else:
        run_result = effective_runner(
            prompt=prompt,
            workdir=workdir,
            timeout_s=timeout_s,
            sandbox=sandbox,
        )

    # 6. Log + parse
    combined = run_result.stdout + ("\n--- STDERR ---\n" + run_result.stderr if run_result.stderr else "")
    log_path = workdir / "_blackbox_run.log"
    log_path.write_text(combined, encoding="utf-8")

    blackbox_result = adapter.extract_result(run_result)
    mex_path = _find_mex(project_dir)

    # 6b. KPI evidence — derived uniformly via the adapter's compute_kpi for
    # BOTH agents (no per-agent special case here). Best-effort: a missing or
    # garbled KPI must not fail the run.
    #
    # For codex, the adapter embeds session_path (the rollout JSONL path)
    # inside the returned kpi dict because it is the only agent with an
    # on-disk session log; we lift it back out to the summary's top-level
    # session_path field so summary["kpi"] never carries session_path and the
    # public summary shape stays unchanged. For opencode there is no on-disk
    # session log, so session_path stays None.
    session_id = run_result.session_id
    session_path: str | None = None
    kpi: dict[str, Any] | None = adapter.compute_kpi(run_result)
    if isinstance(kpi, dict) and "session_path" in kpi:
        session_path = kpi.pop("session_path")

    # 7. Summary
    summary: dict[str, Any] = {
        "case": case.id,
        "scenario": case.scenario,
        "agent": agent,
        "agent_source": agent_source,
        "model": model,
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
    supported_agents = ", ".join(sorted(AGENT_ADAPTERS))
    parser = argparse.ArgumentParser(
        description=(
            "Black-box isolated E2E harness for the RTD CfgFile CLI autombd-rtd skill.\n"
            "Deploys the released skill into a fresh temp dir, copies the case fixture,\n"
            "and drives a third-party agent CLI with the case's Subagent Prompt.\n"
            f"Default agent: {DEFAULT_AGENT}  |  Supported agents: {supported_agents}"
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
        default=None,
        metavar="NAME",
        help=(
            "agent backend to use; if omitted, uses the cached choice or the built-in "
            f"default ({DEFAULT_AGENT}); an explicit value is cached for next time. "
            f"Supported: {supported_agents}"
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        metavar="PROVIDER/MODEL",
        help=(
            "model to use as provider/model (e.g. deepseek/deepseek-chat); "
            "omit to use the configured default; ignored by codex"
        ),
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        metavar="SANDBOX",
        help="codex sandbox policy (default: workspace-write); ignored by opencode",
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

    repo_root: Path = args.repo_root.resolve()

    # Resolve agent from CLI flag + cache (PERSIST-ON-USE semantics)
    cache_path = repo_root / ".agent-state" / "e2e-preferences.json"
    try:
        agent, agent_source = resolve_agent(args.agent, cache_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Validate agent in registry (resolve_agent already does this for explicit flags;
    # this is a safety net for the default/cache path if the registry evolves)
    try:
        get_adapter(agent)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

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

    # Get the runner via get_runner() so test mocks that patch get_runner still
    # intercept correctly.  When runner_fn is supplied, run_pipeline skips the
    # adapter's prepare_workdir; the real opencode isolation (git init) is then
    # performed by the adapter's prepare_workdir call below, before run_pipeline
    # invokes the runner.  For mocked tests the prepare_workdir is a no-op because
    # codex adapter's prepare_workdir is a no-op, and the workdir doesn't exist
    # until run_pipeline creates it — so we let the pipeline handle it internally
    # when runner_fn is None.  Passing runner_fn here triggers the "skip
    # prepare_workdir" guard in run_pipeline, which is correct for tests that
    # want to fully mock the run.
    runner_fn = get_runner(agent)

    summary = run_pipeline(
        case=case,
        agent=agent,
        sandbox=args.sandbox,
        timeout_s=timeout_s,
        repo_root=repo_root,
        temp_base=args.temp_base,
        keep=args.keep,
        agent_source=agent_source,
        model=args.model,
        runner_fn=runner_fn,
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
