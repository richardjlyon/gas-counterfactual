"""Card [internal ticket]: the Annex E change log (reference/change_log_v4_s39.json, read into annex_e_change_log) is complete
at the cut: every step measured or named as moving no number, none pending, each with where it was measured, and the
steps add up to the cut run file's headline less v4-s37's (the release card's stop rule), to £0.01bn (the steps are
measured to 3 dp on the release-candidate builds)."""
import json
from pathlib import Path

from gascf.figures import to_2024

ROOT = Path(__file__).resolve().parents[1]
LOG = json.loads((ROOT / "reference/change_log_v4_s39.json").read_text())
RUN = ROOT / "out/v4/2026-10-22-s39.json"


def test_no_step_is_pending_and_each_says_where_it_was_measured():
    for s in LOG["steps"]:
        assert s["headline_change_gbp_bn"] is not None, s["item"]
        assert "pending" not in s["status"], s["item"]
        assert s["measured_on"].strip(), s["item"]


def test_the_v4_s39_rulings_each_have_a_step():
    items = " | ".join(s["item"] for s in LOG["steps"]).lower()
    for want in ("m2", "m6", "m9 b", "0166", "m7", "m8", "generators' share", "ro mutualisation", "c-009"):
        assert want in items, want


def test_steps_add_up_to_the_cut_headline():
    r = json.loads(RUN.read_text())
    headline = sum(to_2024(r["gap"][str(y)]["national_gbp_bn_real"], r) for y in range(2002, 2025))
    # v4-s40 (card [internal ticket]) appends its own steps, marked release v4-s40: this test keeps to the v4-s39 steps
    steps = sum(s["headline_change_gbp_bn"] for s in LOG["steps"] if s.get("release", "v4-s39") == "v4-s39")
    assert abs(headline - LOG["baseline"]["headline_2002_24_gbp_bn"] - steps) < 0.01
