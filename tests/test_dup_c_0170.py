"""Decision 0170 (card [internal ticket]): measure (c) release keys, tools/figures_keys/dup_c.py.

Checks, each against something the module does not compute itself:
- (a), the run's own printed gap (bills[y].totals.gap_gbp_m), is rebuilt from (c) every year;
- the engine's VAT rule rebuilds NZ11 every year, so splitting VAT by line is exact;
- carbon is taken out once: step 1 plus NZ1c is the whole power line, and the carbon the kept_price=actual row puts
  into fossil Britain's kept output is the same per MWh as NZ1c in net-zero Britain's price (same monthly carbon);
- every one-at-a-time row's move, rebuilt from its moved lines, equals the row's own printed gap;
- the generators' share before VAT equals the item 1 attribution on v4-s40 (+8.632 before VAT; v4-s39's +8.674 from
  [internal ticket] still holds on the v4-s39 run file; 0167 guard; re-pinned on card [internal ticket], 0177);
- every line is read through the one reader (`_line_m`).
The run file is the latest out/v4 file written by this engine version, or $DUP_C_RUN.
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

from gascf import export_v4 as X
from gascf.figures import to_2024
from tools.figures_keys import dup_c as D

ROOT = Path(__file__).resolve().parents[1]


def _run_path() -> Path:
    if os.environ.get("DUP_C_RUN"):
        return Path(os.environ["DUP_C_RUN"])
    hits = [q for q in sorted((ROOT / "out/v4").glob("*.json"))
            if json.loads(q.read_text())["meta"].get("engine_version") == X.ENGINE_VERSION]
    if not hits:
        pytest.skip(f"no out/v4 file written by engine {X.ENGINE_VERSION} yet")
    return hits[-1]


@pytest.fixture(scope="module")
def run():
    return json.loads(_run_path().read_text())


@pytest.fixture(scope="module")
def keys(run):
    return D.values(run)


def test_every_declared_key_has_a_value(keys):
    assert set(keys) == set(D.DECLARED)
    assert all(v is not None for v in keys.values())


def test_a_is_rebuilt_from_c_every_year(run):
    for y in D.YEARS:
        p = D.year_parts(run, y)
        a = run["bills"][y]["totals"]["gap_gbp_m"] * D._real(run, y)
        rebuilt = p["c"] + p["carbon"] + p["vat_carbon"] + p["ccl"] + p["schemes"] + p["vat_schemes"]
        assert rebuilt == pytest.approx(a, abs=1e-9), y


def test_c_is_cost_plus_vat_less_saving_and_the_parts_add(run, keys):
    assert keys["dup_c_2002_24_gbp_bn"] == pytest.approx(
        keys["dup_cost_2002_24_gbp_bn"] + keys["dup_vat_gbp_bn"] - keys["dup_saving_2002_24_gbp_bn"], abs=1e-9)
    assert keys["dup_cost_2002_24_gbp_bn"] == pytest.approx(sum(keys[k] for k in D.PARTS), abs=1e-9)
    assert keys["dup_saving_2002_24_gbp_bn"] == pytest.approx(sum(keys[k] for k in D.SAVING_PARTS), abs=1e-6)
    assert sum(r["c_gbp_bn"] for r in keys["dup_c_by_year"]) == pytest.approx(keys["dup_c_2002_24_gbp_bn"], abs=1e-9)
    assert keys["dup_a_minus_c_gbp_bn"] + keys["dup_c_2002_24_gbp_bn"] == pytest.approx(
        sum(to_2024(run["gap"][y]["national_gbp_bn_real"], run) for y in D.YEARS), abs=1e-6)


def test_the_engine_vat_rule_rebuilds_nz11_every_year(run):
    for y in D.YEARS:
        k, v = D._vat_rates(run, y)
        L = lambda i: D._line_m(run, y, i)                                  # noqa: E731
        rebuilt = k * sum(L(i) for i in ("NZ1", "NZ2", "NZ3", "NZ4", "NZ4b", "NZ5", "NZ6", "NZ7")) + v * L("NZ10")
        assert rebuilt == pytest.approx(L("NZ11"), abs=1e-6), y


def test_fossil_market_cost_is_its_fleet_parts_so_the_saving_split_is_exact(run):
    for y in D.YEARS:
        f = run["fleet"][y]
        parts = sum(f[k] for k in ("market_gbp_m", "moe_gbp_m", "gas_feedback_gbp_m", "fixed_gbp_m", "fuel_gbp_m",
                                   "vom_gbp_m", "transport_gbp_m"))
        assert parts == pytest.approx(D._line_m(run, y, "GO1"), abs=1e-6), y
        p = D.year_parts(run, y)
        assert p["saving_energy"] + p["saving_price_effect"] + p["saving_own_plant"] == pytest.approx(
            p["saving"], abs=1e-9), y


def test_carbon_is_taken_out_once(run):
    """Step 1 + NZ1c = NZ1 - GO1 - GO1k: carbon leaves net-zero Britain's power line once."""
    for y in D.YEARS:
        p = D.year_parts(run, y)
        r = D._real(run, y)
        L = lambda i: D._line_m(run, y, i)                                  # noqa: E731
        assert p["step1"] + p["carbon"] == pytest.approx((L("NZ1") - L("GO1") - L("GO1k")) * r, abs=1e-9), y


def test_the_same_monthly_carbon_comes_out_of_both_roads(run):
    """The kept_price=actual row puts carbon into fossil Britain's kept output; per kept MWh it is the same carbon as
    NZ1c per billed MWh in net-zero Britain ([internal ticket] measured 0.966-1.038; the spread is monthly weighting and the
    0.1 TWh rounding of the kept volume in the run's note)."""
    row = next(o for o in run["one_at_a_time"]["ranked"]["kept_price (actual / fleet avg)"]
               if o["settings"] == D.CARBON_ROW)
    ratios = []
    for y in D.YEARS:
        note = D._bill_line(run, y, "GO1k")["years_note"]
        kept = float(re.search(r"kept ([0-9.]+) TWh", note).group(1))
        v_twh = run["fleet"][y]["gen_nz_charge"]["v_twh"]
        nz = D._line_m(run, y, "NZ1c") / v_twh
        if nz > 0.5 and kept > 1:
            ratios.append(row["lines_moved_gbp_m_nominal"][y]["GO1k"] / kept / nz)
    assert ratios and 0.9 < min(ratios) and max(ratios) < 1.1, (min(ratios), max(ratios))


def test_row_moves_rebuilt_from_lines_equal_each_rows_printed_gap(run):
    head = sum(to_2024(run["gap"][y]["national_gbp_bn_real"], run) for y in D.YEARS)
    for blk in ("ranked", "methods_page"):
        for name, opts in run["one_at_a_time"][blk].items():
            for o in opts:
                d_a, _ = D._row_move_c(run, o)
                printed = to_2024(sum(o["gap_real_bn"][y] for y in D.YEARS), run) - head \
                    if isinstance(o["gap_real_bn"], dict) else to_2024(o["gap_real_bn"], run) - head
                assert d_a == pytest.approx(printed, abs=1e-6), (blk, name, o["settings"])


def test_range_r1_leaves_out_only_the_carbon_row(keys):
    assert "kept_price=actual" not in keys["dup_c_low_option"]
    assert keys["dup_c_low_r2_gbp_bn"] <= keys["dup_c_low_gbp_bn"] <= keys["dup_c_2002_24_gbp_bn"] \
        <= keys["dup_c_high_gbp_bn"]


def test_generators_share_before_vat_equals_the_item_1_attribution(keys):
    """+8.632 GBP bn before VAT, 2024 prices, 2002-24, on v4-s40 (0167 guard, against 8.5 +/- 2).

    Not an independent measurement: the v4-s40 build's isolated exports (card [internal ticket], M4 job jE) give
    8.67299 with neither item, 8.63244 with item 1 alone (0175, the permit-derived coal limit: BSUoS part
    4.62064 -> 4.58009), 8.67299 with item 2 alone and 8.63244 with all items. Re-pinned from 8.674 ([internal ticket],
    measured on v4-s39) on card [internal ticket] (0177).
    Re-pin, 24 Oct 2026 (card [internal ticket]; v4-s42, decision 0195): 8.632 -> 8.512 (BSUoS part 4.58009 -> 4.46002, from
    the v4-s42 cut's run file), moved by D1 (FY2010/11 balancing basis (i): BSUoS part 4.45908 alone) with A1 (+0.00105
    alone) and A2 (-0.00010 alone), measured on the candidate ([internal ticket]); TNUoS part unchanged."""
    got = keys["dup_cost_gen_share_bsuos_gbp_bn"] + keys["dup_cost_gen_share_tnuos_gbp_bn"]
    assert got == pytest.approx(8.512, abs=0.001)
    assert keys["dup_cost_gen_share_bsuos_gbp_bn"] == pytest.approx(4.460, abs=0.001)
    assert keys["dup_cost_gen_share_tnuos_gbp_bn"] == pytest.approx(4.052, abs=0.001)    # item 1 leaves TNUoS alone


def test_generators_share_v4_s39_is_unchanged():
    """The same reader on the frozen v4-s39 run file still gives v4-s39's 8.673 (out/figures/v4-s39.json: BSUoS
    4.62064 + TNUoS 4.05235 = 8.67299; [internal ticket] stated +8.674, the old pin held it to +/- 0.01)."""
    k = D.values(json.loads((ROOT / "out/v4/2026-10-22-s39.json").read_text()))
    assert k["dup_cost_gen_share_bsuos_gbp_bn"] + k["dup_cost_gen_share_tnuos_gbp_bn"] == pytest.approx(8.673, abs=0.001)
    assert k["dup_cost_gen_share_bsuos_gbp_bn"] == pytest.approx(4.621, abs=0.001)


def test_every_line_goes_through_the_one_reader():
    """Only _bill_line, _line_m and the totals/households reads in values/year_parts touch run['bills']; no file is
    opened and no other source is imported (0168: one number, one source)."""
    src = Path(D.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
            assert not any(m in ("csv", "json", "pathlib", "io", "os") for m in mods), mods
    assert "open(" not in src and "read_text" not in src
    bills_users = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
                   and any(isinstance(n, ast.Constant) and n.value == "bills" for n in ast.walk(f))}
    assert bills_users == {"_bill_line", "_line_m", "year_parts", "values"}


def test_central_key_says_its_choices_are_ruled_by_0173():
    """Decision 0173 (22 Oct 2026): P1 (i), P2 (i), P5 R1 ruled; P3/P4/P6 method already ruled. No key says
    provisional or OPEN; the R2 low end stays a key (Annex D prints it); the alternatives stay as built."""
    for k, d in D.DECLARED.items():
        assert d["provisional"] is False and d["ruling"] == "0170, 0173", k
        assert "provisional" not in d["note"].lower() and "OPEN" not in d["note"], k
        assert "ruled, decision 0173" in d["note"], k
    assert "dup_c_low_r2_gbp_bn" in D.DECLARED
    assert "provisional" not in D.__doc__.lower()


def test_module_is_registered_so_the_release_writes_its_keys():
    from tools import figures_keys
    assert "dup_c" in figures_keys.MODULES


def test_a_run_without_the_carbon_split_gives_none_not_an_error():
    """A toy or pre-v4-s35 run with no netzero_groups carbon split cannot give measure (c): every key is None (the
    release gate refuses None), so other modules' toy-run tests still generate (card [internal ticket])."""
    toy = {"meta": {}, "one_at_a_time": {"ranked": {}, "methods_page": {}},
           "bills": {y: {"netzero": [], "gasonly": [], "netzero_groups": {}} for y in D.YEARS}}
    assert all(v is None for v in D.values(toy).values())
