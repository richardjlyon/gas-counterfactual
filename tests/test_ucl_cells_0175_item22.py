"""0175 item 22 (b) (card [internal ticket], sweep-flags row 5; 0100): every pinned UCL cell prints by a sourced key.

The UCL preprint 290 v1 tables that do not add (analyst's ucl-cells.md, [internal ticket]): 8 cells over the strict rounding
rule, 6 over the looser one. Every one carries in data/figures/sourced.yaml its printed result, the sum of its printed
terms, the difference and the rounding allowance under both rules, plus the counts under each counting option, so the
paper can print whichever Richard picks (0175 item 22: "NOT RULED: how many to print").

Checked against two things the entries are not built from:
- the analyst's figures, transcribed by eye against 300 dpi renders (ucl-cells.md items 1-8), as literals here;
- the committed text layer of the hashed PDF, read again here (tools/ucl_layout.py).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf.figures import load_sourced  # noqa: E402
from tools import ucl_layout as L  # noqa: E402

SOURCED = ROOT / "data/figures/sourced.yaml"
PDF = ROOT / "data/raw/s36/ucl-oshea/oshea-ucloe-preprint-290-v1.pdf"

# ucl-cells.md items 1-8: (printed, sum of terms, n terms), £bn as printed
ANALYST = {
    "t1_r2022_total": (3.9, 4.7, 2), "t1_total_cfd": (5.2, 5.9, 7), "t9_total_c4": (104.3, 104.6, 3),
    "t10_total_c1": (138.3, 133.4, 14), "t10_total_c3": (41.8, 47.6, 14), "t10_total_c6": (12.8, 18.7, 14),
    "t10_total_c7": (96.4, 85.6, 14), "t10_total_c9": (96.4, 85.6, 14),
}
COUNTS = {"strict_count": 8, "strict_tables": 3, "loose_count": 6, "loose_tables": 2, "on_loose_line_count": 2,
          "strict_count_excl_t10_c9": 7, "strict_total_rows_count": 4}


@pytest.fixture(scope="module")
def S():
    return load_sourced(SOURCED)


def test_text_layer_is_of_the_hashed_pdf():
    assert hashlib.sha256(PDF.read_bytes()).hexdigest().startswith("d7fa85732a2b30a3")
    assert hashlib.sha256(L.LAYOUT.read_bytes()).hexdigest() == \
        "0cc830a7cdf8f5e14b429b486247e23fea352d1617f7427d2de99168161fb258"


@pytest.mark.parametrize("iid", sorted(ANALYST))
def test_every_pinned_cell_has_its_keys_and_they_match_the_analyst(S, iid):
    printed, total, n = ANALYST[iid]
    k = f"sourced.ucl_{iid}"
    assert S[f"{k}_printed_gbp_bn"]["value"] == pytest.approx(printed, abs=1e-9)
    assert S[f"{k}_cells_sum_gbp_bn"]["value"] == pytest.approx(total, abs=1e-9)
    assert S[f"{k}_diff_gbp_bn"]["value"] == pytest.approx(printed - total, abs=1e-9)
    assert S[f"{k}_bound_strict_gbp_bn"]["value"] == pytest.approx(0.05 * (n + 1), abs=1e-9)
    assert S[f"{k}_bound_loose_gbp_bn"]["value"] == pytest.approx(0.1 * n, abs=1e-9)
    assert len(S[f"{k}_cells_sum_gbp_bn"]["inputs"]) == n
    for suffix in ("printed", "cells_sum", "diff", "bound_strict", "bound_loose"):
        e = S[f"{k}_{suffix}_gbp_bn"]
        assert e["section"] == "3" and e["status"] == "SOURCED" and e["claims_id_tbc"] is True
        assert ("derived" in e) == (suffix != "printed"), (iid, suffix)


@pytest.mark.parametrize("iid", sorted(ANALYST))
def test_every_input_and_printed_cell_is_in_the_text_layer(S, iid):
    t = iid.split("_")[0].removeprefix("t")
    rows = L.table(t)
    every = {c for r in rows.values() for c in r}
    k = f"sourced.ucl_{iid}"
    assert f"{S[f'{k}_printed_gbp_bn']['value']:.1f}" in rows["Total"] + rows.get("2022", [])
    for v in S[f"{k}_cells_sum_gbp_bn"]["inputs"]:
        assert v in every, (iid, v)


def test_counts_under_each_rule_and_option(S):
    for k, v in COUNTS.items():
        assert S[f"sourced.ucl_discrepancies_{k}"]["value"] == v, k
