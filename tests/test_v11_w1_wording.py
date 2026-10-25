"""RB v1.1 W1 (decision 0160, card [internal ticket]): release wording, no number moves (paper line 1200).

The expected words are literals: the wording the fact register's checker gave for each Annex A row (decision 0154
rule 1, logged in reliable-britain review/fact-register-v1-changes.md and applied by the paper's fill/make_figures.py
as REGISTER_OVERRIDES and REGISTER_FIXES), and the per-household name ruled under 0144 item 5b. Once the release
carries them, the paper no longer needs to rewrite its own Annex A rows. W2 ("estimated" vs "modelled") is ruling
R23 and is not touched here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

S37_RUN = ROOT / "out/v4/2026-10-20-s37.json"


@pytest.fixture(scope="module")
def keys():
    from tools import figures as F
    return F.generate(json.loads(S37_RUN.read_text()))["keys"]


# key -> (field, text that must appear, text that must be gone)
FIXES = {
    "sourced.ucl_net_benefit_gbp_bn": ("label", "v1: abstract, PDF p.3 (printed p.1) (", "v1: abstract, PDF p.1 ("),
    "sourced.ucl_period_years": ("label", "v1: abstract, PDF p.3 (printed p.1):", "v1: abstract, PDF p.1:"),
    "sourced.casoli_sr_gas_supply_median": ("label", "Casoli, Manera and Valenti (2022, updated version July 2023), FEEM",
                                            "Casoli, Manera and Valenti (2022), FEEM"),
    "sourced.albrizio_eu_weighted_gas_demand_elasticity": ("label", "Russian Gas Shut-off to the European Union,",
                                                           "Russian Gas Shut-off to the EU,"),
    "sourced.generator_share_pct": ("label", "\"27% of total transmission revenue is recovered from generation "
                                             "customers ... This ratio is fixed in the charging methodology\"",
                                    "\"27% of total transmission revenue is recovered from generation\", fixed"),
    "sourced.scottish_nlr_2005_06_gbp_m": ("label", "BETTA: Final proposals and impact assessment (December 2004)",
                                           "BETTA: final proposals (December 2004)"),
    "sourced.spt_nlr_2005_06_gbp_m": ("label", "'SP Transmission price controls', 'Roll forward price controls "
                                               "(without BETTA adjustments)'",
                                      "'SP Transmission price controls, roll forward (without BETTA adjustments)'"),
    "sourced.ukets_incentives_defra_2006_results_gbp_m": ("label", "penultimate column '2002 - 2006",
                                                          "last column '2002 - 2006"),
    "sourced.ccl_2001_rate_real_p_kwh": ("label", "ONS CPIH (L522): CPIH 2024", "ONS CPIH (L522): Sch. 6 para 42(1); CPIH"),
    # W6 (card [internal ticket] item 7) re-labels this key as the two-year average it is (tests/test_v11_w6_eesop.py)
    "sourced.eesop_fy2001_02_level_gbp_m": ("label", "average a year over April 2000 to March 2002",
                                            "supplier cost £110 million over April 2000 to March 2002, halved"),
    "sourced.eesop_elec_share_pct": ("label", "in App. 5, pp.63-64 (PDF pp.69-70))", "in App. 5, PDF pp.63-64)"),
    "ets_power_2025p_gbp_m": ("label", "2024 share)", "DESNZ figure about 30 Nov 2026"),
    "cps_2025p_gbp_m": ("label", "HMRC's next estimate of receipts from the Carbon Price Floor for 2025, in the "
                                 "Environmental Taxes Bulletin tables due in March 2027", "final HMRC data March 2027"),
    "sourced.coal_cm_excluded_gw": ("label", "\"Coal cannot take part in the T-4 auctions anymore due to CM emissions "
                                             "limits which apply from 1st October 2024 for Capacity in operation before "
                                             "July 2019. Therefore the 11 GW of Coal that previously took part in the "
                                             "T-4 auctions from 2017/18 are no longer able to gain CM agreements.\"",
                                    None),
    "sourced.nao_balancing_2005_06_gbp_m": ("units", "£m; price basis not stated by NAO; treated as cash", None),
    "sourced.epg_cost_gbp_m": ("units", "£m, cash, estimate; United Kingdom, gas and electricity together", None),
    "gas_feedback_e_central": ("label", "the pair of Albrizio et al. 2022 (IMF WP/22/143), combined by their equation 5, "
                                        "pp.13-14", None),
    "gas_feedback_e_supply_central": ("label", "Albrizio et al. 2022 (p.12) take 0.06 from Krichene (2002), Energy "
                                               "Economics 24(6); Krichene 2005 (IMF WP/05/32), Table 5, p.20, prints "
                                               "the same short-run figure", "as Albrizio use it"),
    "gas_feedback_e_demand_central": ("label", "0.084 x 0.23 + 0.24 x 0.34 + 0.136 x 0.32 + 0.22 x 0.11 = 0.169", None),
}


@pytest.mark.parametrize("key", sorted(FIXES))
def test_w1_register_wording_is_the_checked_wording(keys, key):
    field, want, gone = FIXES[key]
    s = keys[key]["meta"][field]
    assert want in s, (key, s)
    if gone:
        assert gone not in s, (key, s)


def test_w1_per_household_labels_use_the_ruled_name(keys):
    for k, e in keys.items():
        lab = e["meta"]["label"]
        assert "cost to britain per household" not in lab.lower(), k
    assert keys["cost_per_household_2024_gbp"]["meta"]["label"].startswith(
        "Extra cost of net zero on electricity bills, per household")