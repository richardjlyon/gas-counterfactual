"""RB v1.1 (decision 0160, card [internal ticket]): switches built OFF by default, each run as a named row in the run file so
its value is measured, but never in the range, the methods page or the headline. Where each row is printed is a
ruling for Richard (R10 M10, R13 O2, R18 O3; O5a is the 0044 "note run only"), so the rows sit in their own
`one_at_a_time.held` block, which no range or table key reads.

Expected values are literals from the card and the registries' own rules (the central defaults of v4-s37's Settings,
quoted from its docstring), never the engine's own output. The block test uses a stand-in build so it is light.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gascf import bills as B  # noqa: E402

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"      # the released v4-s37 run file (releases.yaml sha256)
S37_FIGS = ROOT / "out/figures/v4-s37.json"


def _all_settings(reg):
    return [s for sets in reg.values() for s in sets]


def test_central_settings_are_v4_s37s_for_every_v11_switch():
    """The central case keeps v4-s37's values for each held-row switch this card touches; the 2021-23 uplift is
    M9 B from v4-s39 (0164 addendum, card [internal ticket]), so 'shao' is now an explicit setting."""
    c = B.CENTRAL
    assert c.nuclear_cm_column == "post_trade_less_suspended"     # 0089 variant D
    assert c.ccl_lec_cap is True                                   # 0044 cap ruling
    assert c.moe_crisis == "m9_direct_mayon"                       # 0164 (was 'shao', 0069)
    assert getattr(c, "cost_case", "medium") == "medium"           # the editions' medium column


def test_o3_row_is_held_not_ranked_not_methods_page():
    row = B.HELD_O3
    assert [s.nuclear_cm_column for s in B.HELD_SWITCHES[row]] == ["auction_acquired"]
    assert row not in B.SWITCHES and row not in B.METHOD_SWITCHES
    assert all(s.nuclear_cm_column == "post_trade_less_suspended"
               for s in _all_settings(B.switch_settings()) + _all_settings(B.METHOD_SWITCHES))


def test_o5a_row_is_held_and_is_the_0044_note_run():
    row = B.HELD_O5A
    assert [s.ccl_lec_cap for s in B.HELD_SWITCHES[row]] == [False]
    assert row not in B.SWITCHES and row not in B.METHOD_SWITCHES
    assert all(s.ccl_lec_cap is True for s in _all_settings(B.switch_settings()) + _all_settings(B.METHOD_SWITCHES))


# M10: UCL Table 5 'Long-Term MOE Model Results', column (2) 'Total MOE', printed p.25 (PDF p.27), wind, GBP/MWh,
# stored as magnitudes (data/raw/s36/ucl_oshea_2025_moe.yaml): 2021 7.19, 2022 18.18, 2023 8.41.
UCL_T5 = {2021: 7.19, 2022: 18.18, 2023: 8.41}
SHAO_SOLAR = 2.98     # Shao et al. (2022) Table 3 pooled solar term, GBP/MWh per GW (stored as -2.98)


def test_m10_long_run_target_is_table5_plus_shao_solar_part_beside_the_short_run_rule():
    """The rule mirrors 0086 target B with Table 5 in place of Table 4: UCL wind + the engine's Shao solar part."""
    from gascf import moe_crisis as MC
    assert "ucl_ltmoe" in MC.RULES and "ucl_stmoe" in MC.RULES
    for y, t5 in UCL_T5.items():
        assert MC.target_gbp_mwh(y, 0.0, rule="ucl_ltmoe") == pytest.approx(t5, abs=1e-12)
        assert MC.target_gbp_mwh(y, 2.0, rule="ucl_ltmoe") == pytest.approx(t5 + 2 * SHAO_SOLAR, abs=1e-12)
        assert MC.k(y, 10.0, 0.0, rule="ucl_ltmoe") == pytest.approx(t5 / 10.0, abs=1e-12)
    assert MC.k(2020, 10.0, 0.0, rule="ucl_ltmoe") == 1.0
    # the short-run rule is unchanged (Table 4: 2022 56.48)
    assert MC.target_gbp_mwh(2022, 0.0) == pytest.approx(56.48, abs=1e-12)


def test_m10_row_is_held_not_methods_page():
    row = B.HELD_M10
    assert [s.moe_crisis for s in B.HELD_SWITCHES[row]] == ["ucl_ltmoe"]
    assert row not in B.SWITCHES and row not in B.METHOD_SWITCHES
    # v4-s39: the methods-page rows sit on the central's M9 B (0164) unless they are the UCL row; never the held M10
    assert all(s.moe_crisis in (B.CENTRAL.moe_crisis, "ucl_stmoe") for s in _all_settings(B.METHOD_SWITCHES))


def test_m10_scale_reaches_the_fleet_uplift_in_crisis_years_only():
    """2022 (about 1 min): the long-run uplift over the short-run uplift is (T5 + solar part) / (T4 + solar part), with
    UCL's own Table 4 (56.48) and Table 5 (18.18) and the year's solar part (2.98 x mean solar GW). Outside 2021-23 the
    held rule takes the central cache key."""
    assert B._lfl_args(B.replace(B.CENTRAL, moe_crisis="ucl_ltmoe"), 2022)[10] == "ucl_ltmoe"
    assert B._lfl_args(B.replace(B.CENTRAL, moe_crisis="ucl_ltmoe"), 2020)[10] == "shao"
    st = B.fleet_lfl(2022, *B._lfl_args(B.replace(B.CENTRAL, moe_crisis="ucl_stmoe"), 2022))
    lt = B.fleet_lfl(2022, *B._lfl_args(B.replace(B.CENTRAL, moe_crisis="ucl_ltmoe"), 2022))
    sol = SHAO_SOLAR * st["moe"]["solar_gw_mean"]
    want = (UCL_T5[2022] + sol) / (56.48 + sol)
    for k in ("moe_gbp_m", "moe_kept_gbp_m"):
        assert lt[k] / st[k] == pytest.approx(want, rel=1e-9), k


# A5 (J3): Krichene (2005) IMF WP/05/32 Table 2 'Long-Run Elasticities', panel 1 'Vector error correction method',
# period 1974-2004 (PDF p.13): natural gas supply 0.21 (t 6.51), demand -0.06 (t -1.67); sum 0.27. Confirmed by the
# analyst (card [internal ticket]) and read here from the stored text. The cointegration panel is a different estimator.
def _krichene_t2_vecm_1974_2004() -> tuple[float, float]:
    import re
    t = (ROOT / "data/raw/s36/s36-krichene2005_IMF_WP0532.txt").read_text()
    i = t.index("Table 2: World Crude Oil and Natural Gas: Long-Run Elasticities")
    j = t.index("2. Cointegration method", i)
    vecm = t[i:j]
    assert "Period 1974-2004" in vecm
    dem = re.search(r"Natural gas demand\s+Price elasticity\s+\S+ \([^)]*\)\s+\S+ \([^)]*\)\s+(-?[\d.]+) \(", vecm)
    sup = re.search(r"Natural gas supply\s+Price elasticity\s+\S+ \([^)]*\)\s+\S+ \([^)]*\)\s+(-?[\d.]+) \(", vecm)
    return float(sup.group(1)), -float(dem.group(1))


def test_a5_pair_is_krichene_vecm_1974_2004_from_the_stored_text():
    from gascf import fossil_like_for_like as L
    s, d = _krichene_t2_vecm_1974_2004()
    assert (s, d) == (0.21, 0.06)
    assert L.GAS_ELASTICITY_PAIRS["krichene_lr_1974"] == (s, d)
    assert L.GAS_ELASTICITY["krichene_lr_1974"] == pytest.approx(0.27)
    assert "krichene_lr_1974" in L.GAS_FEEDBACK_RULES


def test_a5_row_is_held_and_the_range_feedback_row_is_unchanged():
    row = B.HELD_A5
    assert [s.gas_feedback for s in B.HELD_SWITCHES[row]] == ["krichene_lr_1974"]
    assert row not in B.SWITCHES and row not in B.METHOD_SWITCHES
    assert [s.gas_feedback for s in B.SWITCHES[B.FEEDBACK_KRICHENE]] == ["krichene_lr"]      # 0.61 stays the row
    from tools.figures_keys import range as R
    assert R.option_name("x", {"gas_feedback": "krichene_lr_1974"}) == \
        "gas-price feedback, elasticity 0.27 (supply 0.21 + demand 0.06)"


def test_held_block_in_one_at_a_time_with_every_held_row():
    """The run file carries `one_at_a_time.held`, one entry per held row, built like the other two blocks."""
    from gascf import one_at_a_time as O

    def fake_build(s):
        return {y: {"netzero": [], "fossil": [], "nz1c": {"national_gbp_m_nominal": 0.0},
                    "totals": {"gap_real_bn": 1.0}} for y in B.YEARS}
    central = fake_build(B.CENTRAL)
    blk = O.block(central, build=fake_build, ranked={}, methods={}, checks={})
    assert set(blk) == {"ranked", "methods_page", "held", "method_checks"}     # v4-s40 item 9 adds the fourth group
    assert list(blk["held"]) == list(B.HELD_SWITCHES)
    for row, sets in B.HELD_SWITCHES.items():
        assert len(blk["held"][row]) == len(sets)


def test_range_and_table_keys_ignore_the_held_block():
    """A held row far below the low end and far above the high end changes no range or table key."""
    from tools.figures_keys import range as R
    run = json.loads(S37_RUN.read_text())
    before = R.values(run)
    ys = [str(y) for y in B.YEARS]
    run["one_at_a_time"]["held"] = {
        "probe low": [{"settings": {"nuclear_cm_column": "auction_acquired"},
                       "gap_real_bn": {y: -1000.0 for y in ys}, "lines_moved_gbp_m_nominal": {}}],
        "probe high": [{"settings": {"ccl_lec_cap": False},
                        "gap_real_bn": {y: 1000.0 for y in ys}, "lines_moved_gbp_m_nominal": {}}]}
    assert R.values(run) == before


# ----------------------------------------------------------------------------- the held keys

# The 2025-to-2024 price ratio read from the released v4-s37 pair: headline_2002_24_gbp_bn (figures.json, 2024 prices)
# over the run file's Σ2002-24 gap[y].national_gbp_bn_real (2025 prices): 141.10113... / 146.51584... .
TO_2024 = 141.10113097962292 / 146.51584706687706
HELD_KEYS = {"held_o3_nuclear_cm_auction_2002_24_gbp_bn": "HELD_O3",
             "headline_lec_uncapped_2002_24_gbp_bn": "HELD_O5A",
             "held_m10_ucl_long_run_2002_24_gbp_bn": "HELD_M10",
             "held_o2_high_capital_hurdle_2002_24_gbp_bn": "HELD_O2_CAP_HURDLE",
             "held_o2_high_capital_only_2002_24_gbp_bn": "HELD_O2_CAP",
             "held_a5_krichene_1974_2004_2002_24_gbp_bn": "HELD_A5"}


def _run_with_held(deltas: dict) -> dict:
    run = json.loads(S37_RUN.read_text())
    ys = [str(y) for y in B.YEARS]
    run["one_at_a_time"]["held"] = {
        getattr(B, attr): [{"settings": {}, "lines_moved_gbp_m_nominal": {},
                            "gap_real_bn": {y: run["gap"][y]["national_gbp_bn_real"] + d for y in ys}}]
        for attr, d in deltas.items()}
    return run


def test_each_held_row_has_a_key_off_print_and_reads_its_row():
    from tools.figures_keys import held_rows as H
    attrs = sorted(set(HELD_KEYS.values()))
    run = _run_with_held({a: 0.1 * (i + 1) for i, a in enumerate(attrs)})
    v = H.values(run)
    for key, attr in HELD_KEYS.items():
        meta = H.DECLARED[key]
        assert meta["in_range"] is False and meta["can_set_range_end"] is False   # placement: test_v11_rows_placed
        d = 0.1 * (attrs.index(attr) + 1)
        assert v[key] == pytest.approx((146.51584706687706 + 23 * d) * TO_2024, abs=1e-9)
        assert v[key.replace("_gbp_bn", "_change_gbp_bn")] == pytest.approx(23 * d * TO_2024, abs=1e-9)


def test_held_keys_are_none_on_a_run_without_the_block():
    from tools.figures_keys import held_rows as H
    run = json.loads(S37_RUN.read_text())
    assert all(v is None for v in H.values(run).values())


def test_held_keys_change_no_released_v4_s37_key():
    """Every v4-s37 figures key keeps its released value when the held module is in the key list. One key is moved by
    this branch's base (e7b86f8, decision 0159, Rugeley 1,006 MW; b2d7df5, C-007, zone 18), not by this card, and is
    named."""
    from tools import figures as F
    moved_by_0159 = {"rugeley_margin_ex_carbon_last_year_gbp_m"}
    # card [internal ticket] item 5: lost value with the same-in-both block counted once (tests/test_v11_lost_value_once.py)
    moved_by_item5 = ({f"lost_value_{p}_{c}_gbp_bn" for p in ("2002_24", "2025p") for c in ("low", "central", "high")}
                      | {f"rb.lost_value.straight_line.{c}.{p}" for c in ("low", "central", "high")
                         for p in ("2002-2024", "2025")}
                      | {"rb.lost_value.by_year", "lost_value_straight_line_over_quoted_pct"})
    # card [internal ticket]: a text key relabelled on purpose, because 0164 (M9 B) supersedes its claim for 2021-23
    # (tests/test_shao_relabel_v4_s39.py); its figures are unchanged
    relabelled_by_0164 = {"note_uplift_2021_23_probably_low"}
    out = F.generate(json.loads(S37_RUN.read_text()))["keys"]
    rel = json.loads(S37_FIGS.read_text())["keys"]

    # v4-s41 (decision 0184, card [internal ticket]) adds two columns to table_results_by_year; they are additions, checked in
    # tests/test_v4_s41_bill_per_mwh.py, and every value the row already had is still compared here
    added_v4_s41 = ("nz_bill_gbp_per_mwh", "rb_bill_gbp_per_mwh")

    def no_labels(v):          # W1 (0160) renames rows inside table keys (tests/test_v11_w1_wording.py); numbers stay
        if isinstance(v, dict):  # F1/F2 ([internal ticket]) add each Annex B line's tag and cash figure and each year's basis
            return {a: no_labels(b) for a, b in v.items()
                    if a not in ("label", "tag", "cash_gbp_m", "data_basis", *added_v4_s41)}
        if isinstance(v, list):
            return [no_labels(b) for b in v]
        return v
    for k, e in rel.items():
        if k == F.REGISTER_KEY or k in moved_by_0159 or k in moved_by_item5 or k == "annex_e_bridge" \
                or k in relabelled_by_0164:   # cut, 0162
            continue
        assert no_labels(out[k]["value"]) == no_labels(e["value"]), k
