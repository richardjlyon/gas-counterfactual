"""RB v1.1 M4 tests (card [internal ticket]; decision 0163 R5 (a), Richard Lyon, 21 Oct 2026, as relayed: "Agree. Next."):
the pollution-filter running cost on kept coal's extra output is counted once.

Since v4-s37 (0144 item 1A) the extra running of the plant real Britain had is charged the market price, in place of
its fuel and running costs. Kept coal's filter running cost (SCR, £/MWh) was still added on top for its share of the
extra output, so that cost was counted twice (paper Annex F.1, 'Held for the author's decision'). With
kept_filter_vom='in_price' it is not added when the extra running is at the market price; at cost (sensitivity row C)
it is still charged, once. Expected values are the released v4-s37 run file's own figures (2024 is untouched by the
Rugeley fix, which moves 2016-20 only).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from gascf import bills as B

ROOT = Path(__file__).resolve().parents[1]
# v4-s39 (card [internal ticket]): CENTRAL now carries the ruled coal settings; the v4-s37/v4-s38 kept-coal settings these
# tests reproduce are an explicit setting.
V38 = replace(B.CENTRAL, closure_test="register", kept_coal_pay="full", kept_filter_vom="added", coal_lf="dukes_max",
              gen_nz_charge="none", ro_mutualisation="off", moe_crisis="shao")
RUN37 = json.loads((ROOT / "out/v4/2026-10-20-s37.json").read_text())


def _f(s, y=2024):
    """fleet_lfl on the real register (the release's), bypassing its cache: this session runs on the conftest
    fixture register, and lfl_year below is cached by the register path, so nothing crosses over."""
    import os
    old = os.environ.get("GASCF_FOSSIL_CLOSURES")
    os.environ["GASCF_FOSSIL_CLOSURES"] = str(ROOT / "reference/fossil_closures.yaml")
    try:
        return B.fleet_lfl.__wrapped__(y, *B._lfl_args(s, y))
    finally:
        if old is None:
            del os.environ["GASCF_FOSSIL_CLOSURES"]
        else:
            os.environ["GASCF_FOSSIL_CLOSURES"] = old


def _total(f: dict) -> float:
    """GO1 as `bills.fleet_lfl` sums it, from the run file (it prints the total per MWh and the energy)."""
    return f["gbp_per_mwh"] * f["energy_twh"]


def test_released_v4_s37_charged_the_filters_on_top_of_the_market_price():
    f = RUN37["fleet"]["2024"]
    assert f["extra_running"] == "market"
    assert f["kept_abatement_vom_gbp_m"] == pytest.approx(4.4573, abs=1e-4)


def test_in_price_drops_the_second_charge_at_the_market_price():
    f37 = RUN37["fleet"]["2024"]
    got = _f(replace(V38, kept_filter_vom="in_price"))
    assert got["kept_abatement_vom_gbp_m"] == 0.0
    assert got["vom_gbp_m"] == pytest.approx(f37["vom_gbp_m"] - f37["kept_abatement_vom_gbp_m"], abs=1e-9)
    assert got["total_gbp_m"] == pytest.approx(_total(f37) - f37["kept_abatement_vom_gbp_m"] + S42_2024, abs=1e-6)


# v4-s42 (card [internal ticket], decision 0195): the seven input fixes move fossil Britain's 2024 fleet cost on this seam by
# S42_2024 GBP m, the same with the filters added or in the price (re-pinned from this test's own obtained values on
# the v4-s42 build: 17462.543007 and 17458.085688), attributed to A3 (gas transport 2021-25 at National Gas's
# published rates; the only fix that moves 2024) by the single-fix candidate trees ([internal ticket]) on the M4. Nothing
# else in the v4-s37 2024 fleet moves: the abatement charge and the VOM are compared unchanged.
S42_2024 = -48.067966949334


def test_default_reproduces_v4_s37_2024():
    f37 = RUN37["fleet"]["2024"]
    got = _f(V38)
    assert got["kept_abatement_vom_gbp_m"] == pytest.approx(f37["kept_abatement_vom_gbp_m"], abs=1e-9)
    assert got["total_gbp_m"] == pytest.approx(_total(f37) + S42_2024, abs=1e-6)


def test_at_cost_the_filters_are_still_charged_once():
    a = _f(replace(V38, extra_running="cost"))
    b = _f(replace(V38, extra_running="cost", kept_filter_vom="in_price"))
    assert a["kept_abatement_vom_gbp_m"] > 0
    assert b["kept_abatement_vom_gbp_m"] == pytest.approx(a["kept_abatement_vom_gbp_m"], abs=1e-12)
    assert b["total_gbp_m"] == pytest.approx(a["total_gbp_m"], abs=1e-9)


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
