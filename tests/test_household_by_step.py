"""Ticket 19 (B6): household shares by waterfall step, steps 4 and 5 apart. `on_household_bill` also
returns `by_step[n]` for n = 1-9: domestic share d for 1-6, 0 for step 7 (CCL is not charged on
domestic supply), in full for 8 (schemes) and 9 (VAT); the parts add to `value` exactly."""
import pytest

from gascf import bills as B


def _steps():
    return [{"step": n, "value_gbp_m_nominal": float(n)} for n in range(1, 10)]


def test_by_step_rules_on_a_unit_fixture(monkeypatch):
    from gascf import system_costs
    monkeypatch.setattr(system_costs, "domestic_share_cy", lambda: {2024: 0.4})
    hb = B.on_household_bill({"households": 1e6}, 2024, _steps())
    got = [hb["by_step"][n]["nominal_gbp_m"] for n in range(1, 10)]
    assert got == pytest.approx([0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 0.0, 8.0, 9.0], abs=1e-12)


def test_parts_add_to_the_total_and_the_end_rows_are_not_steps(monkeypatch):
    """Spec test 1 at the unit seam: the waterfall also carries step 0 (Britain without net zero) and
    '=' (net zero's bill); neither is a step. Σ by_step per household = value, to 1e-9."""
    from gascf import system_costs
    monkeypatch.setattr(system_costs, "domestic_share_cy", lambda: {2024: 0.37})
    steps = [{"step": 0, "value_gbp_m_nominal": 50000.0}] + _steps() + [{"step": "=", "value_gbp_m_nominal": 50045.0}]
    hb = B.on_household_bill({"households": 2.8e7}, 2024, steps)
    assert sorted(hb["by_step"]) == list(range(1, 10))
    assert sum(p["per_household_real"] for p in hb["by_step"].values()) == pytest.approx(hb["value"], abs=1e-9)


# ---- heavy: subprocess builds on the real closure register (the run behind out/v4), under the lock ----
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).parents[1]
WINDOWS = {"2006-2023": (2006, 2023), "2006-2024": (2006, 2024), "2006-2025": (2006, 2025), "2002-2025": (2002, 2025)}


@lru_cache(maxsize=1)
def _real_register_by_step() -> dict:
    """Σ real £bn by step and window for v4-s35 settings (metered interconnectors, metered nuclear)
    and the s36 central case, plus the largest |Σ by_step − value| over all years, from a separate
    interpreter (this session runs on the conftest fixture register)."""
    code = (
        "import json; from gascf import bills as B; from gascf import waterfall as W\n"
        "out = {}\n"
        "for name, s in (('s35', B.replace(B.CENTRAL, ic_basis='metered', nuclear_cm_column=None)), ('s36', B.CENTRAL)):\n"
        "    b, wf = B.build(s), W.waterfall(s)\n"
        f"    win = {WINDOWS!r}\n"
        "    hb = {y: B.on_household_bill(b[y], y, wf[y]) for y in B.YEARS}\n"
        "    out[name] = {'windows': {w: {n: sum(hb[y]['by_step'][n]['real_gbp_m'] for y in range(a, z + 1)) / 1e3\n"
        "                                 for n in range(1, 10)} for w, (a, z) in win.items()},\n"
        "                 'max_err': max(abs(sum(p['per_household_real'] for p in hb[y]['by_step'].values()) - hb[y]['value'])\n"
        "                                for y in B.YEARS)}\n"
        "print(json.dumps(out))")
    env = {k: v for k, v in os.environ.items() if k != "GASCF_FOSSIL_CLOSURES"}
    r = subprocess.run([sys.executable, "-W", "ignore", "-c", code], env=env, cwd=ROOT, capture_output=True,
                       text=True, timeout=3000)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_v4_s35_settings_reproduce_the_b6_arithmetic_steps_4_and_5():
    """Spec test 3, first half: on v4-s35 settings, 2006-25 step 4 = 0.72 and step 5 = 3.79 £bn (2025
    money), as the B6 arithmetic on the v4-s35 run file (b6_steps45.json); and parts add to the total.
    B-merge re-pin (17 Oct 2026, fix 2): step 5 (NZ6 - GO4) is re-pinned to the merged build, 3.8309.
    It moved +0.0364 £bn only through A1 tickets merged before B, which change NZ6 and GO4 on purpose:
    09 (B4, GO4 gas index on NBP) +0.4110, 10 (F1, GO4 at RB's own gas price) -0.3370, 03 (0088, NZ6
    2017-24 daily BSUoS) -0.0376 (traced on the s36 central case; this case gives the same step 5 to
    the last digit). Step 4 (NZ5) does not move.
    Re-pin, 20 Oct 2026 (card [internal ticket]): decision 0144 item 2A (Richard Lyon, "Yes, take all the
    recommendations"; v4-s37) moves step 5 through F1 only (GO4 at RB's own gas price: the paired e =
    0.06 + 0.169 (2A) and the dQ that Cottam's closure moves (6)): 3.8309 -> 3.8970, measured by
    work/s37/repin_0144.py with this module's helper code, on these
    settings and on the central alike. Step 4 0.7119 (inside the pin)."""
    d = _real_register_by_step()["s35"]
    assert d["windows"]["2006-2025"]["4"] == pytest.approx(0.72, abs=0.01)
    assert d["windows"]["2006-2025"]["5"] == pytest.approx(3.8970, abs=0.01)
    assert d["max_err"] < 1e-9


def test_s36_central_steps_4_and_5_re_pinned_from_the_build():
    """Spec test 3, second half: re-pinned to s36 (ticket 19, group B, 17 Oct 2026) from the build on wt/B
    (this module's subprocess, real register, 2025 money). Step 4 (Capacity Market extra) 2006-25 moves
    0.718 -> 0.463 £bn under contracted interconnectors (15) and variant D nuclear (17); step 5 is
    unchanged at 3.795. B-merge re-pin (17 Oct 2026, fix 2): step 5 = 3.8309 on the merged build, moved
    +0.0364 £bn by A1 tickets 09 (B4) +0.4110, 10 (F1) -0.3370 and 03 (0088) -0.0376, traced line by
    line (only NZ6 and GO4 moved); B itself moves neither line.
    Re-pin, 19 Oct 2026 (card [internal ticket]): decision 0110 item 1.8 option (b) (Richard Lyon, 19 Oct 2026; commit
    a2ba8d1) moves step 4 only. Measured with this module's helper code on the real register at c3cc564 (before
    1.8) and a2ba8d1 (after): 2006-25 0.4635 -> 0.4495, 2006-23 0.3255 -> 0.2964, 2006-24 0.3979 -> 0.3718; step 5
    unchanged at 3.8309; the same values at c9ce0a9 (head).
    Re-pin, 20 Oct 2026 (card [internal ticket]): decision 0133 (Richard Lyon, "a": the margin over the 2027/28 peak) moves
    step 4 only (a larger margin gives RB more of its own backup, so less Capacity Market is net zero's), measured by
    work/s36/repin_0133.py with this helper: 2006-25 0.4495 -> 0.4421, 2006-23 0.2964 -> 0.2915, 2006-24
    0.3718 -> 0.3656; step 5 unchanged at 3.8309.
    Re-pin, 20 Oct 2026 (card [internal ticket]): decision 0144 (v4-s37) moves step 5 only, through F1 (2A, the paired
    elasticity, and the dQ Cottam moves): 2006-25 3.8309 -> 3.8970 (work/s37/repin_0144.py, this helper); step 4
    unchanged (0.4421)."""
    d = _real_register_by_step()["s36"]
    assert d["windows"]["2006-2025"]["4"] == pytest.approx(0.4421, abs=0.0005)
    assert d["windows"]["2006-2025"]["5"] == pytest.approx(3.8970, abs=0.0005)          # 3.8309 before 0144
    assert d["windows"]["2006-2023"]["4"] == pytest.approx(0.2915, abs=0.0005)
    assert d["windows"]["2006-2024"]["4"] == pytest.approx(0.3656, abs=0.0005)
    assert d["max_err"] < 1e-9
