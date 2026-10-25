"""Decision 0162 (Richard Lyon, 21 Oct 2026) in the release's annex generator; card [internal ticket] item 8.

- The new Annex E, "Version and change log" (0162 items 3-4):
  * annex_e_before_after: every headline figure and range end (and the two labelled estimates beside the gap), v4-s37
    as published (its figures.json, sha256-checked against releases.yaml) against this run;
  * annex_e_change_log: the measured steps, in build order, from reference/change_log_v4_s39.json, with the sum of the
    measured steps and what is left to measure.
  The old Annex E (Reconciliation, annex_e_bridge) is cut (0162 item 1; tools/figures_keys/recut_0122.py).
- Annex D in full (0162 item 6): table_vat_working, table_carbon_split_by_year, table_2001_levels_working, and
  annex_d_working_index, which names for each derived figure the keys that give it and its working.
- Annex C (read-through item 99): annex_c_equations and annex_c_parameters. Parameter values are read from the code
  and the run, never typed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gascf.figures import PRICE_BASE_LABEL, to_2024

ROOT = Path(__file__).resolve().parents[2]
CHANGE_LOG = ROOT / "reference/change_log_v4_s39.json"
BEFORE = "v4-s37"                       # 0162 item 3: "v1.0 (v4-s37) against the new release"
Y02_24 = [str(y) for y in range(2002, 2025)]
Y02_25 = Y02_24 + ["2025"]

HEADLINE_KEYS = (
    "headline_2002_24_gbp_bn", "headline_2002_24_low_gbp_bn", "headline_2002_24_high_gbp_bn",
    "headline_low_end_option", "headline_high_end_option", "headline_range_text",
    "gap_2024_gbp_bn", "gap_2025p_gbp_bn",
    "cost_per_household_2002_24_gbp", "cost_per_household_2024_gbp", "cost_per_household_2025p_gbp",
    "own_bills_per_household_2002_24_gbp", "own_bills_per_household_2024_gbp", "own_bills_per_household_2025p_gbp",
    "nz_bill_2002_24_gbp_bn", "rb_bill_2002_24_gbp_bn",
    "wf_power_before_carbon_gbp_bn", "wf_carbon_gbp_bn", "wf_ro_gbp_bn", "wf_fit_gbp_bn", "wf_cfd_gbp_bn",
    "wf_cm_gbp_bn", "wf_balancing_gbp_bn", "wf_grid_gbp_bn", "wf_ccl_extra_gbp_bn", "wf_schemes_gbp_bn",
    "wf_vat_gbp_bn")
BESIDE_GAP_KEYS = ("lost_value_2002_24_central_gbp_bn", "npg_estimate_2002_24_central_gbp_bn")


def _m(label, run_field, units, period, basis="modelled", **extra):
    return {"label": label, "basis": basis, "provisional": False, "ticket": "t_6c0411d4 item 8 (0162)",
            "run_field": run_field, "units": units, "period": period, "price_base": PRICE_BASE_LABEL,
            "status": "SOURCED", "print": True, "decisions": ["0162"], **extra}


DECLARED = {
    "annex_e_before_after": _m(
        "Annex E (Version and change log): every headline figure and range end, v4-s37 (v1.0, as published) against "
        "this release, and the change; the two labelled estimates beside the gap shown apart",
        "out/figures/v4-s37.json (releases.yaml figures_sha256) and this run's keys", "table, £bn and £ a household, "
        "2024 prices", "2002-2025"),
    "annex_e_change_log": _m(
        "Annex E (Version and change log): each change from v4-s37 to this release in build order, with its own "
        "measured effect on the 2002-24 headline, the sum of the measured steps, and any step still to measure",
        "reference/change_log_v4_s39.json", "table, £bn, 2024 prices", "2002-2024"),
    "table_vat_working": _m(
        "Annex D, VAT on the extra: by year, households' domestic share, the 5% rate, NZ11, GO7 and the VAT on the "
        "extra (NZ11 less GO7); NZ11 = 5% x (share x (NZ1 to NZ7) + NZ10), GO7 = 5% x share x (GO1 to GO5)",
        "bills[y] NZ11, GO7 and netzero_on_household_bill_per_household.domestic_share", "table, £bn, 2024 prices",
        "2002-2025"),
    "table_carbon_split_by_year": _m(
        "Annex D, the carbon split: by year, carbon in the wholesale price (NZ1c, inside NZ1, never added), of which "
        "carbon prices collected as tax on power (NZ1c_tax) and the rest (NZ1c_price)",
        "bills[y].nz1c; waterfall[y] step 2 parts", "table, £bn, 2024 prices", "2002-2025"),
    "table_2001_levels_working": _m(
        "Annex D, the 2001 levels and their netting: by year, the Fossil Fuel Levy (NZ2, to 2019) and EESoP (NZ10) "
        "netted at their 2001 levels with the VAT each carried, and the CCL netted at its 2001 rate (NZ8)",
        "on_the_road.years[y] (the amounts the build netted)", "table, £bn, 2024 prices", "2002-2025"),
    "annex_d_working_index": _m(
        "Annex D in full (0162 item 6): for each derived figure, the keys that give it and the keys that give its "
        "working", "figures.json keys", "index", "release"),
    "annex_c_equations": _m(
        "Annex C: the engine's equations in summary, each with the code that computes it and the spec or decision "
        "that sets it; the code at the release tag is the authority",
        "tools/figures_keys/annex_v11.py EQUATIONS; non_power_gas.method from the run", "text", "release"),
    "annex_c_parameters": _m(
        "Annex C: the engine's parameters with their values, units and sources, read from the code and the run",
        "gascf constants and meta.central_settings", "table", "release"),
}

EQUATIONS = [
    {"id": "gap", "name": "The gap, each year",
     "equation": "gap(y) = NZ(y) - RB(y); NZ(y) = NZ1 + NZ2 + NZ3 + NZ4 + NZ4b + NZ5 + NZ6 + NZ7 + NZ8 + NZ10 + NZ11 + "
                 "S1; RB(y) = GO1 + GO1k + GO2 + GO3 + GO4 + GO5 + GO6 + GO7 + S1. NZ1c (carbon in NZ1) and GO2 "
                 "(backup inside GO1) are 'of which' rows, never added. S1, the same-in-both block, cancels.",
     "code": "gascf.bills.build (totals); gascf.export_v4._gap", "set_by": "spec §3, §9.2; brief §1"},
    {"id": "headline", "name": "The headline",
     "equation": "headline = Σ over 2002-24 of gap(y) x CPIH(2024) / CPIH(y); 2025 provisional, never in the sum.",
     "code": "gascf.deflator_cpih; gascf.figures.to_2024; tools.figures_keys.core", "set_by": "spec §1, §8; 0035; 0093"},
    {"id": "per_household", "name": "Per household",
     "equation": "cost per household(y) = gap(y) in 2024 prices / households(y) (ONS, GB); summed over 2002-24 for "
                 "the 2002-24 figure. Of which on a household's own bill: the household share of each line plus VAT, "
                 "CCL excluded.",
     "code": "gascf.bills.build (totals.gap_per_hh_real); gascf.household_bill", "set_by": "spec §8, §9.3; 0025; 0122"},
    {"id": "vat", "name": "VAT, both bills",
     "equation": "NZ11 = v x (d x (NZ1 + NZ2 + NZ3 + NZ4 + NZ4b + NZ5 + NZ6 + NZ7) + NZ10); GO7 = v x d x (GO1 + GO1k + "
                 "GO2 + GO3 + GO4 + GO5); v = 5% (domestic rate), d = households' share of supply (DUKES 5.2, 5.5.D). "
                 "VAT on the extra = NZ11 - GO7.",
     "code": "gascf.bills.build (NZ11, GO7)", "set_by": "spec §3; s30"},
    {"id": "go1", "name": "Reliable Britain's power (GO1)",
     "equation": "GO1 = the plant Britain had on its actual output at the actual price less carbon + extra running of "
                 "that plant for renewables' output at the market price + new plant (fixed, fuel, running, transport) "
                 "+ the merit-order uplift (Shao et al. 2022 coefficients in 2002-20, Jan-Apr 2021 and 2024-25p; "
                 "re-estimated on outturn with direct coefficients from May 2021 to Dec 2023, decision 0164) "
                 "+ the gas-price feedback; each part by "
                 "year is in the run file's GO1 note and fleet[y].",
     "code": "gascf.fossil_like_for_like.lfl_year; gascf.bills.fleet_lfl", "set_by": "spec §15.3-§15.5; 0144 item 1A"},
    {"id": "gas_feedback", "name": "Gas-price feedback",
     "equation": "dP / P = dQ / ((e_s + e_d) x Q), with dQ the road's extra gas burn and Q the gas market's volume; "
                 "central e_s + e_d = 0.06 + 0.169; both ways (dQ signed): the price rises in years when the road "
                 "burns more gas than Britain did and falls in years when it burns less.",
     "code": "gascf.fossil_like_for_like (GAS_ELASTICITY, GAS_FEEDBACK_RULES)",
     "set_by": "spec §15.6; 0033; 0144 item 2A; Albrizio et al. (2022) eq. 5"},
    {"id": "carbon_once", "name": "Carbon, counted once",
     "equation": "NZ1c = the carbon part of the wholesale price, inside NZ1 (NZ1c_tax: carbon prices collected as tax "
                 "on power; NZ1c_price: the rest). GO3 = 0: Reliable Britain pays no carbon price.",
     "code": "gascf.carbon; gascf.waterfall (step 2 parts)", "set_by": "spec §6; 0090; 0144 item 5a"},
    {"id": "capacity_market", "name": "Backup (NZ5)",
     "equation": "NZ5 = the Capacity Market actually paid less what Reliable Britain's own fleet would have needed, "
                 "floored at zero under the central rule.",
     "code": "gascf.bills.build (cm block)", "set_by": "spec §5.4; s32"},
    {"id": "levels_2001", "name": "The 2001 levels",
     "equation": "NZ2 counted = the line less the Fossil Fuel Levy at its 2001 level (to 2019); NZ10 counted = the "
                 "line less EESoP at its 2001 level x its electricity share; NZ8 counted = the CCL above its 2001 rate; "
                 "each netting takes its VAT with it.",
     "code": "gascf.on_the_road; gascf.otr_blocks; gascf.ccl_baseline", "set_by": "0044; 0097; 0101"},
    {"id": "lost_value", "name": "Lost value (§12.6), a labelled estimate",
     "equation": "r(y) = gap(y) / RB(y) (the whole bill, each line once); quoted (constant elasticity on actual "
                 "demand): L / gap = (1 + r) / (r (1 + e)) x (1 - (1 + r)^-(1 + e)) - 1; straight line: L / gap = "
                 "|e| r / 2; e(y) = s(y) x e_households + (1 - s(y)) x e_others.",
     "code": "gascf.lost_value (price_rise, _ce_actual, _straight, estimate)",
     "set_by": "0080-0085; 0093; card t_6c0411d4 item 5"},
]


def _released_before() -> dict:
    rows = json.loads((ROOT / "releases.yaml").read_text())["releases"]
    (row,) = [r for r in rows if r["version"] == BEFORE]
    raw = (ROOT / row["figures_file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["figures_sha256"]:
        raise ValueError(f"{row['figures_file']}: sha256 does not match releases.yaml")
    return {k: e["value"] for k, e in json.loads(raw)["keys"].items()}


def _before_after(run: dict, this: dict) -> dict:
    old = _released_before()
    rows = []
    for k in HEADLINE_KEYS + BESIDE_GAP_KEYS:
        a, b = old.get(k), this.get(k)
        num = isinstance(a, (int, float)) and isinstance(b, (int, float))
        rows.append({"key": k, "beside_gap": k in BESIDE_GAP_KEYS, "v4_s37": a, "this_release": b,
                     "change": (b - a) if num else (None if a == b else "changed")})
    return {"before": BEFORE, "this_release": run["meta"].get("engine_version"), "rows": rows}


def _change_log(run: dict, this: dict) -> dict:
    reg = json.loads(CHANGE_LOG.read_text())
    steps = [{"order": i + 1, **s} for i, s in enumerate(reg["steps"])]
    measured = [s["headline_change_gbp_bn"] for s in steps if s["headline_change_gbp_bn"] is not None]
    pending = [s["item"] for s in steps if s["headline_change_gbp_bn"] is None]
    total = this.get("headline_2002_24_gbp_bn")
    base = reg["baseline"]["headline_2002_24_gbp_bn"]
    return {"baseline": reg["baseline"], "steps": steps, "sum_of_measured_steps_gbp_bn": sum(measured),
            "pending": pending,
            # what the measured steps leave unexplained; the release card's stop rule ([internal ticket]: > £0.5bn) reads it
            "unexplained_gbp_bn": (None if total is None else total - base - sum(measured))}


def _vat(run: dict) -> list[dict]:
    out = []
    for y in Y02_25:
        b = run["bills"][y]
        nz = {l["id"]: l["national_gbp_m_real"] for l in b["netzero"]}
        go = {l["id"]: l["national_gbp_m_real"] for l in b["gasonly"]}
        bn = lambda v: to_2024(v, run) / 1e3         # noqa: E731
        out.append({"year": int(y), "domestic_share": b["netzero_on_household_bill_per_household"]["domestic_share"],
                    "rate": _vat_rate(), "nz11_gbp_bn": bn(nz["NZ11"]), "go7_gbp_bn": bn(go["GO7"]),
                    "vat_on_extra_gbp_bn": bn(nz["NZ11"] - go["GO7"])})
    return out


def _vat_rate() -> float:
    from gascf import same_in_both
    return same_in_both.domestic_vat_rate()["rate"]


def _carbon(run: dict) -> list[dict]:
    out = []
    for y in Y02_25:
        st = [s for s in run["waterfall"][y] if tuple(s.get("lines") or ()) == ("NZ1c",)][0]
        parts = {p["line"]: p["value_gbp_m_real"] for p in st.get("parts", {}).values()}
        bn = lambda v: to_2024(v, run) / 1e3         # noqa: E731
        out.append({"year": int(y), "carbon_in_price_gbp_bn": bn(run["bills"][y]["nz1c"]["national_gbp_m_real"]),
                    "price_receipts_gbp_bn": bn(parts.get("NZ1c_tax", 0.0)),
                    "rest_in_price_gbp_bn": bn(parts.get("NZ1c_price", 0.0))})
    return out


def _levels_2001(run: dict) -> list[dict] | None:
    otr = run.get("on_the_road")
    if otr is None:
        return None
    out = []
    for y in Y02_25:
        r = otr["years"].get(y)
        if r is None:
            continue
        out.append({"year": int(y), "ffl_line_gbp_bn": r["nz2_on_the_road_gbp_m_2024"] / 1e3,
                    "ffl_vat_gbp_bn": r["nz2_on_the_road_vat_gbp_m_2024"] / 1e3,
                    "eesop_line_gbp_bn": r["nz10_on_the_road_gbp_m_2024"] / 1e3,
                    "eesop_vat_gbp_bn": r["nz10_on_the_road_vat_gbp_m_2024"] / 1e3,
                    "ccl_2001_level_gbp_bn": r["nz8_on_the_road_gbp_m_2024"] / 1e3})
    return out


ANNEX_D = [
    ("household figures (divisor and household share)",
     ["cost_per_household_2002_24_gbp", "cost_per_household_2024_gbp", "own_bills_per_household_2002_24_gbp",
      "own_bills_per_household_2024_gbp"], ["table_household_by_year"]),
    ("VAT on the extra", ["wf_vat_gbp_bn"], ["table_vat_working", "table_waterfall_by_year"]),
    ("carbon split", ["carbon_line_2002_24_gbp_bn", "carbon_price_receipts_2002_24_gbp_bn",
                      "carbon_rest_in_price_2002_24_gbp_bn"], ["table_carbon_split_by_year"]),
    ("2001 levels and their netting", ["pre2002_netting_nz2_2002_19_gbp_bn", "pre2002_netting_nz10_2002_24_gbp_bn",
                                       "ccl_2001_level_netted_2002_24_gbp_bn"], ["table_2001_levels_working"]),
    ("EII shift", ["eii_shift_2018_24_low", "eii_shift_2018_24_high"], ["table_eii_shift_working"]),
    ("lost value (§12.6)", ["lost_value_2002_24_central_gbp_bn", "lost_value_2002_24_low_gbp_bn",
                            "lost_value_2002_24_high_gbp_bn", "lost_value_2025p_central_gbp_bn"],
     ["rb.lost_value.by_year", "lost_value_elasticity_central", "lost_value_straight_line_over_quoted_pct"]),
    ("other gas users (§9.8)", ["npg_estimate_2002_24_central_gbp_bn", "npg_estimate_2002_24_low_gbp_bn",
                                "npg_estimate_2002_24_gross_gbp_bn", "npg_producers_gain_2002_24_gbp_bn",
                                "npg_estimate_2025p_central_gbp_bn"], ["table_npg_working"]),
]


def _parameters(run: dict) -> list[dict]:
    from gascf import capacity
    from gascf import fossil_like_for_like as L
    from gascf import lost_value as lv
    rows = [
        ("gas_feedback_e_central", L.GAS_ELASTICITY["central"], "elasticity", "Albrizio et al. 2022 pair (0.06 + 0.169); 0144"),
        ("gas_feedback_e_high", L.GAS_ELASTICITY["krichene_lr"], "elasticity", "Krichene 2005 Table 2, 0.16 + 0.45; 0144"),
        ("margin_central_pct", 100 * capacity.margin_fraction(run["meta"]["central_settings"]["margin"]), "%",
         "spare margin, central (capacity.margin_fraction)"),
        ("margin_low_pct", 100 * capacity.margin_fraction("low"), "%", "spare margin, low"),
        ("margin_high_pct", 100 * capacity.margin_fraction("high"), "%", "spare margin, high"),
        ("coal_lf_cap_pct", 100 * L.dukes_coal_lf_max()[0], "%", "highest DUKES 5.10.B coal load factor"),
        ("vat_rate_domestic", _vat_rate(), "rate", "HMRC VAT manual VFUP1000: \"reduced to the minimum of 5% with "
                                                   "effect from 1 September 1997\" (same_in_both.domestic_vat_rate)"),
        ("lost_value_e_households", lv.E_HOUSEHOLDS, "elasticity", "Pellini (2021) Table 4 (CR-S018)"),
        ("lost_value_e_others", lv.E_NON_HOUSEHOLDS, "elasticity", "Labandeira et al. (2016) RSCAS 2016/25, Table 3"),
        ("lost_value_e_low", lv.E_LOW, "elasticity", "Labandeira et al. (2016) Table 3, short run"),
        ("lost_value_e_high", lv.E_HIGH, "elasticity", "Labandeira et al. (2016) Table 4"),
    ]
    out = [{"name": n, "value": v, "units": u, "source": s} for n, v, u, s in rows]
    for k, v in sorted(run["meta"]["central_settings"].items()):
        out.append({"name": f"central_settings.{k}", "value": v, "units": "setting",
                    "source": "meta.central_settings (the run's own record)"})
    return out


def values(run: dict) -> dict:
    out = {k: None for k in DECLARED}
    if not all(b in run for b in ("bills", "gap", "waterfall", "meta")):
        return out
    from tools.figures_keys import core, held_rows, lost_value, non_power_gas
    from tools.figures_keys import range as R
    this = {}
    for m in (core, R, lost_value, non_power_gas, held_rows):
        try:
            this |= m.values(run)
        except KeyError:                       # a run without the one-at-a-time block: those rows read None
            pass
    out["annex_e_before_after"] = _before_after(run, this)
    out["annex_e_change_log"] = _change_log(run, this)
    out["table_vat_working"] = _vat(run)
    out["table_carbon_split_by_year"] = _carbon(run)
    out["table_2001_levels_working"] = _levels_2001(run)
    out["annex_d_working_index"] = [{"part": p, "figures": f, "working": w} for p, f, w in ANNEX_D]
    eqs = [dict(e) for e in EQUATIONS]
    npg = non_power_gas.method(run)          # only non_power_gas.py reads that block (test 2 of 0070)
    eqs.append({"id": "other_gas_users", "name": "Other gas users (§9.8), a labelled estimate",
                "equation": npg or "not in this run file", "code": "gascf.non_power_gas",
                "set_by": "0070; 0099; R21 (a) (0163)"})
    out["annex_c_equations"] = eqs
    out["annex_c_parameters"] = _parameters(run)
    return out
