"""Ticket 15: Reliable Britain's fleet sizing and CM line on contracted interconnectors
(0057 option B, 0062-0066). Spec item interconnectors-contracted.md tests 5-14, 16-17."""
import pytest

from gascf import bills as B


def test_imports_counted_break_at_2016_0062():
    # spec tests 9 and 12 (loader-level part): 2016 0 MW contracted; 2015 metered; 2017 590.6 MW
    assert B.imports_contracted_gw(2016) == 0.0
    assert B.imports_counted_gw(2016, "contracted") == 0.0
    assert B.imports_counted_gw(2015, "contracted") == B.imports_counted_gw(2015, "metered")
    assert B.imports_counted_gw(2015, "metered") == B.kept_at_peak_parts(2015)["imports"]
    assert B.imports_counted_gw(2017, "contracted") == pytest.approx(0.5906, abs=5e-5)


def test_margin_on_the_gross_peak_0065_unit():
    r = B.firm_requirement(gross_peak_gw=60.0, margin=0.07, contracted_gw=6.9589)
    assert r["firm_requirement_gw"] == pytest.approx(57.2411, abs=1e-9)          # 60 × 1.07 − 6.9589
    assert r["firm_requirement_gw"] != pytest.approx((60.0 - 6.9589) * 1.07, abs=1e-3)   # not 56.7540
    assert r["margin_on_gross_extra_gw"] == pytest.approx(0.4871, abs=1e-4)


def test_peak_day_delivery_year_printed_only_0066():
    import datetime as dt
    assert B.ic_peak_dy(dt.date(2019, 1, 15)) == {"ic_peak_dy": "2018/19", "ic_peak_dy_contracted_mw": 0.0}
    late = B.ic_peak_dy(dt.date(2019, 12, 10))
    assert late["ic_peak_dy"] == "2019/20"
    assert late["ic_peak_dy_contracted_mw"] == pytest.approx(2886.76, abs=0.005)
    assert B.imports_counted_gw(2019, "contracted") == pytest.approx(0.7217, abs=5e-5)   # time-weighted


def test_shortfall_called_imports_priced_as_kept_output_0063_unit():
    c = B.ic_called(residual_mw=[50_000.0] * 3 + [40_000.0], available_mw=48_000.0, p_less_c_gbp_mwh=60.0)
    assert c["ic_called_twh"] == pytest.approx(0.003, abs=1e-12)
    assert c["ic_called_halfhours"] == 3
    assert c["ic_called_gbp_m"] == pytest.approx(0.18, abs=1e-12)


def test_setting_default_contracted_and_switch_registry():
    from dataclasses import replace
    assert B.CENTRAL.ic_basis == "contracted"
    assert B.SWITCHES["interconnectors at peak (metered flow, v4-s35)"] == (replace(B.CENTRAL, ic_basis="metered"),)


# ---- decision 0110 item 1.8 (Richard Lyon, 19 Oct 2026: option (b), "the same basis on both sides, so there is one
# basis in one subtraction"): under contracted interconnectors the actual system's own firm test is also on
# (actual fossil + metered imports) peak x (1 + m) - contracted imports - the plant the actual system had.
def _a_actual(year):
    from gascf import capacity
    from gascf import fossil_like_for_like as LFL
    return sum(LFL.existing_plant(year).derated(capacity.read_derating()).values())


def test_own_firm_test_same_basis_as_rb_under_contracted_0110():
    from gascf import capacity
    from gascf import fossil_like_for_like as LFL
    y = LFL.lfl_year(2025, ic_basis="contracted")
    mf = capacity.margin_fraction("central")
    assert y.own_firm_basis == "gross_less_contracted"
    assert y.peak_actual_fossil_gross_mw > y.peak_actual_fossil_mw          # metered imports added at the peak
    want = max(0.0, y.peak_actual_fossil_gross_mw * (1 + mf) - B.imports_contracted_gw(2025) * 1e3 - _a_actual(2025))
    assert y.unlisted_firm_gw * 1e3 == pytest.approx(want, abs=1e-6)


def test_own_firm_test_unchanged_under_metered_and_before_2016_0110():
    from gascf import capacity
    from gascf import fossil_like_for_like as LFL
    mf = capacity.margin_fraction("central")
    for year, basis in ((2025, "metered"), (2012, "contracted")):
        y = LFL.lfl_year(year, ic_basis=basis)
        assert y.own_firm_basis == "actual_residual", (year, basis)
        want = max(0.0, y.peak_actual_fossil_mw * (1 + mf) - _a_actual(year))
        assert y.unlisted_firm_gw * 1e3 == pytest.approx(want, abs=1e-6), (year, basis)


def test_own_firm_same_basis_headline_and_2025_as_measured_for_0110(monkeypatch, request):
    """0110 quotes the measured effect: +GBP 0.182bn on the 2002-24 headline (2024 prices) and +GBP 1.20 a household in
    2025 (2025 prices), from SIZES-2026-10-19.md (prototype run on 4077be6, real closure register: headline 161.2755,
    NZ5 2025 212.775 cash, gap 2025 570.758 a household). Nothing else that moves the headline differs between that
    build and this one. The release reads the real closure register, so this build does too (as test 5)."""
    from gascf import deflator_cpih
    from gascf import fossil_like_for_like as LFL
    monkeypatch.setenv(LFL.CLOSURES_ENV, str(LFL.CLOSURES_FILE))
    # neither cache key holds the register path: clear both either side, so no other test reads this build
    B.fleet_lfl.cache_clear()
    B.build.cache_clear()
    request.addfinalizer(B.fleet_lfl.cache_clear)
    request.addfinalizer(B.build.cache_clear)
    c = deflator_cpih.cpih()
    # decision 0133 (Richard Lyon, 20 Oct 2026) moved the margin after 0110 was measured; this guard proves nothing
    # else moved, so it builds on the margin 0110's prototype had (tests/_pre_0133.py). The 0133 move is in
    # tests/test_margin_0133.py and the re-cut's run file.
    # decision 0144 (v4-s37) moved the extra running's price, the feedback elasticity and Cottam after 0110 was
    # measured; the guard builds on the engine as it was (tests/_pre_0133.py pre_s37), so it still proves nothing
    # else moved. The 0144 moves are pinned in tests/test_s37_0144.py.
    from _pre_0133 import pre_s37
    with pre_s37():
        b = B.build(B.CENTRAL)
    head = sum(b[y]["totals"]["gap_real_bn"] for y in range(2002, 2025)) * c[2024] / c[B.PRICE_BASE]
    # v4-s42 (card [internal ticket], decision 0195): the seven input fixes move this build's headline 161.2755 -> 161.1443
    # (A1, A2, A3, A5, D1; 2002-24) and its 2025 gap per household 570.758 -> 590.285 (A4, 2025 on EGC 2023, and A3),
    # measured on this seam by work/[internal ticket]/repin_s42.py; NZ5 2025 does not move.
    # v4-s43 (card [internal ticket], decision 0197): the 2002-05 NI lists move it 161.1443 -> 161.1475 (work/[internal ticket]/
    # repin_s43.py on this seam; fails at 59512c8, passes at a7e5ee4); NZ5 2025 and the 2025 gap do not move.
    assert head == pytest.approx(161.14746883137346, abs=5e-4)
    assert B.val(b[2025], "NZ5") == pytest.approx(212.77518920695888, abs=5e-3)
    assert b[2025]["totals"]["gap_per_hh_real"] == pytest.approx(590.284661668059, abs=5e-3)


# ---- build-level (heavy: two full builds, run alone) ----
@pytest.fixture(scope="module")
def both():
    from dataclasses import replace
    return {"contracted": B.build(B.CENTRAL), "metered": B.build(replace(B.CENTRAL, ic_basis="metered"))}


def test_same_basis_in_fleet_sizing_and_cm_split(both):
    # spec test 6: the imports MW the sizing nets off = the imports MW in cm_split = imports_counted_gw
    for basis, b in both.items():
        for y in range(2016, 2026):
            sized = b[y]["fleet"]["imports_counted_gw"]
            assert b[y]["cm"]["split_gw"]["imports_counted_gw"] == sized, (basis, y)
            assert sized == B.imports_counted_gw(y, basis), (basis, y)
    assert both["contracted"][2025]["fleet"]["imports_counted_gw"] == pytest.approx(6.9589, abs=5e-5)


def test_metered_reproduces_v4_s35(monkeypatch, request):
    # spec test 5, at the bills seam (the full run-file comparison is ticket 35's): under 'metered'
    # every bill line and total equals the frozen v4-s35 run file. The release reads the real closure
    # register, not conftest's fixture, so this build does too.
    import json
    from dataclasses import replace
    from pathlib import Path
    from gascf import fossil_like_for_like as LFL
    monkeypatch.setenv(LFL.CLOSURES_ENV, str(LFL.CLOSURES_FILE))
    # fleet_lfl's cache key does not include the register path, so clear it either side of this build
    B.fleet_lfl.cache_clear()
    request.addfinalizer(B.fleet_lfl.cache_clear)
    E = json.loads((Path(__file__).resolve().parents[1] / "out/v4/2026-10-14-s35.json").read_text())
    # after the merge with 17 (0089), v4-s35 also needs nuclear at its metered peak (column None); and v4-s35's
    # margin, which decision 0133 moved after it (tests/_pre_0133.py)
    from _pre_0133 import pre_s37              # and the engine before decision 0144 (v4-s37)
    with pre_s37():
        b = B.build(replace(B.CENTRAL, ic_basis="metered", nuclear_cm_column=None))
    # s36 group A1 re-pin (from the build): lines moved on purpose by earlier s36 tickets are named here and
    # left out of the line-by-line match; every other line matches v4-s35 exactly, and the totals move by
    # exactly the named lines' moves. NZ6 2017-24: daily BSUoS (0088, ticket 03) and NZ11 its VAT; GO4 every
    # year: NBP gas index (B4, ticket 09) and RB's own gas price (F1, ticket 10), and GO7 its VAT.
    # A2 merge: NZ2 and NZ10 are netted at their 2001 levels (0097, ticket 26) and NZ8 above its 2001 rate less
    # the capped LEC exemption (0044, ticket 12); NZ11 (VAT) follows NZ2/NZ10 every year. GO1 moves because
    # 0059 (ticket 11) takes the unbilled station load out of the fossil fleet's cost (every year). These move
    # under the central settings, independent of ic_basis, so they join the A1 moved set and the totals move by
    # exactly the named lines' sum.
    # v4-s42 (card [internal ticket], decision 0195) adds the lines its seven input fixes move on this build, by year, from
    # work/[internal ticket]/repin_s42.py (every other line still matches v4-s35 to 1e-6): NZ6 2010-11 (D1, FY2010/11
    # balancing on basis (i)); GO1k (fossil Britain's new build) 2002-06 (A2), 2010-11 (A1; A5 in 2011) and 2021-25
    # (A3; A4 in 2025). The totals still move by exactly the named lines' sum.
    S42_GO1K_YEARS = {2002, 2003, 2004, 2005, 2006, 2010, 2011, 2021, 2022, 2023, 2024, 2025}
    moved = {"netzero": lambda y: {"NZ2", "NZ8", "NZ10", "NZ11"} | ({"NZ6"} if 2017 <= y <= 2024 else set())
                                  | ({"NZ6"} if y in (2010, 2011) else set()),
             "gasonly": lambda y: {"GO1", "GO4", "GO7"} | ({"GO1k"} if y in S42_GO1K_YEARS else set())}
    for y in B.YEARS:
        e = E["bills"][str(y)]
        delta = {}
        for side, lines in (("netzero", b[y]["netzero"]), ("gasonly", b[y]["fossil"])):
            want = {l["id"]: l["national_gbp_m_nominal"] for l in e[side]}
            got = {l["id"]: l["national_gbp_m_nominal"] for l in lines}
            assert set(got) == set(want), (y, side)
            m = moved[side](y)
            assert {k: v for k, v in got.items() if k not in m} == pytest.approx(
                {k: v for k, v in want.items() if k not in m}, abs=1e-6), (y, side)
            delta[side] = sum(got[k] - want[k] for k in m)
        assert b[y]["totals"]["nz_gbp_m"] == pytest.approx(e["totals"]["nz_gbp_m"] + delta["netzero"], abs=1e-6), y
        assert b[y]["totals"]["go_gbp_m"] == pytest.approx(e["totals"]["go_gbp_m"] + delta["gasonly"], abs=1e-6), y
        assert b[y]["totals"]["gap_gbp_m"] == pytest.approx(
            e["totals"]["gap_gbp_m"] + delta["netzero"] - delta["gasonly"], abs=1e-6), y


def test_method_break_2002_15_identical_under_both_bases_0062(both):
    # spec test 9: every bill line 2002-2015 identical under both settings
    for y in range(2002, 2016):
        for side in ("netzero", "fossil"):
            c = {l["id"]: l["national_gbp_m_nominal"] for l in both["contracted"][y][side]}
            m = {l["id"]: l["national_gbp_m_nominal"] for l in both["metered"][y][side]}
            assert c == m, (y, side)
        assert both["contracted"][y]["totals"] == both["metered"][y]["totals"], y


def test_2016_start_at_0_mw_nz5_unchanged_0062(both):
    # spec test 12: 2016 credits no imports; NZ5(2016) = v4-s35's £5.0484747m (CM price £0/kW)
    c = both["contracted"][2016]
    assert c["fleet"]["imports_counted_gw"] == 0.0
    nz5 = next(l["national_gbp_m_nominal"] for l in c["netzero"] if l["id"] == "NZ5")
    assert nz5 == pytest.approx(5.0484747, abs=5e-8)
    m = capacity_margin = c["fleet"]["margin_fraction"]
    assert c["fleet"]["firm_requirement_gw"] == pytest.approx(c["fleet"]["sizing_peak_gross_gw"] * (1 + m), rel=1e-12)


def test_margin_on_gross_extra_2025_build_0065(both):
    f = both["contracted"][2025]["fleet"]
    # The spec writes m = 0.070 and 0.4871 GW (ticket 15). Decision 0133 (Richard Lyon, 20 Oct 2026): the central
    # margin is 4.5 GW over the 2027/28 Base Case peak of 61 GW (ECR 2026 p.5, Figure B1) = 0.0737705, so the
    # extra is 4.5 / 61 x 6.9589 = 0.5134 GW (was 0.0700935 and 0.4878 GW on the 2030/31 peak).
    assert f["margin_fraction"] == pytest.approx(4.5 / 61.0, abs=1e-7)
    assert f["margin_on_gross_extra_gw"] == pytest.approx(f["margin_fraction"] * 6.9589, abs=1e-4)
    assert f["margin_on_gross_extra_gw"] == pytest.approx(0.5134, abs=1e-4)
    assert both["metered"][2025]["fleet"]["margin_on_gross_extra_gw"] == 0.0


def test_cm_line_moves_the_right_way_2025(both):
    # spec test 7: under contracted NZ5(2025) is below metered's; the counted GW rises by
    # contracted − metered imports at peak, less any change in existing unkept plant
    nz5 = {k: next(l["national_gbp_m_nominal"] for l in b[2025]["netzero"] if l["id"] == "NZ5") for k, b in both.items()}
    assert nz5["contracted"] < nz5["metered"]
    sc, sm = both["contracted"][2025]["cm"]["split_gw"], both["metered"][2025]["cm"]["split_gw"]
    d_counted = sc["non_go1_gw"] - sm["non_go1_gw"]
    want = (sc["kept_at_peak_gw"] - sm["kept_at_peak_gw"]
            + sc["existing_unkept_gw"] - sm["existing_unkept_gw"] + sc["unlisted_gw"] - sm["unlisted_gw"])
    assert d_counted == pytest.approx(want, abs=1e-9)
    # with 0089 nuclear is the same contracted figure on both bases, so kept_at_peak moves by
    # imports counted plus pumped storage at the (different) peak half-hour only
    assert sc["nuclear_contracted_gw"] == sm["nuclear_contracted_gw"]
    assert sc["kept_at_peak_gw"] - sm["kept_at_peak_gw"] == pytest.approx(
        sc["imports_counted_gw"] - sm["imports_counted_gw"] + sc["ps_at_peak_gw"] - sm["ps_at_peak_gw"], abs=1e-9)
    assert sc["imports_counted_gw"] - sm["imports_counted_gw"] > 6.0


def test_fleet_sizing_peak_lower_under_contracted_2025(both):
    # spec test 8: under contracted the 2025 sizing peak, net of the contracted imports, is below the metered
    # residual peak, by at least contracted MW less the metered imports in the new (gross) peak half-hour; it is
    # exactly that when the gross peak falls in the metered peak half-hour, more otherwise (the metered peak is
    # the highest residual of the year). The firm requirement and the de-rated fleet fall with it.
    c, m = both["contracted"][2025]["fleet"], both["metered"][2025]["fleet"]
    net_c = c["sizing_peak_gross_gw"] - c["imports_contracted_gw"]
    res_at_new = c["sizing_peak_gross_gw"] - c["imports_metered_at_peak_gw"]
    assert res_at_new <= m["sizing_peak_gross_gw"] + 1e-9
    drop = m["sizing_peak_gross_gw"] - net_c
    assert drop >= c["imports_contracted_gw"] - c["imports_metered_at_peak_gw"] - 1e-9
    assert net_c < m["sizing_peak_gross_gw"]
    if c["sizing_peak_halfhour"] == m["sizing_peak_halfhour"]:
        assert drop == pytest.approx(c["imports_contracted_gw"] - c["imports_metered_at_peak_gw"], abs=1e-9)
    assert c["firm_requirement_gw"] < m["firm_requirement_gw"]
    print("2025 sizing:", c["sizing_peak_halfhour"], m["sizing_peak_halfhour"], round(drop, 4),
          round(c["imports_contracted_gw"] - c["imports_metered_at_peak_gw"], 4))


def test_energy_unchanged_called_imports_moved_not_lost(both):
    # spec test 10: under contracted, V, station load and the volume identity hold every year exactly as under
    # metered; any contracted imports called (0063) move from fleet energy to kept, not lost:
    # fleet + called = metered fleet, kept - called = metered kept, and the identity residual is unchanged (1e-9).
    for y in B.YEARS:
        c, m = both["contracted"][y], both["metered"][y]
        vc, vm = c["volume"], m["volume"]
        called = c["fleet"].get("ic_called_twh", 0.0)
        assert vc["v_twh"] == pytest.approx(vm["v_twh"], abs=1e-9), y
        assert vc["station_load_twh"] == pytest.approx(vm["station_load_twh"], abs=1e-9), y
        assert vc["fleet_twh"] + called == pytest.approx(vm["fleet_twh"], abs=1e-9), y
        assert vc["kept_twh"] - called == pytest.approx(vm["kept_twh"], abs=1e-9), y
        ident = lambda v: v["fleet_twh"] + v["kept_twh"] - v["station_load_twh"] - v["v_twh"]   # noqa: E731
        assert ident(vc) == pytest.approx(ident(vm), abs=1e-9), y
        assert called >= 0.0, y


IC_FIELDS = ("ic_called_twh", "ic_called_halfhours", "ic_called_gbp_m")


def test_ic_called_fields_published_in_the_run_file_0063(both):
    # spec test 14, run-file half (figures.json rb.ic.called_* is 29's, keys at the A2 merge): for every CY 2016-25
    # under contracted the run file's fleet[y] carries ic_called_twh, ic_called_halfhours and ic_called_gbp_m;
    # all are 0 for 2002-15 and under metered (0 by construction in every year, 0063).
    from gascf import export_v4 as X
    for basis, b in both.items():
        fl = X._fleet(b)
        for y in B.YEARS:
            row = fl[str(y)]
            for k in IC_FIELDS:
                if basis == "contracted" and y >= 2016:
                    assert k in row and row[k] == b[y]["fleet"][k], (basis, y, k)
                if y < 2016 or basis == "metered":
                    assert row.get(k, 0) == 0, (basis, y, k)


CM_CLOCK_FIELDS = ("netzero_gbp", "netzero_low_gbp", "netzero_high_gbp", "cm_paid_gbp", "price_gbp_per_kw_yr")


def _clock_cm_block(s, built):
    from gascf import bridge as R
    from gascf import clock_export as CE
    from gascf import export_v4 as X
    run = {"clock_cm_correction": {str(y): v for y, v in R.clock_cm_correction(s).items()}, "capacity_market": X._cm(built)}
    return CE.capacity_market(run)


def test_clock_export_cm_block_expected_change_0075(both):
    # spec test 18 (0075, replaces the byte-identical test), contracted against metered on the same code and register:
    # no year before 2016 and the same carry_forward_from; 2016 netzero (central, low, high), cm_paid and price equal
    # to the penny; 2017-25 cm_paid and price equal, netzero_gbp moves by exactly NZ5 contracted - NZ5 metered (£0.01),
    # non-zero in 2025 (fails if the export still reads the metered run). No sign asserted for 2017-24.
    from dataclasses import replace
    c = _clock_cm_block(B.CENTRAL, both["contracted"])
    m = _clock_cm_block(replace(B.CENTRAL, ic_basis="metered"), both["metered"])
    assert min(int(y) for y in c["years"]) == 2016 and c["carry_forward_from"] == m["carry_forward_from"]
    assert {k: c["years"]["2016"][k] for k in CM_CLOCK_FIELDS} == {k: m["years"]["2016"][k] for k in CM_CLOCK_FIELDS}
    nz5 = lambda b, y: next(l["national_gbp_m_nominal"] for l in b[y]["netzero"] if l["id"] == "NZ5")   # noqa: E731
    for y in range(2017, 2026):
        rc, rm = c["years"][str(y)], m["years"][str(y)]
        assert (rc["cm_paid_gbp"], rc["price_gbp_per_kw_yr"]) == (rm["cm_paid_gbp"], rm["price_gbp_per_kw_yr"]), y
        want = (nz5(both["contracted"], y) - nz5(both["metered"], y)) * 1e6
        assert rc["netzero_gbp"] - rm["netzero_gbp"] == pytest.approx(want, abs=0.01), y
    assert abs(c["years"]["2025"]["netzero_gbp"] - m["years"]["2025"]["netzero_gbp"]) > 1.0


def test_clock_export_cm_block_metered_identical_to_v4_s35(monkeypatch, request):
    # spec test 18, last bullet: under ic_basis="metered" (with v4-s35's nuclear at its metered peak, 0089, and the
    # real closure register as the release reads it) the Clock export CM block equals v4-s35's, field by field.
    import json
    from dataclasses import replace
    from pathlib import Path
    from gascf import fossil_like_for_like as LFL
    monkeypatch.setenv(LFL.CLOSURES_ENV, str(LFL.CLOSURES_FILE))
    for f in (B.build, B.fleet_lfl):
        f.cache_clear()
        request.addfinalizer(f.cache_clear)
    E = json.loads((Path(__file__).resolve().parents[1] / "out/clock/v4-s35.json").read_text())["capacity_market"]
    from _pre_0133 import pre_s37
    with pre_s37():                  # v4-s35's margin (0133) and the engine before 0144 (tests/_pre_0133.py)
        s = replace(B.CENTRAL, ic_basis="metered", nuclear_cm_column=None)
        got = _clock_cm_block(s, B.build(s))
    assert got["carry_forward_from"] == E["carry_forward_from"]
    assert got["years"] == E["years"]
