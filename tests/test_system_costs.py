"""Tests for system_costs: constraint payments, OFTO demand share, GB households.

Spot values are the figures in the stored source files, checked by eye when written.
"""
import pytest

from gascf import system_costs as sc
from gascf.deflator import rebase


# ----------------------------------------------------------------- constraints

def test_constraint_spot_values():
    y = sc.read_constraint_breakdown()
    # NESO constraint-breakdown, sum of each cost column over the FY file (all four categories)
    assert y[2017].cost_all_categories / 1e6 == pytest.approx(396.9, abs=0.1)
    assert y[2022].cost_all_categories / 1e6 == pytest.approx(1754.3, abs=0.1)
    assert y[2024].cost_all_categories / 1e6 == pytest.approx(1904.6, abs=0.1)
    # counted (thermal + voltage) only: 2017/18 thermal 309.4m + voltage 28.3m
    assert y[2017].category_cost("Thermal constraints") / 1e6 == pytest.approx(309.4, abs=0.1)
    assert y[2017].category_cost("Voltage constraints") / 1e6 == pytest.approx(28.3, abs=0.1)
    assert y[2017].cost_gbp == pytest.approx(y[2017].category_cost("Thermal constraints")
                                             + y[2017].category_cost("Voltage constraints"))
    # volume columns: sum of |daily net| MWh (review B1 table: thermal 3.71 / 5.16 / 12.15 TWh)
    assert y[2017].volume_mwh["Thermal constraints"] == pytest.approx(3_707_484, abs=1)
    assert y[2022].volume_mwh["Thermal constraints"] / 1e6 == pytest.approx(5.16, abs=0.01)
    assert y[2024].volume_mwh["Thermal constraints"] / 1e6 == pytest.approx(12.15, abs=0.01)
    assert y[2017].days == 365 and y[2019].days == 366
    assert not y[2026].complete          # 2026/27 is part-year: never annualised


def test_inertia_not_counted_in_4b():
    """Review S6 / spec §6: stability (NESO's 'Inertia' group) is 'not counted'."""
    assert set(sc.COUNTED) == {"Voltage constraints", "Thermal constraints"}
    assert set(sc.NOT_COUNTED) == {"Reducing largest loss", "Increasing system inertia"}
    # NESO's own grouping, quoted from the stored dataset metadata
    assert sc.NESO_GROUPING_QUOTE in sc.PACKAGE_SHOW.read_text()
    y = sc.read_constraint_breakdown()[2022]
    assert y.cost_gbp == pytest.approx(y.cost_all_categories - y.category_cost("Increasing system inertia")
                                       - y.category_cost("Reducing largest loss"))
    o = sc.constraint_per_household(2022)
    assert o["inertia_not_counted_total"].value / 1e6 == pytest.approx(103.8 + 5.5, abs=0.1)


def test_missing_constraint_day_is_recorded():
    """Review N3: NESO's 2025/26 file has no row for 8 Apr 2025; it must be visible."""
    from datetime import date
    y = sc.read_constraint_breakdown()
    assert y[2025].missing_dates == (date(2025, 4, 8),)
    assert y[2024].missing_dates == () and y[2017].missing_dates == ()
    assert "2025-04-08" in sc.constraint_per_household(2025)["actual_total"].note


def test_constraints_reconcile_with_daily_balancing_costs():
    """Two NESO datasets, same quantity: agree to 0.2% in every complete year."""
    a = sc.read_constraint_breakdown()
    b = sc.read_daily_balancing_constraints()
    for fy, cy in a.items():
        if cy.complete:
            assert cy.cost_all_categories == pytest.approx(b[fy], rel=2e-3), fy


def test_annual_report_constraints_are_wider_category():
    """NESO's Annual Balancing Costs report 'Constraints' includes more than the breakdown."""
    a = sc.read_constraint_breakdown()
    abc = sc.read_abc_constraints()
    assert abc[2024] / 1e6 == pytest.approx(1914.6, abs=0.1)
    for fy, v in abc.items():
        assert v >= a[fy].cost_all_categories


def test_all_gas_volume_basis():
    """Review B1: all-gas = 2017/18 volume x this year's £/MWh, category by category."""
    y = sc.read_constraint_breakdown()
    total, d = sc.constraint_all_gas_volume(2022)
    th = d["Thermal constraints"]
    assert th["price_gbp_mwh"] == pytest.approx(1503.5e6 / 5.156e6, rel=2e-3)     # ~£291.6/MWh
    assert th["all_gas_gbp"] == pytest.approx(3_707_484 * th["price_gbp_mwh"])
    assert total == pytest.approx(sum(x["all_gas_gbp"] for x in d.values()))
    # baseline year: all-gas equals actual, by construction
    t17, _ = sc.constraint_all_gas_volume(2017)
    assert t17 == pytest.approx(y[2017].cost_gbp)
    # the crisis price moves the baseline with it: 2022/23 all-gas is ~3.5x 2017/18, whereas the
    # GDP deflator allows only ~1.17x
    assert total / y[2017].cost_gbp > 3


def test_volume_basis_is_the_smaller_renewables_line():
    """Richard's conservative rule: the central (volume) 4(b) line is never above the
    real-terms alternative, and in the crisis years it is far below it (review B1 table)."""
    for fy in range(2018, 2026):
        o = sc.constraint_per_household(fy)
        assert o["difference_per_2500kwh"].value <= o["difference_real_terms_per_2500kwh"].value + 1e-9, fy
    o = sc.constraint_per_household(2021)
    assert o["difference_per_2500kwh"].value < 0.2 * o["difference_real_terms_per_2500kwh"].value


def test_constraint_baseline_alternative_real_terms():
    y = sc.read_constraint_breakdown()
    earliest = min(fy for fy, c in y.items() if c.complete)
    assert earliest == sc.BASELINE_FY == 2017
    idx = sc.read_deflator()[0]
    for py in (2017, 2025):
        b = sc.constraint_baseline(py)
        assert b.value == pytest.approx(y[2017].cost_gbp * idx[py] / sc.fy_index(2017, idx), rel=1e-12)
        assert b.basis == "estimated" and "cautious" not in b.note and "alternative" in b.note
    assert sc.constraint_baseline(2025).value > y[2017].cost_gbp


def test_bsuos_demand_share_sourced():
    """Review S1: CMP201 report para 2.1 '50:50'; CMP308 demand-only from 1 April 2023."""
    import re
    import pymupdf
    t = re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(sc.CMP201)))
    assert sc.CMP201_QUOTE in t
    assert sc.bsuos_demand_share(2022).value == 0.5
    assert sc.bsuos_demand_share(2023).value == 1.0


def test_constraint_actual_not_above_receipt_bsuos():
    """Review S1: the 4(b) actual constraint line never exceeds the bill's BSUoS line for the
    matching cap period (2,500 kWh), in every period with a constraint line."""
    from gascf import receipt_actual as ra
    n = 0
    for r in ra.receipts():
        fy = r.period[0] if r.period[1] >= 4 else r.period[0] - 1
        py = r.period[0] if r.period[1] <= 6 or r.period[3] >= r.period[1] else r.period[0]
        try:
            o = sc.constraint_per_household(fy, price_year=py)
        except (KeyError, ValueError):
            continue
        bsuos = ra.at_consumption(r.period, 2500).line("bsuos").typical
        assert o["actual_per_2500kwh"].value <= bsuos, r.label
        n += 1
    assert n >= 25


def test_constraint_per_household_identities():
    o = sc.constraint_per_household(2024, price_year=2025)
    fc = 0.75 * sc.gb_final_consumption_gwh(2024).value + 0.25 * sc.gb_final_consumption_gwh(2025).value
    hh, _ = sc.gb_households_fy(2024)
    d = 0.75 * sc.domestic_share_cy()[2024] + 0.25 * sc.domestic_share_cy()[2025]
    tot = o["actual_total"].value
    assert o["actual_per_2500kwh"].value == pytest.approx(tot / (fc * 1e3) * 2.5)
    assert o["actual_per_avg_household"].value == pytest.approx(tot * d / hh)
    for k in ("per_2500kwh", "per_avg_household"):
        assert o[f"difference_{k}"].value == pytest.approx(o[f"actual_{k}"].value - o[f"all_gas_{k}"].value)
        assert o[f"difference_real_terms_{k}"].value == pytest.approx(
            o[f"actual_{k}"].value - o[f"all_gas_real_terms_{k}"].value)
    assert o["difference_per_2500kwh"].value > 0
    # pre-CMP308: only the demand half
    p = sc.constraint_per_household(2022)
    fc22 = 0.75 * sc.gb_final_consumption_gwh(2022).value + 0.25 * sc.gb_final_consumption_gwh(2023).value
    assert p["actual_per_2500kwh"].value == pytest.approx(0.5 * p["actual_total"].value / (fc22 * 1e3) * 2.5)
    # in the baseline year itself the difference is zero on both bases
    z = sc.constraint_per_household(2017)
    assert z["difference_per_2500kwh"].value == pytest.approx(0, abs=1e-9)
    assert z["difference_real_terms_per_2500kwh"].value == pytest.approx(0, abs=1e-9)
    # nominal means the financial year's own £
    assert z["actual_total"].value == pytest.approx(sc.read_constraint_breakdown()[2017].cost_gbp)


def test_constraint_regression_values():
    """Before/after record (work/s9-fix-wave1/notes.md): 4(b) difference, nominal, per 2,500 kWh."""
    want = {2021: 0.32, 2022: 2.03, 2024: 12.09, 2025: 14.65}
    for fy, v in want.items():
        assert sc.constraint_per_household(fy)["difference_per_2500kwh"].value == pytest.approx(v, abs=0.01), fy


def test_incomplete_year_refused():
    with pytest.raises(ValueError, match="incomplete"):
        sc.constraint_per_household(2026)


def test_dukes_spot_values():
    d = sc.read_dukes_final_and_domestic()
    assert d[2024] == pytest.approx((270962.0891, 93721.5123))
    assert d[2017] == pytest.approx((299611.7446, 105061.4874))


def test_gb_demand_excludes_northern_ireland():
    """Review S5: GB = DUKES UK final x subnational GB / (GB + NI), Table 7.1 (GWh)."""
    sh = sc.read_subnational_gb_share()
    assert sh[2024] == pytest.approx(249_248 / 256_430)
    assert sh[2017] == pytest.approx(279_646 / 287_433)
    g = sc.gb_final_consumption_gwh(2024)
    assert g.value == pytest.approx(270962.0891 * 249_248 / 256_430)
    assert sc.gb_final_consumption_gwh(2025).basis == "estimated"    # 2025 subnational not yet out


def test_one_domestic_share():
    """Review S3: one definition. DUKES 2026 T5.2 Domestic PDS 2025 = 92,812.3256 GWh;
    T5.5.D UK sales 2025 = 253,961.5553 GWh."""
    d = sc.domestic_share_cy()
    assert d[2025] == pytest.approx(92812.3256 / 253961.5553)
    from gascf import goods
    assert goods.domestic_share_cy is sc.domestic_share_cy


def test_fy_weight():
    assert sc.fy_weight({2024: 1.0, 2025: 2.0}, 2024) == (1.25, "modelled")
    assert sc.fy_weight({2024: 1.0}, 2024) == (1.0, "estimated")
    with pytest.raises(KeyError):
        sc.fy_weight({2024: 1.0}, 2023)


# ----------------------------------------------------------------- households

def test_gb_households_sum_and_tags():
    total, parts = sc.gb_households(2024)
    assert total == sum(p.value for p in parts.values())
    assert total == pytest.approx(27_867_000)
    assert all(p.basis == "measured" for p in parts.values())
    with pytest.raises(KeyError, match="UNSOURCED"):
        sc.gb_households(2030)


def test_gb_households_fy():
    a, _ = sc.gb_households(2023)
    b, _ = sc.gb_households(2024)
    v, basis = sc.gb_households_fy(2023)
    assert v == pytest.approx(0.75 * a + 0.25 * b)
    assert basis == "modelled"


def test_gb_share_of_uk():
    v, b = sc.gb_share_of_uk(2020)
    assert 0.97 < v < 0.98 and b == "modelled"
    assert sc.gb_share_of_uk(2003)[1] == "estimated" and sc.gb_share_of_uk(2025)[1] == "estimated"


# ----------------------------------------------------------------- OFTO

def test_tnuos_spot_values_2026():
    t = sc.read_tnuos_year(2026)
    assert t.total_revenue == pytest.approx(7610.0508609, abs=1e-6)
    assert t.demand_revenue == pytest.approx(6378.3788254, abs=1e-6)
    assert t.offshore_local == pytest.approx(869.1210323, abs=1e-6)
    assert t.ofto_revenue == pytest.approx(1135.5361889, abs=1e-6)
    assert t.domestic_proportion == pytest.approx(0.387644003, abs=1e-9)
    assert t.domestic_sites == pytest.approx(29_896_095.15, abs=0.01)


def test_ofto_pass_through_equals_sum_of_ofto_rows():
    """Table 33 total row = sum of the individual OFTO rows (2026/27 column)."""
    import openpyxl
    wb = openpyxl.load_workbook(sc._tnuos_path(2026), read_only=True, data_only=True)
    rows = list(wb["T33"].iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r[0] == "Regulatory Year")
    col = list(rows[hi]).index("2026/27")
    body = []
    for r in rows[hi + 1:]:
        if r[0] and str(r[0]).startswith("Offshore Transmission Pass-Through"):
            break
        if r[0] and isinstance(r[col], (int, float)):
            body.append(r[col])
    assert sum(body) == pytest.approx(sc.read_tnuos_year(2026).ofto_revenue, rel=1e-6)


def test_ofto_demand_share():
    o = sc.ofto_demand_share(2026)
    t = sc.read_tnuos_year(2026)
    frac = t.demand_revenue / (t.total_revenue - t.offshore_local - t.onshore_local)
    expect = (t.ofto_revenue - t.offshore_local) * frac * t.domestic_proportion * 1e6 / t.domestic_sites
    assert o["per_household"].value == pytest.approx(expect)
    assert o["per_household"].value == pytest.approx(3.31, abs=0.01)
    assert o["per_household"].basis == "estimated"
    assert o["per_household"].value < o["per_household_upper"].value
    # upper bound cannot exceed all OFTO revenue at the domestic proportion
    assert o["per_household_upper"].value <= t.ofto_revenue * t.domestic_proportion * 1e6 / t.domestic_sites


def test_ofto_years_without_domestic_band_raise():
    with pytest.raises(KeyError, match="UNSOURCED"):
        sc.ofto_demand_share(2022)
    with pytest.raises(KeyError, match="UNSOURCED"):
        sc.ofto_demand_share(2019)



# ----------------------------------------------------------------- trailing 12 months (s11)

from datetime import date


@pytest.mark.parametrize("fy", [2017, 2018, 2021, 2022, 2024, 2025])
def test_window_agrees_with_financial_year(fy):
    """A window of exactly one financial year computed by the window route equals the FY route."""
    a = sc.constraint_per_household(fy, price_year=2026)
    b = sc.constraint_per_household_window(date(fy, 4, 1), date(fy + 1, 3, 31), price_year=2026)
    for k in ("actual_total", "all_gas_total", "all_gas_real_terms_total", "difference_per_2500kwh",
              "difference_per_avg_household", "difference_real_terms_per_2500kwh"):
        assert b[k].value == pytest.approx(a[k].value, rel=1e-12), k
    assert b["difference_per_2500kwh"].basis == a["difference_per_2500kwh"].basis


def test_month_weights():
    assert sc.month_weights(date(2025, 4, 1), date(2026, 3, 31)) == pytest.approx({2025: 0.75, 2026: 0.25})
    w = sc.month_weights(date(2025, 10, 7), date(2026, 10, 6))
    assert sum(w.values()) == pytest.approx(1.0)
    assert w[2026] == pytest.approx((9 + 6 / 31) / 12)


def test_window_daily_sums_match_fy_reader():
    """The day-level reader sums to the FY reader for every stored year (same files)."""
    y = sc.read_constraint_breakdown()
    for fy, cy in y.items():
        end = date(fy + 1, 3, 31) if cy.complete else sc.latest_constraint_day()
        w = sc.constraint_window(date(fy, 4, 1), end)
        assert w.cost_gbp == pytest.approx(cy.cost_gbp, rel=1e-12), fy
        assert w.volume_mwh["Thermal constraints"] == pytest.approx(cy.volume_mwh["Thermal constraints"], rel=1e-12)


def test_current_year_uses_trailing_12_months():
    """FY 2026/27 is incomplete (to 6 Oct 2026): the current-year route takes the trailing 12
    months to the latest stored NESO day; a complete year still goes the FY route."""
    assert sc.latest_constraint_day() == date(2026, 10, 6)
    assert sc.trailing_year() == (date(2025, 10, 7), date(2026, 10, 6))
    with pytest.raises(ValueError):
        sc.constraint_per_household(2026)
    c = sc.constraint_per_household_current(2026, price_year=2026)
    assert "2025-10-07 to 2026-10-06" in c["window"].note
    assert "2026-10-03" in c["window"].note          # the one day NESO's file lacks
    assert c["difference_per_2500kwh"].basis in ("modelled", "estimated")
    # NESO thermal + voltage over the window, summed from the stored daily files (nominal £):
    # thermal £2,518.8m + voltage £233.3m (cross-checked by a separate csv sum when written)
    raw = sc.constraint_window(date(2025, 10, 7), date(2026, 10, 6))
    assert raw.cost_gbp / 1e6 == pytest.approx(2752.03, abs=0.01)
    assert raw.category_cost("Thermal constraints") / 1e6 == pytest.approx(2518.77, abs=0.01)
    assert raw.days == 364
    assert c["actual_total"].value > c["all_gas_total"].value > 0
    full = sc.constraint_per_household_current(2025, price_year=2026)
    assert "window" not in full
    assert full["difference_per_2500kwh"].value == pytest.approx(
        sc.constraint_per_household(2025, price_year=2026)["difference_per_2500kwh"].value)
    with pytest.raises(KeyError):
        sc.constraint_per_household_current(2027)


def test_window_must_be_twelve_months():
    with pytest.raises(ValueError):
        sc.constraint_per_household_window(date(2026, 4, 1), date(2026, 10, 6))
