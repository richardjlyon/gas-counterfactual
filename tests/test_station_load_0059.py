"""Ticket 11 (0059): station load stays in Reliable Britain's residual for sizing and dispatch but is billed
in neither Britain. Spec `s36-routeA-spec-items/station-load.md`, tests 1-6.

Seam: `bills.build(Settings)` (the run-file export reads the same build). Builds that are compared with the
frozen v4-s35 run file read the real closure register (as the release does) under the v4-s35 interconnector
basis (`ic_basis="metered"`, `nuclear_cm_column=None`, as `test_metered_reproduces_v4_s35`).
Literals: the measured +765.5 £m over 2002-05 (2025 money) and the restated §5.3 residual +162.1 £m."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from gascf import bills as B

S35 = json.loads((Path(__file__).resolve().parents[1] / "out/v4/2026-10-14-s35.json").read_text())
EARLY = (2002, 2003, 2004, 2005)
# 0144 (v4-s37): v4-s35's extra running was at cost; the rest of the pre-0144 engine is set by pre_s37 below
from _pre_0133 import V4_S38     # v4-s39 (card [internal ticket]): the v4-s38 settings, explicit
V435 = replace(B.CENTRAL, **V4_S38, ic_basis="metered", nuclear_cm_column=None, extra_running="cost")


@pytest.fixture(scope="module")
def real_register():
    """The real register, and the margin as v4-s35 had it (decision 0133 moved it after; tests/_pre_0133.py), so the
    builds compared with the frozen v4-s35 run file move only by what this ticket moves."""
    from _pre_0133 import pre_s37
    from gascf import fossil_like_for_like as LFL
    mp = pytest.MonkeyPatch()
    mp.setenv(LFL.CLOSURES_ENV, str(LFL.CLOSURES_FILE))
    B.fleet_lfl.cache_clear()          # the cache key does not carry the register path
    with pre_s37():                    # and the engine before decision 0144 (v4-s37): tests/_pre_0133.py
        yield
    mp.undo()
    B.fleet_lfl.cache_clear()


@pytest.fixture(scope="module")
def b435(real_register):
    return B.build(V435)


@pytest.fixture(scope="module")
def central():
    return B.build(B.CENTRAL)


def _billed_equals_v(b):
    V = B.v_monthly()
    for y in B.YEARS:
        bm = b[y]["volume"]["billed_monthly_twh"]
        for m in range(1, 13):
            assert bm[m] == pytest.approx(V[(y, m)], abs=1e-9), (y, m)
        assert b[y]["volume"]["billed_twh"] == pytest.approx(b[y]["volume"]["v_twh"], abs=1e-9), y


def test_1_billed_volume_equals_v_on_both_sides_every_month(central):
    """Spec test 1: RB billed TWh (fleet + kept − unbilled station load) = V = NZ1's billed volume, by month."""
    _billed_equals_v(central)


def _step1_real(b, y):
    v = lambda i: B.val(b[y], i)                               # noqa: E731
    return B.real(v("NZ1") - b[y]["nz1c"]["national_gbp_m_nominal"] - v("GO1") - v("GO1k"), y)


def test_3_step1_2002_05_rises_by_the_measured_station_load(b435):
    """Spec test 3: step 1 (power before carbon), 2002-05, 2025 money, rises by 765.5 ± 10.0 £m against v4-s35;
    years within ± £5m of +106.0, +181.8, +196.0, +281.7.
    Re-pin, 24 Oct 2026 (card [internal ticket]; v4-s42, decision 0195): A2 (NI CCGT 2006 1,036 MW, and through the unchanged
    nearest-year fill 2002-05) moves the existing gas fleet 2002-05, so step 1 against v4-s35 is now 748.5 ± 10.0 £m:
    +107.3, +183.4, +175.8, +282.0 (work/[internal ticket]/repin_s42.py on this build; A2 alone on the candidate)."""
    d = {y: _step1_real(b435, y) - S35["waterfall"][str(y)][1]["value_gbp_m_real"] for y in EARLY}
    assert sum(d.values()) == pytest.approx(748.5, abs=10.0)
    for y, want in zip(EARLY, (107.3, 183.4, 175.8, 282.0)):
        assert d[y] == pytest.approx(want, abs=5.0), y


def test_6_pricing_residual_2002_05_after_0059(b435):
    """Spec test 6: res = (NZ1 − NZ1c) − GO1 market − GO1k, 2002-05, 2025 money = +162.1 ± 10.0 £m
    (−3.7, +20.9, +37.8, +107.1 ± £5m). Pinned to v4-s35 inputs; re-pinned on the s36 run (35), never loosened."""
    res = {}
    for y in EARLY:
        v = lambda i: B.val(b435[y], i)                        # noqa: E731
        res[y] = B.real(v("NZ1") - b435[y]["nz1c"]["national_gbp_m_nominal"]
                        - b435[y]["fleet"]["market_gbp_m"] - v("GO1k"), y)
    assert sum(res.values()) == pytest.approx(162.1, abs=10.0)
    for y, want in zip(EARLY, (-3.7, 20.9, 37.8, 107.1)):
        assert res[y] == pytest.approx(want, abs=5.0), y


def test_2_fleet_and_dispatch_unchanged_against_v4_s35(b435):
    """Spec test 2 (guard): fleet capacities, generation, energy, gas burn, merit-order uplift, residual peak and
    the CM split equal the frozen v4-s35 run file (v4-s35 interconnector basis, real register)."""
    keys = ("coal_gw", "ccgt_gw", "ocgt_gw", "spare_gw", "gen_twh", "energy_twh", "gas_burn_twh",
            "moe_gbp_m", "moe_kept_gbp_m")
    # v4-s42 (card [internal ticket], decision 0195): the (year, key) pairs the seven input fixes move against v4-s35 are
    # compared with the v4-s42 build's value (tests/fixtures/station_load_v4_s42_moves.json, written by
    # work/[internal ticket]/write_sl_fixture.py from repin_s42.py); every other pair is still v4-s35's exactly.
    # v4-s43 (card [internal ticket], decision 0197): the 2002-05 NI lists move 2002-05 again; the fixture now holds the
    # v4-s43 values (tests/fixtures/station_load_v4_s43_moves.json, work/[internal ticket]/repin_s43.py), every pair
    # outside 2002-05 equal to the v4-s42 fixture (the script refuses otherwise).
    s42 = json.loads((Path(__file__).parent / "fixtures/station_load_v4_s43_moves.json").read_text())["moves"]
    for y in B.YEARS:
        e = S35["fleet"][str(y)]
        for k in keys:
            want = s42[str(y)][k]["v4_s43"] if k in s42.get(str(y), {}) else e[k]
            assert b435[y]["fleet"][k] == pytest.approx(want, abs=1e-9), (y, k)
        if str(y) in S35["capacity_market"]:                 # the run file's CM block starts in 2016
            assert S35["capacity_market"][str(y)]["nz5_real"] == pytest.approx(B.real(B.val(b435[y], "NZ5"), y), abs=1e-6), y


def test_4_only_go1_and_its_vat_move(real_register, b435, monkeypatch):
    """Spec test 4, against the same build with the deduction set to 0 (the s36 lines that earlier tickets moved
    on purpose are in both builds, so v4-s35 itself is not the comparison): only GO1 and GO7 differ; GO1 moves by
    −station_load_unbilled_gbp_m and GO7 by the VAT rate × the domestic share × the GO1 move."""
    monkeypatch.setattr(B, "sl_unbilled_gbp_m", lambda y, f, s: 0.0)
    B.build.cache_clear()                    # build is lru_cached on Settings: V435 is already built with the deduction
    try:
        off = B.build(V435)
    finally:
        B.build.cache_clear()                # never leave the zero-deduction build in the cache
    from gascf import same_in_both
    rate = same_in_both.domestic_vat_rate()["rate"]
    for y in B.YEARS:
        on_l = {l["id"]: l["national_gbp_m_nominal"] for l in b435[y]["netzero"] + b435[y]["fossil"]}
        off_l = {l["id"]: l["national_gbp_m_nominal"] for l in off[y]["netzero"] + off[y]["fossil"]}
        assert {k: v for k, v in on_l.items() if k not in ("GO1", "GO7")} == pytest.approx(
            {k: v for k, v in off_l.items() if k not in ("GO1", "GO7")}, abs=1e-9), y
        d_go1 = on_l["GO1"] - off_l["GO1"]
        assert d_go1 == pytest.approx(-b435[y]["volume"]["station_load_unbilled_gbp_m"], abs=1e-9), y
        d = next(l for l in b435[y]["fossil"] if l["id"] == "GO7")["domestic_share"]
        assert on_l["GO7"] - off_l["GO7"] == pytest.approx(rate * d * d_go1, abs=1e-6), y


@pytest.mark.parametrize("over", [{"residual": "fuelhh"}, {"fleet": "all_new"}])
def test_5_billed_volume_equals_v_under_other_residual_and_fleet_paths(over):
    """Spec test 5: test 1 holds under residual='fuelhh' and fleet='all_new'."""
    _billed_equals_v(B.build(replace(B.CENTRAL, **over)))


def test_p1_p2_ruled_0108_station_load_at_price_less_carbon():
    """Decision 0108 (Richard Lyon, 19 Oct 2026): item 1.5 option (b), the all-new fleet values station load at price
    less carbon (the central rule, one rule); item 1.6 option (a), under kept_price = fleet_avg the deduction stays at
    price less carbon. Both are now the defaults, no longer placeholders. Checked on a synthetic fleet average far from
    any market price, so a fleet-average deduction cannot pass."""
    from dataclasses import replace
    from gascf import bills as B
    assert B.CENTRAL.sl_all_new_price == "less_carbon" and B.ALL_NEW.sl_all_new_price == "less_carbon"
    assert B.CENTRAL.sl_kept_price == "less_carbon"
    f = {"gbp_per_mwh": 9999.0}
    for y in (2003, 2015, 2024):
        lc = B.sl_unbilled_gbp_m(y, f, B.CENTRAL)                                     # like for like, P - C
        assert B.sl_unbilled_gbp_m(y, f, B.ALL_NEW) == pytest.approx(lc, abs=1e-9), y
        assert B.sl_unbilled_gbp_m(y, f, replace(B.CENTRAL, kept_price="fleet_avg")) == pytest.approx(lc, abs=1e-9), y
