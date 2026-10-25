"""RB v1.1 W2 (ruling R23 (a), decision 0163: "modelled" in both the release and the paper; card [internal ticket] item 1).

The gap is a model output, so the release calls it "modelled", never "estimated": the run file's gap[y].basis and the
basis of every figures key that is the gap, a part of it, a bill total, a range end, a one-at-a-time or sensitivity row,
or a table of those. Only the labelled estimates of decision 0007 that sit beside the gap (lost value, other gas users,
the EII shift) and the provisional input estimates of the carbon block keep "estimated". Light: the released v4-s37
run file and a stand-in build.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"

# The modules whose keys are labelled estimates (0007) or provisional input estimates, not the gap.
ESTIMATE_MODULES = {"lost_value", "eii_shift", "non_power_gas", "carbon_split"}
GAP_KEYS = ("headline_2002_24_gbp_bn", "gap_2024_gbp_bn", "gap_2025p_gbp_bn", "gap_2022_gbp_bn",
            "headline_2002_24_low_gbp_bn", "headline_2002_24_high_gbp_bn", "headline_range_text",
            "wf_power_before_carbon_gbp_bn", "wf_vat_gbp_bn", "nz_bill_2002_24_gbp_bn", "rb_bill_2002_24_gbp_bn",
            "cost_per_household_2002_24_gbp", "table_one_at_a_time", "table_results_by_year",
            "table_waterfall_2002_24", "table_waterfall_by_year", "table_options_2025p", "annex_b_annual_tables",
            "table_household_by_year", "table_exceptions_register", "table_sensitivity_rows_0144",
            "gap_ucl_period", "annex_b_low_end", "annex_b_high_end")


def test_run_file_gap_basis_is_modelled_even_when_a_line_is_estimated():
    from gascf import bills as B
    from gascf import export_v4 as E
    line = lambda basis: {"basis": basis}      # noqa: E731
    built = {y: {"households": 28e6, "netzero": [line("measured"), line("estimated")],
                 "fossil": [line("modelled")]} for y in B.YEARS}
    rg = {y: {"central": 100.0, "low": 90.0, "high": 110.0} for y in B.YEARS}
    gap = E._gap(built, rg)
    assert {g["basis"] for g in gap.values()} == {"modelled"}


def test_no_gap_key_says_estimated():
    from tools import figures as F
    from tools import figures_keys
    run = json.loads(S37_RUN.read_text())
    module_of = {}
    for m in F._modules():
        for k in m.DECLARED:
            module_of[k] = m.__name__.rsplit(".", 1)[1]
    keys = F.generate(run)["keys"]
    wrong = sorted(k for k, e in keys.items()
                   if e["meta"]["basis"] == "estimated" and module_of[k] not in ESTIMATE_MODULES)
    assert wrong == []
    for k in GAP_KEYS:
        assert keys[k]["meta"]["basis"] == "modelled", k
    assert set(figures_keys.MODULES) >= ESTIMATE_MODULES


def test_labelled_estimates_keep_estimated():
    from tools import figures as F
    keys = F.generate(json.loads(S37_RUN.read_text()))["keys"]
    for k in ("lost_value_2002_24_central_gbp_bn", "npg_estimate_2002_24_central_gbp_bn", "eii_shift_2018_24_low",
              "cps_2025p_gbp_m"):
        assert keys[k]["meta"]["basis"] == "estimated", k
