"""Staircase and all-gas Britain column (spec §2, §6, §7.3, §12).

The identity test is the core one: for every cap period, both fleets and both orders, the
actual total = step 1 + 2 + 3 + 4a + 4b + 4c, and every line's actual − all-gas difference is
assigned in full to steps.
"""
import pytest

from gascf import receipt_actual as ra
from gascf import staircase as st

PERIODS = [r.period for r in ra.receipts()]
Q4_2026 = (2026, 10, 2026, 12)


@pytest.fixture(scope="module")
def all_a():
    return {k: st.staircase(k, "A") for k in PERIODS}


@pytest.fixture(scope="module")
def all_b():
    return {k: st.staircase(k, "B") for k in PERIODS}


# ------------------------------------------------------------------ identity

def test_32_periods():
    assert len(PERIODS) == 32
    assert PERIODS[0] == (2015, 4, 2015, 9) and PERIODS[-1] == Q4_2026


@pytest.mark.parametrize("fleet", ["A", "B", "D"])
@pytest.mark.parametrize("order", ["carbon_first", "renewables_first"])
@pytest.mark.parametrize("kwh", [2500.0, None])
def test_identity_every_period(fleet, order, kwh):
    for k in PERIODS:
        s = st.staircase(k, fleet, kwh=kwh, order=order)
        assert s.actual_total == pytest.approx(sum(s.steps.values()), abs=1e-8), s.label
        assert s.steps["1"] == pytest.approx(s.all_gas_total, abs=1e-9)
        for ln in s.lines:
            # every line's difference is assigned, in full, to the steps
            assert ln.actual - ln.all_gas == pytest.approx(sum(ln.by_step.values()), abs=1e-8), (s.label, ln.key)
            # a line held equal (or a zero line) contributes nothing to steps 2-4
            if ln.step == "1" or ln.actual == ln.all_gas == 0:
                assert all(abs(v) < 1e-9 for v in ln.by_step.values()), (s.label, ln.key)
            # a driver line moves in exactly the step it names
            elif ln.step in st.STEPS:
                assert all(abs(v) < 1e-9 for kk, v in ln.by_step.items() if kk != ln.step)


def test_actual_column_is_the_receipt(all_a):
    """Actual side not adjusted (spec §2): bill lines equal receipt_actual at 2,500 kWh."""
    for k, s in all_a.items():
        rc = ra.at_consumption(k, 2500)
        bill = sum(ln.actual for ln in s.lines if ln.key != "ro_treasury")
        assert bill == pytest.approx(rc.total, abs=1e-6), s.label
        # the 4b carve-outs come out of BSUoS / TNUoS, so network total is unchanged
        net = sum(s.line(x).actual for x in ("tnuos", "duos", "bsuos", "constraint_difference", "ofto")
                  if x in {ln.key for ln in s.lines})
        assert net == pytest.approx(sum(rc.line(x).typical for x in ("tnuos", "duos", "bsuos")), abs=1e-6)


def test_ofgem_consumption_matches_published(all_a):
    """At Ofgem's own consumption the actual bill = Ofgem's published GB-average level."""
    for k in PERIODS:
        s = st.staircase(k, "A", kwh=None)
        bill = sum(ln.actual for ln in s.lines if ln.key != "ro_treasury")
        r = ra.receipt(k)
        assert bill == pytest.approx(r.published_inc_vat, abs=0.02), s.label


def test_fixed_and_per_kwh_restate_any_size(all_a):
    s = all_a[Q4_2026]
    s0 = st.staircase(Q4_2026, "A", kwh=4000)
    for ln, ln0 in zip(s.lines, s0.lines):
        for kwh, x in ((2500, ln), (4000, ln0)):
            assert x.actual == pytest.approx(ln.actual_fixed_gbp + ln.actual_gbp_per_kwh * kwh, abs=1e-6)
            assert x.all_gas == pytest.approx(ln.all_gas_fixed_gbp + ln.all_gas_gbp_per_kwh * kwh, abs=1e-6)
            for k2 in st.STEPS[1:]:
                assert x.by_step[k2] == pytest.approx(
                    ln.by_step_fixed_gbp[k2] + ln.by_step_gbp_per_kwh[k2] * kwh, abs=1e-6)


def test_every_line_tagged(all_a, all_b):
    for d in (all_a, all_b):
        for s in d.values():
            for ln in s.lines:
                # receipt lines are Ofgem ex-ante allowances: never relabelled 'measured'
                assert ln.basis_actual in ("allowance", "modelled", "estimated"), ln.key
                assert ln.basis_all_gas in ("allowance", "modelled", "estimated"), ln.key
                assert ln.source_id


# ------------------------------------------------------------------ step contents

def test_step_assignment_q4_2026(all_a):
    s = all_a[Q4_2026]
    step = {ln.key: ln.step for ln in s.lines}
    for k in ("cfd", "ro", "fit", "ro_treasury"):
        assert step[k] == "4a" and s.line(k).all_gas == 0
    for k in ("eco", "sizewell_c"):
        assert step[k] == "3" and s.line(k).all_gas == 0
    # Richard, 11 Oct 2026, decision 3: not net zero, held equal in both columns
    for k in ("whd", "aahedc", "eii_levy"):
        assert step[k] == "1" and s.line(k).all_gas == s.line(k).actual and s.line(k).note
    assert step["ofto"] == "4b"
    for k in ("backwardation", "duos", "core_operating_costs", "levelisation", "adjustment_allowance"):
        assert step[k] == "1"
    assert step["capacity_market"] == ("1" if s.fleet == "A" else "4c")
    assert step["direct_fuel"] == "2+4c"
    for k in ("debt_related_costs", "ebit", "headroom", "vat"):
        assert step[k] == "pro rata"
    # spec §6 figures at 2,500 kWh
    assert s.line("direct_fuel").actual == pytest.approx(301.13, abs=0.01)
    assert s.line("backwardation").actual == pytest.approx(22.46, abs=0.01)
    assert s.line("cfd").actual == pytest.approx(17.14, abs=0.01)
    assert s.line("capacity_market").actual == pytest.approx(38.44, abs=0.01)
    assert sum(s.line(k).actual for k in st.STEP3 + st.NOT_NET_ZERO if k != "eco") == pytest.approx(
        31.35, abs=0.01)
    assert s.line("ro_treasury").actual == pytest.approx(61.37, abs=0.01)
    # step 3 = the four levies exactly (no supplier percentage lines depend on them? they do:
    # pro-rata share of the percentage lines is added, so step 3 >= the levies)
    assert s.steps["3"] >= sum(s.line(k).actual for k in st.STEP3) - 1e-9


def test_step3_and_4a_include_their_pro_rata_share(all_a):
    s = all_a[Q4_2026]
    levies = sum(s.line(k).actual for k in st.STEP3)
    pro = sum(s.line(k).by_step["3"] for k in ("debt_related_costs", "ebit", "headroom", "vat",
                                                 "payment_adjustment_pct"))
    assert s.steps["3"] == pytest.approx(levies + pro, abs=1e-9)
    assert pro > 0


def test_layer3_beside_not_inside(all_a):
    for s in all_a.values():
        keys = {ln.key for ln in s.lines}
        assert not any("goods" in k or "layer3" in k for k in keys)
    s = all_a[(2024, 4, 2024, 6)]
    assert s.layer3["per_household"]["central"] > 0
    assert s.actual_total == pytest.approx(sum(s.steps.values()), abs=1e-8)


def test_fleet_b_cm_removes_only_the_gas_share(all_b, all_a):
    """Spec §3.3 (s15 S4): fleet B's £/MWh already pays for the gas plant, so the CM paid to gas
    plant is removed; the CM paid to everything else is kept. Fleet A and DESNZ: held equal."""
    b, a = all_b[Q4_2026], all_a[Q4_2026]
    cm = b.line("capacity_market")
    share = st.cm_gas_share()["used"]
    assert cm.step == "4c" and b.inputs["cm_gas_share"] == share
    assert cm.all_gas == pytest.approx(cm.actual * (1 - share), rel=1e-9)
    assert cm.by_step["4c"] == pytest.approx(cm.actual * share, rel=1e-9)
    assert a.line("capacity_market").all_gas == a.line("capacity_market").actual   # fleet A: held equal
    d = st.staircase(Q4_2026, "D").line("capacity_market")
    assert d.all_gas == d.actual and d.step == "1"


def test_cm_gas_share_read_from_ofgem_reports():
    """Ofgem CM annual reports: DY 2026/27 T-4 (held 2022/23) and T-1 (held 2025/26)."""
    c = st.cm_gas_share()
    t4, t1 = c["auctions"]["T-4"], c["auctions"]["T-1"]
    assert (t4["price_gbp_kw_yr"], t4["total_gw"], t4["gas_gw"]) == (63.0, 43.0, 29.0)
    assert (t1["price_gbp_kw_yr"], t1["total_gw"], t1["gas_gw"]) == (5.0, 7.2, 2.1)
    assert c["capacity_share"] == pytest.approx(31.1 / 50.2)
    assert c["used"] == min(c["capacity_share"], c["payment_share"])


def test_cm_reader_fails_loudly_if_text_moves(monkeypatch, tmp_path):
    import pymupdf
    bad = tmp_path / "bad.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "nothing here")
    doc.save(bad)
    monkeypatch.setattr(st, "CM_REPORTS", {"T-4": bad, "T-1": bad})
    st.cm_gas_share.cache_clear()
    try:
        with pytest.raises(ValueError):
            st.cm_gas_share()
    finally:
        monkeypatch.undo()
        st.cm_gas_share.cache_clear()


# ------------------------------------------------------------------ Richard's decisions, 11 Oct 2026

def test_desnz_gas_power_is_total_less_carbon():
    """Decision 1(a): DESNZ EGC 2025 Annex A, Gas CCGT 93% load factor, 2030: £111 - £41 = £70."""
    d = st.desnz_gas_power_2024()
    assert (d["total"], d["carbon"]) == (111, 41)
    assert d["gbp_mwh_2024"] == 70


def test_fleet_d_uses_desnz_figure_restated(all_a):
    from gascf.deflator import rebase
    s = st.staircase(Q4_2026, "D")
    assert s.inputs["fleet_gbp_mwh"] == pytest.approx(rebase(70.0, 2024, 2026), rel=1e-12)
    q = s.kwh / 1000
    assert s.line("direct_fuel").all_gas == pytest.approx(s.inputs["fleet_gbp_mwh"] * s.inputs["uplift_losses"] * q)
    assert s.actual_total == pytest.approx(all_a[Q4_2026].actual_total, abs=1e-9)   # what you pay: unchanged
    assert any("DESNZ EGC 2025 Annex A" in n for n in s.notes)
    assert not any("gas transport" in n for n in s.notes)


def test_no_carbon_in_all_gas_column():
    """Decision 2: all-gas Britain pays no carbon price: step 1 is the fleet cost without carbon."""
    for f in ("A", "B", "D"):
        s = st.staircase(Q4_2026, f)
        q = s.kwh / 1000
        assert s.line("direct_fuel").all_gas == pytest.approx(
            s.inputs["fleet_gbp_mwh"] * s.inputs["uplift_losses"] * q, rel=1e-12)
        assert s.steps["2"] > 0


def test_margin_is_volume_weighted_mean():
    """S2 (spec §3, decided 11 Oct 2026): the gas-market margin is the volume-weighted mean of the
    §8 spread; its median equals validate_year's (same loop and filters)."""
    from gascf.validate import validate_year
    m = st.margin_stats(2025)
    assert st.MARGIN_STAT == "vw_mean"
    assert m["median"] == pytest.approx(validate_year(2025).spread_median, abs=1e-9)
    assert st._margin(2025) == m["vw_mean"]
    s = st.staircase(Q4_2026, "A")
    assert s.inputs["gas_market_margin_gbp_mwh"] == st._margin(s.inputs["margin_year"])


@pytest.mark.parametrize("kw", [dict(eta="new"), dict(capex="high"), dict(hurdle="low"),
                                dict(gas_mult=1.5)])
def test_switches_keep_identity_and_actual(kw, all_a):
    for f in ("A", "B", "D"):
        s = st.staircase(Q4_2026, f, **kw)
        assert s.actual_total == pytest.approx(sum(s.steps.values()), abs=1e-8)
        assert s.actual_total == pytest.approx(all_a[Q4_2026].actual_total, abs=1e-9)


def test_switch_directions():
    base = {f: st.staircase(Q4_2026, f) for f in "AB"}
    assert st.staircase(Q4_2026, "A", eta="new").all_gas_total < base["A"].all_gas_total
    assert st.staircase(Q4_2026, "B", capex="high").all_gas_total > base["B"].all_gas_total
    assert st.staircase(Q4_2026, "B", hurdle="low").all_gas_total < base["B"].all_gas_total
    for f in "ABD":
        assert st.staircase(Q4_2026, f, gas_mult=1.5).all_gas_total > st.staircase(Q4_2026, f).all_gas_total
    with pytest.raises(ValueError):
        st.staircase(Q4_2026, "C")
    with pytest.raises(ValueError):
        st.staircase(Q4_2026, "A", capex="huge")


def test_constraint_null_or_present_never_silent(all_a):
    """Coverage follows system_costs (being reworked): wherever it raises, the line is null
    with a reason and the cost stays inside BSUoS; wherever it returns, the line is in 4b."""
    from gascf.system_costs import constraint_per_household_current
    for k, s in all_a.items():
        reasons = dict(s.nulls)
        try:
            constraint_per_household_current(st.fy_of(k), price_year=st.price_year(k))
            ok = True
        except (KeyError, ValueError):
            ok = False
        if ok:
            assert "constraint_difference" not in reasons and s.line("constraint_difference").step == "4b"
        else:
            assert "held equal" in reasons["constraint_difference"], s.label
            assert "constraint_difference" not in {ln.key for ln in s.lines}


# ------------------------------------------------------------------ percentage lines

def test_ofgem_percentage_formulas_reproduce_actual():
    """f(actual bill) reproduces Ofgem's payment-method %, debt, EBIT and headroom lines.

    Known exception: Apr-Jun and Jul-Sep 2024 EBIT, where Annex 9 v1.11's published EBIT
    (22.39, 21.54) differs from cap model v1.31's own GB-average EBIT (22.48, 21.62) by ~8p;
    the cap model formula reproduces the cap model. The staircase's delta form
    (actual + f(state) − f(actual)) keeps the actual column on Annex 9 regardless."""
    known = {(2024, 4, 2024, 6), (2024, 7, 2024, 9)}
    for r in ra.receipts():
        vec = {ln.key: (ln.typical, ln.nil) for ln in r.lines if ln.key != "vat"}
        f = st.apply_pct(vec, st._rules_for(r.period))
        for code, key in st.PCT.items():
            for side in (0, 1):
                tol = 0.10 if (r.period in known and code == "E") else 0.01
                assert f[code][side] == pytest.approx(vec[key][side], abs=tol), (r.label, code, side)
    cm = ra._cap_model()
    for k in known:
        assert st.apply_pct({ln.key: (ln.typical, ln.nil) for ln in ra.receipt(k).lines if ln.key != "vat"},
                            st._rules_for(k))["E"][0] == pytest.approx(cm[k]["typical"]["E"], abs=0.01)


def test_headroom_rate_read_from_cap_model():
    rules = st._rules_for(Q4_2026)
    assert rules["typical"]["H"].rate == pytest.approx(0.014641)   # '3l HAP'!E9
    assert "NC" not in rules["typical"]["H"].base                    # headroom excludes networks
    assert rules["typical"]["PAP"] is None                          # no PAP from Apr 2025


# ------------------------------------------------------------------ wholesale and carbon

def test_all_gas_wholesale_is_fleet_through_ofgem_chain(all_a):
    s = all_a[Q4_2026]
    i = s.inputs
    assert i["gas_index_gbp_mwh"] == pytest.approx(st.annex2_periods()[Q4_2026].gas_index)
    q = s.kwh / 1000
    assert s.line("direct_fuel").all_gas == pytest.approx(i["fleet_gbp_mwh"] * i["uplift_losses"] * q, rel=1e-9)
    assert 1.0 < i["uplift_losses"] < 1.3


def test_carbon_first_vs_reversed():
    """Reversed order (renewables first) gives a larger renewables step (spec §7.3, brief)."""
    for fleet in ("A", "B"):
        for k in ((2019, 4, 2019, 9), (2022, 10, 2022, 12), (2025, 4, 2025, 6), Q4_2026):
            a = st.staircase(k, fleet, order="carbon_first")
            b = st.staircase(k, fleet, order="renewables_first")
            assert b.renewables > a.renewables, (fleet, k)
            assert a.steps["2"] > b.steps["2"]
            assert a.steps["3"] == pytest.approx(b.steps["3"], rel=0.05)


def test_spec_12_spot_check():
    """8 Oct 2026, SAP 6.417 p/kWh at η 0.4799: 133.71 + 4.44 + 1 = £139.15/MWh.
    Exact values 133.7154 and 139.1554; the spec truncates to 2 dp (as test_today notes)."""
    from gascf.today import cepa_vom_existing, fleet_a_running
    fuel = 64.17 / 0.4799
    assert int(fuel * 100) / 100 == 133.71
    assert cepa_vom_existing() == 4.44
    v = fleet_a_running(64.17, 0.4799, cepa_vom_existing(), 1.0)
    assert v == pytest.approx(139.1554, abs=1e-4) and int(v * 100) / 100 == 139.15


def test_fleet_a_pure_running_cost_matches_spot_logic():
    """Fleet A on a flat load the existing fleet covers = gas/η + VOM + margin (no carbon)."""
    from gascf.fleeta import cost_fleet_a
    kit = st._fleet_kit()
    flat = [10_000.0] * 17520
    f = cost_fleet_a(flat, 64.17, 0.4799, 4.44, 1.0, {"ccgt": 30_000, "single_cycle": 0},
                     kit["ccgt"], kit["ocgt"], 0.0, {"ccgt": 1.0, "ocgt": 1.0})
    assert f.gbp_per_mwh == pytest.approx(139.1554, abs=1e-4)      # spec truncates: 139.15


# ------------------------------------------------------------------ replaced set

def test_replaced_generation_is_subsidised_set():
    """Spec §12: replaced = wind, biomass, hydro (RO), embedded wind and solar (FiT/RO);
    coal and oil are NOT replaced (no subsidy) and nuclear, imports, storage are kept."""
    from gascf.residual import FOSSIL_NON_GAS, HYDRO, KEPT, RENEWABLE, residual_year
    assert st.REPLACE_COAL_OIL is False and st.REPLACE_HYDRO is True
    assert set(RENEWABLE) == {"WIND", "BIOMASS"} and "NUCLEAR" in KEPT
    rows_kept, _ = residual_year(2017, replace_coal_oil=False)
    rows_repl, _ = residual_year(2017, replace_coal_oil=True)
    used = st._ldc(2017)
    assert max(used) == pytest.approx(max(r.residual for r in rows_kept))
    # 2017 had coal on the system, so keeping it gives a smaller residual
    assert sum(r.residual for r in rows_kept) < sum(r.residual for r in rows_repl)
    assert set(FOSSIL_NON_GAS) == {"COAL", "OIL"} and HYDRO == ("NPSHYD",)


# ------------------------------------------------------------------ period mapping

def test_price_year_and_fy():
    assert st.price_year((2015, 4, 2015, 9)) == 2015
    assert st.price_year((2015, 10, 2016, 3)) == 2015      # 3 + 3 months: tie -> start year
    assert st.price_year((2026, 10, 2026, 12)) == 2026
    assert st.fy_of((2023, 1, 2023, 3)) == 2022
    assert st.nearest(2015, st.RESIDUAL_YEARS) == (2016, True)
    assert st.nearest(2026, st.RESIDUAL_YEARS) == (2025, True)


def test_eco_step3_and_held_equal_lines_every_period(all_a, all_b):
    """ECO is in step 3 (DESNZ ECO4 guidance §1.2); adjustment allowance, levelisation and the
    not-net-zero lines are held equal (step 1) in every period."""
    for d in (all_a, all_b):
        for s in d.values():
            keys = {ln.key for ln in s.lines}
            assert s.line("eco").step == "3" and s.line("eco").all_gas == 0, s.label
            for k in ("adjustment_allowance", "levelisation") + st.NOT_NET_ZERO:
                if k in keys:
                    ln = s.line(k)
                    assert ln.step == "1" and ln.all_gas == ln.actual and ln.note, (s.label, k)


def test_constraint_line_comes_from_system_costs():
    """The 4b constraint line is whatever system_costs.constraint_per_household returns
    (its baseline is being reworked): no values pinned here, only the plumbing."""
    from gascf.system_costs import constraint_per_household
    k = (2023, 4, 2023, 6)
    s = st.staircase(k, "A", kwh=None)
    if "constraint_difference" in dict(s.nulls):
        pytest.skip("system_costs gives no constraint line for FY 2023/24")
    c = constraint_per_household(st.fy_of(k), price_year=st.price_year(k))
    q = s.ofgem_kwh / 1000
    assert s.line("constraint_difference").actual == pytest.approx(
        c["difference_per_2500kwh"].value / 2.5 * q, rel=1e-9)
    assert s.line("constraint_difference").all_gas == 0
    assert s.line("constraint_difference").step == "4b"



# ------------------------------------------------------------------ s11: the three missing costs

def test_q4_2026_constraint_uses_trailing_12_months(all_a):
    """FY 2026/27 is incomplete: 4(b) takes the trailing 12 months to the latest NESO day."""
    from gascf import system_costs as sc
    s = all_a[Q4_2026]
    assert "constraint_difference" not in dict(s.nulls)
    c = sc.constraint_per_household_current(2026, price_year=2026)
    assert "window" in c
    q = s.ofgem_kwh / 1000
    ln = s.line("constraint_difference")
    assert ln.step == "4b" and ln.all_gas == 0
    assert ln.actual == pytest.approx(c["difference_per_2500kwh"].value, rel=1e-9)   # 2,500 kWh
    assert ln.basis_actual == c["difference_per_2500kwh"].basis
    assert any("trailing 12 months" in n for n in s.notes)
    # carved out of BSUoS, not added: BSUoS + constraint line = Ofgem's BSUoS allowance
    b = next(x for x in ra.receipt(Q4_2026).lines if x.key == "bsuos")
    allowance = b.nil + (b.typical - b.nil) * 2.5 / q
    assert s.line("bsuos").actual + ln.actual == pytest.approx(allowance, abs=1e-9)


def test_grid_netzero_low_default_high_bracket():
    """Low (£0) is the default; high moves exactly the bracket from step 1 to 4(b)."""
    from gascf.network_netzero import grid_netzero_per_household
    lo, hi = st.staircase(Q4_2026, "A"), st.staircase(Q4_2026, "A", grid="high")
    g = grid_netzero_per_household(2026, price_year=2026)
    assert lo.line("grid_netzero").actual == 0 and lo.inputs["grid_case"] == "low"
    assert hi.line("grid_netzero").actual == pytest.approx(g.high, rel=1e-12)
    assert hi.line("grid_netzero").step == "4b" and hi.line("grid_netzero").all_gas == 0
    assert hi.actual_total == pytest.approx(lo.actual_total, abs=1e-9)        # actual bill unchanged
    assert hi.steps["4b"] - lo.steps["4b"] == pytest.approx(g.high, abs=1e-9)
    assert lo.steps["1"] - hi.steps["1"] == pytest.approx(g.high, abs=1e-9)
    # TNUoS is reduced by the same amount (carve-out, not addition)
    assert lo.line("tnuos").actual - hi.line("tnuos").actual == pytest.approx(g.high, abs=1e-9)
    with pytest.raises(ValueError):
        st.staircase(Q4_2026, "A", grid="middle")


@pytest.mark.parametrize("fleet", ["A", "B", "D"])
def test_identity_holds_with_grid_high(fleet):
    for k in PERIODS[-6:]:
        s = st.staircase(k, fleet, grid="high")
        assert s.actual_total == pytest.approx(sum(s.steps.values()), abs=1e-8), s.label


def test_grid_netzero_null_before_riio3(all_a):
    """Before April 2026 no regulator per-household figure: null with the reason, never zero-filled."""
    for k, s in all_a.items():
        if st.fy_of(k) < 2026:
            assert "grid_netzero" in dict(s.nulls), s.label
            assert "UNSOURCED" in dict(s.nulls)["grid_netzero"]
            assert "grid_netzero" not in {ln.key for ln in s.lines}
        else:
            assert "grid_netzero" not in dict(s.nulls)
