"""Transcription check: our reading of Annex 2 reproduces Ofgem's published Direct Fuel.

Spec draft 3, §8 and §12: index x uplift x losses x Ofgem's own consumption = tab 1a,
for every region and every period, to the penny. This proves we read Ofgem correctly;
it does not test the gas-world model (that is the §8 validation).
"""
from pathlib import Path

import pytest

from gascf.ofgem import REGIONS, read_annex2, unique_periods

ANNEX2 = (Path(__file__).parents[1] / "research/2026-10-10-methods/src/"
          "Annex-2-wholesale-cost-allowance-methodology-v1.30_data_removed-2.xlsx")


@pytest.fixture(scope="module")
def periods():
    return read_annex2(ANNEX2)


def test_period_count(periods):
    # roast 2, check 1: 33 columns with both indices, 32 unique
    assert len(periods) == 33
    assert len(unique_periods(periods)) == 32
    assert periods[0].name.startswith("April 2015")
    assert periods[-1].name == "October 2026 - December 2026"


def test_q4_2026_indices(periods):
    q4 = periods[-1]
    assert q4.elec_index == pytest.approx(99.153, abs=1e-3)
    assert q4.gas_index == pytest.approx(40.24, abs=5e-3)


def test_consumption_basis_changes(periods):
    """Ofgem's typical consumption: 3.1 MWh to Dec 2025, 2.7 Jan-Jun 2026, 2.5 from Jul 2026."""
    by = {p.name: round(p.consumption_mwh(), 3) for p in periods}
    assert by["April 2015 - September 2015"] == 3.1
    assert by["October 2025 - December 2025"] == 3.1
    assert by["January 2026 - March 2026"] == 2.7
    assert by["April 2026 - June 2026"] == 2.7
    assert by["July 2026 - September 2026"] == 2.5
    assert by["October 2026 - December 2026"] == 2.5


@pytest.mark.parametrize("region", REGIONS)
def test_transcription_every_period_to_the_penny(periods, region):
    """Index x uplift x losses x Ofgem's stated consumption = published DF, every period."""
    for p in periods:
        mwh = round(p.consumption_mwh(region), 3)       # Ofgem's TDCV, stated to 0.1 MWh
        assert mwh in (3.1, 2.7, 2.5), (p.name, region, mwh)
        rebuilt = p.elec_index * p.uplift * p.losses(region) * mwh
        assert rebuilt == pytest.approx(p.direct_fuel[region], abs=0.005), (p.name, region)


def test_eastern_q4_2026_matches_roast(periods):
    q4 = periods[-1]
    assert q4.direct_fuel["Eastern"] == pytest.approx(304.42, abs=0.005)
    gb = sum(q4.direct_fuel.values()) / len(REGIONS)
    assert gb == pytest.approx(301.13, abs=0.005)


def test_period_lengths(periods):
    lengths = [p.months for p in unique_periods(periods)]
    assert lengths.count(6) == 15 and sum(lengths) == 15 * 6 + 17 * 3
