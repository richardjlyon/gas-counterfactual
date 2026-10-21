"""Layer 3 (goods): CfD, RO and FiT costs on business electricity, passed through per household."""
import pytest

from gascf import goods
from gascf.goods import (PASS_THROUGH, PASS_THROUGH_LABEL, PASS_THROUGH_QUOTE, PASS_THROUGH_SOURCE,
                         UK_SOLD_QUOTE, UK_SOLD_SHARE, UK_SOLD_SOURCE, SchemeYear, split)


@pytest.fixture(scope="module")
def cfd():
    return goods.read_cfd()


@pytest.fixture(scope="module")
def rows():
    return goods.layer3()


# ---- spot values, as printed in the stored source files (read 10 Oct 2026) -------------------

def test_ro_reports_read_at_source():
    r = goods.read_ro_report(2024)        # RO annual report SY23, supply/obligation table
    assert r["supply_uk"] == 247_852_713 and r["rocs_uk"] == 119_526_379
    assert r["rocs_ew"] == 107_608_506 and r["rocs_sc"] == 10_524_875
    assert r["eii_excluded_gb"] == 11_983_131
    r = goods.read_ro_report(2016)        # 2016-17: no EII exemption yet
    assert r["rocs_uk"] == 100_748_885 and r["supply_ew"] == 260_077_848
    assert r["eii_excluded_gb"] == 0
    assert goods.read_ro_report(2019)["eii_excluded_gb"] == 8_966_043.9


def test_ro_obligation_matches_ofgem_notice():
    """Annual report obligation equals Ofgem's separate total-obligation notice (2018-19..2024-25)."""
    import re
    for fy in range(2018, 2025):
        t = goods._html_text(goods.OFG / f"RO_total_obligation_{goods.fy_label(fy)}.html")
        ew = int(re.search(r"([\d,]+) ROCs in England and Wales", t).group(1).replace(",", ""))
        assert abs(goods.read_ro_report(fy)["rocs_ew"] - ew) <= 1, fy


def test_ro_buyout_prices():
    bo = goods.read_ro_buyout()
    assert bo[2015] == 44.33 and bo[2023] == 59.01 and bo[2024] == 64.73
    assert sorted(bo) == list(range(2009, 2025))


def test_ro_cost_is_gb_rocs_times_buyout():
    ro = goods.read_ro()[2024]
    assert ro.cost_gbp == pytest.approx((107_608_506 + 10_524_875) * 64.73)
    assert ro.basis == "modelled"


def test_fit_read_at_source():
    f = goods.read_fit_year(2022)          # 2022-23 levelisation notice
    assert f["fund"] == 1_452_953_030.365 and f["relevant"] == 231_809_252.605
    assert f["green"] == 14_380_210.614 and f["eii"] == 9_660_605.031
    f = goods.read_fit_year(2024)          # SY15 annual report
    assert f["fund"] == 1_725_741_218 and f["relevant"] == 240_978_492
    assert goods.read_fit_year(2015)["relevant"] is None      # notice prints no volumes


def test_fit_volume_identity():
    """Ofgem's own arithmetic: supply + additions - green cap - EII claimed = relevant supply."""
    for fy in range(2016, 2025):
        f = goods.read_fit_year(fy)
        if fy == 2021:
            # Ofgem's 2021-22 notice: the printed relevant supply omits the stated 2,704,849.299 MWh
            # "further addition" for exited suppliers (or it is already inside the supply figure).
            # We use the printed relevant supply; the inconsistency is logged in GAPS.
            assert f["supply"] - f["green"] - f["eii"] == pytest.approx(f["relevant"], abs=1)
            continue
        assert f["supply"] + f["extra"] - f["green"] - f["eii"] == pytest.approx(f["relevant"], abs=1), fy


def test_fit_2015_is_unsourced(rows):
    r = next(r for r in rows if r["scheme"] == "FiT" and r["period"] == "2015-16")
    assert r["basis"] == goods.UNSOURCED and r["per_household"] == goods.UNSOURCED


def test_cfd_complete_years_only(cfd):
    assert 2015 in cfd and 2025 in cfd and 2026 not in cfd
    assert cfd[2015].cost_gbp == 0           # levy rate zero before the first CfD payments


def test_cfd_reconciled_against_interim_invoiced(cfd):
    """Reconciled levy and the interim levy invoiced are separate LCCC series (review N4: the old
    test was a 10% band over 8 summed years). Pinned per year, £m, both read 10 Oct 2026: the
    gap is the reconciliation, and it is largest in the crisis years (2021-23) when wholesale
    prices moved far from LCCC's forecast."""
    ilr = goods.read_ilr()
    want = {2017: (544.0, 594.2), 2018: (980.0, 984.2), 2020: (2268.1, 2247.6),
            2021: (289.3, 762.2), 2022: (9.5, 145.1), 2024: (2238.1, 2569.3)}
    for y, (rec, inv) in want.items():
        assert cfd[y].cost_gbp / 1e6 == pytest.approx(rec, abs=0.05), y
        assert ilr[y] / 1e6 == pytest.approx(inv, abs=0.05), y


def test_cfd_interim_runs_noted(cfd):
    """Review N5: 2025/26 is mostly interim runs; the row says so."""
    assert dict(cfd[2025].run_days) == {"R1": 20, "R2": 101, "R3": 196, "RF": 48}
    assert "317 of 365 days from interim runs" in cfd[2025].note
    assert "interim" not in cfd[2024].note
    assert set(dict(cfd[2024].run_days)) <= goods.FINAL_RUNS


def test_cfd_outturn_by_cap_period():
    """Review B2: LCCC outturn beside Ofgem's allowance (values in review B2's table)."""
    from datetime import date
    want = {(date(2021, 10, 1), date(2022, 3, 31)): -1.83, (date(2022, 10, 1), date(2022, 12, 31)): 1.59,
            (date(2023, 1, 1), date(2023, 3, 31)): 3.07, (date(2023, 4, 1), date(2023, 6, 30)): 4.17}
    for (a, b), v in want.items():
        o = goods.cfd_outturn(a, b)
        assert o["gbp_mwh"] == pytest.approx(v, abs=0.005), a
        assert o["days"] == (b - a).days + 1 and o["basis"] == "measured"
    # independent arithmetic from the raw file for one quarter
    import csv
    num = den = 0.0
    with open(goods.LCCC / "reconciled_daily_levy_rates.csv") as fh:
        for x in csv.DictReader(fh):
            if x["Latest_Flag"] == "Latest Settlement Run" and "2023-04-01" <= x["Settlement_Date"][:10] <= "2023-06-30":
                num += float(x["Reconciled_Daily_Levy_Rate_GBP_Per_MWh"]) * float(x["Reconciled_Eligible_Demand_MWh"])
                den += float(x["Reconciled_Eligible_Demand_MWh"])
    assert goods.cfd_outturn(date(2023, 4, 1), date(2023, 6, 30))["gbp_mwh"] == pytest.approx(num / den)
    # a future period has no outturn
    assert goods.cfd_outturn(date(2026, 10, 1), date(2026, 12, 31)) is None
    # interim-run days make the period `estimated`
    assert goods.cfd_outturn(date(2025, 10, 1), date(2025, 12, 31))["basis"] == "estimated"


def test_one_domestic_share_and_household_count():
    """Review S3: goods uses system_costs' domestic share and taxes' household count."""
    from gascf import system_costs as sc, taxes
    assert goods.domestic_share_cy is sc.domestic_share_cy
    assert goods.gb_households_fy is taxes.gb_households_fy is sc.gb_households_fy
    assert not hasattr(goods, "gb_households_cy")


def test_dukes_domestic_share():
    d = goods.domestic_share_cy()
    # DUKES 2026 T5.2 Domestic PDS 2025 = 92,812.3256 GWh; T5.5.D UK sales 2025 = 253,961.5553 GWh
    assert d[2025] == pytest.approx(92812.3256 / 253961.5553)
    assert all(0.3 < v < 0.45 for v in d.values())


def test_gb_households(rows):
    from gascf import system_costs as sc
    r = next(r for r in rows if r["scheme"] == "CfD" and r["period"] == "2023-24")
    a, _ = sc.gb_households(2023)
    b, _ = sc.gb_households(2024)
    assert r["gb_households"] == pytest.approx(0.75 * a + 0.25 * b)
    assert a == pytest.approx(27_630_000, abs=1)              # ONS LFS, England + Wales + Scotland (s30)


# ---- identities ------------------------------------------------------------------------------

def test_cfd_domestic_plus_business_reconciles_to_lccc_total(cfd, rows):
    for r in (r for r in rows if r["scheme"] == "CfD"):
        assert r["domestic_gbp"] + r["business_gbp"] == pytest.approx(cfd[r["fy"]].cost_gbp, abs=0.01)
    # and the LCCC total itself is rate x eligible demand summed from the daily file
    import csv
    tot = 0.0
    with open(goods.LCCC / "reconciled_daily_levy_rates.csv") as fh:
        for x in csv.DictReader(fh):
            if x["Latest_Flag"] == "Latest Settlement Run" and x["Settlement_Date"][:10] >= "2024-04-01" \
                    and x["Settlement_Date"][:10] < "2025-04-01":
                tot += float(x["Reconciled_Daily_Levy_Rate_GBP_Per_MWh"]) * float(x["Reconciled_Eligible_Demand_MWh"])
    assert cfd[2024].cost_gbp == pytest.approx(tot)


def test_every_scheme_splits_exactly(rows):
    for r in rows:
        if r["scheme"] in ("CfD", "RO", "FiT") and r.get("cost_basis"):
            assert r["domestic_gbp"] + r["business_gbp"] == pytest.approx(r["cost_gbp"])


def test_exemption_lands_on_business():
    """With no exemption, households pay share d; an exempt volume raises the unit rate on
    everyone else, so the domestic £ rises and business £ falls by the same amount."""
    base = SchemeYear("X", 2024, 1000.0, 100.0, 0.0, "measured", "t")
    ex = SchemeYear("X", 2024, 1000.0, 90.0, 10.0, "measured", "t")
    assert split(base, 0.4) == pytest.approx((400.0, 600.0))
    dom, bus = split(ex, 0.4)
    assert dom == pytest.approx(1000 * 0.4 * 100 / 90) and dom + bus == pytest.approx(1000)


def test_pass_through_convention(rows):
    assert PASS_THROUGH == {"low": 0.33, "central": 0.5, "high": 0.8} and UK_SOLD_SHARE == 0.70
    for r in rows:
        if "passed_through" in r:
            assert r["pass_through_label"] == PASS_THROUGH_LABEL
            p = r["passed_through"]
            assert p["low"] <= p["central"] <= p["high"] == pytest.approx(0.8 * 0.7 * r["business_per_household"])


def test_totals_sum_and_tags(rows):
    for t in (r for r in rows if r["scheme"] == "total"):
        parts = [r for r in rows if r.get("fy") == t["fy"] and r["scheme"] in ("CfD", "RO", "FiT")]
        assert len(parts) == 3
        assert t["business_gbp"] == pytest.approx(sum(r["business_gbp"] for r in parts))
    for r in rows:
        assert r["basis"] in ("measured", "modelled", "estimated", goods.UNSOURCED) and r["source_id"]


def test_passed_through_is_estimated(rows):
    """Review S4: the pass-through rate has no UK consumer-price source, so every row's
    passed-through figure is `estimated`; only the pre-pass-through business £ may be `modelled`."""
    n = 0
    for r in rows:
        if "passed_through" in r:
            assert r["passed_through_basis"] == "estimated" and r["basis"] == "estimated"
            assert r["business_basis"] in ("modelled", "estimated")
            n += 1
    assert n > 20


def test_spot_2024_25(rows):
    """Regression values (work/s9-fix-wave1/notes.md), £/GB household/yr."""
    t = next(r for r in rows if r["scheme"] == "total" and r["period"] == "2024-25")
    assert t["business_per_household"] == pytest.approx(256.05, abs=0.01)   # s30: one GB count (LFS)
    assert t["passed_through"]["central"] == pytest.approx(89.62, abs=0.01)   # s30
    assert t["basis"] == "estimated"
    t = next(r for r in rows if r["scheme"] == "total" and r["period"] == "2022-23")
    assert t["business_per_household"] == pytest.approx(173.41, abs=0.01)   # s30
    assert t["business_basis"] == "modelled"


def test_layout_guard(tmp_path):
    bad = tmp_path / "x.csv"
    bad.write_text("Settlement_Date,Rate\n2024-04-01,1\n")
    with pytest.raises(ValueError):
        goods.read_cfd(bad)


def _stored_text(rel):
    import html as h
    import re
    from pathlib import Path
    import pymupdf
    f = Path(__file__).parents[1] / rel
    if f.suffix == ".pdf":
        t = " ".join(p.get_text() for p in pymupdf.open(f))
    else:
        t = re.sub("<[^>]+>", " ", h.unescape(f.read_text(errors="ignore")))
    return re.sub(r"\s+", " ", t.replace("\xad", "")).replace("\u2019", "'")


def test_pass_through_quotes_are_in_the_sources():
    assert PASS_THROUGH_QUOTE in _stored_text(PASS_THROUGH_SOURCE)
    assert UK_SOLD_QUOTE in _stored_text(UK_SOLD_SOURCE)


def test_passed_through_applies_rate_and_exports(rows):
    for r in rows:
        if "passed_through" in r and isinstance(r.get("business_per_household"), float):
            assert r["passed_through"]["central"] == pytest.approx(0.5 * 0.7 * r["business_per_household"])
