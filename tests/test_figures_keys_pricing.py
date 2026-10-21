"""Ticket 47: the rb.pricing.* figures keys read the run-file pricing.qep_dayahead_ratio block (never a typed
value), print the three ratios bare to 3 dp, and carry the two min/max years the draft §9.2 types. Block missing
gives None (lead builder's ruling for 46-48; the release check at 35 stops on a None PENDING key)."""
from __future__ import annotations

import pytest

from tools import figures as F
from tools.figures_keys import pricing

MEAN, MINV, MAXV = 1.0646459, 0.7384363, 1.4055864


def _run(with_block=True, minyear=2021, maxyear=2020):
    r = {"meta": {"engine_version": "test"}}
    if with_block:
        r["pricing"] = {"qep_dayahead_ratio": {
            "mean_2010_25": MEAN,
            "min_2010_25": {"value": MINV, "year": minyear},
            "max_2010_25": {"value": MAXV, "year": maxyear}}}
    return r


def _keys(run=None):
    return F.generate(run or _run(), modules=[pricing])["keys"]


def test_rb_pricing_keys_read_the_run_block():
    k = _keys()
    assert k["rb.pricing.qep_dayahead_ratio_2010_25"]["value"] == MEAN
    assert k["rb.pricing.qep_dayahead_ratio_min_2010_25"]["value"] == MINV
    assert k["rb.pricing.qep_dayahead_ratio_max_2010_25"]["value"] == MAXV
    m = k["rb.pricing.qep_dayahead_ratio_2010_25"]["meta"]
    assert m["basis"] == "modelled" and m["ticket"] == "47" and m["units"] == "ratio"
    assert m["period"] == "2010-2025" and m["year_basis"] == "calendar"
    assert m["run_field"] == "pricing.qep_dayahead_ratio.mean_2010_25"
    assert m["was_claims_id"] == "CR-S008" and m["provisional"] is True and m["status"] == "PENDING"
    assert any("QEP" in s and "3.2.1 (Annual)" in s and "F32 to F47" in s for s in m["sources"])
    assert any("Ofgem WMI" in s and "YFsS4g98P" in s for s in m["sources"])
    mn = k["rb.pricing.qep_dayahead_ratio_min_2010_25"]["meta"]
    mx = k["rb.pricing.qep_dayahead_ratio_max_2010_25"]["meta"]
    assert mn["was_claims_id"] == "CR-S050" and mn["year"] == 2021
    assert mx["was_claims_id"] == "CR-S051" and mx["year"] == 2020
    assert mn["run_field"] == "pricing.qep_dayahead_ratio.min_2010_25.value"
    assert mx["run_field"] == "pricing.qep_dayahead_ratio.max_2010_25.value"


def test_block_missing_gives_none_for_every_key():
    k = _keys(_run(with_block=False))
    for name in pricing.DECLARED:
        assert k[name]["value"] is None


def test_min_year_is_2021_as_the_text_types():
    k = _keys()
    v = k["rb.pricing.qep_dayahead_ratio_min_year_2010_25"]["value"]
    assert v == 2021, f"run gives {v}; §9.2 L493 types 2021; tell the Report writer; do not loosen"
    assert isinstance(v, int)
    m = k["rb.pricing.qep_dayahead_ratio_min_year_2010_25"]["meta"]
    assert m["print"] is False and m["units"] == "calendar year" and m["basis"] == "modelled"
    assert m["ticket"] == "47" and m["text_types"] == "2021" and "§9.2 L493" in m["locator"]


def test_max_year_is_2020_as_the_text_types():
    k = _keys()
    v = k["rb.pricing.qep_dayahead_ratio_max_year_2010_25"]["value"]
    assert v == 2020, f"run gives {v}; §9.2 L493 types 2020; tell the Report writer; do not loosen"
    m = k["rb.pricing.qep_dayahead_ratio_max_year_2010_25"]["meta"]
    assert m["print"] is False and m["text_types"] == "2020" and "§9.2 L493" in m["locator"]


def test_ratio_keys_print_bare_to_3_dp():
    k = _keys()
    want = {"rb.pricing.qep_dayahead_ratio_2010_25": (MEAN, "1.065"),
            "rb.pricing.qep_dayahead_ratio_min_2010_25": (MINV, "0.738"),
            "rb.pricing.qep_dayahead_ratio_max_2010_25": (MAXV, "1.406")}
    for name, (val, printed) in want.items():
        m = k[name]["meta"]
        assert m["print_dp"] == 3 and m["print_prefix"] == ""
        assert k[name]["value"] == val and k[name]["value"] != round(val, 3)   # figures.json unrounded
        filled = f"{m['print_prefix']}{round(val, m['print_dp']):.{m['print_dp']}f}"
        assert filled == printed
        assert "about" not in m["label"].lower()
        assert all("about" not in n.lower() for n in m.get("notes", []))
