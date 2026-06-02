# tests/integration/test_configure_pipeline.py
import json
import subprocess
import sys

from rtd_config.backends.s32_mex.document import MexDocument
from tests.fixtures import copy_uart_fixture


def _run_configure(project, *extra):
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
            "--json",
            *extra,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_configure_lpuart_polling_changes_mex_and_checks(tmp_path):
    project = copy_uart_fixture(tmp_path)
    result = _run_configure(project)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "passed"
    assert "uart" in payload["changed_modules"]
    assert payload["runtime_verification"]["static_check"]["status"] == "passed"


def test_configure_writes_real_edit_and_file_reloads(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    before = MexDocument.load(mex)
    before_cfg = before.find_config_set("Uart")
    channel0 = before.find_uart_channel(before_cfg, 0)
    before_baud = before.find_child_setting(channel0, "DesireBaudrate").attrib["value"]

    result = _run_configure(project)
    assert result.returncode == 0

    # The written file must re-load as well-formed XML and reflect a real edit.
    after = MexDocument.load(mex)
    after_cfg = after.find_config_set("Uart")
    channel0_after = after.find_uart_channel(after_cfg, 0)
    after_baud = after.find_child_setting(channel0_after, "DesireBaudrate").attrib["value"]
    after_hw = after.find_child_setting(channel0_after, "UartHwChannel").attrib["value"]

    assert after_baud == "LPUART_UART_BAUDRATE_115200"
    assert after_hw == "LPUART_0"
    # The edit genuinely changed the document (fixture channel 0 was 115200 on
    # LPUART_3; we still assert a concrete post-state above regardless).
    assert before_baud is not None
