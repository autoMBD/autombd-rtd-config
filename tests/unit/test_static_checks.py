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
# File:        test_static_checks.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-03
# Version:     0.1.0
# Description: Unit tests for the static checks.
# =================================================================================

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


def test_dma_enabled_uart_passes_static_check(tmp_path):
    """DMA mode (RTD-MEX-UART-003) is now supported; a correctly-applied DMA file must not block.

    The former ``dma_not_supported_in_m1`` blocker was removed when DMA mode was
    implemented.  This test verifies the static checker accepts a DMA-configured
    file without producing ANY blocker -- not just the old dma_not_supported_in_m1 code.
    """
    from rtd_config.backends.s32_mex.apply import apply_uart_set
    from rtd_config.intent import Intent
    mex, doc = _load(tmp_path)
    # Apply a full correct DMA configuration so UartDmaTxChannelRef / UartDmaRxChannelRef
    # are populated and MclEnableDma=true -- matching the INVALID rule in Uart.xdm.
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {"hw": "LPUART_3", "mode": "dma", "priority": 2},
    })
    apply_result = apply_uart_set(doc, intent)
    assert not apply_result.blocked, [d.to_dict() for d in apply_result.diagnostics]
    result = run_static_checks(mex, doc)
    assert result.status != "blocked", (
        f"A correctly-applied DMA file must not be blocked. Diagnostics: "
        f"{[d.to_dict() for d in result.diagnostics]}"
    )


def test_dma_broken_missing_refs_is_blocked(tmp_path):
    """Uart channel with UartInteruptDmaMethod=DMA but empty DMA refs must be blocked.

    Grounded in Uart.xdm INVALID rule: when UartInteruptDmaMethod==LPUART_UART_IP_USING_DMA,
    UartDmaTxChannelRef and UartDmaRxChannelRef must be non-empty.
    """
    mex, doc = _load(tmp_path)
    # Set the method to DMA (without populating refs -- simulates a hand-broken file)
    for setting in doc.root.iter():
        if (
            setting.tag.endswith("setting")
            and setting.attrib.get("name") == "UartInteruptDmaMethod"
        ):
            setting.set("value", "LPUART_UART_IP_USING_DMA")
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert result.status == "blocked", (
        "A DMA-method Uart channel with empty refs must be blocked"
    )
    assert "dma_refs_incomplete" in codes, (
        f"Expected 'dma_refs_incomplete' blocker, got: {codes}"
    )


def test_dma_broken_mcl_not_enabled_is_blocked(tmp_path):
    """Uart channel with DMA method+refs but MclEnableDma=false must be blocked.

    Grounded in Uart.xdm cross-module rule: DMA transfers require MclEnableDma=true.
    """
    from rtd_config.backends.s32_mex.apply import apply_uart_set
    from rtd_config.intent import Intent
    mex, doc = _load(tmp_path)
    # Apply a full correct DMA config first (sets refs + MclEnableDma=true)
    intent = Intent.from_dict({
        "module": "uart",
        "action": "set",
        "payload": {"hw": "LPUART_3", "mode": "dma", "priority": 2},
    })
    apply_uart_set(doc, intent)
    # Now manually break it by setting MclEnableDma back to false
    for setting in doc.root.iter():
        if (
            setting.tag.endswith("setting")
            and setting.attrib.get("name") == "MclEnableDma"
        ):
            setting.set("value", "false")
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert result.status == "blocked", (
        "DMA configured with MclEnableDma=false must be blocked"
    )
    assert "dma_mcl_not_enabled" in codes, (
        f"Expected 'dma_mcl_not_enabled' blocker, got: {codes}"
    )


def test_interrupt_mode_uart_not_blocked_by_dma_check(tmp_path):
    """An interrupt-mode Uart channel must not trigger DMA checks (no DMA -> no-op)."""
    mex, doc = _load(tmp_path)
    result = run_static_checks(mex, doc)
    codes = _codes(result)
    assert "dma_refs_incomplete" not in codes
    assert "dma_mcl_not_enabled" not in codes


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
