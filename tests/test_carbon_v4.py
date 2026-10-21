"""Strand s20c: carbon counted once (spec §6, §3.1 NZ1c, §15 decision 3)."""
from datetime import date

import pytest

from gascf import carbon as c


def test_eea_annual_series():
    e = c.read_eea_eua_annual()
    assert e[2005] == pytest.approx(21.82, abs=0.01) and e[2020] == pytest.approx(24.36, abs=0.01)


def test_allowance_regimes():
    a = c.allowance_monthly_v4()
    assert a[(2004, 12)][0] == 0                                  # no market before 2005
    assert a[(2008, 6)][1] == "estimated"                         # EEA 2005–12, unstated origin
    assert a[(2015, 6)][2] == c.SRC_EEX
    for m in range(1, 5):                                         # decision 3: Jan–Apr 2021 zero
        assert a[(2021, m)][0] == 0
    assert a[(2021, 5)][0] == pytest.approx(49.09) and a[(2021, 5)][2] == c.SRC_UKA


def test_jan_apr_2021_cps_only():
    eta = 0.49
    v = c.c_marg_gbp_per_mwh_elec(0.0, date(2021, 2, 1), eta)
    assert v == pytest.approx(3.31 / eta)                          # CPS £3.31/MWh gas, no allowance


def test_cps_zero_before_april_2013_and_coal_factor():
    assert c.cps_gas_or_zero(date(2013, 3, 1)) == 0
    assert c.cps_gbp_per_mwh_coal(date(2013, 3, 1)) == 0
    assert c.cps_gbp_per_mwh_coal(date(2016, 6, 1)) == pytest.approx(1.5479 * 3.6)
    assert c.co2_t_per_mwh_coal() == pytest.approx(0.3226, abs=0.0005)


def test_nz1c_is_price_times_volume():
    eta = {y: 48.0 for y in range(2002, 2026)}
    v = {(2024, m): 10.0 for m in range(1, 13)}
    out = c.nz1c(v, eta)
    cm = c.c_marg_monthly(eta, range(2024, 2025))
    assert out[2024]["gbp_m"] == pytest.approx(10 * sum(cm[(2024, m)]["gbp_per_mwh"] for m in range(1, 13)))
    assert c.nz1c({(2003, 1): 30.0}, eta)[2003]["gbp_m"] == 0


def test_collected_cpf_read():
    assert c.collected_carbon_on_power(2016) == pytest.approx(1044.0)
