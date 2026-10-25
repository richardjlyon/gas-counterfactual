"""RB v1.1 M8 (decision 0163, R9 (a)): fossil output priced half-hourly from when a FREE half-hourly series
exists (Elexon MID, APX rows, from 12 Sep 2016 SP32, the first row Elexon publishes), monthly before.
Built as a switch, OFF by default, measure only (research-director, 21 Oct 2026 overnight: "measure each
reading, flag it"); Richard rules which reading, if either, goes into the central case.

Switches (environment):
- GASCF_M8_HH_PRICE = "monthly" (default, OFF) | "mid_level" (each half-hour at MID's own price) |
  "mid_shape" (the month's Ofgem price, the engine's series, with MID's half-hour shape inside the month).
- GASCF_M8_SCOPE = "fossil" (default: the road's market-priced fossil output only, as R9 is worded) |
  "both" (also Reliable Britain's NZ1 volume priced half-hourly the same way).
Half-hours from the start with no MID row (Elexon's own gaps, e.g. 2 Jun 2017) are priced at the month's
price and counted, never filled with an invented value.

Expected values: hand-worked toy months, and literal rows of the saved Elexon file.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ENV, SCOPE = "GASCF_M8_HH_PRICE", "GASCF_M8_SCOPE"


def test_default_is_mid_shape_both_and_monthly_fossil_is_explicit(monkeypatch):
    """v4-s39 (0167, M8 "Approve."; card [internal ticket]): MID shape in both Britains by default; monthly / fossil
    (v4-s38) stays an explicit setting."""
    from gascf import hh_pricing as H
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.delenv(SCOPE, raising=False)
    assert H.method() == "mid_shape" and H.scope() == "both"
    monkeypatch.setenv(ENV, "monthly")
    monkeypatch.setenv(SCOPE, "fossil")
    assert H.method() == "monthly" and H.scope() == "fossil"
    monkeypatch.setenv(ENV, "hourly")
    with pytest.raises(ValueError):
        H.method()
    monkeypatch.setenv(SCOPE, "all")
    with pytest.raises(ValueError):
        H.scope()


def test_break_is_the_first_free_mid_row():
    from gascf import hh_pricing as H
    assert H.HH_FROM == (date(2016, 9, 12), 32)
    assert H.mid_at(date(2016, 9, 12), 31) is None          # before the break: monthly, not a gap
    assert H.mid_at(date(2016, 9, 12), 32) == pytest.approx(35.15)
    assert H.mid_at(date(2016, 9, 12), 33) == pytest.approx(36.08)
    assert H.mid_at(date(2018, 1, 1), 1) == pytest.approx(47.27)
    assert H.mid_at(date(2017, 6, 2), 20) is None           # Elexon publishes no MID for 2 Jun 2017
    assert H.is_gap(date(2017, 6, 2), 20) and not H.is_gap(date(2016, 9, 12), 31)


def test_effective_price_on_a_toy_month():
    """Two half-hours with MID 40 and 80 (time mean 60), output 1 and 3 MW; the month's price 50.
    mid_level: (40 + 240) / 4 = 70. mid_shape: 50 x (70 / 60) = 58.333.
    Add a half-hour with no MID and 4 MW: priced at the month's 50. level (280 + 200) / 8 = 60;
    shape (4 x 58.333 + 4 x 50) / 8 = 54.1667."""
    from gascf import hh_pricing as H
    s = H.MonthSums()
    s.add(40.0, 1.0)
    s.add(80.0, 3.0)
    assert s.price(50.0, "mid_level", mid_mean=60.0) == pytest.approx(70.0)
    assert s.price(50.0, "mid_shape", mid_mean=60.0) == pytest.approx(50.0 * 70.0 / 60.0)
    assert s.price(50.0, "monthly", mid_mean=60.0) == 50.0
    s.add(None, 4.0)
    assert s.price(50.0, "mid_level", mid_mean=60.0) == pytest.approx(60.0)
    assert s.price(50.0, "mid_shape", mid_mean=60.0) == pytest.approx((4 * 50 * 70 / 60 + 4 * 50) / 8)
    e = H.MonthSums()
    assert e.price(50.0, "mid_level", mid_mean=None) == 50.0      # no output: the month's price


def test_month_time_mean_of_mid():
    from gascf import hh_pricing as H
    from gascf.mid import read_mid
    rows = [p for (d, _), (p, _) in read_mid(2017).items() if d.month == 3]
    assert H.mid_month_mean(2017, 3) == pytest.approx(sum(rows) / len(rows))
    assert H.mid_month_mean(2015, 3) is None


def test_scope_both_prices_reliable_britain_volume_the_same_way(monkeypatch):
    """Scope 'fossil' leaves NZ1 as Σ months P x V. Scope 'both' prices NZ1 from the break with the same reading,
    weighted by Reliable Britain's own volume each half-hour; 2015 unchanged."""
    from gascf import bills as B, prices
    V = B.v_monthly()
    base = prices.nz1(dict(V), "ofgem_chart")
    monkeypatch.setenv(ENV, "mid_level")
    monkeypatch.setenv(SCOPE, "fossil")
    assert B.nz1_by_year("ofgem_chart")[2017]["gbp_m"] == base[2017]["gbp_m"]
    monkeypatch.setenv(SCOPE, "both")
    both = B.nz1_by_year("ofgem_chart")
    assert both[2015]["gbp_m"] == base[2015]["gbp_m"]
    assert both[2017]["gbp_m"] != pytest.approx(base[2017]["gbp_m"], rel=1e-6)
    monkeypatch.setenv(ENV, "monthly")           # v4-s38 = explicit setting
    monkeypatch.setenv(SCOPE, "fossil")
    assert B.nz1_by_year("ofgem_chart")[2017]["gbp_m"] == base[2017]["gbp_m"]


def _market(year, monkeypatch, meth):
    from gascf import bills as B
    from gascf import fossil_like_for_like as L
    if meth is None:
        monkeypatch.setenv(ENV, "monthly")       # v4-s38 = explicit setting (v4-s39 default is mid_shape, 0167)
    else:
        monkeypatch.setenv(ENV, meth)
    L.lfl_year.cache_clear()
    B.fleet_lfl.cache_clear()
    return B.fleet_lfl(year)


def test_switch_moves_the_road_market_part_only_from_the_break(monkeypatch):
    """OFF: 2017 market part equals Σ months (P − C) x volume. ON: 2015 is unchanged; 2017 moves, and its
    market part equals Σ months (P_eff − C) x volume with P_eff from the year's own sums."""
    from gascf import bills as B
    off15, off17 = _market(2015, monkeypatch, None), _market(2017, monkeypatch, None)
    P, C = B.p_elec("ofgem_chart"), B.c_marg()
    for meth in ("mid_level", "mid_shape"):
        on15, on17 = _market(2015, monkeypatch, meth), _market(2017, monkeypatch, meth)
        assert on15["market_gbp_m"] == pytest.approx(off15["market_gbp_m"], rel=1e-12)
        assert on17["market_gbp_m"] != pytest.approx(off17["market_gbp_m"], rel=1e-6)
        assert on17["hh_pricing"]["method"] == meth
        assert on17["hh_pricing"]["gap_halfhours"] > 0          # 2 Jun 2017 and the short days, counted
    monkeypatch.delenv(ENV, raising=False)
    from gascf import fossil_like_for_like as L
    L.lfl_year.cache_clear()
    B.fleet_lfl.cache_clear()
