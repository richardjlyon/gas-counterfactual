"""Fleet B screening-curve costing."""
from pathlib import Path

import pytest

from gascf.fleetb import cost_fleet_b
from gascf.official import read_desnz_plants
from gascf.plant import annualised_fixed_gbp_kw_yr, crossover_load_factor, variable_gbp_mwh
from gascf.residual import load_duration, residual_year

RAW = Path(__file__).parents[1] / "data/raw"
GAS = 40.24   # Ofgem gas index, Oct-Dec 2026 cap, £/MWh


@pytest.fixture(scope="module")
def plants():
    p = read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")
    return p[("Gas CCGT 93% Load Factor", 2030)], p[("Gas OCGT 760MW 30% Load Factor", 2030)]


def test_flat_load_is_all_ccgt(plants):
    ccgt, ocgt = plants
    f = cost_fleet_b([10_000.0] * 17520, GAS, ccgt, ocgt, reserve_margin=0)
    assert f.ocgt_gw == 0 and f.ccgt_gw == pytest.approx(10)
    assert f.energy_twh == pytest.approx(87.6)
    exact = annualised_fixed_gbp_kw_yr(ccgt) / 8.76 + variable_gbp_mwh(ccgt, GAS)
    assert f.gbp_per_mwh == pytest.approx(exact)


def test_two_step_load_splits_at_crossover(plants):
    """1 GW all year + 1 GW for 10% of the year: the top GW runs below the ~17% crossover,
    so it is OCGT; the base GW is CCGT. Energy and cost add exactly."""
    ccgt, ocgt = plants
    assert crossover_load_factor(ocgt, ccgt, GAS) > 0.10
    ldc = [2000.0] * 1752 + [1000.0] * (17520 - 1752)
    f = cost_fleet_b(ldc, GAS, ccgt, ocgt, reserve_margin=0, step_mw=1000)
    assert (f.ccgt_gw, f.ocgt_gw) == (pytest.approx(1), pytest.approx(1))
    assert f.energy_twh == pytest.approx(8.76 + 0.876)
    want = (annualised_fixed_gbp_kw_yr(ccgt) + annualised_fixed_gbp_kw_yr(ocgt)) * 1e6 \
        + variable_gbp_mwh(ccgt, GAS) * 8.76e6 + variable_gbp_mwh(ocgt, GAS) * 0.876e6
    assert f.total_gbp_m == pytest.approx(want / 1e6)


def test_reserve_is_fixed_cost_only(plants):
    ccgt, ocgt = plants
    a = cost_fleet_b([10_000.0] * 17520, GAS, ccgt, ocgt, reserve_margin=0)
    b = cost_fleet_b([10_000.0] * 17520, GAS, ccgt, ocgt, reserve_margin=0.1)
    assert b.energy_twh == a.energy_twh and b.variable_gbp_m == a.variable_gbp_m
    assert b.fixed_gbp_m - a.fixed_gbp_m == pytest.approx(annualised_fixed_gbp_kw_yr(ocgt) * 1e6 / 1e6)


def test_energy_matches_residual_2025(plants):
    ccgt, ocgt = plants
    rows, _ = residual_year(2025)
    f = cost_fleet_b(load_duration(rows), GAS, ccgt, ocgt, reserve_margin=0)
    assert f.energy_twh == pytest.approx(sum(r.residual for r in rows) / 2e6, rel=0.002)
    assert f.ccgt_gw + f.ocgt_gw == pytest.approx(45.18, abs=0.01)
