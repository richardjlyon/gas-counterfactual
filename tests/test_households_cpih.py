"""Strand s20c / s30: GB households (LFS) and CPIH L522 (spec §2, §12.2 item 11, §12.3)."""
import pytest

from gascf import deflator_cpih as d
from gascf import households as h


def test_households_gb_year_matched():
    """s30: GB households (England + Wales + Scotland, ONS LFS), year-matched."""
    k = h.read_households()
    assert k[2002] == 24_149 and k[2024] == 27_867 and k[2025] == 28_253
    hh = h.households()
    assert hh[2002]["households"] == pytest.approx(24_148_600)       # ONS 005374, rounded to 100
    assert hh[2025]["households"] == pytest.approx(28_253_000)       # ONS LFS 2025 workbook
    assert hh[2002]["source_id"] == h.SOURCE_ID_OLD and hh[2025]["source_id"] == h.SOURCE_ID
    assert h.per_household(28.253, 2025) == pytest.approx(1.0)


def test_households_two_files_agree_where_they_overlap():
    old, new = h.read_lfs_1996_2017(), h.read_lfs_2015_2025()
    for y in (2015, 2016, 2017):
        for n in h.NATIONS:
            assert old[n][y] == pytest.approx(new[n][y], rel=0.01), (n, y)
        assert sum(old[n][y] for n in h.NATIONS) == pytest.approx(sum(new[n][y] for n in h.NATIONS), rel=0.002), y


def test_cpih_spot_and_base():
    c = d.cpih()
    assert c[2015] == 100.0 and c[2002] == 75.7 and c[2024] == 132.9   # Clock deflators.yaml
    r = d.cpih_rebased(2024)
    assert r[2024] == pytest.approx(100.0)
    assert r[2002] == pytest.approx(100 * 75.7 / 132.9)
    assert d.to_real(100.0, 2002, 2024) == pytest.approx(100 * 132.9 / 75.7)
    s = d.series(2024)
    assert sorted(s) == list(range(2002, 2026)) and s[2002]["source_id"] == "ons-cpih-l522"


def test_rpi_read():
    r = d.rpi()
    assert r[2002] == 176.2 and r[2024] == 386.7
    assert d.rpi_to_nominal(100.0, 2002, 2024) == pytest.approx(100 * 386.7 / 176.2)
