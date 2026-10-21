"""Ticket 25: figures keys for the grid switches (tools/figures_keys/grid.py), read from the run file only.
Values stay in the run's 2025 money; the 2024-price conversion is ticket 29's one function."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import figures as F  # noqa: E402
from tools.figures_keys import grid as K  # noqa: E402

ROW = "grid index at the controls' own X (RPI-X, 0091)"


def _run():
    years = range(2002, 2026)
    return {"meta": {"engine_version": "toy", "price_base": 2025, "deflator": "ONS CPIH L522"},
            "years": [{"year": y, "households": 2_000_000.0} for y in years],
            "gap": {str(y): {"national_gbp_bn_real": 0.5} for y in years},
            # decision 0112: the rpi_x row is in the range, so it is read from one_at_a_time.ranked
            "one_at_a_time": {"ranked": {ROW: [{"settings": {"go5_index": "rpi_x"},
                                                "gap_real_bn": {str(y): 1.0 if y < 2025 else 9e9 for y in years},
                                                "lines_moved_gbp_m_nominal": {}}]}, "methods_page": {}},
            "scot_share_alt": {"gap_effect_2002_05_gbp_m": 0.126, "level_shift_gbp_m": 270.07}}


def _k():
    from gascf import deflator_cpih
    c = deflator_cpih.cpih()
    return c[2024] / c[2025]


def test_rpi_x_headline_is_the_2002_24_national_gap_under_the_switch():
    # £1.0bn a year national real gap under the switch (run money, 2025 £), 23 years 2002-24; 2025 never counted.
    # Decision 0122 item 3: restated in 2024 £ like every headline key (was left in 2025 £ at the f82e9f9 cut).
    v = K.values(_run())
    assert v["sens_grid_rpi_x_2002_24_gbp_bn"] == pytest.approx(23.0 * _k(), rel=1e-12)
    assert v["rpi_x_effect_2002_24_gbp_bn"] == pytest.approx((23.0 - 11.5) * _k(), rel=1e-12)


def test_scot_share_alt_keys_read_the_0102_block():
    v = K.values(_run())
    assert v["scot_share_alt_gap_effect_2002_05_gbp_m"] == pytest.approx(0.126 * _k(), rel=1e-12)
    assert v["scot_share_alt_level_shift_gbp_m"] == pytest.approx(270.07 * _k(), rel=1e-12)


def test_grid_keys_module_is_listed_and_names_the_engine_switch():
    from gascf import bills as B
    from tools import figures_keys
    assert "grid" in figures_keys.MODULES
    assert K.RPI_X_ROW == B.RPI_X and K.RPI_X_ROW not in B.METHOD_SWITCHES          # 0112: in the range
    assert B.SWITCHES[K.RPI_X_ROW] == (B.replace(B.CENTRAL, go5_index="rpi_x"),)
    keys = F.generate(_run(), modules=[K])["keys"]
    assert set(keys) == set(K.DECLARED)
