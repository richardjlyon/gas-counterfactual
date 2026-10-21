"""Decision 0108 item 1.16 (Richard Lyon, 19 Oct 2026: add the B7 waterfall-formula defect, which he ruled a defect on
16 Oct, to ticket 29 now). Each waterfall step exports its signed terms and a formula generated from them, because
step 1 is NZ1 - NZ1c - GO1 - GO1k, a difference, not a sum. The value is computed from the same terms."""
import pytest

from gascf import waterfall as W

VALS = {"NZ1": 1000.0, "NZ1c": 300.0, "GO1": 500.0, "GO1k": 50.0, "NZ2": 80.0, "NZ3": 20.0, "NZ4": 10.0, "NZ5": 5.0,
        "NZ6": 60.0, "GO4": 40.0, "NZ7": 90.0, "GO5": 70.0, "NZ8": 15.0, "NZ10": 12.0, "NZ11": 9.0, "GO7": 7.0}


def _b():
    nz = [{"id": i, "national_gbp_m_nominal": v, "basis": "measured"} for i, v in VALS.items()
          if i.startswith("NZ") and i != "NZ1c"]
    go = [{"id": i, "national_gbp_m_nominal": v, "basis": "measured"} for i, v in VALS.items() if i.startswith("GO")]
    return {"netzero": nz, "fossil": go, "nz1c": {"id": "NZ1c", "national_gbp_m_nominal": VALS["NZ1c"],
                                                  "basis": "modelled"},
            "households": 1e6, "totals": {"go_gbp_m": 2000.0, "nz_gbp_m": 2000.0 + 1}}


def test_step_1_is_a_difference_with_signed_terms_and_formula():
    s1 = next(r for r in W.steps_for(_b(), 2024) if r["step"] == 1)
    assert s1["terms"] == [{"line": "NZ1", "sign": 1}, {"line": "NZ1c", "sign": -1}, {"line": "GO1", "sign": -1},
                           {"line": "GO1k", "sign": -1}]
    assert s1["formula"] == "NZ1 - NZ1c - GO1 - GO1k"
    assert s1["value_gbp_m_nominal"] == pytest.approx(1000 - 300 - 500 - 50, abs=1e-12)
    assert s1["lines"] == ["NZ1", "NZ1c", "GO1", "GO1k"]          # unchanged: the wf_ keys find steps by lines


def test_every_step_value_and_formula_come_from_its_terms():
    for r in W.steps_for(_b(), 2024):
        if r["step"] in (0, "="):
            continue
        assert r["value_gbp_m_nominal"] == pytest.approx(
            sum(t["sign"] * VALS.get(t["line"], 0.0) for t in r["terms"]), abs=1e-12), r["step"]
        assert r["formula"] == W.formula(r["terms"]), r["step"]
        assert " + -" not in r["formula"] and "--" not in r["formula"]
    f = {r["step"]: r["formula"] for r in W.steps_for(_b(), 2024) if r["step"] not in (0, "=")}
    assert f[3] == "NZ2 + NZ3 + NZ4"                                  # NZ4b absent from this fixture: left out
    assert f[5] == "NZ6 - GO4" and f[9] == "NZ11 - GO7"
