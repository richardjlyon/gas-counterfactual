"""Gas-price sensitivity and the DESNZ reconciliation (brief s12)."""
import pytest

from gascf import receipt_actual as ra
from gascf import sensitivity as sv
from gascf import staircase as sc
from gascf.breakeven import cfd_volume, fit_cap_periods

Q4 = sv.Q4_2026


# ------------------------------------------------------------------ DESNZ inputs, read from stored files

def test_ffpa_gas_spot_values_match_table_1():
    """FFPA 2025 Table 1 (p.7 of the PDF), p/therm real 2024: 2024 = 84 in all cases;
    2030 = 42 / 71 / 120 (A / B / C); 2050 B = 66."""
    g = sv.ffpa_gas()
    assert (g["A"][2024], g["B"][2024], g["C"][2024]) == (84, 84, 84)
    assert (g["A"][2030], g["B"][2030], g["C"][2030]) == (42, 71, 120)
    assert g["B"][2050] == 66


def test_therm_factor_is_ofgems():
    assert sv.therm_factor() == pytest.approx(2.9307111, abs=1e-12)


def test_desnz_gas_in_gbp_mwh():
    d = sv.desnz_gas()
    assert d["p_therm_2024"].value == 71
    assert d["gbp_mwh_2024"].value == pytest.approx(71 / 2.9307111, rel=1e-12)
    assert 25 < d["gbp_mwh"].value < 26.5                      # 2026 money, ~+6% deflator
    assert d["p_therm_2024"].basis == "measured" and d["gbp_mwh"].basis == "modelled"


def test_desnz_printed_column():
    p = sv.desnz_printed()
    assert (p["Total"], p["Carbon costs"], p["Fuel costs"], p["Construction costs"]) == (111, 41, 45, 15)
    assert p["Total"] - p["Carbon costs"] == 70


def test_desnz_fuel_row_is_its_2030_central_gas_price():
    """Annex A's fuel row (45, rounded) needs 70.4–72.0 p/therm at η 0.54; FFPA B 2030 is 71."""
    ours, printed = sv.rebuild_rows()["Fuel costs"]
    assert abs(ours - printed) <= 0.5
    # and the low and high cases do not reproduce it
    for case in ("A", "C"):
        g = sv.ffpa_gas()[case][2030] / sv.therm_factor() / 0.54
        assert abs(g - printed) > 5


def test_rebuild_matches_every_printed_row_within_rounding():
    for row, (ours, printed) in sv.rebuild_rows().items():
        assert abs(ours - printed) <= 0.5 + 1e-9, row


# ------------------------------------------------------------------ the actual side moves with the regression

def test_actual_unchanged_at_todays_gas_price():
    p = sc.annex2_periods()[Q4]
    r0, r1 = ra.receipt(Q4), sv.actual_receipt_at_gas(Q4, p.gas_index)
    for a, b in zip(r0.lines, r1.lines):
        assert (a.key, a.typical, a.nil) == (b.key, pytest.approx(b.typical, abs=1e-9), pytest.approx(b.nil, abs=1e-9))


def test_actual_wholesale_and_cfd_move_by_slope():
    """Independent check: wholesale moves by uplift-and-losses x slope x ΔG x Q; CfD by
    −share x slope x ΔG x Q."""
    p = sc.annex2_periods()[Q4]
    r0 = ra.receipt(Q4)
    b = fit_cap_periods(False).b
    s = cfd_volume().share
    ul = sum(p.supplied.values()) / len(p.supplied) / p.elec_index
    dG = 60.0 - p.gas_index
    r1 = sv.actual_receipt_at_gas(Q4, 60.0)
    Q = r0.consumption_mwh
    assert r1.line("direct_fuel").typical - r0.line("direct_fuel").typical == pytest.approx(ul * b * dG * Q, rel=1e-12)
    assert r1.line("cfd").typical - r0.line("cfd").typical == pytest.approx(-s * b * dG * Q, rel=1e-12)
    assert r1.line("direct_fuel").nil == r0.line("direct_fuel").nil
    # VAT rate is zero for Q4 2026 (Layer 2); total ex VAT moves by more than wholesale + CfD
    # because headroom, EBIT and bad debt are percentages
    d_lines = (r1.line("direct_fuel").typical - r0.line("direct_fuel").typical
               + r1.line("cfd").typical - r0.line("cfd").typical)
    assert r1.total_ex_vat - r0.total_ex_vat > d_lines > 0


def test_cfd_switch_off():
    r0 = ra.receipt(Q4)
    r1 = sv.actual_receipt_at_gas(Q4, 80.0, cfd_moves=False)
    assert r1.line("cfd").typical == r0.line("cfd").typical


def test_override_is_undone_even_on_error():
    before = sc.annex2_periods()[Q4].gas_index
    with pytest.raises(RuntimeError):
        with sv._gas_override(Q4, 99.0, "all", True):
            assert sc.annex2_periods()[Q4].gas_index == 99.0
            raise RuntimeError
    assert sc.annex2_periods()[Q4].gas_index == before
    assert sc.ra is ra


# ------------------------------------------------------------------ the sweep

@pytest.fixture(scope="module")
def rows():
    return sv.sweep()


def test_sweep_covers_brief(rows):
    labels = {r.label for r in rows}
    assert len(rows) == 7 * 2 * 2
    assert {"£20", "£30", "£60", "£80", "£100"} <= labels
    assert any(l.startswith("DESNZ central") for l in labels) and any(l.startswith("current") for l in labels)


def test_identity_holds_at_every_price(rows):
    for r in rows:
        assert abs(r.identity_residual) < 1e-8, (r.label, r.fleet, r.slope)
        assert r.headline == pytest.approx(r.actual_total - r.step1, abs=1e-12)


def test_current_price_reproduces_the_staircase(rows):
    for fl in ("A", "B"):
        s = sc.staircase(Q4, fl)
        r = next(x for x in rows if x.label.startswith("current") and x.fleet == fl and x.slope == "all")
        assert r.actual_total == pytest.approx(s.actual_total, abs=1e-9)
        assert r.step1 == pytest.approx(s.steps["1"], abs=1e-9)


def test_both_columns_rise_with_gas(rows):
    for fl in ("A", "B"):
        for sl in ("all", "ex_epg"):
            xs = sorted((r for r in rows if r.fleet == fl and r.slope == sl), key=lambda r: r.gas_gbp_mwh)
            for a, b in zip(xs, xs[1:]):
                assert b.actual_total > a.actual_total and b.step1 > a.step1 and b.fleet_gbp_mwh > a.fleet_gbp_mwh


def test_headline_positive_everywhere(rows):
    """Net zero costs more than pure gas at every price tried, both fleets, both slopes."""
    assert min(r.headline for r in rows) > 0


def test_fleet_cost_matches_staircase_fleet_function(rows):
    """Independent route: staircase.fleet_gbp_mwh with gas rebased to 2024 money."""
    from gascf.deflator import rebase
    s = sc.staircase(Q4, "B")
    r = next(x for x in rows if x.label == "£60" and x.fleet == "B" and x.slope == "all")
    want = sc.fleet_gbp_mwh("B", s.inputs["ldc_year"], round(rebase(60.0, 2026, 2024), 9)) * rebase(1.0, 2024, 2026)
    assert r.fleet_gbp_mwh == pytest.approx(want, rel=1e-12)


# ------------------------------------------------------------------ the reconciliation

@pytest.fixture(scope="module")
def rec():
    return sv.reconcile()


@pytest.mark.parametrize("fleet", ["A", "B"])
def test_reconciliation_adds_up(rec, fleet):
    steps = rec[fleet]
    assert steps[0].level == 70.0
    assert steps[0].level + sum(s.delta for s in steps[1:]) == pytest.approx(steps[-1].level, abs=1e-9)
    assert steps[-1].level == pytest.approx(sc.staircase(Q4, fleet).inputs["fleet_gbp_mwh"], abs=1e-6)
    assert all(s.basis in ("measured", "modelled", "estimated") and s.source_id for s in steps)


def test_gas_price_step_is_fuel_only(rec):
    """Changing the gas price for one plant moves cost by ΔG / η and nothing else."""
    from gascf.deflator import rebase
    st = next(s for s in rec["B"] if s.name.startswith("Gas price"))
    g_now24 = sc.annex2_periods()[Q4].gas_index * rebase(1.0, 2026, 2024)
    assert st.delta == pytest.approx((g_now24 - sv.desnz_gas()["gbp_mwh_2024"].value) / 0.54, rel=1e-12)


def test_one_plant_rebuild_equals_row_by_row_rebuild(rec):
    """Independent route: the 'our rebuild' level from plant.annualised_fixed_gbp_kw_yr must
    equal the five rows rebuilt one by one (capital levelised on discounted output)."""
    st = next(s for s in rec["B"] if s.name.startswith("Our rebuild"))
    assert st.level == pytest.approx(sum(o for o, _ in sv.rebuild_rows().values()), rel=1e-9)


def test_transport_step_matches_national_gas_charges(rec):
    """Exit capacity for 1 kW electric at full load, spread over 8.76 x 0.86 MWh, plus
    commodity / η: computed here from the GasTransport fields directly."""
    t = sc._fleet_kit()["transport"]
    want = (t.exit_capacity_p_kwh_day / 100 * 24 / 0.54 * 365) / (8.76 * 0.86) + t.commodity_p_kwh * 10 / 0.54
    st = next(s for s in rec["B"] if s.name.startswith("Gas pipeline"))
    assert st.delta == pytest.approx(want, rel=1e-9)


def test_gas_price_is_the_biggest_step(rec):
    for fl in ("A", "B"):
        moves = [abs(s.delta) for s in rec[fl][1:] if not s.name.startswith("Price base")]
        gas = next(abs(s.delta) for s in rec[fl] if s.name.startswith("Gas price"))
        assert gas == max(moves)
