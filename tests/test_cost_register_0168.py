"""Decision 0168 (one number, one source), point 6: the engine reads every covered subsidy and system-cost series
from the shared cost register, and from nowhere else (card [internal ticket]).

How it is proved: each test points the engine at a copy of the register with ONE row moved by GBP 1m and checks
that the accessor the bills use moves by exactly that (or by its calendar-year weight). An accessor that reads
its own source file instead does not move, and the test fails on the figure, not on an import.

A static check then lists every call of a source parser in src/gascf and fails on any call outside the parsers
themselves and the named disclosure uses below, so a later rewiring cannot bypass the register unseen.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
from pathlib import Path

import pytest

from gascf import balancing, bridge, carbon, cost_register as CR, grid, register_pin as RP, schemes, subsidies

SRC = Path(__file__).resolve().parents[1] / "src/gascf"
HOME = Path("<internal path>")


def _moved_copy(tmp_path: Path, line: str, year: int, item: str | None = None, by: float = 1.0) -> Path:
    """A copy of the pinned register with one row (series, memo or input adjustment) moved by `by` GBP m."""
    text = RP.REGISTER.read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    hit = [r for r in rows if r["line_id"] == line and int(r["year"]) == year
           and (r["item_id"] == (item or line))]
    assert len(hit) == 1, (line, year, item, len(hit))
    hit[0]["cash_gbp_m"] = repr(float(hit[0]["cash_gbp_m"]) + by)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    p = tmp_path / "moved-register.csv"
    p.write_text(out.getvalue(), encoding="utf-8")
    return p


@pytest.fixture
def point_at(monkeypatch, tmp_path):
    """point_at(line, year, item=None) -> re-point the engine at a register with that row moved by +1."""
    def _point(line, year, item=None):
        p = _moved_copy(tmp_path, line, year, item)
        monkeypatch.setattr(RP, "REGISTER", p)
        monkeypatch.setattr(RP, "REGISTER_SHA256", hashlib.sha256(p.read_bytes()).hexdigest())
        RP.clear_caches()
    yield _point
    RP.clear_caches()


def _v(x):
    if isinstance(x, tuple):
        return x[0]
    if isinstance(x, dict):
        return x["gbp_m"]
    return x


# (register line, year moved, input-adjustment item or None, accessor read, expected move)
COVERED = [
    ("RO", 2020, None, lambda: subsidies.ro_fy()[2020], 1.0),
    ("RO", 2020, None, lambda: subsidies.ro()[2020], 0.75),
    ("RO_MUT", 2019, None, lambda: subsidies.ro_mutualisation_cy()[2019], 0.75),
    ("FIT", 2020, None, lambda: subsidies.fit_fy("levelisation")[2020], 1.0),
    ("FIT", 2020, None, lambda: subsidies.fit()[2020], 0.75),
    ("FIT", 2020, None, lambda: subsidies.fit_fy("scheme_value")[2020], 1.0),
    ("FIT", 2020, "alt.FIT.ofgem_scheme_value", lambda: subsidies.fit_fy("scheme_value")[2020], 1.0),
    ("CFD", 2020, None, lambda: subsidies.cfd(part="all")[2020], 1.0),
    ("CFD_OTHER", 2020, None, lambda: subsidies.cfd(part="other")[2020], 1.0),
    ("CFD_BIOMASS", 2020, None, lambda: subsidies.cfd(part="biomass")[2020], 1.0),
    ("CM_PAID", 2020, None, lambda: subsidies.CM_paid()[2020], 1.0),
    ("CCL_ELEC", 2020, None, lambda: subsidies.ccl_electricity()[2020], 1.0),
    ("CCL_ELEC", 2010, None, lambda: subsidies.ccl_electricity_exempt_period()[2010], 1.0),
    ("CPS", 2020, None, lambda: carbon.cpf_receipts()[2020], 1.0),
    ("CPS", 2020, None, lambda: bridge.cps_part(2020), 1.0),
    ("ETS_POWER", 2020, None, lambda: carbon.ets_power_receipts()[2020], 1.0),
    ("ETS_POWER_PHASE2", 2010, None, lambda: carbon.nz1c_split(
        {2010: {"gbp_m": 0.0, "basis": "measured", "source_id": "t"}})[2010]["carbon_price_receipts"]
        ["ets_phase2_gbp_m"] / __import__("gascf.system_costs", fromlist=["x"]).gb_share_of_uk(2010)[0], 1.0),
    ("BSUOS", 2020, None, lambda: balancing.nz6(gen_share="included")[2020], 1.0),
    ("BSUOS", 2020, None, lambda: balancing.nz6(gen_share="removed")[2020], 1.0),
    ("BSUOS", 2020, "rb.BSUOS.generators_share_out", lambda: balancing.nz6(gen_share="removed")[2020], 1.0),
    ("TNUOS", 2020, None, lambda: grid.nz7(gen_share="included")[2020], 1.0),
    ("TNUOS", 2020, None, lambda: grid.nz7(gen_share="removed")[2020], 1.0),
    ("TNUOS", 2020, "rb.TNUOS.generators_share_out", lambda: grid.nz7(gen_share="removed")[2020], 1.0),
    ("ENERGY_SAVING", 2020, None, lambda: schemes.schemes()[2020], 1.0),
]


@pytest.mark.parametrize("line,year,item,read,move", COVERED,
                         ids=[f"{c[0]}-{c[1]}-{c[2] or 'series'}-{i}" for i, c in enumerate(COVERED)])
def test_covered_series_is_read_from_the_register(point_at, line, year, item, read, move):
    RP.clear_caches()
    before = _v(read())
    point_at(line, year, item)
    after = _v(read())
    assert after - before == pytest.approx(move, abs=1e-9), (
        f"{line} {year}{' ' + item if item else ''}: the register row moved by 1.0 but the engine's value moved "
        f"by {after - before}: this series is read from somewhere other than the register (0168)")


def test_register_is_pinned_and_refuses_other_bytes(tmp_path):
    reg = RP.register()
    assert reg.sha256 == RP.REGISTER_SHA256
    p = _moved_copy(tmp_path, "RO", 2020)
    with pytest.raises(CR.RegisterError, match="not the pinned register"):
        CR.load(p, RP.REGISTER_SHA256)


def test_vendored_register_is_the_register_homes_file():
    home = HOME / RP.REGISTER.name
    if not home.is_file():
        pytest.skip(f"register home not reachable from here: {home}")
    assert hashlib.sha256(home.read_bytes()).hexdigest() == RP.REGISTER_SHA256


# The register is a faithful copy of the release's own reading of its sources: every covered accessor equals its
# source parser (the register's builder) to GBP 1e-6m, with the same basis and source id.
PAIRS = [
    (lambda: subsidies.ro_fy(), lambda: subsidies.src_ro_fy()),
    (lambda: subsidies.fit_fy("levelisation"), lambda: subsidies.src_fit_fy("levelisation")),
    (lambda: subsidies.fit_fy("scheme_value"), lambda: subsidies.src_fit_fy("scheme_value")),
    (lambda: subsidies.cfd(part="all"), lambda: subsidies.src_cfd(part="all")),
    (lambda: subsidies.cfd(part="other"), lambda: subsidies.src_cfd(part="other")),
    (lambda: subsidies.cfd(part="biomass"), lambda: subsidies.src_cfd(part="biomass")),
    (lambda: subsidies.CM_paid(), lambda: subsidies.src_CM_paid()),
    (lambda: carbon.cpf_receipts(), lambda: carbon.src_cpf_receipts()),
    (lambda: carbon.ets_power_receipts(), lambda: carbon.src_ets_power_receipts()),
    (lambda: balancing.nz6(gen_share="removed"), lambda: balancing.src_nz6(gen_share="removed")),
    (lambda: balancing.nz6(gen_share="included"), lambda: balancing.src_nz6(gen_share="included")),
    (lambda: grid.nz7(gen_share="removed"), lambda: grid.src_nz7(gen_share="removed")),
    (lambda: grid.nz7(gen_share="included"), lambda: grid.src_nz7(gen_share="included")),
    (lambda: schemes.schemes(), lambda: schemes.src_schemes()),
]


def _flat(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _flat(v, f"{path}.{k}")
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x):
            yield from _flat(v, f"{path}[{i}]")
    else:
        yield path, x


@pytest.mark.parametrize("reg,src", PAIRS, ids=[str(i) for i in range(len(PAIRS))])
def test_register_equals_the_release_source_reading(reg, src):
    RP.clear_caches()
    a, b = dict(_flat(reg())), dict(_flat(src()))
    assert a.keys() == b.keys()
    for k in a:
        if isinstance(a[k], float) or isinstance(b[k], float):
            assert a[k] == pytest.approx(b[k], abs=1e-6), k
        else:
            assert a[k] == b[k], k


# ---------------------------------------------------------------- static: no covered source parser is called
# outside the parsers themselves, except the named disclosure uses (each prints a source reading beside the
# register figure; none feeds a bill line).
PARSERS = {
    "read_ro_sy1_4", "read_ro_sy5_8", "read_ro_sy9_23", "read_ro_2025_26_ex_ante", "read_ro_mutualisation",
    "read_fit_scheme_value", "read_fit_quarterly_payments", "fit_fy_scheme_value", "read_fit_levelisation",
    "fit_sy1_5_figure_2_5", "cfd_monthly", "cfd_monthly_by_group", "cm_monthly", "read_ccl_table_1b",
    "read_ccl_table_1c_electricity", "bsuos_fy", "bsuos_daily", "bsuos_csv_fy", "fy2025_estimate", "tnuos_fy",
    "read_tnuos_year", "ets_power_phases", "uk_revenue_2013_20", "ukets_revenue_cy", "ukets_revenue_2025",
    "phase2_revenue_cy", "phase3_2012", "monthly",
    "src_ro_fy", "src_fit_fy", "src_cfd", "src_CM_paid", "src_cpf_receipts", "src_ets_power_receipts",
    "src_nz6", "src_nz7", "src_schemes",
}
# functions that ARE the source reading (the register's builder and its helpers)
BUILDER = {
    "subsidies": {"src_ro_fy", "src_fit_fy", "src_cfd", "src_CM_paid", "fit_fy_scheme_value",
                  "read_fit_levelisation", "read_ro_sy9_23", "read_ro_mutualisation", "cfd_monthly",
                  "cfd_monthly_by_group", "cm_monthly", "read_ccl_table_1b", "read_ccl_table_1c_electricity",
                  "fit_sy1_5_figure_2_5", "read_fit_scheme_value", "read_fit_quarterly_payments",
                  "read_ro_sy1_4", "read_ro_sy5_8", "read_ro_2025_26_ex_ante"},
    "carbon": {"src_cpf_receipts", "src_ets_power_receipts", "ets_power_phases"},
    "balancing": {"src_nz6", "bsuos_fy", "bsuos_daily", "bsuos_csv_fy", "fy2025_estimate"},
    "grid": {"src_nz7", "tnuos_fy", "read_tnuos_year"},
    "schemes": {"src_schemes", "monthly"},
    "ets_auctions": {"uk_revenue_2013_20", "ukets_revenue_cy", "ukets_revenue_2025", "phase2_revenue_cy",
                     "phase3_2012", "ukets_auction_rows", "_checked_rows", "_rows"},
}
DISCLOSURE = {
    ("subsidies", "ccl_2015_monthly_readings"): "HMRC Table 1c monthly declarations, printed beside D2's 7/12",
    ("carbon", "cps_2025_record"): "HMRC's printed 2025 CPF split, kept as a noted number only (0054)",
    ("carbon", "shortfall_rule_receipts"): "0058 shortfall sensitivity: UK auction revenue before power's share; "
                                           "moves only the split inside NZ1c",
    ("carbon", "ets_revenue_periods"): "the period each year's auction revenue covers (dates, not money)",
    ("carbon_blocks", "ets_auctions_block"): "the auction files' readings printed as the ETS source block",
    ("bills", "record_netzero_fallbacks"): "sizes of the two estimated BSUoS charging years, for meta.fallbacks",
    ("system_costs", "*"): "NESO constraint breakdown for the per-household answers (definitions D-12)",
}


def _calls():
    out = []
    for f in sorted(SRC.glob("*.py")):
        mod = f.stem
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            for c in ast.walk(fn):
                if isinstance(c, ast.Call):
                    name = (c.func.attr if isinstance(c.func, ast.Attribute) else
                            c.func.id if isinstance(c.func, ast.Name) else None)
                    if name in PARSERS:
                        out.append((mod, fn.name, name))
    return out


def test_no_covered_source_parser_is_called_outside_the_builder():
    bad = []
    for mod, fn, name in _calls():
        if fn in BUILDER.get(mod, set()) or (mod, fn) in DISCLOSURE or (mod, "*") in DISCLOSURE:
            continue
        if name == "monthly" and mod != "schemes":
            continue          # other modules' own monthly() helpers are not the schemes parser
        bad.append(f"{mod}.{fn} calls {name}")
    assert not bad, ("covered series read from a source parser, not the register (0168): " + "; ".join(sorted(set(bad))))
