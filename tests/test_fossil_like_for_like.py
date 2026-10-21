"""s22: like-for-like fossil Britain (the actual system with net zero taken out)."""
from datetime import date
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import fossil_like_for_like as L
from gascf import waterfall as W

YEARS = list(B.YEARS)
# Sanity test 1 tolerance (brief s22): in 2002-2004, when the two Britains were nearly the
# same, the gap must sit within £25 a household (2025 money) and within 30% of the sum of
# the net-zero-only lines.
EARLY_TOL_GBP = 25.0
EARLY_TOL_FRAC = 0.30


@pytest.fixture(scope="module")
def central():
    return B.build()


def nz_only_lines(b: dict) -> float:
    """Subsidies + carbon + CCL + extra backup + grid and balancing extras + schemes, £m."""
    v = lambda i: B.val(b, i)                          # noqa: E731
    nz4b = v("NZ4b") if any(l["id"] == "NZ4b" for l in b["netzero"]) else 0.0     # s27b biomass CfD split
    return (v("NZ2") + v("NZ3") + v("NZ4") + nz4b + v("NZ1c") + v("NZ5") + v("NZ8") + v("NZ10") + (v("NZ11") - v("GO7"))
            + (v("NZ6") - v("GO4")) + (v("NZ7") - v("GO5")))


def test_central_is_like_for_like_and_all_new_is_a_switch():
    assert B.CENTRAL.fleet == "like_for_like"
    assert B.ALL_NEW.fleet == "all_new"
    a = B.build(B.ALL_NEW)
    assert a[2025]["fleet"].get("method") is None                  # the s21b fleet dict
    assert "built new" in B.line(a[2025], "GO1")["label"]


def test_early_years_gap_close_to_net_zero_extras_pooled(central):
    """Ticket 13 spec test 7 (0061: judged pooled over 2002-04, sum over sum). Decision 0111 (Richard Lyon,
    19 Oct 2026, item 1.3): the check keeps the 0097-netted lines and is NOT re-pinned. On the s36 build it gives
    about 34.6% against the 30% limit (36.1% after decision 0133 moved the margin to the 2027/28 peak), so this test FAILS by design: an expected, disclosed failure, stated in the
    paper's §5 with its cause (0097's netting takes about £647m, 2025 prices, out of the lines over 2002-04) and the
    fact that the headline is unaffected. Never loosen, skip or xfail it (0111)."""
    from gascf.calibration_block import early_years_check
    rows = [{"year": y, "gap_hh": central[y]["totals"]["gap_per_hh_real"],
             "lines_hh": B.real(nz_only_lines(central[y]), y) * 1e6 / central[y]["households"],
             "households": central[y]["households"]} for y in (2002, 2003, 2004)]
    assert early_years_check(rows)["passed"] is True


def test_calibration_early_block_discloses_the_0111_failure(central):
    """Run file tests.calibration_early (spec D6) carries the pooled and per-year figures from the same lines as the
    test above, passed False and the 0111 disclosure; the figures keys read it (ticket 13 rows of figures-keys.md)."""
    import sys
    from gascf import export_v4 as X
    from gascf.calibration_block import early_years_check
    blk = X._calibration_early(central)
    rows = [{"year": y, "gap_hh": central[y]["totals"]["gap_per_hh_real"],
             "lines_hh": B.real(nz_only_lines(central[y]), y) * 1e6 / central[y]["households"],
             "households": central[y]["households"]} for y in (2002, 2003, 2004)]
    want = early_years_check(rows)
    assert blk["pooled"] == pytest.approx(want["pooled"]) and blk["passed"] is want["passed"] is False
    assert blk["pooled"]["pct"] == pytest.approx(36.6, abs=0.05)   # 34.6 at s36-gA; 36.1 after decision 0133 (margin on the 2027/28 peak); 36.6 after 0144 (v4-s37 run file: 36.637)
    assert blk["pooled"]["diff_hh"] == pytest.approx(-7.11, abs=0.01)   # -6.72 before 0133; -7.01 before 0144 (v4-s37 run file: -7.113)
    assert blk["decision"] == "0111" and blk["disclosed_failure"] is True
    assert "0097" in blk["note"] and "headline" in blk["note"]
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.figures_keys import calibration as K
    v = K.values({"tests": {"calibration_early": blk}})
    assert v["calib_pooled_2002_04_pct"] == blk["pooled"]["pct"]
    assert v["calib_pooled_2002_04_gbp_hh"] == blk["pooled"]["diff_hh"]
    assert [v[f"calib_{y}_pct"] for y in (2002, 2003, 2004)] == [p["pct"] for p in blk["per_year"]]
    assert v["calib_limit_pct"] == 30.0 and v["calib_limit_gbp_hh"] == 25.0
    assert v["calib_pooled_2002_04_passed"] is False
    assert K.values({"tests": {}})["calib_pooled_2002_04_pct"] is None


def test_gap_sign_matches_net_zero_only_lines(central):
    for y in YEARS:
        b = central[y]
        g, nz = b["totals"]["gap_gbp_m"], nz_only_lines(b)
        assert (g > 0) == (nz > 0), (y, g, nz)


def test_fossil_britain_pays_more_for_power_than_the_actual_price_less_carbon(central):
    """Under the s22 rule (with the merit-order uplift) step 1 is never positive. s23b, spec
    §15.3 item 1: with no uplift in the central case, step 1 CAN be positive (2021-22: the
    renewables' MWh are paid the actual price less carbon in net-zero Britain, but cost only
    fuel and running cost in fossil Britain). That is shown, not tested away."""
    wf = W.waterfall(B.replace(B.CENTRAL, moe="larger", closures="actual", newbuild="gas_only"))
    for y in YEARS:
        s1 = next(s for s in wf[y] if s["step"] == 1)["value_gbp_m_nominal"]
        assert s1 <= 1e-6, (y, s1)


def test_volume_and_waterfall_identities(central):
    wf = W.waterfall()
    for y in YEARS:
        v = central[y]["volume"]
        assert abs((v["fleet_twh"] + v["kept_twh"] - v["station_load_twh"]) / v["v_twh"] - 1) < 0.005, y
        assert abs(W.identity_error(wf[y])) < 0.01, y


def test_go1_parts_add_up(central):
    for y in YEARS:
        f = central[y]["fleet"]
        parts = f["market_gbp_m"] + f["moe_gbp_m"] + f["gas_feedback_gbp_m"] + f["fixed_gbp_m"] + f["fuel_gbp_m"] \
            + f["vom_gbp_m"] + f["transport_gbp_m"]          # fuel includes the at-cost gas-price feedback
        assert parts == pytest.approx(B.val(central[y], "GO1"), rel=1e-9, abs=1e-6), y
        assert f["fixed_gbp_m"] >= 0 and f["moe_gbp_m"] >= 0


def test_replacement_order_existing_first_then_new(central):
    """Existing plant runs harder first; new plant only where it runs out. Before 2015 the
    existing fleet covered every half-hour, so no new plant is built."""
    for y in YEARS:
        f = central[y]["fleet"]
        assert f["gen_twh"]["extra_existing"] == pytest.approx(
            f["renewables_replaced_twh"] - f["gen_twh"]["new_ccgt"] - f["gen_twh"]["new_ocgt"]
            - f["gen_twh"]["new_coal"], abs=0.05), y
        if y < 2015:
            assert f["new_gw"] == pytest.approx(0.0, abs=1e-9), y


def test_firm_capacity_reported_every_year(central):
    for y in YEARS:
        f = central[y]["fleet"]
        assert f["firm_extra_gw"] >= 0 and f["existing_derated_gw"] > 20, y


def test_moe_central_is_shao_and_none_is_a_methods_switch(central):
    """Spec §15.5 item 1 (overrides §15.3 item 1): Shao uplift in the central case on fossil
    output and on the kept nuclear/imports line; 'model' is the high side; 'none' is a
    methods-page switch. The bills.py half lands with s27c (work/s27a-fossil/bills-patch.md)."""
    assert L.DEFAULT_MOE == "shao" and L.MOE_HIGH == "model" and L.MOE_METHODS == "none"
    if B.CENTRAL.moe != "shao":
        pytest.skip("bills.py not yet patched (s27c applies work/s27a-fossil/bills-patch.md)")
    # 0144 item 4A (v4-s37): the stack estimate is a methods-page row, no longer in the range
    assert any("merit-order" in n and "own stack" in n for n in B.METHOD_SWITCHES)
    assert not any("merit-order" in n and "own stack" in n for n in B.switch_settings())
    assert any("no merit-order" in n for n in B.METHOD_SWITCHES)
    nn = B.build(B.replace(B.CENTRAL, moe="none"))
    for y in YEARS:
        f = central[y]["fleet"]
        assert f["moe_gbp_m"] >= 0.0 and f["moe_kept_gbp_m"] >= 0.0, y
        assert f["moe"]["applied_mean_gbp_mwh"] == pytest.approx(max(0.0, f["moe"]["shao_mean_gbp_mwh"])), y
        # the uplift makes fossil Britain dearer -> smaller (or equal) gap
        assert central[y]["totals"]["gap_gbp_m"] <= nn[y]["totals"]["gap_gbp_m"] + 1e-6, y


def test_shao_2025_matches_spec():
    """Spec §15.5 item 1: Shao uplift about £18.9/MWh in 2025."""
    assert L.lfl_year(2025).moe_shao_mean == pytest.approx(18.9, abs=0.1)


def test_coal_load_factor_cap_from_dukes():
    cap, yr = L.dukes_coal_lf_max()
    assert cap == pytest.approx(0.6504) and yr == 2003          # DUKES 5.10.B, read from the file
    assert L.coal_lf_cap("none") is None and L.DEFAULT_COAL_LF == "dukes_max"
    with pytest.raises(ValueError):
        L.coal_lf_cap("bogus")
    on, off = L.lfl_year(2016), L.lfl_year(2016, coal_lf="none")
    assert off.coal_lf_achieved > cap + 0.05                    # the uncapped stack runs coal harder than any year on record
    assert on.coal_lf_achieved == pytest.approx(cap, abs=0.005) and on.coal_avail_scale < 1
    # the shortfall goes to the next blocks and new build: more new plant, never less
    new_gw = lambda r: sum(v for k, v in (r.new or {}).items() if k.endswith("_gw"))
    assert new_gw(on) >= new_gw(off) - 1e-9
    assert on.energy_twh == pytest.approx(off.energy_twh)


def test_gas_feedback_rules_and_size():
    y = L.lfl_year(2025)
    g = {k: L.gas_feedback(y, k) for k in L.GAS_FEEDBACK_RULES}
    # v4-s37, decision 0144 item 2A: dQ / ((e_s + e_d) Q); central 0.06 + 0.169 (was 0.16 supply only); the range
    # row Krichene's pair 0.16 + 0.45; 'high' 0.06 supply only for case B. The formula itself: tests/test_s37_0144.py
    assert L.DEFAULT_GAS_FEEDBACK == "central" and g["central"]["elasticity"] == pytest.approx(0.229)
    assert g["none"]["at_cost_gbp_m"] == g["none"]["market_gbp_m"] == g["none"]["kept_gbp_m"] == 0.0
    tot = {k: v["at_cost_gbp_m"] + v["market_gbp_m"] + v["kept_gbp_m"] for k, v in g.items()}
    assert tot["none"] < tot["krichene_lr"] < tot["central"] < tot["high"]
    c = g["central"]
    assert c["price_rise_frac"] == pytest.approx(c["dq_twh"] / ((0.06 + 0.169) * c["q_twh"]))
    assert (g["krichene_lr"]["elasticity"], g["high"]["elasticity"]) == (pytest.approx(0.61), 0.06)
    for k, e in (("krichene_lr", 0.61), ("high", 0.06)):
        assert g[k]["price_rise_frac"] == pytest.approx(c["price_rise_frac"] * 0.229 / e, rel=1e-12)
    assert c["q_twh"] == pytest.approx(L.EU_GAS_DEMAND_TWH + L.gb_gas_demand_twh()[2025])
    assert 0 < c["gas_marginal_share"] <= 1 and c["dq_twh"] > 0
    # s27c: dQ is fossil Britain's gas burn for power less the ACTUAL burn (DUKES 5.6.A), not the
    # engine's own coal-first dispatch of the actual load (which double-counted coal-for-gas)
    assert c["dq_twh"] == pytest.approx(c["fossil_power_gas_twh"] - c["actual_power_gas_twh"])
    assert c["dq_twh"] < c["dq_vs_engine_actual_dispatch_twh"]
    assert 100 < c["actual_power_gas_twh"] < 400                # DUKES 5.6.A MPP gas, TWh
    assert L.NEUHOFF_PDF.exists() and L.ET_41.exists()
    with pytest.raises(ValueError):
        L.gas_feedback(y, "bogus")


def test_shao_coefficients_transcribed():
    assert L.SHAO_WIND_FY[2011] == -1.83 and L.SHAO_WIND_FY[2017] == -0.61
    assert min(L.SHAO_WIND_FY.values()) == -1.83 and max(L.SHAO_WIND_FY.values()) == -0.61
    c, _ = L.shao_wind_coeff(2015)
    assert c == pytest.approx(0.25 * -1.22 + 0.75 * -1.19)
    assert L.SHAO_PDF.exists()


def test_existing_plant_is_gb_and_closes_on_actual_dates():
    from gascf.fossil_fleet import coal_capacity_gb
    for y in (2002, 2016, 2024, 2025):
        e = L.existing_plant(y)
        assert e.coal == pytest.approx(coal_capacity_gb(y)[0])
    assert L.existing_plant(2025).coal == 0.0
    assert L.existing_plant(2010).ccgt > L.existing_plant(2002).ccgt


# ------------------------------------------------------------------ s23b (spec §15.3)

FIXTURE = str(Path(__file__).parent / "fixtures/s23b_fossil_closures_fixture.yaml")


def _bad_register(tmp_path, **change):
    import json
    rows = json.loads(Path(FIXTURE).read_text())
    rows[1].update(change)
    p = tmp_path / f"bad{len(list(tmp_path.iterdir()))}.yaml"   # read_closures caches by path
    p.write_text(json.dumps(rows))
    return str(p)


def test_closure_register_schema_and_brief_rules(tmp_path):
    rows = L.read_closures(FIXTURE)
    assert len(rows) == 5 and all(r["url"] and r["quote"] for r in rows)
    with pytest.raises(ValueError, match="differs from actual"):        # age closes on its real date
        L.read_closures(_bad_register(tmp_path, fossil_britain_close="2020-01-01"))
    with pytest.raises(ValueError, match="must stay open"):             # net-zero closure: null
        L.read_closures(_bad_register(tmp_path, reason="net_zero_policy"))
    with pytest.raises(ValueError, match="reason"):
        L.read_closures(_bad_register(tmp_path, reason="carbon"))
    with pytest.raises(FileNotFoundError):
        L.read_closures(str(tmp_path / "missing.yaml"))
    # capacity may be unknown only where the station closes on the same date in both worlds
    assert L.read_closures(_bad_register(tmp_path, capacity_mw=None))[1]["capacity_mw"] == 0.0
    with pytest.raises(ValueError, match="not a number"):
        L.read_closures(_bad_register(tmp_path, capacity_mw=None, reason="net_zero_policy",
                                      fossil_britain_close=None))


def test_kept_open_is_time_weighted_and_follows_the_rule():
    k16 = L.kept_open(2016, "legitimate", FIXTURE)
    share = (date(2017, 1, 1) - date(2016, 3, 31)).days / 366
    # A (2000 MW from 31 Mar 2016) + D (600 MW, all year) ; B (age) is not kept; C closes in 2019 actually
    assert k16["mw"]["coal"] == pytest.approx(2000 * share + 600)
    assert k16["mw"]["ccgt"] == pytest.approx(400)                      # E, carbon-price closure
    assert k16["abated_mw"]["FGD+SCR"] == pytest.approx(2000 * share)
    k22 = L.kept_open(2022, "legitimate", FIXTURE)                      # C closed mid-2021 for its own reason
    assert k22["mw"]["coal"] == pytest.approx(2600) and k22["abated_mw"]["SCR"] == 0.0
    k20 = L.kept_open(2020, "legitimate", FIXTURE)
    assert k20["abated_mw"]["SCR"] == pytest.approx(500)
    assert L.kept_open(2016, "actual", FIXTURE)["mw"] == {"coal": 0.0, "ccgt": 0.0, "other_gas": 0.0, "oil": 0.0}


def test_actual_closures_switch_reproduces_s22_existing_fleet():
    a = B.fleet_lfl(2016, closures="actual", newbuild="gas_only")
    assert a["coal_gw"] == pytest.approx(L.existing_plant(2016).coal / 1e3)
    assert a["kept_fixed_gbp_m"] == 0.0 and a["new_coal_gw"] == 0.0


def test_kept_plant_pays_keep_open_costs_and_filters(central):
    for y in YEARS:
        f = central[y]["fleet"]
        kept = sum(f["kept_gw"].values())
        if kept > 0:
            assert f["kept_fixed_gbp_m"] > 0, y
        if f["kept_abated_gw"] and sum(f["kept_abated_gw"].values()) > 0:
            assert f["kept_detail"]["abatement_fixed_gbp_m"] > 0, y


def test_new_build_is_cheapest_including_coal_and_never_nuclear(central):
    from gascf import fossil_fleet as ff
    for y in YEARS:
        assert ff.nuclear_available(y)[0] is False, y
        f = central[y]["fleet"]
        assert f["newbuild"] == "cheapest" and f["new_coal_gw"] >= 0
    # cheapest choice per strip: the new block is never dearer than gas only by more than the
    # dispatch rounding (sizing uses demand-weighted mean prices, dispatch monthly prices)
    for y in (2016, 2020, 2025):
        c = B.fleet_lfl(y)
        g = B.fleet_lfl(y, newbuild="gas_only")
        assert c["new_total_gbp_m"] <= g["new_total_gbp_m"] * 1.02 + 1.0, y


def test_reader_groups_cover_every_line_and_change_no_total(central):
    """§15.3 item 3: layout only. Every line carries a group; the groups add to the bill; the
    grouped waterfall lands on net-zero Britain's total."""
    for y in YEARS:
        b = central[y]
        for l in b["netzero"] + b["fossil"] + b["same_in_both"]:
            assert l["group"] in B.GROUPS + ("power", "fossil", "same_in_both"), (y, l["id"])
        nz = sum(l["national_gbp_m_nominal"] for l in b["netzero"]) + b["totals"]["s1_gbp_m"]
        assert nz == pytest.approx(b["totals"]["nz_gbp_m"])
        g = W.grouped(W.steps_for(b, y))
        mid = sum(s["value_gbp_m_nominal"] for s in g[1:-1])
        assert g[0]["value_gbp_m_nominal"] + mid == pytest.approx(g[-1]["value_gbp_m_nominal"], abs=0.01), y
        assert sorted({st for s in g[1:-1] for st in s["steps"]}) == list(range(1, 10))   # step 2 split in two


@pytest.mark.parametrize("year", [2003, 2006, 2012, 2013, 2016])
def test_coal_cap_never_below_actual_coal_output(year):
    """s29: fossil Britain has the same coal plant with carbon removed, so it never burns less
    coal than real Britain sent out (DUKES 5.6.J, MPP coal 'Supplied (gross)'). Before the fix
    the 65% cap on the engine's coal MW fell below that in 2003, 2005-07, 2012 and 2013 and
    took up to £100 a household off the 2013 gap. The cap still binds where it should (2016)."""
    on, off = L.lfl_year(year), L.lfl_year(year, coal_lf="none")
    actual = L.actual_coal_supplied_twh(year)
    assert on.coal_twh >= actual * (1 - 2e-3)                   # the floor holds
    cap, _ = L.dukes_coal_lf_max()
    # never more than the larger of the actual output and 65% of the engine's coal MW
    assert on.coal_lf_achieved <= cap + 1e-3 or on.coal_twh <= actual * (1 + 2e-3)
    assert on.coal_twh <= off.coal_twh * (1 + 1e-6)             # and never exceeds the uncapped stack
    if year == 2016:
        assert on.coal_twh < off.coal_twh * 0.9                 # the cap still bites above the floor


# ---- ticket 13 (0061): the early-years check judged pooled over 2002-04, sum over sum, national £m (spec
# calibration-pooled.md D1-D6). Fixtures from calib-calc/option_v_0059.json (`b_lec`: 0044 with the LEC exemption
# built, 0059), as (gap - lines £/hh, lines £/hh, households), 2025 money.
HH = {2002: 24_148_600, 2003: 24_281_000, 2004: 24_340_100, 2005: 24_541_900}   # v4-s35 run file `years`


def _rows(spec):
    return [{"year": y, "gap_hh": d + l, "lines_hh": l, "households": HH[y]} for y, (d, l) in spec.items()]


B_LEC = {2002: (-6.33, 18.35), 2003: (-5.86, 29.48), 2004: (-7.95, 34.97)}


def test_13_1_pooled_pass_under_0044_with_lec_and_0059():
    """Spec test 1 (with P1 answered by the cap ruling): pooled 24.3% (±0.05), -£6.71 a household (±0.01), passes."""
    from gascf.calibration_block import early_years_check
    r = early_years_check(_rows(B_LEC))
    assert r["pooled"]["pct"] == pytest.approx(24.3, abs=0.05)
    assert r["pooled"]["diff_hh"] == pytest.approx(-6.71, abs=0.01)
    assert r["passed"] is True


B_ALONE = {2002: (-10.72, 18.67), 2003: (-13.34, 29.75), 2004: (-16.00, 35.43)}   # 0044 alone, no 0059


def test_13_2_would_have_failed_under_0044_alone():
    """Spec test 2: pooled -£13.36 a household passes £25, but 47.8% fails 30%, so `passed` is False."""
    from gascf.calibration_block import early_years_check
    r = early_years_check(_rows(B_ALONE))
    assert r["pooled"]["diff_hh"] == pytest.approx(-13.36, abs=0.01)
    assert r["pooled"]["pct"] == pytest.approx(47.8, abs=0.05)
    assert r["passed"] is False


def test_13_6_the_25_pound_limit_is_live():
    """Spec test 6: pooled -£26 a household at 10% of the lines fails (the £25 limit, not only the 30% one)."""
    from gascf.calibration_block import early_years_check
    r = early_years_check(_rows({y: (-26.0, 260.0) for y in (2002, 2003, 2004)}))
    assert r["pooled"]["diff_hh"] == pytest.approx(-26.0, abs=1e-9) and r["pooled"]["pct"] == pytest.approx(10.0)
    assert r["passed"] is False


def test_13_5_2005_is_excluded():
    """Spec test 5: a 2005 row (-12.85, 188.79) added to the failing test-2 fixture is ignored, so still False
    (pooled 2002-05 would have been 12.0% and passed); the pooled figures are the 2002-04 ones."""
    from gascf.calibration_block import early_years_check
    r = early_years_check(_rows({**B_ALONE, 2005: (-12.85, 188.79)}))
    assert r["passed"] is False
    assert r["pooled"]["pct"] == pytest.approx(47.8, abs=0.05)


def test_13_3_per_year_lines_are_printed(capsys):
    """Spec test 3 (D4): the per-year rows 2002, 2003, 2004 are returned and printed (difference £/hh, lines £/hh, %,
    each limit); with the test-1 fixture (LEC built) 2002 shows 34.5% (33.7% before the LEC lines)."""
    from gascf.calibration_block import early_years_check
    r = early_years_check(_rows(B_LEC))
    out = capsys.readouterr().out
    assert [p["year"] for p in r["per_year"]] == [2002, 2003, 2004]
    assert r["per_year"][0]["pct"] == pytest.approx(34.5, abs=0.05)
    for y in (2002, 2003, 2004):
        assert str(y) in out
    assert "34.5%" in out


def test_13_4_a_per_year_failure_does_not_fail_the_check():
    """Spec test 4: with the test-1 fixture 2002 alone is over 30% and the check still passes (guards against a
    per-year assertion coming back)."""
    from gascf.calibration_block import early_years_check
    r = early_years_check(_rows(B_LEC))
    assert r["per_year"][0]["pass_pct"] is False
    assert r["passed"] is True
