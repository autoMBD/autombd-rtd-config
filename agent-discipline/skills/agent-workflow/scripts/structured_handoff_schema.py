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
# File:        structured_handoff_schema.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-09-06
# Version:     0.1.0
# Description: Strict schema and canonical byte validation for handoffs.
# =================================================================================

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
KEYWORDS = {"$schema", "$id", "title", "$defs", "$ref", "type", "properties",
            "required", "additionalProperties", "items", "minItems", "maxItems",
            "enum", "const", "anyOf", "oneOf", "pattern", "format", "minimum",
            "maximum", "uniqueItems", "description"}


class ProtocolError(ValueError):
    """A safe, stable rule failure, without untrusted content in diagnostics."""

    def __init__(self, rule_id, pointer="/", diagnostic="Protocol requirement not met."):
        super().__init__(diagnostic)
        self.rule_id = rule_id
        self.pointer = pointer
        self.diagnostic = diagnostic


def require(condition, rule_id, pointer="/", diagnostic="Protocol requirement not met."):
    if not condition:
        raise ProtocolError(rule_id, pointer, diagnostic)


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def parse_json(raw, expected_sha256=None, canonical=True):
    if expected_sha256 is not None:
        require(isinstance(expected_sha256, str) and
                re.fullmatch("[0-9a-f]{64}", expected_sha256), "DIGEST_SYNTAX")
        require(hashlib.sha256(raw).hexdigest() == expected_sha256, "DIGEST_MISMATCH")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_MEMBER")
            result[key] = value
        return result
    def forbidden(_):
        raise ProtocolError("JSON_NUMBER")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=forbidden, parse_float=forbidden)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolError("JSON_ENCODING") from exc
    if canonical:
        require(raw == canonical_bytes(value), "NON_CANONICAL")
    return value


def load_schema():
    return parse_json((SCHEMA_DIR / "handoff-v1.schema.json").read_bytes(), canonical=False)


def load_registry():
    return parse_json((SCHEMA_DIR / "functional-development-v1.json").read_bytes(), canonical=False)


def _format(value, name):
    if name in {"relative-path", "state-path"}:
        require(bool(value) and not any(c in value for c in "\\\x00:*?\"<>|")
                and not value.startswith("/"), "PATH_SYNTAX")
        for part in value.split("/"):
            require(part not in {"", ".", ".."} and part[-1] not in " ."
                    and not any(ord(c) < 32 for c in part), "PATH_SYNTAX")
            stem = part.split(".")[0].upper()
            require(stem not in {"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$"}
                    and not re.fullmatch(r"(COM|LPT)[1-9¹²³]", stem), "PATH_DEVICE")
        if name == "state-path":
            require(value.startswith(".agent-state/"), "STATE_PATH")
    elif name == "utc-time":
        require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", value)), "TIME_SYNTAX")
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProtocolError("TIME_SYNTAX") from exc
    elif name == "canonical-root":
        path = Path(value)
        require(path.is_absolute() and str(path.resolve()) == value, "ROOT_CANONICAL")
    else:
        raise ProtocolError("UNSUPPORTED_SCHEMA_FORMAT")


def validate_schema(value, schema, definitions, pointer="/"):
    require(not (set(schema) - KEYWORDS), "UNSUPPORTED_SCHEMA_KEYWORD", pointer)
    if "$ref" in schema:
        ref = schema["$ref"]
        require(ref.startswith("#/$defs/") and ref[8:] in definitions, "SCHEMA_REFERENCE")
        validate_schema(value, definitions[ref[8:]], definitions, pointer)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            passes = 0
            for option in schema[key]:
                try:
                    validate_schema(value, option, definitions, pointer)
                    passes += 1
                except ProtocolError as exc:
                    if exc.rule_id.startswith("UNSUPPORTED_SCHEMA"):
                        raise
            require(passes >= 1 if key == "anyOf" else passes == 1, "SCHEMA_VARIANT", pointer)
    if "type" in schema:
        checks = {"object": lambda: type(value) is dict,
                  "array": lambda: type(value) is list,
                  "string": lambda: type(value) is str,
                  "integer": lambda: type(value) is int,
                  "boolean": lambda: type(value) is bool,
                  "null": lambda: value is None}
        require(schema["type"] in checks, "UNSUPPORTED_SCHEMA_TYPE", pointer)
        require(checks[schema["type"]](), "SCHEMA_TYPE", pointer)
    if "const" in schema:
        require(type(value) is type(schema["const"]) and value == schema["const"], "SCHEMA_CONST", pointer)
    if "enum" in schema:
        require(any(type(value) is type(item) and value == item for item in schema["enum"]), "SCHEMA_ENUM", pointer)
    if type(value) is dict:
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            require(set(value) <= set(properties), "EXTRA_MEMBER", pointer)
        require(set(schema.get("required", [])) <= set(value), "MISSING_MEMBER", pointer)
        for name, sub in properties.items():
            if name in value:
                validate_schema(value[name], sub, definitions, pointer.rstrip("/") + "/" + name)
    if type(value) is list:
        require(len(value) >= schema.get("minItems", 0), "ARRAY_MINIMUM", pointer)
        require(len(value) <= schema.get("maxItems", len(value)), "ARRAY_MAXIMUM", pointer)
        if schema.get("uniqueItems"):
            require(len({canonical_bytes(x) for x in value}) == len(value), "ARRAY_DUPLICATE", pointer)
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], definitions, pointer.rstrip("/") + "/" + str(index))
    if type(value) is str:
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, "STRING_PATTERN", pointer)
        if "format" in schema:
            _format(value, schema["format"])
    if type(value) is int:
        require(value >= schema.get("minimum", value) and value <= schema.get("maximum", value), "INTEGER_RANGE", pointer)


def validate_definition(value, definition):
    schema = load_schema()
    require(definition in schema["$defs"], "SCHEMA_DEFINITION")
    validate_schema(value, schema["$defs"][definition], schema["$defs"])


def validate_artifact(value):
    require(type(value) is dict and value.get("artifact_kind") in load_registry()["artifacts"], "ARTIFACT_KIND")
    validate_definition(value, value["artifact_kind"])
