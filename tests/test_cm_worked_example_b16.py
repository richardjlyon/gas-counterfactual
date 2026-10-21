"""Ticket 17, B16: the Capacity Market worked-example fields, `capacity_market[y].worked_example =
{peak_settlement_date, peak_settlement_period, residual_peak_mw, margin}`. Per the Editor-in-chief's
R-A1 ruling (option A, 17 Oct 16:18) the CM worked example reports the half-hour the fleet is sized on
(from 2016 under contracted interconnectors, the peak of residual + metered imports, 0065), not the
residual maximum that §4.3 uses (ticket 44). `peak_actual_fossil_mw` is not added (B16 point 1)."""
import datetime as dt

import pytest

from gascf import bills as B
from gascf import residual_neso as rn


def test_sizing_peak_reports_the_residual_at_the_sizing_halfhour():
    # R-A1 record (s35 inputs, contracted basis): 2024 sizing peak 18 Jan SP26, gross 46,076 MW,
    # residual 42,468 MW (draft2-new-keys-and-register-questions.md §a1 item 3)
    sp = B.sizing_peak(2024, rn.residual_neso_year(2024), "contracted")
    assert (sp["day"], sp["period"]) == (dt.date(2024, 1, 18), 26)
    assert sp["gross_peak_mw"] == pytest.approx(46076, abs=0.5)
    assert sp["residual_mw"] == pytest.approx(42468, abs=0.5)


def test_worked_example_reads_the_fleets_sizing_halfhour_and_margin():
    f = {"sizing_peak_halfhour": "2024-01-18 SP26", "sizing_peak_gross_gw": 46.076,
         "sizing_peak_residual_mw": 42468.0, "margin_fraction": 0.07}
    assert B.cm_worked_example(f) == {"peak_settlement_date": "2024-01-18", "peak_settlement_period": 26,
                                      "residual_peak_mw": 42468.0, "margin": 0.07}


# ---- heavy: the central build and the run-file block (run under the heavy lock) ----
CM_YEARS = range(2016, 2026)


@pytest.fixture(scope="module")
def central():
    return B.build()


def test_worked_example_traces_kept_at_peak_at_the_sizing_halfhour(central):
    """B16 tests 1-2 under R-A1 (A): the exported half-hour is the year's sizing peak, the maximum of
    residual + metered imports (0065, contracted from 2016), and kept_at_peak_gw × 1000 = nuclear
    (its CM obligation on calendar years, 0089 variant D, else metered) + pumped storage metered at
    that half-hour + imports counted (contracted), to 0.1 MW."""
    from gascf import cm_contracted as cmc
    nuc = cmc.nuclear_contracted_cy_mw("post_trade_less_suspended")
    ic = cmc.ic_contracted_cy_mw()
    for y in CM_YEARS:
        w = central[y]["cm"]["worked_example"]
        rows = rn.residual_neso_year(y)
        top = max(rows, key=lambda h: h.residual + h.imports)
        assert (w["peak_settlement_date"], w["peak_settlement_period"]) == (top.day.isoformat(), top.period), y
        assert w["residual_peak_mw"] == pytest.approx(top.residual, abs=0.1), y
        # the engine's central margin fraction: 4.5 GW over the 2027/28 peak of 61 GW (decision 0133; printed as
        # 7.4%; was 0.0700935 on the 2030/31 peak, ticket 15 record f7a7d04)
        assert w["margin"] == pytest.approx(4.5 / 61.0, abs=1e-7)
        want = nuc.get(y, top.nuclear) + top.ps_gen + ic.get(y, 0.0)
        assert central[y]["cm"]["split_gw"]["kept_at_peak_gw"] * 1000 == pytest.approx(want, abs=0.1), y


def test_run_file_capacity_market_block_carries_the_worked_example(central):
    from gascf import export_v4 as X
    out = X._cm(central)
    for y in CM_YEARS:
        if str(y) in out:
            assert out[str(y)]["worked_example"] == central[y]["cm"]["worked_example"]
    assert "2024" in out
