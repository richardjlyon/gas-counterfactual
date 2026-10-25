"""Input audit v4-s41, part A find 1 (A1): Kilroot coal deduction, 2010 and 2011 (card [internal ticket]; v4-s42, decision 0195).

The 'DUKES 2010' and 'DUKES 2011' sheets of DUKES 2026 Table 5.11 print one row 'AES | Kilroot | coal/oil | 662'.
The 'DUKES 2012' sheet splits the same station into 'Kilroot | coal/oil | 520' and 'Kilroot OCGT | gas oil | 142'.
Until v4-s41 the engine took all 662 MW off UK coal, so 142 MW of oil-fired OCGT came off coal and was missing from
Northern Ireland 'other'. The candidate takes 520 MW off coal and counts 142 MW in NI 'other', as the 2012 sheet does.

Ruled in decision 0195 (part A option 1(b)). Expected values are the printed MW
in data/raw/DUKES_5.11.xlsx (sheets named) and Table 5.7.A (All generating companies, Coal fired, 2010: 23,682.21).
"""
import pytest

from gascf import fossil_fleet as ff
from gascf import fossil_like_for_like as lfl


@pytest.mark.parametrize("year", [2010, 2011])
def test_kilroot_coal_is_520_not_662(year):
    assert ff.kilroot_mw()[year] == pytest.approx(520.0)


@pytest.mark.parametrize("year,mw", [(2008, 520.0), (2009, 600.0), (2012, 520.0), (2016, 540.0)])
def test_other_kilroot_years_unchanged(year, mw):
    assert ff.kilroot_mw()[year] == pytest.approx(mw)


def test_gb_coal_2010_is_uk_coal_less_520():
    coal, basis = ff.coal_capacity_gb(2010)
    assert coal == pytest.approx(23682.21 - 520.0, abs=0.01)
    assert basis == "measured"


@pytest.mark.parametrize("year,other", [(2010, 540.0 + 142.0), (2011, 656.0 + 142.0)])
def test_kilroot_ocgt_counted_in_ni_other(year, other):
    assert lfl.ni_fossil_mw()[year]["other"] == pytest.approx(other)


@pytest.mark.parametrize("year,other", [(2009, 540.0), (2012, 851.0)])
def test_ni_other_neighbours_unchanged(year, other):
    assert lfl.ni_fossil_mw()[year]["other"] == pytest.approx(other)
