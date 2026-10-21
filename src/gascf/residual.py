"""Residual demand: the half-hourly electricity all-gas Britain must make from gas (spec §3).

Built from the generation side, so it does not depend on how NESO's demand measures
treat pumping, exports and station load:

    residual = transmission output of every fuel that all-gas Britain replaces (Elexon FUELHH)
             + embedded wind + embedded solar (NESO estimates)

Kept as they actually were: nuclear, pumped storage, interconnector imports, and Elexon
'OTHER' (it carries battery discharge: in 2025 its mean is 1.1 GW at 18:00-20:00 against
0.3 GW overnight; replacing it would count stored energy twice).
Replaced by gas: wind, biomass, non-pumped hydro and the gas itself; coal and oil too by
default (an all-gas Britain), switchable. Before Nov 2017 Elexon filed biomass under
OTHER, so pre-2018 years understate replaced biomass (Drax units 1-3 converted 2013-16).
Proper fix: map BM units to the Ofgem RO/FiT and LCCC CfD registers (memory.md, open).

NESO's demand balance is used as a check, not an input (tests/test_residual.py).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

RAW = Path(__file__).parents[2] / "data/raw"

KEPT = ("NUCLEAR", "PS")                       # plus every INT* interconnector column
GAS = ("CCGT", "OCGT")
RENEWABLE = ("WIND", "BIOMASS")               # subsidised transmission output
HYDRO = ("NPSHYD",)                            # small/refurbished RO-paid; large pre-2002 not
OTHER = ("OTHER",)                             # batteries + waste, AD, small thermal
FOSSIL_NON_GAS = ("COAL", "OIL")


@dataclass(frozen=True)
class HalfHour:
    day: date
    period: int
    gas_actual: float          # MW, CCGT + OCGT
    replaced_transmission: float   # MW, renewables + other (+ coal/oil if replaced)
    embedded: float            # MW, NESO embedded wind + solar
    kept: float                # MW, nuclear + PS + interconnector imports
    nd: float                  # MW, NESO national demand (for the balance check)

    @property
    def residual(self) -> float:
        return self.gas_actual + self.replaced_transmission + self.embedded


def _neso_date(s: str) -> date:
    s = s.strip('"')
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(s.title() if "-" in s[:3] else s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"NESO date format: {s!r}")


def read_neso(year: int) -> dict[tuple[date, int], dict[str, float]]:
    name = f"demanddataupdate_{year}.csv" if year >= 2026 else f"demanddata_{year}.csv"
    out = {}
    with (RAW / "neso" / name).open(newline="") as f:
        for r in csv.DictReader(f):
            if r.get("FORECAST_ACTUAL_INDICATOR", "A") != "A":
                continue
            k = (_neso_date(r["SETTLEMENT_DATE"]), int(r["SETTLEMENT_PERIOD"]))
            out[k] = {"ND": float(r["ND"]), "EW": float(r["EMBEDDED_WIND_GENERATION"]),
                      "ES": float(r["EMBEDDED_SOLAR_GENERATION"])}
    return out


def read_fuelhh(year: int) -> dict[tuple[date, int], dict[str, float]]:
    out = {}
    with (RAW / "elexon" / f"FUELHH_{year}.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            k = (date.fromisoformat(r["settlementDate"]), int(r["settlementPeriod"]))
            out[k] = {c: float(v) for c, v in r.items()
                      if c not in ("settlementDate", "settlementPeriod") and v != ""}
    return out


def residual_year(year: int, replace_coal_oil: bool = True, replace_hydro: bool = True,
                  replace_other: bool = False) -> tuple[list[HalfHour], list[tuple[date, int]]]:
    """Half-hours with both sources present, and the half-hours missing from either.

    Whatever is not replaced is kept, so residual + kept is the same in every bracket.
    """
    neso, fuel = read_neso(year), read_fuelhh(year)
    replaced = RENEWABLE + (HYDRO if replace_hydro else ()) + (OTHER if replace_other else ()) \
        + (FOSSIL_NON_GAS if replace_coal_oil else ())
    swing = HYDRO + OTHER + FOSSIL_NON_GAS
    rows, missing = [], sorted(set(neso) ^ set(fuel))
    for k in sorted(set(neso) & set(fuel)):
        g, n = fuel[k], neso[k]
        kept = sum(g.get(c, 0.0) for c in KEPT) + sum(v for c, v in g.items() if c.startswith("INT"))
        kept += sum(g.get(c, 0.0) for c in (FOSSIL_NON_GAS + swing) if c not in replaced)
        rows.append(HalfHour(
            day=k[0], period=k[1],
            gas_actual=sum(g.get(c, 0.0) for c in GAS),
            replaced_transmission=sum(g.get(c, 0.0) for c in replaced),
            embedded=n["EW"] + n["ES"], kept=kept, nd=n["ND"]))
    return rows, missing


def load_duration(rows: list[HalfHour]) -> list[float]:
    """Residual demand, MW, sorted high to low: the load-duration curve."""
    return sorted((r.residual for r in rows), reverse=True)
