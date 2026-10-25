"""Card [internal ticket]: under M9 B (decision 0164) the run file's fleet[y].moe.applied_mean_gbp_mwh and the GO1 note give
the uplift actually applied, not the Shao mean before the 2021-23 rule.

Expected: [internal ticket]'s independent measurement of B's 2022 scale on the Shao mean, k = 2.8295 (card metadata
"k": {"B": {"2022": 2.8295}}); 2020 is outside the window, so the applied mean is the Shao mean (rule 'shao').
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gascf import bills as B
from gascf import fossil_like_for_like as L

REG = str(Path(__file__).resolve().parents[1] / "reference/fossil_closures.yaml")


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    from _pre_0133 import s39_caches    # caches are keyed on arguments, not the register: clear either side
    for f in s39_caches():
        f.cache_clear()
    monkeypatch.setenv(L.CLOSURES_ENV, REG)
    yield
    for f in s39_caches():
        f.cache_clear()


def _moe(y):
    return B.fleet_lfl(y, *B._lfl_args(B.CENTRAL, y))["moe"]


def test_2022_applied_mean_is_the_m9_b_uplift():
    m = _moe(2022)
    assert m["crisis_rule"] == "m9_direct_mayon"
    assert m["applied_mean_gbp_mwh"] == pytest.approx(m["shao_mean_gbp_mwh"] * 2.8295, rel=2e-4)


def test_2020_applied_mean_is_shao():
    m = _moe(2020)
    assert m["crisis_rule"] == "shao"
    assert m["applied_mean_gbp_mwh"] == pytest.approx(m["shao_mean_gbp_mwh"], rel=1e-12)
