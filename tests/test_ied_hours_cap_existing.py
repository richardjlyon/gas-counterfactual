"""Card [internal ticket] (measure only; Richard has not ruled): existing coal obeys each station's real hours cap too.

Switch: coal_lf rule "dukes_max+ied_<reading>_<hours>+existing" (OFF by default: "dukes_max" = v4-s38). On top of the
kept-coal reading of card [internal ticket], existing coal (in the engine's coal block on its DUKES end-year capacity basis)
is held to:
  - the LCPD opt-out: 20,000 operating hours in total from 1 Jan 2008 (Directive 2001/80/EC Art. 4(4)(a)) for
    Didcot A, Cockenzie, Kingsnorth, Ironbridge, Ferrybridge C units 1-2 and Tilbury B. Hours used each year =
    the lower of the hours left and the coal block's load factor x the year's hours. Once used, the station is held.
  - the post-1-July-2020 permits (condition 2.3.6) for West Burton A and Drax units 5-6 while they are still open in
    reality (2020 H2 to 2022): the reading's hours a year, pro rata from 1 July 2020.
A station is in the block in a year when its register coal end is on or after 31 December of that year (the engine's
end-year capacity basis; analyst file section 4: 15 station-years, not 19).

Expected values are literals from the register's MW and dates, the Directive's 20,000 hours and the permits' hours.
"""
import pytest

from gascf import fossil_like_for_like as L

P_X = "dukes_max+ied_permits_1500+existing"
C_X = "dukes_max+ied_route_1500+existing"
REG = str(L.CLOSURES_FILE)
LCPD5 = [("Cockenzie", 1152.0), ("Didcot A", 1958.0), ("Ferrybridge C", 980.0), ("Ironbridge", 1000.0),
         ("Kingsnorth", 1940.0)]


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    monkeypatch.setenv(L.CLOSURES_ENV, REG)
    # register MW: the LCPD5 literals are the register's (Ironbridge 1,000); the v4-s39 default is C-009's 900
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)


def test_rules_named_off_by_default():
    assert L.DEFAULT_COAL_LF == "dukes_max"
    for r in (P_X, C_X, "dukes_max+ied_permits_2250+existing", "dukes_max+ied_route_2250+existing"):
        assert r in L.COAL_LF_RULES
        assert L.coal_lf_cap(r) == L.coal_lf_cap("dukes_max")
    # the kept-only rules of [internal ticket] cap no existing coal
    assert L.ied_existing_units(2021, "dukes_max+ied_permits_1500", REG) == []
    assert L.ied_existing_units(2011, "dukes_max", REG, lcpd_used_h=19000.0) == []


def test_lcpd_hours_used_from_2008():
    lf = {2008: 0.6504, 2009: 0.6194, 2010: 0.6504, 2011: 0.6504}
    assert L.lcpd_hours_used(2008, lf) == 0.0
    want_2011 = 0.6504 * 8784 + 0.6194 * 8760 + 0.6504 * 8760          # 16,836.56 h, under 20,000
    assert L.lcpd_hours_used(2011, lf) == pytest.approx(want_2011)
    assert L.lcpd_hours_used(2012, lf) == pytest.approx(20000.0)        # 2011 uses the last 3,163.44 h


def test_lcpd_2011_holds_five_stations_to_their_hours_left():
    u = L.ied_existing_units(2011, P_X, REG, lcpd_used_h=16836.5616)
    assert sorted((s, mw) for s, _, mw, _, _ in u) == LCPD5            # Tilbury B ends 30 Jun 2011: not in block
    for _, _, _, sh, h in u:
        assert sh == 1.0
        assert h == pytest.approx(20000.0 - 16836.5616)


def test_lcpd_2012_2013_held_and_2010_2014_free():
    cap = L.coal_lf_cap("dukes_max")
    u12 = L.ied_existing_units(2012, P_X, REG, lcpd_used_h=20000.0)
    assert sorted((s, mw) for s, _, mw, _, _ in u12) == LCPD5           # Kingsnorth ends 31 Dec 2012: in block
    assert all(h == 0.0 for *_, h in u12)
    u13 = L.ied_existing_units(2013, P_X, REG, lcpd_used_h=20000.0)
    assert [(s, mw, h) for s, _, mw, _, h in u13] == [("Ferrybridge C", 980.0, 0.0)]
    assert L.ied_existing_units(2014, P_X, REG, lcpd_used_h=20000.0) == []
    # 2010: 8,860.94 h left is more than the block cap's 0.6504 x 8,760 h, so nothing binds
    assert 20000.0 - 11139.0576 > cap * 8760
    assert L.ied_existing_units(2010, P_X, REG, lcpd_used_h=11139.0576) == []


def test_permits_existing_west_burton_a_and_drax_5_6_2020_to_2022():
    for y, sh in ((2020, 184 / 366), (2021, 1.0), (2022, 1.0)):
        u = L.ied_existing_units(y, P_X, REG)
        assert sorted((s, mw, h) for s, _, mw, _, h in u) == [("Drax", 1320.0, 1500.0), ("West Burton A", 2000.0, 1500.0)]
        assert all(s_ == pytest.approx(sh) for _, _, _, s_, _ in u)
    assert L.ied_existing_units(2023, P_X, REG) == []                  # kept from 2023: the kept switch caps them
    assert L.ied_existing_units(2019, P_X, REG) == []
    # route reading caps the same existing coal
    assert L.ied_existing_units(2021, C_X, REG) == L.ied_existing_units(2021, P_X, REG)


def test_limit_2021_with_existing():
    cap = L.coal_lf_cap("dukes_max")
    ex = L.ied_existing_units(2021, P_X, REG)
    want = cap * (6000.0 - 3320.0) * 8760.0 + 3320.0 * 1500.0
    assert L.coal_energy_limit_mwh(2021, 6000.0, 8760.0, P_X, REG, extra_units=ex) == pytest.approx(want)


def test_engine_2011_holds_lcpd_coal_and_2012_obeys_the_limit():
    """Engine seam: with existing coal on, 2011 coal output falls below OFF and total energy is unchanged. In 2012 the
    stations' hours are used up and the block stays within its permit-derived limit (v4-s40 item 1, decision 0175: the
    s29 actual-output floor no longer overrides a permit-derived limit; v4-s39 kept the floor here)."""
    off = L.lfl_year(2011, closures_file=REG)
    on = L.lfl_year(2011, closures_file=REG, coal_lf=P_X)
    assert on.coal_twh < off.coal_twh - 1.0
    assert on.energy_twh == pytest.approx(off.energy_twh)
    assert on.coal_ied["existing_mw_eq"] == pytest.approx(sum(mw for _, mw in LCPD5))
    on12 = L.lfl_year(2012, closures_file=REG, coal_lf=P_X)
    assert on12.coal_ied["lcpd_hours_used_before"] == pytest.approx(20000.0)
    assert on12.coal_twh <= on12.coal_ied["limit_twh"] * (1 + 1e-4)
