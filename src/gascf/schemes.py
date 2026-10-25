"""Energy-saving obligations on electricity bills (spec §15.4 item 1): EEC, CERT, CESP, ECO, GBIS.

Richard's decision (11 Oct 2026, binding): the energy-saving obligations that suppliers recover
through bills are net-zero policy. Their electricity share goes on the net-zero bill as its own
line, group ``schemes``; fossil Britain pays nothing for them. The Warm Home Discount is social
policy and is NOT here (it stays in both bills, i.e. outside the gap).

National cost recovered on electricity, £m per calendar year, money of the day, 2002-2025.
Every figure is read from a stored source (``data/raw/s24/`` and ``data/raw/ofgem/``). Where only
a range exists the LOWER figure is used (conservative: it shrinks the net-zero bill) and the
range is carried in ``low`` / ``high``.

Periods and sources
-------------------
- **EEC1, Apr 2002-Mar 2005.** Defra Explanatory Memorandum to SI 2004/3392 (EEC Order 2004),
  para 29: "no more than about £4 per customer per fuel each year" (2004 prices). Lower figure:
  Ofgem DCMR 2004, Figure 4.2, "Energy Efficiency Commitment, 1%" of the 2003 direct-debit
  electricity bill (QEP 2.2.1, 3,300 kWh, incl. VAT). Central = DCMR (lower).
- **EEC2, Apr 2005-Mar 2008.** Same EM para 29: the extension "is likely to result in a potential
  additional cost of £5 per customer per fuel ... an increase on average of not more than about
  £9 (in 2004 prices) per customer per fuel per annum ... compared to prices before the start of
  the EEC in 2002". Range £5 (the extension's own addition) to £9 (the whole); central £5.
  Per-customer figures × UK households (the project's single denominator, as in
  ``same_in_both``: one electricity customer per household); 2004 prices to money of the day
  with CPIH (the EM names no index).
- **CERT, Apr 2008-Dec 2012 (57 months).** DECC/Ipsos-CAR-CSE evaluation of CERT and CESP (Dec
  2014), §8.1: delivery costs "£3.4bn ... (in nominal terms)" reported by all six obligated
  parties, plus administration "£107m across all suppliers in nominal terms" (§8.1.1). Spread
  evenly over the 57 months.
- **CESP, Oct 2009-Dec 2012 (39 months).** Same evaluation, Table 9.1: total £702.1m nominal
  (£665m delivery + £37.1m administration). Spread evenly over the 39 months.
- **Electricity share of CERT and CESP.** Both obligations were set per supplier licence on
  domestic customer numbers for gas and for electricity (Ofgem EEC 2002-05 review para 3.4:
  "Each supplier is set a separate gas and electricity target, according to the number of
  consumers on each licence"). Range: 50% (Ofgem's own price-cap rule for ECO: "Calculate by
  dividing annualised estimate of supplier impact of scheme in half", Annex 4 tab '3e ECO')
  to 55.6% (equal cost per customer per fuel and the EM's "£9 per customer per fuel ... about
  £16 p.a. per household": 9/16.2 of each household's cost on electricity). Central 50%.
- **ECO1/ECO2, Jan 2013-Mar 2015.** Range: lower = the 2015/16 electricity attribution in the cap
  (Annex 4 tab '3e ECO' row 14, £393.5m a year) carried back; higher = Ofgem SMI (Apr 2015)
  'Electricity data' G26 "Electricity Energy Companies Obligation (ECO)" £20.10 per customer for
  2014 × households. Central = lower.
- **ECO3/ECO4 and GBIS, Apr 2015-Dec 2025.** Ofgem price-cap Annex 4 v1.25, tab '3e ECO': row 14
  (ECO) and row 16 (GBIS) "Annualised costs for scheme year attributed to electricity", uprated
  to the year's money by rows 17/18 (OBR GDP deflator, %), each cap period's annual £ applied to
  the months it covers. National, all obligated suppliers' electricity supply (GB).

Not double counted: the cap's policy-cost line (PC) is not read anywhere in the bills; the
same-in-both supplier block uses the cap's OC/PAAC/PAP/HAP/CO/DRC/IC/EBIT/SMNCC only, SMI rows
37+45 (operating costs, margin; ECO is row 26, a separate block), and DCMR's "Supply costs and
margin, 26%" (EEC is its own 1% slice). ``subsidies.py`` holds RO, FiT, CfD, CM and CCL only.
"""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import openpyxl

from gascf import deflator_cpih as dfl
from gascf import households as hh
from gascf import same_in_both

ROOT = Path(__file__).parents[2]
RAW = ROOT / "data/raw"
S24 = RAW / "s24"
EM_EEC = S24 / "s24-EM_EEC_2004_3392.txt"
EEC_REVIEW = S24 / "s24-Ofgem_EEC_2002-05_review.txt"
EVAL = S24 / "s24-DECC_CERT_CESP_evaluation_2014.txt"
CERT_FINAL = S24 / "s24-Ofgem_CERT_final_report_2013.txt"
CESP_FINAL = S24 / "s24-Ofgem_CESP_final_report_2013.txt"
ANNEX4 = RAW / "ofgem/Annex-4-policy-cost-allowance-methodology-v1.25.xlsx"

YEARS = range(2002, 2026)
SRC = {"em_eec": "s24-defra-em-eec-2004", "eec_review": "s24-ofgem-eec-2002-05-review",
       "dcmr": "ofgem-dcmr-2004", "qep221": "desnz-qep-2.2.1", "eval": "s24-decc-cert-cesp-evaluation-2014",
       "cert": "s24-ofgem-cert-final-2013", "cesp": "s24-ofgem-cesp-final-2013",
       "a4": "ofgem-annex4-v1.25", "smi": "ofgem-smi-2015", "cpih": dfl.SOURCE_CPIH, "hh": hh.SOURCE_ID}

ELEC_SHARE_LOW = 0.5                 # cap rule: "dividing ... in half"
ELEC_SHARE_HIGH = 9 / 16.2           # EM: £9 per customer per fuel ≈ £16 per household (16.2 = 9×1.8)


def _text(p: Path) -> str:
    return re.sub(r"\s+", " ", p.read_text())


def _need(p: Path, quote: str) -> None:
    if quote not in _text(p):
        raise ValueError(f"{p.name}: quote missing: {quote[:70]}…")


# ----------------------------------------------------------------------------- readers

@lru_cache(maxsize=1)
def eec_per_customer() -> dict:
    """EEC1 and EEC2 £ per customer per fuel per year (2004 prices) from the EM, and the DCMR
    1% share for EEC1 (cash, 2003)."""
    _need(EM_EEC, "the average energy bill would increase by no more than about £4 per customer per fuel each year of the programme")
    _need(EM_EEC, "likely to result in a potential additional cost of £5 per customer per fuel")
    _need(EM_EEC, "not more than about £9 (in 2004 prices) per customer per fuel per annum (or about £16 p.a. per household)")
    _need(EEC_REVIEW, "Each supplier is set a separate gas and electricity target, according to the number of consumers on each licence")
    t = _text(same_in_both.DCMR)
    i = t.find("Figure 4.2: Breakdown of domestic direct debit electricity bill")
    if i < 0 or "Energy Efficiency Commitment, 1%" not in t[i:i + 800]:
        raise ValueError("DCMR 2004 Figure 4.2: 'Energy Efficiency Commitment, 1%' not found")
    dd2003 = same_in_both.qep_elec_bill_3300()[2003]["dd"]
    return {"eec1_high_2004p": 4.0, "eec2_low_2004p": 5.0, "eec2_high_2004p": 9.0,
            "eec1_dcmr_cash_2003": 0.01 * dd2003, "dd2003": dd2003}


@lru_cache(maxsize=1)
def cert_cesp_totals() -> dict:
    """Nominal totals, £m: CERT delivery + administration; CESP total (DECC evaluation 2014)."""
    _need(EVAL, "Total delivery costs of £3.4bn were reported across the submissions (in nominal terms)")
    _need(EVAL, "these costs totalled £107m across all suppliers in nominal terms")
    t = EVAL.read_text()
    m = re.search(r"Total delivery costs\s+£([\d.,]+)m", t)
    if not m or m.group(1) != "702.1":
        raise ValueError("evaluation Table 9.1 'Total delivery costs £702.1m' moved")
    _need(CERT_FINAL, "obligation period started on 1 April 2008 and finished on 31 December 2012")
    _need(CESP_FINAL, "The CESP obligation period ran from 1 October 2009 to 31 December 2012")
    return {"cert_gbp_m": 3400.0 + 107.0, "cert_months": ((2008, 4), (2012, 12)),
            "cesp_gbp_m": 702.1, "cesp_months": ((2009, 10), (2012, 12))}


def _period(label: str) -> tuple[date, date] | None:
    """'April 2015 – September 2015' → (2015-04-01, 2015-10-01)."""
    mo = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"), 1)}
    p = re.findall(r"([A-Za-z]+)\s*(\d{4})", label or "")
    if len(p) != 2:
        return None
    (m0, y0), (m1, y1) = p
    s = date(int(y0), mo[m0.lower()], 1)
    em, ey = mo[m1.lower()] + 1, int(y1)
    if em == 13:
        em, ey = 1, ey + 1
    return s, date(ey, em, 1)


@lru_cache(maxsize=1)
def annex4_eco() -> list[tuple[date, date, float, float]]:
    """Cap periods with the annual electricity cost of ECO and GBIS, £m in the period's money
    (rows 14/16 × (1 + rows 17/18 %)). Header: row 9 (quarterly labels from Oct 2022)."""
    ws = openpyxl.load_workbook(ANNEX4, read_only=True, data_only=True)["3e ECO"]
    rows = list(ws.iter_rows(min_row=1, max_row=30, values_only=True))
    lab = {13: "Annualised costs for scheme year attributed to electricity - ECO4",
           15: "Annualised costs for scheme year attributed to electricity -  Great British Insulation Scheme",
           16: "Uprate to current year prices using GDP deflator", 17: "Uprate to current year prices using GDP deflator"}
    for i, txt in lab.items():
        if not str(rows[i][1] or "").startswith(txt):
            raise ValueError(f"Annex 4 '3e ECO' row {i + 1}: expected {txt!r}, got {rows[i][1]!r}")
    if "2021 prices" not in str(rows[16][2]) or "2022 prices" not in str(rows[17][2]):
        raise ValueError("Annex 4 '3e ECO' uprating notes moved")
    out = []
    for j in range(5, len(rows[8])):
        per = _period(str(rows[8][j] or ""))
        eco = rows[13][j]
        if per is None or not isinstance(eco, (int, float)):
            continue
        u_eco = rows[16][j] if isinstance(rows[16][j], (int, float)) else 0.0
        gbis = rows[15][j] if isinstance(rows[15][j], (int, float)) else 0.0
        u_g = rows[17][j] if isinstance(rows[17][j], (int, float)) else 0.0
        out.append((per[0], per[1], eco * (1 + u_eco / 100) / 1e6, gbis * (1 + u_g / 100) / 1e6))
    if not out or out[0][0] != date(2015, 4, 1) or out[-1][1] < date(2026, 1, 1):
        raise ValueError("Annex 4 '3e ECO': periods should run Apr 2015 to at least Dec 2025")
    return out


@lru_cache(maxsize=1)
def smi_eco_2014() -> float:
    """Ofgem SMI (Apr 2015) 'Electricity data' G26: ECO £ per customer, Jan-Dec 2014."""
    e = openpyxl.load_workbook(same_in_both.SMI, data_only=True)["Electricity data"]
    if "Electricity Energy Companies Obligation" not in str(e["A26"].value):
        raise ValueError(f"SMI A26 moved: {e['A26'].value!r}")
    return float(e["G26"].value)


# ----------------------------------------------------------------------------- the series

def _months(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
    out, (y, m) = [], a
    while (y, m) <= b:
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


@lru_cache(maxsize=1)
def monthly() -> dict[tuple[int, int], dict[str, dict[str, float]]]:
    """{(y, m): {scheme: {"central", "low", "high"}}}, £m nominal per month, electricity share."""
    k = hh.read_households()
    e = eec_per_customer()
    cc = cert_cesp_totals()
    out: dict[tuple[int, int], dict] = {}

    def add(key, scheme, c, lo, hi):
        out.setdefault(key, {})[scheme] = {"central": c, "low": lo, "high": hi}

    # EEC: per customer per year × households / 12; 2004 prices → nominal by CPIH
    for (y, m) in _months((2002, 4), (2008, 3)):
        n = k[y] * 1000
        if (y, m) <= (2005, 3):
            lo = dfl.to_real(e["eec1_dcmr_cash_2003"], 2003, y)       # 2003 cash → year y money
            hi = dfl.to_real(e["eec1_high_2004p"], 2004, y)
            add((y, m), "EEC", lo * n / 1e6 / 12, min(lo, hi) * n / 1e6 / 12, max(lo, hi) * n / 1e6 / 12)
        else:
            lo = dfl.to_real(e["eec2_low_2004p"], 2004, y)
            hi = dfl.to_real(e["eec2_high_2004p"], 2004, y)
            add((y, m), "EEC", lo * n / 1e6 / 12, lo * n / 1e6 / 12, hi * n / 1e6 / 12)
    for scheme, tot, span in (("CERT", cc["cert_gbp_m"], cc["cert_months"]),
                              ("CESP", cc["cesp_gbp_m"], cc["cesp_months"])):
        ms = _months(*span)
        per = tot / len(ms)
        for key in ms:
            add(key, scheme, per * ELEC_SHARE_LOW, per * ELEC_SHARE_LOW, per * ELEC_SHARE_HIGH)
    a4 = annex4_eco()
    eco_first = a4[0][2]
    smi = smi_eco_2014()
    for (y, m) in _months((2013, 1), (2015, 3)):
        lo = eco_first / 12
        hi = smi * k[2014 if y >= 2014 else y] * 1000 / 1e6 / 12 if y >= 2014 else lo
        add((y, m), "ECO", lo, min(lo, hi), max(lo, hi))
    for (y, m) in _months((2015, 4), (2025, 12)):
        d = date(y, m, 1)
        hit = next(((s, e2, eco, g) for s, e2, eco, g in a4 if s <= d < e2), None)
        if hit is None:
            raise KeyError(f"Annex 4 has no period covering {d}")
        add((y, m), "ECO", hit[2] / 12, hit[2] / 12, hit[2] / 12)
        if hit[3]:
            add((y, m), "GBIS", hit[3] / 12, hit[3] / 12, hit[3] / 12)
    return out


BASIS = {"EEC": "estimated", "CERT": "estimated", "CESP": "estimated", "ECO": "estimated", "GBIS": "estimated"}


@lru_cache(maxsize=1)
def schemes(years=YEARS) -> dict[int, dict]:
    """{year: {"gbp_m" (central, lower of each range), "low", "high", "by_scheme": {...},
    "basis", "source_id", "note"}} — electricity share, £m nominal, calendar year, from the shared cost register
    (0168; series ENERGY_SAVING and its memo rows ENERGY_SAVING_<scheme>, built by `src_schemes`)."""
    from gascf import register_pin as RP
    reg = RP.register()
    memo = sorted((r for r in reg.rows if r["row_type"] == "memo" and r["line_id"].startswith("ENERGY_SAVING_")),
                  key=lambda r: (int(r["year"]), int(r["note"].split()[-1])))
    out = {}
    for y in years:
        r = reg.row("ENERGY_SAVING", y)
        by = {m["line_id"].removeprefix("ENERGY_SAVING_"): {"central": float(m["cash_gbp_m"]),
                                                           "low": float(m["low_gbp_m"]),
                                                           "high": float(m["high_gbp_m"])}
              for m in memo if int(m["year"]) == y}
        out[y] = {"gbp_m": float(r["cash_gbp_m"]), "low": float(r["low_gbp_m"]), "high": float(r["high_gbp_m"]),
                  "by_scheme": by, "basis": r["basis"], "source_id": r["source_id"], "note": r["note"]}
    return out


@lru_cache(maxsize=1)
def src_schemes(years=YEARS) -> dict[int, dict]:
    """The engine's reading of its stored scheme files: the register's builder only (0168).
    {year: {"gbp_m" (central, lower of each range), "low", "high", "by_scheme": {...},
    "basis", "source_id", "note"}} — electricity share, £m nominal, calendar year."""
    mo = monthly()
    out = {}
    for y in years:
        by: dict[str, dict[str, float]] = {}
        for m in range(1, 13):
            for sch, v in mo.get((y, m), {}).items():
                d = by.setdefault(sch, {"central": 0.0, "low": 0.0, "high": 0.0})
                for kk in d:
                    d[kk] += v[kk]
        src = sorted({SRC[s] for s in _sources_for(by)} | {SRC["hh"]} if by else {"none"})
        out[y] = {"gbp_m": sum(v["central"] for v in by.values()),
                  "low": sum(v["low"] for v in by.values()),
                  "high": sum(v["high"] for v in by.values()),
                  "by_scheme": by,
                  "basis": "estimated" if by else "measured",
                  "source_id": ";".join(src),
                  "note": ", ".join(f"{s} {v['central']:.0f}" for s, v in by.items())
                          + ("; lower of each range (conservative)" if by else "")}
    return out


def _sources_for(by: dict) -> set[str]:
    s: set[str] = set()
    if "EEC" in by:
        s |= {"em_eec", "eec_review", "dcmr", "qep221", "cpih"}
    if "CERT" in by:
        s |= {"eval", "cert", "a4", "em_eec"}
    if "CESP" in by:
        s |= {"eval", "cesp", "a4", "em_eec"}
    if "ECO" in by or "GBIS" in by:
        s |= {"a4", "smi"}
    return s
