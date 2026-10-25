"""Ticket 44, key half (s36 group D): new figures keys for §4.3, §6.2, §7.4, §8.4, §15 and §18.

Seam: `tools.figures.generate(run, modules=[...])` on the v4-s35 run file with fixture fields added for
exports that are not built yet (the worked half-hour export is the serial tail's half of 44). Every s35
value here is a reference, not quotable; the release run (35) gives the printed values.
"""
import copy
import json
from pathlib import Path

import pytest

from tools import figures as F

ROOT = Path(__file__).resolve().parents[1]
RUN = json.loads((ROOT / "out/v4/2026-10-14-s35.json").read_text())


def _run(**fleet2019):
    r = copy.deepcopy(RUN)
    r["fleet"]["2019"].update(fleet2019)
    return r


def test_ic_peak_dy_contracted_mw_2019_is_a_bare_number():
    """E1 (Editor-in-chief, 17 Oct): the draft adds "MW" after the value, so the value is a bare number."""
    from tools.figures_keys import fleet
    k = F.generate(_run(ic_peak_dy="2019/20", ic_peak_dy_contracted_mw=2886.76), modules=[fleet])["keys"]
    e = k["ic_peak_dy_contracted_mw_2019"]
    assert isinstance(e["value"], (int, float)) and not isinstance(e["value"], bool)
    assert e["value"] == 2886.76
    assert e["meta"]["units"] == "MW" and e["meta"]["run_field"] == "fleet[2019].ic_peak_dy_contracted_mw"
    assert k["ic_peak_dy_2019"]["value"] == "2019/20"
    # v4-s35 predates the field: None, never a string
    assert F.generate(RUN, modules=[fleet])["keys"]["ic_peak_dy_contracted_mw_2019"]["value"] is None


def test_shao_uplift_2022_is_declared_modelled_not_sourced():
    """E2 (Editor-in-chief, 17 Oct): the engine's own value (Shao's coefficients applied in 2022, s22 notes),
    not a figure Shao and others published; declared modelled so the export (serial tail) carries the label."""
    from tools.figures_keys import worked_hh
    e = F.generate(RUN, modules=[worked_hh])["keys"]["shao_uplift_2022_gbp_mwh"]
    assert e["meta"]["basis"] == "modelled"
    assert "modelled" in e["meta"]["label"].lower()
    assert "Shao's" not in e["meta"]["label"]
    assert e["meta"]["units"] == "£/MWh, cash" and e["meta"]["period"] == "2022"
    assert e["meta"].get("status") != "SOURCED" and "claims_id" not in e["meta"]
    # Re-pinned 19 Oct 2026 (card [internal ticket]): the export half is built; the value is the run's own 2022 Shao mean.
    assert e["value"] == RUN["fleet"]["2022"]["moe"]["shao_mean_gbp_mwh"]
    sourced = ROOT / "data/figures/sourced.yaml"
    if sourced.exists():
        assert "shao_uplift_2022_gbp_mwh" not in sourced.read_text()


WH = {"peak": {"date": "2024-01-15", "time": "12:00-12:30", "sp": 25, "residual_mw": 44478.5, "raw_step_gbp_mwh": 10.0,
               "scaled_step_gbp_mwh": 12.354, "p0_gbp_mwh": 80.0, "p1_gbp_mwh": 90.0, "top_block": "new_ocgt",
               "rb_cost_gbp_mwh": 90.0},
      "median": {"date": "2024-08-15", "time": "10:00-10:30", "sp": 21, "residual_mw": 22010.0, "raw_step_gbp_mwh": 2.0,
                 "scaled_step_gbp_mwh": 2.4708, "p0_gbp_mwh": 60.0, "p1_gbp_mwh": 62.0, "top_block": "ccgt",
                 "rb_cost_gbp_mwh": 62.0}}


def _wh_run():
    r = copy.deepcopy(RUN)
    r["fleet"]["2024"]["worked_hh"] = copy.deepcopy(WH)
    return r


def test_wh_keys_take_placeholder_names():
    from tools.figures_keys import worked_hh
    k = F.generate(_wh_run(), modules=[worked_hh])["keys"]
    eng = {"wh_peak_halfhour": "rb.s4.worked_hh_peak_date", "wh_peak_settlement_period": "rb.s4.worked_hh_peak_sp",
           "wh_median_halfhour": "rb.s4.worked_hh_median_date",
           "wh_median_settlement_period": "rb.s4.worked_hh_median_sp",
           "wh_peak_uplift_gbp_mwh": "rb.s4.merit_order_uplift_peak_gbp_mwh",
           "wh_median_uplift_gbp_mwh": "rb.s4.merit_order_uplift_median_gbp_mwh"}
    for name, field in eng.items():
        assert k[name]["meta"]["engine_field"] == field
    for p in ("peak", "median"):
        assert k[f"wh_{p}_residual_gw"]["value"] == pytest.approx(WH[p]["residual_mw"] / 1000, abs=1e-12)
        assert k[f"wh_{p}_settlement_period"]["value"] == WH[p]["sp"]          # number only
        assert isinstance(k[f"wh_{p}_settlement_period"]["value"], int)
        assert k[f"wh_{p}_halfhour"]["value"] == f"{WH[p]['date']} {WH[p]['time']}"
        assert k[f"wh_{p}_uplift_gbp_mwh"]["value"] == WH[p]["scaled_step_gbp_mwh"]
        assert k[f"annex.s4.merit_order_uplift_raw_{p}_gbp_mwh"]["value"] == WH[p]["raw_step_gbp_mwh"]
    assert not [n for n in k if n.startswith("rb.s4.")]
    # without worked_hh every wh key is None; shao_uplift_2022 reads fleet[2022] (re-pinned 19 Oct 2026, [internal ticket]),
    # and so do shao_uplift_2021 and _2023 (R26, [internal ticket]; card [internal ticket])
    assert all(v["value"] is None for n, v in F.generate(RUN, modules=[worked_hh])["keys"].items()
               if not n.startswith("shao_uplift_"))


def test_wh_halfhour_prints_the_span_on_the_uk_clock():
    """Ticket 44, option (b) (Editor-in-chief, 17 Oct 2026): wh_*_halfhour is the date plus the half-hour
    as a span on the UK clock (SP25 -> '12:00-12:30', SP48 -> '23:30-00:00'); a clock-change day (46 or
    50 periods) still stops the build."""
    from tools.figures_keys import worked_hh
    k = F.generate(_wh_run(), modules=[worked_hh])["keys"]
    assert k["wh_peak_halfhour"]["value"] == "2024-01-15 12:00-12:30"
    r = _wh_run()
    r["fleet"]["2024"]["worked_hh"]["median"].update(sp=48)
    assert F.generate(r, modules=[worked_hh])["keys"]["wh_median_halfhour"]["value"] == "2024-08-15 23:30-00:00"
    for day in ("2024-03-31", "2024-10-27"):              # last Sundays of March and October 2024
        r = _wh_run()
        r["fleet"]["2024"]["worked_hh"]["peak"].update(date=day)
        with pytest.raises(NotImplementedError, match="clock-change"):
            F.generate(r, modules=[worked_hh])


def test_wh_rb_cost_and_marginal_plant_from_the_export():
    """R-A3 (17 Oct 16:18): from the export only, placeholder names; the plant is a stack block name."""
    from tools.figures_keys import worked_hh
    k = F.generate(_wh_run(), modules=[worked_hh])["keys"]
    for p in ("peak", "median"):
        assert k[f"wh_{p}_rb_cost_gbp_mwh"]["value"] == WH[p]["rb_cost_gbp_mwh"]
        assert k[f"wh_{p}_marginal_plant"]["value"] == WH[p]["top_block"]
        assert k[f"wh_{p}_rb_cost_gbp_mwh"]["meta"]["units"] == "£/MWh, cash"
    bad = _wh_run()
    bad["fleet"]["2024"]["worked_hh"]["peak"]["top_block"] = "Coal"
    with pytest.raises(ValueError, match="block"):
        F.generate(bad, modules=[worked_hh])


MARGINS = ROOT / "work/s24-closure-test/margins.json"


def _margins(tmp_path, rug=(56.34, 13.96, 3.091), lng=(139.6, 35.04, -0.833)):
    m = json.loads(MARGINS.read_text())
    for st, vals in (("Rugeley", rug), ("Longannet", lng)):
        m[st]["years"] = [{"year": y, "margin_before_filters_gbp_m": v} for y, v in zip((2013, 2014, 2015), vals)]
    p = tmp_path / "margins.json"
    p.write_text(json.dumps(m))
    return p


def test_closure_margin_keys_read_regenerated_margins_last_year(tmp_path, monkeypatch):
    """R-A4 option A: the file the release step regenerates; years[-1] (2015, £m cash); sha pinned in meta."""
    from tools.figures_keys import closures
    import hashlib
    p = _margins(tmp_path)
    monkeypatch.setattr(closures, "MARGINS", p)
    k = F.generate(RUN, modules=[closures])["keys"]
    assert k["rugeley_margin_ex_carbon_last_year_gbp_m"]["value"] == 3.091
    assert k["longannet_margin_ex_carbon_last_year_gbp_m"]["value"] == -0.833
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    for n in ("rugeley_margin_ex_carbon_last_year_gbp_m", "longannet_margin_ex_carbon_last_year_gbp_m"):
        assert k[n]["meta"]["file_sha256"] == sha and k[n]["meta"]["year"] == 2015
        assert k[n]["meta"]["units"] == "£m, cash"


@pytest.mark.parametrize("rug,lng", [((56.34, 13.96, 0.0), (139.6, 35.04, -0.833)),
                                     ((56.34, -1.0, 3.091), (139.6, 35.04, -0.833)),
                                     ((56.34, 13.96, 3.091), (139.6, 35.04, 0.0))])
def test_closure_margin_signs_match_the_text(tmp_path, monkeypatch, rug, lng):
    from tools.figures_keys import closures
    monkeypatch.setattr(closures, "MARGINS", _margins(tmp_path, rug, lng))
    with pytest.raises(ValueError, match="§6.2"):
        F.generate(RUN, modules=[closures])


def test_wf_largest_three_steps_ranks_the_eleven_rows():
    """R-A5 option A: by |value|, sign shown; a negative step is named as lowering the gap."""
    from tools.figures_keys import ranking, core
    c = core.values(RUN)
    wf = {k: c[k] for k in core.WF_ORDER}
    assert len(wf) == 11
    want = sorted(wf, key=lambda n: -abs(wf[n]))[:3]
    v = F.generate(RUN, modules=[ranking])["keys"]["wf_largest_three_steps"]["value"]
    assert [r["key"] for r in v] == want
    assert [r["value_gbp_bn"] for r in v] == [wf[n] for n in want]
    for r in v:
        assert r["lowers_gap"] is (r["value_gbp_bn"] < 0)
    # on s35, reference only (not pinned in the build): RO, carbon in the price, power before carbon
    assert [r["key"] for r in v] == ["wf_ro_gbp_bn", "wf_carbon_gbp_bn", "wf_power_before_carbon_gbp_bn"]
    assert v[2]["label"] == "Power, before carbon" and v[2]["lowers_gap"] is True


def _row(block, choice, change, option="o"):
    return {"block": block, "choice": choice, "option": option, "change_gbp_bn": change}


def test_largest_two_choices_by_effect_from_one_at_a_time_table():
    """R-A6: Table 15.1's rows grouped by Choice 1-8 (ticket 28's map), ranked block only; a choice's effect is
    its largest |headline - central|; top two; ties by choice number."""
    from tools.figures_keys import ranking
    rows = [_row("ranked", 3, 17.78, "kept price"), _row("ranked", 4, -38.17, "e 0.06"), _row("ranked", 4, 7.76),
            _row("ranked", 2, 6.07), _row("ranked", 1, -17.78, "residual"),
            _row("methods_page", 3, 38.66, "no merit-order uplift"), _row("methods_page", 1, -20.54)]
    got = ranking.largest_two_choices(rows)
    assert [(g["choice"], g["option"]) for g in got] == [(4, "e 0.06"), (1, "residual")]   # 1 beats 3 on the tie
    assert got[0]["change_gbp_bn"] == -38.17 and got[0]["effect_gbp_bn"] == 38.17
    assert F.generate(RUN, modules=[ranking])["keys"]["largest_two_choices_by_effect"]["value"] is None
