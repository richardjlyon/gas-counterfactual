"""Decision 0122, needs file §5 (optional): a plain-English label on every row of `table_one_at_a_time` (and so of the
chapter tables `table_choice1`..`8`), so the writer need not read engine options such as `bal_share=0.4192...`,
`wholesale_pre2010`, `kept_price=fleet_avg`, `residual=fuelhh`, `cm_rule=full` or `transport=False`."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.figures_keys import range as R  # noqa: E402

# v4-s37 (0144): the plain labels follow the switch registry, so they are read from the run file of this engine
# (v4-s36's file carries the supply-only feedback rows 0144 removed)
S36 = ROOT / "out/v4/2026-10-20-s37.json"
ENGINE_WORDS = ("fuelhh", "fleet_avg", "bal_share", "bal_option", "cm_rule", "transport=", "kept_price", "moe=",
                "go5_index", "otr_", "ccl_baseline", "wholesale_pre2010", "=", "True", "False")


@pytest.fixture(scope="module")
def table():
    return R.table(json.loads(S36.read_text()))


def test_every_row_has_a_plain_label_with_no_engine_words(table):
    for r in table:
        p = r["plain_option"]
        assert p and p[0].isupper(), r["option"]
        assert not any(w in p for w in ENGINE_WORDS), (r["option"], p)
        assert "—" not in p


def test_plain_labels_are_distinct_within_a_switch(table):
    seen = {}
    for r in table:
        seen.setdefault(r["switch"], []).append(r["plain_option"])
    for sw, labs in seen.items():
        assert len(labs) == len(set(labs)), sw


def test_balancing_rows_name_the_baseline_and_the_financial_year_of_the_share(table):
    bal = [r for r in table if r["switch"].startswith("balancing")]
    assert len(bal) == 5
    for r in bal:
        assert re.search(r"FY20\d\d/\d\d", r["plain_option"]), r["plain_option"]
        assert ("NAO" in r["plain_option"]) == (r["settings"]["bal_option"] == "nao_2005")


def test_chapter_tables_carry_the_same_plain_labels():
    run = json.loads(S36.read_text())
    v = R.values(run)
    for c in range(1, 9):
        for r in v[f"table_choice{c}"]:
            assert r["plain_option"]
