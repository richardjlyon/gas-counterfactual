"""Break-even gas price (spec §9, output P4).

The question: at what wholesale gas price would what a household pays equal the pure gas
price, with both sides recomputed as gas moves?

**Actual side.** What the bill's wholesale line does when gas moves is read from Ofgem's own
history: the cap model's hard-coded electricity index E against its gas index G, 32 unique
cap periods since April 2015 (Annex 2 tab 1b), fitted as

    E = a + b x G,

by weighted least squares with each period weighted by its length in months (so a six-month
period counts twice a quarter). Slope and intercept are reported with 95% confidence
intervals (Student's t), with and without the Energy Price Guarantee periods
(Oct 2022 - Jun 2023). Weights are "analytic": the residual variance is
sum(w r^2) / (n - 2) with n the number of periods, so rescaling the weights changes nothing.
Plain-words glossary: the *slope* b is how many £/MWh of electricity one £/MWh of gas adds;
the *intercept* a is the electricity index the line implies at zero gas price.

**CfD paybacks are not done by the slope** (spec §9). A Contract for Difference (CfD) pays
the generator (strike price - market reference price) on each MWh. If wholesale power falls
by X £/MWh, suppliers pay X more on every CfD MWh, so the CfD line rises. Here that is
computed from LCCC's own unit-by-unit settlement data: the CfD volume share s = CfD
generation / CfD-eligible demand over the latest 12 months, and

    CfD(G) = CfD_observed - s x (E(G) - E(G_observed)).

Assumption (stated, `estimated`): reference prices move one-for-one with Ofgem's forward
electricity index. Strike prices are fixed over the year; the formula needs only volumes.

**All-gas side.** Pure gas cost of power from fleet A or B (fleeta / fleetb) on the 2025
residual-demand load curve, at the trial gas price, through the same Ofgem uplift and
GB-average losses as the actual side (spec §5).

**What else is in the gap, held fixed as gas moves.** Policy lines that are zero in all-gas
Britain (RO, FiT, WHD, AAHEDC, EII levy, Sizewell C, and from April 2026 the RO paid by the
Treasury), and the renewables-driven grid lines (constraint difference, offshore
transmission demand share). Lines held equal on both sides cancel. Supplier percentage lines
and VAT are proportional to the bill on both sides, so they scale the gap but cannot change
its sign, and are left out of the break-even (stated in the output).

Result: the break-even is the gas price G* at which

    gap(G) = UL x (E(G) - F(G)) + fixed lines + CfD_observed - s x (E(G) - E(G_observed)) = 0,

where the fixed lines include the CfD allowance at the observed gas price (all-gas side 0),
found for the central fit and for both edges of its 95% band, reported as a range, or as
"none below £X" if the gap stays positive up to the search ceiling.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Callable

from .ofgem import CapPeriod, REGIONS, read_annex2, unique_periods

ROOT = Path(__file__).parents[2]
RAW = ROOT / "data/raw"
ANNEX2 = ROOT / "research/2026-10-10-methods/src/Annex-2-wholesale-cost-allowance-methodology-v1.30_data_removed-2.xlsx"
LCCC_GEN = RAW / "lccc/actual_cfd_generation.csv"
LCCC_ILR = RAW / "lccc/actual_ilr_income.csv"

SRC_ANNEX2 = "ofgem-annex2-v1.30"
SRC_CFD_GEN = "lccc-actual-cfd-generation"
SRC_ILR = "lccc-actual-ilr-income"

# Energy Price Guarantee periods (cap periods starting Oct 2022, Jan 2023, Apr 2023)
EPG_STARTS = {(2022, 10), (2023, 1), (2023, 4)}

GEN_COLS = ["Settlement_Date", "CfD_ID", "Name_of_CfD_Unit", "Technology", "Allocation_round",
            "Reference_Type", "CFD_Generation_MWh", "Avoided_GHG_tonnes_CO2e",
            "Strike_Price_GBP_Per_MWh", "CFD_Payments_GBP", "Avoided_GHG_Cost_GBP",
            "Market_Reference_Price_GBP_Per_MWh", "Weighted_IMRP_GBP_Per_MWh"]
ILR_COLS = ["Settlement_Date", "Actual_Eligible_Demand_MWh", "Actual_EII_Excluded_Electricity_MWh",
            "Actual_Gross_Demand_MWh", "Actual_ILR_GBP_Per_MWh", "Actual_Income_GBP"]


# ------------------------------------------------------------------ statistics (stdlib only)

def t_quantile(p: float, df: int) -> float:
    """Quantile of Student's t distribution (two-sided 95% uses p = 0.975).

    The density is integrated by Simpson's rule and the quantile found by bisection;
    accurate to better than 1e-8, which is far below anything reported."""
    if not 0.5 <= p < 1:
        raise ValueError("p must be in [0.5, 1)")
    c = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)

    def cdf(t: float) -> float:
        n = 4000
        h = t / n
        f = lambda x: c * (1 + x * x / df) ** (-(df + 1) / 2)
        s = f(0) + f(t) + sum((4 if k % 2 else 2) * f(k * h) for k in range(1, n))
        return 0.5 + s * h / 3

    lo, hi = 0.0, 50.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) < p else (lo, mid)
    return (lo + hi) / 2


@dataclass(frozen=True)
class Fit:
    """E = a + b x G, weighted least squares, with its uncertainty."""
    label: str
    a: float
    b: float
    var_a: float
    var_b: float
    cov_ab: float
    n: int
    sigma2: float          # weighted residual variance, sum(w r^2) / (n - 2)
    t95: float             # Student's t, 97.5th percentile, n - 2 degrees of freedom
    periods: tuple[str, ...]
    weights: tuple[float, ...]
    source_id: str = SRC_ANNEX2
    basis: str = "modelled"

    @property
    def se_a(self) -> float:
        return math.sqrt(self.var_a)

    @property
    def se_b(self) -> float:
        return math.sqrt(self.var_b)

    @property
    def a_ci(self) -> tuple[float, float]:
        return self.a - self.t95 * self.se_a, self.a + self.t95 * self.se_a

    @property
    def b_ci(self) -> tuple[float, float]:
        return self.b - self.t95 * self.se_b, self.b + self.t95 * self.se_b

    def mean(self, g: float) -> float:
        return self.a + self.b * g

    def band(self, g: float) -> tuple[float, float]:
        """95% confidence band for the fitted line at gas price g (the mean, not a new period)."""
        se = math.sqrt(self.var_a + g * g * self.var_b + 2 * g * self.cov_ab)
        m = self.mean(g)
        return m - self.t95 * se, m + self.t95 * se


def wls(x: list[float], y: list[float], w: list[float]) -> tuple[float, float, float, float, float, float]:
    """(a, b, var_a, var_b, cov_ab, sigma2) for y = a + b x, weights w.

    Normal equations solved by the 2x2 inverse of X'WX; sigma2 = sum(w r^2)/(n-2)."""
    n = len(x)
    if n < 3 or not (len(y) == len(w) == n):
        raise ValueError("need at least 3 points and equal lengths")
    s0 = sum(w)
    s1 = sum(wi * xi for wi, xi in zip(w, x))
    s2 = sum(wi * xi * xi for wi, xi in zip(w, x))
    t0 = sum(wi * yi for wi, yi in zip(w, y))
    t1 = sum(wi * xi * yi for wi, xi, yi in zip(w, x, y))
    det = s0 * s2 - s1 * s1
    a = (s2 * t0 - s1 * t1) / det
    b = (s0 * t1 - s1 * t0) / det
    sigma2 = sum(wi * (yi - a - b * xi) ** 2 for wi, xi, yi in zip(w, x, y)) / (n - 2)
    return a, b, sigma2 * s2 / det, sigma2 * s0 / det, -sigma2 * s1 / det, sigma2


@lru_cache(maxsize=1)
def cap_periods(path: Path = ANNEX2) -> tuple[CapPeriod, ...]:
    ps = tuple(unique_periods(read_annex2(path)))
    if len(ps) != 32:
        raise ValueError(f"expected 32 unique cap periods, found {len(ps)}")
    return ps


def _start(p: CapPeriod) -> tuple[int, int]:
    from .receipt_actual import period_key
    y1, m1, _, _ = period_key(p.name)
    return y1, m1


def is_epg(p: CapPeriod) -> bool:
    return _start(p) in EPG_STARTS


def fit_cap_periods(exclude_epg: bool = False, periods: tuple[CapPeriod, ...] | None = None) -> Fit:
    ps = [p for p in (periods or cap_periods()) if not (exclude_epg and is_epg(p))]
    x = [p.gas_index for p in ps]
    y = [p.elec_index for p in ps]
    w = [float(p.months) for p in ps]
    a, b, va, vb, cab, s2 = wls(x, y, w)
    label = "32 cap periods, Apr 2015 - Dec 2026" if not exclude_epg else \
        "29 cap periods, excluding Oct 2022 - Jun 2023 (Energy Price Guarantee)"
    return Fit(label=label, a=a, b=b, var_a=va, var_b=vb, cov_ab=cab, n=len(ps), sigma2=s2,
               t95=t_quantile(0.975, len(ps) - 2), periods=tuple(p.name for p in ps),
               weights=tuple(w))


# ------------------------------------------------------------------ CfD volumes (LCCC)

@dataclass(frozen=True)
class CfdVolume:
    start: date
    end: date
    generation_mwh: float
    payments_gbp: float
    eligible_demand_mwh: float
    days: int
    by_technology: dict[str, float] = field(default_factory=dict)

    @property
    def share(self) -> float:
        """CfD generation per MWh of CfD-eligible demand."""
        return self.generation_mwh / self.eligible_demand_mwh


def _check(path: Path, want: list[str]) -> csv.DictReader:
    fh = path.open(newline="")
    rd = csv.DictReader(fh)
    if rd.fieldnames != want:
        raise ValueError(f"LCCC layout moved in {path.name}: {rd.fieldnames}")
    return rd


@lru_cache(maxsize=4)
def cfd_volume(end: date | None = None, days: int = 365) -> CfdVolume:
    """CfD generation and eligible demand over the `days` days ending `end`
    (default: the last day both LCCC files cover). Fails if any day is missing."""
    gen: dict[date, float] = {}
    pay: dict[date, float] = {}
    tech: dict[str, float] = {}
    rows = list(_check(LCCC_GEN, GEN_COLS))
    dem: dict[date, float] = {}
    for r in _check(LCCC_ILR, ILR_COLS):
        dem[date.fromisoformat(r["Settlement_Date"][:10])] = float(r["Actual_Eligible_Demand_MWh"])
    last = end or min(max(dem), max(date.fromisoformat(r["Settlement_Date"][:10]) for r in rows))
    first = last - timedelta(days=days - 1)
    for r in rows:
        d = date.fromisoformat(r["Settlement_Date"][:10])
        if first <= d <= last:
            g = float(r["CFD_Generation_MWh"])
            gen[d] = gen.get(d, 0.0) + g
            pay[d] = pay.get(d, 0.0) + float(r["CFD_Payments_GBP"])
            tech[r["Technology"]] = tech.get(r["Technology"], 0.0) + g
    want = {first + timedelta(days=k) for k in range(days)}
    if want - set(gen) or want - set(dem):
        raise ValueError(f"LCCC data missing days in {first}..{last}")
    return CfdVolume(first, last, sum(gen.values()), sum(pay.values()),
                     sum(dem[d] for d in want), days, tech)


# ------------------------------------------------------------------ the gap model

@dataclass(frozen=True)
class GapLine:
    key: str
    gbp_per_mwh: float      # actual minus all-gas, £ per MWh supplied, held fixed as gas moves
    step: str
    basis: str
    source_id: str
    note: str = ""


@dataclass(frozen=True)
class GapModel:
    """One cap period's bill, reduced to what moves with gas and what does not."""
    period: str
    uplift_losses: float        # Ofgem uplift x GB-average losses: £/MWh supplied per £/MWh index
    gas_observed: float         # Ofgem gas index for the period
    elec_observed: float        # Ofgem electricity index for the period
    cfd_share: CfdVolume | None
    fixed: tuple[GapLine, ...]
    excluded: tuple[str, ...]

    @property
    def fixed_total(self) -> float:
        return sum(ln.gbp_per_mwh for ln in self.fixed)

    def gap(self, g: float, elec_fn: Callable[[float], float], gas_cost_fn: Callable[[float], float],
            elec_at_observed: float | None = None) -> float:
        """What you pay minus the pure gas price, £/MWh supplied, at gas price g.

        elec_fn: actual electricity index as a function of gas (the fit or a band edge).
        gas_cost_fn: fleet pure gas cost of power, £/MWh at transmission."""
        e = elec_fn(g)
        e0 = elec_fn(self.gas_observed) if elec_at_observed is None else elec_at_observed
        cfd_move = -self.cfd_share.share * (e - e0) if self.cfd_share else 0.0
        return self.uplift_losses * (e - gas_cost_fn(g)) + self.fixed_total + cfd_move


def gap_model(period: str = "October 2026 - December 2026", fleet: str = "A",
              cfd_window_end: date | None = None) -> GapModel:
    """Build the gap model for a cap period at the site's 2,500 kWh.

    Fixed lines (actual minus all-gas, per MWh supplied):
      step 3 WHD, AAHEDC, EII levy, Sizewell C (all-gas 0);
      step 4(a) RO bill share, FiT, CfD allowance at the observed gas price (all-gas 0);
      RO paid by the Treasury from April 2026;
      step 4(b) constraint difference (latest complete NESO financial year, period's money)
                and OFTO demand share (estimated).
    The CfD line's movement with the wholesale price is added in GapModel.gap.
    """
    from .receipt_actual import at_consumption, period_key
    from .system_costs import constraint_per_household, ofto_demand_share, read_constraint_breakdown

    p = next(q for q in cap_periods() if q.name == period)
    ul = sum(p.supplied[r] for r in REGIONS) / len(REGIONS) / p.elec_index
    key = period_key(period)
    rc = at_consumption(key, 2500)
    mwh = 2.5
    lines: list[GapLine] = []
    for k, step in (("whd", "3"), ("aahedc", "3"), ("eii_levy", "3"), ("sizewell_c", "3"),
                    ("ro", "4a"), ("fit", "4a"), ("cfd", "4a")):
        ln = rc.line(k)
        lines.append(GapLine(k, ln.typical / mwh, step, ln.basis, ln.source_id,
                             "all-gas Britain: 0" + ("; level at the observed gas price, moves "
                                                     "with wholesale via GapModel.gap" if k == "cfd" else "")))
    if key[:2] >= (2026, 4):
        from .taxes import ro_treasury
        t = ro_treasury(period)["ro_treasury_mwh"]
        lines.append(GapLine("ro_treasury", t.value, "4a", t.basis, t.source_id,
                             "Layer 2: RO paid by the Treasury, all-gas 0"))
    years = read_constraint_breakdown()
    fy = max(y for y, c in years.items() if c.complete)
    c = constraint_per_household(fy, price_year=key[0])["difference_per_2500kwh"]
    lines.append(GapLine("constraints", c.value / mwh, "4b", c.basis, c.source_id,
                         f"NESO FY {fy}/{(fy + 1) % 100:02d} (latest complete), {key[0]} prices"))
    o = ofto_demand_share(fy)["per_household"]
    lines.append(GapLine("ofto", o.value / mwh, "4b", o.basis, o.source_id,
                         "per domestic site (Table B), spread over 2.5 MWh: estimated"))
    excluded = [
        "capacity_market: held equal (fleet A rule, spec §3.3)" if fleet == "A" else
        "capacity_market: UNSOURCED for fleet B (CM register by technology not yet read); held "
        "equal on both sides; its direction on the gap is not established",
        "supplier percentage lines (headroom, EBIT, bad debt) and VAT: proportional on both sides; "
        "they scale the gap but cannot change its sign, so they do not move the break-even",
        "networks, operating costs, smart meter, industry charges, backwardation, levelisation: "
        "held equal, cancel",
    ]
    return GapModel(period=p.name, uplift_losses=ul, gas_observed=p.gas_index, elec_observed=p.elec_index,
                    cfd_share=cfd_volume(cfd_window_end), fixed=tuple(lines), excluded=tuple(excluded))


# ------------------------------------------------------------------ root finding

@dataclass(frozen=True)
class BreakEven:
    """Where the gap (what you pay - pure gas price) crosses zero.

    direction: 'gas_cheaper_below' means the pure gas price is below what you pay at gas
    prices under the root and above it over the root; 'gas_cheaper_above' the reverse."""
    label: str
    gas_gbp_mwh: float | None      # first root in [floor, ceiling], or None
    none_below: float | None       # ceiling, when there is no root up to it
    direction: str = ""
    gap_at_floor: float = float("nan")
    gap_at_ceiling: float = float("nan")

    def text(self) -> str:
        if self.gas_gbp_mwh is not None:
            return f"£{self.gas_gbp_mwh:.2f}/MWh ({self.direction.replace('_', ' ')})"
        sign = "what you pay is higher" if self.gap_at_floor > 0 else "pure gas is dearer"
        return f"none below £{self.none_below:.0f}/MWh ({sign} throughout)"


def solve(f: Callable[[float], float], lo: float = 0.0, hi: float = 300.0, step: float = 2.0,
          label: str = "") -> BreakEven:
    """Lowest gas price in [lo, hi] where f changes sign, by a 2 £/MWh grid then bisection
    to 1e-9. f is the gap, what you pay - pure gas price, £/MWh."""
    f_lo = f(lo)
    g, fg = lo, f_lo
    while g < hi:
        g2 = min(g + step, hi)
        f2 = f(g2)
        if (fg > 0) != (f2 > 0):
            pos_left = fg > 0
            a, b = g, g2
            for _ in range(60):
                m = (a + b) / 2
                a, b = (m, b) if (f(m) > 0) == pos_left else (a, m)
            return BreakEven(label, (a + b) / 2, None,
                             "gas_cheaper_below" if pos_left else "gas_cheaper_above", f_lo, f(hi))
        g, fg = g2, f2
    return BreakEven(label, None, hi, "", f_lo, fg)


# ------------------------------------------------------------------ fleet cost as a function of gas

def fleet_cost_fn(fleet: str = "A", ldc_year: int = 2025, money_year: int = 2026,
                  margin: str = "central") -> Callable[[float], float]:
    """Pure gas cost of power, £/MWh at transmission in `money_year` prices, as a function of
    the gas price (£/MWh gross CV, same money). No carbon (step 2).

    Fleet A: existing GB CCGT at DUKES fleet efficiency for ldc_year, CEPA/GHD variable O&M,
    §8 gas-market margin for ldc_year (median; 'low' = lower quartile, 'high' = upper),
    topped up by screening curve. Fleet B: all new, DESNZ EGC 2025 Annex A.
    Both: ECR 2026 central spare margin and de-rating; National Gas 2026/27 transport.
    Plant costs are 2024 money: gas goes in rebased to 2024, the result comes out rebased
    to money_year (HMT GDP deflator)."""
    from .capacity import margin_fraction, read_derating
    from .deflator import rebase
    from .fleeta import cost_fleet_a, read_existing_gb_gas
    from .fleetb import cost_fleet_b
    from .gastransport import GasTransport, read_transport
    from .official import read_desnz_plants, read_dukes_510
    from .residual import load_duration, residual_year
    from .today import cepa_vom_existing

    pl = read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")
    ccgt, ocgt = pl[("Gas CCGT 93% Load Factor", 2030)], pl[("Gas OCGT 760MW 30% Load Factor", 2030)]
    rows, _ = residual_year(ldc_year)
    ldc = load_duration(rows)
    m, d = margin_fraction("central"), read_derating()
    t = read_transport()["2026/27"]
    k = rebase(1.0, 2026, 2024)
    t24 = GasTransport(t.gas_year, t.exit_capacity_p_kwh_day * k, t.commodity_p_kwh * k)
    to24 = rebase(1.0, money_year, 2024)
    back = rebase(1.0, 2024, money_year)
    cache: dict[float, float] = {}
    if fleet == "A":
        from .validate import validate_year
        dukes = read_dukes_510(RAW / "DUKES_5.10.xlsx").ccgt_efficiency
        eta = dukes.get(ldc_year, dukes[max(dukes)]) / 100
        v = validate_year(ldc_year)
        mg = {"central": v.spread_median, "low": v.spread_q1, "high": v.spread_q3}[margin]
        mg24 = rebase(mg, ldc_year, 2024)
        vom = cepa_vom_existing()
        ex = read_existing_gb_gas()

        def f(g: float) -> float:
            if g not in cache:
                cache[g] = cost_fleet_a(ldc, g * to24, eta, vom, mg24, ex, ccgt, ocgt, m, d,
                                        transport=t24).gbp_per_mwh * back
            return cache[g]
    elif fleet == "B":
        def f(g: float) -> float:
            if g not in cache:
                cache[g] = cost_fleet_b(ldc, g * to24, ccgt, ocgt, m, derating=d,
                                        transport=t24).gbp_per_mwh * back
            return cache[g]
    else:
        raise ValueError(fleet)
    return f


def break_even(fleet_cost: Callable[[float], float], model: GapModel, fit: Fit,
               ceiling: float = 300.0, anchored: bool = False,
               wholesale_only: bool = False) -> dict[str, BreakEven]:
    """Break-even on the central fit and on both edges of its 95% confidence interval.

    anchored=False: the fitted line E = a + bG and its 95% confidence band.
    anchored=True: the line through this period's observed point with the fitted slope,
      E = E_obs + b (G - G_obs), and with the slope at each end of its 95% interval. This
      keeps the actual side equal to Ofgem's allowance at today's gas price; only the slope
      comes from history.
    wholesale_only=True: drop the fixed policy and grid lines and the CfD movement; this is
      the gas price at which Ofgem's wholesale line alone meets the fleet cost (diagnostic).

    The CfD movement is measured from each curve's own value at the observed gas price,
    so at the observed price the CfD line equals Ofgem's allowance on every curve."""
    g0, e0 = model.gas_observed, model.elec_observed
    if anchored:
        lo_b, hi_b = fit.b_ci
        curves = {"central": lambda g: e0 + fit.b * (g - g0),
                  "band_low": lambda g: e0 + lo_b * (g - g0),
                  "band_high": lambda g: e0 + hi_b * (g - g0)}
    else:
        curves = {"central": fit.mean,
                  "band_low": lambda g: fit.band(g)[0],
                  "band_high": lambda g: fit.band(g)[1]}
    m = model if not wholesale_only else GapModel(model.period, model.uplift_losses, g0, e0, None, (), ())
    out = {}
    for name, e in curves.items():
        out[name] = solve(lambda g, e=e: m.gap(g, e, fleet_cost), 0.0, ceiling, label=name)
    return out


def feedback_threshold(fleet_cost: Callable[[float], float], model: GapModel,
                       drop_steps: tuple[str, ...] = ("3",), ceiling: float = 10.0,
                       carbon_gbp_mwh: float = 0.0) -> dict:
    """Spec §7.4 in threshold form: by what fraction k would the gas price in all-gas Britain
    have to rise (from the extra gas it burns) before the gap closes, the actual side staying
    at Ofgem's observed allowance? Lines in `drop_steps` are left out of the gap (default:
    step 3, other policy costs, which are not renewables). Carbon (step 2) is subtracted only
    if `carbon_gbp_mwh` (all-gas carbon, £/MWh at transmission) is given; it does not move
    with the gas price. Without it k is overstated.

    Returns k (0.25 = 25%), or None with the gap at k = ceiling."""
    fixed = sum(ln.gbp_per_mwh for ln in model.fixed if ln.step not in drop_steps)
    g0, e0, ul = model.gas_observed, model.elec_observed, model.uplift_losses
    f = lambda k: ul * (e0 - fleet_cost(g0 * (1 + k)) - carbon_gbp_mwh) + fixed
    r = solve(f, 0.0, ceiling, step=0.02, label="feedback")
    return {"k": r.gas_gbp_mwh, "gap_at_zero": r.gap_at_floor, "gap_at_ceiling": r.gap_at_ceiling,
            "dropped_steps": list(drop_steps), "carbon_subtracted_gbp_mwh": carbon_gbp_mwh}


def gap_profile(fleet_cost: Callable[[float], float], model: GapModel, e: Callable[[float], float],
                lo: float = 0.0, hi: float = 300.0, step: float = 2.0) -> dict:
    """Smallest gap on the grid, where it falls, and the gap at the observed gas price."""
    grid = [lo + step * k for k in range(int((hi - lo) / step) + 1)]
    vals = [(model.gap(g, e, fleet_cost), g) for g in grid]
    mn = min(vals)
    return {"min_gap_gbp_mwh": mn[0], "at_gas": mn[1],
            "gap_at_observed": model.gap(model.gas_observed, e, fleet_cost)}


def p4(period: str = "October 2026 - December 2026", ceiling: float = 300.0) -> dict:
    """Output P4: break-even for fleets A and B, fitted and anchored, with and without the
    Energy Price Guarantee periods; the overall range or 'none below £X'; diagnostics."""
    from datetime import date as _d

    from .carbon import allowance_monthly_gbp, carbon_gbp_per_mwh_elec
    from .official import read_dukes_510
    fits = {"all": fit_cap_periods(False), "ex_epg": fit_cap_periods(True)}
    out: dict = {"period": period, "ceiling_gbp_mwh": ceiling, "fits": {}, "fleets": {}}
    for k, f in fits.items():
        out["fits"][k] = {"label": f.label, "n": f.n, "a": f.a, "a_ci95": f.a_ci, "b": f.b,
                          "b_ci95": f.b_ci, "t95": f.t95, "basis": f.basis, "source_id": f.source_id}
    allow = allowance_monthly_gbp(RAW)
    m_last = max(allow)
    eta_a = read_dukes_510(RAW / "DUKES_5.10.xlsx").ccgt_efficiency[2025] / 100
    carbon_a = carbon_gbp_per_mwh_elec(allow[m_last][0], _d(2026, 10, 1), eta_a)
    for fleet in ("A", "B"):
        model = gap_model(period, fleet)
        fc = fleet_cost_fn(fleet)
        res, roots = {}, []
        g0, e0 = model.gas_observed, model.elec_observed
        for k, f in fits.items():
            for anchored in (False, True):
                r = break_even(fc, model, f, ceiling, anchored=anchored)
                w = break_even(fc, model, f, ceiling, anchored=anchored, wholesale_only=True)
                tag = f"{k}_{'anchored' if anchored else 'fitted'}"
                e = (lambda g, f=f: e0 + f.b * (g - g0)) if anchored else f.mean
                res[tag] = {"break_even": {n: x.text() for n, x in r.items()},
                            "summary": summarise(r, ceiling),
                            "gap_at_zero_gas": r["central"].gap_at_floor,
                            "gap_at_ceiling": r["central"].gap_at_ceiling,
                            "profile_central": gap_profile(fc, model, e, 0.0, ceiling),
                            "wholesale_only": {n: x.text() for n, x in w.items()}}
                roots += [x.gas_gbp_mwh for x in r.values() if x.gas_gbp_mwh is not None]
        fb: dict = {"without_carbon": feedback_threshold(fc, model)}
        if fleet == "A":
            fb["with_fleet_a_carbon"] = feedback_threshold(fc, model, carbon_gbp_mwh=carbon_a)
            fb["carbon_note"] = (f"UKA {m_last[0]}-{m_last[1]:02d} £{allow[m_last][0]:.2f}/t + CPS at "
                                 f"DUKES 2025 eta {eta_a:.4f}: £{carbon_a:.2f}/MWh")
        else:
            fb["with_carbon"] = ("UNSOURCED in this strand: fleet B's fuel burn by plant type is "
                                 "needed for its carbon (staircase step 2)")
        out["fleets"][fleet] = {
            "variants": res,
            "range": ({"low": min(roots), "high": max(roots)} if roots else None),
            "text": (f"£{min(roots):.0f}-£{max(roots):.0f}/MWh gas" if roots
                     else f"none below £{ceiling:.0f}/MWh gas"),
            "fleet_cost_at_observed_gas": fc(model.gas_observed),
            "uplift_losses": model.uplift_losses,
            "fixed_lines": [vars(ln) for ln in model.fixed],
            "fixed_total_gbp_mwh": model.fixed_total,
            "cfd_share": model.cfd_share.share if model.cfd_share else None,
            "cfd_window": (str(model.cfd_share.start), str(model.cfd_share.end)) if model.cfd_share else None,
            "excluded": list(model.excluded),
            "feedback_threshold": fb,
        }
    return out


def summarise(results: dict[str, BreakEven], ceiling: float = 300.0) -> dict:
    """P4 entry: a range across the confidence interval, or 'none below £X'."""
    roots = [r.gas_gbp_mwh for r in results.values() if r.gas_gbp_mwh is not None]
    if len(roots) == len(results):
        return {"kind": "range", "low": min(roots), "central": results["central"].gas_gbp_mwh,
                "high": max(roots), "direction": results["central"].direction,
                "text": f"£{min(roots):.0f}-£{max(roots):.0f}/MWh gas"}
    if not roots:
        return {"kind": "none_below", "ceiling": ceiling,
                "gap_sign": "positive" if results["central"].gap_at_floor > 0 else "negative",
                "text": f"none below £{ceiling:.0f}/MWh gas"}
    return {"kind": "partial", "results": {k: r.text() for k, r in results.items()},
            "text": "; ".join(f"{k}: {r.text()}" for k, r in results.items())}
