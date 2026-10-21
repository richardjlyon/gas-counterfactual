"""Decision 0122 (Richard Lyon, 19 Oct 2026: fill v4-s36's gaps and re-cut), card item 3 and item 2's
`rpi_x_effect_2002_24_gbp_bn`.

The v4-s36 cut at f82e9f9 wrote `sens_grid_rpi_x_2002_24_gbp_bn` = 162.71 in the run's own money (2025 £) while every
other headline key is in 2024 £; read in 2025 £ it looked as if RPI-X raised the gap (161.28 central, 2024 £). The
one-at-a-time table row for the same option gives 156.70 (2024 £), 4.58 below central. These tests pin the key to the
table row (same level, same price base) and add the signed effect.

Expected values: the released v4-s36 run file (pre-cut bytes, sha256 30d0571e...), central 2002-24 headline
161.275 (2024 £, decision 0119), the one-at-a-time rpi_x row 156.699 (2024 £)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import deflator_cpih  # noqa: E402
from tools import figures as F  # noqa: E402
from tools.figures_keys import grid as G  # noqa: E402
from tools.figures_keys import range as R  # noqa: E402

S36 = ROOT / "out/v4/2026-10-20-s36.json"
Y02_24 = [str(y) for y in range(2002, 2025)]


@pytest.fixture(scope="module")
def run():
    return json.loads(S36.read_text())


def test_published_headline_reproduced_first(run):
    """Reproduce the cut's figures to the penny before testing anything: £161.207bn 2002-24 and £549.54 a household
    in 2025 (provisional), both 2024 £, re-cut 2 under decision 0133 (margin on the 2027/28 peak). The 0122 cut at
    2fea228 gave £161.275bn and £549.66 (decision 0119's figures); 0133 is the only move between them."""
    from tools.figures_keys import core
    v = core.values(run)
    print(f"\nREPRODUCED v4-s36 headline 2002-24 £{v['headline_2002_24_gbp_bn']:.3f}bn; "
          f"2025p £{v['cost_per_household_2025p_gbp']:.2f} a household (2024 £)")
    assert round(v["headline_2002_24_gbp_bn"], 3) == 161.207
    assert round(v["cost_per_household_2025p_gbp"], 2) == 549.54


def test_sens_grid_rpi_x_is_the_table_row_in_2024_prices(run):
    v = G.values(run)["sens_grid_rpi_x_2002_24_gbp_bn"]
    row = [r for r in R.table(run) if r["switch"] == G.RPI_X_ROW]
    assert len(row) == 1
    assert v == pytest.approx(row[0]["headline_2002_24_gbp_bn"], rel=1e-12)
    assert round(v, 3) == 156.631          # 156.699 at the 0122 cut; the 0133 margin moves it with central
    meta = G.DECLARED["sens_grid_rpi_x_2002_24_gbp_bn"]
    assert meta["price_base"] == "2024 £ (CPIH L522)" and meta["units"] == "£bn, 2024 prices"
    assert "2025" not in json.dumps(meta)


def test_rpi_x_effect_is_switch_row_less_central_and_negative(run):
    from tools.figures_keys import core
    v = G.values(run)
    central = core.values(run)["headline_2002_24_gbp_bn"]
    assert v["rpi_x_effect_2002_24_gbp_bn"] == pytest.approx(v["sens_grid_rpi_x_2002_24_gbp_bn"] - central, abs=1e-12)
    assert v["rpi_x_effect_2002_24_gbp_bn"] < 0
    assert round(v["rpi_x_effect_2002_24_gbp_bn"], 3) == -4.577
    row = [r for r in R.table(run) if r["switch"] == G.RPI_X_ROW][0]
    assert v["rpi_x_effect_2002_24_gbp_bn"] == pytest.approx(row["change_gbp_bn"], abs=1e-12)


def test_scot_share_alt_keys_are_in_2024_prices_as_labelled(run):
    c = deflator_cpih.cpih()
    v = G.values(run)
    assert v["scot_share_alt_gap_effect_2002_05_gbp_m"] == pytest.approx(
        run["scot_share_alt"]["gap_effect_2002_05_gbp_m"] * c[2024] / c[2025], rel=1e-12)
    assert v["scot_share_alt_level_shift_gbp_m"] == pytest.approx(
        run["scot_share_alt"]["level_shift_gbp_m"] * c[2024] / c[2025], rel=1e-12)
    for k in ("scot_share_alt_gap_effect_2002_05_gbp_m", "scot_share_alt_level_shift_gbp_m"):
        assert G.DECLARED[k]["units"] == "£m, 2024 prices"


def test_no_grid_key_is_left_in_the_run_price_base():
    for k, m in G.DECLARED.items():
        assert "run price base" not in json.dumps(m), k


def test_renewal_high_equals_central_by_construction_and_the_switch_is_wired(run):
    """Card item 4: renewal=high gives exactly central because grid.renewal_allowance sets high = central (v4-s35 T4,
    Richard 14 Oct 2026: central counts the whole allowance above the 2002-05 level, low = 0). The switch is wired:
    the low option moves the headline by GO5's whole renewal allowance."""
    from gascf import grid
    r = grid.renewal_allowance()
    assert all(r[y]["high"] == r[y]["central"] for y in r)
    assert any(r[y]["low"] != r[y]["central"] for y in r)
    t = {r_["settings"].get("renewal"): r_ for r_ in R.table(run) if r_["switch"] == "grid renewal R (low / high)"}
    assert t["high"]["change_gbp_bn"] == pytest.approx(0.0, abs=1e-9)
    assert t["low"]["change_gbp_bn"] > 1.0
    lab = R.DECLARED["sens_grid_base_high_2002_24_gbp_bn"]["label"].lower()
    assert "equals central" in lab and "higher base" not in lab


def test_new_grid_keys_go_through_the_release_gate(run):
    keys = F.generate(run, modules=[G])["keys"]
    assert set(keys) == set(G.DECLARED)
    F.assert_complete({"keys": keys})
