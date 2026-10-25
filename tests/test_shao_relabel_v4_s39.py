"""Card [internal ticket]: figures-key text that named Shao as the 2021-23 central uplift follows decision 0164 (M9 B:
re-estimated on outturn with direct coefficients, May 2021-Dec 2023; Shao in 2002-20, Jan-Apr 2021, 2024-25p)."""
from __future__ import annotations

from tools.figures_keys import annex_v11, held_rows, sens_0144, worked_hh


def test_sens_0144_note_no_longer_calls_shao_the_2021_23_central():
    t = sens_0144.DECLARED["note_uplift_2021_23_probably_low"]["label"]
    assert "the central uplift (Shao et al. pooled" not in t
    assert "0164" in t


def test_annex_v11_go1_equation_names_the_m9_re_estimate():
    row = next(r for r in annex_v11.EQUATIONS if r["id"] == "go1") if hasattr(annex_v11, "EQUATIONS") else None
    src = repr(row) if row else open(annex_v11.__file__).read()
    assert "May 2021 to Dec 2023" in src and "0164" in src


def test_held_rows_m10_no_longer_says_shao_stays_central():
    assert "(Shao stays central)" not in held_rows.__doc__


def test_shao_uplift_keys_say_they_are_not_the_2021_23_central():
    for k in ("shao_uplift_2021_gbp_mwh", "shao_uplift_2022_gbp_mwh", "shao_uplift_2023_gbp_mwh"):
        assert "0164" in worked_hh.DECLARED[k]["label"], k


def test_moe_crisis_keys_on_a_v4_s37_run_read_shao_as_that_runs_central():
    """A pre-v4-s39 run file has no `central` column and its central rule was Shao, so Shao is its central and the
    released v4-s37 keys are reproduced (the annex before/after reads them)."""
    import json
    from pathlib import Path
    import pytest
    from tools.figures_keys import moe_crisis
    run = json.loads((Path(__file__).resolve().parents[1] / "out/v4/2026-10-20-s37.json").read_text())
    rel = json.loads((Path(__file__).resolve().parents[1] / "out/figures/v4-s37.json").read_text())["keys"]
    v = moe_crisis.values(run)
    assert v["gap_2021_23_central_gbp_bn"] == pytest.approx(v["gap_2021_23_shao_gbp_bn"], abs=1e-12)
    assert v["gap_2021_23_shao_gbp_bn"] == pytest.approx(34.88432043571801, abs=1e-9)          # v4-s37 key
    assert v["gap_2021_23_ucl_difference_gbp_bn"] == pytest.approx(rel["gap_2021_23_ucl_difference_gbp_bn"]["value"],
                                                                   abs=1e-9)
