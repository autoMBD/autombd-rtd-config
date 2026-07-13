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
# File:        test_validation_command.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Unit tests for the S32DS validation command builder.
# =================================================================================

import hashlib
import _thread
import json
import os
from pathlib import Path
import sys
import time
import threading
from types import SimpleNamespace

import pytest

from rtd_config import cli
from rtd_config.backends.s32_mex.validation import (
    ValidationOutcome,
    _DEFAULT_S32DS_PARENTS,
    build_validation_command,
    default_sdk_path,
    find_severe_tool_problems,
    find_s32ds_root,
    is_valid_s32ds_root,
    probe_which_root,
    run_validation,
)
from rtd_config.backends.s32_mex.process_tree import (
    ProcessOutputLimits,
    ProcessTreeRunner,
)
from rtd_config.errors import CliFailure
from rtd_config.project import Project
from tests.fixtures import copy_uart_fixture
from rtd_config.backends.s32_mex.validation_workspace import ControlledValidationWorkspace
import rtd_config.backends.s32_mex.metadata as metadata_module
import rtd_config.backends.s32_mex.validation_workspace as workspace_module


def _validate_cmd():
    return build_validation_command(
        s32ds_root=Path("C:/NXP/S32DS.3.6.7"),
        mex_file=Path("C:/tmp/Uart_Example_S32K344/Uart_Example.mex"),
        workspace=Path("C:/tmp/_ws"),
        export_dir=Path("C:/tmp/_export"),
    )


def test_build_validation_command_is_standalone_flow_b():
    """Flow B: -Load + -ExportSrc, headless, no workspace registration.

    The earlier project flow (-ProjectLink + -UpdateCode) required a registered
    workspace project; its CDT -import step routinely timed out and produced a
    spurious exit 2 with "Cannot get container for IPath". Flow B exports
    generated code to a throwaway folder and needs no registration.
    """
    command = _validate_cmd()
    joined = " ".join(command)
    assert "eclipse" in joined.lower()
    assert "-nosplash" in command
    # The framework app only runs headless when -HeadlessTool is supplied.
    assert "-HeadlessTool" in command
    assert any("framework.application" in item for item in command)
    assert "-Load" in command
    assert "-ExportSrc" in command
    assert "-sdkPath" in command
    assert "-ShowProblems" in command
    # Flow B must NOT use the registration-bound project flow.
    assert "-ProjectLink" not in command
    assert "-UpdateCode" not in command
    assert "-import" not in command


def test_default_sdk_path_points_at_bundled_platform_sdk():
    sdk = default_sdk_path(Path("C:/NXP/S32DS.3.6.7"))
    assert sdk.parts[-3:] == ("S32DS", "software", "PlatformSDK_S32K3")


def test_find_severe_tool_problems_filters_out_environment_noise():
    """Only [TOOL] '... has the following error' resource problems gate.

    Everything else ConfigTools logs at SEVERE/严重 on a headless, unregistered
    run -- "Cannot get container", SerDes "No script file", localized framework
    NLS errors -- is environment noise, not .mex validity, and must be excluded.

    Also verifies the real known-good benign lines (from Explorer live runs)
    that must never be flagged:
    - "Dependency from Pins/Clocks ... M7_0 not found" (no Tool problem issue pair)
    - "Cannot get container for IPath" (localized 严重:)
    - "[TOOL] No script file found" SerDes line (lacks "From Problems view")
    - "Null toolchain project" warning
    """
    text = "\n".join([
        ' SEVERE: [TOOL] The resource "BaseNXP" ... has the following error: The number of OsIf Counters ... [x]',
        ' SEVERE: From Problems view: ... target: Toolchain/IDE project [y]',
        ' SEVERE: [TOOL] No script file found while trying to recompile ... SerDes Config Tool [z]',
        '严重: Cannot get container for IPath C:/tmp/Uart_Example.mex',
        # Real known-good benign lines from Explorer live runs (must NOT be flagged):
        '!MESSAGE Dependency from Pins:PortContainer_0_VS_0 for platform.driver.pins requires configuration M7_0 that was not found in the result of query',
        ' SEVERE: Dependency from Clocks:BOARD_BootClockRUN for platform.driver.clock requires configuration M7_0 that was not found in the result of query [ValidationEngineImpl.validate]',
        '严重: Cannot get container for IPath C:/tmp/x.mex',
        '严重: [TOOL] No script file found while trying to recompile the codegeneration script for SerDes Config Tool',
        ' WARNING: Null toolchain project for the configuration [ToolchainProjectQuery.query]',
    ])
    problems = find_severe_tool_problems(text)
    assert len(problems) == 1, (
        f"Expected exactly 1 severe problem (the BaseNXP [TOOL] line); "
        f"got {len(problems)}: {problems}"
    )
    assert "has the following error" in problems[0]
    assert "BaseNXP" in problems[0]


def test_find_severe_tool_problems_flags_problems_view_hse_clk():
    """'From Problems view: Tool problem issue:' lines are flagged (LL-014).

    HSE_CLK>120 MHz violations exit ConfigTools with code 0 and still generate
    code, so the existing '[TOOL] ... has the following error' sentinel misses
    them entirely. The new sentinel pair ('From Problems view' + 'Tool problem
    issue') catches these in both the !MESSAGE (stdout) and SEVERE: (stderr)
    forms, and in both English and localized (Chinese) variants.
    """
    hse_clk_stdout = (
        '!MESSAGE From Problems view: Tool problem issue: '
        '"CORE_CLK is higher than 120 MHz, HSE_CLK must be half of the CORE_CLK", '
        'origin: Clocks: BOARD_BootClockRUN, target: Clocks, resource: HSE_CLK'
    )
    hse_clk_stderr_zh = (
        ' SEVERE: From Problems view: Tool problem issue: '
        '"输入频率必须小于或等于： 120 MHz", '
        'origin: Clocks: BOARD_BootClockRUN, target: Clocks, resource: HSE_CLK'
        '  [ValidationEngineFactory.lambda$5]'
    )
    text = "\n".join([hse_clk_stdout, hse_clk_stderr_zh])
    problems = find_severe_tool_problems(text)
    assert len(problems) == 2, (
        f"Expected 2 flagged problems (stdout + stderr HSE_CLK forms); "
        f"got {len(problems)}: {problems}"
    )
    assert any("CORE_CLK is higher than 120 MHz" in p for p in problems)
    assert any("输入频率必须小于或等于" in p for p in problems)


def test_find_severe_tool_problems_flags_peripherals_and_pins_targets():
    """'From Problems view: Tool problem issue:' is flagged for any target (LL-014 generality).

    The detector must not be limited to target: Clocks; Peripherals and Pins
    resource-constraint violations emit the same sentinel pair and must also be caught.
    """
    peripherals_line = (
        '!MESSAGE From Problems view: Tool problem issue: '
        '"SomePeripheral constraint violated", '
        'origin: Peripherals: CAN_0, target: Peripherals, resource: CAN_CLOCK'
    )
    pins_line = (
        '!MESSAGE From Problems view: Tool problem issue: '
        '"Pin mux conflict detected", '
        'origin: Pins: PTA0, target: Pins, resource: PTA0'
    )
    text = "\n".join([peripherals_line, pins_line])
    problems = find_severe_tool_problems(text)
    assert len(problems) == 2, (
        f"Expected 2 flagged problems (Peripherals + Pins targets); "
        f"got {len(problems)}: {problems}"
    )
    assert any("Peripherals" in p and "CAN_CLOCK" in p for p in problems)
    assert any("Pins" in p and "PTA0" in p for p in problems)


def test_validation_outcome_pass_gate_with_problems_view_problem():
    """A Problems-view severe problem makes passed False even with exit 0 and codegen.

    This confirms the LL-014 bypass is enforced end-to-end: ConfigTools can
    return exit 0 with generated files AND a 'From Problems view: Tool problem
    issue:' line, but ValidationOutcome.passed must be False.
    """
    problems_view_line = (
        'From Problems view: Tool problem issue: '
        '"CORE_CLK is higher than 120 MHz, HSE_CLK must be half of the CORE_CLK", '
        'origin: Clocks: BOARD_BootClockRUN, target: Clocks, resource: HSE_CLK'
    )
    outcome = ValidationOutcome(
        exit_code=0,
        severe_problems=[problems_view_line],
        generated_files=120,
        command=[],
        log_path="x",
    )
    assert outcome.passed is False, (
        "A 'From Problems view: Tool problem issue:' severe problem must make "
        "passed False even when exit_code=0 and generated_files=120"
    )


def test_validation_outcome_pass_gate():
    base = dict(command=[], log_path="x")
    # Pass = exit 0 AND code generated AND no SEVERE [TOOL] config error.
    assert ValidationOutcome(
        exit_code=0, severe_problems=[], generated_files=122, **base
    ).passed is True
    # exit 0 but a SEVERE [TOOL] problem present -> not a pass.
    assert ValidationOutcome(
        exit_code=0, severe_problems=["boom"], generated_files=122, **base
    ).passed is False
    # The vendor gate is exactly exit 0 + no qualifying resource problem.
    assert ValidationOutcome(
        exit_code=0, severe_problems=[], generated_files=0, **base
    ).passed is True
    # non-zero exit -> not a pass.
    assert ValidationOutcome(
        exit_code=2, severe_problems=[], generated_files=122, **base
    ).passed is False


def test_process_tree_runner_bounds_invalid_output_without_deadlock(tmp_path):
    runner = ProcessTreeRunner(ProcessOutputLimits(max_bytes=128, max_lines=4))
    result = runner.run(
        [
            sys.executable,
            "-c",
            "import os; os.write(1, b'head\\n' + b'x'*4096 + b'\\xfftail\\n')",
        ],
        cwd=tmp_path,
        env={},
        timeout_s=10,
    )
    assert result.exit_code == 0
    assert result.stdout_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 256
    assert "tail" in result.stdout
    assert "\ufffd" in result.stdout


def test_process_tree_timeout_kills_descendant_before_it_can_escape(tmp_path):
    marker = tmp_path / "escaped.txt"
    child = (
        "import pathlib,time,sys; time.sleep(1); "
        "pathlib.Path(sys.argv[1]).write_text('escaped')"
    )
    parent = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); "
        "time.sleep(30)"
    )
    result = ProcessTreeRunner().run(
        [sys.executable, "-c", parent, child, str(marker)],
        cwd=tmp_path,
        env={},
        timeout_s=0.2,
    )
    assert result.code == "process_timeout"
    assert result.timed_out is True
    time.sleep(1.2)
    assert not marker.exists()


def test_process_tree_argv_is_never_interpreted_by_a_shell(tmp_path):
    marker = tmp_path / "injected.txt"
    payload = f"; echo injected > {marker}"
    result = ProcessTreeRunner().run(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", payload],
        cwd=tmp_path,
        env={},
        timeout_s=10,
    )
    assert result.exit_code == 0
    assert payload in result.stdout
    assert not marker.exists()


def test_process_tree_keyboard_interrupt_kills_descendants_and_reaps(tmp_path):
    marker = tmp_path / "interrupt-escaped.txt"
    child = (
        "import pathlib,time,sys; time.sleep(1); "
        "pathlib.Path(sys.argv[1]).write_text('escaped')"
    )
    parent = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]]); "
        "time.sleep(30)"
    )
    timer = threading.Timer(0.2, _thread.interrupt_main)
    timer.start()
    try:
        with pytest.raises(KeyboardInterrupt):
            ProcessTreeRunner().run(
                [sys.executable, "-c", parent, child, str(marker)],
                cwd=tmp_path, env={}, timeout_s=30,
            )
    finally:
        timer.cancel()
    time.sleep(1.2)
    assert not marker.exists()


def test_process_tree_spawn_failure_is_sanitized(tmp_path):
    result = ProcessTreeRunner().run(
        [str(tmp_path / "missing-validator.exe")],
        cwd=tmp_path, env={}, timeout_s=1,
    )
    assert result.code == "process_spawn_failed"
    assert result.exit_code == 127
    assert str(tmp_path) not in result.stderr


def _project_manifest(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_ino,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in root.rglob("*")
        if path.is_file()
    }


def test_validation_uses_controlled_copy_and_leaves_project_byte_identical(tmp_path):
    project = copy_uart_fixture(tmp_path)
    control = tmp_path / "controlled-validation"
    before = _project_manifest(project)
    observed = {}

    class FakeRunner:
        def run(self, argv, *, cwd, env, timeout_s):
            observed["argv"] = list(argv)
            observed["cwd"] = cwd
            load = Path(argv[argv.index("-Load") + 1])
            export = Path(argv[argv.index("-ExportSrc") + 1])
            assert load.is_relative_to(control)
            assert cwd.is_relative_to(control)
            assert not load.is_relative_to(project)
            assert Path(env["TEMP"]).is_relative_to(control)
            assert Path(env["TMP"]).is_relative_to(control)
            staged = {
                item.relative_to(load.parent).as_posix(): item
                for item in load.parent.rglob("*")
                if item.is_file()
            }
            required = {
                load.name,
                ".project",
                ".cproject",
                *(
                    item.relative_to(project).as_posix()
                    for item in (project / ".settings").rglob("*")
                    if item.is_file()
                ),
            }
            assert required <= set(staged), (
                "controlled validation stage lacks the S32DS project metadata "
                f"required by the real -Load command: {sorted(required - set(staged))}"
            )
            for relative in required:
                assert staged[relative].read_bytes() == (project / relative).read_bytes()
            load.write_bytes(b"vendor-mutated-stage")
            export.mkdir(parents=True, exist_ok=True)
            (export / "generated.c").write_bytes(b"generated")
            return type("Result", (), {
                "exit_code": 0, "stdout": "ok", "stderr": "",
                "code": "process_exit", "timed_out": False,
                "stdout_truncated": False, "stderr_truncated": False,
            })()

    outcome = run_validation(
        project,
        Path("C:/NXP/S32DS.3.6.7"),
        workspace=control,
        runner=FakeRunner(),
    )
    assert outcome.passed is True
    assert _project_manifest(project) == before
    assert not control.exists()
    assert outcome.log_path == "validation.log"
    assert all(str(project) not in item for item in outcome.command)


def test_validation_rejects_linked_source_without_launch(tmp_path):
    project = copy_uart_fixture(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    linked = project / ".settings" / "linked.prefs"
    try:
        linked.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    class ForbiddenRunner:
        def run(self, *_args, **_kwargs):
            pytest.fail("vendor launched for linked source")

    with pytest.raises(CliFailure) as caught:
        run_validation(
            project,
            Path("C:/NXP/S32DS.3.6.7"),
            workspace=tmp_path / "controlled-validation",
            runner=ForbiddenRunner(),
        )
    assert caught.value.code == "validation_source_unsafe"
    assert outside.read_bytes() == b"outside"


def test_validation_rejects_linked_workspace_root_without_launch(tmp_path):
    project = copy_uart_fixture(tmp_path)
    outside = tmp_path / "outside-workspace"
    outside.mkdir()
    linked = tmp_path / "linked-workspace"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")

    class ForbiddenRunner:
        def run(self, *_args, **_kwargs):
            pytest.fail("vendor launched for linked workspace")

    with pytest.raises(CliFailure) as caught:
        run_validation(
            project, Path("C:/NXP/S32DS.3.6.7"),
            workspace=linked, runner=ForbiddenRunner(),
        )
    assert caught.value.code in {"validation_source_unsafe", "validation_workspace_unsafe"}
    assert not tuple(outside.iterdir())


def test_validation_rejects_system_temp_workspace_before_launch(monkeypatch, tmp_path):
    project = copy_uart_fixture(tmp_path)
    system_temp = tmp_path / "system-temp"
    system_temp.mkdir()
    monkeypatch.setenv("TEMP", str(system_temp))
    monkeypatch.setenv("TMP", str(system_temp))

    class ForbiddenRunner:
        def run(self, *_args, **_kwargs):
            pytest.fail("vendor launched in system temp")

    with pytest.raises(CliFailure) as caught:
        run_validation(
            project, Path("C:/NXP/S32DS.3.6.7"),
            workspace=system_temp / "validation", runner=ForbiddenRunner(),
        )
    assert caught.value.code == "validation_workspace_unsafe"
    assert not (system_temp / "validation").exists()


def test_nonqualifying_severe_text_does_not_fail_vendor_gate():
    text = "SEVERE: ordinary launcher warning\n[TOOL] harmless status"
    assert find_severe_tool_problems(text) == []


def test_validate_static_blocker_short_circuits_before_vendor_or_workspace(
    monkeypatch, capsys, tmp_path
):
    project = copy_uart_fixture(tmp_path)
    control = tmp_path / "must-not-exist"
    blocked = SimpleNamespace(
        status="blocked", diagnostics=[],
        to_dict=lambda: {"status": "blocked", "diagnostics": []},
    )
    monkeypatch.setattr(cli, "run_static_checks", lambda *_args, **_kwargs: blocked)
    monkeypatch.setattr(
        cli, "find_s32ds_root",
        lambda *_args, **_kwargs: pytest.fail("S32DS resolution ran after static blocker"),
    )
    monkeypatch.setattr(
        cli, "run_validation",
        lambda *_args, **_kwargs: pytest.fail("vendor ran after static blocker"),
    )
    result = cli.cmd_validate(SimpleNamespace(
        project=project, s32ds_root="unused", workspace=control, sdk_path=None,
    ))
    payload = json.loads(capsys.readouterr().out)
    assert result == 1
    assert payload["status"] == "blocked"
    assert payload["runtime_verification"]["static_check"]["status"] == "blocked"
    assert "validation" not in payload
    assert not control.exists()


def test_vendor_mutation_of_original_project_is_detected_and_workspace_cleaned(
    tmp_path
):
    project = copy_uart_fixture(tmp_path)
    control = tmp_path / "controlled-validation"
    source = project / ".project"

    class MutatingRunner:
        def run(self, argv, *, cwd, env, timeout_s):
            source.write_bytes(source.read_bytes() + b"mutated")
            export = Path(argv[argv.index("-ExportSrc") + 1])
            (export / "generated.c").write_bytes(b"generated")
            return SimpleNamespace(
                exit_code=0, stdout="", stderr="", code="process_exit",
                timed_out=False, stdout_truncated=False, stderr_truncated=False,
            )

    with pytest.raises(CliFailure) as caught:
        run_validation(
            project, Path("C:/NXP/S32DS.3.6.7"),
            workspace=control, runner=MutatingRunner(),
        )
    assert caught.value.code == "validation_source_changed"
    assert tuple(caught.value.details["entries"]) == (".project",)
    assert not control.exists()


def test_cleanup_failure_is_explicit_and_preserves_only_workspace_basename(
    monkeypatch, tmp_path
):
    project = copy_uart_fixture(tmp_path)
    control = tmp_path / "controlled-validation"
    real_rmtree = workspace_module.shutil.rmtree

    class PassingRunner:
        def run(self, argv, *, cwd, env, timeout_s):
            export = Path(argv[argv.index("-ExportSrc") + 1])
            (export / "generated.c").write_bytes(b"generated")
            return SimpleNamespace(
                exit_code=0, stdout="", stderr="", code="process_exit",
                timed_out=False, stdout_truncated=False, stderr_truncated=False,
            )

    monkeypatch.setattr(
        workspace_module.shutil, "rmtree",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected cleanup")),
    )
    outcome = run_validation(
        project, Path("C:/NXP/S32DS.3.6.7"),
        workspace=control, runner=PassingRunner(),
    )
    assert outcome.passed is False
    assert outcome.cleanup_warnings[0]["code"] == "validation_cleanup_failed"
    preserved = outcome.cleanup_warnings[0]["details"]["preserved"]
    assert len(preserved) == 1 and not Path(preserved[0]).is_absolute()
    monkeypatch.setattr(workspace_module.shutil, "rmtree", real_rmtree)
    real_rmtree(control)


def test_validation_keyboard_interrupt_cleans_workspace_and_preserves_project(tmp_path):
    project = copy_uart_fixture(tmp_path)
    control = tmp_path / "controlled-validation"
    before = _project_manifest(project)

    class InterruptingRunner:
        def run(self, *_args, **_kwargs):
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_validation(
            project, Path("C:/NXP/S32DS.3.6.7"),
            workspace=control, runner=InterruptingRunner(),
        )
    assert _project_manifest(project) == before
    assert not control.exists()


@pytest.mark.parametrize("operation", ["add", "delete"])
def test_vendor_settings_inventory_drift_is_detected(operation, tmp_path):
    project = copy_uart_fixture(tmp_path)
    control = tmp_path / "controlled-validation"
    settings = project / ".settings"
    victim = settings / "org.eclipse.core.resources.prefs"

    class DriftingRunner:
        def run(self, argv, *, cwd, env, timeout_s):
            if operation == "add":
                (settings / "added-during-validation.prefs").write_bytes(b"new=true\n")
            else:
                victim.unlink()
            return SimpleNamespace(
                exit_code=0, stdout="", stderr="", code="process_exit",
                timed_out=False, stdout_truncated=False, stderr_truncated=False,
            )

    with pytest.raises(CliFailure) as caught:
        run_validation(
            project, Path("C:/NXP/S32DS.3.6.7"),
            workspace=control, runner=DriftingRunner(),
        )
    assert caught.value.code == "validation_source_changed"
    assert not control.exists()


def test_workspace_materializes_captured_bytes_after_source_is_deleted(tmp_path):
    root = copy_uart_fixture(tmp_path)
    control = tmp_path / "controlled-validation"
    with Project.verified(root) as project:
        inventory = project.capture_validator_inputs()
        expected = {
            item.relative: item.snapshot.content for item in inventory.files
        }
        (root / ".project").unlink()
        workspace = ControlledValidationWorkspace(control, inventory).open()
        try:
            assert workspace.project_dir is not None
            for relative, content in expected.items():
                assert (workspace.project_dir / relative).read_bytes() == content
        finally:
            assert workspace.close() == []
    assert not control.exists()


def test_inventory_capture_rejects_same_name_preference_recreation(
    monkeypatch, tmp_path
):
    root = copy_uart_fixture(tmp_path)
    relative = ".settings/org.eclipse.core.resources.prefs"
    source = root / relative
    with Project.verified(root) as project:
        project.metadata
        capture = metadata_module.snapshot_project_relative
        mutated = {"value": False}

        def recreate_after_capture(target, requested, *, max_bytes):
            snapshot = capture(target, requested, max_bytes=max_bytes)
            if requested == relative and not mutated["value"]:
                mutated["value"] = True
                content = source.read_bytes()
                source.unlink()
                source.write_bytes(content)
            return snapshot

        monkeypatch.setattr(
            metadata_module, "snapshot_project_relative", recreate_after_capture
        )
        with pytest.raises(CliFailure) as caught:
            project.capture_validator_inputs()
    assert caught.value.code == "validation_inventory_changed"


# ---------------------------------------------------------------------------
# Helpers — fabricate a minimal valid S32DS root tree in tmp_path.
# ---------------------------------------------------------------------------

def _make_valid_root(base: Path, name: str = "S32DS.3.6.7") -> Path:
    """Create marker files that satisfy is_valid_s32ds_root under base/name."""
    root = base / name
    (root / "eclipse").mkdir(parents=True)
    (root / "eclipse" / "s32dsc.exe").write_bytes(b"")
    (root / "S32DS" / "software" / "PlatformSDK_S32K3").mkdir(parents=True)
    return root


def _make_invalid_root(base: Path, name: str = "S32DS.3.6.0-bad") -> Path:
    """Create a root that is missing the SDK dir (is_valid_s32ds_root -> False)."""
    root = base / name
    (root / "eclipse").mkdir(parents=True)
    (root / "eclipse" / "s32dsc.exe").write_bytes(b"")
    # SDK dir intentionally absent
    return root


# ---------------------------------------------------------------------------
# is_valid_s32ds_root
# ---------------------------------------------------------------------------

def test_is_valid_s32ds_root_true_on_complete_tree(tmp_path):
    root = _make_valid_root(tmp_path)
    assert is_valid_s32ds_root(root) is True


def test_is_valid_s32ds_root_false_missing_exe(tmp_path):
    root = tmp_path / "S32DS.3.6.7"
    # Only SDK dir, no exe
    (root / "S32DS" / "software" / "PlatformSDK_S32K3").mkdir(parents=True)
    assert is_valid_s32ds_root(root) is False


def test_is_valid_s32ds_root_false_missing_sdk(tmp_path):
    root = _make_invalid_root(tmp_path)
    assert is_valid_s32ds_root(root) is False


def test_is_valid_s32ds_root_false_nonexistent(tmp_path):
    assert is_valid_s32ds_root(tmp_path / "does_not_exist") is False


# ---------------------------------------------------------------------------
# find_s32ds_root — explicit wins
# ---------------------------------------------------------------------------

def test_find_s32ds_root_explicit_wins_over_env_and_glob(tmp_path):
    """Explicit path is returned as-is even when env and parent-glob have valid roots."""
    valid_explicit = _make_valid_root(tmp_path, "explicit_root")
    valid_env = _make_valid_root(tmp_path, "env_root")
    valid_parent = _make_valid_root(tmp_path / "parents", "S32DS.3.6.7")

    result = find_s32ds_root(
        explicit=str(valid_explicit),
        env={"RTD_CONFIG_S32DS_ROOT": str(valid_env)},
        search_parents=[tmp_path / "parents"],
        which=lambda _: None,
    )
    assert result == valid_explicit


def test_find_s32ds_root_explicit_returned_even_if_invalid(tmp_path):
    """Explicit is trusted unconditionally — invalid path still returned."""
    bogus = tmp_path / "no_such_install"
    result = find_s32ds_root(
        explicit=str(bogus),
        env={},
        search_parents=[],
        which=lambda _: None,
    )
    assert result == bogus


# ---------------------------------------------------------------------------
# find_s32ds_root — env fallback
# ---------------------------------------------------------------------------

def test_find_s32ds_root_env_used_when_no_explicit(tmp_path):
    valid_env = _make_valid_root(tmp_path)
    result = find_s32ds_root(
        explicit=None,
        env={"RTD_CONFIG_S32DS_ROOT": str(valid_env)},
        search_parents=[],
        which=lambda _: None,
    )
    assert result == valid_env


def test_find_s32ds_root_env_returned_even_if_invalid(tmp_path):
    bogus = tmp_path / "not_a_real_s32ds"
    result = find_s32ds_root(
        explicit=None,
        env={"RTD_CONFIG_S32DS_ROOT": str(bogus)},
        search_parents=[],
        which=lambda _: None,
    )
    assert result == bogus


# ---------------------------------------------------------------------------
# find_s32ds_root — which fallback
# ---------------------------------------------------------------------------

def test_find_s32ds_root_which_valid_root_returned(tmp_path):
    """which returns exe path whose parent.parent is a valid root -> returned."""
    root = _make_valid_root(tmp_path)
    exe = root / "eclipse" / "s32dsc.exe"

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _name: str(exe),
    )
    assert result == root


def test_find_s32ds_root_which_invalid_root_falls_through_to_none(tmp_path):
    """which returns exe but the derived root is invalid -> falls through to None."""
    bad_root = _make_invalid_root(tmp_path)
    exe = bad_root / "eclipse" / "s32dsc.exe"

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _name: str(exe),
    )
    assert result is None


def test_find_s32ds_root_which_none_falls_through(tmp_path):
    """which returns None -> falls through to parent-glob or None."""
    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _: None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# find_s32ds_root — parent-glob, version-sort
# ---------------------------------------------------------------------------

def test_find_s32ds_root_glob_picks_highest_version(tmp_path):
    """Among multiple valid roots, the one with the highest parsed version wins."""
    parent = tmp_path / "NXP"
    _make_valid_root(parent, "S32DS.3.5.0")
    _make_valid_root(parent, "S32DS.3.6.7")
    _make_valid_root(parent, "S32DS.3.6.2")

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result is not None
    assert result.name == "S32DS.3.6.7"


def test_find_s32ds_root_glob_ignores_invalid_roots(tmp_path):
    """Invalid roots (missing exe or SDK) are skipped; valid one is returned."""
    parent = tmp_path / "NXP"
    _make_invalid_root(parent, "S32DS.3.6.7")   # invalid (no SDK)
    valid = _make_valid_root(parent, "S32DS.3.5.0")

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result == valid


def test_find_s32ds_root_glob_empty_parent_returns_none(tmp_path):
    """Parent dir exists but has no S32DS* children -> None."""
    parent = tmp_path / "NXP"
    parent.mkdir()

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# find_s32ds_root — nothing valid -> None
# ---------------------------------------------------------------------------

def test_find_s32ds_root_returns_none_when_nothing_configured(tmp_path):
    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[],
        which=lambda _: None,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Fix 2 — unparseable-named valid root must not beat a real versioned install
# ---------------------------------------------------------------------------

def test_find_s32ds_root_glob_versioned_beats_unparseable_name(tmp_path):
    """An ARM-named (unparseable) install must never win over a real versioned one.

    Creates two valid roots under one parent:
    - S32DS.3.6.7  -- parseable version (3, 6, 7)
    - S32DS_ARM_v2.2 -- unparseable (no 'S32DS.' prefix with all-int tail)

    The sort key is (version_tuple, name) descending.  S32DS.3.6.7 has key
    ((3,6,7), 'S32DS.3.6.7') while S32DS_ARM_v2.2 has key ((), 'S32DS_ARM_v2.2').
    Any non-empty tuple compares greater than the empty tuple, so the versioned
    install wins regardless of lexicographic directory name order.
    """
    parent = tmp_path / "NXP"
    versioned = _make_valid_root(parent, "S32DS.3.6.7")
    _make_valid_root(parent, "S32DS_ARM_v2.2")  # structurally valid but unparseable name

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=[parent],
        which=lambda _: None,
    )
    assert result == versioned, (
        f"Expected {versioned!r}, got {result!r}: "
        "versioned install must win over an unparseable-named install"
    )


# ---------------------------------------------------------------------------
# Fix 3 — production default _DEFAULT_S32DS_PARENTS path is exercised
# ---------------------------------------------------------------------------

def test_default_s32ds_parents_exact_contents():
    """_DEFAULT_S32DS_PARENTS must be [C:\\NXP, C:\\nxp] in that order.

    This pins the constant so that any typo or reorder immediately breaks the
    test.  The test does not depend on those directories existing on disk.
    """
    assert _DEFAULT_S32DS_PARENTS == [Path(r"C:\NXP"), Path(r"C:\nxp")], (
        "_DEFAULT_S32DS_PARENTS order or content changed — update the constant "
        "and this test together"
    )


def test_find_s32ds_root_uses_default_parents_when_none_given(tmp_path, monkeypatch):
    """Calling find_s32ds_root with search_parents=None uses _DEFAULT_S32DS_PARENTS.

    Monkeypatching the module-level list to point at a temp parent containing a
    valid root proves the default branch is reached and that _DEFAULT_S32DS_PARENTS
    is the actual list consulted — not a local copy or hard-coded fallback.
    """
    import rtd_config.backends.s32_mex.validation as _val_mod

    # Build a valid root inside the temp directory.
    valid = _make_valid_root(tmp_path, "S32DS.3.6.7")

    # Redirect the module-level default so our temp dir is searched.
    monkeypatch.setattr(_val_mod, "_DEFAULT_S32DS_PARENTS", [tmp_path])

    result = find_s32ds_root(
        explicit=None,
        env={},
        search_parents=None,   # <-- exercises the default branch
        which=lambda _: None,
    )
    assert result == valid, (
        f"Expected {valid!r}, got {result!r}: "
        "default _DEFAULT_S32DS_PARENTS branch was not taken"
    )


# ---------------------------------------------------------------------------
# Fix 4 — probe_which_root returns the derived path regardless of validity
# ---------------------------------------------------------------------------

def test_probe_which_root_returns_derived_path_even_when_invalid(tmp_path):
    """probe_which_root returns the derived root path even when the install is incomplete.

    This is the breadcrumb contract: the caller (cmd_validate) can surface
    'found s32dsc.exe at X but the installation is incomplete' instead of
    the generic 'not configured' message.
    """
    bad_root = _make_invalid_root(tmp_path)  # exe present, SDK absent
    exe = bad_root / "eclipse" / "s32dsc.exe"

    result = probe_which_root(which_fn=lambda _: str(exe))
    assert result == bad_root


def test_probe_which_root_returns_none_when_which_returns_none():
    """probe_which_root returns None when s32dsc.exe is not on PATH."""
    result = probe_which_root(which_fn=lambda _: None)
    assert result is None
