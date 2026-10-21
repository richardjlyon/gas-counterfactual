"""Decision 0117 (Richard Lyon, 19 Oct 2026): the register keys (figures-keys.md, tickets 09, 10, 15, 17, 28, 29) that
only read fields the s36 run already has. Definitions are the register's; where it left a choice of field, the label
says which was read. £ keys in 2024 prices (`gascf.figures.to_2024`); cash fields go to the run's money by CPIH first.

Counts (ticket 29; register "field to confirm"): register stations = distinct station names in the closure register
the run names (`meta.closures_register.path`); kept = distinct station names in any year's `fleet[y].kept_stations`;
margin test passed = distinct stations kept with reason "mixed" (the register's mixed-reason closures, which stay open
in fossil Britain only when the margin test without carbon passes, spec §15.4 item 2)."""
from __future__ import annotations

import json
from pathlib import Path

from gascf import deflator_cpih
from gascf.figures import to_2024

ROOT = Path(__file__).resolve().parents[2]
Y02_24 = [str(y) for y in range(2002, 2025)]
Y16_24 = [str(y) for y in range(2016, 2025)]
BAL_ROW = "balancing (other sourced share / baseline)"
LOW_OPTION = "nao_2005"          # AGENTS.md standing decision 7: the stacked NAO choice with the top share = low end


def _m(label, ticket, units, period, mapped=None, basis="modelled", **extra):
    # mapped_name only where the register gives a second name (other modules read it as a string)
    return {"label": label, "basis": basis, "provisional": period == "2025", "ticket": ticket,
            **({"mapped_name": mapped} if mapped else {}), "units": units, "period": period, "status": "SOURCED",
            "print": True, "decisions": ["0117"], **extra}


DECLARED = {
    "closures_register_stations_count": _m("Stations in the fossil-Britain closure register (distinct station names)",
                                           "29", "count", "2002-2025",
                                           run_field="len(distinct station in meta.closures_register.path)"),
    "closures_kept_count": _m("Stations kept open in fossil Britain in at least one year (distinct station names)",
                              "29", "count", "2002-2025", run_field="distinct fleet[y].kept_stations[*][0]"),
    "closures_margin_test_pass_count": _m("Mixed-reason closures kept open because the margin test without carbon "
                                          "passed (distinct station names)", "29", "count", "2002-2025",
                                          run_field="distinct fleet[y].kept_stations[*][0] with reason 'mixed'"),
    "rb_coal_kept_gw_2024": _m("Reliable Britain's kept coal, 2024, de-rated GW (CM split)", "29", "GW", "2024",
                               run_field="firm_capacity[2024].gasonly_cm_split_gw.kept_coal_gw"),
    "margin_gross_extra_gw_2024": _m("Extra GW from setting the margin on the gross peak (0065), 2024", "15", "GW",
                                     "2024", "rb.fleet.margin_on_gross_extra_gw[2024]",
                                     run_field="fleet[2024].margin_on_gross_extra_gw"),
    "ic_contracted_mw_2024": _m("Interconnectors' CM contracted de-rated MW, calendar 2024 (time-weighted over "
                                "delivery years)", "15", "MW", "2024", "rb.ic.contracted_mw_cy[2024]",
                                run_field="fleet[2024].imports_contracted_gw x 1000"),
    "ic_timeweighted_mw_2019": _m("Interconnectors' CM contracted de-rated MW, calendar 2019, time-weighted over "
                                  "delivery years", "15", "MW", "2019", "rb.ic.contracted_mw_cy[2019]",
                                  run_field="fleet[2019].imports_contracted_gw x 1000"),
    "ic_called_twh_2016_24": _m("Energy Reliable Britain calls from contracted interconnectors, 2016-24 (0 on the "
                                "s36 build: the fleet is dispatched to the metered residual, 0063)", "15", "TWh",
                                "2016-2024", "rb.ic.called_twh_2016_24", run_field="Σ2016-24 fleet[y].ic_called_twh"),
    "ic_called_halfhours_2016_24": _m("Half-hours in which Reliable Britain calls contracted interconnectors, "
                                      "2016-24 (0 on the s36 build, 0063)", "15", "count", "2016-2024", "rb.ic.called_halfhours_2016_24",
                                      run_field="Σ2016-24 fleet[y].ic_called_halfhours"),
    "cm_nuclear_contracted_mw_2024": _m("Nuclear CM contracted de-rated MW, calendar 2024 (0089 variant D)", "17", "MW",
                                        "2024", "rb.cm.nuclear_contracted_mw_cy[2024]",
                                        run_field="capacity_market[2024].split_gw.nuclear_contracted_gw x 1000"),
    "cm_nuclear_effect_2002_24_gbp_bn": _m("NZ5 with the nuclear CM column (0089) less NZ5 with nuclear at peak "
                                           "(v4-s35 rule), 2002-24", "17", "£bn, 2024 prices", "2002-2024",
                                           "rb.cm.nuclear_effect_2002_24_gbp_bn",
                                           run_field="Σ2002-24 release_step_effects.years[y]."
                                                     "cm_nuclear_nz5_change_gbp_m_nominal, CPIH"),
    "nbp_qep_pre2009_effect_2002_24_gbp_bn": _m("Effect on the gap of NBP in place of QEP for balancing gas before "
                                                "October 2009 (B4), as the v4-s35 to s36 difference, 2002-24 (not a "
                                                "QEP run)", "09", "£bn, 2024 prices", "2002-2024",
                                                "rb.b4.nbp_vs_qep_effect_2002_24_gbp_bn",
                                                run_field="Σ2002-24 release_step_effects.years[y]."
                                                          "b4_gap_effect_gbp_m_real",
                                                decisions=["0030", "0072", "0108 item 1.10", "0117"]),
    "f1_effect_2002_24_gbp_bn": _m("Effect on the gap of pricing Reliable Britain's balancing energy at its own "
                                   "feedback-raised gas price (F1), on against off, 2002-24", "10",
                                   "£bn, 2024 prices", "2002-2024", "rb.f1.effect_2002_24_gbp_bn",
                                   run_field="Σ2002-24 release_step_effects.years[y].f1_gap_effect_gbp_m_real"),
    "renewal_allowance_2002_24_gbp_bn": _m("Grid renewal allowance R inside GO5 (GO5 less the carried 2002-05 "
                                           "baseline), 2002-24", "29", "£bn, 2024 prices", "2002-2024",
                                           run_field="Σ2002-24 (GO5 national_gbp_m_nominal - carried_gbp_m), CPIH"),
    "balancing_low_end_2002_24_gbp_bn": _m("Balancing step (NZ6 less GO4) under the low-end balancing option (NAO "
                                           "2005 baseline, top workbook share), 2002-24", "28", "£bn, 2024 prices",
                                           "2002-2024", run_field=f"waterfall NZ6-GO4 less one_at_a_time.ranked"
                                                                  f"[{BAL_ROW}][nao_2005, max share] GO4 move"),
    "balancing_exception_cost_2002_24_gbp_bn": _m("Central gap less the gap under the low-end balancing option (the "
                                                  "cost of the stated exception to the conservative rule), 2002-24",
                                                  "28", "£bn, 2024 prices", "2002-2024",
                                                  run_field="Σ gap[y] - one_at_a_time low-end option gap_real_bn[y]"),
    "balancing_exception_cost_2025p_gbp_bn": _m("The same, 2025 provisional", "28", "£bn, 2024 prices", "2025",
                                                run_field="gap[2025] - low-end option gap_real_bn[2025]"),
    "balancing_low_window_2002_05_gbp_m": _m("Balancing step (NZ6 less GO4) under the low-end option, 2002-05", "28",
                                             "£m, 2024 prices", "2002-2005",
                                             run_field="Σ2002-05 low-end NZ6-GO4"),
}


def _real(v: float, y, run) -> float:
    return deflator_cpih.to_real(v, int(y), int(run["meta"]["price_base"]))


def _counts(run: dict) -> dict:
    reg = run["meta"].get("closures_register") or {}
    rows = json.loads((ROOT / reg["path"]).read_text()) if reg.get("path") else None
    rows = rows if rows is None or isinstance(rows, list) else rows["stations"]
    kept, mixed = set(), set()
    for f in run["fleet"].values():
        for st in f.get("kept_stations") or []:
            kept.add(st[0])
            if st[3] == "mixed":
                mixed.add(st[0])
    return {"closures_register_stations_count": len({r["station"] for r in rows}) if rows is not None else None,
            "closures_kept_count": len(kept), "closures_margin_test_pass_count": len(mixed)}


def _balancing(run: dict) -> dict:
    oat = (run.get("one_at_a_time") or {}).get("ranked", {}).get(BAL_ROW)
    if not oat or "gap" not in run or "waterfall" not in run:
        return {k: None for k in ("balancing_low_end_2002_24_gbp_bn", "balancing_exception_cost_2002_24_gbp_bn",
                                  "balancing_exception_cost_2025p_gbp_bn", "balancing_low_window_2002_05_gbp_m")}
    lows = [o for o in oat if o["settings"].get("bal_option") == LOW_OPTION]
    if not lows:                     # a run (or test fixture) without the balancing options: None, refused at release
        return {k: None for k in ("balancing_low_end_2002_24_gbp_bn", "balancing_exception_cost_2002_24_gbp_bn",
                                  "balancing_exception_cost_2025p_gbp_bn", "balancing_low_window_2002_05_gbp_m")}
    low = max(lows, key=lambda o: o["settings"]["bal_share"])
    tot = {id(o): sum(o["gap_real_bn"][y] for y in Y02_24) for o in oat}
    if min(tot.values()) < tot[id(low)] - 1e-12:
        raise ValueError(f"the stacked {LOW_OPTION} option (top share) is not the lowest 2002-24 gap among the "
                         "balancing options: the low end needs re-ruling")

    def step(y):
        s = [w for w in run["waterfall"][y] if tuple(w.get("lines") or ()) == ("NZ6", "GO4")]
        if len(s) != 1:
            raise KeyError(f"waterfall[{y}]: {len(s)} NZ6-GO4 steps")
        return s[0]["value_gbp_m_real"] - _real(low["lines_moved_gbp_m_nominal"].get(y, {}).get("GO4", 0.0), y, run)

    gap = run["gap"]
    return {"balancing_low_end_2002_24_gbp_bn": to_2024(sum(step(y) for y in Y02_24), run) / 1e3,
            "balancing_exception_cost_2002_24_gbp_bn": to_2024(sum(
                gap[y]["national_gbp_bn_real"] - low["gap_real_bn"][y] for y in Y02_24) * 1e3, run) / 1e3,
            "balancing_exception_cost_2025p_gbp_bn": to_2024(
                (gap["2025"]["national_gbp_bn_real"] - low["gap_real_bn"]["2025"]) * 1e3, run) / 1e3,
            "balancing_low_window_2002_05_gbp_m": to_2024(sum(step(str(y)) for y in range(2002, 2006)), run)}


def values(run: dict) -> dict:
    out = {k: None for k in DECLARED}
    fl = run.get("fleet")
    if fl is None:
        return out
    out |= _counts(run)
    sp = run.get("firm_capacity", {}).get("2024", {}).get("gasonly_cm_split_gw") or {}
    out["rb_coal_kept_gw_2024"] = sp.get("kept_coal_gw")
    out["margin_gross_extra_gw_2024"] = fl["2024"].get("margin_on_gross_extra_gw")
    ic = {y: fl[y].get("imports_contracted_gw") for y in ("2019", "2024")}
    out["ic_contracted_mw_2024"] = ic["2024"] * 1000 if ic["2024"] is not None else None
    out["ic_timeweighted_mw_2019"] = ic["2019"] * 1000 if ic["2019"] is not None else None
    called = [fl[y].get("ic_called_twh") for y in Y16_24]
    out["ic_called_twh_2016_24"] = sum(called) if None not in called else None
    hh = [fl[y].get("ic_called_halfhours") for y in Y16_24]
    out["ic_called_halfhours_2016_24"] = sum(hh) if None not in hh else None
    nc = (run.get("capacity_market", {}).get("2024", {}).get("split_gw") or {}).get("nuclear_contracted_gw")
    out["cm_nuclear_contracted_mw_2024"] = nc * 1000 if nc is not None else None
    rse = (run.get("release_step_effects") or {}).get("years")
    if rse:
        out["nbp_qep_pre2009_effect_2002_24_gbp_bn"] = to_2024(
            sum(rse[y]["b4_gap_effect_gbp_m_real"] for y in Y02_24), run) / 1e3
        out["f1_effect_2002_24_gbp_bn"] = to_2024(sum(rse[y]["f1_gap_effect_gbp_m_real"] for y in Y02_24), run) / 1e3
        out["cm_nuclear_effect_2002_24_gbp_bn"] = to_2024(sum(
            _real(rse[y]["cm_nuclear_nz5_change_gbp_m_nominal"], y, run) for y in Y02_24), run) / 1e3
    go5 = [[x for x in run["bills"][y]["gasonly"] if x["id"] == "GO5"] for y in Y02_24] if "bills" in run else []
    if go5 and all(len(g) == 1 and "carried_gbp_m" in g[0] for g in go5):
        out["renewal_allowance_2002_24_gbp_bn"] = to_2024(sum(
            _real(g[0]["national_gbp_m_nominal"] - g[0]["carried_gbp_m"], y, run) for g, y in zip(go5, Y02_24)),
            run) / 1e3
    out |= _balancing(run)
    return out
