"""RB v1.1 F4 (decision 0160, card [internal ticket]): each one-at-a-time option's 2025 figure (provisional), beside its
2002-24 headline, for the ranked block and the methods page (the rows of table_one_at_a_time, same order). Held rows
(one_at_a_time.held) are not in it: where they print is a ruling.

Money: the run file's one_at_a_time[..].gap_real_bn is in the run's price base (2025 prices); keys print 2024 prices,
so each value goes through gascf.figures.to_2024 (CPIH 2024/2025 = 0.96304), never copied. No number moves."""
from __future__ import annotations

from gascf.figures import PRICE_BASE_LABEL, to_2024

DECLARED = {
    "table_options_2025p": {
        "label": "Each one-at-a-time option's 2025 gap (provisional) and its change from central 2025, beside its "
                 "2002-24 headline (Table 15.1 rows, same order); held rows excluded",
        "basis": "modelled", "provisional": True, "ticket": "v1.1 F4 (0160)",
        "run_field": "one_at_a_time.{ranked,methods_page}[..].gap_real_bn[2025] (run money, 2025 prices) to 2024 "
                     "prices; central gap[2025].national_gbp_bn_real",
        "units": "table, £bn, 2024 prices", "period": "2025", "price_base": PRICE_BASE_LABEL, "status": "SOURCED",
        "print": True},
}


def values(run: dict) -> dict:
    if "one_at_a_time" not in run:
        return {"table_options_2025p": None}
    from tools.figures_keys import range as R
    central = to_2024(run["gap"]["2025"]["national_gbp_bn_real"], run)
    out = []
    for r in R.table(run):
        opts = run["one_at_a_time"][r["block"]][r["switch"]]
        hit = [o for o in opts if o["settings"] == r["settings"]]
        if len(hit) != 1:
            raise KeyError(f"one_at_a_time.{r['block']}[{r['switch']!r}]: {len(hit)} options with {r['settings']}")
        g = to_2024(hit[0]["gap_real_bn"]["2025"], run)
        out.append({"block": r["block"], "switch": r["switch"], "option": r["option"],
                    "plain_option": r["plain_option"], "settings": r["settings"], "provisional": True,
                    "headline_2002_24_gbp_bn": r["headline_2002_24_gbp_bn"],
                    "gap_2025p_gbp_bn": g, "change_gbp_bn": g - central})
    return {"table_options_2025p": out}
