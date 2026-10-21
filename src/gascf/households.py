"""Great Britain households by calendar year, ONS Labour Force Survey: the engine's one
household count (spec §2; s30, Richard 12 Oct 2026: GB costs over GB households throughout).

England + Wales + Scotland, LFS April-June estimate of each year, used for the whole calendar
year and matched year by year (never one year's count for every year: that is the Subsidy
Clock's 29.0m shortcut, a bridge row). One survey for every nation and year, so the series has
no break where an administrative source starts.

- 2015-2025: ONS, "Households by household size, regions of England and GB constituent
  countries" 2025, sheets England / Wales / Scotland, row "All households" (thousands).
  File `data/raw/ons_households/householdsizebyregionscountries2025.xlsx`.
- 2002-2014: ONS ad hoc 005374, "Households in the UK by region, 1996 to 2017" (LFS, rounded
  to the nearest hundred), rows "England (Total)", "Wales", "Scotland".
  File `data/raw/ons_households/s30-ons005374_households_region_country_1996-2017.xls`.
  The two files overlap 2015-2017 and agree within 0.2% (tested).

Before s30 the engine divided GB costs by UK households (ONS Families and households Table 5),
understating every per-household figure by about 2.7%, while system_costs used a second GB
count (StatsWales, NRS). Both are retired; UK-only cost lines (RO, CCL) are put on a GB basis
in `bills.py`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import openpyxl
import xlrd

RAW = Path(__file__).parents[2] / "data/raw/ons_households"
XLSX = RAW / "householdsizebyregionscountries2025.xlsx"
XLS = RAW / "s30-ons005374_households_region_country_1996-2017.xls"
SOURCE_ID = "ons_lfs_households_by_size_2025"
SOURCE_ID_OLD = "ons-adhoc-005374-households-region-1996-2017"
NATIONS = ("England", "Wales", "Scotland")
_XLS_ROWS = {"England": "England (Total)", "Wales": "Wales", "Scotland": "Scotland"}
FIRST_NEW = 2015          # first year read from the 2025 workbook


@lru_cache(maxsize=None)
def read_lfs_2015_2025() -> dict[str, dict[int, float]]:
    """{nation: {year: households}} 2015-2025 (count, from thousands)."""
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    out = {}
    for nation in NATIONS:
        rows = list(wb[nation].iter_rows(values_only=True))
        if not str(rows[1][0]).startswith(f"{nation}, 2015 to 2025"):
            raise ValueError(f"ONS LFS households: sheet {nation} title changed: {rows[1][0]!r}")
        hdr = next(i for i, r in enumerate(rows) if r[0] and str(r[0]).startswith("Number of households"))
        tot = next(r for r in rows[hdr:] if r[0] == "All households")
        out[nation] = {int(str(v)[:4]): float(tot[j]) * 1000
                       for j, v in enumerate(rows[hdr]) if v and str(v).endswith(" Estimate")}
    return out


@lru_cache(maxsize=None)
def read_lfs_1996_2017() -> dict[str, dict[int, float]]:
    """{nation: {year: households}} 1996-2017 from ONS ad hoc 005374 (count)."""
    sh = xlrd.open_workbook(str(XLS)).sheet_by_index(0)
    if not str(sh.cell_value(0, 0)).startswith("Households in the UK  by region, 1996 to 2017"):
        raise ValueError(f"ONS 005374: title changed: {sh.cell_value(0, 0)!r}")
    if "Labour Force Survey" not in str(sh.cell_value(31, 0)):
        raise ValueError("ONS 005374: source line moved")
    rows = {str(sh.cell_value(r, 0)).strip(): sh.row_values(r) for r in range(sh.nrows)}
    years = [int(v) for v in rows["Region"][1:] if v != ""]
    if years != list(range(1996, 2018)):
        raise ValueError(f"ONS 005374: year header {years}")
    return {n: {y: float(v) for y, v in zip(years, rows[_XLS_ROWS[n]][1:])} for n in NATIONS}


@lru_cache(maxsize=None)
def gb_parts(year: int) -> dict[str, tuple[float, str]]:
    """{nation: (households, source id)} for a calendar year."""
    src, d = (SOURCE_ID, read_lfs_2015_2025()) if year >= FIRST_NEW else (SOURCE_ID_OLD, read_lfs_1996_2017())
    if any(year not in d[n] for n in NATIONS):
        raise KeyError(f"UNSOURCED: no ONS LFS household estimate for GB {year}")
    return {n: (d[n][year], src) for n in NATIONS}


def gb_households_count(year: int) -> float:
    """GB households in `year`, count."""
    return sum(v for v, _ in gb_parts(year).values())


@lru_cache(maxsize=None)
def read_households() -> dict[int, int]:
    """{year: GB households, thousands (rounded)} for 1996-2025."""
    return {y: round(gb_households_count(y) / 1000) for y in range(1996, 2026)}


def households(years: range = range(2002, 2026)) -> dict[int, dict]:
    """Strand interface: {year: {"households": count, "basis", "source_id"}}."""
    return {y: {"households": gb_households_count(y), "basis": "measured",
                "source_id": next(iter(gb_parts(y).values()))[1]} for y in years}


def per_household(gbp_m: float, year: int) -> float:
    """£ per GB household in `year` from a national £m figure in the same year."""
    return gbp_m * 1e6 / gb_households_count(year)
