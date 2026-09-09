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
# File:        test_workflow_evidence.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Independent owner functional evidence verification gate.
# =================================================================================

"""Requirement-driven functional checks of the public evidence verifier only."""
import copy
import json
import math
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from workflow_evidence_cases import (ROOT, SCRIPTS, History, canonical, digest,
                                      load_target, snapshot, target_path)
import workflow_transition

RESULT_KEYS = {"schema_version", "status", "task", "governor", "task_contract", "input_sha256",
               "approved_test_sha", "effective_test_sha", "executed_test_sha", "implementation_sha",
               "candidate_sha", "candidate_index", "functional_correction_count", "accepted_candidate_sha",
               "terminal_disposition", "checks", "remote_evidence"}

@pytest.fixture(scope="session")
def api():
    return load_target()

@pytest.fixture
def history(tmp_path):
    return History(tmp_path / "source")

def assert_error(api, operation, code):
    with pytest.raises(api.WorkflowEvidenceError) as caught:
        operation()
    error = caught.value
    assert error.code == code, error.as_dict()
    assert isinstance(error.pointer, str) and error.pointer.startswith("/")
    assert isinstance(error.message, str) and error.message.strip()
    assert error.as_dict() == {"error": {"code": error.code, "pointer": error.pointer,
                                      "message": error.message}}
    assert not any(secret in json.dumps(error.as_dict()) for secret in
                   ("private-node", "private-assertion", "private-case", "Traceback"))
    return error.as_dict()

def invoke(api, h, *, state=None, context=None, authority=None, get=None, **options):
    s, c, a = h.inputs()
    return api.verify_evidence(s if state is None else state, context=c if context is None else context,
        repository_root=str(h.root.resolve()), authority=a if authority is None else authority,
        github_get=h.get if get is None else get, **options)

def test_public_api_exists():
    load_target()

def test_initial_closed_deterministic_nonmutating(api, history):
    h = history
    state, context, authority = h.inputs()
    before = copy.deepcopy((state, context, authority))
    files = snapshot(h.root)
    result = invoke(api, h, state=state, context=context, authority=authority)
    assert set(result) == RESULT_KEYS
    assert result["status"] == "VERIFIED" and result["schema_version"] == "1.0"
    assert result["input_sha256"] == {"state": digest(state), "context": digest(context),
                                     "authority": digest(authority)}
    for field in RESULT_KEYS - {"schema_version", "status", "task", "governor", "task_contract",
            "input_sha256", "functional_correction_count", "checks", "remote_evidence"}:
        assert result[field] is None
    assert result["task_contract"] is None and result["functional_correction_count"] == 0
    assert result["checks"]["state"] == "PASS"
    assert result["checks"]["human_authority"] == result["checks"]["finalization"] == "NOT_APPLICABLE"
    assert result["remote_evidence"] == [] and h.calls == []
    assert invoke(api, h) == result
    result["task"]["repository"] = "detached/result"
    assert (state, context, authority) == before and snapshot(h.root) == files

@pytest.mark.parametrize("stage,index", [("ready", None), ("candidate", 0), ("gap", 0), ("corrected", 1)])
def test_source_projection_and_count_are_independent(api, history, stage, index):
    h = history.ready()
    if stage != "ready":
        h.candidate_ready()
    if stage in ("gap", "corrected"):
        h.correction_ready(1, assemble=stage == "corrected")
    result = h.verify(api)
    assert result["candidate_index"] == index
    assert result["functional_correction_count"] == (1 if stage in ("gap", "corrected") else 0)
    assert result["implementation_sha"] == h.i
    assert result["approved_test_sha"] == result["effective_test_sha"] == h.t
    assert result["executed_test_sha"] == (None if stage == "ready" else h.t)
    assert result["candidate_sha"] == (None if stage == "ready" else h.objects[h.c["artifact_id"]]["payload"]["candidate"]["commit"])

@pytest.mark.parametrize("execute", [False, True])
def test_support_keeps_original_case_anchor(api, history, execute):
    h = history.ready().support_ready(execute=execute)
    r = h.verify(api)
    repair = h.objects[h.bridge.state["repairs"][-1]["artifact_id"]]["payload"]
    assert r["approved_test_sha"] == h.t
    assert r["effective_test_sha"] == repair["to_test_tip"]["commit"] != h.t
    assert r["executed_test_sha"] == (r["effective_test_sha"] if execute else None)
    assert r["functional_correction_count"] == 0

def test_full_chain_merge_and_failure(api, history):
    h = history.ready().candidate_ready()
    for index in (1, 2):
        h.correction_ready(index)
    h.proposal().merged()
    result = h.verify(api)
    assert result["terminal_disposition"] == "MERGED"
    assert result["candidate_index"] == result["functional_correction_count"] == 2
    assert result["accepted_candidate_sha"] == result["candidate_sha"]
    assert result["checks"] == {name: "PASS" for name in ("state", "git", "human_authority", "finalization")}
    assert result["remote_evidence"] == sorted(result["remote_evidence"], key=lambda v: v["endpoint"])
    assert result["remote_evidence"] == [{"endpoint": e, "sha256": digest(h.responses[e]["body"])}
                                         for e in sorted(set(h.calls))]
    assert all(set(entry) == {"endpoint", "sha256"} for entry in result["remote_evidence"])

def test_exhaustion_is_truthful_failure(api, history):
    h = history.ready().candidate_ready()
    for index in (1, 2, 3):
        h.correction_ready(index)
    h.proposal(success=False)
    result = h.verify(api)
    assert result["terminal_disposition"] == "RECORD_FAILURE"
    assert result["candidate_index"] == result["functional_correction_count"] == 3
    assert result["accepted_candidate_sha"] is None and result["implementation_sha"] == h.i
    assert not any("/pulls/" in endpoint for endpoint in h.calls)

@pytest.mark.parametrize("field,value", [
    ("schema_version", "2.0"), ("authorized_actors", []), ("authorized_actors", ["x", "x"]),
    ("authorized_actors", [" "]), ("base_ref", ""), ("packets", [{"decision_artifact_id": "x",
      "packet_comment_id": True}]), ("unknown", "forbidden")])
def test_authority_closed_shape(api, history, field, value):
    authority = copy.deepcopy(history.authority)
    authority[field] = value
    assert_error(api, lambda: invoke(api, history, authority=authority), "MALFORMED_INPUT")

@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf"), "15"])
def test_invalid_command_deadline(api, history, timeout):
    assert_error(api, lambda: invoke(api, history, command_timeout_seconds=timeout), "MALFORMED_INPUT")

def test_existing_invalid_state_priority(api, history):
    h = history.ready()
    state, context, _ = h.inputs()
    state["test"]["launch"] = None
    context["checks"] = []
    assert_error(api, lambda: invoke(api, h, state=state, context=context), "INVALID_STATE")

@pytest.mark.parametrize("missing", ["artifact", "receipt", "attachment", "object"])
def test_missing_owned_proof_is_not_not_applicable(api, history, missing):
    h = history.ready().candidate_ready()
    state, context, _ = h.inputs()
    if missing == "artifact":
        context["artifacts"] = [x for x in context["artifacts"] if x["ref"] != state["contract"]]
    elif missing == "receipt":
        context["checks"] = []
    elif missing == "attachment":
        (h.root / h.tm["path"]).unlink()
    else:
        sha = h.i
        object_path = h.root / ".git/objects" / sha[:2] / sha[2:]
        assert object_path.resolve().is_relative_to(h.root.resolve())
        object_path.chmod(stat.S_IREAD | stat.S_IWRITE)
        object_path.unlink()
    assert_error(api, lambda: invoke(api, h, state=state, context=context), "MISSING_EVIDENCE")

def test_present_attachment_tamper_is_invalid(api, history):
    h = history.ready()
    (h.root / h.tm["path"]).write_bytes(b"{}\n")
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

def test_real_candidate_direct_union_not_only_parent_claim(api, history):
    h = history.ready().candidate_ready(omitted=True)
    # Real guard/reducer accepted the historical parent/coverage proof, but its
    # Candidate tree omits the actual Test delta. The new verifier must catch it.
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

@pytest.mark.parametrize("field,value", [
    ("body", "/approve-test stale"), ("id", 13), ("issue_url", "https://api.github.com/repos/foreign/repo/issues/417"),
    ("html_url", "https://evil.invalid/comment"), ("created_at", "2026-09-09T00:00:00Z"),
    ("updated_at", "2026-09-09T04:00:00Z"), ("in_reply_to_id", 42), ("deleted", True)])
def test_remote_decision_identity_and_current_facts(api, history, field, value):
    h = history.ready()
    endpoint = next(e for e, r in h.responses.items() if r["body"]["body"].startswith("/approve-test"))
    h.responses[endpoint]["body"][field] = value
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

@pytest.mark.parametrize("user", [{"login": "intruder", "type": "User"},
                                 {"login": "boundary-owner", "type": "Bot"}])
def test_human_actor_is_explicit_policy(api, history, user):
    h = history.ready()
    endpoint = next(e for e, r in h.responses.items() if r["body"]["body"].startswith("/approve-test"))
    h.responses[endpoint]["body"]["user"] = user
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

@pytest.mark.parametrize("status,code", [(404, "MISSING_EVIDENCE"), (401, "REMOTE_UNAVAILABLE"),
                                       (403, "REMOTE_UNAVAILABLE"), (429, "REMOTE_UNAVAILABLE"),
                                       (503, "REMOTE_UNAVAILABLE")])
def test_remote_status_is_not_authorization(api, history, status, code):
    h = history.ready()
    for response in h.responses.values():
        response["status"] = status
    assert_error(api, lambda: h.verify(api), code)

def test_unavailable_transport_is_safe(api, history):
    h = history.ready()
    def unavailable(endpoint):
        raise OSError("private-case unavailable")
    assert_error(api, lambda: invoke(api, h, get=unavailable), "REMOTE_UNAVAILABLE")

@pytest.mark.parametrize("response", [{"status": True, "body": {}}, {"status": 200, "body": []},
                                    {"status": 200, "body": {}, "unexpected": True}])
def test_transport_shape_is_checked(api, history, response):
    h = history.ready()
    assert_error(api, lambda: invoke(api, h, get=lambda endpoint: response), "REMOTE_UNAVAILABLE")

@pytest.mark.parametrize("field,value", [("id", 93), ("issue_url", "https://api.github.com/repos/synthetic/repository/issues/999"),
                                        ("created_at", "2026-09-09T05:00:00Z")])
def test_packet_binding_and_strict_decision_order(api, history, field, value):
    h = history.ready()
    endpoint = next(e for e, r in h.responses.items() if r["body"]["body"] == "Review the exact source packet.")
    h.responses[endpoint]["body"][field] = value
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

def test_snapshots_are_not_authenticated_remote_transport(api, history):
    h = history.ready()
    state, context, authority = h.inputs()
    assert_error(api, lambda: api.verify_evidence(state, context=context, authority=authority,
        repository_root=str(h.root)), "REMOTE_UNAVAILABLE")

@pytest.mark.parametrize("field,value", [
    ("state", "closed"), ("merged", True), ("number", 99),
    ("html_url", "https://github.com/foreign/repository/pull/73"),
    ("base.ref", "wrong"), ("base.sha", "f" * 40), ("head.sha", "e" * 40),
    ("base.repo.full_name", "foreign/repository")])
def test_pr_exact_candidate_and_premerge_base(api, history, field, value):
    h = history.ready().candidate_ready().proposal()
    body = h.responses[f"/repos/{h.task['repository']}/pulls/73"]["body"]
    cursor = body
    keys = field.split(".")
    for key in keys[:-1]:
        cursor = cursor[key]
    cursor[keys[-1]] = value
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

@pytest.mark.parametrize("ff", [False, True])
def test_merge_lineage_uses_real_git_not_current_base(api, history, ff):
    h = history.ready().candidate_ready().proposal().merged(ff=ff)
    assert h.verify(api)["terminal_disposition"] == "MERGED"

def test_duplicate_reducer_event_keeps_source_count(api, history):
    h = history.ready().candidate_ready()
    state, context, _ = h.inputs()
    ref = state["consumed"][-1]["artifact"]
    checked = next(x["ref"] for x in context["checks"] if x["body"]["input"]["artifact_id"] == ref["artifact_id"])
    event = {"schema_version": "1.0", "type": "CONSUME", "event_id": state["consumed"][-1]["event_id"],
             "artifact": ref, "checked": checked}
    before = copy.deepcopy(state)
    with pytest.raises(workflow_transition.WorkflowTransitionError) as caught:
        workflow_transition.transition(state, event, context=context)
    assert caught.value.code == "DUPLICATE_EVENT" and state == before
    assert invoke(api, h)["functional_correction_count"] == 0

def run_cli(history, extra=()):
    state, context, authority = history.inputs()
    for name, value in (("state", state), ("context", context), ("authority", authority)):
        history.write("inputs/" + name + ".json", canonical(value))
    return subprocess.run([sys.executable, str(target_path()), "verify",
        "--state", str(history.root / "inputs/state.json"), "--context", str(history.root / "inputs/context.json"),
        "--authority", str(history.root / "inputs/authority.json"),
        "--repository-root", str(history.root), *extra], capture_output=True, timeout=45)

def test_cli_empty_state_and_help(api, history):
    result = run_cli(history, ("--github-cli", str(history.root / "must-not-run.exe")))
    assert result.returncode == 0 and result.stderr == b""
    body = json.loads(result.stdout)
    assert result.stdout == canonical(body) and body["status"] == "VERIFIED"
    help_result = subprocess.run([sys.executable, str(target_path()), "--help"], capture_output=True)
    assert help_result.returncode == 0 and help_result.stderr == b""

@pytest.mark.parametrize("argv", [[], ["verify"], ["unknown"]])
def test_cli_usage_is_structured(api, argv):
    result = subprocess.run([sys.executable, str(target_path()), *argv], capture_output=True)
    assert result.returncode == 2 and result.stdout == b""
    error = json.loads(result.stderr)
    assert set(error) == {"error"} and set(error["error"]) == {"code", "pointer", "message"}
    assert result.stderr == canonical(error)

def test_cli_semantic_rejection_uses_stderr(api, history):
    history.bridge.state["candidate"] = {"envelope": None, "result": None}
    result = run_cli(history)
    assert result.returncode == 1 and not result.stdout
    assert json.loads(result.stderr)["error"]["code"] == "INVALID_STATE"


@pytest.mark.parametrize("suffix", [" ", "\n", " trailing approval text"])
def test_exact_decision_command_not_prefix_or_whitespace(api, history, suffix):
    history.capture_command("/approve-test " + history.t + suffix)
    history.ready()
    assert_error(api, lambda: history.verify(api), "INVALID_EVIDENCE")

def test_request_changes_exact_reason_is_supported(api, history):
    reason = "Require explicit downstream evidence."
    history.capture_command("/request-test-changes " + history.t + " " + reason,
                            decision="REQUEST_CHANGES", reason=reason)
    history.ready()
    result = history.verify(api)
    assert result["approved_test_sha"] is None and result["candidate_sha"] is None
    assert result["checks"]["human_authority"] == "PASS"

def test_manual_authority_does_not_become_remote_verified(api, history):
    history.capture_command(kind="human-command")
    history.ready()
    assert_error(api, lambda: history.verify(api), "AUTHORITY_UNVERIFIABLE")

@pytest.mark.parametrize("field,value", [("status", "REJECTED"), ("exit_code", 1),
                                      ("evidence_available", False), ("consumer_role", "reviewer"),
                                      ("visibility", "terminal-review")])
def test_matching_invalid_receipt_is_invalid_evidence(api, history, field, value):
    h = history.ready()
    for body in list(h.objects.values()):
        if body["artifact_kind"] == "guard-result" and body["input"]["artifact_id"] == h.tr["artifact_id"]:
            body[field] = value
            h.store(body)
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

def test_valid_matching_receipt_not_poisoned_by_bad_alternative(api, history):
    h = history.ready()
    source = next(body for body in h.objects.values() if body["artifact_kind"] == "guard-result"
                  and body["input"]["artifact_id"] == h.tr["artifact_id"])
    bad = copy.deepcopy(source)
    bad.update(artifact_id="a-invalid-alternative", status="REJECTED", exit_code=1)
    h.store(bad)
    state, context, authority = h.inputs()
    first = invoke(api, h, state=state, context=context, authority=authority)
    context["checks"].reverse()
    second = invoke(api, h, state=state, context=context, authority=authority)
    first.pop("input_sha256")
    second.pop("input_sha256")
    assert first == second and first["status"] == "VERIFIED"

@pytest.mark.parametrize("path,operation", [
    ("tests/reference-fixture.py", "add"),
    ("tests/accepted-evidence-fixture.py", "delete"),
    ("tests/accepted-evidence-fixture.py", "execute"),
    ("tests/accepted-evidence-fixture.py", "link")])
def test_real_leaf_tree_modes_deletions_and_legitimate_names(api, history, path, operation):
    history.test_change(path, operation=operation)
    history.ready().candidate_ready()
    assert history.verify(api)["status"] == "VERIFIED"

@pytest.mark.parametrize("path", [".agent-state/forged-proof.json",
    "tests/.tmp/reference-overlay.py", "agent-discipline/agent-lessons-learned.md"])
def test_task_introduced_evidence_is_not_candidate_content(api, history, path):
    history.test_change(path)
    history.ready().candidate_ready()
    assert_error(api, lambda: history.verify(api), "INVALID_EVIDENCE")

def test_pre_pr_proposal_checks_local_truth_without_remote_pr(api, history):
    h = history.ready().candidate_ready()
    report = h.report("PASS")
    h.bridge.consume(report)
    terminal = h.terminal(report, True, 0)
    review = h.objects[terminal["artifact_id"]]["payload"]["review"]
    launch = h.objects[review["artifact_id"]]["predecessors"][0]
    for ref in (launch, review, terminal):
        h.bridge.consume(ref)
    result = h.verify(api)
    assert result["terminal_disposition"] == "OPEN_SUCCESS_PR"
    assert result["accepted_candidate_sha"] == result["candidate_sha"]
    assert result["checks"]["finalization"] == "NOT_APPLICABLE"
    assert not any("/pulls/" in path for path in h.calls)

def test_all_implementation_findings_are_mapped(api, history):
    h = history.ready().candidate_ready()
    ref = h.report("IMPLEMENTATION_FAIL")
    report = copy.deepcopy(h.objects[ref["artifact_id"]])
    second = copy.deepcopy(report["payload"]["findings"][0])
    second["id"] = "second-implementation-finding"
    report["payload"]["findings"].append(second)
    ref = h.store(report)
    h.bridge.consume(ref)
    h.bridge.consume(h.correction(1, ref))
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

def test_readonly_real_git_commands_and_deadlines(api, history, monkeypatch):
    h = history.ready().candidate_ready()
    before = snapshot(h.root)
    calls = []
    run = subprocess.run
    forbidden = {"merge", "checkout", "commit", "commit-tree", "read-tree", "write-tree",
                 "update-index", "update-ref", "add", "reset", "fetch", "push"}
    def observed(argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and Path(str(argv[0])).stem.lower() == "git":
            assert not forbidden.intersection(argv)
            assert not ("hash-object" in argv and "-w" in argv)
            assert kwargs.get("timeout") == 7.25
            calls.append(list(argv))
        return run(argv, *args, **kwargs)
    monkeypatch.setattr(subprocess, "run", observed)
    assert h.verify(api, command_timeout_seconds=7.25)["status"] == "VERIFIED"
    assert calls and snapshot(h.root) == before

def test_git_timeout_is_stable_without_private_output(api, history, monkeypatch):
    def timed_out(argv, *args, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 1), output=b"private-case")
    monkeypatch.setattr(subprocess, "run", timed_out)
    assert_error(api, lambda: history.verify(api), "COMMAND_TIMEOUT")

def test_explicit_absolute_repository_path_is_required(api, history):
    s, c, a = history.inputs()
    assert_error(api, lambda: api.verify_evidence(s, context=c, authority=a,
        repository_root="relative"), "MALFORMED_INPUT")


@pytest.mark.parametrize("status,exit_code,error_code", [(200, 0, None), (404, 1, "MISSING_EVIDENCE"),
                                                        (403, 2, "REMOTE_UNAVAILABLE")])
def test_cli_authenticated_get_only_and_http_mapping(api, history, monkeypatch, capfdbinary,
                                                    status, exit_code, error_code):
    import runpy
    h = history.ready()
    state, context, authority = h.inputs()
    for name, value in (("state", state), ("context", context), ("authority", authority)):
        h.write("cli/" + name + ".json", canonical(value))
    executable = h.write("cli/transport.exe", b"intercepted trusted GET transport")
    original = subprocess.run
    calls = []
    def transport(argv, *args, **kwargs):
        if str(argv[0]) != str(executable):
            return original(argv, *args, **kwargs)
        assert "api" in argv and "--hostname" in argv and "github.com" in argv
        assert kwargs.get("shell", False) is False and kwargs.get("timeout") == 6.5
        if "--method" in argv:
            assert argv[argv.index("--method") + 1] == "GET"
        if "-X" in argv:
            assert argv[argv.index("-X") + 1] == "GET"
        assert not set(argv) & {"auth", "login", "token", "--field", "-f", "-F"}
        endpoint = next(str(v) for v in argv if str(v).lstrip("/").startswith("repos/"))
        endpoint = "/" + endpoint.lstrip("/")
        calls.append(endpoint)
        body = canonical(h.responses[endpoint]["body"])
        if "--include" in argv or "-i" in argv:
            body = f"HTTP/2.0 {status}\r\ncontent-type: application/json\r\n\r\n".encode() + body
        stderr = b"" if status == 200 else f"gh: HTTP {status}\n".encode()
        if kwargs.get("text") or kwargs.get("encoding"):
            body, stderr = body.decode(), stderr.decode()
        return subprocess.CompletedProcess(argv, 0 if status == 200 else 1, body, stderr)
    monkeypatch.setattr(subprocess, "run", transport)
    monkeypatch.setattr(sys, "argv", [str(target_path()), "verify",
        "--state", str(h.root / "cli/state.json"), "--context", str(h.root / "cli/context.json"),
        "--authority", str(h.root / "cli/authority.json"), "--repository-root", str(h.root),
        "--github-cli", str(executable), "--command-timeout-seconds", "6.5"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(target_path()), run_name="__main__")
    assert caught.value.code == exit_code
    captured = capfdbinary.readouterr()
    if status == 200:
        assert not captured.err and json.loads(captured.out)["status"] == "VERIFIED"
    else:
        assert not captured.out and json.loads(captured.err)["error"]["code"] == error_code
    assert calls

def test_closed_authority_result_schema_only(api, history):
    schema_path = Path(os.environ.get("RTD_EVIDENCE_SCHEMA",
        SCRIPTS.parent / "schemas/workflow-evidence-v1.schema.json"))
    assert schema_path.is_file(), "R14 missing closed public authority/result schema"
    schema = json.loads(schema_path.read_bytes())
    def objects(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from objects(child)
        elif isinstance(value, list):
            for child in value:
                yield from objects(child)
    shapes = list(objects(schema))
    for required in (set(history.authority), RESULT_KEYS):
        matches = [node for node in shapes if set(node.get("properties", {})) == required]
        assert matches and all(node.get("additionalProperties") is False and
                               set(node.get("required", [])) == required for node in matches)
    assert not {"State", "Context"} & set(schema.get("$defs", {}))


@pytest.mark.parametrize("variant", ["squash", "extra", "wrong-parent"])
def test_merge_rebuild_or_additional_edits_are_rejected(api, history, variant):
    h = history.ready().candidate_ready().proposal().merged(variant=variant)
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")

@pytest.mark.parametrize("variant", ["third-lane", "blob", "mode"])
def test_candidate_merge_only_tree_tamper_is_rejected(api, history, variant):
    h = history.ready()
    ref = h.candidate(0)
    body = copy.deepcopy(h.objects[ref["artifact_id"]])
    h.git("read-tree", body["payload"]["candidate"]["commit"])
    path = "src/third.py" if variant == "third-lane" else "src/component.py"
    blob = (h.git("rev-parse", h.i + ":" + path) if variant == "mode" else
            h.git("hash-object", "-w", "--stdin", data=b"merge-only edit"))
    h.git("update-index", "--add", "--cacheinfo",
          ("100755" if variant == "mode" else "100644") + "," + blob + "," + path)
    candidate = h.git("commit-tree", h.git("write-tree"), "-p", h.t, "-p", h.i, "-m", variant)
    body["payload"]["candidate"] = h.tip(candidate)
    h.c = h.store(body)
    h.bridge.consume(h.c)
    assert_error(api, lambda: h.verify(api), "INVALID_EVIDENCE")
