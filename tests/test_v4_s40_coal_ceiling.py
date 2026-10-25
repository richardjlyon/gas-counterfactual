"""v4-s40 item 1 (step-3 sheet item 1 (a); decision 0175, Richard Lyon 23 Oct 2026, "Yes." at 06:13:51 UTC to the
chief-executive's point 3: "The coal fix caps coal at its legal energy limit, without building a station-by-station
timetable."; verified first-hand on card [internal ticket]).

To v4-s39 the coal block's yearly output limit was max(permit-derived energy limit, actual coal supplied): the s29
actual-output floor overrode the permit ceiling (C-011, 0166 reading (i)). Review [internal ticket] item 1: in 2012 the road
ran 132.694 TWh of coal against a 92.616 TWh limit, in 2013 123.494 against 110.836. The fix: where a permit-derived
energy limit is supplied, it is absolute; the floor stays only under the DUKES load-factor cap (no permit limit), which
is not a legal limit. `$GASCF_COAL_CEILING`: "absolute" (v4-s40 central, unset) or "floored" (v4-s39, explicit only).

Expected values: the reviewer's limits (literals above) and the DUKES 5.6.J actual coal the floor reads. Engine seams
run the central coal settings (road_lf closure test, contracted interconnectors, the C-009 register MW default).
About 1 to 2 minutes a year.
"""
import pytest

from gascf import fossil_like_for_like as L

P_X = "dukes_max+ied_permits_1500+existing"
REG = str(L.CLOSURES_FILE)
LIMIT = {2012: 92.616, 2013: 110.836}          # review [internal ticket] item 1, TWh
COAL_V4S39 = {2012: 132.694, 2013: 123.494}    # the same review: the road's coal under the floor, TWh
ENV = getattr(L, "COAL_CEILING_ENV", "GASCF_COAL_CEILING")   # getattr: the red run on v4-s39 fails on behaviour


@pytest.fixture(autouse=True)
def _real_register(monkeypatch):
    monkeypatch.setenv(L.CLOSURES_ENV, REG)
    monkeypatch.delenv(L.EDITION_MW_ENV, raising=False)       # v4-s39 default: C-009 MW
    monkeypatch.delenv(L.LCPD_KEPT_ENV, raising=False)
    _clear()
    yield
    _clear()


def _clear():
    L.lfl_year.cache_clear()
    L.road_lf_closures.cache_clear()


def _year(y, monkeypatch, reading=None):
    if reading is None:
        monkeypatch.delenv(ENV, raising=False)
    else:
        monkeypatch.setenv(ENV, reading)
    _clear()
    # the central coal settings as bills.fleet_lfl passes them (residual, margin, transport, closures, new build)
    return L.lfl_year(y, "neso", "central", True, "legitimate", "cheapest", REG, P_X, "contracted",
                      closure_test="road_lf", real_date_class="none", cost_case="medium")


def test_switch_named_and_absolute_by_default(monkeypatch):
    assert L.COAL_CEILING_READINGS == ("absolute", "floored")
    monkeypatch.delenv(L.COAL_CEILING_ENV, raising=False)
    assert L.coal_ceiling_reading() == "absolute"
    monkeypatch.setenv(L.COAL_CEILING_ENV, "floored")
    assert L.coal_ceiling_reading() == "floored"
    monkeypatch.setenv(L.COAL_CEILING_ENV, "timetable")
    with pytest.raises(ValueError):
        L.coal_ceiling_reading()


@pytest.mark.parametrize("y", [2012, 2013])
def test_coal_never_exceeds_the_permit_derived_limit(y, monkeypatch):
    on = _year(y, monkeypatch)
    assert on.coal_ied["limit_twh"] == pytest.approx(LIMIT[y], abs=5e-4)
    assert on.coal_twh <= on.coal_ied["limit_twh"] * (1 + 1e-4)
    assert on.coal_ied.get("actual_floor") is False


def test_2012_limit_binds_energy_still_met_and_gas_takes_the_coal(monkeypatch):
    """The displaced coal goes to the next blocks in the merit order: the residual is the same, nothing is unserved
    (no contracted imports called), and the road burns more gas than under the floor."""
    on = _year(2012, monkeypatch)
    old = _year(2012, monkeypatch, "floored")
    assert old.coal_twh == pytest.approx(COAL_V4S39[2012], abs=5e-4)     # reproduces the review's v4-s39 figure
    assert old.coal_twh >= L.actual_coal_supplied_twh(2012) * (1 - 1e-4)
    assert old.coal_ied.get("actual_floor") is True
    assert on.energy_twh == pytest.approx(old.energy_twh, abs=1e-9)
    assert on.ic_called_twh == 0.0 and old.ic_called_twh == 0.0
    assert on.coal_twh < old.coal_twh - 30.0
    assert on.gas_burn_existing_twh > old.gas_burn_existing_twh


def test_no_permit_limit_keeps_the_actual_floor_2003(monkeypatch):
    """2003: no permit-derived limit (the DUKES 65.04% cap only), so the floor still holds the block at actual coal."""
    on = _year(2003, monkeypatch)
    assert on.coal_ied["limit_twh"] is None
    assert on.coal_twh >= L.actual_coal_supplied_twh(2003) * (1 - 1e-4)
