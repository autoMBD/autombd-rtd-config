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
# File:        handoff_guard.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-20
# Version:     0.1.0
# Description: Validate and execute one exact workflow handoff.
# =================================================================================

import argparse, hashlib, json, os, re, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath


MANIFEST_KEYS = {"schema_version", "role", "git_top_level", "base_sha", "lane_sha",
                 "contract_path", "contract_blob_sha", "argv", "timeout_seconds"}
RECEIPT_KEYS = {"schema_version", "operation", "started_at_utc", "ended_at_utc", "cwd",
                "git_top_level", "expected_head", "actual_head", "manifest_path",
                "manifest_sha256", "argv", "timeout_seconds", "outcome", "exit_code", "error"}
SHA_RE, ROLE_RE = re.compile(r"[0-9a-f]{40}\Z"), re.compile(r"[a-z][a-z0-9_-]*\Z")


class Rejected(Exception): pass


def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical(path): return str(Path(path).resolve())


def json_bytes(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def atomic_write(path, data):
    target = Path(path)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def probe(receipt_path, event_path):
    for path, append in ((receipt_path, False), (event_path, True)):
        target = Path(path)
        if not target.parent.is_dir() or target.is_dir():
            raise OSError(f"evidence path is not writable: {target}")
        descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".handoff-probe.")
        os.close(descriptor); os.unlink(temporary)
        if append and target.exists():
            with target.open("ab"): pass


def emit(ctx, receipt_path, event_path, outcome, exit_code, error):
    value = {"schema_version": 1, **ctx, "ended_at_utc": utc_now(), "outcome": outcome, "exit_code": exit_code, "error": error}
    data = json_bytes(value)
    atomic_write(receipt_path, data)
    with Path(event_path).open("ab") as stream:
        stream.write(data + b"\n")


def reject(message): raise Rejected(message)


def unique_object(pairs):
    value = dict(pairs)
    len(value) == len(pairs) or reject("manifest contains a duplicate object key")
    return value


def trusted_git(*lanes):
    names = ("git.exe", "git") if os.name == "nt" else ("git",)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        directory = Path(entry)
        if not entry or not directory.is_absolute(): continue
        for name in names:
            candidate = directory / name
            if candidate.is_file() and (os.name == "nt" or os.access(candidate, os.X_OK)):
                resolved = candidate.resolve()
                any(Path(lane) == resolved or Path(lane) in resolved.parents for lane in lanes) and reject(
                    "resolved Git executable is inside the current lane")
                return str(resolved)
    reject("trusted Git executable was not found on absolute PATH entries")


def git(executable, *arguments, cwd):
    try:
        return subprocess.run([executable, *arguments], cwd=cwd, check=True, text=True,
                              capture_output=True).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise Rejected("Git identity command failed") from error


def paths_overlap(paths):
    resolved = [Path(path).resolve() for path in paths]
    return any(os.path.normcase(str(left)) == os.path.normcase(str(right)) or
               (left.exists() and right.exists() and os.path.samefile(left, right))
               for index, left in enumerate(resolved) for right in resolved[index + 1:])


def unsafe_windows_spelling(paths):
    return os.name == "nt" and any(part.endswith((".", " "))
                                   for path in paths for part in Path(path).parts)


def safe_relative(value):
    if not isinstance(value, str) or not value or PureWindowsPath(value).drive: return False
    parts = value.replace("\\", "/").split("/"); return not value.startswith(("/", "\\")) and all(
        part not in ("", ".", "..") for part in parts)


def validate_manifest(value):
    isinstance(value, dict) and set(value) == MANIFEST_KEYS or reject(
            "manifest keys do not match the closed schema")
    type(value["schema_version"]) is int and value["schema_version"] == 1 or reject(
            "schema_version must be integer 1")
    isinstance(value["role"], str) and ROLE_RE.fullmatch(value["role"]) or reject("role is invalid")
    for name in ("base_sha", "lane_sha", "contract_blob_sha"):
        isinstance(value[name], str) and SHA_RE.fullmatch(value[name]) or reject(
                f"{name} must be a lowercase full SHA")
    top = value["git_top_level"]; isinstance(top, str) and Path(top).is_absolute() and canonical(top) == top or reject(
            "git_top_level must be a canonical absolute path")
    safe_relative(value["contract_path"]) or reject("contract_path must be a safe relative path")
    argv = value["argv"]; isinstance(argv, list) and argv and all(isinstance(x, str) and x for x in argv) or reject(
            "argv must contain nonempty strings")
    timeout = value["timeout_seconds"]; type(timeout) is int and timeout > 0 or reject(
                                                "timeout_seconds must be a positive integer")


def verify_identity(manifest, ctx, executable):
    current = ctx["cwd"]
    actual_top = canonical(git(executable, "rev-parse", "--show-toplevel", cwd=current))
    actual_head = git(executable, "rev-parse", "--verify", "HEAD", cwd=current)
    ctx["git_top_level"], ctx["actual_head"] = actual_top, actual_head
    current == manifest["git_top_level"] == actual_top or reject(
            "current directory does not match git_top_level")
    actual_head == manifest["lane_sha"] or reject("current HEAD does not match lane_sha")
    base_type = git(executable, "cat-file", "-t", manifest["base_sha"], cwd=actual_top)
    base_type == "commit" or reject("base_sha does not name a commit")
    git(executable, "merge-base", "--is-ancestor", manifest["base_sha"],
        manifest["lane_sha"], cwd=actual_top)
    blob = git(executable, "hash-object", "--", manifest["contract_path"], cwd=actual_top)
    blob == manifest["contract_blob_sha"] or reject(
            "current contract blob does not match contract_blob_sha")


def load_manifest(path, ctx):
    raw = Path(path).read_bytes()
    ctx["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Rejected("manifest is not valid UTF-8 JSON") from error
    validate_manifest(value)
    ctx.update(expected_head=value["lane_sha"], argv=value["argv"],
               timeout_seconds=value["timeout_seconds"])
    return value


def verify_receipt(path, manifest_sha256):
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Rejected("prior receipt is missing or malformed") from error
    isinstance(value, dict) or reject("prior receipt is malformed")
    value.get("manifest_sha256") == manifest_sha256 or reject(
            "prior receipt does not match the current manifest digest")
    return value, raw


def verify_checked_receipt(prior_receipt, event_path, ctx):
    value, raw = prior_receipt
    (set(value) == RECEIPT_KEYS and type(value.get("schema_version")) is int
     and value["schema_version"] == 1 and value.get("operation") == "check-handoff"
     and value.get("outcome") == "CHECKED" and type(value.get("exit_code")) is int
     and value["exit_code"] == 0 and value.get("error") is None) or reject(
            "run requires the immediately preceding successful CHECKED receipt")
    for field in ("cwd", "git_top_level", "expected_head", "actual_head", "manifest_path",
                  "manifest_sha256", "argv", "timeout_seconds"):
        type(value[field]) is type(ctx[field]) and value[field] == ctx[field] or reject(
            f"successful CHECKED receipt {field} does not match current identity")
    try:
        with Path(event_path).open("rb") as stream:
            last_event = b""
            for last_event in stream:
                pass
    except OSError as error:
        raise Rejected("prior event log is missing or unreadable") from error
    last_event == raw + b"\n" or reject(
            "successful CHECKED receipt does not match the immediately preceding event")


def parse_args():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="operation", required=True)
    prepare = commands.add_parser("prepare")
    for option in ("role", "expected-top-level", "base-sha", "lane-sha", "contract-path",
                   "contract-blob-sha", "manifest", "receipt", "event-log"):
        prepare.add_argument(f"--{option}", required=True)
    timeout = prepare.add_mutually_exclusive_group(required=True)
    timeout.add_argument("--command-timeout-seconds", dest="timeout_seconds", type=int,
                         help="deterministic child-command deadline; not an Agent task deadline")
    timeout.add_argument("--timeout-seconds", dest="timeout_seconds", type=int,
                         help="v1 compatibility alias for --command-timeout-seconds")
    prepare.add_argument("command", nargs=argparse.REMAINDER)
    for operation in ("check-handoff", "run"):
        command = commands.add_parser(operation)
        for option in ("manifest", "receipt", "event-log"):
            command.add_argument(f"--{option}", required=True)
    artifact = commands.add_parser("validate-artifact")
    for option in ("artifact", "expected-sha256", "context", "result"):
        artifact.add_argument(f"--{option}", required=True)
    artifact.add_argument("--view", choices=("orchestrator-full", "consumer-local"), required=True)
    interface = commands.add_parser("validate-interface")
    interface.add_argument("--packet", required=True)
    interface.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    if args.operation == "prepare":
        if not args.command or args.command[0] != "--": parser.error("prepare requires -- CMD [ARG...]")
        args.argv = args.command[1:]
    return args


def main():
    args = parse_args()
    if args.operation == "validate-artifact":
        from structured_handoff import run_validation
        return run_validation(args.artifact, args.expected_sha256, args.context, args.view, args.result)
    if args.operation == "validate-interface":
        from legacy_interface_handoff import run_validation
        return run_validation(args.packet, args.expected_sha256)
    ctx = {"operation": args.operation, "started_at_utc": utc_now(), "cwd": canonical(Path.cwd()),
           "git_top_level": None, "expected_head": None, "actual_head": None,
           "manifest_path": canonical(args.manifest), "manifest_sha256": None,
           "argv": None, "timeout_seconds": None}
    outcome, code, error = "EXEC_ERROR", 2, None
    try:
        evidence_paths = [args.manifest, args.receipt, args.event_log]
        if unsafe_windows_spelling(evidence_paths) or paths_overlap(evidence_paths):
            print("handoff guard rejected aliased manifest/evidence paths", file=sys.stderr); return 1
        if args.operation == "prepare":
            manifest = {"schema_version": 1, "role": args.role, "base_sha": args.base_sha,
                        "lane_sha": args.lane_sha, "contract_path": args.contract_path,
                        "contract_blob_sha": args.contract_blob_sha, "argv": args.argv,
                        "timeout_seconds": args.timeout_seconds,
                        "git_top_level": canonical(args.expected_top_level)}
            ctx.update(expected_head=args.lane_sha, argv=args.argv, timeout_seconds=args.timeout_seconds)
            validate_manifest(manifest)
        else:
            manifest = load_manifest(args.manifest, ctx)
        contract = Path(manifest["git_top_level"], manifest["contract_path"])
        if paths_overlap([*evidence_paths, contract]):
            print("handoff guard rejected a path alias with the contract", file=sys.stderr); return 1
        probe(args.receipt, args.event_log)
        if args.operation != "prepare":
            prior_receipt = verify_receipt(args.receipt, ctx["manifest_sha256"])
        executable = trusted_git(ctx["cwd"], manifest["git_top_level"])
        verify_identity(manifest, ctx, executable)
        if args.operation == "prepare":
            raw = json_bytes(manifest); atomic_write(args.manifest, raw)
            ctx["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
            outcome, code = "PREPARED", 0
        elif args.operation == "check-handoff":
            outcome, code = "CHECKED", 0
        else:
            verify_checked_receipt(prior_receipt, args.event_log, ctx)
            result = subprocess.run(manifest["argv"], cwd=manifest["git_top_level"], shell=False,
                                    timeout=manifest["timeout_seconds"])
            outcome, code = "EXITED", result.returncode
    except Rejected as failure:
        outcome, code, error = "REJECTED", 1, str(failure)
    except subprocess.TimeoutExpired as failure:
        outcome, code, error = "TIMED_OUT", 124, str(failure)
    except (OSError, ValueError, subprocess.SubprocessError) as failure:
        outcome, code, error = "EXEC_ERROR", 2, str(failure)
    try:
        emit(ctx, args.receipt, args.event_log, outcome, code, error)
    except OSError as failure:
        print(f"handoff guard evidence error: {failure}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
