"""Lost value: the second cost of a dearer bill (0080), as a labelled estimate, not a model output (0007).

Port of reports-programme growth-calc/dwl.py into the release (0081, 0085, 0093). The Labandeira elasticities are cited
to the open working paper only: Labandeira, Labeaga and López-Otero (2016), RSCAS 2016/25 (0081 citation
ruling, 17 Oct 2026). The journal version is never cited and its numbers are never used."""
from __future__ import annotations

E_HOUSEHOLDS = -0.607       # Pellini (2021) Table 4, UK long-run residential, PDF p.15 (CR-S018)
E_NON_HOUSEHOLDS = -0.520   # 0081 option 2: electricity, all consumers, long-run average (Labandeira et al. 2016, Table 3); RSCAS 2016/25, Good block, PDF p.15
E_LOW = -0.203              # RSCAS 2016/25 Table 3, Good block, Electricity ST simple average, PDF p.15; international average (0082)
E_HIGH = -0.677             # RSCAS 2016/25 Table 4, Electricity LT meta-regression (GLS), PDF p.16

import warnings
from pathlib import Path

import openpyxl

from gascf import deflator_cpih as dfl

_LABANDEIRA = ("Labandeira, Labeaga and López-Otero (2016), A meta-analysis on the price elasticity of "
               "energy demand, EUI working paper RSCAS 2016/25 (open copy)")
# EIC ruling 17 Oct 2026 (ticket 31, 0085): the all-consumers average stands for non-household use only.
NON_HOUSEHOLD_ONLY = ("The Labandeira all-consumers long-run average is used here for the non-household share of use only; "
                      "households use Pellini (2021).")
SOURCE_ELASTICITIES = {
    "households": {"value": E_HOUSEHOLDS, "register": "CR-S018",
                   "citation": "Pellini (2021), Energy Economics 101:105411 (accepted version)",
                   "locator": "Table 4, UK long-run residential [-0.703, -0.562], PDF p.15 (accepted version)"},
    "non_households_central": {"value": E_NON_HOUSEHOLDS, "citation": _LABANDEIRA,
                               "locator": "Table 3, Good block, Electricity LT simple average, PDF p.15",
                               "label": "electricity, all consumers, long-run average (Labandeira et al. 2016, Table 3)",
                               "note": NON_HOUSEHOLD_ONLY},
    "low": {"value": E_LOW, "citation": _LABANDEIRA,
            "locator": "Table 3, Good block, Electricity ST simple average, PDF p.15"},
    "high": {"value": E_HIGH, "citation": _LABANDEIRA,
             "locator": "Table 4, Electricity LT meta-regression (GLS), PDF p.16"},
}
DESNZ_1920 = Path(__file__).resolve().parents[2] / "data/raw/s36/desnz/Electricity_since_1920.xlsx"  # staged once (ticket 01)
SHEET = "Supply, Availability & Consumpt"


def household_share() -> dict[int, float]:
    """{year: domestic consumption ÷ total consumption by final users} (DESNZ Electricity since 1920).
    UK-wide (Northern Ireland about 2.7%), stated in the label (0085, D6)."""
    warnings.simplefilter("ignore")
    ws = openpyxl.load_workbook(DESNZ_1920, read_only=True, data_only=True)[SHEET]
    rows = list(ws.iter_rows(values_only=True))
    h = rows[5]
    if h[9] != "Domestic consumption" or not str(h[11]).startswith("Total consumption by final users"):
        raise ValueError(f"{DESNZ_1920.name}: header cells J6/L6 moved")
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    return {r[0]: r[9] / r[11] for r in rows if isinstance(r[0], int) and num(r[9]) and num(r[11]) and r[11]}


def _ce_actual(e: float, r: float) -> float:
    """Lost value ÷ GAP, constant elasticity anchored on actual demand (0085); e < 0."""
    a = 1 + e
    return (1 + r) / (r * a) * (1 - (1 + r) ** (-a)) - 1


def _straight(e: float, r: float) -> float:
    """Lost value ÷ GAP, straight line ½|ε|r (0083 comparison)."""
    return 0.5 * abs(e) * r


def total_bn(run: dict, e: float, method: str, years) -> float:
    """Σ over `years` of lost value at one elasticity for every user, £bn 2024 prices (port check, spec test 2)."""
    f = {"quoted": _ce_actual, "straight_line": _straight}[method]
    cp = dfl.cpih()
    k = cp[2024] / cp[int(run["meta"]["price_base"])]
    tot = 0.0
    for y in years:
        t = run["bills"][str(y)]["totals"]
        tot += f(e, t["gap_gbp_m"] / (t["go_gbp_m"] + t["s1_gbp_m"])) * t["gap_real_bn"] * k
    return tot


def estimate(run: dict) -> dict:
    """The lost-value block for figures.json from a v4 run file (2024 prices, £bn)."""
    years = sorted(int(y) for y in run["bills"])
    s = household_share()
    cp = dfl.cpih()
    base = int(run["meta"]["price_base"])
    to_2024 = cp[2024] / cp[base]
    eps = {"central": lambda y: s[y] * E_HOUSEHOLDS + (1 - s[y]) * E_NON_HOUSEHOLDS,
           "low": lambda y: E_LOW, "high": lambda y: E_HIGH}
    by_year, out = {}, {"quoted": {}, "straight_line": {}}
    periods = {"2002-2024": [y for y in years if y <= 2024], "2025": [2025]}
    for case, e in eps.items():
        for name, f in (("quoted", _ce_actual), ("straight_line", _straight)):
            per_year = {}
            for y in years:
                t = run["bills"][str(y)]["totals"]
                r = t["gap_gbp_m"] / (t["go_gbp_m"] + t["s1_gbp_m"])
                per_year[y] = f(e(y), r) * t["gap_real_bn"] * to_2024
            out[name][case] = {p: sum(per_year[y] for y in ys) for p, ys in periods.items()}
    q, sl = out["quoted"]["central"]["2002-2024"], out["straight_line"]["central"]["2002-2024"]
    out["straight_line_over_quoted"] = sl / q - 1
    out["label"] = "estimate, not a model output (0007); UK-wide household share (NI about 2.7%)"
    out["sources"] = {"elasticities": SOURCE_ELASTICITIES,
                      "household_share": f"DESNZ, Historical electricity data: 1920 to 2025 ({DESNZ_1920.name})"}
    return out
