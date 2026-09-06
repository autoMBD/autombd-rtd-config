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
# File:        structured_handoff_rules.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Declarative protocol local-edge and evidence invariants.
# =================================================================================

from structured_handoff_schema import require
from structured_handoff_refs import git


def unique(values, rule="DUPLICATE_ID"):
    require(len(values) == len(set(values)), rule)


class LocalRules:
    def __init__(self, graph):
        self.g = graph
        self.checked = set()

    def check(self, artifact):
        aid = artifact["artifact_id"]
        if aid in self.checked:
            return
        self.checked.add(aid)
        kind = artifact["artifact_kind"]
        if kind == "guard-result":
            self.guard_result(artifact)
            return
        original = artifact["payload"]["original"] if kind == "delivery-repair" else (artifact["replaces"]["original"] if artifact["replaces"] else None)
        for ref in artifact["predecessors"]:
            if ref != original:
                self.check(self.g.artifacts[ref["artifact_id"]])
        require(len({r["artifact_id"] for r in artifact["predecessors"]}) == len(artifact["predecessors"]), "DUPLICATE_PREDECESSOR")
        for required in self.g.registry["checkpoints"][kind]["required_predecessors"]:
            require(bool(self.g.direct(artifact, required)), "PREDECESSOR_REQUIRED")
        self.references(artifact)
        getattr(self, kind.replace("-", "_"))(artifact)
        if artifact["replaces"]:
            self.replacement(artifact)

    def references(self, artifact):
        k = self.g.contract(artifact)["payload"]
        domains = {name: {x["id"] for x in k[section]} for name, section in
                   [("requirement", "requirements"), ("authority", "authorities"),
                    ("interface", "interfaces"), ("decision_rule", "decision_rules")]}
        def visit(value):
            if isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for key, child in value.items():
                    domain = None
                    if key in {"requirement_id", "requirement_ids", "behavior_requirement_ids",
                               "affected_requirement_ids", "resume_requirement_ids", "public_obligation_ids",
                               "expected_requirement_ids", "required_outcome_requirement_ids"}:
                        domain = "requirement"
                    elif key in {"authority_ids", "changed_authority_ids", "public_reproduction_authority_id"}:
                        domain = "authority"
                    elif key == "interface_ids":
                        domain = "interface"
                    elif key == "decision_rule_id":
                        domain = "decision_rule"
                    if domain and child is not None:
                        values = child if isinstance(child, list) else [child]
                        unique(values)
                        require(set(values) <= domains[domain], "UNRESOLVED_PUBLIC_ID")
                    visit(child)
        visit(artifact["payload"])
        visit(artifact["unresolved"])

    def task_contract(self, a):
        p = a["payload"]
        all_ids = [item["id"] for group in ("authorities", "requirements", "interfaces", "decision_rules", "acceptance") for item in p[group]]
        unique(all_ids)
        priorities = [rule["priority"] for rule in p["decision_rules"]]
        require(priorities == sorted(set(priorities)), "DECISION_PRIORITY")
        require(all(x["snapshot"]["evidence_type"] == "authority" for x in p["authorities"]), "AUTHORITY_TYPE")
        revision = p["revision"]
        if revision["number"] == 0:
            require(revision["predecessor"] is None and revision["authority"] is None and not a["predecessors"], "INITIAL_CONTRACT")
        else:
            require(revision["predecessor"] is not None and revision["authority"] is not None, "REVISION_AUTHORITY")
            old = self.g.artifacts[revision["predecessor"]["artifact_id"]]
            require(old["artifact_kind"] == "task-contract" and old["payload"]["revision"]["number"] + 1 == revision["number"], "REVISION_SEQUENCE")
            require(revision["predecessor"] in a["predecessors"], "REVISION_PREDECESSOR")
            require(revision["authority"]["evidence_type"] == "authority", "REVISION_AUTHORITY")

    def launch(self, a):
        p = a["payload"]
        k = self.g.one(a, "task-contract")
        kr = a["task_contract"]
        require(self.g.refs[k["artifact_id"]]["sha256"] == kr["sha256"], "LAUNCH_CONTRACT")
        if p["mode"] == "INITIAL":
            require(p["previous_launch"] is None and not p["revision_ack_required"], "LAUNCH_MODE")
        else:
            require(p["previous_launch"] is not None and p["revision_ack_required"], "LAUNCH_MODE")
            old = self.g.artifacts[p["previous_launch"]["artifact_id"]]
            require(old["artifact_kind"] == a["artifact_kind"] and old["payload"]["lane"] == p["lane"], "LAUNCH_LINEAGE")
            require(p["previous_launch"] in a["predecessors"] and old["task_contract"]["revision"] < kr["revision"], "LAUNCH_REVISION")
        require(set(p["requirement_ids"]) == {r["id"] for r in k["payload"]["requirements"]}, "LAUNCH_REQUIREMENTS")

    def test_launch(self, a):
        self.launch(a)

    def worker_launch(self, a):
        self.launch(a)
        for item in a["payload"]["salvage"]:
            self.g.verify_commit(item["source_commit"])
            require(item["disclosure_review"]["evidence_type"] == "disclosure-review", "SALVAGE_DISCLOSURE")

    def dispatch(self, a, launch):
        expected = launch["payload"]["dispatch_id"]
        if a["replaces"] and self.g.direct(a, "delivery-repair"):
            expected = self.g.one(a, "delivery-repair")["payload"]["dispatch_id"]
        require(a["payload"]["dispatch_id"] == expected, "DISPATCH_IDENTITY")
        if "lane" in a["payload"]:
            require(a["payload"]["lane"] == launch["payload"]["lane"], "LANE_IDENTITY")
        self.g.same_k(a, launch)

    def acknowledgement(self, a, launch):
        p = a["payload"]
        ack = p["revision_ack"]
        if p["status"] == "K_ACK":
            require(ack is not None and launch["payload"].get("revision_ack_required"), "REVISION_ACK")
            require(ack["new_contract"] == a["task_contract"] and ack["verified_sha256"] == a["task_contract"]["sha256"], "REVISION_ACK_DIGEST")
            require(ack["old_contract"]["revision"] < ack["new_contract"]["revision"], "REVISION_ACK_ORDER")
            self.g.verify_commit(ack["current_tip"])
        else:
            require(ack is None, "REVISION_ACK_STATUS")
            if p["status"] == "READY" and launch["payload"].get("revision_ack_required"):
                if self.g.view == "consumer-local":
                    require(self.g.central_verified, "CENTRAL_CHECK_REQUIRED")
                    return
                for role_kind in ("test-gate-report", "implementation-report"):
                    matches = [x for x in self.g.artifacts.values() if x["artifact_kind"] == role_kind
                               and x["payload"]["status"] == "K_ACK" and x["task_contract"] == a["task_contract"]]
                    require(len(matches) == 1, "BOTH_REVISION_ACKS")
                    require(matches[0]["artifact_id"] in self.g.private_context_ids or any(r["artifact_id"] == matches[0]["artifact_id"] for r in a["predecessors"]), "ACK_EXACT_REFERENCE")
                    self.check(matches[0])

    def ready(self, a, tip_key, runs_key):
        p = a["payload"]
        if p["status"] != "READY":
            return False
        require(p[tip_key] is not None and p["manifest"] is not None and p[runs_key], "READY_EVIDENCE")
        require(not any(o["category"] in {"CONTRACT_AMBIGUITY", "DEPENDENCY_UNAVAILABLE"} for o in a["unresolved"]), "READY_UNRESOLVED")
        requirements = {r["id"] for r in self.g.contract(a)["payload"]["requirements"]}
        covered = [x["requirement_id"] for x in p["requirement_coverage"]]
        unique(covered)
        require(set(covered) == requirements, "READY_COVERAGE")
        self.manifest(p["manifest"], p[tip_key]["commit"], requirements)
        for run in p[runs_key]:
            self.run(run)
        return True

    def manifest(self, ref, commit, requirements):
        require(ref["evidence_type"] == "manifest", "MANIFEST_TYPE")
        m = self.g.evidence(ref)
        gov = self.g.context["governor"]
        require(m["contract_version"] == self.g.workflow_version, "MANIFEST_VERSION")
        require(m["base_sha"] == gov["commit"] and m["contract_blob_sha"] == gov["workflow_contract_blob"] and m["lane_sha"] == commit, "MANIFEST_IDENTITY")
        unique(m["requirement_ids"])
        require(set(m["requirement_ids"]) == requirements, "MANIFEST_COVERAGE")

    def run(self, run):
        require(run["result"]["evidence_type"] == "command-result", "RUN_RESULT_TYPE")
        data = self.g.evidence(run["result"])
        for key in ("argv", "cwd", "exit_code", "outcome", "environment_id"):
            require(run[key] == data[key], "RUN_RESULT_IDENTITY")
        require(run["outcome"] != "PASS" or run["exit_code"] == 0, "RUN_OUTCOME")
        require(run["outcome"] != "TIMED_OUT" or run["exit_code"] == 124, "RUN_OUTCOME")

    def impact(self, a, ref):
        require(ref["evidence_type"] == "impact-set", "IMPACT_TYPE")
        impact = self.g.evidence(ref)
        require(impact["task"] == a["task"] and impact["task_contract"] == a["task_contract"], "IMPACT_IDENTITY")
        unique([x["id"] for x in impact["selected_checks"] + impact["excluded_checks"]])
        requirements = {r["id"] for r in self.g.contract(a)["payload"]["requirements"]}
        require({r for x in impact["selected_checks"] for r in x["requirement_ids"]} == requirements, "IMPACT_REQUIREMENTS")
        unique([x["id"] for x in impact["prevalidation_obligations"]])
        for obligation in impact["prevalidation_obligations"]:
            require((obligation["reason"] is not None) == (obligation["mode"] == "NOT_APPLICABLE"), "PREVALIDATION_REASON")
        return impact

    def test_gate_report(self, a):
        launch = self.g.one(a, "test-launch")
        self.dispatch(a, launch)
        self.acknowledgement(a, launch)
        if not self.ready(a, "test_tip", "prevalidation"):
            return
        p = a["payload"]
        require(p["impact_set"] is not None, "READY_IMPACT")
        impact = self.impact(a, p["impact_set"])
        obligations = impact["prevalidation_obligations"]
        require({"FULL_CHAIN", "KNOWN_GOOD", "KNOWN_BAD"} <= {x["mode"] for x in obligations}, "PREVALIDATION_CHAIN")
        require("RED" in {x["mode"] for x in obligations} or any(x["mode"] == "NOT_APPLICABLE" for x in obligations), "PREVALIDATION_RED")
        runs = {r["purpose"]: r for r in p["prevalidation"]}
        unique([r["purpose"] for r in p["prevalidation"]])
        for obligation in obligations:
            if obligation["mode"] == "NOT_APPLICABLE":
                require(obligation["id"] not in runs, "NOT_APPLICABLE_EXECUTION")
                continue
            require(obligation["id"] in runs, "PREVALIDATION_MISSING")
            expected = "FAIL" if obligation["mode"] in {"RED", "KNOWN_BAD"} else "PASS"
            require(runs[obligation["id"]]["outcome"] == expected, "PREVALIDATION_OUTCOME")
        expected = {(x["family"], disposition) for group, disposition in [("selected_checks", "SELECTED"), ("excluded_checks", "EXCLUDED")] for x in impact[group]}
        require({(x["family"], x["disposition"]) for x in p["impact_selection"]} == expected, "IMPACT_SELECTION")

    def implementation_report(self, a):
        p = a["payload"]
        kind = "worker-launch" if p["implementation_index"] == 0 else "worker-correction-envelope"
        launch = self.g.one(a, kind)
        self.dispatch(a, launch)
        if kind == "worker-launch":
            self.acknowledgement(a, launch)
            require(p["previous_implementation"] is None, "INITIAL_IMPLEMENTATION")
        else:
            require(p["implementation_index"] == launch["payload"]["correction_index"] and
                    p["previous_implementation"] == launch["payload"]["previous_implementation"], "IMPLEMENTATION_SEQUENCE")
        if self.ready(a, "implementation_tip", "generality"):
            require(all(x["outcome"] == "PASS" for x in p["generality"]), "GENERALITY_PASS")
            if p["implementation_index"]:
                self.g.strict_ancestor(p["previous_implementation"], p["implementation_tip"]["commit"])
            require({x["path"] for x in p["changed_paths"]} == self.g.changed_paths(p["implementation_tip"]["commit"]), "IMPLEMENTATION_CHANGED_PATHS")

    def human_decision(self, a):
        p = a["payload"]
        require(a["visibility"] == ("tester-confidential" if p["gate"] == "TEST" else "terminal-review"), "DECISION_VISIBILITY")
        if p["decision"] == "APPROVE":
            require(p["subject_sha"] is not None and p["source"]["created_at"] == p["source"]["updated_at"] and not p["source"]["deleted"], "APPROVAL_IMMUTABLE")
        if p["decision"] == "REQUEST_CHANGES":
            require(p["reason"] is not None, "DECISION_REASON")
        if p["gate"] == "TEST":
            if p["subject_sha"] is not None:
                report = self.g.one(a, "test-gate-report", lambda x: x["payload"]["status"] == "READY")
                self.g.same_k(a, report)
                require(p["subject_sha"] == report["payload"]["test_tip"]["commit"], "APPROVAL_SUBJECT")
        elif p["decision"] == "APPROVE":
            terminal = self.g.one(a, "terminal-record")
            require(terminal["payload"]["result"] == "SUCCESS" and p["subject_sha"] == terminal["payload"]["accepted_candidate"], "FINAL_SUBJECT")

    def candidate_test_envelope(self, a):
        p = a["payload"]
        index = p["candidate_index"]
        require(index == p["correction_count"], "CANDIDATE_COUNT")
        require(p["candidate"]["parents"] == [p["test_tip"]["commit"], p["implementation_tip"]["commit"]], "CANDIDATE_PARENTS")
        tr = self.g.one(a, "test-gate-report", lambda x: x["payload"]["status"] == "READY")
        ir = self.g.one(a, "implementation-report", lambda x: x["payload"]["status"] == "READY")
        approval = self.g.one(a, "human-decision", lambda x: x["payload"]["gate"] == "TEST" and x["payload"]["decision"] == "APPROVE")
        for predecessor in (tr, ir, approval):
            self.g.same_k(a, predecessor)
        require(p["test_tip"] == tr["payload"]["test_tip"] and p["test_manifest"] == tr["payload"]["manifest"] and p["impact_set"] == tr["payload"]["impact_set"], "FROZEN_TEST")
        require(approval["payload"]["subject_sha"] == p["test_tip"]["commit"], "FROZEN_APPROVAL")
        require(self.g.one(approval, "test-gate-report")["artifact_id"] == tr["artifact_id"], "FROZEN_TEST_REPORT")
        require(p["implementation_tip"] == ir["payload"]["implementation_tip"] and p["implementation_manifest"] == ir["payload"]["manifest"] and index == ir["payload"]["implementation_index"], "CANDIDATE_IMPLEMENTATION")
        if p["rerun_of"]:
            invalid = self.g.artifacts[p["rerun_of"]["artifact_id"]]
            require(p["rerun_of"] in a["predecessors"] and invalid["artifact_kind"] == "tester-confidential-report" and invalid["payload"]["outcome"] == "INVALID_RUN", "RERUN_INVALID")
            old = self.g.one(invalid, "candidate-test-envelope")
            require(self.g.refs[old["artifact_id"]] in a["predecessors"], "RERUN_PREDECESSOR")
            fields = ("candidate_index", "correction_count", "candidate", "test_tip", "implementation_tip", "test_manifest", "implementation_manifest", "impact_set", "coverage_join", "previous_candidate")
            require(all(p[f] == old["payload"][f] for f in fields), "RERUN_IDENTITY")
            require(p["execution_id"] != old["payload"]["execution_id"], "RERUN_EXECUTION")
        if index == 0:
            require(p["previous_candidate"] is None, "INITIAL_CANDIDATE")
        else:
            require(p["previous_candidate"] is not None and p["previous_candidate"] in a["predecessors"], "PREVIOUS_CANDIDATE")
            previous = self.g.artifacts[p["previous_candidate"]["artifact_id"]]
            require(previous["artifact_kind"] == "candidate-test-envelope" and previous["payload"]["candidate_index"] + 1 == index, "CANDIDATE_SEQUENCE")
            for key in ("test_tip", "test_manifest", "impact_set"):
                require(p[key] == previous["payload"][key], "FROZEN_TEST")
            self.g.same_k(a, previous)
        self.coverage_join(a)

    def coverage_join(self, a):
        p = a["payload"]
        require(p["coverage_join"]["evidence_type"] == "coverage-join", "COVERAGE_JOIN_TYPE")
        join = self.g.evidence(p["coverage_join"])
        require(join["test_commit"] == p["test_tip"]["commit"] and join["implementation_commit"] == p["implementation_tip"]["commit"] and join["impact_set_sha256"] == p["impact_set"]["sha256"], "COVERAGE_JOIN_IDENTITY")
        actual_test = self.g.changed_paths(join["test_commit"])
        actual_impl = self.g.changed_paths(join["implementation_commit"])
        require(not (actual_test & actual_impl), "OWNERSHIP_OVERLAP")
        unique([x["path"] for x in join["changed_paths"]], "COVERAGE_DUPLICATE_PATH")
        for owner, actual in (("TEST", actual_test), ("IMPLEMENTATION", actual_impl)):
            require({x["path"] for x in join["changed_paths"] if x["owner"] == owner} == actual, "COVERAGE_CHANGED_PATHS")
        impact = self.impact(a, p["impact_set"])
        checks = {x["id"]: x for x in impact["selected_checks"]}
        requirements = {x["id"] for x in self.g.contract(a)["payload"]["requirements"]}
        edges = {(x["from"], x["to"]) for x in impact["public_dependency_edges"]}
        unique(list(edges), "DEPENDENCY_EDGE")
        for change in join["changed_paths"]:
            require(set(change["requirement_ids"]) <= requirements and set(change["selected_check_ids"]) <= checks.keys(), "COVERAGE_REFERENCE")
            for check_id in change["selected_check_ids"]:
                check = checks[check_id]
                require(change["path"] in check["covered_paths"] and set(change["requirement_ids"]) <= set(check["requirement_ids"]), "COVERAGE_JOIN_MISSING")
                for target in set(check["covered_paths"]) & actual_test:
                    if change["owner"] == "IMPLEMENTATION":
                        require((change["path"], target) in edges, "PUBLIC_DEPENDENCY_MISSING")

    def tester_confidential_report(self, a):
        p = a["payload"]
        launch = self.g.one(a, "candidate-test-envelope")
        self.dispatch(a, launch)
        for report_key, launch_key in (("candidate_index", "candidate_index"), ("execution_id", "execution_id")):
            require(p[report_key] == launch["payload"][launch_key], "EXECUTION_IDENTITY")
        require(p["candidate_sha"] == launch["payload"]["candidate"]["commit"], "EXECUTION_CANDIDATE")
        for run in p["execution"]:
            self.run(run)
        impact = self.g.evidence(launch["payload"]["impact_set"])
        selected = {x["id"]: x for x in impact["selected_checks"]}
        executed = [run["purpose"] for run in p["execution"]]
        unique(executed, "EXECUTION_DUPLICATE")
        require(set(executed) <= selected.keys(), "EXECUTION_SCOPE")
        for run in p["execution"]:
            require(run["argv"] == selected[run["purpose"]]["argv"], "EXECUTION_ARGV")
        if p["outcome"] in {"PASS", "IMPLEMENTATION_FAIL"}:
            require(p["execution"] and all(r["outcome"] in {"PASS", "FAIL"} for r in p["execution"]), "EXECUTION_INCOMPLETE")
            require(set(executed) == selected.keys(), "EXECUTION_SCOPE")
        if p["outcome"] == "PASS":
            require(not p["findings"] and all(r["outcome"] == "PASS" for r in p["execution"]), "PASS_FINDINGS")
        if p["outcome"] == "IMPLEMENTATION_FAIL":
            require(p["findings"] and any(r["outcome"] == "FAIL" for r in p["execution"]), "FAIL_FINDINGS")
            require(all(f["responsibility"] == "IMPLEMENTATION" and f["production_location"] is not None and f["exclusion_evidence"] for f in p["findings"]), "FAIL_DIAGNOSIS")
        unique([x["id"] for x in p["findings"]])

    def worker_correction_envelope(self, a):
        p = a["payload"]
        prior = self.g.one(a, "implementation-report", lambda x: x["payload"]["status"] == "READY")
        self.g.same_k(a, prior)
        require(prior["payload"]["implementation_index"] + 1 == p["correction_index"] and prior["payload"]["implementation_tip"]["commit"] == p["previous_implementation"], "CORRECTION_SEQUENCE")
        require(prior["payload"]["lane"] == p["lane"], "CORRECTION_LANE")
        disclosure = p["disclosure_review"]
        diagnoses = {d["id"] for d in p["diagnoses"]}
        unique([d["id"] for d in p["diagnoses"]])
        require({m["public_diagnosis_id"] for m in disclosure["mapping"]} == diagnoses, "DISCLOSURE_DIAGNOSES")
        unique([m["public_diagnosis_id"] for m in disclosure["mapping"]])
        if self.g.view == "consumer-local":
            return
        sid = disclosure["source_report_id"]
        require(sid in self.g.private_context_ids and sid in self.g.artifacts, "DISCLOSURE_SOURCE")
        source = self.g.artifacts[sid]
        require(source["artifact_kind"] == "tester-confidential-report" and self.g.refs[sid]["sha256"] == disclosure["source_report_sha256"], "DISCLOSURE_DIGEST")
        self.check(source)
        sp = source["payload"]
        require(sp["outcome"] == "IMPLEMENTATION_FAIL" and sp["candidate_index"] + 1 == p["correction_index"], "CORRECTION_VALID_FAIL")
        candidate = self.g.one(source, "candidate-test-envelope")
        require(candidate["payload"]["implementation_tip"]["commit"] == p["previous_implementation"], "CORRECTION_SOURCE")
        findings = {f["id"]: f for f in sp["findings"]}
        require(all(m["confidential_finding_id"] in findings for m in disclosure["mapping"]), "DISCLOSURE_MAPPING")
        for mapping in disclosure["mapping"]:
            public = next(d for d in p["diagnoses"] if d["id"] == mapping["public_diagnosis_id"])
            confidential = findings[mapping["confidential_finding_id"]]
            require(public["requirement_id"] == confidential["requirement_id"] and public["production_location"] == confidential["production_location"], "DISCLOSURE_PUBLIC_IDENTITY")

    def reviewer_launch(self, a):
        p = a["payload"]
        sources = [self.g.artifacts[r["artifact_id"]] for r in p["source_reports"]]
        require(sources and all(r in a["predecessors"] for r in p["source_reports"]), "TERMINAL_SOURCES")
        reason = p["terminal_reason"]
        if reason in {"TESTER_PASS", "CORRECTIONS_EXHAUSTED"}:
            outcome = "PASS" if reason == "TESTER_PASS" else "IMPLEMENTATION_FAIL"
            matches = [s for s in sources if s["artifact_kind"] == "tester-confidential-report" and s["payload"]["outcome"] == outcome]
            require(len(matches) == 1, "TERMINAL_REASON")
            source = matches[0]
            require(reason != "CORRECTIONS_EXHAUSTED" or source["payload"]["candidate_index"] == 3, "CORRECTIONS_NOT_EXHAUSTED")
            candidate = self.g.one(source, "candidate-test-envelope")
            require(p["candidate"] == candidate["payload"]["candidate"] and p["last_implementation"] == candidate["payload"]["implementation_tip"]["commit"], "REVIEW_CANDIDATE")
        elif reason == "HUMAN_STOP":
            decisions = [s for s in sources if s["artifact_kind"] == "human-decision" and s["payload"]["decision"] == "STOP"]
            require(len(decisions) == 1, "TERMINAL_REASON")
            candidate = self.review_candidate(a)
            subject = candidate["payload"]["candidate"]["commit"] if candidate else None
            require(decisions[0]["payload"]["subject_sha"] == subject, "STOP_SUBJECT")
            self.stop_implementation(a, candidate)
        else:
            require(any(s["artifact_kind"] == "tester-confidential-report" and s["payload"]["outcome"] == reason for s in sources), "TERMINAL_REASON")
        peers = [x for x in self.g.artifacts.values() if x["artifact_kind"] == "reviewer-launch" and x["payload"]["review_id"] == p["review_id"] and x["artifact_id"] != a["artifact_id"]]
        require(not peers or a["replaces"] is not None, "REVIEW_REPEATED")

    def review_candidate(self, launch):
        """Resolve exact supplied Candidate evidence, including pre-execution STOP."""
        p = launch["payload"]
        candidates = self.g.direct(launch, "candidate-test-envelope")
        for ref in p["source_reports"]:
            source = self.g.artifacts[ref["artifact_id"]]
            candidates.extend(self.g.direct(source, "candidate-test-envelope"))
        candidates = {a["artifact_id"]: a for a in candidates}
        if p["candidate"] is None:
            require(not candidates, "REVIEW_CANDIDATE")
            return None
        matches = [a for a in candidates.values() if a["payload"]["candidate"] == p["candidate"]]
        require(len(matches) == 1, "REVIEW_CANDIDATE")
        candidate = matches[0]
        self.g.same_k(launch, candidate)
        if p["terminal_reason"] != "HUMAN_STOP":
            require(candidate["payload"]["implementation_tip"]["commit"] == p["last_implementation"], "REVIEW_IMPLEMENTATION")
        return candidate

    def stop_implementation(self, launch, candidate):
        """Bind completed Worker progress separately from the assembled Candidate."""
        reported = self.g.direct(launch, "implementation-report")
        baseline = self.g.one(candidate, "implementation-report") if candidate else None
        if not reported and baseline:
            reported = [baseline]
        if launch["payload"]["last_implementation"] is None:
            require(not reported, "STOP_IMPLEMENTATION")
            return None
        require(len(reported) == 1, "STOP_IMPLEMENTATION")
        implementation = reported[0]
        p = implementation["payload"]
        self.g.same_k(launch, implementation)
        require(p["status"] == "READY" and p["implementation_tip"] is not None and p["implementation_tip"]["commit"] == launch["payload"]["last_implementation"], "STOP_IMPLEMENTATION")
        if baseline:
            previous = baseline["payload"]
            require(p["lane"] == previous["lane"], "STOP_LANE")
            old, new = previous["implementation_tip"]["commit"], p["implementation_tip"]["commit"]
            if old == new:
                require(p["implementation_index"] == previous["implementation_index"], "STOP_IMPLEMENTATION_INDEX")
            else:
                require(p["implementation_index"] == previous["implementation_index"] + 1 and p["previous_implementation"] == old, "STOP_IMPLEMENTATION_INDEX")
                self.g.strict_ancestor(old, new)
        else:
            require(p["implementation_index"] == 0, "STOP_IMPLEMENTATION_INDEX")
        return implementation

    def review_correction_count(self, launch, candidate):
        if launch["payload"]["terminal_reason"] == "HUMAN_STOP":
            implementation = self.stop_implementation(launch, candidate)
            return implementation["payload"]["implementation_index"] if implementation else 0
        return candidate["payload"]["correction_count"] if candidate else 0

    def reviewer_report(self, a):
        p = a["payload"]
        launch = self.g.one(a, "reviewer-launch")
        self.dispatch(a, launch)
        require(p["review_id"] == launch["payload"]["review_id"], "REVIEW_IDENTITY")
        require(p["verdict"] != "APPROVED" or not any(f["severity"] == "BLOCKER" for f in p["findings"]), "REVIEW_BLOCKER")
        require(p["lessons"]["evidence_type"] == "lesson", "LESSON_TYPE")

    def terminal_record(self, a):
        p = a["payload"]
        review = self.g.one(a, "reviewer-report")
        require(p["review"] == self.g.refs[review["artifact_id"]], "TERMINAL_REVIEW")
        launch = self.g.one(review, "reviewer-launch")
        lp = launch["payload"]
        require(p["preserved_implementation"] == lp["last_implementation"], "PRESERVED_IMPLEMENTATION")
        candidate = self.review_candidate(launch)
        index = candidate["payload"]["candidate_index"] if candidate else None
        count = self.review_correction_count(launch, candidate)
        require(p["candidate_index"] == index and p["correction_count"] == count, "TERMINAL_COUNT")
        if p["result"] == "SUCCESS":
            require(lp["terminal_reason"] == "TESTER_PASS" and review["payload"]["verdict"] == "APPROVED", "SUCCESS_EVIDENCE")
            require(p["accepted_candidate"] == lp["candidate"]["commit"] and p["disposition"] in {"OPEN_SUCCESS_PR", "MERGED"}, "SUCCESS_CANDIDATE")
            if p["pr"]:
                require(p["pr"]["head_sha"] == p["accepted_candidate"], "PR_HEAD")
            if p["disposition"] == "MERGED":
                require(p["pr"] is not None and p["pr"]["merge_sha"] is not None and p["final_decision"] is not None, "MERGE_EVIDENCE")
                decision = self.g.artifacts[p["final_decision"]["artifact_id"]]
                require(decision["artifact_kind"] == "human-decision" and decision["payload"]["gate"] == "FINAL" and decision["payload"]["decision"] == "APPROVE" and decision["payload"]["subject_sha"] == p["accepted_candidate"], "MERGE_APPROVAL")
        else:
            require(p["accepted_candidate"] is None and p["pr"] is None and p["disposition"] == "RECORD_FAILURE", "FAILURE_NOT_PR")

    def guard_result(self, a):
        if a["status"] == "CHECKED":
            require(a["trusted_context"] is not None and all(v is not None for v in a["input"].values()) and not a["violations"] and a["exit_code"] == 0 and a["evidence_available"], "CHECKED_IDENTITY")

    def delivery_repair(self, a):
        p = a["payload"]
        original = self.g.artifacts[p["original"]["artifact_id"]]
        rejection = self.g.artifacts[p["rejection"]["artifact_id"]]
        require(p["original"] in a["predecessors"] and p["rejection"] in a["predecessors"], "REPAIR_PREDECESSOR")
        require(rejection["artifact_kind"] == "guard-result" and rejection["status"] == "REJECTED" and rejection["input"]["sha256"] == p["original"]["sha256"], "REPAIR_REJECTION")
        require(a["consumer_role"] == original["producer_role"], "REPAIR_CONSUMER")
        require(a["visibility"] == original["visibility"], "REPAIR_VISIBILITY")
        op = original["payload"]
        require(p["lane"] == op.get("lane", p["lane"]), "REPAIR_LANE")
        tip = op.get("implementation_tip") or op.get("test_tip") or op.get("candidate")
        source = tip["commit"] if tip else None
        index = op.get("candidate_index")
        count = op.get("correction_count", op.get("implementation_index", 0))
        if original["artifact_kind"] == "tester-confidential-report":
            candidate = self.repair_predecessor(a, original, "candidate-test-envelope")
            cp = candidate["payload"]
            require(op["candidate_sha"] == cp["candidate"]["commit"] and op["candidate_index"] == cp["candidate_index"] and op["execution_id"] == cp["execution_id"], "REPAIR_CANDIDATE")
            source, index, count = op["candidate_sha"], cp["candidate_index"], cp["correction_count"]
        elif original["artifact_kind"] == "reviewer-report":
            launch = self.repair_predecessor(a, original, "reviewer-launch")
            require(op["review_id"] == launch["payload"]["review_id"], "REPAIR_REVIEW")
            candidate = self.review_candidate(launch)
            source = launch["payload"]["candidate"]["commit"] if candidate else launch["payload"]["last_implementation"]
            index = candidate["payload"]["candidate_index"] if candidate else None
            count = self.review_correction_count(launch, candidate)
        require(p["preserve_tip"] == source, "REPAIR_TIP")
        require(p["preserve_candidate_index"] == index and p["preserve_correction_count"] == count and p["preserve_review_id"] == op.get("review_id"), "REPAIR_IDENTITY")

    def repair_predecessor(self, envelope, original, kind):
        refs = [ref for ref in original["predecessors"] if ref["kind"] == kind]
        require(len(refs) == 1 and (refs[0] in envelope["predecessors"] or refs[0] in self.g.context["predecessor_refs"]), "REPAIR_SOURCE_REFERENCE")
        source = self.g.artifacts[refs[0]["artifact_id"]]
        self.g.same_k(original, source)
        self.check(source)
        return source

    def replacement(self, a):
        replacement = a["replaces"]
        original = self.g.artifacts[replacement["original"]["artifact_id"]]
        require(original["artifact_id"] != a["artifact_id"] and original["artifact_kind"] == a["artifact_kind"], "REPLACEMENT_IDENTITY")
        require(original["task_contract"] == a["task_contract"], "REPAIR_CONTRACT")
        guard = self.g.artifacts[replacement["guard_result"]["artifact_id"]]
        require(guard["artifact_kind"] == "guard-result" and guard["status"] == "REJECTED" and guard["input"]["sha256"] == replacement["original"]["sha256"], "REPAIR_REJECTION")
        preserved = ("status", "outcome", "verdict", "implementation_index", "implementation_tip", "previous_implementation",
                     "test_tip", "candidate", "candidate_index", "candidate_sha", "correction_count", "review_id", "lane", "result",
                     "accepted_candidate", "preserved_implementation", "impact_set", "test_manifest", "implementation_manifest")
        for key in preserved:
            require(a["payload"].get(key) == original["payload"].get(key), "REPAIR_BUSINESS_CHANGE")
        if a["payload"].get("dispatch_id") != original["payload"].get("dispatch_id"):
            repair = self.g.one(a, "delivery-repair")
            require(repair["payload"]["original"] == replacement["original"] and a["payload"]["dispatch_id"] == repair["payload"]["dispatch_id"], "REPAIR_DISPATCH")
