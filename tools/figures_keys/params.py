"""Figures keys whose definitions decision 0108 item 1.15 confirmed (Richard Lyon, 19 Oct 2026: the recommended
definitions; Q-KEYS-4) and the gas-feedback elasticities (ticket 08, 0033). Read from the run file only.

- station_load_twh_yr: the "typical year" = the 2002-24 mean of years[y].station_load_twh (0059).
- pricing_residual_2002_05_gbp_m: ticket 11 spec test 6 (station-load.md, §5.3): Σ2002-05 of (NZ1 - NZ1c) - GO1's
  market part - GO1k, restated in 2025 money.
- gas_feedback_e_*: by value (decision 0144 item 2A: e = supply + demand). Central 0.229 = supply 0.06 + demand 0.169
  (Albrizio's pair); the high end of the range 0.61 (Krichene's world long-run pair, the gap's feedback range row).
  v4-s36's gas_feedback_e_low (0.06, supply only) is gone: no sourced pair gives more feedback than the central.
- pricing_residual_2002_05_gbp_m: the market part of the plant real Britain had on its ACTUAL output (from v4-s37 the
  fleet's market part also carries the extra running, 0144 item 1A, which is taken back out here)."""
from __future__ import annotations

Y02_24 = range(2002, 2025)


def _m(label, run_field, units, period, ticket, **extra):
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": ticket, "run_field": run_field,
            "units": units, "period": period, "status": "SOURCED", "print": True, **extra}


DECLARED = {
    "station_load_twh_yr": _m("Station load in a typical year (the 2002-24 mean), TWh", "mean 2002-24 years[y]."
                              "station_load_twh", "TWh a year", "2002-2024", "11",
                              mapped_name="rb.station_load.twh_mean_2002_24"),
    "pricing_residual_2002_05_gbp_m": _m("Pricing residual 2002-05: (NZ1 - NZ1c) - GO1 market part - GO1k (§5.3)",
                                         "Σ2002-05 bills[y] NZ1 - nz1c - fleet[y].market_gbp_m - GO1k, to 2025 money",
                                         "£m, 2025 prices", "2002-2005", "11"),
    "gas_feedback_e_central": _m("Gas-price feedback, elasticity, central: supply 0.06 + demand 0.169 (Albrizio et "
                                 "al. 2022's pair; 0144 item 2A)",
                                 "fossil_like_for_like.GAS_ELASTICITY['central']", "elasticity", "", "0144"),
    "gas_feedback_e_supply_central": _m("Gas-price feedback, supply elasticity in the central pair (Krichene 2005 "
                                        "Table 5, short-run, as Albrizio use it; 0144)",
                                        "fossil_like_for_like.GAS_ELASTICITY_PAIRS['central'][0]", "elasticity", "",
                                        "0144"),
    "gas_feedback_e_demand_central": _m("Gas-price feedback, demand elasticity in the central pair (Albrizio et al. "
                                        "2022 Table 2, EU-weighted; 0144)",
                                        "fossil_like_for_like.GAS_ELASTICITY_PAIRS['central'][1]", "elasticity", "",
                                        "0144"),
    "gas_feedback_e_high": _m("Gas-price feedback, elasticity at the high end of the range (Krichene 2005 Table 2 "
                              "world long-run pair, supply 0.16 + demand 0.45; 0144)",
                              "fossil_like_for_like.GAS_ELASTICITY['krichene_lr']", "elasticity", "", "0144"),
}


def _line(b: dict, side: str, lid: str) -> float:
    (v,) = [l["national_gbp_m_nominal"] for l in b[side] if l["id"] == lid]
    return v


def values(run: dict) -> dict:
    from gascf import deflator_cpih
    from gascf.fossil_like_for_like import GAS_ELASTICITY, GAS_ELASTICITY_PAIRS
    out = {"gas_feedback_e_central": GAS_ELASTICITY["central"],
           "gas_feedback_e_supply_central": GAS_ELASTICITY_PAIRS["central"][0],
           "gas_feedback_e_demand_central": GAS_ELASTICITY_PAIRS["central"][1],
           "gas_feedback_e_high": GAS_ELASTICITY["krichene_lr"], "station_load_twh_yr": None,
           "pricing_residual_2002_05_gbp_m": None}
    yrs = {r["year"]: r for r in run.get("years", [])}
    if yrs and all("station_load_twh" in yrs.get(y, {}) for y in Y02_24):
        out["station_load_twh_yr"] = sum(yrs[y]["station_load_twh"] for y in Y02_24) / len(Y02_24)
    if "bills" in run and "fleet" in run:
        base = int(run["meta"]["price_base"])
        out["pricing_residual_2002_05_gbp_m"] = sum(deflator_cpih.to_real(
            _line(run["bills"][str(y)], "netzero", "NZ1") - run["bills"][str(y)]["nz1c"]["national_gbp_m_nominal"]
            - (run["fleet"][str(y)]["market_gbp_m"] - run["fleet"][str(y)].get("extra_market_gbp_m", 0.0)) - _line(run["bills"][str(y)], "gasonly", "GO1k"), y, base)
            for y in range(2002, 2006))
    return out
