"""Ticket 38 (spec item non-power-gas-users.md D1-D6, tests 1-7): the extra cost to Britain's non-power gas users from
Reliable Britain's higher gas price, a labelled estimate beside the gap, never added to it.

Decisions: 0070 (Richard, 17 Oct 2026: labelled estimate, net of UK producers' gain, beside the gap, not added; editor
note: netted fully, gross shown beside it); 0099 (covers 2002-24, §9 and §16 only); 0033 (range from the
elasticities 0.34 / 0.16 / 0.06); 0108 item 1.9 option (a) (Richard Lyon, 19 Oct 2026: GB, scaled by DESNZ
sub-national gas); 0117 (build it before the v4-s36 cut).

Light tests on toy inputs, plus the two real-file readers (DUKES 2026 Table 4.1 balance as staged; DESNZ
sub-national Table 7.2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

YEARS = list(range(2002, 2025))


def _built(dq, q=4500.0):
    return {y: {"fleet": {"gas_feedback": {"dq_twh": dq(y), "q_twh": q, "elasticity": 0.16,
                                           "price_rise_frac": dq(y) / (0.16 * q)}}} for y in [*YEARS, 2025]}


def _inputs(v=500.0, s=400.0, d=800.0):
    return {y: {"v_np_twh": v, "uk_production_twh": s, "uk_demand_twh": d} for y in YEARS}


SHARES = {y: (0.985, "modelled") for y in YEARS}
PRICE = {y: 20.0 for y in YEARS}


def _block(dq=lambda y: 100.0 if y >= 2012 else 0.0, inputs=None, shares=None, price=None):
    from gascf import non_power_gas as N
    return N.block(_built(dq), inputs=inputs or _inputs(), shares=shares or SHARES, gas_price=price or PRICE)


# ------------------------------------------------------------------ the method (D1, D2, D4)

def test_formula_net_of_producers_on_the_gb_volume():
    """D1 and 0108 item 1.9 (a): gross = rise x P x V_np x GB share; net = gross x (1 - S_uk / D) (test 6)."""
    from gascf import bills as B
    b = _block()
    r = b["years"]["2020"]
    rise = 100.0 / (0.229 * 4500.0)                  # 0144 item 2A: e = 0.06 + 0.169 (was 0.16)
    gross_m = rise * 20.0 * 500.0 * 0.985          # TWh x £/MWh = £m
    assert r["gross_gbp_m_nominal"] == pytest.approx(gross_m, rel=1e-12)
    assert r["net_gbp_m_nominal"] == pytest.approx(gross_m * (1 - 400.0 / 800.0), rel=1e-12)
    assert r["net_gbp_m_nominal"] < r["gross_gbp_m_nominal"]
    assert r["net_gbp_bn_real"] == pytest.approx(B.real(r["net_gbp_m_nominal"], 2020) / 1e3, rel=1e-12)
    assert r["gross_gbp_bn_real"] == pytest.approx(B.real(gross_m, 2020) / 1e3, rel=1e-12)
    assert r["producers_gain_gbp_bn_real"] == pytest.approx(r["gross_gbp_bn_real"] - r["net_gbp_bn_real"],
                                                            rel=1e-12)
    assert r["inputs"] == {"v_np_twh": 500.0, "gb_share": 0.985, "gb_share_basis": "modelled",
                           "v_np_gb_twh": 500.0 * 0.985, "uk_production_twh": 400.0, "uk_demand_twh": 800.0,
                           "price_rise_frac": pytest.approx(rise, rel=1e-12), "gas_price_gbp_mwh": 20.0}


def test_range_order_and_one_over_e_scaling():
    """Test 4 (0033; 0144 item 2A): net(0.61, Krichene's pair) <= net(0.229, central), and their ratio is
    0.229 / 0.61 when dq > 0. v4-s36's supply-only ends (0.34 / 0.06) are gone with the supply-only formula."""
    b = _block()
    for y in map(str, YEARS):
        rg = b["years"][y]["range"]
        assert set(rg) == {"central", "krichene_lr"}
        assert rg["krichene_lr"] <= rg["central"], y
        assert rg["central"] == b["years"][y]["net_gbp_bn_real"]
        if b["years"][y]["inputs"]["price_rise_frac"] > 0:
            assert rg["krichene_lr"] / rg["central"] == pytest.approx(0.229 / 0.61, rel=1e-9)


def test_zero_when_there_is_no_feedback():
    """Test 5: in every year with dq = 0, net = gross = 0."""
    b = _block()
    for y in range(2002, 2012):
        r = b["years"][str(y)]
        assert r["net_gbp_bn_real"] == 0.0 and r["gross_gbp_bn_real"] == 0.0
        assert all(v == 0.0 for v in r["range"].values())


def test_labelled_estimate_with_method_range_and_print_sections():
    """Test 3 and 0099: basis estimated, label says estimate, method, three-point range; 2002-24 only;
    print_sections §9 and §16."""
    b = _block()
    assert sorted(b["years"]) == [str(y) for y in YEARS]          # no 2025 (0099)
    for r in b["years"].values():
        assert r["basis"] == "estimated" and "estimate" in r["label"] and r["method"]
        assert set(r["range"]) == {"central", "krichene_lr"}        # 0144: two points (was 0.34 / 0.16 / 0.06)
    assert b["basis"] == "estimated" and b["print_sections"] == ["§9", "§16"]
    assert b["in_gap"] is False
    assert "0108 item 1.9" in b["decisions"] and "0070" in b["decisions"] and "0099" in b["decisions"]
    tot = b["totals"]["2002-2024"]
    for k in ("central", "low", "gross", "producers_gain"):
        assert k in tot
    assert "high" not in tot                     # 0144: no sourced pair gives more feedback than the central
    assert tot["central"] == pytest.approx(sum(r["net_gbp_bn_real"] for r in b["years"].values()), rel=1e-12)
    assert tot["low"] == pytest.approx(sum(r["range"]["krichene_lr"] for r in b["years"].values()), rel=1e-12)


def test_gap_and_built_untouched():
    """Test 1: the block only reads the central build; nothing in it changes."""
    import copy
    from gascf import non_power_gas as N
    built = _built(lambda y: 50.0)
    before = copy.deepcopy(built)
    N.block(built, inputs=_inputs(), shares=SHARES, gas_price=PRICE)
    assert built == before


def test_source_guard_raises_before_output():
    """Test 7: an input missing for a year with dq > 0 raises PendingSourceError; a year with dq = 0 does not need it."""
    from gascf.pending import PendingSourceError
    inp = _inputs()
    inp[2015]["uk_production_twh"] = None
    with pytest.raises(PendingSourceError, match="2015"):
        _block(inputs=inp)
    inp = _inputs()
    del inp[2005]
    _block(inputs=inp)                      # 2005 has dq = 0
    sh = dict(SHARES)
    del sh[2013]
    with pytest.raises(PendingSourceError, match="2013"):
        _block(shares=sh)


# ------------------------------------------------------------------ the real inputs

def test_dukes_2026_inputs_read_from_the_staged_balance():
    """V_np = total demand less transformation: electricity generation (MPP + autogenerators); S_uk = production;
    D = total demand; DUKES 2026 Table 4.1 as staged (data/raw/s36/gas-demand), GWh / 1000. Literals are the
    CSV's 2002 cells F16, F18, F7 (published values, not engine output)."""
    from gascf import non_power_gas as N
    d = N.dukes_inputs()
    assert set(range(2002, 2025)) <= set(d)
    assert d[2002]["uk_demand_twh"] == pytest.approx(1112.93138, abs=1e-9)
    assert d[2002]["v_np_twh"] == pytest.approx(1112.93138 - 329.441, abs=1e-9)
    assert d[2002]["uk_production_twh"] == pytest.approx(1204.713, abs=1e-9)
    for y in range(2002, 2025):
        r = d[y]
        assert 0 < r["v_np_twh"] < r["uk_demand_twh"], y


def test_gb_gas_share_from_subnational_table_7_2():
    """DESNZ sub-national summary report 2024, Table 7.2 (gas, weather corrected): GB / (GB + NI). 2024 row:
    438,005 and 7,029 GWh (published values)."""
    from gascf import non_power_gas as N
    sh = N.read_gb_gas_share()
    assert sorted(sh) == list(range(2015, 2025))
    assert sh[2024] == pytest.approx(438005 / 445034, rel=1e-9)
    assert sh[2015] == pytest.approx(488387 / 494311, rel=1e-9)


def test_gb_share_outside_the_table_is_the_nearest_year_recorded_as_a_fallback():
    """The engine's existing rule for the GB share (system_costs.gb_share_of_uk, s30): nearest published year,
    tagged estimated. Here it is recorded in the fallback registry, never silent."""
    from gascf import fallbacks
    from gascf import non_power_gas as N
    assert "gb_gas_share_nearest_year" in fallbacks.DECLARED
    v, basis = N.gb_gas_share(2010)
    assert basis == "estimated" and v == N.read_gb_gas_share()[2015]
    assert any(r["name"] == "gb_gas_share_nearest_year" and r["year"] == 2010 for r in fallbacks.recorded())
    v, basis = N.gb_gas_share(2020)
    assert basis == "modelled"


# ------------------------------------------------------------------ run file and figures.json

def test_block_registered_and_keys_read_it_never_under_gap():
    from gascf import export_v4 as X
    from gascf.figures import to_2024
    assert "gascf.non_power_gas" in X.BLOCK_MODULES
    from tools import figures_keys
    from tools.figures_keys import non_power_gas as K
    assert "non_power_gas" in figures_keys.MODULES
    b = _block()
    run = {"meta": {"price_base": 2025, "deflator": "ONS CPIH L522"}, "non_power_gas": b}
    v = K.values(run)
    t = b["totals"]["2002-2024"]
    for key, part in (("central", "central"), ("low", "low"), ("gross", "gross")):          # 0144: no "high"
        assert v[f"npg_estimate_2002_24_{key}_gbp_bn"] == pytest.approx(to_2024(t[part] * 1e3, run) / 1e3,
                                                                       rel=1e-12)
    for k, meta in K.DECLARED.items():
        assert meta["basis"] == "estimated" and "estimate" in meta["label"].lower(), k
        # 0099 covers 2002-24; RB v1.1 A3 (0160) adds the 2025 keys and the working, printed under R21 (a) (0163)
        held = meta.get("ruling") == "R21 (a)" and meta["period"] in ("2025", "2002-2025")
        assert meta["print_sections"] == ["§9", "§16"] and (meta["period"] == "2002-2024" or held), k
        assert not k.startswith(("gap", "headline")), k
    assert K.values({"meta": run["meta"]})["npg_estimate_2002_24_central_gbp_bn"] is None


def test_no_other_figures_module_reads_the_estimate():
    """Test 2 (never summed into a headline): only tools/figures_keys/non_power_gas.py reads the run-file block."""
    root = Path(__file__).resolve().parents[1] / "tools/figures_keys"
    import re
    reads = re.compile(r"""run(\.get\(|\[)["']non_power_gas["']""")
    readers = sorted(p.name for p in root.glob("*.py") if reads.search(p.read_text()))
    assert readers == ["non_power_gas.py"]
