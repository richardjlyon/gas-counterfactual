"""Ticket 13 (0061, spec calibration-pooled.md D6): figures keys for the pooled 2002-04 early-years check, read from
the run file's tests.calibration_early. Decision 0111 (Richard Lyon, 19 Oct 2026, item 1.3): the check is printed as
it falls (about 34.6% against the 30% limit on the s36 build), with its cause, as an expected and disclosed failure."""
from __future__ import annotations


def _m(label: str, mapped: str, units: str, **extra) -> dict:
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "13", "mapped_name": mapped,
            "units": units, "period": "2002-2004", "money": "2025 prices", "status": "SOURCED", "print": True,
            "decisions": ["0061", "0111"], **extra}


DECLARED = {
    "calib_pooled_2002_04_pct": _m("Early-years check, pooled 2002-04: |gap - net-zero-only lines| as % of the lines "
                                   "(fails the 30% limit; 0111, stated in §5)",
                                   "rb.calibration.pooled_2002_04.pct", "%"),
    "calib_pooled_2002_04_gbp_hh": _m("Early-years check, pooled 2002-04: gap less net-zero-only lines, £ a household",
                                      "rb.calibration.pooled_2002_04.diff_hh", "£ a household, 2025 prices"),
    **{f"calib_{y}_pct": _m(f"Early-years check, {y} alone, % of the lines (printed, never judged; 0061)",
                            f"rb.calibration.per_year[{y}].pct", "%") for y in (2002, 2003, 2004)},
    "calib_limit_pct": _m("Early-years check limit: within 30% of the net-zero-only lines",
                          "rb.calibration.pooled_2002_04.pass_pct", "%"),
    "calib_limit_gbp_hh": _m("Early-years check limit: within £25 a household", "rb.calibration.pooled_2002_04.pass_gbp",
                             "£ a household, 2025 prices"),
    "calib_pooled_2002_04_passed": _m("Early-years check, pooled 2002-04, passed both limits (False: disclosed failure, "
                                      "0111)", "rb.calibration.pooled_2002_04.passed", "true/false"),
}


def values(run: dict) -> dict:
    b = run.get("tests", {}).get("calibration_early")
    if b is None:                     # a run file without the block (v4-s35): None, as the other s36 modules
        return {k: None for k in DECLARED}
    per = {p["year"]: p for p in b["per_year"]}
    return {"calib_pooled_2002_04_pct": b["pooled"]["pct"], "calib_pooled_2002_04_gbp_hh": b["pooled"]["diff_hh"],
            **{f"calib_{y}_pct": per[y]["pct"] for y in (2002, 2003, 2004)},
            "calib_limit_pct": b["limit_pct"], "calib_limit_gbp_hh": b["limit_gbp_hh"],
            "calib_pooled_2002_04_passed": b["passed"]}
