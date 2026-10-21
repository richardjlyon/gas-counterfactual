"""Running the grid (balancing, BSUoS), 2002–2025, both worlds (spec §3.1 NZ6, §3.2 GO4, §5.5,
§7.2; §15 decision 5 "costs incurred", decision 6; §15.1).

Terms: *BSUoS* = Balancing Services Use of System, the charge that recovers the system
operator's cost of balancing the grid second by second; *IBC* = incentivised balancing cost,
the part of that cost inside National Grid's incentive scheme (external costs only); *SO
internal costs* = the system operator's own running costs, recovered through BSUoS too;
*MBSS* = National Grid's Monthly Balancing Services Summary; *FY* = April–March, keyed by its
start year (2013 = 2013/14).

Net-zero Britain (NZ6), one basis every year: **costs incurred, external + SO internal**:

| FY | figure | basis | file |
|---|---|---|---|
| 2005/06 | NAO "£642 million in 2005-06" | measured | `nao_s18b/Electricity-Balancing-Services.txt` |
| 2006/07 | GB IBC outturn 495 (NG Table 1) × (1 + internal/external 2007/08) | estimated | `neso_s18b/neso_doc_46611.txt`; `ofgem_s18b/transmission_annual_report_final.txt` T22 |
| 2007/08–09/10 | "Balancing External" + "Balancing Internal" | measured | Ofgem TAR 2008-09 Table 22; TAR 2009-10 |
| 2010/11 | not found: real-terms (CPIH) interpolation 2009/10 ↔ 2011/12 | estimated | — |
| 2011/12–15/16 | MBSS March issue, §10.3 total outturn row + "Estimated Internal BSUoS (£m)" | measured | `neso_s20d/s20d-MBSS_MARCH_{2013,2014_V2,2016v1}.txt`, `neso_s18b/neso_doc_60556.txt` |
| 2016/17–22/23 | Σ half-hourly "Half-hourly Charge" | measured | `neso_s18b/bsuos_charges/2016-2023-rf.csv` |
| 2023/24–24/25 | Σ "Actual BSUoS Cost (£)" | measured | `…/2023-2024-rf.csv`, `…/2024-2025-rf.csv` |
| 2025/26 | Σ "Actual BSUoS Cost_GBP" to the last day held, scaled by 2024/25's full-year ÷ same-days ratio | estimated | `…/webprice_output_rf_2025-26_0910260747.csv` |

Why the 2016–2023 charges count as costs incurred: until the April 2023 reform the BSUoS price
for each half-hour was set after the event from that half-hour's balancing cost (internal
costs included), so the charge is the cost passed through. From April 2023 the tariff is fixed
ahead, so charges and costs part (2023/24 recovery 3,769.6 vs cost 2,872.9): the cost column is
used. Check: the 2013/14 MBSS total (869.4 + 132.6 = 1,002.0) equals NAO's "£1,002 million".

Fossil Britain (GO4): `B_energy0 × gasidx(y) + B_services0 × cpih(y)/cpih(base)` (§7.2).
gasidx runs on NBP day-ahead in every month, the series GO1 uses (s36 B4, 0030; QEP before Oct 2009
until v4-s35).
B0 = mean over CY2002–05 of the FY2001/02–05/06 baseline: NGC IBC (England & Wales) grossed up
to GB by demand and to the BSUoS basis by the 2007/08 internal ratio; FY2005/06 = NAO £642m.
The four E&W IBC years (FY2001/02–2004/05) all come from ONE document, NGET's Dec 2005 incentive
note, 'Outturn IBC' (v4-s34, decision D1; until v4-s33 FY2004/05 was NG 2010 Table 1's 289.2, a
different IBC definition).
Energy share = (Constraints + Energy Imbalance) ÷ total in the NESO workbook's first year
(FY2018/19), range 30–70% (decision 5).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
from datetime import date
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from gascf.pathutil import rel_to_root

import openpyxl

from gascf import deflator_cpih as dfl
from gascf import prices
from gascf.grid import fy_to_cy

RAW = Path(__file__).parents[2] / "data/raw"
NAO = RAW / "nao_s18b/Electricity-Balancing-Services.txt"
NG_SO_2010 = RAW / "neso_s18b/neso_doc_46611.txt"
OFGEM_SO_2003 = RAW / "ofgem_s18b/2545_16so_incentives.txt"
NGET_PERF_2005 = RAW / "ofgem_s18b/12409-ngetincentive-_0.txt"
TAR_0809 = RAW / "ofgem_s18b/transmission_annual_report_final.txt"
TAR_0910 = RAW / "ofgem_s18b/treport_0.txt"
MBSS = {  # report → (file, FY the year-to-date block belongs to)
    2013: (RAW / "neso_s20d/s20d-MBSS_MARCH_2013.txt", 2012),
    2014: (RAW / "neso_s20d/s20d-MBSS_MARCH_2014_V2.txt", 2013),
    2015: (RAW / "neso_s18b/neso_doc_60556.txt", 2014),
    2016: (RAW / "neso_s20d/s20d-MBSS_MARCH_2016v1.txt", 2015),
}
BSUOS = RAW / "neso_s18b/bsuos_charges"
WORKBOOK = RAW / "neso/NESO_2025_Annual_Balancing_Costs_Data_Workbook.xlsx"
DEMAND = {y: RAW / f"neso/s18c-demanddata_{y}.csv" for y in range(2002, 2006)}
TABLE22_REF = Path(__file__).parents[2] / "reference/balancing_tar_2008_09_table22.json"   # ticket 48
GB_OVER_EW_YEARS = (2002, 2003, 2004, 2005)

YEARS = range(2002, 2026)
BASE_WINDOW = range(2002, 2006)

SRC_B0 = "s20d-balancing-baseline-ibc-grossed-up-gb"
SRC_NAO = "nao-2014-electricity-balancing-services-para2.2"
SRC_IBC_2005 = "nget-2005-so-incentive-performance-outturn-ibc"


def _flat(p: Path) -> str:
    return re.sub(r"\s+", " ", p.read_text(errors="replace"))


def _f(s: str) -> float:
    return float(s.replace(",", "").replace("£", ""))


def _row(v, basis, src):
    return {"gbp_m": v, "basis": basis, "source_id": src}


# ------------------------------------------------------------------ readers

def nao_totals() -> dict[int, float]:
    m = re.search(r"from £(\d+) million in 2005-06 to £([\d,]+) million in 2013-14", _flat(NAO))
    if not m:
        raise ValueError("NAO para 2.2 sentence moved")
    return {2005: _f(m.group(1)), 2013: _f(m.group(2))}


@lru_cache(maxsize=None)
def ng_table1() -> dict[int, dict]:
    """NG Nov 2010 Table 1 'Summary of historic BSIS parameters': {FY: {target, actual}}."""
    t = _flat(NG_SO_2010)
    out = {}
    for m in re.finditer(r"(20\d\d)/\d\d (\d+) \d+ \d+ [\d.]+ -?[\d.]+ ([\d.]+) -?[\d.]+ -?[\d.]+", t):
        out.setdefault(int(m.group(1)), {"target": float(m.group(2)), "actual": float(m.group(3))})
    m = re.search(r"2006/07 n/a n/a n/a n/a n/a (\d+) n/a", t)
    if not m or 2004 not in out:
        raise ValueError("doc 46611 Table 1 moved")
    out[2006] = {"target": None, "actual": float(m.group(1))}
    return out


@lru_cache(maxsize=None)
def ofgem_ibc_ew() -> dict[int, dict]:
    """NGC IBC outturn, England & Wales, FY2001/02-2004/05, £m money of the day, ALL FOUR YEARS from
    ONE document: NGET, *System Operator Incentive Performance* (Dec 2005, Ofgem library
    12409-ngetincentive-_0.pdf), table 'Historical performance', row 'Outturn IBC':
    365.6, 379.0, 351.5, 384.1 (Richard, 14 Oct 2026, decision D1).

    Why one document: until v4-s33 FY2004/05 came from National Grid's Nov 2010 *SO Incentives
    Review* Table 1 (289.2), whose IBC definition differs (its 2001/02-03/04 actuals are 263.0, 285.6,
    280.8, £71-100m below the 2005 note's, against different targets). Mixing the two inside the
    2002-05 average was a definitional splice (method fact-check 14 Oct 2026, W1). NG 2010 Table 1
    stays in use where it is the only source (`ng_table1`: GB IBC 2006/07 for NZ6), never in B0.
    The 2005 note's own identity is checked: target - outturn = its printed 'cost difference' row
    (2002/03-2004/05) and Ofgem 2003's 'approximately £366 million' agrees with 365.6 for 2001/02."""
    a = _flat(NGET_PERF_2005)
    out_row = re.search(r"Outturn IBC ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)", a)
    tgt_row = re.search(r"Target IBC [\d.]+ to [\d.]+ ([\d.]+) ([\d.]+) ([\d.]+)", a)
    diff_row = re.search(r"Cost difference ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)", a)
    if not (out_row and tgt_row and diff_row):
        raise ValueError("NGET Dec 2005 note: 'Historical performance' table moved")
    outturn = [float(x) for x in out_row.groups()]
    target = [float(x) for x in tgt_row.groups()]
    diff = [float(x) for x in diff_row.groups()]
    for t, o, d in zip(target, outturn[1:], diff[1:]):
        if abs((t - o) - d) > 0.05:
            raise ValueError("NGET Dec 2005 note: target - outturn != cost difference")
    m = re.search(r"IBC totalled approximately £(\d+) million", _flat(OFGEM_SO_2003))
    if not m or abs(float(m.group(1)) - outturn[0]) > 0.5:
        raise ValueError("Ofgem 2003 'approximately £366 million' does not agree with the 2005 note")
    return {fy: _row(v, "measured", SRC_IBC_2005) for fy, v in zip((2001, 2002, 2003, 2004), outturn)}


def tar_balancing() -> dict[int, dict]:
    """Ofgem TAR: {FY: {external, internal}} 2007/08–2009/10, £m nominal."""
    a, b = _flat(TAR_0809), _flat(TAR_0910)
    e1 = re.search(r"Balancing External ([\d.]+) ([\d.]+)", a)
    i1 = re.search(r"Balancing Internal ([\d.]+) ([\d.]+)", a)
    e2 = re.search(r"Balancing External ([\d.]+) ([\d.]+)", b)
    i2 = re.search(r"Balancing Internal ([\d.]+) ([\d.]+)", b)
    if not all((e1, i1, e2, i2)) or e2.group(2) != "907.7":
        raise ValueError("TAR balancing rows moved")
    return {2007: {"external": float(e1.group(1)), "internal": float(i1.group(1))},
            2008: {"external": float(e1.group(2)), "internal": float(i1.group(2))},
            2009: {"external": float(e2.group(1)), "internal": float(i2.group(1))}}


def internal_ratio() -> float:
    """Earliest measured SO internal ÷ external, FY2007/08 (spec §7.2)."""
    t = tar_balancing()[2007]
    return t["internal"] / t["external"]


_T22_EXTERNAL = "tar_2008_09_t22_balancing_external_2007_08"
_T22_INTERNAL = "tar_2008_09_t22_balancing_internal_2007_08"
_T22_REQUIRED = ("value", "units", "period", "document", "file", "sha256", "page", "table", "quote")


@lru_cache(maxsize=None)
def table22_rows(path: Path = None) -> dict:
    """Ticket 48: the two Ofgem TAR 2008-09 Table 22 balancing rows (external, internal, FY2007/08), each with
    its document, registered file and sha256, page, table and verbatim quote, from the engine reference file.
    Raises if a row is missing any required field. Not figures keys and not sourced keys: reference rows that let
    the fact-checker trace the BSUoS-basis gross-up factor to the stored PDF."""
    rows = json.loads((path or TABLE22_REF).read_text())["rows"]
    for rid in (_T22_EXTERNAL, _T22_INTERNAL):
        if rid not in rows:
            raise ValueError(f"table22 reference: missing row {rid}")
    for rid, r in rows.items():
        for fld in _T22_REQUIRED:
            if fld not in r:
                raise ValueError(f"table22 row {rid}: missing field {fld!r}")
    return rows


def bsuos_basis_grossup(path: Path = None) -> dict:
    """Ticket 48: the BSUoS-basis gross-up factor 1 + internal / external (FY2007/08) from the two Table 22
    reference rows, with its inputs (the two row ids, internal then external). Computed value, unrounded."""
    rows = table22_rows(path)
    internal = rows[_T22_INTERNAL]["value"]
    external = rows[_T22_EXTERNAL]["value"]
    return {"value": 1 + internal / external, "inputs": [_T22_INTERNAL, _T22_EXTERNAL]}


def bsuos_basis_grossup_factor(path: Path = None) -> float:
    """The BSUoS-basis gross-up factor (ticket 48). Equals 1 + internal_ratio() (the GO4 and NZ6 route, unchanged)."""
    return bsuos_basis_grossup(path)["value"]


def _nums27(text: str, label: str) -> list[list[float]]:
    pat = re.escape(label) + r"((?: -?\d+(?:\.\d+)?){27})"
    return [[float(x) for x in m.group(1).split()] for m in re.finditer(pat, text)]


@lru_cache(maxsize=None)
def mbss_totals() -> dict[int, dict]:
    """{FY: {external, internal}} from the MBSS March issues, 12-month outturn blocks only."""
    out = {}
    for rep, (path, fy) in MBSS.items():
        t = _flat(path)
        ytd = re.search(r"TOTAL(?: \(excl TLIC\))? £([\d,.]+)", t)
        label = {2013: "TOTAL (excl TLIC)", 2016: "TOTAL (inc SBR Tests)"}.get(rep, "TOTAL")
        rows = _nums27(t, label)
        intl = _nums27(t, "Estimated Internal BSUoS (£m)")
        if not (ytd and rows and intl):
            raise ValueError(f"MBSS March {rep}: anchors moved")
        r, i = rows[0], intl[0]
        if abs(sum(r[:12]) - r[12]) > 0.6 or abs(sum(r[13:25]) - r[25]) > 0.6:
            raise ValueError(f"MBSS March {rep}: monthly rows do not sum")
        k = 12 if abs(r[12] - _f(ytd.group(1))) < 0.05 else 25
        if abs(r[k] - _f(ytd.group(1))) >= 0.05:
            raise ValueError(f"MBSS March {rep}: no block equals the YTD total")
        out[fy] = {"external": r[k], "internal": i[k], "source_id": f"ng-mbss-march-{rep}-s10.3"}
        if rep == 2013 and k == 25 and "Apr-11" in t:      # the earlier block is 2011/12 outturn
            out[2011] = {"external": r[12], "internal": i[12], "source_id": "ng-mbss-march-2013-s10.3"}
    return out


def _day(s: str) -> date:
    """'2016-04-01', ' 2022-10-1', '2023-04-01T00:00:00' → date."""
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if not m:
        raise ValueError(f"bad settlement day {s!r}")
    return date(*map(int, m.groups()))


def _fy_of(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


@lru_cache(maxsize=None)
def bsuos_csv_fy() -> dict[int, dict]:
    """Σ by FY: 'Half-hourly Charge' (2016–2023 file) and 'Actual BSUoS Cost' / 'Total Recovery'
    (2023-24, 2024-25 files), £m. Also day counts, to prove whole years."""
    sums: dict[int, dict] = {}

    def add(fy, key, v, d):
        s = sums.setdefault(fy, {"days": set()})
        s[key] = s.get(key, 0.0) + v
        s["days"].add(d)

    with (BSUOS / "2016-2023-rf.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = _day(r["Settlement Day"])
            add(_fy_of(d), "charge", float(r["Half-hourly Charge"]) / 1e6, d)
    for fn in ("2023-2024-rf.csv", "2024-2025-rf.csv"):
        with (BSUOS / fn).open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                d = _day(r["Settlement Day"])
                add(_fy_of(d), "cost", float(r["Actual BSUoS Cost (£)"]) / 1e6, d)
                add(_fy_of(d), "recovery", float(r["BSUoS Total Recovery ()"]) / 1e6, d)
    return {fy: {k: v for k, v in s.items() if k != "days"} | {"n_days": len(s["days"])}
            for fy, s in sums.items()}


DAILY_CY_YEARS = range(2017, 2025)   # 0088: NZ6 summed from the daily files by calendar year


@lru_cache(maxsize=None)
def bsuos_daily() -> dict[date, float]:
    """{settlement day: £m} gross BSUoS, the same field the Subsidy Clock sums (`bsuos.raw_annual`):
    'Half-hourly Charge' to 31 March 2023 (2016-2023 file), 'Actual BSUoS Cost (£)' from 1 April
    2023 (2023-24, 2024-25 files). FY2016/17-2024/25."""
    out: dict[date, float] = {}
    with (BSUOS / "2016-2023-rf.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = _day(r["Settlement Day"])
            out[d] = out.get(d, 0.0) + float(r["Half-hourly Charge"]) / 1e6
    for fn in ("2023-2024-rf.csv", "2024-2025-rf.csv"):
        with (BSUOS / fn).open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                d = _day(r["Settlement Day"])
                out[d] = out.get(d, 0.0) + float(r["Actual BSUoS Cost (£)"]) / 1e6
    return out


def fy2025_estimate() -> dict:
    """FY2025/26 cost to the last day held, scaled by 2024/25 full-year ÷ the same days of 2024/25."""
    part, last = 0.0, None
    with next(BSUOS.glob("webprice_output_rf_2025-26_*.csv")).open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            dd, mm, yy = r["Settlement Date"].split("-")
            d = date(int(yy), int(mm), int(dd))
            part += float(r["Actual BSUoS Cost_GBP"]) / 1e6
            last = max(last or d, d)
    same = 0.0
    with (BSUOS / "2024-2025-rf.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d = _day(r["Settlement Day"])
            if d <= date(2024, last.month, last.day):
                same += float(r["Actual BSUoS Cost (£)"]) / 1e6
    full = bsuos_csv_fy()[2024]["cost"]
    return {"gbp_m": part * full / same, "held_gbp_m": part, "last_day": last}


@lru_cache(maxsize=None)
def bsuos_fy() -> dict[int, dict]:
    """NZ6 by FY, £m nominal, costs incurred (external + internal), FY2005/06–2025/26."""
    out: dict[int, dict] = {}
    nao = nao_totals()
    out[2005] = _row(nao[2005], "measured", SRC_NAO)
    # FY2006/07 and FY2010/11 are estimated: listed in the fallback register as
    # 'bsuos-fy2006-ibc-grossup' and 'bsuos-fy2010-cpih-interpolation' (bills.record_netzero_fallbacks).
    out[2006] = _row(ng_table1()[2006]["actual"] * (1 + internal_ratio()), "estimated",
                     "ng-2010-table1-ibc-x-ofgem-tar-2008-09-t22-internal-ratio")
    for fy, v in tar_balancing().items():
        out[fy] = _row(v["external"] + v["internal"], "measured", "ofgem-tar-2008-09-t22|ofgem-tar-2009-10")
    for fy, v in mbss_totals().items():
        out[fy] = _row(v["external"] + v["internal"], "measured", v["source_id"])
    c = dfl.cpih()
    r09 = out[2009]["gbp_m"] / c[2009]
    r11 = out[2011]["gbp_m"] / c[2011]
    out[2010] = _row((r09 + r11) / 2 * c[2010], "estimated", "s20d-cpih-interpolation-2009-10-2011-12")
    b = bsuos_csv_fy()
    for fy in range(2016, 2023):
        out[fy] = _row(b[fy]["charge"], "measured", "neso-bsuos-2016-2023-rf-half-hourly-charge")
    for fy in (2023, 2024):
        out[fy] = _row(b[fy]["cost"], "measured", f"neso-bsuos-{fy}-{fy + 1}-rf-actual-cost")
    out[2025] = _row(fy2025_estimate()["gbp_m"], "estimated", "neso-bsuos-2025-26-rf-partial-scaled")
    return dict(sorted(out.items()))


_RANK = {"measured": 0, "modelled": 1, "estimated": 2}

CMP308_PDF = RAW / "neso/CMP308_Second_Workgroup_Consultation_2021-04-01.pdf"
SRC_CMP308 = "neso-cmp308-second-workgroup-consultation-2021-04"
BSUOS_GEN_OPTIONS = ("removed", "included")   # 'removed' = central (s27b); 'included' = pre-s27 behaviour
# Anchor points of the generators' BSUoS share (FY start year → share), read from CMP308 below.
# Before CMP202 (implemented 1 April 2013) BSUoS was split 50:50; "in 2017 … 49:51"; "expected
# to be 47:53 by 2020"; from 1 April 2023 (CMP308) generators pay none.
_CMP308_ANCHORS = (("split 50:50", 2012, 0.50), ("49:51", 2017, 0.49), ("47:53", 2020, 0.47))


@lru_cache(maxsize=None)
def bsuos_gen_share_fy() -> dict[int, dict]:
    """{FY: {share, basis, source_id}} the generators' share of BSUoS (spec §15.5 item 3, s27b).

    Read from the CMP308 second workgroup consultation (NESO, 1 April 2021, stored): "CMP201
    modelling (for status quo) assumed BSUoS was split 50:50 between demand and generation. As a
    result of CMP202 the G:D split for BSUoS charging in 2017 was around 49:51 and is expected to
    be 47:53 by 2020." CMP202 took effect 1 April 2013. Shares: FY2001/02–2012/13 50% (measured
    rule); FY2013/14–2016/17 straight line 50%→49% (estimated); 2017/18 49%; 2018/19–2019/20
    straight line to 47% (estimated); 2020/21–2022/23 47% (estimated: "expected"); from FY2023/24
    0 (CMP308: BSUoS on final demand only)."""
    import pymupdf
    t = re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(CMP308_PDF)))
    for phrase in ("assumed BSUoS was split 50:50 between demand and generation",
                   "G:D split for BSUoS charging in 2017 was around 49:51 and is expected to be 47:53 by 2020",
                   "implemented into the CUSC charging arrangements on 1 April 2013"):
        if phrase not in t:
            raise ValueError(f"CMP308 consultation: {phrase!r} moved")
    out = {}
    pts = [(fy, s) for _, fy, s in _CMP308_ANCHORS]
    for fy in range(2001, 2027):
        if fy >= 2023:
            share, basis = 0.0, "measured"
        elif fy <= pts[0][0]:
            share, basis = pts[0][1], "measured"
        elif fy >= pts[-1][0]:
            share, basis = pts[-1][1], "estimated"
        else:
            (a, sa), (b, sb) = next(((p, q) for p, q in zip(pts, pts[1:]) if p[0] <= fy <= q[0]))
            share = sa + (sb - sa) * (fy - a) / (b - a)
            basis = "measured" if fy == 2017 else "estimated"
        out[fy] = {"share": share, "basis": basis, "source_id": SRC_CMP308}
    return out


def bsuos_gen_share_cy(years=YEARS) -> dict[int, float]:
    return fy_to_cy({k: v["share"] for k, v in bsuos_gen_share_fy().items()}, years)


def nz6(years=YEARS, gen_share: str = "removed") -> dict[int, dict]:
    """NZ6 by calendar year (§2 weighting), £m nominal. CY2002–05: the §7.2 baseline (modelled).

    gen_share: 'removed' (central, s27b): each FY less the generators' BSUoS share
    (`bsuos_gen_share_fy`; zero from FY2023/24); 'included': the whole BSUoS (pre-s27 line)."""
    if gen_share not in BSUOS_GEN_OPTIONS:
        raise ValueError(gen_share)
    gs = bsuos_gen_share_fy()
    keep = (lambda k: 1 - gs[k]["share"]) if gen_share == "removed" else (lambda k: 1.0)
    fy = bsuos_fy()
    cy = fy_to_cy({k: v["gbp_m"] * keep(k) for k, v in fy.items()}, [y for y in years if y >= 2006])
    out = {}
    for y in years:
        if y >= 2006:
            a, b = fy[y - 1], fy[y]
            src = f"{a['source_id']}|{b['source_id']}" + (f"|{SRC_CMP308}" if gen_share == "removed" else "")
            out[y] = {"gbp_m": cy[y], "basis": max(a["basis"], b["basis"], key=_RANK.get),
                      "source_id": src, "geo": "GB"}
    daily = bsuos_daily()
    for y in DAILY_CY_YEARS:
        if y in out:
            out[y]["gbp_m"] = sum(v * keep(_fy_of(d)) for d, v in daily.items() if d.year == y)
    base = fy_to_cy({k: v["gbp_m"] * keep(k) for k, v in baseline_fy().items()}, BASE_WINDOW)
    for y in BASE_WINDOW:
        out[y] = {"gbp_m": base[y], "basis": "modelled", "source_id": SRC_B0, "geo": "GB"}
    if gen_share == "removed":
        g = bsuos_gen_share_cy(years)
        for y in out:
            out[y]["gen_share"] = g[y]
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ §7.2 baseline

@lru_cache(maxsize=None)
def gb_over_ew_by_year() -> dict:
    """GB ÷ England & Wales demand, each calendar year 2002-05, Σ ND ÷ Σ ENGLAND_WALES_DEMAND from the NESO
    Historic Demand Data CSVs. Raises if any year is missing (ticket 48)."""
    out = {}
    for y in GB_OVER_EW_YEARS:
        if y not in DEMAND:
            raise ValueError(f"NESO demand data missing for {y}")
        nd = ew = 0.0
        with DEMAND[y].open() as f:
            for r in csv.DictReader(f):
                nd += float(r["ND"])
                ew += float(r["ENGLAND_WALES_DEMAND"])
        out[y] = nd / ew
    return out


def gb_over_ew() -> float:
    """GB ÷ England & Wales demand, CY2002-05 mean of the yearly ND ÷ ENGLAND_WALES_DEMAND ratios."""
    return statistics.mean(gb_over_ew_by_year().values())


def gb_over_ew_inputs() -> list:
    """The four registered NESO demand CSVs (2002-05) and their sha256, for the run-file block (ticket 48)."""
    return [{"path": rel_to_root(DEMAND[y]), "sha256": hashlib.sha256(DEMAND[y].read_bytes()).hexdigest()}
            for y in GB_OVER_EW_YEARS]


def baseline_fy(option: str = "ibc") -> dict[int, dict]:
    """FY2001/02–2005/06 balancing baseline, £m nominal, BSUoS basis, GB.
    option 'ibc' (central): E&W IBC × GB/E&W × (1 + internal ratio); FY2005/06 = NAO 642.
    option 'nao_2005' (decision 6 alternative): NAO 2005/06 £642m for every year, CPIH-deflated."""
    nao = nao_totals()[2005]
    if option == "nao_2005":
        c = dfl.cpih()
        c05 = 0.75 * c[2005] + 0.25 * c[2006]
        return {fy: _row(nao * (0.75 * c[fy] + 0.25 * c[fy + 1]) / c05, "modelled", SRC_NAO)
                for fy in range(2001, 2006)}
    k = gb_over_ew() * (1 + internal_ratio())
    out = {fy: _row(v["gbp_m"] * k, "modelled", f"{SRC_B0}|{v['source_id']}")
           for fy, v in ofgem_ibc_ew().items()}
    out[2005] = _row(nao, "measured", SRC_NAO)
    return out


@lru_cache(maxsize=None)
def energy_share_2018() -> float:
    """(Constraints + Energy Imbalance) ÷ total, NESO workbook 'Total outturn', FY2018/19."""
    ws = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)["Total outturn"]
    rows = list(ws.iter_rows(values_only=True))
    h = next(r for r in rows if r and r[0] == "FY")
    r = next(r for r in rows if r and r[0] == "2018/19")
    d = dict(zip(h, r))
    cats = [c for c in h[1:] if c and c.endswith("(£)")]
    if not {"Constraints (£)", "Energy Imbalance (£)"} <= set(cats):
        raise ValueError("workbook headers moved")
    return (d["Constraints (£)"] + d["Energy Imbalance (£)"]) / sum(d[c] for c in cats)


def workbook_external_fy() -> dict[int, float]:
    """Workbook 'Total outturn' category sum by FY, £m (external costs only): cross-check."""
    ws = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)["Total outturn"]
    rows = list(ws.iter_rows(values_only=True))
    h = next(r for r in rows if r and r[0] == "FY")
    cats = [i for i, c in enumerate(h) if c and str(c).endswith("(£)")]
    return {int(r[0][:4]): sum(r[i] for i in cats) / 1e6
            for r in rows if r and isinstance(r[0], str) and re.fullmatch(r"20\d\d/\d\d", r[0])}


def gas_monthly() -> dict[tuple[int, int], float]:
    """GO4's gas price (§4.4), £/MWh, by month: NBP day-ahead in every month, the series GO1 uses
    (`prices.nbp_gbp_mwh`: Ofgem WEM 2015 Fig 5 before Oct 2009, Ofgem WMI after). s36 B4 (0030):
    until v4-s35 the months before Oct 2009 used DESNZ QEP 3.2.1 (major power producers' gas)."""
    n = prices.nbp_gbp_mwh()
    out = {}
    for y in range(2002, 2026):
        for m in range(1, 13):
            if (y, m) not in n:
                raise ValueError(f"gas price missing {y}-{m:02d}")
            out[(y, m)] = n[(y, m)][0]
    return out


def gas_annual() -> dict[int, float]:
    """GO4's gas price, £/MWh, calendar-year mean of `gas_monthly`."""
    g = gas_monthly()
    return {y: statistics.mean(g[(y, m)] for m in range(1, 13)) for y in range(2002, 2026)}


def go4(base_year: int, share: float | None = None, option: str = "ibc", years=YEARS,
        gen_share: str = "removed", gas_uplift: Mapping[int, float] | None = None) -> dict[int, dict]:
    """GO4 = (B_energy0 × gas(y)/gas(2002–05) + B_services0 × cpih(y)/cpih(base)) × (1 − g(y)),
    £m nominal. B_energy0 = s × B0_nom / (1 + internal ratio): the energy share s is a share of
    EXTERNAL balancing cost (`energy_share_2018`, NESO workbook categories), and B0 is on the
    BSUoS basis, grossed up by SO internal costs (`baseline_fy`), so the share is applied to the
    external part only (v4-s35, T6b; until v4-s34 s was applied to the whole of B0, which carried
    the SO's own staff and IT costs by the gas price). B_energy0 uses the nominal CY2002–05 mean
    (the gas index carries it, including inflation); B_services0 = B0 − B_energy0, the same mean
    restated to `base_year` money with CPIH (internal costs included). g(y) is the
    generators' BSUoS share in year y (`bsuos_gen_share_cy`) when gen_share='removed' (central,
    s27b, symmetric with NZ6); 'included' = pre-s27 line."""
    if gen_share not in BSUOS_GEN_OPTIONS:
        raise ValueError(gen_share)
    s = energy_share_2018() if share is None else share
    s_b0 = s / (1 + internal_ratio())          # share of B0 (BSUoS basis) carried by gas
    cy = fy_to_cy({k: v["gbp_m"] for k, v in baseline_fy(option).items()}, BASE_WINDOW)
    c = dfl.cpih()
    b_nom = statistics.mean(cy[y] for y in BASE_WINDOW)
    b_real = statistics.mean(cy[y] * c[base_year] / c[y] for y in BASE_WINDOW)
    gas = gas_annual()
    g0 = statistics.mean(gas[y] for y in BASE_WINDOW)
    gs = bsuos_gen_share_cy(years) if gen_share == "removed" else {y: 0.0 for y in years}
    u = {y: 0.0 for y in years} if gas_uplift is None else dict(gas_uplift)
    for y in years:
        if y not in u or not math.isfinite(u[y]) or u[y] < 0:
            raise ValueError(f"gas_uplift for {y}: {u.get(y)!r} (needs a finite fraction >= 0 every year)")
    out = {}
    for y in years:
        k = 1 - gs[y]
        e_actual = s_b0 * b_nom * gas[y] / g0 * k
        e = e_actual * (1 + u[y])
        sv = (1 - s_b0) * b_real * c[y] / c[base_year] * k
        out[y] = {"gbp_m": e + sv, "energy_gbp_m": e, "services_gbp_m": sv, "energy_share": s,
                  "energy_gbp_m_actual_gas": e_actual, "gas_uplift_frac": u[y],
                  "gas_feedback_gbp_m": e - e_actual,
                  "energy_share_of_b0": s_b0,
                  "gen_share": gs[y], "basis": "modelled",
                  "source_id": f"{SRC_B0}|neso-2025-abc-workbook-total-outturn"
                  + (f"|{SRC_CMP308}" if gen_share == "removed" else "")
                  + ("|neuhoff-2022-eprg2212-gas-price-limits" if any(v > 0 for v in u.values()) else ""),
                  "geo": "GB"}
    return out
