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
# File:        test_interface_handoff_check_generality.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-24
# Version:     0.1.0
# Description: Prove general interface-handoff completeness validation behavior.
# =================================================================================

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "agent-discipline" / "skills" / "agent-workflow" / "scripts" / "interface_handoff_check.py"
TEMP_BASE = ROOT / "tests" / ".tmp"
REJECTION_PREFIX = "interface handoff rejected: "


def complete_packet(issue_number=17):
    return {
        "schema_version": 1,
        "handoff_kind": "owner-test-to-worker",
        "issue_number": issue_number,
        "base_sha": "1" * 40,
        "workflow_contract_blob_sha": "2" * 40,
        "test_sha": "3" * 40,
        "consumer_role": "worker",
        "required_interfaces": ["python", "cli", "json"],
        "interfaces": [
            {
                "kind": "python",
                "path": "src/adapters/manifest_reader.py",
                "symbol": "read_manifest",
                "signature": "(path: str) -> dict[str, object]",
            },
            {
                "kind": "cli",
                "path": "tools\\inspect_contract.py",
                "argv": ["validate", "--packet", "<handoff.json>"],
                "stdin": "none",
                "stdout": "one compact receipt object",
                "stderr": "one rejection diagnostic",
                "exit_codes": [0, 1, 2],
            },
            {
                "kind": "json",
                "path": "schemas/interface-declaration.json",
                "top_level_type": "object",
                "required_keys": ["name", "revision"],
            },
        ],
        "authorities": [
            {"kind": "issue_body", "id": 3107, "sha256": "a" * 64},
            {"kind": "issue_comment", "id": 4129, "sha256": "b" * 64},
        ],
        "reference_prevalidation": {"receipt_sha256": "c" * 64, "outcome": "PASS"},
        "forbidden_sources": ["owner_test_source", "owner_test_literals"],
        "unresolved": [],
    }


def compact_bytes(packet):
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def interface(packet, kind):
    return next(entry for entry in packet["interfaces"] if entry["kind"] == kind)


def temporary_directory():
    TEMP_BASE.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="issue93-b-interface-", dir=TEMP_BASE)


class InterfaceHandoffCheckGeneralityTests(unittest.TestCase):
    def test_legacy_import_api_works_without_script_directory_on_sys_path(self):
        spec = importlib.util.spec_from_file_location("issue93_legacy_adapter", SCRIPT)
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        raw = compact_bytes(complete_packet(947))
        digest = hashlib.sha256(raw).hexdigest()
        with temporary_directory() as directory:
            path = Path(directory) / "packet.json"
            path.write_bytes(raw)
            packet, actual = adapter.load_packet(str(path), digest)
            self.assertEqual(digest, actual)
            self.assertIsNone(adapter.validate_packet(packet))
            self.assertEqual(set(packet), adapter.TOP_LEVEL_KEYS)
            with self.assertRaises(adapter.Rejected):
                adapter.load_packet(str(path), "f" * 64)
            with self.assertRaises(adapter.Rejected):
                adapter.validate_packet({})

    def test_unified_guard_preserves_legacy_raw_bytes_and_diagnostics(self):
        valid = compact_bytes(complete_packet(619))
        pretty = json.dumps(complete_packet(731), ensure_ascii=False, indent=2).encode()
        for raw, expected_code in ((valid, 0), (pretty, 0), (b"{}", 1),
                                   (b'{"schema_version":1,"schema_version":1}', 1),
                                   (b"\xef\xbb\xbf" + valid, 1)):
            with self.subTest(raw=raw[:40]):
                with temporary_directory() as directory:
                    path = Path(directory) / "packet.json"
                    path.write_bytes(raw)
                    results = []
                    for script, operation in ((SCRIPT, "validate"),
                                              (SCRIPT.with_name("handoff_guard.py"), "validate-interface")):
                        results.append(subprocess.run(
                            [sys.executable, str(script), operation, "--packet", str(path),
                             "--expected-sha256", hashlib.sha256(raw).hexdigest()],
                            cwd=directory, capture_output=True, text=True,
                        ))
                    legacy, unified = results
                    self.assertEqual(expected_code, legacy.returncode, legacy.stderr)
                    self.assertEqual((legacy.returncode, legacy.stdout, legacy.stderr),
                                     (unified.returncode, unified.stdout, unified.stderr))
                    self.assertEqual(raw, path.read_bytes())
                    self.assertEqual([path], list(Path(directory).iterdir()))

    def invoke_raw(self, raw, expected_sha256=None):
        with temporary_directory() as directory:
            packet_path = Path(directory) / "handoff.json"
            packet_path.write_bytes(raw)
            expected = expected_sha256 or hashlib.sha256(raw).hexdigest()
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "validate",
                    "--packet",
                    str(packet_path),
                    "--expected-sha256",
                    expected,
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )

    def invoke_packet(self, packet):
        return self.invoke_raw(compact_bytes(packet))

    def assert_pass(self, result, raw):
        expected = json.dumps(
            {
                "schema_version": 1,
                "packet_sha256": hashlib.sha256(raw).hexdigest(),
                "outcome": "PASS",
            },
            separators=(",", ":"),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected + "\n", result.stdout)
        self.assertEqual("", result.stderr)

    def assert_rejected(self, result):
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)
        self.assertEqual(1, len(result.stderr.splitlines()))
        self.assertTrue(result.stderr.startswith(REJECTION_PREFIX), result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_accepts_complete_mixed_interface_history(self):
        packet = complete_packet(17)
        raw = compact_bytes(packet)
        self.assert_pass(self.invoke_raw(raw), raw)

    def test_accepts_independent_array_json_history_and_ordinary_prose(self):
        packet = complete_packet(271)
        packet["base_sha"] = "4" * 40
        packet["workflow_contract_blob_sha"] = "5" * 40
        packet["test_sha"] = "6" * 40
        packet["required_interfaces"] = ["json"]
        packet["interfaces"] = [
            {
                "kind": "json",
                "path": "contracts\\release\\entries.json",
                "top_level_type": "array",
                "required_keys": ["todo_state", "unknown_reason"],
            },
            {
                "kind": "json",
                "path": "contracts/release/metadata.json",
                "top_level_type": "object",
                "required_keys": ["revision"],
            },
        ]
        packet["authorities"] = [
            {"kind": "issue_comment", "id": 7391, "sha256": "d" * 64}
        ]
        raw = compact_bytes(packet)
        self.assert_pass(self.invoke_raw(raw), raw)

    def test_success_is_read_only_and_reports_raw_digest(self):
        packet = complete_packet(43)
        raw = compact_bytes(packet)
        with temporary_directory() as directory:
            root = Path(directory)
            packet_path = root / "packet.json"
            packet_path.write_bytes(raw)
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "validate",
                    "--packet",
                    str(packet_path),
                    "--expected-sha256",
                    hashlib.sha256(raw).hexdigest(),
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assert_pass(result, raw)
            after = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(before, after)

    def test_rejects_invalid_expected_digest_and_digest_mismatch(self):
        raw = compact_bytes(complete_packet())
        invalid_values = ["A" * 64, "a" * 63, "g" * 64]
        for expected in invalid_values:
            with self.subTest(expected=expected):
                self.assert_rejected(self.invoke_raw(raw, expected))
        self.assert_rejected(self.invoke_raw(raw, "0" * 64))

    def test_rejects_unreadable_packet_as_contract_rejection(self):
        with temporary_directory() as directory:
            missing = Path(directory) / "missing.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "validate",
                    "--packet",
                    str(missing),
                    "--expected-sha256",
                    "e" * 64,
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assert_rejected(result)

    def test_rejects_bom_non_utf8_malformed_and_duplicate_keys(self):
        valid = compact_bytes(complete_packet())
        duplicate = valid.replace(b'"kind":"python"', b'"kind":"python","kind":"python"', 1)
        for label, raw in (
            ("bom", b"\xef\xbb\xbf" + valid),
            ("non_utf8", b"\xff"),
            ("malformed", b"{"),
            ("nested_duplicate", duplicate),
        ):
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_raw(raw))

    def test_rejects_non_object_and_nonstandard_json_constants(self):
        for label, raw in (("array", b"[]"), ("constant", b'{"schema_version":NaN}')):
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_raw(raw))

    def test_rejects_over_limit_json_integer_without_traceback(self):
        raw = b'{"schema_version":' + b"7" * 5000 + b"}"
        self.assert_rejected(self.invoke_raw(raw))

    def test_enforces_closed_top_level_and_fixed_identity_fields(self):
        mutations = []

        packet = complete_packet()
        del packet["authorities"]
        mutations.append(("missing", packet))

        packet = complete_packet()
        packet["annotation"] = "complete"
        mutations.append(("extra", packet))

        for field, value in (
            ("schema_version", True),
            ("schema_version", 2),
            ("handoff_kind", "worker-to-tester"),
            ("issue_number", True),
            ("issue_number", 0),
            ("base_sha", "A" * 40),
            ("workflow_contract_blob_sha", "f" * 39),
            ("test_sha", "z" * 40),
            ("consumer_role", "tester"),
        ):
            packet = complete_packet()
            packet[field] = value
            mutations.append((f"{field}-{value!r}", packet))

        packet = complete_packet()
        packet["forbidden_sources"] = list(reversed(packet["forbidden_sources"]))
        mutations.append(("forbidden-order", packet))

        packet = complete_packet()
        packet["unresolved"] = ["open question"]
        mutations.append(("unresolved", packet))

        for label, packet in mutations:
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_packet(packet))

    def test_enforces_required_interface_kind_set(self):
        values = [[], ["python", "python"], ["python", "rpc"], ["python", 7]]
        for required in values:
            packet = complete_packet()
            packet["required_interfaces"] = required
            with self.subTest(required=required):
                self.assert_rejected(self.invoke_packet(packet))

        packet = complete_packet()
        packet["required_interfaces"] = ["python", "cli"]
        self.assert_rejected(self.invoke_packet(packet))

        packet = complete_packet()
        packet["interfaces"] = []
        self.assert_rejected(self.invoke_packet(packet))

    def test_enforces_closed_python_declarations(self):
        mutations = []
        packet = complete_packet()
        interface(packet, "python")["return_type"] = "mapping"
        mutations.append(("extra", packet))

        packet = complete_packet()
        del interface(packet, "python")["signature"]
        mutations.append(("missing", packet))

        for field, value in (("path", ""), ("symbol", ""), ("signature", 4)):
            packet = complete_packet()
            interface(packet, "python")[field] = value
            mutations.append((field, packet))

        for label, packet in mutations:
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_packet(packet))

    def test_enforces_closed_cli_declarations(self):
        mutations = []
        packet = complete_packet()
        interface(packet, "cli")["environment"] = "clean"
        mutations.append(("extra", packet))

        packet = complete_packet()
        del interface(packet, "cli")["stderr"]
        mutations.append(("missing", packet))

        for field, value in (
            ("argv", []),
            ("argv", ["validate", ""]),
            ("stdin", ""),
            ("stdout", 9),
            ("stderr", ""),
            ("exit_codes", []),
            ("exit_codes", [0, 0]),
            ("exit_codes", [True]),
            ("exit_codes", [256]),
        ):
            packet = complete_packet()
            interface(packet, "cli")[field] = value
            mutations.append((field, packet))

        for label, packet in mutations:
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_packet(packet))

    def test_enforces_closed_json_declarations(self):
        mutations = []
        packet = complete_packet()
        interface(packet, "json")["version"] = 1
        mutations.append(("extra", packet))

        packet = complete_packet()
        del interface(packet, "json")["required_keys"]
        mutations.append(("missing", packet))

        for field, value in (
            ("top_level_type", "scalar"),
            ("required_keys", []),
            ("required_keys", ["name", "name"]),
            ("required_keys", [""]),
            ("required_keys", [3]),
        ):
            packet = complete_packet()
            interface(packet, "json")[field] = value
            mutations.append((field, packet))

        for label, packet in mutations:
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_packet(packet))

    def test_rejects_unknown_interface_kinds_and_non_string_kind(self):
        for kind in ("rpc", 3):
            packet = complete_packet()
            interface(packet, "python")["kind"] = kind
            with self.subTest(kind=kind):
                self.assert_rejected(self.invoke_packet(packet))

    def test_rejects_duplicate_canonical_interface_identities(self):
        for kind in ("python", "cli", "json"):
            packet = complete_packet()
            original = interface(packet, kind)
            duplicate = copy.deepcopy(original)
            duplicate["path"] = duplicate["path"].replace("/", "\\")
            if kind == "python":
                duplicate["signature"] = "(path: Path) -> object"
            elif kind == "cli":
                duplicate["stdout"] = "a second declaration"
            else:
                duplicate["required_keys"] = ["different"]
            packet["interfaces"].append(duplicate)
            with self.subTest(kind=kind):
                self.assert_rejected(self.invoke_packet(packet))

    def test_rejects_unsafe_repository_relative_paths(self):
        unsafe_paths = [
            "",
            "/rooted/file.py",
            "\\rooted\\file.py",
            "C:\\repo\\file.py",
            "\\\\server\\share\\file.py",
            "folder//file.py",
            "folder\\\\file.py",
            "./file.py",
            "folder/../file.py",
        ]
        for path in unsafe_paths:
            packet = complete_packet()
            interface(packet, "python")["path"] = path
            with self.subTest(path=path):
                self.assert_rejected(self.invoke_packet(packet))

    def test_rejects_placeholder_values_but_not_prose_containing_placeholder_words(self):
        for placeholder in ("TBD", " todo ", "UnKnOwN"):
            packet = complete_packet()
            interface(packet, "cli")["stdout"] = placeholder
            with self.subTest(placeholder=placeholder):
                self.assert_rejected(self.invoke_packet(packet))

        packet = complete_packet(113)
        interface(packet, "python")["signature"] = "TodoState -> UnknownResult"
        interface(packet, "cli")["stdout"] = "unknown fields remain ordinary prose"
        raw = compact_bytes(packet)
        self.assert_pass(self.invoke_raw(raw), raw)

    def test_enforces_closed_unique_authority_identities(self):
        mutations = []
        packet = complete_packet()
        packet["authorities"] = []
        mutations.append(("empty", packet))

        packet = complete_packet()
        packet["authorities"][0]["url"] = "issues/17"
        mutations.append(("extra", packet))

        packet = complete_packet()
        del packet["authorities"][0]["sha256"]
        mutations.append(("missing", packet))

        for field, value in (
            ("kind", "pull_request"),
            ("id", True),
            ("id", 0),
            ("sha256", "A" * 64),
            ("sha256", "a" * 63),
        ):
            packet = complete_packet()
            packet["authorities"][0][field] = value
            mutations.append((field, packet))

        packet = complete_packet()
        packet["authorities"].append(copy.deepcopy(packet["authorities"][0]))
        packet["authorities"][-1]["sha256"] = "e" * 64
        mutations.append(("duplicate", packet))

        for label, packet in mutations:
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_packet(packet))

    def test_enforces_closed_pass_reference_receipt_identity(self):
        mutations = []
        packet = complete_packet()
        packet["reference_prevalidation"]["note"] = "reviewed"
        mutations.append(("extra", packet))

        packet = complete_packet()
        del packet["reference_prevalidation"]["receipt_sha256"]
        mutations.append(("missing", packet))

        for field, value in (
            ("receipt_sha256", "F" * 64),
            ("receipt_sha256", "f" * 65),
            ("outcome", "FAILED"),
        ):
            packet = complete_packet()
            packet["reference_prevalidation"][field] = value
            mutations.append((field, packet))

        for label, packet in mutations:
            with self.subTest(label=label):
                self.assert_rejected(self.invoke_packet(packet))

    def test_argparse_owns_usage_errors(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--packet", "handoff.json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertTrue(result.stderr.startswith("usage:"), result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
