"""Decision 0144 (Richard Lyon, 20 Oct 2026: "Yes, take all the recommendations (headline about £141bn)"): one named
sensitivity row for each finding of the critic's review of v4-s36 that the decision sheet tagged JUDGEMENT (findings
1, 3, 4, 5b, 7) and for finding 2's paired-elasticity row, each with its headline and its change from the central,
2002-24, £bn, 2024 prices (CPIH). Sheet test 7.

| Row | Finding, option not chosen | How measured |
|---|---|---|
| 1C | 1, extra running at cost (the v4-s36 mix) | methods-page build, `extra_running='cost'` |
| 2B | 2, Krichene's world long-run pair 0.16 + 0.45 | ranked build, `gas_feedback='krichene_lr'` (also a range row) |
| 3B | 3, UCL short-run uplift for 2021-23 (preprint) | methods-page build, `moe_crisis='ucl_stmoe'` |
| 4 | 4, the engine's four-block stack estimate | methods-page build, `moe='model'` (ranked in v4-s36) |
| 5bB | 5b, "to Britain" with the transfers netted out: B's measurable part, a partial whole-Britain view | arithmetic on this run's keys: central less carbon price receipts, less VAT, less Reliable Britain's non-power gas cost |
| 7B | 7, energy-saving schemes line out of the gap | arithmetic: central less the NZ10 waterfall step; treated as additive, any VAT knock-on not measured |

5bB's sign (the sheet's round 2, accepted by the research-director on [internal ticket] round 2): the headline is actual
Britain's cost less Reliable Britain's. The non-power gas estimate is an extra cost that Reliable Britain's dearer gas
puts on its own non-power gas users, so counting it raises Reliable Britain's cost and lowers the gap. The research-
director's build card ([internal ticket]) and 0144 note 1 had it with the opposite sign (+npg, -£15.915bn on v4-s36); the
PR body records both. The British share of the £50.4bn carbon rest and finding 1 on a resource basis are not
measured, so the row is partial.

The paper's sentence on finding 3 ("the central uplift is probably low in 2021-23") is the report-writer's; the
key `note_uplift_2021_23_probably_low` carries the ruled wording and points at row 3B.
"""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL

Y02_24 = [str(y) for y in range(2002, 2025)]


def _rows() -> dict:
    from gascf import bills as B
    return {
        "1C": {"slug": "extra_running_at_cost", "switch": B.EXTRA_AT_COST, "finding": "1",
               "name": "Extra running of the plant Britain had at its fuel, running and transport cost (the v4-s36 "
                       "mix), not the market price (finding 1, option C)"},
        "2B": {"slug": "feedback_krichene_pair", "switch": B.FEEDBACK_KRICHENE, "finding": "2",
               "name": "Gas-price feedback at Krichene's world long-run pair, supply 0.16 + demand 0.45 = 0.61 "
                       "(finding 2, option B)"},
        "3B": {"slug": "uplift_ucl_2021_23", "switch": B.MOE_UCL, "finding": "3",
               "name": "Merit-order uplift for 2021-23 from the UCL short-run estimate, a preprint (finding 3, "
                       "option B)"},
        "4": {"slug": "uplift_engine_stack", "switch": B.MOE_STACK, "finding": "4",
              "name": "Merit-order uplift from the engine's own four-block supply stack (finding 4; on the methods "
                      "page, out of the range)"},
        "5bB": {"slug": "whole_britain_partial", "switch": None, "finding": "5b",
                "name": "B's measurable part, a partial whole-Britain view: carbon price receipts and VAT netted "
                        "out, Reliable Britain's non-power gas cost counted (finding 5b, option B)"},
        "7B": {"slug": "schemes_out", "switch": None, "finding": "7",
               "name": "Energy-saving schemes line (EEC to GBIS) taken out of the gap (finding 7, option B)"},
    }


ROW_IDS = ("1C", "2B", "3B", "4", "5bB", "7B")


def _key(fid: str, part: str) -> str:
    slug = {"1C": "extra_running_at_cost", "2B": "feedback_krichene_pair", "3B": "uplift_ucl_2021_23",
            "4": "uplift_engine_stack", "5bB": "whole_britain_partial", "7B": "schemes_out"}[fid]
    return f"sens_{slug}_2002_24_gbp_bn" if part == "headline" else f"sens_{slug}_change_gbp_bn"


def _m(label, run_field, units="£bn, 2024 prices", **extra):
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "0144", "run_field": run_field,
            "units": units, "period": "2002-2024", "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
            "print": True, "decisions": ["0144"], **extra}


_LABEL = {
    "1C": "extra running at cost (the v4-s36 mix; finding 1, option C)",
    "2B": "gas-price feedback at Krichene's world long-run pair 0.16 + 0.45 (finding 2, option B)",
    "3B": "merit-order uplift 2021-23 from UCL's short-run estimate, preprint (finding 3, option B)",
    "4": "merit-order uplift from the engine's four-block stack estimate (finding 4, methods page)",
    "5bB": "B's measurable part, a partial whole-Britain view: less carbon price receipts, less VAT, less Reliable "
           "Britain's non-power gas cost (finding 5b, option B)",
    "7B": "the energy-saving schemes line out of the gap (finding 7, option B; additive, VAT knock-on not measured)",
}
ROWS = {fid: {"name": "", "headline_key": _key(fid, "headline"), "change_key": _key(fid, "change")}
        for fid in ROW_IDS}
DECLARED = {}
for _fid in ROW_IDS:
    DECLARED[_key(_fid, "headline")] = _m(f"Headline 2002-24 with {_LABEL[_fid]}",
                                          f"sens_0144.measure[{_fid}].headline_gbp_bn")
    DECLARED[_key(_fid, "change")] = _m(f"Change from the central headline 2002-24 with {_LABEL[_fid]}",
                                        f"sens_0144.measure[{_fid}].change_gbp_bn")
DECLARED["table_sensitivity_rows_0144"] = _m("Sensitivity rows for the review findings (decision 0144): name, "
                                             "headline 2002-24 and change from the central",
                                             "sens_0144.measure", units="table, £bn, 2024 prices")
DECLARED["note_uplift_2021_23_probably_low"] = _m(
    "Finding 3, as superseded for 2021-23 by decision 0164 (M9 B): the central uplift is now re-estimated on outturn "
    "with direct coefficients from May 2021 to Dec 2023 (Shao et al. pooled, sample April 2009 to March 2021, in "
    "every other year), because Shao's sample-period uplift was probably low when gas cost several times its sample "
    "level; the UCL short-run estimate stays a methods-page row, its change in "
    "sens_uplift_ucl_2021_23_change_gbp_bn. The paper's sentence is the report-writer's.",
    "text; sens_0144 row 3B", units="text")


def _fill_names() -> None:
    for fid, r in _rows().items():
        ROWS[fid]["name"] = r["name"]


_fill_names()


def measure(run: dict, only=None) -> dict:
    """{row id: {name, headline_gbp_bn, change_gbp_bn}} on `run`, 2002-24, £bn, 2024 prices."""
    from tools.figures_keys import core, non_power_gas
    from tools.figures_keys import range as R
    rows = _rows()
    ids = [f for f in ROW_IDS if only is None or f in only]
    t = R.table(run)
    from gascf.figures import to_2024
    central = to_2024(sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24), run)
    out = {}
    need_core = any(f in ("5bB", "7B") for f in ids)
    cv = core.values(run) if need_core else {}
    for fid in ids:
        r = rows[fid]
        if r["switch"] is not None:
            hit = [x for x in t if x["switch"] == r["switch"]]
            if len(hit) != 1:
                raise KeyError(f"sens_0144 row {fid}: expected one one_at_a_time row for {r['switch']!r}, "
                               f"found {len(hit)}")
            h = hit[0]["headline_2002_24_gbp_bn"]
        elif fid == "5bB":
            npg = non_power_gas.values(run)["npg_estimate_2002_24_central_gbp_bn"]
            parts = (cv["carbon_price_receipts_2002_24_gbp_bn"], cv["wf_vat_gbp_bn"], npg)
            h = None if None in parts else central - sum(parts)      # a run without a block: None, as other modules
        elif fid == "7B":
            h = None if cv["wf_schemes_gbp_bn"] is None else central - cv["wf_schemes_gbp_bn"]
        out[fid] = {"id": fid, "finding": r["finding"], "name": r["name"], "headline_gbp_bn": h,
                    "change_gbp_bn": None if h is None else h - central}
    return out


def values(run: dict) -> dict:
    if "one_at_a_time" not in run:
        return {k: None for k in DECLARED}
    rows = measure(run)
    out = {}
    for fid, r in rows.items():
        out[_key(fid, "headline")] = r["headline_gbp_bn"]
        out[_key(fid, "change")] = r["change_gbp_bn"]
    out["table_sensitivity_rows_0144"] = list(rows.values())
    out["note_uplift_2021_23_probably_low"] = DECLARED["note_uplift_2021_23_probably_low"]["label"]
    return out
