"""Ticket 19 (B6): the part of each waterfall step that reaches households' own bills, steps 4 (Capacity
Market extra) and 5 (running the grid) apart, read from the run file's
bills[y].netzero_on_household_bill_per_household.by_step. £bn in the run's price base (D4: no new
deflator). Key names follow the spec item (household-steps-split.md D3): by year and by window."""
from __future__ import annotations

from gascf.waterfall import STEPS

YEARS = range(2002, 2026)
WINDOWS = {"2006-2023": (2006, 2023), "2006-2024": (2006, 2024), "2006-2025": (2006, 2025),
           "2002-2025": (2002, 2025)}
LABEL = {n: label for n, label, _, _ in STEPS}


def _meta(n: int, what: str, field: str) -> dict:
    return {"label": f"Step {n}, {LABEL[n]}: on households' own bills, {what}, £bn real (run price base)",
            "basis": "modelled", "provisional": False, "ticket": "19",
            "run_field": f"bills[{field}].netzero_on_household_bill_per_household.by_step.{n}.real_gbp_m"}


DECLARED = {
    **{f"rb.household_bill.by_step_real_bn.{n}.{y}": _meta(n, str(y), str(y)) for n in LABEL for y in YEARS},
    **{f"rb.household_bill.by_step_real_bn_total.{n}.{w}": _meta(n, f"sum {w}", w) for n in LABEL for w in WINDOWS},
}


def values(run: dict) -> dict:
    if "by_step" not in run["bills"]["2002"].get("netzero_on_household_bill_per_household", {}):
        return {k: None for k in DECLARED}   # ruling 17 Oct 2026 (a): pre-s36 run file -> None; 35's check stops the release

    def bn(n: int, y: int) -> float:
        return run["bills"][str(y)]["netzero_on_household_bill_per_household"]["by_step"][str(n)]["real_gbp_m"] / 1e3

    out = {f"rb.household_bill.by_step_real_bn.{n}.{y}": bn(n, y) for n in LABEL for y in YEARS}
    out.update({f"rb.household_bill.by_step_real_bn_total.{n}.{w}": sum(bn(n, y) for y in range(a, z + 1))
                for n in LABEL for w, (a, z) in WINDOWS.items()})
    return out
