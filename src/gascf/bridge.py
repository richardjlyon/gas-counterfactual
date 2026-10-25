"""Bridge from the Subsidy Clock's annual figure to this site's gap (spec v4 §10.1), and the
Capacity Market correction to the Clock (§10.2).

Plain words: the Subsidy Clock adds up the support schemes and levies. This site asks a
different question (what would a fossil Britain have paid instead?), so the two numbers
differ. The bridge names every difference, row by row, so that the Clock's total plus the
rows equals this site's gap, to the penny, every year.

Money: national £m, **nominal (money of the year)**. The Clock's `cost` column (nominal) is
used, not `cost_real` (the Clock's real figures are in 2024 money; this site's in 2025
money), so no price-base row is needed. Row H (households) is therefore zero in £m: it is
named because the Clock's per-household figure divides every year by 29.0m (2025 count)
and this site divides by the year's own count; its per-household effect is reported
separately (`household_divisor_effect`).

Rows (spec §10.1, plus row J, which the spec table lacked but the identity needs; the old
row J, − EGL, is deleted, s30: no Treasury receipt is netted off):
A  Clock total (CfD, RO, FiT, constraints, constraint turn-up, TNUoS uplift, BSUoS uplift,
   CM, CCL & CPS, ETS), blanks as zero (the Clock's 2025 RO, FiT, CCL, ETS, TNUoS are blank)
B  − Clock CM + NZ5                         (the CM correction)
C  − Clock ETS − CPS part of the Clock's CCL + NZ1c
D  − Clock constraints − constraint turn-up (inside NZ6)
E  − Clock BSUoS uplift + (NZ6 − GO4)
F  − Clock TNUoS uplift + (NZ7 − GO5)
G  (NZ2 + NZ3 + NZ4) − Clock (RO + FiT + CfD): FY-to-start-year keying, RO rounding
H  0 in £m (household divisor; see above)
I  + step 1 (power before carbon; the avoided fossil fleet)
J  NZ8 − (Clock CCL − CPS): CCL electricity main rate, the Clock's rounding down to £0.1m
K  + NZ10: energy-saving schemes (EEC, CERT, CESP, ECO, GBIS), which the Clock does not count
   (spec §15.4 item 1, strand s24)
L  + (NZ11 − GO7): VAT on households' share of the extra (s30: taxes are a cost to the payer)
M  − the Clock's electricity CCL from 1 August 2015 (v4-s34; Richard, 14 Oct 2026, decision D2).
   From its 31 Oct release the Clock counts the levy only while renewable electricity was exempt
   (to 31 July 2015; Finance (No. 2) Act 2015 s.49). Row A is the stored live Clock, which still
   counts it, so M takes it out and row J, measured against the Clock's D2 CCL, puts the same
   amount back: this engine counts the whole levy (net zero's total cost). M + its share of J = 0,
   so the identity is unchanged; the two rows show the difference. 2015's split uses HMRC's
   2015's split is 7/12 to July (HMRC publishes no monthly electricity receipts; see
   subsidies.ccl_electricity_exempt_period), applied to the Clock's rounded CCL-less-CPS figure.

Rows G and J also carry the s30 move of the UK-only RO and CCL to GB (× GB share of consumption).
"""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

from gascf import bills as B
from gascf import waterfall as W
from gascf.subsidies import ccl_electricity_exempt_period

RAW = Path(__file__).parents[2] / "data/raw"
# Stored byte copies of the live Clock, GitHub master 35132e73 (files as served 21 Oct 2026, equal by sha256 to
# that commit's site/data), so the bridge does not move when the Clock's working tree does (review s25c).
# SHA-256 in data/raw/SHA256SUMS. v4-s39 (card [internal ticket]) replaced the stale cf9b292e copy (2026-10-10), which
# stays in data/raw for reruns of v4-s38 and earlier.
CLOCK = RAW / "subsidy_clock/s39-combined-annual_35132e73.csv"
CLOCK_TIMESERIES = RAW / "subsidy_clock/s39-timeseries_35132e73.json"
CLOCK_HOUSEHOLDS = 29_000_000          # subsidy-clock/reference/context.yaml 'households'
SRC_CLOCK = "subsidy-clock-combined-annual-2026-10-21"
SRC_CLOCK_TS = "subsidy-clock-timeseries-2026-10-21"
COLS = ("cfd_renewable", "constraints", "capacity_market", "ro", "fit", "ccl", "ets", "tnuos",
        "constraint_turnup", "bsuos")
ROWS = "ABCDEFGHIJKLM"
CLOCK_TOL_GBP_M = 0.01


@lru_cache(maxsize=None)
def read_clock(path: Path = CLOCK) -> dict[int, dict[str, float | None]]:
    """The Clock's annual nominal £ by scheme, converted to £m; blank cells → None."""
    with path.open(newline="") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    head = rows[0]
    if tuple(head[1:]) != COLS or head[0] != "year":
        raise ValueError(f"Clock combined-annual columns moved: {head}")
    return {int(r[0]): {c: (float(v) / 1e6 if v else None) for c, v in zip(head[1:], r[1:])}
            for r in rows[1:]}


@lru_cache(maxsize=None)
def read_clock_published(path: Path = CLOCK_TIMESERIES) -> dict:
    """The Clock's own published series (timeseries.json, same commit), £m nominal:
    {"schemes": {col: {year: £m}}, "total": {year: renewables perspective + indirect}}.
    The Clock's headline per year is the 'renewables' perspective (direct schemes) plus
    'indirect' (CCL, ETS, TNUoS and BSUoS uplifts)."""
    ts = json.loads(path.read_text())
    if set(ts["schemes"]) != set(COLS):
        raise ValueError(f"Clock timeseries schemes moved: {sorted(ts['schemes'])}")
    sch = {c: {d["year"]: d["cost"] / 1e6 for d in ts["schemes"][c]["annual"]} for c in COLS}
    direct = {d["year"]: d["cost"] / 1e6 for d in ts["perspectives"]["renewables"]["annual"]}
    ind = {d["year"]: d["cost"] / 1e6 for d in ts["indirect"]["annual"]}
    return {"schemes": sch, "total": {y: direct.get(y, 0.0) + ind.get(y, 0.0) for y in set(direct) | set(ind)}}


def clock_check(clock: dict[int, dict[str, float | None]] | None = None,
                published: dict | None = None, years=None) -> dict[int, dict]:
    """Check the bridge's Clock input against the Clock's own published series, every year:
    - each non-blank column equals the Clock's per-scheme annual figure (£0.01m);
    - each blank column has NO published figure for that year (a genuine blank, not a reader
      miss), and is listed in `blank` so the reader sees it;
    - row A (the column sum, blanks as zero) equals the Clock's published headline total.
    Returns {year: {"blank": [...], "mismatch": [(col, ours, published), ...],
    "total_ours", "total_published", "total_error", "ok"}}. Able to fail: any edit to either file,
    a column shift or a reader bug shows up as a mismatch."""
    clock = read_clock() if clock is None else clock
    pub = read_clock_published() if published is None else published
    out = {}
    for y in (years or B.YEARS):
        row = clock[y]
        blank = [c for c in COLS if row.get(c) is None]
        mism = []
        for c in COLS:
            p = pub["schemes"][c].get(y)
            if row.get(c) is None:
                if p not in (None, 0.0):
                    mism.append((c, None, p))
            elif p is None or abs(row[c] - p) > CLOCK_TOL_GBP_M:
                mism.append((c, row[c], p))
        tot = sum(v or 0.0 for v in row.values())
        tp = pub["total"].get(y)
        err = None if tp is None else tot - tp
        out[y] = {"blank": blank, "mismatch": mism, "total_ours": tot, "total_published": tp,
                  "total_error": err, "ok": not mism and err is not None and abs(err) < CLOCK_TOL_GBP_M}
    return out


def cps_part(y: int) -> float:
    """The CPS part of the Clock's CCL line, £m: CPS as the Clock builds it (no CPS in 2013), read from the shared
    cost register (0168: series CPS plus the input adjustment clock.CPS.not_counted_2013)."""
    from gascf import register_pin as RP
    return RP.register().line("CPS", "clock_live").get(y, 0.0) or 0.0


def clock_ccl_after_exemption(y: int, clock_ccl_less_cps: float) -> float:
    """The part of the Clock's electricity CCL (its CCL line less CPS, £m) from 1 August 2015,
    which the Clock stops counting at its 31 Oct release (D2): all of it after 2015, none before,
    and for 2015 the Aug-Dec 5/12 (D2's pro-rata fallback)."""
    from gascf import register_pin as RP
    if y < 2015:
        return 0.0
    if y > 2015:
        return clock_ccl_less_cps
    t = RP.register().series("CCL_ELEC")[y]
    return clock_ccl_less_cps * (1 - ccl_electricity_exempt_period([y])[y] / t)


def _v_opt(b: dict, lid: str) -> float:
    """A line's nominal £m, or 0 if the build does not carry it (e.g. NZ4b with cfd_split off)."""
    try:
        return B.val(b, lid) or 0.0
    except KeyError:
        return 0.0


def bridge_year(b: dict, y: int, clock: dict[str, float | None]) -> list[dict]:
    c = {k: (v or 0.0) for k, v in clock.items()}
    v = lambda i: B.val(b, i)                                    # noqa: E731
    step1 = W.STEPS[0][2](b)
    ccl_blank = clock.get("ccl") is None
    cps = 0.0 if ccl_blank else cps_part(y)
    post = 0.0 if ccl_blank else clock_ccl_after_exemption(y, c["ccl"] - cps)
    rows = [
        ("A", "Subsidy Clock total (blank schemes as zero)", sum(c.values())),
        ("B", "Capacity Market: drop the Clock's line, add NZ5 (the CM correction)",
         -c["capacity_market"] + v("NZ5")),
        ("C", "Carbon: drop the Clock's ETS and CPS, add carbon in the wholesale price (NZ1c)",
         -c["ets"] - cps + v("NZ1c")),
        ("D", "Constraints: inside BSUoS here, not added again", -c["constraints"] - c["constraint_turnup"]),
        ("E", "Running the grid: drop the Clock's BSUoS uplift, add NZ6 − GO4",
         -c["bsuos"] + v("NZ6") - v("GO4")),
        ("F", "High-voltage grid: drop the Clock's TNUoS uplift, add NZ7 − GO5",
         -c["tnuos"] + v("NZ7") - v("GO5")),
        ("G", "RO, FiT, CfD (incl. biomass CfD): calendar-year time weighting, unrounded, RO scaled UK to GB, "
              "FiT at levelisation cost",
         v("NZ2") + v("NZ3") + v("NZ4") + _v_opt(b, "NZ4b") - c["ro"] - c["fit"] - c["cfd_renewable"]),
        ("H", "Households: year-matched count (zero in £m)", 0.0),
        ("I", "Power before carbon: the avoided fossil fleet (waterfall step 1)", step1),
        ("J", "Climate Change Levy, electricity main rate: NZ8 (the whole levy, every year) against "
              "the CCL the Clock counts (to 31 July 2015 only, D2)",
         v("NZ8") - (c["ccl"] - cps - post)),
        ("K", "Energy-saving schemes on bills (NZ10): not in the Clock", v("NZ10")),
        ("L", "VAT on households' share of the extra (NZ11 − GO7): not in the Clock", v("NZ11") - v("GO7")),
        ("M", "Clock from its 31 Oct release (D2): electricity CCL from 1 August 2015 no longer counted "
              "(renewable power paid the levy too); counted here in row J", -post),
    ]
    H = b["households"]
    return [{"row": r, "label": lab, "gbp_m_nominal": val, "per_household_nominal": val * 1e6 / H}
            for r, lab, val in rows]


BRIDGE_LINES = {"NZ1", "NZ2", "NZ3", "NZ4", "NZ4b", "NZ5", "NZ6", "NZ7", "NZ8", "NZ10", "NZ11", "GO7",
                "GO1", "GO1k", "GO2", "GO3", "GO4", "GO5", "GO6"}   # NZ1, GO1, GO1k, GO2-3, GO6 via step 1


def unnamed_lines(b: dict) -> list[str]:
    """Bill lines (S1 excepted: same in both, they cancel) that no bridge row names. A new line
    added to either bill without a bridge row makes this non-empty, and the test fails."""
    ids = {l["id"] for side in ("netzero", "fossil") for l in b[side]}
    return sorted(i for i in ids if not i.startswith("S1.") and i not in BRIDGE_LINES)


def bridge(s: B.Settings = B.CENTRAL) -> dict[int, dict]:
    """{year: {"rows": [A..L], "sum": A+…+L, "gap": this site's gap, "error": sum − gap,
    "clock_total": A, "clock_check": `clock_check` for the year (blank columns flagged, every
    column and the total against the Clock's own published series), "unnamed_lines": bill lines
    the bridge does not name, "household_divisor_effect": Clock £/hh (29.0m) − A ÷ year's
    households}}. The gap is recomputed from the lines (net zero − fossil), not read from the
    build's totals. Years with no Clock row (none in 2002-2025 today) raise."""
    built, clock = B.build(s), read_clock()
    chk = clock_check(clock)
    out = {}
    for y in B.YEARS:
        if y not in clock:
            raise KeyError(f"Subsidy Clock has no {y} row")
        rows = bridge_year(built[y], y, clock[y])
        tot = sum(r["gbp_m_nominal"] for r in rows)
        b = built[y]
        gap = (sum(l["national_gbp_m_nominal"] or 0.0 for l in b["netzero"])
               - sum(l["national_gbp_m_nominal"] or 0.0 for l in b["fossil"]))
        a = rows[0]["gbp_m_nominal"]
        out[y] = {"rows": rows, "sum": tot, "gap": gap, "error": tot - gap, "clock_total": a,
                  "gap_totals_error": gap - b["totals"]["gap_gbp_m"],
                  "clock_blank": chk[y]["blank"], "clock_check": chk[y],
                  "unnamed_lines": unnamed_lines(b),
                  "household_divisor_effect": a * 1e6 / CLOCK_HOUSEHOLDS - a * 1e6 / b["households"],
                  "source_id": f"{SRC_CLOCK};{SRC_CLOCK_TS}"}
    return out


def clock_cm_correction(s: B.Settings = B.CENTRAL, clock_years=None) -> dict[int, dict]:
    """§10.2: per year, the Clock's CM line, this site's NZ5, and the correction (NZ5 − Clock CM),
    £m nominal and £ per household (Clock's 29.0m divisor). Drafted, not published (brief §3a).

    s32: only the years the engine models (2016-2025: the CM paid nothing before Oct 2016) carry
    a correction. Any later Clock year (2026, part-year) is reported with `status` 'not covered':
    the engine has no NZ5 for it, so the Clock's own CM stands there. `nz5_unfloored_gbp_m` is
    exported beside the (floored) NZ5; the low / high sides are the kept-coal and full-CM rules."""
    built, clock = B.build(s), read_clock()
    low, high = B.build(B.replace(s, cm_rule="extra_kept_coal")), B.build(B.replace(s, cm_rule="full"))
    out = {}
    for y in sorted(clock if clock_years is None else clock_years):
        cm = clock[y]["capacity_market"] or 0.0
        if y not in B.YEARS:
            out[y] = {"clock_cm_gbp_m": cm, "nz5_gbp_m": None, "correction_gbp_m": None,
                      "correction_per_household_clock": None,
                      "status": "not covered: the engine does not model this year (Clock CM stands)"}
            continue
        if not cm and not built[y]["cm"]["paid_gbp_m"]:
            continue                                        # no Capacity Market before Oct 2016
        nz5 = B.val(built[y], "NZ5")
        out[y] = {"clock_cm_gbp_m": cm, "nz5_gbp_m": nz5,
                  "nz5_unfloored_gbp_m": built[y]["cm"]["nz5_unfloored_gbp_m"],
                  "nz5_low_gbp_m": B.val(low[y], "NZ5"), "nz5_high_gbp_m": B.val(high[y], "NZ5"),
                  "correction_gbp_m": nz5 - cm,
                  "correction_per_household_clock": (nz5 - cm) * 1e6 / CLOCK_HOUSEHOLDS,
                  "status": "draft, for Richard's approval (spec §15.1 decision 4)"}
    return out
