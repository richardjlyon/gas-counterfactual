"""Daily gas SAP: ONS copy (2018-2021) + National Gas API (Dec 2021-)."""
from datetime import date, timedelta

import pytest

from gascf.sap import API_FROM, read_api, read_ons, sap_gbp_per_mwh


def test_two_copies_agree_on_overlap():
    ons, api = read_ons(), read_api()
    overlap = sorted(set(ons) & set(api))
    assert overlap[0] == date(2021, 12, 1) and overlap[-1] == date(2021, 12, 19)
    for d in overlap:
        assert ons[d] == pytest.approx(api[d], abs=5e-5), d


def test_spot_values():
    ons, api = read_ons(), read_api()
    assert ons[date(2018, 1, 1)] == 1.7083          # first ONS row
    assert api[date(2021, 12, 1)] == 8.0803
    assert api[date(2026, 10, 6)] == 6.262          # cross-checks research ng.json


def test_series_is_daily_and_unbroken():
    s = sap_gbp_per_mwh()
    days = list(s)
    assert days[0] == date(2018, 1, 1)
    gaps = [(a, b) for a, b in zip(days, days[1:]) if b - a != timedelta(days=1)]
    assert gaps == []
    assert days[-1] >= date(2026, 10, 1)
    assert s[date(2021, 12, 1)] == pytest.approx(80.803)   # £/MWh = p/kWh x 10
    assert all(d < API_FROM for d in read_ons() if d not in read_api())
