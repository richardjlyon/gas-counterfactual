"""The same-in-both block (spec S1, §8; §15.1 decision 6): bill items that are identical in
net-zero Britain and fossil Britain, so they set the *height* of both bills but never the gap.

Four items, calendar years 2002–2025, money of the day (nominal) and per UK household:

1. **Local wires (DUoS, distribution use of system):** what the 14 GB distribution network
   operators (DNOs, the companies that own the local poles and cables) were allowed to, or did,
   recover from all customers, domestic and non-domestic. Spliced from Ofgem's price-control
   documents, financial-year (April–March) values turned into calendar years (3/12 + 9/12):

   - FY2001/02–2003/04: DPCR3 Final Proposals (Dec 1999), Tables 1–14, line 17 "Adj price
     control rev" (£m 1997/98 prices). Allowance, tagged ``estimated``.
   - FY2004/05–2009/10: DPCR4 Final Proposals (Nov 2004), Appendix "Price control
     calculations for …", line 22 "Price control revenue" (£m 2002/03 prices). Allowance,
     ``estimated``.
   - FY2010/11–2014/15: DPCR5 Final Proposals, Financial methodologies, line 25 "Base price
     control revenue (after profiling)" (£m 2007/08 prices). Allowance, ``estimated``.
   - FY2015/16–2022/23: RIIO-ED2 Price Control Financial Model (PCFM) V5 (June 2026), each
     DNO sheet, row "Regulated Distribution Network Revenue" (RD, £m nominal), which is the
     revenue actually collected under RIIO-ED1. ``measured``.
   - FY2023/24–2025/26: same PCFM, row "Revenue as billed (ignoring bad debt)" (BILLRt, £m
     nominal). ``measured``.

   Real-price allowances are put into money of the day with the ONS RPI (CHAW, April–March
   average), the index the price controls were set in. Allowances differ from collected
   revenue by the correction factor (K), typically a few per cent.

2. **Metering:** DPCR3 line 18 "DMS revenue" (distribution metering services) for
   FY2001/02–2003/04 (national, ``estimated``); for 2017–2025 the Ofgem default tariff cap
   "SMNCC" allowance (smart-meter net cost change) per typical domestic electricity customer.
   2007–2016: £0 here because meters sit inside supplier operating costs (Ofgem SMI row 35
   "Operational (inc. meters and smart meters)"; CMA 2016 appendix 9.11 para 25 counts
   metering as an indirect cost). 2004–2006 metering was removed from the DNO price control
   (DPCR4 line 33 "Exclude metering") and is a GAP; so is all non-domestic metering. Legacy
   metering inside the cap's operating-cost allowance (OC) is counted under supplier costs.

3. **Supplier operating costs and margin:** the default tariff cap allowances per typical
   domestic electricity customer (single-rate, "other payment method", typical consumption):
   OC + PAAC + PAP + HAP (to Mar 2025) and CO + DRC + IC + HAP (from Apr 2025), plus EBIT
   (the supplier margin). Cap periods are time-weighted into calendar years 2017 (Jan–Mar
   carried from the first cap, labelled) to 2025. 2002–2016 from Ofgem's own supplier-cost
   publications (``supplier_history``: SMI 2009–13 measured; RMI 2014–16, CMA/Probe 2007–08
   and a DCMR-anchored range 2002–06, all estimated). Domestic only: non-domestic supply
   costs are a GAP.

4. **VAT on the block:** domestic electricity is charged the reduced rate, 5% since
   1 September 1997 (HMRC VAT Fuel and Power manual VFUP1000, read from the stored page);
   most business customers recover VAT, so VAT on non-domestic use is not a cost to Britain.
   VAT = 5% × (domestic share of DUoS + supplier + metering), per household. Cross-check:
   DUKES 2026 Table 1.2, domestic electricity VAT ÷ (market value − VAT) ≈ 5% every year.

Per-household figures divide national £m by GB households (households.py). Supplier and SMNCC
figures are already per domestic customer and are used as per household without scaling: a
deliberate choice, flagged in the notes (the cost to Britain per household is larger once
non-domestic supply costs are added, so leaving them out makes the bills lower, never the gap).

Everything here is identical on both sides; ``block()`` returns one value per item per year
and ``both_bills()`` hands the same dict to each side (a test proves they are identical).
"""
from __future__ import annotations

import csv
import re
from datetime import date
from functools import lru_cache
from html import unescape
from pathlib import Path

import openpyxl

from gascf import households as hh

ROOT = Path(__file__).parents[2]
RAW = ROOT / "data/raw"
DPCR3 = RAW / "ofgem_s20e/s20e-DPCR3_FP_Dec1999.txt"
DPCR4 = RAW / "ofgem_s20e/s20e-DPCR4_FP_Nov2004.txt"
DPCR5 = RAW / "ofgem_s20e/s20e-DPCR5_FP_financial.txt"
ED2_PCFM = RAW / "ofgem_s20e/s20e-ED2_PCFM_V5_2026-06.xlsx"
CAP = RAW / "ofgem/Default-tariff-cap-level-v1.31.xlsx"
RPI_CSV = RAW / "ons/s20c-chaw_mm23.csv"
VFUP1000 = RAW / "hmrc/s20e-HMRC_VFUP_vfup1000.html"
DUKES_12 = RAW / "dukes_s20e/s20e-DUKES_1.2.xlsx"
SMI = RAW / "ofgem/s21a-SMI_chart_data_as_of_april_2015.xlsx"
RMI_DUAL = RAW / "ofgem/s21a-RMI_everviz_H2G7IL0vq_dual_fuel_bill_breakdown.js"
CMA_IND = RAW / "cma/s21a-CMA_EMI_FR_appendix_9-11_indirect_costs.txt"
PROBE = RAW / "ofgem/s21a-Energy_Supply_Probe_IFR_Oct2008.txt"
DCMR = RAW / "ofgem/s21a-DCMR2004_ch4-7.txt"
QEP221 = RAW / "desnz_qep/s21a-QEP_table_221.xlsx"

DNO_SHEETS = ("ENWL", "NPgN", "NPgY", "WMID", "EMID", "SWALES", "SWEST",
              "LPN", "SPN", "EPN", "SPD", "SPMW", "SSEH", "SSES")
YEARS = range(2002, 2026)

SRC = {
    "dpcr3": "ofgem-dpcr3-fp-dec1999-t1-14",
    "dpcr4": "ofgem-dpcr4-fp-nov2004-appx-pcc",
    "dpcr5": "ofgem-dpcr5-fp-financial-dec2009-pcc",
    "ed2pcfm": "ofgem-riio-ed2-pcfm-v5-2026-06",
    "cap": "ofgem-default-tariff-cap-level-v1.31-t1b",
    "rpi": "ons-rpi-chaw",
    "vat": "hmrc-vfup1000",
    "dukes12": "desnz-dukes-2026-t1.2",
    "smi": "ofgem-smi-chart-data-apr2015-elec",
    "rmi": "ofgem-rmi-dual-fuel-bill-breakdown-css",
    "cma": "cma-emi-2016-appx-9.11-annexA-t1",
    "probe": "ofgem-energy-supply-probe-oct2008-p8.6",
    "dcmr": "ofgem-dcmr-2004-fig4.2",
    "qep221": "desnz-qep-2.2.1-3300kwh",
    "hh": hh.SOURCE_ID,
}

_NUM = r"\(?-?[\d,]+\.?\d*\)?"


def _num(s: str) -> float:
    s = s.replace(",", "")
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()"))
    return -v if neg else v


# --------------------------------------------------------------------------- RPI


@lru_cache(maxsize=1)
def rpi_monthly() -> dict[tuple[int, int], float]:
    """{(year, month): RPI} from the ONS CHAW CSV (Jan 1987 = 100)."""
    months = {m: i for i, m in enumerate(
        "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), start=1)}
    with RPI_CSV.open(newline="") as f:
        rows = list(csv.reader(f))
    meta = {r[0]: r[1] for r in rows if len(r) >= 2}
    if meta.get("CDID") != "CHAW":
        raise ValueError(f"{RPI_CSV.name}: CDID {meta.get('CDID')!r}, expected CHAW")
    out = {}
    for r in rows:
        if len(r) >= 2 and re.fullmatch(r"\d{4} [A-Z]{3}", r[0]) and r[1]:
            y, m = r[0].split()
            out[(int(y), months[m])] = float(r[1])
    return out


def rpi_fy(fy_end: int) -> float:
    """April (fy_end−1) to March (fy_end) average RPI. Raises if any month is missing."""
    m = rpi_monthly()
    keys = [(fy_end - 1, k) for k in range(4, 13)] + [(fy_end, k) for k in range(1, 4)]
    missing = [k for k in keys if k not in m]
    if missing:
        raise KeyError(f"RPI months missing for FY ending {fy_end}: {missing[:3]}…")
    return sum(m[k] for k in keys) / 12


def to_nominal(value: float, price_fy_end: int, fy_end: int) -> float:
    """Restate £m in FY `price_fy_end` RPI prices into FY `fy_end` money of the day."""
    return value * rpi_fy(fy_end) / rpi_fy(price_fy_end)


# --------------------------------------------------------------------------- DPCR readers


@lru_cache(maxsize=1)
def read_dpcr3() -> dict[str, dict[int, dict[str, float]]]:
    """{DNO: {FY end: {"duos": £m, "dms": £m}}} in 1997/98 prices, FY2001/02–2003/04.

    DPCR3 Final Proposals, Tables 1–14, "CALCULATION OF PRICE CONTROL REVENUE FOR <DNO>
    (£MILLION 1997/98 PRICES)", line 17 "Adj price control rev" and line 18 "DMS revenue"
    (columns 1999/00 … 2004/05; 1999/00 is the old control's base year).
    """
    t = DPCR3.read_text()
    parts = re.split(r"TABLE \d+:\s+CALCULATION OF PRICE CONTROL REVENUE FOR", t)[1:]
    if len(parts) != 14:
        raise ValueError(f"DPCR3: expected 14 DNO tables, found {len(parts)}")
    out = {}
    for p in parts:
        head = p[: p.find("(£MILLION")]
        if "1997/98 PRICES" not in p[:300]:
            raise ValueError("DPCR3: price base '1997/98 PRICES' not found")
        name = " ".join(head.split())
        cols = re.search(r"1999/00\s+2000/01\s+2001/02\s+2002/03\s+2003/04\s+2004/05", p)
        adj = re.search(r"^\s*17\s+Adj price control rev\s+((?:\d+\s+){5}\d+)", p, re.M)
        dms = re.search(r"^\s*18\s+DMS revenue\s+((?:\d+\s+){5}\d+)", p, re.M)
        if not (cols and adj and dms):
            raise ValueError(f"DPCR3 {name}: column header or line 17/18 not found")
        a = [float(x) for x in adj.group(1).split()]
        d = [float(x) for x in dms.group(1).split()]
        # index 3 = 2002/03, 4 = 2003/04
        # columns: 0 = 1999/00 (old control), 1 = 2000/01, 2 = 2001/02, 3 = 2002/03, 4 = 2003/04
        out[name] = {fy: {"duos": a[i], "dms": d[i]} for fy, i in ((2002, 2), (2003, 3), (2004, 4))}
    return out


@lru_cache(maxsize=1)
def read_dpcr4() -> dict[str, dict[int, float]]:
    """{DNO: {FY end: £m 2002/03 prices}} for FY2004/05–2009/10, line 22 "Price control revenue".

    Six values under the headers 2004/05 … 2009/10. DPCR4 ran April 2005–March 2010; the
    2004/05 figure is Ofgem's estimate of the last DPCR3 year (the base the P0 cut applies
    to), and it is used for FY2004/05 in preference to DPCR3's 1999 forecast.
    """
    t = DPCR4.read_text()
    blocks = t.split("PRICE CONTROL CALCULATIONS FOR ")[1:]
    if len(blocks) != 14:
        raise ValueError(f"DPCR4: expected 14 DNO blocks, found {len(blocks)}")
    out = {}
    for b in blocks:
        name = b.splitlines()[0].strip()
        if "2002/03 Prices" not in b[:200]:
            raise ValueError(f"DPCR4 {name}: '2002/03 Prices' not found")
        if not re.search(r"2004/05\s+2005/06\s+2006/07\s+2007/08\s+2008/09\s+2009/10", b[:600]):
            raise ValueError(f"DPCR4 {name}: column header moved")
        m = re.search(r"^\s*22\s+Price control revenue\s+((?:[\d,.]+\s+){5}[\d,.]+)\s*$", b, re.M)
        if not m:
            raise ValueError(f"DPCR4 {name}: line 22 not found")
        v = [_num(x) for x in m.group(1).split()]
        out[name] = dict(zip(range(2005, 2011), v))
    return out


@lru_cache(maxsize=1)
def read_dpcr5() -> dict[str, dict[int, float]]:
    """{DNO: {FY end: £m 2007/08 prices}} FY2010/11–2014/15, line 25 "Base price control revenue
    (after profiling)" (the 09-10 column is blank "-" on that line)."""
    t = DPCR5.read_text()
    pat = re.compile(
        r"\n\s{2,}(\S[^\n]*?)\s{5,}09-10\s+10-11\s+11-12\s+12-13\s+13-14\s+14-15\s+Total.*?"
        r"\n\s*25 Base price control revenue \(after profiling\)\s+-\s+"
        r"((?:" + _NUM + r"\s+){5})", re.S)
    out = {}
    for m in pat.finditer(t):
        if "£m 07/08" not in t[m.end(1): m.end(1) + 400]:
            raise ValueError(f"DPCR5 {m.group(1)}: '£m 07/08' price base not found")
        v = [_num(x) for x in m.group(2).split()]
        out[m.group(1).strip()] = dict(zip(range(2011, 2016), v))
    if len(out) != 14:
        raise ValueError(f"DPCR5: expected 14 DNO tables, found {len(out)}: {list(out)}")
    return out


@lru_cache(maxsize=1)
def read_ed_pcfm() -> dict[str, dict[int, float]]:
    """{"RD"|"BILLRt": {FY end: £m nominal, sum of 14 DNOs}} from the RIIO-ED2 PCFM V5.

    RD = "Regulated Distribution Network Revenue" (RIIO-ED1 actual, FY2015/16–2022/23);
    BILLRt = "Revenue as billed (ignoring bad debt)" (RIIO-ED2, FY2023/24 on). Only years
    where all 14 DNOs report are kept.
    """
    wb = openpyxl.load_workbook(ED2_PCFM, read_only=True, data_only=True)
    want = {"RD": "Regulated Distribution Network Revenue",
            "BILLRt": "Revenue as billed (ignoring bad debt)"}
    acc: dict[str, dict[int, list[float]]] = {k: {} for k in want}
    for s in DNO_SHEETS:
        rows = list(wb[s].iter_rows(min_row=1, max_row=420, values_only=True))
        hdr = rows[3]
        if not str(hdr[4] or "").startswith("PCFM year end"):
            raise ValueError(f"PCFM {s}: year header row moved")
        for code, label in want.items():
            r = next((r for r in rows if r[7] == code and str(r[4] or "").strip() == label), None)
            if r is None:
                raise ValueError(f"PCFM {s}: row {code} '{label}' not found")
            if r[6] != "£m nominal":
                raise ValueError(f"PCFM {s} {code}: units {r[6]!r}")
            for j, v in enumerate(r):
                if j >= 9 and isinstance(v, (int, float)) and hasattr(hdr[j], "year"):
                    acc[code].setdefault(hdr[j].year, []).append(float(v))
    return {k: {y: sum(v) for y, v in d.items() if len(v) == len(DNO_SHEETS)}
            for k, d in acc.items()}


# --------------------------------------------------------------------------- DUoS series


@lru_cache(maxsize=1)
def duos_fy() -> dict[int, dict]:
    """{FY end: {"gbp_m", "basis", "source_id", "note"}}, nominal £m, all GB customers."""
    out = {}
    d3 = read_dpcr3()
    for fy in (2002, 2003, 2004):
        real = sum(v[fy]["duos"] for v in d3.values())
        out[fy] = {"gbp_m": to_nominal(real, 1998, fy), "basis": "estimated",
                   "source_id": SRC["dpcr3"], "note": f"allowance £{real:.0f}m 1997/98 prices, RPI"}
    d4 = read_dpcr4()
    for fy in range(2005, 2011):
        real = sum(v[fy] for v in d4.values())
        out[fy] = {"gbp_m": to_nominal(real, 2003, fy), "basis": "estimated",
                   "source_id": SRC["dpcr4"], "note": f"allowance £{real:.1f}m 2002/03 prices, RPI"}
    d5 = read_dpcr5()
    for fy in range(2011, 2016):
        real = sum(v[fy] for v in d5.values())
        out[fy] = {"gbp_m": to_nominal(real, 2008, fy), "basis": "estimated",
                   "source_id": SRC["dpcr5"], "note": f"allowance £{real:.1f}m 2007/08 prices, RPI"}
    pc = read_ed_pcfm()
    for fy, v in pc["RD"].items():
        if 2016 <= fy <= 2023:
            out[fy] = {"gbp_m": v, "basis": "measured", "source_id": SRC["ed2pcfm"],
                       "note": "RD, collected, nominal"}
    for fy, v in pc["BILLRt"].items():
        if 2024 <= fy <= 2026:
            out[fy] = {"gbp_m": v, "basis": "measured", "source_id": SRC["ed2pcfm"],
                       "note": "BILLRt, billed, nominal"}
    missing = [fy for fy in range(2002, 2027) if fy not in out]
    if missing:
        raise ValueError(f"DUoS: no figure for FY ending {missing}")
    return out


def fy_to_cy(series: dict[int, dict], year: int, key: str = "gbp_m") -> tuple[float, str, str]:
    """Calendar year = 3/12 of the FY ending in `year` + 9/12 of the FY ending `year`+1.
    Basis is the weaker of the two (estimated < measured) and at best ``modelled`` because
    the split is a weighting, not a reading."""
    a, b = series[year], series[year + 1]
    v = 0.25 * a[key] + 0.75 * b[key]
    basis = "estimated" if "estimated" in (a["basis"], b["basis"]) else "modelled"
    src = a["source_id"] if a["source_id"] == b["source_id"] else f'{a["source_id"]}+{b["source_id"]}'
    return v, basis, src


@lru_cache(maxsize=1)
def metering_dms_fy() -> dict[int, float]:
    """DPCR3 DMS revenue, nominal £m, FY2001/02–2003/04 (the only DNO metering lines)."""
    d3 = read_dpcr3()
    return {fy: to_nominal(sum(v[fy]["dms"] for v in d3.values()), 1998, fy)
            for fy in (2002, 2003, 2004)}


# --------------------------------------------------------------------------- price cap


_MON = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
SUPPLIER_LINES = ("OC", "PAAC", "PAP", "HAP", "CO", "DRC", "IC", "EBIT")
METERING_LINES = ("SMNCC",)


def _period(label: str) -> tuple[date, date]:
    """'Apr 2017 - Sep 2017' → (1 Apr 2017, 1 Oct 2017), end exclusive."""
    m = re.match(r"([A-Z][a-z]+) (\d{4}) - ([A-Z][a-z]+) (\d{4})", label.strip())
    if not m or m.group(1)[:3] not in _MON or m.group(3)[:3] not in _MON:
        raise ValueError(f"cap period label not understood: {label!r}")
    s = date(int(m.group(2)), _MON[m.group(1)[:3]], 1)
    em, ey = _MON[m.group(3)[:3]] + 1, int(m.group(4))
    if em == 13:
        em, ey = 1, ey + 1
    return s, date(ey, em, 1)


@lru_cache(maxsize=1)
def read_cap() -> list[tuple[date, date, dict[str, float]]]:
    """Ofgem default tariff cap, sheet '1b Historical level tables', block "Other Payment
    Method", sub-table "Typical consumption" for "Electricity: Single-Rate Metering
    Arrangement": per period, £ per customer per year excl. VAT, nominal."""
    ws = openpyxl.load_workbook(CAP, read_only=True, data_only=True)["1b Historical level tables"]
    rows = list(ws.iter_rows(min_row=1, max_row=48, values_only=True))
    if not str(rows[7][1] or "").startswith("Other Payment Method"):
        raise ValueError(f"cap 1b: 'Other Payment Method' anchor moved: {rows[7][1]!r}")
    if not str(rows[9][1] or "").startswith("Electricity: Single"):
        raise ValueError(f"cap 1b: 'Electricity: Single-Rate' anchor moved: {rows[9][1]!r}")
    hi = next((i for i in range(10, 40) if str(rows[i][1] or "").startswith("Typical cons")), None)
    if hi is None:
        raise ValueError("cap 1b: 'Typical consumption' sub-table not found")
    hdr = rows[hi]
    body = {}
    for r in rows[hi + 1: hi + 17]:
        if r[1] is None:
            break
        body[str(r[1]).strip()] = r
    for need in SUPPLIER_LINES + METERING_LINES + ("DF", "NC", "Total_GB average"[:8]):
        if not any(k.startswith(need) for k in body):
            raise ValueError(f"cap 1b: line {need!r} missing")
    out = []
    # The single-rate block runs from column C until the next sub-table label (the Multi-rate,
    # Gas and Dual fuel blocks follow to the right and must not be read). Blank spacer
    # columns inside the block (one sits between Apr–Sep 2022 and Oct–Dec 2022) are skipped.
    for j in range(2, len(hdr)):
        h = hdr[j]
        if isinstance(h, str) and h.strip().startswith(("Typical cons", "Nil cons")):
            break
        if not isinstance(h, str) or " - " not in h:
            continue
        s, e = _period(h)
        vals = {}
        for k, r in body.items():
            v = r[j]
            vals[k] = float(v) if isinstance(v, (int, float)) else 0.0  # '-' = not in use then
        out.append((s, e, vals))
    if not out or out[0][0] != date(2017, 4, 1):
        raise ValueError("cap 1b: first period should start Apr 2017")
    return out


def cap_calendar_year(year: int, lines: tuple[str, ...]) -> tuple[float, str]:
    """Time-weighted mean of the cap periods inside `year`, £/customer/yr nominal, summed over
    `lines`. Jan–Mar 2017 (before the first cap) takes the Apr 2017 value: basis ``estimated``."""
    caps = read_cap()
    y0, y1 = date(year, 1, 1), date(year + 1, 1, 1)
    total, days, basis = 0.0, 0, "modelled"
    for s, e, vals in caps:
        a, b = max(s, y0), min(e, y1)
        if a < b:
            n = (b - a).days
            total += n * sum(vals.get(k, 0.0) for k in lines)
            days += n
    full = (y1 - y0).days
    if days < full:
        first = caps[0]
        if year == 2017:
            n = (first[0] - y0).days
            total += n * sum(first[2].get(k, 0.0) for k in lines)
            days += n
            basis = "estimated"
        else:
            raise KeyError(f"cap does not cover {year}")
    return total / days, basis


# --------------------------------------------------------------------------- supplier costs before the cap
#
# One denominator: £ per typical domestic electricity customer per year, excl. VAT, money of
# the day, the same denominator as the cap allowances used for 2017-2025 (and, like them,
# used as per household). Local wires stay national £m ÷ households (spec §2); that mismatch
# is unchanged from s20e and documented there (domestic-only supplier costs).


@lru_cache(maxsize=1)
def read_smi() -> dict:
    """Ofgem Supply Market Indicator chart data (April 2015), sheet 'Electricity data':
    row 37 'TOTAL' of 'Supplier operating costs' and row 45 'Pre-tax margin', columns B-F =
    calendar 2009-2013 CSS actuals in 2014 prices; column G = Jan-Dec 2014 SMI estimate (cash).
    Restated to money of the day with the workbook's own 'Inflation' tab factors (RPI CHAW,
    'For inflating CSS figures to express in current prices', row 6 columns E-I)."""
    wb = openpyxl.load_workbook(SMI, data_only=True)
    e, inf = wb["Electricity data"], wb["Inflation"]
    anchors = {"A34": "Supplier operating costs", "A37": "TOTAL", "A43": "Revenue",
               "A45": "Pre-tax margin", "B5": "CSS (historic actuals)", "G5": "SMI"}
    for cell, text in anchors.items():
        if not str(e[cell].value or "").strip().startswith(text):
            raise ValueError(f"SMI 'Electricity data' {cell}: expected {text!r}, got {e[cell].value!r}")
    if "2014 prices" not in str(e["B1"].value):
        raise ValueError("SMI: note on 2014 prices moved")
    out = {}
    for col, fcol, y in zip("BCDEF", "EFGHI", range(2009, 2014)):
        if not str(e[f"{col}7"].value).startswith(f"Jan-{y % 100:02d} to Dec-{y % 100:02d}"):
            raise ValueError(f"SMI {col}7 is not calendar {y}: {e[col + '7'].value!r}")
        if inf[f"{fcol}5"].value != f"{y} to 2014":
            raise ValueError(f"SMI Inflation {fcol}5 is not '{y} to 2014'")
        f = 1 + float(inf[f"{fcol}6"].value)
        out[y] = {"opex": e[f"{col}37"].value / f, "margin": e[f"{col}45"].value / f,
                  "revenue": e[f"{col}43"].value / f, "basis": "measured"}
    if not str(e["G7"].value).startswith("Jan-14 to Dec-14"):
        raise ValueError("SMI G7 is not Jan-Dec 2014")
    out[2014] = {"opex": e["G37"].value, "margin": e["G45"].value, "revenue": e["G43"].value,
                 "basis": "estimated"}           # SMI forward-looking estimate, cross-check only
    return out


@lru_cache(maxsize=1)
def read_rmi_dual() -> dict[int, dict[str, float]]:
    """Ofgem Retail Market Indicators chart 'Large legacy suppliers: Domestic dual fuel bill
    breakdown over time' (everviz H2G7IL0vq; source: Ofgem analysis of Consolidated Segmental
    Statements, CSS): £ per dual-fuel customer, nominal, 2009-2020. Columns 'Operating costs'
    (incl. depreciation and amortisation) and 'EBIT'."""
    import json
    t = RMI_DUAL.read_text()
    if "Large legacy suppliers: Domestic dual fuel bill breakdown over time" not in t:
        raise ValueError("RMI chart title changed")
    i = t.find("var options = ")
    o = json.loads(t[i + 14:t.find("\n", i)].rstrip(";"))
    rows = [r.split(";") for r in o["data"]["csv"].splitlines()]
    hdr = [h.strip('"') for h in rows[0]]
    jo, je = hdr.index("Operating costs"), hdr.index("EBIT")
    return {int(r[0]): {"opex": float(r[jo]), "ebit": float(r[je])} for r in rows[1:] if r[0].isdigit()}


@lru_cache(maxsize=1)
def read_cma_indirect() -> dict[int, float]:
    """CMA Energy Market Investigation final report (June 2016), Appendix 9.11, Annex A
    Table 1 'Total supply business indirect cost ratios over the relevant period for the Six
    Large Energy Firms combined' (£ per account, FY2007 prices, CPI), turned back into money of
    the day with the appendix's own Table 1 'Annual CPI and associated deflator' (December
    year-ends; the majority of the six). Returns {calendar year: £ per account, nominal}."""
    t = CMA_IND.read_text()
    a = t.find("Table 1: Total supply business indirect cost ratios over the relevant period for the Six Large\nEnergy Firms combined")
    if a < 0:
        raise ValueError("CMA 9.11 Annex A Table 1 (combined) not found")
    real = {2000 + int(m[0]): float(m[1]) for m in re.findall(r"^ FY(\d\d)\s+(\d+)\s", t[a:a + 1500], re.M)}
    d = t.find("Table 1: Annual CPI and associated deflator")
    if d < 0:
        raise ValueError("CMA 9.11 CPI deflator table not found")
    defl = {int(m[0]): float(m[2]) / 100
            for m in re.findall(r"December (\d{4})\s.*?([\d.]+)%\s+([\d.]+)%", t[d:d + 3000])}
    if set(real) != set(range(2007, 2015)) or set(defl) != set(range(2007, 2015)):
        raise ValueError(f"CMA 9.11 years moved: {sorted(real)} / {sorted(defl)}")
    return {y: real[y] / defl[y] for y in real}


def _quote(path: Path, quote: str) -> str:
    t = re.sub(r"\s+", " ", path.read_text())
    if quote not in t:
        raise ValueError(f"{path.name}: quote missing: {quote[:60]}…")
    return quote


@lru_cache(maxsize=1)
def probe_margin() -> float:
    """Ofgem Energy Supply Probe initial findings (6 Oct 2008), para 8.6: 'the average
    pre-tax margin on sales in energy supply between 2005 and 2007 (inclusive) was around 2 per
    cent'. Returned as a fraction."""
    _quote(PROBE, "we estimate the average pre-tax margin on sales in energy supply between "
                  "2005 and 2007 (inclusive) was around 2 per cent")
    return 0.02


@lru_cache(maxsize=1)
def dcmr_supply_share() -> float:
    """Ofgem Domestic Competitive Market Review 2004 (April 2004), Figure 4.2 'Breakdown of
    domestic direct debit electricity bill': 'Supply costs and margin, 26%' of a bill incl.
    VAT (Appendix 5 para 1.2: 3,300 kWh; network and metering from 2003/04 charging statements,
    so metering is NOT inside this share). Returned as a fraction."""
    t = DCMR.read_text()
    i = t.find("Figure 4.2: Breakdown of domestic direct debit electricity bill")
    seg = re.sub(r"\s+", " ", t[i:i + 1500]) if i >= 0 else ""
    if not all(x in seg for x in ("Supply costs and margin, 26%", "Distribution and metering, 25%",
                                  "VAT, 5%")):
        raise ValueError("DCMR 2004 Figure 4.2 labels moved")
    return 0.26


@lru_cache(maxsize=1)
def qep_elec_bill_3300() -> dict[int, dict[str, float]]:
    """DESNZ QEP Table 2.2.1, sheet '2.2.1 3,300kWh' (cash terms, incl. VAT, UK, 3,300 kWh):
    'Direct debit' all consumers and 'Overall' UK, £ per year."""
    rows = list(openpyxl.load_workbook(QEP221, read_only=True, data_only=True)["2.2.1 3,300kWh"]
                .iter_rows(values_only=True))
    if not (str(rows[3][6]).startswith("Direct debit") and rows[3][14] == "Overall"
            and str(rows[4][8]).startswith("All cons") and rows[5][0] == "Cash terms"):
        raise ValueError("QEP 2.2.1 3,300kWh header moved")
    out = {}
    for r in rows[6:]:
        if r[0] is not None:                     # 'Real terms' block starts: stop
            break
        y = int(str(r[1])[:4])
        out[y] = {"dd": float(r[8]), "overall": float(r[14])}
    return out


@lru_cache(maxsize=1)
def supplier_history() -> dict[int, dict]:
    """Supplier operating costs + margin, £ per typical domestic electricity customer per
    year, excl. VAT, nominal, 2002-2016 (the cap covers 2017 on). See notes.md for the method.

    - 2009-2013: SMI CSS actuals, electricity, operating costs (row 37, incl. meters) + pre-tax
      margin (row 45). ``measured``.
    - 2014-2016: RMI dual-fuel operating costs + EBIT (CSS) × the electricity share of the
      dual-fuel total in SMI over 2009-2013 (same CSS data, so a like-for-like split).
      ``estimated``. 2014 is cross-checked against the SMI 2014 estimate.
    - 2007-2008: SMI 2009 electricity operating cost moved with the CMA 9.11 indirect cost per
      account (nominal); margin = Supply Probe 2% of the QEP overall 3,300 kWh bill excl. VAT
      (2008 carries the 2005-07 rate). ``estimated``.
    - 2002-2006: a range. Low = DCMR 2004 'supply costs and margin' 26% of the QEP 2003 direct
      debit bill (the 26% slice is already excl. VAT; no meters); high = the 2007 value (meters
      inside). Central = low for
      2002-2004 (the DCMR years, held flat), straight line to 2007 for 2005-2006. ``estimated``.
    """
    smi, rmi, cma = read_smi(), read_rmi_dual(), read_cma_indirect()
    qep, m_probe, share = qep_elec_bill_3300(), probe_margin(), dcmr_supply_share()
    vat = 1.05
    out: dict[int, dict] = {}
    for y in range(2009, 2014):
        s = smi[y]
        out[y] = {"value": s["opex"] + s["margin"], "opex": s["opex"], "margin": s["margin"],
                  "basis": "measured", "source_id": f"{SRC['smi']}+{SRC['rpi']}",
                  "note": "SMI CSS actuals, electricity: operating costs (incl. meters) + pre-tax margin"}
    # electricity share of the dual-fuel opex+EBIT, SMI vs RMI on the same CSS years
    elec = sum(out[y]["value"] for y in range(2009, 2014))
    dual = sum(rmi[y]["opex"] + rmi[y]["ebit"] for y in range(2009, 2014))
    r = elec / dual
    for y in (2014, 2015, 2016):
        v = r * (rmi[y]["opex"] + rmi[y]["ebit"])
        out[y] = {"value": v, "basis": "estimated", "source_id": f"{SRC['rmi']}+{SRC['smi']}",
                  "note": f"RMI dual-fuel operating costs + EBIT × SMI electricity share {r:.3f} (2009-13)"}
    for y in (2007, 2008):
        opex = out[2009]["opex"] * cma[y] / cma[2009]
        margin = m_probe * qep[y]["overall"] / vat
        out[y] = {"value": opex + margin, "opex": opex, "margin": margin, "basis": "estimated",
                  "source_id": f"{SRC['smi']}+{SRC['cma']}+{SRC['probe']}+{SRC['qep221']}",
                  "note": "SMI 2009 opex moved with CMA indirect cost per account; Probe 2% margin"
                          + (" (2005-07 rate carried)" if y == 2008 else "")}
    # DCMR's 26% is a slice of the bill incl. VAT whose other slices include 'VAT, 5%', so the
    # slice itself is already excl. VAT: no further division.
    low = share * qep[2003]["dd"]
    high = out[2007]["value"]
    for y in range(2002, 2007):
        c = low if y <= 2004 else low + (high - low) * (y - 2004) / 3
        out[y] = {"value": c, "low": min(low, high), "high": max(low, high), "basis": "estimated",
                  "source_id": f"{SRC['dcmr']}+{SRC['qep221']}+{SRC['smi']}+{SRC['cma']}",
                  "note": "RANGE: low DCMR 2004 26% of 2003 DD bill (no meters), high 2007 value "
                          "(meters in); central low to 2004, straight line to 2007"}
    return out


# --------------------------------------------------------------------------- VAT


@lru_cache(maxsize=1)
def domestic_vat_rate() -> dict:
    """Reduced VAT rate on domestic fuel and power, read from HMRC VFUP1000."""
    t = unescape(re.sub(r"<[^>]+>", " ", VFUP1000.read_text()))
    t = re.sub(r"\s+", " ", t)
    quote = "The rate was reduced to the minimum of 5% with effect from 1 September 1997."
    if quote not in t:
        raise ValueError("VFUP1000: the 5% from 1 September 1997 sentence is missing")
    return {"rate": 0.05, "from": date(1997, 9, 1), "quote": quote, "source_id": SRC["vat"]}


@lru_cache(maxsize=1)
def dukes_domestic_vat() -> dict[int, dict[str, float]]:
    """DUKES 2026 Table 1.2 (value balance), Electricity column: domestic "VAT and duties" and
    domestic "Market value" (Other final users > Domestic), £m. Cross-check only."""
    wb = openpyxl.load_workbook(DUKES_12, read_only=True, data_only=True)
    out = {}
    for y in YEARS:
        rows = list(wb[str(y)].iter_rows(values_only=True))
        hdr = next(r for r in rows if r[0] == "Column1")
        j = list(hdr).index("Electricity")
        labels = [str(r[0] or "").split(" [")[0].strip() for r in rows]
        iv = labels.index("VAT and duties")
        vat = next(rows[i][j] for i in range(iv + 1, len(rows)) if labels[i] == "Domestic")
        io = labels.index("Other final users")
        mv = next(rows[i][j] for i in range(io + 1, len(rows)) if labels[i] == "Domestic")
        out[y] = {"vat": float(vat), "market": float(mv)}
    return out


# --------------------------------------------------------------------------- the block


def _line(value, basis, source_id, note="") -> dict:
    return {"value": value, "basis": basis, "source_id": source_id, "note": note}


def _unsourced(note: str) -> dict:
    return {"value": None, "basis": "UNSOURCED", "source_id": "UNSOURCED", "note": note}


@lru_cache(maxsize=1)
def block() -> dict[int, dict[str, dict]]:
    """{year: {item: {"value" (£ per UK household, nominal) | None, "basis", "source_id",
    "note"}}} for 2002–2025. Items: duos, metering, supplier, vat, total, plus duos_gbp_m."""
    from gascf.system_costs import domestic_share_cy

    dshare = domestic_share_cy()
    duos = duos_fy()
    dms = metering_dms_fy()
    vat_rate = domestic_vat_rate()["rate"]
    k = hh.read_households()
    sup_hist = supplier_history()
    out = {}
    for y in YEARS:
        n = k[y] * 1000
        row: dict[str, dict] = {}
        v, basis, src = fy_to_cy(duos, y)
        note = "FY→CY 3/12 + 9/12"
        row["duos_gbp_m"] = _line(v, basis, src, note)
        row["duos"] = _line(v * 1e6 / n, basis, f"{src}+{SRC['hh']}", note)

        if y in (2002, 2003):
            mv = 0.25 * dms[y] + 0.75 * dms[y + 1]
            row["metering"] = _line(mv * 1e6 / n, "estimated", f"{SRC['dpcr3']}+{SRC['hh']}",
                                    "DPCR3 DMS revenue (DNO metering), national")
        elif y >= 2017:
            mv, b = cap_calendar_year(y, METERING_LINES)
            row["metering"] = _line(mv, b, SRC["cap"],
                                    "cap SMNCC per typical domestic customer; legacy metering is in OC")
        elif y >= 2007:
            row["metering"] = _line(0.0, "estimated", SRC["smi"] if 2009 <= y <= 2013 else
                                    sup_hist[y]["source_id"],
                                    "inside supplier operating costs (SMI row 35 'inc. meters and "
                                    "smart meters'; CMA 9.11 para 25 treats metering as indirect)")
        else:
            row["metering"] = _unsourced("2004–2006 metering outside DNO control and before the "
                                         "CSS series (the supplier range's high end includes it)")

        if y >= 2017:
            sv, b = cap_calendar_year(y, SUPPLIER_LINES)
            row["supplier"] = _line(sv, b, SRC["cap"],
                                    "cap OC/PAAC/PAP/HAP/CO/DRC/IC + EBIT, per typical domestic customer")
        else:
            h = sup_hist[y]
            row["supplier"] = _line(h["value"], h["basis"], h["source_id"], h["note"])
            if "low" in h:
                row["supplier"]["low"], row["supplier"]["high"] = h["low"], h["high"]

        vat_base = row["duos"]["value"] * dshare[y]
        partial = []
        for item in ("metering", "supplier"):
            if row[item]["value"] is None:
                partial.append(item)
            else:
                vat_base += row[item]["value"]
        vat_basis = "modelled" if not partial else "estimated"
        row["vat"] = _line(vat_rate * vat_base, vat_basis, f"{SRC['vat']}+{SRC['dukes12']}",
                           "5% on domestic share of DUoS + supplier + metering"
                           + (f"; excludes unsourced {', '.join(partial)}" if partial else ""))

        parts = [row[i]["value"] for i in ("duos", "metering", "supplier", "vat")]
        tot = sum(p for p in parts if p is not None)
        complete = all(p is not None for p in parts)
        row["total"] = _line(tot, "modelled" if complete else "estimated",
                             "same_in_both", "complete" if complete
                             else "PARTIAL (lower bound): " + ", ".join(partial))
        out[y] = row
    return out


def both_bills() -> dict[str, dict[int, dict[str, dict]]]:
    """The same block handed to both bills (spec §8: identical by construction)."""
    b = block()
    return {"net_zero": b, "fossil": b}
