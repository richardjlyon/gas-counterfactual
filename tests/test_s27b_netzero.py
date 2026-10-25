"""s27b: net-zero side review fixes (spec §15.5 item 3). Each fix has a switch whose default is
the new central behaviour; the old behaviour stays reachable as a named value."""
import warnings

import pytest

from gascf import balancing as b
from gascf import bridge as R
from gascf import carbon as c
from gascf import grid as g
from gascf import subsidies as s

warnings.filterwarnings("ignore")
YEARS = range(2002, 2026)


# ------------------------------------------------------------------ 1. TNUoS generator share

def test_tnuos_gen_share_read_from_documents():
    sh = {k: v["share"] for k, v in g.tnuos_gen_share_fy().items()}
    assert all(sh[fy] == 0.27 for fy in range(2001, 2014))           # fixed by the methodology
    expect = {2014: 0.270, 2015: 0.232, 2016: 0.167, 2017: 0.148, 2018: 0.161, 2019: 0.142,
              2020: 0.132, 2021: 0.233, 2022: 0.234, 2023: 0.214, 2024: 0.253, 2025: 0.222, 2026: 0.162}
    for fy, v in expect.items():
        assert sh[fy] == pytest.approx(v, abs=0.0015), fy
    assert sh[2018] == pytest.approx(430.1 / 2670)


def test_nz7_and_go5_lose_the_same_share():
    new, old = g.nz7(), g.nz7(gen_share="included")
    gs = g.tnuos_gen_share_cy()
    go_new, go_old = g.go5(2025), g.go5(2025, gen_share="included")
    for y in YEARS:
        assert new[y]["gbp_m"] == pytest.approx(old[y]["gbp_m"] * (1 - gs[y]), rel=0.02)   # FY mix
        assert go_new[y]["gbp_m"] == pytest.approx(go_old[y]["gbp_m"] * (1 - gs[y]))
        assert new[y]["gbp_m"] < old[y]["gbp_m"]
    with pytest.raises(ValueError):
        g.nz7(gen_share="bogus")


# ------------------------------------------------------------------ 2. BSUoS generator share

def test_bsuos_gen_share_from_cmp308_and_zero_from_april_2023():
    sh = {k: v["share"] for k, v in b.bsuos_gen_share_fy().items()}
    assert sh[2005] == 0.50 and sh[2012] == 0.50 and sh[2017] == 0.49 and sh[2020] == 0.47
    assert sh[2022] == 0.47 and sh[2023] == 0.0 and sh[2025] == 0.0
    assert 0.49 < sh[2015] < 0.50


def test_nz6_go4_symmetric_and_unchanged_after_2023():
    new, old = b.nz6(), b.nz6(gen_share="included")
    for y in (2024, 2025):
        assert new[y]["gbp_m"] == pytest.approx(old[y]["gbp_m"])
    assert new[2010]["gbp_m"] == pytest.approx(old[2010]["gbp_m"] * 0.5)
    gn, go = b.go4(2025), b.go4(2025, gen_share="included")
    gs = b.bsuos_gen_share_cy()
    for y in YEARS:
        assert gn[y]["gbp_m"] == pytest.approx(go[y]["gbp_m"] * (1 - gs[y]))


# ------------------------------------------------------------------ 3. GO5 by RPI

def test_control_index_rpi_then_cpih():
    assert g.control_index_fy(2015) == pytest.approx(g.rpi_fy(2015))
    assert g.control_index_fy(2020) == pytest.approx(g.rpi_fy(2020))
    assert g.control_index_fy(2022) / g.control_index_fy(2020) != pytest.approx(g.rpi_fy(2022) / g.rpi_fy(2020))


def test_go5_rpi_above_cpih_and_same_in_base_window():
    rpi, cpih = g.go5(2025, gen_share="included"), g.go5(2025, index="cpih", gen_share="included")
    base = sum(rpi[y]["carried_gbp_m"] for y in range(2002, 2006)) / 4
    assert base == pytest.approx(sum(cpih[y]["carried_gbp_m"] for y in range(2002, 2006)) / 4, rel=0.03)
    assert rpi[2020]["carried_gbp_m"] > cpih[2020]["carried_gbp_m"]      # RPI ran above CPIH
    assert rpi[2025]["carried_gbp_m"] > cpih[2025]["carried_gbp_m"]


# ------------------------------------------------------------------ 4. FiT levelisation, biomass CfD

def test_fit_levelisation_fund_values():
    lev = {k: round(v[0], 1) for k, v in s.read_fit_levelisation().items()}
    assert lev == {2010: 14.4, 2011: 150.8, 2012: 506.3, 2013: 691.0, 2014: 865.6,
                   2015: 1110.0, 2016: 1283.5, 2017: 1375.1, 2018: 1414.7, 2019: 1539.7,
                   2020: 1603.0, 2021: 1273.1, 2022: 1453.0, 2023: 1754.9, 2024: 1725.7, 2025: 1877.6}
    new, old = s.fit(), s.fit(basis="scheme_value")
    assert new[2009]["gbp_m"] == 0 and new[2020]["gbp_m"] < old[2020]["gbp_m"]
    assert new[2012]["basis"] == "measured"                            # C-008: SY1-5 published, no estimate
    assert s.FIT_FALLBACKS == []


# C-008 (input audit [internal ticket]): Ofgem's published levelisation fund for FIT years 1-5, £, as printed in each
# year's own annual report (file, table, PDF page). Typed from the PDFs, not from the engine.
FIT_SY1_5_OFGEM = {
    2010: (14_435_324.77, "FIT_annual_report_2010-11.pdf", "Levelisation fund row", 5),
    2011: (150_756_063.58, "FIT_annual_report_2011-12.pdf", "Table 7 (cont.)", 24),
    2012: (506_328_139, "FIT_annual_report_2012-13.pdf", "Table 9", 21),
    2013: (690_991_283, "FIT_annual_report_2013-14.pdf", "Levelisation fund (=A+B+C-D) row", 17),
    2014: (865_553_975, "FIT_annual_report_2014-15.pdf", "Levelisation fund (=A+B+C-D) row", 15),
}


def test_fit_sy1_5_are_ofgem_published_levelisation_funds_c008():
    """C-008: FIT years 1-5 are read from Ofgem's annual reports to the penny, each tagged measured with its
    own source id, in place of the old scheme value x SY6 ratio estimate (which gave 149.48 for SY2)."""
    lev, fy = s.read_fit_levelisation(), s.fit_fy()
    for y, (gbp, fname, _table, _page) in FIT_SY1_5_OFGEM.items():
        assert lev[y][0] == pytest.approx(gbp / 1e6, abs=5e-9), y
        assert lev[y][1] == "measured" and lev[y][2] == s.SRC_FIT_LEV_SY1_5, y
        assert fy[y] == lev[y], y
        assert (s.RAW / "ofgem_ro_fit" / fname).is_file(), fname
    assert set(s.FIT_AR_SY1_5) == set(FIT_SY1_5_OFGEM)


def test_fit_sy1_5_agree_with_the_2014_15_five_year_table_c008():
    """Not a choice between sources: the 2014-15 report's Figure 2.5 restates all five years, to the pound,
    and each equals that year's own report rounded to £1."""
    t = s.fit_sy1_5_figure_2_5()
    assert sorted(t) == sorted(FIT_SY1_5_OFGEM)
    for y, (gbp, *_rest) in FIT_SY1_5_OFGEM.items():
        assert t[y] == round(gbp), y


def test_fit_sy1_5_ratio_fallback_is_gone_c008():
    """No estimate left for SY1-5: the build records no 'fit-sy1-5-levelisation-ratio' fallback."""
    from gascf import bills as B
    from gascf import fallbacks as fb
    assert "fit-sy1-5-levelisation-ratio" not in fb.DECLARED
    B.record_netzero_fallbacks(B.CENTRAL)
    assert all(r["name"] != "fit-sy1-5-levelisation-ratio" for r in fb.recorded())


def test_cfd_biomass_split_adds_up():
    a, o, bio = s.cfd(), s.cfd(part="other"), s.cfd(part="biomass")
    for y in YEARS:
        assert o[y]["gbp_m"] + bio[y]["gbp_m"] == pytest.approx(a[y]["gbp_m"], abs=1e-6)
    assert bio[2020]["gbp_m"] > 300 and bio[2015]["gbp_m"] == 0


# ------------------------------------------------------------------ 5. carbon split

def test_carbon_split_sums_to_nz1c():
    fake = {y: {"gbp_m": 3000.0, "basis": "modelled", "source_id": "nz1c"} for y in YEARS}
    sp = c.nz1c_split(fake)
    for y in YEARS:
        t, p = sp[y]["carbon_price_receipts"], sp[y]["carbon_in_price"]
        assert t["gbp_m"] + p["gbp_m"] == pytest.approx(3000.0)
        assert t["gbp_m"] == pytest.approx(t["cps_gbp_m"] + t["ets_gbp_m"])
    assert sp[2005]["carbon_price_receipts"]["gbp_m"] == 0
    assert sp[2016]["carbon_price_receipts"]["cps_gbp_m"] == pytest.approx(1044.0)
    # s36 ticket 20 (0043 after 0078): the ETS part is now scaled to GB; the UK figure is unchanged and the
    # GB figure is re-pinned from the build (882.834732 x gb_share_of_uk(2024) 0.97199236)
    # s36 ticket 21: 2024 is now the printed auction total x the exact tonnes ratio (2,564.09 x 29,484,524 /
    # 85,634,344) instead of the Clock's 0.344307-rounded product; moves 1e-7, re-pinned from the build
    assert sp[2024]["carbon_price_receipts"]["ets_uk_gbp_m"] == pytest.approx(2564.09 * 29_484_524 / 85_634_344, abs=1e-9)
    assert sp[2024]["carbon_price_receipts"]["ets_gbp_m"] == pytest.approx(858.108611724838, abs=1e-9)
    assert sp[2013]["carbon_price_receipts"]["cps_gbp_m"] == pytest.approx(920.6 - 658.5)


# ------------------------------------------------------------------ 6. bridge can fail

def test_clock_input_matches_the_clocks_published_series():
    ck = R.clock_check()
    bad = {y: v for y, v in ck.items() if not v["ok"]}
    assert not bad, bad
    assert ck[2025]["blank"] == ["ro", "fit", "ccl", "ets", "tnuos"]      # flagged, not hidden


def test_clock_check_fails_on_a_changed_cell_or_a_false_blank():
    clock = {y: dict(v) for y, v in R.read_clock().items()}
    clock[2020]["ro"] += 1.0
    assert not R.clock_check(clock, years=[2020])[2020]["ok"]
    clock = {y: dict(v) for y, v in R.read_clock().items()}
    clock[2020]["fit"] = None                                            # a reader miss
    r = R.clock_check(clock, years=[2020])[2020]
    assert not r["ok"] and ("fit", None, pytest.approx(1764.0)) in r["mismatch"]


def test_clock_reads_the_stored_copy():
    assert R.CLOCK.parent.name == "subsidy_clock" and R.CLOCK.parents[1].name == "raw"


def test_unnamed_bill_line_is_caught():
    fake = {"netzero": [{"id": "NZ1"}, {"id": "S1.a"}, {"id": "NZ99"}], "fossil": [{"id": "GO1"}]}
    assert R.unnamed_lines(fake) == ["NZ99"]
