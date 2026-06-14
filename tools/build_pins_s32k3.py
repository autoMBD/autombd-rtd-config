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
# File:        build_pins_s32k3.py
# Author:      autoMBD <tkung.lqk@foxmail.com>
# Date:        2026-06-11
# Version:     0.1.0
# Description: Development-time build script: extracts S32K344 IOMUX data from
#              the NXP IOMUX Excel workbook and writes the committed runtime
#              asset autombd-rtd/assets/nxp/s32k3/port/pins.json.
#              DEVELOPMENT TOOL ONLY — never a runtime dependency of the CLI.
# =================================================================================
"""Build script for autombd-rtd/assets/nxp/s32k3/port/pins.json.

Source workbook (development-time input only — NEVER a runtime dependency):
    D:\\WorkSpace\\ExploreSpace\\Copy of S32K344_S32K324_S32K314_IOMUX.xlsx

Reads the xlsx with stdlib zipfile + xml.etree.ElementTree (no openpyxl).
Parses two sheets:
  - S32K344_Pinout: col A=hdqfp172 pin number, col B=mapbga257 pin, col C=Pin Name
  - S32K344_IO Signal Table: IOMUX signal-to-pin mapping

Column layout in IO Signal Table (0-based indices):
  col A (0)  = Port pin name — carry-forward on blank rows within a pin group
  col B (1)  = CR register: SIUL_MSCRnn, SIUL_IMCRnn, '-' (analog), or '' (output alt)
  col C (2)  = SSS as binary like '0000_0100' — mux select bits
  col D (3)  = Function, e.g. 'LPUART0_TX', 'GPIO[27]', 'FXIO_D0'
  col E (4)  = Module/peripheral, e.g. 'LPUART0', 'FXIO', 'SIUL'
  col G (6)  = Direction: 'O', 'I', or 'I/O'
  col I (8)  = S32K344_257bga (mapbga257) availability value
  col J (9)  = S32K344_172hdqfp (hdqfp172) availability value

Build rules (carry-forward current_pin from col A, current_mscr from the
SIUL_MSCRnn row of each pin group):
  - Skip rows where col C == '-' or col B == '-' (analog-only signals).
  - OUTPUT record: col G == 'O' AND col B not matching SIUL_IMCR.
  - GPIO record:   col G == 'I/O' AND col B matches SIUL_MSCR.
  - INPUT record:  col G == 'I' AND col B matches SIUL_IMCR.

Record schema (every entry in signals[]):
  peripheral    str   - e.g. "LPUART0" (asset-internal form, no underscore)
  signal        str   - derived: strip peripheral prefix+direction from function
  function      str   - verbatim from col D, e.g. "LPUART0_TX"
  mux           str   - same as function
  pin           str   - carry-forward pin name, e.g. "PTA27"
  mscr          int   - MSCR index
  mux_sss       str|null - SSS bits without underscores (output/gpio), null for input
  direction     str   - "output", "input", or "gpio"
  imcr          int|null - IMCR index (input only), null otherwise
  imcr_sss      str|null - IMCR SSS bits (input only), null otherwise
  pin_hdqfp172  str   - hdqfp172 pin number from Pinout sheet
  pin_mapbga257 str   - mapbga257 pin from Pinout sheet

Output file:
  autombd-rtd/assets/nxp/s32k3/port/pins.json
  Top-level: {"family": "s32k3", "device": "s32k344", "package": "default",
              "signals": [...]}
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Source workbook — development-time input ONLY, never a runtime dependency
# ---------------------------------------------------------------------------
DEFAULT_WORKBOOK = Path(
    r"D:\WorkSpace\ExploreSpace\Copy of S32K344_S32K324_S32K314_IOMUX.xlsx"
)

# Output asset path relative to this script's repo root
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
OUTPUT_ASSET = (
    _REPO_ROOT
    / "autombd-rtd"
    / "assets"
    / "nxp"
    / "s32k3"
    / "port"
    / "pins.json"
)

# OOXML namespace
_NS = {"wb": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _col_letter_to_idx(col: str) -> int:
    """Convert column letter string (A, B, AA, …) to 0-based index."""
    result = 0
    for ch in col:
        result = result * 26 + (ord(ch.upper()) - ord("A") + 1)
    return result - 1


def _parse_cell_ref(ref: str) -> tuple[int, int]:
    """Return (col_idx, row_idx) both 0-based from a cell reference like 'B3'."""
    m = re.match(r"([A-Z]+)(\d+)", ref)
    if not m:
        raise ValueError(f"Unparseable cell reference: {ref!r}")
    return _col_letter_to_idx(m.group(1)), int(m.group(2)) - 1


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    """Load the sharedStrings.xml table into a flat list."""
    ss_xml = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    result = []
    for si in ss_xml.findall(".//wb:si", _NS):
        texts = [t.text or "" for t in si.findall(".//wb:t", _NS)]
        result.append("".join(texts))
    return result


def _cell_value(cell_el, shared_strings: list[str]) -> str:
    """Extract the display value of a worksheet cell element."""
    t = cell_el.get("t")
    v_el = cell_el.find("wb:v", _NS)
    if v_el is None:
        return ""
    raw = v_el.text or ""
    if t == "s":
        return shared_strings[int(raw)]
    return raw


def _sheet_rows(
    zf: zipfile.ZipFile, sheet_path: str, shared_strings: list[str]
) -> list[dict[int, str]]:
    """Parse a worksheet into a list of row dicts (col_idx -> value)."""
    ws = ET.fromstring(zf.read(sheet_path))
    rows: list[dict[int, str]] = []
    for row_el in ws.findall(".//wb:row", _NS):
        cells: dict[int, str] = {}
        for c in row_el:
            col_idx, _ = _parse_cell_ref(c.get("r", "A1"))
            cells[col_idx] = _cell_value(c, shared_strings)
        rows.append(cells)
    return rows


def _resolve_sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    """Resolve a human-readable sheet name -> 'xl/worksheets/sheetN.xml'."""
    wb_xml = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))

    # Build r:id -> relative target map
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    id_to_target: dict[str, str] = {}
    for rel in rels_xml.findall(f"{{{rel_ns}}}Relationship"):
        id_to_target[rel.get("Id", "")] = rel.get("Target", "")

    # Find sheet by name
    for sheet_el in wb_xml.findall(".//wb:sheet", _NS):
        if sheet_el.get("name") == sheet_name:
            r_id = sheet_el.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            target = id_to_target.get(r_id, "")
            if not target:
                raise KeyError(f"No rels target for sheet {sheet_name!r}, r:id={r_id!r}")
            return f"xl/{target}"

    raise KeyError(f"Sheet not found in workbook: {sheet_name!r}")


# ---------------------------------------------------------------------------
# Signal derivation helpers
# ---------------------------------------------------------------------------

def _derive_signal(function: str, peripheral: str) -> str:
    """Derive a short signal name from the function string.

    Examples:
      LPUART0_TX  -> TX
      LPUART0_RX  -> RX
      GPIO[4]     -> GPIO
      FXIO_D2     -> D2
      eMIOS_0_CH[17]_Y -> CH[17]_Y
    """
    # GPIO pattern: "GPIO[N]"
    if function.startswith("GPIO["):
        return "GPIO"

    # Strip the peripheral prefix (case-sensitive) and a following underscore
    if function.startswith(peripheral + "_"):
        return function[len(peripheral) + 1:]
    if function.startswith(peripheral):
        return function[len(peripheral):]

    # Fallback: return the function verbatim
    return function


def _strip_underscores(sss: str) -> str:
    """Remove underscores from an SSS string like '0000_0100' -> '00000100'."""
    return sss.replace("_", "")


# ---------------------------------------------------------------------------
# Pinout extraction
# ---------------------------------------------------------------------------

def _extract_pin_packages(
    zf: zipfile.ZipFile, shared_strings: list[str]
) -> dict[str, dict[str, str]]:
    """Extract {pin_name: {hdqfp172: str, mapbga257: str}} from S32K344_Pinout.

    Header is on row 2 (index 1):
      col 0 = S32K344_172hdqfp  (hdqfp172 pin number)
      col 1 = S32K344_257bga    (mapbga257 BGA ball)
      col 2 = Pin Name
    Data rows start at row 3 (index 2).
    """
    sheet_path = _resolve_sheet_path(zf, "S32K344_Pinout")
    all_rows = _sheet_rows(zf, sheet_path, shared_strings)

    packages: dict[str, dict[str, str]] = {}
    # Skip rows 0 (empty header) and 1 (column labels); data from row 2 onward
    for row in all_rows[2:]:
        pin_name = row.get(2, "").strip()
        if not pin_name:
            continue
        hdqfp172 = row.get(0, "").strip()
        mapbga257 = row.get(1, "").strip()
        packages[pin_name] = {"hdqfp172": hdqfp172, "mapbga257": mapbga257}

    return packages


# ---------------------------------------------------------------------------
# IO Signal Table extraction
# ---------------------------------------------------------------------------

_MSCR_RE = re.compile(r"SIUL_MSCR(\d+)")
_IMCR_RE = re.compile(r"SIUL_IMCR(\d+)")


def _extract_signals(
    zf: zipfile.ZipFile,
    shared_strings: list[str],
    pin_packages: dict[str, dict[str, str]],
) -> list[dict]:
    """Extract signal records from S32K344_IO Signal Table.

    Column indices (0-based):
      0  = col A: Port pin name (carry-forward)
      1  = col B: CR register (SIUL_MSCRnn, SIUL_IMCRnn, '-', or '')
      2  = col C: SSS bits
      3  = col D: Function
      4  = col E: Module/peripheral
      6  = col G: Direction ('O', 'I', 'I/O')
      8  = col I: S32K344_257bga availability
      9  = col J: S32K344_172hdqfp availability

    Skip two header rows (rows 1-2), then process data rows.
    """
    sheet_path = _resolve_sheet_path(zf, "S32K344_IO Signal Table")
    all_rows = _sheet_rows(zf, sheet_path, shared_strings)

    signals: list[dict] = []
    current_pin: str = ""
    current_mscr: int | None = None

    # Skip the two header rows (indices 0 and 1)
    for row in all_rows[2:]:
        col_a = row.get(0, "").strip()
        col_b = row.get(1, "").strip()
        col_c = row.get(2, "").strip()
        col_d = row.get(3, "").strip()
        col_e = row.get(4, "").strip()
        col_g = row.get(6, "").strip()

        # Carry-forward pin name from col A
        if col_a:
            current_pin = col_a

        # Carry-forward MSCR index when col B has an MSCR reference
        mscr_m = _MSCR_RE.match(col_b)
        if mscr_m:
            current_mscr = int(mscr_m.group(1))

        # Skip analog-only rows (col B or col C is '-')
        if col_b == "-" or col_c == "-":
            continue

        # Skip rows with no function or no pin context
        if not col_d or not current_pin or current_mscr is None:
            continue

        pkg = pin_packages.get(current_pin, {})
        hdqfp172 = pkg.get("hdqfp172", "")
        mapbga257 = pkg.get("mapbga257", "")

        peripheral = col_e
        function = col_d
        signal = _derive_signal(function, peripheral)

        if col_g == "O" and not _IMCR_RE.match(col_b):
            # OUTPUT record: col B is '' (alternate function output) or MSCR row itself
            signals.append({
                "peripheral": peripheral,
                "signal": signal,
                "function": function,
                "mux": function,
                "pin": current_pin,
                "mscr": current_mscr,
                "mux_sss": _strip_underscores(col_c) if col_c else None,
                "direction": "output",
                "imcr": None,
                "imcr_sss": None,
                "pin_hdqfp172": hdqfp172,
                "pin_mapbga257": mapbga257,
            })

        elif col_g == "I/O" and mscr_m:
            # GPIO record: the MSCR row itself with direction I/O (GPIO function)
            signals.append({
                "peripheral": peripheral,
                "signal": signal,
                "function": function,
                "mux": function,
                "pin": current_pin,
                "mscr": current_mscr,
                "mux_sss": _strip_underscores(col_c) if col_c else None,
                "direction": "gpio",
                "imcr": None,
                "imcr_sss": None,
                "pin_hdqfp172": hdqfp172,
                "pin_mapbga257": mapbga257,
            })

        elif col_g == "I":
            imcr_m = _IMCR_RE.match(col_b)
            if imcr_m:
                # INPUT record: col B is SIUL_IMCRnn
                signals.append({
                    "peripheral": peripheral,
                    "signal": signal,
                    "function": function,
                    "mux": function,
                    "pin": current_pin,
                    "mscr": current_mscr,
                    "mux_sss": None,
                    "direction": "input",
                    "imcr": int(imcr_m.group(1)),
                    "imcr_sss": _strip_underscores(col_c) if col_c else None,
                    "pin_hdqfp172": hdqfp172,
                    "pin_mapbga257": mapbga257,
                })

    return signals


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build(workbook_path: Path, output_path: Path) -> int:
    """Extract IOMUX data and write pins.json. Returns total signal count."""
    if not workbook_path.exists():
        print(
            f"ERROR: workbook not found: {workbook_path}\n"
            "This script requires the NXP IOMUX Excel workbook at the path above.\n"
            "It is a DEVELOPMENT-TIME tool only — the workbook is not shipped with the repo.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Reading workbook: {workbook_path}")

    with zipfile.ZipFile(workbook_path) as zf:
        shared_strings = _load_shared_strings(zf)
        pin_packages = _extract_pin_packages(zf, shared_strings)
        signals = _extract_signals(zf, shared_strings, pin_packages)

    asset = {
        "family": "s32k3",
        "device": "s32k344",
        "package": "default",
        "signals": signals,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total = len(signals)
    n_output = sum(1 for s in signals if s["direction"] == "output")
    n_gpio = sum(1 for s in signals if s["direction"] == "gpio")
    n_input = sum(1 for s in signals if s["direction"] == "input")
    print(
        f"Wrote {output_path}\n"
        f"  Total signals : {total}\n"
        f"  Output records: {n_output}\n"
        f"  GPIO records  : {n_gpio}\n"
        f"  Input records : {n_input}\n"
        f"  Pinout pins   : {len(pin_packages)}"
    )
    return total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build S32K344 pin-mux asset from IOMUX workbook."
    )
    parser.add_argument(
        "--workbook",
        default=str(DEFAULT_WORKBOOK),
        help="Path to the NXP IOMUX xlsx workbook (development-time source).",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_ASSET),
        help="Path to write the output pins.json asset.",
    )
    args = parser.parse_args()

    total = build(Path(args.workbook), Path(args.output))
    print(f"Done. len(signals) = {total}")
