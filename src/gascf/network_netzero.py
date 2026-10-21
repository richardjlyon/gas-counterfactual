"""Grid build-out for renewables: the part of transmission charges a regulator itself puts
down to net zero (spec §6, step 4(b), third line).

What a regulator says, and only that:

* **Ofgem, RIIO-3 Final Determinations, Impact Assessment (Dec 2025).** Table 3 "Profiling
  effects" gives electricity transmission (ET) network charges for a dual-fuel household with
  average energy use, £ a year in 2025/26 prices, for 2025/26 (the last RIIO-2 year) to
  2030/31, with Ofgem's re-profiling. Ofgem gives the reason for the rise in its own words:
  para 3.21, investment "projected to rise from £18bn during RIIO-ET2 to up to £70bn during
  RIIO-ET3 as we expand the network to reduce constraint costs, reduce our reliance on
  wholesale gas prices and connect new renewable generation"; para 5.39, "These bill increases
  will support the electrification of the power system, in line with government's CP2030 plans
  and the wider transition to net zero".
* **But Ofgem never splits that rise between renewables and other drivers.** Its ET annex
  (para 2.3) adds that "Upgrades are also required to connect increased demand, including the
  growth in industry, data centres and Artificial Intelligence (AI) zones", and Table 2 of the
  impact assessment shows part of the 2030/31 rise is finance (higher WACC, semi-nominal WACC),
  not build. ASTI (Ofgem, Dec 2022) is attributed wholly to offshore wind ("connect 50GW of
  offshore wind by 2030"; 26 projects "worth £19.8bn") but no one publishes its bill effect, and
  NESO says it has no ASTI cost granularity in TNUoS (Five-Year View Q&A, question 8).
* **RIIO-ED2 (distribution, 2023-28)** is described as "£22.2bn ... to help deliver net zero"
  but Ofgem gives no split of the bill between net zero and ordinary running of the network,
  so DUoS stays held equal.

So the bracket, per household, from 1 April 2026 (RIIO-3):

* **low = £0**: no regulator figure attributes any £ of the bill to renewables alone;
* **high = the whole ET step-up** since 2025/26 (Table 3, after profiling): the rise Ofgem
  attributes to CP2030 and net zero, which also carries demand growth and the finance changes.

Richard's rule (when evidence is thin, take the figure that makes the net-zero cost smaller)
makes **low** the staircase default; ``staircase(..., grid="high")`` gives the other end.
Before April 2026 there is no regulator per-household figure: null, with the reason.

Basis: `estimated` (an Ofgem projection at the time of Final Determinations, re-expressed from
2025/26 prices to the period's price year by the GDP deflator, financial-year weighted).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pymupdf

from .deflator import read_deflator

RAW = Path(__file__).parents[2] / "data/raw/ofgem_networks"
IA = RAW / "RIIO-3-Final-Determinations-impact-assessment.pdf"
ET_ANNEX = RAW / "RIIO-3-Final-Determinations-ET.pdf"
ASTI = RAW / "ASTI_decision_doc_-_Final_Published.pdf"
SRC_IA = "ofgem_riio3_fd_impact_assessment_t3"
SRC_ASTI = "ofgem_asti_decision_2022"
FIRST_FY = 2025            # Table 3's first column, 2025/26 (RIIO-2 baseline)
PRICE_BASE_FY = 2025       # "2025/26 prices"
UNSOURCED = "UNSOURCED"

QUOTE_DRIVERS = ("as we expand the network to reduce constraint costs, reduce our reliance on "
                 "wholesale gas prices and connect new renewable generation")
QUOTE_NET_ZERO = ("These bill increases will support the electrification of the power system, in "
                  "line with government’s CP2030 plans and the wider transition to net zero")
QUOTE_DEMAND = ("Upgrades are also required to connect increased demand, including the growth in "
                "industry, data centres and Artificial Intelligence (AI) zones")
QUOTE_ASTI = "We have decided to apply the ASTI framework to an initial 26 projects (worth £19.8bn)"


@lru_cache(maxsize=4)
def _text(path: Path) -> str:
    return re.sub(r"\s+", " ", " ".join(p.get_text() for p in pymupdf.open(path)))


@dataclass(frozen=True)
class EtCharges:
    years: tuple[int, ...]             # financial years, 2025 = 2025/26
    pre_profiling: dict[int, float]    # £/dual-fuel household/yr, 2025/26 prices
    profiling: dict[int, float]        # Ofgem's re-profiling (0 for 2025/26)

    def after_profiling(self, fy: int) -> float:
        return self.pre_profiling[fy] + self.profiling[fy]


def _nums(s: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


@lru_cache(maxsize=1)
def read_et_charges(path: Path = IA) -> EtCharges:
    """Ofgem RIIO-3 FD Impact Assessment, Table 3 'Profiling effects', ET rows."""
    t = _text(path)
    i = t.find("Table 3: Profiling effects")
    if i < 0:
        raise ValueError("RIIO-3 IA layout changed: 'Table 3: Profiling effects' not found")
    tab = t[i:i + 900]
    m = re.search(r"Period ((?:\d{4}/\d{2} ){5}\d{4}/\d{2})", tab)
    pre = re.search(r"ET charges \(pre-profiling\) ((?:-?\d+ ){5}-?\d+)", tab)
    prof = re.search(r"ET profiling effect ((?:-?\d+ ){4}-?\d+)", tab)
    if not (m and pre and prof):
        raise ValueError("RIIO-3 IA Table 3 layout changed: Period / ET rows not found")
    years = tuple(int(y[:4]) for y in m.group(1).split())
    if years[0] != FIRST_FY:
        raise ValueError(f"RIIO-3 IA Table 3 starts at {years[0]}, expected {FIRST_FY}")
    p = _nums(pre.group(1))
    q = [0.0] + _nums(prof.group(1))       # no profiling in 2025/26
    return EtCharges(years, dict(zip(years, p)), dict(zip(years, q)))


def check_quotes() -> dict[str, bool]:
    """Every quoted attribution is present in the stored document (tests assert all True)."""
    ia, et, asti = _text(IA), _text(ET_ANNEX), _text(ASTI)
    return {"drivers": QUOTE_DRIVERS in ia, "net_zero": QUOTE_NET_ZERO in ia,
            "demand": QUOTE_DEMAND in et, "asti": QUOTE_ASTI in asti}


def _fy_index(fy: int, idx: dict[int, float]) -> float:
    return 0.75 * idx[fy] + 0.25 * idx[fy + 1]


@dataclass(frozen=True)
class Bracket:
    fy: int
    low: float | None
    high: float | None
    unit: str
    basis: str
    source_id: str
    note: str

    def pick(self, case: str) -> float | None:
        if case not in ("low", "high"):
            raise ValueError(case)
        return self.low if case == "low" else self.high


def grid_netzero_per_household(fy: int, price_year: int | None = None) -> Bracket:
    """Low/high per-household transmission cost Ofgem attributes to net zero, financial year
    ``fy``, in ``price_year`` calendar-year prices (default 2025/26 prices, Ofgem's own)."""
    et = read_et_charges()
    if fy < et.years[1]:
        return Bracket(fy, None, None, "£/household/yr", UNSOURCED, SRC_ASTI,
                       f"{UNSOURCED}: before RIIO-3 (April 2026) no regulator gives a per-household "
                       "figure for renewables-driven transmission (ASTI: £19.8bn of projects, no bill "
                       "effect published); TNUoS held equal")
    if fy not in et.years:
        raise KeyError(f"{UNSOURCED}: RIIO-3 IA Table 3 ends at {et.years[-1]}/"
                       f"{(et.years[-1] + 1) % 100:02d}")
    step_up = et.after_profiling(fy) - et.after_profiling(FIRST_FY)
    if price_year is None:
        k, unit = 1.0, "£/household/yr (2025/26 prices)"
    else:
        idx = read_deflator()[0]
        k, unit = idx[price_year] / _fy_index(PRICE_BASE_FY, idx), f"£/household/yr ({price_year} prices)"
    lab = f"{fy}/{(fy + 1) % 100:02d}"
    return Bracket(
        fy, 0.0, step_up * k, unit, "estimated", SRC_IA,
        f"low £0: Ofgem attributes no £ to renewables alone (demand growth and finance changes are "
        f"also in the rise); high: ET charge {lab} £{et.after_profiling(fy):g} less 2025/26 "
        f"£{et.after_profiling(FIRST_FY):g} = £{step_up:g} per dual-fuel household (2025/26 prices, "
        f"Ofgem RIIO-3 FD IA Table 3, after profiling), the rise Ofgem says supports CP2030 and "
        "net zero")
