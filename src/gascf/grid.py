"""High-voltage grid: GB transmission revenue (TNUoS), 2002–2025, both worlds (spec §3.1 NZ7,
§3.2 GO5, §5.5, §7.1, §7.3; §15.1).

Terms: *TNUoS* = Transmission Network Use of System charges, the charges that recover the
transmission owners' allowed revenue; *TO* = transmission owner (NGET in England & Wales,
SP Transmission and SHE Transmission in Scotland, plus offshore OFTOs); *allowed revenue* =
what Ofgem lets a TO collect in a year; *NLR* = non-load-related capex, mostly asset
replacement; *FY* = financial year April–March, keyed here by its start year (2002 = 2002/03).

Net-zero Britain (NZ7): the GB TNUoS total each FY, from the regulator / system-operator
document for that year, read from the stored text (never typed in):

| FY | figure | file |
|---|---|---|
| 2005/06 | NGC TO + SPT + SHETL allowed revenue, the §7.1 pieces (modelled) | as `baseline_pieces` |
| 2006/07 | TPCR4 FP Table 2.1 "2006/07 Revenues" NGET 1005 + SPTL 160 + SHETL 51, 2004/05 prices, RPI to nominal (modelled) | `ofgem_s18b/16342-…tpcr-final-proposals….txt` |
| 2007/08–09/10 | NGET "Total Actual Revenue" (Ofgem: "Figures include income collected on behalf of the Scottish TOs", so SPTL/SHETL are not added again) | `ofgem_s18b/transmission_annual_report_final.txt` Table 1; `treport_0.txt` Table 1 |
| 2010/11–12/13 | "Total TNUoS revenue" | `neso_s18b/neso_doc_50676.txt` |
| 2013/14 | "TNUoS Charges" | `neso_s18b/neso_doc_50671.txt` |
| 2014/15–16/17 | "Total to Collect from TNUoS" | `neso_s18b/neso_doc_50181.txt`, `50211.txt` |
| 2017/18, 2019/20 | "Total to Collect from TNUoS" (Jan Final column) | `neso_s20d/s20d-neso_doc_{50276,137351}_…_extract.md` |
| 2018/19 | "total TO revenue to be recovered will be £2,670m" | `neso_s20d/s20d-neso_doc_114041_…_extract.md` |
| 2020/21 | "Total to Collect from TNUoS" Final | `neso_s18b/neso_doc_163311.txt` |
| 2021/22 | "Total revenue to be collected is £3,318m" | `neso_s18b/neso_doc_186176.txt` |
| 2022/23–23/24 | Tables T15/T16 "Total to Collect from TNUoS", January Final | `neso/tnuos/Final_TNUoS_Tariffs_*_Tables.xlsx` |
| 2024/25–26/27 | Table 16/17 "Total to Collect from TNUoS", January Final | `neso_s20d/s20d-Final_TNUoS_Tariffs_*_Report.txt` |

From 2010/11 the figures are ex-ante revenue to collect (the tariff-setting total); they
include OFTO revenue, so OFTO is never added again (review A11). Converted to calendar years
by the §2 time weighting.

Fossil Britain (GO5): `G0 × cpih(y)/cpih(base) + R(y)`. G0 is the CY2002–05 mean (CPIH,
headline-year money) of the three TOs' allowed revenues (§7.1, decision 6(a)), restated from
their RPI price bases to nominal with RPI first (the index the controls used). R(y) is the
renewal allowance range (§7.3).
"""
from __future__ import annotations

import re
import statistics
from functools import lru_cache
from pathlib import Path

import openpyxl

from gascf import deflator_cpih as dfl

RAW = Path(__file__).parents[2] / "data/raw"
NGC_2000 = RAW / "ofgem_s18b/transmission-price-control-review-of-ngc-from-2001---transmission-owner-final-proposals-2709_0.txt"
BETTA_2004 = RAW / "ofgem_s18b/7851-18204.txt"          # draft (Jul 2004): FY2000/01-04/05 existing controls
# v4-s35 (T12): the FY2005/06 Scottish roll-forward allowances come from the FINAL proposals, Ofgem,
# *Transmission price controls and BETTA: Final proposals*, Dec 2004 (279/04), Table 2.3 "Final
# proposals - Total allowed revenues", £m 2002/3 prices: SPT 127.5, SHETL 52.56 (2005/6), "Includes
# fixed allowances for pass-through items". Until v4-s34 the draft's 114.5 / 47.3 were used.
# https://www.ofgem.gov.uk/sites/default/files/docs/2004/12/9122-27904_0.pdf
# 0094: the Scottish 2005/06 allowance is taken from 279/04 Appendices 5 and 6; the £2.8m Appendix 8
# interconnector allowance is left out (kept at £55.9m, no engine change).
BETTA_FINAL_2004 = RAW / "ofgem_s35/s35-9122-27904_BETTA_final_proposals_Dec2004.txt"
# v4-s35 (T3, T8): RIIO-ET2 Price Control Financial Handbook (part of transmission licence Special
# Condition 8.1), version published 31 May 2024. https://www.ofgem.gov.uk/sites/default/files/
# 2024-07/ET2_PCFH_C06_published_31%20May_2024.pdf
PCFH_ET2 = RAW / "ofgem_s35/s35-ET2_PCFH_C06_published_31May2024.txt"
TPCR4 = RAW / "ofgem_s18b/16342-20061201_tpcr-final-proposals_in_v71-6-final_0.txt"
TAR_0809 = RAW / "ofgem_s18b/transmission_annual_report_final.txt"
TAR_0910 = RAW / "ofgem_s18b/treport_0.txt"
NESO18 = RAW / "neso_s18b"
NESO20 = RAW / "neso_s20d"
TNUOS_XLSX = RAW / "neso/tnuos"
RIIO_T1_NGET = RAW / "ofgem_s20d/s20d-RIIO-T1_FP_overview_NGET_NGG_Dec2012.txt"
RIIO_T1_SCOT = RAW / "ofgem_s20d/s20d-RIIO-T1_FP_SPT_SHETL_support_Apr2012.txt"
RIIO2 = {k: RAW / f"ofgem_s20d/s20d-RIIO-2_FD_{k}_annex_revised.txt" for k in ("NGET", "SHET", "SPT")}

YEARS = range(2002, 2026)
BASE_WINDOW = range(2002, 2006)        # CY2002–2005, spec §7
ANNUITY_YEARS = 45                      # spec §7.3: RAV depreciation life (straight line)

SRC_G0 = "s20d-grid-baseline-assembled-ngc-a6.2-spt-shetl-t1-t2"
SRC_R = "s20d-renewal-allowance-tpcr4-riio-t1-riio2-nlr"


def _txt(p: Path) -> str:
    return p.read_text(errors="replace")


def _flat(p: Path) -> str:
    return re.sub(r"\s+", " ", _txt(p))


def _nums(s: str) -> list[float]:
    return [float(x.replace(",", "").strip("()")) * (-1 if x.startswith("(") else 1)
            for x in re.findall(r"\(?\d[\d,]*(?:\.\d+)?\)?", s)]


def _after(text: str, label: str, n: int, start: int = 0) -> list[float]:
    """The first n numbers after `label` (fails loudly if the label has moved)."""
    if start < 0:
        raise ValueError(f"table anchor for {label!r} not found")
    i = text.find(label, start)
    if i < 0:
        raise ValueError(f"anchor {label!r} not found")
    vals = _nums(text[i + len(label): i + len(label) + 400])
    if len(vals) < n:
        raise ValueError(f"anchor {label!r}: only {len(vals)} numbers")
    return vals[:n]


# ------------------------------------------------------------------ money helpers

def rpi_fy(fy: int) -> float:
    """RPI for financial year fy/fy+1, time-weighted from calendar-year averages (9 + 3 months)."""
    r = dfl.rpi()
    return 0.75 * r[fy] + 0.25 * r.get(fy + 1, r[fy])   # FY2025/26: no CY2026 average yet


def rpi_restate(value: float, price_base_fy: int, fy: int) -> float:
    """A figure in FY `price_base_fy` RPI prices, restated to FY `fy` money (nominal)."""
    return value * rpi_fy(fy) / rpi_fy(price_base_fy)


def fy_to_cy(fy: dict[int, float], years=YEARS) -> dict[int, float]:
    """Spec §2: CY(y) = 0.25 × FY(y−1/y) + 0.75 × FY(y/y+1). Raises if a needed FY is missing."""
    out = {}
    for y in years:
        if y - 1 not in fy or y not in fy:
            raise ValueError(f"FY missing for CY{y}")
        out[y] = 0.25 * fy[y - 1] + 0.75 * fy[y]
    return out


# ------------------------------------------------------------------ §7.1 the 2002–05 pieces

@lru_cache(maxsize=None)
def baseline_pieces() -> dict[str, dict]:
    """The three TOs' allowed revenues FY2001/02–2005/06 as printed, with their price bases.
    SPT/SHETL FY2000/01–04/05 = the existing controls (draft Tables 1-2, the same in the final);
    FY2005/06 and 06/07 = the final proposals' Table 2.3 (v4-s35, T12)."""
    t = _flat(NGC_2000)
    i = t.find("Table A6.2: NGC’s price controlled revenues excluding all SO costs")
    ngc = _after(t, "Price control revenues", 6, i)          # 01/02 … 05/06, Total
    if abs(ngc[5] - sum(ngc[:5])) > 2 or "1999/000 prices" not in t:
        raise ValueError("NGC Table A6.2 layout moved")
    b = _flat(BETTA_2004)
    rows = [m.start() for m in re.finditer(r"revenues £m", b)]
    spt, shetl = (_nums(b[k + 11: k + 120])[:7] for k in rows[:2])   # 2000/1 … 2006/7
    if spt[1] != 116.7 or shetl[1] != 50.6:
        raise ValueError("BETTA draft Tables 1/2 moved")
    spt[5:7], shetl[5:7] = betta_final_table_2_3()
    return {
        "ngc": {"fy": dict(zip(range(2001, 2006), ngc[:5])), "price_base_fy": 1999},
        "spt": {"fy": dict(zip(range(2000, 2007), spt)), "price_base_fy": 2002},
        "shetl": {"fy": dict(zip(range(2000, 2007), shetl)), "price_base_fy": 2002},
    }


@lru_cache(maxsize=None)
def betta_final_table_2_3() -> tuple[list[float], list[float]]:
    """Final proposals Dec 2004 Table 2.3, "Final proposals - Total allowed revenues", £m 2002/3
    prices, 2005/6 and 2006/7: ([SPT], [SHETL])."""
    f = _flat(BETTA_FINAL_2004)
    i = f.find("TABLE 2.3: £m 2002/3 prices")
    if i < 0:
        raise ValueError("BETTA final proposals Table 2.3 moved")
    spt = _after(f, "Final proposals - Total allowed revenues", 2, i)
    shetl = _after(f, "Final proposals - Total allowed revenues", 2, f.find("SHETL", i))
    if spt[0] != 127.5 or shetl[0] != 52.56:
        raise ValueError(f"BETTA final Table 2.3 values moved: {spt} {shetl}")
    return spt, shetl


def baseline_fy_nominal() -> dict[int, float]:
    """Sum of the three allowed revenues, FY2001/02–2005/06, each restated to nominal with RPI."""
    p = baseline_pieces()
    return {fy: sum(rpi_restate(p[k]["fy"][fy], p[k]["price_base_fy"], fy) for k in p)
            for fy in range(2001, 2006)}


def g0(base_year: int) -> float:
    """G0: CY2002–05 mean of the assembled allowed revenue, £m in `base_year` CPIH money."""
    cy = fy_to_cy(baseline_fy_nominal(), BASE_WINDOW)
    return statistics.mean(dfl.to_real(cy[y], y, base_year) for y in BASE_WINDOW)


def tpcr4_2006_07() -> dict:
    """TPCR4 FP Table 2.1 '2006/07 Revenues' (NGG gas, NGET, SPTL, SHETL, Total), 2004/05 prices."""
    v = _after(_flat(TPCR4), "2006/07 Revenues", 5)
    if abs(v[4] - sum(v[:4])) > 2:          # printed total rounds
        raise ValueError("TPCR4 Table 2.1 sum fails")
    elec = v[1] + v[2] + v[3]
    return {"elec_2004_05_prices": elec, "nominal": rpi_restate(elec, 2004, 2006)}


# ------------------------------------------------------------------ NZ7 actual TNUoS by FY

def _xlsx_total(path: Path) -> float:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            if r and r[0] == "Total to Collect from TNUoS":
                return float([c for c in r if isinstance(c, (int, float))][-1])   # January Final
    raise ValueError(f"{path.name}: 'Total to Collect from TNUoS' not found")


@lru_cache(maxsize=None)
def tnuos_fy() -> dict[int, dict]:
    """{FY start year: {gbp_m, basis, source_id}} GB TNUoS, nominal £m, FY2005/06–2026/27."""
    out: dict[int, dict] = {}

    def put(fy, v, basis, src):
        out[fy] = {"gbp_m": v, "basis": basis, "source_id": src}

    put(2005, baseline_fy_nominal()[2005], "modelled", SRC_G0)
    put(2006, tpcr4_2006_07()["nominal"], "modelled", "ofgem-tpcr4-fp-dec2006-t2.1")
    a = _flat(TAR_0809)
    v = _after(a, "Table 1 - NGET TO Revenue Summary", 0)
    v = _after(a, "Total Actual Revenue", 2, a.find("Table 1 - NGET TO Revenue Summary"))
    if "include income collected on behalf of the Scottish TOs" not in a:
        raise ValueError("TAR 2008-09: Scottish-TO note moved")
    put(2007, v[0], "measured", "ofgem-tar-2008-09-t1")
    put(2008, v[1], "measured", "ofgem-tar-2008-09-t1")
    b = _flat(TAR_0910)
    put(2009, _after(b, "Total Actual Revenue", 1, b.find("Table 1: NGET TO Revenue Summary"))[0],
        "measured", "ofgem-tar-2009-10-t1")
    v = _after(_flat(NESO18 / "neso_doc_50676.txt"), "Total TNUoS revenue", 3)
    for fy, x in zip((2010, 2011, 2012), v):
        put(fy, x, "measured", "neso-doc-50676-tnuos-2012-13")
    put(2013, _after(_flat(NESO18 / "neso_doc_50671.txt"), "TNUoS Charges", 2)[1],
        "measured", "neso-doc-50671-tnuos-2013-14")
    v = _after(_flat(NESO18 / "neso_doc_50181.txt"), "Total to Collect from TNUoS", 7)
    put(2014, v[0], "measured", "neso-doc-50181-final-tnuos-2015-16")
    put(2015, v[6], "measured", "neso-doc-50181-final-tnuos-2015-16")
    put(2016, _after(_flat(NESO18 / "neso_doc_50211.txt"), "Total to Collect from TNUoS", 7)[6],
        "measured", "neso-doc-50211-final-tnuos-2016-17")
    put(2017, _after(_flat(NESO20 / "s20d-neso_doc_50276_Final_TNUoS_2017-18_extract.md"),
                     "Total to Collect from TNUoS", 6)[5], "measured", "neso-doc-50276-final-tnuos-2017-18")
    m = re.search(r"2018/19 charging year.{0,80}?total TO revenue to be recovered will be £([\d,]+)m",
                  _flat(NESO20 / "s20d-neso_doc_114041_TNUoS_in_10_minutes_extract.md"))
    if not m:
        raise ValueError("doc 114041: 2018/19 sentence moved")
    put(2018, float(m.group(1).replace(",", "")), "measured", "neso-doc-114041-tnuos-in-10-minutes-mar2018")
    put(2019, _after(_flat(NESO20 / "s20d-neso_doc_137351_Final_TNUoS_2019-20_extract.md"),
                     "Total to Collect from TNUoS", 2)[1], "measured", "neso-doc-137351-final-tnuos-2019-20")
    put(2020, _after(_flat(NESO18 / "neso_doc_163311.txt"), "Total to Collect from TNUoS", 2)[1],
        "measured", "neso-doc-163311-final-tnuos-2020-21")
    m = re.search(r"Total revenue to be collected is £([\d,]+)m", _flat(NESO18 / "neso_doc_186176.txt"))
    put(2021, float(m.group(1).replace(",", "")), "measured", "neso-doc-186176-final-tnuos-2021-22")
    for fy, tag in ((2022, "2022-23"), (2023, "2023-24")):
        put(fy, _xlsx_total(TNUOS_XLSX / f"Final_TNUoS_Tariffs_{tag}_Tables.xlsx"), "measured",
            f"neso-final-tnuos-{tag}-tables")
    for fy, tag in ((2024, "2024-25"), (2025, "2025-26"), (2026, "2026-27")):
        t = _flat(NESO20 / f"s20d-Final_TNUoS_Tariffs_{tag}_Report.txt")
        put(fy, _after(t, "Total to Collect from TNUoS", 4)[3], "measured", f"neso-final-tnuos-{tag}-report")
    return out


TNUOS_GEN_FIXED = 0.27        # G:D 27:73 fixed by the charging methodology before 2014/15


def _pct_row(text: str, label: str, n: int) -> list[float]:
    i = text.find(label)
    if i < 0:
        raise ValueError(f"{label!r} not found")
    return [float(x) / 100 for x in re.findall(r"(\d+(?:\.\d+)?)%", text[i + len(label): i + len(label) + 120])[:n]]


def _xlsx_gen(path: Path) -> float:
    """'G.R Revenue recovered from generation (£m)', January Final column."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            cells = [c for c in (r or ()) if c is not None]
            if cells[:2] == ["G.R", "Revenue recovered from generation (£m)"]:
                return float([c for c in cells if isinstance(c, (int, float))][-1])
    raise ValueError(f"{path.name}: 'G.R Revenue recovered from generation' not found")


@lru_cache(maxsize=None)
def tnuos_gen_share_fy() -> dict[int, dict]:
    """{FY: {share, source_id}} the generators' share of GB TNUoS revenue (the G/D split), as
    read from each year's tariff document (s27b; spec §15.5 item 3). Generators' TNUoS is paid
    by generators and reaches households only through the wholesale price, which NZ1 already
    carries, so it is taken off NZ7 (and off GO5, the same share, so the two stay symmetric).

    FY2001/02–2013/14: 27%, "fixed in the charging methodology" (doc 50671, 2013/14; doc 50676,
    2012/13; NGC's pre-BETTA E&W split was the same 27:73). From 2014/15 the EU €2.5/MWh cap
    sets G.R: G.R ÷ total revenue, read from the document."""
    out: dict[int, dict] = {}
    t = _flat(NESO18 / "neso_doc_50671.txt")
    if "27% of total transmission revenue is recovered from generation" not in t \
            or "This ratio is fixed in the charging methodology" not in t:
        raise ValueError("doc 50671: 27% sentence moved")
    if "27% of the increase in the total transmission allowed revenue is recovered from generation" \
            not in _flat(NESO18 / "neso_doc_50676.txt"):
        raise ValueError("doc 50676: 27% sentence moved")
    for fy in range(2001, 2014):
        out[fy] = {"share": TNUOS_GEN_FIXED, "source_id": "neso-doc-50671-tnuos-2013-14|neso-doc-50676-tnuos-2012-13"}
    a = _flat(NESO18 / "neso_doc_50181.txt")
    gr = _after(a, "G.R (£m) Revenue recovered from generation", 2)
    tot = _after(a, "R (£m) Total TNUoS revenue", 2)
    out[2014] = {"share": gr[0] / tot[0], "source_id": "neso-doc-50181-final-tnuos-2015-16"}
    b = _flat(NESO18 / "neso_doc_50211.txt")
    gr = _after(b, "G.R Revenue recovered from generation (£m)", 2)
    tot = _after(b, "MAR Total Revenue (£m)", 2)
    out[2015] = {"share": gr[0] / tot[0], "source_id": "neso-doc-50211-final-tnuos-2016-17"}
    out[2016] = {"share": gr[1] / tot[1], "source_id": "neso-doc-50211-final-tnuos-2016-17"}
    c = _flat(NESO20 / "s20d-neso_doc_50276_Final_TNUoS_2017-18_extract.md")
    out[2017] = {"share": _pct_row(c, "G Proportion of revenue recovered from generation (%)", 6)[5],
                 "source_id": "neso-doc-50276-final-tnuos-2017-18"}
    m = re.search(r"total TO revenue to be recovered will be £([\d,]+)m\. This is recovered through generation "
                  r"tariffs totalling £([\d.,]+)m", _flat(NESO20 / "s20d-neso_doc_114041_TNUoS_in_10_minutes_extract.md"))
    if not m:
        raise ValueError("doc 114041: generation-tariff sentence moved")
    out[2018] = {"share": float(m.group(2).replace(",", "")) / float(m.group(1).replace(",", "")),
                 "source_id": "neso-doc-114041-tnuos-in-10-minutes-mar2018"}
    d = _flat(NESO20 / "s20d-neso_doc_137351_Final_TNUoS_2019-20_extract.md")
    out[2019] = {"share": _after(d, "G.MAR Revenue recovered from generation (£m)", 2)[1]
                 / _after(d, "MAR Total Revenue (£m)", 2)[1], "source_id": "neso-doc-137351-final-tnuos-2019-20"}
    e = _flat(NESO18 / "neso_doc_163311.txt")
    out[2020] = {"share": _after(e, "Revenue recovered from generation (£m)", 2)[1]
                 / _after(e, "Total Revenue (£m)", 2)[1], "source_id": "neso-doc-163311-final-tnuos-2020-21"}
    f = _flat(NESO18 / "neso_doc_186176.txt")
    out[2021] = {"share": _pct_row(f, "G % of revenue from generation", 4)[3],
                 "source_id": "neso-doc-186176-final-tnuos-2021-22"}
    for fy, tag in ((2022, "2022-23"), (2023, "2023-24"), (2024, "2024-25"), (2025, "2025-26"), (2026, "2026-27")):
        p = TNUOS_XLSX / f"Final_TNUoS_Tariffs_{tag}_Tables.xlsx"
        out[fy] = {"share": _xlsx_gen(p) / _xlsx_total(p), "source_id": f"neso-final-tnuos-{tag}-tables"}
    for fy, v in out.items():
        if not 0.10 < v["share"] < 0.30:
            raise ValueError(f"TNUoS G share FY{fy} {v['share']:.3f} out of range")
    return out


def tnuos_gen_share_cy(years=YEARS) -> dict[int, float]:
    """The generators' TNUoS share by calendar year (§2 weighting)."""
    return fy_to_cy({k: v["share"] for k, v in tnuos_gen_share_fy().items()}, years)


GEN_SHARE_OPTIONS = ("removed", "included")   # 'removed' = central (s27b); 'included' = pre-s27 behaviour


def nz7(years=YEARS, gen_share: str = "removed") -> dict[int, dict]:
    """NZ7 by calendar year, £m nominal, from the shared cost register (0168): series TNUOS (the whole charge;
    CY2002–05 the assembled allowances, modelled) and, for 'removed', Reliable Britain's input adjustment
    rb.TNUOS.generators_share_out. Both were built by `src_nz7` at the v4-s39 release.

    gen_share: 'removed' (central, s27b): each FY's total less the generators' share
    (`tnuos_gen_share_fy`); 'included': the whole TNUoS total (the pre-s27 line)."""
    from gascf import register_pin as RP
    if gen_share not in GEN_SHARE_OPTIONS:
        raise ValueError(gen_share)
    reg = RP.register()
    vals = reg.line("TNUOS", "rb") if gen_share == "removed" else reg.series("TNUOS")
    gs = tnuos_gen_share_fy() if gen_share == "removed" else None
    out = {}
    for y in years:
        r = reg.row("TNUOS", y)
        src = r["source_id"]
        if gs is not None and y not in BASE_WINDOW:
            src += f"|{gs[y - 1]['source_id']}|{gs[y]['source_id']}"
        out[y] = {"gbp_m": vals[y], "basis": r["basis"], "source_id": src, "geo": "GB"}
    if gen_share == "removed":
        g = tnuos_gen_share_cy(years)
        for y in out:
            out[y]["gen_share"] = g[y]
    return dict(sorted(out.items()))


def src_nz7(years=YEARS, gen_share: str = "removed") -> dict[int, dict]:
    """The engine's reading of its stored TNUoS files: the register's builder only (0168).
    NZ7 by calendar year, £m nominal. Basis = weakest of the two FYs used.

    gen_share: 'removed' (central, s27b): each FY's total less the generators' share
    (`tnuos_gen_share_fy`); 'included': the whole TNUoS total (the pre-s27 line)."""
    if gen_share not in GEN_SHARE_OPTIONS:
        raise ValueError(gen_share)
    fy = tnuos_fy()
    gs = tnuos_gen_share_fy()
    keep = (lambda k: 1 - gs[k]["share"]) if gen_share == "removed" else (lambda k: 1.0)
    cy = fy_to_cy({k: v["gbp_m"] * keep(k) for k, v in fy.items()}, [y for y in years if y >= 2006])
    rank = {"measured": 0, "modelled": 1, "estimated": 2}
    out = {}
    for y in years:
        a, b = fy.get(y - 1), fy.get(y)
        if a is None:                                   # CY2002–2005: before the first GB year
            continue
        basis = max(a["basis"], b["basis"], key=rank.get)
        src = f"{a['source_id']}|{b['source_id']}"
        if gen_share == "removed":
            src += f"|{gs[y - 1]['source_id']}|{gs[y]['source_id']}"
        out[y] = {"gbp_m": cy[y], "basis": basis, "source_id": src, "geo": "GB"}
    # 2002–2005: no GB TNUoS existed (three regimes); the assembled allowances stand in, modelled.
    base = fy_to_cy({k: v * keep(k) for k, v in baseline_fy_nominal().items()}, BASE_WINDOW)
    for y in BASE_WINDOW:
        out[y] = {"gbp_m": base[y], "basis": "modelled", "source_id": SRC_G0, "geo": "GB"}
    if gen_share == "removed":
        g = tnuos_gen_share_cy(years)
        for y in out:
            out[y]["gen_share"] = g[y]
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ §7.3 renewal allowance R

@lru_cache(maxsize=None)
def nlr_allowances() -> dict[str, dict]:
    """Non-load-related capex allowances by control, as printed, with price base."""
    t = _flat(TPCR4)
    tp = {}
    for co, table in (("NGET", "Table 3.1 - NGET: Summary of Final Proposals"),
                      ("SHETL", "Table 4.1 - SHETL: Summary of Final Proposals"),
                      ("SPTL", "Table 5.1 - SPTL: Summary of Final Proposals")):
        i = t.find(table)
        tp[co] = dict(zip(range(2007, 2012), _after(t, "- non-load", 5, i)))
    t1 = _flat(RIIO_T1_NGET)
    nget_t1 = _after(t1, "Non load-related capex", 3, t1.find("Table 3.2 – RIIO-T1 total cost parameters for NGET (TO)"))[2]
    s = _flat(RIIO_T1_SCOT)
    spt_t1 = _after(s, "Total non-load related capex baseline", 8, s.find("Table 4.3 – SPTL’s non-load related capex"))
    shetl_t1 = _after(s, "Total non-load related capex baseline", 8, s.find("Table 4.7 – Annual baselines for SHETL"))
    r2 = {}
    for co, p in RIIO2.items():
        r2[co] = _after(_flat(p), "Non-load related capex", 3)[2]           # Ofgem FD baseline
    return {
        "tpcr4": {"annual": {fy: sum(tp[c][fy] for c in tp) for fy in range(2007, 2012)},
                  "price_base_fy": 2004, "index": "rpi", "source_id": "ofgem-tpcr4-fp-dec2006-t3.1-4.1-5.1"},
        "riio_t1": {"total_8yr": nget_t1 + sum(spt_t1) + sum(shetl_t1), "years": range(2013, 2021),
                    "price_base_fy": 2009, "index": "rpi",
                    "source_id": "ofgem-riio-t1-fp-nget-t3.2-spt-t4.3-shetl-t4.7"},
        "riio2": {"total_5yr": sum(r2.values()), "years": range(2021, 2026),
                  "price_base_fy": 2018, "index": "cpih", "source_id": "ofgem-riio2-fd-annexes-t1-t6"},
    }


RETURN = {"tpcr4": 0.0505, "riio_t1": 0.0455}   # vanilla WACC / allowed return on capital
# RIIO-2 (v4-s34, fact-check W4 / F3): each TO's own "Allowed return on capital" as printed in its
# FD annex (NGET 2.81%, SHET 2.69%, SPT 2.81%), weighted by that TO's FD non-load-related capex
# (the renewal allowance's own weights). Until v4-s33 NGET's 2.81% was applied to all three.


@lru_cache(maxsize=None)
def riio2_returns() -> dict[str, float]:
    """{TO: allowed return on capital} read from each RIIO-2 FD annex (revised, Feb 2021)."""
    out = {}
    for co, p in RIIO2.items():
        m = re.search(r"Allowed return on capital ([\d.]+)%", _flat(p))
        if not m:
            raise ValueError(f"RIIO-2 FD {co} annex: 'Allowed return on capital' moved")
        out[co] = float(m.group(1)) / 100
    return out


@lru_cache(maxsize=None)
def riio2_return_weighted() -> float:
    """RIIO-2 return weighted by each TO's FD NLR baseline (`nlr_allowances` RIIO-2 inputs)."""
    w = {co: _after(_flat(p), "Non-load related capex", 3)[2] for co, p in RIIO2.items()}
    r = riio2_returns()
    return sum(w[c] * r[c] for c in w) / sum(w.values())


def allowed_return(ctrl: str) -> float:
    return riio2_return_weighted() if ctrl == "riio2" else RETURN[ctrl]


def baseline_nlr_fy() -> float:
    """2002–05 NLR level: NGC Table 3.1 Ofgem projection NLRE £735m over 2001/02–05/06
    (1999/00 prices) ÷ 5, plus the Scottish TOs' 2005/06 roll-forward NLR (2002/03 prices:
    SPT 44.8, SHETL 11.1; final proposals Dec 2004 Appendices 5-6, unchanged from the draft),
    all restated to FY2004/05 RPI money."""
    t = _flat(NGC_2000)
    lre, nlre, tot = _after(t, "Ofgem Projection", 3, t.find("Table 3.1 : Comparison of LRE and NLRE"))
    if lre + nlre != tot:
        raise ValueError("NGC 2000 Table 3.1 moved")
    b = _flat(BETTA_FINAL_2004)
    k = [m.start() for m in re.finditer("Non Load related", b)]
    spt, shetl = _nums(b[k[0] + 16:k[0] + 40])[0], _nums(b[k[1] + 16:k[1] + 40])[0]
    if (spt, shetl) != (44.8, 11.1):
        raise ValueError(f"BETTA final Appendices 5-6 NLR moved: {spt} {shetl}")
    return rpi_restate(nlre / 5, 1999, 2004) + rpi_restate(spt + shetl, 2002, 2004)


def _control_of(fy: int) -> str:
    return "tpcr4" if fy <= 2012 else ("riio_t1" if fy <= 2020 else "riio2")


def renewal_excess_fy() -> dict[int, float]:
    """FY → NLR allowance above the 2002-05 level added that FY, £m nominal (money of FY)."""
    a = nlr_allowances()
    base04 = baseline_nlr_fy()
    out: dict[int, float] = {}
    for fy in range(2007, 2026):
        if fy in a["tpcr4"]["annual"]:
            cap = rpi_restate(a["tpcr4"]["annual"][fy], 2004, fy)
        elif fy == 2012:                         # TPCR4 one-year rollover: hold 2011/12 in real terms
            cap = rpi_restate(a["tpcr4"]["annual"][2011], 2004, fy)
        elif fy in a["riio_t1"]["years"]:
            cap = rpi_restate(a["riio_t1"]["total_8yr"] / 8, 2009, fy)
        else:
            c = dfl.cpih()
            c_fy = 0.75 * c[fy] + 0.25 * c.get(fy + 1, c[fy])     # FY2025/26: CY2026 not yet published
            cap = a["riio2"]["total_5yr"] / 5 * c_fy / (0.75 * c[2018] + 0.25 * c[2019])
        out[fy] = max(0.0, cap - rpi_restate(base04, 2004, fy))
    return out


def renewal_allowance(years=YEARS) -> dict[int, dict]:
    """R(y), £m nominal, low/central/high (spec §7.3): the revenue a no-net-zero grid would be
    allowed on the non-load-related (asset replacement) allowance above the 2002–05 level.

    v4-s35 (T3): the regulator's own mechanics, a RAV roll-forward. Each FY's excess capex v
    enters the RAV; in FY t it earns (i) depreciation, straight line over 45 years, and (ii) the
    CURRENT control's real allowed return on the opening remaining balance, both indexed from
    v to t by the control index (RPI to FY2020/21, then CPIH; `control_index_fy`). Primary:
    RIIO-ET2 PCFH (licence Special Condition 8.1) para 4.1, the cost of capital is "calculated as
    a percentage return on the licensee’s RAV ... This is calculated on a real basis"; para 2.17,
    values indexed by PIt (RPI before April 2021, CPIH after). Earlier controls likewise: TPCR4
    and RIIO-T1 indexed the RAV by RPI (RIIO-T1 FP overview "the previous RPI-X framework", and
    45-year straight-line depreciation for new assets, para 3.44). Until v4-s34: a frozen
    nominal annuity per vintage at that vintage's return.

    v4-s35 (T4, Richard 14 Oct 2026): central = the WHOLE allowance above the 2002–05 level (was
    half). low = 0 (R not counted), high = central. Tag estimated."""
    exc = renewal_excess_fy()
    idx = {fy: control_index_fy(fy) for fy in range(2001, 2026)}
    n = ANNUITY_YEARS
    r_fy: dict[int, float] = {}
    for t in range(2001, 2026):
        r = allowed_return(_control_of(t))
        tot = 0.0
        for v, e in exc.items():
            if v > t:
                continue
            remaining = e * max(0.0, 1 - (t - v) / n)          # opening balance, vintage-v money
            tot += (e / n + r * remaining) * idx[t] / idx[v]
        r_fy[t] = tot
    r_fy[2026] = r_fy[2025]
    cy = fy_to_cy(r_fy, years)
    return {y: {"low": 0.0, "central": cy[y], "high": cy[y], "basis": "estimated",
                "source_id": SRC_R} for y in years}


# ------------------------------------------------------------------ GO5

RPI_LAST_FY = 2020       # RIIO-T1 (and TPCR3/TPCR4 before it) indexed by RPI to FY2020/21
SRC_INDEX = "ofgem-riio-et2-pcfh-2.17-pi-rpi-to-cpih"
RIIO_ED2_FINANCE = RAW / "ofgem_s20e/s20e-RIIO-ED2_FD_Finance_Annex.txt"   # corroborating (distribution)
GO5_INDEX_OPTIONS = ("rpi", "cpih", "rpi_x")   # 'rpi' = central (s27b); 'cpih' = pre-s27 behaviour;
# 'rpi_x' = the controls' own X values (0091, sensitivity)


def control_index_fy(fy: int) -> float:
    """The index the transmission price controls carried allowed revenue by, FY basis.

    FY2001/02–2020/21: RPI (TPCR3 2001–07 and TPCR4 2007–13 were RPI-X; RIIO-T1 2013–21 indexed
    revenue and RAV by RPI: "the previous RPI-X framework", RIIO-T1 FP overview §1.8). From
    FY2021/22 (RIIO-T2, 1 April 2021): CPIH, chained on at FY2020/21. Transmission primary (v4-s35,
    T8): RIIO-ET2 Price Control Financial Handbook (licence Special Condition 8.1) para 2.17: PIt is
    "the arithmetic average value of each of the twelve monthly values of PIm from 1 April to 31
    March", with PIm = RPIm before April 2021, a 50/50 RPI/CPIH link in April 2021, CPIH after
    (stored `ofgem_s35/s35-ET2_PCFH_C06_published_31May2024.txt`). Until v4-s34 this cited the
    RIIO-2 FD Finance Annex ¶2.24, which is about CPI-linked debt, not revenue indexation.
    Corroborating (a distribution document): RIIO-ED2 FD Finance Annex ¶2.40 "switch indexation of
    the Regulatory Asset Value (RAV) from RPI at RIIO-1 to CPIH at RIIO-2"."""
    if fy <= RPI_LAST_FY:
        return rpi_fy(fy)
    c = dfl.cpih()
    c_fy = lambda k: 0.75 * c[k] + 0.25 * c.get(k + 1, c[k])     # FY2025/26: CY2026 not yet published
    return rpi_fy(RPI_LAST_FY) * c_fy(fy) / c_fy(RPI_LAST_FY)


def _check_index_source() -> None:
    f = _flat(PCFH_ET2)
    for q in ("2.17. Where variable values need to be deflated from a nominal price base to the 2018/19",
              "monthly values of PIm from 1 April to 31 March within Regulatory Year t",
              "Retail Prices Index (all items) (series: CHAW)",
              "calculated as a percentage return on the licensee’s RAV",
              "This is calculated on a real basis"):
        if q not in f:
            raise ValueError(f"RIIO-ET2 PCFH: {q!r} moved")
    t = _flat(RIIO_ED2_FINANCE)
    if "switch indexation of the Regulatory Asset Value (RAV) from RPI at RIIO-1 to CPIH at RIIO-2" not in t:
        raise ValueError("RIIO-ED2 FD Finance Annex: RPI→CPIH sentence moved")


RPI_X_NGET_2006_REAL_STEP = 0.060   # Ofgem 253/05 para 4.10 (PDF p.36): NGET P0 +6.0% real for 2006/07
RPI_X_STEP_SHARE_FY = 2005          # 0091 fit|A3: weights = 2005/06 revenues (SPT, SHETL flat: 279/04 Table 2.3)


def rpi_x_2006_step() -> dict:
    """Decision 0091, item A (fit|A3): the GB control-index step in FY2006/07.

    NGET's +6.0% real step (SPT and SHETL flat) weighted by the three TOs' FY2005/06 revenues as
    printed in `baseline_pieces` (NGC 714 in 1999/00 prices; SPT 127.5 and SHETL 52.56 in 2002/03
    prices), each restated to 2004/05 prices by `rpi_fy` (ONS CHAW)."""
    p = baseline_pieces()
    v = {name: p[key]["fy"][RPI_X_STEP_SHARE_FY] * rpi_fy(2004) / rpi_fy(p[key]["price_base_fy"])
         for name, key in (("NGET", "ngc"), ("SPT", "spt"), ("SHETL", "shetl"))}
    total = sum(v.values())
    shares = {k: x / total for k, x in v.items()}
    return {"values_2004_05_prices": v, "shares": shares,
            "step": 1 + shares["NGET"] * RPI_X_NGET_2006_REAL_STEP}


def tpcr4_base_allowances() -> dict[int, float]:
    """{FY: NGET + SHETL + SPTL base price control revenue allowance}, £m 2004/05 prices,
    FY2006/07-2011/12: TPCR4 Final Proposals Tables 3.1, 4.1 and 5.1."""
    t = _flat(TPCR4)
    tot = [0.0] * 6
    for table in ("Table 3.1 - NGET", "Table 4.1 - SHETL", "Table 5.1 - SPTL"):
        v = _after(t, "Base Price Control Revenue Allowance", 6, t.find(table))
        tot = [a + b for a, b in zip(tot, v)]
    return dict(zip(range(2006, 2012), tot))


def rpi_x_multiplier_fy() -> dict[int, float]:
    """Decision 0091: the multiplier on the control index for the controls' own X values, by FY.

    FY2001/02-2005/06 (the base window): 1. NGC's RPI-1.5% is inside the window, so G0 in index
    units already carries it. FY2006/07: the GB step from NGET's one-year +6.0% real extension
    (`rpi_x_2006_step`). FY2007/08-2011/12 (TPCR4, RPI+2 for the TOs): the real path of the three
    TOs' base allowances against 2006/07 (`tpcr4_base_allowances`). FY2012/13: X = 0, a stated
    exclusion (the one-year rollover reset is not modelled: no company's TII share of it is
    published). FY2013/14 on (RIIO): no X, so the multiplier stays at its 2011/12 value."""
    m = {fy: 1.0 for fy in range(2001, 2006)}
    m[2006] = rpi_x_2006_step()["step"]
    base = tpcr4_base_allowances()
    for fy in range(2007, 2012):
        m[fy] = m[2006] * base[fy] / base[2006]
    for fy in range(2012, max(YEARS) + 1):
        m[fy] = m[2011]      # 2012/13 at X = 0 (0091 item B1, a stated exclusion); RIIO: no X
    return m


def go5(base_year: int, years=YEARS, index: str = "rpi", gen_share: str = "removed") -> dict[int, dict]:
    """GO5 = (G0 × index(y) + R(y)) × (1 − generators' TNUoS share(y)), £m nominal, with the R range.

    index: 'rpi' (central, s27b): G0 carried as the price controls carried it, RPI to FY2020/21
      then CPIH (`control_index_fy`), calendar-weighted (§2); 'cpih': G0 × cpih(y)/cpih(base),
      the pre-s27 line; 'rpi_x' (0091, sensitivity): as 'rpi' with the controls' own X values on
      top (`rpi_x_multiplier_fy`), so G0 in index units (base window) is unchanged.
    gen_share: 'removed' (central for the engine's own bills: `Settings.tnuos_gen`, run file
      `meta.central_settings.tnuos_gen`; decision 0024): the same per-year generators' share
      (`tnuos_gen_share_fy`) is taken off NZ7 and GO5, so the two grids are compared on the same
      demand-side basis. 'included': no removal. Used only by the Subsidy Clock export
      (`clock_export.GEN_SHARE`), because the Clock has no power-price line and so counts the
      generators' part as a cost Britain paid."""
    if index not in GO5_INDEX_OPTIONS or gen_share not in GEN_SHARE_OPTIONS:
        raise ValueError((index, gen_share))
    r = renewal_allowance(years)
    if index == "cpih":
        g, c = g0(base_year), dfl.cpih()
        carried_all = {y: g * c[y] / c[base_year] for y in years}
        src = f"{SRC_G0}|{SRC_R}"
    else:
        _check_index_source()
        mult = rpi_x_multiplier_fy() if index == "rpi_x" else {}
        idx = fy_to_cy({fy: control_index_fy(fy) * mult.get(fy, 1.0)
                        for fy in range(2001, max(years) + 1)},
                       range(min(min(years), BASE_WINDOW[0]), max(years) + 1))
        cy = fy_to_cy(baseline_fy_nominal(), BASE_WINDOW)
        g_units = statistics.mean(cy[y] / idx[y] for y in BASE_WINDOW)     # G0 in index units
        carried_all = {y: g_units * idx[y] for y in years}
        src = f"{SRC_G0}|{SRC_R}|{SRC_INDEX}|ons-rpi-chaw"
        if index == "rpi_x":
            src += "|ofgem-253-05-nget-2006-07|ofgem-tpcr4-fp-206-06"
    gs = tnuos_gen_share_cy(years) if gen_share == "removed" else {y: 0.0 for y in years}
    if gen_share == "removed":
        src += "|tnuos-gen-share"
    out = {}
    for y in years:
        k = 1 - gs[y]
        carried = carried_all[y] * k
        out[y] = {"carried_gbp_m": carried, "gbp_m": carried + r[y]["central"] * k,
                  "low": carried + r[y]["low"] * k, "high": carried + r[y]["high"] * k,
                  "gen_share": gs[y], "index": index,
                  "basis": "modelled", "source_id": src, "geo": "GB"}
    return out


# ------------------------------------------------------------------ 0102 alternative (methods-page check)

PRE_BETTA_LAST_FY = 2004    # FY2004/05: the last year before BETTA (1 April 2005)


def scot_share_alt(base_year: int = 2025) -> dict:
    """Decision 0102: the alternative Scottish treatment before BETTA, as a printed check only.

    Central keeps the generators' 27% on the whole stand-in GB base (NGC + SPT + SHETL) before April
    2005. The alternative takes it off NGC (England and Wales) only for FY2001/02-2004/05, so NZ7
    keeps the Scottish part whole and GO5's CY2002-05 share falls to 27% × NGC / base. Both moves
    are £m in `base_year` CPIH money, CY2002-05; the gap moves by NZ7's change less GO5's."""
    p = baseline_pieces()
    base = baseline_fy_nominal()
    scot_pre = {fy: (sum(rpi_restate(p[k]["fy"][fy], p[k]["price_base_fy"], fy) for k in ("spt", "shetl"))
                     if fy <= PRE_BETTA_LAST_FY else 0.0) for fy in base}
    share_alt = {fy: TNUOS_GEN_FIXED * (1 - scot_pre[fy] / base[fy]) for fy in base}
    gs_alt = fy_to_cy(share_alt, BASE_WINDOW)
    d_nz7 = {y: TNUOS_GEN_FIXED * v for y, v in fy_to_cy(scot_pre, BASE_WINDOW).items()}
    central = go5(base_year, BASE_WINDOW)
    d_go5 = {y: (r["gen_share"] - gs_alt[y]) * r["gbp_m"] / (1 - r["gen_share"]) for y, r in central.items()}
    d_nz7_real = {y: dfl.to_real(d_nz7[y], y, base_year) for y in BASE_WINDOW}
    d_go5_real = {y: dfl.to_real(d_go5[y], y, base_year) for y in BASE_WINDOW}
    nz7_shift, go5_shift = sum(d_nz7_real.values()), sum(d_go5_real.values())
    return {"gap_effect_2002_05_gbp_m": nz7_shift - go5_shift, "level_shift_gbp_m": nz7_shift,
            "level_shift_by_line_gbp_m": {"NZ7": nz7_shift, "GO5": go5_shift}}
