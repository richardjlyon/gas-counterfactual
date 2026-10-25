"""Tests for reference/fossil_closures.yaml (strand s23a): the register of GB fossil
stations closed or converted 2002-2025, with the reason and the fossil-Britain close date.

Checks: the schema in brief s23; the closure rules in spec §15.3; every row carries a URL
and a quote that is found word for word in the stored source; and the coal capacity in the
register agrees with DUKES Table 5.11 (changed and converted stations) and Table 5.7
(capacity by fuel) read from the stored workbooks.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "reference" / "fossil_closures.yaml"
REASONS = {"age", "air_pollution", "net_zero_policy", "mixed", "other"}
ABATEMENT = {"FGD", "SCR", "FGD+SCR", None}
FUELS = {"coal", "gas", "oil"}
REQUIRED = ["station", "unit", "fuel", "capacity_mw", "actual_close", "reason",
            "fossil_britain_close", "abatement_needed", "source_id", "url", "quote", "note"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _norm(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip()


@pytest.fixture(scope="module")
def rows():
    return json.loads(REG.read_text())


def test_schema(rows):
    assert len(rows) >= 50
    for r in rows:
        for k in REQUIRED:
            assert k in r, (r["station"], k)
        assert r["fuel"] in FUELS
        assert r["reason"] in REASONS
        assert r["abatement_needed"] in ABATEMENT
        assert DATE.match(r["actual_close"])
        assert "2002-01-01" <= r["actual_close"] <= "2025-12-31"
        assert r["fossil_britain_close"] is None or DATE.match(r["fossil_britain_close"])
        assert r["url"].startswith("http") and len(r["quote"]) > 15
        assert r["capacity_mw"] is None or r["capacity_mw"] > 0


def test_closure_rules(rows):
    """Brief s23 rules: age/air_pollution/other close on the actual date; net_zero_policy
    rows never close (null); mixed rows close no earlier than actual; abatement only where
    the station is kept running."""
    for r in rows:
        if r["reason"] in ("age", "other"):
            assert r["fossil_britain_close"] == r["actual_close"], r["station"]
        if r["reason"] == "air_pollution":
            assert r["fossil_britain_close"] == r["actual_close"], r["station"]
        if r["reason"] == "net_zero_policy":
            assert r["fossil_britain_close"] is None, r["station"]
            assert r["fuel"] == "coal"
        if r["reason"] == "mixed":
            assert r["fossil_britain_close"] >= r["actual_close"], r["station"]
        if r["abatement_needed"] is not None:
            assert r["fossil_britain_close"] is None, r["station"]


def test_biomass_conversions_stay_coal(rows):
    """Spec §15.3 item 5: Drax and Lynemouth conversions are net-zero policy and stay on coal."""
    drax = [r for r in rows if r["station"] == "Drax"]
    assert len(drax) == 5
    assert sum(r["capacity_mw"] for r in drax) == 3960  # DUKES 5.11: '2013 | Drax | ... | 3960 | 3300'
    assert all(r["reason"] == "net_zero_policy" for r in drax)
    lyn = [r for r in rows if r["station"] == "Lynemouth"][0]
    assert lyn["reason"] == "net_zero_policy" and lyn["fossil_britain_close"] is None


def test_quotes_in_stored_sources(rows):
    cache = {}
    for r in rows:
        f = ROOT / r["source_file"]
        assert f.exists(), f
        if f not in cache:
            cache[f] = _norm(f.read_text(errors="ignore"))
        assert _norm(r["quote"]) in cache[f], (r["station"], r["source_id"])


def test_spot_values(rows):
    by = {(r["station"], r["unit"]): r for r in rows}
    assert by[("Kingsnorth", "all")]["capacity_mw"] == 1940
    assert by[("Kingsnorth", "all")]["reason"] == "air_pollution"
    assert by[("Longannet", "all")]["capacity_mw"] == 2260
    assert by[("Ratcliffe-on-Soar", "all")]["actual_close"] == "2024-09-30"
    assert by[("West Burton A", "all")]["actual_close"] == "2023-03-31"


def _dukes_511_gb_coal_2011_2024():
    """GB coal capacity closed or converted 2011-2024, from the stored DUKES 5.11 'Changed
    and converted stations' sheet (coal rows with status closed/converted/mothballed;
    Northern Ireland's Kilroot excluded)."""
    wb = openpyxl.load_workbook(ROOT / "data/raw/DUKES_5.11.xlsx", read_only=True)
    ws = wb["Changed and converted stations"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [i for i, r in enumerate(rows) if r and r[0] == "Year of opening/closure, capacity change or conversion"]
    assert hdr, "DUKES 5.11 changed-list header moved"
    total = 0.0
    for r in rows[hdr[0] + 1:]:
        if not r or not isinstance(r[0], int) or not (2011 <= r[0] <= 2024):
            continue
        site, fuel, status, prev, new = r[1], str(r[2]), str(r[3]), r[4], r[5]
        if not fuel.lower().startswith("coal") or "Kilroot" in site:
            continue
        if any(s in status for s in ("Closed", "Converted", "Mothballed")):
            total += prev - new
    return total


def test_coal_total_matches_dukes_511(rows):
    """Identity: register coal (2011-2024) = DUKES 5.11 changed list + Fiddler's Ferry
    unit 1 (485 MW) + Rugeley's 558 MW. The DUKES list closes only 1510 MW at Fiddler's Ferry in 2020 from an
    edition capacity of 1961 MW; SSE's RNS records the separate March 2019 unit 1 closure. The list closes Rugeley
    at 448 MW; the register uses the 1,006 MW of the DUKES 2004-16 edition sheets (decision 0159, Richard Lyon,
    21 Oct 2026), so 1,006 - 448 = 558 MW more."""
    reg = sum(r["capacity_mw"] for r in rows if r["fuel"] == "coal" and r["capacity_mw"]
              and "2011-01-01" <= r["actual_close"] <= "2024-12-31")
    dukes = _dukes_511_gb_coal_2011_2024()
    assert dukes == pytest.approx(27431, abs=1)  # recorded value from the stored workbook
    assert reg - 485 - (1006 - 448) == pytest.approx(dukes, abs=1), (reg, dukes)


def test_coal_total_vs_dukes_57(rows):
    """Register GB coal closures 2011-2024 against the fall in DUKES 5.7 major-power-producer
    coal plus mixed/dual-fired capacity (end-2010 to end-2024), less Northern Ireland's
    Kilroot (520 MW in 5.11 edition DUKES 2011). Mixed/dual includes some gas/oil plant,
    so only a loose tolerance (15%) is meaningful; the gap is recorded in notes.md."""
    wb = openpyxl.load_workbook(ROOT / "data/raw/DUKES_5.7.xlsx", read_only=True, data_only=True)
    rows57 = list(wb["5.7"].iter_rows(values_only=True))
    hdr = rows57[6]
    i10, i24 = hdr.index("2010"), hdr.index("2024")
    get = {}
    for r in rows57:
        if r[0] and str(r[0]).startswith("Major power producers"):
            get[r[1]] = r
    coal = get["Coal fired"]
    mixed = get["Mixed or dual fired [note 5]"]
    fall = (coal[i10] - coal[i24]) + (mixed[i10] - mixed[i24]) - 520
    reg = sum(r["capacity_mw"] for r in rows if r["fuel"] == "coal" and r["capacity_mw"]
              and "2011-01-01" <= r["actual_close"] <= "2024-12-31")
    assert reg == pytest.approx(fall, rel=0.15), (reg, fall)


def test_s24_closure_test_applied(rows):
    """Spec §15.4 item 2 (strand s24): every mixed coal row, and the 'other' coal rows tested,
    carry the margin result; the one positive (Rugeley) keeps running until the pollution-law
    deadline (30 June 2020), because it loses money once it must pay for filters (spec §15.4
    item 3); the negatives close on the real date (Tilbury B and Ironbridge no longer wait
    for the LCPD)."""
    by = {r["station"]: r for r in rows if r["fuel"] == "coal"}
    tested = ("Tilbury B", "Ironbridge", "Ferrybridge C", "Longannet", "Rugeley", "Uskmouth",
              "Eggborough", "Aberthaw B")
    for s in tested:
        assert "s24 closure test" in by[s]["note"], s
    assert not [r for r in rows if r["reason"] == "mixed" and "s24 closure test" not in r["note"]]
    for s in ("Tilbury B", "Ironbridge", "Ferrybridge C", "Longannet", "Aberthaw B"):
        assert by[s]["reason"] == "mixed" and by[s]["fossil_britain_close"] == by[s]["actual_close"], s
    for s in ("Uskmouth", "Eggborough"):
        assert by[s]["reason"] == "other" and by[s]["fossil_britain_close"] == by[s]["actual_close"], s
    rug = by["Rugeley"]
    assert rug["reason"] == "mixed" and rug["fossil_britain_close"] == "2020-06-30"
    # Decision 0159 (Richard Lyon, 21 Oct 2026, "A we have to fix it."): 1,006 MW, the installed capacity in all 13
    # DUKES edition sheets 2004-16 (DUKES 2026 Table 5.11 workbook, e.g. sheet 'DUKES 2016' row 107), not the 448 MW
    # of the 2016 'Changed and converted stations' row 58.
    assert rug["abatement_needed"] is None and rug["capacity_mw"] == 1006
    assert "DUKES 2016" in rug["quote"] and "1006" in rug["quote"]


def test_s24_margins_file_agrees_with_register(rows):
    """The stored margin table drives the register: positive in the year before closure
    exactly where the register keeps the station running beyond its real date. The margin
    script types each station's MW in by hand, so it must equal the register's (0159)."""
    m = json.loads((ROOT / "work/s24-closure-test/margins.json").read_text())
    by = {r["station"]: r for r in rows if r["fuel"] == "coal"}
    assert m["Rugeley"]["mw"] == by["Rugeley"]["capacity_mw"]
    # C-007 (Richard Lyon, 21 Oct 2026, relayed by the chief-executive: "Agree to all. Yep."): Rugeley's TNUoS
    # generation zone is 18. NG 'TNUoS tariffs for 2013/14' (doc 50671) p.27 old-to-new zone table lists
    # 'Rugeley B' under old zone 14, new zone 18, with Ironbridge and Ratcliffe-on-Soar. Zone 18 wider tariffs,
    # £/kW: 2013/14 2.44 (doc 50671); 2014/15 3.55 and 2015/16 2.09 (doc 50181). Zone 16 (5.18, 6.17, 4.89) is not used.
    t = (ROOT / "data/raw/neso_s18b/neso_doc_50671.txt").read_text()
    block = t[t.index("14       Ironbridge             18"):t.index("Pembroke               20")]
    assert "Rugeley B" in block
    rug_years = {r["year"]: r for r in m["Rugeley"]["years"]}
    for y, tariff in ((2013, 2.44), (2014, 3.55), (2015, 2.09)):
        assert rug_years[y]["tnuos_gbp_kw"] == pytest.approx(tariff, abs=0.005), y
        assert "16 North Midlands" not in rug_years[y]["tnuos_src"], y
    for s, v in m.items():
        last = v["years"][-1]["margin_before_filters_gbp_m"]
        kept = by[s]["fossil_britain_close"] is None or by[s]["fossil_britain_close"] > by[s]["actual_close"]
        assert (last > 0) == kept, (s, last)
