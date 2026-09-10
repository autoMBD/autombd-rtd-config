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
# File:        workflow_environment.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Portable operation capability preflight and JSON command line.
# =================================================================================

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from workflow_environment_io import (EnvironmentError, PLATFORMS, ROLES, CAPABILITIES, CONTEXTS,
    fields, version, strings, canonical, digest, sha256, check_hash, validate_bindings,
    fail, root_path, inspect_checkout, create_isolated_checkout, read_json)
from workflow_environment_hygiene import snapshot_evidence, verify_evidence, cleanup_paths


def required_capabilities(role: str, *, requires_blackbox: bool = False, requires_s32ds: bool = False) -> tuple[str, ...]:
    if role not in ROLES or type(requires_blackbox) is not bool or type(requires_s32ds) is not bool:
        fail("INVALID_INPUT", "Unsupported role or operation selection.")
    required = ["filesystem-read"]
    if role in ("orchestrator", "worker", "tester"):
        required.extend(("filesystem-write", "git"))
    if requires_blackbox:
        required.extend(("agent-cli", "blackbox"))
    if requires_s32ds:
        required.append("s32ds")
    return tuple(required)


def select_agent(current_platform: str | None, available_agents: Sequence[str], *, explicit_agent: str | None = None) -> str:
    available = strings(available_agents, choices=PLATFORMS)
    selected = explicit_agent if explicit_agent is not None else current_platform
    if not isinstance(selected, str) or selected not in PLATFORMS:
        fail("INVALID_INPUT", "Specify the current contributor platform or an explicit supported agent.")
    if selected not in available:
        fail("CAPABILITY_UNAVAILABLE", "The selected contributor Agent CLI is unavailable; select an available actor explicitly.")
    return selected


def _request(request: dict) -> tuple[str, ...]:
    fields(request, {"version", "role", "platform", "bindings", "required_capabilities", "isolation"})
    version(request["version"])
    baseline = required_capabilities(request["role"])
    if request["platform"] not in PLATFORMS or request["isolation"] not in ("checkout", "input"):
        fail("INVALID_INPUT", "Unsupported platform or isolation requirement.")
    validate_bindings(request["bindings"])
    declared = strings(request["required_capabilities"], choices=CAPABILITIES)
    return tuple(sorted(set(baseline) | set(declared) | ({"input-isolation"} if request["isolation"] == "input" else set())))


def _capability(record: dict) -> None:
    fields(record, {"id", "context", "status", "approved", "mode", "evidence_sha256"})
    if record["id"] not in CAPABILITIES or record["context"] not in CONTEXTS:
        fail("INVALID_INPUT", "Unsupported capability or execution context.")
    if record["status"] not in ("available", "unavailable", "unknown") or type(record["approved"]) is not bool:
        fail("INVALID_INPUT", "Invalid capability availability or authorization.")
    if not isinstance(record["mode"], str) or not record["mode"].strip() or "\x00" in record["mode"]:
        fail("INVALID_INPUT", "Capability mode must identify its evidence origin.")
    check_hash(record["evidence_sha256"])


def _checkout(checkout: dict, bindings: dict) -> None:
    fields(checkout, {"root", "head", "git_dir", "common_dir", "checkout_kind", "shared_objects", "ref_isolated", "os_read_isolated"})
    if checkout["root"] != bindings["checkout_root"] or checkout["head"] != bindings["head"]:
        fail("STALE_IDENTITY", "Checkout observation is bound to a different source.")
    for field in ("git_dir", "common_dir"):
        if not isinstance(checkout[field], str) or not Path(checkout[field]).is_absolute():
            fail("INVALID_INPUT", "Checkout Git paths must be absolute.")
    if checkout["checkout_kind"] not in ("worktree", "clone"):
        fail("INVALID_INPUT", "Unknown checkout topology.")
    if any(type(checkout[field]) is not bool for field in ("shared_objects", "ref_isolated", "os_read_isolated")):
        fail("INVALID_INPUT", "Checkout topology flags must be boolean.")
    if checkout["ref_isolated"] and (checkout["shared_objects"] or checkout["checkout_kind"] == "worktree"):
        fail("INVALID_INPUT", "Shared Git topology cannot prove reference isolation.")


def evaluate_preflight(request: dict, observations: dict) -> dict:
    required = _request(request)
    fields(observations, {"version", "bindings", "capabilities", "checkout"})
    version(observations["version"])
    validate_bindings(observations["bindings"])
    if request["bindings"] != observations["bindings"]:
        fail("STALE_IDENTITY", "Capability observations have stale task/source bindings.")
    _checkout(observations["checkout"], request["bindings"])
    records = observations["capabilities"]
    if not isinstance(records, list):
        fail("INVALID_INPUT", "Capabilities must be an observation list.")
    identities = set()
    for record in records:
        _capability(record)
        identity = (record["id"], record["context"], record["mode"])
        if identity in identities:
            fail("INVALID_INPUT", "Duplicate capability context/mode observations are ambiguous.")
        identities.add(identity)
    selected, diagnostics = [], []
    for capability in required:
        candidates = [r for r in records if r["id"] == capability
                      and r["status"] == "available" and r["approved"]]
        if capability == "github" and request["platform"] == "codex":
            candidates = [r for r in candidates if (r["context"], r["mode"]) in
                          (("connector", "connector"), ("host", "host-cli"))]
            candidates.sort(key=lambda r: (r["context"] != "connector", r["mode"]))
        else:
            candidates.sort(key=lambda r: (CONTEXTS.index(r["context"]), r["mode"]))
        if candidates:
            selected.append(copy.deepcopy(candidates[0]))
        else:
            diagnostics.append({"code": "CAPABILITY_UNAVAILABLE", "capability": capability,
                                "message": "Required current-operation evidence is absent, unavailable, unknown or unapproved."})
    report = {"version": 1, "status": "BLOCKED" if diagnostics else "READY",
              "request_sha256": digest(request), "bindings": copy.deepcopy(request["bindings"]),
              "selected_capabilities": selected, "diagnostics": diagnostics,
              "request": copy.deepcopy(request), "observations_sha256": digest(observations),
              "evidence_origin": "trusted-adapter-observations"}
    report["report_sha256"] = digest(report)
    return report


def require_preflight(report: dict, *, expected_request_sha256: str, current_bindings: dict) -> None:
    check_hash(expected_request_sha256)
    validate_bindings(current_bindings)
    fields(report, {"version", "status", "request_sha256", "bindings", "selected_capabilities",
                    "diagnostics", "request", "observations_sha256", "evidence_origin", "report_sha256"})
    version(report["version"])
    required = _request(report["request"])
    check_hash(report["observations_sha256"])
    if digest({k: v for k, v in report.items() if k != "report_sha256"}) != report["report_sha256"]:
        fail("STALE_IDENTITY", "Capability report bytes no longer match their identity.")
    if (report["request_sha256"] != expected_request_sha256 or digest(report["request"]) != expected_request_sha256
            or report["bindings"] != current_bindings or report["request"]["bindings"] != current_bindings):
        fail("STALE_IDENTITY", "Capability report does not bind the current request and source.")
    if report["status"] != "READY" or report["diagnostics"]:
        fail("CAPABILITY_UNAVAILABLE", "Caller dispatch requires a READY capability report.")
    if not isinstance(report["selected_capabilities"], list):
        fail("INVALID_INPUT", "Malformed capability selection.")
    for record in report["selected_capabilities"]:
        _capability(record)
        if not record["approved"] or record["status"] != "available":
            fail("CAPABILITY_UNAVAILABLE", "A selected capability is not available and authorized.")
    if sorted(r["id"] for r in report["selected_capabilities"]) != list(required):
        fail("CAPABILITY_UNAVAILABLE", "Capability report omits a current-operation requirement.")
    # Re-probe the real Git HEAD immediately before the caller's operation.
    # Adapter observation digests remain trusted inputs, not authenticated OS proof.
    inspect_checkout(Path(current_bindings["checkout_root"]), expected_head=current_bindings["head"])


def probe_command(argv: Sequence[str], cwd: Path, *, approved: bool, context: str, timeout_seconds: int = 60) -> dict:
    if type(approved) is not bool or not approved:
        fail("CAPABILITY_UNAVAILABLE", "A probe requires pre-authorized execution.")
    if (not isinstance(argv, (list, tuple)) or not argv or
            any(not isinstance(x, str) or "\x00" in x for x in argv) or not argv[0]):
        fail("INVALID_INPUT", "Probe argv must be an explicit executable and argument sequence.")
    if context not in CONTEXTS or type(timeout_seconds) is not int or timeout_seconds <= 0:
        fail("INVALID_INPUT", "Probe context and positive command deadline are required.")
    cwd = root_path(cwd)
    if Path(argv[0]).suffix.lower() in (".cmd", ".bat"):
        fail("INVALID_INPUT", "Batch probes require an explicitly supplied trusted interpreter.")
    try:
        result = subprocess.run(list(argv), cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                shell=False, timeout=timeout_seconds, check=False)
        output, errors, code, timed_out = result.stdout, result.stderr, result.returncode, False
    except subprocess.TimeoutExpired as exc:
        output, errors, code, timed_out = exc.stdout or b"", exc.stderr or b"", None, True
    except OSError:
        output, errors, code, timed_out = b"", b"", None, False
    return {"version": 1, "status": "available" if code == 0 and not timed_out else "unavailable",
            "command_sha256": digest(list(argv)), "cwd": str(cwd),
            "context": context, "exit_code": code, "timed_out": timed_out,
            "stdout_sha256": sha256(output), "stderr_sha256": sha256(errors)}


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_INPUT", "Malformed command-line arguments; use --help for the interface.")


def main(argv=None) -> int:
    parser = JsonParser(description="Source-bound capability preflight; never dispatches a workflow.")
    sub = parser.add_subparsers(dest="operation", required=True)
    inspect = sub.add_parser("inspect-checkout")
    inspect.add_argument("--root", required=True, type=Path)
    inspect.add_argument("--expected-head", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--request", required=True, type=Path)
    preflight.add_argument("--observations", required=True, type=Path)
    verify = sub.add_parser("verify-preflight")
    verify.add_argument("--report", required=True, type=Path)
    verify.add_argument("--expected-request-sha256", required=True)
    verify.add_argument("--bindings", required=True, type=Path)
    try:
        args = parser.parse_args(argv)
        if args.operation == "inspect-checkout":
            result = inspect_checkout(args.root, expected_head=args.expected_head)
        elif args.operation == "preflight":
            result = evaluate_preflight(read_json(args.request), read_json(args.observations))
        else:
            require_preflight(read_json(args.report), expected_request_sha256=args.expected_request_sha256,
                              current_bindings=read_json(args.bindings))
            result = {"version": 1, "status": "READY"}
        sys.stdout.buffer.write(canonical(result))
        return 1 if result.get("status") == "BLOCKED" else 0
    except EnvironmentError as exc:
        sys.stdout.buffer.write(canonical(exc.as_dict()))
        return exc.exit_code
    except OSError:
        sys.stdout.buffer.write(canonical(EnvironmentError("INVALID_INPUT", "Filesystem input is unreadable.").as_dict()))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
