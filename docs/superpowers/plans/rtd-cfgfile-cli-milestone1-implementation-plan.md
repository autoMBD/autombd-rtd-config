# RTD CfgFile CLI Milestone 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Milestone 1 RTD CfgFile CLI path for S32K3 RTD 7.0.1 `.mex` projects, validated first on the S32K344 Uart fixture.

**Architecture:** Implement a Python CLI with a modular configuration core, S32 ConfigTools `.mex` backend document core, prepared runtime assets, module providers for `Mcu`, `BaseNXP`, `Platform`, `Port`, `Dio`, `Mcl`, and `Uart`, and a runtime verification pipeline. Keep JSON intent as the stable request contract; shortcut commands normalize into the same plan/apply/check/validate pipeline.

**Tech Stack:** Python 3 standard library first, `pytest` for development testing, S32DS/S32 ConfigTools headless validation through the configured local vendor tool environment, JSON runtime assets, XML parsing through `xml.etree.ElementTree` unless measurement proves another parser is required.

| Field | Value |
| --- | --- |
| Version | 0.1.1 |
| Date | 2026-06-02 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Executable Milestone 1 implementation plan for RTD CfgFile CLI. |

---

## Scope

Milestone 1 implements only the mandatory minimum test set from `docs/superpowers/tests/rtd-config-test-strategy.md`:

- `RTD-M1-MIN-001`: inspect existing complete S32K344 Uart fixture;
- `RTD-M1-MIN-002`: configure one LPUART Uart channel in polling mode;
- `RTD-M1-MIN-003`: configure one LPUART Uart channel in interrupt mode;
- `RTD-M1-MIN-004`: configure one FlexIO-backed Uart channel in polling mode;
- `RTD-M1-MIN-005`: configure one FlexIO-backed Uart channel in interrupt mode;
- `RTD-M1-MIN-006`: query generic pin options before Uart pin assignment;
- `RTD-M1-MIN-007`: E2E minimal LPUART stack;
- `RTD-M1-MIN-008`: E2E minimal FlexIO Uart stack.

Milestone 1 does not implement DMA, `.mex` creation from scratch, missing-module completion, EB tresos, K1/K5 validation, runtime Excel parsing, or runtime RTD installation scans.

## Current Fixture

```text
fixtures/
  mex/
    s32k3/
      s32k344/
        uart/
          projects/
            Uart_Example_S32K344/
```

The fixture is a real S32DS/S32 ConfigTools project. Implementation tasks must copy this fixture into a temporary test workspace before applying configuration edits.

## Planned File Structure

```text
pyproject.toml
rtd_config/
  __init__.py
  __main__.py
  cli.py
  config.py
  diagnostics.py
  intent.py
  plan.py
  project.py
  timing.py
  backends/
    __init__.py
    base.py
    s32_mex/
      __init__.py
      document.py
      locate.py
      static_check.py
      validation.py
  checks/
    __init__.py
    static.py
  modules/
    __init__.py
    base.py
    mcu.py
    basenxp.py
    platform.py
    port.py
    dio.py
    mcl.py
    uart.py
  resources/
    __init__.py
    pins.py
    runtime.py
data/
  s32k/
    families/
      s32k3/
        devices/
          s32k344/
            packages/
              default/
                pins.json
            rtd/
              7_0_1/
                modules.json
                validation_profiles.json
tests/
  conftest.py
  fixtures.py
  unit/
  integration/
  e2e/
.skills/
  rtd-config/
    SKILL.md
```

## Execution Rules

- Use TDD for each implementation task: write a failing test, run it, implement the minimal behavior, rerun it, commit.
- Do not edit the checked-in fixture in place during tests. Copy it to a temporary test directory.
- Runtime commands must not read Excel workbooks or raw RTD `.xdm` descriptors.
- `configure` modifies projects in place by default and supports optional `--backup`.
- `inspect`, `plan`, `check`, and `pin-options` must not launch vendor tools.
- `validate` may launch the configured vendor validation tool without a visible GUI window.
- Advanced tests are not part of this plan unless the user explicitly adds them.
- `.mex` document editing and M1 provider implementation must use and comply
  with `docs/superpowers/specs/rtd-config-m1-legacy-skills-experience.md`.

---

### Task 1: Project Skeleton And CLI Smoke Test

**Files:**
- Create: `pyproject.toml`
- Create: `rtd_config/__init__.py`
- Create: `rtd_config/__main__.py`
- Create: `rtd_config/cli.py`
- Create: `tests/unit/test_cli_smoke.py`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
# tests/unit/test_cli_smoke.py
import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "rtd_config", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_cli_version_returns_json():
    result = run_cli("--version", "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["command"] == "version"
    assert payload["tool"] == "RTD CfgFile CLI"
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/unit/test_cli_smoke.py -q
```

Expected: FAIL because `rtd_config` does not exist.

- [ ] **Step 3: Add packaging and minimal CLI**

```toml
# pyproject.toml
[project]
name = "rtd-cfgfile-cli"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
rtd-config = "rtd_config.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

```python
# rtd_config/__init__.py
__version__ = "0.1.0"
```

```python
# rtd_config/__main__.py
from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

```python
# rtd_config/cli.py
from __future__ import annotations

import argparse
import json
from . import __version__


def emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rtd-config")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        return emit({
            "status": "passed",
            "command": "version",
            "tool": "RTD CfgFile CLI",
            "version": __version__,
        })
    parser.print_help()
    return 0
```

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
pytest tests/unit/test_cli_smoke.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml rtd_config tests/unit/test_cli_smoke.py
git commit -m "Add RTD CfgFile CLI skeleton"
```

---

### Task 2: Stable Diagnostics And Runtime Configuration

**Files:**
- Create: `rtd_config/diagnostics.py`
- Create: `rtd_config/config.py`
- Create: `tests/unit/test_diagnostics.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write diagnostics tests**

```python
# tests/unit/test_diagnostics.py
from rtd_config.diagnostics import Diagnostic, Result


def test_result_serializes_stable_json_shape():
    result = Result(
        status="blocked",
        command="plan",
        diagnostics=[
            Diagnostic(
                severity="blocker",
                code="missing_pin_mapping",
                module="port",
                message="Pin PTA15 is not available.",
                details={"pin": "PTA15"},
            )
        ],
    )
    payload = result.to_dict()
    assert payload["status"] == "blocked"
    assert payload["diagnostics"][0]["code"] == "missing_pin_mapping"
    assert payload["diagnostics"][0]["details"]["pin"] == "PTA15"
```

```python
# tests/unit/test_config.py
from pathlib import Path
from rtd_config.config import RuntimeConfig


def test_runtime_config_defaults_to_repo_data_dir(tmp_path):
    config = RuntimeConfig.from_dict({"project": str(tmp_path)})
    assert config.project == tmp_path
    assert config.family == "s32k3"
    assert config.device == "s32k344"
    assert config.rtd_version == "7_0_1"
    assert config.data_root == Path("data")
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest tests/unit/test_diagnostics.py tests/unit/test_config.py -q
```

Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement diagnostics and config**

```python
# rtd_config/diagnostics.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["blocker", "error", "warning", "info"]
Status = Literal["passed", "failed", "blocked"]


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    module: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "module": self.module,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True)
class Result:
    status: Status
    command: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "command": self.command,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
        payload.update(self.data)
        return payload
```

```python
# rtd_config/config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeConfig:
    project: Path
    backend: str = "mex"
    family: str = "s32k3"
    device: str = "s32k344"
    package: str = "default"
    rtd_version: str = "7_0_1"
    data_root: Path = Path("data")
    validation_timeout_s: int = 180

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuntimeConfig":
        values = dict(raw)
        values["project"] = Path(values["project"])
        if "data_root" in values:
            values["data_root"] = Path(values["data_root"])
        return cls(**values)
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```powershell
pytest tests/unit/test_diagnostics.py tests/unit/test_config.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/diagnostics.py rtd_config/config.py tests/unit/test_diagnostics.py tests/unit/test_config.py
git commit -m "Add diagnostics and runtime config"
```

---

### Task 3: Fixture Copy Helper And MEX Project Locator

**Files:**
- Create: `tests/fixtures.py`
- Create: `tests/conftest.py`
- Create: `rtd_config/project.py`
- Create: `rtd_config/backends/s32_mex/locate.py`
- Create: `tests/unit/test_project_locator.py`

- [ ] **Step 1: Write failing fixture and locator tests**

```python
# tests/unit/test_project_locator.py
from pathlib import Path

from rtd_config.backends.s32_mex.locate import find_single_mex
from tests.fixtures import copy_uart_fixture


def test_copy_uart_fixture_creates_isolated_project(tmp_path):
    project = copy_uart_fixture(tmp_path)
    assert project.exists()
    assert (project / "Uart_Example.mex").exists()
    assert "fixtures" not in str(project)


def test_find_single_mex_returns_project_mex(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = find_single_mex(project)
    assert mex == project / "Uart_Example.mex"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest tests/unit/test_project_locator.py -q
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 3: Implement fixture helper and MEX locator**

```python
# tests/fixtures.py
from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UART_FIXTURE = REPO_ROOT / "fixtures" / "mex" / "s32k3" / "s32k344" / "uart" / "projects" / "Uart_Example_S32K344"


def copy_uart_fixture(tmp_path: Path) -> Path:
    target = tmp_path / "Uart_Example_S32K344"
    shutil.copytree(UART_FIXTURE, target)
    return target
```

```python
# tests/conftest.py
from __future__ import annotations
```

```python
# rtd_config/project.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    root: Path
    backend: str
    mex_file: Path
```

```python
# rtd_config/backends/s32_mex/locate.py
from __future__ import annotations

from pathlib import Path


def find_single_mex(project: Path) -> Path:
    matches = sorted(project.glob("*.mex"))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one .mex in {project}, found {len(matches)}")
    return matches[0]
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```powershell
pytest tests/unit/test_project_locator.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add tests/fixtures.py tests/conftest.py rtd_config/project.py rtd_config/backends tests/unit/test_project_locator.py
git commit -m "Add fixture copy helper and MEX locator"
```

---

### Task 4: S32 MEX Document Core

**Files:**
- Create: `rtd_config/backends/base.py`
- Create: `rtd_config/backends/s32_mex/document.py`
- Create: `tests/unit/test_mex_document.py`

- [ ] **Step 1: Write failing document tests**

```python
# tests/unit/test_mex_document.py
from rtd_config.backends.s32_mex.document import MexDocument
from tests.fixtures import copy_uart_fixture


def test_mex_document_loads_and_detects_enabled_instances(tmp_path):
    project = copy_uart_fixture(tmp_path)
    doc = MexDocument.load(project / "Uart_Example.mex")
    instances = doc.enabled_instance_names()
    assert "Mcu" in instances
    assert "BaseNXP" in instances
    assert "Platform" in instances
    assert "Port" in instances
    assert "Dio" in instances
    assert "Mcl" in instances
    assert "Uart" in instances


def test_mex_document_write_preserves_xml_well_formedness(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    doc.write(mex)
    MexDocument.load(mex)


def test_mex_document_removes_quick_selection_from_modified_element(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    doc = MexDocument.load(mex)
    element = doc.find_first_with_attribute("quick_selection")
    assert element is not None

    doc.mark_modified(element)

    assert "quick_selection" not in element.attrib
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest tests/unit/test_mex_document.py -q
```

Expected: FAIL because `MexDocument` does not exist.

- [ ] **Step 3: Implement document load/index/write**

```python
# rtd_config/backends/base.py
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class BackendDocument(Protocol):
    path: Path

    def mark_modified(self, element: object) -> None:
        ...

    def write(self, path: Path | None = None) -> None:
        ...
```

```python
# rtd_config/backends/s32_mex/document.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass
class MexDocument:
    path: Path
    tree: ET.ElementTree

    @classmethod
    def load(cls, path: Path) -> "MexDocument":
        return cls(path=path, tree=ET.parse(path))

    @property
    def root(self) -> ET.Element:
        return self.tree.getroot()

    def enabled_instance_names(self) -> set[str]:
        names: set[str] = set()
        for element in self.root.iter():
            if element.tag.endswith("instance") and element.attrib.get("enabled", "true") != "false":
                name = element.attrib.get("name")
                if name:
                    names.add(name)
        return names

    def find_first_with_attribute(self, attribute: str) -> ET.Element | None:
        for element in self.root.iter():
            if attribute in element.attrib:
                return element
        return None

    def mark_modified(self, element: ET.Element) -> None:
        element.attrib.pop("quick_selection", None)

    def write(self, path: Path | None = None) -> None:
        target = path or self.path
        self.tree.write(target, encoding="utf-8", xml_declaration=True)
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```powershell
pytest tests/unit/test_mex_document.py -q
```

Expected: all document tests pass, including quick-selection removal.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/backends/base.py rtd_config/backends/s32_mex/document.py tests/unit/test_mex_document.py
git commit -m "Add S32 MEX document core"
```

---

### Task 5: Runtime Assets And Pin Options

**Files:**
- Create: `data/s32k/families/s32k3/devices/s32k344/packages/default/pins.json`
- Create: `rtd_config/resources/runtime.py`
- Create: `rtd_config/resources/pins.py`
- Modify: `rtd_config/cli.py`
- Create: `tests/unit/test_pin_options.py`

- [ ] **Step 1: Write failing pin-options tests**

```python
# tests/unit/test_pin_options.py
import json
import subprocess
import sys


def test_pin_options_returns_runtime_data_without_vendor_launch():
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "pin-options",
            "--device", "s32k344",
            "--package", "default",
            "--peripheral", "LPUART_0",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["command"] == "pin-options"
    assert any(item["peripheral"] == "LPUART_0" for item in payload["options"])
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/unit/test_pin_options.py -q
```

Expected: FAIL because command/resources do not exist.

- [ ] **Step 3: Add minimal prepared runtime pin data**

Use pins observed from the real S32K344 Uart fixture. Do not load Excel at runtime.

```json
{
  "family": "s32k3",
  "device": "s32k344",
  "package": "default",
  "signals": [
    {
      "peripheral": "LPUART_0",
      "signal": "TX",
      "pin": "PTA15",
      "mux": "LPUART_0_TX",
      "direction": "output"
    },
    {
      "peripheral": "LPUART_0",
      "signal": "RX",
      "pin": "PTA16",
      "mux": "LPUART_0_RX",
      "direction": "input"
    },
    {
      "peripheral": "FLEXIO_0",
      "signal": "TX",
      "pin": "PTB0",
      "mux": "FLEXIO_0_D0",
      "direction": "output"
    },
    {
      "peripheral": "FLEXIO_0",
      "signal": "RX",
      "pin": "PTB1",
      "mux": "FLEXIO_0_D1",
      "direction": "input"
    }
  ]
}
```

- [ ] **Step 4: Implement runtime resource loader and command**

```python
# rtd_config/resources/runtime.py
from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
```

```python
# rtd_config/resources/pins.py
from __future__ import annotations

from pathlib import Path
from .runtime import load_json


def pin_options(data_root: Path, device: str, package: str, peripheral: str) -> list[dict]:
    path = data_root / "s32k" / "families" / "s32k3" / "devices" / device / "packages" / package / "pins.json"
    data = load_json(path)
    return [item for item in data["signals"] if item["peripheral"] == peripheral]
```

Extend `rtd_config/cli.py` with a `pin-options` subcommand that returns:

```json
{
  "status": "passed",
  "command": "pin-options",
  "options": []
}
```

- [ ] **Step 5: Run test and confirm pass**

Run:

```powershell
pytest tests/unit/test_pin_options.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```powershell
git add data rtd_config/resources rtd_config/cli.py tests/unit/test_pin_options.py
git commit -m "Add runtime pin options"
```

---

### Task 6: Inspect Command

**Files:**
- Modify: `rtd_config/cli.py`
- Create: `rtd_config/backends/s32_mex/static_check.py`
- Create: `tests/integration/test_inspect_uart_fixture.py`

- [ ] **Step 1: Write failing inspect test**

```python
# tests/integration/test_inspect_uart_fixture.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_inspect_uart_fixture_reports_modules_and_backend(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "inspect", "--project", str(project), "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["backend"] == "mex"
    assert payload["family"] == "s32k3"
    assert payload["device"] == "s32k344"
    assert "Uart" in payload["modules"]
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/integration/test_inspect_uart_fixture.py -q
```

Expected: FAIL because `inspect` is not implemented.

- [ ] **Step 3: Implement inspect**

Implement `inspect --project <path> --json` by locating the `.mex`, loading `MexDocument`, and returning backend, default family/device/rtd version, module list, and validation profile.

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
pytest tests/integration/test_inspect_uart_fixture.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/cli.py rtd_config/backends/s32_mex/static_check.py tests/integration/test_inspect_uart_fixture.py
git commit -m "Add inspect command for MEX fixtures"
```

---

### Task 7: Intent, Plan Model, And Provider Interface

**Files:**
- Create: `rtd_config/intent.py`
- Create: `rtd_config/plan.py`
- Create: `rtd_config/modules/base.py`
- Create: `tests/unit/test_intent_plan.py`

- [ ] **Step 1: Write failing intent/plan tests**

```python
# tests/unit/test_intent_plan.py
from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


def test_intent_loads_module_action_payload():
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {"hw": "LPUART_0", "mode": "polling"},
    })
    assert intent.module == "uart"
    assert intent.action == "set"
    assert intent.payload["mode"] == "polling"


def test_plan_records_owned_changes():
    plan = Plan(changes=[
        PlannedChange(module="uart", owner="uart", path="/Uart", description="Set channel")
    ])
    assert plan.to_dict()["changes"][0]["owner"] == "uart"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
pytest tests/unit/test_intent_plan.py -q
```

Expected: FAIL because intent/plan models do not exist.

- [ ] **Step 3: Implement intent and plan models**

```python
# rtd_config/intent.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Intent:
    module: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Intent":
        return cls(module=raw["module"], action=raw["action"], payload=dict(raw.get("payload", {})))
```

```python
# rtd_config/plan.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlannedChange:
    module: str
    owner: str
    path: str
    description: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass(frozen=True)
class Plan:
    changes: list[PlannedChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"changes": [change.to_dict() for change in self.changes]}
```

```python
# rtd_config/modules/base.py
from __future__ import annotations

from typing import Protocol
from rtd_config.intent import Intent
from rtd_config.plan import Plan


class ModuleProvider(Protocol):
    name: str

    def plan(self, intent: Intent) -> Plan:
        ...
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```powershell
pytest tests/unit/test_intent_plan.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/intent.py rtd_config/plan.py rtd_config/modules/base.py tests/unit/test_intent_plan.py
git commit -m "Add intent and plan models"
```

---

### Task 8: Minimal Module Providers

**Files:**
- Create: `rtd_config/modules/mcu.py`
- Create: `rtd_config/modules/basenxp.py`
- Create: `rtd_config/modules/dio.py`
- Create: `rtd_config/modules/platform.py`
- Create: `rtd_config/modules/port.py`
- Create: `rtd_config/modules/mcl.py`
- Create: `rtd_config/modules/uart.py`
- Create: `tests/unit/test_module_providers.py`

- [ ] **Step 1: Write failing provider ownership tests**

```python
# tests/unit/test_module_providers.py
from rtd_config.intent import Intent
from rtd_config.modules.uart import UartProvider


def test_uart_plan_declares_dependencies_without_owning_other_modules():
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {
            "hw": "LPUART_0",
            "mode": "interrupt",
            "baud": 115200,
            "pins": {"tx": "PTA15", "rx": "PTA16"},
        },
    })
    plan = UartProvider().plan(intent)
    payload = plan.to_dict()
    owners = {item["owner"] for item in payload["changes"]}
    assert "uart" in owners
    assert "platform" in owners
    assert "port" in owners
    assert "mcu" in owners
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/unit/test_module_providers.py -q
```

Expected: FAIL because providers do not exist.

- [ ] **Step 3: Implement minimal providers**

Implement each provider as a focused class returning owned `PlannedChange` records. In this task, providers do not yet edit XML; they produce deterministic plans.

Example:

```python
# rtd_config/modules/uart.py
from __future__ import annotations

from rtd_config.intent import Intent
from rtd_config.plan import Plan, PlannedChange


class UartProvider:
    name = "uart"

    def plan(self, intent: Intent) -> Plan:
        payload = intent.payload
        changes = [
            PlannedChange("uart", "uart", "/Uart/UartGlobalConfig", f"Configure {payload['hw']} {payload['mode']}")
        ]
        if payload.get("pins"):
            changes.append(PlannedChange("port", "port", "/Port/PortConfigSet", "Configure Uart pins"))
        if payload.get("mode") == "interrupt":
            changes.append(PlannedChange("platform", "platform", "/Platform/IntCtrlConfig", "Configure Uart IRQ"))
        changes.append(PlannedChange("mcu", "mcu", "/Mcu/McuClockSettingConfig", "Ensure Uart clock reference"))
        return Plan(changes)
```

- [ ] **Step 4: Run tests and confirm pass**

Run:

```powershell
pytest tests/unit/test_module_providers.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/modules tests/unit/test_module_providers.py
git commit -m "Add minimal module providers"
```

---

### Task 9: Plan Command And Shortcut Normalization

**Files:**
- Modify: `rtd_config/cli.py`
- Create: `tests/integration/test_plan_command.py`

- [ ] **Step 1: Write failing plan command test**

```python
# tests/integration/test_plan_command.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_uart_shortcut_normalizes_to_plan(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "uart", "set",
            "--project", str(project),
            "--hw", "LPUART_0",
            "--mode", "polling",
            "--baud", "115200",
            "--tx", "PTA15",
            "--rx", "PTA16",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["normalized_intent"]["module"] == "uart"
    assert any(change["owner"] == "uart" for change in payload["plan"]["changes"])
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/integration/test_plan_command.py -q
```

Expected: FAIL because shortcut command is not implemented.

- [ ] **Step 3: Implement `uart set` as plan-only first**

Add `uart set` parser arguments and route to `UartProvider().plan(intent)`. Return the normalized intent and plan JSON. Do not write project files in this task.

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
pytest tests/integration/test_plan_command.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/cli.py tests/integration/test_plan_command.py
git commit -m "Add Uart shortcut planning"
```

---

### Task 10: Static Check And Check Command

**Files:**
- Create: `rtd_config/checks/static.py`
- Modify: `rtd_config/cli.py`
- Create: `tests/integration/test_check_command.py`

- [ ] **Step 1: Write failing check test**

```python
# tests/integration/test_check_command.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_check_reports_well_formed_fixture(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "check", "--project", str(project), "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["checks"]["xml_well_formed"] is True
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/integration/test_check_command.py -q
```

Expected: FAIL because `check` is not implemented.

- [ ] **Step 3: Implement static check**

Implement XML well-formedness, single `.mex` detection, enabled module list,
duplicate enabled-instance-name warning, quick-selection conflict detection for
planned edits, stale FlexIO Uart `UartHwChannelRef` detection, missing Mcl
FlexIO logic-channel detection, and M1 DMA rejection.

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
pytest tests/integration/test_check_command.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/checks/static.py rtd_config/cli.py tests/integration/test_check_command.py
git commit -m "Add static check command"
```

---

### Task 11: Minimal Apply And Configure Pipeline

**Files:**
- Modify: `rtd_config/cli.py`
- Modify: `rtd_config/backends/s32_mex/document.py`
- Create: `rtd_config/backends/s32_mex/static_check.py`
- Create: `tests/integration/test_configure_pipeline.py`

- [ ] **Step 1: Write failing configure pipeline test**

```python
# tests/integration/test_configure_pipeline.py
import json
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_configure_lpuart_polling_changes_mex_and_checks(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "uart", "set",
            "--project", str(project),
            "--hw", "LPUART_0",
            "--mode", "polling",
            "--baud", "115200",
            "--tx", "PTA15",
            "--rx", "PTA16",
            "--configure",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/integration/test_configure_pipeline.py -q
```

Expected: FAIL because configure/apply is not implemented.

- [ ] **Step 3: Implement minimal safe apply**

Implement localized XML edits by updating existing Uart/Port/Mcl/Platform/Mcu nodes in the real fixture. For Milestone 1, only edit existing module instances; do not create missing module instances.

The first implementation may use fixture-known paths discovered through `MexDocument` indexes. It must return blocker diagnostics instead of raw tracebacks when a node cannot be found.

- [ ] **Step 4: Run configure test and static check**

Run:

```powershell
pytest tests/integration/test_configure_pipeline.py tests/integration/test_check_command.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config tests/integration/test_configure_pipeline.py
git commit -m "Add minimal configure pipeline"
```

---

### Task 12: Backup Option

**Files:**
- Modify: `rtd_config/cli.py`
- Create: `tests/integration/test_backup_option.py`

- [ ] **Step 1: Write failing backup test**

```python
# tests/integration/test_backup_option.py
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_configure_backup_creates_mex_backup(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, "-m", "rtd_config",
            "uart", "set",
            "--project", str(project),
            "--hw", "LPUART_0",
            "--mode", "polling",
            "--baud", "115200",
            "--tx", "PTA15",
            "--rx", "PTA16",
            "--configure",
            "--backup",
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0
    assert (project / "Uart_Example.mex.bak").exists()
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/integration/test_backup_option.py -q
```

Expected: FAIL because `--backup` is not implemented.

- [ ] **Step 3: Implement optional backup**

Create `<mex>.bak` before writing only when `--backup` is present. Default behavior must not create a backup.

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
pytest tests/integration/test_backup_option.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add rtd_config/cli.py tests/integration/test_backup_option.py
git commit -m "Add optional backup support"
```

---

### Task 13: S32DS Headless Validation Command

**Files:**
- Create: `rtd_config/backends/s32_mex/validation.py`
- Modify: `rtd_config/cli.py`
- Create: `tests/unit/test_validation_command.py`
- Create: `tests/e2e/test_s32ds_validation.py`

- [ ] **Step 1: Write validation command builder test**

```python
# tests/unit/test_validation_command.py
from pathlib import Path

from rtd_config.backends.s32_mex.validation import build_validation_command


def test_build_validation_command_is_headless():
    command = build_validation_command(
        s32ds_root=Path("C:/NXP/S32DS.3.6.7"),
        project=Path("C:/tmp/Uart_Example_S32K344"),
    )
    joined = " ".join(command)
    assert "S32DS" in joined or "eclipse" in joined.lower()
    assert "-nosplash" in command
    assert any("application" in item.lower() for item in command)
```

- [ ] **Step 2: Write E2E validation test guarded by environment**

```python
# tests/e2e/test_s32ds_validation.py
import json
import os
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def test_validate_uart_fixture_headless(tmp_path):
    if not os.environ.get("RTD_CONFIG_RUN_S32DS_VALIDATION"):
        return
    project = copy_uart_fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "rtd_config", "validate", "--project", str(project), "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert payload["validation"]["exit_code"] == 0
```

- [ ] **Step 3: Run unit test and confirm failure**

Run:

```powershell
pytest tests/unit/test_validation_command.py -q
```

Expected: FAIL because validation builder does not exist.

- [ ] **Step 4: Implement validation command builder and CLI**

Implement:

- config lookup for S32DS root from CLI/env;
- no visible GUI window;
- timeout;
- stdout/stderr/log capture;
- JSON result with command, exit code, and log paths.

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest tests/unit/test_validation_command.py -q
```

Expected: pass.

Run when local S32DS is available:

```powershell
$env:RTD_CONFIG_RUN_S32DS_VALIDATION='1'
pytest tests/e2e/test_s32ds_validation.py -q
```

Expected: pass or actionable validation diagnostic with captured logs.

- [ ] **Step 6: Commit**

```powershell
git add rtd_config/backends/s32_mex/validation.py rtd_config/cli.py tests/unit/test_validation_command.py tests/e2e/test_s32ds_validation.py
git commit -m "Add S32DS headless validation"
```

---

### Task 14: Mandatory Minimum Test Matrix

**Files:**
- Create: `tests/e2e/test_m1_mandatory_minimum.py`

- [ ] **Step 1: Implement M1 test matrix**

Create one test per mandatory case ID. Each test should call the public CLI and assert JSON status, changed modules, static check status, and backend validation status when `RTD_CONFIG_RUN_S32DS_VALIDATION=1`.

Use test function names:

```python
def test_rtd_m1_min_001_inspect_uart_fixture(tmp_path): ...
def test_rtd_m1_min_002_lpuart_polling(tmp_path): ...
def test_rtd_m1_min_003_lpuart_interrupt(tmp_path): ...
def test_rtd_m1_min_004_flexio_polling(tmp_path): ...
def test_rtd_m1_min_005_flexio_interrupt(tmp_path): ...
def test_rtd_m1_min_006_pin_options(tmp_path): ...
def test_rtd_m1_min_007_e2e_lpuart_stack(tmp_path): ...
def test_rtd_m1_min_008_e2e_flexio_stack(tmp_path): ...
```

- [ ] **Step 2: Run matrix without vendor validation**

Run:

```powershell
pytest tests/e2e/test_m1_mandatory_minimum.py -q
```

Expected: all non-vendor checks pass.

- [ ] **Step 3: Run matrix with vendor validation**

Run:

```powershell
$env:RTD_CONFIG_RUN_S32DS_VALIDATION='1'
pytest tests/e2e/test_m1_mandatory_minimum.py -q
```

Expected: all mandatory cases pass, or any failure returns actionable diagnostics and captured validation logs.

- [ ] **Step 4: Commit**

```powershell
git add tests/e2e/test_m1_mandatory_minimum.py
git commit -m "Add M1 mandatory minimum test matrix"
```

---

### Task 15: Companion Agent Skill

**Files:**
- Create: `.skills/rtd-config/SKILL.md`
- Create: `tests/unit/test_agent_skill_contract.py`

- [ ] **Step 1: Write failing skill contract test**

```python
# tests/unit/test_agent_skill_contract.py
from pathlib import Path


def test_rtd_config_skill_names_public_cli_and_m1_scope():
    skill = Path(".skills/rtd-config/SKILL.md").read_text(encoding="utf-8")
    assert "RTD CfgFile CLI" in skill
    assert "rtd-config inspect" in skill
    assert "rtd-config pin-options" in skill
    assert "Milestone 1" in skill
    assert "DMA" in skill
    assert "not in Milestone 1" in skill
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
pytest tests/unit/test_agent_skill_contract.py -q
```

Expected: FAIL because skill does not exist.

- [ ] **Step 3: Add skill**

The skill must teach agents:

- use only public CLI;
- convert user requests into JSON intent or shortcut commands;
- run `inspect`, `pin-options`, `plan`, `configure`, `check`, `validate`;
- respect M1 scope and reject/defer DMA;
- use only mandatory minimum tests unless user asks for advanced tests;
- interpret diagnostics.

- [ ] **Step 4: Run test and confirm pass**

Run:

```powershell
pytest tests/unit/test_agent_skill_contract.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add .skills/rtd-config/SKILL.md tests/unit/test_agent_skill_contract.py
git commit -m "Add RTD Config agent skill"
```

---

### Task 16: Independent Subagent Validation Handoff

**Files:**
- Create: `docs/superpowers/tests/rtd-config-m1-subagent-validation.md`

- [ ] **Step 1: Create validation handoff document**

The document must list each mandatory case ID and the exact subagent user prompt from the test strategy. It must also state:

```text
Subagent calls must set "fork_context": false.
The subagent receives only the simulated user configuration request, repository-visible instructions, companion skills, and public CLI.
Focused KPI is 3 minutes.
E2E KPI is 5 minutes.
Main agent intervenes after 10 minutes.
```

- [ ] **Step 2: Verify prompt isolation**

Run:

```powershell
rg "implementation notes|main-agent|hidden assumptions|debugging process" docs/superpowers/tests/rtd-config-m1-subagent-validation.md
```

Expected: no matches.

- [ ] **Step 3: Commit**

```powershell
git add docs/superpowers/tests/rtd-config-m1-subagent-validation.md
git commit -m "Add M1 subagent validation handoff"
```

---

## Final Milestone 1 Acceptance

- [ ] Run full deterministic tests:

```powershell
pytest tests/unit tests/integration -q
```

Expected: all pass.

- [ ] Run mandatory E2E tests without vendor validation:

```powershell
pytest tests/e2e/test_m1_mandatory_minimum.py -q
```

Expected: all pass.

- [ ] Run mandatory E2E tests with S32DS validation:

```powershell
$env:RTD_CONFIG_RUN_S32DS_VALIDATION='1'
pytest tests/e2e/test_m1_mandatory_minimum.py -q
```

Expected: all mandatory tests pass, including static check plus S32DS headless validation.

- [ ] Run independent subagent validation for mandatory cases using `"fork_context": false`.

- [ ] Confirm `.mex` quick-selection behavior from
      `rtd-config-m1-legacy-skills-experience.md` is covered by unit or fixture
      tests.

Expected:

- focused cases converge within 3 minutes;
- E2E cases converge within 5 minutes;
- no case exceeds 10 minutes without main-agent intervention and issue capture.

## Plan Self-Review

| Check | Result |
| --- | --- |
| Spec coverage | Covers CLI/JSON contract, S32 `.mex` backend, runtime assets, seven M1 modules, fixture structure, runtime verification, mandatory tests, companion skill, and M1 legacy-skills experience baseline. |
| Scope guard | DMA, `.mex` creation, missing-module completion, EB tresos, K1/K5, runtime Excel parsing, and RTD install scans are excluded from implementation tasks. |
| Test alignment | Tasks map to `RTD-M1-MIN-001` through `RTD-M1-MIN-008`. |
| Placeholder scan | No placeholder markers or open-ended delayed-work steps are used. |
| Execution handoff | Tasks are checkbox-based, include files, tests, commands, and commit points. |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.1.1 | Added M1 legacy-skills experience baseline and quick-selection requirements to document core, static checks, and acceptance. |
| 2026-06-02 | 0.1.0 | Created Milestone 1 implementation plan from active RTD CfgFile CLI specs, roadmap, fixture layout, and test strategy. |
