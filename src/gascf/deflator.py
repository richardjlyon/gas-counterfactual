"""GDP deflator at market prices, calendar years (HM Treasury, September 2026 QNA).

Outturn to 2025 is ONS series MNF2 as republished by HMT (2025 = 100). From 2026 HMT
prints only the OBR forecast percentage change (March 2026 EFO); those years are built
by compounding it and are flagged as forecast.
"""
from __future__ import annotations

from pathlib import Path

import openpyxl

XLSX = Path(__file__).parents[2] / "data/raw/hmt/GDP_Deflators_Qtrly_National_Accounts_September_2026.xlsx"


def read_deflator() -> tuple[dict[int, float], set[int]]:
    """{calendar year: index, 2025 = 100}, and the set of years that are OBR forecasts."""
    ws = openpyxl.load_workbook(XLSX, read_only=True, data_only=True).worksheets[0]
    idx: dict[int, float] = {}
    growth: dict[int, float] = {}
    for r in ws.iter_rows(values_only=True):
        if len(r) < 10 or r[7] is None:
            continue
        label = str(r[7]).split(" ")[0]
        if not label.isdigit():
            continue
        y = int(label)
        if isinstance(r[8], (int, float)):
            idx[y] = float(r[8])
        elif isinstance(r[9], (int, float)):
            growth[y] = float(r[9])
    if idx.get(2025) != 100:
        raise ValueError("HMT deflator base year moved")
    forecast = set()
    for y in sorted(growth):
        if y not in idx and y - 1 in idx:
            idx[y] = idx[y - 1] * (1 + growth[y] / 100)
            forecast.add(y)
    return idx, forecast


def rebase(value: float, from_year: int, to_year: int) -> float:
    """Re-express a money value from one year's prices in another's."""
    idx, _ = read_deflator()
    return value * idx[to_year] / idx[from_year]
