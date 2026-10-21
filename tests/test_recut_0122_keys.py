"""Decision 0122 (Richard Lyon, 19 Oct 2026), card item 2: the modelled keys and tables the Reliable Britain draft
needs and the f82e9f9 cut lacked, read from the run file (tools/figures_keys/recut_0122.py), plus the release-detail
keys of item 7 and the figure register (annex A) written by tools.figures.

Expected values come from the run file's own fields, read here independently of the module, and from literals the
release records (sizing peak 18 Jan 2024 SP26: ticket 44's note, PROGRESS.md; prior release v4-s35 headline
£177.763bn, 2024 £: CHANGELOG and decision 0119)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import bills as B  # noqa: E402
from gascf import deflator_cpih  # noqa: E402
from tools import figures as F  # noqa: E402

S36 = ROOT / "out/v4/2026-10-20-s36.json"
S35 = ROOT / "out/v4/2026-10-14-s35.json"
Y02_24 = [str(y) for y in range(2002, 2025)]


@pytest.fixture(scope="module")
def run():
    r = json.loads(S36.read_text())
    r["meta"].setdefault("test_suite", {"commit": "a" * 40, "passed": 1, "failed": 0, "skipped": 0, "errors": 0,
                                        "started_utc": "2026-10-20T00:00:00+00:00"})
    return r


@pytest.fixture(scope="module")
def K():
    from tools.figures_keys import recut_0122
    return recut_0122


@pytest.fixture(scope="module")
def v(run, K):
    return K.values(run)


def _k24():
    c = deflator_cpih.cpih()
    return c[2024] / c[2025]


def test_module_is_registered_and_every_key_declared(K, run):
    from tools import figures_keys
    assert "recut_0122" in figures_keys.MODULES
    keys = F.generate(run, modules=[K])["keys"]
    assert set(keys) == set(K.DECLARED)
    F.assert_complete({"keys": keys})


def test_sizing_peak_halfhour_2024_reads_the_fleet(v):
    assert v["sizing_peak_halfhour_2024"] == "2024-01-18 SP26"


def test_release_version_and_commit_come_from_the_run_and_its_suite_record(v, run):
    assert v["release_version"] == "v4-s36" == run["meta"]["engine_version"]
    assert v["release_commit"] == run["meta"]["test_suite"]["commit"]


def test_release_commit_is_none_without_a_suite_record(K, run):
    r = dict(run, meta={k: x for k, x in run["meta"].items() if k != "test_suite"})
    assert K.values(r)["release_commit"] is None          # the release gate then refuses figures.json


def test_exceptions_register_lists_every_ranked_switch_with_an_option_below_central(v, run):
    from tools.figures_keys import range as R
    t = [r for r in R.table(run) if r["block"] == "ranked"]
    below = {}
    for r in t:
        if r["change_gbp_bn"] < -1e-9:
            below.setdefault(r["switch"], []).append(r)
    reg = v["table_exceptions_register"]
    assert [r["switch"] for r in reg] == sorted(below, key=lambda s: min(x["change_gbp_bn"] for x in below[s]))
    for r in reg:
        low = min(below[r["switch"]], key=lambda x: x["change_gbp_bn"])
        assert r["lowest_option"] == low["option"]
        assert r["change_gbp_bn"] == pytest.approx(low["change_gbp_bn"], abs=1e-12)
        assert r["change_gbp_bn"] < 0
    names = [r["switch"] for r in reg]
    assert any(n.startswith("balancing") for n in names)          # 0051's exception is on the list
    assert not any(n.startswith("grid renewal R") for n in names)  # low R raises the gap: central is the lower


def test_calibration_table_is_the_runs_early_years_block_and_the_residual_rows(v, run):
    t = v["table_calibration"]
    ce = run["tests"]["calibration_early"]
    assert [r["year"] for r in t["early_years"]] == [2002, 2003, 2004, "2002-04 pooled"]
    pooled = t["early_years"][-1]
    assert pooled["pct"] == ce["pooled"]["pct"] and round(pooled["pct"], 1) == 36.1     # 34.6 before decision 0133
    assert pooled["passed_pct"] is False and t["limit_pct"] == 30.0 and t["limit_gbp_hh"] == 25.0
    assert t["money"] == "2025 prices" and t["decision"] == "0111"
    cal = run["tests"]["calibration"]
    assert [r["year"] for r in t["residual_demand"]] == [r["year"] for r in cal["loosened"]]
    assert t["residual_demand"][0]["energy_err"] == cal["loosened"][0]["energy_err"]


def test_household_table_by_year_reads_gap_and_own_bill_in_2024_prices(v, run):
    t = v["table_household_by_year"]
    assert [r["year"] for r in t] == list(range(2002, 2026))
    k = _k24()
    hh = {r["year"]: r["households"] for r in run["years"]}
    for r in t:
        y = str(r["year"])
        assert r["cost_per_household_gbp"] == pytest.approx(run["gap"][y]["per_household_real"] * k, rel=1e-12)
        assert r["own_bill_per_household_gbp"] == pytest.approx(
            run["bills"][y]["netzero_on_household_bill_per_household"]["value"] * k, rel=1e-12)
        assert r["households_m"] == pytest.approx(hh[r["year"]] / 1e6, rel=1e-12)
        assert r["provisional"] is (r["year"] == 2025)
    assert round(t[-1]["cost_per_household_gbp"], 2) == 549.54          # 549.66 before decision 0133


def test_annex_b_has_every_bill_line_every_year_in_2024_prices(v, run):
    a = v["annex_b_annual_tables"]
    assert [x["year"] for x in a] == list(range(2002, 2026))
    k = _k24()
    for x in a:
        y = str(x["year"])
        b = run["bills"][y]
        ids = {(r["bill"], r["id"]) for r in x["rows"]}
        for bill, blk in (("net_zero_britain", "netzero"), ("reliable_britain", "gasonly"),
                          ("same_in_both", "same_in_both")):
            for line in b[blk]:
                assert (bill, line["id"]) in ids
        nz1 = [r for r in x["rows"] if r["id"] == "NZ1"][0]
        assert nz1["value"] == pytest.approx(b["netzero"][0]["national_gbp_m_real"] * k / 1e3, rel=1e-12)
        added_nz = sum(r["value"] for r in x["rows"] if r["bill"] in ("net_zero_britain", "same_in_both")
                       and r["added"] and "value" in r)
        assert added_nz == pytest.approx(b["totals"]["nz_real"] * k / 1e3, rel=1e-9)


def test_annex_c_engine_summary_is_the_runs_meta(v, run):
    c = v["annex_c_engine_summary"]
    m = run["meta"]
    assert c["engine_version"] == m["engine_version"] and c["central_settings"] == m["central_settings"]
    assert c["fallbacks"] == m["fallbacks"] and c["run_price_base"] == m["price_base"]
    assert c["input_checksums_count"] == len(m["input_checksums"])


def test_annex_e_bridges_to_the_prior_release(v):
    rows = {r["key"]: r for r in v["annex_e_bridge"]}
    h = rows["headline_2002_24_gbp_bn"]
    assert round(h["v4_s35"], 3) == 177.763 and round(h["v4_s36"], 3) == 161.207   # 161.275 before decision 0133
    assert h["change"] == pytest.approx(h["v4_s36"] - h["v4_s35"], abs=1e-12)
    assert round(rows["cost_per_household_2025p_gbp"]["v4_s35"], 2) == 576.79


def test_annex_e_is_none_on_a_run_without_release_step_effects(K):
    r = json.loads(S35.read_text())
    assert K.values(r)["annex_e_bridge"] is None


def test_cm_nuclear_suspended_effect_sums_the_block_2017_24_in_2024_prices(K, run):
    r = json.loads(json.dumps(run))
    for y in r["release_step_effects"]["years"]:
        r["release_step_effects"]["years"][y]["cm_nuclear_suspended_nz5_change_gbp_m_nominal"] = \
            1.0 if 2017 <= int(y) <= 2024 else 1e9
    got = K.values(r)["cm_nuclear_suspended_effect_2017_24_gbp_m"]
    want = sum(B.real(1.0, y) * _k24() for y in range(2017, 2025))
    assert got == pytest.approx(want, rel=1e-12)


def test_release_step_block_carries_the_suspended_agreement_change():
    from gascf import release_step_effects as R

    def _y(nz5):
        return {"fossil": [{"id": "GO4", "national_gbp_m_nominal": 1.0, "gas_feedback_gbp_m": 0.0},
                           {"id": "GO7", "national_gbp_m_nominal": 0.0, "domestic_share": 0.4}],
                "netzero": [{"id": "NZ5", "national_gbp_m_nominal": nz5}]}
    built = {y: _y(10.0) for y in B.YEARS}
    prior = {"meta": {"engine_version": "v4-s35"},
             "bills": {str(y): {"gasonly": [{"id": "GO4", "national_gbp_m_real": B.real(1.0, y)}]} for y in B.YEARS}}
    builds = {None: {y: _y(4.0) for y in B.YEARS}, "post_trade_tw": {y: _y(9.0) for y in B.YEARS}}
    blk = R.block(built, prior=prior, build=lambda s: builds[s.nuclear_cm_column])
    for y in B.YEARS:
        row = blk["years"][str(y)]
        assert row["cm_nuclear_nz5_change_gbp_m_nominal"] == pytest.approx(6.0)
        assert row["cm_nuclear_suspended_nz5_change_gbp_m_nominal"] == pytest.approx(1.0)
    assert blk["suspended_off_settings"] == {"nuclear_cm_column": "post_trade_tw"}


def test_gb_household_share_is_the_subnational_domestic_share_and_context_only(v, K):
    """Needs file 4.5: the engine's household share (36.5%) is UK (DUKES 5.2/5.5.D sales). A GB figure exists on another
    basis: DESNZ sub-national electricity consumption 2024, domestic meters / all meters, GB incl. unallocated
    (97,503.6 / 249,247.7 GWh). Context only: the engine's own-bill line keeps the UK basis unless Richard rules."""
    assert round(v["household_share_gb_2024_pct"], 1) == 39.1
    m = K.DECLARED["household_share_gb_2024_pct"]
    assert m["context_only"] is True and m["headline"] is False and "UK" in m["note"]


def test_figure_register_lists_every_other_key_with_its_label(run):
    from tools.figures_keys import grid
    out = F.generate(run, modules=[grid])
    reg = F.figure_register(out)
    assert [r["key"] for r in reg] == list(out["keys"])
    assert all(r["label"] == out["keys"][r["key"]]["meta"]["label"] for r in reg)
    assert all(r["units"] == out["keys"][r["key"]]["meta"]["units"] for r in reg)
    assert not any(x is None for r in reg for x in r.values())
