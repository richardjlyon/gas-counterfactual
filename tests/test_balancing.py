"""Tests for balancing.py (spec §3.1 NZ6, §3.2 GO4, §7.2, §12.2, §12.3)."""
import warnings

import pytest

from gascf import balancing as b

warnings.filterwarnings("ignore")


def test_nao_identity_2013_14():
    # MBSS March 2014 external + internal equals NAO's £1,002m exactly
    m = b.mbss_totals()[2013]
    assert m["external"] + m["internal"] == pytest.approx(b.nao_totals()[2013], abs=0.05)


def test_mbss_spot_values():
    m = b.mbss_totals()
    assert (m[2011]["external"], m[2011]["internal"]) == (822.0, 105.0)
    assert (m[2012]["external"], m[2014]["external"], m[2015]["external"]) == (802.5, 848.5, 868.4)
    assert (m[2014]["internal"], m[2015]["internal"]) == (141.3, 148.0)


def test_ibc_cross_check_ng_vs_nget():
    # NG 2010 Table 1 is still read (GB IBC 2006/07 for NZ6) but never enters B0 (v4-s34, D1)
    ng = b.ng_table1()
    assert ng[2004] == {"target": 320.0, "actual": 289.2}
    assert ng[2006]["actual"] == 495.0
    # v4-s33 pinned 366 (Ofgem 2003 'approximately £366 million'); the 2005 note prints 365.6
    assert b.ofgem_ibc_ew()[2001]["gbp_m"] == 365.6


def test_b0_four_years_from_one_source():
    """Richard, 14 Oct 2026 (D1): B0's four E&W IBC years (FY2001/02-2004/05) all come from ONE
    document, NGET's Dec 2005 incentive note ('Outturn IBC' 365.6, 379.0, 351.5, 384.1). Mixing in
    NG 2010 Table 1 (a different IBC definition: 289.2 for 2004/05) is the splice this forbids."""
    ibc = b.ofgem_ibc_ew()
    assert sorted(ibc) == [2001, 2002, 2003, 2004]
    assert {v["source_id"] for v in ibc.values()} == {b.SRC_IBC_2005}
    assert [ibc[fy]["gbp_m"] for fy in (2001, 2002, 2003, 2004)] == [365.6, 379.0, 351.5, 384.1]
    ng = b.ng_table1()
    assert all(ibc[fy]["gbp_m"] != ng[fy]["actual"] for fy in (2001, 2002, 2003, 2004))
    fy = b.baseline_fy("ibc")
    srcs = {s for k, v in fy.items() if k <= 2004 for s in v["source_id"].split("|")}
    assert srcs == {b.SRC_B0, b.SRC_IBC_2005}


def test_csv_whole_years_and_basis_switch():
    c = b.bsuos_csv_fy()
    for fy in range(2016, 2025):
        assert c[fy]["n_days"] in (365, 366), fy
    # from April 2023 recovery and cost diverge: NZ6 must use cost
    assert b.bsuos_fy()[2023]["gbp_m"] == pytest.approx(c[2023]["cost"])
    assert abs(c[2023]["recovery"] - c[2023]["cost"]) > 500


def test_bsuos_fy_complete_and_tagged():
    fy = b.bsuos_fy()
    assert set(fy) == set(range(2005, 2026))
    assert {k for k, v in fy.items() if v["basis"] == "estimated"} == {2006, 2010, 2025}
    for v in fy.values():
        assert v["source_id"] and v["gbp_m"] > 0


def test_workbook_external_below_bsuos_costs():
    # workbook = external costs only; BSUoS charges add SO internal costs
    w, fy = b.workbook_external_fy(), b.bsuos_fy()
    for y in range(2018, 2023):
        assert w[y] < fy[y]["gbp_m"] < 1.35 * w[y], y


def test_nz6_weighting_and_baseline():
    """s36 ticket 03 (0088): 2017-24 are summed from the daily files by calendar year (pinned in
    tests/test_bsuos_0088.py); the 1/4 : 3/4 rule stays for 2006-2016 and 2025."""
    fy, nz = b.bsuos_fy(), b.nz6(gen_share="included")
    assert set(nz) == set(b.YEARS)
    for y in list(range(2006, 2017)) + [2025]:
        assert nz[y]["gbp_m"] == pytest.approx(0.25 * fy[y - 1]["gbp_m"] + 0.75 * fy[y]["gbp_m"])
    daily = b.bsuos_daily()
    for y in range(2017, 2025):
        assert nz[y]["gbp_m"] == pytest.approx(sum(v for d, v in daily.items() if d.year == y))
    assert all(nz[y]["basis"] == "modelled" for y in b.BASE_WINDOW)


def test_go4_identity_and_range():
    g = b.go4(2024)
    for v in g.values():
        assert v["gbp_m"] == pytest.approx(v["energy_gbp_m"] + v["services_gbp_m"])
    assert 0.3 <= b.energy_share_2018() <= 0.7
    # go4_range (energy share 0.30/0.70) was dead code and is deleted (v4-s35, T1)
    assert not hasattr(b, "go4_range") and not hasattr(b, "ENERGY_SHARE_RANGE")
    # baseline-window mean reproduces itself in base-window years (gas index ≈ 1 on average)
    assert 300 < b.go4(2024, gen_share="included")[2003]["gbp_m"] < 700
    assert 150 < g[2003]["gbp_m"] < 350                 # s27b: generators' 50% off before Apr 2023


def test_nz6_fy_is_external_plus_internal():
    # NZ6 basis = costs incurred incl. SO internal: 2013/14 must equal NAO's £1,002m
    assert b.bsuos_fy()[2013]["gbp_m"] == pytest.approx(1002.0, abs=0.05)
    assert b.bsuos_fy()[2008]["gbp_m"] == pytest.approx(907.7 + 99.3, abs=0.05)


def test_energy_share_applies_to_external_b0_only():
    """v4-s35 (T6b): the FY2018/19 share is a share of EXTERNAL cost, so the gas-carried part of B0
    is s × B0/(1 + internal ratio); SO internal costs ride on CPIH with the services part."""
    s, ir = b.energy_share_2018(), b.internal_ratio()
    g = b.go4(2024, gen_share="included")
    for y, v in g.items():
        assert v["energy_share"] == pytest.approx(s)
        assert v["energy_share_of_b0"] == pytest.approx(s / (1 + ir))
    # in the base window the energy part's mean is s/(1+ir) of the nominal B0 (gas index mean = 1)
    import statistics
    cy = b.fy_to_cy({k: v["gbp_m"] for k, v in b.baseline_fy("ibc").items()}, b.BASE_WINDOW)
    b_nom = statistics.mean(cy.values())
    assert statistics.mean(g[y]["energy_gbp_m"] for y in b.BASE_WINDOW) == pytest.approx(s / (1 + ir) * b_nom)


# ---- ticket 48: BSUoS-basis gross-up factor (modelled key) + gb_over_ew sibling ----
import csv as _csv
import hashlib as _hashlib
import json as _json
from pathlib import Path as _Path

_T22_EXT = "tar_2008_09_t22_balancing_external_2007_08"
_T22_INT = "tar_2008_09_t22_balancing_internal_2007_08"


def test_table22_reference_rows_carry_document_page_and_table():
    import re
    import subprocess
    rows = b.table22_rows()
    assert set(rows) == {_T22_EXT, _T22_INT}
    assert rows[_T22_EXT]["value"] == 569.85 and rows[_T22_INT]["value"] == 112.92
    root = _Path(__file__).resolve().parents[1]
    pdf = root / "data/raw" / rows[_T22_EXT]["file"]               # the registered PDF the rows quote
    assert pdf.exists(), pdf
    pdf_sha = _hashlib.sha256(pdf.read_bytes()).hexdigest()        # hash the actual PDF, not just a typed literal
    page38 = subprocess.run(["pdftotext", "-layout", "-f", "38", "-l", "38", str(pdf), "-"],
                            check=True, capture_output=True, text=True).stdout
    flat38 = re.sub(r"\s+", " ", page38)                           # the row spans table columns; -layout keeps it
    for rid in (_T22_EXT, _T22_INT):
        r = rows[rid]
        assert r["units"] == "£m, cash" and r["period"] == "FY2007/08"
        assert "Transmission Annual Report for 2008-09" in r["document"] and "48/10" in r["document"]
        assert r["file"] == "ofgem_s18b/transmission_annual_report_final.pdf"
        assert r["sha256"] == pdf_sha                              # the stored sha256 is the actual PDF's
        assert r["page"] == 38 and r["table"] == "Table 22 - NGET Revenue Summary"
        assert r["quote"] in flat38                                # verbatim on page 38's text
        assert str(r["value"]) in r["quote"]                       # the value appears in the quote
    assert rows[_T22_EXT]["value"] == b.tar_balancing()[2007]["external"]
    assert rows[_T22_INT]["value"] == b.tar_balancing()[2007]["internal"]


def test_table22_rows_raise_when_a_field_is_missing(tmp_path):
    data = _json.loads(b.TABLE22_REF.read_text())
    del data["rows"][_T22_EXT]["page"]
    p = tmp_path / "ref.yaml"
    p.write_text(_json.dumps(data))
    with pytest.raises(ValueError, match="page"):
        b.table22_rows(p)


def test_bsuos_basis_grossup_factor_is_computed_from_the_two_rows():
    rows = b.table22_rows()
    exp = 1 + rows[_T22_INT]["value"] / rows[_T22_EXT]["value"]
    assert b.bsuos_basis_grossup_factor() == pytest.approx(exp, abs=1e-12)
    assert b.bsuos_basis_grossup_factor() == pytest.approx(1.198157, abs=1e-6)
    assert b.bsuos_basis_grossup()["inputs"] == [_T22_INT, _T22_EXT]
    assert b.bsuos_basis_grossup_factor() == pytest.approx(1 + b.internal_ratio(), abs=1e-12)


def test_bsuos_basis_grossup_factor_is_computed_not_typed(tmp_path):
    data = _json.loads(b.TABLE22_REF.read_text())
    data["rows"][_T22_INT]["value"] = 225.84
    p = tmp_path / "ref2.yaml"
    p.write_text(_json.dumps(data))
    b.table22_rows.cache_clear()
    assert b.bsuos_basis_grossup_factor(p) == pytest.approx(1.396315, abs=1e-6)
    data2 = _json.loads(b.TABLE22_REF.read_text())
    del data2["rows"][_T22_INT]
    p2 = tmp_path / "ref3.yaml"
    p2.write_text(_json.dumps(data2))
    b.table22_rows.cache_clear()
    with pytest.raises(ValueError):
        b.bsuos_basis_grossup_factor(p2)
    b.table22_rows.cache_clear()
    root = _Path(__file__).resolve().parents[1]
    for base in ("src", "tools"):
        for f in (root / base).rglob("*.py"):
            t = f.read_text()
            for lit in ("1.198", "1.1981", "0.198157", "112.92", "569.85"):
                assert lit not in t, f"{f} contains literal {lit}"


def test_gb_over_ew_factor_matches_the_known_value():
    by = b.gb_over_ew_by_year()
    assert by[2002] == pytest.approx(1.112065, abs=1e-6)
    assert by[2003] == pytest.approx(1.109466, abs=1e-6)
    assert by[2004] == pytest.approx(1.107464, abs=1e-6)
    assert by[2005] == pytest.approx(1.105507, abs=1e-6)
    assert b.gb_over_ew() == pytest.approx(1.108626, abs=1e-6)
    import statistics as _st
    assert b.gb_over_ew() == pytest.approx(_st.mean(by.values()), abs=1e-12)


def test_gb_over_ew_factor_is_computed_not_typed(tmp_path, monkeypatch):
    base = b.gb_over_ew_by_year()
    # inputs: the four registered CSVs and their sha256 (checked before any monkeypatch)
    shas = {_Path(i["path"]).name: i["sha256"] for i in b.gb_over_ew_inputs()}
    assert shas["s18c-demanddata_2002.csv"] == "c552c91901f662a3f5bc30bdaf6c100fc32be7f80268eb15323d3ccace141e29"
    assert shas["s18c-demanddata_2005.csv"] == "bd778decf8c742f9405d813d485d6be1216b98052c2f2fd44548879e35480f27"
    # a temp copy of the 2005 CSV with every ENGLAND_WALES_DEMAND halved -> 2005 ratio doubles
    rows = list(_csv.DictReader(b.DEMAND[2005].open()))
    out = tmp_path / "demand2005.csv"
    with out.open("w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            r = dict(r)
            r["ENGLAND_WALES_DEMAND"] = str(float(r["ENGLAND_WALES_DEMAND"]) / 2)
            w.writerow(r)
    monkeypatch.setitem(b.DEMAND, 2005, out)
    b.gb_over_ew_by_year.cache_clear()
    by2 = b.gb_over_ew_by_year()
    assert by2[2005] == pytest.approx(base[2005] * 2, abs=1e-6)
    exp_mean = (base[2002] + base[2003] + base[2004] + base[2005] * 2) / 4
    assert b.gb_over_ew() == pytest.approx(exp_mean, abs=1e-6)
    b.gb_over_ew_by_year.cache_clear()
    # missing year raises
    monkeypatch.setattr(b, "DEMAND", {y: b.RAW / f"neso/s18c-demanddata_{y}.csv" for y in (2002, 2003, 2004)})
    b.gb_over_ew_by_year.cache_clear()
    with pytest.raises(ValueError):
        b.gb_over_ew_by_year()
    b.gb_over_ew_by_year.cache_clear()


def test_gb_over_ew_no_typed_literals_in_source():
    root = _Path(__file__).resolve().parents[1]
    for base in ("src", "tools"):
        for f in (root / base).rglob("*.py"):
            t = f.read_text()
            assert "1.1086" not in t and "1.108626" not in t, f"{f} contains gb_over_ew literal"


def test_balancing_factors_block_fy_is_derived_from_the_reference_period(monkeypatch):
    """Review ST5: the block's `fy` comes from the Table 22 reference rows' period, not a 2007/08 literal; a
    different reference period flows through."""
    from gascf import balancing_factors_block as BFB
    rows = b.table22_rows()
    periods = {rows[rid]["period"].removeprefix("FY") for rid in b.bsuos_basis_grossup()["inputs"]}
    assert len(periods) == 1
    blk = BFB.block({})
    assert blk["bsuos_basis_grossup"]["fy"] == periods.pop() == "2007/08"
    monkeypatch.setattr(b, "table22_rows", lambda *a, **k: {rid: {**v, "period": "FY2010/11"} for rid, v in rows.items()})
    assert BFB.block({})["bsuos_basis_grossup"]["fy"] == "2010/11"
