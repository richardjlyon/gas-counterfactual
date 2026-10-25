"""Ticket 20: UK auction revenue 2008-12 as traced (0056), the 2012 Phase III row (0067), the 2008 power
share (0068) and ETS-only GB scaling of tax collected in every year (0043 as worded after 0078).
Spec: reports-programme s36-routeA-spec-items/ets-phase2-auctions.md, tests 1-14 (13c runs in the Clock)."""
from __future__ import annotations

import pytest

from gascf import ets_auctions as E


def test_phase2_loader_total_is_the_published_1316_593():
    assert sum(E.phase2_revenue_cy().values()) == pytest.approx(1316.593, abs=0.0005)


def test_phase2_loader_years():
    r = E.phase2_revenue_cy()
    for y, v in {2008: 54.443, 2009: 299.676, 2010: 437.011, 2011: 353.978, 2012: 171.485}.items():
        assert r[y] == pytest.approx(v, abs=0.0005), y
    assert set(r) == set(range(2008, 2013))


def test_phase2_series_excludes_phase3_and_reads_published_not_derived():
    import csv
    from datetime import date, datetime
    rows = list(csv.DictReader(E.PHASE2.open()))
    dates = [datetime.strptime(r["date"], "%d %B %Y").date() for r in rows]
    assert max(dates) <= date(2012, 10, 25)
    assert sum(int(r["volume_sold_euas"]) for r in rows) == 122_810_352
    assert E.phase2_revenue_cy()[2008] == 54.443                      # not 54.443179 (derived)
    derived = sum(float(r["derived_gbp_sold_x_price_x_rate"]) for r in rows) / 1e6
    assert abs(derived - 1316.593) == pytest.approx(1.84, abs=0.01)


def test_phase2_loader_refuses_a_changed_file_or_row_count(tmp_path):
    lines = E.PHASE2.read_text().splitlines(keepends=True)
    short = tmp_path / "p2.csv"
    short.write_text("".join(lines[:-1]))
    with pytest.raises(ValueError, match="sha256"):
        E.phase2_revenue_cy(short)
    with pytest.raises(ValueError, match="30 rows"):
        E.phase2_revenue_cy(short, sha256=E._sha(short))


def test_phase3_2012_row_is_separate_61_139(tmp_path):
    p3 = E.phase3_2012()
    assert p3["gbp_m"] == pytest.approx(61.139, abs=0.0005)
    assert p3["rows"] == 2 and p3["allowances"] == 12_258_000
    assert p3["phase"] == "III" and p3["source_id"] == "DECC-ARA-2012-13-HC18"
    lines = E.PHASE3.read_text().splitlines(keepends=True)
    extra = tmp_path / "p3_extra.csv"
    extra.write_text("".join(lines) + lines[-1])
    with pytest.raises(ValueError, match="2 rows"):
        E.phase3_2012(extra, sha256=E._sha(extra))
    jan = tmp_path / "p3_jan.csv"
    jan.write_text("".join(lines).replace("5 Dec 2012", "16 Jan 2013"))
    with pytest.raises(ValueError, match="Nov-Dec 2012"):
        E.phase3_2012(jan, sha256=E._sha(jan))
    with pytest.raises(ValueError, match="sha256"):
        E.phase3_2012(jan)


def _cell_rows(path, sheet, rows):
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    return {r: next(ws.iter_rows(min_row=r, max_row=r, values_only=True)) for r in rows}


def test_2008_share_is_0068_stand_in_from_the_registered_tables():
    # DESNZ GHG 1990-2024 sheet 1.2: V12 (Electricity supply total) less V10 (power stations - MSW), 2008
    g = _cell_rows(E.GHG_TABLES, "1.2", (6, 10, 12))
    assert g[6][21] == "2008"
    num = g[12][21] - g[10][21]
    # EEA Union Registry v82, "2. Verified emissions", 2008, GB 20-99 (Excel row 38988) + XI 20-99 (row 90134)
    e = _cell_rows(E.EEA_REGISTRY, "Sheet1", (38988, 90134))
    assert [str(e[38988][k]) for k in (1, 2, 4, 5)] == ["GB", "20-99", "2. Verified emissions", "2008"]
    assert [str(e[90134][k]) for k in (1, 2, 4, 5)] == ["XI", "20-99", "2. Verified emissions", "2008"]
    den = (e[38988][7] + e[90134][7]) / 1e6
    s = E.stand_in_share(2008)
    assert num == pytest.approx(171.799836, abs=1e-6) and den == pytest.approx(265.055646, abs=1e-6)
    assert s["numerator_mtco2"] == pytest.approx(num, abs=1e-9)
    assert s["denominator_mtco2"] == pytest.approx(den, abs=1e-9)
    assert s["value"] == pytest.approx(0.648165, abs=1e-6)


def test_2008_share_status_guard_refuses_an_unsourced_share(tmp_path):
    from gascf.pending import PendingSourceError
    rec = E.share_2008_record()
    assert rec["status"] == "SOURCED" and float(rec["value"]) == pytest.approx(0.648165164, abs=1e-9)
    fixture = tmp_path / "share2008.csv"
    fixture.write_text(E.SHARE_2008.read_text().replace("SOURCED", "PENDING-0068"))
    with pytest.raises(PendingSourceError, match="ets_power_share_2008"):
        E.power_share(2008, share_2008_file=fixture)
    assert E.power_share(2008)["value"] == pytest.approx(0.648165, abs=1e-6)


def test_2008_share_provenance_is_registered_not_the_research_note():
    s = E.power_share(2008)
    assert (s["numerator_source_id"], s["denominator_source_id"]) == (
        "desnz-final-ghg-1990-2024-t1.2", "eea-ets-union-registry-v82-sep2026")
    sources = (E.RAW / "SOURCES.md").read_text()
    sums = (E.RAW / "SHA256SUMS").read_text()
    for sid in (s["numerator_source_id"], s["denominator_source_id"]):
        assert sid in sources
    assert "39849813643d6ed812c10030fb4fdcba98e598d7f8a890a446450c74baba66fa  ./s36/ets/final-greenhouse" in sums
    assert "6eeb040e380072049823b8919e27503bf60b90573c1d918a6e1fd741d9a23e5a  ./s36/ets/ETS_Database" in sums
    assert f"{E._sha(E.SHARE_2008)}  ./s36/ets/ets-power-share-2008.csv" in sums
    assert "research-model-items" not in s["numerator_source_id"] + s["denominator_source_id"]


def _split():
    from gascf import carbon
    nz1c = {y: {"gbp_m": 5000.0, "basis": "modelled", "source_id": "toy-nz1c"} for y in range(2002, 2026)}
    return carbon.nz1c_split(nz1c)


def _to_2024(v, y):
    from gascf import deflator_cpih as d
    c = d.cpih()
    return v * c[2024] / c[y]


def test_2010_power_gb_in_2024_prices():
    """Spec test 6 gives 412.45 at the rounded share 0.657; the 0055 stand-in is the unrounded ratio
    (ticket 21: to 1e-6), 155.990553 / 237.343841 = 0.657234, so 437.011 x 0.657234 x 0.973859 (GB 2015,
    nearest published year) x 132.9 / 90.1 = 412.58."""
    t = _split()[2010]["carbon_price_receipts"]
    assert t["ets_uk_gbp_m"] == pytest.approx(437.011 * 0.657234, abs=0.001)
    assert _to_2024(t["ets_gbp_m"], 2010) == pytest.approx(412.58, abs=0.01)


def test_2012_phase3_row_is_its_own_field_beside_phase2():
    """Spec test 9 gives 53.66 and 150.51 at the rounded 0.651; at the stand-in 0.651151 (unrounded):
    61.139 x 0.651151 x 0.973859 x 132.9/96.0 = 53.67 and 171.485 x ... = 150.54 (2024 £, GB)."""
    t = _split()[2012]["carbon_price_receipts"]
    assert _to_2024(t["ets_phase3_gbp_m"], 2012) == pytest.approx(53.67, abs=0.01)
    assert _to_2024(t["ets_phase2_gbp_m"], 2012) == pytest.approx(150.54, abs=0.01)
    assert t["ets_phase2_gbp_m"] + t["ets_phase3_gbp_m"] == pytest.approx(t["ets_gbp_m"], abs=1e-9)
    assert "ets_phase3_gbp_m" in _split()[2008]["carbon_price_receipts"]
    assert _split()[2008]["carbon_price_receipts"]["ets_phase3_gbp_m"] == 0.0


def test_2008_power_gb_at_the_sourced_share():
    # 54.443 x 0.648165 x 0.973859 x 132.9/86.2 = 52.99 (spec test 11; 2024 £, GB)
    assert _to_2024(_split()[2008]["carbon_price_receipts"]["ets_gbp_m"], 2008) == pytest.approx(52.99, abs=0.01)


def test_only_the_ets_part_is_scaled_to_gb_in_every_year():
    from gascf import carbon
    from gascf.system_costs import gb_share_of_uk
    sp, cpf = _split(), carbon.cpf_receipts()
    for y in range(2002, 2026):
        t = sp[y]["carbon_price_receipts"]
        assert t["gb_scaled_components"] == ["ets"]
        assert t["cps_uk_gbp_m"] == t["cps_gbp_m"] == cpf[y][0]          # 0078: CPS is not scaled
        assert t["gbp_m"] == pytest.approx(gb_share_of_uk(y)[0] * t["ets_uk_gbp_m"] + t["cps_uk_gbp_m"], abs=1e-9)
    # ETS scaled off 2013-24, 2024 £. Was 325.9 on the Clock's v4-s35 series (gb_scaling_0078.json); s36 ticket 21
    # replaced that series (0055 shares 2013-20, calendar revenue 2021-24), so re-pinned from the build: 306.988844.
    # Decision 0110 item 1.19 (2019 = 0, 2020 = 2,414.5 calendar) moves it by -0.118837, checked by hand arithmetic:
    # sum over 2019-20 of (new - old revenue) x 0055 share x (1 - GB share) x CPIH(2024)/CPIH(y). Re-pinned: 306.870007
    off = sum(_to_2024(sp[y]["carbon_price_receipts"]["ets_uk_gbp_m"] - sp[y]["carbon_price_receipts"]["ets_gbp_m"], y)
              for y in range(2013, 2025))
    # v4-s42 (C1, decision 0195): UK ETS revenue 2016 342.2, not 311.0 (+31.2 GBP m cash) moves it by +0.562278, the
    # 2016 term of the same sum (re-pinned from the v4-s42 build: 307.432285; 306.870007 at v4-s41).
    assert off == pytest.approx(306.98884392469193 - 0.11883694738869677 + 0.5622783251225, abs=1e-6)


def test_years_outside_2008_12_carry_no_phase_fields():
    # s36 ticket 21 replaced the Clock values 2013-25 (its own tests pin them); here only that the
    # 2008-12 phase fields stay on 2008-12 and pre-2008 is nil
    from gascf import carbon
    sp, r = _split(), carbon.ets_power_receipts()
    for y in range(2002, 2008):
        assert sp[y]["carbon_price_receipts"]["ets_uk_gbp_m"] == 0.0
    for y in range(2013, 2026):
        assert sp[y]["carbon_price_receipts"]["ets_uk_gbp_m"] == r[y][0], y
        assert "ets_phase2_gbp_m" not in sp[y]["carbon_price_receipts"]


def test_no_cps_scaling_switch():
    from gascf import bills as B
    with pytest.raises(TypeError):
        B.Settings(gb_scale_cps=True)


def test_run_file_names_the_traced_sources_and_the_2008_share_status():
    import importlib

    from gascf import export_v4 as X
    assert "gascf.carbon_blocks" in X.BLOCK_MODULES
    importlib.import_module("gascf.carbon_blocks")
    b = X._BLOCKS["ets_auctions"]({})
    assert b["phase2_total_uk_gbp_m"] == pytest.approx(1316.593, abs=0.0005)
    assert b["phase3_2012_uk_gbp_m"] == pytest.approx(61.139, abs=0.0005)
    assert b["ets_power_share_2008_status"] == "SOURCED"
    assert b["ets_power_share"]["2008"] == pytest.approx(0.648165, abs=1e-6)
    assert b["gb_scaled_components"] == ["ets"]
    assert b["files"]["s36/ets/uk-ets-phase2-auctions.csv"] == E.PHASE2_SHA256
    assert b["files"]["s36/ets/uk-ets-phase3-2012-auctions.csv"] == E.PHASE3_SHA256
    assert b["files"]["s36/ets/ets-power-share-2008.csv"] == E._sha(E.SHARE_2008)


def test_carbon_crosscheck_note_names_the_traced_file_and_gb_scaling(monkeypatch):
    from gascf import export_v4 as X
    fake = {y: {"carbon_split": {"carbon_price_receipts": {"national_gbp_m_nominal": 1.0}}} for y in X.B.YEARS}
    monkeypatch.setattr(X.B, "val", lambda b, lid: 2.0)
    note = X._carbon_check(fake)["2010"]["collected_note"]
    assert "uk-ets-phase2-auctions" in note and "GB" in note and "Subsidy Clock 'ets'" not in note.split(";")[0]


def test_tax_collected_line_note_says_the_ets_part_is_gb():
    from gascf import bills as B
    note = B._carbon_split_lines(2012, _split()[2012])["carbon_price_receipts"]["years_note"]
    assert "GB" in note and "Phase III" in note


def test_split_moves_but_nz1c_gap_and_households_do_not():
    """Heavy (two builds). Spec tests 7 and 14: only the split moves."""
    from gascf import bills as B
    b, single = B.build(), B.build(B.replace(B.CENTRAL, carbon_split=False))
    for y in B.YEARS:
        cs = b[y]["carbon_split"]
        assert (cs["carbon_price_receipts"]["national_gbp_m_nominal"] + cs["carbon_in_price"]["national_gbp_m_nominal"]
                == pytest.approx(B.val(b[y], "NZ1c"), abs=1e-9)), y
        assert B.val(b[y], "NZ1c") == pytest.approx(B.val(single[y], "NZ1c"), abs=1e-9), y
        assert b[y]["totals"]["gap_gbp_m"] == pytest.approx(single[y]["totals"]["gap_gbp_m"], abs=1e-9), y
        assert b[y]["totals"]["gap_per_hh_real"] == pytest.approx(single[y]["totals"]["gap_per_hh_real"], abs=1e-9), y
    t12 = b[2012]["carbon_split"]["carbon_price_receipts"]
    assert t12["national_gbp_m_nominal"] == pytest.approx(_split()[2012]["carbon_price_receipts"]["gbp_m"], abs=1e-9)
