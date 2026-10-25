"""Decision 0177 (card [internal ticket]; sweep-flags.md rows 3 and 4): release text that is false about the run is fixed at
source. Richard, 23 Oct 2026 (0177): "We cannot put a report out that's not that that is known to be not true."

- Row 3: Annex C's gas-feedback equation must describe the feedback as the engine runs it: both ways (M6 "both", dq
  signed), so a fall in years when the road burns less gas than Britain did. Checked against the v4-s40 run file.
- Row 4: the pooled 2002-04 early-years check label must not say "fails" while the run says it passed.

Light: reads the v4-s40 run file and the key modules only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
S40_RUN = ROOT / "out/v4/2026-10-23-s40.json"


@pytest.fixture(scope="module")
def run():
    return json.loads(S40_RUN.read_text())


def test_gas_feedback_equation_says_both_ways_as_the_engine_runs(run):
    from gascf import fossil_like_for_like as F
    from tools.figures_keys import annex_v11 as A
    eq = next(e for e in A.EQUATIONS if e["id"] == "gas_feedback")["equation"]
    assert F.M6_DEFAULT == "both"
    fb = {y: run["fleet"][y]["gas_feedback"] for y in run["fleet"] if run["fleet"][y].get("gas_feedback")}
    falls = [y for y, g in fb.items() if g.get("price_rise_frac", 0) < 0]
    rises = [y for y, g in fb.items() if g.get("price_rise_frac", 0) > 0]
    assert falls and rises, (falls, rises)                       # the run file has both: 2009 falls, 2024 rises
    assert "one way only" not in eq and "no fall" not in eq, eq
    assert "both ways" in eq, eq


def test_calibration_pooled_label_does_not_say_fails_when_the_run_passed(run):
    from tools.figures_keys import calibration as C
    v = C.values(run)
    label = C.DECLARED["calib_pooled_2002_04_pct"]["label"]
    passed_label = C.DECLARED["calib_pooled_2002_04_passed"]["label"]
    assert v["calib_pooled_2002_04_passed"] is True and v["calib_pooled_2002_04_pct"] < v["calib_limit_pct"]
    assert "fails" not in label and "disclosed failure" not in passed_label, (label, passed_label)
