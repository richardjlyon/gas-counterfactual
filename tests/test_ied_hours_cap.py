"""Card [internal ticket] (measure only; Richard has not ruled): kept coal obeys each unit's IED hours cap.

Switch: coal_lf rule. "dukes_max" (default, OFF) is v4-s38. "dukes_max+ied_<reading>_<hours>" ON:
  reading "permits" = each kept unit held to its station's real post-1-July-2020 permit (analyst reading B:
    West Burton A, Drax units 5-6; EA permits EPR/SP3935LW/V011 and EPR/VP3530LS/V018, condition 2.3.6);
  reading "route" = as permits, plus Drax units 1-4 and Lynemouth given the same 1,500-hour route (reading C);
  hours 1500 (the IED Annex V rolling-average limit) or 2250 (the permits' single-year maximum).
Each capped unit's yearly output may not exceed its cap hours x MW x the share of the year it is kept after
1 July 2020. The coal block's energy limit is the uncapped MW at the 65.04% cap plus each capped unit's cap.

Expected values are literals from the closure register's MW, the register's dates and the permits' hours,
not the engine's own output.
"""
import pytest

from gascf import fossil_like_for_like as L

B_1500 = "dukes_max+ied_permits_1500"
C_1500 = "dukes_max+ied_route_1500"
C_2250 = "dukes_max+ied_route_2250"
REG = str(L.CLOSURES_FILE)          # the real closure register (conftest points the engine at a fixture)


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    monkeypatch.setenv(L.CLOSURES_ENV, REG)


def test_switch_is_off_by_default_and_rules_are_named():
    assert L.DEFAULT_COAL_LF == "dukes_max"
    for r in (B_1500, C_1500, "dukes_max+ied_permits_2250", C_2250):
        assert r in L.COAL_LF_RULES
        assert L.coal_lf_cap(r) == L.coal_lf_cap("dukes_max")      # the 65.04% block cap still applies
    with pytest.raises(ValueError):
        L.coal_lf_cap("dukes_max+ied_bogus_1500")


def test_off_gives_the_v4_s38_limit():
    cap = L.coal_lf_cap("dukes_max")
    assert L.coal_energy_limit_mwh(2024, 9000.0, 8784.0, "dukes_max") == pytest.approx(cap * 9000.0 * 8784.0)
    assert L.coal_energy_limit_mwh(2024, 9000.0, 8784.0, "none") is None
    assert L.ied_capped_units(2024, "dukes_max") == []


def test_permits_2024_caps_west_burton_a_and_drax_5_6():
    cap = L.coal_lf_cap("dukes_max")
    u = L.ied_capped_units(2024, B_1500)
    assert sorted((s, mw) for s, _, mw, _, _ in u) == [("Drax", 1320.0), ("West Burton A", 2000.0)]
    capped_mw = 2000.0 + 1320.0                                    # register MW, kept all of 2024
    want = cap * (9000.0 - capped_mw) * 8784.0 + capped_mw * 1500.0
    assert L.coal_energy_limit_mwh(2024, 9000.0, 8784.0, B_1500) == pytest.approx(want)


def test_route_2024_adds_drax_1_4_and_lynemouth():
    cap = L.coal_lf_cap("dukes_max")
    capped_mw = 2000.0 + 1320.0 + 4 * 660.0 + 420.0               # 6,380 MW
    assert sum(mw for _, _, mw, _, _ in L.ied_capped_units(2024, C_1500)) == pytest.approx(capped_mw)
    want = cap * (9000.0 - capped_mw) * 8784.0 + capped_mw * 1500.0
    assert L.coal_energy_limit_mwh(2024, 9000.0, 8784.0, C_1500) == pytest.approx(want)
    want_2250 = cap * (9000.0 - capped_mw) * 8784.0 + capped_mw * 2250.0
    assert L.coal_energy_limit_mwh(2024, 9000.0, 8784.0, C_2250) == pytest.approx(want_2250)


def test_part_years_2023_and_2020():
    cap = L.coal_lf_cap("dukes_max")
    # 2023, permits: West Burton A kept from 31 Mar (276 of 365 days), Drax 5-6 from 30 Apr (246 of 365)
    s_wba, s_drax = 276 / 365, 246 / 365
    capped_eq = 2000.0 * s_wba + 1320.0 * s_drax
    want = cap * (7000.0 - capped_eq) * 8760.0 + 1500.0 * capped_eq
    assert L.coal_energy_limit_mwh(2023, 7000.0, 8760.0, B_1500) == pytest.approx(want)
    # 2020, route: Drax 1-4 and Lynemouth kept all year, capped from 1 July (184 of 366 days)
    capped_eq = (4 * 660.0 + 420.0) * 184 / 366
    want = cap * (8000.0 - capped_eq) * 8784.0 + 1500.0 * capped_eq
    assert L.coal_energy_limit_mwh(2020, 8000.0, 8784.0, C_1500) == pytest.approx(want)
    # 2020, permits: West Burton A and Drax 5-6 are not kept (still open in reality), so nothing is capped
    assert L.ied_capped_units(2020, B_1500) == []


def test_no_cap_before_july_2020():
    for y in (2013, 2016, 2019):
        assert L.ied_capped_units(y, C_1500) == []
        assert L.coal_energy_limit_mwh(y, 8000.0, 8760.0, C_1500) == pytest.approx(
            L.coal_energy_limit_mwh(y, 8000.0, 8760.0, "dukes_max"))


def test_engine_2024_runs_capped_coal_within_the_limit():
    """The engine seam: with the switch on, the coal block's 2024 output keeps under the new limit, the lost
    output goes to the next blocks and new build (total energy unchanged), and coal MW stay at the peak."""
    off = L.lfl_year(2024, closures_file=REG)
    on = L.lfl_year(2024, closures_file=REG, coal_lf=C_1500)
    hours = 8784.0
    ex_coal_mw = off.coal_twh * 1e6 / (off.coal_lf_achieved * hours)
    lim = L.coal_energy_limit_mwh(2024, ex_coal_mw, hours, C_1500)
    assert on.coal_twh * 1e6 <= lim * (1 + 1e-3)
    assert on.coal_twh < off.coal_twh - 1.0                        # at least 1 TWh less coal
    assert on.energy_twh == pytest.approx(off.energy_twh)
    assert on.coal_ied["capped_mw_eq"] == pytest.approx(6380.0)
