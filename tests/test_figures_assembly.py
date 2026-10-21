"""Ticket 29: figures.json for Report No. 1 (0006, 0045, 0098, 0100).

Seams: `gascf.figures.to_2024` (the one 2024-price conversion), `tools.figures.generate(run)` (the
built figures.json payload) and `gascf.figures.load_sourced` (the sourced section, 0100).
Inputs: the v4-s35 run file (2025 money). s35 values are references, not quotable; re-pinned on the
s36 release run (35), never loosened."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import deflator_cpih  # noqa: E402
from gascf import figures as GF  # noqa: E402

S35 = ROOT / "out/v4/2026-10-14-s35.json"


@pytest.fixture(scope="module")
def run():
    return json.loads(S35.read_text())


def test_to_2024_is_value_times_cpih2024_over_cpih_run_base(run):
    c = deflator_cpih.cpih()
    assert run["meta"]["price_base"] == 2025
    assert GF.to_2024(1000.0, run) == pytest.approx(1000.0 * c[2024] / c[2025], rel=0, abs=1e-12)


def test_to_2024_refuses_a_run_on_another_deflator(run):
    other = {"meta": dict(run["meta"], deflator="HMT GDP deflator")}
    with pytest.raises(ValueError, match="deflator"):
        GF.to_2024(1.0, other)


def test_to_2024_agrees_with_the_runs_own_real_and_nominal_2024(run):
    t = run["bills"]["2024"]["totals"]
    assert GF.to_2024(t["nz_real"], run) == pytest.approx(t["nz_gbp_m"], rel=1e-12)


from tools import figures as F  # noqa: E402

YEARS_02_24 = [str(y) for y in range(2002, 2025)]


@pytest.fixture(scope="module")
def built(run):
    return F.generate(run)


def _v(built, key):
    return built["keys"][key]["value"]


def test_headline_2002_24_is_sum_of_gap_2002_24_in_2024_prices(run, built):
    s = sum(run["gap"][y]["national_gbp_bn_real"] for y in YEARS_02_24)
    assert _v(built, "headline_2002_24_gbp_bn") == pytest.approx(GF.to_2024(s, run), rel=0, abs=1e-9)


def test_2025_never_enters_a_2002_24_key(run, built):
    bumped = json.loads(json.dumps(run))
    bumped["gap"]["2025"]["national_gbp_bn_real"] += 100.0
    bumped["bills"]["2025"]["totals"]["gap_real_bn"] += 100.0
    again = F.generate(bumped)
    assert any("2002_24" in k for k in built["keys"])
    for k, e in built["keys"].items():
        if "2002_24" in k:
            assert again["keys"][k]["value"] == e["value"], k


def test_gap_2002_25_kept_but_not_for_print(run, built):
    e = built["keys"]["gap_2002_25"]
    s = sum(run["gap"][str(y)]["national_gbp_bn_real"] for y in range(2002, 2026))
    assert e["value"] == pytest.approx(GF.to_2024(s, run), rel=0, abs=1e-9)
    assert e["meta"]["print"] is False
    assert built["keys"]["headline_2002_24_gbp_bn"]["meta"]["print"] is True


WF_KEYS = ["wf_power_before_carbon_gbp_bn", "wf_carbon_gbp_bn", "wf_ro_gbp_bn", "wf_fit_gbp_bn", "wf_cfd_gbp_bn",
           "wf_cm_gbp_bn", "wf_balancing_gbp_bn", "wf_grid_gbp_bn", "wf_ccl_extra_gbp_bn", "wf_schemes_gbp_bn",
           "wf_vat_gbp_bn"]


def test_waterfall_steps_sum_to_the_headline(built):
    total = sum(_v(built, k) for k in WF_KEYS)
    assert total == pytest.approx(_v(built, "headline_2002_24_gbp_bn"), rel=0, abs=0.01)


def test_carbon_line_is_nz1c_only(run, built):
    nz1c = sum(run["bills"][y]["nz1c"]["national_gbp_m_real"] for y in YEARS_02_24)
    nz8 = sum(x["national_gbp_m_real"] for y in YEARS_02_24 for x in run["bills"][y]["netzero"] if x["id"] == "NZ8")
    c = _v(built, "carbon_line_2002_24_gbp_bn")
    assert c == pytest.approx(GF.to_2024(nz1c, run) / 1e3, rel=0, abs=1e-9)
    assert c == pytest.approx(_v(built, "wf_carbon_gbp_bn"), rel=0, abs=1e-9)
    assert GF.to_2024(nz8, run) / 1e3 == pytest.approx(18.198, abs=5e-4)   # s35 reference, not quotable
    assert c == pytest.approx(74.062, abs=5e-4)                              # s35 reference, not quotable


def test_wf_carbon_reads_step2_only(run, built):
    poisoned = json.loads(json.dumps(run))
    for y in YEARS_02_24:
        b = poisoned["bills"][y]
        b.pop("waterfall_grouped", None)
        b["netzero_groups"] = {"carbon_price_receipts": {"lines": ["NZ1c", "NZ8"], "national_gbp_m_nominal": 9e9}}
    again = F.generate(poisoned)
    assert _v(again, "wf_carbon_gbp_bn") == _v(built, "wf_carbon_gbp_bn")
    assert _v(built, "wf_carbon_gbp_bn") == pytest.approx(74.062, abs=5e-4)   # s35 reference, not quotable


def _line(run, y, ident):
    b = run["bills"][y]
    return next(x["national_gbp_m_real"] for x in b["netzero"] + b["gasonly"] if x["id"] == ident)


def _sum_line_bn(run, ident, years=YEARS_02_24):
    return GF.to_2024(sum(_line(run, y, ident) for y in years), run) / 1e3


def _nominal_bn(run, field, years=YEARS_02_24):
    return GF.to_2024(sum(deflator_cpih.to_real(run["fleet"][y][field], int(y), 2025) for y in years), run) / 1e3


Y02_05 = ["2002", "2003", "2004", "2005"]
SCALARS = {   # figures-keys.md §1, the "29" rows: expected value from the run, by the table's formula
    "nz_bill_2002_24_gbp_bn": lambda r: GF.to_2024(sum(r["bills"][y]["totals"]["nz_real"] for y in YEARS_02_24), r) / 1e3,
    "rb_bill_2002_24_gbp_bn": lambda r: GF.to_2024(sum(r["bills"][y]["totals"]["go_real"] for y in YEARS_02_24), r) / 1e3,
    "gap_2025p_gbp_bn": lambda r: GF.to_2024(r["gap"]["2025"]["national_gbp_bn_real"], r),
    "gap_2024_gbp_bn": lambda r: GF.to_2024(r["gap"]["2024"]["national_gbp_bn_real"], r),
    "gap_2022_gbp_bn": lambda r: GF.to_2024(r["gap"]["2022"]["national_gbp_bn_real"], r),
    "nz_bill_2024_gbp_bn": lambda r: GF.to_2024(r["bills"]["2024"]["totals"]["nz_real"], r) / 1e3,
    "rb_bill_2024_gbp_bn": lambda r: GF.to_2024(r["bills"]["2024"]["totals"]["go_real"], r) / 1e3,
    "nz_bill_2025p_gbp_bn": lambda r: GF.to_2024(r["bills"]["2025"]["totals"]["nz_real"], r) / 1e3,
    "rb_bill_2025p_gbp_bn": lambda r: GF.to_2024(r["bills"]["2025"]["totals"]["go_real"], r) / 1e3,
    "s1_same_in_both_2024_gbp_bn": lambda r: GF.to_2024(sum(x["national_gbp_m_real"] for x in r["bills"]["2024"]["same_in_both"]), r) / 1e3,
    "firm_capacity_rb_gw_2024": lambda r: r["firm_capacity"]["2024"]["gasonly_gw"],
    "firm_capacity_nz_gw_2024": lambda r: r["firm_capacity"]["2024"]["netzero_gw"],
    "grid_window_2002_05_gbp_m": lambda r: GF.to_2024(sum(_line(r, y, "NZ7") - _line(r, y, "GO5") for y in Y02_05), r),
    "balancing_window_2002_05_gbp_m": lambda r: GF.to_2024(sum(_line(r, y, "NZ6") - _line(r, y, "GO4") for y in Y02_05), r),
    "nz5_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "NZ5"),
    "nz6_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "NZ6"),
    "go4_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "GO4"),
    "nz7_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "NZ7"),
    "go5_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "GO5"),
    "nz10_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "NZ10"),
    "grid_line_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "NZ7") - _sum_line_bn(r, "GO5"),
    "balancing_line_2002_24_gbp_bn": lambda r: _sum_line_bn(r, "NZ6") - _sum_line_bn(r, "GO4"),
    "moe_uplift_2002_24_gbp_bn": lambda r: _nominal_bn(r, "moe_gbp_m") + _nominal_bn(r, "moe_kept_gbp_m"),
    "years_shao_larger_count": lambda r: sum(r["fleet"][y]["moe"]["shao_mean_gbp_mwh"] > r["fleet"][y]["moe"]["model_mean_gbp_mwh"] for y in YEARS_02_24),
    "gas_price_rise_2024_pct": lambda r: 100 * r["answers"]["gas_break_even"]["2024"]["price_rise_frac_central"],
    "rb_extra_gas_twh_2024": lambda r: r["answers"]["gas_break_even"]["2024"]["dq_twh"],
    "break_even_gas_rise_2024_pct": lambda r: 100 * (r["answers"]["gas_break_even"]["2024"]["gas_price_gbp_mwh_break_even"]
                                                     / r["answers"]["gas_break_even"]["2024"]["gas_price_gbp_mwh_actual"] - 1),
    "plant_cost_edition_2024": lambda r: r["fleet"]["2024"]["cost_edition"],
    "rb_new_build_gw_2024": lambda r: r["fleet"]["2024"]["new_gw"],
    "negative_gap_years": lambda r: [int(y) for y in YEARS_02_24 if r["gap"][y]["national_gbp_bn_real"] < 0],
    "cost_per_household_2002_24_gbp": lambda r: GF.to_2024(sum(r["gap"][y]["per_household_real"] for y in YEARS_02_24), r),
    "cost_per_household_2024_gbp": lambda r: GF.to_2024(r["gap"]["2024"]["per_household_real"], r),
    "cost_per_household_2025p_gbp": lambda r: GF.to_2024(r["gap"]["2025"]["per_household_real"], r),
    "own_bills_per_household_2002_24_gbp": lambda r: GF.to_2024(sum(r["bills"][y]["netzero_on_household_bill_per_household"]["value"] for y in YEARS_02_24), r),
    "own_bills_per_household_2024_gbp": lambda r: GF.to_2024(r["bills"]["2024"]["netzero_on_household_bill_per_household"]["value"], r),
    "own_bills_per_household_2025p_gbp": lambda r: GF.to_2024(r["bills"]["2025"]["netzero_on_household_bill_per_household"]["value"], r),
}


@pytest.mark.parametrize("key", sorted(SCALARS))
def test_29_scalar_keys_follow_the_figures_keys_formula(run, built, key):
    want = SCALARS[key](run)
    got = _v(built, key)
    if isinstance(want, float):
        assert got == pytest.approx(want, rel=0, abs=1e-9)
    else:
        assert got == want


def test_margin_and_coal_cap_parameters_in_percent(built):
    from gascf import capacity, fossil_like_for_like as L
    assert _v(built, "margin_central_pct") == pytest.approx(100 * capacity.margin_fraction("central"), abs=1e-12)
    assert _v(built, "margin_low_pct") == pytest.approx(6.6, abs=0.05)     # 4 / 61 GW (decision 0133; 6.2 before)
    assert _v(built, "margin_high_pct") == pytest.approx(8.2, abs=0.05)    # 5 / 61 GW (decision 0133; 7.8 before)
    assert _v(built, "coal_lf_cap_pct") == pytest.approx(100 * L.dukes_coal_lf_max()[0], abs=1e-12)


def test_2025_keys_are_flagged_provisional(built):
    for k, e in built["keys"].items():
        if "2025p" in k:
            assert e["meta"]["provisional"] is True, k


def test_table_waterfall_rows_are_step_keys(built):
    rows = _v(built, "table_waterfall_2002_24")
    assert [r["key"] for r in rows] == WF_KEYS
    assert all(r["value"] == _v(built, r["key"]) for r in rows)
    assert sum(r["value"] for r in rows) == pytest.approx(_v(built, "headline_2002_24_gbp_bn"), abs=0.01)
    by = {r["key"]: r for r in rows}
    assert by["wf_carbon_gbp_bn"]["lines"] == ["NZ1c"]
    assert by["wf_ccl_extra_gbp_bn"]["lines"] == ["NZ8"]
    assert not any({"NZ1c", "NZ8"} <= set(r["lines"]) for r in rows)


def test_table_lines_2024_ccl_own_row(run, built):
    rows = _v(built, "table_lines_2024")
    by = {r["id"]: r for r in rows}
    nz8 = by["NZ8"]
    assert nz8["label"] == "Climate Change Levy, electricity"
    assert "carbon" not in json.dumps({k: v for k, v in nz8.items() if k != "label"}).lower()
    for i in ("NZ1c", "NZ1c_tax", "NZ1c_price"):
        assert by[i]["of_which"] == "NZ1" and by[i]["added"] is False, i
    assert by["NZ1c_tax"]["value"] + by["NZ1c_price"]["value"] == pytest.approx(by["NZ1c"]["value"], abs=1e-9)
    assert not any("Carbon tax collected" in r["label"] and "CCL" in r["label"] for r in rows)
    added_nz = sum(r["value"] for r in rows if r["added"] and r["bill"] == "net_zero_britain")
    assert added_nz == pytest.approx(_v(built, "nz_bill_2024_gbp_bn") - _v(built, "s1_same_in_both_2024_gbp_bn"), abs=1e-6)


def test_table_results_by_year_columns(run, built):
    t = _v(built, "table_results_by_year")
    cols = built["keys"]["table_results_by_year"]["meta"]["columns"]
    assert not any("group" in c["source"] for c in cols)
    src = {c["name"]: c["source"] for c in cols}
    assert src["carbon_gbp_bn"] == "bills[y].nz1c" and src["ccl_gbp_bn"] == "NZ8"
    assert [r["year"] for r in t] == list(range(2002, 2026))
    for r in t:
        y = str(r["year"])
        assert r["carbon_gbp_bn"] == pytest.approx(GF.to_2024(run["bills"][y]["nz1c"]["national_gbp_m_real"], run) / 1e3, abs=1e-12)
        assert r["ccl_gbp_bn"] == pytest.approx(GF.to_2024(_line(run, y, "NZ8"), run) / 1e3, abs=1e-12)
        assert r["gap_gbp_bn"] == pytest.approx(GF.to_2024(run["gap"][y]["national_gbp_bn_real"], run), abs=1e-12)
        assert r["provisional"] is (y == "2025")


CCL_LABEL_KEYS = ["carbon_line_2002_24_gbp_bn", "carbon_price_receipts_2002_24_gbp_bn", "carbon_rest_in_price_2002_24_gbp_bn",
                  "carbon_in_price_2005_12_gbp_bn", "carbon_price_receipts_2005_12_gbp_bn",
                  "carbon_shortfall_rule_price_receipts_2013_20_gbp_bn"]


def test_ccl_label_text(built):
    """EiC R2 (17 Oct): exact words. Keys built by 37 and 21 are checked once they are assembled."""
    present = [k for k in CCL_LABEL_KEYS if k in built["keys"]]
    assert "carbon_line_2002_24_gbp_bn" in present
    for k in present:
        lab = built["keys"][k]["meta"]["label"]
        assert "excludes the CCL at its main rates" in lab, k
        assert lab.count("excludes the CCL") == lab.count("excludes the CCL at its main rates"), k


def test_built_file_meta_and_byte_stability(tmp_path):
    from gascf import clock_export
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    F.write(S35, a)
    F.write(S35, b)
    assert a.read_bytes() == b.read_bytes()
    m = json.loads(a.read_text())["meta"]
    assert m["release_tag"] == "v4-s35"
    assert m["run_file_sha256"] == clock_export.sha256_file(S35)
    assert m["price_base"] == "2024 £ (CPIH L522)"
    assert len(m["commit"]) == 40


def test_release_record_lists_every_key_not_sourced():
    import types
    m = types.ModuleType("toy")
    base = {"label": "x", "basis": "modelled", "provisional": False, "ticket": "29", "run_field": "x"}
    m.DECLARED = {"a": base | {"status": "SOURCED"}, "b": base | {"status": "INTERIM_APPROVED"},
                  "c": base | {"status": "PLACEHOLDER"}, "d": base | {"status": "LOCATOR_TBC"}}
    m.values = lambda r: {"a": 1, "b": 2, "c": 3, "d": 4}
    out = F.generate({"meta": {"engine_version": "toy"}}, modules=[m])
    assert [k for k, _ in F.not_sourced(out)] == ["b", "c", "d"]
    m.DECLARED["e"] = base | {"status": "GUESSED"}
    m.values = lambda r: {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    with pytest.raises(ValueError, match="status"):
        F.generate({"meta": {"engine_version": "toy"}}, modules=[m])


def _sourced(tmp_path, entries):
    p = tmp_path / "sourced.yaml"
    p.write_text(json.dumps({"keys": entries}))
    return p


GOOD = {"value": 104.3, "units": "£bn, as published", "source": "O'Shea, Horne and Maslin (2025) preprint v1",
        "locator": "abstract, PDF p.1", "claims_id": "CR-S005", "status": "SOURCED"}


def test_sourced_refuses_no_locator_or_no_claims_id_unless_locator_tbc(tmp_path):
    ok = GF.load_sourced(_sourced(tmp_path, {"sourced.ucl_net_benefit_gbp_bn": GOOD}))
    assert ok["sourced.ucl_net_benefit_gbp_bn"]["value"] == 104.3
    for drop in ("locator", "claims_id"):
        bad = {k: v for k, v in GOOD.items() if k != drop}
        with pytest.raises(ValueError, match=drop):
            GF.load_sourced(_sourced(tmp_path, {"sourced.x": bad}))
        tbc = bad | {"status": "LOCATOR_TBC"}
        assert GF.load_sourced(_sourced(tmp_path, {"sourced.x": tbc}))["sourced.x"]["status"] == "LOCATOR_TBC"


@pytest.mark.parametrize("cid", ["CR-S039", "CR-S041", "CR-S044", "CR-S008", "CR-S050", "CR-S051", "CR-S048"])
def test_sourced_refuses_a_retired_claims_id(tmp_path, cid):
    with pytest.raises(ValueError, match="retired"):
        GF.load_sourced(_sourced(tmp_path, {"sourced.x": GOOD | {"claims_id": cid}}))


def test_sourced_refuses_two_keys_sharing_a_claims_id(tmp_path):
    with pytest.raises(ValueError, match="CR-S005"):
        GF.load_sourced(_sourced(tmp_path, {"sourced.a": GOOD, "sourced.b": GOOD}))


def test_old_sourced_qep_keys_are_gone(tmp_path):
    """Ticket 47: the three QEP ratio keys moved to modelled rb.pricing.*; the loader refuses the old sourced
    names, and the generated output has no sourced.qep_dayahead_ratio_* key."""
    from tools import figures as F
    from tools.figures_keys import pricing
    for name in ("sourced.qep_dayahead_ratio_2010_25", "sourced.qep_dayahead_ratio_min_2010_25",
                 "sourced.qep_dayahead_ratio_max_2010_25"):
        with pytest.raises(ValueError, match="modelled"):
            GF.load_sourced(_sourced(tmp_path, {name: GOOD | {"claims_id": "CR-S900"}}))
    k = F.generate({"meta": {"engine_version": "t"}}, modules=[pricing])["keys"]
    assert "rb.pricing.qep_dayahead_ratio_2010_25" in k
    assert not any(n.startswith("sourced.qep_dayahead_ratio") for n in k)


def test_old_sourced_grossup_key_is_gone(tmp_path):
    """Ticket 48: the BSUoS-basis gross-up factor moved to modelled rb.balancing.*; CR-S048 retired and the old
    sourced name refused; the generated output has no sourced.balancing_bsuos_basis_grossup_factor."""
    from tools import figures as F
    from tools.figures_keys import balancing_factors
    with pytest.raises(ValueError, match="modelled"):
        GF.load_sourced(_sourced(tmp_path, {"sourced.balancing_bsuos_basis_grossup_factor":
                                            GOOD | {"claims_id": "CR-S901"}}))
    k = F.generate({"meta": {"engine_version": "t"}}, modules=[balancing_factors])["keys"]
    assert "rb.balancing.bsuos_basis_grossup_factor" in k
    assert not any(n.startswith("sourced.balancing_bsuos_basis_grossup") for n in k)


# ---- ticket 37 (0090) CCL key-mapping: carbon-named keys exclude the CCL (NZ8) ----
Y05_12 = [str(y) for y in range(2005, 2013)]
Y13_20 = [str(y) for y in range(2013, 2021)]


def _nz1c_part(run, y, lid):
    step2 = [s for s in run["waterfall"][y] if tuple(s.get("lines") or ()) == ("NZ1c",)][0]
    return next(p["value_gbp_m_real"] for p in step2["parts"].values() if p["line"] == lid)


def _tax_bn(run, ys):
    return GF.to_2024(sum(_nz1c_part(run, y, "NZ1c_tax") for y in ys), run) / 1e3


def _nz8_bn(run, ys):
    return GF.to_2024(sum(_line(run, y, "NZ8") for y in ys), run) / 1e3


def test_carbon_price_receipts_keys_exclude_ccl(run, built):
    assert _v(built, "carbon_price_receipts_2002_24_gbp_bn") == pytest.approx(_tax_bn(run, YEARS_02_24), abs=1e-9)
    assert _v(built, "carbon_price_receipts_2002_24_gbp_bn") == pytest.approx(23.846, abs=1e-3)   # s35 ref
    assert _v(built, "carbon_price_receipts_2005_12_gbp_bn") == pytest.approx(_tax_bn(run, Y05_12), abs=1e-9)
    assert _v(built, "carbon_price_receipts_2005_12_gbp_bn") == pytest.approx(0.479, abs=1e-3)     # s35 ref
    # old combined group (receipts + NZ8) less the new key equals Σ NZ8 (the CCL it no longer carries)
    old24 = _tax_bn(run, YEARS_02_24) + _nz8_bn(run, YEARS_02_24)
    assert old24 - _v(built, "carbon_price_receipts_2002_24_gbp_bn") == pytest.approx(_nz8_bn(run, YEARS_02_24), abs=1e-9)
    assert _nz8_bn(run, YEARS_02_24) == pytest.approx(18.198, abs=1e-3)
    assert _nz8_bn(run, Y05_12) == pytest.approx(6.086, abs=1e-3)


def test_carbon_price_receipts_2013_20(run, built):
    assert _v(built, "carbon_price_receipts_2013_20_gbp_bn") == pytest.approx(_tax_bn(run, Y13_20), abs=1e-9)
    assert _v(built, "carbon_price_receipts_2013_20_gbp_bn") == pytest.approx(12.412, abs=1e-3)   # s35 ref


def test_carbon_rest_is_nz1c_price(run, built):
    rest = GF.to_2024(sum(_nz1c_part(run, y, "NZ1c_price") for y in YEARS_02_24), run) / 1e3
    assert _v(built, "carbon_rest_in_price_2002_24_gbp_bn") == pytest.approx(rest, abs=1e-9)
    assert _v(built, "carbon_rest_in_price_2002_24_gbp_bn") == pytest.approx(50.216, abs=1e-3)     # s35 ref
    assert (_v(built, "carbon_price_receipts_2002_24_gbp_bn") + _v(built, "carbon_rest_in_price_2002_24_gbp_bn")
            == pytest.approx(_v(built, "carbon_line_2002_24_gbp_bn"), abs=1e-9))
    assert _v(built, "carbon_line_2002_24_gbp_bn") == pytest.approx(74.062, abs=1e-3)              # s35 ref


def test_carbon_in_price_2005_12_is_all_nz1c(run, built):
    nz1c = GF.to_2024(sum(run["bills"][y]["nz1c"]["national_gbp_m_real"] for y in Y05_12), run) / 1e3
    price = GF.to_2024(sum(_nz1c_part(run, y, "NZ1c_price") for y in Y05_12), run) / 1e3
    assert _v(built, "carbon_in_price_2005_12_gbp_bn") == pytest.approx(nz1c, abs=1e-9)
    assert _v(built, "carbon_in_price_2005_12_gbp_bn") == pytest.approx(16.639, abs=1e-3)          # s35 ref
    assert abs(_v(built, "carbon_in_price_2005_12_gbp_bn") - price) > 1e-2                          # not NZ1c_price (16.161)
