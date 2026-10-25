"""v4-s40 item 9 (step-3 sheet item 9 (a); decision 0175, Richard Lyon 23 Oct 2026, "Yes." at 06:13:51 UTC to the
chief-executive's five-point question, verified on card [internal ticket]): one key per method check (`bills.METHOD_CHECKS`,
run-file block `one_at_a_time.method_checks`): the 2002-24 headline under that row alone, in 2024 prices, and its
change from central.

The sheet's (a) wording: "These are method checks only: closure classes, kept-coal payments and life extension, and
the alternative coal-hours reading. They do not set the range." The rows sit in their own block, which no range key
reads, so none can set an end of the printed range. A run without the block (v4-s39 and earlier) gives None.
"""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_24 = [str(y) for y in range(2002, 2025)]

# key -> (the row's name in bills.METHOD_CHECKS, short label, the ruling)
ROWS = {
    "check_r4b_kept_coal_cm_from_2014_2002_24_gbp_bn": (
        "kept coal paid the Capacity Market rate from 2014, fixed cost less margin before (R4 (b))",
        "Headline 2002-24 with kept coal paid the road's Capacity Market rate on its de-rated capacity from 2014, "
        "fixed cost less margin before (R4 (b))", "0163 R4 (b)"),
    "check_r6a_kept_coal_life_extension_2002_24_gbp_bn": (
        "kept coal life extension: assumption borrowed from gas plant (CEPA/GHD 2025, £81/kW per 5 years; R6 (a), R33)",
        "Headline 2002-24 with a life-extension cost on kept coal, borrowed from gas plant (CEPA/GHD 2025, £81/kW per "
        "five years)", "0163 R6 (a)"),
    "check_r17a_closures_biomass_conversion_2002_24_gbp_bn": (
        "closures by class: biomass conversions on their real dates (R17 (a); classes R34 (a), 0164)",
        "Headline 2002-24 with the biomass conversions closing on their real dates", "0163 R17 (a); 0164 R34 (a)"),
    "check_r17a_closures_coal_phase_out_deadline_2002_24_gbp_bn": (
        "closures by class: coal phase-out deadline closures on their real dates (R17 (a); classes R34 (a), 0164)",
        "Headline 2002-24 with the coal phase-out deadline closures on their real dates", "0163 R17 (a); 0164 R34 (a)"),
    "check_r17a_closures_mixed_2002_24_gbp_bn": (
        "closures by class: mixed-cause closures on their real dates (R17 (a))",
        "Headline 2002-24 with the mixed-cause closures on their real dates", "0163 R17 (a)"),
    "check_coal_hours_reading_ii_2002_24_gbp_bn": (
        "coal hours (ii): the 1,500-hour route also for Drax 1-4 and Lynemouth (check row, 0166)",
        "Headline 2002-24 with coal-hours reading (ii): the 1,500-hour route also for Drax 1-4 and Lynemouth",
        "0166 item 4"),
}
WHERE = "; a method check outside the range (step-3 item 9 (a), 0175), never an end of the range"


def _m(label: str, row: str, ruling: str, change: bool = False) -> dict:
    return {"label": ("Change from central: " if change else "") + label + WHERE,
            "basis": "modelled", "provisional": False, "ticket": "v4-s40 item 9 (0175)",
            "run_field": f"one_at_a_time.method_checks[{row!r}][0].gap_real_bn, Σ2002-24"
                         + (" less Σ gap[y].national_gbp_bn_real" if change else "") + ", to 2024 prices",
            "units": "£bn, 2024 prices", "period": "2002-2024", "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
            "print": True, "in_range": False, "can_set_range_end": False, "placement": "method_check",
            "ruling": ruling}


DECLARED: dict = {}
for _k, (_row, _lab, _r) in ROWS.items():
    DECLARED[_k] = _m(_lab, _row, _r)
    DECLARED[_k.replace("_gbp_bn", "_change_gbp_bn")] = _m(_lab, _row, _r, change=True)
DECLARED["table_method_checks"] = {
    "label": "Method checks outside the range (step-3 item 9 (a), 0175): kept coal on the Capacity Market rate from "
             "2014 (R4 (b)), kept coal life extension (R6 (a)), the three closures-by-class rows (R17 (a)) and "
             "coal-hours reading (ii) (0166); each headline 2002-24 and its change from central; none can set an end "
             "of the printed range",
    "basis": "modelled", "provisional": False, "ticket": "v4-s40 item 9 (0175)",
    "run_field": "one_at_a_time.method_checks", "units": "table, £bn, 2024 prices", "period": "2002-2024",
    "price_base": PRICE_BASE_LABEL, "status": "SOURCED", "print": True, "in_range": False, "can_set_range_end": False}


def values(run: dict) -> dict:
    checks = (run.get("one_at_a_time") or {}).get("method_checks")
    if checks is None:
        return {k: None for k in DECLARED}
    central = sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24)
    out, table = {}, []
    for key, (row, _, ruling) in ROWS.items():
        opts = checks.get(row)
        if opts is None or len(opts) != 1:
            raise KeyError(f"one_at_a_time.method_checks: expected one row for {row!r}, "
                           f"found {0 if opts is None else len(opts)}")
        h = sum(opts[0]["gap_real_bn"][y] for y in Y02_24)
        ck = key.replace("_gbp_bn", "_change_gbp_bn")
        out[key], out[ck] = to_2024(h, run), to_2024(h - central, run)
        table.append({"key": key, "row": row, "ruling": ruling, "placement": "method_check",
                      "can_set_range_end": False, "headline_2002_24_gbp_bn": out[key], "change_gbp_bn": out[ck]})
    out["table_method_checks"] = table
    return out
