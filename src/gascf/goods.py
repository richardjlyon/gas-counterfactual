"""Layer 3: renewables subsidy costs carried on business electricity, passed through to households.

Spec §6 Layer 3. Shown beside the headline, never inside it.

What this module computes, per financial year (1 April to 31 March, the scheme year of the
Renewables Obligation and Feed-in Tariffs; the Contracts for Difference levy is summed over the
same months from daily data):

* CfD (Contracts for Difference) supplier-obligation cost, from LCCC's reconciled daily levy
  rates (rate x eligible demand, latest settlement run).                      basis: measured
* RO (Renewables Obligation) cost in Great Britain = GB obligation in ROCs (Renewables
  Obligation Certificates) x buy-out price.                                   basis: modelled
* FiT (Feed-in Tariff) cost = Ofgem's total Levelisation Fund for the year.   basis: measured

Each scheme's cost is levied on a "chargeable" volume (supply minus exempt volumes). The
exempt volumes are energy-intensive industry (EII) exclusions and, for CfD and FiT in earlier
years, green-import exemptions; all exempt volume is treated as non-domestic. Households pay
the scheme's £/MWh on their own consumption:

    domestic £  = cost x d x gross / chargeable
    business £  = cost - domestic £

where gross = chargeable + exempt volumes, and d = domestic share of UK electricity sales
(DUKES 2026 Table 5.2 "Domestic" public-distribution row / Table 5.5.D "UK electricity
sales"), calendar years weighted 9/12 and 3/12 into the financial year. Business £ is
therefore net of EII exemptions by construction. The domestic/business split is `modelled`.
The domestic share is the engine's one definition, ``system_costs.domestic_share_cy`` (this
module used to carry its own copy; review S3).

Pass-through of the business cost into the prices of goods and services: 50% central, 33-80%
range. Each row carries two tags: ``business_basis`` (the business £ before pass-through,
`modelled`) and ``basis`` = ``passed_through_basis`` (the per-household passed-through £,
always `estimated`, review S4) (Richard, 10 Oct 2026: be conservative; evidence in
work/s8-passthrough-research/findings.md). No UK estimate to *consumer* prices exists; 0.50 is
the UK sector blend (Bank Underground 2023, "long-run coefficients ranging from 0.4 (for
services industries) to 0.8 (for most manufacturing industries)", weighted by DUKES 2026 Table
5.2 industry share 40.6% = 0.53), rounded down. Range: 0.33 (Hintermann et al. 2020, Germany,
cost borne by some firms only) to 0.80 (UK long-run manufacturing).

Exports: only the part of business output sold in the UK can reach UK households. CCC (2017),
Energy Prices and Bills: "Around 30% of UK output (by GDP) is exported and does not affect UK
consumer prices at all", so 70% is kept. This is generous to the renewables side's critics only
in one direction: government and investment spending also absorb some output, so the true
household share is lower still (ONS input-output share not yet sourced; GAP).

Per GB household: the engine's one household count, ``taxes.gb_households_fy`` (ONS LFS for
England, Wales and Scotland, households.py; defined in system_costs, re-exported by taxes), financial
years weighted 9/12 + 3/12. Review S3: this module used to use ONS LFS for all three nations.

CfD outturn for a cap period (``cfd_outturn``): LCCC reconciled daily levy rate, latest run,
weighted by eligible demand over the period's days. The receipt carries it beside Ofgem's
ex-ante CfD allowance (review B2). Days whose latest run is not final (RF or DF) are counted and
reported, because those figures will still move (review N5).

Every number is read from a stored file under data/raw/; readers check anchor text and raise
if a layout moves.
"""
from __future__ import annotations

import csv
import html
import json
import re
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import openpyxl

from .system_costs import domestic_share_cy, fy_weight  # noqa: F401  (one definition, review S3)
from .taxes import gb_households_fy

RAW = Path(__file__).parents[2] / "data/raw"
LCCC = RAW / "lccc"
OFG = RAW / "ofgem_ro_fit"
DUKES = RAW / "dukes"

PASS_THROUGH = {"low": 0.33, "central": 0.5, "high": 0.8}
UK_SOLD_SHARE = 0.70               # CCC 2017: ~30% of UK output exported
UK_SOLD_SOURCE = "data/raw/papers/CCC_2017_Energy_Prices_and_Bills.pdf"
UK_SOLD_QUOTE = "Around 30% of UK output (by GDP) is exported and does not affect UK consumer prices at all"
PASS_THROUGH_LABEL = "UK sector blend (Bank Underground 2023 x DUKES 2026 5.2), rounded down; exports removed (CCC 2017)"
PASS_THROUGH_SOURCE = "data/raw/papers/BankUnderground_2023_energy_food_costs_supply_chain.html"
PASS_THROUGH_QUOTE = "long-run coefficients ranging from 0.4 (for services industries) to 0.8 (for most manufacturing industries)"

UNSOURCED = "UNSOURCED"


def fy_label(start: int) -> str:
    """2024 -> '2024-25'."""
    return f"{start}-{str(start + 1)[2:]}"


def _num(s: str) -> float:
    return float(s.replace(",", "").replace(" ", ""))


# --------------------------------------------------------------------------------------------
# Fetchers (not run by tests; the stored files are the record)
# --------------------------------------------------------------------------------------------
LCCC_RESOURCES = {
    "actual_ilr_income.csv": "547e29c4-aeb0-4ded-9a26-4337bc16a1a3",
    "reconciled_daily_levy_rates.csv": "24944bfe-b546-4f50-8bf6-895d8f769b2b",
}


def fetch_lccc(out: Path = LCCC) -> None:
    """Download the LCCC datasets through the CKAN datastore API (file links return 403)."""
    api = "https://dp.lowcarboncontracts.uk/api/3/action/datastore_search"
    out.mkdir(parents=True, exist_ok=True)
    for name, rid in LCCC_RESOURCES.items():
        rows, offset, total, fields = [], 0, None, None
        while total is None or offset < total:
            req = urllib.request.Request(f"{api}?resource_id={rid}&limit=32000&offset={offset}",
                                         headers={"User-Agent": "Mozilla/5.0"})
            res = json.load(urllib.request.urlopen(req, timeout=120))["result"]
            total = res["total"]
            fields = [f["id"] for f in res["fields"] if f["id"] != "_id"]
            rows += [[r[f] for f in fields] for r in res["records"]]
            offset += 32000
        rows.sort(key=lambda r: tuple("" if v is None else str(v) for v in r))
        with open(out / name, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(fields)
            w.writerows(rows)


# --------------------------------------------------------------------------------------------
# CfD: LCCC
# --------------------------------------------------------------------------------------------
# BSC settlement run codes: II interim information, SF initial, R1-R3 reconciliation, RF final
# reconciliation, DF dispute final (after RF). RF and DF are final; the others will move.
FINAL_RUNS = frozenset({"RF", "DF"})
RDLR_COLS = ["Settlement_Date", "Settlement_Run_Type", "Reconciled_Daily_Levy_Rate_GBP_Per_MWh",
             "Reconciled_Eligible_Demand_MWh", "Reconciled_Energy_Intensive_Industries_Demand_MWh",
             "Reconciled_Green_Excluded_Electricity_MWh", "Latest_Flag"]


@dataclass(frozen=True)
class SchemeYear:
    """One scheme's cost and volumes for one financial year."""
    scheme: str
    fy: int                 # first calendar year of the financial year
    cost_gbp: float
    chargeable_mwh: float   # volume the cost is levied on
    exempt_mwh: float       # EII (and green-import) volume excluded; all non-domestic
    basis: str
    source_id: str
    note: str = ""
    run_days: tuple[tuple[str, int], ...] = ()   # CfD: (settlement run type, days), latest run

    @property
    def gross_mwh(self) -> float:
        return self.chargeable_mwh + self.exempt_mwh


def _fy_of(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def read_cfd(path: Path = LCCC / "reconciled_daily_levy_rates.csv") -> dict[int, SchemeYear]:
    """Financial-year CfD cost from the latest settlement run of each day.

    Cost = sum over days of reconciled levy rate (£/MWh) x reconciled eligible demand (MWh).
    Eligible demand already excludes EII and green-excluded electricity.
    Only complete financial years are returned.
    """
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != RDLR_COLS:
            raise ValueError(f"LCCC reconciled levy layout moved: {rd.fieldnames}")
        rows = [r for r in rd if r["Latest_Flag"] == "Latest Settlement Run"]
    seen: set[date] = set()
    acc: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    runs: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        d = date.fromisoformat(r["Settlement_Date"][:10])
        if d in seen:
            raise ValueError(f"two latest runs for {d}")
        seen.add(d)
        if r["Reconciled_Daily_Levy_Rate_GBP_Per_MWh"] == "":
            continue                       # day not yet priced: its year is incomplete
        f = lambda k: float(r[k] or 0)
        a = acc[_fy_of(d)]
        a[0] += f("Reconciled_Daily_Levy_Rate_GBP_Per_MWh") * f("Reconciled_Eligible_Demand_MWh")
        a[1] += f("Reconciled_Eligible_Demand_MWh")
        a[2] += (f("Reconciled_Energy_Intensive_Industries_Demand_MWh")
                 + f("Reconciled_Green_Excluded_Electricity_MWh"))
        a[3] += 1
        runs[_fy_of(d)][r["Settlement_Run_Type"]] += 1
    out = {}
    for fy, (cost, elig, exempt, n) in acc.items():
        days = (date(fy + 1, 4, 1) - date(fy, 4, 1)).days
        if n != days:
            continue
        mix = tuple(sorted(runs[fy].items()))
        note = "reconciled daily levy rate x eligible demand, latest run"
        interim = sum(v for k, v in mix if k not in FINAL_RUNS)
        if interim:
            note += (f"; {interim} of {n} days from interim runs, not final (RF/DF), so the figure "
                     f"will move: {', '.join(f'{k} {v}' for k, v in mix)}")
        out[fy] = SchemeYear("CfD", fy, cost, elig, exempt, "measured", "LCCC-RDLR", note, mix)
    return out


@lru_cache(maxsize=1)
def _rdlr_days(path: Path = LCCC / "reconciled_daily_levy_rates.csv") -> dict[date, tuple[float, float, str]]:
    """{settlement date: (levy £/MWh, eligible demand MWh, run type)}, latest run, priced days."""
    out = {}
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != RDLR_COLS:
            raise ValueError(f"LCCC reconciled levy layout moved: {rd.fieldnames}")
        for r in rd:
            if r["Latest_Flag"] != "Latest Settlement Run" or r["Reconciled_Daily_Levy_Rate_GBP_Per_MWh"] == "":
                continue
            out[date.fromisoformat(r["Settlement_Date"][:10])] = (
                float(r["Reconciled_Daily_Levy_Rate_GBP_Per_MWh"]),
                float(r["Reconciled_Eligible_Demand_MWh"] or 0), r["Settlement_Run_Type"])
    return out


def cfd_outturn(start: date, end: date) -> dict | None:
    """CfD outturn for the days start..end inclusive: LCCC reconciled levy, latest run,
    £/MWh of eligible demand (demand-weighted mean). None unless every day is priced.

    Returns {"gbp_mwh", "days", "run_days": {run: days}, "final": all days RF, "basis", "note"}.
    Basis `measured` when every day is a final run (RF or DF), else `estimated` (interim runs move).
    """
    days = _rdlr_days()
    span = [start + timedelta(i) for i in range((end - start).days + 1)]
    if not span or any(d not in days for d in span):
        return None
    cost = sum(days[d][0] * days[d][1] for d in span)
    dem = sum(days[d][1] for d in span)
    mix: dict[str, int] = defaultdict(int)
    for d in span:
        mix[days[d][2]] += 1
    final = set(mix) <= FINAL_RUNS
    note = "LCCC reconciled daily levy x eligible demand / eligible demand, latest run"
    if not final:
        note += "; includes interim runs (" + ", ".join(f"{k} {v}" for k, v in sorted(mix.items())) + "), will move"
    return {"gbp_mwh": cost / dem, "days": len(span), "run_days": dict(mix), "final": final,
            "basis": "measured" if final else "estimated", "source_id": "LCCC-RDLR", "note": note}


def read_ilr(path: Path = LCCC / "actual_ilr_income.csv") -> dict[int, float]:
    """Interim levy income invoiced (£), by complete financial year — a cross-check only."""
    acc: dict[int, list[float]] = defaultdict(lambda: [0.0, 0])
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        if "Actual_Income_GBP" not in (rd.fieldnames or []):
            raise ValueError("LCCC ILR layout moved")
        for r in rd:
            d = date.fromisoformat(r["Settlement_Date"][:10])
            a = acc[_fy_of(d)]
            a[0] += float(r["Actual_Income_GBP"])
            a[1] += 1
    return {fy: v for fy, (v, n) in acc.items()
            if n == (date(fy + 1, 4, 1) - date(fy, 4, 1)).days}


# --------------------------------------------------------------------------------------------
# RO: Ofgem annual reports + buy-out price table
# --------------------------------------------------------------------------------------------
RO_REPORTS = {
    2015: "RO_annual_report_2015-16.pdf", 2016: "RO_annual_report_2016-17.pdf",
    2017: "RO_annual_report_2017-18.pdf", 2018: "RO_annual_report_2018-19.pdf",
    2019: "RO_annual_report_2019-20.pdf", 2020: "RO_annual_report_2020-21.pdf",
    2021: "RO_annual_report_SY20.pdf", 2022: "RO_annual_report_SY21.pdf",
    2023: "RO_annual_report_SY22.pdf", 2024: "RO_annual_report_SY23.pdf",
}


def _pdf_text(p: Path) -> str:
    import pymupdf
    return re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in pymupdf.open(p)))


def _html_text(p: Path) -> str:
    b = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", p.read_text())
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))).replace("\xa0", " ")


def read_ro_buyout() -> dict[int, float]:
    """Buy-out price £/ROC by obligation year: Ofgem RO suppliers page (to 2023-24) and the
    2024-25 total-obligation notice."""
    t = _html_text(OFG / "RO_suppliers_page.html")
    if "Buy-out price (per ROC)" not in t:
        raise ValueError("Ofgem RO suppliers page: buy-out table anchor missing")
    out = {int(a): float(p) for a, p in re.findall(r"(20\d\d)-20\d\d £([\d.]+) 0\.\d{3} 0\.\d{3}", t)}
    t = _html_text(OFG / "RO_total_obligation_2024-25.html")
    m = re.search(r"buy-out payment of £([\d.]+) per ROC", t)
    if not m or "1 April 2024 to 31 March 2025" not in t:
        raise ValueError("Ofgem RO 2024-25 notice: buy-out anchor missing")
    out[2024] = float(m.group(1))
    return out


def read_ro_report(fy: int) -> dict[str, float]:
    """Supply (MWh), obligation (ROCs) by country, and GB EII-excluded MWh, from the summary
    table of ROCs presented ("RO ROS NIRO UK total") and Table 4.1 (EII, from 2018-19)."""
    t = _pdf_text(OFG / RO_REPORTS[fy])
    s = re.search(r"Electricity supplied \(MWh\) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)", t)
    o = re.search(r"Obligation \(ROCs\) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)", t)
    if not (s and o):
        raise ValueError(f"RO report {fy}: supply/obligation table anchor missing")
    yr = f"{fy}-{str(fy + 1)[2:]}"
    if yr not in t and f"{fy} to {fy + 1}" not in t and f"{fy}-{fy + 1}" not in t and f"{fy} -{fy + 1}" not in t:
        raise ValueError(f"RO report {fy}: wrong year")
    sup = [_num(x) for x in s.groups()]
    obl = [_num(x) for x in o.groups()]
    e = re.search(r"Total excluded EII electricity (?:from oblig(?:ation|\.)|\(MWh\)) "
                  r"([\d,.]+) ([\d,.]+) ([\d,.]+)", t)
    if fy >= 2018 and not e:
        raise ValueError(f"RO report {fy}: EII table anchor missing")
    eii_gb = _num(e.group(3)) if e else 0.0
    return {"supply_ew": sup[0], "supply_sc": sup[1], "supply_ni": sup[2], "supply_uk": sup[3],
            "rocs_ew": obl[0], "rocs_sc": obl[1], "rocs_ni": obl[2], "rocs_uk": obl[3],
            "eii_excluded_gb": eii_gb}


def read_ro() -> dict[int, SchemeYear]:
    bo = read_ro_buyout()
    out = {}
    for fy in RO_REPORTS:
        r = read_ro_report(fy)
        rocs_gb = r["rocs_ew"] + r["rocs_sc"]
        out[fy] = SchemeYear(
            "RO", fy, rocs_gb * bo[fy], r["supply_ew"] + r["supply_sc"], r["eii_excluded_gb"],
            "modelled", f"OFGEM-RO-AR-{fy_label(fy)}",
            f"GB obligation {rocs_gb:,.0f} ROCs x buy-out £{bo[fy]:.2f}")
    return out


# --------------------------------------------------------------------------------------------
# FiT: Ofgem annual levelisation notices (2015-16 to 2022-23) and annual reports SY14, SY15
# --------------------------------------------------------------------------------------------
FIT_NOTICES = {fy: f"FIT_levelisation_notice_{fy_label(fy)}.pdf" for fy in range(2015, 2023)}
FIT_REPORTS = {2023: "FIT_annual_report_SY14.pdf", 2024: "FIT_annual_report_SY15.pdf"}


def read_fit_year(fy: int) -> dict[str, float | None]:
    """Levelisation Fund (£) and volumes (MWh) for one FiT year, as printed by Ofgem."""
    if fy in FIT_NOTICES:
        t = _pdf_text(OFG / FIT_NOTICES[fy])
        if f"1 April {fy} to 31 March {fy + 1}" not in t and f"({fy}-{fy + 1})" not in t \
                and f"{fy}-{str(fy + 1)[2:]}" not in t:
            raise ValueError(f"FiT notice {fy}: wrong year")
        fund = re.search(r"total Levelisation Fund for the year was calculated at £([\d,.]+?)\.?(?: |$)", t)
        if not fund:
            raise ValueError(f"FiT notice {fy}: fund anchor missing")
        res: dict[str, float | None] = {"fund": _num(fund.group(1).rstrip("."))}
        sup = re.search(r"A total of ([\d,.]+) ?MWh of electricity supplied", t)
        if not sup:                       # 2015-16 notice prints no volumes
            res.update(supply=None, extra=None, green=None, eii=None, relevant=None)
            return res
        add = re.search(r"further addition of ([\d,.]+) ?MWh", t)
        cap = re.search(r"annual cap of ([\d,.]+?) ?MWh", t)
        eii = re.search(r"with ([\d,.]+) ?MWh of this being claimed", t)
        rel = re.search(r"Total Relevant Electricity Supply was ([\d,.]+?) ?MWh", t)
        if not rel:
            raise ValueError(f"FiT notice {fy}: relevant-supply anchor missing")
        res.update(supply=_num(sup.group(1)), extra=_num(add.group(1)) if add else 0.0,
                   green=_num(cap.group(1)) if cap else 0.0,
                   eii=_num(eii.group(1)) if eii else 0.0, relevant=_num(rel.group(1)))
        return res
    t = _pdf_text(OFG / FIT_REPORTS[fy])
    if f"1 April {fy} to 31 March {fy + 1}" not in t:
        raise ValueError(f"FiT report {fy}: wrong year")
    a = re.search(r"Total supply \(A\) ([\d,]+)", t)
    b = re.search(r"Additional supply \(B\) ([\d,]+)", t)
    c = re.search(r"\(EIIs\) \(C\) ([\d,]+)", t)
    d = re.search(r"Additional exempt supply for energy intensive industries \(EIIs\) \(D\) ([\d,]+)", t)
    rel = re.search(r"Total [Rr]elevant electricity supplied \([^)]*\) ?[–-] ?\([^)]*\) ([\d,]+)", t)
    fund = re.search(r"The levelisation fund \(D\) \(A \+ B \+ C\) £([\d,]+)", t)
    if not (a and b and c and rel and fund):
        raise ValueError(f"FiT report {fy}: anchor missing")
    return {"fund": _num(fund.group(1)), "supply": _num(a.group(1)), "extra": _num(b.group(1)),
            "green": 0.0, "eii": _num(c.group(1)) + (_num(d.group(1)) if d else 0.0),
            "relevant": _num(rel.group(1))}


def read_fit() -> dict[int, SchemeYear | dict]:
    out: dict[int, SchemeYear | dict] = {}
    for fy in list(FIT_NOTICES) + list(FIT_REPORTS):
        r = read_fit_year(fy)
        sid = f"OFGEM-FIT-{'LN' if fy in FIT_NOTICES else 'AR'}-{fy_label(fy)}"
        if r["relevant"] is None:
            out[fy] = {"scheme": "FiT", "fy": fy, "cost_gbp": r["fund"], "basis": UNSOURCED,
                       "source_id": sid, "note": "notice prints no supply volumes"}
            continue
        out[fy] = SchemeYear("FiT", fy, r["fund"], r["relevant"], r["green"] + r["eii"],
                             "measured", sid, "total Levelisation Fund")
    return out


# --------------------------------------------------------------------------------------------
# Domestic share and GB households: one definition each, in system_costs (via taxes); review S3
# --------------------------------------------------------------------------------------------
_fy_weight = fy_weight


# --------------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------------
def split(sy: SchemeYear, d: float) -> tuple[float, float]:
    """(domestic £, business £). Households pay cost/chargeable £/MWh on d x gross MWh."""
    dom = sy.cost_gbp * d * sy.gross_mwh / sy.chargeable_mwh
    return dom, sy.cost_gbp - dom


def layer3() -> list[dict]:
    """One row per scheme per financial year, plus a 'total' row per year where all three exist."""
    d_cy = domestic_share_cy()
    schemes = {"CfD": read_cfd(), "RO": read_ro(), "FiT": read_fit()}
    rows = []
    years = sorted(set().union(*schemes.values()))
    for fy in years:
        try:
            d, d_basis = _fy_weight(d_cy, fy)
            hh, hh_basis = gb_households_fy(fy)
        except KeyError:
            continue
        year_rows = []
        for name, data in schemes.items():
            sy = data.get(fy)
            if sy is None:
                continue
            if isinstance(sy, dict):                      # UNSOURCED volumes
                rows.append({**sy, "period": fy_label(fy), "business_gbp": UNSOURCED,
                             "per_household": UNSOURCED})
                continue
            dom, bus = split(sy, d)
            bus_basis = "estimated" if "estimated" in (d_basis, hh_basis) else "modelled"
            r = {"scheme": name, "period": fy_label(fy), "fy": fy,
                 "cost_gbp": sy.cost_gbp, "cost_basis": sy.basis,
                 "chargeable_mwh": sy.chargeable_mwh, "exempt_mwh": sy.exempt_mwh,
                 "domestic_share": d, "domestic_gbp": dom, "business_gbp": bus,
                 "gb_households": hh, "business_per_household": bus / hh,
                 "passed_through": {k: p * UK_SOLD_SHARE * bus / hh for k, p in PASS_THROUGH.items()},
                 "pass_through_label": PASS_THROUGH_LABEL,
                 "business_basis": bus_basis, "passed_through_basis": "estimated",
                 "basis": "estimated", "note": sy.note,
                 "source_id": f"{sy.source_id}; DUKES26-5.2; DUKES26-5.5; ONS-LFS GB households"}
            rows.append(r)
            year_rows.append(r)
        if len(year_rows) == 3:
            bus = sum(r["business_gbp"] for r in year_rows)
            hh = year_rows[0]["gb_households"]
            rows.append({"scheme": "total", "period": fy_label(fy), "fy": fy, "business_gbp": bus,
                         "business_per_household": bus / hh,
                         "passed_through": {k: p * UK_SOLD_SHARE * bus / hh for k, p in PASS_THROUGH.items()},
                         "pass_through_label": PASS_THROUGH_LABEL,
                         "business_basis": ("estimated" if any(r["business_basis"] == "estimated"
                                                               for r in year_rows) else "modelled"),
                         "passed_through_basis": "estimated", "basis": "estimated",
                         "source_id": "sum of CfD, RO, FiT rows"})
    return rows


if __name__ == "__main__":
    for r in layer3():
        if r["scheme"] == "total" or isinstance(r.get("business_gbp"), str):
            pt = r.get("passed_through", {})
            print(r["period"], r["scheme"], r["business_gbp"] if isinstance(r["business_gbp"], str)
                  else f"business £{r['business_gbp']/1e6:,.0f}m  £{r['business_per_household']:.2f}/hh  "
                       f"passed £{pt['central']:.2f} ({pt['low']:.2f}-{pt['high']:.2f})  "
                       f"business {r['business_basis']}, passed {r['passed_through_basis']}")
        else:
            print(r["period"], r["scheme"], f"cost £{r['cost_gbp']/1e6:,.0f}m  d={r['domestic_share']:.3f}  "
                  f"business £{r['business_gbp']/1e6:,.0f}m  £{r['business_per_household']:.2f}/hh")
