"""Ticket 12: figures keys for the CCL 2001-baseline (figures-keys.md rows 132, 135, 137), read from the run
file's bills NZ8 line and the on_the_road block's exported D3/D5 parts (toy run, no build)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

Y = [str(y) for y in range(2002, 2026)]
RUN = {"meta": {"engine_version": "toy", "price_base": 2025, "deflator": "ONS CPIH L522"},
       "bills": {y: {"netzero": [{"id": "NZ8", "national_gbp_m_real": -10.0}], "gasonly": []} for y in Y},
       "on_the_road": {"decision": "0097, 0044", "years": {
           y: {"nz8_on_the_road_gbp_m_2024": 20.0, "nz8_lec_exempt_gbp_m_2024": 5.0} for y in Y}}}


def test_ccl_keys_from_the_run_file():
    from gascf import deflator_cpih as dfl
    from tools.figures_keys import ccl as K
    from tools import figures_keys
    assert "ccl" in figures_keys.MODULES
    v = F.generate(RUN, modules=[K])["keys"]
    c = dfl.cpih()
    extra = sum(-10.0 * c[2024] / c[2025] for y in range(2002, 2025)) / 1e3
    assert v["ccl_extra_2002_24_gbp_bn"]["value"] == pytest.approx(extra)
    assert v["ccl_2001_level_netted_2002_24_gbp_bn"]["value"] == pytest.approx(23 * 20.0 / 1e3)
    assert v["lec_exemption_effect_2002_24_gbp_bn"]["value"] == pytest.approx(23 * 5.0 / 1e3)
    for meta in (x["meta"] for x in v.values()):
        assert meta["ticket"] == "12" and meta["basis"] == "modelled"


def test_ccl_keys_none_without_the_block():
    from tools.figures_keys import ccl as K
    v = F.generate({"meta": {"engine_version": "toy", "price_base": 2025}, "bills": {}}, modules=[K])["keys"]
    assert all(v[k]["value"] is None for k in K.DECLARED)
