"""Read cells of Tables 1, 9 and 10 of the UCL preprint (O'Shea, Horne and Maslin 2025, preprint 290 v1) from its
committed text layer (pdftotext -layout). Columns are taken from the character positions of the table's units line
("£ bn" / "£bn"), so a blank cell (Table 1's CFD column before 2017) reads as "". Card [internal ticket] (0175 item 22)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[1] / "data/raw/s36/ucl-oshea/oshea-ucloe-preprint-290-v1.layout.txt"


@lru_cache(maxsize=None)
def table(t: str) -> dict[str, list[str]]:
    """{row label ('2010'..'2023', 'Total'): [cell per data column]} for Table t."""
    lines = LAYOUT.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.lstrip("\f").strip() == f"Table {t}")
    units = next(i for i in range(start, start + 20) if re.match(r"^\s+£ ?bn", lines[i]))
    cols = [m.start() for m in re.finditer(r"£ ?bn|%", lines[units])]
    out: dict[str, list[str]] = {}
    for ln in lines[units + 1:units + 40]:
        lab = ln[:cols[0]].strip()
        if not re.fullmatch(r"20[12]\d|Total", lab):
            if out:
                break
            continue
        bounds = cols + [max(len(ln), cols[-1]) + 1]
        out[lab] = [ln[bounds[j]:bounds[j + 1]].strip() for j in range(len(cols))]
    return out


def cell(rows: dict[str, list[str]], row: str, col: int) -> str:
    """The cell at (row, col); col counts every column on the units line from 0 (Table 10's % column is col 1)."""
    return rows[row][col]
