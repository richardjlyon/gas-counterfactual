"""RB v1.1 M6 (decision 0163, R7 (a), Richard Lyon 21 Oct 2026: "Agree. Next."): the gas-price feedback works
both ways. Fossil Britain's extra gas burn for power, dQ = its burn less the actual burn (DUKES 5.6.A, major power
producers), is no longer floored at zero: where fossil Britain burns less gas than the real system did, its gas
price is lower, by the same formula dQ / ((e_s + e_d) Q). The §9.8 other-gas-users estimate (`non_power_gas`) and
the balancing gas index (GO4) follow the same signed fraction.

Expected values come from the formula's own literals (Albrizio's pair 0.06 + 0.169, decision 0144 item 2A) and the
DUKES 5.6.A actual burn, never from the engine's output divided by itself."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gascf import fossil_like_for_like as L  # noqa: E402

E_CENTRAL = 0.06 + 0.169


def test_dq_is_not_floored_where_fossil_britain_burns_less_gas():
    """2016: fossil Britain burns less gas for power than the actual system (DUKES 5.6.A). Under R7 (a) dQ is the
    signed difference and the price-rise fraction is negative (gas cheaper), at the central pair."""
    y = L.lfl_year(2016)
    c = L.gas_feedback(y, "central")
    signed = c["fossil_power_gas_twh"] - c["actual_power_gas_twh"]
    assert signed < 0, "precondition: the fixture road burns less gas than the actual system in 2016"
    assert c["dq_twh"] == pytest.approx(signed, abs=1e-9)
    assert c["price_rise_frac"] == pytest.approx(signed / (E_CENTRAL * c["q_twh"]), rel=1e-12)
    assert c["price_rise_frac"] < 0
    assert c["market_gbp_m"] < 0                       # market-priced MWh are cheaper, not floored


def test_none_rule_still_gives_zero_feedback():
    y = L.lfl_year(2016)
    g = L.gas_feedback(y, "none")
    assert g["price_rise_frac"] == 0.0 and g["at_cost_gbp_m"] == g["market_gbp_m"] == g["kept_gbp_m"] == 0.0


def test_other_gas_users_gain_in_a_year_with_negative_dq():
    """§9.8 follows M6: in a year with dQ < 0 the non-power gas users pay less. gross = rise x P x V_np x GB share,
    net = gross x (1 - S_uk / D), both negative; Krichene's pair gives the smaller move in the same direction."""
    from gascf import bills as B
    from gascf import non_power_gas as N
    q, dq = 4500.0, -20.0
    built = {y: {"fleet": {"gas_feedback": {"dq_twh": (dq if y == 2016 else 0.0), "q_twh": q, "elasticity": E_CENTRAL,
                                            "price_rise_frac": (dq if y == 2016 else 0.0) / (E_CENTRAL * q)}}}
             for y in [*range(2002, 2025), 2025]}
    inputs = {y: {"v_np_twh": 500.0, "uk_production_twh": 400.0, "uk_demand_twh": 800.0} for y in range(2002, 2025)}
    b = N.block(built, inputs=inputs, shares={y: (0.985, "modelled") for y in range(2002, 2025)},
                gas_price={y: 20.0 for y in range(2002, 2025)})
    r = b["years"]["2016"]
    gross_m = dq / (E_CENTRAL * q) * 20.0 * 500.0 * 0.985
    assert gross_m < 0
    assert r["gross_gbp_m_nominal"] == pytest.approx(gross_m, rel=1e-12)
    assert r["net_gbp_m_nominal"] == pytest.approx(gross_m * (1 - 400.0 / 800.0), rel=1e-12)
    assert r["range"]["krichene_lr"] == pytest.approx(r["range"]["central"] * E_CENTRAL / 0.61, rel=1e-9)
    assert b["totals"]["2002-2024"]["central"] == pytest.approx(B.real(gross_m * 0.5, 2016) / 1e3, rel=1e-12)


def test_other_gas_users_reads_its_inputs_in_a_negative_year():
    """No silent zero: a year with dQ < 0 needs the same inputs as a year with dQ > 0 and stops if one is missing."""
    from gascf import non_power_gas as N
    built = {y: {"fleet": {"gas_feedback": {"dq_twh": -5.0, "q_twh": 4500.0, "elasticity": E_CENTRAL,
                                            "price_rise_frac": -5.0 / (E_CENTRAL * 4500.0)}}}
             for y in [*range(2002, 2025), 2025]}
    with pytest.raises(N.PendingSourceError):
        N.block(built, inputs={y: {"v_np_twh": None, "uk_production_twh": 1.0, "uk_demand_twh": 2.0}
                               for y in range(2002, 2025)},
                shares={y: (0.985, "modelled") for y in range(2002, 2025)}, gas_price={y: 20.0 for y in range(2002, 2025)})


def test_go4_accepts_a_negative_gas_uplift():
    """GO4's gas-indexed energy part moves by the signed fraction: feedback = u x energy at the actual gas price."""
    from gascf import balancing as b
    from gascf import bills as B
    years = list(B.YEARS)
    base = b.go4(B.PRICE_BASE)
    u = {y: (-0.02 if y == 2016 else 0.0) for y in years}
    down = b.go4(B.PRICE_BASE, gas_uplift=u)
    assert down[2016]["gas_feedback_gbp_m"] == pytest.approx(-0.02 * base[2016]["energy_gbp_m"], rel=1e-9)
    assert down[2016]["gas_feedback_gbp_m"] < 0
    with pytest.raises(ValueError):                          # a price cannot fall by all of itself or more
        b.go4(B.PRICE_BASE, gas_uplift={**u, 2016: -1.0})
    with pytest.raises(ValueError):
        b.go4(B.PRICE_BASE, gas_uplift={**u, 2016: math.nan})


def test_clock_export_reads_a_negative_rise_from_the_run_file():
    from gascf import bills as B
    from gascf import clock_export as CE
    run = {"fleet": {str(y): {"gas_feedback": {"price_rise_frac": (-0.003 if y == 2016 else 0.01)}} for y in B.YEARS}}
    assert CE.uplift_from_run(run)[2016] == -0.003
    run["fleet"]["2016"]["gas_feedback"]["price_rise_frac"] = math.inf
    with pytest.raises(ValueError):
        CE.uplift_from_run(run)


def test_v4_s38_floored_reading_is_an_explicit_setting(monkeypatch):
    """Card [internal ticket]: M6 both ways is the default (0163); the floored dQ of v4-s37/v4-s38 stays reachable as an
    explicit setting ($GASCF_M6_FEEDBACK=floored), for the guards that reproduce frozen releases before v4-s39."""
    assert L.M6_DEFAULT == "both" and L.M6_OPTIONS == ("both", "floored")
    y = L.lfl_year(2016)
    monkeypatch.setenv(L.M6_ENV, "floored")
    c = L.gas_feedback(y, "central")
    assert c["fossil_power_gas_twh"] - c["actual_power_gas_twh"] < 0
    assert c["dq_twh"] == 0.0 and c["price_rise_frac"] == 0.0
    monkeypatch.setenv(L.M6_ENV, "sideways")
    with pytest.raises(ValueError):
        L.gas_feedback(y, "central")
    monkeypatch.delenv(L.M6_ENV)
    assert L.gas_feedback(y, "central")["dq_twh"] < 0
