"""Ticket 28 (0095): the printed range from the one-at-a-time table, each option alone, the rest central.

Seams: the run-file block `one_at_a_time` (`gascf.one_at_a_time.block`, registered through 02's hook; tested
with a stub build, light) and `tools.figures.generate(run)` (keys built from that block)."""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import bills as B  # noqa: E402
from gascf import one_at_a_time as O  # noqa: E402

YEARS = list(B.YEARS)


def _built(gap_bn: float, nz8: float = 100.0, nz1c: float = 50.0) -> dict:
    return {y: {"totals": {"gap_real_bn": gap_bn, "gap_gbp_m": gap_bn * 1e3},
                "netzero": [{"id": "NZ8", "national_gbp_m_nominal": nz8}, {"id": "NZ2", "national_gbp_m_nominal": 10.0}],
                "fossil": [{"id": "GO1", "national_gbp_m_nominal": 5.0}],
                "nz1c": {"id": "NZ1c", "national_gbp_m_nominal": nz1c}} for y in YEARS}


def test_block_exports_each_option_alone_with_its_settings_and_gap_by_year():
    lo, hi = replace(B.CENTRAL, margin="low"), replace(B.CENTRAL, margin="high")
    runs = {lo: _built(9.0), hi: _built(11.0, nz8=130.0)}
    blk = O.block(_built(10.0), build=runs.__getitem__, ranked={"spare margin (6.6% / 8.2%)": (lo, hi)}, methods={},
                  held={}, checks={})     # RB v1.1 (0160) held block and v4-s40 item 9 method checks, empty here
    opts = blk["ranked"]["spare margin (6.6% / 8.2%)"]
    assert [o["settings"] for o in opts] == [{"margin": "low"}, {"margin": "high"}]
    assert opts[0]["gap_real_bn"]["2024"] == 9.0 and opts[1]["gap_real_bn"]["2002"] == 11.0
    assert opts[1]["lines_moved_gbp_m_nominal"]["2024"] == {"NZ8": 30.0}
    assert opts[0]["lines_moved_gbp_m_nominal"]["2024"] == {}
    assert blk["methods_page"] == {} and blk["held"] == {}


def test_block_is_registered_through_the_run_file_hook():
    from gascf import export_v4 as X
    assert "gascf.one_at_a_time" in X.BLOCK_MODULES
    assert X._BLOCKS.get("one_at_a_time") is O.block


from gascf import figures as GF  # noqa: E402
from tools import figures as F  # noqa: E402

S35 = ROOT / "out/v4/2026-10-14-s35.json"
Y02_24 = [str(y) for y in range(2002, 2025)]


def _opt(run, settings, delta_bn, moved=None):
    return {"settings": settings,
            "gap_real_bn": {y: run["gap"][y]["national_gbp_bn_real"] + delta_bn for y in run["gap"]},
            "lines_moved_gbp_m_nominal": {y: dict(moved or {}) for y in run["gap"]}}


@pytest.fixture(scope="module")
def run():
    r = json.loads(S35.read_text())
    gas = next(k for k in B.SWITCHES if k.startswith("gas-price feedback"))
    special = {
        "spare margin (6.6% / 8.2%)": [_opt(r, {"margin": "low"}, -0.1), _opt(r, {"margin": "high"}, 0.1)],
        gas: [_opt(r, {"gas_feedback": "krichene_lr"}, 0.4)],          # 0144 4A: one paired row (was 0.34 / 0.06)
        "kept_price (actual / fleet avg)": [_opt(r, {"kept_price": "actual"}, -0.7),
                                            _opt(r, {"kept_price": "fleet_avg"}, 0.0)],
        # the options the ticket-28 sensitivity keys look up by their settings
        "capacity market (kept coal in CM / full CM)": [_opt(r, {"cm_rule": "extra_kept_coal"}, -0.3),
                                                        _opt(r, {"cm_rule": "full"}, 0.3)],
        "grid renewal R (low / high)": [_opt(r, {"renewal": "low"}, -0.2), _opt(r, {"renewal": "high"}, 0.25)],
    }
    r["one_at_a_time"] = {
        "ranked": {k: special.get(k, [_opt(r, {"toy": k}, 0.0)]) for k in B.SWITCHES},
        "methods_page": {k: [_opt(r, {"toy": k}, -9.0)] for k in B.METHOD_SWITCHES},
    }
    return r


@pytest.fixture(scope="module")
def built(run):
    return F.generate(run)


def _v(built, k):
    return built["keys"][k]["value"]


def test_range_ends_are_min_and_max_of_the_ranked_table_and_name_their_option(run, built):
    t = _v(built, "table_one_at_a_time")
    ranked = [r for r in t if r["block"] == "ranked"]
    lo, hi = min(ranked, key=lambda r: r["headline_2002_24_gbp_bn"]), max(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    assert _v(built, "headline_2002_24_low_gbp_bn") == pytest.approx(lo["headline_2002_24_gbp_bn"], abs=1e-9)
    assert _v(built, "headline_2002_24_high_gbp_bn") == pytest.approx(hi["headline_2002_24_gbp_bn"], abs=1e-9)
    assert _v(built, "headline_low_end_option") == lo["option"]
    assert _v(built, "headline_high_end_option") == hi["option"]
    central = GF.to_2024(sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24), run)
    # 0144: the toy's low end is now kept_price actual (-0.7 a year); v4-s36's toy had the 0.06 feedback row (-1.5)
    assert _v(built, "headline_2002_24_low_gbp_bn") == pytest.approx(central + GF.to_2024(-0.7 * 23, run), abs=1e-9)
    assert _v(built, "headline_low_end_switch") == lo["switch"] and _v(built, "headline_high_end_switch") == hi["switch"]


def test_case_b_never_enters_the_range(run, built):
    """Fixture now in the real block's shape (ticket 22 built, 19 Oct 2026: `sensitivities_case_b.cases[case][y]`);
    the earlier guessed shape had no `cases` level. Intent unchanged: a huge negative case B moves neither end."""
    r = json.loads(json.dumps(run))
    rows = {y: {"gap_real_bn": -999.0, "dq_twh": 0.0, "rise_at_e016": 0.0, "rise_at_e006": 0.0} for y in r["gap"]}
    r["sensitivities_case_b"] = {"cases": {c: rows for c in ("central", "closures_actual", "closures_actual_e006",
                                                             "case_b_all_three")},
                                 "sign_check": {"case_b_all_three": {"passed": False, "negative_years": [2002]}}}
    again = F.generate(r)
    for k in ("headline_2002_24_low_gbp_bn", "headline_2002_24_high_gbp_bn"):
        assert _v(again, k) == _v(built, k)


def test_every_registry_switch_needs_a_row(run):
    r = json.loads(json.dumps(run))
    r["one_at_a_time"]["ranked"] = {k: v for k, v in r["one_at_a_time"]["ranked"].items() if not k.startswith("spare")}
    with pytest.raises(KeyError, match="spare margin"):
        F.generate(r)


def test_gas_feedback_row_labels_by_value_and_pair(built):
    """0144 (v4-s37): the feedback row is named by its paired elasticity, never by an engine word; v4-s36's
    sens_e006 / sens_e034 keys are gone with the supply-only rows."""
    import re
    from gascf.fossil_like_for_like import GAS_ELASTICITY
    rows = [r for r in _v(built, "table_one_at_a_time") if "gas_feedback" in r["settings"] and r["block"] == "ranked"]
    assert [r["settings"]["gas_feedback"] for r in rows] == ["krichene_lr"]
    for r in rows:
        assert f"elasticity {GAS_ELASTICITY[r['settings']['gas_feedback']]:g} (supply 0.16 + demand 0.45)" in r["option"]
        assert not re.search(r"\b(low|high)\b", r["option"]), r["option"]
    assert "sens_e006_2002_24_gbp_bn" not in built["keys"] and "sens_e034_2002_24_gbp_bn" not in built["keys"]


def test_every_option_has_one_choice_and_choice_tables_hold_only_their_rows(run, built):
    t = _v(built, "table_one_at_a_time")
    for r in t:
        assert r["choice"] in range(1, 9), r["switch"]
    for c in range(1, 9):
        assert _v(built, f"table_choice{c}") == [r for r in t if r["choice"] == c]
    by = {r["switch"]: r["choice"] for r in t}
    assert by["residual method 2016+ (FUELHH)"] == 1 and by["wholesale_pre2010 (lower / model)"] == 3
    assert by["gas transport (none)"] == 4 and by["closures as they actually happened"] == 1
    r = json.loads(json.dumps(run))
    r["one_at_a_time"]["methods_page"]["an unmapped new switch"] = [_opt(r, {"toy": 1}, 0.0)]
    with pytest.raises(KeyError, match="choice"):
        F.generate(r)


def test_one_at_a_time_carbon_and_ccl_rows_apart(run, built):
    for r in _v(built, "table_one_at_a_time"):
        assert isinstance(r["lines_moved"], list)
    bad = json.loads(json.dumps(run))
    bad["one_at_a_time"]["methods_page"]["closures as they actually happened"] = [
        _opt(bad, {"closures": "actual"}, 0.0, moved={"NZ1": 5.0})]
    assert "NZ1" in next(r for r in F.generate(bad)["keys"]["table_one_at_a_time"]["value"]
                         if r["switch"] == "closures as they actually happened")["lines_moved"]
    CHOICE = {"no merit-order uplift (§15.3 rule)": 3}
    for label, moved in (("a carbon option", {"NZ8": 1.0}), ("CCL 2001 rates frozen", {"NZ1c": 1.0})):
        b = json.loads(json.dumps(run))
        b["one_at_a_time"]["methods_page"][label] = [_opt(b, {"toy": 1}, 0.0, moved=moved)]
        with pytest.raises(ValueError, match="moves"):
            from tools.figures_keys import range as RG
            RG.check_carbon_ccl_apart(RG.table(b, choices=CHOICE | {label: 8}))


# ---- decision 0112 (Richard Lyon, 19 Oct 2026, item 1.4 option (a)): the range is set by SWITCHES plus the s36
# alternative central choices: metered interconnectors, rpi_x, CCL cash-frozen, 2001 levels cash-flat and GBP 85.5m.
# Methods-page rows and case B are out; 2.4: the UCL row (M8) is a methods-page row, outside the range.
RANGE_0112_ADDED = {"grid index at the controls' own X (RPI-X, 0091)": {"go5_index": "rpi_x"},
                    "2001 CCL rate held cash-frozen (ccl_2001_cash_frozen, 0044)": {"ccl_baseline": "cash_2001"},
                    "2001 on-the-road levels held cash-flat (on_the_road_cash_flat, 0097)": {"otr_indexation": "cash"},
                    "£85.5m NFFO payments estimate as the 2001 Fossil Fuel Levy level "
                    "(on_the_road_nz2_nffo_payments, 0097)": {"otr_nz2_level_gbp_m": 85.5}}


def test_range_registry_is_switches_plus_the_0112_alternatives():
    from dataclasses import replace
    assert B.SWITCHES["interconnectors at peak (metered flow, v4-s35)"] == (replace(B.CENTRAL, ic_basis="metered"),)
    for label, diff in RANGE_0112_ADDED.items():
        assert B.SWITCHES[label] == (replace(B.CENTRAL, **diff),), label
        assert label not in B.METHOD_SWITCHES, label
    assert B.NFFO_85_5 in RANGE_0112_ADDED and B.OTR_CASH_FLAT in RANGE_0112_ADDED and B.CCL_CASH_FROZEN in RANGE_0112_ADDED
    assert "merit-order uplift 2021-23: UCL short-run (preprint)" in B.METHOD_SWITCHES          # 2.4: M8 stays out
    assert "merit-order uplift 2021-23: UCL short-run (preprint)" not in B.SWITCHES
    assert "closures as they actually happened" in B.METHOD_SWITCHES


def test_0112_rows_are_ranked_and_can_set_an_end(run):
    r = json.loads(json.dumps(run))
    lab = B.NFFO_85_5
    r["one_at_a_time"]["ranked"][lab] = [_opt(r, {"otr_nz2_level_gbp_m": 85.5}, -50.0)]
    out = F.generate(r)["keys"]
    assert out["headline_low_end_option"]["value"].startswith(lab)
    row = next(x for x in out["table_one_at_a_time"]["value"] if x["switch"] == lab)
    assert row["block"] == "ranked" and row["choice"] == 8


def test_named_range_row_keys_read_their_ranked_rows_0112(run):
    """Keys left 'for a ruling' by tickets 12 and 26, now ruled (0108 item 1.20, 0112): each is the 2002-24 headline
    (2024 prices) of its own one-at-a-time row."""
    r = json.loads(json.dumps(run))
    for lab, d, diff in ((B.CCL_CASH_FROZEN, -1.0, {"ccl_baseline": "cash_2001"}),
                         (B.OTR_CASH_FLAT, 2.0, {"otr_indexation": "cash"}),
                         (B.NFFO_85_5, 0.5, {"otr_nz2_level_gbp_m": 85.5})):
        r["one_at_a_time"]["ranked"][lab] = [_opt(r, diff, d)]
    out = F.generate(r)["keys"]
    rows = {x["switch"]: x["headline_2002_24_gbp_bn"] for x in out["table_one_at_a_time"]["value"]}
    assert out["headline_ccl_cash_frozen_2002_24_gbp_bn"]["value"] == rows[B.CCL_CASH_FROZEN]
    assert out["sens_pre2002_cash_flat_2002_24_gbp_bn"]["value"] == rows[B.OTR_CASH_FLAT]
    assert out["sens_pre2002_nffo_payments_2002_24_gbp_bn"]["value"] == rows[B.NFFO_85_5]
    assert rows[B.NFFO_85_5] > rows[B.CCL_CASH_FROZEN]


SENS_ROWS = {  # figures-keys.md rows (ticket 28): key -> (block, switch label, the option's settings or None if one)
    "sens_closures_actual_2002_24_gbp_bn": ("methods_page", "closures as they actually happened", None),
    "sens_margin_low_2002_24_gbp_bn": ("ranked", "spare margin (6.6% / 8.2%)", {"margin": "low"}),
    "sens_ic_metered_2002_24_gbp_bn": ("ranked", "interconnectors at peak (metered flow, v4-s35)", None),
    "sens_cm_kept_coal_2002_24_gbp_bn": ("ranked", "capacity market (kept coal in CM / full CM)",
                                         {"cm_rule": "extra_kept_coal"}),
    "sens_no_moe_2002_24_gbp_bn": ("methods_page", "no merit-order uplift (§15.3 rule)", None),
    "sens_kept_price_actual_2002_24_gbp_bn": ("ranked", "kept_price (actual / fleet avg)", {"kept_price": "actual"}),
    "sens_grid_base_high_2002_24_gbp_bn": ("ranked", "grid renewal R (low / high)", {"renewal": "high"}),
}


def test_sensitivity_row_keys_read_their_one_at_a_time_option(run):
    """figures-keys.md ticket-28 rows, each the 2002-24 headline (2024 prices) of one named option; 0108 item 1.15
    confirmed sens_grid_base_high = grid renewal R high."""
    r = json.loads(json.dumps(run))
    r["one_at_a_time"]["ranked"]["capacity market (kept coal in CM / full CM)"] = [
        _opt(r, {"cm_rule": "extra_kept_coal"}, -0.3), _opt(r, {"cm_rule": "full"}, 0.3)]
    r["one_at_a_time"]["ranked"]["grid renewal R (low / high)"] = [
        _opt(r, {"renewal": "low"}, -0.2), _opt(r, {"renewal": "high"}, 0.25)]
    out = F.generate(r)["keys"]
    rows = out["table_one_at_a_time"]["value"]
    for key, (blk, sw, settings) in SENS_ROWS.items():
        (want,) = [x["headline_2002_24_gbp_bn"] for x in rows if x["block"] == blk and x["switch"] == sw
                   and (settings is None or x["settings"] == settings)]
        assert out[key]["value"] == want, key
    central = GF.to_2024(sum(r["gap"][y]["national_gbp_bn_real"] for y in Y02_24), r)
    assert out["sens_grid_base_high_2002_24_gbp_bn"]["value"] == pytest.approx(central + GF.to_2024(0.25 * 23, r))
