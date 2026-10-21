"""Ticket 24 acceptance (0060): figures key household_share_2024_pct reads the run file's own 2024 domestic
share (bills[2024].netzero_on_household_bill_per_household.domestic_share) and is marked context only."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402


def test_household_share_2024_pct_reads_the_run_file_and_is_context_only():
    from tools import figures_keys
    from tools.figures_keys import household_share as K
    assert "household_share" in figures_keys.MODULES
    run = {"meta": {"engine_version": "toy"},
           "bills": {"2024": {"netzero_on_household_bill_per_household": {"domestic_share": 0.365434}},
                     "2025": {"netzero_on_household_bill_per_household": {"domestic_share": 0.365458}}}}
    k = F.generate(run, modules=[K])["keys"]["household_share_2024_pct"]
    assert k["value"] == pytest.approx(36.5434)
    assert k["meta"]["context_only"] is True and k["meta"]["headline"] is False
    assert k["meta"]["basis"] == "measured"
