"""Write `out/v4/YYYY-MM-DD.json`: the two full bills and everything the site and paper read
(spec v4 §13). Run: `uv run python -m gascf.export_v4 [YYYY-MM-DD]`.

Money: national £m nominal and £m in 2025 money (ONS CPIH L522); per-household figures are
£ per GB household (ONS LFS, year-matched) in 2025 money. Every value carries `basis` and
source ids. Fields the engine cannot yet fill are present and tagged `UNSOURCED` / listed in
`meta.gaps`, never left out or filled with a guess.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import date
from pathlib import Path

from gascf import balancing, bills as B, bridge as R, carbon, prices, residual_neso as rn
from gascf import same_in_both
from gascf import waterfall as W

ROOT = Path(__file__).parents[2]
OUT = ROOT / "out/v4"
RAW = ROOT / "data/raw"
ENGINE_VERSION = "v4-s43"    # card [internal ticket]: point release, decision 0197 (Richard Lyon, 24 Oct 2026, msg 8982, "each year's own list"): the 2002-05 NI station lists, each year's own DUKES list (DUKES 2002 and 2003 Table 5.10 entered from the archived editions; DUKES 2004 and 2005 sheets read by station name), plus text-only fixes from the v4-s42 closure check; v4-s42: card [internal ticket]: point release, decision 0195 (Richard Lyon, 24 Oct 2026, msgs 8539 and 8676, "yes to all three"): the seven input-audit fixes (A1 Kilroot 2010-11, A2 NI CCGT 2006, A3 gas transport 2021-25, A4 2025 on EGC 2023, A5 2011 on PB 2011, C1 ETS 2016, D1 balancing FY2010/11 basis (i)); v4-s41: card [internal ticket]: point release, decision 0184 (Richard Lyon, 23 Oct 2026, msg 7888, "Do it."): table_results_by_year gains the two bills per MWh billed; no value moves; v4-s40: card [internal ticket]: step-3 items 1, 2 and 9 as ruled in decision 0175 (Richard Lyon, 23 Oct 2026, "Yes." 06:13:51 UTC, verified [internal ticket]): coal capped at its permit-derived energy limit, kept coal's M3 margin on the road's own revenue, the method checks exported outside the range; v4-s39: card [internal ticket]: Reliable Britain corrected, as ruled in decisions 0159-0170 (M2-M4, M6, M7 merit order, M8 MID shape both Britains, M9 B, coal permit hours (i), generators' share way 2, RO mutualisation, C-005/C-007/C-008/C-009/C-011); v4-s38: decision 0159 (Richard Lyon, 21 Oct 2026, "A we have to fix it."): Rugeley 1,006 MW (DUKES 2004-16 editions); otherwise as v4-s37, decision 0144 (Richard Lyon, 20 Oct 2026): the review findings on v4-s36 as ruled; s36 Route A before (rulings 0108, 0110, 0111, 0112)
# s33: central GO4 = ibc + FY2018/19 share (spec §15.1 item 8); clock-export/2 per-year grid/balancing
# s32: NZ5 rule (spec §5.4 rewritten: notional CM only on firm capacity GO1 does not pay)
SCHEMA_VERSION = "4.0"

GAPS = [
    "gas_break_even: linear in the gas-price rise (the dispatch is not re-run with dearer gas; "
    "second order, as in fossil_like_for_like.gas_feedback).",
    "firm_capacity.netzero_gw by type: the LCCC obligation file has no technology split; total only.",
    "§9.3 on-bill share: EPG green-levy transfer (Oct 2022-Jun 2023 for households not on prepayment) "
    "amounts not sourced; 2022-23 overstate the on-bill part.",
    "Same-in-both block: supplier costs before 2017 and metering 2004-16 UNSOURCED until s21a lands; "
    "both bills are lower bounds for those years by the same amount (the gap is unaffected).",
    "provenance: source ids are listed with the stored files' sha256; the full id→URL/quote map "
    "lives in data/raw/SOURCES.md (s21a registers the s18-s21 files).",
    "Sensitivities not yet run: build-cost L/M/H and hurdle by edition, CCGT efficiency range, "
    "shape premium, batteries in the residual (spec §11).",
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _m7_meta() -> dict:
    from gascf import marginal_carbon as M7
    return M7.run_meta()


def _m8_meta() -> dict:
    from gascf import hh_pricing as M8
    return M8.run_meta()


def _closures_meta() -> dict:
    import gascf.fossil_like_for_like as lfl
    p = Path(lfl.closures_path()).resolve()
    rel = str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
    meta = {"path": rel, "sha256": _sha(p)}
    sw = lfl.edition_mw_switches()
    if sw:      # card [internal ticket]: recorded only when a switch is on, so a default run file is unchanged
        meta["edition_mw_switches"] = list(sw)
    return meta


def _input_files() -> list[Path]:
    """Every stored file under data/raw named by a module-level Path in the engine modules
    the bills read (directories expanded)."""
    import gascf.capacity, gascf.deflator_cpih, gascf.fossil_fleet, gascf.gastransport, gascf.grid  # noqa: E401
    import gascf.households, gascf.residual_neso, gascf.same_in_both, gascf.subsidies  # noqa: E401
    import gascf.fossil_like_for_like, gascf.schemes  # noqa: E401
    mods = [balancing, carbon, prices, rn, gascf.capacity, gascf.deflator_cpih, gascf.fossil_fleet,
            gascf.fossil_like_for_like,
            gascf.gastransport, gascf.grid, gascf.households, gascf.residual_neso,
            gascf.same_in_both, gascf.subsidies, gascf.schemes]
    files: set[Path] = set()
    for m in mods:
        for v in vars(m).values():
            vals = v.values() if isinstance(v, dict) else [v]
            for p in vals:
                if isinstance(p, Path) and RAW in p.parents and p.exists():
                    files |= {q for q in p.rglob("*") if q.is_file()} if p.is_dir() else {p}
    for y in B.YEARS:
        p = rn.neso_path(y)
        if p.exists():
            files.add(p)
    return sorted(files)


def _counterfactual_text() -> str:
    """One plain description of the central counterfactual, for the run file's meta (v4-s39 rulings named)."""
    if B.CENTRAL.fleet != "like_for_like":
        return "fossil Britain (coal and gas, built new); coal forced to actual GB capacity"
    return ("fossil Britain, like for like (s22): the actual system with net zero taken out; renewables' output "
            "replaced by extra running of existing fossil plant, then new CCGT/OCGT; merit-order uplift from "
            "Shao et al. 2022 (spec §15.5 item 1) in 2002-20, Jan-Apr 2021 and 2024-25p, and re-estimated on "
            "outturn with direct coefficients from May 2021 to Dec 2023 (0164, M9 B); extra running of the plant "
            "Britain had at the market price (0144 item 1A); gas-price feedback dQ / ((e_s + e_d) Q), "
            "e = 0.06 + 0.169 (Albrizio et al. 2022's pair, 0144 item 2A); 'mixed' closures by the margin test at "
            "the road's own coal load factor, kept coal paid its fixed cost less its margin, filter running cost "
            "in the price (0163 M2-M4); every coal station on its real permit hours, the 2011-14 LCPD opt-outs "
            "included and the kept LCPD stations held (0166, reading (i)); carbon in real Britain's price at the "
            "marginal plant from 1 Jan 2009 (0167, M7 merit order); half-hourly prices by Ofgem's month with "
            "Elexon MID's half-hour shape in both Britains from 12 Sep 2016 (0167, M8); the net-zero part of the "
            "generators' share of BSUoS and TNUoS taken out of fossil Britain's market price (0167, way 2); "
            "RO mutualisation payments received counted in the RO (0169); the five closures at their DUKES "
            "edition MW (C-009)")


def _meta(run_date: str) -> dict:
    files = _input_files()
    return {
        "engine_version": ENGINE_VERSION, "schema_version": SCHEMA_VERSION, "run_date": run_date,
        "headline_year": B.HEADLINE_YEAR, "latest_full_year": B.LATEST_FULL_YEAR,
        "provisional_years": list(B.PROVISIONAL_YEARS), "price_base": B.PRICE_BASE,
        "deflator": "ONS CPIH L522", "households_source": "ons_lfs_households_by_size_2025;ons-adhoc-005374-households-region-1996-2017 (GB: England + Wales + Scotland)",
        "counterfactual": _counterfactual_text(),
        "central_settings": vars(B.CENTRAL) | {"bal_choice": B.go4_central_choice(B.CENTRAL.bsuos_gen)},
        "residual_method": "NESO demand-side, every year (departure from §4.1 2016+ FUELHH; see bills.py)",
        "calibration_rule": rn.DEFAULT_CALIBRATION_RULE,
        "pre2016_publishable": rn.calibration_passes(),
        "input_checksums": {str(p.relative_to(ROOT)): _sha(p) for p in files},
        # the fossil-Britain closure register the run used (tests compare a fresh build with it)
        "closures_register": _closures_meta(),
        # RB v1.1 M7 (0163 R8 (a)): which carbon intensity the price is taken out at, and from when
        "carbon_marginal": _m7_meta(),
        # RB v1.1 M8 (0163 R9 (a)): half-hourly pricing switch and its break
        "hh_pricing": _m8_meta(),
        "gaps": GAPS,
    }


def _years(built: dict) -> list[dict]:
    from gascf.fossil_fleet import gas_price_month
    pe, cm = B.p_elec(B.CENTRAL.route), B.c_marg()
    V = B.v_monthly()
    out = []
    for y in B.YEARS:
        ks = [(y, m) for m in range(1, 13)]
        w = sum(V[k] for k in ks)
        gas = [gas_price_month(y, m) for m in range(1, 13)]
        out.append({
            "year": y, "households": built[y]["households"], "volume_twh": w,
            "volume_basis": built[y]["volume"]["basis"],
            "nuclear_ic_ps_net_twh": built[y]["volume"]["kept_twh"],   # 46: nuclear+imports+PS, net, full precision
            "station_load_twh": built[y]["volume"]["station_load_twh"],   # 0059; key station_load_twh_yr (0108 1.15)

            "gas_price_gbp_mwh": statistics.mean(g[0] for g in gas),
            "gas_price_source": "+".join(sorted({g[2] for g in gas})),
            "wholesale_gbp_mwh": sum(pe[k]["gbp_per_mwh"] * V[k] for k in ks) / w,
            "wholesale_basis": B.weakest(*(pe[k]["basis"] for k in ks)),
            "wholesale_source": "+".join(sorted({pe[k]["source_id"] for k in ks})),
            "carbon_marginal_gbp_mwh": sum(cm[k]["gbp_per_mwh"] * V[k] for k in ks) / w,
            "provisional": y in B.PROVISIONAL_YEARS,
            "residual_calibration_pass": True if y < 2016 and rn.calibration_passes() else
            (next((c["pass"] for c in rn.calibration_table() if c["year"] == y), None)),
        })
    return out


def _bills(built: dict, wf: dict) -> dict:
    out = {}
    for y in B.YEARS:
        b = built[y]
        hb = B.on_household_bill(b, y, wf[y])
        out[str(y)] = {
            "netzero": b["netzero"], "gasonly": b["fossil"], "same_in_both": b["same_in_both"],
            "nz1c": b["nz1c"], "same_in_both_complete": b["totals"]["s1_complete"],
            "totals": {k: v for k, v in b["totals"].items()},
            "netzero_on_household_bill_per_household": hb,
            "netzero_groups": _groups(b, y),
            "waterfall_grouped": W.grouped(wf[y]),
        }
    return out


def _groups(b: dict, y: int) -> dict:
    """Net-zero Britain's bill by reader group (§15.3 item 3), nominal £m, 2025 £m and £ per
    household; the 'net zero extra' in each group is the matching waterfall steps."""
    H = b["households"]
    out = {}
    split = "carbon_split" in b
    for g in ("power",) + (B.GROUPS if split else B.GROUPS_SINGLE_CARBON):
        lines = [l for l in b["netzero"] if l["group"] == g]
        if g == "carbon":
            lines = lines + [b["nz1c"]]
        elif split and g in b["carbon_split"]:
            lines = lines + [b["carbon_split"][g]]
        nom = sum(l["national_gbp_m_nominal"] for l in lines)
        if g == "power":
            nom -= b["nz1c"]["national_gbp_m_nominal"]        # power before carbon
        out[g] = {"label": B.GROUP_LABELS[g], "lines": [l["id"] for l in lines],
                  "national_gbp_m_nominal": nom, "per_household_real": B.real(nom, y) * 1e6 / H}
    return out


def _gap(built: dict, rg: dict) -> dict:
    out = {}
    for y in B.YEARS:
        H = built[y]["households"]
        r = lambda v: B.real(v, y)                     # noqa: E731
        g = rg[y]
        out[str(y)] = {
            "national_gbp_bn_real": r(g["central"]) / 1e3, "per_household_real": r(g["central"]) * 1e6 / H,
            "low": {"national_gbp_bn_real": r(g["low"]) / 1e3, "per_household_real": r(g["low"]) * 1e6 / H},
            "high": {"national_gbp_bn_real": r(g["high"]) / 1e3, "per_household_real": r(g["high"]) * 1e6 / H},
            "national_gbp_m_nominal": g["central"],
            # W2 (R23 (a), 0163): the gap is a model output, "modelled" in the release and the paper. Each line keeps
            # its own data basis (bills[y] lines; Annex B's tags).
            "basis": "modelled",
        }
    return out


def _fleet(built: dict) -> dict:
    keys = ("coal_gw", "coal_cap_gw", "ccgt_gw", "ocgt_gw", "spare_gw", "energy_twh", "fixed_gbp_m",
            "fuel_gbp_m", "vom_gbp_m", "transport_gbp_m", "gbp_per_mwh", "cost_edition", "gas_burn_twh",
            "gen_twh", "basis", "gen_nz_charge")      # gen_nz_charge: 0167 way 2, present only when the switch is on
    lfl = ("market_gbp_m", "moe_gbp_m", "moe_kept_gbp_m", "existing_gw", "existing_derated_gw", "new_gw",
           "firm_extra_gw", "renewables_replaced_twh", "new_total_gbp_m", "extra_running_gbp_m", "moe", "method",
           "new_coal_gw", "kept_gw", "kept_abated_gw", "kept_stations", "kept_fixed_gbp_m", "kept_abatement_vom_gbp_m",
           "kept_detail", "closures", "newbuild", "nuclear_note", "extra_gen_by_block_twh",
           "gas_feedback_gbp_m", "gas_feedback_kept_gbp_m", "gas_feedback_at_cost_gbp_m", "gas_feedback",
           "gas_marginal_share", "coal_lf",
           # 0144 item 1A (v4-s37): the extra running at the market price, its parts and the cost no longer counted
           "extra_running", "extra_twh", "extra_market_gbp_m", "extra_moe_gbp_m", "extra_gas_feedback_gbp_m",
           "extra_cost_not_counted_gbp_m",
           "ic_called_twh", "ic_called_halfhours", "ic_called_gbp_m",     # 0063 (ticket 15, spec test 14)
           "worked_hh",                                                  # 44 (B20): 2024 worked half-hours
           # D6 (ticket 15) and 0066: bills._ic_fields, exported at the s36 release run (19 Oct 2026)
           "ic_basis", "sizing_peak_gross_gw", "sizing_peak_residual_mw", "sizing_peak_halfhour", "margin_fraction",
           "firm_requirement_gw", "margin_on_gross_extra_gw", "nuclear_at_peak_gw", "ps_at_peak_gw",
           "imports_metered_at_peak_gw", "imports_contracted_gw", "imports_counted_gw",
           "ic_peak_dy", "ic_peak_dy_contracted_mw",
           # card [internal ticket] (sweep-flags row 6; 0175 item 2): kept coal's pay by year (fixed cost, road margin after
           # the generators' charge, life-extension cost, paid), so the run file shows item 2's result
           "kept_coal_pay")
    return {str(y): {k: built[y]["fleet"][k] for k in keys + lfl if k in built[y]["fleet"]} for y in B.YEARS}


def _all_new(built: dict) -> dict:
    """The s21b all-new method (switch `fleet="all_new"`), gap only, for comparison (s22)."""
    a = B.build(B.ALL_NEW)
    return {str(y): {"gap_per_household_real": a[y]["totals"]["gap_per_hh_real"],
                     "gap_national_gbp_bn_real": a[y]["totals"]["gap_real_bn"],
                     "like_for_like_minus_all_new_per_household_real":
                         built[y]["totals"]["gap_per_hh_real"] - a[y]["totals"]["gap_per_hh_real"]}
            for y in B.YEARS}


def _firm(built: dict) -> dict:
    from gascf import capacity
    der = capacity.read_derating()
    out = {}
    for y in B.YEARS:
        f, cm = built[y]["fleet"], built[y]["cm"]
        out[str(y)] = {
            "gasonly_gw": cm["fossil_firm_gw"],
            "gasonly_cm_split_gw": cm.get("split_gw"),
            "gasonly_by_type_derated_gw": {"coal": f["coal_gw"] * der["ccgt"], "ccgt": f["ccgt_gw"] * der["ccgt"],
                                           "ocgt_and_spare": (f["ocgt_gw"] + f["spare_gw"]) * der["ocgt"],
                                           "kept_at_peak": B.kept_at_peak_gw(y)},
            "netzero_gw": cm["obligation_mw"] / 1e3 if cm["obligation_mw"] else None,
            "netzero_note": "mean monthly Capacity Market obligation (LCCC), de-rated; by type UNSOURCED"
            if cm["obligation_mw"] else "no Capacity Market before Oct 2016",
            "basis": "modelled",
        }
    return out


def _cm(built: dict) -> dict:
    """s32, spec §5.4: NZ5 per year with its parts, the unfloored value, and the low / high rules
    (kept coal needs CM / full CM). £m nominal; GW de-rated."""
    low = B.build(B.replace(B.CENTRAL, cm_rule="extra_kept_coal"))
    high = B.build(B.replace(B.CENTRAL, cm_rule="full"))
    out = {}
    for y in B.YEARS:
        c = built[y]["cm"]
        if not c["paid_gbp_m"]:
            continue
        out[str(y)] = {"cm_paid_gbp_m": c["paid_gbp_m"], "price_gbp_kw_yr": c["price_gbp_kw_yr"],
                       "price_basis": c["price_basis"], "reliable_britain_cm_gw": c["cm_gw"],
                       "reliable_britain_cm_gbp_m": c["fossil_gbp_m"], "split_gw": c["split_gw"],
                       "worked_example": c["worked_example"],
                       "nz5_gbp_m": B.val(built[y], "NZ5"), "nz5_unfloored_gbp_m": c["nz5_unfloored_gbp_m"],
                       "nz5_floored": c["nz5_floored"],
                       "nz5_low_gbp_m": B.val(low[y], "NZ5"),
                       "nz5_low_unfloored_gbp_m": low[y]["cm"]["nz5_unfloored_gbp_m"],
                       "nz5_high_gbp_m": B.val(high[y], "NZ5"),
                       "nz5_real": B.real(B.val(built[y], "NZ5"), y),
                       "note": "NZ5 is a floor: today's £/kW is applied to Reliable Britain, but the 550 g/kWh "
                               "CM emissions limit shut 11 GW of coal out of T-4 (Ofgem CM AR 2020/21-2021/22 "
                               "para 3.49); its effect on the price is UNSOURCED (spec §5.4)."}
    return out


def _carbon_check(built: dict) -> dict:
    from gascf import register_pin as RP
    cps = RP.register().line("CPS", "clock_live")     # 0168: HMRC CPF receipts as the Clock counts them (none in 2013)
    out = {}
    for y in B.YEARS:
        inw = B.val(built[y], "NZ1c")
        if "carbon_split" in built[y]:
            col = built[y]["carbon_split"]["carbon_price_receipts"]["national_gbp_m_nominal"]
            note = ("HMRC CPF receipts + UK auction receipts on power, ETS part scaled to GB (0078); "
                    "2008-12 as traced (data/raw/s36/ets/uk-ets-phase2-auctions.csv, 2012 Phase III row apart, "
                    "s36 ticket 20); 2013-20 data/raw/s36/ets/uk-auction-revenue-2013-20-calendar.csv (calendar years, 0110) x the 0055 stand-in; "
                    "2021-24 calendar sums of data/raw/s36/ets/ukets-auctions-2021-24.csv x DESNZ shares (0055, "
                    "0012); 2025 provisional: ICE report 278 auctions x 2024 share (0079), CPS about 428 (0054)")
        else:
            col = cps.get(y) or None
            note = "HMRC estimated CPF receipts only (ETS auction share not computed)"
        out[str(y)] = {"in_wholesale_gbp_m": inw, "collected_gbp_m": col, "collected_note": note,
                       "ratio": inw / col if col else None}
    return out


def _sens(rg: dict, built: dict) -> dict:
    out = {}
    for y in B.YEARS:
        H = built[y]["households"]
        out[str(y)] = [{"switch": n, "low_per_household_real": B.real(v["low"], y) * 1e6 / H,
                        "high_per_household_real": B.real(v["high"], y) * 1e6 / H,
                        "low_gbp_m_nominal": v["low"], "high_gbp_m_nominal": v["high"]}
                       for n, v in rg[y]["switches"].items()]
    return out


def _methods_page(built: dict) -> dict:
    """§15.3 item 1: the merit-order uplift (the critic's argument) and the effect of the two
    other §15.3 changes, each one at a time from central. Never in the low-high range."""
    out = {}
    for name, sets in B.METHOD_SWITCHES.items():
        runs = [B.build(st) for st in sets]
        out[name] = {str(y): {"gap_per_household_real": [r[y]["totals"]["gap_per_hh_real"] for r in runs],
                              "minus_central_per_household_real":
                                  [r[y]["totals"]["gap_per_hh_real"] - built[y]["totals"]["gap_per_hh_real"]
                                   for r in runs]}
                     for y in B.YEARS}
    return out


# Real payments that exist only because of net-zero / climate policy and are counted in no line
# (brief s23 item 4: flagged with their size, not added without the parent's approval).
# s24: the energy-saving obligations (EEC, CERT, CESP, ECO, GBIS) are now counted as line NZ10
# (spec §15.4 item 1, Richard's decision); nothing else is flagged as uncounted here.
UNCOUNTED: dict[str, dict] = {}


def gas_break_even(built: dict) -> dict:
    """Spec §11 / §15.5 item 2: the gas-price rise in fossil Britain at which the gap is zero,
    with the gas-price feedback ON. Every feedback channel (at-cost gas fuel, market-priced fossil
    MWh x gas-marginal share, kept market-priced MWh) is linear in the price-rise fraction f, so
    the gap is gap(f) = gap_central - F x (f - f_c) / f_c, where F = the central feedback £m and
    f_c the central fraction (e = 0.06 + 0.169, Albrizio's pair, 0144). Break-even f* = f_c + gap_central x f_c / F. Shown as
    a fraction, as £/MWh on the year's mean gas price, and as the elasticity e* (supply + demand) = dQ/(f* Q)
    that would deliver it (Q = EU 4,000 TWh + GB demand ET 4.1, now held)."""
    out = {}
    for y in B.YEARS:
        f = built[y]["fleet"]
        g = f.get("gas_feedback") or {}
        gap = built[y]["totals"]["gap_gbp_m"]
        fc = g.get("price_rise_frac", 0.0)
        # s36 F1 (ticket 10; 0031 item 11): GO4's own feedback joins the GO1 channels, and GO7's
        # VAT on all of it (GO7 is linear in GO1, GO1k and GO4): F x (1 + 0.05 d).
        go4, go7 = B.line(built[y], "GO4"), B.line(built[y], "GO7")
        F = (f.get("gas_feedback_gbp_m", 0.0) + f.get("gas_feedback_kept_gbp_m", 0.0)
             + f.get("gas_feedback_at_cost_gbp_m", 0.0) + go4.get("gas_feedback_gbp_m", 0.0)) \
            * (1 + same_in_both.domestic_vat_rate()["rate"] * go7.get("domestic_share", 0.0))
        row = {"gap_central_gbp_m_nominal": gap, "feedback_central_gbp_m_nominal": F,
               "price_rise_frac_central": fc, "dq_twh": g.get("dq_twh"), "q_twh": g.get("q_twh"),
               "elasticity_central": g.get("elasticity"), "basis": "modelled",
               "source_ids": g.get("source_ids", [])}
        if fc * F > 0:      # M6 (0163 R7 (a)): fc and F may both be negative (fossil Britain burns less gas)
            fstar = fc + gap * fc / F
            from gascf.fossil_fleet import gas_price_month
            gp = statistics.mean(gas_price_month(y, m)[0] for m in range(1, 13))
            row |= {"price_rise_frac": fstar, "gas_price_gbp_mwh_actual": gp,
                    "price_rise_gbp_mwh": fstar * gp, "gas_price_gbp_mwh_break_even": gp * (1 + fstar),
                    "elasticity_break_even": g["dq_twh"] / (fstar * g["q_twh"]) if fstar != 0 else None}
        else:
            row |= {"price_rise_frac": None, "note": "fossil Britain burns the actual gas this year (dQ = 0): "
                    "no feedback channel, no break-even"}
        out[str(y)] = row
    return out


def _answers(built: dict) -> dict:
    gms = {str(y): {"fossil_britain_load": built[y]["fleet"].get("gas_marginal_share"),
                    "actual_load_check": (built[y]["fleet"].get("gas_feedback") or {}).get(
                        "gas_marginal_share_actual_load"),
                    "basis": "modelled", "source_id": "engine-merit-order-stack",
                    "check": "Zakeri et al. 2023 Fig. 7: gas set the GB price >80% of the time in 2021"}
           for y in B.YEARS}
    return {"gas_break_even": gas_break_even(built),
            "gas_marginal_share": gms,
            "desnz_2030_context": {"label": "DESNZ's own figure: £70/MWh at DESNZ's 2030 gas price "
                                            "(context only, never a chart or waterfall line)",
                                   "gbp_mwh": 70, "source_id": "desnz-egc-2025-report"}}


def _calibration_early(built: dict) -> dict:
    """Ticket 13 (0061, D6) with the 0111 disclosure: the pooled 2002-04 early-years check."""
    from gascf import calibration_block
    return calibration_block.build_block(built)


def _tests(built: dict, wf: dict, br: dict) -> dict:
    vol = {}
    for y in B.YEARS:
        v = built[y]["volume"]
        vol[str(y)] = (v["fleet_twh"] + v["kept_twh"] - v["station_load_twh"]) / v["v_twh"] - 1
    return {
        "waterfall_identity_max_abs_gbp_m": max(abs(W.identity_error(wf[y])) for y in B.YEARS),
        "bridge_identity_max_abs_gbp_m": max(abs(br[y]["error"]) for y in B.YEARS),
        "volume_identity_err": vol,
        "calibration_early": _calibration_early(built),
        "calibration": {"rule": rn.DEFAULT_CALIBRATION_RULE,
                        "loosened": rn.calibration_table(), "strict": rn.calibration_table(rule="strict"),
                        "pre2016_publishable": rn.calibration_passes()},
    }


def provenance(built: dict) -> dict:
    ids: set[str] = set()
    for y in B.YEARS:
        for l in (built[y]["netzero"] + built[y]["fossil"] + built[y]["same_in_both"] + [built[y]["nz1c"]]
                  + list(built[y].get("carbon_split", {}).values())):
            ids |= set(l["source_ids"])
    sm = (RAW / "SOURCES.md").read_text()
    files = {str(p.relative_to(ROOT)): {"sha256": _sha(p), "in_SOURCES_md": p.name in sm}
             for p in _input_files()}
    return {"source_ids": sorted(ids), "files": files, "register": "data/raw/SOURCES.md"}


# Run-file block hook (ticket 02): a ticket adds a module that calls register_block(name, fn), not lines in
# build_payload. fn(built) returns the block. With nothing registered the payload is unchanged.
_BLOCKS: dict = {}
BLOCK_MODULES: list[str] = ["gascf.one_at_a_time", "gascf.grid_blocks", "gascf.carbon_blocks", "gascf.moe_crisis_block",
                             "gascf.otr_blocks", "gascf.pricing_block", "gascf.balancing_factors_block",
                             "gascf.pos_cm_block", "gascf.case_b", "gascf.non_power_gas", "gascf.release_step_effects"]   # dotted module names, imported by build_payload so their blocks register


def register_block(name: str, fn) -> None:
    _BLOCKS[name] = fn


def build_payload(run_date: str) -> dict:
    built = B.build()
    wf = W.waterfall()
    br = R.bridge()
    rg = B.ranges()
    meta = _meta(run_date)
    payload = {
        "meta": meta,
        "years": _years(built),
        "bills": _bills(built, wf),
        "gap": _gap(built, rg),
        "waterfall": {str(y): wf[y] for y in B.YEARS},
        "fleet": _fleet(built),
        "all_new_comparison": _all_new(built),
        "firm_capacity": _firm(built),
        "carbon_crosscheck": _carbon_check(built),
        "bridge": {str(y): br[y] for y in B.YEARS},
        "bridge_clock_check": {str(y): {"clock_check": br[y].get("clock_check"),
                                        "clock_blank": br[y].get("clock_blank")} for y in B.YEARS},
        "clock_cm_correction": {str(y): v for y, v in R.clock_cm_correction().items()},
        "capacity_market": _cm(built),
        "sensitivities": _sens(rg, built),
        "methods_page": _methods_page(built),
        "uncounted_net_zero_payments": UNCOUNTED,
        "answers": _answers(built),
        "provenance": provenance(built),
        "tests": _tests(built, wf, br),
    }
    import importlib
    for m in BLOCK_MODULES:
        importlib.import_module(m)
    for name, fn in _BLOCKS.items():
        if name in payload:
            raise ValueError(f"run-file block {name!r} would replace an existing key")
        payload[name] = fn(built)
    from gascf import fallbacks
    # every fallback that fired anywhere in the run (central, range and methods-page builds), with size
    meta["fallbacks"] = fallbacks.recorded()
    return payload


def write(run_date: str | None = None, suffix: str = "") -> Path:
    run_date = run_date or date.today().isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{run_date}{suffix}.json"
    p.write_text(json.dumps(build_payload(run_date), indent=1, default=str, allow_nan=False))
    return p


if __name__ == "__main__":
    # `python -m gascf.export_v4 [YYYY-MM-DD] [suffix]`, e.g. `2026-10-11 -s22`. Run the IMPORTED module's write: the
    # block modules register into gascf.export_v4, not into __main__ (found at the s36 release run, 19 Oct 2026).
    from gascf import export_v4 as _self
    print(_self.write(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2] if len(sys.argv) > 2 else ""))
