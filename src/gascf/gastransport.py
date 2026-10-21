"""Gas transport charges a new gas power station would pay National Gas (spec §3.3).

What is charged, and why only these:
- NTS Exit (Flat) Capacity: p/kWh/day of booked gas offtake capacity. Since Oct 2020 one
  uniform rate at every exit point. Read from National Gas, "October 2026 Charging Information
  Provision" (29 May 2026): 2026/27 final, 2027/28-2030/31 indicative.
- General Non-Transmission Services Charge: p/kWh on every kWh taken off the NTS. Read from
  National Gas, "Notice of General Non-Transmission Services Charges October 2026" (31 Jul 2026).
- Exit Revenue Recovery Charge: 0.0000 p/kWh/day from 1 Oct 2026 (same Information Provision).
- Not charged: entry capacity and entry commodity, because they are paid upstream of the
  NBP and are already inside the System Average Price.

Annex A's "Connection and use of system charges" (CCGT £4,400/MW/yr) are electricity
transmission charges, not gas, so nothing here is counted twice.

The station books exit capacity for its full-load gas burn every day of the year,
spare-capacity plant included. That is the dearer convention; it errs toward a costlier
gas world.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pymupdf

RAW = Path(__file__).parents[2] / "data/raw/nationalgas"
INFO = RAW / "October_2026_Charging_Information_Provision.pdf"
GNTS = RAW / "Notice_of_General_Non-Transmission_Services_Charges_October_2026.pdf"
GAS_YEARS = ("2026/27", "2027/28", "2028/29", "2029/30", "2030/31")


def _text(path: Path) -> str:
    return re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(path)))


@dataclass(frozen=True)
class GasTransport:
    gas_year: str
    exit_capacity_p_kwh_day: float
    commodity_p_kwh: float

    def fixed_gbp_kw_e_yr(self, efficiency_gcv: float) -> float:
        """Exit capacity for 1 kW of electrical output at full load, for a year."""
        return self.exit_capacity_p_kwh_day / 100 * 24 / efficiency_gcv * 365

    @property
    def commodity_gbp_mwh_gas(self) -> float:
        return self.commodity_p_kwh * 10


@cache
def read_transport() -> dict[str, GasTransport]:
    info = _text(INFO)
    # every directly connected (DC) exit point carries the same five-year row
    rows = re.findall(r" DC ((?:\d\.\d{4} ){4}\d\.\d{4})", info)
    distinct = {r for r in rows}
    if len(rows) < 50 or len(distinct) != 1:
        raise ValueError(f"exit prices not uniform: {len(rows)} rows, {len(distinct)} distinct")
    exit_ = [float(x) for x in distinct.pop().split()]
    rrc = re.search(r"Exit RRC 1 October 2026 (\d\.\d{4})", info)
    if rrc is None:
        raise ValueError("Exit RRC not found")
    gnts = re.search(r"General Non-Transmission Services Charges \(p/kWh\) ((?:\d\.\d{4} ?){5})", _text(GNTS))
    if gnts is None:
        raise ValueError("GNTS row not found")
    comm = [float(x) for x in gnts.group(1).split()]
    return {y: GasTransport(y, e + (float(rrc.group(1)) if y == "2026/27" else 0.0), c)
            for y, e, c in zip(GAS_YEARS, exit_, comm)}
