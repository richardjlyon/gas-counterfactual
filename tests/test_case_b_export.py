"""Ticket 22 (spec item case-b-gas-export.md D1-D3; decisions 0029, 0034, 0048, 0095; Richard Lyon, decision 0117,
19 Oct 2026: build it before the v4-s36 cut). Case B is exported as plain second runs with B's settings, never a
switchable block: three `build()` calls with `Settings` replacements, written to run-file block
`sensitivities_case_b[case][y]`. B's failed sign check is recorded openly and never stops the release (0034).
Case B never enters the printed range (0095; tested in test_range_0095.py).

These tests use toy builds (no engine run). The one-off v4-s35 regression (spec test 3) is a measurement, recorded
in the commit and the pull request body, not a test that can run on s36 code."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from gascf import bills as B

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _toy(dq_by_year, q=4680.386, e=0.16, gap=lambda y: 1.0, actual=100.0):
    """A built-like dict: fleet[y].gas_feedback as fossil_like_for_like.gas_feedback returns it (dq floored at 0)."""
    out = {}
    for y in B.YEARS:
        raw = dq_by_year(y)
        dq = max(0.0, raw)
        out[y] = {"fleet": {"gas_feedback": {
            "rule": "x", "elasticity": e, "dq_twh": dq, "q_twh": q, "price_rise_frac": dq / (e * q),
            "actual_power_gas_twh": actual, "fossil_power_gas_twh": actual + raw}},
            "totals": {"gap_real_bn": gap(y)}}
    return out


def _builds(central, cases):
    def build(s):
        for name, settings in __import__("gascf.case_b", fromlist=["CASES"]).CASES.items():
            if s == settings:
                return cases[name]
        raise AssertionError(f"unexpected settings {s}")
    return build


def test_cases_are_the_three_named_settings_replacements():
    from gascf import case_b as CB
    assert CB.CASES == {
        "closures_actual": replace(B.CENTRAL, closures="actual"),
        "closures_actual_e006": replace(B.CENTRAL, closures="actual", gas_feedback="high"),
        "case_b_all_three": replace(B.CENTRAL, closures="actual", gas_feedback="high", kept_price="actual"),
    }
    from gascf.fossil_like_for_like import GAS_ELASTICITY
    # v4-s37 (0144 item 2A): case B's code is left as it is (research-director, card [internal ticket]; what its "0.06"
    # means under the paired formula is open, 0144 note 2). 'high' still holds 0.06 with no demand side; the
    # central is now 0.06 + 0.169 = 0.229 (was 0.16), so case_b.E_CENTRAL and the rise_at_e016 field follow it.
    assert GAS_ELASTICITY["high"] == 0.06 and GAS_ELASTICITY["central"] == pytest.approx(0.229)


def test_block_fields_and_rise_arithmetic_every_case_and_year():
    from gascf import case_b as CB
    central = _toy(lambda y: 134.558 if y == 2025 else 0.0)
    cases = {"closures_actual": _toy(lambda y: 264.7 if y >= 2012 else -5.0),
             "closures_actual_e006": _toy(lambda y: 264.7 if y >= 2012 else 0.0, e=0.06),
             "case_b_all_three": _toy(lambda y: 250.0 if y >= 2012 else 0.0, e=0.06)}
    blk = CB.block(central, build=_builds(central, cases))
    assert set(blk["cases"]) == {"central", *CB.CASES}
    for name, run in {"central": central, **cases}.items():
        for y in B.YEARS:
            row, g = blk["cases"][name][str(y)], run[y]["fleet"]["gas_feedback"]
            # the engine's dq is floored at 0 (fossil_like_for_like.gas_feedback, s27c), so test 1 reads max(0, .)
            assert row["dq_twh"] == pytest.approx(max(0.0, g["fossil_power_gas_twh"] - g["actual_power_gas_twh"]),
                                                  abs=1e-9)
            # 0144: the field named e016 now holds the rise at the engine's central e (0.229); name kept, case B open
            assert row["rise_at_e016"] == pytest.approx(row["dq_twh"] / (0.229 * row["q_twh"]), abs=1e-12)
            assert row["rise_at_e006"] == pytest.approx(row["dq_twh"] / (0.06 * row["q_twh"]), abs=1e-12)
            assert row["gap_real_bn"] == run[y]["totals"]["gap_real_bn"]
            for f in ("q_twh", "elasticity", "price_rise_frac"):
                assert row[f] == g[f]
    # the paper's quoted figures, by the probe's own arithmetic (spec test 3's numbers on toy inputs)
    r25 = blk["cases"]["closures_actual"]["2025"]
    assert r25["dq_twh"] == 264.7
    assert r25["rise_at_e016"] == pytest.approx(0.2470, abs=5e-4)       # v4-s36 at 0.16: 0.3535
    assert r25["rise_at_e006"] == pytest.approx(0.9426, abs=5e-4)
    # central 2025: dq 134.558, q 4,680.386 (v4-s35 run file, spec test 2): rise 0.12554 at 0.229 (0.17968 at 0.16)
    assert blk["cases"]["central"]["2025"]["rise_at_e016"] == pytest.approx(0.12554, abs=5e-6)


def test_engine_rise_must_equal_the_arithmetic_at_its_own_elasticity():
    """Spec test 2: the engine's price_rise_frac at the matching elasticity equals dq / (e q) to 1e-9. A case whose
    engine rise disagrees stops the block (a wrong elasticity reaching the case would otherwise pass silently)."""
    from gascf import case_b as CB
    central = _toy(lambda y: 10.0)
    bad = _toy(lambda y: 10.0, e=0.06)
    bad[2020]["fleet"]["gas_feedback"]["price_rise_frac"] *= 1.01
    cases = {"closures_actual": _toy(lambda y: 10.0), "closures_actual_e006": bad,
             "case_b_all_three": _toy(lambda y: 10.0, e=0.06)}
    with pytest.raises(ValueError, match="closures_actual_e006.*2020"):
        CB.block(central, build=_builds(central, cases))


def test_sign_check_lists_every_negative_year_and_never_raises():
    """0034: B's failed sign check is recorded openly and does not block the release."""
    from gascf import case_b as CB
    neg = {2003, 2009, 2025}
    central = _toy(lambda y: 0.0)
    cases = {n: _toy(lambda y: 0.0, gap=lambda y: -0.5 if y in neg else 0.5) for n in CB.CASES}
    blk = CB.block(central, build=_builds(central, cases))
    for n in CB.CASES:
        sc = blk["sign_check"][n]
        assert sc == {"passed": False, "negative_years": sorted(neg)}
    ok = {n: _toy(lambda y: 0.0) for n in CB.CASES}
    assert CB.block(central, build=_builds(central, ok))["sign_check"]["case_b_all_three"] == \
        {"passed": True, "negative_years": []}


def test_case_b_rejection_text_exact():
    """Editor-in-chief ruling, 17 Oct 2026, 16:18 (ticket 22, supersedes the earlier wordings)."""
    from gascf import case_b as CB
    assert CB.REJECTION == ("Rejected as the central case: 0.06 is a short-run supply elasticity (Krichene 2005, "
                            "Table 5, used by Albrizio et al. over a 12-month horizon) applied to two decades of "
                            "extra demand.")
    for bad in ("no new investment", "supply response", "North Sea", "shale", "moratorium", "\u2014"):
        assert bad not in CB.REJECTION
    central = _toy(lambda y: 0.0)
    blk = CB.block(central, build=_builds(central, {n: _toy(lambda y: 0.0) for n in CB.CASES}))
    assert blk["rejection"] == CB.REJECTION
    assert blk["decisions"] == ["0029", "0034", "0048", "0095", "0117"]
    assert blk["in_range"] is False


def test_block_registered_and_keys_read_it():
    from gascf import case_b as CB
    from gascf import export_v4 as X
    from gascf.figures import to_2024
    assert "gascf.case_b" in X.BLOCK_MODULES
    from tools import figures_keys
    from tools.figures_keys import case_b as K
    assert "case_b" in figures_keys.MODULES
    central = _toy(lambda y: 134.558 if y == 2025 else 0.0)
    cases = {"closures_actual": _toy(lambda y: 264.7, gap=lambda y: 2.0),
             "closures_actual_e006": _toy(lambda y: 264.7, e=0.06, gap=lambda y: 3.0),
             "case_b_all_three": _toy(lambda y: 250.0, e=0.06, gap=lambda y: -1.0 if y == 2004 else 0.25)}
    blk = CB.block(central, build=_builds(central, cases))
    run = {"meta": {"price_base": 2025, "deflator": "ONS CPIH L522"}, "sensitivities_case_b": blk}
    v = K.values(run)
    want = to_2024(sum(-1.0 if y == 2004 else 0.25 for y in range(2002, 2025)) * 1e3, run) / 1e3
    assert v["case_b_2002_24_gbp_bn"] == pytest.approx(want, rel=1e-12)
    assert v["case_b_2025p_gbp_bn"] == pytest.approx(to_2024(250.0, run) / 1e3, rel=1e-12)
    assert v["case_b_extra_gas_twh_2025p"]["closures_actual"] == 264.7
    assert v["case_b_extra_gas_twh_2025p"]["case_b_all_three"] == 250.0
    assert v["case_b_gas_rise_e016_2025p_pct"]["closures_actual"] == pytest.approx(
        100 * 264.7 / (0.229 * 4680.386), rel=1e-12)
    assert v["case_b_gas_rise_e006_2025p_pct"]["closures_actual"] == pytest.approx(
        100 * 264.7 / (0.06 * 4680.386), rel=1e-12)
    assert v["case_b_negative_years"] == [2004]
    for k, meta in K.DECLARED.items():
        assert meta["reason"] == CB.REJECTION and meta["in_range"] is False, k
    assert K.DECLARED["case_b_2025p_gbp_bn"]["provisional"] is True
    assert K.values({"meta": run["meta"]})["case_b_2002_24_gbp_bn"] is None
