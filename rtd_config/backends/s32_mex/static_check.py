# rtd_config/backends/s32_mex/static_check.py
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def is_xml_well_formed(path: Path) -> bool:
    """Return True when the .mex file parses as well-formed XML.

    This is a fast static check. It never launches a vendor tool.
    """
    try:
        ET.parse(path)
    except ET.ParseError:
        return False
    return True
