"""Card [internal ticket]: the Annex E change log (reference/change_log_v4_s39.json, read into annex_e_change_log) carries the
v4-s42 steps, the seven input-audit fixes of decision 0195 (A1, A2, A3, A4, A5, C1, D1 basis (i)), each measured alone
against v4-s41 on the unsealed candidate (card [internal ticket]) and marked release v4-s42, plus the measured interaction of
the seven together; so the v4-s42 steps add up to the v4-s42 cut run file's headline less v4-s41's released headline
(out/figures/v4-s41.json), and Annex E prints nothing unexplained for the release it ships with."""
import json
from pathlib import Path

from gascf import export_v4 as X
from gascf.figures import to_2024

ROOT = Path(__file__).resolve().parents[1]
LOG = json.loads((ROOT / "reference/change_log_v4_s39.json").read_text())
S42 = [s for s in LOG["steps"] if s.get("release") == "v4-s42"]


def _cut_run() -> dict:
    p = [q for q in sorted(Path(X.OUT).glob("*.json"))
         if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    assert p, f"no out/v4 run file written by engine {X.ENGINE_VERSION}"
    return json.loads(p[-1].read_text())


def test_each_of_the_seven_fixes_has_a_measured_v4_s42_step():
    items = [s["item"] for s in S42]
    for want in ("A1", "A2", "A3", "A4", "A5", "C1", "D1"):
        assert sum(1 for i in items if i.startswith(want + ":")) == 1, want
    for s in S42:
        assert "0195" in s["decision"], s["item"]
        assert s["headline_change_gbp_bn"] is not None and s["measured_on"].strip(), s["item"]
        assert s["status"] in ("measured", "no number moves"), s["item"]


def test_v4_s42_steps_add_up_to_the_cut_headline_less_v4_s41():
    v41 = json.loads((ROOT / "out/figures/v4-s41.json").read_text())["keys"]["headline_2002_24_gbp_bn"]["value"]
    # v4-s43 (card [internal ticket]): the current engine writes v4-s43's run file, so v4-s42's steps are checked against
    # v4-s42's released headline (out/figures/v4-s42.json); the v4-s43 step is in tests/test_change_log_v4_s43.py.
    headline = json.loads((ROOT / "out/figures/v4-s42.json").read_text())["keys"]["headline_2002_24_gbp_bn"]["value"]
    assert abs(headline - v41 - sum(s["headline_change_gbp_bn"] for s in S42)) < 1e-6
