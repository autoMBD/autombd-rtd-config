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
# File:        test_coverage_dependencies.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-11
# Version:     0.1.0
# Description: Independent coverage dependency functional gate.
# =================================================================================

"""Issue #116 owner gate: independent real Git, byte bindings and public API.

RTD_COVERAGE_SCRIPTS is a prevalidation-only alternate package. Candidate commands
must leave it unset. No Worker file is imported by this owner gate.
"""
import copy
import json
import sys
from pathlib import Path

import pytest

SUPPORT = Path(__file__).resolve().parents[1] / "fixtures/coverage-dependencies"
sys.path.insert(0, str(SUPPORT))
from support import Repository, SCRIPTS, canonical, LocalRules
from structured_handoff_schema import ProtocolError, validate_definition
from repair_protocol import RepairError, validate_impact_projection, _dependency_audit


@pytest.fixture
def repo(tmp_path):
    return Repository(tmp_path / "source")


def accepted(result):
    code, receipt = result
    assert code == 0, receipt
    assert receipt["status"] == "CHECKED" and receipt["violations"] == []
    assert receipt["command_started"] == "NOT_STARTED"
    assert "outcome" not in receipt and "approved" not in receipt


def rejected(result, rule=None):
    code, receipt = result
    assert code == 1, receipt
    assert receipt["status"] == "REJECTED" and receipt["violations"]
    assert receipt["command_started"] == "NOT_STARTED"
    if rule:
        assert receipt["violations"][0]["rule_id"] == rule, receipt
    return receipt["violations"][0]["rule_id"]


@pytest.mark.parametrize("namespace", ["cobalt", "maple_23", "surface7"])
@pytest.mark.parametrize("version", [2, 3, 4])
def test_shared_coverage_has_no_cartesian_edge_obligation(tmp_path, namespace, version):
    h = Repository(tmp_path / "source", version=version, style="shared", namespace=namespace)
    before = h.fingerprints()
    assert not any(e["to"] == h.paths["review"] for e in h.impact_body["public_dependency_edges"])
    accepted(h.validate())
    assert h.fingerprints() == before


@pytest.mark.parametrize("style", ["split", "chain"])
def test_multilevel_edges_may_span_different_selected_checks(tmp_path, style):
    h = Repository(tmp_path / "source", style=style)
    pairs = {(e["from"], e["to"]) for e in h.impact_body["public_dependency_edges"]}
    assert (h.paths["impl"], h.paths["leaf"]) not in pairs
    accepted(h.validate())


def test_known_good_full_local_chain_and_cli(repo):
    for ref in (repo.k, repo.tlaunch, repo.wlaunch, repo.tr, repo.approval, repo.ir, repo.envelope):
        accepted(repo.validate(ref))
    accepted(repo.validate(cli=True))
    assert repo.git("show", repo.c + ":" + repo.paths["test"]).startswith("from amber.leaf")
    assert repo.git("show", repo.c + ":" + repo.paths["impl"]).endswith("VALUE += 2")


@pytest.mark.parametrize("same_reason", [True, False])
def test_duplicate_directed_pairs_are_rejected_before_deduplication(repo, same_reason):
    duplicate = copy.deepcopy(repo.impact_body["public_dependency_edges"][0])
    if not same_reason:
        duplicate["reason"] = "Different prose still describes the same directed pair"
    repo.impact_body["public_dependency_edges"].append(duplicate)
    repo.rebind()
    rule = rejected(repo.validate())
    assert "DEPENDENCY" in rule


@pytest.mark.parametrize("endpoint", ["from", "to"])
def test_declared_edge_endpoints_need_selected_coverage(repo, endpoint):
    # These real unchanged endpoints exist in G; changed-path coverage is complete.
    missing = repo.paths["middle" if endpoint == "from" else "leaf"]
    for check in repo.impact_body["selected_checks"]:
        check["covered_paths"] = [p for p in check["covered_paths"] if p != missing]
    repo.rebind()
    rule = rejected(repo.validate())
    assert "DEPENDENCY" in rule


def test_excluded_dependency_check_is_not_selected_coverage(repo):
    repo.impact_body["selected_checks"] = [c for c in repo.impact_body["selected_checks"] if c["id"] != "SUPPORT"]
    repo.impact_body["excluded_checks"].append({"id": "SUPPORT", "family": "functional", "reason": "These endpoints are deliberately unselected"})
    # Keep the report's family-selection projection truthful for this input.
    repo.rebind()
    body = copy.deepcopy(repo.objects[repo.tr["artifact_id"]])
    body["payload"]["impact_selection"].append({"family": "functional", "disposition": "EXCLUDED", "dependency_reason": "Unselected endpoint coverage"})
    tr = repo.store(body)
    approval = copy.deepcopy(repo.objects[repo.approval["artifact_id"]])
    approval["predecessors"] = [tr]
    ar = repo.store(approval)
    envelope = copy.deepcopy(repo.objects[repo.envelope["artifact_id"]])
    envelope["predecessors"] = [ar, tr, repo.ir]
    repo.envelope = repo.store(envelope)
    assert "DEPENDENCY" in rejected(repo.validate())


@pytest.mark.parametrize("mutation,rule", [
    ("omit-test", "COVERAGE_CHANGED_PATHS"), ("omit-impl", "COVERAGE_CHANGED_PATHS"),
    ("extra", "COVERAGE_CHANGED_PATHS"), ("duplicate", "COVERAGE_DUPLICATE_PATH"),
    ("wrong-owner", "COVERAGE_CHANGED_PATHS"), ("unknown-check", "COVERAGE_REFERENCE"),
    ("unknown-requirement", "COVERAGE_REFERENCE"), ("wrong-check-path", "COVERAGE_JOIN_MISSING"),
    ("test-tip", "COVERAGE_JOIN_IDENTITY"), ("impl-tip", "COVERAGE_JOIN_IDENTITY"),
    ("impact-digest", "COVERAGE_JOIN_IDENTITY"),
])
def test_changed_inventory_and_mapping_rejections_survive(repo, mutation, rule):
    body = copy.deepcopy(repo.join_body)
    rows = body["changed_paths"]
    if mutation.startswith("omit-"):
        owner = "TEST" if mutation == "omit-test" else "IMPLEMENTATION"
        rows.remove(next(x for x in rows if x["owner"] == owner))
    elif mutation == "extra":
        rows.append({**rows[0], "path": "not/a/change.py"})
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "wrong-owner":
        rows[0]["owner"] = "IMPLEMENTATION"
    elif mutation == "unknown-check":
        rows[0]["selected_check_ids"] = ["UNDECLARED"]
    elif mutation == "unknown-requirement":
        rows[0]["requirement_ids"] = ["UNDECLARED"]
    elif mutation == "wrong-check-path":
        rows[0]["selected_check_ids"] = ["IMPL"]
    elif mutation == "test-tip":
        body["test_commit"] = repo.i
    elif mutation == "impl-tip":
        body["implementation_commit"] = repo.t
    else:
        body["impact_set_sha256"] = "0" * 64
    repo.replace_join(body)
    before = repo.fingerprints()
    rejected(repo.validate(), rule)
    assert repo.fingerprints() == before


def test_selected_check_must_cover_the_changes_requirement(repo):
    next(c for c in repo.impact_body["selected_checks"] if c["id"] == "TEST")["requirement_ids"] = ["S"]
    repo.rebind()
    rejected(repo.validate(), "COVERAGE_JOIN_MISSING")


def test_empty_mapping_is_not_a_coverage_escape(repo):
    body = copy.deepcopy(repo.join_body)
    body["changed_paths"][0]["selected_check_ids"] = []
    repo.replace_join(body)
    rejected(repo.validate())


def test_ownership_overlap_is_rejected(tmp_path):
    h = Repository(tmp_path / "source", overlap=True)
    rejected(h.validate(), "OWNERSHIP_OVERLAP")


@pytest.mark.parametrize("mutation", ["digest", "context-head", "governor-blob", "tip-tree", "manifest", "frozen-impact", "extra-member"])
def test_exact_identity_schema_and_frozen_binding_reject(repo, mutation):
    if mutation == "digest":
        rejected(repo.validate(expected_digest="0" * 64))
        return
    if mutation == "context-head":
        rejected(repo.validate(context_change=lambda c: c.update(expected_head=repo.t)), "HEAD_MISMATCH")
        return
    if mutation == "governor-blob":
        rejected(repo.validate(context_change=lambda c: c["governor"].update(workflow_contract_blob=repo.tip(repo.g)["tree"])))
        return
    body = copy.deepcopy(repo.objects[repo.envelope["artifact_id"]])
    if mutation == "tip-tree":
        body["payload"]["candidate"]["tree"] = repo.tip(repo.g)["tree"]
    elif mutation == "manifest":
        old = json.loads((repo.root / body["payload"]["test_manifest"]["path"]).read_bytes())
        old["lane_sha"] = repo.i
        body["payload"]["test_manifest"] = repo.evidence("manifest", old)
    elif mutation == "frozen-impact":
        altered = copy.deepcopy(repo.impact_body)
        altered["selected_checks"][0]["argv"][-1] = "12"
        body["payload"]["impact_set"] = repo.evidence("impact-set", altered)
    else:
        body["payload"]["automatic_dependency_truth"] = True
    repo.envelope = repo.store(body)
    rejected(repo.validate())


@pytest.mark.parametrize("kind", ["omitted-real-edge", "false-edge", "false-reason"])
def test_structural_checked_cannot_certify_source_semantics(repo, kind):
    # The exact source is known here; this is a responsibility-boundary check,
    # not an automatic extractor or an assertion that such a graph is acceptable.
    actual = repo.git("show", repo.i + ":" + repo.paths["impl"])
    assert "from .middle import VALUE" in actual
    if kind == "omitted-real-edge":
        repo.impact_body["public_dependency_edges"].pop(0)
        assert not any(e["from"] == repo.paths["impl"] for e in repo.impact_body["public_dependency_edges"])
    elif kind == "false-edge":
        repo.impact_body["public_dependency_edges"].append({"from": repo.paths["impl"], "to": repo.paths["review"], "reason": "False synthetic import claim"})
        assert "review" not in actual
    else:
        repo.impact_body["public_dependency_edges"][0]["reason"] = "False claim that this imports review prose"
        assert "review" not in actual
    repo.rebind()
    accepted(repo.validate())


@pytest.mark.parametrize("field,value", [("id", "OTHER"), ("family", "unit"), ("argv", ["python", "wrong.py"]),
    ("requirement_ids", ["R"]), ("covered_paths", ["unrelated/path.py"])])
def test_metadata_repair_freezes_selected_acceptance(repo, field, value):
    new = copy.deepcopy(repo.impact_body)
    new["selected_checks"][0][field] = value
    with pytest.raises(RepairError):
        validate_impact_projection(repo.impact_body, new)


@pytest.mark.parametrize("part", ["excluded_checks", "prevalidation_obligations"])
def test_metadata_repair_freezes_exclusions_and_prevalidation(repo, part):
    new = copy.deepcopy(repo.impact_body)
    new[part] = []
    with pytest.raises(RepairError):
        validate_impact_projection(repo.impact_body, new)


def test_descriptive_repair_needs_complete_real_endpoint_audit(repo):
    before, after = copy.deepcopy(repo.impact_body), copy.deepcopy(repo.impact_body)
    before["public_dependency_edges"][0]["to"] = "misspelled/middle.py"
    facts = [repo.source(repo.i, repo.paths[key]) for key in ("impl", "middle")]
    edge = {"before": {"from": repo.paths["impl"], "to": "misspelled/middle.py"},
            "after": {"from": repo.paths["impl"], "to": repo.paths["middle"]},
            "source_bindings": facts, "explanation": "Exact component blob imports .middle; source typo only."}
    audit = {"source_facts": facts, "dependency_audit": [edge]}
    validate_impact_projection(before, after)
    _dependency_audit(audit, before, after)
    for modified in ({**audit, "dependency_audit": []}, {**audit, "source_facts": facts[:1]}):
        with pytest.raises(RepairError):
            _dependency_audit(modified, before, after)
    graph = repo.graph()
    for fact in facts:
        graph.verify_commit(fact["commit"])
        assert graph.git("rev-parse", fact["commit"] + ":" + fact["path"]) == fact["blob"]


def test_support_coverage_changes_need_actual_source_change(repo):
    path = "checks/transport_adapter.py"
    tip = repo.commit(repo.t, {path: b"def pass_through(value):\n    return value\n"})
    new = copy.deepcopy(repo.impact_body)
    new["selected_checks"][0]["covered_paths"].append(path)
    change = {"path": path, "before_blob": None, "after_blob": repo.source(tip, path)["blob"], "reason": "Added non-case transport support"}
    validate_impact_projection(repo.impact_body, new, source_changes=[change])
    with pytest.raises(RepairError):
        validate_impact_projection(repo.impact_body, new)


def test_coverage_join_uses_real_reference_graph_direct_entry(repo):
    graph = repo.graph()
    LocalRules(graph).coverage_join(graph.artifacts[repo.envelope["artifact_id"]])
    validate_definition(repo.impact_body, "ImpactSet")
