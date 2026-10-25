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


# Recorded known faults in frozen releases (decision 0177, card [internal ticket]). A released file never changes
# (0028, 0045), so a fault found after the cut is recorded here, dated, with the release that fixes it, and the
# test checks the frozen file holds EXACTLY the recorded wrong values: any other difference, or a change to the
# recorded ones, still fails. Nothing is skipped and nothing is hidden: the entry is the disclosure.
KNOWN_FAULTS: dict[str, dict] = {
    "v4-s39": {
        "decision": "0177",
        "recorded": "2026-10-23",
        "card": "[internal ticket]",
        "fixed_in": "v4-s40",
        "what": "Clock export cm_paid_gbp 2017-25 holds the Clock's displayed CM line (since Clock 35132e73 only the "
                "net-zero part), not CM paid (the LCCC levy; register CM_PAID). NZ5 low, NZ5, NZ5 high, the run "
                "file and figures.json are right; only this export field is wrong. Analyst note cm-sources.md "
                "([internal ticket]). Fixed in src/gascf/clock_export.py at c69d8d5.",
        "cm_paid_gbp": {"wrong_values": {   # £ cash, as frozen in out/clock/v4-s39.json (sha256 dffbfb18...480c5e)
            "2017": 31270034.88, "2018": 45467658.97, "2019": 126825663.01, "2020": 177635697.11,
            "2021": 200557514.36, "2022": 145618431.36, "2023": 236669665.63, "2024": 343819210.62,
            "2025": 396333094.27,
        }},
    },
}


def _cm_fault_years(e: dict, run: dict) -> dict[str, float]:
    """Years where the export's cm_paid_gbp is not the run file's CM paid (LCCC levy), with the export's value."""
    return {y: row["cm_paid_gbp"] for y, row in e["capacity_market"]["years"].items()
            if abs(row["cm_paid_gbp"] - run["capacity_market"][y]["cm_paid_gbp_m"] * 1e6) > 0.005}


@pytest.mark.parametrize("r", RELEASES, ids=IDS)
def test_clock_export_cm_block_equals_run_file(r):
    e = json.loads((ROOT / r["clock_export_file"]).read_text())
    run = json.loads((ROOT / r["run_file"]).read_text())
    fault = KNOWN_FAULTS.get(r["version"], {}).get("cm_paid_gbp")
    want = ce.capacity_market(run)
    if fault:
        # the recorded fault, and only it: the wrong values are the Clock's displayed (net-zero) CM line
        assert _cm_fault_years(e, run) == fault["wrong_values"], f"{r['version']}: fault differs from its record"
        for y, v in fault["wrong_values"].items():
            assert abs(v - run["clock_cm_correction"][y]["clock_cm_gbp_m"] * 1e6) <= 0.005, y
            want["years"][y]["cm_paid_gbp"] = v
    assert e["capacity_market"] == want
    # and to the penny against the raw blocks, independently of the rounding helper
    for y, row in e["capacity_market"]["years"].items():
        c, k = run["clock_cm_correction"][y], run["capacity_market"][y]
        faulty = bool(fault) and y in fault["wrong_values"]
        # CM paid = the levy paid (LCCC; register CM_PAID), the run file's capacity_market line (0168, 0177)
        if not faulty:
            assert abs(row["cm_paid_gbp"] - k["cm_paid_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["netzero_gbp"] - c["nz5_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["netzero_low_gbp"] - c["nz5_low_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["netzero_high_gbp"] - c["nz5_high_gbp_m"] * 1e6) <= 0.005, y
        assert abs(row["own_backup_gbp"] - k["reliable_britain_cm_gbp_m"] * 1e6) <= 0.005, y
        assert 0 <= row["netzero_low_gbp"] <= row["netzero_gbp"] <= row["netzero_high_gbp"]
        assert row["netzero_high_gbp"] <= k["cm_paid_gbp_m"] * 1e6 + 0.005, y
        if faulty:
            assert row["netzero_high_gbp"] > row["cm_paid_gbp"], (y, "recorded fault no longer breaks the order")
        else:
            assert row["netzero_high_gbp"] <= row["cm_paid_gbp"], y


def test_known_faults_are_recorded_in_full():
    """Every known-fault entry names a listed release, its decision, the date recorded, the card, and a release
    that fixes it which is listed after it (or is the engine version being built)."""
    from gascf import export_v4 as X
    for v, f in KNOWN_FAULTS.items():
        assert v in IDS, v
        assert {"decision", "recorded", "card", "fixed_in", "what"} <= set(f), (v, sorted(f))
        assert f["fixed_in"] not in KNOWN_FAULTS
        assert f["fixed_in"] == X.ENGINE_VERSION or IDS.index(f["fixed_in"]) > IDS.index(v), (v, f["fixed_in"])


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
