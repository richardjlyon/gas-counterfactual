"""HM Treasury GDP deflator reader."""
import pytest

from gascf.deflator import read_deflator, rebase


def test_values_read_at_source():
    idx, fc = read_deflator()
    assert idx[2025] == 100
    assert idx[2024] == 96.5672 and idx[2016] == 73.9044 and idx[2014] == 72.2397
    assert 2025 not in fc and 2026 in fc
    assert idx[2026] == pytest.approx(100 * 1.02183088, rel=1e-6)   # OBR +2.18%


def test_rebase():
    assert rebase(100, 2024, 2024) == 100
    assert rebase(100, 2024, 2025) == pytest.approx(100 / 0.965672)
    assert rebase(rebase(55.0, 2024, 2016), 2016, 2024) == pytest.approx(55.0)
