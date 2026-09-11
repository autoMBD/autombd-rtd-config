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
# File:        prevalidate_environment.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Execute bounded owner-Test support discrimination checks.
# =================================================================================

"""Owner-Test support self-checks, NEVER a Candidate or live-isolation pass.

The bounded samples below execute real Git, deployment and subprocess operations
through the acceptance driver. They implement only enough public-K behavior to
check the driver's good/bad discrimination. Production imports are not replaced
when pytest runs the actual acceptance file.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("issue79_prevalidate_support", HERE / "env_support.py")
s = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = s
spec.loader.exec_module(s)


class SampleError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

    def as_dict(self):
        return {"code": self.code, "origin": "owner-test-support-sample"}


class OperationSample:
    """Independent public-contract sample, not the #79 production runtime."""

    EnvironmentError = SampleError

    def __init__(self, *, permissive=False):
        self.permissive = permissive

    @staticmethod
    def required_capabilities(role):
        return ("filesystem-read", "filesystem-write", "git") if role in (
            "worker", "tester", "orchestrator") else ("filesystem-read",)

    @staticmethod
    def inspect_checkout(root, *, expected_head):
        head = s.git(root, "rev-parse", "HEAD")
        if head != expected_head:
            raise SampleError("STALE_IDENTITY")
        git_dir = Path(s.git(root, "rev-parse", "--absolute-git-dir"))
        common = Path(s.git(root, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = root / common
        linked = common.resolve() != git_dir.resolve()
        return {"root": str(root.resolve()), "head": head, "git_dir": str(git_dir.resolve()),
                "common_dir": str(common.resolve()), "checkout_kind": "worktree" if linked else "clone",
                "shared_objects": linked, "ref_isolated": not linked, "os_read_isolated": False}

    def create_isolated_checkout(self, source_root, target_root, *, allowed_target_base, branch, expected_source_head):
        assert target_root.resolve().is_relative_to(allowed_target_base.resolve())
        assert s.git(source_root, "rev-parse", "HEAD") == expected_source_head
        s.git(source_root, "clone", "--no-local", "--single-branch", "--branch", "public",
              str(source_root), str(target_root))
        s.git(target_root, "remote", "remove", "origin")
        s.git(target_root, "branch", "-m", branch)
        return self.inspect_checkout(target_root, expected_head=expected_source_head)

    def evaluate_preflight(self, request, observations):
        if request["bindings"] != observations["bindings"]:
            raise SampleError("STALE_IDENTITY")
        required = set(self.required_capabilities(request["role"])) | set(request["required_capabilities"])
        selected, diagnostics = [], []
        for name in sorted(required):
            available = next((item for item in observations["capabilities"] if item["id"] == name
                              and item["status"] == "available" and item["approved"]), None)
            if available:
                selected.append(available)
            else:
                diagnostics.append({"code": "CAPABILITY_UNAVAILABLE", "capability": name,
                                    "message": "Owner support sample has no authorized successful observation"})
        return {"version": 1, "status": "BLOCKED" if diagnostics else "READY",
                "request_sha256": s.sha(s.canonical(request)), "bindings": copy.deepcopy(request["bindings"]),
                "selected_capabilities": selected, "diagnostics": diagnostics}

    def require_preflight(self, report, *, expected_request_sha256, current_bindings):
        if self.permissive:
            return
        if report["request_sha256"] != expected_request_sha256 or report["bindings"] != current_bindings:
            raise SampleError("STALE_IDENTITY")
        if report["status"] != "READY":
            raise SampleError("CAPABILITY_UNAVAILABLE")

    @staticmethod
    def probe_command(argv, cwd, *, approved, context, timeout_seconds=60):
        assert approved
        try:
            result = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                    capture_output=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            return {"status": "unavailable", "context": context, "exit_code": None, "timed_out": True,
                    "stdout_sha256": s.sha(error.stdout or b""), "stderr_sha256": s.sha(error.stderr or b"")}
        return {"status": "available" if result.returncode == 0 else "unavailable", "context": context,
                "exit_code": result.returncode, "timed_out": False,
                "stdout_sha256": s.sha(result.stdout), "stderr_sha256": s.sha(result.stderr)}

    @staticmethod
    def snapshot_evidence(root, paths, *, bindings):
        return {"sample_version": 1, "identity": copy.deepcopy(bindings),
                "files": {path: s.sha((root / path).read_bytes()) for path in paths},
                "head": s.git(root, "rev-parse", "HEAD")}

    @staticmethod
    def verify_evidence(root, snapshot, *, bindings):
        if bindings != snapshot["identity"] or s.git(root, "rev-parse", "HEAD") != snapshot["head"]:
            raise SampleError("STALE_IDENTITY")
        for path, expected in snapshot["files"].items():
            if s.sha((root / path).read_bytes()) != expected:
                raise SampleError("STALE_IDENTITY")


class InitializationSample:
    """Uses accepted real collector/deployer; no initialization GUI or vendor."""

    EnvironmentError = SampleError

    @staticmethod
    def capture_initialization(source_root, input_path, *, expected_input_sha256):
        assert s.sha(input_path.read_bytes()) == expected_input_sha256
        config = json.loads(input_path.read_bytes())
        assert s.load(s.COLLECT).validate_input(config) == []
        assert (source_root / ".codex/agents/worker.toml").is_file()
        assert (source_root / ".agents/skills/agent-workflow").resolve() == (source_root / "agent-discipline/skills/agent-workflow").resolve()
        return {"sample_version": 1, "root": str(source_root.resolve()), "config": config}

    @staticmethod
    def hydrate_checkout(source_root, target_root, *, initialization, expected_initialization_sha256,
                         allowed_target_base, platforms, expected_target_head):
        assert expected_initialization_sha256 == s.sha(s.canonical(initialization))
        assert target_root.resolve().is_relative_to(allowed_target_base.resolve())
        assert set(platforms) <= set(initialization["config"]["platforms"])
        assert s.git(target_root, "rev-parse", "HEAD") == expected_target_head
        config = {**initialization["config"], "platforms": list(platforms), "mode": "update", "reset_confirmed": False}
        before = s.inventory(target_root)
        s.load(s.DEPLOY).deploy(target_root, config, verified_by="owner-test-support-sample")
        after = s.inventory(target_root)
        return {"status": "HYDRATED", "platforms": list(platforms),
                "changed_paths": sorted(path for path in after if before.get(path) != after[path])}


def main():
    spec = importlib.util.spec_from_file_location(
        "issue79_acceptance_driver_selfcheck", s.ROOT / "tests/functional/test_workflow_environment_acceptance.py")
    suite = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = suite
    spec.loader.exec_module(suite)
    observations = []

    def execute(label, operation, *, detected_failure=False):
        lab = s.Lab()
        try:
            if detected_failure:
                try:
                    operation(lab)
                except (AssertionError, pytest.fail.Exception) as error:
                    observations.append({"check": label, "result": "KNOWN_BAD_DETECTED",
                                         "kind": type(error).__name__, "message": str(error)})
                else:
                    raise AssertionError("Acceptance driver failed to detect the injected bad sample")
            else:
                operation(lab)
                observations.append({"check": label, "result": "SUPPORT_PASS"})
        finally:
            lab.close()

    suite.environment = lambda: OperationSample()
    suite.initializer = lambda: InitializationSample()
    if sys.argv[1:] == ["--known-bad"]:
        suite.environment = lambda: OperationSample(permissive=True)
        execute("intentional-known-bad-permissive-full-chain",
                suite.TestCliAndContract().test_c42_full_selected_chain_and_stale_dispatch_sentinel)
        raise AssertionError("Known-bad sample unexpectedly escaped the acceptance driver")
    if sys.argv[1:]:
        raise SystemExit("Only --known-bad is supported")
    execute("full-chain-real-Git-deployer-probe-sentinel-evidence",
            suite.TestCliAndContract().test_c42_full_selected_chain_and_stale_dispatch_sentinel)
    execute("real-linked-and-clone-topology", suite.TestCheckout().test_c02_real_worktree_clone_and_os_claims)
    execute("real-probe-literal-argv-stdin-digests",
            suite.TestProbesAndActor().test_c22_probe_uses_closed_stdin_literal_argv_and_output_digests)
    execute("real-probe-failed-and-timeout", suite.TestProbesAndActor().test_c23_failed_and_timed_out_probes_are_truthful)
    execute("ready-dispatch-driver", suite.TestCapabilities().test_c15_ready_requires_every_baseline_and_optional_absence_is_harmless)
    for fault in ("missing", "unavailable", "unknown", "unapproved"):
        execute("blocked-" + fault, lambda lab, fault=fault: suite.TestCapabilities().test_c16_mandatory_capability_failure_blocks_before_dispatch(lab, fault))
    suite.environment = lambda: OperationSample(permissive=True)
    execute("mutant-permissive-require-preflight",
            suite.TestCliAndContract().test_c42_full_selected_chain_and_stale_dispatch_sentinel,
            detected_failure=True)
    execute("mutant-blocked-dispatch",
            lambda lab: suite.TestCapabilities().test_c16_mandatory_capability_failure_blocks_before_dispatch(lab, "missing"),
            detected_failure=True)
    print(json.dumps({"version": 1, "kind": "OWNER_TEST_SUPPORT_SELFCHECK",
                      "candidate_test": False, "live_agent_or_os_isolation": False,
                      "vendor_validation": False, "observations": observations},
                     sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
