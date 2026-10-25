"""RB v1.1 (decision 0160, card [internal ticket]): one key per held row (`bills.HELD_SWITCHES`, run-file block
`one_at_a_time.held`): the 2002-24 headline under that row alone, in 2024 prices, and its change from central.

The rows sit in their own block, which no range key reads, so none can ever set an end of the printed range. Richard
ruled where four of them print (decision 0163, 21 Oct 2026; card [internal ticket] item 3):
- O2, R13 (a): "DESNZ's published high case as it stands (capital and hurdle rate), as a methods-page row";
- O3, R18 (a): nuclear in the Capacity Market at its auction obligation, on the methods page;
- M10, R10 (a): UCL's long-term values for 2021-23, a sensitivity row (the M9 re-estimate is central for May 2021-Dec 2023, decision 0164);
- A5, R14 (a): Krichene's 0.27, a sensitivity row; 0.61 stays the range end.
Those keys print, with `placement` and `can_set_range_end: False`, and are listed in `table_ruled_rows`. The O2
capital-only row (option (b) of R13, not chosen) and O5a (the 0044 note run) stay unprinted.

O5a keeps the name the figures-keys register already gives it (headline_lec_uncapped_2002_24_gbp_bn, left for a
ruling by ticket 12, tools/figures_keys/ccl.py). A run without the block (v4-s38 and earlier) gives None.
"""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_24 = [str(y) for y in range(2002, 2025)]

# key -> (bills attribute naming the held row, label, the ruling, where it prints or None)
ROWS = {
    "held_o3_nuclear_cm_auction_2002_24_gbp_bn": (
        "HELD_O3", "Headline 2002-24 with nuclear counted in the Capacity Market at its auction obligation (O3)",
        "R18 (a)", "methods_page"),
    "headline_lec_uncapped_2002_24_gbp_bn": (
        "HELD_O5A", "Headline 2002-24 with the pre-August-2015 LEC exemption uncapped (O5a, the 0044 note run)",
        None, None),
    "held_m10_ucl_long_run_2002_24_gbp_bn": (
        "HELD_M10", "Headline 2002-24 with the 2021-23 merit-order uplift scaled to UCL's long-run estimate "
                    "(O'Shea, Horne and Maslin 2025 Table 5, preprint; M10)", "R10 (a)", "sensitivity"),
    "held_o2_high_capital_hurdle_2002_24_gbp_bn": (
        "HELD_O2_CAP_HURDLE", "Headline 2002-24 with plant costs at DESNZ's published high case, capital and hurdle "
                              "rate (the high hurdle is printed only in EGC 2025; O2)", "R13 (a)", "methods_page"),
    "held_o2_high_capital_only_2002_24_gbp_bn": (
        "HELD_O2_CAP", "Headline 2002-24 with plant costs at the editions' high case, capital only (O2)", "R13",
        None),
    "held_a5_krichene_1974_2004_2002_24_gbp_bn": (
        "HELD_A5", "Headline 2002-24 with the gas-price feedback at Krichene's 1974-2004 long-run pair, supply 0.21 "
                   "plus demand 0.06 = 0.27 (Krichene 2005 Table 2, VECM; A5)", "R14 (a)", "sensitivity"),
}
PLACE_TEXT = {"methods_page": "a methods-page row", "sensitivity": "a sensitivity row"}


def _m(label: str, attr: str, ruling: str | None, place: str | None, change: bool = False) -> dict:
    if place:
        where = f"; {PLACE_TEXT[place]} ({ruling}), never an end of the range"
    elif ruling:
        where = f"; not printed ({ruling} chose another row)"
    else:
        where = "; a note run (0044), not printed"
    return {"label": ("Change from central: " if change else "") + label + where,
            "basis": "modelled", "provisional": False, "ticket": "v1.1 (0160); placement t_6c0411d4 (0163)",
            "run_field": f"one_at_a_time.held[bills.{attr}][0].gap_real_bn, Σ2002-24"
                         + (" less Σ gap[y].national_gbp_bn_real" if change else "") + ", to 2024 prices",
            "units": "£bn, 2024 prices", "period": "2002-2024", "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
            "print": place is not None, "in_range": False, "can_set_range_end": False, "placement": place,
            "ruling": ruling}


DECLARED: dict = {}
for _k, (_a, _lab, _r, _p) in ROWS.items():
    DECLARED[_k] = _m(_lab, _a, _r, _p)
    DECLARED[_k.replace("_gbp_bn", "_change_gbp_bn")] = _m(_lab, _a, _r, _p, change=True)
DECLARED["table_ruled_rows"] = {
    "label": "Rows placed by Richard's rulings (0163): methods-page rows O2 (R13 (a)) and O3 (R18 (a)), sensitivity rows "
             "M10 (R10 (a)) and A5 (R14 (a)); each headline 2002-24 and its change from central; none is ranked, and "
             "none can set an end of the printed range",
    "basis": "modelled", "provisional": False, "ticket": "t_6c0411d4 item 3 (0163)",
    "run_field": "one_at_a_time.held, the placed rows", "units": "table, £bn, 2024 prices", "period": "2002-2024",
    "price_base": PRICE_BASE_LABEL, "status": "SOURCED", "print": True, "in_range": False, "can_set_range_end": False}


def values(run: dict) -> dict:
    held = (run.get("one_at_a_time") or {}).get("held")
    if held is None:
        return {k: None for k in DECLARED}
    from gascf import bills as B
    central = sum(run["gap"][y]["national_gbp_bn_real"] for y in Y02_24)
    out = {}
    for key, (attr, _, _, _) in ROWS.items():
        opts = held.get(getattr(B, attr))
        if opts is None or len(opts) != 1:
            raise KeyError(f"one_at_a_time.held: expected one row for bills.{attr}, found {0 if opts is None else len(opts)}")
        h = sum(opts[0]["gap_real_bn"][y] for y in Y02_24)
        out[key] = to_2024(h, run)
        out[key.replace("_gbp_bn", "_change_gbp_bn")] = to_2024(h - central, run)
    order = ("held_o2_high_capital_hurdle_2002_24_gbp_bn", "held_o3_nuclear_cm_auction_2002_24_gbp_bn",
             "held_m10_ucl_long_run_2002_24_gbp_bn", "held_a5_krichene_1974_2004_2002_24_gbp_bn")  # methods page, then sensitivity
    out["table_ruled_rows"] = [
        {"key": k, "row": getattr(B, ROWS[k][0]), "placement": ROWS[k][3], "ruling": ROWS[k][2],
         "can_set_range_end": False, "headline_2002_24_gbp_bn": out[k],
         "change_gbp_bn": out[k.replace("_gbp_bn", "_change_gbp_bn")]} for k in order]
    return out
