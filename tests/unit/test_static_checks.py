# tests/unit/test_static_checks.py
from rtd_config.backends.s32_mex.document import MexDocument
from rtd_config.checks.static import run_static_checks
from tests.fixtures import copy_uart_fixture


def _load(tmp_path):
    project = copy_uart_fixture(tmp_path)
    mex = project / "Uart_Example.mex"
    return mex, MexDocument.load(mex)


def _codes(result):
    return {item.code for item in result.diagnostics}


def test_clean_fixture_passes_all_static_checks(tmp_path):
    mex, doc = _load(tmp_path)
    result = run_static_checks(mex, doc)
    assert result.status == "passed"
    assert result.data["checks"]["xml_well_formed"] is True
    assert result.data["checks"]["single_mex"] is True
    # The fixture has six enabled modules and a coherent FlexIO/Mcl wiring.
    assert "Uart" in result.data["checks"]["enabled_modules"]
    assert "Mcl" in result.data["checks"]["enabled_modules"]


def test_missing_mcl_flexio_logic_channel_is_blocked(tmp_path):
    mex, doc = _load(tmp_path)
    # Remove every FlexIO logic channel so existing Uart FlexIO refs dangle.
    for parent in doc.root.iter():
        for child in list(parent):
            if child.tag.endswith("array") and child.attrib.get("name") == "FlexioMclLogicChannels":
                for ch in list(child):
                    child.remove(ch)
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert result.status == "blocked"
    assert "missing_mcl_flexio_logic_channel" in codes


def test_stale_flexio_uart_hw_channel_ref_is_blocked(tmp_path):
    mex, doc = _load(tmp_path)
    uart_cfg = doc.find_config_set("Uart")
    # Corrupt the UartHwChannelRef on an ACTIVE FlexIO channel (UartHwUsing ==
    # FLEXIO_IP). Inactive FlexIO sub-structs on LPUART channels must not be
    # flagged, so we deliberately target an active FlexIO channel.
    target = None
    for channel in uart_cfg.iter():
        if not (channel.tag.endswith("struct")):
            continue
        using = doc.find_child_setting(channel, "UartHwUsing")
        if using is not None and using.attrib.get("value") == "FLEXIO_IP":
            target = channel
            break
    assert target is not None
    for setting in target.iter():
        if setting.tag.endswith("setting") and setting.attrib.get("name") == "UartHwChannelRef":
            setting.set("value", "/Mcl/Mcl/MclConfig/FlexioCommon_0/DOES_NOT_EXIST")
            break
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert result.status == "blocked"
    assert "stale_flexio_uart_hw_channel_ref" in codes


def test_dma_enabled_uart_is_rejected_for_m1(tmp_path):
    mex, doc = _load(tmp_path)
    for setting in doc.root.iter():
        if setting.tag.endswith("setting") and setting.attrib.get("name") == "UartDmaEnable":
            setting.set("value", "true")
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert result.status == "blocked"
    assert "dma_not_supported_in_m1" in codes


def test_duplicate_lpuart_hw_channel_is_flagged(tmp_path):
    mex, doc = _load(tmp_path)
    # Force two active LPUART Uart channels onto the same hardware instance.
    hw_settings = [
        s for s in doc.root.iter()
        if s.tag.endswith("setting") and s.attrib.get("name") == "UartHwChannel"
    ]
    for s in hw_settings:
        s.set("value", "LPUART_3")
    # Mark the owning channels as LPUART so they count as active LPUART channels.
    using = [
        s for s in doc.root.iter()
        if s.tag.endswith("setting") and s.attrib.get("name") == "UartHwUsing"
    ]
    for s in using:
        s.set("value", "LPUART_IP")
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert "duplicate_lpuart_hw_channel" in codes


def test_quick_selection_conflict_on_modified_element_is_reported(tmp_path):
    mex, doc = _load(tmp_path)
    # Simulate an edit that left quick_selection on a modified config_set.
    config_set = doc.find_config_set("Mcl")
    assert config_set is not None
    config_set.set("quick_selection", "mcl_default")
    result = run_static_checks(mex, doc, modified_elements=[config_set])
    codes = _codes(result)
    assert result.status == "blocked"
    assert "quick_selection_conflict" in codes


def test_callback_null_ptr_is_rejected_as_uart_callback(tmp_path):
    mex, doc = _load(tmp_path)
    result = run_static_checks(mex, doc, requested_callback="NULL_PTR")
    codes = _codes(result)
    assert result.status == "blocked"
    assert "invalid_uart_callback" in codes


def test_valid_c_identifier_callback_is_accepted(tmp_path):
    mex, doc = _load(tmp_path)
    result = run_static_checks(mex, doc, requested_callback="Uart_RxCallback")
    assert result.status == "passed"
