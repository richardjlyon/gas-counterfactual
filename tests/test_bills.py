"""s21b: the two full bills, the waterfall and the Subsidy Clock bridge (spec v4 §3, §9, §10, §12.1)."""
import pytest

from gascf import bills as B
from gascf import bridge as R
from gascf import waterfall as W

YEARS = list(B.YEARS)


@pytest.fixture(scope="module")
def central():
    return B.build()


# ------------------------------------------------------------------ §3 lines and identities

def test_every_line_every_year_has_value_basis_and_source(central):
    for y in YEARS:
        b = central[y]
        ids = [l["id"] for l in b["netzero"]] + [l["id"] for l in b["fossil"]]
        nz = list(B.NZ_IDS)
        if B.CENTRAL.cfd_split:                         # s27b/c: biomass CfD line after NZ4
            nz.insert(nz.index("NZ4") + 1, "NZ4b")
        assert ids == nz + list(B.GO_IDS)
        for l in b["netzero"] + b["fossil"] + [b["nz1c"]]:
            assert l["national_gbp_m_nominal"] is not None, (y, l["id"])
            assert l["basis"] in ("measured", "modelled", "estimated"), (y, l["id"])
            assert l["source_ids"] and "UNSOURCED" not in l["source_ids"], (y, l["id"])
            assert l["per_household_real"] == pytest.approx(
                l["national_gbp_m_real"] * 1e6 / b["households"])


def test_volume_identity_within_half_percent(central):
    """§3.2: fleet output + kept output = V (+ station load, which the fleet also makes)."""
    for y in YEARS:
        v = central[y]["volume"]
        err = (v["fleet_twh"] + v["kept_twh"] - v["station_load_twh"]) / v["v_twh"] - 1
        assert abs(err) < 0.005, (y, err)


def test_volume_identity_holds_on_the_fuelhh_switch_too():
    b = B.build(B.Settings(residual="fuelhh"))
    for y in (2016, 2025):
        v = b[y]["volume"]
        assert abs((v["fleet_twh"] + v["kept_twh"] - v["station_load_twh"]) / v["v_twh"] - 1) < 0.005


def test_s1_identical_and_zero_lines_zero(central):
    for y in YEARS:
        b = central[y]
        assert B.val(b, "GO2") == B.val(b, "GO3") == B.val(b, "GO6") == 0.0
        t = b["totals"]
        nz = sum(l["national_gbp_m_nominal"] for l in b["netzero"])
        go = sum(l["national_gbp_m_nominal"] for l in b["fossil"])
        assert t["nz_gbp_m"] - nz == pytest.approx(t["s1_gbp_m"])
        assert t["go_gbp_m"] - go == pytest.approx(t["s1_gbp_m"])
        assert t["gap_gbp_m"] == pytest.approx(nz - go, abs=1e-6)       # S1 cancels exactly


def test_carbon_once(central):
    """NZ1c is carved out of NZ1, never added: NZ_total contains NZ1 but not NZ1c again."""
    for y in YEARS:
        b = central[y]
        assert "NZ1c" not in [l["id"] for l in b["netzero"]]
        assert 0 <= B.val(b, "NZ1c") < B.val(b, "NZ1")
        if y < 2005:
            assert B.val(b, "NZ1c") == 0


def test_coal_is_actual_capacity_plus_coal_kept_open_every_year(central):
    """s23b (spec §15.3 item 2 overrides §15.2 dec. 1): existing coal = the GB coal capacity that
    actually existed plus the coal stations fossil Britain keeps open (closed by net-zero policy)."""
    from gascf.fossil_fleet import coal_capacity_gb
    for y in YEARS:
        f = central[y]["fleet"]
        assert f["coal_gw"] == pytest.approx(coal_capacity_gb(y)[0] / 1e3 + f["kept_gw"]["coal"], abs=1e-6)
        assert f["coal_gw"] >= coal_capacity_gb(y)[0] / 1e3 - 1e-9


def test_households_year_matched(central):
    assert central[2025]["households"] == 28_253_000            # GB, ONS LFS (s30)
    assert central[2002]["households"] < central[2025]["households"]


def test_nz5_rule(central):
    """§5.4 (s32): NZ5 is the actual CM less Reliable Britain's notional CM on the firm capacity
    GO1 does not pay for, never negative; the 'full' switch gives the whole CM."""
    full = B.build(B.Settings(cm_rule="full"))
    for y in YEARS:
        cm = central[y]["cm"]["paid_gbp_m"]
        assert 0 <= B.val(central[y], "NZ5") <= cm + 1e-9
        assert B.val(full[y], "NZ5") == pytest.approx(cm)
        if y < 2016:
            assert cm == 0


def test_go4_central_is_ibc_with_the_2018_share():
    """Spec §15.1 item 8 (Richard, 14 Oct 2026; exception to standing decision 7): the central GO4
    is B0 'ibc' with the FY2018/19 workbook share; the stacked cautious option (largest GO4, the
    s27-s32 central) is the low end of the range and still a switch."""
    opts = B.go4_options()
    tot = {k: sum(B.real(v[y]["gbp_m"], y) for y in YEARS) for k, v in opts.items()}
    assert B.go4_central_choice() == B.go4_central_choice("included") == "ibc|first"
    assert B.go4_stacked_choice() == max(tot, key=tot.get) == "nao_2005|max"
    c = B.go4_line(B.CENTRAL)
    # s36 ticket 10 (F1): the central GO4's energy part is at RB's own feedback-raised gas price, so the
    # reference carries the build's price_rise_frac (re-pinned from the build, s36-gA)
    u = {y: B.fleet_lfl(y, *B._lfl_args(B.CENTRAL, y))["gas_feedback"].get("price_rise_frac", 0.0) for y in YEARS}
    ref = B.balancing.go4(B.PRICE_BASE, B.balancing.energy_share_2018(), "ibc", YEARS, gas_uplift=u)
    assert all(c[y]["gbp_m"] == pytest.approx(ref[y]["gbp_m"]) for y in YEARS)
    alts = B.switch_settings()["balancing (other sourced share / baseline)"]
    shares = B.balancing_workbook_shares()
    assert any(s.bal_option == "nao_2005" and s.bal_share == max(shares.values()) for s in alts)


# ------------------------------------------------------------------ §9 waterfall

def test_waterfall_identity_every_year(central):
    wf = W.waterfall()
    for y in YEARS:
        assert abs(W.identity_error(wf[y])) < 0.01, y
        s = {x["step"]: x["value_gbp_m_nominal"] for x in wf[y]}
        b = central[y]
        assert s[1] + s[2] == pytest.approx(B.val(b, "NZ1") - B.val(b, "GO1") - B.val(b, "GO1k"))
        assert s[0] == pytest.approx(b["totals"]["go_gbp_m"])
        assert s["="] == pytest.approx(b["totals"]["nz_gbp_m"])


def test_every_line_in_exactly_one_step():
    named = W.lines_in_steps()
    for lid in B.NZ_IDS + B.GO_IDS:
        n = named.count(lid)
        assert n == (0 if lid in W.ZERO_BY_RULE else 1), lid
    assert named.count("NZ1c") == 2           # carved out in step 1, shown in step 2


@pytest.mark.parametrize("name", list(B.switch_settings()))
def test_waterfall_identity_every_switch(name):
    for st in B.switch_settings()[name]:
        wf = W.waterfall(st)
        for y in YEARS:
            assert abs(W.identity_error(wf[y])) < 0.01, (name, y)


def test_waterfall_identity_all_new_switch():
    """s22: the s21b all-new fleet is kept as a switch; its identities still hold."""
    wf = W.waterfall(B.ALL_NEW)
    for y in YEARS:
        assert abs(W.identity_error(wf[y])) < 0.01, y


def test_ranges_bracket_central():
    rg = B.ranges()
    for y in YEARS:
        assert rg[y]["low"] <= rg[y]["central"] + 1e-6 <= rg[y]["high"] + 2e-6


# ------------------------------------------------------------------ §10 bridge

def test_bridge_identity_every_year():
    """§10.1: Clock total + rows B-K = this site's gap, to £0.01m, every year, no row unnamed."""
    br = R.bridge()
    for y in YEARS:
        rows = br[y]["rows"]
        assert [r["row"] for r in rows] == list(R.ROWS)
        assert all(r["label"] for r in rows)
        assert abs(br[y]["error"]) < 0.01, (y, br[y]["error"])


def test_bridge_row_m_ccl_after_july_2015():
    """D2 (Richard, 14 Oct 2026): the Clock counts the electricity CCL only to 31 July 2015; the
    engine counts it all. Row M removes the Clock's post-July-2015 CCL, row J puts it back: M + J
    equals NZ8 - (Clock CCL - CPS) as before, M is nil before 2015 and the whole CCL after."""
    br = R.bridge()
    c = R.read_clock()
    for y in YEARS:
        rows = {r["row"]: r["gbp_m_nominal"] for r in br[y]["rows"]}
        nz8 = next(l["national_gbp_m_nominal"] for l in R.B.build()[y]["netzero"] if l["id"] == "NZ8")
        ccl = c[y]["ccl"] or 0.0
        cps = 0.0 if c[y]["ccl"] is None else R.cps_part(y)
        assert rows["J"] + rows["M"] == pytest.approx(nz8 - (ccl - cps), abs=1e-6), y
        if y < 2015 or c[y]["ccl"] is None:
            assert rows["M"] == 0.0, y
        elif y > 2015:
            assert rows["M"] == pytest.approx(-(ccl - cps)), y
    m15 = next(r for r in br[2015]["rows"] if r["row"] == "M")["gbp_m_nominal"]
    assert -(c[2015]["ccl"] - R.cps_part(2015)) < m15 < 0


def test_bridge_reads_the_clock_and_spot_values():
    c = R.read_clock()
    assert c[2024]["ro"] == pytest.approx(7700.0)
    assert c[2024]["ccl"] == pytest.approx(1253.0)
    assert c[2024]["ets"] == pytest.approx(882.834732)
    assert c[2024]["capacity_market"] == pytest.approx(1256.981395, abs=1e-3)


def test_clock_cm_correction_2024():
    """§10.2: the Clock's CM line is £1.26bn in 2024; the correction is NZ5 − that line (s32: NZ5
    is no longer zero, so the correction is less than the whole line)."""
    c = R.clock_cm_correction()[2024]
    assert c["clock_cm_gbp_m"] == pytest.approx(1257.0, abs=1)
    assert c["correction_gbp_m"] == pytest.approx(c["nz5_gbp_m"] - c["clock_cm_gbp_m"])
    assert c["nz5_gbp_m"] > 0
    assert c["correction_per_household_clock"] == pytest.approx(
        (c["nz5_gbp_m"] - c["clock_cm_gbp_m"]) * 1e6 / R.CLOCK_HOUSEHOLDS)
    assert -43.4 < c["correction_per_household_clock"] < 0



# ----------------------------------------------------------------------------- s27c integration

def test_s27_switch_defaults_are_the_new_central():
    c = B.CENTRAL
    assert (c.moe, c.gas_feedback, c.coal_lf) == ("shao", "central", "dukes_max")
    assert (c.tnuos_gen, c.bsuos_gen, c.go5_index, c.fit_basis) == ("removed", "removed", "rpi", "levelisation")
    assert c.cfd_split and c.carbon_split
    o = B.OLD_CENTRAL
    assert (o.moe, o.gas_feedback, o.coal_lf, o.tnuos_gen, o.bsuos_gen, o.go5_index, o.fit_basis) == (
        "none", "none", "none", "included", "included", "cpih", "scheme_value")
    # decision 0144 item 4A (Richard Lyon, 20 Oct 2026; v4-s37): the stack row left the range for the methods page
    assert "merit-order uplift (engine's own stack estimate)" in B.METHOD_SWITCHES
    assert "merit-order uplift (engine's own stack estimate)" not in B.SWITCHES
    assert not any("high side" in k for k in B.SWITCHES)


def test_biomass_cfd_and_carbon_split_add_up_and_regroup():
    from gascf import subsidies
    b = B.build()
    allc = subsidies.cfd(YEARS, "all")
    for y in YEARS:
        assert B.val(b[y], "NZ4") + B.val(b[y], "NZ4b") == pytest.approx(allc[y]["gbp_m"], abs=1e-6), y
        assert B.line(b[y], "NZ4b")["group"] == "subsidies"
        cs = b[y]["carbon_split"]
        assert (cs["carbon_price_receipts"]["national_gbp_m_nominal"] + cs["carbon_in_price"]["national_gbp_m_nominal"]
                == pytest.approx(B.val(b[y], "NZ1c"), abs=1e-6)), y
        assert B.line(b[y], "NZ8")["group"] == "ccl"
        assert B.line(b[y], "NZ1c_tax")["group"] == "carbon_price_receipts"
    g = {s["group"] for s in W.grouped(W.steps_for(b[2025], 2025))}
    assert {"carbon_price_receipts", "ccl", "carbon_in_price"} <= g and "carbon" not in g


def test_relabel_switches_do_not_move_the_gap():
    """cfd_split and carbon_split are layout only (s27b bills-patch item 7)."""
    c = B.build()
    o = B.build(B.replace(B.CENTRAL, cfd_split=False, carbon_split=False))
    for y in YEARS:
        assert o[y]["totals"]["gap_gbp_m"] == pytest.approx(c[y]["totals"]["gap_gbp_m"], abs=1e-6), y
        assert "carbon_split" not in o[y] and all(l["id"] != "NZ4b" for l in o[y]["netzero"])
    g = {s["group"] for s in W.grouped(W.steps_for(o[2025], 2025))}
    assert "carbon" in g


def test_netzero_fallbacks_are_registered():
    from gascf import carbon, fallbacks, subsidies
    B.build()
    names = {f["name"] for f in fallbacks.recorded()}
    for f in subsidies.FIT_FALLBACKS + carbon.CARBON_FALLBACKS:
        assert f["name"] in fallbacks.DECLARED and f["name"] in names, f["name"]
    assert "bsuos-gen-share-interpolated" in names
