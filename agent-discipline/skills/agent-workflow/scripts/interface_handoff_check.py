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
# File:        interface_handoff_check.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-08-24
# Version:     0.1.0
# Description: Validate interface-handoff completeness and digest continuity.
# =================================================================================

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys


TOP_LEVEL_KEYS = {
    "schema_version",
    "handoff_kind",
    "issue_number",
    "base_sha",
    "workflow_contract_blob_sha",
    "test_sha",
    "consumer_role",
    "required_interfaces",
    "interfaces",
    "authorities",
    "reference_prevalidation",
    "forbidden_sources",
    "unresolved",
}
INTERFACE_KEYS = {
    "python": {"kind", "path", "symbol", "signature"},
    "cli": {"kind", "path", "argv", "stdin", "stdout", "stderr", "exit_codes"},
    "json": {"kind", "path", "top_level_type", "required_keys"},
}
AUTHORITY_KEYS = {"kind", "id", "sha256"}
REFERENCE_KEYS = {"receipt_sha256", "outcome"}
SHA40_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA64_RE = re.compile(r"[0-9a-f]{64}\Z")
PLACEHOLDERS = {"tbd", "todo", "unknown"}


class Rejected(Exception):
    """A stable interface-handoff contract rejection."""


def reject(message):
    raise Rejected(message)


def unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        reject("packet contains a duplicate object key")
    return value


def reject_json_constant(_value):
    reject("packet is not strict JSON")


def load_packet(path, expected_sha256):
    if not isinstance(expected_sha256, str) or not SHA64_RE.fullmatch(expected_sha256):
        reject("expected SHA-256 must be lowercase 64-hex")
    try:
        raw = Path(path).read_bytes()
    except (OSError, ValueError):
        reject("packet could not be read")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        reject("packet SHA-256 does not match expected digest")
    if raw.startswith(b"\xef\xbb\xbf"):
        reject("packet must be UTF-8 without BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        reject("packet is not valid UTF-8")
    try:
        packet = json.loads(
            text,
            object_pairs_hook=unique_object,
            parse_constant=reject_json_constant,
        )
    except json.JSONDecodeError:
        reject("packet is not valid JSON")
    return packet, actual_sha256


def reject_placeholders(value):
    if isinstance(value, str):
        if value.strip().casefold() in PLACEHOLDERS:
            reject("packet contains a placeholder string")
    elif isinstance(value, list):
        for item in value:
            reject_placeholders(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_placeholders(key)
            reject_placeholders(item)


def require_closed_object(value, keys, subject):
    if not isinstance(value, dict) or set(value) != keys:
        reject(f"{subject} keys do not match the closed schema")


def is_nonempty_string(value):
    return isinstance(value, str) and bool(value)


def is_sha(value, pattern):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def is_safe_relative_path(value):
    if not is_nonempty_string(value):
        return False
    if value.startswith(("/", "\\")) or PureWindowsPath(value).drive:
        return False
    parts = value.replace("\\", "/").split("/")
    return all(part not in ("", ".", "..") for part in parts)


def validate_python_interface(entry, normalized_path):
    if not is_nonempty_string(entry["symbol"]):
        reject("python symbol must be a nonempty string")
    if not is_nonempty_string(entry["signature"]):
        reject("python signature must be a nonempty string")
    return "python", normalized_path, entry["symbol"]


def validate_cli_interface(entry, normalized_path):
    argv = entry["argv"]
    if not isinstance(argv, list) or not argv or not all(is_nonempty_string(item) for item in argv):
        reject("cli argv must contain nonempty strings")
    for field in ("stdin", "stdout", "stderr"):
        if not is_nonempty_string(entry[field]):
            reject(f"cli {field} must be a nonempty string")
    exit_codes = entry["exit_codes"]
    if (
        not isinstance(exit_codes, list)
        or not exit_codes
        or not all(type(code) is int and 0 <= code <= 255 for code in exit_codes)
        or len(exit_codes) != len(set(exit_codes))
    ):
        reject("cli exit_codes must contain unique integers in 0..255")
    return "cli", normalized_path, tuple(argv)


def validate_json_interface(entry, normalized_path):
    if entry["top_level_type"] not in ("object", "array"):
        reject("json top_level_type must be object or array")
    required_keys = entry["required_keys"]
    if (
        not isinstance(required_keys, list)
        or not required_keys
        or not all(is_nonempty_string(key) for key in required_keys)
        or len(required_keys) != len(set(required_keys))
    ):
        reject("json required_keys must contain unique nonempty strings")
    return "json", normalized_path, entry["top_level_type"]


def validate_interfaces(packet):
    required = packet["required_interfaces"]
    if (
        not isinstance(required, list)
        or not required
        or not all(isinstance(kind, str) and kind in INTERFACE_KEYS for kind in required)
        or len(required) != len(set(required))
    ):
        reject("required_interfaces must be a nonempty unique subset of python, cli, json")

    interfaces = packet["interfaces"]
    if not isinstance(interfaces, list) or not interfaces:
        reject("interfaces must be a nonempty list")

    identities = set()
    declared_kinds = set()
    validators = {
        "python": validate_python_interface,
        "cli": validate_cli_interface,
        "json": validate_json_interface,
    }
    for entry in interfaces:
        if not isinstance(entry, dict):
            reject("each interface must be an object")
        kind = entry.get("kind")
        if not isinstance(kind, str) or kind not in INTERFACE_KEYS:
            reject("interface kind must be python, cli, or json")
        require_closed_object(entry, INTERFACE_KEYS[kind], f"{kind} interface")
        if not is_safe_relative_path(entry["path"]):
            reject("interface path must be a safe repository-relative path")
        normalized_path = entry["path"].replace("\\", "/")
        identity = validators[kind](entry, normalized_path)
        if identity in identities:
            reject("interface identities must be unique")
        identities.add(identity)
        declared_kinds.add(kind)
    if declared_kinds != set(required):
        reject("interface kinds must equal required_interfaces")


def validate_authorities(authorities):
    if not isinstance(authorities, list) or not authorities:
        reject("authorities must be a nonempty list")
    identities = set()
    for authority in authorities:
        require_closed_object(authority, AUTHORITY_KEYS, "authority")
        if authority["kind"] not in ("issue_body", "issue_comment"):
            reject("authority kind must be issue_body or issue_comment")
        if type(authority["id"]) is not int or authority["id"] <= 0:
            reject("authority id must be a positive integer")
        if not is_sha(authority["sha256"], SHA64_RE):
            reject("authority sha256 must be lowercase 64-hex")
        identity = authority["kind"], authority["id"]
        if identity in identities:
            reject("authority identities must be unique")
        identities.add(identity)


def validate_reference_prevalidation(value):
    require_closed_object(value, REFERENCE_KEYS, "reference_prevalidation")
    if not is_sha(value["receipt_sha256"], SHA64_RE):
        reject("reference receipt_sha256 must be lowercase 64-hex")
    if value["outcome"] != "PASS":
        reject("reference prevalidation outcome must be PASS")


def validate_packet(packet):
    require_closed_object(packet, TOP_LEVEL_KEYS, "packet")
    reject_placeholders(packet)
    if type(packet["schema_version"]) is not int or packet["schema_version"] != 1:
        reject("schema_version must be integer 1")
    if packet["handoff_kind"] != "owner-test-to-worker":
        reject("handoff_kind must be owner-test-to-worker")
    if type(packet["issue_number"]) is not int or packet["issue_number"] <= 0:
        reject("issue_number must be a positive integer")
    for field in ("base_sha", "workflow_contract_blob_sha", "test_sha"):
        if not is_sha(packet[field], SHA40_RE):
            reject(f"{field} must be a lowercase full SHA")
    if packet["consumer_role"] != "worker":
        reject("consumer_role must be worker")
    validate_interfaces(packet)
    validate_authorities(packet["authorities"])
    validate_reference_prevalidation(packet["reference_prevalidation"])
    if packet["forbidden_sources"] != ["owner_test_source", "owner_test_literals"]:
        reject("forbidden_sources must match the closed ordered declaration")
    if packet["unresolved"] != []:
        reject("unresolved must be an empty list")


def parse_args():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="operation", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--packet", required=True)
    validate.add_argument("--expected-sha256", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        packet, packet_sha256 = load_packet(args.packet, args.expected_sha256)
        validate_packet(packet)
    except Rejected as failure:
        print(f"interface handoff rejected: {failure}", file=sys.stderr)
        return 1
    except RecursionError:
        print("interface handoff rejected: packet nesting is too deep", file=sys.stderr)
        return 1
    receipt = {"schema_version": 1, "packet_sha256": packet_sha256, "outcome": "PASS"}
    print(json.dumps(receipt, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
