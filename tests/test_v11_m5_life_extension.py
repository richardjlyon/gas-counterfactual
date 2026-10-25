"""RB v1.1 M5 tests (card [internal ticket]; decision 0163 R6 (a), Richard Lyon, 21 Oct 2026, as relayed: "Agree. Next."):
a life-extension cost for coal kept open past its real closing date, in the central case if a published cost is
found, a sensitivity row if the figure is only an assumption. The analyst found no published coal figure
(outside-data-survey.md, M5), so this is a sensitivity row only, using CEPA and GHD for DESNZ (May 2025), Table 2.2
option 1B, a CCGT figure: £81/kW (2024 values) for a 5-year end-of-life extension, labelled "assumption borrowed from
gas plant". Richard is asked to confirm the row's figure (ruling R33); if he picks (b), the row is dropped.

Working reading (stated in the results): the £81/kW buys 5 years, so it is spread evenly, £81/5 per kW per year,
restated from 2024 money by CPIH, on every kept coal MW-year; it is part of kept coal's fixed cost, so under R4 (a)
it is netted against the margin with the rest. Expected values: the stored source text, the released v4-s37 run file.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import life_extension as LE
from gascf.deflator_cpih import cpih

ROOT = Path(__file__).resolve().parents[1]
# v4-s39 (card [internal ticket]): CENTRAL now carries the ruled coal settings; the v4-s37/v4-s38 kept-coal settings these
# tests reproduce are an explicit setting.
V38 = replace(B.CENTRAL, closure_test="register", kept_coal_pay="full", kept_filter_vom="added", coal_lf="dukes_max",
              gen_nz_charge="none", ro_mutualisation="off", moe_crisis="shao")
RUN37 = json.loads((ROOT / "out/v4/2026-10-20-s37.json").read_text())


def _f(s, y):
    old = os.environ.get("GASCF_FOSSIL_CLOSURES")
    os.environ["GASCF_FOSSIL_CLOSURES"] = str(ROOT / "reference/fossil_closures.yaml")
    try:
        return B.fleet_lfl.__wrapped__(y, *B._lfl_args(s, y))
    finally:
        if old is None:
            del os.environ["GASCF_FOSSIL_CLOSURES"]
        else:
            os.environ["GASCF_FOSSIL_CLOSURES"] = old


def test_the_figure_is_read_from_the_stored_source():
    c = LE.borrowed_gas()
    assert (c["gbp_kw"], c["years"], c["price_base"]) == (81.0, 5, 2024)     # Table 2.2, option 1B, 2024 values
    assert "assumption borrowed from gas plant" in c["label"]
    assert c["source_file"].endswith("cepa-ghd-2025-05-generation-cost-study-life-extension.txt")


def test_the_row_adds_the_cost_on_every_kept_coal_mw_year():
    f37 = RUN37["fleet"]["2015"]
    mw = f37["kept_gw"]["coal"] * 1e3
    want = mw * 81.0 / 5 * cpih()[2015] / cpih()[2024] / 1e3          # £m, 2015 money
    got = _f(replace(V38, kept_life_ext="borrowed_gas"), 2015)
    k = got["kept_coal_pay"]
    assert k["life_ext_gbp_m"] == pytest.approx(want, rel=1e-12)
    assert got["fixed_gbp_m"] == pytest.approx(f37["fixed_gbp_m"] + want, abs=1e-9)


def test_off_by_default():
    f37 = RUN37["fleet"]["2015"]
    got = _f(V38, 2015)
    assert got["kept_coal_pay"]["life_ext_gbp_m"] == 0.0
    assert got["fixed_gbp_m"] == pytest.approx(f37["fixed_gbp_m"], abs=1e-9)


def test_under_r4_a_it_is_netted_against_the_margin():
    k = _f(replace(V38, kept_coal_pay="fixed_less_margin", kept_life_ext="borrowed_gas"), 2015)["kept_coal_pay"]
    assert k["paid_gbp_m"] == pytest.approx(max(0.0, k["coal_fixed_gbp_m"] - k["margin_gbp_m"]), abs=1e-12)
    assert k["coal_fixed_gbp_m"] == pytest.approx(RUN37["fleet"]["2015"]["kept_fixed_gbp_m"] + k["life_ext_gbp_m"])


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
