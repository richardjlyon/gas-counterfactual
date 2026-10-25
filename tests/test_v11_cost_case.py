"""RB v1.1 O2 (decision 0160, card [internal ticket]): a plant-cost case threaded through `fossil_fleet.edition()` and its
readers, off by default ('medium' = v4-s37), run as two held rows for ruling R13:

- 'high_capital': the editions' high column for the capital rows only (pre-development, construction / EPC,
  infrastructure); hurdle rate, efficiency, life, running costs and durations at the medium (central) values.
- 'high_capital_hurdle': the same, plus the high hurdle rate where an edition prints one. Only DESNZ EGC 2025 Annex A
  prints a high hurdle (10.6% against 8.9% medium); every earlier edition prints one hurdle, so before 2025 the two
  rows are the same by construction. v4-s42 (A4, decision 0195): 2025 is costed on EGC 2023, so EGC 2025 (and its high
  hurdle) applies from 2026, a year the engine does not cost; the two rows are now the same in every costed year.

Expected values are literals from the stored editions: the hand-entered PDF rows in reference/cost_editions.yaml
(each row checked against its PDF by tests/test_fossil_fleet.py) and the stored workbooks (EGC 2016 Table 19, EGC 2020
KeyData, EGC 2023 and 2025 Annex A), read by hand for this test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gascf import bills as B  # noqa: E402
from gascf import fossil_fleet as ff  # noqa: E402

# (year, tech) -> high capital literals: (pre-development £/kW, construction / EPC £/kW, infrastructure £k or None)
HIGH = {
    (2005, "ccgt"): (40.0 + 35.0, 687.5, None),         # MM2010 Table A1 CCGT: prelicensing 40 + regulatory 35, EPC 687.5
    (2005, "coal"): (50.0 + 50.0, 1843.8, None),        # MM2010 Table A3 coal
    (2012, "ccgt"): (13.0 + 2.9, 655.1, 22000.0),       # PB2012 CCGT
    (2014, "ccgt"): (15.0 + 4.0, 648.0, 36000.0),       # PB2013 CCGT
    (2014, "ocgt"): (24.6 + 3.1, 330.0, 11100.0),       # PB2013 OCGT
    (2014, "coal"): (30.0 + 1.6, 1800.0, 15000.0),      # PB2012 ASC coal with FGD
    (2018, "ccgt"): (20.0, 600.0, 30200.0),             # EGC 2016 Table 19 CCGT H Class, 2018, High rows
    (2018, "ocgt"): (20.0, 300.0, 30200.0),             # EGC 2016 Table 19 OCGT 600MW 500 hr, 2018, High rows
    (2021, "ccgt"): (20.0, 700.0, 16100.0),             # EGC 2020 KeyData CCGT H Class 2025: High; infrastructure single
    (2024, "ccgt"): (20.0, 700.0, 34600.0),             # EGC 2023 Annex A CCGT H Class 2025: High rows
    # v4-s42 (A4, decision 0195): 2025 is costed on EGC 2023 Annex A (2025 column), read by hand from the stored
    # workbook (work/[internal ticket] egc_col.py): CCGT H Class and OCGT 600MW 500 hr, High rows. Was EGC 2025 (1100 / 600).
    (2025, "ccgt"): (20.0, 700.0, 34600.0),             # EGC 2023 Annex A CCGT H Class 2025: High rows
    (2025, "ocgt"): (30.0, 300.0, 34600.0),             # EGC 2023 Annex A OCGT 600MW 500 hr 2025: High rows
}
HURDLE_2025 = {"medium": 0.089, "high": 0.106}          # EGC 2025 Annex A Hurdle Rate, Medium / High (applies from 2026)
# v4-s42 (A4, decision 0195): 2025 is costed on EGC 2023, which prints one hurdle (CCGT 7.5%), so no costed year
# (2002-25) now has a printed high hurdle and the two held rows are the same by construction in every year.
HURDLE_SINGLE = {2005: 0.075, 2014: 0.075, 2018: 0.078, 2021: 0.075, 2024: 0.075, 2025: 0.075}


def _cap(p):
    return (p.predev_gbp_kw["medium"], p.construction_gbp_kw["medium"], p.infrastructure_gbp_k["medium"])


def test_medium_case_is_v4_s37s_edition_exactly():
    for y in (2005, 2012, 2014, 2018, 2021, 2024, 2025):
        assert ff.edition(y, "medium") == ff.edition(y), y


def test_high_capital_takes_the_high_column_for_capital_rows_only():
    for (y, tech), (pre, con, infra) in HIGH.items():
        hi, med = getattr(ff.edition(y, "high_capital"), tech), getattr(ff.edition(y), tech)
        assert hi.predev_gbp_kw["medium"] == pytest.approx(pre, abs=1e-9), (y, tech)
        assert hi.construction_gbp_kw["medium"] == pytest.approx(con, abs=1e-9), (y, tech)
        if infra is not None:
            assert hi.infrastructure_gbp_k["medium"] == pytest.approx(infra, abs=1e-9), (y, tech)
        # nothing else moves: efficiency, life, running costs, durations, hurdle
        for f in ("efficiency_gcv", "life_years", "fixed_om_gbp_mw_yr", "variable_om_gbp_mwh", "insurance_gbp_mw_yr",
                  "connection_uos_gbp_mw_yr", "predev_phasing", "construction_phasing", "size_mw"):
            assert getattr(hi, f) == getattr(med, f), (y, tech, f)
        assert hi.hurdle["medium"] == med.hurdle["medium"], (y, tech)


def test_hurdle_high_only_where_an_edition_prints_one():
    # v4-s42 (A4): the EGC 2025 high hurdle (HURDLE_2025) no longer reaches a costed year; 2025 is in HURDLE_SINGLE
    for y, h in HURDLE_SINGLE.items():
        assert ff.edition(y, "high_capital_hurdle").ccgt.hurdle["medium"] == pytest.approx(h), y
        from dataclasses import replace
        assert replace(ff.edition(y, "high_capital_hurdle"), cost_case="high_capital") == ff.edition(y, "high_capital"), y


def test_unknown_case_refused():
    with pytest.raises(ValueError):
        ff.edition(2018, "low")


def test_filters_on_kept_coal_take_the_case():
    """FGD (20% of MM2010 coal EPC: medium 1687.5, high 1843.8) and the NOx retrofit (PB2012 SCR EPC 56.5 / 143.6;
    LF2016 125 / 185) are capital: the high case raises the annualised filter cost."""
    for y in (2014, 2018):
        med, hi = ff.edition(y), ff.edition(y, "high_capital")
        assert ff.fgd_retrofit(hi)[0].construction_gbp_kw["medium"] == pytest.approx(1843.8 * 0.20)
        assert ff.fgd_retrofit(med)[0].construction_gbp_kw["medium"] == pytest.approx(1687.5 * 0.20)
        assert ff.abatement_gbp_kw_yr(hi, "FGD+SCR")[0] > ff.abatement_gbp_kw_yr(med, "FGD+SCR")[0]
        assert ff.keep_open_gbp_kw_yr(hi, "coal") == ff.keep_open_gbp_kw_yr(med, "coal")     # running costs only
    assert ff.scr_retrofit(ff.edition(2014, "high_capital"))[0].construction_gbp_kw["medium"] == pytest.approx(143.6)
    assert ff.scr_retrofit(ff.edition(2018, "high_capital"))[0].construction_gbp_kw["medium"] == pytest.approx(185.0)


def test_settings_default_medium_and_two_held_rows():
    assert B.CENTRAL.cost_case == "medium"
    assert [s.cost_case for s in B.HELD_SWITCHES[B.HELD_O2_CAP_HURDLE]] == ["high_capital_hurdle"]
    assert [s.cost_case for s in B.HELD_SWITCHES[B.HELD_O2_CAP]] == ["high_capital"]
    for reg in (B.switch_settings(), B.METHOD_SWITCHES):
        assert all(s.cost_case == "medium" for sets in reg.values() for s in sets)
    assert B._lfl_args(B.replace(B.CENTRAL, cost_case="high_capital"), 2018)[-1] == "high_capital"


def test_all_new_fleet_refuses_a_cost_case_it_does_not_carry():
    with pytest.raises(NotImplementedError):
        B.build(B.replace(B.CENTRAL, fleet="all_new", cost_case="high_capital"))


def test_cost_case_reaches_the_like_for_like_year():
    """2018 (about 1 min): the high capital case raises the fixed cost of the firm spare plant (OCGT) by the ratio of
    the edition's own annualised OCGT fixed cost, and leaves every energy quantity alone."""
    from gascf import fossil_like_for_like as L
    med = L.lfl_year(2018, "neso", "central", True, "legitimate", "cheapest", str(L.closures_path()), "dukes_max",
                     "contracted")
    hi = L.lfl_year(2018, "neso", "central", True, "legitimate", "cheapest", str(L.closures_path()), "dukes_max",
                    "contracted", cost_case="high_capital")
    assert hi.firm_spare_gw == med.firm_spare_gw and hi.energy_twh == med.energy_twh
    assert hi.extra_twh == med.extra_twh and hi.gas_burn_existing_twh == med.gas_burn_existing_twh
    assert hi.firm_spare_fixed_gbp_m > med.firm_spare_fixed_gbp_m > 0
    assert hi.kept_fixed_gbp_m >= med.kept_fixed_gbp_m
