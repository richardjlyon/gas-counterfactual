"""s36 ticket 09 (B4, 0030): GO4's gas index runs on Ofgem NBP before October 2009, the same series
GO1 uses (`fossil_fleet.gas_price_month`), so one gas series runs through the bill.

Seams: `balancing.gas_monthly` / `balancing.gas_annual` (GO4's gas index) and `balancing.go4`."""
import statistics

import pytest

from gascf import balancing as b
from gascf import fossil_fleet as F

PRE = [(y, m) for y in range(2002, 2010) for m in range(1, 13) if (y, m) < (2009, 10)]


@pytest.mark.parametrize("month", PRE, ids=lambda k: f"{k[0]}-{k[1]:02d}")
def test_go4_gas_equals_go1_nbp_before_oct_2009(month):
    """One series: GO4's gas price for every month before Oct 2009 is GO1's NBP price."""
    assert b.gas_monthly()[month] == pytest.approx(F.gas_price_month(*month)[0], rel=1e-12)


# v4-s35 GO4 gas index, £/MWh (computed from the s35 code before this change): unchanged from Oct 2009
S35_ANNUAL = {2010: 14.48340732, 2011: 19.2112150298, 2012: 20.3716278081, 2013: 23.2361213949,
              2014: 17.0789103437, 2015: 14.553071895, 2016: 11.8247796609, 2017: 15.3745451898,
              2018: 20.5954074837, 2019: 11.8438307896, 2020: 8.4646723831, 2021: 39.5455936161,
              2022: 72.1651067489, 2023: 33.8561304257, 2024: 29.0148689794, 2025: 30.4471157729}
S35_OCT_DEC_2009 = {10: 8.5917746894, 11: 9.2093724729, 12: 10.7209515783}


def test_months_from_oct_2009_unchanged_against_v4_s35():
    g, a = b.gas_monthly(), b.gas_annual()
    for m, v in S35_OCT_DEC_2009.items():
        assert g[(2009, m)] == pytest.approx(v, abs=1e-9)
    for y, v in S35_ANNUAL.items():
        assert a[y] == pytest.approx(v, abs=1e-9), y


def test_g0_and_per_year_factor_against_stored_nbp_and_qep_means():
    """g0 (2002-05 base-window mean) is the stored NBP means' mean, not QEP's, and GO4's energy part
    moves by the NBP year mean over g0 (generators' share left in, so the factor is clean)."""
    j = __import__("gascf.prices", fromlist=["x"]).qep_vs_nbp_annual()
    g0_nbp = statistics.mean(j[y]["nbp"] for y in b.BASE_WINDOW)
    g0_qep = statistics.mean(j[y]["qep"] for y in b.BASE_WINDOW)
    a = b.gas_annual()
    assert statistics.mean(a[y] for y in b.BASE_WINDOW) == pytest.approx(g0_nbp, rel=1e-12)
    assert abs(g0_nbp - g0_qep) > 0.1
    go = b.go4(2024, gen_share="included")
    for y in range(2002, 2026):
        assert go[y]["energy_gbp_m"] / go[2002]["energy_gbp_m"] == pytest.approx(j[y]["nbp"] / j[2002]["nbp"],
                                                                                  rel=1e-9), y


def test_meta_gaps_no_longer_report_the_qep_join():
    from gascf import export_v4
    assert not [g for g in export_v4.GAPS if "QEP" in g]
