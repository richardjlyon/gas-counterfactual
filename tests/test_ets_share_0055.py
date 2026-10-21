"""Ticket 21 (share part): power's share of UK auction revenue (0058 emissions-share rule), 2009-25.
2009-20: the 0055 calibrated stand-in (DESNZ GHG 1.2 power stations less MSW / UK EU ETS verified emissions,
EEA v82) with its band (low = x 0.957, high = EUTL activity-20 share). 2021: 0.428 (0055). 2022-24: DESNZ
printed power and covered totals. 2025: the 2024 share (0079). Expected values: research-model-items.md item 1."""
from __future__ import annotations

import pytest

from gascf import ets_auctions as E

RESEARCH = {  # year: (share, low, high), research-model-items.md item 1 table (3 dp, band 2 dp)
    2009: (0.646, 0.62, 0.82), 2010: (0.657, 0.63, 0.83), 2011: (0.648, 0.62, 0.82), 2012: (0.651, 0.62, 0.80),
    2013: (0.630, 0.60, 0.77), 2014: (0.597, 0.57, 0.74), 2015: (0.554, 0.53, 0.72), 2016: (0.507, 0.49, 0.71),
    2017: (0.470, 0.45, 0.68), 2018: (0.457, 0.44, 0.69), 2019: (0.437, 0.42, 0.68), 2020: (0.415, 0.40, 0.67)}


def test_2009_20_share_is_the_stand_in_with_its_band():
    for y, (v, lo, hi) in RESEARCH.items():
        s = E.power_share(y)
        assert s["value"] == pytest.approx(v, abs=5e-4), y
        assert s["low"] == pytest.approx(lo, abs=0.005), y
        # 2012 high is 0.7947 from the tables, printed 0.80 in the research table (0.0053 off its 2-dp rounding;
        # reported in ticket 21); every other year is inside the printed rounding
        assert s["high"] == pytest.approx(hi, abs=0.0055 if y == 2012 else 0.005), y
        assert s["low"] == pytest.approx(0.957 * s["value"], abs=1e-12)
        assert s["rule"] == "0055 stand-in"


def test_2021_24_shares_are_desnz_printed_and_2025_carries_2024():
    exp = {2021: 0.428, 2022: 48_193_462 / 110_618_346, 2023: 36_084_695 / 96_750_817,
           2024: 29_484_524 / 85_634_344}
    for y, v in exp.items():
        assert E.power_share(y)["value"] == pytest.approx(v, abs=1e-6), y
    s25 = E.power_share(2025)
    assert s25["value"] == E.power_share(2024)["value"] and s25["status"] == "provisional"
    assert s25["rule"] == "0079: 2024 share"


def test_calibration_printed():
    # UK ETS power (DESNZ) / inventory power stations less MSW (DESNZ GHG 1.2): 0055's calibration line
    c = E.share_calibration()
    assert c == {2022: pytest.approx(0.991, abs=5e-4), 2023: pytest.approx(0.957, abs=5e-4),
                 2024: pytest.approx(0.972, abs=5e-4)}
