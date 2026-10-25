"""Ticket 38 (non-power-gas-users.md D6; 0070, 0099, 0108 item 1.9 (a), 0117): figures keys for the non-power gas
estimate, read from the run file's `non_power_gas` block. Labelled estimate (0007), printed in §9 and §16 only, never
under `gap` or a headline (0070). 2024 prices (`gascf.figures.to_2024`).

R21 (a) (decision 0163, Richard Lyon, 21 Oct 2026): §9.8 prints the 2002-24 and 2025 figures, with the working in
Annex D. 0099 had said 2002-24 only; R21 (a) is read as setting that aside for §9.8's 2025 figure only, which Richard
confirmed in 0164 R36 (a) (Richard Lyon, 21 Oct 2026: "Agree."). The 2025 figure stays outside the 2002-24 totals.
"""
from __future__ import annotations

from gascf.figures import to_2024

R21 = "R21 (a)"
R21_NOTE = ("R21 (a) (0163): printed with the working in Annex D. 0099 said 2002-24 only; R21 (a) sets that aside for "
            "§9.8's 2025 figure only, as ruled in 0164 R36 (a). Never inside the 2002-24 totals")


def _m(label, mapped, part):
    return {"label": f"Estimate (0007): {label}", "basis": "estimated", "provisional": False, "ticket": "38",
            "mapped_name": mapped, "units": "£bn, 2024 prices", "period": "2002-2024", "status": "SOURCED",
            "print": True, "print_sections": ["§9", "§16"], "in_gap": False,
            "run_field": f"non_power_gas.totals.2002-2024.{part}, run money to 2024 prices",
            "decisions": ["0007", "0033", "0070", "0099", "0108 item 1.9", "0117", "0144"]}


DECLARED = {
    "npg_estimate_2002_24_central_gbp_bn": _m("extra cost to Britain's non-power gas users from Reliable Britain's "
                                              "higher gas price, net of UK producers' gain, elasticity 0.229 (0.06 + 0.169, 0144), "
                                              "2002-24; beside the gap, not added to it",
                                              "rb.non_power_gas_estimate.central.2002-2024", "central"),
    "npg_estimate_2002_24_low_gbp_bn": _m("the same, low end (Krichene's world long-run pair 0.16 + 0.45 = 0.61, "
                                          "0144), 2002-24",
                                          "rb.non_power_gas_estimate.low.2002-2024", "low"),
    "npg_estimate_2002_24_gross_gbp_bn": _m("the same before netting UK producers' gain (gross, elasticity 0.229), "
                                            "2002-24, shown beside the net figure",
                                            "rb.non_power_gas_estimate.gross.2002-2024", "gross"),
    # v1.1 A3 ([internal ticket] item 4): the report-writer's provisional name, confirmed. Gross less net, Annex D's working.
    "npg_producers_gain_2002_24_gbp_bn": _m("UK gas producers' gain netted from the gross figure (gross less net, "
                                            "central elasticity 0.229), 2002-24; Annex D working",
                                            "rb.non_power_gas_estimate.producers_gain.2002-2024", "producers_gain"),
}
_PART = {"npg_estimate_2002_24_central_gbp_bn": "central", "npg_estimate_2002_24_low_gbp_bn": "low",
         "npg_estimate_2002_24_gross_gbp_bn": "gross", "npg_producers_gain_2002_24_gbp_bn": "producers_gain"}

# RB v1.1 A3 (decision 0160, card [internal ticket]): the 2025 figure (provisional; non_power_gas.year_2025p, outside the
# 2002-24 totals of 0099) and the working by year; printed under R21 (a) (card [internal ticket]). The block holds no high
# case (0144 removed it: no sourced pair gives more feedback than central), so no high key is re-instated.
_P25 = {"npg_estimate_2025p_central_gbp_bn": ("central", "the same, 2025 (provisional), central elasticity 0.229"),
        "npg_estimate_2025p_low_gbp_bn": ("krichene_lr", "the same, 2025 (provisional), low end (0.61)"),
        "npg_estimate_2025p_gross_gbp_bn": ("gross", "the same, 2025 (provisional), before netting producers' gain"),
        "npg_producers_gain_2025p_gbp_bn": ("producers_gain", "UK gas producers' gain netted from the gross figure, "
                                                              "2025 (provisional), central elasticity 0.229")}
for _k, (_p, _lab) in _P25.items():
    _mapped = (_k.replace("npg_estimate_2025p_", "rb.non_power_gas_estimate.")
               .replace("npg_producers_gain_2025p_", "rb.non_power_gas_estimate.producers_gain.").replace("_gbp_bn", ".2025p"))
    DECLARED[_k] = {**_m(_lab, _mapped, _p),
                    "period": "2025", "provisional": True, "print": True, "ruling": R21, "note": R21_NOTE,
                    "ticket": "v1.1 A3 (0160); R21 (a) t_6c0411d4", "decisions": ["0007", "0070", "0099", "0163"],
                    "run_field": f"non_power_gas.year_2025p ({_p}), run money to 2024 prices"}
DECLARED["table_npg_working"] = {**_m("the working, year by year 2002-24 and 2025 (provisional, outside the 2002-24 "
                                      "totals): inputs (non-power gas volume, GB share, UK production and demand, price "
                                      "rise, gas price) and the net, low, gross and producers' gain figures; the "
                                      "2002-24 rows add to the 2002-24 keys", "rb.non_power_gas_estimate.working",
                                      "years"),
                                 "units": "table, TWh, shares, £/MWh, £bn 2024 prices", "print": True, "ruling": R21,
                                 "note": R21_NOTE, "period": "2002-2025",
                                 "ticket": "v1.1 A3 (0160); R21 (a) t_6c0411d4",
                                 "run_field": "non_power_gas.years[y] and year_2025p, to 2024 prices"}

_INPUTS = ("v_np_twh", "gb_share", "gb_share_basis", "v_np_gb_twh", "uk_production_twh", "uk_demand_twh",
           "price_rise_frac", "gas_price_gbp_mwh")


def _row(run: dict, r: dict) -> dict:
    bn = lambda v: to_2024(v * 1e3, run) / 1e3                # noqa: E731
    return {**{k: (r.get("inputs") or {}).get(k) for k in _INPUTS},
            "net_gbp_bn": bn(r["net_gbp_bn_real"]),
            # a run file before 0144 (v4-s36 and earlier) names its range rows differently: no low column
            "low_gbp_bn": None if "krichene_lr" not in r.get("range", {}) else bn(r["range"]["krichene_lr"]),
            "gross_gbp_bn": bn(r["gross_gbp_bn_real"]),
            "producers_gain_gbp_bn": (None if r.get("producers_gain_gbp_bn_real") is None
                                      else bn(r["producers_gain_gbp_bn_real"]))}


def _working(run: dict, b: dict) -> dict:
    rows = [{"year": int(y), **_row(run, r)} for y, r in b["years"].items()]
    p25 = b.get("year_2025p")
    return {"years": rows,
            "year_2025p": (None if p25 is None else
                           {"year": 2025, "provisional": True, "in_2002_24_totals": False, **_row(run, p25)}),
            "method": b.get("method"), "elasticities": b.get("elasticities"),
            "high": None, "high_note": "no high case in the block: 0144 removed it (no sourced pair gives more "
                                       "feedback than the central)", "money": "£bn, 2024 prices"}


def method(run: dict) -> str | None:
    """The run's own method text for Annex C (annex_v11 reads it here: this module is the block's only reader)."""
    return (run.get("non_power_gas") or {}).get("method")


def values(run: dict) -> dict:
    b = run.get("non_power_gas")
    if b is None:
        return {k: None for k in DECLARED}
    t = b["totals"]["2002-2024"]
    out = {k: (None if t.get(p) is None else to_2024(t[p] * 1e3, run) / 1e3) for k, p in _PART.items()}
    p25 = b.get("year_2025p")
    for k, (p, _) in _P25.items():
        if p25 is None:
            out[k] = None
        else:
            v = {"gross": p25["gross_gbp_bn_real"], "producers_gain": p25.get("producers_gain_gbp_bn_real")}.get(p)
            if p == "producers_gain" and v is None:
                out[k] = None
                continue
            out[k] = to_2024((p25["range"][p] if v is None else v) * 1e3, run) / 1e3
    out["table_npg_working"] = _working(run, b)
    return out
