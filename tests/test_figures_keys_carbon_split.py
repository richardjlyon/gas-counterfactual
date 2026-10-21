"""s36 ticket 21: figures keys for the 2025 provisional pair (tools/figures_keys/carbon_split.py), run file only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import figures as F  # noqa: E402
from tools.figures_keys import carbon_split as K  # noqa: E402


def _run():
    return {"meta": {"engine_version": "toy", "price_base": 2025},
            "carbon_2025p": {"ets_power_2025p_gbp_m": 900.03, "cps_2025p_gbp_m": 428.0,
                             "cps_2025p_range_high_gbp_m": 468.0, "money": "cash", "status": "provisional"}}


def test_2025_pair_keys_share_one_money_field_and_are_provisional():
    from tools import figures_keys
    assert "carbon_split" in figures_keys.MODULES
    assert {k: K.values(_run())[k] for k in K.P2025} == {"ets_power_2025p_gbp_m": 900.03, "cps_2025p_gbp_m": 428.0,
                                "cps_2025p_range_high_gbp_m": 468.0}
    assert {K.DECLARED[k]["money"] for k in K.P2025} == {"cash"}          # the 2025 pair (0110 added a 2024-price key)
    assert all(K.DECLARED[k]["provisional"] for k in K.P2025)
    assert K.values(_run())[K.SHORTFALL_KEY] is None                    # no block in this run
    assert set(F.generate(_run(), modules=[K])["keys"]) == set(K.DECLARED)
