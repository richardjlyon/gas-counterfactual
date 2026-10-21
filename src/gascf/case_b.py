"""Run-file block `sensitivities_case_b` (ticket 22; spec item case-b-gas-export.md D1-D3; decisions 0029, 0034, 0048,
0095; built under decision 0117, Richard Lyon, 19 Oct 2026).

Case B is a plain second run with B's settings (0029), not a switchable block. The release run makes three extra
`bills.build()` calls with `Settings` replacements (the same replacements as the paper's
`numbers/exceptions_combined.py`) and records, for each case and every year:

- the engine's own gas-price feedback (`fleet[y].gas_feedback`): dq_twh, q_twh, elasticity, price_rise_frac;
- rise_at_e016 and rise_at_e006 = dq / (e x q), so the two quoted rises exist for every case;
- the case's gap, gap_real_bn (run money, £bn).

The central case is carried beside them from the central build, for the paper's comparison and spec test 2.
B's failed sign check is recorded openly (sign_check: passed, negative_years) and never stops the release (0034).
Case B never enters the printed range (0095). `bills.build` is cached on Settings, so `closures_actual` is the
methods-page build already made; the other two are new (spec D3: about 100 s each, cold)."""
from __future__ import annotations

from dataclasses import replace

from gascf import bills as B
from gascf.fossil_like_for_like import GAS_ELASTICITY

# Editor-in-chief ruling, 17 Oct 2026, 16:18 (ticket 22): the one source of the case B reason.
REJECTION = ("Rejected as the central case: 0.06 is a short-run supply elasticity (Krichene 2005, Table 5, used by "
             "Albrizio et al. over a 12-month horizon) applied to two decades of extra demand.")

CASES = {
    "closures_actual": replace(B.CENTRAL, closures="actual"),
    "closures_actual_e006": replace(B.CENTRAL, closures="actual", gas_feedback="high"),
    "case_b_all_three": replace(B.CENTRAL, closures="actual", gas_feedback="high", kept_price="actual"),
}
E_CENTRAL, E_HIGH = GAS_ELASTICITY["central"], GAS_ELASTICITY["high"]     # 0.16 and 0.06 (0033)
TOL = 1e-9


def _rows(name: str, run: dict) -> dict:
    out = {}
    for y in B.YEARS:
        g = run[y]["fleet"]["gas_feedback"]
        dq, q, e = g["dq_twh"], g["q_twh"], g["elasticity"]
        r16, r06 = dq / (E_CENTRAL * q), dq / (E_HIGH * q)
        if e is not None and abs(g["price_rise_frac"] - dq / (e * q)) > TOL:
            raise ValueError(f"case {name} {y}: engine price_rise_frac {g['price_rise_frac']!r} is not "
                             f"dq / (e q) = {dq / (e * q)!r} at its own elasticity {e}")
        out[str(y)] = {"dq_twh": dq, "q_twh": q, "elasticity": e, "price_rise_frac": g["price_rise_frac"],
                       "actual_power_gas_twh": g["actual_power_gas_twh"],
                       "fossil_power_gas_twh": g["fossil_power_gas_twh"],
                       "rise_at_e016": r16, "rise_at_e006": r06, "gap_real_bn": run[y]["totals"]["gap_real_bn"]}
    return out


def block(built: dict, build=None) -> dict:
    build = B.build if build is None else build
    runs = {"central": built, **{n: build(s) for n, s in CASES.items()}}
    cases = {n: _rows(n, r) for n, r in runs.items()}
    sign = {}
    for n in CASES:
        neg = sorted(int(y) for y, row in cases[n].items() if row["gap_real_bn"] < 0)
        sign[n] = {"passed": not neg, "negative_years": neg}
    return {"cases": cases, "sign_check": sign,
            "settings": {n: {"closures": s.closures, "gas_feedback": s.gas_feedback, "kept_price": s.kept_price}
                         for n, s in CASES.items()},
            "rejection": REJECTION, "in_range": False, "money": "gap_real_bn: run price base, £bn",
            "note": "dq_twh is the engine's: fossil Britain's gas burn for power less the actual (DUKES 5.6.A), "
                    "floored at 0. rise_at_e = dq / (e x q). Failed sign check recorded, never a stop (0034).",
            "decisions": ["0029", "0034", "0048", "0095", "0117"]}


from gascf import export_v4 as _X  # noqa: E402

_X.register_block("sensitivities_case_b", block)
