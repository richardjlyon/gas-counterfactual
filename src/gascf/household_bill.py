"""s31: a typical household's electricity bill in both Britains, in two pots.

Plain words. Take one typical household: GB average, single-rate electricity, paying by Direct
Debit, using Ofgem's Typical Domestic Consumption Value (TDCV, "Medium", Profile Class 1) in force
in each price-cap period: 3,100 kWh (TDCV 2017, and before), 2,900 kWh from 1 April 2020, 2,700 kWh
from 1 October 2023, 2,500 kWh from 1 July 2026 (Ofgem decision letters, data/raw/ofgem/s31-*).
Its bill each cap period is Ofgem's cap, line by line (``receipt_actual``), restated at the TDCV
by ``receipt_actual.at_consumption`` (unit-rate parts scale; standing-charge parts do not). That
is the **net-zero column** (Richard, 13 Oct 2026: the reader's household is the TDCV household).

Calibration only: at Ofgem's cap benchmark consumption (3,100 kWh to December 2025, 2,700
Jan-Jun 2026, 2,500 from July 2026; cap model v1.31 ``Notes`` row 163), the same column must
reproduce Ofgem's published cap total in every period (``typical_year(y, "benchmark")``).

The **Reliable column** is the same bill with each net-zero part swapped for its value in
Reliable Britain (the engine still calls it fossil Britain: the actual system with net-zero
policy removed), using the engine's own national lines (``bills.build``):

* wholesale (direct fuel + backwardation): x (GO1 + GO1k) / NZ1, Reliable Britain's wholesale
  bill per £ of the actual one, same year. Split in Pot 1 into carbon (NZ1c / NZ1, and of that
  the tax collected, NZ1c_tax / NZ1c) and power before carbon (the rest).
* Contracts for Difference, Renewables Obligation, Feed-in Tariffs, ECO, Sizewell C: 0.
* Capacity Market: x (1 - NZ5 / CM paid), i.e. only Reliable Britain's own backup is kept.
* TNUoS: x GO5 / NZ7. BSUoS: x GO4 / NZ6 (the engine's grid and balancing lines).
* VAT: recomputed at the period's rate (5%) on the Reliable column's ex-VAT total.
* Everything else (local wires, supplier costs, metering, Warm Home Discount, AAHEDC, EII levy,
  EBIT, headroom, levelisation, adjustment allowance): the same in both. ``CLASSIFICATION``
  gives the reason and source for each line, and the calls Richard must still make.

Calendar years are the time-weighted (days) average of the cap periods that cover them.

**Pot 1, "On your bill"** = net-zero column minus Reliable column, line by line.

**Pot 2, "Not on it"**: the national net-zero extra (the engine's waterfall steps, £m) that
lands on business and public-sector electricity bills, per GB household, as named lines, plus
"of which, tax the Treasury kept" (carbon tax collected in the power price, CCL). One
sector-by-component allocation (roast fault B3):

* steps 1, 2, 4, 5, 6 (power before carbon, carbon, Capacity Market extra, balancing, grid):
  shares of UK electricity sales, DUKES 2026 Table 5.2 public distribution rows "Domestic" and
  "Public administration" over Table 5.5.D "UK electricity sales"; business = the rest.
* step 3 (RO, FiT, CfD): EII and green-import exempt volumes are business; the scheme's £/MWh on
  chargeable volume is paid by domestic and public sector on their whole volume, so their shares
  are d x gross / chargeable and p x gross / chargeable (``goods.read_*`` volumes, financial
  years weighted 3/12 + 9/12 into the calendar year); business is the rest, net of exemptions.
* step 7 (CCL): business and public sector only (not charged on domestic supply, HMRC CCL
  rates page), split by their volume shares.
* steps 8 (energy-saving schemes) and 9 (VAT on households' share): households only.
* UK ETS indirect-cost compensation to energy-intensive industry (DBT transparency reports,
  UK, x GB share): paid by taxpayers, so it is taken OFF the business line and shown once, as
  its own line in the reconciliation (roast fault B1).

**Reconciliation** (no scaling of typical to average): average domestic on-bill (same
allocation) + business + public sector + residual = the national gap per GB household. The
residual is the taxpayer-funded compensation, the one part of the gap on no electricity bill.

Before 2019 there is no cap in force: Pot 1 is the engine's average-household figure
(``bills.on_household_bill``), labelled "average household", and the break is flagged. The
2016-18 typical columns (Ofgem's illustrative cap levels) are computed and labelled
illustrative.

Money: per-period lines are nominal; annual values are given nominal and in 2025 money (CPIH,
``bills.real``), the money of the £570 headline.
"""
from __future__ import annotations

import html
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from gascf import bills as B
from gascf import receipt_actual as RA
from gascf import waterfall as W

ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = ROOT / "data/raw/dbt"
FIRST_CAP_YEAR = 2019              # the cap was in force from 1 Jan 2019
TYPICAL_YEARS = range(2016, 2026)  # 2016-18 illustrative (Ofgem shows them "for illustration only")
POT_YEARS = range(2016, 2026)
SRC_DBT = "dbt-ukets-indirect-compensation-{fy}"
SRC_CCL_DOMESTIC = "hmrc-ccl-rates-page"
SRC_DUKES_PUBLIC = "dukes-5.2-public-administration;dukes-5.5D"

# --------------------------------------------------------------------------- classification
# Every cap line: (treatment, reason, source id). Treatments:
#   "wholesale"  scaled by Reliable Britain's wholesale bill per £ of the actual one
#   "removed"    net-zero policy cost; Reliable Britain pays nothing
#   "cm"         Capacity Market cut to Reliable Britain's own backup
#   "tnuos"/"bsuos"  scaled by the engine's grid / balancing lines
#   "vat"        recomputed at the period's VAT rate
#   "same"       not net zero, the same in both bills
# A line whose class is a judgement Richard has not ruled on carries `call=True`.
CLASSIFICATION: dict[str, dict] = {
    "direct_fuel": dict(treatment="wholesale", call=False, source_id="ofgem-cap-model-v1.31;GO1;GO1k;NZ1",
                        reason="Wholesale energy: Reliable Britain buys power from its own fleet (engine GO1 + GO1k "
                               "against NZ1, spec §4, §15.3)."),
    "backwardation": dict(treatment="wholesale", call=False, source_id="ofgem-cap-model-v1.31;GO1;GO1k;NZ1",
                          reason="Part of Ofgem's wholesale allowance (hedging timing), so it moves with wholesale."),
    "cfd": dict(treatment="removed", call=False, source_id="ofgem-cap-model-v1.31",
                reason="Contracts for Difference: renewables (and nuclear) subsidy, spec §5.2; none in Reliable Britain."),
    "capacity_market": dict(treatment="cm", call=False, source_id="ofgem-cap-model-v1.31;NZ5;lccc-cm-obligation-mw",
                            reason="Spec §5.4 (s32): Reliable Britain's line = the cap's CM line x (its notional CM on "
                                   "the firm capacity GO1 does not already pay for / CM paid, LCCC); the rest, "
                                   "NZ5, is net zero and goes to Pot 1."),
    "adjustment_allowance": dict(treatment="same", call=True, source_id="ofgem-cap-model-v1.31",
                                 reason="Ofgem's own words: 'calculated according to Annex 8 to the licence "
                                        "conditions'. Not a net-zero scheme on its face; kept the same (smaller net "
                                        "zero). CALL: Richard to confirm."),
    "ro": dict(treatment="removed", call=False, source_id="ofgem-annex4-v1.25",
               reason="Renewables Obligation: renewables subsidy, spec §5.2."),
    "fit": dict(treatment="removed", call=False, source_id="ofgem-annex4-v1.25",
                reason="Feed-in Tariffs: small renewables subsidy, spec §5.2."),
    "eco": dict(treatment="removed", call=False, source_id="ofgem-annex4-v1.25;desnz-eco4-guidance",
                reason="Spec §15.4 item 1: energy-saving obligations are net-zero policy (ECO guidance: 'contribute "
                       "to carbon reduction targets in the domestic sector')."),
    "whd": dict(treatment="same", call=False, source_id="ofgem-annex4-v1.25",
                reason="Spec §15.4 item 1: the Warm Home Discount is social policy, in both bills."),
    "aahedc": dict(treatment="same", call=False, source_id="ofgem-annex4-v1.25",
                   reason="Richard, 11 Oct 2026 (export decision_sources): help with grid costs in the north of "
                          "Scotland, not net zero."),
    "eii_levy": dict(treatment="same", call=True, source_id="ofgem-annex4-v1.25;desnz-eii-levy-ia-2024",
                     reason="Richard, 11 Oct 2026 (export decision_sources, keep=False): the levy funds network-"
                            "charge relief for heavy industry (UKIA 2024/62 para 52), not net zero. CALL: the s30 "
                            "Claude roast (S-5) argues it belongs on the net-zero side; left the same in both "
                            "(smaller net zero)."),
    "sizewell_c": dict(treatment="removed", call=True, source_id="ofgem-annex4-v1.25;desnz-szc-fid-vfm",
                       reason="Richard, 11 Oct 2026 (export decision_sources, keep=True): DESNZ says new nuclear is "
                              "'required for a low cost, net zero compliant energy system'. Not renewables, but net-"
                              "zero policy. Charged only from Jan 2026, so it moves no 2019-2025 figure. CALL: "
                              "spec §15 does not rule on it; Richard to confirm."),
    "tnuos": dict(treatment="tnuos", call=False, source_id="ofgem-annex3-elec-v1.25;NZ7;GO5",
                  reason="High-voltage grid: Reliable Britain's grid is the pre-net-zero size plus renewal (spec "
                         "§7.1, §7.3), engine GO5 / NZ7."),
    "duos": dict(treatment="same", call=True, source_id="ofgem-annex3-elec-v1.25",
                 reason="Local wires: the brief keeps them the same in both (spec S1). CALL: any net-zero "
                        "reinforcement inside DUoS is not counted (smaller net zero)."),
    "bsuos": dict(treatment="bsuos", call=False, source_id="ofgem-annex3-elec-v1.25;NZ6;GO4",
                  reason="Running the grid: engine GO4 / NZ6 (spec §5.5, §7.2)."),
    "operating_costs": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                            reason="Supplier operating costs: not net zero (spec S1)."),
    "core_operating_costs": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                                 reason="Supplier operating costs: not net zero (spec S1)."),
    "smart_meter": dict(treatment="same", call=True, source_id="ofgem-cap-model-v1.31",
                        reason="Metering (spec S1). CALL: smart meters are partly justified by net zero; kept the "
                               "same (smaller net zero)."),
    "industry_charges": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                             reason="Supplier industry charges: not a net-zero scheme on its face (spec S1)."),
    "payment_adjustment_cost": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                                    reason="Payment-method cost: not net zero."),
    "payment_adjustment_pct": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                                   reason="Payment-method uplift, a % of costs. Reliable Britain's costs are lower, "
                                          "so keeping it the same makes net zero smaller (conservative rule)."),
    "debt_related_costs": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                               reason="Bad debt: not net zero (it would be lower on a lower bill; kept, conservative)."),
    "ebit": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                 reason="Supplier margin, a % of costs: kept the same (conservative rule, as payment uplift)."),
    "headroom": dict(treatment="same", call=False, source_id="ofgem-cap-model-v1.31",
                     reason="Headroom, a % of costs: kept the same (conservative rule)."),
    "levelisation": dict(treatment="same", call=False, source_id="ofgem-annex9-v1.11",
                         reason="Payment-method levelisation between customers: not net zero."),
    "vat": dict(treatment="vat", call=False, source_id="ofgem-annex9-v1.11;hmrc-vfup1000",
                reason="VAT at the period's rate (5%) on whatever the bill is: recomputed on the Reliable column."),
}
TREATMENTS = ("wholesale", "removed", "cm", "tnuos", "bsuos", "vat", "same")

# Pot 1 line ids: one per net-zero difference; the wholesale difference is split three ways.
POT1_LINES = {
    "power_before_carbon": "Power before carbon (Reliable Britain's own fleet instead)",
    "carbon_tax": "Carbon in the power price: collected as tax (Carbon Price Support, UK carbon auctions)",
    "carbon_price": "Carbon in the power price: not collected as tax in GB",
    "cfd": "Contracts for Difference", "ro": "Renewables Obligation", "fit": "Feed-in Tariffs",
    "eco": "Energy Company Obligation (ECO)", "sizewell_c": "Sizewell C nuclear levy",
    "capacity_market": "Capacity Market above Reliable Britain's own backup",
    "tnuos": "High-voltage grid (TNUoS) extra", "bsuos": "Running the grid (BSUoS) extra",
    "vat": "VAT on the extra",
}


# --------------------------------------------------------------------------- engine inputs

@lru_cache(maxsize=1)
def engine() -> dict[int, dict]:
    """The engine's central bills, built once."""
    return B.build(B.CENTRAL)


@lru_cache(maxsize=None)
def steps(y: int) -> tuple[dict, ...]:
    return tuple(W.steps_for(engine()[y], y))


def ratios(y: int) -> dict:
    """Reliable Britain's value per £ of the actual one, for each scaled line, calendar year y."""
    b = engine()[y]
    v = lambda i: B.val(b, i)                                         # noqa: E731
    nz1, go = v("NZ1"), v("GO1") + v("GO1k")
    cm = b["cm"]["paid_gbp_m"]
    tax = b["carbon_split"]["carbon_price_receipts"]["national_gbp_m_nominal"] if "carbon_split" in b else 0.0
    return {
        "wholesale": go / nz1,
        "carbon_of_wholesale": v("NZ1c") / nz1,
        "tax_of_carbon": tax / v("NZ1c") if v("NZ1c") else 0.0,
        # s32 (spec §5.4): Reliable Britain's CM per £ of the actual = its notional CM (on the firm
        # capacity GO1 does not pay for) / CM paid, capped at 1 (= 1 − NZ5 / CM paid)
        "cm": min(1.0, b["cm"]["fossil_gbp_m"] / cm) if cm else 1.0,
        "tnuos": v("GO5") / v("NZ7"),
        "bsuos": v("GO4") / v("NZ6"),
    }


# --------------------------------------------------------------------------- the typical bill

def _days(a: date, b: date) -> int:
    return (b - a).days + 1


def period_weights(y: int) -> list[tuple[RA.Receipt, float]]:
    """Cap periods covering calendar year y, each with its share of the year's days."""
    y0, y1 = date(y, 1, 1), date(y, 12, 31)
    out = []
    for r in RA.receipts():
        a, b = RA.period_dates(r.period)
        lo, hi = max(a, y0), min(b, y1)
        if lo <= hi:
            out.append((r, _days(lo, hi) / _days(y0, y1)))
    if abs(sum(w for _, w in out) - 1.0) > 1e-9:
        raise KeyError(f"cap periods do not cover all of {y}")
    return out


def reliable_value(key: str, nz: float, rt: dict) -> float:
    """Reliable Britain's value of one cap line (not VAT), £/yr."""
    t = CLASSIFICATION[key]["treatment"]
    if t == "wholesale":
        return nz * rt["wholesale"]
    if t == "removed":
        return 0.0
    if t in ("cm", "tnuos", "bsuos"):
        return nz * rt[t]
    if t == "same":
        return nz
    raise ValueError(f"{key}: treatment {t} has no line rule")


def receipt_columns(r: RA.Receipt, rt: dict) -> dict:
    """One cap period, both columns, line by line (£/yr at the receipt's consumption)."""
    rows = []
    for ln in r.lines:
        if ln.key == "vat":
            continue
        rows.append({"key": ln.key, "label": ln.label, "netzero": ln.typical,
                     "reliable": reliable_value(ln.key, ln.typical, rt),
                     "treatment": CLASSIFICATION[ln.key]["treatment"], "source_id": ln.source_id})
    nz_ex = sum(x["netzero"] for x in rows)
    rel_ex = sum(x["reliable"] for x in rows)
    vat = r.line("vat")
    rows.append({"key": "vat", "label": vat.label, "netzero": vat.typical, "reliable": rel_ex * r.vat_rate,
                 "treatment": "vat", "source_id": vat.source_id})
    return {"rows": rows, "netzero": nz_ex + vat.typical, "reliable": rel_ex * (1 + r.vat_rate)}


# Ofgem's Typical Domestic Consumption Value (TDCV), electricity Profile Class 1 (single rate),
# "Medium": the household Ofgem shows the public. NOT the cap benchmark (Ofgem: "our amendments
# to the TDCVs will not affect the benchmark annual consumption values in the licence
# conditions"), which is used only to reproduce Ofgem's published cap totals.
# (file, quote that must be in it, first day, kWh). The 2017 decision's "Current" column gives the
# value before 1 Oct 2017 (3,100), so the 2015-17 periods are covered too.
TDCV_SOURCES = (
    ("s31-TDCV_2017_decision.txt", "Medium 3,100 3,100", date(2015, 4, 1), 3100.0, "ofgem-tdcv-2017-decision"),
    ("s31-TDCV_2020_decision_letter.txt", "use the new TDCVs from 1 April 2020", date(2020, 4, 1), 2900.0,
     "ofgem-tdcv-2020-decision"),
    ("s31-TDCV_2023_decision_letter.txt", "use the new TDCVs from 1 October 2023", date(2023, 10, 1), 2700.0,
     "ofgem-tdcv-2023-decision"),
    ("s31-TDCV_2026_decision.txt", "Implementation of new TDCV values: 1 July 2026", date(2026, 7, 1), 2500.0,
     "ofgem-tdcv-2026-decision"),
)
TDCV_TABLE_QUOTES = {"s31-TDCV_2020_decision_letter.txt": "Medium 3,100 2,900",
                     "s31-TDCV_2023_decision_letter.txt": "Medium 2,900 2,700",
                     "s31-TDCV_2026_decision.txt": "Medium 2,700 2,500"}


@lru_cache(maxsize=1)
def tdcv_schedule() -> tuple[tuple[date, float, str], ...]:
    """[(first day, kWh, source id)], read-checked against the stored Ofgem decision texts."""
    out = []
    for fn, quote, d0, kwh, sid in TDCV_SOURCES:
        t = " ".join((RA.RAW / fn).read_text(encoding="utf-8").split())
        for q in (quote, TDCV_TABLE_QUOTES.get(fn, quote)):
            if q not in t:
                raise ValueError(f"{fn}: anchor {q!r} missing")
        out.append((d0, kwh, sid))
    return tuple(out)


def tdcv_for(period) -> tuple[float, str]:
    """TDCV (kWh) in force for a whole cap period. Raises if a TDCV change falls inside it."""
    a, b = RA.period_dates(period)
    sched = tdcv_schedule()
    live = [(d0, k, sid) for d0, k, sid in sched if d0 <= a]
    if not live:
        raise KeyError(f"no TDCV before {a}")
    if any(a < d0 <= b for d0, _, _ in sched):
        raise ValueError(f"TDCV changes inside cap period {period}")
    return live[-1][1], live[-1][2]


CONSUMPTION = ("tdcv", "benchmark")


def typical_year(y: int, consumption: str = "tdcv") -> dict:
    """The typical household's two bills for calendar year y, nominal £, days-weighted over the
    cap periods.

    consumption="tdcv" (the reader's household): each period restated at the TDCV in force by
    `receipt_actual.at_consumption` (unit-rate parts scale, standing-charge parts do not; Ofgem's
    own Annex 9 tab 1c method). consumption="benchmark" (calibration only): Ofgem's cap benchmark
    consumption, at which the net-zero column must reproduce Ofgem's published cap."""
    if consumption not in CONSUMPTION:
        raise ValueError(consumption)
    rt = ratios(y)
    lines: dict[str, dict] = {}
    periods, published = [], 0.0
    for r, w in period_weights(y):
        if consumption == "tdcv":
            kwh, sid = tdcv_for(r.period)
            rr = RA.at_consumption(r.period, kwh)
        else:
            rr, sid = r, RA.SRC_CAP
        c = receipt_columns(rr, rt)
        for row in c["rows"]:
            d = lines.setdefault(row["key"], {**row, "netzero": 0.0, "reliable": 0.0})
            d["netzero"] += w * row["netzero"]
            d["reliable"] += w * row["reliable"]
        periods.append({"label": r.label, "weight": w, "consumption_mwh": rr.consumption_mwh,
                        "consumption_source_id": sid,
                        "benchmark_mwh": r.consumption_mwh, "netzero": c["netzero"], "reliable": c["reliable"],
                        "published_inc_vat": r.published_inc_vat, "cap_in_force": r.cap_in_force,
                        "epg_in_force": r.epg_in_force,
                        "check_gbp": (c["netzero"] - r.published_inc_vat) if consumption == "benchmark" else None})
        published += w * r.published_inc_vat
    rows = list(lines.values())
    nz, rel = sum(x["netzero"] for x in rows), sum(x["reliable"] for x in rows)
    return {"year": y, "consumption": consumption, "rows": rows, "netzero": nz, "reliable": rel, "ratios": rt,
            "published_inc_vat": published if consumption == "benchmark" else None,
            "check_gbp": (nz - published) if consumption == "benchmark" else None, "periods": periods,
            "consumption_mwh": sorted({p["consumption_mwh"] for p in periods}),
            "mean_kwh": 1000 * sum(p["weight"] * p["consumption_mwh"] for p in periods),
            "kind": "typical" if y >= FIRST_CAP_YEAR else "typical_illustrative",
            "epg": any(p["epg_in_force"] for p in periods)}


def pot1(t: dict) -> list[dict]:
    """Pot 1, line by line: net-zero column minus Reliable column. The wholesale difference is
    split into power before carbon, carbon collected as tax, and carbon not collected."""
    rt = t["ratios"]
    by = {r["key"]: r for r in t["rows"]}
    out = []
    w_nz = sum(by[k]["netzero"] for k in ("direct_fuel", "backwardation") if k in by)
    carbon = w_nz * rt["carbon_of_wholesale"]
    w_diff = sum(by[k]["netzero"] - by[k]["reliable"] for k in ("direct_fuel", "backwardation") if k in by)
    out.append({"id": "power_before_carbon", "value": w_diff - carbon, "from": ["direct_fuel", "backwardation"]})
    out.append({"id": "carbon_tax", "value": carbon * rt["tax_of_carbon"], "from": ["direct_fuel", "backwardation"]})
    out.append({"id": "carbon_price", "value": carbon * (1 - rt["tax_of_carbon"]),
                "from": ["direct_fuel", "backwardation"]})
    for k in ("cfd", "ro", "fit", "eco", "sizewell_c", "capacity_market", "tnuos", "bsuos", "vat"):
        if k in by:
            out.append({"id": k, "value": by[k]["netzero"] - by[k]["reliable"], "from": [k]})
    for o in out:
        o["label"] = POT1_LINES[o["id"]]
    return out


# --------------------------------------------------------------------------- sector shares

@lru_cache(maxsize=1)
def public_share_cy() -> dict[int, float]:
    """Public-sector share of UK electricity sales: DUKES 2026 Table 5.2 public distribution row
    'Public administration' (includes public lighting) over Table 5.5.D 'UK electricity sales',
    the same denominator as the engine's domestic share."""
    from gascf.system_costs import DUKES_52, _dukes_row, domestic_share_cy
    pub = _dukes_row(DUKES_52, "5.2", "Public administration", "Public distribution system ")
    dom = _dukes_row(DUKES_52, "5.2", "Domestic", "Public distribution system ")
    d = domestic_share_cy()
    # sales = domestic / d (the engine's own denominator, DUKES 5.5.D)
    return {y: pub[y] * d[y] / dom[y] for y in pub if y in d}


def shares(y: int) -> dict:
    from gascf.system_costs import domestic_share_cy
    d, p = domestic_share_cy()[y], public_share_cy()[y]
    return {"domestic": d, "public": p, "business": 1.0 - d - p}


def _cy_from_fy(series: dict[int, float], y: int) -> tuple[float | None, str]:
    """Calendar year y = 3/12 of financial year y-1 + 9/12 of financial year y. A missing
    financial year is replaced by the nearest one present, tagged estimated."""
    if not series:
        return None, "UNSOURCED"
    parts, basis = [], "modelled"
    for fy, wt in ((y - 1, 0.25), (y, 0.75)):
        if fy in series:
            parts.append(wt * series[fy])
        else:
            near = min(series, key=lambda k: (abs(k - fy), k))
            parts.append(wt * series[near])
            basis = "estimated"
    return sum(parts), basis


@lru_cache(maxsize=1)
def _uplift_fy() -> dict[str, dict[int, float]]:
    """gross / chargeable volume per scheme and financial year (EII and green-import exempt
    volume is all non-domestic), from goods.read_* (LCCC, Ofgem RO and FiT reports)."""
    from gascf import goods as G
    out = {}
    for name, f in (("cfd", G.read_cfd), ("ro", G.read_ro), ("fit", G.read_fit)):
        out[name] = {fy: s.gross_mwh / s.chargeable_mwh for fy, s in f().items()
                     if isinstance(s, G.SchemeYear) and s.chargeable_mwh}
    return out


def uplift(y: int) -> dict[str, tuple[float | None, str]]:
    return {k: _cy_from_fy(v, y) for k, v in _uplift_fy().items()}


# --------------------------------------------------------------------------- compensation

def _dbt_file(fy: int) -> Path:
    return DBT_DIR / f"s31-indirect_compensation_{fy}-to-{fy + 1}.html"


@lru_cache(maxsize=1)
def compensation_fy() -> dict[int, dict]:
    """UK ETS indirect-cost compensation awarded to energy-intensive industry, UK, £, by
    financial year (DBT transparency reports, Subsidy Control Act 2022 reporting). Sum of the
    five sector rows of each report's table."""
    out = {}
    for p in sorted(DBT_DIR.glob("s31-indirect_compensation_20*-to-20*.html")):
        m = re.search(r"_(\d{4})-to-", p.name)
        if m is None:
            continue
        fy = int(m.group(1))
        t = p.read_text(encoding="utf-8")
        t = t.replace("\\u003c", "<").replace("\\u003e", ">").replace('\\"', '"').replace("\\n", " ")
        i = t.find(f"Indirect Cost Compensation awarded in")
        if i < 0:
            raise ValueError(f"{p.name}: table anchor missing")
        seg = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", t[i:i + 6000])).split())
        rows = re.findall(r"(Iron and steel|Chemicals|Paper|Non-ferrous metals|Other) (\d+) ([\d.]+) million", seg)
        if [r[0] for r in rows[:5]] != ["Iron and steel", "Chemicals", "Paper", "Non-ferrous metals", "Other"]:
            raise ValueError(f"{p.name}: sector rows moved: {rows[:5]}")
        out[fy] = {"gbp_m": sum(float(r[2]) for r in rows[:5]), "sectors": {r[0]: float(r[2]) for r in rows[:5]},
                   "source_id": SRC_DBT.format(fy=f"{fy}-{(fy + 1) % 100:02d}"), "file": p.name}
    return out


def compensation_gb(y: int) -> dict:
    """GB carbon-cost compensation for calendar year y, £m nominal. UK ETS began 1 Jan 2021, so
    financial years before 2021-22 (EU ETS and CPS compensation) are not in the DBT series:
    UNSOURCED (GAP). Calendar 2021 takes 9/12 of 2021-22 only (Jan-Mar 2021 GAP). A financial
    year not yet published takes the latest one, estimated. x GB share of UK consumption."""
    from gascf.system_costs import gb_share_of_uk
    c = compensation_fy()
    gb, gb_basis = gb_share_of_uk(y)
    if y < 2021 or not c:
        return {"gbp_m": None, "basis": "UNSOURCED", "source_id": "UNSOURCED",
                "note": "EU ETS / CPS compensation before UK ETS: not in the stored DBT series (GAP)"}
    if y == 2021:
        v, basis, note = 0.75 * c[2021]["gbp_m"], "estimated", "9/12 of FY 2021-22; Jan-Mar 2021 (EU ETS) GAP"
        srcs = [c[2021]["source_id"]]
    else:
        latest = max(c)
        v, basis = 0.0, "modelled"
        srcs, notes = [], []
        for fy, wt in ((y - 1, 0.25), (y, 0.75)):
            use = fy if fy in c else latest
            if use != fy:
                basis = "estimated"
                notes.append(f"FY {fy}-{(fy + 1) % 100:02d} not published: FY {use}-{(use + 1) % 100:02d} used")
            v += wt * c[use]["gbp_m"]
            srcs.append(c[use]["source_id"])
        note = "; ".join(notes)
    return {"gbp_m": v * gb, "basis": B.weakest(basis, gb_basis), "uk_gbp_m": v,
            "source_id": ";".join(dict.fromkeys(srcs + ["desnz_subnational_consumption_2024_t7.1"])),
            "note": (note + "; " if note else "") + "UK ETS only; CPS compensation not in the DBT reports (GAP)"}


# --------------------------------------------------------------------------- the two pots

STEP_SECTORS = {1: "volume", 2: "volume", 3: "subsidy", 4: "volume", 5: "volume", 6: "volume",
                7: "non_domestic", 8: "domestic", 9: "domestic"}


def allocate(y: int) -> dict:
    """Each waterfall step (national £m nominal) split domestic / business / public. Every step
    is split once and its parts add back to the step exactly."""
    b = engine()[y]
    sh = shares(y)
    d, p, bz = sh["domestic"], sh["public"], sh["business"]
    up = uplift(y)
    rows = []
    for st in steps(y):
        n = st["step"]
        if n in (0, "="):
            continue
        v = st["value_gbp_m_nominal"]
        rule = STEP_SECTORS[n]
        if rule == "volume":
            dom, pub = d * v, p * v
        elif rule == "subsidy":
            parts = {"ro": B.val(b, "NZ2"), "fit": B.val(b, "NZ3"),
                     "cfd": B.val(b, "NZ4") + W._opt(b, "NZ4b")}
            if abs(sum(parts.values()) - v) > 1e-6:
                raise ValueError(f"{y}: subsidy parts do not add to step 3")
            dom = sum(parts[k] * d * (up[k][0] if up[k][0] else 1.0) for k in parts)
            pub = sum(parts[k] * p * (up[k][0] if up[k][0] else 1.0) for k in parts)
        elif rule == "non_domestic":
            dom, pub = 0.0, v * p / (p + bz)
        elif rule == "domestic":
            dom, pub = v, 0.0
        else:
            raise ValueError(rule)
        rows.append({"step": n, "label": st["label"], "value": v, "rule": rule,
                     "domestic": dom, "public": pub, "business": v - dom - pub})
    tax = b["carbon_split"]["carbon_price_receipts"]["national_gbp_m_nominal"] if "carbon_split" in b else 0.0
    ccl = B.val(b, "NZ8")
    return {"rows": rows, "shares": sh, "uplift": up,
            "tax_kept": {"business": tax * bz + ccl * bz / (p + bz), "public": tax * p + ccl * p / (p + bz),
                         "domestic": tax * d},
            "carbon_price_receipts": tax, "ccl": ccl}


def pots(y: int) -> dict:
    """Pot 1, Pot 2 and the reconciliation for calendar year y, in 2025 money per GB household
    (Pot 1 also nominal)."""
    b = engine()[y]
    H = b["households"]
    hh = lambda m: B.real(m, y) * 1e6 / H                           # noqa: E731  £m nominal -> £/hh 2025 money
    al = allocate(y)
    comp = compensation_gb(y)
    comp_m = comp["gbp_m"] or 0.0
    dom_m = sum(r["domestic"] for r in al["rows"])
    bus_gross_m = sum(r["business"] for r in al["rows"])
    pub_m = sum(r["public"] for r in al["rows"])
    bus_net_m = bus_gross_m - comp_m
    gap = b["totals"]["gap_per_hh_real"]
    out = {"year": y, "households": H, "gap_per_household": gap, "allocation": al, "compensation": comp}
    if y >= FIRST_CAP_YEAR:
        t, cal = typical_year(y, "tdcv"), typical_year(y, "benchmark")
        p1 = pot1(t)
        out["pot1"] = {"kind": "typical", "label": "Typical household (Ofgem cap, GB average, Direct Debit, "
                                                   f"TDCV {t['mean_kwh']:,.0f} kWh)",
                       "lines": [{**l, "value_2025": B.real(l["value"], y)} for l in p1],
                       "nominal": t["netzero"] - t["reliable"],
                       "value_2025": B.real(t["netzero"] - t["reliable"], y), "typical": t,
                       "calibration": {"typical": cal, "lines": pot1(cal),
                                       "nominal": cal["netzero"] - cal["reliable"],
                                       "value_2025": B.real(cal["netzero"] - cal["reliable"], y)}}
    else:
        avg = B.on_household_bill(b, y, list(steps(y)))
        out["pot1"] = {"kind": "average", "label": "Average household (engine, no cap in force: break in series)",
                       "lines": [], "value_2025": avg["value"], "nominal": None, "engine": avg,
                       "typical_illustrative": typical_year(y, "tdcv") if y in TYPICAL_YEARS else None,
                       "calibration": {"typical": typical_year(y, "benchmark")} if y in TYPICAL_YEARS else None}
    out["pot2"] = {
        "business": hh(bus_net_m), "business_gross": hh(bus_gross_m), "public": hh(pub_m),
        # tax collected through business and public bills, less the compensation the Treasury
        # paid back to energy-intensive industry (netted once, from the business part)
        "tax_kept_business": hh(al["tax_kept"]["business"] - comp_m), "tax_kept_public": hh(al["tax_kept"]["public"]),
        "tax_kept": hh(al["tax_kept"]["business"] - comp_m + al["tax_kept"]["public"]),
        "compensation_netted": hh(comp_m),
    }
    out["reconciliation"] = {
        "average_domestic_on_bill": hh(dom_m), "business": hh(bus_net_m), "public": hh(pub_m),
        "residual_taxpayer_compensation": hh(comp_m),
        "total": hh(dom_m) + hh(bus_net_m) + hh(pub_m) + hh(comp_m),
        "national_gap_per_household": gap,
        "engine_on_household_bill": B.on_household_bill(b, y, list(steps(y)))["value"],
    }
    return out


def gaps() -> list[str]:
    """Plain list of what is not sourced or not decided, for Richard."""
    g = [
        "Carbon-cost compensation before UK ETS (EU ETS and Carbon Price Support compensation, 2013-2020, and "
        "Jan-Mar 2021): not in the stored DBT series. Business lines for 2019-2021 are gross of it and the "
        "residual is zero or partial.",
        "Carbon Price Support compensation (2021 on): DBT's reports give UK ETS compensation only. CPS "
        "compensation not found as a published total.",
        "Compensation FY 2025-26 not yet published: calendar 2025 uses FY 2024-25 for its Apr-Dec part (estimated).",
        "Energy Price Guarantee (Oct 2022 - Jun 2023): the household paid EPG rates, below the cap; the taxpayer "
        "paid the difference. The net-zero column is the cap, not what was paid. How much of each line the EPG "
        "covered is not sourced.",
        "RO, FiT volumes for financial year 2025-26 not stored: the 2025 EII uplift uses 2024-25 (estimated).",
        "Capacity Market EII exemption in force from 1 Apr 2024 (SI 2024/434) not modelled in the engine; "
        "stated in words with a labelled estimate (0092). Capacity Market split by volume.",
        "TDCV before 1 Oct 2017: the 2017 decision's 'Current' column (3,100 kWh) is used for the 2015-17 "
        "periods; the date that value took effect is not stored (it moves no 2019-2025 figure).",
        "Carbon tax share of the carbon in the power price (NZ1c_tax / NZ1c): the tax collected is a UK figure "
        "(HMRC CPS receipts, UK ETS auctions on power), the carbon a GB one, as in the engine's carbon split. "
        "Not put on a GB basis: the 'tax the Treasury kept' lines are slightly high.",
        "Public bodies' unrecovered VAT is not counted (the engine counts VAT on households only): smaller net zero.",
    ]
    return g


def calls() -> list[dict]:
    return [{"key": k, **v} for k, v in CLASSIFICATION.items() if v["call"]]
