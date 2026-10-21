"""Fleet B: an all-new gas fleet sized to residual demand, costed by screening curve (spec §3.2).

The load-duration curve is cut into horizontal strips of `step_mw`. A strip's running share
of the year is the share of half-hours in which residual demand reaches it. Each strip is
built as whichever of OCGT or CCGT is cheaper at that running share and is costed at it:
fixed £/kW/yr x strip kW + variable £/MWh x strip MWh. Spare capacity (breakdowns plus
margin, see capacity.py) is added as OCGT that never runs (fixed cost only).

Gas transport (gastransport.py) enters as a fixed £/kW/yr adder (exit capacity) and a
variable £/MWh adder (commodity). Carbon is step 2, not here. Prices are Annex A 2024
money; the caller passes gas and transport in that money (deflator.rebase).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass

from .gastransport import GasTransport
from .official import Plant
from .plant import annualised_fixed_gbp_kw_yr, variable_gbp_mwh


@dataclass(frozen=True)
class FleetCost:
    ccgt_gw: float
    ocgt_gw: float
    reserve_gw: float
    energy_twh: float
    fixed_gbp_m: float
    variable_gbp_m: float

    @property
    def total_gbp_m(self) -> float:
        return self.fixed_gbp_m + self.variable_gbp_m

    @property
    def gbp_per_mwh(self) -> float:
        return self.total_gbp_m / self.energy_twh


def cost_fleet_b(ldc_mw: list[float], gas_gbp_mwh: float, ccgt: Plant, ocgt: Plant,
                 reserve_margin: float, step_mw: float = 50.0, hurdle: str = "medium",
                 derating: dict[str, float] | None = None,
                 transport: GasTransport | None = None) -> FleetCost:
    """ldc_mw: residual demand per half-hour, sorted high to low (one year).

    Security rule: de-rated capacity (installed x de-rating factor) must reach
    peak x (1 + reserve_margin). The running fleet's de-rated capacity is counted; any
    shortfall is bought as OCGT that never runs (fixed cost only). derating=None means
    no breakdowns (factors of 1), used only in tests."""
    drf = derating or {"ccgt": 1.0, "ocgt": 1.0}
    n = len(ldc_mw)
    hours = n / 2
    plants = {"ccgt": ccgt, "ocgt": ocgt}
    tf = {q: transport.fixed_gbp_kw_e_yr(p.efficiency_gcv) if transport else 0.0 for q, p in plants.items()}
    tv = transport.commodity_gbp_mwh_gas if transport else 0.0
    fc = {q: annualised_fixed_gbp_kw_yr(p, hurdle=hurdle) + tf[q] for q, p in plants.items()}
    vc = {q: variable_gbp_mwh(p, gas_gbp_mwh, tv) for q, p in plants.items()}
    asc = sorted(ldc_mw)
    peak = asc[-1]
    gw = {"ccgt": 0.0, "ocgt": 0.0}
    fixed = var = energy = 0.0
    lo = 0.0

    while lo < peak:
        hi = min(lo + step_mw, peak)
        mid = (lo + hi) / 2
        share = (n - bisect.bisect_left(asc, mid)) / n      # running share of the year
        mw = hi - lo
        mwh = mw * share * hours
        p = min(("ccgt", "ocgt"), key=lambda q: fc[q] * 1000 * mw + vc[q] * mwh)
        gw[p] += mw / 1000
        fixed += fc[p] * 1000 * mw
        var += vc[p] * mwh
        energy += mwh
        lo = hi
    derated_mw = 1000 * (gw["ccgt"] * drf["ccgt"] + gw["ocgt"] * drf["ocgt"])
    reserve_mw = max(0.0, peak * (1 + reserve_margin) - derated_mw) / drf["ocgt"]
    fixed += fc["ocgt"] * 1000 * reserve_mw
    return FleetCost(ccgt_gw=gw["ccgt"], ocgt_gw=gw["ocgt"], reserve_gw=reserve_mw / 1000,
                     energy_twh=energy / 1e6, fixed_gbp_m=fixed / 1e6, variable_gbp_m=var / 1e6)
