"""Input audit v4-s41, part A find 3 (A3): gas transport, calendar 2021-25 (card [internal ticket]; v4-s42, decision 0195).

Until v4-s41 every year took the 2026/27 charges restated back with CPIH. National Gas published one uniform rate for
every gas year from 1 Oct 2020 (postage stamp, UNC 0678A). The candidate reads the published rate for each gas year
(firm NTS Exit (Flat) Capacity Reserve Price at directly connected points + Exit RRC, the engine's own 2026/27
construction; General Non-Transmission Services exit charge) and maps gas years to calendar years as the engine maps
other years that start on 1 October: CY y = 0.75 x GY(y-1) + 0.25 x GY(y). 2002-20 keep the CPIH back-cast.
Ruled in decision 0195 (part A option 3(b)). Expected values are the printed rates in the six saved statements and notices
(data/raw/nationalgas/hist/; locators in data/raw/SOURCES.md).
"""
import pytest

from gascf import bills
from gascf import gastransport as gt

# gas year (start): (exit reserve price, Exit RRC, GNTS exit), p/kWh/day and p/kWh, as printed
PRINTED = {2020: (0.0198, 0.0046, 0.0128), 2021: (0.0211, 0.0, 0.0092), 2022: (0.0218, 0.0, 0.0343),
           2023: (0.0127, 0.0, 0.0533), 2024: (0.0265, 0.0, 0.0075), 2025: (0.0299, 0.0, 0.0206)}


@pytest.mark.parametrize("gy", sorted(PRINTED))
def test_published_gas_year_rates(gy):
    p = gt.read_published_gas_years()[gy]
    ex, rrc, gn = PRINTED[gy]
    assert p.exit_capacity_p_kwh_day == pytest.approx(ex + rrc, abs=1e-9)
    assert p.commodity_p_kwh == pytest.approx(gn, abs=1e-9)


@pytest.mark.parametrize("y", range(2021, 2026))
def test_calendar_2021_25_from_published(y):
    t = bills.transport_for(y)
    a, b = PRINTED[y - 1], PRINTED[y]
    assert t.exit_capacity_p_kwh_day == pytest.approx(0.75 * (a[0] + a[1]) + 0.25 * (b[0] + b[1]), abs=1e-9)
    assert t.commodity_p_kwh == pytest.approx(0.75 * a[2] + 0.25 * b[2], abs=1e-9)


def test_2020_keeps_the_cpih_back_cast():
    from gascf import deflator_cpih as dfl
    t, t26 = bills.transport_for(2020), gt.read_transport()["2026/27"]
    k = dfl.cpih()[2020] / dfl.cpih()[2025]
    assert t.exit_capacity_p_kwh_day == pytest.approx(t26.exit_capacity_p_kwh_day * k)
