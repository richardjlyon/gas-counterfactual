"""Ticket 19, spec test 4: figures keys per waterfall step from the run file's
bills[y].netzero_on_household_bill_per_household.by_step (real £m in the run's price base)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import figures as F  # noqa: E402


def _run():
    bills = {}
    for y in range(2002, 2026):
        by = {str(n): {"real_gbp_m": float(n * 10 + (y - 2000))} for n in range(1, 10)}
        bills[str(y)] = {"netzero_on_household_bill_per_household": {"by_step": by}}
    return {"meta": {"engine_version": "toy", "price_base": 2025}, "bills": bills}


def test_step_4_and_5_window_totals_exist_and_add_to_the_combined_value():
    from tools.figures_keys import household as K
    from tools import figures_keys
    assert "household" in figures_keys.MODULES
    v = F.generate(_run(), modules=[K])["keys"]
    k4, k5 = "rb.household_bill.by_step_real_bn_total.4.2006-2025", "rb.household_bill.by_step_real_bn_total.5.2006-2025"
    want4 = sum(40 + (y - 2000) for y in range(2006, 2026)) / 1e3
    want5 = sum(50 + (y - 2000) for y in range(2006, 2026)) / 1e3
    assert v[k4]["value"] == pytest.approx(want4) and v[k5]["value"] == pytest.approx(want5)
    assert v[k4]["value"] + v[k5]["value"] == pytest.approx(want4 + want5)
    assert v["rb.household_bill.by_step_real_bn.4.2024"]["value"] == pytest.approx(0.064)
    assert "Backup" in v[k4]["meta"]["label"] and "grid" in v[k5]["meta"]["label"]
    for w in ("2006-2023", "2006-2024", "2006-2025", "2002-2025"):
        assert all(f"rb.household_bill.by_step_real_bn_total.{n}.{w}" in v for n in range(1, 10))
