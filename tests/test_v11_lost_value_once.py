"""§12.6 lost value, card [internal ticket] item 5: the same-in-both block was counted twice in the whole bill.

bills.py builds totals.go_gbp_m as the Reliable Britain lines plus the same-in-both block (s1_tot), so the old
denominator go_gbp_m + s1_gbp_m counted that block twice. 0082 measures the price rise "against the whole bill
customers pay": each line once. Expected values are summed from the bill lines themselves, and the literals come from
work/v1.1-lost-value/before_after.py (independent of lost_value's denominator) on the released v4-s37 run file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"


@pytest.fixture(scope="module")
def run():
    return json.loads(S37_RUN.read_text())


def _whole_bill_once(b: dict) -> float:
    return (sum(l["national_gbp_m_nominal"] for l in b["gasonly"])
            + sum(l["national_gbp_m_nominal"] for l in b["same_in_both"] if l["national_gbp_m_nominal"] is not None))


def test_go_total_already_holds_the_same_in_both_block(run):
    for y, b in run["bills"].items():
        assert b["totals"]["go_gbp_m"] == pytest.approx(_whole_bill_once(b), abs=1e-6), y


def test_price_rise_is_the_gap_over_the_whole_bill_counted_once(run):
    from tools.figures_keys import lost_value as K
    by = K.by_year(run)
    for y, b in run["bills"].items():
        assert by[y]["r"] == pytest.approx(b["totals"]["gap_gbp_m"] / _whole_bill_once(b), rel=1e-12), y
    assert by["2019"]["r"] == pytest.approx(0.3889, abs=5e-5)          # was 0.2843 with the block counted twice


def test_lost_value_on_v4_s37_inputs_with_the_bill_counted_once(run):
    from gascf import lost_value as lv
    est = lv.estimate(run)
    assert est["quoted"]["central"]["2002-2024"] == pytest.approx(8.2194, abs=5e-4)    # was 6.4421
    assert est["quoted"]["low"]["2002-2024"] == pytest.approx(2.9454, abs=5e-4)        # was 2.3229
    assert est["quoted"]["high"]["2002-2024"] == pytest.approx(10.2031, abs=5e-4)      # was 7.9785
    assert est["quoted"]["central"]["2025"] == pytest.approx(1.1849, abs=5e-4)         # was 0.9397
    assert est["straight_line"]["central"]["2002-2024"] == pytest.approx(9.2772, abs=5e-4)   # was 7.0698
    from gascf import deflator_cpih as dfl
    cp = dfl.cpih()
    k = cp[2024] / cp[int(run["meta"]["price_base"])]
    want = sum(lv._straight(-0.607, run["bills"][str(y)]["totals"]["gap_gbp_m"] / _whole_bill_once(run["bills"][str(y)]))
               * run["bills"][str(y)]["totals"]["gap_real_bn"] * k for y in range(2002, 2025))
    assert lv.total_bn(run, -0.607, "straight_line", range(2002, 2025)) == pytest.approx(want, rel=1e-12)
