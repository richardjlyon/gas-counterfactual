"""Ticket 18 (0069, 0086, 0087): crisis-year merit-order uplift, UCL sensitivity. Under
`moe_crisis="ucl_stmoe"` the 2021-23 Shao uplift is scaled so its time-mean equals target B (0086):
UCL Table 4 (wind) + the engine's own Shao solar part (2.98 £/MWh per solar GW). Shao stays central.
O'Shea, Horne and Maslin (2025) preprint v1: Table 4 printed p.22 (PDF p.24); Table 5 printed p.25
(PDF p.27), carried, not run (0087)."""
import hashlib
from pathlib import Path

import pytest

from gascf import moe_crisis as MC

ROOT = Path(__file__).resolve().parents[1]


def test_ucl_sources_cite_printed_and_pdf_pages():
    d = MC.read()
    assert "printed p.22 (PDF p.24)" in d["stmoe_total_gbp_mwh"]["locator"]
    assert "Table 4" in d["stmoe_total_gbp_mwh"]["locator"]
    assert "printed p.25 (PDF p.27)" in d["ltmoe_gbp_mwh"]["locator"]
    assert "Table 5" in d["ltmoe_gbp_mwh"]["locator"]


def _fixture(tmp_path, **over):
    d = {**MC.read(), **over}
    p = tmp_path / "ucl.yaml"
    p.write_text(__import__("json").dumps(d))
    return p


@pytest.mark.parametrize("over", [{"status": "PENDING"}, {"pdf_sha256": None}, {"pdf_sha256": "0" * 64}])
def test_guard_fires_on_a_pending_or_unpinned_data_file(tmp_path, over):
    from gascf.pending import PendingSourceError
    with pytest.raises(PendingSourceError):
        MC.require_sourced(_fixture(tmp_path, **over))


def test_guard_passes_the_real_file_and_its_pdf_sha_matches_sha256sums():
    MC.require_sourced()
    sums = dict(reversed(l.split(None, 1)) for l in (ROOT / "data/raw/SHA256SUMS").read_text().splitlines()
                if l.strip() and not l.startswith("#"))
    pdf = "./s36/ucl-oshea/oshea-ucloe-preprint-290-v1.pdf"
    assert MC.read()["pdf_sha256"] == sums[pdf] == "d7fa85732a2b30a3f0fa3160401fa888b1d336a79f7d11a3b27655c3f9fd09a6"
    assert hashlib.sha256((ROOT / "data/raw" / pdf).read_bytes()).hexdigest() == sums[pdf]


def test_target_b_is_ucl_wind_plus_the_engines_shao_solar_part():
    # 0086 target B: UCL Table 4 (from the data file) + 2.98 £/MWh per solar GW (Shao Table 3, pooled)
    t4 = MC.read()["stmoe_total_gbp_mwh"]["values"]
    assert MC.target_gbp_mwh(2022, solar_gw=1.5) == pytest.approx(t4["2022"] + 2.98 * 1.5, abs=1e-9)
    assert MC.k(2022, shao_mean=15.93, solar_gw=1.5) == pytest.approx((56.48 + 4.47) / 15.93, abs=1e-9)
    assert MC.k(2020, shao_mean=15.0, solar_gw=1.5) == 1.0 == MC.k(2024, shao_mean=15.0, solar_gw=1.5)


def test_no_build_path_reads_table_5(tmp_path):
    # 0087: Table 5 (ltmoe) is carried, not run. Doubling it in a fixture changes nothing the build reads.
    d = MC.read()
    lt = {y: 2 * v for y, v in d["ltmoe_gbp_mwh"]["values"].items()}
    p = _fixture(tmp_path, ltmoe_gbp_mwh={**d["ltmoe_gbp_mwh"], "values": lt})
    for y in MC.CRISIS_YEARS:
        assert MC.target_gbp_mwh(y, 1.0, p) == MC.target_gbp_mwh(y, 1.0)
    # RB v1.1 M10 (0160; 0163 R10 (a), Richard Lyon 21 Oct 2026): Table 5 is read by one held sensitivity rule,
    # 'ucl_ltmoe' (bills.HELD_M10), and by nothing else. Card [internal ticket] narrowed this guard from "no source line
    # names ltmoe" (0087, before M10 was ruled) to: no central or range build reads it, and every line naming it
    # belongs to the M10 rule.
    from gascf import bills as B
    assert B.CENTRAL.moe_crisis != "ucl_ltmoe"
    assert all(s.moe_crisis != "ucl_ltmoe" for v in B.SWITCHES.values() for s in v)
    assert "ltmoe" not in (ROOT / "src/gascf/fossil_like_for_like.py").read_text()
    for f in ("bills.py", "moe_crisis.py"):
        for line in (ROOT / "src/gascf" / f).read_text().replace('"ltmoe_gbp_mwh" is carried', "").splitlines():
            if "ltmoe" in line:
                assert "ucl_ltmoe" in line or "M10" in line or line.lstrip().startswith("#"), (f, line)


def test_build_refuses_the_ucl_case_on_a_pending_data_file_before_any_output(tmp_path, monkeypatch):
    from gascf import bills as B
    from gascf.pending import PendingSourceError
    assert B.CENTRAL.moe_crisis == "m9_direct_mayon"     # v4-s39: 0164 addendum (M9 B); was "shao" to v4-s38
    monkeypatch.setattr(MC, "DATA", _fixture(tmp_path, status="PENDING"))
    MC.read.cache_clear()
    try:
        with pytest.raises(PendingSourceError):
            B.build(B.replace(B.CENTRAL, moe_crisis="ucl_stmoe"))
    finally:
        MC.read.cache_clear()


# ---- heavy (fleet_lfl / build): run under the heavy lock ----
def test_ucl_case_applied_mean_uplift_is_target_b_in_each_crisis_year():
    """Spec test 3: the applied time-mean uplift equals target B read from the data file, to 1e-6."""
    from gascf import bills as B
    for y in MC.CRISIS_YEARS:
        f = B.fleet_lfl(y, ic_basis="contracted", moe_crisis="ucl_stmoe")
        want = MC.read()["stmoe_total_gbp_mwh"]["values"][str(y)] + 2.98 * f["moe"]["solar_gw_mean"]
        assert f["moe"]["applied_mean_gbp_mwh"] == pytest.approx(want, abs=1e-6), y


@pytest.fixture(scope="module")
def central():
    from gascf import bills as B
    return B.build()


@pytest.fixture(scope="module")
def shao():
    """Shao in every month: the v4-s38 central rule (card [internal ticket]; central is M9 B from v4-s39, 0164)."""
    from gascf import bills as B
    return B.build(B.replace(B.CENTRAL, moe_crisis="shao"))


@pytest.fixture(scope="module")
def ucl():
    from gascf import bills as B
    return B.build(B.replace(B.CENTRAL, moe_crisis="ucl_stmoe"))


def _per_hh(b, y):
    return b[y]["totals"]["gap_per_hh_real"]


def test_only_2021_23_move_each_by_more_than_one_pound_a_household(central, ucl):
    """Spec test 4: outside 2021-23 the UCL case equals central to 1e-9 (gap, bills, fleet uplift);
    each of 2021, 2022 and 2023 moves by more than £1/household (fails if the switch is a no-op)."""
    from gascf import bills as B
    for y in B.YEARS:
        if y in MC.CRISIS_YEARS:
            assert abs(_per_hh(ucl, y) - _per_hh(central, y)) > 1.0, y
            continue
        assert ucl[y]["totals"] == pytest.approx(central[y]["totals"], abs=1e-9), y
        for k in ("total_gbp_m", "moe_gbp_m", "moe_kept_gbp_m"):
            assert ucl[y]["fleet"][k] == pytest.approx(central[y]["fleet"][k], abs=1e-9), (y, k)


def test_ucl_case_is_a_methods_page_switch_not_in_the_range():
    from gascf import bills as B
    name = "merit-order uplift 2021-23: UCL short-run (preprint)"
    assert [s.moe_crisis for s in B.METHOD_SWITCHES[name]] == ["ucl_stmoe"]
    assert all(s.moe_crisis == B.CENTRAL.moe_crisis for v in B.SWITCHES.values() for s in v)


def test_run_file_block_is_registered_through_the_hook():
    import importlib
    from gascf import export_v4 as X
    assert "gascf.moe_crisis_block" in X.BLOCK_MODULES
    importlib.import_module("gascf.moe_crisis_block")
    assert "moe_crisis" in X._BLOCKS


def test_both_gaps_printed_in_the_run_file_block(central, shao, ucl):
    """Spec test 5: `moe_crisis.years[y]` has central, shao, ucl_stmoe for 2021-23. v4-s39 (card [internal ticket];
    0164 addendum): central = the build (M9 B), shao = Shao in every month, difference = ucl_stmoe - central
    (the UCL row re-based on the new central). (Block, not gap[y]: the hook may not replace `gap`.)"""
    from gascf import moe_crisis_block as MB
    from gascf import bills as B
    b = MB.block(central)
    assert b["central_rule"] == B.CENTRAL.moe_crisis == "m9_direct_mayon"
    assert sorted(b["years"]) == ["2021", "2022", "2023"]
    for y in MC.CRISIS_YEARS:
        r = b["years"][str(y)]
        assert r["central"]["per_household_real"] == pytest.approx(central[y]["totals"]["gap_per_hh_real"], abs=1e-9)
        assert r["central"]["national_gbp_bn_real"] == pytest.approx(central[y]["totals"]["gap_real_bn"], abs=1e-12)
        assert r["shao"]["national_gbp_m_nominal"] == pytest.approx(shao[y]["totals"]["gap_gbp_m"], abs=1e-9)
        assert r["ucl_stmoe"]["national_gbp_m_nominal"] == pytest.approx(ucl[y]["totals"]["gap_gbp_m"], abs=1e-9)
        assert abs(r["shao"]["national_gbp_m_nominal"] - r["central"]["national_gbp_m_nominal"]) > 1.0, y
        for k in ("per_household_real", "national_gbp_bn_real", "national_gbp_m_nominal"):
            assert r["difference"][k] == pytest.approx(r["ucl_stmoe"][k] - r["central"][k], abs=1e-9)
    assert b["peer_reviewed"] is False and b["source_id"] == MC.read()["source_id"]


def test_ucl_gap_is_smaller_than_the_shao_gap_each_crisis_year(shao, ucl):
    """Spec test 6: a larger uplift raises Reliable Britain's bill, so the gap falls (against Shao in every
    month; from v4-s39 the central is M9 B, card [internal ticket])."""
    for y in MC.CRISIS_YEARS:
        assert _per_hh(ucl, y) < _per_hh(shao, y), y


def test_central_unchanged_and_applied_uplift_is_shao_every_year(central):
    """Spec test 2: with moe_crisis='shao' the fleet uplift (moe, moe_kept) equals the build before this
    ticket (tests/fixtures/moe_crisis_central_pre18.json, from B.build() on wt/B before the scaling was
    wired) to 1e-9, and the applied mean uplift is Shao's in every year.
    B-merge re-pin (17 Oct 2026, fix 2), re-pinned again at the A2 merge: the gap is pinned to the A2 build
    (tests/fixtures/moe_crisis_central_s36_merged.json). It moved from the pre18 file through A1 tickets (09
    B4, every year; 10 F1, 2012-15 and 2018-25; 03 0088, NZ6 2017-24) and now the A2 group-A tickets:
    12_0044 = -(nz8_on_the_road + nz8_lec_exempt), the CCL counted only above its 2001 rate less the capped
    LEC exemption (no VAT, CCL carries none; 2002 -620.99, matching the ic metered test's NZ8 move), and
    26_0097 = the NZ2/NZ10 on-the-road netting incl. its VAT (the remainder: the only A2 central code is 12
    and 26, so with 12 taken out exactly this is the whole 0097 gap effect). The parts sum to the move. B, C
    and D move no central line. Re-pinned 19 Oct 2026 (card [internal ticket]): part 0110_1_8, decision 0110 item 1.8 (the
    actual system's own firm test on the same basis as RB's), 0 before 2016, from work/s36/repin_0110_1_8.py.
    Re-pinned 20 Oct 2026 (card [internal ticket]): part 0133, decision 0133 (Richard Lyon, "a": the margin over the
    2027/28 Base Case peak), every year, from work/s36/repin_0133.py, which refuses if the uplift moves.
    Re-pinned 20 Oct 2026 (card [internal ticket]): part 0144, decision 0144 (Richard Lyon, "Yes, take all the
    recommendations"; v4-s37), every year, from work/s37/repin_0144.py. 1A adds the uplift on the extra running
    (fleet extra_moe_gbp_m); the uplift on the actual output is unchanged, and that is what is pinned here."""
    import json
    pre = json.loads((ROOT / "tests/fixtures/moe_crisis_central_pre18.json").read_text())["values"]
    # Re-pinned 22 Oct 2026 (card [internal ticket]): part s39, the v4-s39 rulings (0159-0170, C-005/C-008/C-009), from
    # work/[internal ticket]/repin_moe_0069.py (the build on this seam). The uplift on actual output is unchanged except in
    # 2021-23 (M9 B, 0164: scaled, not Shao) and 2020 (coal hours 0166 from 1 Jul 2020 move part of the actual
    # fossil output off the existing blocks, +32.2 £m measured by the script).
    # Re-pinned 23 Oct 2026 (card [internal ticket]): part s40, v4-s40 item 2 (decision 0175, kept coal's M3 margin on the
    # road's own revenue), from work/[internal ticket]/repin_s40.py on the M4 at c48c477: on this fixture register item 2
    # moves 2016-20 and 2023-25, item 1 moves nothing, and the v4-s39 readings reproduce the s39 pin exactly. The
    # uplift on actual output does not move (the assertions below are unchanged).
    # Re-pinned 24 Oct 2026 (card [internal ticket]): part s42, the seven input fixes of v4-s42 (decision 0195), from
    # work/[internal ticket]/repin_s42.py on this seam (the v4-s42 build). By year: 2002-06 A2 (NI CCGT; 2002-05 through the
    # unchanged nearest-year fill), 2010-11 A1, A5 (2011) and D1, 2021-25 A3, 2025 A4; C1 moves no gap. Attribution
    # from the single-fix candidate trees ([internal ticket]) on the M4. The uplift on actual output does not move.
    # Re-pinned 24 Oct 2026 (card [internal ticket]): part s43, decision 0197 (each year's own NI station list), 2002-05
    # only, from work/[internal ticket]/repin_s43.py on this seam (fails at 59512c8, passes at a7e5ee4).
    pin = json.loads((ROOT / "tests/fixtures/moe_crisis_central_s43.json").read_text())
    from gascf import bills as B
    for y in B.YEARS:
        gap0, moe, moe_k = pre[str(y)]
        parts = pin["moves_from_pre18_gbp_m"][str(y)]
        assert sorted(parts) == ["0110_1_8", "0133", "0144", "03_0088", "09_B4", "10_F1", "12_0044", "26_0097",
                                 "s39", "s40", "s42", "s43"], y
        assert pin["gap_gbp_m"][str(y)] - gap0 == pytest.approx(sum(parts.values()), abs=1e-5), y
        assert central[y]["totals"]["gap_gbp_m"] == pytest.approx(pin["gap_gbp_m"][str(y)], abs=1e-9), y
        f = central[y]["fleet"]
        m = central[y]["fleet"]["moe"]
        if y in (2020, 2021, 2022, 2023):
            continue
        # v4-s42: in the fixes' years (A2 2002-06, A1/A5 2010-11, A3 2024, A3/A4 2025) the uplift on actual and on
        # kept output moves with the fleet; those years compare with the v4-s42 build (work/[internal ticket]/
        # repin_moe_s42.py, fixture key s42_uplift_moves), every other year with the pre-18 fixture as before.
        if str(y) in pin["s43_uplift_moves"]:
            moe, moe_k = (pin["s43_uplift_moves"][str(y)][k] for k in ("moe_actual_gbp_m", "moe_kept_gbp_m"))
        assert f["moe_gbp_m"] - f["extra_moe_gbp_m"] == pytest.approx(moe, abs=1e-9), y     # actual output (0144 1A)
        assert central[y]["fleet"]["moe_kept_gbp_m"] == pytest.approx(moe_k, abs=1e-9), y
        assert m["applied_mean_gbp_mwh"] == pytest.approx(max(0.0, m["shao_mean_gbp_mwh"]), abs=1e-9), y


def test_ucl_move_is_linear_in_k_against_the_no_uplift_pass_through(shao, ucl):
    """Spec test 7, on the s36 build: Δgap(UCL) = (gap_central − gap_no_uplift) × (k − 1), within ±2% per
    year (the spec item's own method; its £36.57bn / £48.28bn are s35 arithmetic, reported, not pinned)."""
    from gascf import bills as B
    none = B.build(B.replace(B.CENTRAL, moe="none"))
    # k is UCL's scale on Shao's uplift, so the move is measured from Shao in every month (card [internal ticket])
    blk = __import__("gascf.moe_crisis_block", fromlist=["block"]).block(shao)
    for y in MC.CRISIS_YEARS:
        k = blk["years"][str(y)]["k"]
        want = (shao[y]["totals"]["gap_gbp_m"] - none[y]["totals"]["gap_gbp_m"]) * (k - 1)
        got = ucl[y]["totals"]["gap_gbp_m"] - shao[y]["totals"]["gap_gbp_m"]
        assert got == pytest.approx(want, rel=0.02), y
