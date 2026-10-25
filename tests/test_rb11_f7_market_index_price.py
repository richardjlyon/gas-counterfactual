"""RB v1.1 F7 (decision 0163, R25 (a), Richard Lyon 21 Oct 2026: "Agree. Next."): Elexon's market index price
(MID, APX rows; free, already held by the engine as data/raw/elexon/MID_APX_YYYY.csv) beside each of the two worked
2024 half-hours, named as what it is: "Elexon market index price", never "day-ahead".

Expected values are the analyst's own reading of Elexon's API, saved separately (outside-data-survey.md, card
[internal ticket]; files elexon-bmrs-mid-2024-01-15.json and -2024-08-15.json): 15 Jan 2024 SP 25 = 78.10 and
15 Aug 2024 SP 21 = 18.86 £/MWh, cash."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _run(peak=("2024-01-15", 25), median=("2024-08-15", 21), mid=(78.1, 18.86)):
    from gascf import fossil_like_for_like as L
    wh = {}
    for p, (d, sp), m in (("peak", peak, mid[0]), ("median", median, mid[1])):
        wh[p] = {"date": d, "sp": sp, "residual_mw": 1000.0, "raw_step_gbp_mwh": 1.0, "scaled_step_gbp_mwh": 1.0,
                 "p0_gbp_mwh": 1.0, "p1_gbp_mwh": 2.0, "rb_cost_gbp_mwh": 2.0, "top_block": "ccgt",
                 "market_index_price_gbp_mwh": m}
    assert L is not None
    return {"fleet": {"2024": {"worked_hh": wh}, "2022": {}}}


def test_engine_reads_the_market_index_price_for_the_worked_half_hours():
    """The engine's MID reader gives the analyst's two values for the two worked half-hours (APX rows)."""
    from gascf import fossil_like_for_like as L
    assert L.market_index_price("2024-01-15", 25) == pytest.approx(78.10, abs=0.005)
    assert L.market_index_price("2024-08-15", 21) == pytest.approx(18.86, abs=0.005)
    assert L.market_index_price("2015-06-01", 10) is None        # no MID held before 2018: None, never a filled value


def test_worked_hh_entry_carries_the_market_index_price():
    from datetime import date
    from gascf import fossil_like_for_like as L
    cap = [(44478.5, date(2024, 1, 15), 25, 124.4, 54.7, 179.1, "new_ocgt"),
           (22007.0, date(2024, 8, 15), 21, 27.3, 34.9, 62.2, "ccgt"),
           (100.0, date(2024, 3, 1), 1, 0.0, 1.0, 1.0, "ccgt")]
    wh = L._worked_hh(cap, (1.0, 0.0))
    assert wh["peak"]["market_index_price_gbp_mwh"] == pytest.approx(78.10, abs=0.005)
    assert wh["median"]["market_index_price_gbp_mwh"] == pytest.approx(18.86, abs=0.005)


def test_keys_beside_each_worked_half_hour_named_as_what_they_are():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.figures_keys import worked_hh as K
    v = K.values(_run())
    assert v["wh_peak_market_index_price_gbp_mwh"] == 78.1
    assert v["wh_median_market_index_price_gbp_mwh"] == 18.86
    for p in ("peak", "median"):
        m = K.DECLARED[f"wh_{p}_market_index_price_gbp_mwh"]
        assert "Elexon market index price" in m["label"]
        assert "day-ahead" not in m["label"].lower()
        assert m["units"] == "£/MWh, cash" and m["basis"] == "measured" and m["print"] is True
        assert "MID_APX_2024.csv" in m["run_field"] or "MID" in m["run_field"]


def test_key_is_none_when_the_run_has_no_market_index_price():
    from tools.figures_keys import worked_hh as K
    run = _run()
    for p in ("peak", "median"):
        del run["fleet"]["2024"]["worked_hh"][p]["market_index_price_gbp_mwh"]
    v = K.values(run)
    assert v["wh_peak_market_index_price_gbp_mwh"] is None and v["wh_median_market_index_price_gbp_mwh"] is None
