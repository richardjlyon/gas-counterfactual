"""Ticket 22 (case-b-gas-export.md D2; 0029, 0034, 0048, 0095; decision 0117): figures keys for case B, read from the
run file's `sensitivities_case_b` block. Case B is never in the printed range (0095) and never a headline; every
key carries the one case B reason, `gascf.case_b.REJECTION`. Gap keys are 2024 prices (`gascf.figures.to_2024`);
2025 keys are provisional."""
from __future__ import annotations

from gascf.case_b import REJECTION

Y02_24 = [str(y) for y in range(2002, 2025)]
_CASE_LABEL = "case B (closures actual, kept output at the actual price, elasticity 0.06)"


def _m(label, mapped, units, period, provisional=False, basis="modelled", **extra):
    return {"label": label, "basis": basis, "provisional": provisional, "ticket": "22", "mapped_name": mapped,
            "units": units, "period": period, "status": "SOURCED", "print": True, "reason": REJECTION,
            "in_range": False, "decisions": ["0029", "0034", "0048", "0095", "0117"], **extra}


DECLARED = {
    "case_b_2002_24_gbp_bn": _m(f"Gap under {_CASE_LABEL}, 2002-24 total (not the central case; outside the range)",
                                "rb.case_b.gap_2002_24_gbp_bn", "£bn, 2024 prices", "2002-2024",
                                run_field="Σ2002-24 sensitivities_case_b.cases.case_b_all_three[y].gap_real_bn"),
    "case_b_2025p_gbp_bn": _m(f"Gap under {_CASE_LABEL}, 2025 provisional", "rb.case_b.gap_2025_gbp_bn",
                              "£bn, 2024 prices", "2025", provisional=True,
                              run_field="sensitivities_case_b.cases.case_b_all_three[2025].gap_real_bn"),
    "case_b_extra_gas_twh_2025p": _m("Reliable Britain's extra gas burn for power in 2025, by case (TWh); the paper's "
                                     "figure is closures_actual", "rb.case_b.extra_gas_twh[case][2025]",
                                     "table, TWh by case", "2025", provisional=True,
                                     run_field="sensitivities_case_b.cases[case][2025].dq_twh"),
    # v4-s37 (0144): case B's code is unchanged, so this key now holds the rise at the engine's central e, 0.229
    # (0.06 + 0.169); the key name keeps "e016" until Richard rules what case B means under 0144 (note 2)
    "case_b_gas_rise_e016_2025p_pct": _m("Gas-price rise at the engine's central elasticity, 0.229 (0.06 + 0.169, "
                                         "0144; 0.16 before v4-s37), from each case's 2025 extra burn, dq / (0.229 q), "
                                         "%", "rb.case_b.gas_price_rise_at[central][case][2025]",
                                         "table, % by case", "2025", provisional=True,
                                         run_field="100 x sensitivities_case_b.cases[case][2025].rise_at_e016"),
    "case_b_gas_rise_e006_2025p_pct": _m("Gas-price rise at elasticity 0.06 from each case's 2025 extra burn, "
                                         "dq / (0.06 q), %", "rb.case_b.gas_price_rise_at[0.06][case][2025]",
                                         "table, % by case", "2025", provisional=True,
                                         run_field="100 x sensitivities_case_b.cases[case][2025].rise_at_e006"),
    "case_b_negative_years": _m("Years in which case B's gap is negative (its failed sign check, recorded openly, "
                                "0034)", "rb.case_b.sign_check.negative_years", "list of years", "2002-2025",
                                run_field="sensitivities_case_b.sign_check.case_b_all_three.negative_years"),
}


def values(run: dict) -> dict:
    from gascf.figures import to_2024
    b = run.get("sensitivities_case_b")
    if b is None:
        return {k: None for k in DECLARED}
    c = b["cases"]
    b3 = c["case_b_all_three"]
    names = [n for n in c if n != "central"] + ["central"]
    return {
        "case_b_2002_24_gbp_bn": to_2024(sum(b3[y]["gap_real_bn"] for y in Y02_24) * 1e3, run) / 1e3,
        "case_b_2025p_gbp_bn": to_2024(b3["2025"]["gap_real_bn"] * 1e3, run) / 1e3,
        "case_b_extra_gas_twh_2025p": {n: c[n]["2025"]["dq_twh"] for n in names},
        "case_b_gas_rise_e016_2025p_pct": {n: 100 * c[n]["2025"]["rise_at_e016"] for n in names},
        "case_b_gas_rise_e006_2025p_pct": {n: 100 * c[n]["2025"]["rise_at_e006"] for n in names},
        "case_b_negative_years": list(b["sign_check"]["case_b_all_three"]["negative_years"]),
    }
