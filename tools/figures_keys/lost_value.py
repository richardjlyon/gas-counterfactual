"""Ticket 31 (0080-0085, 0093, 0081 option 2): lost value as a labelled estimate (0007), computed in the
release step from the frozen run file by `gascf.lost_value` (never written into the run file and never
summed into a headline key). 2002-24 quoted, 2025 apart; no 2002-25 key (0098).

Keys take the Report writer's placeholder names where there is one; `meta.mapped_name` carries the
`rb.lost_value.*` name. Keys with no placeholder keep their `rb.lost_value.*` name."""
from __future__ import annotations

from gascf import lost_value as lv
from gascf.figures import PRICE_BASE_LABEL, register_sha256

LABANDEIRA_PDF = "./s36/s36-labandeira-2016-meta-elasticity-rscas.pdf"
# 0081 citation ruling (17 Oct 14:17, corrected 14:25): the Labandeira values cite the open working paper only.
SOURCES = {
    "note": lv.NON_HOUSEHOLD_ONLY,      # EIC ruling 17 Oct 2026: on every rb.lost_value.* key
    "elasticities": {
        "citation": "Labandeira, Labeaga and López-Otero (2016), RSCAS 2016/25 working paper",
        "locators": {
            "-0.520": ("Table 3, Good block, Electricity LT simple average, printed p.7, PDF p.15; "
                       "electricity, all consumers, long-run average (Labandeira et al. 2016, Table 3)"),
            "-0.203": "Table 3, Good block, Electricity ST simple average, PDF p.15",
            "-0.677": "Table 4, Electricity LT meta-regression (GLS), printed p.8, PDF p.16",
        },
        "file": LABANDEIRA_PDF, "file_sha256": register_sha256(LABANDEIRA_PDF),
    },
    "households": dict(lv.SOURCE_ELASTICITIES["households"],
                       file="./s36/s36-pellini-2021-uk-residential-electricity-elasticity.pdf",
                       file_sha256=register_sha256("./s36/s36-pellini-2021-uk-residential-electricity-elasticity.pdf")),
    "household_share": {"file": "./s36/desnz/Electricity_since_1920.xlsx",
                        "file_sha256": register_sha256("./s36/desnz/Electricity_since_1920.xlsx"),
                        "note": "UK-wide household share (Northern Ireland about 2.7%), 0085 D6"},
}

PLACEHOLDERS = {
    "lost_value_2002_24_central_gbp_bn": ("quoted", "central", "2002-2024"),
    "lost_value_2002_24_low_gbp_bn": ("quoted", "low", "2002-2024"),
    "lost_value_2002_24_high_gbp_bn": ("quoted", "high", "2002-2024"),
    "lost_value_2025p_central_gbp_bn": ("quoted", "central", "2025"),
    "lost_value_2025p_low_gbp_bn": ("quoted", "low", "2025"),
    "lost_value_2025p_high_gbp_bn": ("quoted", "high", "2025"),
}
STRAIGHT = {f"rb.lost_value.straight_line.{c}.{p}": ("straight_line", c, p)
            for c in ("low", "central", "high") for p in ("2002-2024", "2025")}


def _m(label, mapped, period, units="£bn, 2024 prices"):
    return {"label": label, "basis": "estimated", "provisional": period == "2025", "ticket": "31",
            "run_field": "bills[y].totals gap_gbp_m, go_gbp_m, s1_gbp_m, gap_real_bn (gascf.lost_value.estimate)",
            "units": units, "period": period, "price_base": PRICE_BASE_LABEL, "status": "SOURCED", "print": True,
            "mapped_name": mapped, "sources": SOURCES, "estimate_label": "estimate, not a model output (0007)", "in_headline": False}


DECLARED = {
    **{k: _m(f"Lost value, {m.replace('_', ' ')}, {c}, {p}", f"rb.lost_value.{m}.{c}.{p}", p)
       for k, (m, c, p) in PLACEHOLDERS.items()},
    **{k: _m(f"Lost value, straight-line comparison (0083/0085), {c}, {p}", k, p) for k, (_, c, p) in STRAIGHT.items()},
    "rb.lost_value.by_year": _m("Lost value by year: household share s, central ε, r and both methods, central",
                                "rb.lost_value.by_year", "2002-2025", units="table, £bn, 2024 prices"),
    # EIC ruling 17 Oct 2026 (ticket 31, labelling only): the gap-weighted mean of the central eps(y), 2002-24.
    "lost_value_elasticity_central": _m(
        "average elasticity across households and non-households, weighted by each year's gap, 2002-24",
        "rb.lost_value.elasticity_central", "2002-2024", units="elasticity (dimensionless)"),
    "lost_value_straight_line_over_quoted_pct": _m(
        "How much higher the straight line is than the quoted figure, 2002-24 (0085: about 12%)",
        "rb.lost_value.straight_line_over_quoted", "2002-2024", units="%"),
}


def by_year(run: dict) -> dict:
    from gascf.figures import to_2024
    s = lv.household_share()
    out = {}
    for y in sorted(run["bills"], key=int):
        t = run["bills"][y]["totals"]
        e = s[int(y)] * lv.E_HOUSEHOLDS + (1 - s[int(y)]) * lv.E_NON_HOUSEHOLDS
        r = t["gap_gbp_m"] / (t["go_gbp_m"] + t["s1_gbp_m"])
        out[y] = {"s": s[int(y)], "eps_central": e, "r": r,
                  "quoted_central_gbp_bn": to_2024(lv._ce_actual(e, r) * t["gap_real_bn"], run),
                  "straight_line_central_gbp_bn": to_2024(lv._straight(e, r) * t["gap_real_bn"], run)}
    return out


def values(run: dict) -> dict:
    est = lv.estimate(run)
    out = {k: est[m][c][p] for k, (m, c, p) in (PLACEHOLDERS | STRAIGHT).items()}
    out["rb.lost_value.by_year"] = by_year(run)
    out["lost_value_straight_line_over_quoted_pct"] = 100 * est["straight_line_over_quoted"]
    yb = {y: v for y, v in out["rb.lost_value.by_year"].items() if int(y) <= 2024}
    gap = {y: run["bills"][y]["totals"]["gap_real_bn"] for y in yb}      # real GAP, as the quoted total weights it
    out["lost_value_elasticity_central"] = sum(yb[y]["eps_central"] * gap[y] for y in yb) / sum(gap.values())
    return out
