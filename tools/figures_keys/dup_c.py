"""Decision 0170 (card [internal ticket]; measure from card [internal ticket]): measure (c), the steelman frame. The cost of the
second system less the power it saved, with carbon pricing (EU ETS, UK ETS, Carbon Price Support) out of both roads.

    (c) = cost of the second system before VAT                  dup_cost_2002_24_gbp_bn
          (RO NZ2, FiT NZ3, CfD NZ4 + NZ4b, Capacity Market extra NZ5, balancing extra NZ6 - GO4,
           high-voltage grid extra NZ7 - GO5, generators' share of BSUoS and TNUoS, net-zero part, 0167 way 2)
        + VAT on households' share of the (c) parts (the engine's VAT rule, split by line)      dup_vat_gbp_bn
        - the power saving before carbon and before the generators' share                     dup_saving_2002_24_gbp_bn

Out of (c), each printed so (a), the headline, is rebuilt from (c) exactly every year:
    (a) = (c) + carbon in the power price NZ1c and its VAT + Climate Change Levy NZ8 + schemes NZ10 and their VAT.

Way 2 (0167) takes the generators' net-zero charge out of fossil Britain's market price, so it sits inside the engine's
step 1 (the fossil market cost and the kept output are lower by `fleet[y].gen_nz_charge.fossil_cut_gbp_m`). Here it is
taken out of step 1 and shown as a cost of the second system, split BSUoS / TNUoS in the proportion of the charge.

Choices ruled, decision 0173 (Richard Lyon, 22 Oct 2026, closing 0170's open items): P1 (i) the second system's own
costs only, schemes and CCL out; P2 (i) VAT in on households' share; P5 R1 (the kept_price=actual row, which charges
fossil Britain carbon, is left out of (c)'s range; its R2 low end is its own key, printed in Annex D). Method already
ruled: P3 the engine's way-2 generators' share (0167); P4 carbon taken out statically (M7, 0167), a limitation (0170);
P6 the engine's power saving at the market rule (0144). Each alternative is its own key; none sets a range end.

One reader (0168): every line comes from the run file through `_line_m` / `_nz1c_m` (the run's own bills lines, the
lines the shared cost register's engine.* rows are copied from) and every row move through `_moves`. The register
itself is not read here: wiring the engine to the shared register is card [internal ticket].

Carbon is taken out statically (no re-dispatch), the only measurable way (P4). The same monthly carbon price is taken
out of both roads: NZ1c from net-zero Britain's price, and fossil Britain's market price carries no carbon in the
central (the kept_price=actual row is the one that charges it, hence P5).
"""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

YEARS = [str(y) for y in range(2002, 2025)]
CRISIS = ("2021", "2022", "2023")
CARBON_ROW = {"kept_price": "actual"}      # the ranked row that charges fossil Britain carbon (P5)
MP_NO_UPLIFT = "no merit-order uplift (§15.3 rule)"
MP_AT_COST = "extra running at fuel, running and transport cost (the v4-s36 mix)"
RULED = ("Choices ruled, decision 0173: P1 (i) schemes and CCL out, P2 (i) VAT in on households' share, P5 R1 "
         "(kept_price=actual row out of (c)'s range; its R2 low end in Annex D). Method already ruled: P3 generators' "
         "share (0167, way 2); P4 carbon taken out statically (M7, 0167; a limitation, 0170); P6 power saving at the "
         "market rule (0144).")


def _m(label, run_field, units="£bn, 2024 prices", period="2002-2024", **extra):
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "t_a6fd25b7 (0170, 0173)",
            "run_field": run_field, "units": units, "period": period, "price_base": PRICE_BASE_LABEL,
            "status": "SOURCED", "print": True, "ruling": "0170, 0173", "note": RULED, **extra}


PARTS = {   # dup_cost parts: key -> (label, run lines)
    "dup_cost_ro_gbp_bn": ("Renewables Obligation (NZ2, incl. RO mutualisation, 0169)", "bills[y] NZ2"),
    "dup_cost_fit_gbp_bn": ("Feed-in Tariffs (NZ3)", "bills[y] NZ3"),
    "dup_cost_cfd_gbp_bn": ("Contracts for Difference incl. biomass (NZ4 + NZ4b)", "bills[y] NZ4 + NZ4b"),
    "dup_cost_cm_gbp_bn": ("Capacity Market extra over fossil Britain's own (NZ5)", "bills[y] NZ5"),
    "dup_cost_balancing_gbp_bn": ("Balancing extra (NZ6 less GO4)", "bills[y] NZ6 - GO4"),
    "dup_cost_grid_gbp_bn": ("High-voltage grid extra (NZ7 less GO5)", "bills[y] NZ7 - GO5"),
    "dup_cost_gen_share_bsuos_gbp_bn": ("Generators' share of BSUoS, net-zero part (0167 way 2)",
                                        "fleet[y].gen_nz_charge fossil_cut x bsuos / (bsuos + tnuos)"),
    "dup_cost_gen_share_tnuos_gbp_bn": ("Generators' share of TNUoS, net-zero part (0167 way 2)",
                                        "fleet[y].gen_nz_charge fossil_cut x tnuos / (bsuos + tnuos)"),
}
SAVING_PARTS = {
    "dup_saving_price_effect_gbp_bn": ("Power saving: price effect (merit-order uplift and gas-price feedback in "
                                       "fossil Britain)", "fleet[y] moe, moe_kept, gas_feedback, *_kept, *_at_cost"),
    "dup_saving_energy_gbp_bn": ("Power saving: energy (renewables' output at the market price against the fossil "
                                 "output that replaced it), before carbon and the generators' share",
                                 "NZ1 - NZ1c - fleet market - (GO1k - moe_kept - gas_feedback_kept) - gen cut"),
    "dup_saving_own_plant_gbp_bn": ("Power saving: fossil Britain's extra plant and its running (fixed, fuel at cost, "
                                    "running, transport)", "fleet[y] fixed + fuel - gas_feedback_at_cost + vom + transport"),
}

DECLARED = {
    "dup_c_2002_24_gbp_bn": _m("Measure (c), 2002-24: the second system's cost less the power it saved, carbon pricing "
                               "out of both roads, incl. VAT (choices ruled, 0173)", "Σ2002-24 (c)"),
    "dup_c_low_gbp_bn": _m("Measure (c), low end: lowest one-at-a-time (c), R1 (kept_price=actual row out)",
                           "min over one_at_a_time.ranked less CARBON_ROW of (c) + row move inside (c)"),
    "dup_c_low_option": _m("Option that sets (c)'s low end (R1)", "argmin, as dup_c_low_gbp_bn", units="text"),
    "dup_c_high_gbp_bn": _m("Measure (c), high end: highest one-at-a-time (c)",
                            "max over one_at_a_time.ranked of (c) + row move inside (c)"),
    "dup_c_high_option": _m("Option that sets (c)'s high end", "argmax, as dup_c_high_gbp_bn", units="text"),
    "dup_c_low_r2_gbp_bn": _m("Measure (c), low end with the kept_price=actual row kept in (R2)",
                              "min over every one_at_a_time.ranked row"),
    "dup_c_low_r2_option": _m("Option that sets (c)'s R2 low end", "argmin, as dup_c_low_r2_gbp_bn", units="text"),
    "dup_cost_2002_24_gbp_bn": _m("The second system's cost before VAT, 2002-24 (sum of the eight dup_cost parts)",
                                  "Σ dup_cost parts"),
    **{k: _m(v[0] + ", 2002-24, before VAT", v[1]) for k, v in PARTS.items()},
    "dup_vat_gbp_bn": _m("VAT on households' share of the (c) parts, 2002-24 (the engine's VAT rule, split by line)",
                         "Σ k[y] x (cost - saving), k = GO7 / (GO1 + GO1k + GO2..GO5)"),
    "dup_saving_2002_24_gbp_bn": _m("The power saving before carbon and before the generators' share, 2002-24 "
                                    "(positive = saving)", "-(waterfall step 1 - gen cut)"),
    **{k: _m(v[0] + ", 2002-24 (positive = saving)", v[1]) for k, v in SAVING_PARTS.items()},
    "dup_saving_share_pct": _m("Share of the second system's cost incl. VAT that the power saving paid",
                               "dup_saving / (dup_cost + dup_vat) x 100", units="%"),
    "dup_saving_share_ex_vat_pct": _m("Share of the second system's cost before VAT that the power saving paid",
                                      "dup_saving / dup_cost x 100", units="%"),
    "dup_c_2021_23_gbp_bn": _m("Measure (c), 2021-23", "Σ2021-23 (c)", period="2021-2023"),
    "dup_c_by_year": _m("Measure (c) year by year, 2002-24, with its parts (each year's parts add to its (c))",
                        "(c) and parts by year", units="table, £bn, 2024 prices"),
    "dup_c_per_household_gbp": _m("Measure (c) per household, 2002-24 (each year's (c) over that year's GB households)",
                                  "Σ (c)[y] / households[y]", units="£ per household, 2024 prices"),
    "dup_a_minus_c_gbp_bn": _m("The headline (a) less measure (c), 2002-24", "headline - (c)"),
    "dup_carbon_in_gap_gbp_bn": _m("Carbon in the power price and its VAT, 2002-24 (out of (c))",
                                   "Σ NZ1c x (1 + k)"),
    "dup_carbon_tax_collected_gbp_bn": _m("Carbon tax collected on power (CPS and UK auctions), 2002-24",
                                          "Σ netzero_groups.carbon_price_receipts"),
    "dup_carbon_not_collected_gbp_bn": _m("Carbon passed through the power price but not collected as tax in GB, "
                                          "2002-24", "Σ netzero_groups.carbon_in_price"),
    "dup_c_with_schemes_gbp_bn": _m("Measure (c) with schemes (and their VAT) and the CCL kept in (P1 (ii))",
                                    "(c) + NZ8 + NZ10 x (1 + v)"),
    "dup_c_ex_vat_gbp_bn": _m("Measure (c) before VAT (P2 (ii))", "(c) - dup_vat"),
    "dup_c_no_gen_share_gbp_bn": _m("Measure (c) without the generators' share (and its VAT)",
                                    "(c) - gen cut x (1 + k)"),
    "dup_c_fuel_at_cost_gbp_bn": _m("Measure (c) with the extra running priced at its fuel, running and transport cost "
                                    "(P6 (ii); the methods-page row)", "(c) + methods_page[MP_AT_COST] move inside (c)"),
    "dup_c_no_merit_uplift_gbp_bn": _m("Measure (c) with no merit-order uplift (the methods-page row)",
                                       "(c) + methods_page[MP_NO_UPLIFT] move inside (c)"),
}


# ------------------------------------------------------------------ the one reader of run lines

def _bill_line(run: dict, y: str, ident: str) -> dict:
    b = run["bills"][y]
    hits = [x for x in b["netzero"] + b["gasonly"] if x["id"] == ident]
    if len(hits) != 1:
        raise KeyError(f"bills[{y}]: {len(hits)} lines {ident}")
    return hits[0]


def _line_m(run: dict, y: str, ident: str) -> float:
    """Nominal £m of a bills line, or of NZ1c and its two parts."""
    b = run["bills"][y]
    if ident == "NZ1c":
        return b["nz1c"]["national_gbp_m_nominal"]
    if ident == "NZ1c_tax":
        return b["netzero_groups"]["carbon_price_receipts"]["national_gbp_m_nominal"]
    if ident == "NZ1c_price":
        return b["netzero_groups"]["carbon_in_price"]["national_gbp_m_nominal"]
    return _bill_line(run, y, ident)["national_gbp_m_nominal"]


def _real(run: dict, y: str) -> float:
    """Nominal £m -> £bn 2024 prices for year y: the run's own real/nominal ratio (NZ1), then CPIH to 2024."""
    nz1 = _bill_line(run, y, "NZ1")
    return to_2024(nz1["national_gbp_m_real"] / nz1["national_gbp_m_nominal"], run) / 1e3


def _vat_rates(run: dict, y: str) -> tuple[float, float]:
    """(k, v): NZ11 = k x (NZ1..NZ7 incl. NZ4b) + v x NZ10, k = v x domestic share (the engine's VAT rule)."""
    go = {i: _line_m(run, y, i) for i in ("GO1", "GO1k", "GO2", "GO3", "GO4", "GO5", "GO7")}
    base = sum(go[i] for i in ("GO1", "GO1k", "GO2", "GO3", "GO4", "GO5"))
    k = go["GO7"] / base if base else 0.0
    d = _bill_line(run, y, "GO7").get("domestic_share")
    return k, (k / d if d else 0.0)


def _moves(row: dict) -> dict:
    return row["lines_moved_gbp_m_nominal"]


# ------------------------------------------------------------------ by year

def year_parts(run: dict, y: str) -> dict:
    """Every part of (c) and of what (c) leaves out, £bn 2024 prices, for year y."""
    f, r = run["fleet"][y], _real(run, y)
    L = lambda i: _line_m(run, y, i)                                       # noqa: E731
    k, v = _vat_rates(run, y)
    g = f.get("gen_nz_charge")
    cut = g["fossil_cut_gbp_m"] if g else 0.0
    d = (g["bsuos_gbp_m"] + g["tnuos_gbp_m"]) if g else 0.0
    cut_b = cut * g["bsuos_gbp_m"] / d if g and d else 0.0
    step1 = L("NZ1") - L("NZ1c") - L("GO1") - L("GO1k")
    moe_k, gfb_k = f.get("moe_kept_gbp_m", 0.0), f.get("gas_feedback_kept_gbp_m", 0.0)
    gfb_ac = f.get("gas_feedback_at_cost_gbp_m", 0.0)
    energy = L("NZ1") - L("NZ1c") - f["market_gbp_m"] - (L("GO1k") - moe_k - gfb_k) - cut
    price = -(f["moe_gbp_m"] + moe_k + f["gas_feedback_gbp_m"] + gfb_k + gfb_ac)
    plant = -(f["fixed_gbp_m"] + f["fuel_gbp_m"] - gfb_ac + f["vom_gbp_m"] + f["transport_gbp_m"])
    m = {
        "ro": L("NZ2"), "fit": L("NZ3"), "cfd": L("NZ4") + L("NZ4b"), "cm": L("NZ5"),
        "balancing": L("NZ6") - L("GO4"), "grid": L("NZ7") - L("GO5"),
        "gen_share_bsuos": cut_b, "gen_share_tnuos": cut - cut_b,
        "saving": -(step1 - cut), "saving_energy": -energy, "saving_price_effect": -price, "saving_own_plant": -plant,
        "carbon": L("NZ1c"), "carbon_tax": L("NZ1c_tax"), "carbon_price": L("NZ1c_price"),
        "ccl": L("NZ8"), "schemes": L("NZ10"), "a": run["bills"][y]["totals"]["gap_gbp_m"],
        "step1": step1, "gen_cut": cut,
    }
    m["cost"] = sum(m[i] for i in ("ro", "fit", "cfd", "cm", "balancing", "grid", "gen_share_bsuos",
                                   "gen_share_tnuos"))
    m["vat"] = k * (m["cost"] - m["saving"])
    m["c"] = m["cost"] + m["vat"] - m["saving"]
    m["vat_carbon"], m["vat_schemes"], m["vat_gen_share"] = k * m["carbon"], v * m["schemes"], k * cut
    out = {key: val * r for key, val in m.items()}
    out["k"], out["v"] = k, v
    return out


def _row_move_c(run: dict, row: dict) -> tuple[float, float]:
    """(move in (a), move inside (c)) of one one-at-a-time row, £bn 2024 prices: (c) leaves out the moves of NZ8,
    of NZ10 with its VAT, and of NZ1c with its VAT."""
    d_a = d_out = 0.0
    for y, lines in _moves(row).items():
        if y not in YEARS:            # 2025p sits outside the 2002-24 total
            continue
        r = _real(run, y)
        k, v = _vat_rates(run, y)
        for lid, dv in lines.items():
            d_a += (-dv if lid.startswith("GO") else dv) * r
            if lid == "NZ8":
                d_out += dv * r
            elif lid == "NZ10":
                d_out += dv * (1 + v) * r
            elif lid == "NZ1c":
                d_out += dv * (1 + k) * r
    return d_a, d_a - d_out


def _opt(name: str, settings: dict) -> str:
    return f"{name}: " + ", ".join(f"{k}={v}" for k, v in settings.items())


def values(run: dict) -> dict:
    if "one_at_a_time" not in run or "bills" not in run:
        return {k: None for k in DECLARED}
    if any("carbon_price_receipts" not in (run["bills"].get(y) or {}).get("netzero_groups", {}) for y in YEARS):
        return {k: None for k in DECLARED}       # a toy or pre-v4-s35 run: no carbon split, so no measure (c)
    P = {y: year_parts(run, y) for y in YEARS}
    T = lambda key, ys=YEARS: sum(P[y][key] for y in ys)                     # noqa: E731
    c = T("c")
    rows = []
    for name, opts in run["one_at_a_time"]["ranked"].items():
        for o in opts:
            _, dc = _row_move_c(run, o)
            rows.append((c + dc, _opt(name, o["settings"]), o["settings"] == CARBON_ROW))
    rows.sort(key=lambda t: t[0])
    lo_r1 = next(t for t in rows if not t[2])
    mp = {name: opts[0] for name, opts in run["one_at_a_time"]["methods_page"].items()}
    hh = {y: run["bills"][y]["totals"]["gap_real_bn"] * 1e9 / run["bills"][y]["totals"]["gap_per_hh_real"]
          for y in YEARS}
    cost, vat, saving = T("cost"), T("vat"), T("saving")
    by_year = [{"year": int(y), "c_gbp_bn": P[y]["c"], "cost_gbp_bn": P[y]["cost"], "vat_gbp_bn": P[y]["vat"],
                "saving_gbp_bn": P[y]["saving"],
                **{k.removeprefix("dup_cost_").removesuffix("_gbp_bn") + "_gbp_bn": P[y][k[9:-7]] for k in PARTS},
                **{k.removeprefix("dup_").removesuffix("_gbp_bn") + "_gbp_bn": P[y][k[4:-7]] for k in SAVING_PARTS},
                "carbon_gbp_bn": P[y]["carbon"], "a_gbp_bn": P[y]["a"],
                "c_per_household_gbp": P[y]["c"] * 1e9 / hh[y]} for y in YEARS]
    out = {
        "dup_c_2002_24_gbp_bn": c,
        "dup_c_low_gbp_bn": lo_r1[0], "dup_c_low_option": lo_r1[1],
        "dup_c_high_gbp_bn": rows[-1][0], "dup_c_high_option": rows[-1][1],
        "dup_c_low_r2_gbp_bn": rows[0][0], "dup_c_low_r2_option": rows[0][1],
        "dup_cost_2002_24_gbp_bn": cost,
        **{k: T(k[9:-7]) for k in PARTS},
        "dup_vat_gbp_bn": vat,
        "dup_saving_2002_24_gbp_bn": saving,
        **{k: T(k[4:-7]) for k in SAVING_PARTS},
        "dup_saving_share_pct": saving / (cost + vat) * 100,
        "dup_saving_share_ex_vat_pct": saving / cost * 100,
        "dup_c_2021_23_gbp_bn": T("c", CRISIS),
        "dup_c_by_year": by_year,
        "dup_c_per_household_gbp": sum(P[y]["c"] * 1e9 / hh[y] for y in YEARS),
        "dup_a_minus_c_gbp_bn": T("a") - c,
        "dup_carbon_in_gap_gbp_bn": T("carbon") + T("vat_carbon"),
        "dup_carbon_tax_collected_gbp_bn": T("carbon_tax"),
        "dup_carbon_not_collected_gbp_bn": T("carbon_price"),
        "dup_c_with_schemes_gbp_bn": c + T("ccl") + T("schemes") + T("vat_schemes"),
        "dup_c_ex_vat_gbp_bn": c - vat,
        "dup_c_no_gen_share_gbp_bn": c - T("gen_cut") - T("vat_gen_share"),
        "dup_c_fuel_at_cost_gbp_bn": c + _row_move_c(run, mp[MP_AT_COST])[1],
        "dup_c_no_merit_uplift_gbp_bn": c + _row_move_c(run, mp[MP_NO_UPLIFT])[1],
    }
    return out
