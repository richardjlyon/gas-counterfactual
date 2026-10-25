"""Input audit v4-s41, part A find 2 (A2): Northern Ireland CCGT deduction, 2006 (card [internal ticket]; v4-s42, decision 0195).

The 'DUKES 2006' sheet of DUKES 2026 Table 5.11 labels Coolkeeragh CCGT (420 MW) 'N. Ireland', not 'Northern
Ireland', so the engine's region filter missed it: NI CCGT 2006 read as 616 MW (Ballylumford C only); the sheet
gives 1,036 MW. Ruled in decision 0195 (part A option 2(b)). The 2002-04 nearest-year list behind it is not ruled (Q-0195-A).
"""
import pytest

from gascf import fossil_like_for_like as lfl


def test_coolkeeragh_counted_2006():
    assert lfl.ni_fossil_mw()[2006]["ccgt"] == pytest.approx(616.0 + 420.0)


def test_ni_other_2006_unchanged():
    assert lfl.ni_fossil_mw()[2006]["other"] == pytest.approx(380.0)


@pytest.mark.parametrize("year,ccgt", [(2007, 1024.0), (2012, 1024.0), (2019, 1029.0)])
def test_ni_ccgt_other_years_unchanged(year, ccgt):
    assert lfl.ni_fossil_mw()[year]["ccgt"] == pytest.approx(ccgt)
