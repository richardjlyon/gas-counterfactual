"""Validation of the gas world (spec §8), and fleet A's gas-market margin.

In half-hours when gas sets the price, the day-ahead price (Elexon MID, APX) is compared
with the short-run cost of the existing gas fleet:

    cost = SAP / eta + carbon(allowance, CPS) + variable O&M

eta is the DUKES 5.10.C CCGT fleet efficiency for that year (latest year carried forward).
'Gas sets the price' is a stated proxy, not a claim about the merit order: CCGT output at
or above `min_ccgt_mw` and coal below `max_coal_mw`. Sensitivity to the thresholds is
reported, not hidden.

Outputs per year: half-hours used, median and quartiles of the spread (price - cost), and
the implied efficiency SAP / (price - carbon - VOM).
"""
from __future__ import annotations

import statistics as st
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .carbon import CO2_T_PER_MWH_GAS_GCV, allowance_monthly_gbp, cps_gbp_per_mwh_gas
from .mid import read_mid
from .official import read_dukes_510
from .residual import read_fuelhh
from .sap import sap_gbp_per_mwh

RAW = Path(__file__).parents[2] / "data/raw"
VOM_GBP_MWH = 5.0   # DESNZ EGC 2025 Annex A, CCGT variable O&M, 2024 prices


def gas_day(d: date, period: int) -> date:
    """Gas day runs 05:00 to 05:00 UK time; settlement period p starts at (p-1) x 30 min."""
    start = datetime(d.year, d.month, d.day) + timedelta(minutes=30 * (period - 1))
    return (start - timedelta(hours=5)).date()


@dataclass(frozen=True)
class YearCheck:
    year: int
    n: int
    coverage: float           # share of the year's half-hours with all inputs
    spread_median: float      # £/MWh, price - cost
    spread_q1: float
    spread_q3: float
    implied_eta_median: float
    eta_dukes: float


def validate_year(year: int, min_ccgt_mw: float = 10_000, max_coal_mw: float = 1_000) -> YearCheck:
    sap = sap_gbp_per_mwh()
    allow = allowance_monthly_gbp(RAW)
    dukes = read_dukes_510(RAW / "DUKES_5.10.xlsx").ccgt_efficiency
    eta = dukes.get(year, dukes[max(dukes)]) / 100
    mid, fuel = read_mid(year), read_fuelhh(year)
    spreads, etas = [], []
    total = 0
    for k, g in fuel.items():
        total += 1
        if k not in mid:
            continue
        price, vol = mid[k]
        if vol <= 0 or g.get("CCGT", 0) < min_ccgt_mw or g.get("COAL", 0) >= max_coal_mw:
            continue
        gd = gas_day(*k)
        if gd not in sap:
            continue
        a = allow.get((k[0].year, k[0].month))
        if a is None:
            continue
        carbon_per_mwh_gas = a[0] * CO2_T_PER_MWH_GAS_GCV + cps_gbp_per_mwh_gas(k[0])
        cost = (sap[gd] + carbon_per_mwh_gas) / eta + VOM_GBP_MWH
        spreads.append(price - cost)
        net = price - VOM_GBP_MWH
        if net > 0:
            etas.append((sap[gd] + carbon_per_mwh_gas) / net)
    q = st.quantiles(spreads, n=4)
    return YearCheck(year=year, n=len(spreads), coverage=len(spreads) / total,
                     spread_median=st.median(spreads), spread_q1=q[0], spread_q3=q[2],
                     implied_eta_median=st.median(etas), eta_dukes=eta)
