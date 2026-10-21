"""Ticket 28 (0092): EII shift estimate keys, ported from b-items-calc/b18_eii_shift.py onto the run file's
RO, FiT, CfD and CM lines. Seam: `tools.figures.generate(run)`. v4-s35 values are references (0092: readings
A £0.89bn, B £1.03bn, 2018-24, 2024 prices), re-pinned on the s36 release run (35), never loosened."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

S35 = ROOT / "out/v4/2026-10-14-s35.json"


@pytest.fixture(scope="module")
def built():
    return F.generate(json.loads(S35.read_text()))


def test_eii_shift_on_s35_lines_matches_0092(built):
    """0092 as printed: £0.89bn and £1.03bn (±0.002 stands)."""
    assert built["keys"]["eii_shift_2018_24_low"]["value"] == pytest.approx(0.895, abs=0.002)
    assert built["keys"]["eii_shift_2018_24_high"]["value"] == pytest.approx(1.032, abs=0.002)


def test_eii_shift_pinned_to_the_0060_domestic_share_on_s35_lines(built):
    """EIC approval 17 Oct 2026 (b-items/eii-domestic-share-source.md): the domestic share is the run-file field
    bills[y].netzero_on_household_bill_per_household.domestic_share at full precision (0060, DUKES 2026 Table 5.2
    'Domestic [note 6]' over 5.5.D), not the 3-decimal NZ11 note text. v4-s35: A £929.57m, B £1,072.06m (2025 money),
    £0.8952bn and £1.0324bn (2024 prices). Re-pinned on the s36 release run (35), never loosened."""
    from tools.figures_keys import eii_shift as E
    run = json.loads(S35.read_text())
    assert E.shift_gbp_m(run, "A") == pytest.approx(929.57, abs=0.005)
    assert E.shift_gbp_m(run, "B") == pytest.approx(1072.06, abs=0.005)
    assert built["keys"]["eii_shift_2018_24_low"]["value"] == pytest.approx(0.8952, abs=0.00005)
    assert built["keys"]["eii_shift_2018_24_high"]["value"] == pytest.approx(1.0324, abs=0.00005)


def test_eii_shift_metadata_names_the_domestic_share_source(built):
    for k in ("eii_shift_2018_24_low", "eii_shift_2018_24_high"):
        assert built["keys"][k]["meta"]["sources"]["domestic_share"] == "dukes-5.2; dukes-5.5D (0060)", k
