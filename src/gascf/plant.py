"""Plant cost arithmetic for the screening curve (spec draft 3, §3.2).

DESNZ levelises by discounting costs and generation at the hurdle rate over a
pre-development, construction and operating timeline. Here the same timeline gives
an annualised fixed cost in £/kW/yr, so each load-duration slice can be priced at
its own running hours: cost per MWh = fixed / (8.76 x LF) + variable.
"""
from __future__ import annotations

from .official import Plant


def _pv_factors(p: Plant, r: float):
    n_pre, n_con = len(p.predev_phasing), len(p.construction_phasing)
    start = n_pre + n_con
    ops = sum(1 / (1 + r) ** (start + y) for y in range(p.life_years))
    return n_pre, ops


def annualised_fixed_gbp_kw_yr(p: Plant, case: str = "medium", hurdle: str = "medium") -> float:
    """Capital (pre-development + construction + infrastructure) as an annuity over the
    operating life, plus fixed O&M, insurance, connection and use-of-system charges."""
    r = p.hurdle[hurdle]
    n_pre, ops = _pv_factors(p, r)
    pv = sum(p.predev_gbp_kw[case] * s / (1 + r) ** k for k, s in enumerate(p.predev_phasing))
    capex = p.construction_gbp_kw[case] + p.infrastructure_gbp_k[case] / p.size_mw
    pv += sum(capex * s / (1 + r) ** (n_pre + k) for k, s in enumerate(p.construction_phasing))
    capital = pv / ops
    fixed = (p.fixed_om_gbp_mw_yr + p.insurance_gbp_mw_yr + p.connection_uos_gbp_mw_yr) / 1000
    return capital + fixed


def levelised_capital_gbp_mwh(p: Plant, load_factor: float | None = None, case: str = "medium",
                              hurdle: str = "medium") -> tuple[float, float]:
    """(pre-development, construction incl. infrastructure) in £/MWh, DESNZ's two rows."""
    lf = p.net_load_factor if load_factor is None else load_factor
    r = p.hurdle[hurdle]
    n_pre, ops = _pv_factors(p, r)
    gen = 8.76 * lf * ops            # MWh per kW, discounted
    pre = sum(p.predev_gbp_kw[case] * s / (1 + r) ** k for k, s in enumerate(p.predev_phasing))
    capex = p.construction_gbp_kw[case] + p.infrastructure_gbp_k[case] / p.size_mw
    con = sum(capex * s / (1 + r) ** (n_pre + k) for k, s in enumerate(p.construction_phasing))
    return pre / gen, con / gen


def variable_gbp_mwh(p: Plant, gas_gbp_mwh_gcv: float, transport_gbp_mwh: float = 0.0) -> float:
    """Fuel (gross CV) + variable O&M + gas transport commodity. No carbon (that is step 2)."""
    return (gas_gbp_mwh_gcv + transport_gbp_mwh) / p.efficiency_gcv + p.variable_om_gbp_mwh


def crossover_load_factor(peaker: Plant, baseload: Plant, gas: float, **kw) -> float:
    """Running share of the year at which the two plants cost the same per kW."""
    f1, f2 = annualised_fixed_gbp_kw_yr(peaker, **kw), annualised_fixed_gbp_kw_yr(baseload, **kw)
    v1, v2 = variable_gbp_mwh(peaker, gas), variable_gbp_mwh(baseload, gas)
    return (f2 - f1) / (8.76 * (v1 - v2))
