"""Ticket 26 (0097, 0101): the shared "on the road at a 2001 level" component, and the netting of the Fossil Fuel
Levy (NZ2, to 2019) and EESoP (NZ10, every year) in Reliable Britain. Spec
`s36-routeA-spec-items/on-the-road-2001.md`, tests written first, one at a time.

Seams: `gascf.on_the_road.net` (the component, shared with ticket 12) and `bills.build(Settings)`.
The £85.5m case (spec P1) is stopped for Richard: no switch, test or key for it here."""
from __future__ import annotations

import pytest

from gascf import on_the_road as OTR


def test_1_amount_mode_real_flat_allows_negatives_and_refuses_a_floor():
    """Spec test 1: series [30, 20], L = 25, CPIH ratios [1.0, 1.2] -> counted [5, -10], netted-off [25, 30];
    a floor other than 'none' raises (no floor is ruled, 0097)."""
    idx = {2001: 100.0, 2002: 100.0, 2003: 120.0}
    r = OTR.net({2002: 30.0, 2003: 20.0}, 25.0, mode="amount", indexation="real_cpih", index=idx)
    assert r["counted"] == pytest.approx({2002: 5.0, 2003: -10.0}, abs=1e-12)
    assert r["netted"] == pytest.approx({2002: 25.0, 2003: 30.0}, abs=1e-12)
    with pytest.raises(ValueError):
        OTR.net({2002: 30.0}, 25.0, mode="amount", floor="zero", index=idx)


def test_2_end_year_stops_the_netting_after_it():
    """Spec test 2: with end_year = 2019 the netted-off part is non-zero for 2002-19 and exactly 0 for 2020-25,
    where the counted value is the series itself."""
    series = {y: 100.0 for y in range(2002, 2026)}
    r = OTR.net(series, 92.0, mode="amount", indexation="real_cpih", end_year=2019)
    assert all(r["netted"][y] > 0 for y in range(2002, 2020))
    assert all(r["netted"][y] == 0.0 and r["counted"][y] == series[y] for y in range(2020, 2026))


# ---- build seam (0097 package on Settings). Effects are 2002-24 in 2024 prices (CPIH L522), £bn, as m2_0097.json.
from dataclasses import replace                                    # noqa: E402

from gascf import bills as B                                       # noqa: E402
from gascf.deflator_cpih import to_real                            # noqa: E402

Y24 = range(2002, 2025)


def _lines(b, y):
    return {l["id"]: l["national_gbp_m_nominal"] for l in b[y]["netzero"] + b[y]["fossil"]}


def _effect_bn(on, off, ids):
    return sum(to_real(sum(_lines(on, y)[i] - _lines(off, y)[i] for i in ids), y, 2024) for y in Y24) / 1e3


@pytest.fixture(scope="module")
def central():
    return B.build(B.CENTRAL)


def test_3_nz2_package_matches_m2_0097_and_stops_after_2019(central):
    """Spec test 3: NZ2 netted at £92m (FY2001/02, CIQY, SOURCED GB), real-flat, to 2019: NZ2 effect incl. VAT
    -3.005 £bn (line -2.950, VAT -0.055) to ±0.001 (m2_0097.json `nffo|fy2001_92|real|to2019`);
    nz2_on_the_road_gbp_m is 0 for 2020-25 and NZ2 there equals the un-netted line to 1e-9."""
    off = B.build(replace(B.CENTRAL, otr_nz2_level_gbp_m=0.0))
    assert _effect_bn(central, off, ("NZ2",)) == pytest.approx(-2.950, abs=0.001)
    assert _effect_bn(central, off, ("NZ11",)) == pytest.approx(-0.055, abs=0.001)
    assert _effect_bn(central, off, ("NZ2", "NZ11")) == pytest.approx(-3.005, abs=0.001)
    for y in range(2020, 2026):
        assert central[y]["on_the_road"]["nz2_on_the_road_gbp_m"] == 0.0, y
        assert _lines(central, y)["NZ2"] == pytest.approx(_lines(off, y)["NZ2"], abs=1e-9), y
    assert all(central[y]["on_the_road"]["nz2_on_the_road_gbp_m"] > 0 for y in range(2002, 2020))


def test_4_nz10_package_matches_m2_0097_and_nets_every_year(central):
    """Spec test 4: NZ10 netted at EESoP's £55m a year x 4,981/11,125 (electricity share by target, 44.8%;
    both INTERIM_APPROVED), real-flat, no end year: NZ10 effect incl. VAT -1.059 £bn (line -1.009, VAT -0.050) to
    ±0.001 (m2_0097.json `eesop|target_0.448|real`); netted in every year 2002-25."""
    off = B.build(replace(B.CENTRAL, otr_nz10_level_gbp_m=0.0))
    assert _effect_bn(central, off, ("NZ10",)) == pytest.approx(-1.009, abs=0.001)
    assert _effect_bn(central, off, ("NZ11",)) == pytest.approx(-0.050, abs=0.001)
    assert _effect_bn(central, off, ("NZ10", "NZ11")) == pytest.approx(-1.059, abs=0.001)
    assert all(central[y]["on_the_road"]["nz10_on_the_road_gbp_m"] > 0 for y in range(2002, 2026))


def test_5_package_total(central):
    """Spec test 5: the 0097 package, NZ2 + NZ10 + their VAT, 2002-24, = -4.064 £bn to ±0.002
    (m2_0097.json `package.end2019|below_nil`)."""
    off = B.build(replace(B.CENTRAL, otr_nz2_level_gbp_m=0.0, otr_nz10_level_gbp_m=0.0))
    assert _effect_bn(central, off, ("NZ2", "NZ10", "NZ11")) == pytest.approx(-4.064, abs=0.002)


def test_5b_nffo_payments_85_5_named_sensitivity_0108_0112():
    """Ticket 26 spec test (P1), ruled by 0108 item 1.20 (Richard Lyon, 19 Oct 2026: a named sensitivity, not central)
    and placed in the range by 0112: L = GBP 85.5m (HC Deb 18 Apr 2002 c1139W) gives NZ2 -2.793 £bn incl. VAT
    (= -3.005 x 85.5/92; line -2.742, VAT -0.051) to ±0.002 against no NZ2 netting; only NZ2 and its VAT move."""
    (s,) = B.SWITCHES[B.NFFO_85_5]
    assert s == replace(B.CENTRAL, otr_nz2_level_gbp_m=85.5)
    on, off = B.build(s), B.build(replace(B.CENTRAL, otr_nz2_level_gbp_m=0.0))
    assert _effect_bn(on, off, ("NZ2",)) == pytest.approx(-2.742, abs=0.002)
    assert _effect_bn(on, off, ("NZ11",)) == pytest.approx(-0.051, abs=0.002)
    assert _effect_bn(on, off, ("NZ2", "NZ11")) == pytest.approx(-2.793, abs=0.002)
    c = B.build(B.CENTRAL)
    for y in B.YEARS:
        a, b = _lines(c, y), _lines(on, y)
        assert {k: v for k, v in a.items() if k not in ("NZ2", "NZ11")} == pytest.approx(
            {k: v for k, v in b.items() if k not in ("NZ2", "NZ11")}, abs=1e-9), y


def test_6_cash_flat_switch_moves_only_nz2_nz10_and_their_vat(central):
    """Spec test 6: the named sensitivity on_the_road_cash_flat (SWITCHES since 0112, label B.OTR_CASH_FLAT) holds the
    2001 levels cash-flat: effects incl. VAT -0.830 (NZ10, `eesop|target_0.448|cash`) and -2.487 (NZ2,
    `nffo|fy2001_92|cash|to2019`) £bn to ±0.001 against no netting, and no other line moves against central
    beyond NZ2, NZ10 and NZ11."""
    (cash,) = B.SWITCHES[B.OTR_CASH_FLAT]          # a range row since decision 0112
    assert cash == replace(B.CENTRAL, otr_indexation="cash")
    cb = B.build(cash)
    off2 = B.build(replace(cash, otr_nz2_level_gbp_m=0.0))
    off10 = B.build(replace(cash, otr_nz10_level_gbp_m=0.0))
    assert _effect_bn(cb, off10, ("NZ10", "NZ11")) == pytest.approx(-0.830, abs=0.001)
    assert _effect_bn(cb, off2, ("NZ2", "NZ11")) == pytest.approx(-2.487, abs=0.001)
    for y in B.YEARS:
        a, c = _lines(central, y), _lines(cb, y)
        assert {k: v for k, v in a.items() if k not in ("NZ2", "NZ10", "NZ11")} == pytest.approx(
            {k: v for k, v in c.items() if k not in ("NZ2", "NZ10", "NZ11")}, abs=1e-9), y


@pytest.fixture(scope="module")
def no_otr():
    """The same build without this item (both 2001 levels 0): what No. 2 counts (0023: what was paid)."""
    return B.build(replace(B.CENTRAL, otr_nz2_level_gbp_m=0.0, otr_nz10_level_gbp_m=0.0))


def test_7_no2_unchanged_and_bridge_inputs_equal_the_difference(central, no_otr):
    """Spec test 7: No. 2 does not net (0097; it bridges). The bridge-input lines nz2/nz10_on_the_road_gbp_m equal the
    No. 2 - RB difference in NZ2 and NZ10 to 1e-9, so No. 2's NZ2 and NZ10 (RB's line plus its netted-off part) equal
    their values without this item, every year."""
    for y in B.YEARS:
        a, n, o = _lines(central, y), _lines(no_otr, y), central[y]["on_the_road"]
        assert o["nz2_on_the_road_gbp_m"] == pytest.approx(n["NZ2"] - a["NZ2"], abs=1e-9), y
        assert o["nz10_on_the_road_gbp_m"] == pytest.approx(n["NZ10"] - a["NZ10"], abs=1e-9), y


def test_8_only_nz2_nz10_and_nz11_move(central, no_otr):
    """Spec test 8 (and acceptance): every RB line other than NZ2, NZ10 and NZ11 equals its value without this item
    to 1e-9; the gap moves by exactly the three lines; nothing moves on the fossil side."""
    for y in B.YEARS:
        a, n = _lines(central, y), _lines(no_otr, y)
        assert {k: v for k, v in a.items() if k not in ("NZ2", "NZ10", "NZ11")} == pytest.approx(
            {k: v for k, v in n.items() if k not in ("NZ2", "NZ10", "NZ11")}, abs=1e-9), y
        moved = sum(a[i] - n[i] for i in ("NZ2", "NZ10", "NZ11"))
        assert central[y]["totals"]["gap_gbp_m"] - no_otr[y]["totals"]["gap_gbp_m"] == pytest.approx(moved, abs=1e-9), y
        assert central[y]["totals"]["go_gbp_m"] == pytest.approx(no_otr[y]["totals"]["go_gbp_m"], abs=1e-9), y


def test_8b_run_file_block_carries_the_netted_off_lines_nominal_and_2024(central):
    """Spec D8: the netted-off parts are exported as their own engine lines, nominal and 2024 £, by year, through
    the run-file block hook (02), so 27 builds No. 2's bridge rows from the run; the inputs carry their status."""
    from gascf import export_v4 as X
    from gascf import otr_blocks
    assert "gascf.otr_blocks" in X.BLOCK_MODULES
    blk = otr_blocks.on_the_road_block(central)
    for y in B.YEARS:
        r = blk["years"][str(y)]
        for k in ("nz2_on_the_road_gbp_m", "nz10_on_the_road_gbp_m"):
            assert r[k] == central[y]["on_the_road"][k], (y, k)
            assert r[k.replace("_gbp_m", "_gbp_m_2024")] == pytest.approx(to_real(r[k], y, 2024), rel=1e-12), (y, k)
    st = {i["name"]: i["status"] for i in blk["inputs"]}
    assert st == {"ffl_level_fy2001_02_gbp_m": "SOURCED", "ffl_geography_gb": "SOURCED",
                  "eesop_spend_gbp_m": "INTERIM_APPROVED", "eesop_electricity_share": "INTERIM_APPROVED"}


def test_8c_run_file_block_carries_the_vat_part_and_it_equals_the_engines_vat(central):
    """Spec D8 / ticket 26 (0097): option (a). The block also carries each netting's VAT part as its own exported
    field, nominal and 2024, so the three pre2002_netting figures keys read what the engine actually charged rather
    than re-deriving it. The exported VAT equals the NZ11 move the engine made for that netting, to 1e-9, and
    pre-VAT plus VAT equals the incl-VAT amount the build removed (line + its VAT)."""
    from gascf import otr_blocks
    off2 = B.build(replace(B.CENTRAL, otr_nz2_level_gbp_m=0.0))
    off10 = B.build(replace(B.CENTRAL, otr_nz10_level_gbp_m=0.0))
    blk = otr_blocks.on_the_road_block(central)
    for y in B.YEARS:
        r = blk["years"][str(y)]
        l, l2, l10 = _lines(central, y), _lines(off2, y), _lines(off10, y)
        nz2_vat, nz10_vat = r["nz2_on_the_road_vat_gbp_m"], r["nz10_on_the_road_vat_gbp_m"]
        assert nz2_vat == pytest.approx(l2["NZ11"] - l["NZ11"], abs=1e-9), y
        assert nz10_vat == pytest.approx(l10["NZ11"] - l["NZ11"], abs=1e-9), y
        assert r["nz2_on_the_road_gbp_m"] + nz2_vat == pytest.approx(
            (l2["NZ2"] - l["NZ2"]) + (l2["NZ11"] - l["NZ11"]), abs=1e-9), y
        assert r["nz10_on_the_road_gbp_m"] + nz10_vat == pytest.approx(
            (l10["NZ10"] - l["NZ10"]) + (l10["NZ11"] - l["NZ11"]), abs=1e-9), y
        for k in ("nz2_on_the_road_vat_gbp_m", "nz10_on_the_road_vat_gbp_m"):
            assert r[k.replace("_gbp_m", "_gbp_m_2024")] == pytest.approx(to_real(r[k], y, 2024), rel=1e-12), (y, k)


def test_interim_check_prints_each_eesop_row_and_warns_only_above_0_2bn(capsys):
    """Spec D8 / acceptance: tools/checks/otr_interim_sensitivity.py prints how far RB 2002-24 (2024 £bn) moves for
    EESoP spend ±10/20/30% and the electricity split at 50%, with a warning line above £0.2bn; it prints only.
    Linear in the level (s35: about -0.0430 £bn per £1m of electricity L incl. VAT): ±10% 0.11, ±20% 0.21,
    ±30% 0.32, split 50% 0.12 (ticket 26 table)."""
    from tools.checks import otr_interim_sensitivity as chk
    rows = chk.rows()
    got = {r["case"]: round(abs(r["move_bn"]), 2) for r in rows}
    assert got == {"spend -10%": 0.11, "spend +10%": 0.11, "spend -20%": 0.21, "spend +20%": 0.21,
                   "spend -30%": 0.32, "spend +30%": 0.32, "split 50%": 0.12}
    chk.main()
    out = capsys.readouterr().out
    warned = {ln.split("WARNING: ")[1].split(" moves")[0] for ln in out.splitlines() if "WARNING: " in ln}
    assert warned == {"spend -20%", "spend +20%", "spend -30%", "spend +30%"}


def test_9_shared_pattern_runs_ticket_12s_rate_x_volume_fixture():
    """Spec test 9 (0101: one netting pattern): ticket 12's rate x volume fixture (tests/fixtures/otr_rate_x_volume.json,
    the same file test_ccl_0044 reads) runs through the same function as NZ2 and NZ10 here."""
    import json
    from pathlib import Path
    f = json.loads((Path(__file__).resolve().parent / "fixtures/otr_rate_x_volume.json").read_text())
    ints = lambda d: {int(k): v for k, v in d.items()}            # noqa: E731
    r = OTR.net(ints(f["counted"]), f["rate_2001_gbp_per_kwh"], mode="rate_x_volume", indexation="real_cpih",
                volume=ints(f["volume_gwh"]), index=ints(f["index"]), applies_to="NZ8")
    assert r["counted"] == pytest.approx(ints(f["expected_counted"]), abs=1e-9)
    assert B._otr is OTR                       # the engine's NZ2/NZ10 netting uses this same module
