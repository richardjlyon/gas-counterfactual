"""v4-s40 item 2 (step-3 sheet item 2 (a); decision 0175, Richard Lyon 23 Oct 2026, "Yes." at 06:13:51 UTC to the
chief-executive's point 1, the reviewer's first-choice fix on every item; verified first-hand on card [internal ticket]).

The sheet's (a): "Have the margin use the road's own revenue consistently, including its timing and charges." Wording
after: "Kept coal receives only the fixed cost not covered by the market margin assigned to its output on the road,
never less than nil."

To v4-s39 M3 (decision 0163 R4 (a)) took kept coal's margin at annual means of the observed price less carbon, and
left out the road's merit-order uplift and gas-price feedback, which the road charges on that same market-priced
output (review [internal ticket] item 2). v4-s40 reads the margin from the road itself: kept coal's share (kept coal MW over
the coal block's MW, the share v4-s39 already used) of the coal block's own output in each half-hour, paid what the
road pays every market-priced MWh in that half-hour: the month's price (MID-shaped under M8) less the month's carbon,
plus the half-hour's uplift on the M9/Shao scale, plus the month's gas-price feedback per MWh, less the generators'
net-zero charge per MWh (0167 way 2); less its fuel at the month's coal price, its running cost and its filters'
running cost. The pay is max(0, fixed cost - margin). `$GASCF_M3_MARGIN`: "road" (v4-s40 central, unset) or
"observed" (v4-s39, explicit only).

Expected values come from the stored price, carbon and coal series (bills.p_elec, bills.c_marg,
fossil_like_for_like.coal_price), not from the margin code. 2022 has kept coal under extra running at the market price.
"""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import closure_test as CT
from gascf import fossil_fleet as ff
from gascf import fossil_like_for_like as L

ROOT = Path(__file__).resolve().parents[1]
ENV = getattr(B, "M3_MARGIN_ENV", "GASCF_M3_MARGIN")   # getattr: the red run on v4-s39 fails on behaviour
Y = 2022


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    monkeypatch.setenv(L.CLOSURES_ENV, str(ROOT / "reference/fossil_closures.yaml"))
    monkeypatch.delenv(L.EDITION_MW_ENV, raising=False)
    monkeypatch.delenv(ENV, raising=False)
    yield
    _clear()


def _clear():
    L.lfl_year.cache_clear()
    L.road_lf_closures.cache_clear()
    B.fleet_lfl.cache_clear()


def _f(s, y=Y):
    return B.fleet_lfl.__wrapped__(y, *B._lfl_args(s, y))



def test_central_margin_carries_the_road_uplift_and_feedback():
    f = _f(B.CENTRAL)
    k = f["kept_coal_pay"]
    assert k["rule"] == "fixed_less_margin" and k["coal_mw"] > 0
    assert k.get("margin_basis") == "road"
    assert k["uplift_gbp_m"] > 0.0                      # 2022: the road's uplift on kept coal's output
    assert k["feedback_gbp_m"] != 0.0
    parts = k["price_less_carbon_gbp_m"] + k["uplift_gbp_m"] + k["feedback_gbp_m"] - k["fuel_gbp_m"] - k["vom_gbp_m"]
    assert k["margin_gbp_m"] == pytest.approx(parts, rel=1e-12)
    assert k["paid_gbp_m"] == pytest.approx(max(0.0, k["coal_fixed_gbp_m"] - k["margin_gbp_m"]), rel=1e-12)


def test_margin_without_uplift_or_feedback_is_the_monthly_price_less_carbon_less_costs(monkeypatch):
    """Monthly prices (M8 off), no uplift, no feedback: the margin is kept coal's share of the coal block's output by
    month at the stored price less carbon, less fuel at the stored coal price, running cost and filters."""
    monkeypatch.setenv("GASCF_M8_HH_PRICE", "monthly")
    s = replace(B.CENTRAL, moe="none", gas_feedback="none")
    _clear()
    f = _f(s)
    k = f["kept_coal_pay"]
    assert k["uplift_gbp_m"] == 0.0 and k["feedback_gbp_m"] == 0.0
    P, C = B.p_elec(s.route), B.c_marg()
    ed = L.edition(Y)
    vom = ff.restate(ed.coal.variable_om_gbp_mwh, ed.price_base["coal"], Y)
    eta = L._eta_dukes("coal", Y)
    sh, twh_m = k["share"], k["block_twh_m"]
    want = sum(sh * twh_m[m] * (P[(Y, m)]["gbp_per_mwh"] - C[(Y, m)]["gbp_per_mwh"] - L.coal_price(Y, m) / eta
                                - vom - k["filter_vom_gbp_mwh"]) for m in range(1, 13))
    assert k["margin_gbp_m"] == pytest.approx(want, rel=1e-9)


def test_coal_block_by_month_adds_up_and_its_uplift_is_inside_the_fleet():
    s = B.CENTRAL
    r = _road_year(s)
    assert sum(r.coal_twh_m.values()) == pytest.approx(r.coal_twh, rel=1e-6)
    for m in range(1, 13):
        assert r.coal_moe_vol_m[m] <= r.moe_vol_f_m[m] + r.moe_vol_x_m[m] + 1e-6
    k = _f(s)["kept_coal_pay"]
    assert k["share"] == pytest.approx(k["coal_mw"] / r.existing.coal, rel=1e-12)
    assert k["margin_twh"] == pytest.approx(k["share"] * r.coal_twh, rel=1e-6)   # v4-s39's volume, by month now


def test_extra_running_at_cost_keeps_the_v4_s39_rule():
    """Row C (extra_running='cost'): kept coal keeps its whole fixed cost, as in v4-s39. Item 2 does not touch it (an
    open question for Richard, recorded in v4-s40-build.md, not decided here)."""
    s = replace(B.CENTRAL, extra_running="cost")
    _clear()
    k = _f(s)["kept_coal_pay"]
    assert "margin_basis" not in k and "margin_gbp_m" not in k
    assert k["paid_gbp_m"] == k["coal_fixed_gbp_m"]


def _road_year(s):
    """lfl_year exactly as bills.fleet_lfl calls it for settings `s` (so it is the same cached year)."""
    a = B._lfl_args(s, Y)
    return L.lfl_year(Y, a[1], a[0], a[2], a[5], a[6], str(L.closures_path()), a[8], a[9],
                      closure_test=a[12], real_date_class=a[16], cost_case=a[17])


def test_observed_reading_reproduces_v4_s39(monkeypatch):
    monkeypatch.setenv(ENV, "observed")
    _clear()
    f = _f(B.CENTRAL)
    k = f["kept_coal_pay"]
    r = _road_year(B.CENTRAL)
    want = CT.kept_coal_margin(Y, k["coal_mw"], r.coal_lf_achieved, k["filter_vom_gbp_mwh"], B.CENTRAL.route)
    assert k["margin_gbp_m"] == want["margin_gbp_m"]
    assert k.get("margin_basis", "observed") == "observed"


def test_generators_net_zero_charge_comes_off_the_margin():
    """0167 way 2 takes delta £/MWh off every MWh the road buys at the market price, so off kept coal's margin too."""
    k = {"rule": "fixed_less_margin", "margin_basis": "road", "coal_mw": 1000.0, "coal_fixed_gbp_m": 100.0,
         "margin_gbp_m": 90.0, "margin_twh": 4.0, "paid_gbp_m": 10.0}
    got = B.kept_coal_pay_after_charge(k, 2.5, Y)
    assert got["charge_gbp_m"] == pytest.approx(10.0)
    assert got["margin_gbp_m"] == pytest.approx(80.0)
    assert got["paid_gbp_m"] == pytest.approx(20.0)
    rich = {**k, "margin_gbp_m": 200.0, "paid_gbp_m": 0.0}
    assert B.kept_coal_pay_after_charge(rich, 2.5, Y)["paid_gbp_m"] == 0.0           # never less than nil
    for other in ({**k, "rule": "full", "paid_gbp_m": 100.0}, {**k, "margin_basis": "observed"},
                  {**k, "rule": "cm_from_2014", "paid_gbp_m": 33.0}):
        assert B.kept_coal_pay_after_charge(other, 2.5, Y)["paid_gbp_m"] == other["paid_gbp_m"]
    early = {**k, "rule": "cm_from_2014"}                                            # R4 (b) before 2014: (a)
    assert B.kept_coal_pay_after_charge(early, 2.5, 2013)["paid_gbp_m"] == pytest.approx(20.0)
