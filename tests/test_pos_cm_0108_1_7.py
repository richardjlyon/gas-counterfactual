"""Decision 0108 item 1.7 (Richard Lyon, 19 Oct 2026, option (a)): "the net-zero change" in the Capacity Market figures
(ticket 15 test 19, 0075) is contracted minus metered NZ5, as a new run-file field, with its 2002-24 total in 2024
prices. Contracted = the central build; metered = the range registry's metered-interconnector row (ic_basis only, the
row test 18 compares). Before 2016 nothing is contracted, so the change is 0 there (0062)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gascf import bills as B

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _toy_build(nz5):
    return {y: {"netzero": [{"id": "NZ5", "national_gbp_m_nominal": nz5(y)}]} for y in B.YEARS}


def test_block_is_contracted_minus_metered_nz5_by_year():
    from gascf import pos_cm_block as P
    central = _toy_build(lambda y: 100.0 + y if y >= 2016 else 50.0)
    metered = _toy_build(lambda y: 50.0)
    blk = P.block(central, build=lambda s: metered)
    assert blk["metered_settings"] == {"ic_basis": "metered"}
    for y in B.YEARS:
        want = (100.0 + y - 50.0) if y >= 2016 else 0.0
        assert blk["netzero_change_gbp_m"][str(y)] == pytest.approx(want, abs=1e-12), y
    assert blk["money"] == "cash £m" and blk["decision"] == "0108 item 1.7"


def test_block_registered_and_keys_read_it():
    from gascf import export_v4 as X
    from gascf import deflator_cpih
    assert "gascf.pos_cm_block" in X.BLOCK_MODULES
    from tools.figures_keys import pos_cm as K
    from tools import figures_keys
    assert "pos_cm" in figures_keys.MODULES
    ch = {str(y): (10.0 if y >= 2016 else 0.0) for y in B.YEARS}
    run = {"meta": {"price_base": 2025, "deflator": "ONS CPIH L522"}, "pos_cm": {"netzero_change_gbp_m": ch}}
    v = K.values(run)
    c = deflator_cpih.cpih()
    want = sum(deflator_cpih.to_real(10.0, y, 2025) for y in range(2016, 2025)) * c[2024] / c[2025] / 1e3
    assert v["pos_cm_netzero_change_2002_24_gbp_bn"] == pytest.approx(want, rel=1e-12)
    assert v["pos_cm_netzero_change_gbp_m"] == {y: ch[y] for y in map(str, range(2016, 2025))}
    assert v["pos_cm_netzero_change_gbp_m"]["2016"] == 10.0
    assert K.values({"meta": run["meta"]})["pos_cm_netzero_change_2002_24_gbp_bn"] is None
