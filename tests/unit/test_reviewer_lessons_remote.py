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
# File:        test_reviewer_lessons_remote.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.0
# Description: Focused W4 lesson-head remote finalization regressions.
# =================================================================================

"""Remote-stage tests; local graph validation and real Git proofs are separate."""

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS = (Path(__file__).resolve().parents[2] /
           "agent-discipline/skills/agent-workflow/scripts")
sys.path.insert(0, str(SCRIPTS))
from workflow_evidence_io import WorkflowEvidenceError
from workflow_evidence_remote import RemoteProof


class ReviewerLessonsRemote(unittest.TestCase):
    G, C, L, M = (character * 40 for character in "abce")
    C_TREE, L_TREE = (character * 40 for character in "df")

    def setUp(self):
        self.configure()

    def configure(self, version=4, *, merged=False, fast_forward=False):
        """Supply the exact RemoteProof boundary after local source verification."""
        publication = self.L if version == 4 else self.C
        publication_tree = self.L_TREE if version == 4 else self.C_TREE
        merge_sha = publication if fast_forward else self.M
        self.terminal = {
            "result": "SUCCESS", "accepted_candidate": self.C,
            "disposition": "MERGED" if merged else "OPEN_SUCCESS_PR",
            "pr": {"url": "https://github.com/sample/repository/pull/431",
                   "head_sha": publication, "merge_sha": merge_sha if merged else None},
        }
        self.review = {"verdict": "APPROVED"}
        if version == 4:
            self.review["lesson_commit"] = {
                "commit": self.L, "tree": self.L_TREE, "parents": [self.C]}
        self.result = {"candidate_sha": self.C, "outcome": "PASS"}
        self.final = {"gate": "FINAL", "decision": "APPROVE", "subject_sha": publication}
        artifacts = {name: {"payload": payload} for name, payload in {
            "terminal": self.terminal, "review": self.review, "result": self.result,
            "candidate": {"candidate": {"commit": self.C, "tree": self.C_TREE}},
            "final": self.final,
        }.items()}
        state = {
            "task": {"repository": "sample/repository", "issue_number": 827},
            "governor": {"commit": self.G}, "terminal": {"artifact_id": "terminal"},
            "candidate": {"envelope": {"artifact_id": "candidate"},
                          "result": {"artifact_id": "result"}},
            "review": {"report": {"artifact_id": "review"}},
            "final_decision": {"artifact_id": "final"} if merged else None,
        }
        self.tips = {
            self.C: {"commit": self.C, "tree": self.C_TREE, "parents": ["1" * 40, "2" * 40]},
            self.L: {"commit": self.L, "tree": self.L_TREE, "parents": [self.C]},
            self.M: {"commit": self.M, "tree": publication_tree, "parents": [self.G, publication]},
        }
        self.graph = SimpleNamespace(state=state, artifacts=artifacts,
                                     workflow_version=version, tip=self.tips.__getitem__)
        self.remote = {
            "number": 431, "html_url": self.terminal["pr"]["url"],
            "base": {"repo": {"full_name": "sample/repository"},
                     "ref": "master", "sha": self.G},
            "head": {"sha": publication}, "state": "closed" if merged else "open",
            "merged": merged, "merge_commit_sha": merge_sha if merged else None,
        }
        self.calls = []
        def get(endpoint):
            self.calls.append(endpoint)
            self.assertEqual("/repos/sample/repository/pulls/431", endpoint)
            return {"status": 200, "body": copy.deepcopy(self.remote)}
        self.proof = RemoteProof(self.graph, {"base_ref": "master"}, get)

    def rejects(self, pointer):
        with self.assertRaises(WorkflowEvidenceError) as caught:
            self.proof.finalization()
        self.assertEqual("INVALID_EVIDENCE", caught.exception.code)
        self.assertEqual(pointer, caught.exception.pointer)

    def test_w4_open_pr_binds_l_without_relabeling_tested_c(self):
        before = copy.deepcopy((self.graph.state, self.graph.artifacts))
        self.assertEqual("PASS", self.proof.finalization())
        self.assertEqual(before, (self.graph.state, self.graph.artifacts))
        self.assertEqual(self.C, self.terminal["accepted_candidate"])
        self.assertEqual(self.C, self.result["candidate_sha"])

    def test_w4_merged_accepts_exact_l_fast_forward_and_two_parent_merge(self):
        for fast_forward in (False, True):
            with self.subTest(fast_forward=fast_forward):
                self.configure(merged=True, fast_forward=fast_forward)
                self.remote["base"]["sha"] = "9" * 40
                self.assertEqual("PASS", self.proof.finalization())
                self.assertEqual(self.C, self.terminal["accepted_candidate"])

    def test_w4_rejects_stale_c_pr_even_when_local_and_remote_agree(self):
        self.terminal["pr"]["head_sha"] = self.C
        self.remote["head"]["sha"] = self.C
        self.rejects("/terminal/pr")

    def test_w4_rejects_remote_c_head_despite_local_l_record(self):
        self.remote["head"]["sha"] = self.C
        self.rejects("/terminal/pr")

    def test_w4_rejects_stale_c_final_approval(self):
        self.configure(merged=True)
        self.final["subject_sha"] = self.C
        self.rejects("/terminal/approval")

    def test_w4_rejects_merge_of_c_instead_of_l(self):
        self.configure(merged=True)
        self.tips[self.M] = {"commit": self.M, "tree": self.C_TREE,
                             "parents": [self.G, self.C]}
        self.rejects("/terminal/merge")

    def test_w4_rejects_fast_forward_c_instead_of_l(self):
        self.configure(merged=True)
        self.terminal["pr"]["merge_sha"] = self.C
        self.remote["merge_commit_sha"] = self.C
        self.rejects("/terminal/merge")

    def test_w4_rejects_l_merge_with_changed_tree_or_parent_order(self):
        for change in ({"tree": self.C_TREE}, {"parents": [self.L, self.G]}):
            with self.subTest(change=change):
                self.configure(merged=True)
                self.tips[self.M].update(change)
                self.rejects("/terminal/merge")

    def test_w4_requires_l_even_before_pr_exists(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.configure()
                self.terminal["pr"] = None
                if missing:
                    del self.review["lesson_commit"]
                else:
                    self.review["lesson_commit"] = None
                self.rejects("/terminal/lesson_commit")

    def test_w4_pre_pr_still_has_no_remote_finalization(self):
        self.terminal["pr"] = None
        self.assertEqual("NOT_APPLICABLE", self.proof.finalization())
        self.assertEqual([], self.calls)

    def test_w4_preserves_tested_and_accepted_c_identity_requirements(self):
        for field in ("tested", "accepted"):
            with self.subTest(field=field):
                self.configure()
                if field == "tested":
                    self.result["candidate_sha"] = self.L
                else:
                    self.terminal["accepted_candidate"] = self.L
                self.rejects("/terminal")

    def test_w4_failure_keeps_l_without_success_fields_or_remote_access(self):
        self.terminal.update(result="FAILURE", disposition="RECORD_FAILURE",
                             accepted_candidate=None, pr=None)
        self.review["verdict"] = "REJECTED"
        before = copy.deepcopy(self.graph.artifacts)
        self.assertEqual("PASS", self.proof.finalization())
        self.assertEqual(before, self.graph.artifacts)
        self.assertEqual([], self.calls)

    def test_w2_w3_keep_c_open_and_merged_semantics(self):
        for version in (2, 3):
            for merged, fast_forward in ((False, False), (True, False), (True, True)):
                with self.subTest(version=version, merged=merged, fast_forward=fast_forward):
                    self.configure(version, merged=merged, fast_forward=fast_forward)
                    self.assertNotIn("lesson_commit", self.review)
                    self.assertEqual("PASS", self.proof.finalization())

    def test_w2_w3_reject_l_as_publication_head(self):
        for version in (2, 3):
            with self.subTest(version=version):
                self.configure(version)
                self.terminal["pr"]["head_sha"] = self.L
                self.remote["head"]["sha"] = self.L
                self.rejects("/terminal/pr")


if __name__ == "__main__":
    unittest.main()
