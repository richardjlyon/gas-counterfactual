"""Ticket 44 (key half): ranking keys assembled from other keys, recomputed from each release (never pinned
to names). `wf_largest_three_steps` (R-A5 option A) and `largest_two_choices_by_effect` (R-A6: ranked block
only, the methods-page rows are out of the ranking)."""
from __future__ import annotations

from tools.figures_keys import core


def _m(label, run_field, **extra):
    return {"label": label, "basis": "modelled", "provisional": True, "ticket": "44", "run_field": run_field,
            "units": "text (ranked list; £bn, 2024 prices, 2002-24)", "period": "2002-24", "status": "PENDING",
            "print": True, **extra}


DECLARED = {
    "wf_largest_three_steps": _m("The three largest of the 11 printed waterfall rows by size, sign shown; a "
                                 "negative row lowers the gap (R-A5 option A)", "wf_* keys (29), ranked by |value|"),
    "largest_two_choices_by_effect": _m("The two choices (1-8) with the largest effect on the 2002-24 headline: "
                                        "each choice's largest |headline - central| over its ranked options",
                                        "table_one_at_a_time (28), ranked block, grouped by choice (R-A6)"),
}


def wf_largest_three(run: dict) -> list[dict]:
    c = core.values(run)
    labels = {k: v[0] for k, v in (core.WF_STEPS | core.WF_LINES).items()}
    top = sorted(core.WF_ORDER, key=lambda n: (-abs(c[n]), core.WF_ORDER.index(n)))[:3]
    return [{"key": n, "label": labels[n], "value_gbp_bn": c[n], "lowers_gap": c[n] < 0} for n in top]


def largest_two_choices(rows: list[dict]) -> list[dict]:
    best = {}
    for r in rows:
        if r["block"] != "ranked":
            continue
        b = best.get(r["choice"])
        if b is None or abs(r["change_gbp_bn"]) > abs(b["change_gbp_bn"]):
            best[r["choice"]] = r
    top = sorted(best.values(), key=lambda r: (-abs(r["change_gbp_bn"]), r["choice"]))[:2]
    return [{"choice": r["choice"], "option": r["option"], "change_gbp_bn": r["change_gbp_bn"],
             "effect_gbp_bn": abs(r["change_gbp_bn"])} for r in top]


def values(run: dict) -> dict:
    from tools.figures_keys import range as R
    t = R.values(run)["table_one_at_a_time"]
    return {"wf_largest_three_steps": wf_largest_three(run),
            "largest_two_choices_by_effect": None if t is None else largest_two_choices(t)}
