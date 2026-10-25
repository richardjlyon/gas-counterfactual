"""Card [internal ticket]: the v4-s39 central carries the ruled settings by default.

Each expected value is a literal from Richard's rulings as recorded in the decisions folder, not the
engine's own output:
- M2 closure test at the road's coal load factor, M3 (a) kept coal paid its fixed cost less its margin,
  M4 filter running cost inside the market price: decision 0163 (R1-R5 (a)).
- M9 B, direct coefficients May 2021-Dec 2023, Jan-Apr 2021 and every other year on Shao:
  decision 0164 addendum ("b").
- The five closures at their DUKES 5.11 edition MW (Rugeley rule, 0159; corrections log C-009):
  Barry 235, Fawley 968, Deeside 515, Ironbridge 900, Uskmouth 230.

- Coal hours reading (i): decision 0166 (tests at the end of this file).

Settings NOT ruled when this was written stay at their v4-s38 values and are not asserted here:
M7 and M8 (environment switches). The cut sets them when Richard rules.
"""
from __future__ import annotations

from pathlib import Path

from gascf import bills as B
from gascf import fossil_like_for_like as L

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "reference/fossil_closures.yaml"


def test_central_has_the_ruled_coal_settings():
    assert B.CENTRAL.closure_test == "road_lf"
    assert B.CENTRAL.kept_coal_pay == "fixed_less_margin"
    assert B.CENTRAL.kept_filter_vom == "in_price"


def test_central_has_m9_b_with_jan_apr_2021_on_shao():
    assert B.CENTRAL.moe_crisis == "m9_direct_mayon"


def test_rows_that_cannot_set_a_range_end_stay_off_in_central():
    assert B.CENTRAL.kept_life_ext == "none"            # M5 row (R33 borrowed)
    assert B.CENTRAL.closures_real_date_class == "none"  # O1 rows (methods page)
    assert B.CENTRAL.cost_case == "medium"               # O2 held rows


def test_five_closures_at_edition_mw_by_default(monkeypatch):
    monkeypatch.delenv(L.EDITION_MW_ENV, raising=False)
    got = {r["station"]: r["capacity_mw"] for r in L.read_closures(REG) if r["unit"] == "all"}
    assert [got[s] for s in ("Barry", "Fawley", "Deeside", "Ironbridge", "Uskmouth")] == [235, 968, 515, 900, 230]


def test_edition_mw_can_still_be_turned_off(monkeypatch):
    """'none' reads the register as stored (v4-s38 MW), for reruns of the older line."""
    monkeypatch.setenv(L.EDITION_MW_ENV, "none")
    assert L.edition_mw_switches() == ()


def test_central_edition_mw_default_does_not_reach_a_fixture_register(monkeypatch, tmp_path):
    """A fixture register without the five stations reads as stored when the variable is unset; a switch named
    in the variable still refuses a register that lacks its station."""
    import json
    rows = [r for r in json.loads(REG.read_text()) if r["station"] != "Barry"]
    p = tmp_path / "fixture.yaml"
    p.write_text(json.dumps(rows))
    monkeypatch.delenv(L.EDITION_MW_ENV, raising=False)
    got = {r["station"]: r["capacity_mw"] for r in L.read_closures(p) if r["unit"] == "all"}
    assert got["Fawley"] == 1036     # register MW: the default is for the real register only
    monkeypatch.setenv(L.EDITION_MW_ENV, "barry")
    with __import__("pytest").raises(ValueError, match="Barry"):
        L.read_closures(p)


# ---- decision 0166 (Richard Lyon, 22 Oct 2026: "As long as it was lawful, then it's legitimate. Approved."):
# coal hours reading (i) central: every coal station, kept and existing, on its real permit hours, the 2011-14
# LCPD opt-outs included and the kept LCPD stations (Tilbury B, Ironbridge) held to their 20,000 hours; H2 2020
# pro rata from 1 July 2020. SCR instead not used; reading (ii) a check row only, never a range end.

def test_central_coal_hours_are_reading_i():
    assert B.CENTRAL.coal_lf == "dukes_max+ied_permits_1500+existing"


def test_kept_lcpd_stations_held_by_default(monkeypatch):
    monkeypatch.delenv(L.LCPD_KEPT_ENV, raising=False)
    assert L.lcpd_kept_on() is True
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "off")
    assert L.lcpd_kept_on() is False
    monkeypatch.setenv(L.LCPD_KEPT_ENV, "on")
    assert L.lcpd_kept_on() is True


def test_reading_ii_is_a_check_row_never_in_the_range():
    rows = {k: v for k, v in B.V11_COAL_ROWS.items() if "1,500-hour route" in k}
    assert len(rows) == 1
    (row,) = rows.values()
    assert [s.coal_lf for s in row] == ["dukes_max+ied_route_1500+existing"]
    assert all("ied_route" not in s.coal_lf for v in B.SWITCHES.values() for s in v)
    assert all("ex_scr" not in s.coal_lf for v in B.SWITCHES.values() for s in v)
    assert all(s.coal_lf in (B.CENTRAL.coal_lf, "none") for v in B.SWITCHES.values() for s in v)


# ---- decision 0167 (Richard Lyon, 22 Oct 2026): M7 "A" = the merit order (carbon at the marginal plant from
# 1 Jan 2009, the modeller's option (b)); M8 "Approve." = MID shape in both Britains from 12 Sep 2016 SP32.

def test_m7_merit_order_is_the_central_default(monkeypatch):
    from gascf import marginal_carbon as MCB
    monkeypatch.delenv(MCB.ENV, raising=False)
    assert MCB.DEFAULT == "merit"
    assert MCB.method() == "merit"


def test_m8_mid_shape_in_both_britains_is_the_central_default(monkeypatch):
    from gascf import hh_pricing as H
    monkeypatch.delenv(H.ENV, raising=False)
    monkeypatch.delenv(H.SCOPE_ENV, raising=False)
    assert (H.method(), H.scope()) == ("mid_shape", "both")
    monkeypatch.setenv(H.ENV, "monthly")
    monkeypatch.setenv(H.SCOPE_ENV, "fossil")
    assert (H.method(), H.scope()) == ("monthly", "fossil")


# ---- decision 0167, generators' share "a" (way 2, card [internal ticket]; guard met, +8.837 with VAT against 8.5 +/- 2)
# and decision 0169, RO mutualisation "a" (count it as part of the RO, as it is not inside the engine's RO line:
# card [internal ticket]). Both confirmed against Richard's own words by [internal ticket] (rule 0046).

def test_generators_share_way_2_is_the_central_default():
    assert B.CENTRAL.gen_nz_charge == "fossil_price"


def test_ro_mutualisation_received_is_the_central_default():
    assert B.CENTRAL.ro_mutualisation == "received"


def test_v4_s38_reading_of_both_is_still_an_explicit_setting():
    from dataclasses import replace
    s = replace(B.CENTRAL, gen_nz_charge="none", ro_mutualisation="off")
    assert (s.gen_nz_charge, s.ro_mutualisation) == ("none", "off")


def test_m7_and_m8_run_meta_say_ruled_central_not_off(monkeypatch):
    """The run file's meta.carbon_marginal / meta.hh_pricing status follows 0167 (it said 'OFF by default')."""
    from gascf import hh_pricing as H
    from gascf import marginal_carbon as MCB
    for e in (MCB.ENV, H.ENV, H.SCOPE_ENV):
        monkeypatch.delenv(e, raising=False)
    for meta in (MCB.run_meta(), H.run_meta()):
        assert "OFF by default" not in meta["status"]
        assert "0167" in meta["status"] and "central" in meta["status"]
