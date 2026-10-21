"""Interim-input check for the 0097 netting (ticket 26), run by the release suite.

Prints how far Reliable Britain's 2002-24 result (2024 £bn, CPIH L522) moves for each INTERIM_APPROVED EESoP input
across its stated range: spend ±10/20/30% and the electricity split at 50% (central 4,981 / 11,125 = 44.8%). A move
above £0.2bn prints a WARNING line. It prints only: it changes no figure and fails no test.

The NZ10 netting is linear in the level, and NZ10's VAT is charged in full (bills NZ11), so the move is the change
in the netted-off part x (1 + the domestic VAT rate), restated in 2024 £."""
from __future__ import annotations

from gascf import bills as B
from gascf import on_the_road as OTR
from gascf import same_in_both
from gascf.deflator_cpih import to_real

YEARS = range(2002, 2025)
THRESHOLD_BN = 0.2
EESOP_GBP_M_A_YEAR = 55.0
SHARE = 4981 / 11125


def _effect_bn(level: float) -> float:
    vat = same_in_both.domestic_vat_rate()["rate"]
    r = OTR.net({y: 0.0 for y in YEARS}, level, indexation=B.CENTRAL.otr_indexation,
                end_year=B.CENTRAL.otr_nz10_end_year, applies_to="NZ10")
    return -sum(to_real(r["netted"][y] * (1 + vat), y, 2024) for y in YEARS) / 1e3


def rows() -> list[dict]:
    central = _effect_bn(B.CENTRAL.otr_nz10_level_gbp_m)
    cases = [(f"spend {s:+d}%", EESOP_GBP_M_A_YEAR * (1 + s / 100) * SHARE)
             for p in (10, 20, 30) for s in (-p, p)]
    cases.append(("split 50%", EESOP_GBP_M_A_YEAR * 0.5))
    return [{"case": c, "level_gbp_m": lv, "move_bn": _effect_bn(lv) - central} for c, lv in cases]


def main() -> None:
    print("0097 interim inputs: move in RB 2002-24, 2024 £bn (EESoP spend £110m indicative; split 44.8% by energy saved)")
    for r in rows():
        print(f"  {r['case']:<12} level £{r['level_gbp_m']:.2f}m  move {r['move_bn']:+.3f}")
        if abs(r["move_bn"]) > THRESHOLD_BN:
            print(f"  WARNING: {r['case']} moves the result by {abs(r['move_bn']):.3f} £bn, above £{THRESHOLD_BN}bn")


if __name__ == "__main__":
    main()
