"""Card [internal ticket]: the Annex E change log (reference/change_log_v4_s39.json, read into annex_e_change_log) carries the
v4-s40 steps (decision 0175, step-3 items 1, 2 and 9), each measured and saying where, and the steps add up to the
v4-s40 cut run file's headline less v4-s37's, to £0.01bn: Annex E prints nothing unexplained for the release it ships
with."""
import json
from pathlib import Path

from gascf import export_v4 as X
from gascf.figures import to_2024

ROOT = Path(__file__).resolve().parents[1]
LOG = json.loads((ROOT / "reference/change_log_v4_s39.json").read_text())


def _cut_run() -> dict:
    p = [q for q in sorted(Path(X.OUT).glob("*.json"))
         if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    assert p, f"no out/v4 run file written by engine {X.ENGINE_VERSION}"
    return json.loads(p[-1].read_text())


def test_the_v4_s40_items_each_have_a_measured_step():
    s40 = [s for s in LOG["steps"] if "0175" in s["decision"]]
    items = " | ".join(s["item"] for s in s40).lower()
    for want in ("item 1", "item 2", "item 9"):
        assert want in items, want
    for s in s40:
        assert s["headline_change_gbp_bn"] is not None and s["measured_on"].strip(), s["item"]


def test_steps_add_up_to_the_v4_s40_cut_headline():
    r = _cut_run()
    headline = sum(to_2024(r["gap"][str(y)]["national_gbp_bn_real"], r) for y in range(2002, 2025))
    steps = sum(s["headline_change_gbp_bn"] for s in LOG["steps"])
    assert abs(headline - LOG["baseline"]["headline_2002_24_gbp_bn"] - steps) < 0.01
