"""Card [internal ticket] (measure only, OFF by default; Richard has not ruled): kept LCPD opt-out stations held to their hours.

Under M2 (closure_test='road_lf') the closure test keeps two LCPD opt-outs open past their real closes: Tilbury B
(real close 30 Jun 2011, kept to its LCPD date 31 Aug 2013) and Ironbridge (real close 30 Jun 2013, kept to
31 Dec 2015). Card [internal ticket]'s '+existing' rules hold the opt-outs to the 20,000 operating hours from 1 Jan 2008
(Directive 2001/80/EC Art. 4(4)(a)) only while they are in the existing block (register coal end on or after 31 Dec),
so the kept years run free of the limit. With $GASCF_IED_LCPD_KEPT=on (set before the process starts), a kept opt-out
is held to the same hours left, for the share of the year it is kept, under a '+existing' rule only.

Expected values are literals from the register (MW, dates), the Directive's 20,000 hours and the hours-left
arithmetic of tests/test_ied_hours_cap_existing.py.
"""
import pytest

from gascf import fossil_like_for_like as L

P_X = "dukes_max+ied_permits_1500+existing"
REG = str(L.CLOSURES_FILE)
TILBURY_KEPT_2012 = (("Tilbury B", "all", 1063.0, "mixed"),)          # kept all year: MW x share 1.0
IRONBRIDGE_KEPT_2013 = (("Ironbridge", "all", 1000.0 * 184 / 365, "mixed"),)   # kept from 1 Jul 2013


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    monkeypatch.setenv(L.CLOSURES_ENV, REG)
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)   # register MW: the fixtures are on that basis (v4-s39 default is C-009)


def test_off_kept_opt_outs_run_free(monkeypatch):   # v4-s39: on by default (0166); "off" = the older line
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "off")
    u = L.ied_existing_units(2012, P_X, REG, lcpd_used_h=20000.0, kept_stations=TILBURY_KEPT_2012)
    assert "Tilbury B" not in {s for s, *_ in u}


def test_on_kept_tilbury_b_2012_held_to_hours_left(monkeypatch):
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "on")
    u = L.ied_existing_units(2012, P_X, REG, lcpd_used_h=20000.0, kept_stations=TILBURY_KEPT_2012)
    assert [(s, mw, sh, h) for s, _, mw, sh, h in u if s == "Tilbury B"] == [("Tilbury B", 1063.0, 1.0, 0.0)]
    # the five existing opt-outs are listed as before
    assert len(u) == 6


def test_on_kept_ironbridge_2013_share_of_year(monkeypatch):
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "on")
    u = L.ied_existing_units(2013, P_X, REG, lcpd_used_h=20000.0, kept_stations=IRONBRIDGE_KEPT_2013)
    got = [(s, mw, sh, h) for s, _, mw, sh, h in u if s == "Ironbridge"]
    assert got == [("Ironbridge", 1000.0, pytest.approx(184 / 365), 0.0)]


def test_on_only_when_the_hours_bind_in_the_window_and_under_existing(monkeypatch):
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "on")
    # 2010: 8,860.94 h left is more than the block cap x 8,760 h: nothing binds, as for existing coal
    assert L.ied_existing_units(2010, P_X, REG, lcpd_used_h=11139.0576, kept_stations=TILBURY_KEPT_2012) == []
    # 2016: after the LCPD's 31 Dec 2015 end
    assert L.ied_existing_units(2016, P_X, REG, lcpd_used_h=20000.0,
                                kept_stations=(("Ironbridge", "all", 1000.0, "mixed"),)) == []
    # a kept-only rule (no '+existing') holds nothing
    assert L.ied_existing_units(2012, "dukes_max+ied_permits_1500", REG, lcpd_used_h=20000.0,
                                kept_stations=TILBURY_KEPT_2012) == []


def test_engine_passes_kept_stations(monkeypatch):
    """Engine seam: lfl_year with Tilbury B kept to 31 Aug 2013 (as M2's closure test sets it) lists it in 2012."""
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "on")
    L.lfl_year.cache_clear()
    ov = (("Tilbury B", "all", "2013-08-31", None),)
    try:
        y = L.lfl_year(2012, closures_file=REG, coal_lf=P_X, overrides=ov)
        names = {u["station"] for u in y.coal_ied["existing_units"]}
        assert "Tilbury B" in names
    finally:
        L.lfl_year.cache_clear()
