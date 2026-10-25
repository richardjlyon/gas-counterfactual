"""RB v1.1 O4, ruling R19 (a) (decision 0163, card [internal ticket] item 2): "the per-MWh gap at actual demand uses the
billed volume the paper already uses for per-MWh figures". The billed-volume keys print; the station-load keys stay
in the file, unprinted. Values are tested in tests/test_v11_new_keys.py (released gaps over the run's volumes).
Light: the released v4-s37 run file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"


def test_o4_billed_volume_prints_station_load_does_not():
    from tools.figures_keys import gap_per_mwh as G
    for k, m in G.DECLARED.items():
        if "with_station_load" in k:
            assert m["print"] is False, k
        else:
            assert m["print"] is True and m["ruling"] == "R19 (a)", k
            assert "ruling R19, not printed" not in m["label"], k
    assert G.DECLARED["table_gap_per_mwh_by_year"]["print"] is True
    assert G.DECLARED["table_gap_per_mwh_by_year_with_station_load"]["print"] is False


def test_o4_printed_table_has_the_billed_volume_only():
    from tools.figures_keys import gap_per_mwh as G
    v = G.values(json.loads(S37_RUN.read_text()))
    for r in v["table_gap_per_mwh_by_year"]:
        assert set(r) == {"year", "provisional", "gap_gbp_bn", "volume_billed_twh", "billed_gbp_mwh"}
    for r in v["table_gap_per_mwh_by_year_with_station_load"]:
        assert {"station_load_twh", "with_station_load_gbp_mwh"} <= set(r)
