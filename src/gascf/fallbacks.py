"""Fallback registry (strand s27a, spec §15.5 item 3: "no silent fallbacks").

Plain words. Wherever the engine has no measured number for a year and uses something else
(a mean of other years, the nearest year, a pooled coefficient, a different source), it must
say so here. Each use is recorded once per (name, year) with its size, so the export can list
every fallback in `meta.fallbacks` and a test can fail on any fallback nobody declared.

Rules:
- Every fallback name is declared in `DECLARED` with a one-line plain description and the
  source it falls back to. `record()` refuses an undeclared name (the test relies on this).
- `size` is the fallback's value (or the gap it fills) in the units given by `unit`, so a
  reader can see how much rides on it.
- The registry is process-wide. Callers that are cached (`lru_cache`) record on their first
  call only; that is enough, because the registry is never cleared during a run.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

DECLARED: dict[str, str] = {
    "coal_efficiency_mean_2015_2023": (
        "DUKES 5.10.C prints no coal-fleet efficiency (0) for a year with no coal fleet "
        "(2025): the 2015-2023 coal-fleet mean is used for coal kept open in fossil Britain."),
    "dukes_efficiency_nearest_year": (
        "DUKES 5.10.C efficiency outside the printed years: the nearest printed year."),
    "ni_fossil_nearest_year": (
        "Northern Ireland fossil MW (taken off the UK DUKES 5.7 totals) for a year before 2002, the first "
        "DUKES station list the engine holds: the nearest list. Each year from 2002 takes its own edition's "
        "list (decision 0197), so this does not fire for 2002-25."),
    "shao_wind_pooled": (
        "Shao et al. 2022 wind coefficient for a calendar year partly or wholly outside its "
        "April 2009 - March 2021 sample: the pooled coefficient (Table 3) for the missing part."),
    "wind_gw_dukes_flat": (
        "Mean wind GW removed (for the Shao uplift) where the NESO generation mix is missing "
        "or estimated: DUKES 5.6.E wind supplied spread flat over the year. DUKES 5.6.E is UK wind, so it "
        "includes Northern Ireland (2002-08; the UK basis, declared, decision 0195)."),
    "oil_price_carried_forward": (
        "DESNZ QEP oil price for a quarter not yet printed: the latest printed quarter."),
    "gb_gas_share_nearest_year": (
        "GB share of UK gas consumption (DESNZ sub-national Table 7.2, 2015-24) for a year outside the table: "
        "the nearest published year (ticket 38, the non-power gas estimate only; never the gap)."),
    "gb_gas_demand_nearest_year": (
        "GB gas demand (Energy Trends 4.1) for a year outside the table: the nearest year "
        "(denominator of the gas-price feedback)."),
    # s27b fallbacks, registered by s27c (names as declared in carbon.CARBON_FALLBACKS; recorded by
    # `bills.record_netzero_fallbacks`). "fit-sy1-5-levelisation-ratio" retired by C-008 (Ofgem's published
    # levelisation funds for FIT years 1-5 now read).
    "cpf-receipts-2013": (
        "HMRC Table 1b prints no Carbon Price Support split for 2013: total CCL+CPF receipts 2013 "
        "less 2012 (carbon tax collected)."),
    # "ets-power-receipts-2025" retired by s36 ticket 21: 2025 is the ICE report 278 auctions x the 2024
    # share, labelled provisional (0079), not a carried value
    "bsuos-gen-share-interpolated": (
        "Generators' BSUoS share for a charging year between the CMP308 consultation's anchors "
        "(50:50 before CMP202, ~49:51 in 2017, 'expected' 47:53 by 2020): straight line; 47% "
        "carried to FY2022/23 (NZ6, GO4)."),
    "bsuos-fy2006-ibc-grossup": (
        "No measured balancing-cost total for FY2006/07: National Grid 2010 Table 1 GB IBC outturn "
        "x (1 + the FY2007/08 SO internal/external ratio, Ofgem TAR 2008-09 T22) (NZ6; s36 B11)."),
    "bsuos-fy2010-internal-cpih-interpolation": (
        "FY2010/11 SO internal balancing cost, which the March 2011 MBSS does not print: the real-terms "
        "(CPIH) mean of the FY2009/10 and FY2011/12 internal costs, added to the MBSS external cost (NZ6; "
        "card t_2dca67b2)."),
    # s36 ticket 24 (0060): the general guard on silent 2025 carry-forwards names each input here.
    "domestic-share-2025-carried": (
        "Domestic share of UK electricity sales (DUKES 5.2 / 5.5.D) for 2025 equal to (or missing and "
        "taken from) 2024: the 2024 value carried. Not used while DUKES 2026 prints 2025."),
    # decision 0169 (cards [internal ticket], [internal ticket]): recorded only when bills.Settings.ro_mutualisation is not 'off'
    "ro-mutualisation-sy24-zero": (
        "RO mutualisation for scheme year 24 (2025-26), whose compliance closes after the SY23 report: "
        "taken as 0 (no shortfall known), for the 2025 calendar year's 3/4 share only (never 2002-24)."),
}


class CarryForwardError(RuntimeError):
    """A bill input's 2025 value is a copy of 2024 (or missing) and no fallback is recorded."""


def require_recorded_carry_forward(name: str, series: dict, year: int = 2025) -> None:
    """s36 ticket 24 (0060): refuse a silent carry-forward. If `series` has no `year` value, or its
    `year` value equals `year - 1`'s, the fallback `name` must be recorded for `year`."""
    if (year in series and series[year] != series.get(year - 1)) or (name, int(year)) in _REG:
        return
    raise CarryForwardError(f"{name}: {year} value missing or a copy of {year - 1}, and no fallback recorded")


@dataclass(frozen=True)
class Fallback:
    name: str
    year: int
    size: float
    unit: str
    note: str = ""


_REG: dict[tuple[str, int], Fallback] = {}


def record(name: str, year: int, size: float, unit: str, note: str = "") -> None:
    """Record one use of a declared fallback. Undeclared names raise KeyError."""
    if name not in DECLARED:
        raise KeyError(f"undeclared fallback {name!r}: add it to gascf.fallbacks.DECLARED")
    _REG.setdefault((name, int(year)), Fallback(name, int(year), float(size), unit, note))


def recorded() -> list[dict]:
    """Every fallback used so far, sorted by name then year, with its description."""
    return [{**asdict(f), "description": DECLARED[f.name]} for _, f in sorted(_REG.items())]


def clear() -> None:
    """Tests only: forget what was recorded (cached callers will not re-record)."""
    _REG.clear()
