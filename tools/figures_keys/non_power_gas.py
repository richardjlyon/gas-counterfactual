"""Ticket 38 (non-power-gas-users.md D6; 0070, 0099, 0108 item 1.9 (a), 0117): figures keys for the non-power gas
estimate, read from the run file's `non_power_gas` block. Labelled estimate (0007), 2002-24 only (0099), printed in
§9 and §16 only, never under `gap` or a headline (0070). 2024 prices (`gascf.figures.to_2024`)."""
from __future__ import annotations


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
}
_PART = {"npg_estimate_2002_24_central_gbp_bn": "central", "npg_estimate_2002_24_low_gbp_bn": "low",
         "npg_estimate_2002_24_gross_gbp_bn": "gross"}


def values(run: dict) -> dict:
    from gascf.figures import to_2024
    b = run.get("non_power_gas")
    if b is None:
        return {k: None for k in DECLARED}
    t = b["totals"]["2002-2024"]
    return {k: to_2024(t[p] * 1e3, run) / 1e3 for k, p in _PART.items()}
