"""The 'today' panel (spec §5, P3)."""
from datetime import date

import pytest

from gascf import today as td
from gascf.today import day_ahead, fleet_a_running, periods_in_day


def test_spec_spot_value_8_oct_2026():
    """Spec §12: SAP 6.417 p/kWh at eta 0.4799 -> 133.71 + 4.44 + 1 = £139.15/MWh.
    Exact values are 133.7154 and 139.1554: the spec truncates to 2 dp (rounding gives
    133.72 and 139.16). Agreement is checked to the penny on the truncated figures."""
    v = fleet_a_running(64.17, 0.4799, 4.44, 1.0)
    assert v == pytest.approx(139.1554, abs=1e-4)
    assert int(v * 100) / 100 == 139.15
    assert int(64.17 / 0.4799 * 100) / 100 == 133.71


def test_inputs_are_read_from_sources():
    assert td.cepa_vom_existing() == 4.44                      # CEPA/GHD Table 3.5, medium current
    assert td.cepa_vom_existing("low") < 4.44 < td.cepa_vom_existing("high")
    assert td.dukes_eta_latest() == (2025, pytest.approx(0.4799))
    # National Gas 2026/27 exit capacity + GNTS commodity, per MWh of electricity at 0.4799
    assert td.transport_gbp_mwh_e(0.4799) == pytest.approx(1.1857, abs=1e-4)


def test_settlement_periods_per_day():
    assert periods_in_day(date(2026, 10, 8)) == 48
    assert periods_in_day(date(2026, 3, 29)) == 46            # clocks go forward
    assert periods_in_day(date(2026, 10, 25)) == 50           # clocks go back


def test_gas_year():
    assert td.gas_year_of(date(2026, 10, 8)) == "2026/27"
    assert td.gas_year_of(date(2026, 9, 30)) == "2025/26"


def _synthetic(d, n=48, drop=(), zero=()):
    mid = {}
    for sp in range(1, n + 1):
        if sp in drop:
            continue
        mid[(d, sp)] = (100.0 + sp, 0.0 if sp in zero else 10.0 * sp)
    return mid


def test_day_ahead_volume_weighting_by_hand():
    d = date(2026, 1, 15)
    da = day_ahead(d, _synthetic(d))
    num = sum((100 + sp) * 10 * sp for sp in range(1, 49))
    den = sum(10 * sp for sp in range(1, 49))
    assert da.gbp_mwh == pytest.approx(num / den)
    assert da.gbp_mwh != pytest.approx(sum(100 + sp for sp in range(1, 49)) / 48)  # not a simple mean
    assert da.complete and da.n_periods == 48


def test_missing_and_zero_volume_periods_are_flagged():
    d = date(2026, 1, 15)
    da = day_ahead(d, _synthetic(d, drop=(3, 17), zero=(40,)))
    assert da.missing_periods == (3, 17, 40)
    assert not da.complete and da.n_periods == 45
    # other days' data are ignored
    other = _synthetic(date(2026, 1, 16))
    assert day_ahead(d, other).gbp_mwh is None
    assert len(day_ahead(d, other).missing_periods) == 48


def test_clock_change_day_expects_fifty():
    d = date(2026, 10, 25)
    assert day_ahead(d, _synthetic(d, n=48)).missing_periods == (49, 50)


def test_mutation_volume_weight_not_price_weight():
    """Mutation guard: two periods, one cheap with big volume. Weighted = 20; a simple mean = 55."""
    d = date(2026, 1, 15)
    mid = {(d, 1): (10.0, 90.0), (d, 2): (100.0, 10.0)}
    assert day_ahead(d, mid).gbp_mwh == pytest.approx(19.0)


@pytest.fixture(scope="module")
def panel():
    return td.today(date(2026, 10, 8))


def test_panel_8_oct_2026(panel):
    """Stored data: SAP 6.417 p/kWh; APX 48/48 periods 14.419 p/kWh; fleet A 13.934 p/kWh with
    sourced transport (£1.19 not the spec's rounded £1); fleet B 15.890 (15.898 after decision 0133: the margin over
    the 2027/28 peak); fleet A + carbon 16.874
    (UKA Aug 2026 £59.34/t, two months' lag, flagged)."""
    assert panel.sap.p_per_kwh == pytest.approx(6.417)
    assert panel.day_ahead.p_per_kwh == pytest.approx(14.4191, abs=1e-4)
    assert panel.missing_periods == ()
    assert panel.fleet_a.gbp_per_mwh == pytest.approx(139.155 + 0.1857, abs=1e-3)
    assert panel.fleet_b.p_per_kwh == pytest.approx(15.898, abs=1e-3)
    assert panel.fleet_a_with_carbon.p_per_kwh == pytest.approx(16.874, abs=1e-3)
    assert any("carbon" in f and "2026-08" in f for f in panel.flags)
    for fig in (panel.sap, panel.day_ahead, panel.fleet_a, panel.fleet_b, panel.fleet_a_with_carbon):
        assert fig.source_id and fig.basis in {"measured", "modelled", "estimated"}
        assert fig.p_per_kwh == pytest.approx(fig.gbp_per_mwh / 10)


def test_panel_ordering_is_sane(panel):
    assert panel.fleet_a_with_carbon.gbp_per_mwh > panel.fleet_a.gbp_per_mwh
    assert panel.fleet_a.gbp_per_mwh > panel.sap.gbp_per_mwh / 0.4799


def test_unknown_day_is_not_guessed():
    with pytest.raises(KeyError, match="UNSOURCED"):
        td.today(date(2040, 1, 1), fleet_b_fn=lambda g: 0.0, sap={}, mid={})


def test_panel_with_injected_data_flags_missing_periods():
    d = date(2026, 10, 8)
    p = td.today(d, fleet_b_fn=lambda g: 2 * g, sap={d: 50.0}, mid=_synthetic(d, drop=(5,)))
    assert p.missing_periods == (5,)
    assert any("1 of 48" in f for f in p.flags)
    assert p.fleet_b.gbp_per_mwh == 100.0
