"""v4-s41 point release (decision 0184, card [internal ticket]): two added series in table_results_by_year, the actual bill
and the road's bill per MWh billed, 2002-25 (2025 provisional), £/MWh in 2024 prices. Built from the run file's own
unrounded bills (bills[y].totals.nz_real, .go_real) over the billed volume (years[y].volume_twh), the volume the
paper already uses for per-MWh figures (R19 (a), decision 0163). No method change, no new input, and no v4-s40
figure moves. All run on the released v4-s40 run file (light); expected values come from the released v4-s40
figures file, never from the new code."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S40_RUN = ROOT / "out/v4/2026-10-23-s40.json"
S40_FIGS = ROOT / "out/figures/v4-s40.json"
NEW = ("nz_bill_gbp_per_mwh", "rb_bill_gbp_per_mwh")
YEARS = list(range(2002, 2026))


@pytest.fixture(scope="module")
def run():
    return json.loads(S40_RUN.read_text())


@pytest.fixture(scope="module")
def rel():
    return json.loads(S40_FIGS.read_text())


@pytest.fixture(scope="module")
def built(tmp_path_factory, rel):
    """The full figures file the release path writes (tools.figures.write, release mode) from the v4-s40 run file."""
    from tools import figures as F
    out = tmp_path_factory.mktemp("s41") / "figures.json"
    F.write(S40_RUN, out, release=True, commit=rel["meta"]["commit"])
    return json.loads(out.read_text())


def _rows(fig):
    return {r["year"]: r for r in fig["keys"]["table_results_by_year"]["value"]}


def test_both_series_in_every_year_2002_25(built):
    t = built["keys"]["table_results_by_year"]["value"]
    assert [r["year"] for r in t] == YEARS
    for r in t:
        for k in NEW:
            assert isinstance(r[k], float) and r[k] > 0, (r["year"], k)


def test_per_mwh_is_the_released_bill_over_the_billed_volume_every_year(built, rel, run):
    """Expected: the released v4-s40 bill (£bn, 2024 prices) x 1,000 / the run's billed volume V (TWh), for all 24
    years; and V is the volume the released per-MWh gap table already prints."""
    r40 = _rows(rel)
    V = {r["year"]: r["volume_twh"] for r in run["years"]}
    vol_printed = {r["year"]: r["volume_billed_twh"] for r in rel["keys"]["table_gap_per_mwh_by_year"]["value"]}
    got = _rows(built)
    for y in YEARS:
        assert V[y] == vol_printed[y], y
        assert got[y]["nz_bill_gbp_per_mwh"] == pytest.approx(r40[y]["nz_bill_gbp_bn"] * 1e3 / V[y], rel=1e-15), y
        assert got[y]["rb_bill_gbp_per_mwh"] == pytest.approx(r40[y]["rb_bill_gbp_bn"] * 1e3 / V[y], rel=1e-15), y


def test_the_two_per_mwh_series_differ_by_the_released_gap_per_mwh(built, rel):
    """Cross-check against an existing released series: actual less the road, per MWh billed, is the released gap
    per MWh billed (table_gap_per_mwh_by_year.billed_gbp_mwh) in every year."""
    gap = {r["year"]: r["billed_gbp_mwh"] for r in rel["keys"]["table_gap_per_mwh_by_year"]["value"]}
    got = _rows(built)
    for y in YEARS:
        assert got[y]["nz_bill_gbp_per_mwh"] - got[y]["rb_bill_gbp_per_mwh"] == pytest.approx(gap[y], abs=1e-9), y


def test_2024_worked_value(built):
    """A literal worked by hand from released v4-s40 (nz_bill_gbp_bn 2024 / volume_billed_twh 2024 x 1,000), to the
    cent."""
    r = _rows(built)[2024]
    exp = json.loads(S40_FIGS.read_text())
    nz = {x["year"]: x for x in exp["keys"]["table_results_by_year"]["value"]}[2024]["nz_bill_gbp_bn"]
    v = {x["year"]: x for x in exp["keys"]["table_gap_per_mwh_by_year"]["value"]}[2024]["volume_billed_twh"]
    assert round(r["nz_bill_gbp_per_mwh"], 2) == round(nz * 1000 / v, 2)


def test_2025_flagged_provisional_as_the_other_2025_rows(built, rel):
    got, r40 = _rows(built), _rows(rel)
    for y in YEARS:
        assert got[y]["provisional"] is (y == 2025)
        assert got[y]["provisional"] is r40[y]["provisional"]


def test_columns_meta_names_both_series_with_source_and_units(built):
    cols = built["keys"]["table_results_by_year"]["meta"]["columns"]
    by = {c["name"]: c for c in cols}
    assert [c["name"] for c in cols][-2:] == list(NEW)
    assert by["nz_bill_gbp_per_mwh"]["source"].startswith("bills[y].totals.nz_real")
    assert by["rb_bill_gbp_per_mwh"]["source"].startswith("bills[y].totals.go_real")
    for k in NEW:
        assert "years[y].volume_twh" in by[k]["source"]
        assert by[k]["units"] == "£/MWh, 2024 prices"
    assert not any("group" in c["source"] for c in cols)


def test_every_v4_s40_key_is_unchanged(built, rel):
    """Remove the two added columns and the figures file the release path writes from the v4-s40 run file is the
    released v4-s40 figures file: every key, every value, every label, byte for byte as written."""
    b = json.loads(json.dumps(built))
    t = b["keys"]["table_results_by_year"]
    for r in t["value"]:
        for k in NEW:
            r.pop(k, None)
    t["meta"]["columns"] = [c for c in t["meta"]["columns"] if c["name"] not in NEW]
    # v4-s42 (card [internal ticket]): Annex E's change log is read from reference/change_log_v4_s39.json, to which v4-s42
    # appends its own steps (decision 0195). Take those out and recompute the two sums the reader derives from them;
    # every v4-s40 step, and every other key, is still compared byte for byte.
    ae = b["keys"]["annex_e_change_log"]["value"]
    # v4-s43 (card [internal ticket]): v4-s43 appends its step (decision 0197) the same way; taken out the same way.
    ae["steps"] = [s for s in ae["steps"] if s.get("release") not in ("v4-s42", "v4-s43")]
    measured = [s["headline_change_gbp_bn"] for s in ae["steps"] if s["headline_change_gbp_bn"] is not None]
    ae["sum_of_measured_steps_gbp_bn"] = sum(measured)
    total = b["keys"]["headline_2002_24_gbp_bn"]["value"]
    ae["unexplained_gbp_bn"] = total - ae["baseline"]["headline_2002_24_gbp_bn"] - sum(measured)
    assert set(b["keys"]) == set(rel["keys"])
    changed = [k for k in rel["keys"] if b["keys"][k] != rel["keys"][k]]
    assert changed == []
    assert b == rel
    assert json.dumps(b, indent=1, allow_nan=False, ensure_ascii=False) == S40_FIGS.read_text()
