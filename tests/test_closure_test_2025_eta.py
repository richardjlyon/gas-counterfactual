"""Card [internal ticket]: closure_test._year_inputs must run for 2025 (B.build(V11_COAL_CENTRAL) stopped with KeyError 2025).

DUKES 5.10.C prints no coal efficiency for 2025. The engine's existing rule (fossil_like_for_like._eta_dukes, s27a)
runs coal kept open after the last printed year at the 2015-2023 coal-fleet mean and records the fallback. The
closure test now takes its efficiency from that rule. Expected values are literals from DUKES 5.10.C (% GCV):
2015-23 = 35.57, 34.98, 34.86, 34.10, 32.05, 33.24, 34.82, 36.46, 34.64; 2024 = 41.51.
"""
import pytest

from gascf import closure_test as CT

MEAN_2015_23 = (35.57 + 34.98 + 34.86 + 34.10 + 32.05 + 33.24 + 34.82 + 36.46 + 34.64) / 9 / 100


def test_2025_runs_at_the_2015_23_mean():
    assert CT._year_inputs(2025)["eta"] == pytest.approx(MEAN_2015_23)


def test_printed_years_unchanged():
    assert CT._year_inputs(2024)["eta"] == pytest.approx(0.4151)
    assert CT._year_inputs(2018)["eta"] == pytest.approx(0.3410)
