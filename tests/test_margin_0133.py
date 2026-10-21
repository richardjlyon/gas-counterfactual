"""Decision 0133 (Richard Lyon, 20 Oct 2026: "a"): the reliability margin is the midpoint of NESO's T-1 2027/28
recommendation (ECR 2026 p.5, "de-rated margin in the range 4 to 5 GW") divided by NESO's 2027/28 Base Case peak
(ECR 2026 Data Workbook, Figure B1, Base Case 2026 ACS peak, 61 GW). The low and high ends use the same peak.

Before 0133 the engine divided by the 2030/31 peak (64.2 GW) and called the quote T-4: 7.0% instead of 7.4%.
The expected values below are literals read from the two source files, not from the engine.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from gascf import capacity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Literals from the sources (read 20 Oct 2026):
T1_RANGE_GW = (4.0, 5.0)        # ECR 2026 p.5, T-1 for 2027/28: "a de-rated margin in the range 4 to 5 GW"
PEAK_2027_28_GW = 61.0          # ECR 2026 Data Workbook, Figure B1, row "Base Case 2026", column "2027/28"
PEAK_2030_31_GW = 64.2          # same row, column "2030/31": the peak the engine wrongly used before 0133


def test_margin_is_the_t1_range_over_the_matching_2027_28_peak():
    assert capacity.margin_fraction("low") == pytest.approx(T1_RANGE_GW[0] / PEAK_2027_28_GW, rel=1e-12)
    assert capacity.margin_fraction("central") == pytest.approx(sum(T1_RANGE_GW) / 2 / PEAK_2027_28_GW, rel=1e-12)
    assert capacity.margin_fraction("high") == pytest.approx(T1_RANGE_GW[1] / PEAK_2027_28_GW, rel=1e-12)
    # as printed: 6.6 / 7.4 / 8.2%
    assert [round(100 * capacity.margin_fraction(w), 1) for w in ("low", "central", "high")] == [6.6, 7.4, 8.2]


def test_margin_is_not_divided_by_the_2030_31_peak():
    assert capacity.margin_fraction("central") != pytest.approx(4.5 / PEAK_2030_31_GW, rel=1e-6)


def test_the_peak_is_a_registered_input_with_source_and_locator():
    p = capacity.MARGIN_PEAK
    assert p["delivery_year"] == "2027/28" == capacity.MARGIN_DELIVERY_YEAR
    assert p["value_gw"] == PEAK_2027_28_GW
    assert "Figure B1" in p["locator"] and "Base Case 2026" in p["locator"] and "2027/28" in p["locator"]
    assert "Electricity Capacity Report 2026" in p["source"]
    assert capacity.read_peak_base_case()["2027/28"] == PEAK_2027_28_GW     # the workbook agrees
    assert capacity.read_peak_base_case()["2030/31"] == PEAK_2030_31_GW


def test_margin_refuses_a_workbook_that_disagrees_with_the_registered_peak(monkeypatch):
    real = capacity.read_peak_base_case()
    monkeypatch.setattr(capacity, "read_peak_base_case", lambda: real | {"2027/28": 61.5})
    with pytest.raises(ValueError, match="2027/28"):
        capacity.margin_fraction("central")


def test_the_quote_is_the_t1_2027_28_recommendation_on_p5_not_t4():
    import pymupdf
    doc = pymupdf.open(capacity.ECR_PDF)
    norm = lambda s: re.sub(r"\s+", " ", s)  # noqa: E731
    p5, p7 = norm(doc[4].get_text()), norm(doc[6].get_text())
    assert capacity.MARGIN_QUOTE in p5
    assert "T-1 auction for delivery in 2027/28" in p5
    assert capacity.MARGIN_QUOTE not in p7                      # the T-4 2030/31 page says "around 4 GW"
    assert capacity.MARGIN_GW_RANGE == T1_RANGE_GW
    loc = capacity.MARGIN_RANGE_LOCATOR
    assert "p.5" in loc and "T-1" in loc and "2027/28" in loc and "T-4" not in loc


def test_module_text_no_longer_calls_the_quote_t4_or_uses_2030_31():
    doc = capacity.__doc__
    assert "T-4 recommendation" not in doc and "64.2" not in doc
    assert "T-1" in doc and "2027/28" in doc and "61" in doc


def _pcts():
    return tuple(f"{100 * capacity.margin_fraction(w):.1f}%" for w in ("low", "central", "high"))


def test_range_and_plain_labels_print_the_engines_margins():
    from gascf import bills as B
    from tools.figures_keys import range as R
    lo, mid, hi = _pcts()
    label = f"spare margin ({lo} / {hi})"
    assert label in B.SWITCHES
    assert not [k for k in B.SWITCHES if k.startswith("spare margin") and k != label]
    assert R.SENS_ROWS["sens_margin_low_2002_24_gbp_bn"][1] == label
    assert lo in R.SENS_ROWS["sens_margin_low_2002_24_gbp_bn"][3]
    assert R.PLAIN[("margin", "low")] == f"Spare plant margin of {lo} (central {mid})"
    assert R.PLAIN[("margin", "high")] == f"Spare plant margin of {hi} (central {mid})"


def test_figures_margin_keys_follow_the_engine():
    from tools import figures as F
    from tools.figures_keys import core
    run = json.loads((ROOT / "out/v4/2026-10-20-s36.json").read_text())
    k = F.generate(run, modules=[core])["keys"]
    assert k["margin_central_pct"]["value"] == pytest.approx(100 * 4.5 / PEAK_2027_28_GW, rel=1e-12)
    assert k["margin_low_pct"]["value"] == pytest.approx(100 * 4.0 / PEAK_2027_28_GW, rel=1e-12)
    assert k["margin_high_pct"]["value"] == pytest.approx(100 * 5.0 / PEAK_2027_28_GW, rel=1e-12)


def test_pre_0133_helper_gives_the_old_margin_and_then_restores_0133():
    """The s35-reproduction guards run on tests/_pre_0133.py; it must give exactly the old margin and leave 0133's."""
    from _pre_0133 import pre_0133_margin
    with pre_0133_margin():
        assert capacity.margin_fraction("central") == pytest.approx(4.5 / PEAK_2030_31_GW, rel=1e-12)
    assert capacity.margin_fraction("central") == pytest.approx(4.5 / PEAK_2027_28_GW, rel=1e-12)
    assert capacity.MARGIN_DELIVERY_YEAR == "2027/28" and capacity.MARGIN_PEAK["value_gw"] == PEAK_2027_28_GW


def test_sourced_keys_carry_the_range_and_the_peak_and_agree_with_the_engine():
    from gascf import figures as GF
    e = GF.load_sourced(ROOT / "data/figures/sourced.yaml")
    peak = e["sourced.ecr2026_base_case_peak_2027_28_gw"]
    lo, hi = e["sourced.ecr2026_t1_derated_margin_low_gw"], e["sourced.ecr2026_t1_derated_margin_high_gw"]
    assert peak["value"] == PEAK_2027_28_GW and "Figure B1" in peak["locator"]
    assert (lo["value"], hi["value"]) == T1_RANGE_GW and "p.5" in lo["locator"] and "p.5" in hi["locator"]
    assert peak["engine_check"] == "margin_peak" and lo["engine_check"] == "margin_low_gw"
    assert hi["engine_check"] == "margin_high_gw"
