"""Residual demand from Elexon FUELHH + NESO embedded estimates."""
import statistics as st

import pytest

from gascf.residual import load_duration, read_fuelhh, residual_year


@pytest.fixture(scope="module")
def y2025():
    return residual_year(2025)


def test_complete_year(y2025):
    rows, missing = y2025
    assert len(rows) == 17520 and missing == []            # 365 x 48, no gaps


def test_balance_against_neso_national_demand():
    """Net transmission output (Elexon; interconnectors and pumped storage are net, so
    exports and pumping already come off) minus NESO national demand should be station
    load, which NESO puts at 500-600 MW. 2017-2023 medians: 515-593 MW. A missed fuel
    column, a doubled one, or embedded output added to the wrong side breaks this."""
    for year in (2018, 2019, 2021, 2023):
        rows, _ = residual_year(year)
        gap = st.median(r.gas_actual + r.replaced_transmission + r.kept - r.nd for r in rows)
        assert 450 <= gap <= 650, (year, gap)


def test_flows_are_net():
    f = read_fuelhh(2025)
    assert any(v.get("PS", 0) < 0 for v in f.values())       # pumping shows as negative
    assert any(v.get("INTFR", 0) < 0 for v in f.values())    # exports show as negative


def test_residual_2025_size(y2025):
    """All-gas Britain 2025: ~205 TWh of gas power against ~77 TWh actually made from gas;
    peak 45.2 GW (46.0 if battery discharge were wrongly replaced). Residual >= actual gas."""
    rows, _ = y2025
    assert sum(r.residual for r in rows) / 2e6 == pytest.approx(205, abs=2)
    assert sum(r.gas_actual for r in rows) / 2e6 == pytest.approx(77, abs=1)
    assert max(r.residual for r in rows) / 1e3 == pytest.approx(45.18, abs=0.01)
    assert all(r.residual >= r.gas_actual for r in rows)


def test_brackets(y2025):
    rows, _ = y2025
    small, _ = residual_year(2025, replace_hydro=False)
    big, _ = residual_year(2025, replace_other=True)
    tw = lambda rr: sum(r.residual for r in rr) / 2e6
    assert tw(rows) - tw(small) == pytest.approx(3.4, abs=0.1)   # 2025 NPSHYD, TWh
    assert tw(big) - tw(rows) == pytest.approx(4.8, abs=0.1)     # 2025 OTHER, TWh
    # what is not replaced is kept: the balance identity holds either way
    for a, b, c in zip(rows[:500], small[:500], big[:500]):
        assert a.residual + a.kept == pytest.approx(b.residual + b.kept)
        assert a.residual + a.kept == pytest.approx(c.residual + c.kept)


def test_other_carries_battery_discharge():
    """Why OTHER is kept by default: evening (SP 37-40) mean > 3x the overnight (SP 5-8) mean."""
    f = read_fuelhh(2025)
    mean = lambda sps: st.mean(v.get("OTHER", 0) for (_, p), v in f.items() if p in sps)
    assert mean(range(37, 41)) > 3 * mean(range(5, 9))


def test_load_duration_sorted(y2025):
    ldc = load_duration(y2025[0])
    assert ldc[0] >= ldc[len(ldc) // 2] >= ldc[-1]
    assert len(ldc) == 17520
