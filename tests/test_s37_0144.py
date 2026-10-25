"""v4-s37, decision 0144 (Richard Lyon, 20 Oct 2026: "Yes, take all the recommendations (headline about £141bn)"),
on the modeller's decision sheet for the critic's review of v4-s36 (card [internal ticket]). Tests 1-7 of the sheet's
"Tests first" section, each seen red on v4-s36 (main at 36c9745) before any engine change.

Expected values come from the stored sources and the released v4-s36 run file, never from the engine's own output:
- Albrizio et al. (2022) Table 2 (sector demand elasticities and EU consumption shares), stored text;
- Krichene (2005) Table 5 (short-run supply 0.06) and Table 2 (world long-run pair, supply 0.16, demand -0.45);
- the v4-s36 run file `out/v4/2026-10-20-s36.json` and `out/figures/v4-s36.json` (released, tagged v4-s36);
- the Cottam margin test stored under `work/s37-cottam/`.

Seams: `fossil_like_for_like` (gas_feedback, GAS_ELASTICITY, the closure register), `bills.fleet_lfl` and the
switch registries, the figures-key modules (labels, range, sensitivity rows).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gascf import bills as B  # noqa: E402
from gascf import fossil_like_for_like as L  # noqa: E402

RAW = ROOT / "data/raw/s36"
S36_RUN = ROOT / "out/v4/2026-10-20-s36.json"
S36_FIGS = ROOT / "out/figures/v4-s36.json"
YEAR = 2018          # a year with extra running, a merit-order uplift and a positive gas-feedback dQ (42 TWh on v4-s36)


@pytest.fixture
def v4_s38():
    """v4-s39 (card [internal ticket]): test 1 is 0144's arithmetic on the v4-s36/s38 engine (monthly prices, carbon at gas
    intensity, register MW and coal hours); the v4-s39 rulings are set back explicitly (tests/_pre_0133.py)."""
    from _pre_0133 import pre_s39
    B.fleet_lfl.cache_clear()
    with pre_s39():
        yield
    B.fleet_lfl.cache_clear()


# ----------------------------------------------------------------------------- sources


def _albrizio_eu_weighted_demand_elasticity() -> float:
    """Albrizio et al. (2022) Table 2: sector price elasticities of demand, weighted by the EU consumption share."""
    t = (RAW / "s36-albrizio2022_imf_wp22-143.txt").read_text()
    m = re.search(r"Industry ([\d.]+) (\d+) \d+ Households ([\d.]+) (\d+) \d+ Power sector ([\d.]+) (\d+) \d+ "
                  r"Other sectors ([\d.]+) (\d+)", t)
    assert m, "Albrizio Table 2 not found in the stored text"
    v = [float(x) for x in m.groups()]
    pairs = [(v[0], v[1]), (v[2], v[3]), (v[4], v[5]), (v[6], v[7])]
    assert sum(s for _, s in pairs) == 100
    return sum(e * s for e, s in pairs) / 100


def _krichene_table5_supply_short_run() -> float:
    t = (RAW / "s36-krichene2005_IMF_WP0532.txt").read_text()
    i = t.index("Table 5: World Crude Oil and Natural Gas: The SEM Extended to Include the NEER")
    m = re.search(r"Natural gas Supply\s+Price elasticity\s+([\d.]+) \(", t[i:])
    return float(m.group(1))


def _krichene_table2_long_run_pair() -> tuple[float, float]:
    """Table 2, VECM, 1918-2004: natural gas supply price elasticity and natural gas demand price elasticity."""
    t = (RAW / "s36-krichene2005_IMF_WP0532.txt").read_text()
    i = t.index("Table 2: World Crude Oil and Natural Gas: Long-Run Elasticities")
    blk = t[i:i + 3000]
    d = re.search(r"Natural gas demand\s+Price elasticity\s+(-[\d.]+) \(", blk)
    s = re.search(r"Natural gas supply\s+Price elasticity\s+([\d.]+) \(", blk)
    return float(s.group(1)), -float(d.group(1))


# ----------------------------------------------------------------------------- test 1 (finding 1, option A)


def _fleet(year: int, s=None) -> dict:
    s = B.CENTRAL if s is None else s
    return B.fleet_lfl(year, *B._lfl_args(s, year))


def _lfl(year: int, s=None):
    """The LfL year exactly as fleet_lfl builds it (same register, residual, margin, transport and IC basis)."""
    s = B.CENTRAL if s is None else s
    cf = str(L.closures_path()) if s.closures == "legitimate" else None
    return L.lfl_year(year, s.residual, s.margin, s.transport, s.closures, s.newbuild, cf, s.coal_lf, s.ic_basis)


def test_1_extra_running_charged_the_market_price_each_month(v4_s38):
    """1A: the extra running of the plant real Britain had is charged what its actual output is charged, each
    month: actual price less carbon (P - C), plus the merit-order uplift, plus the gas-price feedback; its fuel,
    running and gas-transport cost is no longer counted on top. Expected parts built here from the LfL year's own
    volumes and the price series, not from fleet_lfl's sums."""
    r = _lfl(YEAR)
    assert r.extra_twh > 1.0, "the test year must have extra running"
    f = _fleet(YEAR)
    P, C = B.p_elec(B.CENTRAL.route), B.c_marg()
    ms = range(1, 13)
    pc = {m: P[(YEAR, m)]["gbp_per_mwh"] - C[(YEAR, m)]["gbp_per_mwh"] for m in ms}
    # market part: every market-bought MWh, actual output AND extra running, at P - C
    exp_market = sum(pc[m] * (r.market_twh_m[m] + r.extra_twh_m[m]) for m in ms)
    assert f["market_gbp_m"] == pytest.approx(exp_market, rel=1e-12)
    # uplift: on the actual output and on the extra volume
    mult, flat = L.moe_factor(r, B.CENTRAL.moe)
    exp_moe = (mult * (sum(r.moe_vol_f_m.values()) + sum(r.moe_vol_x_m.values())) / 1e6
               + flat * (r.actual_fossil_twh + r.extra_twh))
    assert f["moe_gbp_m"] == pytest.approx(exp_moe, rel=1e-12)
    # feedback: the same £/MWh on the extra running as on the actual output
    g = L.gas_feedback(r, B.CENTRAL.gas_feedback)
    per = {m: g["price_rise_frac"] * r.gas_marginal_share * L.gas_price(YEAR, m) / L._eta_dukes("ccgt", YEAR)
           for m in ms}
    exp_gfb = sum(per[m] * (r.market_twh_m[m] + r.extra_twh_m[m]) for m in ms)
    assert f["gas_feedback_gbp_m"] == pytest.approx(exp_gfb, rel=1e-12)
    # the running cost already counted is taken out: no extra-running fuel, VOM or transport in the at-cost parts
    new_gas_fuel = (r.new or {}).get("gas_fuel_gbp_m", 0.0)
    assert f["gas_feedback_at_cost_gbp_m"] == pytest.approx(g["price_rise_frac"] * new_gas_fuel, rel=1e-12, abs=1e-9)
    assert f["extra_running"] == "market"
    parts = ("market_gbp_m", "moe_gbp_m", "gas_feedback_gbp_m", "fixed_gbp_m", "fuel_gbp_m", "vom_gbp_m",
             "transport_gbp_m")
    assert f["total_gbp_m"] == pytest.approx(sum(f[k] for k in parts), rel=1e-12)


def test_1_option_c_keeps_the_v4_s36_mix_to_the_penny(monkeypatch, request, v4_s38):
    """Sensitivity row C (keep the mix): with extra_running='cost' the fleet's uplift, running and transport parts
    are the released v4-s36 run file's own (fleet block, 2018), to the penny (£m to 1e-6). These parts do not
    depend on the gas-feedback elasticity (2A) or on Cottam (open in 2018 in both registers)."""
    # v4-s36's own register (36c9745, tests/_pre_0133.py): the release register has since moved Rugeley (0159) and
    # the coal rows (0163, 0166), which change the 2018 fleet (card [internal ticket])
    from _pre_0133 import PRE_0144_REGISTER
    monkeypatch.setenv("GASCF_FOSSIL_CLOSURES", str(PRE_0144_REGISTER))
    # fleet_lfl's cache is keyed on its arguments, not on the register in use: clear it either side
    B.fleet_lfl.cache_clear()
    request.addfinalizer(B.fleet_lfl.cache_clear)
    run = json.loads(S36_RUN.read_text())
    rel = run["fleet"][str(YEAR)]
    from dataclasses import replace
    f = _fleet(YEAR, replace(B.CENTRAL, extra_running="cost"))
    assert f["extra_running"] == "cost"
    for k in ("moe_gbp_m", "vom_gbp_m", "transport_gbp_m"):
        assert f[k] == pytest.approx(rel[k], abs=1e-6), k
    c = _fleet(YEAR)
    assert c["moe_gbp_m"] > f["moe_gbp_m"] and c["vom_gbp_m"] < f["vom_gbp_m"]


# ----------------------------------------------------------------------------- test 2 (finding 2, option A)


def test_2_feedback_formula_has_the_demand_side_albrizio_pair():
    """dP/P = dQ / ((e_s + e_d) Q): e_s = 0.06 (Krichene 2005 Table 5, short-run supply, as Albrizio use it) and
    e_d = 0.169 (Albrizio et al. 2022 Table 2, EU-weighted), one source and one (European) market. Replaces the
    supply-only pin in test_fossil_like_for_like."""
    e_s, e_d = _krichene_table5_supply_short_run(), round(_albrizio_eu_weighted_demand_elasticity(), 3)
    assert (e_s, e_d) == (0.06, 0.169)
    assert L.GAS_ELASTICITY_PAIRS["central"] == (e_s, e_d)
    y = L.lfl_year(2025)
    c = L.gas_feedback(y, "central")
    assert c["price_rise_frac"] == pytest.approx(c["dq_twh"] / ((e_s + e_d) * c["q_twh"]), rel=1e-12)
    assert (c["elasticity_supply"], c["elasticity_demand"]) == (e_s, e_d)
    assert c["q_twh"] == pytest.approx(L.EU_GAS_DEMAND_TWH + L.gb_gas_demand_twh()[2025])


def test_2_sensitivity_pair_is_krichene_world_long_run():
    """Sensitivity row B: Krichene's own world long-run pair, Table 2 VECM 1918-2004: 0.16 + 0.45 = 0.61."""
    s, d = _krichene_table2_long_run_pair()
    assert (s, d) == (0.16, 0.45)
    assert L.GAS_ELASTICITY_PAIRS["krichene_lr"] == (s, d)
    y = L.lfl_year(2025)
    k = L.gas_feedback(y, "krichene_lr")
    assert k["price_rise_frac"] == pytest.approx(k["dq_twh"] / ((s + d) * k["q_twh"]), rel=1e-12)


# ----------------------------------------------------------------------------- test 3 (direction, line-116 comment)


def test_3_larger_elasticity_smaller_reliable_britain_bill():
    """A larger elasticity gives a smaller gas-price rise, so a smaller Reliable Britain bill (a LARGER gap). The
    comment that said the opposite ("0.16 errs towards a bigger feedback (a larger gap)") is gone."""
    paired = sorted((r for r in L.GAS_FEEDBACK_RULES if r in L.GAS_ELASTICITY and r != "none"),
                    key=lambda r: L.GAS_ELASTICITY[r])
    assert len(paired) >= 2
    from dataclasses import replace
    tot = [_fleet(YEAR, replace(B.CENTRAL, gas_feedback=r))["total_gbp_m"] for r in paired]
    assert all(a > b for a, b in zip(tot, tot[1:])), list(zip(paired, tot))
    src = (ROOT / "src/gascf/fossil_like_for_like.py").read_text()
    flat = re.sub(r"\s+", " ", src.replace("#", " "))
    assert "bigger feedback (a larger gap)" not in flat
    assert "a bigger feedback (a smaller gap)" in flat or "bigger feedback makes the gap smaller" in flat


# ----------------------------------------------------------------------------- test 4 (finding 6, Cottam)


def test_4_cottam_mixed_closes_on_its_real_date_with_the_margin_test_stored():
    rows = json.loads((ROOT / "reference/fossil_closures.yaml").read_text())
    c = [r for r in rows if r["station"] == "Cottam"]
    assert len(c) == 1
    c = c[0]
    assert (c["reason"], c["fossil_britain_close"], c["abatement_needed"]) == ("mixed", "2019-09-30", None)
    assert c["actual_close"] == "2019-09-30"
    # stored as for Fiddler's Ferry: the test, its years and the sign in the note; inputs in work/
    assert "work/s37-cottam/margins.md" in c["note"] and "0144" in c["note"]
    m = json.loads((ROOT / "work/s37-cottam/cottam_margin.json").read_text())
    zones = [k for k in m if k.startswith("Cottam zone")]
    assert len(zones) == 3
    for z in zones:
        y18 = next(r for r in m[z]["years"] if r["year"] == 2018)
        assert y18["margin_before_filters_gbp_m"] < 0
        for k in ("lf", "lf_src", "p", "c", "fuel_gbp_mwh_e", "vom", "fixed_gbp_kw", "tnuos_gbp_kw", "tnuos_src"):
            assert k in y18, (z, k)
    # the method copy reproduces Fiddler's Ferry unit 1 as stored in the register (2016-18: -17, -16, -18 £m)
    ff = m["Fiddler's Ferry unit 1"]["years"]
    assert [round(r["margin_before_filters_gbp_m"]) for r in ff] == [-17, -16, -18]


# ----------------------------------------------------------------------------- test 5 (finding 5a and 5b labels)


def _all_declared() -> dict:
    import importlib
    from tools import figures_keys
    out = {}
    for name in figures_keys.MODULES:
        out.update(importlib.import_module(f"tools.figures_keys.{name}").DECLARED)
    return out


def test_5_no_label_says_collected_by_nobody():
    d = _all_declared()
    bad = [k for k, m in d.items() if "collected by nobody" in str(m.get("label", "")).lower()]
    assert not bad, bad
    for f in ("src/gascf/bills.py", "tools/figures_keys/core.py"):
        assert "collected by nobody" not in (ROOT / f).read_text(), f
    assert "carbon in the power price not collected as UK carbon tax (the rest)" in (ROOT / "src/gascf/bills.py").read_text()


def test_5b_headline_named_as_ruled():
    from tools.figures_keys import core
    lab = core.DECLARED["headline_2002_24_gbp_bn"]["label"]
    assert lab.startswith("Extra cost of net zero on electricity bills, paid by bill-payers"), lab
    assert "to Britain" not in lab


# ----------------------------------------------------------------------------- test 6 (finding 4, range)

STACK = "merit-order uplift (engine's own stack estimate)"


def test_6_stack_row_on_the_methods_page_and_feedback_rows_paired():
    assert STACK in B.METHOD_SWITCHES and STACK not in B.SWITCHES
    fb = [k for k in B.SWITCHES if k.startswith("gas-price feedback")]
    assert len(fb) == 1
    assert [s.gas_feedback for s in B.SWITCHES[fb[0]]] == ["krichene_lr"]
    for sets in B.SWITCHES.values():
        for s in sets:
            assert s.gas_feedback in ("central", "krichene_lr"), s.gas_feedback


def _toy_run() -> dict:
    """A one_at_a_time block with every registry row, each option moving 2002 by its own amount."""
    from dataclasses import fields
    run = json.loads(S36_RUN.read_text())
    ys = [str(y) for y in B.YEARS]
    cen = {y: run["gap"][y]["national_gbp_bn_real"] for y in ys}
    blocks = {}
    n = 0
    for blk, reg in (("ranked", B.switch_settings()), ("methods_page", B.METHOD_SWITCHES)):
        blocks[blk] = {}
        for lab, sets in reg.items():
            opts = []
            for s in sets:
                n += 1
                diff = {f.name: getattr(s, f.name) for f in fields(s) if getattr(s, f.name) != getattr(B.CENTRAL, f.name)}
                g = dict(cen)
                g["2002"] = cen["2002"] + (n if n % 2 else -n)
                opts.append({"settings": diff, "gap_real_bn": g, "lines_moved_gbp_m_nominal": {}})
            blocks[blk][lab] = opts
    run["one_at_a_time"] = blocks
    return run


def test_6_each_printed_range_end_carries_its_switch_name():
    from tools.figures_keys import range as R
    v = R.values(_toy_run())
    t = R.table(_toy_run())
    ranked = [r for r in t if r["block"] == "ranked"]
    lo = min(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    hi = max(ranked, key=lambda r: r["headline_2002_24_gbp_bn"])
    assert v["headline_low_end_switch"] == lo["switch"] and v["headline_high_end_switch"] == hi["switch"]
    txt = v["headline_range_text"]
    assert lo["switch"] in txt and hi["switch"] in txt
    assert f"£{v['headline_2002_24_low_gbp_bn']:.1f}bn" in txt and f"£{v['headline_2002_24_high_gbp_bn']:.1f}bn" in txt
    for k in ("headline_2002_24_low_gbp_bn", "headline_2002_24_high_gbp_bn"):
        assert "named" in R.DECLARED[k]["label"] or "switch" in R.DECLARED[k]["label"]


# ----------------------------------------------------------------------------- test 7 (sensitivity rows)

JUDGEMENT_ROWS = {"1C", "2B", "3B", "4", "5bB", "7B"}


def test_7_each_judgement_finding_has_a_named_row():
    from tools import figures_keys
    from tools.figures_keys import sens_0144 as S
    assert "sens_0144" in figures_keys.MODULES
    assert set(S.ROWS) == JUDGEMENT_ROWS
    for fid, row in S.ROWS.items():
        assert row["name"] and row["headline_key"] in S.DECLARED and row["change_key"] in S.DECLARED, fid
        assert S.DECLARED[row["headline_key"]]["units"].startswith("£bn")
    assert "partial whole-Britain view" in S.DECLARED[S.ROWS["5bB"]["headline_key"]]["label"]
    # v4-s39 (card [internal ticket]): finding 3's note now says it is superseded for 2021-23 by 0164 (M9 B)
    lab = S.DECLARED["note_uplift_2021_23_probably_low"]["label"]
    assert "probably low" in lab and "0164" in lab


def test_7_rows_reproduce_the_v4_s36_figures_from_the_released_files():
    """On the released v4-s36 run file the rows that exist there reproduce the sheet's measured or release figures:
    3B -11.268 (UCL row), 4 stack +24.322, 7B -9.203 (NZ10 line total), 5bB = - receipts - VAT - non-power gas
    (-37.943, from release keys; the sheet's round 2)."""
    from tools.figures_keys import sens_0144 as S
    run = json.loads(S36_RUN.read_text())
    figs = json.loads(S36_FIGS.read_text())["keys"]
    k = lambda n: figs[n]["value"]  # noqa: E731
    central = k("headline_2002_24_gbp_bn")
    rows = S.measure(run, only={"3B", "4", "5bB", "7B"})
    assert rows["3B"]["change_gbp_bn"] == pytest.approx(-11.268, abs=5e-4)
    assert rows["4"]["change_gbp_bn"] == pytest.approx(24.322, abs=5e-4)
    assert rows["7B"]["change_gbp_bn"] == pytest.approx(-k("wf_schemes_gbp_bn"), abs=1e-9)
    exp5b = -k("carbon_price_receipts_2002_24_gbp_bn") - k("wf_vat_gbp_bn") - k("npg_estimate_2002_24_central_gbp_bn")
    assert exp5b == pytest.approx(-37.943, abs=2e-3)      # the sheet summed the three parts rounded to £m
    assert rows["5bB"]["change_gbp_bn"] == pytest.approx(exp5b, abs=1e-9)
    for r in rows.values():
        assert r["headline_gbp_bn"] == pytest.approx(central + r["change_gbp_bn"], abs=1e-9)
