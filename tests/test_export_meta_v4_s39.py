"""Card [internal ticket]: the run file's meta.counterfactual describes the v4-s39 central, not the v4-s38 one.

Literals are the rulings' own subjects (decisions 0164, 0166, 0167, 0169), not engine output.
"""
from __future__ import annotations

from gascf import export_v4 as E


def test_counterfactual_text_names_the_v4_s39_rulings():
    t = E._counterfactual_text()
    assert "Shao et al. 2022" in t                                   # 2002-20, Jan-Apr 2021, 2024-25p
    assert "May 2021 to Dec 2023" in t and "0164" in t              # M9 B
    assert "permit hours" in t and "0166" in t                      # coal hours reading (i)
    assert "marginal plant" in t and "0167" in t                    # M7 merit order
    assert "MID" in t                                               # M8 shape, both Britains
    assert "generators' share" in t                                 # 0167 way 2
    assert "RO mutualisation" in t and "0169" in t


def test_counterfactual_text_no_longer_says_shao_is_the_uplift_in_every_year():
    t = E._counterfactual_text()
    assert "merit-order uplift = Shao et al. 2022 (spec" not in t
    assert "kept coal capped at the DUKES 5.10.B load factor" not in t
