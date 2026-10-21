"""Ticket 13 (0061): the early-years calibration check judged pooled over 2002-04 (spec calibration-pooled.md).

D1: sum over sum, national £m, 2025 money. For y in EARLY_YEARS, D = Σ (gap(y) - L(y)) x H(y), N = Σ L(y) x H(y);
pooled £ a household = D / Σ H (the household-weighted mean), pooled % = |D| / |N|. Not the mean of the yearly
percentages."""
from __future__ import annotations

EARLY_YEARS = (2002, 2003, 2004)
EARLY_TOL_GBP = 25.0           # within £25 a household, 2025 money (unchanged, s22)
EARLY_TOL_FRAC = 0.30          # within 30% of the net-zero-only lines (unchanged, s22)


def early_years_check(rows: list[dict]) -> dict:
    """rows: per year {"year", "gap_hh", "lines_hh", "households"} (£ a household, 2025 money). Years outside
    EARLY_YEARS are ignored (D2: 2005 is not included)."""
    rows = [r for r in rows if r["year"] in EARLY_YEARS]
    d = sum((r["gap_hh"] - r["lines_hh"]) * r["households"] for r in rows)
    n = sum(r["lines_hh"] * r["households"] for r in rows)
    h = sum(r["households"] for r in rows)
    pooled = {"diff_m": d / 1e6, "lines_m": n / 1e6, "diff_hh": d / h, "lines_hh": n / h, "pct": abs(d) / abs(n) * 100}
    pooled["pass_gbp"] = abs(d / h) <= EARLY_TOL_GBP
    pooled["pass_pct"] = abs(d) <= EARLY_TOL_FRAC * abs(n)
    per_year = []
    for r in sorted(rows, key=lambda r: r["year"]):
        diff = r["gap_hh"] - r["lines_hh"]
        per_year.append({"year": r["year"], "diff_hh": diff, "lines_hh": r["lines_hh"],
                         "pct": abs(diff) / abs(r["lines_hh"]) * 100, "pass_gbp": abs(diff) <= EARLY_TOL_GBP,
                         "pass_pct": abs(diff) <= EARLY_TOL_FRAC * abs(r["lines_hh"])})
    # D4: per-year figures are printed, never asserted (0061)
    for p in per_year:
        print(f"early years {p['year']}: difference {p['diff_hh']:.2f} / lines {p['lines_hh']:.2f} £ a household, "
              f"{p['pct']:.1f}% (within £25: {p['pass_gbp']}, within 30%: {p['pass_pct']})")
    print(f"early years 2002-04 pooled: difference {pooled['diff_hh']:.2f} / lines {pooled['lines_hh']:.2f} £ a household, "
          f"{pooled['pct']:.1f}%")
    return {"pooled": pooled, "per_year": per_year, "passed": pooled["pass_gbp"] and pooled["pass_pct"]}


DISCLOSURE_0111 = ("Decision 0111 (Richard Lyon, 19 Oct 2026, item 1.3): the check keeps the net-zero-only lines as "
                   "netted under 0097 and is not re-pinned. 0097's netting takes about £647m (2025 prices) out of the "
                   "lines over 2002-04, so the pooled figure exceeds the 30% limit; the difference itself is "
                   "unchanged and the headline is unaffected. Stated in the paper's §5.")


def nz_only_lines(b: dict) -> float:
    """Net-zero-only lines, £m nominal: subsidies + carbon + CCL + extra backup + grid and balancing extras + schemes
    + VAT on them (the s22 calibration definition, as tests/test_fossil_like_for_like.py)."""
    from gascf import bills as B
    v = lambda i: B.val(b, i)                          # noqa: E731
    nz4b = v("NZ4b") if any(l["id"] == "NZ4b" for l in b["netzero"]) else 0.0
    return (v("NZ2") + v("NZ3") + v("NZ4") + nz4b + v("NZ1c") + v("NZ5") + v("NZ8") + v("NZ10") + (v("NZ11") - v("GO7"))
            + (v("NZ6") - v("GO4")) + (v("NZ7") - v("GO5")))


def build_block(built: dict) -> dict:
    """Run file tests.calibration_early (spec calibration-pooled.md D6), with the 0111 disclosure."""
    from gascf import bills as B
    rows = [{"year": y, "gap_hh": built[y]["totals"]["gap_per_hh_real"],
             "lines_hh": B.real(nz_only_lines(built[y]), y) * 1e6 / built[y]["households"],
             "households": built[y]["households"]} for y in EARLY_YEARS]
    r = early_years_check(rows)
    return {**r, "limit_pct": EARLY_TOL_FRAC * 100, "limit_gbp_hh": EARLY_TOL_GBP, "money": "2025 prices",
            "decision": "0111", "disclosed_failure": not r["passed"], "note": DISCLOSURE_0111}
