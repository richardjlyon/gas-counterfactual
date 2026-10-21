"""s36 ticket 04: docstrings and notes only (go5-docstring.md, 0024; 0094; CM exemption date, 0092).
No figure moves.

Seams: `bills.CENTRAL`, the v4-s35 run file's meta, `bills.build` GO5, `clock_export.grid_series`,
`grid.go5.__doc__`, `household_bill` notes."""
import json
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import clock_export as CE
from gascf import grid

ROOT = Path(__file__).parents[1]
S35 = json.loads((ROOT / "out/v4/2026-10-14-s35.json").read_text())


def test_engine_central_tnuos_gen_share_is_removed():
    """go5-docstring.md test 1 (light half): engine central is 'removed' (0024)."""
    assert B.CENTRAL.tnuos_gen == "removed"
    assert S35["meta"]["central_settings"]["tnuos_gen"] == "removed"


def test_clock_export_grid_is_included():
    """go5-docstring.md test 2: the Clock export keeps the generators' share in."""
    assert CE.GEN_SHARE == "included"
    go = grid.go5(B.PRICE_BASE, B.YEARS, index="rpi", gen_share="included")
    ys = CE.grid_series()["years"]
    for y in B.YEARS:
        row = ys[y] if y in ys else ys[str(y)]
        assert row["central_gbp"] == pytest.approx(go[y]["gbp_m"] * 1e6, rel=1e-9), y


def test_go5_docstring_states_clock_scope_and_0024():
    """go5-docstring.md test 3: the gen_share paragraph says 'included' is the Clock export's only,
    and names 0024 (scope, not exact text)."""
    doc = grid.go5.__doc__
    para = doc[doc.index("gen_share:"):]
    assert "clock" in para.lower() and "0024" in para
    assert "'included' (central" not in doc


def test_household_bill_cm_exemption_date():
    """CM EII exemption in force from 1 Apr 2024 (SI 2024/434); no '(if any, 2024 on)'."""
    from gascf import household_bill as HB
    text = " ".join(HB.gaps())
    assert "1 Apr 2024" in text and "SI 2024/434" in text and "2024 on)" not in text


def test_build_go5_is_the_removed_series():
    """go5-docstring.md test 1 (heavy half): the central build's GO5 = grid.go5(..., 'rpi', 'removed')."""
    b = B.build()
    go = grid.go5(B.PRICE_BASE, B.YEARS, "rpi", "removed")
    for y in B.YEARS:
        assert B.val(b[y], "GO5") == pytest.approx(go[y]["gbp_m"], rel=1e-12), y
