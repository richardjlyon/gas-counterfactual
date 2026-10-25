"""Card [internal ticket]: the Annex E change log (reference/change_log_v4_s39.json, read into annex_e_change_log) carries the
v4-s43 step, decision 0197 (each year's own NI station list for 2002-05), marked release v4-s43, so the v4-s43 steps
add up to the v4-s43 cut run file's headline less v4-s42's released headline (out/figures/v4-s42.json), and Annex E
prints nothing unexplained for the release it ships with. The text-only fixes in v4-s43 move no value and have no step."""
import json
from pathlib import Path

from gascf import export_v4 as X
from gascf.figures import to_2024

ROOT = Path(__file__).resolve().parents[1]
LOG = json.loads((ROOT / "reference/change_log_v4_s39.json").read_text())
S43 = [s for s in LOG["steps"] if s.get("release") == "v4-s43"]


def _cut_run() -> dict:
    p = [q for q in sorted(Path(X.OUT).glob("*.json"))
         if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    assert p, f"no out/v4 run file written by engine {X.ENGINE_VERSION}"
    return json.loads(p[-1].read_text())


def test_one_measured_v4_s43_step_for_decision_0197():
    assert len(S43) == 1
    s = S43[0]
    assert "0197" in s["decision"] and "each year's own list" in s["decision"]
    assert s["headline_change_gbp_bn"] is not None and s["measured_on"].strip()
    assert s["status"] == "measured"


def test_v4_s43_steps_add_up_to_the_cut_headline_less_v4_s42():
    v42 = json.loads((ROOT / "out/figures/v4-s42.json").read_text())["keys"]["headline_2002_24_gbp_bn"]["value"]
    r = _cut_run()
    headline = sum(to_2024(r["gap"][str(y)]["national_gbp_bn_real"], r) for y in range(2002, 2025))
    assert abs(headline - v42 - sum(s["headline_change_gbp_bn"] for s in S43)) < 1e-6
