"""RB v1.1 M3 tests (card [internal ticket]; decision 0163 R4, Richard Lyon, 21 Oct 2026, as relayed: "Agree. Next."):
(a) kept coal is paid its fixed cost less its market margin, floored at zero, in all years (central);
(b) the Capacity Market price from 2014, (a) before, as a named sensitivity row.

Working reading (stated in the results, not a ruling): the margin is the closure test's (M2) margin on kept coal's
output at the road's coal load factor: output x (price less carbon - fuel / efficiency - variable O&M - filters'
running cost), annual means; the CM price is the rate the road pays other existing plant (its notional CM, £/kW-yr,
the run file's capacity_market block) on kept coal's de-rated MW. Both apply under extra running at the market price;
at cost (row C) kept coal is paid its whole fixed cost, as before. Expected values: the released v4-s37 run file
(2015 and 2022 are untouched by the Rugeley fix: Rugeley is kept only from mid-2016 to mid-2020)
 and the stored s24 closure-test file's 2015 spread.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import capacity
from gascf import fossil_fleet as ff
from gascf import fossil_like_for_like as L

ROOT = Path(__file__).resolve().parents[1]
# v4-s39 (card [internal ticket]): CENTRAL now carries the ruled coal settings; the v4-s37/v4-s38 kept-coal settings these
# tests reproduce are an explicit setting.
V38 = replace(B.CENTRAL, closure_test="register", kept_coal_pay="full", kept_filter_vom="added", coal_lf="dukes_max",
              gen_nz_charge="none", ro_mutualisation="off", moe_crisis="shao")
RUN37 = json.loads((ROOT / "out/v4/2026-10-20-s37.json").read_text())
S24 = json.loads((ROOT / "work/s24-closure-test/margins.json").read_text())


def _f(s, y):
    """fleet_lfl on the real register, bypassing its cache (this session runs on the conftest fixture register)."""
    old = os.environ.get("GASCF_FOSSIL_CLOSURES")
    os.environ["GASCF_FOSSIL_CLOSURES"] = str(ROOT / "reference/fossil_closures.yaml")
    try:
        return B.fleet_lfl.__wrapped__(y, *B._lfl_args(s, y))
    finally:
        if old is None:
            del os.environ["GASCF_FOSSIL_CLOSURES"]
        else:
            os.environ["GASCF_FOSSIL_CLOSURES"] = old


A = replace(V38, kept_coal_pay="fixed_less_margin")
CM = replace(V38, kept_coal_pay="cm_from_2014")


def _filter_vom(y: int, f: dict) -> float:
    ed = ff.edition(y)
    ab = f["kept_abated_gw"]
    w = sum(ff.abatement_gbp_kw_yr(ed, k)[1] * gw for k, gw in ab.items() if gw > 0)
    return w / f["kept_gw"]["coal"]


def test_2015_kept_coal_earns_more_than_its_fixed_cost_so_is_paid_nothing(monkeypatch):
    """The margin pinned here is v4-s39's (annual means of the observed price less carbon), now the explicit
    "observed" reading of $GASCF_M3_MARGIN. v4-s40 item 2 (decision 0175) takes the margin from the road's own revenue
    (tests/test_v4_s40_m3_road_margin.py); under it 2015 kept coal is still paid nothing (checked at the end)."""
    monkeypatch.setenv(B.M3_MARGIN_ENV, "observed")
    f37 = RUN37["fleet"]["2015"]
    spread = next(r for r in S24["Rugeley"]["years"] if r["year"] == 2015)["spread_gbp_mwh"]
    mw = f37["kept_gw"]["coal"] * 1e3
    lf = f37["coal_lf"]["achieved"]
    margin = mw * lf * 8760 / 1e6 * (spread - _filter_vom(2015, f37))
    assert margin > f37["kept_fixed_gbp_m"]                      # about £122m against £96.9m
    got = _f(A, 2015)
    k = got["kept_coal_pay"]
    assert k["rule"] == "fixed_less_margin"
    assert k["coal_fixed_gbp_m"] == pytest.approx(f37["kept_fixed_gbp_m"], abs=1e-9)
    assert k["margin_gbp_m"] == pytest.approx(margin, rel=1e-9)
    assert k["paid_gbp_m"] == 0.0
    assert got["fixed_gbp_m"] == pytest.approx(f37["fixed_gbp_m"] - f37["kept_fixed_gbp_m"], abs=1e-9)
    monkeypatch.delenv(B.M3_MARGIN_ENV)                          # v4-s40 central: the road margin
    road = _f(A, 2015)["kept_coal_pay"]
    assert road["margin_basis"] == "road" and road["margin_gbp_m"] > road["coal_fixed_gbp_m"]
    assert road["paid_gbp_m"] == 0.0


def test_default_pays_the_whole_fixed_cost_as_v4_s37():
    f37 = RUN37["fleet"]["2015"]
    got = _f(V38, 2015)
    assert got["fixed_gbp_m"] == pytest.approx(f37["fixed_gbp_m"], abs=1e-9)
    assert got["kept_coal_pay"]["paid_gbp_m"] == pytest.approx(f37["kept_fixed_gbp_m"], abs=1e-9)


@pytest.mark.parametrize("y", [2013, 2020, 2024])
def test_paid_is_fixed_less_margin_floored_at_zero(y):
    k = _f(A, y)["kept_coal_pay"]
    assert k["paid_gbp_m"] == pytest.approx(max(0.0, k["coal_fixed_gbp_m"] - k["margin_gbp_m"]), abs=1e-12)
    assert k["paid_gbp_m"] >= 0.0


def test_cm_row_pays_the_roads_cm_rate_on_kept_coal_from_2014():
    f37 = RUN37["fleet"]["2022"]
    price = RUN37["capacity_market"]["2022"]["price_gbp_kw_yr"]
    der = capacity.read_derating()["ccgt"]
    got = _f(CM, 2022)["kept_coal_pay"]
    assert got["rule"] == "cm_from_2014"
    assert got["cm_price_gbp_kw_yr"] == pytest.approx(price, rel=1e-12)
    assert got["paid_gbp_m"] == pytest.approx(price * f37["kept_gw"]["coal"] * der, rel=1e-9)
    # before 2014 the row is rule (a)
    assert _f(CM, 2013)["kept_coal_pay"]["paid_gbp_m"] == pytest.approx(_f(A, 2013)["kept_coal_pay"]["paid_gbp_m"])


def test_at_cost_kept_coal_keeps_its_whole_fixed_cost():
    a = _f(replace(A, extra_running="cost"), 2015)
    b = _f(replace(V38, extra_running="cost"), 2015)
    assert a["fixed_gbp_m"] == pytest.approx(b["fixed_gbp_m"], abs=1e-12)


def test_2025_uses_the_engines_recorded_coal_efficiency_rule():
    """DUKES prints no coal efficiency for 2025; the margin uses the engine's own rule for kept coal (the 2015-23
    mean, `fossil_like_for_like._eta_dukes`, recorded as a fallback), as the road's stack does."""
    from gascf import fallbacks as FB
    from gascf import prices
    e = prices.dukes_efficiency()["coal"]
    assert 2025 not in e
    k = _f(A, 2025)["kept_coal_pay"]
    assert k["paid_gbp_m"] == pytest.approx(max(0.0, k["coal_fixed_gbp_m"] - k["margin_gbp_m"]), abs=1e-12)
    assert any(r.get("name") == "coal_efficiency_mean_2015_2023" for r in FB.recorded())


@pytest.fixture(autouse=True)
def _v4_s38_price_settings(monkeypatch):
    """v4-s39 (card [internal ticket]): M7 and M8 are central by default (0167); these tests reproduce v4-s37, so they set the
    v4-s38 readings explicitly and clear the carbon-price cache either side."""
    monkeypatch.setenv("GASCF_M7_CARBON_MARGINAL", "gas")
    monkeypatch.setenv("GASCF_M8_HH_PRICE", "monthly")
    monkeypatch.setenv("GASCF_M8_SCOPE", "fossil")
    from gascf import closure_test as CT
    for f in (B.c_marg, CT._year_inputs, CT.station_margin):
        f.cache_clear()
    yield
    for f in (B.c_marg, CT._year_inputs, CT.station_margin):
        f.cache_clear()
