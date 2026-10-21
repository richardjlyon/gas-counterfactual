"""Fleet A: today's gas fleet, topped up (spec §3, fleet A).

Existing plant: GB natural-gas CCGTs in DUKES Table 5.11 (major power producers, end May
2026; Northern Ireland excluded), running at DUKES 5.10.C CCGT fleet efficiency for the year
and never above the highest fleet load factor ever recorded, 84% (DUKES 5.10.B, 1999).
Existing GB gas single-cycle plant counts toward spare capacity only: no sourced efficiency
for it has been found, so it is not run (labelled; makes gas dearer).

Dispatch, cheapest first: new baseload CCGT (only as much as keeps existing CCGT at or
below 84%), then existing CCGT, then new plant above it costed by the screening curve,
exactly as fleet B. Spare capacity to the ECR rule (capacity.py) is bought as OCGT.

Price, per half-hour: running cost of the marginal plant (no carbon; carbon is step 2) plus
the gas-market margin from §8 validation. Consumers pay that price on every MWh, and new
plant is paid its full fixed cost on top (spec: "New plant is paid in full in step 1").
New plant also earns the gap between price and its own running cost; that rent is
reported (`new_plant_rent_gbp_m`) so the size of this cautious double payment is visible.

Existing plant's running cost carries no explicit gas transport: the §8 margin is measured
against market prices that already include it, so adding it here would count it twice.
New plant carries transport explicitly, as in fleet B.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from .gastransport import GasTransport
from .official import Plant
from .plant import annualised_fixed_gbp_kw_yr, variable_gbp_mwh

DUKES_511 = Path(__file__).parents[2] / "data/raw/DUKES_5.11.xlsx"
LF_CAP = 0.84


def read_existing_gb_gas(sheet: str = "5.11 Full list") -> dict[str, float]:
    """GB natural-gas capacity in MW: {'ccgt': ..., 'single_cycle': ...}."""
    rows = list(openpyxl.load_workbook(DUKES_511, read_only=True, data_only=True)[sheet]
                .iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r and "Site Name" in r)
    h = list(rows[hi])
    col = {k: h.index(k) for k in ("Type", "Primary Fuel", "InstalledCapacity (MW)", "Country")}
    out = {"ccgt": 0.0, "single_cycle": 0.0}
    for r in rows[hi + 1:]:
        if not r or r[col["Primary Fuel"]] != "Natural Gas" or r[col["Country"]] == "Northern Ireland":
            continue
        t = {"CCGT": "ccgt", "Single cycle": "single_cycle"}.get(r[col["Type"]])
        if t:
            out[t] += float(r[col["InstalledCapacity (MW)"]])
    return out


@dataclass(frozen=True)
class FleetA:
    new_baseload_gw: float
    existing_ccgt_gw: float
    existing_lf: float
    new_ccgt_gw: float           # above existing, from the screening curve
    new_ocgt_gw: float
    spare_gw: float
    energy_twh: float
    energy_payments_gbp_m: float   # price x MWh, all half-hours
    new_fixed_gbp_m: float         # full fixed cost of all new plant incl. spare
    new_plant_rent_gbp_m: float    # (price - own running cost) x output, new plant only

    @property
    def total_gbp_m(self) -> float:
        return self.energy_payments_gbp_m + self.new_fixed_gbp_m

    @property
    def gbp_per_mwh(self) -> float:
        return self.total_gbp_m / self.energy_twh


def _strip_energy(asc: list[float], lo: float, hi: float) -> float:
    """MWh delivered by a horizontal strip [lo, hi] MW of the load curve (half-hourly)."""
    i = bisect.bisect_left(asc, lo)
    return 0.5 * sum(min(r, hi) - lo for r in asc[i:])


def cost_fleet_a(ldc_mw: list[float], gas_gbp_mwh: float, eta_existing: float, vom_existing: float,
                 margin_gbp_mwh: float, existing_mw: dict[str, float], ccgt: Plant, ocgt: Plant,
                 reserve_margin: float, derating: dict[str, float],
                 transport: GasTransport | None = None, step_mw: float = 50.0,
                 hurdle: str = "medium") -> FleetA:
    asc = sorted(ldc_mw)
    n, peak = len(asc), asc[-1]
    hours = n / 2
    ce = existing_mw["ccgt"]

    # new baseload below existing: smallest X keeping existing CCGT at or under the cap
    def lf(x: float) -> float:
        return _strip_energy(asc, x, x + ce) / (ce * hours)
    lo_x, hi_x = 0.0, peak
    if lf(0.0) > LF_CAP:
        for _ in range(60):
            mid = (lo_x + hi_x) / 2
            lo_x, hi_x = (lo_x, mid) if lf(mid) <= LF_CAP else (mid, hi_x)
        x = hi_x
    else:
        x = 0.0
    top = min(peak, x + ce)

    plants = {"ccgt": ccgt, "ocgt": ocgt}
    tf = {q: transport.fixed_gbp_kw_e_yr(p.efficiency_gcv) if transport else 0.0 for q, p in plants.items()}
    tv = transport.commodity_gbp_mwh_gas if transport else 0.0
    fc = {q: annualised_fixed_gbp_kw_yr(p, hurdle=hurdle) + tf[q] for q, p in plants.items()}
    vc = {q: variable_gbp_mwh(p, gas_gbp_mwh, tv) for q, p in plants.items()}
    vc_exist = gas_gbp_mwh / eta_existing + vom_existing

    # strips: (lo, hi, plant, variable cost); 'exist' is the existing block
    strips: list[tuple[float, float, str, float]] = []
    lo = 0.0
    while lo < x:
        hi = min(lo + step_mw, x)
        strips.append((lo, hi, "ccgt", vc["ccgt"]))
        lo = hi
    strips.append((x, top, "exist", vc_exist))
    lo = top
    while lo < peak:
        hi = min(lo + step_mw, peak)
        share = (n - bisect.bisect_left(asc, (lo + hi) / 2)) / n
        mwh = (hi - lo) * share * hours
        p = min(("ccgt", "ocgt"), key=lambda q: fc[q] * 1000 * (hi - lo) + vc[q] * mwh)
        strips.append((lo, hi, p, vc[p]))
        lo = hi

    # merit order by running cost: the marginal plant in a half-hour is the dearest strip
    # that the half-hour's demand reaches
    los = [s[0] for s in strips]
    run_max = []
    m = 0.0
    for s in strips:
        m = max(m, s[3])
        run_max.append(m)
    price_sum = energy = new_payments = 0.0
    for r in asc:
        k = max(bisect.bisect_left(los, r) - 1, 0)
        price = run_max[k] + margin_gbp_mwh
        price_sum += price * r * 0.5
        energy += r * 0.5
        new_payments += price * (min(r, x) + max(0.0, r - top)) * 0.5

    # new plant: capacity, fixed cost, running cost
    gw = {"ccgt": x / 1000, "ocgt": 0.0}
    new_fixed = fc["ccgt"] * 1000 * x                    # £/kW/yr x kW
    new_running = 0.0
    for (slo, shi, p, v) in strips:
        if p == "exist":
            continue
        new_running += v * _strip_energy(asc, slo, shi)
        if slo >= top:
            gw[p] += (shi - slo) / 1000
            new_fixed += fc[p] * 1000 * (shi - slo)
    derated = 1000 * (gw["ccgt"] * derating["ccgt"] + gw["ocgt"] * derating["ocgt"]) \
        + ce * derating["ccgt"] + existing_mw["single_cycle"] * derating["ocgt"]
    spare = max(0.0, peak * (1 + reserve_margin) - derated) / derating["ocgt"]
    new_fixed += fc["ocgt"] * 1000 * spare
    rent = new_payments - new_running
    return FleetA(new_baseload_gw=x / 1000, existing_ccgt_gw=ce / 1000, existing_lf=lf(x),
                  new_ccgt_gw=gw["ccgt"] - x / 1000, new_ocgt_gw=gw["ocgt"], spare_gw=spare / 1000,
                  energy_twh=energy / 1e6, energy_payments_gbp_m=price_sum / 1e6,
                  new_fixed_gbp_m=new_fixed / 1e6, new_plant_rent_gbp_m=rent / 1e6)
