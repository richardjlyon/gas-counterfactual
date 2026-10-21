"""Tests for the same-in-both block (src/gascf/same_in_both.py).

Spot values are checked against the stored sources (text layers of the Ofgem PDFs, the
RIIO-ED2 PCFM and the default tariff cap workbook); identities check the block is the same
on both sides and adds up.
"""
import pytest

from gascf import same_in_both as s


# --------------------------------------------------------------------------- spot values


def test_dpcr3_eastern_line17_and_dms():
    # DPCR3 FP Dec 1999, Table 1 Eastern (£m 1997/98): line 17 "Adj price control rev"
    # 363 266 261 256 251 246; line 18 "DMS revenue" 9 6 6 6 6 6.
    d = s.read_dpcr3()
    east = next(v for k, v in d.items() if k.startswith("EASTERN"))
    assert east[2002] == {"duos": 261, "dms": 6}
    assert east[2003] == {"duos": 256, "dms": 6}
    assert east[2004] == {"duos": 251, "dms": 6}
    assert len(d) == 14


def test_dpcr4_cn_midlands_line22():
    # DPCR4 FP Nov 2004, "PRICE CONTROL CALCULATIONS FOR CN - MIDLANDS", 2002/03 prices,
    # line 22 "Price control revenue 246.1 238.0 239.8 241.6 243.3 245.0".
    d = s.read_dpcr4()["CN - MIDLANDS"]
    assert d[2005] == pytest.approx(246.1)
    assert d[2006] == pytest.approx(238.0)
    assert d[2010] == pytest.approx(245.0)
    assert sum(v[2005] for v in s.read_dpcr4().values()) == pytest.approx(2976.7, abs=0.05)


def test_dpcr5_cn_west_line25():
    # DPCR5 FP Financial methodologies, CN West (£m 07/08), line 25 "Base price control
    # revenue (after profiling) - 314.1 327.7 341.8 356.5 371.9".
    d = s.read_dpcr5()["CN West"]
    assert [d[y] for y in range(2011, 2016)] == pytest.approx([314.1, 327.7, 341.8, 356.5, 371.9])


def test_pcfm_enwl_spot_and_totals():
    pc = s.read_ed_pcfm()
    # ENWL sheet: RD FY2015/16 = 415.27; BILLRt FY2023/24 = 539.92 (read in s20e notes).
    assert pc["RD"][2016] == pytest.approx(5258, abs=1)
    assert pc["BILLRt"][2024] == pytest.approx(6447, abs=1)
    assert set(range(2016, 2024)) <= set(pc["RD"])


def test_cap_spot_apr_2022():
    # Cap v1.31, 1b, Other Payment Method, Electricity single-rate, typical consumption,
    # column "Apr 2022 - Sep 2022": OC 87.836…, EBIT 18.676…, SMNCC 15.149…
    caps = s.read_cap()
    v = next(vals for a, b, vals in caps if a.year == 2022 and a.month == 4)
    assert v["OC"] == pytest.approx(87.836, abs=0.001)
    assert v["EBIT"] == pytest.approx(18.676, abs=0.001)
    assert v["SMNCC"] == pytest.approx(15.149, abs=0.001)


def test_cap_periods_contiguous():
    caps = s.read_cap()
    assert caps[0][0].isoformat() == "2017-04-01"
    for (a0, b0, _), (a1, b1, _) in zip(caps, caps[1:]):
        assert b0 == a1, (b0, a1)


def test_vat_rate_read_from_hmrc():
    v = s.domestic_vat_rate()
    assert v["rate"] == 0.05 and v["from"].isoformat() == "1997-09-01"


# --------------------------------------------------------------------------- identities


def test_dukes_domestic_vat_is_five_percent():
    # Cross-check: DUKES 1.2 domestic electricity VAT / (market value − VAT) ≈ 5% each year.
    for y, d in s.dukes_domestic_vat().items():
        assert d["vat"] / (d["market"] - d["vat"]) == pytest.approx(0.05, abs=0.001), y


def test_fy_to_cy_weights():
    series = {2010: {"gbp_m": 100.0, "basis": "measured", "source_id": "a"},
              2011: {"gbp_m": 200.0, "basis": "measured", "source_id": "a"}}
    v, basis, src = s.fy_to_cy(series, 2010)
    assert v == pytest.approx(175.0)          # 3/12 × 100 + 9/12 × 200
    assert basis == "modelled" and src == "a"


def test_rpi_fy_average():
    m = s.rpi_monthly()
    exp = (sum(m[(2002, k)] for k in range(4, 13)) + sum(m[(2003, k)] for k in range(1, 4))) / 12
    assert s.rpi_fy(2003) == pytest.approx(exp)


def test_block_identical_on_both_sides():
    b = s.both_bills()
    assert b["net_zero"] == b["fossil"]
    assert b["net_zero"] is b["fossil"]


def test_block_total_is_sum_of_parts_and_tagged():
    b = s.block()
    assert set(b) == set(range(2002, 2026))
    for y, row in b.items():
        parts = [row[i]["value"] for i in ("duos", "metering", "supplier", "vat")]
        assert row["total"]["value"] == pytest.approx(sum(p for p in parts if p is not None))
        for k, line in row.items():
            assert line["basis"] in ("measured", "modelled", "estimated", "UNSOURCED"), (y, k)
            assert line["source_id"], (y, k)


def test_gaps_are_tagged_not_guessed():
    b = s.block()
    for y in range(2004, 2007):
        assert b[y]["metering"]["basis"] == "UNSOURCED"
        assert b[y]["total"]["note"].startswith("PARTIAL")
    for y in list(range(2002, 2004)) + list(range(2007, 2026)):
        assert b[y]["total"]["note"] == "complete", y
    for y in range(2002, 2026):
        assert b[y]["supplier"]["value"] is not None and b[y]["supplier"]["basis"] != "UNSOURCED"


# --------------------------------------------------------------------------- supplier history


def test_smi_2009_read_and_deflated():
    # SMI Apr 2015 'Electricity data': 2009 col B, 2014 prices: row 37 operating costs and row 45
    # pre-tax margin; Inflation tab E6 '2009 to 2014' factor. Nominal = 2014-prices / (1+f).
    import openpyxl
    wb = openpyxl.load_workbook(s.SMI, data_only=True)
    e, inf = wb["Electricity data"], wb["Inflation"]
    f = 1 + inf["E6"].value
    smi = s.read_smi()
    assert smi[2009]["opex"] == pytest.approx(e["B37"].value / f)
    assert smi[2009]["margin"] == pytest.approx(e["B45"].value / f)
    assert smi[2009]["opex"] == pytest.approx(64.14, abs=0.01)
    assert 1.15 < f < 1.25                        # RPI 2009 -> 2014 ≈ +20%


def test_rmi_dual_fuel_spot():
    # everviz H2G7IL0vq csv: 2015 'Operating costs' 182, 'EBIT' 49; 2009 132 / 8.
    r = s.read_rmi_dual()
    assert r[2015] == {"opex": 182.0, "ebit": 49.0}
    assert r[2009] == {"opex": 132.0, "ebit": 8.0}


def test_cma_indirect_nominal():
    # CMA 9.11 Annex A Table 1 (combined, FY07 prices): FY07 81; CPI deflator
    # December 2007 = 100.0%, so 2007 nominal = 81.
    c = s.read_cma_indirect()
    assert c[2007] == pytest.approx(81.0)
    assert c[2014] > c[2009] > c[2007]


def test_qep_221_spot():
    # QEP 2.2.1 3,300 kWh cash: 2003 direct debit 238, overall 248; 2008 overall 421.
    q = s.qep_elec_bill_3300()
    assert q[2003] == {"dd": 238.0, "overall": 248.0}
    assert q[2008]["overall"] == 421.0


def test_supplier_history_methods():
    h = s.supplier_history()
    assert set(h) == set(range(2002, 2017))
    smi = s.read_smi()
    for y in range(2009, 2014):
        assert h[y]["basis"] == "measured"
        assert h[y]["value"] == pytest.approx(smi[y]["opex"] + smi[y]["margin"])
    # 2014-2016: RMI dual-fuel × electricity share; 2014 within 25% of the SMI 2014 estimate
    rmi = s.read_rmi_dual()
    share = sum(h[y]["value"] for y in range(2009, 2014)) / sum(
        rmi[y]["opex"] + rmi[y]["ebit"] for y in range(2009, 2014))
    assert 0.35 < share < 0.5
    assert h[2015]["value"] == pytest.approx(share * (182 + 49))
    est14 = smi[2014]["opex"] + smi[2014]["margin"]
    assert h[2014]["value"] == pytest.approx(est14, rel=0.25)
    # 2007: SMI 2009 opex × CMA(2007)/CMA(2009) + 2% × QEP overall/1.05
    c = s.read_cma_indirect()
    assert h[2007]["value"] == pytest.approx(smi[2009]["opex"] * c[2007] / c[2009] + 0.02 * 366 / 1.05)
    # 2002-2006 range: low = 26% × 238 (DD 2003, slice already excl. VAT); high = 2007
    assert h[2002]["low"] == pytest.approx(0.26 * 238)
    assert h[2002]["high"] == pytest.approx(h[2007]["value"])
    assert h[2004]["value"] == pytest.approx(h[2004]["low"])
    assert h[2004]["value"] < h[2005]["value"] < h[2006]["value"] < h[2007]["value"]
    for y in range(2002, 2017):
        if y not in range(2009, 2014):
            assert h[y]["basis"] == "estimated"


def test_supplier_join_with_cap_is_plausible():
    # The CSS-based 2016 and the cap-based 2017 should be within 15% (same denominator).
    b = s.block()
    assert b[2017]["supplier"]["value"] == pytest.approx(b[2016]["supplier"]["value"], rel=0.15)
    assert b[2002]["supplier"]["low"] <= b[2002]["supplier"]["value"] <= b[2002]["supplier"]["high"]


def test_duos_per_household_matches_national():
    from gascf import households as hh
    b = s.block()
    for y in (2002, 2015, 2025):
        assert b[y]["duos"]["value"] == pytest.approx(
            b[y]["duos_gbp_m"]["value"] * 1e6 / (hh.read_households()[y] * 1000))
