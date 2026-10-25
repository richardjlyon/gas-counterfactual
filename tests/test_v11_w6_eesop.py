"""RB v1.1 W6 (card [internal ticket] item 7; option-a-sourcing.md section 6): sourced.eesop_fy2001_02_level_gbp_m is a
two-year average, April 2000 to March 2002, not a figure for 2001/02. Its label says so, and its locator cites Ofgem's
March 2000 EESoP 3 final decision for the dates (PDF p.2 and Schedule 1(1)); Figure 3.1 of the 2003 review carries
only "2000 - 2002". Label and locator only: the value stays 55 (£110m over two years, halved)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

KEY = "sourced.eesop_fy2001_02_level_gbp_m"


def test_w6_value_unchanged_label_says_two_year_average():
    from tools.figures_keys import sourced as S
    assert S.values({})[KEY] == 55
    lab = S.DECLARED[KEY]["label"]
    assert "average" in lab and "April 2000 to March 2002" in lab and "2000/01 and 2001/02" in lab


def test_w6_locator_cites_the_final_decision_for_the_dates():
    from tools.figures_keys import sourced as S
    m = S.DECLARED[KEY]
    loc = m["locator"]
    assert "Figure 3.1" in loc and "PDF p.14" in loc and "£110 million (indicative)" in loc
    assert "Energy Efficiency Standards of Performance 2000-2002: Final Decisions" in loc and "March 2000" in loc
    assert "PDF p.2" in loc and "\"the period April 2000 to March 2002\"" in loc
    assert "Schedule 1(1), PDF p.15" in loc and "\"between 1 April 2000 and 31" in loc
    assert "m2-0097/ofgem-2000-03-eesop3-final-decisions.pdf" in m["file"]
    assert m["derivation"].startswith("110 / 2 = 55")
