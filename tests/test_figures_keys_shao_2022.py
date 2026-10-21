"""shao_uplift_2022_gbp_mwh (ticket 44, figures-keys.md): left 'TBC' and never set by worked_hh.values, so None at
the s36 release run (19 Oct 2026), which the release gate refuses. Its label defines it: the 2022 merit-order uplift,
time-mean, modelled by the engine with Shao and others' method = fleet[2022].moe.shao_mean_gbp_mwh, read only when
the engine applied the Shao rule in 2022. Light: a toy run."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.figures_keys import worked_hh as K  # noqa: E402


def _run(rule="shao"):
    return {"fleet": {"2024": {}, "2022": {"moe": {"rule": rule, "shao_mean_gbp_mwh": 15.934304935351477,
                                                  "applied_mean_gbp_mwh": 15.934304935351477,
                                                  "applied_on_fossil_output_gbp_mwh": 11.02}}}}


def test_shao_uplift_2022_is_the_time_mean_shao_estimate():
    assert K.values(_run())["shao_uplift_2022_gbp_mwh"] == 15.934304935351477
    assert "TBC" not in K.DECLARED["shao_uplift_2022_gbp_mwh"]["run_field"]


def test_shao_uplift_2022_refuses_another_rule():
    with pytest.raises(ValueError, match="shao"):
        K.values(_run("model"))
