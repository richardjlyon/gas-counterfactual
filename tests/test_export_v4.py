"""s21b: the v4 export carries the spec §13 fields and agrees with the engine."""
import json
import sys
from pathlib import Path

import pytest

from gascf import bills as B
from gascf import export_v4 as X
from gascf import waterfall as W

SPEC13 = ("meta", "years", "bills", "gap", "waterfall", "fleet", "firm_capacity", "carbon_crosscheck",
          "bridge", "clock_cm_correction", "sensitivities", "answers", "provenance", "tests")
LINE = ("id", "label", "national_gbp_m_nominal", "national_gbp_m_real", "per_household_real", "basis",
        "geo", "source_ids", "years_note")


@pytest.fixture(scope="module")
def built():
    return B.build()


def test_bills_block_has_spec_fields(built):
    out = X._bills(built, W.waterfall())
    for y in ("2002", "2024", "2025"):
        assert set(out[y]) >= {"netzero", "gasonly", "netzero_on_household_bill_per_household"}
        for l in out[y]["netzero"] + out[y]["gasonly"]:
            assert set(LINE) <= set(l)
        assert [l["id"] for l in out[y]["gasonly"]] == list(B.GO_IDS)


def test_fleet_block_has_spec_fields(built):
    f = X._fleet(built)["2025"]
    for k in ("ccgt_gw", "ocgt_gw", "spare_gw", "energy_twh", "fixed_gbp_m", "fuel_gbp_m", "vom_gbp_m",
              "transport_gbp_m", "gbp_per_mwh", "cost_edition", "gas_burn_twh"):
        assert k in f
    lfl = f.get("market_gbp_m", 0.0) + f.get("moe_gbp_m", 0.0) + f.get("gas_feedback_gbp_m", 0.0)  # like for like only
    assert lfl + f["fixed_gbp_m"] + f["fuel_gbp_m"] + f["vom_gbp_m"] + f["transport_gbp_m"] == pytest.approx(
        B.val(built[2025], "GO1"))


def test_years_block(built):
    ys = X._years(built)
    assert [r["year"] for r in ys] == list(B.YEARS)
    r25 = ys[-1]
    assert r25["provisional"] and r25["households"] == 28_253_000
    assert r25["volume_twh"] == pytest.approx(built[2025]["volume"]["v_twh"])


def test_all_new_comparison_block(built):
    """s22: the export carries the old all-new gap beside the like-for-like one."""
    out = X._all_new(built)
    a = B.build(B.ALL_NEW)
    assert out["2025"]["gap_per_household_real"] == pytest.approx(a[2025]["totals"]["gap_per_hh_real"])
    assert out["2002"]["like_for_like_minus_all_new_per_household_real"] == pytest.approx(
        built[2002]["totals"]["gap_per_hh_real"] - a[2002]["totals"]["gap_per_hh_real"])


def test_payload_has_every_spec13_block():
    """A fresh payload (not the stored file) carries every §13 block. Slow on its own (it
    runs every switch); cheap after test_bills in the same session (results are cached)."""
    d = X.build_payload("test")
    assert set(SPEC13) <= set(d)
    assert set(d["bridge"]) == {str(y) for y in B.YEARS}


def _fresh_gap_2025(register: Path) -> float:
    """Central 2025 gap from a fresh build against `register`, in a separate interpreter: the
    rest of this session runs on the conftest fixture register and the engine caches by it.
    The interpreter is shared with the other real-register checks (`tests/real_register.py`)."""
    from real_register import real_register
    return float(real_register(register)["gap_2025"])


def test_written_file_matches_engine():
    """The stored out/v4 file (written by `python -m gascf.export_v4`) carries every §13 block
    and the same central gap as a fresh build. Like with like: the export is built from the
    real register (`reference/fossil_closures.yaml`), so the fresh build here uses the register
    the file records, not the conftest fixture."""
    p = [q for q in sorted(Path(X.OUT).glob("*.json"))
         if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    if not p:
        pytest.skip(f"no out/v4 file written by engine {X.ENGINE_VERSION} yet")
    d = json.loads(p[-1].read_text())
    assert set(SPEC13) <= set(d)
    assert d["meta"]["price_base"] == 2025 and d["meta"]["deflator"] == "ONS CPIH L522"
    reg = d["meta"].get("closures_register") or {"path": "reference/fossil_closures.yaml"}
    path = X.ROOT / reg["path"]
    if "sha256" in reg and X._sha(path) != reg["sha256"]:
        pytest.fail(f"{reg['path']} changed since the export was written: re-run the export")
    assert d["gap"]["2025"]["per_household_real"] == pytest.approx(_fresh_gap_2025(path), abs=0.01)
    assert d["tests"]["waterfall_identity_max_abs_gbp_m"] < 0.01
    assert d["tests"]["bridge_identity_max_abs_gbp_m"] < 0.01


def test_s27c_answers_and_fallbacks():
    """s27c: gas break-even with feedback on, gas-marginal share filled, meta.fallbacks lists
    every fallback that fired (with size), the s27b ones included."""
    d = X.build_payload("test")
    be = d["answers"]["gas_break_even"]["2025"]
    assert be["price_rise_frac"] is not None and be["price_rise_frac"] > be["price_rise_frac_central"]
    gms = d["answers"]["gas_marginal_share"]
    assert all(0 < gms[str(y)]["fossil_britain_load"] <= 1 for y in B.YEARS)
    names = {f["name"] for f in d["meta"]["fallbacks"]}
    # s36 ticket 21: "ets-power-receipts-2025" retired (2025 is the 0079 provisional estimate, not a carry)
    assert "ets-power-receipts-2025" not in names
    assert {"cpf-receipts-2013",
            "bsuos-gen-share-interpolated", "coal_efficiency_mean_2015_2023"} <= names
    assert "fit-sy1-5-levelisation-ratio" not in names      # C-008: FIT years 1-5 are Ofgem's published figures
    assert all(f["unit"] and f["size"] == f["size"] for f in d["meta"]["fallbacks"])


def test_years_row_exports_nuclear_ic_ps_net_twh_at_full_precision(built):
    """Ticket 46 (EIC editorial ruling 17 Oct 2026, writer item 6): each years row carries the nuclear + imports +
    pumped-storage output, net of exports and pumping (engine volume.kept_twh), at full precision. 2024 against the
    v4-s35 residual file 70.9842024 TWh (re-pin from the build only if s36 moves it, never loosened)."""
    rows = X._years(built)
    for y, row in zip(B.YEARS, rows):
        assert "nuclear_ic_ps_net_twh" in row
        assert isinstance(row["nuclear_ic_ps_net_twh"], float)
        assert row["nuclear_ic_ps_net_twh"] == built[y]["volume"]["kept_twh"]   # ==, no tolerance
        assert not any("kept" in k for k in row)                                # no "kept" in field names
    r24 = next(r for r in rows if r["year"] == 2024)
    assert r24["nuclear_ic_ps_net_twh"] == pytest.approx(70.9842024, abs=1e-6)  # v4-s35 residual file
    assert r24["nuclear_ic_ps_net_twh"] != round(r24["nuclear_ic_ps_net_twh"], 1)   # full precision, not 71.0
    payload = json.loads(json.dumps(rows))                                      # survives a JSON round-trip
    assert next(r for r in payload if r["year"] == 2024)["nuclear_ic_ps_net_twh"] == r24["nuclear_ic_ps_net_twh"]


def test_pricing_block_exports_the_qep_ratio_unrounded(monkeypatch):
    """Ticket 47: the run-file block pricing.qep_dayahead_ratio carries the 16 yearly ratios, the mean, the min and
    max (value and year) and the inputs, unrounded, registered through BLOCK_MODULES (no line in build_payload)."""
    import importlib
    import sys
    from gascf import prices as P
    monkeypatch.setattr(X.B, "build", lambda *a, **k: {"built": True})
    monkeypatch.setattr(X.B, "ranges", lambda *a, **k: {})
    monkeypatch.setattr(X.W, "waterfall", lambda *a, **k: {y: {} for y in X.B.YEARS})
    monkeypatch.setattr(X.R, "bridge", lambda *a, **k: {y: {} for y in X.B.YEARS})
    monkeypatch.setattr(X.R, "clock_cm_correction", lambda *a, **k: {})
    for name in ("_meta", "_years", "_bills", "_gap", "_fleet", "_all_new", "_firm", "_carbon_check", "_cm",
                 "_sens", "_methods_page", "_answers", "provenance", "_tests"):
        monkeypatch.setattr(X, name, lambda *a, **k: {})
    monkeypatch.setattr(X, "_BLOCKS", {})
    monkeypatch.setattr(X, "BLOCK_MODULES", ["gascf.pricing_block"])
    sys.modules.pop("gascf.pricing_block", None)                  # re-run the module so it registers in the fresh _BLOCKS
    p = X.build_payload("2026-10-18")
    blk = p["pricing"]["qep_dayahead_ratio"]
    assert len(blk["by_year"]) == 16
    assert set(blk) >= {"by_year", "mean_2010_25", "min_2010_25", "max_2010_25", "inputs", "units"}
    assert blk["min_2010_25"]["year"] == 2021 and blk["max_2010_25"]["year"] == 2020
    assert blk["units"] == "ratio, £/MWh over £/MWh (GCV)"
    eng = P.qep_dayahead_ratio_2010_25()
    assert blk["mean_2010_25"] == eng["mean"]                     # ==, unrounded
    assert blk["mean_2010_25"] != round(blk["mean_2010_25"], 4)
    rt = json.loads(json.dumps(p))["pricing"]["qep_dayahead_ratio"]
    assert rt["mean_2010_25"] == blk["mean_2010_25"]             # survives a JSON round-trip
    assert all(set(i) == {"path", "sha256"} for i in blk["inputs"])


def _stub_build_payload(monkeypatch, block_modules):
    import sys
    monkeypatch.setattr(X.B, "build", lambda *a, **k: {"built": True})
    monkeypatch.setattr(X.B, "ranges", lambda *a, **k: {})
    monkeypatch.setattr(X.W, "waterfall", lambda *a, **k: {y: {} for y in X.B.YEARS})
    monkeypatch.setattr(X.R, "bridge", lambda *a, **k: {y: {} for y in X.B.YEARS})
    monkeypatch.setattr(X.R, "clock_cm_correction", lambda *a, **k: {})
    for name in ("_meta", "_years", "_bills", "_gap", "_fleet", "_all_new", "_firm", "_carbon_check", "_cm",
                 "_sens", "_methods_page", "_answers", "provenance", "_tests"):
        monkeypatch.setattr(X, name, lambda *a, **k: {})
    monkeypatch.setattr(X, "_BLOCKS", {})
    monkeypatch.setattr(X, "BLOCK_MODULES", block_modules)
    for m in block_modules:
        sys.modules.pop(m, None)
    return X.build_payload("2026-10-18")


def test_balancing_factors_block_exports_the_grossup_unrounded(monkeypatch):
    from gascf import balancing as Bal
    p = _stub_build_payload(monkeypatch, ["gascf.balancing_factors_block"])
    blk = p["balancing_factors"]["bsuos_basis_grossup"]
    assert set(blk) >= {"value", "inputs", "fy", "reference_file"}
    assert blk["fy"] == "2007/08"
    assert blk["value"] == Bal.bsuos_basis_grossup_factor()             # ==, unrounded
    assert blk["value"] != round(blk["value"], 3)
    ids = {i["id"]: i["value"] for i in blk["inputs"]}
    assert ids == {"tar_2008_09_t22_balancing_internal_2007_08": 112.92,
                   "tar_2008_09_t22_balancing_external_2007_08": 569.85}
    assert set(blk["reference_file"]) == {"path", "sha256"} and len(blk["reference_file"]["sha256"]) == 64
    rt = json.loads(json.dumps(p))["balancing_factors"]["bsuos_basis_grossup"]
    assert rt["value"] == blk["value"]


def test_balancing_factors_block_exports_gb_over_ew_unrounded(monkeypatch):
    from gascf import balancing as Bal
    p = _stub_build_payload(monkeypatch, ["gascf.balancing_factors_block"])
    blk = p["balancing_factors"]["gb_over_ew"]
    assert set(blk) >= {"value", "by_year", "inputs"}
    assert blk["value"] == Bal.gb_over_ew() and blk["value"] != round(blk["value"], 4)
    assert len(blk["by_year"]) == 4 and len(blk["inputs"]) == 4
    rt = json.loads(json.dumps(p))["balancing_factors"]["gb_over_ew"]
    assert rt["value"] == blk["value"]


def test_cli_runs_the_imported_module_so_run_file_blocks_register(monkeypatch, tmp_path):
    """Found at the s36 release run (19 Oct 2026): `python -m gascf.export_v4` ran build_payload in __main__, whose
    _BLOCKS stays empty because the block modules register into gascf.export_v4, so the run file had no s36 block
    (one_at_a_time, carbon, pos_cm ...). The CLI must call the imported module's write."""
    import runpy
    import sys

    from gascf import bills as B
    called = {}

    def fake_write(d=None, s=""):
        called["args"] = (d, s)
        return tmp_path / "x.json"

    def no_build(*a, **k):
        raise RuntimeError("CLI built in __main__")

    monkeypatch.setattr(X, "write", fake_write)
    monkeypatch.setattr(B, "build", no_build)
    monkeypatch.setattr(sys, "argv", ["export_v4", "2026-10-19", "-s36"])
    runpy.run_module("gascf.export_v4", run_name="__main__")
    assert called["args"] == ("2026-10-19", "-s36")
