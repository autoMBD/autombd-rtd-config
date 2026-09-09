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
# File:        test_workflow_evidence_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-10
# Version:     0.1.2
# Description: Worker-owned real-source workflow evidence generality.
# =================================================================================

import copy
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from workflow_evidence_generality_support import EvidenceHistory, ROOT, SCRIPTS
sys.path.insert(0, str(SCRIPTS))
from workflow_transition_wire import canonical, digest
from unittest import mock


class WorkflowEvidenceGenerality(unittest.TestCase):
    def setUp(self):
        self.assertTrue((SCRIPTS / "workflow_evidence.py").is_file(),
                        "The public read-only verifier must exist.")
        self.api = importlib.import_module("workflow_evidence")
        base = ROOT / "tests/.tmp"
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="worker-evidence-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.h = EvidenceHistory(Path(self.temp.name) / "repo")

    def verify(self, **kwargs):
        return self.api.verify_evidence(self.h.state, context=self.h.context_data,
            repository_root=str(self.h.root.resolve()), authority=self.h.authority,
            github_get=self.h.get, **kwargs)

    def rejects(self, code, **kwargs):
        with self.assertRaises(self.api.WorkflowEvidenceError) as caught:
            self.verify(**kwargs)
        self.assertEqual(code, caught.exception.code)
        self.assertEqual({"code", "pointer", "message"}, set(caught.exception.as_dict()["error"]))

    def test_empty_state_is_detached_deterministic_and_offline(self):
        before = copy.deepcopy((self.h.state, self.h.context_data, self.h.authority))
        result = self.verify()
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(result, self.verify())
        self.assertEqual(before, (self.h.state, self.h.context_data, self.h.authority))
        self.assertEqual([], self.h.calls)
        self.assertIsNone(result["candidate_index"])
        self.assertEqual(0, result["functional_correction_count"])
        result["task"]["task_run"] = "detached"
        self.assertNotEqual(result["task"], self.h.state["task"])

    def test_complete_real_candidate_requires_exact_union(self):
        self.h.assembled()
        result = self.verify()
        self.assertEqual(self.h.t, result["approved_test_sha"])
        self.assertEqual(self.h.t, result["executed_test_sha"])
        self.assertEqual(self.h.i, result["implementation_sha"])
        self.assertEqual(0, result["candidate_index"])

    def test_parent_correct_but_omitted_test_tree_is_rejected(self):
        self.h.bad_union = True
        self.h.assembled()
        self.rejects("INVALID_EVIDENCE")
        self.assertEqual([], self.h.calls)

    def test_missing_accepted_receipt_is_not_verified(self):
        self.h.start()
        self.h.context_data["checks"].clear()
        self.rejects("MISSING_EVIDENCE")

    def test_missing_attachment_is_not_verified(self):
        self.h.start()
        raw = self.h.objects[self.h.k["artifact_id"]]["payload"]["authorities"][0]["snapshot"]
        (self.h.root / raw["path"]).unlink()
        self.rejects("MISSING_EVIDENCE")

    def test_authority_shape_precedes_invalid_state(self):
        self.h.authority["extra"] = True
        self.h.state["worker"] = None
        self.rejects("MALFORMED_INPUT")

    def test_existing_invalid_state_error_is_preserved(self):
        self.h.state["worker"] = None
        self.rejects("INVALID_STATE")

    def test_current_comment_must_match_unedited_exact_command(self):
        self.h.assembled()
        endpoint = next(e for e, r in self.h.remote.items() if r["body"]["body"].startswith("/approve"))
        self.h.remote[endpoint]["body"]["body"] += "\n"
        self.rejects("INVALID_EVIDENCE")

    def test_unavailable_transport_is_not_an_approval(self):
        self.h.assembled()
        for remote in self.h.remote.values():
            remote["status"] = 403
        self.rejects("REMOTE_UNAVAILABLE")

    def test_exact_open_proposal_is_not_final_human_approval(self):
        self.h.proposal()
        result = self.verify()
        self.assertEqual("OPEN_SUCCESS_PR", result["terminal_disposition"])
        self.assertEqual(result["candidate_sha"], result["accepted_candidate_sha"])
        self.assertEqual("PASS", result["checks"]["finalization"])
        self.assertEqual(sorted(item["endpoint"] for item in result["remote_evidence"]),
                         [item["endpoint"] for item in result["remote_evidence"]])

    def test_proposal_implementation_only_head_is_rejected(self):
        self.h.proposal()
        self.h.remote[f"/repos/{self.h.task['repository']}/pulls/219"]["body"]["head"]["sha"] = self.h.i
        self.rejects("INVALID_EVIDENCE")

    def test_first_valid_exact_receipt_is_selected_after_corrupt_candidate(self):
        self.h.start()
        bad = copy.deepcopy(self.h.context_data["checks"][0])
        bad["ref"]["artifact_id"] = "aaa-invalid-receipt"
        bad["body"]["artifact_id"] = bad["ref"]["artifact_id"]
        bad["ref"]["path"] = ".agent-state/aaa-invalid-receipt.json"
        bad["ref"]["sha256"] = "0" * 64
        self.h.write(bad["ref"]["path"], canonical(bad["body"]))
        self.h.context_data["checks"].insert(0, bad)
        self.assertEqual("VERIFIED", self.verify()["status"])

    def test_pre_pr_proposal_owns_local_not_remote_finalization(self):
        self.h.assembled()
        report = self.h.consume(self.h.report("PASS"))
        terminal = self.h.terminal(report, True, 0)
        review = self.h.objects[terminal["artifact_id"]]["payload"]["review"]
        self.h.consume(self.h.objects[review["artifact_id"]]["predecessors"][0])
        self.h.consume(review)
        self.h.consume(terminal)
        result = self.verify()
        self.assertEqual("NOT_APPLICABLE", result["checks"]["finalization"])
        self.assertFalse(any("/pulls/" in endpoint for endpoint in self.h.calls))

    def test_corrected_ready_count_can_lead_candidate(self):
        self.h.assembled()
        self.h.corrected(1)
        result = self.verify()
        self.assertEqual(0, result["candidate_index"])
        self.assertEqual(1, result["functional_correction_count"])
        self.assertEqual(self.h.i, result["implementation_sha"])
        for index in (1, 2, 3):
            if index > 1:
                self.h.corrected(index)
            self.h.consume(self.h.candidate(index))
            result = self.verify()
            self.assertEqual(index, result["candidate_index"])
            self.assertEqual(index, result["functional_correction_count"])

    def test_real_mode_type_and_deletion_changes_are_preserved(self):
        for mode in ("100755", "120000", None):
            with self.subTest(mode=mode):
                history = EvidenceHistory(Path(self.temp.name) / ("entry-" + str(mode)))
                self.h = history
                history.change_component(mode)
                history.assembled()
                self.assertEqual("VERIFIED", self.verify()["status"])

    def test_metadata_replacement_keeps_original_human_vote(self):
        self.h.assembled()
        repair, replacement = self.h.metadata()
        self.h.consume(repair)
        self.h.consume(replacement)
        result = self.verify()
        self.assertEqual(self.h.t, result["approved_test_sha"])
        self.assertEqual(0, result["functional_correction_count"])
        self.assertEqual(2, len(result["remote_evidence"]))

    def test_registered_support_can_lead_executed_test_without_new_count(self):
        self.h.assembled()
        failure = self.h.consume(self.h.report("INVALID_RUN"))
        support = self.h.consume(self.h.support(original=failure, commit_count=2))
        result = self.verify()
        target = self.h.objects[support["artifact_id"]]["payload"]["to_test_tip"]["commit"]
        self.assertEqual(target, result["effective_test_sha"])
        self.assertEqual(self.h.t, result["executed_test_sha"])
        self.assertEqual(self.h.t, result["approved_test_sha"])
        self.assertEqual(0, result["functional_correction_count"])
        self.h.consume(self.h.repaired_candidate(support, invalid=failure))
        result = self.verify()
        self.assertEqual(target, result["executed_test_sha"])

    def test_closure_does_not_treat_wrong_present_tip_as_missing(self):
        self.h.assembled()
        body = self.h.context_data["artifacts"][-1]["body"]
        body["payload"]["candidate"]["tree"] = self.h.tip(self.h.g)["tree"]
        self.rejects("INVALID_EVIDENCE")

    def test_closed_authority_and_result_schema_exists(self):
        schema = SCRIPTS.parent / "schemas/workflow-evidence-v1.schema.json"
        self.assertTrue(schema.is_file(), "Versioned evidence schema must exist.")
        value = json.loads(schema.read_text("utf-8"))
        self.assertNotIn("State", value["$defs"])
        self.assertNotIn("Context", value["$defs"])
        self.assertFalse(value["$defs"]["Authority"]["additionalProperties"])
        self.assertFalse(value["$defs"]["Result"]["additionalProperties"])
        self.assertEqual(set(value["$defs"]["Result"]["required"]), set(self.verify()))

    def test_cli_empty_state_is_canonical_and_does_not_start_gh(self):
        values = {"state": self.h.state, "context": self.h.context_data, "authority": self.h.authority}
        args = [sys.executable, str(SCRIPTS / "workflow_evidence.py"), "verify"]
        for key, value in values.items():
            path = self.h.write(".agent-state/" + key + ".json", canonical(value))
            args += ["--" + key, str(path)]
        args += ["--repository-root", str(self.h.root.resolve()), "--github-cli", "nonexistent-gh"]
        result = subprocess.run(args, capture_output=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(canonical(self.verify()), result.stdout)
        for value in ("0", "-1", "nan", "inf"):
            invalid = subprocess.run(args + ["--command-timeout-seconds", value],
                                     capture_output=True, timeout=30)
            self.assertEqual(2, invalid.returncode)
            self.assertEqual(b"", invalid.stdout)
            self.assertEqual("MALFORMED_INPUT", json.loads(invalid.stderr)["error"]["code"])

    def test_cli_usage_and_bad_json_are_safe(self):
        script = str(SCRIPTS / "workflow_evidence.py")
        for args, exit_code in ((["--help"], 0), (["verify"], 2)):
            result = subprocess.run([sys.executable, script, *args], capture_output=True, timeout=15)
            self.assertEqual(exit_code, result.returncode)
            self.assertNotIn(b"Traceback", result.stderr)

    def test_command_timeout_maps_to_safe_public_code(self):
        from workflow_evidence_io import process
        with mock.patch("workflow_evidence_io.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(["git"], 0.25)):
            with self.assertRaises(self.api.WorkflowEvidenceError) as error:
                process(["git"], timeout=0.25)
        self.assertEqual("COMMAND_TIMEOUT", error.exception.code)

    def test_gh_adapter_is_get_only_and_classifies_missing_provider(self):
        from workflow_evidence_remote import github_cli
        from workflow_evidence_io import WorkflowEvidenceError
        with mock.patch("workflow_evidence_remote.process",
                        side_effect=WorkflowEvidenceError("EXECUTION_ERROR")):
            with self.assertRaises(WorkflowEvidenceError) as error:
                github_cli("absent", 7)("/repos/sample/repository/issues/comments/42")
        self.assertEqual("REMOTE_UNAVAILABLE", error.exception.code)
        response = subprocess.CompletedProcess([], 0, b"HTTP/2.0 200 OK\r\nX-Test: yes\r\n\r\n{}\n", b"")
        with mock.patch("workflow_evidence_remote.process", return_value=response) as command:
            self.assertEqual({"status": 200, "body": {}}, github_cli("gh", 7)("/repos/a/b/pulls/31"))
        argv = command.call_args.args[0]
        self.assertEqual(["gh", "api", "--method", "GET", "--hostname", "github.com",
                          "--include", "/repos/a/b/pulls/31"], argv)
        self.assertEqual(7, command.call_args.kwargs["timeout"])

    def test_verification_runs_no_git_writers_and_preserves_repository_bytes(self):
        self.h.assembled()
        before = {str(p.relative_to(self.h.root)): p.read_bytes()
                  for p in self.h.root.rglob("*") if p.is_file()}
        actual_run = subprocess.run
        argv = []
        def observed(args, **kwargs):
            argv.append(args)
            return actual_run(args, **kwargs)
        with mock.patch("workflow_evidence_io.subprocess.run", side_effect=observed):
            self.verify()
        self.assertEqual(before, {str(p.relative_to(self.h.root)): p.read_bytes()
                                for p in self.h.root.rglob("*") if p.is_file()})
        forbidden = {"merge", "checkout", "commit", "commit-tree", "read-tree", "update-index",
                     "write-tree", "hash-object", "fetch", "push"}
        self.assertFalse(any(args[args.index("-C") + 2] in forbidden for args in argv))

    def test_merged_proof_accepts_exact_fast_forward_and_two_parent_tree(self):
        for fast_forward in (False, True):
            with self.subTest(fast_forward=fast_forward):
                self.h = EvidenceHistory(Path(self.temp.name) / ("merged-" + str(fast_forward)))
                self.h.merged(fast_forward=fast_forward)
                # PR base.sha is mutable after merge; real merge ancestry carries G.
                self.h.remote[f"/repos/{self.h.task['repository']}/pulls/219"]["body"]["base"]["sha"] = "a" * 40
                result = self.verify()
                self.assertEqual("MERGED", result["terminal_disposition"])
                self.assertEqual(result["candidate_sha"], result["accepted_candidate_sha"])

    def test_merged_proof_rejects_squash_tree_even_when_remote_matches(self):
        self.h.merged(squash=True)
        self.rejects("INVALID_EVIDENCE")

    def test_remote_required_identity_and_top_level_fields(self):
        self.h.assembled()
        endpoint = next(e for e, r in self.h.remote.items() if r["body"]["body"].startswith("/approve"))
        original = copy.deepcopy(self.h.remote[endpoint])
        changes = [
            {"user": {"login": "owner-example", "type": "Bot"}},
            {"in_reply_to_id": 39}, {"deleted": True}, {"issue_url": "https://api.github.com/repos/elsewhere/project/issues/417"},
            {"id": True}, {"updated_at": "2026-09-09T01:00:00Z"}]
        for fields in changes:
            with self.subTest(fields=fields):
                self.h.remote[endpoint] = copy.deepcopy(original)
                self.h.remote[endpoint]["body"].update(fields)
                self.rejects("INVALID_EVIDENCE")
        self.h.remote[endpoint] = {"status": 404, "body": {}}
        self.rejects("MISSING_EVIDENCE")

    def test_manual_command_is_preserved_but_not_remotely_verified(self):
        self.h.start()
        for ref in (self.h.ir, self.h.tr):
            self.h.consume(ref)
        body = self.h.objects[self.h.human["artifact_id"]]
        body["payload"]["source"]["kind"] = "human-command"
        self.h.human = self.h.store(body)
        self.h.consume(self.h.human)
        self.rejects("AUTHORITY_UNVERIFIABLE")

    def test_all_implementation_findings_require_public_mapping(self):
        self.h.assembled()
        ref = self.h.report("IMPLEMENTATION_FAIL")
        body = self.h.objects[ref["artifact_id"]]
        extra = copy.deepcopy(body["payload"]["findings"][0])
        extra["id"] = "another-independent-finding"
        body["payload"]["findings"].append(extra)
        ref = self.h.store(body)
        self.h.consume(ref)
        self.h.consume(self.h.correction(1, ref))
        self.rejects("INVALID_EVIDENCE")
        self.assertEqual([], self.h.calls)

    def test_exact_exclusions_do_not_reject_ordinary_reference_names(self):
        from workflow_evidence_io import EvidenceGraph
        graph = EvidenceGraph(self.h.state, self.h.context_data, self.h.root.resolve(), 15)
        graph.attachments[("artifacts/disclosure.json", "a" * 64, "disclosure-review")] = b"evidence"
        for path in (".agent-state/x.json", ".agent-state", "tests/.tmp/y.py",
                     "tests/.tmp", "agent-discipline/agent-lessons-learned.md", "artifacts/disclosure.json"):
            self.assertTrue(graph.temporary_content(path), path)
        for path in ("tests/fixture/reference.json", "reference-overlay/module.py",
                     "agent-discipline/skills/agent-workflow/references/evidence.md"):
            self.assertFalse(graph.temporary_content(path), path)

    def test_path_object_is_an_explicit_absolute_repository_path(self):
        result = self.api.verify_evidence(self.h.state, context=self.h.context_data,
            repository_root=self.h.root.resolve(), authority=self.h.authority)
        self.assertEqual("VERIFIED", result["status"])

    def test_noncallable_transport_is_malformed_even_before_remote_stage(self):
        with self.assertRaises(self.api.WorkflowEvidenceError) as error:
            self.api.verify_evidence(self.h.state, context=self.h.context_data,
                repository_root=str(self.h.root.resolve()), authority=self.h.authority, github_get=27)
        self.assertEqual("MALFORMED_INPUT", error.exception.code)

    def test_authority_rest_extra_json_fields_do_not_change_required_binding(self):
        self.h.start()
        self.h.consume(self.h.ir)
        self.h.consume(self.h.tr)
        body = self.h.objects[self.h.human["artifact_id"]]
        endpoint = next(e for e, r in self.h.remote.items() if r["body"]["body"].startswith("/approve"))
        raw = self.h.remote[endpoint]["body"]
        raw["extended_json"] = {"ratio": 0.5, "nested": [None, True, "context"]}
        body["payload"]["source"]["raw"] = self.h.evidence("authority", raw)
        self.h.human = self.h.store(body)
        self.h.consume(self.h.human)
        self.assertEqual("VERIFIED", self.verify()["status"])

    def test_existing_disjoint_git_root_is_invalid_not_missing(self):
        tree = self.h.tip(self.h.i)["tree"]
        self.h.i = self.h.git("commit-tree", tree, "-m", "independent real root")
        self.h.ir = self.h.implementation(0, self.h.i, None, self.h.wlaunch)
        self.h.assembled()
        self.rejects("INVALID_EVIDENCE")

    def test_timeout_larger_than_float_range_is_safe_malformed_input(self):
        self.rejects("MALFORMED_INPUT", command_timeout_seconds=10 ** 1000)

    def test_equivalent_human_delivery_is_not_a_second_vote(self):
        self.h.assembled()
        repair, replacement = self.h.metadata_for(self.h.human)
        self.h.consume(repair)
        self.h.consume(replacement)
        result = self.verify()
        self.assertEqual(2, len(result["remote_evidence"]))

    def test_equivalent_reviewer_launch_is_not_a_second_review(self):
        self.h.proposal()
        launch = self.h.state["review"]["launch"]
        repair, replacement = self.h.metadata_for(launch)
        self.h.consume(repair)
        self.h.consume(replacement)
        self.assertEqual("VERIFIED", self.verify()["status"])

    def test_valid_receipt_after_wrong_receipt_reference_identity_is_used(self):
        self.h.start()
        bad = copy.deepcopy(self.h.context_data["checks"][0])
        bad["ref"]["artifact_id"] = "aaa-wrong-identity"
        self.h.context_data["checks"].insert(0, bad)
        self.assertEqual("VERIFIED", self.verify()["status"])

    def test_non_utf8_commit_metadata_preserves_structural_identity(self):
        tree = self.h.tip(self.h.i)["tree"]
        raw = (f"tree {tree}\nparent {self.h.g}\n".encode("ascii")
               + b"author Andr\xe9 <author@example.invalid> 1700000000 +0000\n"
               + b"committer Ren\xe9 <committer@example.invalid> 1700000001 +0000\n"
               + b"encoding ISO-8859-1\n\nArbitrary non-UTF-8 metadata: \xff\n")
        self.h.i = self.h.git("hash-object", "-t", "commit", "-w", "--stdin", data=raw)
        self.h.ir = self.h.implementation(0, self.h.i, None, self.h.wlaunch)
        self.h.assembled()
        result = self.verify()
        self.assertEqual("VERIFIED", result["status"])
        self.assertEqual(self.h.i, result["implementation_sha"])

    def test_failed_recursive_receipt_attempt_cannot_poison_later_valid_receipt(self):
        self.h.assembled()
        # This unconsumed recursive predecessor loads an attachment and a Tip,
        # then fails at its missing manifest. None belong to the selected proof.
        poison = copy.deepcopy(self.h.objects[self.h.ir["artifact_id"]])
        poison["artifact_id"] = "unused-recursive-implementation"
        poison["payload"]["implementation_tip"]["commit"] = "d" * 40
        poison["payload"]["manifest"]["path"] = ".agent-state/missing-attempt-manifest.json"
        run = poison["payload"]["generality"][0]
        raw = (self.h.root / run["result"]["path"]).read_bytes()
        run["result"]["path"] = "src/component.py"
        self.h.write(run["result"]["path"], raw)
        poison_ref = self.h.store(poison)
        self.h.sync()
        bad = copy.deepcopy(self.h.context_data["checks"][0]["body"])
        bad["artifact_id"] = "aaa-recursive-invalid-receipt"
        bad["predecessors"].append(poison_ref)
        bad_ref = self.h.ref(bad)
        self.h.write(bad_ref["path"], canonical(bad))
        self.h.context_data["checks"].insert(0, {"ref": bad_ref, "body": bad})
        self.assertEqual("VERIFIED", self.verify()["status"])

    def test_h1_tester_confidential_receipt_is_not_worker_filtered(self):
        from structured_handoff_refs import ReferenceGraph
        self.h.start()
        ref = self.h.checked(self.h.tlaunch)
        graph = ReferenceGraph(self.h.context(self.h.tlaunch, [ref]), "consumer-local")
        value = graph.artifact(ref)
        self.assertEqual("tester", value["consumer_role"])
        self.assertEqual("tester-confidential", value["visibility"])

    def test_h1_tester_confidential_repair_passes_local_guard(self):
        self.h.start(ready=True)
        repair, _ = self.h.metadata()
        central_path = ".agent-state/h1-tester-central.json"
        code, result = self.h.validate(repair, result_name=central_path)
        self.assertEqual(0, code, result)
        central = {"path": central_path, "sha256": digest(result)}
        code, result = self.h.validate(repair, view="consumer-local", central=central)
        self.assertEqual(0, code, result)
        self.assertEqual("CHECKED", result["status"])

    def test_h1_worker_unknown_private_reference_rejects_before_open(self):
        from structured_handoff_refs import ReferenceGraph
        from structured_handoff_schema import ProtocolError
        for kind in ("guard-result", "delivery-repair", "tester-confidential-report"):
            with self.subTest(kind=kind):
                graph = ReferenceGraph(self.h.context(self.h.wlaunch), "consumer-local")
                ref = {"kind": kind, "artifact_id": "unavailable-private",
                       "path": ".agent-state/never-open.json", "sha256": "a" * 64}
                with self.assertRaises(ProtocolError) as caught:
                    graph.artifact(ref)
                self.assertEqual("PRIVATE_REFERENCE", caught.exception.rule_id)

    def test_h1_worker_keeps_public_receipt_predecessor_exception(self):
        from structured_handoff_refs import ReferenceGraph
        self.h.start(ready=True)
        ref = self.h.checked(self.h.ir)
        graph = ReferenceGraph(self.h.context(self.h.wlaunch, [ref]), "consumer-local")
        value = graph.artifact(ref)
        self.assertEqual("public-task", value["visibility"])
        self.assertEqual("orchestrator", value["consumer_role"])

    def test_h1_worker_listed_private_receipt_stays_rejected(self):
        from structured_handoff_refs import ReferenceGraph
        from structured_handoff_schema import ProtocolError
        self.h.start()
        ref = self.h.checked(self.h.tlaunch)
        graph = ReferenceGraph(self.h.context(self.h.wlaunch, [ref]), "consumer-local")
        with self.assertRaises(ProtocolError) as caught:
            graph.artifact(ref)
        self.assertEqual("PRIVATE_REFERENCE", caught.exception.rule_id)

    def test_h1_worker_public_repair_still_requires_worker_recipient(self):
        from structured_handoff_refs import ReferenceGraph
        from structured_handoff_schema import ProtocolError
        self.h.start(ready=True)
        repair, _ = self.h.metadata()
        value = copy.deepcopy(self.h.objects[repair["artifact_id"]])
        value["visibility"] = "public-task"
        ref = self.h.store(value)
        graph = ReferenceGraph(self.h.context(self.h.wlaunch, [ref]), "consumer-local")
        graph.verify_environment()
        with self.assertRaises(ProtocolError) as caught:
            graph.artifact(ref)
        self.assertEqual("PRIVATE_REFERENCE", caught.exception.rule_id)


if __name__ == "__main__":
    unittest.main()
