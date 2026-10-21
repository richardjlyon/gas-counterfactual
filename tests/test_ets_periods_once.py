"""s36 ticket 45: each UK carbon auction counted once in the ETS receipts (Clock audit error 1: the Jan-Mar 2024
auctions sat in both FY2023-24 and calendar 2024). Guards on top of 21's calendar revenue."""
import json
from datetime import date
from pathlib import Path

import pytest

from gascf import carbon
from gascf import ets_auctions as E

FIX = Path(__file__).parent / "fixtures/desnz_ukets_2024_table1_janmar.json"
# 2019 and 2020 on calendar years: decision 0110 (Richard Lyon, 19 Oct 2026, item 1.19: "the 2019-20 calendar
# basis that 0012 requires"). Values from research-model-items item 1: no UK auctions in calendar 2019; calendar
# 2020 = FY2019-20 GBP 201.4m (March 2020 auctions) + FY2020-21 GBP 2,213.1m, BEIS ARA 2020-21 Trust Statement.


def test_ets_revenue_periods_do_not_overlap():
    p = carbon.ets_revenue_periods()
    assert set(p) == set(range(2008, 2026))
    spans = sorted((v["period_start"], v["period_end"], y) for y, v in p.items())
    for (s0, e0, y0), (s1, e1, y1) in zip(spans, spans[1:]):
        assert e0 < s1, (y0, y1)
    for y, v in p.items():
        assert v["period_start"] <= v["period_end"], y
        assert date(y, 1, 1) <= v["period_start"] and v["period_end"] <= date(y, 12, 31), y
    assert p[2025]["provisional"] is True and not p[2024].get("provisional")


def test_jan_mar_2024_auctions_counted_once():
    fx = json.loads(FIX.read_text())
    assert E._sha(E.RAW / fx["report_file"]) == fx["report_sha256"]
    assert sum(v for _, v in fx["rows"]) == fx["total_gbp"] == 562_366_970
    rows = {r["date"]: int(r["revenue_gbp"]) for r in E.ukets_auction_rows()}
    for d, v in fx["rows"]:
        assert rows[d] == v, d
    p = carbon.ets_revenue_periods()
    for d, _ in fx["rows"]:
        dd = date.fromisoformat(d)
        assert p[2024]["period_start"] <= dd <= p[2024]["period_end"]
        assert not (p[2023]["period_start"] <= dd <= p[2023]["period_end"])
    rev = E.ukets_revenue_cy()
    assert rev[2024]["gbp"] == sum(v for d, v in rows.items() if d.startswith("2024"))
    assert rev[2023]["gbp"] == sum(v for d, v in rows.items() if d.startswith("2023"))


def test_ets_2023_is_calendar_2023():
    assert E.ukets_revenue_cy()[2023]["gbp"] == 4_202_870_715 != 3_407_068_000


def test_no_ets_year_reads_the_clock_column():
    r = carbon.ets_power_receipts()
    assert all(carbon.SRC_ETS_POWER not in r[y][2] for y in range(2009, 2026))
    assert carbon.SRC_ETS_POWER == "subsidy-clock-combined-annual-2026-10-10"


def test_split_identity_on_any_nz1c():
    nz1c = {y: {"gbp_m": 4000.0 + y, "basis": "modelled", "source_id": "toy"} for y in range(2002, 2026)}
    sp = carbon.nz1c_split(nz1c)
    for y in range(2002, 2026):
        t, p = sp[y]["carbon_price_receipts"], sp[y]["carbon_in_price"]
        assert t["gbp_m"] + p["gbp_m"] == pytest.approx(4000.0 + y, abs=1e-9), y


def test_run_file_carries_the_periods():
    import importlib

    from gascf import export_v4 as X
    importlib.import_module("gascf.carbon_blocks")
    b = X._BLOCKS["ets_auctions"]({})
    assert b["revenue_periods"]["2023"] == {"period_start": "2023-01-11", "period_end": "2023-12-13",
                                            "basis": "auction_dates"}
    assert b["revenue_periods"]["2019"]["basis"] == "calendar"
    assert b["revenue_periods"]["2025"]["provisional"] is True


def test_2019_20_revenue_on_calendar_years_0110():
    """0110 item 1.19: 2019 = 0 (UK auctions suspended Jan 2019 to Mar 2020); 2020 = 201.4 + 2,213.1 printed."""
    r = E.uk_revenue_2013_20()
    assert r[2019]["gbp_m"] == 0.0 and r[2019]["basis"] == "calendar"
    assert r[2020]["gbp_m"] == pytest.approx(201.4 + 2213.1, abs=1e-9) and r[2020]["basis"] == "calendar"
    for y in range(2013, 2019):                         # 2013-18 unchanged
        assert r[y]["basis"] == "calendar", y
    assert sum(r[y]["gbp_m"] for y in range(2013, 2019)) == pytest.approx(
        347.8 + 312.2 + 412.0 + 311.0 + 529.4 + 1421.8, abs=1e-9)
