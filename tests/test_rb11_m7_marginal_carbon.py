"""RB v1.1 M7 (decision 0163, R8 (a)): carbon taken out of the price at the marginal plant's intensity from
1 Jan 2009, at gas intensity before. Built as a switch, OFF by default (chief-executive, card [internal ticket],
21 Oct 2026: "Build (b) ... as a switch OFF by default, measure only, and measure (a) ... alongside it";
Richard rules which, if either, goes into the central case).

Switch: environment variable GASCF_M7_CARBON_MARGINAL
- "gas" (default, OFF): carbon out at gas intensity in every month, as v4-s37/v4-s38.
- "merit" (option b): from Jan 2009, the engine's merit order of the actual plant on the actual fossil load,
  with the month's carbon price added to each block; the top running block in each half-hour is the
  marginal plant; the month's coal share is the share of half-hours with coal on top.
- "neso_regression" (option a): from Jan 2009, each year's marginal emission factor from NESO's
  historic generation mix (change in fossil CO2 on change in fossil output, half-hour to half-hour), read as
  a coal weight between the gas and coal intensities.

Expected values are literals: HMRC's coal factor (0.3226 t CO2 per MWh of coal, the engine's own reading of
the CPS table), DESNZ's gas factor 0.18194, and hand-worked toy stacks and toy mixes.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ENV = "GASCF_M7_CARBON_MARGINAL"


def test_gas_setting_leaves_the_carbon_price_unchanged(monkeypatch):
    """v4-s39 (0167, M7 "A"; card [internal ticket]): the default is the merit order; 'gas' (v4-s38) is the explicit
    setting that leaves the carbon price as it was."""
    from gascf import bills as B, carbon
    from gascf import marginal_carbon as M
    monkeypatch.delenv(ENV, raising=False)
    assert M.method() == "merit"
    assert M.DEFAULT == "merit"
    monkeypatch.setenv(ENV, "gas")
    assert M.method() == "gas"
    B.c_marg.cache_clear()
    got = B.c_marg()
    want = carbon.c_marg_monthly(B.eta_ccgt(), B.YEARS)
    for k in ((2008, 6), (2009, 1), (2012, 7), (2024, 12)):
        assert got[k]["gbp_per_mwh"] == want[k]["gbp_per_mwh"]
    B.c_marg.cache_clear()


def test_unknown_method_is_refused(monkeypatch):
    from gascf import marginal_carbon as M
    monkeypatch.setenv(ENV, "coal")
    with pytest.raises(ValueError):
        M.method()


def test_break_date_is_1_jan_2009():
    from gascf import marginal_carbon as M
    assert M.MARGINAL_FROM == date(2009, 1, 1)


def test_blend_of_coal_and_gas_carbon_from_literals():
    """a = £10/t, no CPS (2010), coal 36% and gas 50% efficient, coal marginal a quarter of the time:
    coal 10 x 0.3226 / 0.36 = 8.9611; gas 10 x 0.18194 / 0.50 = 3.6388; blend 0.25 x 8.9611 + 0.75 x 3.6388."""
    from gascf import marginal_carbon as M
    v = M.blended_c_marg(10.0, date(2010, 6, 1), eta_coal=0.36, eta_gas=0.50, coal_share=0.25)
    assert v == pytest.approx(0.25 * 10 * 0.3226 / 0.36 + 0.75 * 10 * 0.18194 / 0.50, rel=2e-4)
    assert M.blended_c_marg(10.0, date(2010, 6, 1), 0.36, 0.50, 0.0) == pytest.approx(10 * 0.18194 / 0.50)


def test_regression_weight_on_toy_mixes():
    """Only coal moves: the marginal factor is coal's, weight 1. Only gas moves: weight 0.
    Coal moves 1 MW for every 3 MW of gas: weight 0.25."""
    from gascf import marginal_carbon as M
    ig, ic = 0.4, 0.9
    d = date(2010, 1, 1)
    coal_only = [((d, p), {"GAS": 5000.0, "COAL": 1000.0 + 100 * (p % 7)}) for p in range(1, 49)]
    gas_only = [((d, p), {"GAS": 5000.0 + 100 * (p % 7), "COAL": 1000.0}) for p in range(1, 49)]
    mixed = [((d, p), {"GAS": 5000.0 + 300 * (p % 7), "COAL": 1000.0 + 100 * (p % 7)}) for p in range(1, 49)]
    assert M.regression_coal_weight(dict(coal_only), ig, ic) == pytest.approx(1.0)
    assert M.regression_coal_weight(dict(gas_only), ig, ic) == pytest.approx(0.0, abs=1e-12)
    assert M.regression_coal_weight(dict(mixed), ig, ic) == pytest.approx(0.25)


def test_regression_uses_only_adjacent_half_hours():
    """A gap in the file (here a missing day) must not be read as a half-hour change."""
    from gascf import marginal_carbon as M
    ig, ic = 0.4, 0.9
    rows = {}
    for p in range(1, 49):
        rows[(date(2010, 1, 1), p)] = {"GAS": 5000.0 + 100 * (p % 5), "COAL": 1000.0}
        rows[(date(2010, 1, 3), p)] = {"GAS": 5000.0 + 100 * (p % 5), "COAL": 9000.0}
    assert M.regression_coal_weight(rows, ig, ic) == pytest.approx(0.0, abs=1e-12)


def test_merit_marginal_block_with_carbon_added():
    """Coal £30/MWh and CCGT £40/MWh before carbon; carbon adds £25 to coal and £10 to gas, so CCGT (50)
    runs before coal (55). 500 MW of load is met by CCGT (marginal gas); 1,500 MW reaches coal."""
    from gascf import marginal_carbon as M
    stack = [("coal", 1000.0, 30.0), ("ccgt", 1000.0, 40.0)]
    s = M.stack_with_carbon(stack, {"coal": 25.0, "ccgt": 10.0})
    assert [k for k, _, _ in s] == ["ccgt", "coal"]
    assert M.marginal_block(s, 500.0) == "ccgt"
    assert M.marginal_block(s, 1500.0) == "coal"
    assert M.marginal_block(s, 0.0) is None


def test_switch_moves_only_months_from_2009_and_raises_them(monkeypatch):
    """Both options leave 2002-08 at gas intensity to the penny; from Jan 2009 the carbon taken out is at least
    the gas value, and higher in 2009 (coal sat at the margin part of the time)."""
    from gascf import bills as B
    from gascf import marginal_carbon as M
    monkeypatch.setenv(ENV, "gas")      # v4-s38 = explicit setting (v4-s39 default is merit, 0167)
    B.c_marg.cache_clear()
    gas = {k: v["gbp_per_mwh"] for k, v in B.c_marg().items()}
    for meth in ("merit", "neso_regression"):
        monkeypatch.setenv(ENV, meth)
        B.c_marg.cache_clear()
        got = B.c_marg()
        for y in range(2002, 2009):
            for m in range(1, 13):
                assert got[(y, m)]["gbp_per_mwh"] == gas[(y, m)]
        assert sum(got[(2009, m)]["gbp_per_mwh"] for m in range(1, 13)) > \
            1.2 * sum(gas[(2009, m)] for m in range(1, 13))
        for k in got:
            if k >= (2009, 1):
                assert got[k]["gbp_per_mwh"] >= gas[k] - 1e-9
                assert 0.0 <= got[k]["coal_marginal_share"] <= 1.0
                assert got[k]["m7_method"] == meth
    monkeypatch.delenv(ENV, raising=False)
    B.c_marg.cache_clear()


def test_carbon_in_the_price_line_follows_the_switch(monkeypatch):
    """NZ1c (the carbon inside Reliable Britain's price, carved out of NZ1) must use the same carbon as the price
    the road is charged at: Σ months C(m) x V(m) with C from bills.c_marg, under the switch as under the default."""
    from gascf import bills as B
    V = B.v_monthly()
    for meth in ("gas", "merit"):
        monkeypatch.setenv(ENV, meth)
        B.c_marg.cache_clear()
        C = B.c_marg()
        got = B.nz1c_by_year()
        for y in (2008, 2010, 2015):
            want = sum(C[(y, m)]["gbp_per_mwh"] * V[(y, m)] for m in range(1, 13))
            assert got[y]["gbp_m"] == pytest.approx(want, rel=1e-12)
    monkeypatch.delenv(ENV, raising=False)
    B.c_marg.cache_clear()


def test_run_meta_names_method_and_break_date(monkeypatch):
    from gascf import marginal_carbon as M
    monkeypatch.setenv(ENV, "merit")
    meta = M.run_meta()
    assert meta["method"] == "merit"
    assert meta["marginal_from"] == "2009-01-01"
    assert set(meta["coal_marginal_share_by_year"]) == {str(y) for y in range(2009, 2026)}
    monkeypatch.delenv(ENV, raising=False)
    assert M.run_meta()["method"] == "merit"          # v4-s39 default (0167)
    monkeypatch.setenv(ENV, "gas")
    assert M.run_meta()["method"] == "gas"            # v4-s38 = explicit setting
