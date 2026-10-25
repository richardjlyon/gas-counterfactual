"""RB v1.1 new keys (decision 0160, card [internal ticket]): tables whose numbers are already in the run file but had no key.
No number moves. Each key is checked against the released v4-s37 keys it must add up to (out/figures/v4-s37.json),
never against its own code. All run on the released v4-s37 run file (light)."""
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


# ----------------------------------------------------------------------------- F5 waterfall year by year

def test_f5_waterfall_by_year_adds_to_the_released_2002_24_steps_and_each_years_gap(run, rel):
    from tools.figures_keys import wf_by_year as W
    t = W.values(run)["table_waterfall_by_year"]
    assert [r["year"] for r in t] == list(range(2002, 2026))
    assert t[-1]["provisional"] is True and not any(r["provisional"] for r in t[:-1])
    by_year = {r["year"]: r for r in rel["table_results_by_year"]}
    order = [s["key"] for s in rel["table_waterfall_2002_24"]]
    for r in t:
        assert [s["key"] for s in r["steps"]] == order
        assert sum(s["value"] for s in r["steps"]) == pytest.approx(by_year[r["year"]]["gap_gbp_bn"], abs=1e-9)
        assert r["gap_gbp_bn"] == pytest.approx(by_year[r["year"]]["gap_gbp_bn"], abs=1e-12)
    for i, k in enumerate(order):
        assert sum(r["steps"][i]["value"] for r in t if r["year"] <= 2024) == pytest.approx(rel[k], abs=1e-9), k
    assert W.DECLARED["table_waterfall_by_year"]["units"] == "table, £bn, 2024 prices"


# ----------------------------------------------------------------------------- F4 each option's 2025 figure

# The run file's gap_real_bn is in its own money (2025 prices); keys print 2024 prices. Ratio from the released pair:
# gap_2025p_gbp_bn (figures, 2024 prices) over gap[2025].national_gbp_bn_real (run, 2025 prices).
def test_f4_each_option_2025p_in_2024_prices_and_its_change(run, rel):
    from tools.figures_keys import options_2025p as O
    ratio = rel["gap_2025p_gbp_bn"] / run["gap"]["2025"]["national_gbp_bn_real"]
    assert ratio == pytest.approx(0.9630434782608697, abs=1e-12)        # CPIH 2024 / 2025, not 1
    t = O.values(run)["table_options_2025p"]
    n = sum(len(v) for blk in ("ranked", "methods_page") for v in run["one_at_a_time"][blk].values())
    assert len(t) == n
    for r in t:
        opts = run["one_at_a_time"][r["block"]][r["switch"]]
        o = next(o for o in opts if o["settings"] == r["settings"])
        assert r["gap_2025p_gbp_bn"] == pytest.approx(o["gap_real_bn"]["2025"] * ratio, abs=1e-9)
        assert r["change_gbp_bn"] == pytest.approx(r["gap_2025p_gbp_bn"] - rel["gap_2025p_gbp_bn"], abs=1e-9)
        assert r["provisional"] is True
    # the 2002-24 headline of each row is the released Table 15.1 row (same option, same order)
    for a, b in zip(t, rel["table_one_at_a_time"]):
        assert (a["block"], a["switch"], a["settings"]) == (b["block"], b["switch"], b["settings"])
        assert a["headline_2002_24_gbp_bn"] == pytest.approx(b["headline_2002_24_gbp_bn"], abs=1e-12)
    assert "gap_2025p_central_gbp_bn" not in O.DECLARED       # central 2025 stays gap_2025p_gbp_bn (no duplicate key)


# ----------------------------------------------------------------------------- F3 Annex B at the range ends

def _gap_from_rows(rows) -> float:
    nz = sum(r["value"] for r in rows if r["bill"] == "net_zero_britain" and r["added"])
    rb = sum(r["value"] for r in rows if r["bill"] == "reliable_britain" and r["added"])
    return nz - rb


@pytest.mark.parametrize("end", ["low", "high"])
def test_f3_annex_b_at_each_end_adds_to_the_released_range_end(run, rel, end):
    from tools.figures_keys import annex_b_ends as A
    v = A.values(run)
    t = v[f"annex_b_{end}_end"]
    assert t["switch"] == rel[f"headline_{end}_end_switch"] and t["option"] == rel[f"headline_{end}_end_option"]
    years = {r["year"]: r for r in t["years"]}
    assert sorted(years) == list(range(2002, 2026))
    tot = sum(_gap_from_rows(years[y]["rows"]) for y in range(2002, 2025))
    assert tot == pytest.approx(rel[f"headline_2002_24_{end}_gbp_bn"], abs=1e-6)
    # a line the option does not move keeps its released central Annex B value
    cen = {r["year"]: {x["id"]: x.get("value") for x in r["rows"]} for r in rel["annex_b_annual_tables"]}
    for y, r in years.items():
        for x in r["rows"]:
            if not x["moved"]:
                assert x["value"] == pytest.approx(cen[y][x["id"]], abs=1e-12), (end, y, x["id"])
    assert any(x["moved"] for r in years.values() for x in r["rows"])


# ----------------------------------------------------------------------------- O4 gap per MWh at actual demand

def test_o4_gap_per_mwh_at_both_volumes(run, rel):
    """Released gaps (2024 prices) over the run's billed volume V (years[y].volume_twh) and over V + station load."""
    from tools.figures_keys import gap_per_mwh as G
    v = G.values(run)
    V = {r["year"]: r["volume_twh"] for r in run["years"]}
    SL = {r["year"]: r["station_load_twh"] for r in run["years"]}
    tot_v = sum(V[y] for y in range(2002, 2025))
    tot_vs = sum(V[y] + SL[y] for y in range(2002, 2025))
    assert v["gap_per_mwh_2002_24_billed_gbp"] == pytest.approx(rel["headline_2002_24_gbp_bn"] * 1e3 / tot_v)
    assert v["gap_per_mwh_2002_24_with_station_load_gbp"] == pytest.approx(rel["headline_2002_24_gbp_bn"] * 1e3 / tot_vs)
    assert v["gap_per_mwh_2024_billed_gbp"] == pytest.approx(rel["gap_2024_gbp_bn"] * 1e3 / V[2024])
    assert v["gap_per_mwh_2025p_billed_gbp"] == pytest.approx(rel["gap_2025p_gbp_bn"] * 1e3 / V[2025])
    assert v["gap_per_mwh_2024_with_station_load_gbp"] == pytest.approx(rel["gap_2024_gbp_bn"] * 1e3 / (V[2024] + SL[2024]))
    by = {r["year"]: r for r in v["table_gap_per_mwh_by_year_with_station_load"]}
    gy = {r["year"]: r["gap_gbp_bn"] for r in rel["table_results_by_year"]}
    for y in range(2002, 2026):
        assert by[y]["billed_gbp_mwh"] == pytest.approx(gy[y] * 1e3 / V[y])
        assert by[y]["with_station_load_gbp_mwh"] == pytest.approx(gy[y] * 1e3 / (V[y] + SL[y]))
    for r in v["table_gap_per_mwh_by_year"]:
        assert r["billed_gbp_mwh"] == pytest.approx(gy[r["year"]] * 1e3 / V[r["year"]])
    for k, m in G.DECLARED.items():           # R19 (a) (0163): the billed volume prints (tests/test_v11_o4_r19.py)
        assert m["print"] is ("with_station_load" not in k) and m["ruling"].startswith("R19"), k


# ----------------------------------------------------------------------------- A1 Annex D working (EII)

def test_a1_eii_working_adds_to_the_released_eii_shift_keys(run, rel):
    from tools.figures_keys import eii_shift as E
    t = E.values(run)["table_eii_shift_working"]
    assert [r["year"] for r in t["years"]] == list(range(2018, 2025))
    for reading, key in (("A", "eii_shift_2018_24_low"), ("B", "eii_shift_2018_24_high")):
        assert sum(r[f"shift_{reading}_gbp_m"] for r in t["years"]) / 1e3 == pytest.approx(rel[key], abs=1e-12)
    for r in t["years"]:
        for f in ("final_consumption_twh", "gb_share", "domestic_share", "exempt_twh_fy", "rfc_lines_gbp_m",
                  "cm_line_gbp_m", "ratio_A_rfc", "ratio_B_rfc"):
            assert r[f] is not None, (r["year"], f)
    assert t["exempt_twh_by_fy"][2018] == 10.4 and t["x_reading_A"] == {"to_2023_24": 0.85, "from_2024_25": 1.0}


def test_a1_households_and_share_by_year_are_already_keyed(rel):
    """Annex D's households and household share per year: table_household_by_year (0122) holds both for 2002-25."""
    t = rel["table_household_by_year"]
    assert [r["year"] for r in t] == list(range(2002, 2026))
    assert all("households_m" in r and "domestic_share_pct" in r for r in t)


# ----------------------------------------------------------------------------- A3 §9.8 cost to other gas users

def _npg_built(run):
    """The block's inputs from the released run: each year's engine feedback (fleet[y].gas_feedback)."""
    return {int(y): {"fleet": {"gas_feedback": run["fleet"][y]["gas_feedback"]}} for y in run["fleet"]}


def test_a3_block_reproduces_the_released_totals_and_adds_2025p_outside_them(run):
    from gascf import non_power_gas as N
    yrs = run["non_power_gas"]["years"]
    shares = {int(y): (r["inputs"]["gb_share"], r["inputs"]["gb_share_basis"]) for y, r in yrs.items()}
    price = {int(y): r["inputs"]["gas_price_gbp_mwh"] for y, r in yrs.items()}
    shares[2025], price[2025] = shares[2024], 30.0      # stand-ins for the test only
    b = N.block(_npg_built(run), shares=shares, gas_price=price)
    for k, v in run["non_power_gas"]["totals"]["2002-2024"].items():
        assert b["totals"]["2002-2024"][k] == pytest.approx(v, rel=1e-12), k       # 0099: totals stay 2002-24
    assert "2025" not in b["years"]
    p = b["year_2025p"]
    assert p["provisional"] is True and p["in_totals"] is False
    assert p["inputs"]["uk_demand_twh"] == pytest.approx(680.38579)           # DUKES 2026 Table 4.1, 2025, GWh / 1e3
    assert p["net_gbp_bn_real"] > 0


def test_a3_keys_2025p_print_false_and_the_working_adds_to_the_released_keys(run, rel):
    from tools.figures_keys import non_power_gas as K
    run2 = json.loads(json.dumps(run))
    run2["non_power_gas"]["year_2025p"] = {"net_gbp_bn_real": 1.0, "gross_gbp_bn_real": 2.0,
                                           "range": {"central": 1.0, "krichene_lr": 0.4}, "provisional": True}
    v = K.values(run2)
    r = rel["gap_2025p_gbp_bn"] / run["gap"]["2025"]["national_gbp_bn_real"]       # 2025 to 2024 prices
    assert v["npg_estimate_2025p_central_gbp_bn"] == pytest.approx(1.0 * r)
    assert v["npg_estimate_2025p_low_gbp_bn"] == pytest.approx(0.4 * r)
    assert v["npg_estimate_2025p_gross_gbp_bn"] == pytest.approx(2.0 * r)
    for k in ("npg_estimate_2025p_central_gbp_bn", "npg_estimate_2025p_low_gbp_bn", "npg_estimate_2025p_gross_gbp_bn"):
        assert K.DECLARED[k]["print"] is True and K.DECLARED[k]["ruling"] == "R21 (a)"   # 0163 ([internal ticket])
        assert K.values(run)[k] is None                         # v4-s37 has no 2025 row
    w = v["table_npg_working"]
    assert [x["year"] for x in w["years"]] == list(range(2002, 2025))
    for part, key in (("net_gbp_bn", "npg_estimate_2002_24_central_gbp_bn"), ("gross_gbp_bn",
                      "npg_estimate_2002_24_gross_gbp_bn"), ("low_gbp_bn", "npg_estimate_2002_24_low_gbp_bn")):
        assert sum(x[part] for x in w["years"]) == pytest.approx(rel[key], abs=1e-9), key
    assert w["high"] is None and "no high" in w["high_note"]
    for k in ("npg_estimate_2002_24_central_gbp_bn", "npg_estimate_2002_24_low_gbp_bn",
              "npg_estimate_2002_24_gross_gbp_bn"):
        assert v[k] == rel[k]
