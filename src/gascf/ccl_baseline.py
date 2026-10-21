"""Reliable Britain's Climate Change Levy counted only above its 2001 level (0044, ticket 12), on the shared
on-the-road component (0101, `gascf.on_the_road`, rate x volume mode).

The engine holds CCL receipts (NZ8, HMRC Environmental Taxes Bulletin Table 1b, GB-scaled), not volumes. The taxable
volume is inferred as NZ8 cash / the calendar-year main rate, the rate in force from 1 April (y-1) for a quarter
and from 1 April y for three quarters (0044's ruled figures, ccl-calc/ccl.py). Electricity main rates from
HMRC's historical rates table (vendored `data/raw/hmrc/s18a-envtax_historical_rates.html`); 2001 rate £0.0043/kWh
(Finance Act 2000 Sch. 6 para 42(1))."""
from __future__ import annotations

from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data/raw"
RATES_HTML = RAW / "hmrc/s18a-envtax_historical_rates.html"
# electricity main rate, £/kWh, in force from 1 April of the year (HMRC historical rates, Table 1)
RATES: dict[int, float] = {2001: 0.0043, 2007: 0.00441, 2008: 0.00456, 2009: 0.00470, 2011: 0.00485, 2012: 0.00509,
                           2013: 0.00524, 2014: 0.00541, 2015: 0.00554, 2016: 0.00559, 2017: 0.00568, 2018: 0.00583,
                           2019: 0.00847, 2020: 0.00811, 2021: 0.00775, 2022: 0.00775, 2023: 0.00775, 2024: 0.00775,
                           2025: 0.00775}
RATE_2001 = RATES[2001]


def fy_rate(y: int) -> float:
    """The main rate in force from 1 April of year y."""
    return RATES[max(k for k in RATES if k <= y)]


def cy_rate(y: int) -> float:
    """Calendar-year main rate: 1/4 x the rate from 1 April (y-1) + 3/4 x the rate from 1 April y (D2)."""
    return 0.25 * fy_rate(y - 1) + 0.75 * fy_rate(y)


def inferred_volume_gwh(nz8_gbp_m: float, y: int) -> float:
    """Taxable volume, GWh (£m / (£/kWh) = million kWh), inferred from the year's receipts (D2)."""
    return nz8_gbp_m / cy_rate(y)
