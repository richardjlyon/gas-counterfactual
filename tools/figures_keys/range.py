"""Ticket 28 (0095): the printed range is the lowest and highest one-at-a-time result, each option on its
own with the rest central, over 2002-24 in 2024 prices; never a combined envelope; case B apart; the
option that sets each end is named. Read from the run-file block `one_at_a_time` (gascf.one_at_a_time).

Methods-page rows (`bills.METHOD_SWITCHES`) are an unranked block, never in the range (spec §15.5; R-A6
ruling, 17 Oct). Q-RANGE ruled by decision 0112 (Richard Lyon, 19 Oct 2026): SWITCHES plus the s36 alternatives.
A run without the block (v4-s35 and earlier) gives None for every key here."""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_24 = [str(y) for y in range(2002, 2025)]


def _m(label, run_field, units="£bn, 2024 prices", **extra):
    return {"label": label, "basis": "modelled", "provisional": False, "ticket": "28", "run_field": run_field,
            "units": units, "period": "2002-2024", "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
            "print": True, **extra}


DECLARED = {
    "headline_2002_24_low_gbp_bn": _m("Low end of the range: lowest one-at-a-time headline, each option on its own; "
                                      "printed with its switch's name (headline_low_end_switch, 0144 item 4A)",
                                      "min over one_at_a_time.ranked of Σ2002-24 gap_real_bn"),
    "headline_2002_24_high_gbp_bn": _m("High end of the range: highest one-at-a-time headline, each option on its own; "
                                       "printed with its switch's name (headline_high_end_switch, 0144 item 4A)",
                                       "max over one_at_a_time.ranked of Σ2002-24 gap_real_bn"),
    "headline_low_end_option": _m("Option that sets the low end", "argmin, one_at_a_time.ranked", units="text"),
    "headline_high_end_option": _m("Option that sets the high end", "argmax, one_at_a_time.ranked", units="text"),
    # 0144 item 4A (Richard Lyon, 20 Oct 2026): each printed range end carries its switch's name. v4-s36's
    # sens_e006 / sens_e034 keys (supply-only elasticities) are gone with the supply-only formula (0144 item 2A).
    "headline_low_end_switch": _m("Switch that sets the low end of the range (its registry name)",
                                  "argmin, one_at_a_time.ranked, switch", units="text"),
    "headline_high_end_switch": _m("Switch that sets the high end of the range (its registry name)",
                                   "argmax, one_at_a_time.ranked, switch", units="text"),
    "headline_range_text": _m("The printed range, each end with its switch's name (0144 item 4A)",
                              "one_at_a_time.ranked, min and max with switch names", units="text"),
    **{f"table_choice{c}": _m(f"One-at-a-time rows for Choice {c} (R-A6 map)", "table_one_at_a_time, choice",
                              units="table, £bn, 2024 prices") for c in range(1, 9)},
    "table_one_at_a_time": _m("One-at-a-time table (Table 15.1): ranked block, then the unranked methods page",
                              "one_at_a_time", units="table, £bn, 2024 prices"),
    # Keys tickets 12 and 26 left for a ruling, ruled by 0108 item 1.20 and 0112 (Richard Lyon, 19 Oct 2026)
    "headline_ccl_cash_frozen_2002_24_gbp_bn": _m("Headline 2002-24 with the 2001 CCL rate held cash-frozen (0044)",
                                                  "one_at_a_time.ranked[CCL_CASH_FROZEN]"),
    "sens_pre2002_cash_flat_2002_24_gbp_bn": _m("Headline 2002-24 with the 2001 on-the-road levels held cash-flat "
                                                "(NZ2 and NZ10 only, 0097)", "one_at_a_time.ranked[OTR_CASH_FLAT]"),
    "sens_pre2002_nffo_payments_2002_24_gbp_bn": _m("Headline 2002-24 with the 2001 Fossil Fuel Levy level at the "
                                                    "£85.5m NFFO payments estimate (0097; HC Deb 18 Apr 2002 c1139W)",
                                                    "one_at_a_time.ranked[NFFO_85_5]"),
}
NAMED_ROW_KEYS = {"headline_ccl_cash_frozen_2002_24_gbp_bn": "CCL_CASH_FROZEN",
                  "sens_pre2002_cash_flat_2002_24_gbp_bn": "OTR_CASH_FLAT",
                  "sens_pre2002_nffo_payments_2002_24_gbp_bn": "NFFO_85_5"}
# figures-keys.md ticket-28 rows: key -> (block, switch label, the option's settings, or None for a one-option row).
# 0108 item 1.15 (Richard Lyon, 19 Oct 2026) confirmed sens_grid_base_high = "grid renewal R high".
SENS_ROWS = {
    "sens_closures_actual_2002_24_gbp_bn": ("methods_page", "closures as they actually happened", None,
                                            "Headline 2002-24 with closures as they actually happened (methods page)"),
    "sens_margin_low_2002_24_gbp_bn": ("ranked", "spare margin (6.6% / 8.2%)", {"margin": "low"},
                                       "Headline 2002-24 with the spare margin at 6.6%"),
    "sens_ic_metered_2002_24_gbp_bn": ("ranked", "interconnectors at peak (metered flow, v4-s35)", None,
                                       "Headline 2002-24 with interconnectors counted at metered flow (v4-s35 basis)"),
    "sens_cm_kept_coal_2002_24_gbp_bn": ("ranked", "capacity market (kept coal in CM / full CM)",
                                         {"cm_rule": "extra_kept_coal"},
                                         "Headline 2002-24 with kept coal also needing the Capacity Market"),
    "sens_no_moe_2002_24_gbp_bn": ("methods_page", "no merit-order uplift (§15.3 rule)", None,
                                   "Headline 2002-24 with no merit-order uplift (methods page)"),
    "sens_kept_price_actual_2002_24_gbp_bn": ("ranked", "kept_price (actual / fleet avg)", {"kept_price": "actual"},
                                              "Headline 2002-24 with kept output priced at the actual price"),
    # Decision 0122 card item 4: the switch is wired (the low option moves the headline by +£4.1bn on v4-s36), but
    # grid.renewal_allowance sets high = central (v4-s35 T4, Richard 14 Oct 2026: central counts the WHOLE allowance
    # above the 2002-05 level; low = 0), so this row equals central exactly. It is not a "higher base".
    "sens_grid_base_high_2002_24_gbp_bn": ("ranked", "grid renewal R (low / high)", {"renewal": "high"},
                                           "Headline 2002-24 with the grid renewal allowance R at its high setting, "
                                           "which equals central (the whole allowance above the 2002-05 level, "
                                           "v4-s35 T4), so the row equals central exactly"),
}
DECLARED |= {k: _m(lab, f"one_at_a_time.{blk}[{sw}]" + (f" option {st}" if st else ""))
             for k, (blk, sw, st, lab) in SENS_ROWS.items()}


# R-A6 (Editor-in-chief, 17 Oct 2026, b-items/draft2-new-keys-and-register-questions.md "R-A6: Table 15.1 map"):
# each registry row to the draft's Choice 1-8 (§6-§13). Ranked rows by the label's stem (text before " (",
# so a changed value in brackets, e.g. 08's 0.34, keeps its choice); methods-page rows by full label.
# A row with no entry stops the build: a new switch must be placed by the Editor-in-chief first.
CHOICE_RANKED = {
    "wholesale_pre2010": 3,              # R1 (ruled 17 Oct)
    "kept_price": 3,                     # R2
    "spare margin": 2,                   # R3
    "residual method 2016+": 1,          # R4 (ruled 17 Oct)
    "interconnectors at peak": 2,        # R5
    "capacity market": 2,                # R6
    "balancing": 6,                      # R7
    "grid renewal R": 5,                 # R8
    "gas transport": 4,                  # R9 (ruled 17 Oct)
    "merit-order uplift": 3,             # R10
    "gas-price feedback": 4,             # R11
    # Decision 0112 (Richard Lyon, 19 Oct 2026): rows moved into the range keep their R-A6 choice (M9 5, M10 8,
    # M11 8); the GBP 85.5m row is the same on-the-road component as M11, so choice 8.
    "grid index at the controls' own X": 5,
    "2001 CCL rate held cash-frozen": 8,
    "2001 on-the-road levels held cash-flat": 8,
    "£85.5m NFFO payments estimate as the 2001 Fossil Fuel Levy level": 8,
}
CHOICE_METHODS = {
    "no merit-order uplift (§15.3 rule)": 3,                        # M1
    "merit-order uplift (s22 rule: larger of model / Shao)": 3,     # M2
    "merit-order uplift (smaller of model / Shao)": 3,              # M3
    "no gas-price feedback": 4,                                     # M4
    "no coal load-factor cap (s23b rule)": 1,                       # M5
    "closures as they actually happened": 1,                        # M6
    "new build gas only (no new coal, s22 rule)": 2,                # M7
    "merit-order uplift 2021-23: UCL short-run (preprint)": 3,      # M8 (ticket 18's label; R-A6 row M8, §8.4; 0112)
    # 0144 (v4-s37): the stack row keeps its R-A6 choice (R10, 3) on the methods page; the extra-running row C is
    # placed with the other pricing rows of choice 3 by the modeller, for the Editor-in-chief to confirm.
    "merit-order uplift (engine's own stack estimate)": 3,
    "extra running at fuel, running and transport cost (the v4-s36 mix)": 3,
}


def choice(block: str, switch: str, extra: dict | None = None) -> int:
    methods = CHOICE_METHODS | (extra or {})
    c = CHOICE_RANKED.get(switch.split(" (")[0]) if block == "ranked" else methods.get(switch)
    if c is None:
        raise KeyError(f"one_at_a_time.{block}: {switch!r} has no choice in the R-A6 map")
    return c


_S36_SUPPLY_ONLY = {"low": 0.34}     # v4-s36's supply-only rule removed by 0144 (names old run files only)


def option_name(switch: str, settings: dict) -> str:
    """Gas-price feedback options are named by their elasticity, never by the engine words 'low'/'high'
    (EiC R1: engine names kept; the engine's 'high' setting holds 0.06)."""
    if set(settings) == {"gas_feedback"}:
        from gascf.fossil_like_for_like import GAS_ELASTICITY
        if settings["gas_feedback"] == "none":       # methods-page row M4: the feedback switched off, no elasticity
            return "gas-price feedback off"
        from gascf.fossil_like_for_like import GAS_ELASTICITY_PAIRS
        r = settings["gas_feedback"]
        if r not in GAS_ELASTICITY_PAIRS:          # a v4-s36 run file read by this code: supply-only 'low' 0.34
            return f"gas-price feedback, elasticity {_S36_SUPPLY_ONLY[r]:g} (supply {_S36_SUPPLY_ONLY[r]:g} only, v4-s36)"
        e_s, e_d = GAS_ELASTICITY_PAIRS[r]
        pair = f"supply {e_s:g} + demand {e_d:g}" if e_d else f"supply {e_s:g} only, no demand side"
        return f"gas-price feedback, elasticity {GAS_ELASTICITY[r]:g} ({pair})"
    return f"{switch}: " + ", ".join(f"{k}={v}" for k, v in settings.items())


def _fy(y: int) -> str:
    return f"FY{y}/{str(y + 1)[2:]}"


def _bal_plain(settings: dict) -> str:
    from gascf import bills as B
    shares = B.balancing_workbook_shares()
    fy = [y for y, s in shares.items() if abs(s - settings["bal_share"]) < 1e-12]
    share = f"the {_fy(fy[0])} energy share ({100 * settings['bal_share']:.1f}%)" if fy else \
        f"an energy share of {100 * settings['bal_share']:.1f}%"
    base = {"ibc": "National Grid's incentivised-cost baseline",
            "nao_2005": "the NAO's £642m for 2005/06 as the baseline in every year"}[settings["bal_option"]]
    return f"Balancing: {base}, with {share}"


# Decision 0122 (needs file §5): plain words for each option, keyed by (setting, value); the writer may reword them.
PLAIN = {
    ("route", "lower"): "Wholesale price before mid-2010: the lower published series instead of Ofgem's chart",
    ("route", "model"): "Wholesale price before mid-2010: the engine's own modelled price instead of Ofgem's chart",
    ("kept_price", "actual"): "Power from plant Britain had, priced at the actual market price with carbon left in",
    ("kept_price", "fleet_avg"): "Power from plant Britain had, priced at the fossil fleet's average cost",
    ("margin", "low"): "Spare plant margin of 6.6% (central 7.4%)",
    ("margin", "high"): "Spare plant margin of 8.2% (central 7.4%)",
    ("residual", "fuelhh"): "Demand left for fossil plant from 2016 measured from Elexon's half-hourly generation "
                            "data instead of NESO's demand data",
    ("ic_basis", "metered"): "Interconnectors counted at their metered flow at the peak (the v4-s35 basis) instead "
                             "of their Capacity Market contracts",
    ("cm_rule", "extra_kept_coal"): "Capacity Market: coal stations Reliable Britain keeps open also need Capacity "
                                    "Market payments",
    ("cm_rule", "full"): "Capacity Market: its whole cost counted as a cost of net zero",
    ("renewal", "low"): "Grid renewal allowance not counted at all",
    ("renewal", "high"): "Grid renewal allowance at its high setting, which equals central",
    ("transport", False): "No gas transport cost added to Reliable Britain's fuel",
    ("moe", "model"): "Merit-order uplift from the engine's own estimate instead of Shao et al. (2022)",
    ("moe", "none"): "No merit-order uplift (the spec's §15.3 rule)",
    ("moe", "larger"): "Merit-order uplift: the larger of the engine's estimate and Shao et al. (the s22 rule)",
    ("moe", "smaller"): "Merit-order uplift: the smaller of the engine's estimate and Shao et al.",
    ("moe_crisis", "ucl_stmoe"): "Merit-order uplift in 2021-23 scaled to UCL's short-run estimate (preprint)",
    ("gas_feedback", "krichene_lr"): "Gas-price feedback at Krichene's world long-run pair, supply 0.16 plus demand "
                                     "0.45 (smaller feedback)",
    ("gas_feedback", "high"): "Gas-price feedback at a supply elasticity of 0.06 with no demand side (case B only)",
    ("extra_running", "cost"): "Extra running of the plant Britain had charged its fuel, running and transport cost, "
                               "not the market price (the v4-s36 mix)",
    ("gas_feedback", "none"): "No gas-price feedback",
    ("go5_index", "rpi_x"): "Grid carried forward on the price controls' own X values (RPI minus X) instead of RPI",
    ("ccl_baseline", "cash_2001"): "Climate Change Levy counted above its 2001 rate held in cash, not raised with "
                                   "inflation",
    ("otr_indexation", "cash"): "Fossil Fuel Levy and EESoP 2001 levels held in cash, not raised with inflation",
    ("otr_nz2_level_gbp_m", 85.5): "Fossil Fuel Levy 2001 level set at the £85.5m NFFO payments estimate instead "
                                   "of £92m",
    ("coal_lf", "none"): "Kept coal not capped at its highest recorded load factor",
    ("closures", "actual"): "Every power station closes on its real date",
    ("newbuild", "gas_only"): "New plant gas only, no new coal (the s22 rule)",
}


def plain_option(settings: dict) -> str:
    if set(settings) == {"bal_share", "bal_option"}:
        return _bal_plain(settings)
    if len(settings) == 1:
        (k, v), = settings.items()
        if (k, v) in PLAIN:
            return PLAIN[(k, v)]
    return "Option " + ", ".join(f"{k} {v}" for k, v in settings.items())   # unmapped: a test flags it


CARBON_LINES = ("NZ1c", "NZ1c_tax", "NZ1c_price")


def check_carbon_ccl_apart(rows: list[dict]) -> None:
    """0090 guard (ccl-key-mapping §4): a row labelled carbon moves no NZ8; a row naming the CCL moves no
    carbon line. Carbon and CCL options are never one row."""
    for r in rows:
        lab = r["switch"].lower()
        if "carbon" in lab and "NZ8" in r["lines_moved"]:
            raise ValueError(f"{r['switch']!r} is labelled carbon but moves NZ8")
        if ("ccl" in lab or "climate change levy" in lab) and set(CARBON_LINES) & set(r["lines_moved"]):
            raise ValueError(f"{r['switch']!r} names the CCL but moves a carbon line")


def table(run: dict, choices: dict | None = None) -> list[dict]:
    central = to_2024(sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24), run)
    rows = []
    for blk in ("ranked", "methods_page"):
        for switch, opts in run["one_at_a_time"][blk].items():
            for o in opts:
                h = to_2024(sum(o["gap_real_bn"][y] for y in Y02_24), run)
                moved = sorted({k for y in Y02_24 for k in o["lines_moved_gbp_m_nominal"].get(y, {})})
                rows.append({"block": blk, "switch": switch, "choice": choice(blk, switch, choices),
                             "lines_moved": moved,
                             "option": option_name(switch, o["settings"]),
                             "plain_option": plain_option(o["settings"]),
                             "settings": o["settings"], "headline_2002_24_gbp_bn": h, "change_gbp_bn": h - central})
    return rows


def values(run: dict) -> dict:
    if "one_at_a_time" not in run:
        return {k: None for k in DECLARED}
    from gascf import bills as B
    for blk, reg in (("ranked", B.SWITCHES), ("methods_page", B.METHOD_SWITCHES)):
        missing = [k for k in reg if k not in run["one_at_a_time"][blk]]
        if missing:
            raise KeyError(f"one_at_a_time.{blk}: no row for registry switch(es) {missing}")
    t = table(run)
    check_carbon_ccl_apart(t)
    ranked = [r for r in t if r["block"] == "ranked"]
    lo = min(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    hi = max(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    named = {}
    for key, attr in NAMED_ROW_KEYS.items():
        hit = [r["headline_2002_24_gbp_bn"] for r in ranked if r["switch"] == getattr(B, attr)]
        if len(hit) != 1:
            raise KeyError(f"one_at_a_time.ranked: expected one row for {attr}, found {len(hit)}")
        named[key] = hit[0]
    for key, (blk, sw, st, _) in SENS_ROWS.items():
        hit = [r["headline_2002_24_gbp_bn"] for r in t
               if r["block"] == blk and r["switch"] == sw and (st is None or r["settings"] == st)]
        if len(hit) != 1:
            raise KeyError(f"one_at_a_time.{blk}: expected one row for {sw!r} {st}, found {len(hit)}")
        named[key] = hit[0]
    return {"headline_2002_24_low_gbp_bn": lo["headline_2002_24_gbp_bn"],
            **named,
            "headline_2002_24_high_gbp_bn": hi["headline_2002_24_gbp_bn"],
            "headline_low_end_option": lo["option"], "headline_high_end_option": hi["option"],
            "headline_low_end_switch": lo["switch"], "headline_high_end_switch": hi["switch"],
            "headline_range_text": (f"£{lo['headline_2002_24_gbp_bn']:.1f}bn ({lo['switch']}) to "
                                    f"£{hi['headline_2002_24_gbp_bn']:.1f}bn ({hi['switch']})"),
            "table_one_at_a_time": t,
            **{f"table_choice{c}": [r for r in t if r["choice"] == c] for c in range(1, 9)}}
