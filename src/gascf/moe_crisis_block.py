"""Run-file block `moe_crisis` (s36 ticket 18; 0069, 0086, 0087): the 2021-23 gap under Shao (central)
and under the UCL short-run sensitivity, through the ticket 02 hook (export_v4.register_block). A block
of its own, not `gap[y].moe_crisis` as the spec item wrote it: the hook may not replace `gap`, and the
central `gap[y]` keeps its keys and values (spec D6). O'Shea, Horne and Maslin (2025) Table 4 printed
p.22 (PDF p.24); Table 5 printed p.25 (PDF p.27) is not run (0087)."""
from __future__ import annotations

from gascf import bills as B
from gascf import export_v4 as X
from gascf import moe_crisis as MC
from gascf.fossil_like_for_like import SHAO_SOLAR_POOLED


def _gap(b: dict, y: int) -> dict:
    n = b[y]["totals"]["gap_gbp_m"]
    return {"national_gbp_m_nominal": n, "national_gbp_bn_real": B.real(n, y) / 1e3,
            "per_household_real": B.real(n, y) * 1e6 / b[y]["households"]}


def block(built: dict) -> dict:
    ucl = B.build(B.replace(B.CENTRAL, moe_crisis="ucl_stmoe"))
    d = MC.require_sourced()
    years, tot, wind = {}, {}, {}
    for y in MC.CRISIS_YEARS:
        m = built[y]["fleet"]["moe"]
        shao = max(0.0, m["shao_mean_gbp_mwh"])
        solar = -SHAO_SOLAR_POOLED * m["solar_gw_mean"]
        t4 = d["stmoe_total_gbp_mwh"]["values"][str(y)]
        s, u = _gap(built, y), _gap(ucl, y)
        years[str(y)] = {"shao": s, "ucl_stmoe": u, "difference": {k: u[k] - s[k] for k in s},
                         "shao_mean_gbp_mwh": shao, "shao_solar_part_gbp_mwh": solar,
                         "ucl_table4_gbp_mwh": t4, "target_gbp_mwh": MC.target_gbp_mwh(y, m["solar_gw_mean"]),
                         "k": MC.k(y, shao, m["solar_gw_mean"])}
        tot[str(y)], wind[str(y)] = t4 / shao, t4 / (shao - solar)
    return {"years": years, "ucl_over_shao": {"total": tot, "wind": wind},
            "target": "B (0086): UCL Table 4 Total MOE (wind) + the engine's Shao solar part",
            "source_id": d["source_id"], "locator": d["stmoe_total_gbp_mwh"]["locator"],
            "peer_reviewed": False,
            "note": "methods-page sensitivity; Shao is central in every year (0069); Table 5 carried, not run "
                    "(0087); money: national_gbp_m_nominal, real in the run's price base"}


X.register_block("moe_crisis", block)
