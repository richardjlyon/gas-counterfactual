"""National Gas transport charges, Oct 2026, and their entry into fleet B."""
from dataclasses import replace
from pathlib import Path

import pytest

from gascf.fleetb import cost_fleet_b
from gascf.gastransport import read_transport
from gascf.official import read_desnz_plants

RAW = Path(__file__).parents[1] / "data/raw"


def test_rates_read_at_source():
    t = read_transport()
    assert t["2026/27"].exit_capacity_p_kwh_day == 0.0356
    assert t["2030/31"].exit_capacity_p_kwh_day == 0.0471
    assert t["2026/27"].commodity_p_kwh == 0.0213
    assert t["2030/31"].commodity_p_kwh == 0.0218


def test_unit_conversion():
    t = read_transport()["2026/27"]
    # 1 kW electric at 54% burns 1/0.54 kW gas = 44.4 kWh/day; x 0.0356p x 365 days
    assert t.fixed_gbp_kw_e_yr(0.54) == pytest.approx(0.0356 / 100 * 24 / 0.54 * 365)
    assert t.fixed_gbp_kw_e_yr(0.54) == pytest.approx(5.776, abs=0.001)
    assert t.commodity_gbp_mwh_gas == pytest.approx(0.213)


def test_transport_raises_fleet_cost_by_the_right_amount():
    p = read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")
    ccgt, ocgt = p[("Gas CCGT 93% Load Factor", 2030)], p[("Gas OCGT 760MW 30% Load Factor", 2030)]
    t = read_transport()["2026/27"]
    flat = [10_000.0] * 17520                      # all CCGT, runs all year
    a = cost_fleet_b(flat, 30, ccgt, ocgt, 0)
    b = cost_fleet_b(flat, 30, ccgt, ocgt, 0, transport=t)
    assert b.ccgt_gw == a.ccgt_gw == pytest.approx(10)
    expect = (t.fixed_gbp_kw_e_yr(ccgt.efficiency_gcv) * 10e6 + t.commodity_gbp_mwh_gas / ccgt.efficiency_gcv * 87.6e6) / 1e6
    assert b.total_gbp_m - a.total_gbp_m == pytest.approx(expect, rel=1e-9)
    zero = replace(t, exit_capacity_p_kwh_day=0, commodity_p_kwh=0)
    assert cost_fleet_b(flat, 30, ccgt, ocgt, 0, transport=zero).total_gbp_m == pytest.approx(a.total_gbp_m)
