"""Run-file block `pricing` (s36 ticket 47; EIC ruling 17 Oct 2026 pass-4 point 3): the QEP major power producers'
gas price to Ofgem WMI NBP day-ahead ratio, yearly 2010-25, with the plain mean of the 16 ratios and the lowest
and highest (value and year), unrounded, through the ticket 02 hook (export_v4.register_block). Reads the engine
function prices.qep_dayahead_ratio_2010_25; a block of its own, replaces no existing run-file key."""
from __future__ import annotations

from gascf import export_v4 as X
from gascf import prices as P


def block(built: dict) -> dict:
    r = P.qep_dayahead_ratio_2010_25()
    by_year = [{"year": y, **r["by_year"][y]} for y in sorted(r["by_year"])]
    return {"qep_dayahead_ratio": {
        "by_year": by_year,
        "mean_2010_25": r["mean"],
        "min_2010_25": {"value": r["min"]["value"], "year": r["min"]["year"]},
        "max_2010_25": {"value": r["max"]["value"], "year": r["max"]["year"]},
        "inputs": r["inputs"],
        "units": "ratio, £/MWh over £/MWh (GCV)"}}


X.register_block("pricing", block)
