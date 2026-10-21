"""ONS CPIH (series L522) and RPI (series CHAW), annual averages, read from the stored ONS CSVs.

CPIH is the Consumer Prices Index including owner occupiers' housing costs: the one inflation
measure both sites use (spec §2, decision 7g). RPI (Retail Prices Index) is read too, because
Ofgem's older price controls were set in RPI terms (spec §2, "Regulatory price bases").

Files: `data/raw/ons/s20c-l522_mm23.csv` and `data/raw/ons/s20c-chaw_mm23.csv`, downloaded
11 Oct 2026 from the ONS time-series generator (dataset MM23, release 16 Sep 2026). The CSV
opens with metadata rows (Title, CDID, ...), then annual rows `"YYYY","value"`, then quarterly
(`"YYYY Qn"`) and monthly (`"YYYY MON"`) rows. Only the annual rows are used here.

This module does not touch `deflator.py` (the retired HMT GDP deflator).
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).parents[2] / "data/raw/ons"
CPIH_CSV = RAW / "s20c-l522_mm23.csv"
RPI_CSV = RAW / "s20c-chaw_mm23.csv"

SOURCE_CPIH = "ons-cpih-l522"
SOURCE_RPI = "ons-rpi-chaw"

_EXPECT = {
    "L522": ("CPIH INDEX 00: ALL ITEMS 2015=100", 2015, 100.0),
    "CHAW": ("RPI All Items Index: Jan 1987=100", None, None),
}


def read_ons_annual(path: Path, cdid: str) -> dict[int, float]:
    """{calendar year: annual average index} from an ONS time-series CSV.

    Fails loudly if the title, the series code or (for CPIH) the 2015 = 100 base has moved.
    """
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    meta = {r[0]: r[1] for r in rows if len(r) >= 2 and not r[0][:4].isdigit()}
    title, base_year, base_val = _EXPECT[cdid]
    if meta.get("CDID") != cdid:
        raise ValueError(f"{path.name}: CDID {meta.get('CDID')!r}, expected {cdid}")
    if meta.get("Title", "").strip() != title:
        raise ValueError(f"{path.name}: title {meta.get('Title')!r}, expected {title!r}")
    out = {int(r[0]): float(r[1]) for r in rows
           if len(r) >= 2 and r[0].isdigit() and len(r[0]) == 4 and r[1]}
    if base_year is not None and out.get(base_year) != base_val:
        raise ValueError(f"{cdid}: {base_year} = {out.get(base_year)}, expected {base_val}")
    return out


@lru_cache(maxsize=None)
def cpih() -> dict[int, float]:
    """CPIH annual average, 2015 = 100 (ONS L522)."""
    return read_ons_annual(CPIH_CSV, "L522")


@lru_cache(maxsize=None)
def rpi() -> dict[int, float]:
    """RPI annual average, Jan 1987 = 100 (ONS CHAW)."""
    return read_ons_annual(RPI_CSV, "CHAW")


def cpih_rebased(base_year: int) -> dict[int, float]:
    """CPIH with `base_year` = 100 (the headline year, spec §2)."""
    idx = cpih()
    if base_year not in idx:
        raise ValueError(f"no CPIH annual average for {base_year}")
    return {y: 100 * v / idx[base_year] for y, v in idx.items()}


def to_real(value_nominal: float, year: int, base_year: int) -> float:
    """Restate money spent in `year` in `base_year` prices with CPIH."""
    idx = cpih()
    return value_nominal * idx[base_year] / idx[year]


def rpi_to_nominal(value: float, price_base_year: int, year: int) -> float:
    """Restate a figure in `price_base_year` RPI prices to `year` money (calendar-year averages)."""
    idx = rpi()
    return value * idx[year] / idx[price_base_year]


def series(base_year: int, years: range = range(2002, 2026)) -> dict[int, dict]:
    """Strand interface: {year: {"index", "basis", "source_id"}}, rebased to `base_year`."""
    idx = cpih_rebased(base_year)
    missing = [y for y in years if y not in idx]
    if missing:
        raise ValueError(f"CPIH missing for {missing}")
    return {y: {"index": idx[y], "basis": "measured", "source_id": SOURCE_CPIH} for y in years}
