"""Ticket 30: figures.json key `gap_ucl_period` (0103): RB's gap on RB's method over UCL's 2010-23.

Seam: `tools.figures.generate(run)`. Input: the v4-s35 run file (indicative; re-pinned at the s36 release run)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gascf import figures as GF  # noqa: E402
from tools import figures as F  # noqa: E402

S35 = ROOT / "out/v4/2026-10-14-s35.json"


@pytest.fixture(scope="module")
def run():
    return json.loads(S35.read_text())


def test_gap_ucl_period_is_sum_of_gap_2010_23_same_run(run):
    want = GF.to_2024(sum(run["gap"][str(y)]["national_gbp_bn_real"] for y in range(2010, 2024)), run)
    assert F.generate(run)["keys"]["gap_ucl_period"]["value"] == pytest.approx(want, rel=0, abs=1e-9)


@pytest.mark.parametrize("year", ["2009", "2024", "2025"])
def test_years_outside_2010_23_never_enter(run, year):
    base = F.generate(run)["keys"]["gap_ucl_period"]["value"]
    bumped = json.loads(json.dumps(run))
    bumped["gap"][year]["national_gbp_bn_real"] += 50.0
    assert F.generate(bumped)["keys"]["gap_ucl_period"]["value"] == base


def test_metadata_period_basis_locator_and_note(run):
    m = F.generate(run)["keys"]["gap_ucl_period"]["meta"]
    assert (m["period_start"], m["period_end"], m["year_basis"]) == (2010, 2023, "calendar")
    assert m["price_base"] == "2024 £ (CPIH L522)"
    c = m["compare_to"]
    assert "From 2010 to 2023, wind power delivered a net benefit of £104.3 billion" in c["quote"]
    assert c["locator"] == "abstract, PDF p.1, src/ucl-oshea/o.txt line 53"
    assert c["pdf_sha256"] == "d7fa85732a2b30a3f0fa3160401fa888b1d336a79f7d11a3b27655c3f9fd09a6"
    assert m["note"] == ("UCL's figure is wind-only, on a Europe-wide gas premise. There is no run on that premise; "
                         "this key is RB's gap on RB's method over UCL's period only.")
    assert m["print"] is True


def test_s35_scale_reference(run):
    """Acceptance check (indicative only, pre-s36 lines): £137.47bn on v4-s35; re-pinned at the s36 release
    run (35) from the build, never loosened."""
    assert F.generate(run)["keys"]["gap_ucl_period"]["value"] == pytest.approx(137.468, abs=5e-4)


# ---- R37 (a), decision 0164 (Richard Lyon, 21 Oct 2026: "Agree."): §3.3 compares RB and UCL over 2010-23, both in
# money of the day. One new key: RB's gap over 2010-23 in cash, the sum of the run's nominal gap, never deflated.

def test_r37_cash_key_is_sum_of_nominal_gap_2010_23(run):
    want = sum(run["gap"][str(y)]["national_gbp_m_nominal"] for y in range(2010, 2024)) / 1000.0
    assert F.generate(run)["keys"]["gap_ucl_period_cash"]["value"] == pytest.approx(want, rel=0, abs=1e-9)


def test_r37_s35_cash_reference(run):
    """Independent of generate(): the v4-s35 file's nominal 2010-23 sum, read by hand on 22 Oct 2026, £112.439bn."""
    assert F.generate(run)["keys"]["gap_ucl_period_cash"]["value"] == pytest.approx(112.439, abs=5e-4)


@pytest.mark.parametrize("year", ["2009", "2024", "2025"])
def test_r37_years_outside_2010_23_never_enter(run, year):
    base = F.generate(run)["keys"]["gap_ucl_period_cash"]["value"]
    bumped = json.loads(json.dumps(run))
    bumped["gap"][year]["national_gbp_m_nominal"] += 50_000.0
    assert F.generate(bumped)["keys"]["gap_ucl_period_cash"]["value"] == base


def test_r37_real_gap_does_not_reach_the_cash_key(run):
    base = F.generate(run)["keys"]["gap_ucl_period_cash"]["value"]
    bumped = json.loads(json.dumps(run))
    bumped["gap"]["2015"]["national_gbp_bn_real"] += 50.0
    assert F.generate(bumped)["keys"]["gap_ucl_period_cash"]["value"] == base


def test_r37_metadata_says_cash_and_ucl_basis_inferred(run):
    m = F.generate(run)["keys"]["gap_ucl_period_cash"]["meta"]
    assert (m["period_start"], m["period_end"], m["year_basis"]) == (2010, 2023, "calendar")
    assert m["units"] == "£bn, money of the day (cash)"
    assert m["price_base"] == "cash (money of the day)"
    assert m["print"] is True and m["basis"] == "modelled"
    assert "UCL gives no price basis" in m["note"] and "inferred from its inputs" in m["note"]
    assert "0164" in m["ruling"] and "R37" in m["ruling"]

