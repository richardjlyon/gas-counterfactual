"""Ticket 29: headline, bills, waterfall and per-household keys (figures-keys.md §1, the "29" rows).

Keys are the Report writer's placeholder names; the figures-keys.md name, where it differs, is in
`meta.mapped_name`. Every £ key is converted from the run's money to 2024 prices by
`gascf.figures.to_2024`. `Σ2002-24` never includes 2025 (0035, 0093)."""
from __future__ import annotations

from gascf import capacity, deflator_cpih
from gascf import fossil_like_for_like as lfl
from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_24 = [str(y) for y in range(2002, 2025)]
Y02_05 = ["2002", "2003", "2004", "2005"]
Y05_12 = [str(y) for y in range(2005, 2013)]
Y13_20 = [str(y) for y in range(2013, 2021)]


def _m(label, run_field, units="£bn, 2024 prices", basis="estimated", period="2002-2024", provisional=False,
       **extra):
    return {"label": label, "basis": basis, "provisional": provisional, "ticket": "29",
            "run_field": run_field, "units": units, "period": period, "price_base": PRICE_BASE_LABEL,
            "status": "SOURCED", "print": True, **extra}


# The 11 printed waterfall rows (step 3 split into RO, FiT, CfD). Each row is found by the bill lines
# its step moves, never by group name (groups are renamed in 37) and never from `waterfall_grouped`
# or `netzero_groups`. Rows read from a waterfall step are (step lines); the subsidy split reads
# the net-zero bill lines themselves.
WF_STEPS = {
    "wf_power_before_carbon_gbp_bn": ("Power, before carbon", ("NZ1", "NZ1c", "GO1", "GO1k")),
    "wf_carbon_gbp_bn": ("Carbon in the power price (NZ1c)", ("NZ1c",)),
    "wf_cm_gbp_bn": ("Backup (Capacity Market extra, NZ5)", ("NZ5",)),
    "wf_balancing_gbp_bn": ("Running the grid (NZ6 less GO4)", ("NZ6", "GO4")),
    "wf_grid_gbp_bn": ("High-voltage grid (NZ7 less GO5)", ("NZ7", "GO5")),
    "wf_ccl_extra_gbp_bn": ("Climate Change Levy, electricity (NZ8)", ("NZ8",)),
    "wf_schemes_gbp_bn": ("Energy-saving schemes (NZ10)", ("NZ10",)),
    "wf_vat_gbp_bn": ("VAT on households' share of the extra (NZ11 less GO7)", ("NZ11", "GO7")),
}
WF_LINES = {
    "wf_ro_gbp_bn": ("Renewables Obligation (NZ2)", ("NZ2",)),
    "wf_fit_gbp_bn": ("Feed-in Tariffs (NZ3)", ("NZ3",)),
    "wf_cfd_gbp_bn": ("Contracts for Difference (NZ4 + NZ4b)", ("NZ4", "NZ4b")),
}
WF_ORDER = ["wf_power_before_carbon_gbp_bn", "wf_carbon_gbp_bn", "wf_ro_gbp_bn", "wf_fit_gbp_bn", "wf_cfd_gbp_bn",
            "wf_cm_gbp_bn", "wf_balancing_gbp_bn", "wf_grid_gbp_bn", "wf_ccl_extra_gbp_bn", "wf_schemes_gbp_bn",
            "wf_vat_gbp_bn"]


def _step_m(y: str, run: dict, lines: tuple) -> float:
    hits = [s for s in run["waterfall"][y] if tuple(s.get("lines") or ()) == lines]
    if len(hits) != 1:
        raise KeyError(f"waterfall[{y}]: {len(hits)} steps with lines {list(lines)}")
    return hits[0]["value_gbp_m_real"]


def _line_m(y: str, run: dict, ident: str) -> float:
    b = run["bills"][y]
    hits = [x for x in b["netzero"] + b["gasonly"] if x["id"] == ident]
    if len(hits) != 1:
        raise KeyError(f"bills[{y}]: {len(hits)} lines {ident}")
    return hits[0]["national_gbp_m_real"]


def _nz1c_part_m(y: str, run: dict, line_id: str) -> float:
    """NZ1c_tax or NZ1c_price real £m for year y, from the waterfall step-2 carbon split parts (37, 0090)."""
    step2 = [s for s in run["waterfall"][y] if tuple(s.get("lines") or ()) == ("NZ1c",)]
    if len(step2) != 1:
        raise KeyError(f"waterfall[{y}]: {len(step2)} NZ1c steps")
    hits = [p["value_gbp_m_real"] for p in step2[0].get("parts", {}).values() if p["line"] == line_id]
    if len(hits) != 1:
        raise KeyError(f"waterfall[{y}] step2: {len(hits)} {line_id} parts")
    return hits[0]


def _bn(run: dict, gbp_m: float) -> float:
    return to_2024(gbp_m, run) / 1e3


def _nominal_bn(run: dict, field: str) -> float:
    """Σ2002-24 of a fleet £m field in each year's money (fleet[y] is nominal), → 2024 £bn."""
    base = int(run["meta"]["price_base"])
    return to_2024(sum(deflator_cpih.to_real(run["fleet"][y][field], int(y), base) for y in Y02_24), run) / 1e3


def _gbp(units="£ per household, 2024 prices", **kw):
    return dict(units=units, **kw)


# (label, run field, extra meta) for the scalar "29" rows; values in `values`.
_PROV = dict(provisional=True, period="2025")
_Y24 = dict(period="2024")
SCALARS = {
    "nz_bill_2002_24_gbp_bn": ("Net-zero Britain's bill, 2002-24", "Σ2002-24 bills[y].totals.nz_real", {}),
    "rb_bill_2002_24_gbp_bn": ("Reliable Britain's bill, 2002-24", "Σ2002-24 bills[y].totals.go_real", {}),
    "gap_2025p_gbp_bn": ("Extra cost of net zero, 2025 (provisional)", "gap[2025].national_gbp_bn_real", _PROV),
    "gap_2024_gbp_bn": ("Extra cost of net zero, 2024", "gap[2024].national_gbp_bn_real", _Y24),
    "gap_2022_gbp_bn": ("Extra cost of net zero, 2022", "gap[2022].national_gbp_bn_real", dict(period="2022")),
    "nz_bill_2024_gbp_bn": ("Net-zero Britain's bill, 2024", "bills[2024].totals.nz_real", _Y24),
    "rb_bill_2024_gbp_bn": ("Reliable Britain's bill, 2024", "bills[2024].totals.go_real", _Y24),
    "nz_bill_2025p_gbp_bn": ("Net-zero Britain's bill, 2025 (provisional)", "bills[2025].totals.nz_real", _PROV),
    "rb_bill_2025p_gbp_bn": ("Reliable Britain's bill, 2025 (provisional)", "bills[2025].totals.go_real", _PROV),
    "s1_same_in_both_2024_gbp_bn": ("Same in both bills, 2024", "Σ bills[2024].same_in_both[].national_gbp_m_real", _Y24),
    "firm_capacity_rb_gw_2024": ("Reliable Britain's firm capacity, 2024", "firm_capacity[2024].gasonly_gw",
                                 dict(units="GW", **_Y24)),
    "firm_capacity_nz_gw_2024": ("Net-zero Britain's firm capacity, 2024", "firm_capacity[2024].netzero_gw",
                                 dict(units="GW", basis="measured", **_Y24)),
    "grid_window_2002_05_gbp_m": ("Grid line (NZ7 less GO5), 2002-05", "Σ2002-05 NZ7 − GO5",
                                  dict(units="£m, 2024 prices", period="2002-2005")),
    "balancing_window_2002_05_gbp_m": ("Balancing line (NZ6 less GO4), 2002-05", "Σ2002-05 NZ6 − GO4",
                                       dict(units="£m, 2024 prices", period="2002-2005")),
    "nz5_2002_24_gbp_bn": ("Capacity Market line NZ5, 2002-24", "Σ2002-24 NZ5", dict(basis="modelled")),
    "nz6_2002_24_gbp_bn": ("Balancing line NZ6, 2002-24", "Σ2002-24 NZ6", {}),
    "go4_2002_24_gbp_bn": ("Reliable Britain's balancing GO4, 2002-24", "Σ2002-24 GO4", {}),
    "nz7_2002_24_gbp_bn": ("High-voltage grid line NZ7, 2002-24", "Σ2002-24 NZ7", {}),
    "go5_2002_24_gbp_bn": ("Reliable Britain's grid GO5, 2002-24", "Σ2002-24 GO5", {}),
    "nz10_2002_24_gbp_bn": ("Energy-saving schemes NZ10 as netted in the run, 2002-24", "Σ2002-24 NZ10", {}),
    "grid_line_2002_24_gbp_bn": ("Grid line (NZ7 less GO5), 2002-24", "Σ2002-24 NZ7 − GO5", {}),
    "balancing_line_2002_24_gbp_bn": ("Balancing line (NZ6 less GO4), 2002-24", "Σ2002-24 NZ6 − GO4", {}),
    "moe_uplift_2002_24_gbp_bn": ("Merit-order uplift, 2002-24", "Σ2002-24 fleet[y].moe_gbp_m + moe_kept_gbp_m (cash → 2024 £)",
                                  dict(basis="modelled")),
    "years_shao_larger_count": ("Years 2002-24 in which Shao's uplift exceeds the model's",
                                "count fleet[y].moe.shao_mean_gbp_mwh > model_mean_gbp_mwh, 2002-24",
                                dict(units="years (of 23)", basis="modelled")),
    "gas_price_rise_2024_pct": ("Gas-price rise from Reliable Britain's extra gas burn, 2024",
                                "answers.gas_break_even[2024].price_rise_frac_central × 100",
                                dict(units="%", basis="modelled", **_Y24)),
    "rb_extra_gas_twh_2024": ("Reliable Britain's extra gas burn, 2024", "answers.gas_break_even[2024].dq_twh",
                              dict(units="TWh", basis="modelled", **_Y24)),
    "break_even_gas_rise_2024_pct": ("Gas-price rise at which the 2024 gap is zero",
                                     "answers.gas_break_even[2024] break_even / actual − 1, × 100",
                                     dict(units="%", basis="modelled", **_Y24)),
    "plant_cost_edition_2024": ("Plant cost edition in force, 2024", "fleet[2024].cost_edition",
                                dict(units="text", basis="measured", **_Y24)),
    "rb_new_build_gw_2024": ("New plant standing in Reliable Britain's fleet, 2024, without the margin spare (Q-KEYS-5)",
                             "fleet[2024].new_gw", dict(units="GW, nameplate", basis="modelled", **_Y24)),
    "negative_gap_years": ("Years 2002-24 with a negative gap", "[y for y in 2002-24 if gap[y] < 0]",
                           dict(units="years")),
    "cost_per_household_2002_24_gbp": ("Cost to Britain per household, summed 2002-24",
                                       "Σ2002-24 gap[y].per_household_real", _gbp()),
    "cost_per_household_2024_gbp": ("Cost to Britain per household, 2024", "gap[2024].per_household_real",
                                    _gbp(**_Y24)),
    "cost_per_household_2025p_gbp": ("Cost to Britain per household, 2025 (provisional)",
                                     "gap[2025].per_household_real", _gbp(**_PROV)),
    "own_bills_per_household_2002_24_gbp": ("Net-zero cost on households' own bills, summed 2002-24 (CCL excluded, 0025)",
                                            "Σ2002-24 bills[y].netzero_on_household_bill_per_household.value",
                                            _gbp(basis="modelled")),
    "own_bills_per_household_2024_gbp": ("Net-zero cost on households' own bills, 2024",
                                         "bills[2024].netzero_on_household_bill_per_household.value",
                                         _gbp(basis="modelled", **_Y24)),
    "own_bills_per_household_2025p_gbp": ("Net-zero cost on households' own bills, 2025 (provisional)",
                                          "bills[2025].netzero_on_household_bill_per_household.value",
                                          _gbp(basis="modelled", **_PROV)),
    "margin_central_pct": ("Spare margin, central", "capacity.margin_fraction('central') × 100 (meta.central_settings.margin)",
                           dict(units="%", basis="measured", period="parameter")),
    "margin_low_pct": ("Spare margin, low", "capacity.margin_fraction('low') × 100",
                       dict(units="%", basis="measured", period="parameter")),
    "margin_high_pct": ("Spare margin, high", "capacity.margin_fraction('high') × 100",
                        dict(units="%", basis="measured", period="parameter")),
    "coal_lf_cap_pct": ("Coal load-factor cap: highest DUKES 5.10.B coal load factor", "fossil_like_for_like.dukes_coal_lf_max()",
                        dict(units="%", basis="measured", period="parameter")),
}


OF_WHICH = {"GO2": "GO1"}     # "Backup payments (inside GO1)": shown, never added


def _lines_table(run: dict, y: str) -> list[dict]:
    """Rows carry no engine group or tag (groups are renamed and split in 37; 0090)."""
    b = run["bills"][y]
    row = lambda x, bill: {"id": x["id"], "label": x["label"], "bill": bill,  # noqa: E731
                           "of_which": OF_WHICH.get(x["id"]), "added": x["id"] not in OF_WHICH,
                           "value": _bn(run, x["national_gbp_m_real"])}
    rows = [row(x, "net_zero_britain") for x in b["netzero"]]
    nz1c = b["nz1c"]
    rows.append({"id": "NZ1c", "label": "of which carbon in the wholesale price", "bill": "net_zero_britain",
                 "of_which": "NZ1", "added": False, "value": _bn(run, nz1c["national_gbp_m_real"])})
    step2 = [s for s in run["waterfall"][y] if tuple(s.get("lines") or ()) == ("NZ1c",)][0]
    for part in step2.get("parts", {}).values():
        lab = {"NZ1c_tax": "of which carbon price receipts", "NZ1c_price": "of which carbon in the price, the rest"}
        rows.append({"id": part["line"], "label": lab[part["line"]], "bill": "net_zero_britain",
                     "of_which": "NZ1", "added": False, "value": _bn(run, part["value_gbp_m_real"])})
    rows += [row(x, "reliable_britain") for x in b["gasonly"]]
    return rows


DECLARED = {
    "headline_2002_24_gbp_bn": _m("Extra cost of net zero on electricity bills, paid by bill-payers, 2002-24 (0144 item 5b)",
                                  "Σ2002-24 gap[y].national_gbp_bn_real",
                                  mapped_name="gap_to_2024"),
    "gap_2002_25": _m("Gap summed 2002-25 (build check only; 0098: no 2002-25 total printed)",
                      "Σ2002-25 gap[y].national_gbp_bn_real", period="2002-2025", provisional=True,
                      print=False),
    "carbon_line_2002_24_gbp_bn": _m("Carbon in the power price (NZ1c only), 2002-24; excludes the CCL at its main rates",
                                     "Σ2002-24 bills[y].nz1c.national_gbp_m_real", basis="modelled", lines=["NZ1c"]),
    "carbon_price_receipts_2002_24_gbp_bn": _m(
        "Carbon prices collected as tax on power (NZ1c_tax: CPS + carbon auctions on power), 2002-24; excludes the CCL at its main rates",
        "Σ2002-24 waterfall[y] step-2 part NZ1c_tax, value_gbp_m_real", ticket="37", basis="modelled", lines=["NZ1c_tax"]),
    "carbon_price_receipts_2005_12_gbp_bn": _m(
        "Carbon prices collected as tax on power (NZ1c_tax), 2005-12; excludes the CCL at its main rates",
        "Σ2005-12 waterfall[y] step-2 part NZ1c_tax, value_gbp_m_real", ticket="37", basis="modelled",
        period="2005-2012", lines=["NZ1c_tax"]),
    "carbon_price_receipts_2013_20_gbp_bn": _m(
        "Carbon prices collected as tax on power (NZ1c_tax), 2013-20; excludes the CCL at its main rates",
        "Σ2013-20 waterfall[y] step-2 part NZ1c_tax, value_gbp_m_real", ticket="37", basis="modelled",
        period="2013-2020", lines=["NZ1c_tax"]),
    "carbon_rest_in_price_2002_24_gbp_bn": _m(
        "Carbon in the power price not collected as UK carbon tax (the rest) (NZ1c_price; 0144 item 5a), 2002-24; excludes "
        "the CCL at its main rates",
        "Σ2002-24 waterfall[y] step-2 part NZ1c_price, value_gbp_m_real", ticket="37", basis="modelled",
        lines=["NZ1c_price"]),
    "carbon_in_price_2005_12_gbp_bn": _m(
        "Carbon in the power price (NZ1c, tax plus price), 2005-12; excludes the CCL at its main rates",
        "Σ2005-12 bills[y].nz1c.national_gbp_m_real", ticket="37", basis="modelled", period="2005-2012", lines=["NZ1c"]),
    **{k: _m(lab, f"Σ2002-24 waterfall[y] step with lines {list(ls)}, value_gbp_m_real", lines=list(ls))
       for k, (lab, ls) in WF_STEPS.items()},
    **{k: _m(lab, f"Σ2002-24 bills[y] lines {list(ls)}, national_gbp_m_real", lines=list(ls))
       for k, (lab, ls) in WF_LINES.items()},
    **{k: _m(lab, rf, **ex) for k, (lab, rf, ex) in SCALARS.items()},
    "table_lines_2024": _m("Bill lines, 2024: net-zero Britain and Reliable Britain; the CCL (NZ8) its own row; "
                           "NZ1c and its tax and price parts shown as 'of which' inside NZ1, never added",
                           "bills[2024].netzero, .gasonly, .nz1c; waterfall[2024] step 2 parts",
                           units="table, £bn, 2024 prices", period="2024"),
    "table_results_by_year": _m("Results by year, 2002-25 (2025 provisional); no column is built from a group",
                                "bills[y], gap[y]", units="table, £bn and £ per household, 2024 prices",
                                period="2002-2025", columns=[
                                    {"name": "nz_bill_gbp_bn", "source": "bills[y].totals.nz_real"},
                                    {"name": "rb_bill_gbp_bn", "source": "bills[y].totals.go_real"},
                                    {"name": "gap_gbp_bn", "source": "gap[y].national_gbp_bn_real"},
                                    {"name": "gap_per_household_gbp", "source": "gap[y].per_household_real"},
                                    {"name": "carbon_gbp_bn", "source": "bills[y].nz1c"},
                                    {"name": "ccl_gbp_bn", "source": "NZ8"}]),
    "table_waterfall_2002_24": _m("Waterfall 2002-24: the 11 printed steps in step order, adding to the headline",
                                  "the wf_ keys (never waterfall_grouped or netzero_groups)", units="table, £bn, 2024 prices"),
}


def values(run: dict) -> dict:
    gap = run["gap"]
    wf = {k: _bn(run, sum(_step_m(y, run, ls) for y in Y02_24)) for k, (_, ls) in WF_STEPS.items()}
    wf |= {k: _bn(run, sum(_line_m(y, run, i) for y in Y02_24 for i in ls)) for k, (_, ls) in WF_LINES.items()}
    b, g, f = run["bills"], gap, run["fleet"]
    T = lambda y, k: b[y]["totals"][k]  # noqa: E731
    line = lambda ident, ys=Y02_24: sum(_line_m(y, run, ident) for y in ys)  # noqa: E731
    hh = lambda y: b[y]["netzero_on_household_bill_per_household"]["value"]  # noqa: E731
    ge = run["answers"]["gas_break_even"]["2024"]
    wf |= {
        "nz_bill_2002_24_gbp_bn": _bn(run, sum(T(y, "nz_real") for y in Y02_24)),
        "rb_bill_2002_24_gbp_bn": _bn(run, sum(T(y, "go_real") for y in Y02_24)),
        "gap_2025p_gbp_bn": to_2024(g["2025"]["national_gbp_bn_real"], run),
        "gap_2024_gbp_bn": to_2024(g["2024"]["national_gbp_bn_real"], run),
        "gap_2022_gbp_bn": to_2024(g["2022"]["national_gbp_bn_real"], run),
        "nz_bill_2024_gbp_bn": _bn(run, T("2024", "nz_real")),
        "rb_bill_2024_gbp_bn": _bn(run, T("2024", "go_real")),
        "nz_bill_2025p_gbp_bn": _bn(run, T("2025", "nz_real")),
        "rb_bill_2025p_gbp_bn": _bn(run, T("2025", "go_real")),
        "s1_same_in_both_2024_gbp_bn": _bn(run, sum(x["national_gbp_m_real"] for x in b["2024"]["same_in_both"])),
        "firm_capacity_rb_gw_2024": run["firm_capacity"]["2024"]["gasonly_gw"],
        "firm_capacity_nz_gw_2024": run["firm_capacity"]["2024"]["netzero_gw"],
        "grid_window_2002_05_gbp_m": to_2024(line("NZ7", Y02_05) - line("GO5", Y02_05), run),
        "balancing_window_2002_05_gbp_m": to_2024(line("NZ6", Y02_05) - line("GO4", Y02_05), run),
        "nz5_2002_24_gbp_bn": _bn(run, line("NZ5")),
        "nz6_2002_24_gbp_bn": _bn(run, line("NZ6")),
        "go4_2002_24_gbp_bn": _bn(run, line("GO4")),
        "nz7_2002_24_gbp_bn": _bn(run, line("NZ7")),
        "go5_2002_24_gbp_bn": _bn(run, line("GO5")),
        "nz10_2002_24_gbp_bn": _bn(run, line("NZ10")),
        "grid_line_2002_24_gbp_bn": _bn(run, line("NZ7")) - _bn(run, line("GO5")),
        "balancing_line_2002_24_gbp_bn": _bn(run, line("NZ6")) - _bn(run, line("GO4")),
        "moe_uplift_2002_24_gbp_bn": _nominal_bn(run, "moe_gbp_m") + _nominal_bn(run, "moe_kept_gbp_m"),
        "years_shao_larger_count": sum(f[y]["moe"]["shao_mean_gbp_mwh"] > f[y]["moe"]["model_mean_gbp_mwh"]
                                       for y in Y02_24),
        "gas_price_rise_2024_pct": 100 * ge["price_rise_frac_central"],
        "rb_extra_gas_twh_2024": ge["dq_twh"],
        "break_even_gas_rise_2024_pct": 100 * (ge["gas_price_gbp_mwh_break_even"] / ge["gas_price_gbp_mwh_actual"] - 1),
        "plant_cost_edition_2024": f["2024"]["cost_edition"],
        "rb_new_build_gw_2024": f["2024"]["new_gw"],
        "negative_gap_years": [int(y) for y in Y02_24 if g[y]["national_gbp_bn_real"] < 0],
        "cost_per_household_2002_24_gbp": to_2024(sum(g[y]["per_household_real"] for y in Y02_24), run),
        "cost_per_household_2024_gbp": to_2024(g["2024"]["per_household_real"], run),
        "cost_per_household_2025p_gbp": to_2024(g["2025"]["per_household_real"], run),
        "own_bills_per_household_2002_24_gbp": to_2024(sum(hh(y) for y in Y02_24), run),
        "own_bills_per_household_2024_gbp": to_2024(hh("2024"), run),
        "own_bills_per_household_2025p_gbp": to_2024(hh("2025"), run),
        "margin_central_pct": 100 * capacity.margin_fraction(run["meta"]["central_settings"]["margin"]),
        "margin_low_pct": 100 * capacity.margin_fraction("low"),
        "margin_high_pct": 100 * capacity.margin_fraction("high"),
        "coal_lf_cap_pct": 100 * lfl.dukes_coal_lf_max()[0],
    }
    wf["table_lines_2024"] = _lines_table(run, "2024")
    wf["table_results_by_year"] = [
        {"year": int(y), "provisional": y in [str(p) for p in run["meta"]["provisional_years"]],
         "nz_bill_gbp_bn": _bn(run, T(y, "nz_real")), "rb_bill_gbp_bn": _bn(run, T(y, "go_real")),
         "gap_gbp_bn": to_2024(g[y]["national_gbp_bn_real"], run),
         "gap_per_household_gbp": to_2024(g[y]["per_household_real"], run),
         "carbon_gbp_bn": _bn(run, b[y]["nz1c"]["national_gbp_m_real"]),
         "ccl_gbp_bn": _bn(run, _line_m(y, run, "NZ8"))}
        for y in Y02_24 + ["2025"]]
    labels = {k: v[0] for k, v in (WF_STEPS | WF_LINES).items()}
    lines = {k: list(v[1]) for k, v in (WF_STEPS | WF_LINES).items()}
    wf["table_waterfall_2002_24"] = [{"key": k, "label": labels[k], "lines": lines[k], "value": wf[k]}
                                     for k in WF_ORDER]
    return wf | {
        "carbon_line_2002_24_gbp_bn": _bn(run, sum(run["bills"][y]["nz1c"]["national_gbp_m_real"] for y in Y02_24)),
        "carbon_price_receipts_2002_24_gbp_bn": _bn(run, sum(_nz1c_part_m(y, run, "NZ1c_tax") for y in Y02_24)),
        "carbon_price_receipts_2005_12_gbp_bn": _bn(run, sum(_nz1c_part_m(y, run, "NZ1c_tax") for y in Y05_12)),
        "carbon_price_receipts_2013_20_gbp_bn": _bn(run, sum(_nz1c_part_m(y, run, "NZ1c_tax") for y in Y13_20)),
        "carbon_rest_in_price_2002_24_gbp_bn": _bn(run, sum(_nz1c_part_m(y, run, "NZ1c_price") for y in Y02_24)),
        "carbon_in_price_2005_12_gbp_bn": _bn(run, sum(run["bills"][y]["nz1c"]["national_gbp_m_real"] for y in Y05_12)),
        "headline_2002_24_gbp_bn": to_2024(sum(gap[y]["national_gbp_bn_real"] for y in Y02_24), run),
        "gap_2002_25": to_2024(sum(gap[y]["national_gbp_bn_real"] for y in Y02_24 + ["2025"]), run),
    }
