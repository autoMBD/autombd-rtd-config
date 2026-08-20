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
# File:        test_handoff_guard.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-20
# Version:     0.1.0
# Description: Verify exact workflow handoff validation and execution.
# =================================================================================

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
GUARD = HERE.parents[1] / "agent-discipline" / "skills" / "agent-workflow" / "scripts" / "handoff_guard.py"
TEST_TMP_PARENT = HERE.parent / ".tmp"
MANIFEST_KEYS = {
    "schema_version", "role", "git_top_level", "base_sha", "lane_sha",
    "contract_path", "contract_blob_sha", "argv", "timeout_seconds",
}
RECEIPT_KEYS = {
    "schema_version", "operation", "started_at_utc", "ended_at_utc", "cwd",
    "git_top_level", "expected_head", "actual_head", "manifest_path",
    "manifest_sha256", "argv", "timeout_seconds", "outcome", "exit_code", "error",
}


class HandoffGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._created_temp_parent = not TEST_TMP_PARENT.exists()
        TEST_TMP_PARENT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if cls._created_temp_parent:
            TEST_TMP_PARENT.rmdir()

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(dir=TEST_TMP_PARENT)
        self.root = Path(self._temp.name)
        self.assertEqual(TEST_TMP_PARENT.resolve(), self.root.resolve().parent)
        self.repo = self.root / "lane"
        self.repo.mkdir()
        self.git("init")
        self.git("config", "user.email", "guard@example.invalid")
        self.git("config", "user.name", "Guard Test")
        (self.repo / "contract.json").write_text('{"version":1}\n', encoding="utf-8")
        (self.repo / "alternate-contract.json").write_text(
            '{"version":1,"name":"alternate"}\n', encoding="utf-8"
        )
        self.git("add", "contract.json", "alternate-contract.json")
        self.git("commit", "-m", "base contracts")
        self.base = self.git("rev-parse", "HEAD")
        (self.repo / "lane.txt").write_text("lane\n", encoding="utf-8")
        self.git("add", "lane.txt")
        self.git("commit", "-m", "lane")
        self.head = self.git("rev-parse", "HEAD")
        self.blob = self.git("hash-object", "contract.json")
        self.alternate_blob = self.git("hash-object", "alternate-contract.json")
        self.manifest = self.root / "handoff.json"
        self.receipt = self.root / "receipt.json"
        self.events = self.root / "events.jsonl"
        self.sentinel = self.root / "sentinel.txt"

    def tearDown(self):
        self._temp.cleanup()

    def git(self, *args):
        result = subprocess.run(
            ["git", *args], cwd=self.repo, text=True, capture_output=True, check=True
        )
        return result.stdout.strip()

    def guard(self, *args, cwd=None, env=None):
        return subprocess.run(
            [sys.executable, str(GUARD), *map(str, args)], cwd=cwd or self.repo,
            text=True, capture_output=True, env=env,
        )

    def prepare(self, argv, **overrides):
        values = {
            "role": "worker", "expected": self.repo, "base": self.base,
            "lane": self.head, "contract": "contract.json", "blob": self.blob,
            "timeout": 10, "manifest": self.manifest, "receipt": self.receipt,
            "events": self.events,
        }
        values.update(overrides)
        return self.guard(
            "prepare", "--role", values["role"], "--expected-top-level", values["expected"],
            "--base-sha", values["base"], "--lane-sha", values["lane"],
            "--contract-path", values["contract"], "--contract-blob-sha", values["blob"],
            "--timeout-seconds", values["timeout"], "--manifest", values["manifest"],
            "--receipt", values["receipt"], "--event-log", values["events"], "--", *argv,
            cwd=overrides.get("cwd"), env=overrides.get("env"),
        )

    def write_manifest(self, manifest):
        raw = json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        self.manifest.write_bytes(raw)
        return raw

    def repin_receipt_to_manifest(self, manifest_bytes):
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        receipt["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        self.receipt.write_text(json.dumps(receipt), encoding="utf-8")

    def receipt_and_events(self):
        receipt = json.loads(self.receipt.read_text(encoding="utf-8"))
        events = [json.loads(line) for line in self.events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(RECEIPT_KEYS, set(receipt))
        self.assertEqual(receipt, events[-1])
        return receipt, events

    def assert_success_receipt(self, receipt, operation, outcome, exit_code, manifest_bytes, argv):
        started = datetime.fromisoformat(receipt["started_at_utc"].replace("Z", "+00:00"))
        ended = datetime.fromisoformat(receipt["ended_at_utc"].replace("Z", "+00:00"))
        self.assertTrue(receipt["started_at_utc"].endswith("Z"))
        self.assertTrue(receipt["ended_at_utc"].endswith("Z"))
        self.assertEqual(timezone.utc, started.tzinfo)
        self.assertEqual(timezone.utc, ended.tzinfo)
        self.assertLessEqual(started, ended)
        expected = {
            "schema_version": 1, "operation": operation, "cwd": str(self.repo.resolve()),
            "git_top_level": str(self.repo.resolve()), "expected_head": self.head,
            "actual_head": self.head, "manifest_path": str(self.manifest.resolve()),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "argv": argv,
            "timeout_seconds": 10, "outcome": outcome, "exit_code": exit_code, "error": None,
        }
        self.assertEqual(expected, {name: receipt[name] for name in expected})

    def assert_rejection_receipt(self, receipt, operation, manifest_bytes, argv, actual_head):
        expected = {
            "operation": operation, "cwd": str(self.repo.resolve()),
            "git_top_level": str(self.repo.resolve()), "expected_head": self.head,
            "actual_head": actual_head, "manifest_path": str(self.manifest.resolve()),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "argv": argv,
            "timeout_seconds": 10, "outcome": "REJECTED", "exit_code": 1,
        }
        self.assertEqual(expected, {name: receipt[name] for name in expected})
        self.assertIsInstance(receipt["error"], str)
        self.assertTrue(receipt["error"])

    def counting_command(self, *extra):
        code = (
            "from pathlib import Path; import sys; p=Path(sys.argv[1]); "
            "p.write_text(str(int(p.read_text())+1) if p.exists() else '1', encoding='utf-8')"
        )
        return [sys.executable, "-c", code, str(self.sentinel), *extra]

    def test_temporary_root_is_direct_child_of_canonical_tests_tmp(self):
        self.assertEqual(TEST_TMP_PARENT.resolve(), self.root.resolve().parent)

    def test_valid_prepare_check_run_executes_exact_argv_once(self):
        argv = self.counting_command()
        (self.repo / "untracked.txt").write_text("dirty is allowed", encoding="utf-8")
        prepared = self.prepare(argv)
        self.assertEqual(0, prepared.returncode, prepared.stderr)
        manifest_bytes = self.manifest.read_bytes()
        manifest = json.loads(manifest_bytes)
        self.assertEqual(MANIFEST_KEYS, set(manifest))
        self.assertEqual(argv, manifest["argv"])
        self.assertEqual(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(),
            manifest_bytes,
        )
        receipt, events = self.receipt_and_events()
        self.assertEqual(("prepare", "PREPARED", 0, 1),
                         (receipt["operation"], receipt["outcome"], receipt["exit_code"], len(events)))
        self.assert_success_receipt(receipt, "prepare", "PREPARED", 0, manifest_bytes, argv)

        checked = self.guard("check-handoff", "--manifest", self.manifest,
                             "--receipt", self.receipt, "--event-log", self.events)
        self.assertEqual(0, checked.returncode, checked.stderr)
        receipt, events = self.receipt_and_events()
        self.assertEqual(("check-handoff", "CHECKED", 0, 2),
                         (receipt["operation"], receipt["outcome"], receipt["exit_code"], len(events)))
        self.assert_success_receipt(receipt, "check-handoff", "CHECKED", 0, manifest_bytes, argv)

        ran = self.guard("run", "--manifest", self.manifest,
                         "--receipt", self.receipt, "--event-log", self.events)
        self.assertEqual(0, ran.returncode, ran.stderr)
        receipt, events = self.receipt_and_events()
        self.assertEqual(("run", "EXITED", 0, 3),
                         (receipt["operation"], receipt["outcome"], receipt["exit_code"], len(events)))
        self.assert_success_receipt(receipt, "run", "EXITED", 0, manifest_bytes, argv)
        self.assertEqual("1", self.sentinel.read_text(encoding="utf-8"))

    def test_wrong_cwd_rejects_before_spawn(self):
        self.assertEqual(0, self.prepare(self.counting_command()).returncode)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events, cwd=self.root)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        self.assertEqual("REJECTED", self.receipt_and_events()[0]["outcome"])

    def test_wrong_head_rejects_prepare_before_spawn(self):
        result = self.prepare(self.counting_command(), lane="0" * 40)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(self.sentinel.exists())
        self.assertEqual("REJECTED", self.receipt_and_events()[0]["outcome"])

    def test_nonexistent_and_nonancestor_bases_reject_every_operation_before_spawn(self):
        unrelated = self.git(
            "commit-tree", self.git("rev-parse", "HEAD^{tree}"), "-m", "unrelated root"
        )
        invalid_bases = {
            "nonexistent": "f" * 40,
            "existing-noncommit": self.blob,
            "existing-nonancestor": unrelated,
        }
        for label, invalid_base in invalid_bases.items():
            for operation in ("prepare", "check-handoff", "run"):
                with self.subTest(base=label, operation=operation):
                    self.sentinel.unlink(missing_ok=True)
                    argv = self.counting_command()
                    if operation == "prepare":
                        result = self.prepare(argv, base=invalid_base)
                    else:
                        self.assertEqual(0, self.prepare(argv).returncode)
                        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
                        manifest["base_sha"] = invalid_base
                        manifest_bytes = self.write_manifest(manifest)
                        self.repin_receipt_to_manifest(manifest_bytes)
                        result = self.guard(
                            operation, "--manifest", self.manifest,
                            "--receipt", self.receipt, "--event-log", self.events,
                        )
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertFalse(self.sentinel.exists())
                    self.assertEqual("REJECTED", self.receipt_and_events()[0]["outcome"])

    def test_prepared_manifest_hash_rejects_every_legal_manifest_rewrite_before_spawn(self):
        mutations = {
            "role": lambda manifest: manifest.update(role="tester"),
            "base": lambda manifest: manifest.update(base_sha=self.head),
            "contract": lambda manifest: manifest.update(
                contract_path="alternate-contract.json",
                contract_blob_sha=self.alternate_blob,
            ),
            "argv": lambda manifest: manifest.update(argv=self.counting_command("literal")),
            "timeout": lambda manifest: manifest.update(timeout_seconds=11),
        }
        for field, mutate in mutations.items():
            for operation in ("check-handoff", "run"):
                with self.subTest(field=field, operation=operation):
                    self.sentinel.unlink(missing_ok=True)
                    argv = self.counting_command()
                    self.assertEqual(0, self.prepare(argv).returncode)
                    manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
                    mutate(manifest)
                    self.write_manifest(manifest)
                    result = self.guard(
                        operation, "--manifest", self.manifest,
                        "--receipt", self.receipt, "--event-log", self.events,
                    )
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertFalse(self.sentinel.exists())
                    self.assertEqual("REJECTED", self.receipt_and_events()[0]["outcome"])

    def test_stale_manifest_after_new_commit_rejects_before_spawn(self):
        argv = self.counting_command()
        self.assertEqual(0, self.prepare(argv).returncode)
        manifest_bytes = self.manifest.read_bytes()
        (self.repo / "later.txt").write_text("later", encoding="utf-8")
        self.git("add", "later.txt")
        self.git("commit", "-m", "later")
        actual_head = self.git("rev-parse", "HEAD")
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        receipt, _ = self.receipt_and_events()
        self.assert_rejection_receipt(receipt, "run", manifest_bytes, argv, actual_head)

    def test_check_handoff_rejects_changed_contract_blob(self):
        argv = self.counting_command()
        self.assertEqual(0, self.prepare(argv).returncode)
        manifest_bytes = self.manifest.read_bytes()
        (self.repo / "contract.json").write_text('{"version":2}\n', encoding="utf-8")
        result = self.guard("check-handoff", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        receipt, events = self.receipt_and_events()
        self.assertEqual(("check-handoff", "REJECTED", 1, 2),
                         (receipt["operation"], receipt["outcome"], receipt["exit_code"], len(events)))
        self.assert_rejection_receipt(receipt, "check-handoff", manifest_bytes, argv, self.head)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        receipt, events = self.receipt_and_events()
        self.assertEqual(3, len(events))
        self.assert_rejection_receipt(receipt, "run", manifest_bytes, argv, self.head)

    def test_cwd_fake_git_is_never_invoked(self):
        marker = self.root / "fake-git-invoked.txt"
        if os.name == "nt":
            shutil.copy2(sys.executable, self.repo / "git.exe")
            (self.repo / "rev-parse").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('invoked')\n",
                encoding="utf-8",
            )
        else:
            fake = self.repo / "git"
            fake.write_text(
                f"#!{sys.executable}\nfrom pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('invoked')\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = os.pathsep + "." + os.pathsep + env.get("PATH", "")
        result = self.prepare(self.counting_command(), env=env)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(marker.exists())

    def test_manifest_and_receipt_same_path_rejects_without_writes(self):
        shared = self.root / "shared.json"
        contract_before = (self.repo / "contract.json").read_bytes()
        result = self.prepare(self.counting_command(), manifest=shared, receipt=shared)
        self.assertEqual(1, result.returncode)
        self.assertFalse(shared.exists())
        self.assertFalse(self.events.exists())
        self.assertFalse(self.sentinel.exists())
        self.assertEqual(contract_before, (self.repo / "contract.json").read_bytes())

    @unittest.skipUnless(os.name == "nt", "Win32 trailing-dot alias semantics")
    def test_windows_trailing_dot_alias_rejects_without_writes(self):
        aliased_receipt = self.root / "handoff.json."
        contract_before = (self.repo / "contract.json").read_bytes()
        result = self.prepare(self.counting_command(), receipt=aliased_receipt)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(aliased_receipt.exists())
        self.assertFalse(self.events.exists())
        self.assertFalse(self.sentinel.exists())
        self.assertEqual(contract_before, (self.repo / "contract.json").read_bytes())

    def test_receipt_and_event_log_same_path_rejects_without_writes(self):
        shared = self.root / "evidence.json"
        contract_before = (self.repo / "contract.json").read_bytes()
        result = self.prepare(self.counting_command(), receipt=shared, events=shared)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.manifest.exists())
        self.assertFalse(shared.exists())
        self.assertFalse(self.sentinel.exists())
        self.assertEqual(contract_before, (self.repo / "contract.json").read_bytes())

    def test_existing_hardlink_alias_to_contract_rejects_without_writes(self):
        alias = self.root / "contract-alias.json"
        try:
            os.link(self.repo / "contract.json", alias)
        except OSError as error:
            self.skipTest(f"hard links unavailable: {error}")
        contract_before = (self.repo / "contract.json").read_bytes()
        result = self.prepare(self.counting_command(), manifest=alias)
        self.assertEqual(1, result.returncode)
        self.assertEqual(contract_before, alias.read_bytes())
        self.assertEqual(contract_before, (self.repo / "contract.json").read_bytes())
        self.assertFalse(self.receipt.exists())
        self.assertFalse(self.events.exists())
        self.assertFalse(self.sentinel.exists())

    def test_duplicate_manifest_key_rejects_before_spawn(self):
        self.assertEqual(0, self.prepare(self.counting_command()).returncode)
        raw = self.manifest.read_text(encoding="utf-8")
        duplicate = json.dumps("argv") + ":" + json.dumps(self.counting_command())
        self.manifest.write_text("{" + duplicate + "," + raw[1:], encoding="utf-8")
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        receipt, events = self.receipt_and_events()
        self.assertEqual(("REJECTED", 1, 2),
                         (receipt["outcome"], receipt["exit_code"], len(events)))

    def test_extra_manifest_field_rejects_before_spawn(self):
        self.assertEqual(0, self.prepare(self.counting_command()).returncode)
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["unexpected"] = True
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        self.assertEqual("REJECTED", self.receipt_and_events()[0]["outcome"])

    def test_malformed_manifest_field_rejects_before_spawn(self):
        self.assertEqual(0, self.prepare(self.counting_command()).returncode)
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["timeout_seconds"] = True
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.sentinel.exists())
        self.assertEqual("REJECTED", self.receipt_and_events()[0]["outcome"])

    def test_timeout_returns_124_and_records_timeout(self):
        code = "from pathlib import Path; import sys,time; Path(sys.argv[1]).write_text('started'); time.sleep(5)"
        self.assertEqual(0, self.prepare([sys.executable, "-c", code, str(self.sentinel)], timeout=1).returncode)
        started = time.monotonic()
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(124, result.returncode)
        self.assertLess(time.monotonic() - started, 4)
        receipt, _ = self.receipt_and_events()
        self.assertEqual(("TIMED_OUT", 124), (receipt["outcome"], receipt["exit_code"]))

    def test_child_nonzero_exit_is_passed_through_with_evidence(self):
        argv = [sys.executable, "-c", "import sys; sys.exit(7)"]
        self.assertEqual(0, self.prepare(argv).returncode)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(7, result.returncode)
        receipt, events = self.receipt_and_events()
        self.assertEqual(("EXITED", 7, 2), (receipt["outcome"], receipt["exit_code"], len(events)))

    def test_nul_in_manifest_argv_records_exec_error_without_spawn_or_traceback(self):
        self.assertEqual(0, self.prepare(self.counting_command()).returncode)
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["argv"] = self.counting_command("\0")
        manifest_bytes = self.write_manifest(data)
        self.repin_receipt_to_manifest(manifest_bytes)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(2, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.sentinel.exists())
        receipt, events = self.receipt_and_events()
        self.assertEqual(("EXEC_ERROR", 2, 2),
                         (receipt["outcome"], receipt["exit_code"], len(events)))

    def test_unlaunchable_executable_records_exec_error_without_child_marker(self):
        self.assertEqual(0, self.prepare([str(self.sentinel)]).returncode)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(2, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.sentinel.exists())
        receipt, events = self.receipt_and_events()
        self.assertEqual(("EXEC_ERROR", 2, 2),
                         (receipt["outcome"], receipt["exit_code"], len(events)))

    def test_shell_metacharacters_are_literal_arguments(self):
        captured = self.root / "captured.json"
        side_effect = self.root / "must-not-exist.txt"
        code = "import json,sys; open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps(sys.argv[2:]))"
        literal = ["&&", "echo owned", ">", str(side_effect), "$(echo nope)"]
        argv = [sys.executable, "-c", code, str(captured), *literal]
        self.assertEqual(0, self.prepare(argv).returncode)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(literal, json.loads(captured.read_text(encoding="utf-8")))
        self.assertFalse(side_effect.exists())

    def test_evidence_failure_before_spawn_returns_2(self):
        self.assertEqual(0, self.prepare(self.counting_command()).returncode)
        bad_receipt = self.root / "receipt-directory"
        bad_receipt.mkdir()
        result = self.guard("run", "--manifest", self.manifest, "--receipt", bad_receipt,
                            "--event-log", self.events)
        self.assertEqual(2, result.returncode)
        self.assertFalse(self.sentinel.exists())

    def test_post_child_evidence_failure_does_not_relaunch(self):
        code = (
            "from pathlib import Path; import sys; s,e=map(Path,sys.argv[1:]); "
            "s.write_text(str(int(s.read_text())+1) if s.exists() else '1'); e.unlink(); e.mkdir()"
        )
        argv = [sys.executable, "-c", code, str(self.sentinel), str(self.events)]
        self.assertEqual(0, self.prepare(argv).returncode)
        result = self.guard("run", "--manifest", self.manifest, "--receipt", self.receipt,
                            "--event-log", self.events)
        self.assertEqual(2, result.returncode)
        self.assertEqual("1", self.sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
