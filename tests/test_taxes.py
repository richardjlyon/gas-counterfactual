"""Tests for taxes: RO paid by the Treasury, and the EPG note."""
import pytest

from gascf import taxes as tx


def test_annex4_ro_spot_values():
    ro = tx.read_annex4_ro()
    assert ro["January 2026 - March 2026"] == pytest.approx(33.06058)
    assert ro["April 2026 - June 2026"] == pytest.approx(8.18212)
    assert ro["October 2026 - December 2026"] == pytest.approx(8.18212)


def test_ro_treasury_is_three_times_bill_share():
    r = tx.ro_treasury()
    assert r["ro_treasury_mwh"].value == pytest.approx(3 * r["ro_bill_share_mwh"].value)
    assert r["ro_bill_share_per_household"].value == pytest.approx(20.4553, abs=1e-4)
    assert r["ro_treasury_per_household"].value == pytest.approx(61.3659, abs=1e-4)
    # spec §6 (spec.md:126) quotes £61.37: the unrounded product, not 3 x the rounded £20.46
    from pathlib import Path
    assert round(r["ro_treasury_per_household"].value, 2) == 61.37
    assert r["ro_bill_share_mwh"].basis == "allowance"
    assert r["ro_treasury_scheme_total_per_household"].value == pytest.approx(3 * 61.3659, abs=1e-3)


def test_ro_bill_share_against_the_pre_transfer_level():
    """Review N4 (was rel=0.30). Annex 4 1a row 53: Jan-Mar 2026 £33.06058/MWh (100% on bill),
    Apr-Jun 2026 £8.18212 (25%). The implied 100% after April, 4 x 8.18212 = £32.72848, is 1.0%
    below Jan-Mar: the 2026/27 obligation and buy-out price differ from 2025/26."""
    r = tx.ro_treasury()
    full_after = r["ro_bill_share_mwh"].value + r["ro_treasury_mwh"].value
    assert full_after == pytest.approx(4 * 8.18212, abs=1e-9)
    assert r["ro_full_jan_mar_2026_mwh"].value == pytest.approx(33.06058, abs=1e-9)
    assert full_after / r["ro_full_jan_mar_2026_mwh"].value == pytest.approx(0.98996, abs=1e-5)


def test_government_statements_spot_values():
    s = tx.ro_government_statements()
    assert s["guidance_buyout_gbp_per_roc"].value == 69.34
    assert s["guidance_obligation_roc_per_mwh"].value == 0.472
    assert s["guidance_discount_p_kwh"].value == 2.45
    assert s["budget_average_household"].value == 88
    assert s["budget_mwh_off_unit_rate"].value == 24.80
    assert s["em_average_household"].value == 87
    assert s["em_typical_dual_fuel"].value == 66
    assert s["em_total_bn_3yr"].value == 6.7


def test_guidance_formula_reconciles_with_ofgem_cap():
    """DESNZ's 0.75 x buy-out x obligation equals Ofgem's 3 x bill share, to the penny."""
    s = tx.ro_government_statements()
    r = tx.ro_treasury()
    assert s["guidance_formula_mwh"].value == pytest.approx(r["ro_treasury_mwh"].value, abs=1e-4)
    assert round(s["guidance_formula_mwh"].value / 10, 2) == s["guidance_discount_p_kwh"].value


def test_em_typical_matches_formula_at_2_7_mwh():
    s = tx.ro_government_statements()
    assert round(2.7 * s["guidance_formula_mwh"].value) == s["em_typical_dual_fuel"].value


def test_government_averages_imply_average_not_typical_household():
    s = tx.ro_government_statements()
    assert s["budget_implied_mwh"].value == pytest.approx(88 / 24.80)          # 3.548 MWh
    # review N2: the EM never says whether £87 includes VAT, so both readings are reported
    assert s["em_implied_mwh"].value == pytest.approx(87 / 24.54636)             # 3.544 ex VAT
    assert s["em_implied_mwh_if_inc_vat"].value == pytest.approx(87 / 1.05 / 24.54636)  # 3.376
    assert "not stated" in s["em_average_household"].note
    assert "VAT" not in tx._pdf_text(tx.RO_EM)
    # the Budget page counts VAT separately, so its £88 is ex VAT (quoted)
    assert tx.BUDGET_VAT_QUOTE in tx._page_text(tx.BUDGET_PAGE)
    assert "state whether £87 includes VAT" in tx.__doc__


def test_em_total_per_gb_household():
    ln = tx.ro_em_total_per_gb_household(2025)
    assert ln.value == pytest.approx(6.7e9 / 3 / 28_253_000)
    assert ln.basis == "modelled"            # s30: one LFS count, all nations measured


def test_epg_discounts_spot_values():
    d = tx.read_epg_discounts()
    assert (d["Oct-Dec 2022"].elec_p_kwh, d["Oct-Dec 2022"].gas_p_kwh) == (17.0, 4.2)
    assert (d["Jan-Mar 2023"].elec_p_kwh, d["Jan-Mar 2023"].gas_p_kwh) == (31.8, 6.4)
    assert (d["Apr-Jun 2023"].elec_p_kwh, d["Apr-Jun 2023"].gas_p_kwh) == (16.570, 2.185)


def test_epg_discount_equals_cap_minus_epg_rate():
    """Ofgem cap unit rate - DESNZ EPG unit rate (GB mean of 14 regions) = stated discount."""
    cap = tx.read_cap_unit_rates()
    d = tx.read_epg_discounts()
    for q in tx.EPG_RATES:
        e, g = tx.read_epg_regional_dd(q)
        assert cap[q][0] - e == pytest.approx(d[q].elec_p_kwh, abs=0.05), q
        assert cap[q][1] - g == pytest.approx(d[q].gas_p_kwh, abs=0.05), q


def test_epg_note_per_household():
    n = tx.epg_note()
    assert n["Oct-Dec 2022"]["elec_per_household_quarter"].value == pytest.approx(17.0 * 25 / 4)
    assert n["Jan-Mar 2023"]["elec_per_household_annualised"].value == pytest.approx(795.0)
    assert n["Apr-Jun 2023"]["elec_per_household_quarter"].value == pytest.approx(16.57 * 25 / 4)
    assert all(ln.basis in ("measured", "modelled") for q in n.values() for ln in q.values())


def test_nao_epg_total():
    assert tx.read_nao_epg_total().value == 23_999
