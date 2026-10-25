"""RB v1.1 M5: a life-extension cost for coal kept open past its real closing date (card [internal ticket]).

Decision 0163 R6 (a) (Richard Lyon, 21 Oct 2026, as relayed: "Agree. Next."): in the central case if the analyst
finds a published cost; a sensitivity row if the figure is only an assumption. No published coal figure was found
(outside-data-survey.md, M5), so on R6's own words this is a sensitivity row, never central: `kept_life_ext=
"borrowed_gas"`. The figure is CEPA and GHD for DESNZ (May 2025), Table 2.2, option 1B "End of life extension for 5
years", £81/kW in 2024 values, a CCGT figure: "assumption borrowed from gas plant". Ruling R33 asks Richard to confirm
it; if he picks (b) the row is dropped.

The figure is read from the stored text (data/raw/v11/, byte-identical to the programme's saved PDF), never typed in.
Working reading (stated in the card's results, not a ruling): the cost buys 5 years, so it is spread evenly, £/kW / 5 a
year, restated from 2024 money by CPIH, on each kept coal MW-year (time-weighted, as the keep-open cost).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

RULES = ("none", "borrowed_gas")
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/v11/cepa-ghd-2025-05-generation-cost-study-life-extension.txt"
SOURCE_ID = "cepa-ghd-2025-05-life-extension-table-2.2"
LABEL = "assumption borrowed from gas plant (CEPA/GHD 2025, CCGT, 5-year end-of-life extension)"


@lru_cache(maxsize=1)
def borrowed_gas() -> dict:
    """{'gbp_kw', 'years', 'price_base', 'label', 'source_file', 'quote'} from Table 2.2 option 1B."""
    t = SOURCE.read_text()
    if "Table 2.2: Refurbishment Cost Summary" not in t or "(2024 values)" not in t:
        raise ValueError(f"{SOURCE.name}: Table 2.2 or its '2024 values' heading moved")
    m = re.search(r"1B\s+End of life\s+Replacement and\s+(\d+)\s+(\d+)\s*\n\s*extension for (\d+)", t)
    if not m:
        raise ValueError(f"{SOURCE.name}: Table 2.2 option 1B row not found")
    gbp_m, gbp_kw, years = int(m.group(1)), float(m.group(2)), int(m.group(3))
    return {"gbp_kw": gbp_kw, "years": years, "price_base": 2024, "gbp_m": gbp_m, "label": LABEL,
            "source_id": SOURCE_ID, "source_file": str(SOURCE.relative_to(ROOT)),
            "quote": f"1B End of life extension for {years} years ... £{gbp_m}m, £{gbp_kw:.0f}/kW (2024 values)"}


def gbp_kw_yr(rule: str, year: int) -> float:
    """The row's cost, £/kW a year in year-y money (0 under 'none')."""
    if rule not in RULES:
        raise ValueError(f"unknown kept_life_ext rule {rule!r}; one of {RULES}")
    if rule == "none":
        return 0.0
    from gascf.fossil_fleet import restate
    c = borrowed_gas()
    return restate(c["gbp_kw"] / c["years"], c["price_base"], year)
