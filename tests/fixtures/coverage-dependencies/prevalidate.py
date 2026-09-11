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
# File:        prevalidate.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Capture real authoring checks and controlled reference evidence.
# =================================================================================

"""Capture actual K0 authoring evidence; references never certify a Candidate."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
G = "cf78144a3786d1dc3f1e92d27157674a7ebea85c"
REL = "agent-discipline/skills/agent-workflow"
REGRESSIONS = [
    "tests/unit/test_handoff_repair_guard.py::test_observed_checked_metadata_and_fresh_replacement_guard",
    "tests/unit/test_handoff_repair_guard.py::test_incremental_support_guard_uses_actual_new_test_source",
    "tests/unit/test_handoff_repair_guard.py::test_support_guard_rejects_forged_or_semantic_mutations",
    "tests/unit/test_handoff_repair_guard.py::test_real_guard_to_reducer_metadata_does_not_repeat_approval",
    "tests/unit/test_handoff_repair_guard.py::test_support_retest_requires_fresh_result_ref_even_for_identical_pass",
    "tests/unit/test_handoff_repair_schema.py::test_gate_retains_explicit_legacy_v1",
    "tests/unit/test_handoff_repair_schema.py::test_gate_loads_supported_declarations_but_never_as_legacy_records",
    "tests/functional/test_workflow_evidence.py::test_source_projection_and_count_are_independent",
    "tests/functional/test_workflow_evidence.py::test_present_attachment_tamper_is_invalid",
    "tests/functional/test_workflow_evidence.py::test_real_candidate_direct_union_not_only_parent_claim",
]

REFERENCE_JOIN = '''    def coverage_join(self, a):
        """Controlled K0 reference, never a delivered implementation."""
        payload = a["payload"]
        require(payload["coverage_join"]["evidence_type"] == "coverage-join", "COVERAGE_JOIN_TYPE")
        joined = self.g.evidence(payload["coverage_join"])
        require(joined["test_commit"] == payload["test_tip"]["commit"] and
                joined["implementation_commit"] == payload["implementation_tip"]["commit"] and
                joined["impact_set_sha256"] == payload["impact_set"]["sha256"], "COVERAGE_JOIN_IDENTITY")
        real = {"TEST": self.g.changed_paths(joined["test_commit"]),
                "IMPLEMENTATION": self.g.changed_paths(joined["implementation_commit"])}
        require(not real["TEST"].intersection(real["IMPLEMENTATION"]), "OWNERSHIP_OVERLAP")
        unique([item["path"] for item in joined["changed_paths"]], "COVERAGE_DUPLICATE_PATH")
        for owner in real:
            require(real[owner] == {item["path"] for item in joined["changed_paths"] if item["owner"] == owner}, "COVERAGE_CHANGED_PATHS")
        impact = self.impact(a, payload["impact_set"])
        checks = {check["id"]: check for check in impact["selected_checks"]}
        requirements = {item["id"] for item in self.g.contract(a)["payload"]["requirements"]}
        for item in joined["changed_paths"]:
            require(set(item["requirement_ids"]) <= requirements and set(item["selected_check_ids"]) <= checks.keys(), "COVERAGE_REFERENCE")
            for identifier in item["selected_check_ids"]:
                check = checks[identifier]
                require(item["path"] in check["covered_paths"] and set(item["requirement_ids"]) <= set(check["requirement_ids"]), "COVERAGE_JOIN_MISSING")
        pairs = [(edge["from"], edge["to"]) for edge in impact["public_dependency_edges"]]
        unique(pairs, "DEPENDENCY_EDGE")
        paths = {path for check in checks.values() for path in check["covered_paths"]}
        for start, end in pairs:
            require(start in paths and end in paths, "PUBLIC_DEPENDENCY_MISSING")

'''


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True, timeout=30).stdout


def reference(directory):
    records = []
    paths = git("ls-tree", "-r", "--name-only", G, "--", REL + "/scripts", REL + "/schemas").decode().splitlines()
    paths.append(REL + "/references/structured-handoffs.md")
    for path in paths:
        raw = git("show", G + ":" + path)
        original = hashlib.sha256(raw).hexdigest()
        if path.endswith("/structured_handoff_rules.py"):
            text = raw.decode()
            start = text.index("    def coverage_join(self, a):")
            end = text.index("    def tester_confidential_report", start)
            raw = (text[:start] + REFERENCE_JOIN + text[end:]).encode()
        elif path.endswith("/structured-handoffs.md"):
            raw += b"\nControlled K0 reference only: covered_paths assigns checks; public_dependency_edges declares directed source relationships. Shared coverage does not imply direct edges. Each declared endpoint needs selected coverage, and directed pairs are unique. Orchestrator checks exact source truth, completeness and reason; structural CHECKED does not execute commands or authenticate approval. An upgraded verifier records its own exact source while retaining each task Governor and W2/W3/W4; explicit W1 behavior remains unchanged.\n"
        target = directory / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        records.append({"path": path, "governor_sha256": original, "reference_sha256": hashlib.sha256(raw).hexdigest()})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("red", "known-good", "known-bad", "reference", "regressions"))
    parser.add_argument("--identity", required=True)
    args = parser.parse_args()
    if not args.identity.replace("-", "").replace("_", "").isalnum():
        parser.error("identity must be a safe local identifier")
    out = ROOT / ".agent-state/agent-loop/issue116-20260911-coverage-dependencies/evidence" / args.identity
    out.mkdir(parents=True, exist_ok=False)
    temp = ROOT / "tests/.tmp" / args.identity
    temp.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop("RTD_COVERAGE_SCRIPTS", None)
    env.pop("RTD_COVERAGE_SOURCE_ROOT", None)
    metadata = {"mode": args.mode, "governor": G, "environment_id": "windows-host-python314-real-git", "source": []}
    if args.mode == "reference":
        ref = temp / "controlled-reference"
        metadata["source"] = reference(ref)
        env["RTD_COVERAGE_SCRIPTS"] = str(ref / REL / "scripts")
        env["RTD_COVERAGE_SOURCE_ROOT"] = str(ref)
    if args.mode == "known-bad":
        script = ("from pathlib import Path; import sys; "
            "sys.path.insert(0,'tests/fixtures/coverage-dependencies'); from support import Repository; "
            "h=Repository(Path(" + repr(str(temp / "known-bad")) + ")); "
            "h.join_body['changed_paths'].pop(); h.replace_join(h.join_body); "
            "code,result=h.validate(); print(result); raise SystemExit(code)")
        argv = [sys.executable, "-c", script]
    else:
        nodes = ["tests/functional/test_coverage_dependencies.py", "tests/functional/test_coverage_dependencies_scope.py"]
        if args.mode == "known-good":
            nodes = ["tests/functional/test_coverage_dependencies.py::test_known_good_full_local_chain_and_cli"]
        elif args.mode == "regressions":
            nodes = REGRESSIONS
        argv = [sys.executable, "-m", "pytest", *nodes, "-q", "--basetemp", str(temp / "pytest"),
                "--junitxml", str(out / "junit.xml")]
    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, timeout=1200)
    (out / "stdout.log").write_bytes(result.stdout)
    (out / "stderr.log").write_bytes(result.stderr)
    body = {"schema_version": "1.0", "argv": argv, "cwd": ".", "exit_code": result.returncode,
            "outcome": "PASS" if result.returncode == 0 else "FAIL", "environment_id": metadata["environment_id"]}
    (out / "command-result.json").write_bytes(canonical(body))
    metadata.update(command=body, actual_environment_overrides={k: env[k] for k in ("RTD_COVERAGE_SCRIPTS", "RTD_COVERAGE_SOURCE_ROOT") if k in env},
        source_tip=git("rev-parse", "HEAD").decode().strip(),
        owned_sources={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                      for folder in (ROOT / "tests/fixtures/coverage-dependencies", ROOT / "tests/functional")
                      for p in folder.glob("*") if p.is_file() and (folder.name == "coverage-dependencies" or p.name.startswith("test_coverage_dependencies"))})
    (out / "execution-context.json").write_bytes(canonical(metadata))
    print(result.stdout.decode("utf-8", errors="replace"))
    print(result.stderr.decode("utf-8", errors="replace"))
    print("Evidence:", out.relative_to(ROOT).as_posix())
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
