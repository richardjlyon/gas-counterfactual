"""Capacity Market contracted (de-rated) obligations by delivery year, put on calendar years.

Interconnectors (0057, 0062-0066): one row per agreement in `cm_interconnectors_contracted_dy.csv`
(spec item interconnectors-contracted.md D1). The calendar rule is one function, reused for nuclear
(0089).

Nuclear (0089, variant D ruled 17 Oct 2026): nuclear counts in the CM split at its CM obligation,
post-trade, less any agreement the NESO CM register flags as suspended, for that whole delivery year
(the register has no suspension dates). Both nuclear input files are pinned by sha256 and refused on
mismatch. Reference: reports-programme b-items-calc/b13_nuclear_columns.py (variant D)."""
from __future__ import annotations

import csv
import hashlib
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[2] / "data/raw/s36"
IC_DY_CSV = RAW / "cm_interconnectors_contracted_dy.csv"


@lru_cache(maxsize=None)
def ic_rows() -> tuple[dict, ...]:
    with IC_DY_CSV.open(newline="") as f:
        return tuple({**r, "dy_start": int(r["dy_start"]), "derated_mw": float(r["derated_mw"])}
                     for r in csv.DictReader(f))


def ic_contracted_dy_mw() -> dict[int, float]:
    """{DY start year: contracted de-rated interconnector MW}."""
    out: dict[int, float] = {}
    for r in ic_rows():
        out[r["dy_start"]] = out.get(r["dy_start"], 0.0) + r["derated_mw"]
    return out


def ic_contracted_by_link(dy_start: int) -> dict[str, float]:
    """{interconnector: contracted de-rated MW} for one delivery year (rows with 0 MW '(none)' left out)."""
    out: dict[str, float] = {}
    for r in ic_rows():
        if r["dy_start"] == dy_start and r["interconnector"] != "(none)":
            out[r["interconnector"]] = out.get(r["interconnector"], 0.0) + r["derated_mw"]
    return out


def dy_to_cy(dy: dict[int, float]) -> dict[int, float]:
    """{DY start year: MW} -> {calendar year: MW} (0066): CY y = 9/12 DY(y-1)/y + 3/12 DY y/(y+1).
    Defined for each y whose DY y/(y+1) is in the file; a DY before the file's first is 0 MW."""
    return {y: 0.75 * dy.get(y - 1, 0.0) + 0.25 * dy[y] for y in sorted(dy)}


def ic_contracted_cy_mw() -> dict[int, float]:
    """{calendar year: contracted de-rated interconnector MW}, 2016-2025."""
    return dy_to_cy(ic_contracted_dy_mw())


NUCLEAR_DY_CSV = RAW / "cm_nuclear_contracted_dy.csv"
NUCLEAR_DY_SHA256 = "5cd7148cf16d61717b92541393255c4d6f2c886599133e1fb61d7c5e5b5cfcbd"
NUCLEAR_FLAGS_CSV = RAW / "cm-register-nuclear-flags-dy2017-2023.csv"
NUCLEAR_FLAGS_SHA256 = "1247d8e8575caced62c15b03b5c732e791b4daf1860226c495fee059872d141e"

# setting value -> column in the Researcher's file (variant D is derived from post-trade)
NUCLEAR_COLUMNS = {"auction_acquired": "auction_acquired_mw",
                   "post_trade_tw": "post_trade_tw_mw",
                   "post_trade_ex_dungeness": "post_trade_ex_dungeness_mw",
                   "post_trade_less_suspended": "post_trade_tw_mw"}
NUCLEAR_DEFAULT = "post_trade_less_suspended"


def _pinned(path: Path, sha: str) -> Path:
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != sha:
        raise ValueError(f"{path.name}: sha256 {got} does not match the pinned {sha}")
    return path


def _dy_days(y: int) -> int:
    return (date(y + 1, 9, 30) - date(y, 10, 1)).days + 1


def _summary_tw_mw(summary: str, y: int) -> float | None:
    """Time-weighted MW from the register's 'dd/mm/yyyy - dd/mm/yyyy:MW' obligation summary."""
    if not (summary or "").strip():
        return None
    tw = 0.0
    for part in filter(None, (p.strip() for p in summary.split(";"))):
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2})/(\d{2})/(\d{4}):\s*([0-9.]+)\s*MW", part)
        if not m:
            raise ValueError(f"unparsed capacity-obligation summary segment: {part!r}")
        a = date(int(m[3]), int(m[2]), int(m[1]))
        b = date(int(m[6]), int(m[5]), int(m[4]))
        tw += float(m[7]) * ((b - a).days + 1) / _dy_days(y)
    return tw


@lru_cache(maxsize=None)
def _suspended() -> tuple[dict, ...]:
    out = []
    with _pinned(NUCLEAR_FLAGS_CSV, NUCLEAR_FLAGS_SHA256).open(newline="") as f:
        for r in csv.DictReader(f):
            if not (r["Has Capacity Agreement been Suspended"] or "").strip().startswith("Yes"):
                continue
            y = int(r["Delivery Year"])
            tw = _summary_tw_mw(r["Capacity obligation Summary"], y)
            out.append({"dy": y, "cmu": r["CMU ID"], "unit": r["CM Unit Name"],
                        "agreement": r["Unique Agreement Identifier"],
                        "mw": tw if tw is not None else float(r["Auction Acquired Capacity Obligation"])})
    return tuple(out)


def suspended_agreements() -> list[dict]:
    """Nuclear agreements the register flags suspended: dy, cmu, unit, agreement, post-trade MW."""
    return [dict(r) for r in _suspended()]


@lru_cache(maxsize=None)
def suspended_mw_by_dy() -> dict[int, float]:
    """{DY start year: post-trade MW of agreements flagged suspended} (whole DY)."""
    out: dict[int, float] = {}
    for r in _suspended():
        out[r["dy"]] = out.get(r["dy"], 0.0) + r["mw"]
    return out


@lru_cache(maxsize=None)
def nuclear_contracted_dy_mw(column: str = NUCLEAR_DEFAULT) -> dict[int, float]:
    """{DY start year: nuclear de-rated CM obligation, MW} for the chosen column."""
    if column not in NUCLEAR_COLUMNS:
        raise ValueError(f"nuclear_cm_column {column!r}: one of {sorted(NUCLEAR_COLUMNS)}")
    with _pinned(NUCLEAR_DY_CSV, NUCLEAR_DY_SHA256).open(newline="") as f:
        dy = {int(r["delivery_year"][:4]): float(r[NUCLEAR_COLUMNS[column]]) for r in csv.DictReader(f)}
    if column == "post_trade_less_suspended":
        sus = suspended_mw_by_dy()
        dy = {y: v - sus.get(y, 0.0) for y, v in dy.items()}
    return dy


def nuclear_contracted_cy_mw(column: str = NUCLEAR_DEFAULT) -> dict[int, float]:
    """{calendar year: nuclear CM obligation, MW}, 2015-2025, by the one DY->CY rule (dy_to_cy)."""
    return dy_to_cy(nuclear_contracted_dy_mw(column))


def nuclear_release_stops() -> list[str]:
    """Rows still marked PLACEHOLDER in the nuclear file (none since the Researcher's file)."""
    with _pinned(NUCLEAR_DY_CSV, NUCLEAR_DY_SHA256).open(newline="") as f:
        return [f"{NUCLEAR_DY_CSV.name}:{r['delivery_year']}" for r in csv.DictReader(f)
                if (r.get("status") or "").strip().upper() == "PLACEHOLDER"]
