"""capacity_cm: extra Capacity Market an all-gas Britain would buy (s11, report only).

Spot values read by eye from the stored files when written: NESO ECR 2026 data workbook
(Figures B4, 24), Ofgem CM annual report 2025/26 (Table 1), DESNZ Auction Monitor report for
the 2022 T-4 (delivery year 2026/27).
"""
import pytest

from gascf import capacity_cm as cm


def test_ecr_spot_values():
    w = cm.read_wind_outside_cm()
    assert w[2025] == 26.7 and w[2026] == 28.9 and w[2027] == 32.7 and w[2030] == 51.0
    efc = cm.read_wind_efc()
    assert efc[2027] == pytest.approx(0.18217, abs=1e-5)
    assert efc[2030] == pytest.approx(0.15561, abs=1e-5)


def test_clearing_prices_and_monitor_agree():
    p = cm.read_t4_clearing_prices()
    assert p[2026] == 63.00 and p[2027] == 65.00 and p[2029] == 27.10 and p[2021] == 8.40
    price, mw = cm.read_monitor_t4_2627()
    assert price == p[2026]                       # two primary sources, same figure
    assert mw == pytest.approx(43000.955)


def test_quotes_present():
    assert all(cm.check_quotes().values()), cm.check_quotes()


def test_all_gas_extra_2026_27():
    x = cm.all_gas_cm_extra(2026)
    assert x.wind_outside_cm_derated_gw == pytest.approx(28.9 * 0.18217354, rel=1e-6)
    assert x.extra_cost_gbp == pytest.approx(x.wind_outside_cm_derated_gw * 1e6 * 63.0)
    assert x.extra_cost_gbp / 1e6 == pytest.approx(331.7, abs=0.1)
    assert x.basis == "estimated"
    assert x.extra_per_avg_household is not None and 0 < x.extra_per_avg_household < 10


def test_missing_year_raises():
    with pytest.raises(KeyError):
        cm.all_gas_cm_extra(2041)
    with pytest.raises(KeyError):
        cm.all_gas_cm_extra(2031)      # no T-4 clearing price yet
