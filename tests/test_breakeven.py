"""Break-even gas price (spec §9): the Ofgem regression, the CfD movement, the root finder."""
import math
from datetime import date

import pytest

from gascf import breakeven as be
from gascf.breakeven import (BreakEven, GapLine, GapModel, cap_periods, cfd_volume, fit_cap_periods,
                             is_epg, solve, summarise, t_quantile, wls)


# ------------------------------------------------------------------ statistics

def test_t_quantile_matches_printed_tables():
    # Student's t, two-sided 95%: printed tables give 12.706 (1 df), 2.228 (10), 2.042 (30), 2.048 (28)
    for df, want in ((1, 12.706), (10, 2.228), (30, 2.042), (28, 2.048)):
        assert t_quantile(0.975, df) == pytest.approx(want, abs=5e-4)


def test_wls_recovers_an_exact_line():
    x = [1.0, 2.0, 5.0, 9.0]
    y = [3 + 2 * v for v in x]
    a, b, va, vb, cab, s2 = wls(x, y, [1, 3, 2, 6])
    assert (a, b) == (pytest.approx(3), pytest.approx(2))
    assert s2 == pytest.approx(0, abs=1e-20) and va == pytest.approx(0, abs=1e-18)


def _closed_form(x, y, w):
    """Independent calculation: weighted means and centred sums (not the normal-equation
    inverse used in the module)."""
    W = sum(w)
    xb = sum(wi * xi for wi, xi in zip(w, x)) / W
    yb = sum(wi * yi for wi, yi in zip(w, y)) / W
    sxx = sum(wi * (xi - xb) ** 2 for wi, xi in zip(w, x))
    sxy = sum(wi * (xi - xb) * (yi - yb) for wi, xi, yi in zip(w, x, y))
    b = sxy / sxx
    a = yb - b * xb
    s2 = sum(wi * (yi - a - b * xi) ** 2 for wi, xi, yi in zip(w, x, y)) / (len(x) - 2)
    se_b = math.sqrt(s2 / sxx)
    se_a = math.sqrt(s2 * (1 / W + xb * xb / sxx))
    return a, b, se_a, se_b


@pytest.mark.parametrize("exclude", [False, True])
def test_fit_reproduced_by_independent_closed_form(exclude):
    ps = [p for p in cap_periods() if not (exclude and is_epg(p))]
    a, b, se_a, se_b = _closed_form([p.gas_index for p in ps], [p.elec_index for p in ps],
                                    [p.months for p in ps])
    f = fit_cap_periods(exclude)
    assert f.n == (29 if exclude else 32)
    assert (f.a, f.b) == (pytest.approx(a, rel=1e-10), pytest.approx(b, rel=1e-10))
    assert (f.se_a, f.se_b) == (pytest.approx(se_a, rel=1e-9), pytest.approx(se_b, rel=1e-9))


def test_weights_are_period_lengths():
    """Six-month periods to Sep 2022 weigh 6, quarters from Oct 2022 weigh 3; 32 periods
    covering Apr 2015 - Dec 2026 = 141 months."""
    f = fit_cap_periods()
    assert sum(f.weights) == 141
    assert f.weights[0] == 6 and f.weights[-1] == 3
    # weights matter: an unweighted fit gives a different slope
    ps = cap_periods()
    a1, b1, *_ = wls([p.gas_index for p in ps], [p.elec_index for p in ps], [1.0] * len(ps))
    assert abs(b1 - f.b) > 1e-3


def test_epg_periods_are_the_three_quarters():
    assert [p.name for p in cap_periods() if is_epg(p)] == [
        "October 2022 - December 2022", "January 2023 - March 2023", "April 2023 - June 2023"]


def test_headline_fit_values():
    """Values this strand reports (notes.md REPORT). Slope CI excludes 1: the electricity
    index moves far more than one-for-one with gas, as expected for gas-fired marginal
    plant at ~0.48 efficiency (1/0.48 = 2.08) plus carbon that rose with gas."""
    f, g = fit_cap_periods(False), fit_cap_periods(True)
    assert f.b == pytest.approx(2.8018, abs=1e-4) and f.a == pytest.approx(2.088, abs=1e-3)
    assert f.b_ci == (pytest.approx(2.6753, abs=1e-4), pytest.approx(2.9282, abs=1e-4))
    assert g.b == pytest.approx(2.5591, abs=1e-4) and g.a == pytest.approx(7.471, abs=1e-3)
    assert g.b_ci == (pytest.approx(2.3195, abs=1e-4), pytest.approx(2.7987, abs=1e-4))


def test_confidence_band_contains_the_line_and_widens_away_from_the_mean():
    f = fit_cap_periods()
    lo1, hi1 = f.band(25)
    lo2, hi2 = f.band(110)
    assert lo1 < f.mean(25) < hi1
    assert hi2 - lo2 > hi1 - lo1


# ------------------------------------------------------------------ CfD volumes

def test_cfd_volume_twelve_months_to_sep_2026():
    """LCCC actual CfD generation 1 Oct 2025 - 30 Sep 2026: 38.20 TWh; eligible demand
    262.80 TWh (actual ILR income file); share 14.5%. Payments £2,568.5m."""
    v = cfd_volume(date(2026, 9, 30))
    assert v.days == 365 and v.start == date(2025, 10, 1)
    assert v.generation_mwh / 1e6 == pytest.approx(38.200, abs=1e-3)
    assert v.eligible_demand_mwh / 1e6 == pytest.approx(262.801, abs=1e-3)
    assert v.share == pytest.approx(0.14536, abs=1e-5)
    assert v.payments_gbp / 1e6 == pytest.approx(2568.53, abs=0.01)


def test_cfd_volume_fails_on_missing_days():
    with pytest.raises(ValueError):
        cfd_volume(date(2030, 1, 1))


# ------------------------------------------------------------------ gap model and root finder

def _toy(fixed=10.0, share=0.0):
    cfd = None
    if share:
        cfd = be.CfdVolume(date(2025, 1, 1), date(2025, 12, 31), share * 100, 0.0, 100.0, 365)
    return GapModel("toy", 1.0, 40.0, 100.0, cfd, (GapLine("x", fixed, "4a", "measured", "t"),), ())


def test_gap_identity_and_cfd_direction():
    m = _toy(fixed=10.0, share=0.2)
    e = lambda g: 2.5 * g                 # electricity index
    c = lambda g: 2.0 * g + 5              # fleet cost
    # at the observed gas price the CfD term is zero
    assert m.gap(40, e, c) == pytest.approx(1.0 * (100 - 85) + 10)
    # gas 20 lower: wholesale falls 50, CfD top-up rises 0.2 x 50 = 10
    assert m.gap(20, e, c) == pytest.approx((50 - 45) + 10 + 10)


def test_solve_finds_a_known_root_both_ways():
    r = solve(lambda g: 50 - g, 0, 300)
    assert r.gas_gbp_mwh == pytest.approx(50, abs=1e-8) and r.direction == "gas_cheaper_below"
    r = solve(lambda g: g - 73.3, 0, 300)
    assert r.gas_gbp_mwh == pytest.approx(73.3, abs=1e-8) and r.direction == "gas_cheaper_above"


def test_solve_reports_none_below():
    r = solve(lambda g: 10 + g, 0, 300)
    assert r.gas_gbp_mwh is None and r.none_below == 300 and r.gap_at_floor > 0
    assert summarise({"central": r, "band_low": r, "band_high": r})["text"] == "none below £300/MWh gas"


def test_break_even_on_toy_model_closed_form():
    """Linear everything: gap(G) = (a + bG - (c + dG)) + fixed; root (c - a - fixed)/(b - d)."""
    fit = be.Fit("toy", a=5.0, b=2.0, var_a=0.0, var_b=0.0, cov_ab=0.0, n=10, sigma2=0.0, t95=2.3,
                 periods=(), weights=())
    m = GapModel("toy", 1.0, 40.0, 85.0, None, (GapLine("x", 10.0, "4a", "measured", "t"),), ())
    fleet = lambda g: 3.0 * g                         # dearer per £ of gas than the market
    r = be.break_even(fleet, m, fit)
    assert r["central"].gas_gbp_mwh == pytest.approx((0 - 5 - 10) / (2 - 3), abs=1e-8)
    assert r["central"].direction == "gas_cheaper_below"


# ------------------------------------------------------------------ the real model (Oct-Dec 2026)

@pytest.fixture(scope="module")
def model_a():
    return be.gap_model("October 2026 - December 2026", "A")


def test_gap_model_lines(model_a):
    keys = {ln.key: ln for ln in model_a.fixed}
    assert set(keys) == {"whd", "aahedc", "eii_levy", "sizewell_c", "ro", "fit", "cfd", "ro_treasury",
                         "constraints", "ofto"}
    assert keys["cfd"].gbp_per_mwh * 2.5 == pytest.approx(17.14, abs=0.005)    # spec §6 CfD £17.14
    assert keys["ro"].gbp_per_mwh == pytest.approx(8.18212, abs=1e-5)       # Annex 4, £20.46 / 2.5
    assert keys["ro_treasury"].gbp_per_mwh == pytest.approx(24.54636, abs=1e-5)
    assert sum(keys[k].gbp_per_mwh for k in ("whd", "aahedc", "eii_levy", "sizewell_c")) * 2.5 \
        == pytest.approx(31.35, abs=0.01)                                    # spec §6 £31.35
    assert model_a.uplift_losses == pytest.approx(1.2148, abs=1e-4)
    assert model_a.gas_observed == pytest.approx(40.24, abs=5e-3)


@pytest.fixture(scope="module")
def fleets():
    return {f: be.fleet_cost_fn(f) for f in "AB"}


def test_fleet_costs_match_memory(fleets):
    """memory.md: 2025 load curve, gas £40.24 (2026 money): fleet A £104.3/MWh, fleet B £114.1. Decision 0133
    (margin over the 2027/28 peak, 7.4% not 7.0%) moves both: re-pinned from the build, 20 Oct 2026."""
    assert fleets["A"](40.24) == pytest.approx(104.40, abs=0.05)
    assert fleets["B"](40.24) == pytest.approx(114.18, abs=0.05)


def test_oct_dec_2026_has_no_break_even_below_300(model_a, fleets):
    """Reported result: what you pay stays above the pure gas price for every gas price up
    to £300/MWh, both fleets, both fits, fitted and anchored, across the 95% interval."""
    for fleet in "AB":
        m = be.gap_model("October 2026 - December 2026", fleet)
        for ex in (False, True):
            for anchored in (False, True):
                r = be.break_even(fleets[fleet], m, fit_cap_periods(ex), anchored=anchored)
                assert all(x.gas_gbp_mwh is None and x.gap_at_floor > 0 for x in r.values())


def test_wholesale_alone_does_cross(model_a, fleets):
    """Without the policy and grid lines the wholesale line alone does cross the fleet-A
    cost (fitted, all periods: about £22/MWh): the result is carried by the policy lines."""
    r = be.break_even(fleets["A"], model_a, fit_cap_periods(), wholesale_only=True)
    assert r["central"].gas_gbp_mwh == pytest.approx(21.76, abs=0.1)     # 21.6 before decision 0133
    assert r["central"].direction == "gas_cheaper_above"


def test_mutation_cfd_sign_is_pinned(model_a, fleets):
    """Mutation guard: if the CfD movement had the wrong sign, the gap at zero gas would fall
    by 2 x share x (E(G0) - E(0)). Pin the value so a sign flip fails."""
    f = fit_cap_periods()
    g = model_a.gap(0.0, f.mean, fleets["A"])
    # 68.91 after s9 (constraint baseline volume-based, GB demand): 2025/26 constraint line 15.25 -> 14.89;
    # 68.81 after decision 0133 (fleet A carries the 7.4% margin over the 2027/28 peak; fixed lines unchanged)
    assert g == pytest.approx(68.81, abs=0.01)
    assert model_a.fixed_total == pytest.approx(67.349, abs=1e-3)


def test_feedback_threshold_fleet_a(model_a, fleets):
    """Spec §7.4 threshold, step 3 left out: gas would have to rise 46.5% (no carbon
    subtracted) or 12.1% (fleet A carbon £29.39/MWh subtracted) before the gap closes. Decision 0133 (margin
    over the 2027/28 peak) re-pin, from the build: 0.4620 -> 0.4610 and 0.1174 -> 0.1165."""
    assert be.feedback_threshold(fleets["A"], model_a)["k"] == pytest.approx(0.4610, abs=1e-4)
    assert be.feedback_threshold(fleets["A"], model_a, carbon_gbp_mwh=29.394)["k"] \
        == pytest.approx(0.1165, abs=1e-4)
