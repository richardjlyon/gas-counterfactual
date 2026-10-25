"""Decision 0167 (generators' share, "a"; card [internal ticket]): the net-zero part of the generators' share of BSUoS
and TNUoS (with their half of constraints and turn-up) counted as a cost of real Britain, WAY 2: both bills stay
as they are (NZ6/NZ7 and GO4/GO5 with the generators' share removed, decision 0024), and the generators' net-zero
charge is taken out of fossil Britain's market price (fossil Britain is priced at the actual market price, which
carries that charge, so until now it cancelled). Switch `Settings.gen_nz_charge`: 'none' (default, OFF) |
'fossil_price' (way 2).

The charge per MWh in year y is the net-zero part D(y) spread over the power real Britain billed, V(y):
  D(y) = [NZ6 whole - NZ6 removed] - [GO4 whole - GO4 removed]   (BSUoS: actual generators' part less fossil
         + [NZ7 whole - NZ7 removed] - [GO5 whole - GO5 removed]  Britain's own; the same for TNUoS)
  delta(y) = D(y) / V(y), £/MWh, taken off every MWh fossil Britain buys at the market price: the actual fossil
  output and the extra running (0144 1A), the kept nuclear, imports and storage (GO1k), less the station load
  not billed (0059). New plant priced at its cost is not touched.

Expected values: literals from the shared cost register ([internal ticket], rows engine.*_generators_share, read from
the v4-s37 release run file 2026-10-20-s37.json), hand-worked toy numbers, and the billing identity
fleet + kept - station load = V (0059 D3).
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ------------------------------------------------------------------ the switch

def test_module_default_is_off_and_the_v4_s39_central_is_way_2():
    """The module's own default stays 'none' (v4-s38); the v4-s39 central sets way 2 (0167, card [internal ticket])."""
    from gascf import bills as B
    from gascf import gen_nz_charge as G
    assert G.DEFAULT == "none"
    assert B.Settings().gen_nz_charge == "fossil_price"
    assert set(G.OPTIONS) == {"none", "fossil_price"}


def test_unknown_option_is_refused():
    from gascf import gen_nz_charge as G
    with pytest.raises(ValueError):
        G.check("included")


# ------------------------------------------------------------------ the arithmetic (toy numbers, by hand)

def test_net_zero_part_is_real_less_fossil_generators_part():
    """Whole 1,000, removed 530 (generators 470); fossil whole 600, removed 318 (generators 282): 470 - 282 = 188."""
    from gascf import gen_nz_charge as G
    got = G.net_zero_part({2020: 1000.0}, {2020: 530.0}, {2020: 600.0}, {2020: 318.0}, [2020])
    assert got == {2020: pytest.approx(188.0)}


def test_series_spreads_the_charge_over_real_britains_billed_power():
    """BSUoS part 100 + TNUoS part 50 = £150m over 300 TWh = £0.50/MWh (£m / TWh = £/MWh)."""
    from gascf import gen_nz_charge as G
    s = G.series({2010: 100.0}, {2010: 50.0}, {2010: 300.0}, [2010])
    assert s[2010]["bsuos_gbp_m"] == 100.0 and s[2010]["tnuos_gbp_m"] == 50.0
    assert s[2010]["gbp_m"] == pytest.approx(150.0)
    assert s[2010]["v_twh"] == 300.0
    assert s[2010]["gbp_per_mwh"] == pytest.approx(0.5)


def test_series_refuses_a_year_with_no_billed_power():
    from gascf import gen_nz_charge as G
    with pytest.raises(ValueError):
        G.series({2010: 1.0}, {2010: 1.0}, {2010: 0.0}, [2010])


# ------------------------------------------------------------------ the engine's parts against the register
# The register's engine.*_generators_share rows ([internal ticket]) were derived as line x s / (1 - s) with the CALENDAR
# share s. That is exact only where both charging years in the calendar year carry the same share (BSUoS 50% to
# FY2012/13 and 0 from FY2023/24; TNUoS 27% to FY2014/15); elsewhere it is line arithmetic, not the engine's own
# charging-year sum (e.g. BSUoS 2023: register 370.4, engine 490.4). Only the flat-share years are literals here.

# v4-s42 (D1 basis (i), decision 0195): 2010 is the v4-s42 register row rb.BSUOS.generators_share_out 2010, -356.006228
# (v4-s39 register -418.117474): FY2010/11 balancing 685.78, not 851.41.
@pytest.mark.parametrize("year, want", [(2010, 356.006228), (2024, 0.0)])
def test_real_britains_bsuos_generators_part_equals_the_register(year, want):
    """Register rows engine.NZ6_generators_share (cash £m, v4-s37 run file)."""
    from gascf import balancing
    whole, rem = balancing.nz6(gen_share="included"), balancing.nz6(gen_share="removed")
    assert whole[year]["gbp_m"] - rem[year]["gbp_m"] == pytest.approx(want, abs=1e-4)


@pytest.mark.parametrize("year, want", [(2005, 274.796993), (2010, 415.19925)])
def test_real_britains_tnuos_generators_part_equals_the_register(year, want):
    """Register rows engine.NZ7_generators_share (cash £m, v4-s37 run file)."""
    from gascf import grid
    whole, rem = grid.nz7(gen_share="included"), grid.nz7(gen_share="removed")
    assert whole[year]["gbp_m"] - rem[year]["gbp_m"] == pytest.approx(want, abs=1e-4)


@pytest.mark.parametrize("year, want", [(2005, 277.821038), (2010, 341.276801)])
def test_fossil_britains_tnuos_generators_part_equals_the_register(year, want):
    """Register rows engine.GO5_generators_share (cash £m, v4-s37 run file; GO5 does not depend on the fleet)."""
    from gascf import bills as B, grid
    whole = grid.go5(B.PRICE_BASE, B.YEARS, "rpi", "included")
    rem = grid.go5(B.PRICE_BASE, B.YEARS, "rpi", "removed")
    assert whole[year]["gbp_m"] - rem[year]["gbp_m"] == pytest.approx(want, abs=1e-4)


# ------------------------------------------------------------------ the bills (two central builds, heavy)

@pytest.fixture(scope="module")
def both():
    """Two central builds on the real register: the v4-s39 central (M2 closure test) needs the register's
    closure_test data, which the conftest fixture register does not carry."""
    from gascf import bills as B
    from gascf import fossil_like_for_like as L
    from _pre_0133 import s39_caches
    # build caches are keyed on settings, not on the register: clear them either side so these real-register builds
    # are neither read from nor left for the fixture-register tests (card [internal ticket])
    for f in s39_caches():
        f.cache_clear()
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(L.CLOSURES_ENV, str(Path(__file__).resolve().parents[1] / "reference/fossil_closures.yaml"))
        off = B.build(replace(B.CENTRAL, gen_nz_charge="none"))     # v4-s38 = explicit setting
        on = B.build(B.CENTRAL)                                      # v4-s39 central: way 2
    for f in s39_caches():
        f.cache_clear()
    return B, off, on


def _v(b, lid):
    from gascf import bills as B
    return B.val(b, lid)


def test_switch_on_leaves_both_bills_lines_but_the_fossil_price_unchanged(both):
    B, off, on = both
    for y in B.YEARS:
        for l in off[y]["netzero"]:
            assert _v(on[y], l["id"]) == l["national_gbp_m_nominal"], (y, l["id"])
        for lid in ("GO2", "GO3", "GO4", "GO5", "GO6"):
            assert _v(on[y], lid) == _v(off[y], lid), (y, lid)
        assert on[y]["totals"]["s1_gbp_m"] == off[y]["totals"]["s1_gbp_m"]


def test_switch_on_takes_delta_off_every_market_priced_mwh_of_fossil_britain(both):
    """GO1 + GO1k fall by delta x (actual fossil + extra running at market + kept - station load); by the billing
    identity that volume is V less the new plant's output priced at cost."""
    B, off, on = both
    for y in B.YEARS:
        g = on[y]["fleet"]["gen_nz_charge"]
        f, vol = on[y]["fleet"], on[y]["volume"]
        new_twh = f["gen_twh"]["new_ccgt"] + f["gen_twh"]["new_ocgt"] + f["gen_twh"]["new_coal"]
        market_billed = vol["v_twh"] - new_twh
        cut = (_v(off[y], "GO1") + _v(off[y], "GO1k")) - (_v(on[y], "GO1") + _v(on[y], "GO1k"))
        assert cut == pytest.approx(g["gbp_per_mwh"] * market_billed, rel=1e-9, abs=1e-6), y
        assert g["fossil_cut_gbp_m"] == pytest.approx(cut, rel=1e-12, abs=1e-9), y


def test_the_charge_is_the_net_zero_part_of_both_charges(both, monkeypatch, request):
    """D(y) from the four lines, each whole less removed, read independently of the build."""
    from gascf import balancing, grid
    from gascf import fossil_like_for_like as L
    from _pre_0133 import s39_caches
    B, off, on = both
    # GO4 reads the fleet's gas feedback, so read it on the register the builds used (card [internal ticket])
    monkeypatch.setenv(L.CLOSURES_ENV, str(Path(__file__).resolve().parents[1] / "reference/fossil_closures.yaml"))
    for f in s39_caches():
        f.cache_clear()
    request.addfinalizer(lambda: [f.cache_clear() for f in s39_caches()])
    s = B.CENTRAL
    nz6w, nz6r = balancing.nz6(B.YEARS, "included"), balancing.nz6(B.YEARS, "removed")
    nz7w, nz7r = grid.nz7(B.YEARS, "included"), grid.nz7(B.YEARS, "removed")
    go4w, go4r = B.go4_line(replace(s, bsuos_gen="included")), B.go4_line(s)
    go5w = grid.go5(B.PRICE_BASE, B.YEARS, s.go5_index, "included")
    go5r = grid.go5(B.PRICE_BASE, B.YEARS, s.go5_index, "removed")
    for y in B.YEARS:
        g = on[y]["fleet"]["gen_nz_charge"]
        b = (nz6w[y]["gbp_m"] - nz6r[y]["gbp_m"]) - (go4w[y]["gbp_m"] - go4r[y]["gbp_m"])
        t = (nz7w[y]["gbp_m"] - nz7r[y]["gbp_m"]) - (go5w[y]["gbp_m"] - go5r[y]["gbp_m"])
        assert g["bsuos_gbp_m"] == pytest.approx(b, abs=1e-9), y
        assert g["tnuos_gbp_m"] == pytest.approx(t, abs=1e-9), y
        assert g["gbp_per_mwh"] == pytest.approx((b + t) / on[y]["volume"]["v_twh"], rel=1e-12), y


def test_gap_rises_by_the_cut_and_its_vat(both):
    B, off, on = both
    for y in B.YEARS:
        cut = on[y]["fleet"]["gen_nz_charge"]["fossil_cut_gbp_m"]
        d = B.line(on[y], "GO7")["domestic_share"]
        want = cut * (1 + 0.05 * d)
        assert on[y]["totals"]["gap_gbp_m"] - off[y]["totals"]["gap_gbp_m"] == pytest.approx(want, rel=1e-9, abs=1e-6)


def test_switch_off_is_the_v4_s38_build(both):
    B, off, on = both
    for y in B.YEARS:
        assert "gen_nz_charge" not in off[y]["fleet"]
