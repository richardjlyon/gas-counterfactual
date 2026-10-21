"""The Subsidy Clock's export: exactly the counterfactual figures the Clock consumes, and nothing
else (Richard, 14 Oct 2026: the two models are not merged; every counterfactual figure the Clock
uses comes from this engine, pinned by version and sha256).

`out/clock/<engine_version>.json` (schema clock-export/2 from v4-s33; v4-s32 was clock-export/1)
carries these blocks:

- `capacity_market` (spec §5.4, NZ5): per calendar year, the Capacity Market paid (the Clock's own
  LCCC total, as the engine read it), the net-zero part (central, low, high), Reliable Britain's
  own backup payment, the £/kW/yr price and the GW it applies to. Taken from the run file's
  `clock_cm_correction` and `capacity_market` blocks, rounded exactly as the Clock's former hand
  copy (`subsidy-clock/reference/capacity_market_netzero_share.yaml`, commit e0bfd735): £ to the
  penny, price to 4 dp, GW to 3 dp. Years the engine did not model (`nz5_gbp_m` null) are left out;
  `carry_forward_from` is the last modelled year.
- `baselines` (spec §7.1, §7.2): the 2002-05 pre-renewables means the Clock subtracts from its raw
  TNUoS and BSUoS series, £ nominal, calendar-year mean of CY2002-2005, computed here by the
  engine's own functions (never typed in):
    tnuos = mean_y fy_to_cy(grid.baseline_fy_nominal())[y]  (G0, nominal; the three TOs' allowed
            revenues NGC + SPT + SHETL, i.e. GB, not England & Wales only)
    bsuos = mean_y fy_to_cy(balancing.baseline_fy('ibc'))[y]  (B0, nominal; the IBC baseline of
            §7.2 grossed up to GB and to the BSUoS basis; FY2005/06 = NAO £642m). This is the
            same nominal mean `balancing.go4` calls `b_nom`.

  Kept for reference only from clock-export/2: the Clock no longer carries them itself.
- `grid` and `balancing` (clock-export/2; Richard, 14 Oct 2026: one method for carrying the
  2002-05 costs forward, in both models): the no-net-zero (counterfactual) cost per calendar year,
  £ nominal, for every engine year, generators' share INCLUDED (the Clock has no power-price
  line, so for the Clock the generators' part is a cost Britain paid; the engine's own bills
  remove it from both sides). Scope: 'included' is the Clock export's basis only
  (`GEN_SHARE`); the engine's central is 'removed' (0024, `grid.go5`, `Settings.tnuos_gen`):
    grid       = GO5 = G0 carried by the regulator's control index (RPI to FY2020/21, then CPIH)
                 + renewal allowance R (v4-s35: RAV roll-forward, central = the whole allowance
                 above the 2002-05 level; R = 0 gives the high end of net zero's cost)
                 = grid.go5(PRICE_BASE, YEARS, index='rpi', gen_share='included')
    balancing  = GO4 = B0 ('ibc') x [s' x gas(y)/gas(2002-05) + (1 - s') x CPIH(y)/CPIH(2002-05)],
                 s' = s/(1 + internal ratio), s = NESO workbook FY2018/19 energy share of
                 external cost (v4-s35: applied to external B0 only); low end = the stacked
                 'nao_2005|max' option, high end = the option giving the smallest GO4
                 = balancing.go4(PRICE_BASE, s, 'ibc', YEARS, gen_share='included')
  "low" and "high" are the ends of NET ZERO's cost range (v4-s35, T1: every label is by net-zero
  cost): low uses the LARGER no-net-zero cost. Grid: low >= central >= high in every year
  (low = central since R central = R high). Balancing: each end is one rule for every year,
  chosen on the 2002-2025 total, so it can cross the central; `crossing_years` lists the years. The Clock subtracts the per-year figure from its own measured
  TNUoS / BSUoS; for years after `carry_forward.from` it carries the last year by CPIH.

The baselines do not depend on the run file (the run file does not store them); they come from the
engine code at the release commit, which is recorded in `meta.commit`. `gascf.release` refuses to
cut a release from a working tree whose `src/` differs from that commit.
"""
from __future__ import annotations

import hashlib
import math
import json
import statistics
from collections.abc import Mapping
from pathlib import Path

from gascf import balancing, grid

SCHEMA = "clock-export/2"
KNOWN_SCHEMAS = ("clock-export/1", SCHEMA)   # v4-s32 was cut with /1; released files are immutable
BASE_PERIOD = "2002-2005"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _pennies(gbp_m: float) -> float:
    return round(gbp_m * 1e6, 2)


def capacity_market(run: dict) -> dict:
    """{years: {year: row}, carry_forward_from} from the run's clock_cm_correction + capacity_market."""
    corr, cm = run["clock_cm_correction"], run["capacity_market"]
    years: dict[str, dict] = {}
    for y in sorted(corr, key=int):
        c = corr[y]
        if c.get("nz5_gbp_m") is None:
            continue                       # not modelled: the Clock carries the last share forward
        k = cm[y]
        years[str(int(y))] = {
            "cm_paid_gbp": _pennies(c["clock_cm_gbp_m"]),
            "netzero_gbp": _pennies(c["nz5_gbp_m"]),
            "netzero_low_gbp": _pennies(c["nz5_low_gbp_m"]),
            "netzero_high_gbp": _pennies(c["nz5_high_gbp_m"]),
            "own_backup_gbp": _pennies(k["reliable_britain_cm_gbp_m"]),
            "price_gbp_per_kw_yr": round(float(k["price_gbp_kw_yr"]), 4),
            "own_backup_gw": round(float(k["reliable_britain_cm_gw"]), 3),
        }
    if not years:
        raise ValueError("run file has no modelled Capacity Market year")
    return {"years": years, "carry_forward_from": max(int(y) for y in years),
            "method": "spec.md §5.4 (NZ5 = CM paid - Reliable Britain's own backup payment)",
            "source_blocks": ["clock_cm_correction", "capacity_market"]}


def tnuos_baseline_gbp_m() -> tuple[float, dict[int, float]]:
    cy = grid.fy_to_cy(grid.baseline_fy_nominal(), grid.BASE_WINDOW)
    return statistics.mean(cy[y] for y in grid.BASE_WINDOW), cy


def bsuos_baseline_gbp_m(option: str = "ibc") -> tuple[float, dict[int, float], list[str]]:
    fy = balancing.baseline_fy(option)
    cy = balancing.fy_to_cy({k: v["gbp_m"] for k, v in fy.items()}, balancing.BASE_WINDOW)
    srcs = sorted({s for v in fy.values() for s in v["source_id"].split("|")})
    return statistics.mean(cy[y] for y in balancing.BASE_WINDOW), cy, srcs


def baselines() -> dict:
    t, t_cy = tnuos_baseline_gbp_m()
    b, b_cy, b_src = bsuos_baseline_gbp_m("ibc")
    b_alt, _, _ = bsuos_baseline_gbp_m("nao_2005")
    pieces = grid.baseline_pieces()
    return {
        "tnuos": {
            "value_gbp_nominal": round(t * 1e6, 2),
            "period": BASE_PERIOD,
            "geography": "GB",
            "basis": ("G0 (spec §7.1): transmission owners' allowed revenues NGC (England & Wales, "
                      "excluding connection revenue and all SO costs) + SP Transmission + SHETL, "
                      "each restated from its RPI price base to nominal, summed by financial year, "
                      "time-weighted to calendar years (0.25 x FY(y-1) + 0.75 x FY(y)), mean of "
                      "CY2002-2005; nominal £"),
            "calendar_years_gbp_m": {str(y): v for y, v in t_cy.items()},
            "function": "gascf.grid.fy_to_cy(gascf.grid.baseline_fy_nominal(), BASE_WINDOW), mean",
            "source_ids": [grid.SRC_G0],
            "source_files": [str(p.relative_to(grid.RAW.parents[1])) for p in (grid.NGC_2000, grid.BETTA_2004)],
            "pieces_price_base_fy": {k: v["price_base_fy"] for k, v in pieces.items()},
        },
        "bsuos": {
            "value_gbp_nominal": round(b * 1e6, 2),
            "period": BASE_PERIOD,
            "geography": "GB",
            "basis": ("B0 (spec §7.2, option 'ibc'): NGC incentivised balancing cost (England & "
                      "Wales) grossed up to GB by the demand ratio and to the BSUoS basis by SO "
                      "internal costs; FY2005/06 = NAO £642m (GB); time-weighted to calendar years, "
                      "mean of CY2002-2005; nominal £ (= balancing.go4 b_nom)"),
            "calendar_years_gbp_m": {str(y): v for y, v in b_cy.items()},
            "function": "gascf.balancing.fy_to_cy(gascf.balancing.baseline_fy('ibc')), mean",
            "source_ids": b_src,
            "alternative": {
                "option": "nao_2005",
                "value_gbp_nominal": round(b_alt * 1e6, 2),
                "note": ("NAO 2005/06 £642m for every year, CPIH-deflated. From v4-s33 used only "
                         "in the LOW end of the balancing range (stacked with the top workbook "
                         "energy share); the central is 'ibc' (Richard, 14 Oct 2026)."),
            },
        },
    }


GEN_SHARE = "included"
CARRY_FORWARD_RULE = ("For a calendar year after carry_forward.from (the engine's last modelled "
                      "year), the no-net-zero cost is that year's figure carried by CPIH: "
                      "value(y) = value(from) x CPIH(y) / CPIH(from). The Clock applies it with its "
                      "own CPIH series (and the latest index for a year without one, including the "
                      "run-rate), the same series it deflates every line with.")


def _gbp(gbp_m: float) -> float:
    return round(gbp_m * 1e6, 2)


def grid_series() -> dict:
    """GO5 per engine year, generators' share included (Clock export only; the engine's central
    removes it, 0024), £ nominal (spec §7.1, §7.3)."""
    from gascf import bills as B
    go = grid.go5(B.PRICE_BASE, B.YEARS, index="rpi", gen_share=GEN_SHARE)
    r = grid.renewal_allowance(B.YEARS)
    years = {}
    for y in B.YEARS:
        g = go[y]
        years[str(y)] = {
            "central_gbp": _gbp(g["gbp_m"]),
            "low_gbp": _gbp(g["high"]),          # net-zero cost LOW end: R high, largest no-net-zero grid
            "high_gbp": _gbp(g["low"]),          # net-zero cost HIGH end: R = 0
            "carried_by_index_gbp": _gbp(g["carried_gbp_m"]),
            "renewal_allowance_gbp": _gbp(r[y]["central"]),
            "renewal_allowance_low_gbp": _gbp(r[y]["low"]),
            "renewal_allowance_high_gbp": _gbp(r[y]["high"]),
        }
    src = sorted(set(go[min(B.YEARS)]["source_id"].split("|")))
    return {"years": years,
            "method": ("GO5 (spec §7.1, §7.3): G0 carried by the transmission price controls' own "
                       "index (RPI to FY2020/21, then CPIH; RIIO-ET2 PCFH para 2.17; "
                       "gascf.grid.control_index_fy), plus the grid renewal allowance R: the "
                       "non-load-related allowance above the 2002-05 level, rolled into an indexed "
                       "RAV, depreciated straight line over 45 years, earning the current control's "
                       "real allowed return (RIIO-ET2 PCFH para 4.1). Central = the whole allowance "
                       "(v4-s35, Richard); low/high are by NET-ZERO cost: low = central (R whole), "
                       "high = R not counted. Generators' share included."),
            "range_labels": RANGE_LABELS,
            "function": "gascf.grid.go5(PRICE_BASE, YEARS, index='rpi', gen_share='included')",
            "gen_share": GEN_SHARE, "source_ids": src}


def uplift_from_run(run: dict) -> dict[int, float]:
    """s36 F1 (ticket 10): Reliable Britain's own gas-price rise per engine year, read from the run
    file (`fleet[y].gas_feedback.price_rise_frac`), never recomputed at export time, so the export
    does not depend on the closure register this process sees. Missing, non-finite or negative
    raises (no silent zero). Version-blind: v4-s35 run files carry the field too."""
    from gascf import bills as B
    out = {}
    for y in B.YEARS:
        v = ((run.get("fleet", {}).get(str(y)) or {}).get("gas_feedback") or {}).get("price_rise_frac")
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(f"run file fleet[{y}].gas_feedback.price_rise_frac: {v!r}")
        out[y] = float(v)
    return out


def balancing_series(uplift: Mapping[int, float]) -> dict:
    """GO4 per engine year, generators' share included, £ nominal (spec §7.2), with the energy part
    at Reliable Britain's own feedback-raised gas price (s36 F1; `uplift` from `uplift_from_run`;
    no default and no zero-uplift path: one method in both models, spec §15.1 item 8)."""
    from gascf import bills as B
    if uplift is None:
        raise ValueError("balancing_series needs the run file's uplift (uplift_from_run)")
    shares = B.balancing_workbook_shares()
    pick = {"first": shares[2018], "min": min(shares.values()), "max": max(shares.values())}
    s = balancing.energy_share_2018()
    opt_c, which_c = B.go4_central_choice(GEN_SHARE).split("|")
    if (opt_c, pick[which_c]) != ("ibc", s):
        raise ValueError(f"central GO4 is not ibc + the FY2018/19 share: {opt_c}|{which_c}")
    low_k, high_k = B.go4_stacked_choice(GEN_SHARE), B.go4_high_choice(GEN_SHARE)
    mid = balancing.go4(B.PRICE_BASE, s, "ibc", B.YEARS, gen_share=GEN_SHARE, gas_uplift=uplift)
    lo = balancing.go4(B.PRICE_BASE, pick[low_k.split("|")[1]], low_k.split("|")[0], B.YEARS,
                       gen_share=GEN_SHARE, gas_uplift=uplift)
    hi = balancing.go4(B.PRICE_BASE, pick[high_k.split("|")[1]], high_k.split("|")[0], B.YEARS,
                       gen_share=GEN_SHARE, gas_uplift=uplift)
    years = {}
    crossing = [y for y in B.YEARS
                if not (lo[y]["gbp_m"] >= mid[y]["gbp_m"] >= hi[y]["gbp_m"])]
    for y in B.YEARS:
        years[str(y)] = {
            "central_gbp": _gbp(mid[y]["gbp_m"]),
            "low_gbp": _gbp(lo[y]["gbp_m"]),
            "high_gbp": _gbp(hi[y]["gbp_m"]),
            "energy_part_gbp": _gbp(mid[y]["energy_gbp_m"]),
            "services_part_gbp": _gbp(mid[y]["services_gbp_m"]),
            "energy_share": round(mid[y]["energy_share"], 6),
            "energy_share_of_b0": round(mid[y]["energy_share_of_b0"], 6),
        }
    src = sorted(set(mid[min(B.YEARS)]["source_id"].split("|")) | {balancing.SRC_NAO})
    return {"years": years,
            "method": ("GO4 (spec §7.2): B0 (option 'ibc', CY2002-05 mean) split into an energy part "
                       "carried by the gas price gas(y)/gas(2002-05) and a services part carried by "
                       "CPIH; energy share = NESO 2025 Annual Balancing Costs workbook, FY2018/19 "
                       "(central), a share of external cost, so applied to B0's external part "
                       "B0/(1 + SO internal ratio) only (v4-s35); SO internal costs ride on CPIH. "
                       "Energy part at Reliable Britain's own feedback-raised gas price, gas(y) x "
                       "(1 + u(y)), u read from the run file (s36 F1). "
                       "Generators' share included. Range, by NET-ZERO cost: low = the stacked option "
                       f"'{low_k}' (the largest no-net-zero cost), high = '{high_k}', each as one "
                       "rule for every year (chosen on the 2002-2025 total), so an end can cross the "
                       f"central: the high end lies above the central no-net-zero cost in "
                       f"{', '.join(map(str, crossing)) or 'no year'}."),
            "gas_uplift": {"rule": "Reliable Britain's own gas-price feedback (spec §15.5 item 2), "
                                   "read from the run file",
                           "price_rise_frac": {str(y): uplift[y] for y in B.YEARS}},
            "range_labels": RANGE_LABELS, "crossing_years": crossing,
            "function": ("gascf.balancing.go4(PRICE_BASE, energy_share_2018(), 'ibc', YEARS, "
                         "gen_share='included', gas_uplift=uplift_from_run(run))"),
            "central_option": B.GO4_CENTRAL, "low_option": low_k, "high_option": high_k,
            "gen_share": GEN_SHARE, "source_ids": src}


RANGE_LABELS = ("low/high = the ends of NET ZERO's cost range: low_gbp holds the LARGER "
                "no-net-zero cost (smaller net-zero cost), high_gbp the smaller")


def carry_forward() -> dict:
    from gascf import bills as B
    return {"from": max(B.YEARS), "index": "CPIH", "rule": CARRY_FORWARD_RULE}


NOTES = [
    "One method in both models (Richard, 14 Oct 2026; reports-programme no1-price-of-support/"
    "decisions.md): grid carried by the regulator's control index plus the renewal allowance; "
    "balancing split into a gas-price energy part and a CPIH services part, B0 'ibc', FY2018/19 "
    "energy share central. The Clock takes `grid` and `balancing` per year and computes no "
    "counterfactual itself; `baselines` (G0, B0) are kept for reference only.",
    "Generators' share: included here (the Clock has no power-price line). The engine's own bills "
    "remove it from both sides (gen_share='removed'); the bridge table reconciles the two.",
]


def build(run_path: Path, *, commit: str, created: str, run_commit: str | None = None) -> dict:
    run_path = Path(run_path)
    run = json.loads(run_path.read_text())
    root = Path(__file__).parents[2]
    rel = run_path.resolve().relative_to(root.resolve()) if run_path.is_absolute() else run_path
    return {
        "meta": {
            "engine_version": run["meta"]["engine_version"],
            "schema": SCHEMA,
            "commit": commit,
            "run_commit": run_commit,
            "run_file": str(rel),
            "run_sha256": sha256_file(run_path),
            "run_date": run["meta"].get("run_date"),
            "created": created,
            "money": "nominal £, calendar year",
        },
        "capacity_market": capacity_market(run),
        "grid": grid_series(),
        "balancing": balancing_series(uplift_from_run(run)),
        "carry_forward": carry_forward(),
        "baselines": baselines(),
        "notes": NOTES,
    }
