"""Ticket 47 (EIC ruling 17 Oct 2026 pass-4 point 3): figures keys for the QEP major power producers' gas price to
Ofgem WMI NBP day-ahead ratio, 2010-25. The mean, min and max move from the sourced section to MODELLED keys
(CR-S008, CR-S050, CR-S051 retired, not reassigned): nobody prints the ratio, the engine computes it. Two further
keys give the years of the min and max, which the draft §9.2 types. All read the run-file pricing block; a run
without the block gives None (lead builder 46-48 ruling); figures.assert_complete refuses any None key, whatever its status, when the release build writes figures.json (write(release=True)), so a missing value stops the release."""
from __future__ import annotations

_SOURCES = (
    "DESNZ Quarterly Energy Prices (QEP) Table 3.2.1 (Annual), 'Major power producers: Natural gas (pence per kWh) "
    "[Note 4]' (column F, cells F32 to F47), publication 29 Sep 2026",
    "Ofgem WMI 'Gas prices: day-ahead contracts, monthly average (Great Britain)' (chart YFsS4g98P)",
)


def _ratio(label: str, run_field: str, was: str, year: int | None = None) -> dict:
    m = {"label": label, "basis": "modelled", "provisional": True, "ticket": "47", "units": "ratio",
         "period": "2010-2025", "year_basis": "calendar", "run_field": run_field, "was_claims_id": was,
         "sources": list(_SOURCES), "status": "PENDING", "print": True, "print_dp": 3, "print_prefix": "",
         "notes": []}
    if year is not None:
        m["year"] = year
    return m


def _year_key(label: str, run_field: str, text_types: str) -> dict:
    return {"label": label, "basis": "modelled", "provisional": True, "ticket": "47", "units": "calendar year",
            "year_basis": "calendar", "run_field": run_field, "status": "PENDING", "print": False,
            "text_types": text_types, "locator": "draft 2.5 §9.2 L493", "notes": []}


DECLARED = {
    "rb.pricing.qep_dayahead_ratio_2010_25": _ratio(
        "Mean of the 16 calendar-year ratios 2010-25 of the QEP major power producers' gas price to the monthly "
        "NBP day-ahead price", "pricing.qep_dayahead_ratio.mean_2010_25", "CR-S008"),
    "rb.pricing.qep_dayahead_ratio_min_2010_25": _ratio(
        "Lowest of the 16 yearly QEP to day-ahead ratios 2010-25 (2021)",
        "pricing.qep_dayahead_ratio.min_2010_25.value", "CR-S050", year=2021),
    "rb.pricing.qep_dayahead_ratio_max_2010_25": _ratio(
        "Highest of the 16 yearly QEP to day-ahead ratios 2010-25 (2020)",
        "pricing.qep_dayahead_ratio.max_2010_25.value", "CR-S051", year=2020),
    "rb.pricing.qep_dayahead_ratio_min_year_2010_25": _year_key(
        "Calendar year of the lowest yearly QEP to day-ahead ratio 2010-25",
        "pricing.qep_dayahead_ratio.min_2010_25.year", "2021"),
    "rb.pricing.qep_dayahead_ratio_max_year_2010_25": _year_key(
        "Calendar year of the highest yearly QEP to day-ahead ratio 2010-25",
        "pricing.qep_dayahead_ratio.max_2010_25.year", "2020"),
}


def values(run: dict) -> dict:
    out = {k: None for k in DECLARED}
    blk = (run.get("pricing") or {}).get("qep_dayahead_ratio")
    if not blk:          # block missing: None; figures.assert_complete refuses it in release mode (any None, any status)
        return out
    out["rb.pricing.qep_dayahead_ratio_2010_25"] = blk["mean_2010_25"]
    out["rb.pricing.qep_dayahead_ratio_min_2010_25"] = blk["min_2010_25"]["value"]
    out["rb.pricing.qep_dayahead_ratio_max_2010_25"] = blk["max_2010_25"]["value"]
    out["rb.pricing.qep_dayahead_ratio_min_year_2010_25"] = int(blk["min_2010_25"]["year"])
    out["rb.pricing.qep_dayahead_ratio_max_year_2010_25"] = int(blk["max_2010_25"]["year"])
    return out
