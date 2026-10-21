"""Tests for receipt_actual: the Actual column of the household electricity receipt.

Spot values are checked against cells read by hand in Ofgem's workbooks (cell refs given).
The key test is the reconciliation: for every cap period the receipt lines add up to
Ofgem's published GB-average cap level at Ofgem's own consumption.
"""
import math

import openpyxl
import pytest

from gascf import receipt_actual as ra

OCT26 = (2026, 10, 2026, 12)


@pytest.fixture(scope="module")
def all_receipts():
    return ra.receipts()


def test_period_coverage(all_receipts):
    keys = [r.period for r in all_receipts]
    assert keys[0] == (2015, 4, 2015, 9)
    assert keys[-1] == OCT26
    assert len(keys) == 32                     # 4 notional + 28 in Annex 9 tab 1b
    assert keys == sorted(set(keys))
    # periods tile the calendar with no gap or overlap
    for a, b in zip(keys, keys[1:]):
        nxt = (a[2] + (a[3] == 12), a[3] % 12 + 1)
        assert (b[0], b[1]) == nxt, (a, b)


def test_reconciles_to_published_cap_every_period(all_receipts):
    """Lines sum to Ofgem's published GB-average cap at Ofgem's consumption, to the penny.

    Ofgem's tab 1b carries unrounded values, and our lines are its components (or exact
    sub-splits of them), so the match is to floating-point precision, far inside a penny.
    """
    for r in all_receipts:
        assert abs(r.total_ex_vat - r.published_ex_vat) < 1e-6, r.label
        if r.period < (2017, 4, 2017, 9):
            # review N4: for 2015-17 the "published" inc-VAT is our own ex x 1.05, so checking
            # it would be circular; the ex-VAT level is checked against the cap model cell below
            continue
        assert abs(r.total - r.published_inc_vat) < 1e-6, r.label
        assert round(r.total, 2) == round(r.published_inc_vat, 2), r.label


def test_notional_periods_against_cap_model_cells(all_receipts):
    """2015-17: ex-VAT total equals the cap model's own GB-average Total row (row 239), read
    here independently of the module by locating the column from its period label."""
    wb = openpyxl.load_workbook(ra.CAP_MODEL, read_only=True, data_only=True)
    R = list(wb["ElecSingle_Other_Benchmark"].iter_rows(values_only=True, max_col=50, max_row=239))
    assert R[238][2] == "Total_GB average"
    hdr = {ra.period_key(v): j for j, v in enumerate(R[11]) if j >= 6 and isinstance(v, str) and "20" in v}
    n = 0
    for r in all_receipts:
        if r.period < (2017, 4, 2017, 9):
            assert r.total_ex_vat == pytest.approx(R[238][hdr[r.period]], abs=1e-9), r.label
            n += 1
    assert n == 4


def test_published_level_matches_ofgem_headline_table():
    """Annex 9 tab 1a (the published Oct-Dec 2026 benchmark maximum charges, GB average row 28-29)."""
    wb = openpyxl.load_workbook(ra.ANNEX9, read_only=True, data_only=True)
    rows = list(wb["1a Levelised DTC"].iter_rows(values_only=True, max_col=10, max_row=29))
    assert rows[5][2] == "October 2026 - December 2026"
    assert rows[27][1] == "GB average"
    regional = [rows[i][3] for i in range(13, 27)]          # D14:D27, 2 d.p. as in the 17a PDF
    assert len(regional) == 14
    r = ra.receipt(OCT26)
    # Ofgem's GB average = unweighted mean of the 14 regions (D28 = 858.2007 from 2 d.p. values)
    assert sum(regional) / 14 == pytest.approx(rows[27][3], abs=1e-9)
    assert round(r.total_ex_vat, 2) == round(rows[27][3], 2) == 858.20
    assert round(r.total, 2) == round(rows[28][3], 2) == 858.20       # 0% VAT
    # dual-fuel inc VAT GB average J29 = £1,723 headline in the Summary of changes
    assert round(rows[28][9]) == 1723


def test_gb_average_is_mean_of_14_regions():
    """Ofgem's GB-average rows are literally AVERAGE() of the 14 regional rows (cap model v1.31)."""
    wb = openpyxl.load_workbook(ra.CAP_MODEL, read_only=True)
    row = list(wb["ElecSingle_Other_Benchmark"].iter_rows(
        min_row=225, max_row=225, max_col=43, values_only=True))[0]
    f = row[42]  # AQ225
    assert f.startswith('=IF(AQ15="-","-",AVERAGE(')
    assert f.count(",AQ") == 13                   # 14 regional cells


def test_oct_dec_2026_spot_values():
    r = ra.receipt(OCT26)
    v = {ln.key: ln.typical for ln in r.lines}
    assert r.consumption_mwh == 2.5
    assert r.vat_rate == 0.0 and v["vat"] == 0.0
    # cap model 3a DF, GB mean of 14 regions (rows 11-24, 48-61, 85-98; col AP)
    assert round(v["direct_fuel"], 2) == 301.13
    assert round(v["backwardation"], 2) == 22.46
    assert round(v["cfd"], 2) == 17.14
    assert round(v["direct_fuel"] + v["backwardation"] + v["cfd"], 2) == 340.73   # A9 1b AE32
    # Annex 4 1a rows 53-60 (col AO) x 2.5 MWh
    assert round(v["ro"], 2) == 20.46          # 8.1821 £/MWh
    assert round(v["fit"], 2) == 20.13
    assert round(v["capacity_market"], 2) == 38.44   # A9 1b AE33
    # spec §6 (spec.md:118) says WHD+Sizewell C+AAHEDC+EII = £31.35, as the workbook gives
    assert round(v["whd"] + v["sizewell_c"] + v["aahedc"] + v["eii_levy"], 2) == 31.35
    assert round(v["whd"], 2) == 15.93 and round(r.line("whd").nil, 2) == 3.41
    assert round(v["sizewell_c"], 2) == 11.59
    # policy total = Ofgem PC (A9 1b AE35)
    pol = sum(v[k] for k in ("ro", "fit", "eco", "whd", "aahedc", "eii_levy", "sizewell_c"))
    assert round(pol, 2) == 71.94
    # network: TNUoS + DUoS + BSUoS = NC 228.59 (A9 1b AE36)
    assert round(v["tnuos"] + v["duos"] + v["bsuos"], 2) == 228.59
    # supplier costs incl. EBIT and headroom: the sum of A9 1b AE37:AE45 (OC..HAP)
    sup = sum(ln.typical for ln in r.lines if ln.group == "supplier")
    wb = openpyxl.load_workbook(ra.ANNEX9, read_only=True, data_only=True)
    R = list(wb["1b Historical level tables"].iter_rows(values_only=True, max_col=31, max_row=48))
    j = next(j for j, x in enumerate(R[30]) if j >= 2 and isinstance(x, str) and ra.period_key(x) == OCT26)
    codes = {ra._norm(R[i][1]): R[i][j] for i in range(31, 48)}
    assert sup == pytest.approx(sum(codes[c] for c in ("OC", "SMNCC", "IC", "PAAC", "PAP", "CO", "DRC",
                                                        "EBIT", "HAP") if isinstance(codes[c], float)))
    assert v["levelisation"] == pytest.approx(codes["Levelisation"])


def _annex3_gb_mean(tab, first, label):
    """Mean of the 14 regional cells (rows first+1..first+14) under a period label in row 8."""
    wb = openpyxl.load_workbook(ra.ANNEX3, read_only=True, data_only=True)
    R = list(wb[tab].iter_rows(values_only=True, max_col=58, max_row=first + 14))
    j = next(j for j, x in enumerate(R[7]) if j >= 8 and isinstance(x, str) and ra._norm(x) == label)
    regions = [R[first + i][5] for i in range(14)]
    assert regions[0] == "Eastern" and regions[-1] == "Northern Scotland"
    return sum(R[first + i][j] for i in range(14)) / 14


@pytest.mark.parametrize("period,label,tnuos,duos,bsuos", [
    # Annex 3 v1.25, col AO, typical rows 25-38 (TNUoS, DUoS) and 11-24 (BSUoS)
    (OCT26, "October 2026 - December 2026", 83.1236, 110.1468, 35.3241),
    # col Z, "October 2022 - March 2023": the cap's Oct-Dec 2022 and Jan-Mar 2023 both sit in it
    # (the _lookup containment rule)
    ((2022, 10, 2022, 12), "October 2022 - March 2023", 40.2979, 140.7668, 26.0849),
    ((2023, 1, 2023, 3), "October 2022 - March 2023", 40.2979, 140.7668, 26.0849),
])
def test_network_lines_against_annex3_cells(period, label, tnuos, duos, bsuos):
    """Review S2: each network line separately, against Annex 3 cells read by this test (a
    TNUoS/DUoS swap now fails here)."""
    r = ra.receipt(period)
    want = {"tnuos": _annex3_gb_mean("2a TNUoS", 24, label), "duos": _annex3_gb_mean("2b DUoS", 24, label),
            "bsuos": _annex3_gb_mean("2c BSUoS", 10, label)}
    for k, quoted in (("tnuos", tnuos), ("duos", duos), ("bsuos", bsuos)):
        assert want[k] == pytest.approx(quoted, abs=5e-5), k
        assert r.line(k).typical == pytest.approx(want[k], abs=0.01), (period, k)


@pytest.mark.parametrize("period,col_label,q,want", [
    # Annex 4 1a rows 56-60: WHD £/customer, WHD £/MWh, AAHEDC, NCC (EII), nRAB (Sizewell C)
    (OCT26, "October 2026 - December 2026", 2.5,
     {"whd_cust": 3.4102172359204843, "whd_mwh": 5.006199122053527, "aahedc": 0.49387668323172623,
      "eii_levy": 1.043618419609701, "sizewell_c": 4.634096837462586}),
    ((2022, 10, 2022, 12), "October 2022 - December 2022", 3.1,
     {"whd_cust": 9.950486379774244, "whd_mwh": 0.0, "aahedc": 0.4411573444204216,
      "eii_levy": 0.0, "sizewell_c": 0.0}),
])
def test_scheme_lines_against_annex4_cells(period, col_label, q, want):
    """Review S2: each Annex 4 scheme row individually (values quoted from the cells)."""
    wb = openpyxl.load_workbook(ra.ANNEX4, read_only=True, data_only=True)
    R = list(wb["1a Policy Cost Allowance"].iter_rows(values_only=True, max_col=45, max_row=60))
    j = next(j for j, x in enumerate(R[11]) if j >= 6 and isinstance(x, str) and ra._norm(x) == col_label)
    cell = {"whd_cust": R[55][j], "whd_mwh": R[56][j], "aahedc": R[57][j], "eii_levy": R[58][j],
            "sizewell_c": R[59][j]}
    for k, v in want.items():
        assert cell[k] == pytest.approx(v, abs=1e-12), k
    r = ra.receipt(period)
    assert r.line("whd").typical == pytest.approx(want["whd_cust"] + want["whd_mwh"] * q, abs=1e-9)
    assert r.line("whd").nil == pytest.approx(want["whd_cust"], abs=1e-9)
    for k in ("aahedc", "eii_levy", "sizewell_c"):
        assert r.line(k).typical == pytest.approx(want[k] * q, abs=0.01), k


def test_plug_residuals_visible_and_tiny(all_receipts):
    """Review S2: what is folded into AAHEDC / DUoS is recorded on the receipt and < 1p."""
    worst = 0.0
    for r in all_receipts:
        assert set(r.residuals) == {"policy_into_aahedc", "network_typical_into_duos",
                                    "network_nil_into_duos"}, r.label
        worst = max(worst, *(abs(v) for v in r.residuals.values()))
    assert worst < 0.01
    # the one real residual: Apr-Jun 2023, Annex 3 v1.25 vs cap model v1.31 (0.836p)
    assert ra.receipt((2023, 4, 2023, 6)).residuals["network_typical_into_duos"] == pytest.approx(
        0.00836, abs=1e-5)


def test_vat_five_percent_before_oct_2026(all_receipts):
    for r in all_receipts:
        if r.period < OCT26:
            assert r.vat_rate == 0.05, r.label
            assert r.line("vat").typical == pytest.approx(0.05 * r.total_ex_vat)


def test_consumption_by_period():
    assert ra.receipt((2015, 4, 2015, 9)).consumption_mwh == 3.1
    assert ra.receipt((2025, 10, 2025, 12)).consumption_mwh == 3.1
    assert ra.receipt((2026, 1, 2026, 3)).consumption_mwh == 2.7
    assert ra.receipt((2026, 4, 2026, 6)).consumption_mwh == 2.7
    assert ra.receipt((2026, 7, 2026, 9)).consumption_mwh == 2.5


def test_every_line_tagged(all_receipts):
    for r in all_receipts:
        assert [ln.key for ln in r.lines] == [k for k in ra.LINES if k in {ln.key for ln in r.lines}]
        assert len(r.lines) == len(ra.LINES)
        for ln in r.lines:
            assert ln.basis in ra.BASES
            assert ln.source_id
            assert not math.isnan(ln.typical)


def test_cap_components_are_allowances_not_measured(all_receipts):
    """Review B2: Ofgem's cap components are ex-ante allowances; none is tagged `measured`."""
    for r in all_receipts:
        for ln in r.lines:
            assert ln.basis != "measured", (r.label, ln.key)
            if ln.key != "vat" or r.period >= (2017, 4, 2017, 9):
                assert ln.basis == ra.BASIS_ALLOWANCE, (r.label, ln.key)
    for ln in ra.at_consumption(OCT26, 2500).lines:
        assert ln.basis == ra.BASIS_ALLOWANCE


def test_cfd_outturn_carried_beside_allowance():
    """Review B2: LCCC outturn beside the allowance. In Apr-Jun 2023 Ofgem allowed -£18.49/MWh
    of supply (-£57.31/yr at 3.1 MWh) while LCCC reconciled at +£4.17/MWh."""
    r = ra.receipt((2023, 4, 2023, 6))
    assert r.line("cfd").typical / r.consumption_mwh == pytest.approx(-18.49, abs=0.01)
    assert r.cfd_outturn["gbp_mwh"] == pytest.approx(4.17, abs=0.005)
    assert r.cfd_outturn_typical() == pytest.approx(4.166 * 3.1, abs=0.01)
    assert r.cfd_outturn["basis"] == "measured" and r.cfd_outturn["days"] == 91
    assert ra.receipt((2021, 10, 2022, 3)).cfd_outturn["gbp_mwh"] == pytest.approx(-1.83, abs=0.005)
    # every period from the first CfD levy to Mar 2026 has an outturn. Apr-Jun 2026 has none:
    # LCCC's latest run for 16 Jun 2026 is II (no levy rate yet), so the period is not complete.
    for r in ra.receipts():
        if (2016, 4, 2016, 9) <= r.period <= (2026, 1, 2026, 3):
            assert r.cfd_outturn is not None, r.label
    assert ra.receipt((2026, 4, 2026, 6)).cfd_outturn is None
    assert ra.receipt(OCT26).cfd_outturn is None
    assert ra.receipt(OCT26).cfd_outturn_typical() is None


def test_labels_sourced():
    """Review S7 / B3: named lines; the Adjustment Allowance label uses Ofgem's own words."""
    wb = openpyxl.load_workbook(ra.CAP_MODEL, read_only=True, data_only=True)
    b3 = list(wb["3c AA"].iter_rows(values_only=True, min_row=3, max_row=3, max_col=2))[0][1]
    assert ra.AA_ANCHOR in ra._norm(b3)
    assert "Annex 8" in ra.LINES["adjustment_allowance"][0]
    assert "crisis" not in ra.LINES["adjustment_allowance"][0].lower()
    for k in ("eco", "adjustment_allowance", "levelisation"):
        assert k in ra.LINES and ra.receipt(OCT26).line(k).label == ra.LINES[k][0]


def test_history_flags():
    # review N6: Oct 2018-Mar 2019 only contains the first cap quarter, and says so
    h = ra.receipt((2018, 10, 2019, 3))
    assert h.cap_in_force and "from 1 Jan 2019 only" in h.published_note
    assert "only" not in ra.receipt((2019, 4, 2019, 9)).published_note
    assert not ra.receipt((2017, 4, 2017, 9)).cap_in_force
    assert ra.receipt((2019, 4, 2019, 9)).cap_in_force
    assert ra.receipt((2022, 10, 2022, 12)).epg_in_force
    assert ra.receipt((2023, 4, 2023, 6)).epg_in_force
    assert not ra.receipt((2023, 7, 2023, 9)).epg_in_force
    # 2015-17: illustrative only, VAT is our stated assumption
    r = ra.receipt((2015, 4, 2015, 9))
    assert r.line("vat").basis == "estimated"
    assert round(r.total_ex_vat, 2) == 482.57     # cap model ElecSingle_Other_Benchmark G239


def test_at_consumption_identity():
    r = ra.receipt(OCT26)
    same = ra.at_consumption(OCT26, 2500)
    assert same.total == pytest.approx(r.total, abs=1e-9)
    zero = ra.at_consumption(OCT26, 0)
    assert zero.total_ex_vat == pytest.approx(r.nil_published_ex_vat, abs=1e-6)   # A9 1b AE28 200.14
    # linear in kWh
    a, b, c = (ra.at_consumption(OCT26, q).total for q in (1000, 2000, 3000))
    assert b - a == pytest.approx(c - b)
    # standing-charge parts never scale
    for ln in ra.at_consumption(OCT26, 5000).lines:
        if ln.key in ("tnuos", "levelisation"):
            assert ln.nil == r.line(ln.key).nil


def test_at_consumption_matches_ofgem_2500_kwh_restatement():
    """Annex 9 tab 1c restates every period at 2,500 kWh; ours must agree for every period."""
    wb = openpyxl.load_workbook(ra.ANNEX9, read_only=True, data_only=True)
    R = list(wb["1c Consumption adjusted levels"].iter_rows(values_only=True, max_col=32, max_row=56))
    assert R[6][4] == 2.5 and R[53][1] == "Total_GB average"
    n = 0
    for j in range(2, 31):
        if not R[37][j]:
            continue
        a = ra.at_consumption(ra.period_key(R[37][j]), 2500)
        assert a.total_ex_vat == pytest.approx(R[53][j], abs=1e-6), R[37][j]
        assert a.total == pytest.approx(R[54][j], abs=1e-6), R[37][j]
        n += 1
    assert n == 28
