"""Run-file block `non_power_gas` (ticket 38; spec item non-power-gas-users.md D1-D6): the extra cost to Britain's
non-power gas users from Reliable Britain's higher gas price. A labelled estimate (0007), shown beside the gap and
never added to it (0070).

Decisions: 0070 (Richard, 17 Oct 2026: net of UK producers' gain; editor note: netted fully, gross shown beside it);
0099 (covers 2002-24 to match the headline; printed in §9 and §16 only); 0033 (range from the elasticities);
0108 item 1.9 option (a) (Richard Lyon, 19 Oct 2026: Great Britain, scaled by DESNZ sub-national gas); built under
0117 (Richard Lyon, 19 Oct 2026).

Per year y (cash, then to the run's money with the engine's CPIH deflator, `bills.real`):

    rise(y, e)     = dQ(y) / (e x Q(y))             the engine's own feedback inputs (`fleet[y].gas_feedback`)
    gross(y, e)    = rise x P_gas(y) x V_np(y) x GB share(y)
    net(y, e)      = gross x (1 - S_uk(y) / D(y))    net of UK producers' gain on the share of UK production
                                                      serving these users (0070, netted fully)

e = the gap's own paired elasticity (`GAS_ELASTICITY`, supply + demand; decision 0144 item 2A): central 0.229
(Albrizio's pair, 0.06 + 0.169); the low end at Krichene's world long-run pair 0.61 (0.16 + 0.45), the gap's own
sensitivity row. v4-s36's supply-only ends (0.34 / 0.06) and its high end are gone with the supply-only formula:
no sourced pair gives more feedback than the central. P_gas = the calendar
mean of the engine's actual monthly gas price (`fossil_fleet.gas_price_month`, the series behind
`answers.gas_break_even`). V_np = UK total gas demand less transformation: electricity generation (major power
producers and autogenerators), S_uk = UK production, D = UK total demand: DUKES 2026 Table 4.1, as staged in
`data/raw/s36/gas-demand/gas_demand_production.csv`. GB share = GB / (GB + NI) gas consumption, DESNZ sub-national
summary report 2024, Table 7.2 (2015-24); outside those years the nearest published year, tagged estimated and
recorded in the fallback registry (the engine's rule for the electricity GB share, `system_costs.gb_share_of_uk`).

Pass-through (D5): the wholesale rise is assumed to reach non-power users in full in the same year. Hedging and the
price cap lag homes' bills; no adjustment is made without a source."""
from __future__ import annotations

import csv
import re
import statistics
from functools import lru_cache
from pathlib import Path

from gascf import bills as B
from gascf import fallbacks as fb
from gascf.fossil_like_for_like import GAS_ELASTICITY
from gascf.pending import PendingSourceError

ROOT = Path(__file__).resolve().parents[2]
DUKES_41 = ROOT / "data/raw/s36/gas-demand/gas_demand_production.csv"
SUBNATIONAL = ROOT / "data/raw/desnz_subnational/subnational-electricity-and-gas-consumption-summary-report-2024.pdf"
SRC_DUKES41 = "desnz-dukes-2026-4.1-gas-balance"
SRC_SUBNAT_GAS = "desnz_subnational_consumption_2024_t7.2"
YEARS = list(range(2002, 2025))          # 0099: 2002-24, matching the headline; 2025 only as year_2025p (v1.1 A3)
E = {"central": GAS_ELASTICITY["central"], "krichene_lr": GAS_ELASTICITY["krichene_lr"]}   # 0144 item 2A
LABEL = "estimate (0007): extra cost to non-power gas users, beside the gap, never added to it (0070)"
METHOD = ("0070 D1: rise = dQ / (e Q) from the engine's feedback; gross = rise x actual gas price x non-power gas "
          "volume (DUKES 2026 Table 4.1, demand less electricity generation) x GB share (DESNZ sub-national "
          "Table 7.2); net = gross x (1 - UK production / UK demand). Full same-year pass-through assumed.")
DECISIONS = ["0007", "0033", "0070", "0099", "0108 item 1.9", "0117", "0144"]


@lru_cache(maxsize=None)
def dukes_inputs(path: Path = DUKES_41) -> dict[int, dict]:
    """{year: v_np_twh, uk_production_twh, uk_demand_twh} from the staged DUKES 2026 Table 4.1 balance (GWh)."""
    want = {"V_np_total_demand_less_elecgen": "v_np_twh", "dukes41_production": "uk_production_twh",
            "dukes41_total_demand_D": "uk_demand_twh"}
    out: dict[int, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["series"] in want:
                if r["unit"] != "GWh":
                    raise ValueError(f"{path.name}: {r['series']} {r['year']} unit {r['unit']!r}, expected GWh")
                out.setdefault(int(r["year"]), {})[want[r["series"]]] = float(r["value"]) / 1e3
    if not out:
        raise ValueError(f"{path.name}: no DUKES 4.1 rows read")
    return out


@lru_cache(maxsize=None)
def read_gb_gas_share(path: Path = SUBNATIONAL) -> dict[int, float]:
    """{calendar year: GB / (GB + NI)} gas consumption (weather corrected), DESNZ sub-national summary report 2024
    (published 18 Dec 2025), Table 7.2 "Subnational: GB" and "Subnational: NI" (GWh)."""
    import pymupdf
    t = re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(path)))
    i = t.find("Table 7.2: Total gas consumption (GWh)")
    j = t.find("Average", i)
    if i < 0 or j < 0 or "Subnational: GB Subnational: NI Subnational: GB + NI" not in t[i:j]:
        raise ValueError("DESNZ subnational Table 7.2 anchor missing; layout changed")
    out = {}
    for y, gb, ni, both in re.findall(r"(20\d\d) ([\d,]+) ([\d,]+) ([\d,]+) [\d,]+", t[i:j]):
        gb, ni, both = (float(x.replace(",", "")) for x in (gb, ni, both))
        if abs(gb + ni - both) > 1.5:
            raise ValueError(f"Table 7.2 {y}: GB + NI != GB + NI column")
        out[int(y)] = gb / both
    if not out:
        raise ValueError("DESNZ subnational Table 7.2: no rows read")
    return out


def gb_gas_share(year: int) -> tuple[float, str]:
    sh = read_gb_gas_share()
    if year in sh:
        return sh[year], "modelled"
    near = min(sh, key=lambda k: (abs(k - year), k))
    fb.record("gb_gas_share_nearest_year", year, sh[near], "share",
              f"DESNZ sub-national Table 7.2 GB share {near} used for {year}")
    return sh[near], "estimated"


def actual_gas_price(year: int) -> float:
    from gascf.fossil_fleet import gas_price_month
    return statistics.mean(gas_price_month(year, m)[0] for m in range(1, 13))


def _row(y: int, g: dict, inp: dict | None, share: tuple | None, price: float | None) -> dict:
    dq, q = g["dq_twh"], g["q_twh"]
    if dq != 0:     # RB v1.1 M6 (0163 R7 (a)): a year with dQ < 0 is a gain to these users and needs the same inputs
        missing = [k for k in ("v_np_twh", "uk_production_twh", "uk_demand_twh")
                   if inp is None or inp.get(k) is None]
        if missing or share is None or share[0] is None or price is None:
            raise PendingSourceError(f"non-power gas estimate {y}: input missing "
                                     f"({', '.join(missing) or 'GB share or gas price'}) in a year with dQ != 0")
    else:
        inp = inp or {}
    v = inp.get("v_np_twh") or 0.0
    s, d = inp.get("uk_production_twh") or 0.0, inp.get("uk_demand_twh") or 0.0
    sh, sh_basis = share if share is not None else (None, None)
    p = price if price is not None else 0.0
    keep = (1 - s / d) if d else 0.0
    net_m = {k: (dq / (e * q)) * p * v * (sh or 0.0) * keep for k, e in E.items()}
    gross_m = (dq / (E["central"] * q)) * p * v * (sh or 0.0)
    if dq == 0:
        net_m, gross_m = {k: 0.0 for k in E}, 0.0
    rng = {k: B.real(x, y) / 1e3 for k, x in net_m.items()}
    return {"basis": "estimated", "label": LABEL, "method": METHOD,
            "net_gbp_m_nominal": net_m["central"], "gross_gbp_m_nominal": gross_m,
            "net_gbp_bn_real": rng["central"], "gross_gbp_bn_real": B.real(gross_m, y) / 1e3,
            "producers_gain_gbp_bn_real": B.real(gross_m - net_m["central"], y) / 1e3, "range": rng,
            "inputs": {"v_np_twh": inp.get("v_np_twh"), "gb_share": sh, "gb_share_basis": sh_basis,
                       "v_np_gb_twh": (inp.get("v_np_twh") or 0.0) * (sh or 0.0),
                       "uk_production_twh": inp.get("uk_production_twh"), "uk_demand_twh": inp.get("uk_demand_twh"),
                       "price_rise_frac": dq / (E["central"] * q), "gas_price_gbp_mwh": price},
            "source_ids": [SRC_DUKES41, SRC_SUBNAT_GAS, "ofgem-wmi-nbp-dayahead"]}


def block(built: dict, inputs: dict | None = None, shares: dict | None = None, gas_price: dict | None = None) -> dict:
    inputs = dukes_inputs() if inputs is None else inputs
    years = {}
    for y in YEARS:
        g = built[y]["fleet"]["gas_feedback"]
        need = g["dq_twh"] != 0
        share = (shares.get(y) if shares is not None else (gb_gas_share(y) if need else None))
        price = (gas_price.get(y) if gas_price is not None else (actual_gas_price(y) if need else None))
        years[str(y)] = _row(y, g, inputs.get(y), share, price)
    tot = {"central": sum(r["net_gbp_bn_real"] for r in years.values()),
           "low": sum(r["range"]["krichene_lr"] for r in years.values()),
           "gross": sum(r["gross_gbp_bn_real"] for r in years.values()),
           "producers_gain": sum(r["producers_gain_gbp_bn_real"] for r in years.values())}
    # RB v1.1 A3 (decision 0160, card [internal ticket]): 2025, provisional, by the same rule, kept OUTSIDE `years` and the
    # 2002-24 totals (0099: the estimate covers 2002-24 to match the headline). Printed under R21 (a) (0163); 0099
    # set aside for this 2025 figure only, as ruled in 0164 R36 (a).
    # The GB share takes the nearest published year (Table 7.2 ends 2024), recorded by gb_gas_share's fallback.
    p25 = None
    if 2025 in built and inputs.get(2025) is not None:     # a toy or partial input set without 2025: not computed
        g = built[2025]["fleet"]["gas_feedback"]
        need = g["dq_twh"] > 0
        share = (shares.get(2025) if shares is not None else (gb_gas_share(2025) if need else None))
        price = (gas_price.get(2025) if gas_price is not None else (actual_gas_price(2025) if need else None))
        p25 = _row(2025, g, inputs.get(2025), share, price) | {"provisional": True, "in_totals": False,
                                                                "ruling": "R21 (a): printed in §9.8 and Annex D"}
    return {"years": years, "totals": {"2002-2024": tot}, "year_2025p": p25, "basis": "estimated", "label": LABEL,
            "method": METHOD,
            "in_gap": False, "print_sections": ["§9", "§16"], "money": "£bn in the run's price base (CPIH)",
            "elasticities": E, "pass_through": "full, same year (D5; stated, not adjusted)",
            "decisions": DECISIONS}


from gascf import export_v4 as _X  # noqa: E402

_X.register_block("non_power_gas", block)
