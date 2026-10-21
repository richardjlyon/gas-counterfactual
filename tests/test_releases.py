"""Release registry guard (Richard, 14 Oct 2026): every listed release's files exist and match their
sha256; versions are unique; each clock export's CM block equals what its run file says; and the
latest release's baselines still equal what the engine code computes (so a change to the
baseline code without a new release fails here, rather than drifting silently)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gascf import clock_export as ce
from gascf import release as rel

ROOT = Path(__file__).parents[1]
REG = rel.load(ROOT / "releases.yaml")
RELEASES = REG["releases"]
IDS = [r["version"] for r in RELEASES]


def test_registry_has_releases_and_unique_versions():
    assert RELEASES, "releases.yaml lists no release"
    assert len(IDS) == len(set(IDS)), f"duplicate versions: {IDS}"


@pytest.mark.parametrize("r", RELEASES, ids=IDS)
def test_release_files_exist_and_sha256_match(r):
    run, exp = ROOT / r["run_file"], ROOT / r["clock_export_file"]
    assert run.exists(), r["run_file"]
    assert exp.exists(), r["clock_export_file"]
    assert ce.sha256_file(run) == r["run_sha256"], f"{r['run_file']} changed after release {r['version']}"
    assert ce.sha256_file(exp) == r["clock_export_sha256"], \
        f"{r['clock_export_file']} changed after release {r['version']}"


@pytest.mark.parametrize("r", RELEASES, ids=IDS)
def test_clock_export_meta_matches_registry(r):
    e = json.loads((ROOT / r["clock_export_file"]).read_text())
    run = json.loads((ROOT / r["run_file"]).read_text())
    assert e["meta"]["engine_version"] == r["version"] == run["meta"]["engine_version"]
    assert e["meta"]["run_sha256"] == r["run_sha256"]
    assert e["meta"]["run_file"] == r["run_file"]
    assert e["meta"]["commit"] == r["commit"]
    assert e["meta"]["schema"] in ce.KNOWN_SCHEMAS


@pytest.mark.parametrize("r", RELEASES, ids=IDS)
def test_clock_export_cm_block_equals_run_file(r):
    e = json.loads((ROOT / r["clock_export_file"]).read_text())
    run = json.loads((ROOT / r["run_file"]).read_text())
    assert e["capacity_market"] == ce.capacity_market(run)
    # and to the penny against the raw blocks, independently of the rounding helper
    for y, row in e["capacity_market"]["years"].items():
        c, k = run["clock_cm_correction"][y], run["capacity_market"][y]
        assert abs(row["cm_paid_gbp"] - c["clock_cm_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["netzero_gbp"] - c["nz5_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["netzero_low_gbp"] - c["nz5_low_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["netzero_high_gbp"] - c["nz5_high_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["own_backup_gbp"] - k["reliable_britain_cm_gbp_m"] * 1e6) <= 0.005, y
        assert 0 <= row["netzero_low_gbp"] <= row["netzero_gbp"] <= row["netzero_high_gbp"] <= row["cm_paid_gbp"]


def test_latest_release_baselines_equal_engine_code():
    """Drift detector: if grid/balancing baseline code changes, cut a new release."""
    e = json.loads((ROOT / RELEASES[-1]["clock_export_file"]).read_text())
    now = ce.baselines()
    for k in ("tnuos", "bsuos"):
        assert e["baselines"][k]["value_gbp_nominal"] == now[k]["value_gbp_nominal"], \
            f"{k} baseline moved since release {RELEASES[-1]['version']}: cut a new release"
    assert e["baselines"]["tnuos"]["period"] == e["baselines"]["bsuos"]["period"] == "2002-2005"


def test_latest_release_series_equal_engine_code():
    """Drift detector for the per-year grid and balancing series (clock-export/2): if GO4/GO5 code
    or the central balancing rule changes, cut a new release."""
    e = json.loads((ROOT / RELEASES[-1]["clock_export_file"]).read_text())
    assert e["meta"]["schema"] == ce.SCHEMA
    assert e["grid"] == json.loads(json.dumps(ce.grid_series())), "grid series moved: cut a new release"
    run = json.loads((ROOT / RELEASES[-1]["run_file"]).read_text())
    # s36 R-2: expected red from F1 in code until the s36 release row exists ("cut a new release")
    assert e["balancing"] == json.loads(json.dumps(ce.balancing_series(ce.uplift_from_run(run)))), \
        "balancing series moved: cut a new release"
    assert e["carry_forward"] == ce.carry_forward()


def test_clock_series_shape_and_method():
    """Richard, 14 Oct 2026: generators' share included; central balancing = ibc + FY2018/19 share,
    split into energy and services parts that add up; grid = carried + renewal allowance; every
    engine year present; the carry-forward rule stated."""
    from gascf import balancing, bills as B, grid
    run = json.loads((ROOT / RELEASES[-1]["run_file"]).read_text())      # s36 R-2: call site only
    g, b, cf = ce.grid_series(), ce.balancing_series(ce.uplift_from_run(run)), ce.carry_forward()
    assert g["gen_share"] == b["gen_share"] == "included"
    assert b["central_option"] == "ibc|first" and b["low_option"] == "nao_2005|max"
    assert sorted(map(int, g["years"])) == sorted(map(int, b["years"])) == list(B.YEARS)
    assert cf["from"] == max(B.YEARS) and cf["index"] == "CPIH" and "CPIH" in cf["rule"]
    s = balancing.energy_share_2018()
    for y, r in b["years"].items():
        assert r["energy_share"] == round(s, 6)
        assert r["energy_part_gbp"] + r["services_part_gbp"] == pytest.approx(r["central_gbp"], abs=0.02)
        assert r["central_gbp"] > 0
    for y, r in g["years"].items():
        assert r["carried_by_index_gbp"] + r["renewal_allowance_gbp"] == pytest.approx(r["central_gbp"], abs=0.02)
        assert r["low_gbp"] >= r["central_gbp"] >= r["high_gbp"] == pytest.approx(r["carried_by_index_gbp"], abs=0.01)
    # the 2002-05 mean of the central balancing series is B0 itself (nominal, both parts)
    b0 = ce.baselines()["bsuos"]["value_gbp_nominal"]
    m = sum(b["years"][str(y)]["central_gbp"] for y in range(2002, 2006)) / 4
    assert m == pytest.approx(b0, rel=0.03)


def test_release_refuses_an_existing_version(tmp_path):
    with pytest.raises(SystemExit, match="already in releases.yaml"):
        rel.release(RELEASES[0]["version"], ROOT / RELEASES[0]["run_file"], "dup")
