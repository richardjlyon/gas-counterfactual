"""Decision 0122 (Richard Lyon, 19 Oct 2026), card item 1, and decision 0100: figures.json carries a `sourced.*`
section, one key per figure the paper quotes from a published source, each with its value, source, locator and
claims ID (or `claims_id_tbc` where the writer's register has none yet).

The list is the writer's 51 keys (draft-notes.md Part 1, copied to programme/research-audits/
v4-s36-recut-needs-2026-10-19.md). Values were read from the primaries on 20 Oct 2026; where the engine uses the same
figure the test checks the two agree (an independent check: the engine reads its own registered copy)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import figures as GF  # noqa: E402
from tools import figures as F  # noqa: E402

SOURCED = ROOT / "data/figures/sourced.yaml"
S36 = ROOT / "out/v4/2026-10-20-s36.json"

# The writer's list, by section (needs file §1). 51 keys.
WRITER_KEYS = {
    "2.5": ["reliability_standard_lole_hours_yr", "ecr2026_base_case_lole_hours_yr", "ecr2026_nondelivery_gw",
            "ecr2026_nondelivery_lole_hours_yr", "ecr2026_known_nondelivery_gw"],
    "2.7": ["vat_domestic_rate_pct", "gb_households_2024_m", "eii_exemption_pct_to_mar2024",
            "eii_exemption_pct_from_apr2024"],
    "3": ["ccc_2017_bill_fall_since_2008_gbp", "ccc_2017_household_saving_gbp_yr", "ccc_2017_lowcarbon_bill_2016_gbp",
          "ucl_net_benefit_gbp_bn", "ucl_period_years", "ucl_table10_sum_gbp_bn"],
    "7": ["cm_standstill_deferred_paid_gbp_m"],
    "8": ["ucl_lt_moe_2022_gbp_mwh"],
    "9": ["casoli_sr_gas_supply_median"],
    "10": ["generator_share_pct", "scottish_nlr_2005_06_gbp_m", "spt_nlr_2005_06_gbp_m", "shetl_nlr_2005_06_gbp_m",
           "app8_spt_interconnector_allowance_gbp_m", "ofgem_so_revenue_target_gbp_bn"],
    "11": ["nao_balancing_2005_06_gbp_m", "balancing_energy_share_central", "balancing_energy_share_low_option",
           "balancing_ibc_over_actual_low_gbp_m", "balancing_ibc_over_actual_high_gbp_m"],
    "12": ["elasticity_households", "elasticity_non_households", "elasticity_low", "elasticity_high"],
    "13": ["ffl_nffo_payments_fy2001_02_gbp_m", "ffl_fy2001_02_level_gbp_m", "ukets_incentives_2002_06_gbp_m",
           "ukets_incentives_defra_2006_results_gbp_m", "ets_power_share_2009_low", "ets_power_share_2009_high",
           "employers_ni_secondary_rate_2001_pct", "ccl_2001_rate_real_p_kwh", "ccl_2024_rate_p_kwh",
           "eesop_fy2001_02_level_gbp_m", "eesop_elec_share_pct"],
    "16": ["coal_cm_excluded_gw", "egl_fy2023_24_gbp_bn", "egl_fy2024_25_gbp_bn", "eec_deemed_twh_2010",
           "cert_forecast_twh_2012", "epg_cost_gbp_m", "ebss_gb_cost_gbp_m"],
}
# Claims IDs settled with the writer (work/s36/tickets/sourced-keys-reconciliation.md, 17 Oct 2026); never renumbered.
CLAIMS = {"gb_households_2024_m": "CR-S001", "ccc_2017_bill_fall_since_2008_gbp": "CR-S002",
          "ccc_2017_household_saving_gbp_yr": "CR-S003", "ccc_2017_lowcarbon_bill_2016_gbp": "CR-S004",
          "ucl_net_benefit_gbp_bn": "CR-S005", "ucl_table10_sum_gbp_bn": "CR-S006", "ucl_period_years": "CR-S007",
          "generator_share_pct": "CR-S009", "ofgem_so_revenue_target_gbp_bn": "CR-S010",
          "app8_spt_interconnector_allowance_gbp_m": "CR-S011", "scottish_nlr_2005_06_gbp_m": "CR-S012",
          "spt_nlr_2005_06_gbp_m": "CR-S013", "shetl_nlr_2005_06_gbp_m": "CR-S014",
          "balancing_energy_share_central": "CR-S015", "balancing_energy_share_low_option": "CR-S016",
          "nao_balancing_2005_06_gbp_m": "CR-S017", "elasticity_households": "CR-S018",
          "elasticity_non_households": "CR-S019", "elasticity_low": "CR-S020", "elasticity_high": "CR-S021",
          "ets_power_share_2009_low": "CR-S022", "ets_power_share_2009_high": "CR-S023",
          "ccl_2001_rate_real_p_kwh": "CR-S024", "ccl_2024_rate_p_kwh": "CR-S025",
          "ffl_fy2001_02_level_gbp_m": "CR-S026", "eesop_fy2001_02_level_gbp_m": "CR-S027",
          "eesop_elec_share_pct": "CR-S028", "ukets_incentives_2002_06_gbp_m": "CR-S029",
          "coal_cm_excluded_gw": "CR-S032", "egl_fy2023_24_gbp_bn": "CR-S033", "egl_fy2024_25_gbp_bn": "CR-S034",
          "eec_deemed_twh_2010": "CR-S035", "cert_forecast_twh_2012": "CR-S036", "epg_cost_gbp_m": "CR-S037",
          "ebss_gb_cost_gbp_m": "CR-S038", "ukets_incentives_defra_2006_results_gbp_m": "CR-S042",
          "cm_standstill_deferred_paid_gbp_m": "CR-S043", "employers_ni_secondary_rate_2001_pct": "CR-S045",
          "ucl_lt_moe_2022_gbp_mwh": "CR-S046", "casoli_sr_gas_supply_median": "CR-S047",
          "ecr2026_base_case_lole_hours_yr": "CR-S052"}


@pytest.fixture(scope="module")
def entries():
    return GF.load_sourced(SOURCED)


# Decision 0133 (Richard Lyon, 20 Oct 2026, "a"): the margin's range and its 2027/28 peak, for claim 10. No claims ID yet.
DECISION_0133_KEYS = {"2.5": ["ecr2026_t1_derated_margin_low_gw", "ecr2026_t1_derated_margin_high_gw",
                              "ecr2026_base_case_peak_2027_28_gw"]}
# Decision 0144 item 2A (Richard Lyon, 20 Oct 2026; v4-s37): the gas-feedback pairs' sources, engine-checked.
DECISION_0144_KEYS = {"9": ["albrizio_eu_weighted_gas_demand_elasticity", "krichene_sr_gas_supply_table5",
                            "krichene_lr_gas_demand_table2"]}


def test_the_writers_51_keys_plus_0133s_3_and_no_others(entries):
    want = {f"sourced.{k}" for ks in WRITER_KEYS.values() for k in ks}
    assert len(want) == 51
    extra = {f"sourced.{k}" for ks in DECISION_0133_KEYS.values() for k in ks}
    extra44 = {f"sourced.{k}" for ks in DECISION_0144_KEYS.values() for k in ks}
    assert len(extra) == 3 and not extra & want and len(extra44) == 3 and not extra44 & (want | extra)
    assert set(entries) == want | extra | extra44
    for k in DECISION_0144_KEYS["9"]:
        assert entries[f"sourced.{k}"]["section"] == "9", k
    for sec, ks in (WRITER_KEYS | {"2.5": WRITER_KEYS["2.5"] + DECISION_0133_KEYS["2.5"]}).items():
        for k in ks:
            assert entries[f"sourced.{k}"]["section"] == sec, k


def test_claims_ids_as_settled_and_the_rest_flagged_tbc(entries):
    for name, e in entries.items():
        k = name.removeprefix("sourced.")
        if k in CLAIMS:
            assert e.get("claims_id") == CLAIMS[k], k
            assert not e.get("claims_id_tbc"), k
        else:
            assert e.get("claims_id_tbc") is True and "claims_id" not in e, k
    assert len([e for e in entries.values() if e.get("claims_id_tbc")]) == 10 + 3 + 3   # 0122's ten, 0133's, 0144's


def test_every_entry_has_value_units_source_locator_file_and_a_known_status(entries):
    for name, e in entries.items():
        for f in ("value", "units", "source", "locator", "file", "status"):
            assert e.get(f) not in (None, ""), (name, f)
        assert isinstance(e["value"], (int, float)) and not isinstance(e["value"], bool), name
        assert e["status"] in F.STATUSES, name
        if e.get("derived"):
            assert e.get("derivation"), name


def test_loader_accepts_claims_id_tbc_but_still_refuses_a_bare_missing_id(tmp_path):
    good = {"value": 3, "units": "h", "source": "s", "locator": "l", "status": "SOURCED"}
    p = tmp_path / "s.yaml"
    p.write_text(json.dumps({"keys": {"sourced.x": good | {"claims_id_tbc": True}}}))
    assert GF.load_sourced(p)["sourced.x"]["value"] == 3
    p.write_text(json.dumps({"keys": {"sourced.x": good}}))
    with pytest.raises(ValueError, match="claims_id"):
        GF.load_sourced(p)
    p.write_text(json.dumps({"keys": {"sourced.x": good | {"claims_id_tbc": True, "claims_id": "CR-S900"}}}))
    with pytest.raises(ValueError, match="tbc"):
        GF.load_sourced(p)


def _engine():
    from gascf import balancing as BL
    from gascf import bills as B
    from gascf import capacity
    from gascf import ccl_baseline as CCL
    from gascf import deflator_cpih
    from gascf import ets_auctions as E
    from gascf import grid
    from gascf import households
    from gascf import lost_value as LV
    from gascf import same_in_both
    from gascf.fossil_like_for_like import GAS_ELASTICITY_PAIRS
    from tools.figures_keys import ucl_period
    c = deflator_cpih.cpih()
    shares = B.balancing_workbook_shares()
    ng = BL.ng_table1()
    return {
        "vat_rate": lambda: 100 * same_in_both.domestic_vat_rate()["rate"],
        "households_2024": lambda: round(households.gb_households_count(2024) / 1e6, 3),
        "ucl_quote": lambda: 104.3 if "£104.3 billion" in ucl_period.DECLARED["gap_ucl_period"]["compare_to"]["quote"]
        else None,
        "ucl_period": lambda: len(ucl_period.PERIOD),
        # 0144 item 2A (v4-s37): the engine's pairs; 0.34 (Casoli) is no longer an engine setting
        "gas_e_supply_central": lambda: GAS_ELASTICITY_PAIRS["central"][0],
        "gas_e_demand_central": lambda: GAS_ELASTICITY_PAIRS["central"][1],
        "gas_e_demand_krichene": lambda: GAS_ELASTICITY_PAIRS["krichene_lr"][1],
        "tnuos_gen_fixed": lambda: 100 * grid.TNUOS_GEN_FIXED,
        "scottish_nlr": lambda: grid.baseline_nlr_fy() and None,      # raises unless 44.8 / 11.1 (its own guard)
        "nao_2005": lambda: BL.nao_totals()[2005],
        "share_2018": lambda: 100 * BL.energy_share_2018(),
        "share_max": lambda: 100 * max(shares.values()),
        "ng2010_actual": lambda: {f"{y}/{str(y + 1)[2:]}": ng[y]["actual"] for y in range(2001, 2005)},
        "e_households": lambda: LV.E_HOUSEHOLDS, "e_non_households": lambda: LV.E_NON_HOUSEHOLDS,
        "e_low": lambda: LV.E_LOW, "e_high": lambda: LV.E_HIGH,
        "nffo_85_5": lambda: B.SWITCHES[B.NFFO_85_5][0].otr_nz2_level_gbp_m,
        "otr_nz2_level": lambda: B.CENTRAL.otr_nz2_level_gbp_m,
        "ets_2009_low": lambda: 100 * E.stand_in_share(2009)["low"],
        "ets_2009_high": lambda: 100 * E.stand_in_share(2009)["high"],
        "ccl_2001_real": lambda: 100 * CCL.RATE_2001 * c[2024] / c[2001],
        "ccl_2024": lambda: 100 * CCL.fy_rate(2024),
        "margin_low_gw": lambda: capacity.MARGIN_GW_RANGE[0],
        "margin_high_gw": lambda: capacity.MARGIN_GW_RANGE[1],
        "margin_peak": lambda: capacity.margin_peak_gw(),               # 0133; refuses a workbook that disagrees
        "otr_nz10_spend": lambda: 55.0,
        "otr_nz10_share": lambda: 100 * B.CENTRAL.otr_nz10_level_gbp_m / 55.0,
    }


def test_sourced_values_agree_with_the_engine_where_it_uses_them(entries):
    eng = _engine()
    checked = 0
    for name, e in entries.items():
        chk = e.get("engine_check")
        if not chk:
            continue
        got = eng[chk]()
        checked += 1
        if chk == "scottish_nlr":
            continue                                   # grid.baseline_nlr_fy raised if the file moved
        if chk == "ng2010_actual":
            assert got == e["inputs"]["actual_costs"], name
            diffs = [e["inputs"]["outturn_ibc"][fy] - got[fy] for fy in got]
            want = min(diffs) if name.endswith("_low_gbp_m") else max(diffs)
            assert e["value"] == pytest.approx(round(want, 1), abs=1e-9), name
            continue
        assert e["value"] == pytest.approx(got, rel=1e-12, abs=1e-12), (name, got)
    assert checked >= 25


def test_nffo_key_equals_the_engines_named_range_row():
    from gascf import bills as B
    (st,) = B.SWITCHES[B.NFFO_85_5]
    e = GF.load_sourced(SOURCED)["sourced.ffl_nffo_payments_fy2001_02_gbp_m"]
    assert e["value"] == st.otr_nz2_level_gbp_m == 85.5


def test_derived_values_match_their_arithmetic(entries):
    e = lambda k: entries[f"sourced.{k}"]["value"]  # noqa: E731
    assert e("scottish_nlr_2005_06_gbp_m") == pytest.approx(e("spt_nlr_2005_06_gbp_m") + e("shetl_nlr_2005_06_gbp_m"))
    assert e("ucl_table10_sum_gbp_bn") == pytest.approx(12.8 + 96.4)
    assert e("ffl_fy2001_02_level_gbp_m") == 4 * 23
    assert e("eesop_elec_share_pct") == pytest.approx(100 * 4981 / (4981 + 6144), rel=1e-12)


def test_sourced_module_puts_every_entry_in_figures_json():
    from tools import figures_keys
    from tools.figures_keys import sourced as S
    assert "sourced" in figures_keys.MODULES
    run = json.loads(S36.read_text())
    keys = F.generate(run, modules=[S])["keys"]
    ent = GF.load_sourced(SOURCED)
    assert set(keys) == set(ent)
    for k, v in keys.items():
        assert v["value"] == ent[k]["value"]
        m = v["meta"]
        assert m["section"] == "sourced" and m["basis"] == "measured"
        assert m["source"] == ent[k]["source"] and m["locator"] == ent[k]["locator"]
        assert m["status"] == ent[k]["status"] and m["units"] == ent[k]["units"]
        assert m.get("claims_id") == ent[k].get("claims_id")
    F.assert_complete({"keys": keys})
