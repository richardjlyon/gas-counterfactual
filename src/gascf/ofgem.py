"""Reader for Ofgem's wholesale cost allowance workbook (cap model Annex 2).

Reads, for every cap period, the hard-coded forward indices (tab 1b section "1b Index
(hard coded)"), the uplifted index, the regional £/MWh supplied, and the published
Direct Fuel cost per customer per year (tab 1a). Nothing is computed here except the
ratios Ofgem's own numbers imply (uplift, losses, consumption).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

REGIONS = (
    "Eastern", "East Midlands", "London", "N Wales and Mersey", "Midlands", "Northern",
    "North West", "Southern", "South East", "South Wales", "Southern Western", "Yorkshire",
    "Southern Scotland", "Northern Scotland",
)

TAB_1A = "1a Wholesale allowance"
TAB_1B = "1b Direct Fuel Cost Component"


@dataclass(frozen=True)
class CapPeriod:
    name: str                       # Ofgem's label, whitespace-normalised
    elec_index: float               # £/MWh at transmission, single-rate, hard-coded
    gas_index: float                # £/MWh at NBP, non-PPM, hard-coded
    elec_uplifted: float            # after shaping, imbalance, transaction costs, basis risk
    supplied: dict[str, float] = field(repr=False)   # region -> £/MWh supplied (after losses)
    direct_fuel: dict[str, float] = field(repr=False)  # region -> £/customer/yr (tab 1a)

    @property
    def uplift(self) -> float:
        return self.elec_uplifted / self.elec_index

    def losses(self, region: str) -> float:
        return self.supplied[region] / self.elec_uplifted

    def consumption_mwh(self, region: str = "Eastern") -> float:
        """Consumption Ofgem used for this period, implied by its own two tables."""
        return self.direct_fuel[region] / self.supplied[region]

    @property
    def months(self) -> int:
        return _months(self.name)


_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}


def _months(name: str) -> int:
    found = re.findall(r"(January|February|March|April|May|June|July|August|September|"
                       r"October|November|December)\s*(\d{4})?", name)
    (m1, y1), (m2, y2) = found[0], found[-1]
    y2 = int(y2)
    y1 = int(y1) if y1 else (y2 if _MONTHS[m1] <= _MONTHS[m2] else y2 - 1)
    return (y2 - y1) * 12 + _MONTHS[m2] - _MONTHS[m1] + 1


def _norm(s) -> str:
    return " ".join(str(s).replace("–", "-").split()).replace(" -", " -").strip()


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def _f(v) -> float:
    """A cell that must hold a number; anything else means the layout moved."""
    if not isinstance(v, (int, float)):
        raise ValueError(f"Annex 2: expected a number, found {v!r}")
    return float(v)


def read_annex2(path: Path) -> list[CapPeriod]:
    """All cap periods with both hard-coded indices populated, in workbook order.

    Fails loudly if the layout has moved: every anchor label is checked.
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    b = list(wb[TAB_1B].iter_rows(values_only=True))
    a = list(wb[TAB_1A].iter_rows(values_only=True))

    def find(rows, text, col=1):
        for i, r in enumerate(rows):
            if r[col] and str(r[col]).strip().startswith(text):
                return i
        raise ValueError(f"Annex 2 layout changed: {text!r} not found")

    hdr_b = find(b, "28AD Charge Restriction Period", col=5)
    hard = find(b, "1b Index (hard coded)")
    upl = find(b, "2. Apply allowance for shaping")
    loss = find(b, "3. Apply regional electricity losses")
    hdr_a = find(a, "28AD Charge Restriction Period", col=5)
    df = find(a, "4. Direct Fuel Cost Component")
    for i, want in ((hard + 1, "Electricity"), (hard + 3, "Non-PPM gas"),
                    (upl + 1, "Electricity"), (loss + 1, "Electricity"), (df + 1, "Electricity")):
        got = (b if i != df + 1 else a)[i][1]
        if str(got).strip() != want:
            raise ValueError(f"Annex 2 layout changed at row {i}: {got!r} != {want!r}")
    if str(b[hard + 1][2]).strip() != "Single-Rate Metering Arrangement":
        raise ValueError("Annex 2 layout changed: hard-coded electricity row is not single-rate")

    sup_rows = {str(b[loss + 1 + k][3]).strip(): loss + 1 + k for k in range(len(REGIONS))}
    df_rows = {str(a[df + 1 + k][3]).strip(): df + 1 + k for k in range(len(REGIONS))}
    if set(sup_rows) != set(REGIONS) or set(df_rows) != set(REGIONS):
        raise ValueError("Annex 2 layout changed: region rows do not match the 14 regions")

    a_cols = {_norm(v): j for j, v in enumerate(a[hdr_a]) if v and j >= 7}
    periods = []
    for j, label in enumerate(b[hdr_b]):
        if not label or j < 7:
            continue
        e, g = _num(b[hard + 1][j]), _num(b[hard + 3][j])
        if e is None or g is None:
            continue
        name = _norm(label)
        ja = a_cols[name]
        periods.append(CapPeriod(
            name=name, elec_index=e, gas_index=g, elec_uplifted=_f(b[upl + 1][j]),
            supplied={r: _f(b[i][j]) for r, i in sup_rows.items()},
            direct_fuel={r: _f(a[i][ja]) for r, i in df_rows.items()},
        ))
    if not periods:
        raise ValueError("Annex 2: no periods with hard-coded indices")
    return periods


def unique_periods(periods: list[CapPeriod]) -> list[CapPeriod]:
    """Drop Ofgem's duplicate 'January 2019 - March 2019' column (same indices as Oct 18-Mar 19)."""
    seen, out = set(), []
    for p in periods:
        key = (round(p.elec_index, 6), round(p.gas_index, 6))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out
