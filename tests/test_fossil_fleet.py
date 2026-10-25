"""s20b fossil fleet tests: sources reproduce, bases are consistent, coal is capped, books balance."""
import re
from datetime import date
from types import SimpleNamespace

import pymupdf
import pytest

from gascf import fossil_fleet as F
from gascf.plant import annualised_fixed_gbp_kw_yr

DERATE = {"ccgt": 0.9, "ocgt": 0.93}


@pytest.mark.parametrize("key", sorted(F.cost_editions()["tables"]))
def test_every_hand_entered_row_is_on_its_pdf_page(key):
    t = F.cost_editions()["tables"][key]
    page = re.sub(r"\s+", " ", pymupdf.open(F.EGC / t["file"])[t["page"] - 1].get_text())
    for name, r in t["rows"].items():
        assert r["row"] in page, f"{key}.{name} not on {t['file']} p{t['page']}"


def test_price_base_and_basis_quotes_are_in_the_pdfs():
    for k, q in F.cost_editions()["quotes"].items():
        page = re.sub(r"\s+", " ", pymupdf.open(F.EGC / q["file"])[q["page"] - 1].get_text())
        assert q["quote"] in page, k


def test_ncv_gcv_ratio_matches_published_cvs():
    r = F.ncv_gcv_ratio()
    assert r["gas"][2025] == pytest.approx(35.608 / 39.564, abs=0.002)   # DUKES A.1.3/A.2.3
    assert 0.94 < r["coal"][2012] < 0.96


def test_cepa_lhv_reproduces_egc2025_hhv():
    """CEPA/GHD 60.2% LHV x NCV/GCV = the 54% EGC 2025 prints (HHV): the basis claim."""
    assert F.to_gross(0.602, "net_lhv", "gas", 2024) == pytest.approx(0.54, abs=0.003)


def test_unknown_basis_raises():
    with pytest.raises(ValueError):
        F.to_gross(0.5, "lhv-ish", "gas", 2020)


@pytest.mark.parametrize("year,ccgt", [(2005, "mm2010-tableA1"), (2012, "pb2012-ccgt"), (2014, "pb2013-ccgt"),
                                       (2017, "beis-egc2016-table19"), (2021, "beis-egc2020-keydata"),
                                       (2024, "desnz-egc2023-annexA"),
                                       # v4-s42 (A4, decision 0195): 2025 on EGC 2023, the set in force at the end of 2025
                                       (2025, "desnz-egc2023-annexA")])
def test_edition_rule(year, ccgt):
    e = F.edition(year)
    assert e.source_id["ccgt"] == ccgt
    for k in ("coal", "ccgt", "ocgt"):
        assert 0.25 < getattr(e, k).efficiency_gcv < 0.6       # gross CV, sent out


def test_egc2016_reads_table19_values():
    p = F.read_egc2016("CCGT H Class")
    assert (p.size_mw, p.construction_gbp_kw["medium"], p.fixed_om_gbp_mw_yr) == (1200, 500, 12200)
    assert p.efficiency_gcv == pytest.approx(0.5371, abs=1e-4)


def test_fixed_cost_restated_with_cpih():
    from gascf.deflator_cpih import cpih
    e = F.edition(2017)
    hand = annualised_fixed_gbp_kw_yr(e.ccgt) * cpih()[2017] / cpih()[2014]
    assert F.fixed_gbp_kw_yr(e, "ccgt") == pytest.approx(hand)


def test_coal_capacity_gb_drops_kilroot_and_hits_zero():
    # v4-s42 (A1, decision 0195): Kilroot coal 2010 is 520 MW (the DUKES 2010 row of 662 carries its 142 MW OCGT)
    assert F.coal_capacity_gb(2010)[0] == pytest.approx(F.coal_capacity_uk()[2010] - 520)
    assert F.coal_capacity_gb(2025)[0] == 0.0


def test_fuel_prices_units():
    assert 5 < F.gas_price_month(2012, 6)[0] < 40              # £/MWh
    assert F.gas_price_month(2008, 6, pre_wmi="qep")[2] == "desnz-qep-321-mpp-gas"
    assert F.gas_price_month(2022, 8)[0] > 100                  # 2022 spike
    assert F.coal_price_month(2012, 1)[1] == "measured"


def test_pre_2009_gas_is_nbp_fig5_by_default():
    """Spec §15.2 item 3: NBP throughout. Before Oct 2009 the default reads Ofgem WEM 2015
    Fig 5; from Oct 2009 WMI is used under either route."""
    from gascf import prices
    assert F.GAS_PRE_WMI == "nbp"
    v, basis, sid = F.gas_price_month(2008, 6)
    assert sid == "ofgem-wholesale-energy-markets-2015-fig5-vector" and basis == "measured"
    assert v == pytest.approx(prices.fig5_gas_ptherm()[(2008, 6)] / 2.93071, rel=1e-9)
    # identity with prices.nbp_gbp_mwh(), the electricity module's own NBP series
    for k in [(2002, 1), (2005, 11), (2008, 6), (2009, 9)]:
        assert F.gas_price_month(*k)[0] == pytest.approx(prices.nbp_gbp_mwh()[k][0], rel=1e-9)
    # the switch only changes months before WMI
    assert F.gas_price_month(2012, 6, "qep") == F.gas_price_month(2012, 6, "nbp")
    assert F.gas_price_month(2008, 6, "qep")[0] != v
    # 2008 hub spike: NBP day-ahead year mean above the contract-lagged QEP price paid
    yr = lambda r: sum(F.gas_price_month(2008, m, r)[0] for m in range(1, 13)) / 12
    assert yr("nbp") > yr("qep")
    assert 15 < v < 30                                           # £/MWh, i.e. ~44-88 p/therm
    with pytest.raises(ValueError):
        F.gas_price_month(2008, 6, pre_wmi="bogus")
    with pytest.raises(ValueError):
        F.gas_price_month(2000, 6)                               # before Fig 5 starts


def _rows(year, mw_list):
    d0 = date(year, 1, 1)
    out = []
    for i, mw in enumerate(mw_list):
        out.append(SimpleNamespace(day=date(year, 1 + (i * 12) // len(mw_list), 1 + (i % 28)), residual=mw))
    return out


def test_coal_never_exceeds_actual_capacity():
    rows = _rows(2012, [30000] * 17000 + [45000] * 568)
    for rule in F.COAL_RULES:
        r = F.cost_fossil_year(2012, rows, 0.05, DERATE, coal_cap_mw=10000, coal_rule=rule)
        assert r.coal_gw <= 10.0 + 1e-9
        r0 = F.cost_fossil_year(2012, rows, 0.05, DERATE, coal_cap_mw=0, coal_rule=rule)
        assert r0.coal_gw == 0 and r0.gen_twh["coal"] == 0


def test_coal_forced_to_actual_capacity():
    """§15.2 decision 1: with coal forced (the default), fossil Britain runs exactly the coal
    capacity Britain had, even in a year (2016: coal dearer than gas) where coal would not
    win a strip; 'allowed' builds none there. The odd last strip lands exactly on the cap."""
    rows = _rows(2016, [20000 + (i % 48) * 400 for i in range(17568)])
    forced = F.cost_fossil_year(2016, rows, 0.05, DERATE, coal_cap_mw=7_321)
    allowed = F.cost_fossil_year(2016, rows, 0.05, DERATE, coal_cap_mw=7_321, coal_rule="allowed")
    assert forced.coal_gw == pytest.approx(7.321, abs=1e-9)
    assert allowed.coal_gw == 0
    assert forced.total_gbp_m > allowed.total_gbp_m          # forcing only ever adds cost
    assert forced.energy_twh == pytest.approx(allowed.energy_twh)
    with pytest.raises(ValueError):
        F.cost_fossil_year(2016, rows, 0.05, DERATE, coal_rule="banned")


def test_energy_balances_and_peak_covered():
    rows = _rows(2016, [20000 + (i % 48) * 400 for i in range(17568)])
    r = F.cost_fossil_year(2016, rows, 0.05, DERATE)
    assert r.energy_twh == pytest.approx(sum(x.residual for x in rows) / 2 / 1e6)
    derated = r.coal_gw * 0.9 + r.ccgt_gw * 0.9 + (r.ocgt_gw + r.spare_gw) * 0.93
    assert derated >= max(x.residual for x in rows) * 1.05 / 1000 - 1e-6


def test_no_carbon_in_costs():
    import inspect
    assert "carbon" not in inspect.getsource(F.cost_fossil_year).lower().replace("no carbon", "")


# ------------------------------------------------------------------ s23b (spec §15.3)

def test_fgd_share_is_quoted_from_mott_macdonald_2010():
    import pymupdf
    from gascf import fossil_fleet as ff
    d = pymupdf.open(ff.EGC / "s18d-MottMacDonald_2010_UK_generation_costs.pdf")
    text = " ".join(" ".join(p.get_text().split()) for p in d).replace("15- 20%", "15-20%")
    assert ff.FGD_QUOTE in text
    assert ff.FGD_SHARE_OF_COAL_EPC == 0.20            # top of the quoted 15-20% (conservative)
    p, base, src = ff.fgd_retrofit(ff.edition(2016))
    assert p.construction_gbp_kw["medium"] == pytest.approx(1687.5 * 0.20) and base == 2009


def test_abatement_costs_add_up():
    from gascf import fossil_fleet as ff
    ed = ff.edition(2018)
    both = ff.abatement_gbp_kw_yr(ed, "FGD+SCR")
    fgd, scr = ff.abatement_gbp_kw_yr(ed, "FGD"), ff.abatement_gbp_kw_yr(ed, "SCR")
    assert both[0] == pytest.approx(fgd[0] + scr[0]) and both[1] == pytest.approx(scr[1])
    assert ff.abatement_gbp_kw_yr(ed, None) == (0.0, 0.0, [])
    with pytest.raises(ValueError):
        ff.abatement_gbp_kw_yr(ed, "CCS")
    assert 0 < ff.keep_open_gbp_kw_yr(ed, "coal") < ff.fixed_gbp_kw_yr(ed, "coal")


def test_no_new_nuclear_in_any_year():
    """No edition in force 2002-2025 lets a new nuclear plant run before 2026 (§15.3 item 4)."""
    from gascf import fossil_fleet as ff
    assert all(not ff.nuclear_available(y)[0] for y in range(2002, 2026))
    assert ff.nuclear_available(2018)[1].startswith("edition egc2016")
