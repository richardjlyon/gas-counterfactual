"""Decision 0162 in the release's annex generator (card [internal ticket] item 8).

- Annex E (Reconciliation) is cut: no annex_e_bridge key.
- The new Annex E, "Version and change log": annex_e_before_after (every headline figure and range end, v4-s37 as
  published against this run) and annex_e_change_log (the measured steps, from reference/change_log_v4_s39.json).
- Annex D in full (0162 item 6): a working key for each derived figure, listed in annex_d_working_index; new workings
  for VAT on the extra, the carbon split by year and the 2001 levels and their netting.
- Annex C: the equations and parameters (read-through item 99): annex_c_equations, annex_c_parameters.

Expected values come from the released v4-s37 figures.json and from the run file's own lines, never from the new code.
Light: the released v4-s37 run file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"
S37_FIGS = ROOT / "out/figures/v4-s37.json"
Y02_24 = [str(y) for y in range(2002, 2025)]


@pytest.fixture(scope="module")
def run():
    return json.loads(S37_RUN.read_text())


@pytest.fixture(scope="module")
def rel():
    return {k: e["value"] for k, e in json.loads(S37_FIGS.read_text())["keys"].items()}


@pytest.fixture(scope="module")
def keys(run):
    from tools import figures as F
    return F.generate(run)["keys"]


def _k24(run, rel):
    return rel["headline_2002_24_gbp_bn"] / sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24)


# ----------------------------------------------------------------------------- Annex E cut, new Annex E

def test_annex_e_bridge_is_cut(keys):
    from tools.figures_keys import recut_0122 as R
    assert "annex_e_bridge" not in keys and "annex_e_bridge" not in R.DECLARED


def test_before_after_reads_v4_s37_as_published_and_this_run(keys, rel):
    t = keys["annex_e_before_after"]
    assert t["meta"]["print"] is True and "v4-s37" in t["meta"]["label"]
    rows = {r["key"]: r for r in t["value"]["rows"]}
    for k in ("headline_2002_24_gbp_bn", "headline_2002_24_low_gbp_bn", "headline_2002_24_high_gbp_bn",
              "gap_2024_gbp_bn", "gap_2025p_gbp_bn", "cost_per_household_2002_24_gbp", "cost_per_household_2024_gbp",
              "headline_low_end_option", "headline_high_end_option", "lost_value_2002_24_central_gbp_bn"):
        r = rows[k]
        assert r["v4_s37"] == rel[k], k                                         # as published
        assert r["this_release"] == keys[k]["value"], k
        if isinstance(r["v4_s37"], float):
            assert r["change"] == pytest.approx(r["this_release"] - r["v4_s37"], abs=1e-12), k
    assert t["value"]["before"] == "v4-s37"
    # on v4-s37's own run file nothing in the headline set moves; lost value moves by item 5 alone
    assert rows["headline_2002_24_gbp_bn"]["change"] == 0.0
    assert rows["lost_value_2002_24_central_gbp_bn"]["change"] == pytest.approx(8.2194 - 6.4421, abs=5e-4)


def test_change_log_steps_from_the_register(keys):
    t = keys["annex_e_change_log"]["value"]
    steps = t["steps"]
    assert [s["order"] for s in steps] == list(range(1, len(steps) + 1))
    for s in steps:
        assert {"item", "what", "decision", "card", "commits", "headline_change_gbp_bn", "status"} <= set(s), s
        assert s["status"] in ("measured", "no number moves", "pending: measured at the cut ([internal ticket])")
    rug = [s for s in steps if s["item"] == "0159 + C-007"][0]
    assert rug["headline_change_gbp_bn"] == pytest.approx(141.693 - 141.101, abs=1e-3)


# ----------------------------------------------------------------------------- Annex D in full

def test_vat_working_follows_the_engine_rule_from_the_lines(run, rel, keys):
    k24 = _k24(run, rel)
    rows = {r["year"]: r for r in keys["table_vat_working"]["value"]}
    for y in Y02_24 + ["2025"]:
        b = run["bills"][y]
        nz = {l["id"]: l["national_gbp_m_real"] for l in b["netzero"]}
        go = {l["id"]: l["national_gbp_m_real"] for l in b["gasonly"]}
        d = b["netzero_on_household_bill_per_household"]["domestic_share"]
        r = rows[int(y)]
        assert r["domestic_share"] == d and r["rate"] == 0.05
        want_nz11 = 0.05 * (d * sum(nz.get(i, 0.0) for i in ("NZ1", "NZ2", "NZ3", "NZ4", "NZ4b", "NZ5", "NZ6", "NZ7"))
                            + nz["NZ10"])
        assert want_nz11 == pytest.approx(nz["NZ11"], rel=1e-9), y
        assert r["vat_on_extra_gbp_bn"] == pytest.approx((nz["NZ11"] - go["GO7"]) * k24 / 1e3, rel=1e-9), y
    assert sum(rows[int(y)]["vat_on_extra_gbp_bn"] for y in Y02_24) == pytest.approx(rel["wf_vat_gbp_bn"], abs=1e-9)


def test_carbon_split_by_year_adds_to_the_released_keys(rel, keys):
    rows = keys["table_carbon_split_by_year"]["value"]
    s = lambda f, ys: sum(r[f] for r in rows if str(r["year"]) in ys)   # noqa: E731
    assert s("carbon_in_price_gbp_bn", Y02_24) == pytest.approx(rel["carbon_line_2002_24_gbp_bn"], abs=1e-9)
    assert s("price_receipts_gbp_bn", Y02_24) == pytest.approx(rel["carbon_price_receipts_2002_24_gbp_bn"], abs=1e-9)
    assert s("rest_in_price_gbp_bn", Y02_24) == pytest.approx(rel["carbon_rest_in_price_2002_24_gbp_bn"], abs=1e-9)


def test_2001_levels_working_adds_to_the_released_netting_keys(rel, keys):
    rows = keys["table_2001_levels_working"]["value"]
    s = lambda f, last=2024: sum(r[f] for r in rows if 2002 <= r["year"] <= last)   # noqa: E731
    assert -(s("ffl_line_gbp_bn", 2019) + s("ffl_vat_gbp_bn", 2019)) == pytest.approx(
        rel["pre2002_netting_nz2_2002_19_gbp_bn"], abs=1e-9)
    assert -(s("eesop_line_gbp_bn") + s("eesop_vat_gbp_bn")) == pytest.approx(
        rel["pre2002_netting_nz10_2002_24_gbp_bn"], abs=1e-9)
    assert s("ccl_2001_level_gbp_bn") == pytest.approx(rel["ccl_2001_level_netted_2002_24_gbp_bn"], abs=1e-9)


def test_annex_d_index_covers_every_derived_figure_of_0162_item_6(keys):
    idx = keys["annex_d_working_index"]["value"]
    assert [p["part"] for p in idx] == ["household figures (divisor and household share)", "VAT on the extra",
                                        "carbon split", "2001 levels and their netting", "EII shift",
                                        "lost value (§12.6)", "other gas users (§9.8)"]
    for p in idx:
        assert p["figures"] and p["working"], p["part"]
        for k in p["figures"] + p["working"]:
            assert k in keys, (p["part"], k)
            assert keys[k]["meta"]["print"] is True, (p["part"], k)


# ----------------------------------------------------------------------------- Annex C

def test_annex_c_equations_hold_on_the_run(run, rel, keys):
    eq = {e["id"]: e for e in keys["annex_c_equations"]["value"]}
    for need in ("gap", "headline", "per_household", "vat", "gas_feedback", "lost_value", "other_gas_users"):
        assert need in eq and eq[need]["equation"] and eq[need]["code"], need
    for y in Y02_24:                                          # the gap identity, each year, from the totals
        t = run["bills"][y]["totals"]
        assert t["gap_gbp_m"] == pytest.approx(t["nz_gbp_m"] - t["go_gbp_m"], abs=1e-6)


def test_annex_c_parameters_are_the_released_values(rel, keys):
    p = {r["name"]: r for r in keys["annex_c_parameters"]["value"]}
    assert p["gas_feedback_e_central"]["value"] == rel["gas_feedback_e_central"]
    assert p["gas_feedback_e_high"]["value"] == rel["gas_feedback_e_high"]
    assert p["margin_central_pct"]["value"] == rel["margin_central_pct"]
    assert p["coal_lf_cap_pct"]["value"] == rel["coal_lf_cap_pct"]
    assert p["lost_value_e_households"]["value"] == -0.607 and p["vat_rate_domestic"]["value"] == 0.05
    for r in p.values():
        assert r["source"] and r["units"], r["name"]
