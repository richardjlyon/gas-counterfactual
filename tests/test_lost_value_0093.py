"""Lost value in the release (0080-0085), quoted for 2002-24 with 2025 apart (0093), with 0081 re-ruled
as option 2 (non-household central -0.520). Literals on v4-s35 inputs (2024 prices, £bn).

Card [internal ticket] item 5 (21 Oct 2026): the literals first came from reports-programme
b-items-calc/l0081_alternatives.json, whose price rise was GAP / (TOTAL_GO + S1_TOTAL); TOTAL_GO already holds the
same-in-both block, so that counted it twice. The price rise is now the gap over the whole bill counted once (0082),
and the literals are re-pinned from work/v1.1-lost-value/before_after.py, which sums the bill lines itself (old value
in each comment). tests/test_v11_lost_value_once.py pins the same on the released v4-s37 run file."""
import json
from pathlib import Path

import pytest

from gascf import lost_value as lv

S35 = Path(__file__).resolve().parents[1] / "out/v4/2026-10-14-s35.json"


def test_nonhousehold_central_elasticity_is_labandeira_t3_electricity_lt_simple_avg():
    assert lv.E_HOUSEHOLDS == -0.607
    assert lv.E_NON_HOUSEHOLDS == -0.520
    assert (lv.E_LOW, lv.E_HIGH) == (-0.203, -0.677)


@pytest.fixture(scope="module")
def s35():
    return lv.estimate(json.loads(S35.read_text()))


def test_quoted_central_2002_24_on_s35_inputs(s35):
    assert s35["quoted"]["central"]["2002-2024"] == pytest.approx(12.515, abs=0.005)     # was 9.831 (block twice)


def test_quoted_central_2025_alone_on_s35_inputs(s35):
    assert s35["quoted"]["central"]["2025"] == pytest.approx(1.555, abs=0.005)           # was 1.232


def test_straight_line_central_2002_24_on_s35_inputs(s35):
    assert s35["straight_line"]["central"]["2002-2024"] == pytest.approx(14.505, abs=0.005)   # was 11.012


def test_straight_line_over_quoted_rounds_to_16_percent_on_s35_inputs(s35):
    # 0085 wording fix said about 12% (block counted twice); with the bill counted once it is 15.9% on v4-s35
    # inputs (12.9% on v4-s37's): the paper's "about 12%" must be re-read from the new release
    assert round(100 * s35["straight_line_over_quoted"]) == 16


def test_range_on_current_bounds_on_s35_inputs(s35):
    # the journal range change is dropped (0081 citation ruling): bounds -0.203 / -0.677
    assert s35["quoted"]["low"]["2002-2024"] == pytest.approx(4.46, abs=0.01)           # was 3.53
    assert s35["quoted"]["high"]["2002-2024"] == pytest.approx(15.57, abs=0.01)         # was 12.19


def test_no_2002_25_key(s35):
    # 0098: no 2002-25 cumulative figure
    assert all("2002-2025" not in s35[m][c] for m in ("quoted", "straight_line") for c in s35[m])


def test_lost_value_keys_cite_rscas_2016_25_working_paper_only(s35):
    # only the Labandeira values cite RSCAS 2016/25; the journal version never appears
    src = s35["sources"]["elasticities"]
    for k in ("non_households_central", "low", "high"):
        assert "RSCAS 2016/25" in src[k]["citation"], k
    assert src["non_households_central"]["locator"] == "Table 3, Good block, Electricity LT simple average, PDF p.15"
    assert src["low"]["locator"] == "Table 3, Good block, Electricity ST simple average, PDF p.15"
    assert src["high"]["locator"] == "Table 4, Electricity LT meta-regression (GLS), PDF p.16"
    assert src["non_households_central"]["label"] == (
        "electricity, all consumers, long-run average (Labandeira et al. 2016, Table 3)")
    assert "Energy Policy" not in json.dumps(s35)
    assert "industrial" not in json.dumps(s35).lower()
    assert s35["label"].startswith("estimate")


def test_household_elasticity_cites_pellini_2021_table_4(s35):
    h = s35["sources"]["elasticities"]["households"]
    assert h["value"] == -0.607
    assert "Pellini (2021)" in h["citation"] and "Energy Economics 101" in h["citation"]
    assert h["locator"] == "Table 4, UK long-run residential [-0.703, -0.562], PDF p.15 (accepted version)"
    assert h["register"] == "CR-S018"
    assert "RSCAS" not in h["citation"] and "Labandeira" not in h["citation"]


def test_desnz_1920_is_the_s36_copy_with_its_registered_sha256():
    """WORKERS §7 (31): the file is staged once, at data/raw/s36/desnz/ (ticket 01); no second copy."""
    import hashlib
    root = Path(__file__).resolve().parents[1]
    assert lv.DESNZ_1920 == root / "data/raw/s36/desnz/Electricity_since_1920.xlsx"
    want = "c95cc17e446f76cd4333421be3e2e537fbaf81073c5795385d70a9ae7bdde8de"
    assert hashlib.sha256(lv.DESNZ_1920.read_bytes()).hexdigest() == want
    assert f"{want}  ./s36/desnz/Electricity_since_1920.xlsx" in (root / "data/raw/SHA256SUMS").read_text()
    assert not (root / "data/raw/desnz/Electricity_since_1920.xlsx").exists()


def test_first_draft_reproduced_at_0607_for_all_users():
    """Spec test 2: ε = −0.607 for every user, straight line, 2002-25 as in dwl.py's first draft, with the bill counted
    once (item 5): 18.02 (low 6.03, high 20.10); the first draft's 13.69 (4.58, 15.27) counted the same-in-both block
    twice. A port check only; no 2002-25 key is exported (0098)."""
    run = json.loads(S35.read_text())
    yrs = range(2002, 2026)
    assert lv.total_bn(run, -0.607, "straight_line", yrs) == pytest.approx(18.019, abs=0.005)
    assert lv.total_bn(run, -0.203, "straight_line", yrs) == pytest.approx(6.026, abs=0.005)
    assert lv.total_bn(run, -0.677, "straight_line", yrs) == pytest.approx(20.097, abs=0.005)


def test_actual_anchor_ratio_equals_numerical_integration():
    """Spec test 3: for r = 0.3424, ε = −0.5426 the actual-anchor ratio equals direct integration of
    A·P^ε (demand anchored on actual demand at the higher price) to 1e-9: 0.0800770."""
    r, e = 0.3424, -0.5426
    p1 = 1 + r                                   # actual price ÷ counterfactual price
    q = lambda p: (p / p1) ** e                 # demand, actual = 1 at p1 # noqa: E731
    n = 200000
    h = (p1 - 1) / n
    area = sum(q(1 + (i + 0.5) * h) for i in range(n)) * h       # consumer surplus lost between 1 and p1
    gap = r * 1.0                                 # GAP = (p1 − 1) × actual demand
    dwl = (area - gap) / gap
    assert lv._ce_actual(e, r) == pytest.approx(dwl, abs=1e-9)
    assert lv._ce_actual(e, r) == pytest.approx(0.0800770, abs=5e-8)


def test_both_methods_tend_to_half_e_r_as_r_goes_to_zero():
    e, r = -0.55, 1e-6
    assert lv._ce_actual(e, r) / r == pytest.approx(0.5 * abs(e), rel=1e-4)
    assert lv._straight(e, r) / r == pytest.approx(0.5 * abs(e), rel=1e-12)


def test_household_share_has_every_release_year():
    """Spec test 4 (the header and sha256 checks are above and in household_share())."""
    s = lv.household_share()
    assert all(y in s and 0 < s[y] < 1 for y in range(2002, 2026))


import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import figures as F  # noqa: E402

LV_KEYS = {  # placeholder → rb.lost_value name (figures-keys.md §1, derived)
    "lost_value_2002_24_central_gbp_bn": ("quoted", "central", "2002-2024"),
    "lost_value_2002_24_low_gbp_bn": ("quoted", "low", "2002-2024"),
    "lost_value_2002_24_high_gbp_bn": ("quoted", "high", "2002-2024"),
    "lost_value_2025p_central_gbp_bn": ("quoted", "central", "2025"),
    "lost_value_2025p_low_gbp_bn": ("quoted", "low", "2025"),
    "lost_value_2025p_high_gbp_bn": ("quoted", "high", "2025"),
}


@pytest.fixture(scope="module")
def built():
    return F.generate(json.loads(S35.read_text()))


def test_figures_keys_carry_the_release_lost_value(s35, built):
    for k, (m, c, p) in LV_KEYS.items():
        e = built["keys"][k]
        assert e["value"] == s35[m][c][p], k
        assert e["meta"]["mapped_name"] == f"rb.lost_value.{m}.{c}.{p}"
    for c in ("low", "central", "high"):
        for p in ("2002-2024", "2025"):
            assert built["keys"][f"rb.lost_value.straight_line.{c}.{p}"]["value"] == s35["straight_line"][c][p]
    assert built["keys"]["lost_value_straight_line_over_quoted_pct"]["value"] == pytest.approx(
        100 * s35["straight_line_over_quoted"], abs=1e-12)
    assert not any("2002-2025" in k or "2002_25" in k for k in built["keys"] if "lost_value" in k)


def test_every_lost_value_key_cites_rscas_working_paper_with_locators_and_sha256(built):
    lab_sha = "afda2b3885ffd1022b03ba91fbe6d08ab5b058aa22a684453bca6aaa926d4e63"   # data/raw/SHA256SUMS
    for k, e in built["keys"].items():
        if e["meta"].get("ticket") != "31":
            continue
        el = e["meta"]["sources"]["elasticities"]
        assert el["citation"] == "Labandeira, Labeaga and López-Otero (2016), RSCAS 2016/25 working paper", k
        assert el["file_sha256"] == lab_sha, k
        assert el["locators"]["-0.520"] == ("Table 3, Good block, Electricity LT simple average, printed p.7, PDF p.15; "
                                           "electricity, all consumers, long-run average (Labandeira et al. 2016, Table 3)")
        assert el["locators"]["-0.203"] == "Table 3, Good block, Electricity ST simple average, PDF p.15"
        assert el["locators"]["-0.677"] == "Table 4, Electricity LT meta-regression (GLS), printed p.8, PDF p.16"
        h = e["meta"]["sources"]["households"]
        assert "Pellini (2021)" in h["citation"] and h["register"] == "CR-S018"
        text = json.dumps(e["meta"]).lower()
        assert "industrial" not in text and "energy policy" not in text and "-0.508" not in text, k


def test_gap_and_bill_lines_unchanged_with_step_on():
    """Spec test 5 (separation): the release step reads the frozen run file and writes only figures.json;
    the run's gap and bill lines are byte-identical with the step on or off, and no headline key moves."""
    import importlib
    raw = S35.read_bytes()
    run = json.loads(raw)
    mods_off = [importlib.import_module(f"tools.figures_keys.{m}") for m in ("core", "ucl_period")]
    off = F.generate(run, modules=mods_off)
    on = F.generate(run)
    assert json.dumps(run, sort_keys=True) == json.dumps(json.loads(raw), sort_keys=True)
    for k, e in off["keys"].items():
        assert on["keys"][k]["value"] == e["value"], k


def test_by_year_reconciles_with_the_quoted_totals(s35, built):
    by = built["keys"]["rb.lost_value.by_year"]["value"]
    assert sorted(by) == [str(y) for y in range(2002, 2026)]
    s = lv.household_share()
    for y, row in by.items():
        assert row["s"] == s[int(y)]
        assert row["eps_central"] == pytest.approx(s[int(y)] * -0.607 + (1 - s[int(y)]) * -0.520, abs=1e-15)
    assert sum(by[str(y)]["quoted_central_gbp_bn"] for y in range(2002, 2025)) == pytest.approx(
        s35["quoted"]["central"]["2002-2024"], abs=1e-12)
    assert sum(by[str(y)]["straight_line_central_gbp_bn"] for y in range(2002, 2025)) == pytest.approx(
        s35["straight_line"]["central"]["2002-2024"], abs=1e-12)


ELASTICITY_CENTRAL_LABEL = "average elasticity across households and non-households, weighted by each year's gap, 2002-24"


def test_elasticity_central_is_the_gap_weighted_mean_2002_24(built):
    """EIC ruling 17 Oct 2026 (labelling only): rb.lost_value.elasticity_central is
    sum eps(y) * GAP(y) / sum GAP(y) over 2002-24 (GAP in real terms, as the quoted total and l0081's eps_gap_weighted);
    -0.5510 on v4-s35 inputs; the exact label."""
    e = built["keys"]["lost_value_elasticity_central"]
    assert e["value"] == pytest.approx(-0.5510, abs=0.0005)
    assert e["meta"]["label"] == ELASTICITY_CENTRAL_LABEL
    assert e["meta"]["mapped_name"] == "rb.lost_value.elasticity_central"
    assert e["meta"]["period"] == "2002-2024"


NON_HOUSEHOLD_ONLY = ("The Labandeira all-consumers long-run average is used here for the non-household share of use only; "
                      "households use Pellini (2021).")


def test_non_household_use_only_sentence_in_the_elasticity_metadata_and_every_lost_value_note(built):
    """EIC ruling 17 Oct 2026 (0085): -0.520 (Labandeira) applies to the non-household share only; households -0.607 (Pellini 2021)."""
    assert NON_HOUSEHOLD_ONLY in lv.SOURCE_ELASTICITIES["non_households_central"]["note"]
    lv_keys = [k for k, e in built["keys"].items()
               if "lost_value" in k or e["meta"].get("mapped_name", "").startswith("rb.lost_value.")]
    assert len(lv_keys) == 15            # 6 quoted, 6 straight line, by_year, over_quoted, elasticity_central
    for k in lv_keys:
        assert NON_HOUSEHOLD_ONLY in built["keys"][k]["meta"]["sources"]["note"], k
