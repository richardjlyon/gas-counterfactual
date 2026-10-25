"""Card [internal ticket] (measure only; Richard has not ruled): the IED law on EXISTING coal from 1 July 2020.

West Burton A and Drax units 5-6 are existing plant (in DUKES 5.7.A, so in the engine's coal block) from 1 July
2020 until each closes in reality (31 Mar 2023, 30 Apr 2023), after which the road keeps them. Their EA permits
(condition 2.3.6) held them to under 1,500 hours a year (5-year rolling average; at most 2,250 in any one year),
because neither had SCR. Two lawful fixes, each a suffix on the coal_lf rule, OFF by default:
  "+ex_cap_<hours>": (a) the two stations are held to the hours cap while existing (hours 1500 or 2250);
  "+ex_scr":         (b) the two stations are charged SCR while existing (no hours cap), costed as kept SCR is.
The suffix goes on "dukes_max" (fix alone) or on a kept-coal rule "dukes_max+ied_<reading>_<hours>" (combined).

Basis: the engine's coal block counts a station as existing in a year if it is in DUKES's end-of-year capacity,
i.e. every year before its closure year (West Burton A and Drax 5-6: 2020, 2021, 2022; not 2023). From 1 July
2020: 2020 share 184/366. Expected values are literals from the closure register's MW (2,000 and 1,320), these
dates and the permits' hours.
"""
import pytest

from gascf import fossil_like_for_like as L

CAP = "dukes_max+ex_cap_1500"
CAP_2250 = "dukes_max+ex_cap_2250"
SCR = "dukes_max+ex_scr"
B_CAP = "dukes_max+ied_permits_1500+ex_cap_1500"
B_SCR = "dukes_max+ied_permits_1500+ex_scr"
REG = str(L.CLOSURES_FILE)
UNITS = [("Drax", 1320.0), ("West Burton A", 2000.0)]


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    monkeypatch.setenv(L.CLOSURES_ENV, REG)


def test_rules_named_off_by_default_and_block_cap_kept():
    assert L.DEFAULT_COAL_LF == "dukes_max"
    for r in (CAP, CAP_2250, SCR, B_CAP, B_SCR, "dukes_max+ied_route_2250+ex_cap_2250"):
        assert r in L.COAL_LF_RULES
        assert L.coal_lf_cap(r) == L.coal_lf_cap("dukes_max")
    for bad in ("dukes_max+ex_cap_999", "dukes_max+ex_scr+ex_cap_1500", "none+ex_scr"):
        with pytest.raises(ValueError):
            L.coal_lf_cap(bad)
    assert L.existing_ied_units(2021, "dukes_max") == []
    assert L.existing_ied_units(2021, "dukes_max+ied_permits_1500") == []


def test_existing_units_and_shares():
    u = L.existing_ied_units(2021, CAP)
    assert sorted((s, mw) for s, _, mw, _, _ in u) == UNITS
    assert all(sh == pytest.approx(1.0) and h == 1500.0 for *_, sh, h in u)
    assert all(sh == pytest.approx(1.0) for *_, sh, _ in L.existing_ied_units(2022, CAP))
    assert all(sh == pytest.approx(184 / 366) for *_, sh, _ in L.existing_ied_units(2020, CAP))
    assert all(h == 2250.0 for *_, h in L.existing_ied_units(2021, CAP_2250))
    for y in (2019, 2023, 2024):                      # before the cap; closure year onwards: not existing
        assert L.existing_ied_units(y, CAP) == []
    # SCR: the same units and shares; no hours
    s = L.existing_ied_units(2020, SCR)
    assert sorted((st, mw) for st, _, mw, _, _ in s) == UNITS
    assert all(sh == pytest.approx(184 / 366) and h is None for *_, sh, h in s)


def test_cap_limit_2021_and_2020():
    cap = L.coal_lf_cap("dukes_max")
    want = cap * (7850.0 - 3320.0) * 8760.0 + 3320.0 * 1500.0
    assert L.coal_energy_limit_mwh(2021, 7850.0, 8760.0, CAP) == pytest.approx(want)
    want = cap * (7850.0 - 3320.0) * 8760.0 + 3320.0 * 2250.0
    assert L.coal_energy_limit_mwh(2021, 7850.0, 8760.0, CAP_2250) == pytest.approx(want)
    eq = 3320.0 * 184 / 366
    want = cap * (8000.0 - eq) * 8784.0 + 1500.0 * eq
    assert L.coal_energy_limit_mwh(2020, 8000.0, 8784.0, CAP) == pytest.approx(want)


def test_scr_does_not_move_the_limit():
    for y in (2020, 2021, 2022):
        assert L.coal_energy_limit_mwh(y, 7850.0, 8760.0, SCR) == pytest.approx(
            L.coal_energy_limit_mwh(y, 7850.0, 8760.0, "dukes_max"))


def test_combined_adds_kept_permits_from_2023():
    cap = L.coal_lf_cap("dukes_max")
    # 2021: nothing kept is capped under permits, so combined = existing cap alone
    assert L.coal_energy_limit_mwh(2021, 7850.0, 8760.0, B_CAP) == pytest.approx(
        cap * (7850.0 - 3320.0) * 8760.0 + 3320.0 * 1500.0)
    # 2023: the existing cap has ended; kept West Burton A from 31 Mar (276/365), Drax 5-6 from 30 Apr (246/365)
    eq = 2000.0 * 276 / 365 + 1320.0 * 246 / 365
    assert L.coal_energy_limit_mwh(2023, 7000.0, 8760.0, B_CAP) == pytest.approx(
        cap * (7000.0 - eq) * 8760.0 + 1500.0 * eq)
    assert L.ied_capped_units(2023, B_CAP) == L.ied_capped_units(2023, "dukes_max+ied_permits_1500")


def test_scr_cost_is_kept_scr_cost():
    """(b) is costed exactly as the road costs SCR on kept coal: kept_costs' SCR line on the same MW."""
    for y, eq in ((2020, 3320.0 * 184 / 366), (2021, 3320.0)):
        fixed, vom_mwh = L.existing_scr_costs(y, SCR)
        kfix, kvom, kdet = L.kept_costs(y, {"mw": {"coal": eq, "ccgt": 0.0, "other_gas": 0.0, "oil": 0.0},
                                            "abated_mw": {"FGD": 0.0, "SCR": eq, "FGD+SCR": 0.0}})
        assert fixed == pytest.approx(kdet["abatement_fixed_gbp_m"])
        assert fixed > 0 and vom_mwh == pytest.approx(kvom) and vom_mwh > 0
    assert L.existing_scr_costs(2023, SCR) == (0.0, 0.0)
    assert L.existing_scr_costs(2021, CAP) == (0.0, 0.0)


def test_engine_2021_cap_binds_and_scr_charges():
    off = L.lfl_year(2021, closures_file=REG)
    on = L.lfl_year(2021, closures_file=REG, coal_lf=CAP)
    hours = 8760.0
    coal_mw = off.coal_twh * 1e6 / (off.coal_lf_achieved * hours)
    lim = L.coal_energy_limit_mwh(2021, coal_mw, hours, CAP)
    assert on.coal_twh * 1e6 <= lim * (1 + 1e-3)
    assert on.coal_twh < off.coal_twh - 5.0                         # 3,320 MW from 65% to 17%: ~14 TWh less
    assert on.energy_twh == pytest.approx(off.energy_twh)
    assert on.existing_scr_fixed_gbp_m == 0.0
    scr = L.lfl_year(2021, closures_file=REG, coal_lf=SCR)
    assert scr.coal_twh == pytest.approx(off.coal_twh)               # no hours cap under the retrofit
    fixed, vom_mwh = L.existing_scr_costs(2021, SCR)
    assert scr.existing_scr_fixed_gbp_m == pytest.approx(fixed)
    # filters' running cost on the two stations' share of the block's output
    assert scr.existing_scr_vom_gbp_m == pytest.approx(vom_mwh * scr.coal_twh * 3320.0 / coal_mw)


def test_bill_carries_the_scr_charge():
    from gascf import bills as B
    off = B.fleet_lfl(2021)
    scr = B.fleet_lfl(2021, coal_lf=SCR)
    r = L.lfl_year(2021, closures_file=str(L.closures_path()), coal_lf=SCR)
    add = r.existing_scr_fixed_gbp_m + r.existing_scr_vom_gbp_m
    assert add > 0
    assert scr["total_gbp_m"] - off["total_gbp_m"] == pytest.approx(add)
