"""RB v1.1 M7 (decision 0163, R8 (a)): carbon out of the price at the marginal plant's intensity from 1 Jan 2009.

A switch, OFF by default. The chief-executive (card [internal ticket], 21 Oct 2026) asked for both readings of
"the marginal plant" to be built and measured so that Richard can rule between them; until he does, the
central case keeps gas intensity in every month. Set the environment variable GASCF_M7_CARBON_MARGINAL:

- "gas" (default to v4-s38): carbon out at gas intensity in every month (`carbon.c_marg_monthly`), as v4-s37.
- "merit" (option b; the v4-s39 central default, decision 0167): from Jan 2009, each half-hour's marginal plant is the top running block of the
  engine's own merit order of the plant the actual system had (DUKES 5.10/5.11 fleet, de-rated as
  `fossil_like_for_like.existing_plant`), on the actual fossil load (residual less transmission renewables
  and embedded output, less hydro, as `lfl_year`'s g0 walk), with the month's carbon price (allowance and
  CPS) added to each block's running cost. The month's coal share is the share of its half-hours with coal
  on top (a time share, because the price it is taken from is the month's time-mean baseload price). Oil on
  top (rare: 1.2% of 2009's half-hours, under 1% after) is counted at gas intensity, as today.
- "neso_regression" (option a): from Jan 2009, each year's marginal emission factor from NESO's historic
  generation mix (the engine's saved copy): the least-squares slope of the half-hour change in fossil CO2
  (gas and coal output at their intensities) on the half-hour change in fossil output, over adjacent
  half-hours only (Hawkes 2010's method), read as a coal weight (MEF - gas) / (coal - gas). Applied to
  every month of the year.

Carbon on a coal MWh: (allowance x HMRC's coal factor + CPS on coal) / DUKES 5.10.C coal efficiency
(`carbon.c_marg_coal_gbp_per_mwh_elec`). On a gas MWh: as `carbon.c_marg_gbp_per_mwh_elec` at the CCGT
fleet efficiency. Before 2009 every option is gas intensity (no free half-hourly fuel data).
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from functools import lru_cache

from gascf import carbon

ENV = "GASCF_M7_CARBON_MARGINAL"
METHODS = ("gas", "merit", "neso_regression")
# v4-s39 central (card [internal ticket]; decision 0167, Richard Lyon 22 Oct 2026: "A", the merit order). "gas" = v4-s38.
DEFAULT = "merit"
MARGINAL_FROM = date(2009, 1, 1)
YEARS_FROM = MARGINAL_FROM.year
GAS_BLOCKS = ("ccgt", "other_gas")
SRC = {"merit": "m7-merit-order-with-carbon", "neso_regression": "m7-neso-mix-regression+neso-historic-generation-mix-df_fuel_ckan"}


def method() -> str:
    m = os.environ.get(ENV, DEFAULT) or DEFAULT
    if m not in METHODS:
        raise ValueError(f"{ENV}={m!r}: one of {METHODS}")
    return m


def blended_c_marg(allowance_gbp_t: float, d: date, eta_coal: float, eta_gas: float, coal_share: float) -> float:
    """£/MWh of electricity: coal_share x carbon on a coal MWh + (1 - coal_share) x carbon on a gas MWh."""
    g = carbon.c_marg_gbp_per_mwh_elec(allowance_gbp_t, d, eta_gas)
    if coal_share == 0.0:
        return g
    c = carbon.c_marg_coal_gbp_per_mwh_elec(allowance_gbp_t, d, eta_coal)
    return coal_share * c + (1.0 - coal_share) * g


# ------------------------------------------------------------------ option (a): regression on the NESO mix

def _adjacent(k0, k1) -> bool:
    (d0, p0), (d1, p1) = k0, k1
    return (d1 == d0 and p1 == p0 + 1) or (d1 == d0 + timedelta(days=1) and p1 == 1)


def regression_coal_weight(mix: dict, i_gas: float, i_coal: float) -> float:
    """Coal weight at the margin from {(day, period): {"GAS": MW, "COAL": MW}}, adjacent half-hours only."""
    ks = sorted(mix)
    n = sx = sy = sxx = sxy = 0.0
    for k0, k1 in zip(ks, ks[1:]):
        if not _adjacent(k0, k1):
            continue
        dg = mix[k1]["GAS"] - mix[k0]["GAS"]
        dc = mix[k1]["COAL"] - mix[k0]["COAL"]
        x, e = dg + dc, i_gas * dg + i_coal * dc
        n += 1; sx += x; sy += e; sxx += x * x; sxy += x * e
    den = n * sxx - sx * sx
    if n < 2 or den == 0:
        raise ValueError("regression_coal_weight: no movement in the fossil output")
    mef = (n * sxy - sx * sy) / den
    return (mef - i_gas) / (i_coal - i_gas)


# ------------------------------------------------------------------ option (b): merit order with carbon

def stack_with_carbon(stack, adders: dict) -> list:
    """(name, MW, SRMC) blocks with each block's carbon £/MWh added, re-sorted cheapest first."""
    return sorted(((k, mw, c + adders.get(k, 0.0)) for k, mw, c in stack), key=lambda x: x[2])


def marginal_block(stack, load_mw: float):
    """Top running block when `load_mw` is served from `stack` cheapest first (None at zero load)."""
    from gascf.fossil_like_for_like import _walk
    if load_mw <= 0:
        return None
    _, _, g = _walk(stack, load_mw)
    return list(g)[-1] if g else None


def _adders(y: int, m: int, allowance: float) -> dict:
    from gascf import fossil_like_for_like as L
    d = date(y, m, 1)
    gas_t = allowance * carbon.CO2_T_PER_MWH_GAS_GCV + carbon.cps_gas_or_zero(d)
    return {"coal": (allowance * carbon.co2_t_per_mwh_coal() + carbon.cps_gbp_per_mwh_coal(d)) / L._eta_dukes("coal", y),
            "ccgt": gas_t / L._eta_dukes("ccgt", y), "other_gas": gas_t / L.ETA_OTHER_GAS, "oil": 0.0}


@lru_cache(maxsize=None)
def _merit_year(y: int) -> dict:
    from gascf import bills as B, capacity
    from gascf import fossil_like_for_like as L
    from gascf import residual_neso as rn
    alw = carbon.allowance_monthly_v4(range(y, y + 1))
    rows = rn.residual_neso_year(y)
    keys = tuple((r.day, r.period) for r in rows)
    rtr, _ = L.renewables_trans_year(y, keys)
    H = L.hydro_year(y, keys)
    avail = L.existing_plant(y).derated(capacity.read_derating())
    tv = B.transport_for(y).commodity_gbp_mwh_gas
    st = {m: stack_with_carbon(L.stack_month(y, m, avail, tv), _adders(y, m, alw[(y, m)][0])) for m in range(1, 13)}
    n = {m: [0, 0, 0] for m in range(1, 13)}          # coal on top, oil on top, half-hours
    for r, h, t in zip(rows, H, rtr):
        f = max(0.0, max(0.0, r.residual) - t - r.embedded)
        top = marginal_block(st[r.day.month], max(0.0, f - h))
        c = n[r.day.month]
        c[0] += top == "coal"
        c[1] += top == "oil"
        c[2] += 1
    return {m: {"coal": c[0] / c[2] if c[2] else 0.0, "oil": c[1] / c[2] if c[2] else 0.0} for m, c in n.items()}


@lru_cache(maxsize=None)
def _regression_year(y: int) -> float:
    from gascf import fossil_like_for_like as L
    ig = carbon.CO2_T_PER_MWH_GAS_GCV / L._eta_dukes("ccgt", y)
    ic = carbon.co2_t_per_mwh_coal() / L._eta_dukes("coal", y)
    mix = L.neso_mix_year(y)
    if not mix:
        raise ValueError(f"M7 neso_regression: no NESO mix rows for {y}")
    w = regression_coal_weight(mix, ig, ic)
    if not 0.0 <= w <= 1.0:
        # outside the two intensities: never clipped silently (a method question for Richard)
        raise ValueError(f"M7 neso_regression: {y} coal weight {w:.3f} outside [0, 1]")
    return w


def coal_share(y: int, m: int, meth: str) -> float:
    if meth == "gas" or (y, m) < (MARGINAL_FROM.year, MARGINAL_FROM.month):
        return 0.0
    if meth == "merit":
        return _merit_year(y)[m]["coal"]
    return _regression_year(y)


def c_marg_monthly(eta_ccgt: dict[int, float], years: range, meth: str | None = None) -> dict:
    """As `carbon.c_marg_monthly`, with carbon at the marginal plant's intensity from Jan 2009 under `meth`."""
    from gascf import fossil_like_for_like as L
    meth = meth or method()
    base = carbon.c_marg_monthly(eta_ccgt, years)
    if meth == "gas":
        return base
    out = {}
    for k, row in base.items():
        w = coal_share(k[0], k[1], meth)
        if k < (MARGINAL_FROM.year, MARGINAL_FROM.month):
            out[k] = {**row, "coal_marginal_share": 0.0, "m7_method": meth}
            continue
        v = blended_c_marg(row["allowance_gbp_t"], date(k[0], k[1], 1), L._eta_dukes("coal", k[0]),
                           eta_ccgt[k[0]] / 100, w) if w else row["gbp_per_mwh"]
        out[k] = {**row, "gbp_per_mwh": v, "coal_marginal_share": w, "m7_method": meth,
                  "source_id": f"{row['source_id']}+{SRC[meth]}"}
    return out


def run_meta() -> dict:
    """Run-file record of the switch: method, break date, and the coal share by year (0 under 'gas')."""
    meth = method()
    by = {}
    for y in range(YEARS_FROM, 2026):
        if meth == "gas":
            by[str(y)] = 0.0
        elif meth == "merit":
            by[str(y)] = sum(_merit_year(y)[m]["coal"] for m in range(1, 13)) / 12
        else:
            by[str(y)] = _regression_year(y)
    return {"method": meth, "switch_env": ENV, "default": DEFAULT, "marginal_from": MARGINAL_FROM.isoformat(),
            "before": "gas intensity", "coal_marginal_share_by_year": by,
            "status": "central in v4-s39, as ruled in decision 0167 (M7 'A': the merit order); 'gas' reproduces v4-s38"}
