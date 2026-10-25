"""RB v1.1 rows placed by ruling (decision 0163, card [internal ticket] item 3).

O2, R13 (a) (DESNZ's published high case as it stands, capital and hurdle rate) and O3, R18 (a) (nuclear in
the Capacity Market at its auction obligation) are methods-page rows; M10, R10 (a) (UCL long-term 2021-23) and A5,
R14 (a) (Krichene's 0.27) are sensitivity rows, 0.61 staying the range end. Each is printed, and none can set an end of
the printed range. Light: the released v4-s37 run file with a stand-in held block.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gascf import bills as B  # noqa: E402

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"


# ----------------------------------------------------------------------------- rows that print, never a range end

PLACED = {"held_o2_high_capital_hurdle_2002_24_gbp_bn": ("HELD_O2_CAP_HURDLE", "methods_page", "R13 (a)"),
          "held_o3_nuclear_cm_auction_2002_24_gbp_bn": ("HELD_O3", "methods_page", "R18 (a)"),
          "held_m10_ucl_long_run_2002_24_gbp_bn": ("HELD_M10", "sensitivity", "R10 (a)"),
          "held_a5_krichene_1974_2004_2002_24_gbp_bn": ("HELD_A5", "sensitivity", "R14 (a)")}
UNPLACED = ("held_o2_high_capital_only_2002_24_gbp_bn", "headline_lec_uncapped_2002_24_gbp_bn")


def test_ruled_rows_print_in_their_place_and_cannot_set_a_range_end():
    from tools.figures_keys import held_rows as H
    for key, (_, place, ruling) in PLACED.items():
        for k in (key, key.replace("_gbp_bn", "_change_gbp_bn")):
            m = H.DECLARED[k]
            assert m["print"] is True and m["placement"] == place and m["ruling"] == ruling, k
            assert m["in_range"] is False and m["can_set_range_end"] is False, k
            assert "not printed" not in m["label"], k
    for key in UNPLACED:                                    # R13 (a) chose capital and hurdle; O5a is a note run
        assert H.DECLARED[key]["print"] is False


def _run_with_held(deltas: dict) -> dict:
    run = json.loads(S37_RUN.read_text())
    ys = [str(y) for y in B.YEARS]
    run["one_at_a_time"]["held"] = {
        getattr(B, a): [{"settings": {}, "lines_moved_gbp_m_nominal": {},
                         "gap_real_bn": {y: run["gap"][y]["national_gbp_bn_real"] + d for y in ys}}]
        for a, d in deltas.items()}
    return run


def test_ruled_rows_table_lists_each_row_with_its_place():
    from tools.figures_keys import held_rows as H
    attrs = sorted({a for a, _, _ in PLACED.values()} | {"HELD_O2_CAP", "HELD_O5A"})
    v = H.values(_run_with_held({a: 0.1 for a in attrs}))
    t = v["table_ruled_rows"]
    assert [r["key"] for r in t] == list(PLACED)
    for r in t:
        _, place, ruling = PLACED[r["key"]]
        assert (r["placement"], r["ruling"], r["can_set_range_end"]) == (place, ruling, False)
        assert r["headline_2002_24_gbp_bn"] == v[r["key"]]


def test_a_ruled_row_beyond_either_end_moves_no_range_key():
    """O2 and O3 far below the low end, M10 and A5 far above the high end: the range keys do not move."""
    from tools import figures as F
    base = json.loads(S37_RUN.read_text())
    probe = _run_with_held({"HELD_O2_CAP_HURDLE": -50.0, "HELD_O3": -40.0, "HELD_M10": 40.0, "HELD_A5": 50.0,
                            "HELD_O2_CAP": 0.0, "HELD_O5A": 0.0})
    rng = ("headline_2002_24_low_gbp_bn", "headline_2002_24_high_gbp_bn", "headline_low_end_switch",
           "headline_high_end_switch", "headline_range_text")
    from tools.figures_keys import range as R
    a, b = R.values(base), R.values(probe)
    assert {k: a[k] for k in rng} == {k: b[k] for k in rng}
    keys = F.generate(probe)["keys"]
    assert keys["held_a5_krichene_1974_2004_2002_24_gbp_bn"]["value"] > keys["headline_2002_24_high_gbp_bn"]["value"]
    assert keys["held_o2_high_capital_hurdle_2002_24_gbp_bn"]["value"] < keys["headline_2002_24_low_gbp_bn"]["value"]
