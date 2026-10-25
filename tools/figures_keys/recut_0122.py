"""Decision 0122 (Richard Lyon, 19 Oct 2026: "Yes", to "May the modeller fix these and repackage the release?"), card
item 2 and item 7: the modelled keys and tables the Reliable Britain draft needs that the f82e9f9 cut lacked, read from
the run file only. Money: 2024 prices (CPIH, `gascf.figures.to_2024`) unless a key says otherwise.

- sizing_peak_halfhour_2024 (§7.3): fleet[2024].sizing_peak_halfhour (the fleet-sizing peak; not the §4.3 residual
  peak, ticket 44 R-A1).
- cm_nuclear_suspended_effect_2017_24_gbp_m: NZ5 with variant D (0089, post-trade less suspended agreements) less NZ5
  with the same post-trade column and nothing taken out, 2017-24 (release_step_effects, one more build).
- table_exceptions_register (§2, glossary "Exceptions register": the central choices that are not the gap-lowering
  option, with their size): every ranked (range) switch with an option below central, mechanically, lowest first.
  Which of them the paper argues as exceptions is the writer's and Richard's; this is the measured list.
- table_calibration (§5.1): the early-years check (0061, 0111) and the residual-demand calibration rows.
- table_household_by_year (§14.3): households, the extra cost of net zero on electricity bills per household and the part on households' own
  bills, by year.
- annex_b_annual_tables: every bill line, every year 2002-25 (the 2024 table's layout, plus the same-in-both lines).
- annex_c_engine_summary: the run's own record of how it was built (settings, sources, fallbacks with their size).
- (annex_e_bridge, the old Annex E bridge to the prior release, is cut by decision 0162; the new Annex E, the version
  and change log, and Annex C's equations and parameters are tools/figures_keys/annex_v11.py.)
- release_version, release_commit: the release name and the commit the cut ran at (the run's suite record).

Annex A (the figure register) is written by tools.figures over the whole file. Annex D's workings are keyed in this
module, the per-item modules and annex_v11 (annex_d_working_index lists them)."""
from __future__ import annotations

import json
from pathlib import Path

from gascf import deflator_cpih
from gascf.figures import PRICE_BASE_LABEL, to_2024

ROOT = Path(__file__).resolve().parents[2]

Y02_24 = [str(y) for y in range(2002, 2025)]
Y02_25 = Y02_24 + ["2025"]
Y17_24 = [str(y) for y in range(2017, 2025)]
TICKET = "0122"


def _m(label, run_field, units, period, basis="modelled", **extra):
    return {"label": label, "basis": basis, "provisional": False, "ticket": TICKET, "run_field": run_field,
            "units": units, "period": period, "status": "SOURCED", "print": True, "decisions": ["0122"], **extra}


_P = {"price_base": PRICE_BASE_LABEL}

DECLARED = {
    "sizing_peak_halfhour_2024": _m("Half-hour at which Reliable Britain's fleet is sized, 2024 (gross demand peak, "
                                    "contracted interconnector basis); not the §4.3 residual peak",
                                    "fleet[2024].sizing_peak_halfhour", "text (date and settlement period)", "2024",
                                    basis="measured"),
    "cm_nuclear_suspended_effect_2017_24_gbp_m": _m(
        "Effect on NZ5 of taking out the nuclear CM agreements the NESO register flags suspended (0089 variant D, "
        "against the same post-trade column with none taken out), 2017-24; positive = more cost of net zero",
        "Σ2017-24 release_step_effects.years[y].cm_nuclear_suspended_nz5_change_gbp_m_nominal, CPIH to 2024 £",
        "£m, 2024 prices", "2017-2024", signed=True, **_P),
    "table_exceptions_register": _m(
        "Exceptions register (glossary, §2): every range switch with an option that gives a lower 2002-24 headline "
        "than central, with the lowest such option and its change; lowest first. Mechanical list: which of these the "
        "paper argues as exceptions is not decided here",
        "table_one_at_a_time ranked rows with change_gbp_bn < 0, lowest option per switch",
        "table, £bn, 2024 prices", "2002-2024", basis="modelled", **_P),
    "table_calibration": _m(
        "Calibration (§5.1): the early-years check pooled over 2002-04 (0061; failure disclosed under 0111) and the "
        "residual-demand calibration of FUELHH against NESO by year (loosened rule)",
        "tests.calibration_early; tests.calibration.loosened", "table, £ a household (2025 prices) and %",
        "2002-2025", money="2025 prices (the calib_* keys' money)"),
    "table_household_by_year": _m(
        "Households, the extra cost of net zero on electricity bills per household, and the net-zero cost on households' own bills (CCL "
        "excluded, 0025), by year 2002-25 (2025 provisional)",
        "years[y].households; gap[y].per_household_real; bills[y].netzero_on_household_bill_per_household",
        "table, million households, £ a household, 2024 prices, %", "2002-2025", basis="modelled", **_P),
    "annex_b_annual_tables": _m(
        "Annex B: every bill line, every year 2002-25 (2025 provisional): net-zero Britain, Reliable Britain and the "
        "same-in-both lines; 'of which' rows are shown, never added; each line tagged measured, modelled or labelled "
        "estimate and given its cash figure (£m, that year's money) beside 2024 prices; each year's data basis (v1.1 "
        "F1, F2)",
        "bills[y].netzero, .gasonly, .same_in_both, .nz1c; waterfall[y] step 2 parts", "table, £bn, 2024 prices",
        "2002-2025", basis="modelled", **_P),
    "annex_c_engine_summary": _m(
        "Annex C: engine summary, the run's own record (version, run date, money, households source, central "
        "settings, residual method, calibration rule, provisional years, every declared fallback with its size)",
        "meta.*", "record", "release", basis="measured"),
    # Decision 0162 item 1 (Richard Lyon, 21 Oct 2026: "Yep, cut annex E."): annex_e_bridge is cut. The new Annex E
    # (Version and change log) is tools/figures_keys/annex_v11.py.
    "release_version": _m("Release name", "meta.engine_version", "text", "release", basis="measured"),
    "household_share_gb_2024_pct": _m(
        "Domestic meters' share of Great Britain's electricity consumption, 2024 (DESNZ sub-national statistics, GB "
        "incl. unallocated), %; context only", "data/raw/desnz_subnational (sheet 2024, row K03000001)", "%", "2024",
        basis="measured", context_only=True, headline=False,
        note="A GB figure on a meter basis (domestic meters / all meters). The engine's household share (36.5%, "
             "household_share_2024_pct) is UK supplier sales (DUKES 5.2 / 5.5.D) and stays the basis of the own-bill "
             "line unless Richard rules otherwise."),
    "release_commit": _m("Commit the release was cut at (its code and suite); the tag names the commit that adds "
                         "the release files to it and changes no code", "meta.test_suite.commit", "git commit",
                         "release", basis="measured"),
}


def _real(v: float, y, run) -> float:
    return deflator_cpih.to_real(v, int(y), int(run["meta"]["price_base"]))


def _exceptions(run: dict) -> list[dict] | None:
    if "one_at_a_time" not in run:
        return None
    from tools.figures_keys import range as R
    settings = run["meta"]["central_settings"]
    below: dict = {}
    for r in R.table(run):
        if r["block"] == "ranked" and r["change_gbp_bn"] < -1e-9:
            below.setdefault(r["switch"], []).append(r)
    rows = []
    for sw, opts in below.items():
        low = min(opts, key=lambda r: r["change_gbp_bn"])
        rows.append({"switch": sw, "choice": low["choice"],
                     "central_setting": {k: settings.get(k) for k in low["settings"]},
                     "lowest_option": low["option"], "lowest_option_plain": low["plain_option"],
                     "lowest_option_settings": low["settings"],
                     "headline_2002_24_gbp_bn": low["headline_2002_24_gbp_bn"],
                     "change_gbp_bn": low["change_gbp_bn"]})
    return sorted(rows, key=lambda r: r["change_gbp_bn"])


def _calibration(run: dict) -> dict | None:
    t = run.get("tests") or {}
    ce, cal = t.get("calibration_early"), t.get("calibration")
    if not ce or not cal:
        return None
    rows = [{"year": r["year"], "diff_gbp_hh": r["diff_hh"], "lines_gbp_hh": r["lines_hh"], "pct": r["pct"],
             "passed_gbp": r["pass_gbp"], "passed_pct": r["pass_pct"]} for r in ce["per_year"]]
    p = ce["pooled"]
    rows.append({"year": "2002-04 pooled", "diff_gbp_hh": p["diff_hh"], "lines_gbp_hh": p["lines_hh"],
                 "pct": p["pct"], "passed_gbp": p["pass_gbp"], "passed_pct": p["pass_pct"]})
    return {"early_years": rows, "passed": ce["passed"], "limit_pct": ce["limit_pct"],
            "limit_gbp_hh": ce["limit_gbp_hh"], "money": ce["money"], "decision": ce["decision"],
            "disclosed_failure": ce["disclosed_failure"], "note": ce["note"],
            "residual_demand_rule": cal.get("rule"),
            "residual_demand": [dict(r) for r in cal[cal.get("rule", "loosened")]],
            "pre2016_publishable": cal.get("pre2016_publishable")}


def _households(run: dict) -> list[dict]:
    hh = {r["year"]: r["households"] for r in run["years"]}
    prov = [str(p) for p in run["meta"]["provisional_years"]]
    out = []
    for y in Y02_25:
        own = run["bills"][y]["netzero_on_household_bill_per_household"]
        out.append({"year": int(y), "provisional": y in prov, "households_m": hh[int(y)] / 1e6,
                    "cost_per_household_gbp": to_2024(run["gap"][y]["per_household_real"], run),
                    "own_bill_per_household_gbp": to_2024(own["value"], run),
                    "domestic_share_pct": 100 * own["domestic_share"]})
    return out


# v1.1 F1 (0160; W2, R23 (a)): each Annex B line's tag is the engine's own data basis for that line and year (the
# weakest evidence among its inputs, bills._RANK). "estimated" prints as "labelled estimate" (0007); the 2004-06
# metering rows, which have no figure of their own, as "no separate figure".
TAG = {"measured": "measured", "modelled": "modelled", "estimated": "labelled estimate",
       "UNSOURCED": "no separate figure"}


def _line_facts(run: dict, y: str) -> dict:
    """{line id: (engine basis, cash £m in year y's money)} for every Annex B row of year y."""
    b = run["bills"][y]
    facts = {x["id"]: (x["basis"], x.get("national_gbp_m_nominal"))
             for x in b["netzero"] + b["gasonly"] + b["same_in_both"]}
    facts["NZ1c"] = (b["nz1c"]["basis"], b["nz1c"]["national_gbp_m_nominal"])
    step2 = [s for s in run["waterfall"][y] if tuple(s.get("lines") or ()) == ("NZ1c",)][0]
    for p in step2.get("parts", {}).values():
        facts[p["line"]] = (p["basis"], p["value_gbp_m_nominal"])
    return facts


def _annex_b(run: dict) -> list[dict]:
    from tools.figures_keys.core import _lines_table
    prov = [str(p) for p in run["meta"]["provisional_years"]]
    years = {str(r["year"]): r for r in run["years"]}
    out = []
    for y in Y02_25:
        rows = _lines_table(run, y)
        rows += [{"id": x["id"], "label": x["label"], "bill": "same_in_both", "of_which": None, "added": True,
                  "value": (to_2024(x["national_gbp_m_real"], run) / 1e3
                            if x.get("national_gbp_m_real") is not None else None),
                  # 2004-06 metering has no separate figure (the run's own note says where it sits): no value, a note
                  "note": x.get("years_note") if x.get("national_gbp_m_real") is None else None}
                 for x in run["bills"][y]["same_in_both"]]
        facts = _line_facts(run, y)
        for r in rows:                                   # F1 tag and F2 cash column (£m, that year's money)
            basis, cash = facts[r["id"]]
            r["tag"] = TAG[basis]
            r["cash_gbp_m"] = cash if r.get("value") is not None else None
        by_tag: dict = {}
        for r in rows:
            by_tag.setdefault(r["tag"], []).append(r["id"])
        out.append({"year": int(y), "provisional": y in prov,
                    # F2: the year's data basis
                    "data_basis": {"status": "provisional" if y in prov else "outturn",
                                   "volume_basis": years[y]["volume_basis"],
                                   "wholesale_basis": years[y]["wholesale_basis"],
                                   "lines_by_tag": by_tag},
                    "rows": [{k: v for k, v in r.items() if v is not None} for r in rows]})
    return out


SUMMARY_FIELDS = ("engine_version", "schema_version", "run_date", "headline_year", "latest_full_year",
                  "provisional_years", "deflator", "households_source", "counterfactual", "central_settings",
                  "residual_method", "calibration_rule", "pre2016_publishable", "fallbacks")


def _annex_c(run: dict) -> dict:
    m = run["meta"]
    return {**{f: m.get(f) for f in SUMMARY_FIELDS if m.get(f) is not None}, "run_price_base": m.get("price_base"),
            "figures_price_base": PRICE_BASE_LABEL, "input_checksums_count": len(m.get("input_checksums") or {})}


def _gb_household_share_2024() -> float:
    import openpyxl
    from pathlib import Path
    p = (Path(__file__).resolve().parents[2]
         / "data/raw/desnz_subnational/s18c-Subnational_electricity_consumption_statistics_2005-2024.xlsx")
    ws = openpyxl.load_workbook(p, read_only=True, data_only=True)["2024"]
    rows = list(ws.iter_rows(values_only=True))
    h = next(r for r in rows if r and r[0] == "Code")
    gb = [r for r in rows if r and r[0] == "K03000001"]
    if len(gb) != 1 or "Great Britain" not in str(gb[0][1]):
        raise ValueError("sub-national 2024: no single Great Britain row")
    col = {str(c).replace("\n", " "): i for i, c in enumerate(h) if c}
    dom = gb[0][col["Total consumption (GWh): All Domestic"]]
    tot = gb[0][col["Total consumption (GWh): All meters"]]
    return 100 * dom / tot


def values(run: dict) -> dict:
    out = {k: None for k in DECLARED}
    m = run["meta"]
    out["household_share_gb_2024_pct"] = _gb_household_share_2024()
    out["release_version"] = m.get("engine_version")
    out["release_commit"] = (m.get("test_suite") or {}).get("commit")
    if "fleet" in run:
        out["sizing_peak_halfhour_2024"] = run["fleet"]["2024"].get("sizing_peak_halfhour")
    rse = (run.get("release_step_effects") or {}).get("years") or {}
    if rse and all("cm_nuclear_suspended_nz5_change_gbp_m_nominal" in rse[y] for y in Y17_24):
        out["cm_nuclear_suspended_effect_2017_24_gbp_m"] = to_2024(sum(
            _real(rse[y]["cm_nuclear_suspended_nz5_change_gbp_m_nominal"], y, run) for y in Y17_24), run)
    out["table_exceptions_register"] = _exceptions(run)
    out["table_calibration"] = _calibration(run)
    if "bills" in run and "gap" in run:
        out["table_household_by_year"] = _households(run)
        if "waterfall" in run:
            out["annex_b_annual_tables"] = _annex_b(run)
    out["annex_c_engine_summary"] = _annex_c(run)
    return out
