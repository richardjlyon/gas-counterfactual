"""Carbon reader: UK ETS monthly averages, EU ETS auctions before May 2021, CPS."""
from datetime import date, timedelta
from pathlib import Path

import pytest

from gascf.carbon import (allowance_monthly_gbp, carbon_gbp_per_mwh_elec, cps_gbp_per_mwh_gas,
                          read_ukets_ccm)

RAW = Path(__file__).parents[1] / "data/raw"


@pytest.fixture(scope="module")
def ccm():
    return read_ukets_ccm(RAW / "UKETS_CCM_full_table.html")


@pytest.fixture(scope="module")
def allowance():
    return allowance_monthly_gbp(RAW)


def test_ukets_months_read_at_source(ccm):
    avgs, trig = ccm
    # values as printed on gov.uk (CCM full table, read 10 Oct 2026)
    assert avgs[(2021, 5)] == 49.09 and avgs[(2022, 1)] == 76.70
    assert avgs[(2026, 8)] == 59.34 and avgs[(2026, 3)] == 39.46
    assert trig[(2027, 3)] == 148.59
    assert min(avgs) == (2021, 5) and len(avgs) == 64      # May 2021 to Aug 2026, no gaps


def test_series_is_continuous(allowance):
    months = list(allowance)
    assert months[0] == (2014, 1)
    for (y, m), (y2, m2) in zip(months, months[1:]):
        assert (y2, m2) == ((y, m + 1) if m < 12 else (y + 1, 1))
    assert {s for _, s in allowance.values()} == {"EUA", "UKA"}
    assert allowance[(2021, 4)][1] == "EUA" and allowance[(2021, 5)][1] == "UKA"


def _weekdays(y, m, start=1):
    d, n = date(y, m, start), 0
    while d.month == m:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


@pytest.mark.parametrize("assess,ref,mult", [
    ((2021, 8), ((2019, 5), (2021, 4)), 2.0),
    ((2021, 12), ((2019, 9), (2021, 8)), 2.0),
    ((2022, 6), ((2020, 3), (2022, 2)), 2.5),
    ((2023, 2), ((2020, 8), (2022, 7)), 3.0),
    ((2023, 6), ((2020, 12), (2022, 11)), 3.0),
])
def test_reproduces_authority_trigger_prices(ccm, allowance, assess, ref, mult):
    """The Authority's trigger = multiple x the 2-year mean of EUA (to Dec 2020, at BoE daily
    rates) and UKA (from 19 May 2021) December futures; Jan-18 May 2021 not counted.
    Rebuilt from our independent series it lands 0.2-1.1% low: we use EEX auction (spot)
    prices before 2021, the Authority used December futures, which carry a small premium.
    A wrong FX direction, wrong contract or wrong month alignment misses by far more."""
    _, trig = ccm
    num = den = 0.0
    (y, m), end = ref
    while (y, m) <= end:
        if (y, m) < (2021, 1) or (y, m) >= (2021, 5):
            w = _weekdays(y, m, 19) if (y, m) == (2021, 5) else _weekdays(y, m)
            num += allowance[(y, m)][0] * w
            den += w
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    gap = mult * num / den / trig[assess] - 1
    assert -0.012 < gap < 0.0


def test_cps_rates():
    assert cps_gbp_per_mwh_gas(date(2014, 3, 31)) == 0.91
    assert cps_gbp_per_mwh_gas(date(2015, 4, 1)) == 3.34
    assert cps_gbp_per_mwh_gas(date(2026, 10, 8)) == 3.31
    with pytest.raises(ValueError):
        cps_gbp_per_mwh_gas(date(2028, 4, 1))
    with pytest.raises(ValueError):
        cps_gbp_per_mwh_gas(date(2013, 3, 31))


def test_carbon_per_mwh_electricity():
    """Aug 2026 UKA £59.34 at the 2025 CCGT fleet efficiency 47.99% GCV:
    59.34 x 0.18194 / 0.4799 + 3.31 / 0.4799 = 22.50 + 6.90 = £29.39/MWh."""
    v = carbon_gbp_per_mwh_elec(59.34, date(2026, 8, 15), 0.4799)
    assert v == pytest.approx(29.39, abs=0.01)


def test_auction_filter():
    """2015 report: 142 EU + 47 DE + 6 PL general auctions (T3PA); 12 aviation (EAA3) excluded.
    2020: one cancelled T3PA auction excluded."""
    from gascf.carbon import read_eex_auctions
    z = RAW / "eex/emission-spot-primary-market-auction-report-2012-2025-data.zip"
    assert len(read_eex_auctions(z, range(2015, 2016))) == 195
    assert len(read_eex_auctions(z, range(2020, 2021))) == 139 + 46 + 24
