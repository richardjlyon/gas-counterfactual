"""Tests for schemes.py: the energy-saving obligations line (spec §15.4 item 1)."""
import pytest

from gascf import bills as B
from gascf import schemes as S
from gascf import waterfall as W

YEARS = range(2002, 2026)


@pytest.fixture(scope="module")
def sch():
    return S.schemes()


def test_every_year_has_a_value_and_source(sch):
    assert set(sch) == set(YEARS)
    for y, v in sch.items():
        assert v["gbp_m"] > 0, y                     # EEC from Apr 2002 to ECO/GBIS in 2025
        assert v["low"] <= v["gbp_m"] + 1e-9 <= v["high"] + 2e-9, y
        assert v["source_id"] and "UNSOURCED" not in v["source_id"], y


def test_central_is_the_lower_figure(sch):
    """Brief: where only a range exists, take the lower figure."""
    for y, v in sch.items():
        assert v["gbp_m"] == pytest.approx(v["low"]), y


def test_schemes_in_force_by_year(sch):
    by = {y: set(v["by_scheme"]) for y, v in sch.items()}
    assert by[2002] == {"EEC"} and by[2007] == {"EEC"}
    assert by[2008] == {"EEC", "CERT"}
    assert by[2010] == {"CERT", "CESP"} and by[2012] == {"CERT", "CESP"}
    assert by[2013] == {"ECO"} and by[2022] == {"ECO"}
    assert by[2023] == {"ECO", "GBIS"} and by[2025] == {"ECO", "GBIS"}


def test_cert_cesp_totals_add_back_to_the_evaluation():
    """Electricity share × the evaluation totals, spread over the obligation months."""
    tot = {"CERT": 0.0, "CESP": 0.0}
    for (y, m), d in S.monthly().items():
        for k in tot:
            if k in d:
                tot[k] += d[k]["central"]
    assert tot["CERT"] == pytest.approx(0.5 * 3507.0)
    assert tot["CESP"] == pytest.approx(0.5 * 702.1)


def test_annex4_reader_values():
    a4 = S.annex4_eco()
    first = a4[0]
    assert first[2] == pytest.approx(393.5)            # Apr-Sep 2015: £393.5m, no uprating
    last2025 = [p for p in a4 if p[0].year == 2025]
    assert all(500 < p[2] < 700 and 200 < p[3] < 300 for p in last2025)


def test_line_is_net_zero_only_and_in_one_step():
    b = B.build()
    for y in (2005, 2010, 2025):
        assert B.line(b[y], "NZ10")["group"] == "schemes"
        # NZ10 is counted less its 2001 on-the-road level (0097, ticket 26); add it back to check the scheme amount
        assert B.val(b[y], "NZ10") + b[y]["on_the_road"]["nz10_on_the_road_gbp_m"] == pytest.approx(S.schemes()[y]["gbp_m"])
        assert all(l["id"] != "NZ10" for l in b[y]["fossil"])
        st = {s["step"]: s for s in W.steps_for(b[y], y)}
        assert st[8]["value_gbp_m_nominal"] == pytest.approx(B.val(b[y], "NZ10"))
        assert abs(W.identity_error(W.steps_for(b[y], y))) < 0.01


def test_not_inside_same_in_both():
    """The same-in-both supplier block reads cap OC/PAAC/PAP/HAP/CO/DRC/IC/EBIT and SMNCC only,
    never the policy-cost line PC (where ECO sits in the cap)."""
    from gascf import same_in_both as sib
    assert "PC" not in sib.SUPPLIER_LINES + sib.METERING_LINES
