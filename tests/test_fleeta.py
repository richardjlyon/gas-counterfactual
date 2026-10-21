"""Fleet A: existing GB gas fleet topped up, priced as a market."""
from pathlib import Path

import pytest

from gascf.fleeta import LF_CAP, _strip_energy, cost_fleet_a, read_existing_gb_gas
from gascf.official import read_desnz_plants

RAW = Path(__file__).parents[1] / "data/raw"
ONE = {"ccgt": 1.0, "ocgt": 1.0}


@pytest.fixture(scope="module")
def plants():
    p = read_desnz_plants(RAW / "DESNZ_EGC2025_AnnexA.xlsx")
    return p[("Gas CCGT 93% Load Factor", 2030)], p[("Gas OCGT 760MW 30% Load Factor", 2030)]


def test_existing_fleet_read_at_source():
    e = read_existing_gb_gas()
    assert e["ccgt"] == 29_747          # DUKES 5.11 end May 2026, GB, natural gas CCGT
    assert e["single_cycle"] == 2_104


def test_strip_energy():
    asc = sorted([100.0, 300.0, 500.0])
    assert _strip_energy(asc, 200, 400) == pytest.approx(0.5 * (100 + 200))


def test_small_existing_fleet_is_capped_and_topped_up(plants):
    ccgt, ocgt = plants
    flat = [10_000.0] * 17520
    f = cost_fleet_a(flat, 30, 0.48, 4.44, 0, {"ccgt": 5_000, "single_cycle": 0}, ccgt, ocgt, 0, ONE)
    assert f.existing_lf <= LF_CAP + 1e-9 and f.existing_lf == pytest.approx(LF_CAP, abs=1e-6)
    assert f.new_baseload_gw + f.existing_ccgt_gw * f.existing_lf == pytest.approx(10, rel=1e-6)


def test_price_is_marginal_running_cost_plus_margin(plants):
    ccgt, ocgt = plants
    flat = [10_000.0] * 17520
    ex = {"ccgt": 20_000, "single_cycle": 0}           # existing covers it, runs < 84%
    f0 = cost_fleet_a(flat, 30, 0.48, 4.44, 0, ex, ccgt, ocgt, 0, ONE)
    f5 = cost_fleet_a(flat, 30, 0.48, 4.44, 5, ex, ccgt, ocgt, 0, ONE)
    assert f0.new_fixed_gbp_m == 0 and f0.new_baseload_gw == 0
    assert f0.gbp_per_mwh == pytest.approx(30 / 0.48 + 4.44)
    assert f5.gbp_per_mwh - f0.gbp_per_mwh == pytest.approx(5)


def test_spare_counts_existing_peakers(plants):
    ccgt, ocgt = plants
    flat = [10_000.0] * 17520
    a = cost_fleet_a(flat, 30, 0.48, 4.44, 0, {"ccgt": 20_000, "single_cycle": 0}, ccgt, ocgt, 0.07, ONE)
    assert a.spare_gw == 0                              # 20 GW existing > 10.7 GW needed
    # 12 GW existing runs at 10/12 = 83% (under the cap, so no new baseload); need 13 GW
    b = cost_fleet_a(flat, 30, 0.48, 4.44, 0, {"ccgt": 12_000, "single_cycle": 500}, ccgt, ocgt, 0.3, ONE)
    assert b.new_baseload_gw == 0
    assert b.spare_gw == pytest.approx(13 - 12 - 0.5, abs=1e-6)
