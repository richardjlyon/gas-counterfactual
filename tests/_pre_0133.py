"""The margin as it was before decision 0133, for the guards that reproduce a frozen earlier release.

Decision 0133 (Richard Lyon, 20 Oct 2026, "a") moved the margin's denominator from the 2030/31 Base Case peak
(64.2 GW) to the 2027/28 one (61 GW). The tests that prove a code path still equals a frozen release cut before
0133 (v4-s35) run inside `pre_0133_margin()`, so they keep proving that nothing else moved. The 0133 move itself is
pinned in tests/test_margin_0133.py.

Every cache whose result depends on the margin is cleared on the way in and on the way out, so no build made on
the old margin is left for another test to read.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from gascf import capacity

PRE_0133 = {"delivery_year": "2030/31", "value_gw": 64.2}     # ECR 2026 workbook Figure B1, Base Case 2026, 2030/31


def margin_caches() -> list:
    from gascf import bills as B
    from gascf import fossil_like_for_like as LFL
    from gascf import staircase as ST
    return [B.fleet, B.fleet_lfl, B.build, B.ranges, LFL.lfl_year, ST._fleet_kit]


def _clear() -> None:
    for f in margin_caches():
        f.cache_clear()


@contextmanager
def pre_0133_margin():
    _clear()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(capacity, "MARGIN_DELIVERY_YEAR", PRE_0133["delivery_year"])
        mp.setitem(capacity.MARGIN_PEAK, "delivery_year", PRE_0133["delivery_year"])
        mp.setitem(capacity.MARGIN_PEAK, "value_gw", PRE_0133["value_gw"])
        try:
            yield
        finally:
            _clear()
    _clear()


# ----------------------------------------------------------------------------- decision 0144 (v4-s37)

PRE_0144_REGISTER = Path(__file__).parent / "fixtures/fossil_closures_pre_0144.yaml"   # = 36c9745 (v4-s36)


@contextmanager
def pre_0144():
    """The engine as it was before decision 0144 (Richard Lyon, 20 Oct 2026), for the guards that reproduce a frozen
    release cut before it: extra running at cost (1A's 'cost', the v4-s36 mix), the gas-price feedback on the
    supply-only central 0.16 (2A), and, where the guard reads the real register, the v4-s36 register (Cottam
    net_zero_policy, kept open; item 6). The 0144 moves themselves are pinned in tests/test_s37_0144.py."""
    import os
    from dataclasses import replace

    from gascf import bills as B
    from gascf import fossil_like_for_like as LFL
    _clear()
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(LFL.GAS_ELASTICITY_PAIRS, "central", (0.16, 0.0))
        mp.setitem(LFL.GAS_ELASTICITY, "central", 0.16)
        mp.setattr(B, "CENTRAL", replace(B.CENTRAL, extra_running="cost"))
        if os.environ.get(LFL.CLOSURES_ENV) == str(LFL.CLOSURES_FILE):
            mp.setenv(LFL.CLOSURES_ENV, str(PRE_0144_REGISTER))
        try:
            yield
        finally:
            _clear()
    _clear()


@contextmanager
def pre_s37():
    """Both moves since v4-s35's cut: the margin (0133) and decision 0144."""
    with pre_0133_margin(), pre_0144():
        yield
