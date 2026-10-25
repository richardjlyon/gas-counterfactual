"""s36 ticket 10 (F1; 0029, 0031 items 1, 11, 18, 24; 0034): GO4's energy part at Reliable Britain's own
feedback-raised gas price. Formula tests only (fixture register under pytest); the acceptance bands
are release-step checks (35), never asserted here.

Seams: `balancing.go4(..., gas_uplift=)`, `bills.build` (GO4, GO7), `export_v4.gas_break_even`,
`clock_export.balancing_series(uplift)` / `uplift_from_run(run)`."""
import json
import math
import statistics
from pathlib import Path

import pytest

from gascf import balancing as b
from gascf import bills as B

ROOT = Path(__file__).parents[1]
YEARS = list(b.YEARS)
U = {y: 0.01 * (y - 2000) for y in YEARS}          # a made-up positive uplift, base window included


def test_go4_energy_part_scales_by_one_plus_uplift():
    """F1-1: energy part = no-uplift energy part x (1 + u[y]); services part identical."""
    base = b.go4(B.PRICE_BASE)
    up = b.go4(B.PRICE_BASE, gas_uplift=U)
    for y in YEARS:
        assert up[y]["energy_gbp_m"] == pytest.approx(base[y]["energy_gbp_m"] * (1 + U[y]), rel=1e-9), y
        assert up[y]["services_gbp_m"] == base[y]["services_gbp_m"]


@pytest.mark.parametrize("bad", [{**U, 2010: -1.0}, {**U, 2010: math.nan}, {**U, 2010: math.inf},
                                 {y: v for y, v in U.items() if y != 2010}],
                         ids=["minus_one", "nan", "inf", "missing"])
def test_go4_refuses_a_bad_uplift(bad):
    """F1-7: ValueError if uplift <= -1 (RB v1.1 M6, 0163 R7 (a): a negative uplift is allowed, the feedback works both
    ways; was < 0 to v4-s38), not finite, or a year missing (no silent zero)."""
    with pytest.raises(ValueError):
        b.go4(B.PRICE_BASE, gas_uplift=bad)


def test_go4_reports_actual_gas_energy_uplift_and_feedback():
    """A2 item 1: per-year fields energy_gbp_m_actual_gas (no-uplift value, net of the generators'
    share), gas_uplift_frac, gas_feedback_gbp_m = energy - actual-gas energy; the feedback source id
    only when an uplift is positive."""
    base = b.go4(B.PRICE_BASE)
    up = b.go4(B.PRICE_BASE, gas_uplift=U)
    for y in YEARS:
        assert up[y]["energy_gbp_m_actual_gas"] == pytest.approx(base[y]["energy_gbp_m"], rel=1e-12)
        assert up[y]["gas_uplift_frac"] == U[y]
        assert up[y]["gas_feedback_gbp_m"] == pytest.approx(U[y] * base[y]["energy_gbp_m"], rel=1e-9)
        assert base[y]["gas_feedback_gbp_m"] == 0.0
    assert "neuhoff-2022-eprg2212-gas-price-limits" in up[2025]["source_id"]
    assert "neuhoff-2022-eprg2212-gas-price-limits" not in base[2025]["source_id"]


def test_g0_is_the_actual_base_window_mean_and_base_window_uplift_allowed():
    """F1-7: g0 is never uplifted (B0 was measured at the actual price); a positive base-window
    uplift raises nothing and moves only those years' energy part."""
    up = b.go4(B.PRICE_BASE, gas_uplift={y: (0.5 if y == 2003 else 0.0) for y in YEARS})
    base = b.go4(B.PRICE_BASE)
    g = b.gas_annual()
    g0 = statistics.mean(g[y] for y in b.BASE_WINDOW)
    for y in YEARS:
        k = 1.5 if y == 2003 else 1.0
        assert up[y]["energy_gbp_m"] == pytest.approx(base[y]["energy_gbp_m"] * k, rel=1e-12)
        assert base[y]["energy_gbp_m"] / base[2002]["energy_gbp_m"] == pytest.approx(
            g[y] / g[2002] * (1 - base[y]["gen_share"]) / (1 - base[2002]["gen_share"]), rel=1e-12)
    assert g0 > 0


def test_lfl_args_is_the_only_constructor_of_fleet_lfl_arguments():
    """F1-10: every fleet_lfl call in bills.py takes its arguments from _lfl_args(s), so GO4's
    uplift is always the build's own."""
    import ast
    tree = ast.parse((ROOT / "src/gascf/bills.py").read_text())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "fleet_lfl"]
    assert len(calls) >= 2
    for c in calls:
        assert len(c.args) == 2 and isinstance(c.args[1], ast.Starred), ast.unparse(c)
        assert ast.unparse(c.args[1].value).startswith("_lfl_args("), ast.unparse(c)


def test_build_go4_moves_by_price_rise_times_actual_gas_energy_and_go7_follows():
    """F1-3 and GO7: in the central build GO4 - GO4(no uplift) = price_rise_frac x
    energy_gbp_m_actual_gas (to £0.01m), zero where price_rise_frac is 0; GO7 = 5% x domestic
    share x (GO1 + GO1k + GO2 + GO3 + GO4 + GO5), so it moves by 5% x d x dGO4, and its note
    names all six lines. Fixture register: the formula only, no bands (35)."""
    built = B.build()
    go4 = B.go4_line(B.CENTRAL)
    for y in YEARS:
        u = built[y]["fleet"]["gas_feedback"].get("price_rise_frac", 0.0)
        g = go4[y]
        assert g["gas_uplift_frac"] == u
        assert g["gas_feedback_gbp_m"] == pytest.approx(u * g["energy_gbp_m_actual_gas"], abs=0.01), y
        if u == 0:
            assert g["gas_feedback_gbp_m"] == 0.0
        assert B.val(built[y], "GO4") == pytest.approx(g["gbp_m"], rel=1e-12)
        assert B.line(built[y], "GO4")["gas_feedback_gbp_m"] == g["gas_feedback_gbp_m"]
        go7 = B.line(built[y], "GO7")
        assert "GO1 + GO1k + GO2 + GO3 + GO4 + GO5" in go7["years_note"]
        gv = {i: B.val(built[y], i) for i in ("GO1", "GO1k", "GO2", "GO3", "GO4", "GO5")}
        assert go7["national_gbp_m_nominal"] == pytest.approx(0.05 * go7["domestic_share"] * sum(gv.values()),
                                                              rel=1e-12)
    assert any(built[y]["fleet"]["gas_feedback"].get("price_rise_frac", 0.0) > 0 for y in YEARS)


def test_no_feedback_switch_gives_the_no_uplift_go4():
    """F1-5: gas_feedback='none' -> GO4 equals the no-uplift GO4 every year (the switch moves GO4)."""
    s = B.replace(B.CENTRAL, gas_feedback="none")
    go4 = B.go4_line(s)
    for y in YEARS:
        assert go4[y]["gas_feedback_gbp_m"] == 0.0
        assert go4[y]["gbp_m"] == pytest.approx(go4[y]["energy_gbp_m_actual_gas"] + go4[y]["services_gbp_m"])


def _synthetic_built(gap, f_go1=100.0, f_kept=50.0, f_at=30.0, f_go4=20.0, d=0.4, frac=0.1):
    out = {}
    for y in YEARS:
        out[y] = {"fleet": {"gas_feedback_gbp_m": f_go1, "gas_feedback_kept_gbp_m": f_kept,
                            "gas_feedback_at_cost_gbp_m": f_at,
                            "gas_feedback": {"price_rise_frac": frac, "dq_twh": 100.0, "q_twh": 5000.0,
                                             "elasticity": 0.16, "source_ids": []}},
                  "totals": {"gap_gbp_m": gap},
                  "fossil": [{"id": "GO4", "national_gbp_m_nominal": 500.0, "gas_feedback_gbp_m": f_go4},
                             {"id": "GO7", "national_gbp_m_nominal": 50.0, "domestic_share": d}],
                  "netzero": []}
    return out


def test_break_even_feedback_total_includes_go4_and_vat():
    """Item 11 (0031) and A2 item 3: F = (F_GO1 + F_GO1k + F_GO4) x (1 + 0.05 d); f* = f_c + gap f_c / F."""
    from gascf import export_v4 as E
    r = E.gas_break_even(_synthetic_built(gap=1000.0))["2025"]
    F = (100.0 + 50.0 + 30.0 + 20.0) * (1 + 0.05 * 0.4)
    assert r["feedback_central_gbp_m_nominal"] == pytest.approx(F, rel=1e-12)
    assert r["price_rise_frac"] == pytest.approx(0.1 + 1000.0 * 0.1 / F, rel=1e-12)
    assert not [g for g in E.GAPS if "VAT on the feedback" in g]


S35_RUN = json.loads((ROOT / "out/v4/2026-10-14-s35.json").read_text())


def test_clock_balancing_needs_an_uplift_and_reads_it_from_the_run():
    """R-3: balancing_series() with no argument is a TypeError, None a ValueError; uplift_from_run
    reads every engine year's price_rise_frac from the run file and refuses a missing, non-finite
    or a fall of all of the price or more (RB v1.1 M6, 0163 R7 (a): a negative rise is allowed; was any negative to
    v4-s38)."""
    from gascf import clock_export as ce
    with pytest.raises(TypeError):
        ce.balancing_series()
    with pytest.raises(ValueError):
        ce.balancing_series(None)
    u = ce.uplift_from_run(S35_RUN)
    assert set(u) == set(YEARS)
    assert u[2025] == S35_RUN["fleet"]["2025"]["gas_feedback"]["price_rise_frac"]
    for bad in (None, -1.0, math.nan):
        run = json.loads(json.dumps(S35_RUN))
        run["fleet"]["2020"]["gas_feedback"]["price_rise_frac"] = bad
        with pytest.raises(ValueError):
            ce.uplift_from_run(run)
    run = json.loads(json.dumps(S35_RUN))
    del run["fleet"]["2020"]["gas_feedback"]
    with pytest.raises(ValueError):
        ce.uplift_from_run(run)


def test_clock_balancing_moves_by_exactly_the_uplift_on_the_included_energy_part():
    """Clock export: central balancing = no-uplift central + u(y) x energy part (generators' share
    included), to £0.01; the block carries the uplift it used; grid is not touched."""
    from gascf import clock_export as ce
    u = ce.uplift_from_run(S35_RUN)
    zero = ce.balancing_series({y: 0.0 for y in YEARS})
    up = ce.balancing_series(u)
    for y in YEARS:
        z, r = zero["years"][str(y)], up["years"][str(y)]
        assert r["central_gbp"] - z["central_gbp"] == pytest.approx(u[y] * z["energy_part_gbp"], abs=0.02), y
        assert r["services_part_gbp"] == z["services_part_gbp"]
    assert up["gas_uplift"]["price_rise_frac"] == {str(y): u[y] for y in YEARS}
    assert "run file" in up["gas_uplift"]["rule"] and "run file" in up["method"]
