"""Ticket 12 (0044, 0101): figures keys for the CCL counted only above its 2001 level, with the capped LEC
exemption (figures-keys.md rows 132, 135, 137). Read from the run file: the netted NZ8 line (bills[y]) and the
on_the_road block's exported D3 (2001-levy) and D5 (LEC) parts, which the block already carries in 2024 prices.

Keys left for a ruling, not built here (reported at the A2 merge): headline_ccl_cash_frozen_2002_24_gbp_bn and
headline_lec_uncapped_2002_24_gbp_bn (28 owns the headline/sens keys; the cash-frozen case reads the one_at_a_time
methods block once R-A6 places it, and the uncapped note run is not a METHOD_SWITCHES row, so it has no run source);
cca_upper_bound_gbp_bn (a port of ccl-calc/cca.py, not yet in the engine)."""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_24 = [str(y) for y in range(2002, 2025)]


def _m(label: str, run_field: str) -> dict:
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "12", "run_field": run_field,
            "units": "£bn, 2024 prices", "period": "2002-2024", "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
            "print": True}


DECLARED = {
    "ccl_extra_2002_24_gbp_bn": _m("CCL counted above its 2001 level, Σ2002-24 (netted NZ8, 0044/0101)",
                                   "Σ2002-24 bills[y] NZ8 national_gbp_m_real, to 2024 £bn"),
    "ccl_2001_level_netted_2002_24_gbp_bn": _m("The 2001-levy part netted off NZ8 (D3, bridge row 8b), Σ2002-24",
                                               "Σ2002-24 on_the_road.years[y].nz8_on_the_road_gbp_m_2024"),
    "lec_exemption_effect_2002_24_gbp_bn": _m("The capped LEC exemption part of NZ8 (D5, bridge row 8c), Σ2002-24",
                                              "Σ2002-24 on_the_road.years[y].nz8_lec_exempt_gbp_m_2024"),
}


def _nz8_real(run: dict, y: str) -> float:
    b = run["bills"][y]
    hits = [x for x in b["netzero"] if x["id"] == "NZ8"]
    if len(hits) != 1:
        raise KeyError(f"bills[{y}]: {len(hits)} NZ8 lines")
    return hits[0]["national_gbp_m_real"]


def values(run: dict) -> dict:
    otr = run.get("on_the_road")
    if otr is None:          # a run file without the s36 block gives None (35's release check stops on it)
        return {k: None for k in DECLARED}
    yrs = otr["years"]
    return {
        "ccl_extra_2002_24_gbp_bn": to_2024(sum(_nz8_real(run, y) for y in Y02_24), run) / 1e3,
        "ccl_2001_level_netted_2002_24_gbp_bn": sum(yrs[y]["nz8_on_the_road_gbp_m_2024"] for y in Y02_24) / 1e3,
        "lec_exemption_effect_2002_24_gbp_bn": sum(yrs[y]["nz8_lec_exempt_gbp_m_2024"] for y in Y02_24) / 1e3,
    }
