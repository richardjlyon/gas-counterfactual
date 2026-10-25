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
    with pre_s39(), pytest.MonkeyPatch.context() as mp:
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
    """Both moves since v4-s35's cut: the margin (0133) and decision 0144 (and so also the v4-s39 rulings)."""
    with pre_0133_margin(), pre_0144():
        yield


# ----------------------------------------------------------------------------- v4-s39 (card [internal ticket])

# The v4-s39 central's ruled settings, set back to v4-s38's, for guards that reproduce a frozen release cut before
# v4-s39 (decisions 0163, 0164, 0166, 0167, 0169). The environment readings go with them.
V4_S38 = dict(closure_test="register", kept_coal_pay="full", kept_filter_vom="added", coal_lf="dukes_max",
              moe_crisis="shao", gen_nz_charge="none", ro_mutualisation="off")
V4_S38_ENV = {"GASCF_M7_CARBON_MARGINAL": "gas", "GASCF_M8_HH_PRICE": "monthly", "GASCF_M8_SCOPE": "fossil",
              "GASCF_EDITION_MW": "none", "GASCF_IED_LCPD_KEPT": "off", "GASCF_M6_FEEDBACK": "floored"}


def s39_caches() -> list:
    from gascf import bills as B
    from gascf import closure_test as CT
    from gascf import fossil_like_for_like as LFL
    return [*margin_caches(), B.c_marg, CT._year_inputs, CT.station_margin, LFL.road_lf_closures]


@contextmanager
def pre_s39():
    """The engine as it was before the v4-s39 rulings: B.CENTRAL with V4_S38, the v4-s38 environment, and the two
    data readings v4-s39 replaced without a switch: the Clock copy (cf9b292e, kept in data/raw for reruns of v4-s38
    and earlier) and FiT scheme years 1-5 before C-008 (scheme value x the SY6 levelisation ratio, f85dc0f^)."""
    from dataclasses import replace

    from gascf import bills as B
    from gascf import bridge as R
    from gascf import subsidies as S

    lev_now, clock_now, clock_ts_now = S.read_fit_levelisation, R.read_clock, R.read_clock_published

    def lev_pre_c008():
        sv, lev = S.read_fit_scheme_value(), dict(lev_now())
        ratio = lev[2015][0] / sv[2015]
        lev.update({fy: (v * ratio, "estimated", f"{S.SRC_FIT}+{S.SRC_FIT_LEV}") for fy, v in sv.items()
                    if fy < 2015})
        return lev

    old = R.RAW / "subsidy_clock"

    def clear():
        for f in s39_caches():
            f.cache_clear()
        for f in (clock_now, clock_ts_now, lev_now):
            f.cache_clear()
    clear()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(B, "CENTRAL", replace(B.CENTRAL, **V4_S38))
        for k, v in V4_S38_ENV.items():
            mp.setenv(k, v)
        mp.setattr(S, "read_fit_levelisation", lev_pre_c008)
        # card [internal ticket]: since the register-read (0168, part A 1509fd6) the run reads FiT through S.fit_fy from the
        # shared cost register, which holds the C-008 reading; the pre-C-008 reading goes in at that seam too
        fit_fy_now = S.fit_fy
        mp.setattr(S, "fit_fy", lambda basis="levelisation": (dict(lev_pre_c008()) if basis == "levelisation"
                                                              else fit_fy_now(basis)))
        mp.setattr(R, "read_clock", lambda path=old / "s26b-combined-annual_cf9b292e.csv": clock_now(path))
        mp.setattr(R, "read_clock_published", lambda path=old / "s27b-timeseries_cf9b292e.json": clock_ts_now(path))
        try:
            yield
        finally:
            clear()
    clear()
