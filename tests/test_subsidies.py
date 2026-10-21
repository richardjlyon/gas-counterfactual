"""Strand s20c: RO, FiT, CfD, CM_paid, CCL (spec §3.1 NZ2–NZ4, NZ8; §5.2; §12.2 items 1–2)."""
import pytest

from gascf import subsidies as s


def test_ro_sy1_4_spot_values():
    ro = s.read_ro_sy1_4()
    # 2002-03: E&W 4,973,091 × £45.94 + Scotland 478,358 × £53.55 (2005-06 report, Tables 1-2)
    assert ro[2002] == pytest.approx((4_973_091 * 45.94 + 478_358 * 53.55) / 1e6)
    assert ro[2005] == pytest.approx(582.77, abs=0.01)       # includes NI 41,295 × £42.54


def test_ro_sy5_8_spot_values():
    ro = s.read_ro_sy5_8()
    assert ro[2006] == pytest.approx(720.1, abs=0.1)
    assert ro[2009] == pytest.approx(21_337_205 * 52.36 / 1e6)


def test_ro_reproduces_ofgem_sy23_scheme_value_within_10m():
    # spec §5.2 / §12.2 item 1: ROCs × worth reproduces Ofgem's £7.70bn within £10m
    a = s.read_ro_sy9_23()
    assert abs(a[2024]["gbp_m"] - s.ro_sy23_printed_bn() * 1000) < 10
    assert a[2010]["rocs_m"] == 25.0 and a[2010]["worth"] == 51.34


def test_ro_2025_26_ex_ante():
    r = s.read_ro_2025_26_ex_ante()
    assert r["rocs"] == 119_412_356 and r["buyout"] == 67.06


def test_time_weighting_not_start_year():
    ro = s.ro()
    fy = s.ro_fy()
    assert ro[2002]["gbp_m"] == pytest.approx(0.75 * fy[2002][0])
    assert ro[2024]["gbp_m"] == pytest.approx(0.25 * fy[2023][0] + 0.75 * fy[2024][0])
    assert ro[2025]["basis"] == "estimated" and ro[2024]["basis"] == "measured"


def test_fy_to_cy_identity_money_preserved():
    fy = {2010: 100.0, 2011: 200.0}
    with pytest.raises(ValueError):
        s.fy_to_cy(fy, range(2010, 2013))                    # CY2012 needs FY2012, missing
    # with the following years zero, every pound lands in exactly one calendar year
    cy = s.fy_to_cy({**fy, 2012: 0.0, 2013: 0.0}, range(2010, 2014))
    assert sum(cy.values()) == pytest.approx(300.0)


def test_fit_values():
    f = s.read_fit_scheme_value()
    assert f[2010] == 15 and f[2024] == 1844
    fit = s.fit(basis="scheme_value")                   # pre-s27 basis; levelisation in test_s27b_netzero
    assert fit[2009]["gbp_m"] == 0 and fit[2010]["gbp_m"] == pytest.approx(0.75 * 15)
    q = s.read_fit_quarterly_payments()
    assert sorted(q[16]) == [1, 2, 3, 4]
    # FIT payments are below the scheme value (no qualifying costs): SY15 check
    assert sum(q[15].values()) < f[2024]


def test_cfd_and_cm_match_clock_series():
    # s18c: CY sums match the Subsidy Clock to the pound; spot values in £m
    cfd, cm = s.cfd(), s.CM_paid()
    assert round(cfd[2022]["gbp_m"]) == -346 and round(cfd[2024]["gbp_m"]) == 2360
    assert cfd[2015]["gbp_m"] == 0
    assert round(cm[2024]["gbp_m"]) == 1257 and cm[2015]["gbp_m"] == 0


def test_ccl_electricity_and_no_cps():
    c = s.ccl_electricity()
    assert c[2002]["gbp_m"] == pytest.approx(623.0, abs=0.01)
    assert c[2024]["gbp_m"] == pytest.approx(806.77, abs=0.01)
    assert c[2025]["basis"] == "estimated"
    t = s.read_ccl_table_1b()
    # carbon once (§6): the CPF receipts are never inside NZ8
    assert c[2016]["gbp_m"] == pytest.approx(t[2016]["electricity"]) != t[2016]["electricity"] + t[2016]["cpf_receipts"]


def test_every_row_tagged():
    for f in (s.ro, s.fit, s.cfd, s.CM_paid, s.ccl_electricity):
        out = f()
        assert sorted(out) == list(range(2002, 2026))
        for r in out.values():
            assert r["basis"] in ("measured", "modelled", "estimated") and r["source_id"]
