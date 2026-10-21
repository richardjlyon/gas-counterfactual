"""The site data file (export.py). Every expected figure comes from an engine call, never typed,
so these tests still hold after the engine's numbers change."""
import json
import re
from pathlib import Path

import pytest

from gascf import export as ex
from gascf import goods, receipt_actual, sensitivity, staircase, today
from gascf.deflator import rebase


@pytest.fixture(scope="module")
def data():
    return ex.build()


@pytest.fixture(scope="module")
def stairs():
    k = ex.latest_period()
    return {f: staircase.staircase(k, f, ex.KWH, ex.ORDER) for f in ex.FLEETS}


def monies(o, path=""):
    """Every Money object ({gbp, fixed_gbp, gbp_per_kwh}) in the file, with its path."""
    if isinstance(o, dict):
        if set(o) == {"gbp", "fixed_gbp", "gbp_per_kwh"}:
            yield path, o
        else:
            for k, v in o.items():
                yield from monies(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from monies(v, f"{path}[{i}]")


# ---------------------------------------------------------------- the headline

def test_headline_is_actual_minus_step_1_for_every_gas_power_choice(data, stairs):
    """Schema 0.4 (Richard, 11 Oct 2026): one headline per gas-power choice A, B, D; default A."""
    h = data["headline"]
    assert set(ex.FLEETS) == {"A", "B", "D"} and h["default_fleet"] == ex.DEFAULT_FLEET == "D"
    gaps = {}
    for f in ex.FLEETS:
        s = stairs[f]
        assert h["with_net_zero_gbp"]["gbp"] == pytest.approx(s.actual_total, abs=1e-9)
        assert h["without_net_zero_gbp"][f]["gbp"] == pytest.approx(s.steps["1"], abs=1e-9)
        gaps[f] = s.actual_total - s.steps["1"]
        assert h["net_zero_costs_gbp"][f]["gbp"] == pytest.approx(gaps[f], abs=1e-9)
        assert data["p2_receipt"]["fleets"][f]["totals"]["gap"]["gbp"] == pytest.approx(gaps[f], abs=1e-9)
        # carbon is its own block; the figure without carbon is gap minus step 2
        assert h["carbon_gbp"][f]["gbp"] == pytest.approx(s.steps["2"], abs=1e-9)
        assert h["net_zero_costs_without_carbon_gbp"][f]["gbp"] == pytest.approx(gaps[f] - s.steps["2"], abs=1e-9)
    r = h["range_across_fleets"]
    assert r["low"]["gbp"] == pytest.approx(min(gaps.values())) and r["high"]["gbp"] == pytest.approx(max(gaps.values()))
    assert h["default"]["gap"]["gbp"] == pytest.approx(gaps["D"], abs=1e-9)
    assert h["desnz_beside"]["gap"]["gbp"] == pytest.approx(gaps["D"], abs=1e-9)
    assert "no carbon price" in h["no_carbon_statement"]


def test_not_net_zero_lines_equal_in_both_columns(data, stairs):
    """Decision 3: WHD, AAHEDC and the EII levy are held equal, shown as their own block."""
    for f in ex.FLEETS:
        r = data["p2_receipt"]["fleets"][f]
        sec = next(x for x in r["sections"] if x["id"] == "not_net_zero")
        assert [ln["id"] for ln in sec["lines"]] == list(staircase.NOT_NET_ZERO)
        for ln in sec["lines"]:
            assert ln["actual"] == ln["all_gas"] and ln["gap"]["gbp"] == 0 and ln["not_net_zero"]
        blk = r["not_net_zero_block"]
        assert blk["money"]["gbp"] == pytest.approx(sum(stairs[f].line(k).actual for k in staircase.NOT_NET_ZERO))
    lev = next(x for x in data["p2_receipt"]["fleets"]["A"]["sections"] if x["id"] == "levies")
    assert [ln["id"] for ln in lev["lines"]] == list(staircase.STEP3) == ["eco", "sizewell_c"]


def test_carbon_block(data):
    for f in ex.FLEETS:
        cb = data["p2_receipt"]["fleets"][f]["carbon_block"]
        assert cb["label"] == ex.CARBON_LABEL
        assert cb["money"] == data["p2_receipt"]["fleets"][f]["steps"][1]["money"]


def test_at_least_follows_spec_7_2(data):
    """B1: X = min over every switch (grid and sensitivity rows) of 4a + 4b + min(0, 4c)."""
    sw, h = data["p6_switches"], data["headline"]
    xs = [v["at_least_test_gbp"] for v in sw["variants"].values()]
    xs += [r["at_least_test_gbp"] for r in sw["sensitivity"]["rows"]]
    assert sw["at_least"]["x_gbp"] == pytest.approx(min(xs), abs=1e-12)
    assert sw["at_least"]["passed"] == (min(xs) > 0)
    assert h["at_least"] == sw["at_least"]
    for v in sw["variants"].values():
        st = {x["id"]: x["money"]["gbp"] for x in v["steps"]}
        assert v["at_least_test_gbp"] == pytest.approx(st["4a"] + st["4b"] + min(0.0, st["4c"]), abs=1e-12)
    gaps = [v["gap"]["gbp"] for v in sw["variants"].values()] + [r["gap"]["gbp"] for r in sw["sensitivity"]["rows"]]
    assert h["range_across_switches"]["low"] == min(gaps) and h["range_across_switches"]["high"] == max(gaps)


def test_feedback_threshold_zeroes_the_gap(data):
    """S1: at the exported rise in the gas price (all-gas side only) the gap is about nil."""
    k = ex.latest_period()
    fb = data["methods"]["feedback"]["A"]
    assert fb["whole_gap"] is not None and fb["whole_gap"] > 0
    s = staircase.staircase(k, "A", ex.KWH, ex.ORDER, gas_mult=1 + fb["whole_gap"])
    assert abs(s.actual_total - s.steps["1"]) < 0.01
    s = staircase.staircase(k, "A", ex.KWH, ex.ORDER, gas_mult=1 + fb["without_carbon"])
    assert abs(s.actual_total - s.steps["1"] - s.steps["2"]) < 0.01


def test_gap_is_the_whole_staircase_not_the_renewables_subtotal(data, stairs):
    """Carbon (step 2) and other policy (step 3) are inside the gap; 4a+4b+4c alone is not it."""
    for f in ex.FLEETS:
        s = stairs[f]
        gap = data["p2_receipt"]["fleets"][f]["totals"]["gap"]["gbp"]
        assert gap == pytest.approx(sum(s.steps[k] for k in ("2", "3", "4a", "4b", "4c")), abs=0.01)
        ren = s.steps["4a"] + s.steps["4b"] + s.steps["4c"]
        assert abs(gap - ren) > 1, "headline must not be the 4a+4b+4c subtotal"
        assert abs(gap - (ren - s.steps["2"])) > 1, "carbon must never be an offset"


def test_goods_sit_beside_never_inside(data):
    h, rows = data["headline"], goods.layer3()
    latest = max((r for r in rows if r.get("scheme") == "total"), key=lambda r: r["fy"])
    g = h["goods_beside_gbp"]
    assert (g["low"], g["central"], g["high"]) == tuple(latest["passed_through"][k] for k in ("low", "central", "high"))
    assert g["period"] == latest["period"] and "not restated" in g["money_note"]
    # each headline is that choice's gap exactly: goods are not added in
    for f in ex.FLEETS:
        assert h["net_zero_costs_gbp"][f] == data["p2_receipt"]["fleets"][f]["totals"]["gap"]


def test_pence_per_pound_is_gap_over_what_you_pay(data):
    h = data["headline"]
    w = h["with_net_zero_gbp"]["gbp"]
    for k in ex.FLEETS:
        assert h["net_zero_pence_per_pound"][k] == pytest.approx(100 * h["net_zero_costs_gbp"][k]["gbp"] / w)
    assert h["default"]["pence_per_pound"] == h["net_zero_pence_per_pound"][ex.DEFAULT_FLEET]


# ---------------------------------------------------------------- the receipt

def test_lines_add_up_to_both_columns_and_the_steps(data, stairs):
    for f in ex.FLEETS:
        r = data["p2_receipt"]["fleets"][f]
        lines = [ln for s in r["sections"] for ln in s["lines"] if ln["status"] != "not_built"]
        assert len(lines) == len(stairs[f].lines)
        assert sum(ln["actual"]["gbp"] for ln in lines) == pytest.approx(r["totals"]["with_net_zero"]["gbp"], abs=1e-6)
        assert sum(ln["all_gas"]["gbp"] for ln in lines) == pytest.approx(r["totals"]["without_net_zero"]["gbp"], abs=1e-6)
        assert sum(st["money"]["gbp"] for st in r["steps"]) == pytest.approx(r["totals"]["with_net_zero"]["gbp"], abs=0.01)
        for ln in lines:
            eng = stairs[f].line(ln["id"])
            assert ln["actual"]["gbp"] == eng.actual and ln["all_gas"]["gbp"] == eng.all_gas
            assert ln["basis"] == {"actual": eng.basis_actual, "all_gas": eng.basis_all_gas}
            assert ln["engine_source_id"] == eng.source_id


def test_every_line_carries_the_required_fields(data):
    for f in ex.FLEETS:
        for s in data["p2_receipt"]["fleets"][f]["sections"]:
            for ln in s["lines"]:
                for key in ("id", "label", "explain", "actual", "all_gas", "gap", "step", "basis",
                            "status", "source_id", "note"):
                    assert key in ln, (ln["id"], key)
                if ln["status"] == "not_built":
                    assert ln["note"], ln["id"]        # the reason it is missing
                    continue
                for col in ("actual", "all_gas", "gap"):
                    m = ln[col]
                    assert all(isinstance(m[k], float) for k in ("gbp", "fixed_gbp", "gbp_per_kwh")), (ln["id"], col)
                assert ln["basis"]["actual"] in ("allowance", "measured", "modelled", "estimated")
                assert ln["basis"]["all_gas"] in ("allowance", "measured", "modelled", "estimated")
                assert ln["step"]


def test_every_money_splits_into_fixed_and_per_kwh(data):
    ref = data["household"]["reference_kwh"]
    n = 0
    for path, m in monies(data):
        if m["gbp"] is None:
            continue
        n += 1
        assert m["fixed_gbp"] is not None and m["gbp_per_kwh"] is not None, path
        assert m["fixed_gbp"] + m["gbp_per_kwh"] * ref == pytest.approx(m["gbp"], abs=0.01), path
    assert n > 100


def test_every_source_id_resolves_to_a_full_source(data):
    used = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "source_id" and isinstance(v, str):
                    used.add(v)
                elif k == "source_ids":
                    used.update(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    assert used == set(data["sources"])
    for sid, s in data["sources"].items():
        assert s["publisher"] and s["title"] and s["locator"], sid
        assert s["url"] or s["publisher"] == ex.ENGINE, sid


def test_unknown_engine_source_id_raises():
    with pytest.raises(KeyError):
        ex.source_tokens("ofgem-annex4-v1.25; made-up-source")
    assert ex.source_tokens("elexon-fuelhh+neso (residual); hmrc-cps") == ["elexon-fuelhh", "neso", "hmrc-cps"]


# ---------------------------------------------------------------- presets, today, break-even

def test_presets_read_from_ofgem_tdcv_table_1(data):
    assert [(p["ofgem_level"], p["kwh"]) for p in data["household"]["presets"]] == [
        ("Low", 1600), ("Medium", 2500), ("High", 3800)]      # Ofgem TDCV decision, Table 1, PC1, 2026
    assert data["household"]["reference_kwh"] == data["household"]["presets"][1]["kwh"]


def test_presets_reader_fails_loudly_if_table_moves(tmp_path):
    txt = ex.TDCV_TXT.read_text().replace("2026 TDCV", "2027 TDCV", 1)
    p = tmp_path / "tdcv.txt"
    p.write_text(txt)
    with pytest.raises(ValueError):
        ex.presets_from_tdcv(p)


def test_today_matches_the_engine(data):
    from datetime import date
    t = today.today(date.fromisoformat(data["p3_today"]["date"])).as_dict()
    assert data["p3_today"]["fleet_a_pure_gas"]["gbp_per_mwh"] == t["fleet_a_pure_gas_cost_of_power"]["gbp_per_mwh"]
    assert data["p3_today"]["market_price"]["gbp_per_mwh"] == t["day_ahead"]["gbp_per_mwh"]
    assert data["p3_today"]["sap"]["gbp_per_mwh"] == t["sap"]["gbp_per_mwh"]


def test_break_even_present_for_both_fleets(data):
    for f in ex.FLEETS:
        assert data["p4_break_even"]["fleets"][f]["text"]


# ---------------------------------------------------------------- the file itself

def test_written_file_round_trips_and_copies(data, tmp_path):
    site = tmp_path / "site" / "latest.json"
    p = ex.write(data, out_dir=tmp_path / "out", site=site)
    assert p.name == data["generated_at"][:10] + ".json"
    assert json.loads(site.read_text()) == json.loads(p.read_text())
    assert json.loads(p.read_text())["schema_version"] == ex.SCHEMA_VERSION


def test_no_figures_typed_into_export_py():
    """Only tolerances, the reference consumption and the slider's control values may appear."""
    src = Path(ex.__file__).read_text()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', code)     # drop string literals (words, URLs)
    code = re.sub(r"#.*", "", code)
    nums = set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?:e-?\d+)?", code))
    allowed = {"0", "1", "2", "3", "100",
               "1000", "6000", "2500.0", "0.005", "0.01", "1e-9"}   # tolerances, controls, digits of dates
    assert nums <= allowed, sorted(nums - allowed)


def test_words_never_call_carbon_an_offset():
    text = json.dumps([ex.WORDS, ex.STEP_WORDS, ex.FLEET_WORDS]).lower()
    assert "offset" not in text
    assert "cost of net zero" in ex.STEP_WORDS["2"][1].lower()


# ---------------------------------------------------------------- history (P5)

def test_history_covers_every_cap_period_built_fleets_both_grids(data):
    h = data["p5_history"]
    keys = [r.period for r in receipt_actual.receipts()]
    assert len(h["periods"]) == len(keys) == 32
    assert h["periods"][0]["start"] == "2015-04-01"
    assert h["periods"][-1]["id"] == data["period"]["id"]
    for p in h["periods"]:
        # DESNZ's figure ("D") is for 2030 plant: not used for past periods
        assert set(p["variants"]) == {f"{f}|{g}" for f in ex.BUILT for g in ex.GRIDS}


@pytest.mark.parametrize("i", [0, 14, 30])
def test_history_headline_is_actual_minus_step_1_per_period(data, i):
    """Spot periods recomputed straight from the engine: gap = actual − step 1, then restated."""
    p = data["p5_history"]["periods"][i]
    k = receipt_actual.period_key(p["engine_label"])
    f = rebase(1.0, staircase.price_year(k), data["money_year"])
    assert p["to_money_year"] == pytest.approx(f, rel=1e-12)
    for fl in ex.BUILT:
        for g in ex.GRIDS:
            s = staircase.staircase(k, fl, ex.KWH, ex.ORDER, grid=g)
            v = p["variants"][f"{fl}|{g}"]
            assert v["gap"]["gbp"] == pytest.approx((s.actual_total - s.steps["1"]) * f, abs=1e-9)
            assert v["with_net_zero"]["gbp"] == pytest.approx(s.actual_total * f, abs=1e-9)
            assert [n["id"] for n in v["not_counted"]] == [kk for kk, _ in s.nulls]


def test_history_latest_period_equals_the_receipt(data):
    last = data["p5_history"]["periods"][-1]
    assert last["to_money_year"] == 1.0
    for fl in ex.BUILT:
        assert last["variants"][f"{fl}|low"]["gap"] == data["p2_receipt"]["fleets"][fl]["totals"]["gap"]


def test_history_missing_figures_stay_null(monkeypatch):
    """If the engine cannot build a period, that period is null with the reason, never filled."""
    real = staircase.staircase
    bad = receipt_actual.receipts()[3].period

    def fake(k, *a, **kw):
        if k == bad:
            raise ValueError("UNSOURCED: test")
        return real(k, *a, **kw)
    monkeypatch.setattr(staircase, "staircase", fake)
    h = ex.p5_history(2026)
    v = h["periods"][3]["variants"]["A|low"]
    assert v["gap"]["gbp"] is None and v["status"] == "not_built" and "UNSOURCED" in v["reason"]
    assert h["periods"][4]["variants"]["A|low"]["gap"]["gbp"] is not None


def test_history_epg_note_reads_ofgem_observation_window(data):
    w = data["p5_history"]["ofgem_window"]
    assert (w["period"], w["first"], w["last"]) == ("Q2 2023", "2022-11-17", "2023-02-17")   # Annex 2, 2a(iii)
    assert "17 November 2022 to 17 February 2023" in data["p5_history"]["epg"]
    assert [p["id"] for p in data["p5_history"]["periods"] if p["epg"]] == ["2022-Q4", "2023-Q1", "2023-Q2"]


# ---------------------------------------------------------------- switches (P6)

def test_switches_cover_every_setting(data):
    """Full grid only for gas-power choice x gas price x grid: 3 x 4 x 2 = 24 settings."""
    sw = data["p6_switches"]
    assert [o["id"] for o in sw["gas"]] == ["desnz", "today", "60", "100"]
    assert [f["id"] for f in sw["fleet"]] == ["A", "B", "D"]
    assert len(sw["variants"]) == 4 * 3 * len(ex.GRIDS) == 24
    assert sw["key"] == "gas|fleet|grid"
    for v in sw["variants"].values():
        assert abs(v["identity_residual"]) < 1e-8
    slot = sw["gas_slots_unbuilt"][0]
    assert slot["id"] == "normal_years" and slot["built"] is False and "gbp_mwh" not in slot


def test_sensitivity_table_is_one_switch_at_a_time(data):
    """Efficiency, build cost, hurdle and margin move one at a time from the default."""
    k = ex.latest_period()
    sens_ = data["p6_switches"]["sensitivity"]
    rows = sens_["rows"]
    want = {(f, sw, c) for f in ex.FLEETS for sw in ex.PLANT_APPLIES[f] for c in ex.SENS_CASES[sw]
            if c != ex.SWITCH_DEFAULT[sw]}
    assert {(r["fleet"], r["switch"], r["case"]) for r in rows} == want
    assert len(rows) == 7 + 4   # fleet A: eta 1, capex 2, hurdle 2, margin 2; fleet B: capex 2, hurdle 2
    r = next(x for x in rows if (x["fleet"], x["switch"], x["case"]) == ("A", "hurdle", "low"))
    s = staircase.staircase(k, "A", ex.KWH, ex.ORDER, hurdle="low")
    assert r["gap"]["gbp"] == pytest.approx(s.actual_total - s.steps["1"], abs=1e-9)
    base = data["p6_switches"]["variants"]["today|A|low"]["gap"]["gbp"]
    assert r["change_gbp"] == pytest.approx(r["gap"]["gbp"] - base, abs=1e-12)
    m = next(x for x in rows if (x["fleet"], x["switch"], x["case"]) == ("A", "margin", "median"))
    assert m["gap"]["gbp"] > base     # the vw-mean default is the highest margin: smallest gap


def test_export_runs_in_under_five_minutes(tmp_path):
    """Brief s16: `python -m gascf.export` must finish in under 5 minutes, from a cold start."""
    import os
    import subprocess
    import sys
    import time
    t0 = time.monotonic()
    subprocess.run([sys.executable, "-W", "ignore", "-m", "gascf.export", "--site", "", "--out", str(tmp_path)],
                   check=True, cwd=Path(ex.__file__).parents[2], capture_output=True, timeout=300,
                   env=dict(os.environ))
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert time.monotonic() - t0 < 300


def test_switch_today_low_is_the_receipt_exactly(data):
    """And the not-net-zero lines stay out of every variant's gap (same in both columns)."""
    for fl in ex.FLEETS:
        v, r = data["p6_switches"]["variants"][f"today|{fl}|low"], data["p2_receipt"]["fleets"][fl]
        assert v["with_net_zero"] == r["totals"]["with_net_zero"]
        assert v["without_net_zero"] == r["totals"]["without_net_zero"]
        assert [s["money"] for s in v["steps"]] == [s["money"] for s in r["steps"]]


def test_switch_gas_prices_are_the_engines_sensitivity_runs(data):
    k = ex.latest_period()
    sw = data["p6_switches"]
    d = sensitivity.desnz_gas(money_year=staircase.price_year(k))["gbp_mwh"].value
    assert sw["gas"][0]["gbp_mwh"] == pytest.approx(d, abs=1e-12)
    assert sw["gas"][1]["gbp_mwh"] == staircase.annex2_periods()[k].gas_index
    s = sensitivity.staircase_at_gas(k, 100.0, "B")
    v = sw["variants"]["100|B|low"]
    assert v["with_net_zero"]["gbp"] == pytest.approx(s.actual_total, abs=1e-9)
    assert v["without_net_zero"]["gbp"] == pytest.approx(s.steps["1"], abs=1e-9)


def test_switch_grid_high_is_staircase_grid_high(data):
    k = ex.latest_period()
    for fl in ex.FLEETS:
        s = staircase.staircase(k, fl, ex.KWH, ex.ORDER, grid="high")
        assert data["p6_switches"]["variants"][f"today|{fl}|high"]["gap"]["gbp"] == pytest.approx(
            s.actual_total - s.steps["1"], abs=1e-9)
    assert data["p6_switches"]["grid"][1]["gbp"] == pytest.approx(s.inputs["grid_netzero_high"], abs=1e-12)


# ---------------------------------------------------------------- the opposing case (P9)

def test_ar7_reader_spot_values():
    a = ex.ar7_results()
    off = a["techs"]["Offshore Wind"]                 # DESNZ AR7 results, table (E)
    assert (off["strike_old"], off["strike_new"]) == (65.45, 91.2)
    assert a["techs"]["Floating Offshore Wind"]["strike_new"] == 216.49
    assert a["total_mw"] == 8437.5                    # table (F), total
    assert (a["price_base"], a["published"]) == (2024, "14 January 2026")
    assert a["delivery_years"][0] == "2028/29" and a["delivery_years"][-1] == "2030/31"   # table (D)


def test_ar7_reader_fails_loudly_if_layout_moves(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Contracts for Difference Allocation Round 7 results")
    p = tmp_path / "ar7.pdf"
    doc.save(p)
    with pytest.raises(ValueError):
        ex.ar7_results(p)


def test_egc_scope_sentence_is_in_the_stored_report(tmp_path):
    assert "Wider system costs" in ex.egc_scope_quote()
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Electricity Generation Costs 2025")
    p = tmp_path / "egc.pdf"
    doc.save(p)
    with pytest.raises(ValueError):
        ex.egc_scope_quote(p)


def test_opposing_case_placeholders_all_resolve(data):
    p9 = data["p9_opposing_case"]
    assert [pt["id"] for pt in p9["points"]] == ["strike", "lcoe", "refunds"]
    for pt in p9["points"]:
        for part in ("case", "answer"):
            for name in re.findall(r"\{(\w+)\}", pt[part]):
                f = p9["figures"][name]
                assert f["value"] is not None and f["source_id"] in data["sources"], name
                assert f["basis"] in ("allowance", "measured", "modelled", "estimated"), name


def test_opposing_case_answers_use_the_files_own_numbers(data):
    F = {k: v["value"] for k, v in data["p9_opposing_case"]["figures"].items()}
    gaps = [v["gap"]["gbp"] for p in data["p5_history"]["periods"] for v in p["variants"].values()]
    assert F["history_min_gap"] == pytest.approx(min(gaps), abs=1e-12)
    assert F["fleet_b_now"] == data["p6_switches"]["variants"]["today|B|low"]["fleet_gbp_mwh"]
    walk = data["p9_opposing_case"]["reconciliation"]["B"]
    assert walk[0]["level"] == F["desnz_gas_ex_carbon"] == 70.0       # DESNZ Annex A: 111 − 41
    assert walk[-1]["level"] == pytest.approx(F["fleet_b_now"], abs=1e-6)
    epg = [p for p in data["p5_history"]["periods"] if p["epg"]]
    assert F["epg_cfd_refund_max"] == pytest.approx(
        -min(p["variants"]["A|low"]["cfd_on_bill"]["gbp"] for p in epg), abs=1e-12)
    assert F["epg_cfd_refund_max"] > 0                   # Ofgem's CfD allowance was a refund then


def test_opposing_case_words_stop_if_the_numbers_turn(data):
    """The words claim, e.g., that net zero added cost in every period. If the engine said
    otherwise, the export must stop, not print a sentence the numbers contradict. Uses a copy of
    the module's built file rather than rebuilding history and switches (saves ~90 s)."""
    import copy
    hist = copy.deepcopy(data["p5_history"])
    for v in hist["periods"][0]["variants"].values():
        v["gap"] = ex.money(-1.0, -1.0, 0.0)
    sw = copy.deepcopy(data["p6_switches"])
    with pytest.raises(ValueError, match="no longer match"):
        ex.p9_opposing_case(ex.latest_period(), hist, sw, 2026)
