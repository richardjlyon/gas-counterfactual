"""RB v1.1 F1 and F2 for Annex B (card [internal ticket] item 1, after W2; read-through items 49 and 84-98).

F1: each Annex B line carries its tag: measured, modelled or labelled estimate. The tag is the engine's own data basis
for that line and year (the weakest evidence among its inputs): "estimated" prints as "labelled estimate" (0007).
F2: each line carries its cash figure (£m, that year's money) beside the 2024-prices value, and each year carries its
data basis (outturn or provisional, the volume and wholesale bases, and which lines rest on which kind of figure).

Expected values come from the released v4-s37 figures.json (the 2024-prices values the cash must convert to) and from
literals of the engine's basis rules, never from the new code. Light: the released v4-s37 run file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"
S37_FIGS = ROOT / "out/figures/v4-s37.json"
TAGS = {"measured", "modelled", "labelled estimate", "no separate figure"}


@pytest.fixture(scope="module")
def run():
    return json.loads(S37_RUN.read_text())


@pytest.fixture(scope="module")
def annex_b(run):
    from tools.figures_keys import recut_0122 as R
    return R.values(run)["annex_b_annual_tables"]


@pytest.fixture(scope="module")
def released():
    return json.loads(S37_FIGS.read_text())["keys"]["annex_b_annual_tables"]["value"]


def test_f1_every_line_is_tagged(annex_b):
    for yr in annex_b:
        for r in yr["rows"]:
            assert r.get("tag") in TAGS, (yr["year"], r["id"])


def test_f1_tags_follow_the_engine_basis_rules(annex_b):
    tag = {(yr["year"], r["id"]): r["tag"] for yr in annex_b for r in yr["rows"]}
    for y in range(2002, 2026):
        assert tag[(y, "NZ4")] == "measured"           # CfD: LCCC actual payments (and zero before 2015)
        assert tag[(y, "NZ4b")] == "measured"
        assert tag[(y, "GO2")] == "modelled"           # backup inside GO1, a model line
        assert tag[(y, "GO3")] == "modelled"           # no carbon in Reliable Britain (brief 3.1)
        assert tag[(y, "NZ11")] == "modelled"          # VAT computed from the lines
    assert tag[(2005, "S1.metering")] == "no separate figure"     # 2004-06 metering sits inside supplier costs


def test_f2_cash_converts_to_the_released_2024_prices_value(run, annex_b, released):
    from gascf import deflator_cpih
    from gascf.figures import to_2024
    base = int(run["meta"]["price_base"])
    rel = {(yr["year"], r["id"]): r.get("value") for yr in released for r in yr["rows"]}
    n = 0
    for yr in annex_b:
        for r in yr["rows"]:
            if rel[(yr["year"], r["id"])] is None:
                assert "cash_gbp_m" not in r
                continue
            got = to_2024(deflator_cpih.to_real(r["cash_gbp_m"], yr["year"], base), run) / 1e3
            assert got == pytest.approx(rel[(yr["year"], r["id"])], rel=1e-12, abs=1e-12), (yr["year"], r["id"])
            n += 1
    assert n > 24 * 20


def test_f2_each_year_has_its_data_basis(run, annex_b):
    years = {r["year"]: r for r in run["years"]}
    for yr in annex_b:
        d = yr["data_basis"]
        assert d["status"] == ("provisional" if yr["year"] == 2025 else "outturn")
        assert d["volume_basis"] == years[yr["year"]]["volume_basis"]
        assert d["wholesale_basis"] == years[yr["year"]]["wholesale_basis"]
        ids = sorted(i for v in d["lines_by_tag"].values() for i in v)
        assert ids == sorted(r["id"] for r in yr["rows"])
        for t, v in d["lines_by_tag"].items():
            assert all(r["tag"] == t for r in yr["rows"] if r["id"] in v)


def test_f1_f2_change_no_released_number(annex_b, released):
    strip = lambda r: {k: v for k, v in r.items() if k not in ("tag", "cash_gbp_m", "label")}   # noqa: E731
    for a, b in zip(annex_b, released, strict=True):
        assert [strip(r) for r in a["rows"]] == [strip(r) for r in b["rows"]]
