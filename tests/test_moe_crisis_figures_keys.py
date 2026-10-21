"""Ticket 18: figures keys for the UCL crisis-year sensitivity (figures-keys.md rows 93-99), read from the
run file's `moe_crisis` block. Gap keys in 2024 £ (CPIH), £bn; ratio keys the low and high over 2021-23."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

RUN = {"meta": {"engine_version": "toy"}, "moe_crisis": {
    "years": {"2021": {"shao": {"national_gbp_m_nominal": 10000.0}, "ucl_stmoe": {"national_gbp_m_nominal": 8000.0}},
              "2022": {"shao": {"national_gbp_m_nominal": 11000.0}, "ucl_stmoe": {"national_gbp_m_nominal": 6000.0}},
              "2023": {"shao": {"national_gbp_m_nominal": 12000.0}, "ucl_stmoe": {"national_gbp_m_nominal": 11000.0}}},
    "ucl_over_shao": {"total": {"2021": 1.71, "2022": 3.54, "2023": 1.59},
                      "wind": {"2021": 2.37, "2022": 4.94, "2023": 2.22}}}}


def test_moe_crisis_keys_from_the_run_file():
    from gascf import deflator_cpih as dfl
    from tools.figures_keys import moe_crisis as K
    from tools import figures_keys
    assert "moe_crisis" in figures_keys.MODULES
    v = F.generate(RUN, modules=[K])["keys"]
    to24 = lambda n, y: dfl.to_real(n, y, 2024) / 1e3  # noqa: E731
    shao = to24(10000, 2021) + to24(11000, 2022) + to24(12000, 2023)
    ucl = to24(8000, 2021) + to24(6000, 2022) + to24(11000, 2023)
    assert v["gap_2021_23_shao_gbp_bn"]["value"] == pytest.approx(shao)
    assert v["gap_2021_23_ucl_gbp_bn"]["value"] == pytest.approx(ucl)
    assert v["gap_2021_23_ucl_difference_gbp_bn"]["value"] == pytest.approx(ucl - shao)
    assert (v["ucl_over_shao_total_low"]["value"], v["ucl_over_shao_total_high"]["value"]) == (1.59, 3.54)
    assert (v["ucl_over_shao_wind_low"]["value"], v["ucl_over_shao_wind_high"]["value"]) == (2.22, 4.94)
    for meta in (x["meta"] for x in v.values()):
        assert meta["ticket"] == "18" and meta["basis"] == "modelled"
        assert "printed p.22 (PDF p.24)" in meta["source"]
