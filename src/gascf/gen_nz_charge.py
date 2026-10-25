"""Decision 0167 (Richard Lyon, 22 Oct 2026, "a"; card [internal ticket]): the generators' net-zero charge out of fossil
Britain's market price (WAY 2). Switch `bills.Settings.gen_nz_charge`, OFF by default.

The rule. Decision 0024 takes the generators' share of BSUoS and TNUoS out of both bills (NZ6/NZ7, GO4/GO5): in
real Britain the generators pass that charge on through the wholesale price, and fossil Britain is priced at the
actual market price, which carries the same charge, so it cancels out of the gap. 0167 counts the NET-ZERO part of
it as a cost of real Britain (with the generators' half of constraints and turn-up, which BSUoS recovers). Way 2
keeps both bills as they are and takes that part out of fossil Britain's market price instead:

  D(y)     = [NZ6 whole - NZ6 removed] - [GO4 whole - GO4 removed]      BSUoS: the generators' part real Britain paid,
           + [NZ7 whole - NZ7 removed] - [GO5 whole - GO5 removed]      less fossil Britain's own; the same for TNUoS
  delta(y) = D(y) / V(y)   £/MWh (£m / TWh), V = the power real Britain billed (the volume NZ1 prices)

`bills._build` takes delta(y) off every MWh fossil Britain buys at the market price (actual fossil output, extra
running at the market price, kept nuclear / imports / storage in GO1k) and off the station load it does not bill
at that price (0059). New plant priced at its own cost is not touched. Where a component's generators' share is
'included' in the bills (the pre-s27 line), that component is already counted there and is zero here.

Reading built here, for Richard to confirm: the charge per MWh spreads D over V (real Britain's billed power), so
if fossil Britain bought every MWh at the market price, way 2 would equal way 1 (`included` in both bills) before
VAT. The part fossil Britain buys from new plant at cost carries no deduction, so way 2 is smaller than way 1.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

OPTIONS = ("none", "fossil_price")
DEFAULT = "none"


def check(option: str) -> str:
    if option not in OPTIONS:
        raise ValueError(f"gen_nz_charge {option!r}: one of {OPTIONS}")
    return option


def net_zero_part(nz_whole: Mapping[int, float], nz_removed: Mapping[int, float],
                  go_whole: Mapping[int, float], go_removed: Mapping[int, float],
                  years: Iterable[int]) -> dict[int, float]:
    """£m by year: the generators' part of real Britain's charge less the generators' part of fossil Britain's."""
    return {y: (nz_whole[y] - nz_removed[y]) - (go_whole[y] - go_removed[y]) for y in years}


def series(bsuos: Mapping[int, float], tnuos: Mapping[int, float], v_twh: Mapping[int, float],
           years: Iterable[int]) -> dict[int, dict]:
    """{y: {bsuos_gbp_m, tnuos_gbp_m, gbp_m, v_twh, gbp_per_mwh}}; £m nominal, TWh, £/MWh nominal."""
    out = {}
    for y in years:
        v = v_twh[y]
        if not v > 0:
            raise ValueError(f"gen_nz_charge {y}: real Britain's billed power {v!r} TWh; the charge per MWh is undefined")
        d = bsuos[y] + tnuos[y]
        out[y] = {"bsuos_gbp_m": bsuos[y], "tnuos_gbp_m": tnuos[y], "gbp_m": d, "v_twh": v, "gbp_per_mwh": d / v}
    return out
