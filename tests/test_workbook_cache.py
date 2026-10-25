"""[internal ticket]: each Excel workbook the fossil fleet and the capacity margin read is opened once per
process, not once per call (the EGC cost workbooks were opened 598 times in one export, the ECR
capacity workbook 1,351 times). No figure may move.

The guard risk (s36 B-merge cause 4: a cache once hid an input guard): the cache must be keyed on
everything the read depends on (the file's path, its contents and the read options), so a changed
workbook is read again, and every reader's layout guard still runs on every call.
"""
from __future__ import annotations

import os
import shutil
from collections import Counter
from pathlib import Path

import openpyxl
import pytest

from gascf import capacity as CAP
from gascf import fossil_fleet as F
from gascf import official as O

EGC_FILES = ("s18d-BEIS_EGC2016_Annexes.xlsx", "s18d-BEIS_EGC2020_KeyData.xlsx",
             "s18d-EGC2023_AnnexA.xlsx", "s18d-EGC2025_AnnexA_current.xlsx")


@pytest.fixture
def opens(monkeypatch):
    """Counts openpyxl.load_workbook calls by file name, still opening the real file."""
    real, seen = openpyxl.load_workbook, Counter()

    def counting(filename, *a, **k):
        seen[Path(filename).name] += 1
        return real(filename, *a, **k)

    monkeypatch.setattr(openpyxl, "load_workbook", counting)
    return seen


@pytest.fixture
def egc_copy(tmp_path, monkeypatch):
    """The four EGC cost workbooks copied to a fresh folder the engine reads instead (a path this
    process has never read, so nothing is cached for it yet)."""
    d = tmp_path / "desnz_egc"
    d.mkdir()
    for f in EGC_FILES:
        shutil.copy2(F.EGC / f, d / f)
    monkeypatch.setattr(F, "EGC", d)
    return d


@pytest.fixture
def ecr_copy(tmp_path, monkeypatch):
    p = tmp_path / CAP.WORKBOOK.name
    shutil.copy2(CAP.WORKBOOK, p)
    monkeypatch.setattr(CAP, "WORKBOOK", p)
    return p


def _rewrite(path: Path, sheet: str, edit) -> None:
    """Save `path` again with `edit(ws)` applied to one sheet, values only, then put the old mtime
    back: the cache must notice the new contents, not trust the timestamp."""
    st = path.stat()
    wb = openpyxl.load_workbook(path, data_only=True)
    edit(wb[sheet])
    wb.save(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


def _cell(ws, pred):
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and pred(c.value):
                return c
    raise AssertionError("cell not found")


# ------------------------------------------------------------------ read once

def test_edition_opens_each_egc_workbook_once_however_often_it_is_called(egc_copy, opens):
    first = {y: F.edition(y) for y in (2017, 2021, 2023, 2025)}
    for _ in range(5):
        for y in (2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025):
            F.edition(y)
    assert {y: F.edition(y) for y in first} == first
    # one open per sheet read: KeyData and Annex A (2023) need the sheet list, then the sheet
    assert opens["s18d-BEIS_EGC2016_Annexes.xlsx"] == 1
    assert opens["s18d-BEIS_EGC2020_KeyData.xlsx"] <= 2
    assert opens["s18d-EGC2023_AnnexA.xlsx"] <= 2
    # v4-s42 (A4, decision 0195): 2025 is costed on EGC 2023, so no costed year opens EGC 2025 (was == 1)
    assert opens["s18d-EGC2025_AnnexA_current.xlsx"] == 0


def test_the_ecr_workbook_is_opened_once_per_sheet(ecr_copy, opens):
    d, peak = CAP.read_derating(), CAP.read_peak_base_case()
    for _ in range(20):
        assert CAP.read_derating() == d
        assert CAP.read_peak_base_case() == peak
        CAP.margin_fraction("central")
    assert opens[ecr_copy.name] == 2           # Figure A10 once, Figure B1 once


# ------------------------------------------------------------- same values

@pytest.mark.parametrize("path,sheet", [
    (F.EGC / "s18d-BEIS_EGC2016_Annexes.xlsx", "Table 19"),
    (F.EGC / "s18d-BEIS_EGC2020_KeyData.xlsx", None),
    (F.EGC / "s18d-EGC2023_AnnexA.xlsx", None),
    (F.EGC / "s18d-EGC2025_AnnexA_current.xlsx", O.TECH_SHEET),
    (CAP.WORKBOOK, "Figure A10"),
    (CAP.WORKBOOK, "Figure B1"),
])
def test_cached_rows_are_exactly_what_openpyxl_reads(path, sheet):
    from gascf import workbook_cache as WC
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    assert WC.sheetnames(path) == wb.sheetnames
    sheet = sheet or next(s for s in wb.sheetnames if s.lower() == "technical and cost assumptions")
    direct = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    assert WC.sheet_rows(path, sheet) == direct
    assert WC.sheet_rows(path, sheet) == direct          # second call, from the cache


def test_a_caller_cannot_change_what_the_next_caller_reads(ecr_copy):
    from gascf import workbook_cache as WC
    rows = WC.sheet_rows(ecr_copy, "Figure A10")
    n = len(rows)
    rows.clear()
    assert len(WC.sheet_rows(ecr_copy, "Figure A10")) == n
    assert all(isinstance(r, tuple) for r in WC.sheet_rows(ecr_copy, "Figure A10"))


def test_a_missing_sheet_still_raises():
    from gascf import workbook_cache as WC
    with pytest.raises(KeyError):
        WC.sheet_rows(CAP.WORKBOOK, "No such sheet")


# --------------------------------------------- a changed workbook is read again; guards fire

def test_a_changed_value_is_read_again(ecr_copy):
    before = CAP.read_derating()["ccgt"]
    _rewrite(ecr_copy, "Figure A10",
             lambda ws: setattr(_cell(ws, lambda v: v == before), "value", 0.5))
    assert CAP.read_derating()["ccgt"] == 0.5


def test_a_broken_ecr_layout_fires_its_guard_after_a_good_read(ecr_copy):
    CAP.read_derating()                                    # good read, now cached
    _rewrite(ecr_copy, "Figure A10",
             lambda ws: setattr(_cell(ws, lambda v: isinstance(v, str) and "CCGT" in v), "value", "Gas turbine"))
    for _ in range(2):                                     # and on every call, not just the first
        with pytest.raises(ValueError, match="ECR Figure A10 layout changed"):
            CAP.read_derating()


def test_a_broken_egc2016_layout_fires_its_guard_after_a_good_read(egc_copy):
    assert F.edition(2017).ccgt.size_mw == 1200            # good read, now cached
    f = egc_copy / "s18d-BEIS_EGC2016_Annexes.xlsx"
    _rewrite(f, "Table 19", lambda ws: setattr(ws["A1"], "value", "Table 18"))
    for _ in range(2):
        with pytest.raises(ValueError, match="EGC 2016 Table 19 layout changed"):
            F.edition(2017)


def test_a_broken_egc2020_phasing_fires_its_guard_after_a_good_read(egc_copy):
    F.edition(2021)
    f = egc_copy / "s18d-BEIS_EGC2020_KeyData.xlsx"
    names = openpyxl.load_workbook(f, read_only=True).sheetnames
    sheet = next(s for s in names if s.lower() == "technical and cost assumptions")

    def edit(ws):
        lab = _cell(ws, lambda v: isinstance(v, str) and v.strip().lower().startswith("construction phasing"))
        ccgt = next(c.column for c in ws[1] if c.value and str(c.value).strip() == "CCGT H Class"
                    and ws.cell(2, c.column).value == 2025)
        ws.cell(lab.row, ccgt).value = 5.0                 # year-1 share 500%: phasing no longer sums to 1
    _rewrite(f, sheet, edit)
    for _ in range(2):
        with pytest.raises(ValueError, match="construction phasing phasing sums to"):
            F.edition(2021)
