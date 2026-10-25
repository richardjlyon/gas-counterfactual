"""v4-s40 item 9 (step-3 sheet item 9 (a); decision 0175, Richard Lyon 23 Oct 2026, "Yes." at 06:13:51 UTC to the
chief-executive's five-point question, verified first-hand on card [internal ticket]): wire and export the ruled checks
outside the range, with keys.

The rows are `bills.V11_COAL_ROWS` (decision 0163 R4 (b), R6 (a), R17 (a); 0166 item 4): kept coal paid the Capacity
Market rate from 2014, the £81/kW per five years life extension, the three closures-by-class rows and coal-hours
reading (ii). To v4-s39 they were defined but no export traversed them (review [internal ticket] item 9). The run file gets a
fourth `one_at_a_time` group, `method_checks`; each row gets a printed key and a change key, and no range key reads
the group, so none can set an end of the range.

Expected values are literals (the six row names as the code states them, a stand-in build, and the released v4-s37
run file's own 2025-to-2024 ratio, as tests/test_v11_held_rows.py), never the engine's output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gascf import bills as B  # noqa: E402

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"
TO_2024 = 141.10113097962292 / 146.51584706687706      # v4-s37 headline (2024 prices) / Σ run gap (2025 prices)

ROWS = (
    "kept coal paid the Capacity Market rate from 2014, fixed cost less margin before (R4 (b))",
    "kept coal life extension: assumption borrowed from gas plant (CEPA/GHD 2025, £81/kW per 5 years; R6 (a), R33)",
    "closures by class: biomass conversions on their real dates (R17 (a); classes R34 (a), 0164)",
    "closures by class: coal phase-out deadline closures on their real dates (R17 (a); classes R34 (a), 0164)",
    "closures by class: mixed-cause closures on their real dates (R17 (a))",
    "coal hours (ii): the 1,500-hour route also for Drax 1-4 and Lynemouth (check row, 0166)",
)
KEYS = {
    ROWS[0]: "check_r4b_kept_coal_cm_from_2014_2002_24_gbp_bn",
    ROWS[1]: "check_r6a_kept_coal_life_extension_2002_24_gbp_bn",
    ROWS[2]: "check_r17a_closures_biomass_conversion_2002_24_gbp_bn",
    ROWS[3]: "check_r17a_closures_coal_phase_out_deadline_2002_24_gbp_bn",
    ROWS[4]: "check_r17a_closures_mixed_2002_24_gbp_bn",
    ROWS[5]: "check_coal_hours_reading_ii_2002_24_gbp_bn",
}


def _fake_build(s):
    return {y: {"netzero": [], "fossil": [], "nz1c": {"national_gbp_m_nominal": 0.0},
                "totals": {"gap_real_bn": 1.0}} for y in B.YEARS}


def test_the_six_ruled_rows_are_the_method_checks():
    assert tuple(B.V11_COAL_ROWS) == ROWS
    assert B.METHOD_CHECKS is B.V11_COAL_ROWS
    for row in ROWS:
        assert row not in B.SWITCHES and row not in B.METHOD_SWITCHES and row not in B.HELD_SWITCHES


def test_one_at_a_time_has_a_method_checks_group_with_every_row():
    from gascf import one_at_a_time as O
    blk = O.block(_fake_build(B.CENTRAL), build=_fake_build, ranked={}, methods={}, held={})
    assert set(blk) == {"ranked", "methods_page", "held", "method_checks"}
    assert tuple(blk["method_checks"]) == ROWS
    for row in ROWS:
        assert len(blk["method_checks"][row]) == len(B.V11_COAL_ROWS[row]) == 1


def _run_with_checks(deltas: dict) -> dict:
    run = json.loads(S37_RUN.read_text())
    ys = [str(y) for y in B.YEARS]
    run["one_at_a_time"]["method_checks"] = {
        row: [{"settings": {}, "lines_moved_gbp_m_nominal": {},
               "gap_real_bn": {y: run["gap"][y]["national_gbp_bn_real"] + d for y in ys}}]
        for row, d in deltas.items()}
    return run


def test_each_check_has_a_printed_key_that_reads_its_row_and_cannot_set_a_range_end():
    from tools.figures_keys import method_checks as M
    run = _run_with_checks({row: 0.1 * (i + 1) for i, row in enumerate(ROWS)})
    v = M.values(run)
    for i, row in enumerate(ROWS):
        key = KEYS[row]
        for k in (key, key.replace("_gbp_bn", "_change_gbp_bn")):
            meta = M.DECLARED[k]
            assert meta["print"] is True
            assert meta["in_range"] is False and meta["can_set_range_end"] is False
            assert meta["placement"] == "method_check"
        d = 0.1 * (i + 1)
        assert v[key] == pytest.approx((146.51584706687706 + 23 * d) * TO_2024, abs=1e-9)
        assert v[key.replace("_gbp_bn", "_change_gbp_bn")] == pytest.approx(23 * d * TO_2024, abs=1e-9)
    t = v["table_method_checks"]
    assert [r["row"] for r in t] == list(ROWS)
    assert all(r["can_set_range_end"] is False for r in t)


def test_the_module_is_registered():
    from tools import figures_keys
    assert "method_checks" in figures_keys.MODULES


def test_no_method_check_sets_an_end_of_the_range():
    """Rows far below the low end and far above the high end change no range or table key."""
    from tools.figures_keys import range as R
    run = json.loads(S37_RUN.read_text())
    before = R.values(run)
    run = _run_with_checks({ROWS[0]: -1000.0 / 23, ROWS[1]: 1000.0 / 23})
    assert R.values(run) == before


def test_keys_are_none_on_a_run_without_the_group():
    from tools.figures_keys import method_checks as M
    run = json.loads(S37_RUN.read_text())
    assert all(v is None for v in M.values(run).values())
