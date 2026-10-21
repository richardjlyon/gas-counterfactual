"""Run-file blocks for the grid lines (ticket 25), registered through export_v4's block hook (ticket 02).

scot_share_alt: decision 0102's alternative Scottish treatment before BETTA (`grid.scot_share_alt`),
a methods-page check printed beside the grid line. Never in the low-high range."""
from gascf import bills as B
from gascf import export_v4 as X
from gascf import grid


def scot_share_alt_block(built: dict) -> dict:
    return grid.scot_share_alt(B.PRICE_BASE) | {
        "price_base": B.PRICE_BASE, "in_range": False, "period": "CY2002-2005",
        "decision": "0102", "basis": "modelled",
        "note": "alternative: the generators' 27% taken off NGC (England and Wales) only before "
                "April 2005, nothing off SPT and SHETL; central keeps it on the whole base"}


X.register_block("scot_share_alt", scot_share_alt_block)
