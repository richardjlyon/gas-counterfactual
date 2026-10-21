"""Ticket 44 (B20), export half: the 2024 worked half-hours for the §4.3 example. The engine selects the peak
(largest residual) and the median (lower middle of the residual) half-hours and exports, for each, the raw and
Shao-scaled merit-order step, RB's marginal cost and the top running block. The figures keys (group D, key half)
read fleet[2024].worked_hh. Selection tested against the residual data itself; the s35 values are a reference,
not a quotable figure (final values from the release run 35), and are pinned so a drift is caught."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import pytest

from gascf import bills as B
from gascf import fossil_like_for_like as LFL
from gascf import residual_neso as rn


@pytest.fixture(scope="module")
def y24():
    return LFL.lfl_year(2024)


@pytest.fixture(scope="module")
def y24dbg():
    return LFL.lfl_year(2024, keep_hh=True)


@pytest.fixture(scope="module")
def y24c():
    return LFL.lfl_year(2024, ic_basis="contracted")


@pytest.fixture(scope="module")
def rows24():
    return rn.residual_neso_year(2024)


def test_worked_hh_peak_is_max_of_2024_residual_earliest_on_ties(y24, rows24):
    peak_res = max(r.residual for r in rows24)
    first = next(r for r in rows24 if r.residual == peak_res)
    wh = y24.worked_hh["peak"]
    assert wh["residual_mw"] == pytest.approx(peak_res, abs=1e-6)
    assert wh["date"] == first.day.isoformat() and wh["sp"] == first.period
    # s35 reference pin (not quotable): 15 Jan 2024 SP25, 44,478.5 MW
    assert wh["date"] == "2024-01-15" and wh["sp"] == 25
    assert wh["residual_mw"] == pytest.approx(44478.5, abs=0.1)


def test_worked_hh_median_is_lower_middle_earliest_on_ties(y24, rows24):
    asc = sorted(r.residual for r in rows24)
    med_res = asc[(len(asc) - 1) // 2]
    first = next(r for r in rows24 if r.residual == med_res)
    wh = y24.worked_hh["median"]
    assert wh["residual_mw"] == pytest.approx(med_res, abs=1e-6)
    assert wh["date"] == first.day.isoformat() and wh["sp"] == first.period
    # s35 reference pin (not quotable): 15 Aug 2024 SP21
    assert wh["date"] == "2024-08-15" and wh["sp"] == 21


def test_worked_hh_is_residual_peak_not_sizing_peak(y24c):
    """R-A1 option A (review R2-SP2a): on the contracted basis (the central/release basis) the fleet is sized on a
    different half-hour from the residual peak, so this test runs where the two genuinely differ, both drawn from
    the SAME run. The §4.3 worked peak is the residual peak (15 Jan 2024 SP25); the sizing peak is 18 Jan 2024
    SP26. Fails if the worked peak is silently pulled onto the sizing peak."""
    exp = y24c.worked_hh["peak"]
    sizing = (y24c.sizing["day"].isoformat(), y24c.sizing["period"])
    assert (exp["date"], exp["sp"]) == ("2024-01-15", 25)
    assert sizing == ("2024-01-18", 26)
    assert (exp["date"], exp["sp"]) != sizing


def test_worked_hh_scaled_step_is_raw_times_the_years_shao_factor(y24):
    mult, flat = LFL.moe_factor(y24, "shao")
    for k in ("peak", "median"):
        e = y24.worked_hh[k]
        assert e["scaled_step_gbp_mwh"] == pytest.approx(e["raw_step_gbp_mwh"] * mult + flat, abs=1e-9)


def test_worked_hh_raw_step_is_recomputed_from_the_chosen_half_hours_dispatch(y24dbg, rows24):
    """Not a restatement of the export: p0 and p1 are recomputed independently by walking that month's stack at the
    chosen half-hour's own loads (w0 = fossil output less hydro, w1 = served load less hydro), then the new-plant
    SRMC floor when the fleet is short, exactly as lfl_year does. Taking a different half-hour's loads (e.g. the
    next one, where the load crosses a block) would change the recomputed step and fail this."""
    dbg = y24dbg.hh_debug
    keys = tuple((r.day, r.period) for r in rows24)
    rtr, _ = LFL.renewables_trans_year(2024, keys)        # transmission-metered renewables, per half-hour
    H = LFL.hydro_year(2024, keys)                         # hydro, per half-hour
    A = y24dbg.existing_derated_mw                         # total de-rated existing (incl. kept) MW
    for name in ("peak", "median"):
        res = (max(r.residual for r in rows24) if name == "peak"
               else sorted(r.residual for r in rows24)[(len(rows24) - 1) // 2])
        i = next(k for k, r in enumerate(rows24) if r.residual == res)
        row = rows24[i]                                    # work out the loads from the residual row itself
        m = row.day.month
        L = max(0.0, row.residual)
        F = max(0.0, L - (rtr[i] + row.embedded))         # actual fossil output
        serv = min(L, max(A, F))                          # served load in fossil Britain
        short = L - serv
        w0, w1 = max(0.0, F - H[i]), max(0.0, serv - H[i])
        p0r = LFL._walk(dbg["stacks"][m], w0)[1]
        p1r = LFL._walk(dbg["stacks"][m], w1)[1]
        if short > 0:
            p1r = max(p1r, dbg["new_srmc"][m]["ocgt" if short > dbg["new_ccgt_mw"] + 1e-6 else "ccgt"])
        e = y24dbg.worked_hh[name]
        assert e["p0_gbp_mwh"] == pytest.approx(p0r, abs=1e-9)
        assert e["p1_gbp_mwh"] == pytest.approx(p1r, abs=1e-9)
        assert e["raw_step_gbp_mwh"] == pytest.approx(max(0.0, p1r - p0r), abs=1e-9)
        assert e["rb_cost_gbp_mwh"] == e["p1_gbp_mwh"]
        assert e["top_block"] in ("coal", "ccgt", "other_gas", "oil", "new_ccgt", "new_ocgt", None)


def test_worked_hh_raw_steps_reconcile_with_monthly_sums(y24dbg, rows24):
    """Every half-hour's raw step d (hh_cap) summed per month reconciles with the engine's own monthly model mean
    (moe_model_m x the month's count) and the yearly model mean, to 1e-6."""
    month_sum, month_n = defaultdict(float), defaultdict(int)
    for row in y24dbg.hh_cap:
        day, d = row[1], row[3]
        month_sum[day.month] += d
        month_n[day.month] += 1
    for m in range(1, 13):
        assert month_sum[m] == pytest.approx(y24dbg.moe_model_m[m] * month_n[m], abs=1e-6)
    total, n = sum(month_sum.values()), sum(month_n.values())
    assert total / n == pytest.approx(y24dbg.moe_model_mean, abs=1e-6)


def test_worked_hh_export_changes_no_other_fleet_field(monkeypatch):
    """Adding the worked_hh export changes no other run-file field: byte-compare the rest of the 2024 fleet block
    against the same block built with the worked_hh computation switched off."""
    import json
    from gascf import export_v4 as X

    def fleet_block():
        f = B.fleet_lfl(2024)
        built = {y: {"fleet": (f if y == 2024 else {})} for y in B.YEARS}
        return X._fleet(built)["2024"]

    on = fleet_block()
    monkeypatch.setattr(LFL, "_worked_hh", lambda *a, **k: None)
    LFL.lfl_year.cache_clear()
    B.fleet_lfl.cache_clear()
    off = fleet_block()
    LFL.lfl_year.cache_clear()
    B.fleet_lfl.cache_clear()
    rest_on = {k: v for k, v in on.items() if k != "worked_hh"}
    rest_off = {k: v for k, v in off.items() if k != "worked_hh"}
    assert json.dumps(rest_on, sort_keys=True, default=str) == json.dumps(rest_off, sort_keys=True, default=str)
    assert set(on["worked_hh"]) == {"peak", "median"} and off["worked_hh"] is None


def test_worked_hh_surfaced_in_the_built_fleet_export_block():
    """The run-file fleet block carries worked_hh, read from the built fleet (not grepped from source)."""
    from gascf import export_v4 as X
    f = B.fleet_lfl(2024)
    built = {y: {"fleet": (f if y == 2024 else {})} for y in B.YEARS}
    block = X._fleet(built)["2024"]
    assert block["worked_hh"] == f["worked_hh"]
    assert set(block["worked_hh"]) == {"peak", "median"}


def _c(res, day, sp, d=0.0, p0=0.0, p1=0.0, top=None):
    return (res, date(2024, 1, day), sp, d, p0, p1, top)


def test_worked_hh_peak_tie_picks_the_earlier():
    """Synthetic data with two equal maxima: the earlier half-hour (chronological cap order) is the peak."""
    cap = [_c(10, 1, 1), _c(30, 1, 2), _c(30, 1, 3), _c(20, 1, 4)]
    wh = LFL._worked_hh(cap, (1.0, 0.0))
    assert (wh["peak"]["date"], wh["peak"]["sp"]) == ("2024-01-01", 2)


def test_worked_hh_median_odd_length_is_true_middle_earliest_on_ties():
    """Odd-length synthetic data: median is the lower middle (rank (n-1)//2) of the residual sorted ascending;
    on tied values the earliest cap row with that residual wins."""
    cap = [_c(40, 1, 1), _c(20, 1, 2), _c(10, 1, 3), _c(20, 1, 4), _c(30, 1, 5)]   # asc [10,20,20,30,40], rank 2 -> 20
    wh = LFL._worked_hh(cap, (1.0, 0.0))
    assert (wh["median"]["date"], wh["median"]["sp"]) == ("2024-01-01", 2)


def test_worked_hh_applies_the_given_moe_factor_to_the_scaled_step():
    cap = [_c(10, 1, 1, d=5.0, p0=1.0, p1=6.0, top="ccgt")]
    wh = LFL._worked_hh(cap, (2.0, 3.0))
    assert wh["peak"]["scaled_step_gbp_mwh"] == pytest.approx(5.0 * 2.0 + 3.0)
    assert wh["peak"] == wh["median"]
