"""Ticket 44 (key half): fleet keys for §7.2 and §7.4, read from the run file's `fleet` block.

The engine sizes new plant afresh each year (no vintages), so the 2024 keys are the plant standing in 2024,
not a cumulative build (Q-KEYS-5, 17 Oct 2026).
"""
from __future__ import annotations


def _m(label, run_field, units, basis="modelled", **extra):
    return {"label": label, "basis": basis, "provisional": True, "ticket": "44", "run_field": run_field,
            "units": units, "status": "PENDING", "print": True, **extra}


Y02_24 = [str(y) for y in range(2002, 2025)]
EPS = 1e-9

DECLARED = {
    "rb.s7.new_ccgt_built_by_2024": _m(
        "Whether Reliable Britain's fleet has any new CCGT standing in any year 2002-24 (the engine sizes new "
        "plant afresh each year, no vintages); metadata lists the years and the same check on new coal",
        "any(fleet[y].ccgt_gw > 1e-9, 2002-24)", "boolean", period="2002-24",
        years_with_new_ccgt=None, new_coal_built_by_2024=None, years_with_new_coal=None),
    "rb.s7.new_build_mix_gw_2024": _m(
        "New plant standing in Reliable Britain's fleet in 2024, by type, GW nameplate: the engine sizes new plant "
        "afresh each year (no vintages), so this is the plant standing in 2024, not a cumulative build; printed "
        "at the new-build-sized total without the margin spare (Q-KEYS-5)",
        "fleet[2024]: ccgt_gw, ocgt_gw, new_coal_gw, spare_gw - firm_extra_gw, firm_extra_gw, new_gw",
        "table, GW nameplate (not de-rated)", period="2024"),
    "annex.s7.margin_spare_ocgt_gw_2024": _m("Margin (firm) spare OCGT standing in 2024, outside the printed "
                                             "new-build total (Q-KEYS-5)", "fleet[2024].firm_extra_gw",
                                             "GW nameplate", period="2024"),
    # E1 (Editor-in-chief, 17 Oct 2026): a bare number; the unit lives here only, the draft prints "MW" itself.
    "ic_peak_dy_contracted_mw_2019": _m(
        "Contracted interconnector capacity in the delivery year in force at the 2019 sizing-peak half-hour "
        "({{ic_peak_dy_2019}}), printed for information only (0066); sizing uses the calendar-year value",
        "fleet[2019].ic_peak_dy_contracted_mw", "MW", period="2019", value_form="bare number (E1)"),
    "ic_peak_dy_2019": _m("Delivery-year label in force at the 2019 sizing-peak half-hour "
                          "(\"2018/19\" if January to September, \"2019/20\" if October to December)",
                          "fleet[2019].ic_peak_dy", "text", period="2019"),
}


def values(run: dict) -> dict:
    fl = run["fleet"]
    ccgt = [y for y in Y02_24 if fl[y]["ccgt_gw"] > EPS]
    coal = [y for y in Y02_24 if fl[y]["new_coal_gw"] > EPS]
    DECLARED["rb.s7.new_ccgt_built_by_2024"].update(years_with_new_ccgt=ccgt, new_coal_built_by_2024=bool(coal),
                                                    years_with_new_coal=coal)
    f19 = run["fleet"]["2019"]
    mw = f19.get("ic_peak_dy_contracted_mw")
    f = fl["2024"]
    mix = {"ccgt": f["ccgt_gw"], "ocgt": f["ocgt_gw"], "coal": f["new_coal_gw"],
           "ocgt_block_spare": f["spare_gw"] - f["firm_extra_gw"], "ocgt_firm_spare": f["firm_extra_gw"]}
    neg = [n for n, v in mix.items() if v < -EPS]
    if neg:
        raise ValueError(f"fleet[2024] new-build rows negative: {neg}")
    mix |= {"total_ex_firm_spare": f["new_gw"], "total": sum(mix.values()), "printed_total": "total_ex_firm_spare"}
    if abs(mix["total"] - mix["ocgt_firm_spare"] - f["new_gw"]) > 1e-9:
        raise ValueError("fleet[2024]: rows less the firm spare do not equal new_gw")
    return {"rb.s7.new_ccgt_built_by_2024": bool(ccgt), "rb.s7.new_build_mix_gw_2024": mix,
            "annex.s7.margin_spare_ocgt_gw_2024": f["firm_extra_gw"],
            "ic_peak_dy_contracted_mw_2019": None if mw is None else float(mw),
            "ic_peak_dy_2019": f19.get("ic_peak_dy")}
