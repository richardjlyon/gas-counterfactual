"""Ticket 18: figures keys for the UCL crisis-year sensitivity (figures-keys.md rows 93-99), read from the
run file's `moe_crisis` block. Gap keys in 2024 £ (CPIH), £bn; ratio keys the low and high over 2021-23.

v4-s39 (card [internal ticket]; decision 0164 and its addendum, Richard Lyon 21 Oct 2026): the central 2021-23 gap
uses the re-estimated price effect May 2021-Dec 2023 (M9 B), so the block carries a `central` column beside
`shao` (Shao's uplift in every month, the v4-s38 central). The UCL methods-page row is measured against the
central (0164 addendum housekeeping: "re-based on the new central")."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402

RUN = {"meta": {"engine_version": "toy"}, "moe_crisis": {
    "central_rule": "m9_direct_mayon",
    "years": {"2021": {"central": {"national_gbp_m_nominal": 9000.0}, "shao": {"national_gbp_m_nominal": 10000.0},
                       "ucl_stmoe": {"national_gbp_m_nominal": 8000.0}},
              "2022": {"central": {"national_gbp_m_nominal": 7000.0}, "shao": {"national_gbp_m_nominal": 11000.0},
                       "ucl_stmoe": {"national_gbp_m_nominal": 6000.0}},
              "2023": {"central": {"national_gbp_m_nominal": 10500.0}, "shao": {"national_gbp_m_nominal": 12000.0},
                       "ucl_stmoe": {"national_gbp_m_nominal": 11000.0}}},
    "ucl_over_shao": {"total": {"2021": 1.71, "2022": 3.54, "2023": 1.59},
                      "wind": {"2021": 2.37, "2022": 4.94, "2023": 2.22}}}}


def _to24(n, y):
    from gascf import deflator_cpih as dfl
    return dfl.to_real(n, y, 2024) / 1e3


def test_moe_crisis_keys_from_the_run_file():
    from tools.figures_keys import moe_crisis as K
    from tools import figures_keys
    assert "moe_crisis" in figures_keys.MODULES
    v = F.generate(RUN, modules=[K])["keys"]
    central = _to24(9000, 2021) + _to24(7000, 2022) + _to24(10500, 2023)
    shao = _to24(10000, 2021) + _to24(11000, 2022) + _to24(12000, 2023)
    ucl = _to24(8000, 2021) + _to24(6000, 2022) + _to24(11000, 2023)
    assert v["gap_2021_23_central_gbp_bn"]["value"] == pytest.approx(central)
    assert v["gap_2021_23_shao_gbp_bn"]["value"] == pytest.approx(shao)
    assert v["gap_2021_23_ucl_gbp_bn"]["value"] == pytest.approx(ucl)
    assert v["gap_2021_23_ucl_difference_gbp_bn"]["value"] == pytest.approx(ucl - central)
    assert (v["ucl_over_shao_total_low"]["value"], v["ucl_over_shao_total_high"]["value"]) == (1.59, 3.54)
    assert (v["ucl_over_shao_wind_low"]["value"], v["ucl_over_shao_wind_high"]["value"]) == (2.22, 4.94)
    for meta in (x["meta"] for x in v.values()):
        assert meta["basis"] == "modelled"
        assert "printed p.22 (PDF p.24)" in meta["source"]


def test_labels_say_which_rule_is_central():
    from tools.figures_keys import moe_crisis as K
    d = K.DECLARED
    assert "central" in d["gap_2021_23_central_gbp_bn"]["label"]
    assert "May 2021" in d["gap_2021_23_central_gbp_bn"]["label"]
    assert "(central)" not in d["gap_2021_23_shao_gbp_bn"]["label"]
    assert "v4-s38" in d["gap_2021_23_shao_gbp_bn"]["label"]
    assert "less central" in d["gap_2021_23_ucl_difference_gbp_bn"]["label"]


def test_a_block_without_a_central_column_is_refused():
    """A block with no `central` column, in a run whose central rule is M9 B, must not be read as if Shao were still
    central (card [internal ticket]). A pre-v4-s39 run (central rule 'shao') reads Shao as its own central: see
    tests/test_shao_relabel_v4_s39.py."""
    from tools.figures_keys import moe_crisis as K
    old = {"meta": {**RUN["meta"], "central_settings": {"moe_crisis": "m9_direct_mayon"}},
           "moe_crisis": {**RUN["moe_crisis"], "years": {
               y: {k: r[k] for k in ("shao", "ucl_stmoe")} for y, r in RUN["moe_crisis"]["years"].items()}}}
    with pytest.raises(KeyError):
        K.values(old)
