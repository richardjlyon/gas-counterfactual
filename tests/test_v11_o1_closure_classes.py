"""RB v1.1 O1 tests (card [internal ticket]; decision 0163 R17 (a), Richard Lyon, 21 Oct 2026, as relayed: "Agree to all.
Yep. Next."): closures by class, printed on the methods page, not in the range.

How the 8 'net_zero_policy' rows are classed waits on ruling R34 (rulings-sheet-2.md). The rows carry the
recommended option R34 (a) as data, named as such: "biomass_conversion" = Drax units 1-4 and Lynemouth;
"coal_phase_out_deadline" = West Burton A, Drax units 5-6, Ratcliffe-on-Soar; the 9 'mixed' rows "mixed" (the
analyst's sourcing, option-a-sourcing.md section 8). A class row lets that class close on its real dates while every
other closure stays as in the central case. Expected values: the register's own dates and capacities, and the
released v4-s37 run file's 2024 kept coal (6.8935 GW).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gascf import fossil_like_for_like as L

ROOT = Path(__file__).resolve().parents[1]
REG = str(ROOT / "reference/fossil_closures.yaml")
RUN37 = json.loads((ROOT / "out/v4/2026-10-20-s37.json").read_text())

R34_A = {("Drax", "unit 1 (first biomass conversion)"): "biomass_conversion",
         ("Drax", "unit 2 (second biomass conversion)"): "biomass_conversion",
         ("Drax", "unit 3 (third biomass conversion)"): "biomass_conversion",
         ("Drax", "unit 4 (fourth biomass conversion)"): "biomass_conversion",
         ("Lynemouth", "all"): "biomass_conversion",
         ("West Burton A", "all"): "coal_phase_out_deadline",
         ("Drax", "units 5-6 (last coal units)"): "coal_phase_out_deadline",
         ("Ratcliffe-on-Soar", "all"): "coal_phase_out_deadline"}


def test_classes_are_register_data_on_the_r34_a_mapping():
    rows = L.read_closures(REG)
    nzp = {(r["station"], r["unit"]): r["closure_class"] for r in rows if r["reason"] == "net_zero_policy"}
    assert nzp == R34_A
    assert all(r["closure_class"] == "mixed" for r in rows if r["reason"] == "mixed")
    assert all("closure_class" not in r for r in rows if r["reason"] not in ("net_zero_policy", "mixed"))
    for r in rows:
        if "closure_class" in r:
            assert "R34 (a)" in r["closure_class_source"]
    assert set(L.CLOSURE_CLASSES) == {"biomass_conversion", "coal_phase_out_deadline", "mixed"}


def test_central_2024_kept_coal_is_v4_s37s():
    assert L.kept_open(2024, "legitimate", REG)["mw"]["coal"] == pytest.approx(
        RUN37["fleet"]["2024"]["kept_gw"]["coal"] * 1e3, abs=1e-6)


@pytest.mark.parametrize("cls, closed_mw", [
    # West Burton A 2,000 (closed 31 Mar 2023) + Drax 5-6 1,320 (30 Apr 2023) + Ratcliffe 2,021 x 93/366 of 2024
    ("coal_phase_out_deadline", 2000 + 1320 + 2021 * 93 / 366),
    # Drax units 1-4 4 x 660 + Lynemouth 420, all closed before 2024
    ("biomass_conversion", 4 * 660 + 420),
    # no mixed station is kept in 2024 in the register as written
    ("mixed", 0.0),
])
def test_a_class_row_closes_that_class_on_its_real_dates(cls, closed_mw):
    base = L.kept_open(2024, "legitimate", REG)["mw"]["coal"]
    got = L.kept_open(2024, "legitimate", REG, (), cls)["mw"]["coal"]
    assert base - got == pytest.approx(closed_mw, abs=1e-6)


def test_mixed_class_row_undoes_the_m2_list():
    """Under M2 Cottam is kept to 30 June 2020; the 'mixed' class row closes it on its real date again."""
    ov = (("Cottam", "all", "2020-06-30", None),)
    kept = {s for s, *_ in L.kept_open(2020, "legitimate", REG, ov)["stations"]}
    assert "Cottam" in kept
    assert "Cottam" not in {s for s, *_ in L.kept_open(2020, "legitimate", REG, ov, "mixed")["stations"]}


def test_unknown_class_stops():
    with pytest.raises(ValueError):
        L.kept_open(2024, "legitimate", REG, (), "carbon_price")
