"""Decision 0177 / 0168 (card [internal ticket]): CM paid is one number from one source.

CM paid is the whole levy paid to capacity providers: LCCC "Capacity Obligation by Auction",
Capacity_Payment_GBP, summed by calendar year of the delivery month. That is the engine's own
capacity_market[y].cm_paid_gbp_m and the shared cost register's CM_PAID line. The Clock export's
cm_paid_gbp must be that number, not the Clock's displayed CM line (which since Clock 35132e73, 13 Oct
2026, is only the net-zero part; analyst note cm-sources.md, [internal ticket]).

Checked, every modelled year 2017-25, in the engine's Clock export (built from the run file now) and in
the run file itself:
- 0 <= NZ5 low <= NZ5 <= NZ5 high <= CM paid;
- CM paid equals the run file's capacity_market block, to the penny;
- CM paid equals the LCCC calendar-year totals read independently by the analyst (cm-sources.md
  Table 1a, LCCC CSV re-read 23 Oct 2026 10:35 UTC), to the printed £0.001m.

The run file is the out/v4 file written by this engine version. There is no skip: if it is missing, fail.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gascf import clock_export as ce
from gascf import export_v4 as X

ROOT = Path(__file__).resolve().parents[1]

# £m cash, LCCC Capacity_Payment_GBP by calendar year of delivery month (cm-sources.md Table 1a, [internal ticket])
LCCC_PAID_GBP_M = {
    2017: 117.562, 2018: 549.449, 2019: 962.992, 2020: 1005.762, 2021: 1061.709,
    2022: 646.942, 2023: 898.210, 2024: 1256.981, 2025: 1431.463,
}
YEARS = sorted(LCCC_PAID_GBP_M)


def _run_path() -> Path:
    hits = [q for q in sorted((ROOT / "out/v4").glob("*.json"))
            if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    assert hits, f"no out/v4 file written by engine {X.ENGINE_VERSION}: export before testing"
    return hits[-1]


@pytest.fixture(scope="module")
def run():
    return json.loads(_run_path().read_text())


@pytest.fixture(scope="module")
def export_cm(run):
    return ce.capacity_market(run)["years"]


def test_every_year_2017_25_is_in_the_export(export_cm):
    assert all(str(y) in export_cm for y in YEARS), sorted(export_cm)


@pytest.mark.parametrize("y", YEARS)
def test_export_order_nz5_low_nz5_high_cm_paid(export_cm, y):
    r = export_cm[str(y)]
    assert 0 <= r["netzero_low_gbp"] <= r["netzero_gbp"] <= r["netzero_high_gbp"] <= r["cm_paid_gbp"], (y, r)


@pytest.mark.parametrize("y", YEARS)
def test_run_file_order_nz5_low_nz5_high_cm_paid(run, y):
    c, k = run["clock_cm_correction"][str(y)], run["capacity_market"][str(y)]
    assert 0 <= c["nz5_low_gbp_m"] <= c["nz5_gbp_m"] <= c["nz5_high_gbp_m"] <= k["cm_paid_gbp_m"] + 5e-9, (y, c, k)


@pytest.mark.parametrize("y", YEARS)
def test_export_cm_paid_is_the_run_files_cm_paid(run, export_cm, y):
    assert abs(export_cm[str(y)]["cm_paid_gbp"] - run["capacity_market"][str(y)]["cm_paid_gbp_m"] * 1e6) <= 0.005, y


@pytest.mark.parametrize("y", YEARS)
def test_export_cm_paid_is_lccc(export_cm, y):
    assert export_cm[str(y)]["cm_paid_gbp"] / 1e6 == pytest.approx(LCCC_PAID_GBP_M[y], abs=0.0005), y
