"""Policy-cost lines of the net-zero bill, by calendar year 2002–2025 (spec §3.1 NZ2–NZ5, NZ8; §5.2).

Every function returns `{year: {"gbp_m": float, "basis": str, "source_id": str}}`, nominal £m,
calendar year. The parent deflates (CPIH, `deflator_cpih.py`) and divides by households.

- **NZ2 Renewables Obligation (RO)**: ROCs presented × the "worth" of a ROC to a supplier, by
  obligation year (April–March), from Ofgem's annual reports, read from the stored PDFs.
  A ROC (Renewables Obligation Certificate) is issued per unit of renewable output; suppliers
  must present a set number per MWh sold or pay the buy-out price. "Worth" = buy-out price plus
  the recycled buy-out fund per ROC.
- **NZ3 Feed-in tariffs (FiT)**: Ofgem FIT scheme value, Figure 3.3 of the SY15 annual report.
- **NZ4 Contracts for Difference (CfD)**: LCCC payments, summed by settlement month.
- **CM_paid**: Capacity Market payments, LCCC, summed by month. NZ5 itself is the parent's.
- **NZ8 Climate Change Levy (CCL), electricity**: HMRC electricity declarations, calendar year.

Financial years become calendar years by time weighting (spec §2):
`CY(y) = 0.25 × FY(y−1/y) + 0.75 × FY(y/y+1)`; monthly series are summed by month.
"""
from __future__ import annotations

import csv
import html
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pymupdf

RAW = Path(__file__).parents[2] / "data/raw"
RO_0506 = RAW / "ofgem_ro_fit/s18c-RO_annual_report_2005-06.pdf"
RO_0910 = RAW / "ofgem_ro_fit/s18c-RO_annual_report_2009-10.pdf"
RO_SY23 = RAW / "ofgem_ro_fit/RO_annual_report_SY23.pdf"
RO_OBLIG_2526 = RAW / "ofgem_ro_fit/s20c-RO_total_obligation_2025-26.html"
RO_BUYOUT_2526 = RAW / "ofgem_ro_fit/s20c-RO_buyout_price_2025-26.html"
FIT_SY15 = RAW / "ofgem_ro_fit/FIT_annual_report_SY15.pdf"
FIT_QR = {n: RAW / f"ofgem_ro_fit/s20c-FIT_quarterly_report_issue_{n}.pdf" for n in range(57, 65)}
CFD_CSV = RAW / "lccc/actual_cfd_generation.csv"
CM_CSV = RAW / "lccc/s18c-capacity_obligation_by_auction.csv"
HMRC_ENVTAX = RAW / "hmrc/s18a-envtax_bulletin_tables_2026-03-31.ods"

YEARS = range(2002, 2026)

SRC_RO_0506 = "ofgem-ro-annual-report-2005-06-t1-t3"
SRC_RO_0910 = "ofgem-ro-annual-report-2009-10-t1-t3"
SRC_RO_SY23 = "ofgem-ro-annual-report-sy23-fig-a4.1"
SRC_RO_2526 = "ofgem-ro-total-obligation-2025-26+buyout-2025-26"
SRC_FIT = "ofgem-fit-annual-report-sy15-fig3.3"
SRC_FIT_QR = "ofgem-fit-quarterly-reports-57-64"
SRC_CFD = "lccc-actual-cfd-generation"
SRC_CM = "lccc-capacity-obligation-by-auction"
SRC_CCL = "hmrc-envtax-bulletin-2026-03-t1b"


# ------------------------------------------------------------------ helpers

def _pdf_text(path: Path) -> str:
    return re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(path)))


def _num(s: str) -> float:
    return float(s.replace(",", "").replace("£", ""))


def fy_to_cy(fy: dict[int, float], years=YEARS) -> dict[int, float]:
    """Time-weight financial years (keyed by start year: 2002 = 2002-03) to calendar years.
    A missing FY counts as zero only before the scheme's first year; otherwise it raises."""
    first = min(fy)
    out = {}
    for y in years:
        a = fy.get(y - 1, 0.0 if y - 1 < first else None)
        b = fy.get(y, 0.0 if y < first else None)
        if a is None or b is None:
            raise ValueError(f"financial year missing for calendar year {y}")
        out[y] = 0.25 * a + 0.75 * b
    return out


def read_ods(path: Path) -> dict[str, list[list]]:
    """Minimal OpenDocument spreadsheet reader (stdlib only): {sheet: rows of cell values}."""
    T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    O = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
    P = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"
    root = ET.fromstring(zipfile.ZipFile(path).read("content.xml"))
    out = {}
    for t in root.iter(T + "table"):
        rows = []
        for r in t.iter(T + "table-row"):
            cells = []
            for c in r:
                if c.tag not in (T + "table-cell", T + "covered-table-cell"):
                    continue
                n = min(int(c.get(T + "number-columns-repeated", "1")), 200)
                if c.get(O + "value-type") in ("float", "percentage", "currency"):
                    v = float(c.get(O + "value"))
                else:
                    v = " ".join("".join(p.itertext()) for p in c.iter(P)) or None
                cells.extend([v] * n)
            while cells and cells[-1] is None:
                cells.pop()
            rows.extend([cells] * min(int(r.get(T + "number-rows-repeated", "1")), 5))
        out[t.get(T + "name")] = rows
    return out


def _row(v: float, basis: str, src: str) -> dict:
    return {"gbp_m": v, "basis": basis, "source_id": src}


# ------------------------------------------------------------------ NZ2 Renewables Obligation

def _grab_row(text: str, label: str, n: int, start: int = 0) -> tuple[list[float], int]:
    pat = re.escape(label) + r"\S*" + r"".join(r"\s+(£?[\d,]+(?:\.\d+)?)" for _ in range(n))
    m = re.compile(pat).search(text, start)
    if not m:
        raise ValueError(f"RO report: row {label!r} not found after {start}")
    return [_num(g) for g in m.groups()], m.end()


@lru_cache(maxsize=None)
def read_ro_sy1_4() -> dict[int, float]:
    """SY1–SY4 (2002-03 to 2005-06), £m: Σ regions ROCs presented × worth (Tables 1–3, 2005-06 report)."""
    t = _pdf_text(RO_0506)
    i = t.index("Table 1: How suppliers complied with their obligations in England & Wales")
    j = t.index("Table 2: How suppliers complied with their obligations in Scotland")
    k = t.index("Table 3: How suppliers complied with their obligations in Northern Ireland")
    ew_rocs, _ = _grab_row(t, "Total number of ROCs presented", 4, i)
    ew_worth, _ = _grab_row(t, 'What a ROC was "worth" to a supplier', 4, i)
    sc_rocs, _ = _grab_row(t, "Total number of ROCs presented", 4, j)
    sc_worth, _ = _grab_row(t, 'What a ROC was "worth" to a supplier', 4, j)
    ni_rocs, _ = _grab_row(t, "Total number of ROCs presented", 1, k)
    ni_worth, _ = _grab_row(t, 'What a ROC was "worth" to a supplier', 1, k)
    if not (ew_worth[0] < 100 and sc_rocs[0] == 478358):
        raise ValueError("RO 2005-06 report layout moved")
    out = {2002 + n: (ew_rocs[n] * ew_worth[n] + sc_rocs[n] * sc_worth[n]) / 1e6 for n in range(4)}
    out[2005] += ni_rocs[0] * ni_worth[0] / 1e6       # NIRO began 1 April 2005
    return out


@lru_cache(maxsize=None)
def read_ro_sy5_8() -> dict[int, float]:
    """SY5–SY8 (2006-07 to 2009-10), £m: Σ (E&W + Scotland + NI ROCs presented) × the single worth."""
    t = _pdf_text(RO_0910)
    i = t.index("2006-07 2007-08 2008-09 2009-10 Total obligation (ROCs)")
    rocs = [0.0] * 4
    pos = i
    worth = None
    for _ in range(3):                                   # E&W, Scotland, NI tables in order
        r, pos = _grab_row(t, "Total ROCs presented", 4, pos)
        w, _ = _grab_row(t, "'Worth' of a ROC to a supplier", 4, pos)
        rocs = [a + b for a, b in zip(rocs, r)]
        if worth is not None and w != worth:
            raise ValueError("RO 2009-10: worth differs between countries")
        worth = w
    return {2006 + n: rocs[n] * worth[n] / 1e6 for n in range(4)}


@lru_cache(maxsize=None)
def read_ro_sy9_23() -> dict[int, dict]:
    """SY9–SY23 from Figure A4.1 of the SY23 report: {start year: {rocs_m, worth, gbp_m}}.
    ROCs are printed to 0.1m, so each value carries up to ±0.05m × worth (≈ ±£3.6m)."""
    t = _pdf_text(RO_SY23)
    i = t.index("Figure A4.1 - Determination of ROC recycle value since SY9")
    out = {}
    for m in re.finditer(r"SY(\d+) \((\d{4})-(\d{2})\) £([\d,.]+)m ([\d.]+)m £([\d.]+) £([\d.]+) ([\d.]+) £([\d.]+)",
                         t[i:i + 3000]):
        sy, y = int(m.group(1)), int(m.group(2))
        if sy != y - 2001:
            raise ValueError(f"RO A4.1: SY{sy} labelled {y}")
        rocs, worth = float(m.group(5)), float(m.group(7))
        out[y] = {"rocs_m": rocs, "worth": worth, "gbp_m": rocs * worth}
    if sorted(out) != list(range(2010, 2025)):
        raise ValueError(f"RO A4.1: scheme years read {sorted(out)}")
    return out


def ro_sy23_printed_bn() -> float:
    """Ofgem's printed SY23 scheme value, £bn (para 5.36: 'giving a scheme value of £7.70 billion')."""
    t = _pdf_text(RO_SY23)
    m = re.search(r"each worth £72\.77 giving a scheme value of £([\d.]+) billion", t)
    if not m:
        raise ValueError("RO SY23: scheme value sentence not found")
    return float(m.group(1))


def _html_text(path: Path) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(errors="ignore"))))


@lru_cache(maxsize=None)
def read_ro_2025_26_ex_ante() -> dict[str, float]:
    """SY24 (2025-26), ex ante: Ofgem total obligation (ROCs) × buy-out price (£/ROC)."""
    a = _html_text(RO_OBLIG_2526)
    b = _html_text(RO_BUYOUT_2526)
    m1 = re.search(r"total obligation value of ([\d,]+) Renewable Obligation Certificates", a)
    m2 = re.search(r"Buy-out price for 2025 to 2026 £([\d.]+) per ROC", b)
    if not (m1 and m2 and "1 April 2025 to 31 March 2026" in a):
        raise ValueError("Ofgem RO 2025-26 pages: anchor text moved")
    rocs, bo = _num(m1.group(1)), float(m2.group(1))
    return {"rocs": rocs, "buyout": bo, "gbp_m": rocs * bo / 1e6}


def ro_fy() -> dict[int, tuple[float, str, str]]:
    """RO by obligation year (start year), £m, with basis and source."""
    out = {y: (v, "measured", SRC_RO_0506) for y, v in read_ro_sy1_4().items()}
    out.update({y: (v, "measured", SRC_RO_0910) for y, v in read_ro_sy5_8().items()})
    out.update({y: (r["gbp_m"], "measured", SRC_RO_SY23) for y, r in read_ro_sy9_23().items()})
    out[2025] = (read_ro_2025_26_ex_ante()["gbp_m"], "estimated", SRC_RO_2526)
    return out


def ro(years=YEARS) -> dict[int, dict]:
    """NZ2 by calendar year, £m (time-weighted). A year touching SY24 is 'estimated'."""
    fy = ro_fy()
    cy = fy_to_cy({y: v[0] for y, v in fy.items()}, years)
    out = {}
    for y in years:
        parts = [fy[k] for k in (y - 1, y) if k in fy]
        basis = "estimated" if any(p[1] == "estimated" for p in parts) else "measured"
        out[y] = _row(cy[y], basis, "+".join(sorted({p[2] for p in parts})))
    return out


# ------------------------------------------------------------------ NZ3 Feed-in tariffs

@lru_cache(maxsize=None)
def read_fit_scheme_value() -> dict[int, float]:
    """FIT scheme value SY1–SY15, £m, keyed by start year (SY1 = 2010-11), from the Fig 3.3
    data labels in the SY15 report's text layer; checked against the figure's own prose."""
    doc = pymupdf.open(FIT_SY15)
    page = next(p.get_text() for p in doc if "Figure 3.3: FIT scheme value, SY1-15" in p.get_text())
    vals = [_num(v) for v in re.findall(r"^£([\d,]+)m$", page, re.M)]
    if len(vals) != 15:
        raise ValueError(f"FIT Fig 3.3: {len(vals)} labels")
    prose = re.sub(r"\s+", " ", page)
    for sy, v in ((11, 1764), (12, 1575), (14, 1858)):
        if f"£{v:,} million" not in prose or vals[sy - 1] != v:
            raise ValueError(f"FIT Fig 3.3: SY{sy} label does not match the prose")
    return {2009 + sy: v for sy, v in enumerate(vals, 1)}


@lru_cache(maxsize=None)
def read_fit_quarterly_payments() -> dict[int, dict[int, float]]:
    """Generation + export payments per levelisation quarter, £m, from FIT quarterly reports
    57–64: {FIT year: {quarter: £m}}. FIT year 15 = 2024-25 = SY15."""
    words = {"one": 1, "two": 2, "three": 3, "four": 4}
    out: dict[int, dict[int, float]] = defaultdict(dict)
    for n, p in FIT_QR.items():
        t = _pdf_text(p)
        m = re.search(r"A total of £([\d,.]+) FIT Export and Generation payments were made this quarter", t)
        q = re.search(r"levelisation process for quarter (\w+) of FIT Year (\d+) was completed", t)
        if not (m and q):
            raise ValueError(f"FIT quarterly report {n}: anchors not found")
        qn = words.get(q.group(1), None) or int(q.group(1))
        out[int(q.group(2))][qn] = _num(m.group(1)) / 1e6
    return dict(out)


def fit_fy_scheme_value() -> dict[int, tuple[float, str, str]]:
    """FIT by scheme year (start year), £m, on the scheme-value basis (the pre-s27 NZ3).
    SY16 (2025-26), whose annual report is not out, is the sum of the four quarterly levelisation
    payment totals: payments only, without the 'qualifying FIT costs' that the scheme value adds
    (SY15: scheme value £1,844m against quarterly payments summing to about £1,766m). The lower
    measure is taken (conservative rule)."""
    out = {y: (v, "measured", SRC_FIT) for y, v in read_fit_scheme_value().items()}
    q = read_fit_quarterly_payments()
    if sorted(q.get(16, {})) != [1, 2, 3, 4]:
        raise ValueError("FIT year 16: four quarters not all held")
    out[2025] = (sum(q[16].values()), "estimated", SRC_FIT_QR)
    return out


FIT_NOTICE = {fy: RAW / f"ofgem_ro_fit/FIT_levelisation_notice_{fy}-{str(fy + 1)[2:]}.pdf" for fy in range(2015, 2023)}
FIT_SY14 = RAW / "ofgem_ro_fit/FIT_annual_report_SY14.pdf"
SRC_FIT_LEV = "ofgem-fit-annual-levelisation-notices-2015-16-to-2022-23"
SRC_FIT_LEV_AR = "ofgem-fit-annual-reports-sy14-sy15-levelisation-fund"
SRC_FIT_LEV_QR = "ofgem-fit-quarterly-reports-61-64-levelisation-fund"
FIT_BASIS_OPTIONS = ("levelisation", "scheme_value")   # 'levelisation' = central (s27b)


@lru_cache(maxsize=None)
def read_fit_levelisation() -> dict[int, tuple[float, str, str]]:
    """The FIT levelisation fund, £m, by scheme year (start year): the cost of the scheme to
    licensed suppliers, which is what reaches bills (generation + deemed export + qualifying
    costs − value of export electricity to suppliers). Ofgem: "The levelisation fund is the total
    combined cost of the scheme to licensed electricity suppliers" (SY14 report).

    SY6–SY13 (2015-16 … 2022-23): "The total Levelisation Fund for the year was calculated at £…"
    (annual levelisation notices). SY14, SY15: "The levelisation fund (D) (A + B + C) £…" (annual
    reports). SY16 (2025-26): sum of "The levelisation fund totalled £…" in quarterly reports 61–64
    (estimated: quarterly, before annual reconciliation)."""
    out: dict[int, tuple[float, str, str]] = {}
    for fy, p in FIT_NOTICE.items():
        m = re.search(r"The total Levelisation Fund for the year was calculated at £([\d,]+\.\d+)", _pdf_text(p))
        if not m:
            raise ValueError(f"{p.name}: levelisation sentence moved")
        out[fy] = (_num(m.group(1)) / 1e6, "measured", SRC_FIT_LEV)
    for fy, p in ((2023, FIT_SY14), (2024, FIT_SY15)):
        m = re.search(r"The levelisation fund \(D\) \(A \+ B \+ C\) £([\d,]+)", _pdf_text(p))
        if not m:
            raise ValueError(f"{p.name}: levelisation fund row moved")
        out[fy] = (_num(m.group(1)) / 1e6, "measured", SRC_FIT_LEV_AR)
    q = {}
    for n in range(61, 65):
        t = _pdf_text(FIT_QR[n])
        m = re.search(r"The levelisation fund totalled £([\d,]+\.\d{2})", t)
        k = re.search(r"levelisation process for quarter (\d) of FIT Year 16", t)
        if not (m and k):
            raise ValueError(f"FIT quarterly report {n}: levelisation fund sentence moved")
        q[int(k.group(1))] = _num(m.group(1)) / 1e6
    if sorted(q) != [1, 2, 3, 4]:
        raise ValueError("FIT year 16: four levelisation quarters not all held")
    out[2025] = (sum(q.values()), "estimated", SRC_FIT_LEV_QR)
    return out


def fit_fy(basis: str = "levelisation") -> dict[int, tuple[float, str, str]]:
    """FIT by scheme year (start year), £m.

    basis 'levelisation' (central, s27b; spec §15.5 item 3 "FiT at the levelisation cost"): the
    levelisation fund (`read_fit_levelisation`) for SY6–SY16. SY1–SY5 (2010-11 … 2014-15) have no
    stored levelisation notice: scheme value × the SY6 ratio levelisation ÷ scheme value
    (estimated; disclosed fallback 'fit-sy1-5-levelisation-ratio'). 'scheme_value': the pre-s27 line."""
    if basis == "scheme_value":
        return fit_fy_scheme_value()
    if basis != "levelisation":
        raise ValueError(basis)
    sv = read_fit_scheme_value()
    lev = read_fit_levelisation()
    ratio = lev[2015][0] / sv[2015]
    out = {fy: (v * ratio, "estimated", f"{SRC_FIT}+{SRC_FIT_LEV}") for fy, v in sv.items() if fy < 2015}
    out.update(lev)
    return out


FIT_FALLBACKS = [{"name": "fit-sy1-5-levelisation-ratio", "years": "SY1-SY5 (FY2010/11-2014/15)",
                  "what": "levelisation fund not stored for SY1-SY5: scheme value x SY6 levelisation/scheme-value ratio"}]


def fit(years=YEARS, basis: str = "levelisation") -> dict[int, dict]:
    """NZ3 by calendar year, £m; zero before April 2010 (scheme start)."""
    fy = fit_fy(basis)
    cy = fy_to_cy({y: v[0] for y, v in fy.items()}, years)
    out = {}
    for y in years:
        parts = [fy[k] for k in (y - 1, y) if k in fy]
        if not parts:
            out[y] = _row(0.0, "measured", "fit-not-yet-started")
            continue
        basis = "estimated" if any(p[1] == "estimated" for p in parts) else "measured"
        out[y] = _row(cy[y], basis, "+".join(sorted({p[2] for p in parts})))
    return out


# ------------------------------------------------------------------ NZ4 CfD and CM_paid (LCCC)

@lru_cache(maxsize=None)
def cfd_monthly() -> dict[tuple[int, int], float]:
    """CfD payments by settlement month, £m (negative when generators paid back, kept)."""
    out: dict[tuple[int, int], float] = defaultdict(float)
    with CFD_CSV.open(newline="") as f:
        r = csv.DictReader(f)
        if "CFD_Payments_GBP" not in r.fieldnames or "Settlement_Date" not in r.fieldnames:
            raise ValueError("LCCC CfD file: columns moved")
        for row in r:
            d = datetime.strptime(row["Settlement_Date"][:10], "%Y-%m-%d")
            out[(d.year, d.month)] += float(row["CFD_Payments_GBP"] or 0) / 1e6
    return dict(out)


BIOMASS_TECH = ("Biomass Conversion", "Dedicated Biomass")
SRC_CFD_BIO = "lccc-actual-cfd-generation-biomass"
CFD_SPLIT_OPTIONS = ("biomass_split", "combined")   # 'biomass_split' = central (s27b)


@lru_cache(maxsize=None)
def cfd_monthly_by_group() -> dict[str, dict[tuple[int, int], float]]:
    """CfD payments by settlement month, £m, split into 'biomass' (LCCC Technology 'Biomass
    Conversion' (Drax unit) and 'Dedicated Biomass') and 'other' (wind, solar, energy from
    waste, advanced conversion)."""
    out: dict[str, dict[tuple[int, int], float]] = {"biomass": defaultdict(float), "other": defaultdict(float)}
    with CFD_CSV.open(newline="") as f:
        r = csv.DictReader(f)
        if "Technology" not in r.fieldnames:
            raise ValueError("LCCC CfD file: Technology column moved")
        seen = set()
        for row in r:
            d = datetime.strptime(row["Settlement_Date"][:10], "%Y-%m-%d")
            g = "biomass" if row["Technology"] in BIOMASS_TECH else "other"
            seen.add(row["Technology"])
            out[g][(d.year, d.month)] += float(row["CFD_Payments_GBP"] or 0) / 1e6
    if not set(BIOMASS_TECH) <= seen:
        raise ValueError(f"LCCC CfD file: biomass technologies not found in {sorted(seen)}")
    return {k: dict(v) for k, v in out.items()}


def cfd(years=YEARS, part: str = "all") -> dict[int, dict]:
    """NZ4 by calendar year, £m; zero before the first settlement (30 June 2016).

    part: 'all' (the whole CfD, pre-s27 NZ4), 'other' (NZ4 central from s27b: CfD without
    biomass) or 'biomass' (NZ4b: Biomass Conversion + Dedicated Biomass). other + biomass = all."""
    if part == "all":
        m = cfd_monthly()
        src = SRC_CFD
    elif part in ("other", "biomass"):
        m = cfd_monthly_by_group()[part]
        src = SRC_CFD if part == "other" else SRC_CFD_BIO
    else:
        raise ValueError(part)
    return {y: _row(sum(v for k, v in m.items() if k[0] == y), "measured",
                    src if any(k[0] == y for k in m) else "cfd-not-yet-started") for y in years}


@lru_cache(maxsize=None)
def cm_monthly() -> dict[tuple[int, int], float]:
    months = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                          "August", "September", "October", "November", "December"], 1)}
    out: dict[tuple[int, int], float] = defaultdict(float)
    with CM_CSV.open(newline="") as f:
        r = csv.DictReader(f)
        need = {"Calendar_Year", "Calendar_Month", "Capacity_Payment_GBP"}
        if not need <= set(r.fieldnames):
            raise ValueError("LCCC CM file: columns moved")
        for row in r:
            out[(int(row["Calendar_Year"]), months[row["Calendar_Month"]])] += float(row["Capacity_Payment_GBP"] or 0) / 1e6
    return dict(out)


def CM_paid(years=YEARS) -> dict[int, dict]:
    """Capacity Market payments to capacity providers by calendar year, £m (LCCC). Zero
    before October 2016. NZ5 = max(0, CM_paid − CM_gasonly) is computed by the parent."""
    m = cm_monthly()
    return {y: _row(sum(v for k, v in m.items() if k[0] == y), "measured",
                    SRC_CM if any(k[0] == y for k in m) else "cm-not-yet-started") for y in years}


# ------------------------------------------------------------------ NZ8 CCL, electricity

@lru_cache(maxsize=None)
def read_ccl_table_1b() -> dict[int, dict]:
    """HMRC Environmental Taxes Bulletin Table 1b (calendar year): electricity declarations,
    estimated CCL and CPF receipts, £m, with the 'provisional' flag."""
    rows = read_ods(HMRC_ENVTAX)["CCL_and_CPF_statistics_tables"]
    i = next(k for k, r in enumerate(rows) if r and str(r[0]).startswith("Table 1b."))
    h = rows[i]
    je = h.index("Electricity declarations (£ million)")
    jcpf = h.index("Estimated CPF receipts (£ million)")
    out = {}
    for r in rows[i + 1:]:
        if not r or str(r[0]).startswith("Table 1c"):
            break
        y = int(str(r[0])[:4])
        cpf = r[jcpf] if isinstance(r[jcpf], float) else None
        out[y] = {"electricity": r[je], "cpf_receipts": cpf, "provisional": "provisional" in str(r[0])}
    return out


# Finance (No. 2) Act 2015 s.49 (https://www.legislation.gov.uk/ukpga/2015/33/section/49/enacted)
# inserted into FA 2000 Sch 6 para 19(3) "(za) it is generated before 1 August 2015": renewable
# electricity generated from 1 August 2015 pays the levy. The engine counts the whole levy every
# year (it measures net zero's total cost); the Subsidy Clock counts it only to 31 July 2015
# (Richard, 14 Oct 2026, decision D2). bridge.py row M shows the difference.
LEC_EXEMPTION_END = (2015, 7)          # last month renewable electricity was exempt
SRC_FA2015_S49 = "legislation-fa2-2015-s49-ccl-renewables-exemption-removed"


@lru_cache(maxsize=None)
def read_ccl_table_1c_electricity() -> dict[tuple[int, int], float]:
    """HMRC Environmental Taxes Bulletin Table 1c (by month): electricity declarations, £m,
    {(year, month): £m}. Declarations are booked by return period, so the series is lumpy
    (quarter-end months carry most of each quarter)."""
    import calendar
    rows = read_ods(HMRC_ENVTAX)["CCL_and_CPF_statistics_tables"]
    i = next(k for k, r in enumerate(rows) if r and str(r[0]).startswith("Table 1c."))
    je = rows[i].index("Electricity declarations (£ million)")
    months = {calendar.month_name[m]: m for m in range(1, 13)}
    out = {}
    for r in rows[i + 1:]:
        if not r or not str(r[0]).strip():
            continue
        parts = str(r[0]).split()
        if len(parts) < 2 or parts[0] not in months or not parts[1][:4].isdigit():
            continue
        if isinstance(r[je], (int, float)):
            out[(int(parts[1][:4]), months[parts[0]])] = float(r[je])
    return out


def ccl_electricity_exempt_period(years=YEARS) -> dict[int, float]:
    """CCL electricity declarations in the months renewable electricity was exempt (to 31 July
    2015), £m UK, by calendar year: the whole Table 1b year before 2015; 2015 = 7/12 of the Table 1b
    year (decision D2's stated fallback); 0 after 2015.

    Why 7/12 and not the monthly table: HMRC publishes no monthly electricity RECEIPTS (receipts
    carry no commodity split; the bulletin says separate CCL/CPF receipts are only estimated).
    Table 1c gives monthly electricity DECLARATIONS, but they are booked by accounting-period end
    (mostly quarterly: Mar/Jun/Sep/Dec carry 95%+), so July 2015 cannot be read from it. For the
    record, Table 1c Jan-Jul 2015 = £144.2m, and Jan-Jun plus a third of the Jul-Sep quarter = about
    £168m, against 7/12 = £189.1m: pro rata counts about £21m more for the exempt months than the
    quarterly reading does (`ccl_2015_monthly_readings`)."""
    t = read_ccl_table_1b()
    ey, em = LEC_EXEMPTION_END
    out = {}
    for y in years:
        if y < ey:
            out[y] = t[y]["electricity"]
        elif y == ey:
            out[y] = t[y]["electricity"] * em / 12
        else:
            out[y] = 0.0
    return out


def ccl_2015_monthly_readings() -> dict[str, float]:
    """The alternative 2015 splits from HMRC Table 1c (declarations by month), £m, for disclosure."""
    m = read_ccl_table_1c_electricity()
    jan_jun = sum(m[(2015, k)] for k in range(1, 7))
    q3 = sum(m[(2015, k)] for k in (7, 8, 9))
    return {"table_1b_2015": read_ccl_table_1b()[2015]["electricity"],
            "pro_rata_7_12": read_ccl_table_1b()[2015]["electricity"] * 7 / 12,
            "table_1c_jan_jul": jan_jun + m[(2015, 7)],
            "table_1c_jan_jun_plus_third_of_q3": jan_jun + q3 / 3}


def ccl_electricity(years=YEARS) -> dict[int, dict]:
    """NZ8: CCL electricity declarations by calendar year, £m (UK). CPS is not here (it is in
    NZ1c). The 2025 row is HMRC-provisional and tagged estimated."""
    t = read_ccl_table_1b()
    return {y: _row(t[y]["electricity"], "estimated" if t[y]["provisional"] else "measured", SRC_CCL)
            for y in years}
