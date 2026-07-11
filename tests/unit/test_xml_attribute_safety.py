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
# File:        test_xml_attribute_safety.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-07-11
# Version:     0.1.0
# Description: Security tests for XML attribute rendering in .mex edit paths.
# =================================================================================

from __future__ import annotations

from collections.abc import Callable
import xml.etree.ElementTree as ET

import pytest

from rtd_config.backends.s32_mex.apply import (
    _build_adc_channel_struct_bytes,
    _build_dio_channel_array_bytes,
    _build_flexio_channel_struct_bytes,
    _build_flexio_uart_channel_bytes,
)
from rtd_config.backends.s32_mex.document import _sub_attr_value


Builder = Callable[[str], bytes]

_INJECTED_ATTRIBUTE_TEXT = 'SAFE"/><setting name="Injected" value="true'
_XML_METACHAR_TEXT = 'R&D <diagnostic> "quoted"'
_ILLEGAL_XML_TEXT = "SAFE\x01UNSAFE"


def _build_mcl_channel(value: str) -> bytes:
    return _build_flexio_channel_struct_bytes(
        struct_index=2,
        channel_id="CHANNEL_2",
        pin_id="PIN_2",
        channel_name=value,
        indent=0,
        line_ending=b"\n",
    )


def _build_dio_channel(value: str) -> bytes:
    return _build_dio_channel_array_bytes(
        channel_name=value,
        channel_id=3,
        indent=0,
        line_ending=b"\n",
    )


def _build_uart_channel(value: str) -> bytes:
    return _build_flexio_uart_channel_bytes(
        struct_index=3,
        channel_name=value,
        uart_channel_id=3,
        clock_ref_path="/Mcu/Mcu/McuModuleConfiguration/Clock/FLEXIO_CLK",
        mcl_channel_ref="/Mcl/Mcl/MclConfig/FlexioCommon_0/CHANNEL",
        baud_enum="FLEXIO_UART_BAUDRATE_921600",
        bit_count_enum="FLEXIO_UART_8_BITS",
        direction_enum="FLEXIO_UART_DIRECTION_TX",
        struct_indent=0,
        line_ending=b"\n",
    )


def _build_adc_watchdog_notification(value: str) -> bytes:
    return _build_adc_channel_struct_bytes(
        struct_index=0,
        logical_id=0,
        channel_name="P5",
        channel_id=5,
        watchdog={"notification": value},
        unit_name="AdcHwUnit_0",
        indent=0,
        line_ending=b"\n",
    )


_RAW_BUILDERS = (
    pytest.param(_build_mcl_channel, "Name", id="mcl-channel-name"),
    pytest.param(_build_dio_channel, "Name", id="dio-channel-name"),
    pytest.param(_build_uart_channel, "Name", id="flexio-uart-channel-name"),
    pytest.param(
        _build_adc_watchdog_notification,
        "AdcWdogNotification",
        id="adc-watchdog-notification",
    ),
)


def _setting_values(root: ET.Element, setting_name: str) -> list[str | None]:
    return [
        element.attrib.get("value")
        for element in root.iter("setting")
        if element.attrib.get("name") == setting_name
    ]


@pytest.mark.parametrize(("builder", "target_setting"), _RAW_BUILDERS)
def test_raw_builder_free_text_cannot_inject_xml_node(
    builder: Builder,
    target_setting: str,
) -> None:
    root = ET.fromstring(builder(_INJECTED_ATTRIBUTE_TEXT))

    assert _setting_values(root, "Injected") == []
    assert _INJECTED_ATTRIBUTE_TEXT in _setting_values(root, target_setting)


@pytest.mark.parametrize(("builder", "target_setting"), _RAW_BUILDERS)
def test_raw_builder_xml_metacharacters_round_trip_as_one_attribute_value(
    builder: Builder,
    target_setting: str,
) -> None:
    root = ET.fromstring(builder(_XML_METACHAR_TEXT))

    assert _XML_METACHAR_TEXT in _setting_values(root, target_setting)


@pytest.mark.parametrize(("builder", "_target_setting"), _RAW_BUILDERS)
def test_raw_builder_rejects_illegal_xml_control_character_before_rendering(
    builder: Builder,
    _target_setting: str,
) -> None:
    with pytest.raises(ValueError):
        builder(_ILLEGAL_XML_TEXT)


def test_document_attr_replacement_preserves_single_quotes_for_apostrophe_value() -> None:
    original_tag = "<setting name='Name' value='before'/>"
    replacement_value = 'driver\'s "callback" & <safe>'

    rewritten = _sub_attr_value(original_tag, "value", replacement_value)

    assert rewritten is not None
    assert "value='" in rewritten
    assert 'value="' not in rewritten
    assert "&apos;" in rewritten
    assert ET.fromstring(rewritten).attrib["value"] == replacement_value


def test_document_attr_replacement_rejects_illegal_xml_control_character() -> None:
    original_tag = '<setting name="Name" value="before"/>'

    with pytest.raises(ValueError):
        _sub_attr_value(original_tag, "value", _ILLEGAL_XML_TEXT)
