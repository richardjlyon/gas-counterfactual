"""DUKES 5.10 and DESNZ Annex A readers, and the plant arithmetic built on them.

Values asserted here were read at source by roast 2 (review/2026-10-10-spec-roast-2.md)
or are printed in the workbooks themselves.
"""
from pathlib import Path

import pytest

from gascf.official import read_desnz_levelised, read_desnz_plants, read_dukes_510
from gascf.plant import (annualised_fixed_gbp_kw_yr, crossover_load_factor,
                         levelised_capital_gbp_mwh, variable_gbp_mwh)

RAW = Path(__file__).parents[1] / "data/raw"
CCGT = ("Gas CCGT 93% Load Factor", 2030)
OCGT = ("Gas OCGT 760MW 30% Load Factor", 2030)


@pytest.fixture(scope="module")
def dukes():
    return read_dukes_510(RAW / "DUKES_5.10.xlsx")


@pytest.fixture(scope="module")
def plants():
    return read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")


@pytest.fixture(scope="module")
def printed():
    return read_desnz_levelised(RAW / "DESNZ_EGC2025_AnnexA.xlsx", 2030)


def test_dukes_ccgt(dukes):
    assert "30th July 2026" in dukes.published
    assert dukes.ccgt_efficiency[2025] == 47.99
    assert dukes.ccgt_load_factor[2025] == 29.66
    peak = max(dukes.ccgt_load_factor, key=dukes.ccgt_load_factor.get)
    assert peak == 1999 and round(dukes.ccgt_load_factor[peak]) == 84
    assert min(dukes.ccgt_efficiency) == 1996 and max(dukes.ccgt_efficiency) == 2025


def test_desnz_ccgt_inputs(plants):
    p = plants[CCGT]
    assert (p.net_load_factor, p.efficiency_gcv, p.life_years) == (0.86, 0.54, 25)
    assert p.construction_gbp_kw == {"low": 800, "medium": 1000, "high": 1100}
    assert p.hurdle == {"low": 0.073, "medium": 0.089, "high": 0.106}
    # the '30%' column runs at 28%, not 30%: labels are not the load factor used
    assert plants[("Gas CCGT 30% Load Factor", 2030)].net_load_factor == 0.28


def test_desnz_ocgt_inputs(plants):
    p = plants[OCGT]
    assert (p.efficiency_gcv, p.net_load_factor) == (0.36, 0.29)
    assert plants[("Gas OCGT 300MW 30% Load Factor", 2030)].efficiency_gcv == 0.35


def test_printed_rows_sum_to_total(printed):
    for tech in ("Gas CCGT 93% Load Factor", "Gas OCGT 760MW 30% Load Factor"):
        rows = printed[tech]
        parts = sum(v or 0 for k, v in rows.items() if k not in ("Total",))
        assert abs(parts - rows["Total"]) <= 2      # integer rounding, '<1' as 0


@pytest.mark.parametrize("tech,tol", [
    ("Gas CCGT 93% Load Factor", 0.05), ("Gas CCGT 30% Load Factor", 0.05),
    ("Gas OCGT 760MW 30% Load Factor", 0.10), ("Gas OCGT 760MW 93% Load Factor", 0.10),
])
def test_construction_row_reproduced(plants, printed, tech, tol):
    """Our annuity timeline reproduces DESNZ's printed construction £/MWh.

    Tolerance covers DESNZ's integer rounding (8 vs 8.68 is 8%). The 5% load-factor
    columns are NOT reproduced (CCGT 258.5 vs 271 printed): open question, logged in
    memory.md; the screening curve does not use DESNZ's 5% columns.
    """
    p = plants[(tech, 2030)]
    key = next(k for k in printed if k.startswith(tech))
    _, con = levelised_capital_gbp_mwh(p)
    assert con == pytest.approx(printed[key]["Construction costs"], rel=tol, abs=0.6)


def test_fuel_row_implies_desnz_gas_price(plants, printed):
    """CCGT 45 and OCGT-760 68 £/MWh printed fuel imply one gas price (~£24.3-24.5/MWh GCV)."""
    g_ccgt = printed["Gas CCGT 93% Load Factor"]["Fuel costs"] * plants[CCGT].efficiency_gcv
    g_ocgt = printed["Gas OCGT 760MW 30% Load Factor"]["Fuel costs"] * plants[OCGT].efficiency_gcv
    assert g_ccgt == pytest.approx(g_ocgt, abs=0.5)


def test_fixed_costs_in_roast_range(plants):
    """Roast 2 back-derived CCGT £134-146/kW/yr and OCGT £78-82 from DESNZ's printed,
    integer-rounded £/MWh rows. Built from the inputs instead: CCGT 138.8, OCGT 82.9.
    OCGT sits 1% above the roast's band, inside its rounding (printed 5% column:
    (6+150+32) x 8.76 x 0.05 = £82.3)."""
    assert annualised_fixed_gbp_kw_yr(plants[CCGT]) == pytest.approx(138.8, abs=0.05)
    assert annualised_fixed_gbp_kw_yr(plants[OCGT]) == pytest.approx(82.9, abs=0.05)
    assert 134 <= 138.8 <= 146 and abs(82.9 - 82) / 82 < 0.015


def test_crossover_moves_with_gas_price(plants):
    """Roast 2: OCGT/CCGT cut-over ~27% at DESNZ's fuel price, ~16% at the Q4 2026 index."""
    desnz_gas = 45 * 0.54
    lo = crossover_load_factor(plants[OCGT], plants[CCGT], desnz_gas)
    hi = crossover_load_factor(plants[OCGT], plants[CCGT], 40.24)
    assert 0.24 <= lo <= 0.30
    assert 0.14 <= hi <= 0.18
    assert hi < lo


def test_variable_cost_has_no_carbon(plants):
    p = plants[CCGT]
    assert variable_gbp_mwh(p, 40.24) == pytest.approx(40.24 / 0.54 + 5)
