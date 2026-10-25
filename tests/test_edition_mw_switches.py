"""Card [internal ticket]: one switch per station for the Rugeley rule on five closures (measure only).

The Rugeley rule (decision 0159 for Rugeley alone): use the capacity in the DUKES 5.11 edition sheet
listing last before closure. For Barry, Fawley, Ironbridge, Deeside and Uskmouth the register follows
another source; Richard has not ruled on these five. Each switch is OFF by default, so the register
and every figure stay as they are until he rules. A switch is named in $GASCF_EDITION_MW
(comma-separated); the register file itself is never edited by a switch.

Expected MW are literals from the stored edition-sheet extract (data/raw/s23a/s23a-DUKES_5.11_editions.txt),
and each test checks the quoted row is in that file, so the expected value is not the engine's own output.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gascf import fossil_like_for_like as L

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "reference/fossil_closures.yaml"
EDITIONS = (ROOT / "data/raw/s23a/s23a-DUKES_5.11_editions.txt").read_text()

# switch -> (register station, register MW today, edition MW, edition row quoted from the stored extract)
EXPECTED = {
    "barry": ("Barry", 375, 235, "DUKES 2018 :: Barry | CCGT | 235 | 1998 | Wales | (2)"),
    "fawley": ("Fawley", 1036, 968, "DUKES 2012 :: Fawley  | oil | 968 | 1969 | South East"),
    "ironbridge_940": ("Ironbridge", 1000, 940, "DUKES 2012 :: Ironbridge | coal | 940 | 1970 | West Midlands"),
    "ironbridge_900": ("Ironbridge", 1000, 900, "DUKES 2013 :: E.On UK | Ironbridge | biomass | 900 | 1970 | West Midlands"),
    "deeside": ("Deeside", 498, 515, "DUKES 2017 :: ENGIE | Deeside | CCGT | 515 | 1994 | Wales"),
    "uskmouth_230": ("Uskmouth", 220, 230, "DUKES 2017 :: SIMEC | Uskmouth Power | Coal | 230 | 1966 | Wales"),
    "uskmouth_363": ("Uskmouth", 220, 363, "DUKES 2018 :: SIMEC | Uskmouth power | Coal | 363 | 1966 | Wales"),
}


def _mw(rows, station):
    (r,) = [r for r in rows if r["station"] == station and r["unit"] == "all"]
    return r["capacity_mw"]


@pytest.fixture
def no_switch(monkeypatch):
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)   # v4-s39: unset now means the central five


def test_quotes_are_in_the_stored_edition_sheets():
    for sw, (_, _, mw, quote) in EXPECTED.items():
        assert quote in EDITIONS, sw
        assert f"| {mw} |" in quote, sw


def test_all_switches_off_with_none(no_switch):
    """Off ("none"): the register is read exactly as stored (the file's own MW for every row)."""
    stored = json.loads(REG.read_text())
    got = L.read_closures(REG)
    assert len(got) == len(stored)
    for a, b in zip(got, stored):
        want = 0.0 if b["capacity_mw"] is None else float(b["capacity_mw"])
        assert a["capacity_mw"] == want, a["station"]
    for station, reg_mw, _, _ in EXPECTED.values():
        assert _mw(got, station) == reg_mw


@pytest.mark.parametrize("sw", sorted(EXPECTED))
def test_each_switch_alone_moves_only_its_station(monkeypatch, sw):
    station, _, mw, _ = EXPECTED[sw]
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)   # v4-s39: unset now means the central five
    base = L.read_closures(REG)
    monkeypatch.setenv(L.EDITION_MW_ENV, sw)
    on = L.read_closures(REG)
    assert _mw(on, station) == mw
    moved = [(a["station"], a["unit"]) for a, b in zip(base, on) if a["capacity_mw"] != b["capacity_mw"]]
    assert moved == [(station, "all")]
    # nothing else on the row changes: dates, reason and fuel stay as the register has them
    (a,) = [r for r in base if r["station"] == station and r["unit"] == "all"]
    (b,) = [r for r in on if r["station"] == station and r["unit"] == "all"]
    for k in ("fuel", "actual_close", "fossil_britain_close", "reason", "abatement_needed"):
        assert a[k] == b[k], (sw, k)


def test_all_five_together(monkeypatch):
    monkeypatch.setenv(L.EDITION_MW_ENV, "barry,fawley,ironbridge_940,deeside,uskmouth_230")
    on = L.read_closures(REG)
    assert [_mw(on, s) for s in ("Barry", "Fawley", "Ironbridge", "Deeside", "Uskmouth")] == [235, 968, 940, 515, 230]


def test_two_variants_of_one_station_refused(monkeypatch):
    monkeypatch.setenv(L.EDITION_MW_ENV, "ironbridge_940,ironbridge_900")
    with pytest.raises(ValueError, match="Ironbridge"):
        L.read_closures(REG)


def test_unknown_switch_refused(monkeypatch):
    monkeypatch.setenv(L.EDITION_MW_ENV, "rugeley")
    with pytest.raises(ValueError, match="rugeley"):
        L.read_closures(REG)


def test_switch_refuses_a_register_that_has_moved(monkeypatch, tmp_path):
    """A switch overrides only the MW it was written against; if the register row has since
    changed, the switch fails loudly instead of silently replacing a new value."""
    rows = json.loads(REG.read_text())
    for r in rows:
        if r["station"] == "Barry":
            r["capacity_mw"] = 300
    p = tmp_path / "reg.yaml"
    p.write_text(json.dumps(rows))
    monkeypatch.setenv(L.EDITION_MW_ENV, "barry")
    with pytest.raises(ValueError, match="Barry"):
        L.read_closures(p)


def test_kept_open_follows_the_switch_in_one_process(monkeypatch, tmp_path):
    """kept_open is cached: the switch must be part of its key, or a run that turns a switch on
    in the same process would read the stale result. A test register keeps Barry open to
    30 June 2020 (it is not kept in the real register), so its MW reaches fossil Britain."""
    rows = json.loads(REG.read_text())
    for r in rows:
        if r["station"] == "Barry":
            r["reason"], r["fossil_britain_close"] = "mixed", "2020-06-30"
    p = tmp_path / "reg-barry-kept.yaml"
    p.write_text(json.dumps(rows))
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)   # v4-s39: unset now means the central five
    off = dict((s, mw) for s, _, mw, _ in L.kept_open(2019, "legitimate", str(p))["stations"])
    monkeypatch.setenv(L.EDITION_MW_ENV, "barry")
    on = dict((s, mw) for s, _, mw, _ in L.kept_open(2019, "legitimate", str(p))["stations"])
    assert off["Barry"] == pytest.approx(375 * 276 / 365)      # kept from 31 March 2019 (276 days to year end)
    assert on["Barry"] == pytest.approx(235 * 276 / 365)


def test_switched_mw_for_the_margin_script(monkeypatch):
    """work/s24-closure-test/margins.py types each station's MW by hand; it reads the switch
    through switched_mw, so Ironbridge and Uskmouth's margins follow the same switch."""
    monkeypatch.setenv(L.EDITION_MW_ENV, L.EDITION_MW_OFF)   # v4-s39: unset now means the central five
    assert L.switched_mw("Uskmouth", 220) == 220
    monkeypatch.setenv(L.EDITION_MW_ENV, "uskmouth_363")
    assert L.switched_mw("Uskmouth", 220) == 363
    assert L.switched_mw("Ironbridge", 1000) == 1000
