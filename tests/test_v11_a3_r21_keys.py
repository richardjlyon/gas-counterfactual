"""RB v1.1 A3, R21 (a) (decision 0163; card [internal ticket] item 4): §9.8 prints the 2002-24 and 2025 figures for other gas
users, with the working in Annex D. Plus R26 / R123 (research-director's comment on the card): the Shao-method
uplift for 2021 and 2023 beside the 2022 key, same basis. No number moves.

Keys confirmed (report-writer's provisional names, v1.1-inserts/a3-9.8-other-gas-users.md):
npg_estimate_2025p_{central,low,gross}_gbp_bn keep their names; npg_producers_gain_2002_24_gbp_bn is new, with
npg_producers_gain_2025p_gbp_bn beside it. R21 (a) sets 0099's "never 2025" aside for §9.8's 2025 figure only; Richard
is asked to confirm that (R36). Expected values are the released v4-s37 run file's own block totals (gross = net +
producers' gain) and its fleet records, read here independently of the key code.
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


@pytest.fixture(scope="module")
def run():
    return json.loads(S37_RUN.read_text())


def _with_2025p(run):
    r = json.loads(json.dumps(run))
    r["non_power_gas"]["year_2025p"] = {"net_gbp_bn_real": 1.0, "gross_gbp_bn_real": 2.0,
                                        "producers_gain_gbp_bn_real": 1.0,
                                        "range": {"central": 1.0, "krichene_lr": 0.4},
                                        "inputs": {}, "provisional": True, "in_totals": False}
    return r


def test_r21a_2025_keys_and_working_print_with_the_ruling():
    from tools.figures_keys import non_power_gas as K
    for k in ("npg_estimate_2025p_central_gbp_bn", "npg_estimate_2025p_low_gbp_bn", "npg_estimate_2025p_gross_gbp_bn",
              "npg_producers_gain_2025p_gbp_bn", "table_npg_working"):
        m = K.DECLARED[k]
        assert m["print"] is True and m["ruling"] == "R21 (a)", k
        assert "0099" in m["note"] and "R36" in m["note"], k
    for k in ("npg_estimate_2002_24_central_gbp_bn", "npg_producers_gain_2002_24_gbp_bn"):
        assert K.DECLARED[k]["print"] is True and K.DECLARED[k]["period"] == "2002-2024"


def test_producers_gain_is_gross_less_net(run):
    from gascf.figures import to_2024
    from tools.figures_keys import non_power_gas as K
    rel = {k: e["value"] for k, e in json.loads(S37_FIGS.read_text())["keys"].items()}
    v = K.values(run)
    assert v["npg_producers_gain_2002_24_gbp_bn"] == pytest.approx(
        rel["npg_estimate_2002_24_gross_gbp_bn"] - rel["npg_estimate_2002_24_central_gbp_bn"], abs=1e-9)
    assert v["npg_producers_gain_2002_24_gbp_bn"] == pytest.approx(
        to_2024(run["non_power_gas"]["totals"]["2002-2024"]["producers_gain"] * 1e3, run) / 1e3, rel=1e-12)
    v25 = K.values(_with_2025p(run))
    r = to_2024(1.0, run)
    assert v25["npg_producers_gain_2025p_gbp_bn"] == pytest.approx(1.0 * r)


def test_working_carries_each_years_producers_gain_and_the_2025_row(run):
    from tools.figures_keys import non_power_gas as K
    w = K.values(_with_2025p(run))["table_npg_working"]
    for row in w["years"]:
        assert row["gross_gbp_bn"] - row["net_gbp_bn"] == pytest.approx(row["producers_gain_gbp_bn"], abs=1e-12)
    assert w["year_2025p"]["provisional"] is True and w["year_2025p"]["in_2002_24_totals"] is False
    assert w["year_2025p"]["net_gbp_bn"] == pytest.approx(K.values(_with_2025p(run))["npg_estimate_2025p_central_gbp_bn"])


def test_shao_method_uplift_2021_and_2023_beside_2022(run):
    from tools.figures_keys import worked_hh as W
    v = W.values(run)
    for y in ("2021", "2022", "2023"):
        k = f"shao_uplift_{y}_gbp_mwh"
        assert v[k] == run["fleet"][y]["moe"]["shao_mean_gbp_mwh"], k
        m = W.DECLARED[k]
        assert m["units"] == "£/MWh, cash" and m["basis"] == "modelled" and m["period"] == y, k
    assert v["shao_uplift_2021_gbp_mwh"] == pytest.approx(14.207147949990079, abs=1e-12)    # v4-s37 run file
    assert v["shao_uplift_2023_gbp_mwh"] == pytest.approx(16.115334694676545, abs=1e-12)
