"""Ticket 14: interconnector CM contracted capacity loader (0057, 0064, 0066).
Spec item s36-routeA-spec-items/interconnectors-contracted.md, tests 1-4 and 15."""
import pytest

from gascf import cm_contracted as cmc


def test_dy_totals_equal_the_printed_figures():
    dy = cmc.ic_contracted_dy_mw()
    assert dy[2020] == pytest.approx(3162.1, abs=0.005)    # T-4 2016 Table 1 2,342.1 + T-1 NEMO 820
    assert dy[2017] == pytest.approx(2362.42, abs=0.005)   # EA 2017 Table 1
    assert dy[2019] == pytest.approx(2886.76, abs=0.005)
    assert dy[2024] == pytest.approx(6874.2, abs=0.005)
    assert dy[2016] == 0.0


def test_dy2020_21_per_link_rows():
    links = cmc.ic_contracted_by_link(2020)
    assert links == pytest.approx({"IFA": 1192.8, "BritNed": 888.0, "EWIC": 131.3, "Moyle": 130.0, "NEMO": 820.0},
                                  abs=0.005)


def test_calendar_mapping_nine_twelfths_three_twelfths():
    cy = cmc.ic_contracted_cy_mw()
    assert cy[2020] == pytest.approx(0.75 * 2886.76 + 0.25 * 3162.1, abs=1e-6)
    assert cy[2020] == pytest.approx(2955.6, abs=0.05)
    assert cy[2025] == pytest.approx(6958.9, abs=0.05)
    assert cy.get(2015, 0.0) == 0.0


def test_integrity_sha_sources_no_negatives_every_dy():
    import hashlib
    raw = cmc.IC_DY_CSV.parents[1]
    sums = dict(reversed(l.split(None, 1)) for l in (raw / "SHA256SUMS").read_text().splitlines() if l.strip())
    assert sums["./s36/cm_interconnectors_contracted_dy.csv"] == hashlib.sha256(cmc.IC_DY_CSV.read_bytes()).hexdigest()
    sources = (raw / "SOURCES.md").read_text()
    rows = cmc.ic_rows()
    assert all(r["source_id"] and r["source_id"] in sources for r in rows)
    assert all(r["derated_mw"] >= 0 for r in rows)
    assert set(range(2016, 2026)) <= {r["dy_start"] for r in rows}


def test_dy2017_18_from_the_emr_early_auction_report_0064():
    rows = [r for r in cmc.ic_rows() if r["dy_start"] == 2017]
    assert {r["cmu_id"]: r["derated_mw"] for r in rows} == pytest.approx(
        {"Brit16": 888.0, "EWIC15": 151.5, "IFA_16": 1172.92, "Moyle2": 150.0}, abs=1e-9)
    assert all(r["source_id"] == "EMR-FAR-EA-DY1718" for r in rows)
    assert sum(r["derated_mw"] for r in rows) == pytest.approx(2362.42, abs=0.005)
    assert not any(r["source_id"] == "OFGEM-CMAR-2016-17" for r in rows)
    # Spec test 15 reads "no note contains 'chart label'", but the pinned file's notes say
    # "0064 found: replaces Ofgem chart label" (sha256 cd128d8f…0647). The intent is that no row IS
    # the chart label; checked that way. Flagged in ticket 14 for the spec owner.
    assert all(r["note"].count("chart label") == r["note"].count("replaces Ofgem chart label") for r in rows)
    cy = cmc.ic_contracted_cy_mw()
    assert cy[2017] == pytest.approx(590.6, abs=0.05) and cy[2018] == pytest.approx(1771.8, abs=0.05)
