"""Crisis-year merit-order uplift: the UCL sensitivity (s36 ticket 18; decisions 0069, 0086, 0087).

Shao et al. (2022) stays the central uplift in every year (0069). Under `Settings.moe_crisis =
"ucl_stmoe"` (a methods-page switch, not the range: the source is a preprint, not peer reviewed),
the 2021-23 Shao uplift is scaled so its time-mean equals target B (0086): O'Shea, Horne and Maslin
(2025) Table 4 Total MOE (the merit-order effect of wind), printed p.22 (PDF p.24), plus the engine's
own Shao solar part (2.98 £/MWh per GW of solar). Table 5 (long-run), printed p.25 (PDF p.27), is
carried in the data file for the record (0087); from RB v1.1 it is read only by the held rule 'ucl_ltmoe' (M10,
ruling R10), never by the central case or the range."""
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
# RB v1.1 M10 (decision 0160, card [internal ticket]): 'ucl_ltmoe' is the long-run rule beside the short-run one, built off by
# default and held for ruling R10 (bills.HELD_SWITCHES). It reads Table 5, which 0087 carried "for the record, not
# read by the build"; it is read only under this held rule, never by the central case or the range.
SCALED_RULES = {"ucl_stmoe": "stmoe_total_gbp_mwh",      # Table 4, printed p.22 (PDF p.24), 0086 target B
                "ucl_ltmoe": "ltmoe_gbp_mwh"}            # Table 5, printed p.25 (PDF p.27), M10
# Card [internal ticket] (MEASURE ONLY, default OFF): the M9 re-estimate (back-test [internal ticket], 4182bf7) as a switch.
# Richard Lyon, 21 Oct 2026, relayed on the card: "The number has to be accurate." He chooses A or B and Jan-Apr 2021.
M9_RULES = ("m9_ratio", "m9_ratio_mayon", "m9_direct", "m9_direct_mayon")
RULES = ("shao", "ucl_stmoe", "ucl_ltmoe") + M9_RULES   # rb-v4-s39-rc: M10 (rb-v1.1) and M9 ([internal ticket])
M9_LOG = ROOT / "data/derived/m9/run-20261021T160841Z.log"


@lru_cache(maxsize=None)
def m9_window(path: Path | None = None) -> dict:
    """The test window's (May 2021-Dec 2023) wind and solar coefficients and R, read from the back-test run log."""
    import re
    p = Path(path or M9_LOG)
    text = p.read_text()
    win = text[text.index("== TEST WINDOW"):]
    coef = {n: float(re.search(rf"^\s+{n}\s+(-?\d+\.\d+)\s+se", win, re.M).group(1)) for n in ("wind", "solar")}
    r = re.search(r"R = (\d+\.\d+), se [\d.]+, 95% interval \[(\d+\.\d+), (\d+\.\d+)\]", win)
    return {**coef, "R": float(r.group(1)), "R_lo": float(r.group(2)), "R_hi": float(r.group(3)),
            "log_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def k_months(rule: str, year: int, shao_mean: float, wind_gw: float, solar_gw: float) -> dict[int, float]:
    """Monthly scale on the hourly Shao uplift for the M9 rules ('shao' gives 1 everywhere).
    A ('m9_ratio'): x R. B ('m9_direct'): time-mean = -wind_coef x wind GW - solar_coef x solar GW, over the
    engine's own Shao mean (the year's means; for the '_mayon' variant the same annual k on May-Dec only).
    '_mayon': Jan-Apr 2021, outside the May 2021-Dec 2023 test window, keeps Shao."""
    if rule not in RULES:
        raise ValueError(f"moe_crisis {rule!r}: one of {RULES}")
    ones = {m: 1.0 for m in range(1, 13)}
    if rule not in M9_RULES or year not in CRISIS_YEARS:
        return ones
    w = m9_window()
    if rule.startswith("m9_ratio"):
        k = w["R"]
    else:
        k = (-w["wind"] * wind_gw - w["solar"] * solar_gw) / shao_mean
    out = {m: k for m in range(1, 13)}
    if rule.endswith("_mayon") and year == 2021:
        out.update({m: 1.0 for m in (1, 2, 3, 4)})
    return out


def target_gbp_mwh(year: int, solar_gw: float, path: Path | None = None, rule: str = "ucl_stmoe") -> float:
    """0086 target B: UCL Table 4 Total MOE (wind), printed p.22 (PDF p.24), plus the engine's own Shao
    solar part (Shao et al. 2022 Table 3 pooled solar term × the year's mean solar GW). rule 'ucl_ltmoe' (M10): the
    same construction with Table 5 Total MOE (wind, long-term model), printed p.25 (PDF p.27)."""
    from gascf.fossil_like_for_like import SHAO_SOLAR_POOLED
    return read(path)[SCALED_RULES[rule]]["values"][str(year)] - SHAO_SOLAR_POOLED * solar_gw


def k(year: int, shao_mean: float, solar_gw: float, path: Path | None = None, rule: str = "ucl_stmoe") -> float:
    """Scale on the hourly Shao uplift so its time-mean is the rule's target in 2021-23; 1 in every other year."""
    if year not in CRISIS_YEARS:
        return 1.0
    return target_gbp_mwh(year, solar_gw, path, rule) / shao_mean
