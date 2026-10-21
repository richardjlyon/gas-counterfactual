"""Figures keys confirmed by decision 0108 item 1.15 (Richard Lyon, 19 Oct 2026, the definitions as recommended) and
the gas-feedback elasticities (ticket 08, 0033): tools/figures_keys/params.py. Toy run, no build."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import figures as F  # noqa: E402

Y = [str(y) for y in range(2002, 2026)]


def _run():
    def lines(y, side):
        ids = ("NZ1",) if side == "netzero" else ("GO1k",)
        return [{"id": i, "national_gbp_m_nominal": (1000.0 if i == "NZ1" else 300.0)} for i in ids]
    return {"meta": {"engine_version": "toy", "price_base": 2025, "deflator": "ONS CPIH L522"},
            "bills": {y: {"netzero": lines(y, "netzero"), "gasonly": lines(y, "gasonly"),
                          "nz1c": {"national_gbp_m_nominal": 200.0}} for y in Y},
            "fleet": {y: {"market_gbp_m": 450.0} for y in Y},
            "years": [{"year": int(y), "station_load_twh": 4.0 + (int(y) - 2002) * 0.1} for y in Y]}


def test_pricing_residual_2002_05_is_nz1_less_carbon_less_market_fleet_less_kept_2025_money():
    """Ticket 11 spec test 6's definition (station-load.md, §5.3): (NZ1 - NZ1c) - GO1 market part - GO1k, 2002-05,
    restated in 2025 money."""
    from gascf import deflator_cpih
    from tools.figures_keys import params as K
    v = F.generate(_run(), modules=[K])["keys"]["pricing_residual_2002_05_gbp_m"]
    want = sum(deflator_cpih.to_real(1000.0 - 200.0 - 450.0 - 300.0, y, 2025) for y in range(2002, 2006))
    assert v["value"] == pytest.approx(want, rel=1e-12)
    assert v["meta"]["units"] == "£m, 2025 prices" and v["meta"]["period"] == "2002-2005"


def test_station_load_typical_year_is_the_2002_24_mean():
    from tools.figures_keys import params as K
    v = F.generate(_run(), modules=[K])["keys"]["station_load_twh_yr"]["value"]
    assert v == pytest.approx(sum(4.0 + i * 0.1 for i in range(23)) / 23, rel=1e-12)


def test_gas_feedback_elasticities_by_value_with_the_name_trap():
    """0144 item 2A (v4-s37): central e = supply 0.06 + demand 0.169; the range's high end at Krichene's world
    long-run pair 0.61. gas_feedback_e_low (v4-s36: 0.06, supply only) is gone."""
    from gascf.fossil_like_for_like import GAS_ELASTICITY
    from tools.figures_keys import params as K
    k = F.generate(_run(), modules=[K])["keys"]
    assert k["gas_feedback_e_central"]["value"] == GAS_ELASTICITY["central"] == pytest.approx(0.229)
    assert (k["gas_feedback_e_supply_central"]["value"], k["gas_feedback_e_demand_central"]["value"]) == (0.06, 0.169)
    assert k["gas_feedback_e_high"]["value"] == GAS_ELASTICITY["krichene_lr"] == pytest.approx(0.61)
    assert "gas_feedback_e_low" not in k


def test_module_listed_and_none_without_the_run_fields():
    from tools import figures_keys
    from tools.figures_keys import params as K
    assert "params" in figures_keys.MODULES
    v = K.values({"meta": {"price_base": 2025, "deflator": "ONS CPIH L522"}})
    assert v["pricing_residual_2002_05_gbp_m"] is None and v["station_load_twh_yr"] is None
