"""Security-of-supply parameters for fleet B, read from NESO's Electricity Capacity Report 2026.

- De-rating factors (share of a plant's capacity counted as available at peak, net of
  breakdowns): ECR 2026 Data Workbook, Figure A10 (also printed in the 2026 T-1/T-4
  Auction Guidelines, Table 3: OCGT 92.97%, CCGT 90.48%).
- Margin (decision 0133, Richard Lyon, 20 Oct 2026): ECR 2026 p.5 says its T-1 recommendation,
  for delivery in 2027/28, "is equivalent to a de-rated margin in the range 4 to 5 GW" at a
  Base Case LOLE of about 0.1 hours/year. It is divided by the matching year's peak: the Base
  Case 2026 ACS peak for 2027/28 (Data Workbook, Figure B1, 61 GW). That is 6.6-8.2% of peak;
  the central case uses the midpoint, 4.5 GW = 7.4%. NESO does not publish the percentage: it
  is this division. (Before 0133 the engine divided by the 2030/31 peak and called the quote
  T-4; the T-4 page, p.7, gives a different margin, "around 4 GW".)

Why not 'target capacity / peak' (spec draft 3): the auction target (41.4 GW) counts only
Capacity-Market-eligible plant, so it is about 64% of peak, not a margin above it.

An all-gas system borrows this margin; whether gas alone would need more or less to meet
3 hours LOLE is not modelled, and is labelled as such.
"""
from __future__ import annotations

from pathlib import Path

from . import workbook_cache

RAW = Path(__file__).parents[2] / "data/raw/desnz_cm"
WORKBOOK = RAW / "NESO_ECR_2026_Data_Workbook.xlsx"
ECR_PDF = RAW / "NESO_ECR_2026.pdf"

MARGIN_GW_RANGE = (4.0, 5.0)          # ECR 2026 p.5, T-1 for 2027/28: "de-rated margin in the range 4 to 5 GW"
MARGIN_QUOTE = "de-rated margin in the range 4 to 5 GW"
MARGIN_RANGE_LOCATOR = ("NESO, Electricity Capacity Report 2026, p.5 (PDF p.5), 'T-1 capacity to secure', right-hand "
                        "column, T-1 recommendation for delivery in 2027/28: \"This is equivalent to a de-rated margin "
                        "in the range 4 to 5 GW\"")
MARGIN_DELIVERY_YEAR = "2027/28"      # the T-1 recommendation's delivery year (0133)
# The peak the margin is divided by: an input, registered here and checked against the workbook on every read.
MARGIN_PEAK = {
    "value_gw": 61.0,
    "delivery_year": MARGIN_DELIVERY_YEAR,
    "source": "NESO, Electricity Capacity Report 2026 Data Workbook (May 2026)",
    "locator": "sheet 'Figure B1' (Peak Demand next 10 years), row 'Base Case 2026', column '2027/28': ACS peak "
               "demand, GW",
    "file": "data/raw/desnz_cm/NESO_ECR_2026_Data_Workbook.xlsx",
    "decision": "0133",
}


def _rows(sheet: str) -> list[list]:
    """Rows of one ECR sheet with blank cells dropped: the workbook's tables start in varying columns.
    The workbook is read once per process (`workbook_cache`); the layout checks below run on every call."""
    return [[c for c in r if c is not None] for r in workbook_cache.sheet_rows(WORKBOOK, sheet)
            if any(c is not None for c in r)]


def read_derating() -> dict[str, float]:
    """{'ocgt': f, 'ccgt': f} from Figure A10, ECR 2026 column."""
    out = {}
    for r in _rows("Figure A10"):
        label = str(r[0])
        if "OCGT" in label:
            out["ocgt"] = float(r[2])         # [label, ECR 2025, ECR 2026, ...]
        elif "CCGT" in label:
            out["ccgt"] = float(r[2])
    if set(out) != {"ocgt", "ccgt"}:
        raise ValueError("ECR Figure A10 layout changed")
    return out


def read_peak_base_case() -> dict[str, float]:
    """ACS peak demand, Base Case 2026, GW by delivery year (Figure B1)."""
    rows = _rows("Figure B1")
    hdr = next(r for r in rows if r[0] == "Capacity (GW)")
    base = next(r for r in rows if r[0] == "Base Case 2026")
    return {y: float(v) for y, v in zip(hdr[1:], base[1:]) if y and v is not None}


def margin_peak_gw() -> float:
    """The registered 2027/28 Base Case peak, refused unless the workbook prints the same value."""
    got = read_peak_base_case().get(MARGIN_DELIVERY_YEAR)
    if got != MARGIN_PEAK["value_gw"]:
        raise ValueError(f"ECR Figure B1 Base Case 2026 peak for {MARGIN_DELIVERY_YEAR} reads {got}, "
                         f"registered {MARGIN_PEAK['value_gw']} GW (decision 0133)")
    return got


def margin_fraction(which: str = "central") -> float:
    """De-rated margin as a share of the 2027/28 ACS peak: 'low' 4 GW, 'central' 4.5 GW, 'high' 5 GW (0133)."""
    gw = {"low": MARGIN_GW_RANGE[0], "high": MARGIN_GW_RANGE[1],
          "central": sum(MARGIN_GW_RANGE) / 2}[which]
    return gw / margin_peak_gw()
