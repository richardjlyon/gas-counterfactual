"""Ticket 12 (0044, 0101): Reliable Britain's CCL (NZ8) counted only above its 2001 level, on the shared on-the-road
component (ticket 26) in rate x volume mode, less the capped LEC exemption. Spec
`s36-routeA-spec-items/ccl-2001-baseline.md`, tests written first, one at a time.

Seams: `gascf.on_the_road.net` (shared with 26) and `bills.build(Settings)`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gascf import on_the_road as OTR

FIX = Path(__file__).resolve().parent / "fixtures/otr_rate_x_volume.json"


def _shared_fixture():
    f = json.loads(FIX.read_text())
    ints = lambda d: {int(k): v for k, v in d.items()}            # noqa: E731
    return f, ints


def test_1_rate_x_volume_on_the_2001_rate_negative_not_clipped():
    """Spec test 1 (and 11, the shared pattern): through the component, NZ8 £100m at 0.43p all year with
    CPIH(y)/CPIH(2001) = 1.1 gives an on-the-road levy of £110m and counted NZ8 -£10m (negative, not clipped)."""
    f, ints = _shared_fixture()
    r = OTR.net(ints(f["counted"]), f["rate_2001_gbp_per_kwh"], mode="rate_x_volume", indexation="real_cpih",
                volume=ints(f["volume_gwh"]), index=ints(f["index"]), applies_to="NZ8")
    assert r["netted"] == pytest.approx(ints(f["expected_netted"]), abs=1e-9)
    assert r["counted"] == pytest.approx(ints(f["expected_counted"]), abs=1e-9)


def test_2_calendar_year_rate_by_quarter_three_quarters_and_inferred_volume():
    """Spec test 2 (D2): the calendar-year main rate is 1/4 x the rate from 1 April (y-1) + 3/4 x the rate from
    1 April y; 2019: 0.25 x 0.583p + 0.75 x 0.847p = 0.781p, and the inferred taxable volume is NZ8 / 0.781p.
    Every electricity main rate is the one printed in HMRC's historical rates table (vendored html)."""
    from gascf import ccl_baseline as CB
    assert CB.cy_rate(2019) == pytest.approx(0.25 * 0.00583 + 0.75 * 0.00847, abs=1e-12)
    assert CB.inferred_volume_gwh(781.0, 2019) == pytest.approx(781.0 / (0.25 * 0.00583 + 0.75 * 0.00847), rel=1e-12)
    html = CB.RATES_HTML.read_text()
    assert all(f"£{r:.5f}".rstrip("0") in html for r in CB.RATES.values()), CB.RATES
    assert CB.RATES[2001] == 0.0043


# ---- build seam. Sums in 2024 prices (CPIH L522), £bn, as ccl-calc/ccl.json and ccl2.json.
from dataclasses import replace                                    # noqa: E402

from gascf import bills as B                                       # noqa: E402
from gascf.deflator_cpih import to_real                            # noqa: E402

P = {"2002-05": range(2002, 2006), "2002-24": range(2002, 2025), "2002-25": range(2002, 2026)}


def _nz8(b, y):
    return next(l["national_gbp_m_nominal"] for l in b[y]["netzero"] if l["id"] == "NZ8")


def _bn(f, ys):
    return sum(to_real(f(y), y, 2024) for y in ys) / 1e3


@pytest.fixture(scope="module")
def central():
    return B.build(B.CENTRAL)


@pytest.fixture(scope="module")
def whole():
    """The same build with the whole levy counted (no 0044 netting): what No. 2 counts."""
    return B.build(replace(B.CENTRAL, ccl_baseline="none"))


# literals from ccl-calc/ccl.json (sha256 58e1ca3c...), copied so the test does not depend on the programme folder
CCL_B_COUNTED = {"2002-05": -0.142, "2002-24": -0.106, "2002-25": -0.126}
NZ8_BY_YEAR = {2002: 606.7, 2003: 605.2, 2004: 555.8, 2005: 519.3, 2006: 511.7, 2007: 500.5, 2008: 528.1, 2009: 515.6,
               2010: 472.1, 2011: 486.0, 2012: 435.6, 2013: 301.8, 2014: 250.8, 2015: 315.8, 2016: 567.0, 2017: 637.7,
               2018: 687.0, 2019: 885.6, 2020: 812.6, 2021: 784.3, 2022: 787.8, 2023: 764.5, 2024: 784.2, 2025: 773.9}
CF_B = {2002: 615.7, 2003: 622.2, 2004: 579.7, 2005: 552.7, 2006: 558.4, 2007: 548.4, 2008: 580.2, 2009: 560.0,
        2010: 521.6, 2011: 544.8, 2012: 479.2, 2013: 328.3, 2014: 268.2, 2015: 330.5, 2016: 591.9, 2017: 673.1,
        2018: 724.6, 2019: 704.6, 2020: 622.1, 2021: 643.6, 2022: 706.0, 2023: 731.3, 2024: 775.1, 2025: 794.3}
B_NEGATIVE_YEARS = list(range(2002, 2019)) + [2025]


def test_3_d3_reproduces_ccl_json_b_cpih(central, whole):
    """Spec test 3 (D3, 0044 central basis): the on-the-road levy nz8_on_the_road_gbp_m equals ccl.json `cf_b` by
    year to 0.1 £m (on the whole levy, which equals `nz8` by year to 0.1); the CCL counted after D3 alone sums to
    -0.106 (2002-24), -0.126 (2002-25), -0.142 (2002-05) £bn to ±0.001; negative years [2002-2018, 2025]."""
    for y in B.YEARS:
        assert _nz8(whole, y) == pytest.approx(NZ8_BY_YEAR[y], abs=0.05), y
        assert central[y]["on_the_road"]["nz8_on_the_road_gbp_m"] == pytest.approx(CF_B[y], abs=0.05), y
    d3 = lambda y: _nz8(whole, y) - central[y]["on_the_road"]["nz8_on_the_road_gbp_m"]   # noqa: E731
    for k, ys in P.items():
        assert _bn(d3, ys) == pytest.approx(CCL_B_COUNTED[k], abs=0.001), k
    assert [y for y in B.YEARS if d3(y) < 0] == B_NEGATIVE_YEARS


LEC_CY = {2002: (5805915, 2290044, 12), 2003: (7023838, 2770433, 12), 2004: (9233669, 3642063, 12),
          2005: (12151416, 6152754, 12), 2006: (13723905, 7463192, 12), 2007: (14917564, 8112315, 12),
          2008: (17590994, 10224858, 12), 2009: (19228883, 11791295, 12), 2010: (21033080, 13773952, 12),
          2011: (27714894, 19920635, 12), 2012: (32738855, 24875672, 12), 2013: (44401938, 36433292, 12),
          2014: (52519936, 44441151, 12), 2015: (17422771, 14808214, 3)}     # ccl-calc/lec.json `cy` (c2729d5c...)


def test_4a_lec_volumes_reproduce_lec_json():
    """Spec test 4, input half (D5): GB LECs issued by calendar year, all technologies and RB's technologies, equal
    ccl-calc/lec.json to 1 MWh (rounded), from the five staged Ofgem files; 2015 has 3 months (Jan-Mar)."""
    from gascf import lec
    got = lec.gb_rbtech_mwh_by_cy()
    assert sorted(got) == list(range(2002, 2016))
    for y, (allv, rbv, n) in LEC_CY.items():
        assert round(got[y]["gb_all_mwh"]) == allv, y
        assert round(got[y]["gb_rbtech_mwh"]) == rbv, y
        assert got[y]["months"] == n, y


REPLACED_TWH = {2002: 1.256, 2003: 1.285, 2004: 1.935, 2005: 2.904, 2006: 4.225, 2007: 5.274, 2008: 7.123,
                2009: 8.907, 2010: 10.133, 2011: 15.419, 2012: 20.86, 2013: 31.414, 2014: 40.853,
                2015: 54.838}                                       # ccl-calc/ccl2.json `replaced_twh` (a4ebfb5d...)


def test_4b_lec_exemption_capped_reproduces_ccl2_json(central):
    """Spec test 4 (D5, cap ruling): the extra counterfactual levy on RB-technology LECs, capped each year at RB's own
    replaced renewables volume, x the 2001 rate indexed by CPIH x the GB share, sums to 1.241 (2002-24), 1.241
    (2002-25), 0.055 (2002-05) £bn to ±0.001 (`b_cpih|lec_capped|extra_levy`); capped in 2002-14, not in 2015;
    zero from 2016; the cap is the same run's replaced renewables volume (= ccl2.json `replaced_twh` to 0.001 TWh)."""
    lec = lambda y: central[y]["on_the_road"]["nz8_lec_exempt_gbp_m"]          # noqa: E731
    for k, ys in P.items():
        assert _bn(lec, ys) == pytest.approx({"2002-05": 0.055, "2002-24": 1.241, "2002-25": 1.241}[k], abs=0.001), k
    for y in range(2002, 2016):
        assert central[y]["fleet"]["renewables_replaced_twh"] == pytest.approx(REPLACED_TWH[y], abs=0.0005), y
        assert central[y]["on_the_road"]["nz8_lec_capped"] is (y <= 2014), y
    assert all(lec(y) == 0.0 for y in range(2016, 2026))


def _others(b, y):
    return {l["id"]: l["national_gbp_m_nominal"] for l in b[y]["netzero"] if l["id"] != "NZ8"}


def test_5_cash_frozen_switch_a_cash_lec_capped_moves_only_nz8(central, whole):
    """Spec test 5 (D3 cash, its own named sensitivity `ccl_2001_cash_frozen`, apart from 26's cash-flat case): the
    METHOD_SWITCHES row is the central case with the 2001 rate held cash-frozen. CCL counted after D3 alone sums to
    3.627 (2002-24), 3.958 (2002-25), 0.000 (2002-05) £bn (ccl.json `a_cash` ccl_counted) and the capped LEC extra
    levy to 0.983 / 0.983 / 0.053 (ccl2.json `a_cash|lec_capped|extra_levy`), ±0.001. Every other net zero line is
    unchanged against central to 1e-9 (only NZ8 moves)."""
    assert B.SWITCHES[B.CCL_CASH_FROZEN] == (replace(B.CENTRAL, ccl_baseline="cash_2001"),)
    cf = B.build(*B.SWITCHES[B.CCL_CASH_FROZEN])
    d3 = lambda y: _nz8(whole, y) - cf[y]["on_the_road"]["nz8_on_the_road_gbp_m"]   # noqa: E731
    lec = lambda y: cf[y]["on_the_road"]["nz8_lec_exempt_gbp_m"]                    # noqa: E731
    for k, ys in P.items():
        assert _bn(d3, ys) == pytest.approx({"2002-05": 0.0, "2002-24": 3.627, "2002-25": 3.958}[k], abs=0.001), k
        assert _bn(lec, ys) == pytest.approx({"2002-05": 0.053, "2002-24": 0.983, "2002-25": 0.983}[k], abs=0.001), k
    for y in B.YEARS:
        assert _others(cf, y) == pytest.approx(_others(central, y), abs=1e-9), y


def _nz8_note(b, y):
    return next(l.get("years_note") or "" for l in b[y]["netzero"] if l["id"] == "NZ8")


def test_6_uncapped_note_run_b_cpih_lec_uncapped():
    """Spec test 6 (D5 alternative, for the note on 0044's cap ruling): with the cap off, the extra levy on all
    RB-technology LEC output sums to 1.542 (2002-24), 1.542 (2002-25), 0.111 (2002-05) £bn ±0.001
    (ccl2.json `b_cpih|lec_uncapped|extra_levy`); the NZ8 line's note says the LEC part is uncapped, not capped."""
    un = B.build(replace(B.CENTRAL, ccl_lec_cap=False))
    lec = lambda y: un[y]["on_the_road"]["nz8_lec_exempt_gbp_m"]                    # noqa: E731
    for k, ys in P.items():
        assert _bn(lec, ys) == pytest.approx({"2002-05": 0.111, "2002-24": 1.542, "2002-25": 1.542}[k], abs=0.001), k
    for y in range(2002, 2016):
        assert "uncapped" in _nz8_note(un, y) and "capped at RB" not in _nz8_note(un, y), (y, _nz8_note(un, y))


# calibration-residual.md row "CCL counted, £m: today / (b) / (b)+LEC", 2002-05 in 2025 money
CAL_ROW = {2002: (1106.0, -16.3, -26.0), 2003: (1088.9, -30.7, -40.6), 2004: (985.9, -42.3, -57.3),
           2005: (902.5, -58.1, -80.6)}


def test_7_2002_05_counted_ccl_by_year_matches_calibration_residual(central, whole):
    """Spec test 7: in 2025 money, the whole levy, the levy counted after D3 alone and the counted NZ8 (D3 + D5) equal
    calibration-residual.md's today / (b) / (b)+LEC row by year 2002-05 to 0.05 £m: -26.0, -40.6, -57.3, -80.6."""
    for y, (today, b_only, b_lec) in CAL_ROW.items():
        assert to_real(_nz8(whole, y), y, 2025) == pytest.approx(today, abs=0.05), y
        d3 = _nz8(whole, y) - central[y]["on_the_road"]["nz8_on_the_road_gbp_m"]
        assert to_real(d3, y, 2025) == pytest.approx(b_only, abs=0.05), y
        assert to_real(_nz8(central, y), y, 2025) == pytest.approx(b_lec, abs=0.05), y


def test_10_only_nz8_moves_and_the_gap_moves_by_d3_plus_d5(central, whole):
    """Spec test 10: against the same build without 0044 (`ccl_baseline="none"`), every other net zero line (NZ11
    included, CCL carries no domestic VAT), every fossil line and the same-in-both lines equal their values to 1e-9;
    NZ8 and the gap move by exactly -(D3 part + D5 part)."""
    for y in B.YEARS:
        assert _others(central, y) == pytest.approx(_others(whole, y), abs=1e-9), y
        for sec in ("fossil", "same_in_both"):
            got = {l["id"]: l["national_gbp_m_nominal"] for l in central[y][sec]}
            ref = {l["id"]: l["national_gbp_m_nominal"] for l in whole[y][sec]}
            assert got == pytest.approx(ref, abs=1e-9), (y, sec)
        o = central[y]["on_the_road"]
        move = -(o["nz8_on_the_road_gbp_m"] + o["nz8_lec_exempt_gbp_m"])
        assert _nz8(central, y) - _nz8(whole, y) == pytest.approx(move, abs=1e-9), y
        assert (central[y]["totals"]["gap_gbp_m"] - whole[y]["totals"]["gap_gbp_m"]) == pytest.approx(move, abs=1e-9), y


def test_8c_run_file_block_carries_the_d3_and_d5_parts_nominal_and_2024(central):
    """Spec user story 8 / D-lines: the 2001-levy part (D3) and the LEC part (D5) are exported as their own engine lines
    through the on_the_road run-file block, nominal and 2024 £ by year, with the capped flag, so 27 builds No. 2's
    bridge rows 8b and 8c from the run; the block names both decisions."""
    from gascf import otr_blocks
    blk = otr_blocks.on_the_road_block(central)
    assert "0044" in blk["decision"] and "0097" in blk["decision"]
    for y in B.YEARS:
        r, o = blk["years"][str(y)], central[y]["on_the_road"]
        for k in ("nz8_on_the_road_gbp_m", "nz8_lec_exempt_gbp_m"):
            assert r[k] == o[k], (y, k)
            assert r[k.replace("_gbp_m", "_gbp_m_2024")] == pytest.approx(to_real(o[k], y, 2024), rel=1e-12), (y, k)
        assert r["nz8_lec_capped"] is o["nz8_lec_capped"], y


def test_8a_waterfall_step7_is_the_netted_nz8_and_carbon_is_not_in_it(central):
    """Mapping keys, engine half (`test_wf_ccl_extra_is_step7_netted`, `test_no_double_count_carbon_and_ccl_steps`;
    the figures.json keys come at the A2 merge): waterfall step 7 is NZ8 alone, after the netting, so Σ2002-24 of
    step 7 in 2024 £bn is the D3-counted -0.106 less the capped LEC extra levy 1.241 = -1.347 ±0.002; no NZ1c id in
    step 7, no NZ8 in step 2."""
    from gascf import waterfall as W
    tot = 0.0
    for y in P["2002-24"]:
        st = {r["step"]: r for r in W.steps_for(central[y], y)}
        assert st[7]["lines"] == ["NZ8"], y
        assert st[7]["value_gbp_m_nominal"] == pytest.approx(_nz8(central, y), abs=1e-9), y
        assert not {"NZ1c", "NZ1c_tax", "NZ1c_price"} & set(st[7]["lines"]) and "NZ8" not in st[2]["lines"], y
        tot += to_real(st[7]["value_gbp_m_nominal"], y, 2024) / 1e3
    assert tot == pytest.approx(-0.106 - 1.241, abs=0.002)


def _carbon(b, y):
    out = {"NZ1c": b[y]["nz1c"]["national_gbp_m_nominal"]}
    out.update({l["id"]: l["national_gbp_m_nominal"] for l in b[y].get("carbon_split", {}).values()})
    return out


def test_choice8_ccl_rows_move_only_ccl(central):
    """Mapping key `test_choice8_ccl_rows_move_only_ccl`: under `ccl_2001_cash_frozen` and the LEC-uncapped note run,
    NZ1c and its split lines (NZ1c_tax, NZ1c_price) are unchanged every year to 1e-9, so table_choice8 (28) can print
    carbon and CCL rows apart; NZ8 does move in each."""
    for s in (*B.SWITCHES[B.CCL_CASH_FROZEN], replace(B.CENTRAL, ccl_lec_cap=False)):
        alt = B.build(s)
        for y in B.YEARS:
            assert _carbon(alt, y) == pytest.approx(_carbon(central, y), abs=1e-9), (s, y)
        assert any(abs(_nz8(alt, y) - _nz8(central, y)) > 1e-6 for y in B.YEARS), s
