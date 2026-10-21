"""Ticket 21 (calendar part): UK ETS auction revenue by calendar year, 2021-25 (0055 as corrected 17 Oct 2026
16:36 BST, 0012, 0088, 0079). Spec: reports-programme s36-routeA-spec-items/ets-calendar-revenue-2021-25.md,
tests 1-7."""
from __future__ import annotations

import pytest

from gascf import ets_auctions as E


def test_ets_calendar_2022_includes_13_july(tmp_path):
    rev = E.ukets_revenue_cy()
    assert rev[2022]["gbp"] == 6_134_413_180 and rev[2022]["auctions"] == 25
    rows = [r for r in E.ukets_auction_rows() if r["date"] == "2022-07-13"]
    assert len(rows) == 1 and int(rows[0]["revenue_gbp"]) == 259_878_405
    lines = E.UKETS_2021_24.read_text().splitlines(keepends=True)
    fixture = tmp_path / "no-13-july.csv"
    fixture.write_text("".join(l for l in lines if not l.startswith("2022-07-13")))
    with pytest.raises(ValueError, match="2022"):
        E.ukets_revenue_cy(fixture, sha256=E._sha(fixture))


def test_ets_calendar_2021():
    rev = E.ukets_revenue_cy()
    assert rev[2021]["gbp"] == 4_310_021_495 and rev[2021]["auctions"] == 16
    (oct6,) = [r for r in E.ukets_auction_rows() if r["date"] == "2021-10-06"]
    assert int(oct6["allowances_sold"]) == 4_149_000                    # the one partial clearance


def test_ets_calendar_2023_is_not_fy2023_24():
    assert E.ukets_revenue_cy()[2023]["gbp"] == 4_202_870_715 != 3_407_068_000


def test_ets_calendar_2024_equals_the_printed_totals_row():
    assert E.ukets_revenue_cy()[2024]["gbp"] == 2_564_090_000


def test_every_row_re_adds_volume_times_price():
    for r in E.ukets_auction_rows():
        assert abs(int(r["allowances_sold"]) * float(r["clearing_price_gbp"]) - int(r["revenue_gbp"])) < 1, r["date"]


def test_each_auction_once_and_inside_its_year(tmp_path):
    lines = E.UKETS_2021_24.read_text().splitlines(keepends=True)
    i = next(k for k, l in enumerate(lines) if l.startswith("2022-07-13"))
    dup = tmp_path / "dup.csv"                     # 13 July twice in place of 27 July: 25 rows, one date twice
    dup.write_text("".join(lines[:i + 1] + [lines[i]] + lines[i + 2:]))
    with pytest.raises(ValueError, match="twice"):
        E.ukets_revenue_cy(dup, sha256=E._sha(dup))
    out = tmp_path / "outside.csv"                 # a 2022 scheme-year row dated in 2023
    out.write_text("".join(lines).replace("2022-12-14,2022,", "2023-01-04,2022,"))
    with pytest.raises(ValueError, match="outside"):
        E.ukets_revenue_cy(out, sha256=E._sha(out))


def test_ets_2025_from_the_2025_auctions_provisional():
    r = E.ukets_revenue_2025()
    assert r["gbp"] == 2_689_349_225 and r["auctions"] == 25 and r["allowances"] == 55_964_500
    assert r["status"] == "provisional" and "about 30 Nov 2026" in r["note"]
    assert r["gbp"] != 2_786_818_000                       # FY2025-26 Trust Statement (B5), not used


def _split():
    from gascf import carbon
    nz1c = {y: {"gbp_m": 5000.0, "basis": "modelled", "source_id": "toy-nz1c"} for y in range(2002, 2026)}
    return carbon.nz1c_split(nz1c)


def test_receipts_2021_25_from_calendar_revenue_and_no_year_reads_the_clock_column():
    from gascf import carbon
    r = carbon.ets_power_receipts()
    assert r[2021][0] == pytest.approx(4310.021495 * 0.428, abs=1e-6)
    assert r[2022][0] == pytest.approx(6134.413180 * 48_193_462 / 110_618_346, abs=1e-6)
    assert r[2023][0] == pytest.approx(4202.870715 * 36_084_695 / 96_750_817, abs=1e-6)
    assert r[2013][0] == pytest.approx(347.8 * E.power_share(2013)["value"], abs=1e-9)
    assert all("subsidy-clock-combined-annual" not in r[y][2] for y in range(2008, 2026))


def test_ets_power_2025p_is_provisional_and_gb_scaled():
    from gascf import deflator_cpih as d
    t = _split()[2025]["carbon_price_receipts"]
    assert t["ets_uk_gbp_m"] == pytest.approx(2689.349225 * 0.344307, abs=0.01)
    assert t["ets_gbp_m"] == pytest.approx(900.03, abs=0.01)              # x 0.9720 (GB 2024, nearest year)
    c = d.cpih()
    assert t["ets_gbp_m"] * c[2024] / c[2025] == pytest.approx(866.77, abs=0.01)
    assert t["ets_status"] == "provisional" and "about 30 Nov 2026" in t["ets_note"]


def test_carbon_crosscheck_note_no_longer_names_the_clock_column(monkeypatch):
    from gascf import export_v4 as X
    fake = {y: {"carbon_split": {"carbon_price_receipts": {"national_gbp_m_nominal": 1.0}}} for y in X.B.YEARS}
    monkeypatch.setattr(X.B, "val", lambda b, lid: 2.0)
    note = X._carbon_check(fake)["2022"]["collected_note"]
    assert "Subsidy Clock" not in note
    assert "ukets-auctions-2021-24.csv" in note and "0055" in note and "0079" in note and "0054" in note
