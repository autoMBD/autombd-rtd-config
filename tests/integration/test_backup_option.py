# tests/integration/test_backup_option.py
import subprocess
import sys

from tests.fixtures import copy_uart_fixture


def _configure(project, *extra):
    return subprocess.run(
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
            *extra,
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_configure_backup_creates_mex_backup(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project, "--backup")
    assert result.returncode == 0
    assert (project / "Uart_Example.mex.bak").exists()


def test_configure_without_backup_creates_no_backup(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _configure(project)
    assert result.returncode == 0
    assert not (project / "Uart_Example.mex.bak").exists()
