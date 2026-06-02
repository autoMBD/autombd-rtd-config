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
