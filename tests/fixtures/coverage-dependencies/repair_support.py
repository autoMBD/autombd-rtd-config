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
# File:        repair_support.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Real source-bound add-only metadata repair fixtures.
# =================================================================================

"""K1 fixtures for fully bound add-only METADATA attribution repairs."""
import copy
import json
import subprocess
import sys

from support import Repository, canonical
from repair_protocol import changed_fields


class AttributionRepository(Repository):
    def __init__(self, root, version=4, count=1, multiple_checks=False):
        super().__init__(root, version=version)
        self.added = [f"checks/preload_{i}.py" for i in range(count)]
        executed = [self.paths["leaf"], *self.added]
        script = ("from pathlib import Path\nimport runpy\n"
                  "root = Path(__file__).resolve().parents[1]\n"
                  f"paths = {executed!r}\n"
                  "assert all(runpy.run_path(str(root / p))['VALUE'] == 11 for p in paths)\n"
                  "print('checked:' + ','.join(paths))\n")
        self.t = self.commit(self.t, {self.paths["test"]: script.encode(),
                                     **{p: b"VALUE = 11\n" for p in self.added}})
        self.git("read-tree", self.i)
        for path in self.changed(self.t):
            row = self.git("ls-tree", self.t, "--", path).split("\t")[0].split()
            self.git("update-index", "--add", "--cacheinfo", row[0] + "," + row[2] + "," + path)
        self.c = self.git("commit-tree", self.git("write-tree"), "-p", self.t, "-p", self.i, "-m", "real repair union")
        self.git("reset", "--hard", self.t)
        self.affected = ["TEST", "SUPPORT"] if multiple_checks else ["TEST"]
        for check in self.impact_body["selected_checks"]:
            if check["id"] in self.affected:
                check["argv"] = [sys.executable, "-B", self.paths["test"]]
        self.impact_body["public_dependency_edges"].extend(
            {"from": self.paths["test"], "to": path, "reason": "Frozen gate executes this exact preload with runpy"}
            for path in self.added)
        self.rebind()

    def context(self, ref):
        context = super().context(ref)
        context["expected_head"] = self.t
        return context

    def invocation(self):
        outputs = []
        for check in self.impact_body["selected_checks"]:
            if check["id"] not in self.affected:
                continue
            result = subprocess.run(check["argv"], cwd=self.root, capture_output=True, timeout=30)
            assert result.returncode == 0, result.stderr
            assert all(path.encode() in result.stdout for path in self.added)
            outputs.append(check["id"].encode() + b":" + result.stdout)
        return b"".join(outputs)

    def snapshot(self, ref):
        return {"ref": ref, "raw": (self.root / ref["path"]).read_bytes().decode()}

    def repair(self):
        self.invocation()
        code, receipt = self.validate(self.tr)
        assert code == 0, receipt
        checked = self.store(receipt)
        before = copy.deepcopy(self.impact_body)
        after = copy.deepcopy(before)
        for check in after["selected_checks"]:
            if check["id"] in self.affected:
                check["covered_paths"].extend(self.added)
        new_ref = self.evidence("impact-set", after)
        facts = [self.source(self.t, p) for p in (self.paths["test"], *self.added)]
        description = ("The exact preserved Test gate runs all listed preload paths with runpy before this repair. "
                       "Only omitted covered_paths attribution is added; original commands, inputs, assertions and pass criteria remain unchanged.")
        mapping = {"field": "impact_set", "before": self.snapshot(self.impact), "after": self.snapshot(new_ref),
                   "changed_fields": changed_fields(before, after), "reason": description,
                   "source_facts": facts, "dependency_audit": []}
        audit = {"requirement_ids": ["R", "S"], "source_bindings": facts,
                 "dimensions": [{"dimension": name, "before": description, "after": description,
                                 "explanation": "Verified exact preserved source blobs and unchanged argv. " + name}
                                for name in ("scenarios", "conditions", "assertions", "expected_results", "pass_fail_criteria",
                                             "selected_checks", "exclusions", "coverage")],
                 "affected_check_ids": list(self.affected), "reviewer_role": "orchestrator", "reviewer_id": "source-auditor"}
        tag = str(self.serial)
        payload = {"repair_version": "1.0", "mode": "METADATA", "dispatch_id": "metadata-" + tag,
                   "original": self.tr, "trigger": {"kind": "ORCHESTRATOR_OBSERVED", "checked": checked,
                   "observation": description}, "lane": self.lane("test"),
                   "replacement_output": ".agent-state/replacement-" + tag + ".json", "reason": description,
                   "attachment_changes": [mapping], "semantic_audit": audit, "preserve_tip": self.t,
                   "preserve_candidate_index": None, "preserve_correction_count": 0, "preserve_review_id": None}
        ref = self.artifact("delivery-repair", payload, [self.tr, checked])
        body = self.objects[ref["artifact_id"]]
        body["consumer_role"] = "tester"
        body["visibility"] = "tester-confidential"
        ref = self.store(body)
        replacement = copy.deepcopy(self.objects[self.tr["artifact_id"]])
        replacement.update(artifact_id="replacement-" + tag, replaces={"original": self.tr, "repair": ref})
        replacement["predecessors"].extend([self.tr, ref])
        replacement["payload"].update(dispatch_id=payload["dispatch_id"], impact_set=new_ref)
        return ref, self.store(replacement)

    def changed_repair(self, ref, mutation):
        body = copy.deepcopy(self.objects[ref["artifact_id"]])
        body["artifact_id"] += "-invalid-" + mutation
        payload = body["payload"]
        mapping = payload["attachment_changes"][0]
        after = json.loads(mapping["after"]["raw"])
        check = next(c for c in after["selected_checks"] if c["id"] == "TEST")
        if mutation == "no-added-binding":
            payload["semantic_audit"]["source_bindings"] = payload["semantic_audit"]["source_bindings"][:1]
            mapping["source_facts"] = mapping["source_facts"][:1]
        elif mutation == "wrong-blob":
            for facts in (payload["semantic_audit"]["source_bindings"], mapping["source_facts"]):
                facts[-1]["blob"] = self.source(self.t, self.paths["test"])["blob"]
        elif mutation == "wrong-source":
            for facts in (payload["semantic_audit"]["source_bindings"], mapping["source_facts"]):
                facts[-1]["commit"] = self.g
        elif mutation == "no-affected-checks":
            payload["semantic_audit"]["affected_check_ids"] = []
        elif mutation == "partial-affected-checks":
            payload["semantic_audit"]["affected_check_ids"] = ["TEST"]
        elif mutation == "extra-affected-check":
            payload["semantic_audit"]["affected_check_ids"].append("UNKNOWN")
        elif mutation == "empty-audit":
            payload["semantic_audit"]["dimensions"] = []
        elif mutation == "missing-coverage-dimension":
            payload["semantic_audit"]["dimensions"] = [d for d in payload["semantic_audit"]["dimensions"] if d["dimension"] != "coverage"]
        elif mutation == "wrong-preserved-tip":
            payload["preserve_tip"] = self.g
        elif mutation == "missing-changed-fields":
            mapping["changed_fields"] = []
        elif mutation == "permission-flag":
            payload["allow_coverage_addition"] = True
            payload["semantic_audit"]["dimensions"] = []
        elif mutation == "remove-old-path":
            check["covered_paths"].remove(self.paths["review"])
        elif mutation == "transfer-old-path":
            check["covered_paths"].remove(self.paths["review"])
            next(c for c in after["selected_checks"] if c["id"] == "SUPPORT")["covered_paths"].append(self.paths["review"])
        elif mutation == "argv":
            check["argv"][-1] = "checks/another.py"
        elif mutation == "check-id":
            check["id"] = "NEW"
        elif mutation == "family":
            check["family"] = "unit"
        elif mutation == "requirements":
            check["requirement_ids"] = ["R"]
        elif mutation == "exclusions":
            after["excluded_checks"] = []
        elif mutation == "prevalidation":
            after["prevalidation_obligations"][0]["mode"] = "KNOWN_GOOD"
        else:
            raise AssertionError(mutation)
        if after != json.loads(mapping["after"]["raw"]):
            new_ref = self.evidence("impact-set", after)
            mapping["after"] = self.snapshot(new_ref)
            mapping["changed_fields"] = changed_fields(json.loads(mapping["before"]["raw"]), after)
        return self.store(body)

    def repaired_candidate(self, replacement):
        body = copy.deepcopy(self.objects[self.envelope["artifact_id"]])
        new_impact = self.objects[replacement["artifact_id"]]["payload"]["impact_set"]
        impact = json.loads((self.root / new_impact["path"]).read_bytes())
        join = copy.deepcopy(self.join_body)
        join["impact_set_sha256"] = new_impact["sha256"]
        for row in join["changed_paths"]:
            row["selected_check_ids"] = [c["id"] for c in impact["selected_checks"] if row["path"] in c["covered_paths"]]
        body["payload"].update(impact_set=new_impact, coverage_join=self.evidence("coverage-join", join))
        body["predecessors"] = [self.approval, replacement, self.ir]
        body["artifact_id"] += "-repaired"
        return self.store(body)
