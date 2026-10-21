"""Ofgem Levy Exemption Certificates (LECs) issued, GB, by output month, and the share of them from the technologies
Reliable Britain replaces (wind, biomass / plant and animal substances / energy crops, PV), for 0044's pre-August-2015
renewables exemption (ticket 12, D5). Port of ccl-calc/lec.py (0101), reading the five Ofgem files staged by ticket 01
under data/raw/s36/lec/ (sha256 as in ccl-calc/lec.json) without pandas: xlrd for .xls, openpyxl for .xlsx.

GB = England + Scotland + Wales (overseas LECs excluded: imports are kept by RB). The technology share is the period
total's share before April 2008 (spread evenly over the months, an allocation) and each financial year's from 2008-09.
LECs issued, not redeemed (an upper bound); Apr-Jul 2015 not computed (the last Ofgem file ends March 2015)."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path

LEC_DIR = Path(__file__).resolve().parents[2] / "data/raw/s36/lec"
GB = ("England", "Scotland", "Wales")
RB_TECH = ("biomass", "plant/animal", "wind", "photovoltaic")
A = "lecissued_mar01_apr05[2].xls"
B_ = "lecissued_apr05_todate.xls"
C = "renewable-lecs-april-2008---jan-2011_summary.xls"
D = "summary_of_renewable_levy_exemption_certificates_lecs_from_april_2009_to_march_2014_0.xlsx"
E = "summary_of_renewable_levy_exemption_certificates_lecs_from_april_2014_to_march_2015.xlsx"
BLOCKS = [((2002, 1), (2005, 3), (A, "LECs issued to date"), (A, "LECs by Tech&Country")),
          ((2005, 4), (2008, 3), (B_, "LECs issued to date"), (B_, "LECs by Tech&Country")),
          ((2008, 4), (2009, 3), (C, "2008-09 Country"), (C, "2008-09 Technology"))] + [
          ((y, 4), (y + 1, 3), (D, f"{y} - {str(y + 1)[2:]} Country"),
           (D, f"{y} - {str(y + 1)[2:]} Technology" + (" " if y == 2009 else ""))) for y in range(2009, 2014)] + [
          ((2014, 4), (2015, 3), (E, "2014 - 15 Country"), (E, "2014 - 15 Technology"))]


@lru_cache(maxsize=None)
def _rows(fname: str, sheet: str) -> tuple[tuple, ...]:
    """The sheet as rows of Python values: None for empty, datetime for date cells."""
    p = LEC_DIR / fname
    if p.suffix == ".xls":
        import xlrd
        bk = xlrd.open_workbook(str(p))
        sh = bk.sheet_by_name(sheet)
        out = []
        for i in range(sh.nrows):
            row = []
            for c in sh.row(i):
                if c.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    row.append(None)
                elif c.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate_as_datetime(c.value, bk.datemode))
                else:
                    row.append(c.value)
            out.append(tuple(row))
        return tuple(out)
    import openpyxl
    ws = openpyxl.load_workbook(p, read_only=True, data_only=True)[sheet]
    return tuple(tuple(r) for r in ws.iter_rows(values_only=True))


def _num(v) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return float(v)


def _gb_cols(rows, test) -> tuple[int, dict[str, int]]:
    hdr = next(i for i, r in enumerate(rows) if test([str(c).strip() for c in r]))
    return hdr, {str(c).strip(): j for j, c in enumerate(rows[hdr])}


def _gb_sum(r, cols) -> float:
    return sum(v for c in GB if c in cols and cols[c] < len(r) and (v := _num(r[cols[c]])) is not None)


def monthly(fname: str, sheet: str) -> dict[tuple[int, int], float]:
    """GB LECs issued (MWh) by output month."""
    rows = _rows(fname, sheet)
    hdr, cols = _gb_cols(rows, lambda c: "England" in c and "Scotland" in c)
    out = {}
    for r in rows[hdr + 1:]:
        d = next((c for c in r if isinstance(c, dt.datetime)), None)
        if d is not None:
            out[(d.year, d.month)] = _gb_sum(r, cols)
    return out


def tech_share(fname: str, sheet: str) -> float:
    """Share of the period's GB LECs from the technologies RB replaces."""
    rows = _rows(fname, sheet)
    hdr, cols = _gb_cols(rows, lambda c: "England" in c)
    tot = rb = 0.0
    for r in rows[hdr + 1:]:
        name = next((c for c in r if isinstance(c, str)), "")
        if not name or name.lower().startswith(("grand", "total", "data", "notes")):
            continue
        v = _gb_sum(r, cols)
        tot += v
        if any(k in name.lower() for k in RB_TECH):
            rb += v
    return rb / tot


@lru_cache(maxsize=None)
def gb_rbtech_mwh_by_cy() -> dict[int, dict]:
    """By calendar year 2002-2015: GB LECs issued (all technologies) and from RB's technologies, MWh, and months."""
    mon = {}
    for a, b, (mf, ms), (tf, ts) in BLOCKS:
        sh = tech_share(tf, ts)
        for k, v in monthly(mf, ms).items():
            if a <= k <= b:
                mon[k] = (v, v * sh)
    yrs: dict[int, list] = {}
    for (y, _m), (allv, rbv) in mon.items():
        if 2002 <= y <= 2015:
            t = yrs.setdefault(y, [0.0, 0.0, 0])
            t[0] += allv
            t[1] += rbv
            t[2] += 1
    return {y: {"gb_all_mwh": v[0], "gb_rbtech_mwh": v[1], "months": v[2]} for y, v in sorted(yrs.items())}
