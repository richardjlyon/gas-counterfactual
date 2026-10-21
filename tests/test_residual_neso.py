"""Tests for the 2002-2025 demand-side residual (spec v4 §4.1), strand s20a.

Spot values are read from the stored files and checked against the figure as printed in
the source (cell references in work/s20a-residual/sources.md).
"""
import pytest

from gascf import residual_neso as rn


# --------------------------------------------------------------------------- spot values

def test_dukes_56_spot_values():
    d = rn.dukes_56()
    assert d["nuclear_supplied"][2002] == pytest.approx(81090.0)       # 5.6.E, All cos, Nuclear
    assert d["nuclear_supplied"][2016] == pytest.approx(65149.08)
    assert d["storage_generated"][2002] == pytest.approx(2652.0)       # 5.6.B, Energy storage
    assert d["storage_generated"][2008] == pytest.approx(4088.94)


def test_energy_trends_spot_values():
    e = rn.energy_trends_51()
    assert e["nuclear_supplied"][(2002, 1)] == pytest.approx(22.6613)  # 5.1c Q1 2002
    assert e["ps_generated"][(2016, 4)] == pytest.approx(0.8152)       # 5.1b Q4 2016
    assert rn.energy_trends_54_nuclear()[(2002, 1)] == pytest.approx(7.0962)  # 5.4 Jan 2002


def test_dukes_57_pumped_hydro_capacity():
    c = rn.dukes_57_pumped_hydro()
    assert c[2002] == pytest.approx(2788.0)
    assert c[2025] == pytest.approx(2744.0)


def test_neso_rows_read_and_signed_flows_split():
    first = rn.read_neso(2002)[0]
    assert (first.nd, first.pumping, first.imports, first.exports) == (39544.0, 1406.0, 1059.0, 0)
    assert first.embedded_missing                                    # NA in 2002: tagged
    r25 = rn.read_neso(2025)[0]
    assert r25.exports == pytest.approx(3720.0)                     # negative flows → exports
    assert r25.embedded_wind == pytest.approx(5405.0)
    for y in rn.YEARS:
        n = len(rn.read_neso(y))
        assert n in (17520, 17568), (y, n)                           # 365 or 366 days × 48


def test_bst_station_load():
    from datetime import date
    assert rn._is_bst(date(2019, 7, 1)) and not rn._is_bst(date(2019, 1, 1))
    assert rn._is_bst(date(2019, 3, 31)) and not rn._is_bst(date(2019, 3, 30))
    assert not rn._is_bst(date(2019, 10, 27))


# --------------------------------------------------------------------------- identities

@pytest.mark.parametrize("year", [2002, 2009, 2016, 2025])
def test_annual_totals_conserved(year):
    """Nuclear and pumped storage spread over the year sum back to the DESNZ annual figure."""
    rows = rn.residual_neso_year(year)
    assert sum(r.nuclear for r in rows) / 2e3 == pytest.approx(rn.dukes_56()["nuclear_supplied"][year])
    assert sum(r.ps_gen for r in rows) / 2e3 == pytest.approx(rn.pumped_storage_gwh(year)[0])
    cap = rn.dukes_57_pumped_hydro()[year]
    assert max(r.ps_gen for r in rows) <= cap + 1e-6


@pytest.mark.parametrize("year", [2002, 2016, 2025])
def test_half_hour_balance(year):
    """residual + kept output = V + station load, every half-hour (the defining identity)."""
    neso = rn.read_neso(year)
    for r, n in zip(rn.residual_neso_year(year), neso):
        v = n.nd + n.embedded_wind + n.embedded_solar
        assert r.residual + r.kept == pytest.approx(v + r.station_load)
        assert r.residual == pytest.approx(
            n.nd + r.station_load + n.pumping + n.exports + n.embedded_wind
            + n.embedded_solar - n.imports - r.nuclear - r.ps_gen)


def test_volume_and_basis():
    v = rn.volume_annual()
    assert set(v) == set(rn.YEARS)
    assert v[2008]["basis"] == "estimated" and v[2009]["basis"] == "measured"
    nd = sum(r.nd + r.embedded_wind + r.embedded_solar for r in rn.read_neso(2019)) / 2e6
    assert v[2019]["twh"] == pytest.approx(nd)
    assert sum(rn.volume_monthly(2019).values()) == pytest.approx(nd)
    a = rn.residual_annual()
    for y in rn.YEARS:
        assert a[y]["basis"] in ("modelled", "estimated") and a[y]["source_id"]
        assert 150 < a[y]["twh"] < 320 and 35e3 < a[y]["peak_mw"] < 60e3


def test_ps_rules_all_conserve_energy():
    for rule in rn.PS_RULES:
        rows = rn.residual_neso_year(2012, True, rule)
        assert sum(r.ps_gen for r in rows) / 2e3 == pytest.approx(rn.pumped_storage_gwh(2012)[0])
    with pytest.raises(ValueError):
        rn.residual_neso_year(2012, True, "no_such_rule")


# --------------------------------------------------------------------------- calibration

def test_calibration_energy_within_2pct_every_year():
    for c in rn.calibration_table():
        assert c["pass_energy"], c


def test_calibration_result_is_reported_honestly():
    """Under §4.1 as first written ('strict') the method passes 8 of 10 years: 2016
    (load-duration curve at its minimum +6.9%) and 2024 (peak -3.9%, minimum -7.0%) fail.
    Under Richard's §15.2 decision 2 ('loosened', the default: peak 4%, curve 1st-99th
    percentile) all ten pass, so the pre-2016 years are publishable."""
    strict = rn.calibration_table(rule="strict")
    assert sorted(c["year"] for c in strict if not c["pass"]) == [2016, 2024]
    assert not rn.calibration_passes(rule="strict")
    loose = rn.calibration_table()
    assert [c["year"] for c in loose if not c["pass"]] == []
    assert all(c["pass_loosened"] for c in strict) and all(c["rule"] == "loosened" for c in loose)
    assert rn.calibration_passes()
    assert rn.residual_published(2010)["publishable"] is True
    assert rn.residual_published(2020)["publishable"] is True
    # Inside the curve (1st-99th percentile) every year is within 5%; the peak within 4%.
    assert max(c["ldc_worst_err_p1_p99"] for c in loose) < 0.05
    assert max(abs(c["peak_err"]) for c in loose) < 0.04


def test_unknown_calibration_rule_raises():
    with pytest.raises(ValueError):
        rn.calibrate(2020, rule="lenient")


def test_spec_rule_as_written_fails():
    """Spec §4.1's 'highest-residual half-hours' pumped-storage rule misses the peak."""
    c = rn.calibrate(2019, True, "annual_peak")
    assert not c["pass_peak"] and c["peak_err"] < -0.03
