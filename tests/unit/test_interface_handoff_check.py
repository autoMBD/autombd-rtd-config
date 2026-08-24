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
# File:        test_interface_handoff_check.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-24
# Version:     0.1.0
# Description: Verify the immutable interface-handoff CLI and packet contract.
# =================================================================================

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
SCRIPTS = REPOSITORY / "agent-discipline" / "skills" / "agent-workflow" / "scripts"
CHECKER = SCRIPTS / "interface_handoff_check.py"
HANDOFF_GUARD = SCRIPTS / "handoff_guard.py"
TEST_TMP_PARENT = HERE.parent / ".tmp"
TOP_KEYS = {
    "schema_version", "handoff_kind", "issue_number", "base_sha",
    "workflow_contract_blob_sha", "test_sha", "consumer_role",
    "required_interfaces", "interfaces", "authorities",
    "reference_prevalidation", "forbidden_sources", "unresolved",
}
ENTRY_KEYS = {
    "python": {"kind", "path", "symbol", "signature"},
    "cli": {"kind", "path", "argv", "stdin", "stdout", "stderr", "exit_codes"},
    "json": {"kind", "path", "top_level_type", "required_keys"},
}
AUTHORITY_KEYS = {"kind", "id", "sha256"}
PREVALIDATION_KEYS = {"receipt_sha256", "outcome"}
PASS_KEYS = {"schema_version", "packet_sha256", "outcome"}
PREFIX = b"interface handoff rejected: "
DELETE = object()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def unique_object(pairs):
    if len(dict(pairs)) != len(pairs):
        raise ValueError("duplicate JSON object key")
    return dict(pairs)


class InterfaceHandoffTargetPresenceTests(unittest.TestCase):
    def test_required_production_cli_exists(self):
        self.assertTrue(CHECKER.is_file(), f"required production CLI is absent: {CHECKER}")


@unittest.skipUnless(CHECKER.is_file(), "contract exercises require production CLI")
class InterfaceHandoffCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._created_temp_parent = not TEST_TMP_PARENT.exists()
        TEST_TMP_PARENT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if cls._created_temp_parent:
            TEST_TMP_PARENT.rmdir()

    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(dir=TEST_TMP_PARENT)
        self.root = Path(self._temporary.name)
        self.assertEqual(TEST_TMP_PARENT.resolve(), self.root.resolve().parent)
        self._counter = 0

    def tearDown(self):
        self._temporary.cleanup()

    @staticmethod
    def entry(kind, path=None):
        paths = {"python": "pkg/public_api.py", "cli": "tools/interface_check.py",
                 "json": "contracts/interface-handoff.json"}
        path = paths[kind] if path is None else path
        if kind == "python":
            return {"kind": kind, "path": path, "symbol": "validate_handoff",
                    "signature": "validate_handoff(packet_bytes, expected_sha256)"}
        if kind == "cli":
            return {"kind": kind, "path": path,
                    "argv": ["python", path, "validate", "--packet", "handoff.json",
                             "--expected-sha256", "0" * 64],
                    "stdin": "none", "stdout": "compact PASS JSON record",
                    "stderr": "stable rejection diagnostic or argparse usage",
                    "exit_codes": [0, 1, 2]}
        return {"kind": kind, "path": path, "top_level_type": "object",
                "required_keys": ["schema_version", "interfaces"]}

    def packet(self, history=1):
        value = {
            "schema_version": 1, "handoff_kind": "owner-test-to-worker", "issue_number": 314,
            "base_sha": "1" * 40, "workflow_contract_blob_sha": "2" * 40,
            "test_sha": "3" * 40, "consumer_role": "worker",
            "required_interfaces": ["cli", "json"],
            "interfaces": [self.entry("cli"), self.entry("json")],
            "authorities": [{"kind": "issue_body", "id": 314, "sha256": "4" * 64}],
            "reference_prevalidation": {"receipt_sha256": "5" * 64, "outcome": "PASS"},
            "forbidden_sources": ["owner_test_source", "owner_test_literals"], "unresolved": [],
        }
        if history == 1:
            return value
        if history != 2:
            raise ValueError(f"unknown synthetic history: {history}")
        python_one = self.entry("python", r"src\public_api.py")
        python_one.update(symbol="todo_count", signature="todo_count(unknown_value)")
        python_two = self.entry("python", r"src\alternate_api.py")
        python_two["symbol"] = "validate_unknown_items"
        cli = self.entry("cli", r"bin\interface_check.py")
        cli.update(stdin="TODO values are described by ordinary prose",
                   stdout="unknown values are reported without ambiguity", exit_codes=[255, 0, 2])
        json_entry = self.entry("json", r"schemas\handoff-array.json")
        json_entry.update(top_level_type="array", required_keys=["todo_count", "unknown_count"])
        value.update(issue_number=2718, base_sha="a" * 40, workflow_contract_blob_sha="b" * 40,
                     test_sha="c" * 40, required_interfaces=["json", "python", "cli"],
                     interfaces=[python_one, cli, json_entry, python_two],
                     authorities=[{"kind": "issue_body", "id": 2718, "sha256": "d" * 64},
                                  {"kind": "issue_comment", "id": 1618, "sha256": "e" * 64}],
                     reference_prevalidation={"receipt_sha256": "f" * 64, "outcome": "PASS"})
        return value

    def only(self, kind, entry=None):
        value = self.packet()
        value.update(required_interfaces=[kind], interfaces=[entry or self.entry(kind)])
        return value

    def changed(self, path, replacement=DELETE, source=None):
        value = copy.deepcopy(source if source is not None else self.packet())
        target = value
        for component in path[:-1]:
            target = target[component]
        if replacement is DELETE:
            target.pop(path[-1])
        else:
            target[path[-1]] = replacement
        return value

    def write(self, value=None, raw=None):
        self._counter += 1
        path = self.root / f"packet-{self._counter}.json"
        data = canonical(value) if raw is None else raw
        path.write_bytes(data)
        return path, data

    def invoke(self, *arguments):
        environment = os.environ.copy()
        environment.update(PYTHONDONTWRITEBYTECODE="1", PATH="")
        return subprocess.run([sys.executable, str(CHECKER), *map(str, arguments)], cwd=self.root,
                              capture_output=True, env=environment, timeout=10, check=False)

    def guard(self, cwd, *arguments):
        environment = os.environ.copy()
        environment.update(PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1",
                           GIT_CONFIG_GLOBAL=os.devnull)
        return subprocess.run([sys.executable, str(HANDOFF_GUARD), *map(str, arguments)], cwd=cwd,
                              capture_output=True, env=environment, timeout=20, check=False)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def one_line(self, stream):
        newline = os.linesep.encode()
        body = stream[:-len(newline)] if stream.endswith(newline) else stream
        self.assertNotIn(b"\r", body)
        self.assertNotIn(b"\n", body)
        return body

    def assert_pass_record(self, stream, digest):
        body = self.one_line(stream)
        value = json.loads(body.decode(), object_pairs_hook=unique_object)
        self.assertEqual(PASS_KEYS, set(value))
        self.assertIs(type(value["schema_version"]), int)
        self.assertEqual({"schema_version": 1, "packet_sha256": digest, "outcome": "PASS"}, value)
        self.assertEqual(json.dumps(value, separators=(",", ":")).encode(), body)

    def accept(self, value=None, *, raw=None):
        path, raw = self.write(value=value, raw=raw)
        digest, before = hashlib.sha256(raw).hexdigest(), self.snapshot()
        result = self.invoke("validate", "--packet", path, "--expected-sha256", digest)
        self.assertEqual(0, result.returncode, result.stderr.decode(errors="replace"))
        self.assertEqual(b"", result.stderr)
        self.assert_pass_record(result.stdout, digest)
        self.assertEqual(before, self.snapshot())
        return raw, digest

    def assert_rejection_result(self, result, fragments=()):
        self.assertEqual((1, b""), (result.returncode, result.stdout),
                         result.stderr.decode(errors="replace"))
        line = self.one_line(result.stderr)
        self.assertTrue(line.startswith(PREFIX), line)
        suffix = line[len(PREFIX):]
        self.assertTrue(suffix.strip())
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertTrue(not fragments or any(f.lower().encode() in suffix.lower() for f in fragments),
                        f"diagnostic {suffix!r} did not name {fragments!r}")
        return result.returncode, result.stdout, result.stderr

    def reject(self, value=None, *, raw=None, expected=None, fragments=(), repeat=False):
        path, data = self.write(value=value, raw=raw)
        digest = hashlib.sha256(data).hexdigest() if expected is None else expected
        before = self.snapshot()
        args = ("validate", "--packet", path, "--expected-sha256", digest)
        first = self.assert_rejection_result(self.invoke(*args), fragments)
        if repeat:
            second = self.assert_rejection_result(self.invoke(*args), fragments)
            self.assertEqual(first, second)
        self.assertEqual(before, self.snapshot())

    def reject_table(self, cases, source=None):
        for label, path, invalid, fragments in cases:
            with self.subTest(case=label):
                self.reject(self.changed(path, invalid, source), fragments=fragments)

    def closed_object(self, source, path, keys, fragments):
        for field in sorted(keys):
            with self.subTest(missing=field, path=path):
                self.reject(self.changed((*path, field), source=source),
                            fragments=(*fragments, field, "schema", "keys"))
        self.reject(self.changed((*path, "extension"), "not approved", source),
                    fragments=(*fragments, "schema", "field"))

    def test_two_distinct_synthetic_histories_pass_with_exact_envelopes(self):
        first = self.accept(self.packet(1))
        second = self.accept(self.packet(2))
        self.assertNotEqual(first, second)
        non_ascii = self.packet()
        non_ascii["interfaces"][0]["stdout"] = "接口契约已冻结"
        valid_raw_packets = (
            ("whitespace-member-order", json.dumps(self.packet(), ensure_ascii=False, indent=2).encode()),
            ("non-ascii", json.dumps(non_ascii, ensure_ascii=False, separators=(",", ":")).encode()),
        )
        for label, raw in valid_raw_packets:
            with self.subTest(valid_transport=label):
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                if label == "whitespace-member-order":
                    self.assertIn(b"\n", raw)
                    self.assertTrue(raw.startswith(b'{\n  "schema_version"'))
                    self.assertNotEqual(canonical(json.loads(raw)), raw)
                else:
                    self.assertIn("接口".encode(), raw)
                self.accept(raw=raw)

    def test_public_cli_usage_errors_are_argparse_owned_exit_2(self):
        packet, raw = self.write(value=self.packet())
        digest = hashlib.sha256(raw).hexdigest()
        cases = ((), ("validate",), ("validate", "--packet", packet),
                 ("validate", "--expected-sha256", digest),
                 ("validate", "--packet", packet, "--expected-sha256", digest, "--unknown"))
        before = self.snapshot()
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual((2, b""), (result.returncode, result.stdout))
                self.assertIn(b"usage:", result.stderr.lower())
                self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_raw_byte_digest_drift_and_malformed_expected_digest_fail_closed(self):
        raw = canonical(self.packet())
        actual = hashlib.sha256(raw).hexdigest()
        wrong = "0" * 64 if actual != "0" * 64 else "1" * 64
        for data, expected in ((raw, wrong), (raw + b"\n", actual)):
            self.reject(raw=data, expected=expected, fragments=("digest", "sha256", "sha-256"))
        for malformed in ("a" * 63, "A" * 64, "g" * 64, ""):
            self.reject(raw=raw, expected=malformed, fragments=("digest", "sha256", "sha-256"))
        sha_member = b'"sha256":"' + b"4" * 64 + b'"'
        duplicate_sha = raw.replace(sha_member, sha_member + b"," + sha_member, 1)
        self.assertNotEqual(raw, duplicate_sha)
        repeatability = (
            ("digest", {"raw": raw + b"  ", "expected": actual,
                        "fragments": ("digest", "sha256", "sha-256")}),
            ("closed-schema", {"value": self.changed(("repeatability_probe",), True),
                               "fragments": ("schema", "field", "keys")}),
            ("unsafe-path", {"value": self.changed(("interfaces", 0, "path"),
                                                     "repeat/../probe.py"),
                             "fragments": ("path",)}),
            ("duplicate-key", {"raw": duplicate_sha, "fragments": ("duplicate", "json")}),
        )
        for label, arguments in repeatability:
            with self.subTest(repeatability=label):
                self.reject(repeat=True, **arguments)

    def test_missing_unreadable_and_malformed_packets_are_stable_rejections(self):
        for packet in (self.root / "missing.json", self.root):
            before = self.snapshot()
            args = ("validate", "--packet", packet, "--expected-sha256", "0" * 64)
            self.assert_rejection_result(self.invoke(*args))
            self.assertEqual(before, self.snapshot())
        malformed = ((b"\xff", ("utf-8", "json")), (b"{", ("json",)),
                     (b"[]", ("schema", "object")), (b"null", ("schema", "object")),
                     (b"true", ("schema", "object")), (b"1", ("schema", "object")),
                     (b'"packet"', ("schema", "object")),
                     (b"\xef\xbb\xbf" + canonical(self.packet()), ("bom", "utf-8", "json")))
        for raw, fragments in malformed:
            self.reject(raw=raw, fragments=fragments)

    def test_duplicate_json_keys_are_rejected_at_every_object_nesting_level(self):
        raw = canonical(self.packet())
        duplicates = (
            raw.replace(b"{", b'{"schema_version":1,', 1),
            raw.replace(b'"kind":"cli"', b'"kind":"cli","kind":"cli"', 1),
            raw.replace(b'"id":314', b'"id":314,"id":314', 1),
            raw.replace(b'"outcome":"PASS"', b'"outcome":"PASS","outcome":"PASS"', 1),
        )
        for duplicate in duplicates:
            self.assertNotEqual(raw, duplicate)
            self.reject(raw=duplicate, fragments=("duplicate", "json"))

    def test_top_level_closed_schema_rejects_every_missing_and_extra_field(self):
        self.assertEqual(TOP_KEYS, set(self.packet()))
        self.closed_object(self.packet(), (), TOP_KEYS, ("packet",))

    def test_top_level_exact_values_and_types_reject_booleans_and_drift(self):
        cases = [
            ("schema", ("schema_version",), value, ("schema_version",))
            for value in (True, 1.0, "1", 2)
        ] + [
            ("handoff", ("handoff_kind",), value, ("handoff_kind",))
            for value in ("worker-to-owner", 1)
        ] + [
            ("issue", ("issue_number",), value, ("issue_number",))
            for value in (0, -1, True, 314.0, "314")
        ] + [
            ("role", ("consumer_role",), value, ("consumer_role",))
            for value in ("tester", False)
        ] + [
            ("interfaces", ("interfaces",), value, ("interface",))
            for value in ([], {}, [None])
        ] + [
            ("authorities", ("authorities",), value, ("authorit",))
            for value in ([], {}, [None])
        ] + [("prevalidation", ("reference_prevalidation",), [], ("prevalidation", "reference"))]
        for field in ("base_sha", "workflow_contract_blob_sha", "test_sha"):
            cases += [(field, (field,), value, (field, "sha"))
                      for value in ("a" * 39, "A" * 40, "g" * 40, 7, None)]
        self.reject_table(cases)

    def test_interface_objects_are_closed_for_every_kind_and_field(self):
        for kind, keys in ENTRY_KEYS.items():
            source = self.only(kind)
            self.assertEqual(keys, set(source["interfaces"][0]))
            self.closed_object(source, ("interfaces", 0), keys, (kind, "interface"))

    def test_python_interface_requires_nonempty_string_symbol_and_signature(self):
        cases = [(field, ("interfaces", 0, field), invalid, (field, "python"))
                 for field in ("symbol", "signature") for invalid in ("", 7, None, False, [])]
        self.reject_table(cases, self.only("python"))

    def test_cli_interface_enforces_argv_streams_and_exit_code_types(self):
        source = self.only("cli")
        cases = [("argv", ("interfaces", 0, "argv"), value, ("argv", "cli"))
                 for value in ([], "python", [""], [7], [True], ["python", None])]
        cases += [(field, ("interfaces", 0, field), value, (field, "cli"))
                  for field in ("stdin", "stdout", "stderr")
                  for value in ("", 7, None, False, [])]
        cases += [("exit_codes", ("interfaces", 0, "exit_codes"), value,
                   ("exit_codes", "exit code", "cli"))
                  for value in ([], "0", [True], [0.0], [-1], [256], [0, 0], [0, None])]
        self.reject_table(cases, source)

    def test_json_interface_enforces_type_and_required_key_declarations(self):
        source = self.only("json")
        cases = [("top_level_type", ("interfaces", 0, "top_level_type"), value,
                  ("top_level_type", "json")) for value in ("mapping", "OBJECT", "", 1, None, False)]
        cases += [("required_keys", ("interfaces", 0, "required_keys"), value,
                   ("required_keys", "required key", "json"))
                  for value in ([], "key", [""], [7], [True], ["name", "name"], [None])]
        self.reject_table(cases, source)
        valid_array = self.changed(("interfaces", 0, "top_level_type"), "array", source)
        valid_array["interfaces"][0]["required_keys"] = ["declared_key"]
        self.accept(valid_array)

    def test_paths_reject_absolute_empty_and_dot_segments_for_all_kinds(self):
        unsafe = ("", ".", "..", "/absolute/file.py", r"\rooted\file.py",
                  r"C:\absolute\file.py", r"C:relative.py", r"\\server\share\file.py", "dir/./file.py",
                  "dir/../file.py", "dir//file.py", "dir/", "dir\\\\file.py", "dir\\",
                  None, 7, False, [])
        for kind in ENTRY_KEYS:
            source = self.only(kind)
            for path in unsafe:
                self.reject(self.changed(("interfaces", 0, "path"), path, source), fragments=("path",))

    def test_required_kind_set_equality_and_canonical_identity_uniqueness(self):
        values = (["cli", "json", "cli"], ["cli", "json", "yaml"], [], "cli")
        cases = [self.changed(("required_interfaces",), value) for value in values]
        cases += [self.changed(("required_interfaces",), ["cli", "json", value])
                  for value in ("", None, True, 7)]
        cases += [self.changed(("interfaces",), [self.entry("cli")]),
                  self.changed(("interfaces",), [*self.packet()["interfaces"], self.entry("python")]),
                  self.changed(("interfaces",), [*self.packet()["interfaces"], {"kind": "yaml"}])]
        cases += [self.changed(("interfaces", 0, "kind"), value) for value in (None, True, 7, [])]
        for value in cases:
            self.reject(value, fragments=("required_interfaces", "interface", "kind"))
        for kind, changed_field, changed_value in (
            ("python", "signature", "validate_handoff(other, digest)"),
            ("cli", "stdout", "different declaration"),
            ("json", "required_keys", ["different_key"]),
        ):
            first, second = self.entry(kind), self.entry(kind)
            second[changed_field] = changed_value
            value = self.only(kind, first)
            value["interfaces"].append(second)
            self.reject(value, fragments=("duplicate", "identity", kind, "interface"))
        for kind, changed_field, changed_value in (
            ("python", "symbol", "validate_alternate_handoff"),
            ("cli", "argv", ["python", "tools/interface_check.py", "validate", "--strict"]),
            ("json", "top_level_type", "array"),
        ):
            first, second = self.entry(kind), self.entry(kind)
            second[changed_field] = changed_value
            value = self.only(kind, first)
            value["interfaces"].append(second)
            self.accept(value)

    def test_authorities_are_closed_typed_immutable_and_unique(self):
        source = self.packet()
        self.assertEqual(AUTHORITY_KEYS, set(source["authorities"][0]))
        self.closed_object(source, ("authorities", 0), AUTHORITY_KEYS, ("authorit",))
        cases = [(field, ("authorities", 0, field), invalid, (field, "authorit", "sha"))
                 for field, invalid in (("kind", "repository"), ("kind", 7), ("id", 0),
                                        ("id", -1), ("id", True), ("id", 314.0), ("id", "314"),
                                        ("sha256", "a" * 63), ("sha256", "A" * 64),
                                        ("sha256", "g" * 64), ("sha256", 7))]
        self.reject_table(cases, source)
        duplicate = copy.deepcopy(source["authorities"][0])
        duplicate["sha256"] = "9" * 64
        value = self.changed(("authorities",), [source["authorities"][0], duplicate], source)
        self.reject(value, fragments=("duplicate", "identity", "authorit"))
        for distinct in ({"kind": "issue_body", "id": 315, "sha256": "7" * 64},
                         {"kind": "issue_comment", "id": 314, "sha256": "8" * 64}):
            value = self.changed(("authorities",), [source["authorities"][0], distinct], source)
            self.accept(value)

    def test_prevalidation_forbidden_sources_and_unresolved_are_exact(self):
        source = self.packet()
        self.assertEqual(PREVALIDATION_KEYS, set(source["reference_prevalidation"]))
        self.closed_object(source, ("reference_prevalidation",), PREVALIDATION_KEYS,
                           ("prevalidation", "reference"))
        receipt_cases = [(field, ("reference_prevalidation", field), invalid,
                          (field, "prevalidation", "reference", "pass", "sha"))
                         for field, invalid in (("receipt_sha256", "a" * 63),
                                                ("receipt_sha256", "A" * 64),
                                                ("receipt_sha256", "g" * 64),
                                                ("receipt_sha256", 7), ("outcome", "pass"),
                                                ("outcome", "FAIL"), ("outcome", True))]
        self.reject_table(receipt_cases, source)
        forbidden = ([], ["owner_test_source"], ["owner_test_literals", "owner_test_source"],
                     ["owner_test_source", "owner_test_literals", "implementation_source"],
                     ["owner_test_source", "owner_test_source"],
                     ["OWNER_TEST_SOURCE", "owner_test_literals"], "owner_test_source", None)
        for value in forbidden:
            self.reject(self.changed(("forbidden_sources",), value), fragments=("forbidden",))
        for value in (["pending"], [None], {}, None, ""):
            self.reject(self.changed(("unresolved",), value), fragments=("unresolved",))

    def test_placeholders_match_only_trimmed_case_insensitive_whole_strings(self):
        cases = []
        for kind, field, token in (("python", "symbol", " TBD "), ("python", "signature", "todo"),
                                   ("cli", "stdin", " unknown "), ("cli", "stdout", "TBD"),
                                   ("cli", "stderr", "ToDo"),
                                   ("json", "required_keys", [" tbd "])):
            cases.append(self.changed(("interfaces", 0, field), token, self.only(kind)))
        cli = self.only("cli")
        cli["interfaces"][0]["argv"][4] = " UNKNOWN "
        cases += [cli, self.changed(("interfaces", 0, "path"), "TODO", self.only("python"))]
        for value in cases:
            self.reject(value, fragments=("placeholder",))
        self.accept(self.packet(2))

    def test_synthetic_handoff_chains_reference_packet_and_exact_guard_argv(self):
        lane = self.root / "lane"
        lane.mkdir()
        hooks = self.root / "empty-hooks"
        hooks.mkdir()
        git_environment = os.environ.copy()
        git_environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

        def git(*arguments):
            command = ["git", "-c", "commit.gpgsign=false", "-c",
                       f"core.hooksPath={hooks.resolve()}", *arguments]
            return subprocess.run(command, cwd=lane, text=True, capture_output=True,
                                  env=git_environment, timeout=10, check=True).stdout.strip()

        git("init")
        git("config", "user.email", "interface-guard@example.invalid")
        git("config", "user.name", "Interface Guard Test")
        contract = lane / "workflow-contract.json"
        contract.write_text('{"contract_version":1}\n', encoding="utf-8")
        git("add", contract.name)
        git("commit", "-m", "synthetic base")
        base, blob = git("rev-parse", "HEAD"), git("hash-object", contract.name)
        (lane / "lane.txt").write_text("worker lane\n", encoding="utf-8")
        git("add", "lane.txt")
        git("commit", "-m", "synthetic test identity")
        head = git("rev-parse", "HEAD")
        reference_raw = canonical({"schema_version": 1, "outcome": "PASS"})
        reference = lane / "reference-prevalidation.json"
        reference.write_bytes(reference_raw)
        reference_digest = hashlib.sha256(reference_raw).hexdigest()
        packet = self.packet()
        packet.update(issue_number=431, base_sha=base, workflow_contract_blob_sha=blob,
                      test_sha=head,
                      authorities=[{"kind": "issue_body", "id": 431, "sha256": "6" * 64}],
                      reference_prevalidation={"receipt_sha256": reference_digest,
                                               "outcome": "PASS"})
        packet_path = lane / "interface-handoff.json"
        packet_raw = canonical(packet)
        packet_path.write_bytes(packet_raw)
        packet_digest = hashlib.sha256(packet_raw).hexdigest()
        argv = [sys.executable, str(CHECKER), "validate", "--packet", str(packet_path),
                "--expected-sha256", packet_digest]
        manifest, receipt = self.root / "manifest.json", self.root / "receipt.json"
        events = self.root / "events.jsonl"

        def receipt_error():
            return (json.loads(receipt.read_bytes()).get("error") if receipt.is_file()
                    else "receipt was not created")

        prepared = self.guard(lane, "prepare", "--role", "worker", "--expected-top-level", lane,
                              "--base-sha", base, "--lane-sha", head, "--contract-path", contract.name,
                              "--contract-blob-sha", blob, "--timeout-seconds", 10,
                              "--manifest", manifest, "--receipt", receipt, "--event-log", events,
                              "--", *argv)
        self.assertEqual((0, b"", b""), (prepared.returncode, prepared.stdout, prepared.stderr),
                         f"#88 prepare receipt error: {receipt_error()}")
        manifest_raw = manifest.read_bytes()
        manifest_value = json.loads(manifest_raw, object_pairs_hook=unique_object)
        self.assertEqual(argv, manifest_value["argv"])
        self.assertEqual("PREPARED", json.loads(receipt.read_bytes())["outcome"])
        checked = self.guard(lane, "check-handoff", "--manifest", manifest, "--receipt", receipt,
                             "--event-log", events)
        self.assertEqual((0, b"", b""), (checked.returncode, checked.stdout, checked.stderr),
                         f"#88 check-handoff receipt error: {receipt_error()}")
        self.assertEqual("CHECKED", json.loads(receipt.read_bytes())["outcome"])
        ran = self.guard(lane, "run", "--manifest", manifest, "--receipt", receipt,
                         "--event-log", events)
        self.assertEqual((0, b""), (ran.returncode, ran.stderr))
        self.assert_pass_record(ran.stdout, packet_digest)
        records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        outcomes = [record["outcome"] for record in records]
        manifest_digest = hashlib.sha256(manifest_raw).hexdigest()
        self.assertEqual(["PREPARED", "CHECKED", "EXITED"], outcomes)
        self.assertTrue(all(record["manifest_sha256"] == manifest_digest for record in records))
        self.assertTrue(packet["reference_prevalidation"]["outcome"] == "PASS"
                        and hashlib.sha256(reference.read_bytes()).hexdigest() == reference_digest
                        and hashlib.sha256(packet_path.read_bytes()).hexdigest() == packet_digest
                        and records[-1]["exit_code"] == 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
