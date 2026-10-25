"""RB v1.1 F5 (decision 0160, card [internal ticket]): the waterfall year by year, 2002-25 (2025 provisional), the same 11
printed steps as table_waterfall_2002_24 in the same order, each year's steps adding to that year's gap. Read from the
run file's waterfall[y] and bills[y] (the RO, FiT and CfD steps from their lines, as tools.figures_keys.core does).
No number moves: Σ2002-24 of each step is the released wf_ key. 2024 prices (CPIH, gascf.figures.to_2024)."""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

from tools.figures_keys import core

Y02_25 = [str(y) for y in range(2002, 2026)]

DECLARED = {
    "table_waterfall_by_year": {
        "label": "Waterfall year by year, 2002-25 (2025 provisional): the 11 printed steps in step order, each year "
                 "adding to that year's gap",
        "basis": "modelled", "provisional": False, "ticket": "v1.1 F5 (0160)",
        "run_field": "waterfall[y] steps and bills[y] NZ2, NZ3, NZ4, NZ4b (as the wf_ keys), each year",
        "units": "table, £bn, 2024 prices", "period": "2002-2025", "price_base": PRICE_BASE_LABEL,
        "status": "SOURCED", "print": True},
}


def _step(run: dict, y: str, key: str) -> float:
    if key in core.WF_STEPS:
        return core._step_m(y, run, core.WF_STEPS[key][1])
    return sum(core._line_m(y, run, i) for i in core.WF_LINES[key][1])


def values(run: dict) -> dict:
    if "waterfall" not in run or "bills" not in run:
        return {"table_waterfall_by_year": None}
    prov = [str(p) for p in run["meta"]["provisional_years"]]
    labels = {k: v[0] for k, v in (core.WF_STEPS | core.WF_LINES).items()}
    out = []
    for y in Y02_25:
        steps = [{"key": k, "label": labels[k], "value": to_2024(_step(run, y, k), run) / 1e3} for k in core.WF_ORDER]
        out.append({"year": int(y), "provisional": y in prov, "steps": steps,
                    "gap_gbp_bn": to_2024(run["gap"][y]["national_gbp_bn_real"], run)})
    return {"table_waterfall_by_year": out}
