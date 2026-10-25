"""Input audit v4-s41, part C find 1 (C1): UK EU ETS auction revenue, calendar 2016 (card [internal ticket]; v4-s42, decision 0195).

The engine's 2016 figure (£311.0m) is built from EC UK Auction Platform Report no. 58, section 5, whose row "Q4' 16"
prints revenue EUR 55,622,630 for 17,447,500 allowances at EUR 4.52 (sold x price is EUR 78.9m, so the row is wrong).
The per-auction tables of the October and December 2016 reports (section 1, p.1) give EUR 94,635,240 for the five Q4
EUA auctions (14 Dec cancelled; the 26 Oct EUAA auction is left out as in every other year 2013-18). On the engine's own
construction (EUR at the BoE 2016 annual-mean rate, 1.2233) 2016 is GBP 342.2m. BEIS ARA 2017-18 Trust Statement
note 2.2 agrees with the per-auction figure. Ruled in decision 0195 (v4-s42). Expected values are the printed rows.
"""
import pytest

from gascf import ets_auctions as E

Q4_PER_AUCTION_EUR = [18_494_350, 20_518_260, 20_518_260, 19_715_675, 15_388_695]   # 5, 19 Oct; 2, 16, 30 Nov 2016
Q4_REPORT58_EUR = 55_622_630
YEAR_REPORT58_EUR_M = 379.603          # report 58, section 5, calendar 2016 EUA total as the engine built it
XUDLERS_2016 = 1.2233


def test_per_auction_sum():
    assert sum(Q4_PER_AUCTION_EUR) == 94_635_240


def test_2016_revenue_is_342_2():
    want = (YEAR_REPORT58_EUR_M - Q4_REPORT58_EUR / 1e6 + sum(Q4_PER_AUCTION_EUR) / 1e6) / XUDLERS_2016
    assert want == pytest.approx(342.2, abs=0.05)
    assert E.uk_revenue_2013_20()[2016]["gbp_m"] == pytest.approx(342.2)


@pytest.mark.parametrize("year,v", [(2015, 412.0), (2017, 529.4)])
def test_neighbours_unchanged(year, v):
    assert E.uk_revenue_2013_20()[year]["gbp_m"] == pytest.approx(v)
