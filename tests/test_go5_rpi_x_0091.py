"""Decision 0091 (fully ruled 17 Oct 2026): grid index at the price controls' own X values.

Item A = fit|A3: NGET's +6.0% real step in FY2006/07, weighted by 2005/06 shares.
Item B = B1: 2012/13 at X = 0 (a stated exclusion). No X under RIIO.
Reference: reports-programme b-items-calc/b17_optb.py / .json, case fit|A3 (A6.2_714_1999p|annual_rule)."""
import pytest

from gascf import grid as g


def test_base_window_multiplier_is_one():
    m = g.rpi_x_multiplier_fy()
    assert all(m[fy] == 1.0 for fy in range(2001, 2006))


def test_2006_07_step_is_nget_6pct_weighted_by_2005_06_shares():
    # b17 fit|A3: NGET 714 (1999/00 £), SPT 127.5 and SHETL 52.56 (2002/03 £), all to 2004/05 £ by RPI
    s = g.rpi_x_2006_step()
    assert s["shares"]["NGET"] == pytest.approx(0.8085594, abs=5e-7)
    assert s["shares"]["SPT"] == pytest.approx(0.1355585, abs=5e-7)
    assert s["shares"]["SHETL"] == pytest.approx(0.0558820, abs=5e-7)
    assert s["step"] == pytest.approx(1.0485136, abs=5e-7)     # +4.85%
    assert g.rpi_x_multiplier_fy()[2006] == s["step"]


def test_tpcr4_path_2007_08_to_2011_12():
    # TPCR4 FP 206/06 Tables 3.1, 4.1, 5.1, base price control revenue allowance (2004/05 £),
    # NGET + SHETL + SPTL: 1129.5 (2006/07), 1179.3, 1203.3, 1227.2, 1252.3, 1277.4
    m = g.rpi_x_multiplier_fy()
    step = 1.0485135662393574
    for fy, tot in zip(range(2007, 2012), (1179.3, 1203.3, 1227.2, 1252.3, 1277.4)):
        assert m[fy] == pytest.approx(step * tot / 1129.5, rel=1e-9), fy


def test_2012_13_reset_at_x0_and_flat_under_riio():
    # Item B = B1: 2012/13 at X = 0 (stated exclusion: no company's TII share is published);
    # RIIO from 2013/14: no X. b17 fit|A3 m_end = 1.1858089681400223
    m = g.rpi_x_multiplier_fy()
    assert m[2012] == m[2011]
    assert m[2012] == pytest.approx(1.1858089681400223, rel=1e-9)
    assert all(m[fy] == m[2012] for fy in range(2013, 2026))


def test_rpi_x_go5_effect_matches_b17_fit_a3():
    # b17_optb.json fit|A3 (A6.2_714_1999p|annual_rule): sum0225 = 4947.857, d2025 = 283.916,
    # £m 2025 money, RB basis (generators' share removed). The RB grid line falls by this much.
    from gascf import bills as B
    rpi = g.go5(B.PRICE_BASE, B.YEARS, index="rpi", gen_share="removed")
    rpx = g.go5(B.PRICE_BASE, B.YEARS, index="rpi_x", gen_share="removed")
    d = {y: B.real(rpx[y]["gbp_m"] - rpi[y]["gbp_m"], y) for y in B.YEARS}
    assert all(abs(d[y]) < 1e-9 for y in range(2002, 2006))          # base window untouched
    assert sum(d.values()) == pytest.approx(4947.9, abs=5)
    assert d[2025] == pytest.approx(283.9, abs=1)
    assert all(rpx[y]["index"] == "rpi_x" for y in B.YEARS)


def test_central_rpi_unchanged_by_the_switch():
    from gascf import bills as B
    assert B.CENTRAL.go5_index == "rpi"
    assert "rpi_x" in g.GO5_INDEX_OPTIONS


def test_share_restatement_uses_ons_chaw_fy_values():
    # ONS CHAW (src/rb-b/rpi-x/ons-chaw-2026-10-17.csv, sha256 259a40ec…5b08), FY = 0.75 CY + 0.25 CY+1:
    # b17 fit|A3_rpi fy1999 166.625, fy2002 177.475, fy2004 188.025
    assert g.rpi_fy(1999) == pytest.approx(166.625, abs=1e-9)
    assert g.rpi_fy(2002) == pytest.approx(177.475, abs=1e-9)
    assert g.rpi_fy(2004) == pytest.approx(188.025, abs=1e-9)


def test_rpi_x_is_a_range_row_not_a_methods_page_switch():
    """Decision 0112 (Richard Lyon, 19 Oct 2026, item 1.4 option (a)) moved the RPI-X row into the printed range
    (commit 003f9c6); before it, 0091 placed it on the methods page. Exactly one row, in SWITCHES, none on the
    methods page."""
    from gascf import bills as B
    ranked = [s for v in B.SWITCHES.values() for s in v if s.go5_index == "rpi_x"]
    methods = [s for v in B.METHOD_SWITCHES.values() for s in v if s.go5_index == "rpi_x"]
    assert len(ranked) == 1 and ranked[0] == B.replace(B.CENTRAL, go5_index="rpi_x")
    assert B.SWITCHES[B.RPI_X] == (ranked[0],)
    assert methods == []
