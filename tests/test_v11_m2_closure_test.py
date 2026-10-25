"""RB v1.1 M2 tests (card [internal ticket]; decision 0163, R1 (a) + R2 (a) + R3 (a), Richard Lyon, 21 Oct 2026, as relayed:
"Agree. Next."): the closure test for the 9 'mixed' closures at the road's own coal load factor, repeated until the
closure list stops changing.

Expected values come from the stored closure-test files written by the work scripts (work/s24-closure-test,
work/s28-fiddlers, work/s37-cottam), from the TNUoS components printed in those files, and from the register's own
dates; never from the code under test.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from gascf import closure_test as CT
from gascf import fossil_like_for_like as L

ROOT = Path(__file__).resolve().parents[1]
STORED = {**json.loads((ROOT / "work/s24-closure-test/margins.json").read_text()),
          **json.loads((ROOT / "work/s28-fiddlers/margins.json").read_text())}
STORED["Cottam"] = json.loads((ROOT / "work/s37-cottam/cottam_margin.json").read_text())["Cottam zone 15"]


def _mixed():
    return [r for r in L.read_closures(L.CLOSURES_FILE) if r["reason"] == "mixed"]


def test_nine_mixed_rows_carry_their_test_as_data():
    rows = _mixed()
    assert len(rows) == 9
    names = {r["closure_test"]["margin_name"] for r in rows}
    assert names == {"Tilbury B", "Ironbridge", "Ferrybridge C", "Longannet", "Rugeley", "Fiddler's Ferry unit 1",
                     "Cottam", "Aberthaw B", "Fiddler's Ferry units 2-4"}
    for r in rows:
        t = r["closure_test"]
        assert t["if_kept_rule"] in CT.IF_KEPT_RULES
        assert t["if_kept_source"]
        # the margin test's MW is the register's MW (one capacity per station)
        assert CT.station(t["margin_name"])["mw"] == r["capacity_mw"]


@pytest.mark.parametrize("name", sorted(STORED))
def test_margin_at_the_stations_own_load_factor_reproduces_the_stored_test(name):
    for row in STORED[name]["years"]:
        got = CT.station_margin(name, row["year"], row["lf"])
        assert got["margin_before_filters_gbp_m"] == pytest.approx(row["margin_before_filters_gbp_m"], abs=1e-9)
        assert got["fgdscr_gbp_m"] == pytest.approx(row["fgdscr_gbp_m"], abs=1e-9)


def _components(src: str) -> tuple[float, ...]:
    return tuple(float(x) for x in re.search(r"\((-?[\d.]+), (-?[\d.]+), (-?[\d.]+), (-?[\d.]+)\)", src).groups())


def test_cottam_2018_at_the_roads_load_factor_hand_worked():
    """Cottam 2018 (the year before its real closure) at a 65.04% load factor, worked from the stored file: output
    x spread (price less carbon, less fuel and running cost), less fixed cost, less TNUoS at that ALF (2018/19 paper
    not stored: the higher of the 2017/18 and 2019/20 component sums, as the stored test does)."""
    ys = {r["year"]: r for r in STORED["Cottam"]["years"]}
    lf = 0.6504
    twh = 2000 * lf * 8760 / 1e6
    tn = max(pk + lf * yrs + yrns + res for pk, yrs, yrns, res in
             (_components(ys[2017]["tnuos_src"]), _components(ys[2019]["tnuos_src"])))
    want = twh * ys[2018]["spread_gbp_mwh"] - ys[2018]["fixed_gbp_m"] - 2000 * tn / 1000
    got = CT.station_margin("Cottam", 2018, lf)
    # the stored file prints the TNUoS components to 2 decimals: 4 parts x £0.005/kW x 2,000 MW = £0.04m at most
    assert got["margin_before_filters_gbp_m"] == pytest.approx(want, abs=0.04)
    assert got["margin_before_filters_gbp_m"] > 0            # at the road's load factor Cottam earns its keep


def test_carbon_hook_adds_its_charge_per_mwh_of_output():
    """The carbon rows ([internal ticket], R12 (a)) use this same test: their carbon terms enter as £ per MWh of the
    station's output at the road's load factor."""
    a = CT.station_margin("Longannet", 2015, 0.6)
    b = CT.station_margin("Longannet", 2015, 0.6, extra_gbp_mwh=-5.0)
    assert b["margin_before_filters_gbp_m"] - a["margin_before_filters_gbp_m"] == pytest.approx(-5.0 * a["twh"])


def _row(name):
    return next(r for r in _mixed() if r["closure_test"]["margin_name"] == name)


@pytest.mark.parametrize("name, before, after, want_close, want_ab", [
    ("Aberthaw B", -1.0, -50.0, date(2020, 3, 31), None),       # loses money: real date
    ("Cottam", 10.0, -50.0, date(2020, 6, 30), None),           # earns, filters don't pay: IED TNP deadline
    ("Cottam", 10.0, 5.0, None, "FGD+SCR"),                      # filters pay: fits them and runs on
    ("Ironbridge", 10.0, 5.0, date(2015, 12, 31), None),        # LCPD opt-out: no filters allowed, latest LCPD date
    ("Tilbury B", 10.0, -5.0, date(2013, 8, 31), None),         # LCPD opt-out: hours ran out, August 2013
    ("Ferrybridge C", 10.0, 5.0, date(2016, 3, 31), None),      # IED LLD: no datable close, real date (register)
])
def test_what_a_kept_station_does_next_follows_the_register(name, before, after, want_close, want_ab):
    close, ab, _ = CT.decide(_row(name), before, after)
    assert (close, ab) == (want_close, want_ab)


class _Fake:
    def __init__(self, name, close, rule="ied_tnp"):
        self.r = {"station": name, "unit": "all", "actual_close_d": close, "fossil_britain_close_d": close,
                  "abatement_needed": None, "capacity_mw": 100.0,
                  "closure_test": {"margin_name": name, "if_kept_close": "2020-06-30", "if_kept_rule": rule,
                                   "if_kept_source": "test"}}


def test_the_loop_repeats_until_the_list_stops_changing():
    """A closes 2016, B closes 2018. A earns at a high road load factor only. B earns only if A is kept (a toy
    coupling): round 1 keeps A; round 2 sees A kept and keeps B; round 3 changes nothing."""
    a, b = _Fake("A", date(2016, 3, 31)).r, _Fake("B", date(2018, 3, 31)).r

    def lf_of(year, overrides):
        return 0.65

    def margin_of(row, year, lf, overrides):
        if row["station"] == "A":
            return (1.0, -1.0)
        kept_a = any(o[0] == "A" and o[2] != "2016-03-31" for o in overrides)
        return (1.0, -1.0) if kept_a else (-1.0, -2.0)

    res = CT.fixed_point([a, b], lf_of, margin_of)
    got = {o[0]: o[2] for o in res["overrides"]}
    assert got == {"A": "2020-06-30", "B": "2020-06-30"}
    assert len(res["rounds"]) == 3 and res["converged"]


def test_a_loop_that_cycles_stops_loudly():
    a = _Fake("A", date(2016, 3, 31)).r

    def margin_of(row, year, lf, overrides):
        kept = any(o[2] != "2016-03-31" for o in overrides)
        return (-1.0, -2.0) if kept else (1.0, -1.0)          # kept -> loses, closed -> earns: no fixed point

    with pytest.raises(CT.NoFixedPoint):
        CT.fixed_point([a], lambda y, o: 0.65, margin_of)


def test_in_the_engine_cottam_runs_to_the_tnp_end_on_the_road():
    """Engine seam (`fossil_like_for_like.lfl_year` on the real register, central fleet settings). Cottam earns its
    keep at the road's 2018 load factor (hand-worked above, about £+79m) and its FGD+SCR (about £132m a year at 2018
    rates, stored file) would not pay, so on the road it runs to 30 June 2020: 2,000 MW x 181/366 of 2020. Under the
    register rule (the default) it closes on its real date, 30 Sept 2019, as in v4-s38."""
    from gascf import bills as B
    s = B.CENTRAL
    args = (2020, s.residual, s.margin, s.transport, s.closures, s.newbuild, str(L.CLOSURES_FILE), s.coal_lf,
            s.ic_basis)
    reg = L.lfl_year(*args)
    road = L.lfl_year(*args, closure_test="road_lf")
    share = {st: mw for st, unit, mw, _ in road.kept["stations"] if st == "Cottam"}
    assert share.get("Cottam") == pytest.approx(2000 * 181 / 366)
    assert not any(st == "Cottam" for st, *_ in reg.kept["stations"])
    ct = road.closure_test
    assert ct["rule"] == "road_lf" and ct["converged"]
    assert {(o[0], o[1]): o[2] for o in ct["overrides"]}[("Cottam", "all")] == "2020-06-30"
    assert reg.closure_test is None


@pytest.fixture(autouse=True)
def _stored_test_basis(monkeypatch):
    """v4-s39 (card [internal ticket]): the stored s24/s28/s37 margin tests were worked with carbon at gas intensity (M7
    'gas', v4-s38) on the register's MW; under the v4-s39 defaults (M7 merit order, 0167; edition MW, C-009) the
    margins move. These tests reproduce the stored files, so they set that basis explicitly."""
    from gascf import bills as B
    monkeypatch.setenv("GASCF_M7_CARBON_MARGINAL", "gas")
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)
    for f in (B.c_marg, CT._year_inputs, CT.station_margin):
        f.cache_clear()
    yield
    for f in (B.c_marg, CT._year_inputs, CT.station_margin):
        f.cache_clear()
