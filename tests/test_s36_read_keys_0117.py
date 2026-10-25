"""Decision 0117 (Richard Lyon, 19 Oct 2026, "do A"): the register keys (figures-keys.md) that only read fields the
s36 run already has, plus the three release-step differences of tickets 09, 10 and 17:

- 09 B4: NBP before October 2009 against QEP, as the v4-s35 to s36 difference (0108 item 1.10 option (a); not a QEP
  run, 0072), with F1's part (ticket 10) taken out so the two never overlap;
- 10 F1: Reliable Britain's balancing energy at its own feedback-raised gas price, on against off, read from the GO4
  line's own `gas_feedback_gbp_m` with GO7's VAT on it;
- 17: NZ5 with the nuclear CM column (0089 variant D) against nuclear at peak (v4-s35), one extra build.

Effects are on the gap (positive = more cost of net zero), run money then 2024 prices. Light tests on toy inputs; one
heavy test builds the central case to check the GO5 field."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gascf import bills as B

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
META = {"price_base": 2025, "deflator": "ONS CPIH L522"}


def _go(y, go4_nom, fb, d, go4_real=None):
    """A built-like year: GO4 (with F1's gas_feedback_gbp_m), GO7 (domestic_share) and NZ5."""
    return {"fossil": [{"id": "GO4", "national_gbp_m_nominal": go4_nom, "gas_feedback_gbp_m": fb},
                       {"id": "GO7", "national_gbp_m_nominal": 0.0, "domestic_share": d}],
            "netzero": [{"id": "NZ5", "national_gbp_m_nominal": 10.0}]}


def _prior(go4_real):
    return {"meta": {"engine_version": "v4-s35", "price_base": 2025},
            "bills": {str(y): {"gasonly": [{"id": "GO4", "national_gbp_m_real": go4_real(y)}]} for y in B.YEARS}}


# ------------------------------------------------------------------ release-step block

def test_b4_is_the_release_difference_less_f1_and_f1_is_the_go4_field_with_vat():
    from gascf import release_step_effects as R
    d = 0.4
    built = {y: _go(y, 100.0, 7.0 if y >= 2012 else 0.0, d) for y in B.YEARS}
    nz5_peak = {y: {"netzero": [{"id": "NZ5", "national_gbp_m_nominal": 4.0}]} for y in B.YEARS}
    prior = _prior(lambda y: B.real(100.0, y) + 30.0)        # s35's GO4 was 30 (real) higher in every year
    blk = R.block(built, prior=prior, build=lambda s: nz5_peak)
    for y in B.YEARS:
        row = blk["years"][str(y)]
        f1 = -B.real(7.0 if y >= 2012 else 0.0, y) * (1 + 0.05 * d)
        assert row["f1_gap_effect_gbp_m_real"] == pytest.approx(f1, rel=1e-12, abs=1e-12)
        # release difference: GO4 fell by 30 real -> gap +30 (x VAT); F1's part is not B4's
        total = -(B.real(100.0, y) - (B.real(100.0, y) + 30.0)) * (1 + 0.05 * d)
        assert row["b4_gap_effect_gbp_m_real"] == pytest.approx(total - f1, rel=1e-12)
        assert row["cm_nuclear_nz5_change_gbp_m_nominal"] == pytest.approx(6.0)
    assert blk["prior_release"] == "v4-s35"
    assert blk["nuclear_at_peak_settings"] == {"nuclear_cm_column": None}
    assert "0108 item 1.10" in blk["decisions"] and "0117" in blk["decisions"]


def test_prior_release_is_read_from_releases_yaml_and_sha_checked(tmp_path):
    from gascf import release_step_effects as R
    run = tmp_path / "prior.json"
    run.write_text('{"meta": {"engine_version": "v4-s35"}}')
    rel = tmp_path / "releases.yaml"
    rel.write_text('{"releases": [{"version": "v4-s35", "run_file": "prior.json", "run_sha256": "00"}]}')
    with pytest.raises(ValueError, match="sha256"):
        R.prior_release_run("v4-s35", releases=rel, root=tmp_path)
    import hashlib
    rel.write_text('{"releases": [{"version": "v4-s35", "run_file": "prior.json", "run_sha256": "%s"}]}'
                   % hashlib.sha256(run.read_bytes()).hexdigest())
    assert R.prior_release_run("v4-s35", releases=rel, root=tmp_path)["meta"]["engine_version"] == "v4-s35"


def test_block_registered():
    from gascf import export_v4 as X
    assert "gascf.release_step_effects" in X.BLOCK_MODULES


# ------------------------------------------------------------------ keys

def _run():
    years = {str(y): y for y in B.YEARS}
    fleet = {y: {"margin_on_gross_extra_gw": 0.1 * int(y), "imports_contracted_gw": 0.5,
                 "ic_called_twh": 1.0 if int(y) >= 2016 else None, "ic_called_halfhours": 2 if int(y) >= 2016 else None,
                 "kept_stations": ([["Drax", "unit 1", 660.0, "net_zero_policy"],
                                    ["Rugeley", "all", 1006.0, "mixed"]] if int(y) in (2016, 2017) else
                                   [["Drax", "unit 2", 660.0, "net_zero_policy"]])}
             for y in years}
    gas = {y: {"gasonly": [{"id": "GO5", "national_gbp_m_nominal": 100.0, "carried_gbp_m": 60.0}]} for y in years}
    rse = {"years": {y: {"b4_gap_effect_gbp_m_real": 1.0, "f1_gap_effect_gbp_m_real": -2.0,
                         "cm_nuclear_nz5_change_gbp_m_nominal": 3.0} for y in years}}
    return {"meta": {**META, "closures_register": {"path": "tests/fixtures/s23b_fossil_closures_fixture.yaml"}},
            "fleet": fleet, "bills": gas, "release_step_effects": rse,
            "firm_capacity": {"2024": {"gasonly_cm_split_gw": {"kept_coal_gw": 8.0}}},
            "capacity_market": {"2024": {"split_gw": {"nuclear_contracted_gw": 4.91882525}}}}


def test_read_keys_from_the_run_file():
    from gascf import deflator_cpih
    from gascf.figures import to_2024
    from tools import figures_keys
    from tools.figures_keys import s36_reads as K
    assert "s36_reads" in figures_keys.MODULES
    run = _run()
    v = K.values(run)
    assert v["margin_gross_extra_gw_2024"] == pytest.approx(202.4)
    assert v["ic_contracted_mw_2024"] == pytest.approx(500.0)
    assert v["ic_timeweighted_mw_2019"] == pytest.approx(500.0)
    assert v["ic_called_twh_2016_24"] == pytest.approx(9.0)
    assert v["ic_called_halfhours_2016_24"] == 18
    assert v["cm_nuclear_contracted_mw_2024"] == pytest.approx(4918.82525)
    assert v["rb_coal_kept_gw_2024"] == 8.0
    assert v["closures_kept_count"] == 2                 # distinct stations kept in any year: Drax, Rugeley
    assert v["closures_margin_test_pass_count"] == 1     # kept with reason 'mixed' (passed the margin test): Rugeley
    renewal = sum(deflator_cpih.to_real(40.0, y, 2025) for y in range(2002, 2025))
    assert v["renewal_allowance_2002_24_gbp_bn"] == pytest.approx(to_2024(renewal, run) / 1e3, rel=1e-12)
    assert v["nbp_qep_pre2009_effect_2002_24_gbp_bn"] == pytest.approx(to_2024(23.0, run) / 1e3, rel=1e-12)
    assert v["f1_effect_2002_24_gbp_bn"] == pytest.approx(to_2024(-46.0, run) / 1e3, rel=1e-12)
    nz5 = sum(deflator_cpih.to_real(3.0, y, 2025) for y in range(2002, 2025))
    assert v["cm_nuclear_effect_2002_24_gbp_bn"] == pytest.approx(to_2024(nz5, run) / 1e3, rel=1e-12)


def test_register_station_count_reads_the_named_register_file():
    import json
    from tools.figures_keys import s36_reads as K
    root = Path(__file__).resolve().parents[1]
    reg = json.loads((root / "tests/fixtures/s23b_fossil_closures_fixture.yaml").read_text())
    rows = reg if isinstance(reg, list) else reg["stations"]
    assert K.values(_run())["closures_register_stations_count"] == len({r["station"] for r in rows})


def test_balancing_keys_from_the_ranked_rows():
    """Low end = the stacked option (NAO 2005 baseline with the top workbook share, AGENTS.md standing decision 7),
    which must also be the lowest 2002-24 gap among the balancing options; its balancing step = central NZ6 - GO4
    less the option's GO4 move. Exception cost = central gap less that option's gap."""
    from gascf.figures import to_2024
    from gascf import deflator_cpih
    from tools.figures_keys import s36_reads as K
    run = _run()
    Y = [str(y) for y in B.YEARS]
    run["gap"] = {y: {"national_gbp_bn_real": 10.0} for y in Y}
    run["waterfall"] = {y: [{"lines": ["NZ6", "GO4"], "value_gbp_m_real": 500.0}] for y in Y}

    def opt(share, option, gap, dgo4):
        return {"settings": {"bal_share": share, "bal_option": option}, "gap_real_bn": {y: gap for y in Y},
                "lines_moved_gbp_m_nominal": {y: {"GO4": dgo4} for y in Y}}
    run["one_at_a_time"] = {"ranked": {"balancing (other sourced share / baseline)": [
        opt(0.42, "ibc", 10.5, -20.0), opt(0.70, "ibc", 9.9, 5.0), opt(0.42, "nao_2005", 9.8, 8.0),
        opt(0.70, "nao_2005", 9.5, 40.0)]}}
    v = K.values(run)
    low_step = sum(500.0 - deflator_cpih.to_real(40.0, int(y), 2025) for y in Y if int(y) <= 2024)
    assert v["balancing_low_end_2002_24_gbp_bn"] == pytest.approx(to_2024(low_step, run) / 1e3, rel=1e-12)
    assert v["balancing_exception_cost_2002_24_gbp_bn"] == pytest.approx(to_2024(23 * 0.5 * 1e3, run) / 1e3)
    assert v["balancing_exception_cost_2025p_gbp_bn"] == pytest.approx(to_2024(0.5 * 1e3, run) / 1e3)
    win = sum(500.0 - deflator_cpih.to_real(40.0, y, 2025) for y in range(2002, 2006))
    assert v["balancing_low_window_2002_05_gbp_m"] == pytest.approx(to_2024(win, run), rel=1e-12)
    # the stacked option must be the lowest-gap balancing option, or the key refuses
    run["one_at_a_time"]["ranked"]["balancing (other sourced share / baseline)"][1]["gap_real_bn"] = \
        {y: 9.0 for y in Y}
    with pytest.raises(ValueError, match="lowest"):
        K.values(run)
    # a run whose balancing row has no NAO option (a test fixture): None, which the release gate refuses
    run["one_at_a_time"]["ranked"]["balancing (other sourced share / baseline)"] = [opt(0.42, "ibc", 10.5, 0.0)]
    assert K.values(run)["balancing_low_end_2002_24_gbp_bn"] is None


def test_go5_line_carries_its_carried_part():
    """Ticket 29 note 3: renewal allowance = GO5 - carried_gbp_m needs carried_gbp_m on the GO5 line (builds the
    central case: heavy)."""
    b = B.build()
    for y in (2002, 2024):
        go5 = B.line(b[y], "GO5")
        assert "carried_gbp_m" in go5, y
        assert 0 < go5["carried_gbp_m"] <= go5["national_gbp_m_nominal"] + 1e-9, y
