"""Tests for grid.py (spec §3.1 NZ7, §3.2 GO5, §7.1, §7.3, §12.2 item 9, §12.3)."""
import pytest

from gascf import grid as g


def test_baseline_pieces_spot_values():
    p = g.baseline_pieces()
    assert p["ngc"]["fy"] == {2001: 758, 2002: 747, 2003: 736, 2004: 724, 2005: 714}
    # v4-s35 (T12): 2005/06 from the Dec 2004 final proposals Table 2.3 (draft: 114.5 / 47.3)
    assert p["spt"]["fy"][2002] == 116.7 and p["spt"]["fy"][2005] == 127.5
    assert p["shetl"]["fy"][2004] == 50.6 and p["shetl"]["fy"][2005] == 52.56


def test_baseline_is_rpi_restated_not_cpih():
    # spot: NGC 2002/03 in 1999/00 prices restated with RPI
    fy = g.baseline_fy_nominal()
    ngc = 747 * g.rpi_fy(2002) / g.rpi_fy(1999)
    scot = (116.7 + 50.6) * g.rpi_fy(2002) / g.rpi_fy(2002)
    assert fy[2002] == pytest.approx(ngc + scot, rel=1e-9)
    assert 900 < fy[2002] < 1100


def test_continuity_into_tpcr4_2006_07():
    # §12.2 item 9: the 2006/07 opening revenue (1,216 £m, 2004/05 prices) within ±15%
    # of the 2005/06 assembled baseline restated to 2004/05 prices — report-only tolerance
    t = g.tpcr4_2006_07()
    assert t["elec_2004_05_prices"] == 1005 + 160 + 51
    b05 = g.baseline_fy_nominal()[2005] * g.rpi_fy(2004) / g.rpi_fy(2005)
    ratio = t["elec_2004_05_prices"] / b05
    print(f"TPCR4 2006/07 vs assembled 2005/06 (2004/05 prices): {ratio:.3f}")
    assert 0.85 < ratio < 1.35       # TPCR4 added BETTA/TIRG revenue; printed, not hidden


def test_tnuos_fy_spot_values_and_coverage():
    fy = g.tnuos_fy()
    assert set(range(2005, 2027)) <= set(fy)
    spots = {2007: 1298.72, 2008: 1421.63, 2009: 1465.1, 2010: 1562, 2012: 1948, 2013: 2153,
             2014: 2477.3, 2015: 2636.7, 2016: 2708.7, 2017: 2631.5, 2018: 2670, 2019: 2837.4,
             2020: 2843.0, 2021: 3318, 2024: 4188.5, 2025: 5087.0}
    for k, v in spots.items():
        assert fy[k]["gbp_m"] == pytest.approx(v), k
    assert fy[2022]["gbp_m"] == pytest.approx(3594.25, abs=0.01)
    assert fy[2023]["gbp_m"] == pytest.approx(4416.42, abs=0.01)
    for v in fy.values():
        assert v["basis"] in ("measured", "modelled", "estimated") and v["source_id"]


def test_ofto_not_added_twice():
    # 2024/25: total = TO income + other pass-through + offshore, read from Table 16
    assert g.tnuos_fy()[2024]["gbp_m"] == pytest.approx(3248.7 + 59.8 + 880.0, abs=0.05)


def test_nz7_time_weighting_identity():
    fy = g.tnuos_fy()
    nz = g.nz7(gen_share="included")
    assert set(nz) == set(g.YEARS)
    for y in range(2006, 2026):
        assert nz[y]["gbp_m"] == pytest.approx(0.25 * fy[y - 1]["gbp_m"] + 0.75 * fy[y]["gbp_m"])
    assert nz[2003]["basis"] == "modelled"


def test_nlr_allowances_spot():
    a = g.nlr_allowances()
    assert a["tpcr4"]["annual"][2007] == pytest.approx(333 + 11.6 + 52.5)
    assert a["riio_t1"]["total_8yr"] == pytest.approx(4806.4 + 643.7 + 209.0, abs=0.05)
    assert a["riio2"]["total_5yr"] == pytest.approx(1765.8 + 794.3 + 458.0)


def test_renewal_range_and_go5():
    r = g.renewal_allowance()
    for y, v in r.items():
        assert v["low"] == 0 and v["low"] <= v["central"] <= v["high"] and v["basis"] == "estimated"
    assert r[2002]["high"] == 0                     # no renewal before TPCR4
    assert r[2024]["high"] > r[2010]["high"] > 0
    # v4-s35 (T4, Richard): central = the whole allowance above the 2002-05 level (was half)
    assert all(v["central"] == v["high"] for v in r.values())
    go = g.go5(2024, index="cpih", gen_share="included")
    c = g.dfl.cpih()
    assert go[2024]["carried_gbp_m"] == pytest.approx(g.g0(2024))
    assert go[2010]["carried_gbp_m"] == pytest.approx(g.g0(2024) * c[2010] / c[2024])


def test_riio2_return_per_to_from_the_fd_annexes():
    """v4-s34 (fact-check W4): each TO's own RIIO-2 'Allowed return on capital' (SHET 2.69%, not
    NGET's 2.81%), weighted by FD non-load-related capex."""
    r = g.riio2_returns()
    assert r == {"NGET": 0.0281, "SHET": 0.0269, "SPT": 0.0281}
    w = (1765.8 * 0.0281 + 794.3 * 0.0269 + 458.0 * 0.0281) / (1765.8 + 794.3 + 458.0)
    assert g.riio2_return_weighted() == pytest.approx(w, abs=1e-9)
    assert g.allowed_return("riio2") == pytest.approx(w)
    assert "riio2" not in g.RETURN


def test_index_switch_cites_the_riio_et2_pcfh():
    """v4-s35 (T8): RPI->CPIH switch cited to RIIO-ET2 PCFH para 2.17 (was Finance Annex 2.24)."""
    assert g.SRC_INDEX == "ofgem-riio-et2-pcfh-2.17-pi-rpi-to-cpih"
    g._check_index_source()


def test_renewal_is_a_rav_roll_forward():
    """v4-s35 (T3): each FY's excess NLR capex enters an indexed RAV, depreciates straight line
    over 45 years and earns the CURRENT control's real return on the remaining balance
    (RIIO-ET2 PCFH para 4.1, 2.17). Re-derived here independently, FY by FY."""
    exc = g.renewal_excess_fy()
    assert min(exc) == 2007 and all(v >= 0 for v in exc.values())
    I = {fy: g.control_index_fy(fy) for fy in range(2001, 2026)}
    ctrl = lambda fy: "tpcr4" if fy <= 2012 else ("riio_t1" if fy <= 2020 else "riio2")
    def r_fy(t):
        return sum((e / 45 + g.allowed_return(ctrl(t)) * e * (1 - (t - v) / 45)) * I[t] / I[v]
                   for v, e in exc.items() if v <= t)
    r = g.renewal_allowance()
    for y in (2008, 2013, 2021, 2024, 2025):
        assert r[y]["central"] == pytest.approx(0.25 * r_fy(y - 1) + 0.75 * r_fy(y), rel=1e-12)
    # first-year payment = depreciation + return on the full addition
    assert r_fy(2007) == pytest.approx(exc[2007] * (1 / 45 + 0.0505))
    assert 400 < r[2024]["central"] < 470                 # triage_effects 'rav' R(2024) = 434.2 (pre-T12)


def test_scottish_g0_from_betta_final_proposals_table_2_3():
    """v4-s35 (T12): SPT 127.5 and SHETL 52.56 (2005/6, £m 2002/3 prices), Dec 2004 final
    proposals Table 2.3; FY2001/02-04/05 unchanged (116.7, 50.6)."""
    p = g.baseline_pieces()
    assert p["spt"]["fy"][2005] == 127.5 and p["shetl"]["fy"][2005] == 52.56
    assert p["spt"]["fy"][2004] == 116.7 and p["shetl"]["fy"][2004] == 50.6
    assert g.baseline_fy_nominal()[2005] == pytest.approx(1025.6, abs=0.1)   # triage_effects betta_final
