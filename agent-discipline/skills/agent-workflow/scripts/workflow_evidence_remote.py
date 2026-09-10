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
# File:        workflow_evidence_remote.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-09
# Version:     0.1.0
# Description: Read-only exact workflow evidence verification.
# =================================================================================

"""Exact read-only GitHub authority and accepted-Candidate finalization."""

import json
import copy
import re
from datetime import datetime

from workflow_evidence_io import WorkflowEvidenceError, process, require
from workflow_transition_wire import canonical, digest


def remote_json(raw, code):
    """REST JSON may contain extra finite numeric fields; protocol wire may not."""
    def pairs(items):
        value = {}
        for key, child in items:
            require(key not in value, code, "/remote")
            value[key] = child
        return value
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        require(type(value) is dict, code, "/remote")
        canonical(value)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise WorkflowEvidenceError(code, "/remote") from None


class RemoteProof:
    def __init__(self, graph, authority, github_get):
        self.graph, self.authority, self.get = graph, authority, github_get
        self.repository = graph.state["task"]["repository"]
        self.issue = graph.state["task"]["issue_number"]
        self.bodies = {}

    def fetch(self, endpoint):
        if endpoint in self.bodies:
            return self.bodies[endpoint]
        require(callable(self.get), "REMOTE_UNAVAILABLE", "/remote")
        try:
            response = self.get(endpoint)
        except WorkflowEvidenceError:
            raise
        except Exception:
            raise WorkflowEvidenceError("REMOTE_UNAVAILABLE", "/remote") from None
        require(type(response) is dict and set(response) == {"status", "body"}
                and type(response["status"]) is int and type(response["body"]) is dict,
                "REMOTE_UNAVAILABLE", "/remote")
        require(response["status"] != 404, "MISSING_EVIDENCE", "/remote")
        require(response["status"] == 200, "REMOTE_UNAVAILABLE", "/remote")
        try:
            require(remote_json(canonical(response["body"]), "REMOTE_UNAVAILABLE") == response["body"],
                    "REMOTE_UNAVAILABLE", "/remote")
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise WorkflowEvidenceError("REMOTE_UNAVAILABLE", "/remote") from None
        self.bodies[endpoint] = copy.deepcopy(response["body"])
        return self.bodies[endpoint]

    def comment(self, number):
        body = self.fetch(f"/repos/{self.repository}/issues/comments/{number}")
        require(type(body.get("id")) is int and body["id"] == number
                and body.get("html_url") == f"https://github.com/{self.repository}/issues/{self.issue}#issuecomment-{number}"
                and body.get("issue_url") == f"https://api.github.com/repos/{self.repository}/issues/{self.issue}",
                pointer="/authority/comment")
        require(type(body.get("user")) is dict and type(body.get("body")) is str,
                pointer="/authority/comment")
        require(body.get("in_reply_to_id") is None and "pull_request" not in body
                and body.get("deleted", False) is False,
                pointer="/authority/comment")
        for key in ("created_at", "updated_at"):
            require(type(body.get(key)) is str and
                    re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", body[key]),
                    pointer="/authority/comment")
            try:
                datetime.fromisoformat(body[key].replace("Z", "+00:00"))
            except ValueError:
                raise WorkflowEvidenceError("INVALID_EVIDENCE", "/authority/comment") from None
        return body

    def human(self):
        nominations = {p["decision_artifact_id"]: p["packet_comment_id"]
                       for p in self.authority["packets"]}
        done = set()
        for item in self.graph.state["consumed"]:
            body = self.graph.artifacts[item["artifact"]["artifact_id"]]
            if body["artifact_kind"] != "human-decision":
                continue
            while body.get("replaces"):
                body = self.graph.artifacts[body["replaces"]["original"]["artifact_id"]]
            if body["artifact_id"] in done:
                continue
            done.add(body["artifact_id"])
            p = body["payload"]
            source = p["source"]
            require(p["decision"] != "STOP" and source["kind"] == "github-issue-comment",
                    "AUTHORITY_UNVERIFIABLE", "/authority/source")
            pattern = (rf"https://github\.com/{re.escape(self.repository)}/issues/{self.issue}"
                       r"#issuecomment-([1-9][0-9]*)")
            match = re.fullmatch(pattern, source["locator"])
            require(match is not None, pointer="/authority/source")
            require(body["artifact_id"] in nominations, "MISSING_EVIDENCE", "/authority/packets")
            number = int(match.group(1))
            remote = self.comment(number)
            packet = self.comment(nominations[body["artifact_id"]])
            raw = remote_json(self.graph.raw(source["raw"]), "INVALID_EVIDENCE")
            for key in ("id", "html_url", "issue_url", "body", "created_at", "updated_at"):
                require(key in raw and type(raw[key]) is type(remote[key]) and raw[key] == remote[key],
                        pointer="/authority/source")
            require(type(raw.get("user")) is dict and all(
                key in raw["user"] and raw["user"][key] == remote["user"].get(key)
                for key in ("login", "type")), pointer="/authority/source")
            login = remote["user"].get("login")
            require(remote["user"].get("type") == "User" and
                    login in self.authority["authorized_actors"] and login == p["authority_actor"],
                    pointer="/authority/actor")
            require(source["created_at"] == source["updated_at"] == remote["created_at"] == remote["updated_at"]
                    and source["deleted"] is False and raw.get("deleted", False) is False
                    and raw.get("in_reply_to_id") is None and "pull_request" not in raw,
                    pointer="/authority/source")
            require(datetime.fromisoformat(remote["created_at"].replace("Z", "+00:00")) >
                    datetime.fromisoformat(packet["created_at"].replace("Z", "+00:00")),
                    pointer="/authority/packet")
            word = "test" if p["gate"] == "TEST" else "candidate"
            if p["decision"] == "APPROVE":
                expected = f"/approve-{word} {p['subject_sha']}"
            else:
                require(type(p["reason"]) is str and p["reason"].strip(), pointer="/authority/command")
                expected = f"/request-{word}-changes {p['subject_sha']} {p['reason']}"
            require(remote["body"] == expected, pointer="/authority/command")
        return "PASS" if done else "NOT_APPLICABLE"

    def finalization(self):
        state = self.graph.state
        if state["terminal"] is None:
            return "NOT_APPLICABLE"
        terminal = self.graph.artifacts[state["terminal"]["artifact_id"]]["payload"]
        if terminal["result"] != "SUCCESS":
            require(terminal["accepted_candidate"] is None and terminal["pr"] is None,
                    pointer="/terminal")
            return "PASS"
        candidate = self.graph.artifacts[state["candidate"]["envelope"]["artifact_id"]]["payload"]
        result = self.graph.artifacts[state["candidate"]["result"]["artifact_id"]]["payload"]
        review = self.graph.artifacts[state["review"]["report"]["artifact_id"]]["payload"]
        sha = candidate["candidate"]["commit"]
        require(terminal["accepted_candidate"] == sha and result["candidate_sha"] == sha
                and result["outcome"] == "PASS" and review["verdict"] == "APPROVED",
                pointer="/terminal")
        pr = terminal["pr"]
        if pr is None and terminal["disposition"] == "OPEN_SUCCESS_PR":
            return "NOT_APPLICABLE"
        require(pr is not None, "MISSING_EVIDENCE", "/terminal/pr")
        match = re.fullmatch(rf"https://github\.com/{re.escape(self.repository)}/pull/([1-9][0-9]*)", pr["url"])
        require(match is not None and pr["head_sha"] == sha, pointer="/terminal/pr")
        number = int(match.group(1))
        remote = self.fetch(f"/repos/{self.repository}/pulls/{number}")
        require(type(remote.get("number")) is int and remote["number"] == number
                and remote.get("html_url") == pr["url"], pointer="/terminal/pr")
        base, head = remote.get("base"), remote.get("head")
        require(type(base) is dict and type(head) is dict
                and type(base.get("repo")) is dict
                and base["repo"].get("full_name") == self.repository
                and base.get("ref") == self.authority["base_ref"] and head.get("sha") == sha,
                pointer="/terminal/pr")
        if terminal["disposition"] == "OPEN_SUCCESS_PR":
            require(remote.get("state") == "open" and remote.get("merged") is False
                    and base.get("sha") == state["governor"]["commit"], pointer="/terminal/pr")
        else:
            merge = remote.get("merge_commit_sha")
            require(remote.get("state") == "closed" and remote.get("merged") is True
                    and merge is not None and merge == pr["merge_sha"], pointer="/terminal/pr")
            final_ref = state["final_decision"]
            require(final_ref is not None, "MISSING_EVIDENCE", "/terminal/approval")
            final = self.graph.artifacts[final_ref["artifact_id"]]["payload"]
            require(final["gate"] == "FINAL" and final["decision"] == "APPROVE"
                    and final["subject_sha"] == sha, pointer="/terminal/approval")
            actual = self.graph.tip(merge)
            require(merge == sha or (actual["parents"] == [state["governor"]["commit"], sha]
                    and actual["tree"] == self.graph.tip(sha)["tree"]),
                    pointer="/terminal/merge")
        return "PASS"

    def evidence(self):
        return [{"endpoint": endpoint, "sha256": digest(body)}
                for endpoint, body in sorted(self.bodies.items())]


def github_cli(executable, timeout):
    def get(endpoint):
        try:
            result = process([executable, "api", "--method", "GET", "--hostname", "github.com",
                              "--include", endpoint], timeout=timeout, pointer="/remote")
        except WorkflowEvidenceError as error:
            if error.code == "COMMAND_TIMEOUT":
                raise
            raise WorkflowEvidenceError("REMOTE_UNAVAILABLE", "/remote") from None
        # --include is parsed only as transport status; errors never expose stderr.
        raw = result.stdout
        try:
            head, body = re.split(b"\r?\n\r?\n", raw, maxsplit=1)
            status = int(head.splitlines()[0].split()[1])
            parsed = remote_json(body, "REMOTE_UNAVAILABLE")
        except (ValueError, IndexError, UnicodeError):
            raise WorkflowEvidenceError("REMOTE_UNAVAILABLE", "/remote") from None
        if result.returncode and status == 200:
            raise WorkflowEvidenceError("REMOTE_UNAVAILABLE", "/remote")
        return {"status": status, "body": parsed}
    return get
