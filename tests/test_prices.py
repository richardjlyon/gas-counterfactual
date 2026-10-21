"""Strand s20c: wholesale prices 2002–2025 (spec §5.1, §15.1 decision 3, §12.2 items 4, 12)."""
import statistics

import pytest

from gascf import prices as p


def _cy(series, y):
    return statistics.mean(series[(y, m)] for m in range(1, 13))


def test_wmi_spot_values_match_s18a():
    # s18a E1/G2 CY means read from the same files
    assert _cy(p.wmi_elec(), 2013) == pytest.approx(50.80, abs=0.01)
    assert _cy(p.wmi_elec(), 2022) == pytest.approx(211.85, abs=0.01)
    assert _cy(p.wmi_gas_ptherm(), 2022) == pytest.approx(211.50, abs=0.01)


def test_therm_conversion():
    # 100 p/therm = £34.12/MWh; NBP 2022 CY mean ≈ £72.2/MWh (SAP 2022 £71.16 in s18a G3)
    assert p.ptherm_to_gbp_mwh(100) == pytest.approx(34.121, abs=0.001)
    assert _cy({k: p.ptherm_to_gbp_mwh(v) for k, v in p.wmi_gas_ptherm().items()}, 2022) == pytest.approx(72.17, abs=0.05)


def test_ofgem_fig8_vector_read_matches_wmi_on_overlap():
    e = p.overlap_error(p.fig8_elec(), p.wmi_elec())
    assert e["n"] == 60 and e["max_abs"] < 0.1           # Jun 2010 – May 2015
    f8 = p.fig8_elec()
    assert min(f8) == (2003, 1) and max(f8) == (2015, 5)
    assert _cy(f8, 2008) == pytest.approx(74.25, abs=0.05)   # the 2008 spike, Ofgem chart


def test_ofgem_fig5_gas_vector_read_matches_wmi_on_overlap():
    e = p.overlap_error(p.fig5_gas_ptherm(), p.wmi_gas_ptherm())
    assert e["n"] == 68 and e["max_abs"] < 0.1
    assert min(p.fig5_gas_ptherm()) == (2001, 1)            # plotted axis starts at 2001


def test_dukes_efficiency_reads_2004_note_column():
    e = p.dukes_efficiency()
    assert e["ccgt"][2002] == 46.8 and e["coal"][2002] == 36.3
    assert 2004 in e["ccgt"] and 2004 in e["coal"]


def test_calibration_errors_are_printed_and_bounded():
    for f in p.MODEL_FORMS:
        c = p.calibrate(f)
        assert c["n"] == 91                                  # Jun 2010 – Dec 2017
        assert abs(c["mean_error"]) < 1e-6                   # μ / OLS fit is unbiased in-sample
        assert c["rmse"] < 7
    assert p.calibrate("ols_gas_coal")["rmse"] < p.calibrate("gas_only")["rmse"]


def test_model_choice_follows_decision_3():
    f = p.choose_model_form()
    assert f in p.COAL_FORMS                                 # coal may set the price
    rng = p.model_only_range()
    assert rng[f] == min(rng[g] for g in p.COAL_FORMS if p.calibrate(g)["rmse"] <= 5)


def test_joined_series_bases_and_sources():
    m = p.elec_monthly("ofgem_chart")
    assert len(m) == 24 * 12
    assert m[(2002, 6)]["basis"] == "modelled"
    assert m[(2005, 6)]["source_id"] == p.SRC_FIG8
    assert m[(2010, 6)]["source_id"] == p.SRC_WMI_ELEC
    low, chart = p.elec_monthly("lower"), m
    assert all(low[k]["gbp_per_mwh"] <= chart[k]["gbp_per_mwh"] + 1e-9 for k in m)


def test_qep_below_nbp_in_2022_hedging_lag():
    # spec §12.2 item 12: QEP must sit below NBP in 2022, or the reader is wrong
    j = p.qep_vs_nbp_annual()
    assert j[2022]["qep"] < j[2022]["nbp"]
    assert j[2022]["qep"] == pytest.approx(61.92, abs=0.05)


def test_nz1_sums_price_times_volume():
    v = {(2024, m): 20.0 for m in range(1, 13)}             # 20 TWh a month
    out = p.nz1(v)
    assert out[2024]["gbp_m"] == pytest.approx(20 * sum(p.wmi_elec()[(2024, m)] for m in range(1, 13)))
    assert out[2024]["basis"] == "measured"
