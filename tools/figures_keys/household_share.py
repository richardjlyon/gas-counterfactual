"""Ticket 24 (0060): the household (domestic) share of UK electricity sales for 2024, in per cent, read from
the run file's bills[2024].netzero_on_household_bill_per_household.domestic_share (DUKES 2026 5.2 / 5.5.D,
supplier sales only). Context only, not a headline figure."""
from __future__ import annotations

DECLARED = {
    "household_share_2024_pct": {
        "label": "Households' share of UK electricity sales, 2024 (DUKES 2026 5.2 / 5.5.D), %",
        "basis": "measured", "provisional": False, "ticket": "24", "context_only": True, "headline": False,
        "run_field": "bills[2024].netzero_on_household_bill_per_household.domestic_share"},
}


def values(run: dict) -> dict:
    return {"household_share_2024_pct":
            100 * run["bills"]["2024"]["netzero_on_household_bill_per_household"]["domestic_share"]}
