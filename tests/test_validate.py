"""§8 validation gate: the gas-world cost formula must reproduce the day-ahead price
in half-hours when gas sets it. If these fail, nothing is published (spec §8)."""
from datetime import date

import pytest

from gascf.validate import gas_day, validate_year

NORMAL_YEARS = (2018, 2019, 2020, 2021, 2023, 2024, 2025)


@pytest.fixture(scope="module")
def central():
    return {y: validate_year(y) for y in range(2018, 2027)}


def test_gas_day():
    assert gas_day(date(2025, 3, 2), 1) == date(2025, 3, 1)      # 00:00 belongs to previous gas day
    assert gas_day(date(2025, 3, 2), 10) == date(2025, 3, 1)     # 04:30
    assert gas_day(date(2025, 3, 2), 11) == date(2025, 3, 2)     # 05:00 starts the gas day


def test_formula_reproduces_price(central):
    """Central proxy (CCGT >= 10 GW, coal < 1 GW): median spread within ±£5/MWh in every
    non-crisis year (2018-25 actuals: -2.3 to +3.6)."""
    for y in NORMAL_YEARS:
        assert abs(central[y].spread_median) <= 5, (y, central[y].spread_median)


def test_implied_efficiency_matches_dukes(central):
    """Efficiency implied by the market price is within 0.03 of DUKES fleet efficiency."""
    for y in NORMAL_YEARS:
        c = central[y]
        assert abs(c.implied_eta_median - c.eta_dukes) <= 0.03, (y, c.implied_eta_median)


def test_2022_crisis_premium_is_visible(central):
    """2022 carries a market premium over gas cost (median ~£15/MWh) that the other
    years do not: this is what fleet A's market margin exists to absorb, rather than
    let it be booked to renewables (roast 2, N3)."""
    assert central[2022].spread_median > 10
    assert central[2022].spread_median > max(central[y].spread_median for y in NORMAL_YEARS) + 8


def test_enough_half_hours(central):
    for y, c in central.items():
        assert c.n >= 3000, (y, c.n)


def test_carbon_matters():
    """Dropping carbon from the cost would leave a spread equal to the carbon cost:
    2025 UKA ~£40-50/t + CPS -> ~£20+/MWh. The gate would then fail, so it bites."""
    import gascf.validate as v
    real = validate_year(2025).spread_median
    orig = v.CO2_T_PER_MWH_GAS_GCV
    try:
        v.CO2_T_PER_MWH_GAS_GCV = 0.0
        no_carbon = validate_year(2025).spread_median
    finally:
        v.CO2_T_PER_MWH_GAS_GCV = orig
    assert no_carbon - real > 15
