"""Crisis-year merit-order uplift: the UCL sensitivity (s36 ticket 18; decisions 0069, 0086, 0087).

Shao et al. (2022) stays the central uplift in every year (0069). Under `Settings.moe_crisis =
"ucl_stmoe"` (a methods-page switch, not the range: the source is a preprint, not peer reviewed),
the 2021-23 Shao uplift is scaled so its time-mean equals target B (0086): O'Shea, Horne and Maslin
(2025) Table 4 Total MOE (the merit-order effect of wind), printed p.22 (PDF p.24), plus the engine's
own Shao solar part (2.98 £/MWh per GW of solar). Table 5 (long-run), printed p.25 (PDF p.27), is
carried in the data file for the record and never read by the build (0087)."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/raw/s36/ucl_oshea_2025_moe.yaml"


@lru_cache(maxsize=None)
def read(path: Path | None = None) -> dict:
    return json.loads(Path(path or DATA).read_text())


def require_sourced(path: Path | None = None) -> dict:
    """Refuse the UCL figures unless the data file is SOURCED and pinned to the staged PDF (test 1)."""
    from gascf.pending import PendingSourceError
    d = read(path)
    if d.get("status") != "SOURCED":
        raise PendingSourceError(f"{path or DATA}: status {d.get('status')!r}, not SOURCED")
    pdf = ROOT / d["file"]
    if not d.get("pdf_sha256") or hashlib.sha256(pdf.read_bytes()).hexdigest() != d["pdf_sha256"]:
        raise PendingSourceError(f"{path or DATA}: pdf_sha256 missing or not the staged PDF's")
    return d


CRISIS_YEARS = (2021, 2022, 2023)
RULES = ("shao", "ucl_stmoe")


def target_gbp_mwh(year: int, solar_gw: float, path: Path | None = None) -> float:
    """0086 target B: UCL Table 4 Total MOE (wind), printed p.22 (PDF p.24), plus the engine's own Shao
    solar part (Shao et al. 2022 Table 3 pooled solar term × the year's mean solar GW)."""
    from gascf.fossil_like_for_like import SHAO_SOLAR_POOLED
    return read(path)["stmoe_total_gbp_mwh"]["values"][str(year)] - SHAO_SOLAR_POOLED * solar_gw


def k(year: int, shao_mean: float, solar_gw: float, path: Path | None = None) -> float:
    """Scale on the hourly Shao uplift so its time-mean is target B in 2021-23; 1 in every other year."""
    if year not in CRISIS_YEARS:
        return 1.0
    return target_gbp_mwh(year, solar_gw, path) / shao_mean
