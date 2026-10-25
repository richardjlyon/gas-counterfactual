"""Ticket 28 (0092): the cost of the EII exemptions shifted onto households, a labelled estimate (0007),
stated beside the gap and never summed into a headline key. Port of
`reports-programme/b-items-calc/b18_eii_shift.py` onto the run file's own lines.

Engine household amount = national line × domestic share d (cost spread over all supply). With an
exemption on x·E of supply S the charge falls on S − x·E, so the household shift = engine household
amount × x·E / (S − x·E).
- S = UK consumption by final users (DESNZ Electricity since 1920, col L) × the engine's GB share
  (read from the NZ8 line's note, "consumption <share>").
- E = exempt EII electricity by RO obligation year (DESNZ/BEIS "Calculating the level of the RO" notes;
  Researcher, research-pos-shared-b.md B18). Inferred inputs (0092): the same exempt volumes apply to
  FiT and CfD as to the RO; 2018/19 and 2019/20 are inferred outturns; 2025/26 is a forecast.
- Reading A (low): E is eligible supply, x = 0.85 to 2023/24, 1.0 from 2024/25. Reading B (high): E is
  the exempt volume already, x = 1 throughout.
- Financial to calendar year: 0.25 FY(y−1) + 0.75 FY(y). The CM exemption starts 1 Apr 2024 (SI 2024/434).
- Lines: RO + FiT + CfD (NZ2, NZ3, NZ4, NZ4b) and CM (NZ5), in the run's money, then 2024 prices."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from gascf.figures import PRICE_BASE_LABEL, to_2024

XLSX = Path(__file__).resolve().parents[2] / "data/raw/s36/desnz/Electricity_since_1920.xlsx"
SHEET = "Supply, Availability & Consumpt"
EXEMPT_TWH = {2018: 10.4, 2019: 10.7, 2020: 9.9, 2021: 11.5, 2022: 9.50, 2023: 8.84, 2024: 11.6, 2025: 10.69}
RFC = ("NZ2", "NZ3", "NZ4", "NZ4b")
YEARS = range(2018, 2025)


@lru_cache(maxsize=None)
def final_consumption_twh() -> dict[int, float]:
    import openpyxl
    rows = list(openpyxl.load_workbook(XLSX, read_only=True, data_only=True)[SHEET].iter_rows(values_only=True))
    if not str(rows[5][11]).startswith("Total consumption by final users"):
        raise ValueError(f"{XLSX.name}: column L is not 'Total consumption by final users'")
    return {r[0]: r[11] for r in rows if isinstance(r[0], int)}


def _year(run: dict, y: int) -> dict:
    b = run["bills"][str(y)]
    ln = {x["id"]: x for x in b["netzero"]}
    gb = float(re.search(r"consumption ([\d.]+)", ln["NZ8"]["years_note"]).group(1))
    r = lambda ks: sum(ln[k]["national_gbp_m_real"] for k in ks if k in ln)  # noqa: E731
    return {"d": b["netzero_on_household_bill_per_household"]["domestic_share"], "gb": gb,
            "S": final_consumption_twh().get(y), "rfc": r(RFC), "cm": r(("NZ5",))}


def shift_gbp_m(run: dict, reading: str) -> float:
    """Σ2018-24 household shift, £m in the run's money."""
    eng = {y: _year(run, y) for y in range(2017, 2026)}

    def ratio(fy):
        if fy not in EXEMPT_TWH:
            return 0.0
        x = 1.0 if (fy >= 2024 or reading == "B") else 0.85
        nxt = eng.get(fy + 1, {}).get("S") or eng[fy]["S"]
        S = (0.75 * eng[fy]["S"] + 0.25 * nxt) * eng[fy]["gb"]
        return x * EXEMPT_TWH[fy] / (S - x * EXEMPT_TWH[fy])

    tot = 0.0
    for y in YEARS:
        rc = 0.25 * ratio(y - 1) + 0.75 * ratio(y)
        rcm = 0.25 * (ratio(y - 1) if y - 1 >= 2024 else 0) + 0.75 * (ratio(y) if y >= 2024 else 0)
        e = eng[y]
        tot += e["rfc"] * e["d"] * rc + e["cm"] * e["d"] * rcm
    return tot


def _m(label):
    return {"label": label, "basis": "estimated", "provisional": False, "ticket": "28",
            "run_field": "bills[y] NZ2+NZ3+NZ4+NZ4b and NZ5, 2018-24; domestic share; NZ8 note GB share",
            "units": "£bn, 2024 prices", "period": "2018-2024", "price_base": PRICE_BASE_LABEL,
            "status": "SOURCED", "print": True, "estimate_label": "estimate (0007)",
            "inferred_inputs": ["exempt volumes applied to FiT and CfD as to the RO",
                                "2018/19 and 2019/20 exempt volumes as inferred outturns",
                                "2025/26 exempt volume is a forecast (10.69 TWh)"],
            "sources": {"exempt_twh": "DESNZ/BEIS 'Calculating the level of the RO' notes (research-pos-shared-b.md B18)",
                        "final_consumption": "data/raw/s36/desnz/Electricity_since_1920.xlsx, col L",
                        # EIC approval 17 Oct 2026: the run-file field at full precision (DUKES 2026 5.2 over 5.5.D)
                        "domestic_share": "dukes-5.2; dukes-5.5D (0060)"},
            "in_headline": False}


DECLARED = {
    "eii_shift_2018_24_low": _m("EII exemptions' cost shifted onto households, 2018-24, reading A (estimate)"),
    "eii_shift_2018_24_high": _m("EII exemptions' cost shifted onto households, 2018-24, reading B (estimate)"),
    # RB v1.1 A1 (decision 0160, card [internal ticket]): Annex D's working for the two keys above, year by year
    "table_eii_shift_working": {**_m("Annex D working: the EII shift year by year, 2018-24, both readings, with every "
                                     "input (S, GB share, domestic share, exempt volume, x, the calendar ratios, the "
                                     "lines); the shifts add to eii_shift_2018_24_low and _high"),
                                "units": "table, TWh, shares, £m 2024 prices", "ticket": "v1.1 A1 (0160)"},
}


def working(run: dict) -> dict:
    """The arithmetic of `shift_gbp_m`, kept year by year (same formula, same inputs)."""
    eng = {y: _year(run, y) for y in range(2017, 2026)}

    def ratio(fy, reading):
        if fy not in EXEMPT_TWH:
            return 0.0
        x = 1.0 if (fy >= 2024 or reading == "B") else 0.85
        nxt = eng.get(fy + 1, {}).get("S") or eng[fy]["S"]
        S = (0.75 * eng[fy]["S"] + 0.25 * nxt) * eng[fy]["gb"]
        return x * EXEMPT_TWH[fy] / (S - x * EXEMPT_TWH[fy])

    rows = []
    for y in YEARS:
        e = eng[y]
        row = {"year": y, "final_consumption_twh": e["S"], "gb_share": e["gb"], "domestic_share": e["d"],
               "exempt_twh_fy": EXEMPT_TWH.get(y), "rfc_lines_gbp_m": to_2024(e["rfc"], run),
               "cm_line_gbp_m": to_2024(e["cm"], run)}
        for rd in ("A", "B"):
            rc = 0.25 * ratio(y - 1, rd) + 0.75 * ratio(y, rd)
            rcm = 0.25 * (ratio(y - 1, rd) if y - 1 >= 2024 else 0) + 0.75 * (ratio(y, rd) if y >= 2024 else 0)
            row |= {f"ratio_{rd}_rfc": rc, f"ratio_{rd}_cm": rcm,
                    f"shift_{rd}_gbp_m": to_2024(e["rfc"] * e["d"] * rc + e["cm"] * e["d"] * rcm, run)}
        rows.append(row)
    return {"years": rows, "exempt_twh_by_fy": dict(EXEMPT_TWH),
            "x_reading_A": {"to_2023_24": 0.85, "from_2024_25": 1.0}, "x_reading_B": 1.0,
            "calendar_rule": "0.25 FY(y-1) + 0.75 FY(y); CM exemption from 1 Apr 2024 (SI 2024/434)",
            "money": "£m, 2024 prices"}


def values(run: dict) -> dict:
    return {"eii_shift_2018_24_low": to_2024(shift_gbp_m(run, "A"), run) / 1e3,
            "eii_shift_2018_24_high": to_2024(shift_gbp_m(run, "B"), run) / 1e3,
            "table_eii_shift_working": working(run)}
