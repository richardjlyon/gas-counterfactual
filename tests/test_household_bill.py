"""s31: the typical household's bill in both Britains, in two pots (src/gascf/household_bill.py)."""
import pytest

from gascf import bills as B
from gascf import household_bill as HB
from gascf import receipt_actual as RA

YEARS = range(2019, 2026)


@pytest.fixture(scope="module")
def pots():
    return {y: HB.pots(y) for y in HB.POT_YEARS}


# ---------------------------------------------------------------- cap reproduction

def test_every_cap_period_reproduces_ofgem_within_a_pound():
    for r in RA.receipts():
        a, _ = RA.period_dates(r.period)
        if 2016 <= a.year <= 2025:
            assert abs(r.total - r.published_inc_vat) < 1.0, r.label


def test_calendar_year_net_zero_column_matches_time_weighted_cap(pots):
    for y in YEARS:
        t = pots[y]["pot1"]["calibration"]["typical"]
        assert t["consumption"] == "benchmark"
        assert abs(t["check_gbp"]) < 1.0
        assert sum(p["weight"] for p in t["periods"]) == pytest.approx(1.0)
        for p in t["periods"]:
            assert abs(p["check_gbp"]) < 1.0


def test_benchmark_consumption_read_from_cap_model():
    # cap model v1.31 Notes row 163: 3.1 MWh Apr 2018 - Dec 2025, 2.7 Jan-Jun 2026, 2.5 from Jul 2026
    for y in YEARS:
        assert HB.typical_year(y, "benchmark")["consumption_mwh"] == [3.1]
    assert RA.receipt((2026, 1, 2026, 3)).consumption_mwh == 2.7
    assert RA.receipt((2026, 7, 2026, 9)).consumption_mwh == 2.5


def test_reader_household_is_the_tdcv():
    # Ofgem TDCV decisions: 3,100 (2017), 2,900 from 1 Apr 2020, 2,700 from 1 Oct 2023, 2,500 from 1 Jul 2026
    assert HB.tdcv_for((2019, 10, 2020, 3))[0] == 3100
    assert HB.tdcv_for((2020, 4, 2020, 9))[0] == 2900
    assert HB.tdcv_for((2023, 7, 2023, 9))[0] == 2900
    assert HB.tdcv_for((2023, 10, 2023, 12))[0] == 2700
    assert HB.tdcv_for((2025, 10, 2025, 12))[0] == 2700
    assert HB.tdcv_for((2026, 7, 2026, 9))[0] == 2500
    assert HB.typical_year(2025)["consumption_mwh"] == [2.7]
    assert HB.typical_year(2019)["consumption_mwh"] == [3.1]
    assert HB.typical_year(2020)["consumption_mwh"] == [2.9, 3.1]
    for r in RA.receipts():                      # no TDCV change falls inside a cap period
        HB.tdcv_for(r.period)


def test_tdcv_restatement_scales_unit_rate_only():
    for r, _ in HB.period_weights(2025):
        kwh, _ = HB.tdcv_for(r.period)
        rr = RA.at_consumption(r.period, kwh)
        f = (kwh / 1000) / r.consumption_mwh
        for a, b in zip(r.lines, rr.lines):
            if a.key != "vat":
                assert b.nil == pytest.approx(a.nil)
                assert b.typical == pytest.approx(a.nil + (a.typical - a.nil) * f)
        assert rr.total < r.total                # 2,700 kWh bill below the 3,100 kWh cap


def test_headline_at_tdcv_below_calibration(pots):
    p1 = pots[2025]["pot1"]
    assert p1["typical"]["consumption"] == "tdcv"
    assert p1["value_2025"] < p1["calibration"]["value_2025"]


# ---------------------------------------------------------------- Pot 1

def test_pot1_is_the_column_difference(pots):
    for y in YEARS:
        p1 = pots[y]["pot1"]
        t = p1["typical"]
        assert sum(l["value"] for l in p1["lines"]) == pytest.approx(t["netzero"] - t["reliable"], abs=1e-9)
        assert p1["nominal"] == pytest.approx(t["netzero"] - t["reliable"])
        c = p1["calibration"]
        assert sum(l["value"] for l in c["lines"]) == pytest.approx(c["nominal"], abs=1e-9)
        by = {r["key"]: r for r in t["rows"]}
        for l in p1["lines"]:
            if l["from"] != ["direct_fuel", "backwardation"]:
                k = l["from"][0]
                assert l["value"] == pytest.approx(by[k]["netzero"] - by[k]["reliable"])


def test_wholesale_split_adds_back(pots):
    for y in YEARS:
        p1 = pots[y]["pot1"]
        by = {r["key"]: r for r in p1["typical"]["rows"]}
        w = sum(by[k]["netzero"] - by[k]["reliable"] for k in ("direct_fuel", "backwardation") if k in by)
        split = sum(l["value"] for l in p1["lines"] if l["id"] in ("power_before_carbon", "carbon_tax", "carbon_price"))
        assert split == pytest.approx(w)


def test_vat_recomputed_at_period_rate():
    for y in YEARS:
        for r0, _ in HB.period_weights(y):
            r = RA.at_consumption(r0.period, HB.tdcv_for(r0.period)[0])
            c = HB.receipt_columns(r, HB.ratios(y))
            ex = sum(x["reliable"] for x in c["rows"] if x["key"] != "vat")
            vat = next(x for x in c["rows"] if x["key"] == "vat")
            assert vat["reliable"] == pytest.approx(ex * r.vat_rate)
            assert r.vat_rate == pytest.approx(0.05, abs=1e-3)


def test_before_2019_is_average_household_and_flagged(pots):
    for y in (2016, 2017, 2018):
        p1 = pots[y]["pot1"]
        assert p1["kind"] == "average" and "Average household" in p1["label"]
        assert p1["value_2025"] == pytest.approx(B.on_household_bill(HB.engine()[y], y, list(HB.steps(y)))["value"])
        assert p1["typical_illustrative"]["kind"] == "typical_illustrative"
    for y in YEARS:
        assert pots[y]["pot1"]["kind"] == "typical"


# ---------------------------------------------------------------- reconciliation

def test_reconciliation_identity_within_a_penny(pots):
    for y in HB.POT_YEARS:
        r = pots[y]["reconciliation"]
        parts = (r["average_domestic_on_bill"] + r["business"] + r["public"]
                 + r["residual_taxpayer_compensation"])
        assert abs(parts - r["national_gap_per_household"]) < 0.01, y
        assert abs(r["total"] - r["national_gap_per_household"]) < 0.01


def test_gap_is_the_engines_own(pots):
    # tests run on the fixture closure register (conftest), so this is not £570; the identity
    # with the engine's own gap is what matters (the £570 run is in work/s31-household-bill)
    for y in HB.POT_YEARS:
        assert pots[y]["gap_per_household"] == HB.engine()[y]["totals"]["gap_per_hh_real"]


# ---------------------------------------------------------------- no double counting

def test_each_step_split_once_and_adds_back(pots):
    for y in HB.POT_YEARS:
        rows = pots[y]["allocation"]["rows"]
        assert sorted(r["step"] for r in rows) == list(range(1, 10))
        for r in rows:
            assert r["domestic"] + r["business"] + r["public"] == pytest.approx(r["value"], abs=1e-9)
        sh = pots[y]["allocation"]["shares"]
        assert sh["domestic"] + sh["public"] + sh["business"] == pytest.approx(1.0)
        assert 0 < sh["public"] < 0.1


def test_domestic_only_and_business_only_lines(pots):
    for y in HB.POT_YEARS:
        rows = {r["step"]: r for r in pots[y]["allocation"]["rows"]}
        assert rows[7]["domestic"] == 0.0                       # CCL not on domestic supply
        for n in (8, 9):                                         # schemes, household VAT
            assert rows[n]["business"] == pytest.approx(0) and rows[n]["public"] == pytest.approx(0)
        sh = pots[y]["allocation"]["shares"]
        assert rows[3]["domestic"] >= sh["domestic"] * rows[3]["value"] - 1e-9   # EII exemptions raise it


def test_compensation_counted_once(pots):
    for y in HB.POT_YEARS:
        p2, r = pots[y]["pot2"], pots[y]["reconciliation"]
        assert p2["business"] == pytest.approx(p2["business_gross"] - p2["compensation_netted"])
        assert r["residual_taxpayer_compensation"] == pytest.approx(p2["compensation_netted"])
        assert r["business"] == pytest.approx(p2["business"])


def test_no_cap_line_in_two_pot1_lines(pots):
    for y in YEARS:
        seen = {}
        for l in pots[y]["pot1"]["lines"]:
            for k in l["from"]:
                seen.setdefault(k, []).append(l["id"])
        for k, ids in seen.items():
            if k in ("direct_fuel", "backwardation"):
                assert ids == ["power_before_carbon", "carbon_tax", "carbon_price"]
            else:
                assert len(ids) == 1, (k, ids)


# ---------------------------------------------------------------- classification

def test_classification_complete():
    keys = {ln.key for r in RA.receipts() for ln in r.lines} | set(RA.LINES)
    assert keys <= set(HB.CLASSIFICATION), keys - set(HB.CLASSIFICATION)
    for k, c in HB.CLASSIFICATION.items():
        assert c["treatment"] in HB.TREATMENTS
        assert c["reason"] and c["source_id"]
        if c["call"]:
            assert "CALL" in c["reason"]


def test_same_in_both_lines_equal_and_removed_lines_zero(pots):
    for y in YEARS:
        for row in pots[y]["pot1"]["typical"]["rows"]:
            t = HB.CLASSIFICATION[row["key"]]["treatment"]
            if t == "same":
                assert row["reliable"] == pytest.approx(row["netzero"])
            if t == "removed":
                assert row["reliable"] == 0.0


def test_whd_and_aahedc_same_in_both_eco_removed():
    assert HB.CLASSIFICATION["whd"]["treatment"] == "same"
    assert HB.CLASSIFICATION["aahedc"]["treatment"] == "same"
    assert HB.CLASSIFICATION["eco"]["treatment"] == "removed"


# ---------------------------------------------------------------- sources

def test_dbt_compensation_read_from_stored_reports():
    c = HB.compensation_fy()
    assert set(c) == {2021, 2022, 2023, 2024}
    assert c[2024]["gbp_m"] == pytest.approx(42.0 + 35.7 + 50.3 + 6.3 + 12.5)
    assert c[2021]["gbp_m"] == pytest.approx(81.2 + 71.3 + 55.8 + 4.0 + 1.3)
    assert HB.compensation_gb(2019)["basis"] == "UNSOURCED"
    assert HB.compensation_gb(2025)["basis"] == "estimated"


def test_gaps_and_calls_listed():
    assert len(HB.gaps()) >= 5
    assert {c["key"] for c in HB.calls()} >= {"sizewell_c", "eii_levy", "smart_meter", "duos"}
