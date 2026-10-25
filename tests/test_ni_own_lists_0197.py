"""Decision 0197 (Richard Lyon, 24 Oct 2026, msg 8982: "each year's own list"; card [internal ticket], v4-s43).

For 2002-05 the Northern Ireland stations taken off UK capacity are each year's own DUKES list, classed as each
list prints them (Kilroot's coal/oil row is NI coal, already out of GB coal; a CCGT label is NI CCGT; anything
else, e.g. "oil" or "oil/gas", is NI 'other'). Expected values are the printed cells, not engine output:

  DUKES 2002 Table 5.10 (end of May 2002; data/raw/dukes_s43/dukes2002_table5_10_end-may-2002.xls):
      Coolkeeragh oil 293 (D53); Ballylumford oil/gas 1,080 (D131)          -> other 1,373, CCGT 0
  DUKES 2003 Table 5.10 (end of May 2003; data/raw/dukes_s43/dukes2003_table5_10_end-may-2003.xls):
      Coolkeeragh oil 293 (D57); Ballylumford oil/gas 823 (D134)            -> other 1,116, CCGT 0
  DUKES 2004 (data/raw/DUKES_5.11.xlsx sheet 'DUKES 2004', no region column, read by station name):
      Coolkeeragh oil 120 (D56); Ballylumford oil/gas 1,216 (D121)          -> other 1,336, CCGT 0
  DUKES 2005 (sheet 'DUKES 2005', read by station name):
      Coolkeeragh CCGT 420 (D77); Ballylumford CCGT 996 (D165)              -> CCGT 1,416, other 0
  From 2006 nothing changes: 'DUKES 2006' CCGT 616 + 420 = 1,036, other 380 (Ballylumford B gas/oil).

Kilroot coal/oil 520 is in every list and is NI coal, not counted here (DUKES 2002 row 12, 2003 row 12, 2004 and
2005 row 9). With a list for every year from 2002 the nearest-year fill (the 2006 list for 2002-05) no longer fires.
"""
import pytest

from gascf import fossil_like_for_like as lfl


@pytest.mark.parametrize("year,ccgt,other", [
    (2002, 0.0, 293.0 + 1080.0),
    (2003, 0.0, 293.0 + 823.0),
    (2004, 0.0, 120.0 + 1216.0),
    (2005, 420.0 + 996.0, 0.0),
    (2006, 616.0 + 420.0, 380.0),
])
def test_each_years_own_ni_list(year, ccgt, other):
    assert lfl.ni_fossil_mw()[year] == {"ccgt": pytest.approx(ccgt), "other": pytest.approx(other)}


def test_every_year_from_2002_has_its_own_list_so_no_nearest_year_fill():
    ni = lfl.ni_fossil_mw()
    assert min(ni) == 2002
    assert [y for y in range(2002, 2026) if y not in ni] == []


def test_the_two_texts_say_what_the_engine_does():
    from gascf import fallbacks
    doc = lfl.ni_fossil_mw.__doc__ or lfl.ni_fossil_mw.__wrapped__.__doc__
    assert "Editions before 2006 list none" not in doc
    assert "DUKES 2002" in doc and "DUKES 2003" in doc
    d = fallbacks.DECLARED["ni_fossil_nearest_year"]
    assert "does not cover" not in d
    assert "before 2002" in d
