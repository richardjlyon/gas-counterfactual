"""RB v1.1 F3 (decision 0160, card [internal ticket]): Annex B at the low and high ends of the printed range. For the option
that sets each end (the same option the range keys name), every bill line every year 2002-25: the central Annex B
value plus the change that option makes to the line (one_at_a_time.ranked[..].lines_moved_gbp_m_nominal, cash, put
into the run's money by CPIH and then 2024 prices). No number moves: each end's lines add to the released range end.

Rows: the net-zero Britain and Reliable Britain lines of Annex B. The same-in-both lines are the same in both bills
and no range option is recorded as moving them, so they are not repeated here (see annex_b_annual_tables). The two
carbon 'of which' parts (NZ1c_tax, NZ1c_price) are kept only where the option leaves NZ1c unmoved: the run file holds
the split for central only."""
from __future__ import annotations

from gascf import deflator_cpih
from gascf.figures import PRICE_BASE_LABEL, to_2024

Y02_25 = [str(y) for y in range(2002, 2026)]
NZ1C_PARTS = ("NZ1c_tax", "NZ1c_price")


def _m(end: str) -> dict:
    return {"label": f"Annex B at the {end} end of the range: every net-zero Britain and Reliable Britain bill line, "
                     f"every year 2002-25 (2025 provisional), under the option that sets the {end} end",
            "basis": "modelled", "provisional": False, "ticket": "v1.1 F3 (0160)",
            "run_field": f"annex_b_annual_tables rows + one_at_a_time.ranked[headline_{end}_end_switch] option "
                         "lines_moved_gbp_m_nominal (cash, CPIH to run money, to 2024 prices)",
            "units": "table, £bn, 2024 prices", "period": "2002-2025", "price_base": PRICE_BASE_LABEL,
            "status": "SOURCED", "print": True}


DECLARED = {"annex_b_low_end": _m("low"), "annex_b_high_end": _m("high")}


def _end_table(run: dict, row: dict) -> dict:
    from tools.figures_keys.core import _lines_table
    opts = [o for o in run["one_at_a_time"]["ranked"][row["switch"]] if o["settings"] == row["settings"]]
    if len(opts) != 1:
        raise KeyError(f"one_at_a_time.ranked[{row['switch']!r}]: {len(opts)} options with {row['settings']}")
    moved_all = opts[0]["lines_moved_gbp_m_nominal"]
    base = int(run["meta"]["price_base"])
    prov = [str(p) for p in run["meta"]["provisional_years"]]
    years = []
    for y in Y02_25:
        moved = moved_all.get(y, {})
        rows = []
        for r in _lines_table(run, y):
            if r["id"] in NZ1C_PARTS and "NZ1c" in moved:
                continue                          # the split under this option is not in the run file
            d = moved.get(r["id"], 0.0)
            v = r["value"] + (to_2024(deflator_cpih.to_real(d, int(y), base), run) / 1e3 if d else 0.0)
            rows.append({**{k: x for k, x in r.items() if x is not None}, "value": v, "moved": bool(d)})
        years.append({"year": int(y), "provisional": y in prov, "rows": rows})
    return {"switch": row["switch"], "option": row["option"], "plain_option": row["plain_option"],
            "settings": row["settings"], "headline_2002_24_gbp_bn": row["headline_2002_24_gbp_bn"], "years": years}


def values(run: dict) -> dict:
    if "one_at_a_time" not in run or "waterfall" not in run:
        return {k: None for k in DECLARED}
    from tools.figures_keys import range as R
    ranked = [r for r in R.table(run) if r["block"] == "ranked"]
    lo = min(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    hi = max(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    return {"annex_b_low_end": _end_table(run, lo), "annex_b_high_end": _end_table(run, hi)}
