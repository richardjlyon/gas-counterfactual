"""Card [internal ticket], sweep-flags row 6 (0175 items 2 and 9; 0177): the life-extension method check (R6 (a), R33: CEPA/GHD
2025 £81/kW per five years on kept coal) prints a change of exactly 0.0 on v4-s40. Show why, from the run file.

- The run file carries kept coal's pay by year (fleet[y].kept_coal_pay: fixed cost, the road margin after the
  generators' charge, the life-extension cost and what is paid). Before this card nothing in the run file showed
  item 2's result.
- In every year with kept coal, the road margin covers kept coal's fixed cost AND the borrowed life-extension cost, so
  max(0, fixed + life - margin) is nil with or without the row: the 0.0 comes from the nil floor, not from the row
  failing to run. If a later change lifts any year off the floor, this test fails and the 0.0 must be re-read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import bills as B  # noqa: E402
from gascf import export_v4 as X  # noqa: E402
from gascf import life_extension as LE  # noqa: E402


def _run_path() -> Path:
    hits = [q for q in sorted((ROOT / "out/v4").glob("*.json"))
            if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    assert hits, f"no out/v4 file written by engine {X.ENGINE_VERSION}: export before testing"
    return hits[-1]


@pytest.fixture(scope="module")
def run():
    return json.loads(_run_path().read_text())


def test_fleet_export_carries_kept_coal_pay():
    built = {y: {"fleet": {"coal_gw": 1.0, "kept_coal_pay": {"paid_gbp_m": 0.0}}} for y in B.YEARS}
    assert X._fleet(built)["2019"]["kept_coal_pay"] == {"paid_gbp_m": 0.0}


def test_run_file_has_kept_coal_pay_every_year(run):
    for y in map(str, B.YEARS):
        k = run["fleet"][y]["kept_coal_pay"]
        assert {"rule", "coal_mw", "coal_fixed_gbp_m", "paid_gbp_m", "life_ext"} <= set(k), y
        assert k["rule"] == run["meta"]["central_settings"]["kept_coal_pay"] and k["life_ext"] == "none", y


def test_life_extension_zero_comes_from_the_nil_floor(run):
    kept = [y for y in map(str, B.YEARS) if run["fleet"][y]["kept_coal_pay"]["coal_mw"] > 0]
    assert kept, "no year with kept coal: the check would be 0.0 for another reason"
    for y in kept:
        k = run["fleet"][y]["kept_coal_pay"]
        life = LE.gbp_kw_yr("borrowed_gas", int(y)) * k["coal_mw"] / 1e3
        assert life > 0, y
        assert k["margin_basis"] == "road", y
        assert k["paid_gbp_m"] == 0.0, (y, k["paid_gbp_m"])
        assert k["margin_gbp_m"] >= k["coal_fixed_gbp_m"] + life, (y, k["margin_gbp_m"], k["coal_fixed_gbp_m"], life)
    from tools.figures_keys import method_checks as M
    assert M.values(run)["check_r6a_kept_coal_life_extension_2002_24_change_gbp_bn"] == 0.0
